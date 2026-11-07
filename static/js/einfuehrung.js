"use strict";
// Vorleser – Erster Start und Rundgang. Teil der Oberfläche; Reihenfolge der Dateien: index.html
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
      <div class="big-logo">${[32, 60, 32, 16].map((h) => `<i style="--h:${h}"></i>`).join("")}</div>
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
      <div class="gt-body"><div class="num">${i + 1} / ${TOUR.length}</div><h3>${esc(step.t)}</h3><p>${esc(step.p)}</p>${step.by ? `<p class="gt-by">Gebaut von ${BYNAME}</p>` : ""}
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

