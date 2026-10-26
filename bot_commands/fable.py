"""
!fable -- fables from the world's collections: Aesop (Townsend's translation, 1867: 313 fables), Phaedrus (Riley,
1887), La Fontaine (Thornbury's verse, 1886), and The Talking Beasts (1911): Bidpai, the Hitopadesa, India, Malaya,
the Moors, Africa, Krylov, China, Yriarte, Gay and Cowper. One chapter a fable in each book
(data/classical/aesop.json, phaedrus.json; data/ballads/la_fontaine.json, talking_beasts.json).

    !fable                    a fable at random, from any collection
    !fable fox                one with the fox in its title (else one that mentions it)
    !fable lion and mouse     by its title
    !fable 12                 Aesop's by number
    !fable la fontaine        one of La Fontaine's (and !fable krylov wolf, !fable phaedrus 3)
    !fable list               Aesop's titles, a page at a time (!fable la fontaine list for his)
    !fable collections        the collections

🎲 Another draws again from the same kind; ◀ ▶ turn a long fable's pages; 🖼️ Card makes an image of a short prose
fable, set justified like a printed book (a Discord message can't be).
"""
import asyncio
import functools
import random
import re
import unicodedata

import discord

from bot_commands import card, illustrations
from core import bot, log, lookup, tradition_enabled
from scripture_lookup import CORPUS_TRADITION

# code (in the buttons' ids: "" for Aesop, as before) -> (book, short name, what to call for it)
COLLECTIONS = {
    "": ("Aesop's Fables", "Aesop", ["aesop", "aesops"]),
    "ph": ("Fables of Phaedrus", "Phaedrus", ["phaedrus", "phaedrus's", "phaedrus'"]),
    "lf": ("Fables of La Fontaine", "La Fontaine", ["la fontaine", "lafontaine", "fontaine"]),
    "bi": ("Fables of Bidpai", "Bidpai", ["bidpai", "pilpay", "panchatantra", "kalila"]),
    "hi": ("Fables from the Hitopadesa", "the Hitopadesa", ["hitopadesa", "hitopadesha"]),
    "in": ("Fables from India", "India", ["india", "indian"]),
    "ma": ("Malayan Fables", "Malaya", ["malayan", "malay", "malaya"]),
    "mo": ("Moorish Fables", "the Moors", ["moorish", "moor", "moors"]),
    "af": ("African Fables", "Africa", ["african", "africa"]),
    "kr": ("Fables of Krylov", "Krylov", ["krylov", "krilof", "krylof", "russian"]),
    "ch": ("Fables from the Chinese", "China", ["chinese", "china"]),
    "yr": ("Fables of Yriarte", "Yriarte", ["yriarte", "iriarte", "spanish"]),
    "gc": ("Fables of Gay and Cowper", "Gay and Cowper", ["gay", "cowper"]),
}
BOOK = COLLECTIONS[""][0]
COLOR = discord.Color.from_rgb(150, 110, 60)
LIST_PAGE = 40
PAGE = 1500                                          # characters a page, never splitting a paragraph
CARD_MOST = 1400                                     # a card holds a short fable
STOP = {"the", "and", "a", "an", "of", "his", "her", "its", "in", "on", "to", "with"}
# what people call them now -> Townsend's word (!fable donkey finds The Ass and the Grasshopper)
SAME = {"donkey": "ass", "donkeys": "asses"}


def _fold(text: str) -> str:
    return unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()


def _find_book(book: str) -> "tuple[str, dict]":
    for corpus, books in lookup._data.items():
        if book in books:
            return corpus, books[book]
    return "", {}


@functools.lru_cache(maxsize=None)
def chapters(code: str = "") -> dict:
    """{"1": {"1": "*The Lion and the Mouse*\\nA LION...", "2": ...}}, or {} if the book isn't loaded."""
    return _find_book(COLLECTIONS[code][0])[1]


def fables() -> dict:
    """Aesop's (the name other modules and tests know)."""
    return chapters("")


def tradition_of(code: str) -> "str | None":
    return CORPUS_TRADITION.get(_find_book(COLLECTIONS[code][0])[0])


def source(code: str) -> str:
    return lookup._book_sources.get(COLLECTIONS[code][0], "")


def title(n: int, code: str = "") -> str:
    m = re.match(r"\*([^*\n]+)\*", chapters(code)[str(n)]["1"])
    return m.group(1) if m else f"Fable {n}"


def paragraphs(n: int, code: str = "") -> list:
    paras = list(chapters(code)[str(n)].values())
    paras[0] = re.sub(r"^\*[^*\n]+\*\n", "", paras[0])
    return paras


def body(n: int, code: str = "") -> str:
    """The fable's paragraphs, without the title that leads the first."""
    return "\n\n".join(paragraphs(n, code))


def pages(n: int, code: str = "") -> list:
    out, page = [], ""
    for p in paragraphs(n, code):
        while len(p) > PAGE:                            # (a paragraph longer than a page: at its sentences)
            cut = max(p.rfind(". ", 0, PAGE), p.rfind(".\n", 0, PAGE), p.rfind("\n", 0, PAGE))
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


def _significant(text: str) -> list:
    return [SAME.get(w, w) for w in re.findall(r"[a-z]+", _fold(text)) if w not in STOP]


def numbers(code: str = "") -> list:
    return sorted(map(int, chapters(code)))


def collections_for(guild_id) -> list:
    """The codes of the collections loaded here and allowed on this server."""
    return [c for c in COLLECTIONS if chapters(c) and tradition_enabled(guild_id, tradition_of(c))]


# ── finding ─────────────────────────────────────────────────────────────────
# A spec says which fables a filter allows, and travels in the buttons' ids: "lf|t:wolf" is La Fontaine's with
# the wolf in the title; "*|w:grapes" any collection's that mention grapes; "kr|" all Krylov's; "" all of them.
# (Before there were collections, a spec was just "t:fox", meaning Aesop's; it still does.)

def _split(spec: str) -> "tuple[list, str]":
    if "|" not in spec:
        return ([""] if spec else list(COLLECTIONS)), spec
    code, _, rest = spec.partition("|")
    return ([code] if code != "*" and code in COLLECTIONS else list(COLLECTIONS)), rest


def pool(spec: str, allowed=None) -> list:
    """[(code, n)] the filter allows, among the `allowed` collections (all loaded, if None)."""
    codes, rest = _split(spec)
    codes = [c for c in codes if chapters(c) and (allowed is None or c in allowed)]
    kind, _, arg = rest.partition(":")
    words = _significant(arg)
    out, exact = [], []
    for c in codes:
        if kind == "t":
            found = [n for n in numbers(c) if all(re.search(rf"\b{re.escape(w)}", _fold(title(n, c))) for w in words)]
            exact += [(c, n) for n in found if _significant(title(n, c)) == words]
            out += [(c, n) for n in found]
        elif kind == "w":
            out += [(c, n) for n in numbers(c)
                    if all(re.search(rf"\b{re.escape(w)}", _fold(title(n, c) + " " + body(n, c))) for w in words)]
        else:
            out += [(c, n) for n in numbers(c)]
    return exact or out                                 # ("lion and mouse": that one, not the Lion, the Mouse and the Cat)


def collection_named(query: str) -> "tuple[str | None, str]":
    """(the collection a query starts with, the rest), e.g. "la fontaine wolf" -> ("lf", "wolf")."""
    q = _fold(query).strip()
    best = None
    for code, (_, _, names) in COLLECTIONS.items():
        for name in names:
            if (q == name or q.startswith(name + " ")) and (best is None or len(name) > len(best[1])):
                best = (code, name)
    if best is None:
        return None, query
    return best[0], q[len(best[1]):].strip()


def parse(query: str, code: "str | None" = None) -> "tuple[str, str]":
    """(filter spec, how it was read) for what follows !fable (and its collection): the title, else the text."""
    q = query.strip()[:50]
    prefix = f"{code}|" if code is not None else "*|"
    if not q:
        return (prefix if code is not None else ""), ""
    if not [w for w in _fold(q).split() if w not in STOP]:
        return f"{prefix}w:{q}", f"with “{q}”"
    if pool(f"{prefix}t:{q}"):
        return f"{prefix}t:{q}", f"“{q}”"
    return f"{prefix}w:{q}", f"with “{q}”"


# ── showing ─────────────────────────────────────────────────────────────────

def _key(code: str, n: int) -> str:
    return f"{code}{n}"


def _unkey(key: str) -> "tuple[str, int]":
    m = re.fullmatch(r"([a-z]{0,2})(\d+)", key)
    return m.group(1), int(m.group(2))


class FableButton(discord.ui.DynamicItem[discord.ui.Button],
                  template=r"fable:(?P<action>again|card|list|back|next):(?P<n>[a-z]{0,2}\d+)(?::p(?P<page>\d+))?"
                           r":(?P<spec>.{0,60})"):
    """🎲 another of the same kind, 🖼️ the fable as a card, ◀ ▶ a long fable's pages or the list of titles. The
    custom_id carries what it needs (the collection's code before the number), so these keep working after a
    restart -- and those from before the collections still do, as Aesop's."""

    def __init__(self, action, n, spec, label="", emoji="", page=None):
        page_part = f":p{page}" if page is not None else ""
        super().__init__(discord.ui.Button(label=label or None, emoji=emoji or None, style=discord.ButtonStyle.secondary,
                                           custom_id=f"fable:{action}:{n}{page_part}:{spec}"[:100]))
        self.action, self.key, self.spec, self.page = action, str(n), spec, int(page or 0)

    @classmethod
    async def from_custom_id(cls, interaction, item, match):
        return cls(match["action"], match["n"], match["spec"], page=match["page"])

    async def callback(self, interaction: discord.Interaction):
        code, n = _unkey(self.key)
        guild = interaction.guild.id if interaction.guild else None
        if self.action == "list":                              # n is the page; the spec says "back"/"next"
            await interaction.response.edit_message(**list_message(n, code))
            return
        if code not in COLLECTIONS or str(n) not in chapters(code):
            await interaction.response.send_message("⚠️ I can't find that fable any more.", ephemeral=True)
            return
        if self.action == "again":
            await interaction.response.send_message(**another(code, n, self.spec, collections_for(guild)))
        elif self.action == "card":
            await interaction.response.defer(thinking=True)
            buf = await asyncio.to_thread(render_card, n, code)
            await interaction.followup.send(file=discord.File(buf, filename=f"fable-{code}{n}.png"))
        else:
            await interaction.response.edit_message(**message(n, spec=self.spec, code=code, page=self.page))


bot.add_dynamic_items(FableButton)


def _cardable(n: int, code: str) -> bool:
    """A short fable in prose: a card holds it (verse would be spoiled by justifying)."""
    text = body(n, code)
    return len(text) <= CARD_MOST and not any("\n" in p for p in paragraphs(n, code))


def footer(n: int, code: str) -> str:
    book, short, _ = COLLECTIONS[code]
    return f"{book}, no. {n} · {source(code)}" if code else f"Aesop's Fables, no. {n} · {source(code)}"


def message(n: int, spec: str = "", heading: str = "", code: str = "", page: int = 0) -> dict:
    texts = pages(n, code)
    page %= len(texts)
    embed = discord.Embed(title=f"🦊 {title(n, code)}"[:256], description=texts[page], color=COLOR)
    if heading:
        embed.set_author(name=heading[:256])
    where = f" · page {page + 1} of {len(texts)}" if len(texts) > 1 else ""
    embed.set_footer(text=footer(n, code) + where)
    view = discord.ui.View(timeout=None)
    if len(texts) > 1:
        view.add_item(FableButton("back", _key(code, n), spec, emoji="◀", page=(page - 1) % len(texts)))
        view.add_item(FableButton("next", _key(code, n), spec, emoji="▶", page=(page + 1) % len(texts)))
    view.add_item(FableButton("again", _key(code, n), spec, label="Another", emoji="🎲"))
    if _cardable(n, code):
        view.add_item(FableButton("card", _key(code, n), spec, label="Card", emoji="🖼️"))
    for b in illustrations.buttons(illustrations.for_passage(COLLECTIONS[code][0], str(n))):
        view.add_item(b)                                # (🖌️ Doré, Rackham...: the fable's pictures)
    return {"embed": embed, "view": view}


def another(code: str, n: int, spec: str, allowed=None) -> dict:
    """🎲: a different fable of the same kind; when this was the only one (fox and grapes), say so and give
    a random fable instead -- pressing it used to bring the same fable back every time."""
    others = [(c, m) for c, m in pool(spec, allowed) if (c, m) != (code, n)]
    if others:
        c, m = random.choice(others)
        return message(m, spec=spec, code=c)
    asked = _split(spec)[1].partition(":")[2]
    sorry = (f"Sorry, that's the only fable with “{asked}”. Here's a random fable instead." if asked
             else "Here's a random fable instead.")
    c, m = random.choice([x for x in pool("", allowed) if x != (code, n)])
    return message(m, heading=sorry, code=c)


def render_card(n: int, code: str = ""):
    """The fable as a PNG card, justified, in the classical style."""
    return card._render_verse_card(title(n, code), body(n, code), footer(n, code), style="classical", justify=True)


def list_message(page: int = 0, code: str = "") -> dict:
    ns = numbers(code)
    pages_ = max(1, -(-len(ns) // LIST_PAGE))
    page %= pages_
    shown = ns[page * LIST_PAGE:(page + 1) * LIST_PAGE]
    book, short, names = COLLECTIONS[code]
    embed = discord.Embed(title=f"🦊 {book}", description="\n".join(f"`{n}` {title(n, code)}" for n in shown),
                          color=COLOR)
    how = f"!fable {names[0]} 12" if code else "!fable 12 or !fable fox"
    embed.set_footer(text=f"Page {page + 1} of {pages_} · {how} · {source(code)}")
    view = discord.ui.View(timeout=None)
    view.add_item(FableButton("list", _key(code, (page - 1) % pages_), "back", emoji="◀"))   # ("back"/"next" keep
    view.add_item(FableButton("list", _key(code, (page + 1) % pages_), "next", emoji="▶"))   #  the ids apart)
    return {"embed": embed, "view": view}


def collections_message(allowed: list) -> dict:
    lines = [f"**{COLLECTIONS[c][0]}** — {len(chapters(c))} fables · `!fable {COLLECTIONS[c][2][0]}`" for c in allowed]
    embed = discord.Embed(title="🦊 The fable collections", description="\n".join(lines), color=COLOR)
    embed.set_footer(text="!fable alone draws from all of them · !fable fox looks in all of them")
    return {"embed": embed}


async def send_fable(ctx, query: str = "") -> None:
    guild = getattr(ctx, "guild", None)
    allowed = collections_for(guild.id if guild else None)
    if not any(chapters(c) for c in COLLECTIONS):
        await ctx.send("⚠️ The fables aren't loaded.")
        return
    if not allowed:
        await ctx.send("The fables are among the Greek and Roman texts and the folk tales, which this server has "
                       "turned off.")
        return
    q = query.strip()
    if _fold(q) in ("collections", "books", "sources"):
        await ctx.send(**collections_message(allowed))
        return
    code, rest = collection_named(q)
    if code is not None and code not in allowed:
        await ctx.send(f"{COLLECTIONS[code][0]} are among the texts this server has turned off.")
        return
    if _fold(rest) in ("list", "all", "titles", "index", "contents"):
        await ctx.send(**list_message(0, code or ""))
        return
    if re.fullmatch(r"#?\d{1,4}", rest):
        c, n = code or "", int(rest.lstrip("#"))
        if c not in allowed:
            await ctx.send("Aesop's Fables are among the Greek and Roman texts, which this server has turned off.")
            return
        if str(n) not in chapters(c):
            await ctx.send(f"{COLLECTIONS[c][0]} are numbered 1 to {max(numbers(c))}.")
            return
        await ctx.send(**message(n, code=c))
        return
    spec, label = parse(rest, code)
    found = pool(spec, allowed)
    if not found:
        where = f" in {COLLECTIONS[code][0]}" if code is not None else ""
        await ctx.send(f"I found no fable {label}{where}. Try `!fable list`, or just `!fable`." if label
                       else "I couldn't find a fable.")
        return
    c, n = random.choice(found)
    log.info(f"RNG  fable {spec or 'any':24} → {c}{n} (user: {ctx.author})")
    heading = "" if not label or len(found) == 1 else f"A fable {label} ({len(found)} like it)"
    await ctx.send(**message(n, spec=spec, heading=heading, code=c))


@bot.command(name="fable", aliases=["aesop", "fables"])
async def cmd_fable(ctx, *, query: str = ""):
    """A fable: Aesop, Phaedrus, La Fontaine, Bidpai, Krylov and more.
    Usage: !fable              — one at random, from any collection
           !fable fox          — one with the fox in its title
           !fable lion mouse   — by its title
           !fable 12           — Aesop's by number
           !fable la fontaine  — one of his (also: phaedrus, bidpai, krylov, african...)
           !fable list         — Aesop's titles (!fable la fontaine list for his)
           !fable collections  — the collections"""
    await send_fable(ctx, query)
