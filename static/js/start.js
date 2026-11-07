"use strict";
// Vorleser – Start der Oberfläche. Teil der Oberfläche; Reihenfolge der Dateien: index.html
/* ===================================================================== */
/* Start                                                                  */
/* ===================================================================== */
(async () => {
  try { const r = localStorage.getItem("vorleser.rate"); if (r) $("rate").value = r; } catch {}
  const [settings] = await Promise.all([api("/api/settings"), reloadVoices()]);
  st.settings = settings;
  if ((settings.uiLang || "de") !== UI_LANG) setUiLang(settings.uiLang || "de");
  applyTheme(); renderSettings(); renderPlay();
  $("dictTab").classList.toggle("hidden", !st.features.dictate);
  fillLangSelect();
  const docs = await refreshLibrary();
  const h = location.hash.slice(1);
  if (h.startsWith("einstellungen")) {
    showView("settings");
    const tab = h.split("/")[1];
    if (tab) document.querySelector(`#setTabs [data-tab="${tab}"]`)?.click(); else renderSettings();
  } else if (h === "neu" || !docs.length) showNew();
  else { await openDoc(docs[0].id); if (h === "bearbeiten") openEditor(); }
  if (h === "tutorial" || h.startsWith("rundgang")) gtStart(false, (parseInt(h.split("/")[1], 10) || 1) - 1);
  else if (!st.settings.onboarded || h === "willkommen") onbOpen("setup");
})();

setInterval(() => { if (!document.hidden && $("libMenu").classList.contains("hidden")) renderLibrary(); }, 60000);   // „Gestern“/Uhrzeit aktuell halten

