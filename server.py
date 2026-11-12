#!/usr/bin/env python3
"""Vorleser – lokaler Hörbuch-Server.

Stimmen: Microsoft Edge (online, gratis) mit Piper (offline) als Fallback.
Start:   .venv/bin/python server.py   →  http://127.0.0.1:8765
"""
from __future__ import annotations

import hmac
import json
import os
import re
import secrets
import shutil
import threading
import time
import uuid
from http.cookies import CookieError, SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, unquote, urlparse

import bugreport
import meldungen
import clone_setup
import exporter
import importers
import ocr
import paths
import settings
import storage
import stt
import tts
import uninstaller
import updater
from importers import ImportFailed, import_file
from textproc import DEFAULT_LANG, LANGS, chunk_text, detect_language

DOCS_DIR = paths.DATA_DIR / "docs"
STATIC_DIR = paths.STATIC_DIR
HOST, PORT = "127.0.0.1", int(os.environ.get("VORLESER_PORT", "8765"))
MAX_UPLOAD = 300 * 1024 * 1024
_quick: dict[str, dict] = {}            # markierter Text (nur im Speicher)
STATS_FILE = paths.DATA_DIR / "hoerzeit.json"   # Hör-Rückblick (3.0)
_stats_lock = threading.Lock()


def _stats_load() -> dict:
    try:
        data = json.loads(STATS_FILE.read_text("utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}

# Zugriffsschutz: Jede Webseite im Browser kann Anfragen an 127.0.0.1 schicken. Deshalb verlangt /api/* einen
# Zufallsschlüssel pro Start – die eigene Oberfläche bekommt ihn als Cookie (SameSite=Strict, fremde Seiten
# senden ihn nicht mit), ein zweiter App-Start liest ihn aus TOKEN_FILE. Host/Origin-Prüfung gegen DNS-Rebinding.
TOKEN = secrets.token_urlsafe(32)
TOKEN_HEADER = "X-Vorleser-Token"
TOKEN_FILE = paths.DATA_DIR / "api-token"

DOCS_DIR.mkdir(parents=True, exist_ok=True)


# --------------------------------------------------------------------------- #
# Bibliothek
# --------------------------------------------------------------------------- #
_doc_lock = threading.Lock()


def doc_path(doc_id: str) -> Path:
    if not re.fullmatch(r"[0-9a-f]{32}", doc_id):
        raise KeyError(doc_id)
    return DOCS_DIR / f"{doc_id}.json"


def upgrade_doc(doc: dict) -> dict:
    """Ältere Dokumente auf das aktuelle Format bringen."""
    doc["voice"] = tts.normalize_voice_id(doc.get("voice") or "")
    if "lang" not in doc:
        v = tts.voice_by_id(doc["voice"])
        doc["lang"] = v["lang"] if v else DEFAULT_LANG
    doc.setdefault("chapters", [])
    return doc


def load_doc(doc_id: str) -> dict:
    p = doc_path(doc_id)
    if not p.exists():
        raise KeyError(doc_id)
    return upgrade_doc(json.loads(p.read_text("utf-8")))


def save_doc(doc: dict) -> None:
    p = doc_path(doc["id"])
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(doc, ensure_ascii=False), "utf-8")
    tmp.replace(p)


def doc_text(doc: dict) -> str:
    """Abschnitte wieder zu bearbeitbarem Text zusammensetzen (Kapitel als „# Titel“)."""
    parts, cur = [], []
    for c in doc["chunks"]:
        if c.get("h") or c.get("par"):
            if cur:
                parts.append(" ".join(cur))
            cur = []
        if c.get("h"):
            parts.append(f"# {c['text']}")
        else:
            cur.append(c["text"])
    if cur:
        parts.append(" ".join(cur))
    return "\n\n".join(parts)


def doc_summary(doc: dict) -> dict:
    return {
        "id": doc["id"], "title": doc["title"], "created": doc["created"], "lang": doc["lang"],
        "count": len(doc["chunks"]), "chapters": len(doc["chapters"]), "progress": doc["progress"],
        "sample": bool(doc.get("sample")),
    }


# --------------------------------------------------------------------------- #
# HTTP
# --------------------------------------------------------------------------- #
def parse_changelog(path: Path) -> list[dict]:
    """CHANGELOG.md → [{version, lead, items}] (neueste zuerst). Erste Zeile eines Abschnitts = Kurzfassung,
    „- “-Zeilen = Punkte (eingerückte Folgezeilen gehören zum Punkt davor)."""
    try:
        text = path.read_text("utf-8")
    except OSError:
        return []
    out: list[dict] = []
    for line in text.splitlines():
        m = re.match(r"^## (\d+(?:\.\d+)*)\s*$", line)
        if m:
            out.append({"version": m.group(1), "lead": "", "items": []})
            continue
        if not out or not line.strip():
            continue
        rel = out[-1]
        if line.startswith("- "):
            rel["items"].append(line[2:].strip())
        elif line.startswith((" ", "\t")) and rel["items"]:
            rel["items"][-1] += " " + line.strip()
        elif not rel["lead"] and not rel["items"]:
            rel["lead"] = line.strip()
    return out


class Handler(BaseHTTPRequestHandler):
    server_version = "Vorleser/2.0"

    def log_message(self, fmt, *args):  # Audio-Abrufe und Statusabfragen nicht loggen
        line = str(args[0]) if args else ""
        if not any(k in line for k in ("/audio/", "/marks/", "/export ", "/prepare ", "/api/cache", "/api/voices/preview")):
            super().log_message(fmt, *args)

    # -- helpers --
    def send(self, status: int, body: bytes, ctype: str, extra: dict | None = None):
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def json(self, obj, status: int = 200):
        self.send(status, json.dumps(obj, ensure_ascii=False).encode(), "application/json; charset=utf-8")

    def error(self, status: int, msg: str):
        self.json({"error": msg}, status)

    def raw_body(self) -> bytes:
        n = int(self.headers.get("Content-Length") or 0)
        if n > MAX_UPLOAD:
            raise ValueError("Datei zu groß (max. 300 MB)")
        return self.rfile.read(n)

    def body(self) -> dict:
        try:
            data = json.loads(self.raw_body() or b"{}")
        except (json.JSONDecodeError, UnicodeDecodeError):
            raise ValueError(meldungen.ANFRAGE) from None
        if not isinstance(data, dict):
            raise ValueError(meldungen.ANFRAGE)
        return data

    def _port(self) -> int:
        return self.server.server_address[1]

    def _allowed_origin(self) -> bool:
        """Nur Anfragen an 127.0.0.1/localhost auf unserem Port, von unserer eigenen Seite."""
        own = {f"127.0.0.1:{self._port()}", f"localhost:{self._port()}"}
        if (self.headers.get("Host") or "").lower() not in own:
            return False
        origin = self.headers.get("Origin")
        return origin is None or origin.lower() in {f"http://{h}" for h in own}

    def _has_token(self) -> bool:
        if _same(self.headers.get(TOKEN_HEADER, ""), TOKEN):
            return True
        try:
            morsel = SimpleCookie(self.headers.get("Cookie") or "").get(cookie_name(self._port()))
        except CookieError:
            return False
        return bool(morsel) and _same(morsel.value, TOKEN)

    def route(self, method: str):
        path = urlparse(self.path).path
        if not self._allowed_origin() or (path.startswith("/api/") and not self._has_token()):
            return self.error(403, "Nicht erlaubt")
        try:
            for pattern, m_, fn in ROUTES:
                if m_ == method and (m := re.fullmatch(pattern, path)):
                    return fn(self, *m.groups())
            self.error(404, "Nicht gefunden")
        except KeyError as e:
            print(f"[server] {method} {path}: nicht gefunden ({e!r})", flush=True)
            self.error(404, meldungen.NICHT_GEFUNDEN)
        except (ValueError, ImportFailed, meldungen.Meldung) as e:
            print(f"[server] {method} {path}: {e}", flush=True)
            self.error(400, meldungen.fuer_nutzer(e))
        except (BrokenPipeError, ConnectionResetError):
            pass
        except Exception as e:
            meldungen.loggen(f"server {method} {path}", e)       # mit Traceback – nur der feste Satz geht in die UI
            try:
                self.error(500, meldungen.fuer_nutzer(e))
            except Exception:
                pass

    def do_GET(self): self.route("GET")
    def do_POST(self): self.route("POST")
    def do_PATCH(self): self.route("PATCH")
    def do_DELETE(self): self.route("DELETE")
    def do_PUT(self): self.route("PUT")

    # -- Seite & Stammdaten --
    def index(self):
        cookie = f"{cookie_name(self._port())}={TOKEN}; Path=/; HttpOnly; SameSite=Strict"
        self.send(200, (STATIC_DIR / "index.html").read_bytes(), "text/html; charset=utf-8",
                  {"Cache-Control": "no-store", "Set-Cookie": cookie})

    def static(self, name):
        ext = name.rsplit(".", 1)[1]
        if ext == "m4a":                                    # Atmosphäre-Klänge (Version 3.0)
            return self.send(200, (STATIC_DIR / name).read_bytes(), "audio/mp4", {"Cache-Control": "max-age=86400"})
        if ext == "woff2":                                  # mitgelieferte Schriften (3.0.2, vorher Google Fonts)
            return self.send(200, (STATIC_DIR / name).read_bytes(), "font/woff2", {"Cache-Control": "max-age=86400"})
        ctype = {"css": "text/css", "js": "text/javascript"}[ext] + "; charset=utf-8"
        self.send(200, (STATIC_DIR / name).read_bytes(), ctype, {"Cache-Control": "no-cache"})

    # -- Einstellungen --
    def settings_get(self):
        self.json(settings.load())

    def settings_patch(self):
        res = settings.update(self.body())
        tts.schedule_prune()
        self.json(res)

    def preview(self):
        q = parse_qs(urlparse(self.path).query)
        voice, lang = (q.get("voice") or [""])[0], (q.get("lang") or ["de"])[0]
        if not tts.voice_by_id(voice):
            raise KeyError("Stimme")
        data, mime, used = tts.synthesize(tts.PREVIEW_TEXT.get(lang, tts.PREVIEW_TEXT["de"]), voice, lang)
        self.send(200, data, mime, {"Cache-Control": "no-store", "X-Voice-Used": used})


    def voices(self):
        self.json({"voices": tts.list_voices(), "langs": LANGS,
                   "defaults": {l: tts.default_voice(l) for l in LANGS},
                   "features": {"dictate": stt.stt_available(), "clone": tts.clone_available(),
                                "cloneSetup": clone_setup.supported(), "desktop": DESKTOP,
                                "os": "mac" if paths.IS_MAC else "win" if paths.IS_WIN else "other",
                                "gpu": clone_setup.gpu_kind()}})

    def detect(self):
        self.json({"lang": detect_language(self.body().get("text") or "")})

    def do_import(self):
        name = unquote(self.headers.get("X-Filename") or "datei.txt")
        data = self.raw_body()
        try:
            res = import_file(name, data)
        except importers.BrauchtTexterkennung:       # eingescannt → Texterkennung im Hintergrund (Version 3.0)
            if not ocr.verfuegbar():
                raise ImportFailed(importers.PDF_SCAN + " " + ocr.OCR_FEHLT)
            stem = Path(name).stem

            def fertig(seiten):
                r = importers.pdf_mit_texterkennung(data, stem, seiten)
                r["lang"] = detect_language(r["text"])
                r["ocr"] = True
                return r
            return self.json({"ocr": ocr.start(data, name, fertig)})
        res["lang"] = detect_language(res["text"])
        self.json(res)

    def ocr_status(self, jid):
        self.json(ocr.status(jid))

    def ocr_cancel(self, jid):
        ocr.abbrechen(jid)
        self.json({"ok": True})

    def import_link(self):
        from importers import import_url
        res = import_url(str(self.body().get("url") or ""))
        res["lang"] = detect_language(res["text"])
        self.json(res)

    # -- Dokumente --
    def list_docs(self):
        def summary(doc):                          # + wie viele Abschnitte schon fertig erzeugt sind (heller Balken)
            return {**doc_summary(doc), "prepared": sum(tts.is_cached(c["text"], doc["voice"], doc["id"]) for c in doc["chunks"])}
        loaded = []
        with _doc_lock:                            # nur das Lesen unter der Sperre – das Zählen (pro Abschnitt eine
            for p in DOCS_DIR.glob("*.json"):      # Datei-Abfrage) blockierte sonst Vorlesen und Fortschritt-Speichern
                try:                               # eine kaputte Datei (Stromausfall, Sync-Tool) darf nicht alle verstecken
                    loaded.append(upgrade_doc(json.loads(p.read_text("utf-8"))))
                except Exception as e:
                    print(f"[server] Text-Datei {p.name} übersprungen (beschädigt?): {e!r}", flush=True)
        docs = [summary(d) for d in loaded]
        docs.sort(key=lambda d: d["progress"].get("updated") or d["created"], reverse=True)
        self.json({"docs": docs})

    def create_doc(self):
        data = self.body()
        text = (data.get("text") or "").strip()
        if not text:
            raise ValueError("Kein Text")
        lang = data.get("lang") if data.get("lang") in LANGS else detect_language(text)
        ids = [v["id"] for v in tts.voices_for(lang)]
        voice = data.get("voice") if data.get("voice") in ids else tts.default_voice(lang)
        if not voice:
            raise ValueError("Für diese Sprache ist gerade keine Stimme verfügbar")
        chunks, chapters = chunk_text(text, lang)
        if not chunks:
            raise ValueError("Kein vorlesbarer Text gefunden")
        title = (data.get("title") or "").strip() or text.lstrip("# ").split("\n", 1)[0][:60]
        doc = {
            "id": uuid.uuid4().hex, "title": title, "created": time.time(), "lang": lang, "voice": voice,
            "chunks": chunks, "chapters": chapters,
            "progress": {"chunk": 0, "offset": 0.0, "updated": None},
        }
        orig = data.get("original")
        if isinstance(orig, str) and orig.strip() and len(orig) < 20_000_000:
            doc["original"] = orig          # Version 3.0: PDF vor dem Aufräumen („Original wiederherstellen“)
        if data.get("sample"):              # Beispieltext aus dem Rundgang (wird beim erneuten Rundgang wiederverwendet)
            doc["sample"] = True
        with _doc_lock:
            save_doc(doc)
        self.json(doc_summary(doc), 201)

    def get_doc(self, doc_id):
        with _doc_lock:
            doc = load_doc(doc_id)
        orig = doc.pop("original", None)           # kann MB groß sein → nur bei Bedarf (/original)
        self.json({**doc, "hasOriginal": bool(orig)})

    # -- Hör-Rückblick (Version 3.0, Etappe 3): nur echte Hörzeit, lokal in data/hoerzeit.json --
    def stats_add(self):
        p = self.body()
        secs = float(p.get("secs") or 0)
        doc = str(p.get("doc") or "")
        if not (0 < secs <= 600) and not p.get("finished"):
            raise ValueError(meldungen.ANFRAGE)
        day = time.strftime("%Y-%m-%d")
        with _stats_lock:
            data = _stats_load()
            d = data.setdefault(day, {"secs": 0, "docs": {}, "finished": []})
            if secs > 0:
                d["secs"] = round(d["secs"] + secs, 1)
                d["docs"][doc] = round(d["docs"].get(doc, 0) + secs, 1)
            if p.get("finished") and doc and doc not in d["finished"]:
                d["finished"].append(doc)
            for old in sorted(data)[:-400]:            # gut ein Jahr reicht
                data.pop(old, None)
            tmp = STATS_FILE.with_suffix(".tmp")
            tmp.write_text(json.dumps(data), "utf-8")
            tmp.replace(STATS_FILE)
        self.json({"ok": True})

    def stats_week(self):
        """Woche Mo–So: last=1 → die vergangene Woche (Montagskarte), sonst die laufende."""
        q = parse_qs(urlparse(self.path).query)
        import datetime as dt
        today = dt.date.today()
        monday = today - dt.timedelta(days=today.weekday()) - dt.timedelta(days=7 if q.get("last") == ["1"] else 0)
        with _stats_lock:
            data = _stats_load()
        days, per_doc, finished = [], {}, set()
        for k in range(7):
            day = (monday + dt.timedelta(days=k)).isoformat()
            d = data.get(day, {})
            days.append({"date": day, "secs": d.get("secs", 0)})
            for doc_id, sec in d.get("docs", {}).items():
                per_doc[doc_id] = per_doc.get(doc_id, 0) + sec
            finished.update(d.get("finished", []))
        top = max(per_doc.items(), key=lambda x: x[1], default=(None, 0))[0]
        title = None
        if top:
            try:
                with _doc_lock:
                    title = load_doc(top)["title"]
            except Exception:
                title = None
        self.json({"week": monday.isoformat(), "days": days, "total": round(sum(x["secs"] for x in days)),
                   "finished": len(finished), "top": title})

    # -- Lesezeichen (Version 3.0, Etappe 3): gehören zum Text --
    def bm_add(self, doc_id):
        p = self.body()
        with _doc_lock:
            doc = load_doc(doc_id)
            i = int(p.get("chunk", -1))
            if not 0 <= i < len(doc["chunks"]):
                raise KeyError("Abschnitt")
            bms = doc.setdefault("bookmarks", [])
            if not any(b["chunk"] == i for b in bms):
                bms.append({"id": uuid.uuid4().hex[:12], "chunk": i, "text": doc["chunks"][i]["text"][:160],
                            "note": str(p.get("note") or "")[:2000], "created": time.time()})
                bms.sort(key=lambda b: b["chunk"])
                save_doc(doc)
        self.json({"bookmarks": doc["bookmarks"]})

    def bm_patch(self, doc_id, bid):
        note = str(self.body().get("note") or "")[:2000]
        with _doc_lock:
            doc = load_doc(doc_id)
            b = next((b for b in doc.get("bookmarks", []) if b["id"] == bid), None)
            if not b:
                raise KeyError("Lesezeichen")
            b["note"] = note
            save_doc(doc)
        self.json({"bookmarks": doc["bookmarks"]})

    def bm_delete(self, doc_id, bid):
        with _doc_lock:
            doc = load_doc(doc_id)
            doc["bookmarks"] = [b for b in doc.get("bookmarks", []) if b["id"] != bid]
            save_doc(doc)
        self.json({"bookmarks": doc["bookmarks"]})

    def get_original(self, doc_id):
        with _doc_lock:
            doc = load_doc(doc_id)
        if not doc.get("original"):
            raise KeyError("Original")
        self.json({"text": doc["original"]})

    def patch_doc(self, doc_id):
        data = self.body()
        with _doc_lock:
            doc = load_doc(doc_id)
            if "progress" in data:
                p = data["progress"]
                doc["progress"] = {
                    "chunk": max(0, min(int(p.get("chunk", 0)), len(doc["chunks"]) - 1)),
                    "offset": max(0.0, float(p.get("offset", 0))),
                    "frac": max(0.0, min(float(p.get("frac", 0)), 1.0)),    # Anteil im Abschnitt → gleicher % wie im Player
                    "updated": time.time(),
                }
            if data.get("voice") in [v["id"] for v in tts.voices_for(doc["lang"])]:
                doc["voice"] = data["voice"]
            if isinstance(data.get("title"), str) and data["title"].strip():
                doc["title"] = data["title"].strip()
            save_doc(doc)
        self.json(doc_summary(doc))

    def get_text(self, doc_id):
        with _doc_lock:
            doc = load_doc(doc_id)
        self.json({"title": doc["title"], "text": doc_text(doc), "lang": doc["lang"]})

    def put_text(self, doc_id):
        data = self.body()
        text = (data.get("text") or "").strip()
        if not text:
            raise ValueError("Der Text ist leer")
        with _doc_lock:
            doc = load_doc(doc_id)
            chunks, chapters = chunk_text(text, doc["lang"])
            if not chunks:
                raise ValueError("Kein vorlesbarer Text gefunden")
            # Lesezeichen an derselben Textstelle halten
            old, old_idx = doc["chunks"], min(doc["progress"]["chunk"], len(doc["chunks"]) - 1)
            cur_text = old[old_idx]["text"]
            ratio = old_idx / max(1, len(old) - 1)
            exact = [i for i, c in enumerate(chunks) if c["text"] == cur_text]
            if exact:                                   # 1) derselbe Abschnitt existiert noch → genau dorthin
                new_idx = min(exact, key=lambda i: abs(i / max(1, len(chunks) - 1) - ratio))
            else:                                       # 2) Abschnitt geändert → über die Zeichenposition
                before = [c["text"] for c in old[:old_idx]]
                # Anker: der letzte unveränderte Abschnitt davor
                anchor = next((t for t in reversed(before) if any(c["text"] == t for c in chunks)), None)
                if anchor is not None:
                    a_idx = max(i for i, c in enumerate(chunks) if c["text"] == anchor)
                    new_idx = min(a_idx + 1, len(chunks) - 1)
                else:
                    pos = sum(len(t) + 1 for t in before)
                    acc, new_idx = 0, len(chunks) - 1
                    for i, c in enumerate(chunks):
                        if acc + len(c["text"]) >= pos:
                            new_idx = i
                            break
                        acc += len(c["text"]) + 1
            same = bool(exact)
            doc["progress"] = {**doc["progress"], "chunk": new_idx,
                               "offset": doc["progress"]["offset"] if same else 0.0}
            doc["chunks"], doc["chapters"] = chunks, chapters
            # Lesezeichen (3.0): über ihren Ausschnitt wiederfinden; Abschnitt weg → Lesezeichen weg
            keep = []
            for bm in doc.get("bookmarks", []):
                head = bm.get("text", "")[:60]
                hit = next((i for i, c in enumerate(chunks) if head and c["text"].startswith(head)), None)
                if hit is not None and all(k["chunk"] != hit for k in keep):
                    keep.append({**bm, "chunk": hit, "text": chunks[hit]["text"][:160]})
            if "bookmarks" in doc:
                doc["bookmarks"] = sorted(keep, key=lambda b: b["chunk"])
            if isinstance(data.get("title"), str) and data["title"].strip():
                doc["title"] = data["title"].strip()
            doc["edited"] = time.time()
            save_doc(doc)
        exporter.delete_exports(doc_id)      # alter Export passt nicht mehr zum Text
        self.json(doc_summary(doc))

    def delete_doc(self, doc_id):
        with _doc_lock:
            try:
                doc = load_doc(doc_id)
            except KeyError:
                doc = None
            doc_path(doc_id).unlink(missing_ok=True)
        exporter.delete_exports(doc_id)
        freed = storage.delete_doc_audio(doc) if doc else 0   # erzeugtes Audio + Wortmarken mitlöschen
        self.json({"ok": True, "freed": freed})

    # -- Markierten Text vorlesen (Version 3.0): nur im Speicher, „In Bibliothek sichern“ macht einen Text daraus --
    def quick_create(self):
        data = self.body()
        text = (data.get("text") or "").strip()
        if not text:
            raise ValueError("Kein Text")
        lang = detect_language(text)
        ids = [v["id"] for v in tts.voices_for(lang)]
        voice = data.get("voice") if data.get("voice") in ids else tts.default_voice(lang)
        if not voice:
            raise ValueError("Für diese Sprache ist gerade keine Stimme verfügbar")
        chunks, _ = chunk_text(text, lang)
        if not chunks:
            raise ValueError("Kein vorlesbarer Text gefunden")
        qid = uuid.uuid4().hex
        with _doc_lock:
            _quick[qid] = {"text": text, "lang": lang, "voice": voice, "chunks": chunks}
            while len(_quick) > 5:                       # nur die letzten paar behalten
                _quick.pop(next(iter(_quick)))
        self.json(self._quick_info(qid, _quick[qid]))

    def _quick_info(self, qid, q):
        ids = [v["id"] for v in tts.voices_for(q["lang"])]
        fast = next((v for v in ids if not v.startswith("clone:")), None)
        slow = q["voice"].startswith("clone:")
        return {"id": qid, "lang": q["lang"], "voice": q["voice"], "count": len(q["chunks"]), "preview": q["text"][:160],
                "texts": [c["text"] for c in q["chunks"]],             # für die Mitlesezeile im Mini-Player
                "slow": slow, "fast": fast if slow else None,
                "voiceName": next((v.get("name") or v["id"] for v in tts.voices_for(q["lang"]) if v["id"] == q["voice"]), q["voice"])}

    def quick_info(self, qid):
        with _doc_lock:
            q = _quick.get(qid)
        if not q:
            raise KeyError("Text")
        self.json(self._quick_info(qid, q))

    def quick_voice(self, qid):
        voice = self.body().get("voice")
        with _doc_lock:
            q = _quick.get(qid)
            if not q or voice not in [v["id"] for v in tts.voices_for(q["lang"])]:
                raise KeyError("Stimme")
            q["voice"] = voice
        self.json(self._quick_info(qid, q))

    def mini(self):
        """Mini-Player für markierten Text (eigenes rahmenloses Fenster der Desktop-App)."""
        cookie = f"{cookie_name(self._port())}={TOKEN}; Path=/; HttpOnly; SameSite=Strict"
        self.send(200, (STATIC_DIR / "mini.html").read_bytes(), "text/html; charset=utf-8",
                  {"Cache-Control": "no-store", "Set-Cookie": cookie})

    # -- Aussprache-Wörterbuch (Version 3.0) --
    def lex_get(self):
        self.json({"entries": tts.lexikon()})

    def lex_put(self):
        entries = self.body().get("entries")
        if not isinstance(entries, list):
            raise ValueError(meldungen.ANFRAGE)
        self.json({"entries": tts.lexikon_speichern(entries)})

    def lex_probe(self):
        """Probe: wie klingt die Schreibweise? (Standardstimme der Sprache des Worts, ohne Ersatzstimme)"""
        p = self.body()
        sprich = str(p.get("sprich") or "").strip()[:200]
        if not sprich:
            raise ValueError("Kein Text")
        lang = p.get("lang") if p.get("lang") in LANGS else "de"
        voice = tts.default_voice(lang)
        if voice and voice.startswith("clone:"):          # Probe soll schnell sein
            voice = next((v["id"] for v in tts.voices_for(lang) if not v["id"].startswith("clone:")), voice)
        data, mime, used = tts.synthesize(sprich, voice, lang, fallback=False)
        self.send(200, data, mime, {"Cache-Control": "no-store", "X-Voice-Used": used})

    def lex_affected(self):
        """Wie viele schon erzeugte Abschnitte enthalten das Wort? (für „… werden neu kalibriert“)"""
        import re as _re
        p = self.body()
        wort = str(p.get("wort") or "").strip()
        only = p.get("doc") if _re.fullmatch(r"[0-9a-f]{32}", str(p.get("doc") or "")) else None
        lang = p.get("lang") if p.get("lang") in LANGS else None
        if not wort:
            self.json({"count": 0}); return
        rx = _re.compile(r"(?<!\w)" + _re.escape(wort) + r"(?!\w)")
        n = 0
        with _doc_lock:
            for path in DOCS_DIR.glob("*.json"):
                try:
                    doc = json.loads(path.read_text("utf-8"))
                except Exception:
                    continue
                if only and doc.get("id") != only:
                    continue
                if lang and tts._voice_lang(doc.get("voice", "")) not in (lang, None):   # Eintrag gilt nur für seine Sprache
                    continue
                n += sum(1 for c in doc.get("chunks", []) if rx.search(c["text"]) and tts.is_cached(c["text"], doc["voice"], doc["id"]))
        self.json({"count": n})

    def quick_audio(self, qid, idx):
        with _doc_lock:
            q = _quick.get(qid)
        if not q or int(idx) >= len(q["chunks"]):
            raise KeyError("Abschnitt")
        data, mime, used = tts.synthesize(q["chunks"][int(idx)]["text"], q["voice"], q["lang"])
        self.send(200, data, mime, {"Cache-Control": "no-store", "X-Voice-Used": used})

    def quick_marks(self, qid, idx):
        with _doc_lock:
            q = _quick.get(qid)
        if not q or int(idx) >= len(q["chunks"]):
            raise KeyError("Abschnitt")
        self.json({"marks": tts.get_marks(q["chunks"][int(idx)]["text"], q["voice"], q["lang"])})

    def quick_save(self, qid):
        with _doc_lock:
            q = _quick.get(qid)
        if not q:
            raise KeyError("Text")
        chunks, chapters = chunk_text(q["text"], q["lang"])
        doc = {"id": uuid.uuid4().hex, "title": q["text"].lstrip("# ").split("\n", 1)[0][:60], "created": time.time(),
               "lang": q["lang"], "voice": q["voice"], "chunks": chunks, "chapters": chapters,
               "progress": {"chunk": 0, "offset": 0.0, "updated": None}}
        with _doc_lock:
            save_doc(doc)
        self.json(doc_summary(doc), 201)

    def audio(self, doc_id, idx):
        with _doc_lock:
            doc = load_doc(doc_id)
        idx = int(idx)
        if idx >= len(doc["chunks"]):
            raise KeyError("Abschnitt")
        # 3.0.2: nie automatisch zur Ersatzstimme wechseln (Rückmeldung Simon) – hängt die Online-Stimme, bietet der
        # Player den Wechsel an; offline=1 = ausdrücklich gewählt. pre=1 (Vorladen): bei Sperre sofort Fehler, später neu.
        q = parse_qs(urlparse(self.path).query)
        pre, offline = (q.get("pre") or [""])[0] == "1", (q.get("offline") or [""])[0] == "1"
        text = doc["chunks"][idx]["text"]
        if offline:
            fb = tts.fallback_voice(doc["lang"])
            if not fb:
                raise meldungen.Meldung(tts.KEINE_STIMME)
            data, mime, used = tts.synthesize(text, fb, doc["lang"], doc_id=doc["id"])
        else:
            try:
                data, mime, used = tts.synthesize(text, doc["voice"], doc["lang"], doc_id=doc["id"], fallback=False, sperre=pre)
            except meldungen.Meldung as e:
                if str(e) != tts.NICHTS_VORLESBAR:        # z. B. „* * *“: diese eine Stelle wie bisher überbrücken
                    raise
                data, mime, used = tts.synthesize(text, doc["voice"], doc["lang"], doc_id=doc["id"])
        self.send(200, data, mime, {"Cache-Control": "no-store", "X-Voice-Used": used})

    def marks(self, doc_id, idx):
        with _doc_lock:
            doc = load_doc(doc_id)
        idx = int(idx)
        if idx >= len(doc["chunks"]):
            raise KeyError("Abschnitt")
        self.json({"marks": tts.get_marks(doc["chunks"][idx]["text"], doc["voice"], doc["lang"], doc_id=doc["id"])})

    # -- Export --
    def export_status(self, doc_id):
        load_doc(doc_id)
        self.json(exporter.status(doc_id))

    def export_info(self, doc_id):
        """Export-Dialog: vorbereitet? + echte Länge (→ echte Größe je Format)."""
        with _doc_lock:
            doc = load_doc(doc_id)
        self.json(exporter.info(doc))

    def export_start(self, doc_id):
        with _doc_lock:
            doc = load_doc(doc_id)
        b = self.body()
        try:
            rate = float(b.get("rate") or 1)
        except (TypeError, ValueError):
            rate = 1.0
        self.json(exporter.start(doc, b.get("format", "m4b"), ambient=bool(b.get("ambient")), rate=rate))

    def export_cancel(self, doc_id):
        exporter.cancel(doc_id)
        self.json({"ok": True})

    def export_file(self, doc_id):
        with _doc_lock:
            doc = load_doc(doc_id)
        st = exporter.status(doc_id)
        if st.get("status") != "ready":
            raise KeyError("Export")
        fmt = st["format"]
        path = exporter.export_path(doc_id, fmt)
        name = re.sub(r'[\\/:*?"<>|]+', "_", doc["title"]).strip() or "hoerbuch"
        self.send_response(200)
        self.send_header("Content-Type", exporter.FORMATS[fmt][2])
        self.send_header("Content-Length", str(path.stat().st_size))
        self.send_header("Content-Disposition", f"attachment; filename*=UTF-8''{quote(name)}.{fmt}")
        self.end_headers()
        with open(path, "rb") as f:
            shutil.copyfileobj(f, self.wfile, 1024 * 256)

    # -- Vorab erzeugen (z. B. für die langsame Klonstimme) --
    def prepare_status(self, doc_id):
        """Eine Wahrheit für „vorbereitet“: was wirklich im Cache liegt (live), plus ob gerade erzeugt wird."""
        with _doc_lock:
            doc = load_doc(doc_id)
        job = exporter.status(doc_id, "prepare")
        cached = [tts.is_cached(c["text"], doc["voice"], doc["id"]) for c in doc["chunks"]]
        done, total = sum(cached), len(cached)
        status = "running" if job.get("status") == "running" else "ready" if done == total else job.get("status", "none")
        self.json({**job, "status": status, "done": done, "total": total, "cached": cached})

    def prepared_by_voice(self, doc_id):
        """Wie viele Abschnitte dieses Texts liegen in welcher Stimme schon fertig vor? (Stimmen-Menü)"""
        q = parse_qs(urlparse(self.path).query)
        voices = [v for v in (q.get("voices") or [""])[0].split(",") if v][:40]
        with _doc_lock:
            doc = load_doc(doc_id)
        texts = [c["text"] for c in doc["chunks"]]
        self.json({"total": len(texts), "voices": {v: sum(tts.is_cached(t, v, doc["id"]) for t in texts) for v in voices}})

    def jobs(self):
        self.json({"jobs": exporter.running()})

    def prepare_start(self, doc_id):
        with _doc_lock:
            doc = load_doc(doc_id)
        self.json(exporter.start(doc, "prepare"))

    def prepare_pending(self):
        """Texte, deren Vorab-Erzeugen beim letzten Beenden unterbrochen wurde (Karte „Weitermachen?“)."""
        items = []
        for doc_id in exporter.pending_ids():
            try:
                with _doc_lock:
                    doc = load_doc(doc_id)
            except Exception:
                exporter.set_pending(doc_id, False)   # Text gelöscht/kaputt → vergessen
                continue
            if exporter.status(doc_id, "prepare").get("status") == "running":
                continue
            done = sum(tts.is_cached(c["text"], doc["voice"], doc["id"]) for c in doc["chunks"])
            if done >= len(doc["chunks"]):
                exporter.set_pending(doc_id, False)
                continue
            items.append({"doc": doc_id, "title": doc["title"], "done": done, "total": len(doc["chunks"])})
        self.json({"items": items})

    def prepare_resume(self):
        started = []
        for it in exporter.pending_ids():
            try:
                with _doc_lock:
                    doc = load_doc(it)
            except Exception:
                exporter.set_pending(it, False)
                continue
            exporter.start(doc, "prepare")
            started.append(it)
        self.json({"started": started})

    def prepare_cancel(self, doc_id):
        exporter.cancel(doc_id, "prepare")
        self.json({"ok": True})

    # -- Diktat --
    def transcribe(self):
        lang = self.headers.get("X-Lang") or None
        self.json(stt.transcribe(self.raw_body(), lang if lang in LANGS else None))

    # -- Eigene Stimme (Klon) --
    def clone_create(self):
        name = unquote(self.headers.get("X-Name") or "Meine Stimme")
        vid = tts.create_clone(name, self.raw_body())
        first = self.headers.get("X-Lang") if self.headers.get("X-Lang") in LANGS else settings.get("uiLang")
        # Hörprobe sofort vorbereiten (lädt dabei auch das Modell) – mit niedriger Priorität: Vorlesen geht vor
        threading.Thread(target=tts.warm_clone_preview, args=(vid, first), daemon=True).start()
        self.json({"id": vid, "voices": tts.list_voices()}, 201)

    def clone_delete(self, slug):
        tts.delete_clone(slug)
        self.json({"voices": tts.list_voices()})

    # -- Cache --
    def cache_info(self):
        self.json(tts.cache_stats())

    # -- Stimmklon nachinstallieren (Desktop-App) --
    def clone_setup_status(self):
        self.json(clone_setup.status())

    def clone_setup_start(self):
        self.json(clone_setup.start())

    def clone_setup_remove(self):
        tts._clone_worker.stop()
        self.json(clone_setup.uninstall())

    # -- Speicher --
    def storage_report(self):
        self.json(storage.report())

    def storage_delete(self, what, doc_id=None):
        if what == "docs":
            with _doc_lock:
                doc = load_doc(doc_id)
            freed = storage.delete_doc_audio(doc)
        else:
            freed = {"previews": storage.delete_previews, "other": storage.delete_other,
                     "exports": storage.delete_exports, "whisper": storage.delete_whisper}[what]()
        self.json({"freed": freed, **storage.report()})

    # -- Deinstallieren (Desktop-App) --
    def uninstall_info(self):
        self.json(uninstaller.info())

    def uninstall_run(self):
        self.json(uninstaller.launch(bool(self.body().get("keepData")), lambda: ON_QUIT()))

    # -- Fehler melden --
    def bugreport_info(self):
        self.json(bugreport.info())

    def client_error(self):
        """Unerwartete Fehler der Oberfläche ins Log (in pywebview gibt es keine sichtbare Konsole)."""
        p = self.body()
        msg = str(p.get("msg") or "")[:500].replace("\n", " ")
        stack = str(p.get("stack") or "")[:1500]
        print(f"[oberfläche] {msg}" + (f"\n{stack}" if stack else ""), flush=True)
        self.json({"ok": True})

    # -- Updates (Desktop-App) --
    def update_status(self):
        self.json(updater.status())

    def changelog(self):
        self.json({"current": paths.APP_VERSION, "releases": parse_changelog(paths.CHANGELOG)})

    def update_check(self):
        updater.check(force=True)
        self.json(updater.status())

    def update_install(self):
        self.json(updater.install())

    def update_restart(self):
        self.json(updater.restart_now(lambda: ON_QUIT()))

    def focus(self):
        """Zweiter Start der App: das bestehende Fenster nach vorne holen (statt ein zweites zu öffnen)."""
        if not DESKTOP:
            raise KeyError("focus")
        self.json({"ok": True})
        threading.Timer(0.05, ON_FOCUS).start()

    def quit(self):
        self.json({"ok": True})
        threading.Timer(0.3, ON_QUIT).start()   # Antwort erst rausschicken, dann beenden

    def cache_clear(self):
        tts.clear_cache()
        self.json(tts.cache_stats())


D = r"([0-9a-f]{32})"
ROUTES = [
    (r"/|/index\.html", "GET", Handler.index),
    (r"/mini", "GET", Handler.mini),
    (r"/(app\.css|i18n\.js|js/[a-z0-9-]+\.js|klang/[a-z]+\.m4a|fonts/fonts\.css|fonts/[a-z-]+\.woff2)", "GET", Handler.static),
    (r"/api/settings", "GET", Handler.settings_get),
    (r"/api/settings", "PATCH", Handler.settings_patch),
    (r"/api/voices/preview", "GET", Handler.preview),
    (rf"/api/docs/{D}/marks/(\d+)", "GET", Handler.marks),
    (r"/api/voices", "GET", Handler.voices),
    (r"/api/detect", "POST", Handler.detect),
    (r"/api/import", "POST", Handler.do_import),
    (r"/api/quick", "POST", Handler.quick_create),
    (rf"/api/quick/{D}/audio/(\d+)", "GET", Handler.quick_audio),
    (rf"/api/quick/{D}/save", "POST", Handler.quick_save),
    (rf"/api/quick/{D}/marks/(\d+)", "GET", Handler.quick_marks),
    (rf"/api/quick/{D}", "GET", Handler.quick_info),
    (rf"/api/quick/{D}/voice", "POST", Handler.quick_voice),
    (r"/api/import-url", "POST", Handler.import_link),
    (rf"/api/import/ocr/{D}", "GET", Handler.ocr_status),
    (rf"/api/import/ocr/{D}", "DELETE", Handler.ocr_cancel),
    (r"/api/aussprache", "GET", Handler.lex_get),
    (r"/api/aussprache", "PUT", Handler.lex_put),
    (r"/api/aussprache/probe", "POST", Handler.lex_probe),
    (r"/api/aussprache/betroffen", "POST", Handler.lex_affected),
    (rf"/api/docs/{D}/original", "GET", Handler.get_original),
    (r"/api/hoerzeit", "POST", Handler.stats_add),
    (r"/api/hoerzeit/woche", "GET", Handler.stats_week),
    (rf"/api/docs/{D}/bookmarks", "POST", Handler.bm_add),
    (rf"/api/docs/{D}/bookmarks/([0-9a-f]{{12}})", "PATCH", Handler.bm_patch),
    (rf"/api/docs/{D}/bookmarks/([0-9a-f]{{12}})", "DELETE", Handler.bm_delete),
    (r"/api/cache", "GET", Handler.cache_info),
    (r"/api/cache", "DELETE", Handler.cache_clear),
    (r"/api/quit", "POST", Handler.quit),
    (r"/api/focus", "POST", Handler.focus),
    (r"/api/docs", "GET", Handler.list_docs),
    (r"/api/docs", "POST", Handler.create_doc),
    (rf"/api/docs/{D}", "GET", Handler.get_doc),
    (rf"/api/docs/{D}", "PATCH", Handler.patch_doc),
    (rf"/api/docs/{D}", "DELETE", Handler.delete_doc),
    (rf"/api/docs/{D}/audio/(\d+)", "GET", Handler.audio),
    (rf"/api/docs/{D}/text", "GET", Handler.get_text),
    (rf"/api/docs/{D}/text", "PUT", Handler.put_text),
    (rf"/api/docs/{D}/export/info", "GET", Handler.export_info),
    (rf"/api/docs/{D}/export", "GET", Handler.export_status),
    (rf"/api/docs/{D}/export", "POST", Handler.export_start),
    (rf"/api/docs/{D}/export", "DELETE", Handler.export_cancel),
    (rf"/api/docs/{D}/export/file", "GET", Handler.export_file),
    (r"/api/jobs", "GET", Handler.jobs),
    (rf"/api/docs/{D}/prepare", "GET", Handler.prepare_status),
    (rf"/api/docs/{D}/prepared", "GET", Handler.prepared_by_voice),
    (rf"/api/docs/{D}/prepare", "POST", Handler.prepare_start),
    (rf"/api/docs/{D}/prepare", "DELETE", Handler.prepare_cancel),
    (r"/api/prepare/pending", "GET", Handler.prepare_pending),
    (r"/api/prepare/resume", "POST", Handler.prepare_resume),
    (r"/api/transcribe", "POST", Handler.transcribe),
    (r"/api/clones", "POST", Handler.clone_create),
    (r"/api/clones/([a-z0-9-]+)", "DELETE", Handler.clone_delete),
    (r"/api/clone-setup", "GET", Handler.clone_setup_status),
    (r"/api/clone-setup", "POST", Handler.clone_setup_start),
    (r"/api/clone-setup", "DELETE", Handler.clone_setup_remove),
    (r"/api/bugreport", "GET", Handler.bugreport_info),
    (r"/api/client-error", "POST", Handler.client_error),
    (r"/api/uninstall", "GET", Handler.uninstall_info),
    (r"/api/uninstall", "POST", Handler.uninstall_run),
    (r"/api/storage", "GET", Handler.storage_report),
    (rf"/api/storage/(docs)/{D}", "DELETE", Handler.storage_delete),
    (r"/api/storage/(previews|other|exports|whisper)", "DELETE", Handler.storage_delete),
    (r"/api/update", "GET", Handler.update_status),
    (r"/api/changelog", "GET", Handler.changelog),
    (r"/api/update/check", "POST", Handler.update_check),
    (r"/api/update/install", "POST", Handler.update_install),
    (r"/api/update/restart", "POST", Handler.update_restart),
]


SERVER: ThreadingHTTPServer | None = None
DESKTOP = False                    # True, wenn desktop.py das Fenster stellt


def _shutdown_server():
    if SERVER:
        SERVER.shutdown()


ON_QUIT = _shutdown_server         # desktop.py ersetzt das durch „Fenster schließen“
ON_FOCUS = lambda: None            # desktop.py: Fenster nach vorne holen


def _same(a: str, b: str) -> bool:
    """Vergleich in konstanter Zeit (Bytes: compare_digest lehnt Nicht-ASCII-Strings mit TypeError ab)."""
    return hmac.compare_digest(a.encode("utf-8", "surrogateescape"), b.encode("utf-8"))


def cookie_name(port: int) -> str:
    return f"vorleser_{port}"     # Cookies gelten für alle Ports eines Hosts → Port im Namen


def write_token_file() -> None:
    """Schlüssel für einen zweiten App-Start ablegen (nur für den eigenen Benutzer lesbar)."""
    try:
        TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(TOKEN_FILE, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(TOKEN)
    except OSError as e:
        print(f"[server] Schlüsseldatei nicht geschrieben: {e!r}", flush=True)


class _Server(ThreadingHTTPServer):
    # Standard sind 5 wartende Verbindungen – beim Seitenaufbau holt der Browser gut ein Dutzend Dateien gleichzeitig.
    # War der Server kurz beschäftigt, wurden die übrigen abgewiesen und einzelne Skripte fehlten („… is not defined“).
    request_queue_size = 64
    daemon_threads = True
    # Windows: SO_REUSEADDR lässt einen ZWEITEN Vorleser denselben Port belegen (macOS nicht) → die Prüfung „läuft schon?“
    # griff nie, zwei Fenster teilten sich Port + Schlüsseldatei (403er, „Kürzel belegt“; Tester-Rückmeldung 11.11.2026).
    allow_reuse_address = not paths.IS_WIN


def bind(port: int = PORT) -> ThreadingHTTPServer:
    """Server-Socket öffnen (OSError, wenn der Port belegt ist)."""
    global SERVER
    SERVER = _Server((HOST, port), Handler)
    write_token_file()
    return SERVER


def startup() -> None:
    """Vorbereitung, die den Start nicht blockieren muss."""
    for old in tts.CACHE_DIR.glob("*.wav"):  # Cache-Format von Version 1
        old.unlink(missing_ok=True)
    # Jeder Schritt für sich: scheitert einer (z. B. Platte voll), laufen die übrigen – vor allem der Updater,
    # sonst käme nicht einmal der Fix für das Problem an.
    for name, step in (("Edge-Stimmenliste", tts.refresh_edge_voices), ("Offline-Stimme", tts.warm_up),
                       ("Updater", updater.start_background)):
        try:
            step()
        except Exception as e:
            meldungen.loggen(f"start {name}", e)
    for fn in (tts.prune_cache, tts.fix_webm_durations, tts.warm_previews):
        threading.Thread(target=_logged(fn), daemon=True).start()


def _logged(fn):
    """Hintergrund-Thread: Fehler mit Traceback ins Log statt still zu sterben."""
    def run():
        try:
            fn()
        except Exception as e:
            meldungen.loggen(f"hintergrund {fn.__name__}", e)
    return run


def serve() -> None:
    try:
        SERVER.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        tts._clone_worker.stop()                           # Stimmklon-Prozess mit beenden
        print("Vorleser beendet", flush=True)


def main():
    startup()
    try:
        bind()
    except OSError:
        print(f"Port {PORT} ist belegt – läuft der Vorleser schon? → http://{HOST}:{PORT}", flush=True)
        return
    print(f"Vorleser läuft auf http://{HOST}:{PORT}  (Strg+C zum Beenden)", flush=True)
    serve()


if __name__ == "__main__":
    main()
