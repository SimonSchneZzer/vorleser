#!/usr/bin/env python3
"""Teil-Updates: Dateiliste mit Prüfsummen + kleines Paket mit nur den geänderten Dateien.

  python packaging/make_patch.py <mac|windows> <App-Ordner> <Version> <Ausgabe-Ordner> [Vorversion …]

Schreibt in den Ausgabe-Ordner:
  Vorleser-<plat>-manifest.json   alle Dateien der App (Pfad → Prüfsumme, Größe, ausführbar; Verknüpfungen → Ziel)
  Vorleser-<plat>-patch.zip       nur Dateien, die sich gegenüber einer der Vorversionen geändert haben
                                  (+ manifest.json darin) – nur, wenn es Vorversionen mit Dateiliste gibt
  Vorleser-<plat>-patch.json      {"from": [Vorversionen], "files": n}

Die App prüft beim Einspielen jede Datei, die NICHT im Paket ist, per Prüfsumme gegen die Liste – passt etwas
nicht (z. B. eine ältere Version als die hier abgedeckten), lädt sie wie bisher das komplette Installationspaket.
"""
from __future__ import annotations

import hashlib
import json
import os
import stat
import sys
import urllib.request
import zipfile
from pathlib import Path

DL = "https://github.com/SimonSchneZzer/vorleser-download/releases/download"


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        while b := f.read(1 << 20):
            h.update(b)
    return h.hexdigest()


def manifest(root: Path) -> dict:
    """Pfad (mit /) → {"h", "s", "x"} für Dateien bzw. {"l": Ziel} für Verknüpfungen."""
    files: dict[str, dict] = {}
    for dirpath, dirnames, filenames in os.walk(root):
        d = Path(dirpath)
        for name in sorted(dirnames + filenames):
            p = d / name
            rel = p.relative_to(root).as_posix()
            if p.is_symlink():
                files[rel] = {"l": os.readlink(p)}
            elif p.is_file():
                st = p.stat()
                files[rel] = {"h": sha256(p), "s": st.st_size, "x": bool(st.st_mode & stat.S_IXUSR)}
        dirnames[:] = [n for n in dirnames if not (d / n).is_symlink()]   # verlinkte Ordner nicht betreten
    return dict(sorted(files.items()))


def _vkey(v: str) -> tuple:
    return tuple(int(x) if x.isdigit() else 0 for x in v.split("."))


def previous(plat: str, versions: list[str]) -> dict[str, dict]:
    out = {}
    for v in versions:
        if Path(v).is_file():                                   # lokale Dateiliste (Tests)
            m = json.loads(Path(v).read_text("utf-8"))
            out[m["version"]] = m["files"]
            continue
        url = f"{DL}/v{v}/Vorleser-{plat}-manifest.json"
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "Vorleser-Build"}), timeout=30) as r:
                out[v] = json.loads(r.read())["files"]
            print(f"Vorversion {v}: Dateiliste gefunden")
        except Exception as e:
            print(f"Vorversion {v}: keine Dateiliste ({type(e).__name__}) – nicht abgedeckt")
    return out


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")   # Windows-Konsole (cp1252) kennt „→“ nicht
    plat, root, version, out = sys.argv[1], Path(sys.argv[2]), sys.argv[3], Path(sys.argv[4])
    out.mkdir(parents=True, exist_ok=True)
    files = manifest(root)
    man = {"version": version, "platform": plat, "files": files}
    (out / f"Vorleser-{plat}-manifest.json").write_text(json.dumps(man, separators=(",", ":")), "utf-8")
    total = sum(f.get("s", 0) for f in files.values())
    print(f"Dateiliste: {len(files)} Einträge, {total / 1e6:.0f} MB")

    prev = previous(plat, sys.argv[5:])
    if not prev:
        print("Keine Vorversion mit Dateiliste → kein Teil-Update (die App lädt das komplette Paket)")
        return 0
    # Ausreißer nicht mitversorgen (3.0.4): fehlt einer alten Version z. B. die Offline-Stimme (63 MB), landete sie
    # bei JEDEM Update im Paket – alle 3.0.x-Nutzer luden 75 MB statt ~16. Abgedeckt wird nur, wer höchstens das
    # Doppelte (bzw. +10 MB) des Unterschieds zur neuesten Vorversion braucht; die übrigen laden das komplette Paket
    # (die App erkennt das selbst an der Dateiliste).
    def diff(p: dict) -> list[str]:
        return [rel for rel, f in files.items() if "h" in f and p.get(rel) != f]
    sizes = {v: sum(files[r]["s"] for r in diff(p)) for v, p in prev.items()}
    newest = max(prev, key=_vkey)
    limit = max(2 * sizes[newest], sizes[newest] + 10_000_000)
    for v in sorted(prev, key=_vkey):
        if sizes[v] > limit:
            print(f"Vorversion {v}: {sizes[v] / 1e6:.0f} MB anders (Grenze {limit / 1e6:.0f} MB) – nicht abgedeckt, lädt das komplette Paket")
    prev = {v: p for v, p in prev.items() if sizes[v] <= limit}
    changed = sorted(rel for rel, f in files.items() if "h" in f and any(p.get(rel) != f for p in prev.values()))
    zpath = out / f"Vorleser-{plat}-patch.zip"
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        z.writestr("manifest.json", json.dumps(man, separators=(",", ":")))
        for rel in changed:
            z.write(root / rel, "files/" + rel)
    size = sum(files[r]["s"] for r in changed)
    (out / f"Vorleser-{plat}-patch.json").write_text(json.dumps({"from": sorted(prev), "files": len(changed)}), "utf-8")
    print(f"Teil-Update: {len(changed)} Dateien ({size / 1e6:.1f} MB, gepackt {zpath.stat().st_size / 1e6:.1f} MB) "
          f"für {', '.join(sorted(prev))}")
    for rel in changed[:40]:
        print("  ", rel)
    return 0


if __name__ == "__main__":
    sys.exit(main())
