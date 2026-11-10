"use strict";
// Vorleser – Editor als Bauteil (3.0.3): Absätze per Enter, Text/Überschrift, Rückgängig/Wiederholen, Gliederung,
// Suchen & ersetzen. Genutzt von „Neuer Text“; „Text bearbeiten“ (player.js) hat noch seine eigene Fassung und zieht
// später nach. Gespeichert wird wie bisher als Text („# Überschrift“, Leerzeile = neuer Absatz).
// Reihenfolge der Dateien: index.html (vor neuer-text.js).

/**
 * E: { doc, toc, kindP, kindH, undo, redo, findBtn, find, findQ, findR, findN, findAll } (Elemente)
 * opts.onChange(): nach jeder Änderung · opts.active(): gehört die Auswahl gerade zu diesem Editor?
 * opts.onPaste(e): vor dem Einfügen – true = schon erledigt (z. B. nur ein Link → Artikel holen)
 */
function makeEditor(E, opts = {}) {
  const ed = {};
  ed.render = (text) => {
    const blocks = (text || "").split(/\n{2,}/).map((b) => b.trim()).filter(Boolean);
    E.doc.innerHTML = (blocks.length ? blocks : [""]).map((b) => /^#{1,4}\s+/.test(b)
      ? `<h2>${esc(b.replace(/^#{1,4}\s+/, ""))}</h2>` : `<p>${esc(b).replace(/\n/g, "<br>") || "<br>"}</p>`).join("");
    toc(); empty();
  };
  ed.serialize = () => {
    const out = [];
    for (const n of E.doc.childNodes) {
      const t = (n.nodeType === 3 ? n.textContent : n.innerText || "").replace(/ /g, " ").trim();
      if (!t) continue;
      out.push(n.nodeName === "H2" ? `# ${t.replace(/\n+/g, " ")}` : t);
    }
    return out.join("\n\n");
  };
  const empty = () => E.doc.classList.toggle("empty", !E.doc.textContent.trim() && !E.doc.querySelector("h2"));
  function toc() {
    if (!E.toc) return;
    const hs = [...E.doc.querySelectorAll("h2")];
    E.toc.innerHTML = hs.length ? `<b>GLIEDERUNG</b>` + hs.map((h, i) => `<button data-h="${i}">${esc(h.textContent || "…")}</button>`).join("")
      : `<b>GLIEDERUNG</b><span>Überschriften erscheinen hier als Kapitel.</span>`;
  }
  ed.block = () => {
    let n = getSelection().anchorNode;
    while (n && n.parentNode !== E.doc) n = n.parentNode;
    return n && n.nodeType === 1 ? n : null;
  };
  function tools() {                                       // Umschalter zeigt, was die Zeile mit dem Cursor gerade ist
    const isH = ed.block()?.nodeName === "H2";
    if (E.kindH.classList.contains("on") === isH) return;
    E.kindH.classList.toggle("on", isH); E.kindH.setAttribute("aria-checked", String(isH));
    E.kindP.classList.toggle("on", !isH); E.kindP.setAttribute("aria-checked", String(!isH));
    segThumbs(E.kindP.parentElement.parentElement);
  }
  ed.sync = () => { toc(); tools(); empty(); opts.onChange?.(); };
  E.doc.addEventListener("input", ed.sync);
  E.doc.addEventListener("focus", () => document.execCommand("defaultParagraphSeparator", false, "p"));
  document.addEventListener("selectionchange", () => { if (opts.active?.() && document.activeElement === E.doc) tools(); });
  /** Reinen Text an der Schreibmarke einfügen; Leerzeilen → Absätze (wie beim Einfügen). */
  ed.insertText = (t) => {
    const parts = t.replace(/\r/g, "").split(/\n{2,}/);
    if (parts.length < 2) document.execCommand("insertText", false, t);
    else document.execCommand("insertHTML", false, parts.map((p) => `<p>${esc(p.trim()).replace(/\n/g, "<br>")}</p>`).join(""));
  };
  E.doc.addEventListener("paste", (e) => {                 // nur Text einfügen
    e.preventDefault();
    if (opts.onPaste?.(e)) return;
    ed.insertText(e.clipboardData?.getData("text/plain") || "");
  });
  E.doc.addEventListener("drop", (e) => {                  // gezogener Text: als reiner Text an der Stelle einfügen
    const t = e.dataTransfer?.getData("text/plain");
    if (!t || e.dataTransfer.files?.length) return;
    e.preventDefault();
    const r = document.caretRangeFromPoint?.(e.clientX, e.clientY);
    if (r) { const s = getSelection(); s.removeAllRanges(); s.addRange(r); }
    E.doc.focus(); ed.insertText(t);
  });
  const fmt = (tag) => { E.doc.focus(); document.execCommand("formatBlock", false, tag); ed.sync(); };
  E.kindH.onclick = () => fmt("h2");
  E.kindP.onclick = () => fmt("p");
  for (const b of [E.kindH, E.kindP]) b.addEventListener("mousedown", (e) => e.preventDefault());   // Cursor bleibt im Text
  E.undo.onclick = () => { E.doc.focus(); document.execCommand("undo"); ed.sync(); };
  E.redo.onclick = () => { E.doc.focus(); document.execCommand("redo"); ed.sync(); };
  E.toc && (E.toc.onclick = (e) => {
    const b = e.target.closest("[data-h]"); if (!b) return;
    const h = E.doc.querySelectorAll("h2")[+b.dataset.h]; if (!h) return;
    h.scrollIntoView({ block: "start", behavior: "smooth" });
    const rg = document.createRange(); rg.selectNodeContents(h); rg.collapse(false);
    const sel = getSelection(); sel.removeAllRanges(); sel.addRange(rg); E.doc.focus({ preventScroll: true });
  });
  E.findBtn.onclick = () => {
    const on = !E.find.classList.contains("open");
    E.find.classList.toggle("open", on); E.findBtn.classList.toggle("on", on); E.findBtn.setAttribute("aria-pressed", String(on));
    if (on) setTimeout(() => E.findQ.focus(), 60);
  };
  const rx = (q) => q.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  E.findQ.oninput = () => {
    const q = E.findQ.value;
    E.findN.textContent = q ? `${(ed.serialize().match(new RegExp(rx(q), "g")) || []).length} Treffer` : "";
  };
  E.findAll.onclick = () => {
    const q = E.findQ.value; if (!q) return;
    ed.render(ed.serialize().split(q).join(E.findR.value)); ed.sync(); E.findQ.oninput();
  };
  ed.focusEnd = () => {
    E.doc.focus({ preventScroll: true });
    const rg = document.createRange(); rg.selectNodeContents(E.doc.lastElementChild || E.doc); rg.collapse(false);
    const s = getSelection(); s.removeAllRanges(); s.addRange(rg);
  };
  toc(); empty();
  return ed;
}
