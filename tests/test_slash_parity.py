"""Every user-facing prefix command has a slash version, and the admin ones
are locked down on Discord's side (calling a prefix command directly from a
slash wrapper skips its own @has_permissions check)."""
import asyncio

import pytest

# Owner/maintenance tools that stay prefix-only
PREFIX_ONLY = {"guildactivity", "scanstats", "votdmode"}
ADMIN_SLASH = {"votdsetup", "oraclesetup", "quizsetup", "verslesetup", "hymndaysetup", "saintsetup", "angelussetup", "troparionsetup", "learningsetup", "changelogsetup", "changelogintro", "features"}


def test_every_command_has_a_slash_version(bot_module):
    slash = {c.name for c in bot_module.bot.tree.get_commands()}
    missing = sorted(c.name for c in bot_module.bot.commands
                     if not c.hidden and c.name not in PREFIX_ONLY and c.name not in slash)
    assert not missing, f"prefix commands without a slash version: {missing}"


@pytest.mark.parametrize("name", sorted(ADMIN_SLASH))
def test_admin_slash_commands_are_locked_down(bot_module, name):
    cmd = bot_module.bot.tree.get_command(name)
    assert cmd.default_permissions is not None and cmd.default_permissions.administrator   # hidden from non-admins
    assert cmd.checks, "must also enforce the permission, not just hide the command"
    assert cmd.guild_only


def test_admin_prefix_commands_still_check_permissions(bot_module):
    for name in ADMIN_SLASH:
        assert bot_module.bot.get_command(name).checks, name


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
