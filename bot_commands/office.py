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
import re
import shutil
from pathlib import Path

import discord

from core import ROOT, bot, log

ENGINE = ROOT / "vendor" / "divinum-officium"
SCRIPTS = ENGINE / "web" / "cgi-bin" / "horas"
TEXTS = ENGINE / "web" / "www" / "horas"
VERSION = "Divino Afflatu - 1954"
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
            "or `!office matins 2026-12-25`. The hours: matins, lauds, prime, terce, sext, none, vespers, compline.")


# ── running the engine ──────────────────────────────────────────────────────

def query(hour: str, day: datetime.date) -> str:
    return (f"date1={day.month:02d}-{day.day:02d}-{day.year}&command=pray{HOURS[hour][0]}&version={VERSION}"
            f"&testmode=regular&lang1=English&lang2=English&votive=&nofancychars=1")


async def run(hour: str, day: datetime.date) -> str:
    """The engine's page for the hour (it reads its texts by paths relative to its own folder)."""
    proc = await asyncio.create_subprocess_exec(perl(), "officium.pl", query(hour, day), cwd=str(SCRIPTS),
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
        name = re.sub(r"\s+[IVX]+\. of \w+$", "", name)                              # ("IV. of November": the week)
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


async def hour_pages(hour: str, day: datetime.date) -> "tuple[str, list[str]]":
    key = (HOURS[hour][1], day)
    if key not in _CACHE:
        if len(_CACHE) > 64:
            _CACHE.clear()
        name, sections = parse_hour(await run(hour, day))
        _CACHE[key] = (name, pages_of(sections))
    return _CACHE[key]


def embed_for(hour: str, day: datetime.date, name: str, pages: list, page: int) -> discord.Embed:
    title = f"🕯️ {HOURS[hour][1]} · {day.strftime('%A')} {day.day} {day.strftime('%B %Y')}"
    embed = discord.Embed(title=title[:256], color=COLOR, description=pages[page][:4096])
    if name:
        embed.add_field(name="The day", value=name[:1024], inline=False)
    embed.set_footer(text=f"The Roman Breviary ({VERSION.split(' - ')[0]}), from Divinum Officium · "
                          f"page {page + 1} of {len(pages)}")
    return embed


class OfficePage(discord.ui.DynamicItem[discord.ui.Button], template=r"doff:(?P<hour>[a-z]+):(?P<day>\d{8}):"
                                                                            r"(?P<page>\d+):(?P<dir>[pn])"):
    """◀ ▶ through an hour's pages; the hour is worked out again when pressed (after a restart, too)."""

    def __init__(self, hour: str, day: datetime.date, page: int, direction: str, disabled: bool = False):
        super().__init__(discord.ui.Button(emoji="◀️" if direction == "p" else "▶️", style=discord.ButtonStyle.secondary,
                                           custom_id=f"doff:{hour}:{day:%Y%m%d}:{page}:{direction}", disabled=disabled))
        self.hour, self.day, self.page, self.direction = hour, day, page, direction

    @classmethod
    async def from_custom_id(cls, interaction, item, match):
        return cls(match["hour"], datetime.datetime.strptime(match["day"], "%Y%m%d").date(), int(match["page"]),
                   match["dir"])

    async def callback(self, interaction: discord.Interaction):
        name, pages = await hour_pages(self.hour, self.day)
        page = max(0, min(len(pages) - 1, self.page + (1 if self.direction == "n" else -1)))
        await interaction.response.edit_message(embed=embed_for(self.hour, self.day, name, pages, page),
                                                view=view_for(self.hour, self.day, page, len(pages)))


def view_for(hour: str, day: datetime.date, page: int, total: int) -> "discord.ui.View | None":
    if total < 2:
        return None
    view = discord.ui.View(timeout=None)
    view.add_item(OfficePage(hour, day, page, "p", disabled=page == 0))
    view.add_item(OfficePage(hour, day, page, "n", disabled=page >= total - 1))
    return view


def _today() -> datetime.date:
    return datetime.datetime.now(datetime.timezone.utc).date()


async def send_office(ctx, args: str) -> None:
    parsed = parse(args, _today())
    if isinstance(parsed, str):
        await ctx.send(parsed)
        return
    if not available():
        await ctx.send("The Divine Office isn't set up on this bot yet.")
        return
    hour, day = parsed
    async with ctx.typing():
        name, pages = await hour_pages(hour, day)
    if not pages:
        await ctx.send(f"I couldn't put together {HOURS[hour][1]} for {day:%d %B %Y}.")
        return
    await ctx.send(embed=embed_for(hour, day, name, pages, 0), view=view_for(hour, day, 0, len(pages)))


@bot.command(name="office", aliases=["breviary", "hours", "divineoffice"])
async def cmd_office(ctx, *, args: str = ""):
    """An hour of the Divine Office (the Roman Breviary) for today or another day.
    Usage: !office  |  !office vespers  |  !office compline tomorrow  |  !office matins 2026-12-25"""
    await send_office(ctx, args)


bot.add_dynamic_items(OfficePage)
