"""Dateien → Text mit Kapitelüberschriften ("# Titel"), den textproc.chunk_text versteht."""
from __future__ import annotations

import io
import re
import os
import tempfile
import warnings
from collections import Counter
from pathlib import Path

from textproc import HEADING_WORD
from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning

warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)
warnings.filterwarnings("ignore", category=UserWarning, module="ebooklib")
warnings.filterwarnings("ignore", category=FutureWarning, module="ebooklib")

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


def _decode(data: bytes) -> str:
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


def _epub(data: bytes, stem: str) -> dict:
    from ebooklib import ITEM_DOCUMENT, epub

    # Datei erst schließen, dann lesen: Windows erlaubt kein zweites Öffnen einer offenen Temp-Datei
    fd, tmp = tempfile.mkstemp(suffix=".epub", prefix="vorleser-")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
        book = epub.read_epub(tmp, options={"ignore_ncx": False})
    except Exception as e:
        raise ImportFailed(f"EPUB konnte nicht gelesen werden: {e}") from e
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
def _pdf(data: bytes, stem: str) -> dict:
    from pypdf import PdfReader

    try:
        reader = PdfReader(io.BytesIO(data))
        if reader.is_encrypted:
            reader.decrypt("")
        pages = [(p.extract_text() or "") for p in reader.pages]
    except Exception as e:
        raise ImportFailed(f"PDF konnte nicht gelesen werden: {e}") from e
    if sum(len(p.strip()) for p in pages) < 20:
        raise ImportFailed("Das PDF enthält keinen Text (vermutlich eingescannt – dafür wäre OCR nötig)")

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

    # Kopf-/Fußzeilen erkennen: Zeilen, die auf über der Hälfte der Seiten vorkommen
    def key(line):
        return re.sub(r"\d+", "#", line.strip())
    counts = Counter(k for p in pages for k in {key(l) for l in p.split("\n") if l.strip()})
    repeated = {k for k, n in counts.items() if len(pages) >= 4 and n > len(pages) / 2}

    lines_all = [l.strip() for p in pages for l in p.split("\n") if l.strip()]
    lens = sorted(len(l) for l in lines_all) or [80]
    typical = lens[int(len(lens) * 0.8)]

    out: list[str] = []
    cur = ""
    for pg, page in enumerate(pages):
        if pg in marks:
            if cur:
                out.append(cur)
                cur = ""
            out.extend(f"# {t}" for t in marks[pg])
        for line in page.split("\n"):
            s = line.strip()
            if not s or PAGE_NO.fullmatch(s) or key(s) in repeated:
                continue
            if len(s) <= 80 and HEADING_WORD.match(s) and not s.endswith((".", ",")):
                if cur:
                    out.append(cur)
                    cur = ""
                out.append(f"# {s}")                      # "Kapitel 3" als eigene Überschrift
                continue
            if cur.endswith("-") and s[:1].islower():
                cur = cur[:-1] + s                       # Silbentrennung zusammenfügen
            else:
                cur = f"{cur} {s}" if cur else s
            # Absatzende: Satzzeichen am Ende einer deutlich kürzeren Zeile
            if re.search(r"[.!?:\"”»“]$", s) and len(s) < typical * 0.85:
                out.append(cur)
                cur = ""
    if cur:
        out.append(cur)

    meta_title = None
    try:
        meta_title = reader.metadata.title if reader.metadata else None
    except Exception:
        pass
    return {"title": _norm(meta_title) if meta_title and _norm(meta_title) else stem,
            "text": "\n\n".join(out)}
