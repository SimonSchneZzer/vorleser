"""HTML aus Template-Strings: fremde Texte (Titel, Namen, Fehlermeldungen …) nur über esc().

Titel und Kapitel stammen aus importierten Büchern, Namen aus Stimmen-Listen, Fehlermeldungen vom Server – landen sie
ungeschützt in innerHTML, kann ein präpariertes EPUB Skripte in die Oberfläche schmuggeln. Der Test liest jeden
Template-String in static/js/, der HTML enthält, und prüft jede ${…}-Stelle: Verweise auf solche Felder müssen in
esc(…) (oder mdBold(…), das selbst esc nutzt) stehen. Geprüfte Ausnahmen stehen mit Grund in REVIEWED.
"""
import re
from pathlib import Path

import pytest

JS_DIR = Path(__file__).resolve().parents[1] / "static" / "js"

# Felder/Namen, die fremden Text tragen können
_F = r"(?:title|name|text|label|message|msg|error|err|lead|detail|reason|filename|summary)"
UNTRUSTED = re.compile(rf"\.{_F}\b|(?<![.\w$]){_F}\b(?!\s*:)")   # x.title überall; bare title nicht als Objekt-Schlüssel
SAFE_CALLS = ("esc", "mdBold")

# (Datei, Ausdruck) → warum ungefährlich. Neue Einträge nur nach Prüfung!
REVIEWED = {
    ("einfuehrung.js", "p.name"): "PRESETS: feste Farbnamen aus dem Code",
    ("einstellungen.js", "p.name"): "PRESETS: feste Farbnamen aus dem Code",
}

REGEX_PREV = set("(,=:[!&|?{};+-*%<>~^")
REGEX_KEYWORDS = ("return", "typeof", "case", "in", "of", "else", "void", "delete", "instanceof", "new", "yield", "await")


class Scanner:
    """Kleiner JS-Tokenizer: findet Template-Strings (auch verschachtelte) und ihre ${…}-Ausdrücke."""

    def __init__(self, src: str):
        self.s, self.templates = src, []          # [(Zeile, Literaltext, [Ausdrücke])]

    def line(self, i):
        return self.s.count("\n", 0, i) + 1

    def _prev_significant(self, i):
        j = i - 1
        while j >= 0 and self.s[j] in " \t\r\n":
            j -= 1
        if j < 0:
            return "", ""
        k = j
        while k >= 0 and (self.s[k].isalnum() or self.s[k] in "_$"):
            k -= 1
        return self.s[j], self.s[k + 1:j + 1]

    def code(self, i, stop_brace=False):
        """Code ab i bis Dateiende (oder bis zur schließenden } eines ${…}); gibt das Ende zurück."""
        s, depth = self.s, 0
        while i < len(s):
            c = s[i]
            if c in "'\"":
                i = self.string(i)
            elif c == "`":
                i = self.template(i)
            elif s.startswith("//", i):
                i = s.find("\n", i)
                i = len(s) if i < 0 else i
            elif s.startswith("/*", i):
                i = s.index("*/", i + 2) + 2
            elif c == "/":
                prev, word = self._prev_significant(i)
                i = self.regex(i) if (prev == "" or prev in REGEX_PREV or word in REGEX_KEYWORDS) else i + 1
            elif c == "{":
                depth += 1
                i += 1
            elif c == "}":
                if depth == 0 and stop_brace:
                    return i
                depth -= 1
                i += 1
            else:
                i += 1
        assert not stop_brace and depth == 0, "Klammern laufen nicht auf – Tokenizer verirrt"
        return i

    def string(self, i):
        q, i = self.s[i], i + 1
        while self.s[i] != q:
            i += 2 if self.s[i] == "\\" else 1
        return i + 1

    def regex(self, i):
        i, in_class = i + 1, False
        while True:
            c = self.s[i]
            assert c != "\n", f"Regex über Zeilenende in Zeile {self.line(i)} – Tokenizer verirrt"
            if c == "\\":
                i += 2
                continue
            if c == "[":
                in_class = True
            elif c == "]":
                in_class = False
            elif c == "/" and not in_class:
                break
            i += 1
        i += 1
        while i < len(self.s) and self.s[i].isalpha():
            i += 1
        return i

    def template(self, i):
        start, i, lit, exprs = i, i + 1, [], []
        while self.s[i] != "`":
            if self.s[i] == "\\":
                lit.append(self.s[i:i + 2])
                i += 2
            elif self.s.startswith("${", i):
                end = self.code(i + 2, stop_brace=True)
                exprs.append(self.s[i + 2:end])
                i = end + 1
            else:
                lit.append(self.s[i])
                i += 1
        self.templates.append((self.line(start), "".join(lit), exprs))
        return i + 1


def _strip(expr: str) -> str:
    """Strings, verschachtelte Templates (werden einzeln geprüft) und esc(…)-Aufrufe entfernen."""
    sc, out, i = Scanner(expr), [], 0
    while i < len(expr):
        c = expr[i]
        if c in "'\"":
            i = sc.string(i)
        elif c == "`":
            i = sc.template(i)
        elif m := re.match(rf"\b(?:{'|'.join(SAFE_CALLS)})\(", expr[i:]):
            depth, i = 1, i + m.end()
            while depth:
                if expr[i] in "'\"":
                    i = sc.string(i)
                    continue
                if expr[i] == "`":
                    i = sc.template(i)
                    continue
                depth += {"(": 1, ")": -1}.get(expr[i], 0)
                i += 1
        else:
            out.append(c)
            i += 1
    rest = "".join(out)
    m = re.search(r"(?<![?])\?(?![.?])", rest)    # Bedingung eines „a ? b : c“ gibt nichts aus
    return rest[m.end():] if m else rest


def _html_templates():
    for path in sorted(JS_DIR.glob("*.js")):
        sc = Scanner(path.read_text("utf-8"))
        sc.code(0)
        for line, lit, exprs in sc.templates:
            if re.search(r"<[a-zA-Z/!]", lit):
                yield path.name, line, exprs


def test_tokenizer_findet_templates():
    alle = list(_html_templates())
    assert len(alle) > 60                                       # sonst liest der Test nichts Sinnvolles
    assert sum(len(e) for _, _, e in alle) > 150


@pytest.mark.parametrize("name", sorted(p.name for p in JS_DIR.glob("*.js")))
def test_fremde_texte_nur_mit_esc(name):
    fehler = []
    for fname, line, exprs in _html_templates():
        if fname != name:
            continue
        for expr in exprs:
            rest = _strip(expr)
            if UNTRUSTED.search(rest) and (fname, expr.strip()) not in REVIEWED:
                fehler.append(f"{fname}:{line}: ${{{expr.strip()}}}")
    assert not fehler, "Ungeschützt ins HTML (esc() nutzen oder geprüft in REVIEWED eintragen):\n" + "\n".join(fehler)


def test_selbsttest_erkennt_ungeschuetzte_stelle():
    sc = Scanner('el.innerHTML = `<b>${d.title}</b><i>${esc(d.title)}</i>${n ? `<u>${v.name}</u>` : ""}'
                 '${d.lead ? "x" : ""}${ok ? e.message : ""}${a?.b ?? x.label}` / 2;')
    sc.code(0)
    funde = [e for _, _, ex in sc.templates for e in ex if UNTRUSTED.search(_strip(e))]
    assert funde == ["v.name", "d.title", "ok ? e.message : \"\"", "a?.b ?? x.label"]
