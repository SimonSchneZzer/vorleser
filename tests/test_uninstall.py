"""Deinstallieren: nur in der App, „behalten“ schont data/, Helfer löscht genau das Richtige."""
import time
from pathlib import Path

import pytest

import paths
import uninstaller
import updater


def test_in_entwicklung_nicht_moeglich(api):
    s, info = api.json("GET", "/api/uninstall")
    assert s == 200 and info["possible"] is False and info["reason"]
    assert api.call("POST", "/api/uninstall", {"keepData": False})[0] == 400


@pytest.fixture
def fake_app(monkeypatch, tmp_path):
    """So tun, als liefe eine installierte Mac-App aus tmp/Apps mit Datenordner tmp/home."""
    home = tmp_path / "home"
    for d in ("data/docs", "cache", "clone-env", "webview"):
        (home / d).mkdir(parents=True)
    (home / "data" / "docs" / "x.json").write_text("{}")
    app = tmp_path / "Apps" / "Vorleser.app"
    app.mkdir(parents=True)
    monkeypatch.setattr(paths, "FROZEN", True)
    monkeypatch.setattr(paths, "IS_MAC", True)
    monkeypatch.setattr(paths, "IS_WIN", False)
    monkeypatch.setattr(paths, "USER_DIR", home)
    monkeypatch.setattr(updater, "_app_path", lambda: app)
    monkeypatch.setenv("TMPDIR", str(tmp_path))
    calls = []
    monkeypatch.setattr(uninstaller.subprocess, "Popen", lambda args, **kw: calls.append(args))
    return home, app, calls, tmp_path


def test_behalten_schont_nur_data(fake_app):
    home, *_ = fake_app
    names = sorted(p.name for p in uninstaller._targets(keep_data=True))
    assert names == ["cache", "clone-env", "webview"]               # data/ bleibt
    assert uninstaller._targets(keep_data=False) == [home]            # sonst alles


@pytest.mark.parametrize("keep", [False, True])
def test_mac_helfer_loescht_genau_das_richtige(fake_app, keep):
    home, app, calls, tmp = fake_app
    quit_calls = []
    uninstaller.launch(keep, lambda: quit_calls.append(True))
    script = (tmp / "vorleser-uninstall.sh").read_text()
    rm_line = next(l for l in script.splitlines() if l.startswith("rm -rf"))
    assert str(app) in rm_line                                        # App weg
    assert str(Path.home() / "Library" / "WebKit" / uninstaller.BUNDLE_ID) in rm_line   # Webview-Daten weg
    if keep:
        assert str(home / "cache") in rm_line and str(home / "data") not in rm_line
    else:
        assert f"'{home}'" in rm_line
    assert "kill -0" in script                                        # wartet, bis die App beendet ist
    assert calls and calls[0][0] == "/bin/bash"
    time.sleep(1.4)
    assert quit_calls == [True]                                       # App beendet sich selbst
