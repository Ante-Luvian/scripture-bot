"""!edda: a stanza of the Poetic Edda, with a card, ◀ ▶, and the poem's pictures (the owner's request, 2026-11-07)."""
import asyncio
import random

import pytest


@pytest.fixture(scope="module")
def oracles(bot_module):
    from bot_commands import oracles
    return oracles


def test_picks(oracles):
    rng = random.Random(1)
    assert oracles._edda_pick("havamal 138", rng) == ("Hovamol", "138")
    poem, stanza = oracles._edda_pick("Sayings of the High One", rng)
    assert poem == "Hovamol"
    assert oracles._edda_pick("lokasenna 999", rng).startswith("**Lokasenna** has stanzas")
    assert oracles._edda_pick("will it rain?", rng)[0] in oracles._edda()          # (a question: any poem)
    assert set(oracles.EDDA_ENGLISH) == set(oracles._edda())                       # (every poem's English title)


def test_the_card(oracles):
    title, text, source = oracles._oracle_card_content("edda", "Hovamol|138")
    assert title.startswith("Hovamol (The Sayings of the High One), stanza 138") and "Hail to the speaker" in text
    assert "Bellows" in source and oracles._oracle_card_content("edda", "Hovamol|9999") is None


def test_the_reply_and_its_buttons(oracles, fake_ctx):
    asyncio.run(oracles.cmd_edda.callback(fake_ctx, query="havamal 138"))
    sent = fake_ctx.sent[0]
    assert "stanza 138" in sent["embed"].title
    ids = [getattr(getattr(item, "item", item), "custom_id", "") or "" for item in sent["view"].children]
    assert any(i.startswith("ocard:edda:Hovamol|138") for i in ids)
    assert any(i.startswith("pnav:p:") for i in ids) and any(i.startswith("pnav:n:") for i in ids)
    assert any(i.startswith("pics:") for i in ids)                                 # (Collingwood's Hávamál)


def test_the_pictures(bot_module):
    from bot_commands import illustrations
    found = illustrations.for_passage("Voluspo", "57")                             # (a whole poem's: any stanza)
    assert {p["artist"] for p in found} == {"W. G. Collingwood", "Lorenz Frølich"}
    assert illustrations.reference(found[0]) == "Voluspo"
