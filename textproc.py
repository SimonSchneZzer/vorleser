"""Text → Abschnitte: Spracherkennung, Satzzerlegung, Kapitel/Überschriften."""
from __future__ import annotations

import re

LANGS = {"de": "Deutsch", "en": "English"}
DEFAULT_LANG = "de"

TARGET_CHUNK = 350   # angestrebte Zeichen pro Abschnitt
MAX_CHUNK = 600      # harte Obergrenze

# Abkürzungen, nach deren Punkt kein Satzende ist. Einzelbuchstaben ("z. B.", "e.g.",
# Initialen wie "J. R. R. Tolkien") gelten in allen Sprachen als Abkürzung.
ABBREV = {
    "de": {
        "bzw", "ca", "dr", "prof", "nr", "str", "vgl", "evtl", "ggf", "usw", "etc", "inkl",
        "bspw", "hr", "fr", "st", "mio", "mrd", "jh", "abs", "geb", "max", "min", "zb",
        "mr", "mrs", "vs", "sog", "ggü", "zzgl", "bzgl", "jun", "sen", "dipl", "ing", "tel",
    },
    "en": {
        "mr", "mrs", "ms", "dr", "prof", "st", "jr", "sr", "vs", "etc", "approx", "no",
        "fig", "inc", "ltd", "co", "corp", "dept", "est", "vol", "ch", "pp", "ft", "mt",
        "gen", "gov", "sgt", "capt", "col", "lt", "rev", "jan", "feb", "mar", "apr", "jun",
        "jul", "aug", "sep", "sept", "oct", "nov", "dec", "al", "cf", "ave", "blvd",
    },
}
SENT_SPLIT = re.compile(r"(?<=[.!?…])[\"'“”»«)]*\s+")

# Häufige Funktionswörter für eine einfache, schnelle Spracherkennung.
STOPWORDS = {
    "de": set("der die das und ist nicht ein eine einen dem den des zu mit sich auf für von "
              "auch es im wie aber als noch nach bei aus wenn nur oder war wird sind ich sie "
              "wir ihr er dass über so kann hat haben werden dann schon".split()),
    "en": set("the and is are was were of to in that it for with as on be by this have from "
              "at not but or which you he she they we an will would there their what all "
              "been has had can if when who so than into could".split()),
}

# Überschriften: Markdown "# Titel" oder alleinstehende Zeilen wie "Kapitel 3", "Chapter IV: …"
HEADING_MD = re.compile(r"^\s{0,3}#{1,4}\s+(.+?)\s*#*\s*$")
HEADING_WORD = re.compile(
    r"^(kapitel|chapter|teil|part|buch|book|prolog|prologue|epilog|epilogue|vorwort|nachwort|"
    r"preface|foreword|einleitung|introduction|afterword|anhang|appendix)\b.{0,70}$",
    re.IGNORECASE,
)


def detect_language(text: str) -> str:
    words = re.findall(r"[a-zäöüß']+", text[:8000].lower())
    scores = {lang: sum(w in sw for w in words) for lang, sw in STOPWORDS.items()}
    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else DEFAULT_LANG


def clean_inline(s: str) -> str:
    """Markdown-Auszeichnungen entfernen, die nicht vorgelesen werden sollen."""
    s = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", s)                 # Bilder
    s = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", s)              # Links → Linktext
    s = re.sub(r"(\*\*|__)(.+?)\1", r"\2", s)                   # fett
    s = re.sub(r"(?<!\w)([*_])(\S.*?\S|\S)\1(?!\w)", r"\2", s)  # kursiv
    s = re.sub(r"`([^`]*)`", r"\1", s)                          # Code
    s = re.sub(r"^\s*>\s?", "", s)                              # Zitat
    s = re.sub(r"^\s*[-*+]\s+", "", s)                          # Aufzählung
    return s


def split_sentences(par: str, lang: str) -> list[str]:
    abbrev = ABBREV.get(lang, set())
    parts, buf = [], ""
    for piece in SENT_SPLIT.split(par):
        buf = f"{buf} {piece}".strip() if buf else piece.strip()
        last = re.search(r"(\w+)\.$", buf)
        if last:
            word = last.group(1)
            if (
                len(word) == 1 and word.isalpha()           # z. B. / e.g. / Initialen
                or word.lower() in abbrev                   # Dr. / Mr.
                or (lang == "de" and word.isdigit())        # Ordinalzahl "3. Mai" (nur DE)
            ):
                continue
        if buf:
            parts.append(buf)
            buf = ""
    if buf:
        parts.append(buf)
    return parts


def split_long(sentence: str) -> list[str]:
    """Überlange Sätze an Satzzeichen bzw. Leerzeichen kürzen."""
    out = []
    while len(sentence) > MAX_CHUNK:
        window = sentence[:MAX_CHUNK]
        cut = max(window.rfind(", "), window.rfind("; "), window.rfind(": "), window.rfind(" – "))
        if cut < MAX_CHUNK // 3:
            cut = window.rfind(" ")
        if cut <= 0:
            cut = MAX_CHUNK
        out.append(sentence[: cut + 1].strip())
        sentence = sentence[cut + 1 :].strip()
    if sentence:
        out.append(sentence)
    return out


def _blocks(text: str):
    """Liefert ("h", Titel) für Überschriften und ("p", Absatz) für Absätze."""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    par: list[str] = []

    def flush():
        if par:
            joined = re.sub(r"\s+", " ", " ".join(clean_inline(l) for l in par)).strip()
            par.clear()
            if joined:
                single = "\n" not in joined and len(joined) <= 80 and not joined.endswith((".", ",", ";"))
                return ("h", joined) if single and HEADING_WORD.match(joined) else ("p", joined)
        return None

    for line in text.split("\n"):
        m = HEADING_MD.match(line)
        if m or not line.strip():
            b = flush()
            if b:
                yield b
            if m:
                title = clean_inline(m.group(1)).strip()
                if title:
                    yield ("h", title)
            continue
        par.append(line.strip())
    b = flush()
    if b:
        yield b


def chunk_text(text: str, lang: str = DEFAULT_LANG) -> tuple[list[dict], list[dict]]:
    """Zerlegt Text in Abschnitte.

    Rückgabe: (chunks, chapters)
      chunks:   [{text, par, h?}] – par=True: neuer Absatz, h=True: Überschrift
      chapters: [{title, chunk}]  – Index des ersten Abschnitts des Kapitels
    """
    chunks: list[dict] = []
    chapters: list[dict] = []
    for kind, content in _blocks(text):
        if kind == "h":
            chapters.append({"title": content[:120], "chunk": len(chunks)})
            chunks.append({"text": content[:MAX_CHUNK], "par": True, "h": True})
            continue
        cur, first = "", True
        for sent in split_sentences(content, lang):
            for piece in split_long(sent):
                if cur and len(cur) + 1 + len(piece) > TARGET_CHUNK:
                    chunks.append({"text": cur, "par": first})
                    cur, first = piece, False
                else:
                    cur = f"{cur} {piece}" if cur else piece
        if cur:
            chunks.append({"text": cur, "par": first})
    if chapters and chapters[0]["chunk"] > 0:
        chapters.insert(0, {"title": "Anfang", "chunk": 0})
    return chunks, chapters
