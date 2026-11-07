"""Stimmklon-Installer und Updater (ohne echte Downloads)."""
import json
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

import clone_setup
import paths
import updater


# --------------------------------------------------------------------------- #
# Stimmklon nachinstallieren
# --------------------------------------------------------------------------- #
def test_klon_nicht_installiert_ohne_umgebung():
    assert not clone_setup.installed()


def test_klon_mit_marker_installiert(monkeypatch, tmp_path):
    env = tmp_path / "env"
    py = env / ("Scripts/python.exe" if paths.IS_WIN else "bin/python")
    py.parent.mkdir(parents=True)
    py.write_text("")
    monkeypatch.setattr(clone_setup, "CLONE_ENV", env)
    monkeypatch.setattr(clone_setup, "CLONE_PY", py)
    monkeypatch.setattr(clone_setup, "MARKER", env / "vorleser-ok")
    assert not clone_setup.installed()
    (env / "vorleser-ok").write_text("x")
    assert clone_setup.installed()


def test_klon_ohne_uv_nicht_moeglich(monkeypatch):
    monkeypatch.setattr(clone_setup, "_uv", lambda: None)
    assert not clone_setup.supported()
    with pytest.raises(ValueError):
        clone_setup.start()


def test_klon_status_form():
    s = clone_setup.status()
    assert {"status", "installed", "supported"} <= s.keys()


# --------------------------------------------------------------------------- #
# Updater
# --------------------------------------------------------------------------- #
def test_versionen_vergleichen():
    assert updater._ver("2.0.10") > updater._ver("2.0.9")
    assert updater._ver("v2.1.0") > updater._ver("2.0.99")
    assert updater._ver("2.0.0") == updater._ver("v2.0.0")
    assert updater._ver("") == (0,)


def test_entwicklung_installiert_nicht():
    ok, why = updater.can_install()
    assert not ok and why


class _Release(BaseHTTPRequestHandler):
    body = {}

    def do_GET(self):
        data = json.dumps(self.body).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *a):
        pass


@pytest.fixture
def release_server(monkeypatch):
    srv = ThreadingHTTPServer(("127.0.0.1", 0), _Release)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    monkeypatch.setattr(updater, "API_URL", f"http://127.0.0.1:{srv.server_address[1]}/latest")
    monkeypatch.setattr(updater, "LATEST_PAGE", "http://127.0.0.1:9/releases/latest")   # Tests nie ins Netz
    monkeypatch.setattr(updater, "JSON_URL", "http://127.0.0.1:9/latest.json")           # → Ausweichweg API
    monkeypatch.setattr(updater, "ASSET", "Vorleser-mac.dmg")
    monkeypatch.setattr(updater, "_latest", None)
    monkeypatch.setattr(updater, "_checked", 0.0)
    monkeypatch.setattr(updater, "_api_tried", 0.0)
    _Release.port = srv.server_address[1]
    yield _Release
    srv.shutdown()


def _rel(tag, name="Vorleser-mac.dmg", **kw):
    return {"tag_name": tag, "draft": False, "prerelease": False, "body": "Neu: Dinge.\nhttps://x", "html_url": "https://x",
            "assets": [{"name": name, "browser_download_url": "http://dl/" + name, "size": 123}], **kw}


def test_neue_version_erkannt(release_server, monkeypatch):
    monkeypatch.setattr(paths, "APP_VERSION", "1.0.0")
    release_server.body = _rel("v1.2.0")
    latest = updater.check(force=True)
    assert latest["version"] == "1.2.0" and latest["size"] == 123
    s = updater.status()
    assert s["available"] and s["latest"] == "1.2.0" and s["notes"].startswith("Neu: Dinge.")


def test_gleiche_version_kein_update(release_server, monkeypatch):
    monkeypatch.setattr(paths, "APP_VERSION", "1.2.0")
    release_server.body = _rel("v1.2.0")
    updater.check(force=True)
    assert not updater.status()["available"]


@pytest.mark.parametrize("extra", [{"draft": True}, {"prerelease": True}])
def test_entwurf_und_vorabversion_ignoriert(release_server, monkeypatch, extra):
    monkeypatch.setattr(paths, "APP_VERSION", "1.0.0")
    release_server.body = _rel("v9.0.0", **extra)
    assert updater.check(force=True) is None


def test_fehlende_datei_fuer_system_ignoriert(release_server, monkeypatch):
    monkeypatch.setattr(paths, "APP_VERSION", "1.0.0")
    release_server.body = _rel("v9.0.0", name="Vorleser-windows-setup.exe")
    assert updater.check(force=True) is None


def test_latest_json_ist_hauptweg(release_server, monkeypatch):
    """latest.json (Download-Seite) wird zuerst gelesen; die API wird dann gar nicht gefragt."""
    monkeypatch.setattr(paths, "APP_VERSION", "1.0.0")
    monkeypatch.setattr(updater, "JSON_URL", f"http://127.0.0.1:{release_server.port}/latest.json")
    monkeypatch.setattr(updater, "API_URL", "http://127.0.0.1:9/nix")
    release_server.body = {"version": "1.3.0", "notes": "Neu: Export.", "page": "https://x",
                           "assets": {"Vorleser-mac.dmg": {"url": "http://dl/mac.dmg", "size": 7}}}
    latest = updater.check(force=True)
    assert latest == {"version": "1.3.0", "url": "http://dl/mac.dmg", "size": 7, "notes": "Neu: Export.", "page": "https://x", "patch": None}
    assert updater.status()["available"]


def test_api_ausweichweg_hoechstens_stuendlich(release_server, monkeypatch):
    """Ist latest.json nicht erreichbar, fragt die minütliche Prüfung die API nur einmal pro Stunde."""
    monkeypatch.setattr(paths, "APP_VERSION", "1.0.0")
    release_server.body = _rel("v1.2.0")
    assert updater.check()["version"] == "1.2.0"                  # erste Prüfung: API
    release_server.body = _rel("v1.4.0")
    monkeypatch.setattr(updater, "_checked", 0.0)                  # eine Minute später …
    assert updater.check()["version"] == "1.2.0"                  # … API noch nicht wieder gefragt
    assert updater.check(force=True)["version"] == "1.4.0"        # „Jetzt suchen“ darf immer


def test_offline_kein_absturz(monkeypatch):
    monkeypatch.setattr(updater, "JSON_URL", "http://127.0.0.1:9/latest.json")
    monkeypatch.setattr(updater, "API_URL", "http://127.0.0.1:9/nix")
    monkeypatch.setattr(updater, "LATEST_PAGE", "http://127.0.0.1:9/releases/latest")
    monkeypatch.setattr(updater, "ASSET", "Vorleser-mac.dmg")
    monkeypatch.setattr(updater, "_latest", None)
    assert updater.check(force=True) is None


def test_gerade_aktualisiert(monkeypatch, tmp_path):
    f = tmp_path / "last-version"
    f.write_text("1.0.0")
    monkeypatch.setattr(updater, "LAST_VERSION_FILE", f)
    monkeypatch.setattr(updater, "UPDATES_DIR", tmp_path / "updates")
    monkeypatch.setattr(paths, "APP_VERSION", "1.1.0")
    (tmp_path / "updates").mkdir()
    (tmp_path / "updates" / "1.1.0-Vorleser-mac.dmg").write_text("alt")
    (tmp_path / "updates" / "x.part").write_text("halb")
    updater.start_background()
    assert updater.status()["justUpdated"] == "1.1.0"
    assert f.read_text() == "1.1.0"
    assert not list((tmp_path / "updates").iterdir())          # erledigte Downloads aufgeräumt
    monkeypatch.setattr(updater, "_just_updated", None)


class _Redirect(BaseHTTPRequestHandler):
    """Spielt github.com: /releases/latest → 302 auf /tag/v3.1.0, Datei per HEAD mit Größe."""
    def do_HEAD(self):
        if self.path.endswith("/releases/latest"):
            self.send_response(302)
            self.send_header("Location", "https://example.org/x/releases/tag/v3.1.0")
        elif self.path.endswith("/releases/download/v3.1.0/Vorleser-mac.dmg"):
            self.send_response(200)
            self.send_header("Content-Length", "4242")
        else:
            self.send_response(404)
        self.end_headers()

    def log_message(self, *a):
        pass


def test_ausweichweg_ohne_api(monkeypatch):
    """API am Ratenlimit (60/h pro IP) → Version aus der Weiterleitung der Release-Seite."""
    srv = ThreadingHTTPServer(("127.0.0.1", 0), _Redirect)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        monkeypatch.setattr(updater, "API_URL", "http://127.0.0.1:9/gesperrt")
        monkeypatch.setattr(updater, "LATEST_PAGE", f"http://127.0.0.1:{srv.server_address[1]}/x/releases/latest")
        monkeypatch.setattr(updater, "ASSET", "Vorleser-mac.dmg")
        monkeypatch.setattr(updater, "_latest", None)
        monkeypatch.setattr(paths, "APP_VERSION", "3.0.0")
        latest = updater.check(force=True)
        assert latest["version"] == "3.1.0" and latest["size"] == 4242
        assert latest["url"].endswith("/releases/download/v3.1.0/Vorleser-mac.dmg")
        assert updater.status()["available"]
    finally:
        srv.shutdown()


def test_klon_abbruch_ist_kein_fehler(monkeypatch, tmp_path):
    """Regression: „Installation abbrechen“ wurde als „Installation fehlgeschlagen“ gemeldet."""
    import sys
    monkeypatch.setattr(clone_setup, "_uv", lambda: sys.executable)
    monkeypatch.setattr(clone_setup, "CLONE_ENV", tmp_path / "env")
    monkeypatch.setattr(clone_setup, "SETUP_LOG", tmp_path / "setup.log")
    monkeypatch.setattr(clone_setup, "UV_CACHE", tmp_path / "cache")
    # „uv venv …“ durch einen Prozess ersetzen, der einfach lange läuft
    real_popen = clone_setup.subprocess.Popen
    monkeypatch.setattr(clone_setup.subprocess, "Popen",
                        lambda args, **kw: real_popen([sys.executable, "-c", "import time; time.sleep(30)"], **kw))
    clone_setup.start()
    time.sleep(1.0)
    assert clone_setup.status()["status"] == "running"
    clone_setup.uninstall()                          # = Knopf „Installation abbrechen“
    for _ in range(40):
        if clone_setup.status()["status"] != "running":
            break
        time.sleep(0.1)
    time.sleep(0.5)
    s = clone_setup.status()
    assert s["status"] == "idle" and "error" not in s


def test_modellgroesse_waechst_nicht_mit(monkeypatch):
    """Regression: Kopie aus .incomplete ließ „von 3.060 MB“ auf „von 4.166 MB“ wachsen."""
    with clone_setup._lock:
        clone_setup._state.clear()
        clone_setup._state.update(status="running", phase="model", mb=4100)
    totals = {"python": 63, "packages": 1070, "model": 3060}
    clone_setup._progress(totals, ["python", "packages", "model"])
    s = clone_setup.status()
    assert totals["model"] == 3060 and s["mb"] == 3060 and s["total"] == 3060
    with clone_setup._lock:                           # Programmteile (Schätzung) dürfen mitwachsen
        clone_setup._state.update(phase="packages", mb=1500)
    clone_setup._progress(totals, ["python", "packages", "model"])
    assert totals["packages"] > 1500
    with clone_setup._lock:
        clone_setup._state.clear()
        clone_setup._state["status"] = "idle"


def test_modell_vollstaendig_heisst_fast_fertig():
    """Wunsch: am Ende nicht „lädt noch“, sondern „Fast fertig – wird eingerichtet“."""
    totals = {"python": 63, "packages": 1070, "model": 3060}
    with clone_setup._lock:
        clone_setup._state.clear()
        clone_setup._state.update(status="running", phase="model", mb=3060, step=None)
    clone_setup._progress(totals, ["python", "packages", "model"])
    assert clone_setup.status()["step"] == "finish"
    with clone_setup._lock:
        clone_setup._state.update(mb=1500, step=None)
    clone_setup._progress(totals, ["python", "packages", "model"])
    assert clone_setup.status()["step"] is None
    with clone_setup._lock:
        clone_setup._state.clear()
        clone_setup._state["status"] = "idle"


def test_klon_worker_beendet_sich_ohne_app(tmp_path):
    """Regression: Nach ⌘Q lief der Stimmklon-Prozess verwaist weiter."""
    import os
    import subprocess
    import sys
    root = str(paths.APP_DIR)
    app = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(1)"])
    worker = subprocess.Popen([sys.executable, "-c",
                               f"import sys; sys.path.insert(0, {root!r}); import clone_worker as w; w._watch_parent(); "
                               "import time; time.sleep(30)"],
                              env={**os.environ, "VORLESER_PARENT_PID": str(app.pid)})
    app.wait()                                        # „App“ beendet (und aufgeräumt)
    try:
        assert worker.wait(timeout=10) == 0           # Worker merkt es und beendet sich selbst
    finally:
        if worker.poll() is None:
            worker.kill()


def test_app_gilt_erst_mit_markierung_als_installiert(monkeypatch, tmp_path):
    """In der App zählt nur die Markierung nach dem Modell – nicht schon die Programmteile."""
    env = tmp_path / "env"
    py = env / ("Scripts/python.exe" if paths.IS_WIN else "bin/python")
    py.parent.mkdir(parents=True); py.write_text("")
    (env / "lib" / "python3.11" / "site-packages" / "chatterbox").mkdir(parents=True)
    monkeypatch.setattr(clone_setup, "CLONE_ENV", env)
    monkeypatch.setattr(clone_setup, "CLONE_PY", py)
    monkeypatch.setattr(clone_setup, "MARKER", env / "vorleser-ok")
    monkeypatch.setattr(paths, "FROZEN", True)
    assert not clone_setup.installed()               # Programmteile da, Modell noch nicht
    (env / "vorleser-ok").write_text("x")
    assert clone_setup.installed()


def test_erste_pruefung_wird_gemeldet(monkeypatch):
    """Regression: Oberfläche fragte vor der ersten Prüfung und dann erst 30 min später wieder → keine Karte."""
    monkeypatch.setattr(updater, "API_URL", "http://127.0.0.1:9/nix")
    monkeypatch.setattr(updater, "LATEST_PAGE", "http://127.0.0.1:9/releases/latest")
    monkeypatch.setattr(updater, "_checked_once", False)
    assert updater.status()["checked"] is False
    updater.check(force=True)                       # auch offline gilt „geprüft“
    assert updater.status()["checked"] is True


def test_update_beim_beenden_nur_wenn_bereit_und_nur_einmal(monkeypatch):
    calls = []
    monkeypatch.setattr(updater, "_launch_helper", lambda relaunch: calls.append(relaunch))
    monkeypatch.setattr(updater, "_ready", None)
    monkeypatch.setattr(updater, "_state", {"state": "idle"})
    updater.install_on_exit()
    assert calls == []
    monkeypatch.setattr(updater, "_ready", {"version": "9.9.9", "installer": "x", "staged": "y"})
    monkeypatch.setattr(updater, "_state", {"state": "ready"})
    for _ in range(3):                              # closing, closed, atexit
        updater.install_on_exit()
    assert calls == [False]                         # einmal, ohne Neustart


def test_jetzt_neu_starten(monkeypatch):
    calls, quit_ = [], []
    monkeypatch.setattr(updater, "_launch_helper", lambda relaunch: calls.append(relaunch))
    monkeypatch.setattr(updater, "_ready", None)
    with pytest.raises(ValueError):
        updater.restart_now(lambda: None)
    monkeypatch.setattr(updater, "_ready", {"version": "9.9.9", "installer": "x", "staged": "y"})
    monkeypatch.setattr(updater, "_state", {"state": "ready"})
    updater.restart_now(lambda: quit_.append(1))
    time.sleep(0.5)
    assert calls == [True] and quit_ == [1] and updater.status()["state"] == "installing"
    updater.install_on_exit()                       # Beenden danach startet keinen zweiten Helfer
    assert calls == [True]


@pytest.mark.skipif(sys.platform != "darwin", reason="Mac-Helfer")
def test_mac_helfer_tauscht_vorbereitete_app(monkeypatch, tmp_path):
    app = tmp_path / "Vorleser.app"
    (app / "Contents").mkdir(parents=True); (app / "Contents" / "alt").write_text("1")
    staged = tmp_path / "Vorleser.app.new"
    (staged / "Contents").mkdir(parents=True); (staged / "Contents" / "neu").write_text("2")
    monkeypatch.setattr(updater, "_app_path", lambda: app)
    monkeypatch.setattr(updater, "UPDATES_DIR", tmp_path)
    monkeypatch.setattr(updater.os, "getpid", lambda: 999999)          # „App schon beendet“
    monkeypatch.setattr(updater, "_ready", {"version": "9.9.9", "installer": "x", "staged": str(staged)})
    updater._launch_helper(relaunch=False)
    for _ in range(50):
        if (app / "Contents" / "neu").exists() and not staged.exists():
            break
        time.sleep(0.1)
    assert (app / "Contents" / "neu").exists() and not (app / "Contents" / "alt").exists() and not staged.exists()
