"""Packs: a server keeps only the commands and traditions it chose (core.PACKS, bot_commands/packs.py)."""
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
    """A Protestant server that answered: Christianity, Protestant, no divination."""
    packs.save_choices(GUILD, packs.packs_for({"bible", "christian"}, packs.CHURCHES["protestant"][1], False),
                       {"bible", "christian"})


def test_every_pack_command_is_real_and_has_a_slash_version(bot_module):
    import core
    slash = {c.name for c in bot_module.bot.tree.get_commands()}
    for name in core.PACK_OF:
        assert bot_module.bot.get_command(name) is not None, name
        assert bot_module.bot.get_command(name).name == name, f"{name} is an alias; use the command's name"
        assert name in slash, f"/{name} (needed to hide it per server)"


def test_pack_names_never_clash_with_traditions():
    import core
    from scripture_lookup import TRADITIONS
    assert not set(core.PACKS) & set(TRADITIONS)        # so !packs jewish can only mean the texts


def test_a_server_that_never_chose_has_everything(bot_module):
    import core
    assert core.guild_packs(GUILD) == frozenset(core.PACKS)
    assert core.guild_corpora(GUILD) is None
    assert all(core.command_enabled(GUILD, name) for name in core.PACK_OF)


@pytest.mark.parametrize("church, answer, on, off", [
    ("protestant", None, {"church", "protestant"}, {"saints", "catholic_devotion", "orthodox", "divination"}),
    ("anglican", "low", {"protestant"}, {"saints", "catholic_devotion"}),
    ("anglican", "broad", {"protestant", "saints"}, {"catholic_devotion"}),
    ("anglican", "high", {"protestant", "saints", "catholic_devotion"}, {"catholic_teaching", "orthodox"}),
    ("catholic", None, {"saints", "catholic_devotion", "catholic_teaching"}, {"protestant", "orthodox"}),
    ("orthodox", None, {"saints", "orthodox"}, {"protestant", "catholic_teaching"}),
])
def test_the_answers_choose_the_packs(packs, church, answer, on, off):
    church_packs = packs.ANGLICAN[answer][1] if answer else packs.CHURCHES[church][1]
    chosen = packs.packs_for({"bible", "christian"}, church_packs, False)
    assert on <= chosen and not off & chosen
    assert "comparative" not in chosen and "jewish_learning" not in chosen


def test_other_traditions_bring_their_own_packs(packs):
    assert packs.packs_for({"bible", "jewish"}, set(), False) == {"jewish_learning", "comparative"}
    assert packs.packs_for({"bible", "islamic", "sufi"}, set(), True) == {"islamic_prayer", "comparative", "divination"}
    assert packs.packs_for({"bible"}, set(), False) == set()


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


def test_a_turned_off_tradition_is_a_book_i_dont_have(bot_module, packs, lookup):
    from bot_commands import verse
    protestant(packs)
    gita = lookup.get_verse("Gita 2:47")
    assert gita["found"] and gita["tradition"] == "hindu"
    hidden = verse.hidden_in_guild(ctx_in(GUILD), gita)
    assert not hidden["found"] and hidden["error"].startswith("Unknown book")
    john = lookup.get_verse("John 3:16")
    assert john["tradition"] == "bible" and verse.hidden_in_guild(ctx_in(GUILD), john) is john
    augustine = lookup.random_verse_from_book("Confessions")
    assert verse.hidden_in_guild(ctx_in(GUILD), dict(augustine, tradition=lookup.tradition_of(augustine)))["found"]


def test_online_libraries_are_tagged_too(lookup):
    quran = lookup.get_verse("Quran 1:1")                 # our own Pickthall, offline
    assert quran["found"] and quran["tradition"] == "islamic"


def test_random_and_search_stay_in_the_servers_traditions(bot_module, packs, lookup):
    import core
    protestant(packs)
    allowed = core.guild_traditions(GUILD)
    assert allowed == {"bible", "christian"}
    for _ in range(40):
        assert lookup.tradition_of(lookup.random_verse(traditions=allowed)) in allowed
    corpora = core.guild_corpora(GUILD)
    assert "kjv" in corpora and "reformation" in corpora and "dharmic" not in corpora
    ctx = ctx_in(GUILD)
    asyncio.run(bot_module.bot.get_command("search").callback(ctx, query="nirvana in:buddhist"))
    assert "don't know the tradition" in ctx.sent[-1]["content"]


def test_help_and_the_introduction_leave_out_what_a_server_turned_off(bot_module, packs):
    from bot_commands import changelog
    protestant(packs)
    ctx = ctx_in(GUILD)
    asyncio.run(bot_module.bot.get_command("help").callback(ctx))
    menu = str([(f.name, f.value) for f in ctx.sent[-1]["embed"].fields]) + ctx.sent[-1]["embed"].footer.text
    assert "!vov" in menu and "!verse" in menu and "!hymn" in menu
    for gone in ("!rosary", "!ccc", "!iching", "!tarot", "!parsha", "!salah", "!help gita", "!icon", "!story"):
        assert gone not in menu, gone
    ctx = ctx_in(GUILD)
    asyncio.run(bot_module.bot.get_command("help").callback(ctx, topic="rosary"))
    assert ctx.sent == []

    intro = "\n".join(body for _, body in changelog.intro_sections(GUILD))
    assert "!vov" in intro and "Daily Office" in intro and "Church Fathers" in intro
    for gone in ("!rosary", "Hinduism", "Catholic teaching", "Rabbinic", "!troparion", "For centuries", "!tarot"):
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
    asyncio.run(run(ctx_in(GUILD), "hindu", "on"))
    asyncio.run(run(ctx_in(GUILD), "protestant", "off"))
    assert "divination" in core.guild_packs(GUILD) and "protestant" not in core.guild_packs(GUILD)
    assert "hindu" in core.guild_traditions(GUILD)
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


def test_the_wizard_walks_through_the_questions(bot_module, packs, monkeypatch):
    import core
    applied = []

    async def apply(guild):
        applied.append(guild)
    monkeypatch.setattr(packs, "apply", apply)

    class Response:
        async def edit_message(self, **kw): self.last = kw
        async def defer(self): pass

    def press(label):
        button = next(item for item in wizard.children if getattr(item, "label", None) == label)
        interaction = types.SimpleNamespace(response=Response(), guild=None)
        asyncio.run(button.callback(interaction))
        return interaction.response.last

    wizard = packs.SetupWizard(GUILD)
    wizard.traditions = {"christian", "jewish"}
    press("Next ▶")
    assert "Which church" in wizard.question
    press("Anglican")
    assert "How high church" in wizard.question
    press("High church / Anglo-Catholic")
    assert "divination" in wizard.question
    final = press("No thanks")
    assert final["view"] is None and "All set" in final["embed"].title
    assert core.guild_packs(GUILD) == {"church", "protestant", "saints", "catholic_devotion", "jewish_learning",
                                       "comparative"}
    assert core.guild_traditions(GUILD) == {"bible", "christian", "jewish"}
    assert applied


def test_welcome_offers_the_setup(bot_module, packs, monkeypatch):
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
    assert isinstance(sent[0]["view"], packs.WelcomeView)
    assert "Set me up" in sent[0]["embed"].description
