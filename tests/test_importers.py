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


def test_pdf_aufraeumen_zaehlt_und_sammelt_fussnoten(monkeypatch):
    """Version 3.0 (Etappe 2): Kopfzeilen, Seitenzahlen, Trennstriche weg – mit Zählung für die Zeile „Aufgeräumt: …“;
    Fußnoten wandern gesammelt ans Kapitelende; das Original bleibt für „Original wiederherstellen“ erhalten."""
    import pypdf
    import importers
    saetze = ["Gregor Samsa erwachte aus unruhigen Träumen.", "Er lag auf seinem harten Rücken.", "Die Beine flimmerten hilflos.",
              "Das Zimmer lag ruhig da.", "Über dem Tisch hing ein Bild.", "Der Regen klopfte an das Fenster."]
    noten = ["Vgl. Brief an den Vater.", "Siehe Tagebücher, Band zwei.", "Erstdruck in Leipzig.", "So in der Handschrift.",
             "Anders bei Brod.", "Gestrichen im Entwurf."]
    worte = ["Aben", "Mor", "Win", "Som", "Früh", "Herb"]
    weiter = ["ging es weiter.", "blieb alles still.", "kam die Schwester.", "rief der Vater.", "fiel Schnee.", "schlief er ein."]
    pages = [f"Die Verwandlung · Kafka\n{saetze[n]} Es wurde {worte[n]}-\nder, und dann {weiter[n]}\n{n + 1} {noten[n]}\n{n + 1}"
             for n in range(6)]

    class P:
        def __init__(self, t): self.t = t
        def extract_text(self): return self.t

    class R:
        is_encrypted = False; outline = []; metadata = None
        def __init__(self, *a): self.pages = [P(p) for p in pages]
    monkeypatch.setattr(pypdf, "PdfReader", R)
    r = importers._pdf(b"x", "test")
    assert r["cleanup"] == {"kopf": 6, "seiten": 6, "getrennt": 6, "fussnoten": 6, "punkte": 0, "tabellen": 0}
    assert "Kafka" not in r["text"] and "Abender" in r["text"]
    assert r["text"].split("\n\n")[-1].startswith("Fußnoten: 1 Vgl. Brief an den Vater.")
    assert "Kafka" in r["original"]


# --------------------------------------------------------------------------- #
# Listen und Sonderzeichen (Rückmeldung 9.11.2026: Aufzählungszeichen wurden als „o“ vorgelesen)
# --------------------------------------------------------------------------- #
def test_listenpunkte_werden_eigene_abschnitte():
    from textproc import chunk_text
    T = ("Einkaufsliste:\n- Äpfel\n- Birnen\n\nSchritte:\n1. Ofen vorheizen\n2. Teig kneten, dann\nin Form bringen.\n3) Backen\n"
         "Danach genießen.\n\no Unterpunkt aus Word\n§ Wingdings-Quadrat\n Symbol-Punkt\nSiehe § 3 Abs. 2.\n\n– Komm her, sagte er.\n\n"
         "| Name | Wert |\n|------|------|\n| A | 1 |\n\nEin Absatz, der in einem PDF über\nmehrere Zeilen umbrochen wurde.")
    texts = [c["text"] for c in chunk_text(T, "de")[0]]
    assert texts == ["Einkaufsliste:", "Äpfel", "Birnen", "Schritte:", "1. Ofen vorheizen", "2. Teig kneten, dann in Form bringen.",
                     "3) Backen", "Danach genießen.", "Unterpunkt aus Word", "Wingdings-Quadrat", "Symbol-Punkt", "Siehe § 3 Abs. 2.",
                     "– Komm her, sagte er.", "Name, Wert", "A, 1", "Ein Absatz, der in einem PDF über mehrere Zeilen umbrochen wurde."]


def test_pdf_listenpunkte_ohne_aufzaehlungszeichen():
    import importers
    seite = "Einleitung zur Liste:\no Erster Punkt\no Zweiter Punkt\n\uf0b7 Dritter Punkt\nDanach geht der normale Text weiter."
    r = importers.pdf_mit_texterkennung(_mini_pdf("x"), "liste", [seite])
    assert "o Erster" not in r["text"] and "- Erster Punkt\n\n- Zweiter Punkt\n\n- Dritter Punkt" in r["text"]
    assert not r["text"].startswith("#")                              # „Einleitung zur Liste:“ ist keine Überschrift
    assert r["cleanup"]["punkte"] == 3


def test_stimme_bekommt_aufbereiteten_text():
    import tts
    assert tts.spoken("Mehr unter https://www.example.com/pfad?x=1. Danke 😀 → jetzt ✓") == "Mehr unter example.com. Danke jetzt"
    assert tts.spoken("z.B. so, d.h. so, u.U. auch") == "zum Beispiel so, das heißt so, unter Umständen auch"
    assert tts.spoken("Die U.S.A. und Version 3.0.1 und test.pdf") == "Die U.S.A. und Version 3.0.1 und test.pdf"
    assert tts.spoken("Zeile ------ | Zelle |") == "Zeile Zelle"


def test_markdown_vollstaendig():
    from textproc import chunk_text
    T = ("# Titel\n\nEin **fetter** und *kursiver* Text mit `code`, ~~weg~~ und [Link](https://x.de).\n\n"
         "Setext\n======\n\nUnter\n-----\n\n##### Ebene fünf\n\n- [ ] offen\n- [x] erledigt\n\n```python\ndef foo():\n    return 1\n```\n\n---\n\n"
         "Fußnote hier[^1] und [Text][1] und <https://auto.link> und <b>HTML</b> und \\*kein fett\\*.\n\n[^1]: Die Fußnote.\n[1]: https://ref.example\n")
    ch, chap = chunk_text(T, "de")
    assert [c["text"] for c in ch] == ["Titel", "Ein fetter und kursiver Text mit code, weg und Link.", "Setext", "Unter", "Ebene fünf",
                                       "offen", "erledigt", "Fußnote hier und Text und https://auto.link und HTML und *kein fett*.",
                                       "Die Fußnote."]
    assert [c["title"] for c in chap] == ["Titel", "Setext", "Unter", "Ebene fünf"]


def test_pdf_fachartikel_tabellen_kopfzeile_abstract():
    """Tester-Rückmeldung (2.x, Fachartikel): Kopfzeile mit wechselnder Seitenzahl, Tabellen mitten im Satz, „Abstract“."""
    import importers
    worte = ["granite", "basalt", "limestone", "sandstone", "marble", "slate"]
    pages = []
    for n in range(6):
        satz = f"This {worte[n]} sentence is a fairly long line of ordinary prose text in the column"
        head = f"{218 + n} D. Stead et al. / Engineering Geology 83 (2006) 217–235" if n % 2 else f"D. Stead et al. / Engineering Geology 83 (2006) 217–235{218 + n}"
        body = [head, f"{satz} number {n} and it goes on", f"{satz} and continues to determine a factor of safety"]
        if n == 0:
            body = [head, "Abstract", "Recent advances in numerical techniques are shown in this paper today."] + body[1:]
        if n == 2:
            body += ["Table 1", "Conventional methods of analysis", "Analysis", "method", "Critical input", "parameters", "Advantages"]
        pages.append("\n".join(body))
    pages[3] = pages[3].replace("This sandstone sentence", "or probability of failure for blocks. This sandstone sentence", 1)
    r = importers.pdf_mit_texterkennung(_mini_pdf("x"), "artikel", pages)
    t = r["text"]
    assert "Engineering Geology" not in t and r["cleanup"]["kopf"] == 6
    assert "# Abstract" in t
    assert "Critical input" not in t and "Table 1 skipped: Conventional methods of analysis" in t and r["cleanup"]["tabellen"] == 1
    assert "factor of safety or probability of failure" in t          # Satz läuft über die Tabelle hinweg weiter
