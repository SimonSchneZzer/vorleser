"""Dateien → Text mit Kapitelüberschriften ("# Titel"), den textproc.chunk_text versteht."""
from __future__ import annotations

import io
import re
import os
import tempfile
import warnings
from collections import Counter
from pathlib import Path

from textproc import HEADING_WORD, detect_language, list_item
from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning

warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)
warnings.filterwarnings("ignore", category=UserWarning, module="ebooklib")
warnings.filterwarnings("ignore", category=FutureWarning, module="ebooklib")

FOOTNOTE = re.compile(r"^\d{1,3}\s+(?![\d.])[^\s]")
PAGE_NO = re.compile(r"[-–\s]*(?:seite|page|s\.)?\s*\d{1,4}(?:\s*(?:/|von|of)\s*\d{1,4})?[-–\s]*", re.I)
BLOCK_TAGS = ["h1", "h2", "h3", "h4", "h5", "h6", "p", "li", "blockquote", "pre", "dt", "dd"]


class ImportFailed(Exception):
    pass


def import_file(filename: str, data: bytes) -> dict:
    ext = Path(filename).suffix.lower()
    stem = Path(filename).stem
    if ext == ".epub":
        return _epub(data, stem)
    if ext == ".pdf":
        return _pdf(data, stem)
    if ext in (".html", ".htm", ".xhtml"):
        title, text = _html_to_text(data, headings_as_chapters=True)
        return {"title": title or stem, "text": text}
    if ext in (".txt", ".md", ".markdown", ".text", ""):
        return {"title": stem, "text": _decode(data)}
    raise ImportFailed(f"Dateityp {ext} wird nicht unterstützt (EPUB, PDF, TXT, MD, HTML)")


PDF_GESCHUETZT = ("Das PDF ist geschützt und lässt sich nicht lesen – speichere es ohne Schutz "
                  "(z. B. „Drucken › Als PDF sichern“) und importiere es erneut.")
PDF_KAPUTT = "Das PDF konnte nicht gelesen werden – die Datei ist vermutlich beschädigt."
EPUB_KAPUTT = "Das EPUB konnte nicht gelesen werden – die Datei ist vermutlich beschädigt oder kopiergeschützt."


def _decode(data: bytes) -> str:
    if data[:2] in (b"\xff\xfe", b"\xfe\xff"):          # UTF-16 mit BOM (Windows-Editor „Unicode“)
        return data.decode("utf-16", errors="replace")
    if len(data) > 8 and data[:200].count(0) > len(data[:200]) // 4:   # UTF-16 ohne BOM: jedes 2. Byte 0
        try:
            return data.decode("utf-16-le" if data[1] == 0 else "utf-16-be")
        except UnicodeDecodeError:
            pass
    for enc in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


# --------------------------------------------------------------------------- #
# HTML / EPUB
# --------------------------------------------------------------------------- #
def _html_blocks(html: bytes | str):
    soup = BeautifulSoup(html, "html.parser")
    for t in soup(["script", "style", "sup", "nav", "aside"]):
        t.decompose()
    title = _norm(soup.title.get_text()) if soup.title else ""
    body = soup.body or soup
    blocks = []
    for el in body.find_all(BLOCK_TAGS):
        if el.find_parent(BLOCK_TAGS):        # verschachtelt → schon im Elternblock enthalten
            continue
        text = _norm(el.get_text(" "))
        if text:
            blocks.append((el.name, text))
    if not blocks:                             # Fallback: reiner Text
        for line in body.get_text("\n").split("\n"):
            if _norm(line):
                blocks.append(("p", _norm(line)))
    return title, blocks


def _html_to_text(data, headings_as_chapters: bool) -> tuple[str, str]:
    title, blocks = _html_blocks(data)
    out = []
    for tag, text in blocks:
        text = text.lstrip("#").strip()
        if headings_as_chapters and tag in ("h1", "h2"):
            out.append(f"# {text}")
        else:
            out.append(text)
    return title, "\n\n".join(out)


# --------------------------------------------------------------------------- #
# Link → Artikel (Version 3.0, Link-Reiter). Ohne neue Abhängigkeit: BeautifulSoup + eine einfache Lese-Heuristik.
# --------------------------------------------------------------------------- #
LINK_UNGUELTIG = "Das ist kein gültiger Link – er sollte mit https:// beginnen."
LINK_NICHT_LADBAR = "Die Seite ließ sich nicht laden – stimmt der Link, und bist du online?"
LINK_NICHT_GEFUNDEN = "Die Seite wurde nicht gefunden – stimmt der Link?"
LINK_KEIN_TEXT = ("Auf der Seite wurde kaum Text gefunden – vielleicht liegt er hinter einer Bezahlschranke oder Anmeldung. "
                  "Tipp: den Text im Browser markieren und per Tastenkürzel vorlesen lassen (Einstellungen › App).")
_JUNK = re.compile(r"cookie|consent|newsletter|share|social|comment|related|promo|advert|banner|subscribe|paywall|"
                   r"breadcrumb|sidebar|footer|navigation|navbar|menu|popup|modal|teaser-list|recommend", re.I)


def _fetch(url: str) -> tuple[bytes, str]:
    import urllib.error
    import urllib.request
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Vorleser",
        "Accept": "text/html,application/xhtml+xml", "Accept-Language": "de,en;q=0.8"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            data = r.read(10_000_001)
            charset = r.headers.get_content_charset() or ""
    except urllib.error.HTTPError as e:
        print(f"[link] {url}: HTTP {e.code}", flush=True)
        raise ImportFailed(LINK_NICHT_GEFUNDEN if e.code in (404, 410) else
                           LINK_KEIN_TEXT if e.code in (401, 402, 403) else LINK_NICHT_LADBAR) from e
    except Exception as e:
        print(f"[link] {url}: {e!r}", flush=True)
        raise ImportFailed(LINK_NICHT_LADBAR) from e
    if len(data) > 10_000_000:
        raise ImportFailed(LINK_KEIN_TEXT)
    return data, charset


def _article_root(soup):
    """Bereich mit dem eigentlichen Artikel: <article>/<main> mit dem meisten Absatztext, sonst der Block mit dem
    meisten direkten <p>-Text (klassische Lese-Heuristik)."""
    ptext = lambda el: sum(len(_norm(p.get_text(" "))) for p in el.find_all("p"))
    cands = soup.find_all(["article", "main"]) or []
    best = max(cands, key=ptext, default=None)
    if best is not None and ptext(best) > 300:
        return best
    scores = {}
    for p in soup.find_all("p"):
        par = p.parent
        if par is not None:
            scores[id(par)] = (scores.get(id(par), (par, 0))[0], scores.get(id(par), (par, 0))[1] + len(_norm(p.get_text(" "))))
    return max(scores.values(), key=lambda x: x[1])[0] if scores else (soup.body or soup)


def import_url(url: str) -> dict:
    from urllib.parse import urlparse
    url = (url or "").strip()
    u = urlparse(url)
    if u.scheme not in ("http", "https") or not u.netloc:
        raise ImportFailed(LINK_UNGUELTIG)
    data, charset = None, ""
    # Seiten mit Raute-Pfad (z. B. orf.at/#/stories/3447805/): der Teil nach # geht nie an den Server – geladen wurde
    # die Startseite mit allen Schlagzeilen. Erst die Adresse ohne Raute versuchen, sonst wie bisher (Simon, 3.0.4).
    frag = u.fragment.removeprefix("!")
    if frag.startswith("/") and len(frag) > 1:
        try:
            data, charset = _fetch(f"{u.scheme}://{u.netloc}{frag}")
        except ImportFailed:
            data = None
    if data is None:
        data, charset = _fetch(url)
    html = data.decode(charset, errors="replace") if charset else data
    soup = BeautifulSoup(html, "html.parser")
    og = soup.find("meta", property="og:title")
    for t in soup(["script", "style", "noscript", "nav", "aside", "header", "footer", "form", "figure", "iframe",
                   "svg", "button", "sup", "template"]):
        t.decompose()
    for t in soup.find_all(True):
        if t.attrs is None:
            continue
        attrs = " ".join([t.get("id") or "", " ".join(t.get("class") or []), t.get("role") or ""])
        if attrs.strip() and _JUNK.search(attrs) and t.name not in ("body", "html", "article", "main"):
            t.decompose()
    root = _article_root(soup)
    h1 = root.find("h1") or soup.find("h1")
    title = _norm(og["content"]) if og and og.get("content") else _norm(h1.get_text(" ")) if h1 else \
        _norm(soup.title.get_text()) if soup.title else u.netloc
    title = re.split(r"\s+[|–—-]\s+[^|–—-]{2,40}$", title)[0] or title       # „Titel | Zeitung“ → „Titel“
    out = []
    for el in root.find_all(BLOCK_TAGS):
        if el.find_parent(BLOCK_TAGS):
            continue
        text = _norm(el.get_text(" "))
        if not text or (el.name == "h1" and _norm(text) == title):
            continue
        out.append(f"# {text}" if el.name in ("h2", "h3") else text)
    text = "\n\n".join(out)
    if len(text) < 400:
        raise ImportFailed(LINK_KEIN_TEXT)
    return {"title": title[:160], "text": text, "source": u.netloc.removeprefix("www.")}


def _epub(data: bytes, stem: str) -> dict:
    from ebooklib import ITEM_DOCUMENT, epub

    # Datei erst schließen, dann lesen: Windows erlaubt kein zweites Öffnen einer offenen Temp-Datei
    fd, tmp = tempfile.mkstemp(suffix=".epub", prefix="vorleser-")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
        book = epub.read_epub(tmp, options={"ignore_ncx": False})
    except Exception as e:
        print(f"[import] EPUB: {e!r}", flush=True)
        raise ImportFailed(EPUB_KAPUTT) from e
    finally:
        try:
            os.unlink(tmp)
        except OSError:
            pass

    # Inhaltsverzeichnis: Datei → Titel des ersten Eintrags
    toc: dict[str, str] = {}

    def walk(items):
        for it in items:
            if isinstance(it, tuple):           # (Section, [Kinder])
                sec, kids = it
                if getattr(sec, "href", None) and sec.title:
                    toc.setdefault(sec.href.split("#")[0], _norm(sec.title))
                walk(kids)
            elif getattr(it, "href", None) and getattr(it, "title", None):
                toc.setdefault(it.href.split("#")[0], _norm(it.title))
    walk(book.toc)

    titles = book.get_metadata("DC", "title")
    title = _norm(titles[0][0]) if titles else stem
    out: list[str] = []
    for idref, _ in book.spine:
        item = book.get_item_with_id(idref)
        if item is None or item.get_type() != ITEM_DOCUMENT or isinstance(item, epub.EpubNav):
            continue
        _, blocks = _html_blocks(item.get_content())
        if not blocks:
            continue
        name = item.get_name()
        chap = toc.get(name) or next((v for k, v in toc.items() if k.endswith("/" + name) or name.endswith("/" + k)), None)
        if chap:
            out.append(f"# {chap}")
        for tag, text in blocks:
            text = text.lstrip("#").strip()
            if chap and tag.startswith("h") and text.lower() == chap.lower():
                continue                         # Überschrift doppelt (TOC + Text)
            if not toc and tag in ("h1", "h2"):  # kein TOC → Überschriften sind Kapitel
                out.append(f"# {text}")
            else:
                out.append(text)
    text = "\n\n".join(out).strip()
    if not text:
        raise ImportFailed("Im EPUB wurde kein Text gefunden")
    return {"title": title, "text": text}


# --------------------------------------------------------------------------- #
# PDF
# --------------------------------------------------------------------------- #
class BrauchtTexterkennung(ImportFailed):
    """PDF ohne Textebene (eingescannt) → Texterkennung nötig (Version 3.0, `ocr.py`)."""
    def __init__(self, pages: int):
        super().__init__(PDF_SCAN)
        self.pages = pages


PDF_SCAN = "Das PDF enthält keinen Text – es ist vermutlich eingescannt."


def pdf_mit_texterkennung(data: bytes, stem: str, pages: list[str]) -> dict:
    """Wie ein normales PDF aufräumen, nur mit den erkannten Seitentexten."""
    return _pdf(data, stem, pages)


TABLE_CAP = re.compile(r"^(?:Table|Tabelle|Tab\.)\s*(\d+)[.:]?\s*(.*)$")
SECTION_WORD = re.compile(r"^(?:\d+(?:\.\d+)*\.?\s*)?(abstract|zusammenfassung|kurzfassung|summary|references|literatur|"
                          r"literaturverzeichnis|bibliography|quellen|quellenverzeichnis)$", re.I)


def _title_start(line_nk: str, title_nk: str) -> bool:
    """Ist diese Zeile der Anfang der Lesezeichen-Überschrift? (Nummer davor egal, Titel darf über mehrere Zeilen gehen)"""
    line_nk = re.sub(r"^\d+", "", line_nk)
    return len(line_nk) >= min(8, len(title_nk)) and title_nk.startswith(line_nk)


def _pdf(data: bytes, stem: str, ocr_pages: list[str] | None = None) -> dict:
    from pypdf import PdfReader

    try:
        reader = PdfReader(io.BytesIO(data))
        if reader.is_encrypted:
            try:                                          # nur Besitzer-Passwort → leeres Passwort öffnet es
                ok = reader.decrypt("")
            except Exception as e:                        # z. B. AES ohne Krypto-Paket
                print(f"[import] PDF verschlüsselt: {e!r}", flush=True)
                ok = 0
            if not ok:
                raise ImportFailed(PDF_GESCHUETZT)
        pages = ocr_pages if ocr_pages is not None else [(p.extract_text() or "") for p in reader.pages]
    except ImportFailed:
        raise
    except Exception as e:
        print(f"[import] PDF: {e!r}", flush=True)
        raise ImportFailed(PDF_KAPUTT) from e
    if sum(len(p.strip()) for p in pages) < 20:
        if ocr_pages is not None:
            raise ImportFailed("Auch die Texterkennung hat auf den Seiten keinen Text gefunden.")
        raise BrauchtTexterkennung(len(pages))

    # Kapitel aus den Lesezeichen (zwei Ebenen)
    marks: dict[int, list[str]] = {}

    def walk(items, depth=0):
        for it in items:
            if isinstance(it, list):
                if depth < 1:
                    walk(it, depth + 1)
                continue
            try:
                pg = reader.get_destination_page_number(it)
                if it.title and _norm(it.title):
                    marks.setdefault(pg, []).append(_norm(it.title))
            except Exception:
                pass
    try:
        walk(reader.outline)
    except Exception:
        pass

    # Kopf-/Fußzeilen erkennen: Zeilen, die auf über der Hälfte der Seiten vorkommen. Zahlen und Leerzeichen zählen nicht –
    # die Seitenzahl steht mal links, mal rechts, mal angeklebt („…217–235218“ / „…217–235 225“, Tester-Rückmeldung)
    def key(line):
        return re.sub(r"\s+", "", re.sub(r"\d+", "#", line.strip())).strip("#")
    counts = Counter(k for p in pages for k in {key(l) for l in p.split("\n") if l.strip()})
    repeated = {k for k, n in counts.items() if k and len(pages) >= 4 and n > len(pages) / 2}

    lines_all = [l.strip() for p in pages for l in p.split("\n") if l.strip()]
    lens = sorted(len(l) for l in lines_all) or [80]
    typical = lens[int(len(lens) * 0.8)]

    out: list[str] = []
    cur = ""
    stats = {"kopf": 0, "seiten": 0, "getrennt": 0, "fussnoten": 0, "punkte": 0, "tabellen": 0}
    in_item = False
    notes: list[str] = []                         # Fußnoten des laufenden Kapitels → ans Kapitelende (Simon, F11)

    def flush_notes():
        if notes:
            out.append("Fußnoten: " + " · ".join(notes))
            notes.clear()

    en = detect_language(" ".join(pages[:3])[:4000]) == "en"
    later: list[str] = []                          # Tabellen-Hinweise: erst nach dem laufenden Absatz (Satz nicht zerreißen)

    def push(par: str) -> None:
        out.append(par)
        if later:
            out.extend(later)
            later.clear()

    def nk(s: str) -> str:
        return re.sub(r"[^\w]+", "", s.lower())

    for pg, page in enumerate(pages):
        lines = [l.strip() for l in page.split("\n")]
        # Kapitel aus den Lesezeichen dort einfügen, wo die Überschrift auf der Seite steht (nicht am Seitenanfang –
        # sonst steht sie mitten in einem Satz, Tester-Rückmeldung). Nicht gefunden → wie bisher am Seitenanfang.
        pending, title_rest = [], ""
        if pg in marks:
            starts = [t for t in marks[pg] if not any(_title_start(nk(l), nk(t)) for l in lines)]
            pending = [t for t in marks[pg] if t not in starts]
            if starts:
                if cur:
                    push(cur)
                    cur = ""
                flush_notes()
                out.extend(f"# {t}" for t in starts)
        # Fußnoten: Block am Seitenende, beginnt mit „Zahl Leerzeichen Text“ (ohne Punkt – „1.“ wäre eine Liste)
        body_end = len(lines)
        tail = [i for i, l in enumerate(lines) if l and not PAGE_NO.fullmatch(l) and key(l) not in repeated]
        for i in reversed(tail[-6:]):
            if FOOTNOTE.match(lines[i]) and i > len(lines) * 0.5:
                body_end = i
        for l in lines[body_end:]:
            if l and PAGE_NO.fullmatch(l):
                stats["seiten"] += 1
            elif l and key(l) in repeated:
                stats["kopf"] += 1
            if l and not PAGE_NO.fullmatch(l) and key(l) not in repeated:
                if FOOTNOTE.match(l) or not notes:
                    notes.append(l)
                    stats["fussnoten"] += 1 if FOOTNOTE.match(l) else 0
                else:
                    notes[-1] += " " + l
        skip = 0
        for idx, line in enumerate(lines[:body_end]):
            s = line
            if skip:
                skip -= 1
                continue
            if not s:
                continue
            if PAGE_NO.fullmatch(s):
                stats["seiten"] += 1
                continue
            if key(s) in repeated:
                stats["kopf"] += 1
                continue
            if title_rest:                                # mehrzeilige Überschrift: Folgezeilen gehören dazu
                n = nk(s)
                if n and title_rest.startswith(n):
                    title_rest = title_rest[len(n):]
                    continue
                title_rest = ""
            if pending and _title_start(nk(s), nk(pending[0])):
                t = pending.pop(0)
                if cur:
                    push(cur)
                    cur = ""
                flush_notes()
                out.append(f"# {t}")
                title_rest = nk(t)[len(nk(re.sub(r"^\d+(\.\d+)*\.?\s*", "", s))):]
                continue
            if len(s) <= 80 and (HEADING_WORD.match(s) or SECTION_WORD.match(s)) and not s.endswith((".", ",", ":")):
                if cur:
                    push(cur)
                    cur = ""
                flush_notes()
                out.append(f"# {re.sub(r'^\d+(\.\d+)*\.?\s*', '', s)}")   # „Kapitel 3“, „Abstract“ als eigene Überschrift
                continue
            tm = TABLE_CAP.match(s)
            if tm:                                        # Tabelle: kurze Zellen-Zeilen bis zur nächsten normalen Zeile
                cap = tm.group(2).strip()
                j = idx + 1
                if not cap and j < body_end and lines[j]:
                    cap, j = lines[j], j + 1
                k = j
                while k < body_end and lines[k] and len(lines[k]) < typical * 0.8 and key(lines[k]) not in repeated:
                    k += 1
                if k - j >= 4:
                    num = tm.group(1)
                    later.append((f"Table {num} skipped" if en else f"Tabelle {num} übersprungen") + (f": {cap}" if cap else "."))
                    stats["tabellen"] += 1
                    skip = k - idx - 1
                    continue
            item = list_item(s)                          # Listenpunkt (auch „o“/„§“/ aus Word) → eigener Absatz, als „- …“
            if item is not None:
                if cur:
                    push(cur)
                cur, in_item = (item if item == s.strip() else f"- {item}"), True   # nummeriert bleibt, Aufzählung → „- “
                stats["punkte"] += 1
                continue
            if in_item and cur and not s[:1].islower() and len(cur) < typical * 0.85 and not cur.endswith((",", "-")):
                push(cur)                                # kurzer Punkt fertig, danach normaler Text
                cur = ""
            in_item = False if not cur else in_item
            if cur.endswith("-") and s[:1].islower():
                cur = cur[:-1] + s                       # Silbentrennung zusammenfügen
                stats["getrennt"] += 1
            else:
                cur = f"{cur} {s}" if cur else s
            # Absatzende: Satzzeichen am Ende einer deutlich kürzeren Zeile
            if re.search(r"[.!?:\"”»“]$", s) and len(s) < typical * 0.85:
                push(cur)
                cur = ""
        if pending:                                       # auf der Seite gefunden, aber nicht erreicht → nicht verlieren
            if cur:
                push(cur)
                cur = ""
            out.extend(f"# {t}" for t in pending)
    if cur:
        push(cur)
    out.extend(later)
    flush_notes()

    meta_title = None
    try:
        meta_title = reader.metadata.title if reader.metadata else None
    except Exception:
        pass
    raw = "\n\n".join(p.strip() for p in pages if p.strip())     # Original (für „Original wiederherstellen“)
    title = _norm(meta_title) if meta_title else ""
    if not title or re.match(r"(doi:|\d|untitled|microsoft word|.*\.(pdf|docx?)$)", title, re.I):
        first = next((t for pg in sorted(marks) for t in marks[pg]), None)   # DOI/Dateiname als Titel → Inhaltsverzeichnis
        title = first or stem
    return {"title": title,
            "text": "\n\n".join(out), "cleanup": stats, "original": raw}
