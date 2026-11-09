"""Atmosphäre-Klänge für static/klang/ erzeugen (Version 3.0).

Lädt die CC0-Originale von BigSoundBank, schneidet je ~70 s heraus, gleicht die Lautheit an (≈ −24 LUFS) und blendet das
Ende 6 s lang in den Anfang → nahtlose Schleife. „Rauschen“ ist selbst erzeugtes braunes Rauschen.
Aufruf:  .venv-build/bin/python packaging/make_klang.py   (braucht Netz + numpy)
"""
import subprocess
import tempfile
import urllib.request
from pathlib import Path

import imageio_ffmpeg
import numpy as np

FF = imageio_ffmpeg.get_ffmpeg_exe()
SR = 44100
OUT = Path(__file__).resolve().parent.parent / "static" / "klang"
# Name: (BigSoundBank-Nummer, Start in s, Schleifenlänge in s)
QUELLEN = {"regen": (1019, 20, 72), "kamin": (2856, 1, 70), "cafe": (2561, 30, 72), "wald": (2713, 40, 72)}
BLENDE = 6


def laden(datei: Path, start: float, dauer: float) -> np.ndarray:
    raw = subprocess.run([FF, "-v", "error", "-ss", str(start), "-t", str(dauer), "-i", str(datei),
                          "-af", "loudnorm=I=-24:LRA=7:TP=-3", "-ar", str(SR), "-ac", "2", "-f", "f32le", "-"],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.float32).reshape(-1, 2).copy()


def schleife(x: np.ndarray, laenge: float) -> np.ndarray:
    n, b = int(laenge * SR), int(BLENDE * SR)
    a = x[:n + b]
    assert len(a) == n + b, "Aufnahme zu kurz"
    t = np.linspace(0, 1, b)[:, None]
    y = a[b:n + b].copy()
    y[-b:] = a[n:n + b] * np.cos(t * np.pi / 2) + a[:b] * np.sin(t * np.pi / 2)   # Ende läuft in den Anfang über
    return y


def speichern(y: np.ndarray, name: str) -> None:
    subprocess.run([FF, "-v", "error", "-y", "-f", "f32le", "-ar", str(SR), "-ac", "2", "-i", "-",
                    "-c:a", "aac", "-b:a", "96k", str(OUT / f"{name}.m4a")], input=y.astype(np.float32).tobytes(), check=True)
    print(name, f"{len(y) / SR:.0f} s", (OUT / f"{name}.m4a").stat().st_size // 1024, "KB")


def braunes_rauschen(laenge: float) -> np.ndarray:
    n = int((laenge + BLENDE) * SR)
    b = np.cumsum(np.random.default_rng(7).standard_normal((n, 2)), axis=0)
    fr = np.fft.rfftfreq(n, 1 / SR)
    for c in range(2):                                   # Drift unter 30 Hz entfernen
        spec = np.fft.rfft(b[:, c]); spec[fr < 30] = 0; b[:, c] = np.fft.irfft(spec, n)
    b /= np.sqrt((b ** 2).mean()) * 10 ** (26 / 20)
    return b.astype(np.float32)


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        for name, (nr, start, laenge) in QUELLEN.items():
            datei = Path(tmp) / f"{nr}.mp3"
            req = urllib.request.Request(f"https://bigsoundbank.com/UPLOAD/mp3/{nr:04d}.mp3", headers={"User-Agent": "Vorleser-Build"})
            datei.write_bytes(urllib.request.urlopen(req, timeout=60).read())
            speichern(schleife(laden(datei, start, laenge + BLENDE + 1), laenge), name)
    speichern(schleife(braunes_rauschen(72), 72), "rauschen")
