"""
!tarot -- the Rider tarot of 1909 (data/tarot/, built by scripts/build_tarot.py): Pamela
Colman Smith's pictures, with A. E. Waite's own account of each card from his Pictorial Key
to the Tarot (1911). Draw a card, ask for one by name, or lay a spread: three cards, or
Waite's ten-card "Ancient Celtic Method".
"""
import functools
import io
import json
import random
import re

import discord
from PIL import Image

from core import ROOT, bot

TAROT_DIR = ROOT / "data" / "tarot"
COLOR = discord.Color.from_rgb(120, 60, 140)
SOURCE = "Rider tarot (1909), drawn by Pamela Colman Smith · words: A. E. Waite, The Pictorial Key to the Tarot (1911)"

NO_REVERSED = "*Waite gives no reversed meaning for this card.*"
THREE = ["The past", "The present", "The future"]
# Waite's "Ancient Celtic Method of Divination" (Pictorial Key, Part III § 7), in the order he lays them
CELTIC = ["What covers him: the influence at work", "What crosses him: the obstacles",
          "What crowns him: the best that can be achieved", "What is beneath him: the foundation",
          "What is behind him: what has just passed", "What is before him: what is coming",
          "Himself: the questioner's attitude", "His house: those around him", "His hopes and fears",
          "What will come: the outcome"]

WORDS = {"ace": 1, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8,
         "nine": 9, "ten": 10, "page": 11, "knave": 11, "knight": 12, "queen": 13, "king": 14}
SUIT_NAMES = {"wands": "Wands", "wand": "Wands", "rods": "Wands", "rod": "Wands", "staves": "Wands", "batons": "Wands",
              "cups": "Cups", "cup": "Cups", "chalices": "Cups", "swords": "Swords", "sword": "Swords",
              "pentacles": "Pentacles", "pentacle": "Pentacles", "coins": "Pentacles", "coin": "Pentacles",
              "disks": "Pentacles", "discs": "Pentacles", "denarii": "Pentacles"}


@functools.lru_cache(maxsize=1)
def cards() -> list:
    path = TAROT_DIR / "cards.json"
    return json.loads(path.read_text(encoding="utf-8"))["cards"] if path.exists() else []


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]", " ", text.lower())).strip()


def find(query: str) -> "dict | None":
    """A card by name: "the magician", "magician", "13", "ten of wands", "10 cups", "queen of coins"."""
    q = _norm(query)
    if not q:
        return None
    for card in cards():
        if q in (_norm(card["name"]), _norm(card["name"]).removeprefix("the ")):
            return card
    if q.isdigit() and int(q) <= 21:                       # a trump by its number
        return cards()[int(q)]
    words = [w for w in q.split() if w != "of"]
    if len(words) == 2:
        rank = WORDS.get(words[0]) or (int(words[0]) if words[0].isdigit() else None)
        suit = SUIT_NAMES.get(words[1])
        if rank and suit:
            return next((c for c in cards() if c.get("suit") == suit and c["number"] == rank), None)
    alias = {"judgment": "judgement", "last judgement": "judgement", "wheel": "wheel of fortune",
             "fortitude": "strength", "pope": "the hierophant", "popess": "the high priestess"}.get(q)
    return find(alias) if alias else None


def card_file(card: dict, reversed_: bool, name: str) -> discord.File:
    path = TAROT_DIR / card["file"]
    if not reversed_:
        return discord.File(path, filename=name)
    buf = io.BytesIO()
    Image.open(path).rotate(180).save(buf, "JPEG", quality=85)
    buf.seek(0)
    return discord.File(buf, filename=name)


def _short(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    cut = text[:limit].rsplit(". ", 1)[0]
    return (cut if len(cut) > limit // 3 else text[:limit].rsplit(" ", 1)[0]).rstrip(".;,") + "…"


def card_embed(card: dict, reversed_: "bool | None" = None, position: str = "", filename: str = "",
               short: bool = False) -> discord.Embed:
    """reversed_ None: a card looked up (both meanings); True/False: a card drawn (its meaning only)."""
    title = card["name"] + (" (reversed)" if reversed_ else "")
    embed = discord.Embed(title=(f"{position} — " if position else "") + title, color=COLOR,
                          description=_short(card["description"], 160 if short else 1500))
    if reversed_ is None:
        embed.add_field(name="Upright", value=_short(card["upright"], 1000) or "—", inline=False)
        embed.add_field(name="Reversed", value=_short(card["reversed"], 1000) or NO_REVERSED, inline=False)
    else:
        meaning = (card["reversed"] or NO_REVERSED) if reversed_ else card["upright"]
        embed.add_field(name="Reversed, it means" if reversed_ else "It means",
                        value=_short(meaning, 260 if short else 1000) or "—", inline=False)
    embed.set_image(url=f"attachment://{filename or card['file']}")
    if not short:
        embed.set_footer(text=SOURCE)
    return embed


def draw(n: int, rng=random) -> list:
    """n different cards, each with whether it fell reversed."""
    return [(card, rng.random() < 0.5) for card in rng.sample(cards(), n)]


def list_embed() -> discord.Embed:
    embed = discord.Embed(title="🃏 The Rider tarot: 78 cards", color=COLOR, description=(
        "**The Major Arcana** (the trumps): " + ", ".join(f"{c['number']} {c['name']}" for c in cards()[:22])))
    for suit in ("Wands", "Cups", "Swords", "Pentacles"):
        embed.add_field(name=suit, value="Ace, Two … Ten, Page, Knight, Queen, King", inline=True)
    embed.set_footer(text="!tarot <card> · !tarot draws one · !tarot three · !tarot celtic")
    return embed


async def send_spread(ctx, positions: list, intro: str) -> None:
    drawn = draw(len(positions))
    embeds, files = [], []
    for i, ((card, rev), position) in enumerate(zip(drawn, positions), 1):
        name = f"card{i}.jpg"
        embeds.append(card_embed(card, rev, position, name, short=True))
        files.append(card_file(card, rev, name))
    embeds[-1].set_footer(text=SOURCE)
    await ctx.send(intro, embeds=embeds, files=files)


async def send_tarot(ctx, query: str = "") -> None:
    if not cards():
        await ctx.send("⚠️ The tarot isn't available right now.")
        return
    q = query.strip().lower()
    if q in ("list", "all", "cards", "deck"):
        await ctx.send(embed=list_embed())
    elif q in ("three", "3", "spread", "past present future"):
        await send_spread(ctx, THREE, "🃏 **Three cards: the past, the present and the future.**")
    elif q in ("celtic", "celtic cross", "ten", "10"):
        await send_spread(ctx, CELTIC, "🃏 **The Celtic Cross**, as Waite lays it in *The Pictorial Key to the Tarot*: "
                                       "the first card covers the question, the second crosses it, and the rest "
                                       "are laid around them.")
    elif not q or q in ("draw", "one", "card", "random"):
        card, rev = draw(1)[0]
        await ctx.send("🃏 **Your card**", embed=card_embed(card, rev), file=card_file(card, rev, card["file"]))
    else:
        card = find(q)
        if card is None:
            await ctx.send(f"I don't know a card called **{discord.utils.escape_markdown(query.strip())}**. "
                           f"Try `!tarot the tower`, `!tarot queen of cups`, or `!tarot list`.")
            return
        await ctx.send(embed=card_embed(card), file=card_file(card, False, card["file"]))


@bot.command(name="tarot", aliases=["taro", "riderwaite"])
async def cmd_tarot(ctx, *, query: str = ""):
    """The Rider tarot, with Waite's own meanings.
    Usage: !tarot              — draw a card
           !tarot the tower    — a card by name (`!tarot list` for them all)
           !tarot three        — past, present and future
           !tarot celtic       — Waite's ten-card Celtic Cross"""
    await send_tarot(ctx, query)


@bot.tree.command(name="tarot", description="The Rider tarot: draw a card, look one up, or lay a spread")
@discord.app_commands.describe(card="A card's name (the tower, queen of cups), 'three', 'celtic' or 'list'; empty to draw one")
async def tarot_slash(interaction: discord.Interaction, card: str = ""):
    await interaction.response.defer()
    await send_tarot(await bot.get_context(interaction), card)
