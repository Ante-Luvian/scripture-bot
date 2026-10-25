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
import json
import re

import discord

from discord.ext import commands, tasks

from core import ROOT, _atomic_write_json, _load_guild_config, _update_guild_config, bot, command_enabled, log, lookup

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
# Lilly groups the aspects as conjunctions, the "good" (✶ sextile, △ trine) and the "evil" (☐ square, ☍ opposition)
KIND = {0: "☌", 60: "✶△", 120: "✶△", 90: "☐☍", 180: "☐☍"}
LILLY_APPENDIX = "Lilly's Introduction to Astrology, Appendix"
# How noteworthy an event is (the voice message asked for "noteworthy astrological developments", not everything):
# 4 rare (the slow planets meeting, or changing sign), 3 a station, 2 worth a line, 1 or 0 routine. The Moon
# changes sign every two or three days: routine.
SLOW = {"Jupiter", "Saturn", "Uranus", "Neptune", "Pluto"}
INGRESS_WEIGHT = {"Moon": 0, "Sun": 2, "Mercury": 2, "Venus": 2, "Mars": 2, "Jupiter": 3, "Saturn": 3,
                  "Uranus": 4, "Neptune": 4, "Pluto": 4}


def aspect_weight(a: str, b: str, angle: int) -> int:
    base = 4 if a in SLOW and b in SLOW else 2
    return base + (1 if angle in (0, 180) and base < 4 else 0) - (1 if angle == 60 else 0)
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
    """[(moment, text)] of the UTC day's events, in order (day_events without the rest)."""
    return [(e["at"], e["text"]) for e in day_events(day)]


def day_events(day: dt.date) -> list:
    """The UTC day's exact aspects (planets, not the Moon, which makes a dozen a day), ingresses, stations,
    and the Moon's quarters, in order: [{"at", "text", "signs": the signs it falls in, "lilly": the key
    of Lilly's reading on it, or None}]."""
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
                found.append({"at": moment, "signs": [s1], "lilly": (glyph[name], "in", sglyph),
                              "weight": INGRESS_WEIGHT[name],
                              "text": f"{glyph[name]} {name} enters {sglyph} {sign}"
                                      + (" (retrograde)" if (s1 - s0) % 12 == 11 else "")})
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
                where = lon_at(name, moment)
                found.append({"at": moment, "signs": [int(where % 360 // 30)], "lilly": None, "weight": 3,
                              "text": f"{glyph[name]} {name} stations {turning} at {zodiac(where)}"})
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
                        sa, sb = int(lon_at(a, moment) % 360 // 30), int(lon_at(b, moment) % 360 // 30)
                        found.append({"at": moment, "signs": sorted({sa, sb}),
                                      "lilly": (glyph[a], KIND[angle], glyph[b]),
                                      "weight": aspect_weight(a, b, angle),
                                      "text": f"{glyph[a]} {a} {sym} {word} {glyph[b]} {b}, in "
                                              f"{SIGNS[sa][1]} and {SIGNS[sb][1]}"})
    # the Moon's quarters
    from skyfield import almanac
    times, phases = almanac.find_discrete(t[0], t[-1], almanac.moon_phases(eph))
    for tm, ph in zip(times, phases):
        moment = tm.utc_datetime()
        where = lon_at("Moon", moment)
        found.append({"at": moment, "signs": [int(where % 360 // 30)], "lilly": None,
                      "weight": 2 if int(ph) in (0, 2) else 1,
                      "text": f"☽ {PHASES[int(ph)]} in {zodiac(where)}"})
    return sorted((e for e in found if start <= e["at"] < start + dt.timedelta(days=1)), key=lambda e: e["at"])


@functools.lru_cache(maxsize=1)
def lilly_readings() -> dict:
    """Lilly's readings in his appendix (built by scripts/build_astrology.py), by what they're about:
    {("♂", "in", "♏"): [(reference, text)], ("♄", "☌", "♃"): [...], ("♀", "✶△", "♂"): [...], ...}.
    Appendix 3 is a planet in each sign; 4 the conjunctions; 5 the ✶ and △; 6 the ☐ and ☍."""
    corpus, book = lookup._resolve_exact(LILLY_APPENDIX)
    if not book:
        return {}
    heads = {"☌": "☌", "✶ *or* △": "✶△", "☐ *or* ☍": "☐☍"}
    out = {}
    for chapter in ("3", "4", "5", "6"):
        current = None
        for verse, text in lookup._data[corpus][book].get(chapter, {}).items():
            last = text.strip().split("\n")[-1].strip()
            m = (re.fullmatch(r"([☉☽☿♀♂♃♄]) \*in\* ([♈♉♊♋♌♍♎♏♐♑♒♓])", last)
                 or re.fullmatch(r"([☉☽☿♀♂♃♄]) (☌|✶ \*or\* △|☐ \*or\* ☍) ([☉☽☿♀♂♃♄])", last))
            if m and m.lastindex == 2:
                current = (m.group(1), "in", m.group(2))
            elif m:
                current = (m.group(1), heads[m.group(2)], m.group(3))
            elif current:
                out.setdefault(current, []).append((f"{book} {chapter}:{verse}", text.strip()))
    return out


def lilly_on(key) -> "tuple | None":
    """(reference, text) of Lilly's first reading on an event (an aspect either way round), if he has one."""
    if not key:
        return None
    readings = lilly_readings()
    found = readings.get(key) or (readings.get((key[2], key[1], key[0])) if key[1] != "in" else None)
    return found[0] if found else None


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


def planets_embed(when: dt.datetime, now: bool, with_events: bool = True) -> discord.Embed:
    """Where everything is; and, unless the day's horoscope follows it (the daily post), the day's events."""
    lines = []
    for name, glyph, lon, retro in positions(when):
        lines.append(f"{glyph} **{name}** — {zodiac(lon)}" + (" ℞" if retro else ""))
    title = "🪐 The sky now" if now else f"🪐 The sky on {when.day} {when:%B %Y}"
    embed = discord.Embed(title=title, description="\n".join(lines), color=COLOR)
    embed.add_field(name="The Moon", value=moon_phase(when), inline=False)
    if with_events:
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


@bot.command(name="planets", aliases=["sky", "ephemeris", "astrology", "astro"])
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


# ── the day's sky, as a horoscope: !horoscope, and the daily post (!astrosetup) ─────────────────
# A friend of the owner's, by voice message: "daily updates on various noteworthy astrological
# developments ... 'Venus is in conjunction with Mercury. Look out, Leos' ... a daily horoscope sort of
# thing." Each event says which signs it falls in, and where Lilly wrote on it, what he said (quoted and
# referenced, never made up). Settings per server in guild_config.json: astro_channel_id, astro_time
# ("HH:MM" UTC); what was posted in ASTRO_PATH.

ASTRO_PATH = ROOT / "data" / "astroday.json"       # {"posted": {guild id: "YYYY-MM-DD"}}
DEFAULT_ASTRO_TIME = "06:00"


def _signs(indexes: list) -> str:
    named = [f"{SIGNS[i][1]} {SIGNS[i][0]}" for i in indexes]
    return named[0] if len(named) == 1 else ", ".join(named[:-1]) + " and " + named[-1]


# Sepharial's forecasts for one planet passing over another ("Astrology", 1920, Section IV, Chapter II, "The
# Effects of Transits"), quoted whole: a sentence that leans on the one before ("Neptune thereover", "Mars over
# the same planet") is quoted with it. Each is checked against the book when first used.
SEPHARIAL_REF = "Sepharial's Astrology 4.2:2"
SEPHARIAL = {
    frozenset("♅♀"): "So Uranus in transit over the place of Venus will give a love affair, a romantic attachment.",
    frozenset("♂♀"): "Mars over the place of Venus will engender passionate love.",
    frozenset("♄♀"): "Saturn over Venus will give disappointment or bereavement; and Neptune thereover will bring "
                     "entanglements and complications, with danger of being led astray.",
    frozenset("♆♀"): "Saturn over Venus will give disappointment or bereavement; and Neptune thereover will bring "
                     "entanglements and complications, with danger of being led astray.",
    frozenset("♄☿"): "Saturn over Mercury will produce melancholy and many errors of judgment.",
    frozenset("♂☿"): "Saturn over Mercury will produce melancholy and many errors of judgment. Mars over the same "
                     "planet will excite the mind and dispose to impulse and unreasoning anger, quarrels and "
                     "disputation.",
    frozenset("♅☿"): "Uranus over Mercury will render the mind wayward and headstrong, disposed to erratic courses "
                     "and egotistic methods.",
    frozenset("♆☿"): "Neptune passing the place of Mercury produces deceits, treacheries, and apprehension of "
                     "impending evil, a sense of espionage and ambush.",
}


@functools.lru_cache(maxsize=1)
def _sepharial_text() -> str:
    corpus, book = lookup._resolve_exact("Sepharial's Astrology")
    if not book:
        return ""
    return re.sub(r"\s+", " ", lookup._data[corpus][book].get("4.2", {}).get("2", ""))


def _sign_index(word: str) -> "int | None":
    w = word.strip().lower().rstrip("s")
    for i, (name, glyph) in enumerate(SIGNS):
        if w in (name.lower(), name.lower().rstrip("s"), glyph):
            return i
    return None


MOST = 4                                                  # significant events a day, at most


def notable(day: dt.date) -> list:
    """The day's significant events (weight 2 and up), at most MOST of them, heaviest kept, in time order."""
    found = [e for e in day_events(day) if e["weight"] >= 2]
    kept = sorted(found, key=lambda e: (-e["weight"], e["at"]))[:MOST]
    return sorted(kept, key=lambda e: e["at"])


def _touches(signs: list) -> str:
    """The signs an event falls in, plainly ("♏ Scorpio, ♒ Aquarius"): with no note, no stock line in its place."""
    return ", ".join(f"{SIGNS[i][1]} {SIGNS[i][0]}" for i in signs)


def sepharial_on(e: dict) -> "str | None":
    """Sepharial's one-sentence forecast for one planet passing over another, if he made one for this event."""
    key = e.get("lilly")
    if key and key[1] == "☌":
        words = SEPHARIAL.get(frozenset((key[0], key[2])))
        if words and words in _sepharial_text():
            return words
    return None


def horoscope_embed(day: dt.date, notes: "dict | None" = None, sign: "int | None" = None) -> discord.Embed:
    """The day's significant events, each with a short note: Sepharial's words where he has some, else the
    day's written note (`notes`, by event text), else just the signs it touches. With `sign`, only those touching it."""
    whose = "" if sign is None else f" for {SIGNS[sign][1]} {SIGNS[sign][0]}"
    embed = discord.Embed(title=f"🪐 The sky today{whose} — {day:%A}, {day.day} {day:%B}", color=COLOR)
    found = [e for e in notable(day) if sign is None or sign in e["signs"]]
    for e in found:
        old = sepharial_on(e)
        if old:
            note = f"“{old}” — *Sepharial*"
        else:
            note = (notes or {}).get(e["text"]) or _touches(e["signs"])
        embed.add_field(name=f"`{e['at'] + dt.timedelta(seconds=30):%H:%M}` {e['text']}"[:256], value=note[:1024],
                        inline=False)
    if not found:
        embed.description = ("A quiet sky today: nothing significant." if sign is None
                             else f"Nothing significant touches {SIGNS[sign][0]} today.")
    written = notes and any(e["text"] in notes and not sepharial_on(e) for e in found)
    embed.set_footer(text="Times UTC · tropical zodiac · positions from NASA JPL"
                          + (" · notes written by AI (Claude) from the real sky" if written else ""))
    return embed


# ── the notes, written by AI from the day's real events ──────────────────────────────────────────────
# A short note on each significant event, what it means and for whom (the owner: never a stock "look out"
# line), from one request a day for every server, today only (other dates would be
# a cost anyone could run up), kept in HOROSCOPE_PATH. Needs ANTHROPIC_API_KEY in .env; without it, or if the
# request fails, each event just shows the signs it touches.

HOROSCOPE_PATH = ROOT / "data" / "horoscopes.json"      # {"YYYY-MM-DD": {event text: note}}
MODEL = "claude-haiku-5-5"                              # (one short request a day: pennies a month)
_writing = None                                          # (an asyncio.Lock, made on first use)

PROMPT = """You write the notes for a Discord bot's daily astrology post (tropical zodiac; the events below are \
computed from NASA's ephemeris, and are the day's significant ones).

Context, the planets at noon UTC:
{positions}

The events, in order:
{events}

For each event write one short note, two sentences at most, on what it means in traditional astrology and for \
whom: work the Sun signs it touches (given with the event) into the sentence naturally. Never use a stock opener \
or formula ("Look out", "Heads up", "Attention") and don't start every note the same way. Be specific to the \
planets and signs involved, a little wry, never saccharine; no emoji; no medical, legal or financial instructions; \
no certainties. Invent nothing beyond the events and positions given.

Reply with only a JSON list of the notes, one string per event, in the same order."""


def _ask_claude(prompt: str) -> str:
    import os
    import urllib.request
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        raise RuntimeError("no ANTHROPIC_API_KEY")
    # (thinking kept to a minimum: it spent a 2,500-token allowance thinking and wrote nothing)
    body = json.dumps({"model": MODEL, "max_tokens": 2000, "thinking": {"type": "between_tools"},
                       "messages": [{"role": "user", "content": prompt}]}).encode()
    req = urllib.request.Request("https://api.anthropic.com/v1/messages", data=body, method="POST", headers={
        "x-api-key": key, "anthropic-version": "2023-06-01", "content-type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as r:
        reply = json.loads(r.read().decode("utf-8"))
    return "".join(part.get("text", "") for part in reply.get("content", []))


def _notes_from(reply: str, found: list) -> "dict | None":
    m = re.search(r"\[.*\]", reply, re.S)
    try:
        data = json.loads(m.group(0)) if m else None
    except ValueError:
        return None
    if not isinstance(data, list) or len(data) != len(found):
        return None
    if not all(isinstance(n, str) and n.strip() and len(n) <= 400 for n in data):
        return None
    return {e["text"]: re.sub(r"\s+", " ", n).strip() for e, n in zip(found, data)}


def _brief(day: dt.date) -> dict:
    noon = dt.datetime(day.year, day.month, day.day, 12, tzinfo=dt.timezone.utc)
    return {"positions": "\n".join(f"- {name}: {zodiac(lon)}" + (" (retrograde)" if retro else "")
                                   for name, _, lon, retro in positions(noon)),
            "events": "\n".join(f"- {e['at']:%H:%M}: {e['text']} (signs: "
                                f"{', '.join(SIGNS[i][0] for i in e['signs'])})" for e in notable(day))}


def _load_horoscopes() -> dict:
    try:
        return json.loads(HOROSCOPE_PATH.read_text(encoding="utf-8")) if HOROSCOPE_PATH.exists() else {}
    except ValueError:
        return {}


async def day_notes(day: dt.date) -> "dict | None":
    """{event text: note} for today's significant events, written once and kept; None for another day, a quiet
    day, or when they can't be had."""
    global _writing
    import asyncio
    import os
    if day != dt.datetime.now(dt.timezone.utc).date():
        return None
    kept = _load_horoscopes().get(day.isoformat())
    if isinstance(kept, dict) and kept and all(isinstance(v, str) for v in kept.values()) \
            and not {name for name, _ in SIGNS} & set(kept):   # (not an old-style {sign: reading} day)
        return kept
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return None                                       # (no key set: the post goes without, quietly)
    if _writing is None:
        _writing = asyncio.Lock()
    async with _writing:                                  # (two servers at 06:00 make one request)
        found = await asyncio.to_thread(notable, day)
        if not found:
            return None
        try:
            prompt = PROMPT.format(**await asyncio.to_thread(_brief, day))
            notes = _notes_from(await asyncio.to_thread(_ask_claude, prompt), found)
        except Exception as e:
            log.warning(f"The day's horoscope notes couldn't be written: {e}")
            return None
        if not notes:
            log.warning("The day's horoscope notes came back in a form I can't use")
            return None
        state = {k: v for k, v in _load_horoscopes().items() if k >= (day - dt.timedelta(days=14)).isoformat()}
        state[day.isoformat()] = notes
        _atomic_write_json(HOROSCOPE_PATH, state)
        return notes


def _load_state() -> dict:
    try:
        return json.loads(ASTRO_PATH.read_text(encoding="utf-8")) if ASTRO_PATH.exists() else {}
    except ValueError:
        return {}


async def post_astroday(guild_id, channel, day: dt.date, force: bool = False) -> bool:
    state = _load_state()
    if state.get("posted", {}).get(str(guild_id)) == day.isoformat() and not force:
        return False                                            # (a restart doesn't post it twice)
    if sky() is None:
        return False
    import asyncio
    # !planets (where everything is, as the post goes out), then !horoscope (the day's events, read)
    now = dt.datetime.now(dt.timezone.utc)
    moment = now if now.date() == day else dt.datetime(day.year, day.month, day.day, 12, tzinfo=dt.timezone.utc)
    sky_now = await asyncio.to_thread(planets_embed, moment, moment is now, False)
    notes = await day_notes(day)
    reading = await asyncio.to_thread(horoscope_embed, day, notes)
    await channel.send(embed=sky_now)
    await channel.send(embed=reading)
    state.setdefault("posted", {})[str(guild_id)] = day.isoformat()
    _atomic_write_json(ASTRO_PATH, state)
    return True


async def run_daily_astro(client, day: dt.date, current_hm: str) -> int:
    posted = 0
    for guild_id, g in _load_guild_config().items():
        channel_id = g.get("astro_channel_id")
        if not channel_id or g.get("astro_time", DEFAULT_ASTRO_TIME) != current_hm:
            continue
        if not command_enabled(int(guild_id), "planets"):         # the server turned the pack off
            continue
        channel = client.get_channel(int(channel_id))
        if channel is None:
            continue
        try:
            posted += await post_astroday(guild_id, channel, day)
        except Exception:
            log.exception(f"Failed to post the day's sky for guild {guild_id}")
    return posted


@tasks.loop(minutes=1)
async def daily_astro_task():
    now = dt.datetime.now(dt.timezone.utc)
    await run_daily_astro(bot, now.date(), f"{now.hour:02d}:{now.minute:02d}")


@daily_astro_task.before_loop
async def _before_daily_astro():
    await bot.wait_until_ready()


@bot.command(name="horoscope", aliases=["horoscopes", "astroday"])
async def cmd_horoscope(ctx, *, when: str = ""):
    """The day's significant events in the sky, each with who should take note and a short note on it.
    Usage: !horoscope              — today
           !horoscope leo          — today, for Leo
           !horoscope 2026-12-25   — that day"""
    if sky() is None:
        await ctx.send("⚠️ I can't work out the sky right now: my planetary tables aren't installed.")
        return
    words = when.split()
    sign = _sign_index(words[0]) if words else None
    if sign is not None:
        when = " ".join(words[1:])
    moment = parse_when(when, dt.datetime.now(dt.timezone.utc))
    if isinstance(moment, str):
        await ctx.send(moment if sign is not None or not words else
                       moment + " Or give a sign: `!horoscope leo`.")
        return
    import asyncio
    notes = await day_notes(moment.date())
    await ctx.send(embed=await asyncio.to_thread(horoscope_embed, moment.date(), notes, sign))


@bot.command(name="astrosetup", aliases=["astroconfig", "horoscopesetup"])
@commands.has_permissions(administrator=True)
async def cmd_astrosetup(ctx, action: str = "", *, arg: str = ""):
    """Post the day's sky in a channel every day: !planets (where everything is), then !horoscope.
    Usage: !astrosetup                  — show this server's settings
           !astrosetup channel #chan    — post it there each day
           !astrosetup time 06:00       — daily post time (24h UTC)
           !astrosetup test             — post today's now
           !astrosetup off              — stop the daily post"""
    if not ctx.guild:
        await ctx.send("This command only works in a server.")
        return
    g = _load_guild_config().get(str(ctx.guild.id), {})
    channel_id, time_hm = g.get("astro_channel_id"), g.get("astro_time", DEFAULT_ASTRO_TIME)
    action = action.strip().lower()
    if not action:
        embed = discord.Embed(title=f"🪐 The day's sky — {ctx.guild.name}", color=COLOR)
        embed.add_field(name="Channel", value=f"<#{channel_id}>" if channel_id else "*not set — no daily post*")
        embed.add_field(name="Time (UTC)", value=time_hm)
        embed.set_footer(text="!astrosetup channel #chan · time HH:MM · test · off")
        await ctx.send(embed=embed)
    elif action == "off":
        _update_guild_config(ctx.guild.id, astro_channel_id=None)
        await ctx.send("The daily sky post is off for this server. (`!horoscope` and `!planets` still work.)")
    elif action == "channel":
        channel = ctx.message.channel_mentions[0] if ctx.message.channel_mentions else None
        if channel is None:
            await ctx.send("Mention a channel: `!astrosetup channel #astrology`")
            return
        _update_guild_config(ctx.guild.id, astro_channel_id=channel.id)
        m = re.search(r"\btime\s+(\d{1,2}):(\d{2})\b", arg)              # ("channel #chan time 04:00" in one go)
        if m and 0 <= int(m.group(1)) <= 23 and 0 <= int(m.group(2)) <= 59:
            time_hm = f"{int(m.group(1)):02d}:{m.group(2)}"
            _update_guild_config(ctx.guild.id, astro_time=time_hm)
        await ctx.send(f"The day's sky will be posted in {channel.mention} at {time_hm} UTC.")
    elif action == "time":
        m = re.match(r"^(\d{1,2}):(\d{2})$", arg.strip())
        if not m or not (0 <= int(m.group(1)) <= 23 and 0 <= int(m.group(2)) <= 59):
            await ctx.send("Use 24-hour UTC time: `!astrosetup time 06:00`")
            return
        hm = f"{int(m.group(1)):02d}:{int(m.group(2)):02d}"
        _update_guild_config(ctx.guild.id, astro_time=hm)
        await ctx.send(f"Daily sky time set to **{hm} UTC**.")
    elif action == "test":
        channel = bot.get_channel(int(channel_id)) if channel_id else ctx.channel
        if not await post_astroday(ctx.guild.id, channel, dt.datetime.now(dt.timezone.utc).date(), force=True):
            await ctx.send("⚠️ I can't work out the sky right now: my planetary tables aren't installed.")
    else:
        await ctx.send("Unknown option. Use `channel`, `time`, `test`, or `off`.")
