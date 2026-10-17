"""The :sowwy: emoji on "I can't find that" replies, in servers that have one."""
import types

import pytest


@pytest.fixture(scope="module")
def core(bot_module):
    import core
    return core


class _Emoji:
    name = "sowwy"

    def __str__(self):
        return "<:sowwy:123>"


MINE = types.SimpleNamespace(emojis=[_Emoji()])
OTHER = types.SimpleNamespace(emojis=[])


@pytest.mark.parametrize("message", [
    "I don't know a saint called **Daria**.", "⚠️ I couldn't reach the Orthodox Church in America's site.",
    "I don't have an icon called **zz**.", "No hymn found for **zz**.", "Unknown book: **Hezz**",
    "I have no tune to play for **zz**.", "⚠️ Sorry — something went wrong with that.",
    "There's no part of the Liturgy called **zz**.", "Couldn't parse `zz`.",
])
def test_apologies_get_the_emoji(core, message):
    out = core.apologetic(MINE, message)
    assert out.startswith("<:sowwy:123> ") and "⚠️" not in out
    assert core.apologetic(OTHER, message) == message              # a server without it: unchanged
    assert core.apologetic(None, message) == message               # direct messages: unchanged


@pytest.mark.parametrize("message", [
    "🎵 **Hymn of the day**", "Which psalm? `!psalm 110 chant`", "The Angelus will be posted in <#1>.",
    "Mention a channel: `!hymndaysetup channel #hymns`", None,
])
def test_other_messages_are_left_alone(core, message):
    assert core.apologetic(MINE, message) == message


def test_commands_use_it(core):
    assert isinstance(core.bot, core.ScriptureBot)
    import inspect
    assert inspect.signature(core.bot.get_context).parameters["cls"].default is core.ScriptureContext
