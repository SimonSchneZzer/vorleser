"use strict";
// Vorleser – Start der Oberfläche. Teil der Oberfläche; Reihenfolge der Dateien: index.html
/* ===================================================================== */
/* Start                                                                  */
/* ===================================================================== */
async function startData() {
  // Server startet evtl. noch bzw. antwortet kurz nicht → weiter versuchen statt leerem Fenster.
  // Bildschirm erst nach 1,5 s (sonst flackert er bei jedem normalen Start), Glas-Karte nach ~7 s.
  const boot = $("boot"), retry = {};
  let wake = null;
  const tWait = setTimeout(() => boot.classList.remove("hidden"), 1500);
  const tCard = setTimeout(() => {
    boot.classList.remove("hidden"); boot.classList.add("stuck");
    $("bootWait").classList.add("hidden"); $("bootCard").classList.remove("hidden");
    $("bootQuit").classList.toggle("hidden", !window.pywebview?.api?.quit_app);   // im Browser gibt es nichts zu beenden
  }, 7000);
  $("bootRetry").onclick = () => { retry.fails = 0; wake?.(); };
  $("bootQuit").onclick = () => { try { window.pywebview?.api?.quit_app(); } catch {} };
  for (;;) {
    try {
      const res = await Promise.all([api("/api/settings"), reloadVoices()]);
      clearTimeout(tWait); clearTimeout(tCard);
      if (!boot.classList.contains("hidden")) {                         // weich ausblenden, dann weg
        boot.classList.add("leaving");
        setTimeout(() => boot.classList.add("hidden"), 320);
      }
      return res;
    } catch (e) {
      reportClientError(`Start: ${e?.message || e}`);
      await new Promise((ok) => { wake = ok; retryLater(retry, ok, 1000, true); });   // Hinweis gibt der Bildschirm selbst
    }
  }
}
(async () => {
  try { const r = localStorage.getItem("vorleser.rate"); if (r) $("rate").value = r; } catch {}
  const [settings] = await startData();
  st.settings = settings;
  if ((settings.uiLang || "de") !== UI_LANG) setUiLang(settings.uiLang || "de");
  applyTheme(); renderSettings(); renderPlay();
  $("dictTab").classList.toggle("hidden", !st.features.dictate);
  fillLangSelect();
  const docs = await refreshLibrary().catch((e) => { toastErr(e); return []; });
  const h = location.hash.slice(1);
  if (h.startsWith("einstellungen")) {
    showView("settings");
    const tab = h.split("/")[1];
    if (tab) document.querySelector(`#setTabs [data-tab="${tab}"]`)?.click(); else renderSettings();
  } else if (h === "neu" || !docs.length) showNew();
  else { await openDoc(docs[0].id); if (h === "bearbeiten") openEditor(); }
  if (h === "tutorial" || h.startsWith("rundgang")) gtStart(false, (parseInt(h.split("/")[1], 10) || 1) - 1);
  else if (!st.settings.onboarded || h === "willkommen") onbOpen("setup");
  st.started = true;                                     // Start-Ablauf fertig (Tests warten darauf, sonst springt er dazwischen)
})();

setInterval(() => { if (!document.hidden && $("libMenu").classList.contains("hidden")) renderLibrary(); }, 60000);   // „Gestern“/Uhrzeit aktuell halten

