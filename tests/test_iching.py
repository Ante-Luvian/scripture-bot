"""!iching: casting, changing lines, the reading, and its card."""
import asyncio
import random

import pytest


@pytest.fixture(scope="module")
def oracles(bot_module):
    from bot_commands import oracles
    return oracles


def test_every_hexagram_is_known_and_unique(oracles):
    meta = oracles._iching_meta()
    assert len(meta) == 64 and len({tuple(h["lines"]) for h in meta.values()}) == 64
    assert meta["1"]["lines"] == [1] * 6 and meta["2"]["lines"] == [0] * 6
    assert meta["11"]["lines"] == [1, 1, 1, 0, 0, 0]          # Tai: heaven below, earth above


def test_coins_give_six_to_nine(oracles):
    rng = random.Random(1)
    values = [v for _ in range(200) for v in oracles.cast_lines(rng)]
    assert set(values) == {6, 7, 8, 9}


def test_changing_lines_flip_into_a_second_hexagram(oracles):
    assert oracles.iching_reading([7, 7, 7, 7, 7, 7]) == {"hexagram": "1", "moving": [], "becomes": None}
    # all old yang: Qian (1) becomes Kun (2)
    assert oracles.iching_reading([9] * 6) == {"hexagram": "1", "moving": [1, 2, 3, 4, 5, 6], "becomes": "2"}
    # Tai (11) with its bottom line changing becomes Sheng (46): wind below, earth above
    assert oracles.iching_reading([9, 7, 7, 8, 8, 8]) == {"hexagram": "11", "moving": [1], "becomes": "46"}


def test_figure_is_drawn_top_line_first(oracles):
    rows = oracles._hexagram_figure([9, 7, 7, 8, 8, 6]).strip("`\n").splitlines()
    assert rows[0] == "━━━━   ━━━━  ✕ changing" and rows[-1] == "━━━━━━━━━━━  ○ changing"


def test_the_reading(oracles, fake_ctx, monkeypatch):
    monkeypatch.setattr(oracles, "cast_lines", lambda: [9, 7, 7, 8, 8, 8])
    asyncio.run(oracles.cmd_iching.callback(fake_ctx, question="should I move house?"))
    msg = fake_ctx.sent[0]
    embed = msg["embed"]
    assert embed.title == "☯️ 11. Tài 泰 — Peace" and embed.author.name == "❓ should I move house?"
    assert "The Judgment:" in embed.description and "The Image:" in embed.description
    names = [f.name for f in embed.fields]
    assert names[0] == "Changing line 1" and names[1].startswith("Becoming 46.")
    assert msg["view"].children[0].custom_id == "ocard:iching:11:1"


def test_hafez(oracles, fake_ctx, lookup):
    asyncio.run(oracles.cmd_hafez.callback(fake_ctx, question="will she return?"))
    msg = fake_ctx.sent[0]
    num = msg["embed"].title.rsplit(" ", 1)[1]
    assert msg["embed"].title.startswith("🌹 Fāl-e Hāfez — Poem ") and 1 <= int(num) <= 43
    assert msg["embed"].author.name == "❓ will she return?"
    assert msg["view"].children[0].custom_id == f"ocard:hafez:{num}"
    title, stanza, source = oracles._oracle_card_content("hafez", "1")
    assert stanza.startswith("Arise, oh Cup-bearer, rise!") and "Bell" in source
    r = lookup.get_verse("Hafez 1:1")
    assert r["found"] and "Arise, oh Cup-bearer" in r["text"]


def test_rumi(oracles, fake_ctx, lookup):
    import random
    for seed in range(20):                     # always couplets, never a story's prose summary
        key, text = oracles.rumi_passage(random.Random(seed))
        assert "\n" in text and not text.startswith("*") and lookup.get_verse(f"Masnavi {key}")["found"]
    asyncio.run(oracles.cmd_rumi.callback(fake_ctx, question="what should I do?"))
    msg = fake_ctx.sent[0]
    assert msg["embed"].title.startswith("🌹 The Masnavi — Book ")
    assert msg["embed"].author.name == "❓ what should I do?"
    key = msg["view"].children[0].custom_id.removeprefix("ocard:rumi:")
    assert msg["embed"].description.strip("*") == lookup._data["sufi"]["Masnavi"][key.split(":")[0]][key.split(":")[1]]
    assert oracles._rumi_parts("1.0:2")[0] == "Book 1, Prologue"
    assert oracles._rumi_parts("1.1:2")[2] == "The Prince and the Handmaid"
    title, text, source = oracles._oracle_card_content("rumi", "1.0:2")
    assert title == "The Masnavi — Book 1, Prologue" and "Whinfield" in source


def test_card_content(oracles):
    title, text, source = oracles._oracle_card_content("iching", "11:1")
    assert title.startswith("I Ching — 11. Tài") and "Legge" in source
    assert not text.startswith("The Judgment") and text.count("\n\n") == 1      # judgment + one changing line
    assert oracles._oracle_card_content("iching", "99:") is None
