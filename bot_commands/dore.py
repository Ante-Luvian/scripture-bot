"""
!dore -- Gustave Doré's engravings for the Bible (with the Apocrypha), the Divine Comedy and
Paradise Lost (data/dore/plates.json, built by scripts/build_dore.py), each tied to the
passage it illustrates. Also the 🖼️ Doré button under !verse, wherever a passage has a plate.
The pictures are shown from Wikimedia.
"""
import functools
import json
import random
import re

import discord

from core import ROOT, bot, lookup

PLATES_PATH = ROOT / "data" / "dore" / "plates.json"
COLOR = discord.Color.from_rgb(60, 60, 70)
WORKS = {"bible": "The Holy Bible (1866)", "dante": "The Divine Comedy (1861–68)", "milton": "Paradise Lost (1866)"}
REF = re.compile(r"^(?P<book>.+?) (?P<ch>\d+)(?::(?P<v1>\d+)(?:\s*[–-]\s*(?P<v2>\d+))?)?(?: \([^)]*\))?$")
MAX_SHOWN = 4


@functools.lru_cache(maxsize=1)
def plates() -> list:
    if not PLATES_PATH.exists():
        return []
    out = json.loads(PLATES_PATH.read_text(encoding="utf-8"))["plates"]
    seen = set()
    for p in out:
        key = f"{p['set'][0]}{p['n']}".lower()          # "b026", "dinf3", "m12": short, for button ids
        while key in seen:                              # (two plates share page 095, and 123)
            key += "x"
        seen.add(key)
        p["key"] = key
    return out


@functools.lru_cache(maxsize=1)
def by_key() -> dict:
    return {p["key"]: p for p in plates()}


def for_passage(book: str, chapter: int, start: "int | None" = None, end: "int | None" = None) -> list:
    """The plates illustrating a passage (a whole chapter if no verses are given)."""
    hits = []
    for p in plates():
        if p["book"] != book or p["chapter"] != chapter:
            continue
        if start is None or p["set"] == "dante":            # (Dante's are by canto)
            hits.append(p)
        elif p["start"] <= (end or start) and start <= p["end"]:
            hits.append(p)
    return hits


def for_result(result: dict) -> list:
    """The plates for a !verse result ("John 3:16", "Inferno 1:1–3", "Genesis 7")."""
    if not result.get("found"):
        return []
    m = REF.match(result.get("reference", ""))
    if not m:
        return []
    book = lookup._resolve_book(m["book"])[1] or m["book"]
    start = int(m["v1"]) if m["v1"] else None
    return for_passage(book, int(m["ch"]), start, int(m["v2"]) if m["v2"] else start)


def plate_embed(p: dict) -> discord.Embed:
    if p["set"] == "milton":
        title = f"Paradise Lost {p['chapter']}:{p['start']}" + (f"–{p['end']}" if p["end"] != p["start"] else "")
        description = f"*{p['title']}*"
        read = f"!verse Paradise Lost {p['chapter']}:{p['start']}" + (f"-{p['end']}" if p["end"] != p["start"] else "")
    elif p["set"] == "dante":
        title, description = p["title"], None
        read = f"!verse {p['book']} {p['chapter']}" if p["book"] else ""
    else:
        span = f"{p['book']} {p['chapter']}:{p['start']}" + (f"-{p['end']}" if p["end"] != p["start"] else "")
        title, description, read = p["title"], span, f"!verse {span}"
    embed = discord.Embed(title=f"🖼️ {title}", url=p["page"], color=COLOR, description=description)
    if read:
        embed.add_field(name="Read it", value=f"`{read}`", inline=False)
    embed.set_image(url=p["image"])
    embed.set_footer(text=f"Gustave Doré, {WORKS[p['set']]} · image: Wikimedia Commons")
    return embed


class DoreButton(discord.ui.DynamicItem[discord.ui.Button], template=r"dore:(?P<keys>[a-z0-9,]+)"):
    """🖼️ under a !verse result: the passage's Doré plates. The ids are in the custom_id, so it
    keeps working after a restart."""

    def __init__(self, keys: list):
        super().__init__(discord.ui.Button(label="Doré", emoji="🖼️", style=discord.ButtonStyle.secondary, row=2,
                                           custom_id="dore:" + ",".join(keys)[:94]))
        self.keys = keys

    @classmethod
    async def from_custom_id(cls, interaction, item, match):
        return cls(match["keys"].split(","))

    async def callback(self, interaction: discord.Interaction):
        shown = [by_key()[k] for k in self.keys if k in by_key()][:MAX_SHOWN]
        if not shown:
            await interaction.response.send_message("⚠️ I can't find that engraving any more.", ephemeral=True)
            return
        await interaction.response.send_message(embeds=[plate_embed(p) for p in shown])


bot.add_dynamic_items(DoreButton)


def dore_button(result: dict) -> "DoreButton | None":
    found = for_result(result)
    return DoreButton([p["key"] for p in found]) if found else None


def search(query: str) -> list:
    q = query.lower().strip()
    words = [w for w in re.findall(r"[a-z]+", q) if len(w) > 2]
    hits = [p for p in plates() if words and all(w in (p["title"] + " " + p.get("cited", "")).lower() for w in words)]
    return hits


async def send_dore(ctx, query: str = "") -> None:
    if not plates():
        await ctx.send("⚠️ Doré's engravings aren't available right now.")
        return
    q = query.strip()
    if q.lower() in ("list", "all", "help", "index"):
        counts = {k: sum(1 for p in plates() if p["set"] == k) for k in WORKS}
        await ctx.send(embed=discord.Embed(title="🖼️ Gustave Doré's engravings", color=COLOR, description=(
            f"**The Bible**, with the Apocrypha: {counts['bible']} plates\n"
            f"**The Divine Comedy**: {counts['dante']} plates\n"
            f"**Paradise Lost**: {counts['milton']} plates\n\n"
            "`!dore` — one at random\n"
            "`!dore Genesis 7` · `!dore Inferno 3` · `!dore Paradise Lost 1` — a passage's engravings\n"
            "`!dore deluge` — by name\n\n"
            "Under `!verse`, a 🖼️ Doré button appears whenever the passage has one.")))
        return
    if not q:
        await ctx.send(embed=plate_embed(random.choice(plates())))
        return
    found = []
    m = REF.match(q)
    if m:
        book = lookup._resolve_book(m["book"])[1]
        if book:
            start = int(m["v1"]) if m["v1"] else None
            found = for_passage(book, int(m["ch"]), start, int(m["v2"]) if m["v2"] else start)
            if not found:
                await ctx.send(f"Doré made no engraving for **{book} {m['ch']}"
                               + (f":{m['v1']}" if m["v1"] else "") + "**. `!dore list` shows what there is.")
                return
    if not found:
        book = lookup._resolve_book(q)[1]
        if book:
            found = [p for p in plates() if p["book"] == book]
    found = found or search(q)
    if not found:
        await ctx.send(f"I don't have a Doré engraving for **{discord.utils.escape_markdown(q)}**. "
                       f"Try `!dore Genesis 7`, `!dore Inferno 3` or `!dore list`.")
        return
    extra = f"*{len(found)} engravings; here are the first {MAX_SHOWN}. Ask for a chapter to narrow it.*" \
        if len(found) > MAX_SHOWN else None
    await ctx.send(extra, embeds=[plate_embed(p) for p in found[:MAX_SHOWN]])


@bot.command(name="dore", aliases=["doré", "engraving", "engravings"])
async def cmd_dore(ctx, *, query: str = ""):
    """Gustave Doré's engravings for the Bible, Dante and Milton.
    Usage: !dore               — one at random
           !dore Genesis 7     — a passage's engravings (also Inferno 3, Paradise Lost 1)
           !dore deluge        — by name · !dore list"""
    await send_dore(ctx, query)


@bot.tree.command(name="dore", description="Gustave Doré's engravings for the Bible, Dante and Milton")
@discord.app_commands.describe(query="A passage (Genesis 7, Inferno 3, Paradise Lost 1), a name, or 'list'; empty for a random one")
async def dore_slash(interaction: discord.Interaction, query: str = ""):
    await interaction.response.defer()
    await send_dore(await bot.get_context(interaction), query)
