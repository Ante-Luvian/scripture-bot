"""!saint: Butler's Lives of the Saints and the Golden Legend, by day and by name."""
import asyncio
import datetime

import pytest


@pytest.fixture(scope="module")
def S(bot_module):
    from bot_commands import saints
    return saints


def _ask(S, fake_ctx, query):
    asyncio.run(S.send_saint(fake_ctx, query))
    return fake_ctx.sent[-1]


def _components(view):
    return [getattr(i, "item", i) for i in view.children] if view else []


def test_every_day_has_a_saint(S):
    days = {(s["month"], s["day"]) for s in S.saints() if s["month"]}
    assert all((d.month, d.day) in days for d in (datetime.date(2024, 1, 1) + datetime.timedelta(n) for n in range(366)))


def test_butler_with_the_golden_legend_button(S, fake_ctx):
    sent = _ask(S, fake_ctx, "George")
    assert sent["embed"].title == "St. George, Martyr — 23 April"
    assert sent["embed"].description.startswith("ST. GEORGE was born in Cappadocia")
    [button] = _components(sent["view"])
    assert button.label == "Golden Legend" and button.custom_id.startswith("saint:gl:")


def test_a_golden_legend_saint_opens_to_the_legend(S, fake_ctx):
    sent = _ask(S, fake_ctx, "Christopher")
    assert sent["embed"].title == "St. Christopher — 25 July"
    assert "named Reprobus" in sent["embed"].description and "Golden Legend" in sent["embed"].footer.text
    assert [b.emoji.name for b in _components(sent["view"])] == ["◀", "▶"]          # a long chapter: pages


def test_two_of_a_name_offer_a_choice(S, fake_ctx):
    sent = _ask(S, fake_ctx, "Augustine")
    assert "Apostle of England" in sent["embed"].description and "Augustine of Hippo" in sent["embed"].description
    [menu] = _components(sent["view"])
    assert menu.custom_id.startswith("saintpick:") and len(menu.options) == 2
    hippo = S.by_key(next(o.value for o in menu.options if "Hippo" in o.label))
    assert hippo["golden_legend"] and "Austin, or Augustine" in hippo["golden_legend"][0]


def test_by_day(S, fake_ctx):
    sent = _ask(S, fake_ctx, "25 July")
    assert sent["content"].startswith("🕯️ **25 July**") and sent["embed"].title == "St. James, Apostle — 25 July"
    menu = _components(sent["view"])[-1]
    assert [o.label for o in menu.options] == ["St. Christopher"]
    assert S.parse_day("July 25") == S.parse_day("7/25") == S.parse_day("25th Jul") == (7, 25)
    assert S.parse_day("31 February") is None and S.parse_day("Christopher") is None


def test_today(S, fake_ctx, monkeypatch):
    monkeypatch.setattr(S, "_today", lambda: datetime.date(2026, 4, 23))
    sent = _ask(S, fake_ctx, "")
    assert sent["content"].startswith("🕯️ **Saint of the day**") and "George" in sent["embed"].title


def test_spellings_and_unknowns(S, fake_ctx):
    assert any("Alexandria" in s["name"] for s in S.find_saints("Katherine"))
    assert "don't know a saint" in _ask(S, fake_ctx, "zzz")["content"]


def test_the_legend_pages(S):
    s = S.find_saints("Christopher")[0]
    pages = S.legend_pages(s)
    assert len(pages) > 1 and all(len(p) <= S.PAGE for p in pages)
    assert "".join(pages).replace("\n", "").replace(" ", "") == S.legend_text(s).replace("\n", "").replace(" ", "")


def test_no_message_repeats_a_custom_id(S):
    # Discord refuses the whole message if two components share a custom_id; "!saint daria"
    # (a two-page Legend chapter) once sent ◀ and ▶ both as "go to page 2"
    for s in S.saints():
        messages = [S.saint_message(s, S.saints()[:3], "Also")]
        for n, _ in enumerate(s.get("golden_legend", [])):
            messages += [S.legend_message(s, p, n) for p in range(len(S.legend_pages(s, n)))]
        for m in messages:
            ids = [c.custom_id for c in _components(m["view"])]
            assert len(ids) == len(set(ids)), (s["name"], ids)


def test_the_buttons_find_their_saint(S):
    for s in S.saints():
        assert S.by_key(S.saint_key(s)) is s


class _Channel:
    def __init__(self, cid):
        self.id, self.sent, self.mention = cid, [], f"<#{cid}>"

    async def send(self, content=None, **kwargs):
        self.sent.append({"content": content, **kwargs})


def test_daily_post(S):
    import core
    core._update_guild_config(1, saintday_channel_id=100, saintday_time="06:00")
    channel = _Channel(100)
    client = type("C", (), {"get_channel": lambda self, cid: {100: channel}.get(cid)})()
    day = datetime.date(2026, 7, 25)
    assert asyncio.run(S.run_daily_saints(client, day, "06:00")) == 1
    assert "Saint of the day" in channel.sent[0]["content"] and "James" in channel.sent[0]["embed"].title
    assert asyncio.run(S.run_daily_saints(client, day, "06:00")) == 0          # not twice (a restart)


def test_setup(S):
    from conftest import FakeCtx
    import core
    ctx = FakeCtx()
    ctx.guild = type("G", (), {"id": 1, "name": "Test"})()
    ctx.message = type("M", (), {"channel_mentions": [_Channel(100)]})()
    asyncio.run(S.cmd_saintsetup.callback(ctx, "channel"))
    asyncio.run(S.cmd_saintsetup.callback(ctx, "time", arg="5:30"))
    assert core._load_guild_config()["1"] == {"saintday_channel_id": 100, "saintday_time": "05:30"}
    asyncio.run(S.cmd_saintsetup.callback(ctx, "channel", arg="<#100> time 04:00"))     # both in one go
    assert core._load_guild_config()["1"]["saintday_time"] == "04:00" and "04:00 UTC" in ctx.sent[-1]["content"]
