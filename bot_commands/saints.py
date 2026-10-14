"""
!saint -- the saint of the day, or any saint by name, from Butler's Lives of the
Saints (the 1894 abridgement) and the Golden Legend (data/saints/saints.json,
built by scripts/build_saints.py); !saintsetup posts the day's saint in a channel.

    !saint                 today's saint (more than one? a menu for the others)
    !saint Christopher     by name; several of that name ("Augustine")? a menu to pick
    !saint 25 July         that day's

Butler's life comes first, with a 📖 Golden Legend button when the Legend has
the saint too; a saint only the Legend has (Christopher) opens straight to it.
"""
import datetime
import functools
import json
import re
import unicodedata
import zlib

import discord
from discord.ext import commands, tasks

from core import ROOT, _atomic_write_json, _load_guild_config, _update_guild_config, bot, log

SAINTS_PATH = ROOT / "data" / "saints" / "saints.json"
GOLDEN_LEGEND_PATH = ROOT / "data" / "medieval" / "golden_legend.json"
SAINTDAY_PATH = ROOT / "data" / "saintday.json"     # {"posted": {guild id: "YYYY-MM-DD"}}
DEFAULT_SAINTDAY_TIME = "07:00"
COLOR = discord.Color.from_rgb(150, 30, 45)
PAGE = 3500
MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September",
          "October", "November", "December"]
SPELLINGS = {"katherine": "catherine", "anthony": "antony", "blaise": "blase", "alexis": "alexius",
             "quentin": "quintin", "denis": "dionysius", "austin": "augustine"}


@functools.lru_cache(maxsize=1)
def saints() -> list:
    return json.loads(SAINTS_PATH.read_text(encoding="utf-8"))["saints"]


@functools.lru_cache(maxsize=1)
def _legend() -> dict:
    return json.loads(GOLDEN_LEGEND_PATH.read_text(encoding="utf-8"))["books"]


def saint_key(s: dict) -> str:
    return f"{zlib.crc32(f'{s['name']}|{s['month']}|{s['day']}'.encode('utf-8')):08x}"


def by_key(key: str) -> "dict | None":
    return next((s for s in saints() if saint_key(s) == key), None)


def _words(text: str) -> list:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()
    words = re.sub(r"[^a-z ]+", " ", text).split()
    return [SPELLINGS.get(w, w) for w in words if w not in ("st", "sts", "saint", "saints", "s", "ss", "the", "of", "and")]


def on_day(month: int, day: int) -> list:
    return [s for s in saints() if (s["month"], s["day"]) == (month, day)]


def parse_day(text: str) -> "tuple | None":
    """'25 July', 'July 25', 'jul 25th', '7/25' -> (7, 25)."""
    t = text.strip().lower()
    m = re.fullmatch(r"(\d{1,2})/(\d{1,2})", t)
    if m:
        month, day = int(m.group(1)), int(m.group(2))
    else:
        m = re.fullmatch(r"(\d{1,2})(?:st|nd|rd|th)?\s+([a-z]+)|([a-z]+)\s+(\d{1,2})(?:st|nd|rd|th)?", t)
        if not m:
            return None
        day = int(m.group(1) or m.group(4))
        name = m.group(2) or m.group(3)
        month = next((i + 1 for i, mo in enumerate(MONTHS) if len(name) >= 3 and mo.lower().startswith(name)), None)
        if month is None:
            return None
    try:
        datetime.date(2024, month, day)                # (a leap year: 29 February is a real feast day)
    except ValueError:
        return None
    return month, day


def find_saints(query: str) -> list:
    """Saints whose name has every word of the query (Butler's or the Legend's name)."""
    want = _words(query)
    if not want:
        return []
    found = []
    for s in saints():
        names = [s["name"], *s.get("also", [])]
        if any(all(w in _words(n) for w in want) for n in names):
            found.append(s)
    return found


def day_label(s: dict) -> str:
    return f"{s['day']} {MONTHS[s['month'] - 1]}" if s["month"] else "no fixed day"


def butler_embed(s: dict) -> discord.Embed:
    life = s["life"] if len(s["life"]) <= 3600 else s["life"][:3600].rsplit(". ", 1)[0] + ". …"
    embed = discord.Embed(title=f"{s['name']} — {day_label(s)}", description=life, color=COLOR)
    if s.get("reflection"):
        embed.add_field(name="Reflection", value=s["reflection"][:1024], inline=False)
    embed.set_footer(text="Butler's Lives of the Saints (abridged, 1894)"
                          + (" · 📖 the Golden Legend has this saint too" if s.get("golden_legend") else ""))
    return embed


def legend_text(s: dict, n: int = 0) -> str:
    chapters = _legend()[s["golden_legend"][n]]
    return "\n\n".join(t for verses in chapters.values() for t in verses.values()).strip()


def legend_pages(s: dict, n: int = 0) -> list:
    text, pages = legend_text(s, n), []
    while text:
        if len(text) <= PAGE:
            pages.append(text)
            break
        cut = text.rfind("\n\n", 0, PAGE)
        cut = cut if cut > PAGE // 2 else text.rfind(". ", 0, PAGE) + 1
        pages.append(text[:cut].strip())
        text = text[cut:].strip()
    return pages or [""]


def legend_embed(s: dict, page: int = 0, n: int = 0) -> discord.Embed:
    pages = legend_pages(s, n)
    page = max(0, min(page, len(pages) - 1))
    names = s.get("also") or [s["name"]]
    name = names[min(n, len(names) - 1)] if s["source"] == "butler" else s["name"]
    embed = discord.Embed(title=f"{name} — {day_label(s)}", description=pages[page], color=COLOR)
    embed.set_footer(text="The Golden Legend (Jacobus de Voragine; Caxton's translation)"
                          + (f" · page {page + 1} of {len(pages)}" if len(pages) > 1 else ""))
    return embed


class SaintButton(discord.ui.DynamicItem[discord.ui.Button],
                  template=r"saint:(?P<action>gl|page):(?P<key>[0-9a-f]{8}):(?P<n>\d+):(?P<page>\d+)"):
    """📖 Golden Legend under a Butler life, and ◀ ▶ through a Legend chapter. The custom_id
    carries the saint and page, so these keep working after a restart."""

    def __init__(self, action: str, key: str, n: int = 0, page: int = 0, label: str = "", emoji: str = ""):
        super().__init__(discord.ui.Button(label=label or None, emoji=emoji or None, style=discord.ButtonStyle.secondary,
                                           custom_id=f"saint:{action}:{key}:{n}:{page}"))
        self.action, self.key, self.n, self.page = action, key, n, page

    @classmethod
    async def from_custom_id(cls, interaction, item, match):
        return cls(match["action"], match["key"], int(match["n"]), int(match["page"]))

    async def callback(self, interaction: discord.Interaction):
        s = by_key(self.key)
        if s is None:
            await interaction.response.send_message("I can't find that saint any more.", ephemeral=True)
            return
        if self.action == "gl":                        # open the Legend as a new message
            await interaction.response.send_message(**legend_message(s, 0, self.n))
        else:                                          # turn its page
            await interaction.response.edit_message(**legend_message(s, self.page, self.n))


class SaintPicker(discord.ui.DynamicItem[discord.ui.Select], template=r"saintpick:(?P<tag>[0-9a-f]{8})"):
    """A menu of saints (several of one name, or the rest of the day's); each option's value is
    the saint's key, so it keeps working after a restart. Persistent like SaintButton: a view
    that times out unregisters the dynamic items it holds, bot-wide."""

    def __init__(self, choices: list, placeholder: str = "Choose a saint…"):
        options = [discord.SelectOption(label=s["name"][:100], description=day_label(s), value=saint_key(s))
                   for s in choices[:25]]
        tag = f"{zlib.crc32('|'.join(o.value for o in options).encode()):08x}"
        super().__init__(discord.ui.Select(placeholder=placeholder, options=options, custom_id=f"saintpick:{tag}"))

    @classmethod
    async def from_custom_id(cls, interaction, item, match):
        picker = cls.__new__(cls)
        discord.ui.DynamicItem.__init__(picker, item)
        return picker

    async def callback(self, interaction: discord.Interaction):
        s = by_key(self.item.values[0])
        if s is None:
            await interaction.response.send_message("I can't find that saint any more.", ephemeral=True)
            return
        await interaction.response.send_message(**saint_message(s))


bot.add_dynamic_items(SaintButton, SaintPicker)


def legend_message(s: dict, page: int = 0, n: int = 0) -> dict:
    """The Legend's chapter, a page at a time (◀ ▶ when it runs to more than one)."""
    pages = len(legend_pages(s, n))
    page = max(0, min(page, pages - 1))
    view = None
    if pages > 1:
        view = discord.ui.View(timeout=None)
        view.add_item(SaintButton("page", saint_key(s), n, (page - 1) % pages, emoji="◀"))
        view.add_item(SaintButton("page", saint_key(s), n, (page + 1) % pages, emoji="▶"))
    return {"embed": legend_embed(s, page, n), "view": view}


def saint_message(s: dict, others: list = (), others_label: str = "") -> dict:
    """send() kwargs for one saint: Butler's life (with the Legend button), or the Legend's."""
    if s["source"] == "butler":
        message = {"embed": butler_embed(s), "view": discord.ui.View(timeout=None)}
        for n, _ in enumerate(s.get("golden_legend", [])):
            message["view"].add_item(SaintButton("gl", saint_key(s), n, 0, emoji="📖",
                                                 label="Golden Legend" + (f" ({n + 1})" if n else "")))
    else:
        message = legend_message(s)
        message["view"] = message["view"] or discord.ui.View(timeout=None)
    if others:
        message["view"].add_item(SaintPicker(others, others_label))
    if not message["view"].children:
        message["view"] = None
    return message


def _today() -> datetime.date:
    return datetime.datetime.now(datetime.timezone.utc).date()


async def send_saint(ctx, query: str = "") -> None:
    query = query.strip()
    day = parse_day(query) if query else (_today().month, _today().day)
    if day:
        found = on_day(*day)
        if not found:
            await ctx.send(f"I have no saint for {day[1]} {MONTHS[day[0] - 1]}.")
            return
        heading = "🕯️ **Saint of the day**" if not query else f"🕯️ **{day[1]} {MONTHS[day[0] - 1]}**"
        others = found[1:]
        await ctx.send(content=heading + (f" · and {len(others)} more in the menu below" if others else ""),
                       **saint_message(found[0], others, "Also on this day…"))
        return
    found = find_saints(query)
    if not found:
        await ctx.send(f"I don't know a saint called **{discord.utils.escape_markdown(query)}**. "
                       f"Try a name (`!saint Christopher`), a day (`!saint 25 July`), or `!saint` for today's.")
        return
    if len(found) == 1:
        await ctx.send(**saint_message(found[0]))
        return
    view = discord.ui.View(timeout=None)
    view.add_item(SaintPicker(found, "Which one?"))
    listing = "\n".join(f"• **{s['name']}** — {day_label(s)}" for s in found[:25])
    more = f"\n…and {len(found) - 25} more — try a longer name." if len(found) > 25 else ""
    await ctx.send(embed=discord.Embed(title=f"🕯️ Saints called “{query}”", description=listing + more, color=COLOR),
                   view=view)


@bot.command(name="saint", aliases=["saints", "saintoftheday"])
async def cmd_saint(ctx, *, query: str = ""):
    """The saint of the day, or any saint, from Butler's Lives of the Saints and the Golden Legend.
    Usage: !saint                — today's saint
           !saint Christopher    — a saint by name
           !saint 25 July        — the saints of a day"""
    await send_saint(ctx, query)


# ── the daily post (!saintsetup) ────────────────────────────────────────────
# Per-server settings in guild_config.json: saintday_channel_id, saintday_time ("HH:MM" UTC).

def _load_state() -> dict:
    try:
        return json.loads(SAINTDAY_PATH.read_text(encoding="utf-8")) if SAINTDAY_PATH.exists() else {}
    except ValueError:
        return {}


async def post_saintday(guild_id, channel, day: datetime.date, force: bool = False) -> bool:
    state = _load_state()
    if state.get("posted", {}).get(str(guild_id)) == day.isoformat() and not force:
        return False                                    # (a restart doesn't post it twice)
    found = on_day(day.month, day.day)
    if not found:
        return False
    others = found[1:]
    await channel.send(content="🕯️ **Saint of the day**" + (f" · and {len(others)} more in the menu below" if others else ""),
                       **saint_message(found[0], others, "Also on this day…"))
    state.setdefault("posted", {})[str(guild_id)] = day.isoformat()
    _atomic_write_json(SAINTDAY_PATH, state)
    return True


async def run_daily_saints(client, day: datetime.date, current_hm: str) -> int:
    posted = 0
    for guild_id, g in _load_guild_config().items():
        channel_id = g.get("saintday_channel_id")
        if not channel_id or g.get("saintday_time", DEFAULT_SAINTDAY_TIME) != current_hm:
            continue
        channel = client.get_channel(int(channel_id))
        if channel is None:
            continue
        try:
            posted += await post_saintday(guild_id, channel, day)
        except Exception:
            log.exception(f"Failed to post the saint of the day for guild {guild_id}")
    return posted


@tasks.loop(minutes=1)
async def daily_saint_task():
    now = datetime.datetime.now(datetime.timezone.utc)
    await run_daily_saints(bot, now.date(), f"{now.hour:02d}:{now.minute:02d}")


@daily_saint_task.before_loop
async def _before_daily_saint():
    await bot.wait_until_ready()


@bot.command(name="saintsetup", aliases=["saintconfig"])
@commands.has_permissions(administrator=True)
async def cmd_saintsetup(ctx, action: str = "", *, arg: str = ""):
    """Post the saint of the day in a channel.
    Usage: !saintsetup                  — show this server's settings
           !saintsetup channel #chan    — post each day's saint there
           !saintsetup time 07:00       — daily post time (24h UTC)
           !saintsetup test             — post today's now
           !saintsetup off              — stop the daily post"""
    if not ctx.guild:
        await ctx.send("This command only works in a server.")
        return
    g = _load_guild_config().get(str(ctx.guild.id), {})
    channel_id, time_hm = g.get("saintday_channel_id"), g.get("saintday_time", DEFAULT_SAINTDAY_TIME)
    action = action.strip().lower()
    if not action:
        embed = discord.Embed(title=f"🕯️ Saint of the day — {ctx.guild.name}", color=COLOR)
        embed.add_field(name="Channel", value=f"<#{channel_id}>" if channel_id else "*not set — no daily post*")
        embed.add_field(name="Time (UTC)", value=time_hm)
        embed.set_footer(text="!saintsetup channel #chan · time HH:MM · test · off")
        await ctx.send(embed=embed)
    elif action == "off":
        _update_guild_config(ctx.guild.id, saintday_channel_id=None)
        await ctx.send("The daily saint post is off for this server. (`!saint` still works.)")
    elif action == "channel":
        channel = ctx.message.channel_mentions[0] if ctx.message.channel_mentions else None
        if channel is None:
            await ctx.send("Mention a channel: `!saintsetup channel #saints`")
            return
        _update_guild_config(ctx.guild.id, saintday_channel_id=channel.id)
        await ctx.send(f"The saint of the day will be posted in {channel.mention} at {time_hm} UTC.")
    elif action == "time":
        m = re.match(r"^(\d{1,2}):(\d{2})$", arg.strip())
        if not m or not (0 <= int(m.group(1)) <= 23 and 0 <= int(m.group(2)) <= 59):
            await ctx.send("Use 24-hour UTC time: `!saintsetup time 07:00`")
            return
        hm = f"{int(m.group(1)):02d}:{int(m.group(2)):02d}"
        _update_guild_config(ctx.guild.id, saintday_time=hm)
        await ctx.send(f"Daily saint time set to **{hm} UTC**.")
    elif action == "test":
        channel = bot.get_channel(int(channel_id)) if channel_id else ctx.channel
        await post_saintday(ctx.guild.id, channel, _today(), force=True)
    else:
        await ctx.send("Unknown option. Use `channel`, `time`, `test`, or `off`.")
