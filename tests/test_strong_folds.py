"""!concordance, !root and !reverseinterlinear folded into !strong and !interlinear (2026-11-08):
the words that reach them, and the buttons that replaced them."""
import asyncio

import pytest


@pytest.fixture
def calls(bot_module, monkeypatch):
    from bot_commands import card, reference
    seen = []

    async def concordance(ctx, arg=""):
        seen.append(("verses", arg))

    async def root(ctx, arg=""):
        seen.append(("root", arg))

    async def reverse(ctx, reference=""):
        seen.append(("reverse", reference))

    monkeypatch.setattr(card, "send_concordance", concordance)
    monkeypatch.setattr(reference, "send_root", root)
    monkeypatch.setattr(card, "send_reverse_interlinear", reverse)
    return seen


@pytest.mark.parametrize("query, expected", [
    ("G26 verses", ("verses", "G26")),
    ("g26 occurrences", ("verses", "g26")),
    ("agape verses", ("verses", "agape")),
    ("G26 root", ("root", "G26")),
    ("love family", ("root", "love")),
    ("H6 cognates", ("root", "H6")),
])
def test_strong_reaches_the_verses_and_the_root(calls, fake_ctx, query, expected):
    from bot_commands import translations
    asyncio.run(translations.cmd_strong.callback(fake_ctx, query=query))
    assert calls == [expected]


def test_a_verse_with_a_number_is_still_a_tagged_verse(calls, fake_ctx, monkeypatch):
    from bot_commands import translations
    tagged = []

    async def strong_verse(ctx, ref):
        tagged.append(ref)
    monkeypatch.setattr(translations, "_send_compare_ancient_strong", strong_verse)
    asyncio.run(translations.cmd_strong.callback(fake_ctx, query="John 3:16"))
    assert tagged == ["John 3:16"] and calls == []


def test_an_unknown_word_says_so(bot_module, fake_ctx):
    from bot_commands import translations
    asyncio.run(translations.cmd_strong.callback(fake_ctx, query="xyzzyq"))
    assert "No Strong's entry matches **xyzzyq**" in fake_ctx.sent[-1]["content"]


@pytest.mark.parametrize("query", ["reverse John 3:16", "John 3:16 reverse", "KJV John 3:16", "english John 3:16"])
def test_interlinear_reverse(calls, fake_ctx, query):
    from bot_commands import card
    asyncio.run(card.cmd_interlinear.callback(fake_ctx, reference=query))
    assert calls == [("reverse", "John 3:16")]


def test_the_buttons_carry_what_they_need(bot_module):
    from bot_commands import card, translations
    flip = card.InterlinearFlipButton("rev", "John 3:16")
    assert flip.item.custom_id == "ilflip:rev:John 3:16" and flip.item.label == "English order"
    assert card.InterlinearFlipButton("orig", "John 3:16").item.label == "Original order"
    more = translations.StrongMoreButton("verses", "G26")
    assert more.item.custom_id == "strongx:verses:G26"
    assert translations.StrongMoreButton.__discord_ui_compiled_template__.fullmatch("strongx:root:H430")
