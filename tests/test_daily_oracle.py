"""The daily oracle: posting through the real oracle commands, the per-guild
schedule, and !oraclesetup."""
import asyncio

import pytest

from conftest import FakeCtx


@pytest.fixture(scope="module")
def oracles(bot_module):
    from bot_commands import oracles
    return oracles


@pytest.fixture(autouse=True)
def no_stats_allowed(oracles, monkeypatch):
    def fail(*a):
        raise AssertionError("the daily oracle must not record usage stats")
    monkeypatch.setattr(oracles, "record_special_stat", fail)


class FakeChannel:
    def __init__(self, cid=100):
        self.id, self.sent = cid, []
        self.mention = f"<#{cid}>"

    async def send(self, content=None, **kwargs):
        self.sent.append({"content": content, **kwargs})

    def typing(self):
        class _T:
            async def __aenter__(self): return self
            async def __aexit__(self, *e): return False
        return _T()


def test_bibliomancy_is_not_a_daily_oracle(oracles, monkeypatch):
    # excluded at the owner's request: never offered, never picked by "any",
    # and a stored "sortesbiblicae" setting falls back to one of the others
    assert "sortesbiblicae" not in oracles._DAILY_KINDS
    picked = set()
    for _ in range(40):
        picked.add(asyncio.run(oracles.post_daily_oracle(FakeChannel(), "any")))
    assert "sortesbiblicae" not in picked
    assert asyncio.run(oracles.post_daily_oracle(FakeChannel(), "sortesbiblicae")) in oracles._DAILY_KINDS
    assert "Choose `any`, `virgil`, `homer`, `delphi`, or `oracle`." == _run(
        oracles, _admin_ctx(), "kind", "sortesbiblicae")["content"]


@pytest.mark.parametrize("kind", ["virgil", "homer", "delphi", "oracle"])
def test_post_daily_oracle(oracles, monkeypatch, kind):
    if kind == "homer":   # land on a roll that has an answer
        monkeypatch.setattr(oracles, "_load_homer", lambda: {"111": "Be bold."})
        monkeypatch.setattr(oracles.random, "randint", lambda a, b: 1)
    channel = FakeChannel()
    assert asyncio.run(oracles.post_daily_oracle(channel, kind)) == kind
    assert len(channel.sent) == 1
    assert channel.sent[0]["content"] == oracles.DAILY_ORACLE_HEADER
    assert channel.sent[0]["embed"] and channel.sent[0]["view"].timeout is None


def test_any_picks_one_of_the_oracles(oracles):
    channel = FakeChannel()
    assert asyncio.run(oracles.post_daily_oracle(channel, "any")) in oracles._DAILY_KINDS


class FakeClient:
    def __init__(self, channels):
        self.channels = channels

    def get_channel(self, cid):
        return self.channels.get(cid)


def test_schedule_posts_only_where_the_time_matches(oracles):
    import core
    core._update_guild_config(1, oracle_channel_id=100, oracle_time="12:00", oracle_kind="delphi")
    core._update_guild_config(2, oracle_channel_id=200, oracle_time="13:00", oracle_kind="delphi")
    core._update_guild_config(3, votd_channel_id=300)                 # no daily oracle
    a, b = FakeChannel(100), FakeChannel(200)
    client = FakeClient({100: a, 200: b})
    assert asyncio.run(oracles.run_daily_oracles(client, "12:00")) == 1
    assert len(a.sent) == 1 and b.sent == []
    assert asyncio.run(oracles.run_daily_oracles(client, "12:01")) == 0


def test_default_time_is_noon_utc(oracles):
    import core
    core._update_guild_config(1, oracle_channel_id=100)
    a = FakeChannel(100)
    assert asyncio.run(oracles.run_daily_oracles(FakeClient({100: a}), "12:00")) == 1


# ── !oraclesetup ────────────────────────────────────────────────────────────

def _admin_ctx(mentions=(), channel=None):
    ctx = FakeCtx()
    ctx.guild = type("G", (), {"id": 1, "name": "Test"})()
    ctx.message = type("M", (), {"channel_mentions": list(mentions)})()
    ctx.channel = channel
    return ctx


def _guild():
    import core
    return core._load_guild_config().get("1", {})


def _run(oracles, ctx, action="", arg=""):
    asyncio.run(oracles.cmd_oraclesetup.callback(ctx, action, arg=arg))
    return ctx.sent[-1]


def test_setup_channel_time_kind_off(oracles):
    chan = FakeChannel(100)
    assert "will be posted in <#100>" in _run(oracles, _admin_ctx([chan]), "channel")["content"]
    assert _run(oracles, _admin_ctx(), "time", "7:05")["content"] == "Daily oracle time set to **07:05 UTC**."
    assert _run(oracles, _admin_ctx(), "kind", "virgil")["content"] == "Daily oracle set to **virgil**."
    assert _guild() == {"oracle_channel_id": 100, "oracle_time": "07:05", "oracle_kind": "virgil"}
    assert "Use 24-hour UTC time" in _run(oracles, _admin_ctx(), "time", "25:00")["content"]
    assert "Choose `any`" in _run(oracles, _admin_ctx(), "kind", "tarot")["content"]
    status = _run(oracles, _admin_ctx())["embed"]
    assert [f.value for f in status.fields] == ["<#100>", "07:05", "virgil"]
    _run(oracles, _admin_ctx(), "off")
    assert _guild()["oracle_channel_id"] is None


def test_setup_test_posts_one_now(oracles, bot_module, monkeypatch):
    here = FakeChannel(555)
    ctx = _admin_ctx(channel=here)
    asyncio.run(oracles.cmd_oraclesetup.callback(ctx, "test", arg=""))   # no channel set: posts here
    assert here.sent and here.sent[0]["content"] == oracles.DAILY_ORACLE_HEADER
