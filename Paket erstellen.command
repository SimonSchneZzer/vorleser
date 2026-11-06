#!/bin/zsh
# Packt den Vorleser als ZIP auf den Schreibtisch – zum Weitergeben oder für einen anderen Mac.
# Ohne Installation, Cache und persönliche Daten (Texte, eigene Stimmen, Einstellungen).
PROJ="$(cd "$(dirname "$0")" && pwd)"
NAME="$(basename "$PROJ")"
cd "$(dirname "$PROJ")" || exit 1
OUT="$HOME/Desktop/Vorleser.zip"
rm -f "$OUT"
zip -r -q "$OUT" "$NAME" \
  -x "$NAME/.venv/*" "$NAME/.venv-clone/*" "$NAME/cache/*" "$NAME/data/*" "$NAME/voices/*" \
     "$NAME/Vorleser.app/*" "*/__pycache__/*" "*.pyc" "*/.DS_Store"
print -P "\n%BPaket erstellt:%b $OUT ($(du -h "$OUT" | cut -f1))\n"
print "Auf dem anderen Mac: entpacken, dann Installieren.command doppelklicken"
print "(beim ersten Mal ggf. Rechtsklick → Öffnen, weil es aus dem Internet kommt).\n"
[ -z "$NO_OPEN" ] && open -R "$OUT"
