"use strict";
// Vorleser – Eigene Stimme, Einstellungen, Stimmen-Bibliothek, Speicher. Teil der Oberfläche; Reihenfolge der Dateien: index.html
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
function showCloneRedo(on) {
  $("cRedo").classList.toggle("show", on);
  $("cRedo").inert = !on;                                 // unsichtbar → nicht per Tab erreichbar
  $("cloneDlg").classList.toggle("recording", on);        // „Datei …“ macht Platz
  $("cFileBtn").inert = on;
}
function resetCloneRec() {
  if (cTake) { clearInterval(cTake.timer); cTake.stop(); cTake = null; releaseMic(); }
  $("cRec").classList.remove("on");
  $("cRec").innerHTML = `${icon("i-mic", "i", "width:16px;height:16px")}Aufnehmen`;
  showCloneRedo(false);
}
function cloneTick() {
  if (!cTake) return;
  const t = cTake.secs();
  $("cRec").textContent = `Fertig · ${mmss(t)}`;
  $("cMsg").textContent = cTake.again && t < 3 ? "Von vorne – lies den Text noch einmal" : t < 12 ? "Weiterlesen …" : "Reicht – stoppen, wenn du magst";
  if (t >= 40) $("cRec").onclick();
}
async function startCloneTake(again = false) {
  cTake = startRecorder(await getMic());
  cTake.again = again;
  cTake.timer = setInterval(cloneTick, 250);
  cloneTick();
}
$("cRec").onclick = async () => {
  if (!cTake) {
    try { await startCloneTake(); } catch (e) { return ($("cMsg").textContent = "Mikrofon nicht verfügbar: " + e.message); }
    $("cRec").classList.add("on");
    showCloneRedo(true);
    return;
  }
  const t = cTake; cTake = null; clearInterval(t.timer);
  showCloneRedo(false);
  const blob = await t.stop(); releaseMic(); resetCloneRec();
  uploadClone(blob);
};
// Neu beginnen: bisherige Aufnahme verwerfen, Mikrofon bleibt offen, Zeit startet bei 0:00
$("cRedo").onclick = async () => {
  if (!cTake) return;
  const old = cTake; cTake = null; clearInterval(old.timer); old.stop();
  const b = $("cRedo"); b.classList.remove("turn"); void b.offsetWidth; b.classList.add("turn");
  setTimeout(() => b.classList.remove("turn"), 520);
  $("cText").scrollTop = 0; animateIn($("cText"), "swap");
  try { await startCloneTake(true); } catch (e) { resetCloneRec(); $("cMsg").textContent = "Mikrofon nicht verfügbar: " + e.message; }
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
  const TABS = { look: "tabLook", play: "tabPlay", voices: "tabVoices", storage: "tabStorage", app: "tabApp" };
  const prev = setTab, order = Object.keys(TABS);
  setTab = b.dataset.tab;
  const how = setTab === prev ? null : order.indexOf(setTab) > order.indexOf(prev) ? "right" : "left";
  const ghost = how && view === "settings" ? ghostOf($(TABS[prev])) : null;
  document.querySelectorAll("#setTabs [data-tab]").forEach((x) => x.classList.toggle("on", x === b));
  for (const [k, id] of Object.entries(TABS)) $(id).classList.toggle("hidden", k !== setTab);
  if (ghost) { navIn($(TABS[setTab]), how); navOut(ghost, how); }
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
  // Platzhalter → Inhalt: Karten bleiben stehen, ihre Höhe gleitet; nur die Werte blenden ein
  const grow = fresh ? [...$("tabStorage").querySelectorAll(".box")].map((b) => heightFrom(b)) : [];
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
  if (fresh) {
    grow.forEach((g) => g(420));
    if (!reducedMotion.matches) for (const id of ["stoTotal", "stoStack", "stoLegend", "cacheTxt", "cacheBar", "stoDocs", "stoMisc", "whisperSize", "cloneSize", "piperSize", "whisperNote", "cloneState", "piperCount"])
      $(id).animate([{ opacity: 0, filter: "blur(3px)" }, { opacity: 1, filter: "blur(0)" }], { duration: 420, easing: EASE });
  }
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

