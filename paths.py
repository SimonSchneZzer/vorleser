"""Wo liegt was? Programmdateien vs. Benutzerdaten – für Entwicklung und fertige Desktop-App.

Entwicklung (./start.sh):  alles im Projektordner wie bisher (data/, cache/, voices/, .venv-clone/).
Desktop-App (PyInstaller): Programm schreibgeschützt im App-Paket, Daten im Benutzerordner:
    macOS:   ~/Library/Application Support/Vorleser
    Windows: %APPDATA%\\Vorleser
Mit VORLESER_HOME lässt sich der Datenordner überall festlegen.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

FROZEN = getattr(sys, "frozen", False)
IS_WIN = sys.platform == "win32"
IS_MAC = sys.platform == "darwin"

# Mitgelieferte, nur lesbare Dateien (static/, clone_worker.py, mitgelieferte Piper-Stimmen)
APP_DIR = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))


def _user_dir() -> Path:
    if os.environ.get("VORLESER_HOME"):
        return Path(os.environ["VORLESER_HOME"]).expanduser()
    if not FROZEN:
        return APP_DIR
    if IS_WIN:
        return Path(os.environ.get("APPDATA") or Path.home() / "AppData" / "Roaming") / "Vorleser"
    if IS_MAC:
        return Path.home() / "Library" / "Application Support" / "Vorleser"
    return Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share") / "Vorleser"


USER_DIR = _user_dir()
DATA_DIR = USER_DIR / "data"
CACHE_DIR = USER_DIR / "cache"
STATIC_DIR = APP_DIR / "static"
BUNDLED_VOICES = APP_DIR / "voices"          # mitgelieferte Piper-Stimmen (Offline-Ersatz)
USER_VOICES = USER_DIR / "voices"             # nachinstallierte Piper-Stimmen
CLONE_ENV = USER_DIR / (".venv-clone" if not FROZEN else "clone-env")
CLONE_PY = CLONE_ENV / ("Scripts/python.exe" if IS_WIN else "bin/python")
CLONE_WORKER = APP_DIR / "clone_worker.py"
CLONE_MODELS = USER_DIR / "clone-models"     # Chatterbox-Modell (nur App; Entwicklung: HF-Standardcache)
LOG_FILE = DATA_DIR / "server.log"
try:
    APP_VERSION = os.environ.get("VORLESER_VERSION") or (APP_DIR / "VERSION").read_text("utf-8").strip()
except OSError:
    APP_VERSION = "0.0.0"

# In der App alle Modelle (Whisper, Chatterbox) im eigenen Ordner halten → sauber deinstallierbar
if FROZEN:
    os.environ.setdefault("HF_HOME", str(USER_DIR / "models"))
    # HTTPS-Stammzertifikate: Das Python des macOS-Build-Runners (python.org) nutzt nicht die Zertifikate von
    # macOS – urllib (Updater) scheiterte dann an jeder HTTPS-Verbindung. certifi liegt ohnehin in der App.
    try:
        import certifi
        os.environ.setdefault("SSL_CERT_FILE", certifi.where())
    except ImportError:
        pass


def clone_env() -> dict:
    """Umgebung für Prozesse der Klon-Umgebung (eigener Modellordner in der App)."""
    env = {**os.environ, "PYTHONUTF8": "1", "VORLESER_PARENT_PID": str(os.getpid())}
    if FROZEN:
        env["HF_HOME"] = str(CLONE_MODELS)
    return env


for _d in (DATA_DIR, CACHE_DIR, USER_VOICES):
    _d.mkdir(parents=True, exist_ok=True)

# Unter Windows sonst bei jedem ffmpeg-/Worker-Aufruf ein aufblitzendes Konsolenfenster
NO_WINDOW = {"creationflags": 0x08000000} if IS_WIN else {}   # CREATE_NO_WINDOW
