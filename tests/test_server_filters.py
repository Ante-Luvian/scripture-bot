"""The shared commands follow a server's choices too: a Protestant server isn't offered the Hail Mary by
!prayer, Latin chant by !hymnday or the Orthodox calendar by !today. (Texts are never hidden: every server has
the whole library.)"""
import asyncio
import datetime
import types

import pytest

GUILD = 5151


@pytest.fixture
def protestant(bot_module):
    from bot_commands import packs
    packs.save_choices(GUILD, packs.packs_for({"bible", "christian"}, packs.CHURCHES["protestant"][1], False))
    return GUILD


def ctx_in(guild_id):
    ctx = types.SimpleNamespace(guild=types.SimpleNamespace(id=guild_id), sent=[],
                                author=types.SimpleNamespace(id=1))

    async def send(content=None, **kwargs):
        ctx.sent.append({"content": content, **kwargs})
    ctx.send = send

    class _Typing:
        async def __aenter__(self): return self
        async def __aexit__(self, *exc): return False
    ctx.typing = lambda: _Typing()
    return ctx


def test_prayers(bot_module, protestant):
    from bot_commands import prayers
    assert not prayers.available("hail mary", protestant) and not prayers.available("jesus prayer", protestant)
    assert prayers.available("our father", protestant) and prayers.available("hail mary", None)
    listed = prayers.list_embed(protestant)
    assert "Our Father" in listed.description and "Memorare" not in listed.description
    assert not any("Orthodox" in f.name for f in listed.fields)
    ctx = ctx_in(protestant)
    asyncio.run(prayers.send_prayer(ctx, "hail mary"))
    assert "don't know a prayer" in ctx.sent[-1]["content"]


def test_hymnday_without_latin_chant(bot_module, protestant):
    from bot_commands import hymnday
    from bot_commands.hymns import shelf
    start = datetime.date(2026, 1, 1)
    for n in range(0, 365, 3):                       # a year: feasts, seasons and ordinary days
        hymn, _ = hymnday.hymn_for(start + datetime.timedelta(days=n), latin=False)
        assert shelf(hymn) != "chant", hymn["title"]
    message = hymnday.hymnday_message(datetime.date(2026, 5, 24), protestant)       # Pentecost: Veni Creator?
    assert "Pentecost" in message["content"]


def test_today_keeps_the_servers_calendars(bot_module, protestant):
    import core
    assert core.guild_calendars(protestant, ["catholic", "anglican", "orthodox", "jewish", "islamic"]) == ["anglican"]
    assert core.guild_calendars(None, ["catholic", "orthodox"]) == ["catholic", "orthodox"]
    assert core.guild_calendars(protestant, ["orthodox"]) == ["orthodox"]          # asked for by name: still given


def test_every_text_on_every_server(bot_module, protestant):
    """The per-server traditions filter was removed (the owner, 2026-11-11): a Protestant server still has the
    Buddhist scriptures in !books and !cloud, and the classics in !parallel."""
    from bot_commands import books
    ctx = ctx_in(protestant)
    asyncio.run(books.list_books.callback(ctx, section="Dhammapada"))
    assert "not found" not in str(ctx.sent[-1].get("content"))
    ctx = ctx_in(protestant)
    asyncio.run(bot_module.bot.get_command("cloud").callback(ctx, book="Dhammapada"))
    assert "don't know a book" not in str(ctx.sent[-1].get("content"))
    ctx = ctx_in(protestant)
    asyncio.run(bot_module.bot.get_command("parallel").callback(ctx, reference="works"))
    assert "Iliad" in ctx.sent[-1]["embed"].description
