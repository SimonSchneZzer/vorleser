# PyInstaller-Bauplan für Vorleser (macOS → Vorleser.app, Windows → Vorleser\Vorleser.exe)
# Aufruf aus dem Projektordner:  pyinstaller --noconfirm packaging/vorleser.spec
import shutil
import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_all, collect_data_files

ROOT = Path(SPECPATH).parent
VERSION = (ROOT / "VERSION").read_text().strip()
IS_WIN = sys.platform == "win32"
IS_MAC = sys.platform == "darwin"

datas = [
    (str(ROOT / "static"), "static"),
    (str(ROOT / "clone_worker.py"), "."),        # läuft später in der nachinstallierten Klon-Umgebung
    (str(ROOT / "VERSION"), "."),                # für die Update-Prüfung
    (str(ROOT / "LICENSE"), "."),                # GPL: Lizenz + Hinweise liegen der App bei
    (str(ROOT / "THIRD_PARTY_NOTICES.md"), "."),
]
voices = sorted((ROOT / "voices").glob("*.onnx*"))
if not voices:
    sys.exit("voices/ ist leer – vorher die Piper-Stimmen laden (siehe packaging/README.md)")
datas += [(str(p), "voices") for p in voices]

binaries = []
uv = shutil.which("uv")                          # zum Nachinstallieren der eigenen Stimme
if not uv:
    sys.exit("uv nicht gefunden – wird zum Nachinstallieren der eigenen Stimme mitgeliefert")
binaries.append((uv, "."))

hiddenimports = []
for pkg in ("piper", "faster_whisper", "imageio_ffmpeg", "edge_tts", "ctranslate2", "onnxruntime"):
    d, b, h = collect_all(pkg)
    datas += d
    binaries += b
    hiddenimports += h
datas += collect_data_files("ebooklib")

a = Analysis(
    [str(ROOT / "desktop.py")],
    pathex=[str(ROOT)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    excludes=["tkinter", "matplotlib", "torch", "IPython", "pytest", "PIL"],
    noarchive=False,
)
pyz = PYZ(a.pure)

icon = str(ROOT / "packaging" / "icon.png")      # PyInstaller wandelt per Pillow in .icns/.ico um

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Vorleser",
    console=False,                               # kein Konsolenfenster
    icon=icon,
    codesign_identity=None,
    entitlements_file=None,
    upx=False,
)
coll = COLLECT(exe, a.binaries, a.datas, name="Vorleser", upx=False)

if IS_MAC:
    app = BUNDLE(
        coll,
        name="Vorleser.app",
        icon=icon,
        bundle_identifier="de.neke-neke.vorleser",
        version=VERSION,
        info_plist={
            "CFBundleDisplayName": "Vorleser",
            "CFBundleShortVersionString": VERSION,
            "CFBundleVersion": VERSION,
            "LSMinimumSystemVersion": "12.0",
            "NSHighResolutionCapable": True,
            "NSMicrophoneUsageDescription": "Zum Diktieren und zum Aufnehmen deiner eigenen Stimme.",
            "NSRequiresAquaSystemAppearance": False,   # Dunkelmodus erlauben
            "CFBundleDocumentTypes": [{
                "CFBundleTypeName": "Text",
                "CFBundleTypeRole": "Viewer",
                "LSItemContentTypes": ["org.idpf.epub-container", "com.adobe.pdf", "public.plain-text"],
                "LSHandlerRank": "Alternate",
            }],
        },
    )
