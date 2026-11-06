"""Text → Abschnitte: Spracherkennung, Satzgrenzen, Kapitel."""
from textproc import MAX_CHUNK, chunk_text, detect_language, split_long, split_sentences


def test_sprache_deutsch_und_englisch():
    assert detect_language("Der Hund ist nicht im Haus, aber die Katze schon.") == "de"
    assert detect_language("The dog is not in the house, but the cat is.") == "en"


def test_sprache_ohne_hinweise_ist_deutsch():
    assert detect_language("12345 ...") == "de"


def test_abkuerzungen_sind_kein_satzende():
    s = split_sentences("Das ist z. B. ein Test. Dr. Müller kommt um 3 Uhr. Fertig!", "de")
    assert s == ["Das ist z. B. ein Test.", "Dr. Müller kommt um 3 Uhr.", "Fertig!"]


def test_englische_abkuerzungen():
    s = split_sentences("Mr. Smith arrived. He was late.", "en")
    assert s == ["Mr. Smith arrived.", "He was late."]


def test_ueberschriften_werden_kapitel():
    chunks, chapters = chunk_text("# Eins\n\nErster Satz. Zweiter Satz.\n\n# Zwei\n\nText.", "de")
    assert [c["text"] for c in chunks] == ["Eins", "Erster Satz. Zweiter Satz.", "Zwei", "Text."]
    assert chunks[0]["h"] and chunks[2]["h"]
    assert chapters == [{"title": "Eins", "chunk": 0}, {"title": "Zwei", "chunk": 2}]


def test_kapitelwort_ohne_markdown():
    _, chapters = chunk_text("Kapitel 1\n\nEs war einmal.\n\nKapitel 2\n\nUnd dann.", "de")
    assert [c["title"] for c in chapters] == ["Kapitel 1", "Kapitel 2"]


def test_text_vor_erstem_kapitel_bekommt_anfang():
    _, chapters = chunk_text("Vorwort hier.\n\n# Teil A\n\nInhalt.", "de")
    assert chapters[0] == {"title": "Anfang", "chunk": 0}


def test_abschnitte_bleiben_unter_grenze():
    satz = "Dies ist ein ziemlich normaler Satz mit einigen Wörtern darin. "
    chunks, _ = chunk_text(satz * 80, "de")
    assert len(chunks) > 5
    assert all(len(c["text"]) <= MAX_CHUNK for c in chunks)
    assert chunks[0]["par"] and not chunks[1]["par"]        # nur der erste Abschnitt eines Absatzes


def test_ueberlanger_satz_wird_geteilt():
    lang = ", ".join(["ein Teil"] * 200) + "."
    teile = split_long(lang)
    assert len(teile) > 1 and all(len(t) <= MAX_CHUNK for t in teile)
    assert " ".join(teile).replace("  ", " ").startswith("ein Teil")


def test_absaetze_markiert():
    chunks, _ = chunk_text("Absatz eins.\n\nAbsatz zwei.", "de")
    assert [c["par"] for c in chunks] == [True, True]
