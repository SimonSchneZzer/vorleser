#!/usr/bin/env python3
"""Export vorbereiteter Texte in der GEBAUTEN App prüfen (macOS + Windows).

  python packaging/test_export_app.py <App-Programm> [<Ordner für Screenshots>]
    macOS:   dist/Vorleser.app/Contents/MacOS/Vorleser
    Windows: dist/Vorleser/Vorleser.exe

Ablauf wie bei einem Nutzer: Text anlegen → Export-Dialog zeigt Schätzung → „Vorab erzeugen“ → Dialog zeigt
„Vorbereitet“ + echte Größe → Export in M4B, MP3, WAV: Phase „Zusammensetzen“, Dauer, Größe wie angezeigt.
Mit Screenshot-Ordner (und installiertem Playwright) zusätzlich Bilder des Dialogs aus der Oberfläche der App –
Windows: Chromium (= Engine von WebView2), macOS: WebKit (= Engine von WKWebView). Exit-Code ≠ 0 bei Fehlern.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

TMP = Path(os.environ.get("RUNNER_TEMP") or tempfile.gettempdir()) / "vorleser-export-test"
HOME = TMP / "home"
PORT = 8796
fehler: list[str] = []

TEXT = """# Erstes Kapitel

Der Wind strich über die Felder, und die Bäume am Rand des Dorfes bogen sich leise. Niemand war mehr auf der Straße.
Nur der alte Hund lag vor der Bäckerei und schlief. Später am Abend kam ein Wagen den Hügel herunter.

Die Lichter in den Fenstern gingen eines nach dem anderen an. Es roch nach Regen und nach frischem Brot.

# Zweites Kapitel

Am nächsten Morgen war der Himmel klar. Die Kinder liefen zur Schule, und der Bäcker stellte die ersten Körbe vor die Tür.
Am Brunnen standen zwei Frauen und sprachen über das Wetter, über die Ernte und über den Fremden im Wagen.
"""


def log(msg: str) -> None:
    print(f"[test {time.strftime('%H:%M:%S')}] {msg}", flush=True)


def pruefe(ok: bool, was: str) -> None:
    log(("OK     " if ok else "FEHLER ") + was)
    if not ok:
        fehler.append(was)


def token() -> str:
    return (HOME / "data" / "api-token").read_text("utf-8").strip()


def api(method: str, path: str, body: dict | None = None, timeout: float = 30):
    req = urllib.request.Request(f"http://127.0.0.1:{PORT}{path}", method=method,
                                 data=json.dumps(body or {}).encode() if method in ("POST", "PATCH", "PUT") else None,
                                 headers={"X-Vorleser-Token": token(), "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        raw = r.read()
        return json.loads(raw) if r.headers.get("Content-Type", "").startswith("application/json") else raw


def wait_up(timeout: float = 120) -> None:
    end, last = time.time() + timeout, None
    while time.time() < end:
        try:
            api("GET", "/api/update")
            return
        except Exception as e:
            last = e
            time.sleep(1)
    raise TimeoutError(f"App antwortet nicht ({last!r})")


def mb(b: float) -> str:
    return f"{b / 2 ** 20:.2f} MB"


def screenshots(out: Path, doc_id: str, name: str) -> None:
    """Export-Dialog in der Oberfläche der App (über ihren Server) fotografieren, deutsch + englisch."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        log("Playwright fehlt – keine Screenshots")
        return
    out.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = (p.webkit if sys.platform == "darwin" else p.chromium).launch()
        for lang in ("de", "en"):
            api("PATCH", "/api/settings", {"uiLang": lang})
            pg = browser.new_page(viewport={"width": 1280, "height": 860}, color_scheme="dark")
            pg.goto(f"http://127.0.0.1:{PORT}/")
            pg.wait_for_timeout(2000)
            pg.evaluate(f"openDoc('{doc_id}')")
            pg.wait_for_timeout(1500)
            pg.evaluate("document.querySelector('dialog[open]')?.close(); document.getElementById('exportBtn').click()")
            pg.wait_for_timeout(1200)
            box = pg.locator("#exportDlg").bounding_box()          # Seite statt Element: Glas-Hintergrund mit drauf
            pg.screenshot(path=str(out / f"{name}-{lang}.png"), clip={"x": box["x"] - 8, "y": box["y"] - 8,
                                                                       "width": box["width"] + 16, "height": box["height"] + 16})
            pg.close()
        browser.close()
    log(f"Screenshots: {name}-de.png, {name}-en.png")


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    exe = Path(sys.argv[1]).resolve()
    shots = Path(sys.argv[2]).resolve() if len(sys.argv) > 2 else None
    shutil.rmtree(TMP, ignore_errors=True)
    HOME.mkdir(parents=True)
    app = subprocess.Popen([str(exe)], env=dict(os.environ, VORLESER_HOME=str(HOME), VORLESER_PORT=str(PORT)),
                           cwd=str(exe.parent))
    log(f"App gestartet: {exe}")
    try:
        wait_up()
        api("PATCH", "/api/settings", {"onboarded": True})
        lang = TEXT.split("# Zweites")                       # ~10 Minuten Audio: Zeiten sagen etwas aus
        text = lang[0] + "\n\n".join([lang[0].split("\n", 2)[2]] * 8) + "\n\n# Zweites" + lang[1] * 1
        d = api("POST", "/api/docs", {"text": text, "title": "Exporttest"})
        doc_id = d["id"]
        voices = [v["id"] for v in api("GET", "/api/voices")["voices"]]
        piper = next((v for v in voices if v.startswith("piper:de")), None)
        if piper:                                           # Offline-Stimme: kein Netz nötig, immer gleich
            api("PATCH", f"/api/docs/{doc_id}", {"voice": piper})
        doc = api("GET", f"/api/docs/{doc_id}")
        log(f"Text angelegt: {len(doc['chunks'])} Abschnitte, Stimme {doc['voice']}")

        info = api("GET", f"/api/docs/{doc_id}/export/info")
        pruefe(info["prepared"] == 0 and info["seconds"] is None, f"vorher: nichts vorbereitet, keine echte Länge ({info})")
        if shots:
            screenshots(shots, doc_id, "1-nicht-vorbereitet")

        api("POST", f"/api/docs/{doc_id}/prepare")
        t0 = time.time()
        while time.time() - t0 < 900:
            st = api("GET", f"/api/docs/{doc_id}/prepare")
            if st["status"] != "running":
                break
            time.sleep(1)
        pruefe(st["status"] == "ready", f"Vorab erzeugen fertig in {time.time() - t0:.0f} s ({st['done']}/{st['total']})")

        info = api("GET", f"/api/docs/{doc_id}/export/info")
        pruefe(info["prepared"] == info["total"] and (info["seconds"] or 0) > 5,
               f"nachher: alles vorbereitet, echte Länge {info['seconds']} s")
        if shots:
            screenshots(shots, doc_id, "2-vorbereitet")

        for fmt in ("m4b", "mp3", "wav"):
            t0, phasen = time.time(), []
            api("POST", f"/api/docs/{doc_id}/export", {"format": fmt, "rate": 1})
            while time.time() - t0 < 120:
                st = api("GET", f"/api/docs/{doc_id}/export")
                if st.get("phase") and (not phasen or phasen[-1] != st["phase"]):
                    phasen.append(st["phase"])
                if st["status"] != "running":
                    break
                time.sleep(0.1)
            dauer = time.time() - t0
            pruefe(st["status"] == "ready", f"{fmt}: fertig in {dauer:.1f} s, Phasen {phasen}")
            pruefe("Vertonen" not in phasen, f"{fmt}: nichts neu vertont (Phase „Zusammensetzen“)")
            datei = api("GET", f"/api/docs/{doc_id}/export/file", timeout=60)
            angezeigt = info["seconds"] * info["bytesPerSec"][fmt]
            abw = abs(len(datei) - angezeigt) / max(1, len(datei))
            pruefe(abw < 0.05, f"{fmt}: Datei {mb(len(datei))}, Dialog zeigte {mb(angezeigt)} (Abweichung {abw:.1%})")
            pruefe(abs((st.get("duration") or 0) - info["seconds"]) < 1.5,
                   f"{fmt}: Länge {st.get('duration'):.1f} s, Dialog kannte {info['seconds']} s")
        try:
            api("POST", "/api/quit")
        except Exception:
            pass
    except Exception as e:
        pruefe(False, f"Ablauf abgebrochen: {e!r}")
    finally:
        try:
            app.wait(20)
        except subprocess.TimeoutExpired:
            app.kill()
        logf = HOME / "data" / "server.log"
        if logf.exists():
            print("\n===== server.log (Ende) =====\n" + "\n".join(logf.read_text("utf-8", "replace").splitlines()[-40:]), flush=True)
    log("alles gut" if not fehler else f"{len(fehler)} Fehler: " + "; ".join(fehler))
    return 1 if fehler else 0


if __name__ == "__main__":
    sys.exit(main())
