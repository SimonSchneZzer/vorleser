# Vorleser

**Macht aus jedem Text ein Hörbuch – kostenlos, ohne Konto, für Mac und Windows.**
*Turns any text into an audiobook – free, no account, for Mac and Windows. (UI in German and English.)*

Ein Projekt von **[Simon Schnetzer](https://github.com/SimonSchneZzer)**.

Text einfügen oder EPUB, PDF, TXT, Markdown oder HTML hineinziehen – der Vorleser liest vor, markiert dabei
Wort für Wort, merkt sich die Stelle und exportiert auf Wunsch als Hörbuch mit Kapiteln.

**➜ [Download & Anleitung](https://simonschnezzer.github.io/vorleser-download/)**

## Was er kann
- **Natürliche Stimmen** (Microsoft Edge, online, Deutsch + Englisch) – offline springt automatisch Piper ein
- **Eigene Stimme:** 15–30 Sekunden vorlesen, dann liest der Vorleser mit deiner Stimme (Chatterbox, lokal, optionaler Download)
- **Mitlesen:** Markierung pro Abschnitt, Satz oder Wort
- **Kapitel** aus EPUB-Inhaltsverzeichnis, PDF-Lesezeichen oder Überschriften
- **Export** als M4B oder MP3 mit Kapitelmarken, oder WAV
- **Diktieren** statt tippen (Whisper, lokal)
- Lesezeichen, Bibliothek, Hell/Dunkel, Akzentfarbe, automatische Updates

## Privatsphäre
Texte, Lesezeichen und eigene Stimmen bleiben auf deinem Rechner
(Mac: `~/Library/Application Support/Vorleser`, Windows: `%APPDATA%\Vorleser`).
Ins Internet gehen nur: der Text des gerade vorgelesenen Abschnitts an Microsofts Vorlese-Dienst (nur bei
Online-Stimmen), die Update-Prüfung bei GitHub, Schriften von Google Fonts, einmalige Modell-Downloads – und eine Fehlermeldung, wenn
du selbst eine abschickst. Kein Tracking, keine Analyse.

> Die Online-Stimmen nutzen über [`edge-tts`](https://github.com/rany2/edge-tts) die Vorlese-Funktion des
> Edge-Browsers. Das ist kein offizielles Produkt von Microsoft und kann sich ändern – dann liest Piper weiter.

## Aus dem Quellcode starten
Voraussetzungen: Python 3.12 und [uv](https://docs.astral.sh/uv/) (ffmpeg kommt über `imageio-ffmpeg` mit).

```bash
uv venv --python 3.12 .venv-build
uv pip install --python .venv-build/bin/python -r requirements.lock
.venv-build/bin/python -m piper.download_voices --download-dir voices de_DE-thorsten-medium en_US-lessac-medium
.venv-build/bin/python desktop.py          # App-Fenster
./start.sh                                 # oder nur der Server → http://127.0.0.1:8765 im Browser
```

Nützliche Variablen: `VORLESER_HOME=/tmp/vh` (eigener Datenordner), `VORLESER_PORT=8790`,
`VORLESER_DEBUG=1` (Entwicklerwerkzeuge im Fenster).

**Tests** (laufen in einem Wegwerf-Datenordner, nie gegen echte Daten; der Browser-Test braucht Chrome):
```bash
.venv-build/bin/python -m pytest -q
```

**App bauen** (lokal auf dem Mac; Windows-Installer entsteht per GitHub Actions):
```bash
.venv-build/bin/pyinstaller --noconfirm packaging/vorleser.spec   # → dist/Vorleser.app
bash packaging/make_dmg.sh                                         # → dist/Vorleser-x.y.z-mac.dmg
```

## Aufbau
Python-Server (nur Standardbibliothek) mit JSON-API, Oberfläche als HTML/CSS/JS ohne Build-Schritt, in einem
nativen Fenster über [pywebview](https://pywebview.flowrl.com). Gepackt mit PyInstaller, Windows-Installer mit
Inno Setup. Überblick über die Dateien: [`CLAUDE.md`](CLAUDE.md). Warum Dinge so sind, wie sie sind:
[`docs/DECISIONS.md`](docs/DECISIONS.md). Änderungen: [`CHANGELOG.md`](CHANGELOG.md).

Oberfläche, Kommentare und Commits sind auf Deutsch; englische Oberflächentexte entstehen zur Laufzeit über
[`static/i18n.js`](static/i18n.js).

## Mitmachen
Fehler und Ideen gern als [Issue](https://github.com/SimonSchneZzer/vorleser/issues) – oder direkt in der
App über *Fehler melden*. Pull Requests sind willkommen; bitte vorher `pytest` laufen lassen.

## Lizenz
Copyright © 2026 Simon Schnetzer

Der Vorleser ist freie Software unter der **GNU General Public License v3.0 oder später** – siehe
[`LICENSE`](LICENSE). Mitgelieferte Komponenten und ihre Lizenzen: [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md).
