"use strict";
// Vorleser – Dokument öffnen, Audio abspielen, Markierung. Teil der Oberfläche; Reihenfolge der Dateien: index.html
/* ===================================================================== */
/* Dokument öffnen & darstellen                                           */
/* ===================================================================== */
let openTok = 0;
async function openDoc(id) {
  const my = ++openTok;                                  // schnell A, dann B geklickt → nur die letzte Antwort zählt
  let doc;
  try { doc = await api(`/api/docs/${id}`); }
  catch (e) { if (my === openTok) toastErr(e); return; }   // Laden gescheitert → alter Text spielt weiter
  if (my !== openTok) return;
  if (st.doc && st.doc.id !== id) { if (st.wantPlay) pause(); else saveProgress(true); }
  stop();
  showDoc(doc);
}
/** Text anzeigen (vom Server geladen oder der Beispieltext des Rundgangs). */
function showDoc(doc) {
  openTok++;                                             // ein noch laufendes openDoc (z. B. vom Start) darf das nicht überschreiben
  const switching = view === "read" && st.doc && st.doc.id !== doc.id && !$("viewRead").classList.contains("hidden");
  const prevRank = navRank, ghost = switching ? ghostOf($("readScroll")) : null;
  st.doc = doc; st.idx = doc.progress.chunk; st.pendingOffset = doc.progress.offset || 0;
  st.pendingFrac = !doc.progress.offset && doc.progress.frac > 0 && doc.progress.frac < 1 ? doc.progress.frac : null; st.words = null; st.srvCached = new Set();
  showView("read");
  $("docTitle").textContent = doc.title;
  $("tbTitle").textContent = doc.title; $("tbTitle").title = doc.title;
  nowSync();
  renderDocOver();
  setVoicePill($("voiceAv"), $("voiceLbl"), doc.voice);
  $("chapterBtn").classList.toggle("hidden", !doc.chapters.length);
  posRender();
  $("ticks").innerHTML = doc.chapters.filter((c) => c.chunk > 0).map((c) => `<span class="tick" data-c="${c.chunk}" style="left:${(c.chunk / doc.chunks.length) * 100}%"></span>`).join("");

  const box = $("docText"); box.innerHTML = "";
  const frag = document.createDocumentFragment();
  let p = null;
  st.spans = doc.chunks.map((c, i) => {
    let s;
    if (c.h) { s = document.createElement("h2"); frag.appendChild(s); p = null; }
    else {
      if (c.par || !p) {
        p = document.createElement("p"); frag.appendChild(p);
        if (c.li) p.className = c.li === "n" ? "li num" : "li";     // Listenpunkt (Version 3.0)
      }
      else p.appendChild(document.createTextNode(" "));
      s = document.createElement("span"); p.appendChild(s);
    }
    s.className = "chunk"; s.textContent = c.text; s.dataset.i = i;
    return s;
  });
  box.appendChild(frag);
  requestAnimationFrame(() => window.bmRender?.());          // Lesezeichen (3.0)
  st.readySet = new Set();
  st.lastError = null;
  if (switching) {
    const how = viewRank("read") >= prevRank ? "down" : "up";
    navIn($("readScroll"), how); navOut(ghost, how);
    navRank = viewRank("read");
  }
  renderLibrary();
  highlight(false);
  st.spans[st.idx]?.scrollIntoView({ block: "center" });      // gleich an der richtigen Stelle (gleitet nicht nach)
  prefetch();
  updateStatus(); updatePrep(); updateMediaSession();
}
// Gezogen = markiert → nicht springen (das Menü zum Kopieren/Aussprechen kommt, einstellungen.js); nur echter Klick springt
let downAt = null;
$("docText").addEventListener("mousedown", (e) => { downAt = [e.clientX, e.clientY, e.detail]; });
$("docText").onclick = (e) => {
  const moved = downAt && Math.hypot(e.clientX - downAt[0], e.clientY - downAt[1]) > 4;
  if (moved || e.detail > 1) return;                      // ziehen oder Doppelklick (Wort markieren)
  const s = e.target.closest(".chunk"); if (s) jumpTo(+s.dataset.i, 0, true);
};
function renderDocOver() {
  const doc = st.doc; if (!doc) return;
  const chars = doc.chunks.reduce((s, c) => s + c.text.length, 0);
  $("docOver").textContent = [doc.chapters.length ? `${doc.chapters.length} Kapitel` : nAbschn(doc.chunks.length),
    `ca. ${fmtDuration(chars / 15)} Hördauer`,
    doc.progress.updated ? `zuletzt gehört ${new Date(doc.progress.updated * 1000).toLocaleString(LOC(), { dateStyle: "medium", timeStyle: "short" })}` : ""].filter(Boolean).join(" · ");   // mit Uhrzeit (Tester-Rückmeldung)
}
/** „Abschnitt 6 von 6“ links (statt „Abschn. 6 … von 6“, das verwirrte – Tester-Rückmeldung), rechts die Restzeit. */
function posRender() {
  if (!st.doc) return;
  const n = st.doc.chunks.length, i = Math.min(st.idx, n - 1);
  rollText($("posL"), `Abschnitt ${i + 1} von ${n}`);
  const rest = st.doc.chunks.slice(i).reduce((a, c) => a + c.text.length, 0) / 15 / (+$("rate").value || 1);
  rollText($("posR"), rest < 30 ? "fast fertig" : `noch ca. ${fmtDuration(rest)}`);
}
function fmtDuration(sec) { const m = Math.max(1, Math.round(sec / 60)); return m < 60 ? `${m} Min.` : `${Math.floor(m / 60)} Std. ${m % 60 ? `${m % 60} Min.` : ""}`.trim(); }
function currentChapter() {
  let ch = null;
  for (const c of st.doc?.chapters || []) { if (c.chunk <= st.idx) ch = c; else break; }
  return ch;
}

/* ===================================================================== */
/* Audio vorbereiten & abspielen                                          */
/* ===================================================================== */
function getAudio(i) {
  if (st.doc?.demo) return Promise.reject(new Error("demo"));
  if (!st.cache.has(i)) {
    const docId = st.doc.id, voice = st.doc.voice;
    // weiter vorne: „pre“ → Server nimmt keine Ersatzstimme (die bliebe sonst für den Rest der Sitzung hängen)
    const pre = (i > st.idx + 1 ? "&pre=1" : "") + (st.offline ? "&offline=1" : ""), offline = st.offline;
    const entry = { url: null, used: null, fallback: false, at: Date.now() };
    entry.promise = fetch(`/api/docs/${docId}/audio/${i}?v=${encodeURIComponent(voice)}${pre}`)
      .then(async (r) => {
        if (!r.ok) throw new Error((await r.json().catch(() => ({}))).error || "Synthese fehlgeschlagen");
        entry.used = r.headers.get("X-Voice-Used") || voice;
        entry.fallback = entry.used !== voice;
        return r.blob();
      })
      .then((b) => { entry.url = URL.createObjectURL(b); if (st.doc?.id === docId && !offline) st.srvCached.add(i); markReady(); return entry.url; })
      .catch((e) => { st.cache.delete(i); throw e; });
    st.cache.set(i, entry);
  }
  return st.cache.get(i).promise;
}
let prefetching = false, prefetchAgain = false;
async function prefetch() {
  if (!st.doc || st.doc.demo) return;
  if (prefetching) { prefetchAgain = true; return; }       // läuft schon (evtl. für alte Stelle/Text) → danach nochmal
  prefetching = true; prefetchAgain = false;
  try {
    // Aktueller + nächster Abschnitt gleichzeitig, der Rest nacheinander (bei „Viel“ nicht 10 Anfragen auf einmal)
    const doc = st.doc, from = st.idx, last = Math.min(from + ahead(), doc.chunks.length - 1);
    await Promise.all([from, from + 1].filter((i) => i <= last).map((i) => getAudio(i).catch(() => {})));
    for (let i = from + 2; i <= last && st.doc === doc && st.idx === from; i++) await getAudio(i).catch(() => {});
    // „Ganzer Text“: Rest im Hintergrund vorab erzeugen (eigener Auftrag, lässt dem Vorlesen den Vortritt)
    if (st.settings?.ahead === "all" && st.wantPlay && st.doc === doc && st.autoPrep !== doc.id && st.readySet.size < doc.chunks.length) {
      st.autoPrep = doc.id;
      api(`/api/docs/${doc.id}/prepare`, { method: "POST" }).then(() => { updatePrep(true); jobsPoll(); }).catch(() => {});
    }
  } finally { prefetching = false; }
  for (const [i, e] of st.cache) {
    if (i < st.idx - 1 || i > st.idx + ahead() + 1) { if (e.url) URL.revokeObjectURL(e.url); st.cache.delete(i); }
  }
  if (prefetchAgain) return prefetch();
  markReady();
}
function clearCache() {
  for (const e of st.cache.values()) if (e.url) URL.revokeObjectURL(e.url);
  st.cache.clear(); st.loadedIdx = -1;
  st.srvCached = new Set();             // Audio auf dem Server ist weg/ungültig → nicht weiter als „vorbereitet“ zeigen
}

async function playFrom(i, offset = 0) {
  const my = ++st.token;
  const frac = offset && typeof offset === "object" ? offset.frac : null;   // {frac}: Stelle als Anteil am Abschnitt
  st.pendingFrac = frac;
  st.idx = i; st.wantPlay = true; st.lastError = null; st.buffering = false;
  highlight(true); renderPlay(); updateStatus();
  let url;
  // Hängt die Online-Stimme, bietet die Statuszeile nach 6 s den Wechsel zur Offline-Stimme an (nie automatisch, 3.0.2)
  st.waitSince = Date.now(); setTimeout(() => { if (my === st.token && st.waitSince) updateStatus(); }, 6100);
  try { url = await getAudio(i); }
  catch (e) { if (my === st.token) { st.waitSince = 0; failPlay(friendlyError(e), () => playFrom(i, offset)); } return; }
  if (my === st.token) st.waitSince = 0;
  if (my !== st.token) return;
  st.loadedIdx = i; st.switching = true;
  audio.src = url;
  audio.defaultPlaybackRate = audio.playbackRate = +$("rate").value;
  const ok = await new Promise((res) => {               // Metadaten mit Zeitlimit und Fehlerfall abwarten
    const t = setTimeout(() => res(false), 15000);
    audio.addEventListener("loadedmetadata", () => { clearTimeout(t); res(true); }, { once: true });
    audio.addEventListener("error", () => { clearTimeout(t); res(false); }, { once: true });
  });
  if (my !== st.token) return;
  if (!ok) { st.cache.delete(i); st.loadedIdx = -1; return failPlay("Audio konnte nicht geladen werden", () => playFrom(i, offset)); }
  if (frac != null) offset = frac * audio.duration;
  st.pendingFrac = null;
  if (offset > 0 && offset < audio.duration - 0.3) audio.currentTime = offset;
  timeWords(i);
  try { await audio.play(); }
  catch (e) { if (my === st.token) { st.switching = false; if (e.name === "NotAllowedError") { st.wantPlay = false; renderPlay(); } else failPlay("Wiedergabe fehlgeschlagen", () => playFrom(i, offset)); } return; }
  if (my !== st.token) return;
  st.switching = false; renderPlay();
  updateStatus(); saveProgress(true); prefetch(); updateMediaSession();
}
function play() {
  if (!st.doc || st.doc.demo) return;
  if (st.loadedIdx === st.idx && audio.src && !audio.ended) {
    st.wantPlay = true; st.lastError = null; renderPlay();
    audio.playbackRate = +$("rate").value;
    audio.play().then(renderPlay, () => { st.wantPlay = false; renderPlay(); updateStatus(); });
    updateStatus();
  } else {
    const off = st.pendingFrac != null ? { frac: st.pendingFrac } : st.pendingOffset; st.pendingOffset = 0;
    if (window.recapStart?.(off)) return;                 // 3.0: „Was bisher geschah“ nach langer Pause
    playFrom(st.idx, off);
  }
}
function pause() { st.wantPlay = false; st.buffering = false; st.token++; st.switching = false; audio.pause(); renderPlay(); updateStatus(); saveProgress(true); }
function stop() {
  st.token++; st.wantPlay = false; audio.pause(); audio.removeAttribute("src"); audio.load();
  clearCache(); setPlayIcon(false);
}
const toggle = () => (st.wantPlay ? pause() : play());
function jumpTo(i, offset = 0, autoplay = st.wantPlay, frac = null) {
  if (!st.doc) return;
  i = Math.max(0, Math.min(i, st.doc.chunks.length - 1));
  st.lastError = null;
  glideBar();
  if (frac != null && st.loadedIdx === i && st.idx === i && audio.duration) {   // im selben, geladenen Abschnitt: nur spulen
    audio.currentTime = Math.min(frac * audio.duration, audio.duration - 0.3);
    updateBar(); saveProgress(true);
    return;
  }
  if (autoplay) playFrom(i, frac != null ? { frac } : offset);
  else {
    st.token++; st.switching = false; audio.pause(); st.idx = i; st.pendingOffset = offset; st.pendingFrac = frac; st.loadedIdx = -1;
    highlight(true); updateStatus(); saveProgress(true); prefetch(); updateMediaSession();
  }
}
function seekBy(sec) {
  if (st.loadedIdx !== st.idx) return;
  glideBar();
  const t = audio.currentTime + sec;
  if (t < 0 && st.idx > 0) return jumpTo(st.idx - 1, 0);
  if (t > audio.duration) return jumpTo(st.idx + 1, 0);
  audio.currentTime = Math.max(0, t);
}
audio.addEventListener("ended", () => {
  if (!st.doc) return;
  if (window.recapNext?.()) return;                       // 3.0: Wiederholung vorbei → genau an der alten Stelle weiter
  const next = st.idx < st.doc.chunks.length - 1 ? st.idx + 1 : st.doc.chunks.length;
  if (next < st.doc.chunks.length) playFrom(next);
  else { st.wantPlay = false; setPlayIcon(false); saveProgress(true, 0, 1); toast("Fertig gehört"); updateBar(); refreshLibrary(); }
});
audio.addEventListener("timeupdate", () => { updateBar(); if (st.wantPlay && Date.now() - st.lastSave > SAVE_EVERY_MS) saveProgress(); });
audio.addEventListener("play", startTick);
for (const ev of ["play", "playing", "pause", "waiting", "stalled", "canplay", "seeking", "seeked", "emptied"]) {
  audio.addEventListener(ev, () => {
    if (ev === "waiting" || ev === "stalled") st.buffering = true;
    if (ev === "playing" || ev === "canplay" || ev === "seeked") st.buffering = false;
    renderPlay();
    if (ev === "playing" || ev === "waiting") updateStatus();
  });
}
audio.addEventListener("error", () => {
  if (st.switching || !st.wantPlay || !audio.getAttribute("src")) return;   // Fehler beim Laden behandelt playFrom
  const i = st.idx, off = audio.currentTime || 0;
  st.cache.delete(i); st.loadedIdx = -1;
  failPlay("Wiedergabe unterbrochen", () => playFrom(i, off));
});
audio.addEventListener("seeked", () => tick(true));
audio.addEventListener("pause", () => {
  if (st.wantPlay && !st.switching && !audio.ended && !audio.seeking) { st.wantPlay = false; setPlayIcon(false); saveProgress(true); }
});

/* ---------- Lesezeichen ---------- */
function curFrac() {
  if (st.loadedIdx === st.idx && audio.duration) return Math.min(1, audio.currentTime / audio.duration);
  if (st.pendingFrac != null) return st.pendingFrac;
  const p = st.doc?.progress;
  return p && p.chunk === st.idx ? p.frac || 0 : 0;             // noch nicht geladen: gespeicherten Stand zeigen
}
function saveProgress(force = false, offsetOverride, fracOverride) {
  if (!st.doc || st.doc.demo) return;
  if (!force && Date.now() - st.lastSave < SAVE_EVERY_MS) return;
  st.lastSave = Date.now();
  const offset = offsetOverride ?? (st.loadedIdx === st.idx ? audio.currentTime : st.pendingOffset);
  const frac = fracOverride ?? curFrac();
  st.doc.progress = { ...st.doc.progress, chunk: st.idx, offset, frac, updated: Date.now() / 1000 };
  libSync();
  fetch(`/api/docs/${st.doc.id}`, { method: "PATCH", keepalive: true, headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ progress: { chunk: st.idx, offset, frac } }) }).catch(() => {});
}
window.addEventListener("pagehide", () => saveProgress(true));
document.addEventListener("visibilitychange", () => { if (document.hidden) saveProgress(true); });

/* ===================================================================== */
/* Markierung: Abschnitt / Satz / Wort                                    */
/* ===================================================================== */
const markMode = () => st.settings?.mark || "word";
const ABBR = new Set("bzw ca dr prof nr str vgl evtl ggf usw etc inkl bspw hr fr st mio mrd jh abs geb max min zb mr mrs ms vs sog jr sr approx no fig inc ltd co dept vol ch pp".split(" "));
const norm = (s) => s.toLowerCase().replace(/[^\p{L}\p{N}]+/gu, "");
function isSentenceEnd(tok) {
  if (!/[.!?…]["'“”»«)\]]*$/.test(tok)) return false;
  const w = tok.replace(/[.!?…"'“”»«)\]]+$/, "").toLowerCase().replace(/^[(\["'“„»«]+/, "");
  if (/[!?…]/.test(tok.slice(-3))) return true;
  return !(w.length === 1 || ABBR.has(w) || (st.doc?.lang === "de" && /^\d+$/.test(w)));
}
function clearWords() {
  const W = st.words; st.words = null;
  placeWordBox(null); placeSentBoxes([]);
  if (!W || W.doc !== st.doc?.id) return;
  const span = st.spans[W.idx];
  if (span) span.textContent = st.doc.chunks[W.idx].text;
}
/** Wörter eines Abschnitts: Text, Leerraum danach, Position im Text, Satznummer. */
function tokenize(text) {
  const out = []; let sent = 0;
  for (const m of text.matchAll(/\S+\s*/g)) {
    const core = m[0].trimEnd();
    out.push({ text: core, tail: m[0].slice(core.length), at: m.index, sent });
    if (isSentenceEnd(core)) sent++;
  }
  return out;
}
function buildWords(i) {
  clearWords();
  if (markMode() === "section" || !st.spans[i]) return;
  const span = st.spans[i];
  span.textContent = "";
  const list = [];
  for (const tk of tokenize(st.doc.chunks[i].text)) {
    const w = document.createElement("span"); w.className = "w";
    const wt = document.createElement("span"); wt.className = "wt"; wt.textContent = tk.text;
    w.appendChild(wt);
    if (tk.tail) w.appendChild(document.createTextNode(tk.tail));
    span.appendChild(w);
    list.push({ el: w, text: tk.text, sent: tk.sent, t: 0 });
  }
  st.words = { doc: st.doc.id, idx: i, list, cur: -1, curSent: -1, timed: false };
  setWord(0, false, false);                             // Mitlesezeile gleicht highlight() ab (sonst kurz Satz 1, dann Ziel)
}
const wordWeight = (s) => s.length + 2 + (/[,;:–]$/.test(s) ? 4 : 0) + (/[.!?…]["'“”»«)]*$/.test(s) ? 8 : 0);
/** Wort an einer Stelle (Anteil 0–1 am Abschnitt) schätzen – gleiche Gewichtung wie timeWords, ohne Audio. */
function wordAtFrac(L, frac) {
  const total = L.reduce((a, w) => a + wordWeight(w.text), 0) || 1;
  let acc = 0;
  for (let k = 0; k < L.length; k++) { acc += wordWeight(L[k].text); if (acc / total > frac) return k; }
  return Math.max(0, L.length - 1);
}
async function timeWords(i) {
  const W = st.words;
  if (!W || W.idx !== i || st.loadedIdx !== i) return;   // Timing nur mit dem geladenen Audio
  const L = W.list;
  // 1) sofort schätzen (nach Wortlänge und Satzzeichen-Pausen) …
  const dur = audio.duration;
  if (!Number.isFinite(dur) || dur <= 0) {               // Länge noch unbekannt → nicht mit falscher Länge schätzen
    audio.addEventListener("durationchange", () => timeWords(i), { once: true });
    return;
  }
  const weight = wordWeight;
  const total = L.reduce((a, w) => a + weight(w.text), 0) || 1;
  const lead = 0.05, span = Math.max(0.1, dur - lead - 0.25);
  let acc = 0;
  for (const w of L) { w.t = lead + (acc / total) * span; acc += weight(w.text); }
  W.timed = true; W.exact = false;
  tick(true);
  // 2) … dann echte Wortmarken holen (Edge: sofort; eigene Stimme/Piper: per Whisper, dauert ein paar Sekunden)
  let marks = null;
  try { marks = (await api(`/api/docs/${st.doc.id}/marks/${i}`)).marks; } catch {}
  if (st.words !== W || !marks || !marks.length) return;
  const times = L.map(() => null);
  let p = 0;
  for (const [t, , txt] of marks) {
    const n = norm(txt); if (!n) continue;
    for (let k = p; k < Math.min(p + 5, L.length); k++) {
      const wn = norm(L[k].text);
      if (wn && (wn.includes(n) || n.includes(wn))) { if (times[k] == null) times[k] = t; p = wn.endsWith(n) || n.includes(wn) ? k + 1 : k; break; }
    }
  }
  const hits = times.filter((t) => t != null).length;
  if (hits < L.length * 0.5) return;                    // Zuordnung zu unsicher → bei der Schätzung bleiben
  let last = 0;
  L.forEach((w, k) => { w.t = times[k] ?? last; last = w.t; });
  W.exact = true;
  tick(true);
}
function setWord(k, scroll = true, sync = true) {
  const W = st.words; if (!W || k === W.cur) return;
  const old = W.list[W.cur]; if (old) old.el.classList.remove("wc");
  const nw = W.list[k];
  const s = nw ? nw.sent : -1;
  if (s !== W.curSent) {
    const inS = W.list.filter((x) => x.sent === s);
    for (const x of W.list) { x.el.classList.toggle("ws", x.sent === s); x.el.classList.remove("wf", "wl"); }
    inS[0]?.el.classList.add("wf"); inS.at(-1)?.el.classList.add("wl");
    W.curSent = s;
    placeSentBoxes(inS.map((x) => x.el));
  }
  if (nw && markMode() === "word") nw.el.classList.add("wc");
  placeWordBox(nw?.el, W.cur >= 0);
  W.cur = k;
  if (sync && !scrub.drag) mlSync();
  if (scroll && nw) keepVisible(nw.el);
}
/** Gleitende Box (Wort-Markierung, Rahmen beim Ziehen – im Text und in der Mitlesezeile) über ein Rechteck legen.
 *  Gleitet von Wort zu Wort; beim ersten Zeigen und bei Zeilenwechsel springt sie. r = null → ausblenden. */
function boxIn(host, id, cls, r, animate = true) {
  let box = host.querySelector(`:scope > #${id}`);
  if (!box) { box = document.createElement("span"); box.id = id; box.className = cls; box.setAttribute("aria-hidden", "true"); host.appendChild(box); }
  if (!r) { box.classList.remove("on"); box.dataset.y = ""; return; }
  const R = host.getBoundingClientRect(), x = r.left - R.left - 3, y = r.top - R.top - 2;
  const snap = !animate || !box.classList.contains("on") || Math.abs((+box.dataset.y || 0) - y) > r.height / 2 || reducedMotion.matches;
  box.classList.toggle("snap", snap);
  if (snap) void box.offsetWidth;
  Object.assign(box.style, { transform: `translate(${x}px, ${y}px)`, width: `${r.width + 6}px`, height: `${r.height + 4}px` });
  box.dataset.y = y; box.classList.add("on");
  if (snap) requestAnimationFrame(() => box.classList.remove("snap"));
}
/* ---------- Mitlesezeile: außerhalb der Textseite der gesprochene Satz über der Playbar ---------- */
const ml = { key: "" };
const mlOn = () => !!(st.doc && !st.doc.demo && markMode() !== "section"
  && (document.body.classList.contains("compact") || (view !== "read" && view !== "edit")));
function mlSync() {
  const W = st.words, on = mlOn() && !!W && W.idx === st.idx && W.doc === st.doc.id, was = $("ml")._on;
  slideBar($("ml"), on, null, true);                    // erst sichtbar, dann messen
  if (on && W.cur >= 0) mlShow(W.idx, W.list, W.cur, false, was);   // gerade erst eingeblendet → kein Satzwechsel obendrauf
}
/** Satz von Wort k (aus toks) zeigen; ghost = beim Ziehen geschätzt (Rahmen statt Markierung). */
function mlShow(i, toks, k, ghost, swapOk = true) {
  const tk = toks[k]; if (!tk) return;
  const win = $("mlWin"), key = `${st.doc.id}:${i}:${tk.sent}`, first = toks.findIndex((x) => x.sent === tk.sent);
  let row = win.querySelector(".ml-row:not(.gone)");
  const fresh = key !== ml.key || !row;
  if (fresh) {                                           // neuer Satz: alte Zeile hebt sich weg, neue steigt von unten nach
    ml.key = key;
    const old = row, swap = old && swapOk && !ghost && !reducedMotion.matches;
    row = document.createElement("div"); row.className = "ml-row";
    row.innerHTML = toks.filter((x) => x.sent === tk.sent).map((x) => `<span class="mw">${esc(x.text)}</span>`).join(" ");
    win.appendChild(row);
    if (swap) {
      old.classList.add("gone");
      old.animate([{ opacity: 1, translate: "0 0" }, { opacity: 0, translate: "0 -14px" }], { duration: 220, easing: EASE, fill: "forwards" })
        .finished.then(() => old.remove(), () => old.remove());
      row.animate([{ opacity: 0, translate: "0 14px" }, { opacity: 1, translate: "0 0" }], { duration: 420, delay: 120, easing: EASE_OUT, fill: "backwards" });
    } else win.querySelectorAll(".ml-row").forEach((r) => r !== row && r.remove());
  }
  const spans = row.querySelectorAll(".mw"), j = k - first, el = spans[j];
  for (let n = 0; n < spans.length; n++) spans[n].className = ghost ? "mw" : n < j ? "mw said" : n === j && markMode() === "word" ? "mw cur" : "mw";
  // Kurzer Satz mittig; langer rutscht so nach, dass das Wort bei ~40 % steht (nie über die Enden hinaus)
  // Ränder blenden aus (Maske 6 %) → Satzanfang/-ende nie in die Blende schieben, sonst steht das Wort „hinten“ im Nebel
  const Wn = win.clientWidth, rw = row.scrollWidth, x = el.offsetLeft + el.offsetWidth / 2, pad = Math.round(Wn * 0.07);
  row.classList.toggle("snap", fresh);
  row.style.transform = `translateX(${rw <= Wn - 2 * pad ? (Wn - rw) / 2 : -Math.max(-pad, Math.min(x - Wn * 0.4, rw - Wn + pad))}px)`;
  if (fresh) { void row.offsetWidth; row.classList.remove("snap"); }
  const word = markMode() === "word";
  boxIn(row, "mlBox", "wbox", !ghost && word ? el.getBoundingClientRect() : null, !fresh);
  boxIn(row, "mlGhost", "wghost", ghost && word ? el.getBoundingClientRect() : null);
}
/** Satz-Markierung: je Zeile EINE runde Fläche hinter dem Satz (statt Hintergrund je Wort) – jede Zeile hat runde
 *  Ecken, und zwischen den Zeilen bleibt Luft statt Überlappung. */
function placeSentBoxes(els, fresh = true) {
  const reader = $("reader");
  let layer = $("sboxes");
  if (!layer || !layer.isConnected) { layer = document.createElement("span"); layer.id = "sboxes"; layer.className = "sboxes"; layer.setAttribute("aria-hidden", "true"); reader.appendChild(layer); }
  if (!els.length || markMode() === "section") { layer.innerHTML = ""; return; }
  const R = reader.getBoundingClientRect(), lines = [];
  // je Zeilenstück messen: ein Wort mit Bindestrich („cross-section“) kann über zwei Zeilen umbrechen – sein
  // Gesamt-Rechteck wäre dann zwei Zeilen hoch und so breit wie die Spalte (doppelte Fläche, Tester-Rückmeldung 3.0.1)
  for (const el of els) for (const r of (el.firstElementChild || el).getClientRects()) {
    if (!r.width) continue;
    const ln = lines.find((l) => Math.abs(l.top - r.top) < r.height / 2);
    if (ln) { ln.left = Math.min(ln.left, r.left); ln.right = Math.max(ln.right, r.right); ln.bottom = Math.max(ln.bottom, r.bottom); }
    else lines.push({ top: r.top, left: r.left, right: r.right, bottom: r.bottom });
  }
  layer.innerHTML = lines.map((l) => `<i style="transform:translate(${l.left - R.left - 4}px,${l.top - R.top - 1}px);width:${l.right - l.left + 8}px;height:${l.bottom - l.top + 2}px"></i>`).join("");
  layer.classList.toggle("fresh", fresh && !reducedMotion.matches);
}
/** Markierungs-Box hinter das aktuelle Wort im Text. */
function placeWordBox(el, animate = true) {
  // umbrochenes Wort: nur das erste Zeilenstück markieren (sonst leuchtet kurz ein Block über zwei Zeilen)
  const r = markMode() === "word" && el?.firstElementChild ? [...el.firstElementChild.getClientRects()].find((x) => x.width) : null;
  boxIn($("reader"), "wbox", "wbox", r || null, animate);
}
function replaceMarks() {                  // Wort- und Satz-Box neu an den Text legen (ohne Gleiten)
  const W = st.words;
  if (!$("reader").offsetWidth) return;     // Textansicht ausgeblendet (z. B. Einstellungen): alle Maße 0 → nicht messen
  if (W && W.cur >= 0) placeWordBox(W.list[W.cur]?.el, false);
  if (W && W.curSent >= 0) placeSentBoxes(W.list.filter((x) => x.sent === W.curSent).map((x) => x.el), false);
  window.bmPlace?.();                       // Lesezeichen (3.0) mitwandern lassen
}
new ResizeObserver(replaceMarks).observe($("reader"));   // Umbruch geändert (Fenster, Seitenleiste, Schriftgröße)
// Lese-Schrift (Literata) kommt oft erst nach dem Setzen der Boxen: Die Wörter verschieben sich, der Leser bleibt aber
// gleich hoch (feste Zeilenhöhe) → kein ResizeObserver. Ohne das stehen Wort- und Satz-Box ein paar Pixel daneben.
document.fonts?.addEventListener("loadingdone", replaceMarks);
function keepVisible(el) {
  const box = $("readScroll").getBoundingClientRect(), r = el.getBoundingClientRect();
  if (r.top < box.top + box.height * 0.15 || r.bottom > box.bottom - box.height * 0.2) el.scrollIntoView({ block: "center", behavior: "smooth" });
}
function tick(once) {
  st.raf = 0;
  const W = st.words;
  if (W && W.timed && W.idx === st.idx && st.loadedIdx === st.idx) {
    const t = audio.currentTime;
    let k = Math.max(0, W.cur);
    if (W.list[k] && W.list[k].t > t) k = 0;
    while (k + 1 < W.list.length && W.list[k + 1].t <= t) k++;
    setWord(k);
  }
  if (once !== true && st.wantPlay && !audio.paused) st.raf = requestAnimationFrame(tick);
}
function startTick() { if (!st.raf) st.raf = requestAnimationFrame(tick); }

