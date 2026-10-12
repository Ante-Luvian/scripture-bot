"""Drive the real !verse command with a stand-in Discord context (no network,
no Discord connection)."""
import asyncio

import pytest


class FakeCtx:
    """Just enough of commands.Context for the code paths exercised here."""

    def __init__(self):
        self.sent = []
        self.author = type("Author", (), {"id": 1, "__str__": lambda self: "tester"})()

    async def send(self, content=None, **kwargs):
        self.sent.append({"content": content, **kwargs})

    def typing(self):
        class _Typing:
            async def __aenter__(self): return self
            async def __aexit__(self, *exc): return False
        return _Typing()


@pytest.fixture(scope="module")
def verse(bot_module):
    from bot_commands import verse
    return verse


def test_multi_translation_verse_sends_parallel_embed(verse, monkeypatch):
    """Regression: `!verse John 3:16 kjv web` raised TypeError, because the
    2-arg sender it called was shadowed by !parallel's 3-arg _send_parallel."""
    calls = []

    def fake_get_parallel(ref, translations):
        calls.append((ref, translations))
        return {"found": True, "reference": "John 3:16",
                "parallel": [("KJV", "King James Version", "For God so loved the world"),
                             ("WEB", "World English Bible", "For God so loved the world")]}

    monkeypatch.setattr(verse, "get_parallel", fake_get_parallel)
    ctx = FakeCtx()
    asyncio.run(verse.verse_prefix.callback(ctx, reference="John 3:16 kjv web"))

    assert calls == [("John 3:16", ["kjv", "web"])]
    assert len(ctx.sent) == 1
    embed = ctx.sent[0]["embed"]
    assert embed.title == "📖 John 3:16"
    assert [f.name for f in embed.fields] == ["**KJV**", "**WEB**"]
    assert embed.footer.text == "King James Version · World English Bible"


def test_multi_translation_verse_error(verse, monkeypatch):
    monkeypatch.setattr(verse, "get_parallel",
                        lambda ref, tr: {"found": False, "error": "Unknown book: **Notabook**"})
    ctx = FakeCtx()
    asyncio.run(verse.verse_prefix.callback(ctx, reference="Notabook 1:1 kjv web"))
    assert ctx.sent[0]["embed"].description == "Unknown book: **Notabook**"


def test_plain_verse_lookup_sends_result(verse, monkeypatch):
    """The ordinary local path, end to end through _send_result."""
    monkeypatch.setattr(verse, "_get_preferred_translation", lambda user_id: None)
    ctx = FakeCtx()
    asyncio.run(verse.verse_prefix.callback(ctx, reference="John 3:16"))
    assert ctx.sent, "nothing was sent"
    text = " ".join(str(m.get("content") or "") + str(m["embed"].to_dict() if m.get("embed") else "")
                    for m in ctx.sent)
    assert "For God so loved the world" in text
