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
    (str(ROOT / "CHANGELOG.md"), "."),           # „Was ist neu“ in der App (offline)
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
AUTHOR = "Simon Schnetzer"
COPYRIGHT = f"© 2026 {AUTHOR}"

version_file = None
if IS_WIN:                                       # Datei-Eigenschaften der .exe: Firma, Copyright, Version
    nums = tuple((list(map(int, VERSION.split(".")[:4])) + [0, 0, 0, 0])[:4])
    strings = {"CompanyName": AUTHOR, "FileDescription": "Vorleser", "FileVersion": VERSION, "InternalName": "Vorleser",
               "LegalCopyright": COPYRIGHT, "OriginalFilename": "Vorleser.exe", "ProductName": "Vorleser",
               "ProductVersion": VERSION}
    version_file = Path(workpath) / "version_info.txt"   # Textformat, das PyInstaller unter Windows einliest
    version_file.parent.mkdir(parents=True, exist_ok=True)
    version_file.write_text(f"""VSVersionInfo(
  ffi=FixedFileInfo(filevers={nums}, prodvers={nums}, mask=0x3f, flags=0x0, OS=0x40004, fileType=0x1,
                    subtype=0x0, date=(0, 0)),
  kids=[
    StringFileInfo([StringTable('040704B0', [{", ".join(f"StringStruct({k!r}, {v!r})" for k, v in strings.items())}])]),
    VarFileInfo([VarStruct('Translation', [0x0407, 1200])])
  ]
)
""", encoding="utf-8")
    version_file = str(version_file)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Vorleser",
    console=False,                               # kein Konsolenfenster
    icon=icon,
    version=version_file,
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
            "NSHumanReadableCopyright": COPYRIGHT,     # Finder › Informationen, „Über Vorleser“
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
