"""Fehlerbehandlung: verständliche, übersetzte Meldungen statt Rohtexten – und nichts bleibt still hängen."""
import errno
import json
import re
import socket
import sys
import urllib.error
from pathlib import Path

import pytest

import meldungen
import paths
import server
import tts

ROOT = paths.APP_DIR
I18N = (ROOT / "static" / "i18n.js").read_text("utf-8")
BACKEND = ["server.py", "tts.py", "exporter.py", "importers.py", "stt.py", "clone_setup.py", "storage.py",
           "uninstaller.py", "meldungen.py", "updater.py", "settings.py", "desktop.py"]
# Meldungen an die Oberfläche: raise …("…"), Konstanten (GROSS = "…"), self.error(…, "…"), Gründe (return False, "…")
_MSG = re.compile(r'''(?:raise\s+(?:ValueError|ImportFailed|Meldung|meldungen\.Meldung|_NoUpdate)\(|^\s*[A-Z_]{3,}\s*=\s*\(?|'''
                  r'''self\.error\(\d+,\s*|return False, |"(?:python|packages|model)":\s*)'''
                  r'''("(?:[^"\\]|\\.)+"(?:\s*\n?\s*"(?:[^"\\]|\\.)+")*)''', re.M)


def _backend_meldungen():
    out = {}
    for f in BACKEND:
        for m in _MSG.finditer((ROOT / f).read_text("utf-8")):
            txt = "".join(re.findall(r'"((?:[^"\\]|\\.)*)"', m.group(1)))
            if "{" not in txt and re.search(r"[äöüß]|\b(der|die|das|nicht|ist|bitte|keine?)\b", txt, re.I):
                out[txt] = f
    return out


def test_backend_meldungen_sind_uebersetzt():
    """Jede deutsche Meldung, die das Backend an die Oberfläche gibt, braucht einen Eintrag in static/i18n.js."""
    found = _backend_meldungen()
    assert len(found) > 30                               # der Scanner findet überhaupt etwas
    fehlt = [f"{f}: {t}" for t, f in found.items() if json.dumps(t, ensure_ascii=False) + ":" not in I18N]
    assert not fehlt, "in static/i18n.js eintragen:\n" + "\n".join(fehlt)


def test_feste_meldungen_sind_uebersetzt():
    for m in meldungen.ALLE:
        assert json.dumps(m, ensure_ascii=False) + ":" in I18N, m


@pytest.mark.parametrize("err, want", [
    (OSError(errno.ENOSPC, "No space left on device"), meldungen.PLATTE),
    (PermissionError(errno.EACCES, "denied"), meldungen.RECHTE),
    (urllib.error.URLError(socket.gaierror(8, "x")), meldungen.OFFLINE),
    (meldungen.FFmpegFehler("ffmpeg: [mp3 @ 0x1] broken"), meldungen.AUDIO),
    (AttributeError("'list' object has no attribute 'get'"), meldungen.INTERN),
    (KeyError("Stimme"), meldungen.NICHT_GEFUNDEN),
    (json.JSONDecodeError("Expecting value", "", 0), meldungen.ANFRAGE),
    (ValueError("invalid literal for int() with base 10: 'x'"), meldungen.ANFRAGE),
    (ValueError("Der Text ist leer"), "Der Text ist leer"),
    (meldungen.Meldung("Die eigene Stimme wurde nicht gefunden"), "Die eigene Stimme wurde nicht gefunden"),
])
def test_fuer_nutzer(err, want):
    assert meldungen.fuer_nutzer(err) == want


def test_kaputte_text_datei_versteckt_nicht_die_bibliothek(api):
    status, d = api.json("POST", "/api/docs", {"title": "Heil", "text": "Ein ganz normaler Satz zum Vorlesen."})
    assert status in (200, 201)
    broken = server.DOCS_DIR / "kaputt0000.json"
    broken.write_text("", "utf-8")                       # z. B. nach Stromausfall
    try:
        status, lib = api.json("GET", "/api/docs")
        assert status == 200 and any(x["title"] == "Heil" for x in lib["docs"])
    finally:
        broken.unlink()
        api.json("DELETE", f"/api/docs/{d['id']}")


def test_ungueltiger_body_ergibt_feste_meldung(api):
    status, d = api.json("PATCH", "/api/settings", raw=b"{kaputt")
    assert status == 400 and d["error"] == meldungen.ANFRAGE
    status, d = api.json("PATCH", "/api/settings", raw=b"[1, 2]")
    assert status == 400 and d["error"] == meldungen.ANFRAGE


def test_interner_fehler_ohne_rohtext_aber_mit_traceback(api, monkeypatch, capfd):
    def kaputt(self):
        raise AttributeError("'list' object has no attribute 'get'")
    monkeypatch.setattr(server.Handler, "bugreport_info", kaputt)
    monkeypatch.setattr(server, "ROUTES", [(p, m, kaputt if f.__name__ == "bugreport_info" else f) for p, m, f in server.ROUTES])
    status, d = api.json("GET", "/api/bugreport")
    assert status == 500 and d["error"] == meldungen.INTERN
    assert "Traceback" in capfd.readouterr().err         # → landet in der App im server.log


def test_fehler_der_oberflaeche_landen_im_log(api, capfd):
    status, _ = api.json("POST", "/api/client-error", {"msg": "TypeError: x is null", "stack": "at foo (basis.js:1)"})
    assert status == 200
    assert "[oberfläche] TypeError: x is null" in capfd.readouterr().out


def test_start_laeuft_weiter_wenn_ein_schritt_scheitert(monkeypatch):
    calls = []
    monkeypatch.setattr(tts, "refresh_edge_voices", lambda: calls.append("edge"))
    monkeypatch.setattr(tts, "warm_up", lambda: (_ for _ in ()).throw(OSError(errno.ENOSPC, "voll")))
    monkeypatch.setattr(server.updater, "start_background", lambda: calls.append("updater"))
    for name in ("prune_cache", "fix_webm_durations", "warm_previews"):
        monkeypatch.setattr(tts, name, lambda: None)
    server.startup()
    assert calls == ["edge", "updater"]                  # Updater startet trotz Fehler davor


def test_klon_worker_haengt_wird_beendet(monkeypatch, tmp_path):
    """Antwortet der Worker nicht, kommt nach dem Zeitlimit eine Meldung – statt alles zu blockieren."""
    w = tts._CloneWorker()
    hang = tmp_path / "hang.py"
    hang.write_text("import sys, time\nprint('{\"ready\": true}', flush=True)\nsys.stdin.readline()\ntime.sleep(60)\n")
    monkeypatch.setattr(tts, "CLONE_PY", Path(sys.executable))
    monkeypatch.setattr(paths, "CLONE_WORKER", hang)
    monkeypatch.setattr(paths, "clone_env", lambda: None)
    monkeypatch.setattr(tts, "CLONE_TIMEOUT", 1)
    with pytest.raises(meldungen.Meldung) as e:
        w.synth("Hallo", "de", tmp_path / "ref.wav")
    assert str(e.value) == tts.CLONE_HAENGT and w.proc is None


def test_utf16_text_wird_gelesen():
    import importers
    assert importers._decode("Grüße aus Wien".encode("utf-16")) == "Grüße aus Wien"
    assert importers._decode("Grüße aus Wien".encode("utf-16-le")) == "Grüße aus Wien"


def test_export_ueberbrueckt_aussetzer_ohne_ersatzstimme(monkeypatch):
    import exporter
    monkeypatch.setattr(exporter, "RETRY_WAIT", (0, 0, 0))
    calls = []

    def synth(text, voice, lang, fallback=True, low=False, doc_id=None):
        calls.append(fallback)
        if len(calls) < 3:
            raise meldungen.Meldung(tts.EDGE_WEG)
        return b"audio", "audio/mpeg", voice
    monkeypatch.setattr(tts, "synthesize", synth)
    doc = {"chunks": [{"text": "Hallo"}], "voice": "edge:de-DE-KatjaNeural", "lang": "de"}
    assert exporter.synth_strict(doc, 0) == b"audio"
    assert calls == [False, False, False]                # nie mit Ersatzstimme

    calls.clear()
    monkeypatch.setattr(tts, "synthesize", lambda *a, **k: (_ for _ in ()).throw(meldungen.Meldung(tts.CLONE_SPEICHER)))
    with pytest.raises(meldungen.Meldung):                # andere Fehler: sofort, ohne Warten
        exporter.synth_strict(doc, 0)


def test_export_nichts_vorlesbar_bricht_nicht_ab(monkeypatch):
    """„* * *“: Edge liefert kein Audio → diese Stelle wie beim Vorlesen überbrücken, nicht den Export abbrechen."""
    import exporter
    calls = []

    def synth(text, voice, lang, fallback=True, low=False, doc_id=None):
        calls.append(fallback)
        if not fallback:
            raise meldungen.Meldung(tts.NICHTS_VORLESBAR)
        return b"ersatz", "audio/webm", "piper:x"
    monkeypatch.setattr(tts, "synthesize", synth)
    doc = {"chunks": [{"text": "* * *"}], "voice": "edge:de-DE-KatjaNeural", "lang": "de"}
    assert exporter.synth_strict(doc, 0) == b"ersatz" and calls == [False, True]


def test_export_abbrechen_beendet_das_warten(monkeypatch):
    import time as _t
    import exporter
    monkeypatch.setattr(exporter, "RETRY_WAIT", (60, 60, 60))
    monkeypatch.setattr(tts, "synthesize", lambda *a, **k: (_ for _ in ()).throw(meldungen.Meldung(tts.EDGE_WEG)))
    doc = {"chunks": [{"text": "Hallo"}], "voice": "edge:de-DE-KatjaNeural", "lang": "de"}
    t0 = _t.time()
    with pytest.raises(InterruptedError):
        exporter.synth_strict(doc, 0, stop=lambda: _t.time() - t0 > 0.3)
    assert _t.time() - t0 < 2


def test_geloeschte_stimme_ohne_stille_ersatzstimme():
    with pytest.raises(meldungen.Meldung) as e:
        tts.synthesize("Ein Satz, der noch nicht im Cache liegt 4711.", "piper:gibt-es-nicht", "de", fallback=False)
    assert str(e.value) == tts.STIMME_FEHLT


def _wav(secs: float) -> bytes:
    import io, wave
    b = io.BytesIO()
    with wave.open(b, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(24000)
        w.writeframes(b"\0\0" * int(24000 * secs))
    return b.getvalue()


def test_eigene_stimme_bricht_ab_wird_nachgeholt(monkeypatch, tmp_path):
    """Chatterbox bricht manchmal mitten im Satz ab (Hör-Plan, Frage 18: 18 Wörter in 3,3 s) → neu erzeugen,
    notfalls Satz für Satz – statt dass Text fehlt und die Markierung drüberrast."""
    text = "Frage 18: Welche Klänge möchtest du? Mein Vorschlag sind diese fünf: Regen, Kaminfeuer, Café, Wald und sanftes Rauschen."
    calls = []

    def synth(t, lang, ref, low=False):
        calls.append(t)
        return _wav(3.3) if t == text else _wav(len(t.split()) / 2.3)   # ganzer Text: immer abgebrochen
    monkeypatch.setattr(tts, "CLONE_DIR", tmp_path)
    (tmp_path / "ich").mkdir(); (tmp_path / "ich" / "sample.wav").write_bytes(b"x")
    monkeypatch.setattr(tts._clone_worker, "synth", synth)
    monkeypatch.setattr(tts, "to_opus", lambda wav: wav)
    out = tts._synth_clone(text, "ich", "de")
    assert calls[:2] == [text, text] and len(calls) == 4          # 2 Versuche, dann die 2 Sätze einzeln
    assert tts._wav_secs(out) > 7                                  # vollständig (≈ 18 Wörter / 2,3 + Pause)


def test_eigene_stimme_normales_tempo_bleibt():
    assert not tts._clone_too_short("Ein ganz normaler Satz mit acht Wörtern drin.", _wav(3.2))
    assert not tts._clone_too_short("Kurz.", _wav(0.2))             # kurze Texte schwanken – nie nachholen
