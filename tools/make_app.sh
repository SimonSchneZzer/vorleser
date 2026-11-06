#!/bin/zsh
# Baut Vorleser.app (Doppelklick-Start) im Projektordner – inkl. Icon.
set -e
DIR="$(cd "$(dirname "$0")/.." && pwd)"
APP="$DIR/Vorleser.app"
rm -rf "$APP"
mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources"

cat > "$APP/Contents/Info.plist" <<'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>CFBundleName</key><string>Vorleser</string>
  <key>CFBundleDisplayName</key><string>Vorleser</string>
  <key>CFBundleIdentifier</key><string>local.vorleser.app</string>
  <key>CFBundleVersion</key><string>1.0</string>
  <key>CFBundleShortVersionString</key><string>1.0</string>
  <key>CFBundlePackageType</key><string>APPL</string>
  <key>CFBundleExecutable</key><string>Vorleser</string>
  <key>CFBundleIconFile</key><string>Vorleser</string>
  <key>LSUIElement</key><true/>
  <key>LSMinimumSystemVersion</key><string>12.0</string>
</dict></plist>
PLIST

# Startprogramm: findet den Projektordner neben der App (oder den beim Bauen gemerkten Pfad)
cat > "$APP/Contents/MacOS/Vorleser" <<EOF
#!/bin/zsh
APP_DIR="\$(cd "\$(dirname "\$0")/../.." && pwd)"
DIR="\$(dirname "\$APP_DIR")"
[ -f "\$DIR/server.py" ] || DIR="$DIR"
VORLESER_DIR="\$DIR" exec /bin/zsh "\$DIR/tools/launch.sh"
EOF
chmod +x "$APP/Contents/MacOS/Vorleser"

# Icon: Petrol-Kachel mit Wellenform (mit dem mitgelieferten ffmpeg gezeichnet)
FF="$("$DIR/.venv/bin/python" -c 'import imageio_ffmpeg as i; print(i.get_ffmpeg_exe())' 2>/dev/null || true)"
if [ -n "$FF" ]; then
  TMP="$(mktemp -d)"
  ALPHA="if(lte(pow(max(max(280-X\,X-744)\,0)\,2)+pow(max(max(280-Y\,Y-744)\,0)\,2)\,32400)*between(X\,100\,924)*between(Y\,100\,924)\,255\,0)"
  "$FF" -hide_banner -loglevel error -y -f lavfi -i "color=c=0x0F6A80:s=1024x1024" -frames:v 1 -vf "\
drawbox=x=332:y=392:w=64:h=240:color=white:t=fill,\
drawbox=x=446:y=292:w=64:h=440:color=white:t=fill,\
drawbox=x=560:y=392:w=64:h=240:color=white:t=fill,\
drawbox=x=674:y=452:w=64:h=120:color=white:t=fill,\
format=rgba,geq=r='r(X,Y)':g='g(X,Y)':b='b(X,Y)':a='$ALPHA'" "$TMP/icon.png"
  mkdir -p "$TMP/Vorleser.iconset"
  for s in 16 32 128 256 512; do
    sips -z $s $s "$TMP/icon.png" --out "$TMP/Vorleser.iconset/icon_${s}x${s}.png" >/dev/null
    sips -z $((s*2)) $((s*2)) "$TMP/icon.png" --out "$TMP/Vorleser.iconset/icon_${s}x${s}@2x.png" >/dev/null
  done
  iconutil -c icns "$TMP/Vorleser.iconset" -o "$APP/Contents/Resources/Vorleser.icns" && echo "Icon erstellt"
  rm -rf "$TMP"
fi

codesign --force --deep -s - "$APP" >/dev/null 2>&1 || true   # Ad-hoc-Signatur (lokal)
touch "$APP"
echo "Fertig: $APP"
