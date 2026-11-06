"""Updates für die Desktop-App: neue Version erkennen, laden und mit einem Klick installieren.

Quelle ist das neueste Release im öffentlichen Repo vorleser-download (feste Dateinamen).
Installiert wird von einem kleinen Helfer, der wartet, bis die App beendet ist:
  macOS:   DMG einhängen, Vorleser.app austauschen, neu starten
  Windows: Setup still ausführen (Inno Setup), danach neu starten
Was die App selbst lädt, bekommt kein Quarantäne-/Internet-Kennzeichen → keine Sicherheitswarnung.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

import paths

REPO = "SimonSchneZzer/vorleser-download"
API_URL = os.environ.get("VORLESER_UPDATE_URL", f"https://api.github.com/repos/{REPO}/releases/latest")
PAGE_URL = "https://simonschnezzer.github.io/vorleser-download/"
# Ausweichweg ohne API (kein Ratenlimit von 60/h pro IP): die Release-Seite leitet auf /tag/vX.Y.Z weiter
LATEST_PAGE = os.environ.get("VORLESER_UPDATE_PAGE", f"https://github.com/{REPO}/releases/latest")
ASSET = "Vorleser-mac.dmg" if paths.IS_MAC else "Vorleser-windows-setup.exe" if paths.IS_WIN else None
CHECK_EVERY = 6 * 3600
UPDATES_DIR = paths.USER_DIR / "updates"
LAST_VERSION_FILE = paths.DATA_DIR / "last-version"

_lock = threading.Lock()
_state: dict = {"state": "idle"}      # idle | downloading | ready (geladen + vorbereitet) | installing | error
_ready: dict | None = None             # {"version", "installer", "staged"} – wartet auf Neustart oder Beenden
_checked_once = False                  # erste Prüfung nach dem Start abgeschlossen (Oberfläche wartet darauf)
_latest: dict | None = None
_checked = 0.0
_just_updated: str | None = None


def _ver(v: str) -> tuple:
    return tuple(int(x) for x in re.findall(r"\d+", v or "")[:3]) or (0,)


def _app_path() -> Path | None:
    """Das laufende App-Paket (macOS) bzw. die Vorleser.exe (Windows)."""
    if not paths.FROZEN:
        return None
    exe = Path(sys.executable).resolve()
    if paths.IS_MAC:
        return exe.parents[2] if exe.parents[2].suffix == ".app" else None
    return exe


def can_install() -> tuple[bool, str]:
    """Kann sich die App selbst ersetzen? Sonst Grund (→ Download-Seite öffnen)."""
    if not paths.FROZEN or ASSET is None:
        return False, "Nur in der installierten App"
    app = _app_path()
    if app is None:
        return False, "App-Ordner nicht gefunden"
    s = str(app)
    if paths.IS_MAC and ("AppTranslocation" in s or s.startswith("/Volumes/")):
        return False, "Bitte Vorleser zuerst in den Ordner Programme ziehen"
    if not os.access(app.parent, os.W_OK):
        return False, "Keine Schreibrechte im App-Ordner"
    return True, ""


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **kw):
        return None


def _check_via_redirect() -> dict | None:
    """Neueste Version aus der Weiterleitung der Release-Seite (ohne API, ohne Release-Notizen)."""
    opener = urllib.request.build_opener(_NoRedirect)
    req = urllib.request.Request(LATEST_PAGE, method="HEAD", headers={"User-Agent": "Vorleser-Updater"})
    try:
        opener.open(req, timeout=15)
        return None                                   # keine Weiterleitung → kein Release
    except urllib.error.HTTPError as e:
        loc = e.headers.get("Location") or ""
        if e.code not in (301, 302, 303, 307, 308) or "/tag/" not in loc:
            return None
    tag = loc.rstrip("/").rsplit("/tag/", 1)[1]
    url = LATEST_PAGE.replace("/releases/latest", f"/releases/download/{tag}/{ASSET}")
    head = urllib.request.Request(url, method="HEAD", headers={"User-Agent": "Vorleser-Updater"})
    with urllib.request.urlopen(head, timeout=15) as r:      # existiert die Datei für dieses System?
        size = int(r.headers.get("Content-Length") or 0)
    return {"version": tag.lstrip("v"), "url": url, "size": size, "notes": "", "page": PAGE_URL}


def check(force: bool = False) -> dict | None:
    """Neuestes Release abfragen (höchstens alle paar Minuten, außer force)."""
    try:
        return _check(force)
    finally:
        global _checked_once
        _checked_once = True


def _check(force: bool = False) -> dict | None:
    global _latest, _checked
    if ASSET is None or (not force and time.time() - _checked < 300):
        return _latest
    _checked = time.time()
    try:
        req = urllib.request.Request(API_URL, headers={"Accept": "application/vnd.github+json",
                                                       "User-Agent": "Vorleser-Updater"})
        with urllib.request.urlopen(req, timeout=15) as r:
            rel = json.loads(r.read())
        asset = next((a for a in rel.get("assets", []) if a.get("name") == ASSET), None)
        if rel.get("draft") or rel.get("prerelease") or not asset:
            return _latest
        notes = (rel.get("body") or "").strip()
        _latest = {"version": rel["tag_name"].lstrip("v"), "url": asset["browser_download_url"],
                   "size": asset.get("size") or 0, "notes": notes[:600], "page": rel.get("html_url") or PAGE_URL}
        print(f"[update] neueste Version {_latest['version']} (installiert {paths.APP_VERSION})", flush=True)
    except Exception as e:
        print(f"[update] API nicht nutzbar ({type(e).__name__}) – versuche Release-Seite", flush=True)
        try:
            found = _check_via_redirect()
            if found:
                _latest = found
                print(f"[update] neueste Version {found['version']} (über Release-Seite)", flush=True)
        except Exception as e2:
            print(f"[update] Prüfen fehlgeschlagen: {type(e2).__name__}", flush=True)
    return _latest


def status() -> dict:
    latest = _latest
    ok, why = can_install()
    available = bool(latest and _ver(latest["version"]) > _ver(paths.APP_VERSION))
    with _lock:
        return {**_state, "current": paths.APP_VERSION, "latest": latest["version"] if latest else None,
                "available": available, "notes": latest["notes"] if latest else "", "size": latest["size"] if latest else 0,
                "canInstall": ok, "reason": why, "page": PAGE_URL, "justUpdated": _just_updated, "checked": _checked_once,
                "readyVersion": _ready["version"] if _ready else None,
                "enabled": paths.FROZEN or bool(os.environ.get("VORLESER_UPDATE_URL"))}


def _download(latest: dict) -> Path:
    UPDATES_DIR.mkdir(parents=True, exist_ok=True)
    dest = UPDATES_DIR / f"{latest['version']}-{ASSET}"
    if dest.exists() and (not latest["size"] or dest.stat().st_size == latest["size"]):
        return dest
    part = dest.with_suffix(dest.suffix + ".part")
    req = urllib.request.Request(latest["url"], headers={"User-Agent": "Vorleser-Updater"})
    with urllib.request.urlopen(req, timeout=60) as r, open(part, "wb") as f:
        total = int(r.headers.get("Content-Length") or latest["size"] or 0)
        done = 0
        while chunk := r.read(1 << 20):
            f.write(chunk)
            done += len(chunk)
            with _lock:
                _state.update(done=done, total=total)
    if latest["size"] and part.stat().st_size != latest["size"]:
        part.unlink(missing_ok=True)
        raise RuntimeError("Download unvollständig")
    part.replace(dest)
    return dest


def _ps(s) -> str:
    return str(s).replace("'", "''")          # für PowerShell-Strings in '…'


def _stage_mac(installer: Path, app: Path) -> Path:
    """DMG schon VOR dem Neustart einhängen und die neue App neben die alte kopieren – beim Neustart bleibt
    nur noch ein Umbenennen (sofort statt DMG prüfen + 450 MB kopieren nach dem Beenden)."""
    staged = app.with_name(app.name + ".new")
    mnt = Path(subprocess.check_output(["mktemp", "-d", "/tmp/vorleser-update.XXXXXX"], text=True).strip())
    try:
        subprocess.run(["hdiutil", "attach", "-nobrowse", "-readonly", "-noautoopen", "-noverify",
                        "-mountpoint", str(mnt), str(installer)], check=True, capture_output=True, timeout=180)
        subprocess.run(["rm", "-rf", str(staged)], check=False)
        subprocess.run(["ditto", str(mnt / "Vorleser.app"), str(staged)], check=True, timeout=600)
        subprocess.run(["xattr", "-cr", str(staged)], check=False)
    finally:
        subprocess.run(["hdiutil", "detach", str(mnt), "-quiet"], check=False)
        subprocess.run(["rmdir", str(mnt)], check=False)
    return staged


def _launch_helper(relaunch: bool) -> None:
    """Helfer starten, der nach dem Beenden der App das vorbereitete Update einspielt (und ggf. neu startet)."""
    app, pid, log = _app_path(), os.getpid(), paths.DATA_DIR / "update.log"
    if paths.IS_MAC:
        staged = Path(_ready["staged"])
        script = UPDATES_DIR / "install.sh"
        script.write_text(f"""#!/bin/bash
exec >>"{log}" 2>&1
echo "== $(date) Update auf {_ready['version']} (Neustart: {'ja' if relaunch else 'nein'})"
while kill -0 {pid} 2>/dev/null; do sleep 0.1; done
if [ -d "{staged}" ]; then
  rm -rf "{app}.old" && mv "{app}" "{app}.old" && mv "{staged}" "{app}" && echo "installiert"
  rm -rf "{app}.old" &
fi
{f'open "{app}"' if relaunch else ''}
""", "utf-8")
        script.chmod(0o755)
        subprocess.Popen(["/bin/bash", str(script)], start_new_session=True,
                         stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    elif paths.IS_WIN:
        L, I, A = _ps(log), _ps(_ready["installer"]), _ps(app)
        ps = (f"Add-Content -Path '{L}' -Value ('== ' + (Get-Date) + ' Update'); "
              f"Wait-Process -Id {pid} -ErrorAction SilentlyContinue; "
              f"$p = Start-Process -FilePath '{I}' -ArgumentList '/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART','/NOCANCEL' -Wait -PassThru; "
              f"Add-Content -Path '{L}' -Value ('Setup beendet: ' + $p.ExitCode)"
              + (f"; Start-Process -FilePath '{A}'" if relaunch else ""))
        flags = 0x00000008 | 0x00000200 | 0x08000000   # DETACHED_PROCESS | NEW_PROCESS_GROUP | NO_WINDOW
        subprocess.Popen(["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-WindowStyle", "Hidden",
                          "-Command", ps], creationflags=flags, close_fds=True,
                         stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def _prepare() -> None:
    """Laden und vorbereiten – die App läuft dabei normal weiter."""
    global _ready
    try:
        latest = check(force=True)
        if not latest or _ver(latest["version"]) <= _ver(paths.APP_VERSION):
            raise RuntimeError("Keine neuere Version gefunden")
        installer = _download(latest)
        with _lock:
            _state.update(state="preparing")
        staged = str(_stage_mac(installer, _app_path())) if paths.IS_MAC else None
        _ready = {"version": latest["version"], "installer": str(installer), "staged": staged}
        with _lock:
            _state.update(state="ready")
        print(f"[update] {latest['version']} bereit – startet beim Neustart oder beim nächsten Öffnen", flush=True)
    except Exception as e:
        print(f"[update] Fehler: {e}", flush=True)
        with _lock:
            _state.update(state="error", error=str(e))


def install(quit_app=None) -> dict:
    """Update laden und vorbereiten (Neustart erst auf Wunsch – oder beim Beenden)."""
    ok, why = can_install()
    if not ok:
        raise ValueError(why)
    with _lock:
        if _state["state"] in ("downloading", "preparing", "ready", "installing"):
            return dict(_state)
        _state.clear()
        _state.update(state="downloading", done=0, total=_latest["size"] if _latest else 0)
    threading.Thread(target=_prepare, daemon=True).start()
    return status()


def restart_now(quit_app) -> dict:
    """„Jetzt neu starten“: Helfer los, App beenden – das Austauschen dauert nur einen Moment."""
    if not _ready:
        raise ValueError("Kein Update bereit")
    with _lock:
        _state.update(state="installing")
    print(f"[update] Neustart in {_ready['version']}", flush=True)
    _launch_helper(relaunch=True)
    threading.Timer(0.3, quit_app).start()
    return status()


def install_on_exit() -> None:
    """Beim Beenden: ein bereitliegendes Update einspielen – beim nächsten Öffnen läuft die neue Version."""
    if _ready and _state.get("state") == "ready":
        with _lock:
            _state.update(state="installing")          # _cleanup läuft mehrfach (closing/closed/atexit) → nur einmal
        print(f"[update] {_ready['version']} wird beim Beenden eingespielt", flush=True)
        _launch_helper(relaunch=False)


def start_background() -> None:
    """Beim Start: „gerade aktualisiert?“ merken, alte Downloads löschen, regelmäßig prüfen."""
    global _just_updated
    try:
        prev = LAST_VERSION_FILE.read_text("utf-8").strip()
    except OSError:
        prev = ""
    if prev and _ver(prev) < _ver(paths.APP_VERSION):
        _just_updated = paths.APP_VERSION
    LAST_VERSION_FILE.write_text(paths.APP_VERSION, "utf-8")
    if UPDATES_DIR.exists():
        for p in UPDATES_DIR.iterdir():
            if paths.APP_VERSION in p.name or p.suffix == ".part":
                p.unlink(missing_ok=True)

    app = _app_path() if paths.IS_MAC and paths.FROZEN else None
    if app and app.with_name(app.name + ".new").exists():      # Rest eines abgebrochenen Updates (~450 MB)
        subprocess.Popen(["rm", "-rf", str(app.with_name(app.name + ".new"))], **paths.NO_WINDOW)

    def loop():
        time.sleep(1)                       # bei jedem Start kurz nach dem Öffnen prüfen
        while True:
            check(force=True)
            time.sleep(CHECK_EVERY)
    if status()["enabled"]:
        threading.Thread(target=loop, daemon=True).start()
