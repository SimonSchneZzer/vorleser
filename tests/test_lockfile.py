"""requirements.lock passt zu den Wünschen in requirements*.txt (sonst baut die CI etwas anderes als gedacht)."""
import re

import paths
from packaging.requirements import Requirement
from packaging.utils import canonicalize_name

LOCK = paths.APP_DIR / "requirements.lock"


def _wishes():
    for name in ("requirements.txt", "requirements-desktop.txt", "requirements-dev.txt"):
        for line in (paths.APP_DIR / name).read_text("utf-8").splitlines():
            line = line.split("#", 1)[0].strip()
            if line:
                yield name, Requirement(line)


def _locked() -> dict[str, str]:
    pins = {}
    for line in LOCK.read_text("utf-8").splitlines():
        if m := re.match(r"^([A-Za-z0-9_.\-]+)==([^\s;]+)", line):
            pins[canonicalize_name(m.group(1))] = m.group(2)
    return pins


def test_lockfile_deckt_alle_wuensche():
    pins = _locked()
    for source, req in _wishes():
        name = canonicalize_name(req.name)
        assert name in pins, f"{req.name} ({source}) fehlt in requirements.lock – neu erzeugen (siehe CLAUDE.md)"
        assert req.specifier.contains(pins[name], prereleases=True), \
            f"{req.name}=={pins[name]} passt nicht zu „{req}“ ({source}) – requirements.lock neu erzeugen"


def test_lockfile_nur_feste_versionen():
    lines = [l for l in LOCK.read_text("utf-8").splitlines() if l and not l.startswith(("#", " "))]
    assert lines and all("==" in l for l in lines)
