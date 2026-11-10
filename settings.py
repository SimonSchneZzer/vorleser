"""Einstellungen (data/settings.json): Darstellung, Markierung, Standardstimmen, Cache-Grenze."""
from __future__ import annotations

import json
import os
import re
import threading
from paths import DATA_DIR

PATH = DATA_DIR / "settings.json"
_lock = threading.Lock()

DEFAULTS = {
    "theme": "system",         # light | dark | system
    "accent": "#0F6A80",       # Preset (Hell-Variante) oder eigene Farbe
    "mark": "word",            # section | sentence | word
    "uiLang": "de",            # Sprache der Oberfläche: de | en
    "onboarded": False,        # Einrichtung + Tutorial beim ersten Öffnen erledigt?
    "defaultVoices": {},       # {"de": "edge:…", "en": "…"}
    "favorites": None,         # Voice-IDs fürs Player-Menü (None = noch nie gesetzt → Vorschlag)
    "ahead": "normal",         # wie viel im Voraus erzeugt wird: low (1) | normal (3) | high (10) | all (ganzer Text)
    "cacheMB": int(os.environ.get("VORLESER_CACHE_MB", "500")),
    "background": True,        # Fenster schließen → Vorleser läuft in der Menüleiste weiter (für ⌃⌥V), Version 3.0
    "bgHintSeen": False,       # Hinweis beim ersten Schließen schon gezeigt?
    "recap": True,             # „Was bisher geschah“: nach > 1 Tag Pause die letzten zwei Absätze wiederholen
    # Tastenkürzel „Markierten Text vorlesen“ (Version 3.0) – plattformneutral: KeyboardEvent.code + Zusatztasten
    "hotkey": {"code": "KeyV", "ctrl": True, "alt": True, "shift": False, "meta": False},
    "ambient": "aus",          # Atmosphäre unter der Stimme: aus | regen | kamin | cafe | wald | rauschen
    "ambientVol": 35,          # Lautstärke der Atmosphäre in Prozent (0–100)
}
CHOICES = {"theme": ("light", "dark", "system"), "mark": ("section", "sentence", "word"), "uiLang": ("de", "en"),
           "ahead": ("low", "normal", "high", "all"), "ambient": ("aus", "regen", "kamin", "cafe", "wald", "rauschen")}
DEFAULT_FAVORITES = ["edge:de-DE-SeraphinaMultilingualNeural", "edge:de-DE-ConradNeural", "edge:de-DE-KatjaNeural",
                     "edge:en-US-AvaMultilingualNeural", "edge:en-US-AndrewMultilingualNeural", "edge:en-GB-SoniaNeural"]


def valid_hotkey(v) -> bool:
    """Buchstabe/Ziffer/F-Taste und mindestens Strg/⌃, Alt/⌥ oder ⌘ – sonst würde eine normale Taste abgefangen."""
    return (isinstance(v, dict) and isinstance(v.get("code"), str)
            and re.fullmatch(r"Key[A-Z]|Digit[0-9]|F([1-9]|1[0-2])", v["code"]) is not None
            and any(v.get(m) is True for m in ("ctrl", "alt", "meta")))


def load() -> dict:
    with _lock:
        try:
            data = json.loads(PATH.read_text("utf-8"))
        except (OSError, ValueError):
            data = {}
    out = {**DEFAULTS, **{k: v for k, v in data.items() if k in DEFAULTS}}
    if out["favorites"] is None:
        out["favorites"] = list(DEFAULT_FAVORITES)
    return out


def get(key: str):
    return load()[key]


def update(patch: dict) -> dict:
    cur = load()
    for k, v in patch.items():
        if k in CHOICES and v in CHOICES[k]:
            cur[k] = v
        elif k == "accent" and isinstance(v, str) and re.fullmatch(r"#[0-9a-fA-F]{6}", v):
            cur[k] = v.upper()
        elif k == "cacheMB" and isinstance(v, (int, float)) and 50 <= v <= 100_000:
            cur[k] = int(v)
        elif k in ("background", "bgHintSeen", "recap") and isinstance(v, bool):
            cur[k] = v
        elif k == "ambientVol" and isinstance(v, (int, float)) and not isinstance(v, bool) and 0 <= v <= 100:
            cur[k] = int(v)
        elif k == "hotkey" and valid_hotkey(v):
            cur[k] = {"code": v["code"], **{m: bool(v.get(m)) for m in ("ctrl", "alt", "shift", "meta")}}
        elif k == "onboarded" and isinstance(v, bool):
            cur[k] = v
        elif k == "favorites" and isinstance(v, list):
            cur[k] = list(dict.fromkeys(str(x) for x in v))[:200]
        elif k == "defaultVoices" and isinstance(v, dict):
            cur[k] = {**cur["defaultVoices"], **{str(a): str(b) for a, b in v.items()}}
    with _lock:
        PATH.parent.mkdir(parents=True, exist_ok=True)
        tmp = PATH.with_suffix(".tmp")
        tmp.write_text(json.dumps(cur, ensure_ascii=False, indent=2), "utf-8")
        tmp.replace(PATH)
    return cur
