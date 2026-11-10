"use strict";
// Vorleser – Neuer Text (3.0.3): eine Karte wie „Text bearbeiten“ – schreiben, einfügen, Datei hineinziehen, Link
// einfügen, diktieren (schwebender Knopf). Editor-Bauteil: editor.js, Diktier-Knopf: diktat.js.
// Teil der Oberfläche; Reihenfolge der Dateien: index.html. Der Inhalt steht zusätzlich als Text in #text (versteckt)
// – so lesen Zähler, Spracherkennung, Entwurf und „Vorbereiten“ ihn wie bisher.
/* ===================================================================== */
/* Neuer Text                                                             */
/* ===================================================================== */
function showNew() {
  showView("new");                                        // Wiedergabe läuft weiter – der Player bleibt unten
  fillLangSelect();
  draftRestore();
  // Leeres Feld: Sprache der Oberfläche vorwählen (englische App startete mit „German“, Tester-Rückmeldung)
  const ui = UI_LANG === "en" ? "en" : "de";
  if (!$("text").value.trim() && !st.langManual && $("newLang").value !== ui && [...$("newLang").options].some((o) => o.value === ui)) {
    $("newLang").value = ui; st.newVoice = st.defaults[ui];
  }
  if (!st.newVoice || voiceById(st.newVoice)?.lang !== $("newLang").value) st.newVoice = st.defaults[$("newLang").value];
  setVoicePill($("newVoiceAv"), $("newVoiceLbl"), st.newVoice);
  updateCount();
  $("ntOrig").classList.toggle("hidden", !st.importOriginal);
  $("ntDoc").dataset.ph = UI_LANG === "en" ? trString(NT_PH) || NT_PH : NT_PH;   // Editor selbst ist von der Übersetzung ausgenommen
  requestAnimationFrame(() => segThumbs($("ntKind").parentElement));
  // gleich losschreiben: Cursor blinkt im Feld
  setTimeout(() => { if (view === "new" && !document.querySelector("dialog[open]")) nt.focusEnd(); }, 60);
}
const NT_PH = "Schreib los oder füge Text ein – eine Datei oder einen Link kannst du einfach hier hineinziehen oder einfügen.";
$("newBtn").onclick = () => showNew();

function fillLangSelect() {
  const sel = $("newLang"), cur = sel.value;
  sel.innerHTML = Object.entries(st.langs).filter(([k]) => langVoices(k).length).map(([k, n]) => `<option value="${k}">${esc(n)}</option>`).join("");
  if (cur && [...sel.options].some((o) => o.value === cur)) sel.value = cur;
}

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
function detectLang() {
  if (!$("text").value.trim()) { st.langManual = false; $("langHint").classList.add("hidden"); return; }
  if (st.langManual) return;
  clearTimeout(detectTimer);
  detectTimer = setTimeout(async () => {
    const { lang } = await api("/api/detect", { method: "POST", body: JSON.stringify({ text: $("text").value.slice(0, 8000) }) });
    if (!st.langManual && $("text").value.trim() && lang !== $("newLang").value) setNewLang(lang, true);
    else if (!st.langManual) showHint(true);
  }, 400);
}
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

/* ---------- Der Editor ---------- */
const nt = makeEditor({
  doc: $("ntDoc"), toc: $("ntToc"), kindP: $("ntP"), kindH: $("ntH"), undo: $("ntUndo"), redo: $("ntRedo"),
  findBtn: $("ntFindBtn"), find: $("ntFind"), findQ: $("ntFindQ"), findR: $("ntFindR"), findN: $("ntFindN"), findAll: $("ntFindAll"),
}, {
  active: () => view === "new",
  onChange: () => { $("text").value = nt.serialize(); updateCount(); detectLang(); draftSave(); lnRefresh(); },
  onPaste: (e) => {                                       // nur ein Link in ein leeres Feld → Artikel holen statt Adresse
    const t = (e.clipboardData?.getData("text/plain") || "").trim();
    if (!$("text").value.trim() && isOnlyLink(t)) { importLink(t, false); return true; }
    setTimeout(afterPaste, 0);                            // sonst einfügen lassen, dann schauen, ob Links drinstecken
    return false;
  },
});
/** Inhalt setzen (Datei, Link-Inhalt, Entwurf, Rundgang …) – Editor, Text-Spiegel und Zähler. */
function ntSet(text, title) {
  nt.render(text || "");
  $("text").value = nt.serialize();
  if (title !== undefined) $("title").value = title || "";
  $("ntDoc").scrollTop = 0;
  updateCount(); lnRefresh();
}
$("title").addEventListener("input", () => draftSave());

/* ---------- Ersetzen mit Rückgängig, Lade-Fläche ---------- */
/** Feld-Inhalt durch etwas Neues ersetzen (Datei, Link-Inhalt) – mit „Rückgängig“, wenn vorher Text da war. */
function replaceField(title, text, msg) {
  const prev = { title: $("title").value, text: $("text").value, orig: st.importOriginal };
  lnClose(); ntSet(text, title); draftSave();
  // Fertig geladen: kein blinkender Cursor mehr am Anfang des neuen Inhalts (Simon, 3.0.4) – ein Klick setzt ihn wieder
  if ($("ntDoc").contains(document.activeElement)) document.activeElement.blur();
  if ($("ntDoc").contains(getSelection().anchorNode)) getSelection().removeAllRanges();
  if (prev.text.trim()) {
    toast(msg, false, { label: "Rückgängig", fn: () => {
      st.importOriginal = prev.orig; $("ntOrig").classList.toggle("hidden", !prev.orig);
      lnClose(); ntSet(prev.text, prev.title); draftSave(); detectLang();
    } });
  }
}
function busyShow(label, sub) {
  $("busyLbl").textContent = label; $("busySub").textContent = sub || ""; $("ocrPages").textContent = "";
  $("ocrFill").style.width = ""; $("ocrFill").classList.add("indet"); $("ocrCancel").classList.add("hidden");
  const o = $("busyOv"); if (o.classList.contains("hidden")) { o.classList.remove("hidden"); animateIn(o, "enter"); }
}
function busyHide() {
  const o = $("busyOv"); if (o.classList.contains("hidden") || o.dataset.closing) return;
  o.dataset.closing = "1";
  const done = () => { o.classList.add("hidden"); delete o.dataset.closing; };
  if (o.animate && !reducedMotion.matches) o.animate([{ opacity: 1 }, { opacity: 0 }], { duration: 200, easing: EASE }).finished.then(done, done);
  else done();
}

/* ---------- Links: nur ein Link → Artikel holen · ein Link im Text → hinspringen · mehrere → ruhiger Hinweis ---------- */
const URL_RX = /\b(?:https?:\/\/|www\.)[^\s<>"'()[\]{}]+[^\s<>"'()[\]{}.,;:!?]/gi;
const isOnlyLink = (t) => { const m = t.match(URL_RX); return !!m && m.length === 1 && m[0] === t; };
function findLinks(text) { return [...text.matchAll(URL_RX)].map((m) => m[0]); }
const ln = { links: [], i: 0, walk: false, focus: -1 };
let linkBusy = false;
async function fetchArticle(url) {
  const u = /^https?:\/\//i.test(url) ? url : `https://${url}`;
  return readJson(await fetch("/api/import-url", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ url: u }) }));
}
async function importLink(url, replacesText) {
  if (linkBusy) return; linkBusy = true;
  busyShow(replacesText ? "Inhalt wird geholt …" : "Link erkannt – Artikel wird geholt …",
    replacesText ? "Ersetzt den Text im Feld – Rückgängig holt ihn zurück." : "Nur der Artikel: Werbung, Menüs und Cookie-Hinweise fliegen raus.");
  try {
    const d = await fetchArticle(url);
    st.importOriginal = null; $("ntOrig").classList.add("hidden");
    replaceField(d.title || "", d.text, "Ersetzt durch den Inhalt des Links");
    st.langManual = false; setNewLang(d.lang, true);
  } catch (e) { toastErr(e); }
  finally { linkBusy = false; busyHide(); }
}
/** Bereiche (Range) aller Links im Editor, in Textreihenfolge – aus den Textknoten, ohne den Inhalt zu verändern. */
function linkRanges() {
  const out = [];
  for (const blk of $("ntDoc").children) {
    const nodes = [], tw = document.createTreeWalker(blk, NodeFilter.SHOW_TEXT);
    let all = "";
    while (tw.nextNode()) { nodes.push([tw.currentNode, all.length]); all += tw.currentNode.nodeValue; }
    if (!nodes.length) continue;
    const at = (pos) => { let k = nodes.length - 1; while (k > 0 && nodes[k][1] > pos) k--; return [nodes[k][0], pos - nodes[k][1]]; };
    for (const m of all.matchAll(URL_RX)) {
      const r = document.createRange();
      try { r.setStart(...at(m.index)); r.setEnd(...at(m.index + m[0].length)); out.push(r); } catch {}
    }
  }
  return out;
}
/** Markierung hinter dem Text: je Zeile des Links eine runde Fläche (wie die Wort-Box beim Lesen).
 *  Beim Scrollen werden die Flächen nur verschoben (nicht neu angelegt) – sonst bricht das Pulsieren ab. */
function lkPaint(pulse) {
  const layer = $("lkLayer");
  if (!ln.links.length) { layer.innerHTML = ""; return; }
  const W = $("ntDoc").parentElement.getBoundingClientRect(), boxes = [];
  linkRanges().forEach((r, k) => { for (const q of r.getClientRects()) if (q.width) boxes.push([k, q]); });
  if (layer.children.length !== boxes.length) layer.innerHTML = boxes.map(() => '<i class="lk-box"></i>').join("");
  boxes.forEach(([k, q], n) => {
    const b = layer.children[n];
    Object.assign(b.style, { left: `${q.left - W.left - 3}px`, top: `${q.top - W.top - 1}px`, width: `${q.width + 6}px`, height: `${q.height + 2}px` });
    b.classList.toggle("cur", k === ln.focus);
    if (k !== ln.focus) b.classList.remove("pulse");
    else if (pulse) { b.classList.remove("pulse"); void b.offsetWidth; b.classList.add("pulse"); }
  });
}
$("ntDoc").addEventListener("scroll", () => lkPaint(false));
window.addEventListener("resize", () => { if (view === "new") lkPaint(false); });
/** Zum Link k scrollen und ihn 3× pulsieren lassen (erst wenn das Scrollen steht). */
function lnFocus(k) {
  ln.focus = k;
  const r = linkRanges()[k]; if (!r) return;
  const doc = $("ntDoc"), q = r.getBoundingClientRect(), D = doc.getBoundingClientRect();
  const top = Math.max(0, Math.min(doc.scrollHeight - doc.clientHeight, doc.scrollTop + (q.top - D.top) - doc.clientHeight * 0.35));
  lkPaint(false);
  if (reducedMotion.matches || Math.abs(top - doc.scrollTop) < 2) { doc.scrollTop = top; lkPaint(true); return; }
  let done = false;
  const go = () => { if (done) return; done = true; doc.removeEventListener("scrollend", go); lkPaint(true); };
  doc.addEventListener("scrollend", go);
  setTimeout(go, 700);                                     // ohne scrollend (ältere WebViews)
  doc.scrollTo({ top, behavior: "smooth" });
}
function lnRender() {
  const n = ln.links.length, calm = n > 1 && !ln.walk;
  $("lnTitle").textContent = calm ? `${n} Links erkannt – werden als Text vorgelesen` : "In deinem Text steckt ein Link";
  $("lnSub").textContent = calm ? "Sie bleiben einfach im Text stehen. Nur wenn du magst, gehst du sie einzeln durch." : ln.links[ln.i] || "";
  if (calm) delete $("lnSub").dataset.noi18n; else $("lnSub").dataset.noi18n = "";   // Adresse nie übersetzen
  $("lnCnt").textContent = n > 1 && ln.walk ? `Link ${ln.i + 1} von ${n}` : "";
  $("lnWalk").classList.toggle("hidden", !calm);
  $("lnActs").classList.toggle("hidden", calm);
}
function lnOpen() {
  lnRender();
  $("lnWrap").classList.add("open");
  if (ln.links.length === 1 || ln.walk) setTimeout(() => lnFocus(ln.i), 120);   // erst aufklappen, dann springen
  else { ln.focus = -1; lkPaint(false); }
}
function lnClose() {
  ln.links = []; ln.i = 0; ln.walk = false; ln.focus = -1;
  $("lnWrap").classList.remove("open"); lkPaint(false);
}
/** Nach dem Einfügen: Was steckt drin? (Nur beim Einfügen – beim Tippen springt nichts.) */
function afterPaste() {
  $("text").value = nt.serialize();
  const links = findLinks($("text").value);
  if (!links.length) { if (ln.links.length) lnClose(); return; }
  Object.assign(ln, { links, i: 0, walk: false, focus: -1 });
  lnOpen();
}
/** Text geändert: offene Markierung nachziehen bzw. Hinweis schließen, wenn kein Link mehr da ist. */
function lnRefresh() {
  if (!ln.links.length) return;
  const links = findLinks($("text").value);
  if (!links.length) return lnClose();
  ln.links = links; ln.i = Math.min(ln.i, links.length - 1); lnRender(); lkPaint(false);
}
$("lnKeep").onclick = () => {                               // Link bleibt als Text (wird als Adresse ohne Pfad gelesen)
  if (ln.walk && ln.i < ln.links.length - 1) { ln.i++; lnRender(); lnFocus(ln.i); return; }
  lnClose();
};
$("lnFetch").onclick = () => { const l = ln.links[ln.i]; if (l) importLink(l, true); };
$("lnWalk").onclick = () => { ln.walk = true; ln.i = 0; lnRender(); lnFocus(0); };
$("lnClose").onclick = lnClose;

/* ---------- Datei hineinziehen / wählen ---------- */
async function importFile(f) {
  lnClose();
  busyShow(`${f.name} · wird gelesen …`, "");
  try {
    const r = await fetch("/api/import", { method: "POST", body: f, headers: { "X-Filename": encodeURIComponent(f.name) } });
    let d = await readJson(r);
    if (d.ocr) {                                            // eingescannt → Texterkennung (Version 3.0)
      busyShow(`${f.name} · Text wird erkannt …`, "Läuft nur auf deinem Rechner, ohne Internet.");
      d = await ocrWait(d.ocr);
      if (!d) return;                                       // abgebrochen
    }
    replaceField(d.title || f.name.replace(/\.[^.]+$/, ""), d.text, `Ersetzt durch „${f.name}“`);
    st.importOriginal = d.original || null;
    $("ntOrig").classList.toggle("hidden", !st.importOriginal);
    const c = d.cleanup;                                    // Version 3.0: PDF aufgeräumt → kurz sagen, was
    if (c && (c.kopf || c.seiten || c.getrennt || c.fussnoten || c.punkte || c.tabellen) && !$("toast").querySelector("button")) {
      toast("Aufgeräumt: " + [c.kopf && `${c.kopf} Kopf-/Fußzeilen`, c.seiten && `${c.seiten} Seitenzahlen`,
        c.getrennt && `${c.getrennt} getrennte Wörter`, c.fussnoten && `${c.fussnoten} Fußnoten ans Kapitelende`, c.punkte && `${c.punkte} Listenpunkte`, c.tabellen && `${c.tabellen} Tabellen übersprungen`].filter(Boolean).join(", "));
    }
    st.langManual = false;
    setNewLang(d.lang, true);
  } catch (err) { toastErr(err); }                          // eigener Satz vom Server, übersetzbar
  finally { busyHide(); }
}
let ocrJob = null;
function ocrShow(job) {
  if (!job) return;
  $("ocrFill").classList.remove("indet");
  $("ocrPages").textContent = job.total ? `Seite ${job.done} von ${job.total}` : "";
  $("ocrFill").style.width = `${job.total ? (job.done / job.total) * 100 : 0}%`;
  $("ocrCancel").classList.remove("hidden");
}
async function ocrWait(job) {
  ocrJob = job.id; ocrShow(job);
  let fails = 0;
  try {
    for (;;) {
      await new Promise((r) => setTimeout(r, 400));
      if (ocrJob !== job.id) return null;                   // abgebrochen
      try { job = await api(`/api/import/ocr/${job.id}`); fails = 0; }
      catch (e) { if (++fails > 15) throw e; continue; }   // kurzer Aussetzer → weiter fragen
      ocrShow(job);
      if (job.status === "ready") { $("ocrFill").style.width = "100%"; return job.result; }
      if (job.status === "error") throw new Error(job.error);
      if (job.status === "cancelled") return null;
    }
  } finally { if (ocrJob === job.id) ocrJob = null; }
}
$("ocrCancel").onclick = () => {
  const id = ocrJob; if (!id) return;
  ocrJob = null; busyHide();
  api(`/api/import/ocr/${id}`, { method: "DELETE" }).catch(() => {});
  toast("Texterkennung abgebrochen.");
};
$("ntOrig").onclick = async () => {
  if (!st.importOriginal) return;
  if (!(await ask({ title: "Original wiederherstellen?", text: "Der Text wird durch das PDF ersetzt, wie es vor dem Aufräumen war – mit Kopfzeilen und Seitenzahlen.", ok: "Wiederherstellen" }))) return;
  replaceField($("title").value, st.importOriginal, "Original wiederhergestellt");
};
$("pickFile2").onclick = () => $("file").click();
$("file").onchange = (e) => { const f = e.target.files[0]; if (f) importFile(f); e.target.value = ""; };
const card = $("srcPaste");
const isFileDrag = (e) => [...(e.dataTransfer?.types || [])].includes("Files");
card.addEventListener("dragover", (e) => {
  if (!isFileDrag(e)) return;                               // gezogener Text: normal ins Feld (editor.js)
  e.preventDefault();
  if (card.classList.contains("drag")) return;
  card.classList.add("drag");
  $("dropHint").textContent = $("text").value.trim() ? "Ersetzt den Text im Feld – mit Rückgängig holst du ihn zurück." : "Kapitel werden automatisch erkannt.";
  $("dropOv").classList.remove("hidden"); animateIn($("dropOv"), "enter");
});
const dragEnd = () => { card.classList.remove("drag"); $("dropOv").classList.add("hidden"); };
card.addEventListener("dragleave", (e) => { if (!card.contains(e.relatedTarget)) dragEnd(); });
card.addEventListener("drop", (e) => {
  if (!isFileDrag(e)) { setTimeout(afterPaste, 0); return; }   // Text hineingezogen → wie Einfügen
  e.preventDefault(); dragEnd();
  const f = e.dataTransfer.files[0]; if (f) importFile(f);
});

/* ---------- Diktieren: schwebender Knopf (Bauteil aus diktat.js) ---------- */
let ntSel = null;                                           // Schreibmarke merken – der Klick auf den Knopf nimmt den Fokus
$("dictBtn").addEventListener("pointerdown", () => {
  const s = getSelection(); ntSel = s.rangeCount && $("ntDoc").contains(s.anchorNode) ? s.getRangeAt(0).cloneRange() : null;
});
micFab($("dictBtn"), {
  lang: () => (st.langManual ? $("newLang").value : null),
  onStart: () => lnClose(),
  insert: (said, lang) => {                                 // als eigener Absatz an der Schreibmarke (sonst am Ende)
    const doc = $("ntDoc"), p = document.createElement("p"); p.textContent = said;
    let blk = ntSel?.startContainer; while (blk && blk.parentNode !== doc) blk = blk.parentNode;
    if (doc.classList.contains("empty")) doc.replaceChildren(p);
    else if (blk) blk.after(p); else doc.append(p);
    const rg = document.createRange(); rg.selectNodeContents(p); rg.collapse(false);
    doc.focus({ preventScroll: true }); const s = getSelection(); s.removeAllRanges(); s.addRange(rg);
    p.scrollIntoView({ block: "nearest" });
    if (!st.langManual && st.langs[lang]) setNewLang(lang, true);
    nt.sync();
  },
});

$("createBtn").onclick = async () => {
  $("createBtn").disabled = true;
  try {
    const lang = $("newLang").value;
    const d = await api("/api/docs", { method: "POST", body: JSON.stringify({
      title: $("title").value, text: $("text").value, lang, voice: st.newVoice || st.defaults[lang],
      original: st.importOriginal || undefined }) });           // PDF: Original für „Original wiederherstellen“
    const fly = flyStart($("srcPaste"), d.title);       // Karte fliegt gleich in die Bibliothek (3.0.3)
    st.importOriginal = null; $("ntOrig").classList.add("hidden");
    lnClose(); ntSet("", ""); st.langManual = false; $("langHint").classList.add("hidden"); updateCount(); draftClear();
    st.libLand = { id: d.id, t: performance.now() };
    await refreshLibrary();
    fly.to(d.id);
    openDoc(d.id);
  } catch (err) { toastErr(err); $("createBtn").disabled = false; }
};

/* Entwurf behalten: Text im Feld überlebt Schließen/Neustart (Tester-Rückmeldung, Version 3.0) */
let draftT = 0;
function draftSave() {
  clearTimeout(draftT);
  draftT = setTimeout(() => {
    try {
      const d = { title: $("title").value, text: $("text").value };
      if (d.text.trim() || d.title.trim()) localStorage.setItem("vorleser.draft", JSON.stringify(d));
      else localStorage.removeItem("vorleser.draft");
    } catch {}
  }, 400);
}
function draftRestore() {
  if ($("text").value.trim()) return;
  try {
    const d = JSON.parse(localStorage.getItem("vorleser.draft") || "null");
    if (d?.text) ntSet(d.text, d.title || "");
  } catch {}
}
function draftClear() { clearTimeout(draftT); try { localStorage.removeItem("vorleser.draft"); } catch {} }
/* Datei per Strg+V / ⌘V einfügen (im Explorer/Finder kopiert) – wie Hineinziehen */
document.addEventListener("paste", (e) => {
  if (view !== "new") return;
  const f = e.clipboardData?.files?.[0];
  if (!f) return;
  e.preventDefault(); e.stopPropagation();
  importFile(f);
}, true);
