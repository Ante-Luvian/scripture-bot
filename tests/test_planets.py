"""!planets: the tropical zodiac, from NASA JPL's DE421 through Skyfield. The reference values are NASA JPL
Horizons' (observer ecliptic-of-date longitude, quantity 31), fetched 2026-10-24; the bot agreed to 0.3",
the Moon in 1969 to 1.3". Skipped where Skyfield or data/de421.bsp isn't installed."""
import datetime as dt

import pytest

skyfield = pytest.importorskip("skyfield")


@pytest.fixture(scope="module")
def planets(bot_module):
    from bot_commands import planets
    if planets.sky() is None:
        pytest.skip("data/de421.bsp isn't downloaded")
    return planets


UTC = dt.timezone.utc
HORIZONS = {   # 2026-10-24 12:00 UTC
    "Sun": 211.09355, "Moon": 9.15282, "Mercury": 230.97633, "Venus": 210.53968, "Mars": 134.75780,
    "Jupiter": 143.34872, "Saturn": 9.78667, "Uranus": 64.93506, "Neptune": 2.25061, "Pluto": 303.08518,
}


def test_positions_agree_with_nasa(planets):
    got = {name: lon for name, _, lon, _ in planets.positions(dt.datetime(2026, 10, 24, 12, tzinfo=UTC))}
    for name, lon in HORIZONS.items():
        assert abs(((got[name] - lon + 180) % 360 - 180) * 3600) < 2, name     # within 2 arcseconds


def test_retrograde(planets):
    retro = {name for name, _, _, r in planets.positions(dt.datetime(2026, 10, 25, 12, tzinfo=UTC)) if r}
    assert {"Mercury", "Venus", "Saturn"} <= retro and not {"Sun", "Moon", "Mars"} & retro


def test_the_sun_enters_aries_at_the_equinox(planets):
    """Tropical: 0° Aries is the March equinox (2026-03-20 14:46 UTC)."""
    (moment, text), *_ = planets.events(dt.date(2026, 3, 20))
    assert text == "☉ Sun enters ♈ Aries"
    assert abs((moment - dt.datetime(2026, 3, 20, 14, 46, tzinfo=UTC)).total_seconds()) < 90
    winter = dict((t, m) for m, t in planets.events(dt.date(2026, 12, 21)))
    assert abs((winter["☉ Sun enters ♑ Capricorn"] - dt.datetime(2026, 12, 21, 20, 50, tzinfo=UTC)).total_seconds()) < 90


def test_aspects_are_exact(planets):
    day = planets.events(dt.date(2026, 10, 26))
    square = next(m for m, t in day if t.startswith("☉ Sun □ square ♇ Pluto"))
    by = {n: lon for n, _, lon, _ in planets.positions(square)}
    assert abs(abs((by["Sun"] - by["Pluto"] + 180) % 360 - 180) - 90) < 1 / 60      # to the arcminute
    assert any(t.startswith("☽ Full Moon in ♉ Taurus") for _, t in day)
    assert any("Mercury stations retrograde" in t for _, t in planets.events(dt.date(2026, 10, 24)))


def test_zodiac_and_dates(planets):
    assert planets.zodiac(211.09355) == "♏ Scorpio 1°06′"
    assert planets.zodiac(359.9999) == "♈ Aries 0°00′"           # never "Pisces 30°00′"
    assert planets.zodiac(29.9) == "♈ Aries 29°54′"
    now = dt.datetime(2026, 10, 24, 18, tzinfo=UTC)
    assert planets.parse_when("", now) is now
    assert planets.parse_when("2026-12-25", now) == dt.datetime(2026, 12, 25, 12, tzinfo=UTC)
    assert planets.parse_when("tomorrow", now).date() == dt.date(2026, 10, 25)
    assert "YYYY-MM-DD" in planets.parse_when("next tuesday", now)
    assert "1900" in planets.parse_when("2100-01-01", now)
    assert "calendar" in planets.parse_when("2026-02-30", now)


def test_the_embed_fits(planets):
    e = planets.planets_embed(dt.datetime(2026, 10, 26, 12, tzinfo=UTC), False)
    assert e.title == "🪐 The sky on 26 October 2026" and len(e) < 6000
    assert e.description.count("\n") == 9 and "℞" in e.description
