# Änderungen

Neueste Version oben. Der Abschnitt einer Version wird beim Veröffentlichen als Release-Notiz übernommen;
**die erste Zeile erscheint in der Update-Hinweiskarte der App** – kurz und für Nutzer formulieren.

## 2.5.0
Neuer Export: in drei klaren Schritten zum Hörbuch – mit Fortschritt pro Kapitel und Restzeit.

- **Export:** Format wählen (mit Größenschätzung, M4B empfohlen) → Fortschritt pro Kapitel mit Restzeit → fertige Datei mit „Speichern“
- **Im Hintergrund:** „Im Hintergrund weiter“ schließt nur den Dialog; die Bibliothek zeigt den Fortschritt, und ein Hinweis meldet, wenn das Hörbuch fertig ist
- **Animationen:** der Dialog passt seine Größe weich an; beim Fertigwerden zeichnet sich ein Haken und eine Klangwelle springt auf

## 2.4.0
Weichere Übergänge – Texte, Player und Export bewegen sich jetzt sanft statt zu springen.

- **Bibliothek:** neue Texte landen sichtbar oben, gelöschte gleiten hinaus (auch eigene Stimmen)
- **Player:** fährt beim Öffnen eines Texts von unten herein und beim Bearbeiten wieder hinaus
- **Export:** Fortschritt blendet ein; fertig mit Haken, grünem Balken und hereinspringendem Download-Knopf
- **Update:** nach „Aktualisieren“ geht die Karte weich in den Ladebalken über
- **Kleinigkeiten:** Datei-Ablage hebt sich beim Hineinziehen, „erkannt“-Hinweis springt auf, vorbereitete Abschnitte blenden ihre Markierung ein, Seitenleiste im schmalen Fenster gleitet mit Abdunklung

## 2.3.9
Der Vorleser ist jetzt Open Source – freie Software unter GPL-3.0.

- **Open Source:** Quellcode auf GitHub, Link unter *Einstellungen › App › Open Source*
- **Lizenzen:** Lizenztext und Hinweise zu allen mitgelieferten Komponenten liegen der App bei

## 2.3.8
Updates laden im Hintergrund – du entscheidest, wann neu gestartet wird.

- **Updates:** werden direkt nach dem Start zuverlässig erkannt (vorher erschien der Hinweis manchmal erst nach 30 Minuten)
- **Update bereit:** „Jetzt neu starten“ oder „Später“ – dann läuft beim nächsten Öffnen die neue Version
- **Schneller Neustart:** die neue Version wird schon vorher entpackt; der Neustart dauert unter einer Sekunde statt rund zehn
- **Statuszeile:** flackert nicht mehr; neuer Text gleitet kurz herein
- **Seitenleiste:** mehr Abstand zwischen „Neuer Text“ und „Bibliothek“
- **Fortschritt:** die Bibliothek zeigt denselben Stand wie der Player und läuft beim Hören live mit
- **Stimmen:** Sprache, Filter und Suche in einer Zeile

## 2.3.6
Feinschliff: kein weißes Aufblitzen beim Start, eigener Reiter „App“, Speicher lädt sichtbar.

- **Dunkelmodus:** Beim Start blitzt das Fenster nicht mehr weiß auf, auch bei „Darstellung: System“
- **Einstellungen:** „Speicher“ und „App“ sind getrennte Reiter
- **Speicher:** Platzhalter, bis die Größen berechnet sind; beim erneuten Öffnen erscheinen die letzten Werte sofort
- **Alles vorbereitet:** sieht nicht mehr wie ein Knopf aus; Hinweise passend zum Zustand
- **Seitenleiste:** Trennlinie unten auf Höhe der Abspielleiste, „Fehler melden“ ausgeschrieben, Suche erst ab
  7 Texten, der Balken jedes Texts zeigt hell, was schon vorbereitet ist

## 2.3.5
Aufgeräumt: der App-Bereich in den Einstellungen, und die App öffnet sich nicht mehr doppelt.

- **Einstellungen › App:** eine Zeile pro Aktion mit kurzer Erklärung, Version oben rechts, Deinstallieren abgesetzt
- **Kein zweites Fenster mehr:** Wird der Vorleser erneut gestartet (z. B. eine zweite Kopie der App), holt er das
  bestehende Fenster nach vorne, statt ein weiteres zu öffnen

## 2.3.4
Neu: Vorlesen und Vorab-Erzeugen laufen im Hintergrund weiter – der Player bleibt immer sichtbar.

- **Player überall:** Die Wiedergabe läuft weiter, wenn du in die Einstellungen oder zu „Neuer Text“ wechselst;
  die Abspielleiste bleibt unten, ein Klick auf den Titel führt zurück zum Text
- **Im Hintergrund (Mac):** Vorlesen läuft weiter, wenn das Fenster verdeckt oder die App nicht im Vordergrund ist
- **Vorab erzeugen:** läuft im Hintergrund weiter (Fortschrittsring in der Bibliothek, Meldung wenn fertig),
  lässt dem Vorlesen den Vortritt; Abbrechen über ein eigenes ✕ statt versehentlich per Klick auf den Knopf
- **„Vorbereitet“ stimmt überall:** Knopf, Statuszeile, Balken und Markierung im Text zeigen dasselbe
- Eigene Stimme aufnehmen: Die Knöpfe verrutschen nicht mehr
- Beim Beenden mit ⌘Q laufen keine Hintergrundprozesse mehr weiter

- Installation der eigenen Stimme: Der Modell-Download startet sofort (vorher über eine Minute „0 MB“);
  am Anfang steht „wird vorbereitet“ statt „Verbindung langsam“; die Karte springt nicht mehr in der Höhe

## 2.3.3
Feinschliff: ruhigere Animationen beim Rundgang und bei der Installation der eigenen Stimme.

- **Rundgang:** Die Hinweiskarte steht von Anfang an an der richtigen Stelle; Spotlight und Karte gleiten flüssiger
- **Eigene Stimme installieren:** am Ende „Fast fertig – das Stimmmodell wird eingerichtet“ statt scheinbar endlosem
  Download; der Schimmer im Balken springt nicht mehr; die Karte löst sich am Ende auf und der Inhalt rückt weich nach
- **Eigene Stimme:** Nach der Installation öffnet sich direkt die Aufnahme; der Name ist nur ein Vorschlag; die
  Hörprobe der neuen Stimme wird sofort im Hintergrund vorbereitet (Vorlesen hat Vorrang)

## 2.3.2
Behoben: Updates werden auf dem Mac wieder gefunden.

- **Mac:** Die automatische Update-Prüfung schlug seit 2.1.0 fehl. Wer 2.1.0 bis 2.3.1 hat, installiert diese
  Version einmal von Hand von der Download-Seite – danach kommen Updates wieder automatisch.
- Eigene Stimme aufnehmen: Der Vorlesetext ist ganz sichtbar, ohne Scrollen

## 2.3.1
Neu: Vorleser lässt sich direkt aus der App deinstallieren.

- **Deinstallieren:** Einstellungen › Speicher & App – zeigt vorher, was gelöscht wird, und fragt zweimal nach.
  Auf Wunsch bleiben Texte und eigene Stimmen erhalten.
- **Windows:** Beim Entfernen über „Apps“ fragt der Vorleser, ob auch deine Daten gelöscht werden sollen.

## 2.2.0
Neu: Speicher gezielt aufräumen – pro Text, Hörproben, Reste, Exporte und Modelle.

- **Speicher:** Übersicht, wer wie viel Platz belegt; einzelne Teile löschen statt nur „Alles leeren“
- **Text löschen** entfernt jetzt auch sein erzeugtes Audio
- **Rundgang:** Der Beispieltext bleibt danach in der Bibliothek (auch bei Abbruch), ohne Kopien beim erneuten Rundgang
- **Eigene Stimme aufnehmen:** Text in der Sprache der Oberfläche, Umschalter Deutsch | English
- **Installation der eigenen Stimme:** drei wechselnde Szenen beim Stimmmodell (Wellenform › Netz › Sprechblase);
  die Gesamtgröße bleibt fest bei 3.060 MB
- Englische Oberfläche: Zahlen richtig formatiert (1,404 MB statt 1.404 MB)
- Update-Prüfung bei jedem Start schon nach wenigen Sekunden

## 2.1.0
Neu: Fehler direkt aus der App melden und eine übersichtlichere Installation der eigenen Stimme.

- **Fehler melden:** Käfer unten links (oder Einstellungen › Speicher & App) – Beschreibung eingeben, fertig.
- **Eigene Stimme:** ein Knopf „Eigene Stimme verwenden“; die Installation zeigt jetzt Größe, Geschwindigkeit,
  Restzeit und was gerade passiert. Abbrechen funktioniert zuverlässig.
- **Mitlesen:** Die Wortmarkierung bleibt sichtbar, wenn die Maus darüber steht; läuft bei der Offline-Stimme
  nicht mehr davon.
- **Windows:** EPUB-Dateien lassen sich wieder importieren.
- **Updates** werden auch dann gefunden, wenn GitHub gerade viele Anfragen bekommt.

## 2.0.0
Erste Desktop-Version für macOS (Apple-Chip) und Windows 10/11.

- Eigenes App-Fenster statt Browser, Installation per Doppelklick
- Eigene Stimme als optionaler Download direkt aus der App
- Automatische Updates mit einem Klick
