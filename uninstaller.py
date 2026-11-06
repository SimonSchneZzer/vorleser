"""Vorleser deinstallieren – aus der App heraus, nach ausdrücklicher Bestätigung.

Wie beim Updater erledigt ein kleiner Helfer die Arbeit, nachdem die App sich beendet hat:
  macOS:   Vorleser.app, Datenordner (~/Library/Application Support/Vorleser) und die Webview-Daten
           unter ~/Library löschen.
  Windows: den Inno-Setup-Uninstaller still ausführen (Programm, Verknüpfungen, Eintrag in „Apps“)
           und %APPDATA%\\Vorleser löschen.
Auf Wunsch bleiben Texte, Lesezeichen, eigene Stimmen und Einstellungen (Ordner data/) erhalten.
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

import paths
import updater

BUNDLE_ID = "de.neke-neke.vorleser"
KEEP = {"data"}                                   # bleibt bei „Texte und eigene Stimmen behalten“


def can_uninstall() -> tuple[bool, str]:
    if not paths.FROZEN:
        return False, "Nur in der installierten App möglich"
    app = updater._app_path()
    if app is None:
        return False, "App-Ordner nicht gefunden"
    if paths.IS_MAC and ("AppTranslocation" in str(app) or str(app).startswith("/Volumes/")):
        return False, "Die App läuft direkt aus dem Download – einfach die Datei löschen"
    if paths.IS_WIN and not (app.parent / "unins000.exe").exists():
        return False, "Deinstallationsprogramm nicht gefunden – bitte über Windows-Einstellungen › Apps entfernen"
    return True, ""


def _targets(keep_data: bool) -> list[Path]:
    """Was im Datenordner gelöscht wird."""
    if not paths.USER_DIR.exists():
        return []
    if not keep_data:
        return [paths.USER_DIR]
    return [p for p in paths.USER_DIR.iterdir() if p.name not in KEEP]


def _mac_extras() -> list[Path]:
    """Daten, die macOS/WebKit selbst für die App anlegt."""
    lib = Path.home() / "Library"
    return [lib / "WebKit" / BUNDLE_ID, lib / "Caches" / BUNDLE_ID, lib / "HTTPStorages" / BUNDLE_ID,
            lib / "Saved Application State" / f"{BUNDLE_ID}.savedState", lib / "Preferences" / f"{BUNDLE_ID}.plist"]


def _q(p) -> str:
    return "'" + str(p).replace("'", "'\\''") + "'"         # für bash in '…'


def launch(keep_data: bool, quit_app) -> dict:
    ok, why = can_uninstall()
    if not ok:
        raise ValueError(why)
    import clone_setup
    clone_setup.cancel()                                      # laufende Installation stoppen
    app, pid = updater._app_path(), os.getpid()
    log = Path(os.environ.get("TMPDIR") or "/tmp") / "vorleser-uninstall.log"
    targets = _targets(keep_data)
    print(f"[uninstall] Daten {'behalten' if keep_data else 'löschen'} – App beendet sich", flush=True)
    if paths.IS_MAC:
        rm = " ".join(_q(p) for p in [app, *targets, *_mac_extras()])
        script = Path(os.environ.get("TMPDIR") or "/tmp") / "vorleser-uninstall.sh"
        script.write_text(f"""#!/bin/bash
exec >>{_q(log)} 2>&1
echo "== $(date) Deinstallation"
while kill -0 {pid} 2>/dev/null; do sleep 0.3; done
rm -rf {rm}
osascript -e 'display notification "{'Deine Texte wurden behalten.' if keep_data else 'Alle Daten wurden gelöscht.'}" with title "Vorleser wurde entfernt"' 2>/dev/null
rm -f {_q(script)}
""", "utf-8")
        script.chmod(0o755)
        subprocess.Popen(["/bin/bash", str(script)], start_new_session=True,
                         stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    elif paths.IS_WIN:
        P = updater._ps
        uninst = app.parent / "unins000.exe"
        rm = "; ".join(f"Remove-Item -LiteralPath '{P(t)}' -Recurse -Force -ErrorAction SilentlyContinue" for t in targets)
        ps = (f"Wait-Process -Id {pid} -ErrorAction SilentlyContinue; "
              f"Start-Process -FilePath '{P(uninst)}' -ArgumentList '/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART' -Wait; "
              f"{rm}")
        flags = 0x00000008 | 0x00000200 | 0x08000000
        subprocess.Popen(["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-WindowStyle", "Hidden",
                          "-Command", ps], creationflags=flags, close_fds=True,
                         stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    import threading
    threading.Timer(1.2, quit_app).start()                    # Oberfläche kann „Wird entfernt“ noch zeigen
    return {"ok": True}


def info() -> dict:
    ok, why = can_uninstall()
    return {"possible": ok, "reason": why, "dataDir": str(paths.USER_DIR).replace(str(Path.home()), "~"),
            "os": "mac" if paths.IS_MAC else "win" if paths.IS_WIN else "other"}
