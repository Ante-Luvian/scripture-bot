"""!angelus: the Angelus (the Regina caeli in Eastertide), and its posts at the chosen hours."""
import asyncio
import datetime

import pytest

from tests.conftest import needs_sung_chant

D = datetime.date


@pytest.fixture(scope="module")
def ang(bot_module):
    from bot_commands import angelus
    return angelus


@pytest.mark.parametrize("day, easter", [
    (D(2027, 3, 26), False),          # Good Friday (Easter 2027 is 28 March)
    (D(2027, 3, 27), True),           # Holy Saturday: "From Holy Saturday..."
    (D(2027, 5, 16), True),           # Pentecost
    (D(2027, 5, 22), True),           # "...till Trinity Eve"
    (D(2027, 5, 23), False),          # Trinity Sunday
    (D(2026, 10, 14), False),
])
def test_eastertide(ang, day, easter):
    assert ang.eastertide(day) is easter


@needs_sung_chant
def test_the_angelus(ang):
    m = ang.angelus_message(D(2026, 10, 14))
    english, latin = m["embeds"]
    assert english.description.startswith("℣. The Angel of the Lord declared unto Mary.")
    assert english.description.count("Hail, Mary, full of grace") == 3            # written out each time
    assert latin.description.startswith("℣. Angelus Domini nuntiavit Mariæ.") and latin.description.count("Ave, Maria") == 3
    assert "Manual of Prayers" in latin.footer.text
    assert m["file"].filename == "Ave_Maria_sung.ogg" and "Ave Maria" in m["content"]


@needs_sung_chant
def test_regina_caeli_in_eastertide(ang):
    m = ang.angelus_message(D(2027, 4, 10))
    english, latin = m["embeds"]
    assert "Regina" in english.title and english.description.startswith("O Queen of heaven, rejoice! Alleluia.")
    assert latin.description.startswith("Regina Cœli, lætare!")
    assert m["file"].filename == "Regina_caeli_sung.ogg"


@needs_sung_chant
def test_the_sung_chants_exist(ang):
    from bot_commands.hymns import hymns, sung_path
    titles = {h["title"]: h for h in hymns()}
    for title in ang.SUNG.values():
        assert sung_path(titles[title]) is not None


class _Channel:
    def __init__(self, cid):
        self.id, self.sent, self.mention = cid, [], f"<#{cid}>"

    async def send(self, content=None, **kwargs):
        self.sent.append({"content": content, **kwargs})


def test_posts_at_each_hour_once(ang):
    import core
    core._update_guild_config(1, angelus_channel_id=100, angelus_times=["06:00", "12:00", "18:00"])
    core._update_guild_config(2, angelus_channel_id=200)                          # noon, the default
    a, b = _Channel(100), _Channel(200)
    client = type("C", (), {"get_channel": lambda self, cid: {100: a, 200: b}.get(cid)})()
    at = lambda h: datetime.datetime(2026, 10, 14, h, 0, tzinfo=datetime.timezone.utc)
    assert asyncio.run(ang.run_angelus(client, at(6))) == 1 and len(a.sent) == 1 and not b.sent
    assert asyncio.run(ang.run_angelus(client, at(6))) == 0                       # not twice (a restart)
    assert asyncio.run(ang.run_angelus(client, at(12))) == 2 and len(a.sent) == 2 and len(b.sent) == 1
    assert asyncio.run(ang.run_angelus(client, at(9))) == 0


def test_setup(ang):
    from conftest import FakeCtx
    import core

    def run(action="", arg="", mentions=()):
        ctx = FakeCtx()
        ctx.guild = type("G", (), {"id": 1, "name": "Test"})()
        ctx.message = type("M", (), {"channel_mentions": list(mentions)})()
        ctx.channel = _Channel(555)
        asyncio.run(ang.cmd_angelussetup.callback(ctx, action, arg=arg))
        return ctx

    assert "posted in <#100> at 12:00 UTC" in run("channel", mentions=[_Channel(100)]).sent[-1]["content"]
    assert "06:00, 12:00, 18:00" in run("time", "18:00 6:00 12:00").sent[-1]["content"]
    assert core._load_guild_config()["1"]["angelus_times"] == ["06:00", "12:00", "18:00"]
    assert "24-hour" in run("time", "noon").sent[-1]["content"]
    run("off")
    assert core._load_guild_config()["1"]["angelus_channel_id"] is None
    assert run("test").channel.sent[0]["embeds"]
