"""The Toledot Yeshu in its two recensions (scripts/build_toledot.py): Wagenseil's (Foote and Wheeler) by its
chapters and verses, the Strasbourg manuscript (Mead) by its twelve sections."""
import re

import pytest


@pytest.mark.parametrize("ref, words", [
    ("Toledot Yeshu 1:1", "IN the year 671, of the fourth millenary [of the world], in the days of Jannaeus"),
    ("Toledot Yeshu 2:13", "Then they narrated the history of Joseph Pandera."),     # (misprinted "18.")
    ("Toledot Yeshu 2:54", "David, my forefather"),                                 # (run on after a comma)
    ("Toledot Yeshu 4:55", "So perish all thine enemies, O Lord"),
    ("Toledot Yeshu: Strasbourg Manuscript 1:1", "THE beginning of the birth of Jeschu"),
    ("Strasbourg Toledot 2:1", "His mother gave him to a teacher"),
    ("Strasbourg Toledot 12:1", "Now the chief of the Sanhedrin, his name was Shimeon Kepha"),
])
def test_passages(lookup, ref, words):
    result = lookup.get_verse(ref)
    assert result.get("found"), ref
    assert words in result["text"], (ref, result["text"][:300])


def test_whole_and_clean(lookup):
    books = lookup._data["jewish"]
    for book, chapters in (("Toledot Yeshu", 4), ("Toledot Yeshu: Strasbourg Manuscript", 12)):
        assert list(books[book]) == [str(n) for n in range(1, chapters + 1)], book
        for verses in books[book].values():
            keys = [int(k) for k in verses]
            assert keys == list(range(1, len(keys) + 1)), book
            for text in verses.values():
                assert not re.search(r"\[\d+:\d+\]|Freethought|Colavito|Next Section|Agobard|\s\d{1,3}\.\s+[A-Z]", text), (book, text[:100])
