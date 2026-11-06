"""Oberfläche: Syntax, Übersetzungen und ein echter Browser-Test (Headless-Chrome über DevTools)."""
import asyncio
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "static"


@pytest.mark.skipif(shutil.which("node") is None, reason="Node.js fehlt")
@pytest.mark.parametrize("name", ["app.js", "i18n.js"])
def test_js_syntax(name):
    r = subprocess.run(["node", "--check", str(STATIC / name)], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr


def _i18n_keys() -> set[str]:
    src = (STATIC / "i18n.js").read_text("utf-8")
    block = src[src.index("const I18N_EN = {"):src.index("\n};", src.index("const I18N_EN = {"))]
    return set(re.findall(r'"((?:[^"\\]|\\.)*)"\s*:', block))


def test_neue_desktop_texte_uebersetzt():
    """Texte, die per JS gesetzt werden, brauchen einen Eintrag in i18n.js (Deutsch → Englisch)."""
    keys = _i18n_keys()
    pflicht = ["Später", "Aktualisieren", "Nach Updates suchen", "Update wird geladen", "Wird installiert",
               "Eigene Stimme installieren", "Installation abbrechen", "Weiter installieren", "Gespeichert", "Python wird geladen", "Stimmmodell wird geladen", "Restzeit wird berechnet",
               "Fehler melden", "Danke für deine Meldung!", "Senden", "Senden fehlgeschlagen – bist du online?"]
    fehlt = [k for k in pflicht if k not in keys]
    assert not fehlt, f"in static/i18n.js ergänzen: {fehlt}"


def test_html_ids_eindeutig():
    html = (STATIC / "index.html").read_text("utf-8")
    ids = re.findall(r'\sid="([^"]+)"', html)
    doppelt = {i for i in ids if ids.count(i) > 1}
    assert not doppelt, doppelt


def test_js_nutzt_nur_vorhandene_ids():
    """$("…")-Aufrufe in app.js müssen auf IDs in index.html (oder per JS erzeugte) zeigen."""
    html = (STATIC / "index.html").read_text("utf-8")
    js = (STATIC / "app.js").read_text("utf-8")
    ids = set(re.findall(r'\sid="([^"]+)"', html)) | set(re.findall(r'id="([^"$]+)"', js)) | set(re.findall(r'\.id = "([^"]+)"', js))
    used = set(re.findall(r'\$\("([A-Za-z][\w-]*)"\)', js))
    fehlt = sorted(used - ids)
    assert not fehlt, f"unbekannte IDs: {fehlt}"


# --------------------------------------------------------------------------- #
# Browser-Test
# --------------------------------------------------------------------------- #
def _chrome() -> str | None:
    for p in (os.environ.get("CHROME"),
              "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
              r"C:\Program Files\Google\Chrome\Application\chrome.exe",
              r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
              shutil.which("google-chrome"), shutil.which("chromium"), shutil.which("chromium-browser")):
        if p and Path(p).exists():
            return p
    return None


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class Cdp:
    """Minimaler Chrome-DevTools-Client (aiohttp ist über edge-tts ohnehin installiert)."""

    def __init__(self, ws):
        self.ws, self.n, self.errors = ws, 0, []

    async def cmd(self, method, **params):
        self.n += 1
        i = self.n
        await self.ws.send_json({"id": i, "method": method, "params": params})
        while True:
            m = await self.ws.receive_json()
            if m.get("method") == "Runtime.exceptionThrown":
                self.errors.append(m["params"]["exceptionDetails"].get("exception", {}).get("description", "JS-Fehler"))
            if m.get("id") == i:
                if "error" in m:
                    raise RuntimeError(m["error"])
                return m.get("result", {})

    async def js(self, expr):
        r = await self.cmd("Runtime.evaluate", expression=expr, awaitPromise=True, returnByValue=True)
        if r.get("exceptionDetails"):
            raise AssertionError(r["exceptionDetails"])
        return r.get("result", {}).get("value")


async def _neu_laden(c):
    """Seite neu laden und sicher auf die NEUE warten (die alte darf nicht mehr antworten)."""
    await c.js("window.__alteSeite = true; 1")
    await c.cmd("Page.reload")
    for _ in range(120):
        await asyncio.sleep(0.25)
        try:
            if await c.js("!window.__alteSeite && typeof openDoc === 'function' && !!st.settings"):
                return
        except AssertionError:
            pass                                    # Seite gerade im Wechsel
    raise AssertionError("Seite nicht neu geladen")


def _im_browser(api, szenario):
    """Headless-Chrome starten, App laden und `await szenario(c)` ausführen (c = Cdp)."""
    chrome = _chrome()
    if not chrome:
        pytest.skip("Chrome nicht gefunden (Pfad per CHROME=… setzen)")
    aiohttp = pytest.importorskip("aiohttp")
    port = _free_port()
    profile = tempfile.mkdtemp(prefix="vorleser-chrome-")
    proc = subprocess.Popen([chrome, "--headless=new", "--disable-gpu", "--no-first-run", f"--remote-debugging-port={port}",
                             f"--user-data-dir={profile}", "about:blank"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    async def run():
        async with aiohttp.ClientSession() as s:
            for _ in range(60):
                try:
                    tabs = await (await s.get(f"http://127.0.0.1:{port}/json")).json()
                    break
                except Exception:
                    await asyncio.sleep(0.25)
            ws_url = next(t for t in tabs if t["type"] == "page")["webSocketDebuggerUrl"]
            async with s.ws_connect(ws_url, max_msg_size=0) as ws:
                c = Cdp(ws)
                await c.cmd("Runtime.enable")
                await c.cmd("Emulation.setDeviceMetricsOverride", width=1280, height=800, deviceScaleFactor=1, mobile=False)
                api.json("PATCH", "/api/settings", {"onboarded": True, "mark": "word"})
                await c.cmd("Page.navigate", url=api.base + "/")
                for _ in range(40):
                    if await c.js("typeof openDoc === 'function' && !!st.settings"):
                        break
                    await asyncio.sleep(0.25)
                await szenario(c)
                assert not c.errors, c.errors

    try:
        asyncio.run(run())
    finally:
        proc.kill()
        proc.wait(timeout=10)
        shutil.rmtree(profile, ignore_errors=True)


@pytest.mark.browser
def test_wortmarkierung_im_browser(api):
    async def szenario(c):
        _, d = api.json("POST", "/api/docs", {"title": "Browser", "text": "Der alte Wärter stieg die Treppe hinauf."})
        await _neu_laden(c)
        await c.js(f"openDoc('{d['id']}').then(() => 1)")
        await asyncio.sleep(0.5)
        assert await c.js("st.words && st.words.list.length") == 7

        async def box_and_word(k):
            await c.js(f"setWord({k})")
            r = None
            for _ in range(30):                         # Gleiten (0,24 s) abwarten – Runner sind unterschiedlich schnell
                await asyncio.sleep(0.1)
                # Langsame Runner: die App baut die Wortliste nach dem Laden ggf. neu auf (springt auf Wort 0)
                await c.js(f"st.words && st.words.cur !== {k} && setWord({k}); 1")
                r = await c.js(f"""(() => {{
                    const b = document.getElementById('wbox').getBoundingClientRect();
                    const w = st.words.list[{k}].el.firstElementChild.getBoundingClientRect();
                    return {{bx: b.x, bw: b.width, wx: w.x, ww: w.width, on: document.getElementById('wbox').classList.contains('on')}};
                }})()""")
                if abs(r["bx"] - (r["wx"] - 3)) < 1.5 and abs(r["bw"] - (r["ww"] + 6)) < 1.5:
                    break
            return r

        a = await box_and_word(1)                       # „alte“
        b = await box_and_word(2)                       # „Wärter“
        for r in (a, b):
            assert r["on"]
            assert abs(r["bx"] - (r["wx"] - 3)) < 1.5 and abs(r["bw"] - (r["ww"] + 6)) < 1.5   # Box sitzt auf dem Wort
        assert b["bx"] > a["bx"] and b["bw"] > a["bw"]     # weitergeglitten und breiter geworden

        # Hover über dem gelesenen Abschnitt darf die Box nicht überdecken
        await c.cmd("Input.dispatchMouseEvent", type="mouseMoved", x=b["bx"] + b["bw"] / 2, y=300)
        pos = await c.js("(() => { const r = document.getElementById('wbox').getBoundingClientRect(); return [r.x + r.width/2, r.y + r.height/2]; })()")
        await c.cmd("Input.dispatchMouseEvent", type="mouseMoved", x=pos[0], y=pos[1])
        await asyncio.sleep(0.3)
        assert await c.js("getComputedStyle(document.querySelector('.chunk.current')).backgroundColor") == "rgba(0, 0, 0, 0)"

        # Satzmodus: keine Wort-Box
        await c.js("saveSettings({ mark: 'sentence' }).then(() => { highlight(false); return 1; })")
        await asyncio.sleep(0.4)
        assert not await c.js("document.getElementById('wbox')?.classList.contains('on')")
        await c.js("saveSettings({ mark: 'word' }).then(() => 1)")
        api.call("DELETE", f"/api/docs/{d['id']}")

    try:
        _im_browser(api, szenario)
    finally:                                            # auch bei Fehlschlag aufräumen (sonst stört es Folgetests)
        for doc in api.json("GET", "/api/docs")[1]["docs"]:
            if doc["title"] == "Browser":
                api.call("DELETE", f"/api/docs/{doc['id']}")


@pytest.mark.browser
def test_rundgang_beispieltext_bleibt_ohne_doppelung(api):
    """Wunsch: Beispieltext nach Rundgang (fertig oder abgebrochen) in der Bibliothek, beim Neustart keine Kopie."""
    samples = lambda: [d for d in api.json("GET", "/api/docs")[1]["docs"] if d["sample"]]
    for d in api.json("GET", "/api/docs")[1]["docs"]:     # leere Bibliothek: kein „vorheriger Text“ zum Zurückkehren
        api.call("DELETE", f"/api/docs/{d['id']}")

    async def szenario(c):
        await _neu_laden(c)
        async def rundgang():
            await c.js("gtStart(false); 1")
            await asyncio.sleep(0.8)
            during = await c.js("document.querySelectorAll('#library li').length")
            await c.js("gtEnd(); 1")                     # Abbruch und „Fertig“ laufen beide über gtEnd
            for _ in range(30):
                await asyncio.sleep(0.2)
                if await c.js("!!st.doc && !st.doc.demo"):
                    break
            return during

        await rundgang()
        first = samples()
        assert len(first) == 1                          # gespeichert …
        assert await c.js("st.doc.id") == first[0]["id"]  # … und geöffnet
        n_lib = await c.js("st.docs.length")
        during = await rundgang()                       # Rundgang erneut
        assert during == n_lib                          # währenddessen kein zweiter „Willkommen“-Eintrag
        assert [d["id"] for d in samples()] == [first[0]["id"]]   # derselbe Text, keine Kopie
        api.call("DELETE", f"/api/docs/{first[0]['id']}")

    _im_browser(api, szenario)


def test_statuszeile_flackert_nicht(api):
    """Regression: #status wurde bei jedem Aufruf neu gesetzt (+ Einblendung) → Flackern trotz gleichem Text."""
    d = api.json("POST", "/api/docs", {"text": "# Eins\n\nErster Satz. Zweiter Satz.", "title": "Status"})[1]

    async def sz(c):
        await c.js(f"openDoc('{d['id']}')")
        await asyncio.sleep(1.0)
        # Gleicher Zustand → kein Neuzeichnen. Ändert sich der Zustand währenddessen echt (Vorbereiten im
        # Hintergrund wird fertig, auf langsamen CI-Rechnern), zählt der Versuch nicht – bis zu 5 Anläufe.
        for _ in range(5):
            r = await c.js("""(async () => {
                await new Promise(r => setTimeout(r, 400));
                const before = statusSt.html; let n = 0;
                const mo = new MutationObserver(() => n++); mo.observe($('status'), {childList: true, subtree: true});
                for (let i = 0; i < 10; i++) { updateStatus(); await new Promise(r => setTimeout(r, 30)); }
                await new Promise(r => setTimeout(r, 300)); mo.disconnect();
                return {n, same: statusSt.html === before}; })()""")
            if r["same"]:
                break
        assert r["same"] and r["n"] == 0, r
    try:
        _im_browser(api, sz)
    finally:
        api.call("DELETE", f"/api/docs/{d['id']}")


def test_bibliothek_zeigt_gleichen_fortschritt_wie_player(api):
    """Regression: Bibliothek rechnete Abschnitt/(n−1) („fertig gehört“), Player (Abschnitt+Anteil)/n."""
    d = api.json("POST", "/api/docs", {"text": "Eins. " * 3 + "\n\nZwei. " * 3 + "\n\nDrei.\n\nVier.", "title": "Fortschritt"})[1]
    api.json("PATCH", f"/api/docs/{d['id']}", {"progress": {"chunk": d["count"] - 1, "offset": 0}})

    async def sz(c):
        await c.js("refreshLibrary()")
        await c.js(f"openDoc('{d['id']}')")
        await asyncio.sleep(1.0)
        await c.js("jumpTo(1, 0); pause(); 1")
        await asyncio.sleep(0.8)
        r = await c.js(f"""({{ fill: parseFloat($('fill').style.width),
            lib: parseFloat(document.querySelector('#library a[data-id="{d['id']}"] .pos').style.width),
            st: document.querySelector('#library a[data-id="{d['id']}"] .st').textContent }})""")
        assert abs(r["fill"] - r["lib"]) < 0.5 and r["st"] != "fertig gehört", r
    try:
        _im_browser(api, sz)
        p = api.json("GET", f"/api/docs/{d['id']}")[1]["progress"]
        assert p["chunk"] == 1 and "frac" in p                       # gespeichert, nicht nur angezeigt
    finally:
        api.call("DELETE", f"/api/docs/{d['id']}")
