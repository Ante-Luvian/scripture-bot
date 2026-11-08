"""!daily: one command for the server's ten daily posts (2026-11-08)."""
import asyncio
import types


def _ctx(fake_ctx, guild_id=1):
    fake_ctx.guild = types.SimpleNamespace(id=guild_id, name="Guild")
    return fake_ctx


def test_every_kind_hands_on_to_a_real_hidden_setup_command(bot_module):
    from bot_commands import daily
    for kind, (_, setup, _, _) in daily.KINDS.items():
        command = bot_module.bot.get_command(setup)
        assert command is not None and command.hidden, setup
        assert command.checks, f"!{setup} must still check for admins when typed"
    assert bot_module.bot.get_command("daily").checks


def test_overview_shows_what_is_set_up(bot_module, fake_ctx):
    import core
    from bot_commands import daily
    core._update_guild_config(1, saintday_channel_id=55, saintday_time="07:30", angelus_channel_id=66,
                              angelus_times=["06:00", "18:00"])
    asyncio.run(daily.cmd_daily.callback(_ctx(fake_ctx)))
    text = fake_ctx.sent[-1]["embed"].description
    assert "😇 The saint of the day — <#55> at 07:30 UTC" in text
    assert "🔔 The Angelus — <#66> at 06:00, 18:00 UTC" in text
    assert "📖 Verse of the Day — off · `!daily votd channel #channel`" in text


def test_a_kind_hands_on_with_its_words(bot_module, fake_ctx, monkeypatch):
    from bot_commands import daily
    calls = []

    async def fake_setup(ctx, action="", *, arg=""):
        calls.append((action, arg))
    monkeypatch.setattr(bot_module.bot.get_command("saintsetup"), "callback", fake_setup)
    monkeypatch.setattr(bot_module.bot.get_command("hymndaysetup"), "callback", fake_setup)
    asyncio.run(daily.cmd_daily.callback(_ctx(fake_ctx), "saint", "time", arg="07:30"))
    asyncio.run(daily.cmd_daily.callback(_ctx(fake_ctx), "Hymnday", "off"))     # another name for "hymn"
    assert calls == [("time", "07:30"), ("off", "")]


def test_an_unknown_kind_lists_them(bot_module, fake_ctx):
    from bot_commands import daily
    asyncio.run(daily.cmd_daily.callback(_ctx(fake_ctx), "`pizza`"))
    reply = fake_ctx.sent[-1]["content"]
    assert "I don't post `'pizza'` daily" in reply and "`saint`" in reply
