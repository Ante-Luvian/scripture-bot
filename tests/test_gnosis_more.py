"""The rest of the Gnostic Society Library's texts (scripts/build_gnosis.py mani, cathar): the Manichaean hymns and
fragments from Central Asia, the Mandaean prayers and the Haran Gawaita, Valentinus, Ptolemy and Heracleon, and the
Cathars' books in English."""
import re

import pytest


@pytest.mark.parametrize("ref, words", [
    ("Manichaean Hymns 2:1", "*Hymn to the Father of Greatness*\n*A hymn ascribed to Mani, in Parthian.*"),
    ("Manichaean Hymns 38:1", "A merchant had many precious gems"),          # (the Pearl-Borer)
    ("Kephalaia 35:1", "three blows"),
    ("Mandaean Prayers 1:1", "I prepared a path for the good ones"),
    ("Haran Gawaita 1", "My Lord be praised. In the name of the Great Life"),
    ("Valentinus 8", "*Summer Harvest: A Psalm By Valentinus*\nIn the spirit I see all suspended"),
    ("Ptolemy on John 1", "John, the disciple of the Lord"),
    ("Heracleon 1", "*On John 1:3*"),
    ("Heracleon 50", ""),
    ("Secret Supper 1", "I, John, your brother and partaker in tribulation"),
    ("Two Principles 1:1", "*Part 1. On Free Will*"),
    ("Two Principles 7:6", "How the Saints Have Suffered"),
    ("Cathar Ritual 1:1", "We have come before God"),
])
def test_passages(lookup, ref, words):
    result = lookup.get_verse(ref)
    assert result.get("found"), ref
    assert words in result["text"], (ref, result["text"][:300])


def test_no_site_furniture_or_broken_characters(lookup):
    """No navigation, notes on sources, Occitan, or the "�" of a page read in the wrong encoding."""
    gnostic = lookup._data["gnostic"]
    for book in ("Manichaean Hymns and Fragments", "Mandaean Prayers", "Haran Gawaita", "Fragments of Valentinus",
                 "Ptolemy's Commentary on John", "Fragments of Heracleon", "The Secret Supper",
                 "Book of the Two Principles", "Cathar Ritual", "Untitled Text of the Bruce Codex", "The Secret Book of John"):
        for verses in gnostic[book].values():
            for text in verses.values():
                assert not re.search(r"�|\xad|Archive \||GNOSIS ARCHIVE|Source document|Lance S?\. Owens|"
                                     r"Benedicite, parcite|Nos em vengut", text), (book, text[:100])
    assert "Aphrêdon" in lookup.get_verse("Untitled Text 3:2")["text"]       # (was "Aphr�don")
