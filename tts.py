"""Stimmen: Microsoft Edge (online, gratis) mit Piper (lokal) als Fallback.

Voice-IDs: "edge:de-DE-KatjaNeural", "piper:de_DE-thorsten-medium" oder "clone:<profil>".
Audio-Cache: Edge → MP3 (so wie geliefert), Piper/Klon → Opus/WebM (ca. 10× kleiner als WAV).
"""
from __future__ import annotations

import asyncio
import hashlib
import io
import json
import os
import queue
import re
import subprocess
import threading
import time
import wave
from pathlib import Path

import edge_tts
import imageio_ffmpeg
from piper import PiperVoice

import meldungen
import paths
import settings
from meldungen import FFmpegFehler, Meldung
from paths import CACHE_DIR, CLONE_PY, DATA_DIR, NO_WINDOW
from textproc import LANGS

EDGE_LIST_FILE = DATA_DIR / "edge_voices.json"
CLONE_DIR = DATA_DIR / "own_voices"
CLONE_TIMEOUT = 600        # Sekunden pro Abschnitt (Klon ist langsam)
CLONE_START_TIMEOUT = 900  # Sekunden für den Start des Workers (Modell laden)
EDGE_WEG = "Die Online-Stimme ist gerade nicht erreichbar – bist du online?"
CLONE_WEG = "Die eigene Stimme konnte nicht starten – die Details stehen im Log."
CLONE_FEHLER = "Die eigene Stimme konnte diesen Abschnitt nicht erzeugen."
CLONE_SPEICHER = "Zu wenig Arbeitsspeicher für die eigene Stimme."
CLONE_HAENGT = "Die eigene Stimme hat zu lange gebraucht und wird neu gestartet."
KEINE_STIMME = "Keine Stimme verfügbar (offline und keine Piper-Stimme installiert)"
NICHTS_VORLESBAR = "Dieser Abschnitt enthält nichts Vorlesbares"
STIMME_FEHLT = "Die gewählte Stimme ist nicht mehr installiert"
FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()

PREVIEW_TEXT = {"de": "Hallo! So klinge ich, wenn ich dir deine Texte vorlese.",
                "en": "Hello! This is how I sound when I read your texts aloud."}


def warm_previews(include_clones: bool = True) -> None:
    """Hörproben aller Stimmen im Hintergrund erzeugen, damit sie sofort abspielen."""
    from concurrent.futures import ThreadPoolExecutor
    todo = [(v["id"], v["lang"]) for v in _edge_voices() + _piper_voices()
            if not is_cached(PREVIEW_TEXT[v["lang"]], v["id"])]
    def one(job):
        try:
            synthesize(PREVIEW_TEXT[job[1]], job[0], job[1], fallback=False)
        except Exception:
            pass
    if todo:
        print(f"[preview] erzeuge {len(todo)} Hörproben im Hintergrund …", flush=True)
        with ThreadPoolExecutor(2) as pool:
            list(pool.map(one, todo))
    if include_clones:                      # eigene Stimmen: langsam, nur wenn der Klon gerade frei ist
        for v in _clone_voices():
            if is_cached(PREVIEW_TEXT[v["lang"]], v["id"]):
                continue
            while _clone_worker.lock.locked():
                time.sleep(5)
            one((v["id"], v["lang"]))
    print("[preview] Hörproben bereit", flush=True)


def cache_limit() -> int:
    return int(settings.get("cacheMB")) * 1024 * 1024

EDGE_PARALLEL = 4          # gleichzeitige Anfragen an Edge
EDGE_TIMEOUT = 40          # Sekunden pro Abschnitt
EDGE_COOLDOWN = 60         # nach einem Fehler so lange direkt Piper nehmen

PREFERRED = {
    "de": ["edge:de-DE-SeraphinaMultilingualNeural", "edge:de-DE-KatjaNeural", "edge:de-DE-ConradNeural"],
    "en": ["edge:en-US-AvaMultilingualNeural", "edge:en-US-AndrewMultilingualNeural", "edge:en-US-AriaNeural"],
}
MIME = {"mp3": "audio/mpeg", "webm": "audio/webm"}
REGION_NAMES = {"DE": "Deutschland", "AT": "Österreich", "CH": "Schweiz", "US": "USA", "GB": "Großbritannien",
                "AU": "Australien", "CA": "Kanada", "IE": "Irland", "IN": "Indien", "NZ": "Neuseeland",
                "ZA": "Südafrika", "SG": "Singapur", "PH": "Philippinen", "HK": "Hongkong", "KE": "Kenia",
                "NG": "Nigeria", "TZ": "Tansania"}
GENDER = {"Female": "Weiblich", "Male": "Männlich"}



# --------------------------------------------------------------------------- #
# Stimmenlisten
# --------------------------------------------------------------------------- #
def _piper_files() -> dict[str, Path]:
    """Name → .onnx-Datei. Nachinstallierte Stimmen (Benutzerordner) vor mitgelieferten."""
    found: dict[str, Path] = {}
    for d in (paths.USER_VOICES, paths.BUNDLED_VOICES):
        for p in sorted(d.glob("*.onnx")) if d.exists() else []:
            found.setdefault(p.stem, p)
    return found


def _piper_voices() -> list[dict]:
    out = []
    for name, p in sorted(_piper_files().items()):
        cfg_path = p.with_suffix(".onnx.json")
        if not cfg_path.exists():
            continue
        try:
            cfg = json.loads(cfg_path.read_text("utf-8"))
        except ValueError:
            cfg = {}
        lc = cfg.get("language") or {}
        parts = name.split("-")  # de_DE-thorsten-medium
        lang = lc.get("family") or parts[0].split("_")[0]
        region = lc.get("region") or (parts[0].split("_")[1] if "_" in parts[0] else "")
        speaker = (cfg.get("dataset") or (parts[1] if len(parts) > 1 else name)).replace("_", " ").title()
        quality = (cfg.get("audio") or {}).get("quality") or (parts[2] if len(parts) > 2 else "")
        out.append({
            "id": f"piper:{name}", "engine": "piper", "lang": lang, "region": region,
            "label": f"{speaker} ({region}{', ' + quality if quality else ''})", "gender": "",
            "name": speaker, "meta": " · ".join(x for x in (REGION_NAMES.get(region, region), f"Piper {quality}".strip()) if x),
            "key": name,
        })
    return out


_edge_cache: dict = {"voices": [], "loaded": 0.0}
_edge_lock = threading.Lock()
_edge_ready = threading.Event()   # erste Abfrage der Online-Stimmen beendet (erfolgreich oder nicht)


def _edge_label(v: dict) -> str:
    short = v["ShortName"]                      # de-DE-SeraphinaMultilingualNeural
    name = short.split("-", 2)[-1].removesuffix("Neural")
    multi = name.endswith("Multilingual")
    name = name.removesuffix("Multilingual")
    region = v["Locale"].split("-")[-1]
    gender = {"Female": "♀", "Male": "♂"}.get(v.get("Gender"), "")
    return f"{name} ({region}{', mehrsprachig' if multi else ''}) {gender}".strip()


def _edge_name(v: dict) -> str:
    return v["ShortName"].split("-", 2)[-1].removesuffix("Neural").removesuffix("Multilingual")


def _edge_meta(v: dict) -> str:
    region = v["Locale"].split("-")[-1]
    parts = [GENDER.get(v.get("Gender"), ""), REGION_NAMES.get(region, region)]
    if "Multilingual" in v["ShortName"]:
        parts.append("mehrsprachig")
    return " · ".join(p for p in parts if p)


def refresh_edge_voices(timeout: float = 10) -> None:
    """Edge-Stimmenliste laden (online) und lokal zwischenspeichern."""
    async def fetch():
        return await asyncio.wait_for(edge_tts.list_voices(), timeout)
    try:
        raw = asyncio.run(fetch())
        voices = [
            {"id": f"edge:{v['ShortName']}", "engine": "edge", "lang": v["Locale"].split("-")[0],
             "region": v["Locale"].split("-")[-1], "label": _edge_label(v), "gender": v.get("Gender", ""),
             "name": _edge_name(v), "meta": _edge_meta(v)}
            for v in raw
            if v["Locale"].split("-")[0] in LANGS and v.get("Status", "GA") != "Deprecated"
        ]
        voices.sort(key=lambda v: (v["lang"], v["region"] not in ("DE", "US"), v["region"], v["label"]))
        _write_atomic(EDGE_LIST_FILE, json.dumps(voices, ensure_ascii=False).encode())
        with _edge_lock:
            _edge_cache.update(voices=voices, loaded=time.time())
        print(f"[edge] {len(voices)} Online-Stimmen geladen", flush=True)
    except Exception as e:  # offline o. Ä. → zwischengespeicherte Liste nutzen
        print(f"[edge] Stimmenliste nicht abrufbar ({type(e).__name__}) – nutze gespeicherte Liste", flush=True)
    finally:
        _edge_ready.set()


def _edge_voices() -> list[dict]:
    # Allererster Start: noch keine gespeicherte Liste → kurz auf die Online-Abfrage warten,
    # sonst wird die Offline-Stimme (Piper) zur Standardstimme.
    if not _edge_cache["voices"] and not EDGE_LIST_FILE.exists():
        _edge_ready.wait(8)
    with _edge_lock:
        if not _edge_cache["voices"] and EDGE_LIST_FILE.exists():
            try:
                _edge_cache["voices"] = json.loads(EDGE_LIST_FILE.read_text("utf-8"))
                _edge_cache["loaded"] = EDGE_LIST_FILE.stat().st_mtime
            except ValueError:
                pass
        for v in _edge_cache["voices"]:
            if "name" not in v:
                raw = {"ShortName": v["id"].split(":", 1)[1], "Locale": f"{v['lang']}-{v['region']}", "Gender": v.get("gender")}
                v["name"], v["meta"] = _edge_name(raw), _edge_meta(raw)
        stale = time.time() - _edge_cache["loaded"] > 7 * 86400
        voices = list(_edge_cache["voices"])
    if stale:  # einmal pro Woche im Hintergrund aktualisieren
        with _edge_lock:
            _edge_cache["loaded"] = time.time()
        threading.Thread(target=refresh_edge_voices, daemon=True).start()
    return voices


def clone_available() -> bool:
    import clone_setup
    return clone_setup.installed()


def _clone_voices() -> list[dict]:
    if not clone_available() or not CLONE_DIR.exists():
        return []
    out = []
    for d in sorted(CLONE_DIR.iterdir()):
        if (d / "sample.wav").exists():
            try:
                meta = json.loads((d / "meta.json").read_text("utf-8"))
            except (OSError, ValueError):
                meta = {}
            for lang in LANGS:  # Chatterbox ist mehrsprachig → Profil für jede Sprache anbieten
                out.append({"id": f"clone:{d.name}", "engine": "clone", "lang": lang, "region": "",
                            "label": f"{meta.get('name') or d.name} (eigene Stimme)", "gender": "",
                            "name": meta.get("name") or d.name,
                            "meta": "Lädt länger · am besten vorab erzeugen",
                            "warming": f"clone:{d.name}" in _warming})
    return out


def list_voices() -> list[dict]:
    return _edge_voices() + _piper_voices() + _clone_voices()


def create_clone(name: str, audio: bytes) -> str:
    """Sprachprobe säubern und als Profil speichern. Liefert die Voice-ID."""
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:40] or "stimme"
    base, n = slug, 2
    while (CLONE_DIR / slug).exists():
        slug, n = f"{base}-{n}", n + 1
    wav = ffmpeg(["-i", "pipe:0", "-af",
                  "silenceremove=start_periods=1:start_threshold=-45dB,areverse,"
                  "silenceremove=start_periods=1:start_threshold=-45dB,areverse,loudnorm=I=-18:TP=-2",
                  "-ac", "1", "-ar", "24000", "-t", "40", "-f", "wav", "pipe:1"], audio)
    secs = (len(wav) - 44) / 48000
    if secs < 5:
        raise ValueError(f"Sprachprobe zu kurz ({secs:.0f} s) – bitte mindestens 10 Sekunden sprechen")
    d = CLONE_DIR / slug
    d.mkdir(parents=True)
    (d / "sample.wav").write_bytes(wav)
    (d / "meta.json").write_text(json.dumps({"name": name.strip() or slug, "seconds": round(secs, 1)},
                                            ensure_ascii=False), "utf-8")
    return f"clone:{slug}"


def delete_clone(slug: str) -> None:
    import shutil
    if re.fullmatch(r"[a-z0-9-]+", slug):
        shutil.rmtree(CLONE_DIR / slug, ignore_errors=True)


def voice_by_id(vid: str) -> dict | None:
    return next((v for v in list_voices() if v["id"] == vid), None)


def voices_for(lang: str) -> list[dict]:
    return [v for v in list_voices() if v["lang"] == lang]


def default_voice(lang: str) -> str | None:
    ids = [v["id"] for v in voices_for(lang)]
    chosen = settings.get("defaultVoices").get(lang)
    if chosen in ids:
        return chosen
    for pref in PREFERRED.get(lang, []):
        if pref in ids:
            return pref
    return ids[0] if ids else None


def fallback_voice(lang: str) -> str | None:
    piper = [v["id"] for v in _piper_voices()]
    same = [v["id"] for v in _piper_voices() if v["lang"] == lang]
    return (same or piper or [None])[0]


def delete_piper(key: str) -> None:
    """Piper-Stimme entfernen – die letzte einer Sprache bleibt als Offline-Ersatz."""
    v = next((v for v in _piper_voices() if v["key"] == key), None)
    if not v:
        raise KeyError(key)
    if len([x for x in _piper_voices() if x["lang"] == v["lang"]]) <= 1:
        raise ValueError("Die letzte Offline-Stimme einer Sprache bleibt als Ersatz installiert")
    p = _piper_files()[key]
    if p.parent != paths.USER_VOICES:
        raise ValueError("Mitgelieferte Offline-Stimmen lassen sich nicht löschen")
    for suffix in (".onnx", ".onnx.json"):
        (paths.USER_VOICES / f"{key}{suffix}").unlink(missing_ok=True)
    _piper.pop(key, None)


def normalize_voice_id(vid: str) -> str:
    """Alte IDs ohne Präfix (nur Piper) → "piper:…"."""
    return vid if ":" in vid else f"piper:{vid}"


# --------------------------------------------------------------------------- #
# Synthese
# --------------------------------------------------------------------------- #
_piper: dict[str, PiperVoice] = {}
_piper_load_lock = threading.Lock()
_piper_lock = threading.Lock()          # Piper: ein Abschnitt nach dem anderen
_edge_sem = threading.Semaphore(EDGE_PARALLEL)
_edge_down_until = 0.0


def _espeak_dir() -> Path:
    """espeak-ng speichert seinen Datenpfad in 160 Zeichen; ist er länger, sucht es einen Pfad vom
    Build-Server und beendet den ganzen Prozess. Dann die Daten einmal an einen kurzen Ort kopieren."""
    import shutil
    import tempfile
    from piper.phonemize_espeak import ESPEAK_DATA_DIR
    src = Path(ESPEAK_DATA_DIR)
    if len(str(src)) < 150:
        return src
    for base in (paths.USER_DIR, Path(tempfile.gettempdir())):
        dest = base / "vorleser-espeak-ng-data"
        if len(str(dest)) < 150:
            if not (dest / "phontab").exists():
                shutil.rmtree(dest, ignore_errors=True)
                shutil.copytree(src, dest)
            return dest
    return src


def _get_piper(name: str) -> PiperVoice:
    with _piper_load_lock:
        if name not in _piper:
            print(f"[piper] lade Stimme {name} …", flush=True)
            _piper[name] = PiperVoice.load(str(_piper_files()[name]), espeak_data_dir=_espeak_dir())
        return _piper[name]


def warm_up() -> None:
    for v in _piper_voices()[:1]:
        _get_piper(v["id"].split(":", 1)[1])


def ffmpeg(args: list[str], data: bytes | None = None) -> bytes:
    """ffmpeg aufrufen. Eingabe-Bytes gehen über eine Temp-Datei statt pipe:0,
    weil MP4/M4A (z. B. Safari-Aufnahmen) nicht aus einer Pipe lesbar ist."""
    import tempfile
    tmp = None
    if data is not None and "pipe:0" in args:
        tmp = tempfile.NamedTemporaryFile(prefix="vorleser-", delete=False)
        tmp.write(data)
        tmp.close()
        args = [tmp.name if a == "pipe:0" else a for a in args]
        data = None
    try:
        r = subprocess.run([FFMPEG, "-hide_banner", "-loglevel", "error", *args],
                           input=data, capture_output=True, check=False, **NO_WINDOW)
    finally:
        if tmp:
            os.unlink(tmp.name)
    if r.returncode != 0:
        raise FFmpegFehler(f"ffmpeg: {r.stderr.decode(errors='replace')[-300:]}")
    return r.stdout


def to_opus(wav: bytes) -> bytes:
    """WAV → Opus/WebM (32 kbit/s mono reicht für Sprache locker).
    In eine echte Datei statt pipe:1: nur dann trägt ffmpeg die Dauer ein. Ohne Dauer raten
    Browser/Webview die Länge – die Wortmarkierung läuft dann dem Audio davon."""
    import tempfile
    fd, out = tempfile.mkstemp(prefix="vorleser-", suffix=".webm")
    os.close(fd)
    try:
        ffmpeg(["-y", "-i", "pipe:0", "-c:a", "libopus", "-b:a", "32k", "-application", "voip",
                "-f", "webm", out], wav)
        return Path(out).read_bytes()
    finally:
        os.unlink(out)


def fix_webm_durations() -> None:
    """Einmalig: ältere WebM-Dateien im Cache ohne Neukodieren umverpacken, damit sie eine Dauer haben."""
    import tempfile
    flag = DATA_DIR / "cache-webm-duration-ok"
    if flag.exists():
        return
    files = list(CACHE_DIR.glob("*.webm"))
    for p in files:
        fd, tmp = tempfile.mkstemp(prefix="vorleser-", suffix=".webm", dir=CACHE_DIR)
        os.close(fd)
        try:
            ffmpeg(["-y", "-i", str(p), "-c", "copy", "-f", "webm", tmp])
            os.replace(tmp, p)
        except Exception:
            Path(tmp).unlink(missing_ok=True)
    flag.write_text("1", "utf-8")
    if files:
        print(f"[cache] {len(files)} WebM-Dateien mit Dauer versehen", flush=True)


def _synth_piper(text: str, name: str) -> bytes:
    voice = _get_piper(name)
    buf = io.BytesIO()
    with _piper_lock:
        with wave.open(buf, "wb") as wav:
            voice.synthesize_wav(text, wav)
    return to_opus(buf.getvalue())


def _synth_edge(text: str, short: str) -> tuple[bytes, list]:
    """Audio + Wortmarken [[start_s, dauer_s, wort], …] (Edge liefert sie mit)."""
    async def run():
        out, marks = bytearray(), []
        async for c in edge_tts.Communicate(text, short, boundary="WordBoundary").stream():
            if c["type"] == "audio":
                out.extend(c["data"])
            elif c["type"] == "WordBoundary":
                marks.append([round(c["offset"] / 1e7, 3), round(c["duration"] / 1e7, 3), c["text"]])
        return bytes(out), marks
    with _edge_sem:
        data, marks = asyncio.run(asyncio.wait_for(run(), EDGE_TIMEOUT))
    if not data:
        raise RuntimeError("Edge lieferte kein Audio")
    return data, marks


_worker_log_file = None


def _worker_log():
    """Fehlerausgabe des Klon-Prozesses: in der App ins Log (dort gibt es keine Konsole). Ein Handle für alle Starts."""
    global _worker_log_file
    if paths.FROZEN and _worker_log_file is None:
        _worker_log_file = open(paths.LOG_FILE, "a", encoding="utf-8")
    return _worker_log_file


class _CloneWorker:
    """Hält den Chatterbox-Prozess (eigenes venv) am Leben; Aufträge nacheinander."""
    def __init__(self):
        self.proc = None
        self.lock = threading.Lock()
        self.urgent = 0                        # wartende normale Aufträge (Vorlesen) – Hintergrund lässt ihnen den Vortritt
        self._ulock = threading.Lock()

    def _start(self):
        print("[clone] starte Worker (Modell laden dauert beim ersten Mal) …", flush=True)
        self.proc = subprocess.Popen([str(CLONE_PY), str(paths.CLONE_WORKER)], stdin=subprocess.PIPE,
                                     stdout=subprocess.PIPE, stderr=_worker_log(), text=True, bufsize=1,
                                     encoding="utf-8", env=paths.clone_env(), **NO_WINDOW)
        q, proc = queue.Queue(), self.proc
        def pump():                            # Zeilen in eine Queue → Lesen mit Zeitlimit (auch unter Windows)
            for line in proc.stdout:
                q.put(line)
            q.put("")
        threading.Thread(target=pump, daemon=True).start()
        self._q = q
        try:
            hello = json.loads(self._readline(CLONE_START_TIMEOUT) or "{}")
        except ValueError:
            hello = {}
        if not hello.get("ready"):
            self.stop()
            raise Meldung(CLONE_WEG)

    def _readline(self, timeout: float) -> str:
        """Nächste Antwort des Workers; hängt er (torch/MPS), wird er beendet statt alles zu blockieren."""
        try:
            return self._q.get(timeout=timeout)
        except queue.Empty:
            print(f"[clone] Worker antwortet seit {timeout:.0f} s nicht – wird beendet", flush=True)
            self.stop()
            raise Meldung(CLONE_HAENGT) from None

    def stop(self):
        if self.proc and self.proc.poll() is None:
            self.proc.kill()
        self.proc = None

    def synth(self, text: str, lang: str, ref: Path, low: bool = False) -> bytes:
        import tempfile
        if low:                                # Hintergrund: erst loslegen, wenn kein Vorlese-Auftrag wartet
            while self.urgent or self.lock.locked():
                time.sleep(0.2)
        else:
            with self._ulock:
                self.urgent += 1
        try:
            self.lock.acquire()
        finally:
            if not low:
                with self._ulock:
                    self.urgent -= 1
        try:
            return self._synth_locked(text, lang, ref, tempfile)
        finally:
            self.lock.release()

    def _synth_locked(self, text, lang, ref, tempfile) -> bytes:
        if self.proc is None or self.proc.poll() is not None:
            self._start()
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            out = Path(tmp.name)
        try:
            self.proc.stdin.write(json.dumps({"text": text, "lang": lang, "ref": str(ref), "out": str(out)}) + "\n")
            self.proc.stdin.flush()
            res = json.loads(self._readline(CLONE_TIMEOUT) or '{"ok": false, "error": "Worker beendet"}')
            if not res.get("ok"):
                err = str(res.get("error", ""))
                print(f"[clone] Worker-Fehler: {err}", flush=True)
                if "memory" in err.lower() and self.proc:
                    self.stop()                 # nächster Auftrag startet einen frischen Worker
                    raise Meldung(CLONE_SPEICHER)
                raise Meldung(CLONE_FEHLER)
            return out.read_bytes()
        finally:
            out.unlink(missing_ok=True)


_clone_worker = _CloneWorker()


def _synth_clone(text: str, slug: str, lang: str, low: bool = False) -> bytes:
    ref = CLONE_DIR / slug / "sample.wav"
    if not ref.exists():
        raise Meldung("Die eigene Stimme wurde nicht gefunden")
    wav = _clone_worker.synth(text, lang, ref, low=low)
    if _clone_too_short(text, wav):
        # Chatterbox bricht manchmal mitten im Satz ab (z. B. vor Aufzählungen) → Text fehlt im Audio, die Wort-
        # markierung rast drüber. Erst einmal neu würfeln (das Modell sampelt zufällig), sonst Satz für Satz.
        print(f"[clone] Audio zu kurz ({_wav_secs(wav):.1f} s für {len(text.split())} Wörter) – neuer Versuch", flush=True)
        again = _clone_worker.synth(text, lang, ref, low=low)
        if not _clone_too_short(text, again):
            wav = again
        else:
            import textproc
            parts = [p for p in textproc.split_sentences(text, lang) if p.strip()]
            if len(parts) > 1:
                print(f"[clone] immer noch zu kurz – erzeuge {len(parts)} Sätze einzeln", flush=True)
                wav = _concat_wavs([_clone_worker.synth(p, lang, ref, low=low) for p in parts])
            elif _wav_secs(again) > _wav_secs(wav):
                wav = again
    return to_opus(wav)


CLONE_WORDS_PER_SEC = 2.3      # typisches Sprechtempo der eigenen Stimme (gemessen: Median 2,28)


def _wav_teile(wav: bytes) -> tuple[bytes, bytes]:
    """(fmt-Block, Audiodaten) einer WAV-Datei. Selbst gelesen statt über `wave`: der Klon-Worker schrieb bis 3.0.1
    Gleitkomma-WAV (Format 3), das `wave` nicht kennt – ein noch laufender alter Worker darf nichts kaputt machen."""
    if wav[:4] != b"RIFF" or wav[8:12] != b"WAVE":
        raise wave.Error("not a WAV file")
    pos, fmt = 12, None
    while pos + 8 <= len(wav):
        cid, size = wav[pos:pos + 4], int.from_bytes(wav[pos + 4:pos + 8], "little")
        if cid == b"fmt ":
            fmt = wav[pos + 8:pos + 8 + size]
        elif cid == b"data" and fmt is not None and len(fmt) >= 16:
            return fmt, wav[pos + 8:pos + 8 + size]      # Größe 0xFFFFFFFF (gestreamt) → einfach bis zum Ende
        pos += 8 + size + (size & 1)
    raise wave.Error("WAV without fmt/data chunk")


def _wav_secs(wav: bytes) -> float | None:
    """Dauer in Sekunden; None, wenn sie sich nicht bestimmen lässt (dann nie als „zu kurz“ werten)."""
    try:
        fmt, data = _wav_teile(wav)
    except wave.Error:
        return None
    rate, block = int.from_bytes(fmt[4:8], "little"), int.from_bytes(fmt[12:14], "little")
    return len(data) // block / rate if rate and block else None


def _clone_too_short(text: str, wav: bytes) -> bool:
    """Deutlich kürzer als für den Text plausibel? (Unter ~45 % der erwarteten Dauer; kurze Texte schwanken zu stark.)
    Unbekannte Dauer zählt nicht als zu kurz: sonst wird jeder Abschnitt dreifach erzeugt (3.0.1: Lüfter, Akku)."""
    words, secs = len(text.split()), _wav_secs(wav)
    return words >= 6 and secs is not None and secs < 0.45 * words / CLONE_WORDS_PER_SEC


def _concat_wavs(wavs: list[bytes]) -> bytes:
    """WAVs gleichen Formats (PCM oder Gleitkomma) aneinanderhängen, mit kurzer Pause zwischen den Sätzen."""
    teile = [_wav_teile(w) for w in wavs]
    fmt = teile[0][0]
    if any(f != fmt for f, _ in teile):
        raise wave.Error("WAV formats differ")
    rate, block = int.from_bytes(fmt[4:8], "little"), int.from_bytes(fmt[12:14], "little")
    data = (b"\0" * (int(rate * 0.25) * block)).join(d for _, d in teile)   # Stille ist in beiden Formaten 0
    fmt_chunk = b"fmt " + len(fmt).to_bytes(4, "little") + fmt + b"\0" * (len(fmt) & 1)
    body = b"WAVE" + fmt_chunk + b"data" + len(data).to_bytes(4, "little") + data + b"\0" * (len(data) & 1)
    return b"RIFF" + len(body).to_bytes(4, "little") + body


# --------------------------------------------------------------------------- #
# Aussprache-Wörterbuch (Version 3.0, Etappe 2). Ersetzt Wörter VOR dem Vorlesen; die Ersetzung steckt im
# Cache-Schlüssel → ändert sich ein Eintrag, werden betroffene Abschnitte automatisch neu erzeugt („neu kalibriert“).
# --------------------------------------------------------------------------- #
LEX_FILE = DATA_DIR / "aussprache.json"
# Vorbelegung je Sprache – ein Eintrag gilt nur für Texte in seiner Sprache (ohne „lang“: für alle)
LEX_DEFAULT = [{"wort": w, "sprich": s, "lang": "de"} for w, s in [
    ("z. B.", "zum Beispiel"), ("d. h.", "das heißt"), ("u. a.", "unter anderem"), ("bzw.", "beziehungsweise"),
    ("usw.", "und so weiter"), ("ggf.", "gegebenenfalls"), ("inkl.", "inklusive"), ("vgl.", "vergleiche"),
    ("evtl.", "eventuell"), ("bspw.", "beispielsweise"), ("zzgl.", "zuzüglich"), ("u. U.", "unter Umständen"),
    ("o. Ä.", "oder Ähnliches")]] + [{"wort": w, "sprich": s, "lang": "en"} for w, s in [
    ("e.g.", "for example"), ("i.e.", "that is"), ("etc.", "et cetera"), ("vs.", "versus"), ("approx.", "approximately"),
    ("incl.", "including"), ("esp.", "especially"), ("a.k.a.", "also known as"), ("cf.", "compare"),
    ("Vorleser", "Fore-lay-zer")]]                  # sonst „Worlieser“ (Tester-Rückmeldung)
_lex = {"mtime": None, "entries": [], "rx": []}


def lexikon() -> list[dict]:
    """Einträge {wort, sprich, doc?} – doc = nur in diesem Text. Fehlt die Datei: Vorbelegung."""
    _lex_laden()
    return [dict(e) for e in _lex["entries"]]


def _lex_laden() -> None:
    """Wörterbuch neu lesen, wenn sich die Datei geändert hat (sonst nichts tun – wird pro Abschnitt gerufen)."""
    try:
        mt = LEX_FILE.stat().st_mtime
    except OSError:
        mt = 0
    if _lex["mtime"] != mt:
        entries = LEX_DEFAULT
        if mt:
            try:
                data = json.loads(LEX_FILE.read_text("utf-8"))
                entries = [e for e in data if isinstance(e, dict) and str(e.get("wort", "")).strip() and str(e.get("sprich", "")).strip()]
            except (OSError, ValueError):
                entries = LEX_DEFAULT
        _lex.update(mtime=mt, entries=entries,
                    rx=[(re.compile(r"(?<!\w)" + re.escape(e["wort"].strip()) + r"(?!\w)"), e["sprich"].strip(), e.get("doc"), e.get("lang"))
                        for e in entries])
        _gesprochen.clear()                  # Aufbereitung hängt am Wörterbuch → gemerkte Ergebnisse verwerfen


def lexikon_speichern(entries: list[dict]) -> list[dict]:
    clean = []
    for e in entries[:2000]:
        w, sp = str(e.get("wort", "")).strip()[:120], str(e.get("sprich", "")).strip()[:200]
        if w and sp:
            clean.append({"wort": w, "sprich": sp, **({"doc": e["doc"]} if re.fullmatch(r"[0-9a-f]{32}", str(e.get("doc") or "")) else {}),
                          **({"lang": e["lang"]} if e.get("lang") in LANGS else {})})
    tmp = LEX_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(clean, ensure_ascii=False, indent=1), "utf-8")
    tmp.replace(LEX_FILE)
    _lex["mtime"] = None
    return lexikon()


# Nur für die Stimme (Anzeige bleibt): Zeichen, die sonst vorgelesen werden oder stören (Tester-Rückmeldung 9.11.2026)
_EMOJI = re.compile("[\U0001F000-\U0001FAFF\u2600-\u27BF\u2B00-\u2BFF\uFE0F\u200D\u20E3]")
_DEKOR = re.compile(r"[*•◦▪▫■□●○◆◇►▶➢➤✓✔✗✘‣⁃→←↑↓⇒⇐⇔↔⟶⟵|\uE000-\uF8FF]")
_LINIE = re.compile(r"[-=_~*#]{3,}")
_URL = re.compile(r"\b(?:https?://)?(?:www\.)?((?:[\w-]+\.)+[a-z]{2,})(?:[/?#][^\s]*?)?(?=[.,;:!?)\]]*(?:\s|$))", re.I)
_ABK = re.compile(r"(?<![\w.])([a-zäöü])\.(?=[A-Za-zÄÖÜäöü]\.)")      # z.B., d.h., u.U., o.Ä. – nicht U.S.A.


def _fuer_stimme(text: str, lang: str | None = None) -> str:
    """Links → Adresse ohne Pfad, Emojis/Aufzählungszeichen/Pfeile/Trennlinien weg, „z.B.“ → „z. B.“ (fürs Wörterbuch)."""
    text = _URL.sub(lambda m: m.group(1) if ("://" in m.group(0) or m.group(0).lower().startswith("www.")) else m.group(0), text)
    text = _EMOJI.sub("", text)
    text = _DEKOR.sub(" ", text)
    text = _LINIE.sub(" ", text)
    if lang != "en":                                   # „z.B.“ → „z. B.“ nur deutsch („e.g.“ bleibt)
        text = _ABK.sub(r"\1. ", text)
    return re.sub(r"[ \t]{2,}", " ", text).strip()


_voice_lang_cache: dict[str, str | None] = {}


def _voice_lang(voice_id: str) -> str | None:
    """Sprache einer Stimme – steckt bei Edge/Piper im Namen (de-DE / de_DE), sonst aus der Stimmenliste (eigene Stimme).
    Bewusst NUR aus der Stimme: Schlüssel im Zwischenspeicher und gesprochener Text müssen überall gleich herauskommen."""
    m = re.match(r"(?:edge|piper):([a-z]{2})[-_]", voice_id or "")
    if m:
        return m.group(1)
    if voice_id not in _voice_lang_cache:
        v = voice_by_id(voice_id)
        _voice_lang_cache[voice_id] = v["lang"] if v else None
    return _voice_lang_cache[voice_id]


_gesprochen: dict[tuple, str] = {}     # (Text, Text-ID, Sprache) → aufbereiteter Text; geleert, wenn sich das Wörterbuch ändert


def spoken(text: str, doc_id: str | None = None, lang: str | None = None) -> str:
    """Text, wie er gesprochen wird (aufbereitet, Wörterbuch der passenden Sprache angewendet).
    Gemerkt: Bibliothek, Vorab erzeugen und Speicher-Übersicht fragen denselben Abschnitt sehr oft ab (Messung
    11.11.2026: Speicher-Übersicht eines Buchs mit 2000 Abschnitten 5 s, fast nur diese Funktion)."""
    _lex_laden()
    key = (text, doc_id, lang)
    hit = _gesprochen.get(key)
    if hit is not None:
        return hit
    out = _fuer_stimme(text, lang)
    for rx, sp, doc, elang in _lex["rx"]:
        if doc and doc != doc_id:
            continue
        if elang and lang and elang != lang:
            continue
        out = rx.sub(sp, out)
    if len(_gesprochen) > 50_000:            # Obergrenze für den Arbeitsspeicher (ein paar große Bücher)
        _gesprochen.clear()
    _gesprochen[key] = out
    return out


def cache_name(voice_id: str, said: str) -> str:
    """Dateiname im Audio-Cache für schon aufbereiteten Text (`spoken`) mit dieser Stimme."""
    key = hashlib.sha1(f"{voice_id}\0{said}".encode()).hexdigest()
    return f"{key}.{'mp3' if voice_id.startswith('edge:') else 'webm'}"


def cache_path(text: str, voice_id: str, doc_id: str | None = None) -> Path:
    return CACHE_DIR / cache_name(voice_id, spoken(text, doc_id, _voice_lang(voice_id)))


_inflight: dict[Path, threading.Event] = {}     # Klon-Abschnitte, die gerade erzeugt werden (nicht doppelt rechnen)
_inflight_lock = threading.Lock()


_warming: set[str] = set()      # neue eigene Stimmen, deren erste Hörprobe (inkl. Modell-Laden) noch läuft


def warm_clone_preview(voice_id: str, first_lang: str = "de") -> None:
    """Hörprobe einer neuen eigenen Stimme sofort im Hintergrund erzeugen – erst in der Oberflächensprache.
    Niedrige Priorität: Wird vorgelesen, wartet sie (ein laufender Abschnitt wird noch fertig).
    Bis die erste fertig ist, meldet `list_voices` die Stimme als `warming` (Oberfläche zeigt „wird vorbereitet“)."""
    langs = [first_lang] + [l for l in LANGS if l != first_lang]
    _warming.add(voice_id)
    try:
        for lang in langs:
            try:
                synthesize(PREVIEW_TEXT[lang], voice_id, lang, fallback=False, low=True)
            except Exception as e:
                print(f"[clone] Hörprobe ({lang}) nicht erzeugt: {e}", flush=True)
                return
            _warming.discard(voice_id)
    finally:
        _warming.discard(voice_id)


def synthesize(text: str, voice_id: str, lang: str, fallback: bool = True, low: bool = False,
               doc_id: str | None = None, sperre: bool = True) -> tuple[bytes, str, str]:
    """Liefert (audio, mime, tatsächlich genutzte Stimme).
    fallback=False: bei Fehler Exception statt Ersatzstimme (z. B. für Hörproben). doc_id: für Wörterbuch-Einträge
    „nur in diesem Text“. sperre=False: Edge auch während der 60-s-Sperre versuchen (Vorlesen ohne Ersatzstimme, 3.0.2)."""
    voice_id = normalize_voice_id(voice_id)
    path = cache_path(text, voice_id, doc_id)
    say = spoken(text, doc_id, _voice_lang(voice_id))
    if path.exists():
        os.utime(path)  # für "zuletzt benutzt" beim Aufräumen
        return path.read_bytes(), MIME[path.suffix[1:]], voice_id

    engine, name = voice_id.split(":", 1)
    t0 = time.time()
    if engine == "edge":
        if sperre and time.time() < _edge_down_until:
            if not fallback:
                raise Meldung(EDGE_WEG)
            return _fallback(text, lang, voice_id, doc_id)
        try:
            data, marks = _synth_edge(say, name)
        except Exception as e:
            return _edge_fehler(e, name, fallback, text, lang, voice_id, doc_id)
        # außerhalb des Edge-Blocks: volle Platte ist kein Edge-Ausfall (sonst 60 s Sperre + Ersatzstimme)
        _write_atomic(path.with_suffix(".marks.json"), json.dumps(marks, ensure_ascii=False).encode())
    elif engine == "piper" and name in _piper_files():
        data = _synth_piper(say, name)
    elif engine == "clone" and clone_available():
        with _inflight_lock:                       # wird derselbe Abschnitt gerade erzeugt? → darauf warten statt doppelt
            ev = _inflight.get(path)
            owner = ev is None
            if owner:
                ev = _inflight[path] = threading.Event()
        if not owner:
            ev.wait(CLONE_TIMEOUT)
            for _ in range(30):                    # der andere schreibt die Datei gleich nach dem Signal
                if path.exists():
                    return path.read_bytes(), MIME[path.suffix[1:]], voice_id
                time.sleep(0.1)
        try:
            data = _synth_clone(say, name, lang, low=low)
        except Exception as e:
            print(f"[clone] Fehler ({e}) – Ersatzstimme", flush=True)
            if not fallback:
                raise
            return _fallback(text, lang, voice_id, doc_id)
        finally:
            if owner:
                with _inflight_lock:
                    _inflight.pop(path, None)
                ev.set()
    else:                                          # Piper-Stimme gelöscht / Klon entfernt
        if not fallback:
            raise Meldung(STIMME_FEHLT)
        return _fallback(text, lang, voice_id, doc_id)
    print(f"[{engine}] {len(text):4d} Zeichen in {time.time() - t0:.2f}s", flush=True)

    _write_atomic(path, data)
    schedule_prune()
    if engine == "clone" and text not in PREVIEW_TEXT.values():   # Wortmarken schon mal vorbereiten
        threading.Thread(target=get_marks, args=(text, voice_id, lang), kwargs={"doc_id": doc_id}, daemon=True).start()
    return data, MIME[path.suffix[1:]], voice_id


def _ist_stimmfehler(e: BaseException) -> bool:
    # „NoAudioReceived“ betrifft nur diese eine Stimme/diesen Abschnitt (z. B. „* * *“) – kein Netzproblem
    return type(e).__name__ == "NoAudioReceived" or str(e) == "Edge lieferte kein Audio"


def _edge_fehler(e, name, fallback, text, lang, voice_id, doc_id):
    global _edge_down_until
    voice_only = _ist_stimmfehler(e)
    if fallback and not voice_only:
        _edge_down_until = time.time() + EDGE_COOLDOWN
    print(f"[edge] {name}: {type(e).__name__}" + ("" if voice_only or not fallback else f" – Piper übernimmt für {EDGE_COOLDOWN}s"), flush=True)
    if not fallback:
        raise Meldung(NICHTS_VORLESBAR if voice_only else EDGE_WEG) from e
    return _fallback(text, lang, voice_id, doc_id)


def _write_atomic(path: Path, data: bytes) -> None:
    """Über eine eigene Zwischendatei je Thread: erzeugen zwei Threads denselben Abschnitt, stört keiner den anderen."""
    tmp = path.with_name(f"{path.name}.{os.getpid()}-{threading.get_ident()}.tmp")
    try:
        tmp.write_bytes(data)
        tmp.replace(path)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise


def _fallback(text: str, lang: str, failed: str, doc_id: str | None = None) -> tuple[bytes, str, str]:
    if failed.startswith("clone:"):          # Klon kaputt → normale Standardstimme
        fb = default_voice(lang)
        if fb and not fb.startswith("clone:"):
            return synthesize(text, fb, lang, doc_id=doc_id)
    fb = fallback_voice(lang)
    if not fb or fb == failed:
        raise Meldung(KEINE_STIMME)
    return synthesize(text, fb, lang, doc_id=doc_id)


# --------------------------------------------------------------------------- #
# Cache aufräumen
# --------------------------------------------------------------------------- #
_prune_lock = threading.Lock()
_last_prune = 0.0


_marks_lock = threading.Lock()


def get_marks(text: str, voice_id: str, lang: str | None = None, compute: bool = True, doc_id: str | None = None) -> list | None:
    """Wortmarken eines erzeugten Abschnitts.
    Edge liefert sie direkt mit; für eigene Stimme und Piper bestimmt Whisper sie aus dem Audio."""
    audio_path = cache_path(text, normalize_voice_id(voice_id), doc_id)
    p = audio_path.with_suffix(".marks.json")
    try:
        return json.loads(p.read_text("utf-8"))
    except (OSError, ValueError):
        pass
    if not compute or not audio_path.exists():
        return None
    try:
        import stt
        if not stt.stt_available():
            return None
        with _marks_lock:                       # nicht zweimal gleichzeitig für denselben Abschnitt rechnen
            if p.exists():
                return json.loads(p.read_text("utf-8"))
            t0 = time.time()
            marks = stt.word_marks(audio_path.read_bytes(), lang)
            _write_atomic(p, json.dumps(marks, ensure_ascii=False).encode())   # halb geschrieben → Whisper rechnet sonst neu
            print(f"[marks] {len(marks)} Wortmarken in {time.time() - t0:.1f}s ({voice_id.split(':')[0]})", flush=True)
            return marks
    except Exception as e:
        print(f"[marks] Fehler: {e}", flush=True)
        return None


def is_cached(text: str, voice_id: str, doc_id: str | None = None) -> bool:
    return cache_path(text, normalize_voice_id(voice_id), doc_id).exists()


def cache_stats() -> dict:
    files = [p for p in CACHE_DIR.iterdir() if p.is_file()]
    return {"bytes": sum(p.stat().st_size for p in files), "files": len(files),
            "limit": cache_limit()}


def prune_cache() -> int:
    """Älteste Dateien löschen, bis der Cache unter 80 % des Limits liegt."""
    limit = cache_limit()
    with _prune_lock:
        files = []
        for p in CACHE_DIR.iterdir():
            try:
                st = p.stat()
            except OSError:                        # gerade umbenannt (Zwischendatei eines anderen Threads)
                continue
            if p.suffix == ".tmp":                 # Rest nach Absturz: nach einer Stunde weg
                if time.time() - st.st_mtime > 3600:
                    p.unlink(missing_ok=True)
                continue
            if p.is_file():
                files.append((p, st))
        total = sum(s.st_size for _, s in files)
        if total <= limit:
            return 0
        removed = 0
        for p, s in sorted(files, key=lambda x: x[1].st_mtime):
            if total <= limit * 0.8:
                break
            p.unlink(missing_ok=True)
            p.with_suffix(".marks.json").unlink(missing_ok=True)
            total -= s.st_size
            removed += 1
        print(f"[cache] {removed} alte Dateien gelöscht", flush=True)
        return removed


def schedule_prune() -> None:
    global _last_prune
    if time.time() - _last_prune > 30:
        _last_prune = time.time()
        threading.Thread(target=prune_cache, daemon=True).start()


def clear_cache() -> None:
    with _prune_lock:
        for p in CACHE_DIR.iterdir():
            if p.is_file():
                p.unlink(missing_ok=True)
