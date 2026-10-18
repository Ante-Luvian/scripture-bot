"""!dore: Gustave Doré's engravings, and the 🖼️ Doré button under !verse."""
import asyncio
import re

import pytest


@pytest.fixture(scope="module")
def do(bot_module):
    from bot_commands import dore
    return dore


def test_the_whole_set(do, lookup):
    plates = do.plates()
    bible = [p for p in plates if p["set"] == "bible"]
    assert len(bible) == 241                                   # all of the 1866 Bible's plates
    assert {"Tobit", "Judith", "Baruch", "Susanna", "Bel and the Dragon", "1 Maccabees", "2 Maccabees"} \
        <= {p["book"] for p in bible}                         # the Apocrypha too
    assert sum(p["set"] == "milton" for p in plates) == 50
    assert sum(p["set"] == "dante" for p in plates) >= 130
    for p in plates:
        assert re.match(r"https://[a-z.]+\.wikimedia\.org/", p["image"]), p["key"]
    for p in bible:                                            # every reference opens in the bot
        assert lookup.get_verse(f"{p['book']} {p['chapter']}:{p['start']}")["found"], p["key"]
    assert len({p["key"] for p in plates}) == len(plates)


@pytest.mark.parametrize("ref, title", [
    ("Genesis 11:4", "The Tower of Babel"), ("Judith 13:8", "Judith and Holofernes"),
    ("Paradise Lost 12:644", "Paradise Lost 12:644"), ("Mark 14:22", "The Last Supper"),
])
def test_the_button_under_verse(do, lookup, ref, title):
    button = do.dore_button(lookup.get_verse(ref))
    assert button is not None and button.item.custom_id.startswith("dore:")
    shown = [do.by_key()[k] for k in button.keys]
    assert any(do.plate_embed(p).title == f"🖼️ {title}" for p in shown)


def test_no_button_without_an_engraving(do, lookup):
    assert do.dore_button(lookup.get_verse("John 3:16")) is None
    assert do.dore_button(lookup.get_verse("Leviticus 3:1")) is None


def test_dante_by_canto(do, lookup):
    button = do.dore_button(lookup.get_verse("Inferno 3:1"))
    assert button and all(do.by_key()[k]["chapter"] == 3 for k in button.keys)


@pytest.mark.parametrize("query, first", [("Genesis 11", "🖼️ The Tower of Babel"), ("flood", None),
                                          ("Inferno 3", "🖼️ Inferno, Canto 3"), ("Paradise Lost 1", "🖼️ Paradise Lost 1:44–45")])
def test_the_command(do, fake_ctx, query, first):
    asyncio.run(do.send_dore(fake_ctx, query))
    sent = fake_ctx.sent[-1]
    embeds = sent.get("embeds") or [sent["embed"]]
    assert 1 <= len(embeds) <= do.MAX_SHOWN
    assert first is None or embeds[0].title == first
    assert all(e.image.url for e in embeds)


def test_nothing_found(do, fake_ctx):
    asyncio.run(do.send_dore(fake_ctx, "Leviticus 3"))
    assert "no engraving" in fake_ctx.sent[-1]["content"]
    asyncio.run(do.send_dore(fake_ctx, "zzzq"))
    assert "don't have a Doré engraving" in fake_ctx.sent[-1]["content"]


def test_the_button_survives_a_study_button(bot_module):
    """Pressing Notes rebuilds the buttons from the message: the Doré button must come back too."""
    from bot_commands import verse
    import types
    rows = [types.SimpleNamespace(children=[types.SimpleNamespace(custom_id="study:notes:Genesis 11:4", disabled=False),
                                            types.SimpleNamespace(custom_id="dore:b010", disabled=False)])]
    view = verse._study_view_from_message(types.SimpleNamespace(components=rows), "study:notes:Genesis 11:4")
    assert [c.custom_id for c in view.children] == ["study:notes:Genesis 11:4", "dore:b010"]
