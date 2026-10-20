"""
!fable -- one of Aesop's Fables, in George Fyler Townsend's translation (1867): 313 fables
(data/classical/aesop.json, built by scripts/build_aesop.py), one chapter a fable.

    !fable                  a fable at random
    !fable fox              one with the fox in its title (else one that mentions it)
    !fable lion and mouse   by its title
    !fable 12               by number
    !fable list             all the titles, a page at a time

🎲 Another draws again from the same kind; 🖼️ Card makes an image of the fable, set justified like a
printed book (a Discord message can't be).
"""
import asyncio
import functools
import random
import re
import unicodedata

import discord

from bot_commands import card
from core import bot, log, lookup, tradition_enabled

BOOK = "Aesop's Fables"
SOURCE = "trans. George Fyler Townsend (1867)"
COLOR = discord.Color.from_rgb(150, 110, 60)
LIST_PAGE = 40
STOP = {"the", "and", "a", "an", "of", "his", "her", "its", "in", "on", "to", "with"}
# what people call them now -> Townsend's word (!fable donkey finds The Ass and the Grasshopper)
SAME = {"donkey": "ass", "donkeys": "asses"}


def _fold(text: str) -> str:
    return unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()


@functools.lru_cache(maxsize=1)
def fables() -> dict:
    """{"1": {"1": "*The Lion and the Mouse*\\nA LION...", "2": ...}}, or {} if the book isn't loaded."""
    for corpus in lookup._data.values():
        if BOOK in corpus:
            return corpus[BOOK]
    return {}


def title(n: int) -> str:
    m = re.match(r"\*([^*\n]+)\*", fables()[str(n)]["1"])
    return m.group(1) if m else f"Fable {n}"


def body(n: int) -> str:
    """The fable's paragraphs, without the title that leads the first."""
    paras = list(fables()[str(n)].values())
    paras[0] = re.sub(r"^\*[^*\n]+\*\n", "", paras[0])
    return "\n\n".join(paras)


def _significant(text: str) -> list:
    return [SAME.get(w, w) for w in re.findall(r"[a-z]+", _fold(text)) if w not in STOP]


def numbers() -> list:
    return sorted(map(int, fables()), key=int)


def pool(spec: str) -> list:
    """The fables a filter allows: "" all; "t:words" those with the words in the title; "w:words" in the text."""
    kind, _, arg = spec.partition(":")
    words = _significant(arg)
    if kind == "t":
        found = [n for n in numbers() if all(re.search(rf"\b{re.escape(w)}", _fold(title(n))) for w in words)]
        exact = [n for n in found if _significant(title(n)) == words]       # "lion and mouse": not the Fox one
        return exact or found
    if kind == "w":
        return [n for n in numbers()
                if all(re.search(rf"\b{re.escape(w)}", _fold(title(n) + " " + body(n))) for w in words)]
    return numbers()


def parse(query: str) -> "tuple[str, str]":
    """(filter spec, how it was read) for what follows !fable: the title first, else the text."""
    q = query.strip()[:60]
    if not q:
        return "", ""
    if not [w for w in _fold(q).split() if w not in STOP]:
        return f"w:{q}", f"with “{q}”"
    if pool(f"t:{q}"):
        return f"t:{q}", f"“{q}”"
    return f"w:{q}", f"with “{q}”"


# ── showing ─────────────────────────────────────────────────────────────────

class FableButton(discord.ui.DynamicItem[discord.ui.Button],
                  template=r"fable:(?P<action>again|card|list):(?P<n>\d+):(?P<spec>.{0,70})"):
    """🎲 another of the same kind, 🖼️ the fable as a card, ◀ ▶ through the list of titles. The custom_id
    carries what it needs, so these keep working after a restart."""

    def __init__(self, action, n, spec, label="", emoji=""):
        super().__init__(discord.ui.Button(label=label or None, emoji=emoji or None, style=discord.ButtonStyle.secondary,
                                           custom_id=f"fable:{action}:{n}:{spec}"[:100]))
        self.action, self.n, self.spec = action, int(n), spec

    @classmethod
    async def from_custom_id(cls, interaction, item, match):
        return cls(match["action"], match["n"], match["spec"])

    async def callback(self, interaction: discord.Interaction):
        if self.action == "again":
            found = pool(self.spec)
            if not found:
                await interaction.response.send_message("I can't find another fable like that.", ephemeral=True)
                return
            await interaction.response.send_message(**message(random.choice(found), spec=self.spec))
        elif self.action == "card":
            await interaction.response.defer(thinking=True)
            buf = await asyncio.to_thread(render_card, self.n)
            await interaction.followup.send(file=discord.File(buf, filename=f"fable-{self.n}.png"))
        else:                                                  # list: n is the page
            await interaction.response.edit_message(**list_message(self.n))


bot.add_dynamic_items(FableButton)


def message(n: int, spec: str = "", heading: str = "") -> dict:
    embed = discord.Embed(title=f"🦊 {title(n)}", description=body(n), color=COLOR)
    if heading:
        embed.set_author(name=heading[:256])
    embed.set_footer(text=f"Aesop's Fables, no. {n} · {SOURCE}")
    view = discord.ui.View(timeout=None)
    view.add_item(FableButton("again", n, spec, label="Another", emoji="🎲"))
    view.add_item(FableButton("card", n, spec, label="Card", emoji="🖼️"))
    return {"embed": embed, "view": view}


def render_card(n: int):
    """The fable as a PNG card, justified, in the classical style."""
    return card._render_verse_card(title(n), body(n), f"Aesop's Fables, no. {n} · {SOURCE}",
                                   style="classical", justify=True)


def list_message(page: int = 0) -> dict:
    ns = numbers()
    pages = max(1, -(-len(ns) // LIST_PAGE))
    page %= pages
    shown = ns[page * LIST_PAGE:(page + 1) * LIST_PAGE]
    embed = discord.Embed(title="🦊 Aesop's Fables", description="\n".join(f"`{n}` {title(n)}" for n in shown),
                          color=COLOR)
    embed.set_footer(text=f"Page {page + 1} of {pages} · !fable 12 or !fable fox · {SOURCE}")
    view = discord.ui.View(timeout=None)
    view.add_item(FableButton("list", (page - 1) % pages, "back", emoji="◀"))     # ("back"/"next" keep the
    view.add_item(FableButton("list", (page + 1) % pages, "next", emoji="▶"))     #  ids apart on two pages)
    return {"embed": embed, "view": view}


async def send_fable(ctx, query: str = "") -> None:
    if not fables():
        await ctx.send("⚠️ Aesop's Fables aren't loaded.")
        return
    guild = getattr(ctx, "guild", None)
    if not tradition_enabled(guild.id if guild else None, "classical"):
        await ctx.send("Aesop's Fables are among the Greek and Roman texts, which this server has turned off.")
        return
    q = query.strip()
    if _fold(q) in ("list", "all", "titles", "index", "contents"):
        await ctx.send(**list_message(0))
        return
    if re.fullmatch(r"#?\d{1,4}", q):
        n = int(q.lstrip("#"))
        if str(n) not in fables():
            await ctx.send(f"The fables are numbered 1 to {max(numbers())}.")
            return
        await ctx.send(**message(n))
        return
    spec, label = parse(q)
    found = pool(spec)
    if not found:
        await ctx.send(f"I found no fable {label}. Try `!fable list`, or just `!fable`." if label
                       else "I couldn't find a fable.")
        return
    n = random.choice(found)
    log.info(f"RNG  fable {spec or 'any':24} → {n} (user: {ctx.author})")
    heading = "" if not label or len(found) == 1 else f"A fable {label} ({len(found)} like it)"
    await ctx.send(**message(n, spec=spec, heading=heading))


@bot.command(name="fable", aliases=["aesop", "fables"])
async def cmd_fable(ctx, *, query: str = ""):
    """One of Aesop's Fables (Townsend's translation).
    Usage: !fable              — one at random
           !fable fox          — one with the fox in its title
           !fable lion mouse   — by its title
           !fable 12           — by number
           !fable list         — all the titles"""
    await send_fable(ctx, query)
