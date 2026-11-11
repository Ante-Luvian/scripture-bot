"""Every server has everything: the per-server traditions setting, !serversetup and !packs were removed at the
owner's request (2026-11-11). A server that once chose only the Protestant packs still gets the Hail Mary, Latin
chant, every calendar and the whole library."""
import asyncio
import datetime
import types

import pytest

GUILD = 5151


@pytest.fixture
def protestant(bot_module):
    import core
    core._update_guild_config(GUILD, packs=["church", "protestant"])        # (a choice saved before the removal)
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


def test_packs_are_gone(bot_module):
    import core
    assert bot_module.bot.get_command("packs") is None and bot_module.bot.get_command("serversetup") is None
    assert not hasattr(core, "PACKS") and not hasattr(core, "command_enabled")
    assert bot_module.bot.tree.get_command("setup").get_command("packs") is None


def test_every_prayer(bot_module, protestant):
    from bot_commands import prayers
    listed = prayers.list_embed()
    assert "Memorare" in listed.description and any("Orthodox" in f.name for f in listed.fields)
    ctx = ctx_in(protestant)
    asyncio.run(prayers.send_prayer(ctx, "hail mary"))
    assert "don't know a prayer" not in str(ctx.sent[-1].get("content"))


def test_hymnday_has_the_chant(bot_module):
    from bot_commands import hymnday
    from bot_commands.hymns import shelf
    start = datetime.date(2026, 1, 1)
    kinds = {shelf(hymnday.hymn_for(start + datetime.timedelta(days=n))[0]) for n in range(365)}
    assert "chant" in kinds


def test_every_text_on_every_server(bot_module, protestant):
    """A server that chose Protestant packs still has the Buddhist scriptures in !books and !cloud, and the
    classics in !parallel."""
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
    ctx = ctx_in(protestant)                                   # (a classical reference: read, not refused)
    asyncio.run(bot_module.bot.get_command("parallel").callback(ctx, reference="the the the"))
    assert ctx.sent                                             # (it once raised NameError here)


def test_old_server_commands_are_cleared(bot_module, monkeypatch):
    """Pack commands were registered server by server until 2026-11-11: those are cleared at startup, or the
    server's / menu would show them twice (now that they're global)."""
    from bot_commands import welcome
    calls = []

    class Tree:
        async def sync(self, guild=None):
            calls.append(("sync", guild))
            return [1, 2, 3] if guild is None else []

        async def fetch_commands(self, guild=None):
            return ["old"] if guild == "old" else []

        def clear_commands(self, guild=None):
            calls.append(("clear", guild))
    fake = types.SimpleNamespace(tree=Tree(), guilds=["old", "new"])
    monkeypatch.setattr(welcome, "bot", fake)
    assert asyncio.run(welcome.sync_all()) == 3
    assert calls == [("sync", None), ("clear", "old"), ("sync", "old")]
