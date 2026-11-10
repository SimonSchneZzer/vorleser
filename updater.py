"""Updates für die Desktop-App: neue Version erkennen, laden und mit einem Klick installieren.

Quelle ist das neueste Release im öffentlichen Repo vorleser-download (feste Dateinamen).
Installiert wird von einem kleinen Helfer, der wartet, bis die App beendet ist:
  macOS:   DMG einhängen, Vorleser.app austauschen, neu starten
  Windows: Setup still ausführen (Inno Setup), danach neu starten
Teil-Update (meist ~15 MB statt ~260 MB): nur die geänderten Dateien laden (packaging/make_patch.py). Jede andere
Datei wird per Prüfsumme gegen die Dateiliste der neuen Version geprüft; passt etwas nicht → komplettes Paket.
Was die App selbst lädt, bekommt kein Quarantäne-/Internet-Kennzeichen → keine Sicherheitswarnung.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

import paths

REPO = "SimonSchneZzer/vorleser-download"
API_URL = os.environ.get("VORLESER_UPDATE_URL", f"https://api.github.com/repos/{REPO}/releases/latest")
PAGE_URL = "https://simonschnezzer.github.io/vorleser-download/"
# Ausweichweg ohne API (kein Ratenlimit von 60/h pro IP): die Release-Seite leitet auf /tag/vX.Y.Z weiter
LATEST_PAGE = os.environ.get("VORLESER_UPDATE_PAGE", f"https://github.com/{REPO}/releases/latest")
# Hauptweg: kleine Datei auf der Download-Seite (GitHub Pages, kein Ratenlimit). Der Release-Workflow schreibt sie
# erst, wenn die Installer hochgeladen sind. Die API (60 Anfragen/h pro IP) ist nur noch Ausweichweg.
JSON_URL = os.environ.get("VORLESER_UPDATE_JSON", PAGE_URL + "latest.json")
ASSET = "Vorleser-mac.dmg" if paths.IS_MAC else "Vorleser-windows-setup.exe" if paths.IS_WIN else None
CHECK_EVERY = 60                       # Sekunden – latest.json kostet nichts
API_EVERY = 3600                       # Ausweichweg über die API höchstens stündlich (außer „Jetzt suchen“)
UPDATES_DIR = paths.USER_DIR / "updates"
LAST_VERSION_FILE = paths.DATA_DIR / "last-version"

_lock = threading.Lock()
_state: dict = {"state": "idle"}      # idle | downloading | ready (geladen + vorbereitet) | installing | error
_ready: dict | None = None             # {"version", "installer", "staged"} – wartet auf Neustart oder Beenden
_checked_once = False                  # erste Prüfung nach dem Start abgeschlossen (Oberfläche wartet darauf)
_latest: dict | None = None
_checked = 0.0
_api_tried = 0.0
_just_updated: str | None = None


def _ver(v: str) -> tuple:
    return tuple(int(x) for x in re.findall(r"\d+", v or "")[:3]) or (0,)


def _app_path() -> Path | None:
    """Das laufende App-Paket (macOS) bzw. die Vorleser.exe (Windows)."""
    if not paths.FROZEN:
        return None
    exe = Path(sys.executable).resolve()
    if paths.IS_MAC:
        return exe.parents[2] if exe.parents[2].suffix == ".app" else None
    return exe


def can_install() -> tuple[bool, str]:
    """Kann sich die App selbst ersetzen? Sonst Grund (→ Download-Seite öffnen)."""
    if not paths.FROZEN or ASSET is None:
        return False, "Nur in der installierten App"
    app = _app_path()
    if app is None:
        return False, "App-Ordner nicht gefunden"
    s = str(app)
    if paths.IS_MAC and ("AppTranslocation" in s or s.startswith("/Volumes/")):
        return False, "Bitte Vorleser zuerst in den Ordner Programme ziehen"
    if not os.access(app.parent, os.W_OK):
        return False, "Keine Schreibrechte im App-Ordner"
    return True, ""


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **kw):
        return None


def _check_via_redirect() -> dict | None:
    """Neueste Version aus der Weiterleitung der Release-Seite (ohne API, ohne Release-Notizen)."""
    opener = urllib.request.build_opener(_NoRedirect)
    req = urllib.request.Request(LATEST_PAGE, method="HEAD", headers={"User-Agent": "Vorleser-Updater"})
    try:
        opener.open(req, timeout=15)
        return None                                   # keine Weiterleitung → kein Release
    except urllib.error.HTTPError as e:
        loc = e.headers.get("Location") or ""
        if e.code not in (301, 302, 303, 307, 308) or "/tag/" not in loc:
            return None
    tag = loc.rstrip("/").rsplit("/tag/", 1)[1]
    url = LATEST_PAGE.replace("/releases/latest", f"/releases/download/{tag}/{ASSET}")
    head = urllib.request.Request(url, method="HEAD", headers={"User-Agent": "Vorleser-Updater"})
    with urllib.request.urlopen(head, timeout=15) as r:      # existiert die Datei für dieses System?
        size = int(r.headers.get("Content-Length") or 0)
    return {"version": tag.lstrip("v"), "url": url, "size": size, "notes": "", "page": PAGE_URL}


def _check_via_json() -> dict | None:
    """Neueste Version aus latest.json. Pages leert seinen CDN-Zwischenspeicher bei jeder Veröffentlichung;
    ?t= (je Minute) schützt zusätzlich vor Zwischenspeichern unterwegs (Proxys)."""
    url = f"{JSON_URL}?t={int(time.time() // 60)}"
    req = urllib.request.Request(url, headers={"User-Agent": "Vorleser-Updater", "Cache-Control": "no-cache"})
    with urllib.request.urlopen(req, timeout=15) as r:
        data = json.loads(r.read())
    asset = (data.get("assets") or {}).get(ASSET)
    if not asset or not data.get("version"):
        return None
    return {"version": str(data["version"]).lstrip("v"), "url": asset["url"], "size": asset.get("size") or 0,
            "notes": (data.get("notes") or "").strip()[:600], "page": data.get("page") or PAGE_URL,
            "patch": asset.get("patch"), "sha256": asset.get("sha256")}


def check(force: bool = False) -> dict | None:
    """Neuestes Release abfragen (höchstens alle paar Minuten, außer force)."""
    try:
        return _check(force)
    finally:
        global _checked_once
        _checked_once = True


def _check(force: bool = False) -> dict | None:
    global _latest, _checked, _api_tried
    now = time.time()
    if ASSET is None or (not force and now - _checked < 50):
        return _latest
    _checked = now
    try:
        found = _check_via_json()
        if found and (not _latest or found["version"] != _latest["version"]):
            print(f"[update] neueste Version {found['version']} (installiert {paths.APP_VERSION})", flush=True)
        if found:
            _latest = found
        return _latest
    except Exception as e:
        print(f"[update] latest.json nicht erreichbar ({type(e).__name__})", flush=True)
    if not force and now - _api_tried < API_EVERY:
        return _latest
    _api_tried = now
    try:
        req = urllib.request.Request(API_URL, headers={"Accept": "application/vnd.github+json",
                                                       "User-Agent": "Vorleser-Updater"})
        with urllib.request.urlopen(req, timeout=15) as r:
            rel = json.loads(r.read())
        asset = next((a for a in rel.get("assets", []) if a.get("name") == ASSET), None)
        if rel.get("draft") or rel.get("prerelease") or not asset:
            return _latest
        notes = (rel.get("body") or "").strip()
        _latest = {"version": rel["tag_name"].lstrip("v"), "url": asset["browser_download_url"],
                   "size": asset.get("size") or 0, "notes": notes[:600], "page": rel.get("html_url") or PAGE_URL}
        print(f"[update] neueste Version {_latest['version']} (installiert {paths.APP_VERSION})", flush=True)
    except Exception as e:
        print(f"[update] API nicht nutzbar ({type(e).__name__}) – versuche Release-Seite", flush=True)
        try:
            found = _check_via_redirect()
            if found:
                _latest = found
                print(f"[update] neueste Version {found['version']} (über Release-Seite)", flush=True)
        except Exception as e2:
            print(f"[update] Prüfen fehlgeschlagen: {type(e2).__name__}", flush=True)
    return _latest


def status() -> dict:
    latest = _latest
    ok, why = can_install()
    available = bool(latest and _ver(latest["version"]) > _ver(paths.APP_VERSION))
    patch = _patch_for(latest)
    with _lock:
        return {**_state, "current": paths.APP_VERSION, "latest": latest["version"] if latest else None,
                "available": available, "notes": latest["notes"] if latest else "",
                "size": (patch or latest)["size"] if latest else 0, "partial": bool(patch),
                "canInstall": ok, "reason": why, "page": PAGE_URL, "justUpdated": _just_updated, "checked": _checked_once,
                "readyVersion": _ready["version"] if _ready else None,
                "enabled": paths.FROZEN or bool(os.environ.get("VORLESER_UPDATE_URL"))}


def _patch_for(latest: dict | None) -> dict | None:
    """Teil-Update, wenn es für die installierte Version gebaut wurde (sonst komplettes Paket)."""
    p = (latest or {}).get("patch") or None
    ok = p and p.get("url") and paths.APP_VERSION in (p.get("from") or []) and paths.FROZEN and not os.environ.get("VORLESER_NO_PATCH")
    if ok and latest and latest.get("version") and _failed_marker(latest["version"]).exists():   # Windows-Helfer meldete Fehler → komplettes Paket
        return None
    return p if ok else None


RETRY_WAIT = (2, 5)                    # Sekunden zwischen den Versuchen je Weg (504 o. Ä. ist meist kurz)
MSG_SERVER = "GitHub ist gerade nicht erreichbar. Versuch es in ein paar Minuten noch einmal."
MSG_OFFLINE = "Keine Internetverbindung. Versuch es noch einmal, sobald du online bist."
MSG_OTHER = "Das Update ließ sich nicht vorbereiten. Versuch es noch einmal oder lade die neue Version von der Webseite."


def _transient(e: Exception) -> bool:
    """Lohnt ein neuer Versuch? Serverfehler (5xx), 429 und Netzwerkfehler ja – 404 o. Ä. nicht."""
    if isinstance(e, urllib.error.HTTPError):
        return e.code >= 500 or e.code == 429
    return isinstance(e, (urllib.error.URLError, TimeoutError, ConnectionError))


class _NoUpdate(RuntimeError):
    pass


def _user_error(e: Exception) -> str:
    """Feste, übersetzbare Meldung für die Update-Karte (Details stehen im Log)."""
    if isinstance(e, _NoUpdate):
        return str(e)
    if isinstance(e, urllib.error.HTTPError):
        return MSG_SERVER if _transient(e) else MSG_OTHER
    if isinstance(e, urllib.error.URLError) and isinstance(e.reason, socket.gaierror):
        return MSG_OFFLINE                                 # Name nicht auflösbar → kein Netz
    return MSG_SERVER if _transient(e) else MSG_OTHER


def _api_asset_url(version: str, name: str) -> str | None:
    """Ausweichweg, wenn github.com selbst hakt (z. B. 504 einer Region): dieselbe Datei über die API.
    Die API leitet direkt auf den Datei-Server weiter und läuft über andere Server als die Webseite."""
    req = urllib.request.Request(f"https://api.github.com/repos/{REPO}/releases/tags/v{version}",
                                 headers={"Accept": "application/vnd.github+json", "User-Agent": "Vorleser-Updater"})
    with urllib.request.urlopen(req, timeout=15) as r:
        rel = json.loads(r.read())
    a = next((a for a in rel.get("assets", []) if a.get("name") == name), None)
    return a and a.get("url")


def _download(latest: dict, url: str | None = None, size: int | None = None, name: str = ASSET or "") -> Path:
    """Laden mit Wiederholung; scheitert der normale Link an Server-/Netzfehlern, über die GitHub-API."""
    url = url or latest["url"]
    try:
        return _download_retry(latest, url, size, name, {})
    except Exception as e:
        if not _transient(e) or "github.com/" not in url:
            raise
        print(f"[update] {url.rsplit('/', 1)[-1]} über github.com nicht ladbar ({e}) – versuche GitHub-API", flush=True)
        try:
            api = _api_asset_url(latest["version"], url.rsplit("/", 1)[-1])
        except Exception as e2:
            print(f"[update] API nicht erreichbar ({e2})", flush=True)
            raise e from None
        if not api:
            raise
        return _download_retry(latest, api, size, name, {"Accept": "application/octet-stream"})


def _download_retry(latest: dict, url: str, size: int | None, name: str, headers: dict) -> Path:
    for wait in (*RETRY_WAIT, None):
        try:
            return _download_once(latest, url, size, name, headers)
        except Exception as e:
            if wait is None or not _transient(e):
                raise
            print(f"[update] Laden fehlgeschlagen ({e}) – neuer Versuch in {wait} s", flush=True)
            time.sleep(wait)


def _download_once(latest: dict, url: str, size: int | None, name: str, headers: dict) -> Path:
    UPDATES_DIR.mkdir(parents=True, exist_ok=True)
    size = latest["size"] if size is None else size
    dest = UPDATES_DIR / f"{latest['version']}-{name}"
    if dest.exists() and (not size or dest.stat().st_size == size):
        return dest
    part = dest.with_suffix(dest.suffix + ".part")
    req = urllib.request.Request(url, headers={"User-Agent": "Vorleser-Updater", **headers})
    with _lock:                                   # Karte: „Verbindung wird hergestellt …“, noch keine MB-Zahl
        _state.update(connected=False, done=0, total=0)
    with urllib.request.urlopen(req, timeout=60) as r, open(part, "wb") as f:
        total = int(r.headers.get("Content-Length") or size or 0)
        done = 0
        with _lock:                               # erst jetzt steht die Größe fest – sie ändert sich nicht mehr
            _state.update(connected=True, done=0, total=total)
        while chunk := r.read(1 << 20):
            f.write(chunk)
            done += len(chunk)
            with _lock:
                _state.update(done=done, total=total)
    if size and part.stat().st_size != size:
        part.unlink(missing_ok=True)
        raise RuntimeError("Download unvollständig")
    part.replace(dest)
    return dest


def _sha256(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        while b := f.read(1 << 20):
            h.update(b)
    return h.hexdigest()


def _install_root() -> Path:
    """Ordner, auf den sich die Dateiliste bezieht: Vorleser.app (macOS) bzw. der Programmordner (Windows)."""
    app = _app_path()
    return app if paths.IS_MAC else app.parent


def _keep_on_windows(rel: str) -> bool:
    return "/" not in rel and rel.lower().startswith("unins")       # Deinstallationsprogramm von Inno Setup


def _apply_patch(zpath: Path, root: Path, target: Path, version: str) -> list[str]:
    """Neue Version in target zusammensetzen: geänderte Dateien aus dem Paket, alle anderen müssen in root
    (bzw. der Kopie target) schon mit der richtigen Prüfsumme liegen. Gibt die zu löschenden Pfade zurück.
    macOS: target = Kopie des ganzen Pakets (wird danach gegen die alte getauscht).
    Windows: target = Ordner nur mit den neuen Dateien (der Helfer kopiert sie nach dem Beenden drüber)."""
    with zipfile.ZipFile(zpath) as z:
        man = json.loads(z.read("manifest.json"))
        if man.get("version") != version:
            raise RuntimeError("Teil-Update passt nicht zur Version")
        files: dict = man["files"]
        names = set(z.namelist())
        for rel, f in files.items():
            dst = target / rel
            if "l" in f:                                          # Verknüpfung (nur macOS)
                if not (dst.is_symlink() and os.readlink(dst) == f["l"]):
                    if dst.is_symlink() or dst.exists():
                        dst.unlink() if not dst.is_dir() or dst.is_symlink() else shutil.rmtree(dst)
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    os.symlink(f["l"], dst)
                continue
            if "files/" + rel in names:
                dst.parent.mkdir(parents=True, exist_ok=True)
                if dst.is_symlink():
                    dst.unlink()
                with z.open("files/" + rel) as src, open(dst.with_name(dst.name + ".tmp"), "wb") as out:
                    shutil.copyfileobj(src, out, 1 << 20)
                dst.with_name(dst.name + ".tmp").replace(dst)
                check = dst
            else:
                check = root / rel                                # unverändert → muss schon so daliegen
                if paths.IS_MAC:
                    check = dst
                if check.is_symlink() or not check.is_file() or check.stat().st_size != f["s"]:
                    raise RuntimeError(f"Datei weicht ab: {rel}")
            if _sha256(check) != f["h"]:
                raise RuntimeError(f"Prüfsumme falsch: {rel}")
            if paths.IS_MAC:
                mode = check.stat().st_mode
                os.chmod(check, (mode | 0o111) if f.get("x") else (mode & ~0o111))
    # Dateien, die es in der neuen Version nicht mehr gibt
    gone = []
    base = target if paths.IS_MAC else root
    for dirpath, dirnames, filenames in os.walk(base):
        d = Path(dirpath)
        for n in dirnames + filenames:
            p = d / n
            rel = p.relative_to(base).as_posix()
            if (p.is_symlink() or p.is_file()) and rel not in files and not rel.endswith(".tmp"):
                if not (paths.IS_WIN and _keep_on_windows(rel)):
                    gone.append(rel)
        dirnames[:] = [n for n in dirnames if not (d / n).is_symlink()]
    if paths.IS_MAC:
        for rel in gone:
            (target / rel).unlink(missing_ok=True)
    return gone


def _prepare_patch(latest: dict, patch: dict) -> dict:
    """Teil-Update laden und vollständig vorbereiten – schlägt etwas fehl, nimmt _prepare das komplette Paket."""
    zpath = _download(latest, patch["url"], patch.get("size") or 0, f"patch-{'mac' if paths.IS_MAC else 'windows'}.zip")
    with _lock:
        _state.update(state="preparing")
    root = _install_root()
    if paths.IS_MAC:
        staged = root.with_name(root.name + ".new")
        subprocess.run(["rm", "-rf", str(staged)], check=False)
        # APFS: Kopie per Klon (sofort, kein Platz); sonst normal kopieren
        if subprocess.run(["cp", "-cR", str(root), str(staged)], capture_output=True).returncode != 0:
            subprocess.run(["rm", "-rf", str(staged)], check=False)
            subprocess.run(["ditto", str(root), str(staged)], check=True, timeout=600)
        try:
            _apply_patch(zpath, root, staged, latest["version"])
        except Exception:
            subprocess.run(["rm", "-rf", str(staged)], check=False)
            raise
        subprocess.run(["xattr", "-cr", str(staged)], check=False)
        return {"staged": str(staged)}
    staged = UPDATES_DIR / f"staged-{latest['version']}"
    shutil.rmtree(staged, ignore_errors=True)
    staged.mkdir(parents=True)
    try:
        gone = _apply_patch(zpath, root, staged, latest["version"])
    except Exception:
        shutil.rmtree(staged, ignore_errors=True)
        raise
    (UPDATES_DIR / f"delete-{latest['version']}.txt").write_text("\n".join(gone), "utf-8")
    return {"staged": str(staged), "patch": True}


def _ps(s) -> str:
    return str(s).replace("'", "''")          # für PowerShell-Strings in '…'


def _stage_mac(installer: Path, app: Path) -> Path:
    """DMG schon VOR dem Neustart einhängen und die neue App neben die alte kopieren – beim Neustart bleibt
    nur noch ein Umbenennen (sofort statt DMG prüfen + 450 MB kopieren nach dem Beenden)."""
    staged = app.with_name(app.name + ".new")
    mnt = Path(subprocess.check_output(["mktemp", "-d", "/tmp/vorleser-update.XXXXXX"], text=True).strip())
    try:
        subprocess.run(["hdiutil", "attach", "-nobrowse", "-readonly", "-noautoopen", "-noverify",
                        "-mountpoint", str(mnt), str(installer)], check=True, capture_output=True, timeout=180)
        subprocess.run(["rm", "-rf", str(staged)], check=False)
        subprocess.run(["ditto", str(mnt / "Vorleser.app"), str(staged)], check=True, timeout=600)
        subprocess.run(["xattr", "-cr", str(staged)], check=False)
    finally:
        subprocess.run(["hdiutil", "detach", str(mnt), "-quiet"], check=False)
        subprocess.run(["rmdir", str(mnt)], check=False)
    return staged


def _launch_helper(relaunch: bool) -> None:
    """Helfer starten, der nach dem Beenden der App das vorbereitete Update einspielt (und ggf. neu startet)."""
    app, pid, log = _app_path(), os.getpid(), paths.DATA_DIR / "update.log"
    if paths.IS_MAC:
        staged = Path(_ready["staged"])
        script = UPDATES_DIR / "install.sh"
        script.write_text(f"""#!/bin/bash
exec >>"{log}" 2>&1
echo "== $(date) Update auf {_ready['version']} (Neustart: {'ja' if relaunch else 'nein'})"
while kill -0 {pid} 2>/dev/null; do sleep 0.1; done
if [ -d "{staged}" ]; then
  rm -rf "{app}.old"
  if mv "{app}" "{app}.old"; then
    if mv "{staged}" "{app}"; then
      echo "installiert"
      rm -rf "{app}.old" &
    else
      rm -rf "{app}"                       # evtl. halb kopiert – dann die bisherige Version zurück
      mv "{app}.old" "{app}" && echo "Tausch fehlgeschlagen – bisherige Version wiederhergestellt"
    fi
  fi
fi
{f'open "{app}"' if relaunch else ''}
""", "utf-8")
        script.chmod(0o755)
        subprocess.Popen(["/bin/bash", str(script)], start_new_session=True,
                         stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    elif paths.IS_WIN:
        _launch_win_helper(app, pid, log, relaunch)


# Windows-Helfer (3.0.2, neu nach Rückmeldung David: 2.10.3 → 3.0.1 wurde nie eingespielt, App kam nicht wieder).
# Als eigene .ps1-Datei (UTF-8 mit BOM – sonst liest Windows PowerShell 5 Umlaute in Pfaden falsch), schreibt sofort ins
# Log, löst sich aus dem Job der App (sonst beendet Windows ihn mit), wartet höchstens 60 s auf das Ende der App,
# beendet Reste aus dem App-Ordner (z. B. ffmpeg, sperren Dateien), sichert ersetzte Dateien und stellt sie bei einem
# Fehler wieder her, startet die App in jedem Fall neu. Teil-Update gescheitert → Merker → nächstes Mal komplettes Paket.
# Geprüft auf echtem Windows: .github/workflows/windows-update.yml (packaging/test_update_windows.py).
_PS_HEAD = """$ErrorActionPreference = 'Continue'
$log = '{L}'
function L($m) {{ try {{ Add-Content -LiteralPath $log -Value ('[' + (Get-Date -Format s) + '] ' + $m) }} catch {{}} }}
L 'Helfer gestartet: Update auf {V} ({kind}, Neustart: {re})'
try {{
  $p = Get-Process -Id {pid} -ErrorAction SilentlyContinue
  if ($p -and -not $p.WaitForExit(60000)) {{ L 'App beendet sich nicht - wird beendet'; Stop-Process -Id {pid} -Force -ErrorAction SilentlyContinue; Start-Sleep -Seconds 1 }}
  Get-Process -ErrorAction SilentlyContinue | Where-Object {{ $_.Path -and $_.Path.StartsWith('{R}\\', 'OrdinalIgnoreCase') }} | ForEach-Object {{ L ('beende ' + $_.Name); Stop-Process -Id $_.Id -Force -ErrorAction SilentlyContinue }}
  Start-Sleep -Milliseconds 500
"""
_PS_PATCH = """  $S = '{S}'; $R = '{R}'; $B = '{B}'
  L ('Quelle da: ' + (Test-Path -LiteralPath $S) + ', Ziel da: ' + (Test-Path -LiteralPath $R))
  Remove-Item -LiteralPath $B -Recurse -Force -ErrorAction SilentlyContinue
  Get-ChildItem -LiteralPath $S -Recurse -File | ForEach-Object {{
    $rel = $_.FullName.Substring($S.Length + 1); $old = Join-Path $R $rel
    if (Test-Path -LiteralPath $old) {{ $dst = Join-Path $B $rel; New-Item -ItemType Directory -Force -Path (Split-Path $dst) | Out-Null; Copy-Item -LiteralPath $old -Destination $dst -Force }}
  }}
  $rc = 16
  for ($i = 0; $i -lt 3 -and $rc -ge 8; $i++) {{
    $out = robocopy $S $R /E /R:10 /W:1 /NFL /NDL /NP 2>&1; $rc = $LASTEXITCODE; L ('robocopy: ' + $rc)
    if ($rc -ge 8) {{ $out | Where-Object {{ $_ -match 'ERROR|FEHLER|Fehler|\\S' }} | Select-Object -Last 12 | ForEach-Object {{ L ('  ' + $_) }}; Start-Sleep -Seconds 2 }}
  }}
  if ($rc -lt 8) {{
    Get-Content -LiteralPath '{D}' -ErrorAction SilentlyContinue | ForEach-Object {{ if ($_) {{ Remove-Item -LiteralPath (Join-Path $R $_) -Force -ErrorAction SilentlyContinue }} }}
    foreach ($h in 'HKCU:','HKLM:') {{ $k = $h + '\\Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\{{6E1B7C52-4D0A-4C1E-9F43-7A8C2B9D0E11}}_is1'; if (Test-Path $k) {{ Set-ItemProperty -Path $k -Name DisplayVersion -Value '{V}' -ErrorAction SilentlyContinue }} }}
    Remove-Item -LiteralPath $S -Recurse -Force -ErrorAction SilentlyContinue
    L 'installiert'
  }} else {{
    if (Test-Path -LiteralPath $B) {{ robocopy $B $R /E /R:10 /W:1 /NFL /NDL /NJH /NJS /NP | Out-Null; L ('wiederhergestellt: ' + $LASTEXITCODE) }}
    Set-Content -LiteralPath '{F}' -Value 'robocopy' -ErrorAction SilentlyContinue
    L 'Teil-Update fehlgeschlagen - naechstes Mal komplettes Paket'
  }}
  Remove-Item -LiteralPath $B -Recurse -Force -ErrorAction SilentlyContinue
"""
_PS_SETUP = """  $p = Start-Process -FilePath '{I}' -ArgumentList '/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART','/NOCANCEL' -Wait -PassThru
  L ('Setup beendet: ' + $p.ExitCode)
"""
_PS_TAIL = """}} catch {{ L ('Fehler: ' + $_) }}
finally {{
{relaunch}}}
"""


def _launch_win_helper(app: Path, pid: int, log: Path, relaunch: bool) -> None:
    ver, patch = _ready["version"], bool(_ready.get("patch"))
    R = app.parent
    f = dict(L=_ps(log), V=_ps(ver), pid=pid, R=_ps(R), kind="Teil-Update" if patch else "Setup", re="ja" if relaunch else "nein")
    body = (_PS_PATCH.format(S=_ps(_ready["staged"]), R=_ps(R), B=_ps(UPDATES_DIR / f"backup-{ver}"),
                             D=_ps(UPDATES_DIR / f"delete-{ver}.txt"), F=_ps(_failed_marker(ver)), V=_ps(ver))
            if patch else _PS_SETUP.format(I=_ps(_ready["installer"])))
        # relaunch: in jedem Fall (auch nach Fehler) – sonst steht der Nutzer ohne App da
    tail = _PS_TAIL.format(relaunch=(f"  L 'starte Vorleser'\n  Start-Process -FilePath '{_ps(app)}' -WorkingDirectory '{_ps(R)}' -WindowStyle Normal\n"
                                     if relaunch else "  L 'fertig'\n"))
    script = UPDATES_DIR / f"install-{ver}.ps1"
    UPDATES_DIR.mkdir(parents=True, exist_ok=True)
    script.write_text(_PS_HEAD.format(**f) + body + tail, "utf-8-sig")
    _log_line(log, f"[app] starte Helfer ({f['kind']} auf {ver}, Neustart: {f['re']})")
    args = ["powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-WindowStyle", "Hidden",
            "-File", str(script)]
    # KEIN DETACHED_PROCESS: Windows PowerShell braucht eine Konsole und beendet sich ohne sofort – genau das war der
    # Fehler bis 3.0.1 (auf echtem Windows nachgestellt: Helfer schrieb keine einzige Zeile). CREATE_NO_WINDOW gibt ihm
    # eine eigene, unsichtbare Konsole; NEW_PROCESS_GROUP trennt ihn von Strg+C der App.
    base = 0x00000200 | 0x08000000                           # CREATE_NEW_PROCESS_GROUP | CREATE_NO_WINDOW
    for flags in (base | 0x01000000, base):                  # + CREATE_BREAKAWAY_FROM_JOB (nicht überall erlaubt)
        try:
            proc = subprocess.Popen(args, creationflags=flags, close_fds=True,
                                    stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except OSError as e:
            if flags & 0x01000000:
                continue
            _log_line(log, f"[app] Helfer ließ sich nicht starten: {e!r}")
            raise
        if not flags & 0x01000000:
            _log_line(log, "[app] Helfer ohne Lösen aus dem Job gestartet")
        _await_helper(proc, log)
        return


def _await_helper(proc, log: Path, wait: float = 5.0) -> None:
    """Kurz prüfen, ob der Helfer sich meldet – sonst steht im Log wenigstens, dass (und wie) er nicht lief."""
    end = time.time() + wait
    while time.time() < end:
        try:
            if "Helfer gestartet" in log.read_text("utf-8", errors="replace")[-2000:]:
                return
        except OSError:
            pass
        if proc.poll() is not None:
            _log_line(log, f"[app] Helfer sofort beendet (Code {proc.returncode})")
            return
        time.sleep(0.1)
    _log_line(log, "[app] Helfer meldet sich nicht (läuft aber)")

def _failed_marker(version: str) -> Path:
    return UPDATES_DIR / f"failed-{version}.txt"


def _log_line(log: Path, text: str) -> None:
    try:
        log.parent.mkdir(parents=True, exist_ok=True)
        with open(log, "a", encoding="utf-8") as f:
            f.write(f"[{time.strftime('%Y-%m-%dT%H:%M:%S')}] {text}\n")
    except OSError:
        pass


def _prepare() -> None:
    """Laden und vorbereiten – die App läuft dabei normal weiter."""
    global _ready
    try:
        latest = check(force=True)
        if not latest or _ver(latest["version"]) <= _ver(paths.APP_VERSION):
            raise _NoUpdate("Keine neuere Version gefunden")
        patch = _patch_for(latest)
        if patch:
            try:
                info = _prepare_patch(latest, patch)
                _ready = {"version": latest["version"], "installer": None, **info}
                with _lock:
                    _state.update(state="ready")
                print(f"[update] {latest['version']} bereit (Teil-Update, {patch.get('size', 0) // 1_000_000} MB)", flush=True)
                return
            except Exception as e:
                if _transient(e):                 # Server/Netz hakt → das große Paket käme vom selben Server
                    raise
                print(f"[update] Teil-Update nicht möglich ({e}) – lade komplettes Paket", flush=True)
                with _lock:
                    _state.update(state="downloading", connected=False, done=0, total=0)
        installer = _download(latest)
        with _lock:
            _state.update(state="preparing")
        if latest.get("sha256") and _sha256(installer) != latest["sha256"]:   # ab 3.0.2 in latest.json; ältere ohne
            installer.unlink(missing_ok=True)         # beschädigt → beim nächsten Versuch neu laden, nie einspielen
            raise RuntimeError("Prüfsumme des Updates stimmt nicht")
        staged = str(_stage_mac(installer, _app_path())) if paths.IS_MAC else None
        _ready = {"version": latest["version"], "installer": str(installer), "staged": staged}
        with _lock:
            _state.update(state="ready")
        print(f"[update] {latest['version']} bereit – startet beim Neustart oder beim nächsten Öffnen", flush=True)
    except Exception as e:
        print(f"[update] Fehler: {e}", flush=True)
        with _lock:
            _state.update(state="error", error=_user_error(e))


def install(quit_app=None) -> dict:
    """Update laden und vorbereiten (Neustart erst auf Wunsch – oder beim Beenden)."""
    ok, why = can_install()
    if not ok:
        raise ValueError(why)
    with _lock:
        if _state["state"] in ("downloading", "preparing", "ready", "installing"):
            return dict(_state)
        _state.clear()
        _state.update(state="downloading", connected=False, done=0, total=0)   # Größe erst, wenn der Server antwortet
    threading.Thread(target=_prepare, daemon=True).start()
    return status()


def restart_now(quit_app) -> dict:
    """„Jetzt neu starten“: Helfer los, App beenden – das Austauschen dauert nur einen Moment."""
    if not _ready:
        raise ValueError("Kein Update bereit")
    with _lock:
        _state.update(state="installing")
    print(f"[update] Neustart in {_ready['version']}", flush=True)
    _launch_helper(relaunch=True)
    threading.Timer(0.3, quit_app).start()
    return status()


def install_on_exit() -> None:
    """Beim Beenden: ein bereitliegendes Update einspielen – beim nächsten Öffnen läuft die neue Version."""
    if _ready and _state.get("state") == "ready":
        with _lock:
            _state.update(state="installing")          # _cleanup läuft mehrfach (closing/closed/atexit) → nur einmal
        print(f"[update] {_ready['version']} wird beim Beenden eingespielt", flush=True)
        _launch_helper(relaunch=False)


def start_background() -> None:
    """Beim Start: „gerade aktualisiert?“ merken, alte Downloads löschen, regelmäßig prüfen."""
    global _just_updated
    try:
        prev = LAST_VERSION_FILE.read_text("utf-8").strip()
    except OSError:
        prev = ""
    if prev and _ver(prev) < _ver(paths.APP_VERSION):
        _just_updated = paths.APP_VERSION
    LAST_VERSION_FILE.write_text(paths.APP_VERSION, "utf-8")
    # Aufräumen läuft im Hintergrund nach Stimmenliste + Offline-Stimme – wurde schon ein Update vorbereitet (früher
    # Klick auf „Aktualisieren“), dessen Dateien nicht löschen (auf echtem Windows nachgestellt, 10.11.2026).
    with _lock:
        busy = _state.get("state") in ("downloading", "preparing", "ready", "installing")
    if UPDATES_DIR.exists() and not busy:
        for p in UPDATES_DIR.iterdir():
            if paths.APP_VERSION in p.name or p.suffix == ".part" or p.name.startswith(("staged-", "backup-")):
                shutil.rmtree(p, ignore_errors=True) if p.is_dir() else p.unlink(missing_ok=True)

    app = _app_path() if paths.IS_MAC and paths.FROZEN else None
    if app and app.with_name(app.name + ".new").exists():      # Rest eines abgebrochenen Updates (~450 MB)
        subprocess.Popen(["rm", "-rf", str(app.with_name(app.name + ".new"))], **paths.NO_WINDOW)

    def loop():
        time.sleep(1)                       # bei jedem Start kurz nach dem Öffnen prüfen
        check(force=True)
        while True:
            time.sleep(CHECK_EVERY)
            check()
    if status()["enabled"]:
        threading.Thread(target=loop, daemon=True).start()
