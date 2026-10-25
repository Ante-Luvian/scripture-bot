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
                found.append({"at": moment, "signs": [int(where % 360 // 30)], "lilly": None,
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
                                      "text": f"{glyph[a]} {a} {sym} {word} {glyph[b]} {b}, in "
                                              f"{SIGNS[sa][1]} and {SIGNS[sb][1]}"})
    # the Moon's quarters
    from skyfield import almanac
    times, phases = almanac.find_discrete(t[0], t[-1], almanac.moon_phases(eph))
    for tm, ph in zip(times, phases):
        moment = tm.utc_datetime()
        where = lon_at("Moon", moment)
        found.append({"at": moment, "signs": [int(where % 360 // 30)], "lilly": None,
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


def horoscope_embed(day: dt.date, with_moon: bool = True) -> discord.Embed:
    """The UTC day's events, each with the signs it falls in and Lilly's reading on it; and the Moon, unless
    !planets has just shown it (the daily post)."""
    noon = dt.datetime(day.year, day.month, day.day, 12, tzinfo=dt.timezone.utc)
    embed = discord.Embed(title=f"🪐 The sky today — {day:%A}, {day.day} {day:%B %Y}", color=COLOR)
    found = day_events(day)
    for e in found[:20]:
        lines = [f"Felt most by those born under {_signs(e['signs'])}."]
        reading = lilly_on(e["lilly"])
        if reading:
            ref, text = reading
            quote = re.sub(r"^(\*[^*\n]+\*\n)+", "", text).replace("\n", " ")
            cite = f"\n— *{ref.replace(LILLY_APPENDIX, 'Appendix')}*"           # (the footer says whose)
            if len(lines[0]) + len(quote) + len(cite) + 10 <= 1024:        # (a quotation is never cut)
                lines.append(f"> {quote}{cite}")
        embed.add_field(name=f"`{e['at'] + dt.timedelta(seconds=30):%H:%M}` {e['text']}"[:256],
                        value="\n".join(lines), inline=False)
    if not found:
        embed.description = "A quiet day: no exact aspects, no planet changing sign or direction."
    if with_moon:
        moon = next(lon for name, _, lon, _ in positions(noon) if name == "Moon")
        embed.add_field(name="The Moon", value=f"In {zodiac(moon)}; {moon_phase(noon)[0].lower()}{moon_phase(noon)[1:]}",
                        inline=False)
    embed.set_footer(text="Times UTC · tropical zodiac · positions from NASA JPL · readings quoted from William "
                          "Lilly (1647, ed. Zadkiel): !verse Lilly appendix 3:118 · !planets for where everything is")
    return embed


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
    reading = await asyncio.to_thread(horoscope_embed, day, False)
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
    """The day's sky as a horoscope: each aspect, sign change and station, the signs it falls in, and
    what William Lilly wrote of it.
    Usage: !horoscope              — today
           !horoscope 2026-12-25   — that day"""
    if sky() is None:
        await ctx.send("⚠️ I can't work out the sky right now: my planetary tables aren't installed.")
        return
    moment = parse_when(when, dt.datetime.now(dt.timezone.utc))
    if isinstance(moment, str):
        await ctx.send(moment)
        return
    import asyncio
    await ctx.send(embed=await asyncio.to_thread(horoscope_embed, moment.date()))


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
