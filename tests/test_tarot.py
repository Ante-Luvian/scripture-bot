"""!tarot: the Rider tarot, with Waite's meanings."""
import asyncio
import random

import pytest


@pytest.fixture(scope="module")
def ta(bot_module):
    from bot_commands import tarot
    return tarot


def test_the_whole_deck(ta):
    deck = ta.cards()
    assert len(deck) == 78 and [c["name"] for c in deck[:2]] == ["The Fool", "The Magician"]
    for card in deck:
        assert (ta.TAROT_DIR / card["file"]).stat().st_size > 20_000, card["name"]
        assert len(card["description"]) > 20 and card["upright"], card["name"]
        assert card["reversed"] or card["name"] == "Two of Cups", card["name"]           # (Waite gives none for it)
        assert "Reversed" not in card["upright"] and "Next:" not in card["reversed"], card["name"]


@pytest.mark.parametrize("query, name", [
    ("the tower", "The Tower"), ("Tower", "The Tower"), ("0", "The Fool"), ("13", "Death"),
    ("ten of wands", "Ten of Wands"), ("10 cups", "Ten of Cups"), ("queen of coins", "Queen of Pentacles"),
    ("ace of swords", "Ace of Swords"), ("knight rods", "Knight of Wands"), ("judgment", "Judgement"),
    ("wheel of fortune", "Wheel of Fortune"),
])
def test_find(ta, query, name):
    assert ta.find(query)["name"] == name


def test_find_nothing(ta):
    assert ta.find("eleven of wands") is None and ta.find("zz") is None


def test_a_drawn_card_shows_its_meaning(ta):
    card = ta.find("the sun")
    upright = ta.card_embed(card, False)
    assert upright.fields[0].name == "It means" and upright.fields[0].value.startswith("Material happiness")
    rev = ta.card_embed(card, True)
    assert rev.title == "The Sun (reversed)" and rev.fields[0].name == "Reversed, it means"
    looked_up = ta.card_embed(card)
    assert [f.name for f in looked_up.fields] == ["Upright", "Reversed"]


def test_spreads(ta, fake_ctx):
    random.seed(3)
    asyncio.run(ta.send_tarot(fake_ctx, "celtic"))
    sent = fake_ctx.sent[-1]
    assert len(sent["embeds"]) == 10 and len(sent["files"]) == 10
    assert len({e.title.split(" — ")[1].removesuffix(" (reversed)") for e in sent["embeds"]}) == 10   # no card twice
    assert sum(len(e) for e in sent["embeds"]) <= 6000
    asyncio.run(ta.send_tarot(fake_ctx, "three"))
    assert [e.title.split(" — ")[0] for e in fake_ctx.sent[-1]["embeds"]] == ta.THREE


def test_draw_and_errors(ta, fake_ctx):
    asyncio.run(ta.send_tarot(fake_ctx, ""))
    assert fake_ctx.sent[-1]["content"] == "🃏 **Your card**"
    asyncio.run(ta.send_tarot(fake_ctx, "the moon"))
    assert fake_ctx.sent[-1]["embed"].title == "The Moon"
    asyncio.run(ta.send_tarot(fake_ctx, "zzz"))
    assert "don't know a card" in fake_ctx.sent[-1]["content"]
