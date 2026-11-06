"""Dateiimport: TXT, Markdown, HTML, EPUB, PDF."""
import io

import pytest

from importers import ImportFailed, import_file


def test_txt_utf8():
    r = import_file("Notizen.txt", "Grüße aus Köln".encode("utf-8"))
    assert r == {"title": "Notizen", "text": "Grüße aus Köln"}


def test_txt_latin1_wird_erkannt():
    r = import_file("alt.txt", "Grüße".encode("latin-1"))
    assert "Grüße" in r["text"]


def test_markdown():
    r = import_file("buch.md", b"# Titel\n\nText.")
    assert r["title"] == "buch" and r["text"].startswith("# Titel")


def test_html_ueberschriften_und_titel():
    html = b"<html><head><title>Seite</title></head><body><h1>Kapitel A</h1><p>Hallo Welt.</p></body></html>"
    r = import_file("x.html", html)
    assert r["title"] == "Seite"
    assert "# Kapitel A" in r["text"] and "Hallo Welt." in r["text"]


def test_unbekannter_typ():
    with pytest.raises(ImportFailed):
        import_file("bild.png", b"\x89PNG")


def test_epub_mit_kapiteln():
    from ebooklib import epub
    book = epub.EpubBook()
    book.set_identifier("test")
    book.set_title("Mein Buch")
    book.set_language("de")
    c1 = epub.EpubHtml(title="Erstes", file_name="c1.xhtml", lang="de")
    c1.content = "<h1>Erstes</h1><p>Es war einmal ein kleiner Test.</p>"
    c2 = epub.EpubHtml(title="Zweites", file_name="c2.xhtml", lang="de")
    c2.content = "<h1>Zweites</h1><p>Und dann ging es weiter.</p>"
    for c in (c1, c2):
        book.add_item(c)
    book.toc = (c1, c2)
    book.spine = ["nav", c1, c2]
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())
    buf = io.BytesIO()
    epub.write_epub(buf, book)
    r = import_file("buch.epub", buf.getvalue())
    assert r["title"] == "Mein Buch"
    assert "Es war einmal ein kleiner Test." in r["text"]
    assert "Und dann ging es weiter." in r["text"]
    assert r["text"].index("Erstes") < r["text"].index("Zweites")


def _mini_pdf(text: str) -> bytes:
    """Kleinstes gültiges PDF mit einer Textzeile (Helvetica)."""
    stream = f"BT /F1 18 Tf 40 700 Td ({text}) Tj ET".encode()
    objs = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
        b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out, offsets = io.BytesIO(), []
    out.write(b"%PDF-1.4\n")
    for i, o in enumerate(objs, 1):
        offsets.append(out.tell())
        out.write(b"%d 0 obj\n" % i + o + b"\nendobj\n")
    xref = out.tell()
    out.write(b"xref\n0 %d\n0000000000 65535 f \n" % (len(objs) + 1))
    for off in offsets:
        out.write(b"%010d 00000 n \n" % off)
    out.write(b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objs) + 1, xref))
    return out.getvalue()


def test_pdf_text():
    r = import_file("dok.pdf", _mini_pdf("Hallo Welt, dies ist ein PDF-Test mit Text."))
    assert "Hallo Welt" in r["text"]


def test_pdf_ohne_text():
    with pytest.raises(ImportFailed):
        import_file("scan.pdf", _mini_pdf(""))


def test_kaputtes_pdf():
    with pytest.raises(ImportFailed):
        import_file("kaputt.pdf", b"%PDF-1.4 kaputt")
