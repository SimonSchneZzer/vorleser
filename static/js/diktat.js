"use strict";
// Vorleser – Diktieren: Mikrofon, Aufnahme und der schwebende Diktier-Knopf (Bauteil für „Neuer Text“, später auch
// „Text bearbeiten“). Teil der Oberfläche; Reihenfolge der Dateien: index.html (vor neuer-text.js).

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

/**
 * Schwebender Diktier-Knopf (Glas, unten rechts im Feld – bleibt beim Scrollen stehen).
 * Ruhe: rundes Mikrofon, beim Darüberfahren gleitet „Diktieren“ heraus. Aufnahme: orange, „Stopp · 0:07“.
 * Danach Whisper (lokal) → opts.insert(text, lang). Glas-Regel (CLAUDE.md): nur transform/Breite animieren,
 * kein opacity/filter auf dem Knopf.
 *   btn: <button class="fmic glass"> mit .fm-lbl darin
 *   opts.lang(): erzwungene Sprache oder null (erkennen) · opts.insert(text, lang) · opts.onStart()
 */
function micFab(btn, opts) {
  const lbl = btn.querySelector(".fm-lbl");
  const S = { rec: null, timer: 0 };
  const set = (cls, text, aria) => {
    btn.classList.toggle("on", cls === "on"); btn.classList.toggle("busy", cls === "busy");
    lbl.textContent = text; btn.setAttribute("aria-label", aria || text);
  };
  const idle = () => { btn.disabled = false; set("", "Diktieren", "Diktieren"); };
  async function start() {
    try { S.rec = startRecorder(await getMic()); }
    catch (e) { reportClientError(`Mikrofon: ${e?.message || e}`); toast("Mikrofon nicht verfügbar – bitte den Zugriff in den Systemeinstellungen erlauben.", true); return; }
    opts.onStart?.();
    const tick = () => set("on", `Stopp · ${mmss(S.rec.secs())}`, "Diktat beenden");
    tick(); S.timer = setInterval(tick, 250);
  }
  async function stop() {
    clearInterval(S.timer);
    const blob = await S.rec.stop(); S.rec = null; releaseMic();
    btn.disabled = true;
    let first = true; try { first = !localStorage.getItem("vorleser.sttReady"); } catch {}
    set("busy", first ? "Sprachmodell wird geladen …" : "Wird umgewandelt …");
    try {
      const lang = opts.lang?.();
      const d = await readJson(await fetch("/api/transcribe", { method: "POST", body: blob, headers: lang ? { "X-Lang": lang } : {} }));
      try { localStorage.setItem("vorleser.sttReady", "1"); } catch {}
      if (d.text?.trim()) opts.insert(d.text.trim(), d.lang);
    } catch (e) { toastErr(e); }
    finally { idle(); }
  }
  btn.onclick = () => (S.rec ? stop() : start());
  idle();
  return {
    recording: () => !!S.rec,
    /** Ansicht verlassen o. Ä.: Aufnahme beenden und trotzdem umwandeln (nichts geht verloren). */
    finish: () => (S.rec ? stop() : null),
  };
}
