"use strict";
// Vorleser – Neuer Text: Einfügen, Import, Diktat. Teil der Oberfläche; Reihenfolge der Dateien: index.html
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
  const ids = { paste: "srcPaste", file: "srcFile", dict: "srcDict" }, order = Object.keys(ids);
  const prev = order.find((k) => !$(ids[k]).classList.contains("hidden"));
  const how = prev && prev !== src ? (order.indexOf(src) > order.indexOf(prev) ? "right" : "left") : null;
  const ghost = how && view === "new" ? ghostOf($(ids[prev])) : null;
  document.querySelectorAll("[data-src]").forEach((b) => b.classList.toggle("on", b.dataset.src === src));
  $("srcPaste").classList.toggle("hidden", src !== "paste");
  $("srcFile").classList.toggle("hidden", src !== "file");
  $("srcDict").classList.toggle("hidden", src !== "dict");
  segThumbs($("viewNew"));
  if (ghost) { navIn($(ids[src]), how); navOut(ghost, how); } else animateIn($(ids[src]), "enter");
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

