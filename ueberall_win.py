"""„Überall vorlesen“ unter Windows (Version 3.0, Teil C) – nur Standardbibliothek (ctypes), keine neue Abhängigkeit.

- Tastenkürzel (Vorgabe Strg+Alt+V, änderbar) per RegisterHotKey in einem eigenen Thread mit Nachrichtenschleife
- markierten Text holen: warten, bis die Zusatztasten losgelassen sind, Strg+C senden, Zwischenablage lesen, die alte
  Zwischenablage des Nutzers zurücklegen
- kein Infobereich-Symbol (bräuchte eine neue Abhängigkeit): das Kürzel wirkt, solange Vorleser offen ist (auch minimiert)

Am Mac nicht testbar – Logik bewusst einfach gehalten, Fehler landen im Log (meldungen.loggen), nie in einer Ausnahme.
"""
from __future__ import annotations

import ctypes
import threading
import time
from ctypes import wintypes

import meldungen

WM_HOTKEY, WM_QUIT, WM_APP = 0x0312, 0x0012, 0x8000
WM_NEU = WM_APP + 1                  # „Kürzel neu anmelden“ an den eigenen Thread
MOD_ALT, MOD_CONTROL, MOD_SHIFT, MOD_WIN, MOD_NOREPEAT = 0x1, 0x2, 0x4, 0x8, 0x4000
VK_SHIFT, VK_CONTROL, VK_MENU, VK_LWIN, VK_RWIN, VK_C = 0x10, 0x11, 0x12, 0x5B, 0x5C, 0x43
KEYEVENTF_KEYUP = 0x2
CF_UNICODETEXT, GMEM_MOVEABLE = 13, 0x2
HOTKEY_ID = 0x5601


def vk_code(code: str) -> int | None:
    """KeyboardEvent.code → Windows Virtual-Key."""
    if code.startswith("Key") and len(code) == 4:
        return ord(code[3])
    if code.startswith("Digit") and len(code) == 6:
        return ord(code[5])
    if code.startswith("F") and code[1:].isdigit() and 1 <= int(code[1:]) <= 12:
        return 0x70 + int(code[1:]) - 1
    return None


def mods(hk: dict) -> int:
    return ((MOD_CONTROL if hk.get("ctrl") else 0) | (MOD_ALT if hk.get("alt") else 0)
            | (MOD_SHIFT if hk.get("shift") else 0) | (MOD_WIN if hk.get("meta") else 0) | MOD_NOREPEAT)


class Kuerzel:
    """Thread mit eigener Nachrichtenschleife – RegisterHotKey gilt nur für den Thread, der es aufruft."""

    def __init__(self, hotkey, ausloesen, belegt):
        self.hotkey, self.ausloesen, self.belegt = hotkey, ausloesen, belegt   # hotkey() → aktuelles dict
        self.tid = None
        threading.Thread(target=self._lauf, daemon=True, name="vorleser-kuerzel").start()

    def _anmelden(self, u32) -> None:
        u32.UnregisterHotKey(None, HOTKEY_ID)
        hk = self.hotkey()
        vk = vk_code(hk["code"])
        if vk is None or not u32.RegisterHotKey(None, HOTKEY_ID, mods(hk), vk):
            print(f"[überall] Kürzel {hk} belegt oder ungültig", flush=True)
            self.belegt()

    def _lauf(self) -> None:
        try:
            u32 = ctypes.windll.user32
            self.tid = ctypes.windll.kernel32.GetCurrentThreadId()
            self._anmelden(u32)
            msg = wintypes.MSG()
            while u32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
                if msg.message == WM_HOTKEY and msg.wParam == HOTKEY_ID:
                    threading.Thread(target=self.ausloesen, daemon=True).start()
                elif msg.message == WM_NEU:
                    self._anmelden(u32)
            u32.UnregisterHotKey(None, HOTKEY_ID)
        except Exception as e:
            meldungen.loggen("windows-kürzel", e)

    def neu_anmelden(self) -> None:
        if self.tid:
            ctypes.windll.user32.PostThreadMessageW(self.tid, WM_NEU, 0, 0)

    def beenden(self) -> None:
        if self.tid:
            ctypes.windll.user32.PostThreadMessageW(self.tid, WM_QUIT, 0, 0)


# --------------------------------------------------------------------------- #
# Zwischenablage (nur Text)
# --------------------------------------------------------------------------- #
def _oeffnen(u32) -> bool:
    for _ in range(20):                                   # eine andere App kann sie kurz offen halten
        if u32.OpenClipboard(None):
            return True
        time.sleep(0.02)
    return False


def ablage_lesen() -> str | None:
    u32, k32 = ctypes.windll.user32, ctypes.windll.kernel32
    u32.GetClipboardData.restype = ctypes.c_void_p
    k32.GlobalLock.restype = ctypes.c_void_p
    k32.GlobalLock.argtypes = [ctypes.c_void_p]
    k32.GlobalUnlock.argtypes = [ctypes.c_void_p]
    if not _oeffnen(u32):
        return None
    try:
        h = u32.GetClipboardData(CF_UNICODETEXT)
        if not h:
            return None
        p = k32.GlobalLock(h)
        try:
            return ctypes.wstring_at(p) if p else None
        finally:
            k32.GlobalUnlock(h)
    finally:
        u32.CloseClipboard()


def ablage_schreiben(text: str) -> None:
    u32, k32 = ctypes.windll.user32, ctypes.windll.kernel32
    k32.GlobalAlloc.restype = ctypes.c_void_p
    k32.GlobalLock.restype = ctypes.c_void_p
    k32.GlobalLock.argtypes = [ctypes.c_void_p]
    k32.GlobalUnlock.argtypes = [ctypes.c_void_p]
    u32.SetClipboardData.argtypes = [wintypes.UINT, ctypes.c_void_p]
    data = (text + "\0").encode("utf-16-le")
    if not _oeffnen(u32):
        return
    try:
        u32.EmptyClipboard()
        h = k32.GlobalAlloc(GMEM_MOVEABLE, len(data))
        p = k32.GlobalLock(h)
        ctypes.memmove(p, data, len(data))
        k32.GlobalUnlock(h)
        u32.SetClipboardData(CF_UNICODETEXT, h)
    finally:
        u32.CloseClipboard()


def markierung_holen() -> str | None:
    """Strg+C an die vordere App senden und die neue Zwischenablage lesen. Vorherigen Text zurücklegen."""
    u32 = ctypes.windll.user32
    # erst warten, bis Strg/Alt/Umschalt/Win losgelassen sind (bis 0,6 s) – sonst käme z. B. Strg+Alt+C an
    for _ in range(30):
        if not any(u32.GetAsyncKeyState(k) & 0x8000 for k in (VK_SHIFT, VK_CONTROL, VK_MENU, VK_LWIN, VK_RWIN)):
            break
        time.sleep(0.02)
    vorher_nr, alt = u32.GetClipboardSequenceNumber(), ablage_lesen()
    for vk, flag in ((VK_CONTROL, 0), (VK_C, 0), (VK_C, KEYEVENTF_KEYUP), (VK_CONTROL, KEYEVENTF_KEYUP)):
        u32.keybd_event(vk, 0, flag, 0)
    for _ in range(50):                                   # bis 1 s auf die Kopie warten
        time.sleep(0.02)
        if u32.GetClipboardSequenceNumber() != vorher_nr:
            break
    if u32.GetClipboardSequenceNumber() == vorher_nr:
        return None
    time.sleep(0.03)
    text = ablage_lesen()
    if alt is not None:                                   # Zwischenablage des Nutzers nicht überschreiben
        try:
            ablage_schreiben(alt)
        except Exception as e:
            meldungen.loggen("zwischenablage zurücklegen", e)
    return (text or "").strip() or None


def bildschirm_breite() -> int:
    try:
        return int(ctypes.windll.user32.GetSystemMetrics(0))
    except Exception:
        return 1280
