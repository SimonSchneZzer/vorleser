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
  if (!r.ok) throw new Error((await r.json().catch(() => ({}))).error || r.statusText || `Fehler ${r.status}`);
  return r.json();
};

/** Antwort eines fetch() lesen: erst den Status prüfen, dann JSON (Fehlerseiten sind nicht immer JSON). */
async function readJson(r) {
  const d = await r.json().catch(() => null);
  if (!r.ok) throw new Error(d?.error || r.statusText || `Fehler ${r.status}`);
  if (d === null) throw new Error(UI_INTERN);          // 200, aber keine lesbare Antwort
  return d;
}

const st = {
  doc: null, idx: 0, pendingOffset: 0,
  cache: new Map(),              // idx -> {promise, url, used, fallback}
  loadedIdx: -1, wantPlay: false, token: 0, lastSave: 0, switching: false,
  voices: [], langs: {}, defaults: {}, features: {}, settings: null, docs: [],
  spans: [], readySet: new Set(), words: null, raf: 0,
  offline: false,                // 3.0.2: Nutzer hat „Offline-Stimme nutzen“ gewählt (nie automatisch)
  waitSince: 0,                  // seit wann der gebrauchte Abschnitt auf die Stimme wartet
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
const LOGO_BG = SURFACE.anthrazit;            // Logo: immer dunkle Fläche, Balken in der (hellen) Akzentfarbe – in jedem Modus
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
      "--logo-bar": readable(accentFor(s.accent, true), LOGO_BG),
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
}
// Dock-Icon: immer das feste Icon aus dem App-Paket (packaging/icon.png) – nicht mehr zur Laufzeit umgefärbt,
// sonst wechselt es beim Schließen der App die Farbe (siehe docs/DECISIONS.md, 2026-11-07).
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
/** Kurze Meldung unten. action = { label, fn }: Knopf darin (z. B. „Rückgängig“), Meldung bleibt dann länger stehen. */
function toast(msg, err = false, action = null) {
  const t = $("toast");
  // Über offenen Dialogen (Top-Layer) sichtbar: als Popover neu öffnen – ältere WebViews ohne Popover: wie bisher
  if (t.showPopover && document.querySelector("dialog[open]")) {
    try { if (t.matches(":popover-open")) t.hidePopover(); t.showPopover(); } catch {}
  }
  t.textContent = msg; t.classList.toggle("err", err);
  // Rote Meldung: gleich „Fehler melden“ anbieten, Meldung wird ins Formular übernommen (3.0.3, Simon)
  if (!action && err && typeof openBug === "function" && typeof bug !== "undefined" && bug.info?.enabled) action = { label: "Fehler melden", fn: () => openBug(msg) };
  if (action) {
    const b = document.createElement("button"); b.className = "tbtn"; b.textContent = action.label;
    b.onclick = () => { toastHide(t); action.fn(); };
    t.append(b);
  }
  t.classList.toggle("act", !!action);
  t.classList.add("show");
  toastArm(t, err ? 9000 : action ? 6000 : 2200);       // Fehler: Zeit zum Lesen (3.0.3)
}
/** Ausblenden planen; solange die Maus auf dem Toast ist, steht die Uhr (danach die Restzeit, mindestens 1,5 s). */
const toastS = { until: 0, left: 0, hover: false };
function toastArm(t, ms) {
  clearTimeout(toastT); toastS.until = Date.now() + ms; toastS.left = ms;
  if (!toastS.hover) toastT = setTimeout(() => toastHide(t), ms);
}
$("toast").addEventListener("mouseenter", () => { toastS.hover = true; clearTimeout(toastT); toastS.left = Math.max(0, toastS.until - Date.now()); });
$("toast").addEventListener("mouseleave", () => { toastS.hover = false; if ($("toast").classList.contains("show")) toastArm($("toast"), Math.max(1500, toastS.left)); });
/** Toast ausblenden: erst gleitet er weg, danach verliert er die Knopf-Gestalt (vorher sprang er im ersten Frame
 *  auf die schmale Form ohne Knopf und blendete erst dann aus). */
let toastActT = 0;
function toastHide(t) {
  t.classList.remove("show");
  clearTimeout(toastActT); toastActT = setTimeout(() => { if (!t.classList.contains("show")) t.classList.remove("act"); }, 380);
}
function toastErr(e) { console.error(e); toast(friendlyError(e), true); }
const UI_INTERN = "Etwas ist schiefgelaufen – die Details stehen im Log. Über „Fehler melden“ kannst du sie mitschicken.";
function friendlyError(e) {
  if (e == null) return UI_INTERN;
  const m = e?.message || String(e);
  if (/Failed to fetch|NetworkError|Load failed|did not match the expected pattern/i.test(m)) return "Der Vorleser-Server antwortet nicht – läuft er noch?";
  if (e instanceof TypeError || e instanceof ReferenceError || e instanceof SyntaxError || e instanceof RangeError) return UI_INTERN;   // Programmierfehler → kein JS-Rohtext
  return m;
}
/* ---------- Unerwartete Fehler: ins Log (pywebview hat keine sichtbare Konsole) + kurze Meldung ---------- */
let clientErrors = 0;
function reportClientError(msg, stack) {
  if (++clientErrors > 20) return;                           // keine Flut bei Fehlern in Schleifen
  fetch("/api/client-error", { method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ msg: String(msg || ""), stack: String(stack || "") }) }).catch(() => {});
}
window.addEventListener("error", (e) => reportClientError(e.message, e.error?.stack));
window.addEventListener("unhandledrejection", (e) => {
  const r = e.reason;
  if (r?.name === "AbortError" || r?.name === "NotAllowedError") return;   // abgebrochenes Audio, Autoplay-Sperre
  reportClientError(r?.message || r, r?.stack);
  if (clientErrors <= 5) toast(friendlyError(r), true);    // wiederkehrender Fehler: nur ins Log, keine Toast-Flut
});
/** Abfrage-Schleife nach einem Fehler weiterführen: 2 s → 4 s → … max. 30 s; ab dem 3. Fehler ein Hinweis. */
function retryLater(state, fn, base = 2000, quiet = false) {
  state.fails = (state.fails || 0) + 1;
  if (state.fails === 3 && !quiet) toast("Keine Verbindung zum Vorleser – es wird weiter versucht …", true);
  return setTimeout(fn, Math.min(30000, base * 2 ** (state.fails - 1)));
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
  if (el._soft) { el._soft.cancel(); el._soft = null; }   // gerade am Schließen (softHide) → wieder auf
  el.classList.remove(cls); void el.offsetWidth; el.classList.add(cls);
  // Nur das eigene Animationsende zählt – Kinder (z. B. der Auswahlpunkt) würden sonst zu früh abbrechen.
  el.addEventListener("animationend", function done(e) {
    if (e.target !== el && el.getAnimations?.().length) return;
    el.classList.remove(cls); el.removeEventListener("animationend", done);
  });
}
const EASE = "cubic-bezier(.2, .8, .2, 1)", EASE_OUT = "cubic-bezier(.16, 1, .3, 1)";
/** Gegenstück zu animateIn(el, "enter") für kleine Menüs/Popups: kurz ausblenden + leicht schrumpfen, dann verstecken
 *  (vorher waren sie von einem Frame auf den nächsten weg). Nur opacity/transform – nie filter (Glas, CLAUDE.md). */
function softHide(el, dur = 150) {
  if (!el || el.classList.contains("hidden") || el._soft) return;
  el.classList.remove("enter");
  if (reducedMotion.matches || !el.animate) { el.classList.add("hidden"); return; }
  const a = el._soft = el.animate([{ opacity: 1, transform: "none" }, { opacity: 0, transform: "translateY(-4px) scale(.97)" }], { duration: dur, easing: EASE });
  a.onfinish = () => { if (el._soft === a) { el._soft = null; el.classList.add("hidden"); } };
}
/** Inhalt eines Dialogs/einer Karte tauschen: Höhe gleitet, das Neue blendet von unten ein, ein Häkchen-Symbol darin
 *  springt einmal auf (statt Formular weg → Bestätigung da von einem Frame auf den nächsten). */
function swapIn(box, outEl, inEl) {
  const done = heightFrom(box);
  outEl.classList.add("hidden"); inEl.classList.remove("hidden");
  done(440); animateIn(inEl, "swap-in");
}
/** Ein-/Ausblenden, das je nach Zustand immer wieder aufgerufen werden darf (macht nichts, wenn sich nichts ändert):
 *  In einer Zeile (Flex-Zeile, Text) wird die Breite weich, sonst die Höhe – die Nachbarn rücken mit, statt zu springen
 *  (auch die Lücke `gap` der Zeile, über einen negativen Rand). Nicht sichtbar (Ansicht zu) → sofort. */
function toggleSoft(el, on) {
  if (!el) return;
  if (el._tg) { const off = el._tgOff; el._tg.cancel(); el._tg = null; if (off) el.classList.add("hidden"); }
  if (on === !el.classList.contains("hidden")) return;
  if (!el.parentElement?.getClientRects().length || reducedMotion.matches || !el.animate) { el.classList.toggle("hidden", !on); return; }
  el.classList.remove("hidden");
  const cs = getComputedStyle(el), ps = getComputedStyle(el.parentElement);
  const row = cs.display.startsWith("inline") || (/flex/.test(ps.display) && !ps.flexDirection.startsWith("column"));
  const gap = /flex|grid/.test(ps.display) ? parseFloat(ps.columnGap) || 0 : 0;
  const [S, A, B, M1, M2] = row ? ["width", "paddingLeft", "paddingRight", "marginLeft", "marginRight"] : ["height", "paddingTop", "paddingBottom", "marginTop", "marginBottom"];
  const full = { [S]: `${row ? el.offsetWidth : el.offsetHeight}px`, [A]: cs[A], [B]: cs[B], [M1]: cs[M1], [M2]: cs[M2], opacity: 1, transform: "none" };
  const zero = { [S]: "0px", [A]: "0px", [B]: "0px", [M1]: "0px", [M2]: "0px", opacity: 0, transform: row ? "scale(.9)" : "none" };
  if (row && gap) {                                    // Lücke zum sichtbaren Nachbarn mit einklappen
    const sib = [...el.parentElement.children].filter((c) => c === el || c.getClientRects().length), k = sib.indexOf(el);
    if (k > 0) zero[M1] = `${-gap}px`; else if (sib.length > 1) zero[M2] = `${-gap}px`;
  }
  if (row) full.minWidth = zero.minWidth = "0px";
  const frames = [zero, full], opts = { duration: on ? 380 : 280, easing: on ? EASE_OUT : EASE };
  el.style.overflow = "hidden"; if (row) el.style.whiteSpace = "nowrap";
  if (!on) frames.reverse();
  const a = el._tg = el.animate(frames, opts); el._tgOff = !on;
  a.onfinish = () => { if (el._tg !== a) return; el._tg = null; el.style.overflow = el.style.whiteSpace = ""; if (!on) el.classList.add("hidden"); };
  a.oncancel = () => { el.style.overflow = el.style.whiteSpace = ""; };
}
/** Kurze Beschriftung wechselt mit einem kleinen Rollen (alt nach oben weg, neu von unten) statt zu springen.
 *  Kommen Änderungen schneller als die Bewegung (Ziehen am Balken), wird ohne Bewegung gesetzt. */
function rollText(el, text) {
  if (!el || el.textContent === text) return;
  if (el._roll) { el._roll.cancel(); el._roll = null; el.textContent = text; return; }
  if (!el.getClientRects().length || reducedMotion.matches || !el.animate || !el.textContent) { el.textContent = text; return; }
  if (getComputedStyle(el).display === "inline") el.style.display = "inline-block";
  const out = el._roll = el.animate([{ transform: "none", opacity: 1 }, { transform: "translateY(-45%)", opacity: 0 }], { duration: 110, easing: "ease-in" });
  out.onfinish = () => {
    if (el._roll !== out) return;
    // Steckt die Beschriftung in einem Knopf, gleitet dessen Breite mit (sonst springt er z. B. bei „Alles vorbereitet“)
    const host = el.closest("button, .pill"), w0 = host?.offsetWidth;
    el.textContent = text;
    const w1 = host?.offsetWidth;
    if (host && Math.abs(w1 - w0) > 1) {
      host.style.overflow = "hidden";
      host.animate([{ width: `${w0}px` }, { width: `${w1}px` }], { duration: 320, easing: EASE_OUT }).onfinish = () => { host.style.overflow = ""; };
    }
    const inn = el._roll = el.animate([{ transform: "translateY(45%)", opacity: 0 }, { transform: "none", opacity: 1 }], { duration: 260, easing: EASE_OUT });
    inn.onfinish = () => { if (el._roll === inn) el._roll = null; };
  };
}
/** Leiser Zwei-Ton-Klang für „fertig“ (selbst erzeugt, keine Datei): zwei kurze Sinustöne, Quinte nach oben. */
let chimeCtx = null;
function chime() {
  try { chimeCtx ||= new (window.AudioContext || window.webkitAudioContext)(); chimeCtx.resume?.(); } catch { return; }
  const c = chimeCtx, t0 = c.currentTime + 0.02;
  for (const [f, d] of [[880, 0], [1318.5, 0.12]]) {
    const o = c.createOscillator(), g = c.createGain();
    o.type = "sine"; o.frequency.value = f;
    g.gain.setValueAtTime(0, t0 + d); g.gain.linearRampToValueAtTime(0.05, t0 + d + 0.012);
    g.gain.exponentialRampToValueAtTime(0.0001, t0 + d + 0.9);
    o.connect(g).connect(c.destination); o.start(t0 + d); o.stop(t0 + d + 1);
  }
}
/* Dialoge schließen weich (3.0.3, Simon: „harter Cut bei Abbrechen“): close() – auch über Esc – blendet den Dialog und
   den Hintergrund kurz aus und schließt erst dann. `open` gilt währenddessen schon als zu; showModal() in der Zeit
   bricht das Schließen ab (der Dialog bleibt einfach offen). Dialoge sind keine Glasflächen → opacity ist erlaubt. */
{
  const P = HTMLDialogElement.prototype, close0 = P.close, show0 = P.showModal;
  const openD = Object.getOwnPropertyDescriptor(P, "open");
  P.close = function (rv) {
    if (!this.hasAttribute("open") || reducedMotion.matches) return close0.call(this, rv);
    if (this._closeT) return;
    this.classList.add("closing");
    this._closeT = setTimeout(() => { this._closeT = 0; this.classList.remove("closing"); close0.call(this, rv); }, 170);
  };
  P.showModal = function () {
    if (this._closeT) { clearTimeout(this._closeT); this._closeT = 0; this.classList.remove("closing"); return; }
    return show0.call(this);
  };
  if (openD?.get) Object.defineProperty(P, "open", { ...openD, get() { return openD.get.call(this) && !this._closeT; } });
  document.addEventListener("cancel", (e) => {
    if (e.target instanceof HTMLDialogElement && !reducedMotion.matches) { e.preventDefault(); e.target.close(); }
  }, true);
}
/** Sichtbar und nicht gerade am Schließen (für Knöpfe, die ein Menü auf/zu schalten). */
function isShown(el) { return !!el && !el.classList.contains("hidden") && !el._soft; }
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
/** Jedes <details> klappt weich auf und zu (Höhe gleitet, Inhalt blendet mit) statt von einem Frame auf den anderen. */
document.addEventListener("click", (e) => {
  const sum = e.target.closest("details > summary");
  if (!sum || reducedMotion.matches || !sum.animate) return;
  e.preventDefault();
  const d = sum.parentElement, body = [...d.children].filter((x) => x !== sum);
  const opening = !d.open || d.classList.contains("closing");
  const h0 = d.offsetHeight;
  d._da?.cancel();
  d.classList.toggle("closing", !opening);
  d.open = true;
  const h1 = opening ? d.offsetHeight : sum.offsetHeight;
  d.style.overflow = "hidden";
  const a = d._da = d.animate([{ height: `${h0}px` }, { height: `${h1}px` }], { duration: opening ? 420 : 300, easing: opening ? EASE_OUT : EASE });
  const fade = [{ opacity: 0, transform: "translateY(-6px)" }, { opacity: 1, transform: "none" }];
  body.forEach((x) => x.animate(opening ? fade : fade.slice().reverse(), { duration: opening ? 380 : 200, easing: EASE, fill: "both" }));
  a.onfinish = () => {
    d.style.overflow = "";
    if (!opening) { d.open = false; d.classList.remove("closing"); }
    body.forEach((x) => x.getAnimations().forEach((an) => an.cancel()));
  };
});
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

