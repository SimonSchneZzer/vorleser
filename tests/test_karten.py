"""Version 3.0: Karten-Stapel unten rechts (Board 21) und „Vorab erzeugen fortsetzen“ (Board 20)."""
import asyncio
import sys

import pytest

import exporter
from test_frontend import _im_browser, _neu_laden


def test_unterbrochenes_vorab_erzeugen_wird_gemerkt(api, monkeypatch):
    _, d = api.json("POST", "/api/docs", {"title": "Vorab", "text": "Ein Satz. Noch ein Satz. Und noch einer."})
    try:
        exporter.set_pending(d["id"], True)                    # so bleibt es stehen, wenn die App mittendrin beendet wird
        status, r = api.json("GET", "/api/prepare/pending")
        assert status == 200 and [i["doc"] for i in r["items"]] == [d["id"]]
        assert r["items"][0]["total"] >= 1 and r["items"][0]["title"] == "Vorab"
        monkeypatch.setattr(exporter, "start", lambda doc, fmt: {"status": "running"})
        status, r = api.json("POST", "/api/prepare/resume")
        assert status == 200 and r["started"] == [d["id"]]
    finally:
        exporter.set_pending(d["id"], False)
        api.call("DELETE", f"/api/docs/{d['id']}")


def test_gelöschter_text_fliegt_von_der_merkliste(api):
    exporter.set_pending("0" * 32, True)
    status, r = api.json("GET", "/api/prepare/pending")
    assert status == 200 and r["items"] == []
    assert "0" * 32 not in exporter.pending_ids()


def test_normales_ende_streicht_den_eintrag(monkeypatch):
    doc = {"id": "a" * 32, "chunks": [{"text": "x"}], "voice": "edge:de-DE-KatjaNeural", "lang": "de"}
    monkeypatch.setattr(exporter, "_prepare_run", lambda d: None)
    exporter.set_pending(doc["id"], True)
    exporter._prepare(doc, "prepare")
    assert doc["id"] not in exporter.pending_ids()


@pytest.mark.browser
def test_karten_stapel(api):
    async def sz(c):
        await _neu_laden(c)
        js = """(() => {
          const vis = (id) => !$(id).classList.contains('hidden') && !$(id).classList.contains('leaving');
          return { upd: vis('upd'), prep: vis('prepCard'), more: $('upd').dataset.more || $('prepCard').dataset.more || null,
                   peek1: $('cardPeek1').classList.contains('on') };
        })()"""
        await c.js("cardPut('prep', $('prepCard'), 'aktion'); cardPut('update', $('upd'), 'info'); 1")
        await asyncio.sleep(0.4)
        r = await c.js(js)
        assert r["prep"] and not r["upd"] and r["more"] == "1" and r["peek1"]   # Aktion vor Info, Info wartet dahinter
        await c.js("cardPut('update', $('upd'), 'dringend', true); 1")        # z. B. Update lädt → nach vorne
        await asyncio.sleep(0.4)
        r = await c.js(js)
        assert r["upd"] and not r["prep"]
        await c.js("cardDrop('update'); 1")                                   # fertig → die wartende rückt nach
        await asyncio.sleep(0.4)
        r = await c.js(js)
        assert r["prep"] and not r["upd"] and r["more"] is None and not r["peek1"]
        assert await c.js("(() => { try { cardPut('x', $('upd'), undefined); return false; } catch { return true; } })()")   # Stufe ist Pflicht
        await c.js("cardDrop('prep'); 1")
    _im_browser(api, sz)


# --------------------------------------------------------------------------- #
# Link-Reiter (Etappe 1)
# --------------------------------------------------------------------------- #
ARTIKEL = ("""<html><head><title>Radwege | Beispiel-Zeitung</title><meta property="og:title" content="Zwölf neue Radwege"></head><body>
<nav>Start Politik Sport</nav><div class="cookie-banner">Wir nutzen Cookies</div>
<article><h1>Zwölf neue Radwege</h1><p>""" + "Die Stadt plant neue Radwege für alle. " * 20 + """</p><h2>Wo gebaut wird</h2><p>"""
           + "Vor allem in den Außenbezirken wird gebaut. " * 10 + """</p><div class="share-buttons">Teilen auf X</div></article>
<footer>Impressum</footer></body></html>""").encode()


def test_link_holt_nur_den_artikel(api, monkeypatch):
    import importers
    monkeypatch.setattr(importers, "_fetch", lambda url: (ARTIKEL, "utf-8"))
    status, d = api.json("POST", "/api/import-url", {"url": "https://www.beispiel.at/radwege"})
    assert status == 200 and d["title"] == "Zwölf neue Radwege" and d["source"] == "beispiel.at" and d["lang"] == "de"
    assert "# Wo gebaut wird" in d["text"] and "Cookies" not in d["text"] and "Teilen" not in d["text"] and "Impressum" not in d["text"]


@pytest.mark.parametrize("url, fetch, msg", [
    ("ftp://x", None, "LINK_UNGUELTIG"),
    ("https://x.at/a", (b"<html><body><p>Nur kurz.</p></body></html>", "utf-8"), "LINK_KEIN_TEXT"),
])
def test_link_fehler_verstaendlich(api, monkeypatch, url, fetch, msg):
    import importers
    if fetch:
        monkeypatch.setattr(importers, "_fetch", lambda u: fetch)
    status, d = api.json("POST", "/api/import-url", {"url": url})
    assert status == 400 and d["error"] == getattr(importers, msg)


@pytest.mark.browser
def test_link_reiter_im_browser(api, monkeypatch):
    import importers
    monkeypatch.setattr(importers, "_fetch", lambda url: (ARTIKEL, "utf-8"))

    async def sz(c):
        await _neu_laden(c)
        await c.js("showNew(); setSrc('link'); $('linkUrl').value = 'https://beispiel.at/radwege'; $('linkForm').requestSubmit(); 1")
        for _ in range(30):
            await asyncio.sleep(0.2)
            if await c.js("!$('linkCard').classList.contains('hidden')"):
                break
        r = await c.js("({ title: $('linkTitle').textContent, meta: $('linkMeta').textContent, text: $('text').value.slice(0, 40), btn: $('createBtn').disabled })")
        assert r["title"] == "Zwölf neue Radwege" and r["meta"].startswith("beispiel.at") and r["text"].startswith("Die Stadt") and not r["btn"]
    _im_browser(api, sz)


# --------------------------------------------------------------------------- #
# Markierten Text vorlesen: Backend + Mini-Player (Etappe 1, Teil A)
# --------------------------------------------------------------------------- #
def test_markierter_text_backend(api, monkeypatch):
    import tts
    from conftest import sine_wav
    monkeypatch.setattr(tts, "synthesize", lambda text, voice, lang, **k: (sine_wav(0.3), "audio/wav", voice))
    status, q = api.json("POST", "/api/quick", {"text": "Die Stadt plant neue Radwege. Sie sollen sicher sein."})
    assert status == 200 and q["count"] >= 1 and q["lang"] == "de" and q["preview"].startswith("Die Stadt")
    status, _, data = api.call("GET", f"/api/quick/{q['id']}/audio/0")
    assert status == 200 and data[:4] == b"RIFF"
    before = len(api.json("GET", "/api/docs")[1]["docs"])
    status, d = api.json("POST", f"/api/quick/{q['id']}/save")
    assert status == 201 and len(api.json("GET", "/api/docs")[1]["docs"]) == before + 1
    api.call("DELETE", f"/api/docs/{d['id']}")
    assert api.json("POST", "/api/quick", {"text": "  "})[0] == 400


@pytest.mark.browser
def test_mini_player(api, monkeypatch):
    import tts
    from conftest import sine_wav
    monkeypatch.setattr(tts, "synthesize", lambda text, voice, lang, **k: (sine_wav(1.0), "audio/wav", voice))
    _, q = api.json("POST", "/api/quick", {"text": "Die Stadt plant neue Radwege. Sie sollen sicher und schnell sein."})

    async def sz(c):
        await c.cmd("Page.navigate", url=f"{api.base}/mini#q={q['id']}")
        await asyncio.sleep(1.5)
        r = await c.js("({ prev: document.getElementById('prev').textContent, voice: document.getElementById('voice').textContent, warn: document.getElementById('warn').hidden, err: document.getElementById('err').hidden })")
        assert r["prev"].startswith("„Die Stadt") and r["voice"] and r["warn"] and r["err"]
    _im_browser(api, sz)


def test_original_wird_gespeichert_aber_nicht_mitgeschickt(api):
    status, d = api.json("POST", "/api/docs", {"title": "PDF", "text": "Aufgeräumter Text zum Vorlesen.", "original": "Kopfzeile\nRoher Text-\nzum Vorlesen. 12"})
    try:
        _, full = api.json("GET", f"/api/docs/{d['id']}")
        assert full["hasOriginal"] is True and "original" not in full
        status, o = api.json("GET", f"/api/docs/{d['id']}/original")
        assert status == 200 and o["text"].startswith("Kopfzeile")
    finally:
        api.call("DELETE", f"/api/docs/{d['id']}")


# --------------------------------------------------------------------------- #
# Aussprache-Wörterbuch (Etappe 2)
# --------------------------------------------------------------------------- #
def test_aussprache_aendert_gesprochenen_text_und_schluessel(monkeypatch, tmp_path):
    import tts
    monkeypatch.setattr(tts, "LEX_FILE", tmp_path / "aussprache.json")
    tts._lex["mtime"] = None
    assert tts.spoken("Das ist z. B. so.") == "Das ist zum Beispiel so."              # Vorbelegung
    vorher = tts.cache_path("Nietzsche las viel.", "edge:de-DE-KatjaNeural")
    tts.lexikon_speichern(tts.lexikon() + [{"wort": "Nietzsche", "sprich": "Nietsche"},
                                           {"wort": "Samsa", "sprich": "Sam-sa", "doc": "a" * 32}])
    assert tts.spoken("Nietzsche las viel.") == "Nietsche las viel."
    assert tts.cache_path("Nietzsche las viel.", "edge:de-DE-KatjaNeural") != vorher    # → wird neu erzeugt
    assert tts.spoken("Gregor Samsa.") == "Gregor Samsa."                                 # nur in Text a…a
    assert tts.spoken("Gregor Samsa.", "a" * 32) == "Gregor Sam-sa."
    assert tts.spoken("Nietzsches Werk") == "Nietzsches Werk"                             # nur ganze Wörter
    tts._lex["mtime"] = None


@pytest.mark.browser
def test_rechtsklick_aussprache(api, monkeypatch, tmp_path):
    import tts
    monkeypatch.setattr(tts, "LEX_FILE", tmp_path / "a.json"); tts._lex["mtime"] = None
    _, d = api.json("POST", "/api/docs", {"title": "Aussprache", "text": "Gregor Samsa erwachte eines Morgens aus unruhigen Träumen."})

    async def sz(c):
        await _neu_laden(c)
        await c.js(f"openDoc('{d['id']}').then(() => 1)"); await asyncio.sleep(0.8)
        x, y = await c.js("""(() => { const n = [...document.querySelectorAll('#docText *')].find((e) => e.childNodes.length === 1 && /Samsa/.test(e.textContent) && e.children.length === 0) || $('docText');
            const t = document.createTreeWalker(n, NodeFilter.SHOW_TEXT); let tn; while ((tn = t.nextNode())) { const i = tn.textContent.indexOf('Samsa'); if (i >= 0) { const r = document.createRange(); r.setStart(tn, i + 2); r.setEnd(tn, i + 3); const b = r.getBoundingClientRect(); return [b.x + 1, b.y + b.height / 2]; } } })()""")
        await c.cmd("Input.dispatchMouseEvent", type="mousePressed", x=x, y=y, button="right", clickCount=1)
        await c.cmd("Input.dispatchMouseEvent", type="mouseReleased", x=x, y=y, button="right", clickCount=1)
        await asyncio.sleep(0.4)
        assert await c.js("!$('lexMenu').classList.contains('hidden')")
        await c.js("$('lexMenuSay').click(); 1"); await asyncio.sleep(0.6)
        assert await c.js("$('lexPopWord').textContent") == "Samsa"
        await c.js("$('lexPopSay').value = 'Sam-sa'; $('lexPopDoc').click(); 1"); await asyncio.sleep(0.4)
        await c.js("$('lexPopSave').click(); 1"); await asyncio.sleep(0.6)
    try:
        _im_browser(api, sz)
        assert {"wort": "Samsa", "sprich": "Sam-sa", "doc": d["id"], "lang": "de"} in tts.lexikon()
    finally:
        tts._lex["mtime"] = None
        api.call("DELETE", f"/api/docs/{d['id']}")


@pytest.mark.browser
def test_schlaf_timer(api):
    _, d = api.json("POST", "/api/docs", {"title": "Schlaf", "text": "Ein Satz zum Einschlafen. Und noch einer."})

    async def sz(c):
        await _neu_laden(c)
        await c.js(f"localStorage.removeItem('vorleser.sleep'); openDoc('{d['id']}').then(() => 1)"); await asyncio.sleep(0.6)
        await c.js("$('sleepBtn').click(); 1"); await asyncio.sleep(0.3)
        assert await c.js("!$('sleepMenu').classList.contains('hidden')")            # erstes Mal: Auswahl
        await c.js("$('sleepOpts').querySelector('[data-i=\"2\"]').click(); 1"); await asyncio.sleep(0.2)
        assert await c.js("$('sleepLbl').textContent") == "30:00"
        await c.js("sleepSet(null); 1")
        await c.js("$('sleepBtn').click(); 1"); await asyncio.sleep(0.2)                # danach: ein Klick reicht
        assert await c.js("$('sleepLbl').textContent") == "30:00" and await c.js("$('sleepMenu').classList.contains('hidden')")
        await c.js("sleepSet(null); 1")
    try:
        _im_browser(api, sz)
    finally:
        api.call("DELETE", f"/api/docs/{d['id']}")


# --------------------------------------------------------------------------- #
# Lesezeichen (Etappe 3)
# --------------------------------------------------------------------------- #
def test_lesezeichen_backend(api):
    _, d = api.json("POST", "/api/docs", {"title": "LZ", "text": "Erster Satz hier. " * 40 + "\n\nZweiter Absatz mit anderem Inhalt. " * 30})
    try:
        _, full = api.json("GET", f"/api/docs/{d['id']}")
        n = len(full["chunks"]); assert n >= 3
        status, r = api.json("POST", f"/api/docs/{d['id']}/bookmarks", {"chunk": n - 1})
        assert status == 200 and len(r["bookmarks"]) == 1 and r["bookmarks"][0]["chunk"] == n - 1
        assert api.json("POST", f"/api/docs/{d['id']}/bookmarks", {"chunk": n - 1})[1]["bookmarks"].__len__() == 1   # nicht doppelt
        bid = r["bookmarks"][0]["id"]
        assert api.json("PATCH", f"/api/docs/{d['id']}/bookmarks/{bid}", {"note": "Zitat fürs Referat"})[1]["bookmarks"][0]["note"] == "Zitat fürs Referat"
        # Text bearbeiten: davor etwas einfügen → Lesezeichen wandert mit
        _, t = api.json("GET", f"/api/docs/{d['id']}/text")
        api.json("PUT", f"/api/docs/{d['id']}/text", {"text": "Ganz neuer Anfang.\n\n" + t["text"]})
        _, full = api.json("GET", f"/api/docs/{d['id']}")
        bm = full["bookmarks"][0]
        assert full["chunks"][bm["chunk"]]["text"].startswith(r["bookmarks"][0]["text"][:40])
        assert api.json("DELETE", f"/api/docs/{d['id']}/bookmarks/{bid}")[1]["bookmarks"] == []
    finally:
        api.call("DELETE", f"/api/docs/{d['id']}")


@pytest.mark.browser
def test_lesezeichen_im_browser(api):
    _, d = api.json("POST", "/api/docs", {"title": "Die Verwandlung", "text": "# Erster Teil\n\n" + "Als Gregor Samsa eines Morgens aus unruhigen Träumen erwachte, fand er sich verwandelt. " * 6
                                          + "\n\nEr lag auf seinem panzerartig harten Rücken und sah seinen gewölbten Bauch. " * 6})

    async def sz(c):
        await c.cmd("Emulation.setDeviceMetricsOverride", width=1280, height=800, deviceScaleFactor=1, mobile=False)
        await _neu_laden(c)
        await c.js(f"localStorage.removeItem('vorleser.bmHint'); openDoc('{d['id']}').then(() => 1)"); await asyncio.sleep(0.8)
        x, y = await c.js("(() => { const r = st.spans[2].getClientRects()[0]; return [r.x + 30, r.y + r.height / 2]; })()")
        await c.cmd("Input.dispatchMouseEvent", type="mouseMoved", x=x, y=y); await asyncio.sleep(0.4)
        assert await c.js("$('bmHover').classList.contains('on')")
        hx, hy = await c.js("(() => { const r = $('bmHover').getBoundingClientRect(); return [r.x + r.width / 2, r.y + r.height / 2]; })()")
        await c.cmd("Input.dispatchMouseEvent", type="mouseMoved", x=hx, y=hy)
        await c.cmd("Input.dispatchMouseEvent", type="mousePressed", x=hx, y=hy, button="left", clickCount=1)
        await c.cmd("Input.dispatchMouseEvent", type="mouseReleased", x=hx, y=hy, button="left", clickCount=1)
        for _ in range(40):
            await asyncio.sleep(0.15)
            if await c.js("!!document.querySelector('#bmHint.card-on')"):
                break
        assert await c.js("st.doc.bookmarks.length") == 1 and await c.js("!$('bmHint').classList.contains('hidden')")
        assert await c.js("!!$('chapterMenu').querySelector('.cm-bm')")              # Reiter „Lesezeichen“ offen
        await c.js("$('bmHintOk').click(); 1"); await asyncio.sleep(0.5)
        await c.js("document.querySelector('.bm-mark').click(); 1"); await asyncio.sleep(0.4)
        await c.js("$('bmPopDel').click(); 1"); await asyncio.sleep(0.6)
        assert await c.js("st.doc.bookmarks.length") == 0
    try:
        _im_browser(api, sz)
    finally:
        api.call("DELETE", f"/api/docs/{d['id']}")


@pytest.mark.browser
def test_was_bisher_geschah(api):
    _, d = api.json("POST", "/api/docs", {"title": "Rückblick", "text": "\n\n".join(f"Absatz {n}. Hier steht ein Satz. Und noch einer dazu." for n in range(8))})

    async def sz(c):
        await _neu_laden(c)
        await c.js(f"openDoc('{d['id']}').then(() => 1)"); await asyncio.sleep(0.6)
        r = await c.js("""(() => { window.playFrom = (i) => { window.__from = i; };   // ohne Audio
            st.idx = 5; st.doc.progress.updated = Date.now() / 1000 - 3 * 86400;
            const ok = recapStart(0);
            return { ok, from: window.__from, bar: !$('recapBar').classList.contains('hidden'), dim: document.querySelectorAll('.chunk.recap').length }; })()""")
        assert r["ok"] and r["from"] < 5 and r["bar"] and r["dim"] >= 1
        assert await c.js("st.idx = 4; recapNext()")                                  # Ende der Wiederholung → zurück an Stelle 5
        assert await c.js("window.__from") == 5
        assert not await c.js("st.idx = 5; st.doc.progress.updated = Date.now() / 1000; recap.done.clear(); recapStart(0)")   # kurze Pause: nichts
    try:
        _im_browser(api, sz)
    finally:
        api.call("DELETE", f"/api/docs/{d['id']}")


# --------------------------------------------------------------------------- #
# Hör-Rückblick (Etappe 3)
# --------------------------------------------------------------------------- #
def test_hoerzeit_woche(api, monkeypatch, tmp_path):
    import server
    monkeypatch.setattr(server, "STATS_FILE", tmp_path / "hoerzeit.json")
    _, d = api.json("POST", "/api/docs", {"title": "Der Prozess", "text": "Jemand musste Josef K. verleumdet haben."})
    try:
        assert api.json("POST", "/api/hoerzeit", {"doc": d["id"], "secs": 125})[0] == 200
        assert api.json("POST", "/api/hoerzeit", {"doc": d["id"], "finished": True})[0] == 200
        assert api.json("POST", "/api/hoerzeit", {"doc": d["id"], "secs": 9999})[0] == 400      # unplausibel
        _, w = api.json("GET", "/api/hoerzeit/woche")
        assert w["total"] == 125 and w["finished"] == 1 and w["top"] == "Der Prozess" and len(w["days"]) == 7
    finally:
        api.call("DELETE", f"/api/docs/{d['id']}")


# --------------------------------------------------------------------------- #
# Editor (Text bearbeiten): Absätze, Überschriften, Suchen & ersetzen
# --------------------------------------------------------------------------- #
def test_editor_absaetze_und_ueberschriften(api):
    _, d = api.json("POST", "/api/docs", {"title": "Ed", "text": "# Anfang\n\nErster Absatz hier.\n\nZweiter Absatz da."})

    async def sz(c):
        await _neu_laden(c)
        await c.js(f"openDoc('{d['id']}').then(() => openEditor()).then(() => 1)"); await asyncio.sleep(0.6)
        assert await c.js("[...$('edDoc').children].map(n => n.nodeName).join()") == "H2,P,P"
        assert await c.js("$('edToc').querySelectorAll('button').length") == 1
        # Enter am Ende des letzten Absatzes → neuer Absatz, Text tippen
        await c.js("(() => { const p = $('edDoc').lastElementChild, r = document.createRange(); r.selectNodeContents(p); r.collapse(false);"
                   " $('edDoc').focus(); getSelection().removeAllRanges(); getSelection().addRange(r); return 1; })()")
        for t in ("keyDown", "char", "keyUp"):
            await c.cmd("Input.dispatchKeyEvent", type=t, key="Enter", code="Enter", windowsVirtualKeyCode=13, text="\r")
        await c.cmd("Input.insertText", text="Neues Kapitel")
        await c.js("$('edH').click(); 1"); await asyncio.sleep(0.1)          # zur Überschrift machen
        assert await c.js("$('edToc').querySelectorAll('button').length") == 2
        assert await c.js("edSerialize()") == "# Anfang\n\nErster Absatz hier.\n\nZweiter Absatz da.\n\n# Neues Kapitel"
        assert await c.js("!$('edSave').disabled")
        await c.js("$('edFindBtn').click(); $('edFindQ').value = 'Absatz'; $('edFindQ').oninput(); 1")
        assert await c.js("$('edFindN').textContent") == "2 Treffer"
        await c.js("$('edFindR').value = 'Teil'; $('edFindAll').click(); 1")
        assert "Erster Teil hier." in await c.js("edSerialize()")
        assert await c.js("$('edOrig').classList.contains('hidden')")         # kein PDF → kein Original
        await c.js("saveEdit().then(() => 1)"); await asyncio.sleep(0.5)
    try:
        _im_browser(api, sz)
        _, t = api.json("GET", f"/api/docs/{d['id']}/text")
        assert t["text"].endswith("# Neues Kapitel") and "Zweiter Teil da." in t["text"]
    finally:
        api.call("DELETE", f"/api/docs/{d['id']}")


# --------------------------------------------------------------------------- #
# Atmosphäre (Etappe 3)
# --------------------------------------------------------------------------- #
def test_atmosphaere_einstellungen():
    import settings
    settings.update({"ambient": "regen", "ambientVol": 60})
    assert settings.get("ambient") == "regen" and settings.get("ambientVol") == 60
    settings.update({"ambient": "disko", "ambientVol": 400})              # Unsinn wird ignoriert
    assert settings.get("ambient") == "regen" and settings.get("ambientVol") == 60
    settings.update({"ambient": "aus", "ambientVol": 35})


def test_atmosphaere_klaenge_da_und_ausgeliefert(api):
    import paths
    for k in ("regen", "kamin", "cafe", "wald", "rauschen"):
        f = paths.STATIC_DIR / "klang" / f"{k}.m4a"
        assert f.exists() and 200_000 < f.stat().st_size < 2_000_000, k
    s, h, body = api.call("GET", "/klang/regen.m4a")
    assert s == 200 and h["Content-Type"] == "audio/mp4" and len(body) > 200_000
    assert api.call("GET", "/klang/../settings.py")[0] == 404


def test_atmosphaere_im_export(monkeypatch):
    """Stimme = Stille → mit Atmosphäre ist der Export hörbar, ohne bleibt er still; Länge = Stimme."""
    import io, wave, subprocess, paths, tts
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(exporter.RATE); w.writeframes(b"\0\0" * exporter.RATE * 4)
    monkeypatch.setattr(exporter, "chunk_audio", lambda doc, i, stop=None: buf.getvalue())

    def lautstaerke(amb):
        doc = {"id": "a" * 32, "title": "Atmo", "chunks": [{"text": "x"}], "voice": "piper:x", "lang": "de", "chapters": []}
        exporter._jobs[doc["id"]] = {"status": "running"}
        exporter._run(doc, "wav", amb)
        assert exporter._jobs[doc["id"]]["status"] == "ready", exporter._jobs[doc["id"]]
        out = exporter.export_path(doc["id"], "wav")
        r = subprocess.run([tts.FFMPEG, "-i", str(out), "-af", "volumedetect", "-f", "null", "-"], capture_output=True, text=True)
        d = exporter._jobs.pop(doc["id"])["duration"]
        out.unlink()
        return float(r.stderr.split("max_volume:")[1].split("dB")[0]), d
    still, d0 = lautstaerke(None)
    laut, d1 = lautstaerke((paths.STATIC_DIR / "klang" / "regen.m4a", 0.5))
    assert still < -80 and laut > -40 and abs(d0 - d1) < 0.01 and 3.9 < d0 < 4.1


def test_atmosphaere_im_browser(api):
    _, d = api.json("POST", "/api/docs", {"title": "Atmo", "text": "Ein Satz. Noch einer."})

    async def sz(c):
        await _neu_laden(c)
        await c.js(f"openDoc('{d['id']}').then(() => 1)"); await asyncio.sleep(0.5)
        await c.js("$('atmoBtn').click(); 1"); await asyncio.sleep(0.3)
        assert await c.js("!$('atmoMenu').classList.contains('hidden')")
        assert await c.js("$('atmoOpts').children.length") == 6
        await c.js("$('atmoOpts').querySelector('[data-a=\"regen\"]').click(); 1"); await asyncio.sleep(0.3)
        assert await c.js("$('atmoLbl').textContent") == "Regen"
        await c.js("st.wantPlay = true; 1"); await asyncio.sleep(1.5)            # Stimme läuft → Klang blendet ein
        assert await c.js("atmoAu.src.startsWith('blob:') && !atmoAu.paused && atmoAu.volume > 0.25")
        await c.js("st.wantPlay = false; 1"); await asyncio.sleep(2.6)           # Pause → blendet aus
        assert await c.js("atmoAu.volume === 0 && atmoAu.paused")
        await c.js("$('exportBtn').click(); 1"); await asyncio.sleep(0.3)
        assert await c.js("$('xAtmoHint').textContent") == "Aus – nur die Stimme"     # im Export standardmäßig aus
        await c.js("$('xAtmoSw').click(); 1")
        assert await c.js("$('xAtmoHint').textContent") == "Regen, leise unter der Stimme"
        await c.js("$('exportDlg').close(); saveSettings({ ambient: 'aus' }); 1"); await asyncio.sleep(0.2)
    try:
        _im_browser(api, sz)
        assert api.json("GET", "/api/settings")[1]["ambient"] == "aus"
    finally:
        api.call("DELETE", f"/api/docs/{d['id']}")


# --------------------------------------------------------------------------- #
# Texterkennung für Scans (Etappe 2)
# --------------------------------------------------------------------------- #
def _scan_pdf(seiten=2) -> bytes:
    import io
    PIL = pytest.importorskip("PIL")
    from PIL import Image, ImageDraw, ImageFont
    try:
        font = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial.ttf", 34)
    except OSError:
        font = ImageFont.load_default()
    pages = []
    for n in range(seiten):
        im = Image.new("L", (1240, 1754), 255)
        d = ImageDraw.Draw(im)
        for k, line in enumerate([f"Kapitel {n + 1}", "", "Gregor Samsa erwachte eines Morgens aus unruhigen",
                                  "Träumen und fand sich in seinem Bett verwandelt."]):
            d.text((150, 150 + k * 60), line, font=font, fill=0)
        pages.append(im)
    buf = io.BytesIO()
    pages[0].save(buf, "PDF", save_all=True, append_images=pages[1:], resolution=150)
    return buf.getvalue()


def _import(api, name, data):
    import json, urllib.request
    req = urllib.request.Request(api.base + "/api/import", data=data, method="POST",
                                 headers={"X-Filename": name, "X-Vorleser-Token": api.token})
    try:
        with urllib.request.urlopen(req) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


def test_scan_ohne_texterkennung_klare_meldung(api, monkeypatch):
    import ocr
    monkeypatch.setattr(ocr, "verfuegbar", lambda: False)
    s, d = _import(api, "scan.pdf", _scan_pdf(1))
    assert s == 400 and "eingescannt" in d["error"] and "nicht verfügbar" in d["error"]


def test_scan_wird_erkannt(api):
    import time as _t, ocr
    if sys.platform != "darwin" or not ocr.verfuegbar():
        pytest.skip("echte Texterkennung nur am Mac prüfbar (Windows-Runner haben kein OCR-Sprachpaket sicher)")
    s, d = _import(api, "scan.pdf", _scan_pdf(2))
    assert s == 200 and d["ocr"]["status"] == "running"
    for _ in range(300):
        _, j = api.json("GET", f"/api/import/ocr/{d['ocr']['id']}")
        if j["status"] != "running":
            break
        _t.sleep(0.2)
    assert j["status"] == "ready" and j["done"] == j["total"] == 2, j
    r = j["result"]
    assert r["ocr"] and r["lang"] == "de" and r["text"].startswith("# Kapitel 1\n\nGregor Samsa erwachte")
    assert "# Kapitel 2" in r["text"]


def test_texterkennung_abbrechen(monkeypatch):
    import ocr, threading, time as _t
    gate = threading.Event()

    class Lahm:
        n = 5
        def __init__(self, data): pass
        def seite(self, i):
            gate.wait(2); return "x"
    monkeypatch.setattr(ocr, "_Mac", Lahm); monkeypatch.setattr(ocr, "_Win", Lahm)
    job = ocr.start(b"", "a.pdf", lambda s: {"text": "".join(s)})
    ocr.abbrechen(job["id"]); gate.set()
    for _ in range(50):
        if ocr.status(job["id"])["status"] != "running":
            break
        _t.sleep(0.05)
    assert ocr.status(job["id"])["status"] == "cancelled"


def test_texterkennung_im_browser(api, monkeypatch):
    import ocr, threading
    gate = threading.Event()

    class Lahm:
        n = 3
        def __init__(self, data): pass
        def seite(self, i):
            if i == 1:
                gate.wait(10)
            return "Gregor Samsa erwachte eines Morgens aus unruhigen Träumen und fand sich verwandelt."
    monkeypatch.setattr(ocr, "verfuegbar", lambda: True)
    monkeypatch.setattr(ocr, "_Mac", Lahm); monkeypatch.setattr(ocr, "_Win", Lahm)
    pdf = _scan_pdf(3)

    async def sz(c):
        await _neu_laden(c)
        await c.js("showView('new'); 1"); await asyncio.sleep(0.3)
        await c.js(f"window._pdf = new File([Uint8Array.from(atob('{__import__('base64').b64encode(pdf).decode()}'), c => c.charCodeAt(0))], 'scan.pdf'); importFile(window._pdf); 1")
        for _ in range(40):
            if await c.js("$('ocrPages').textContent") == "Seite 1 von 3":
                break
            await asyncio.sleep(0.1)
        assert await c.js("$('ocrPages').textContent") == "Seite 1 von 3"
        assert await c.js("!$('ocrBox').classList.contains('hidden')")
        gate.set()
        for _ in range(40):
            if (await c.js("$('text').value")).startswith("Gregor"):
                break
            await asyncio.sleep(0.1)
        assert (await c.js("$('text').value")).startswith("Gregor Samsa")
        await asyncio.sleep(0.8)
        assert await c.js("$('ocrBox').classList.contains('hidden')")
        await c.js("$('text').value = ''; showView('read'); 1")
    _im_browser(api, sz)


def test_lesezeichen_auch_links_neben_dem_absatz(api):
    _, d = api.json("POST", "/api/docs", {"title": "Rand", "text": "Erster Absatz mit etwas Text.\n\nZweiter Absatz mit etwas Text."})

    async def sz(c):
        await _neu_laden(c)
        await c.js(f"openDoc('{d['id']}').then(() => 1)"); await asyncio.sleep(0.6)
        x, y = await c.js("(() => { const T = $('docText').getBoundingClientRect(), r = st.spans[1].getClientRects()[0]; return [T.left - 140, r.top + r.height / 2]; })()")
        await c.cmd("Input.dispatchMouseEvent", type="mouseMoved", x=x, y=y)
        await asyncio.sleep(0.5)
        assert await c.js("$('bmHover').classList.contains('on') && bmState.hoverI === 1")
    try:
        _im_browser(api, sz)
    finally:
        api.call("DELETE", f"/api/docs/{d['id']}")


def test_lesezeichen_satz_mitten_in_der_zeile(api):
    """Tester-Rückmeldung: beginnt der Satz mitten in der Zeile, sprang das Symbol beim Hinfahren zum Absatzanfang."""
    _, d = api.json("POST", "/api/docs", {"title": "Mitte", "text": " ".join(f"Satz {k} ist ein ganz gewöhnlicher Satz mit genug Wörtern, damit der Absatz lang wird." for k in range(30))})

    async def sz(c):
        await _neu_laden(c)
        await c.js(f"openDoc('{d['id']}').then(() => 1)"); await asyncio.sleep(0.6)
        assert await c.js("st.spans.length") >= 2
        x, y = await c.js("(() => { const r = st.spans[1].getClientRects()[0]; return [r.left + 10, r.top + r.height / 2]; })()")
        await c.cmd("Input.dispatchMouseEvent", type="mouseMoved", x=x, y=y)
        await asyncio.sleep(0.3)
        assert await c.js("bmState.hoverI") == 1
        gx = await c.js("$('docText').getBoundingClientRect().left - 30")
        for k in range(1, 6):                                # nach links zum Symbol fahren, gleiche Höhe
            await c.cmd("Input.dispatchMouseEvent", type="mouseMoved", x=x + (gx - x) * k / 5, y=y)
            await asyncio.sleep(0.05)
        await asyncio.sleep(0.3)
        assert await c.js("bmState.hoverI") == 1
    try:
        _im_browser(api, sz)
    finally:
        api.call("DELETE", f"/api/docs/{d['id']}")


def test_umbrochenes_bindestrich_wort_keine_doppelte_flaeche(api):
    """Tester-Rückmeldung: „cross-section“ brach am Bindestrich um → Satzfläche doppelt, Wort-Box kurz zwei Zeilen groß."""
    text = " ".join(["Die Abbildung zeigt einen cross-section Schnitt und noch mehr Wörter"] * 6) + "."
    _, d = api.json("POST", "/api/docs", {"title": "Strich", "text": text})

    async def sz(c):
        await _neu_laden(c)
        await c.js(f"openDoc('{d['id']}').then(() => 1)"); await asyncio.sleep(0.6)
        await c.js("buildWords(st.idx); 1")
        # Breite so wählen, dass ein „cross-section“ am Bindestrich umbricht
        k = await c.js("""(() => { const r = $('reader'); for (let w = 700; w > 250; w -= 3) { r.style.width = w + 'px';
            const k = st.words.list.findIndex((x) => x.el.firstElementChild.getClientRects().length > 1); if (k >= 0) return k; } return -1; })()""")
        assert k >= 0, "kein umbrochenes Wort gefunden"
        await c.js(f"setWord({k}, false); 1"); await asyncio.sleep(0.4)
        r = await c.js("""(() => { const lh = st.words.list[0].el.firstElementChild.getClientRects()[0].height, b = $('wbox').getBoundingClientRect();
            const boxes = [...$('sboxes').children].map((i) => i.getBoundingClientRect());
            const overlap = boxes.some((a, i) => boxes.some((o, j) => j > i && a.top < o.bottom - 1 && o.top < a.bottom - 1 && a.left < o.right && o.left < a.right));
            return { wbox: b.height < lh * 1.6, overlap }; })()""")
        assert r == {"wbox": True, "overlap": False}, r
        await c.js("$('reader').style.width = ''; 1")
    try:
        _im_browser(api, sz)
    finally:
        api.call("DELETE", f"/api/docs/{d['id']}")


def test_offline_stimme_nur_auf_klick(api):
    """3.0.2: hängt die Online-Stimme, wird der Statustext zum Knopf „zur Offline-Stimme wechseln“ – kein Automatismus."""
    _, d = api.json("POST", "/api/docs", {"title": "Hängt", "text": "Ein Satz zum Vorlesen. Noch ein Satz."})
    import server
    with server._doc_lock:
        doc = server.load_doc(d["id"]); doc["voice"] = "edge:de-DE-KatjaNeural"; server.save_doc(doc)

    async def sz(c):
        await _neu_laden(c)
        await c.js(f"openDoc('{d['id']}').then(() => 1)"); await asyncio.sleep(0.5)
        await c.js("st.wantPlay = true; st.loadedIdx = -1; st.loadSince = Date.now() - 1000; st.waitSince = Date.now() - 7000; statusSt.html = ''; updateStatus(); 1")
        await asyncio.sleep(0.4)
        assert await c.js("!!document.querySelector('#status [data-offline]')")
        await c.js("document.querySelector('#status [data-offline]').click(); 1")
        for _ in range(200):                     # erster Piper-Abschnitt lädt das Modell (CI-Rechner: mehrere Sekunden)
            if await c.js("!!st.cache.get(st.idx)?.used"):
                break
            await asyncio.sleep(0.1)
        assert await c.js("st.offline && st.cache.get(st.idx).used.startsWith('piper:')")
        await c.js("setOffline(false); pause(); 1")
    try:
        _im_browser(api, sz)
    finally:
        api.call("DELETE", f"/api/docs/{d['id']}")


def test_markieren_springt_nicht_und_zeigt_menue(api):
    _, d = api.json("POST", "/api/docs", {"title": "Mark", "text": "Erster Absatz mit etwas Text.\n\nZweiter Absatz mit etwas mehr Text zum Markieren."})

    async def sz(c):
        await _neu_laden(c)
        await c.js(f"openDoc('{d['id']}').then(() => 1)"); await asyncio.sleep(0.6)
        a, b = await c.js("""(() => { const r = st.spans[1].getClientRects()[0]; return [[r.left + 3, r.top + r.height / 2], [r.left + 160, r.top + r.height / 2]]; })()""")
        await c.cmd("Input.dispatchMouseEvent", type="mousePressed", x=a[0], y=a[1], button="left", clickCount=1)
        for k in range(1, 6):
            await c.cmd("Input.dispatchMouseEvent", type="mouseMoved", x=a[0] + (b[0] - a[0]) * k / 5, y=a[1], button="left", buttons=1)
        await c.cmd("Input.dispatchMouseEvent", type="mouseReleased", x=b[0], y=b[1], button="left", clickCount=1)
        await asyncio.sleep(0.4)
        assert await c.js("st.idx") == 0                                   # nicht gesprungen
        assert await c.js("!$('lexMenu').classList.contains('hidden') && !$('lexMenuSay').classList.contains('hidden')")
        assert (await c.js("lexPop.word")).startswith("Zweiter")
        await c.cmd("Input.dispatchMouseEvent", type="mousePressed", x=a[0], y=a[1], button="left", clickCount=1)
        await c.cmd("Input.dispatchMouseEvent", type="mouseReleased", x=a[0], y=a[1], button="left", clickCount=1)
        await asyncio.sleep(0.3)
        assert await c.js("st.idx") == 1 and await c.js("$('lexMenu').classList.contains('hidden')")   # normaler Klick springt weiter
        await c.js("pause(); 1")
    try:
        _im_browser(api, sz)
    finally:
        api.call("DELETE", f"/api/docs/{d['id']}")


def test_rundgang_beispieltext_erst_nach_vorbereiten(api):
    async def sz(c):
        await _neu_laden(c)
        im_lib = "$('library').textContent.includes('Willkommen beim Vorleser')"
        await c.js("gtStart(false); 1"); await asyncio.sleep(1.2)
        assert not await c.js(im_lib)
        await c.js("$('gtNext').click(); 1"); await asyncio.sleep(2.5)                 # Vier Wege
        assert await c.js("view") == "new" and not await c.js(im_lib)
        await c.js("$('gtNext').click(); 1"); await asyncio.sleep(1.2)                 # Vorbereiten
        assert await c.js("$('text').value.startsWith('# Willkommen') && !$('createBtn').disabled")
        assert not await c.js(im_lib)
        await c.js("$('gtNext').click(); 1"); await asyncio.sleep(3)                   # Zeiger klickt → gespeichert, Bibliothek
        assert await c.js("view") == "read" and await c.js(im_lib)
        assert any(d.get("sample") for d in api.json("GET", "/api/docs")[1]["docs"])  # wirklich gespeichert
        assert await c.js("TOUR[gt.i].il") == "lib"
        n = await c.js("TOUR.length")
        for k in range(gt_i := await c.js("gt.i"), n - 1):                            # alle weiteren Schritte ohne Fehler
            await c.js("$('gtNext').click(); 1"); await asyncio.sleep(1.6)
        assert await c.js("gt.i") == n - 1 and not c.errors
        await c.js("gtEnd(); 1"); await asyncio.sleep(1.5)
        assert await c.js("$('text').value") == ""
    try:
        _im_browser(api, sz)
    finally:
        for d in api.json("GET", "/api/docs")[1]["docs"]:
            if d.get("sample"):
                api.call("DELETE", f"/api/docs/{d['id']}")


def test_loeschen_in_einstellungen_bleibt_dort(api):
    _, d = api.json("POST", "/api/docs", {"title": "Weg", "text": "Ein Satz zum Löschen."})

    async def sz(c):
        await _neu_laden(c)
        await c.js(f"openDoc('{d['id']}').then(() => {{ showView('settings'); return 1; }})"); await asyncio.sleep(0.6)
        await c.js(f"window.ask = async () => true; deleteDoc('{d['id']}').then(() => 1)"); await asyncio.sleep(1)
        assert await c.js("view") == "settings" and await c.js("st.doc === null")
        assert await c.js("$('player').classList.contains('hidden') || !$('player').offsetHeight")
    _im_browser(api, sz)


def test_aussprache_gilt_nur_fuer_ihre_sprache(monkeypatch, tmp_path):
    import tts
    monkeypatch.setattr(tts, "LEX_FILE", tmp_path / "aussprache.json")
    tts._lex["mtime"] = None
    assert tts.spoken("z.B. so, e.g. that", None, "de") == "zum Beispiel so, e. g. that"
    assert tts.spoken("z. B. so, e.g. that", None, "en") == "z. B. so, for example that"
    tts.lexikon_speichern([{"wort": "Kafka", "sprich": "Kaffka", "lang": "de"}, {"wort": "GIF", "sprich": "jiff"}])
    assert tts.spoken("Kafka GIF", None, "en") == "Kafka jiff"           # ohne Sprache: gilt überall
    assert tts.spoken("Kafka GIF", None, "de") == "Kaffka jiff"
    assert {e.get("lang") for e in tts.lexikon()} == {"de", None}
    # Sprache kommt aus der Stimme → Schlüssel im Zwischenspeicher passt zur gesprochenen Fassung
    assert tts.cache_path("Kafka", "edge:en-US-AvaMultilingualNeural") != tts.cache_path("Kaffka", "edge:en-US-AvaMultilingualNeural")
    assert tts.cache_path("Kafka", "edge:de-DE-KatjaNeural") == tts.cache_path("Kaffka", "edge:de-DE-KatjaNeural")
    tts._lex["mtime"] = None


def test_bundle_id_wie_im_build():
    """ueberall setzt die Erlaubnis über die App-Kennung zurück – sie muss zur gebauten App passen."""
    import re, ueberall, paths
    spec = (paths.APP_DIR / "packaging" / "vorleser.spec").read_text("utf-8")
    assert re.search(r'bundle_identifier="([^"]+)"', spec).group(1) == ueberall.BUNDLE_ID


def test_export_mit_tempo(monkeypatch):
    """Tester-Rückmeldung: Tempo blieb im Export 1×. Jetzt wählbar (vorausgewählt = Tempo beim Hören); Kapitel passen mit."""
    import io, wave, subprocess, tts
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(exporter.RATE); w.writeframes(b"\0\0" * exporter.RATE * 4)
    monkeypatch.setattr(exporter, "chunk_audio", lambda doc, i, stop=None: buf.getvalue())
    assert exporter._atempo(1.0) == "" and exporter._atempo(6).count("atempo") == 3
    doc = {"id": "b" * 32, "title": "Tempo", "chunks": [{"text": "x"}, {"text": "y"}], "voice": "piper:x", "lang": "de",
           "chapters": [{"title": "A", "chunk": 0}, {"title": "B", "chunk": 1}]}
    exporter._jobs[doc["id"]] = {"status": "running"}
    exporter._run(doc, "m4b", None, 2.0)
    job = exporter._jobs.pop(doc["id"])
    out = exporter.export_path(doc["id"], "m4b")
    try:
        assert job["status"] == "ready", job
        r = subprocess.run([tts.FFMPEG, "-i", str(out)], capture_output=True, text=True).stderr
        dur = r.split("Duration: ")[1].split(",")[0]
        h, m, s = dur.split(":")
        assert 3.9 < float(s) + 60 * int(m) < 4.6 and 3.9 < job["duration"] < 4.6    # 2 × 4 s + Pause → halb so lang
        assert "start 2." in r                                                        # Kapitel B halbiert (bei ~2,x s)
    finally:
        out.unlink(missing_ok=True)


def test_favoriten_stern_reihenfolge_bleibt(api):
    """Tester-Rückmeldung: Stern-Klick sortierte die Liste neu → nächster Klick traf die Nachbar-Stimme."""
    before = api.json("GET", "/api/settings")[1]["favorites"]

    async def sz(c):
        await _neu_laden(c)
        await c.js("""st.voices = st.voices.concat(['Rosa', 'James', 'Aria', 'Ava'].map((n, i) => ({ id: 'edge:en-PH-' + n, name: n, lang: 'en', engine: 'edge', region: 'PH', gender: i % 2 ? 'Male' : 'Female', meta: 'Philippines' })));
            st.settings.favorites = []; openSettingsTab('voices', 'en'); 1"""); await asyncio.sleep(1)
        order0 = await c.js("JSON.stringify([...document.querySelectorAll('#voiceLib [data-fav]')].map((b) => b.dataset.fav))")
        # Stern der zweiten Stimme anklicken, dann der dritten – Reihenfolge darf sich nicht ändern
        for k in (1, 2):
            await c.js(f"document.querySelectorAll('#voiceLib [data-fav]')[{k}].click(); 1"); await asyncio.sleep(0.6)
        order1 = await c.js("JSON.stringify([...document.querySelectorAll('#voiceLib [data-fav]')].map((b) => b.dataset.fav))")
        ons = await c.js("JSON.stringify([...document.querySelectorAll('#voiceLib [data-fav]')].map((b, i) => b.classList.contains('on') ? i : -1).filter((i) => i >= 0))")
        assert order0 == order1 and ons == "[1,2]"
    try:
        _im_browser(api, sz)
    finally:
        api.json("PATCH", "/api/settings", {"favorites": before})      # andere Tests erwarten die Vorgabe


def test_suchen_im_text(api):
    _, d = api.json("POST", "/api/docs", {"title": "Suche", "text": "Der Fuchs läuft. Ein anderer Satz.\n\nWieder ein Fuchs im Wald. Und noch ein FUCHS."})

    async def sz(c):
        await _neu_laden(c)
        await c.js(f"openDoc('{d['id']}').then(() => 1)"); await asyncio.sleep(0.5)
        await c.cmd("Input.dispatchKeyEvent", type="keyDown", key="f", code="KeyF", windowsVirtualKeyCode=70, modifiers=2)
        await asyncio.sleep(0.3)
        assert await c.js("$('findBar').classList.contains('open')")
        await c.js("$('findQ').value = 'fuchs'; findRun(); 1"); await asyncio.sleep(0.2)
        assert await c.js("$('findN').textContent") == "1 / 3"
        await c.js("findStep(1); 1"); assert await c.js("$('findN').textContent") == "2 / 3"
        await c.js("findStep(-1); findStep(-1); 1"); assert await c.js("$('findN').textContent") == "3 / 3"   # rundherum
        if await c.js("hiOK"):
            assert await c.js("CSS.highlights.get('vfind').size") == 3
        await c.js("$('findQ').value = 'zebra'; findRun(); 1"); assert await c.js("$('findN').textContent") == "Keine Treffer"
        await c.js("findOpen(false); 1"); assert await c.js("!$('findBar').classList.contains('open')")
    try:
        _im_browser(api, sz)
    finally:
        api.call("DELETE", f"/api/docs/{d['id']}")


def test_platzhalter_in_textfeldern_werden_uebersetzt(api):
    """Tester-Rückmeldung: „Text hier einfügen …“ und „z. B. Beim Export …“ blieben auf Englisch deutsch (textarea übersprungen)."""
    async def sz(c):
        await c.js("localStorage.setItem('vorleser.ui', 'en'); 1")
        api.json("PATCH", "/api/settings", {"uiLang": "en"})
        try:
            await _neu_laden(c)
            assert (await c.js("$('bugMsg').placeholder")).startswith("e.g. When exporting")
            assert (await c.js("$('text').placeholder")).startswith("Paste text here")
        finally:
            api.json("PATCH", "/api/settings", {"uiLang": "de"}); await c.js("localStorage.setItem('vorleser.ui', 'de'); 1")
    _im_browser(api, sz)


def test_lesezeichen_export_und_diktat_knopf(api):
    _, d = api.json("POST", "/api/docs", {"title": "Notizen", "text": "# Eins\n\nErster Absatz mit Text.\n\nZweiter Absatz mit Text."})
    api.json("POST", f"/api/docs/{d['id']}/bookmarks", {"chunk": 2, "note": "Wichtig!"})

    async def sz(c):
        await _neu_laden(c)
        await c.js(f"openDoc('{d['id']}').then(() => 1)"); await asyncio.sleep(0.5)
        await c.js("bmState.tab = 'bm'; $('chapterBtn').click(); 1"); await asyncio.sleep(0.4)
        assert await c.js("!!$('chapterMenu').querySelector('[data-bmexport]')")
        # Export: Text abfangen statt herunterzuladen
        txt = await c.js("""new Promise((ok) => { const o = URL.createObjectURL; URL.createObjectURL = (b) => { b.text().then(ok); URL.createObjectURL = o; return 'blob:x'; };
            $('chapterMenu').querySelector('[data-bmexport]').click(); })""")
        assert "Notizen" in txt and "Abschnitt 3" in txt and "Notiz: Wichtig!" in txt and "Zweiter Absatz" in txt
    try:
        _im_browser(api, sz)
    finally:
        api.call("DELETE", f"/api/docs/{d['id']}")


def test_kuerzel_aendern(api):
    import settings, ueberall
    assert not settings.valid_hotkey({"code": "KeyV", "shift": True})                 # nur Umschalt → abgelehnt
    assert not settings.valid_hotkey({"code": "Space", "ctrl": True})                 # keine Leertaste
    assert settings.valid_hotkey({"code": "F5", "meta": True})
    assert ueberall.kuerzel_label({"code": "KeyK", "ctrl": True, "alt": False, "shift": True, "meta": True}) in ("⌃⇧⌘K", "Strg+Umschalt+Win+K")

    async def sz(c):
        await _neu_laden(c)
        await c.js("openSettingsTab('app'); $('hkRow').classList.remove('hidden'); hkRender(); 1"); await asyncio.sleep(0.6)
        await c.js("$('hkChange').click(); 1"); await asyncio.sleep(0.1)
        assert "Neue Kombination" in await c.js("$('hkKeys').textContent")
        await c.cmd("Input.dispatchKeyEvent", type="keyDown", key="k", code="KeyK", windowsVirtualKeyCode=75, modifiers=8)   # nur ⇧ → ungültig
        await asyncio.sleep(0.1)
        assert "F-Taste" in await c.js("$('hkKeys').textContent")
        await c.cmd("Input.dispatchKeyEvent", type="keyDown", key="k", code="KeyK", windowsVirtualKeyCode=75, modifiers=3)   # ⌃⌥K
        await asyncio.sleep(0.5)
        assert await c.js("JSON.stringify(st.settings.hotkey)") == '{"code":"KeyK","ctrl":true,"alt":true,"shift":false,"meta":false}'
        assert await c.js("[...$('hkKeys').querySelectorAll('kbd')].map((k) => k.textContent).join('')") in ("⌃⌥K", "StrgAltK")
    try:
        _im_browser(api, sz)
        assert api.json("GET", "/api/settings")[1]["hotkey"]["code"] == "KeyK"
    finally:
        api.json("PATCH", "/api/settings", {"hotkey": {"code": "KeyV", "ctrl": True, "alt": True, "shift": False, "meta": False}})
