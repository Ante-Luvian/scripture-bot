"""Drive the real !verse command with a stand-in Discord context (no network,
no Discord connection)."""
import asyncio

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


def test_plain_verse_lookup_sends_result(verse, monkeypatch, fake_ctx):
    """The ordinary local path, end to end through _send_result."""
    monkeypatch.setattr(verse, "_get_preferred_translation", lambda user_id: None)
    asyncio.run(verse.verse_prefix.callback(fake_ctx, reference="John 3:16"))
    assert fake_ctx.sent, "nothing was sent"
    text = " ".join(str(m.get("content") or "") + str(m["embed"].to_dict() if m.get("embed") else "")
                    for m in fake_ctx.sent)
    assert "For God so loved the world" in text
