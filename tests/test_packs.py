"""Packs: a server keeps only the commands it chose (core.PACKS, bot_commands/packs.py). Every server has every
tradition's texts: the per-server traditions filter was removed on 2026-11-11."""
import asyncio
import types

import pytest

GUILD = 4242


@pytest.fixture
def packs(bot_module):
    from bot_commands import packs
    return packs


def ctx_in(guild_id, command=None):
    ctx = types.SimpleNamespace(guild=types.SimpleNamespace(id=guild_id), sent=[])
    ctx.command = command

    async def send(content=None, **kwargs):
        ctx.sent.append({"content": content, **kwargs})
    ctx.send = send
    ctx.author = types.SimpleNamespace(id=1)

    class _Typing:
        async def __aenter__(self): return self
        async def __aexit__(self, *exc): return False
    ctx.typing = lambda: _Typing()
    return ctx


def protestant(packs):
    """A Protestant server: the church commands and the Prayer Book's, nothing else."""
    packs.save_choices(GUILD, {"church", "protestant"})


def test_every_pack_command_is_real_and_has_a_slash_version(bot_module):
    """(Except the ones kept prefix-only on purpose -- !delphi, !parsha, !dafyomi, !hymnlist since
    2026-11-08 -- which have no slash form to hide; the pack check still turns their ! form off.)"""
    import core
    from test_slash_parity import PREFIX_ONLY
    slash = {c.name for c in bot_module.bot.tree.get_commands()}
    for name in core.PACK_OF:
        assert bot_module.bot.get_command(name) is not None, name
        assert bot_module.bot.get_command(name).name == name, f"{name} is an alias; use the command's name"
        assert name in slash or name in PREFIX_ONLY, f"/{name} (needed to hide it per server)"


def test_pack_names_never_clash_with_traditions():
    import core
    from scripture_lookup import TRADITIONS
    assert not set(core.PACKS) & set(TRADITIONS)        # (!packs jewish is no pack: it gets the usage)


def test_a_server_that_never_chose_has_everything(bot_module):
    import core
    assert core.guild_packs(GUILD) == frozenset(core.PACKS)
    assert all(core.command_enabled(GUILD, name) for name in core.PACK_OF)


def test_a_turned_off_command_is_ignored_without_a_reply(bot_module, packs):
    import core
    protestant(packs)
    rosary, vov = bot_module.bot.get_command("rosary"), bot_module.bot.get_command("vov")
    with pytest.raises(core.PackDisabled):
        asyncio.run(core._pack_check(ctx_in(GUILD, rosary)))
    assert asyncio.run(core._pack_check(ctx_in(GUILD, vov)))
    assert asyncio.run(core._pack_check(ctx_in(GUILD, bot_module.bot.get_command("verse"))))
    ctx = ctx_in(GUILD, rosary)
    asyncio.run(core.on_command_error(ctx, core.PackDisabled()))
    assert ctx.sent == []                                            # silence
    assert asyncio.run(core._pack_check(types.SimpleNamespace(guild=None, command=rosary)))   # DMs: everything


def test_every_server_has_every_text(bot_module, packs):
    """Whatever a server chose, every tradition's texts are there (the owner, 2026-11-11)."""
    import core
    protestant(packs)
    assert not hasattr(core, "guild_traditions") and not hasattr(core, "tradition_enabled")
    ctx = ctx_in(GUILD)
    asyncio.run(bot_module.bot.get_command("search").callback(ctx, query="nirvana in:buddhist"))
    assert "don't know the tradition" not in str(ctx.sent[-1].get("content"))
    from bot_commands import books
    assert "🕉️ Hindu" in [name for name, _ in books.BOOKS_TREE]


def test_online_libraries_are_tagged_too(lookup):
    quran = lookup.get_verse("Quran 1:1")                 # our own Pickthall, offline
    assert quran["found"] and quran["tradition"] == "islamic"


def test_help_and_the_introduction_leave_out_what_a_server_turned_off(bot_module, packs):
    from bot_commands import changelog
    protestant(packs)
    ctx = ctx_in(GUILD)
    asyncio.run(bot_module.bot.get_command("help").callback(ctx))
    menu = "".join(str([(f.name, f.value) for f in m["embed"].fields]) + (m["embed"].footer.text or "")
                   for m in ctx.sent if m.get("embed"))                   # (every page: !help can run to two)
    assert "!vov" in menu and "!verse" in menu and "!hymn" in menu
    assert "!help gita" in menu                                     # (a tradition's texts: never turned off)
    for gone in ("!rosary", "!ccc", "!iching", "!tarot", "!parsha", "!salah", "!icon", "!story"):
        assert gone not in menu, gone
    ctx = ctx_in(GUILD)
    asyncio.run(bot_module.bot.get_command("help").callback(ctx, topic="rosary"))
    assert ctx.sent == []

    intro = "\n".join(body for _, body in changelog.intro_sections(GUILD))
    assert "!vov" in intro and "Daily Office" in intro and "Church Fathers" in intro
    assert "Hinduism" in intro and "Rabbinic" in intro                # (the library's texts: every server)
    for gone in ("!rosary", "Catholic teaching", "!troparion", "For centuries", "!tarot"):
        assert gone not in intro, gone
    assert not any("Oracles" in title or "Orthodox" in title or "Jewish" in title
                   for title, _ in changelog.intro_sections(GUILD))


def test_the_markers_never_show(bot_module):
    from bot_commands import changelog
    for guild_id in (None, GUILD):
        for title, body in changelog.intro_sections(guild_id):
            assert "<!--" not in body and "-->" not in body, title


def test_packs_command_switches_one_thing(bot_module, packs, monkeypatch):
    import core

    async def apply(guild):
        pass
    monkeypatch.setattr(packs, "apply", apply)
    protestant(packs)
    run = bot_module.bot.get_command("packs").callback
    asyncio.run(run(ctx_in(GUILD), "divination", "on"))
    asyncio.run(run(ctx_in(GUILD), "protestant", "off"))
    assert "divination" in core.guild_packs(GUILD) and "protestant" not in core.guild_packs(GUILD)
    ctx = ctx_in(GUILD)
    asyncio.run(run(ctx, "hindu", "on"))                  # (a tradition: its texts are always here)
    assert "Usage" in ctx.sent[-1]["content"]
    ctx = ctx_in(GUILD)
    asyncio.run(run(ctx, "nonsense", "on"))
    assert "Usage" in ctx.sent[-1]["content"]
    ctx = ctx_in(GUILD)
    asyncio.run(run(ctx))
    assert ctx.sent[-1]["embed"].fields


def test_each_server_gets_only_its_slash_commands(bot_module, packs, monkeypatch):
    protestant(packs)
    added = []

    class Tree:
        def clear_commands(self, guild): added.clear()
        def add_command(self, command, guild): added.append(command.name)
        async def sync(self, guild): return list(added)

    fake = {name: types.SimpleNamespace(name=name) for name in ("vov", "rosary", "tarot", "hymn")}
    monkeypatch.setattr(packs, "OPTIONAL", fake)
    assert asyncio.run(packs.sync_guild(types.SimpleNamespace(id=GUILD), Tree())) == 2
    assert sorted(added) == ["hymn", "vov"]


def test_welcome_has_no_setup_questions(bot_module, packs, monkeypatch):
    sent = []

    async def no_sync(guild, tree=None):
        return 0
    monkeypatch.setattr(packs, "sync_guild", no_sync)

    class Channel:
        def permissions_for(self, member):
            return types.SimpleNamespace(send_messages=True)

        async def send(self, **kw):
            sent.append(kw)

    guild = types.SimpleNamespace(system_channel=Channel(), me=object(), text_channels=[], id=GUILD)
    asyncio.run(packs.welcome(guild))
    assert "view" not in sent[0] and "Set me up" not in sent[0]["embed"].description     # (removed 2026-11-11)
    assert "!packs" in sent[0]["embed"].description
    assert bot_module.bot.get_command("serversetup") is None
