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
@pytest.mark.skipif(sys.platform == "win32", reason="legt eine Verknüpfung an – unter Windows nur mit Sonderrechten")
def test_windows_python_ohne_verknuepfung(monkeypatch, tmp_path):
    """Rückmeldung 8.11.2026 (Windows 11, os error 448): Die Junction cpython-3.11-… scheitert; danach scheiterte jeder
    Versuch. Jetzt: Verknüpfungen weg, Python über den vollen Pfad ansprechen."""
    py = tmp_path / "clone-python"
    real = py / "cpython-3.11.18-windows-x86_64-none"
    monkeypatch.setattr(clone_setup, "PY_DIR", py)
    monkeypatch.setattr(clone_setup, "CLONE_ENV", tmp_path / "env")
    monkeypatch.setattr(paths, "IS_WIN", True); monkeypatch.setattr(paths, "IS_MAC", False); monkeypatch.setattr(paths, "FROZEN", True)
    monkeypatch.setattr(clone_setup, "_uv", lambda: "uv")
    monkeypatch.setattr(clone_setup, "_has_nvidia", lambda: False)
    monkeypatch.setattr(clone_setup, "_model_mb", lambda: 1)
    calls = []

    class Stopp(Exception):
        pass

    def run(phase, args, totals, order, watch=(), env_extra=None):
        calls.append((args, env_extra))
        if args[1:3] == ["python", "install"]:
            real.mkdir(parents=True); (real / "python.exe").write_text("")
            (py / "cpython-3.11-windows-x86_64-none").symlink_to(real)        # „halbe“ Verknüpfung (am Mac: Symlink)
            raise clone_setup.Meldung(clone_setup.PHASE_FEHLER["python"])
        if args[1] == "venv":
            raise Stopp                                                         # weiter interessiert hier nicht
    monkeypatch.setattr(clone_setup, "_run", run)
    clone_setup._install()                                                      # fängt den Stopp selbst ab
    venv = [a for a, _ in calls if a[1] == "venv"]
    assert venv and venv[0][3] == str(real / "python.exe")
    assert not (py / "cpython-3.11-windows-x86_64-none").exists()            # Verknüpfung entfernt, Python bleibt
    assert real.exists() and calls[-1][1] == {"UV_PYTHON_PREFERENCE": "managed"}


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
    assert latest == {"version": "1.3.0", "url": "http://dl/mac.dmg", "size": 7, "notes": "Neu: Export.", "page": "https://x", "patch": None, "sha256": None}
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


@pytest.mark.skipif(sys.platform != "darwin", reason="Mac-Helfer")
def test_mac_helfer_stellt_alte_app_wieder_her(monkeypatch, tmp_path):
    """Scheitert das Einsetzen der neuen App, darf Vorleser nicht verschwinden (vorher: App weg)."""
    app = tmp_path / "Vorleser.app"
    (app / "Contents").mkdir(parents=True); (app / "Contents" / "alt").write_text("1")
    ro = tmp_path / "ro"
    staged = ro / "Vorleser.app.new"
    (staged / "Contents").mkdir(parents=True)
    ro.chmod(0o555)                                  # neue App lässt sich nicht herausbewegen
    try:
        monkeypatch.setattr(updater, "_app_path", lambda: app)
        monkeypatch.setattr(updater, "UPDATES_DIR", tmp_path)
        monkeypatch.setattr(updater.os, "getpid", lambda: 999999)
        monkeypatch.setattr(updater, "_ready", {"version": "9.9.9", "installer": "x", "staged": str(staged)})
        monkeypatch.setattr(updater.paths, "DATA_DIR", tmp_path)
        updater._launch_helper(relaunch=False)
        for _ in range(50):
            if "wiederhergestellt" in ((tmp_path / "update.log").read_text() if (tmp_path / "update.log").exists() else ""):
                break
            time.sleep(0.1)
        assert "wiederhergestellt" in (tmp_path / "update.log").read_text()
        assert (app / "Contents" / "alt").exists() and not (tmp_path / "Vorleser.app.old").exists()
    finally:
        ro.chmod(0o755)


# --------------------------------------------------------------------------- #
# Laden: Wiederholung bei Serverfehlern, Ausweichweg über die GitHub-API
def _http(code):
    import urllib.error
    return urllib.error.HTTPError("u", code, "x", {}, None)


def test_laden_wiederholt_bei_504_dann_api(monkeypatch, tmp_path):
    """github.com liefert 504 → zwei neue Versuche, dann dieselbe Datei über die API (mit Accept-Header)."""
    monkeypatch.setattr(updater, "RETRY_WAIT", (0, 0))
    monkeypatch.setattr(updater, "UPDATES_DIR", tmp_path)
    calls = []

    def once(latest, url, size, name, headers):
        calls.append((url, headers))
        if url.startswith("https://github.com/"):
            raise _http(504)
        return tmp_path / name
    monkeypatch.setattr(updater, "_download_once", once)
    monkeypatch.setattr(updater, "_api_asset_url", lambda v, n: f"https://api.github.com/assets/{v}/{n}")
    latest = {"version": "2.0.0", "url": "https://github.com/x/releases/download/v2.0.0/Vorleser-mac.dmg", "size": 1}
    assert updater._download(latest) == tmp_path / updater.ASSET
    assert [u for u, _ in calls].count(latest["url"]) == 3
    assert calls[-1] == ("https://api.github.com/assets/2.0.0/Vorleser-mac.dmg", {"Accept": "application/octet-stream"})


def test_laden_404_ohne_wiederholung(monkeypatch, tmp_path):
    monkeypatch.setattr(updater, "RETRY_WAIT", (0, 0))
    calls = []

    def once(*a):
        calls.append(a)
        raise _http(404)
    monkeypatch.setattr(updater, "_download_once", once)
    monkeypatch.setattr(updater, "_api_asset_url", lambda v, n: pytest.fail("API darf bei 404 nicht gefragt werden"))
    with pytest.raises(Exception):
        updater._download({"version": "2.0.0", "url": "https://github.com/x/a.dmg", "size": 1})
    assert len(calls) == 1


def test_meldungen_fuer_die_karte():
    import socket
    import urllib.error
    assert updater._user_error(_http(504)) == updater.MSG_SERVER
    assert updater._user_error(urllib.error.URLError(socket.gaierror(8, "x"))) == updater.MSG_OFFLINE
    assert updater._user_error(urllib.error.URLError(TimeoutError())) == updater.MSG_SERVER
    assert updater._user_error(RuntimeError("Prüfsumme falsch: a")) == updater.MSG_OTHER
    assert updater._user_error(updater._NoUpdate("Keine neuere Version gefunden")) == "Keine neuere Version gefunden"


def test_meldungen_sind_uebersetzt():
    i18n = (paths.APP_DIR / "static" / "i18n.js").read_text("utf-8")
    for m in (updater.MSG_SERVER, updater.MSG_OFFLINE, updater.MSG_OTHER, "Keine neuere Version gefunden",
              "Nur in der installierten App", "App-Ordner nicht gefunden", "Keine Schreibrechte im App-Ordner",
              "Bitte Vorleser zuerst in den Ordner Programme ziehen"):
        assert json.dumps(m, ensure_ascii=False) + ":" in i18n, m


def test_teilupdate_netzfehler_kein_komplettpaket(monkeypatch):
    """504 beim Teil-Update → Fehler, nicht 263 MB vom selben Server hinterher (Karte sprang 15 → 263 MB)."""
    monkeypatch.setattr(paths, "APP_VERSION", "1.0.0")
    latest = {"version": "1.1.0", "url": "https://github.com/x/a.dmg", "size": 263, "notes": "", "page": "",
              "patch": {"url": "https://github.com/x/p.zip", "size": 15, "from": ["1.0.0"]}}
    monkeypatch.setattr(updater, "check", lambda force=False: latest)
    monkeypatch.setattr(updater, "_patch_for", lambda l: l["patch"])
    monkeypatch.setattr(updater, "_prepare_patch", lambda l, p: (_ for _ in ()).throw(_http(504)))
    monkeypatch.setattr(updater, "_download", lambda *a, **k: pytest.fail("komplettes Paket darf nicht geladen werden"))
    monkeypatch.setattr(updater, "_state", {"state": "downloading"})
    updater._prepare()
    assert updater._state["state"] == "error" and updater._state["error"] == updater.MSG_SERVER


def test_komplettpaket_mit_falscher_pruefsumme_wird_verworfen(monkeypatch, tmp_path):
    """latest.json nennt eine Prüfsumme (ab 3.0.2) → beschädigtes Paket nie einspielen, Datei weg (nächster Versuch lädt neu)."""
    import hashlib
    monkeypatch.setattr(paths, "APP_VERSION", "1.0.0")
    inst = tmp_path / "1.1.0-Vorleser-mac.dmg"
    inst.write_bytes(b"kaputt")
    latest = {"version": "1.1.0", "url": "https://github.com/x/a.dmg", "size": 6, "notes": "", "page": "",
              "sha256": hashlib.sha256(b"richtig").hexdigest()}
    monkeypatch.setattr(updater, "check", lambda force=False: latest)
    monkeypatch.setattr(updater, "_patch_for", lambda l: None)
    monkeypatch.setattr(updater, "_download", lambda *a, **k: inst)
    monkeypatch.setattr(updater, "_stage_mac", lambda *a: pytest.fail("darf nicht eingespielt werden"))
    monkeypatch.setattr(updater, "_ready", None)
    monkeypatch.setattr(updater, "_state", {"state": "downloading"})
    updater._prepare()
    assert updater._state["state"] == "error" and not inst.exists() and updater._ready is None


def test_groesse_erst_nach_antwort(monkeypatch, tmp_path):
    """Vor der Antwort des Servers: connected=False und keine Größe; danach feste Größe aus Content-Length."""
    monkeypatch.setattr(updater, "UPDATES_DIR", tmp_path)
    monkeypatch.setattr(updater, "_state", {"state": "downloading"})
    seen = {}

    class Resp:
        headers = {"Content-Length": "4"}
        def __init__(self): self.left = [b"abcd"]
        def read(self, n): return self.left.pop() if self.left else b""
        def __enter__(self): return self
        def __exit__(self, *a): pass

    def urlopen(req, timeout):
        seen["vorher"] = dict(updater._state)
        return Resp()
    monkeypatch.setattr(updater.urllib.request, "urlopen", urlopen)
    updater._download_once({"version": "1.1.0", "size": 4}, "http://x/a", None, "a.dmg", {})
    assert seen["vorher"]["connected"] is False and seen["vorher"]["total"] == 0
    assert updater._state["connected"] is True and updater._state["total"] == 4 and updater._state["done"] == 4


# --------------------------------------------------------------------------- #
# Windows-Helfer (3.0.2): Skriptdatei, aus dem Job lösen, Rückweg, Neustart in jedem Fall
def test_windows_helfer_skript_und_start(monkeypatch, tmp_path):
    from pathlib import PureWindowsPath as W
    monkeypatch.setattr(updater, "UPDATES_DIR", tmp_path)
    monkeypatch.setattr(updater, "_ready", {"version": "9.9.9", "patch": True, "staged": r"C:\U\Jürgen O'Neil\staged-9.9.9"})
    calls = []

    class Proc:
        returncode = 0
        def poll(self): return 0                                   # sofort beendet → steht im Log

    def popen(args, creationflags=0, **kw):
        calls.append(creationflags)
        if creationflags & 0x01000000:
            raise PermissionError("breakaway nicht erlaubt")       # z. B. Job ohne Breakaway-Recht
        return Proc()
    monkeypatch.setattr(updater.subprocess, "Popen", popen)
    updater._launch_win_helper(W(r"C:\Programs\Vorleser\Vorleser.exe"), 4242, tmp_path / "update.log", True)
    raw = (tmp_path / "install-9.9.9.ps1").read_bytes()
    assert raw.startswith(b"\xef\xbb\xbf")                          # BOM: Windows PowerShell 5 liest sonst ANSI
    ps = raw.decode("utf-8-sig")
    assert "Jürgen O''Neil" in ps and "WaitForExit(60000)" in ps and "robocopy $S $R" in ps
    assert "wiederhergestellt" in ps and "failed-9.9.9.txt" in ps
    assert ps.index("finally") < ps.index("Start-Process -FilePath 'C:\\Programs\\Vorleser\\Vorleser.exe'")   # Neustart immer
    assert calls == [0x01000200 | 0x08000000, 0x00000200 | 0x08000000]   # nie DETACHED_PROCESS (0x8): PowerShell stirbt
    log = (tmp_path / "update.log").read_text("utf-8")
    assert "starte Helfer" in log and "ohne Lösen aus dem Job" in log and "sofort beendet (Code 0)" in log


def test_teilupdate_nach_fehler_komplettes_paket(monkeypatch, tmp_path):
    monkeypatch.setattr(updater, "UPDATES_DIR", tmp_path)
    monkeypatch.setattr(paths, "APP_VERSION", "1.0.0")
    monkeypatch.setattr(paths, "FROZEN", True)
    latest = {"version": "1.1.0", "patch": {"url": "u", "from": ["1.0.0"]}}
    assert updater._patch_for(latest)
    updater._failed_marker("1.1.0").write_text("robocopy")
    assert updater._patch_for(latest) is None


def test_fehlerbericht_enthaelt_update_log(monkeypatch, tmp_path):
    import bugreport
    monkeypatch.setattr(paths, "DATA_DIR", tmp_path)
    (tmp_path / "update.log").write_text("[x] Helfer gestartet\n[x] robocopy: 16\n", "utf-8")
    assert "robocopy: 16" in bugreport.info()["log"]


def test_aufraeumen_beim_start_laesst_vorbereitetes_update(monkeypatch, tmp_path):
    """Aufräumen beim Start läuft verzögert – ein schon vorbereitetes Update darf es nicht löschen."""
    monkeypatch.setattr(updater, "UPDATES_DIR", tmp_path / "updates")
    monkeypatch.setattr(updater, "LAST_VERSION_FILE", tmp_path / "last-version")
    monkeypatch.setattr(updater, "status", lambda: {"enabled": False})
    staged = tmp_path / "updates" / "staged-9.9.1"
    staged.mkdir(parents=True)
    monkeypatch.setattr(updater, "_state", {"state": "ready"})
    updater.start_background()
    assert staged.exists()
    monkeypatch.setattr(updater, "_state", {"state": "idle"})
    updater.start_background()
    assert not staged.exists()                                   # ohne vorbereitetes Update: Rest weg
