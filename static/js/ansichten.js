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
  if (typeof nowSync === "function") nowSync();
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
  st.docsRecent = docs; st.docs = libOrdered(docs); renderLibrary();
  return docs;                                          // Server-Reihenfolge = zuletzt gehört (Start öffnet den obersten davon)
}
/* ---------- Reihenfolge der Bibliothek (3.1, Wunsch eines Nutzers) ----------
   „recent“: zuletzt gehört oben (Server sortiert). „own“: eigene Reihenfolge aus settings.libOrder; Texte, die dort
   noch fehlen (neu angelegt), stehen oben. Die eigene Reihenfolge bleibt beim Umschalten auf „recent“ gespeichert.
   st.libPreview überdeckt die Einstellungen nur für die Vorführung im Update-Tutorial (wird nie gespeichert). */
const libPrefs = () => st.libPreview || st.settings || {};
const libOwn = () => libPrefs().libSort === "own";
function libOrdered(docs) {
  const p = libPrefs();
  if (p.libSort !== "own") return docs;
  const pos = new Map((p.libOrder || []).map((id, i) => [id, i]));
  return [...docs.filter((d) => !pos.has(d.id)), ...docs.filter((d) => pos.has(d.id)).sort((a, b) => pos.get(a.id) - pos.get(b.id))];
}
/** Nach einem Wechsel der Sortierung neu ordnen – die Einträge gleiten an ihre Plätze (FLIP in renderLibrary). */
function libResort() { st.docs = libOrdered(st.docsRecent || st.docs); renderLibrary(); }
/** Neue eigene Reihenfolge übernehmen (Ziehen, Nach oben/unten) – im Tutorial nur als Vorführung. */
function libCommit(ids) {
  if (st.libPreview) { st.libPreview = { libSort: "own", libOrder: ids }; return; }
  saveSettings({ libSort: "own", libOrder: ids });
}
let libSortShown = null;
function libSortSync() {
  const b = $("libSortBtn"), own = libOwn();
  if (libSortShown === own) return;
  const strip = b.querySelector(".strip");
  if (libSortShown === null) strip.style.transition = "none";      // beim Start nicht rollen
  b.classList.toggle("own", own);
  b.dataset.tip = own ? "Deine Reihenfolge · klicken für zuletzt gehört oben" : "Zuletzt gehört oben · klicken für deine eigene Reihenfolge";
  b.setAttribute("aria-label", own ? "Sortiert nach deiner Reihenfolge – umschalten auf zuletzt gehört" : "Sortiert nach zuletzt gehört – umschalten auf deine Reihenfolge");
  if (libSortShown === null) requestAnimationFrame(() => requestAnimationFrame(() => (strip.style.transition = "")));
  libSortShown = own;
}
$("libSortBtn").onclick = () => {
  hideTip();
  if (libOwn()) saveSettings({ libSort: "recent" });
  else saveSettings({ libSort: "own", libOrder: st.settings.libOrder?.length ? st.settings.libOrder : st.docs.map((d) => d.id) });
  libResort();
};
function renderLibrary() {
  libSortSync();
  const showSearch = st.docs.length >= 7;                 // Suche erst, wenn es etwas zu suchen gibt
  $("libSearchBox").classList.toggle("hidden", !showSearch);
  if (!showSearch) $("libSearch").value = "";
  const q = $("libSearch").value.trim().toLowerCase();
  const ul = $("library");
  const docs = [...(st.demoEntry ? [st.demoEntry] : []), ...st.docs].filter((d) => !q || d.title.toLowerCase().includes(q));
  if (!docs.length) { ul.innerHTML = `<li class="empty">${q ? "Nichts gefunden." : "Noch keine Texte."}</li>`; return; }
  const ids = docs.map((d) => d.id), sig = ids.join(), prevIds = st.libSig ? st.libSig.split(",") : [];
  // Gestaffelt einblenden nur bei echtem Listenwechsel – nicht, wenn genau ein Text dazukommt oder wegfällt und nicht,
  // wenn nur die Reihenfolge wechselt (dann gleiten die Einträge an ihre neuen Plätze, 3.1).
  const sameSet = prevIds.length === ids.length && ids.every((x) => prevIds.includes(x));
  const stagger = sig !== st.libSig && !sameSet && !oneChanged(prevIds, ids); st.libSig = sig;
  // Neu angelegter Text „landet“ (Höhe wächst + Akzent leuchtet einmal auf). Läuft über Neuzeichnungen
  // hinweg weiter: negative Verzögerung = bereits vergangene Zeit.
  const ago = st.libLand ? performance.now() - st.libLand.t : Infinity;
  const land = ago < 1800 ? st.libLand.id : null;
  if (!stagger && !land && libPatch(ul, docs)) return;        // nur Zahlen geändert → an Ort und Stelle (Board 27)
  const prevPre = new Map([...ul.querySelectorAll("a[data-id]")].map((a) => [a.dataset.id, a.querySelector(".pre")?.style.width]));
  // FLIP: alte Lage jedes Eintrags merken (inkl. Verschiebung beim Ziehen), nach dem Neuzeichnen von dort hingleiten
  const prevTop = !stagger && !land && !reducedMotion.matches
    ? new Map([...ul.querySelectorAll("a[data-id]")].map((a) => [a.dataset.id, a.closest("li").getBoundingClientRect().top])) : null;
  const settle = st.libSettle; st.libSettle = null;
  ul.innerHTML = docs.map((d, n) => {
    const pct = docPct(d), state = docState(d, pct);
    const active = view === "read" && st.doc?.id === d.id ? " active" : "";
    const ts = d.progress.updated || d.created;
    const full = new Date(ts * 1000).toLocaleString(LOC(), { dateStyle: "medium", timeStyle: "short" });
    const cls = d.id === land ? "landed" : stagger ? "enter" : "";
    return `<li class="${cls}" style="--i:${Math.min(n, 12)}${d.id === land ? `;--ago:${-Math.round(ago)}ms` : ""}"><a href="#" class="${active}" data-id="${d.id}" data-k="${esc(libKey(d))}">
        <span class="row1">${jobRing(d.id)}<span class="t" data-noi18n>${esc(d.title)}</span><span class="when" title="${d.progress.updated ? "Zuletzt gehört" : "Erstellt"}: ${full}">${fmtWhen(ts)}</span></span>
        <span class="m"><b>${esc(d.lang.toUpperCase())}</b>·<span>${d.chapters ? `${d.chapters} Kapitel` : nAbschn(d.count)}</span>·<span class="st">${state}</span></span>
        <span class="bar"><i class="pre" style="width:${d.count ? Math.round((d.prepared || 0) / d.count * 100) : 0}%"></i><i class="pos" style="width:${pct}%"></i></span></a>
      <button class="dots" data-dots="${d.id}" aria-label="Aktionen für ${esc(d.title)}" aria-haspopup="menu">${icon("i-dots", "i", "width:18px;height:18px")}</button></li>`;
  }).join("");
  const li = ul.querySelector("li.landed");
  if (li) li.style.setProperty("--lh", `${li.firstElementChild.offsetHeight}px`);
  if (prevTop) for (const a of ul.querySelectorAll("a[data-id]")) {
    const was = prevTop.get(a.dataset.id), li2 = a.closest("li");
    if (was == null || !li2.animate) continue;
    const dy = was - li2.getBoundingClientRect().top, mine = a.dataset.id === settle;
    if (Math.abs(dy) < 0.5 && !mine) continue;
    li2.animate([{ transform: `translateY(${dy}px)` }, { transform: "none" }],
      mine ? { duration: 400, easing: "cubic-bezier(.34, 1.42, .64, 1)" } : { duration: 420, easing: EASE_OUT });
    if (mine && st.libLift) a.animate([{ transform: "scale(1.03)", boxShadow: "0 14px 30px rgba(0,0,0,.28)" }, { transform: "none", boxShadow: "none" }], { duration: 380, easing: EASE_OUT });
  }
  st.libLift = false;
  // „Vorbereitet“-Balken gleitet vom alten zum neuen Stand (z. B. nach dem Löschen des Audios), statt zu springen
  for (const d of docs) {
    const from = prevPre.get(d.id), bar = ul.querySelector(`[data-id="${d.id}"] .pre`);
    if (from != null && bar && from !== bar.style.width && bar.animate && !reducedMotion.matches)
      bar.animate([{ width: from }, { width: bar.style.width }], { duration: 520, easing: EASE });
  }
}
/** Was sich an einem Eintrag nur durch Neuzeichnen ändern lässt (Titel, Sprache, Umfang). */
function libKey(d) { return `${d.title}\u0001${d.lang}\u0001${d.chapters || 0}\u0001${d.count}`; }
/** Gleiche Einträge in gleicher Reihenfolge → nur Ring, Stand, Zeit und Balken anpassen statt die Liste neu zu bauen.
 *  Sonst (Abfrage alle 2 s beim Vorbereiten) gingen Hover/Fokus verloren und die „…“-Knöpfe flackerten. */
function libPatch(ul, docs) {
  const as = [...ul.querySelectorAll("a[data-id]")];
  if (as.length !== docs.length || as.some((a, i) => a.dataset.id !== docs[i].id || a.dataset.k !== libKey(docs[i]))) return false;
  docs.forEach((d, i) => {
    const a = as[i], pct = docPct(d), state = docState(d, pct), ts = d.progress.updated || d.created;
    a.classList.toggle("active", view === "read" && st.doc?.id === d.id);
    const row = a.querySelector(".row1"), old = row.querySelector(".jobring"), ring = jobRing(d.id);
    if (!ring) old?.remove();
    else if (old?.dataset.h !== ring) {
      const t = document.createElement("template"); t.innerHTML = ring;
      const svg = t.content.firstElementChild; svg.dataset.h = ring;
      old ? old.replaceWith(svg) : row.prepend(svg);
    }
    rollText(a.querySelector(".st"), state);
    const w = a.querySelector(".when"), wt = fmtWhen(ts); if (w.textContent !== wt) w.textContent = wt;
    w.title = `${d.progress.updated ? "Zuletzt gehört" : "Erstellt"}: ${new Date(ts * 1000).toLocaleString(LOC(), { dateStyle: "medium", timeStyle: "short" })}`;
    a.querySelector(".pre").style.width = `${d.count ? Math.round((d.prepared || 0) / d.count * 100) : 0}%`;
    a.querySelector(".pos").style.width = `${pct}%`;
  });
  return true;
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
  rollText(a.querySelector(".st"), state);
}
let libMenuFor = null;
/** „…“-Menü eines Bibliothekseintrags – am Knopf oder (Rechtsklick) an der Maus. */
function libMenuOpen(dots, at) {
  const m = $("libMenu"), was = libMenuFor === dots.dataset.dots && !m.classList.contains("hidden") && !m.classList.contains("leaving");
  closePops(true);
  if (was && !at) return;
  libMenuFor = dots.dataset.dots;
  const playing = st.doc?.id === libMenuFor && st.wantPlay;   // erster Eintrag: Abspielen bzw. Pause
  $("libPlayLbl").textContent = playing ? "Pause" : "Abspielen";
  $("libPlayIc").innerHTML = `<use href="#${playing ? "i-pause" : "i-play"}"/>`;
  const k = st.docs.findIndex((d) => d.id === libMenuFor), lock = !!$("libSearch").value.trim() || k < 0;
  $("libUp").disabled = lock || k === 0; $("libDown").disabled = lock || k === st.docs.length - 1;
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
  if (a) { e.preventDefault(); if (view === "edit" && edDirty() && !(await askDiscard())) return; showOrOpen(a.dataset.id); }
};
$("libMenu").onclick = async (e) => {
  const b = e.target.closest("[data-act]"); if (!b || !libMenuFor) return;
  const id = libMenuFor; closePops();
  if (b.dataset.act === "delete") return deleteDoc(id);
  if (b.dataset.act === "up" || b.dataset.act === "down") return libMove(id, b.dataset.act === "up" ? -1 : 1);
  if (view === "edit" && edDirty() && !(await askDiscard())) return;
  if (b.dataset.act === "play") {                         // Abspielen direkt aus der Bibliothek (Simon, 10.11.2026)
    const same = st.doc?.id === id && !st.doc.demo;
    await showOrOpen(id);
    if (same && st.wantPlay) pause(); else play();
    return;
  }
  await showOrOpen(id);
  if (b.dataset.act === "edit") openEditor();
  if (b.dataset.act === "export") $("exportBtn").click();
};
/** Text zeigen: ist es der geöffnete, nur zurück zur Leseansicht – neu laden würde die Wiedergabe anhalten
 *  (Simon, 10.11.2026: abspielen → Einstellungen → zurück zum Text hielt an). */
async function showOrOpen(id) {
  if (st.doc?.id === id && !st.doc.demo) {
    if (view !== "read") { showView("read"); highlight(true); }
    return;
  }
  await openDoc(id);
}
const askDiscard = () => ask({ title: "Änderungen verwerfen?", text: "Deine Änderungen am Text gehen verloren.", ok: "Verwerfen", danger: true, icon: "i-pen" });
$("libSearch").oninput = renderLibrary;
/** „…“ › Nach oben / Nach unten: eine Stelle weiter, gleitet und rastet ein (schaltet auf die eigene Reihenfolge). */
function libMove(id, dir) {
  const ids = st.docs.map((d) => d.id), i = ids.indexOf(id), j = i + dir;
  if (i < 0 || j < 0 || j >= ids.length) return;
  ids.splice(i, 1); ids.splice(j, 0, id);
  libCommit(ids);
  st.libSettle = id; libResort();
  setTimeout(snapSound, 170);
}

/* ---------- Ziehen zum Sortieren (3.1) ----------
   Nach 5 px Bewegung hebt sich der Eintrag an und folgt der Maus; die übrigen gleiten per CSS-Transition zur Seite.
   Beim Loslassen wird neu gezeichnet und der Eintrag federt an seinen Platz (FLIP) – mit leisem Einrasten.
   Nicht während der Suche (gefilterte Liste) und nicht im Tutorial. Vorführung im Tutorial nutzt dieselben Funktionen. */
const libDrag = { on: null };
function libDragStart(g) {
  const ul = $("library");
  closePops(true); hideTip();
  g.moved = true;
  g.items = [...ul.querySelectorAll(":scope > li")].filter((x) => x.querySelector("a[data-id]"));
  g.idx = g.cur = g.items.indexOf(g.li);
  // Einblend-Animationen (fill „both“) halten transform fest und würden das Verschieben überdecken
  g.items.forEach((x) => { x.classList.remove("enter", "landed"); x.getAnimations?.().forEach((a) => a.cancel()); });
  const tops = g.items.map((x) => x.getBoundingClientRect().top);
  g.step = g.items.length > 1 ? (tops[tops.length - 1] - tops[0]) / (g.items.length - 1) : g.li.offsetHeight;
  g.sc0 = ul.scrollTop;
  ul.classList.add("sorting"); g.li.classList.add("dragging"); document.body.classList.add("lib-grab");
  if (g.pid != null) try { ul.setPointerCapture(g.pid); } catch {}
  if (!libOwn()) {                                        // Ziehen schaltet auf die eigene Reihenfolge (Symbol rollt sofort)
    const ids = st.docs.map((d) => d.id);
    if (st.libPreview) st.libPreview = { libSort: "own", libOrder: ids }; else Object.assign(st.settings, { libSort: "own", libOrder: ids });
    libSortSync();
  }
  if (g.pid != null) {                                    // am Rand der Liste mitscrollen
    const tick = () => {
      if (libDrag.on !== g) return;
      const r = ul.getBoundingClientRect(), y = g.y ?? g.y0;
      const v = y < r.top + 36 ? -Math.ceil((r.top + 36 - y) / 6) : y > r.bottom - 36 ? Math.ceil((y - r.bottom + 36) / 6) : 0;
      if (v) { ul.scrollTop += v; libDragMove(g); }
      g.raf = requestAnimationFrame(tick);
    };
    g.raf = requestAnimationFrame(tick);
  }
}
function libDragMove(g) {
  const ul = $("library"), n = g.items.length;
  const lo = -g.idx * g.step - 10, hi = (n - 1 - g.idx) * g.step + 10;
  const dy = Math.max(lo, Math.min(hi, (g.y - g.y0) + (ul.scrollTop - g.sc0)));
  g.li.style.transform = `translateY(${dy}px)`;
  const t = Math.max(0, Math.min(n - 1, g.idx + Math.round(dy / g.step)));
  if (t === g.cur) return;
  g.cur = t;
  g.items.forEach((x, i) => {
    if (x === g.li) return;
    const sh = g.idx < i && i <= t ? -g.step : t <= i && i < g.idx ? g.step : 0;
    x.style.transform = sh ? `translateY(${sh}px)` : "";
  });
}
function libDragEnd(g) {
  const ul = $("library");
  cancelAnimationFrame(g.raf);
  document.body.classList.remove("lib-grab");
  if (g.pid != null) try { ul.releasePointerCapture(g.pid); } catch {}
  const ids = st.docs.map((d) => d.id), from = ids.indexOf(g.id);
  if (from >= 0) { ids.splice(from, 1); ids.splice(g.cur, 0, g.id); }
  libCommit(ids);                                         // speichert auch den Wechsel auf „eigene Reihenfolge“
  if (g.cur === g.idx) {                                  // am alten Platz losgelassen → zurückfedern
    const now = g.li.style.transform;
    g.li.classList.remove("dragging"); ul.classList.remove("sorting");
    g.items.forEach((x) => (x.style.transform = ""));
    g.li.animate?.([{ transform: now || "none" }, { transform: "none" }], { duration: 400, easing: "cubic-bezier(.34, 1.42, .64, 1)" });
    g.li.firstElementChild.animate?.([{ transform: "scale(1.03)" }, { transform: "none" }], { duration: 380, easing: EASE_OUT });
  } else {
    st.libSettle = g.id; st.libLift = true;
    ul.classList.remove("sorting");
    libResort();
  }
  setTimeout(snapSound, 140);
}
$("library").addEventListener("pointerdown", (e) => {
  if (e.button !== 0 || e.pointerType === "touch" || e.target.closest("[data-dots]")) return;
  const li = e.target.closest("li"), a = li?.querySelector("a[data-id]");
  if (!a || st.docs.length < 2 || !st.docs.some((d) => d.id === a.dataset.id)) return;   // Beispiel im Rundgang: nicht
  if ($("libSearch").value.trim() || !$("gt").classList.contains("hidden")) return;
  libDrag.on = { li, id: a.dataset.id, y0: e.clientY, pid: e.pointerId, moved: false };
});
window.addEventListener("pointermove", (e) => {
  const g = libDrag.on; if (!g || e.pointerId !== g.pid) return;
  if (!g.moved) { if (Math.abs(e.clientY - g.y0) < 5) return; libDragStart(g); }
  g.y = e.clientY; libDragMove(g);
});
function libDragStop(e) {
  const g = libDrag.on; if (!g || e.pointerId !== g.pid) return;
  libDrag.on = null;
  if (!g.moved) return;
  // der Klick nach dem Ziehen darf den Text nicht öffnen
  const block = (ev) => { ev.stopPropagation(); ev.preventDefault(); };
  window.addEventListener("click", block, { capture: true, once: true });
  setTimeout(() => window.removeEventListener("click", block, true), 0);
  libDragEnd(g);
}
$("library").addEventListener("dragstart", (e) => e.preventDefault());   // Links nicht als Datei/URL ziehen
window.addEventListener("pointerup", libDragStop);
window.addEventListener("pointercancel", libDragStop);
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


/* „Neuer Text“ → Bibliothek (3.0.3, Board-Idee 4b): nach „Vorbereiten“ fliegt eine Kopie der Karte an ihren Platz in
   der Bibliothek und wird dort zum Eintrag (der Eintrag „landet“ wie bisher). Nur transform/opacity/Größe, keine
   Glasfläche. Ist die Bibliothek nicht zu sehen (Mini-Player), blendet die Kopie an Ort und Stelle aus. */
function flyStart(fromEl, title) {
  if (!fromEl || reducedMotion.matches || !document.body.animate) return { to() {} };
  const r0 = fromEl.getBoundingClientRect();
  const g = document.createElement("div");
  g.className = "fly-ghost"; g.setAttribute("aria-hidden", "true");
  g.innerHTML = `<b data-noi18n>${esc(title || "Neuer Text")}</b><i></i><i></i><i></i>`;
  Object.assign(g.style, { left: `${r0.left}px`, top: `${r0.top}px`, width: `${r0.width}px`, height: `${r0.height}px` });
  document.body.append(g);
  return {
    to(docId) {
      const li = $("library").querySelector(`a[data-id="${docId}"]`)?.closest("li"), r1 = li?.getBoundingClientRect();
      const off = () => g.animate([{ opacity: 1 }, { opacity: 0 }], { duration: 220, easing: EASE, fill: "forwards" }).finished.then(() => g.remove(), () => g.remove());
      if (!li || !r1.width) return off();
      const h1 = parseFloat(li.style.getPropertyValue("--lh")) || r1.height || 60;
      const a = g.animate([
        { left: `${r0.left}px`, top: `${r0.top}px`, width: `${r0.width}px`, height: `${r0.height}px`, borderRadius: "14px", opacity: 1 },
        { left: `${r1.left}px`, top: `${r1.top}px`, width: `${r1.width}px`, height: `${h1}px`, borderRadius: "10px", opacity: 0.9, offset: 0.85 },
        { left: `${r1.left}px`, top: `${r1.top}px`, width: `${r1.width}px`, height: `${h1}px`, borderRadius: "10px", opacity: 0 },
      ], { duration: 700, easing: "cubic-bezier(.3, .75, .2, 1)", fill: "forwards" });
      a.finished.then(() => g.remove(), () => g.remove());
    },
  };
}
