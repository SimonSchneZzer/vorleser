"""Updates automatisch laden (3.2): still im Hintergrund, Karte erst bei „ready“, aufgeben nach Fehlschlägen."""
import threading
import time

import pytest

import paths
import settings
import updater


@pytest.fixture
def auto(monkeypatch):
    """Updater ohne Netz: install-fähig, eine neuere Version bekannt, _prepare simuliert."""
    calls = []
    outcome = {"ok": True}
    done = threading.Event()

    def fake_prepare():
        calls.append(updater._latest["version"])
        with updater._lock:
            if outcome["ok"]:
                updater._ready = {"version": updater._latest["version"], "installer": None}
                updater._state.update(state="ready")
            else:
                updater._state.update(state="error", error="x")
        done.set()

    monkeypatch.setattr(updater, "can_install", lambda: (True, ""))
    monkeypatch.setattr(updater, "_prepare", fake_prepare)
    monkeypatch.setattr(updater, "_latest", {"version": "99.0.0", "url": "x", "size": 1, "notes": "Neu.\n\n- mehr"})
    monkeypatch.setattr(updater, "_ready", None)
    monkeypatch.setattr(updater, "_state", {"state": "idle"})
    monkeypatch.setattr(updater, "_auto", {"version": None, "fails": 0, "next": 0.0})
    settings.update({"autoUpdate": True})

    def step():
        done.clear()
        updater.auto_step()
        done.wait(2)
        time.sleep(0.05)                                     # Nachlauf im Thread (Fehler zählen)
    yield calls, outcome, step
    settings.update({"autoUpdate": True})


def test_laedt_still_und_ist_dann_bereit(auto):
    calls, _, step = auto
    step()
    s = updater.status()
    assert calls == ["99.0.0"] and s["state"] == "ready" and s["readyVersion"] == "99.0.0"
    step()                                                   # schon bereit → nicht nochmal laden
    assert calls == ["99.0.0"]


def test_nicht_wenn_ausgeschaltet_oder_aktuell(auto, monkeypatch):
    calls, _, step = auto
    settings.update({"autoUpdate": False})
    step()
    assert calls == [] and updater.status()["state"] == "idle"
    settings.update({"autoUpdate": True})
    monkeypatch.setattr(updater, "_latest", {"version": paths.APP_VERSION, "url": "x", "size": 1, "notes": ""})
    step()
    assert calls == []


def test_fehlschlaege_still_dann_aufgeben(auto, monkeypatch):
    calls, outcome, step = auto
    outcome["ok"] = False
    for n in range(updater.AUTO_GIVE_UP):
        updater._auto["next"] = 0.0                          # Wartezeit überspringen
        step()
        s = updater.status()
        assert s["state"] == "idle"                          # still: keine Fehlerkarte
        assert s["autoFailed"] == (n + 1 >= updater.AUTO_GIVE_UP)
    assert len(calls) == updater.AUTO_GIVE_UP
    updater._auto["next"] = 0.0
    step()
    assert len(calls) == updater.AUTO_GIVE_UP                # aufgegeben → Karte „Aktualisieren“ übernimmt


def test_wartet_nach_fehlschlag(auto):
    calls, outcome, step = auto
    outcome["ok"] = False
    step()
    step()                                                   # gleich danach: noch in der Wartezeit
    assert len(calls) == 1 and updater._auto["next"] > time.time() + 500


def test_neuere_version_ersetzt_bereitliegende(auto, monkeypatch):
    calls, _, step = auto
    step()
    monkeypatch.setattr(updater, "_latest", {"version": "99.1.0", "url": "x", "size": 1, "notes": ""})
    step()
    assert calls == ["99.0.0", "99.1.0"] and updater.status()["readyVersion"] == "99.1.0"


def test_einstellung_auto_update():
    assert settings.load()["autoUpdate"] is True
    assert settings.update({"autoUpdate": "ja"})["autoUpdate"] is True     # ungültig → bleibt
    assert settings.update({"autoUpdate": False})["autoUpdate"] is False
    settings.update({"autoUpdate": True})
