"""
!office: an hour of the Divine Office (the Roman Breviary) for a day, as the Divinum Officium project sets it out.

The project's own engine works out the day (which feast, which psalms, antiphons, lessons, commemorations) by its
rubrics: its Perl scripts and texts are a git clone in vendor/divinum-officium (not ours to track; `git pull` keeps it
current), and officium.pl is run for the hour, in English, by the Divino Afflatu rubrics (1911-1954: the Breviary
the Anglican Breviary translates). Its HTML is turned into Discord text here: a page a section of the hour (Psalms,
Chapter, Hymn...), rubrics in italics, V. and R., ◀ ▶ to turn the pages, which work after a restart (the hour is
simply worked out again).

    !office            -> Lauds today        !office vespers tomorrow      !office matins 2026-12-25
"""
import asyncio
import datetime
import functools
import html
import json
import re
import shutil
from pathlib import Path

import discord

from discord.ext import commands, tasks

from core import ROOT, _atomic_write_json, _load_guild_config, _update_guild_config, bot, log

ENGINE = ROOT / "vendor" / "divinum-officium"
SCRIPTS = ENGINE / "web" / "cgi-bin" / "horas"
TEXTS = ENGINE / "web" / "www" / "horas"
VERSION = "Divino Afflatu - 1954"
# the rubrics one can ask for (key -> the engine's version, what we call it); the key goes in a button's custom_id
RUBRICS = {"da": ("Divino Afflatu - 1954", "Divino Afflatu, 1911–1954"),
           "1570": ("Tridentine - 1570", "Tridentine, 1570"), "1910": ("Tridentine - 1906", "Tridentine, before 1911"),
           "1955": ("Reduced - 1955", "the 1955 simplification"), "1960": ("Rubrics 1960 - 1960", "the 1960 rubrics"),
           "monastic": ("Monastic - 1963", "the Monastic Breviary (1963)")}
RUBRIC_WORDS = {"1954": "da", "divino": "da", "afflatu": "da", "da": "da", "1911": "da", "1570": "1570",
                "tridentine": "1570", "trent": "1570", "1910": "1910", "1906": "1910", "1955": "1955",
                "1960": "1960", "1962": "1960", "monastic": "monastic", "benedictine": "monastic"}
COLOR = discord.Color.dark_red()
PAGE = 3900
HOURS = {   # what people type -> (the engine's name, ours)
    "matins": ("Matutinum", "Matins"), "matutinum": ("Matutinum", "Matins"), "vigils": ("Matutinum", "Matins"),
    "lauds": ("Laudes", "Lauds"), "laudes": ("Laudes", "Lauds"), "prime": ("Prima", "Prime"), "prima": ("Prima", "Prime"),
    "terce": ("Tertia", "Terce"), "tierce": ("Tertia", "Terce"), "tertia": ("Tertia", "Terce"),
    "sext": ("Sexta", "Sext"), "sexta": ("Sexta", "Sext"), "none": ("Nona", "None"), "nona": ("Nona", "None"),
    "vespers": ("Vespera", "Vespers"), "vespera": ("Vespera", "Vespers"), "evensong": ("Vespera", "Vespers"),
    "compline": ("Completorium", "Compline"), "completorium": ("Completorium", "Compline"),
}
MONTHS = ["january", "february", "march", "april", "may", "june", "july", "august", "september", "october",
          "november", "december"]
RANKS = {"Duplex I. classis": "Double of the First Class", "Duplex II. classis": "Double of the Second Class",
         "Duplex majus": "Greater Double", "Duplex": "Double", "Semiduplex": "Semidouble", "Simplex": "Simple",
         "Dominica major": "Greater Sunday", "Dominica minor": "Lesser Sunday", "Feria major": "Greater Feria",
         "Feria privilegiata": "Privileged Feria", "Feria": "Feria", "Vigilia": "Vigil", "I. classis": "First Class",
         "II. classis": "Second Class", "III. classis": "Third Class", "IV. classis": "Fourth Class"}


def perl() -> "str | None":
    return shutil.which("perl") or next((p for p in (r"C:\Strawberry\perl\bin\perl.exe",) if Path(p).exists()), None)


def available() -> bool:
    return perl() is not None and (SCRIPTS / "officium.pl").exists()


# ── the day and the hour asked for ──────────────────────────────────────────

def rubrics_of(args: str) -> "tuple[str, str]":
    """(the rubrics' key, the rest): "vespers 1960 tomorrow" -> ("1960", "vespers tomorrow"); Divino Afflatu if none."""
    words = args.split()
    key = next((RUBRIC_WORDS[w.lower()] for w in words if w.lower() in RUBRIC_WORDS), "da")
    return key, " ".join(w for w in words if w.lower() not in RUBRIC_WORDS)


def parse(args: str, today: datetime.date) -> "tuple[str, datetime.date] | str":
    """(hour, date) from "vespers tomorrow", "matins 2026-12-25", "25 December", or an error message."""
    words = args.lower().replace(",", " ").split()
    hour = next((w for w in words if w in HOURS), "lauds")
    rest = " ".join(w for w in words if w not in HOURS)
    if not rest or rest == "today":
        return hour, today
    if rest in ("tomorrow", "yesterday"):
        return hour, today + datetime.timedelta(days=1 if rest == "tomorrow" else -1)
    try:
        return hour, datetime.date.fromisoformat(rest)
    except ValueError:
        pass
    m = re.fullmatch(r"(\d{1,2})\s+([a-z]+)(?:\s+(\d{4}))?|([a-z]+)\s+(\d{1,2})(?:\s+(\d{4}))?", rest)
    if m:
        day, month, year = (m[1], m[2], m[3]) if m[1] else (m[5], m[4], m[6])
        month_n = next((i for i, name in enumerate(MONTHS, 1) if name.startswith(month[:3]) and len(month) >= 3), None)
        if month_n:
            try:
                return hour, datetime.date(int(year) if year else today.year, month_n, int(day))
            except ValueError:
                pass
    return ("I didn't understand that. Try `!office` (Lauds today), `!office vespers`, `!office compline tomorrow` "
            "or `!office matins 2026-12-25`. The hours: matins, lauds, prime, terce, sext, none, vespers, compline. "
            "Other rubrics: add `1570`, `1910`, `1955`, `1960` or `monastic`.")


# ── running the engine ──────────────────────────────────────────────────────

def query(hour: str, day: datetime.date, rubrics: str = "da") -> str:
    return (f"date1={day.month:02d}-{day.day:02d}-{day.year}&command=pray{HOURS[hour][0]}"
            f"&version={RUBRICS[rubrics][0]}"
            f"&testmode=regular&lang1=English&lang2=English&votive=&nofancychars=1")


async def run(hour: str, day: datetime.date, rubrics: str = "da") -> str:
    """The engine's page for the hour (it reads its texts by paths relative to its own folder)."""
    proc = await asyncio.create_subprocess_exec(perl(), "officium.pl", query(hour, day, rubrics), cwd=str(SCRIPTS),
                                                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    out, err = await asyncio.wait_for(proc.communicate(), timeout=60)
    if err.strip():
        log.warning(f"!office {hour} {day}: {err.decode('utf-8', 'replace')[:300]}")
    return out.decode("utf-8", "replace")


# ── its HTML as Discord text ────────────────────────────────────────────────

@functools.lru_cache(maxsize=1)
def english_titles() -> dict:
    """The engine names the day in Latin even in English ("Dominica VI Post Epiphaniam"): {Latin title: English}, from
    the [Officium] of the same file in its Latin and English folders, where the English one is English."""
    out = {}
    for folder in ("Sancti", "Tempora", "Commune"):
        for f in (TEXTS / "Latin" / folder).glob("*.txt"):
            e = TEXTS / "English" / folder / f.name
            if not e.exists():
                continue
            lat = re.search(r"(?m)^\[Officium\][^\n]*\n(.+)", f.read_text(encoding="utf-8", errors="replace"))
            eng = re.search(r"(?m)^\[Officium\][^\n]*\n(.+)", e.read_text(encoding="utf-8", errors="replace"))
            if lat and eng and lat[1].strip() != eng[1].strip():
                out[lat[1].strip()] = eng[1].strip()
    return out


ORD = {"I": "First", "II": "Second", "III": "Third", "IV": "Fourth", "V": "Fifth", "VI": "Sixth", "VII": "Seventh",
       "VIII": "Eighth", "IX": "Ninth", "X": "Tenth", "XI": "Eleventh", "XII": "Twelfth", "XIII": "Thirteenth",
       "XIV": "Fourteenth", "XV": "Fifteenth", "XVI": "Sixteenth", "XVII": "Seventeenth", "XVIII": "Eighteenth",
       "XIX": "Nineteenth", "XX": "Twentieth", "XXI": "Twenty-first", "XXII": "Twenty-second", "XXIII": "Twenty-third",
       "XXIV": "Twenty-fourth"}
FERIA = {"II": "Monday", "III": "Tuesday", "IV": "Wednesday", "V": "Thursday", "VI": "Friday"}


def english(title: str) -> str:
    """A Latin title of the day in English: from the texts' own English, or the Sundays and ferias by pattern."""
    title = re.sub(r"\s+", " ", title).strip()
    if title in english_titles():
        return english_titles()[title]
    m = re.fullmatch(r"Dominica ([IVX]+) (Post Epiphaniam|Post Pentecosten|Adventus|in Quadragesima|Post Pascha)"
                     r"(.*)", title)
    if m:
        where = {"Post Epiphaniam": "after Epiphany", "Post Pentecosten": "after Pentecost", "Adventus": "of Advent",
                 "in Quadragesima": "of Lent", "Post Pascha": "after Easter"}[m[2]]
        return f"{ORD.get(m[1], m[1])} Sunday {where}{english(m[3]) if m[3].strip() else ''}"
    m = re.fullmatch(r"Feria ([IVX]+)(?:\s+(.*))?", title)
    if m and m[1] in FERIA:
        return f"{FERIA[m[1]]}" + (f" ({english(m[2])})" if m[2] else "")
    m = re.fullmatch(r"Sabbato(?:\s+(.*))?", title)
    if m:
        return "Saturday" + (f" ({english(m[1])})" if m[1] else "")
    return title


def text_of(cell: str) -> str:
    """A section of the hour as Discord text: its heading in bold, rubrics (the engine's red) in italics, the big red
    first letter of a prayer joined to it, V. and R., the ✠ where one signs oneself."""
    c = re.sub(r"(?is)<DIV ALIGN='right'>.*?</DIV>", "", cell)                       # (Top · Next)
    c = re.sub(r"(?<=[\s>])\*(?=[\s<])", "∗", c)          # (the chant's mid-verse mark: not Discord's italics)
    c = re.sub(r"(?is)<span style='color:red; font-size:1\.25em'>\+</span>", "✠", c)
    c = re.sub(r"(?is)<FONT SIZE='\+2' COLOR=\"red\"><B><I>(\w)</I></B></FONT>", r"\1", c)   # (drop capitals)
    c = re.sub(r"(?is)<FONT SIZE='\+1' COLOR=\"red\"><B><I>(.*?)</I></B></FONT>", r"\n**\1**", c)  # (a heading)
    c = re.sub(r"(?is)<FONT COLOR=\"red\"><I>(V\.|R\.|Ant\.|℣\.|℟\.)</I></FONT>", r"\1", c)
    c = re.sub(r"(?is)<FONT[^>]*COLOR=\"?red\"?[^>]*>(.*?)</FONT>", lambda m: f"*{strip(m[1])}*" if strip(m[1]) else "", c)
    c = re.sub(r"(?is)<FONT SIZE='-1'\s*>\s*\{.*?\}\s*</FONT>", "", c)               # ({the engine's notes})
    c = re.sub(r"(?i)<br\s*/?>", "\n", c)
    # (the chant's mid-verse mark, " * ", in an asterisk Discord doesn't read as italics, before ours are added)
    c = re.sub(r"(?<=\s)\*(?=\s)", "∗", c)
    t = strip(c, keep_lines=True)
    t = re.sub(r"(?<!\*)\*\s+\*(?!\*)", " ", t)                 # (an empty italic)
    return re.sub(r"\n{3,}", "\n\n", t).strip()


def strip(s: str, keep_lines: bool = False) -> str:
    s = html.unescape(re.sub(r"(?s)<[^>]+>", "", s))
    if keep_lines:
        return "\n".join(re.sub(r"[ \t]+", " ", line).strip() for line in s.split("\n"))
    return re.sub(r"\s+", " ", s).strip()


def parse_hour(page: str) -> "tuple[str, list[str]]":
    """(the day, in English, with its rank and commemorations; [a section's text]) from the engine's page."""
    m = re.search(r"(?is)<FONT COLOR=\"green\">(.*?)</FONT>(.*?)</P>", page)
    day = ""
    if m:
        name, _, rank = strip(m[1]).partition(" ~ ")
        name = re.sub(r"\s+[IVX]+\. (?:of \w+|\w+is)$", "", name)          # ("IV. of November", "IV. Novembris")
        day = english(name)
        if rank:
            day += f" · {RANKS.get(rank.strip(), next((v for k, v in RANKS.items() if rank.startswith(k)), rank))}"
        for com in re.findall(r"(?is)Commemoratio:</SPAN>\s*<FONT[^>]*>(.*?)</FONT>", m[2]):
            day += f"\nCommemoration: {english(strip(com))}"
    cells = re.findall(r"(?is)<TD VALIGN='TOP' WIDTH='100%' ID='\w+?\d+'>(.*?)</TD>", page)
    return day, [t for t in (text_of(c) for c in cells) if t]


def pages_of(sections: list) -> list:
    """The sections on pages of up to PAGE characters (a long section, Matins' lessons, cut at a line)."""
    pages, cur = [], ""
    for s in sections:
        while len(s) > PAGE:
            cut = s.rfind("\n", 0, PAGE)
            cut = cut if cut > PAGE // 2 else PAGE
            if cur:
                pages.append(cur)
                cur = ""
            pages.append(s[:cut].rstrip())
            s = s[cut:].lstrip()
        if cur and len(cur) + len(s) + 2 > PAGE:
            pages.append(cur)
            cur = s
        else:
            cur = f"{cur}\n\n{s}" if cur else s
    if cur:
        pages.append(cur)
    return pages


_CACHE: dict = {}


async def hour_pages(hour: str, day: datetime.date, rubrics: str = "da") -> "tuple[str, list[str]]":
    key = (HOURS[hour][1], day, rubrics)
    if key not in _CACHE:
        if len(_CACHE) > 64:
            _CACHE.clear()
        name, sections = parse_hour(await run(hour, day, rubrics))
        _CACHE[key] = (name, pages_of(sections))
    return _CACHE[key]


def embed_for(hour: str, day: datetime.date, name: str, pages: list, page: int, rubrics: str = "da") -> discord.Embed:
    title = f"🕯️ {HOURS[hour][1]} · {day.strftime('%A')} {day.day} {day.strftime('%B %Y')}"
    embed = discord.Embed(title=title[:256], color=COLOR, description=pages[page][:4096])
    if name:
        embed.add_field(name="The day", value=name[:1024], inline=False)
    book = "The Monastic Breviary" if rubrics == "monastic" else f"The Roman Breviary ({RUBRICS[rubrics][1]})"
    embed.set_footer(text=f"{book}, from Divinum Officium · page {page + 1} of {len(pages)}")
    return embed


class OfficePage(discord.ui.DynamicItem[discord.ui.Button], template=r"doff:(?P<hour>[a-z]+):(?P<day>\d{8}):"
                                                                            r"(?P<page>\d+):(?P<dir>[pn])"
                                                                            r"(?::(?P<rub>[a-z0-9]+))?"):
    """◀ ▶ through an hour's pages; the hour is worked out again when pressed (after a restart, too)."""

    def __init__(self, hour: str, day: datetime.date, page: int, direction: str, disabled: bool = False,
                 rubrics: str = "da"):
        super().__init__(discord.ui.Button(emoji="◀️" if direction == "p" else "▶️", style=discord.ButtonStyle.secondary,
                                           custom_id=f"doff:{hour}:{day:%Y%m%d}:{page}:{direction}:{rubrics}",
                                           disabled=disabled))
        self.hour, self.day, self.page, self.direction, self.rubrics = hour, day, page, direction, rubrics

    @classmethod
    async def from_custom_id(cls, interaction, item, match):
        rubrics = match["rub"] if match["rub"] in RUBRICS else "da"         # (buttons made before the choice: "da")
        return cls(match["hour"], datetime.datetime.strptime(match["day"], "%Y%m%d").date(), int(match["page"]),
                   match["dir"], rubrics=rubrics)

    async def callback(self, interaction: discord.Interaction):
        name, pages = await hour_pages(self.hour, self.day, self.rubrics)
        page = max(0, min(len(pages) - 1, self.page + (1 if self.direction == "n" else -1)))
        await interaction.response.edit_message(embed=embed_for(self.hour, self.day, name, pages, page, self.rubrics),
                                                view=view_for(self.hour, self.day, page, len(pages), self.rubrics))


def view_for(hour: str, day: datetime.date, page: int, total: int, rubrics: str = "da") -> "discord.ui.View | None":
    if total < 2:
        return None
    view = discord.ui.View(timeout=None)
    view.add_item(OfficePage(hour, day, page, "p", disabled=page == 0, rubrics=rubrics))
    view.add_item(OfficePage(hour, day, page, "n", disabled=page >= total - 1, rubrics=rubrics))
    return view


def _today() -> datetime.date:
    return datetime.datetime.now(datetime.timezone.utc).date()


async def send_office(ctx, args: str) -> None:
    rubrics, args = rubrics_of(args)
    parsed = parse(args, _today())
    if isinstance(parsed, str):
        await ctx.send(parsed)
        return
    if not available():
        await ctx.send("The Divine Office isn't set up on this bot yet.")
        return
    hour, day = parsed
    async with ctx.typing():
        name, pages = await hour_pages(hour, day, rubrics)
    if not pages:
        await ctx.send(f"I couldn't put together {HOURS[hour][1]} for {day:%d %B %Y}.")
        return
    await ctx.send(embed=embed_for(hour, day, name, pages, 0, rubrics), view=view_for(hour, day, 0, len(pages), rubrics))


@bot.command(name="office", aliases=["breviary", "hours", "divineoffice"])
async def cmd_office(ctx, *, args: str = ""):
    """An hour of the Divine Office (the Roman Breviary) for today or another day.
    Usage: !office  |  !office vespers  |  !office compline tomorrow  |  !office matins 2026-12-25
           !office vespers 1960  |  !office lauds monastic  (also 1570, 1910, 1955; Divino Afflatu if none)"""
    await send_office(ctx, args)


bot.add_dynamic_items(OfficePage)


# ── the daily post (!daily office) ──────────────────────────────────────────
# Per server in guild_config.json: office_channel_id, office_time ("HH:MM" UTC), office_hour, office_rubrics.
OFFICE_PATH = ROOT / "data" / "office.json"          # {"posted": {guild: "date hour"}}: a restart doesn't post twice
DEFAULT_TIME, DEFAULT_HOUR = "06:00", "lauds"


def _load_state() -> dict:
    try:
        return json.loads(OFFICE_PATH.read_text(encoding="utf-8")) if OFFICE_PATH.exists() else {}
    except ValueError:
        return {}


async def post_office(guild_id, channel, day: datetime.date, hour: str, rubrics: str, force: bool = False) -> bool:
    state = _load_state()
    mark = f"{day.isoformat()} {hour}"
    if state.get("posted", {}).get(str(guild_id)) == mark and not force:
        return False
    name, pages = await hour_pages(hour, day, rubrics)
    if not pages:
        return False
    await channel.send(embed=embed_for(hour, day, name, pages, 0, rubrics), view=view_for(hour, day, 0, len(pages), rubrics))
    state.setdefault("posted", {})[str(guild_id)] = mark
    _atomic_write_json(OFFICE_PATH, state)
    return True


async def run_daily_office(client, day: datetime.date, current_hm: str) -> int:
    if not available():
        return 0
    posted = 0
    for guild_id, g in _load_guild_config().items():
        channel_id = g.get("office_channel_id")
        if not channel_id or g.get("office_time", DEFAULT_TIME) != current_hm:
            continue
        channel = client.get_channel(int(channel_id))
        if channel is None:
            continue
        try:
            posted += await post_office(guild_id, channel, day, g.get("office_hour", DEFAULT_HOUR),
                                        g.get("office_rubrics", "da"))
        except Exception:
            log.exception(f"Failed to post the Divine Office for guild {guild_id}")
    return posted


@tasks.loop(minutes=1)
async def daily_office_task():
    now = datetime.datetime.now(datetime.timezone.utc)
    await run_daily_office(bot, now.date(), f"{now.hour:02d}:{now.minute:02d}")


@daily_office_task.before_loop
async def _before_daily_office():
    await bot.wait_until_ready()


@bot.command(name="officesetup", hidden=True)                         # (!daily office)
@commands.has_permissions(administrator=True)
async def cmd_officesetup(ctx, action: str = "", *, arg: str = ""):
    """Post an hour of the Divine Office in a channel each day.
    Usage: !officesetup                  — show this server's settings
           !officesetup channel #chan    — post it there each day
           !officesetup time 06:00       — at that time (24h UTC)
           !officesetup hour vespers     — which hour (Lauds unless set)
           !officesetup rubrics 1960     — which Breviary (1570, 1910, 1954, 1955, 1960, monastic)
           !officesetup test             — post today's now
           !officesetup off              — stop the daily post"""
    if not ctx.guild:
        await ctx.send("This command only works in a server.")
        return
    g = _load_guild_config().get(str(ctx.guild.id), {})
    channel_id, time_hm = g.get("office_channel_id"), g.get("office_time", DEFAULT_TIME)
    hour, rubrics = g.get("office_hour", DEFAULT_HOUR), g.get("office_rubrics", "da")
    action, arg = action.strip().lower(), arg.strip()
    if not action:
        embed = discord.Embed(title=f"🕯️ The Divine Office — {ctx.guild.name}", color=COLOR)
        embed.add_field(name="Channel", value=f"<#{channel_id}>" if channel_id else "*not set — no daily post*")
        embed.add_field(name="Time (UTC)", value=time_hm)
        embed.add_field(name="Hour", value=HOURS[hour][1])
        embed.add_field(name="Rubrics", value=RUBRICS[rubrics][1])
        embed.set_footer(text="!daily office channel #chan · time HH:MM · hour vespers · rubrics 1960 · test · off")
        await ctx.send(embed=embed)
    elif action == "off":
        _update_guild_config(ctx.guild.id, office_channel_id=None)
        await ctx.send("The daily Divine Office post is off for this server. (`!office` still works.)")
    elif action == "channel":
        channel = ctx.message.channel_mentions[0] if ctx.message.channel_mentions else None
        if channel is None:
            await ctx.send("Mention a channel: `!daily office channel #prayer`")
            return
        _update_guild_config(ctx.guild.id, office_channel_id=channel.id)
        await ctx.send(f"{HOURS[hour][1]} will be posted in {channel.mention} each day at {time_hm} UTC.")
    elif action == "time":
        m = re.match(r"^(\d{1,2}):(\d{2})$", arg)
        if not m or not (0 <= int(m.group(1)) <= 23 and 0 <= int(m.group(2)) <= 59):
            await ctx.send("Use 24-hour UTC time: `!daily office time 06:00`")
            return
        hm = f"{int(m.group(1)):02d}:{int(m.group(2)):02d}"
        _update_guild_config(ctx.guild.id, office_time=hm)
        await ctx.send(f"The daily office will be posted at **{hm} UTC**.")
    elif action == "hour":
        if arg.lower() not in HOURS:
            await ctx.send("Which hour? matins, lauds, prime, terce, sext, none, vespers or compline.")
            return
        _update_guild_config(ctx.guild.id, office_hour=arg.lower())
        await ctx.send(f"The daily post will be **{HOURS[arg.lower()][1]}**.")
    elif action == "rubrics":
        key = RUBRIC_WORDS.get(arg.lower())
        if key is None:
            await ctx.send("Which Breviary? `1570`, `1910`, `1954` (Divino Afflatu), `1955`, `1960` or `monastic`.")
            return
        _update_guild_config(ctx.guild.id, office_rubrics=key)
        await ctx.send(f"The daily post will follow **{RUBRICS[key][1]}**.")
    elif action == "test":
        if not available():
            await ctx.send("The Divine Office isn't set up on this bot yet.")
            return
        channel = bot.get_channel(int(channel_id)) if channel_id else ctx.channel
        await post_office(ctx.guild.id, channel, _today(), hour, rubrics, force=True)
    else:
        await ctx.send("Unknown option. Use `channel`, `time`, `hour`, `rubrics`, `test`, or `off`.")
