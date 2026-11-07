"use strict";
/* Oberflächensprache: Deutsch ist die Quelle, Englisch wird beim Anzeigen übersetzt.
   Ein MutationObserver übersetzt auch alles, was später per JavaScript erscheint.
   Ausgenommen sind Bereiche mit [data-noi18n] (Lesetext, Titel, Kapitelnamen …). */

const I18N_EN = {
  // Desktop-App & eigene Stimme installieren
  "Fehler melden": "Report a problem",
  "Wird im Hintergrund erzeugt – du kannst weiterhören oder woanders hin. ✕ bricht ab.": "Generating in the background – keep listening or go elsewhere. ✕ cancels.",
  "Alle Abschnitte sind fertig – alles spielt ohne Wartezeit.": "All sections are ready – everything plays without waiting.",
  "Rundgang": "Tour", "Alle Funktionen in einer Minute": "All features in one minute", "Starten": "Start", "Updates": "Updates",
  "Prüft bei jedem Start automatisch": "Checks automatically on every start", "Jetzt suchen": "Check now", "Du hast die neueste Version": "You have the latest version",
  "Kurz beschreiben, was nicht klappt": "Briefly describe what isn’t working", "Melden": "Report", "Beenden": "Quit",
  "Schließt das Fenster und stoppt alles im Hintergrund": "Closes the window and stops everything in the background",
  "Deinstallieren": "Uninstall", "App und Daten von diesem Computer entfernen": "Remove the app and its data from this computer", "Vorab erzeugen abbrechen": "Cancel preparing", "Zum Text": "Go to text", "Zum Text springen": "Jump to text",
  "Vorleser deinstallieren": "Uninstall Vorleser", "Vorleser deinstallieren?": "Uninstall Vorleser?", "Deinstallieren": "Uninstall",
  "Die App wird geschlossen und von diesem Computer entfernt. Dabei wird gelöscht:": "The app will close and be removed from this computer. This deletes:",
  "Die App selbst": "The app itself", "Eigene Stimmen": "Own voices", "Erzeugtes Audio und Exporte": "Generated audio and exports",
  "Modelle (Diktat, eigene Stimme)": "Models (dictation, own voice)", "bleibt": "kept",
  "Meine Texte und eigenen Stimmen behalten": "Keep my texts and own voices", "Das lässt sich nicht rückgängig machen.": "This cannot be undone.",
  "Texte und eigene Stimmen bleiben im Datenordner erhalten.": "Texts and own voices stay in the data folder.",
  "Wirklich alles löschen?": "Really delete everything?", "Wirklich deinstallieren?": "Really uninstall?",
  "Vorleser wird entfernt": "Removing Vorleser", "Danke fürs Ausprobieren! Das Fenster schließt sich gleich.": "Thanks for trying it! This window will close in a moment.",
  "Belegt": "Used", "Audio deiner Texte": "Audio of your texts", "Hörproben": "Voice samples", "Reste": "Leftovers", "Exporte": "Exports", "Modelle": "Models",
  "Pro Text": "Per text", "Sonstiges": "Other", "Alles leeren": "Clear all", "Ohne Titel": "Untitled", "Weniger anzeigen": "Show less",
  "Audio löschen (der Text bleibt)": "Delete audio (the text stays)", "Hörproben löschen": "Delete voice samples", "Reste löschen": "Delete leftovers",
  "Alle Exporte löschen": "Delete all exports", "Stimmen-Vorschau in den Einstellungen": "Voice previews in the settings",
  "von gelöschten oder bearbeiteten Texten": "from deleted or edited texts", "fertige Hörbuch-Dateien": "finished audiobook files",
  "Diktat (Whisper)": "Dictation (Whisper)", "wird beim ersten Diktat geladen": "downloaded on first dictation",
  "lädt nach dem Entfernen beim nächsten Diktat neu": "re-downloads on next dictation after removal", "installiert": "installed",
  "Alle Exporte löschen?": "Delete all exports?", "Die fertigen Hörbuch-Dateien werden gelöscht. Du kannst sie jederzeit neu exportieren.": "The finished audiobook files will be deleted. You can export them again anytime.",
  "Diktat-Modell entfernen?": "Remove dictation model?", "Gibt ca. 500 MB frei. Beim nächsten Diktat wird es wieder geladen (Internet nötig).": "Frees about 500 MB. It will be downloaded again on the next dictation (internet required).", "Sprache des Aufnahmetexts": "Language of the recording text",
  "Gesendet über den Formulardienst Web3Forms; dabei wird deine IP-Adresse übermittelt.": "Sent via the form service Web3Forms, which receives your IP address.", "Danke für deine Meldung!": "Thanks for your report!", "Sie ist angekommen.": "It has been received.",
  "Sie ist angekommen. Bei Rückfragen melde ich mich per E-Mail.": "It has been received. If there are questions, you’ll get an email.",
  "Was ist passiert, und was hast du davor gemacht? Je genauer, desto schneller lässt es sich beheben.": "What happened, and what did you do right before? The more precise, the faster it can be fixed.",
  "z. B. Beim Export als M4B bleibt der Balken bei 80 % stehen …": "e.g. When exporting as M4B the progress bar stops at 80 % …",
  "E-Mail für Rückfragen (optional)": "Email for follow-up questions (optional)", "Technische Infos anhängen": "Attach technical info",
  "Was wird mitgeschickt?": "What gets sent?", "Senden": "Send", "Wird gesendet …": "Sending …", "Beschreibung": "Description",
  "Bitte kurz beschreiben, was passiert ist.": "Please briefly describe what happened.", "Die E-Mail-Adresse sieht nicht richtig aus.": "That email address doesn’t look right.",
  "Bitte warte etwas, bevor du noch eine Meldung schickst.": "Please wait a little before sending another report.", "Senden fehlgeschlagen – bist du online?": "Sending failed – are you online?",
  "Eigene Stimme installieren": "Install own voice", "Eigene Stimme verwenden": "Use your own voice", "Eigene Stimme wird installiert": "Installing own voice", "Wird vorbereitet": "Getting ready",
  "Python wird geladen": "Downloading Python", "Programmteile werden geladen": "Downloading components", "Stimmmodell wird geladen": "Downloading voice model",
  "Wird installiert": "Installing", "Fertig!": "Done!", "Programmteile": "Components", "Stimmmodell": "Voice model", "Läuft seit": "Running for",
  "Eine eigene Python-Version wird geladen": "Downloading a separate Python version", "Eigene Umgebung wird eingerichtet": "Setting up a separate environment",
  "Passende Pakete werden zusammengestellt": "Picking the right packages", "Programmteile werden ausgepackt und installiert": "Unpacking and installing components",
  "Programmteile sind fertig.": "Components are ready.", "Das Stimmmodell wird geladen": "Downloading the voice model",
  "Die Verbindung ist gerade langsam – es geht gleich weiter.": "The connection is slow right now – it’ll continue shortly.",
  "Große Pakete werden ausgepackt – das dauert einen Moment.": "Unpacking large packages – this takes a moment.",
  "Eine große Datei ist in Arbeit (z. B. PyTorch) – es geht gleich weiter.": "Working on a large file (e.g. PyTorch) – it’ll continue shortly.",
  "Restzeit wird berechnet": "Estimating time left", "gleich fertig": "almost done", "Fast fertig – das Stimmmodell wird eingerichtet": "Almost done – setting up the voice model", "Das Stimmmodell wird vorbereitet": "Preparing the voice model", "noch weniger als 1 Min.": "less than 1 min left",
  "Alles bereit – jetzt deine Stimme aufnehmen.": "All set – now record your voice.",
  "Installation abbrechen": "Cancel installation", "Weiter installieren": "Keep installing",
  "Der Vorleser bekommt eine eigene Python-Version – getrennt von allem anderen auf deinem Rechner.": "Vorleser gets its own Python version – separate from everything else on your computer.",
  "Alles landet nur im Vorleser-Ordner und lässt sich in den Einstellungen wieder entfernen.": "Everything stays in the Vorleser folder and can be removed again in the settings.",
  "Gerade kommt PyTorch – die Rechenbibliothek, mit der das Stimmmodell arbeitet.": "PyTorch is on its way – the computing library the voice model runs on.",
  "Du kannst den Vorleser währenddessen ganz normal benutzen.": "You can keep using Vorleser as usual meanwhile.",
  "Später rechnet der Grafikchip deines Macs die Stimme aus.": "Later, your Mac’s graphics chip will compute the voice.",
  "Später rechnet deine NVIDIA-Grafikkarte die Stimme aus.": "Later, your NVIDIA graphics card will compute the voice.",
  "Ohne passende Grafikkarte rechnet der Prozessor – das klappt, dauert aber länger.": "Without a suitable graphics card the processor does the work – it works, but takes longer.",
  "Jetzt das Herzstück: das Stimmmodell „Chatterbox“ von Resemble AI (MIT-Lizenz).": "Now the centerpiece: the “Chatterbox” voice model by Resemble AI (MIT license).",
  "Danach reichen 15–30 Sekunden Aufnahme deiner Stimme.": "After that, 15–30 seconds of your voice are all it takes.",
  "Tipp für die Aufnahme: ruhiger Raum, normaler Abstand zum Mikrofon.": "Recording tip: quiet room, normal distance to the microphone.",
  "Deine Stimme liest danach Deutsch und Englisch.": "Your voice will then read German and English.",
  "Lädt ca. 3,4 GB und dauert je nach Verbindung 10–30 Minuten. Die Stimme läuft danach auf dem Grafikchip deines Macs.": "Downloads about 3.4 GB and takes 10–30 minutes depending on your connection. The voice then runs on your Mac’s graphics chip.",
  "Lädt ca. 5,7 GB und dauert je nach Verbindung 15–40 Minuten. Die Stimme läuft danach auf deiner NVIDIA-Grafikkarte.": "Downloads about 5.7 GB and takes 15–40 minutes depending on your connection. The voice then runs on your NVIDIA graphics card.",
  "Lädt ca. 3,5 GB und dauert je nach Verbindung 10–30 Minuten. Ohne NVIDIA-Grafikkarte rechnet der Prozessor – das funktioniert, braucht aber pro Abschnitt deutlich länger.": "Downloads about 3.5 GB and takes 10–30 minutes depending on your connection. Without an NVIDIA graphics card the processor does the work – it works, but each section takes much longer.",
  "Später": "Later", "Aktualisieren": "Update", "Download-Seite": "Download page", "Nach Updates suchen": "Check for updates",
  "Update wird geladen": "Downloading update",  "Update fehlgeschlagen": "Update failed",
  "Vorleser schließt sich kurz und startet in der neuen Version neu.": "Vorleser closes briefly and restarts in the new version.",
  "Update wird vorbereitet": "Preparing update", "Einen Moment – du kannst weiter vorlesen.": "One moment – you can keep listening.",
  "Open Source": "Open source", "Freie Software unter GPL-3.0 · Quellcode und Lizenzen auf GitHub": "Free software under GPL-3.0 · source code and licenses on GitHub", "Ansehen": "View",
  "Update bereit": "Update ready", "Jetzt neu starten": "Restart now", "Startet neu …": "Restarting …",
  "Vorleser ist gleich in der neuen Version zurück.": "Vorleser will be back in the new version in a moment.",
  "Wird im Hintergrund geladen, du kannst weiter vorlesen.": "Downloads in the background, you can keep listening.",
  "Prüfen fehlgeschlagen – bist du online?": "Check failed – are you online?", "Keine Update-Information gefunden": "No update information found",
  "Bitte Vorleser zuerst in den Ordner Programme ziehen": "Please move Vorleser to the Applications folder first",
  "Eigene Stimme installieren?": "Install own voice?",
  "Lädt ca. 4,5 GB aus dem Internet (PyTorch + Chatterbox-Modell) und braucht etwa 10–30 Minuten. Auf dem Mac nutzt die Stimme den Grafikchip, unter Windows eine NVIDIA-Grafikkarte – ohne sie läuft sie, aber sehr langsam.":
    "Downloads about 4.5 GB (PyTorch + Chatterbox model) and takes about 10–30 minutes. On a Mac the voice uses the graphics chip, on Windows an NVIDIA graphics card – without one it works, but very slowly.",
  "Installieren": "Install", 
  
  
  "Das dauert je nach Internet 10–30 Minuten. Du kannst den Vorleser währenddessen normal benutzen.":
    "Depending on your connection this takes 10–30 minutes. You can keep using Vorleser meanwhile.",
  "Installation abbrechen?": "Cancel installation?", "Bereits Geladenes wird verworfen.": "Everything downloaded so far is discarded.",
  "Eigene Stimme entfernen?": "Remove own voice?", "Entfernen": "Remove", "Eigene Stimme entfernt": "Own voice removed",
  "Gibt ca. 4,5 GB frei. Deine Sprachproben bleiben erhalten – nach erneutem Installieren sind die eigenen Stimmen wieder da.":
    "Frees about 4.5 GB. Your voice samples are kept – after reinstalling, your own voices are back.",
  "Eigene Stimme installiert – jetzt „Eigene Stimme anlegen“": "Own voice installed – now “Create own voice”",
  "installiert · ca. 4,5 GB": "installed · approx. 4.5 GB", "nicht installiert · ca. 4,5 GB": "not installed · approx. 4.5 GB",
  "Der Vorleser läuft, solange dieses Fenster offen ist. Schließen beendet ihn.": "Vorleser runs while this window is open. Closing it quits Vorleser.",
  "Wiedergabe und laufende Exporte werden gestoppt. Zum Starten den Vorleser wieder öffnen.": "Playback and running exports will stop. Open Vorleser again to start.",
  "Gespeichert": "Saved", "Speichern fehlgeschlagen": "Saving failed",
  // Allgemein & Navigation
  "Neuer Text": "New text", "Bibliothek": "Library", "Bibliothek durchsuchen": "Search library", "Bibliothek öffnen": "Open library",
  "Einstellungen": "Settings", "Hell/Dunkel umschalten": "Toggle light/dark", "Hell / Dunkel umschalten": "Toggle light / dark",
  "Hellen Modus aktivieren": "Switch to light mode", "Dunklen Modus aktivieren": "Switch to dark mode",
  "Nichts gefunden.": "Nothing found.", "Noch keine Texte.": "No texts yet.", "neu": "new", "fertig gehört": "finished",
  "Gestern": "Yesterday", "Zurück": "Back", "Schließen": "Close", "Abbrechen": "Cancel", "Speichern": "Save", "Speichert …": "Saving …",
  "Gespeichert": "Saved", "Gelöscht": "Deleted", "Löschen": "Delete", "Löschen …": "Delete …", "Leeren": "Clear", "Beenden": "Quit",
  "Verwerfen": "Discard", "Erneut versuchen": "Try again", "Weitere Aktionen": "More actions", "Vorleser.app": "Vorleser.app",
  "Leertaste": "Space",

  // Hören
  "Kapitel wählen": "Choose chapter", "Exportieren": "Export", "Als Hörbuch speichern (M4B / MP3 / WAV)": "Save as audiobook (M4B / MP3 / WAV)",
  "Vorab erzeugen": "Prepare in advance", "Alles vorbereitet": "All prepared",
  "Erzeugt alle Abschnitte schon jetzt im Hintergrund. Danach spielt alles ohne Wartezeit – ideal für deine eigene Stimme, die pro Abschnitt etwas länger braucht. Nochmal klicken stoppt.":
    "Generates all sections in the background now. Afterwards everything plays without waiting – ideal for your own voice, which takes a bit longer per section. Click again to stop.",
  "Position im Text": "Position in text", "Vorheriger Abschnitt": "Previous section", "Nächster Abschnitt": "Next section",
  "10 Sekunden zurück": "Back 10 seconds", "10 Sekunden vor": "Forward 10 seconds", "10 s zurück": "Back 10 s", "10 s vor": "Forward 10 s",
  "Abspielen": "Play", "Pause": "Pause", "Lädt … (klicken zum Stoppen)": "Loading … (click to stop)",
  "Tempo": "Speed", "Stimme wählen": "Choose voice", "Stimme wechseln": "Change voice", "Stimme": "Voice",
  "Bereite vor …": "Preparing …", "Eigene Stimme erzeugt …": "Your voice is generating …", "Lesezeichen": "Bookmark",
  "Fertig gehört": "Finished", "Letzter Abschnitt": "Last section",
  "Der nächste Abschnitt muss erst erzeugt werden": "The next section still has to be generated",
  "der nächste fehlt noch": "next one still missing",
  "Nächste Abschnitte sind bereit": "Next sections are ready", "offline: Ersatzstimme": "offline: backup voice",
  "Online-Stimme nicht erreichbar – Piper liest offline weiter": "Online voice unreachable – Piper continues offline",
  "Audio konnte nicht geladen werden": "Audio could not be loaded", "Wiedergabe unterbrochen": "Playback interrupted",
  "Wiedergabe fehlgeschlagen": "Playback failed", "Synthese fehlgeschlagen": "Speech synthesis failed",
  "Der Vorleser-Server antwortet nicht – läuft er noch?": "The Vorleser server isn't responding – is it still running?",
  "Text bearbeiten": "Edit text", "Als Hörbuch exportieren": "Export as audiobook", "Text löschen": "Delete text",

  // Stimmen-Panel
  "Aktuell": "Current", "★ Favoriten": "★ Favorites", "Eigene Stimme": "Your voice", "Eigene Stimmen": "Your voices", "lokal": "local",
  "lokal · langsam": "local · slow", "Stimmen-Bibliothek öffnen": "Open voice library", "Online · natürlich": "Online · natural",
  "Wird vorbereitet … ca. 1 Min.": "Getting ready … about 1 min", "Lädt länger · am besten vorab erzeugen": "Takes longer to load · best prepared in advance",
  "Weiblich": "Female", "Männlich": "Male", "mehrsprachig": "multilingual",
  "Deutschland": "Germany", "Österreich": "Austria", "Schweiz": "Switzerland", "USA": "USA", "Großbritannien": "United Kingdom",
  "Australien": "Australia", "Kanada": "Canada", "Irland": "Ireland", "Indien": "India", "Neuseeland": "New Zealand",
  "Südafrika": "South Africa", "Singapur": "Singapore", "Philippinen": "Philippines", "Hongkong": "Hong Kong", "Kenia": "Kenya",
  "Nigeria": "Nigeria", "Tansania": "Tanzania", "Deutsch": "German", "English": "English",

  // Neuer Text
  "Einfügen, Datei laden oder einfach sprechen. Kapitel und Sprache werden automatisch erkannt.": "Paste, load a file or simply speak. Chapters and language are detected automatically.",
  "Quelle": "Source", "Einfügen": "Paste", "Datei": "File", "Diktieren": "Dictate", "Titel": "Title", "Titel (optional)": "Title (optional)", "Text": "Text",
  "Text hier einfügen …  Kapitel kannst du mit „# Überschrift“ markieren.": "Paste text here …  Mark chapters with “# Heading”.",
  "EPUB, PDF, TXT, Markdown oder HTML hierher ziehen oder": "Drop EPUB, PDF, TXT, Markdown or HTML here or",
  "Datei wählen": "Choose file", "Datei hierher ziehen": "Drop a file here",
  "EPUB, PDF, TXT, Markdown oder HTML – Kapitel werden automatisch erkannt": "EPUB, PDF, TXT, Markdown or HTML – chapters are detected automatically",
  "Diktat starten": "Start dictation", "Diktat beenden": "Stop dictation",
  "Tippen und losreden. Längere Pausen werden zu Absätzen. Läuft lokal mit Whisper.": "Tap and start talking. Longer pauses become paragraphs. Runs locally with Whisper.",
  "Aufnahme läuft – nochmal tippen zum Beenden.": "Recording – tap again to stop.",
  "Wandle in Text um … (beim ersten Mal wird das Sprachmodell geladen)": "Converting to text … (the speech model loads the first time)",
  "Sprache": "Language", "erkannt": "detected", "Vorbereiten": "Prepare",

  // Bearbeiten
  "Zurück zum Text · Esc": "Back to text · Esc", "Ungespeicherte Änderungen": "Unsaved changes",
  "Kapitel markierst du mit „# Überschrift“, Absätze mit einer Leerzeile. Dein Lesezeichen bleibt an der gleichen Stelle, und schon erzeugtes Audio von unveränderten Abschnitten wird weiterverwendet.":
    "Mark chapters with “# Heading” and paragraphs with a blank line. Your bookmark stays in the same place, and audio already generated for unchanged sections is reused.",
  "Änderungen verwerfen?": "Discard changes?", "Deine Änderungen am Text gehen verloren.": "Your changes to the text will be lost.",

  // Einstellungen
  "Darstellung": "Appearance", "Wiedergabe": "Playback", "Stimmen": "Voices", "Speicher": "Storage", "App": "App", "Vorleser": "Vorleser",
  "Modus": "Mode", "Hell": "Light", "Dunkel": "Dark", "System": "System", "Akzentfarbe": "Accent color",
  "Jede Farbe hat eine helle und eine dunkle Variante, die je nach Modus automatisch greift – immer gut lesbar. Eine eigene Farbe wird bei Bedarf genauso angepasst.":
    "Each color has a light and a dark variant that switches automatically with the mode – always easy to read. A custom color is adjusted the same way if needed.",
  "Eigene Farbe wählen": "Choose custom color", "Pflaume": "Plum", "Karmin": "Carmine", "Orange": "Orange", "Rost": "Rust", "Petrol": "Petrol",
  "Markierung beim Vorlesen": "Highlighting while reading", "Abschnitt": "Section", "Satz": "Sentence", "Wort": "Word",
  "Der ganze Abschnitt (2–3 Sätze) wird hinterlegt.": "The whole section (2–3 sentences) is highlighted.",
  "Der gerade gesprochene Satz wird hinterlegt.": "The sentence being spoken is highlighted.",
  "Satz hinterlegt, das gesprochene Wort hervorgehoben. Mit Online-Stimmen exakt, bei Offline- und eigener Stimme aus dem Audio bestimmt.":
    "Sentence highlighted, spoken word emphasized. Exact with online voices; with offline voices and your own voice it is determined from the audio.",
  "Vorschau": "Preview", "Der alte Wärter stieg die Treppe hinauf.": "The old keeper climbed the stairs.", "Es war kalt, so": "It was cold, as",
  "kalt": "cold", "wie nie zuvor.": "as never before.", "Unten schlugen die Wellen an den Fels.": "Below, the waves crashed against the rock.",
  "Sprache der Oberfläche": "Interface language",
  "Stimmen-Bibliothek": "Voice library",
  "Markiere Stimmen mit ★ – deine Favoriten erscheinen beim Vorlesen im Stimmen-Menü.": "Mark voices with ★ – your favorites appear in the voice menu while listening.",
  "Eigene Stimme anlegen": "Create your voice", "Alle": "All", "Eigene": "Own", "Stimme suchen": "Search voices",
  "Keine Stimme gefunden.": "No voice found.", "Standard": "Default", "Als Standard": "Set as default", "Favorit": "Favorite", "Zu Favoriten": "Add to favorites",
  "Erzeugtes Audio": "Generated audio", "Grenze": "Limit", "Jetzt leeren": "Clear now",
  "Älteste Dateien werden automatisch gelöscht, sobald die Grenze erreicht ist. Gelöschtes Audio wird beim nächsten Abspielen neu erzeugt.":
    "The oldest files are deleted automatically once the limit is reached. Deleted audio is regenerated the next time you play it.",
  "Lokale Modelle": "Local models", "Diktat (Whisper small)": "Dictation (Whisper small)", "Eigene Stimme (Chatterbox)": "Your voice (Chatterbox)",
  "Offline-Ersatz (Piper)": "Offline backup (Piper)", "springt ein, wenn offline": "steps in when offline", "keine": "none",
  "App": "App", "Gestartet wird der Vorleser per Doppelklick auf": "Start Vorleser by double-clicking",
  "im Vorleser-Ordner (gern ins Dock ziehen). Er läuft dann unsichtbar im Hintergrund, auch wenn du dieses Fenster schließt.":
    "in the Vorleser folder (feel free to drag it to the Dock). It then runs invisibly in the background, even if you close this window.",
  "Vorleser beenden": "Quit Vorleser", "Vorleser beenden?": "Quit Vorleser?",
  "Wiedergabe und laufende Exporte werden gestoppt. Zum Starten wieder Vorleser.app doppelklicken.": "Playback and running exports will stop. Double-click Vorleser.app to start again.",
  "Speicher leeren?": "Clear storage?",
  "Erzeugtes Audio wird gelöscht und beim nächsten Abspielen neu erzeugt. Mit eigener Stimme kann das dauern.": "Generated audio is deleted and regenerated the next time you play. With your own voice this can take a while.",
  "Der Text wird mit Lesezeichen und Hörbuch-Export endgültig entfernt. Das lässt sich nicht rückgängig machen.": "The text is permanently removed along with its bookmark and audiobook export. This can't be undone.",
  "Die Sprachprobe wird entfernt. Texte, die diese Stimme nutzen, lesen danach mit der Standardstimme.": "The voice sample is removed. Texts using this voice will read with the default voice afterwards.",
  "Vorleser beendet": "Vorleser has quit", "Dieses Fenster kannst du schließen.": "You can close this window.",
  "Zum Starten Vorleser.app doppelklicken.": "Double-click Vorleser.app to start.",

  // Export
  "Als Hörbuch exportieren": "Export as audiobook", "Hörbuch-Apps & Apple Books, mit Kapiteln": "Audiobook apps & Apple Books, with chapters",
  "Läuft überall, Kapitel je nach Player": "Plays everywhere, chapters depend on the player",
  "Unkomprimiert, beste Qualität – sehr große Datei, ohne Kapitel": "Uncompressed, best quality – very large file, no chapters",
  "Hörbuch erstellen": "Create audiobook", "Empfohlen": "Recommended", "Hörbuch-Apps & Apple Books · mit Kapiteln": "Audiobook apps & Apple Books · with chapters",
  "Läuft überall · Kapitel je nach Player": "Plays everywhere · chapters depend on the player", "Unkomprimiert · beste Qualität, ohne Kapitel": "Uncompressed · best quality, no chapters",
  "Export abbrechen": "Cancel export", "Im Hintergrund weiter": "Continue in background", "Anderes Format …": "Other format …", "Fertig": "Done",
  "Kapitelmarken werden gesetzt": "Adding chapter marks", "Format": "Format",
  "Du kannst den Dialog schließen – der Export läuft im Hintergrund weiter. Die Bibliothek zeigt den Fortschritt, und wir melden uns, wenn er fertig ist.":
    "You can close this dialog – the export keeps running in the background. The library shows the progress, and we’ll let you know when it’s done.",
  "Export starten": "Start export", "Neu exportieren": "Export again", "Herunterladen": "Download", "Wird vertont …": "Generating audio …",
  "Datei wird erstellt …": "Creating file …", "Abgebrochen": "Cancelled",

  // Eigene Stimme anlegen
  "Lies den Text 15–30 Sekunden ruhig und deutlich vor (leiser Raum, normaler Abstand). Danach kann jeder Text mit deiner Stimme vorgelesen werden – lokal und kostenlos, aber deutlich langsamer als die Online-Stimmen.":
    "Read the text calmly and clearly for 15–30 seconds (quiet room, normal distance). Afterwards any text can be read in your voice – locally and free, but much slower than the online voices.",
  "Name": "Name", "Datei …": "File …", "Aufnehmen": "Record", "Weiterlesen …": "Keep reading …", "Reicht – stoppen, wenn du magst": "That's enough – stop whenever you like",
  "Stimme wird angelegt …": "Creating voice …", "Meine Stimme": "My voice",

  // Erster Start & Tutorial
  "Willkommen": "Welcome", "Kurz einrichten": "Quick setup", "Das kannst du später jederzeit in den Einstellungen ändern.": "You can change this anytime in Settings.",
  "Erscheinungsbild": "Appearance", "Weiter": "Next", "Überspringen": "Skip", "Los geht's": "Let's go", "Tutorial ansehen": "View tutorial",
  "Text hinzufügen": "Add a text",
  "Über „Neuer Text“ fügst du Text ein, ziehst eine Datei hinein (EPUB, PDF, TXT …) oder diktierst einfach. Kapitel und Sprache erkennt der Vorleser selbst.":
    "With “New text” you paste text, drop in a file (EPUB, PDF, TXT …) or simply dictate. Vorleser detects chapters and language by itself.",
  "Anhören": "Listen",
  "Play startet, die Leertaste pausiert. Ein Klick auf einen Satz springt dorthin – dein Lesezeichen merkt sich der Vorleser automatisch.":
    "Play starts, the space bar pauses. Clicking a sentence jumps there – Vorleser remembers your bookmark automatically.",
  "Bearbeiten": "Edit",
  "Über „…“ › Text bearbeiten oder die Taste E änderst du einen fertigen Text. Dein Lesezeichen bleibt, wo es war.":
    "Use “…” › Edit text or the E key to change a finished text. Your bookmark stays where it was.",
  "Deine eigene Stimme": "Your own voice",
  "Unter Einstellungen › Stimmen nimmst du 15–30 Sekunden auf – danach liest der Vorleser mit deiner Stimme. Sie braucht länger, darum am besten „Vorab erzeugen“.":
    "In Settings › Voices you record 15–30 seconds – afterwards Vorleser reads in your voice. It takes longer, so best use “Prepare in advance”.",
  "Mit „Exportieren“ speicherst du den ganzen Text als M4B mit Kapiteln, als MP3 oder als WAV – für Handy, Auto oder Hörbuch-App.":
    "“Export” saves the whole text as M4B with chapters, as MP3 or as WAV – for your phone, car or audiobook app.",
  "Noch ein paar Tipps": "A few more tips",
  "Markiere Lieblingsstimmen mit ★, dann hast du sie beim Hören griffbereit. Ohne Internet springt automatisch eine Offline-Stimme ein. Dieses Tutorial findest du jederzeit in den Einstellungen.":
    "Mark favorite voices with ★ to have them at hand while listening. Without internet, an offline voice steps in automatically. You'll find this tutorial anytime in Settings.",

  // Rundgang
  "Rundgang": "Tour", "Beispieltext": "Sample text", "Rundgang starten": "Start tour", "Rundgang beenden": "End tour", "Rundgang beenden · Esc": "End tour · Esc",
  "Neuen Text anlegen": "Create a new text", "Hier fängt alles an: Text einfügen, eine Datei hineinziehen oder diktieren.": "Everything starts here: paste text, drop in a file or dictate.",
  "Drei Wege zum Text": "Three ways to add text",
  "Einfügen, Datei (EPUB, PDF, TXT …) oder Diktieren. Kapitel und Sprache erkennt der Vorleser selbst.": "Paste, file (EPUB, PDF, TXT …) or dictate. Vorleser detects chapters and language by itself.",
  "Deine Bibliothek": "Your library",
  "Alle Texte mit Fortschritt und wann du sie zuletzt gehört hast. Über die drei Punkte bearbeitest, exportierst oder löschst du einen Text.":
    "All your texts with progress and when you last listened. Use the three dots to edit, export or delete a text.",
  "Mitlesen": "Read along",
  "Der gesprochene Satz wird markiert, das aktuelle Wort leuchtet mit. Ein Klick auf einen Satz springt dorthin.": "The spoken sentence is highlighted and the current word lights up. Click a sentence to jump there.",
  "Play startet, die Leertaste pausiert, ← und → springen zwischen Abschnitten. Dein Lesezeichen wird automatisch gemerkt.":
    "Play starts, the space bar pauses, ← and → jump between sections. Your bookmark is saved automatically.",
  "Wähle aus deinen Favoriten und eigenen Stimmen – jederzeit, auch mitten im Text.": "Pick from your favorites and your own voices – anytime, even mid-text.",
  "Kapitel": "Chapters", "Springe direkt zu einem Kapitel. Die kleinen Striche auf dem Fortschrittsbalken zeigen, wo sie beginnen.": "Jump straight to a chapter. The small marks on the progress bar show where they start.",
  "Bearbeiten & mehr": "Edit & more",
  "Unter „…“ bearbeitest du den Text (Taste E) oder lässt alles vorab erzeugen. Dein Lesezeichen bleibt beim Bearbeiten erhalten.":
    "Under “…” you edit the text (E key) or prepare everything in advance. Your bookmark is kept when editing.",
  "Speichert den ganzen Text als M4B mit Kapiteln, als MP3 oder als WAV – für Handy, Auto oder Hörbuch-App.": "Saves the whole text as M4B with chapters, as MP3 or as WAV – for your phone, car or audiobook app.",
  "Nimm 15–30 Sekunden auf – danach liest der Vorleser mit deiner Stimme. Mit ★ machst du Stimmen zu Favoriten.": "Record 15–30 seconds – afterwards Vorleser reads in your voice. Use ★ to make voices favorites.",
  "Ganz nach deinem Geschmack": "Make it yours",
  "Hell oder Dunkel, Akzentfarbe, Sprache und wie genau mitgelesen wird – alles hier in den Einstellungen.": "Light or dark, accent color, language and how precisely to follow along – all here in Settings.",
  "Für diesen Text fertig erzeugt": "Fully generated for this text", "Für diesen Text noch nicht erzeugt": "Not generated for this text yet",
  "Im Voraus erzeugen": "Generate ahead", "Knapp": "Minimal", "Normal": "Normal", "Viel": "More", "Ganzer Text": "Whole text",
  "Nur der nächste Abschnitt. Spart Rechenzeit – bei der eigenen Stimme kann es zwischen Abschnitten kurz stocken.": "Only the next section. Saves processing time – with your own voice there may be short pauses between sections.",
  "Die nächsten 3 Abschnitte (etwa eine Minute). Reicht für Online-Stimmen fast immer.": "The next 3 sections (about a minute). Almost always enough for online voices.",
  "Die nächsten 10 Abschnitte (einige Minuten). Gut für die eigene Stimme – weniger Pausen.": "The next 10 sections (a few minutes). Good for your own voice – fewer pauses.",
  "Beim Abspielen wird der ganze Text im Hintergrund erzeugt – wie „Vorab erzeugen“, nur automatisch.": "While playing, the whole text is generated in the background – like “Prepare in advance”, just automatic.",
  "von": "by", "Was ist neu": "What's new", "Was in welcher Version dazugekommen ist": "What each version added", "Anzeigen": "Show",
  "Noch in Entwicklung – Fehler gern melden": "Still in development – please report bugs",
  "Der Vorleser ist noch in der Beta: Er läuft im Alltag, aber hier und da kann noch etwas haken.": "Vorleser is still in beta: it works for everyday use, but things may still go wrong here and there.",
  "Alle Versionen, neueste zuerst": "All versions, newest first", "alle Versionen, neueste zuerst": "all versions, newest first", "Gebaut von": "Built by", "Deine Meldung geht direkt an Simon, der den Vorleser entwickelt. Was ist passiert, und was hast du davor gemacht? Je genauer, desto schneller lässt es sich beheben.": "Your report goes straight to Simon, who develops Vorleser. What happened, and what did you do right before? The more precise, the faster it can be fixed.",
  "Sie ist bei Simon angekommen. Bei Rückfragen meldet er sich per E-Mail.": "Simon has received it. He'll reply by e-mail if he has questions.",
  "Sie ist bei Simon angekommen.": "Simon has received it.",
  "Fertig!": "All set!", "Das war's. Den Rundgang findest du jederzeit unter Einstellungen › App.": "That's it. You can find the tour anytime under Settings › App.",

  // Server-Meldungen
  "Kein Text": "No text", "Der Text ist leer": "The text is empty", "Kein vorlesbarer Text gefunden": "No readable text found",
  "Im EPUB wurde kein Text gefunden": "No text found in the EPUB", "Datei zu groß (max. 300 MB)": "File too large (max. 300 MB)",
  "Das PDF enthält keinen Text (vermutlich eingescannt – dafür wäre OCR nötig)": "The PDF contains no text (probably scanned – that would need OCR)",
  "Aufnahme ist zu kurz oder leer": "Recording is too short or empty",
};

const DUR = (s) => s.replace(/(\d+) Std\./g, "$1 h").replace(/(\d+) Min\./g, "$1 min");
const plural = (n, one, many) => `${n} ${+n === 1 ? one : many}`;
const I18N_PATTERNS = [
  [/^Für diesen Text (\d+) % erzeugt$/, (m, n) => `${n}% generated for this text`],
  [/^Auf Version ([\d.]+) aktualisiert$/, (m, v) => `Updated to version ${v}`],
  [/^Du hast Version ([\d.]+)$/, (m, v) => `You have version ${v}`],
  [/^Abschn\. (\d+)$/, (m, n) => `Sect. ${n}`],
  [/^von (\d+)$/, (m, n) => `of ${n}`],
  [/^(\d+) Abschnitte? vorbereitet$/, (m, n) => `${plural(n, "section", "sections")} ready`],
  [/^(\d+) von (\d+) Abschnitten$/, (m, a, b) => `${a} of ${b} sections`],
  [/^(\d+) Abschnitte?$/, (m, n) => plural(n, "section", "sections")],
  [/^(\d+) Kapitel$/, (m, n) => plural(n, "chapter", "chapters")],
  [/^Kapitel (\d+)$/, (m, n) => `Chapter ${n}`],
  [/^(\d+) Stimmen?$/, (m, n) => plural(n, "voice", "voices")],
  [/^([\d.,]+) Zeichen$/, (m, n) => `${n.replace(/\./g, ",")} characters`],
  // Installation der eigenen Stimme: „1.404 MB von ca. 3.060 MB · 5,3 MB/s“
  [/^([\d.]+) MB von (ca\. )?([\d.]+) MB(?: · ([\d,]+) MB\/s)?$/, (m, a, ca, b, sp) =>
    `${a.replace(/\./g, ",")} MB of ${ca ? "approx. " : ""}${b.replace(/\./g, ",")} MB${sp ? ` · ${sp.replace(",", ".")} MB/s` : ""}`],
  [/^([\d.]+) MB geladen$/, (m, a) => `${a.replace(/\./g, ",")} MB downloaded`],
  [/^noch ca\. (\d+) Min\.$/, (m, n) => `about ${n} min left`],
  [/^Version ([\d.]+) ist verfügbar$/, (m, v) => `Version ${v} is available`],
  [/^Version ([\d.]+) startet beim nächsten Öffnen von Vorleser – oder gleich jetzt\.$/, (m, v) => `Version ${v} starts the next time you open Vorleser – or right now.`],
  [/^(.*) Wird im Hintergrund geladen, du kannst weiter vorlesen\.$/s, (m, t) => `${t} Downloads in the background, you can keep listening.`],
  [/^Deine Texte und Lesezeichen \((\d+)\)$/, (m, n) => `Your texts and bookmarks (${n})`],
  [/^Eigene Stimmen \((\d+)\)$/, (m, n) => `Own voices (${n})`],
  [/^(\d+) Abschnitte? vertont$/, (m, n) => `${plural(n, "section", "sections")} voiced`],
  [/^Alle (\d+) Texte anzeigen$/, (m, n) => `Show all ${n} texts`],
  [/^([\d,]+ (?:KB|MB|GB)) freigegeben$/, (m, s) => `${s.replace(",", ".")} freed`],
  [/^noch ca\. (\d+) Std\. (\d+) Min\.$/, (m, h, n) => `about ${h} h ${n} min left`],
  [/^ca\. (.+) Hördauer$/, (m, d) => `approx. ${DUR(d)} listening time`],
  [/^zuletzt gehört (.+)$/, (m, d) => `last played ${d}`],
  [/^Zuletzt gehört: (.+)$/, (m, d) => `Last played: ${d}`],
  [/^Erstellt: (.+)$/, (m, d) => `Created: ${d}`],
  [/^(\d+) (Std\.|Min\.)( (\d+) Min\.)?$/, (m) => DUR(m)],
  [/^Erzeuge (\d+)\/(\d+)$/, (m, a, b) => `Generating ${a}/${b}`],
  [/^„(.+)“ ist vollständig vorbereitet$/, (m, n) => `“${n}” is fully prepared`],
  [/^„(.+)“ ist als Hörbuch fertig$/, (m, n) => `“${n}” is ready as an audiobook`],
  [/^Wird exportiert: (\d+) von (\d+)$/, (m, a, b) => `Exporting: ${a} of ${b}`],
  [/^Kapitel (\d+) von (\d+)$/, (m, a, b) => `Chapter ${a} of ${b}`],
  [/^ca\. (\d+ (?:Std\.|Min\.)(?: \d+ Min\.)?)$/, (m, d) => `approx. ${DUR(d)}`],
  [/^≈ ([\d,]+) (KB|MB|GB)$/, (m, n, u) => `≈ ${n.replace(",", ".")} ${u}`],

  [/^Wird vorbereitet: (\d+) von (\d+)$/, (m, a, b) => `Preparing: ${a} of ${b}`],
  [/^(MP3|M4B|WAV) fertig$/, (m, f) => `${f} ready`],
  [/^Fehler: (.+)$/, (m, e) => `Error: ${tr1(e) ?? e}`],
  [/^Fertig · (.+)$/, (m, t) => `Done · ${t}`],
  [/^Hörprobe (.+)$/, (m, n) => `Preview ${n}`],
  [/^(.+) zu Favoriten hinzufügen$/, (m, n) => `Add ${n} to favorites`],
  [/^(.+) aus Favoriten entfernen$/, (m, n) => `Remove ${n} from favorites`],
  [/^Eigene Stimme „(.+)“ löschen\?$/, (m, n) => `Delete your voice “${n}”?`],
  [/^„(.+)“ löschen\?$/, (m, n) => `Delete “${n}”?`],
  [/^(.+) löschen$/, (m, n) => `Delete ${n}`],
  [/^Aktionen für (.+)$/, (m, n) => `Actions for ${n}`],
  [/^Akzentfarbe (.+)$/, (m, n) => `Accent color ${I18N_EN[n] || n}`],
  [/^Eigene Farbe(?: \((#\w+)\))?$/, (m, h) => `Custom color${h ? ` (${h})` : ""}`],
  [/^Lese (.+) …$/, (m, f) => `Reading ${f} …`],
  [/^Import fehlgeschlagen: (.+)$/, (m, e) => `Import failed: ${tr1(e) ?? e}`],
  [/^Diktat fehlgeschlagen: (.+)$/, (m, e) => `Dictation failed: ${tr1(e) ?? e}`],
  [/^Mikrofon nicht verfügbar: (.+)$/, (m, e) => `Microphone not available: ${e}`],
  [/^Noch keine Favoriten für (.+)\. Markiere Stimmen in der Bibliothek mit ★\.$/, (m, l) => `No favorites for ${I18N_EN[l] || l} yet. Mark voices with ★ in the library.`],
  [/^„(.+)“ \(ca\. (.+)\) wird komplett vertont und mit Kapitelmarken zu einer Datei zusammengefügt\. Läuft im Hintergrund weiter\.( Mit eigener Stimme dauert das deutlich länger\.)?$/,
    (m, t, d, slow) => `“${t}” (approx. ${DUR(d)}) is fully narrated and combined into one file with chapter marks. Keeps running in the background.${slow ? " With your own voice this takes considerably longer." : ""}`],
  [/^([\d,]+) (KB|MB|GB) von ([\d,]+) (MB|GB)$/, (m, a, u1, b, u2) => `${a.replace(",", ".")} ${u1} of ${b.replace(",", ".")} ${u2}`],
  [/^(\d),(\d+)×$/, (m, a, b) => `${a}.${b}×`],
  [/^ca\. ([\d,]+) (GB|MB)$/, (m, n, u) => `approx. ${n.replace(",", ".")} ${u}`],
  [/^([\d,]+) GB$/, (m, n) => `${n.replace(",", ".")} GB`],
  [/^Sprachprobe zu kurz \((\d+) s\) – bitte mindestens 10 Sekunden sprechen$/, (m, n) => `Voice sample too short (${n} s) – please speak for at least 10 seconds`],
  [/^Dateityp (.*) wird nicht unterstützt \(EPUB, PDF, TXT, MD, HTML\)$/, (m, x) => `File type ${x} is not supported (EPUB, PDF, TXT, MD, HTML)`],
  [/^Keine Stimme für (.+) verfügbar – siehe README\.md$/, (m, l) => `No voice available for ${I18N_EN[l] || l} – see README.md`],
];

let UI_LANG = "de";
try { UI_LANG = localStorage.getItem("vorleser.ui") || "de"; } catch {}
const LOC = () => (UI_LANG === "en" ? "en-GB" : "de");

function tr1(core) {
  if (Object.prototype.hasOwnProperty.call(I18N_EN, core)) return I18N_EN[core];
  for (const [re, fn] of I18N_PATTERNS) { const m = core.match(re); if (m) return fn(...m); }
  return null;
}
function trCore(core) {
  const one = tr1(core);
  if (one != null) return one;
  if (core.includes(" · ")) {                         // „Weiblich · Deutschland · mehrsprachig“ → Teile einzeln
    let any = false;
    const out = core.split(" · ").map((p) => { const r = tr1(p); if (r != null) { any = true; return r; } return p; });
    return any ? out.join(" · ") : null;
  }
  return null;
}
function trString(s) {
  const m = /^(\s*)([\s\S]*?)(\s*)$/.exec(s);
  if (!m[2]) return null;
  const t = trCore(m[2]);
  return t == null ? null : m[1] + t + m[3];
}

const I18N_ATTRS = ["placeholder", "aria-label", "data-tip", "title"];
const trDone = new WeakMap();       // Knoten → {de, en} bzw. Element → {attr: {de, en}}
const skipped = (el) => !el || !!el.closest?.("[data-noi18n], script, style, textarea");

function trText(node) {
  if (UI_LANG !== "en" || skipped(node.parentElement)) return;
  const v = node.nodeValue, done = trDone.get(node);
  if (done && v === done.en) return;
  const t = trString(v);
  if (t != null && t !== v) { trDone.set(node, { de: v, en: t }); node.nodeValue = t; }
}
function trAttrs(el) {
  if (UI_LANG !== "en" || skipped(el)) return;
  let map = trDone.get(el);
  for (const a of I18N_ATTRS) {
    const v = el.getAttribute(a); if (!v) continue;
    if (map?.[a] && v === map[a].en) continue;
    const t = trString(v);
    if (t != null && t !== v) { map = map || {}; map[a] = { de: v, en: t }; trDone.set(el, map); el.setAttribute(a, t); }
  }
}
function trTree(root) {
  if (root.nodeType === 3) return trText(root);
  if (root.nodeType !== 1 || skipped(root)) return;
  trAttrs(root);
  const w = document.createTreeWalker(root, NodeFilter.SHOW_ELEMENT | NodeFilter.SHOW_TEXT, {
    acceptNode: (n) => (n.nodeType === 1 && n.matches("[data-noi18n], script, style, textarea") ? NodeFilter.FILTER_REJECT : NodeFilter.FILTER_ACCEPT),
  });
  let n; while ((n = w.nextNode())) n.nodeType === 3 ? trText(n) : trAttrs(n);
}
function untrTree(root) {           // zurück auf Deutsch
  const w = document.createTreeWalker(root, NodeFilter.SHOW_ELEMENT | NodeFilter.SHOW_TEXT);
  let n = root;
  do {
    const d = trDone.get(n);
    if (d && n.nodeType === 3 && n.nodeValue === d.en) n.nodeValue = d.de;
    else if (d && n.nodeType === 1) for (const a in d) if (n.getAttribute(a) === d[a].en) n.setAttribute(a, d[a].de);
  } while ((n = w.nextNode()));
}

const i18nObserver = new MutationObserver((recs) => {
  if (UI_LANG !== "en") return;
  for (const r of recs) {
    const el = r.target.nodeType === 1 ? r.target : r.target.parentElement;
    if (skipped(el)) continue;
    if (r.type === "characterData") trText(r.target);
    else if (r.type === "attributes") trAttrs(r.target);
    else r.addedNodes.forEach(trTree);
  }
});

function setUiLang(lang) {
  UI_LANG = lang === "en" ? "en" : "de";
  try { localStorage.setItem("vorleser.ui", UI_LANG); } catch {}
  document.documentElement.lang = UI_LANG;
  if (UI_LANG === "en") trTree(document.body); else untrTree(document.body);
}

document.documentElement.lang = UI_LANG;
if (UI_LANG === "en") trTree(document.body);
i18nObserver.observe(document.body, { subtree: true, childList: true, characterData: true, attributes: true, attributeFilter: I18N_ATTRS });
