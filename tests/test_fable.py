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
    assert fable.parse("fox")[0] == "*|t:fox"                      # (every collection's)
    foxes = fable.pool("t:fox")                                     # (a spec from before the collections: Aesop's)
    assert len(foxes) > 20 and all(c == "" and "Fox" in fable.title(n) for c, n in foxes)
    assert len(fable.pool("*|t:fox")) > len(foxes) and {c for c, _ in fable.pool("*|t:fox")} >= {"", "lf", "ph"}
    assert fable.pool(fable.parse("lion and mouse")[0]) == [("", 1)]
    assert fable.parse("strong ropes")[0] == "*|w:strong ropes" and ("", 1) in fable.pool("*|w:strong ropes")
    assert fable.pool(fable.parse("asdfghjkl")[0]) == []
    donkeys = fable.pool(fable.parse("donkey")[0])                  # Townsend's "Ass"
    assert donkeys == fable.pool("*|t:ass") and len(donkeys) > 10
    assert fable.pool(fable.parse("donkey and grasshopper")[0]) == fable.pool(fable.parse("ass and grasshopper")[0])
    assert fable.parse("the and")[0].startswith("*|w:")            # nothing but little words


def test_the_collections(fable):
    assert len(fable.numbers("lf")) == 240 and fable.title(1, "lf") == "The Grasshopper and the Ant"
    assert len(fable.numbers("ph")) == 124 and fable.title(1, "ph") == "The Wolf and the Lamb"
    assert fable.paragraphs(1, "ph")[0] == "(Book I, Fable 1)"
    assert fable.collection_named("la fontaine wolf") == ("lf", "wolf")
    assert fable.collection_named("krilof") == ("kr", "")
    assert fable.collection_named("fox") == (None, "fox")
    assert all(fable.chapters(c) for c in fable.COLLECTIONS), [c for c in fable.COLLECTIONS if not fable.chapters(c)]
    assert fable.parse("wolf", "lf")[0] == "lf|t:wolf" and all(c == "lf" for c, _ in fable.pool("lf|t:wolf"))
    m = fable.message(64, spec="lf|t:wolf", code="lf")              # (two pages: both ◀ ▶, the ids apart)
    ids = [c.custom_id for c in m["view"].children]
    assert ids[:2] == ["fable:back:lf64:p1:lf|t:wolf", "fable:next:lf64:p1:lf|t:wolf"] and len(set(ids)) == len(ids)
    for code in fable.COLLECTIONS:
        for n in fable.numbers(code):
            assert all(len(p) <= 4096 for p in fable.pages(n, code)), (code, n)
    assert fable.tradition_of("") == fable.tradition_of("ph") == "classical" and fable.tradition_of("lf") == "ballads"


def test_old_buttons_still_mean_aesop(fable):
    m = re.fullmatch(fable.FableButton.__discord_ui_compiled_template__, "fable:again:196:t:fox and grapes")
    assert m and m["n"] == "196" and m["spec"] == "t:fox and grapes" and m["page"] is None


def test_message_and_buttons(fable):
    m = fable.message(1)
    assert m["embed"].title.endswith("The Lion and the Mouse") and m["embed"].description == fable.body(1)
    labels = [c.item.label for c in m["view"].children]
    assert labels[:2] == ["Another", "Card"] and labels[2:] in ([], ["Pictures"])   # (Crane's and Winter's)
    assert all(len(c.custom_id) <= 100 for c in fable.message(1, spec="w:" + "x" * 60)["view"].children)
    pages = fable.list_message(0)
    assert pages["embed"].description.startswith("`1` The Lion and the Mouse")
    assert len(pages["embed"].description) < 4096 and len({c.custom_id for c in pages["view"].children}) == 2


def test_another_never_repeats_and_owns_up_when_there_is_only_one(fable):
    """Ten presses of 🎲 on fox and grapes brought the same fable back ten times."""
    spec = "t:fox and grapes"                                       # (Aesop's alone has one)
    ((code, only),) = fable.pool(spec)
    for _ in range(20):
        m = fable.another(code, only, spec)
        assert m["embed"].title != f"🦊 {fable.title(only)}"
        assert m["embed"].author.name == "Sorry, that's the only fable with “fox and grapes”. Here's a random fable instead."
    foxes = fable.pool("t:fox")
    for _ in range(20):
        m = fable.another(*foxes[0], "t:fox")
        assert m["embed"].title != f"🦊 {fable.title(foxes[0][1])}" and "Fox" in m["embed"].title and not m["embed"].author


def test_card(fable):
    from PIL import Image
    longest = max(fable.numbers(), key=lambda n: len(fable.body(n)))
    for n in (1, longest):
        assert Image.open(fable.render_card(n)).size[0] == 1200


def test_verse_reads_it_too(lookup):
    r = lookup.get_verse("Aesop 12")
    assert r["found"] and "Hare and the Tortoise" in r["text"]
    assert lookup.neighbours(r["reference"])["next"] == "Aesop's Fables 13"
