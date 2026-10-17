"""!icon: Orthodox icons, the feast's on its day."""
import asyncio
import datetime

import pytest

D = datetime.date


@pytest.fixture(scope="module")
def ic(bot_module):
    from bot_commands import icons
    return icons


@pytest.mark.parametrize("year, pascha", [(2025, D(2025, 4, 20)), (2026, D(2026, 4, 12)), (2027, D(2027, 5, 2)),
                                          (2028, D(2028, 4, 16))])
def test_orthodox_pascha(ic, year, pascha):
    assert ic.orthodox_pascha(year) == pascha


@pytest.mark.parametrize("day, key", [
    (D(2026, 12, 25), "nativity"), (D(2027, 1, 6), "theophany"), (D(2026, 8, 6), "transfiguration"),
    (D(2026, 8, 15), "dormition"), (D(2026, 4, 12), "resurrection"), (D(2026, 4, 5), "entry into jerusalem"),
    (D(2026, 5, 21), "ascension"), (D(2026, 5, 31), "trinity"), (D(2026, 12, 6), "st nicholas"),
])
def test_feasts(ic, day, key):
    assert ic.icon_for(day) == (key, True)


def test_ordinary_days_take_each_in_turn(ic):
    days = [D(2026, 10, 1) + datetime.timedelta(days=n) for n in range(12)]
    keys = [ic.icon_for(d) for d in days]
    assert all(not feast for _, feast in keys) and len({k for k, _ in keys}) == 12


def test_every_icon_has_its_image_and_words(ic):
    for key, icon in ic.icons().items():
        assert (ic.ICONS_DIR / icon["file"]).stat().st_size > 20_000, key
        assert len(icon["about"]) > 100, key


@pytest.mark.parametrize("query, key", [("trinity", "trinity"), ("Rublev", "trinity"), ("Vladimir", "vladimir"),
                                        ("easter", "resurrection"), ("St. George", "st george"),
                                        ("palm sunday", "entry into jerusalem"), ("christmas", "nativity")])
def test_find(ic, query, key):
    assert ic.find(query) == key


def test_command(ic, fake_ctx):
    asyncio.run(ic.send_icon(fake_ctx, "trinity"))
    sent = fake_ctx.sent[-1]
    assert sent["embed"].title == "☦️ The Holy Trinity, by Andrei Rublev" and sent["file"].filename == "trinity.jpg"
    assert sent["embed"].image.url == "attachment://trinity.jpg"
    asyncio.run(ic.send_icon(fake_ctx, "list"))
    great = fake_ctx.sent[-1]["embed"].fields[1].value
    assert "`!icon nativity`" in great and "st george" not in great
    asyncio.run(ic.send_icon(fake_ctx, ""))
    assert "Icon of the day" in fake_ctx.sent[-1]["content"] or "today's feast" in fake_ctx.sent[-1]["content"]
    asyncio.run(ic.send_icon(fake_ctx, "zzzz"))
    assert "don't have an icon" in fake_ctx.sent[-1]["content"]
