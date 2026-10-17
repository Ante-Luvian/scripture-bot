"""
!troparion -- the day's troparia and kontakia: the short hymns the Orthodox Church sings
for each day's saints and feasts, with their tones, from the Orthodox Church in America
(oca.org/saints/troparia/YYYY/MM/DD), fetched as !today fetches the calendar. And
!troparionsetup, which posts them in a channel every day (like !hymndaysetup).
"""
import asyncio
import datetime
import html
import json
import re
import urllib.request

import discord
from discord.ext import commands, tasks

from core import ROOT, _atomic_write_json, _load_guild_config, _update_guild_config, bot, log

TROPARION_PATH = ROOT / "data" / "troparion.json"   # {"posted": {guild id: "YYYY-MM-DD"}}
DEFAULT_TIME = "06:00"
COLOR = discord.Color.from_rgb(170, 120, 30)
URL = "https://www.oca.org/saints/troparia/{y}/{m:02d}/{d:02d}"
# the site turns away requests without a browser's usual headers (403)
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) ScriptureBot", "Accept": "text/html,application/xhtml+xml",
      "Accept-Language": "en"}


def _text(fragment: str) -> str:
    fragment = re.sub(r"<br\s*/?>", "\n", fragment)
    text = html.unescape(re.sub(r"<[^>]+>", "", fragment)).strip()
    return re.sub(r"\s*/\s*", "\n", re.sub(r"[ \t]+", " ", text))     # "/" marks where a sung phrase ends


def parse(page: str) -> list:
    """[{"name", "hymns": [{"kind": "Troparion", "tone": "2", "text"}]}] from an OCA troparia page."""
    out = []
    for block in re.split(r"<header>\s*<h2>", page)[1:]:
        name = _text(block.split("</h2>", 1)[0])
        hymns = []
        for m in re.finditer(r"(?s)<h3>(.*?)</h3>\s*<p>(.*?)</p>", block):
            head = _text(m.group(1))
            kind, _, tone = head.partition("—")
            tone = re.sub(r"(?i)^\s*tone\s*", "", tone).strip()
            hymns.append({"kind": kind.strip(), "tone": tone, "text": _text(m.group(2))})
        if name and hymns:
            out.append({"name": name, "hymns": hymns})
    return out


_CACHE: dict = {}                                        # day -> commemorations (successes only)


def commemorations(day: datetime.date) -> "list | None":
    """The day's commemorations with their hymns; None if the OCA can't be reached."""
    if day in _CACHE:
        return _CACHE[day]
    try:
        req = urllib.request.Request(URL.format(y=day.year, m=day.month, d=day.day), headers=UA)
        page = urllib.request.urlopen(req, timeout=20).read().decode("utf-8", "replace")
    except Exception as e:
        log.warning(f"troparia for {day}: {e}")
        return None
    if len(_CACHE) > 60:
        _CACHE.clear()
    _CACHE[day] = parse(page)
    return _CACHE[day]


def messages(day: datetime.date, items: list) -> list:
    """send() kwargs, as few messages as Discord's limits allow (10 embeds, 6000 characters each)."""
    heading = f"☦️ **Troparia and kontakia** · {day.strftime('%A')} {day.day} {day.strftime('%B')}"
    embeds = []
    for c in items:
        embed = discord.Embed(title=c["name"][:256], color=COLOR)
        for h in c["hymns"][:6]:
            embed.add_field(name=f"{h['kind']} · Tone {h['tone']}" if h["tone"] else h["kind"],
                            value=h["text"][:1024], inline=False)
        embeds.append(embed)
    if embeds:
        embeds[-1].set_footer(text="From the Orthodox Church in America (oca.org) · a line break is a sung phrase")
    out, batch, size = [], [], 0
    for e in embeds:
        n = len(e)
        if batch and (len(batch) == 10 or size + n > 5800):
            out.append({"embeds": batch})
            batch, size = [], 0
        batch.append(e)
        size += n
    if batch:
        out.append({"embeds": batch})
    if out:
        out[0]["content"] = heading
    return out


def _today() -> datetime.date:
    return datetime.datetime.now(datetime.timezone.utc).date()


def _parse_day(text: str) -> "datetime.date | None":
    text = text.strip()
    if not text:
        return _today()
    try:
        return datetime.date.fromisoformat(text)
    except ValueError:
        pass
    m = re.fullmatch(r"(\d{1,2})[-/](\d{1,2})", text)
    if m:
        try:
            return datetime.date(_today().year, int(m.group(1)), int(m.group(2)))
        except ValueError:
            return None
    return None


async def send_troparia(target, day: datetime.date) -> bool:
    items = await asyncio.to_thread(commemorations, day)
    if items is None:
        await target.send("⚠️ I couldn't reach the Orthodox Church in America's site for the troparia. Try again "
                          "in a little while.")
        return False
    if not items:
        await target.send(f"I found no troparia for {day.day} {day.strftime('%B')}.")
        return False
    for message in messages(day, items):
        await target.send(**message)
    return True


@bot.command(name="troparion", aliases=["troparia", "kontakion"])
async def cmd_troparion(ctx, *, when: str = ""):
    """The Orthodox hymns of the day: the troparion and kontakion of each saint and feast.
    Usage: !troparion              — today's
           !troparion 2026-12-25   — another day's (or 12-25)"""
    day = _parse_day(when)
    if day is None:
        await ctx.send("Give a date like `!troparion 2026-12-25` or `!troparion 12-25`, or nothing for today's.")
        return
    async with ctx.typing():
        await send_troparia(ctx, day)


@bot.tree.command(name="troparion", description="The Orthodox troparia and kontakia of the day")
@discord.app_commands.describe(date="YYYY-MM-DD or MM-DD; empty for today")
async def troparion_slash(interaction: discord.Interaction, date: str = ""):
    await interaction.response.defer()
    ctx = await bot.get_context(interaction)
    await cmd_troparion(ctx, when=date)


# ── the daily post (!troparionsetup) ────────────────────────────────────────
# Per-server settings in guild_config.json: troparion_channel_id, troparion_time ("HH:MM" UTC).

def _load_state() -> dict:
    try:
        return json.loads(TROPARION_PATH.read_text(encoding="utf-8")) if TROPARION_PATH.exists() else {}
    except ValueError:
        return {}


async def post_troparia(guild_id, channel, day: datetime.date, force: bool = False) -> bool:
    state = _load_state()
    if state.get("posted", {}).get(str(guild_id)) == day.isoformat() and not force:
        return False                                     # (a restart doesn't post it twice)
    if not await send_troparia(channel, day):
        return False
    state.setdefault("posted", {})[str(guild_id)] = day.isoformat()
    _atomic_write_json(TROPARION_PATH, state)
    return True


async def run_daily_troparia(client, day: datetime.date, current_hm: str) -> int:
    posted = 0
    for guild_id, g in _load_guild_config().items():
        channel_id = g.get("troparion_channel_id")
        if not channel_id or g.get("troparion_time", DEFAULT_TIME) != current_hm:
            continue
        channel = client.get_channel(int(channel_id))
        if channel is None:
            continue
        try:
            posted += await post_troparia(guild_id, channel, day)
        except Exception:
            log.exception(f"Failed to post the troparia for guild {guild_id}")
    return posted


@tasks.loop(minutes=1)
async def daily_troparion_task():
    now = datetime.datetime.now(datetime.timezone.utc)
    await run_daily_troparia(bot, now.date(), f"{now.hour:02d}:{now.minute:02d}")


@daily_troparion_task.before_loop
async def _before_daily_troparion():
    await bot.wait_until_ready()


@bot.command(name="troparionsetup", aliases=["troparionconfig"])
@commands.has_permissions(administrator=True)
async def cmd_troparionsetup(ctx, action: str = "", *, arg: str = ""):
    """Post the day's troparia in a channel.
    Usage: !troparionsetup                  — show this server's settings
           !troparionsetup channel #chan    — post each day's there
           !troparionsetup time 06:00       — daily post time (24h UTC)
           !troparionsetup test             — post today's now
           !troparionsetup off              — stop the daily post"""
    if not ctx.guild:
        await ctx.send("This command only works in a server.")
        return
    g = _load_guild_config().get(str(ctx.guild.id), {})
    channel_id, time_hm = g.get("troparion_channel_id"), g.get("troparion_time", DEFAULT_TIME)
    action = action.strip().lower()
    if not action:
        embed = discord.Embed(title=f"☦️ Troparia of the day — {ctx.guild.name}", color=COLOR)
        embed.add_field(name="Channel", value=f"<#{channel_id}>" if channel_id else "*not set — no daily post*")
        embed.add_field(name="Time (UTC)", value=time_hm)
        embed.set_footer(text="!troparionsetup channel #chan · time HH:MM · test · off")
        await ctx.send(embed=embed)
    elif action == "off":
        _update_guild_config(ctx.guild.id, troparion_channel_id=None)
        await ctx.send("The daily troparia are off for this server. (`!troparion` still works.)")
    elif action == "channel":
        channel = ctx.message.channel_mentions[0] if ctx.message.channel_mentions else None
        if channel is None:
            await ctx.send("Mention a channel: `!troparionsetup channel #orthodox`")
            return
        _update_guild_config(ctx.guild.id, troparion_channel_id=channel.id)
        m = re.search(r"\btime\s+(\d{1,2}):(\d{2})\b", arg)
        if m and 0 <= int(m.group(1)) <= 23 and 0 <= int(m.group(2)) <= 59:
            time_hm = f"{int(m.group(1)):02d}:{m.group(2)}"
            _update_guild_config(ctx.guild.id, troparion_time=time_hm)
        await ctx.send(f"The day's troparia will be posted in {channel.mention} at {time_hm} UTC.")
    elif action == "time":
        m = re.match(r"^(\d{1,2}):(\d{2})$", arg.strip())
        if not m or not (0 <= int(m.group(1)) <= 23 and 0 <= int(m.group(2)) <= 59):
            await ctx.send("Use 24-hour UTC time: `!troparionsetup time 06:00`")
            return
        hm = f"{int(m.group(1)):02d}:{int(m.group(2)):02d}"
        _update_guild_config(ctx.guild.id, troparion_time=hm)
        await ctx.send(f"Daily troparia time set to **{hm} UTC**.")
    elif action == "test":
        channel = bot.get_channel(int(channel_id)) if channel_id else ctx.channel
        await post_troparia(ctx.guild.id, channel, _today(), force=True)
    else:
        await ctx.send("Unknown option. Use `channel`, `time`, `test`, or `off`.")
