"""Eigene Reihenfolge der Bibliothek (3.1): Einstellung, Umschalten, Ziehen, Nach oben/unten, Update-Tutorial."""
import asyncio

import pytest

import settings
from test_frontend import _im_browser


def test_einstellung_reihenfolge_validiert():
    a, b = "a" * 32, "b" * 32
    s = settings.update({"libSort": "own", "libOrder": [a, b, a, "kaputt", 5, "../x"]})
    assert s["libSort"] == "own" and s["libOrder"] == [a, b]          # ohne Doppelte, nur echte Text-IDs
    assert settings.update({"libSort": "quer"})["libSort"] == "own"    # ungültig → bleibt
    s = settings.update({"libSort": "recent"})
    assert s["libOrder"] == [a, b]                                     # Umschalten behält die eigene Reihenfolge
    settings.update({"libOrder": []})


async def _ids(c):
    return await c.js("[...$('library').querySelectorAll('a[data-id]')].map((a) => a.dataset.id)")


async def _ziehen(c, von, nach):
    """Echte Mausbewegung (CDP) von Eintrag `von` auf die Stelle von Eintrag `nach`."""
    r = await c.js(f"""(() => {{ const li = [...$('library').querySelectorAll(':scope > li')];
        const a = li[{von}].getBoundingClientRect(), b = li[{nach}].getBoundingClientRect();
        return {{ x: a.left + 60, y: a.top + a.height / 2, y2: b.top + b.height / 2 }}; }})()""")
    await c.cmd("Input.dispatchMouseEvent", type="mouseMoved", x=r["x"], y=r["y"])
    await c.cmd("Input.dispatchMouseEvent", type="mousePressed", x=r["x"], y=r["y"], button="left", buttons=1, clickCount=1)
    for k in range(1, 13):
        await c.cmd("Input.dispatchMouseEvent", type="mouseMoved", x=r["x"], y=r["y"] + (r["y2"] - r["y"]) * k / 12, button="left", buttons=1)
        await asyncio.sleep(0.03)
    await c.cmd("Input.dispatchMouseEvent", type="mouseReleased", x=r["x"], y=r["y2"], button="left", buttons=0, clickCount=1)
    await asyncio.sleep(0.7)


@pytest.mark.browser
def test_eigene_reihenfolge_ziehen_umschalten_bleibt(api):
    ids = [api.json("POST", "/api/docs", {"title": f"Reihe {n}", "text": f"Text Nummer {n}. Noch ein Satz."})[1]["id"] for n in range(3)]
    neu_zuerst = ids[::-1]                                             # zuletzt angelegt = oben bei „zuletzt gehört“

    async def sz(c):
        await c.js("refreshLibrary().then(() => 1)"); await asyncio.sleep(0.3)
        assert (await _ids(c))[:3] == neu_zuerst

        # Ziehen schaltet von selbst auf die eigene Reihenfolge und speichert sie
        await _ziehen(c, 2, 0)
        eigen = [neu_zuerst[2], neu_zuerst[0], neu_zuerst[1]]
        assert (await _ids(c))[:3] == eigen
        assert await c.js("$('libSortBtn').classList.contains('own')")
        assert await c.js("document.querySelectorAll('#library li[style*=translate]').length") == 0   # nichts bleibt verschoben
        await asyncio.sleep(0.3)
        s = api.json("GET", "/api/settings")[1]
        assert s["libSort"] == "own" and s["libOrder"][:3] == eigen

        # Umschalten → zuletzt gehört; zurück → eigene Reihenfolge ist wieder da
        await c.js("$('libSortBtn').click(); 1"); await asyncio.sleep(0.6)
        assert (await _ids(c))[:3] == neu_zuerst
        await c.js("$('libSortBtn').click(); 1"); await asyncio.sleep(0.6)
        assert (await _ids(c))[:3] == eigen

        # „…“ › Nach unten
        await c.js(f"libMove('{eigen[0]}', 1); 1"); await asyncio.sleep(0.6)
        assert (await _ids(c))[:3] == [eigen[1], eigen[0], eigen[2]]

        # Neuer Text landet in der eigenen Reihenfolge oben
        neu = api.json("POST", "/api/docs", {"title": "Ganz neu", "text": "Neu angelegt."})[1]["id"]
        ids.append(neu)
        await c.js("refreshLibrary().then(() => 1)"); await asyncio.sleep(0.3)
        assert (await _ids(c))[0] == neu
    try:
        _im_browser(api, sz)
    finally:
        for i in ids:
            api.call("DELETE", f"/api/docs/{i}")
        api.json("PATCH", "/api/settings", {"libSort": "recent", "libOrder": []})


@pytest.mark.browser
def test_update_tutorial_fuehrt_vor_ohne_zu_speichern(api):
    ids = [api.json("POST", "/api/docs", {"title": f"Tour {n}", "text": f"Text {n}. Satz."})[1]["id"] for n in range(4)]

    async def sz(c):
        await c.js("refreshLibrary().then(() => 1)"); await asyncio.sleep(0.3)
        vorher = await _ids(c)
        assert await c.js("localStorage.removeItem('vorleser.tourSort'); sortTourDue()") is True
        await c.js("sortTourStart(); 1")
        for schritt in range(3):
            await asyncio.sleep(4.2 if schritt else 3.0)               # Vorführung des Schritts läuft durch
            assert await c.js("!$('gt').classList.contains('hidden')")
            if schritt == 1:                                           # nach dem Ziehen: vierter Eintrag oben
                assert (await _ids(c))[0] == vorher[3]
            await c.js("$('gtNext').click(); 1")
        await asyncio.sleep(1.0)
        assert await c.js("$('gt').classList.contains('hidden') && st.libPreview === null && TOUR === TOUR_ALL")
        assert await _ids(c) == vorher                                 # alles wieder wie vorher
        assert await c.js("sortTourDue()") is False                    # nur einmal
        s = api.json("GET", "/api/settings")[1]
        assert s["libSort"] == "recent" and s["libOrder"] == []        # nichts gespeichert
    try:
        _im_browser(api, sz)
    finally:
        for i in ids:
            api.call("DELETE", f"/api/docs/{i}")
