"""Stimmklon-Worker (läuft im eigenen venv .venv-clone mit Chatterbox Multilingual, MIT-Lizenz).

Protokoll: eine JSON-Zeile pro Auftrag auf stdin
  {"text": "...", "lang": "de", "ref": "/pfad/sample.wav", "out": "/pfad/out.wav"}
Antwort: eine JSON-Zeile auf stdout  {"ok": true} | {"ok": false, "error": "..."}
Das Modell wird einmal geladen und bleibt im Speicher.
"""
import gc
import json
import os
import sys
import time
import warnings

warnings.filterwarnings("ignore")

# Protokoll exklusiv auf dem echten stdout; alles andere (Bibliotheks-Ausgaben) → stderr
PROTO = sys.stdout
sys.stdout = sys.stderr


def _parent_alive(pid: int) -> bool:
    if sys.platform == "win32":
        import ctypes
        k = ctypes.windll.kernel32
        h = k.OpenProcess(0x00100000, False, pid)          # SYNCHRONIZE
        if not h:
            return False
        try:
            return k.WaitForSingleObject(h, 0) == 0x102      # WAIT_TIMEOUT = läuft noch
        finally:
            k.CloseHandle(h)
    if os.getppid() == 1:                                   # Eltern weg → von launchd/init übernommen
        return False
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


def _watch_parent():
    """Sicherheitsnetz: Endet die App ohne Aufräumen (⌘Q, Absturz), beendet sich auch der Worker."""
    import threading
    pid = int(os.environ.get("VORLESER_PARENT_PID") or os.getppid())

    def loop():
        while True:
            time.sleep(2)
            if not _parent_alive(pid):
                log("App beendet – Worker beendet sich")
                os._exit(0)
    threading.Thread(target=loop, daemon=True).start()


def reply(obj):
    PROTO.write(json.dumps(obj) + "\n")
    PROTO.flush()


def log(msg):
    print(f"[clone] {msg}", file=sys.stderr, flush=True)


def _t3_on_cpu(model):
    """Apple-Chip: T3 (erzeugt Sprach-Token einzeln, hunderte winzige Schritte) läuft auf der CPU ~2,5× schneller
    als auf der Grafikeinheit, wo jeder kleine Schritt mehr Verwaltung kostet als er spart. S3Gen (große Blöcke)
    bleibt auf MPS. Gleiche Gewichte, gleiche Genauigkeit (fp32) → gleiche Qualität."""
    t3 = model.t3.to("cpu")
    inference = t3.inference

    def on_cpu(*, t3_cond, text_tokens, **kw):
        return inference(t3_cond=t3_cond.to(device="cpu"), text_tokens=text_tokens.to("cpu"), **kw).to("mps")
    t3.inference = on_cpu
    log("T3 auf CPU, S3Gen auf MPS")


def main():
    import torch
    import torchaudio as ta
    from chatterbox.mtl_tts import ChatterboxMultilingualTTS

    if torch.cuda.is_available():                 # Windows/Linux mit NVIDIA-Grafikkarte
        device = "cuda"
    elif torch.backends.mps.is_available():       # Mac mit Apple-Chip
        device = "mps"
    else:
        device = "cpu"
    # Chatterbox-Gewichte sind teils für CUDA gespeichert → beim Laden auf CPU abbilden
    _orig_load = torch.load
    torch.load = lambda *a, **k: _orig_load(*a, **{**k, "map_location": k.get("map_location") or torch.device("cpu")})
    t0 = time.time()
    try:
        model = ChatterboxMultilingualTTS.from_pretrained(device=device)
    except Exception as e:  # MPS-Probleme → CPU
        log(f"{device} fehlgeschlagen ({e}), nutze CPU")
        device = "cpu"
        model = ChatterboxMultilingualTTS.from_pretrained(device=device)
    if device == "mps":
        _t3_on_cpu(model)
    log(f"Modell geladen auf {device} in {time.time() - t0:.0f}s")
    reply({"ready": True, "device": device})
    cond_key = None                               # Sprachprobe, für die model.conds gerade gilt

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            job = json.loads(line)
            t0 = time.time()
            with torch.inference_mode():
                # Sprachprobe nur aufbereiten, wenn sie neu ist (deterministisch → gleiches Ergebnis, ~5 % schneller)
                st = os.stat(job["ref"])
                key = (job["ref"], st.st_mtime_ns, st.st_size)
                if key != cond_key:
                    cond_key = None
                    model.prepare_conditionals(job["ref"])
                    cond_key = key
                wav = model.generate(job["text"], language_id=job.get("lang", "de"))
                ta.save(job["out"], wav.cpu(), model.sr)
            del wav
            log(f"{len(job['text'])} Zeichen in {time.time() - t0:.1f}s")
            reply({"ok": True})
        except Exception as e:
            reply({"ok": False, "error": f"{type(e).__name__}: {e}"})
            if "out of memory" in str(e).lower():
                log("Speicher voll – Worker beendet sich und wird frisch gestartet")
                return
        finally:
            # Grafikspeicher nach jedem Abschnitt freigeben (sonst wächst er bis zum Absturz)
            gc.collect()
            if device == "mps":
                torch.mps.empty_cache()
            elif device == "cuda":
                torch.cuda.empty_cache()


def download():
    """Nur das Modell laden (~3 GB) – beim Nachinstallieren, damit der erste Klon nicht ewig hängt."""
    # Bewusst NICHT chatterbox importieren: das zieht PyTorch nach und kostet nach frischer Installation
    # über eine Minute, in der „0 MB“ angezeigt würde. Repo-Name wie in chatterbox/mtl_tts.py.
    from huggingface_hub import snapshot_download
    snapshot_download(repo_id="ResembleAI/chatterbox", repo_type="model", revision="main",
                      allow_patterns=["ve.pt", "t3_mtl23ls_v2.safetensors", "s3gen.pt",
                                      "grapheme_mtl_merged_expanded_v1.json", "conds.pt", "Cangjie5_TC.json"])
    reply({"ok": True})


if __name__ == "__main__":
    _watch_parent()
    download() if "--download" in sys.argv else main()
