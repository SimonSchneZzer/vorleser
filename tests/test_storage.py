"""Speicherverwaltung: Zuordnung des Caches zu Texten, gezieltes Löschen, Löschen mit dem Text."""
import pytest

import paths
import storage
import tts
from conftest import needs_piper


def _fake_audio(text: str, vid: str, size: int = 1000) -> None:
    p = tts.cache_path(text, vid)
    p.write_bytes(b"\0" * size)
    p.with_suffix(".marks.json").write_text("[]")


@pytest.fixture
def voice():
    v = tts._piper_voices()
    if not v:
        pytest.skip("keine Piper-Stimmen")
    return v[0]["id"]


@pytest.fixture(autouse=True)
def leerer_cache():
    tts.clear_cache()
    yield
    tts.clear_cache()


@needs_piper
def test_bericht_ordnet_audio_den_texten_zu(api, voice):
    _, a = api.json("POST", "/api/docs", {"text": "Erster Text. Mit zwei Sätzen.", "title": "A", "voice": voice})
    _, b = api.json("POST", "/api/docs", {"text": "Ganz anderer Text hier.", "title": "B", "voice": voice})
    try:
        full_a = api.json("GET", f"/api/docs/{a['id']}")[1]
        for c in full_a["chunks"]:
            _fake_audio(c["text"], voice, 2000)
        _fake_audio("Ganz anderer Text hier.", voice, 500)
        _fake_audio(tts.PREVIEW_TEXT["de"], voice, 300)                 # Hörprobe
        _fake_audio("Ein Satz aus einem längst gelöschten Text.", voice, 700)   # Rest
        r = storage.report()
        by_id = {d["id"]: d for d in r["docs"]}
        assert by_id[a["id"]]["audio"] > by_id[b["id"]]["audio"] > 0
        assert r["docs"][0]["id"] == a["id"]                             # größte zuerst
        assert r["previews"]["bytes"] >= 300 and r["other"]["bytes"] >= 700
    finally:
        api.call("DELETE", f"/api/docs/{a['id']}")
        api.call("DELETE", f"/api/docs/{b['id']}")


@needs_piper
def test_audio_eines_texts_loeschen_laesst_rest_stehen(api, voice):
    _, a = api.json("POST", "/api/docs", {"text": "Nur dieser Text.", "title": "A", "voice": voice})
    try:
        _fake_audio("Nur dieser Text.", voice)
        _fake_audio(tts.PREVIEW_TEXT["de"], voice)
        _fake_audio("Fremder Satz.", voice)
        s, r = api.json("DELETE", f"/api/storage/docs/{a['id']}")
        assert s == 200 and r["freed"] > 0
        assert not tts.cache_path("Nur dieser Text.", voice).exists()
        assert not tts.cache_path("Nur dieser Text.", voice).with_suffix(".marks.json").exists()
        assert tts.cache_path(tts.PREVIEW_TEXT["de"], voice).exists()     # Hörprobe bleibt
        assert tts.cache_path("Fremder Satz.", voice).exists()            # anderes bleibt
        assert api.call("GET", f"/api/docs/{a['id']}")[0] == 200          # der Text selbst bleibt
    finally:
        api.call("DELETE", f"/api/docs/{a['id']}")


@needs_piper
def test_text_loeschen_loescht_sein_audio(api, voice):
    """Wunsch: Text aus der Bibliothek löschen → auch seine Aufnahmen weg."""
    _, a = api.json("POST", "/api/docs", {"text": "Wird gleich gelöscht.", "title": "A", "voice": voice})
    _fake_audio("Wird gleich gelöscht.", voice)
    _fake_audio("Bleibt im Cache.", voice)
    s, r = api.json("DELETE", f"/api/docs/{a['id']}")
    assert s == 200 and r["freed"] > 0
    assert not tts.cache_path("Wird gleich gelöscht.", voice).exists()
    assert tts.cache_path("Bleibt im Cache.", voice).exists()


@needs_piper
def test_reste_und_hoerproben_getrennt_loeschen(api, voice):
    _fake_audio(tts.PREVIEW_TEXT["de"], voice)
    _fake_audio("Verwaister Satz.", voice)
    api.json("DELETE", "/api/storage/other")
    assert not tts.cache_path("Verwaister Satz.", voice).exists()
    assert tts.cache_path(tts.PREVIEW_TEXT["de"], voice).exists()
    api.json("DELETE", "/api/storage/previews")
    assert not tts.cache_path(tts.PREVIEW_TEXT["de"], voice).exists()


def test_exporte_loeschen(api):
    p = paths.DATA_DIR / "exports" / ("a" * 32 + ".mp3")
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(b"\0" * 1234)
    s, r = api.json("DELETE", "/api/storage/exports")
    assert s == 200 and r["freed"] >= 1234 and not p.exists()


def test_whisper_in_entwicklung_nicht_loeschbar(api):
    assert api.call("DELETE", "/api/storage/whisper")[0] == 400
    assert api.json("GET", "/api/storage")[1]["whisper"]["removable"] is False


def test_unbekannte_kategorie_404(api):
    assert api.call("DELETE", "/api/storage/alles")[0] == 404
