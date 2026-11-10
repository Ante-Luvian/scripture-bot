"""The works of Philo added from Early Jewish Writings (scripts/build_philo_more.py), and the long vowels, dashes and
quotation marks put back in the rest of his works (where the copy had U+FFFD)."""
import re

import pytest


@pytest.mark.parametrize("ref, words", [
    ("On Dreams I 1", "The treatise before this one has contained our opinions"),
    ("On Dreams I 3", "And Jacob dreamed, and behold a ladder"),
    ("On Dreams II 1", "In describing the third species of dreams"),
    ("Hypothetica 6.1", "That their ancient ancestor, the original founder of their race, was a Chaldaean"),
    ("On Providence I 1", "But concerning the quantity of the essence"),
    ("On Providence II 1", "Now he conducts his argument in this way"),
    ("Fragments of Philo 3", "*About those people who have renounced such and such a line of conduct, and then turning back again"),
    ("On Husbandry 3", "(geōrgia)"),          # (was "geo�rgia": the long vowels marked as Yonge prints them)
])
def test_passages(lookup, ref, words):
    result = lookup.get_verse(ref)
    assert result.get("found"), ref
    assert words in result["text"], (ref, result["text"][:300])


def test_no_eusebius_notes_or_advertising(lookup):
    philo = lookup._data["jewish"]
    for book in ("On Dreams I", "On Dreams II", "Hypothetica", "On Providence I", "On Providence II", "Fragments of Philo"):
        for verses in philo[book].values():
            for text in verses.values():
                assert not re.search(r"test-king|exam study|Go to the|Peter Kirby|\{|\}|And first of all I will adduce|"
                                     r"I will produce a man who is a Hebrew", text), (book, text[:100])
