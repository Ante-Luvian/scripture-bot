"""Reading on from a passage: ◀ Previous · Next ▶ · 📖 Whole chapter under any text held here (a user
asked for them), and long passages in phone-screen pages rather than three screens of text."""
import re

import pytest


@pytest.mark.parametrize("ref, prev, nxt, chapter", [
    ("John 3:16", "John 3:15", "John 3:17", "John 3"),
    ("John 3:16-18", "John 3:15", "John 3:19", "John 3"),
    ("John 3", "John 2", "John 4", None),                      # a chapter steps by chapters
    ("Genesis 1:1", None, "Genesis 1:2", "Genesis 1"),
    ("Revelation 22:21", "Revelation 22:20", None, "Revelation 22"),
    ("Timaeus 67", "Timaeus 66e", "Timaeus 67b", None),        # Stephanus sections
    ("Timaeus 67a-68b", "Timaeus 66e", "Timaeus 68c", None),
    ("Enuma Elish 1:9", "Enuma Elish 1:1", "Enuma Elish 1:17", "Enuma Elish 1"),   # chunks of lines
    ("Iliad 1:5", "Iliad 1:1", "Iliad 1:10", "Iliad 1"),
    ("Rig Veda 10.121:9", "Rig Veda 10.121:8", "Rig Veda 10.121:10", "Rig Veda 10.121"),
    ("Gita 2:47", "Bhagavad Gita 2:46", "Bhagavad Gita 2:48", "Bhagavad Gita 2"),
])
def test_neighbours(lookup, ref, prev, nxt, chapter):
    r = lookup.get_verse(ref)
    near = lookup.neighbours(r["reference"])
    assert (near["prev"], near["next"], near["chapter"]) == (prev, nxt, chapter)
    for target in filter(None, (prev, nxt, chapter)):
        assert lookup.get_verse(target)["found"], target


def test_the_last_verse_of_a_chapter_leads_into_the_next(lookup):
    assert lookup.neighbours("John 3:36")["next"] == "John 4:1"
    assert lookup.neighbours("John 4:1")["prev"] == "John 3:36"


def test_nothing_to_step_through_outside_the_library(lookup):
    assert lookup.neighbours("John 3:16 (ESV)") == {}
    assert lookup.neighbours("Mishnah Berakhot 1:1") == {}
    assert lookup.neighbours("not a reference") == {}


def test_pages_are_a_phone_screen_and_lose_nothing():
    from core import PASSAGE_PAGE, passage_pages
    verses = "\n".join(f"**[{i}]** " + "word " * 60 for i in range(1, 30))
    one_long_verse = "A sentence that goes on. " * 300
    for text in (verses, one_long_verse, "short"):
        pages = passage_pages(text)
        assert all(len(p) <= PASSAGE_PAGE for p in pages)
        assert re.sub(r"\s+", "", "".join(pages)) == re.sub(r"\s+", "", text)
    assert all(p.startswith("**[") for p in passage_pages(verses))          # broken between verses


def test_buttons_under_a_passage(bot_module):
    from bot_commands.verse import passage_buttons
    from core import lookup
    kinds = [b.kind for b in passage_buttons(lookup.get_verse("Timaeus 67"))]
    assert kinds == ["p", "n"]
    kinds = [b.kind for b in passage_buttons(lookup.get_verse("John 3:16"))]
    assert kinds == ["p", "n", "c"]
    assert all(len(b.custom_id) <= 100 for b in passage_buttons(lookup.get_verse("John 3:16")))
