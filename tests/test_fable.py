"""!fable: Aesop's Fables (Townsend, Gutenberg #21), at random, by title word, by number, as a card."""
import re

import pytest


@pytest.fixture(scope="module")
def fable(bot_module):
    from bot_commands import fable
    return fable


def test_all_313_fables_are_there_whole(fable):
    assert fable.numbers() == list(range(1, 314))
    assert fable.title(1) == "The Lion and the Mouse"
    assert "bound him by strong ropes" in fable.body(1)          # (sacred-texts' copy: "by st ropes")
    assert fable.title(12) == "The Hare and the Tortoise"
    assert all(fable.body(n) and not fable.body(n).startswith("*") for n in fable.numbers())


def test_titles_read_consistently(fable):
    assert not [fable.title(n) for n in fable.numbers() if re.search(r" (And|The|Of|His) ", fable.title(n))]


def test_choosing(fable):
    assert fable.parse("fox")[0] == "t:fox"
    foxes = fable.pool("t:fox")
    assert len(foxes) > 20 and all("Fox" in fable.title(n) for n in foxes)
    assert fable.pool(fable.parse("lion and mouse")[0]) == [1]
    assert fable.parse("strong ropes")[0] == "w:strong ropes" and 1 in fable.pool("w:strong ropes")
    assert fable.pool(fable.parse("asdfghjkl")[0]) == []
    donkeys = fable.pool(fable.parse("donkey")[0])                  # Townsend's "Ass"
    assert donkeys == fable.pool("t:ass") and len(donkeys) > 10
    assert fable.pool(fable.parse("donkey and grasshopper")[0]) == fable.pool(fable.parse("ass and grasshopper")[0])
    assert fable.parse("the and")[0].startswith("w:")              # nothing but little words


def test_message_and_buttons(fable):
    m = fable.message(1)
    assert m["embed"].title.endswith("The Lion and the Mouse") and m["embed"].description == fable.body(1)
    assert [c.item.label for c in m["view"].children] == ["Another", "Card"]
    assert all(len(c.custom_id) <= 100 for c in fable.message(1, spec="w:" + "x" * 60)["view"].children)
    pages = fable.list_message(0)
    assert pages["embed"].description.startswith("`1` The Lion and the Mouse")
    assert len(pages["embed"].description) < 4096 and len({c.custom_id for c in pages["view"].children}) == 2


def test_another_never_repeats_and_owns_up_when_there_is_only_one(fable):
    """Ten presses of 🎲 on fox and grapes brought the same fable back ten times."""
    spec = fable.parse("fox and grapes")[0]
    (only,) = fable.pool(spec)
    for _ in range(20):
        m = fable.another(only, spec)
        assert m["embed"].title != f"🦊 {fable.title(only)}"
        assert m["embed"].author.name == "Sorry, that's the only fable with “fox and grapes”. Here's a random fable instead."
    foxes = fable.pool("t:fox")
    for _ in range(20):
        m = fable.another(foxes[0], "t:fox")
        assert m["embed"].title != f"🦊 {fable.title(foxes[0])}" and "Fox" in m["embed"].title and not m["embed"].author


def test_card(fable):
    from PIL import Image
    longest = max(fable.numbers(), key=lambda n: len(fable.body(n)))
    for n in (1, longest):
        assert Image.open(fable.render_card(n)).size[0] == 1200


def test_verse_reads_it_too(lookup):
    r = lookup.get_verse("Aesop 12")
    assert r["found"] and "Hare and the Tortoise" in r["text"]
    assert lookup.neighbours(r["reference"])["next"] == "Aesop's Fables 13"
