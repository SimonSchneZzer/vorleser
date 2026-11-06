#!/bin/zsh
# Richtet den Vorleser auf diesem Mac ein (einmalig, braucht Internet).
# Danach startet man ihn per Doppelklick auf Vorleser.app.
cd "$(dirname "$0")" || exit 1
set -e
print -P "\n%BVorleser wird eingerichtet …%b\n"

# 1) uv (Python-Paketmanager, installiert bei Bedarf auch Python selbst)
if command -v uv >/dev/null 2>&1; then UV="$(command -v uv)"
elif [ -x "$HOME/.local/bin/uv" ]; then UV="$HOME/.local/bin/uv"
else
  echo "→ Installiere uv …"
  curl -LsSf https://astral.sh/uv/install.sh | sh
  UV="$HOME/.local/bin/uv"
fi

# 2) Hauptprogramm
echo "→ Installiere den Vorleser (Python 3.12) …"
[ -x .venv/bin/python ] || "$UV" venv --python 3.12 .venv
"$UV" pip install --python .venv/bin/python -q -r requirements.txt

# 3) Offline-Ersatzstimmen (Piper)
mkdir -p voices
for v in de_DE-thorsten-medium en_US-lessac-medium; do
  if [ ! -f "voices/$v.onnx" ]; then
    echo "→ Lade Offline-Stimme $v …"
    (cd voices && ../.venv/bin/python -m piper.download_voices "$v" >/dev/null)
  fi
done

# 4) Optional: eigene Stimme (Stimmklon, ca. 4,5 GB)
if [ ! -x .venv-clone/bin/python ]; then
  echo
  read "ans?Eigene Stimme (Stimmklon) auch installieren? Braucht ca. 4,5 GB. [j/N] "
  if [[ "$ans" == [jJyY]* ]]; then
    echo "→ Installiere Stimmklon (dauert ein paar Minuten) …"
    "$UV" venv --python 3.11 .venv-clone
    "$UV" pip install --python .venv-clone/bin/python -q -r requirements-clone.txt
  fi
fi

# 5) App bauen und starten
echo "→ Baue Vorleser.app …"
zsh tools/make_app.sh >/dev/null
print -P "\n%BFertig!%b Ab jetzt einfach %BVorleser.app%b doppelklicken"
print    "(gern auch ins Dock ziehen). Der Vorleser startet jetzt …\n"
[ -z "$NO_OPEN" ] && open Vorleser.app
