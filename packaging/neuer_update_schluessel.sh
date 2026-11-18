#!/bin/bash
# Einmalig (oder wenn der Schlüssel ersetzt werden muss): Schlüsselpaar für signierte Updates erzeugen.
#   - privater Schlüssel → GitHub-Secret UPDATE_SIGNING_KEY (Repo vorleser) + Sicherung auf dem Homeserver
#     (~/vorleser-signing/, nur für simon lesbar, kommt ins nächtliche Backup). Er wird nie angezeigt.
#   - öffentlicher Schlüssel → PUBLIC_KEY in update_sig.py (danach committen; wirkt ab dem nächsten Release)
# Achtung: Ein NEUER Schlüssel heißt, dass Apps mit dem alten Schlüssel neue Versionen nicht mehr annehmen.
# Nur ausführen, wenn noch kein Schlüssel existiert oder er verloren/verraten ist.
set -euo pipefail
cd "$(dirname "$0")/.."
PY=.venv-build/bin/python; [ -x "$PY" ] || PY=python3

if grep -q '^PUBLIC_KEY = "[0-9a-f]\{64\}"' update_sig.py; then
  read -r -p "In update_sig.py steht schon ein Schlüssel. Wirklich ersetzen? (ja/nein) " a
  [ "$a" = "ja" ] || { echo "Abgebrochen."; exit 1; }
fi

TMP=$(mktemp -d); trap 'rm -rf "$TMP"' EXIT; chmod 700 "$TMP"
umask 077
PUB=$("$PY" - "$TMP/key" <<'PY'
import os, sys, update_sig
seed = os.urandom(32)
open(sys.argv[1], "w").write(seed.hex())
print(update_sig.public_key(seed).hex())
PY
)

gh secret set UPDATE_SIGNING_KEY -R SimonSchneZzer/vorleser < "$TMP/key"
echo "✓ GitHub-Secret UPDATE_SIGNING_KEY gesetzt"

ssh -o HostName=192.168.8.50 homeserver 'umask 077; mkdir -p ~/vorleser-signing && cat > ~/vorleser-signing/update-signing-key' < "$TMP/key"
ssh -o HostName=192.168.8.50 homeserver "printf '%s\n' 'Vorleser: privater Schlüssel für signierte Updates (= GitHub-Secret UPDATE_SIGNING_KEY im Repo vorleser).' 'Öffentlicher Schlüssel (update_sig.py): $PUB' 'Nie weitergeben. Verloren/verraten: packaging/neuer_update_schluessel.sh + Release (alte Apps updaten dann nicht mehr automatisch).' > ~/vorleser-signing/README.txt; chmod 600 ~/vorleser-signing/*"
# Gegenprobe: die Sicherung passt zum öffentlichen Schlüssel
OK=$(ssh -o HostName=192.168.8.50 homeserver 'cat ~/vorleser-signing/update-signing-key' | "$PY" -c "import sys, update_sig; print(update_sig.public_key(bytes.fromhex(sys.stdin.read().strip())).hex())")
[ "$OK" = "$PUB" ] || { echo "✗ Sicherung auf dem Homeserver passt nicht – bitte melden"; exit 1; }
echo "✓ Sicherung auf dem Homeserver (~/vorleser-signing/)"

sed -i '' "s/^PUBLIC_KEY = \".*\"/PUBLIC_KEY = \"$PUB\"/" update_sig.py
echo "✓ Öffentlicher Schlüssel in update_sig.py eingetragen: $PUB"
echo "Fertig. Tipp: den privaten Schlüssel zusätzlich im Passwort-Manager ablegen (ssh homeserver 'cat ~/vorleser-signing/update-signing-key')."
