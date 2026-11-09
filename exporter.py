"""Ganzen Text als Hörbuchdatei exportieren: MP3 oder M4B, jeweils mit Kapitelmarken."""
from __future__ import annotations

import json
import re
import tempfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import meldungen
import paths
import settings
import tts

EXPORT_DIR = tts.DATA_DIR / "exports"
EXPORT_DIR.mkdir(parents=True, exist_ok=True)

RATE = 24000                 # Samplerate der Zwischen-PCM-Datei (mono, 16 bit)
BYTES_PER_SEC = RATE * 2
PAUSE = {"chunk": 0.25, "par": 0.5, "heading_before": 1.0, "heading_after": 0.7}
FORMATS = {"mp3": ("libmp3lame", "mp3", "audio/mpeg"), "m4b": ("aac", "ipod", "audio/mp4"),
           "wav": ("pcm_s16le", "wav", "audio/wav")}   # WAV: unkomprimiert, ohne Kapitel
# "prepare" = nur alle Abschnitte vertonen (Cache füllen), z. B. für die langsame Klonstimme


RETRY_WAIT = (5, 20, 60)     # Sekunden – Edge-Aussetzer überbrücken (Sperre nach Ausfall: 60 s)


def synth_strict(doc: dict, i: int, low: bool = False, stop=lambda: False) -> bytes:
    """Abschnitt in GENAU der Stimme des Texts – keine stille Ersatzstimme (sonst Hörbuch mit gemischten Stimmen
    bzw. „vorbereitet“, obwohl die gewählte Stimme fehlt). Kurze Edge-Aussetzer werden mit Pausen überbrückt;
    `stop()` (Abbrechen/Fehler) beendet das Warten sofort."""
    text = doc["chunks"][i]["text"]
    for wait in (*RETRY_WAIT, None):
        try:
            data, _, _ = tts.synthesize(text, doc["voice"], doc["lang"], fallback=False, low=low, doc_id=doc.get("id"))
            return data
        except meldungen.Meldung as e:
            if str(e) == tts.NICHTS_VORLESBAR:      # „* * *“ o. Ä.: diese eine Stelle wie beim Vorlesen überbrücken
                return tts.synthesize(text, doc["voice"], doc["lang"], fallback=True, low=low, doc_id=doc.get("id"))[0]
            if wait is None or str(e) != tts.EDGE_WEG:
                raise
            print(f"[export] Abschnitt {i + 1}: {e} – neuer Versuch in {wait} s", flush=True)
            end = time.time() + wait
            while time.time() < end:
                if stop():
                    raise InterruptedError
                time.sleep(0.25)


def chunk_audio(doc: dict, i: int, stop=lambda: False) -> bytes:
    return synth_strict(doc, i, stop=stop)


def _cancelled(key: str) -> bool:
    with _lock:
        job = _jobs.get(key)
        return job is None or bool(job.get("cancel"))

_jobs: dict[str, dict] = {}
_lock = threading.Lock()

# „Vorab erzeugen“ unterbrochen? Die Datei hält Texte, deren Vorab-Erzeugen läuft; endet der Auftrag normal (fertig,
# abgebrochen, Fehler), fliegt der Eintrag raus. Wird die App mittendrin beendet, bleibt er → nach dem Start fragt
# eine Karte „Weitermachen?“ (Board 20).
PENDING_FILE = tts.DATA_DIR / "prepare-pending.json"
_pending_lock = threading.Lock()


def pending_ids() -> list[str]:
    try:
        ids = json.loads(PENDING_FILE.read_text("utf-8"))
        return [i for i in ids if isinstance(i, str)] if isinstance(ids, list) else []
    except (OSError, ValueError):
        return []


def set_pending(doc_id: str, on: bool) -> None:
    with _pending_lock:
        ids = [i for i in pending_ids() if i != doc_id] + ([doc_id] if on else [])
        try:
            tmp = PENDING_FILE.with_suffix(".tmp")
            tmp.write_text(json.dumps(ids), "utf-8")
            tmp.replace(PENDING_FILE)
        except OSError as e:
            print(f"[vorab] Merkliste nicht schreibbar: {e}", flush=True)


def export_path(doc_id: str, fmt: str) -> Path:
    return EXPORT_DIR / f"{doc_id}.{fmt}"


def status(doc_id: str, kind: str = "export") -> dict:
    if kind == "prepare":
        with _lock:
            job = dict(_jobs.get(doc_id + "#prep") or {"status": "none"})
        job.pop("cancel", None)
        return job
    with _lock:
        job = dict(_jobs.get(doc_id) or {})
    job.pop("cancel", None)
    if not job:
        ready = [f for f in FORMATS if export_path(doc_id, f).exists()]
        job = {"status": "ready" if ready else "none", "format": ready[0] if ready else None}
    if job.get("status") == "ready":
        p = export_path(doc_id, job["format"])
        job["size"] = p.stat().st_size if p.exists() else 0
    return job


TEMPO_MIN, TEMPO_MAX = 0.5, 15.0


def _atempo(rate: float) -> str:
    """ffmpeg-Filter für Tempo `rate` – atempo in Stufen von höchstens 2× bzw. 0,5× (gleichmäßiger Klang)."""
    if abs(rate - 1) < 1e-3:
        return ""
    steps, r = [], rate
    while r > 2:
        steps.append(2.0); r /= 2
    while r < 0.5:
        steps.append(0.5); r /= 0.5
    steps.append(r)
    return ",".join(f"atempo={x:.4f}" for x in steps)


def start(doc: dict, fmt: str, ambient: bool = False, rate: float = 1.0) -> dict:
    if fmt not in FORMATS and fmt != "prepare":
        raise ValueError("Format muss mp3, m4b, wav oder prepare sein")
    key = doc["id"] + ("#prep" if fmt == "prepare" else "")
    with _lock:
        cur = _jobs.get(key)
        if cur and cur["status"] == "running":
            return dict(cur)
        _jobs[key] = {"status": "running", "format": fmt, "done": 0,
                      "total": len(doc["chunks"]), "phase": "Vertonen", "started": time.time()}
    if fmt == "prepare":
        set_pending(doc["id"], True)
    amb = _ambient() if ambient and fmt != "prepare" else None
    target = _prepare if fmt == "prepare" else _run
    kw = {} if fmt == "prepare" else {"ambient": amb, "rate": max(TEMPO_MIN, min(TEMPO_MAX, float(rate or 1)))}
    threading.Thread(target=target, args=(doc, fmt), kwargs=kw, daemon=True).start()
    return status(doc["id"], "prepare" if fmt == "prepare" else "export")


def running() -> list[dict]:
    """Laufende Hintergrund-Aufträge (Vorab erzeugen, Export) – für die Anzeige in der Bibliothek."""
    with _lock:
        return [{"doc": k.split("#")[0], "kind": "prepare" if k.endswith("#prep") else "export",
                 "done": j.get("done", 0), "total": j.get("total", 0)}
                for k, j in _jobs.items() if j.get("status") == "running"]


def cancel(doc_id: str, kind: str = "export") -> None:
    key = doc_id + ("#prep" if kind == "prepare" else "")
    with _lock:
        if key in _jobs and _jobs[key]["status"] == "running":
            _jobs[key]["cancel"] = True


def delete_exports(doc_id: str) -> None:
    cancel(doc_id)
    cancel(doc_id, "prepare")
    for f in FORMATS:
        export_path(doc_id, f).unlink(missing_ok=True)
    with _lock:
        _jobs.pop(doc_id, None)


def _prepare(doc: dict, _fmt: str) -> None:
    """Alle Abschnitte erzeugen – im Hintergrund, mit niedriger Priorität (Vorlesen geht vor)."""
    try:
        _prepare_run(doc)
    finally:                                  # normales Ende (auch Abbruch/Fehler) → nicht mehr „unterbrochen“
        set_pending(doc["id"], False)


def _prepare_run(doc: dict) -> None:
    key = doc["id"] + "#prep"
    try:
        for i, ch in enumerate(doc["chunks"]):
            if not tts.is_cached(ch["text"], doc["voice"], doc["id"]):
                synth_strict(doc, i, low=True, stop=lambda: _cancelled(key))
            done = sum(tts.is_cached(c["text"], doc["voice"], doc["id"]) for c in doc["chunks"])   # echte Zahl, nicht Schleifenzähler
            if not _update(key, done=done):
                _update(key, status="cancelled")
                return
        _update(key, status="ready", phase="Fertig")
    except Exception as e:
        meldungen.loggen("vorab erzeugen", e)
        _update(key, status="error", error=meldungen.fuer_nutzer(e))


def _update(doc_id: str, **kw) -> bool:
    """Job-Status setzen; liefert False, wenn abgebrochen wurde."""
    with _lock:
        job = _jobs.get(doc_id)
        if job is None:          # Text wurde inzwischen gelöscht → Job verwerfen
            return False
        job.update(kw)
        return not job.get("cancel")


def _meta_escape(s: str) -> str:
    return re.sub(r"([=;#\\\n])", r"\\\1", s)


def _ambient() -> tuple[Path, float] | None:
    """Gewählter Atmosphäre-Klang (Einstellungen) als (Datei, Lautstärke 0–1) – oder None, wenn aus."""
    s = settings.load()
    path = paths.STATIC_DIR / "klang" / f"{s['ambient']}.m4a"
    if s["ambient"] == "aus" or not s["ambientVol"] or not path.exists():
        return None
    return path, s["ambientVol"] / 100


def _run(doc: dict, fmt: str, ambient: tuple[Path, float] | None = None, rate: float = 1.0) -> None:
    doc_id = doc["id"]
    chunks = doc["chunks"]
    is_edge = doc["voice"].startswith("edge:")
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            raw_path = Path(tmpdir) / "all.pcm"
            starts: list[float] = []           # Startzeit (s) jedes Abschnitts

            abort = threading.Event()            # Fehler in einem Abschnitt → wartende Nachbarn hören sofort auf

            def synth(i):
                return chunk_audio(doc, i, stop=lambda: abort.is_set() or _cancelled(doc_id))

            silence = lambda sec: b"\0\0" * int(RATE * sec)  # noqa: E731
            with open(raw_path, "wb") as raw, ThreadPoolExecutor(tts.EDGE_PARALLEL if is_edge else 1) as pool:
                try:
                    futures = []
                    for i, ch in enumerate(chunks):
                        if i == 0:
                            pass
                        elif ch.get("h"):
                            raw.write(silence(PAUSE["heading_before"]))
                        elif chunks[i - 1].get("h"):
                            raw.write(silence(PAUSE["heading_after"]))
                        else:
                            raw.write(silence(PAUSE["par"] if ch.get("par") else PAUSE["chunk"]))
                        # nur ein kleines Fenster vorausschicken, damit der Speicher klein bleibt
                        while len(futures) <= i + tts.EDGE_PARALLEL * 2 and len(futures) < len(chunks):
                            futures.append(pool.submit(synth, len(futures)))
                        data = futures[i].result()
                        futures[i] = None
                        starts.append(raw.tell() / BYTES_PER_SEC)
                        raw.write(tts.ffmpeg(["-i", "pipe:0", "-f", "s16le", "-ac", "1", "-ar", str(RATE), "pipe:1"], data))
                        if not _update(doc_id, done=i + 1):
                            for f in futures:
                                if f:
                                    f.cancel()
                            raise InterruptedError
                except BaseException:            # Fehler/Abbruch: Wartende stoppen, nicht Gestartete verwerfen
                    abort.set()
                    pool.shutdown(wait=False, cancel_futures=True)
                    raise
                total = raw.tell() / BYTES_PER_SEC

            # Kapitelmarken als FFMETADATA
            meta = [";FFMETADATA1", f"title={_meta_escape(doc['title'])}",
                    f"album={_meta_escape(doc['title'])}", "artist=Vorleser", "genre=Audiobook"]
            chapters = doc.get("chapters") or []
            for n, ch in enumerate(chapters):                  # Zeiten im fertigen (ggf. schnelleren) Hörbuch
                start = (starts[ch["chunk"]] if ch["chunk"] < len(starts) else total) / rate
                end = (starts[chapters[n + 1]["chunk"]] if n + 1 < len(chapters) else total) / rate
                meta += ["[CHAPTER]", "TIMEBASE=1/1000", f"START={int(start * 1000)}",
                         f"END={int(end * 1000)}", f"title={_meta_escape(ch['title'])}"]
            meta_path = Path(tmpdir) / "meta.txt"
            meta_path.write_text("\n".join(meta) + "\n", "utf-8")

            _update(doc_id, phase="Kodieren")
            codec, muxer, _ = FORMATS[fmt]
            out = export_path(doc_id, fmt)
            tmp_out = out.with_suffix(f".part.{fmt}")
            # Eingänge: 0 = Stimme (roh), [1 = Kapitel-Metadaten], [letzter = Atmosphäre als Endlosschleife]
            inputs = ["-f", "s16le", "-ar", str(RATE), "-ac", "1", "-i", str(raw_path)]
            if fmt != "wav":
                inputs += ["-i", str(meta_path)]
            out_total = total / rate
            graph: list[str] = []
            vsrc = "[0:a]"
            if _atempo(rate):                     # Tempo wie beim Hören (Simon: im Export wählbar, vorausgewählt = aktuell)
                graph.append(f"[0:a]{_atempo(rate)}[v]")
                vsrc = "[v]"
            src = vsrc if graph else "0:a"
            if ambient:                           # Atmosphäre leise unter die Stimme mischen, ein-/ausblenden (nicht beschleunigt)
                inputs += ["-stream_loop", "-1", "-i", str(ambient[0])]
                n = 1 if fmt == "wav" else 2
                graph += [f"[{n}:a]aformat=channel_layouts=mono,aresample={RATE},volume={ambient[1]:.3f},"
                          f"afade=t=in:d=2,afade=t=out:st={max(0.0, out_total - 3):.2f}:d=3[amb]",
                          f"{vsrc}[amb]amix=inputs=2:duration=first:normalize=0[mix]"]
                src = "[mix]"
            filt = ["-filter_complex", ";".join(graph)] if graph else []
            if fmt == "wav":                      # keine Bitrate/Kapitel; >4 GB automatisch als RF64
                enc = ["-map", src, "-c:a", codec, "-rf64", "auto",
                       "-metadata", f"title={doc['title']}", "-metadata", "artist=Vorleser"]
            else:
                enc = ["-map", src, "-map_metadata", "1", "-map_chapters", "1", "-c:a", codec, "-b:a", "64k"]
            try:
                tts.ffmpeg(["-y", *inputs, *filt, *enc, "-f", muxer, str(tmp_out)])
                tmp_out.replace(out)
            except BaseException:
                tmp_out.unlink(missing_ok=True)       # keine halbe Datei in exports/ liegen lassen
                raise
            for other in FORMATS:                 # nur das jeweils letzte Export behalten
                if other != fmt:
                    export_path(doc_id, other).unlink(missing_ok=True)
        _update(doc_id, status="ready", phase="Fertig", duration=total / rate)
        print(f"[export] {doc['title']} → {fmt} ({total / 60:.1f} min)", flush=True)
    except InterruptedError:
        _update(doc_id, status="cancelled", phase="Abgebrochen")
    except Exception as e:
        meldungen.loggen("export", e)
        _update(doc_id, status="error", error=meldungen.fuer_nutzer(e))
