"""Fehler melden: technische Infos für das Formular in der App.

Gesendet wird vom Formular selbst an Web3Forms (https://web3forms.com) – wie ein normales Webformular.
Der Access Key kann nur an die hinterlegte Adresse senden; die Adresse selbst steht nirgends in der App.
Ist der Key leer, blendet die Oberfläche „Fehler melden“ aus.
"""
from __future__ import annotations

import platform
import re

import paths

WEB3FORMS_KEY = "b8bf57d6-9254-472a-8d37-72aac7141ccd"
ENDPOINT = "https://api.web3forms.com/submit"
LOG_LINES = 150
LOG_CHARS = 6000
# Zeilen ohne Aussagekraft (Seitenabrufe), und persönliche Pfade unkenntlich machen
_NOISE = re.compile(r'"(GET|PATCH) /')
_DIGITS = re.compile(r"\d+(?:[.,]\d+)?")


def system() -> str:
    if paths.IS_MAC:
        name = f"macOS {platform.mac_ver()[0]}"
    elif paths.IS_WIN:
        name = f"Windows {platform.release()} ({platform.version()})"
    else:
        name = f"{platform.system()} {platform.release()}"
    return f"{name}, {platform.machine()}"


def _scrub(text: str) -> str:
    home = str(paths.USER_DIR.home())
    return text.replace(home, "~")


def collapse(lines: list[str]) -> list[str]:
    """Aufeinanderfolgende gleichartige Zeilen (nur Zahlen verschieden) zusammenfassen:
    10× „[edge] 56 Zeichen in 1.05s“ → „[edge] 56 Zeichen in 1.05s  (×10)“ – mehr Platz für Nützliches."""
    out: list[str] = []
    prev_key, count = None, 0
    for line in lines:
        key = _DIGITS.sub("#", line)
        if key == prev_key:
            count += 1
            out[-1] = f"{line}  (×{count})"
        else:
            out.append(line)
            prev_key, count = key, 1
    return out


def log_tail() -> str:
    try:
        lines = paths.LOG_FILE.read_text("utf-8", errors="replace").splitlines()
    except OSError:
        return ""
    keep = collapse([l for l in lines if not _NOISE.search(l)])[-LOG_LINES:]
    return _scrub("\n".join(keep))[-LOG_CHARS:]


def info() -> dict:
    return {
        "enabled": bool(WEB3FORMS_KEY),
        "key": WEB3FORMS_KEY,
        "endpoint": ENDPOINT,
        "version": paths.APP_VERSION,
        "system": system(),
        "mode": "Desktop-App" if paths.FROZEN else "Entwicklung",
        "log": log_tail(),
    }
