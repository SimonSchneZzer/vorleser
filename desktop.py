#!/usr/bin/env python3
"""Vorleser als Desktop-App (macOS + Windows): eigenes Fenster statt Browser-Tab.

Startet den lokalen Server im Hintergrund und zeigt die Oberfläche in einem nativen
Fenster (macOS: WebKit, Windows: Edge WebView2). Schließen des Fensters beendet alles.
Entwicklung:  .venv/bin/python desktop.py   (braucht `pywebview`)
"""
from __future__ import annotations

import json
import os
import re
import shutil
import sys
import threading
import urllib.request

import paths

# In der App gibt es keine Konsole: alle Ausgaben ins Log (vor allen anderen Importen)
if paths.FROZEN:
    _log = open(paths.LOG_FILE, "a", encoding="utf-8", buffering=1)
    sys.stdout = sys.stderr = _log

import webview  # noqa: E402

import exporter  # noqa: E402
import server  # noqa: E402

TITLE = "Vorleser"
window: webview.Window | None = None


def _existing_instance(port: int) -> bool:
    """Läuft schon ein Vorleser auf diesem Port?"""
    try:
        with urllib.request.urlopen(f"http://{server.HOST}:{port}/api/settings", timeout=2) as r:
            return "theme" in json.loads(r.read())
    except Exception:
        return False


class Api:
    """Aus der Oberfläche aufrufbar: window.pywebview.api.<name>(…)"""

    def save_export(self, doc_id: str) -> dict:
        if not re.fullmatch(r"[0-9a-f]{32}", doc_id or ""):
            return {"ok": False, "error": "ungültig"}
        st = exporter.status(doc_id)
        if st.get("status") != "ready":
            return {"ok": False, "error": "Export nicht fertig"}
        fmt = st["format"]
        src = exporter.export_path(doc_id, fmt)
        try:
            title = server.load_doc(doc_id)["title"]
        except KeyError:
            title = "Hörbuch"
        name = re.sub(r'[\\/:*?"<>|]+', "_", title).strip() or "Hörbuch"
        res = window.create_file_dialog(webview.SAVE_DIALOG, directory=os.path.expanduser("~/Downloads"),
                                        save_filename=f"{name}.{fmt}")
        if not res:
            return {"ok": False, "cancelled": True}
        dest = res if isinstance(res, str) else res[0]
        if not dest.lower().endswith(f".{fmt}"):
            dest += f".{fmt}"
        shutil.copyfile(src, dest)
        return {"ok": True, "path": dest}

    def set_icon(self, data_url: str) -> None:
        """Mac: Dock-Icon in der Akzentfarbe (gezeichnet von der Oberfläche, wie das Logo in der App)."""
        prefix = "data:image/png;base64,"
        if not paths.IS_MAC or not isinstance(data_url, str) or not data_url.startswith(prefix) or len(data_url) > 2_000_000:
            return
        try:
            import base64
            from AppKit import NSApplication, NSImage
            from Foundation import NSData
            from PyObjCTools import AppHelper
            raw = base64.b64decode(data_url[len(prefix):])
            img = NSImage.alloc().initWithData_(NSData.dataWithBytes_length_(raw, len(raw)))
            if img:
                AppHelper.callAfter(NSApplication.sharedApplication().setApplicationIconImage_, img)
        except Exception as e:
            print(f"[desktop] Dock-Icon: {e}", flush=True)

    def reveal_data(self) -> None:
        """Datenordner im Finder/Explorer zeigen."""
        import subprocess
        if paths.IS_WIN:
            os.startfile(paths.USER_DIR)  # type: ignore[attr-defined]
        elif paths.IS_MAC:
            subprocess.Popen(["open", str(paths.USER_DIR)])


def _allow_microphone_macos() -> None:
    """WKWebView fragt sonst bei jedem Diktat erneut nach dem Mikrofon (die Systemfrage bleibt)."""
    try:
        import objc
        from webview.platforms.cocoa import BrowserView

        def webView_requestMediaCapturePermissionForOrigin_initiatedByFrame_type_decisionHandler_(
                self, webview_, origin, frame, kind, handler):
            handler(1)   # WKPermissionDecisionGrant – nur unsere eigene Seite (127.0.0.1) läuft hier

        objc.classAddMethods(BrowserView.BrowserDelegate, [objc.selector(
            webView_requestMediaCapturePermissionForOrigin_initiatedByFrame_type_decisionHandler_,
            signature=b"v@:@@@q@?")])
    except Exception as e:  # ältere pywebview/macOS: dann fragt WebKit eben selbst
        print(f"[desktop] Mikrofon-Freigabe nicht eingerichtet: {e}", flush=True)


_cleaned = False


def _cleanup() -> None:
    """Hintergrundprozesse beenden. Läuft beim Schließen des Fensters – auch bei ⌘Q, wo `webview.start`
    nicht zurückkehrt und der Code nach dem Fenster nie erreicht wird."""
    global _cleaned
    if _cleaned:
        return
    _cleaned = True
    print("[desktop] Fenster geschlossen – räume auf", flush=True)
    try:
        server.tts._clone_worker.stop()
        import clone_setup
        clone_setup.cancel()
    except Exception as e:
        print(f"[desktop] Aufräumen: {e}", flush=True)
    try:
        import updater
        updater.install_on_exit()          # „Später“ gewählt → beim nächsten Öffnen läuft die neue Version
    except Exception as e:
        print(f"[desktop] Update beim Beenden: {e}", flush=True)


_activity = None


def _keep_running_in_background() -> None:
    """macOS: Vorlesen soll weiterlaufen, auch wenn das Fenster verdeckt oder die App im Hintergrund ist.
    WebKit drosselt verdeckte Fenster (Timer, Netzwerk) – zwischen zwei Abschnitten, wenn kurz kein Audio
    läuft, kann das den Wechsel zum nächsten Abschnitt ausbremsen. Und App Nap legt inaktive Apps schlafen."""
    global _activity
    try:
        from Foundation import NSProcessInfo
        opts = 0x00FFFFFF                                 # NSActivityUserInitiatedAllowingIdleSystemSleep
        _activity = NSProcessInfo.processInfo().beginActivityWithOptions_reason_(opts, "Vorleser liest vor")
    except Exception as e:
        print(f"[desktop] App Nap nicht abgeschaltet: {e}", flush=True)
    try:
        from webview.platforms.cocoa import BrowserView
        for inst in BrowserView.instances.values():
            wv = inst.webview
            if wv.respondsToSelector_("_setWindowOcclusionDetectionEnabled:"):
                wv._setWindowOcclusionDetectionEnabled_(False)
                print("[desktop] Hintergrund-Drosselung des Fensters aus", flush=True)
    except Exception as e:
        print(f"[desktop] Fenster-Drosselung nicht abgeschaltet: {e}", flush=True)


def _focus() -> None:
    """Fenster wieder zeigen und die App nach vorne holen (aufgerufen von einem zweiten Start)."""
    if not window:
        return
    try:
        window.restore()
        window.show()
        if paths.IS_MAC:
            from AppKit import NSApplication
            from PyObjCTools import AppHelper
            AppHelper.callAfter(lambda: NSApplication.sharedApplication().activateIgnoringOtherApps_(True))
    except Exception as e:
        print(f"[desktop] Fenster nach vorne holen: {e}", flush=True)


def _ask_running_to_focus(port: int) -> bool:
    try:
        req = urllib.request.Request(f"http://{server.HOST}:{port}/api/focus", method="POST", data=b"")
        with urllib.request.urlopen(req, timeout=3) as r:
            return r.status == 200
    except Exception:
        return False


def _quit() -> None:
    if window:
        window.destroy()


def selftest() -> int:
    """`Vorleser --selftest`: Grundfunktionen der fertigen App prüfen (läuft im Build vor der Veröffentlichung)."""
    import ssl
    import urllib.request
    checks = []

    def check(name, fn):
        try:
            fn()
            checks.append((name, "ok"))
        except Exception as e:
            checks.append((name, f"FEHLER {type(e).__name__}: {e}"))

    def https():
        # Gleiche Quelle wie der Updater (GitHub Pages) – die API hat auf geteilten Build-Rechnern oft kein Kontingent mehr
        import updater
        req = urllib.request.Request(updater.JSON_URL, headers={"User-Agent": "Vorleser-Selftest"})
        with urllib.request.urlopen(req, timeout=20) as r:
            assert r.status == 200
    check("HTTPS (Updater)", https)
    check("ffmpeg", lambda: server.tts.ffmpeg(["-version"]))
    check("Piper-Stimmen", lambda: server.tts._piper_voices() or (_ for _ in ()).throw(RuntimeError("keine")))
    check("Version", lambda: paths.APP_VERSION != "0.0.0" or (_ for _ in ()).throw(RuntimeError("fehlt")))
    import updater
    check("Updater-Pfad", lambda: updater._app_path() or (_ for _ in ()).throw(RuntimeError("App-Pfad unbekannt")))
    out = "\n".join(f"{n}: {r}" for n, r in checks) + f"\nSSL: {ssl.get_default_verify_paths().cafile} | SSL_CERT_FILE={os.environ.get('SSL_CERT_FILE')}"
    sys.__stdout__.write(out + "\n") if sys.__stdout__ else None
    (paths.DATA_DIR / "selftest.txt").write_text(out, "utf-8")      # Konsole fehlt in der App → auch als Datei
    return 0 if all(r == "ok" for _, r in checks) else 1


def main() -> None:
    if "--selftest" in sys.argv:
        os._exit(selftest())
    global window
    port = server.PORT
    srv = None
    try:
        srv = server.bind(port)
    except OSError:
        if not _existing_instance(port):          # Port von fremdem Programm belegt → freien nehmen
            srv = server.bind(0)
            port = srv.server_address[1]
    if srv is None and _ask_running_to_focus(port):
        # Läuft schon (z. B. eine zweite Kopie der App gestartet): bestehendes Fenster nach vorne, selbst beenden
        print("[desktop] Vorleser läuft schon – bestehendes Fenster nach vorne geholt", flush=True)
        os._exit(0)
    if srv:
        server.DESKTOP = True
        server.ON_QUIT = _quit
        server.ON_FOCUS = _focus
        threading.Thread(target=server.startup, daemon=True).start()
        threading.Thread(target=server.serve, daemon=True).start()
        print(f"[desktop] Server auf http://{server.HOST}:{port}", flush=True)
    else:
        print("[desktop] Vorleser läuft schon – öffne nur ein weiteres Fenster", flush=True)

    webview.settings["ALLOW_DOWNLOADS"] = True
    webview.settings["OPEN_EXTERNAL_LINKS_IN_BROWSER"] = True
    if paths.IS_MAC:
        _allow_microphone_macos()

    window = webview.create_window(TITLE, f"http://{server.HOST}:{port}/", js_api=Api(),
                                   width=1280, height=860, min_size=(820, 560),
                                   background_color="#1E2124" if _dark() else "#FAFAF9",
                                   text_select=True)
    if paths.IS_MAC:
        window.events.shown += _keep_running_in_background
    window.events.closing += _cleanup                   # ⌘Q: macOS fragt per „closing“ und beendet dann sofort
    window.events.closed += _cleanup
    import atexit
    atexit.register(_cleanup)
    webview.start(private_mode=False, storage_path=str(paths.USER_DIR / "webview"),
                  debug=bool(os.environ.get("VORLESER_DEBUG")))

    # Fenster zu → alles beenden
    if srv:
        srv.shutdown()
    _cleanup()                  # laufende Installation / Stimmklon nicht verwaist weiterlaufen lassen
    os._exit(0)   # Hintergrund-Threads (Export, Hörproben) nicht abwarten


def _system_dark() -> bool:
    """Ist das Betriebssystem im Dunkelmodus? (für „Darstellung: System“)"""
    try:
        if paths.IS_MAC:
            import subprocess
            r = subprocess.run(["defaults", "read", "-g", "AppleInterfaceStyle"], capture_output=True, text=True, timeout=2)
            return r.stdout.strip().lower() == "dark"
        if paths.IS_WIN:
            import winreg
            k = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize")
            return winreg.QueryValueEx(k, "AppsUseLightTheme")[0] == 0
    except Exception:
        pass
    return False


def _dark() -> bool:
    """Startfarbe des Fensters – muss zur App passen, sonst blitzt es beim Öffnen weiß auf."""
    try:
        theme = server.settings.get("theme")
    except Exception:
        theme = "system"
    return theme == "dark" or (theme == "system" and _system_dark())


if __name__ == "__main__":
    main()
