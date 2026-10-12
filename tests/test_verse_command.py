"""Drive the real !verse command with a stand-in Discord context (no network,
no Discord connection)."""
import asyncio

import discord
import pytest


@pytest.fixture(scope="module")
def verse(bot_module):
    from bot_commands import verse
    return verse


def test_multi_translation_verse_sends_parallel_embed(verse, monkeypatch, fake_ctx):
    """Regression: `!verse John 3:16 kjv web` raised TypeError, because the
    2-arg sender it called was shadowed by !parallel's 3-arg _send_parallel."""
    calls = []

    def fake_get_parallel(ref, translations):
        calls.append((ref, translations))
        return {"found": True, "reference": "John 3:16",
                "parallel": [("KJV", "King James Version", "For God so loved the world"),
                             ("WEB", "World English Bible", "For God so loved the world")]}

    monkeypatch.setattr(verse, "get_parallel", fake_get_parallel)
    asyncio.run(verse.verse_prefix.callback(fake_ctx, reference="John 3:16 kjv web"))

    assert calls == [("John 3:16", ["kjv", "web"])]
    assert len(fake_ctx.sent) == 1
    embed = fake_ctx.sent[0]["embed"]
    assert embed.title == "📖 John 3:16"
    assert [f.name for f in embed.fields] == ["**KJV**", "**WEB**"]
    assert embed.footer.text == "King James Version · World English Bible"


def test_multi_translation_verse_error(verse, monkeypatch, fake_ctx):
    monkeypatch.setattr(verse, "get_parallel",
                        lambda ref, tr: {"found": False, "error": "Unknown book: **Notabook**"})
    asyncio.run(verse.verse_prefix.callback(fake_ctx, reference="Notabook 1:1 kjv web"))
    assert fake_ctx.sent[0]["embed"].description == "Unknown book: **Notabook**"


# ── study buttons ───────────────────────────────────────────────────────────

def _labels(buttons):
    return [b.label for b in buttons]


@pytest.mark.parametrize("reference, labels", [
    ("John 3:16",          ["Notes", "Cross-refs", "Interlinear", "Card"]),
    ("John 3:16–18",       ["Notes", "Cross-refs", "Interlinear", "Card"]),
    ("John 3:1–9",         ["Cross-refs", "Interlinear", "Card"]),   # !notes takes up to 5 verses
    ("John 3:16 (ESV)",    ["Notes", "Cross-refs", "Interlinear", "Card"]),
    ("1 Corinthians 13:4", ["Notes", "Cross-refs", "Interlinear", "Card"]),
    ("Psalms 23",          []),   # whole chapter
    ("Quran 1:1",          []),   # not the Bible
    ("Tobit 1:1",          []),   # apocrypha: no NET notes / Strong's
    ("Book of Enoch 1:9",  []),
])
def test_study_buttons_only_for_bible_verses(verse, reference, labels):
    assert _labels(verse._study_buttons({"found": True, "reference": reference})) == labels


def test_no_study_buttons_on_errors(verse):
    assert verse._study_buttons({"found": False, "error": "nope"}) == []


class _FakeResponse:
    def __init__(self):
        self.edited_view = None

    async def edit_message(self, view=None):
        self.edited_view = view

    async def defer(self):
        pass


def test_study_button_runs_its_command_once(verse, monkeypatch):
    calls = []

    async def fake_xref(ctx, reference=""):
        calls.append((ctx, reference))

    class FakeBot:
        async def get_context(self, interaction):
            return "ctx-from-interaction"

    monkeypatch.setattr(verse, "cmd_xref", fake_xref)
    monkeypatch.setattr(verse, "bot", FakeBot())
    buttons = verse._study_buttons({"found": True, "reference": "John 3:16–18 (ESV)"})
    xref = next(b for b in buttons if b.label == "Cross-refs")
    view = discord.ui.View()
    for b in buttons:
        view.add_item(b)

    interaction = type("I", (), {"response": _FakeResponse()})()
    asyncio.run(xref.callback(interaction))

    assert calls == [("ctx-from-interaction", "John 3:16-18")]   # translation suffix dropped
    assert xref.disabled and interaction.response.edited_view is view


def test_verse_command_attaches_study_buttons(verse, monkeypatch, fake_ctx):
    monkeypatch.setattr(verse, "_get_preferred_translation", lambda user_id: None)
    asyncio.run(verse.verse_prefix.callback(fake_ctx, reference="John 3:16"))
    view = fake_ctx.sent[0]["view"]
    assert [c.label for c in view.children] == ["Notes", "Cross-refs", "Interlinear", "Card"]


def test_plain_verse_lookup_sends_result(verse, monkeypatch, fake_ctx):
    """The ordinary local path, end to end through _send_result."""
    monkeypatch.setattr(verse, "_get_preferred_translation", lambda user_id: None)
    asyncio.run(verse.verse_prefix.callback(fake_ctx, reference="John 3:16"))
    assert fake_ctx.sent, "nothing was sent"
    text = " ".join(str(m.get("content") or "") + str(m["embed"].to_dict() if m.get("embed") else "")
                    for m in fake_ctx.sent)
    assert "For God so loved the world" in text
