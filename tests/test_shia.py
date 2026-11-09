"""The Shi'ite texts (scripts/build_shia.py): the Nahj al-Balagha in Qutbuddin's numbering, the Sahifa Sajjadiyya
by supplication."""
import re

import pytest


def test_the_nahj_numbered_as_qutbuddin_numbers_it(lookup):
    nahj = lookup._data["quran"]["Nahj al-Balagha"]
    for part, count in (("1", 238), ("2", 79), ("3", 446)):
        assert {f"{part}.{n}" for n in range(1, count + 1)} <= set(nahj), part
    assert "0" in nahj                                   # (Radi's introduction and conclusion)


@pytest.mark.parametrize("ref, words", [
    ("Nahj al-Balagha 1.1:1", "I praise God. Yet no speaker can articulate his praise"),
    ("Nahj al-Balagha 1.1:2", "God created the world and gave it a beginning"),
    ("Nahj al-Balagha 2.53:2", "Know, O Mālik, that I send you to a land"),       # (the Testament to al-Ashtar)
    ("Nahj al-Balagha 3.1", "In times of sedition, be like a young camel buck"),
    ("Nahj al-Balagha 3.384", "To avoid doing what you dislike in others is discipline enough"),
    ("Nahj 0:8", "I have decided to name this book Nahj al-Balāghah"),
])
def test_nahj_passages(lookup, ref, words):
    result = lookup.get_verse(ref)
    assert result.get("found"), ref
    assert words in result["text"], (ref, result["text"][:200])


def test_the_sahifa_by_supplication(lookup):
    """The preface (0), the 54 supplications and those added after them, by Chittick's verse numbers, his lines
    kept; each headed in italics, a line at a time (Discord's italics don't cross a line break)."""
    sahifa = lookup._data["quran"]["Sahifa Sajjadiyya"]
    assert {str(n) for n in range(0, 55)} <= set(sahifa)
    first = lookup.get_verse("Sahifa Sajjadiyya 1:1")["text"]
    assert "*In Praise of God*" in first and "Praise belongs to God,\nthe First, without a first before Him" in first
    assert "O God,\nno one reaches a limit in thanking Thee" in lookup.get_verse("Sahifa 37:1")["text"]   # ("1." for "1-")
    assert "The greatest sayyid" in lookup.get_verse("Sahifa 0:1")["text"]
    for verses in sahifa.values():
        for text in verses.values():
            assert not re.search(r"[؀-ۿ]|ﬁ", text)
            assert all(line.count("*") in (0, 2) for line in text.split("\n")), text[:80]


def test_only_the_english_and_no_notes(lookup):
    """The Arabic pages, the footnotes and their marks, the part title pages and her appendix are left out."""
    nahj = lookup._data["quran"]["Nahj al-Balagha"]
    for chapter, verses in nahj.items():
        for v, text in verses.items():
            assert not re.search(r"[؀-ۿ]", text), (chapter, v)
            assert not re.search(r"Chapter containing selections|Text and Translation|Text no\. References", text)
            assert not re.search(r"[a-z][.,;:]\d{1,3}(?=\s|$)", text), (chapter, v, text[:120])
