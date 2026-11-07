"""HTTP-API gegen einen echten Server (Wegwerf-Datenordner)."""
import pathlib
import time
from urllib.parse import quote

import pytest

import tts
from conftest import ffprobe_duration, needs_piper

TEXT = "# Anfang\n\nDer alte Wärter stieg die Treppe hinauf. Es war kalt.\n\n# Weiter\n\nUnten schlugen die Wellen an den Fels."


def test_startseite_und_dateien(api):
    status, headers, body = api.call("GET", "/")
    assert status == 200 and b"<html" in body.lower()
    for name in ("app.css", "i18n.js", "js/basis.js", "js/verwaltung.js"):
        assert api.call("GET", f"/{name}")[0] == 200
    for name in ("app.js", "js/../server.py", "js/basis.py"):
        assert api.call("GET", f"/{name}")[0] == 404


def test_api_ohne_schluessel_gesperrt(api):
    """Fremde Webseiten können 127.0.0.1 erreichen – ohne Schlüssel darf /api/* nichts tun."""
    assert api.call("GET", "/api/settings", auth=False)[0] == 403
    assert api.call("POST", "/api/quit", raw=b"{}", auth=False, headers={"Content-Type": "text/plain"})[0] == 403
    assert api.call("POST", "/api/uninstall", {"keepData": True}, auth=False)[0] == 403
    assert api.call("GET", "/api/settings", headers={"X-Vorleser-Token": "falsch"}, auth=False)[0] == 403
    assert api.call("GET", "/api/settings", headers={"X-Vorleser-Token": "ä"}, auth=False)[0] == 403
    assert not api.quit_calls


def test_api_fremde_herkunft_gesperrt(api):
    port = api.base.rsplit(":", 1)[1]
    assert api.call("POST", "/api/quit", {}, headers={"Origin": "https://evil.example"})[0] == 403
    assert api.call("GET", "/api/settings", headers={"Origin": "null"})[0] == 403
    assert api.call("GET", "/", headers={"Host": f"evil.example:{port}"})[0] == 403   # DNS-Rebinding
    assert api.call("GET", "/api/settings", headers={"Origin": f"http://localhost:{port}"})[0] == 200
    assert not api.quit_calls


def test_startseite_setzt_schluessel_als_cookie(api):
    import server
    status, headers, _ = api.call("GET", "/", auth=False)
    cookie = headers["Set-Cookie"]
    assert status == 200 and server.TOKEN in cookie and "SameSite=Strict" in cookie and "HttpOnly" in cookie
    pair = cookie.split(";", 1)[0]
    assert api.call("GET", "/api/settings", headers={"Cookie": pair}, auth=False)[0] == 200
    assert api.call("GET", "/api/settings", headers={"Cookie": pair.split("=")[0] + "=x"}, auth=False)[0] == 403
    assert server.TOKEN_FILE.read_text("utf-8") == server.TOKEN


def test_unbekannte_route_404(api):
    assert api.call("GET", "/api/gibtsnicht")[0] == 404
    assert api.call("GET", "/api/docs/" + "0" * 32)[0] == 404
    assert api.call("GET", "/api/docs/../../etc/passwd")[0] == 404


def test_einstellungen(api):
    s, body = api.json("PATCH", "/api/settings", {"mark": "sentence"})
    assert s == 200 and body["mark"] == "sentence"
    assert api.json("GET", "/api/settings")[1]["mark"] == "sentence"
    api.json("PATCH", "/api/settings", {"mark": "word"})


def test_stimmen_und_features(api):
    s, body = api.json("GET", "/api/voices")
    assert s == 200 and set(body["langs"]) == {"de", "en"}
    assert {"dictate", "clone", "cloneSetup", "desktop"} <= body["features"].keys()


def test_spracherkennung(api):
    assert api.json("POST", "/api/detect", {"text": "The house is big and the dog is old."})[1]["lang"] == "en"


def test_import(api):
    s, body = api.json("POST", "/api/import", raw="# Hallo\n\nDas ist ein Test.".encode(),
                       headers={"X-Filename": quote("Mein Text.md")})
    assert s == 200 and body["title"] == "Mein Text" and body["lang"] == "de"
    assert api.call("POST", "/api/import", raw=b"x", headers={"X-Filename": "a.png"})[0] == 400


@pytest.fixture
def doc(api):
    s, d = api.json("POST", "/api/docs", {"text": TEXT, "title": "Testtext"})
    assert s == 201, d
    yield d
    api.call("DELETE", f"/api/docs/{d['id']}")


def test_leerer_text_abgelehnt(api):
    assert api.call("POST", "/api/docs", {"text": "  "})[0] == 400


def test_dokument_lebenszyklus(api, doc):
    assert doc["title"] == "Testtext" and doc["chapters"] == 2
    ids = [d["id"] for d in api.json("GET", "/api/docs")[1]["docs"]]
    assert doc["id"] in ids
    full = api.json("GET", f"/api/docs/{doc['id']}")[1]
    assert full["chunks"][0] == {"text": "Anfang", "par": True, "h": True}
    s, upd = api.json("PATCH", f"/api/docs/{doc['id']}", {"progress": {"chunk": 99, "offset": 1.5}, "title": "Neu"})
    assert upd["title"] == "Neu" and upd["progress"]["chunk"] == upd["count"] - 1   # auf gültigen Bereich begrenzt


def test_text_bearbeiten_behaelt_lesezeichen(api, doc):
    full = api.json("GET", f"/api/docs/{doc['id']}")[1]
    i = next(k for k, c in enumerate(full["chunks"]) if c["text"].startswith("Unten"))
    api.json("PATCH", f"/api/docs/{doc['id']}", {"progress": {"chunk": i, "offset": 2.0}})
    text = api.json("GET", f"/api/docs/{doc['id']}/text")[1]["text"]
    assert text.startswith("# Anfang")
    neu = text.replace("Es war kalt.", "Es war sehr kalt. Der Wind heulte.")
    s, res = api.json("PUT", f"/api/docs/{doc['id']}/text", {"text": neu})
    assert s == 200
    after = api.json("GET", f"/api/docs/{doc['id']}")[1]
    assert after["chunks"][after["progress"]["chunk"]]["text"].startswith("Unten")   # gleiche Stelle
    assert after["progress"]["offset"] == 2.0


def test_loeschen(api):
    d = api.json("POST", "/api/docs", {"text": "Kurz."})[1]
    assert api.json("DELETE", f"/api/docs/{d['id']}")[1]["ok"] is True
    assert api.call("GET", f"/api/docs/{d['id']}")[0] == 404


@needs_piper
def test_audio_abschnitt_mit_dauer(api, doc):
    if not doc_voice(api, doc).startswith("piper:"):
        pytest.skip("Testserver ohne Piper-Standardstimme")
    s, headers, body = api.call("GET", f"/api/docs/{doc['id']}/audio/1")
    assert s == 200 and headers["Content-Type"] == "audio/webm"
    assert ffprobe_duration(body) > 0.5                          # Regression „Markierung läuft davon“
    assert api.call("GET", f"/api/docs/{doc['id']}/audio/99")[0] == 404


def doc_voice(api, doc):
    return api.json("GET", f"/api/docs/{doc['id']}")[1]["voice"]


@needs_piper
@pytest.mark.parametrize("fmt", ["mp3", "wav"])
def test_export(api, doc, fmt):
    assert api.json("POST", f"/api/docs/{doc['id']}/export", {"format": fmt})[0] == 200
    for _ in range(120):
        st = api.json("GET", f"/api/docs/{doc['id']}/export")[1]
        if st["status"] != "running":
            break
        time.sleep(0.5)
    assert st["status"] == "ready", st
    s, headers, body = api.call("GET", f"/api/docs/{doc['id']}/export/file")
    assert s == 200 and len(body) > 1000
    assert f".{fmt}" in headers["Content-Disposition"]
    assert ffprobe_duration(body) > 1


def test_export_falsches_format(api, doc):
    assert api.call("POST", f"/api/docs/{doc['id']}/export", {"format": "ogg"})[0] == 400


def test_cache_info_und_leeren(api):
    s, c = api.json("GET", "/api/cache")
    assert s == 200 and {"bytes", "files", "limit"} <= c.keys()
    assert api.json("DELETE", "/api/cache")[1]["files"] == 0


def test_klon_setup_status(api):
    s, body = api.json("GET", "/api/clone-setup")
    assert s == 200 and "installed" in body


def test_update_status(api):
    s, body = api.json("GET", "/api/update")
    assert s == 200 and body["current"] and body["enabled"] is False   # Entwicklung: kein Updater


def test_update_installieren_in_entwicklung_abgelehnt(api):
    assert api.call("POST", "/api/update/install")[0] == 400


def test_beenden_ruft_on_quit(api):
    api.quit_calls.clear()
    assert api.json("POST", "/api/quit")[1] == {"ok": True}
    time.sleep(0.6)
    assert api.quit_calls == [True]


@pytest.mark.online
def test_edge_stimme_online():
    tts.refresh_edge_voices()
    vid = "edge:de-DE-KatjaNeural"
    data, mime, used = tts.synthesize("Hallo aus dem Netz.", vid, "de", fallback=False)
    assert mime == "audio/mpeg" and used == vid and len(data) > 1000
    assert tts.get_marks("Hallo aus dem Netz.", vid, compute=False)


@needs_piper
def test_vorbereitet_ist_eine_wahrheit(api, doc):
    """Regression: Knopf „Alles vorbereitet“, Statuszeile „3 vorbereitet“ und Balken zeigten Verschiedenes.
    Der Status meldet jetzt live, was im Cache liegt – pro Abschnitt."""
    s, p = api.json("GET", f"/api/docs/{doc['id']}/prepare")
    assert s == 200 and p["total"] == doc["count"] and len(p["cached"]) == p["total"]
    api.call("GET", f"/api/docs/{doc['id']}/audio/1")                 # ein Abschnitt erzeugt …
    p2 = api.json("GET", f"/api/docs/{doc['id']}/prepare")[1]
    assert p2["cached"][1] is True and p2["done"] == p["done"] + (0 if p["cached"][1] else 1)
    api.json("POST", f"/api/docs/{doc['id']}/prepare")                # … dann alles im Hintergrund
    for _ in range(120):
        p3 = api.json("GET", f"/api/docs/{doc['id']}/prepare")[1]
        if p3["status"] != "running":
            break
        assert any(j["doc"] == doc["id"] for j in api.json("GET", "/api/jobs")[1]["jobs"])   # sichtbar als Auftrag
        time.sleep(0.3)
    assert p3["status"] == "ready" and p3["done"] == p3["total"] and all(p3["cached"])
    assert not any(j["doc"] == doc["id"] for j in api.json("GET", "/api/jobs")[1]["jobs"])


def test_changelog_fuer_was_ist_neu(api):
    """„Was ist neu“ liest CHANGELOG.md: jede Version mit Kurzfassung, neueste zuerst, aktuelle Version enthalten."""
    s, body = api.json("GET", "/api/changelog")
    assert s == 200
    rel = body["releases"]
    assert rel and all(r["lead"] for r in rel), "jeder Abschnitt braucht eine erste Zeile (Text der Update-Karte)"
    vers = [tuple(map(int, r["version"].split("."))) for r in rel]
    assert vers == sorted(vers, reverse=True)
    assert (pathlib.Path(__file__).resolve().parents[1] / "VERSION").read_text().strip() == rel[0]["version"]


def test_changelog_parser(tmp_path):
    import server
    p = tmp_path / "CHANGELOG.md"
    p.write_text("# Änderungen\n\nText oben.\n\n## 1.1\nKurz.\n\n- **A:** eins\n  weiter\n- zwei\n\n## 1.0\nErste.\n", "utf-8")
    assert server.parse_changelog(p) == [
        {"version": "1.1", "lead": "Kurz.", "items": ["**A:** eins weiter", "zwei"]},
        {"version": "1.0", "lead": "Erste.", "items": []}]
    assert server.parse_changelog(tmp_path / "fehlt.md") == []
