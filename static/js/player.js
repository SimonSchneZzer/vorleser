"use strict";
// Vorleser – Player, Fortschrittsleiste, Bearbeiten, Vorab erzeugen, Export. Teil der Oberfläche; Reihenfolge der Dateien: index.html
/* ===================================================================== */
/* Player-Oberfläche                                                      */
/* ===================================================================== */
function highlight(scroll) {
  if (!st.doc) return;
  st.spans.forEach((s, i) => { s.classList.toggle("current", i === st.idx); s.classList.toggle("done", i < st.idx); });
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
  }
  markReady();
  const ch = currentChapter();
  $("chapterLbl").textContent = ch ? ch.title : "";
  $("posL").textContent = `Abschn. ${st.idx + 1}`;
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
  b.classList.toggle("is-playing", s === "playing" || (s === "loading" && !showLoad));
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
// Statuszeile: nur neu zeichnen, wenn sich wirklich etwas ändert (vorher bei jedem Aufruf innerHTML neu →
// Flackern). Kurze Zwischenzustände (< 150 ms, z. B. beim Abschnittswechsel) werden geschluckt; ein neuer
// Text gleitet einmal kurz herein.
const statusSt = { html: "", pending: "", timer: 0 };
function setStatus(html, now = false) {
  statusSt.pending = html;
  clearTimeout(statusSt.timer);
  if (html === statusSt.html) return;
  const apply = () => {
    const el = $("status"), first = !statusSt.html, h = statusSt.pending;
    if (h === statusSt.html) return;
    statusSt.html = h;
    el.innerHTML = h;
    if (!first && !matchMedia("(prefers-reduced-motion: reduce)").matches) {
      el.classList.remove("swap"); void el.offsetWidth; el.classList.add("swap");
    }
  };
  if (now || !statusSt.html) apply(); else statusSt.timer = setTimeout(apply, 150);
}
function updateStatus(loading = false) {
  if (!st.doc) return;
  if (st.doc.demo) return setStatus(`<span class="dot"></span><span>Beispieltext</span>`);
  if (st.lastError && !st.wantPlay) {
    statusSt.html = "";                       // Knopf braucht frische Elemente + Handler
    setStatus(`<span class="status-err">${icon("i-x", "i", "width:14px;height:14px")}${esc(st.lastError.msg)} · <button class="linkbtn" id="retryBtn">Erneut versuchen</button></span>`);
    $("retryBtn").onclick = () => { const r = st.lastError?.retry; st.lastError = null; r ? r() : play(); };
    return;
  }
  let ready = 0; for (let i = st.idx + 1; i < st.doc.chunks.length; i++) if (isReady(i)) ready++;   // alle kommenden, auch nach einer Lücke
  const nextReady = isReady(st.idx + 1);
  const allReady = st.doc.chunks.every((_, i) => isReady(i));
  const waiting = loadingVisible();
  const ch = currentChapter();
  const parts = [];
  if (ch) parts.push(esc(ch.title));
  const last = st.idx >= st.doc.chunks.length - 1;
  if (waiting) parts.push(st.doc.voice.startsWith("clone:") ? "Eigene Stimme erzeugt …" : "Bereite vor …");
  else {
    parts.push(allReady ? "Alles vorbereitet" : last ? "Letzter Abschnitt" : `${nAbschn(ready)} vorbereitet`);
    if (!last && !allReady && ready > 0 && !nextReady) parts.push("der nächste fehlt noch");
  }
  if (!st.wantPlay && st.pendingOffset > 0) parts.push("Lesezeichen");
  const fb = st.cache.get(st.idx)?.fallback ? ` · <span class="warn" title="Online-Stimme nicht erreichbar – Piper liest offline weiter">offline: Ersatzstimme</span>` : "";
  const dot = `<span class="dot${!last && !nextReady ? " empty" : ""}" title="${!nextReady && !last ? "Der nächste Abschnitt muss erst erzeugt werden" : "Nächste Abschnitte sind bereit"}"></span>`;
  setStatus(`${waiting ? '<span class="spin"></span>' : dot}<span>${parts.join(" · ")}${fb}</span>`);
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
  if (W && W.idx === t.i && W.doc === st.doc.id) return W.list[wordAtFrac(W.list, t.frac)]?.el.firstElementChild?.getBoundingClientRect();
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
};
$("voiceBtn").onclick = (e) => {
  e.stopPropagation();
  if (!$("voicePanel").classList.contains("hidden") && !$("voicePanel").classList.contains("leaving")) return closePops();
  openVoicePanel($("voiceBtn"), { langs: [st.doc.lang], lang: st.doc.lang, current: st.doc.voice, onPick: changeDocVoice, doc: st.doc.demo ? null : st.doc.id });
};
async function changeDocVoice(v) {
  if (!st.doc || v === st.doc.voice) return;
  const wasPlaying = st.wantPlay;
  stop();
  await api(`/api/docs/${st.doc.id}`, { method: "PATCH", body: JSON.stringify({ voice: v }) });
  st.doc.voice = v; st.pendingOffset = 0; st.pendingFrac = null; st.srvCached = new Set();
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
  m.innerHTML = st.doc.chapters.map((c, n) => `<button data-chunk="${c.chunk}" class="${c === cur ? "on" : ""}">${n + 1}. ${esc(c.title)}</button>`).join("");
  m.style.setProperty("--origin", "top left");
  openPop(m);
  const r = $("chapterBtn").getBoundingClientRect();
  m.style.left = `${r.left}px`; m.style.top = `${r.bottom + 6}px`;
};
$("chapterMenu").onclick = (e) => { const b = e.target.closest("[data-chunk]"); if (b) { closePops(); jumpTo(+b.dataset.chunk, 0); } };
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
$("mPrep").onclick = async () => { closePops(); await api(`/api/docs/${st.doc.id}/prepare`, { method: "POST" }); updatePrep(true); jobsPoll(); };
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
    showView("edit"); edDirty();
    // Cursor an die Stelle setzen, an der gerade gelesen wird
    const ta = $("edText"), cur = st.doc.chunks[st.idx]?.text || "";
    const pos = Math.max(0, d.text.indexOf(cur.slice(0, 60)));
    requestAnimationFrame(() => {
      ta.focus({ preventScroll: true }); ta.setSelectionRange(pos, pos);
      ta.scrollTop = Math.max(0, (pos / Math.max(1, d.text.length)) * ta.scrollHeight - ta.clientHeight / 3);
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
async function updatePrep(force) {
  clearTimeout(prepTimer);
  if (!st.doc) return;
  if (st.doc.demo) { $("prepBtn").classList.add("hidden"); $("prepX").classList.add("hidden"); return; }
  const id = st.doc.id;
  const j = await api(`/api/docs/${id}/prepare`).catch(() => null);
  if (!j || st.doc?.id !== id) return;
  st.srvCached = new Set((j.cached || []).flatMap((c, i) => (c ? [i] : [])));
  markReady();
  const isClone = st.doc.voice.startsWith("clone:");
  const running = j.status === "running", all = j.total > 0 && j.done >= j.total;
  const b = $("prepBtn");
  b.classList.toggle("hidden", !isClone && !running);
  b.classList.toggle("running", running);
  b.classList.toggle("done", all && !running);
  b.disabled = running || all;                          // läuft → Abbrechen nur über ✕; fertig → nichts mehr zu tun
  $("prepIc").setAttribute("href", all && !running ? "#i-check" : "#i-bolt");
  $("prepLbl").textContent = running ? `Erzeuge ${j.done}/${j.total}` : all ? "Alles vorbereitet" : "Vorab erzeugen";
  b.dataset.tip = running ? "Wird im Hintergrund erzeugt – du kannst weiterhören oder woanders hin. ✕ bricht ab."
    : all ? "Alle Abschnitte sind fertig – alles spielt ohne Wartezeit."
    : "Erzeugt alle Abschnitte schon jetzt im Hintergrund. Danach spielt alles ohne Wartezeit – ideal für deine eigene Stimme, die pro Abschnitt etwas länger braucht.";
  b.setAttribute("aria-disabled", String(running || all));
  $("prepX").classList.toggle("hidden", !running);
  if (running || force) prepTimer = setTimeout(() => updatePrep(), 2000);
}
$("prepBtn").onclick = async () => {
  if ($("prepBtn").disabled) return;
  await api(`/api/docs/${st.doc.id}/prepare`, { method: "POST" });
  updatePrep(true); jobsPoll();
};
$("prepX").onclick = async () => {
  await api(`/api/docs/${st.doc.id}/prepare`, { method: "DELETE" });
  setTimeout(() => updatePrep(true), 300);
};

/* ---------- Hintergrund-Aufträge (Vorab erzeugen) – Fortschritt in der Bibliothek, Meldung am Ende ---------- */
const jobs = { list: [], prev: new Map(), t: 0 };
async function jobsPoll() {
  clearTimeout(jobs.t);
  let r; try { r = await api("/api/jobs"); } catch { return; }
  const cur = new Map(r.jobs.map((j) => [`${j.doc}#${j.kind}`, j]));
  for (const [k, j] of jobs.prev) {
    if (cur.has(k)) continue;
    if (j.kind === "export") {                            // Export fertig → melden (außer der Dialog zeigt es gerade)
      api(`/api/docs/${j.doc}/export`).then((x) => {
        if (x.status !== "ready" || ($("exportDlg").open && st.doc?.id === j.doc)) return;
        const d = st.docs.find((y) => y.id === j.doc);
        toast(`„${d?.title || "Text"}“ ist als Hörbuch fertig`);
      }).catch(() => {});
      continue;
    }
    if (j.kind !== "prepare") continue;                   // beendet → war es vollständig?
    api(`/api/docs/${j.doc}/prepare`).then((p) => {
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
function xDocInfo() {
  const d = st.doc, chars = d.chunks.reduce((s, c) => s + c.text.length, 0), sec = chars / 15;
  $("xInfo").textContent = [d.title, `ca. ${fmtDuration(sec)}`, d.chapters.length ? `${d.chapters.length} Kapitel` : ""].filter(Boolean).join(" · ");
  // Größe grob schätzen: M4B/MP3 mit 64 kbit/s, WAV unkomprimiert (24 kHz, 16 bit, mono)
  const est = { m4b: sec * 8000, mp3: sec * 8000, wav: sec * 48000 };
  document.querySelectorAll("#xFmts [data-sz]").forEach((el) => (el.textContent = `≈ ${fmtMB(est[el.dataset.sz])}`));
  // Fortschritt in Kapitel geteilt (bei sehr vielen Kapiteln ein durchgehender Balken)
  const n = d.chunks.length, starts = d.chapters.map((c) => c.chunk).filter((c) => c > 0);
  const bounds = starts.length && starts.length < 30 ? [0, ...starts, n] : [0, n];
  xDocInfo.bounds = bounds;
  $("xSegs").innerHTML = bounds.slice(0, -1).map((s0, k) => `<span class="xseg" style="flex:${Math.max(1, bounds[k + 1] - s0)}"><i></i></span>`).join("");
}
function xRunRender(j) {
  const coding = j.phase === "Kodieren", d = st.doc, done = coding ? j.total : j.done;
  const pct = coding ? 100 : j.total ? (j.done / j.total) * 100 : 0;
  $("xPhase").textContent = coding ? "Datei wird erstellt …" : "Wird vertont …";
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
async function exportPoll() {
  clearTimeout(xTimer);
  if (!st.doc || !$("exportDlg").open) return;
  const j = await api(`/api/docs/${st.doc.id}/export`);
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
    xSetView("done", animate);
  } else {
    xSetView("pick", animate);
    xMsg(j.status === "error" ? `Fehler: ${j.error}` : j.status === "cancelled" ? "Abgebrochen" : "");
  }
}
$("exportBtn").onclick = () => {
  xDocInfo();
  xPrev = null; xView = null;
  $("xMsg").textContent = ""; $("xMsg").classList.add("hidden");
  $("exportDlg").showModal(); exportPoll();
};
$("xStart").onclick = async () => {
  const fmt = $("xFmts").querySelector("input:checked").value;
  $("xStart").disabled = true;
  try {
    await api(`/api/docs/${st.doc.id}/export`, { method: "POST", body: JSON.stringify({ format: fmt }) });
    xPrev = xPrev ?? "none";      // Übergang Auswählen → Läuft animieren
    await exportPoll();
    jobsPoll();                   // Bibliothek zeigt den Fortschritt, Hinweis beim Fertigwerden
  } catch (err) { xMsg(`Fehler: ${err.message}`); }
  $("xStart").disabled = false;
};
$("xCancel").onclick = async () => { await api(`/api/docs/${st.doc.id}/export`, { method: "DELETE" }); setTimeout(exportPoll, 300); };
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

