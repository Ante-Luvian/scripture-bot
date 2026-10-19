"""The bot runs on the owner's own computer: no one person can flood it with commands, fill its disk
with bookmarks, set off hundreds of downloads with one export, or steer a request's URL."""
import asyncio
import types

import pytest


def ctx_for(user_id, command):
    ctx = types.SimpleNamespace(author=types.SimpleNamespace(id=user_id), command=command, guild=None, sent=[])

    async def send(content=None, **kwargs):
        ctx.sent.append({"content": content, **kwargs})
    ctx.send = send
    return ctx


@pytest.fixture
def not_owner(bot_module, monkeypatch):
    import core

    async def nobody(user):
        return False
    monkeypatch.setattr(core, "bot_is_owner", nobody)
    core._recent_commands.clear()
    return core


def test_too_many_commands_are_turned_away_with_one_notice(bot_module, not_owner):
    core = not_owner
    verse = bot_module.bot.get_command("verse")
    for _ in range(core.RATE_MAX):
        assert asyncio.run(core._rate_check(ctx_for(77, verse)))
    with pytest.raises(core.RateLimited) as first:
        asyncio.run(core._rate_check(ctx_for(77, verse)))
    with pytest.raises(core.RateLimited) as second:
        asyncio.run(core._rate_check(ctx_for(77, verse)))
    assert first.value.first and not second.value.first
    ctx = ctx_for(77, verse)
    asyncio.run(core.on_command_error(ctx, first.value))
    asyncio.run(core.on_command_error(ctx, second.value))
    assert len(ctx.sent) == 1 and "few seconds" in ctx.sent[0]["content"]
    assert asyncio.run(core._rate_check(ctx_for(78, verse)))           # someone else is unaffected


def test_the_owner_is_never_limited(bot_module, monkeypatch):
    import core

    async def owner(user):
        return True
    monkeypatch.setattr(core, "bot_is_owner", owner)
    core._recent_commands.clear()
    verse = bot_module.bot.get_command("verse")
    for _ in range(core.RATE_MAX * 3):
        assert asyncio.run(core._rate_check(ctx_for(1, verse)))


def test_bookmarks_have_a_limit(bot_module, fake_ctx, monkeypatch):
    import core
    from bot_commands import personal
    monkeypatch.setattr(personal, "MAX_BOOKMARKS", 3)
    core._save_bookmarks({str(fake_ctx.author.id): [{"reference": f"John 3:{v}"} for v in range(1, 4)]})
    asyncio.run(bot_module.bot.get_command("save").callback(fake_ctx, reference="Genesis 1:1"))
    assert "as many as I keep" in fake_ctx.sent[-1]["content"]
    assert len(core._load_bookmarks()[str(fake_ctx.author.id)]) == 3


def test_one_export_at_a_time(bot_module):
    from bot_commands import books
    books._last_export.clear()
    assert books._export_wait(5) == 0
    assert 0 < books._export_wait(5) <= books.EXPORT_PAUSE
    assert books._export_wait(6) == 0


def test_user_text_cannot_steer_a_url(monkeypatch):
    import sefaria_lookup
    asked = []

    class Stop(Exception):
        pass

    def fake_urlopen(req, timeout=None):
        asked.append(req.full_url if hasattr(req, "full_url") else req)
        raise Stop
    monkeypatch.setattr(sefaria_lookup.urllib.request, "urlopen", fake_urlopen)
    try:
        sefaria_lookup.fetch_mishnah("../../admin", 1, 1)
    except Stop:
        pass
    assert asked and all("../" not in url and "%2F" in url for url in asked)
    assert all(url.startswith("https://www.sefaria.org/") for url in asked)
