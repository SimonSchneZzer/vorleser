"use strict";
// Vorleser – Updates, Was ist neu, Fehler melden, Deinstallieren. Teil der Oberfläche; Reihenfolge der Dateien: index.html
/* ===================================================================== */
/* Updates (Desktop-App)                                                  */
/* ===================================================================== */
const upd = { s: null, timer: 0 };
const updLaterKey = "vorleser.updLater";
function updDismissed(v) {
  try { const d = JSON.parse(localStorage.getItem(updLaterKey) || "null"); return d && d.v === v && Date.now() < d.until; } catch { return false; }
}
/* ===================================================================== */
/* Karten unten rechts (Board 21): EIN Platz, wartende Karten als Stapel dahinter.                      */
/* Jede Karte MUSS eine Stufe haben – dringend (läuft gerade), aktion (Entscheidung), info (zur Kenntnis). */
/* Vorne: Karten mit Fortschritt (sticky), dann höhere Stufe, bei gleicher Stufe die ältere.              */
/* ===================================================================== */
const CARD_LEVELS = ["dringend", "aktion", "info"];
const cardStack = { list: [], n: 0 };
function cardEl(el, on) {                                 // eine Karte weich ein-/ausblenden
  if (on) { el.classList.remove("hidden", "leaving"); return; }
  if (el.classList.contains("hidden") || el.classList.contains("leaving")) return;
  el.classList.add("leaving");
  setTimeout(() => { if (el.classList.contains("leaving")) { el.classList.add("hidden"); el.classList.remove("leaving"); } }, 250);
}
function cardPut(id, el, level, sticky = false) {
  if (!CARD_LEVELS.includes(level)) throw new Error(`Karte „${id}“ ohne gültige Stufe (${level})`);
  const c = cardStack.list.find((x) => x.id === id);
  if (c) Object.assign(c, { el, level, sticky }); else cardStack.list.push({ id, el, level, sticky, at: ++cardStack.n });
  cardLayout();
}
function cardDrop(id) {
  const c = cardStack.list.find((x) => x.id === id); if (!c) return;
  cardStack.list = cardStack.list.filter((x) => x !== c);
  delete c.el.dataset.more; cardEl(c.el, false);
  cardLayout();
}
function cardOrder() {
  return [...cardStack.list].sort((a, b) => (b.sticky - a.sticky) || CARD_LEVELS.indexOf(a.level) - CARD_LEVELS.indexOf(b.level) || a.at - b.at);
}
function cardLayout() {
  const q = cardOrder(), top = q[0], more = q.length - 1;
  for (const c of q) if (c !== top) { delete c.el.dataset.more; cardEl(c.el, false); }
  if (top) { if (more > 0) top.el.dataset.more = more; else delete top.el.dataset.more; cardEl(top.el, true); }
  requestAnimationFrame(() => {                           // Stapel dahinter: gleiche Größe wie die vordere Karte
    const h = top && !top.el.classList.contains("hidden") ? top.el.offsetHeight : 0;
    ["cardPeek1", "cardPeek2"].forEach((id, i) => {
      const p = $(id); if (h) p.style.height = `${h}px`;
      p.classList.toggle("on", !!h && more > i);
    });
  });
}
function updShow(on) {                                    // Update-Karte meldet sich beim Stapel an bzw. ab
  const el = $("upd");
  if (!on) return cardDrop("update");
  const busy = el.classList.contains("busy");
  cardPut("update", el, busy ? "dringend" : el.classList.contains("news") ? "info" : "aktion", busy);
}
/* ---------- Name → Sprechblase mit GitHub / LinkedIn (überall, wo der Name steht) ---------- */
const BYNAME = $("verTxt").closest(".r").querySelector("[data-by]").outerHTML;
function byPop(btn) {
  const pop = $("byPop"), open = pop.classList.contains("open") && pop._for === btn;
  document.querySelectorAll("[data-by]").forEach((b) => b.setAttribute("aria-expanded", "false"));
  if (!btn || open) { pop.classList.remove("open"); pop._for?.classList.remove("on"); pop._for = null; return; }
  pop._for?.classList.remove("on");
  const r = btn.getBoundingClientRect(), w = pop.offsetWidth, h = pop.offsetHeight;
  const up = r.bottom + 14 + h > innerHeight - 8;                 // unten kein Platz → Blase über dem Namen
  const x = Math.max(8 + w / 2, Math.min(innerWidth - 8 - w / 2, r.left + r.width / 2));
  pop.classList.toggle("up", up);
  pop.style.left = `${x}px`; pop.style.top = `${up ? r.top - 14 - h : r.bottom + 14}px`;
  pop.style.setProperty("--ax", `${r.left + r.width / 2 - x}px`);   // Pfeil zeigt auf den Namen
  if (!pop.classList.contains("open")) void pop.offsetWidth;
  pop.classList.add("open"); pop._for = btn; btn.classList.add("on"); btn.setAttribute("aria-expanded", "true");
}
document.addEventListener("click", (e) => {
  const b = e.target.closest("[data-by]");
  if (b) { e.preventDefault(); e.stopPropagation(); return byPop(b); }
  if (e.target.closest("#byPop .opt")) return setTimeout(() => byPop(null), 150);
  if (!e.target.closest("#byPop")) byPop(null);
}, true);
document.addEventListener("keydown", (e) => { if (e.key === "Escape" && $("byPop").classList.contains("open")) { e.stopPropagation(); byPop(null); } }, true);
addEventListener("resize", () => byPop(null));
document.addEventListener("scroll", () => byPop(null), true);
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
  $("updPage").classList.add("hidden");
  $("verTxt").textContent = `Version ${s.current}`;
  $("updNote").textContent = s.available ? `Version ${s.latest} ist verfügbar` : s.latest ? "Du hast die neueste Version" : "Prüft bei jedem Start automatisch";
  const busy = s.state === "downloading" || s.state === "preparing" || s.state === "installing";
  $("upd").classList.toggle("busy", busy);
  $("updBar").classList.toggle("hidden", !busy);
  $("updBtns").classList.toggle("hidden", busy);
  if (s.state === "downloading") {
    const pct = s.connected && s.total ? Math.round((s.done / s.total) * 100) : 0;
    $("updTitle").textContent = "Update wird geladen";
    $("updText").textContent = s.connected && s.total ? `${fmtMB(s.done)} von ${fmtMB(s.total)}` : "Verbindung wird hergestellt …";
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
    if (upd.errLater) return updShow(false);            // „Später“ → erst nach dem nächsten Start wieder fragen
    $("updTitle").textContent = "Update fehlgeschlagen";
    const other = "Das Update ließ sich nicht vorbereiten. Versuch es noch einmal oder lade die neue Version von der Webseite.";
    $("updText").textContent = s.error || other;
    $("updPage").classList.toggle("hidden", (s.error || other) !== other);   // nur, wenn die Webseite wirklich hilft
    $("updGo").textContent = s.canInstall ? "Erneut versuchen" : "Download-Seite";
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
  try { upd.s = await api(force ? "/api/update/check" : "/api/update", force ? { method: "POST" } : {}); upd.retry = {}; }
  catch {                                                // während des Ladens nicht stehen bleiben (Balken friert sonst ein)
    if (["downloading", "preparing", "installing"].includes(upd.s?.state)) upd.timer = retryLater(upd.retry ||= {}, updRefresh, 1000);
    return null;
  }
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
  if (upd.s?.state === "error") { upd.errLater = true; return updShow(false); }  // nur für diesen Start, keine 24-h-Pause
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
  if (!s.canInstall) return openExternal(s.page);   // „Erneut versuchen“ nach einem Fehler startet einfach neu
  upd.errLater = false;
  try { upd.s = await api("/api/update/install", { method: "POST" }); } catch (e) { return toastErr(e); }
  updRender();
  upd.timer = setTimeout(updRefresh, 400);
};
$("updPage").onclick = (e) => { e.preventDefault(); openExternal(upd.s?.page || "https://simonschnezzer.github.io/vorleser-download/"); };
/* ---------- Vorab erzeugen unterbrochen (Board 20): nach dem Start fragen ---------- */
const prepResume = { items: [] };
async function prepPendingCheck() {
  let r; try { r = await api("/api/prepare/pending"); } catch { return; }
  const items = prepResume.items = r.items || [];
  if (!items.length) return cardDrop("prep");
  const one = items[0];
  $("prepCardTitle").textContent = items.length > 1 ? "Vorab erzeugen nicht fertig" : "Vorab erzeugen unterbrochen";
  $("prepCardText").textContent = items.length > 1
    ? `${items.length} Texte wurden beim letzten Mal nicht fertig vorbereitet. Im Hintergrund weitermachen?`
    : `„${one.title}“: ${one.done} von ${one.total} Abschnitten sind fertig. Im Hintergrund weitermachen?`;
  cardPut("prep", $("prepCard"), "aktion");
}
$("prepCardLater").onclick = () => cardDrop("prep");     // fertige Abschnitte bleiben; beim nächsten Start wieder fragen
$("prepCardGo").onclick = async () => {
  cardDrop("prep");
  try { await api("/api/prepare/resume", { method: "POST" }); } catch (e) { return toastErr(e); }
  jobsPoll(); if (st.doc) updatePrep(true);
};
setTimeout(prepPendingCheck, 1500);                      // kurz nach dem Start (Update-Karte hat Vorrang über den Stapel)
/* ---------- Version 3.0: markierten Text vorlesen / Menüleiste (ueberall.py) ---------- */
const ueMac = /Mac/.test(navigator.platform || navigator.userAgent);
const ueBridge = () => window.pywebview?.api;
/* Tastenkürzel (Version 3.0): anzeigen + ändern („neue Kombination drücken“) */
const HK_DEF = { code: "KeyV", ctrl: true, alt: true, shift: false, meta: false };
const hkGet = () => st.settings?.hotkey || HK_DEF;
const hkKey = (hk) => hk.code.replace(/^Key|^Digit/, "");
function hkParts(hk = hkGet()) {
  return ueMac ? [hk.ctrl && "⌃", hk.alt && "⌥", hk.shift && "⇧", hk.meta && "⌘", hkKey(hk)].filter(Boolean)
    : [hk.ctrl && "Strg", hk.alt && "Alt", hk.shift && "Umschalt", hk.meta && "Win", hkKey(hk)].filter(Boolean);
}
/** Ausgeschrieben für Sätze: „Control + Option + V“ (Mac) bzw. „Strg + Alt + V“ */
function hkLang(hk = hkGet()) {
  return (ueMac ? [hk.ctrl && "Control", hk.alt && "Option", hk.shift && "Shift", hk.meta && "Command", hkKey(hk)]
    : [hk.ctrl && "Strg", hk.alt && "Alt", hk.shift && "Umschalt", hk.meta && "Win", hkKey(hk)]).filter(Boolean).join(" + ");
}
function hkRender() { $("hkKeys").innerHTML = hkParts().map((k) => `<kbd>${esc(k)}</kbd>`).join(""); }
let hkCapture = null;
function hkStop() {
  if (!hkCapture) return;
  document.removeEventListener("keydown", hkCapture, true); hkCapture = null;
  $("hkRow").classList.remove("capture"); $("hkChange").textContent = "Ändern"; hkRender();
}
$("hkChange").onclick = () => {
  if (hkCapture) return hkStop();
  $("hkRow").classList.add("capture"); $("hkChange").textContent = "Abbrechen";
  $("hkKeys").innerHTML = `<span class="hk-wait">Neue Kombination drücken …</span>`;
  hkCapture = async (e) => {
    e.preventDefault(); e.stopPropagation();
    if (e.key === "Escape") return hkStop();
    if (["Control", "Alt", "Shift", "Meta", "OS"].includes(e.key)) return;     // nur Zusatztaste – weiter warten
    const hk = { code: e.code, ctrl: e.ctrlKey, alt: e.altKey, shift: e.shiftKey, meta: e.metaKey };
    if (!/^(Key[A-Z]|Digit[0-9]|F([1-9]|1[0-2]))$/.test(hk.code) || !(hk.ctrl || hk.alt || hk.meta)) {
      $("hkKeys").innerHTML = `<span class="hk-wait bad">Buchstabe, Ziffer oder F-Taste mit ${ueMac ? "⌃, ⌥ oder ⌘" : "Strg oder Alt"}</span>`;
      return;
    }
    hkStop();
    await saveSettings({ hotkey: hk });
    try { await ueBridge()?.ueberall_kuerzel_neu(); } catch {}
    hkRender(); toast(`Tastenkürzel: ${hkParts(hk).join(ueMac ? "" : "+")}`);
  };
  document.addEventListener("keydown", hkCapture, true);
};
async function ueRenderRows() {
  const on = !!(st.features.desktop && (ueMac || st.features.os === "win"));   // Windows: Kürzel ja, Menüleiste/Erlaubnis nein
  document.querySelectorAll(".ue-only").forEach((r) => r.classList.toggle("hidden", !on));
  $("bgRow").classList.toggle("hidden", !on || !ueMac);
  if (!on) return;
  if (!ueMac) { if (!hkCapture) hkRender(); $("hkAllow").classList.add("hidden"); $("hkNote").textContent = "In jeder App: Text markieren, dann das Tastenkürzel (solange Vorleser offen ist)"; return; }
  const bg = st.settings?.background !== false;
  $("bgSw").classList.toggle("on", bg); $("bgSw").setAttribute("aria-checked", String(bg));
  if (!hkCapture) hkRender();
  let ok = true; try { ok = await ueBridge()?.ueberall_erlaubt(); } catch {}
  $("hkAllow").classList.toggle("hidden", ok !== false);
  $("hkNote").textContent = ok === false ? "Braucht einmal deine Erlaubnis (Bedienungshilfen)" : "In jeder App: Text markieren, dann das Tastenkürzel";
}
$("bgSw").onclick = () => saveSettings({ background: !(st.settings?.background !== false) }).then(ueRenderRows);
$("hkAllow").onclick = () => ueberallErlaubnis();
function ueDialog({ icon, title, text, path = false, no, yes, onNo, onYes }) {
  const d = $("ueDlg");
  $("ueIcon").innerHTML = icon; $("ueTitle").textContent = title; $("ueText").textContent = text;
  $("uePath").classList.toggle("hidden", !path); $("uePath").classList.remove("ue-go");
  if (path) { void $("uePath").offsetWidth; $("uePath").classList.add("ue-go"); }   // Schalter springt einmal auf Grün
  $("ueNo").textContent = no; $("ueYes").textContent = yes;
  $("ueYes").disabled = false; clearTimeout(ueRestartT);   // nach „Später“ beim Warten: wieder klickbar
  $("ueNo").classList.toggle("hidden", !no);
  $("ueNo").onclick = () => { d.close(); onNo?.(); };
  $("ueYes").onclick = () => onYes ? onYes() : d.close();
  if (!d.open) d.showModal();
}
// Board 24: erstes Schließen → erklären, dann verstecken
window.ueberallSchliessHinweis = () => ueDialog({
  icon: icon("i-wave"), title: "Vorleser läuft in der Menüleiste weiter",
  text: `So funktioniert ${hkLang()} auch mit geschlossenem Fenster. Öffnen und Beenden über das Symbol oben rechts in der Menüleiste. Ausschalten in Einstellungen › App.`,
  no: "Einstellungen", yes: "Verstanden",
  onNo: () => { saveSettings({ bgHintSeen: true }); openSettingsTab("app"); },
  onYes: () => { $("ueDlg").close(); saveSettings({ bgHintSeen: true }); ueBridge()?.fenster_verstecken(); },
});
let ueRestartT = 0;
// Board 25: Erlaubnis fehlt / wurde entzogen (z. B. nach einem Update)
window.ueberallErlaubnis = () => ueDialog({
  icon: icon("i-wave"), title: "Vorleser braucht einmal deine Erlaubnis", path: true,
  text: `Damit ${hkLang()} markierten Text aus anderen Apps holen kann. Die Erlaubnis fehlt oder wurde ausgeschaltet (zum Beispiel nach einem Update). Bis dahin: Text kopieren und im Menüleisten-Symbol „Zwischenablage vorlesen“ wählen.`,
  no: "Später", yes: "Einstellungen öffnen",
  onYes: () => {
    ueBridge()?.ueberall_einstellungen();
    $("ueText").textContent = "Warte auf die Erlaubnis … Schalte Vorleser in der Liste ein – das wird sofort erkannt.";
    $("ueYes").disabled = true;
    clearTimeout(ueRestartT);
    // Rückfall: nur wenn die Erlaubnis nach 20 s noch nicht erkannt wurde, Neustart anbieten (normal ist keiner nötig)
    ueRestartT = setTimeout(async () => {
      if (!$("ueDlg").open || !$("ueYes").disabled || (await ueBridge()?.ueberall_erlaubt())) return;
      $("ueText").textContent = "Schon eingeschaltet? Manchmal erkennt macOS die Erlaubnis erst nach einem Neustart von Vorleser.";
      $("ueYes").textContent = "Neu starten"; $("ueYes").disabled = false;
      $("ueYes").onclick = () => ueBridge()?.ueberall_neustart();
    }, 20000);
  },
});
window.ueberallErlaubt = () => {
  clearTimeout(ueRestartT);
  $("ueYes").disabled = false;
  ueDialog({ icon: icon("i-check"), title: "Erlaubt – Vorleser erkennt das sofort",
    text: `Kein Neustart nötig. Probier es: Text markieren, dann ${hkLang()}.`, no: "", yes: "Fertig" });
  ueRenderRows();
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
  $("newsDlg").showModal(); $("newsDlg").focus();                // nichts vorausgewählt (sonst leuchtet „Fehler melden“)
}
$("newsBtn").onclick = openNews;
$("newsClose").onclick = () => $("newsDlg").close();
$("newsBug").onclick = (e) => { e.preventDefault(); $("newsDlg").close(); openBug(); };

$("srcBtn").onclick = () => openExternal("https://github.com/SimonSchneZzer/vorleser");
$("updCheck").onclick = async () => {
  const b = $("updCheck"); b.disabled = true;
  upd.errLater = false;                                 // ausdrücklich gesucht → auch einen Fehler wieder zeigen
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
      ? "Senden fehlgeschlagen – bist du online?" : "Senden fehlgeschlagen – bitte später noch einmal versuchen.";
    reportClientError(`Fehler melden: ${err.message}`);
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
