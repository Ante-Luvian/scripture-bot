"""
Pictures tied to passages: Gustave Doré's engravings for the Bible (with the Apocrypha), the
Divine Comedy and Paradise Lost (data/dore/plates.json, built by scripts/build_dore.py), and
William Blake's illustrations to Job, the Bible, Paradise Lost, The Pilgrim's Progress and the
Divine Comedy (data/blake/art.json, scripts/build_blake_art.py).

!dore shows Doré's (Blake's are in !blake, bot_commands/blake.py), and under !verse a 🖼️ Doré
and a 🎨 Blake button appear wherever a passage has one. The pictures are shown from Wikimedia.
"""
import functools
import json
import random
import re

import discord

from core import ROOT, bot, lookup

PLATES_PATH = ROOT / "data" / "dore" / "plates.json"
BLAKE_PATH = ROOT / "data" / "blake" / "art.json"
COLOR = discord.Color.from_rgb(60, 60, 70)
BLAKE_COLOR = discord.Color.from_rgb(150, 70, 30)
WORKS = {("dore", "bible"): "The Holy Bible (1866)", ("dore", "dante"): "The Divine Comedy (1861–68)",
         ("dore", "milton"): "Paradise Lost (1866)",
         ("blake", "job"): "Illustrations of the Book of Job (1826)", ("blake", "bible"): "paintings of the Bible (1799–1810)",
         ("blake", "pl"): "Paradise Lost (the Thomas set, 1807)", ("blake", "pp"): "The Pilgrim's Progress (1824–27)",
         ("blake", "dante"): "the Divine Comedy (1824–27)"}
ARTIST = {"dore": ("Gustave Doré", "🖼️", "Doré"), "blake": ("William Blake", "🎨", "Blake")}
REF = re.compile(r"^(?P<book>.+?) (?P<ch>\d+)(?::(?P<v1>\d+)(?:\s*[–-]\s*(?P<v2>\d+))?)?(?: \([^)]*\))?$")
MAX_SHOWN = 4
BLAKE_SETS = {"job": "j", "bible": "b", "pl": "l", "pp": "p", "dante": "d"}    # (for Blake's keys: "kj5", "kl9")


@functools.lru_cache(maxsize=1)
def _all() -> list:
    out, seen = [], set()
    for artist, path, field in (("dore", PLATES_PATH, "plates"), ("blake", BLAKE_PATH, "art")):
        if not path.exists():
            continue
        for p in json.loads(path.read_text(encoding="utf-8"))[field]:
            # short keys for button ids: Doré's "b026", "dinf3", "m12"; Blake's "kj5", "kb3", "kd12"
            key = (f"{p['set'][0]}{p['n']}" if artist == "dore" else f"k{BLAKE_SETS[p['set']]}{p['n']}").lower()
            while key in seen:                          # (two of Doré's plates share page 095, and 123)
                key += "x"
            seen.add(key)
            out.append({**p, "key": key, "artist": artist})
    return out


def plates(artist: str = "dore") -> list:
    return [p for p in _all() if p["artist"] == artist]


@functools.lru_cache(maxsize=1)
def by_key() -> dict:
    return {p["key"]: p for p in _all()}


def for_passage(book: str, chapter: int, start: "int | None" = None, end: "int | None" = None,
                artist: str = "dore") -> list:
    """The pictures of a passage (a whole chapter if no verses are given)."""
    hits = []
    for p in plates(artist):
        if p["book"] != book or p["chapter"] != chapter:
            continue
        if start is None or p["start"] is None or p["set"] == "dante":     # (Dante's are by canto)
            hits.append(p)
        elif p["start"] <= (end or start) and start <= p["end"]:
            hits.append(p)
    return hits


def for_result(result: dict, artist: str = "dore") -> list:
    """The pictures for a !verse result ("John 3:16", "Inferno 1:1–3", "Genesis 7")."""
    if not result.get("found"):
        return []
    m = REF.match(result.get("reference", ""))
    if not m:
        return []
    book = lookup._resolve_book(m["book"])[1] or m["book"]
    start = int(m["v1"]) if m["v1"] else None
    return for_passage(book, int(m["ch"]), start, int(m["v2"]) if m["v2"] else start, artist)


def plate_embed(p: dict) -> discord.Embed:
    name, emoji, _ = ARTIST[p["artist"]]
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
    embed = discord.Embed(title=f"{emoji} {title}", url=p["page"], description=description,
                          color=COLOR if p["artist"] == "dore" else BLAKE_COLOR)
    if read:
        embed.add_field(name="Read it", value=f"`{read}`", inline=False)
    embed.set_image(url=p["image"])
    embed.set_footer(text=f"{name}, {WORKS[(p['artist'], p['set'])]} · image: Wikimedia Commons")
    return embed


class ArtButton(discord.ui.DynamicItem[discord.ui.Button], template=r"(?P<artist>dore|blakeart):(?P<keys>[a-z0-9,]+)"):
    """🖼️ Doré / 🎨 Blake under a !verse result: the passage's pictures. The ids are in the
    custom_id, so it keeps working after a restart."""

    def __init__(self, artist: str, keys: list):
        _, emoji, label = ARTIST["dore" if artist == "dore" else "blake"]
        prefix = "dore" if artist == "dore" else "blakeart"
        super().__init__(discord.ui.Button(label=label, emoji=emoji, style=discord.ButtonStyle.secondary, row=2,
                                           custom_id=f"{prefix}:" + ",".join(keys)[:90]))
        self.artist, self.keys = prefix, keys

    @classmethod
    async def from_custom_id(cls, interaction, item, match):
        return cls(match["artist"], match["keys"].split(","))

    async def callback(self, interaction: discord.Interaction):
        shown = [by_key()[k] for k in self.keys if k in by_key()][:MAX_SHOWN]
        if not shown:
            await interaction.response.send_message("⚠️ I can't find that picture any more.", ephemeral=True)
            return
        await interaction.response.send_message(embeds=[plate_embed(p) for p in shown])


bot.add_dynamic_items(ArtButton)
DoreButton = ArtButton                                   # (its first name)


def art_buttons(result: dict) -> list:
    """The 🖼️ Doré and 🎨 Blake buttons for a passage that has their pictures."""
    out = []
    for artist, prefix in (("dore", "dore"), ("blake", "blakeart")):
        found = for_result(result, artist)
        if found:
            out.append(ArtButton(prefix, [p["key"] for p in found]))
    return out


def search(query: str, artist: str = "dore") -> list:
    words = [w for w in re.findall(r"[a-z]+", query.lower()) if len(w) > 2]
    return [p for p in plates(artist) if words and all(w in (p["title"] + " " + p.get("cited", "")).lower() for w in words)]


async def send_art(ctx, query: str, artist: str = "dore") -> bool:
    """A passage's pictures, a book's, or ones found by name; False (nothing sent) if there are none."""
    name = ARTIST[artist][0]
    q = query.strip()
    found = []
    m = REF.match(q)
    if m:
        book = lookup._resolve_book(m["book"])[1]
        if book:
            start = int(m["v1"]) if m["v1"] else None
            found = for_passage(book, int(m["ch"]), start, int(m["v2"]) if m["v2"] else start, artist)
    if not found:
        book = lookup._resolve_book(q)[1]
        if book:
            found = [p for p in plates(artist) if p["book"] == book]
    found = found or search(q, artist)
    if not found:
        return False
    extra = f"*{len(found)} pictures; here are the first {MAX_SHOWN}. Ask for a chapter to narrow it.*" \
        if len(found) > MAX_SHOWN else None
    await ctx.send(extra, embeds=[plate_embed(p) for p in found[:MAX_SHOWN]])
    return True


async def send_dore(ctx, query: str = "") -> None:
    if not plates():
        await ctx.send("⚠️ Doré's engravings aren't available right now.")
        return
    q = query.strip()
    if q.lower() in ("list", "all", "help", "index"):
        counts = {k: sum(1 for p in plates() if p["set"] == k) for k in ("bible", "dante", "milton")}
        await ctx.send(embed=discord.Embed(title="🖼️ Gustave Doré's engravings", color=COLOR, description=(
            f"**The Bible**, with the Apocrypha: {counts['bible']} plates\n"
            f"**The Divine Comedy**: {counts['dante']} plates\n"
            f"**Paradise Lost**: {counts['milton']} plates\n\n"
            "`!dore` — one at random\n"
            "`!dore Genesis 11` · `!dore Inferno 3` · `!dore Paradise Lost 1` — a passage's engravings\n"
            "`!dore babel` — by name\n\n"
            "Under `!verse`, a 🖼️ Doré button appears whenever the passage has one.")))
        return
    if not q:
        await ctx.send(embed=plate_embed(random.choice(plates())))
        return
    if await send_art(ctx, q, "dore"):
        return
    m = REF.match(q)
    book = lookup._resolve_book(m["book"])[1] if m else None
    if book:
        await ctx.send(f"Doré made no engraving for **{book} {m['ch']}" + (f":{m['v1']}" if m["v1"] else "")
                       + "**. `!dore list` shows what there is.")
    else:
        await ctx.send(f"I don't have a Doré engraving for **{discord.utils.escape_markdown(q)}**. "
                       f"Try `!dore Genesis 11`, `!dore Inferno 3` or `!dore list`.")


@bot.command(name="dore", aliases=["doré", "engraving", "engravings"])
async def cmd_dore(ctx, *, query: str = ""):
    """Gustave Doré's engravings for the Bible, Dante and Milton.
    Usage: !dore               — one at random
           !dore Genesis 11    — a passage's engravings (also Inferno 3, Paradise Lost 1)
           !dore babel         — by name · !dore list"""
    await send_dore(ctx, query)


@bot.tree.command(name="dore", description="Gustave Doré's engravings for the Bible, Dante and Milton")
@discord.app_commands.describe(query="A passage (Genesis 11, Inferno 3, Paradise Lost 1), a name, or 'list'; empty for a random one")
async def dore_slash(interaction: discord.Interaction, query: str = ""):
    await interaction.response.defer()
    await send_dore(await bot.get_context(interaction), query)
