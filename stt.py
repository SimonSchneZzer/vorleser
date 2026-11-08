"""Diktat: Sprache → Text mit Whisper (faster-whisper), lokal und kostenlos."""
from __future__ import annotations

import os
import threading
import time

import meldungen
import tts

WHISPER_MODEL = os.environ.get("VORLESER_WHISPER", "small")   # tiny/base/small/medium/large-v3

_model = None
_model_lock = threading.Lock()
_stt_lock = threading.Lock()


def stt_available() -> bool:
    try:
        import faster_whisper  # noqa: F401
        return True
    except ImportError:
        return False


DIKTAT_LADEN = "Die Spracherkennung wird beim ersten Diktat einmalig geladen – dafür ist eine Internetverbindung nötig."


_model_failed = 0.0


def _get_model():
    global _model
    with _model_lock:
        if _model is None:
            from faster_whisper import WhisperModel
            print(f"[whisper] lade Modell '{WHISPER_MODEL}' (beim ersten Mal Download) …", flush=True)
            global _model_failed
            if time.time() - _model_failed < 300:  # offline: nicht bei jedem Abschnitt neu versuchen und loggen
                raise meldungen.Meldung(DIKTAT_LADEN)
            try:
                _model = WhisperModel(WHISPER_MODEL, device="cpu", compute_type="int8")
            except Exception as e:                # erster Start offline: Modell fehlt noch
                _model_failed = time.time()
                meldungen.loggen("whisper", e)
                raise meldungen.Meldung(DIKTAT_LADEN) from e
        return _model


def transcribe(data: bytes, lang: str | None = None) -> dict:
    if not stt_available():
        raise meldungen.Meldung("Diktat ist in dieser Version nicht verfügbar")
    model = _get_model()
    t0 = time.time()
    with _stt_lock:
        import numpy as np
        # selbst dekodieren (16 kHz mono float) – unabhängig von PyAV-Versionen
        pcm = tts.ffmpeg(["-i", "pipe:0", "-f", "f32le", "-ac", "1", "-ar", "16000", "pipe:1"], data)
        audio = np.frombuffer(pcm, dtype=np.float32)
        if audio.size < 16000 * 0.3:
            raise ValueError("Aufnahme ist zu kurz oder leer")
        segments, info = model.transcribe(audio, language=lang or None,
                                          vad_filter=True, beam_size=5)
        parts, last_end = [], None
        for seg in segments:
            text = seg.text.strip()
            if not text:
                continue
            if last_end is not None and seg.start - last_end > 1.8:
                parts.append("\n\n")            # längere Pause → neuer Absatz
            elif parts:
                parts.append(" ")
            parts.append(text)
            last_end = seg.end
    print(f"[whisper] {info.duration:.0f}s Audio in {time.time() - t0:.1f}s ({info.language})", flush=True)
    return {"text": "".join(parts).strip(), "lang": info.language, "duration": info.duration}


def word_marks(data: bytes, lang: str | None = None) -> list:
    """Wort-Zeitmarken [[start_s, dauer_s, wort], …] aus fertigem Audio (für Stimmen ohne eigene Marken)."""
    import numpy as np
    model = _get_model()
    pcm = tts.ffmpeg(["-i", "pipe:0", "-f", "f32le", "-ac", "1", "-ar", "16000", "pipe:1"], data)
    audio = np.frombuffer(pcm, dtype=np.float32)
    out = []
    with _stt_lock:
        segments, _ = model.transcribe(audio, language=lang or None, word_timestamps=True,
                                       vad_filter=False, beam_size=1, condition_on_previous_text=False)
        for seg in segments:
            for w in seg.words or []:
                word = w.word.strip()
                if word:
                    out.append([round(w.start, 3), round(max(0.0, w.end - w.start), 3), word])
    return out
