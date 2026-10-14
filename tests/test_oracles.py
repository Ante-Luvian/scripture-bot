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
    return [c.item.label for c in msg["view"].children] if msg.get("view") else []


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
    assert _labels(msg) == ["Notes", "Cross-refs", "Interlinear", "Card", "Catena"]   # it's a Bible verse


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


@pytest.mark.parametrize("kind, key, title", [
    ("virgil", "6.851", "Sortes Vergilianae — Aeneid 6.851"),
    ("delphi", "1", "Delphic Maxim 1"),
    ("oracle", "Delphic Maxims|1", "Delphic Maxims — 1"),
])
def test_oracle_card_content_is_looked_up_again(oracles, kind, key, title):
    got_title, text, source = oracles._oracle_card_content(kind, key)
    assert got_title == title and text and source


def test_oracle_card_content_homer(oracles, monkeypatch):
    monkeypatch.setattr(oracles, "_load_homer", lambda: {"123": "Be bold."})
    assert oracles._oracle_card_content("homer", "1-2-3") == ("Homeromanteion — 1-2-3", "Be bold.", oracles.HOMER_SOURCE)
    assert oracles._oracle_card_content("homer", "6-6-6") is None
    assert oracles._oracle_card_content("oracle", "no separator") is None


def test_oracle_card_button_survives_restart_and_renders(oracles, bot_module):
    """Press the Card button as Discord delivers it after a restart: rebuilt
    from its custom_id alone. It must render a real PNG, once."""
    store = bot_module.bot._connection._view_store
    assert oracles.OracleCardButton.__discord_ui_compiled_template__ in store._dynamic_items

    sent, edited = [], []

    class Response:
        async def edit_message(self, view=None): edited.append(view)

    class Followup:
        async def send(self, *a, **kw): sent.append(kw)

    original = oracles._card_view("delphi", "1").children[0]
    match = oracles.OracleCardButton.__discord_ui_compiled_template__.fullmatch(original.item.custom_id)
    interaction = type("I", (), {"response": Response(), "followup": Followup(),
                                 "message": type("M", (), {"embeds": []})()})()
    rebuilt = asyncio.run(oracles.OracleCardButton.from_custom_id(interaction, original.item, match))
    asyncio.run(rebuilt.callback(interaction))

    assert edited[0].timeout is None and edited[0].children[0].item.disabled   # one image per answer
    assert sent[0]["file"].filename == "oracle.png"
    assert sent[0]["file"].fp.read(8) == b"\x89PNG\r\n\x1a\n"   # a real PNG was rendered


def test_question_heads_the_answer_and_its_card(oracles, fake_ctx):
    asyncio.run(oracles.cmd_delphi.callback(fake_ctx, question="Will I find work?"))
    msg = fake_ctx.sent[0]
    assert msg["embed"].author.name == "❓ Will I find work?"
    assert oracles._question_from(type("M", (), {"embeds": [msg["embed"]]})()) == "Will I find work?"
    # the card renders with the question on it
    buf = oracles._render_verse_card("Delphic Maxim 1", "Follow God.", "Delphic Maxims", "Will I find work?")
    assert buf.read(8) == b"\x89PNG\r\n\x1a\n"


def test_no_question_no_author_line(oracles, fake_ctx):
    asyncio.run(oracles.cmd_delphi.callback(fake_ctx))
    assert not fake_ctx.sent[0]["embed"].author.name


def test_oracle_views_never_time_out(oracles, monkeypatch, fake_ctx):
    # A view that times out unregisters its persistent buttons bot-wide
    asyncio.run(oracles.cmd_delphi.callback(fake_ctx))
    assert fake_ctx.sent[0]["view"].timeout is None
