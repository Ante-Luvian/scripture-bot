"""
!harmony: one event in the life of Christ as each Gospel tells it, side by
side, following A. T. Robertson's Harmony of the Gospels (1922; data/
harmony.json, built by scripts/build_harmony.py) -- 185 sections from the
birth of John the Baptist to the Ascension.
  !harmony feeding five thousand    find an event by its title
  !harmony John 6:5                 the event a verse belongs to
  !harmony 72                       a section by number
  !harmony                          a random event told by more than one Gospel
Buttons read each Gospel's whole account and step to the event before or after.
"""
import functools
import json
import random
import re

import discord
from discord import app_commands

from core import ROOT, bot, lookup

HARMONY_PATH = ROOT / "data" / "harmony.json"
COLOR = discord.Color.from_rgb(70, 90, 140)
GOSPELS = ("Matthew", "Mark", "Luke", "John")
EXCERPT = 300
NUMBERS = {"5000": "five thousand", "4000": "four thousand", "12": "twelve", "70": "seventy", "7": "seven",
           "10": "ten", "2": "two", "3": "three"}


@functools.lru_cache(maxsize=1)
def sections() -> list:
    return json.loads(HARMONY_PATH.read_text(encoding="utf-8"))["sections"]


def by_number(number: str) -> "dict | None":
    return next((s for s in sections() if s["section"] == number.lower()), None)


def position(section: dict) -> int:
    return sections().index(section)


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]+", " ", text.lower().replace("'s", ""))).strip()


# ── references ──────────────────────────────────────────────────────────────

def pieces(ref: str) -> list:
    """'John 11:55-12:1, 9-11' -> ['John 11:55-12:1', 'John 12:9-11']"""
    book, rest = re.match(r"^((?:\d )?[A-Za-z]+)\s+(.+)$", ref).groups()
    out, chapter = [], None
    for piece in re.split(r",\s*", rest):
        if ":" in piece or chapter is None:
            out.append(f"{book} {piece}")
        else:
            out.append(f"{book} {chapter}:{piece}")
        ends = re.findall(r"(\d+):\d+", piece)
        if ends:
            chapter = ends[-1]
        elif ":" not in piece:
            chapter = piece.split("-")[-1]
    return out


def _span(ref: str) -> "tuple | None":
    """'Mark 6:30-44' -> ('Mark', (6, 30), (6, 44)); 'Matthew 5-7' -> ('Matthew', (5, 1), (7, 999))"""
    m = re.match(r"^((?:\d )?[A-Za-z]+) (\d+)(?::(\d+))?(?:-(\d+)(?::(\d+))?)?$", ref)
    if not m:
        return None
    book, c1, v1, a, b = m.groups()
    c1 = int(c1)
    start = (c1, int(v1) if v1 else 1)
    if a is None:
        end = (c1, int(v1)) if v1 else (c1, 999)
    elif b is not None:
        end = (int(a), int(b))
    elif v1:
        end = (c1, int(a))
    else:
        end = (int(a), 999)
    return book, start, end


def sections_for(ref: str) -> "list | None":
    """The sections whose passages include `ref`, or None if it isn't a Gospel reference."""
    m = re.match(r"^\s*((?:\d\s*)?[A-Za-z]+)\.?\s+(\d+)(?::(\d+))?\s*$", ref)
    if not m:
        return None
    _, book = lookup._resolve_book(m.group(1))
    if book not in GOSPELS:
        return None
    want = (int(m.group(2)), int(m.group(3)) if m.group(3) else 1)
    out = []
    for s in sections():
        for r in s["refs"]:
            for p in pieces(r["ref"]):
                span = _span(p)
                if span and span[0] == book and span[1] <= want <= span[2]:
                    out.append(s)
                    break
            else:
                continue
            break
    return out


# Everyday names for events whose titles in Robertson are more formal ("Jesus institutes the
# memorial of eating bread and drinking wine"), each by a verse at the heart of the event.
POPULAR = {
    "last supper": "Luke 22:19", "lords supper": "Luke 22:19", "communion": "Luke 22:19",
    "eucharist": "Luke 22:19", "crucifixion": "Luke 23:33", "the cross": "Luke 23:33",
    "resurrection": "Matthew 28:6", "easter": "Matthew 28:6", "empty tomb": "Matthew 28:6",
    "nativity": "Luke 2:7", "christmas": "Luke 2:7", "birth of jesus": "Luke 2:7",
    "baptism of jesus": "Matthew 3:16", "temptation": "Matthew 4:1", "lords prayer": "Matthew 6:9",
    "beatitudes": "Matthew 5:3", "prodigal son": "Luke 15:11", "lost sheep": "Luke 15:4",
    "good samaritan": "Luke 10:33", "sower": "Mark 4:3", "denial of peter": "Luke 22:61",
    "peters denial": "Luke 22:61", "betrayal": "Mark 14:46", "arrest": "Mark 14:46",
    "woman at the well": "John 4:7", "nicodemus": "John 3:1", "water into wine": "John 2:9",
    "wedding at cana": "John 2:9", "great commission": "Matthew 28:19", "ascension": "Luke 24:51",
    "palm sunday": "Mark 11:8", "doubting thomas": "John 20:27", "emmaus": "Luke 24:13",
    "road to emmaus": "Luke 24:13", "loaves and fishes": "Mark 6:41",
}


def search(query: str) -> list:
    q = query.strip()
    popular = POPULAR.get(_norm(q).replace("the ", "", 1) if _norm(q) not in POPULAR else _norm(q))
    if popular:
        return sections_for(popular)
    if re.fullmatch(r"\d{1,3}[a-z]?", q.lower()):
        s = by_number(q)
        return [s] if s else []
    passage = sections_for(q)
    if passage is not None:
        return passage
    words = [NUMBERS.get(w, w) for w in _norm(q).split()]
    terms = " ".join(words).split()
    stop = {"the", "of", "a", "and", "in", "to", "jesus", "last", "christ"}
    terms = [t for t in terms if t not in stop] or terms
    # word stems, so "crucifixion" finds "crucified" and "feeding" finds "feeds"
    stems = [t[:6] if len(t) > 6 else t[:4] if len(t) > 4 else t for t in terms]

    def hits(s):
        return sum(1 for t in stems if re.search(rf"\b{re.escape(t)}", _norm(s["title"])))
    scored = [(hits(s), s) for s in sections()]
    every = [s for n, s in scored if n == len(stems)]
    if every:
        return every
    best = max((n for n, _ in scored), default=0)
    return [s for n, s in scored if n == best and n * 2 >= len(stems)] if best else []


# ── showing one ─────────────────────────────────────────────────────────────

def passage_text(ref: str) -> str:
    texts = []
    for p in pieces(ref):
        result = lookup.get_verse(p)
        if result.get("found"):
            texts.append(re.sub(r"\*\*\[(\d+)\]\*\*\s*", r"**\1** ", result["text"]).strip())
    return "\n".join(texts)


def told_by(section: dict) -> str:
    books = [g for g in GOSPELS if any(r["book"] == g for r in section["refs"])]
    if not books:
        return ""
    if len(books) == 1:
        return f"Only in {books[0]}"
    if len(books) == 4:
        return "Told by all four Gospels"
    return "Told by " + ", ".join(books[:-1]) + " and " + books[-1]


def section_embed(section: dict) -> discord.Embed:
    embed = discord.Embed(title=f"📖 {section['title']}"[:256], color=COLOR)
    embed.description = f"*{section['part']}* · section {section['section']} of the harmony\n**{told_by(section)}**"
    for r in section["refs"][:6]:
        text = passage_text(r["ref"])
        short = text if len(text) <= EXCERPT else text[:EXCERPT].rsplit(" ", 1)[0] + " …"
        embed.add_field(name=r["ref"], value=short or "—", inline=len(section["refs"]) > 1)
    embed.set_footer(text="A. T. Robertson, A Harmony of the Gospels (1922) · KJV text · "
                          "the buttons read each account in full")
    return embed


class HarmonyButton(discord.ui.DynamicItem[discord.ui.Button],
                    template=r"harmony:(?P<action>read|go):(?P<section>\d{1,3}[a-z]?):(?P<arg>\d{1,3})"):
    """'read': the arg-th passage in full (privately); 'go': show section number arg's neighbour."""

    def __init__(self, action: str, section: str, arg: int, label: str):
        super().__init__(discord.ui.Button(label=label[:80], style=discord.ButtonStyle.secondary,
                                           custom_id=f"harmony:{action}:{section}:{arg}"))
        self.action, self.section, self.arg = action, section, arg

    @classmethod
    async def from_custom_id(cls, interaction, item, match):
        return cls(match["action"], match["section"], int(match["arg"]), item.label or "")

    async def callback(self, interaction: discord.Interaction):
        section = by_number(self.section)
        if section is None:
            await interaction.response.send_message("⚠️ I can't find that part of the harmony.", ephemeral=True)
            return
        if self.action == "read":
            ref = section["refs"][self.arg]["ref"]
            text = passage_text(ref)
            if len(text) > 3900:
                text = text[:3800].rsplit("\n", 1)[0] + f"\n\n*…read on with `!verse {ref}`*"
            embed = discord.Embed(title=f"📖 {ref}", description=text, color=COLOR)
            embed.set_footer(text=section["title"][:200])
            await interaction.response.send_message(embed=embed, ephemeral=True)
        else:
            target = sections()[self.arg]
            await interaction.response.edit_message(embed=section_embed(target), view=section_view(target))


bot.add_dynamic_items(HarmonyButton)


def section_view(section: dict) -> discord.ui.View:
    view = discord.ui.View(timeout=None)            # persistent buttons: must never time out
    for i, r in enumerate(section["refs"][:5]):
        view.add_item(HarmonyButton("read", section["section"], i, f"Read {r['ref']}"))
    at = position(section)
    if at > 0:
        view.add_item(HarmonyButton("go", section["section"], at - 1, "◀ Event before"))
    if at < len(sections()) - 1:
        view.add_item(HarmonyButton("go", section["section"], at + 1, "Event after ▶"))
    return view


class Picker(discord.ui.View):
    def __init__(self, found: list):
        super().__init__(timeout=300)
        options = [discord.SelectOption(label=s["title"][:100], value=s["section"],
                                        description=f"§{s['section']} · {told_by(s)}"[:100]) for s in found[:25]]
        select = discord.ui.Select(placeholder="Choose an event…", options=options)
        select.callback = self._chosen
        self.add_item(select)
        self.select = select

    async def _chosen(self, interaction: discord.Interaction):
        section = by_number(self.select.values[0])
        await interaction.response.send_message(embed=section_embed(section), view=section_view(section))


async def send_harmony(ctx, query: str) -> None:
    query = query.strip()
    if not query or query.lower() == "random":
        section = random.choice([s for s in sections() if len({r["book"] for r in s["refs"]}) > 1])
        await ctx.send(embed=section_embed(section), view=section_view(section))
        return
    found = search(query)
    if not found:
        await ctx.send(f"I couldn't find **{query}** in the harmony. Try words from an event "
                       f"(`!harmony feeding five thousand`, `!harmony transfiguration`) or a verse (`!harmony Mark 6:41`).")
        return
    if len(found) == 1:
        await ctx.send(embed=section_embed(found[0]), view=section_view(found[0]))
        return
    lines = [f"**§{s['section']}** {s['title']} — *{told_by(s)}*" for s in found[:20]]
    more = f"\n…and {len(found) - 20} more" if len(found) > 20 else ""
    embed = discord.Embed(title=f"📖 Events for “{query}”", description="\n".join(lines)[:3900] + more, color=COLOR)
    await ctx.send(embed=embed, view=Picker(found))


@bot.command(name="harmony", aliases=["gospels", "synoptic"])
async def cmd_harmony(ctx, *, query: str = ""):
    """An event in the life of Christ as each Gospel tells it, side by side.
    Usage: !harmony feeding five thousand   — find an event
           !harmony John 6:5                — the event a verse belongs to
           !harmony 72                      — a section by number
           !harmony                         — a random event"""
    await send_harmony(ctx, query)


@bot.tree.command(name="harmony", description="An event in the life of Christ as each Gospel tells it, side by side")
@app_commands.describe(event="Words from the event (feeding five thousand), a verse (Mark 6:41), or a section number")
async def harmony_slash(interaction: discord.Interaction, event: str = ""):
    await interaction.response.defer()
    ctx = await bot.get_context(interaction)
    await send_harmony(ctx, event)
