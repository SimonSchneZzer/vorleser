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


JS_FILES = sorted((STATIC / "js").glob("*.js"))


def app_js() -> str:
    """Alle Teile der Oberfläche in Ladereihenfolge (wie index.html sie einbindet)."""
    html = (STATIC / "index.html").read_text("utf-8")
    return "\n".join((STATIC / src.lstrip("/")).read_text("utf-8") for src in re.findall(r'<script src="(/js/[^"]+)"', html))


@pytest.mark.skipif(shutil.which("node") is None, reason="Node.js fehlt")
@pytest.mark.parametrize("path", [STATIC / "i18n.js", *JS_FILES], ids=lambda p: p.name)
def test_js_syntax(path):
    r = subprocess.run(["node", "--check", str(path)], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr


def test_alle_js_teile_eingebunden():
    """Jede Datei in static/js/ steht genau einmal in index.html (sonst fehlt Code oder läuft doppelt)."""
    html = (STATIC / "index.html").read_text("utf-8")
    eingebunden = re.findall(r'<script src="/js/([^"]+)"', html)
    assert sorted(eingebunden) == [p.name for p in JS_FILES]
    assert len(set(eingebunden)) == len(eingebunden)


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
    """$("…")-Aufrufe in static/js/ müssen auf IDs in index.html (oder per JS erzeugte) zeigen."""
    html = (STATIC / "index.html").read_text("utf-8")
    js = app_js()
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
    """Seite neu laden und sicher auf die NEUE warten (die alte darf nicht mehr antworten).
    Unter Last kommt selten ein Skript nicht an („renderSettings is not defined“) – dann bis zu 3× neu laden und die
    Fehler dieses abgebrochenen Ladens verwerfen. Echte App-Fehler treten beim sauberen Laden wieder auf."""
    for versuch in range(3):
        fehler_vorher = len(c.errors)
        await c.js("window.__alteSeite = true; 1")
        await c.cmd("Page.reload", ignoreCache=True)
        for _ in range(60):
            await asyncio.sleep(0.25)
            try:
                # st.started: Start-Ablauf (Bibliothek laden, ersten Text öffnen) ist durch – sonst öffnet er den Text
                # mitten im Test und holt ihn z. B. aus den Einstellungen zurück (Windows-CI, 10.11.2026)
                if await c.js("!window.__alteSeite && typeof openDoc === 'function' && typeof st !== 'undefined' && !!st.settings && !!st.started"):
                    return
            except AssertionError:
                pass                                # Seite gerade im Wechsel
        del c.errors[fehler_vorher:]                 # Laden abgebrochen → dessen Folgefehler nicht der App anlasten
    raise AssertionError("Seite nicht neu geladen")


def _im_browser(api, szenario):
    """Headless-Chrome starten, App laden und `await szenario(c)` ausführen (c = Cdp)."""
    chrome = _chrome()
    if not chrome:
        pytest.skip("Chrome nicht gefunden (Pfad per CHROME=… setzen)")
    aiohttp = pytest.importorskip("aiohttp")
    port = _free_port()
    profile = tempfile.mkdtemp(prefix="vorleser-chrome-")
    proc = subprocess.Popen([chrome, "--headless=new", "--disable-gpu", "--no-first-run", "--autoplay-policy=no-user-gesture-required", "--mute-audio",   # Testtöne nie aus den Lautsprechern
                              f"--remote-debugging-port={port}",
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


@pytest.mark.browser
def test_satzflaeche_folgt_der_wortbox(api):
    """Verschiebt sich der Text, ohne dass der Leser seine Größe ändert, rückt highlight() Wort-Box UND Satz-Fläche
    zurecht (früher nur die Wort-Box – der Satz stand dann eine Stelle daneben)."""
    async def szenario(c):
        text = "# Titel\n\n" + " ".join(f"Das ist Satz Nummer {n}, der etwas länger ist, damit er umbricht." for n in range(12))
        _, d = api.json("POST", "/api/docs", {"title": "Satzfläche", "text": text})
        await _neu_laden(c)
        await c.js(f"openDoc('{d['id']}').then(() => 1)")
        await asyncio.sleep(0.6)
        await c.js("setWord(Math.min(30, st.words.list.length - 1)); 1")
        await asyncio.sleep(0.5)
        M = """(() => { const W = st.words, ws = W.list.filter((x) => x.sent === W.curSent);
            const w = ws[0].el.firstElementChild.getBoundingClientRect(), b = document.querySelector('#sboxes i').getBoundingClientRect();
            return [Math.round(w.top), Math.round(b.top)]; })()"""
        w, b = await c.js(M)
        assert abs(w - b) <= 2
        await c.js("document.querySelectorAll('#sboxes i').forEach((i) => i.style.transform += ' translateY(190px)'); 1")   # veraltet
        await c.js("highlight(false); 1")
        await asyncio.sleep(0.2)
        w, b = await c.js(M)
        assert abs(w - b) <= 2, (w, b)
        api.call("DELETE", f"/api/docs/{d['id']}")
    _im_browser(api, szenario)


@pytest.mark.browser
def test_schriften_kommen_aus_der_app(api):
    """Inter + Literata liegen in static/fonts (3.0.2) – laden ohne Internet, nichts von Google."""
    async def sz(c):
        ok = await c.js("""Promise.all([document.fonts.load('16px Inter'), document.fonts.load('600 16px Literata')])
            .then(() => ['Inter', 'Literata'].every((f) => document.fonts.check(`16px ${f}`)
                && [...document.fonts].some((x) => x.family.replace(/"|'/g, '') === f && x.status === 'loaded')))""")
        assert ok is True
        fremd = await c.js("performance.getEntriesByType('resource').map((r) => r.name).filter((n) => !n.startsWith(location.origin))")
        assert fremd == [], fremd
    _im_browser(api, sz)


@pytest.mark.browser
def test_kompakt_bibliothek_sichtbar_und_knopfreihe_oben(api):
    """Kompakte Ansicht: Seitenleiste zeigt die Bibliothek (Fußleiste war fensterhoch → 0 px), Knopfreihe oben neben
    dem Menü, Abschnitt/Restzeit/Status ausgeblendet; Schlaf-Timer öffnet unter dem Knopf statt außerhalb (10.11.2026)."""
    _, d = api.json("POST", "/api/docs", {"title": "Kompakt", "text": "Ein Satz. " * 30})

    async def sz(c):
        await c.cmd("Emulation.setDeviceMetricsOverride", width=480, height=420, deviceScaleFactor=1, mobile=False)
        await c.js("refreshLibrary()")
        await c.js(f"openDoc('{d['id']}').then(() => 1)")
        await asyncio.sleep(1.2)
        r = await c.js("""(() => { const m = document.querySelector('.compact-menu').getBoundingClientRect(),
            k = document.querySelector('.player .right').getBoundingClientRect(), vis = (id) => $(id).offsetParent !== null;
            return { compact: document.body.classList.contains('compact'), mitte: Math.abs((m.top + m.bottom) / 2 - (k.top + k.bottom) / 2),
                     posL: vis('posL'), posR: vis('posR'), status: vis('status') }; })()""")
        assert r == {"compact": True, "mitte": r["mitte"], "posL": False, "posR": False, "status": False} and r["mitte"] <= 2, r
        await c.js("document.querySelector('.compact-menu').click(); 1")
        await asyncio.sleep(0.5)
        assert await c.js("$('library').getBoundingClientRect().height") > 40
        await c.js("document.body.click(); $('sleepBtn').click(); 1")
        await asyncio.sleep(0.4)
        assert await c.js("$('sleepMenu').getBoundingClientRect().top") >= 0
    try:
        _im_browser(api, sz)
    finally:
        api.call("DELETE", f"/api/docs/{d['id']}")


@pytest.mark.browser
def test_playknopf_pulsiert_einmal_und_bibliothek_bleibt_stehen(api):
    """Board 27 (10.11.2026): Play-Knopf pulsiert beim Start einmal (vorher endlos → Akku); die Bibliothek passt beim
    Neuzeichnen ohne Strukturänderung nur Zahlen an (Einträge bleiben dieselben Elemente → Hover/Fokus bleiben)."""
    _, d = api.json("POST", "/api/docs", {"title": "Puls", "text": "Ein Satz. " * 30})

    async def sz(c):
        await c.js("refreshLibrary()")
        await c.js(f"openDoc('{d['id']}').then(() => 1)")
        await asyncio.sleep(0.8)
        await c.js("st.playWas = 'idle'; st.wantPlay = true; renderPlay(); 1")
        r = await c.js("""(() => { const b = $('playBtn'), cs = getComputedStyle(b);
            return { pulse: b.classList.contains('pulse'), n: cs.animationIterationCount, name: cs.animationName }; })()""")
        assert r == {"pulse": True, "n": "1", "name": "breathe"}, r
        await c.js("renderPlay(); 1")                       # weiter abspielen → kein neuer Puls, nichts Endloses
        assert "infinite" not in await c.js("getComputedStyle($('playBtn')).animationIterationCount")
        await c.js("st.wantPlay = false; renderPlay(); 1")
        a1 = await c.js(f"window._a = document.querySelector('#library a[data-id=\"{d['id']}\"]'); 1")
        await c.js("st.docs[0].prepared = 7; renderLibrary(); 1")
        same = await c.js(f"document.querySelector('#library a[data-id=\"{d['id']}\"]') === window._a")
        assert a1 == 1 and same is True
        assert await c.js("getComputedStyle(document.querySelector('#library .pos')).transitionTimingFunction") == "linear"
    try:
        _im_browser(api, sz)
    finally:
        api.call("DELETE", f"/api/docs/{d['id']}")


@pytest.mark.browser
def test_zurueck_zum_text_haelt_nicht_an_und_menue_spielt_ab(api):
    """Simon, 10.11.2026: abspielen → Einstellungen → in der Bibliothek zurück zum Text hielt die Wiedergabe an
    (openDoc lud neu → stop). Dazu „Abspielen“/„Pause“ als erster Eintrag im „…“-Menü der Bibliothek."""
    _, d = api.json("POST", "/api/docs", {"title": "Weiter", "text": "Ein Satz. " * 30})

    async def sz(c):
        await c.js("refreshLibrary()")
        await c.js(f"openDoc('{d['id']}').then(() => 1)")
        await asyncio.sleep(0.6)
        await c.js("st.wantPlay = true; $('settingsBtn').click(); 1")
        await asyncio.sleep(0.5)
        sel = f"#library a[data-id=\"{d['id']}\"]"
        await c.js(f"document.querySelector('{sel}').click(); 1")
        await asyncio.sleep(0.6)
        assert await c.js("[view, st.wantPlay]") == ["read", True]
        await c.js(f"libMenuOpen(document.querySelector('[data-dots=\"{d['id']}\"]')); 1")
        assert await c.js("$('libPlayLbl').textContent") == "Pause"
        await c.js("closePops(true); st.wantPlay = false; 1")
        await c.js(f"libMenuOpen(document.querySelector('[data-dots=\"{d['id']}\"]')); 1")
        assert await c.js("[$('libMenu').querySelector('button').dataset.act, $('libPlayLbl').textContent]") == ["play", "Abspielen"]
    try:
        _im_browser(api, sz)
    finally:
        api.call("DELETE", f"/api/docs/{d['id']}")


@pytest.mark.browser
def test_nur_mini_oder_normal_auch_in_einstellungen(api):
    """Simon, 10.11.2026: keine Zwischenstufe – unter 1000 px Mini-Player, auch aus den Einstellungen; dort keine
    Fußleiste (Einstellungen/Fehler melden) und kein „Neuer Text“. Größer ziehen → Einstellungen wie vorher."""
    _, d = api.json("POST", "/api/docs", {"title": "Mini", "text": "Ein Satz. " * 30})

    async def sz(c):
        async def size(w, h):
            await c.cmd("Emulation.setDeviceMetricsOverride", width=w, height=h, deviceScaleFactor=1, mobile=False)
            await asyncio.sleep(0.8)
        await c.js("refreshLibrary()")
        await c.js(f"openDoc('{d['id']}').then(() => 1)")
        await size(700, 620)
        assert await c.js("document.body.classList.contains('compact')") is True
        await size(1280, 800)
        await c.js("$('settingsBtn').click(); 1")
        await size(700, 620)
        r = await c.js("[view, document.body.classList.contains('compact'), $('sideFoot').offsetParent === null, $('newBtn').offsetParent === null]")
        assert r == ["settings", True, True, True], r
        await size(1280, 800)
        assert await c.js("[view, document.body.classList.contains('compact'), !$('viewSettings').classList.contains('hidden')]") == ["settings", False, True]
    try:
        _im_browser(api, sz)
    finally:
        api.call("DELETE", f"/api/docs/{d['id']}")


@pytest.mark.browser
def test_mini_wortbox_sitzt_nach_dem_umschalten(api):
    """Wechsel in den Mini-Player zoomt kurz (98 % → 100 %); die Wort-Box der Mitlesezeile wurde mittendrin gemessen und
    saß danach ~25 px neben dem Wort (Stand-Aufnahme 10.11.2026)."""
    text = "# Titel\n\n" + " ".join(f"Das ist Satz Nummer {n} mit einigen langen Wörtern wie Versteifungen und Bettdecke." for n in range(6))
    _, d = api.json("POST", "/api/docs", {"title": "Box", "text": text, "lang": "de"})
    api.json("PATCH", f"/api/docs/{d['id']}", {"progress": {"chunk": 1, "offset": 0, "frac": 0.6}})

    async def sz(c):
        await c.js("refreshLibrary()")
        await c.js(f"openDoc('{d['id']}').then(() => 1)")
        await asyncio.sleep(1.0)
        await c.cmd("Emulation.setDeviceMetricsOverride", width=700, height=620, deviceScaleFactor=1, mobile=False)
        await asyncio.sleep(1.2)
        r = await c.js("""(() => { const b = document.querySelector('#mlWin .wbox'), w = document.querySelector('#mlWin .mw.cur');
            if (!b || !w) return null; const a = b.getBoundingClientRect(), e = w.getBoundingClientRect();
            return Math.abs((a.left + a.right) / 2 - (e.left + e.right) / 2); })()""")
        assert r is not None and r <= 3, r
    try:
        _im_browser(api, sz)
    finally:
        api.call("DELETE", f"/api/docs/{d['id']}")
