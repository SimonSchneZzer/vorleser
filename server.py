#!/usr/bin/env python3
"""Vorleser – lokaler Hörbuch-Server.

Stimmen: Microsoft Edge (online, gratis) mit Piper (offline) als Fallback.
Start:   .venv/bin/python server.py   →  http://127.0.0.1:8765
"""
from __future__ import annotations

import json
import os
import re
import shutil
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, unquote, urlparse

import bugreport
import clone_setup
import exporter
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
        return json.loads(self.raw_body() or b"{}")

    def route(self, method: str):
        path = urlparse(self.path).path
        try:
            for pattern, m_, fn in ROUTES:
                if m_ == method and (m := re.fullmatch(pattern, path)):
                    return fn(self, *m.groups())
            self.error(404, "Nicht gefunden")
        except KeyError as e:
            self.error(404, f"Nicht gefunden: {e}")
        except (ValueError, ImportFailed) as e:
            self.error(400, str(e))
        except (BrokenPipeError, ConnectionResetError):
            pass
        except Exception as e:
            print(f"[server] Fehler bei {method} {path}: {e!r}", flush=True)
            try:
                self.error(500, str(e))
            except Exception:
                pass

    def do_GET(self): self.route("GET")
    def do_POST(self): self.route("POST")
    def do_PATCH(self): self.route("PATCH")
    def do_DELETE(self): self.route("DELETE")
    def do_PUT(self): self.route("PUT")

    # -- Seite & Stammdaten --
    def index(self):
        self.send(200, (STATIC_DIR / "index.html").read_bytes(), "text/html; charset=utf-8", {"Cache-Control": "no-cache"})

    def static(self, name):
        ctype = {"css": "text/css", "js": "text/javascript"}[name.rsplit(".", 1)[1]] + "; charset=utf-8"
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
        res = import_file(name, self.raw_body())
        res["lang"] = detect_language(res["text"])
        self.json(res)

    # -- Dokumente --
    def list_docs(self):
        def summary(doc):                          # + wie viele Abschnitte schon fertig erzeugt sind (heller Balken)
            return {**doc_summary(doc), "prepared": sum(tts.is_cached(c["text"], doc["voice"]) for c in doc["chunks"])}
        with _doc_lock:
            docs = [summary(upgrade_doc(json.loads(p.read_text("utf-8")))) for p in DOCS_DIR.glob("*.json")]
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
            raise ValueError(f"Keine Stimme für {LANGS[lang]} verfügbar – siehe README.md")
        chunks, chapters = chunk_text(text, lang)
        if not chunks:
            raise ValueError("Kein vorlesbarer Text gefunden")
        title = (data.get("title") or "").strip() or text.lstrip("# ").split("\n", 1)[0][:60]
        doc = {
            "id": uuid.uuid4().hex, "title": title, "created": time.time(), "lang": lang, "voice": voice,
            "chunks": chunks, "chapters": chapters,
            "progress": {"chunk": 0, "offset": 0.0, "updated": None},
        }
        if data.get("sample"):              # Beispieltext aus dem Rundgang (wird beim erneuten Rundgang wiederverwendet)
            doc["sample"] = True
        with _doc_lock:
            save_doc(doc)
        self.json(doc_summary(doc), 201)

    def get_doc(self, doc_id):
        with _doc_lock:
            doc = load_doc(doc_id)
        self.json(doc)

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

    def audio(self, doc_id, idx):
        with _doc_lock:
            doc = load_doc(doc_id)
        idx = int(idx)
        if idx >= len(doc["chunks"]):
            raise KeyError("Abschnitt")
        data, mime, used = tts.synthesize(doc["chunks"][idx]["text"], doc["voice"], doc["lang"])
        self.send(200, data, mime, {"Cache-Control": "no-store", "X-Voice-Used": used})

    def marks(self, doc_id, idx):
        with _doc_lock:
            doc = load_doc(doc_id)
        idx = int(idx)
        if idx >= len(doc["chunks"]):
            raise KeyError("Abschnitt")
        self.json({"marks": tts.get_marks(doc["chunks"][idx]["text"], doc["voice"], doc["lang"])})

    # -- Export --
    def export_status(self, doc_id):
        load_doc(doc_id)
        self.json(exporter.status(doc_id))

    def export_start(self, doc_id):
        with _doc_lock:
            doc = load_doc(doc_id)
        self.json(exporter.start(doc, self.body().get("format", "m4b")))

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
        cached = [tts.is_cached(c["text"], doc["voice"]) for c in doc["chunks"]]
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
        self.json({"total": len(texts), "voices": {v: sum(tts.is_cached(t, v) for t in texts) for v in voices}})

    def jobs(self):
        self.json({"jobs": exporter.running()})

    def prepare_start(self, doc_id):
        with _doc_lock:
            doc = load_doc(doc_id)
        self.json(exporter.start(doc, "prepare"))

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
    (r"/(app\.(?:css|js)|i18n\.js)", "GET", Handler.static),
    (r"/api/settings", "GET", Handler.settings_get),
    (r"/api/settings", "PATCH", Handler.settings_patch),
    (r"/api/voices/preview", "GET", Handler.preview),
    (rf"/api/docs/{D}/marks/(\d+)", "GET", Handler.marks),
    (r"/api/voices", "GET", Handler.voices),
    (r"/api/detect", "POST", Handler.detect),
    (r"/api/import", "POST", Handler.do_import),
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
    (rf"/api/docs/{D}/export", "GET", Handler.export_status),
    (rf"/api/docs/{D}/export", "POST", Handler.export_start),
    (rf"/api/docs/{D}/export", "DELETE", Handler.export_cancel),
    (rf"/api/docs/{D}/export/file", "GET", Handler.export_file),
    (r"/api/jobs", "GET", Handler.jobs),
    (rf"/api/docs/{D}/prepare", "GET", Handler.prepare_status),
    (rf"/api/docs/{D}/prepared", "GET", Handler.prepared_by_voice),
    (rf"/api/docs/{D}/prepare", "POST", Handler.prepare_start),
    (rf"/api/docs/{D}/prepare", "DELETE", Handler.prepare_cancel),
    (r"/api/transcribe", "POST", Handler.transcribe),
    (r"/api/clones", "POST", Handler.clone_create),
    (r"/api/clones/([a-z0-9-]+)", "DELETE", Handler.clone_delete),
    (r"/api/clone-setup", "GET", Handler.clone_setup_status),
    (r"/api/clone-setup", "POST", Handler.clone_setup_start),
    (r"/api/clone-setup", "DELETE", Handler.clone_setup_remove),
    (r"/api/bugreport", "GET", Handler.bugreport_info),
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


def bind(port: int = PORT) -> ThreadingHTTPServer:
    """Server-Socket öffnen (OSError, wenn der Port belegt ist)."""
    global SERVER
    SERVER = ThreadingHTTPServer((HOST, port), Handler)
    return SERVER


def startup() -> None:
    """Vorbereitung, die den Start nicht blockieren muss."""
    for old in tts.CACHE_DIR.glob("*.wav"):  # Cache-Format von Version 1
        old.unlink(missing_ok=True)
    tts.refresh_edge_voices()
    tts.warm_up()
    threading.Thread(target=tts.prune_cache, daemon=True).start()
    threading.Thread(target=tts.fix_webm_durations, daemon=True).start()
    threading.Thread(target=tts.warm_previews, daemon=True).start()
    updater.start_background()


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
