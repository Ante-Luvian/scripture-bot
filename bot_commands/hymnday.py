"""
!hymnday -- a hymn for each day, following the Church year -- and
!hymndaysetup, which posts it in a channel every day.

On a great feast it's that feast's hymn (Veni Creator at Pentecost, Vexilla
Regis on Good Friday); in Advent, Christmas, Lent, Passiontide, Easter and
Pentecost week, one of the season's hymns, in English, Latin chant or from the
Sacred Harp; the rest of the year it takes the three in turn. Everyone gets the
same hymn on the same (UTC) day.
"""
import datetime
import json
import random
import re

import discord
from discord.ext import commands, tasks

from core import command_enabled, pack_enabled, ROOT, _atomic_write_json, _load_guild_config, _update_guild_config, bot, log
from bot_commands.hymns import COLOR, chant_part, hymn_embed, hymn_view, hymns, shelf
from liturgical_calendar import western_season

HYMNDAY_PATH = ROOT / "data" / "hymnday.json"      # {"posted": {guild id: "YYYY-MM-DD"}}
DEFAULT_HYMNDAY_TIME = "08:00"

# the great feasts: the hymn of the day itself, in turn year by year
FEAST_HYMNS = {
    "christmas": ["Adeste fideles", "O Come, All Ye Faithful", "Hark! The Herald Angels Sing",
                  "Christe Redemptor omnium ex Patre"],
    "epiphany": ["As With Gladness Men of Old", "Hostis Herodes impie"],
    "ash_wednesday": ["Attende Domine", "Parce Domine"],
    "palm_sunday": ["Gloria laus", "All Glory, Laud, and Honor"],
    "maundy_thursday": ["Ubi caritas", "Pange lingua gloriosi corporis"],
    "good_friday": ["Vexilla Regis prodeunt", "O Sacred Head, Now Wounded", "Stabat Mater"],
    "holy_saturday": ["Were You There?"],
    "easter": ["Victimae Paschali laudes", "Christ The Lord Is Risen Today (Lyra)", "Easter Anthem"],
    "ascension": ["Crown Him With Many Crowns"],
    "pentecost": ["Veni Creator Spiritus", "Veni Sancte Spiritus et emitte"],
    "trinity": ["Holy, Holy, Holy", "O Trinity of Blessed Light"],
    "corpus_christi": ["Pange lingua gloriosi corporis", "Lauda Sion"],
    "annunciation": ["Ave maris stella"],
    "assumption": ["Ave maris stella"],
    "all_saints": ["For All The Saints"],
    "christ_the_king": ["Crown Him With Many Crowns", "Te Deum"],
}

# the seasons: a hymn a day from these
SEASON_HYMNS = {
    "advent": ["O Come O Come Emmanuel", "Come, Thou Long-Expected Jesus", "Lo! He Comes With Clouds Descending",
               "Let All Mortal Flesh Keep Silence", "Conditor alme siderum", "Creator alme siderum",
               "Veni, veni, Emmanuel", "Rorate caeli", "Alma Redemptoris", "Vox clara"],
    "christmas": ["O Come, All Ye Faithful", "Joy to the World", "Hark! The Herald Angels Sing", "Silent Night",
                  "Angels We Have Heard On High", "The First Noel", "What Child Is This?",
                  "O Little Town of Bethlehem", "It Came Upon A Midnight Clear", "Of The Father's Love Begotten",
                  "Adeste fideles", "A solis ortus cardine", "Christe Redemptor omnium ex Patre",
                  "Puer natus in Bethlehem", "Sherburne"],
    "epiphany": ["As With Gladness Men of Old", "O Chief of Cities Bethlehem", "Hostis Herodes impie",
                 "Crudelis Herodes Deum"],
    "lent": ["Audi benigne Conditor", "Attende Domine", "Parce Domine", "Ave Regina caelorum"],
    "passiontide": ["Vexilla Regis prodeunt", "Pange lingua gloriosi proelium", "Stabat Mater",
                    "O Sacred Head, Now Wounded", "When I Survey the Wondrous Cross", "Were You There?",
                    "Wondrous Cross"],
    "easter": ["Christ The Lord Is Risen Today (Lyra)", "Jesus Christ Is Risen Today",
               "The Strife Is O'er, The Battle Done", "Victimae Paschali laudes", "Ad coenam",
               "Aurora lucis rutilat", "Regina caeli", "O filii et filiae", "Easter Anthem",
               "The Resurrection Day"],
    "pentecost": ["Veni Creator Spiritus", "Veni Sancte Spiritus et emitte", "Breathe on Me, Breath of God",
                  "Heavenly Dove"],
}

FEAST_NAMES = {"christmas": "Christmas Day", "epiphany": "the Epiphany", "ash_wednesday": "Ash Wednesday",
               "palm_sunday": "Palm Sunday", "maundy_thursday": "Maundy Thursday", "good_friday": "Good Friday",
               "holy_saturday": "Holy Saturday", "easter": "Easter Day", "ascension": "Ascension Day",
               "pentecost": "Pentecost", "trinity": "Trinity Sunday", "corpus_christi": "Corpus Christi",
               "annunciation": "the Annunciation", "assumption": "the Assumption",
               "all_saints": "All Saints' Day", "christ_the_king": "Christ the King"}
SEASON_NAMES = {"advent": "Advent", "christmas": "Christmastide", "epiphany": "Epiphany", "lent": "Lent",
                "passiontide": "Passiontide", "easter": "Eastertide", "pentecost": "Pentecost week"}
ROTATION = ["hymns", "chant", "harp"]               # in Ordinary Time, a day each


def _by_title() -> dict:
    return {h["title"]: h for h in hymns()}


def hymn_for(day: datetime.date, latin: bool = True) -> tuple[dict, str]:
    """(the hymn, why: "For Pentecost", "In Advent", "") for a day; without the Latin chant if not `latin`
    (a server without the Catholic devotions gets the English hymns and the Sacred Harp)."""
    season, feast = western_season(day)
    titles = {t: h for t, h in _by_title().items() if latin or shelf(h) != "chant"}
    if feast:
        choices = [titles[t] for t in FEAST_HYMNS[feast] if t in titles]
        if choices:
            return choices[day.year % len(choices)], f"For {FEAST_NAMES[feast]}"
    rng = random.Random(day.toordinal())
    if season in SEASON_HYMNS:
        choices = [titles[t] for t in SEASON_HYMNS[season] if t in titles]
        if choices:
            # each in turn through the season, starting at a different one each year
            return choices[(day.toordinal() + day.year) % len(choices)], f"In {SEASON_NAMES[season]}"
    rotation = ROTATION if latin else [k for k in ROTATION if k != "chant"]
    kind = rotation[day.toordinal() % len(rotation)]
    pool = [h for h in hymns() if shelf(h) == kind and (kind != "chant" or chant_part(h) == "Hymn")]
    pool.sort(key=lambda h: h["title"])
    return rng.choice(pool), ""


def hymnday_message(day: datetime.date, guild_id=None) -> dict:
    """send() kwargs for the day's hymn: a heading, the hymn, its Play button."""
    hymn, why = hymn_for(day, latin=guild_id is None or pack_enabled(guild_id, "catholic_devotion"))
    heading = f"🎵 **Hymn of the day** · {day.strftime('%A')} {day.day} {day.strftime('%B')}" + (f" · {why}" if why else "")
    return {"content": heading, "embed": hymn_embed(hymn), "view": hymn_view(hymn)}


def _today() -> datetime.date:
    return datetime.datetime.now(datetime.timezone.utc).date()


@bot.command(name="hymnday", aliases=["hymnoftheday", "hotd"])
async def cmd_hymnday(ctx, *, when: str = ""):
    """Today's hymn, chosen for the Church year (the same for everyone today).
    Usage: !hymnday               — today's
           !hymnday 2026-12-25    — another day's"""
    day = _today()
    if when.strip():
        try:
            day = datetime.date.fromisoformat(when.strip())
        except ValueError:
            await ctx.send("Give a date like `!hymnday 2026-12-25`, or nothing for today's.")
            return
    await ctx.send(**hymnday_message(day, getattr(getattr(ctx, "guild", None), "id", None)))


# ── the daily post (!hymndaysetup) ──────────────────────────────────────────
# Per-server settings in guild_config.json: hymnday_channel_id, hymnday_time ("HH:MM" UTC).

def _load_state() -> dict:
    try:
        return json.loads(HYMNDAY_PATH.read_text(encoding="utf-8")) if HYMNDAY_PATH.exists() else {}
    except ValueError:
        return {}


async def post_hymnday(guild_id, channel, day: datetime.date, force: bool = False) -> bool:
    state = _load_state()
    if state.get("posted", {}).get(str(guild_id)) == day.isoformat() and not force:
        return False                                    # (a restart doesn't post it twice)
    await channel.send(**hymnday_message(day, guild_id))
    state.setdefault("posted", {})[str(guild_id)] = day.isoformat()
    _atomic_write_json(HYMNDAY_PATH, state)
    return True


async def run_daily_hymns(client, day: datetime.date, current_hm: str) -> int:
    posted = 0
    for guild_id, g in _load_guild_config().items():
        channel_id = g.get("hymnday_channel_id")
        if not channel_id or g.get("hymnday_time", DEFAULT_HYMNDAY_TIME) != current_hm:
            continue
        if not command_enabled(int(guild_id), "hymnday"):   # the server turned it off
            continue
        channel = client.get_channel(int(channel_id))
        if channel is None:
            continue
        try:
            posted += await post_hymnday(guild_id, channel, day)
        except Exception:
            log.exception(f"Failed to post the hymn of the day for guild {guild_id}")
    return posted


@tasks.loop(minutes=1)
async def daily_hymn_task():
    now = datetime.datetime.now(datetime.timezone.utc)
    await run_daily_hymns(bot, now.date(), f"{now.hour:02d}:{now.minute:02d}")


@daily_hymn_task.before_loop
async def _before_daily_hymn():
    await bot.wait_until_ready()


@bot.command(name="hymndaysetup", aliases=["hymndayconfig"])
@commands.has_permissions(administrator=True)
async def cmd_hymndaysetup(ctx, action: str = "", *, arg: str = ""):
    """Post the hymn of the day in a channel.
    Usage: !hymndaysetup                  — show this server's settings
           !hymndaysetup channel #chan    — post each day's hymn there
           !hymndaysetup time 08:00       — daily post time (24h UTC)
           !hymndaysetup test             — post today's now
           !hymndaysetup off              — stop the daily post"""
    if not ctx.guild:
        await ctx.send("This command only works in a server.")
        return
    g = _load_guild_config().get(str(ctx.guild.id), {})
    channel_id, time_hm = g.get("hymnday_channel_id"), g.get("hymnday_time", DEFAULT_HYMNDAY_TIME)
    action = action.strip().lower()
    if not action:
        embed = discord.Embed(title=f"🎵 Hymn of the day — {ctx.guild.name}", color=COLOR)
        embed.add_field(name="Channel", value=f"<#{channel_id}>" if channel_id else "*not set — no daily post*")
        embed.add_field(name="Time (UTC)", value=time_hm)
        embed.set_footer(text="!hymndaysetup channel #chan · time HH:MM · test · off")
        await ctx.send(embed=embed)
    elif action == "off":
        _update_guild_config(ctx.guild.id, hymnday_channel_id=None)
        await ctx.send("The daily hymn post is off for this server. (`!hymnday` still works.)")
    elif action == "channel":
        channel = ctx.message.channel_mentions[0] if ctx.message.channel_mentions else None
        if channel is None:
            await ctx.send("Mention a channel: `!hymndaysetup channel #hymns`")
            return
        _update_guild_config(ctx.guild.id, hymnday_channel_id=channel.id)
        m = re.search(r"\btime\s+(\d{1,2}):(\d{2})\b", arg)              # ("channel #chan time 04:00" in one go)
        if m and 0 <= int(m.group(1)) <= 23 and 0 <= int(m.group(2)) <= 59:
            time_hm = f"{int(m.group(1)):02d}:{m.group(2)}"
            _update_guild_config(ctx.guild.id, hymnday_time=time_hm)
        await ctx.send(f"The hymn of the day will be posted in {channel.mention} at {time_hm} UTC.")
    elif action == "time":
        m = re.match(r"^(\d{1,2}):(\d{2})$", arg.strip())
        if not m or not (0 <= int(m.group(1)) <= 23 and 0 <= int(m.group(2)) <= 59):
            await ctx.send("Use 24-hour UTC time: `!hymndaysetup time 08:00`")
            return
        hm = f"{int(m.group(1)):02d}:{int(m.group(2)):02d}"
        _update_guild_config(ctx.guild.id, hymnday_time=hm)
        await ctx.send(f"Daily hymn time set to **{hm} UTC**.")
    elif action == "test":
        channel = bot.get_channel(int(channel_id)) if channel_id else ctx.channel
        await post_hymnday(ctx.guild.id, channel, _today(), force=True)
    else:
        await ctx.send("Unknown option. Use `channel`, `time`, `test`, or `off`.")
