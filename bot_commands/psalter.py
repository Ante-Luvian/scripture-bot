"""
!metrical: the Scottish Metrical Psalter of 1650 -- every psalm in rhymed,
regular verse for singing, with the tune it is sung to (data/psalter/, built
by scripts/build_psalter.py).
  !metrical 23            Psalm 23 to its tune (Crimond)
  !metrical 100b          the psalm's second version, where there is one
  !metrical 119:105-112   just the stanzas for those verses
  !metrical shepherd      psalms with those words; a tune name lists its psalms
  !metrical               a random psalm
Each psalm has buttons to play its tune (an organ .ogg), to read the psalm
in the KJV, to turn the page of a long psalm, and to switch to its other
version, and a menu that plays any other tune in the same meter.
"""
import functools
import json
import random
import re
import unicodedata

import discord
from discord import app_commands

from core import ROOT, bot, lookup

PSALTER_PATH = ROOT / "data" / "psalter" / "psalter.json"
AUDIO_DIR = ROOT / "data" / "psalter" / "audio"
COLOR = discord.Color.from_rgb(40, 80, 130)
PAGE_CHARS = 3600
SOURCE = "Scottish Psalter, 1650 · words and tunes via the Open 1650 project"


@functools.lru_cache(maxsize=1)
def psalter() -> dict:
    return json.loads(PSALTER_PATH.read_text(encoding="utf-8"))


def tunes() -> dict:
    return psalter()["tunes"]


def get_psalm(number: int, second: bool = False) -> "dict | None":
    version = "alternate" if second else "primary"
    return next((p for p in psalter()["psalms"] if p["number"] == number and p["version"] == version), None)


def has_second(number: int) -> bool:
    return get_psalm(number, True) is not None


def key_of(psalm: dict) -> str:
    """'23' or '100b' -- how users and buttons name a version."""
    return f"{psalm['number']}{'b' if psalm['version'] == 'alternate' else ''}"


def by_key(key: str) -> "dict | None":
    m = re.fullmatch(r"(\d{1,3})(b?)", key)
    return get_psalm(int(m.group(1)), bool(m.group(2))) if m else None


def _norm(text: str) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()
    text = re.sub(r"[^a-z0-9 ]+", " ", text.replace("'", ""))
    return re.sub(r"\s+", " ", text).strip()


def psalm_words(psalm: dict) -> str:
    return " ".join(" ".join(s["lines"]) for s in psalm["stanzas"])


# ── reading a request ───────────────────────────────────────────────────────

_REQUEST = re.compile(r"^(?:ps(?:alms?)?\.?\s*)?(\d{1,3})\s*(b|second|alt(?:ernate)?|2nd)?"
                      r"(?:\s*:\s*(\d{1,3})(?:\s*-\s*(\d{1,3}))?)?$")


def parse_request(text: str) -> "tuple | None":
    """'23' -> (23, False, None); '100b' / '100 second' -> (100, True, None);
    '119:105-112' -> (119, False, (105, 112)); anything else -> None."""
    m = _REQUEST.match(text.strip().lower())
    if not m:
        return None
    verses = None
    if m.group(3):
        first = int(m.group(3))
        verses = (first, int(m.group(4)) if m.group(4) else first)
    return int(m.group(1)), bool(m.group(2)), verses


def search(query: str) -> list:
    """Psalms whose first line, then whose words, contain the query; a tune's name lists its psalms."""
    q = _norm(query)
    if not q:
        return []
    every = psalter()["psalms"]
    tune = next((tid for tid, t in tunes().items() if _norm(t["title"]) == q or tid.replace("-", " ") == q), None)
    if tune:
        return [p for p in every if p["tune"] == tune]
    first = [p for p in every if q in _norm(p["first_line"])]
    words = [p for p in every if p not in first and q in _norm(psalm_words(p))]
    if first or words:
        return first + words
    terms = q.split()
    return [p for p in every if all(t in _norm(psalm_words(p)).split() for t in terms)]


# ── showing one ─────────────────────────────────────────────────────────────

def _stanza_text(stanza: dict) -> str:
    # the old psalm books number each stanza by the Bible verse it starts at
    num = f"**{stanza['verses'][0]}** " if stanza["verses"] else ""
    return num + "\n".join(stanza["lines"])


def pages(psalm: dict, verses: "tuple | None" = None) -> list:
    """The stanzas (those for `verses`, if given) in embed-sized pages."""
    stanzas = psalm["stanzas"]
    if verses:
        lo, hi = verses
        stanzas = [s for s in stanzas if s["verses"] and s["verses"][0] <= hi and lo <= s["verses"][-1]]
    out, page = [], ""
    for s in stanzas:
        text = _stanza_text(s)
        if page and len(page) + len(text) + 2 > PAGE_CHARS:
            out.append(page)
            page = ""
        page = f"{page}\n\n{text}" if page else text
    if page:
        out.append(page)
    return out


def verse_span(psalm: dict) -> str:
    nums = [v for s in psalm["stanzas"] for v in s["verses"]]
    return f"{min(nums)}–{max(nums)}" if nums else ""


def tune_credit(tid: str) -> str:
    t = tunes().get(tid)
    if not t:
        return ""
    return f"**{t['title'].upper()}**" + (f" — {t['attribution']}" if t["attribution"] else "")


def same_meter_tunes(psalm: dict) -> list:
    return [tid for tid, t in tunes().items() if t["meter"] == psalm["meter"]]


def psalm_embed(psalm: dict, page: int = 0, verses: "tuple | None" = None) -> discord.Embed:
    shown = pages(psalm, verses)
    page = max(0, min(page, len(shown) - 1))
    second = " (second version)" if psalm["version"] == "alternate" else ""
    title = f"🎶 Psalm {psalm['number']}{second}"
    if verses:
        title += f", verses {verses[0]}" + (f"–{verses[1]}" if verses[1] != verses[0] else "")
    embed = discord.Embed(title=title, description=shown[page] if shown else "*No stanzas for those verses.*",
                          color=COLOR)
    meter = psalm["meter_name"] if psalm["meter_name"] and not psalm["meter_name"][0].isdigit() else ""
    about = [f"**Meter:** {psalm['meter']}" + (f" ({meter})" if meter else "")]
    if psalm["tune"]:
        about.insert(0, "**Sung to:** " + tune_credit(psalm["tune"]))
    if has_second(psalm["number"]):
        other = "the first" if psalm["version"] == "alternate" else "a second"
        about.append(f"This psalm also has {other} version in the Psalter — the button below switches.")
    embed.add_field(name="About", value="\n".join(about)[:1024], inline=False)
    footer = SOURCE
    if len(shown) > 1 and verses:
        footer = "Too long to show at once — ask for fewer verses · " + footer
    elif len(shown) > 1:
        footer = f"Page {page + 1} of {len(shown)} · " + footer
    embed.set_footer(text=footer)
    return embed


def audio_path(tid: str):
    path = AUDIO_DIR / f"{tid}.ogg"
    return path if tid and path.exists() else None


async def play(interaction: discord.Interaction, psalm: dict, tid: str) -> None:
    path = audio_path(tid)
    if path is None:
        await interaction.response.send_message("⚠️ I don't have that tune to play.", ephemeral=True)
        return
    name = tunes()[tid]["title"]
    own = "" if tid == psalm["tune"] else " (another tune in the same meter)"
    await interaction.response.send_message(
        f"🎵 **Psalm {psalm['number']}** to **{name.upper()}**{own}: one verse of the tune, in four parts on "
        f"an organ — every stanza is sung to it.",
        file=discord.File(path, filename=f"Psalm_{key_of(psalm)}_{re.sub(r'[^A-Za-z0-9]+', '_', name)}.ogg"))


def kjv_embed(psalm: dict) -> discord.Embed:
    result = lookup.get_verse(f"Psalms {psalm['number']}")
    embed = discord.Embed(title=f"📖 Psalm {psalm['number']} in the King James Version", color=COLOR)
    if not result.get("found"):
        embed.description = "⚠️ I couldn't load that psalm."
        return embed
    text = re.sub(r"\*\*\[(\d+)\]\*\*", r"**\1**", result["text"]).strip()
    if len(text) > 4000:
        text = text[:3900].rsplit(" ", 1)[0] + f"…\n\n*Read on with `!verse Psalms {psalm['number']}`.*"
    embed.description = text
    return embed


class PsalterButton(discord.ui.DynamicItem[discord.ui.Button],
                    template=r"metrical:(?P<action>play|bible|other|page):(?P<key>\d{1,3}b?):(?P<page>\d{1,2})"):
    """Persistent buttons; for 'page' the number is the page to show."""

    def __init__(self, action: str, key: str, page: int = 0, label: str = ""):
        look = {"play": ("Play the tune", "▶️"), "bible": ("Read in the KJV", "📖"),
                "other": (label or "Other version", "🔁"), "page": (label or "More", None)}[action]
        super().__init__(discord.ui.Button(label=look[0], emoji=look[1], style=discord.ButtonStyle.secondary,
                                           custom_id=f"metrical:{action}:{key}:{page}"))
        self.action, self.key, self.page = action, key, page

    @classmethod
    async def from_custom_id(cls, interaction, item, match):
        return cls(match["action"], match["key"], int(match["page"]))

    async def callback(self, interaction: discord.Interaction):
        psalm = by_key(self.key)
        if psalm is None:
            await interaction.response.send_message("⚠️ I can't find that psalm any more.", ephemeral=True)
        elif self.action == "play":
            await play(interaction, psalm, psalm["tune"])
        elif self.action == "bible":
            await interaction.response.send_message(embed=kjv_embed(psalm), ephemeral=True)
        elif self.action == "other":
            other = get_psalm(psalm["number"], psalm["version"] == "primary")
            await interaction.response.send_message(embed=psalm_embed(other), view=psalm_view(other))
        else:
            await interaction.response.edit_message(embed=psalm_embed(psalm, self.page),
                                                    view=psalm_view(psalm, self.page))


class TuneMenu(discord.ui.DynamicItem[discord.ui.Select], template=r"metrical:tune:(?P<key>\d{1,3}b?)"):
    """Play the psalm's words against any other tune of the same meter."""

    def __init__(self, key: str):
        psalm = by_key(key)
        options = [discord.SelectOption(label=tunes()[tid]["title"], value=tid,
                                        description=tunes()[tid]["attribution"][:100] or None)
                   for tid in (same_meter_tunes(psalm) if psalm else [])][:25]
        super().__init__(discord.ui.Select(placeholder="Play it to another tune in the same meter…",
                                           options=options or [discord.SelectOption(label="—", value="-")],
                                           custom_id=f"metrical:tune:{key}"))
        self.key = key

    @classmethod
    async def from_custom_id(cls, interaction, item, match):
        return cls(match["key"])

    async def callback(self, interaction: discord.Interaction):
        psalm = by_key(self.key)
        if psalm is None:
            await interaction.response.send_message("⚠️ I can't find that psalm any more.", ephemeral=True)
            return
        await play(interaction, psalm, self.item.values[0])


bot.add_dynamic_items(PsalterButton, TuneMenu)


def psalm_view(psalm: dict, page: int = 0, verses: "tuple | None" = None) -> discord.ui.View:
    view = discord.ui.View(timeout=None)            # persistent: must never time out
    key = key_of(psalm)
    if audio_path(psalm["tune"]):
        view.add_item(PsalterButton("play", key))
    view.add_item(PsalterButton("bible", key))
    if has_second(psalm["number"]):
        label = "First version" if psalm["version"] == "alternate" else "Second version"
        view.add_item(PsalterButton("other", key, label=label))
    total = len(pages(psalm, verses))
    if not verses and total > 1:                    # a verse range is short; whole psalms may need pages
        if page > 0:
            view.add_item(PsalterButton("page", key, page - 1, label="◀ Earlier verses"))
        if page < total - 1:
            view.add_item(PsalterButton("page", key, page + 1, label="Later verses ▶"))
    if len(same_meter_tunes(psalm)) > 1:
        view.add_item(TuneMenu(key))
    return view


def list_embed(query: str, found: list) -> discord.Embed:
    lines = [f"• **Psalm {key_of(p)}** — *{p['first_line']}*" for p in found[:20]]
    more = f"\n…and {len(found) - 20} more — try more words." if len(found) > 20 else ""
    embed = discord.Embed(title=f"🎶 Metrical psalms for “{query}”", description="\n".join(lines) + more,
                          color=COLOR)
    embed.set_footer(text="Pick one below, or !metrical <number>")
    return embed


class PsalmPicker(discord.ui.View):
    def __init__(self, found: list):
        super().__init__(timeout=300)
        options = [discord.SelectOption(label=f"Psalm {key_of(p)}", description=p["first_line"][:100],
                                        value=key_of(p)) for p in found[:25]]
        select = discord.ui.Select(placeholder="Choose a psalm…", options=options)
        select.callback = self._chosen
        self.add_item(select)
        self.select = select

    async def _chosen(self, interaction: discord.Interaction):
        psalm = by_key(self.select.values[0])
        await interaction.response.send_message(embed=psalm_embed(psalm), view=psalm_view(psalm))


async def send_metrical(ctx, query: str) -> None:
    query = query.strip()
    if not query or query.lower() == "random":
        psalm = random.choice(psalter()["psalms"])
        await ctx.send(embed=psalm_embed(psalm), view=psalm_view(psalm))
        return
    request = parse_request(query)
    if request:
        number, second, verses = request
        psalm = get_psalm(number, second)
        if psalm is None:
            if second and get_psalm(number):
                await ctx.send(f"Psalm {number} has only one version in the Psalter — `!metrical {number}`.")
            else:
                await ctx.send("⚠️ The Psalter has Psalms 1 to 150.")
            return
        await ctx.send(embed=psalm_embed(psalm, verses=verses), view=psalm_view(psalm, verses=verses))
        return
    found = search(query)
    if not found:
        await ctx.send(f"No metrical psalm found for **{query}**. Try a number (`!metrical 23`), words "
                       f"(`!metrical shepherd`) or a tune (`!metrical crimond`).")
    elif len(found) == 1:
        await ctx.send(embed=psalm_embed(found[0]), view=psalm_view(found[0]))
    else:
        await ctx.send(embed=list_embed(query, found), view=PsalmPicker(found))


@bot.command(name="metrical", aliases=["metricalpsalm", "singpsalm", "psalter1650"])
async def cmd_metrical(ctx, *, query: str = ""):
    """A psalm from the Scottish Metrical Psalter (1650), with its tune to play.
    Usage: !metrical 23            — Psalm 23 in metre
           !metrical 100b          — a psalm's second version
           !metrical 119:105-112   — the stanzas for those verses
           !metrical shepherd      — psalms with those words (or a tune: !metrical crimond)
           !metrical               — a random psalm"""
    await send_metrical(ctx, query)


async def _psalm_autocomplete(interaction: discord.Interaction, current: str) -> list:
    q = _norm(current)
    out = []
    for p in psalter()["psalms"]:
        name = f"Psalm {key_of(p)} — {p['first_line']}"
        if not q or q in _norm(name):
            out.append(app_commands.Choice(name=name[:100], value=key_of(p)))
    return out[:25]


@bot.tree.command(name="metrical", description="A psalm from the Scottish Metrical Psalter (1650), with its tune")
@app_commands.describe(psalm="A number (23, 100b for a second version, 119:105-112), words, or a tune; "
                             "empty for random")
@app_commands.autocomplete(psalm=_psalm_autocomplete)
async def metrical_slash(interaction: discord.Interaction, psalm: str = ""):
    await interaction.response.defer()
    ctx = await bot.get_context(interaction)
    await send_metrical(ctx, psalm)
