"""Two errors that DMed the owner (data/error_log.json, Oct 2026), and the user could do nothing about."""
import asyncio

import discord
import pytest


def test_the_setup_summary_fits_discord(bot_module):
    """The last step of !serversetup ("No thanks") failed: the packs' lines outgrew one 1,024-character field."""
    from bot_commands import packs
    embed = packs.summary_embed(123)
    assert all(len(f.value) <= 1024 for f in embed.fields)
    text = "\n".join(f.value for f in embed.fields)
    assert all(label in text for label, _, _ in packs.PACKS.values())
    assert len(embed) <= 6000


class _Value:
    id, mention = 42, "<#42>"

    def __init__(self, resolved):
        self._resolved = resolved

    def resolve(self):
        return self._resolved


class _Client:
    def __init__(self, fetched):
        self.fetched = fetched

    async def fetch_channel(self, channel_id):
        if self.fetched is None:
            raise discord.Forbidden(type("R", (), {"status": 403, "reason": "Forbidden"})(), "Missing Access")
        return self.fetched


class _Interaction:
    def __init__(self, fetched):
        self.client = _Client(fetched)


def test_a_channel_i_cant_see_gets_an_answer_not_an_error(bot_module):
    """/setup votd channel:#daily-verse-daily-saint failed with "Failed to convert ... to TextChannel"."""
    from bot_commands.slash import PostChannel
    from core import UserFacingError
    with pytest.raises(UserFacingError, match="I can't see <#42>.*View Channel"):
        asyncio.run(PostChannel().transform(_Interaction(None), _Value(None)))


def test_a_channel_i_wasnt_told_about_is_fetched(bot_module):
    from bot_commands.slash import PostChannel
    channel = discord.TextChannel.__new__(discord.TextChannel)
    assert asyncio.run(PostChannel().transform(_Interaction(channel), _Value(None))) is channel
    assert asyncio.run(PostChannel().transform(_Interaction(None), _Value(channel))) is channel
