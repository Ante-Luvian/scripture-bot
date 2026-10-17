"""!prayer st michael: traditional prayers by name."""
import asyncio
import re

import pytest

from core import ROOT


@pytest.fixture(scope="module")
def pr(bot_module):
    from bot_commands import prayers
    return prayers


# a line of each prayer, as its Wikipedia article prints it (checked when the article is cached)
CHECK = {"st michael": ("Prayer to Saint Michael", "thrust into Hell Satan and all of the other evil spirits"),
         "memorare": ("Memorare", "despise not my petitions"),
         "anima christi": ("Anima Christi", "Within Thy wounds hide me"),
         "act of contrition": ("Act of Contrition", "O my God, I am heartily sorry for having offended Thee"),
         "morning offering": ("Morning Offering", "in union with the Holy Sacrifice of the Mass throughout the world"),
         "sub tuum": ("Sub tuum praesidium", "We fly to thy protection"),
         "st joseph": ("Prayer to Saint Joseph", "Defend, O most watchful guardian of the Holy Family"),
         "st francis": ("Prayer of Saint Francis", "it is in dying that one awakens to eternal life"),
         "grace": ("Grace (prayer)", "which we are about to receive from Thy bounty"),
         "fatima": ("Fátima prayers", "lead all souls to heaven, especially those"),
         "divine praises": ("Divine Praises", "Blessed be the great Mother of God"),
         "angel of god": ("Angel of God", "to whom God's love commits me here"),
         "jesus prayer": ("Jesus Prayer", "Lord Jesus Christ, Son of God, have mercy on me, a sinner"),
         "trisagion": ("Trisagion", "Holy God, Holy Mighty, Holy Immortal, have mercy on us"),
         "o heavenly king": ("O Heavenly King", "Who art everywhere present and fillest all things"),
         "st ephrem": ("Prayer of Saint Ephrem", "grant me to see mine own failings, and not to condemn others"),
         "rejoice o virgin": ("Hail Mary", "because it was the Saviour of our souls that thou borest")}


def test_the_wording(pr):
    cache = ROOT / "scripts" / ".cache" / "wikipedia"
    checked = 0
    for key, (article, line) in CHECK.items():
        assert line.lower() in pr.PRAYERS[key][2].lower(), key
        f = cache / (re.sub(r"[^A-Za-z0-9]+", "_", article).strip("_") + ".wiki")
        if f.exists():
            text = re.sub(r"\s+", " ", re.sub(r"<[^>]+>|''+|:", " ", f.read_text(encoding="utf-8"))).lower()
            assert re.sub(r"\s+", " ", line.lower()) in text, (key, article)
            checked += 1
    if not checked:
        pytest.skip("the Wikipedia articles aren't cached here")


@pytest.mark.parametrize("query, key", [("st michael", "st michael"), ("Saint Michael", "st michael"),
                                        ("michael", "st michael"), ("Memorare", "memorare"),
                                        ("soul of christ", "anima christi"), ("guardian angel", "angel of god"),
                                        ("salve regina", "hail holy queen"), ("Lord's Prayer", "our father"),
                                        ("contrition", "act of contrition"), ("requiem", "eternal rest"),
                                        ("Jesus Prayer", "jesus prayer"), ("holy god", "trisagion"),
                                        ("axion estin", "axion estin"), ("ephrem", "st ephrem"),
                                        ("symbol of faith", "orthodox creed")])
def test_find(pr, query, key):
    assert pr.find(query) == key


def test_the_chants_exist(pr):
    from bot_commands.hymns import hymns
    titles = {h["title"] for h in hymns()}
    for key, p in pr.PRAYERS.items():
        assert not p[5] or p[5] in titles, key


def test_the_command(pr, fake_ctx):
    from bot_commands import liturgy
    asyncio.run(liturgy.cmd_prayer.callback(fake_ctx, name="st michael"))
    sent = fake_ctx.sent[-1]
    assert sent["embed"].title == "🙏 Prayer to Saint Michael" and "Sancte Míchael" in sent["embed"].fields[0].value
    asyncio.run(liturgy.cmd_prayer.callback(fake_ctx, name="memorare"))
    assert fake_ctx.sent[-1]["file"].filename == "Memorare_sung.ogg"
    asyncio.run(liturgy.cmd_prayer.callback(fake_ctx, name="list"))
    assert "`!prayer st michael`" in fake_ctx.sent[-1]["embed"].description
    asyncio.run(liturgy.cmd_prayer.callback(fake_ctx, name="trisagion"))
    assert fake_ctx.sent[-1]["embed"].fields[0].name == "In Greek"
    asyncio.run(liturgy.cmd_prayer.callback(fake_ctx, name="angelus"))
    assert "`!angelus`" in fake_ctx.sent[-1]["content"]
    asyncio.run(liturgy.cmd_prayer.callback(fake_ctx, name="zzzz"))
    assert "I don't know a prayer called" in fake_ctx.sent[-1]["content"]
