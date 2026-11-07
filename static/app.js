"use strict";
/* Vorleser – Oberfläche */

const $ = (id) => document.getElementById(id);
const AHEAD_N = { low: 1, normal: 3, high: 10, all: 10 };   // so viele Abschnitte im Voraus erzeugen (Einstellung „ahead“)
const ahead = () => AHEAD_N[st.settings?.ahead] ?? 3;
const SAVE_EVERY_MS = 4000;
const audio = $("audio");
const pvAudio = $("previewAudio");

const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const nAbschn = (n) => `${n} Abschnitt${n === 1 ? "" : "e"}`;
const fmtMB = (b) => b >= 2 ** 30 ? `${(b / 2 ** 30).toFixed(1).replace(".", ",")} GB`
  : b >= 2 ** 20 || b <= 0 ? `${Math.max(0, Math.round(b / 2 ** 20))} MB` : `${Math.max(1, Math.round(b / 1024))} KB`;
const mmss = (t) => `${Math.floor(t / 60)}:${String(Math.floor(t % 60)).padStart(2, "0")}`;
const icon = (id, cls = "i", style = "") => `<svg class="${cls}" ${style ? `style="${style}"` : ""}><use href="#${id}"/></svg>`;

const api = async (path, opts = {}) => {
  const r = await fetch(path, { headers: { "Content-Type": "application/json" }, ...opts });
  if (!r.ok) throw new Error((await r.json().catch(() => ({}))).error || r.statusText);
  return r.json();
};

const st = {
  doc: null, idx: 0, pendingOffset: 0,
  cache: new Map(),              // idx -> {promise, url, used, fallback}
  loadedIdx: -1, wantPlay: false, token: 0, lastSave: 0, switching: false,
  voices: [], langs: {}, defaults: {}, features: {}, settings: null, docs: [],
  spans: [], readySet: new Set(), words: null, raf: 0,
  srvCached: new Set(),          // Abschnitte, die auf dem Server fertig im Cache liegen (eine Wahrheit für „vorbereitet“)
  newVoice: null, langManual: false,
};

/* ===================================================================== */
/* Farben & Theme                                                         */
/* ===================================================================== */
const PRESETS = [
  { name: "Pflaume", orig: "#5F0F40", light: "#7A1A55", dark: "#D77FB3" },
  { name: "Karmin", orig: "#9A031E", light: "#B0122C", dark: "#F07A85" },
  { name: "Orange", orig: "#FB8B24", light: "#AD5400", dark: "#FFA94D" },
  { name: "Rost", orig: "#E36414", light: "#C2410C", dark: "#F2895A" },
  { name: "Petrol", orig: "#0F4C5C", light: "#0F6A80", dark: "#5CC3D9" },
];
const SURFACE = { light: "#FFFFFF", anthrazit: "#25292D" };
const sysDark = window.matchMedia("(prefers-color-scheme: dark)");
const isDark = (s) => s.theme === "dark" || (s.theme === "system" && sysDark.matches);
const rgbOf = (h) => { const n = parseInt(String(h).replace("#", ""), 16) || 0; return [(n >> 16) & 255, (n >> 8) & 255, n & 255]; };
const hexOf = (c) => "#" + c.map((v) => Math.round(Math.max(0, Math.min(255, v))).toString(16).padStart(2, "0")).join("");
const lum = (h) => { const c = rgbOf(h).map((v) => { v /= 255; return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4; }); return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]; };
const contrast = (a, b) => { const x = lum(a), y = lum(b); return (Math.max(x, y) + 0.05) / (Math.min(x, y) + 0.05); };
const mix = (a, b, t) => { const A = rgbOf(a), B = rgbOf(b); return hexOf(A.map((v, i) => v + (B[i] - v) * t)); };
const readable = (c, bg) => { const to = lum(bg) < 0.2 ? "#FFFFFF" : "#000000"; let out = c; for (let i = 1; i <= 12 && contrast(out, bg) < 4.5; i++) out = mix(c, to, i * 0.07); return out; };
const rgba = (h, a) => { const c = rgbOf(h); return `rgba(${c[0]}, ${c[1]}, ${c[2]}, ${a})`; };

function presetOf(hex) { const u = String(hex).toUpperCase(); return PRESETS.find((p) => [p.orig, p.light, p.dark].includes(u)); }
function accentFor(hex, dark) { const p = presetOf(hex); return p ? (dark ? p.dark : p.light) : String(hex).toUpperCase(); }

function themeVars(s) {
  const dark = isDark(s);
  const key = dark ? "anthrazit" : "light";
  const acc = accentFor(s.accent, dark);
  const accText = readable(acc, SURFACE[key]);
  return {
    theme: key,
    vars: {
      "--acc": acc,
      "--on-acc": contrast("#FFFFFF", acc) >= contrast("#111111", acc) ? "#FFFFFF" : "#111111",
      "--acc-text": accText,
      "--tint": rgba(accText, dark ? 0.2 : 0.12),
      "--buf": rgba(accText, 0.32),
    },
  };
}
function applyTheme() {
  const t = themeVars(st.settings);
  const root = document.documentElement;
  root.dataset.theme = t.theme;
  for (const k in t.vars) root.style.setProperty(k, t.vars[k]);
  try { localStorage.setItem("vorleser.theme", JSON.stringify(t)); } catch {}
  const r = $("reader");
  r.classList.toggle("mark-section", markMode() === "section");
  syncDockIcon(t.vars["--acc"], t.vars["--on-acc"]);
}
/** Mac: Dock-Icon in der Akzentfarbe – dasselbe Zeichen wie das Logo oben links (Windows: festes Icon). */
let dockKey = "";
function syncDockIcon(acc, on) {
  if (acc + on === dockKey || !window.pywebview?.api?.set_icon) return;
  dockKey = acc + on;
  const c = document.createElement("canvas"); c.width = c.height = 512;
  const g = c.getContext("2d");
  g.fillStyle = acc; g.beginPath(); g.roundRect(50, 50, 412, 412, 92); g.fill();     // Raster wie macOS-Icons
  g.translate(256, 256); g.scale(15.85, 15.85); g.translate(-7.5, -8);
  g.strokeStyle = on; g.lineWidth = 1.8; g.lineCap = "round";
  g.stroke(new Path2D("M3 5v6M6 2.5v11M9 5v6M12 6.5v3"));                          // = Logo in index.html
  window.pywebview.api.set_icon(c.toDataURL("image/png")).catch(() => {});
}
window.addEventListener("pywebviewready", () => { if (st.settings) applyTheme(); });
async function saveSettings(patch) {
  Object.assign(st.settings, patch);                       // sofort anwenden …
  if ("uiLang" in patch) {
    setUiLang(patch.uiLang);
    renderLibrary(); renderDocOver(); updateStatus(); renderPlay(); updatePrep();
    requestAnimationFrame(() => { segThumbs(); moveInk(); });
  }
  if ("theme" in patch || "accent" in patch) withTransition(() => { applyTheme(); renderSettings(); });
  else { applyTheme(); renderSettings(); }
  try { st.settings = await api("/api/settings", { method: "PATCH", body: JSON.stringify(patch) }); }   // … dann speichern
  catch (e) { toastErr(e); }
}
let csPolling = false;          // läuft gerade die Installation der eigenen Stimme?
const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)");
let toastT = null;
function toast(msg, err = false) {
  const t = $("toast");
  t.textContent = msg; t.classList.toggle("err", err);
  t.classList.add("show");
  clearTimeout(toastT); toastT = setTimeout(() => t.classList.remove("show"), err ? 4500 : 2200);
}
function toastErr(e) { console.error(e); toast(friendlyError(e), true); }
function friendlyError(e) {
  const m = e?.message || String(e);
  return /Failed to fetch|NetworkError|Load failed/i.test(m) ? "Der Vorleser-Server antwortet nicht – läuft er noch?" : m;
}
/** Eigener Rückfrage-Dialog statt confirm(). Liefert Promise<boolean>. */
function ask({ title, text = "", ok = "OK", cancel = "Abbrechen", danger = false, icon: ico = danger ? "i-trash" : "i-check" }) {
  return new Promise((resolve) => {
    const d = $("confirmDlg");
    d.classList.toggle("danger", danger);
    $("cfIcon").innerHTML = icon(ico);
    $("cfTitle").textContent = title;
    $("cfText").textContent = text;
    $("cfText").classList.toggle("hidden", !text);
    $("cfOk").textContent = ok;
    $("cfCancel").textContent = cancel;
    $("cfOk").className = `btn ${danger ? "danger-fill" : "primary"}`;
    let answer = false;
    $("cfOk").onclick = () => { answer = true; d.close(); };
    $("cfCancel").onclick = () => d.close();
    d.addEventListener("close", () => resolve(answer), { once: true });
    d.showModal();
    (danger ? $("cfCancel") : $("cfOk")).focus();
  });
}
function fmtWhen(ts) {
  if (!ts) return "";
  const d = new Date(ts * 1000), now = new Date();
  const day = (x) => new Date(x.getFullYear(), x.getMonth(), x.getDate()).getTime();
  const diff = Math.round((day(now) - day(d)) / 86400000);
  if (diff === 0) return d.toLocaleTimeString(LOC(), { hour: "2-digit", minute: "2-digit" });
  if (diff === 1) return "Gestern";
  if (diff > 1 && diff < 7) return d.toLocaleDateString(LOC(), { weekday: "short" }).replace(".", "");
  return d.toLocaleDateString(LOC(), d.getFullYear() === now.getFullYear() ? { day: "numeric", month: "short" } : { day: "numeric", month: "short", year: "numeric" });
}
function withTransition(fn) {
  // Während des Onboardings keine View Transition: deren Standbild enthält kein backdrop-filter,
  // die Unschärfe hinter dem Dialog würde kurz verschwinden. Die Farben blenden dort per CSS über.
  const onbOpen = !$("onb").classList.contains("hidden");
  if (document.startViewTransition && !reducedMotion.matches && !onbOpen) document.startViewTransition(fn); else fn();
}
function animateIn(el, cls = "enter") {
  if (!el) return;
  el.classList.remove(cls); void el.offsetWidth; el.classList.add(cls);
  // Nur das eigene Animationsende zählt – Kinder (z. B. der Auswahlpunkt) würden sonst zu früh abbrechen.
  el.addEventListener("animationend", function done(e) {
    if (e.target !== el && el.getAnimations?.().length) return;
    el.classList.remove(cls); el.removeEventListener("animationend", done);
  });
}
const EASE = "cubic-bezier(.2, .8, .2, 1)", EASE_OUT = "cubic-bezier(.16, 1, .3, 1)";
/** Höhe vorher messen; die zurückgegebene Funktion nach der Änderung aufrufen → Höhe gleitet zum neuen Wert. */
function heightFrom(el) {
  const h0 = el.offsetHeight;
  return (dur = 420) => {
    if (!h0 || reducedMotion.matches || !el.animate) return;
    const h1 = el.offsetHeight; if (!h1 || Math.abs(h1 - h0) < 2) return;
    el._sh?.cancel();
    el.style.overflow = "hidden";
    const a = el._sh = el.animate([{ height: `${h0}px` }, { height: `${h1}px` }], { duration: dur, easing: EASE_OUT });
    a.onfinish = a.oncancel = () => { if (el._sh === a) el.style.overflow = ""; };
  };
}
function smoothHeight(el, fn) { const done = heightFrom(el); fn(); done(); }
/** Zeile gleitet nach links hinaus, dann klappt ihre Höhe zu (Einträge darunter rücken nach). */
function collapseOut(el) {
  if (!el || reducedMotion.matches || !el.animate) return Promise.resolve();
  const cs = getComputedStyle(el);
  const full = { height: `${el.offsetHeight}px`, paddingTop: cs.paddingTop, paddingBottom: cs.paddingBottom, borderTopWidth: cs.borderTopWidth, borderBottomWidth: cs.borderBottomWidth };
  const zero = { height: "0px", paddingTop: "0px", paddingBottom: "0px", borderTopWidth: "0px", borderBottomWidth: "0px" };
  el.style.overflow = "hidden"; el.style.pointerEvents = "none";
  return el.animate([
    { ...full, opacity: 1, transform: "none" },
    { ...full, opacity: 0, transform: "translateX(-24px)", offset: 0.45 },
    { ...zero, opacity: 0, transform: "translateX(-24px)" },
  ], { duration: 460, easing: EASE, fill: "forwards" }).finished.catch(() => {});
}

/* ===================================================================== */
/* Ansichten & Seitenleiste                                               */
/* ===================================================================== */
let view = "read";
const VIEWS = { read: "viewRead", new: "viewNew", settings: "viewSettings", edit: "viewEdit" };
function showView(name) {
  const changed = view !== name;
  view = name;
  for (const [k, id] of Object.entries(VIEWS)) $(id).classList.toggle("hidden", k !== name);
  if (changed) animateIn($(VIEWS[name]));
  hideTip();
  requestAnimationFrame(() => { segThumbs(); moveInk(); });
  $("settingsBtn").classList.toggle("active", name === "settings");
  setPlayer(!!st.doc && name !== "edit");
  const t = $("nowTitle"); t.disabled = name === "read";                 // auf der Textseite kein Link
  if (name === "read") delete t.dataset.tip; else t.dataset.tip = "Zum Text springen";
  mlSync();
  $("side").classList.remove("open");
  closePops();
  renderLibrary();
}
/** Player-Leiste fährt von unten herein bzw. hinaus; der Inhalt darüber wächst/schrumpft mit (negativer Rand). */
/** Leiste unten herein-/hinausschieben (Player, Mitlesezeile darüber). after: nach jeder Höhenänderung. */
function slideBar(el, on, after) {
  if (el._on === on) return;
  el._on = on;
  el._pa?.cancel(); el._pa = null;
  const vis = !el.classList.contains("hidden");
  if (on === vis || reducedMotion.matches || !el.animate) { el.classList.toggle("hidden", !on); return after?.(); }
  if (on) {
    el.classList.remove("hidden"); after?.();
    const h = el.offsetHeight;
    el._pa = el.animate([{ marginBottom: `${-h}px`, transform: "translateY(100%)", opacity: 0 },
      { marginBottom: "0px", transform: "none", opacity: 1 }], { duration: 520, easing: EASE_OUT });
  } else {
    const h = el.offsetHeight;
    const a = el._pa = el.animate([{ marginBottom: "0px", transform: "none", opacity: 1 },
      { marginBottom: `${-h}px`, transform: "translateY(100%)", opacity: 0 }], { duration: 280, easing: EASE, fill: "forwards" });
    a.onfinish = () => { el.classList.add("hidden"); a.cancel(); after?.(); };
  }
}
const setPlayer = (on) => slideBar($("player"), on, syncPlayerHeight);
document.querySelectorAll("[data-menu]").forEach((b) => (b.onclick = (e) => { e.stopPropagation(); $("side").classList.toggle("open"); }));
document.addEventListener("click", (e) => { if (!$("side").contains(e.target)) $("side").classList.remove("open"); });

async function refreshLibrary() {
  const { docs } = await api("/api/docs");
  st.docs = docs; renderLibrary();
  return docs;
}
function renderLibrary() {
  const showSearch = st.docs.length >= 7;                 // Suche erst, wenn es etwas zu suchen gibt
  $("libSearchBox").classList.toggle("hidden", !showSearch);
  if (!showSearch) $("libSearch").value = "";
  const q = $("libSearch").value.trim().toLowerCase();
  const ul = $("library");
  const docs = [...(st.demoEntry ? [st.demoEntry] : []), ...st.docs].filter((d) => !q || d.title.toLowerCase().includes(q));
  if (!docs.length) { ul.innerHTML = `<li class="empty">${q ? "Nichts gefunden." : "Noch keine Texte."}</li>`; return; }
  const ids = docs.map((d) => d.id), sig = ids.join();
  // Gestaffelt einblenden nur bei echtem Listenwechsel – nicht, wenn genau ein Text dazukommt oder wegfällt.
  const stagger = sig !== st.libSig && !oneChanged(st.libSig ? st.libSig.split(",") : [], ids); st.libSig = sig;
  // Neu angelegter Text „landet“ (Höhe wächst + Akzent leuchtet einmal auf). Läuft über Neuzeichnungen
  // hinweg weiter: negative Verzögerung = bereits vergangene Zeit.
  const ago = st.libLand ? performance.now() - st.libLand.t : Infinity;
  const land = ago < 1800 ? st.libLand.id : null;
  const prevPre = new Map([...ul.querySelectorAll("a[data-id]")].map((a) => [a.dataset.id, a.querySelector(".pre")?.style.width]));
  ul.innerHTML = docs.map((d, n) => {
    const pct = docPct(d), state = docState(d, pct);
    const active = view === "read" && st.doc?.id === d.id ? " active" : "";
    const ts = d.progress.updated || d.created;
    const full = new Date(ts * 1000).toLocaleString(LOC(), { dateStyle: "medium", timeStyle: "short" });
    const cls = d.id === land ? "landed" : stagger ? "enter" : "";
    return `<li class="${cls}" style="--i:${Math.min(n, 12)}${d.id === land ? `;--ago:${-Math.round(ago)}ms` : ""}"><a href="#" class="${active}" data-id="${d.id}">
        <span class="row1">${jobRing(d.id)}<span class="t" data-noi18n>${esc(d.title)}</span><span class="when" title="${d.progress.updated ? "Zuletzt gehört" : "Erstellt"}: ${full}">${fmtWhen(ts)}</span></span>
        <span class="m"><b>${esc(d.lang.toUpperCase())}</b>·<span>${d.chapters ? `${d.chapters} Kapitel` : nAbschn(d.count)}</span>·<span class="st">${state}</span></span>
        <span class="bar"><i class="pre" style="width:${d.count ? Math.round((d.prepared || 0) / d.count * 100) : 0}%"></i><i class="pos" style="width:${pct}%"></i></span></a>
      <button class="dots" data-dots="${d.id}" aria-label="Aktionen für ${esc(d.title)}" aria-haspopup="menu">${icon("i-dots", "i", "width:18px;height:18px")}</button></li>`;
  }).join("");
  const li = ul.querySelector("li.landed");
  if (li) li.style.setProperty("--lh", `${li.firstElementChild.offsetHeight}px`);
  // „Vorbereitet“-Balken gleitet vom alten zum neuen Stand (z. B. nach dem Löschen des Audios), statt zu springen
  for (const d of docs) {
    const from = prevPre.get(d.id), bar = ul.querySelector(`[data-id="${d.id}"] .pre`);
    if (from != null && bar && from !== bar.style.width && bar.animate && !reducedMotion.matches)
      bar.animate([{ width: from }, { width: bar.style.width }], { duration: 520, easing: EASE });
  }
}
/** Unterscheiden sich die Listen um genau einen Eintrag (einer dazu oder einer weg)? */
function oneChanged(a, b) {
  if (Math.abs(a.length - b.length) !== 1) return false;
  const [long, short] = a.length > b.length ? [a, b] : [b, a];
  return short.every((x) => long.includes(x));
}
// Hörfortschritt: EINE Rechnung für Player-Balken und Bibliothek – (Abschnitt + Anteil darin) / Abschnitte.
function docPct(d) {
  const n = d.count ?? d.chunks?.length ?? 0, p = d.progress || {};
  return n ? Math.min(100, ((p.chunk || 0) + (p.frac || 0)) / n * 100) : 0;
}
function docState(d, pct) {
  return !d.progress?.updated ? "neu" : pct >= 99.5 ? "fertig gehört" : `${Math.floor(pct)} %`;
}
// Laufenden Fortschritt in den Bibliothekseintrag spiegeln (ohne die Liste neu zu zeichnen).
function libSync() {
  if (!st.doc || st.doc.demo) return;
  const d = st.docs.find((x) => x.id === st.doc.id); if (!d) return;
  d.progress = { ...d.progress, ...st.doc.progress };
  const a = $("library").querySelector(`a[data-id="${st.doc.id}"]`); if (!a) return;
  const pct = docPct(d), state = docState(d, pct);
  a.querySelector(".pos").style.width = `${pct}%`;
  const s = a.querySelector(".st"); if (s.textContent !== state) s.textContent = state;
}
let libMenuFor = null;
$("library").onclick = async (e) => {
  const dots = e.target.closest("[data-dots]");
  if (dots) {
    e.preventDefault(); e.stopPropagation();
    const m = $("libMenu"), was = libMenuFor === dots.dataset.dots && !m.classList.contains("hidden") && !m.classList.contains("leaving");
    closePops(true);
    if (was) return;
    libMenuFor = dots.dataset.dots;
    dots.classList.add("open"); dots.closest("li").classList.add("menu-open");
    openPop(m);
    const r = dots.getBoundingClientRect();
    const below = r.bottom + 6 + m.offsetHeight < window.innerHeight - 8;
    m.style.left = `${Math.min(r.left, window.innerWidth - m.offsetWidth - 12)}px`;
    m.style.top = below ? `${r.bottom + 6}px` : `${r.top - 6 - m.offsetHeight}px`;
    m.style.setProperty("--origin", below ? "top left" : "bottom left");
    return;
  }
  const a = e.target.closest("a[data-id]");
  if (a) { e.preventDefault(); if (view === "edit" && edDirty() && !(await askDiscard())) return; openDoc(a.dataset.id); }
};
$("libMenu").onclick = async (e) => {
  const b = e.target.closest("[data-act]"); if (!b || !libMenuFor) return;
  const id = libMenuFor; closePops();
  if (b.dataset.act === "delete") return deleteDoc(id);
  if (view === "edit" && edDirty() && !(await askDiscard())) return;
  if (st.doc?.id !== id || view !== "read") await openDoc(id);
  if (b.dataset.act === "edit") openEditor();
  if (b.dataset.act === "export") $("exportBtn").click();
};
const askDiscard = () => ask({ title: "Änderungen verwerfen?", text: "Deine Änderungen am Text gehen verloren.", ok: "Verwerfen", danger: true, icon: "i-pen" });
$("libSearch").oninput = renderLibrary;
async function deleteDoc(id) {
  const d = st.docs.find((x) => x.id === id);
  const ok = await ask({ title: `„${d?.title || "Text"}“ löschen?`, ok: "Löschen", danger: true,
    text: "Der Text wird mit Lesezeichen und Hörbuch-Export endgültig entfernt. Das lässt sich nicht rückgängig machen." });
  if (!ok) return;
  await api(`/api/docs/${id}`, { method: "DELETE" });
  const cur = st.doc?.id === id;
  if (cur) stop();
  const li = $("library").querySelector(`a[data-id="${id}"]`)?.closest("li");
  st.docs = st.docs.filter((x) => x.id !== id);         // falls zwischendurch neu gezeichnet wird: bleibt weg
  await collapseOut(li);
  if (cur) { st.doc = null; showNew(); }
  await refreshLibrary();
  toast("Gelöscht");
}
$("settingsBtn").onclick = () => { showView("settings"); renderSettings(); };
sysDark.addEventListener("change", () => { if (st.settings?.theme === "system") { applyTheme(); renderSettings(); } });

function segThumbs(root = document) {
  root.querySelectorAll(".seg").forEach((seg) => {
    let th = seg.querySelector(":scope > .thumb");
    if (!th) { th = document.createElement("span"); th.className = "thumb"; seg.prepend(th); }
    const on = seg.querySelector(":scope > button.on");
    if (!on || !on.offsetWidth) { th.style.opacity = "0"; seg.classList.remove("has-thumb"); return; }
    const first = !seg.classList.contains("has-thumb");
    if (first) th.style.transition = "none";
    th.style.opacity = "1";
    th.style.width = `${on.offsetWidth}px`;
    th.style.transform = `translateX(${on.offsetLeft}px)`;
    seg.classList.add("has-thumb");
    if (first) requestAnimationFrame(() => (th.style.transition = ""));
  });
}
function moveInk() {
  const on = document.querySelector("#setTabs button.on"), ink = $("tabInk");
  if (!on || !on.offsetWidth) return;
  ink.style.width = `${on.offsetWidth}px`;
  ink.style.transform = `translateX(${on.offsetLeft}px)`;
}
window.addEventListener("resize", () => { segThumbs(); moveInk(); });

/* ---------- Tooltips ---------- */
const tipEl = $("tip");
let tipT = null, tipFor = null;
function showTip(el) {
  if (!el.isConnected || !el.dataset.tip) return;
  tipEl.textContent = el.dataset.tip;
  tipEl.classList.remove("show", "below");
  const r = el.getBoundingClientRect(), w = tipEl.offsetWidth, h = tipEl.offsetHeight;
  const below = r.top - h - 10 < 8;
  tipEl.classList.toggle("below", below);
  tipEl.style.left = `${Math.max(8, Math.min(window.innerWidth - w - 8, r.left + r.width / 2 - w / 2))}px`;
  tipEl.style.top = `${below ? r.bottom + 10 : r.top - h - 10}px`;
  requestAnimationFrame(() => tipEl.classList.add("show"));
}
function hideTip() { clearTimeout(tipT); tipFor = null; tipEl.classList.remove("show"); }
document.addEventListener("pointerover", (e) => {
  const el = e.target.closest("[data-tip]");
  if (el === tipFor) return;
  hideTip();
  if (!el || e.pointerType === "touch") return;
  tipFor = el;
  tipT = setTimeout(() => showTip(el), el.id === "prepBtn" ? 200 : 500);
});
document.addEventListener("focusin", (e) => { const el = e.target.closest?.("[data-tip]"); if (el && el.matches(":focus-visible")) { hideTip(); tipFor = el; tipT = setTimeout(() => showTip(el), 300); } });
document.addEventListener("focusout", hideTip);
document.addEventListener("pointerdown", hideTip);
document.addEventListener("scroll", hideTip, true);
document.documentElement.addEventListener("mouseleave", hideTip);

/* ===================================================================== */
/* Stimmen                                                                */
/* ===================================================================== */
const voiceById = (id) => st.voices.find((v) => v.id === id);
const langVoices = (lang) => st.voices.filter((v) => v.lang === lang);
const KIND = { edge: "Online", piper: "Offline", clone: "Eigene" };
function setVoicePill(av, lbl, id) {
  const v = voiceById(id);
  lbl.textContent = v ? v.name : "Stimme wählen";
  av.textContent = v ? v.name.slice(0, 1).toUpperCase() : "?";
}
async function reloadVoices() {
  const d = await api("/api/voices");
  st.voices = d.voices; st.langs = d.langs; st.defaults = d.defaults; st.features = d.features;
  for (const v of st.voices) if (v.engine === "clone") v.meta = v.warming ? "Wird vorbereitet … ca. 1 Min." : "Lädt länger · am besten vorab erzeugen";
  // Neue eigene Stimme lädt noch (Modell + erste Hörprobe): nachfragen, bis sie bereit ist
  const warm = new Set(st.voices.filter((v) => v.warming).map((v) => v.id));
  for (const id of st.warmIds || []) if (!warm.has(id)) st.voiceReady = { id, t: performance.now() };   // eben fertig geworden
  st.warmIds = warm;
  clearTimeout(st.warmT);
  if (warm.size) st.warmT = setTimeout(() => reloadVoices().then(() => { if (setTab === "voices") renderVoiceLib(); }).catch(() => {}), 3000);
}

/* ---------- Stimmen-Panel ---------- */
const vp = { lang: "de", langs: [], current: null, onPick: null, showAll: false, anchor: null, doc: null, prep: null };
async function openVoicePanel(anchor, { langs, lang, current, onPick, doc = null }) {
  closePops(true);
  Object.assign(vp, { langs, lang, current, onPick, showAll: false, anchor, doc, prep: null });
  if (doc) {          // Stand je Stimme vorher holen (lokal, Millisekunden) – sonst springt die Höhe des Menüs
    const ids = langVoices(lang).map((v) => v.id);
    const got = api(`/api/docs/${doc}/prepared?voices=${encodeURIComponent(ids.join(","))}`).then((r) => { if (vp.doc === doc) vp.prep = r; }).catch(() => {});
    await Promise.race([got, sleep(300)]);
    if (vp.anchor !== anchor) return;
  }
  const p = $("voicePanel");
  openPop(p);
  renderVoicePanel();
  placePop(p, anchor);
}
function placePop(p, anchor) {
  const r = anchor.getBoundingClientRect(), w = p.offsetWidth, h = p.offsetHeight;
  const left = Math.max(12, Math.min(window.innerWidth - w - 12, r.right - w));
  const below = r.bottom + 8 + h < window.innerHeight - 8;
  p.style.left = `${left}px`;
  p.style.top = below ? `${r.bottom + 8}px` : `${Math.max(12, r.top - 8 - h)}px`;
  p.style.setProperty("--origin", below ? "top right" : "bottom right");
}
const isFav = (id) => (st.settings?.favorites || []).includes(id);
function renderVoicePanel() {
  $("vpLang").classList.toggle("hidden", vp.langs.length < 2);
  $("vpLang").innerHTML = vp.langs.map((l) => `<button data-lang="${l}" class="${l === vp.lang ? "on" : ""}">${esc(st.langs[l] || l)}</button>`).join("");
  const list = langVoices(vp.lang);
  const row = (v) => {
    const on = v.id === vp.current;
    return `<div class="vrow${on ? " on" : ""}">
      <button class="pick" data-id="${esc(v.id)}"><span class="avl">${esc(v.name.slice(0, 1).toUpperCase())}</span>
        <span class="nm"><b data-noi18n>${esc(v.name)}</b><small>${esc(v.meta || "")}</small>${vp.doc ? vpPrepHTML(v) : ""}</span>
        ${on ? icon("i-check", "i check") : ""}</button>
      <button class="prev${v.warming ? " loading" : ""}" data-prev="${esc(v.id)}" aria-label="Hörprobe ${esc(v.name)}">${icon("i-play", "i fill", "width:14px;height:14px")}</button></div>`;
  };
  const favs = list.filter((v) => v.engine !== "clone" && isFav(v.id));
  const own = list.filter((v) => v.engine === "clone");
  const cur = list.find((v) => v.id === vp.current && !isFav(v.id) && v.engine !== "clone");
  let html = "";
  if (cur) html += `<div class="grp"><span>Aktuell</span></div>${row(cur)}`;
  html += `<div class="grp"><span>★ Favoriten</span></div>`;
  html += favs.length ? favs.map(row).join("") : `<div class="vp-empty">Noch keine Favoriten für ${esc(st.langs[vp.lang] || vp.lang)}. Markiere Stimmen in der Bibliothek mit ★.</div>`;
  if (own.length) html += `<div class="grp"><span>Eigene Stimme</span><span>lokal</span></div>${own.map(row).join("")}`;
  $("vpBody").innerHTML = html;
  segThumbs($("voicePanel"));
}
/* „Für diesen Text schon erzeugt“ je Stimme (nur im Stimmen-Menü des Players) */
function vpPrepCount(id) {
  if (st.doc?.id === vp.doc && id === st.doc.voice) return st.readySet?.size ?? 0;   // aktuelle Stimme: dieselbe Quelle wie die Playbar
  return vp.prep?.voices[id];
}
function vpPrepHTML(v) {
  const total = vp.prep?.total || st.doc?.chunks.length || 0, n = vpPrepCount(v.id);
  if (n == null || !total) return "";
  if (!n && v.engine !== "clone") return "";                            // Online-Stimmen sind ohnehin schnell
  const pct = Math.round((n / total) * 100);
  const txt = n >= total ? "Für diesen Text fertig erzeugt" : n ? `Für diesen Text ${pct} % erzeugt` : "Für diesen Text noch nicht erzeugt";
  return `<span class="vprep${n >= total ? " full" : ""}" data-vprep="${esc(v.id)}"><span class="vbar"><i style="width:${pct}%"></i></span><em>${txt}</em></span>`;
}
$("vpLang").onclick = (e) => { const b = e.target.closest("[data-lang]"); if (b) { vp.lang = b.dataset.lang; vp.showAll = false; renderVoicePanel(); } };
$("vpBody").onclick = (e) => {
  const pv = e.target.closest("[data-prev]");
  if (pv) return previewVoice(pv.dataset.prev, vp.lang, pv);
  const pick = e.target.closest("[data-id]");
  if (pick) { vp.current = pick.dataset.id; const cb = vp.onPick; closePops(); cb?.(pick.dataset.id, vp.lang); }
};
$("vpClose").onclick = closePops;
$("vpLib").onclick = () => { closePops(); openSettingsTab("voices", vp.lang); };

let pvBtn = null;
function previewVoice(id, lang, btn) {
  if (pvBtn) pvBtn.classList.remove("playing", "loading");
  if (pvBtn === btn && !pvAudio.paused) { pvAudio.pause(); pvBtn = null; return; }
  pvBtn = btn; btn.classList.add("loading");
  pvAudio.src = `/api/voices/preview?voice=${encodeURIComponent(id)}&lang=${encodeURIComponent(lang)}`;
  pvAudio.play().catch(() => btn.classList.remove("loading"));
}
pvAudio.onplaying = () => { pvBtn?.classList.remove("loading"); pvBtn?.classList.add("playing"); };
pvAudio.onended = pvAudio.onerror = () => { pvBtn?.classList.remove("playing", "loading"); pvBtn = null; };

const popTimers = {};
function closePops(instant = false) {
  document.querySelectorAll(".lib .dots.open").forEach((b) => { b.classList.remove("open"); b.closest("li")?.classList.remove("menu-open"); });
  for (const id of ["voicePanel", "chapterMenu", "moreMenu", "libMenu"]) {
    const el = $(id);
    if (el.classList.contains("hidden")) continue;
    if (instant || reducedMotion.matches) { el.classList.add("hidden"); continue; }
    el.classList.add("leaving");
    clearTimeout(popTimers[id]);
    popTimers[id] = setTimeout(() => { el.classList.add("hidden"); el.classList.remove("leaving"); }, 140);
  }
}
function openPop(el) {
  clearTimeout(popTimers[el.id]);
  el.classList.remove("leaving", "hidden");
}
document.addEventListener("mousedown", (e) => {
  if (!e.target.closest(".pop") && !e.target.closest("#voiceBtn, #newVoiceBtn, #chapterBtn, #moreBtn, [data-dots]")) closePops();
});
document.addEventListener("keydown", (e) => { if (e.key === "Escape") closePops(); });
window.addEventListener("resize", closePops);

/* ===================================================================== */
/* Neuer Text                                                             */
/* ===================================================================== */
function showNew() {
  showView("new");                                        // Wiedergabe läuft weiter – der Player bleibt unten
  fillLangSelect();
  if (!st.newVoice || voiceById(st.newVoice)?.lang !== $("newLang").value) st.newVoice = st.defaults[$("newLang").value];
  setVoicePill($("newVoiceAv"), $("newVoiceLbl"), st.newVoice);
  updateCount();
}
$("newBtn").onclick = () => { showNew(); setSrc("paste"); $("text").focus(); };

function fillLangSelect() {
  const sel = $("newLang"), cur = sel.value;
  sel.innerHTML = Object.entries(st.langs).filter(([k]) => langVoices(k).length).map(([k, n]) => `<option value="${k}">${esc(n)}</option>`).join("");
  if (cur && [...sel.options].some((o) => o.value === cur)) sel.value = cur;
}
function setSrc(src) {
  document.querySelectorAll("[data-src]").forEach((b) => b.classList.toggle("on", b.dataset.src === src));
  $("srcPaste").classList.toggle("hidden", src !== "paste");
  $("srcFile").classList.toggle("hidden", src !== "file");
  $("srcDict").classList.toggle("hidden", src !== "dict");
  segThumbs($("viewNew"));
  animateIn($({ paste: "srcPaste", file: "srcFile", dict: "srcDict" }[src]), "enter");
}
document.querySelectorAll("[data-src]").forEach((b) => (b.onclick = () => setSrc(b.dataset.src)));

function setNewLang(lang, auto) {
  $("newLang").value = lang;
  st.newVoice = st.defaults[lang];
  setVoicePill($("newVoiceAv"), $("newVoiceLbl"), st.newVoice);
  showHint(auto);
}
/** „erkannt“-Chip: springt beim Erscheinen einmal kurz auf. */
function showHint(on) {
  const h = $("langHint"), was = !h.classList.contains("hidden");
  h.classList.toggle("hidden", !on);
  if (on && !was) animateIn(h, "popin");
}
function updateCount() {
  const t = $("text").value;
  const n = t.trim().length;
  const chapters = (t.match(/^\s{0,3}#{1,4}\s+\S/gm) || []).length;
  $("charCount").textContent = n ? `${chapters ? `${chapters} Kapitel · ` : ""}${fmtNum(n)} Zeichen` : "";
  $("createBtn").disabled = n === 0;
}
let detectTimer = null;
$("text").oninput = () => {
  updateCount();
  if (!$("text").value.trim()) { st.langManual = false; $("langHint").classList.add("hidden"); return; }
  if (st.langManual) return;
  clearTimeout(detectTimer);
  detectTimer = setTimeout(async () => {
    const { lang } = await api("/api/detect", { method: "POST", body: JSON.stringify({ text: $("text").value.slice(0, 8000) }) });
    if (!st.langManual && $("text").value.trim() && lang !== $("newLang").value) setNewLang(lang, true);
    else if (!st.langManual) showHint(true);
  }, 400);
};
$("newLang").onchange = () => { st.langManual = true; setNewLang($("newLang").value, false); };
$("newVoiceBtn").onclick = (e) => {
  e.stopPropagation();
  const langs = Object.keys(st.langs).filter((l) => langVoices(l).length);
  openVoicePanel($("newVoiceBtn"), {
    langs, lang: $("newLang").value, current: st.newVoice,
    onPick: (id, lang) => {
      if (lang !== $("newLang").value) { st.langManual = true; $("newLang").value = lang; $("langHint").classList.add("hidden"); }
      st.newVoice = id; setVoicePill($("newVoiceAv"), $("newVoiceLbl"), id);
    },
  });
};

async function importFile(f) {
  setSrc("file");
  $("fileStatus").innerHTML = `<span class="spin" style="display:inline-block;vertical-align:-2px"></span> Lese ${esc(f.name)} …`;
  try {
    const r = await fetch("/api/import", { method: "POST", body: f, headers: { "X-Filename": encodeURIComponent(f.name) } });
    const d = await r.json();
    if (!r.ok) throw new Error(d.error || r.statusText);
    $("text").value = d.text;
    $("title").value = d.title || f.name.replace(/\.[^.]+$/, "");
    st.langManual = false;
    setNewLang(d.lang, true);
    $("fileStatus").textContent = "";
    setSrc("paste"); updateCount();
  } catch (err) { $("fileStatus").textContent = `Import fehlgeschlagen: ${err.message}`; }
}
$("pickFile").onclick = $("pickFile2").onclick = () => $("file").click();
$("file").onchange = (e) => { const f = e.target.files[0]; if (f) importFile(f); e.target.value = ""; };
const wrap = $("newWrap");
wrap.addEventListener("dragover", (e) => { e.preventDefault(); $("srcFile").classList.add("drop-on"); $("srcPaste").classList.add("drop-on"); });
wrap.addEventListener("dragleave", (e) => { if (!wrap.contains(e.relatedTarget)) { $("srcFile").classList.remove("drop-on"); $("srcPaste").classList.remove("drop-on"); } });
wrap.addEventListener("drop", (e) => {
  e.preventDefault(); $("srcFile").classList.remove("drop-on"); $("srcPaste").classList.remove("drop-on");
  const f = e.dataTransfer.files[0]; if (!f) return;
  importFile(f);
  animateIn($("srcFile").querySelector("svg"), "plop");   // Datei-Symbol „plumpst“ einmal in die Fläche
});

$("createBtn").onclick = async () => {
  $("createBtn").disabled = true;
  try {
    const lang = $("newLang").value;
    const d = await api("/api/docs", { method: "POST", body: JSON.stringify({
      title: $("title").value, text: $("text").value, lang, voice: st.newVoice || st.defaults[lang] }) });
    $("title").value = ""; $("text").value = ""; st.langManual = false; $("langHint").classList.add("hidden"); updateCount();
    st.libLand = { id: d.id, t: performance.now() };
    await refreshLibrary();
    openDoc(d.id);
  } catch (err) { toastErr(err); $("createBtn").disabled = false; }
};

/* ---------- Mikrofon / Diktat ---------- */
let micStream = null;
async function getMic() {
  if (micStream && micStream.active) return micStream;
  micStream = await navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true } });
  return micStream;
}
function releaseMic() { micStream?.getTracks().forEach((t) => t.stop()); micStream = null; }
function startRecorder(stream) {
  const mime = ["audio/webm;codecs=opus", "audio/mp4", "audio/ogg;codecs=opus"].find((m) => MediaRecorder.isTypeSupported(m));
  const rec = new MediaRecorder(stream, mime ? { mimeType: mime } : {});
  const parts = [];
  rec.ondataavailable = (e) => e.data.size && parts.push(e.data);
  const done = new Promise((res) => (rec.onstop = () => res(new Blob(parts, { type: rec.mimeType }))));
  const t0 = Date.now();
  rec.start(1000);
  return { stop: () => { rec.stop(); return done; }, secs: () => (Date.now() - t0) / 1000 };
}
let dict = null;
$("dictBtn").onclick = async () => {
  const btn = $("dictBtn");
  if (!dict) {
    try { dict = startRecorder(await getMic()); } catch (e) { return alert("Mikrofon nicht verfügbar: " + e.message); }
    btn.classList.add("on"); btn.setAttribute("aria-label", "Diktat beenden");
    $("dictHint").textContent = "Aufnahme läuft – nochmal tippen zum Beenden.";
    dict.timer = setInterval(() => ($("dictTime").textContent = mmss(dict.secs())), 250);
    return;
  }
  clearInterval(dict.timer);
  const blob = await dict.stop(); dict = null; releaseMic();
  btn.classList.remove("on"); btn.disabled = true; btn.setAttribute("aria-label", "Diktat starten");
  $("dictHint").textContent = "Wandle in Text um … (beim ersten Mal wird das Sprachmodell geladen)";
  try {
    const headers = st.langManual ? { "X-Lang": $("newLang").value } : {};
    const r = await fetch("/api/transcribe", { method: "POST", body: blob, headers });
    const d = await r.json();
    if (!r.ok) throw new Error(d.error);
    const ta = $("text");
    ta.value = (ta.value.trim() ? ta.value.trimEnd() + "\n\n" : "") + d.text;
    if (!st.langManual && st.langs[d.lang]) setNewLang(d.lang, true);
    updateCount(); setSrc("paste");
    $("dictHint").textContent = "Tippen und losreden. Längere Pausen werden zu Absätzen. Läuft lokal mit Whisper.";
  } catch (e) { $("dictHint").textContent = "Diktat fehlgeschlagen: " + e.message; }
  finally { btn.disabled = false; $("dictTime").textContent = "0:00"; }
};

/* ===================================================================== */
/* Dokument öffnen & darstellen                                           */
/* ===================================================================== */
async function openDoc(id) {
  if (st.doc && st.doc.id !== id) { if (st.wantPlay) pause(); else saveProgress(true); }
  stop();
  showDoc(await api(`/api/docs/${id}`));
}
/** Text anzeigen (vom Server geladen oder der Beispieltext des Rundgangs). */
function showDoc(doc) {
  st.doc = doc; st.idx = doc.progress.chunk; st.pendingOffset = doc.progress.offset || 0;
  st.pendingFrac = !doc.progress.offset && doc.progress.frac > 0 && doc.progress.frac < 1 ? doc.progress.frac : null; st.words = null; st.srvCached = new Set();
  showView("read");
  $("docTitle").textContent = doc.title;
  $("nowTitle").textContent = doc.title;
  renderDocOver();
  setVoicePill($("voiceAv"), $("voiceLbl"), doc.voice);
  $("chapterBtn").classList.toggle("hidden", !doc.chapters.length);
  $("posR").textContent = `von ${doc.chunks.length}`;
  $("ticks").innerHTML = doc.chapters.filter((c) => c.chunk > 0).map((c) => `<span class="tick" style="left:${(c.chunk / doc.chunks.length) * 100}%"></span>`).join("");

  const box = $("docText"); box.innerHTML = "";
  const frag = document.createDocumentFragment();
  let p = null;
  st.spans = doc.chunks.map((c, i) => {
    let s;
    if (c.h) { s = document.createElement("h2"); frag.appendChild(s); p = null; }
    else {
      if (c.par || !p) { p = document.createElement("p"); frag.appendChild(p); }
      else p.appendChild(document.createTextNode(" "));
      s = document.createElement("span"); p.appendChild(s);
    }
    s.className = "chunk"; s.textContent = c.text; s.dataset.i = i;
    return s;
  });
  box.appendChild(frag);
  st.readySet = new Set();
  st.lastError = null;
  animateIn($("reader"));
  renderLibrary();
  highlight(true);
  prefetch();
  updateStatus(); updatePrep(); updateMediaSession();
}
$("docText").onclick = (e) => { const s = e.target.closest(".chunk"); if (s) jumpTo(+s.dataset.i, 0, true); };
function renderDocOver() {
  const doc = st.doc; if (!doc) return;
  const chars = doc.chunks.reduce((s, c) => s + c.text.length, 0);
  $("docOver").textContent = [doc.chapters.length ? `${doc.chapters.length} Kapitel` : nAbschn(doc.chunks.length),
    `ca. ${fmtDuration(chars / 15)} Hördauer`,
    doc.progress.updated ? `zuletzt gehört ${new Date(doc.progress.updated * 1000).toLocaleDateString(LOC())}` : ""].filter(Boolean).join(" · ");
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
    const entry = { url: null, used: null, fallback: false };
    entry.promise = fetch(`/api/docs/${docId}/audio/${i}?v=${encodeURIComponent(voice)}`)
      .then(async (r) => {
        if (!r.ok) throw new Error((await r.json().catch(() => ({}))).error || "Synthese fehlgeschlagen");
        entry.used = r.headers.get("X-Voice-Used") || voice;
        entry.fallback = entry.used !== voice;
        return r.blob();
      })
      .then((b) => { entry.url = URL.createObjectURL(b); if (st.doc?.id === docId) st.srvCached.add(i); markReady(); return entry.url; })
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
  try { url = await getAudio(i); }
  catch (e) { if (my === st.token) failPlay(friendlyError(e), () => playFrom(i, offset)); return; }
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
  if (st.idx < st.doc.chunks.length - 1) playFrom(st.idx + 1);
  else { st.wantPlay = false; setPlayIcon(false); saveProgress(true, 0, 1); setStatus("Fertig gehört"); updateBar(); refreshLibrary(); }
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
  placeWordBox(null);
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
  setWord(0, false);
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
function setWord(k, scroll = true) {
  const W = st.words; if (!W || k === W.cur) return;
  const old = W.list[W.cur]; if (old) old.el.classList.remove("wc");
  const nw = W.list[k];
  const s = nw ? nw.sent : -1;
  if (s !== W.curSent) {
    const inS = W.list.filter((x) => x.sent === s);
    for (const x of W.list) { x.el.classList.toggle("ws", x.sent === s); x.el.classList.remove("wf", "wl"); }
    inS[0]?.el.classList.add("wf"); inS.at(-1)?.el.classList.add("wl");
    W.curSent = s;
  }
  if (nw && markMode() === "word") nw.el.classList.add("wc");
  placeWordBox(nw?.el, W.cur >= 0);
  W.cur = k;
  if (!scrub.drag) mlSync();
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
const mlOn = () => !!(st.doc && !st.doc.demo && view !== "read" && view !== "edit" && markMode() !== "section");
function mlSync() {
  const W = st.words, on = mlOn() && !!W && W.idx === st.idx && W.doc === st.doc.id;
  slideBar($("ml"), on);                                // erst sichtbar, dann messen
  if (on && W.cur >= 0) mlShow(W.idx, W.list, W.cur, false);
}
/** Satz von Wort k (aus toks) zeigen; ghost = beim Ziehen geschätzt (Rahmen statt Markierung). */
function mlShow(i, toks, k, ghost) {
  const tk = toks[k]; if (!tk) return;
  const win = $("mlWin"), key = `${st.doc.id}:${i}:${tk.sent}`, first = toks.findIndex((x) => x.sent === tk.sent);
  let row = win.querySelector(".ml-row:not(.gone)");
  const fresh = key !== ml.key || !row;
  if (fresh) {                                           // neuer Satz: alte Zeile hebt sich weg, neue steigt von unten nach
    ml.key = key;
    const old = row, swap = old && !ghost && !reducedMotion.matches && !$("ml").classList.contains("hidden");
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
  const Wn = win.clientWidth, rw = row.scrollWidth, x = el.offsetLeft + el.offsetWidth / 2;
  row.classList.toggle("snap", fresh);
  row.style.transform = `translateX(${rw <= Wn ? (Wn - rw) / 2 : -Math.max(0, Math.min(x - Wn * 0.4, rw - Wn))}px)`;
  if (fresh) { void row.offsetWidth; row.classList.remove("snap"); }
  const word = markMode() === "word";
  boxIn(row, "mlBox", "wbox", !ghost && word ? el.getBoundingClientRect() : null, !fresh);
  boxIn(row, "mlGhost", "wghost", ghost && word ? el.getBoundingClientRect() : null);
}
/** Markierungs-Box hinter das aktuelle Wort im Text. */
function placeWordBox(el, animate = true) {
  boxIn($("reader"), "wbox", "wbox", markMode() === "word" ? el?.firstElementChild?.getBoundingClientRect() : null, animate);
}
new ResizeObserver(() => {                 // Umbruch geändert (Fenster, Seitenleiste, Schrift) → Box nachziehen
  const W = st.words;
  if (W && W.cur >= 0) placeWordBox(W.list[W.cur]?.el, false);
}).observe($("reader"));
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
}
/** Seitenleisten-Fuß so hoch wie der Player – die Trennlinien liegen auf einer Höhe. */
function syncPlayerHeight() {
  const p = $("player"), visible = !p.classList.contains("hidden");
  document.body.classList.toggle("has-player", visible);
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
  if (!scrub.down) return;
  const t = scrub.target, dragged = scrub.drag;
  scrub.down = null; scrub.drag = false;
  if (t.tick) { t.tick.classList.remove("hit"); void t.tick.offsetWidth; t.tick.classList.add("hit"); }
  if (!dragged) glideBar();
  jumpTo(t.i, 0, st.wantPlay, t.frac);
  if (e.pointerType !== "mouse") scrubHide(); else { $("prog").classList.remove("dragging"); scrubShow(scrubTarget(e), false); }
});
$("prog").addEventListener("pointercancel", () => { scrub.down = null; scrub.drag = false; scrubHide(); updateBar(); });
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
        if (r.ok) toast("Gespeichert"); else if (!r.cancelled) toast(r.error || "Speichern fehlgeschlagen", true);
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

/* ===================================================================== */
/* Eigene Stimme anlegen                                                  */
/* ===================================================================== */
const CLONE_TEXT = {
  de: "Es war ein klarer Morgen am Meer. Der alte Leuchtturmwärter öffnete das Fenster, atmete tief durch und lauschte dem Rauschen der Wellen. Irgendwo kreischte eine Möwe. Er lächelte, denn heute würde endlich das Schiff mit den Briefen kommen. Wie lange hatte er darauf gewartet? Wochen, vielleicht Monate. Doch nun war es so weit.",
  en: "It was a clear morning by the sea. The old lighthouse keeper opened the window, took a deep breath and listened to the sound of the waves. Somewhere a seagull cried. He smiled, because today the ship with the letters would finally arrive. How long had he been waiting? Weeks, perhaps months. But now the time had come.",
};
let cloneCb = null, cTake = null;
function setCloneText(lang) {
  lang = CLONE_TEXT[lang] ? lang : "de";
  $("cText").textContent = CLONE_TEXT[lang];
  document.querySelectorAll("#cLang [data-cl]").forEach((b) => b.classList.toggle("on", b.dataset.cl === lang));
}
$("cLang").onclick = (e) => { const b = e.target.closest("[data-cl]"); if (b) { setCloneText(b.dataset.cl); animateIn($("cText"), "swap"); } };
function openClone(cb, lang) {
  cloneCb = cb;
  setCloneText(lang || UI_LANG);                       // Standard: Sprache der Oberfläche; Umschalter im Dialog
  $("cName").value = "";                                  // Name nur als Vorschlag (Platzhalter) – Tippen ersetzt ihn
  $("cName").placeholder = UI_LANG === "en" ? "My voice" : "Meine Stimme";
  $("cMsg").textContent = "";
  $("cloneDlg").showModal();
}
async function uploadClone(blob) {
  $("cMsg").textContent = "Stimme wird angelegt …";
  try {
    const r = await fetch("/api/clones", { method: "POST", body: blob, headers: { "X-Name": encodeURIComponent($("cName").value.trim() || $("cName").placeholder), "X-Lang": UI_LANG } });
    const d = await r.json();
    if (!r.ok) throw new Error(d.error);
    st.voiceLand = { id: d.id, t: performance.now() };
    await reloadVoices();
    $("cloneDlg").close();
    renderSettings();
    cloneCb?.(d.id);
  } catch (e) { $("cMsg").textContent = e.message; }
}
function resetCloneRec() {
  if (cTake) { clearInterval(cTake.timer); cTake.stop(); cTake = null; releaseMic(); }
  $("cRec").classList.remove("on");
  $("cRec").innerHTML = `${icon("i-mic", "i", "width:16px;height:16px")}Aufnehmen`;
}
$("cRec").onclick = async () => {
  if (!cTake) {
    try { cTake = startRecorder(await getMic()); } catch (e) { return ($("cMsg").textContent = "Mikrofon nicht verfügbar: " + e.message); }
    $("cRec").classList.add("on");
    cTake.timer = setInterval(() => {
      const t = cTake.secs();
      $("cRec").textContent = `Fertig · ${mmss(t)}`;
      $("cMsg").textContent = t < 12 ? "Weiterlesen …" : "Reicht – stoppen, wenn du magst";
      if (t >= 40) $("cRec").onclick();
    }, 250);
    return;
  }
  const t = cTake; cTake = null; clearInterval(t.timer);
  const blob = await t.stop(); releaseMic(); resetCloneRec();
  uploadClone(blob);
};
$("cFile").onchange = (e) => { const f = e.target.files[0]; if (f) uploadClone(f); e.target.value = ""; };
$("cClose").onclick = () => $("cloneDlg").close();
$("cloneDlg").addEventListener("close", resetCloneRec);

/* ===================================================================== */
/* Einstellungen                                                          */
/* ===================================================================== */
let setTab = "look";
$("setTabs").onclick = (e) => {
  const b = e.target.closest("[data-tab]"); if (!b) return;
  setTab = b.dataset.tab;
  document.querySelectorAll("#setTabs [data-tab]").forEach((x) => x.classList.toggle("on", x === b));
  const TABS = { look: "tabLook", play: "tabPlay", voices: "tabVoices", storage: "tabStorage", app: "tabApp" };
  for (const [k, id] of Object.entries(TABS)) $(id).classList.toggle("hidden", k !== setTab);
  animateIn($(TABS[setTab]));
  moveInk();
  renderSettings();
};
function openSettingsTab(tab, lang) {
  if (lang) libLang = lang;
  showView("settings");
  document.querySelector(`#setTabs [data-tab="${tab}"]`)?.click();
}
const MARK_HINT = {
  section: "Der ganze Abschnitt (2–3 Sätze) wird hinterlegt.",
  sentence: "Der gerade gesprochene Satz wird hinterlegt.",
  word: "Satz hinterlegt, das gesprochene Wort hervorgehoben. Mit Online-Stimmen exakt, bei Offline- und eigener Stimme aus dem Audio bestimmt.",
};
function renderSettings() {
  const s = st.settings; if (!s) return;
  const dark = isDark(s);
  // Darstellung
  document.querySelectorAll("#modeSeg [data-mode]").forEach((b) => b.classList.toggle("on", b.dataset.mode === s.theme));
  document.querySelectorAll("#uiSeg [data-ui]").forEach((b) => b.classList.toggle("on", b.dataset.ui === (s.uiLang || "de")));
  const preset = presetOf(s.accent);
  const ownCol = preset ? null : accentFor(s.accent, dark);
  $("swatches").innerHTML = PRESETS.map((p) => {
    const col = dark ? p.dark : p.light, on = preset === p;
    const ink = contrast("#FFFFFF", col) >= contrast("#111111", col) ? "#FFFFFF" : "#111111";
    return `<button class="sw${on ? " on" : ""}" data-acc="${p.light}" aria-label="Akzentfarbe ${p.name}" aria-pressed="${on}" title="${p.name}" style="background:${col}">${on ? `<svg class="i" style="stroke:${ink}"><use href="#i-check"/></svg>` : ""}</button>`;
  }).join("") +
    `<label class="sw own${ownCol ? " set on" : ""}" title="Eigene Farbe${ownCol ? ` (${esc(s.accent)})` : ""}" style="${ownCol ? `--own:${ownCol}` : ""}">
      <input type="color" id="accPick" value="${s.accent.toLowerCase()}" aria-label="Eigene Farbe wählen">
      ${ownCol ? `<svg class="i" style="stroke:${contrast("#FFFFFF", ownCol) >= contrast("#111111", ownCol) ? "#FFFFFF" : "#111111"}"><use href="#i-check"/></svg>` : `<span class="plus"><svg class="i"><use href="#i-plus"/></svg></span>`}
    </label>`;
  $("accPick").oninput = (e) => { st.settings.accent = e.target.value.toUpperCase(); applyTheme(); };
  $("accPick").onchange = (e) => saveSettings({ accent: e.target.value.toUpperCase() });
  document.querySelectorAll("#markSeg [data-mark]").forEach((b) => b.classList.toggle("on", b.dataset.mark === s.mark));
  $("markHint").textContent = MARK_HINT[s.mark];
  document.querySelectorAll("#aheadSeg [data-ahead]").forEach((b) => b.classList.toggle("on", b.dataset.ahead === (s.ahead || "normal")));
  $("aheadHint").textContent = AHEAD_HINT[s.ahead || "normal"];
  requestAnimationFrame(() => segThumbs($("viewSettings")));
  // Vorschau: Abschnitt = beide Sätze, Satz = nur der gesprochene Satz, Wort = Satz + Wort
  $("pvSec").classList.toggle("on", s.mark === "section");
  $("pvS").classList.toggle("ws", s.mark !== "section");
  $("pvW").style.cssText = s.mark === "word" ? "background:var(--acc);color:var(--on-acc);box-shadow:0 0 0 2px var(--acc)" : "";
  // Stimmen
  if (setTab === "voices") renderVoiceLib();
  if (setTab === "storage") renderStorage();
  if (setTab === "app") renderAppTab();
}
$("uiSeg").onclick = (e) => { const b = e.target.closest("[data-ui]"); if (b && b.dataset.ui !== st.settings.uiLang) saveSettings({ uiLang: b.dataset.ui }); };
$("modeSeg").onclick = (e) => { const b = e.target.closest("[data-mode]"); if (b) saveSettings({ theme: b.dataset.mode }); };
$("swatches").onclick = (e) => { const b = e.target.closest("[data-acc]"); if (b) saveSettings({ accent: b.dataset.acc }); };
const AHEAD_HINT = {
  low: "Nur der nächste Abschnitt. Spart Rechenzeit – bei der eigenen Stimme kann es zwischen Abschnitten kurz stocken.",
  normal: "Die nächsten 3 Abschnitte (etwa eine Minute). Reicht für Online-Stimmen fast immer.",
  high: "Die nächsten 10 Abschnitte (einige Minuten). Gut für die eigene Stimme – weniger Pausen.",
  all: "Beim Abspielen wird der ganze Text im Hintergrund erzeugt – wie „Vorab erzeugen“, nur automatisch.",
};
$("aheadSeg").onclick = (e) => {
  const b = e.target.closest("[data-ahead]"); if (!b) return;
  saveSettings({ ahead: b.dataset.ahead }).then(() => { st.autoPrep = null; if (st.doc && st.wantPlay) prefetch(); });
};
$("markSeg").onclick = (e) => {
  const b = e.target.closest("[data-mark]"); if (!b) return;
  clearWords();
  saveSettings({ mark: b.dataset.mark }).then(() => { if (st.doc) { highlight(false); timeWords(st.idx); } });
};

/* ---------- Stimmen-Bibliothek ---------- */
let libLang = "de", libFilter = "all";
const REGION_ORDER = { de: ["DE", "AT", "CH"], en: ["US", "GB", "AU", "CA", "IE", "IN", "NZ", "ZA"] };
const REGION_NAME = { DE: "Deutschland", AT: "Österreich", CH: "Schweiz", US: "USA", GB: "Großbritannien", AU: "Australien", CA: "Kanada", IE: "Irland", IN: "Indien", NZ: "Neuseeland", ZA: "Südafrika", SG: "Singapur", PH: "Philippinen", HK: "Hongkong", KE: "Kenia", NG: "Nigeria", TZ: "Tansania" };
function renderVoiceLib() {
  // Ein Knopf: installiert → Aufnahme, sonst → Installation anbieten (während der Installation ausgeblendet)
  $("newCloneBtn").classList.toggle("hidden", !(st.features.clone || st.features.cloneSetup) || csPolling);
  if (!st.features.clone && st.features.cloneSetup && !csPolling) cloneSetupPoll(true);
  $("libLang").innerHTML = Object.entries(st.langs).map(([k, n]) => `<button data-ll="${k}" class="${k === libLang ? "on" : ""}">${esc(n)}</button>`).join("");
  document.querySelectorAll("#libFilter [data-f]").forEach((b) => b.classList.toggle("on", b.dataset.f === libFilter));
  const q = $("vlSearch").value.trim().toLowerCase();
  const std = st.defaults[libLang];
  let list = langVoices(libLang).filter((v) => v.engine !== "piper");       // Piper läuft nur unsichtbar als Ersatz
  if (libFilter === "fav") list = list.filter((v) => isFav(v.id) || v.engine === "clone");
  else if (libFilter === "own") list = list.filter((v) => v.engine === "clone");
  else if (libFilter === "Female" || libFilter === "Male") list = list.filter((v) => v.gender === libFilter);
  if (q) list = list.filter((v) => `${v.name} ${v.meta}`.toLowerCase().includes(q));
  const row = (v) => {
    const own = v.engine === "clone", fav = isFav(v.id), isStd = v.id === std;
    // Gerade aufgenommen → Zeile pulsiert kurz; bereit geworden → leuchtet einmal auf. Läuft über Neuzeichnungen
    // hinweg weiter (negative Verzögerung = bereits vergangene Zeit), statt neu zu starten.
    const fx = (k, dur) => { const m = st[k], ago = m?.id === v.id ? performance.now() - m.t : Infinity; return ago < dur ? ago : null; };
    const land = fx("voiceLand", 1800), ready = land == null ? fx("voiceReady", 900) : null, ago = land ?? ready;
    const cls = (own ? " own" : "") + (v.warming ? " warming" : "") + (land != null ? " landed" : ready != null ? " readied" : "");
    return `<div class="vl-row${cls}"${ago != null ? ` style="animation-delay:${-Math.round(ago)}ms"` : ""}>
      <span class="avl">${esc(v.name.slice(0, 1).toUpperCase())}</span>
      <span class="nm"><b data-noi18n>${esc(v.name)}</b><small>${esc(v.meta || "")}</small></span>
      ${isStd ? `<span class="stdtag">Standard</span>` : `<button class="stdlink" data-std="${esc(v.id)}">Als Standard</button>`}
      <button class="prev${v.warming ? " loading" : ""}" data-prev="${esc(v.id)}" aria-label="Hörprobe ${esc(v.name)}">${icon("i-play", "i fill", "width:14px;height:14px")}</button>
      ${own ? `<button class="star" data-delv="${esc(v.id)}" aria-label="${esc(v.name)} löschen" title="Löschen">${icon("i-trash", "i", "width:16px;height:16px")}</button>`
            : `<button class="star${fav ? " on" : ""}" data-fav="${esc(v.id)}" aria-pressed="${fav}" aria-label="${esc(v.name)} ${fav ? "aus Favoriten entfernen" : "zu Favoriten hinzufügen"}" title="${fav ? "Favorit" : "Zu Favoriten"}">${icon("i-star", "i", "width:18px;height:18px")}</button>`}
    </div>`;
  };
  const groups = [];
  const own = list.filter((v) => v.engine === "clone");
  if (own.length) groups.push(["Eigene Stimmen", "lokal · langsam", own]);
  const edge = list.filter((v) => v.engine === "edge");
  const order = REGION_ORDER[libLang] || [];
  const regions = [...new Set(edge.map((v) => v.region))].sort((a, b) => ((order.indexOf(a) + 1 || 99) - (order.indexOf(b) + 1 || 99)) || a.localeCompare(b));
  for (const r of regions) {
    const vs = edge.filter((v) => v.region === r).sort((a, b) => (isFav(b.id) - isFav(a.id)) || a.name.localeCompare(b.name));
    groups.push([REGION_NAME[r] || r, `${vs.length} Stimme${vs.length === 1 ? "" : "n"}`, vs]);
  }
  $("voiceLib").innerHTML = groups.length
    ? `<div class="box">${groups.map(([t, sub, vs]) => `<div class="vl-group"><span>${esc(t)}</span><span>${esc(sub)}</span></div>${vs.map(row).join("")}`).join("")}</div>`
    : `<div class="box"><div class="vp-empty" style="padding:18px">Keine Stimme gefunden.</div></div>`;
  requestAnimationFrame(() => segThumbs($("tabVoices")));
}
$("libLang").onclick = (e) => { const b = e.target.closest("[data-ll]"); if (b) { libLang = b.dataset.ll; renderVoiceLib(); } };
$("libFilter").onclick = (e) => { const b = e.target.closest("[data-f]"); if (b) { libFilter = b.dataset.f; renderVoiceLib(); } };
$("vlSearch").oninput = renderVoiceLib;
$("voiceLib").onclick = async (e) => {
  const pv = e.target.closest("[data-prev]");
  if (pv) return previewVoice(pv.dataset.prev, libLang, pv);
  const fv = e.target.closest("[data-fav]");
  if (fv) {
    const id = fv.dataset.fav, favs = st.settings.favorites || [];
    await saveSettings({ favorites: favs.includes(id) ? favs.filter((x) => x !== id) : [...favs, id] });
    $("voiceLib").querySelector(`[data-fav="${CSS.escape(id)}"].on`)?.classList.add("pop");   // nur beim Klick aufploppen, nicht bei jedem Neuzeichnen
    return;
  }
  const sb = e.target.closest("[data-std]");
  if (sb) { await saveSettings({ defaultVoices: { [libLang]: sb.dataset.std } }); await reloadVoices(); return renderVoiceLib(); }
  const del = e.target.closest("[data-delv]");
  if (del) {
    const v = voiceById(del.dataset.delv);
    if (!v || !(await ask({ title: `Eigene Stimme „${v.name}“ löschen?`, text: "Die Sprachprobe wird entfernt. Texte, die diese Stimme nutzen, lesen danach mit der Standardstimme.", ok: "Löschen", danger: true }))) return;
    try {
      await api(`/api/clones/${v.id.split(":")[1]}`, { method: "DELETE" });
      await collapseOut(del.closest(".vl-row"));
      await reloadVoices(); renderVoiceLib();
    }
    catch (err) { toastErr(err); }
  }
};
$("newCloneBtn").onclick = () => (st.features.clone ? openClone(null) : offerCloneInstall());

/* ---------- Speicher ---------- */
const STO_COLORS = { audio: "var(--acc-text)", previews: "color-mix(in srgb, var(--acc-text) 55%, var(--surface))",
  other: "color-mix(in srgb, var(--acc-text) 30%, var(--surface))", exports: "#C2913B", models: "var(--muted)" };
let stoAll = false;
function stoRow({ name, sub = "", bytes, del, tip, raw = false }) {
  const nm = raw ? `<span data-noi18n>${esc(name)}</span>` : esc(name);           // Titel von Texten nicht übersetzen
  return `<div class="sto-row"><span class="nm">${nm}${sub ? `<small>${esc(sub)}</small>` : ""}</span>
    <span class="sz">${fmtMB(bytes)}</span>${del ? `<button class="del" data-del="${del}" aria-label="${esc(tip)}" data-tip="${esc(tip)}">${icon("i-trash")}</button>` : ""}</div>`;
}
let stoLast = null;                                      // letzte Werte: beim erneuten Öffnen sofort zeigen
const sk = (w, h = 12) => `<span class="sk" style="width:${w}px;height:${h}px"></span>`;
function storageSkeleton() {                             // Platzhalter, bis die Größen berechnet sind
  $("stoTotal").innerHTML = sk(56, 14);
  $("stoStack").innerHTML = `<i class="sk" style="flex-grow:1;height:100%"></i>`;
  $("stoLegend").innerHTML = [130, 96, 110].map((w) => sk(w)).join("");
  $("cacheTxt").innerHTML = sk(110, 14);
  $("cacheLimit").value = String(st.settings.cacheMB);    // Einstellung ist sofort bekannt – nicht erst nach dem Laden
  const row = (w) => `<div class="sto-row"><span class="nm">${sk(w, 13)}<small>${sk(w * 0.7, 10)}</small></span>${sk(48, 12)}</div>`;
  $("stoDocs").innerHTML = `<h4>Pro Text</h4>${row(180)}${row(140)}`;
  $("stoMisc").innerHTML = "";
  for (const id of ["whisperSize", "cloneSize", "piperSize"]) $(id).innerHTML = sk(54);
}
async function renderStorage() {
  const tab = $("tabStorage");
  if (stoLast) fillStorage(stoLast, false);
  else { tab.classList.add("skel"); storageSkeleton(); }
  let r;
  try { r = await api("/api/storage"); } catch { return; }
  const fresh = tab.classList.contains("skel");
  tab.classList.remove("skel");
  stoLast = r;
  fillStorage(r, fresh);
}
function fillStorage(r, fresh) {
  const docsAudio = r.docs.reduce((a, d) => a + d.audio, 0);
  const models = r.whisper.bytes + r.clone.bytes + r.piper;
  const parts = [["audio", "Audio deiner Texte", docsAudio], ["previews", "Hörproben", r.previews.bytes],
                 ["other", "Reste", r.other.bytes], ["exports", "Exporte", r.exports], ["models", "Modelle", models]];
  const total = parts.reduce((a, p) => a + p[2], 0) + r.texts;
  $("stoTotal").textContent = fmtMB(total);
  $("stoStack").innerHTML = parts.filter((p) => p[2] > 0).map(([k, , b]) => `<i style="flex-grow:${b};background:${STO_COLORS[k]}"></i>`).join("");
  $("stoLegend").innerHTML = parts.filter((p) => p[2] > 0).map(([k, n, b]) => `<span><i style="background:${STO_COLORS[k]}"></i><span>${n}</span><b>${fmtMB(b)}</b></span>`).join("");
  $("cacheTxt").textContent = `${fmtMB(r.audio)} von ${fmtMB(r.limit)}`;
  $("cacheBar").style.width = `${Math.min(100, (r.audio / r.limit) * 100)}%`;
  $("cacheLimit").value = String(st.settings.cacheMB);
  // Audio pro Text (größte zuerst), Rest einklappbar
  const docs = r.docs.filter((d) => d.audio > 0);
  const shown = stoAll ? docs : docs.slice(0, 5);
  $("stoDocs").innerHTML = docs.length ? `<h4>Pro Text</h4>` + shown.map((d) => stoRow({ name: d.title || "Ohne Titel", raw: !!d.title,
      sub: `${d.files} ${d.files === 1 ? "Abschnitt" : "Abschnitte"} vertont`, bytes: d.audio, del: `docs/${d.id}`, tip: "Audio löschen (der Text bleibt)" })).join("")
    + (docs.length > 5 ? `<button class="btn sm sto-more" id="stoMore">${stoAll ? "Weniger anzeigen" : `Alle ${docs.length} Texte anzeigen`}</button>` : "") : "";
  const misc = [];
  if (r.previews.bytes) misc.push(stoRow({ name: "Hörproben", sub: "Stimmen-Vorschau in den Einstellungen", bytes: r.previews.bytes, del: "previews", tip: "Hörproben löschen" }));
  if (r.other.bytes) misc.push(stoRow({ name: "Reste", sub: "von gelöschten oder bearbeiteten Texten", bytes: r.other.bytes, del: "other", tip: "Reste löschen" }));
  if (r.exports) misc.push(stoRow({ name: "Exporte", sub: "fertige Hörbuch-Dateien", bytes: r.exports, del: "exports", tip: "Alle Exporte löschen" }));
  $("stoMisc").innerHTML = misc.length ? `<h4>Sonstiges</h4>` + misc.join("") : "";
  // Modelle
  $("whisperSize").textContent = r.whisper.bytes ? fmtMB(r.whisper.bytes) : "–";
  $("whisperNote").textContent = r.whisper.bytes ? "lädt nach dem Entfernen beim nächsten Diktat neu" : "wird beim ersten Diktat geladen";
  $("whisperRemove").classList.toggle("hidden", !(r.whisper.removable && r.whisper.bytes));
  $("cloneSize").textContent = r.clone.installed ? fmtMB(r.clone.bytes) : "–";
  $("cloneState").textContent = r.clone.installed ? "installiert" : "nicht installiert · ca. 4,5 GB";
  $("cloneRemove").classList.toggle("hidden", !(r.clone.installed && r.clone.removable));
  const names = st.voices.filter((v) => v.engine === "piper").map((v) => v.name);
  $("piperCount").textContent = names.length ? `${names.join(", ")} · springt ein, wenn offline` : "keine";
  $("piperSize").textContent = fmtMB(r.piper);
  if (fresh) for (const el of $("tabStorage").querySelectorAll(".box")) animateIn(el, "fadein");
}
function renderAppTab() {
  if (st.features.desktop) $("appNote").textContent = "Schließt das Fenster und stoppt alles im Hintergrund";
  updRender();
}
$("tabStorage").addEventListener("click", async (e) => {
  if (e.target.closest("#stoMore")) { stoAll = !stoAll; return renderStorage(); }
  const b = e.target.closest("[data-del]"); if (!b) return;
  const what = b.dataset.del;
  if (what === "exports" && !(await ask({ title: "Alle Exporte löschen?", text: "Die fertigen Hörbuch-Dateien werden gelöscht. Du kannst sie jederzeit neu exportieren.", ok: "Löschen", danger: true }))) return;
  b.disabled = true;
  try {
    const r = await api(`/api/storage/${what}`, { method: "DELETE" });
    if (what.startsWith("docs/") && st.doc && what.endsWith(st.doc.id)) { clearCache(); markReady(); }   // Player soll neu laden
    if (what.startsWith("docs/")) refreshLibrary().catch(() => {});      // Vorbereitet-Balken in der Seitenleiste
    toast(`${fmtMB(r.freed)} freigegeben`);
    // Antwort enthält schon den neuen Stand: direkt übernehmen, nicht erst die alten Werte nochmal zeigen
    stoLast = r;
    await collapseOut(b.closest(".sto-row"));
    fillStorage(r, false);
  } catch (err) { b.disabled = false; toastErr(err); }
});
$("whisperRemove").onclick = async () => {
  if (!(await ask({ title: "Diktat-Modell entfernen?", text: "Gibt ca. 500 MB frei. Beim nächsten Diktat wird es wieder geladen (Internet nötig).", ok: "Entfernen", danger: true }))) return;
  try { const r = await api("/api/storage/whisper", { method: "DELETE" }); toast(`${fmtMB(r.freed)} freigegeben`); renderStorage(); }
  catch (e) { toastErr(e); }
};

/* ---------- Eigene Stimme nachinstallieren (Desktop-App) ---------- */
const CS_TITLE = { done: "Fertig!" };              // sonst immer „Eigene Stimme wird installiert“
const CS_STEP = {
  "python:download": "Eine eigene Python-Version wird geladen",
  "python:venv": "Eigene Umgebung wird eingerichtet",
  "packages:resolve": "Passende Pakete werden zusammengestellt",
  "packages:download": "Programmteile werden geladen",
  "packages:install": "Programmteile werden ausgepackt und installiert",
  "packages:finish": "Programmteile sind fertig.",
  "model:": "Das Stimmmodell wird geladen",
  "model:finish": "Fast fertig – das Stimmmodell wird eingerichtet",
  "model:prepare": "Das Stimmmodell wird vorbereitet",
};
const CS_TIPS = {
  python: ["Der Vorleser bekommt eine eigene Python-Version – getrennt von allem anderen auf deinem Rechner.",
           "Alles landet nur im Vorleser-Ordner und lässt sich in den Einstellungen wieder entfernen."],
  packages: ["Gerade kommt PyTorch – die Rechenbibliothek, mit der das Stimmmodell arbeitet.", "GPU",
             "Du kannst den Vorleser währenddessen ganz normal benutzen."],
  model: ["Jetzt das Herzstück: das Stimmmodell „Chatterbox“ von Resemble AI (MIT-Lizenz).",
          "Danach reichen 15–30 Sekunden Aufnahme deiner Stimme.",
          "Tipp für die Aufnahme: ruhiger Raum, normaler Abstand zum Mikrofon.",
          "Deine Stimme liest danach Deutsch und Englisch."],
};
const CS_GPU = { mps: "Später rechnet der Grafikchip deines Macs die Stimme aus.", nvidia: "Später rechnet deine NVIDIA-Grafikkarte die Stimme aus.",
                 cpu: "Ohne passende Grafikkarte rechnet der Prozessor – das klappt, dauert aber länger." };
const CS_ORDER = ["python", "packages", "model"];
let csPollT = 0;
const cs = { s: null, shown: 0, clockT: 0, tipT: 0, tipI: 0, tipPhase: "", offset: 0, lastStep: "" };
const fmtClock = (sec) => { sec = Math.max(0, Math.floor(sec)); const m = Math.floor(sec / 60), h = Math.floor(m / 60);
  return h ? `${h}:${String(m % 60).padStart(2, "0")}:${String(sec % 60).padStart(2, "0")}` : `${m}:${String(sec % 60).padStart(2, "0")}`; };
const fmtEta = (sec) => sec == null ? "Restzeit wird berechnet" : sec < 60 ? "noch weniger als 1 Min." :
  sec < 3600 ? `noch ca. ${Math.round(sec / 60)} Min.` : `noch ca. ${Math.floor(sec / 3600)} Std. ${Math.round((sec % 3600) / 60)} Min.`;
// Deutsch formatieren (wie alle Texte der App) – i18n.js macht im Englischen „1,404“ daraus.
// Nicht toLocaleString: die macOS-Webview ignoriert die angefragte Sprache und nimmt die des Systems.
const fmtNum = (n) => String(Math.round(n)).replace(/\B(?=(\d{3})+(?!\d))/g, ".");

async function offerCloneInstall() {
  const f = st.features;
  const text = f.os === "mac"
    ? "Lädt ca. 3,4 GB und dauert je nach Verbindung 10–30 Minuten. Die Stimme läuft danach auf dem Grafikchip deines Macs."
    : f.gpu === "nvidia"
      ? "Lädt ca. 5,7 GB und dauert je nach Verbindung 15–40 Minuten. Die Stimme läuft danach auf deiner NVIDIA-Grafikkarte."
      : "Lädt ca. 3,5 GB und dauert je nach Verbindung 10–30 Minuten. Ohne NVIDIA-Grafikkarte rechnet der Prozessor – das funktioniert, braucht aber pro Abschnitt deutlich länger.";
  if (!(await ask({ title: "Eigene Stimme installieren?", text, ok: "Installieren", icon: "i-dl" }))) return;
  try { await api("/api/clone-setup", { method: "POST" }); } catch (e) { return toastErr(e); }
  cloneSetupPoll();
}
$("csCancel").onclick = async () => {
  if (!(await ask({ title: "Installation abbrechen?", text: "Bereits Geladenes wird verworfen.",
    ok: "Installation abbrechen", cancel: "Weiter installieren", danger: true, icon: "i-x" }))) return;
  try { await api("/api/clone-setup", { method: "DELETE" }); } catch (e) { toastErr(e); }
};
$("cloneRemove").onclick = async () => {
  if (!(await ask({ title: "Eigene Stimme entfernen?", text: "Gibt ca. 4,5 GB frei. Deine Sprachproben bleiben erhalten – nach erneutem Installieren sind die eigenen Stimmen wieder da.", ok: "Entfernen", danger: true }))) return;
  try { await api("/api/clone-setup", { method: "DELETE" }); await reloadVoices(); renderStorage(); toast("Eigene Stimme entfernt"); }
  catch (e) { toastErr(e); }
};

function csTip() {                                      // Hinweise der aktuellen Phase nacheinander einblenden
  const s = cs.s; if (!s) return;
  const list = (CS_TIPS[s.phase] || []).map((t) => (t === "GPU" ? CS_GPU[s.gpu] || CS_GPU.cpu : t));
  if (!list.length) return;
  if (cs.tipPhase !== s.phase) { cs.tipPhase = s.phase; cs.tipI = 0; } else cs.tipI = (cs.tipI + 1) % list.length;
  const el = $("csTip");
  el.classList.add("out");
  setTimeout(() => { el.textContent = list[cs.tipI]; el.classList.remove("out"); }, 350);
}
function csTick() {                                     // jede Sekunde: Uhr + sanft weiterlaufender Balken
  const s = cs.s; if (!s || s.status !== "running") return;
  const now = Date.now() / 1000 - cs.offset;
  $("csElapsed").textContent = fmtClock(now - (s.started || now));
  // Balken = aktuelle Phase (passt zu „X von Y MB“); bei Stillstand läuft er sanft weiter, aber nie bis 100 %
  const phaseTotal = (s.totals || {})[s.phase] || 1, real = Math.min(100, (s.mb || 0) / phaseTotal * 100);
  const waiting = (s.stalled || 0) >= 4 && s.step !== "finish";   // alles geladen → ruhig voll stehen, kein Schimmer
  if (s.phase !== cs.barPhase) { cs.barPhase = s.phase; cs.shown = 0; }
  if (real > cs.shown) cs.shown = real;
  else if (waiting && cs.shown < 97) cs.shown = Math.min(cs.shown + Math.max(0.05, (100 - cs.shown) * 0.006), 97);   // nie zurück
  $("csBar").style.width = `${Math.max(2, Math.min(100, cs.shown))}%`;
  $("csBarWrap").classList.toggle("waiting", waiting);
}
function csRender() {
  const s = cs.s, box = $("cloneSetupBox");
  $("csArt").dataset.phase = s.phase || "python";
  // Das Stimmmodell lädt lange → nach jedem Drittel eine neue Szene (Welle › Netz › Sprechblase)
  const frac = (s.mb || 0) / ((s.totals || {})[s.phase] || 1);
  $("csArt").dataset.sub = s.phase === "model" ? String(frac < 1 / 3 ? 1 : frac < 2 / 3 ? 2 : 3) : "1";
  $("csPhase").textContent = CS_TITLE[s.phase] || "Eigene Stimme wird installiert";
  if (s.phase !== cs.tipPhase && s.phase !== "done") csTip();        // neuer Schritt → passender Hinweis sofort
  $("csCancel").classList.toggle("hidden", s.phase === "done");
  // Zwischenschritt; bei längerem Stillstand erklären statt still zu hängen
  const preparing = s.phase === "model" && !(s.mb > 0);   // noch keine Daten – vorbereiten, nicht „langsam“
  let step = CS_STEP[`${s.phase}:${preparing ? "prepare" : s.step || ""}`] || CS_STEP[`${s.phase}:`] || "";
  const finishing = s.step === "finish";
  if ((s.stalled || 0) >= 10 && !finishing && !preparing) step = s.phase === "model" ? "Die Verbindung ist gerade langsam – es geht gleich weiter."
    : s.step === "install" ? "Große Pakete werden ausgepackt – das dauert einen Moment."
    : "Eine große Datei ist in Arbeit (z. B. PyTorch) – es geht gleich weiter.";
  if (step !== cs.lastStep) { $("csStep").textContent = step; animateIn($("csStep"), "swap"); cs.lastStep = step; }
  const t = (s.totals || {})[s.phase], est = s.phase === "packages" ? "ca. " : "";
  $("csSize").textContent = s.phase === "python" || !t ? "" :
    finishing ? `${fmtNum(t)} MB geladen` :
    `${fmtNum(s.mb || 0)} MB von ${est}${fmtNum(t)} MB` + (s.speed > 0.2 ? ` · ${s.speed.toFixed(1).replace(".", ",")} MB/s` : "");
  $("csEta").textContent = finishing ? "gleich fertig" : fmtEta(s.eta);
  document.querySelectorAll("#csSteps li").forEach((li) => {
    const k = CS_ORDER.indexOf(li.dataset.p), cur = CS_ORDER.indexOf(s.phase);
    li.classList.toggle("done", k < cur || s.phase === "done");
    li.classList.toggle("on", k === cur);
  });
  box.classList.remove("hidden");
}
/** Karte auflösen und Höhe weich auf 0 – der Inhalt darunter rückt nach, statt hochzuspringen. */
function csCollapse(done) {
  const box = $("cloneSetupBox");
  if (box.classList.contains("hidden")) return done?.();
  box.style.height = `${box.offsetHeight}px`; box.style.overflow = "hidden";
  void box.offsetWidth;
  box.classList.add("collapsing");
  setTimeout(() => {
    box.classList.add("hidden"); box.classList.remove("collapsing");
    box.style.height = ""; box.style.overflow = "";
    done?.();
  }, reducedMotion.matches ? 0 : 580);
}
async function cloneSetupPoll(quiet = false) {
  clearTimeout(csPollT);
  let s;
  try { s = await api("/api/clone-setup"); } catch { csPolling = false; return; }
  const box = $("cloneSetupBox");
  if (s.status === "running") {
    if (!csPolling) { cs.shown = 0; cs.barPhase = ""; cs.lastStep = ""; cs.tipPhase = ""; }
    csPolling = true;
    cs.s = s;
    if (s.now) cs.offset = Date.now() / 1000 - s.now;
    $("newCloneBtn").classList.add("hidden");
    csRender();
    if (!cs.clockT) { cs.clockT = setInterval(csTick, 1000); cs.tipT = setInterval(csTip, 7000); }
    csTick();
    csPollT = setTimeout(() => cloneSetupPoll(), 1500);
    return;
  }
  const was = csPolling;
  csPolling = false;
  clearInterval(cs.clockT); clearInterval(cs.tipT); cs.clockT = cs.tipT = 0;
  if (s.status === "done" && was) {                       // kurz „Fertig“ zeigen, dann ausblenden
    cs.s = { ...cs.s, phase: "done", status: "done" };
    csRender();
    $("csBar").style.width = "100%"; $("csBarWrap").classList.remove("waiting");
    $("csStep").textContent = "Alles bereit – jetzt deine Stimme aufnehmen.";
    $("csEta").textContent = ""; $("csTip").textContent = "";
    await reloadVoices();
    setTimeout(() => csCollapse(() => { renderVoiceLib(); openClone(null); }), 2200);   // direkt weiter: Stimme aufnehmen
    return;
  }
  csCollapse();
  if (s.status === "error" && !quiet) {
    toast(`Installation fehlgeschlagen: ${s.error}`, true);
    renderVoiceLib();
  } else if (was) renderVoiceLib();
}
$("quitBtn").onclick = async () => {
  const how = st.features.desktop ? "Zum Starten den Vorleser wieder öffnen." : "Zum Starten wieder Vorleser.app doppelklicken.";
  if (!(await ask({ title: "Vorleser beenden?", text: `Wiedergabe und laufende Exporte werden gestoppt. ${how}`, ok: "Beenden", danger: true, icon: "i-x" }))) return;
  if (st.wantPlay) pause();
  saveProgress(true);
  try { await api("/api/quit", { method: "POST" }); } catch {}
  if (st.features.desktop) return;          // Desktop-App: das Fenster schließt sich selbst
  document.body.innerHTML = `<div style="height:100vh;display:grid;place-items:center;text-align:center;font:15px/1.6 var(--ui);color:var(--muted)">
    <div><div style="font-size:22px;font-weight:700;color:var(--ink);margin-bottom:6px">Vorleser beendet</div>
    <div>Zum Starten Vorleser.app doppelklicken.</div><div>Dieses Fenster kannst du schließen.</div></div></div>`;
};
$("cacheLimit").onchange = () => saveSettings({ cacheMB: +$("cacheLimit").value });
$("cacheClear").onclick = async () => {
  if (!(await ask({ title: "Speicher leeren?", text: "Erzeugtes Audio wird gelöscht und beim nächsten Abspielen neu erzeugt. Mit eigener Stimme kann das dauern.", ok: "Leeren", danger: true }))) return;
  if (st.doc) { const keep = { i: st.idx, off: st.loadedIdx === st.idx ? audio.currentTime : st.pendingOffset }; if (st.wantPlay) pause(); clearCache(); st.idx = keep.i; st.pendingOffset = keep.off; }
  await api("/api/cache", { method: "DELETE" }); renderStorage(); markReady(); refreshLibrary().catch(() => {});
};

/* ===================================================================== */
/* Erster Start: Einrichten → Willkommen → Tutorial                       */
/* ===================================================================== */
const onbEl = $("onb");
const L = (de, en) => (UI_LANG === "en" ? en : de);
const SLIDES = [
  { t: "Text hinzufügen",
    p: "Über „Neuer Text“ fügst du Text ein, ziehst eine Datei hinein (EPUB, PDF, TXT …) oder diktierst einfach. Kapitel und Sprache erkennt der Vorleser selbst.",
    il: () => `<div class="paper">${[80, 95, 60, 85].map((w, k) => `<div class="ln" style="--k:${k};width:${w}%"></div>`).join("")}</div><div class="file">EPUB</div>` },
  { t: "Anhören",
    p: "Play startet, die Leertaste pausiert. Ein Klick auf einen Satz springt dorthin – dein Lesezeichen merkt sich der Vorleser automatisch.",
    il: () => `<div class="read">${L("Es war ein klarer Morgen am weiten Meer", "It was a clear morning by the sea").split(" ").map((w, k) => `<span style="--k:${k}">${w}</span>`).join("")}</div>
      <span class="play is-playing">${icon("i-pause", "i fill")}</span>` },
  { t: "Bearbeiten",
    p: "Über „…“ › Text bearbeiten oder die Taste E änderst du einen fertigen Text. Dein Lesezeichen bleibt, wo es war.",
    il: () => `<div class="paper" style="font:16px/1.6 var(--read);color:var(--ink2)">${L("Der alte", "The old")} <span class="strike">${L("Wärter", "keeper")}</span> <span class="new">${L("Wächter", "guard")}</span><span class="cursor"></span>
      <div class="ln" style="--k:1;width:90%;margin-top:12px"></div><div class="ln" style="--k:2;width:70%"></div></div><span class="pen">${icon("i-pen")}</span>` },
  { t: "Deine eigene Stimme",
    p: "Unter Einstellungen › Stimmen nimmst du 15–30 Sekunden auf – danach liest der Vorleser mit deiner Stimme. Sie braucht länger, darum am besten „Vorab erzeugen“.",
    il: () => `${[0, 1, 2].map((k) => `<span class="ringw" style="--k:${k}"></span>`).join("")}<span class="mic">${icon("i-mic")}</span>
      <div class="wave" style="bottom:-6px;opacity:.5">${Array.from({ length: 24 }, (_, k) => `<i style="--k:${k};height:${10 + ((k * 7) % 22)}px"></i>`).join("")}</div>` },
  { t: "Als Hörbuch exportieren",
    p: "Mit „Exportieren“ speicherst du den ganzen Text als M4B mit Kapiteln, als MP3 oder als WAV – für Handy, Auto oder Hörbuch-App.",
    il: () => `<div class="chips">${["M4B", "MP3", "WAV"].map((f, k) => `<span class="chip" style="--k:${k}">${f}</span>`).join("")}</div>
      <span class="arrow">${icon("i-dl")}</span><div class="tray"></div>` },
  { t: "Noch ein paar Tipps",
    p: "Markiere Lieblingsstimmen mit ★, dann hast du sie beim Hören griffbereit. Ohne Internet springt automatisch eine Offline-Stimme ein. Dieses Tutorial findest du jederzeit in den Einstellungen.",
    il: () => `<div class="keys">${[L("Leertaste", "Space"), "←", "→", "E"].map((k, i) => `<span class="key" style="--k:${i}">${k}</span>`).join("")}</div>
      <span class="bigstar">${icon("i-star")}</span>` },
];

function onbOpen(stage = "setup") {
  hideTip(); closePops(true);
  if (st.wantPlay) pause();
  onbEl.classList.remove("hidden", "closing");
  onbSetup();
}
function onbClose() {
  onbEl.classList.add("closing");
  if (!st.settings.onboarded) saveSettings({ onboarded: true });
  setTimeout(() => { onbEl.classList.add("hidden"); onbEl.classList.remove("closing"); onbEl.innerHTML = ""; }, 600);
}

/* 1) Einrichten */
function onbSetup() {
  onbEl.innerHTML = `<div class="onb-card onb-in" id="onbCard">
    <h2 style="--d:0">Kurz einrichten</h2>
    <p class="sub" style="--d:1">Das kannst du später jederzeit in den Einstellungen ändern.</p>
    <div style="--d:2"><div class="lbl">Sprache</div>
      <div class="seg" id="oLang" data-noi18n><button data-ui="de">Deutsch</button><button data-ui="en">English</button></div></div>
    <div style="--d:3"><div class="lbl">Erscheinungsbild</div><div class="onb-modes" id="oMode">
      <button class="onb-mode" data-mode="light"><span class="pv pv-light"><i></i><i></i><i></i></span>Hell</button>
      <button class="onb-mode" data-mode="dark"><span class="pv pv-dark"><i></i><i></i><i></i></span>Dunkel</button>
      <button class="onb-mode" data-mode="system"><span class="pv pv-sys"><i></i><i></i><i></i></span>System</button></div></div>
    <div style="--d:4"><div class="lbl">Akzentfarbe</div><div class="onb-sw" id="oSw"></div></div>
    <div class="onb-foot" style="--d:5"><span class="spacer"></span><button class="btn primary" id="oNext">Weiter</button></div>
  </div>`;
  onbSync();
  $("oLang").onclick = (e) => { const b = e.target.closest("[data-ui]"); if (b) { saveSettings({ uiLang: b.dataset.ui }); onbSync(); } };
  $("oMode").onclick = (e) => { const b = e.target.closest("[data-mode]"); if (b) { saveSettings({ theme: b.dataset.mode }); onbSync(); } };
  $("oSw").onclick = (e) => { const b = e.target.closest("[data-acc]"); if (b) { saveSettings({ accent: b.dataset.acc }); onbSync(); } };
  $("oNext").onclick = onbWelcome;
  setTimeout(() => $("oNext")?.focus({ focusVisible: false }), 400);
}
function onbSync() {
  if (!$("oLang")) return;
  const s = st.settings, dark = isDark(s), preset = presetOf(s.accent);
  $("oLang").querySelectorAll("[data-ui]").forEach((b) => b.classList.toggle("on", b.dataset.ui === (s.uiLang || "de")));
  $("oMode").querySelectorAll("[data-mode]").forEach((b) => b.classList.toggle("on", b.dataset.mode === s.theme));
  $("oSw").innerHTML = PRESETS.map((p) => {
    const col = dark ? p.dark : p.light, on = preset === p;
    const ink = contrast("#FFFFFF", col) >= contrast("#111111", col) ? "#FFFFFF" : "#111111";
    return `<button class="sw${on ? " on" : ""}" data-acc="${p.light}" aria-label="Akzentfarbe ${p.name}" style="background:${col}">${on ? `<svg class="i" style="stroke:${ink}"><use href="#i-check"/></svg>` : ""}</button>`;
  }).join("");
  requestAnimationFrame(() => segThumbs(onbEl));
}

/* 2) Willkommen – blendet langsam aus und geht ins Tutorial über */
function onbWelcome() {
  $("onbCard")?.classList.add("onb-out");
  setTimeout(() => {
    const word = L("Willkommen", "Welcome");
    onbEl.innerHTML = `<div class="onb-welcome" id="onbW" data-noi18n>
      <div class="big-logo">${[0, 1, 2, 3, 4].map((k) => `<i style="--k:${k}"></i>`).join("")}</div>
      <h1 class="welcome-title">${[...word].map((c, k) => `<span style="--k:${k}">${c}</span>`).join("")}</h1>
      <p class="welcome-sub">${L("Hören statt lesen – mit deiner Lieblingsstimme.", "Listen instead of reading – in your favorite voice.")}</p></div>`;
    setTimeout(() => {
      $("onbW")?.classList.add("leave");
      setTimeout(() => { onbEl.classList.add("closing"); gtStart(true); setTimeout(() => { onbEl.classList.add("hidden"); onbEl.classList.remove("closing"); onbEl.innerHTML = ""; }, 600); }, 700);
    }, 2700);
  }, 450);
}

$("tourBtn").onclick = () => gtStart(false);
document.addEventListener("keydown", (e) => {          // Esc beim Einrichten: überspringen
  if (onbEl.classList.contains("hidden") || e.key !== "Escape") return;
  e.preventDefault(); onbClose();
});

/* ===================================================================== */
/* Rundgang in der App (mit Beispieltext)                                  */
/* ===================================================================== */
function demoDoc() {
  const de = UI_LANG !== "en", lang = de ? "de" : "en";
  const c = de ? [
    ["Willkommen", 1, 1], ["Das ist ein Beispieltext, damit du siehst, wie der Vorleser funktioniert.", 0, 1],
    ["Er liest dir Texte abschnittsweise vor und merkt sich, wo du warst.", 0, 0],
    ["Beim Hören wird der gesprochene Satz markiert, und das aktuelle Wort leuchtet mit. So findest du jederzeit die Stelle.", 0, 1],
    ["Kapitel zwei", 1, 1], ["Kapitel erkennt der Vorleser automatisch – aus Überschriften, EPUB-Inhaltsverzeichnissen oder PDF-Lesezeichen.", 0, 1],
    ["Diesen Beispieltext findest du danach in deiner Bibliothek – behalte ihn oder lösche ihn einfach.", 0, 1],
  ] : [
    ["Welcome", 1, 1], ["This is a sample text so you can see how Vorleser works.", 0, 1],
    ["It reads texts to you section by section and remembers where you left off.", 0, 0],
    ["While listening, the spoken sentence is highlighted and the current word lights up. So you always know where you are.", 0, 1],
    ["Chapter two", 1, 1], ["Vorleser detects chapters automatically – from headings, EPUB tables of contents or PDF bookmarks.", 0, 1],
    ["You'll find this sample text in your library afterwards – keep it or simply delete it.", 0, 1],
  ];
  const now = Date.now() / 1000;
  const sample = st.docs.find((d) => d.sample);            // schon in der Bibliothek? → denselben Eintrag nutzen
  return {
    id: sample ? sample.id : "demo", demo: true, lang, voice: st.defaults[lang] || "", title: de ? "Willkommen beim Vorleser" : "Welcome to Vorleser",
    chunks: c.map(([text, h, par]) => ({ text, h: !!h, par: !!par })),
    chapters: [{ title: c[0][0], chunk: 0 }, { title: c[4][0], chunk: 4 }],
    progress: { chunk: 3, offset: 0, updated: now }, created: now,
  };
}

const ILL = Object.fromEntries(SLIDES.map((s, i) => [["create", "listen", "edit", "voice", "export", "tips"][i], s.il]));
ILL.three = () => `<div class="three"><span class="thumb3"></span>${["i-doc", "i-file", "i-mic"].map((ic, k) => `<span class="t3" style="--k:${k}">${icon(ic)}</span>`).join("")}</div>
  <div class="three-sub"><i></i></div>`;
ILL.chapters = () => `<div class="chap"><div class="cbar"><i class="cfill"></i><span class="ctick" style="left:36%"></span><span class="ctick" style="left:70%"></span><span class="cknob"></span></div>
  <div class="clist">${[L("1. Willkommen", "1. Welcome"), L("2. Kapitel zwei", "2. Chapter two"), L("3. Kapitel drei", "3. Chapter three")].map((t, k) => `<span style="--k:${k}">${t}</span>`).join("")}</div></div>`;
const TOUR = [
  { view: "read", target: "#newBtn", il: "create", t: "Neuen Text anlegen",
    p: "Hier fängt alles an: Text einfügen, eine Datei hineinziehen oder diktieren." },
  { view: "new", via: "#newBtn", target: "#viewNew .seg", il: "three", t: "Drei Wege zum Text",
    p: "Einfügen, Datei (EPUB, PDF, TXT …) oder Diktieren. Kapitel und Sprache erkennt der Vorleser selbst." },
  { view: "read", target: "#chapterBtn", il: "chapters", t: "Kapitel",
    p: "Springe direkt zu einem Kapitel. Die kleinen Striche auf dem Fortschrittsbalken zeigen, wo sie beginnen." },
  { view: "read", target: "#moreMenu", more: true, il: "edit", t: "Bearbeiten & mehr",
    p: "Unter „…“ bearbeitest du den Text (Taste E) oder lässt alles vorab erzeugen. Dein Lesezeichen bleibt beim Bearbeiten erhalten." },
  { view: "read", target: "#exportBtn", il: "export", t: "Als Hörbuch exportieren",
    p: "Speichert den ganzen Text als M4B mit Kapiteln, als MP3 oder als WAV – für Handy, Auto oder Hörbuch-App." },
  { view: "settings", tab: "voices", via: "#settingsBtn", target: () => (st.features.clone || st.features.cloneSetup ? $("newCloneBtn") : $("voiceLib")), il: "voice", t: "Deine eigene Stimme",
    p: "Nimm 15–30 Sekunden auf – danach liest der Vorleser mit deiner Stimme. Mit ★ machst du Stimmen zu Favoriten." },
  { view: "read", target: null, il: "tips", t: "Fertig!",
    p: "Das war's. Den Rundgang findest du jederzeit unter Einstellungen › App.", by: true },
];

const gt = { i: 0, prev: null, wordsTimer: null, token: 0 };
function gtStart(fromOnboarding, startAt = 0) {
  hideTip(); closePops(true);
  if (st.wantPlay) pause();
  gt.prev = { id: st.doc && !st.doc.demo ? st.doc.id : null, onboarding: fromOnboarding };
  gt.cardPos = null;
  st.demoEntry = st.docs.some((d) => d.sample) ? null : { ...demoDoc(), count: 7, chapters: 2 };   // keine Doppelung in der Bibliothek
  renderLibrary();
  stop();
  showDoc(demoDoc());
  gt.i = 0; gt.pct = 0;
  $("gt").classList.remove("hidden", "leaving");
  $("gtSpot").classList.add("enter");
  setTimeout(() => $("gtSpot").classList.remove("enter"), 700);
  $("gtCard").classList.add("first");
  gtShow(Math.max(0, Math.min(TOUR.length - 1, startAt)));
}
function gtEnd() {
  gt.token++;
  clearInterval(gt.wordsTimer);
  $("gtCursor").classList.remove("show");
  closePops(true);
  $("gt").classList.add("leaving");
  if (!st.settings.onboarded) saveSettings({ onboarded: true });
  setTimeout(async () => {
    $("gt").classList.add("hidden"); $("gt").classList.remove("leaving");
    stop(); st.doc = null; st.words = null;
    const sampleId = await ensureSample();                 // Beispieltext bleibt (auch bei Abbruch) in der Bibliothek
    st.demoEntry = null;
    renderLibrary();
    if (gt.prev?.id && st.docs.some((d) => d.id === gt.prev.id)) await openDoc(gt.prev.id);
    else if (sampleId) await openDoc(sampleId);
    else if (st.docs.length) await openDoc(st.docs[0].id);
    else showNew();
  }, 500);
}
/** Beispieltext als echten Text speichern, falls noch keiner in der Bibliothek ist. Liefert dessen ID. */
async function ensureSample() {
  const have = st.docs.find((d) => d.sample);
  if (have) return have.id;
  const d = demoDoc();
  let text = "", prevHead = true;
  for (const c of d.chunks) {                              // wie der Server: Überschriften „# …“, Absätze per Leerzeile
    text += c.h ? `${text ? "\n\n" : ""}# ${c.text}` : (c.par || prevHead ? `\n\n${c.text}` : ` ${c.text}`);
    prevHead = c.h;
  }
  try {
    const res = await api("/api/docs", { method: "POST", body: JSON.stringify({ text: text.trim(), title: d.title, lang: d.lang, sample: true }) });
    await refreshLibrary();
    return res.id;
  } catch { return null; }
}
function gtTarget(step) {
  const t = typeof step.target === "function" ? step.target() : step.target ? document.querySelector(step.target) : null;
  return t && t.offsetWidth ? t : null;
}
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
/** Warten, bis Seiten-/Reiter-Animationen fertig sind (sonst misst das Spotlight verschobene Positionen). */
async function gtSettled(max = 900) {
  const t0 = Date.now();
  while (document.querySelector(".view.enter, .set-body.enter, .reader.enter") && Date.now() - t0 < max) await sleep(40);
}
function gtCardHTML(i) {
  const step = TOUR[i];
  const pct = ((i + 1) / TOUR.length) * 100, prevPct = gt.pct ?? 0;
  gt.pct = pct;
  return { pct, html: `<div class="gt-prog"><i id="gtProg" style="width:${prevPct}%"></i></div>
    <button class="gt-x" id="gtX" aria-label="Rundgang beenden" data-tip="Rundgang beenden · Esc">${icon("i-x")}</button>
    <div class="gt-step">
      ${step.il ? `<div class="gt-stage"><div class="il" data-noi18n>${ILL[step.il]()}</div></div>` : ""}
      <div class="gt-body"><div class="num">${i + 1} / ${TOUR.length}</div><h3>${esc(step.t)}</h3><p>${esc(step.p)}</p>${step.by ? `<p class="gt-by">Gebaut von <a href="https://github.com/SimonSchneZzer" target="_blank" rel="noopener">Simon Schnetzer</a></p>` : ""}
        <div class="gt-foot"><span class="spacer"></span>
          ${i > 0 ? `<button class="btn" id="gtBack">Zurück</button>` : ""}
          <button class="btn primary" id="gtNext">${i === TOUR.length - 1 ? "Los geht's" : "Weiter"}</button></div></div></div>` };
}
/** Animierter Mauszeiger fährt zum Element und „klickt“ – macht Seitenwechsel nachvollziehbar. */
async function gtClick(el, my) {
  const cur = $("gtCursor"), rip = $("gtRipple"), card = $("gtCard").getBoundingClientRect();
  const r = el.getBoundingClientRect(), x = r.left + r.width / 2, y = r.top + r.height / 2;
  cur.style.transition = "none";
  cur.style.left = `${card.left + card.width / 2}px`; cur.style.top = `${card.top + 40}px`;
  void cur.offsetWidth; cur.style.transition = "";
  cur.classList.add("show");
  await sleep(30); if (my !== gt.token) return false;
  cur.style.left = `${x}px`; cur.style.top = `${y}px`;
  await sleep(780); if (my !== gt.token) return false;
  cur.classList.add("click");
  rip.style.left = `${x}px`; rip.style.top = `${y}px`;
  rip.classList.remove("go"); void rip.offsetWidth; rip.classList.add("go");
  await sleep(160); cur.classList.remove("click");
  await sleep(260); cur.classList.remove("show");
  return my === gt.token;
}
async function gtShow(i) {
  const step = TOUR[i], my = ++gt.token, card = $("gtCard");
  gt.i = i; gt.override = null;
  card.classList.remove("nav");
  clearInterval(gt.wordsTimer);
  closePops(true);
  const needSwitch = (step.view === "settings" && view !== "settings") || (step.view === "new" && view !== "new");
  const { pct, html } = gtCardHTML(i);
  card.innerHTML = html;
  requestAnimationFrame(() => requestAnimationFrame(() => { if ($("gtProg")) $("gtProg").style.width = `${pct}%`; }));
  $("gtX").onclick = gtEnd;
  if ($("gtBack")) $("gtBack").onclick = () => gtShow(i - 1);
  $("gtNext").onclick = () => (i < TOUR.length - 1 ? gtShow(i + 1) : gtEnd());
  $("gtNext").focus({ preventScroll: true, focusVisible: false });
  if (card.classList.contains("first")) gtPlace();      // erster Schritt: gleich richtig stehen (kein Gleiten von oben links)

  // 1) Bei Seitenwechsel: erst zum Knopf, Zeiger klickt sichtbar
  const via = needSwitch && step.via ? document.querySelector(step.via) : null;
  if (via && via.offsetWidth) {
    card.classList.add("nav");                         // Karte aus – Aufmerksamkeit auf Spotlight + Zeiger
    gt.override = via;
    gtPlace(via);
    await sleep(650); if (my !== gt.token) return;
    if (!(await gtClick(via, my))) { card.classList.remove("nav"); return; }
    gt.override = null;
  }
  // 2) Ansicht wechseln
  let wait = 60;
  if (step.view === "settings") {
    if (view !== "settings") { showView("settings"); wait = 450; }
    if (setTab !== step.tab) { document.querySelector(`#setTabs [data-tab="${step.tab}"]`).click(); wait = 450; }
  } else if (step.view === "new" && view !== "new") { showNew(); setSrc("paste"); wait = 450; }
  else if (step.view === "read" && view !== "read") { showDoc(st.doc?.demo ? st.doc : demoDoc()); wait = 450; }
  if (step.more) { $("moreBtn").click(); wait = Math.max(wait, 260); }
  // 3) Spotlight aufs Ziel
  await sleep(Math.min(wait, 120)); await gtSettled();
  if (my !== gt.token) { card.classList.remove("nav"); return; }
  gtPlace();
  if (card.classList.contains("first")) requestAnimationFrame(() => requestAnimationFrame(() => card.classList.remove("first")));
  if (card.classList.contains("nav")) {                // an neuer Stelle wieder einblenden (ohne Gleiten)
    card.classList.remove("nav");
    animateIn(card, "reveal");
  }
  setTimeout(() => { if (my === gt.token) gtPlace(); }, 450);   // nach Ende der Seitenanimation nachjustieren
  if (step.words) gtWords();
}
function gtPlace(override) {
  const step = TOUR[gt.i];
  if (!override && step.more && $("moreMenu").classList.contains("hidden")) $("moreBtn").click();   // Menü ggf. wieder öffnen
  const el = override || gtTarget(step), spot = $("gtSpot"), card = $("gtCard");
  const vw = window.innerWidth, vh = window.innerHeight, pad = 8, gap = 16;
  const cw = card.offsetWidth, ch = card.offsetHeight;
  if (!el) {                                           // kein Ziel → Karte mittig, Spotlight schrumpft weg
    spot.classList.add("none");
    Object.assign(spot.style, { translate: `${vw / 2}px ${vh / 2}px`, width: "0px", height: "0px", borderRadius: "50%" });
    gtMoveCard((vw - cw) / 2, (vh - ch) / 2);
    return;
  }
  spot.classList.remove("none");
  el.scrollIntoView?.({ block: "nearest" });
  const r0 = el.getBoundingClientRect();
  const r = { left: Math.max(6, r0.left - pad), top: Math.max(6, r0.top - pad), right: Math.min(vw - 6, r0.right + pad), bottom: Math.min(vh - 6, r0.bottom + pad) };
  r.width = r.right - r.left; r.height = r.bottom - r.top;
  Object.assign(spot.style, { translate: `${r.left}px ${r.top}px`, width: `${r.width}px`, height: `${r.height}px`, borderRadius: `${Math.min(18, r.height / 2)}px` });
  let x, y;                                            // Karte: rechts, unten, oben, links – was zuerst passt
  if (r.right + gap + cw < vw - 8 && r.width < vw * 0.5) { x = r.right + gap; y = r.top + r.height / 2 - ch / 2; }
  else if (r.bottom + gap + ch < vh - 8) { x = r.left + r.width / 2 - cw / 2; y = r.bottom + gap; }
  else if (r.top - gap - ch > 8) { x = r.left + r.width / 2 - cw / 2; y = r.top - gap - ch; }
  else if (r.left - gap - cw > 8) { x = r.left - gap - cw; y = r.top + r.height / 2 - ch / 2; }
  else { x = (vw - cw) / 2; y = vh - ch - 16; }
  gtMoveCard(Math.max(12, Math.min(vw - cw - 12, x)), Math.max(12, Math.min(vh - ch - 12, y)));
}
/** Karte verschieben – nur wenn sich wirklich etwas ändert (sonst „zuckt“ sie beim Nachjustieren). */
function gtMoveCard(x, y) {
  const card = $("gtCard"), last = gt.cardPos;
  if (last && Math.abs(last.x - x) < 2 && Math.abs(last.y - y) < 2) return;
  gt.cardPos = { x, y };
  card.style.translate = `${Math.round(x)}px ${Math.round(y)}px`;
}
function gtWords() {                                   // Wortmarkierung im Beispieltext vorführen
  if (!st.doc?.demo) return;
  const saved = st.settings.mark;
  if (saved === "section") st.settings.mark = "word";
  buildWords(st.idx);
  st.settings.mark = saved;
  if (!st.words) return;
  let k = 0;
  gt.wordsTimer = setInterval(() => {
    const W = st.words; if (!W) return clearInterval(gt.wordsTimer);
    const s = W.list[k].sent;
    W.list.forEach((x, n) => { x.el.classList.toggle("wc", n === k); x.el.classList.toggle("ws", x.sent === s); });
    k = (k + 1) % W.list.length;
  }, 330);
}
window.addEventListener("resize", () => { if (!$("gt").classList.contains("hidden")) gtPlace(gt.override || undefined); });
document.addEventListener("keydown", (e) => {
  if ($("gt").classList.contains("hidden")) return;
  e.stopPropagation();
  if (e.key === "Escape") { e.preventDefault(); gtEnd(); }
  else if (e.key === "ArrowRight" || e.key === "Enter") { e.preventDefault(); $("gtNext").click(); }
  else if (e.key === "ArrowLeft") { e.preventDefault(); $("gtBack")?.click(); }
}, true);

/* ===================================================================== */
/* Start                                                                  */
/* ===================================================================== */
(async () => {
  try { const r = localStorage.getItem("vorleser.rate"); if (r) $("rate").value = r; } catch {}
  const [settings] = await Promise.all([api("/api/settings"), reloadVoices()]);
  st.settings = settings;
  if ((settings.uiLang || "de") !== UI_LANG) setUiLang(settings.uiLang || "de");
  applyTheme(); renderSettings(); renderPlay();
  $("dictTab").classList.toggle("hidden", !st.features.dictate);
  fillLangSelect();
  const docs = await refreshLibrary();
  const h = location.hash.slice(1);
  if (h.startsWith("einstellungen")) {
    showView("settings");
    const tab = h.split("/")[1];
    if (tab) document.querySelector(`#setTabs [data-tab="${tab}"]`)?.click(); else renderSettings();
  } else if (h === "neu" || !docs.length) showNew();
  else { await openDoc(docs[0].id); if (h === "bearbeiten") openEditor(); }
  if (h === "tutorial" || h.startsWith("rundgang")) gtStart(false, (parseInt(h.split("/")[1], 10) || 1) - 1);
  else if (!st.settings.onboarded || h === "willkommen") onbOpen("setup");
})();

setInterval(() => { if (!document.hidden && $("libMenu").classList.contains("hidden")) renderLibrary(); }, 60000);   // „Gestern“/Uhrzeit aktuell halten

/* ===================================================================== */
/* Updates (Desktop-App)                                                  */
/* ===================================================================== */
const upd = { s: null, timer: 0 };
const updLaterKey = "vorleser.updLater";
function updDismissed(v) {
  try { const d = JSON.parse(localStorage.getItem(updLaterKey) || "null"); return d && d.v === v && Date.now() < d.until; } catch { return false; }
}
function updShow(on) {
  const el = $("upd");
  if (on) { el.classList.remove("hidden", "leaving"); return; }
  if (el.classList.contains("hidden") || el.classList.contains("leaving")) return;
  el.classList.add("leaving");
  setTimeout(() => { el.classList.add("hidden"); el.classList.remove("leaving"); }, 250);
}
function openExternal(url) {
  const a = document.createElement("a"); a.href = url; a.target = "_blank"; a.rel = "noopener"; a.click();
}
function updRender() {
  const s = upd.s; if (!s || !s.enabled) return;
  // Wechsel Knöpfe ↔ Ladebalken (z. B. nach „Aktualisieren“): Karte ändert ihre Höhe weich, Balken bzw.
  // Knöpfe und Texte gleiten einmal herein.
  const card = $("upd"), busy = ["downloading", "preparing", "installing"].includes(s.state);
  const flip = !card.classList.contains("hidden") && !card.classList.contains("leaving") && card.classList.contains("busy") !== busy;
  const done = flip ? heightFrom(card) : null;
  updRenderCard();
  if (flip) { done(480); animateIn(busy ? $("updBar") : $("updBtns")); animateIn(card.querySelector(".upd-body"), "swap"); }
}
function updRenderCard() {
  const s = upd.s, card = $("upd");
  card.classList.remove("news"); updIcon("i-dl"); $("updLater").textContent = "Später";
  $("updRow").classList.remove("hidden");
  $("verTxt").textContent = `Version ${s.current}`;
  $("updNote").textContent = s.available ? `Version ${s.latest} ist verfügbar` : s.latest ? "Du hast die neueste Version" : "Prüft bei jedem Start automatisch";
  const busy = s.state === "downloading" || s.state === "preparing" || s.state === "installing";
  $("upd").classList.toggle("busy", busy);
  $("updBar").classList.toggle("hidden", !busy);
  $("updBtns").classList.toggle("hidden", busy);
  if (s.state === "downloading") {
    const pct = s.total ? Math.round((s.done / s.total) * 100) : 0;
    $("updTitle").textContent = "Update wird geladen";
    $("updText").textContent = s.total ? `${fmtMB(s.done)} von ${fmtMB(s.total)}` : "";
    $("updFill").style.width = `${pct}%`;
    return updShow(true);
  }
  if (s.state === "preparing") {
    $("updTitle").textContent = "Update wird vorbereitet";
    $("updText").textContent = "Einen Moment – du kannst weiter vorlesen.";
    $("updFill").style.width = "100%";
    return updShow(true);
  }
  if (s.state === "ready") {
    $("updTitle").textContent = "Update bereit";
    $("updText").textContent = `Version ${s.readyVersion} startet beim nächsten Öffnen von Vorleser – oder gleich jetzt.`;
    $("updGo").textContent = "Jetzt neu starten";
    return upd.later ? updShow(false) : updShow(true);
  }
  if (s.state === "installing") {
    $("updTitle").textContent = "Startet neu …";
    $("updText").textContent = "Vorleser ist gleich in der neuen Version zurück.";
    $("updFill").style.width = "100%";
    return updShow(true);
  }
  if (s.state === "error") {
    $("updTitle").textContent = "Update fehlgeschlagen";
    $("updText").textContent = `${s.error || ""} – du kannst die neue Version auch von der Webseite laden.`;
    $("updGo").textContent = "Download-Seite";
    return updShow(true);
  }
  if (newsPending()) {                                  // gerade aktualisiert → einmal zeigen, was neu ist
    card.classList.add("news"); updIcon("i-check");
    $("updTitle").textContent = `Auf Version ${s.current} aktualisiert`;
    $("updText").textContent = news.data?.releases.find((r) => r.version === s.current)?.lead || "";
    $("updLater").textContent = "Schließen";
    $("updGo").textContent = "Was ist neu";
    if (!news.data) newsLoad().then(() => newsPending() && updRender()).catch(() => {});
    return updShow(true);
  }
  if (s.available && !updDismissed(s.latest)) {
    $("updTitle").textContent = `Vorleser ${s.latest} ist da`;
    const first = (s.notes || "").split("\n").map((x) => x.trim()).find((x) => x && !/^https?:/.test(x)) || "";
    $("updText").textContent = s.canInstall
      ? [first, "Wird im Hintergrund geladen, du kannst weiter vorlesen."].filter(Boolean).join(" ")
      : s.reason;
    $("updGo").textContent = s.canInstall ? "Aktualisieren" : "Download-Seite";
    return updShow(true);
  }
  updShow(false);
}
async function updRefresh(force = false) {
  clearTimeout(upd.timer);
  try { upd.s = await api(force ? "/api/update/check" : "/api/update", force ? { method: "POST" } : {}); } catch { return null; }
  if (upd.s.justUpdated) {
    try { if (localStorage.getItem(NEWS_SEEN) !== upd.s.justUpdated) localStorage.setItem(NEWS_PENDING, upd.s.justUpdated); } catch {}
  }
  updRender();
  if (["downloading", "preparing", "installing"].includes(upd.s.state)) upd.timer = setTimeout(updRefresh, 600);
  else if (upd.s.enabled && !upd.s.checked && (upd.polls = (upd.polls || 0) + 1) < 60) upd.timer = setTimeout(updRefresh, 2000);   // erste Prüfung nach dem Start abwarten
  return upd.s;
}
$("updLater").onclick = () => {
  if ($("upd").classList.contains("news")) { newsSeen(); return updShow(false); }
  if (upd.s?.state === "ready") { upd.later = true; return updShow(false); }   // wird beim Beenden eingespielt
  try { localStorage.setItem(updLaterKey, JSON.stringify({ v: upd.s?.latest, until: Date.now() + 24 * 3600e3 })); } catch {}
  updShow(false);
};
$("updGo").onclick = async () => {
  const s = upd.s; if (!s) return;
  if ($("upd").classList.contains("news")) { newsSeen(); updShow(false); return openNews(); }
  if (s.state === "ready") {
    try { upd.s = await api("/api/update/restart", { method: "POST" }); } catch (e) { return toastErr(e); }
    return updRender();
  }
  if (!s.canInstall || s.state === "error") return openExternal(s.page);
  try { upd.s = await api("/api/update/install", { method: "POST" }); } catch (e) { return toastErr(e); }
  updRender();
  upd.timer = setTimeout(updRefresh, 400);
};
function updIcon(id) { $("updIc").querySelector("use")?.setAttribute("href", `#${id}`); }

/* ---------- Was ist neu (Versionsverlauf aus CHANGELOG.md) ---------- */
const NEWS_PENDING = "vorleser.newsPending", NEWS_SEEN = "vorleser.newsSeen";
const news = { data: null };
function newsPending() {
  try { const v = localStorage.getItem(NEWS_PENDING); return !!v && v === upd.s?.current && localStorage.getItem(NEWS_SEEN) !== v; } catch { return false; }
}
function newsSeen() {
  try { localStorage.setItem(NEWS_SEEN, upd.s?.current || ""); localStorage.removeItem(NEWS_PENDING); } catch {}
}
async function newsLoad() { return (news.data ||= await api("/api/changelog")); }
const mdBold = (t) => esc(t).replace(/\*\*(.+?)\*\*/g, "<b>$1</b>");
async function openNews() {
  let d; try { d = await newsLoad(); } catch (e) { return toastErr(e); }
  const cur = d.current;
  $("newsSub").textContent = d.releases.some((r) => r.version === cur) ? `Du hast Version ${cur} · alle Versionen, neueste zuerst` : "Alle Versionen, neueste zuerst";
  $("newsList").innerHTML = d.releases.map((r) => `<section class="rel${r.version === cur ? " now" : ""}">
      <div class="rel-h"><b>${esc(r.version)}</b>${r.version === cur ? `<span class="rel-chip">${UI_LANG === "en" ? "Installed" : "Installiert"}</span>` : ""}</div>
      ${r.lead ? `<p class="lead">${mdBold(r.lead)}</p>` : ""}
      ${r.items.length ? `<ul>${r.items.map((i) => `<li>${mdBold(i)}</li>`).join("")}</ul>` : ""}</section>`).join("");
  $("newsList").scrollTop = 0;
  $("newsBug").classList.toggle("hidden", !bug.info?.enabled);
  $("newsDlg").showModal();
}
$("newsBtn").onclick = openNews;
$("betaBtn").onclick = openNews;
$("newsClose").onclick = () => $("newsDlg").close();
$("newsBug").onclick = (e) => { e.preventDefault(); $("newsDlg").close(); openBug(); };

$("srcBtn").onclick = () => openExternal("https://github.com/SimonSchneZzer/vorleser");
$("updCheck").onclick = async () => {
  const b = $("updCheck"); b.disabled = true;
  const s = await updRefresh(true);
  b.disabled = false;
  if (!s) return toast("Prüfen fehlgeschlagen – bist du online?", true);
  if (s.available) { try { localStorage.removeItem(updLaterKey); } catch {} updRender(); }
  else toast(s.latest ? `Du hast die neueste Version (${s.current})` : "Keine Update-Information gefunden");
};
/* ===================================================================== */
/* Fehler melden (über Web3Forms; Empfängeradresse steht nicht in der App) */
/* ===================================================================== */
const bug = { info: null };
const BUG_LIMIT = 3;                                    // Meldungen pro Stunde (Schutz vor Doppelklicks/Spam)
function bugRecent() {
  try { return JSON.parse(localStorage.getItem("vorleser.bugs") || "[]").filter((t) => Date.now() - t < 3600e3); } catch { return []; }
}
function bugTechText() {
  const i = bug.info; if (!i) return "";
  return [`Version: ${i.version} (${i.mode})`, `System: ${i.system}`, `Oberfläche: ${UI_LANG}`,
          `Ansicht: ${view}${st.doc ? ` · Text-Sprache ${st.doc.lang} · Stimme ${st.doc.voice}` : ""}`,
          "", "Letzte Log-Zeilen:", i.log || "(leer)"].join("\n");
}
async function bugInit() {
  try { bug.info = await api("/api/bugreport"); } catch { return; }
  $("bugRow").classList.toggle("hidden", !bug.info.enabled);
  $("bugSideBtn").classList.toggle("hidden", !bug.info.enabled);
}
function openBug() {
  if (!bug.info?.enabled) return;
  $("bugForm").classList.remove("hidden", "sending");
  $("bugOk").classList.add("hidden");
  $("bugMsgInfo").textContent = "";
  $("bugMsg").classList.remove("bad");
  api("/api/bugreport").then((i) => { bug.info = i; $("bugTechText").textContent = bugTechText(); }).catch(() => {});
  $("bugTechText").textContent = bugTechText();
  $("bugDlg").showModal();
  setTimeout(() => $("bugMsg").focus(), 50);
}
$("bugBtn").onclick = openBug;
$("bugSideBtn").onclick = openBug;
for (const id of ["bugMsg", "bugMail"]) $(id).addEventListener("input", () => { $(id).classList.remove("bad"); $("bugMsgInfo").textContent = ""; });
$("bugCancel").onclick = () => $("bugDlg").close();
$("bugDone").onclick = () => $("bugDlg").close();
$("bugForm").onsubmit = async (e) => {
  e.preventDefault();
  const msg = $("bugMsg").value.trim(), mail = $("bugMail").value.trim();
  if (msg.length < 5) {
    $("bugMsg").classList.remove("bad"); void $("bugMsg").offsetWidth; $("bugMsg").classList.add("bad");
    $("bugMsgInfo").textContent = "Bitte kurz beschreiben, was passiert ist.";
    return $("bugMsg").focus();
  }
  if (mail && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(mail)) {
    $("bugMsgInfo").textContent = "Die E-Mail-Adresse sieht nicht richtig aus.";
    return $("bugMail").focus();
  }
  const recent = bugRecent();
  if (recent.length >= BUG_LIMIT) { $("bugMsgInfo").textContent = "Bitte warte etwas, bevor du noch eine Meldung schickst."; return; }
  const i = bug.info;
  const payload = {
    access_key: i.key, botcheck: $("bugBot").checked,
    subject: `Vorleser ${i.version} – Fehlermeldung (${i.system.split(",")[0]})`,
    from_name: "Vorleser Fehlermelder",
    Beschreibung: msg,
    "Antwort an": mail || "(keine Angabe)",
    ...(mail ? { email: mail, replyto: mail } : {}),
    ...($("bugTech").checked ? { "Technische Infos": bugTechText() } : { "Technische Infos": "(nicht mitgeschickt)" }),
  };
  $("bugForm").classList.add("sending");
  $("bugMsgInfo").textContent = "Wird gesendet …";
  try {
    // Als klassische Formulardaten (kein JSON): „einfache“ CORS-Anfrage ohne Preflight – den blockt Web3Forms
    const form = new FormData();
    for (const [k, v] of Object.entries(payload)) form.append(k, typeof v === "boolean" ? (v ? "true" : "") : v);
    const r = await fetch(i.endpoint, { method: "POST", headers: { Accept: "application/json" }, body: form });
    const res = await r.json().catch(() => ({}));
    if (!r.ok || !res.success) throw new Error(res.message || `HTTP ${r.status}`);
    try { localStorage.setItem("vorleser.bugs", JSON.stringify([...recent, Date.now()])); } catch {}
    $("bugMsg").value = "";
    $("bugOkText").textContent = mail ? "Sie ist bei Simon angekommen. Bei Rückfragen meldet er sich per E-Mail." : "Sie ist bei Simon angekommen.";
    $("bugForm").classList.add("hidden");
    $("bugOk").classList.remove("hidden");
  } catch (err) {
    $("bugForm").classList.remove("sending");
    $("bugMsgInfo").textContent = /Failed to fetch|NetworkError|Load failed/i.test(err.message)
      ? "Senden fehlgeschlagen – bist du online?" : `Senden fehlgeschlagen: ${err.message}`;
  }
};
bugInit();

/* ===================================================================== */
/* Deinstallieren (Desktop-App) – mit Warnung und zweitem Bestätigungsklick */
/* ===================================================================== */
const unin = { info: null, sure: false, t: 0 };
api("/api/uninstall").then((i) => { unin.info = i; $("uninRow").classList.toggle("hidden", !i.possible); }).catch(() => {});
function uninList(r) {
  const keep = $("uninKeep").checked;
  const own = new Set(st.voices.filter((v) => v.engine === "clone").map((v) => v.id)).size;
  const n = st.docs.length;
  const rows = [
    ["Die App selbst", ""],
    [`Deine Texte und Lesezeichen (${n})`, r ? fmtMB(r.texts) : "", "keep"],
    [own ? `Eigene Stimmen (${own})` : "Eigene Stimmen", "", "keep"],
    ["Einstellungen", "", "keep"],
    ["Erzeugtes Audio und Exporte", r ? fmtMB(r.audio + r.exports) : ""],
    ["Modelle (Diktat, eigene Stimme)", r ? fmtMB(r.whisper.bytes + r.clone.bytes) : ""],
  ];
  $("uninList").innerHTML = rows.map(([t, size, k]) => {
    const kept = keep && k === "keep";
    return `<li class="${kept ? "kept" : ""}"><span>${esc(t)}</span><span>${kept ? "bleibt" : esc(size)}</span></li>`;
  }).join("");
}
function uninReset() {
  unin.sure = false; clearTimeout(unin.t);
  $("uninGo").classList.remove("sure");
  $("uninGo").textContent = "Deinstallieren";
  $("uninWarn").textContent = $("uninKeep").checked ? "Texte und eigene Stimmen bleiben im Datenordner erhalten." : "Das lässt sich nicht rückgängig machen.";
  $("uninWarn").classList.toggle("ok", $("uninKeep").checked);
}
$("uninBtn").onclick = async () => {
  $("uninAsk").classList.remove("hidden"); $("uninBye").classList.add("hidden");
  $("uninKeep").checked = false;
  uninReset(); uninList(null);
  $("uninDlg").showModal();
  $("uninCancel").focus();                                // sicherer Standard: Abbrechen
  try { uninList(await api("/api/storage")); } catch {}
};
$("uninKeep").onchange = () => { uninReset(); api("/api/storage").then(uninList).catch(() => uninList(null)); };
$("uninCancel").onclick = () => $("uninDlg").close();
$("uninDlg").addEventListener("close", uninReset);
$("uninGo").onclick = async () => {
  if (!unin.sure) {                                       // erster Klick: nochmal ausdrücklich fragen
    unin.sure = true;
    $("uninGo").textContent = $("uninKeep").checked ? "Wirklich deinstallieren?" : "Wirklich alles löschen?";
    $("uninGo").classList.remove("sure"); void $("uninGo").offsetWidth; $("uninGo").classList.add("sure");
    unin.t = setTimeout(uninReset, 5000);                 // ohne zweiten Klick zurücksetzen
    return;
  }
  clearTimeout(unin.t);
  try {
    if (st.wantPlay) pause();
    await api("/api/uninstall", { method: "POST", body: JSON.stringify({ keepData: $("uninKeep").checked }) });
    $("uninAsk").classList.add("hidden"); $("uninBye").classList.remove("hidden");
  } catch (e) { uninReset(); toastErr(e); }
};

setInterval(() => { if (!upd.s || upd.s.state === "idle") updRefresh(); }, 60000);   // Server prüft minütlich (latest.json)
updRefresh();                                     // Version, „aktualisiert“-Hinweis; fragt nach, bis die erste Prüfung durch ist   // „Gestern“/Uhrzeit aktuell halten
