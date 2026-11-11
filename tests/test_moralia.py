"""St Gregory's Morals on the Book of Job (scripts/build_moralia.py, data/patristics/gregory_moralia.json)."""
import json
import re

from core import ROOT

DATA = json.loads((ROOT / "data" / "patristics" / "gregory_moralia.json").read_text(encoding="utf-8"))
BOOK = DATA["books"]["Morals on the Book of Job"]


def test_the_whole_work():
    """The letter and Preface (chapter 0) and all 35 books, each opening with its summary, its paragraphs numbered
    as printed. (Three numbers the transcription never had -- Book 4's 71, Book 17's 52 -- have their text kept with
    the paragraph before.)"""
    assert list(BOOK) == [str(n) for n in range(36)]
    assert BOOK["0"]["1"].startswith("*The Epistle to Leander*\nWHEN I knew you long since at Constantinople")
    for n in range(1, 36):
        assert BOOK[str(n)]["0"].startswith("*") and BOOK[str(n)]["0"].endswith("*"), n
        keys = sorted(int(k) for k in BOOK[str(n)] if k != "0")
        missing = set(range(1, keys[-1] + 1)) - set(keys)
        assert missing <= {71, 52}, (n, missing)
    assert BOOK["35"]["49"].startswith("This work then being now completed, I see that I must go back to myself.")


def test_verse_headings():
    """The verse of Job a paragraph explains leads it, in italics; misprints in the transcription are read right."""
    assert BOOK["31"]["4"].startswith("*Ver. 10.* *Wilt thou bind the rhinoceros with thy band to plough?*\n")
    assert BOOK["1"]["1"].startswith("*Historical Interpretation*\n*There was a man in the land of Uz")
    assert BOOK["23"]["18"].startswith("*Ver. 18–20.* *I am full of words")                  # ("Ver. 18.* *—20.")


def test_clean():
    for chapter, verses in BOOK.items():
        for verse, text in verses.items():
            assert text.count("*") % 2 == 0, (chapter, verse)
            assert not re.search(r"<|&\w+;|\[[a-z]\]|_{3,}|[Ͱ-Ͽἀ-῿]{2}", text), (chapter, verse)
            assert not re.search(r"(?<=[a-z])1(?=[a-z])", text), (chapter, verse)     # (the scanner's 1 for l)


def test_lookup(lookup):
    r = lookup.get_verse("Morals on the Book of Job 31:4")
    assert r.get("found") and "rhinoceros" in r["text"]
    assert lookup.get_verse("Morals on Job 1:1").get("found")
    assert lookup.get_verse("Moralia 1:1").get("did_you_mean")       # (bare "Moralia" is Plutarch's: not Gregory's)
