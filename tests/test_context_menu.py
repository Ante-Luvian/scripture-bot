"""Right-click → Apps → "Look up verses"."""
import asyncio

import pytest


@pytest.fixture(scope="module")
def auto(bot_module):
    from bot_commands import autodetect
    return autodetect


class Interaction:
    def __init__(self):
        self.messages, self.followups, self.deferred = [], [], False
        outer = self

        class Response:
            async def send_message(self, text, ephemeral=False):
                outer.messages.append((text, ephemeral))

            async def defer(self, ephemeral=False, thinking=False):
                outer.deferred = ephemeral

        class Followup:
            async def send(self, embed=None, ephemeral=False, view=None):
                outer.followups.append((embed, ephemeral, view))
        self.response, self.followup = Response(), Followup()


def _run(auto, content):
    interaction = Interaction()
    message = type("M", (), {"content": content})()
    asyncio.run(auto.look_up_verses.callback(interaction, message))
    return interaction


def test_registered_as_a_message_command(auto, bot_module):
    import discord
    cmd = bot_module.bot.tree.get_command("Look up verses", type=discord.AppCommandType.message)
    assert cmd is not None


def test_replies_privately_with_each_verse(auto):
    i = _run(auto, "!something about John 3:16 and Romans 8:28")     # auto-detect ignores "!" messages
    assert i.deferred and [e.title.split(" (")[0] for e, _, _ in i.followups] == ["John 3:16", "Romans 8:28"]
    assert all(ephemeral for _, ephemeral, _ in i.followups)
    assert i.followups[0][2] is not None                                  # study buttons


def test_up_to_five(auto):
    refs = ", ".join(f"Psalm 23:{v}" for v in range(1, 7))
    assert len(_run(auto, refs).followups) == auto.CONTEXT_MENU_LIMIT


def test_nothing_found(auto):
    i = _run(auto, "hello there")
    assert not i.followups and i.messages[0][1] and "couldn't find" in i.messages[0][0]
