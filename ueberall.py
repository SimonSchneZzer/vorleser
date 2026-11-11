"""Version 3.0 · „Markierten Text vorlesen“ – Vorleser von überall (Boards 22, 24, 25).

macOS: Menüleisten-Symbol (NSStatusItem), Tastenkürzel ⌃⌥V (NSEvent-Monitor), markierten Text per simuliertem ⌘C holen
(Quartz) und aus der Zwischenablage lesen, Erlaubnis „Bedienungshilfen“ prüfen (AXIsProcessTrusted per ctypes),
Mini-Player als eigenes rahmenloses Fenster (static/mini.html). Keine neue Abhängigkeit: AppKit/Quartz kommen mit pywebview.
Windows: folgt (Teil C im Plan). Alles hier läuft nur in der Desktop-App (desktop.py ruft `setup`).
"""
from __future__ import annotations

import ctypes
import json
import threading
import time
import urllib.request
from pathlib import Path

import meldungen
import paths

HOTKEY_LABEL = "⌃⌥V"            # Vorgabe; tatsächlich: kuerzel_label() aus den Einstellungen
# macOS-Tastencodes (kVK_ANSI_*) für KeyboardEvent.code
_MAC_KEYS = {**{f"Key{c}": k for c, k in zip("ASDFHGZXCVBQWERYTOUIPLJKNM",
                                                 (0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 11, 12, 13, 14, 15, 16, 17, 31, 32, 34, 35, 37, 38, 40, 45, 46))},
             **{f"Digit{d}": k for d, k in zip("1234567890", (18, 19, 20, 21, 23, 22, 26, 28, 25, 29))},
             **{f"F{n}": k for n, k in zip(range(1, 13), (122, 120, 99, 118, 96, 97, 98, 100, 101, 109, 103, 111))}}


def _hotkey() -> dict:
    try:
        import settings
        hk = settings.get("hotkey")
        if settings.valid_hotkey(hk):
            return hk
    except Exception:
        pass
    return {"code": "KeyV", "ctrl": True, "alt": True, "shift": False, "meta": False}


def kuerzel_label(hk: dict | None = None) -> str:
    """„⌃⌥V“ (Mac) bzw. „Strg+Alt+V“ (Windows)."""
    hk = hk or _hotkey()
    key = hk["code"].removeprefix("Key").removeprefix("Digit")
    if paths.IS_WIN:
        return "+".join([m for m, on in (("Strg", hk["ctrl"]), ("Alt", hk["alt"]), ("Umschalt", hk["shift"]), ("Win", hk["meta"])) if on] + [key])
    return "".join(s for s, on in (("⌃", hk["ctrl"]), ("⌥", hk["alt"]), ("⇧", hk["shift"]), ("⌘", hk["meta"])) if on) + key


def kuerzel_neu() -> None:
    """Nach Änderung in den Einstellungen: neu anmelden + Menüleisten-Eintrag aktualisieren."""
    if paths.IS_MAC:
        _on_main(_kuerzel_anmelden)
        mi = _state.get("lesen_item")
        if mi is not None:
            _on_main(lambda: mi.setTitle_(("Read selected text" if _ui_en() else "Markierten Text vorlesen") + f"   {kuerzel_label()}"))
    elif paths.IS_WIN:
        _win_kuerzel_neu()
_state = {"main": None, "port": 0, "token": "", "mini": None, "monitors": [], "menu": None, "item": None,
          "quitting": False, "busy": False}


# --------------------------------------------------------------------------- #
# Allgemein
# --------------------------------------------------------------------------- #
def _api(path: str, body: dict | None = None) -> dict:
    req = urllib.request.Request(f"http://127.0.0.1:{_state['port']}{path}", method="POST" if body is not None else "GET",
                                 data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Content-Type": "application/json", "X-Vorleser-Token": _state["token"]})
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read())


def _main_js(code: str) -> None:
    """JavaScript im Hauptfenster ausführen (zeigt das Fenster vorher, wenn nötig)."""
    w = _state["main"]
    if w is None:
        return
    if threading.current_thread() is threading.main_thread():
        # evaluate_js wartet auf die Antwort von WebKit, die nur über den Haupt-Thread kommt → von dort aus
        # (z. B. im Schließen-Handler) eingefroren. Dann im Hintergrund ausführen (⌘W hing, 11.11.2026).
        threading.Thread(target=_main_js, args=(code,), daemon=True).start()
        return
    try:
        w.evaluate_js(code)
    except Exception as e:
        print(f"[überall] Hauptfenster: {e}", flush=True)


def autoplay_erlauben() -> None:
    """Mini-Player startet ohne Klick in die Seite → WebKit muss Abspielen ohne Nutzer-Geste erlauben.
    pywebview legt die WKWebViewConfiguration an genau einer Stelle an; dort setzen wir die Eigenschaft."""
    if not paths.IS_MAC:
        return
    try:
        import webview.platforms.cocoa as cocoa
        real = cocoa.WebKit

        class _Cfg:
            @staticmethod
            def alloc():
                return _Cfg()

            def init(self):
                cfg = real.WKWebViewConfiguration.alloc().init()
                cfg.setMediaTypesRequiringUserActionForPlayback_(0)     # WKAudiovisualMediaTypeNone
                return cfg

        class _WebKit:
            WKWebViewConfiguration = _Cfg

            def __getattr__(self, name):
                return getattr(real, name)

        cocoa.WebKit = _WebKit()
    except Exception as e:
        print(f"[überall] Autoplay nicht eingerichtet: {e}", flush=True)


# --------------------------------------------------------------------------- #
# macOS
# --------------------------------------------------------------------------- #
def ist_erlaubt() -> bool:
    """Darf Vorleser andere Apps „bedienen“ (⌘C senden, Tasten global beobachten)?"""
    if not paths.IS_MAC:
        return True
    try:
        lib = ctypes.cdll.LoadLibrary("/System/Library/Frameworks/ApplicationServices.framework/ApplicationServices")
        lib.AXIsProcessTrusted.restype = ctypes.c_bool
        return bool(lib.AXIsProcessTrusted())
    except Exception:
        return False


def _in_liste_eintragen() -> None:
    """AXIsProcessTrustedWithOptions(Prompt) trägt Vorleser in die Erlaubnis-Liste ein (sonst fehlt der Eintrag dort
    ganz) und zeigt den Systemhinweis. Aus dem Quellcode gestartet erscheint statt „Vorleser“ die startende App."""
    if paths.FROZEN and not ist_erlaubt():
        # Unsignierte App: nach Update/Neubau gilt der alte Listeneintrag nicht mehr (Schalter steht auf „an“, wirkt aber
        # nicht – Simon, 9.11.2026). Eigenen Eintrag zurücksetzen → frisch eintragen, man legt nur noch den Schalter um.
        import subprocess
        try:
            subprocess.run(["/usr/bin/tccutil", "reset", "Accessibility", BUNDLE_ID], timeout=5,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, **paths.NO_WINDOW)
        except Exception as e:
            meldungen.loggen("erlaubnis zurücksetzen", e)
    try:
        import objc
        from Foundation import NSDictionary
        lib = ctypes.cdll.LoadLibrary("/System/Library/Frameworks/ApplicationServices.framework/ApplicationServices")
        lib.AXIsProcessTrustedWithOptions.restype = ctypes.c_bool
        lib.AXIsProcessTrustedWithOptions.argtypes = [ctypes.c_void_p]
        opts = NSDictionary.dictionaryWithObject_forKey_(True, "AXTrustedCheckOptionPrompt")
        lib.AXIsProcessTrustedWithOptions(objc.pyobjc_id(opts))
    except Exception as e:
        meldungen.loggen("erlaubnis eintragen", e)


def einstellungen_oeffnen() -> None:
    import subprocess
    _in_liste_eintragen()
    subprocess.Popen(["open", "x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility"])
    threading.Thread(target=_warte_auf_erlaubnis, daemon=True).start()


def _warte_auf_erlaubnis() -> None:
    """Nach „Einstellungen öffnen“: bis zu 3 Minuten prüfen – sobald erlaubt, Kürzel neu anmelden und melden."""
    for _ in range(180):
        time.sleep(1)
        if ist_erlaubt():
            _on_main(_kuerzel_anmelden)
            _main_js("window.ueberallErlaubt && ueberallErlaubt()")
            return


def _on_main(fn) -> None:
    from PyObjCTools import AppHelper
    AppHelper.callAfter(fn)


_JS_MARKIERUNG = """(() => {
  if (!document.hasFocus()) return "";
  const a = document.activeElement;
  if (a && (a.tagName === "TEXTAREA" || (a.tagName === "INPUT" && /^(text|search)$/.test(a.type))))
    return a.value.slice(a.selectionStart || 0, a.selectionEnd || 0);
  return String(window.getSelection() || "");
})()"""


def _markierung_im_fenster() -> str | None:
    """Ist das Vorleser-Fenster vorne, die Markierung direkt aus der Seite lesen – ohne Strg+C/⌘C über die
    Zwischenablage (unter Windows kam die Kopie im eigenen Fenster nicht an, Tester-Rückmeldung 11.11.2026)."""
    w = _state["main"]
    if w is None:
        return None
    ergebnis = []

    def frage():
        try:
            ergebnis.append(w.evaluate_js(_JS_MARKIERUNG))
        except Exception as e:
            print(f"[überall] Markierung im Fenster: {e!r}", flush=True)
    t = threading.Thread(target=frage, daemon=True)
    t.start()
    t.join(1.5)                                       # Seite hängt / lädt gerade → nicht warten, Strg+C versuchen
    text = ergebnis[0] if ergebnis and isinstance(ergebnis[0], str) else ""
    return text.strip() or None


def _markierung_holen() -> str | None:
    """⌘C an die vordere App senden und den neuen Inhalt der Zwischenablage lesen. Vorherigen Text zurücklegen."""
    if paths.IS_WIN:
        import ueberall_win
        return ueberall_win.markierung_holen()
    from AppKit import NSPasteboard, NSPasteboardTypeString
    import Quartz
    pb = NSPasteboard.generalPasteboard()
    before, alt = pb.changeCount(), pb.stringForType_(NSPasteboardTypeString)
    # Erst warten, bis ⌃⌥ losgelassen sind (bis 0,6 s): sonst kommt unser ⌘C bei manchen Apps (Chrome) als ⌃⌥⌘C an
    halt = Quartz.kCGEventFlagMaskControl | Quartz.kCGEventFlagMaskAlternate
    for _ in range(30):
        if not Quartz.CGEventSourceFlagsState(Quartz.kCGEventSourceStateHIDSystemState) & halt:
            break
        time.sleep(0.02)
    src = Quartz.CGEventSourceCreate(Quartz.kCGEventSourceStatePrivate)   # eigener Zustand: gedrückte Tasten nicht mischen
    for down in (True, False):
        ev = Quartz.CGEventCreateKeyboardEvent(src, 8, down)          # 8 = kVK_ANSI_C
        Quartz.CGEventSetFlags(ev, Quartz.kCGEventFlagMaskCommand)     # gedrücktes ⌃⌥ ignorieren → reines ⌘C
        Quartz.CGEventPost(Quartz.kCGHIDEventTap, ev)
    for _ in range(50):                                                 # bis 1 s auf die Kopie warten
        time.sleep(0.02)
        if pb.changeCount() != before:
            break
    if pb.changeCount() == before:
        return None
    text = pb.stringForType_(NSPasteboardTypeString)
    if alt is not None:                                                 # Zwischenablage des Nutzers nicht überschreiben
        pb.clearContents()
        pb.setString_forType_(alt, NSPasteboardTypeString)
    return (text or "").strip() or None


def _zwischenablage() -> str | None:
    if paths.IS_WIN:
        import ueberall_win
        return (ueberall_win.ablage_lesen() or "").strip() or None
    from AppKit import NSPasteboard, NSPasteboardTypeString
    return ((NSPasteboard.generalPasteboard().stringForType_(NSPasteboardTypeString)) or "").strip() or None


def vorlesen(text: str | None = None, aus_ablage: bool = False) -> None:
    """Markierten Text (oder Zwischenablage) im Mini-Player vorlesen. Läuft in einem Hintergrund-Thread."""
    if _state["busy"]:
        return
    _state["busy"] = True
    try:
        frage = False
        if text is None and not aus_ablage:
            if not ist_erlaubt():
                _focus_main()
                _main_js("window.ueberallErlaubnis && ueberallErlaubnis()")
                return
            text, quelle = _markierung_im_fenster(), "Fenster"
            if not text:
                text, quelle = _markierung_holen(), "Kopie"
            if not text:                                             # nichts markiert → Zwischenablage anbieten
                text, frage, quelle = _zwischenablage(), True, "Zwischenablage"
                if not text:
                    print("[überall] kein markierter Text, Zwischenablage leer", flush=True)
                    _main_js("window.toast && toast('Kein markierter Text gefunden', true)")
                    return
            print(f"[überall] vorlesen: {len(text)} Zeichen ({quelle})", flush=True)
        elif aus_ablage:
            text = _zwischenablage()
            if not text:
                return
        q = _api("/api/quick", {"text": text[:200_000]})
        _mini_zeigen(q["id"], frage, q.get("slow"))
    except Exception as e:
        print(f"[überall] Vorlesen: {e!r}", flush=True)
        _main_js("window.toast && toast(friendlyError(new Error('Markierter Text ließ sich nicht vorlesen')), true)")
    finally:
        _state["busy"] = False


MINI_BREITE = 560
BUNDLE_ID = "de.neke-neke.vorleser"             # wie in packaging/vorleser.spec


def _mini_zeigen(qid: str, frage: bool, slow: bool) -> None:
    import webview
    old = _state["mini"]
    if old is not None:
        try:
            old.destroy()
        except Exception:
            pass
    w, h = MINI_BREITE, 210 if slow or frage else 150
    x, y = 0, 40
    try:
        if paths.IS_WIN:
            import ueberall_win
            x = int((ueberall_win.bildschirm_breite() - w) / 2)
        else:
            from AppKit import NSScreen
            fr = NSScreen.mainScreen().frame()
            x = int((fr.size.width - w) / 2)
    except Exception:
        pass
    # Windows kann rahmenlose Fenster nicht durchsichtig machen → Seite füllt das Fenster selbst (opaque=1)
    url = (f"http://127.0.0.1:{_state['port']}/mini#q={qid}" + ("&ask=1" if frage else "")
           + ("&opaque=1" if paths.IS_WIN else ""))
    _state["mini"] = webview.create_window("Vorleser", url, js_api=MiniApi(), width=w, height=h, x=x, y=y,
                                           frameless=True, on_top=True, transparent=not paths.IS_WIN, resizable=False,
                                           easy_drag=False, focus=False, shadow=paths.IS_WIN)


class MiniApi:
    """Brücke für static/mini.html (window.pywebview.api.…)."""

    def mini_groesse(self, h) -> None:
        w = _state["mini"]
        if w is not None:
            try:
                w.resize(MINI_BREITE, max(80, min(600, int(h))))       # oben links bleibt stehen
            except Exception:
                pass

    def mini_close(self) -> None:
        w, _state["mini"] = _state["mini"], None
        if w is not None:
            try:
                w.destroy()
            except Exception:
                pass

    def mini_saved(self) -> None:
        _main_js("window.refreshLibrary && refreshLibrary()")


def _focus_main() -> None:
    w = _state["main"]
    if w is None:
        return
    try:
        w.show()
        from AppKit import NSApplication
        _on_main(lambda: NSApplication.sharedApplication().activateIgnoringOtherApps_(True))
    except Exception as e:
        print(f"[überall] Fenster zeigen: {e}", flush=True)


def _kuerzel_anmelden() -> None:
    """Kürzel (Vorgabe ⌃⌥V, änderbar) global (andere Apps; braucht die Erlaubnis) und lokal (Vorleser vorne) beobachten."""
    from AppKit import (NSEvent, NSEventMaskKeyDown, NSEventModifierFlagCommand, NSEventModifierFlagControl,
                        NSEventModifierFlagOption, NSEventModifierFlagShift)
    for m in _state["monitors"]:
        NSEvent.removeMonitor_(m)
    hk = _hotkey()
    alle = NSEventModifierFlagControl | NSEventModifierFlagOption | NSEventModifierFlagCommand | NSEventModifierFlagShift
    want = ((NSEventModifierFlagControl if hk["ctrl"] else 0) | (NSEventModifierFlagOption if hk["alt"] else 0)
            | (NSEventModifierFlagShift if hk["shift"] else 0) | (NSEventModifierFlagCommand if hk["meta"] else 0))
    key = _MAC_KEYS.get(hk["code"], 9)

    def treffer(ev) -> bool:
        return ev.keyCode() == key and (ev.modifierFlags() & alle) == want

    def global_(ev):
        if treffer(ev):
            threading.Thread(target=vorlesen, daemon=True).start()

    def local_(ev):
        if treffer(ev):
            threading.Thread(target=vorlesen, daemon=True).start()
            return None                                          # Taste nicht an die Seite weitergeben
        return ev

    _state["monitors"] = [NSEvent.addGlobalMonitorForEventsMatchingMask_handler_(NSEventMaskKeyDown, global_),
                          NSEvent.addLocalMonitorForEventsMatchingMask_handler_(NSEventMaskKeyDown, local_)]


def _menueleiste() -> None:
    from AppKit import NSImage, NSMenu, NSMenuItem, NSStatusBar, NSVariableStatusItemLength
    from Foundation import NSObject

    class _Ziel(NSObject):
        def lesen_(self, sender):
            threading.Thread(target=vorlesen, daemon=True).start()

        def ablage_(self, sender):
            threading.Thread(target=vorlesen, kwargs={"aus_ablage": True}, daemon=True).start()

        def oeffnen_(self, sender):
            _focus_main()

        def beenden_(self, sender):
            beenden()

    ziel = _Ziel.alloc().init()
    item = NSStatusBar.systemStatusBar().statusItemWithLength_(NSVariableStatusItemLength)
    img = None
    try:
        img = NSImage.imageWithSystemSymbolName_accessibilityDescription_("waveform", "Vorleser")
        img.setTemplate_(True)
    except Exception:
        pass
    if img is not None:
        item.button().setImage_(img)
    else:
        item.button().setTitle_("Vorleser")
    en = _ui_en()
    menu = NSMenu.alloc().init()
    for title, sel, key in ((("Read selected text" if en else "Markierten Text vorlesen") + f"   {kuerzel_label()}", "lesen:", ""),
                            ("Read clipboard" if en else "Zwischenablage vorlesen", "ablage:", ""),
                            (None, None, None),
                            ("Open Vorleser" if en else "Vorleser öffnen", "oeffnen:", ""),
                            ("Quit Vorleser" if en else "Vorleser beenden", "beenden:", "q")):
        if title is None:
            menu.addItem_(NSMenuItem.separatorItem())
            continue
        mi = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(title, sel, key)
        mi.setTarget_(ziel)
        menu.addItem_(mi)
        if sel == "lesen:":
            _state["lesen_item"] = mi
    item.setMenu_(menu)
    _state.update(item=item, menu=menu, ziel=ziel)


def _ui_en() -> bool:
    try:
        import settings
        return settings.get("uiLang") == "en"
    except Exception:
        return False


def beenden() -> None:
    """Wirklich beenden (Menüleiste / Einstellungen) – nicht nur das Fenster verstecken."""
    _state["quitting"] = True
    if _state.get("win") is not None:
        try:
            _state["win"].beenden()
        except Exception:
            pass
    for w in (_state["mini"], _state["main"]):
        if w is not None:
            try:
                w.destroy()
            except Exception:
                pass


def neu_starten() -> None:
    """Vorleser beenden und gleich wieder öffnen – nur als Rückfall, wenn macOS die frisch erteilte Erlaubnis nicht erkennt.
    App: per `open` (dann gilt die Erlaubnis der App selbst); Quellcode: derselbe Befehl noch einmal. Kurz warten, damit der
    alte Server den Port frei hat (sonst öffnet der neue Start nur ein Fenster im alten)."""
    import os
    import shlex
    import subprocess
    import sys
    if paths.FROZEN:
        app = Path(sys.executable).resolve().parents[2]                 # …/Vorleser.app/Contents/MacOS/Vorleser
        env = " ".join(f"--env {shlex.quote(f'{k}={v}')}" for k, v in os.environ.items() if k.startswith("VORLESER_"))
        cmd = f"sleep 2; open {env} {shlex.quote(str(app))}"              # VORLESER_HOME & Co. mitnehmen (Testordner)
    else:
        cmd = f"sleep 2; cd {shlex.quote(os.getcwd())} && exec {' '.join(shlex.quote(a) for a in [sys.executable, *sys.argv])}"
    subprocess.Popen(["/bin/sh", "-c", cmd], start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    beenden()


def beim_schliessen() -> bool | None:
    """window.events.closing: False = Schließen abbrechen (Fenster nur verstecken, Vorleser läuft in der Menüleiste)."""
    if _state["quitting"] or not paths.IS_MAC:
        return None
    try:
        import settings
        if not settings.get("background"):
            return None
        from AppKit import NSApplication, NSEventTypeKeyDown, NSEventModifierFlagCommand
        ev = NSApplication.sharedApplication().currentEvent()
        if ev is not None and ev.type() == NSEventTypeKeyDown and ev.modifierFlags() & NSEventModifierFlagCommand \
                and (ev.charactersIgnoringModifiers() or "").lower() == "q":
            return None                                          # ⌘Q = wirklich beenden
        if not settings.get("bgHintSeen"):                       # beim ersten Mal erklären (Board 24), dann verstecken
            _main_js("window.ueberallSchliessHinweis && ueberallSchliessHinweis()")
            return False
        threading.Thread(target=lambda: _state["main"].hide(), daemon=True).start()
        return False
    except Exception as e:
        print(f"[überall] Schließen: {e}", flush=True)
        return None


def fenster_verstecken() -> None:
    if _state["main"] is not None:
        _state["main"].hide()


def _beenden_erkennen() -> None:
    """Beenden über das App-Menü, das Dock oder beim Abmelden (nicht nur per ⌘Q-Taste) wirklich als Beenden
    behandeln: macOS fragt dann zuerst die App (applicationShouldTerminate) und erst danach jedes Fenster
    („closing“). Ohne diese Markierung versteckte „Beenden“ per Maus nur das Fenster bzw. zeigte den Hinweis."""
    try:
        import objc
        from webview.platforms.cocoa import BrowserView
        original = BrowserView.AppDelegate.applicationShouldTerminate_

        def applicationShouldTerminate_(self, app):
            _state["quitting"] = True
            return original(self, app)
        objc.classAddMethods(BrowserView.AppDelegate, [objc.selector(
            applicationShouldTerminate_, selector=b"applicationShouldTerminate:", signature=original.signature)])
    except Exception as e:
        print(f"[überall] Beenden-Erkennung nicht eingerichtet: {e}", flush=True)


def _dock_klick() -> None:
    """Klick aufs Dock-Symbol, während das Fenster versteckt ist → Fenster zurückholen (pywebview fängt das nicht ab)."""
    try:
        import objc
        from webview.platforms.cocoa import BrowserView

        def applicationShouldHandleReopen_hasVisibleWindows_(self, app, visible):
            if not visible:
                threading.Thread(target=_focus_main, daemon=True).start()
            return True
        objc.classAddMethods(BrowserView.AppDelegate, [objc.selector(
            applicationShouldHandleReopen_hasVisibleWindows_, signature=b"Z@:@Z")])
    except Exception as e:
        print(f"[überall] Dock-Klick nicht eingerichtet: {e}", flush=True)


def setup(main_window, port: int, token: str) -> None:
    """Nach dem Start des Fensters (aus desktop.py): Menüleiste + Kürzel einrichten."""
    if _state["item"] is not None:                 # „shown“ kommt bei jedem Wieder-Zeigen – nur einmal einrichten
        return
    _state.update(main=main_window, port=port, token=token)
    if paths.IS_WIN:                                  # Windows: nur Kürzel (kein Infobereich-Symbol), Teil C
        if _state.get("win") is None:
            import ueberall_win
            _state["win"] = ueberall_win.Kuerzel(_hotkey, vorlesen, _kuerzel_belegt)
            print(f"[überall] Windows-Kürzel {kuerzel_label()} angemeldet", flush=True)
        return
    if not paths.IS_MAC:
        return
    _on_main(_menueleiste)
    _on_main(_kuerzel_anmelden)
    _on_main(_dock_klick)
    _on_main(_beenden_erkennen)
    _on_main(_dienst_anmelden)
    print(f"[überall] Menüleiste + {kuerzel_label()} bereit (Erlaubnis: {'ja' if ist_erlaubt() else 'nein'})", flush=True)


def _dienst_text(pboard) -> str | None:
    from AppKit import NSPasteboardTypeString
    t = pboard.stringForType_(NSPasteboardTypeString)
    return str(t).strip() if t else None


def _dienst_anmelden() -> None:
    """macOS-Dienst „Mit Vorleser vorlesen“ (Info.plist: NSServices, NSMessage vorleserLesen). Ausweg ohne
    Bedienungshilfen-Erlaubnis: Der Dienst bekommt den markierten Text direkt von macOS."""
    try:
        import objc
        from AppKit import NSApplication, NSUpdateDynamicServices
        from Foundation import NSObject

        class _Dienst(NSObject):
            @objc.typedSelector(b"v@:@@o^@")
            def vorleserLesen_userData_error_(self, pboard, userData, error):
                text = _dienst_text(pboard)
                if text:
                    threading.Thread(target=vorlesen, kwargs={"text": text}, daemon=True).start()
                return None

        _state["dienst"] = _Dienst.alloc().init()                   # Referenz halten, sonst räumt Python ihn weg
        NSApplication.sharedApplication().setServicesProvider_(_state["dienst"])
        NSUpdateDynamicServices()
    except Exception as e:
        meldungen.loggen("dienst anmelden", e)


def _kuerzel_belegt() -> None:
    text = f"Das Tastenkürzel {kuerzel_label()} ist schon von einer anderen App belegt – in Einstellungen › App eine andere Kombination wählen."
    _main_js(f"window.toast && toast({json.dumps(text)}, true)")


def _win_kuerzel_neu() -> None:
    """Windows: Kürzel neu anmelden (Teil C)."""
    w = _state.get("win")
    if w:
        w.neu_anmelden()
