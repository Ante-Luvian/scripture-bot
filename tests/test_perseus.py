"""The Perseus library (scripts/build_perseus.py): Greek and Latin works in English, by their usual citations."""
import json
import re

import pytest

from core import ROOT

PERSEUS = ROOT / "data" / "classical" / "perseus"


@pytest.mark.parametrize("ref, words", [
    ("History of the Peloponnesian War 2.40:1", "We cultivate refinement without extravagance"),   # Pericles
    ("Histories 1.1:0", "Herodotus of Halicarnassus"),                 # the translator's name, not a map's
    ("Antigone 1:450", "it was not Zeus that published me that edict"),
    ("On the Murder of Eratosthenes 1:6", "When I, Athenians, decided to marry"),
    ("Metamorphoses 1:1", "Of shapes transformde to bodies straunge"),  # book:line, no "card" level
    ("De Rerum Natura 1:1", "Mother of Rome, delight of Gods and men"),
    ("Anabasis 1.1:1", "Darius and Parysatis had two sons"),
    ("Clouds 1:1", "O King Jupiter, of what a terrible length the nights are"),
    ("Germania 1:1", "Germany is separated from the Galli"),             # by its Latin title too
    ("Discourses 1.1:1", "OF all the faculties"),
    ("Description of Greece 1.1:1", "the Sunium promontory"),
    ("First Philippic 1:1", "men of Athens"),
])
def test_passages(lookup, ref, words):
    result = lookup.get_verse(ref)
    assert result.get("found"), ref
    assert words in result["text"], (ref, result["text"][:200])


def test_names(lookup):
    index = json.loads((PERSEUS / "index.json").read_text(encoding="utf-8"))
    names = [n for books in index.values() for n in books]
    assert len(names) == len(set(names)) and len(names) >= 550
    # the same title by two authors keeps each author's name; the library's own Plato isn't doubled
    assert "Sophocles: Electra" in names and "Euripides: Electra" in names
    assert "Xenophon: Apology" in names and "Plato" not in index
    assert not any(re.search(r"\d$", n) for n in names)           # a trailing number would read as a chapter
    for name in ("Sophocles: Electra", "Theseus", "Gallic War", "Metamorphoses"):
        assert lookup._resolve_book(name)[1] == name


def test_bible_still_wins(lookup):
    # 600 new titles must not capture the Bible's abbreviations
    for typed, book in (("Gen", "Genesis"), ("Jn", "John"), ("1 Thess", "1 Thessalonians"), ("Rev", "Revelation"),
                        ("Acts", "Acts"), ("Ps", "Psalms"), ("Matt", "Matthew")):
        assert lookup._resolve_book(typed)[1] == book, typed


def test_clean_text(lookup):
    for path in sorted(PERSEUS.glob("*.json")):
        if path.name in ("index.json", "aliases.json"):
            continue
        for book in json.loads(path.read_text(encoding="utf-8"))["books"].values():
            for chapter, verses in book.items():
                assert re.fullmatch(r"\d+(\.\d+)*", chapter), (path.name, chapter)
                for verse, text in verses.items():
                    assert verse.isdigit() and text.strip(), (path.name, chapter, verse)
                    assert not re.search(r"\[\d+\.\d+,\d+\.\d+\]|\(inhabited place\)", text), (path.name, text[:80])
