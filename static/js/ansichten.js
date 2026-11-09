"use strict";
// Vorleser – Ansichten, Seitenleiste, Bibliothek, Tooltips. Teil der Oberfläche; Reihenfolge der Dateien: index.html
/* ===================================================================== */
/* Ansichten & Seitenleiste                                               */
/* ===================================================================== */
/* ===================== Bewegungsmodell (Navigation) =====================
   senkrecht = Seitenleiste: der neue Inhalt kommt aus der Richtung, in der sein Eintrag liegt (Neuer Text oben,
   Texte in Reihenfolge, Einstellungen unten); waagrecht = Tabs; Tiefe = Unterseite (Text bearbeiten).
   Alter und neuer Inhalt bewegen sich beide (der alte als Abbild darüber) – kein Schnitt. */
const NAV_MOVE = { down: ["translateY(26px)", "translateY(-26px)"], up: ["translateY(-26px)", "translateY(26px)"],
  right: ["translateX(32px)", "translateX(-32px)"], left: ["translateX(-32px)", "translateX(32px)"],
  deeper: ["scale(.965)", "scale(1.03)"], back: ["scale(1.03)", "scale(.965)"] };
function navIn(el, how) {
  if (!el?.animate || !how) return;
  const rm = reducedMotion.matches;
  const kf = (blur) => [{ opacity: 0, transform: rm ? "none" : NAV_MOVE[how][0], ...(blur ? { filter: rm ? "none" : "blur(4px)" } : {}) },
    { opacity: 1, transform: "none", ...(blur ? { filter: "blur(0)" } : {}) }];
  const opt = { duration: 360, easing: EASE_OUT, fill: "backwards" };
  // Glas-Leisten (backdrop-filter) dürfen keinen Vorfahren mit filter/opacity haben – sonst rendert WebKit die Unschärfe
  // erst nach der Animation (Titel unter der Leiste kurz scharf). Darum die Kinder einzeln animieren, die Leiste ohne Filter.
  const kids = [...el.children], glass = kids.filter((c) => c.matches(".topbar"));
  if (!glass.length) return void el.animate(kf(true), opt);
  for (const c of kids) c.animate(kf(!glass.includes(c)), opt);
}
/** Abbild von el (an gleicher Stelle, gleicher Scroll-Stand) – damit der alte Inhalt hinausgleiten kann. */
function ghostOf(el) {
  if (!el || el.classList.contains("hidden") || !el.offsetParent || !el.animate) return null;
  const all = el.querySelectorAll("*"), pos = [];
  all.forEach((n, i) => { if (n.scrollTop) pos.push([i, n.scrollTop]); });
  const g = el.cloneNode(true);
  g.removeAttribute("id"); g.querySelectorAll("[id]").forEach((n) => n.removeAttribute("id"));
  g.classList.add("nav-ghost"); g.setAttribute("aria-hidden", "true"); g.inert = true;
  Object.assign(g.style, { position: "absolute", top: `${el.offsetTop}px`, left: `${el.offsetLeft}px`,
    width: `${el.offsetWidth}px`, height: `${el.offsetHeight}px`, margin: "0" });
  const par = el.parentElement;
  if (getComputedStyle(par).position === "static") par.style.position = "relative";
  par.appendChild(g);
  const gall = g.querySelectorAll("*");
  pos.forEach(([i, t]) => { if (gall[i]) gall[i].scrollTop = t; });
  if (el.scrollTop) g.scrollTop = el.scrollTop;
  return g;
}
function navOut(g, how) {
  if (!g) return;
  if (!how || reducedMotion.matches) {
    const a = g.animate([{ opacity: 1 }, { opacity: 0 }], { duration: 200, easing: EASE, fill: "forwards" });
    return void (a.onfinish = () => g.remove());
  }
  const a = g.animate([{ opacity: 1, transform: "none", filter: "blur(0)" }, { opacity: 0, transform: NAV_MOVE[how][1], filter: "blur(4px)" }],
    { duration: 300, easing: EASE, fill: "forwards" });
  a.onfinish = () => g.remove();
}
/** Lage in der Seitenleiste: Neuer Text oben, dann die Texte in ihrer Reihenfolge, Einstellungen unten. */
function viewRank(name) {
  if (name === "new") return -1;
  if (name === "settings") return 1e6;
  const i = st.docs.findIndex((d) => d.id === st.doc?.id);
  return i < 0 ? 0 : i;
}
let navRank = 0;
let view = "read";
const VIEWS = { read: "viewRead", new: "viewNew", settings: "viewSettings", edit: "viewEdit" };
function showView(name) {
  const prev = view, changed = prev !== name;
  let how = null, ghost = null;
  if (changed) {
    how = name === "edit" ? "deeper" : prev === "edit" && name === "read" ? "back" : viewRank(name) >= navRank ? "down" : "up";
    ghost = ghostOf($(VIEWS[prev]));
  }
  view = name;
  for (const [k, id] of Object.entries(VIEWS)) $(id).classList.toggle("hidden", k !== name);
  if (changed) {
    navIn($(VIEWS[name]), how); navOut(ghost, how);
    // Markierungen erst nach dem Hereingleiten neu anlegen – mitten in der Bewegung gemessen sitzen sie daneben
    if (name === "read") {
      const rd = $("reader"); rd.classList.add("marks-wait");
      setTimeout(() => {
        rd.classList.remove("marks-wait");
        if (view !== "read") return;
        window.replaceMarks?.();
        for (const m of rd.querySelectorAll(":scope > #wbox, :scope > #sboxes")) m.animate?.([{ opacity: 0 }, { opacity: 1 }], { duration: 220, easing: EASE });
      }, 400);
    }
  }
  navRank = viewRank(name);
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
function slideBar(el, on, after, fromTop = false) {
  if (el._on === on) return;
  el._on = on;
  el._pa?.cancel(); el._pa = null;
  const vis = !el.classList.contains("hidden");
  if (on === vis || reducedMotion.matches || !el.animate) { el.classList.toggle("hidden", !on); return after?.(); }
  if (on) {
    el.classList.remove("hidden"); after?.();
    const h = el.offsetHeight;
    const hide = fromTop ? { marginTop: `${-h}px`, transform: "translateY(-60%)", opacity: 0 } : { marginBottom: `${-h}px`, transform: "translateY(100%)", opacity: 0 };
    el._pa = el.animate([hide, { marginTop: "0px", marginBottom: "0px", transform: "none", opacity: 1 }], { duration: 520, easing: EASE_OUT });
  } else {
    const h = el.offsetHeight;
    const hide = fromTop ? { marginTop: `${-h}px`, transform: "translateY(-60%)", opacity: 0 } : { marginBottom: `${-h}px`, transform: "translateY(100%)", opacity: 0 };
    const a = el._pa = el.animate([{ marginTop: "0px", marginBottom: "0px", transform: "none", opacity: 1 }, hide], { duration: 320, easing: EASE, fill: "forwards" });
    a.onfinish = () => { el.classList.add("hidden"); a.cancel(); after?.(); };
  }
}
const setPlayer = (on) => slideBar($("player"), on, syncPlayerHeight);
// Glas-Kopf der Einstellungen liegt über dem Inhalt → Inhalt beginnt darunter (Höhe gemessen)
new ResizeObserver(() => document.documentElement.style.setProperty("--sethead-h", `${document.querySelector("#viewSettings .set-head").offsetHeight}px`))
  .observe(document.querySelector("#viewSettings .set-head"));
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
/** „…“-Menü eines Bibliothekseintrags – am Knopf oder (Rechtsklick) an der Maus. */
function libMenuOpen(dots, at) {
  const m = $("libMenu"), was = libMenuFor === dots.dataset.dots && !m.classList.contains("hidden") && !m.classList.contains("leaving");
  closePops(true);
  if (was && !at) return;
  libMenuFor = dots.dataset.dots;
  dots.classList.add("open"); dots.closest("li").classList.add("menu-open");
  openPop(m);
  const r = at ? { left: at.x, right: at.x, top: at.y, bottom: at.y } : dots.getBoundingClientRect();
  const below = r.bottom + 6 + m.offsetHeight < window.innerHeight - 8;
  m.style.left = `${Math.max(8, Math.min(r.left, window.innerWidth - m.offsetWidth - 12))}px`;
  m.style.top = below ? `${r.bottom + 6}px` : `${r.top - 6 - m.offsetHeight}px`;
  m.style.setProperty("--origin", below ? "top left" : "bottom left");
}
// Rechtsklick auf einen Eintrag = dasselbe Menü wie „…“ (Tester-Rückmeldung)
$("library").addEventListener("contextmenu", (e) => {
  const dots = e.target.closest("li")?.querySelector("[data-dots]");
  if (!dots) return;
  e.preventDefault();
  getSelection()?.removeAllRanges();                      // Mac markiert beim Rechtsklick sonst das Wort
  libMenuOpen(dots, { x: e.clientX, y: e.clientY });
});
$("library").onclick = async (e) => {
  const dots = e.target.closest("[data-dots]");
  if (dots) {
    e.preventDefault(); e.stopPropagation();
    libMenuOpen(dots);
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
  try { await api(`/api/docs/${id}`, { method: "DELETE" }); } catch (e) { return toastErr(e); }
  const cur = st.doc?.id === id;
  if (cur) stop();
  const li = $("library").querySelector(`a[data-id="${id}"]`)?.closest("li");
  st.docs = st.docs.filter((x) => x.id !== id);         // falls zwischendurch neu gezeichnet wird: bleibt weg
  await collapseOut(li);
  if (cur) {                                            // nur von der Textseite weg – in Einstellungen/Neuer Text bleiben
    st.doc = null;
    if (view === "read" || view === "edit") showNew();
    else { setPlayer(false); mlSync(); }
  }
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
/** Strich unter dem Tab wie ein Gummiband: die vordere Kante zieht zuerst, die hintere folgt. */
function moveInk() {
  const on = document.querySelector("#setTabs button.on"), ink = $("tabInk");
  if (!on || !on.offsetWidth) return;
  const W = ink.parentElement.clientWidth, left = on.offsetLeft, right = W - left - on.offsetWidth;
  const was = parseFloat(ink.style.left);
  const toRight = Number.isFinite(was) && left > was;
  const lead = ".32s cubic-bezier(.3, 1.25, .5, 1)", lag = ".4s cubic-bezier(.3, 1.1, .5, 1) .08s";
  ink.style.transition = Number.isFinite(was) && !reducedMotion.matches
    ? `left ${toRight ? lag : lead}, right ${toRight ? lead : lag}` : "none";
  Object.assign(ink.style, { transform: "none", width: "auto", left: `${left}px`, right: `${right}px` });
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

