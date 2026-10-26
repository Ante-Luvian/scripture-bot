"""Medieval English poetry (scripts/build_english.py): every poem there whole, clean, its old letters kept, and
cited by line the way the owner asked -- "Sir Orfeo 233", never "Sir Orfeo 1:233"."""
import re

import pytest

LINES = {                                     # one-part poems cited by line -> their last passage starts after
    "Sir Orfeo": 590, "Pearl": 1190, "Cleanness": 1790, "Patience": 500, "Havelok the Dane": 2970,
    "King Horn": 1600, "Piers Plowman": 14600, "Genesis and Exodus": 4100, "The Sowdone of Babylone": 3200,
    "Torrent of Portyngale": 2650, "The House of Fame": 2100, "The Legend of Good Women": 2700,
    "The Romaunt of the Rose": 7600, "The Book of the Duchess": 1300, "Sir Beues of Hamtoun": 4400,
    "Of Arthour and of Merlin": 9700, "Sir Gawayn and the Grene Knyȝt": 2500, "Lancelot of the Laik": 3400,
}
PARTS = {"Troilus and Criseyde": 5, "Confessio Amantis": 9, "The Bruce": 20, "Wallace": 11}   # (the Prologue is 0)


@pytest.fixture(scope="module")
def books(lookup):
    return {**lookup._data["english"], **lookup._data["arthurian"]}


def _text(book):
    return "\n".join(v for c in book.values() for v in c.values())


def test_every_poem_is_there(books):
    for book, last in LINES.items():
        assert max(int(k) for k in books[book]["1"]) >= last, book
    for book, parts in PARTS.items():
        assert len(books[book]) == parts, book
    assert len(books["The Faerie Queene"]) == 75 and "7.8" in books["The Faerie Queene"]   # (the unfinished canto)
    assert len(books["The Canterbury Tales"]) >= 45
    assert len(books["Ludus Coventriae"]) == 43                                     # (the Prologue and 42 plays)
    assert len(books["The Pastime of Pleasure"]) == 46 and len(books["Lyndsay's Poems"]) == 8
    assert max(int(k) for k in books["Magnyfycence"]["1"]) >= 2500                  # (the play, its 2567 lines)
    skelton = "\n".join(_text(books[b]) for b in books if "Skelton" in b)
    assert "Lamentatio" not in skelton and "Tetrastichon" not in skelton            # (his Latin poems: left out)


def test_clean(books):
    text = "\n".join(_text(b) for b in books.values())
    assert not re.search(r"<|&#|&[a-z]+;|\[Pg|\{f\.|myLayer|facsimile|Project Gutenberg|LINENOTES|�", text)
    for line in text.split("\n"):
        assert line.count("*") % 2 == 0, line                           # (italics close on their own line)


def test_old_letters(books):
    """ȝ, þ and ð as themselves, never a stand-in: Morris's transcriber's 3 for yogh, a scribe's y for thorn."""
    gawayn = _text(books["Sir Gawayn and the Grene Knyȝt"])
    assert "watȝ" in gawayn and not re.search(r"[a-zþ]3|3[a-zþ]", gawayn)
    assert "ð" in _text(books["Genesis and Exodus"])
    laik = _text(books["Lancelot of the Laik"])
    assert "þat" in laik and not re.search(r"\byat\b", laik)


def test_cited_by_line(lookup):
    r = lookup.get_verse("Sir Orfeo 233")
    assert r["found"] and r["reference"].startswith("Sir Orfeo ") and ":" not in r["reference"]
    assert lookup.get_verse("Sir Orfeo 233-260")["reference"].startswith("Sir Orfeo 2")
    assert lookup.get_verse("orfeo 1:233")["reference"] == r["reference"]           # (still read, never shown)
    assert lookup.get_verse("Pearl 1")["text"].count("Perle plesaunte")              # (line 1, not the whole poem)
    assert lookup.get_verse("Troilus 3:1")["reference"].startswith("Troilus and Criseyde 3:1")
    assert lookup.get_verse("Confessio Amantis 0:1")["found"]
    assert not lookup.get_verse("Sir Orfeo 5000")["found"]
    for ref in ("Canterbury Tales 1:1", "Faerie Queene 1.1:1", "Bruce 20:1", "Gawayn 1", "Beues 100",
                "Chaucer's Shorter Poems 13:1", "Middle English Lyrics 3:1", "Piers Plowman 460"):
        assert lookup.get_verse(ref)["found"], ref
    assert lookup.get_verse("Pearl 1")["tradition"] == "english"


def test_every_one_chapter_book_is_cited_by_verse_alone(lookup):
    """The owner's rule for all of them, not only the poems: "Jude 3", never "Jude 1:3"."""
    assert lookup.get_verse("Jude 3")["reference"] == "Jude 3"
    assert lookup.get_verse("Jude 1:3")["reference"] == "Jude 3"                    # (still read)
    assert lookup.get_verse("Jude 3-5")["reference"] == "Jude 3–5"
    assert lookup.get_verse("Philemon 1:10")["reference"] == "Philemon 10"
    assert lookup.get_verse("Wace 5")["reference"] == "Wace, Roman de Brut 5"
    assert lookup.get_verse("John 3:16")["reference"] == "John 3:16"               # (more chapters: as before)
    assert lookup._cite("Jude", "1", "3") == "Jude 3" and lookup._cite("John", "3", "16") == "John 3:16"
    whole = lookup.get_verse("Wace 1", whole=True)                                  # (the !books browser)
    assert whole["found"] and whole["reference"] == "Wace, Roman de Brut" and whole.get("pages")
