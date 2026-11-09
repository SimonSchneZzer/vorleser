"""Speicherverwaltung: Wer belegt wie viel Platz – und gezielt löschen.

Der Audio-Cache ist nach sha1(Stimme + Abschnittstext) benannt (`tts.cache_path`). Welche Datei zu welchem
Text gehört, lässt sich daher exakt nachrechnen: für jeden Abschnitt eines Texts × jede bekannte Stimme.
Was keinem Text und keiner Hörprobe zugeordnet ist („Reste“), stammt von gelöschten/bearbeiteten Texten
oder entfernten Stimmen.
"""
from __future__ import annotations

import json
import os
import shutil
import threading
from pathlib import Path

import clone_setup
import exporter
import paths
import tts

DOCS_DIR = paths.DATA_DIR / "docs"
_lock = threading.Lock()


def _dir_bytes(d: Path) -> int:
    total = 0
    if not d.exists():
        return 0
    for root, _, files in os.walk(d):
        for f in files:
            try:
                total += os.path.getsize(os.path.join(root, f))
            except OSError:
                pass
    return total


def _cache_index() -> dict[str, int]:
    """Dateiname → Größe für alles im Audio-Cache."""
    out = {}
    try:
        with os.scandir(paths.CACHE_DIR) as it:
            for e in it:
                if e.is_file():
                    out[e.name] = e.stat().st_size
    except OSError:
        pass
    return out


def _voice_ids(extra: set[str] = frozenset()) -> set[str]:
    ids = {v["id"] for v in tts.list_voices()} | {tts.normalize_voice_id(x) for x in extra if x}
    return ids


def _names_for(texts, voice_ids, index: dict[str, int], doc_id: str | None = None) -> set[str]:
    """Cache-Dateien (Audio + Wortmarken) für diese Texte mit irgendeiner der Stimmen."""
    found = set()
    for text in texts:
        for vid in voice_ids:
            p = tts.cache_path(text, vid, doc_id)
            if p.name in index:
                found.add(p.name)
                marks = p.with_suffix(".marks.json").name
                if marks in index:
                    found.add(marks)
    return found


def _docs() -> list[dict]:
    out = []
    for p in DOCS_DIR.glob("*.json"):
        try:
            out.append(json.loads(p.read_text("utf-8")))
        except (OSError, ValueError):
            pass
    return out


def _preview_names(index, voice_ids) -> set[str]:
    return _names_for(set(tts.PREVIEW_TEXT.values()), voice_ids, index)


def _whisper_dir() -> Path:
    hf = Path(os.environ.get("HF_HOME") or Path.home() / ".cache" / "huggingface")
    return hf / "hub"


def _whisper_bytes() -> int:
    hub = _whisper_dir()
    return sum(_dir_bytes(d) for d in hub.glob("models--Systran--faster-whisper-*")) if hub.exists() else 0


def report() -> dict:
    """Aufschlüsselung des belegten Platzes."""
    index = _cache_index()
    docs = _docs()
    voice_ids = _voice_ids({d.get("voice", "") for d in docs})
    assigned: set[str] = set()
    per_doc = []
    for d in docs:
        names = _names_for({c["text"] for c in d.get("chunks", [])}, voice_ids, index, d.get("id"))
        assigned |= names
        exp = sum(exporter.export_path(d["id"], f).stat().st_size for f in exporter.FORMATS
                  if exporter.export_path(d["id"], f).exists())
        per_doc.append({"id": d["id"], "title": d.get("title", ""), "audio": sum(index[n] for n in names),
                        "files": len([n for n in names if not n.endswith(".marks.json")]), "export": exp})
    per_doc.sort(key=lambda x: x["audio"] + x["export"], reverse=True)
    prev = _preview_names(index, voice_ids)
    assigned |= prev
    other = set(index) - assigned
    exports = sum(x["export"] for x in per_doc) + sum(
        p.stat().st_size for p in exporter.EXPORT_DIR.glob("*") if p.is_file() and p.stem not in {d["id"] for d in docs})
    clone_bytes = _dir_bytes(paths.CLONE_ENV) + (
        _dir_bytes(clone_setup.PY_DIR) + _dir_bytes(paths.CLONE_MODELS) if paths.FROZEN else 0)
    piper = sum(p.stat().st_size for d in (paths.BUNDLED_VOICES, paths.USER_VOICES) if d.exists()
                for p in d.glob("*.onnx*")) if paths.FROZEN else _dir_bytes(paths.USER_VOICES)
    return {
        "docs": [x for x in per_doc if x["audio"] or x["export"]],
        "audio": sum(index.values()),
        "previews": {"bytes": sum(index[n] for n in prev), "files": len(prev)},
        "other": {"bytes": sum(index[n] for n in other), "files": len(other)},
        "exports": exports,
        "texts": _dir_bytes(DOCS_DIR),
        "whisper": {"bytes": _whisper_bytes(), "removable": paths.FROZEN},
        "clone": {"bytes": clone_bytes if clone_setup.installed() else 0, "installed": clone_setup.installed(),
                  "removable": paths.FROZEN},
        "piper": piper,
        "limit": tts.cache_limit(),
    }


def _remove(names) -> int:
    freed = 0
    with _lock:
        for n in names:
            p = paths.CACHE_DIR / n
            try:
                freed += p.stat().st_size
                p.unlink()
            except OSError:
                pass
    return freed


def delete_doc_audio(doc: dict) -> int:
    """Erzeugtes Audio + Wortmarken eines Texts löschen (der Text selbst bleibt)."""
    index = _cache_index()
    names = _names_for({c["text"] for c in doc.get("chunks", [])}, _voice_ids({doc.get("voice", "")}), index, doc.get("id"))
    keep = _preview_names(index, _voice_ids())        # Hörproben nie mitlöschen
    return _remove(names - keep)


def delete_previews() -> int:
    index = _cache_index()
    return _remove(_preview_names(index, _voice_ids()))


def delete_other() -> int:
    """Reste: Audio, das zu keinem Text und keiner Hörprobe mehr gehört."""
    index = _cache_index()
    docs = _docs()
    voice_ids = _voice_ids({d.get("voice", "") for d in docs})
    used = _preview_names(index, voice_ids)
    for d in docs:
        used |= _names_for({c["text"] for c in d.get("chunks", [])}, voice_ids, index, d.get("id"))
    return _remove(set(index) - used)


def delete_exports() -> int:
    freed = 0
    for p in exporter.EXPORT_DIR.glob("*"):
        if p.is_file():
            freed += p.stat().st_size
            exporter.delete_exports(p.stem)
            p.unlink(missing_ok=True)
    return freed


def delete_whisper() -> int:
    """Whisper-Modell entfernen (nur in der App; wird beim nächsten Diktat neu geladen)."""
    if not paths.FROZEN:
        raise ValueError("Nur in der installierten App möglich")
    import stt
    freed = _whisper_bytes()
    with stt._model_lock:
        stt._model = None
    for d in _whisper_dir().glob("models--Systran--faster-whisper-*"):
        shutil.rmtree(d, ignore_errors=True)
    return freed
