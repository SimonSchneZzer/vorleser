"""Einstellungen (Validierung) und Pfade (Entwicklung vs. App)."""
import re
import paths
import settings


def test_datenordner_ist_testordner(home):
    assert paths.USER_DIR == home
    assert paths.DATA_DIR == home / "data" and paths.CACHE_DIR == home / "cache"
    assert not paths.FROZEN


def test_version_aus_datei():
    assert paths.APP_VERSION == (paths.APP_DIR / "VERSION").read_text().strip()


def test_klon_umgebung_entwicklung():
    assert paths.CLONE_ENV.name == ".venv-clone"
    env = paths.clone_env()
    assert env["PYTHONUTF8"] == "1"
    assert env.get("HF_HOME") == __import__("os").environ.get("HF_HOME")   # nur die App setzt eigenen Modellordner


def test_standardwerte():
    s = settings.load()
    assert s["theme"] == "system" and s["mark"] == "word"
    assert s["favorites"]                                      # Vorschlag statt leer


def test_update_validiert():
    s = settings.update({"theme": "neon", "mark": "sentence", "accent": "#0f6a80", "cacheMB": 1,
                         "favorites": ["a", "b", "a"], "unbekannt": 1})
    assert s["theme"] != "neon"                               # ungültig → ignoriert
    assert s["mark"] == "sentence"
    assert s["accent"] == "#0F6A80"                           # normalisiert
    assert s["cacheMB"] != 1                                  # außerhalb 50–100000
    assert s["favorites"] == ["a", "b"]                       # ohne Doppelte
    assert "unbekannt" not in settings.load()
    settings.update({"mark": "word"})


def test_standardstimmen_werden_gemischt():
    settings.update({"defaultVoices": {"de": "edge:x"}})
    s = settings.update({"defaultVoices": {"en": "edge:y"}})
    assert s["defaultVoices"] == {"de": "edge:x", "en": "edge:y"}
    settings.update({"defaultVoices": {"de": "", "en": ""}})


# --------------------------------------------------------------------------- #
# Fehler melden
# --------------------------------------------------------------------------- #
def test_fehlerbericht_info(home):
    import bugreport
    log = paths.LOG_FILE
    log.write_text(
        '127.0.0.1 - - "GET /api/voices HTTP/1.1" 200 -\n'
        f'[edge] Fehler in {paths.USER_DIR.home()}/Library/Vorleser\n'
        '[piper] lade Stimme x\n', "utf-8")
    i = bugreport.info()
    assert i["enabled"] and i["key"] and i["endpoint"].startswith("https://")
    assert i["version"] == paths.APP_VERSION and i["system"]
    assert "GET /api" not in i["log"]                         # Seitenabrufe raus
    assert str(paths.USER_DIR.home()) not in i["log"] and "~/Library" in i["log"]   # Benutzerpfad anonymisiert
    assert not re.search(r"[\w.+-]+@[\w-]+\.\w+", repr(i))     # keine E-Mail-Adresse (Empfänger) in der App
    log.unlink()


def test_fehlerbericht_wiederholungen_zusammengefasst():
    import bugreport
    lines = ["[edge] 57 Online-Stimmen geladen"] + [f"[edge] 56 Zeichen in 1.0{i}s" for i in range(10)] + \
            ["[piper] lade Stimme x", "[edge] 55 Zeichen in 1.2s", "[edge] 55 Zeichen in 1.1s"]
    out = bugreport.collapse(lines)
    assert out == ["[edge] 57 Online-Stimmen geladen", "[edge] 56 Zeichen in 1.09s  (×10)",
                   "[piper] lade Stimme x", "[edge] 55 Zeichen in 1.1s  (×2)"]


def test_vorladen_einstellung():
    assert settings.load()["ahead"] == "normal"
    assert settings.update({"ahead": "all"})["ahead"] == "all"
    assert settings.update({"ahead": "unendlich"})["ahead"] == "all"   # ungültig → bleibt
    settings.update({"ahead": "normal"})
