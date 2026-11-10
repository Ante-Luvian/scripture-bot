"""Jewish pseudepigrapha added from Charles's edition and M. R. James (scripts/build_pseudepigrapha.py), and the
Apocalypse of Sedrach from ANF 9."""
import re

import pytest


@pytest.mark.parametrize("ref, words", [
    ("2 Baruch 1:1", "And it came to pass in the twenty-fifth year of Jeconiah"),
    ("2 Baruch 32:1", "if you prepare your hearts, so as to sow in them the fruits of the law"),   # (anchored "32.1")
    ("2 Baruch 85:2", "No more, we were in our own land"),          # (where every copy online stops)
    ("3 Baruch 0:1", "A narrative and revelation of Baruch"),
    ("3 Baruch 1:1", "Verily I Baruch was weeping"),
    ("Greek Apocalypse of Baruch 17:1", ""),
    ("Biblical Antiquities 1:1", "The beginning of the world. Adam begat three sons and one daughter"),
    ("Pseudo-Philo 43:1", "Eluma conceived and bare a son and called his name Samson"),   # (no heading of its own)
    ("Pseudo-Philo 29:1", "the people appointed Zebul ruler"),                            # ("XXIX And": no stop)
    ("Apocalypse of Sedrach 1:1", "Beloved, let us prefer nothing in honour except sincere love"),
    ("History of the Rechabites 1:1", ""),
])
def test_passages(lookup, ref, words):
    result = lookup.get_verse(ref)
    assert result.get("found"), ref
    assert words in result["text"], (ref, result["text"][:300])


def test_no_site_furniture(lookup):
    charles = lookup._data["charles"]
    for book in ("2 Baruch", "3 Baruch", "Biblical Antiquities"):
        for verses in charles[book].values():
            for text in verses.values():
                assert not re.search(r"Wesley|Copyright|finish$|Gen\. \d+:\d+|p\. \d+|Next:|(?<!\.)\s[,;:]", text)    # (". . . ," is Charles's gap), (book, text[:100])
    assert "ends at 85:2" in lookup.get_verse("2 Baruch 1:1")["source"]
