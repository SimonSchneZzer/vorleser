"""Player-Layout und Bewegungen (3.0.3): nichts überlappt, nichts springt."""
import asyncio

import pytest

from test_frontend import _im_browser, _neu_laden


@pytest.mark.browser
def test_player_rechts_laeuft_nicht_ueber_die_knoepfe(api):
    """Lange Beschriftung am Schlaf-Timer (z. B. „End of chapter“) in einem schmalen Fenster: die rechte Gruppe darf
    nicht nach links über Vorspulen/Weiter laufen – die Beschriftungen weichen der Reihe nach."""
    _, d = api.json("POST", "/api/docs", {"title": "Breite", "text": "Ein Satz zum Testen. " * 20})

    async def sz(c):
        await c.cmd("Emulation.setDeviceMetricsOverride", width=1180, height=760, deviceScaleFactor=1, mobile=False)
        await _neu_laden(c)
        await c.js(f"openDoc('{d['id']}').then(() => 1)"); await asyncio.sleep(0.5)
        for breite in (1180, 1100, 1030, 1005):                                   # bis kurz vor den Mini-Player (< 1000 px)
            await c.cmd("Emulation.setDeviceMetricsOverride", width=breite, height=760, deviceScaleFactor=1, mobile=False)
            await c.js("$('sleepBtn').classList.add('on'); $('sleepLbl').textContent = 'End of chapter'; $('atmoBtn').classList.add('on'); $('atmoLbl').textContent = 'Kaminfeuer'; 1")
            await asyncio.sleep(0.5)
            r = await c.js("""(() => { const n = $('nextBtn').getBoundingClientRect().right;
                const first = [...document.querySelector('.player .right').children].find((x) => x.getClientRects().length);
                return { next: n, right: first.getBoundingClientRect().left }; })()""")
            assert r["right"] >= r["next"] + 4, f"überlappt bei {breite} px: {r}"
    try:
        _im_browser(api, sz)
    finally:
        api.call("DELETE", f"/api/docs/{d['id']}")


@pytest.mark.browser
def test_status_als_toast_und_dialog_schliesst_weich(api):
    """3.0.3: Puffern erscheint verzögert als Toast mit „Offline-Stimme“ und bleibt, bis ✕; danach erst bei neuem Zustand.
    Dialoge: close() blendet aus und schließt erst danach – `open` gilt sofort als zu, showModal() bricht das Schließen ab."""
    _, d = api.json("POST", "/api/docs", {"title": "Status", "text": "Ein Satz zum Vorlesen. Noch ein Satz."})
    import server
    with server._doc_lock:
        doc = server.load_doc(d["id"]); doc["voice"] = "edge:de-DE-KatjaNeural"; server.save_doc(doc)

    async def sz(c):
        # CI-Rechner melden „Bewegung reduzieren“ → dann schließt ein Dialog absichtlich sofort; hier die Bewegung prüfen
        await c.cmd("Emulation.setEmulatedMedia", features=[{"name": "prefers-reduced-motion", "value": "no-preference"}])
        await _neu_laden(c)
        await c.js(f"openDoc('{d['id']}').then(() => 1)"); await asyncio.sleep(0.5)
        assert not await c.js("reducedMotion.matches")
        # Laden simulieren, häufig aktualisieren (wie beim Abspielen) – der Toast muss trotzdem nach ~0,7 s kommen
        await c.js("window.loadingVisible = () => true; st.waitSince = Date.now(); statusSt.html = ''; statusSt.closed = ''; window.__t = setInterval(updateStatus, 100); 1")
        await asyncio.sleep(0.3)
        assert not await c.js("$('stToast').classList.contains('show')")             # nicht sofort (kein Aufblitzen)
        for _ in range(40):                      # erscheint nach ~0,7 s – unter CI-Last etwas später
            if await c.js("$('stToast').classList.contains('show')"):
                break
            await asyncio.sleep(0.1)
        assert await c.js("$('stToast').classList.contains('show') && !!$('stToast').querySelector('[data-offline]')")
        await c.js("$('stToast').querySelector('[data-stx]').click(); 1"); await asyncio.sleep(0.4)
        assert not await c.js("$('stToast').classList.contains('show')")             # ✕ → bleibt weg, solange es lädt
        await c.js("clearInterval(window.__t); 1")
        # Dialog weich schließen
        r = await c.js("""(async () => { const dl = $('bugDlg'); dl.showModal(); await new Promise(r => setTimeout(r, 350));
            dl.close(); const mid = { open: dl.open, attr: dl.hasAttribute('open'), closing: dl.classList.contains('closing') };
            await new Promise(r => setTimeout(r, 300)); return { mid, after: dl.hasAttribute('open') }; })()""")
        assert r["mid"] == {"open": False, "attr": True, "closing": True} and r["after"] is False, r
        r = await c.js("""(async () => { const dl = $('bugDlg'); dl.showModal(); await new Promise(r => setTimeout(r, 350));
            dl.close(); await new Promise(r => setTimeout(r, 50)); dl.showModal(); await new Promise(r => setTimeout(r, 300));
            const o = dl.open; dl.close(); return o; })()""")
        assert r is True                                                              # wieder geöffnet → bleibt offen
    try:
        _im_browser(api, sz)
    finally:
        api.call("DELETE", f"/api/docs/{d['id']}")


@pytest.mark.browser
def test_fortschrittsbalken_laeuft_fluessig(api):
    """3.0.3: beim Abspielen wird der Balken in jedem Bild nachgezogen, nicht nur bei `timeupdate` (~4× pro Sekunde)."""
    _, d = api.json("POST", "/api/docs", {"title": "Flüssig", "text": "Ein etwas längerer Satz zum Vorlesen, damit es ein paar Sekunden dauert. " * 3})

    async def sz(c):
        await _neu_laden(c)
        await c.js(f"openDoc('{d['id']}').then(() => 1)"); await asyncio.sleep(0.5)
        await c.js("play(); 1")
        for _ in range(200):
            if await c.js("!audio.paused && st.loadedIdx === st.idx && audio.currentTime > 0.2"):
                break
            await asyncio.sleep(0.1)
        n = await c.js("""new Promise((res) => { const seen = new Set(); const t0 = performance.now();
            const f = () => { seen.add($('fill').style.width); if (performance.now() - t0 < 1000) requestAnimationFrame(f); else res(seen.size); };
            requestAnimationFrame(f); })""")
        await c.js("pause(); 1")
        assert n >= 20, f"nur {n} verschiedene Stände in 1 s"
    try:
        _im_browser(api, sz)
    finally:
        api.call("DELETE", f"/api/docs/{d['id']}")


@pytest.mark.browser
def test_neuer_text_kein_cursor_nach_dem_laden(api):
    """3.0.4: Nach dem Ersetzen durch Datei/Link-Inhalt blinkt kein Cursor mehr im Feld (Fokus wird abgegeben)."""
    async def sz(c):
        await _neu_laden(c)
        await c.js("showNew(); 1"); await asyncio.sleep(0.4)
        await c.js("nt.focusEnd(); 1")
        assert await c.js("$('ntDoc').contains(document.activeElement)")              # leeres Feld: Cursor bereit
        await c.js("replaceField('Titel', '# Erster Teil\\n\\nEin Satz aus der Datei.', 'Ersetzt'); 1"); await asyncio.sleep(0.2)
        assert await c.js("!$('ntDoc').contains(document.activeElement) && !$('ntDoc').contains(getSelection().anchorNode)")
        await c.js("ntSet('', ''); 1")
    _im_browser(api, sz)


@pytest.mark.browser
def test_beschriftung_rollt_auf_englisch_nicht_dauernd(api):
    """3.0.4: auf Englisch übersetzt i18n.js nach dem Setzen – „Erzeuge 0/266“ ≠ „Generating 0/266“ sah wie eine Änderung
    aus, die Beschriftung rollte alle 2 s neu und der Knopf wurde kurz auf die deutsche Länge gekürzt („Generating …“)."""
    _, d = api.json("POST", "/api/docs", {"title": "Englisch", "text": "One sentence to read. Another one here. " * 5})
    api.json("PATCH", "/api/settings", {"uiLang": "en"})

    async def sz(c):
        await c.cmd("Emulation.setEmulatedMedia", features=[{"name": "prefers-reduced-motion", "value": "no-preference"}])
        await c.js("try { localStorage.setItem('vorleser.ui', 'en'); } catch {} 1")
        await _neu_laden(c)
        await c.js(f"openDoc('{d['id']}').then(() => 1)"); await asyncio.sleep(0.8)
        assert (await c.js("$('posL').textContent")).startswith("Section")
        await asyncio.sleep(0.6)                                                       # alles in Ruhe
        n = await c.js("(() => { posRender(); return $('posL').getAnimations().length; })()")
        assert n == 0, "gleicher Text darf nicht neu rollen"
        # Bibliothek neu gezeichnet (frisches Element, schon übersetzt) → Stand darf nicht neu einrollen („finished“ flackerte)
        n = await c.js("""(async () => { const n = st.doc.chunks.length;
            st.doc.progress = { ...st.doc.progress, chunk: n - 1, frac: 1, updated: Date.now() / 1000 };   // „fertig gehört“
            st.docs.find((x) => x.id === st.doc.id).progress = { ...st.doc.progress };
            libSync(); await new Promise((r) => setTimeout(r, 700));                      // Stand steht, alles ruht
            st.libSig = 'x,y,z'; renderLibrary(); await new Promise((r) => setTimeout(r, 50));   // ganz neu gezeichnet
            libSync(); const s = $('library').querySelector('a[data-id] .st'); return s.textContent === 'finished' ? s.getAnimations().length : 'Stand: ' + s.textContent; })()""")
        assert n == 0, "frisch gezeichneter Eintrag darf nicht einrollen"
        # Knopf mit Beschriftung: neue Breite passt zum übersetzten Text (kein abgeschnittenes „…“)
        r = await c.js("""(async () => { const b = $('prepBtn'), l = $('prepLbl'); b.classList.remove('hidden');
            rollText(l, 'Vorab erzeugen'); await new Promise((r) => setTimeout(r, 200));
            rollText(l, 'Erzeuge 0/266'); await new Promise((r) => setTimeout(r, 700));
            return { txt: l.textContent, fits: l.scrollWidth <= l.clientWidth + 1 && b.scrollWidth <= b.clientWidth + 1 }; })()""")
        assert r["txt"] == "Generating 0/266" and r["fits"], r
    try:
        _im_browser(api, sz)
    finally:
        api.json("PATCH", "/api/settings", {"uiLang": "de"})
        api.call("DELETE", f"/api/docs/{d['id']}")


@pytest.mark.browser
def test_gliederung_mit_vielen_kapiteln_ueberlappt_nicht(api):
    """3.0.4: ~30 Überschriften (news.ORF.at-Startseite) – die Einträge der Gliederung wurden zusammengequetscht und
    überlappten; jetzt behalten sie ihre Höhe und die Liste scrollt."""
    async def sz(c):
        await _neu_laden(c)
        await c.js("showNew(); 1"); await asyncio.sleep(0.4)
        text = "\\n\\n".join(f"# Überschrift Nummer {i} mit etwas längerem Titel\\n\\nEin Satz darunter." for i in range(30))
        r = await c.js(f"""(async () => {{ ntSet("{text}", "Viele"); await new Promise((r) => setTimeout(r, 300));
            const toc = document.querySelector('#viewNew .ed-toc'), bs = [...toc.querySelectorAll('button')];
            const hs = bs.map((b) => b.getBoundingClientRect());
            const overlap = hs.some((h, i) => i && h.top < hs[i - 1].bottom - 0.5);
            return {{ n: bs.length, overlap, minH: Math.min(...hs.map((h) => h.height)), scrolls: toc.scrollHeight > toc.clientHeight }}; }})()""")
        await c.js("ntSet('', ''); 1")
        assert r["n"] == 30 and not r["overlap"] and r["minH"] >= 24 and r["scrolls"], r
    _im_browser(api, sz)
