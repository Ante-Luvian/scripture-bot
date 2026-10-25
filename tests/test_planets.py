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
    assert sun.value == "Felt most by those born under ♏ Scorpio."       # (no looks-not-forecast quote)
    assert e.footer.text.count("Lilly") == 2
    assert all(len(f.value) <= 1024 and len(f.name) <= 256 for f in e.fields) and len(e) < 6000
    square = next(f for f in planets.horoscope_embed(dt.date(2026, 10, 26)).fields if "Pluto" in f.name)
    assert square.value == "Felt most by those born under ♏ Scorpio and ♒ Aquarius."


def test_sepharials_forecasts_are_his_words_and_go_to_the_right_conjunctions(planets):
    text = planets._sepharial_text()
    for words in planets.SEPHARIAL.values():
        assert words in text, words
    assert planets.old_reading({"lilly": ("♂", "☌", "♀")}) == (
        "Sepharial", "4.2:2", "Mars over the place of Venus will engender passionate love.")
    assert planets.old_reading({"lilly": ("☿", "☌", "♂")})[2].endswith("quarrels and disputation.")
    who, where, _ = planets.old_reading({"lilly": ("♄", "☌", "♃")})            # Sepharial hasn't it: Lilly
    assert who == "Lilly" and where.startswith("Appendix 4:")
    assert planets.old_reading({"lilly": ("♂", "in", "♏")}) is None           # (looks, not a forecast)
    assert planets.old_reading({"lilly": None}) is None


def test_the_twelve_signs_are_asked_for_once_a_day_and_kept(planets, monkeypatch):
    import asyncio
    import json as _json
    asked = []
    reply = _json.dumps({name: f"A reading for {name}." for name, _ in planets.SIGNS})
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test")
    monkeypatch.setattr(planets, "_ask_claude", lambda prompt: asked.append(prompt) or reply)
    monkeypatch.setattr(planets, "_writing", None)
    today = dt.datetime.now(dt.timezone.utc).date()
    first = asyncio.run(planets.sign_readings(today))
    again = asyncio.run(planets.sign_readings(today))
    assert first == again and first["Leo"] == "A reading for Leo." and len(asked) == 1
    assert "Today's events" in asked[0] and "Positions at noon UTC" in asked[0]
    assert asyncio.run(planets.sign_readings(today - dt.timedelta(days=3))) is None     # (today only)
    e = planets.signs_embed(first)
    assert len(e.fields) == 12 and "Written by AI" in e.footer.text
    assert [f.name for f in planets.signs_embed(first, 4).fields] == ["♌ Leo"]


def test_no_key_no_ai(planets, monkeypatch):
    import asyncio
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setattr(planets, "_ask_claude", lambda prompt: (_ for _ in ()).throw(AssertionError("asked")))
    assert asyncio.run(planets.sign_readings(dt.datetime.now(dt.timezone.utc).date())) is None


def test_a_reply_that_isnt_twelve_readings_is_refused(planets):
    import json as _json
    assert planets._readings_from("not json") is None
    assert planets._readings_from(_json.dumps({"Leo": "x"})) is None
    good = {name: "Fine." for name, _ in planets.SIGNS}
    assert planets._readings_from("Here you are:\n" + _json.dumps(good)) == good


def test_horoscope_for_one_sign(planets):
    assert planets._sign_index("Leo") == 4 and planets._sign_index("scorpios") == 7 and planets._sign_index("♓") == 11
    assert planets._sign_index("2026-10-26") is None
    e = planets.horoscope_embed(dt.date(2026, 10, 26), True, 7)
    assert e.title.startswith("🪐 The sky today for ♏ Scorpio")
    assert [f.name for f in e.fields if "Pluto" in f.name] and not [f for f in e.fields if "Full Moon" in f.name]


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
    # each post: !planets (positions and the Moon, not the events), then !horoscope (the events, no Moon)
    assert len(sent) == 4
    sky, reading = sent[0]["embed"], sent[1]["embed"]
    assert sky.title == "🪐 The sky on 23 October 2026" and sky.description.count("\n") == 9
    assert [f.name for f in sky.fields] == ["The Moon"]
    assert reading.title.startswith("🪐 The sky today") and "The Moon" not in [f.name for f in reading.fields]
    assert any("Sun enters ♏ Scorpio" in f.name for f in reading.fields)


def test_the_embed_fits(planets):
    e = planets.planets_embed(dt.datetime(2026, 10, 26, 12, tzinfo=UTC), False)
    assert e.title == "🪐 The sky on 26 October 2026" and len(e) < 6000
    assert e.description.count("\n") == 9 and "℞" in e.description
