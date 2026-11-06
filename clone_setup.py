"""Eigene Stimme (Chatterbox) nachinstallieren – auf Knopfdruck aus der App, ohne Terminal.

Die App bringt das Werkzeug `uv` mit. Damit entsteht im Benutzerordner eine eigene
Python-Umgebung mit PyTorch + Chatterbox (~1–2,5 GB), danach wird das Modell (~3 GB) geladen.
Mac: Grafikchip (MPS). Windows: NVIDIA-Grafikkarte (CUDA), sonst Prozessor (langsam).
"""
from __future__ import annotations

import os
import shutil
import subprocess
import threading
import time
from pathlib import Path

import paths
from paths import CLONE_ENV, CLONE_PY, NO_WINDOW

PYTHON = "3.11"
PACKAGES = ["chatterbox-tts==0.1.7", "setuptools<81"]   # perth (Wasserzeichen) braucht pkg_resources
MARKER = CLONE_ENV / "vorleser-ok"
PY_DIR = paths.USER_DIR / "clone-python"        # von uv geladenes Python (nur App)
UV_CACHE = paths.USER_DIR / "clone-uv-cache"     # Download-Zwischenspeicher, wird danach gelöscht

_lock = threading.Lock()
_state: dict = {"status": "idle"}               # idle | running | done | error | cancelled
_proc: subprocess.Popen | None = None
_cancel = threading.Event()                      # Abbruch gewünscht (unabhängig vom Status, der beim Entfernen zurückgesetzt wird)


def _uv() -> str | None:
    exe = "uv.exe" if paths.IS_WIN else "uv"
    bundled = paths.APP_DIR / exe
    if bundled.exists():
        return str(bundled)
    return shutil.which("uv")


def supported() -> bool:
    """Kann diese Installation den Klon nachinstallieren?"""
    return _uv() is not None


def installed() -> bool:
    if not CLONE_PY.exists():
        return False
    if MARKER.exists():
        return True
    if paths.FROZEN:                                  # App: nur die Abschluss-Markierung zählt (kommt nach dem Modell)
        return False
    # ältere Entwicklungs-Umgebung (vor dem Marker) erkennen
    libs = [CLONE_ENV / "Lib" / "site-packages"] + list((CLONE_ENV / "lib").glob("python3*/site-packages"))
    return any((d / "chatterbox").is_dir() for d in libs)


def _has_nvidia() -> bool:
    smi = shutil.which("nvidia-smi")
    if not smi:
        return False
    try:
        return subprocess.run([smi, "-L"], capture_output=True, timeout=10, **NO_WINDOW).returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


_gpu_cache: str | None = None


def gpu_kind() -> str:
    """mps (Mac) | nvidia | cpu – für Texte in der Oberfläche (einmal ermittelt)."""
    global _gpu_cache
    if _gpu_cache is None:
        _gpu_cache = "mps" if paths.IS_MAC else "nvidia" if (paths.IS_WIN and _has_nvidia()) else "cpu"
    return _gpu_cache


def _dir_mb(d: Path) -> int:
    total = 0
    for root, _, files in os.walk(d):
        for f in files:
            try:
                total += os.path.getsize(os.path.join(root, f))
            except OSError:
                pass
    return total // (1024 * 1024)


def _env() -> dict:
    env = {**paths.clone_env(), "UV_CACHE_DIR": str(UV_CACHE),
           # Hugging Face „Xet“ sammelt Daten im Speicher und schreibt erst am Ende → kein messbarer Fortschritt
           "HF_HUB_DISABLE_XET": "1"}
    if paths.FROZEN:
        env["UV_PYTHON_INSTALL_DIR"] = str(PY_DIR)
        env["UV_PYTHON_PREFERENCE"] = "only-managed"   # nie ein zufälliges System-Python nehmen
    return env


# Erwartete Größen in MB (gemessen am entpackten uv-Cache bzw. an den Modelldateien, 2026-11-06).
# Nur Schätzwerte – wird einer überschritten, wächst er mit (Balken läuft nie über 100 %).
SIZES = {
    "python": 63,
    "packages": {"mac": 1070, "cpu": 1650, "nvidia": 5100},
    "model": 3060,                       # wird vor dem Download exakt bei Hugging Face erfragt
}
MODEL_FILES = {"ve.pt", "t3_mtl23ls_v2.safetensors", "s3gen.pt", "grapheme_mtl_merged_expanded_v1.json",
               "conds.pt", "Cangjie5_TC.json"}
SETUP_LOG = paths.DATA_DIR / "clone-setup.log"


def _model_mb() -> int:
    """Exakte Größe der Modelldateien laut Hugging Face (ohne Download)."""
    import json
    import urllib.request
    try:
        req = urllib.request.Request("https://huggingface.co/api/models/ResembleAI/chatterbox/tree/main",
                                     headers={"User-Agent": "Vorleser"})
        with urllib.request.urlopen(req, timeout=15) as r:
            files = json.loads(r.read())
        total = sum((f.get("lfs") or {}).get("size") or f.get("size", 0) for f in files if f.get("path") in MODEL_FILES)
        return max(1, total // (1024 * 1024)) if total else SIZES["model"]
    except Exception:
        return SIZES["model"]


def _step_from_log(phase: str) -> str | None:
    """Was macht uv gerade? (uv schreibt ohne Terminal nur Zusammenfassungen je Schritt.)"""
    try:
        tail = SETUP_LOG.read_text("utf-8", errors="replace")[-4000:]
    except OSError:
        return None
    if phase == "python":
        return "venv" if "Creating virtual environment" in tail or "Using CPython" in tail else "download"
    if phase == "packages":
        if "Installed " in tail:
            return "finish"
        if "Prepared " in tail:
            return "install"
        if "Resolved " in tail:
            return "download"
        return "resolve"
    return None


def _progress(totals: dict, order: list[str]) -> None:
    """Gesamtfortschritt, Geschwindigkeit (gleitend über ~20 s) und Restzeit berechnen."""
    st = _state
    phase = st["phase"]
    if phase == "model":
        # Größe ist exakt bekannt. Hugging Face kopiert große Dateien aus „.incomplete“ an ihren Platz –
        # kurz liegt die Datei doppelt auf der Platte. Deshalb begrenzen statt mitwachsen.
        st["mb"] = min(st["mb"], totals[phase])
        if st["mb"] >= totals[phase] * 0.995:
            st["step"] = "finish"                     # alles da – Hugging Face richtet es noch ein (kein „Download“ mehr)
    elif phase in totals and st["mb"] > totals[phase] * 0.97:
        totals[phase] = int(st["mb"] / 0.97) + 1               # Schätzung zu klein → mitwachsen
    done_before = sum(totals[p] for p in order[:order.index(phase)]) if phase in order else 0
    overall = done_before + min(st["mb"], totals.get(phase, 0))
    total = sum(totals.values())
    now = time.time()
    samples = st.setdefault("_samples", [])
    samples.append((now, overall))
    while samples and now - samples[0][0] > 20:
        samples.pop(0)
    speed = 0.0
    if len(samples) > 1 and samples[-1][0] > samples[0][0]:
        speed = (samples[-1][1] - samples[0][1]) / (samples[-1][0] - samples[0][0])
    if samples and len(samples) > 1 and samples[-1][1] > samples[-2][1]:
        st["lastGrowth"] = now
    eta = None
    if speed > 0.3:
        raw = (total - overall) / speed
        eta = raw if st.get("eta") is None else 0.7 * st["eta"] + 0.3 * raw   # glätten, damit sie nicht springt
    st.update(total=totals.get(phase, 0), overall=overall, overallTotal=total, speed=round(speed, 2),
              eta=round(eta) if eta is not None else None, stalled=round(now - st.get("lastGrowth", now)),
              totals=dict(totals))


def _run(phase: str, args: list[str], totals: dict, order: list[str], watch: tuple[Path, ...] = ()) -> None:
    """Befehl ausführen; währenddessen Fortschritt (wachsende Ordner) und Zwischenschritt melden."""
    global _proc
    if _cancel.is_set():
        raise InterruptedError
    with _lock:
        _state.update(phase=phase, mb=0, step=None, phaseStarted=time.time(), lastGrowth=time.time())
    print(f"[clone-setup] {phase}: {' '.join(args)}", flush=True)
    log = open(SETUP_LOG, "a", encoding="utf-8")
    log.write(f"\n== {time.strftime('%H:%M:%S')} {phase}\n")
    log.flush()
    measure = lambda: sum(_dir_mb(d) for d in watch if d.exists())
    base = measure()                                  # nur den Zuwachs zählen (Ordner kann schon Daten enthalten)
    try:
        _proc = subprocess.Popen(args, stdout=log, stderr=subprocess.STDOUT, env=_env(), **NO_WINDOW)
        while _proc.poll() is None:
            time.sleep(1.5)
            with _lock:
                if watch:
                    _state["mb"] = max(0, measure() - base)
                _state["step"] = _step_from_log(phase)
                _progress(totals, order)
        if _cancel.is_set():
            raise InterruptedError
        if _proc.returncode != 0:
            raise RuntimeError(f"{phase} fehlgeschlagen (Details im Log)")
        with _lock:                                   # Phase fertig → voll anrechnen
            _state["mb"] = totals.get(phase, _state["mb"])
            _progress(totals, order)
    finally:
        _proc = None
        log.close()


def _install() -> None:
    uv = _uv()
    started = time.time()
    try:
        shutil.rmtree(CLONE_ENV, ignore_errors=True)
        SETUP_LOG.unlink(missing_ok=True)
        nvidia = paths.IS_WIN and _has_nvidia()
        gpu = "nvidia" if nvidia else "mps" if paths.IS_MAC else "cpu"
        totals = {"python": SIZES["python"],
                  "packages": SIZES["packages"]["mac" if paths.IS_MAC else "nvidia" if nvidia else "cpu"],
                  "model": SIZES["model"]}
        order = list(totals)
        with _lock:
            _state.update(gpu=gpu, started=started, totals=dict(totals))
        threading.Thread(target=lambda: totals.update(model=_model_mb()), daemon=True).start()
        _run("python", [uv, "venv", "--python", PYTHON, str(CLONE_ENV)], totals, order,
             watch=(PY_DIR,) if paths.FROZEN else ())
        pip = [uv, "pip", "install", "--python", str(CLONE_PY)]
        if nvidia:
            try:     # torch 2.6 gibt es für CUDA 12.4; scheitert das, nimmt der Prozessor
                _run("packages", pip + ["--torch-backend", "cu124", *PACKAGES], totals, order, watch=(UV_CACHE,))
            except RuntimeError:
                with _lock:
                    _state["gpu"] = "cpu"
                totals["packages"] = SIZES["packages"]["cpu"]
                _run("packages", pip + ["--torch-backend", "cpu", *PACKAGES], totals, order, watch=(UV_CACHE,))
        else:
            _run("packages", pip + PACKAGES, totals, order, watch=(UV_CACHE,))
        hf_home = Path(_env().get("HF_HOME") or Path.home() / ".cache" / "huggingface")
        _run("model", [str(CLONE_PY), str(paths.CLONE_WORKER), "--download"], totals, order, watch=(hf_home,))
        MARKER.write_text(time.strftime("%Y-%m-%d %H:%M"), "utf-8")
        with _lock:
            _state.update(status="done", phase="done", seconds=round(time.time() - started))
        print(f"[clone-setup] fertig in {round(time.time() - started)} s", flush=True)
    except InterruptedError:
        print("[clone-setup] abgebrochen", flush=True)
        shutil.rmtree(CLONE_ENV, ignore_errors=True)
        with _lock:
            _state.clear()
            _state["status"] = "idle"
    except Exception as e:
        if _cancel.is_set():                          # während des Abbruchs gestorben → kein Fehler
            print("[clone-setup] abgebrochen", flush=True)
            with _lock:
                _state.clear()
                _state["status"] = "idle"
            return
        print(f"[clone-setup] Fehler: {e}", flush=True)
        with _lock:
            _state.update(status="error", error=str(e))
    finally:
        shutil.rmtree(UV_CACHE, ignore_errors=True)


def status() -> dict:
    with _lock:
        pub = {k: v for k, v in _state.items() if not k.startswith("_")}
        if pub.get("status") == "running":
            pub["now"] = time.time()                     # Uhr in der Oberfläche unabhängig von deren Uhrzeit
        return {**pub, "installed": installed(), "supported": supported()}


def start() -> dict:
    if not supported():
        raise ValueError("Nachinstallieren ist hier nicht möglich (uv fehlt)")
    with _lock:
        if _state["status"] == "running":
            return {**_state}
        _state.clear()
        _state.update(status="running", phase="python", mb=0)
    _cancel.clear()
    threading.Thread(target=_install, daemon=True).start()
    return status()


def cancel() -> None:
    """Laufende Installation abbrechen (auch beim Beenden der App aufgerufen)."""
    with _lock:
        if _state.get("status") != "running":
            return
    _cancel.set()
    proc = _proc
    if proc and proc.poll() is None:
        proc.kill()


def uninstall() -> dict:
    """Umgebung + (in der App) Python und Modell entfernen. Sprachproben der eigenen Stimmen bleiben."""
    cancel()
    time.sleep(0.5)                                  # abgebrochenem uv Zeit zum Beenden geben
    shutil.rmtree(CLONE_ENV, ignore_errors=True)
    shutil.rmtree(UV_CACHE, ignore_errors=True)
    if paths.FROZEN:
        shutil.rmtree(PY_DIR, ignore_errors=True)
        shutil.rmtree(paths.CLONE_MODELS, ignore_errors=True)
    with _lock:
        _state.clear()
        _state["status"] = "idle"
    return status()
