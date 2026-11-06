#!/bin/zsh
# Startet den Vorleser (falls er nicht schon läuft) und öffnet ihn im Browser.
# Wird von Vorleser.app und start.sh benutzt.
DIR="${VORLESER_DIR:-$(cd "$(dirname "$0")/.." && pwd)}"
URL="http://127.0.0.1:8765"
alive() { /usr/bin/curl -sf -m 2 "$URL/api/settings" >/dev/null 2>&1; }

if alive; then open "$URL"; exit 0; fi

if [ ! -x "$DIR/.venv/bin/python" ]; then          # noch nicht installiert
  open -a Terminal "$DIR/Installieren.command"
  exit 0
fi

mkdir -p "$DIR/data"
cd "$DIR" || exit 1
nohup .venv/bin/python server.py >> "$DIR/data/server.log" 2>&1 &
disown 2>/dev/null

for i in {1..90}; do alive && break; sleep 0.5; done
if alive; then
  open "$URL"
else
  osascript -e 'display alert "Vorleser konnte nicht starten" message "Details stehen in data/server.log im Vorleser-Ordner."' >/dev/null
  open -R "$DIR/data/server.log"
fi
