"""Every user-facing prefix command has a slash version, and the admin ones
are locked down on Discord's side (calling a prefix command directly from a
slash wrapper skips its own @has_permissions check)."""
import asyncio

import pytest

# Owner/maintenance tools that stay prefix-only
PREFIX_ONLY = {"guildactivity", "scanstats", "votdmode"}
# Admin commands; their slash forms are subcommands of /setup (Discord allows 100 slash commands)
ADMIN_SLASH = {"votdsetup", "oraclesetup", "quizsetup", "verslesetup", "hymndaysetup", "saintsetup", "astrosetup", "angelussetup", "troparionsetup", "learningsetup", "changelogsetup", "changelogintro", "features", "serversetup", "packs"}


def test_every_command_has_a_slash_version(bot_module):
    slash = {c.name for c in bot_module.bot.tree.get_commands()}
    missing = sorted(c.name for c in bot_module.bot.commands
                     if not c.hidden and c.name not in PREFIX_ONLY | ADMIN_SLASH and c.name not in slash)
    assert not missing, f"prefix commands without a slash version: {missing}"


def test_within_discords_slash_limit(bot_module):
    from discord import AppCommandType
    assert len(bot_module.bot.tree.get_commands(type=AppCommandType.chat_input)) <= 100


def test_setup_group_is_locked_down(bot_module):
    group = bot_module.bot.tree.get_command("setup")
    assert group.default_permissions is not None and group.default_permissions.administrator   # hidden from non-admins
    assert group.guild_only


@pytest.mark.parametrize("name", sorted(ADMIN_SLASH))
def test_admin_slash_commands_are_locked_down(bot_module, name):
    from bot_commands import slash
    sub = bot_module.bot.tree.get_command("setup").get_command(slash.SETUP_SUBCOMMANDS[name])
    assert sub is not None, f"/setup has no subcommand for !{name}"
    assert sub.checks, "must also enforce the permission, not just hide the command"


def test_admin_prefix_commands_still_check_permissions(bot_module):
    for name in ADMIN_SLASH:
        assert bot_module.bot.get_command(name).checks, name


def test_setup_subcommand_calls_the_prefix_command(bot_module, monkeypatch, fake_ctx):
    from bot_commands import slash
    calls = []

    async def fake_ctx_for(interaction):
        return fake_ctx

    class FakeCommand:
        def __init__(self, name):
            self.name = name

        async def __call__(self, ctx, *args, **kwargs):
            calls.append((self.name, args, kwargs))

    monkeypatch.setattr(slash, "_slash_ctx", fake_ctx_for)
    monkeypatch.setattr(slash, "_command", FakeCommand)
    fake_ctx.message = object()
    group = bot_module.bot.tree.get_command("setup")
    asyncio.run(group.get_command("votd").callback(None, action="time", channel=None, value="07:00"))
    asyncio.run(group.get_command("saint").callback(None))
    assert calls == [("votdsetup", ("time",), {"arg": "07:00"}), ("saintsetup", ("",), {"arg": ""})]


def test_slash_setup_commands_receive_the_picked_channel(bot_module):
    from bot_commands import slash
    original = type("Message", (), {"id": 7, "content": "/votdsetup"})()
    channel = object()
    shim = slash._WithChannelMention(original, channel)
    assert shim.channel_mentions == [channel] and shim.id == 7     # everything else passes through
    assert slash._WithChannelMention(original, None).channel_mentions == []


def test_slash_wrapper_calls_the_prefix_command(bot_module, monkeypatch, fake_ctx):
    from bot_commands import slash
    calls = []

    async def fake_ctx_for(interaction):
        return fake_ctx

    class FakeCommand:
        async def __call__(self, ctx, *args, **kwargs):
            calls.append((ctx, args, kwargs))

    monkeypatch.setattr(slash, "_slash_ctx", fake_ctx_for)
    monkeypatch.setattr(slash, "_command", lambda name: FakeCommand())
    asyncio.run(slash.virgil_slash.callback(None, question="will it rain?"))
    asyncio.run(slash.psalm_slash.callback(None, period="ep"))
    assert calls == [(fake_ctx, (), {"question": "will it rain?"}), (fake_ctx, (), {"args": "ep"})]
