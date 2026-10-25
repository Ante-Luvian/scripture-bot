"""
!tale -- one of the Brothers Grimm's Household Tales, in Margaret Hunt's translation (1884): the 200 tales and the
ten Children's Legends (201-210) (data/ballads/grimm.json, built by scripts/build_grimm.py), one chapter a tale.

    !tale                    a tale at random
    !tale wolf               one with the wolf in its title (else one that mentions it)
    !tale hansel and grethel by its title (Gretel, Snow White and the like are found too)
    !tale 12                 by number
    !tale list               all the titles, a page at a time

◀ ▶ turn a long tale's pages (The Two Brothers runs to 30); 🎲 Another draws again from the same kind.
"""
import functools
import random
import re
import unicodedata

import discord

from core import bot, log, lookup, tradition_enabled

BOOK = "Grimm's Household Tales"
SOURCE = "trans. Margaret Hunt (1884)"
COLOR = discord.Color.from_rgb(70, 100, 60)
PAGE = 1500                                            # characters a page, never splitting a paragraph
LIST_PAGE = 40
STOP = {"the", "and", "a", "an", "of", "his", "her", "its", "in", "on", "to", "with", "or", "who"}
# what the tales are called now -> Hunt's spelling (!tale hansel and gretel finds Hansel and Grethel)
SAME = {"gretel": "grethel", "hulda": "holle", "rumplestiltskin": "rumpelstiltskin", "rumpelstilzchen": "rumpelstiltskin"}
# and the names they're best known by now, where Hunt's title is another (!tale sleeping beauty)
NAMES = {"little red riding hood": 26, "red riding hood": 26, "sleeping beauty": 50, "snow white": 53,
         "frog prince": 1, "elves and the shoemaker": 39, "shoemaker and the elves": 39, "tom thumb": 37,
         "twelve dancing princesses": 133, "dancing princesses": 133, "brave little tailor": 20, "iron hans": 136,
         "mother hulda": 24, "bremen town musicians": 27, "town musicians of bremen": 27}


def _fold(text: str) -> str:
    return unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()


@functools.lru_cache(maxsize=1)
def tales() -> dict:
    """{"12": {"1": "*Rapunzel*\\nThere were once...", ...}, ...}, or {} if the book isn't loaded."""
    return lookup._data.get("ballads", {}).get(BOOK, {})


def title(n: int) -> str:
    m = re.match(r"\*([^*\n]+)\*", tales()[str(n)]["1"])
    return m.group(1) if m else f"Tale {n}"


def label(n: int) -> str:
    """"no. 12", or "Children's Legend 3" for 203."""
    return f"Children's Legend {n - 200}" if n > 200 else f"no. {n}"


def paragraphs(n: int) -> list:
    paras = list(tales()[str(n)].values())
    paras[0] = re.sub(r"^\*[^*\n]+\*\n", "", paras[0])
    return paras


def pages(n: int) -> list:
    out, page = [], ""
    pieces = []
    for p in paragraphs(n):                             # (a paragraph longer than a page: at its sentences)
        while len(p) > PAGE:
            cut = max(p.rfind(". ", 0, PAGE), p.rfind("” ", 0, PAGE), p.rfind("? ", 0, PAGE), p.rfind("! ", 0, PAGE))
            cut = cut + 1 if cut > PAGE // 3 else p.rfind(" ", 0, PAGE)
            pieces.append(p[:cut].strip())
            p = p[cut:].strip()
        pieces.append(p)
    for p in pieces:
        if page and len(page) + len(p) + 2 > PAGE:
            out.append(page)
            page = ""
        page = f"{page}\n\n{p}" if page else p
    return out + [page] if page else out or [""]


def _significant(text: str) -> list:
    return [SAME.get(w, w) for w in re.findall(r"[a-z]+", _fold(text)) if w not in STOP]


def numbers() -> list:
    return sorted(map(int, tales()))


def pool(spec: str) -> list:
    """The tales a filter allows: "" all; "t:words" those with the words in the title; "w:words" in the text."""
    kind, _, arg = spec.partition(":")
    words = _significant(arg)
    if kind == "t":
        found = [n for n in numbers() if all(re.search(rf"\b{re.escape(w)}", _fold(title(n))) for w in words)]
        exact = [n for n in found if _significant(title(n)) == words]
        return exact or found
    if kind == "w":
        return [n for n in numbers()
                if all(re.search(rf"\b{re.escape(w)}", _fold(" ".join(tales()[str(n)].values()))) for w in words)]
    return numbers()


def parse(query: str) -> "tuple[str, str]":
    """(filter spec, how it was read): the title first, else the text."""
    q = query.strip()[:60]
    if not q:
        return "", ""
    if not _significant(q):
        return f"w:{q}", f"with “{q}”"
    if pool(f"t:{q}"):
        return f"t:{q}", f"with “{q}” in its title"
    return f"w:{q}", f"with “{q}”"


# ── showing ─────────────────────────────────────────────────────────────────

class TaleButton(discord.ui.DynamicItem[discord.ui.Button],
                 template=r"tale:(?P<action>back|next|again|list):(?P<n>\d+):(?P<arg>\d+):(?P<spec>.{0,70})"):
    """◀ ▶ a tale's pages (arg: the page), 🎲 another of the same kind, ◀ ▶ the list (arg: the page). The
    custom_id carries what it needs, so they keep working after a restart."""

    def __init__(self, action, n, arg, spec="", label="", emoji=""):
        super().__init__(discord.ui.Button(label=label or None, emoji=emoji or None, style=discord.ButtonStyle.secondary,
                                           custom_id=f"tale:{action}:{n}:{arg}:{spec}"[:100]))
        self.action, self.n, self.arg, self.spec = action, int(n), int(arg), spec

    @classmethod
    async def from_custom_id(cls, interaction, item, match):
        return cls(match["action"], match["n"], match["arg"], match["spec"])

    async def callback(self, interaction: discord.Interaction):
        if self.action == "list":
            await interaction.response.edit_message(**list_message(self.arg))
        elif self.action == "again":
            await interaction.response.send_message(**another(self.n, self.spec))
        elif str(self.n) not in tales():
            await interaction.response.send_message("⚠️ I can't find that tale any more.", ephemeral=True)
        else:
            await interaction.response.edit_message(**message(self.n, self.spec, page=self.arg))


bot.add_dynamic_items(TaleButton)


def message(n: int, spec: str = "", heading: str = "", page: int = 0) -> dict:
    texts = pages(n)
    page %= len(texts)
    embed = discord.Embed(title=f"🏰 {title(n)}"[:256], description=texts[page], color=COLOR)
    if heading:
        embed.set_author(name=heading[:256])
    where = f" · page {page + 1} of {len(texts)}" if len(texts) > 1 else ""
    embed.set_footer(text=f"Grimm's Household Tales, {label(n)}{where} · {SOURCE}")
    view = discord.ui.View(timeout=None)                # persistent buttons: must never time out
    if len(texts) > 1:
        view.add_item(TaleButton("back", n, (page - 1) % len(texts), spec, emoji="◀"))
        view.add_item(TaleButton("next", n, (page + 1) % len(texts), spec, emoji="▶"))
    view.add_item(TaleButton("again", n, 0, spec, label="Another", emoji="🎲"))
    return {"embed": embed, "view": view}


def another(n: int, spec: str) -> dict:
    """🎲: a different tale of the same kind; when this was the only one, say so and give a random one."""
    others = [m for m in pool(spec) if m != n]
    if others:
        return message(random.choice(others), spec=spec)
    asked = spec.partition(":")[2]
    sorry = (f"Sorry, that's the only tale with “{asked}”. Here's a random tale instead." if asked
             else "Here's a random tale instead.")
    return message(random.choice([m for m in numbers() if m != n]), heading=sorry)


def list_message(page: int = 0) -> dict:
    ns = numbers()
    count = max(1, -(-len(ns) // LIST_PAGE))
    page %= count
    shown = ns[page * LIST_PAGE:(page + 1) * LIST_PAGE]
    lines = [f"`{n}` {title(n)}" + (" *(a children's legend)*" if n > 200 else "") for n in shown]
    embed = discord.Embed(title="🏰 Grimm's Household Tales", description="\n".join(lines), color=COLOR)
    embed.set_footer(text=f"Page {page + 1} of {count} · !tale 12 or !tale wolf · {SOURCE}")
    view = discord.ui.View(timeout=None)
    view.add_item(TaleButton("list", 0, (page - 1) % count, "back", emoji="◀"))   # ("back"/"next" keep the
    view.add_item(TaleButton("list", 0, (page + 1) % count, "next", emoji="▶"))   #  ids apart on two pages)
    return {"embed": embed, "view": view}


async def send_tale(ctx, query: str = "") -> None:
    if not tales():
        await ctx.send("⚠️ The Grimms' tales aren't loaded.")
        return
    guild = getattr(ctx, "guild", None)
    if not tradition_enabled(guild.id if guild else None, "ballads"):
        await ctx.send("The folk tales and ballads are turned off on this server.")
        return
    q = query.strip()
    if _fold(q) in ("list", "all", "titles", "index", "contents"):
        await ctx.send(**list_message(0))
        return
    if re.fullmatch(r"#?\d{1,6}", q):
        n = int(q.lstrip("#"))
        if str(n) not in tales():
            await ctx.send(f"The tales are numbered 1 to 200, and the Children's Legends 201 to 210.")
            return
        await ctx.send(**message(n))
        return
    phrase = " ".join(w for w in re.findall(r"[a-z]+", _fold(q)) if w != "the")
    if NAMES.get(phrase):
        n = NAMES[phrase]
        await ctx.send(**message(n, heading=f"“{q}” is {title(n)}, as Margaret Hunt calls it"))
        return
    spec, how = parse(q)
    found = pool(spec)
    if not found:
        await ctx.send(f"I found no tale {how}. Try `!tale list`, or just `!tale`." if how
                       else "I couldn't find a tale.")
        return
    n = random.choice(found)
    log.info(f"RNG  tale {spec or 'any':24} → {n} (user: {ctx.author})")
    heading = "" if not how or len(found) == 1 else f"A tale {how} ({len(found)} like it)"
    await ctx.send(**message(n, spec=spec, heading=heading))


@bot.command(name="tale", aliases=["grimm", "fairytale", "tales"])
async def cmd_tale(ctx, *, query: str = ""):
    """One of the Brothers Grimm's Household Tales (Margaret Hunt's translation).
    Usage: !tale              — one at random
           !tale wolf         — one with the wolf in its title
           !tale rapunzel     — by its title
           !tale 12           — by number
           !tale list         — all the titles"""
    await send_tale(ctx, query)
