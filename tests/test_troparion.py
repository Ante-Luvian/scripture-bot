"""!troparion: the day's Orthodox hymns, from the OCA's daily troparia page."""
import asyncio
import datetime
from pathlib import Path

import pytest

D = datetime.date
PAGE = (Path(__file__).parent / "fixtures" / "oca_troparia_2026-10-17.html").read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def tr(bot_module):
    from bot_commands import troparion
    return troparion


@pytest.fixture
def offline(tr, monkeypatch):
    """The fixture page in place of the OCA site."""
    monkeypatch.setattr(tr, "_CACHE", {D(2026, 10, 17): tr.parse(PAGE)})
    return tr


def test_parse(tr):
    items = tr.parse(PAGE)
    assert items[0]["name"] == "Prophet Hosea"
    trop, kont = items[0]["hymns"]
    assert (trop["kind"], trop["tone"]) == ("Troparion", "2")
    assert trop["text"].startswith("We celebrate the memory\nof Your prophet Hosea, O Lord;")   # "/" -> a new line
    assert kont["kind"] == "Kontakion" and "(Podoben" in kont["text"] and "<" not in kont["text"]
    assert any(i["name"] == "Monastic Martyr Andrew of Crete" for i in items)


def test_messages_fit_discord(offline):
    msgs = offline.messages(D(2026, 10, 17), offline.commemorations(D(2026, 10, 17)))
    assert msgs[0]["content"].startswith("☦️ **Troparia and kontakia** · Saturday 17 October")
    for m in msgs:
        assert len(m["embeds"]) <= 10 and sum(len(e) for e in m["embeds"]) <= 6000
    assert msgs[0]["embeds"][0].title == "Prophet Hosea"


def test_command(offline, fake_ctx, monkeypatch):
    monkeypatch.setattr(offline, "_today", lambda: D(2026, 10, 17))
    asyncio.run(offline.cmd_troparion.callback(fake_ctx, when=""))
    assert any(e.title == "Prophet Hosea" for s in fake_ctx.sent for e in s.get("embeds", []))
    asyncio.run(offline.cmd_troparion.callback(fake_ctx, when="not a day"))
    assert "Give a date" in fake_ctx.sent[-1]["content"]


def test_unreachable(tr, fake_ctx, monkeypatch):
    monkeypatch.setattr(tr, "_CACHE", {})
    monkeypatch.setattr(tr.urllib.request, "urlopen", lambda *a, **k: (_ for _ in ()).throw(OSError("offline")))
    assert asyncio.run(tr.send_troparia(fake_ctx, D(2026, 10, 18))) is False
    assert "couldn't reach" in fake_ctx.sent[-1]["content"]
    assert D(2026, 10, 18) not in tr._CACHE                       # a failure isn't remembered


class _Channel:
    def __init__(self, cid):
        self.id, self.sent, self.mention = cid, [], f"<#{cid}>"

    async def send(self, content=None, **kwargs):
        self.sent.append({"content": content, **kwargs})


def test_daily_post(offline):
    import core
    core._update_guild_config(1, troparion_channel_id=100, troparion_time="05:00")
    a = _Channel(100)
    client = type("C", (), {"get_channel": lambda self, cid: {100: a}.get(cid)})()
    assert asyncio.run(offline.run_daily_troparia(client, D(2026, 10, 17), "05:00")) == 1
    assert "Troparia and kontakia" in a.sent[0]["content"]
    assert asyncio.run(offline.run_daily_troparia(client, D(2026, 10, 17), "05:00")) == 0   # not twice


@pytest.mark.live
def test_the_oca_page_still_parses(tr, monkeypatch):
    monkeypatch.setattr(tr, "_CACHE", {})
    items = tr.commemorations(datetime.date.today())
    assert items and all(i["hymns"] for i in items)
