"""Anonymes Mitzählen (Version 3.3): Wie viele Leute nutzen den Vorleser?

Die App meldet höchstens **einmal pro Kalenderwoche** „aktiv“ (mit System und Version) und **einmal pro Installation**
„neu“ an den GoatCounter auf simon.schnetzer.at (`/c/count`). Keine Kennung, kein Konto, keine Texte, keine Stimmen –
nur der Pfad, z. B. `/app/aktiv/mac/3.3.0`. Abschaltbar in Einstellungen › App („Anonyme Statistik“, Einstellung `count`).

Wöchentlich aktive Nutzer = Summe der `/app/aktiv/…`-Aufrufe einer Kalenderwoche (UTC); Neuinstallationen = `/app/neu/…`.
Nur in der gebauten App (Entwicklung und Tests zählen nie; zum Ausprobieren `VORLESER_ZAEHLER_URL` setzen).
"""
from __future__ import annotations

import json
import os
import threading
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone

import paths

# Nie aus der CI (GitHub Actions setzt CI=true; dort startet die gebaute App für Tests) und nie aus dem Quellcode
URL = os.environ.get("VORLESER_ZAEHLER_URL") or (
    "https://simon.schnetzer.at/c/count" if paths.FROZEN and not os.environ.get("CI") else "")
STATE = paths.DATA_DIR / "zaehler.json"       # {"neu": true, "woche": "2026-W47"} – was schon gemeldet wurde
SYSTEM = "mac" if paths.IS_MAC else "windows" if paths.IS_WIN else "linux"
FIRST_DELAY = 30                              # Sekunden nach dem Start (Start nicht ausbremsen)
EVERY = 6 * 3600                              # läuft die App tagelang in der Menüleiste: neue Woche trotzdem melden
_lock = threading.Lock()


def week(now: datetime | None = None) -> str:
    y, w, _ = (now or datetime.now(timezone.utc)).isocalendar()
    return f"{y}-W{w:02d}"


def wanted() -> bool:
    try:
        import settings                       # erst hier: Tests setzen den Datenordner vorher
        return settings.get("count") is not False
    except Exception:
        return True


def _load() -> dict:
    try:
        d = json.loads(STATE.read_text("utf-8"))
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def _save(d: dict) -> None:
    tmp = STATE.with_suffix(".tmp")
    tmp.write_text(json.dumps(d), "utf-8")
    tmp.replace(STATE)


def _send(path: str) -> bool:
    q = urllib.parse.urlencode({"p": path, "t": "Vorleser App"})
    req = urllib.request.Request(f"{URL}?{q}", headers={"User-Agent": f"Vorleser/{paths.APP_VERSION} ({SYSTEM})"})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return 200 <= r.status < 300
    except Exception as e:                    # offline o. Ä.: still, nächster Versuch beim nächsten Durchlauf
        print(f"[zaehler] nicht gesendet ({type(e).__name__})", flush=True)
        return False


def step() -> list[str]:
    """Meldet, was fällig ist (Installationen von vor 3.3 hat `start_background` schon als „neu“ abgehakt).
    Gibt die gesendeten Pfade zurück (für Tests)."""
    if not URL or not wanted():
        return []
    sent = []
    with _lock:
        d = _load()
        if not d.get("neu"):
            if _send(f"/app/neu/{SYSTEM}"):
                d["neu"] = True
                sent.append(f"/app/neu/{SYSTEM}")
                _save(d)
        w = week()
        if d.get("woche") != w:
            p = f"/app/aktiv/{SYSTEM}/{paths.APP_VERSION}"
            if _send(p):
                d["woche"] = w
                sent.append(p)
                _save(d)
    return sent


def start_background() -> None:
    """Beim Start aufrufen, **bevor** der Updater `last-version` schreibt: daran erkennen wir Installationen von vor 3.3."""
    if not URL:
        return
    if not STATE.exists():
        # Gleich festhalten: Ein frischer Rechner, der beim ersten Start offline ist, darf beim nächsten Start
        # (dann gibt es last-version schon) nicht als alte Installation gelten.
        try:
            _save({"neu": True} if (paths.DATA_DIR / "last-version").exists() else {})
        except OSError:
            return

    def loop():
        time.sleep(FIRST_DELAY)
        while True:
            try:
                step()
            except Exception as e:
                print(f"[zaehler] {type(e).__name__}", flush=True)
            time.sleep(EVERY)
    threading.Thread(target=loop, daemon=True).start()
