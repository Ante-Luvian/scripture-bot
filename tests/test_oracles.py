"""Oracles: !sortesbiblicae, and the 🖼️ Card button on every oracle answer."""
import asyncio

import pytest


@pytest.fixture(scope="module")
def oracles(bot_module):
    from bot_commands import oracles
    return oracles


@pytest.fixture(autouse=True)
def no_stats(oracles, monkeypatch):
    monkeypatch.setattr(oracles, "record_special_stat", lambda *a: None)


def _labels(msg):
    return [c.label for c in msg["view"].children] if msg.get("view") else []


def test_sortes_biblicae(oracles, monkeypatch, fake_ctx):
    monkeypatch.setattr(oracles.lookup, "random_verse_from_books", lambda books: {
        "found": True, "reference": "Isaiah 40:31", "book": "Isaiah", "chapter": "40", "verse": "31",
        "text": "But they that wait upon the Lord shall renew their strength", "source": "King James Version"})
    asyncio.run(oracles.cmd_sortes_biblicae.callback(fake_ctx))
    msg = fake_ctx.sent[0]
    embed = msg["embed"]
    assert embed.title == "Sortes Biblicae"
    assert embed.description.startswith("📖 Isaiah  🕯️ 40:31  👈")
    assert "*But they that wait upon the Lord shall renew their strength*" in embed.description
    assert embed.footer.text == "Isaiah 40:31 — King James Version"
    assert _labels(msg) == ["Notes", "Cross-refs", "Interlinear", "Card"]   # it's a Bible verse


def test_sortes_biblicae_draws_only_from_the_bible(oracles, monkeypatch, fake_ctx):
    seen = []
    monkeypatch.setattr(oracles.lookup, "random_verse_from_books",
                        lambda books: seen.append(books) or {"found": False, "error": "x"})
    asyncio.run(oracles.cmd_sortes_biblicae.callback(fake_ctx))
    assert seen[0] == oracles.BIBLE_OT + oracles.BIBLE_NT   # no apocrypha, no other corpora


@pytest.mark.parametrize("command", ["cmd_virgil", "cmd_homer", "cmd_delphi", "cmd_oracle"])
def test_oracle_answers_have_a_card_button(oracles, monkeypatch, fake_ctx, command):
    if command == "cmd_homer":   # make sure the dice land on a roll with an answer
        monkeypatch.setattr(oracles, "_load_homer", lambda: {"111": "Be bold."})
        monkeypatch.setattr(oracles.random, "randint", lambda a, b: 1)
    cmd = getattr(oracles, command)
    asyncio.run(cmd.callback(fake_ctx) if command == "cmd_delphi" else cmd.callback(fake_ctx, question=""))
    assert _labels(fake_ctx.sent[0]) == ["Card"]


def test_silent_homer_roll_has_no_card(oracles, monkeypatch, fake_ctx):
    monkeypatch.setattr(oracles, "_load_homer", lambda: {})
    asyncio.run(oracles.cmd_homer.callback(fake_ctx, question=""))
    msg = fake_ctx.sent[0]
    assert msg["embed"].title.startswith("The Oracle is Silent") and not msg.get("view")


def test_card_button_renders_an_image_once(bot_module):
    import discord
    from bot_commands.card import _make_card_image_button

    sent, edited = [], []

    class Response:
        async def edit_message(self, view=None): edited.append(view)
        async def defer(self): pass

    class Followup:
        async def send(self, **kw): sent.append(kw)

    btn = _make_card_image_button("Delphic Maxim 1", "Follow God.", "Delphic Maxims")
    view = discord.ui.View()
    view.add_item(btn)
    interaction = type("I", (), {"response": Response(), "followup": Followup()})()
    asyncio.run(btn.callback(interaction))

    assert btn.disabled and edited == [view]
    file = sent[0]["file"]
    assert file.filename == "oracle.png"
    assert file.fp.read(8) == b"\x89PNG\r\n\x1a\n"   # a real PNG was rendered
