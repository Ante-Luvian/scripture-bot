"""!salah: the day's Muslim prayer times, from Aladhan."""
import asyncio

import pytest

DATA = {"timings": {"Fajr": "05:38", "Sunrise": "07:29", "Dhuhr": "12:46", "Asr": "15:30", "Maghrib": "18:01",
                    "Isha": "19:46", "Imsak": "05:28"},
        "date": {"readable": "18 Oct 2026", "hijri": {"day": "7", "month": {"en": "Jumādá al-ūlá"}, "year": "1448"}},
        "meta": {"timezone": "Europe/London", "method": {"name": "Muslim World League"}}}


@pytest.fixture
def sa(bot_module, monkeypatch):
    from bot_commands import salah
    monkeypatch.setattr(salah, "fetch", lambda place: DATA if place == "London" else None)
    return salah


def test_times(sa, fake_ctx):
    asyncio.run(sa.send_salah(fake_ctx, "London"))
    e = fake_ctx.sent[-1]["embed"]
    assert e.title == "🕌 Prayer times — London" and "7 Jumādá al-ūlá 1448 AH" in e.description
    lines = e.fields[0].value.splitlines()
    assert lines[0] == "**Fajr** 05:38 — the dawn prayer" and lines[-1] == "**Isha** 19:46 — the night prayer"
    assert "Europe/London" in e.footer.text and "Muslim World League" in e.footer.text


def test_unknown_place_and_no_place(sa, fake_ctx):
    asyncio.run(sa.send_salah(fake_ctx, "Zzzq"))
    assert "couldn't find prayer times for **Zzzq**" in fake_ctx.sent[-1]["content"]
    asyncio.run(sa.send_salah(fake_ctx, ""))
    assert "Which place?" in fake_ctx.sent[-1]["content"]


@pytest.mark.live
def test_aladhan_live(bot_module):
    from bot_commands import salah
    data = salah.fetch("Cairo, Egypt")
    assert data and data["timings"]["Fajr"] and data["meta"]["timezone"] == "Africa/Cairo"
