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
HEADING_MD = re.compile(r"^\s{0,3}#{1,6}\s+(.+?)\s*#*\s*$")
SETEXT = re.compile(r"^\s{0,3}(=+|-+)\s*$")                 # Unterstreichung: Zeile darüber ist Überschrift (--- allein = Linie)
FENCE = re.compile(r"^\s{0,3}(```|~~~)")
MD_DEF = re.compile(r"^\s{0,3}\[[^\]]+\]:\s+\S+\s*$")       # [1]: https://… (Referenz-Link-Ziel) – nicht vorlesen
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


# Listenpunkte am Zeilenanfang. Aus PDFs kommen Word-Aufzählungszeichen oft als „o“ (2. Ebene), „§“ (Wingdings ▪) oder
# Zeichen aus dem privaten Unicode-Bereich (, ) – sonst liest die Stimme „o“ vor (Tester-Rückmeldung 9.11.2026).
# „–“/„—“ bewusst nicht: Gedankenstrich am Zeilenanfang ist in Romanen die wörtliche Rede.
BULLET = re.compile(r"^\s*(?:[-*+•◦▪▫■□●○◆◇►▶➢➤✓✔✗‣⁃·\uf000-\uf0ff]|o(?=\s+\S)|§(?=\s+[^\d\s]))\s+")
NUMBERED = re.compile(r"^\s*(?:\d{1,3}[.)]|[a-zA-Z]\)|\(\d{1,3}\))\s+\S")
TABLE_ROW = re.compile(r"^\s*\|.*\|\s*$")


def list_item(line: str) -> str | None:
    """Listenpunkt → Text ohne Aufzählungszeichen (Nummer bleibt); sonst None."""
    m = BULLET.match(line)
    if m:
        return line[m.end():].strip()
    if NUMBERED.match(line):
        return line.strip()
    return None


def table_row(line: str) -> str | None:
    """Markdown-Tabellenzeile → „Zelle, Zelle“; Trennzeile (|---|) → ""; sonst None."""
    if not TABLE_ROW.match(line):
        return None
    cells = [c.strip() for c in line.strip().strip("|").split("|")]
    if all(re.fullmatch(r":?-{2,}:?", c) or not c for c in cells):
        return ""
    return ", ".join(c for c in cells if c)


def clean_inline(s: str) -> str:
    """Markdown-Auszeichnungen entfernen, die nicht vorgelesen werden sollen."""
    # Escapes (\*) zuerst wegsperren, damit fett/kursiv sie nicht als Auszeichnung nehmen; am Ende zurück als Zeichen
    s = re.sub(r"\\([\\`*_{}\[\]()#+\-.!~|>])", lambda m: chr(0xF0000 + ord(m.group(1))), s)
    s = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", s)                 # Bilder
    s = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", s)              # Links → Linktext
    s = re.sub(r"(\*\*|__)(.+?)\1", r"\2", s)                   # fett
    s = re.sub(r"(?<!\w)([*_])(\S.*?\S|\S)\1(?!\w)", r"\2", s)  # kursiv
    s = re.sub(r"`([^`]*)`", r"\1", s)                          # Code
    s = re.sub(r"~~(.+?)~~", r"\1", s)                         # durchgestrichen
    s = re.sub(r"^\s*\[\^[^\]]+\]:\s*", "", s)                    # Fußnote „[^1]: …“ → nur der Text
    s = re.sub(r"\[\^[^\]]+\]", "", s)                           # Verweis [^1] im Text
    s = re.sub(r"\[([^\]]+)\]\[[^\]]*\]", r"\1", s)              # Referenz-Link [Text][1]
    s = re.sub(r"<((?:https?://|mailto:)[^>\s]+)>", r"\1", s)     # Autolink <https://…>
    s = re.sub(r"</?[a-zA-Z][a-zA-Z0-9]*(?:\s[^<>]*)?/?>", "", s)  # einfache HTML-Tags
    s = re.sub(r"^\s*\[[ xX]\]\s+", "", s)                       # Aufgabe [ ] / [x]
    s = re.sub(r"^\s*>\s?", "", s)                              # Zitat
    s = re.sub(r"^\s*[-*+]\s+", "", s)                          # Aufzählung
    s = re.sub("[\U000F0000-\U000F00FF]", lambda m: chr(ord(m.group(0)) - 0xF0000), s)   # Escapes zurück
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

    def flush(kind="p"):
        if par:
            joined = re.sub(r"\s+", " ", " ".join(clean_inline(l) for l in par)).strip()
            par.clear()
            if joined:
                if kind != "p":                    # Listenpunkt: „b“ Aufzählung, „n“ nummeriert (Nummer steht im Text)
                    return (kind, joined)
                single = "\n" not in joined and len(joined) <= 80 and not joined.endswith((".", ",", ";", ":"))
                return ("h", joined) if single and HEADING_WORD.match(joined) else ("p", joined)
        return None

    def split_items(lines):
        """Absatz-Zeilen in Fließtext + Listenpunkte/Tabellenzeilen trennen – jeder Punkt eigener Block (Pause)."""
        out, cur, kind = [], [], "p"              # out: [(art, zeilen)] – art: p | b (Aufzählung) | n (nummeriert)
        for l in lines:
            row = table_row(l)
            if row is not None:                    # Tabellenzeile steht für sich, Trennzeile fällt weg
                if cur:
                    out.append((kind, cur))
                cur, kind = [], "p"
                if row:
                    out.append(("p", [row]))
                continue
            item = list_item(l)
            if item is not None:
                if cur:
                    out.append((kind, cur))
                cur, kind = [item], ("n" if NUMBERED.match(l) else "b")
                continue
            if kind != "p" and cur:               # Folgezeile eines Punkts – oder schon wieder normaler Text?
                prev = cur[-1]
                wrapped = (l[:1].islower() or prev.endswith((",", "-", "–", "(")) or
                           (len(prev) >= 50 and not re.search(r"[.!?:]$", prev)))
                if not wrapped:
                    out.append((kind, cur))
                    cur, kind = [], "p"
            cur.append(l)
        if cur:
            out.append((kind, cur))
        return out

    def flush_all():
        lines = par[:]
        par.clear()
        for kind, group in split_items(lines):
            par.extend(group)
            b = flush(kind)
            if b:
                yield b

    fenced = False
    for line in text.split("\n"):
        if FENCE.match(line):                  # Code-Block: nicht vorlesen
            fenced = not fenced
            yield from flush_all()
            continue
        if fenced or MD_DEF.match(line):
            continue
        st = SETEXT.match(line)
        if st and line.strip() not in ("-", "="):
            if len(par) == 1 and not list_item(par[0]):   # „Titel\n=====“ → Überschrift
                title = clean_inline(par.pop()).strip()
                if title:
                    yield ("h", title)
                continue
            if not par and len(line.strip()) >= 3:      # --- allein = Trennlinie
                continue
        m = HEADING_MD.match(line)
        if m or not line.strip():
            yield from flush_all()
            if m:
                title = clean_inline(m.group(1)).strip()
                if title:
                    yield ("h", title)
            continue
        par.append(line.strip())
    yield from flush_all()


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
        li = {"li": kind} if kind in ("b", "n") else {}       # Listenpunkt → im Lesetext mit Punkt/Einzug
        for sent in split_sentences(content, lang):
            for piece in split_long(sent):
                if cur and len(cur) + 1 + len(piece) > TARGET_CHUNK:
                    chunks.append({"text": cur, "par": first, **(li if first else {})})
                    cur, first = piece, False
                else:
                    cur = f"{cur} {piece}" if cur else piece
        if cur:
            chunks.append({"text": cur, "par": first, **(li if first else {})})
    if chapters and chapters[0]["chunk"] > 0:
        chapters.insert(0, {"title": "Anfang", "chunk": 0})
    return chunks, chapters
