"use strict";
// Vorleser – Player, Fortschrittsleiste, Bearbeiten, Vorab erzeugen, Export. Teil der Oberfläche; Reihenfolge der Dateien: index.html
/* ===================================================================== */
/* Player-Oberfläche                                                      */
/* ===================================================================== */
/** „current“/„done“ an den Abschnitten: nur zwischen altem und neuem Abschnitt umschalten (lange Bücher: sonst bei
 *  jedem Satzwechsel alle Tausend Abschnitte). Neuer Text (neue span-Liste) → einmal alle. */
function hlClasses() {
  const sp = st.spans, i = st.idx;
  const set = (k) => { sp[k].classList.toggle("current", k === i); sp[k].classList.toggle("done", k < i); };
  if (st.hl?.spans !== sp) { for (let k = 0; k < sp.length; k++) set(k); st.hl = { spans: sp, idx: i }; return; }
  for (let k = Math.max(0, Math.min(st.hl.idx, i)); k <= Math.min(sp.length - 1, Math.max(st.hl.idx, i)); k++) set(k);
  st.hl.idx = i;
}
function highlight(scroll) {
  if (!st.doc) return;
  hlClasses();
  if (markMode() !== "section" && (!st.words || st.words.idx !== st.idx || st.words.doc !== st.doc.id)) buildWords(st.idx);
  if (markMode() === "section") clearWords();
  const W = st.words;                                   // Markierungsart gewechselt → Wort-Box passend zeigen/verstecken
  if (W && st.loadedIdx !== st.idx) {                   // Abschnitt noch nicht geladen (z. B. pausiert gesprungen):
    if (st.pendingFrac != null) setWord(wordAtFrac(W.list, st.pendingFrac), false);   // Wort an der Zielstelle schätzen
    else if (!st.pendingOffset) setWord(0, false);
  }
  if (W) {
    const cur = W.list[W.cur]?.el;
    cur?.classList.toggle("wc", markMode() === "word");
    placeWordBox(markMode() === "word" ? cur : null, false);
    // Satz-Fläche immer mit: sonst sitzt nach einer Verschiebung nur die Wort-Box richtig, der Satz eine Stelle daneben
    if (W.curSent >= 0) placeSentBoxes(W.list.filter((x) => x.sent === W.curSent).map((x) => x.el), false);
  }
  markReady();
  nowSync();
  posRender();
  const cur = st.spans[st.idx];
  if (scroll && cur) cur.scrollIntoView({ block: "center", behavior: "smooth" });
  updateBar();
  if (!scrub.drag) mlSync();
}
/** Seitenleisten-Fuß so hoch wie der Player – die Trennlinien liegen auf einer Höhe. */
// Fußleiste der Seitenleiste = Höhe der Playbar. Wächst die Playbar animiert (Mitlesezeile gleitet herein), meldet der
// ResizeObserver jede Zwischenhöhe → die Fußleiste folgt Bild für Bild ohne eigenen Übergang (sonst hinkt sie hinterher).
// Nur beim Erscheinen der Playbar springt die Höhe auf einmal → dann gleitet sie (Klasse „foot-follow“ fehlt kurz).
let playerShownAt = 0;
function syncPlayerHeight() {
  const p = $("player"), visible = !p.classList.contains("hidden"), b = document.body;
  if (visible && !b.classList.contains("has-player")) playerShownAt = performance.now();
  b.classList.toggle("has-player", visible);
  b.classList.toggle("foot-follow", visible && performance.now() - playerShownAt > 350);
  if (visible) document.documentElement.style.setProperty("--player-h", `${p.offsetHeight}px`);
}
new ResizeObserver(syncPlayerHeight).observe($("player"));
/** Ist Abschnitt i sofort abspielbar? (im Fenster geladen ODER auf dem Server fertig) */
const isReady = (i) => !!st.cache.get(i)?.url || st.srvCached.has(i);
function markReady() {
  const now = new Set();
  if (st.doc) for (let i = 0; i < st.doc.chunks.length; i++) if (isReady(i)) now.add(i);
  for (const i of st.readySet) if (!now.has(i)) st.spans[i]?.classList.remove("ready");
  for (const i of now) st.spans[i]?.classList.add("ready");
  st.readySet = now;
  if (!st.doc) return;
  syncLibPrepared(st.doc.id, now.size);
  const N = st.doc.chunks.length;
  let n = st.idx; while (n < N && isReady(n)) n++;
  $("buf").style.width = `${(n / N) * 100}%`;
  // Weiter hinten schon fertige Abschnitte (nach einer Lücke) als eigene Stücke zeigen – wie die Markierung im Text
  const runs = [];
  for (let i = n; i < N; i++) if (isReady(i)) { const a = i; while (i < N && isReady(i)) i++; runs.push([a, i]); }
  const key = runs.map((r) => r.join("-")).join(","), more = $("bufMore");
  if (more.dataset.k !== key) {
    more.dataset.k = key;
    more.innerHTML = runs.map(([a, b]) => `<div class="buf" style="left:${(a / N) * 100}%;width:${((b - a) / N) * 100}%"></div>`).join("");
  }
  updateStatus();
}
/** Seitenleiste zeigt für den offenen Text denselben „vorbereitet“-Stand wie die Playbar (eine Quelle). */
function syncLibPrepared(id, n) {
  if (vp.doc === id && vp.prep && !$("voicePanel").classList.contains("hidden")) {
    // nur Breite + Text ändern (Element bleibt → Balken gleitet per Transition, statt neu von 0 zu wachsen)
    const el = $("vpBody").querySelector(`[data-vprep="${CSS.escape(st.doc.voice)}"]`);
    const v = st.voices.find((x) => x.id === st.doc.voice), tmp = document.createElement("div");
    tmp.innerHTML = v ? vpPrepHTML(v) : "";
    const nu = tmp.firstElementChild;
    if (el && nu) {
      el.className = nu.className; el.querySelector("em").textContent = nu.querySelector("em").textContent;
      const i = el.querySelector(".vbar i"); i.style.animation = "none"; i.style.width = nu.querySelector(".vbar i").style.width;
    }
  }
  const d = st.docs.find((x) => x.id === id);
  if (!d || d.prepared === n) return;
  const bar = $("library").querySelector(`[data-id="${id}"] .pre`);
  const to = `${d.count ? Math.round(n / d.count * 100) : 0}%`;
  d.prepared = n;
  if (!bar) return;
  const from = bar.style.width; bar.style.width = to;
  if (from && from !== to && bar.animate && !reducedMotion.matches)
    bar.animate([{ width: from }, { width: to }], { duration: 520, easing: EASE });
}
function updateBar() {
  if (!st.doc) return;
  const pct = docPct({ count: st.doc.chunks.length, progress: { chunk: st.idx, frac: curFrac() } });
  if (!scrub.drag) { $("fill").style.width = `${pct}%`; $("knob").style.left = `${pct}%`; }
  $("prog").setAttribute("aria-valuenow", Math.round(pct));
  if (!st.doc.demo && st.doc.progress) {                       // Bibliothek läuft live mit
    st.doc.progress = { ...st.doc.progress, chunk: st.idx, frac: curFrac() };
    if (st.loadedIdx === st.idx || st.doc.progress.updated) libSync();
  }
}
function playState() {
  if (!st.wantPlay) return "idle";
  if (st.loadedIdx !== st.idx || st.buffering || audio.paused) return "loading";
  return "playing";
}
function loadingVisible() {               // „Laden“ erst zeigen, wenn es länger als 250 ms dauert (kein Flackern zwischen Abschnitten)
  if (playState() !== "loading") { st.loadSince = 0; return false; }
  if (!st.loadSince) { st.loadSince = Date.now(); setTimeout(() => { renderPlay(); updateStatus(); }, 260); }
  return Date.now() - st.loadSince >= 250;
}
function renderPlay() {
  const s = playState(), b = $("playBtn"), showLoad = loadingVisible();
  if ((st.playWas ?? "idle") === "idle" && s !== "idle") { b.classList.remove("pulse"); void b.offsetWidth; b.classList.add("pulse"); }   // einmal beim Start
  st.playWas = s;
  b.classList.toggle("is-playing", s === "playing" || (s === "loading" && !showLoad));
  document.body.classList.toggle("is-playing", s === "playing");          // Wellen-Animation der kompakten Ansicht
  b.classList.toggle("is-loading", showLoad);
  const lbl = { idle: "Abspielen", loading: "Lädt … (klicken zum Stoppen)", playing: "Pause" }[s];
  b.setAttribute("aria-label", lbl);
  b.dataset.tip = `${lbl} · Leertaste`;
  if (tipFor === b) tipEl.textContent = b.dataset.tip;
  if ("mediaSession" in navigator) navigator.mediaSession.playbackState = s === "idle" ? "paused" : "playing";
}
const setPlayIcon = () => renderPlay();
function failPlay(msg, retry) {
  st.wantPlay = false; st.switching = false; st.buffering = false;
  st.lastError = { msg, retry };
  renderPlay(); updateStatus();
}
// Status als Toast (3.0.3, Simon): die Zeile unter dem Titel ist weg – sie verwirrte („4 Abschnitte bereit“). Nur was
// zählt, erscheint über dem Player: Vorbereiten/Puffern (mit „Offline-Stimme“), Online-Stimme hängt, Fehler. Bleibt,
// bis es vorbei ist oder ✕ (dann erst wieder bei einem anderen Zustand). Gleicher Inhalt → nichts neu zeichnen.
const stBox = document.createElement("div");
stBox.id = "stToast"; stBox.className = "toast st-toast"; stBox.setAttribute("role", "status"); stBox.setAttribute("aria-live", "polite");
document.body.append(stBox);
const statusSt = { html: "", key: "", closed: "", pending: null, timer: 0, lifeT: 0 };
/** html leer → ausblenden. opts: key (Zustand, für ✕), delay (erst nach so vielen ms zeigen), life (ms, sonst bleibt er). */
function setStatus(html, { key = html, delay = 0, life = 0 } = {}) {
  if (key !== statusSt.key && key !== statusSt.closed) statusSt.closed = "";
  if (key && key === statusSt.closed) html = "";
  if (html === statusSt.html && key === statusSt.key) { clearTimeout(statusSt.timer); statusSt.pending = null; return; }
  if (statusSt.pending === html) return;               // schon unterwegs (Verzögerung läuft) – nicht neu starten
  clearTimeout(statusSt.timer); statusSt.pending = null;
  const apply = () => {
    statusSt.pending = null;
    clearTimeout(statusSt.lifeT);
    statusSt.html = html; statusSt.key = key;
    if (!html) { stBox.classList.remove("show"); document.body.classList.remove("st-on"); return; }
    stBox.innerHTML = `<span class="st-msg">${html}</span><button class="st-x" data-stx aria-label="Hinweis schließen">${icon("i-x", "i", "width:14px;height:14px")}</button>`;
    stBox.classList.add("show"); document.body.classList.add("st-on");
    if (life) statusSt.lifeT = setTimeout(() => { statusSt.closed = key; setStatus("", { key }); }, life);
  };
  if (html && delay && !statusSt.html) { statusSt.pending = html; statusSt.timer = setTimeout(apply, delay); } else apply();
}
/** Player-Zeile (3.0.1): auf der Textseite das aktuelle Kapitel (Titel steht oben), sonst der Titel als Link zum Text. */
function nowSync() {
  if (!st.doc) return;
  const ch = currentChapter(), el = $("nowTitle");
  const t = view === "read" && ch && !document.body.classList.contains("compact") ? ch.title : st.doc.title;   // kompakt: Kopfleiste fehlt
  if (el.textContent === t) return;
  el.textContent = t;
  if (!reducedMotion.matches) { el.classList.remove("swap"); void el.offsetWidth; el.classList.add("swap"); }
}
const canOffline = () => !!st.doc && !st.doc.demo && !st.offline && st.doc.voice.startsWith("edge:");
/** Offline-Stimme ein/aus – nur auf Wunsch (3.0.2). Liest an derselben Stelle weiter. */
function setOffline(on) {
  if (!st.doc) return;
  st.offline = on; st.lastError = null;
  const frac = st.loadedIdx === st.idx && audio.duration ? { frac: audio.currentTime / audio.duration } : 0;
  const play = on || st.wantPlay;
  if (play) audio.pause();
  clearCache();
  if (play) playFrom(st.idx, frac); else updateStatus();
}
stBox.addEventListener("click", (e) => {
  if (e.target.closest("[data-stx]")) { statusSt.closed = statusSt.key; setStatus("", { key: statusSt.key }); }
  else if (e.target.closest("[data-offline]")) setOffline(true);
  else if (e.target.closest("[data-online]")) setOffline(false);
  else if (e.target.closest("[data-bug]")) openBug(st.lastError?.msg || "");
  else if (e.target.closest("[data-retry]")) { const r = st.lastError?.retry; st.lastError = null; r ? r() : play(); }
});
function updateStatus(loading = false) {
  if (!st.doc || st.doc.demo) return setStatus("");
  const offBtn = canOffline() ? ` <button class="tbtn" data-offline>Offline-Stimme</button>` : "";
  if (st.lastError && !st.wantPlay) {
    const bugBtn = typeof bug !== "undefined" && bug.info?.enabled ? ` <button class="tbtn" data-bug>Fehler melden</button>` : "";
    return setStatus(`<span class="status-err">${icon("i-x", "i", "width:14px;height:14px")}<span>${esc(st.lastError.msg)}</span></span> <button class="tbtn" data-retry>Erneut versuchen</button>${offBtn}${bugBtn}`, { key: "err" });
  }
  if (canOffline() && loadingVisible() && st.waitSince && Date.now() - st.waitSince > 6000)
    return setStatus(`<span class="dot busy"></span><span>Online-Stimme hängt</span>${offBtn}`, { key: "hang" });
  if (loadingVisible())
    return setStatus(`<span class="spin"></span><span>${st.doc.voice.startsWith("clone:") ? "Eigene Stimme erzeugt …" : "Bereite vor …"}</span>${offBtn}`, { key: "load", delay: 700 });
  if (st.offline && st.doc.voice.startsWith("edge:"))
    return setStatus(`<span>Offline-Stimme liest</span> <button class="tbtn" data-online>Zur Online-Stimme</button>`, { key: "offline", life: 6000 });
  setStatus("");
}
function updateMediaSession() {
  if (!("mediaSession" in navigator) || !st.doc) return;
  const ch = currentChapter();
  navigator.mediaSession.metadata = new MediaMetadata({ title: ch ? ch.title : st.doc.title, artist: ch ? st.doc.title : `Abschnitt ${st.idx + 1}/${st.doc.chunks.length}`, album: "Vorleser" });
}
if ("mediaSession" in navigator) {
  navigator.mediaSession.setActionHandler("play", play);
  navigator.mediaSession.setActionHandler("pause", pause);
  navigator.mediaSession.setActionHandler("previoustrack", () => jumpTo(st.idx - 1));
  navigator.mediaSession.setActionHandler("nexttrack", () => jumpTo(st.idx + 1));
}

$("playBtn").onclick = toggle;
$("prevBtn").onclick = () => (st.loadedIdx === st.idx && audio.currentTime > 3 ? jumpTo(st.idx, 0) : jumpTo(st.idx - 1));
$("nextBtn").onclick = () => jumpTo(st.idx + 1);
$("backBtn").onclick = () => seekBy(-10);
$("fwdBtn").onclick = () => seekBy(10);
/* ---------- Fortschrittsleiste: Klicken, Ziehen, Vorschau, Einrasten an Kapiteln, Gleiten ---------- */
const scrub = { drag: false, down: null, target: null };
const SNAP_PX = 8;
/** Leiste gleitet beim nächsten Sprung zum neuen Punkt, statt umzuspringen (nicht beim Abspielen/Ziehen). */
function glideBar() {
  if (reducedMotion.matches) return;
  const p = $("prog");
  p.classList.add("glide");
  clearTimeout(scrub.glideT);
  scrub.glideT = setTimeout(() => p.classList.remove("glide"), 420);
}
/** Mausposition → Ziel {p (0–1), i (Abschnitt), frac (Anteil im Abschnitt), tick (eingerastet)} */
function scrubTarget(e) {
  const r = $("prog").getBoundingClientRect(), n = st.doc.chunks.length;
  let p = Math.max(0, Math.min(1, (e.clientX - r.left) / r.width)), tick = null;
  for (const t of $("ticks").children) {                 // in der Nähe eines Kapitelstrichs: dort einrasten
    const tp = parseFloat(t.style.left) / 100;
    if (Math.abs((tp - p) * r.width) <= SNAP_PX) { p = tp; tick = t; break; }
  }
  if (!tick && p * r.width <= SNAP_PX) p = 0;             // ganz links = Anfang
  const x = Math.min(p * n, n - 1e-6), i = Math.floor(x);
  return { p, i, frac: tick || p === 0 ? 0 : x - i, tick };
}
function scrubShow(t, drag) {
  const tip = $("progTip"), ch = (st.doc.chapters || []).filter((c) => c.chunk <= t.i).pop();
  tip.textContent = (ch && st.doc.chapters.length > 1 ? `${ch.title} · ` : "") + `Abschn. ${t.i + 1}`;
  const W = $("prog").offsetWidth, half = tip.offsetWidth / 2;   // Blase nicht über den Rand hinausschieben
  tip.style.left = `${Math.max(half - 40, Math.min(W - half + 40, t.p * W))}px`;
  tip.classList.toggle("on", !(drag && mlOn()));        // beim Ziehen zeigt die Mitlesezeile die Stelle
  $("progGhost").style.left = `${t.p * 100}%`;
  $("prog").classList.toggle("hovering", !drag);
  if (drag) { $("fill").style.width = `${t.p * 100}%`; $("knob").style.left = `${t.p * 100}%`; }
  for (const el of $("ticks").children) el.classList.toggle("near", el === t.tick);
  // Zielabschnitt im Text leicht hinterlegen (nicht den aktuellen: dort liegt die Wort-Markierung)
  const peek = drag && t.i !== st.idx ? st.spans[t.i] : null;
  if (scrub.peek !== peek) { scrub.peek?.classList.remove("peek"); peek?.classList.add("peek"); scrub.peek = peek; }
  const word = drag && markMode() !== "section";
  boxIn($("reader"), "wghost", "wghost", word && view === "read" ? ghostRect(t) : null);
  if (word && mlOn()) { const toks = tokenize(st.doc.chunks[t.i].text); mlShow(t.i, toks, wordAtFrac(toks, t.frac), true); }
}
/** Geschätztes Zielwort beim Ziehen: im aktuellen Abschnitt das Wort-Element, sonst per Range im reinen Text. */
function ghostRect(t) {
  const W = st.words;
  if (W && W.idx === t.i && W.doc === st.doc.id) { const w = W.list[wordAtFrac(W.list, t.frac)]?.el.firstElementChild; return w ? [...w.getClientRects()].find((x) => x.width) : null; }   // umbrochenes Wort: erstes Zeilenstück
  const node = st.spans[t.i]?.firstChild;
  if (!node || node.nodeType !== 3) return null;
  const toks = tokenize(node.data), tk = toks[wordAtFrac(toks, t.frac)];
  if (!tk) return null;
  const r = document.createRange();
  r.setStart(node, tk.at); r.setEnd(node, tk.at + tk.text.length);
  return r.getClientRects()[0] || null;
}
function scrubHide() {
  $("progTip").classList.remove("on");
  $("prog").classList.remove("hovering", "dragging");
  for (const el of $("ticks").children) el.classList.remove("near");
  scrub.peek?.classList.remove("peek"); scrub.peek = null;
  boxIn($("reader"), "wghost", "wghost", null);
  mlSync();                                              // Mitlesezeile zurück auf die echte Stelle
}
$("prog").addEventListener("pointerdown", (e) => {
  if (!st.doc || e.button !== 0) return;
  e.preventDefault();                                     // beim Ziehen keinen Text markieren (und kein Fokusrahmen per Maus)
  document.body.classList.add("scrubbing");
  e.currentTarget.setPointerCapture(e.pointerId);
  scrub.down = { x: e.clientX }; scrub.target = scrubTarget(e);
  scrubShow(scrub.target, false);
});
$("prog").addEventListener("pointermove", (e) => {
  if (!st.doc) return;
  const t = scrubTarget(e);
  if (scrub.down && !scrub.drag && Math.abs(e.clientX - scrub.down.x) > 3) {   // ab 3 px ist es Ziehen statt Klicken
    scrub.drag = true; $("prog").classList.add("dragging"); $("prog").classList.remove("glide");
  }
  if (scrub.down) scrub.target = t;
  scrubShow(t, scrub.drag);
});
$("prog").addEventListener("pointerup", (e) => {
  document.body.classList.remove("scrubbing");
  if (!scrub.down) return;
  const t = scrub.target, dragged = scrub.drag;
  scrub.down = null; scrub.drag = false;
  if (t.tick) { t.tick.classList.remove("hit"); void t.tick.offsetWidth; t.tick.classList.add("hit"); }
  if (!dragged) glideBar();
  jumpTo(t.i, 0, st.wantPlay, t.frac);
  if (e.pointerType !== "mouse") scrubHide(); else { $("prog").classList.remove("dragging"); scrubShow(scrubTarget(e), false); }
});
$("prog").addEventListener("pointercancel", () => { document.body.classList.remove("scrubbing"); scrub.down = null; scrub.drag = false; scrubHide(); updateBar(); });
$("prog").addEventListener("pointerleave", () => { if (!scrub.down) scrubHide(); });
$("prog").onkeydown = (e) => { if (e.key === "ArrowRight") { e.preventDefault(); jumpTo(st.idx + 1); } else if (e.key === "ArrowLeft") { e.preventDefault(); jumpTo(st.idx - 1); } };
$("rate").onchange = () => {
  audio.playbackRate = audio.defaultPlaybackRate = +$("rate").value;
  try { localStorage.setItem("vorleser.rate", $("rate").value); } catch {}
  posRender();                                            // Restzeit hängt am Tempo
};
$("voiceBtn").onclick = (e) => {
  e.stopPropagation();
  if (!$("voicePanel").classList.contains("hidden") && !$("voicePanel").classList.contains("leaving")) return closePops();
  openVoicePanel($("voiceBtn"), { langs: [st.doc.lang], lang: st.doc.lang, current: st.doc.voice, onPick: changeDocVoice, doc: st.doc.demo ? null : st.doc.id });
};
async function changeDocVoice(v) {
  if (!st.doc || v === st.doc.voice) return;
  const wasPlaying = st.wantPlay;
  try { await api(`/api/docs/${st.doc.id}`, { method: "PATCH", body: JSON.stringify({ voice: v }) }); }
  catch (e) { return toastErr(e); }                     // erst speichern, dann stoppen: bei Fehler läuft alles weiter
  stop();
  st.doc.voice = v; st.offline = false; st.pendingOffset = 0; st.pendingFrac = null; st.srvCached = new Set();
  setVoicePill($("voiceAv"), $("voiceLbl"), v);
  updatePrep();
  wasPlaying ? playFrom(st.idx, 0) : (highlight(false), prefetch());
}

/* ---------- Kapitel- & Mehr-Menü ---------- */
$("chapterBtn").onclick = (e) => {
  e.stopPropagation();
  const m = $("chapterMenu");
  if (!m.classList.contains("hidden") && !m.classList.contains("leaving")) return closePops();
  closePops(true);
  const cur = currentChapter();
  m.innerHTML = chapterMenuHtml(cur);
  m.style.setProperty("--origin", "top left");
  openPop(m);
  const r = $("chapterBtn").getBoundingClientRect();
  m.style.left = `${r.left}px`; m.style.top = `${r.bottom + 6}px`;
};
$("chapterMenu").onclick = (e) => {
  const t = e.target.closest("[data-cmtab]");
  if (t) { e.stopPropagation(); bmState.tab = t.dataset.cmtab; const m = $("chapterMenu"), grow = heightFrom(m); m.innerHTML = chapterMenuHtml(currentChapter()); grow(320); return; }
  if (e.target.closest("[data-bmexport]")) { closePops(); return bmExport(); }
  const b = e.target.closest("[data-chunk]"); if (b) { closePops(); jumpTo(+b.dataset.chunk, 0); flashTick(+b.dataset.chunk); }
};
/** Markierung im Fortschrittsbalken leuchtet einmal auf – zeigt, wohin der Sprung ging (Kapitel, Lesezeichen). */
function flashTick(chunk) {
  const t = $("ticks").querySelector(`.tick[data-c="${chunk}"]`); if (t) animateIn(t, "fresh");
}
/** Lesezeichen als Textdatei (Kapitel · Abschnitt, Textauszug, Notiz) – Desktop: „Sichern unter“, Browser: Download. */
async function bmExport() {
  const d = st.doc, en = UI_LANG === "en", chs = d.chapters || [];
  const lines = [d.title, "=".repeat(Math.min(60, d.title.length)), "", en ? `Bookmarks (${bmList().length})` : `Lesezeichen (${bmList().length})`, ""];
  for (const b of [...bmList()].sort((x, y) => x.chunk - y.chunk)) {
    let t = ""; for (const c of chs) if (c.chunk <= b.chunk) t = c.title;
    lines.push(`• ${t ? t + " · " : ""}${en ? "Section" : "Abschnitt"} ${b.chunk + 1}`, `  „${b.text}“`);
    if (b.note) lines.push(`  ${en ? "Note" : "Notiz"}: ${b.note}`);
    lines.push("");
  }
  const text = lines.join("\n"), name = `${d.title} – ${en ? "Bookmarks" : "Lesezeichen"}`;
  if (window.pywebview?.api?.save_text) {
    try { const r = await window.pywebview.api.save_text(name, text); if (r.ok) toast("Gespeichert"); else if (!r.cancelled) toast(r.error || "Speichern fehlgeschlagen", true); }
    catch (err) { toastErr(err); }
    return;
  }
  const a = document.createElement("a");
  a.href = URL.createObjectURL(new Blob([text], { type: "text/plain;charset=utf-8" }));
  a.download = `${name.replace(/[\\/:*?"<>|]+/g, "_")}.txt`; document.body.appendChild(a); a.click(); a.remove();
}
/* Notiz diktieren (Lesezeichen-Popover): Mikro an → nochmal tippen → Whisper → an die Notiz anhängen */
let bmRec = null;
$("bmPopMic").onclick = async (e) => {
  e.stopPropagation();
  const btn = $("bmPopMic");
  if (!bmRec) {
    try { bmRec = startRecorder(await getMic()); } catch { return toast("Mikrofon nicht verfügbar – bitte den Zugriff in den Systemeinstellungen erlauben.", true); }
    btn.classList.add("rec"); btn.setAttribute("aria-label", "Diktat beenden"); return;
  }
  const blob = await bmRec.stop(); bmRec = null; releaseMic();
  btn.classList.remove("rec"); btn.classList.add("busy"); btn.disabled = true;
  try {
    const d = await readJson(await fetch("/api/transcribe", { method: "POST", body: blob, headers: st.doc?.lang ? { "X-Lang": st.doc.lang } : {} }));
    const ta = $("bmPopNote"); ta.value = (ta.value.trim() ? ta.value.trimEnd() + " " : "") + (d.text || "").trim();
  } catch (err) { toastErr(err); }
  btn.classList.remove("busy"); btn.disabled = false; btn.setAttribute("aria-label", "Notiz diktieren");
};
$("moreBtn").onclick = (e) => {
  e.stopPropagation();
  const m = $("moreMenu");
  if (!m.classList.contains("hidden") && !m.classList.contains("leaving")) return closePops();
  // „Vorab erzeugen“ nur im Menü, wenn der Knopf in der Kopfzeile nicht schon sichtbar ist
  $("mPrep").classList.toggle("hidden", !$("prepBtn").classList.contains("hidden"));
  closePops(true); openPop(m);
  const r = $("moreBtn").getBoundingClientRect();
  m.style.left = `${r.right - m.offsetWidth}px`; m.style.top = `${r.bottom + 6}px`;
};
$("mPrep").onclick = async () => {
  closePops();
  try { await api(`/api/docs/${st.doc.id}/prepare`, { method: "POST" }); } catch (e) { return toastErr(e); }
  updatePrep(true); jobsPoll();
};
$("mEdit").onclick = () => { closePops(); openEditor(); };

/* ---------- Text bearbeiten ---------- */
let edit = { id: null, orig: "", origTitle: "" };
async function openEditor() {
  if (!st.doc) return;
  if (st.wantPlay) pause();
  try {
    const d = await api(`/api/docs/${st.doc.id}/text`);
    edit = { id: st.doc.id, orig: d.text, origTitle: d.title };
    $("edTitle").value = d.title; $("edText").value = d.text;
    edRender(d.text);
    $("edOrig").classList.toggle("hidden", !st.doc.hasOriginal);
    showView("edit"); edDirty(); edTools(); requestAnimationFrame(() => segThumbs($("edKind").parentElement));
    // Cursor an die Stelle setzen, an der gerade gelesen wird
    const cur = (st.doc.chunks[st.idx]?.text || "").slice(0, 40);
    requestAnimationFrame(() => {
      const blk = [...$("edDoc").children].find((b) => cur && b.textContent.includes(cur)) || $("edDoc").firstElementChild;
      if (!blk) return;
      $("edDoc").focus({ preventScroll: true });
      const rg = document.createRange(); rg.selectNodeContents(blk); rg.collapse(true);
      const sel = getSelection(); sel.removeAllRanges(); sel.addRange(rg);
      blk.scrollIntoView({ block: "center" });
    });
  } catch (e) { toastErr(e); }
}
function edDirty() {
  const dirty = $("edText").value !== edit.orig || $("edTitle").value !== edit.origTitle;
  $("edState").textContent = dirty ? "Ungespeicherte Änderungen" : "";
  $("edSave").disabled = !dirty || !$("edText").value.trim();
  return dirty;
}
$("edText").oninput = $("edTitle").oninput = edDirty;
/* Editor (Version 3.0): Absätze per Enter, Überschriften per Knopf, Gliederung, Suchen & ersetzen, Original.
   Gespeichert wird wie bisher als Text („# Überschrift“, Leerzeile = neuer Absatz) – Kapitel/Lesezeichen bleiben gleich. */
function edRender(text) {
  const blocks = text.split(/\n{2,}/).map((b) => b.trim()).filter(Boolean);
  $("edDoc").innerHTML = (blocks.length ? blocks : [""]).map((b) => /^#{1,4}\s+/.test(b)
    ? `<h2>${esc(b.replace(/^#{1,4}\s+/, ""))}</h2>` : `<p>${esc(b).replace(/\n/g, "<br>") || "<br>"}</p>`).join("");
  edToc();
}
function edSerialize() {
  const out = [];
  for (const n of $("edDoc").childNodes) {
    const t = (n.nodeType === 3 ? n.textContent : n.innerText || "").replace(/\u00a0/g, " ").trim();
    if (!t) continue;
    out.push(n.nodeName === "H2" ? `# ${t.replace(/\n+/g, " ")}` : t);
  }
  return out.join("\n\n");
}
function edToc() {
  const hs = [...$("edDoc").querySelectorAll("h2")];
  $("edToc").innerHTML = hs.length ? `<b>GLIEDERUNG</b>` + hs.map((h, i) => `<button data-h="${i}">${esc(h.textContent || "…")}</button>`).join("")
    : `<b>GLIEDERUNG</b><span>Noch keine Überschriften – Zeile markieren und „Überschrift“ wählen.</span>`;
}
function edSync() { $("edText").value = edSerialize(); edDirty(); edToc(); edTools(); }
function edBlock() {
  let n = getSelection().anchorNode;
  while (n && n.parentNode !== $("edDoc")) n = n.parentNode;
  return n && n.nodeType === 1 ? n : null;
}
function edTools() {                                      // Umschalter zeigt, was die Zeile mit dem Cursor gerade ist
  const isH = edBlock()?.nodeName === "H2";
  if ($("edH").classList.contains("on") === isH) return;
  $("edH").classList.toggle("on", isH); $("edH").setAttribute("aria-checked", String(isH));
  $("edP").classList.toggle("on", !isH); $("edP").setAttribute("aria-checked", String(!isH));
  segThumbs($("edKind").parentElement);
}
$("edDoc").addEventListener("input", edSync);
$("edDoc").addEventListener("focus", () => document.execCommand("defaultParagraphSeparator", false, "p"));
document.addEventListener("selectionchange", () => { if (view === "edit" && document.activeElement === $("edDoc")) edTools(); });
$("edDoc").addEventListener("paste", (e) => {                 // nur Text einfügen; Leerzeilen → Absätze
  e.preventDefault();
  const t = (e.clipboardData?.getData("text/plain") || "").replace(/\r/g, "");
  const parts = t.split(/\n{2,}/);
  if (parts.length < 2) return document.execCommand("insertText", false, t);
  document.execCommand("insertHTML", false, parts.map((p) => `<p>${esc(p.trim()).replace(/\n/g, "<br>")}</p>`).join(""));
});
const edFmt = (tag) => { $("edDoc").focus(); document.execCommand("formatBlock", false, tag); edSync(); };
$("edH").onclick = () => edFmt("h2");
$("edP").onclick = () => edFmt("p");
for (const b of [$("edH"), $("edP")]) b.addEventListener("mousedown", (e) => e.preventDefault());   // Cursor bleibt im Text
$("edUndo").onclick = () => { $("edDoc").focus(); document.execCommand("undo"); edSync(); };
$("edRedo").onclick = () => { $("edDoc").focus(); document.execCommand("redo"); edSync(); };
$("edToc").onclick = (e) => {
  const b = e.target.closest("[data-h]"); if (!b) return;
  const h = $("edDoc").querySelectorAll("h2")[+b.dataset.h]; if (!h) return;
  h.scrollIntoView({ block: "start", behavior: "smooth" });
  const rg = document.createRange(); rg.selectNodeContents(h); rg.collapse(false);
  const sel = getSelection(); sel.removeAllRanges(); sel.addRange(rg); $("edDoc").focus({ preventScroll: true });
};
$("edFindBtn").onclick = () => {
  const on = !$("edFind").classList.contains("open");
  $("edFind").classList.toggle("open", on); $("edFindBtn").classList.toggle("on", on); $("edFindBtn").setAttribute("aria-pressed", String(on));
  if (on) setTimeout(() => $("edFindQ").focus(), 60);
};
const edEsc = (q) => q.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
$("edFindQ").oninput = () => {
  const q = $("edFindQ").value;
  $("edFindN").textContent = q ? `${(edSerialize().match(new RegExp(edEsc(q), "g")) || []).length} Treffer` : "";
};
$("edFindAll").onclick = () => {
  const q = $("edFindQ").value; if (!q) return;
  edRender(edSerialize().split(q).join($("edFindR").value)); edSync(); $("edFindQ").oninput();
};
$("edOrig").onclick = async () => {
  if (!(await ask({ title: "Original wiederherstellen?", text: "Der Text wird durch das PDF ersetzt, wie es vor dem Aufräumen war – mit Kopfzeilen und Seitenzahlen. Speichern musst du danach noch selbst.", ok: "Wiederherstellen" }))) return;
  try { edRender((await api(`/api/docs/${edit.id}/original`)).text); edSync(); } catch (e) { toastErr(e); }
};
async function saveEdit() {
  if (!edDirty() || !$("edText").value.trim()) return;
  $("edSave").disabled = true; $("edState").textContent = "Speichert …";
  try {
    await api(`/api/docs/${edit.id}/text`, { method: "PUT", body: JSON.stringify({ title: $("edTitle").value, text: $("edText").value }) });
    toast("Gespeichert");
    await refreshLibrary();
    openDoc(edit.id);
  } catch (e) { toastErr(e); edDirty(); }
}
async function leaveEdit() {
  if (edDirty() && !(await askDiscard())) return;
  showView("read");
}
$("edSave").onclick = saveEdit;
$("edCancel").onclick = $("edBack").onclick = leaveEdit;
document.addEventListener("keydown", (e) => {
  if (view !== "edit") return;
  if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "s") { e.preventDefault(); saveEdit(); }
  else if (e.key === "Escape" && !document.querySelector("dialog[open]")) { e.preventDefault(); leaveEdit(); }
});
window.addEventListener("beforeunload", (e) => { if (view === "edit" && edDirty()) { e.preventDefault(); e.returnValue = ""; } });
$("mDelete").onclick = () => { closePops(); deleteDoc(st.doc.id); };
$("nowTitle").onclick = () => { if (st.doc && view !== "read") { showView("read"); highlight(true); } };

/* ---------- Vorab erzeugen (v. a. für die eigene Stimme) ---------- */
let prepTimer = null;
const prepRetry = {};
async function updatePrep(force) {
  clearTimeout(prepTimer);
  if (!st.doc) return;
  if (st.doc.demo) { $("prepBtn").classList.add("hidden"); $("prepX").classList.add("hidden"); return; }
  if (st.doc.id !== $("prepBtn").dataset.doc) { clearTimeout($("prepBtn")._keepT); $("prepBtn")._keepT = 0; $("prepBtn").dataset.doc = st.doc.id; }
  const id = st.doc.id;
  const j = await api(`/api/docs/${id}/prepare`).catch(() => null);
  if (st.doc?.id !== id) return;
  if (!j) {                                              // kurz keine Antwort → weiter fragen, Anzeige nicht einfrieren
    if (force || $("prepBtn").classList.contains("running")) prepTimer = retryLater(prepRetry, () => updatePrep(force));
    return;
  }
  prepRetry.fails = 0;
  st.srvCached = new Set((j.cached || []).flatMap((c, i) => (c ? [i] : [])));
  markReady();
  const isClone = st.doc.voice.startsWith("clone:");
  const running = j.status === "running", all = j.total > 0 && j.done >= j.total;
  const b = $("prepBtn");
  // Gerade fertig geworden: Häkchen springt auf, ein leiser Klang (nur wenn nichts vorgelesen wird), der Knopf bleibt
  // kurz stehen und blendet dann aus – vorher verschwand er im selben Moment (3.0.3).
  const justDone = b.classList.contains("running") && all && !running && !b.classList.contains("hidden");
  if (justDone) {
    clearTimeout(b._keepT); b._keepT = setTimeout(() => { b._keepT = 0; updatePrep(); }, 2600);
    animateIn(b, "celebrate"); if (!st.wantPlay) chime();
  }
  toggleSoft(b, isClone || running || !!b._keepT);
  b.classList.toggle("running", running);
  b.classList.toggle("done", all && !running);
  b.disabled = running || all;                          // läuft → Abbrechen nur über ✕; fertig → nichts mehr zu tun
  $("prepIc").setAttribute("href", all && !running ? "#i-check" : "#i-bolt");
  rollText($("prepLbl"), running ? `Erzeuge ${j.done}/${j.total}` : all ? "Alles vorbereitet" : "Vorab erzeugen");
  b.dataset.tip = running ? "Wird im Hintergrund erzeugt – du kannst weiterhören oder woanders hin. ✕ bricht ab."
    : all ? "Alle Abschnitte sind fertig – alles spielt ohne Wartezeit."
    : "Erzeugt alle Abschnitte schon jetzt im Hintergrund. Danach spielt alles ohne Wartezeit – ideal für deine eigene Stimme, die pro Abschnitt etwas länger braucht.";
  b.setAttribute("aria-disabled", String(running || all));
  toggleSoft($("prepX"), running);
  if (running || force) prepTimer = setTimeout(() => updatePrep(), 2000);
}
$("prepBtn").onclick = async () => {
  const b = $("prepBtn");
  if (b.disabled) return;
  b.disabled = true;                                     // Doppelklick → nur ein Auftrag
  try { await api(`/api/docs/${st.doc.id}/prepare`, { method: "POST" }); }
  catch (e) { b.disabled = false; return toastErr(e); }
  updatePrep(true); jobsPoll();
};
$("prepX").onclick = async () => {
  try { await api(`/api/docs/${st.doc.id}/prepare`, { method: "DELETE" }); } catch (e) { return toastErr(e); }
  setTimeout(() => updatePrep(true), 300);
};

/* ---------- Export im Hintergrund fertig → Karte mit „Speichern“ (Tester-Rückmeldung, Version 3.0) ---------- */
let xDoneDoc = null;
function xDoneShow(docId, title) {
  xDoneDoc = docId;
  $("xDoneTitle").textContent = `„${title}“ ist als Hörbuch fertig`;
  cardPut("xdone", $("xDoneCard"), "aktion");
}
$("xDoneLater").onclick = () => cardDrop("xdone");
$("xDoneSave").onclick = async () => {
  const id = xDoneDoc; if (!id) return;
  if (!window.pywebview) {                                 // Browser: einfach herunterladen
    const a = document.createElement("a"); a.href = `/api/docs/${id}/export/file`; a.download = ""; document.body.appendChild(a); a.click(); a.remove();
    return cardDrop("xdone");
  }
  try {
    const r = await window.pywebview.api.save_export(id);
    if (r.ok) { cardDrop("xdone"); toast("Gespeichert"); }
    else if (!r.cancelled) toast(r.error || "Speichern fehlgeschlagen", true);
  } catch (err) { toastErr(err); }
};

/* ---------- Hintergrund-Aufträge (Vorab erzeugen) – Fortschritt in der Bibliothek, Meldung am Ende ---------- */
const jobs = { list: [], prev: new Map(), t: 0 };
async function jobsPoll() {
  clearTimeout(jobs.t);
  let r; try { r = await api("/api/jobs"); jobs.retry = {}; }
  catch { if (jobs.list.length) jobs.t = retryLater(jobs.retry ||= {}, jobsPoll); return; }
  const cur = new Map(r.jobs.map((j) => [`${j.doc}#${j.kind}`, j]));
  for (const [k, j] of jobs.prev) {
    if (cur.has(k)) continue;
    if (j.kind === "export") {                            // Export fertig → melden (außer der Dialog zeigt es gerade)
      api(`/api/docs/${j.doc}/export`).then((x) => {
        if ($("exportDlg").open && st.doc?.id === j.doc) return;
        if (x.status === "error") return toast(x.error || "Export fehlgeschlagen", true);
        if (x.status !== "ready") return;
        const d = st.docs.find((y) => y.id === j.doc);
        if (!st.wantPlay) chime();                          // fertig-Klang wie bei „Vorab erzeugen“ (3.0.3)
        xDoneShow(j.doc, d?.title || "Text");               // Karte mit „Speichern“ – nicht erst wieder hinsuchen (Tester-Rückmeldung)
      }).catch(() => {});
      continue;
    }
    if (j.kind !== "prepare") continue;                   // beendet → war es vollständig?
    api(`/api/docs/${j.doc}/prepare`).then((p) => {
      if (p.status === "error") { if (st.doc?.id === j.doc) updatePrep(); return toast(p.error || "Vorab erzeugen fehlgeschlagen", true); }
      if (p.status !== "ready") return;
      const d = st.docs.find((x) => x.id === j.doc);
      toast(`„${d?.title || "Text"}“ ist vollständig vorbereitet`);
      refreshLibrary();
      if (st.doc?.id === j.doc) updatePrep();
    }).catch(() => {});
  }
  // Laufende Aufträge erzeugen Audio → „vorbereitet“-Balken der Bibliothek vom Server nachziehen
  const moved = r.jobs.some((j) => jobs.prev.get(`${j.doc}#${j.kind}`)?.done !== j.done) || [...jobs.prev.keys()].some((k) => !cur.has(k));
  jobs.prev = cur; jobs.list = r.jobs;
  if (moved) await refreshLibrary().catch(() => renderLibrary());
  else renderLibrary();
  if (r.jobs.length) jobs.t = setTimeout(jobsPoll, 2000);
}
function jobRing(docId) {
  const j = jobs.list.find((x) => x.doc === docId && x.kind === "prepare") || jobs.list.find((x) => x.doc === docId && x.kind === "export");
  if (!j) return "";
  const c = 2 * Math.PI * 5.5, off = c * (1 - (j.total ? j.done / j.total : 0));
  const lbl = `${j.kind === "export" ? "Wird exportiert" : "Wird vorbereitet"}: ${j.done} von ${j.total}`;
  return `<svg class="jobring" viewBox="0 0 14 14" role="img" aria-label="${lbl}"><title>${lbl}</title>
    <circle class="bg" cx="7" cy="7" r="5.5"/><circle class="fg" cx="7" cy="7" r="5.5" stroke-dasharray="${c.toFixed(2)}" stroke-dashoffset="${off.toFixed(2)}"/></svg>`;
}
jobsPoll();

/* ---------- Export ---------- */
// Drei Stufen: Auswählen → Läuft → Fertig. JEDE Änderung, die die Höhe des Dialogs ändern kann, läuft über
// xChange(): Höhe vorher messen, ändern, dann gleitet der Dialog zur neuen Höhe (kein Sprung).
let xTimer = null, xPrev = null, xView = null;   // xPrev: letzter Status (null = gerade geöffnet → nichts animieren)
const X_VIEWS = { pick: "xPick", run: "xRun", done: "xDone" };
function xChange(fn, animate = true) {
  const dlg = $("exportDlg");
  if (!animate || !dlg.open) return fn();
  const done = heightFrom(dlg); fn(); done(480);
}
function xSetView(v, animate) {
  if (v === xView) return;
  xChange(() => {
    for (const [k, id] of Object.entries(X_VIEWS)) $(id).classList.toggle("hidden", k !== v);
    $("xChip").classList.toggle("hidden", v === "pick");
    $("xDone").classList.toggle("xplay", v === "done" && animate);   // Fertig-Animationen nur beim echten Übergang
  }, animate);
  xView = v;
  if (!animate) return;
  animateIn($(X_VIEWS[v]), "rise");
  if (v !== "pick") animateIn($("xChip"), "popin");
}
function xMsg(text) {
  if ($("xMsg").textContent === text) return;
  xChange(() => { $("xMsg").textContent = text; $("xMsg").classList.toggle("hidden", !text); });
}
let xInfoSrv = null;   // vom Server: { prepared, total, seconds } – seconds = echte Länge, wenn alles vorbereitet ist
function xDocInfo() {
  const d = st.doc, rate = +$("xRate").value || 1, real = xInfoSrv?.seconds;
  const chars = d.chunks.reduce((s, c) => s + c.text.length, 0), sec = (real || chars / 15) / rate;   // mit Export-Tempo
  $("xInfo").textContent = [d.title, real ? fmtDuration(sec) : `ca. ${fmtDuration(sec)}`, d.chapters.length ? `${d.chapters.length} Kapitel` : ""].filter(Boolean).join(" · ");
  // Größe = Länge × Bytes je Sekunde des Formats (vom Server, passend zum dort genutzten Encoder) – mit echter Länge genau
  const bps = { m4b: 8550, mp3: 8000, wav: 48000, ...(xInfoSrv?.bytesPerSec || {}) };
  const est = { m4b: sec * bps.m4b, mp3: sec * bps.mp3, wav: sec * bps.wav };
  document.querySelectorAll("#xFmts [data-sz]").forEach((el) => {
    el.innerHTML = real ? `${esc(fmtMB(est[el.dataset.sz]))}<em>in Sekunden</em>` : esc(`≈ ${fmtMB(est[el.dataset.sz])}`);
  });
  const p = xInfoSrv, alle = p && p.total && p.prepared === p.total, teil = p && p.prepared > 0 && !alle;
  $("xPrep").classList.toggle("hidden", !alle && !teil);
  $("xPrep").classList.toggle("part", !!teil);
  $("xPrepTxt").textContent = alle ? "Vorbereitet – alle Abschnitte sind schon erzeugt. Jedes Format ist in Sekunden fertig."
    : teil ? `Teilweise vorbereitet – ${p.total - p.prepared} von ${p.total} Abschnitten werden beim Export noch erzeugt.` : "";
  // Fortschritt in Kapitel geteilt (bei sehr vielen Kapiteln ein durchgehender Balken)
  const n = d.chunks.length, starts = d.chapters.map((c) => c.chunk).filter((c) => c > 0);
  const bounds = starts.length && starts.length < 30 ? [0, ...starts, n] : [0, n];
  xDocInfo.bounds = bounds;
  $("xSegs").innerHTML = bounds.slice(0, -1).map((s0, k) => `<span class="xseg" style="flex:${Math.max(1, bounds[k + 1] - s0)}"><i></i></span>`).join("");
}
function xRunRender(j) {
  const coding = j.phase === "Kodieren", d = st.doc, done = coding ? j.total : j.done;
  const pct = coding ? 100 : j.total ? (j.done / j.total) * 100 : 0;
  $("xPhase").textContent = coding ? "Datei wird erstellt …" : j.phase === "Zusammensetzen" ? "Wird zusammengesetzt …" : "Wird vertont …";
  $("xPct").textContent = `${Math.floor(pct)} %`;
  const b = xDocInfo.bounds || [0, j.total];
  $("xSegs").querySelectorAll("i").forEach((el, k) => {
    const len = b[k + 1] - b[k]; el.style.width = `${Math.max(0, Math.min(1, (done - b[k]) / (len || 1))) * 100}%`;
  });
  const chs = d.chapters, ci = chs.reduce((acc, c, k) => (c.chunk <= j.done ? k : acc), -1);
  $("xChap").textContent = coding ? "Kapitelmarken werden gesetzt" : ci >= 0 && chs.length > 1 ? `Kapitel ${ci + 1} von ${chs.length} · ${chs[ci].title}` : `${j.done} von ${j.total} Abschnitten`;
  const elapsed = j.started ? Date.now() / 1000 - j.started : 0;
  $("xLeft").textContent = coding ? "gleich fertig" : fmtEta(j.done > 0 && elapsed > 3 ? (elapsed / j.done) * (j.total - j.done) : null);
}
const xRetry = {};
async function exportPoll() {
  clearTimeout(xTimer);
  if (!st.doc || !$("exportDlg").open) return;
  let j;
  try { j = await api(`/api/docs/${st.doc.id}/export`); xRetry.fails = 0; }
  catch { xTimer = retryLater(xRetry, exportPoll); return; }   // Dialog nicht bei „43 %“ einfrieren
  if (!$("exportDlg").open) return;
  const animate = xPrev !== null && xPrev !== j.status; xPrev = j.status;
  if (j.format) $("xChip").textContent = j.format.toUpperCase();
  if (j.status === "running") {
    xMsg("");
    if (xView === "run") xChange(() => xRunRender(j)); else xRunRender(j);   // längere Zeile → Höhe gleitet mit
    xSetView("run", animate);
    xTimer = setTimeout(exportPoll, 1000);
  } else if (j.status === "ready") {
    $("xFile").textContent = `${st.doc.title}.${j.format}`;
    $("xFileMeta").textContent = [fmtMB(j.size), j.duration ? fmtDuration(j.duration) : "",
      j.format !== "wav" && st.doc.chapters.length ? `${st.doc.chapters.length} Kapitel` : ""].filter(Boolean).join(" · ");
    $("xDownload").href = `/api/docs/${st.doc.id}/export/file`;
    $("xDownload").onclick = window.pywebview ? async (e) => {   // Desktop-App: „Sichern unter …“
      e.preventDefault();
      try {
        const r = await window.pywebview.api.save_export(st.doc.id);
        // Dialog zu, sonst verdeckt er den Hinweis (modale Dialoge liegen über allem, auch über dem Toast)
        if (r.ok) { $("exportDlg").close(); toast("Gespeichert"); }
        else if (!r.cancelled) toast(r.error || "Speichern fehlgeschlagen", true);
      } catch (err) { toastErr(err); }
    } : null;
    if (animate && xView === "run" && !st.wantPlay) chime();   // Export fertig, während der Dialog offen ist (3.0.3)
    xSetView("done", animate);
  } else {
    xSetView("pick", animate);
    xMsg(j.status === "error" ? j.error || "Export fehlgeschlagen" : j.status === "cancelled" ? "Abgebrochen" : "");
  }
}
$("exportBtn").onclick = async () => {
  // Vorbereitet? Echte Länge? Vor dem Öffnen holen (lokal, schnell) – so steht der Dialog gleich richtig da, nichts springt
  const id = st.doc?.id;
  try { xInfoSrv = id ? await api(`/api/docs/${id}/export/info`) : null; } catch { xInfoSrv = null; }
  if (!st.doc || st.doc.id !== id) return;
  xDocInfo(); atmoExport = false; atmoExportRender();
  $("xRate").innerHTML = $("rate").innerHTML; $("xRate").value = $("rate").value; xDocInfo();   // vorausgewählt: Tempo beim Hören
  xPrev = null; xView = null;
  $("xMsg").textContent = ""; $("xMsg").classList.add("hidden");
  $("exportDlg").showModal(); exportPoll();
};
$("xRate").onchange = xDocInfo;                         // Dauer + Größe passen sich dem Tempo an
$("xStart").onclick = async () => {
  const fmt = $("xFmts").querySelector("input:checked").value;
  $("xStart").disabled = true;
  try {
    await api(`/api/docs/${st.doc.id}/export`, { method: "POST", body: JSON.stringify({ format: fmt, ambient: atmoExport && atmoKey() !== "aus", rate: +$("xRate").value }) });
    xPrev = xPrev ?? "none";      // Übergang Auswählen → Läuft animieren
    await exportPoll();
    jobsPoll();                   // Bibliothek zeigt den Fortschritt, Hinweis beim Fertigwerden
  } catch (err) { xMsg(`Fehler: ${err.message}`); }
  $("xStart").disabled = false;
};
$("xCancel").onclick = async () => {
  try { await api(`/api/docs/${st.doc.id}/export`, { method: "DELETE" }); } catch (e) { return xMsg(friendlyError(e)); }   // im Dialog sichtbar
  setTimeout(exportPoll, 300);
};
$("xOther").onclick = () => { xMsg(""); xSetView("pick", true); };
$("xClose").onclick = $("xBg").onclick = $("xDoneBtn").onclick = () => $("exportDlg").close();

/* ---------- Tastatur ---------- */
document.addEventListener("keydown", (e) => {
  if (view !== "read" || !st.doc || document.querySelector("dialog[open]") || !$("onb").classList.contains("hidden") || !$("gt").classList.contains("hidden") || /INPUT|TEXTAREA|SELECT/.test(e.target.tagName)) return;
  if (e.code === "Space" && e.target.tagName !== "BUTTON") { e.preventDefault(); toggle(); }
  else if (e.key === "ArrowRight" && e.target.id !== "prog") { e.preventDefault(); e.shiftKey ? seekBy(10) : jumpTo(st.idx + 1); }
  else if (e.key === "ArrowLeft" && e.target.id !== "prog") { e.preventDefault(); e.shiftKey ? seekBy(-10) : jumpTo(st.idx - 1); }
  else if (e.key.toLowerCase() === "e" && !e.metaKey && !e.ctrlKey) { e.preventDefault(); openEditor(); }
});


/* ===================================================================== */
/* Schlaf-Timer (Version 3.0, Etappe 3): merkt sich die letzte Wahl, Satz zu Ende + 10 s ausblenden          */
/* ===================================================================== */
const schlaf = { mode: null, left: 0, t: 0, fading: false, armed: false, armSent: null, armIdx: null };
const SLEEP_OPTS = [[null, "Aus"], [15, "15 Minuten"], [30, "30 Minuten"], [45, "45 Minuten"], [60, "60 Minuten"], ["chapter", "Ende des Kapitels"]];
function sleepLast() { try { return JSON.parse(localStorage.getItem("vorleser.sleep") || "null"); } catch { return null; } }
function sleepSet(mode) {
  clearInterval(schlaf.t);
  Object.assign(schlaf, { mode: mode ?? null, fading: false, armed: false, armSent: null, armIdx: null, left: typeof mode === "number" ? mode * 60 : 0 });
  if (mode != null) { try { localStorage.setItem("vorleser.sleep", JSON.stringify(mode)); } catch {} schlaf.t = setInterval(sleepTick, 1000); }
  sleepRender();
}
function sleepTick() {
  if (typeof schlaf.mode === "number" && st.wantPlay && !schlaf.armed) {   // Pause hält den Countdown an
    schlaf.left = Math.max(0, schlaf.left - 1);
    if (!schlaf.left) schlaf.armed = true;
  }
  sleepRender();
}
function sleepRender() {
  const on = schlaf.mode != null, b = $("sleepBtn");
  b.classList.toggle("on", on);
  $("sleepLbl").textContent = !on ? "" : schlaf.mode === "chapter" ? "Kapitelende" : schlaf.armed ? "gleich" : mmss(schlaf.left);
  b.dataset.tip = on ? "Schlaf-Timer ändern" : "Schlaf-Timer";
}
function sleepFade() {
  if (schlaf.fading) return;
  schlaf.fading = true;
  const v0 = audio.volume, t0 = performance.now();
  const step = () => {
    if (!schlaf.fading) { audio.volume = v0; return; }               // abgebrochen (Timer aus)
    const k = Math.min(1, (performance.now() - t0) / 10000);
    audio.volume = v0 * (1 - k);
    if (k < 1 && st.wantPlay) return requestAnimationFrame(step);
    if (st.wantPlay) pause();                                        // speichert die Stelle, an der wirklich Schluss war
    audio.volume = v0; sleepSet(null); toast("Schlaf-Timer: gute Nacht");
  };
  requestAnimationFrame(step);
}
audio.addEventListener("timeupdate", () => {
  if (schlaf.mode == null || schlaf.fading || !st.doc) return;
  if (schlaf.armed) {                                                  // Zeit um → Satz zu Ende, dann ausblenden
    const s = st.words?.curSent ?? -1;
    if (schlaf.armSent === null) { schlaf.armSent = s; schlaf.armIdx = st.idx; }
    else if (s !== schlaf.armSent || st.idx !== schlaf.armIdx) sleepFade();
  }
  if (schlaf.mode === "chapter") {                                     // 10 s vor dem Kapitelende ausblenden
    const next = (st.doc.chapters || []).find((c) => c.chunk > st.idx);
    const last = next ? next.chunk - 1 : st.doc.chunks.length - 1;
    if (st.idx === last && audio.duration && audio.duration - audio.currentTime <= 10) sleepFade();
  }
});
function sleepMenu(open) {
  const m = $("sleepMenu");
  if (!open) return softHide(m);
  const cur = schlaf.mode, last = sleepLast();
  $("sleepOpts").innerHTML = SLEEP_OPTS.map(([v, l], i) => `<button role="menuitemradio" aria-checked="${v === cur}" data-i="${i}" class="${v === cur ? "on" : ""}">${l}${v != null && v === last && v !== cur ? '<small>zuletzt</small>' : ""}</button>`).join("");
  m.classList.remove("hidden");
  popAtBtn(m, $("sleepBtn"));
  animateIn(m, "enter");
}
$("sleepBtn").onclick = (e) => {
  e.stopPropagation();
  const last = sleepLast();
  if (schlaf.mode == null && last != null) { sleepSet(last); return toast(last === "chapter" ? "Schlaf-Timer: bis zum Ende des Kapitels" : `Schlaf-Timer: ${last} Minuten`); }
  sleepMenu(!isShown($("sleepMenu")));
};
$("sleepOpts").onclick = (e) => {
  const b = e.target.closest("[data-i]"); if (!b) return;
  sleepSet(SLEEP_OPTS[+b.dataset.i][0]); sleepMenu(false);
};
document.addEventListener("pointerdown", (e) => { if (!e.target.closest("#sleepMenu, #sleepBtn")) sleepMenu(false); }, true);

/* ===================================================================== */
/* Atmosphäre (Version 3.0): Klang-Schleife leise unter der Stimme, blendet mit Abspielen/Pause weich ein und aus.
   Klänge: static/klang/*.m4a (CC0, BigSoundBank; Rauschen selbst erzeugt). Wahl + Lautstärke = Einstellungen. */
/* ===================================================================== */
const ATMO = [["aus", "Aus"], ["regen", "Regen"], ["kamin", "Kaminfeuer"], ["cafe", "Café"], ["wald", "Wald"], ["rauschen", "Rauschen"]];
const atmoAu = new Audio(); atmoAu.loop = true; atmoAu.preload = "none"; atmoAu.volume = 0;
let atmoExport = false;
const atmoKey = () => st.settings?.ambient || "aus";
const atmoBlobs = {}; let atmoCur = null;
async function atmoLoad(k) {                             // als Blob: WebKit spielt so ohne Range-Anfragen
  if (!atmoBlobs[k]) atmoBlobs[k] = fetch(`/klang/${k}.m4a`).then((r) => (r.ok ? r.blob() : null)).then((b) => b && URL.createObjectURL(b)).catch(() => null);
  return atmoBlobs[k];
}
const atmoVolume = () => (st.settings?.ambientVol ?? 35) / 100;
function atmoTick() {                                    // weich zum Ziel: Stimme läuft → Klang an, sonst aus
  const k = atmoKey(), want = k !== "aus" && st.wantPlay && view === "read";
  if (want && atmoCur !== k) {                           // anderer Klang: alten ausblenden lassen, neuen laden
    if (atmoAu.volume > 0.004) { atmoStep(0); return; }
    atmoCur = k; atmoAu.pause();
    atmoLoad(k).then((u) => { if (u && atmoCur === k) atmoAu.src = u; });
    return;
  }
  const fade = schlaf.fading ? audio.volume : 1;          // Schlaf-Timer blendet beides gemeinsam aus
  atmoStep(want && atmoAu.src ? atmoVolume() * fade : 0);
}
function atmoStep(target) {
  const v = atmoAu.volume + (target - atmoAu.volume) * 0.18;
  atmoAu.volume = Math.abs(v - target) < 0.004 ? target : Math.max(0, Math.min(1, v));
  if (target > 0 && atmoAu.paused) atmoAu.play().catch(() => {});
  if (!target && !atmoAu.volume && !atmoAu.paused) atmoAu.pause();
}
// Nur beim Ein-/Ausblenden und Abspielen fein takten; in Ruhe 1×/s (12,5 Weckrufe/s kosteten Akku, 3.0.2).
// Startet die Stimme, sofort wecken – sonst käme der Klang bis zu 1 s zu spät.
let atmoT = 0;
function atmoLoop() {
  atmoTick();
  const ruhig = atmoAu.paused && !atmoAu.volume && !(atmoKey() !== "aus" && st.wantPlay && view === "read");
  atmoT = setTimeout(atmoLoop, ruhig ? 1000 : 80);
}
function atmoWake() { clearTimeout(atmoT); atmoT = setTimeout(atmoLoop, 0); }
audio.addEventListener("play", atmoWake);
atmoWake();
function atmoRender() {
  atmoWake();                                            // Klang gewechselt → sofort ein-/ausblenden
  const k = atmoKey(), on = k !== "aus";
  $("atmoBtn").classList.toggle("on", on);
  $("atmoLbl").textContent = on ? ATMO.find((a) => a[0] === k)[1] : "";
  $("atmoOpts").innerHTML = ATMO.map(([v, l]) => `<button class="chip${v === k ? " on" : ""}" data-a="${v}" aria-pressed="${v === k}">${l}</button>`).join("");
  $("atmoVol").value = Math.round(atmoVolume() * 100);
  $("atmoSel").innerHTML = ATMO.map(([v, l]) => `<option value="${v}"${v === k ? " selected" : ""}>${l}</option>`).join("");
  atmoExportRender();
}
function atmoExportRender() {
  const k = atmoKey(), off = k === "aus";
  $("xAtmoSw").classList.toggle("on", atmoExport && !off); $("xAtmoSw").setAttribute("aria-checked", String(atmoExport && !off));
  $("xAtmoSw").disabled = off;
  if (off) $("xAtmoHint").innerHTML = `Erst im Player über <svg class="i ico-inl" aria-hidden="true"><use href="#i-wave"/></svg> einen Klang wählen`;
  else $("xAtmoHint").textContent = atmoExport ? `${ATMO.find((a) => a[0] === k)[1]}, leise unter der Stimme` : "Aus – nur die Stimme";
}
/** Menü mittig über dem Knopf – passt es oben nicht hin (kompakte Ansicht: Knöpfe oben rechts), darunter. */
function popAtBtn(m, btn) {
  const r = btn.getBoundingClientRect(), h = m.offsetHeight, above = r.top - h - 10 >= 8;
  m.style.left = `${Math.max(8, Math.min(innerWidth - m.offsetWidth - 8, r.left + r.width / 2 - m.offsetWidth / 2))}px`;
  m.style.top = `${above ? r.top - h - 10 : r.bottom + 10}px`;
}
function atmoMenu(open) {
  const m = $("atmoMenu");
  if (!open) return softHide(m);
  atmoRender(); m.classList.remove("hidden");
  popAtBtn(m, $("atmoBtn"));
  animateIn(m, "enter");
}
$("atmoBtn").onclick = (e) => { e.stopPropagation(); atmoMenu(!isShown($("atmoMenu"))); };
$("atmoOpts").onclick = (e) => {
  const b = e.target.closest("[data-a]"); if (!b) return;
  saveSettings({ ambient: b.dataset.a }); atmoRender();
};
$("atmoVol").oninput = () => { st.settings.ambientVol = +$("atmoVol").value; };          // sofort hörbar …
$("atmoVol").onchange = () => saveSettings({ ambientVol: +$("atmoVol").value });          // … gespeichert beim Loslassen
$("atmoSel").onchange = () => { saveSettings({ ambient: $("atmoSel").value }); atmoRender(); };
$("xAtmoSw").onclick = () => { atmoExport = !atmoExport; atmoExportRender(); };
document.addEventListener("pointerdown", (e) => { if (!e.target.closest("#atmoMenu, #atmoBtn")) atmoMenu(false); }, true);

/* ===================================================================== */
/* Lesezeichen (Version 3.0, Etappe 3): Symbol links beim Darüberfahren, Klick = gefüllt, Abspielen läuft weiter */
/* ===================================================================== */
const bmState = { tab: "kap", hoverI: -1, popId: null };
const bmList = () => st.doc?.bookmarks || [];
function chapterMenuHtml(cur) {
  const bms = bmList(), chs = st.doc.chapters || [];
  const en = UI_LANG === "en";                             // Menü ist „nicht übersetzen“ (Kapitelnamen) → Reiter selbst übersetzen
  const tabs = bms.length ? `<div class="cm-tabs"><button data-cmtab="kap" class="${bmState.tab === "kap" ? "on" : ""}" ${chs.length ? "" : "disabled"}>${en ? "Chapters" : "Kapitel"}</button>
    <button data-cmtab="bm" class="${bmState.tab === "bm" || !chs.length ? "on" : ""}">${en ? "Bookmarks" : "Lesezeichen"} · ${bms.length}</button></div>` : "";
  if (bms.length && (bmState.tab === "bm" || !chs.length)) {
    const where = (i) => { let t = ""; for (const c of chs) if (c.chunk <= i) t = c.title; return `${t ? esc(t) + " · " : ""}${en ? "Section" : "Abschnitt"} ${i + 1}`; };
    return tabs + bms.map((b) => `<button data-chunk="${b.chunk}" class="cm-bm"><span class="w"><svg class="i"><use href="#i-bm"/></svg>${where(b.chunk)}</span>
      <span class="t">„${esc(b.text.slice(0, 90))}${b.text.length > 90 ? " …" : ""}“</span>${b.note ? `<span class="n">${esc(b.note)}</span>` : ""}</button>`).join("")
      + `<button class="cm-export" data-bmexport><svg class="i"><use href="#i-export"/></svg>${en ? "Export as text file" : "Als Textdatei exportieren"}</button>`;
  }
  return tabs + chs.map((c, n) => `<button data-chunk="${c.chunk}" class="${c === cur ? "on" : ""}">${n + 1}. ${esc(c.title)}</button>`).join("");
}
function bmLayer() {
  let l = $("bmLayer");
  if (!l || !l.isConnected) { l = document.createElement("div"); l.id = "bmLayer"; l.className = "bm-layer"; $("reader").appendChild(l); }
  return l;
}
function bmPos(i) {
  const el = st.spans[i], R = $("reader").getBoundingClientRect(), r = el?.getClientRects()[0];
  if (!r || !R.width) return null;
  return { x: $("docText").getBoundingClientRect().left - R.left - 44, y: r.top - R.top + r.height / 2 - 15 };
}
function bmRender(fresh) {
  const l = bmLayer();
  if (!st.doc) { l.innerHTML = ""; return; }
  l.innerHTML = bmList().map((b) => `<button class="bm-mark${b.id === fresh ? " enter" : ""}" data-bm="${b.id}" aria-label="Lesezeichen bearbeiten"><svg class="i"><use href="#i-bm"/></svg></button>`).join("")
    + (st.doc.demo ? "" : `<button class="bm-hover" id="bmHover" aria-label="Lesezeichen setzen"><svg class="i"><use href="#i-bm"/></svg></button>`);   // Rundgang: nur zeigen
  bmPlace();
  $("ticks").querySelectorAll(".tick.bm").forEach((t) => t.remove());
  const n = st.doc.chunks.length;
  $("ticks").insertAdjacentHTML("beforeend", bmList().map((b) => `<span class="tick bm${b.id === fresh ? " fresh" : ""}" data-c="${b.chunk}" style="left:${(b.chunk / n) * 100}%"></span>`).join(""));
  $("chapterBtn").classList.toggle("hidden", !st.doc.chapters.length && !bmList().length);
}
function bmPlace() {
  for (const m of $("bmLayer")?.querySelectorAll(".bm-mark") || []) {
    const b = bmList().find((x) => x.id === m.dataset.bm), p = b && bmPos(b.chunk);
    if (p) m.style.translate = `${p.x}px ${p.y}px`;
  }
}
new ResizeObserver(() => bmPlace()).observe($("reader"));
// Auch links neben dem Absatz (dort sitzt das Symbol) – nicht nur über dem Text selbst
function bmChunkAt(e) {
  // Vom Satz nach links zum Symbol: beginnt er mitten in der Zeile, fährt die Maus über den vorigen Satz bzw. landet am
  // Zeilenanfang bei ihm → solange sie auf einer Zeile des gezeigten Satzes nach links fährt (oder schon im Rand ist),
  // diesen behalten (Tester-Rückmeldung 3.0.1). Nach rechts/oben/unten wechselt das Symbol wie gewohnt.
  // Geprüft wird die ganze Höhe des Satzes (erste bis letzte Zeile): die Lücken zwischen den Zeilen gehören dazu –
  // sonst ging der Satz dort verloren und das Symbol sprang zum vorigen Satz (Tester-Rückmeldung 3.0.2).
  // Richtung selbst aus der letzten Position: `movementX` ist in WebKit nicht verlässlich, und ein kurzes Zittern nach
  // rechts (Trackpad) darf den Satz nicht abgeben → erst ab 4 px nach rechts gilt die Bewegung als „nach rechts“.
  const T = $("docText").getBoundingClientRect();
  const dx = bmState.lastX == null ? 0 : e.clientX - bmState.lastX; bmState.lastX = e.clientX;
  const cur = bmState.hoverI >= 0 ? st.spans[bmState.hoverI] : null;
  if (cur && (dx < 4 || e.clientX < T.left)) {
    const rs = cur.getClientRects();
    if (rs.length && e.clientY >= rs[0].top - 4 && e.clientY <= rs[rs.length - 1].bottom + 4) return cur;
  }
  const c = e.target.closest?.(".chunk"); if (c) return c;
  if (e.clientX >= T.left) return null;                   // irgendwo links vom Text – egal wie weit
  for (const dx of [4, 24, 60]) {
    const hit = document.elementFromPoint(T.left + dx, e.clientY)?.closest(".chunk");
    if (hit) return hit;
  }
  return null;
}
$("readScroll").addEventListener("mousemove", (e) => {
  if (e.target.closest("#bmLayer")) return;                 // über dem Symbol selbst: stehen lassen
  const c = bmChunkAt(e), h = $("bmHover"); if (!h || st.doc?.demo) return;
  const i = c ? +c.dataset.i : -1;
  if (i < 0 || bmList().some((b) => b.chunk === i)) { h.classList.remove("on"); bmState.hoverI = -1; return; }
  if (i === bmState.hoverI) return;
  const p = bmPos(i); if (!p) return;
  bmState.hoverI = i; h.style.translate = `${p.x}px ${p.y}px`; h.classList.add("on");
});
$("readScroll").addEventListener("mouseleave", () => { $("bmHover")?.classList.remove("on"); bmState.hoverI = -1; });
$("reader").addEventListener("click", async (e) => {
  const h = e.target.closest("#bmHover"), m = e.target.closest(".bm-mark");
  if (h && bmState.hoverI >= 0) {
    e.stopPropagation();
    const i = bmState.hoverI; h.classList.remove("on"); bmState.hoverI = -1;
    let r; try { r = await api(`/api/docs/${st.doc.id}/bookmarks`, { method: "POST", body: JSON.stringify({ chunk: i }) }); } catch (err) { return toastErr(err); }
    st.doc.bookmarks = r.bookmarks;
    const nb = r.bookmarks.find((b) => b.chunk === i);
    bmRender(nb?.id);
    let seen = false; try { seen = localStorage.getItem("vorleser.bmHint") === "1"; } catch {}
    if (!seen) setTimeout(() => bmHintShow(nb), 450); else toast("Lesezeichen gesetzt");
  } else if (m) { e.stopPropagation(); bmPopOpen(m.dataset.bm, m); }
});
function bmPopOpen(id, anchor) {
  const b = bmList().find((x) => x.id === id); if (!b) return;
  bmState.popId = id;
  let t = ""; for (const c of st.doc.chapters || []) if (c.chunk <= b.chunk) t = c.title;
  $("bmPopWhere").textContent = `${t ? t + " · " : ""}Abschn. ${b.chunk + 1}`;
  $("bmPopText").textContent = `„${b.text}“`;
  $("bmPopNote").value = b.note || "";
  $("bmPopMic").classList.toggle("hidden", !st.features?.dictate);   // Diktat nur, wenn Whisper da ist
  const p = $("bmPop"); p.classList.remove("hidden");
  const r = anchor.getBoundingClientRect();
  p.style.left = `${Math.min(innerWidth - p.offsetWidth - 8, r.right + 10)}px`;
  p.style.top = `${Math.max(8, Math.min(innerHeight - p.offsetHeight - 8, r.top - 12))}px`;
  animateIn(p, "enter");
}
async function bmPopClose(save) {
  const id = bmState.popId; if (!id) return;
  bmState.popId = null; softHide($("bmPop"));
  const b = bmList().find((x) => x.id === id), note = $("bmPopNote").value.trim();
  if (save && b && note !== (b.note || "")) {
    try { st.doc.bookmarks = (await api(`/api/docs/${st.doc.id}/bookmarks/${id}`, { method: "PATCH", body: JSON.stringify({ note }) })).bookmarks; } catch (e) { toastErr(e); }
  }
}
$("bmPopOk").onclick = () => bmPopClose(true);
$("bmPopDel").onclick = async () => {
  const id = bmState.popId; bmState.popId = null; softHide($("bmPop"));
  const mark = $("bmLayer")?.querySelector(`[data-bm="${id}"]`);
  if (mark) { mark.classList.add("leaving"); await new Promise((r) => setTimeout(r, 220)); }
  try { st.doc.bookmarks = (await api(`/api/docs/${st.doc.id}/bookmarks/${id}`, { method: "DELETE" })).bookmarks; } catch (e) { return toastErr(e); }
  bmRender();
};
document.addEventListener("pointerdown", (e) => { if (bmState.popId && !e.target.closest("#bmPop, .bm-mark")) bmPopClose(true); }, true);
/* Erstes Lesezeichen: Spotlight wie im Rundgang – erst aufs Lesezeichen, dann gleitet es zum Kapitel-Menü (Board 02b) */
function bmSpotTo(r, pad = 8) {
  const s = $("bmSpot");
  Object.assign(s.style, { translate: `${r.left - pad}px ${r.top - pad}px`, width: `${r.width + 2 * pad}px`, height: `${r.height + 2 * pad}px` });
}
function bmHintShow(b) {
  const hint = $("bmHint"), mark = $("bmLayer")?.querySelector(`[data-bm="${b?.id}"]`);
  if (!mark) return;
  hint.classList.remove("hidden", "leaving", "card-on");
  bmSpotTo(mark.getBoundingClientRect(), 10);
  setTimeout(() => {                                       // Kapitel-Menü öffnet sich auf „Lesezeichen“
    bmState.tab = "bm";
    if ($("chapterMenu").classList.contains("hidden")) $("chapterBtn").click();
    setTimeout(() => {
      const entry = $("chapterMenu").querySelector(`.cm-bm[data-chunk="${b.chunk}"]`) || $("chapterMenu");
      bmSpotTo(entry.getBoundingClientRect(), 6);
      entry.classList.add("glow");
      const r = entry.getBoundingClientRect(), card = $("bmCard");
      card.style.translate = `${Math.min(innerWidth - 420, r.right + 18)}px ${Math.max(16, r.top)}px`;
      hint.classList.add("card-on");
    }, 380);
  }, 900);
}
$("bmHintOk").onclick = () => {
  try { localStorage.setItem("vorleser.bmHint", "1"); } catch {}
  const hint = $("bmHint"); hint.classList.add("leaving");
  setTimeout(() => { hint.classList.add("hidden"); hint.classList.remove("leaving", "card-on"); }, 300);
  closePops();
};

/* ===================================================================== */
/* Was bisher geschah (Version 3.0): nach > 1 Tag Pause die letzten zwei Absätze nochmal, dann nahtlos weiter       */
/* ===================================================================== */
const recap = { doc: null, to: -1, off: 0, done: new Set() };
function recapStart(off) {
  const d = st.doc, upd = d?.progress?.updated;
  if (!d || d.demo || st.settings?.recap === false || !upd || st.idx < 1 || recap.done.has(d.id)) return false;
  if (Date.now() / 1000 - upd < 86400) return false;
  let from = st.idx, pars = 0;                              // zwei Absatz-Anfänge zurück
  while (from > 0 && pars < 2) { from--; if (d.chunks[from].par || d.chunks[from].h || from === 0) pars++; }
  if (from >= st.idx) return false;
  recap.done.add(d.id);
  Object.assign(recap, { doc: d.id, to: st.idx, off });
  st.spans.forEach((s, i) => s.classList.toggle("recap", i >= from && i < st.idx));
  const bar = $("recapBar"); bar.classList.remove("hidden", "leaving"); animateIn(bar, "enter");
  playFrom(from, 0);
  return true;
}
function recapEnd(jump) {
  if (recap.to < 0) return false;
  const to = recap.to, off = recap.off;
  recap.to = -1;
  st.spans.forEach((s) => s.classList.remove("recap"));
  const bar = $("recapBar"); bar.classList.add("leaving");
  setTimeout(() => { bar.classList.add("hidden"); bar.classList.remove("leaving"); }, 260);
  if (jump) playFrom(to, off);
  return true;
}
function recapNext() { return recap.to >= 0 && st.doc?.id === recap.doc && st.idx + 1 >= recap.to ? recapEnd(true) : false; }
$("recapSkip").onclick = () => recapEnd(true);
$("recapSw").onclick = () => saveSettings({ recap: st.settings?.recap === false });

/* ===================================================================== */
/* Hör-Rückblick (Version 3.0): echte Hörzeit zählen, montags „Deine Woche“ oben in der Seitenleiste             */
/* ===================================================================== */
const hz = { last: null, acc: 0, doc: null };
function hzFlush(finished = false) {
  const secs = Math.round(hz.acc * 10) / 10, doc = hz.doc || st.doc?.id;
  if ((secs < 1 && !finished) || !doc) return;
  hz.acc = 0;
  fetch("/api/hoerzeit", { method: "POST", headers: { "Content-Type": "application/json" }, keepalive: true,
    body: JSON.stringify({ doc, secs: Math.min(600, secs), finished }) }).catch(() => {});
}
audio.addEventListener("timeupdate", () => {
  const t = audio.currentTime;
  if (hz.doc !== st.doc?.id) { hzFlush(); hz.doc = st.doc?.id; hz.last = null; }
  if (!audio.paused && hz.last != null && t > hz.last && t - hz.last < 2) hz.acc += (t - hz.last) / (audio.playbackRate || 1);   // echte Zeit (bei 1,5× weniger als Audiolänge)
  hz.last = t;
  if (hz.acc >= 30) hzFlush();
});
audio.addEventListener("pause", () => { hz.last = null; hzFlush(); });
audio.addEventListener("ended", () => { hz.last = null; if (st.doc && st.idx >= st.doc.chunks.length - 1) hzFlush(true); else hzFlush(); });
addEventListener("pagehide", () => hzFlush());
const fmtHM = (s) => { const m = Math.round(s / 60); return m < 60 ? `${m} Min.` : `${Math.floor(m / 60)} Std. ${m % 60 ? `${m % 60} Min.` : ""}`.trim(); };
async function weekShow(last) {
  let w; try { w = await api(`/api/hoerzeit/woche${last ? "?last=1" : ""}`); } catch { return; }
  if (last && w.total < 60) return;                        // leere Woche → keine Karte
  const card = $("weekCard"), max = Math.max(1, ...w.days.map((d) => d.secs)), names = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"];
  $("weekTitle").textContent = last ? "Deine Woche" : "Diese Woche";
  $("weekTotal").textContent = fmtHM(w.total);
  $("weekSub").textContent = [`${w.finished} ${w.finished === 1 ? "Text" : "Texte"} beendet`, w.top ? `am längsten: ${w.top}` : ""].filter(Boolean).join(" · ");
  const today = new Date().toISOString().slice(0, 10);
  $("weekBars").innerHTML = w.days.map((d, i) => `<div class="wk-b"><i style="height:${Math.max(4, Math.round(d.secs / max * 54))}px;--k:${i}" class="${d.date === today ? "now" : ""}"></i><span>${names[i]}</span></div>`).join("");
  card.dataset.week = w.week;
  const grow = heightFrom($("side"));
  card.classList.remove("hidden"); animateIn(card, "enter"); grow?.(420);
}
$("weekClose").onclick = async () => {
  try { localStorage.setItem("vorleser.weekSeen", $("weekCard").dataset.week || ""); } catch {}
  await collapseOut($("weekCard")); $("weekCard").classList.add("hidden");
};
$("weekBtn").onclick = () => { showView("read"); weekShow(false); };
setTimeout(() => {                                          // montags: Rückblick auf die vergangene Woche, einmal
  if (new Date().getDay() !== 1) return;
  const d = new Date(); d.setDate(d.getDate() - 7 - ((d.getDay() + 6) % 7));
  let seen = ""; try { seen = localStorage.getItem("vorleser.weekSeen") || ""; } catch {}
  const wk = d.toISOString().slice(0, 10);
  if (seen !== wk) weekShow(true);
}, 2500);


/* ===================================================================== */
/* Suchen im Text (⌘F / Strg+F, Tester-Rückmeldung): Treffer per CSS Highlight API – der Text selbst bleibt unverändert */
/* ===================================================================== */
const fnd = { hits: [], i: -1, t: 0 };
const hiOK = !!(window.CSS?.highlights && window.Highlight);
function findRanges(q) {
  const out = [], ql = q.toLowerCase();
  for (const span of st.spans || []) {
    const txt = span.textContent, low = txt.toLowerCase();
    let at = low.indexOf(ql); if (at < 0) continue;
    const nodes = [], w = document.createTreeWalker(span, NodeFilter.SHOW_TEXT); let n, pos = 0;
    while ((n = w.nextNode())) { nodes.push([n, pos]); pos += n.nodeValue.length; }
    const locate = (o) => { for (let k = nodes.length - 1; k >= 0; k--) if (nodes[k][1] <= o) return [nodes[k][0], o - nodes[k][1]]; return [nodes[0][0], 0]; };
    while (at >= 0) {
      const r = document.createRange(), [a, ao] = locate(at), [b, bo] = locate(at + q.length);
      try { r.setStart(a, ao); r.setEnd(b, bo); out.push({ r, span }); } catch {}
      at = low.indexOf(ql, at + Math.max(1, q.length));
    }
  }
  return out;
}
function findPaint() {
  if (!hiOK) return;
  CSS.highlights.set("vfind", new Highlight(...fnd.hits.map((h) => h.r)));
  CSS.highlights.set("vfind-cur", fnd.hits[fnd.i] ? new Highlight(fnd.hits[fnd.i].r) : new Highlight());
}
function findRun(keep) {
  const q = $("findQ").value.trim();
  fnd.hits = q.length >= 2 ? findRanges(q) : [];
  if (!keep || fnd.i >= fnd.hits.length) fnd.i = fnd.hits.length ? 0 : -1;
  $("findN").textContent = q.length < 2 ? "" : fnd.hits.length ? `${fnd.i + 1} / ${fnd.hits.length}` : "Keine Treffer";
  findPaint();
  if (!keep) findShow();
}
function findShow() {
  const h = fnd.hits[fnd.i]; if (!h) return;
  document.querySelectorAll(".chunk.find-hit").forEach((s) => s.classList.remove("find-hit"));
  if (!hiOK) h.span.classList.add("find-hit");
  const box = $("readScroll").getBoundingClientRect(), r = h.r.getBoundingClientRect();
  if (r.top < box.top + 90 || r.bottom > box.bottom - 120) $("readScroll").scrollBy({ top: r.top - box.top - box.height / 3, behavior: "smooth" });
}
function findStep(d) {
  if (!fnd.hits.length) return;
  fnd.i = (fnd.i + d + fnd.hits.length) % fnd.hits.length;
  $("findN").textContent = `${fnd.i + 1} / ${fnd.hits.length}`;
  findPaint(); findShow();
}
function findOpen(on) {
  const bar = $("findBar");
  if (on) { bar.classList.add("open"); setTimeout(() => { $("findQ").focus(); $("findQ").select(); }, 30); if ($("findQ").value) findRun(); return; }
  bar.classList.remove("open"); fnd.hits = []; fnd.i = -1;
  if (hiOK) { CSS.highlights.delete("vfind"); CSS.highlights.delete("vfind-cur"); }
  document.querySelectorAll(".chunk.find-hit").forEach((s) => s.classList.remove("find-hit"));
}
$("findQ").oninput = () => { clearTimeout(fnd.t); fnd.t = setTimeout(() => findRun(), 120); };
$("findQ").onkeydown = (e) => {
  if (e.key === "Enter") { e.preventDefault(); findStep(e.shiftKey ? -1 : 1); }
  else if (e.key === "Escape") { e.preventDefault(); e.stopPropagation(); findOpen(false); }
};
$("findNext").onclick = () => findStep(1);
$("findPrev").onclick = () => findStep(-1);
$("findX").onclick = () => findOpen(false);
document.addEventListener("keydown", (e) => {
  if ((e.metaKey || e.ctrlKey) && !e.altKey && e.key.toLowerCase() === "f" && view === "read" && st.doc && !document.querySelector("dialog[open]")) {
    e.preventDefault(); findOpen(true);
  }
});
// Wort-Markierung baut den aktuellen Abschnitt um → Treffer neu berechnen, damit sie nicht ins Leere zeigen
new MutationObserver(() => { if ($("findBar").classList.contains("open") && fnd.hits.length) { clearTimeout(fnd.mo); fnd.mo = setTimeout(() => findRun(true), 60); } })
  .observe($("docText"), { childList: true, subtree: true });


/* ===================================================================== */
/* Kompakte Ansicht (Fenster schmaler als 640 px oder niedriger als 560 px): nur noch der Player – groß, mit Wellen und
   Mitlesezeile. Vorher drängelte sich die Oberfläche und „glitchte“ (Rückmeldung Simon). Bibliothek über ☰. */
/* ===================================================================== */
// Nur zwei Ansichten (Simon, 10.11.2026): normal mit Seitenleiste oder Mini-Player – keine Zwischenstufe. Ab 1000 px Breite
// passt die Seitenleiste nicht mehr (siehe @media max-width 1000px) → Mini. Auch in Einstellungen/Neuer Text; die Ansicht
// darunter bleibt erhalten und ist beim Größerziehen wieder da. Ausnahme Bearbeiten (dort wird getippt).
const compactMq = matchMedia("(max-width: 1000px), (max-height: 560px)");
function compactSync() {
  const on = compactMq.matches && !!st.doc && view !== "edit";
  if (document.body.classList.contains("compact") === on) return;
  document.body.classList.toggle("compact", on);
  nowSync();
  const anim = on ? $("player").animate?.([{ transform: "scale(.98)" }, { transform: "none" }], { duration: 320, easing: EASE_OUT }) : null;
  mlSync();
  // Wort-Box der Mitlesezeile nach dem Einzoomen neu messen – mittendrin (98 %) gemessen saß sie ~25 px daneben (10.11.2026)
  anim?.finished.then(() => mlSync(), () => {});
}
compactMq.addEventListener?.("change", compactSync);
setInterval(compactSync, 500);                            // Ansichtswechsel / Text geöffnet – billig, kein Haken nötig

/* Player rechts: Beschriftungen nur, solange sie passen. Feste Breiten (Container-Abfragen) reichten nicht – wie lang
   „Kapitelende“/„End of chapter“, ein Atmosphäre- oder Stimmenname ist, hängt von Sprache und Zustand ab; sonst lief die
   Gruppe nach links über Vorspulen/Weiter (Tester-Rückmeldung 3.0.2). Reihenfolge: Atmosphäre, Stimme, Schlaf-Timer. */
const FIT_STEPS = ["fit-atmo", "fit-voice", "fit-sleep", "fit-tight"];   // zuletzt: Knöpfe enger zusammen
function fitRight() {
  const r = document.querySelector(".player .right"); if (!r) return;
  r.classList.remove(...FIT_STEPS);
  const row = r.parentElement, tr = row?.querySelector(".transport");
  if (!tr || !row.clientWidth || getComputedStyle(r).position === "absolute") return;   // Mini-Player: eigene Anordnung
  // Platz pro Seite neben den Wiedergabe-Knöpfen (Titel links und Gruppe rechts teilen ihn sich, die Mitte bleibt mittig).
  // Gemessen an der Zeile, nicht an der Gruppe: die darf seit 3.0.4 nie schmaler als ihr Inhalt werden (CSS).
  const rs = getComputedStyle(row), ts = getComputedStyle(tr), gapRow = parseFloat(rs.columnGap) || 0;
  const mid = tr.getBoundingClientRect().width + (parseFloat(ts.marginLeft) || 0) + (parseFloat(ts.marginRight) || 0);
  const side = (row.clientWidth - (parseFloat(rs.paddingLeft) || 0) - (parseFloat(rs.paddingRight) || 0) - mid - 2 * gapRow) / 2;
  const need = () => { const g = parseFloat(getComputedStyle(r).columnGap) || 0, cs = [...r.children].filter((c) => c.getClientRects().length);
    return cs.reduce((w, c) => w + c.getBoundingClientRect().width, 0) + Math.max(0, cs.length - 1) * g; };
  for (const s of FIT_STEPS) { if (need() <= side + 0.5) break; r.classList.add(s); }
}
{
  const r = document.querySelector(".player .right");
  if (r) {
    new ResizeObserver(() => fitRight()).observe(r.parentElement);
    const mo = new MutationObserver(() => fitRight());
    for (const id of ["sleepLbl", "atmoLbl", "voiceLbl"]) mo.observe($(id), { childList: true, characterData: true, subtree: true });
  }
}

/* Fortschrittsbalken flüssig (3.0.3, Simon): `timeupdate` kommt in WebKit nur ~4× pro Sekunde → Balken und Knopf
   rückten in Stufen vor. Beim Abspielen zeichnet requestAnimationFrame jedes Bild aus audio.currentTime (nur Breite
   und Lage; Bibliothek, ARIA und Speichern bleiben bei timeupdate). Pause/verdecktes Fenster → Schleife steht. */
let barRaf = 0;
function barFrame() {
  barRaf = 0;
  if (!st.doc || audio.paused || document.hidden || st.loadedIdx !== st.idx) return;
  if (!scrub.drag && !$("prog").classList.contains("glide")) {
    const pct = docPct({ count: st.doc.chunks.length, progress: { chunk: st.idx, frac: curFrac() } });
    $("fill").style.width = `${pct}%`; $("knob").style.left = `${pct}%`;
  }
  barRaf = requestAnimationFrame(barFrame);
}
const barGo = () => { if (!barRaf) barRaf = requestAnimationFrame(barFrame); };
audio.addEventListener("playing", barGo);
audio.addEventListener("timeupdate", barGo);
document.addEventListener("visibilitychange", barGo);
