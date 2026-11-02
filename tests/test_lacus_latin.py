"""The Latin historians and Frontinus from LacusCurtius (2026-11-02, scripts/build_latin.py): the Historia Augusta's
thirty lives, Velleius Paterculus, Florus, Frontinus's Stratagems and Aqueducts."""
import json

import pytest

from core import ROOT


@pytest.fixture(scope="module")
def books(bot_module):
    from bot_commands import books
    return books


@pytest.fixture(scope="module")
def latin():
    return json.loads((ROOT / "data" / "classical" / "latin.json").read_text(encoding="utf-8"))["books"]


def found(lookup, ref):
    res = lookup.get_verse(ref)
    assert res.get("found"), (ref, res.get("error") or res.get("suggestions"))
    return res


def test_historia_augusta(lookup):
    assert "Picenum" in found(lookup, "Historia Augusta: Hadrian 1:1")["text"]
    assert "Picenum" in found(lookup, "hadrian 1:1")["text"]
    # (Hadrian's life is on two pages: chapter 14 runs across them)
    assert "poetry and in letters" in found(lookup, "Hadrian 14:8")["text"]
    assert "*Postumus*" in found(lookup, "Thirty Pretenders 3:1")["text"]                  # (the pretender's name)
    assert "Play-actor" in found(lookup, "macrinus 11:4")["text"]                        # (a verse quotation)
    assert "Carinus" in str(found(lookup, "Historia Augusta: Carus, Carinus and Numerian 1:1").get("reference"))


def test_names_other_books_keep(lookup):
    """Emperors whose names were already books: the Historia Augusta's lives are reached another way."""
    assert "Historia Augusta" not in str(found(lookup, "Claudius 1:1").get("reference"))   # (Suetonius)
    assert "Historia Augusta" not in str(found(lookup, "marcus aurelius 1:1").get("reference"))   # (the Meditations)
    assert "Historia Augusta: Tacitus" in str(found(lookup, "life of tacitus 1:1").get("reference"))
    assert "The Deified Claudius" in str(found(lookup, "life of claudius 1:1").get("reference"))


def test_frontinus(lookup):
    res = found(lookup, "Stratagems 1.1:1")
    assert "*On Concealing One's Plans*" in res["text"] and "Cato" in res["text"]
    assert "military science" in found(lookup, "frontinus 1.0:1")["text"]                  # (Book 1's preface)
    assert "Appian aqueduct" in found(lookup, "de aquis 5")["text"]


def test_velleius_and_florus(lookup):
    assert "Jupiter Capitolinus" in found(lookup, "Velleius 2.131:1")["text"]
    res = found(lookup, "Florus 1.1:1")
    assert "*The period of the Seven Kings, beginning with Romulus*\nThe first founder" in res["text"]
    assert "*The Norican War*" in found(lookup, "Florus 4.12:4")["text"]       # (a title at the top of a page)


def test_text_is_clean(latin):
    """None of Thayer's apparatus: page and note numbers, his • pop-ups, his pointers to the next page."""
    new = [b for b in latin if b.startswith("Historia Augusta") or b in (
        "Stratagems", "The Aqueducts of Rome", "Roman History", "Epitome of Roman History")]
    assert len(new) == 34
    for book in new:
        for chapter, verses in latin[book].items():
            for verse, text in verses.items():
                assert not any(s in text for s in ("•", "For the end of chapter", "R 2003", "\x01", "\x02", "<", "Latin text")), (book, chapter, verse)
                assert "\n\n" not in text and text == text.strip(), (book, chapter, verse)


def test_the_historians_shelf(books):
    latin = dict(dict(books.BOOKS_TREE)["🦅 Latin"])
    authors = [a for a, _ in latin["Historians"]]
    assert authors.index("Livy") < authors.index("Velleius Paterculus") < authors.index("Tacitus")
    assert authors.index("Suetonius") < authors.index("Florus") < authors.index("Historia Augusta")
    assert len(dict(latin["Historians"])["Historia Augusta"]) == 30
    assert dict(latin["Farming & Practical Arts"])["Frontinus"] == ["Stratagems", "The Aqueducts of Rome"]
