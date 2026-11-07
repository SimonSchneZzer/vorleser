"""Teil-Updates: Paket bauen (packaging/make_patch.py) und einspielen (updater._apply_patch) – ohne Netz."""
import json
import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

import updater

ROOT = Path(__file__).resolve().parent.parent


def _app(d: Path, files: dict[str, bytes], links: dict[str, str] | None = None) -> Path:
    for rel, data in files.items():
        p = d / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)
    for rel, target in (links or {}).items() if os.name != "nt" else ():   # Verknüpfungen brauchen unter Windows Sonderrechte
        (d / rel).parent.mkdir(parents=True, exist_ok=True)
        os.symlink(target, d / rel)
    return d


def _build(tmp: Path, version: str, app: Path, prev: list[str] = ()) -> Path:
    out = tmp / f"out-{version}"
    subprocess.run([sys.executable, str(ROOT / "packaging/make_patch.py"), "mac", str(app), version, str(out), *prev],
                   check=True, capture_output=True)
    return out


@pytest.fixture
def apps(tmp_path):
    old = _app(tmp_path / "old", {"Contents/a.bin": b"A" * 1000, "Contents/b.txt": b"alt", "Contents/c.txt": b"weg"},
               {"Contents/link": "a.bin"})
    new = _app(tmp_path / "new", {"Contents/a.bin": b"A" * 1000, "Contents/b.txt": b"neu", "Contents/d/e.txt": b"dazu"},
               {"Contents/link": "a.bin"})
    o = _build(tmp_path, "1.0.0", old)
    n = _build(tmp_path, "1.1.0", new, [str(o / "Vorleser-mac-manifest.json")])
    return tmp_path, old, new, n


def test_paket_enthaelt_nur_geaenderte_dateien(apps):
    _, _, _, n = apps
    with zipfile.ZipFile(n / "Vorleser-mac-patch.zip") as z:
        assert sorted(z.namelist()) == ["files/Contents/b.txt", "files/Contents/d/e.txt", "manifest.json"]
    assert json.loads((n / "Vorleser-mac-patch.json").read_text())["from"] == ["1.0.0"]


def test_mac_einspielen_ergibt_genau_die_neue_version(apps, monkeypatch):
    tmp, old, new, n = apps
    monkeypatch.setattr(updater.paths, "IS_MAC", True)
    monkeypatch.setattr(updater.paths, "IS_WIN", False)
    staged = tmp / "staged"
    shutil.copytree(old, staged, symlinks=True)
    gone = updater._apply_patch(n / "Vorleser-mac-patch.zip", old, staged, "1.1.0")
    assert gone == ["Contents/c.txt"]
    assert (staged / "Contents/b.txt").read_bytes() == b"neu"
    assert (staged / "Contents/d/e.txt").read_bytes() == b"dazu"
    assert not (staged / "Contents/c.txt").exists()
    if os.name != "nt":
        assert os.readlink(staged / "Contents/link") == "a.bin"
    assert (old / "Contents/b.txt").read_bytes() == b"alt"            # Original bleibt unangetastet


def test_windows_bereitet_nur_neue_dateien_vor(apps, monkeypatch):
    tmp, old, new, n = apps
    monkeypatch.setattr(updater.paths, "IS_MAC", False)
    monkeypatch.setattr(updater.paths, "IS_WIN", True)
    (old / "unins000.exe").write_bytes(b"inno")                      # Deinstallationsprogramm bleibt
    for d in (old, new):                                             # Windows kennt keine Verknüpfungen im Paket
        if os.path.lexists(d / "Contents/link"):
            os.remove(d / "Contents/link")
    o = _build(tmp, "1.0.0", old); n = _build(tmp, "1.1.0", new, [str(o / "Vorleser-mac-manifest.json")])
    staged = tmp / "win-staged"; staged.mkdir()
    gone = updater._apply_patch(n / "Vorleser-mac-patch.zip", old, staged, "1.1.0")
    assert sorted(p.relative_to(staged).as_posix() for p in staged.rglob("*") if p.is_file()) == ["Contents/b.txt", "Contents/d/e.txt"]
    assert gone == ["Contents/c.txt"]


def test_abweichende_datei_bricht_ab(apps, monkeypatch):
    tmp, old, new, n = apps
    monkeypatch.setattr(updater.paths, "IS_MAC", True)
    (old / "Contents/a.bin").write_bytes(b"B" * 1000)                # gleiche Größe, anderer Inhalt
    staged = tmp / "staged"
    shutil.copytree(old, staged, symlinks=True)
    with pytest.raises(RuntimeError, match="Prüfsumme"):
        updater._apply_patch(n / "Vorleser-mac-patch.zip", old, staged, "1.1.0")


def test_teilupdate_nur_fuer_abgedeckte_version(monkeypatch):
    monkeypatch.setattr(updater.paths, "FROZEN", True)
    monkeypatch.setattr(updater.paths, "APP_VERSION", "1.0.0")
    p = {"url": "x", "size": 1, "from": ["1.0.0"]}
    assert updater._patch_for({"patch": p}) == p
    monkeypatch.setattr(updater.paths, "APP_VERSION", "0.9.0")
    assert updater._patch_for({"patch": p}) is None
    assert updater._patch_for({"patch": None}) is None
