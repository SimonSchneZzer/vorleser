# Mitgelieferte Komponenten und ihre Lizenzen

Der Vorleser selbst (Copyright © 2026 Simon Schnetzer) steht unter der **GNU General Public License v3.0 oder später** (siehe `LICENSE`).
Quellcode: https://github.com/SimonSchneZzer/vorleser

Die App enthält bzw. lädt folgende freie Software. Die vollständigen Lizenztexte liegen den jeweiligen
Paketen bei (in der App unter `_internal/<paket>.dist-info/`) und sind auf den genannten Projektseiten abrufbar.

## In der App enthalten
| Komponente | Lizenz | Projekt |
|---|---|---|
| Piper (Sprachausgabe offline), inkl. espeak-ng | GPL-3.0-or-later | https://github.com/OHF-Voice/piper1-gpl |
| EbookLib (EPUB-Import) | AGPL-3.0-or-later | https://github.com/aerkalov/ebooklib |
| edge-tts (Online-Stimmen) | LGPL-3.0 | https://github.com/rany2/edge-tts |
| faster-whisper (Diktat, Wortmarken) | MIT | https://github.com/SYSTRAN/faster-whisper |
| CTranslate2 | MIT | https://github.com/OpenNMT/CTranslate2 |
| ONNX Runtime | MIT | https://github.com/microsoft/onnxruntime |
| PyAV | BSD-3-Clause | https://github.com/PyAV-Org/PyAV |
| FFmpeg (über imageio-ffmpeg) | GPL/LGPL (je nach Build) | https://ffmpeg.org · https://github.com/imageio/imageio-ffmpeg |
| pywebview (App-Fenster) | BSD-3-Clause | https://github.com/r0x0r/pywebview |
| PyObjC inkl. Vision/Quartz (macOS: Fenster, Menüleiste, Texterkennung) | MIT | https://github.com/ronaldoussoren/pyobjc |
| pypdfium2 / PDFium (Windows: Scan-Seiten rendern für die Texterkennung) | Apache-2.0 bzw. BSD-3-Clause | https://github.com/pypdfium2-team/pypdfium2 |
| PyWinRT (Windows: Texterkennung über Windows.Media.Ocr) | MIT | https://github.com/pywinrt/pywinrt |
| pypdf (PDF-Import) | BSD-3-Clause | https://github.com/py-pdf/pypdf |
| Beautiful Soup, soupsieve | MIT | https://www.crummy.com/software/BeautifulSoup/ |
| lxml | BSD-3-Clause | https://lxml.de |
| NumPy | BSD-3-Clause | https://numpy.org |
| aiohttp | Apache-2.0 | https://github.com/aio-libs/aiohttp |
| Hugging Face Hub, tokenizers | Apache-2.0 | https://github.com/huggingface |
| certifi | MPL-2.0 | https://github.com/certifi/python-certifi |
| tqdm | MPL-2.0 / MIT | https://github.com/tqdm/tqdm |
| uv (Installation der eigenen Stimme) | MIT / Apache-2.0 | https://github.com/astral-sh/uv |
| Python | PSF-2.0 | https://www.python.org |
| PyInstaller (Bootloader) | GPL-2.0 mit Ausnahme für gebaute Apps | https://pyinstaller.org |

## Schriften
In `static/fonts/` (dieselben Dateien, die vorher von Google Fonts geladen wurden), beide unter der
**SIL Open Font License 1.1**: **Inter** (Rasmus Andersson, https://github.com/rsms/inter) und **Literata**
(TypeTogether für Google, https://github.com/googlefonts/literata).

## Klänge (Atmosphäre)
Die Klang-Schleifen in `static/klang/` sind gekürzt, lautstärke-angeglichen und nahtlos geschnitten. Die Originale stehen unter
**CC0 1.0 (gemeinfrei)**, Quelle BigSoundBank (Joseph Sardin, https://bigsoundbank.com). Eine Nennung ist freiwillig.

| Datei | Original |
|---|---|
| `regen.m4a` | Summer Rain on Terrace (#1019) |
| `kamin.m4a` | Fireplace #4 (#2856) |
| `cafe.m4a` | Coffee Shop at the Capucins (#2561) |
| `wald.m4a` | Forêt et ruisseau #1 (#2713) |
| `rauschen.m4a` | selbst erzeugt (braunes Rauschen), kein Fremdmaterial |

## Stimmen
| Stimme | Lizenz |
|---|---|
| Piper `de_DE-thorsten-medium` | CC0 (Thorsten Müller) |
| Piper `en_US-lessac-medium` | Blizzard-2013-Lizenz (nur nicht-kommerziell) |
| Online-Stimmen | Microsoft Edge „Vorlesen“ – Dienst von Microsoft, nicht Teil dieser Software |

## Erst auf Wunsch nachgeladen
| Komponente | Lizenz |
|---|---|
| Chatterbox (eigene Stimme, Resemble AI) | MIT |
| PyTorch | BSD-3-Clause |
| Whisper-Modelle (Systran/faster-whisper) | MIT |
