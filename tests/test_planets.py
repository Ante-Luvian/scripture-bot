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


def test_lilly_has_a_reading_for_every_placement_and_every_possible_aspect(planets):
    """84 placements (7 planets x 12 signs); every pair's ☌; the ✶△ and ☐☍ of every pair but those that can't
    happen (Mercury and Venus never get far enough from the Sun, or Venus from Mercury)."""
    import itertools
    r = planets.lilly_readings()
    seven = "♄♃♂☉♀☿☽"
    assert all((p, "in", s) in r for p in seven for s in "♈♉♊♋♌♍♎♏♐♑♒♓")
    impossible = {frozenset("☉♀"), frozenset("☉☿"), frozenset("♀☿")}
    for a, b in itertools.combinations(seven, 2):
        assert planets.lilly_on((a, "☌", b)) and planets.lilly_on((b, "☌", a))
        if frozenset((a, b)) not in impossible:
            assert planets.lilly_on((a, "☐☍", b)), (a, b)
            if frozenset((a, b)) - {"☉"} != {"♀"} and frozenset((a, b)) - {"☉"} != {"☿"}:
                assert planets.lilly_on((a, "✶△", b)), (a, b)
    assert planets.lilly_on(("☉", "☐☍", "♇")) is None                 # Lilly never knew of Pluto


def test_the_horoscope(planets):
    """The voice message: "Venus is in conjunction with Mercury. Look out, Leos" -- each event, the signs it
    falls in, and Lilly on it where he has it."""
    e = planets.horoscope_embed(dt.date(2026, 10, 23))
    assert e.title == "🪐 The sky today — Friday, 23 October 2026"
    sun = next(f for f in e.fields if "Sun enters ♏ Scorpio" in f.name)
    assert sun.value.startswith("Felt most by those born under ♏ Scorpio.")
    assert "> Gives a remarkably square-built" in sun.value and "— *Appendix 3:" in sun.value
    assert sum(f.value.count("Lilly") for f in e.fields) == 0 and e.footer.text.count("Lilly") == 2   # (his name once, in the footer, and its !verse)
    assert all(len(f.value) <= 1024 and len(f.name) <= 256 for f in e.fields) and len(e) < 6000
    square = next(f for f in planets.horoscope_embed(dt.date(2026, 10, 26)).fields if "Pluto" in f.name)
    assert square.value == "Felt most by those born under ♏ Scorpio and ♒ Aquarius."


def test_the_lilly_references_open(planets, lookup):
    for ref, _ in [planets.lilly_on(("♂", "in", "♏")), planets.lilly_on(("♄", "☌", "♃"))]:
        short = ref.replace(planets.LILLY_APPENDIX, "Lilly appendix")
        assert lookup.get_verse(short)["found"], short


def test_the_daily_post_goes_once_a_day(planets):
    import asyncio
    sent = []

    class Channel:
        async def send(self, **kwargs):
            sent.append(kwargs)

    day = dt.date(2026, 10, 23)
    assert asyncio.run(planets.post_astroday(1, Channel(), day))
    assert not asyncio.run(planets.post_astroday(1, Channel(), day))       # (a restart doesn't post twice)
    assert asyncio.run(planets.post_astroday(1, Channel(), day, force=True))
    assert len(sent) == 2 and sent[0]["embed"].title.startswith("🪐 The sky today")


def test_the_embed_fits(planets):
    e = planets.planets_embed(dt.datetime(2026, 10, 26, 12, tzinfo=UTC), False)
    assert e.title == "🪐 The sky on 26 October 2026" and len(e) < 6000
    assert e.description.count("\n") == 9 and "℞" in e.description
