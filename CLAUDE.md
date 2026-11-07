# Vorleser – Hinweise für AI-Assistenten

Desktop-App (macOS + Windows), die Texte (EPUB, PDF, TXT, MD, HTML) als Hörbuch vorliest. Python-Server
+ Weboberfläche in einem nativen Fenster (pywebview). Oberfläche, Kommentare und Commits sind **deutsch**.

**Bevor du etwas Größeres änderst: `docs/DECISIONS.md` lesen.** Dort steht, warum Dinge so sind, wie sie
sind (inkl. verworfener Alternativen). **Nach jeder nicht offensichtlichen Entscheidung dort einen Eintrag
ergänzen** (Datum, Kontext, Entscheidung, Folgen) – auch bei Bugfixes, deren Ursache überraschend war.

## Aufbau
| Datei | Rolle |
|---|---|
| `desktop.py` | Einstieg der App: Server im Thread + pywebview-Fenster, `Api` für JS (Export speichern) |
| `server.py` | HTTP-Server (stdlib) + JSON-API, Routen-Tabelle `ROUTES` unten in der Datei |
| `paths.py` | **Einzige Quelle für Pfade.** Entwicklung: alles im Projektordner. App: Daten im Benutzerordner |
| `tts.py` | Stimmen: Edge (online, MP3) → Piper (offline, Opus/WebM) als Ersatz → Klon (Chatterbox) |
| `textproc.py` | Spracherkennung, Satzgrenzen, Abschnitte (`chunk_text`), Kapitel |
| `importers.py` | EPUB/PDF/HTML/TXT → Text |
| `exporter.py` | Export M4B/MP3/WAV mit Kapiteln, „Vorab erzeugen“ |
| `stt.py` | Whisper: Diktat + Wortzeitmarken für Stimmen ohne eigene Marken |
| `clone_setup.py` / `clone_worker.py` | Eigene Stimme nachinstallieren (mitgeliefertes `uv`) / Worker im eigenen venv |
| `updater.py` | Updates: Release im Repo `vorleser-download` erkennen, laden + vorbereiten; Tausch nach „Jetzt neu starten“ oder beim Beenden |
| `storage.py` | Speicher-Aufschlüsselung (Audio pro Text über Cache-Hash), gezieltes Löschen |
| `uninstaller.py` | Deinstallieren aus der App (Helfer nach dem Beenden, optional Daten behalten) |
| `bugreport.py` | „Fehler melden“: technische Infos; Versand vom Formular an Web3Forms (Key, keine Adresse) |
| `settings.py` | `data/settings.json` mit Validierung |
| `static/` | `index.html`, `app.js` (eine Datei, kein Build), `app.css`, `i18n.js` |
| `packaging/` | PyInstaller-Spec, `make_dmg.sh`, Inno-Setup (`vorleser.iss`), Icon |
| `.github/workflows/build.yml` | Tests → Build Mac (.dmg) + Windows (Setup) → bei Tag `v*` Veröffentlichung |

Download-Seite + Releases liegen im **separaten öffentlichen Repo** `SimonSchneZzer/vorleser-download`
(lokal `../vorleser-download`). Dieses Repo ist **öffentlich** (Open Source, GPL-3.0-or-later): keine Schlüssel,
Tokens oder privaten Daten committen. Lizenzhinweise der mitgelieferten Pakete: `THIRD_PARTY_NOTICES.md`
(bei neuen Abhängigkeiten ergänzen; GPL/AGPL-Pakete sind der Grund für die GPL-Lizenz).

## Befehle
```bash
uv venv --python 3.12 .venv-build && uv pip install --python .venv-build/bin/python \
  -r requirements.txt -r requirements-desktop.txt -r requirements-dev.txt
.venv-build/bin/python -m pytest -q                      # alle Tests (~10 s), Browser-Test braucht Chrome
VORLESER_TEST_ONLINE=1 .venv-build/bin/python -m pytest -q -m online   # + Edge-Stimmen übers Netz
.venv-build/bin/python desktop.py                        # App-Fenster aus dem Quellcode
./start.sh                                               # nur Server, Oberfläche im Browser (Port 8765)
.venv-build/bin/pyinstaller --noconfirm packaging/vorleser.spec && bash packaging/make_dmg.sh
```
Zum Ausprobieren ohne echte Daten: `VORLESER_HOME=/tmp/vh VORLESER_PORT=8790 …` (eigener Datenordner/Port).
Weitere Variablen: `VORLESER_DEBUG=1` (DevTools), `VORLESER_VERSION`, `VORLESER_UPDATE_URL` (Updater testen).

## Regeln & Stolperfallen
- **Nichts springt von einem Frame auf den nächsten.** Ein-/Ausblenden, Auf-/Zuklappen, Größen- und Positionswechsel
  bekommen immer eine Bewegung (Höhe gleitet, Inhalt blendet mit, Pfeile drehen sich). Helfer in `app.js`:
  `heightFrom`/`smoothHeight`, `collapseOut`, `slideBar`, `boxIn`, `animateIn`; `<details>` klappt automatisch weich.
  Animationen laufen einmal (keine Endlosschleifen) und respektieren `prefers-reduced-motion`.
- **Pfade nur über `paths.py`.** Nie in `APP_DIR` schreiben (in der App schreibgeschützt).
- **Jeder `subprocess`-Aufruf bekommt `**NO_WINDOW`** (sonst blitzen unter Windows Konsolenfenster auf).
- **Opus/WebM immer über `tts.to_opus()`** (in Datei, nicht `pipe:1`): sonst fehlt die Dauer im Header und
  die Wortmarkierung läuft dem Audio davon.
- **Texte in der Oberfläche sind deutsch**; Englisch entsteht zur Laufzeit über die Zuordnung in
  `static/i18n.js`. Neue Texte, die per JS gesetzt werden → dort eintragen (Test prüft wichtige).
- **Tests nie ins Netz** (außer Marker `online`) und nie in echte Daten: `tests/conftest.py` setzt
  `VORLESER_HOME` auf einen Wegwerf-Ordner, bevor Module importiert werden.
- Die Wort-Markierung ist **eine** Box (`#wbox`, `placeWordBox` in `app.js`) hinter dem Text (z-index −1);
  Hintergründe auf dem aktuellen Abschnitt verdecken sie → dort keine Hover-Hintergründe.
- View Transitions (`withTransition`) rendern `backdrop-filter` nicht → während des Onboardings aus.
- Release-Dateinamen sind fest: `Vorleser-mac.dmg`, `Vorleser-windows-setup.exe` (Webseite + Updater).
- App ist **unsigniert** (Entscheidung); Erstinstallation zeigt eine Warnung, Updates über den Updater nicht.

## Neue Version veröffentlichen
`VERSION` erhöhen, Abschnitt `## X.Y.Z` oben in `CHANGELOG.md` (**auf Englisch**; erste Zeile = Text der Update-Karte
in der App, kurz und für Nutzer; alles erscheint unter „Was ist neu“) → committen → `git tag vX.Y.Z && git push origin main vX.Y.Z`. Der Workflow testet, baut und
veröffentlicht im Download-Repo (braucht Secret `DOWNLOAD_REPO_TOKEN`: Fine-grained Token, nur
`vorleser-download`, „Contents: Read and write“). Danach schreibt er `latest.json` ins Download-Repo; laufende
Apps prüfen diese Datei minütlich und melden das Update nach wenigen Minuten (GitHub-API nur Ausweichweg, max. 1×/h).
