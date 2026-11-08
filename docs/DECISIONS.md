# Entscheidungslog

Warum der Vorleser so gebaut ist, wie er ist. Neueste Einträge oben. Format: **Kontext → Entscheidung →
Folgen** (+ verworfene Alternativen). Bei neuen Entscheidungen einen Eintrag oben ergänzen.

---

## 2026-11-08 · Update laden: Wiederholung + Ausweichweg über die GitHub-API
**Kontext:** Das Update auf 2.10.1 schlug dreimal mit „HTTP Error 504: Gateway Time-out“ fehl (Teil-Update und
komplettes Paket). Ursache war nicht das Release, sondern github.com selbst: die Webseite (auch fremde Repos und
`releases/download/…`) lieferte in der Region `switzerlandnorth` stundenlang 504, die Statusseite meldete
„operational“. `api.github.com` und der Datei-Server (`release-assets.githubusercontent.com`) liefen normal.
Die Karte zeigte den rohen Python-Fehler plus einen nicht übersetzten deutschen Satz, und „Download-Seite“ half nicht
(deren Links zeigen ebenfalls auf github.com).
**Entscheidung:** `_download` versucht es bei 5xx/429/Netzfehlern zweimal neu (2 s, 5 s) und lädt danach dieselbe
Datei über `api.github.com/repos/…/releases/assets/<id>` (`Accept: application/octet-stream`, leitet auf den
Datei-Server um). Die Karte bekommt feste, übersetzbare Meldungen (`MSG_SERVER`/`MSG_OFFLINE`/`MSG_OTHER`), Details
nur im Log. „Später“ bei einem Fehler blendet die Karte nur bis zum nächsten Start aus (keine 24-h-Pause wie beim
normalen Angebot); „Jetzt suchen“ oder ein neuer Versuch zeigen sie wieder.
Die Karte zeigte erst 15 MB (Teil-Update), dann 263 MB (Ausweichen aufs komplette Paket), dann den Fehler. Jetzt:
„Verbindung wird hergestellt …“ (`connected: false`), die MB-Zahl erst nach der Antwort des Servers (Content-Length),
danach fest. Scheitert das Teil-Update an Server-/Netzfehlern, gibt es kein komplettes Paket hinterher (käme vom
selben Server); nur bei abweichenden Dateien/Prüfsummen weiterhin das komplette Paket.
**Folgen:** Die API (60 Anfragen/h pro IP) wird nur im Fehlerfall gefragt. Fällt GitHub komplett aus, hilft nur
noch ein zweiter Download-Ort (verworfen, siehe 2026-11-06: Dateigrößenlimits bei Pages/Cloudflare/Netlify).

## 2026-11-07 · Markierungen nach dem Laden der Lese-Schrift neu anlegen
**Kontext:** Wort- und Satz-Box standen ein paar Pixel neben dem Text (Wort-Box zu hoch). Ursache: Literata kommt
asynchron von Google Fonts (`display=swap`); wechselt die Schrift nach dem Setzen der Boxen, verschieben sich die
Wörter, der Leser bleibt aber gleich hoch (feste Zeilenhöhe 1,75) → der `ResizeObserver` meldet nichts.
**Entscheidung:** `replaceMarks()` legt beide Boxen neu an – beim `ResizeObserver` und bei `document.fonts`
`loadingdone`. Im Browser nachgestellt (Schriftwechsel ohne Größenänderung) und mit dem Fix geprüft.

## 2026-11-07 · Dock-Icon nicht mehr umfärben (ersetzt „Dock-Icon in der Akzentfarbe“)
**Kontext:** Die Oberfläche setzte das Dock-Icon zur Laufzeit in der Akzentfarbe (`Api.set_icon`). Ist die App zu,
zeigt macOS aber das Icon aus dem Paket – das Icon wechselte also beim Schließen die Farbe.
**Entscheidung:** Kein Umfärben mehr; das Dock zeigt immer `packaging/icon.png` (Petrol). `set_icon`/`syncDockIcon` entfernt.
**Verworfen:** Icon dauerhaft ins App-Paket schreiben (`NSWorkspace setIcon:forFile:`) – braucht Schreibrechte in
`/Applications`, fügt dem unsignierten Paket eine Datei hinzu (Teil-Updates prüfen das Paket per Prüfsumme), macOS
cached solche Icons hartnäckig. In der App selbst folgen die Logo-Balken weiter der Akzentfarbe.

## 2026-11-07 · Fußleiste der Seitenleiste folgt der Playbar Bild für Bild
**Kontext:** Gleitet die Mitlesezeile in die Playbar, wächst diese animiert; die Fußleiste (Höhe `--player-h`) lief
jedem Zwischenwert mit eigenem 0,3-s-Übergang hinterher – ihre Grenzlinie hing bis zu 22 px nach.
**Entscheidung:** Der `ResizeObserver` meldet jede Zwischenhöhe ohnehin; solange die Playbar schon sichtbar ist
(Klasse `foot-follow`), hat die Fußleiste keinen eigenen Übergang mehr → 0 px Abweichung (im Browser je Bild gemessen,
direkt nach dem Observer). Nur beim Erscheinen der Playbar (Höhe springt auf einmal) gleitet sie wie bisher.

## 2026-11-07 · Eigene Stimme: „Neu beginnen“ während der Aufnahme
**Kontext:** Ein Versprecher bedeutete bisher: abbrechen, Dialog neu öffnen, neu starten – oder eine schlechte
Aufnahme hochladen (Stoppen lädt sofort hoch).
**Entscheidung:** Während der Aufnahme gleitet links von „Fertig · 0:12“ der Knopf **Neu beginnen** (Pfeil-Icon) herein;
„Datei …“ gleitet dafür hinaus (während einer Aufnahme sinnlos, und alles bleibt in einer Zeile). Klick verwirft die
bisherige Aufnahme, das Mikrofon bleibt offen, die Zeit startet bei 0:00, Text springt nach oben, Hinweis „Von vorne –
lies den Text noch einmal“. Ausgeblendete Knöpfe sind `inert` (nicht per Tab erreichbar).
**Verworfen:** Prüfschritt nach dem Stoppen (Anhören → Behalten/Neu) – ein Klick mehr für den Normalfall.

## 2026-11-07 · Export: Dialog schließt nach dem Speichern
**Kontext:** Nach „Sichern unter …“ blieb der Dialog „Fertig“ offen; der Hinweis „Gespeichert“ lag darunter
(modale `<dialog>` liegen in der obersten Ebene, über jedem Toast).
**Entscheidung:** Erfolgreich gespeichert → Dialog zu, dann Toast. Abbruch im Sichern-Dialog oder Fehler → Dialog bleibt.

## 2026-11-07 · Neues Logo: dunkle Kachel, helle Akzent-Balken, statisch
**Kontext:** Bisher Kachel in der Akzentfarbe mit weißen Balken; Willkommen-Logo mit wippenden Balken.
Wunsch des Nutzers: das dunkle Zeichen der Webseite („Mit deiner eigenen Stimme“) überall.
**Entscheidung:** Kachel immer #25292D (Anthrazit der App), Balken mittel/hoch/mittel/kurz, statisch. In der App folgen
die Balken der Akzentfarbe (`--logo-bar` = helle Variante, lesbar auf der Kachel); feste Dateien
(`packaging/icon.png` → .icns/.ico, Webseite `icon.png`/`favicon.png`) nutzen Petrol #5FB7CB, erzeugt von
`packaging/make_icon.py`. Feiner heller Innenrand, weil die Kachel im Dunkelmodus sonst mit der Seitenleiste verschmilzt.

## 2026-11-07 · Lokale API nur mit Schlüssel (Cookie) und eigener Herkunft
**Kontext:** Der Server auf `127.0.0.1:8765` nahm jede Anfrage an. Jede Webseite im Browser kann dorthin
schicken; `body()` liest JSON unabhängig vom Content-Type, ein einfaches `fetch(…, {mode:"no-cors"})` hätte z. B.
`/api/uninstall` oder `/api/quit` auslösen können. DNS-Rebinding hätte sogar Antworten lesbar gemacht.
**Entscheidung:** Zufallsschlüssel pro Start (`server.TOKEN`). `/api/*` verlangt ihn als Cookie `vorleser_<port>`
(von `/` gesetzt, `HttpOnly; SameSite=Strict` → fremde Seiten senden ihn nicht) oder als Header `X-Vorleser-Token`.
Zusätzlich muss `Host` 127.0.0.1/localhost:<port> sein und ein `Origin` (falls vorhanden) die eigene Seite.
Ein zweiter App-Start liest den Schlüssel aus `data/api-token` (0600) für `/api/focus`; erkannt wird ein laufender
Vorleser jetzt am `Server`-Header der Startseite (braucht keinen Schlüssel).
**Warum Cookie statt Header im Frontend:** `<audio src>`, Hörproben und der Export-Download können keine eigenen
Header senden; das Cookie gilt für alle gleichermaßen, `app.js` musste nicht angefasst werden.
**Folgen:** Tests schicken den Header (`conftest.Api`). Port im Cookie-Namen, weil Cookies für alle Ports eines
Hosts gelten (Test- und Dev-Server stören sich sonst).

## 2026-11-07 · Gebaut wird aus `requirements.lock`
**Kontext:** `requirements*.txt` hatten nur `>=`. Zwei Builds derselben Version konnten andere Pakete enthalten
(beim Erzeugen wäre z. B. `pypdf` von 6 auf 7 gesprungen); jede unnötige Änderung vergrößert auch die Teil-Updates.
**Entscheidung:** `uv pip compile … --universal --python-version 3.12 -o requirements.lock` (Mac + Windows in
einer Datei); CI und lokale Umgebung installieren daraus. Die `.txt`-Dateien bleiben die Wünsche;
`tests/test_lockfile.py` prüft, dass das Lockfile sie erfüllt. Startversionen = die zuletzt getesteten.
**Nicht gelockt:** `requirements-clone.txt` / `clone_setup.PACKAGES` – Torch wird je Rechner (CUDA/CPU) gewählt.

## 2026-11-07 · Oberfläche in Teilen: `static/js/*.js` statt einer `app.js`
**Kontext:** `app.js` hatte ~3.000 Zeilen. ES-Module hätten Verhalten geändert: Variablen wie `view`, `navRank`
werden quer durch die Datei neu zugewiesen (Import-Bindungen sind schreibgeschützt), und Tests rufen globale
Funktionen (`openDoc`, `st`, `setWord`) direkt auf.
**Entscheidung:** An den bestehenden Abschnittsgrenzen in zehn **normale** Skripte geteilt, ohne Build. Normale
Skripte teilen sich die globalen Namen; die Dateien in der Reihenfolge von `index.html` hintereinander ergeben
exakt die alte `app.js` (+ je ein `"use strict"`).
**Stolperfalle:** Funktionsdeklarationen werden nur innerhalb ihrer Datei vorgezogen. Code, der **beim Laden**
läuft (Handler verdrahten, `x.onclick = fn`), darf nur Namen aus derselben oder früheren Dateien nutzen – sonst
ReferenceError. Die Browser-Tests schlagen bei JS-Fehlern beim Laden an; `test_alle_js_teile_eingebunden` prüft
die Liste in `index.html`.
**Verworfen:** ES-Module (siehe Kontext), Bundler (widerspricht „kein Build“).

## 2026-11-07 · Test: fremde Texte nur über `esc()` ins HTML
**Kontext:** 40+ Stellen bauen HTML aus Template-Strings; Titel/Kapitel kommen aus importierten Büchern.
Bei der Prüfung war alles korrekt escaped – das soll so bleiben.
**Entscheidung:** `tests/test_html_escape.py` liest jeden HTML-Template-String in `static/js/` (kleiner Tokenizer)
und verlangt für Felder wie `.title`, `.name`, `.text`, `.message` ein `esc()`/`mdBold()`. Geprüfte Ausnahmen mit
Grund in `REVIEWED`. Bedingungen eines `a ? b : c` zählen nicht (geben nichts aus).

## 2026-11-07 · Ein Bewegungsmodell für die Navigation
**Kontext:** Jeder Wechsel (Text A → B, Ansicht, Tab) nutzte dasselbe „einblenden und 10 px hoch“ – der alte Inhalt
verschwand ohne Übergang (harter Schnitt).
**Entscheidung:** Richtung hat Bedeutung. Senkrecht = Seitenleiste (`viewRank`: Neuer Text oben, Texte in ihrer
Reihenfolge, Einstellungen unten – der neue Inhalt kommt aus der Richtung seines Eintrags); waagrecht = Tabs
(Einstellungen, Einfügen/Datei/Diktieren; Strich als Gummiband über `left`/`right`); Tiefe = Unterseite (Bearbeiten
zoomt hinein, Zurück heraus). Der alte Inhalt wird als Abbild (`ghostOf`, gleicher Scroll-Stand) darübergelegt und
gleitet hinaus (`navOut`), der neue kommt herein (`navIn`) – ~0,36 s, 26 px, leichte Unschärfe.
**Verworfen:** Text A → B waagrecht – die Texte stehen untereinander; waagrecht bleibt den Tabs.
Außerdem: Seitenleiste wieder grau hinterlegt wie die Menüs (gleitende Glas-Markierung war „zu viel“).

## 2026-11-07 · Glas-Look (Liquid Glass) für alles, was über Inhalt schwebt
**Kontext:** Simon wollte die Mitlesezeile mit „glossy blur“ und den Look überall, wo er Sinn macht (Entwurf im
Design-Artifact freigegeben).
**Nachtrag (gleicher Tag):** Simon: frei schwebende, runde Flächen wirken zu sehr nach Apple. Player und obere
Leiste liegen deshalb über die ganze Breite am Rand (Linie statt Ecken), Knöpfe 8 px statt Pille (Play bleibt rund),
Menüs/Dialoge 6–12 px. Seitenleiste: eine Glas-Markierung gleitet über die ganze Breite (`glideList`).
**Entscheidung:** Glas = halbtransparente Fläche + `backdrop-filter: blur(26px) saturate(1.7)`, dünner Rand,
Lichtkante oben, weicher Schatten (Variablen `--glass*`, hell/dunkel). Nur für schwebende Teile: Player (jetzt
schwebend, mit Mitlesezeile darin; Inhalt scrollt dahinter, `.scroll` bekommt unten `--player-h` Platz), Pillen oben im
Text, Menüs, Sprechblase, Tooltips, Dialoge (+ unscharfer Hintergrund), Update-Karte. Seitenleiste, Karten und
Lesetext bleiben deckend – dahinter liegt nichts. Hinweis: View Transitions zeigen `backdrop-filter` nicht (kurzer
Moment ohne Unschärfe beim Moduswechsel).

## 2026-11-07 · Teil-Updates: nur geänderte Dateien laden (Prüfsummen statt Diff-Ketten)
**Kontext:** Jedes Update lud die ganze App (~260 MB), obwohl sich meist nur Programm und Oberfläche ändern (~15 MB);
Stimmen (121 MB) und Bibliotheken bleiben gleich.
**Entscheidung:** Der Build schreibt je System eine Dateiliste (Pfad → SHA-256, Größe, ausführbar; Verknüpfungen →
Ziel) und ein Paket mit allen Dateien, die sich gegenüber einer der letzten 5 Versionen geändert haben
(`packaging/make_patch.py`; macOS erst nach `make_dmg.sh`, weil dort signiert wird). `latest.json` nennt das Paket
und die abgedeckten Versionen. Die App prüft beim Einspielen JEDE Datei: geänderte aus dem Paket, alle anderen
müssen per Prüfsumme schon stimmen – sonst lädt sie wie bisher das komplette Installationspaket. macOS: APFS-Klon
der App (`cp -c`, sofort, kein Platz) → Paket drüber → überzählige Dateien weg → Ergebnis ist bitgleich mit der
neuen Version (Signatur bleibt gültig) → Tausch wie bisher beim Neustart. Windows: neue Dateien vorbereiten, nach
dem Beenden per robocopy drüber, Überzähliges löschen (außer `unins*`), Versionsanzeige unter „Apps“ nachziehen.
**Verworfen:** Binäre Diffs (bsdiff) – mehr Code, kaum Gewinn, da sich ganze Dateien ändern; Patch-Ketten über
mehrere Versionen – die Prüfsummen machen sie unnötig. **Folge:** Wirkt erst ab der zweiten Version mit Dateiliste;
ältere Apps (ohne neuen Updater) laden noch einmal komplett.

## 2026-11-07 · Speicher: nach den Platzhaltern bleiben die Karten stehen
**Kontext:** Nach dem Laden spielte jede Karte ihre Einblend-Animation neu (kurz unsichtbar, dann neu hereinschweben).
**Entscheidung:** Karten bleiben; ihre Höhe gleitet von Platzhalter- auf echte Höhe (`heightFrom`), nur die Werte
blenden weich ein.

## 2026-11-07 · Mitlesezeile: von oben, nur ein Satzwechsel; Name → GitHub/LinkedIn; weiches `<details>`
**Kontext:** Die Zeile kam von unten (wie der Player), wirkt über dem Player aber wie „aus dem Text heruntergereicht“
– Simon wollte oben rein, oben raus. Nach dem Ziehen lief der Satzwechsel doppelt: `buildWords` setzte erst Wort 0
(→ Satz 1 der Zeile), danach `highlight` das geschätzte Zielwort (→ zweiter Wechsel).
**Entscheidung:** `slideBar(…, fromTop)`; `buildWords` setzt Wort 0 ohne Abgleich, die Zeile wird am Ende von
`highlight()` einmal abgeglichen; beim Einblenden kein Satzwechsel obendrauf. Name: eine gemeinsame Sprechblase
(`#byPop`, `[data-by]`), positioniert am geklickten Namen, klappt nach oben, wenn unten kein Platz ist.
Alle `<details>` klappen über einen globalen Klick-Handler weich (Regel „nichts springt“ in CLAUDE.md).

## 2026-11-07 · Mitlesezeile über der Playbar; Dock-Icon in der Akzentfarbe
**Kontext:** Wer außerhalb der Textseite zuhört (Einstellungen, Neuer Text), sah nicht, wo der Vorleser gerade ist.
Das App-Icon (eckige Balken, fest Petrol) passte nicht zum Logo in der App (runde Striche, Akzentfarbe).
**Entscheidung:** `#ml` zeigt außerhalb der Textseite den aktuellen Satz – nur Text, Ränder per Maske ausgeblendet,
ein-/ausgeschoben wie der Player (`slideBar`). Alle gleitenden Boxen (Wort im Text, Rahmen beim Ziehen, beides in der
Zeile) laufen über `boxIn`, Wörter/Sätze über `tokenize` – eine Logik statt Kopien. Beim Ziehen zeigt die Zeile den
Zielsatz mit Rahmen; die Abschnitt-Blase der Leiste ist dann aus (würde die Zeile verdecken). „Zum Text“ ist kein Knopf,
sondern Tooltip am Titel; auf der Textseite ist der Titel kein Link. Icon: dasselbe Zeichen wie das Logo; auf dem Mac
zeichnet die Oberfläche es in der Akzentfarbe und setzt es über `Api.set_icon` als Dock-Icon (Windows: festes Icon).

## 2026-11-07 · „vorbereitet“ zählt alle kommenden Abschnitte, Leiste zeigt Lücken; Tab „Wiedergabe“
**Kontext:** Die eigene Stimme wird nicht streng der Reihe nach fertig. Der Text markierte alle fertigen Abschnitte,
die Statuszeile zählte aber nur lückenlos ab dem nächsten → „0 Abschnitte vorbereitet“ neben markiertem Text.
**Entscheidung:** Statuszeile zählt alle fertigen kommenden Abschnitte, Punkt rot = der *nächste* fehlt
(+ „der nächste fehlt noch“). Die Leiste zeigt fertige Stücke hinter einer Lücke als eigene Segmente (`#bufMore`).
„Im Voraus erzeugen“, „Markierung“ und die Vorschau ziehen in einen eigenen Tab „Wiedergabe“ (Darstellung = Aussehen
und Sprache). Später passen dort Standard-Tempo, Sprungweite, Mitscrollen hin.

## 2026-11-07 · Installation: Leiste springt bei 100 % nicht mehr zurück; Sterne ploppen nur beim Klick
**Kontext:** Im letzten Schritt wächst die Größe nicht mehr (alles geladen) → `stalled` → der „sanft weiterlaufen“-Zweig
setzte die Leiste auf max. 97 % zurück, die nächste Messung wieder auf 100 % – Flackern im Sekundentakt. Messung
selbst geprüft (kompletter Download mitgeschnitten): sie zählt richtig. Favoriten-Sterne: `.star.on svg` hatte eine
Animation, die bei jedem Neuzeichnen der Liste (alle 3 s, solange eine Stimme vorbereitet wird) neu lief.
**Entscheidung:** Der Zweig hebt nur an, nie ab; bei `step=finish` kein Schimmer, kein MB/s, „X MB geladen“.
Stern-Animation nur mit Klasse `pop`, die der Klick setzt.

## 2026-11-07 · Einstellung „Im Voraus erzeugen“ + Stand je Stimme im Stimmen-Menü
**Kontext:** Fest 3 Abschnitte voraus; bei der eigenen Stimme zu wenig, bei Online-Stimmen genug. Im Stimmen-Menü
war nicht zu sehen, ob ein Text in einer Stimme schon erzeugt ist.
**Entscheidung:** Einstellung `ahead` (low 1 · normal 3 · high 10 · all = beim Abspielen automatisch „Vorab erzeugen“).
`prefetch()` holt aktuellen + nächsten Abschnitt parallel, den Rest nacheinander; ein Aufruf während eines laufenden
Vorladens wird danach nachgeholt (`prefetchAgain`) – vorher ging er verloren (z. B. Textwechsel während des Vorladens).
`GET /api/docs/{id}/prepared?voices=…` zählt fertige Abschnitte je Stimme; das Menü holt das vor dem Öffnen (max. 300 ms),
damit seine Höhe nicht springt; die aktuelle Stimme nimmt dieselbe Quelle wie die Playbar (`readySet`).

## 2026-11-07 · Fortschrittsleiste: genau landen, ziehen, einrasten, gleiten
**Kontext:** Ein Klick sprang immer an den Anfang des getroffenen Abschnitts – bei wenigen, langen Abschnitten
landete der Knopf weit links vom Klick („unkontrolliertes Snapping“). Ziehen ging nicht.
**Entscheidung:** Ziel = Abschnitt + Anteil darin (`jumpTo(i, 0, autoplay, frac)`; `playFrom(i, {frac})` rechnet den
Anteil nach dem Laden in Sekunden um; pausiert merkt sich `st.pendingFrac` den Anteil). Ziehen ab 3 px (Sprung erst beim
Loslassen), Vorschau-Blase + Geisterstrich beim Hovern, Einrasten nur an Kapitelstrichen (8 px), beim Sprung gleiten
Balken und Knopf (Klasse `glide`, nur kurz – beim Abspielen und Ziehen nicht, sonst hinkt der Knopf hinterher).
Gespeicherter Stand ohne Sekunden (`offset` 0, `frac` > 0) wird beim Öffnen über `pendingFrac` wiederhergestellt.

## 2026-11-07 · Beta-Kennzeichen, Karte „aktualisiert“ und „Was ist neu“
**Kontext:** Nutzer sollen sehen, dass der Vorleser noch nicht fertig ist, und nach einem Update erfahren, was neu ist.
**Entscheidung:** „BETA“-Plakette (Seitenleiste, Einstellungen › App, Webseite) statt anderer Versionsnummern –
GitHub-Releases werden **nicht** als Pre-release markiert (sonst brechen `releases/latest`-Links und der API-Ausweichweg).
`CHANGELOG.md` liegt der App bei; `/api/changelog` liefert sie geparst (`parse_changelog`). Nach einem Update zeigt die
Update-Karte „Auf Version X aktualisiert“ mit „Was ist neu“; offen bleibt sie per `localStorage` (`vorleser.newsPending`)
auch über einen Neustart, bis sie geschlossen wird. Ein Dialog für Karte, Einstellungen und Klick auf BETA.
**Folgen:** Changelog-Einträge sind **englisch** (Simons Wunsch: wichtiger als eine deutsche Fassung) – auch in der
deutschen Oberfläche; Release-Notizen auf GitHub ebenso. Test: oberster Abschnitt = `VERSION`,
jeder Abschnitt hat eine erste Zeile.

## 2026-11-07 · Seitenleiste und Playbar: eine Quelle für „vorbereitet“
**Kontext:** Nach dem Löschen von Audio zeigte die Seitenleiste weiter den alten Balken, die Speicherliste kurz
wieder den gelöschten Eintrag. Ursachen: Bibliothek wurde nur bei `refreshLibrary()` aktualisiert; `fillStorage`
zeichnete vor dem Neuladen die zwischengespeicherten alten Werte; `clearCache()` vergaß `st.srvCached` nicht.
**Entscheidung:** `markReady()` schreibt den Stand des offenen Texts in die Bibliothek (`syncLibPrepared`);
laufende Aufträge lösen `refreshLibrary()` aus, wenn sich ihr Fortschritt ändert; Löschen übernimmt den neuen
Stand aus der DELETE-Antwort; `clearCache()` leert auch `srvCached`.

## 2026-11-07 · Windows-Versionsinfo als Text in der Spec
**Kontext:** Copyright/Firma sollen in den Dateieigenschaften der .exe stehen. `PyInstaller.utils.win32.versioninfo`
lässt sich nur unter Windows importieren (pefile/pywin32).
**Entscheidung:** Die Spec schreibt die Versionsinfo als Text (Format von `pyi-grab_version`) nach `build/` und
übergibt den Pfad an `EXE(version=…)` – kein Import nötig, lokal auf dem Mac prüfbar.

## 2026-11-07 · Stimmklon auf Apple-Chip: T3 auf der CPU, S3Gen auf MPS
**Kontext:** Eigene Stimme brauchte auf einem M4 ~54 s pro Abschnitt (~8 s Audio). Messung: T3 (autoregressive
Token-Schleife, CFG-Batch 2) ~80 %, S3Gen ~18 %, Aufbereitung der Sprachprobe ~5 %, Wasserzeichen <1 %.
**Entscheidung:** Auf MPS läuft nur T3 auf der CPU (Wrapper um `t3.inference`, Ein-/Ausgabe werden umkopiert),
S3Gen bleibt auf MPS → ~22 s pro Abschnitt (≈2,5×). Gleiche Gewichte, fp32 → gleiche Qualität (Hörvergleich +
Whisper-Transkript gleichwertig). Die Sprachprobe wird nur neu aufbereitet, wenn sich Pfad/Änderungszeit/Größe
ändern (`prepare_conditionals` ist deterministisch). CUDA und reine CPU bleiben unverändert.
**Verworfen:** alles auf CPU (S3Gen dort ~100× langsamer, >30 min pro Abschnitt); zwei Worker parallel (T3 nutzt
schon mehrere Kerne, doppelter Speicher ~3 GB).
**Folgen:** Während eine eigene Stimme vorliest, ist die CPU stärker ausgelastet.

## 2026-11-07 · Update-Prüfung minütlich über latest.json
**Kontext:** Updates erschienen erst nach bis zu 6 h. Die GitHub-API erlaubt ohne Anmeldung nur 60 Anfragen/h
pro öffentlicher IP – mehrere Apps im selben Netz teilen sich das.
**Entscheidung:** Der Release-Workflow schreibt nach dem Hochladen der Installer `latest.json` (Version, Notizen,
URL + Größe je Installer) ins Download-Repo; die App liest sie über GitHub Pages minütlich (kein Ratenlimit).
Die API bleibt Ausweichweg, aus der Schleife höchstens stündlich („Jetzt suchen“ darf immer). Oberfläche fragt
den lokalen Server ebenfalls minütlich.
**Folgen:** Pages leert seinen Zwischenspeicher beim Deploy (getestet) → neue Version nach ~1–3 min sichtbar.
Apps ≤ 2.5.0 prüfen weiter alle 6 h über die API.

## 2026-11-07 · Export-Dialog in drei Stufen
**Kontext:** Formatwahl, Fortschritt und Ergebnis standen gleichzeitig im Dialog; zwei orange Knöpfe
(„Herunterladen“/„Neu exportieren“); unklar, ob „Schließen“ abbricht. Entwurf vorher im Design-Artefakt abgestimmt.
**Entscheidung:** Stufen Auswählen → Läuft → Fertig (`xSetView`). Jede Höhenänderung läuft über `xChange`
(Höhe messen → ändern → gleiten), auch Textänderungen während des Exports. Fortschritt in Kapitel geteilt
(ab 30 Kapiteln ein Balken), Restzeit aus `started` des Auftrags. „Im Hintergrund weiter“ statt „Schließen“;
Bibliotheks-Ring zeigt jetzt auch Exporte; beim Fertigwerden Hinweis (außer der Dialog zeigt es gerade).
**Stolperfalle:** Klassennamen kollidieren leicht mit bestehenden (`play` = Play-Knopf, 52 px!) → Export-Klassen
mit Präfix `x…`. `animateIn` beendet nur noch beim eigenen `animationend` (Kinder-Events bubbeln).

## 2026-11-06 · Ein-/Ausgänge animiert (Bibliothek, Player, Export, Update-Karte)
**Kontext:** Elemente sprangen beim Erscheinen/Verschwinden (nur `hidden` umgeschaltet bzw. neu gezeichnet).
**Entscheidung:** Einmalige Bewegungen über Web Animations: `collapseOut` (Zeile gleitet hinaus, Höhe klappt
zu), `heightFrom`/`smoothHeight` (Höhe gleitet bei Inhaltswechsel – Export-Dialog, Update-Karte),
`setPlayer` (Player per negativem `margin-bottom` + `translateY`, damit der Inhalt darüber mitwächst).
Neuer Text „landet“ per CSS-Animation mit **negativer Verzögerung** (`--ago`), weil `renderLibrary` die Liste
oft neu zeichnet (z. B. `jobsPoll` alle 2 s) – so läuft die Animation nach dem Neuzeichnen nahtlos weiter.
Gestaffeltes Einblenden der Bibliothek nur noch, wenn sich mehr als ein Eintrag ändert.
**Stolperfalle:** Klassenname `pop` ist für Popover vergeben (`position: fixed`) → Einspring-Animationen heißen
`popin`.

## 2026-11-06 · Open Source unter GPL-3.0-or-later
**Kontext:** Actions-Minuten im privaten Repo (macOS zählt 10-fach) waren nach einem Tag mit vielen Pushes
aufgebraucht. Beim Prüfen der Lizenzen: `piper-tts` (≥ 1.3) ist GPL-3.0, `EbookLib` AGPL-3.0 – eine
verteilte Closed-Source-App mit diesen Paketen ist nicht lizenzkonform.
**Entscheidung:** Projekt wird Open Source unter **GPL-3.0-or-later** (kompatibel mit beiden; GPL-3 §13 erlaubt
die Kombination mit AGPL). `LICENSE` + `THIRD_PARTY_NOTICES.md` liegen der App bei, *Einstellungen › App ›
Open Source* verlinkt den Quellcode. Veröffentlicht als **frisches öffentliches Repo mit einem Start-Commit**
(Autor: GitHub-noreply-Adresse) – die alte Historie enthält eine private E-Mail-Adresse und bleibt im privaten
Archiv-Repo. Öffentliche Repos: Actions gratis.
**Folgen:** Web3Forms-Schlüssel ist sichtbar (war er in der App schon; für öffentliche Formulare gedacht – bei
Spam austauschen). `en_US-lessac-medium` hat eine nicht-kommerzielle Lizenz – solange der Vorleser kostenlos ist,
kein Problem; bei einem kommerziellen Angebot ersetzen.
**Verworfen:** Repo einfach öffentlich schalten (private E-Mail in 44 Commits); Historie umschreiben (riskanter,
alte Forks/Caches); weiter privat mit Budget (Lizenzproblem bliebe).

## 2026-11-06 · Hörfortschritt: eine Rechnung für Player und Bibliothek
**Ursache:** Bibliothek rechnete `Abschnitt / (n − 1)` (letzter Abschnitt begonnen = „fertig gehört“), der Player
`(Abschnitt + Anteil) / n`; zudem wurde die Liste erst beim Neuladen aktualisiert.
**Entscheidung:** `docPct()` in `app.js` für beide; der Anteil im Abschnitt wird als `progress.frac` gespeichert,
der aktive Eintrag in der Bibliothek läuft live mit (`libSync`, ohne die Liste neu zu zeichnen). „Fertig gehört“
erst ab 99,5 % (Ende des letzten Abschnitts setzt `frac = 1`).

## 2026-11-06 · Update: erst vorbereiten, Neustart auf Wunsch oder beim Beenden
**Kontext:** Nach einem Neustart kam kein Update-Hinweis: Die Oberfläche fragte `/api/update` ~4 s nach dem Start,
die erste Prüfung war da noch nicht fertig – nächste Abfrage erst nach 30 min. Außerdem schloss sich die App nach
„Aktualisieren“ sofort (Hinweistext nur kurz sichtbar), und der Neustart dauerte ~10 s (DMG prüfen + 450 MB
kopieren *nach* dem Beenden).
**Entscheidung:** `status()` meldet `checked`; die Oberfläche fragt alle 2 s nach, bis die erste Prüfung durch ist.
„Aktualisieren“ lädt nur und bereitet vor (Mac: DMG mit `-noverify` einhängen, App als `Vorleser.app.new` daneben
kopieren) → Zustand `ready`, Karte „Update bereit“ mit „Jetzt neu starten“ / „Später“. Der Helfer tauscht nach
dem Beenden nur noch per `mv` (Neustart < 1 s). Bei „Später“ spielt `desktop._cleanup` → `updater.install_on_exit()`
das Update beim Beenden ohne Neustart ein. Windows: Setup läuft weiterhin still nach dem Beenden (dort ist
Vorbereiten ohne Installieren nicht möglich).
**Folgen:** Bis zum Neustart liegen ~450 MB zusätzlich neben der App; Reste eines abgebrochenen Updates räumt der
nächste Start weg. `-noverify` ist vertretbar, weil die Datei frisch per HTTPS geladen und auf die Größe geprüft ist.

## 2026-11-06 · Statuszeile flackerte
**Ursache:** `setStatus` setzte bei jedem Aufruf (Zeitupdates, Vorab-Erzeugen, Puffern) `innerHTML` neu, und eine
CSS-Einblendung auf dem Textteil lief dadurch jedes Mal erneut.
**Entscheidung:** Nur bei echter Änderung neu zeichnen, Zwischenzustände < 150 ms schlucken, neuer Text gleitet
einmal herein (`.swap`). Test: `test_statuszeile_flackert_nicht`.

## 2026-11-06 · Kein weißes Aufblitzen beim Start
**Ursache:** Fensterfarbe nur bei `theme == "dark"` dunkel (bei „System“ immer hell); Seite ohne Grundfarbe vor
dem CSS; Google-Fonts-Stylesheet blockierte das erste Zeichnen.
**Entscheidung:** `desktop._dark()` fragt bei „System“ macOS (`AppleInterfaceStyle`) bzw. Windows
(`AppsUseLightTheme`); Inline-`<style>` im `<head>` mit Grundfarbe (prefers-color-scheme + gespeichertes Theme);
Schriften nicht blockierend (`media=print` → `all`).

## 2026-11-06 · Zweiter Start: bestehendes Fenster nach vorne
**Kontext:** „Die App geht manchmal ein zweites Mal auf.“ Auf dem Mac waren fünf Kopien mit derselben Bundle-ID
registriert (Papierkorb, alte Browser-Startdatei, Test-Builds); Spotlight/Launchpad starten mitunter eine andere
Kopie – die galt als eigene App und öffnete per „zweites Fenster“-Logik ein weiteres Fenster am selben Server.
**Entscheidung:** Ein zweites Exemplar ruft `POST /api/focus` beim laufenden auf (Fenster wiederherstellen, App
aktivieren) und beendet sich sofort. Nur wenn der Port von etwas anderem belegt ist, nimmt die App einen freien.
Überzählige Kopien beim Entwickler mit `lsregister -u` abgemeldet (nicht gelöscht).

## 2026-11-06 · „Vorbereitet“: eine Wahrheit; Player global; Hintergrund
**Kontext:** Knopf („Alles vorbereitet“, Server-Job), Statuszeile (im Fenster geladene Abschnitte) und heller
Balken (lückenlos geladen ab hier) zeigten Verschiedenes; Klick auf „Erzeuge 3/6“ brach still ab; Player war
Teil der Lese-Ansicht, „Neuer Text“ pausierte.
**Entscheidung:** `GET /prepare` liefert live pro Abschnitt, ob er im Server-Cache liegt (`cached`); die Oberfläche
nutzt `isReady(i)` = im Fenster geladen ODER auf dem Server fertig – für Knopf, Statuszeile, Balken, Unterstreichung.
Knopf: Vorab erzeugen › „Erzeuge n/m“ (deaktiviert) + eigenes ✕ › „Alles vorbereitet ✓“ (deaktiviert).
Vorab-Erzeugen mit niedriger Priorität; `GET /api/jobs` → Ring in der Bibliothek, Meldung bei Fertigstellung.
Player als eigenes Element unter allen Ansichten (außer Bearbeiten). macOS: WKWebView-Verdeckungsdrosselung aus
(`_setWindowOcclusionDetectionEnabled:`), App Nap per `beginActivityWithOptions` verhindert.
**Offen:** Hintergrundwiedergabe auf echtem Mac im verdeckten Fenster ist nicht automatisch testbar – manuell prüfen.

## 2026-11-06 · Aufräumen auch bei ⌘Q
**Kontext:** Nach ⌘Q lief ein Stimmklon-Prozess verwaist weiter; im Log fehlte „Vorleser beendet“.
**Ursache:** Bei ⌘Q fragt macOS `applicationShouldTerminate` (→ pywebview-Ereignis `closing`) und beendet den
Prozess dann direkt – `webview.start` kehrt nie zurück, der Aufräumcode danach lief nicht.
**Entscheidung:** `_cleanup` hängt an `window.events.closing` und `closed` (+ atexit), idempotent. Zusätzlich
überwacht `clone_worker.py` die App-PID (`VORLESER_PARENT_PID`) und beendet sich, wenn sie weg ist.

## 2026-11-06 · Eigene Stimme: Hörprobe sofort, Vorlesen hat Vorrang
**Entscheidung:** Nach dem Anlegen einer Stimme erzeugt `tts.warm_clone_preview` die Hörprobe sofort im
Hintergrund (Oberflächensprache zuerst) – das lädt nebenbei auch das Modell. Der Klon-Worker kennt zwei
Prioritäten: Hintergrund-Aufträge (`low=True`) starten nur, wenn kein Vorlese-Auftrag wartet; ein laufender
Abschnitt wird fertig gerechnet (Abbrechen hieße Modell neu laden, ~1 min – schlechter). Gleiche Abschnitte
werden nicht doppelt erzeugt (`_inflight`): Play während der Hintergrund-Hörprobe wartet auf deren Ergebnis.
Nach der Installation öffnet sich direkt der Aufnahme-Dialog; der Name ist nur Platzhalter.

## 2026-11-06 · HTTPS-Zertifikate in der GitHub-gebauten Mac-App + Selbsttest
**Kontext:** Ab 2.1.0 fand keine Mac-App mehr Updates (`URLError` bei API und Ausweichweg). Lokal gebaute Apps
funktionierten, Edge-Stimmen (aiohttp + certifi) auch.
**Ursache:** Das Python des macOS-Runners (python.org-Build) nutzt nicht die Zertifikate von macOS; `urllib`
hatte in der App keine Stammzertifikate.
**Entscheidung:** In der App `SSL_CERT_FILE` auf das mitgelieferte `certifi` setzen (nur falls nicht gesetzt).
`Vorleser --selftest` prüft HTTPS, ffmpeg, Piper, Version, App-Pfad; der Workflow führt ihn mit der **fertigen**
App aus und veröffentlicht nur, wenn er grün ist.
**Folgen:** Mac-Installationen 2.1.0–2.3.1 können sich nicht selbst aktualisieren → einmal von Hand von der
Download-Seite installieren; danach funktionieren Updates wieder.

## 2026-11-06 · Deinstallieren aus der App
**Entscheidung:** `uninstaller.py` + Dialog (Einstellungen › Speicher & App). Dialog listet, was gelöscht wird
(mit Größen), Option „Texte und eigene Stimmen behalten“ (= Ordner `data/` bleibt), roter Knopf braucht zwei
Klicks (zweiter innerhalb 5 s), Fokus startet auf „Abbrechen“. Danach wie beim Updater ein Helfer nach dem
Beenden: Mac löscht `Vorleser.app`, Datenordner und die WebKit-/Cache-Ordner der Bundle-ID unter `~/Library`
(dann Mitteilung); Windows führt `unins000.exe /VERYSILENT` aus und löscht `%APPDATA%\Vorleser`.
Inno-Setup fragt beim Deinstallieren über „Apps“ (nicht still) jetzt, ob die Daten mit gelöscht werden sollen.
Nur in der installierten App; aus der DMG gestartet → Hinweis statt Löschen.
**Verworfen:** In den Papierkorb verschieben (Finder-Automation braucht eine Berechtigungsabfrage).

## 2026-11-06 · Beispieltext des Rundgangs bleibt in der Bibliothek
**Entscheidung:** Am Ende des Rundgangs (fertig oder abgebrochen – beides `gtEnd`) wird der Beispieltext als
normaler Text mit `sample: true` gespeichert und geöffnet. Beim erneuten Rundgang nutzt `demoDoc()` die ID des
vorhandenen Beispieltexts (kein zusätzlicher Eintrag in der Bibliothek); wurde er gelöscht, entsteht am Ende ein
neuer. Während des Rundgangs bleibt das Dokument im Demo-Modus (kein Audio-Abruf, kein Lesezeichen speichern).
Sprache = Oberflächensprache beim Speichern.
**Update-Prüfung:** läuft schon seit 2.0.0 bei jedem Start; Verzögerung von 8 s auf 2 s verkürzt. Kosten:
eine kleine Anfrage pro Start, gratis; am API-Limit greift der Ausweichweg.

## 2026-11-06 · Speicherverwaltung: gezielt löschen, Audio mit dem Text löschen
**Kontext:** Nur „Cache leeren“ (alles) war möglich; gelöschte Texte ließen ihr Audio bis zur Größengrenze liegen.
**Entscheidung:** Kein zusätzlicher Index – die Zuordnung wird aus dem Cache-Namen sha1(Stimme + Abschnitt)
nachgerechnet (`storage.py`): pro Text × alle bekannten Stimmen. Kategorien: Audio pro Text, Hörproben,
Reste (keinem Text/keiner Hörprobe zugeordnet), Exporte, Modelle (Whisper – nur in der App entfernbar,
da der Entwicklungs-Cache geteilt ist –, eigene Stimme, Piper). Text löschen → sein Audio + Wortmarken mit.
**Folgen:** Identische Sätze in zwei Texten teilen sich eine Cache-Datei; löscht man einen Text, wird sie
beim anderen bei Bedarf neu erzeugt (selten, unkritisch). Hörproben werden nie mit einem Text gelöscht.

## 2026-11-06 · Installation der eigenen Stimme: ehrlicher, lebendiger Fortschritt
**Kontext:** Nutzer sah „20 MB“ minutenlang stehen und hätte abgebrochen, obwohl schon 1,2 GB geladen waren.
**Ursache:** Hugging Face lädt per „Xet“ erst in den Speicher und schreibt am Ende – die Ordnergröße (unser
Messwert) wächst nicht. Beim Entpacken der Pakete wächst ebenfalls nichts.
**Entscheidung:** `HF_HUB_DISABLE_XET=1` (fortlaufend auf Platte → messbar). Zielgrößen: Modell exakt per
Hugging-Face-API (3.060 MB), Pakete als gemessene Schätzung (Mac ≈ 1.070 MB entpackt; Windows CPU/NVIDIA
geschätzt) – wächst mit, falls überschritten. Nur Zuwachs ab Phasenbeginn zählen (Dev-Cache hat schon Daten).
Zwischenschritte aus uv-Ausgabe („Resolved/Prepared/Installed“). Geschwindigkeit über 20 s, Restzeit geglättet.
Oberfläche: Balken = aktuelle Phase (passt zu „X von Y MB“), Schritte 1–2–3 = Gesamt; bei ≥ 4 s Stillstand
Schimmer + sanftes Weiterlaufen (max. 97 %) + erklärender Text; Animation je Phase; wechselnde Hinweise; Uhr.
Texte ohne „…“ (wirkten genervt), Dialoge systemspezifisch (Mac: Grafikchip; Windows: mit/ohne NVIDIA).
Ein Knopf „Eigene Stimme verwenden“: installiert → Aufnahme, sonst → Installation anbieten.
**Nachtrag:** Abbrechen wurde als Fehler gemeldet (Status wurde beim Entfernen zurückgesetzt, bevor der
Installationsthread den Abbruch sah) → eigenes `threading.Event`. Schließen der App bricht eine laufende
Installation ab (vorher lief der Download-Prozess verwaist weiter).

## 2026-11-06 · „Fehler melden“ über Web3Forms
**Kontext:** Nutzer sollen Fehler aus der App melden können, ohne eigenes Mailprogramm und ohne dass die
private Empfängeradresse sichtbar ist. Kostenlos.
**Entscheidung:** Formular in der App (Einstellungen › Speicher & App) schickt an Web3Forms; dort ist nur ein
Access Key hinterlegt (`bugreport.py`), der ausschließlich an die verifizierte Adresse sendet. Optionale
Antwortadresse wird `replyto`. Technische Infos (Version, System, bereinigte Log-Zeilen ohne Seitenabrufe,
Benutzerpfad → `~`) abwählbar und vorher einsehbar. Max. 3 Meldungen/Stunde (lokal), Honeypot `botcheck`.
**Wichtig:** Web3Forms (Gratis-Plan) blockt Server-Anfragen und den CORS-Preflight → Versand **aus der
Oberfläche** als `FormData` (einfache CORS-Anfrage), nicht vom Python-Server und nicht als JSON.
**Datenschutz:** Web3Forms hängt die IP-Adresse des Meldenden an die Mail; im Gratis-Plan nicht abschaltbar →
Hinweis im Formular statt „anonym“ zu versprechen. Aufbewahrung in Web3Forms kurz halten (Advanced Options).
Wiederholte Log-Zeilen (nur Zahlen verschieden) werden zusammengefasst (`bugreport.collapse`).
**Verworfen:** SMTP mit Gmail-App-Passwort (Geheimnis in der App auslesbar); GitHub Issues (Account nötig);
Cloudflare Worker + Mail-API (sauberste Lösung, aber mehr Einrichtung – Umstieg, falls Spam kommt).

## 2026-11-06 · Windows: Temp-Dateien vor dem Weiterreichen schließen
**Kontext:** EPUB-Import schlug unter Windows fehl (`PermissionError`), gefunden vom ersten CI-Testlauf auf Windows.
**Ursache:** `NamedTemporaryFile` blieb offen, während ebooklib die Datei erneut öffnete – macOS erlaubt das,
Windows nicht.
**Entscheidung:** Temp-Dateien, die eine andere Bibliothek/ein anderer Prozess öffnet, immer erst schließen
(`mkstemp` + `os.fdopen`, danach löschen). Regel gilt für neuen Code.

## 2026-11-06 · Download-Seite zweisprachig nach Browsersprache
**Entscheidung:** Deutsch steht im HTML (Grundfassung, Suchmaschinen, ohne JS). Bevorzugt der Browser nicht
Deutsch, ersetzt ein Skript vor dem Sichtbarwerden alle Texte durch Englisch – inkl. der nachgestellten
System-Dialoge („Open Anyway“, „Run anyway“), wie sie auf englischen Systemen aussehen. `?lang=` erzwingt.
**Verworfen:** zwei getrennte Seiten (doppelte Pflege, Links müssten sprachabhängig sein).

## 2026-11-06 · Tests + Doku für AI-Assistenten
**Kontext:** Viele Änderungen an einem Tag, mehrere Regressionen nur durch Zufall gefunden.
**Entscheidung:** pytest-Suite (`tests/`): Unit-Tests, API-Tests gegen echten Server mit Wegwerf-Datenordner,
Browser-Test über Chrome DevTools (ohne Playwright – `aiohttp` ist ohnehin installiert). Läuft in CI vor jedem
Build auf Mac + Windows. Regressionen der unten genannten Bugs haben eigene Tests. `CLAUDE.md` + dieses Log.
**Folgen:** Kein Build/Release bei roten Tests. Netz-Tests nur mit `VORLESER_TEST_ONLINE=1`.

## 2026-11-06 · Updater: Ausweichweg ohne GitHub-API
**Kontext:** Unangemeldete GitHub-API erlaubt 60 Abfragen/Stunde **pro IP** – beim Testen erreicht; im Büro
mit vielen Nutzern hinter einer IP realistisch.
**Entscheidung:** Erst API (liefert Release-Notizen), bei Fehler `github.com/…/releases/latest` per HEAD →
Weiterleitung `/tag/vX.Y.Z` → Version; Dateigröße per HEAD auf die Download-URL.
**Folgen:** Updates funktionieren auch am Ratenlimit (dann ohne Notizen in der Hinweiskarte).

## 2026-11-06 · Updates mit einem Klick (Variante „B“)
**Kontext:** Nutzer sollen von neuen Versionen erfahren und einfach aktualisieren.
**Entscheidung:** Eigener Updater (`updater.py`): prüft beim Start + alle 6 h das neueste Release im Repo
`vorleser-download`, lädt den Installer selbst, startet einen Helfer und beendet die App. Mac: Helfer-Skript
hängt die DMG ein, tauscht `Vorleser.app` aus, startet neu. Windows: PowerShell wartet auf das Ende der App,
führt Inno-Setup mit `/VERYSILENT` aus, startet neu. Ohne Schreibrechte (z. B. aus DMG/App Translocation
gestartet) → Download-Seite öffnen.
**Warum:** Was die App selbst lädt, bekommt kein Quarantäne-/Mark-of-the-Web-Kennzeichen → **keine
Sicherheitswarnung bei Updates** trotz unsignierter App.
**Verworfen:** (A) nur Download-Seite öffnen – jede Aktualisierung mit Gatekeeper/SmartScreen-Warnung.
Sparkle/WinSparkle – setzen Signierung voraus bzw. lohnen nicht.
**Getestet:** Mac Ende-zu-Ende (1.9.0 → 2.0.0 mit lokalem Fake-Release). **Windows noch ungetestet.**

## 2026-11-06 · espeak-ng: Datenpfad ≤ 160 Zeichen
**Kontext:** App stürzte ohne Fehlermeldung ab, sobald Piper geladen wurde – nur bei langem Installationspfad.
**Ursache:** espeak-ng (in Piper) speichert den Datenpfad in einem 160-Zeichen-Puffer; ist er länger, nimmt es
den Pfad vom Build-Server und ruft `exit(1)`.
**Entscheidung:** `tts._espeak_dir()`: bei ≥ 150 Zeichen die Daten (20 MB) einmal an einen kurzen Ort kopieren.

## 2026-11-06 · Erster Start: auf Online-Stimmen warten
**Kontext:** Neue Texte bekamen Piper („Thorsten“) als Stimme. Seit `desktop.py` läuft `server.startup()` im
Hintergrund; die Oberfläche fragte die Stimmen ab, bevor die Edge-Liste geladen war.
**Entscheidung:** Gibt es noch keine gespeicherte Edge-Liste, wartet `_edge_voices()` bis zu 8 s auf die
erste Online-Abfrage. Danach (auch offline) normale Auswahl.

## 2026-11-06 · Opus/WebM mit Dauer (Wortmarkierung lief davon)
**Kontext:** Bei Piper und eigener Stimme raste die Wortmarkierung dem Audio voraus.
**Ursache:** ffmpeg schrieb WebM in `pipe:1` und konnte keine Dauer eintragen (`Duration: N/A`); die Webview
riet eine zu kurze Länge; die geschätzten Wortzeiten (bis Whisper-Marken da sind) wurden gestaucht.
**Entscheidung:** `tts.to_opus()` kodiert in eine Temp-Datei. Alter Cache wird einmalig ohne Neukodierung
umverpackt (`fix_webm_durations`, wichtig für die langsame Klonstimme). Oberfläche schätzt nicht, solange die
Dauer unbekannt ist.

## 2026-11-06 · Wortmarkierung als gleitende Box
**Kontext:** Markierung wirkte wie Überblenden (Hintergrund pro Wort an/aus).
**Entscheidung:** Eine absolut positionierte Box (`#wbox`) hinter dem Text gleitet von Wort zu Wort und passt
Breite/Höhe an (0,24 s). Bei Zeilenwechsel springt sie (diagonales Wischen über den Absatz wirkte unruhig).
`ResizeObserver` hält sie bei Umbrüchen in Position. Gleiches Prinzip auf der Webseite (einmal abgespielt).
**Folgen:** Hintergründe auf dem aktuellen Abschnitt (Hover) liegen über der Box → dort abgeschaltet.

## 2026-11-06 · Onboarding: keine View Transition
**Kontext:** Beim Farbwechsel im Onboarding verschwand die Hintergrund-Unschärfe kurz.
**Ursache:** View-Transitions-Snapshots enthalten kein `backdrop-filter`.
**Entscheidung:** Während das Onboarding offen ist, `withTransition` ohne View Transition; Farben blenden per
CSS-Transition über.

## 2026-11-06 · Download-Seite in eigenem öffentlichem Repo
**Kontext:** Kollegen sollen ohne GitHub-Login laden können; Quellcode soll privat bleiben. Private Repos haben
ohne Bezahlplan keine Pages und keine öffentlichen Release-Downloads.
**Entscheidung:** Öffentliches Repo `SimonSchneZzer/vorleser-download` nur mit Webseite (GitHub Pages) und
Releases. Feste Dateinamen, damit `releases/latest/download/<Datei>` immer stimmt. Workflow im privaten Repo
veröffentlicht dort per Token.
**Verworfen:** Repo öffentlich machen (Code sichtbar); Cloudflare/Netlify (Dateigrößenlimits).

## 2026-11-06 · Unsigniert, private Verteilung
**Entscheidung:** Keine Apple Developer ID (99 $/Jahr) und kein Windows-Zertifikat. Erstinstallation:
Mac „Dennoch öffnen“ bzw. `xattr -cr`, Windows „Trotzdem ausführen“. Mac-App ad-hoc signiert (nötig auf Apple-Chips).
**Neu bewerten,** falls die App öffentlich/breit verteilt werden soll.

## 2026-11-06 · Build über GitHub Actions
**Kontext:** PyInstaller kann nicht cross-kompilieren.
**Entscheidung:** Matrix `macos-latest` (Apple-Chip) + `windows-latest`. Piper-Stimmen werden im Build geladen
(nicht im Git). Windows-Installer mit Inno Setup, ohne Adminrechte nach `%LOCALAPPDATA%\Programs`.
**Folgen:** Kein Intel-Mac-Build (Apple-Chip-only wie zuvor). `macos-14` ist bei GitHub nicht mehr verfügbar.

## 2026-11-06 · Eigene Stimme als optionaler Download
**Kontext:** Chatterbox + PyTorch ≈ 4,5 GB; würde den Installer sprengen; braucht GPU.
**Entscheidung:** App liefert `uv` mit; „Eigene Stimme installieren“ erzeugt im Benutzerordner ein venv
(Python 3.11, `chatterbox-tts==0.1.7`), lädt das Modell in einen eigenen Ordner (sauber entfernbar).
Windows mit NVIDIA: `--torch-backend cu124` (torch 2.6 gibt es dort), sonst CPU. Worker nutzt CUDA/MPS/CPU.
**Folgen:** Windows ohne NVIDIA: funktioniert, aber sehr langsam.

## 2026-11-06 · Desktop-App mit pywebview + PyInstaller
**Kontext:** Bisher Browser-Oberfläche + `Vorleser.app`-Shellskript, nur Mac, Installation per Terminal.
**Entscheidung:** pywebview (macOS WebKit, Windows WebView2) um den bestehenden Server; PyInstaller pro OS.
Daten in `~/Library/Application Support/Vorleser` bzw. `%APPDATA%\Vorleser` (`paths.py`); Entwicklung
unverändert im Projektordner. Läuft schon ein Vorleser auf Port 8765, öffnet ein zweiter Start nur ein Fenster.
Export über nativen „Sichern unter“-Dialog (JS-Bridge statt Webview-Download).
**Verworfen:** Electron/Tauri mit Python-Sidecar – mehr Teile, gleicher Python-Kern; Rewrite – unnötig.

## Vor 2026-11-06 · Grundarchitektur (aus README rekonstruiert)
- **Stimmen:** Edge-TTS (gratis, ohne Konto, sehr natürlich, inoffiziell) mit **Piper als automatischem
  Offline-Ersatz** (60 s Sperre nach Edge-Fehler). Piper ist nicht direkt auswählbar.
- **Klon:** Chatterbox Multilingual (MIT) in eigenem venv/Prozess (Abhängigkeitskonflikte, GPU-Speicher
  wird nach jedem Abschnitt freigegeben, Neustart bei OOM).
- **Wortmarken:** Edge liefert sie; für Piper/Klon bestimmt Whisper sie aus dem Audio, bis dahin Schätzung.
- **Server:** Python-Standardbibliothek (`http.server`), keine Web-Frameworks; Oberfläche ohne Build-Schritt.
