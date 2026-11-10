"""The Kebra Nagast, the Cave of Treasures and the Book of the Bee in Budge's translations (scripts/build_budge.py)."""
import re

import pytest


@pytest.mark.parametrize("ref, words", [
    ("Kebra Nagast 1:1", "*The Glory of Kings*\nIn praising God the Father, the Sustainer of the universe"),  # (caps)
    ("Kebra Nagast 1:2", "*Concerning the Glory of Kings*\nThe interpretation and explanation"),
    ("Kebra Nagast 21:1", "And the Queen of the South of whom He spake was the Queen of Ethiopia."),
    ("Kebra Nagast 118:1", "*Colophon*\nIn the Arabic text it is said"),
    ("Glory of Kings 48:1", "*How they carried away Zion*"),               # (small capitals: "ZION")
    ("Cave of Treasures 1:1", "*The First Thousand Years*\nBy the might of our Lord Jesus Christ"),
    ("Cave of Treasures 2:1", "*Of the transmission of the art of playing the harp"),   # (the manuscript's heading)
    ("Cave of Treasures 3:42", "In the days of Reu the third thousand years came to an end."),
    ("Cave of Treasures 6:94", "And to God be glory for ever!"),
    ("Book of the Bee 0:1", "*The Book of the Bee*\nTrusting in the power of our Lord Jesus Christ"),
    ("Book of the Bee 13:1", "*Of the Formation of Adam*\nOn the Friday, after the making of all created things"),
    ("Book of the Bee 51:1", "1. Addai was buried in Edessa."),
    ("Book of the Bee 41:1", "John the Baptist lived thirty years in the desert"),     # (the page: "yeats")
])
def test_passages(lookup, ref, words):
    result = lookup.get_verse(ref)
    assert result.get("found"), ref
    assert words in result["text"], (ref, result["text"][:300])
    assert "Budge" in result["source"]


def test_whole_and_clean(lookup):
    books = lookup._data["charles"]
    assert list(books["Kebra Nagast"]) == [str(n) for n in range(1, 119)]
    assert list(books["Cave of Treasures"]) == [str(n) for n in range(1, 7)]
    assert list(books["Book of the Bee"]) == [str(n) for n in range(0, 61)]
    for name in ("Kebra Nagast", "Cave of Treasures", "Book of the Bee"):
        for ch, verses in books[name].items():
            assert list(verses) == [str(n) for n in range(1, len(verses) + 1)], (name, ch)
            for text in verses.values():
                # no notes, folio or page numbers, site furniture, small capitals left in capitals, lone asterisks
                assert not re.search(r"NOTES?\.--|\bFol\. \d|\bp\. \d|sacred-texts|\{|@@|<|>|  |\b[A-ZÂÊÎÔÛ]{4,}\b",
                                     text), (name, ch, text[:120])
                assert text.count("*") % 2 == 0, (name, ch, text[:120])
    # the Cave's text without Budge's commentary: the zodiac table in his note is gone, the genealogy kept
    cave = " ".join(t for vs in books["Cave of Treasures"].values() for t in vs.values())
    assert "Zibanitum" not in cave and "Babylonian Signs" not in cave
    assert "1. Adam begot Seth.\n2. Seth took to wife" in cave
    assert "Abimelech, king of Gâdhâr.\nÂmarphîl" in cave                 # (a table: the kings who built Jerusalem)
