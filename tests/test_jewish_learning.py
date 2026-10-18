"""The Jewish learning calendar (Sefaria): !parsha, !dafyomi, !learning, !learningsetup."""
import asyncio
import datetime
import types

import pytest

ITEMS = [
    {"title": {"en": "Parashat Hashavua"}, "displayValue": {"en": "Lech-Lecha"}, "ref": "Genesis 12:1-17:27",
     "description": {"en": "Lech Lecha (“Go Forth”) recounts Abraham’s first encounter with God."},
     "extraDetails": {"aliyot": ["Genesis 12:1-12:13", "Genesis 12:14-13:4", "Genesis 13:5-13:18", "Genesis 14:1-14:20",
                                 "Genesis 14:21-15:6", "Genesis 15:7-17:6", "Genesis 17:7-17:27", "Genesis 17:24-17:27"]}},
    {"title": {"en": "Haftarah"}, "displayValue": {"en": "Isaiah 40:27-41:16"}, "ref": "Isaiah 40:27-41:16"},
    {"title": {"en": "Daf Yomi"}, "displayValue": {"en": "Bekhorot 30"}, "ref": "Bekhorot 30"},
    {"title": {"en": "Daily Mishnah"}, "displayValue": {"en": "Mishnah Oholot 10:7-11:1"}, "ref": "Mishnah Oholot 10:7-11:1"},
    {"title": {"en": "Chok LeYisrael"}, "displayValue": {"en": "Lech Lecha"}, "ref": None},
]
DAY = datetime.date(2026, 10, 18)


@pytest.fixture
def jl(bot_module, monkeypatch):
    from bot_commands import jewish_learning
    monkeypatch.setattr(jewish_learning, "calendar", lambda day: ITEMS)
    monkeypatch.setattr(jewish_learning, "_today", lambda: DAY)
    return jewish_learning


def test_dates(jl):
    assert jl.parse_day("") == DAY and jl.parse_day("12-25") == datetime.date(2026, 12, 25)
    assert jl.parse_day("2027-01-06") == datetime.date(2027, 1, 6) and jl.parse_day("soon") is None
    assert jl.parse_day("13-45") is None


def test_parsha(jl, fake_ctx):
    asyncio.run(jl.send_parsha(fake_ctx))
    e = fake_ctx.sent[-1]["embed"]
    assert e.title == "📜 Parashat Lech-Lecha" and "Abraham" in e.description
    aliyot = e.fields[1].value.splitlines()
    assert len(aliyot) == 8 and aliyot[0] == "1. Genesis 12:1-12:13 — `!verse Genesis 12:1-12:13`" and aliyot[-1].startswith("Maftir.")
    assert "Isaiah 40:27-41:16" in e.fields[2].value


def test_learning(jl, fake_ctx):
    asyncio.run(jl.send_learning(fake_ctx))
    e = fake_ctx.sent[-1]["embed"]
    names = [f.name for f in e.fields]
    assert names == ["Parashat Hashavua: this week's Torah portion", "Haftarah: read from the Prophets with it",
                     "Daf Yomi: a page of the Talmud a day", "Daily Mishnah"]     # (Chok LeYisrael: nothing to open)
    assert "`!verse Bekhorot 30a`" in e.fields[2].value and all(len(f.value) <= 1024 for f in e.fields)


def test_daf_yomi_shows_the_page(jl, fake_ctx, monkeypatch):
    shown = []

    async def send(ctx, result):
        shown.append(result)
    monkeypatch.setattr(jl, "_send_result", send)
    monkeypatch.setattr(jl.lookup, "get_verse", lambda ref: {"found": True, "reference": ref, "text": "…", "source": "x"})
    asyncio.run(jl.send_daf(fake_ctx))
    assert "Bekhorot 30" in fake_ctx.sent[-1]["content"] and "`!verse Bekhorot 30b`" in fake_ctx.sent[-1]["content"]
    assert shown[0]["reference"] == "Bekhorot 30a"


def test_daily_post_once_a_day(jl, monkeypatch):
    sent = []

    class Channel:
        async def send(self, **kw):
            sent.append(kw)
    monkeypatch.setattr(jl, "_load_guild_config", lambda: {"5": {"learning_channel_id": 9, "learning_time": "06:00"}})
    client = types.SimpleNamespace(get_channel=lambda cid: Channel())
    assert asyncio.run(jl.run_daily_learning(client, DAY, "06:00")) == 1
    assert asyncio.run(jl.run_daily_learning(client, DAY, "06:00")) == 0     # a restart doesn't post it twice
    assert asyncio.run(jl.run_daily_learning(client, DAY, "07:00")) == 0
    assert len(sent) == 1 and "Jewish learning" in sent[0]["embed"].title


@pytest.mark.live
def test_sefaria_calendar_live(bot_module):
    from bot_commands import jewish_learning as jl
    items = jl.calendar(datetime.date(2026, 10, 18))
    assert jl.parsha_embed(items).title == "📜 Parashat Lech-Lecha"
