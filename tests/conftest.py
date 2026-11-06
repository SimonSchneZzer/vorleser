"""Gemeinsame Test-Grundlage.

Wichtig: VORLESER_HOME wird gesetzt, BEVOR irgendein Projektmodul importiert wird – paths.py liest
den Datenordner beim Import. So läuft jeder Testlauf in einem Wegwerf-Ordner und fasst nie echte
Daten an. Die mitgelieferten Piper-Stimmen kommen weiter aus voices/ im Projektordner.

Marker (siehe pyproject.toml):
  online  – braucht Internet (Edge-Stimmen); nur mit  VORLESER_TEST_ONLINE=1
  browser – startet Headless-Chrome; übersprungen, wenn Chrome fehlt
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_HOME = Path(tempfile.mkdtemp(prefix="vorleser-test-"))
os.environ["VORLESER_HOME"] = str(_HOME)
os.environ.pop("VORLESER_VERSION", None)
os.environ.pop("VORLESER_UPDATE_URL", None)
os.environ["VORLESER_UPDATE_JSON"] = "http://127.0.0.1:9/latest.json"   # Updater: nie die echte latest.json
sys.path.insert(0, str(ROOT))

# Leere Edge-Liste: keine Netzabfrage, kein 8-s-Warten auf die Online-Stimmen beim „ersten Start“
(_HOME / "data").mkdir(parents=True, exist_ok=True)
(_HOME / "data" / "edge_voices.json").write_text("[]", "utf-8")

import pytest  # noqa: E402

import paths  # noqa: E402
import tts  # noqa: E402

HAS_PIPER = any(paths.BUNDLED_VOICES.glob("*.onnx"))
needs_piper = pytest.mark.skipif(not HAS_PIPER, reason="keine Piper-Stimmen in voices/ (siehe README)")


def pytest_collection_modifyitems(config, items):
    online = os.environ.get("VORLESER_TEST_ONLINE") == "1"
    for item in items:
        if "online" in item.keywords and not online:
            item.add_marker(pytest.mark.skip(reason="Internet-Test – mit VORLESER_TEST_ONLINE=1 aktivieren"))


def pytest_sessionfinish(session, exitstatus):
    shutil.rmtree(_HOME, ignore_errors=True)


@pytest.fixture
def home() -> Path:
    """Der Wegwerf-Datenordner dieses Testlaufs."""
    return _HOME


def ffprobe_duration(data_or_path) -> float | None:
    """Dauer laut Container-Header (None = 'N/A'), über das mitgelieferte ffmpeg."""
    if isinstance(data_or_path, (bytes, bytearray)):
        f = tempfile.NamedTemporaryFile(suffix=".bin", delete=False)
        f.write(data_or_path)
        f.close()
        path = f.name
    else:
        path = str(data_or_path)
    try:
        r = subprocess.run([tts.FFMPEG, "-hide_banner", "-i", path], capture_output=True, text=True)
    finally:
        if isinstance(data_or_path, (bytes, bytearray)):
            os.unlink(path)
    for line in r.stderr.splitlines():
        if "Duration:" in line:
            val = line.split("Duration:")[1].split(",")[0].strip()
            if val == "N/A":
                return None
            h, m, s = val.split(":")
            return int(h) * 3600 + int(m) * 60 + float(s)
    return None


def sine_wav(seconds: float = 1.0) -> bytes:
    """Kurzer Testton als WAV (24 kHz mono)."""
    return tts.ffmpeg(["-f", "lavfi", "-i", f"sine=frequency=440:duration={seconds}",
                       "-ac", "1", "-ar", "24000", "-f", "wav", "pipe:1"])


class Api:
    """Kleiner HTTP-Client für den Test-Server."""

    def __init__(self, base: str):
        self.base = base

    def call(self, method: str, path: str, body=None, raw: bytes | None = None, headers: dict | None = None):
        data = raw if raw is not None else (json.dumps(body).encode() if body is not None else None)
        h = {"Content-Type": "application/json", **(headers or {})}
        req = urllib.request.Request(self.base + path, data=data, method=method, headers=h)
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                payload = r.read()
                return r.status, r.headers, payload
        except urllib.error.HTTPError as e:
            return e.code, e.headers, e.read()

    def json(self, method: str, path: str, body=None, **kw):
        status, _, payload = self.call(method, path, body, **kw)
        return status, json.loads(payload or b"null")


@pytest.fixture(scope="session")
def api():
    """Echter Vorleser-Server auf einem freien Port (ohne Netz-Startaufgaben)."""
    import server
    srv = server.bind(0)
    quit_calls = []
    server.ON_QUIT = lambda: quit_calls.append(True)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    client = Api(f"http://127.0.0.1:{srv.server_address[1]}")
    client.quit_calls = quit_calls
    yield client
    srv.shutdown()
