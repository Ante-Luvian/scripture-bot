"""Zosimus's New History in the English of 1814 (scripts/build_zosimus.py): a book a chapter, a paragraph a verse."""
import re

import pytest


@pytest.mark.parametrize("ref, words", [
    ("zosimus 1:1", "WHEN Polybius of Megalopolis"),
    ("new history 4:1", "IN the preceding book"),
    ("historia nova 6:1", "ALARIC having thus received insult"),
])
def test_it_opens(lookup, ref, words):
    r = lookup.get_verse(ref)
    assert r["found"] and words in r["text"], ref


def test_clean_of_the_online_editions_marks(lookup):
    corpus, name = lookup._resolve_book("New History")
    text = "\n".join(v for ch in lookup._data[corpus][name].values() for v in ch.values())
    assert list(lookup._data[corpus][name]) == ["1", "2", "3", "4", "5", "6"]
    assert not re.search(r"Note (to|for) the online|\|\d|\|'|\* \* \*|SPIonic|aiw_n|Roger Pearse", text)
    assert "αιών" in text                                          # (the SPIonic Greek as Greek)
    assert "they sailed to the mouth of the Rhine" in text
