"""
!blake -- William Blake's illuminated books, plate by plate (data/blake/plates.json, built by
scripts/build_blake_plates.py). Blake etched his words and pictures together on copper and
coloured every copy by hand; each book here is one copy, as Wikimedia Commons has it, and
the pictures are shown from Wikimedia. ◀ ▶ turn the plates. (Their words are in the
library too: !verse Songs of Experience 12, !verse Thel 1.)
"""
import functools
import json
import random
import re

import discord

from core import ROOT, bot

PLATES_PATH = ROOT / "data" / "blake" / "plates.json"
COLOR = discord.Color.from_rgb(150, 70, 30)
ALIASES = {"songs of innocence and of experience": "songs", "innocence and experience": "songs",
           "experience": "songs", "tyger": "songs", "mhh": "marriage", "heaven and hell": "marriage",
           "daughters of albion": "visions", "oothoon": "visions", "first book of urizen": "urizen",
           "all religions": "religion", "no natural religion": "natural", "and did those feet": "milton",
           "song of los": "songoflos"}


@functools.lru_cache(maxsize=1)
def books() -> dict:
    return json.loads(PLATES_PATH.read_text(encoding="utf-8"))["illuminated"] if PLATES_PATH.exists() else {}


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z ]", " ", text.lower())).strip()


def find(query: str) -> "str | None":
    q = _norm(query)
    if not q:
        return None
    if q in books():
        return q
    if ALIASES.get(q) in books():
        return ALIASES[q]
    for key, book in books().items():
        if q in (_norm(book["title"]), _norm(book["title"]).removeprefix("the ")):
            return key
    hits = [k for k, b in books().items() if q in _norm(b["title"])]
    return hits[0] if len(hits) == 1 else None


TEXTS_PATH = ROOT / "data" / "blake" / "plate_texts.json"


@functools.lru_cache(maxsize=1)
def texts() -> dict:
    """{book: [the words on each plate]} (scripts/build_blake_texts.py)."""
    return json.loads(TEXTS_PATH.read_text(encoding="utf-8"))["texts"] if TEXTS_PATH.exists() else {}


def plate_text(key: str, page: int) -> str:
    words = texts().get(key, [])
    return words[page] if page < len(words) else ""


def plate_message(key: str, page: int) -> dict:
    book = books()[key]
    plates = book["plates"]
    page %= len(plates)
    plate = plates[page]
    words = discord.utils.escape_markdown(plate_text(key, page))
    about = f"*{book['about']}*" if page == 0 else ""
    description = "\n\n".join(p for p in (about, words) if p)
    if len(description) > 4000:                         # (Discord: 4,096 to an embed's description)
        description = description[:description.rfind("\n", 0, 3990)] + "\n…"
    embed = discord.Embed(title=f"{book['title']} — plate {page + 1} of {len(plates)}", url=plate["page"],
                          color=COLOR, description=description or None)
    embed.set_image(url=plate["image"])
    embed.set_footer(text=f"William Blake, {book['year']} · copy {book['copy']} · image: Wikimedia Commons")
    view = discord.ui.View(timeout=None)                # persistent: must never time out
    view.add_item(PlateButton("back", key, (page - 1) % len(plates)))
    view.add_item(PlateButton("next", key, (page + 1) % len(plates)))
    return {"embed": embed, "view": view}


class PlateButton(discord.ui.DynamicItem[discord.ui.Button],
                  template=r"blake:(?P<action>back|next):(?P<key>[a-z]+):(?P<page>\d+)"):
    """◀ ▶ through a book's plates ("back" and "next" keep the custom_ids apart on a two-plate book)."""

    def __init__(self, action: str, key: str, page: int):
        super().__init__(discord.ui.Button(emoji="◀" if action == "back" else "▶", style=discord.ButtonStyle.secondary,
                                           custom_id=f"blake:{action}:{key}:{page}"))
        self.key, self.page = key, page

    @classmethod
    async def from_custom_id(cls, interaction, item, match):
        return cls(match["action"], match["key"], int(match["page"]))

    async def callback(self, interaction: discord.Interaction):
        if self.key not in books():
            await interaction.response.send_message("⚠️ I can't find that book any more.", ephemeral=True)
            return
        await interaction.response.edit_message(**plate_message(self.key, self.page))


bot.add_dynamic_items(PlateButton)


def list_embed() -> discord.Embed:
    embed = discord.Embed(title="🎨 William Blake's illuminated books", color=COLOR, description=(
        "Blake etched his poems and pictures together on copper, printed them himself and coloured each "
        "copy by hand, so no two copies are alike.\n\n" + "\n".join(
            f"• **{b['title']}** ({b['year']}) — {len(b['plates'])} plates · `!blake {k}`" for k, b in books().items())))
    embed.add_field(name="And his illustrations of other books", value=(
        "The Book of Job (`!blake Job 38`), the Bible (`!blake Revelation 12`), the Divine Comedy (`!blake Inferno 5`), "
        "Paradise Lost (`!blake Paradise Lost 9`) and The Pilgrim's Progress (`!blake Pilgrim's Progress 4`). "
        "Under `!verse`, a 🎨 Blake button appears whenever the passage has one."), inline=False)
    embed.set_footer(text="!blake <book> <plate> · !blake on its own: a plate at random")
    return embed


async def send_blake(ctx, query: str = "") -> None:
    if not books():
        await ctx.send("⚠️ Blake's books aren't available right now.")
        return
    q = query.strip()
    if q.lower() in ("list", "all", "books", "index"):
        await ctx.send(embed=list_embed())
        return
    if not q:
        key = random.choice(list(books()))
        await ctx.send(**plate_message(key, random.randrange(len(books()[key]["plates"]))))
        return
    m = re.match(r"^(.*?)\s+(?:plate\s+)?(\d+)$", q, re.I)
    name, plate = (m.group(1), int(m.group(2))) if m else (q, 1)
    key = find(name)
    if key is None:
        # not one of his illuminated books: his illustrations of a passage ("Job 38", "Inferno 5", "Paradise Lost 9")
        from bot_commands.dore import send_art
        if await send_art(ctx, q, "blake"):
            return
        await ctx.send(f"I don't have a Blake book or picture for **{discord.utils.escape_markdown(q)}**. "
                       f"`!blake list` shows his illuminated books; `!blake Job 38` or `!blake Inferno 5` his illustrations.")
        return
    count = len(books()[key]["plates"])
    if not 1 <= plate <= count:
        await ctx.send(f"**{books()[key]['title']}** has {count} plates.")
        return
    await ctx.send(**plate_message(key, plate - 1))


@bot.command(name="blake", aliases=["illuminated", "blakeplate"])
async def cmd_blake(ctx, *, query: str = ""):
    """William Blake's illuminated books, plate by plate.
    Usage: !blake               — a plate at random
           !blake songs 42      — a book, at a plate (`!blake list` for the books)"""
    await send_blake(ctx, query)


@bot.tree.command(name="blake", description="William Blake's illuminated books, plate by plate")
@discord.app_commands.describe(book="A book (songs, thel, marriage, urizen, jerusalem…) or 'list'; empty for a random plate",
                               plate="Which plate (default: the first)")
async def blake_slash(interaction: discord.Interaction, book: str = "", plate: int = 0):
    await interaction.response.defer()
    await send_blake(await bot.get_context(interaction), f"{book} {plate}".strip() if book and plate else book)
