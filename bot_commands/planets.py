"""
!planets -- where the Sun, Moon and planets are in the (tropical) zodiac, and the day's events: exact
aspects between the planets, a planet entering a sign, turning retrograde or direct, the Moon's quarters.

Positions are NASA JPL's (the DE421 ephemeris, through Skyfield): apparent geocentric longitude on the
ecliptic and equinox of the date, which is the tropical zodiac. The ephemeris file, data/de421.bsp (17 MB,
1900-2050), isn't kept in git; fetch it with
    Invoke-WebRequest https://ssd.jpl.nasa.gov/ftp/eph/planets/bsp/de421.bsp -OutFile data/de421.bsp

    !planets                where everything is now, and today's events
    !planets 2026-12-25     that day (noon UTC), and its events
    !planets tomorrow       (or yesterday)
"""
import datetime as dt
import functools
import re

import discord

from core import ROOT, bot, log

EPHEMERIS = ROOT / "data" / "de421.bsp"
COLOR = discord.Color.from_rgb(40, 50, 110)
BODIES = [("Sun", "☉", "sun"), ("Moon", "☽", "moon"), ("Mercury", "☿", "mercury"), ("Venus", "♀", "venus"),
          ("Mars", "♂", "mars barycenter"), ("Jupiter", "♃", "jupiter barycenter"),
          ("Saturn", "♄", "saturn barycenter"), ("Uranus", "♅", "uranus barycenter"),
          ("Neptune", "♆", "neptune barycenter"), ("Pluto", "♇", "pluto barycenter")]
SIGNS = [("Aries", "♈"), ("Taurus", "♉"), ("Gemini", "♊"), ("Cancer", "♋"), ("Leo", "♌"), ("Virgo", "♍"),
         ("Libra", "♎"), ("Scorpio", "♏"), ("Sagittarius", "♐"), ("Capricorn", "♑"), ("Aquarius", "♒"),
         ("Pisces", "♓")]
ASPECTS = [(0, "conjunct", "☌"), (60, "sextile", "⚹"), (90, "square", "□"), (120, "trine", "△"),
           (180, "opposite", "☍")]
PHASES = ["New Moon", "First Quarter", "Full Moon", "Last Quarter"]
FIRST, LAST = dt.datetime(1900, 1, 2, tzinfo=dt.timezone.utc), dt.datetime(2050, 1, 1, tzinfo=dt.timezone.utc)


@functools.lru_cache(maxsize=1)
def sky():
    """(timescale, ephemeris), or None when Skyfield or the ephemeris file is missing."""
    try:
        from skyfield.api import load
    except ImportError:
        return None
    if not EPHEMERIS.exists():
        return None
    return load.timescale(builtin=True), load(str(EPHEMERIS))


def longitudes(t, key: str):
    """Apparent geocentric ecliptic longitude of date (the tropical zodiac), in degrees, at Skyfield time(s) t."""
    ts, eph = sky()
    lat, lon, _ = eph["earth"].at(t).observe(eph[key]).apparent().ecliptic_latlon(epoch="date")
    return lon.degrees


def zodiac(lon: float) -> str:
    """"♏ Scorpio 1°12′" for a longitude."""
    minutes = round(lon % 360 * 60) % (360 * 60)        # rounded first, so 29°59.7′ shows as the next 0°00′
    sign, d, m = minutes // 1800, minutes % 1800 // 60, minutes % 60
    name, glyph = SIGNS[sign]
    return f"{glyph} {name} {d}°{m:02d}′"


def positions(when: dt.datetime) -> list:
    """[(name, glyph, longitude, retrograde)] at a moment."""
    ts, _ = sky()
    t = ts.from_datetimes([when - dt.timedelta(hours=12), when, when + dt.timedelta(hours=12)])
    out = []
    for name, glyph, key in BODIES:
        before, now, after = longitudes(t, key)
        motion = (after - before + 540) % 360 - 180
        out.append((name, glyph, float(now), name not in ("Sun", "Moon") and motion < 0))
    return out


def _wrap(x):
    return (x + 180) % 360 - 180


def _bisect(f, a: dt.datetime, b: dt.datetime, fa: float) -> dt.datetime:
    """The moment between a and b where f changes sign (f(a) = fa)."""
    for _ in range(22):                                        # 1 hour / 2^22: well under a second
        mid = a + (b - a) / 2
        fm = f(mid)
        if (fm < 0) == (fa < 0):
            a, fa = mid, fm
        else:
            b = mid
    return a + (b - a) / 2


def events(day: dt.date) -> list:
    """[(moment, text)] of the UTC day's exact aspects (planets, not the Moon, which makes a dozen a day),
    ingresses, stations, and the Moon's quarters, in order."""
    ts, eph = sky()
    start = dt.datetime(day.year, day.month, day.day, tzinfo=dt.timezone.utc)
    grid = [start + dt.timedelta(hours=h) for h in range(25)]
    t = ts.from_datetimes(grid)
    lons = {name: [float(x) for x in longitudes(t, key)] for name, _, key in BODIES}
    glyph = {name: g for name, g, _ in BODIES}
    key = {name: k for name, _, k in BODIES}
    found = []

    def lon_at(name, moment):
        return float(longitudes(ts.from_datetime(moment), key[name]))

    # a planet (or the Sun or Moon) entering a sign
    for name, _, _ in BODIES:
        ls = lons[name]
        for h in range(24):
            s0, s1 = int(ls[h] % 360 // 30), int(ls[h + 1] % 360 // 30)
            if s0 != s1:
                boundary = (s1 if (s1 - s0) % 12 == 1 else s0) * 30
                f = lambda m, n=name, bd=boundary: _wrap(lon_at(n, m) - bd)
                moment = _bisect(f, grid[h], grid[h + 1], _wrap(ls[h] - boundary))
                sign, sglyph = SIGNS[s1]
                found.append((moment, f"{glyph[name]} {name} enters {sglyph} {sign}"
                                      + (" (retrograde)" if (s1 - s0) % 12 == 11 else "")))
    # stations: a planet's motion along the zodiac changing direction
    for name, _, _ in BODIES[2:]:
        ls = lons[name]
        speeds = [_wrap(ls[h + 1] - ls[h]) for h in range(24)]
        for h in range(23):
            if (speeds[h] < 0) != (speeds[h + 1] < 0):
                turning = "retrograde" if speeds[h + 1] < 0 else "direct"
                speed = lambda m, n=name: _wrap(lon_at(n, m + dt.timedelta(minutes=30))
                                                - lon_at(n, m - dt.timedelta(minutes=30)))
                moment = _bisect(speed, grid[h], grid[h + 2], speed(grid[h]))
                found.append((moment, f"{glyph[name]} {name} stations {turning} at {zodiac(lon_at(name, moment))}"))
    # exact aspects between the planets (the Sun included)
    names = [n for n, _, _ in BODIES if n != "Moon"]
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            sep = [abs(_wrap(lons[a][h] - lons[b][h])) for h in range(25)]
            for angle, word, sym in ASPECTS:
                for h in range(24):
                    d0, d1 = sep[h] - angle, sep[h + 1] - angle
                    if (d0 < 0) != (d1 < 0) and abs(d0) < 5 and abs(d1) < 5:
                        f = lambda m, a=a, b=b, ang=angle: abs(_wrap(lon_at(a, m) - lon_at(b, m))) - ang
                        moment = _bisect(f, grid[h], grid[h + 1], d0)
                        found.append((moment, f"{glyph[a]} {a} {sym} {word} {glyph[b]} {b}, in "
                                              f"{SIGNS[int(lon_at(a, moment) % 360 // 30)][1]} and "
                                              f"{SIGNS[int(lon_at(b, moment) % 360 // 30)][1]}"))
    # the Moon's quarters
    from skyfield import almanac
    times, phases = almanac.find_discrete(t[0], t[-1], almanac.moon_phases(eph))
    for tm, ph in zip(times, phases):
        moment = tm.utc_datetime()
        found.append((moment, f"☽ {PHASES[int(ph)]} in {zodiac(lon_at('Moon', moment))}"))
    return sorted((m, text) for m, text in found if start <= m < start + dt.timedelta(days=1))


def moon_phase(when: dt.datetime) -> str:
    """"Waxing gibbous, 78% lit"."""
    from skyfield import almanac
    ts, eph = sky()
    t = ts.from_datetime(when)
    angle = almanac.moon_phase(eph, t).degrees
    lit = 100 * eph["earth"].at(t).observe(eph["moon"]).apparent().fraction_illuminated(eph["sun"])
    name = ("New" if angle < 11.25 or angle >= 348.75 else "Waxing crescent" if angle < 78.75
            else "First quarter" if angle < 101.25 else "Waxing gibbous" if angle < 168.75
            else "Full" if angle < 191.25 else "Waning gibbous" if angle < 258.75
            else "Last quarter" if angle < 281.25 else "Waning crescent")
    return f"{name}, {lit:.0f}% lit"


def parse_when(arg: str, now: dt.datetime) -> "dt.datetime | str":
    """The moment asked for, or why it can't be read."""
    a = arg.strip().lower()
    if a in ("", "now", "today"):
        return now
    if a in ("tomorrow", "yesterday"):
        day = now.date() + dt.timedelta(days=1 if a == "tomorrow" else -1)
        return dt.datetime(day.year, day.month, day.day, 12, tzinfo=dt.timezone.utc)
    m = re.fullmatch(r"(\d{4})-(\d{1,2})-(\d{1,2})", a)
    if not m:
        return "Give a date as YYYY-MM-DD (like `!planets 2026-12-25`), or `tomorrow` or `yesterday`."
    try:
        day = dt.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    except ValueError:
        return "That isn't a date on the calendar."
    when = dt.datetime(day.year, day.month, day.day, 12, tzinfo=dt.timezone.utc)
    if not FIRST <= when < LAST:
        return "I can only work out the sky between 1900 and 2049."
    return when


def planets_embed(when: dt.datetime, now: bool) -> discord.Embed:
    lines = []
    for name, glyph, lon, retro in positions(when):
        lines.append(f"{glyph} **{name}** — {zodiac(lon)}" + (" ℞" if retro else ""))
    title = "🪐 The sky now" if now else f"🪐 The sky on {when.day} {when:%B %Y}"
    embed = discord.Embed(title=title, description="\n".join(lines), color=COLOR)
    embed.add_field(name="The Moon", value=moon_phase(when), inline=False)
    day = events(when.date())
    if day:
        text = "\n".join(f"`{m + dt.timedelta(seconds=30):%H:%M}` {e}" for m, e in day)   # (to the nearest minute)
        embed.add_field(name=f"{'Today' if now else 'That day'} (times UTC)", value=text[:1024], inline=False)
    else:
        embed.add_field(name=f"{'Today' if now else 'That day'}", value="No exact aspects, ingresses or stations.",
                        inline=False)
    stamp = f"{when:%H:%M} UTC" if now else "noon UTC"
    embed.set_footer(text=f"Tropical zodiac · ℞ retrograde · positions at {stamp}, from NASA JPL (DE421)")
    return embed


@bot.command(name="planets", aliases=["sky", "ephemeris", "astrology"])
async def cmd_planets(ctx, *, when: str = ""):
    """Where the Sun, Moon and planets are in the zodiac, and the day's aspects.
    Usage: !planets              — now, and today's events
           !planets 2026-12-25   — that day
           !planets tomorrow     — (or yesterday)"""
    if sky() is None:
        await ctx.send("⚠️ I can't work out the sky right now: my planetary tables aren't installed.")
        log.warning("!planets: Skyfield or data/de421.bsp is missing")
        return
    now = dt.datetime.now(dt.timezone.utc)
    moment = parse_when(when, now)
    if isinstance(moment, str):
        await ctx.send(moment)
        return
    import asyncio
    embed = await asyncio.to_thread(planets_embed, moment, moment is now)
    await ctx.send(embed=embed)
