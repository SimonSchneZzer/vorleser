#!/usr/bin/env python3
"""„Überall vorlesen“ und Einzelstart auf einem echten Windows-Rechner prüfen (läuft im Build auf windows-latest).

  python packaging/test_ueberall_windows.py <Pfad zu Vorleser.exe>

Spielt durch, was ein Tester gemeldet hat (11.11.2026: zwei Vorleser gleichzeitig, „Kein markierter Text gefunden“):
  1. zweiter Start → darf keinen zweiten Vorleser öffnen, sondern beendet sich (bestehendes Fenster nach vorne)
  2. Text im Vorleser-Fenster markieren (Strg+A) + Kürzel Strg+Alt+V → Mini-Player mit Text aus dem Fenster
  3. Text in Notepad markieren + Kürzel → Text per Strg+C, die Zwischenablage des Nutzers bleibt erhalten
  4. Beenden und sofort neu starten → derselbe Port (sonst wären Einstellungen im Fenster-Speicher weg)
Tasten werden wie echte Eingaben gesendet (keybd_event). Nur Standardbibliothek. Exit-Code ≠ 0, wenn etwas nicht klappt.
"""
from __future__ import annotations

import ctypes
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
from ctypes import wintypes
from pathlib import Path

TMP = Path(os.environ.get("RUNNER_TEMP") or tempfile.gettempdir()) / "vorleser-ueberall-test"
HOME = TMP / "home"
PORT = 8797
LOG = HOME / "data" / "server.log"

u32 = ctypes.windll.user32
k32 = ctypes.windll.kernel32
VK_CONTROL, VK_MENU, VK_A, VK_V = 0x11, 0x12, 0x41, 0x56
KEYUP = 0x2
fehler: list[str] = []


def log(msg: str) -> None:
    print(f"[test {time.strftime('%H:%M:%S')}] {msg}", flush=True)


def pruefe(ok: bool, was: str) -> None:
    log(("OK    " if ok else "FEHLER ") + was)
    if not ok:
        fehler.append(was)


def start(exe: Path) -> subprocess.Popen:
    p = subprocess.Popen([str(exe)], env=dict(os.environ, VORLESER_HOME=str(HOME), VORLESER_PORT=str(PORT)),
                         cwd=str(exe.parent))
    log(f"Vorleser gestartet (PID {p.pid})")
    return p


def api(method: str, path: str, body: dict | None = None, timeout: float = 10):
    token = (HOME / "data" / "api-token").read_text("utf-8").strip()
    req = urllib.request.Request(f"http://127.0.0.1:{PORT}{path}", method=method,
                                 data=json.dumps(body or {}).encode() if method != "GET" else None,
                                 headers={"X-Vorleser-Token": token, "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read() or b"{}")


def wait_up(timeout: float = 120) -> None:
    end, last = time.time() + timeout, None
    while time.time() < end:
        try:
            api("GET", "/api/update")
            return
        except Exception as e:
            last = e
            time.sleep(1)
    raise TimeoutError(f"Vorleser antwortet nicht auf Port {PORT} ({last!r})")


def wait_down(timeout: float = 60) -> None:
    end = time.time() + timeout
    while time.time() < end:
        try:
            api("GET", "/api/update", timeout=2)
            time.sleep(0.5)
        except Exception:
            return
    raise TimeoutError("Vorleser beendet sich nicht")


def log_text() -> str:
    try:
        return LOG.read_text("utf-8", errors="replace")
    except OSError:
        return ""


def warte_log(muster: str, ab: int, timeout: float = 15) -> str | None:
    """Erste neue Log-Zeile (nach Position `ab`), die `muster` enthält."""
    end = time.time() + timeout
    while time.time() < end:
        for zeile in log_text()[ab:].splitlines():
            if muster in zeile:
                return zeile
        time.sleep(0.3)
    return None


def fenster_von(pid: int, timeout: float = 30) -> int:
    """Sichtbares Hauptfenster eines Prozesses (Vorleser: auch die WebView-Kindprozesse gehören nicht dazu)."""
    gefunden = []
    PROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    def cb(hwnd, _):
        p = wintypes.DWORD()
        u32.GetWindowThreadProcessId(hwnd, ctypes.byref(p))
        if p.value == pid and u32.IsWindowVisible(hwnd) and u32.GetWindowTextLengthW(hwnd) > 0 \
                and not u32.GetWindow(hwnd, 4):                      # GW_OWNER: nur Hauptfenster
            gefunden.append(hwnd)
        return True
    end = time.time() + timeout
    while time.time() < end:
        gefunden.clear()
        u32.EnumWindows(PROC(cb), 0)
        if gefunden:
            return gefunden[0]
        time.sleep(0.5)
    return 0


def nach_vorne(hwnd: int) -> bool:
    """SetForegroundWindow klappt nur, wenn wir selbst „vorne“ sind → an den Eingabe-Thread des Vordergrunds hängen."""
    vorne = u32.GetForegroundWindow()
    a = u32.GetWindowThreadProcessId(vorne, None)
    b = k32.GetCurrentThreadId()
    u32.AttachThreadInput(b, a, True)
    u32.ShowWindow(hwnd, 9)                       # SW_RESTORE
    u32.BringWindowToTop(hwnd)
    u32.SetForegroundWindow(hwnd)
    u32.AttachThreadInput(b, a, False)
    time.sleep(0.5)
    return u32.GetForegroundWindow() == hwnd


def tasten(*vks: int, halten: float = 0.15) -> None:
    for vk in vks:
        u32.keybd_event(vk, 0, 0, 0)
        time.sleep(0.03)
    time.sleep(halten)
    for vk in reversed(vks):
        u32.keybd_event(vk, 0, KEYUP, 0)
        time.sleep(0.03)


def vorlese_versuch(hwnd: int, name: str, quelle: str) -> None:
    pruefe(nach_vorne(hwnd), f"{name} ist vorne")
    tasten(VK_CONTROL, VK_A)                      # alles markieren
    time.sleep(0.5)
    ab = len(log_text())
    tasten(VK_CONTROL, VK_MENU, VK_V, halten=0.3)  # Kürzel Strg+Alt+V (Vorgabe)
    zeile = warte_log("[überall] vorlesen:", ab) or warte_log("[überall] kein markierter Text", ab, 1)
    log(f"Log: {zeile}")
    pruefe(bool(zeile) and f"({quelle})" in zeile, f"{name}: markierter Text kommt an ({quelle})")


def ablage(text: str | None = None) -> str | None:
    """Zwischenablage lesen/schreiben über PowerShell (unabhängig vom Code unter Test)."""
    if text is None:
        r = subprocess.run(["powershell", "-NoProfile", "-Command", "Get-Clipboard -Raw"],
                           capture_output=True, text=True, timeout=30)
        return r.stdout.rstrip("\r\n")
    subprocess.run(["powershell", "-NoProfile", "-Command", f"Set-Clipboard -Value '{text}'"], timeout=30)
    return None


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    exe = Path(sys.argv[1]).resolve()
    shutil.rmtree(TMP, ignore_errors=True)
    HOME.mkdir(parents=True)
    notepad = None
    try:
        erster = start(exe)
        wait_up()
        hwnd = fenster_von(erster.pid)
        pruefe(bool(hwnd), "Vorleser-Fenster sichtbar")
        time.sleep(5)                                       # Oberfläche + Kürzel fertig einrichten lassen

        # 1. zweiter Start
        ab = len(log_text())
        zweiter = start(exe)
        try:
            zweiter.wait(30)
            beendet = True
        except subprocess.TimeoutExpired:
            beendet = False
        pruefe(beendet, "zweiter Start beendet sich von selbst")
        pruefe(bool(warte_log("läuft schon", ab, 5)), "zweiter Start erkennt den laufenden Vorleser")
        pruefe(erster.poll() is None, "erster Vorleser läuft weiter")
        if not beendet:
            zweiter.kill()

        # 2. Markierung im Vorleser-Fenster
        if hwnd:
            vorlese_versuch(hwnd, "Vorleser-Fenster", "Fenster")

        # 3. Markierung in Notepad (Strg+C), Zwischenablage bleibt
        datei = TMP / "notiz.txt"
        datei.write_text("Hallo aus dem Editor. Dieser Satz soll vorgelesen werden.", "utf-8")
        ablage("Zwischenablage vorher")
        notepad = subprocess.Popen(["notepad.exe", str(datei)])
        time.sleep(3)
        nhwnd = fenster_von(notepad.pid, 20)
        if not nhwnd:                                       # neues Notepad (Windows 11) läuft in einem anderen Prozess
            r = subprocess.run(["powershell", "-NoProfile", "-Command",
                                "(Get-Process notepad | Where-Object { $_.MainWindowHandle -ne 0 } | Select-Object -First 1).MainWindowHandle"],
                               capture_output=True, text=True, timeout=30)
            nhwnd = int(r.stdout.strip() or 0)
        pruefe(bool(nhwnd), "Notepad-Fenster gefunden")
        if nhwnd:
            vorlese_versuch(nhwnd, "Notepad", "Kopie")
            time.sleep(1)
            pruefe(ablage() == "Zwischenablage vorher", "Zwischenablage des Nutzers zurückgelegt")

        # 4. Beenden + sofort neu starten → derselbe Port
        try:
            api("POST", "/api/quit")
        except Exception:
            pass
        wait_down()
        try:
            erster.wait(30)
        except subprocess.TimeoutExpired:
            pass
        dritter = start(exe)
        try:
            wait_up(90)
            pruefe(True, f"Neustart direkt danach wieder auf Port {PORT}")
        except TimeoutError as e:
            pruefe(False, f"Neustart direkt danach wieder auf Port {PORT} ({e})")
        try:
            api("POST", "/api/quit")
        except Exception:
            pass
        try:
            dritter.wait(30)
        except subprocess.TimeoutExpired:
            pass
    except Exception as e:
        pruefe(False, f"Ablauf abgebrochen: {e!r}")
    finally:
        if notepad:
            notepad.kill()
        subprocess.run(["taskkill", "/F", "/IM", "notepad.exe"], capture_output=True)
        subprocess.run(["taskkill", "/F", "/IM", "Vorleser.exe", "/T"], capture_output=True)
        print("\n===== server.log (Ende) =====", flush=True)
        print("\n".join(log_text().splitlines()[-60:]), flush=True)
    log("alles gut" if not fehler else f"{len(fehler)} Fehler: " + "; ".join(fehler))
    return 1 if fehler else 0


if __name__ == "__main__":
    sys.exit(main())
