#!/usr/bin/env python3
"""Update auf einem echten Windows-Rechner durchspielen (läuft im Build auf windows-latest).

  python packaging/test_update_windows.py e2e   <Setup.exe> <Setup-9.9.3.exe>
  python packaging/test_update_windows.py alt   <Setup einer alten Version>      (nur Diagnose, echtes Release)

e2e: installiert die gebaute App in einen Wegwerf-Ordner und spielt nacheinander durch, was ein Nutzer tut:
  1. Teil-Update → „Jetzt neu starten“      → App muss von selbst in 9.9.1 wiederkommen
  2. Teil-Update → „Später“ + Beenden        → beim Beenden eingespielt, nächster Start = 9.9.2
  3. komplettes Paket (Setup) → „Jetzt neu starten“ → 9.9.3
Die neuen Versionen sind Kopien der installierten App mit anderer VERSION (+ einer neuen Datei), Teil-Updates
entstehen mit packaging/make_patch.py, ausgeliefert über einen kleinen Server auf 127.0.0.1 (wie latest.json).
alt: installiert eine veröffentlichte alte Version und versucht das echte Update (Davids Fall) – nur Protokoll.
Nur Standardbibliothek. Gibt am Ende update.log und server.log aus; Exit-Code ≠ 0, wenn etwas nicht klappt.
"""
from __future__ import annotations

import http.server
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TMP = Path(os.environ.get("RUNNER_TEMP") or tempfile.gettempdir()) / "vorleser-update-test"
INSTALL = TMP / "install" / "Vorleser"
HOME = TMP / "home"
SERVE = TMP / "serve"
PORT = 8799
SRV_PORT = 8798


def log(msg: str) -> None:
    print(f"[test {time.strftime('%H:%M:%S')}] {msg}", flush=True)


def version_file(root: Path) -> Path:
    hits = [p for p in (root / "_internal" / "VERSION", root / "VERSION") if p.is_file()]
    if not hits:
        raise SystemExit(f"VERSION nicht gefunden in {root}")
    return hits[0]


def installed_version() -> str:
    return version_file(INSTALL).read_text("utf-8").strip()


def install(setup: Path) -> None:
    log(f"installiere {setup.name} nach {INSTALL}")
    r = subprocess.run([str(setup), "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/NOCANCEL", "/NOICONS",
                        f"/DIR={INSTALL}", f"/LOG={TMP / 'setup.log'}"], timeout=600)
    if r.returncode != 0:
        raise SystemExit(f"Setup fehlgeschlagen: {r.returncode}")
    log(f"installiert: Version {installed_version()}")


def env(extra: dict | None = None) -> dict:
    e = dict(os.environ, VORLESER_HOME=str(HOME), VORLESER_PORT=str(PORT))
    e.pop("VORLESER_VERSION", None)
    e.update(extra or {})
    return e


def start_app(extra: dict | None = None) -> subprocess.Popen:
    p = subprocess.Popen([str(INSTALL / "Vorleser.exe")], env=env(extra), cwd=str(INSTALL))
    log(f"App gestartet (PID {p.pid})")
    return p


def token() -> str:
    return (HOME / "data" / "api-token").read_text("utf-8").strip()


def api(method: str, path: str, timeout: float = 10):
    req = urllib.request.Request(f"http://127.0.0.1:{PORT}{path}", method=method, data=b"{}" if method == "POST" else None,
                                 headers={"X-Vorleser-Token": token(), "Content-Type": "application/json",
                                          "Host": f"127.0.0.1:{PORT}"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read() or b"{}")


def wait_up(timeout: float = 120) -> dict:
    """Bis der Server antwortet (neuer Schlüssel pro Start → jedes Mal frisch lesen)."""
    end = time.time() + timeout
    last = None
    while time.time() < end:
        try:
            return api("GET", "/api/update")
        except Exception as e:
            last = e
            time.sleep(1)
    raise TimeoutError(f"App antwortet nicht ({last!r})")


def wait_down(timeout: float = 60) -> None:
    end = time.time() + timeout
    while time.time() < end:
        try:
            api("GET", "/api/update", timeout=2)
            time.sleep(0.5)
        except Exception:
            return
    raise TimeoutError("App beendet sich nicht")


def prepare_update(wait_ready: float = 300) -> dict:
    api("POST", "/api/update/check", timeout=30)
    api("POST", "/api/update/install", timeout=30)
    end = time.time() + wait_ready
    while time.time() < end:
        s = api("GET", "/api/update")
        if s.get("state") == "ready":
            log(f"Update bereit: {s.get('latest')} ({'Teil-Update' if s.get('partial') else 'komplett'})")
            return s
        if s.get("state") == "error":
            raise RuntimeError(f"Update-Fehler: {s.get('error')}")
        time.sleep(1)
    raise TimeoutError(f"Update wurde nicht bereit: {s}")


def serve() -> None:
    SERVE.mkdir(parents=True, exist_ok=True)

    class H(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *a, **kw):
            super().__init__(*a, directory=str(SERVE), **kw)

        def log_message(self, *a):
            pass
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", SRV_PORT), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()


def publish(new_version: str, setup: Path | None = None, patch: bool = True) -> None:
    """Neue Version aus der installierten bauen (andere VERSION + neue Datei) und als latest.json anbieten."""
    old = installed_version()
    work = TMP / f"build-{new_version}"
    shutil.rmtree(work, ignore_errors=True)
    asset = {}
    if patch:
        new_root = work / "Vorleser"
        shutil.copytree(INSTALL, new_root, ignore=shutil.ignore_patterns("unins*"))
        version_file(new_root).write_text(new_version, "utf-8")
        (version_file(new_root).parent / f"update-test-{new_version}.txt").write_text("neu", "utf-8")
        mp = [sys.executable, str(ROOT / "packaging" / "make_patch.py"), "windows"]
        subprocess.run(mp + [str(INSTALL), old, str(work / "old")], check=True)
        subprocess.run(mp + [str(new_root), new_version, str(work / "new"), str(work / "old" / "Vorleser-windows-manifest.json")], check=True)
        for f in ("Vorleser-windows-patch.zip",):
            shutil.copy(work / "new" / f, SERVE / f"{new_version}-{f}")
        z = SERVE / f"{new_version}-Vorleser-windows-patch.zip"
        asset["patch"] = {"url": f"http://127.0.0.1:{SRV_PORT}/{z.name}", "size": z.stat().st_size, "from": [old]}
    if setup is None:                                   # Teil-Update: das komplette Paket darf nie geladen werden
        asset.update(url=f"http://127.0.0.1:{SRV_PORT}/fehlt.exe", size=1)
    else:
        dst = SERVE / f"{new_version}-setup.exe"
        shutil.copy(setup, dst)
        asset.update(url=f"http://127.0.0.1:{SRV_PORT}/{dst.name}", size=dst.stat().st_size)
    (SERVE / "latest.json").write_text(json.dumps({"version": new_version, "notes": "Test", "page": "http://127.0.0.1/",
                                                   "assets": {"Vorleser-windows-setup.exe": asset}}), "utf-8")
    log(f"angeboten: {new_version} ({'Teil-Update' if patch else 'komplettes Paket'} von {old})")


UPDATE_ENV = {"VORLESER_UPDATE_JSON": f"http://127.0.0.1:{SRV_PORT}/latest.json",
              "VORLESER_UPDATE_URL": "http://127.0.0.1:9/keine-api", "VORLESER_UPDATE_PAGE": "http://127.0.0.1:9/keine-seite"}


def dump_logs() -> None:
    for name in ("update.log", "server.log"):
        p = HOME / "data" / name
        print(f"\n===== {name} =====", flush=True)
        try:
            lines = p.read_text("utf-8", errors="replace").splitlines()
            print("\n".join(lines[-80:]), flush=True)
        except OSError:
            print("(nicht vorhanden)", flush=True)
    for d in (INSTALL, ):
        print(f"\n===== Dateien {d} (Auszug) =====", flush=True)
        for p in sorted(d.glob("update-test*")) + sorted((d / "_internal").glob("update-test*")):
            print("  ", p.name, flush=True)


def windows_visible() -> int:
    """Wie viele Vorleser-Prozesse haben ein sichtbares Hauptfenster? (Nach dem Neustart muss der Nutzer es sehen.)"""
    r = subprocess.run(["powershell", "-NoProfile", "-Command",
                        "@(Get-Process -Name Vorleser -ErrorAction SilentlyContinue | Where-Object { $_.MainWindowHandle -ne 0 }).Count"],
                       capture_output=True, text=True, timeout=30)
    try:
        return int(r.stdout.strip() or 0)
    except ValueError:
        return 0


def wait_window(timeout: float = 30) -> bool:
    end = time.time() + timeout
    while time.time() < end:
        if windows_visible():
            return True
        time.sleep(1)
    return False


BASE_WINDOW: bool | None = None                      # zeigt dieser Rechner überhaupt Fenster? (erster Start)


def kill_all() -> None:
    subprocess.run(["taskkill", "/F", "/IM", "Vorleser.exe", "/T"], capture_output=True)


def step_restart(new: str, setup: Path | None = None, patch: bool = True, extra: dict | None = None) -> None:
    publish(new, setup, patch)
    global BASE_WINDOW
    p = start_app({**UPDATE_ENV, **(extra or {})})
    wait_up()
    if BASE_WINDOW is None:
        BASE_WINDOW = wait_window()
        log(f"Fenster sichtbar beim normalen Start: {BASE_WINDOW}")
    prepare_update()
    log("„Jetzt neu starten“")
    api("POST", "/api/update/restart")
    p.wait(timeout=60)
    log(f"alte App beendet (Code {p.returncode}) – warte auf Neustart")
    s = wait_up(180)
    if s.get("current") != new:
        raise AssertionError(f"nach Neustart läuft {s.get('current')}, erwartet {new}")
    log(f"OK: neu gestartet in {new}")
    if BASE_WINDOW:
        if not wait_window():
            raise AssertionError("nach dem Neustart ist kein Vorleser-Fenster sichtbar")
        log("OK: Fenster nach dem Neustart sichtbar")
    api("POST", "/api/quit")
    wait_down()
    time.sleep(2)


def step_later(new: str) -> None:
    publish(new)
    p = start_app(UPDATE_ENV)
    wait_up()
    prepare_update()
    log("„Später“, dann Beenden")
    api("POST", "/api/quit")
    p.wait(timeout=60)
    end = time.time() + 120                           # Helfer spielt nach dem Beenden ein
    while time.time() < end and installed_version() != new:
        time.sleep(1)
    if installed_version() != new:
        raise AssertionError(f"nach dem Beenden installiert: {installed_version()}, erwartet {new}")
    p = start_app(UPDATE_ENV)
    s = wait_up()
    if s.get("current") != new:
        raise AssertionError(f"nächster Start läuft {s.get('current')}, erwartet {new}")
    log(f"OK: beim Beenden eingespielt, nächster Start = {new}")
    api("POST", "/api/quit")
    p.wait(timeout=60)
    time.sleep(2)


def e2e(setup: Path, setup3: Path) -> None:
    install(setup)
    serve()
    step_restart("9.9.1")
    step_later("9.9.2")
    step_restart("9.9.3", setup=setup3, patch=False)
    leftovers = list((HOME / "updates").glob("staged-*")) if (HOME / "updates").exists() else []
    log(f"übrig im Update-Ordner: {[p.name for p in leftovers]}")


def alt(setup: Path) -> None:
    """Diagnose: veröffentlichte alte Version → echtes Update (latest.json der Download-Seite)."""
    install(setup)
    old = installed_version()
    p = start_app()
    s = wait_up()
    log(f"läuft: {s.get('current')}")
    prepare_update(600)
    api("POST", "/api/update/restart")
    try:
        p.wait(timeout=60)
        log(f"alte App beendet (Code {p.returncode})")
    except subprocess.TimeoutExpired:
        log("alte App beendet sich nicht innerhalb 60 s")
    try:
        s = wait_up(180)
        log(f"nach Neustart läuft: {s.get('current')}")
    except TimeoutError:
        log("App kam nicht wieder")
    log(f"installierte Version jetzt: {installed_version()} (vorher {old})")
    tasks = subprocess.run(["tasklist"], capture_output=True, text=True).stdout
    log("Prozesse: " + ", ".join(sorted({l.split()[0] for l in tasks.splitlines()[3:] if l.strip() and
                                         l.split()[0].lower() in ("vorleser.exe", "powershell.exe", "robocopy.exe")})))


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    shutil.rmtree(TMP, ignore_errors=True)
    TMP.mkdir(parents=True)
    mode = sys.argv[1]
    ok = True
    try:
        if mode == "e2e":
            e2e(Path(sys.argv[2]).resolve(), Path(sys.argv[3]).resolve())
        else:
            alt(Path(sys.argv[2]).resolve())
    except Exception as e:
        ok = False
        log(f"FEHLER: {e!r}")
    finally:
        dump_logs()
        kill_all()
    return 0 if ok or mode == "alt" else 1


if __name__ == "__main__":
    sys.exit(main())
