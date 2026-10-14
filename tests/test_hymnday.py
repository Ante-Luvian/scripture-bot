"""!hymnday: a hymn for each day of the Church year, and its daily post."""
import asyncio
import datetime

import pytest

from liturgical_calendar import western_season

D = datetime.date


@pytest.fixture(scope="module")
def hd(bot_module):
    from bot_commands import hymnday
    return hymnday


@pytest.mark.parametrize("day, season, feast", [
    (D(2026, 11, 29), "advent", None),             # Advent Sunday, the nearest Sunday to 30 November
    (D(2026, 11, 28), "ordinary", None),
    (D(2026, 11, 22), "ordinary", "christ_the_king"),
    (D(2026, 12, 25), "christmas", "christmas"),
    (D(2027, 1, 3), "christmas", None),
    (D(2027, 1, 6), "epiphany", "epiphany"),
    (D(2027, 2, 10), "lent", "ash_wednesday"),       # Easter 2027 is 28 March
    (D(2027, 3, 14), "passiontide", None),           # the fifth Sunday of Lent
    (D(2027, 3, 26), "passiontide", "good_friday"),
    (D(2027, 3, 28), "easter", "easter"),
    (D(2027, 5, 16), "pentecost", "pentecost"),
    (D(2027, 5, 23), "ordinary", "trinity"),
])
def test_the_church_year(day, season, feast):
    assert western_season(day) == (season, feast)


def test_every_named_hymn_exists(hd):
    titles = hd._by_title()
    named = [t for lst in list(hd.FEAST_HYMNS.values()) + list(hd.SEASON_HYMNS.values()) for t in lst]
    assert not [t for t in named if t not in titles]


def test_feasts_and_seasons(hd):
    hymn, why = hd.hymn_for(D(2027, 5, 16))
    assert why == "For Pentecost" and hymn["title"] in hd.FEAST_HYMNS["pentecost"]
    hymn, why = hd.hymn_for(D(2026, 12, 3))
    assert why == "In Advent" and hymn["title"] in hd.SEASON_HYMNS["advent"]
    days = [D(2027, 3, 14) + datetime.timedelta(days=n) for n in range(5)]  # Passiontide: a different one each day
    assert len({hd.hymn_for(d)[0]["title"] for d in days}) == 5


def test_ordinary_time_takes_each_shelf_in_turn(hd):
    from bot_commands.hymns import shelf
    days = [D(2026, 10, 13) + datetime.timedelta(days=n) for n in range(3)]
    picks = [hd.hymn_for(d) for d in days]
    assert {shelf(h) for h, _ in picks} == {"hymns", "chant", "harp"} and all(why == "" for _, why in picks)
    assert hd.hymn_for(days[0])[0] is hd.hymn_for(days[0])[0]                 # the same all day


def test_the_message(hd):
    msg = hd.hymnday_message(D(2026, 12, 25))
    assert msg["content"].startswith("🎵 **Hymn of the day** · Friday 25 December · For Christmas Day")
    assert msg["embed"].title and msg["view"] is not None


class _Channel:
    def __init__(self, cid):
        self.id, self.sent, self.mention = cid, [], f"<#{cid}>"

    async def send(self, content=None, **kwargs):
        self.sent.append({"content": content, **kwargs})


def test_daily_post(hd):
    import core
    core._update_guild_config(1, hymnday_channel_id=100, hymnday_time="07:00")
    core._update_guild_config(2, hymnday_channel_id=200)                     # the default time
    a, b = _Channel(100), _Channel(200)
    client = type("C", (), {"get_channel": lambda self, cid: {100: a, 200: b}.get(cid)})()
    day = D(2026, 10, 13)
    assert asyncio.run(hd.run_daily_hymns(client, day, "07:00")) == 1
    assert "Hymn of the day" in a.sent[0]["content"] and a.sent[0]["embed"]
    assert asyncio.run(hd.run_daily_hymns(client, day, "07:00")) == 0       # not twice (a restart)
    assert asyncio.run(hd.run_daily_hymns(client, day, hd.DEFAULT_HYMNDAY_TIME)) == 1 and b.sent


def test_setup(hd):
    from conftest import FakeCtx
    import core

    def run(action="", arg="", mentions=()):
        ctx = FakeCtx()
        ctx.guild = type("G", (), {"id": 1, "name": "Test"})()
        ctx.message = type("M", (), {"channel_mentions": list(mentions)})()
        ctx.channel = _Channel(555)
        asyncio.run(hd.cmd_hymndaysetup.callback(ctx, action, arg=arg))
        return ctx

    assert "will be posted in <#100>" in run("channel", mentions=[_Channel(100)]).sent[-1]["content"]
    assert run("time", "6:30").sent[-1]["content"] == "Daily hymn time set to **06:30 UTC**."
    assert core._load_guild_config()["1"] == {"hymnday_channel_id": 100, "hymnday_time": "06:30"}
    run("off")
    assert core._load_guild_config()["1"]["hymnday_channel_id"] is None
    assert "Hymn of the day" in run("test").channel.sent[0]["content"]


def test_command(hd, fake_ctx):
    asyncio.run(hd.cmd_hymnday.callback(fake_ctx, when="2027-03-28"))
    assert "For Easter Day" in fake_ctx.sent[-1]["content"]
    asyncio.run(hd.cmd_hymnday.callback(fake_ctx, when="not a date"))
    assert "2026-12-25" in fake_ctx.sent[-1]["content"]
