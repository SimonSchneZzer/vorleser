"""Audio: Opus mit Dauer, Cache, Stimmenauswahl, Piper, espeak-Pfad."""
import os
import time
from pathlib import Path

import pytest

import paths
import settings
import tts
from conftest import ffprobe_duration, needs_piper, sine_wav


def test_opus_hat_dauer_im_header():
    """Regression: WebM aus pipe:1 hatte 'Duration: N/A' → Wortmarkierung lief davon."""
    webm = tts.to_opus(sine_wav(1.5))
    d = ffprobe_duration(webm)
    assert d is not None and abs(d - 1.5) < 0.1


def test_alter_cache_wird_umverpackt(home):
    old = tts.ffmpeg(["-i", "pipe:0", "-c:a", "libopus", "-b:a", "32k", "-f", "webm", "pipe:1"], sine_wav(1.0))
    assert ffprobe_duration(old) is None                         # so sahen alte Cache-Dateien aus
    p = paths.CACHE_DIR / "alt.webm"
    p.write_bytes(old)
    flag = paths.DATA_DIR / "cache-webm-duration-ok"
    flag.unlink(missing_ok=True)
    tts.fix_webm_durations()
    assert abs(ffprobe_duration(p) - 1.0) < 0.1
    assert flag.exists()
    mtime = p.stat().st_mtime
    tts.fix_webm_durations()                                     # nur einmal
    assert p.stat().st_mtime == mtime
    p.unlink()


def test_cache_dateiendung_nach_stimme():
    assert tts.cache_path("x", "edge:de-DE-KatjaNeural").suffix == ".mp3"
    assert tts.cache_path("x", "piper:de_DE-thorsten-medium").suffix == ".webm"
    assert tts.cache_path("x", "clone:ich").suffix == ".webm"
    assert tts.cache_path("a", "piper:v") != tts.cache_path("b", "piper:v")


def test_alte_voice_ids():
    assert tts.normalize_voice_id("de_DE-thorsten-medium") == "piper:de_DE-thorsten-medium"
    assert tts.normalize_voice_id("edge:x") == "edge:x"


def test_cache_aufraeumen_aelteste_zuerst():
    settings.update({"cacheMB": 50})
    files = []
    for i in range(6):                                           # 6 × 10 MB = 60 MB > 50 MB
        p = paths.CACHE_DIR / f"prune{i}.webm"
        p.write_bytes(b"\0" * 10 * 1024 * 1024)
        os.utime(p, (time.time() - 100 + i, time.time() - 100 + i))
        files.append(p)
    try:
        removed = tts.prune_cache()
        assert removed >= 2
        assert not files[0].exists() and files[-1].exists()       # älteste weg, neueste bleibt
        assert tts.cache_stats()["bytes"] <= 50 * 1024 * 1024
    finally:
        for p in files:
            p.unlink(missing_ok=True)
        settings.update({"cacheMB": 500})


def test_ohne_onlinestimmen_ist_piper_standard(monkeypatch):
    monkeypatch.setattr(tts, "_edge_voices", lambda: [])
    if not tts._piper_voices():
        pytest.skip("keine Piper-Stimmen")
    assert tts.default_voice("de").startswith("piper:")


def test_bevorzugte_onlinestimme(monkeypatch):
    fake = [{"id": "edge:de-DE-KatjaNeural", "lang": "de"}, {"id": "edge:de-DE-SeraphinaMultilingualNeural", "lang": "de"}]
    monkeypatch.setattr(tts, "_edge_voices", lambda: fake)
    monkeypatch.setattr(tts, "_piper_voices", lambda: [])
    monkeypatch.setattr(tts, "_clone_voices", lambda: [])
    assert tts.default_voice("de") == "edge:de-DE-SeraphinaMultilingualNeural"
    settings.update({"defaultVoices": {"de": "edge:de-DE-KatjaNeural"}})
    assert tts.default_voice("de") == "edge:de-DE-KatjaNeural"   # eigene Wahl schlägt Vorschlag
    settings.update({"defaultVoices": {"de": ""}})


def test_erster_start_wartet_auf_onlinestimmen(monkeypatch, tmp_path):
    """Regression: ohne gespeicherte Liste wurde Piper zur Standardstimme."""
    monkeypatch.setattr(tts, "EDGE_LIST_FILE", tmp_path / "fehlt.json")
    monkeypatch.setattr(tts, "_edge_cache", {"voices": [], "loaded": 0.0})
    ev = tts._edge_ready.__class__()
    monkeypatch.setattr(tts, "_edge_ready", ev)
    import threading
    def fertig():
        time.sleep(0.3)
        tts._edge_cache["voices"] = [{"id": "edge:de-DE-SeraphinaMultilingualNeural", "lang": "de", "region": "DE",
                                       "name": "Seraphina", "meta": "", "label": ""}]
        tts._edge_cache["loaded"] = time.time()
        ev.set()
    threading.Thread(target=fertig).start()
    t = time.time()
    assert tts._edge_voices()[0]["id"].startswith("edge:")
    assert 0.2 < time.time() - t < 5


@needs_piper
def test_laenge_aus_cache_datei_ohne_dekodieren(tmp_path):
    """Export-Dialog: Länge aus WebM-Kopf bzw. MP3-Größe (Edge: feste 48 kbit/s) – wie ffprobe."""
    webm = tmp_path / "a.webm"
    webm.write_bytes(tts.to_opus(sine_wav(2.3)))
    assert abs(tts.audio_seconds(webm) - ffprobe_duration(webm)) < 0.01
    mp3 = tmp_path / "b.mp3"
    mp3.write_bytes(b"\0" * 6000 * 3)
    assert abs(tts.audio_seconds(mp3) - 3.0) < 0.01
    kaputt = tmp_path / "c.webm"
    kaputt.write_bytes(b"kein webm")
    assert tts.audio_seconds(kaputt) is None


def test_piper_spricht_mit_dauer():
    name = tts._piper_voices()[0]["id"].split(":", 1)[1]
    webm = tts._synth_piper("Hallo, das ist ein kurzer Test.", name)
    assert ffprobe_duration(webm) > 0.5


@needs_piper
def test_synthesize_cached():
    vid = tts._piper_voices()[0]["id"]
    data, mime, used = tts.synthesize("Ein Satz für den Cache.", vid, "de")
    assert mime == "audio/webm" and used == vid
    assert tts.is_cached("Ein Satz für den Cache.", vid)
    assert tts.synthesize("Ein Satz für den Cache.", vid, "de")[0] == data


def test_unbekannte_stimme_faellt_auf_piper(monkeypatch):
    if not tts._piper_voices():
        pytest.skip("keine Piper-Stimmen")
    _, _, used = tts.synthesize("Ersatz.", "piper:gibt-es-nicht", "de")
    assert used.startswith("piper:") and used != "piper:gibt-es-nicht"


def test_mitgelieferte_piper_stimme_nicht_loeschbar():
    if paths.USER_VOICES == paths.BUNDLED_VOICES or not tts._piper_voices():
        pytest.skip("Entwicklung ohne getrennten Stimmenordner")
    key = tts._piper_voices()[0]["key"]
    with pytest.raises(ValueError):
        tts.delete_piper(key)


def test_nachinstallierte_stimme_hat_vorrang(home):
    src = next(paths.BUNDLED_VOICES.glob("*.onnx"), None)
    if src is None:
        pytest.skip("keine Piper-Stimmen")
    files = tts._piper_files()
    assert files[src.stem].parent in (paths.BUNDLED_VOICES, paths.USER_VOICES)


def test_espeak_kurzer_pfad_bleibt():
    assert len(str(tts._espeak_dir())) < 150


def test_espeak_langer_pfad_wird_kopiert(monkeypatch, tmp_path):
    """Regression: espeak-ng beendete bei Pfaden > 160 Zeichen den ganzen Prozess."""
    import piper.phonemize_espeak as pe
    lang = tmp_path / ("x" * 170) / "espeak-ng-data"
    lang.mkdir(parents=True)
    (lang / "phontab").write_bytes(b"test")
    monkeypatch.setattr(pe, "ESPEAK_DATA_DIR", lang)
    ziel = tts._espeak_dir()
    assert len(str(ziel)) < 150 and (ziel / "phontab").read_bytes() == b"test"


def test_klon_vorlesen_hat_vorrang_vor_hoerprobe(monkeypatch):
    """Hörprobe im Hintergrund wartet, wenn vorgelesen werden soll (laufender Abschnitt wird fertig)."""
    import threading
    w = tts._CloneWorker()
    order = []
    def fake(text, lang, ref, tempfile):
        order.append(text)
        time.sleep(0.4)
        return b"wav"
    monkeypatch.setattr(w, "_synth_locked", fake)
    a = threading.Thread(target=w.synth, args=("hoerprobe-1", "de", None), kwargs={"low": True}); a.start()
    time.sleep(0.1)                                      # Hörprobe läuft schon …
    c = threading.Thread(target=w.synth, args=("hoerprobe-2", "de", None), kwargs={"low": True}); c.start()
    time.sleep(0.05)
    b = threading.Thread(target=w.synth, args=("vorlesen", "de", None)); b.start()   # … dann kommt Vorlesen
    for t in (a, b, c):
        t.join(5)
    assert order == ["hoerprobe-1", "vorlesen", "hoerprobe-2"]


def test_klon_abschnitt_nicht_doppelt_erzeugen(monkeypatch, tmp_path):
    """Hörprobe läuft im Hintergrund, Nutzer klickt Play: kein zweites Rechnen, beide bekommen das Ergebnis."""
    import threading
    calls = []
    def fake_clone(text, slug, lang, low=False):
        calls.append(low)
        time.sleep(0.5)
        return b"OggS-fake-audio"
    monkeypatch.setattr(tts, "_synth_clone", fake_clone)
    monkeypatch.setattr(tts, "clone_available", lambda: True)
    text, vid = "Doppelt angefragter Satz.", "clone:test-stimme"
    tts.cache_path(text, vid).unlink(missing_ok=True)
    res = []
    t1 = threading.Thread(target=lambda: res.append(tts.synthesize(text, vid, "de", fallback=False, low=True)))
    t1.start(); time.sleep(0.1)
    res.append(tts.synthesize(text, vid, "de", fallback=False))
    t1.join(5)
    assert len(calls) == 1 and len(res) == 2 and res[0][0] == res[1][0] == b"OggS-fake-audio"
    tts.cache_path(text, vid).unlink(missing_ok=True)


def test_verschwundene_onlinestimmen_bleiben(monkeypatch, tmp_path):
    """Meldung 14.11.2026: Microsoft listet Conrad, Katja, Seraphina … nicht mehr, sie sprechen aber weiter."""
    import asyncio
    liste = tmp_path / "edge_voices.json"
    monkeypatch.setattr(tts, "EDGE_LIST_FILE", liste)
    monkeypatch.setattr(tts, "_edge_cache", {"voices": [], "loaded": 0.0})
    liste.write_text('[{"id": "edge:de-DE-AltNeural", "engine": "edge", "lang": "de", "region": "DE", '
                     '"label": "Alt (DE)", "gender": "Male", "name": "Alt", "meta": ""}]', "utf-8")

    monkeypatch.setattr(asyncio, "run", lambda coro: (coro.close(), [
        {"ShortName": "de-DE-TanjaNeural", "Locale": "de-DE", "Gender": "Female", "Status": "GA"}])[1])
    tts.refresh_edge_voices()
    ids = [v["id"] for v in tts._edge_voices()]
    assert "edge:de-DE-TanjaNeural" in ids                      # neu aus der Online-Liste
    assert "edge:de-DE-AltNeural" in ids                        # aus der bisher gespeicherten Liste
    assert "edge:de-DE-ConradNeural" in ids                     # aus der mitgelieferten Grundliste
    assert len(ids) == len(set(ids))
    assert tts.default_voice("de") == "edge:de-DE-SeraphinaMultilingualNeural"
    assert "edge:de-DE-ConradNeural" in liste.read_text("utf-8")   # auch gespeichert


def test_grundliste_ohne_gespeicherte_liste(monkeypatch, tmp_path):
    """Erster Start ohne Netz bzw. alte gespeicherte Liste: Grundliste ergänzt."""
    monkeypatch.setattr(tts, "EDGE_LIST_FILE", tmp_path / "edge_voices.json")
    monkeypatch.setattr(tts, "_edge_cache", {"voices": [], "loaded": time.time()})
    ev = tts._edge_ready.__class__()
    ev.set()
    monkeypatch.setattr(tts, "_edge_ready", ev)
    ids = [v["id"] for v in tts._edge_voices()]
    assert "edge:de-DE-ConradNeural" in ids and "edge:en-US-AvaMultilingualNeural" in ids
