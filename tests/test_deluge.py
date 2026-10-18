"""Deluge points: mods' sayings quietly kept in a ledger; !delugepoints for mods only."""
import asyncio
import datetime
import random
import types

import pytest


@pytest.fixture(scope="module")
def dl(bot_module):
    from bot_commands import deluge
    return deluge


@pytest.mark.parametrize("text, n", [
    ("+5 deluge points", 5), ("-10 delugepoints", -10), ("50 deluge points to @x", 50),
    ("50 deluge points from Gryffindor", -50), ("minus 3 deluge points for that", -3),
    ("a deluge point for you", 1), ("twenty-five Deluge Points", 25), ("1,000 deluge points", 1000),
    ("10k deluge points", 10_000), ("deluge points: -7", -7), ("you lose 4 deluge points", -4),
    ("−2 deluge points", -2), ("one hundred and fifty deluge points", 150),
    ("what are deluge points", None), ("the deluge points ledger", None), ("no deluge points", None),
    ("I love the deluge", None), ("+0 deluge points", 0),
])
def test_amount(dl, text, n):
    assert dl.amount(text) == n


def _user(uid, bot=False):
    return types.SimpleNamespace(id=uid, bot=bot, __str__=lambda self: f"user{uid}")


def _message(text, mentions=(), reply_to=None, mid=1, guild=7):
    ref = types.SimpleNamespace(resolved=types.SimpleNamespace(author=reply_to)) if reply_to else None
    return types.SimpleNamespace(id=mid, content=text, mentions=list(mentions), reference=ref, author=_user(99),
                                 guild=types.SimpleNamespace(id=guild, name="g"),
                                 created_at=datetime.datetime(2026, 10, 17, tzinfo=datetime.timezone.utc))


def test_the_ledger(dl):
    data = {}
    assert dl.record(data, _message("+5 deluge points", [_user(1), _user(2)]), mod=True) == {"1": 5, "2": 5}
    assert dl.record(data, _message("+5 deluge points", [_user(1)]), mod=True) == {}          # the same message: once
    dl.record(data, _message("50 deluge points from you", reply_to=_user(1), mid=2), mod=True)
    dl.record(data, _message("1000 deluge points", [_user(3)], mid=3), mod=False)           # not a mod: doesn't count
    dl.record(data, _message("+9 deluge points", [_user(4, bot=True)], mid=4), mod=True)   # nor do bots
    ledger = data["7"]
    assert ledger["points"] == {"1": -45, "2": 5}                 # negative points are allowed
    assert [e["given"] for e in ledger["log"]] == [{"1": 5, "2": 5}, {"1": -50}, {}, {}]


def test_mods(dl):
    assert dl.is_mod(types.SimpleNamespace(id=5, guild_permissions=types.SimpleNamespace(
        administrator=False, manage_guild=False, manage_messages=True)))
    assert not dl.is_mod(types.SimpleNamespace(id=5, guild_permissions=types.SimpleNamespace(
        administrator=False, manage_guild=False, manage_messages=False)))
    assert not dl.is_mod(None)


def test_listener_is_silent(dl, monkeypatch):
    sent = []
    channel = types.SimpleNamespace(send=lambda *a, **k: sent.append(a))
    m = _message("+3 deluge points", [_user(1)])
    m.author = types.SimpleNamespace(id=50, bot=False, guild_permissions=types.SimpleNamespace(
        administrator=True, manage_guild=False, manage_messages=False), __str__=lambda self: "mod")
    m.channel = channel
    asyncio.run(dl.deluge_listener(m))
    assert dl._load()["7"]["points"] == {"1": 3} and not sent


def test_excerpt(dl):
    points = {str(i): i - 10 for i in range(30)}
    embed = dl.ledger_embed(points, random.Random(1))
    lines = embed.description.splitlines()
    assert 1 <= len(lines) < 30 and "Delugery" in embed.title
    values = [int(line.split("**")[1].replace(",", "")) for line in lines]
    assert values == sorted(values, reverse=True)


def test_command_is_hidden_and_mods_only(dl, bot_module, fake_ctx):
    cmd = bot_module.bot.get_command("delugepoints")
    assert cmd.hidden
    fake_ctx.guild = types.SimpleNamespace(id=7)
    fake_ctx.author = types.SimpleNamespace(id=2, guild_permissions=types.SimpleNamespace(
        administrator=False, manage_guild=False, manage_messages=False))
    fake_ctx.message = types.SimpleNamespace(mentions=[])
    asyncio.run(cmd.callback(fake_ctx))
    assert fake_ctx.sent == []                                    # not a mod: as if it weren't there
    fake_ctx.author.guild_permissions.administrator = True
    asyncio.run(cmd.callback(fake_ctx))
    assert "empty" in fake_ctx.sent[-1]["embed"].description


def test_search_results_count_too(dl):
    raw = {"id": "500", "content": "+20 deluge points", "timestamp": "2026-08-01T12:00:00+00:00",
           "author": {"id": "9", "username": "xpnc"}, "mentions": [],
           "referenced_message": {"id": "499", "author": {"id": "3", "username": "groyper"}}}
    m = dl._searched(raw, types.SimpleNamespace(id=7))
    data = {}
    assert dl.record(data, m, mod=True) == {"3": 20} and data["7"]["log"][0]["author"] == "xpnc"
