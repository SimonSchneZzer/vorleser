"""Fehler → Text für die Oberfläche. Ein Ort für alle Meldungen, die Nutzer sehen.

Regel: In der Oberfläche landen nur feste deutsche Sätze (in static/i18n.js übersetzt), nie rohe Exception-Texte.
Details (Traceback, englische Bibliotheksmeldungen) gehen ins Log – „Fehler melden“ schickt die letzten Log-Zeilen mit.
Absichtliche Meldungen aus dem eigenen Code: `raise Meldung("…")` (oder ValueError/ImportFailed mit deutschem Text).
"""
from __future__ import annotations

import errno
import json
import socket
import traceback
import urllib.error

INTERN = "Unerwarteter Fehler – die Details stehen im Log. Über „Fehler melden“ kannst du sie mitschicken."
PLATTE = "Kein Speicherplatz mehr frei – unter Einstellungen › Speicher kannst du Audio löschen."
RECHTE = "Keine Schreibrechte im Datenordner von Vorleser."
OFFLINE = "Keine Internetverbindung – bitte später noch einmal versuchen."
AUDIO = "Audio konnte nicht umgewandelt werden."
ANFRAGE = "Ungültige Anfrage"
NICHT_GEFUNDEN = "Nicht gefunden"

ALLE = (INTERN, PLATTE, RECHTE, OFFLINE, AUDIO, ANFRAGE, NICHT_GEFUNDEN)


class Meldung(RuntimeError):
    """Fehler, dessen Text so in der Oberfläche erscheinen darf (deutsch, in static/i18n.js übersetzt)."""


class FFmpegFehler(RuntimeError):
    """ffmpeg ist gescheitert – Text enthält dessen Ausgabe (nur fürs Log)."""


def _netz(e: BaseException) -> bool:
    if isinstance(e, (urllib.error.URLError, socket.gaierror, ConnectionError, TimeoutError)):
        return True
    try:                                              # edge-tts / Whisper-Download nutzen aiohttp bzw. requests
        import aiohttp
        if isinstance(e, aiohttp.ClientError):
            return True
    except ImportError:
        pass
    return type(e).__module__.split(".")[0] in ("requests", "httpx", "huggingface_hub") and "connect" in str(e).lower()


def fuer_nutzer(e: BaseException) -> str:
    """Fester, übersetzbarer Text für die Oberfläche."""
    if isinstance(e, (json.JSONDecodeError, UnicodeDecodeError)):
        return ANFRAGE
    if isinstance(e, Meldung):
        return str(e)
    if isinstance(e, KeyError):
        return NICHT_GEFUNDEN
    if isinstance(e, ValueError):                     # eigene ValueErrors tragen deutsche Sätze …
        s = str(e)
        return ANFRAGE if s.startswith(("invalid literal", "could not convert")) or not s else s   # … Bibliotheken nicht
    if isinstance(e, OSError) and e.errno == errno.ENOSPC:
        return PLATTE
    if isinstance(e, PermissionError) or (isinstance(e, OSError) and e.errno in (errno.EACCES, errno.EROFS)):
        return RECHTE
    if isinstance(e, FFmpegFehler):
        return AUDIO
    if _netz(e):
        return OFFLINE
    if type(e).__name__ == "ImportFailed":            # importers.ImportFailed (ohne Import-Kreis)
        return str(e)
    return INTERN


def loggen(wo: str, e: BaseException) -> None:
    """Fehler mit Traceback ins Log (server.log) – damit „Fehler melden“ wirklich hilft."""
    print(f"[{wo}] Fehler: {e!r}", flush=True)
    traceback.print_exception(type(e), e, e.__traceback__)
