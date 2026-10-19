"""The !help menu is data (help.HELP_MENU) laid out to Discord's limits, and every command is in it."""
import asyncio
import re

import pytest


@pytest.fixture(scope="module")
def h(bot_module):
    from bot_commands import help
    return help


def test_every_command_is_in_the_menu(h, bot_module):
    text = " ".join(f.value for e in h.menu_embeds() for f in e.fields)
    named = {bot_module.bot.get_command(n).name for n in re.findall(r"!([a-z]+)", text) if bot_module.bot.get_command(n)}
    missing = sorted(c.name for c in bot_module.bot.commands
                     if not c.hidden and c.name not in h.NOT_IN_MENU and c.name not in named)
    assert not missing, missing


def test_within_discords_limits_however_long(h, monkeypatch):
    long_menu = h.HELP_MENU + [(f"Extra {n}", [f"`!verse` — line {i} " + "x" * 80 for i in range(30)]) for n in range(6)]
    monkeypatch.setattr(h, "HELP_MENU", long_menu)
    embeds = h.menu_embeds()
    assert len(embeds) >= 3
    for e in embeds:
        assert len(e) <= 6000 and len(e.fields) <= 25 and all(len(f.value) <= 1024 for f in e.fields)
    assert embeds[-1].footer.text and not embeds[0].footer.text


def test_more_lines_are_whole_sentences(h):
    for line in h._more_lines():
        assert line.startswith("`!") and not line.rstrip().endswith((",", " from", " the"))


def test_the_menu_is_sent_in_as_many_messages_as_it_needs(h, fake_ctx):
    asyncio.run(h.cmd_help.callback(fake_ctx))
    assert len(fake_ctx.sent) == len(h.menu_embeds()) >= 1
