"""
The Jewish learning calendar, from Sefaria: !parsha (this week's Torah portion, with what
it's about and its readings), !dafyomi (today's page of the Talmud, which Jews around the
world study together, a page a day), !learning (all of the day's learning cycles), and
!learningsetup, which posts the day's learning in a channel every morning.

API: https://www.sefaria.org/api/calendars?year=Y&month=M&day=D&diaspora=1
"""
import asyncio
import datetime
import json
import re
import urllib.request

import discord
from discord.ext import commands, tasks

from core import (command_enabled, ROOT, _atomic_write_json, _load_guild_config, _send_result, _update_guild_config, bot, log,
                  lookup)

LEARNING_PATH = ROOT / "data" / "learning.json"     # {"posted": {guild id: "YYYY-MM-DD"}}
CALENDAR = "https://www.sefaria.org/api/calendars?year={y}&month={m}&day={d}&diaspora=1"
DEFAULT_TIME = "06:00"
COLOR = discord.Color.from_rgb(40, 80, 160)

_CACHE: dict = {}

# what each cycle is, for people who don't know the names
EXPLAINED = {
    "Parashat Hashavua": "Parashat Hashavua: this week's Torah portion",
    "Haftarah": "Haftarah: read from the Prophets with it",
    "Daf Yomi": "Daf Yomi: a page of the Talmud a day",
    "929": "929: a chapter of the Bible a day",
    "Daily Mishnah": "Daily Mishnah",
    "Daily Rambam": "Daily Rambam: Maimonides' code of law, a chapter a day",
    "Daily Rambam (3 Chapters)": "Daily Rambam: three chapters a day",
    "Daf a Week": "Daf a Week: a page of the Talmud a week",
    "Halakhah Yomit": "Halakhah Yomit: Jewish law (the Shulchan Arukh)",
    "Tanakh Yomi": "Tanakh Yomi: the Hebrew Bible in a year",
    "Tanya Yomi": "Tanya Yomi: the Hasidic classic, a passage a day",
    "Yerushalmi Yomi": "Yerushalmi Yomi: the Jerusalem Talmud",
}
NO_ENGLISH = {"Arukh HaShulchan Yomi", "Chok LeYisrael"}   # (Sefaria has these only in Hebrew)


def _today() -> datetime.date:
    return datetime.datetime.now(datetime.timezone.utc).date()


def parse_day(text: str) -> "datetime.date | None":
    """'' -> today; '2026-12-25' or '12-25' -> that day; None if it isn't a date."""
    text = text.strip()
    if not text:
        return _today()
    try:
        if re.fullmatch(r"\d{4}-\d{1,2}-\d{1,2}", text):
            return datetime.date(*map(int, text.split("-")))
        if re.fullmatch(r"\d{1,2}-\d{1,2}", text):
            return datetime.date(_today().year, *map(int, text.split("-")))
    except ValueError:
        return None
    return None


def calendar(day: datetime.date) -> "list | None":
    """The day's calendar items from Sefaria (cached); None if Sefaria can't be reached."""
    if day in _CACHE:
        return _CACHE[day]
    try:
        req = urllib.request.Request(CALENDAR.format(y=day.year, m=day.month, d=day.day),
                                     headers={"User-Agent": "ScriptureBot/1.0"})
        with urllib.request.urlopen(req, timeout=15) as r:
            items = json.loads(r.read().decode("utf-8")).get("calendar_items") or []
    except Exception:
        return None
    if len(_CACHE) > 60:
        _CACHE.clear()
    _CACHE[day] = items
    return items


def _item(items: list, title: str) -> "dict | None":
    return next((i for i in items if i.get("title", {}).get("en") == title), None)


def _en(value) -> str:
    return (value or {}).get("en", "") if isinstance(value, dict) else (value or "")


def readable_ref(item: dict) -> "str | None":
    """What to give !verse for a calendar item ("Bekhorot 30" is a daf: its first side, 30a)."""
    ref = item.get("ref")
    if not ref:
        return None
    if _en(item.get("title")) in ("Daf Yomi", "Daf a Week") and re.search(r"\s\d+$", ref):
        return f"{ref}a"
    return ref


def _when(day: datetime.date) -> str:
    return f"{day:%A} {day.day} {day:%B %Y}"


def learning_embed(items: list, day: datetime.date) -> discord.Embed:
    embed = discord.Embed(title=f"✡️ Jewish learning — {_when(day)}", color=COLOR, description=(
        "The texts Jews around the world are studying today, each in a daily cycle. Read any of them with "
        "the command shown."))
    for item in items:
        ref = readable_ref(item)
        if not ref or _en(item.get("title")) in NO_ENGLISH:
            continue
        name, shown = _en(item.get("title")), _en(item.get("displayValue"))
        name = EXPLAINED.get(name, name)
        value = shown
        about = _en(item.get("description"))
        if about:
            value += "\n" + (about if len(about) <= 300 else about[:300].rsplit(" ", 1)[0] + "…")
        value += f"\n`!verse {ref}`"
        embed.add_field(name=name, value=value[:1024], inline=False)
        if len(embed.fields) == 25:
            break
    embed.set_footer(text="From Sefaria's learning calendar · !parsha · !dafyomi")
    return embed


def parsha_embed(items: list) -> "discord.Embed | None":
    parsha = _item(items, "Parashat Hashavua")
    if parsha is None:
        return None
    embed = discord.Embed(title=f"📜 Parashat {_en(parsha.get('displayValue'))}", color=COLOR,
                          description=_en(parsha.get("description"))[:3000] or None)
    torah = parsha.get("ref")
    if torah:
        embed.add_field(name="The Torah reading", value=f"{torah}\n`!verse {torah}`", inline=False)
    aliyot = (parsha.get("extraDetails") or {}).get("aliyot") or []
    if aliyot:
        lines = [f"{'Maftir' if n == 8 else n}. {ref} — `!verse {ref}`" for n, ref in enumerate(aliyot, 1)]
        embed.add_field(name="In its seven readings (aliyot)", value="\n".join(lines)[:1024], inline=False)
    haftarah = _item(items, "Haftarah")
    if haftarah and haftarah.get("ref"):
        embed.add_field(name="The Haftarah (from the Prophets)",
                        value=f"{haftarah['ref']}\n`!verse {haftarah['ref']}`", inline=False)
    embed.set_footer(text="The portion read in synagogue this Shabbat · from Sefaria")
    return embed


async def send_parsha(ctx, when: str = "") -> None:
    day = parse_day(when)
    if day is None:
        await ctx.send("Give a date like `!parsha 2026-12-25` or `!parsha 12-25`, or nothing for this week's.")
        return
    items = (await asyncio.to_thread(calendar, day))
    embed = parsha_embed(items) if items else None
    if embed is None:
        await ctx.send("⚠️ I couldn't reach Sefaria's calendar just now.")
        return
    await ctx.send(embed=embed)


async def send_daf(ctx, when: str = "") -> None:
    day = parse_day(when)
    if day is None:
        await ctx.send("Give a date like `!dafyomi 2026-12-25` or `!dafyomi 12-25`, or nothing for today's.")
        return
    items = (await asyncio.to_thread(calendar, day))
    daf = _item(items or [], "Daf Yomi")
    if daf is None:
        await ctx.send("⚠️ I couldn't reach Sefaria's calendar just now.")
        return
    ref = readable_ref(daf)
    await ctx.send(f"✡️ **Daf Yomi for {_when(day)}: {_en(daf.get('displayValue'))}.** Each day Jews around the "
                   f"world study the same page of the Talmud, finishing it all in about seven and a half years. "
                   f"Here is its first side; the second is `!verse {ref[:-1]}b`.")
    await _send_result(ctx, (await asyncio.to_thread(lookup.get_verse, ref)))


@bot.command(name="parsha", aliases=["parasha", "parashah", "torahportion", "sidra"])
async def cmd_parsha(ctx, *, when: str = ""):
    """This week's Torah portion: what it's about, and its readings.
    Usage: !parsha               — this week's
           !parsha 2026-12-25    — the week of that day"""
    await send_parsha(ctx, when)


@bot.tree.command(name="parsha", description="This week's Torah portion, what it's about and its readings")
@discord.app_commands.describe(date="Optional: YYYY-MM-DD or MM-DD; blank for this week")
async def parsha_slash(interaction: discord.Interaction, date: str = ""):
    await interaction.response.defer()
    await send_parsha(await bot.get_context(interaction), date)


@bot.command(name="dafyomi", aliases=["daf", "dafyomit"])
async def cmd_dafyomi(ctx, *, when: str = ""):
    """Today's page of the Talmud in the Daf Yomi cycle, with its text.
    Usage: !dafyomi              — today's
           !dafyomi 2026-12-25   — another day's"""
    await send_daf(ctx, when)


@bot.tree.command(name="dafyomi", description="Today's page of the Talmud (Daf Yomi), with its text")
@discord.app_commands.describe(date="Optional: YYYY-MM-DD or MM-DD; blank for today")
async def dafyomi_slash(interaction: discord.Interaction, date: str = ""):
    await interaction.response.defer()
    await send_daf(await bot.get_context(interaction), date)


async def send_learning(ctx, when: str = "") -> None:
    day = parse_day(when)
    if day is None:
        await ctx.send("Give a date like `!learning 2026-12-25` or `!learning 12-25`, or nothing for today's.")
        return
    items = (await asyncio.to_thread(calendar, day))
    if not items:
        await ctx.send("⚠️ I couldn't reach Sefaria's calendar just now.")
        return
    await ctx.send(embed=learning_embed(items, day))


@bot.command(name="learning", aliases=["jewishlearning", "limmud", "dailylearning"])
async def cmd_learning(ctx, *, when: str = ""):
    """The day's Jewish learning: the Torah portion, Daf Yomi, daily Mishnah, Maimonides and more.
    Usage: !learning             — today's
           !learning 2026-12-25  — another day's"""
    await send_learning(ctx, when)


@bot.tree.command(name="learning", description="Today's Jewish learning: Torah portion, Daf Yomi, Mishnah, Rambam…")
@discord.app_commands.describe(date="Optional: YYYY-MM-DD or MM-DD; blank for today")
async def learning_slash(interaction: discord.Interaction, date: str = ""):
    await interaction.response.defer()
    await send_learning(await bot.get_context(interaction), date)


# ── the daily post (!learningsetup) ─────────────────────────────────────────
# Per-server settings in guild_config.json: learning_channel_id, learning_time ("HH:MM" UTC).

def _load_state() -> dict:
    try:
        return json.loads(LEARNING_PATH.read_text(encoding="utf-8")) if LEARNING_PATH.exists() else {}
    except ValueError:
        return {}


async def post_learning(guild_id, channel, day: datetime.date, force: bool = False) -> bool:
    state = _load_state()
    if state.get("posted", {}).get(str(guild_id)) == day.isoformat() and not force:
        return False                                     # (a restart doesn't post it twice)
    items = (await asyncio.to_thread(calendar, day))
    if not items:
        return False
    await channel.send(embed=learning_embed(items, day))
    state.setdefault("posted", {})[str(guild_id)] = day.isoformat()
    _atomic_write_json(LEARNING_PATH, state)
    return True


async def run_daily_learning(client, day: datetime.date, current_hm: str) -> int:
    posted = 0
    for guild_id, g in _load_guild_config().items():
        channel_id = g.get("learning_channel_id")
        if not channel_id or g.get("learning_time", DEFAULT_TIME) != current_hm:
            continue
        if not command_enabled(int(guild_id), "learning"):   # the server turned it off
            continue
        channel = client.get_channel(int(channel_id))
        if channel is None:
            continue
        try:
            posted += await post_learning(guild_id, channel, day)
        except Exception:
            log.exception(f"Failed to post the day's learning for guild {guild_id}")
    return posted


@tasks.loop(minutes=1)
async def daily_learning_task():
    now = datetime.datetime.now(datetime.timezone.utc)
    await run_daily_learning(bot, now.date(), f"{now.hour:02d}:{now.minute:02d}")


@daily_learning_task.before_loop
async def _before_daily_learning():
    await bot.wait_until_ready()


@bot.command(name="learningsetup", aliases=["learningconfig"])
@commands.has_permissions(administrator=True)
async def cmd_learningsetup(ctx, action: str = "", *, arg: str = ""):
    """Post the day's Jewish learning in a channel.
    Usage: !learningsetup                  — show this server's settings
           !learningsetup channel #chan    — post each day's there
           !learningsetup time 06:00       — daily post time (24h UTC)
           !learningsetup test             — post today's now
           !learningsetup off              — stop the daily post"""
    if not ctx.guild:
        await ctx.send("This command only works in a server.")
        return
    g = _load_guild_config().get(str(ctx.guild.id), {})
    channel_id, time_hm = g.get("learning_channel_id"), g.get("learning_time", DEFAULT_TIME)
    action = action.strip().lower()
    if not action:
        embed = discord.Embed(title=f"✡️ Jewish learning of the day — {ctx.guild.name}", color=COLOR)
        embed.add_field(name="Channel", value=f"<#{channel_id}>" if channel_id else "*not set — no daily post*")
        embed.add_field(name="Time (UTC)", value=time_hm)
        embed.set_footer(text="!learningsetup channel #chan · time HH:MM · test · off")
        await ctx.send(embed=embed)
    elif action == "off":
        _update_guild_config(ctx.guild.id, learning_channel_id=None)
        await ctx.send("The daily learning post is off for this server. (`!learning` still works.)")
    elif action == "channel":
        channel = ctx.message.channel_mentions[0] if ctx.message.channel_mentions else None
        if channel is None:
            await ctx.send("Mention a channel: `!learningsetup channel #torah`")
            return
        _update_guild_config(ctx.guild.id, learning_channel_id=channel.id)
        m = re.search(r"\btime\s+(\d{1,2}):(\d{2})\b", arg)
        if m and 0 <= int(m.group(1)) <= 23 and 0 <= int(m.group(2)) <= 59:
            time_hm = f"{int(m.group(1)):02d}:{m.group(2)}"
            _update_guild_config(ctx.guild.id, learning_time=time_hm)
        await ctx.send(f"The day's learning will be posted in {channel.mention} at {time_hm} UTC.")
    elif action == "time":
        m = re.match(r"^(\d{1,2}):(\d{2})$", arg.strip())
        if not m or not (0 <= int(m.group(1)) <= 23 and 0 <= int(m.group(2)) <= 59):
            await ctx.send("Use 24-hour UTC time: `!learningsetup time 06:00`")
            return
        hm = f"{int(m.group(1)):02d}:{int(m.group(2)):02d}"
        _update_guild_config(ctx.guild.id, learning_time=hm)
        await ctx.send(f"Daily learning time set to **{hm} UTC**.")
    elif action == "test":
        channel = bot.get_channel(int(channel_id)) if channel_id else ctx.channel
        if not await post_learning(ctx.guild.id, channel, _today(), force=True):
            await ctx.send("⚠️ I couldn't reach Sefaria's calendar just now.")
    else:
        await ctx.send("Unknown option. Use `channel`, `time`, `test`, or `off`.")
