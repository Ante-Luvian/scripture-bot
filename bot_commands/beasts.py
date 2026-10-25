"""
Two medieval books of beasts (scripts/build_beasts.py):

!physiologus -- the Physiologus, the early Christian book of what beasts do and what it means (the lion's cubs
woken on the third day, the pelican's blood), in Mladenova and Stoykov's English (data/medieval/physiologus.json).
    !physiologus             a beast at random
    !physiologus pelican     by the beast
    !physiologus 19          by chapter
    !physiologus list        the beasts

!reynard -- Reynard the Fox, Caxton's translation (1481) in Morley's modern spelling (data/ballads/reynard.json).
    !reynard                 the first chapter (!reynard 12 another; !reynard list the chapters)
    !reynard tybert          the first chapter whose heading names him

◀ ▶ turn a long chapter's pages; ⏮ ⏭ go to the chapter before or after; 🎲 another beast.
"""
import functools
import random
import re
import unicodedata

import discord

from core import bot, log, lookup, tradition_enabled
from scripture_lookup import CORPUS_TRADITION

PAGE = 1500                                          # characters a page, never splitting a paragraph
# key -> (book, emoji, colour, footer source, the word for its parts)
BOOKS = {
    "ph": ("Physiologus", "🦁", discord.Color.from_rgb(120, 90, 40),
           "trans. Olga M. Mladenova and Vesselin Stoykov, from Ana Stoykova's", "beast"),
    "rf": ("Reynard the Fox", "🦊", discord.Color.from_rgb(170, 80, 30),
           "Caxton's translation (1481), ed. Henry Morley (1889)", "chapter"),
}
STOP = {"the", "a", "an", "of", "and", "about", "how", "in", "to", "he", "his", "who", "is", "what", "or", "with",
        "lives", "like", "other", "words"}


def _fold(text: str) -> str:
    return unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()


@functools.lru_cache(maxsize=None)
def _where(key: str) -> "tuple[str, dict]":
    for corpus, books in lookup._data.items():
        if BOOKS[key][0] in books:
            return corpus, books[BOOKS[key][0]]
    return "", {}


def chapters(key: str) -> dict:
    return _where(key)[1]


def numbers(key: str) -> list:
    return sorted(map(int, chapters(key)))


def title(key: str, n: int) -> str:
    m = re.match(r"\*([^*\n]+)\*", chapters(key)[str(n)]["1"])
    return m.group(1) if m else f"{BOOKS[key][4].title()} {n}"


def name(key: str, n: int) -> str:
    """The beast a Physiologus chapter is about ("About the Lion, the King of Beasts" -> "the Lion")."""
    t = title(key, n)
    if key == "ph":
        t = re.sub(r"^About\s+", "", t)
        t = re.split(r"[,.;(]", t)[0].strip()
        t = t[:1].upper() + t[1:]
    return t


def pages(key: str, n: int) -> list:
    paras = list(chapters(key)[str(n)].values())
    paras[0] = re.sub(r"^\*[^*\n]+\*\n", "", paras[0])
    out, page = [], ""
    for p in paras:
        while len(p) > PAGE:                            # (a paragraph longer than a page: at its sentences)
            cut = max(p.rfind(". ", 0, PAGE), p.rfind("” ", 0, PAGE), p.rfind("? ", 0, PAGE))
            cut = cut + 1 if cut > PAGE // 3 else p.rfind(" ", 0, PAGE)
            if page:
                out.append(page)
                page = ""
            out.append(p[:cut].strip())
            p = p[cut:].strip()
        if page and len(page) + len(p) + 2 > PAGE:
            out.append(page)
            page = ""
        page = f"{page}\n\n{p}" if page else p
    return out + [page] if page else out or [""]


def find(key: str, query: str) -> list:
    """The chapters whose heading has all the words ("pelican"; "tybert"; "frog"), in order."""
    words = [w for w in re.findall(r"[a-z]+", _fold(query)) if w not in STOP]
    if not words:
        return []
    def has(n):
        heading = set(re.findall(r"[a-z]+", _fold(title(key, n))))
        return all(any(h.startswith(w) or w.startswith(h) and len(h) > 3 for h in heading) for w in words)
    return [n for n in numbers(key) if has(n)]


# ── showing ─────────────────────────────────────────────────────────────────

class BeastButton(discord.ui.DynamicItem[discord.ui.Button],
                  template=r"beast:(?P<key>ph|rf):(?P<action>back|next|prev|after|again|list):(?P<n>\d+):(?P<page>\d+)"):
    """◀ ▶ a chapter's pages, ⏮ ⏭ the chapter before or after, 🎲 another, ◀ ▶ the list (n: its page). The
    custom_id carries all it needs, so they keep working after a restart."""

    def __init__(self, key, action, n, page=0, label="", emoji=""):
        super().__init__(discord.ui.Button(label=label or None, emoji=emoji or None, style=discord.ButtonStyle.secondary,
                                           custom_id=f"beast:{key}:{action}:{n}:{page}"))
        self.key, self.action, self.n, self.page = key, action, int(n), int(page)

    @classmethod
    async def from_custom_id(cls, interaction, item, match):
        return cls(match["key"], match["action"], match["n"], match["page"])

    async def callback(self, interaction: discord.Interaction):
        if self.action == "list":
            await interaction.response.edit_message(**list_message(self.key, self.page))
        elif str(self.n) not in chapters(self.key):
            await interaction.response.send_message("⚠️ I can't find that any more.", ephemeral=True)
        elif self.action == "again":
            others = [m for m in numbers(self.key) if m != self.n]
            await interaction.response.send_message(**message(self.key, random.choice(others)))
        else:
            await interaction.response.edit_message(**message(self.key, self.n, self.page))


bot.add_dynamic_items(BeastButton)


def message(key: str, n: int, page: int = 0, heading: str = "") -> dict:
    book, emoji, color, source, part = BOOKS[key]
    texts = pages(key, n)
    page %= len(texts)
    shown = name(key, n) if key == "ph" else title(key, n)
    if key == "rf":
        shown = f"{n}. {shown}"
    embed = discord.Embed(title=f"{emoji} {shown}"[:256], description=texts[page], color=color)
    if heading:
        embed.set_author(name=heading[:256])
    where = f" · page {page + 1} of {len(texts)}" if len(texts) > 1 else ""
    embed.set_footer(text=f"{book}, {part} {n} of {len(numbers(key))}{where} · {source}")
    view = discord.ui.View(timeout=None)                # persistent buttons: must never time out
    ns = numbers(key)
    if len(texts) > 1:
        view.add_item(BeastButton(key, "back", n, (page - 1) % len(texts), emoji="◀"))
        view.add_item(BeastButton(key, "next", n, (page + 1) % len(texts), emoji="▶"))
    i = ns.index(n)
    if key == "rf":
        if i > 0:
            view.add_item(BeastButton(key, "prev", ns[i - 1], label="Chapter before", emoji="⏮"))
        if i + 1 < len(ns):
            view.add_item(BeastButton(key, "after", ns[i + 1], label="Next chapter", emoji="⏭"))
    else:
        view.add_item(BeastButton(key, "again", n, label="Another beast", emoji="🎲"))
    return {"embed": embed, "view": view}


def list_message(key: str, page: int = 0) -> dict:
    book, emoji, color, source, part = BOOKS[key]
    ns = numbers(key)
    per = 40
    count = max(1, -(-len(ns) // per))
    page %= count
    lines = [f"`{n}` {name(key, n) if key == 'ph' else title(key, n)}" for n in ns[page * per:(page + 1) * per]]
    embed = discord.Embed(title=f"{emoji} {book}", description="\n".join(lines)[:4096], color=color)
    cmd = "!physiologus pelican" if key == "ph" else "!reynard 12"
    embed.set_footer(text=f"Page {page + 1} of {count} · {cmd} · {source}")
    view = discord.ui.View(timeout=None)
    if count > 1:
        view.add_item(BeastButton(key, "list", 0, (page - 1) % count, emoji="◀"))
        view.add_item(BeastButton(key, "list", 1, (page + 1) % count, emoji="▶"))   # (0/1: the ids apart)
    return {"embed": embed, "view": view}


async def send_beast(ctx, key: str, query: str = "") -> None:
    book, _, _, _, part = BOOKS[key]
    if not chapters(key):
        await ctx.send(f"⚠️ {book} isn't loaded.")
        return
    guild = getattr(ctx, "guild", None)
    tradition = CORPUS_TRADITION.get(_where(key)[0])
    if not tradition_enabled(guild.id if guild else None, tradition):
        await ctx.send(f"{book} is among the texts this server has turned off.")
        return
    q = query.strip()[:80]
    if _fold(q) in ("list", "all", "contents", "chapters", "beasts", "index"):
        await ctx.send(**list_message(key))
        return
    if re.fullmatch(r"#?\d{1,6}", q):
        n = int(q.lstrip("#"))
        if str(n) not in chapters(key):
            await ctx.send(f"{'The Physiologus' if key == 'ph' else book}'s {part}s are numbered 1 to {max(numbers(key))}.")
            return
        await ctx.send(**message(key, n))
        return
    if not q:
        n = random.choice(numbers(key)) if key == "ph" else numbers(key)[0]
        log.info(f"RNG  {key} → {n} (user: {ctx.author})")
        await ctx.send(**message(key, n))
        return
    found = find(key, q)
    if not found:
        what = "beast" if key == "ph" else "chapter heading naming"
        await ctx.send(f"I found no {what} “{discord.utils.escape_markdown(q)}” in {'the Physiologus' if key == 'ph' else book}. "
                       f"Try `!{'physiologus' if key == 'ph' else 'reynard'} list`.")
        return
    heading = f"{len(found)} {part}s for “{q}”; this is the first" if len(found) > 1 else ""
    await ctx.send(**message(key, found[0], heading=heading))


@bot.command(name="physiologus", aliases=["bestiary", "beast"])
async def cmd_physiologus(ctx, *, query: str = ""):
    """The Physiologus: what the beasts do, and what it means for a Christian.
    Usage: !physiologus            — a beast at random
           !physiologus pelican    — by the beast
           !physiologus 19         — by chapter
           !physiologus list       — the beasts"""
    await send_beast(ctx, "ph", query)


@bot.command(name="reynard", aliases=["reynart", "reynardthefox"])
async def cmd_reynard(ctx, *, query: str = ""):
    """Reynard the Fox, in Caxton's translation (1481).
    Usage: !reynard           — the first chapter
           !reynard 12        — a chapter
           !reynard tybert    — the first chapter whose heading names him
           !reynard list      — the chapters"""
    await send_beast(ctx, "rf", query)
