"""The shared commands follow a server's choices too: a Protestant server isn't offered the Hail Mary by
!prayer, Latin chant by !hymnday, the Orthodox calendar by !today, the Apocrypha at random, or the
Buddhist scriptures in !books, !cloud and !parallel."""
import asyncio
import datetime
import types

import pytest

GUILD = 5151


@pytest.fixture
def protestant(bot_module):
    from bot_commands import packs
    packs.save_choices(GUILD, packs.packs_for({"bible", "christian"}, packs.CHURCHES["protestant"][1], False),
                       {"bible", "christian"})
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


def test_random_bible_without_the_apocrypha(bot_module, protestant, lookup):
    from scripture_lookup import BIBLE_APOCRYPHA
    import core
    allowed = core.guild_traditions(protestant)
    for _ in range(80):
        r = lookup.random_verse(traditions=allowed)
        assert r["book"] not in BIBLE_APOCRYPHA


def test_books_shows_only_the_servers_sections(bot_module, protestant):
    from bot_commands import books
    root, sections = books.tree_for(protestant)
    names = {n for n, _ in sections}
    assert "📖 The Bible" in names and "⛪ Patristics & Church History" in names
    assert "☸️ Buddhist" not in names and "✡️ Rabbinic & Kabbalistic" not in names
    assert all(subs for _, subs in root)
    assert books.tree_for(None)[0] is books.ROOT_BOOKS_TREE
    ctx = ctx_in(protestant)
    asyncio.run(books.list_books.callback(ctx, section="Dhammapada"))
    assert "not found" in ctx.sent[-1]["content"]


def test_cloud_and_parallel(bot_module, protestant):
    ctx = ctx_in(protestant)
    asyncio.run(bot_module.bot.get_command("cloud").callback(ctx, book="Dhammapada"))
    assert "don't know a book" in ctx.sent[-1]["content"]
    ctx = ctx_in(protestant)
    asyncio.run(bot_module.bot.get_command("parallel").callback(ctx, reference="works"))
    assert "John 3:16" in ctx.sent[-1]["embed"].description and "Iliad" not in ctx.sent[-1]["embed"].description
    ctx = ctx_in(protestant)
    asyncio.run(bot_module.bot.get_command("parallel").callback(ctx, reference="Il. 6.440"))
    assert "Couldn't parse" in ctx.sent[-1]["content"]
