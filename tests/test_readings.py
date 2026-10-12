"""The 📅 Today's readings button under the Verse of the Day."""
import asyncio
import datetime

import pytest


@pytest.fixture(scope="module")
def liturgy(bot_module):
    from bot_commands import liturgy
    return liturgy


def test_readings_for_a_day(liturgy):
    embed = liturgy.readings_embed(datetime.date(2026, 10, 12))
    assert embed.title == "📅 Readings for Monday, 12 October 2026"
    fields = {f.name: f.value for f in embed.fields}
    for office in ("🌅 Morning Prayer", "🌙 Evening Prayer"):
        lines = fields[office].splitlines()
        assert lines[0].startswith("Psalm")
        assert any(l.startswith("First Lesson: ") for l in lines) and any(l.startswith("Second Lesson: ") for l in lines)
    assert fields.get("📿 Collect")


def test_christmas(liturgy):
    embed = liturgy.readings_embed(datetime.date(2026, 12, 25))
    assert "Christmas" in (embed.description or "") + embed.fields[-1].value


class Response:
    def __init__(self):
        self.sent = []

    async def send_message(self, content=None, embed=None, ephemeral=False):
        self.sent.append((content, embed, ephemeral))


def test_button_replies_privately_with_its_own_date(liturgy):
    view = liturgy.readings_view(datetime.date(2026, 12, 25))
    button = view.children[0]
    assert view.timeout is None and button.custom_id == "readings:2026-12-25"
    dynamic = liturgy.ReadingsButton("2026-12-25")
    interaction = type("I", (), {"response": Response()})()
    asyncio.run(dynamic.callback(interaction))
    _, embed, ephemeral = interaction.response.sent[0]
    assert ephemeral and "25 December 2026" in embed.title


def test_verse_of_the_day_carries_the_button(bot_module, monkeypatch):
    from bot_commands import votd
    monkeypatch.setattr(votd, "_scrape_votd", lambda: ("John 3:16", "October 12, 2026"))
    sent = []

    class Channel:
        async def send(self, content=None, **kw):
            sent.append(kw)
    asyncio.run(votd._send_votd(Channel()))
    assert sent[0]["view"].children[0].custom_id.startswith("readings:")
