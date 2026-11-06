#!/bin/bash
# dist/Vorleser.app → dist/Vorleser-<Version>-mac.dmg (mit Verknüpfung zu „Programme“ zum Hineinziehen)
set -euo pipefail
cd "$(dirname "$0")/.."
VERSION="$(cat VERSION)"
APP="dist/Vorleser.app"
OUT="dist/Vorleser-${VERSION}-mac.dmg"
[ -d "$APP" ] || { echo "$APP fehlt – erst PyInstaller laufen lassen"; exit 1; }

# Ad-hoc-Signatur über das ganze Paket (ohne Apple-Konto; nötig, damit es auf Apple-Chips startet)
codesign --force --deep --sign - "$APP"

STAGE="$(mktemp -d)"
cp -R "$APP" "$STAGE/"
ln -s /Applications "$STAGE/Programme"
rm -f "$OUT"
hdiutil create -volname "Vorleser" -srcfolder "$STAGE" -ov -format UDZO -fs HFS+ "$OUT" >/dev/null
rm -rf "$STAGE"
echo "Fertig: $OUT ($(du -h "$OUT" | cut -f1))"
