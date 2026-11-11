"""Percy's Reliques of Ancient English Poetry (scripts/build_percy.py, data/ballads/percy.json): the poems, in Percy's
order, without the notes or the versions and verse they quote."""
import json
import re

import pytest

from core import ROOT

BOOK = "Percy's Reliques"
DATA = json.loads((ROOT / "data" / "ballads" / "percy.json").read_text(encoding="utf-8"))
POEMS = DATA["books"][BOOK]


def first_line(chapter: str) -> str:
    """The poem's first line of verse (past its title and any heading, speaker or note)."""
    lines = POEMS[chapter]["1"].split("\n")[1:]
    return next(line for line in lines if not re.fullmatch(r"\*.*\*", line))


def test_the_whole_book():
    assert len(POEMS) == 180 and DATA["titles"]["7"] == "Sir Patrick Spence"
    assert DATA["titles"]["180"] == "The Wanton Wife of Bath"               # (Wheatley's appendix, kept last)
    assert POEMS["1"]["1"].startswith("*The Ancient Ballad of Chevy Chase* (Series I, Book I, no. I)")


@pytest.mark.parametrize("chapter, line", [
    ("7", "The king sits in Dumferling toune,"),
    # the poem, not the verse quoted in its notes or the version Wheatley prints after it
    ("12", "It fell about the Martinmas,"),                                 # (not Captaine Carre, the folio's)
    ("22", "Farewell, dear love; since thou wilt needs be gone,"),          # (not Constant Susanna, quoted)
    ("35", "My minde to me a kingdome is;"),                                # (not "A Contented Minde")
    ("96", "An ancient story Ile tell you anon"),
    ("126", "In the merrie moneth of Maye,"),
])
def test_each_poem_is_its_own(chapter, line):
    assert first_line(chapter) == line


def test_labels():
    """Speakers in bold, parts and gaps in italics; stanza numbers ("I.", "I. 1.") left out."""
    assert POEMS["38"]["1"].split("\n")[1] == "**Syren**"                     # Ulysses and the Syren
    assert POEMS["4"]["1"].split("\n")[1] == "*The First Part*"               # Sir Cauline
    assert not any(re.search(r"(?m)^\*?\*?[IVX]+\.( \d\.)?\*?\*?$", t) for c in POEMS.values() for t in c.values())


def test_clean():
    for chapter, verses in POEMS.items():
        for verse, text in verses.items():
            assert text.count("**") % 2 == 0, (chapter, verse)
            assert not re.search(r"<|&\w+;|\[\d+\]|\[Pg ", text), (chapter, verse, text[:80])
            assert not re.search(r"(?m)^\*[^*\n]*$|\w\*+\w", text), (chapter, verse, text[:80])  # (starred words: ∗)
    assert "Ja∗∗s" in POEMS["113"]["12"]


def test_lookup(lookup):
    r = lookup.get_verse("Percy's Reliques 7:1")
    assert r.get("found") and "Dumferling" in r["text"]
    for alias in ("Percy 7:1", "Reliques 7:1"):
        assert lookup.get_verse(alias).get("found"), alias
