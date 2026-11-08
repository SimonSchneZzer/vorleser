"use strict";
// Vorleser – Stimmen-Auswahl und Hörproben. Teil der Oberfläche; Reihenfolge der Dateien: index.html
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
  if (warm.size) st.warmT = setTimeout(function again() {
    reloadVoices().then(() => { st.warmRetry = {}; if (setTab === "voices") renderVoiceLib(); })
      .catch(() => { st.warmT = retryLater(st.warmRetry ||= {}, again, 3000); });
  }, 3000);
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

