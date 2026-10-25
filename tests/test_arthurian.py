"""The Arthurian legend (scripts/build_arthurian.py): every book there whole, and clean of its sources' leftovers."""
import re

import pytest

BOOKS = {                                            # book -> chapters at least
    "Le Morte d'Arthur": 503, "Erec and Enide": 50, "Cligès": 80, "Yvain, the Knight with the Lion": 50,
    "Lancelot, the Knight of the Cart": 50, "Parzival": 16, "The High History of the Holy Graal": 400,
    "The Quest of the Holy Grail": 15, "Tristan and Iseult": 15, "Sir Gawain and the Green Knight": 60,
    "Lays of Marie de France": 17, "Geoffrey of Monmouth, History of the Kings of Britain": 200,
    "Wace, Roman de Brut": 1, "Layamon's Brut": 1, "Nennius, History of the Britons": 8, "Morien": 1,
    "Sir Libeaus Desconus": 1, "Sir Launfal": 1, "The Adventures of Arthur at the Tarn Wadeling": 1, "Tyolet": 1,
}


@pytest.fixture(scope="module")
def arthur(lookup):
    return lookup._data["arthurian"]


def test_every_book_is_there(arthur):
    for book, most in BOOKS.items():
        assert len(arthur.get(book, {})) >= most, book
    malory = arthur["Le Morte d'Arthur"]
    assert {k.split(".")[0] for k in malory} == {str(n) for n in range(1, 22)}       # (21 books)
    assert len([k for k in malory if k.startswith("3.")]) == 15                       # ("CHAPTER VII" with no stop)
    assert "12.8" in malory and "12.55" not in malory                                 # (the etext's "LV." for VIII)


def test_clean(arthur):
    text = "\n".join(v for b in arthur.values() for c in b.values() for v in c.values())
    assert not re.search(r"Ž|Ò|Ó|Õ|¾|\[Pg|\[Footnote|Project Gutenberg|In Parentheses Publications|Endnotes|"
                         r"Printed by|TEMPLE PRESS|<|&#|�", text)
    assert not re.search(r"[a-z][.,;]?\d{1,3}\s", text.replace("MCCCC", ""))           # (note marks)


def test_drop_capitals_and_the_right_endings(arthur):
    assert arthur["Sir Launfal"]["1"]["1"].split("\n")[1].startswith("In the days of mighty Arthur")
    assert arthur["Morien"]["1"]["1"].split("\n")[1].startswith("Herein doth the adventure tell")
    assert list(arthur["Erec and Enide"].values())[-1][str(len(list(arthur["Erec and Enide"].values())[-1]))] \
        .endswith("Here the story ends at last.")
    assert "Bournemouth" not in " ".join(arthur["Morien"]["1"].values())              # (the preface: left out)


def test_references(lookup):
    assert "sword taken out of a stone" in lookup.get_verse("Malory 1.5")["text"]
    assert lookup.get_verse("Geoffrey 9.1:1")["text"].startswith("**[1]** *Arthur succeeds Uther")
    assert lookup.get_verse("Gawain 5")["tradition"] == "arthurian"
    for ref in ("Yvain 3", "Queste 1:1", "High History 1.1", "Wace 1:5", "Layamon 1:1", "Tarn Wadeling 1:1"):
        assert lookup.get_verse(ref)["found"], ref
