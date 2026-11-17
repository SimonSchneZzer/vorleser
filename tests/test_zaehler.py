"""Anonymes Mitzählen (zaehler.py, 3.3): höchstens 1×/Woche „aktiv“, 1× „neu“, abschaltbar, nie ohne URL."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

import paths
import settings
import zaehler


@pytest.fixture
def z(monkeypatch):
    sent = []
    monkeypatch.setattr(zaehler, "URL", "http://127.0.0.1:9/count")
    monkeypatch.setattr(zaehler, "_send", lambda p: sent.append(p) or True)
    zaehler.STATE.unlink(missing_ok=True)
    settings.update({"count": True})
    yield sent
    zaehler.STATE.unlink(missing_ok=True)
    settings.update({"count": True})


def test_neu_und_aktiv_einmal(z):
    assert zaehler.step() == [f"/app/neu/{zaehler.SYSTEM}", f"/app/aktiv/{zaehler.SYSTEM}/{paths.APP_VERSION}"]
    assert zaehler.step() == []                     # gleiche Woche: nichts mehr


def test_neue_woche_meldet_wieder(z, monkeypatch):
    zaehler.step()
    monkeypatch.setattr(zaehler, "week", lambda now=None: "2099-W01")
    assert zaehler.step() == [f"/app/aktiv/{zaehler.SYSTEM}/{paths.APP_VERSION}"]


def test_abgeschaltet_sendet_nichts(z):
    settings.update({"count": False})
    assert zaehler.step() == [] and z == []


def test_ohne_url_nie(z, monkeypatch):
    monkeypatch.setattr(zaehler, "URL", "")
    assert zaehler.step() == [] and z == []


def test_offline_versucht_spaeter_erneut(z, monkeypatch):
    monkeypatch.setattr(zaehler, "_send", lambda p: False)
    assert zaehler.step() == []
    monkeypatch.setattr(zaehler, "_send", lambda p: z.append(p) or True)
    assert len(zaehler.step()) == 2


def test_alte_installation_zaehlt_nicht_als_neu(z, monkeypatch):
    (paths.DATA_DIR / "last-version").write_text("3.2.1", "utf-8")
    monkeypatch.setattr(zaehler.threading, "Thread", lambda **k: type("T", (), {"start": lambda self: None})())
    zaehler.start_background()
    assert zaehler.step() == [f"/app/aktiv/{zaehler.SYSTEM}/{paths.APP_VERSION}"]


def test_frisch_offline_bleibt_neu(z, monkeypatch):
    (paths.DATA_DIR / "last-version").unlink(missing_ok=True)
    monkeypatch.setattr(zaehler.threading, "Thread", lambda **k: type("T", (), {"start": lambda self: None})())
    zaehler.start_background()                      # erster Start, noch ohne last-version
    (paths.DATA_DIR / "last-version").write_text(paths.APP_VERSION, "utf-8")   # Updater schreibt sie danach
    zaehler.start_background()                      # zweiter Start: Statusdatei gibt es schon → bleibt „neu“
    assert f"/app/neu/{zaehler.SYSTEM}" in zaehler.step()


def test_woche_iso():
    assert zaehler.week(datetime(2026, 11, 17, tzinfo=timezone.utc)) == "2026-W47"
    assert zaehler.week(datetime(2027, 1, 1, tzinfo=timezone.utc)) == "2026-W53"


def test_kein_netz_in_tests():
    assert zaehler.URL == ""
