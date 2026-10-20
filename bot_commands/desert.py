"""
!desert (!apophthegm) -- a saying of the Desert Fathers, from Budge's "Paradise of the Holy Fathers",
Volume II (1907): the 635 sayings of Book I, in fourteen chapters by subject, and the 706 questions and
answers of Book II (data/patristics/paradise_of_the_fathers.json, built by scripts/build_paradise.py).

    !desert                 a saying at random
    !desert Poemen          one by or about a father (or mother: Sarah)
    !desert fathers         the fathers, and how many sayings each has
    !desert topics          the chapters, to choose from
    !desert humility        one from a chapter, by a word of its title (or !desert topic 10)
    !desert 1:303           a saying by number (Book I, saying 303)
    !desert anger           anything else: a saying with those words in it

A long saying comes a page at a time (◀ ▶); 🎲 draws another of the same kind.
"""
import difflib
import functools
import random
import re
import unicodedata

import discord

from core import bot, log, lookup

BOOK = "Sayings of the Desert Fathers"
SOURCE = "Budge (1907)"
COLOR = discord.Color.from_rgb(176, 132, 72)
PAGE = 3800
BOOK_NAMES = {"1": "Book I", "2": "Book II"}
# names given in more than one spelling, and words that follow "Abbâ" without being a name
SAME = {"Panbô": "Pambô", "Pamô": "Pambô", "Paule": "Paulê", "Antonius": "Anthony", "Nestîr": "Nastîr",
        "Nastir": "Nastîr", "Battimion": "Betimius"}
NOT_NAMES = {"Abbâ", "Mâr", "Apostle", "Cross", "Archbishop", "Christ", "He", "Bishop", "The", "And", "Father"}
_NAME = re.compile(r"\b(?:Abbâ|ABBÂ|Abba|Mother|Amma|old man|blessed|holy man)\s+([A-Z][a-zâêîôûA-ZÂÊÎÔÛ]+)")


def _fold(text: str) -> str:
    return unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()


@functools.lru_cache(maxsize=1)
def sayings() -> dict:
    """{"1": {"303": text}, "2": {...}}, or {} if the book isn't loaded."""
    for corpus in lookup._data.values():
        if BOOK in corpus:
            return corpus[BOOK]
    return {}


@functools.lru_cache(maxsize=1)
def topics() -> list:
    """[(book, first saying, last saying, title)] from the chapter headings that lead their first sayings."""
    starts = []
    for book, vs in sayings().items():
        for n, text in vs.items():
            heads = [h for h in re.findall(r"^\*([^*\n]+)\*$", re.match(r"(?:\*[^*\n]+\*\n)*", text).group(0), re.M)
                     if not h.startswith("Book the") and h != "Appendix"]
            if heads:
                title = heads[-1] + (" (Appendix)" if "*Appendix*" in text.split("\n")[0] else "")
                starts.append((book, int(n), title))
    starts.sort(key=lambda s: (s[0], s[1]))
    out = []
    for i, (book, first, title) in enumerate(starts):
        nxt = starts[i + 1] if i + 1 < len(starts) and starts[i + 1][0] == book else None
        last = nxt[1] - 1 if nxt else max(map(int, sayings()[book]))
        out.append((book, first, last, _short(title)))
    return out


def _short(title: str) -> str:
    """"Chapter VI: Of Patient Endurance" -> "Of Patient Endurance"; Budge's capitals kept."""
    title = re.sub(r"^Chapter [IVXL]+:\s*", "", title)
    return re.sub(r"\s+", " ", title).strip()


def topic_of(book: str, n: int) -> str:
    return next((t for b, a, z, t in topics() if b == book and a <= n <= z), "")


# A short name for each of Budge's chapters and sections, in order (his own titles run to thirty words)
SHORT = ["Flight from Men", "Fasting", "Scripture, Vigils and Prayer", "Weeping for Sin", "Voluntary Poverty",
         "Patient Endurance", "Obedience", "Watchfulness", "Love and Hospitality", "Humility", "Fornication",
         "Repentance", "Wonderworkers", "The Solitary Life",
         "The Rule of Life", "The Pupils' Questions", "The Vision of the Mind", "The Brethren's Questions"]


def brief(title: str) -> str:
    """A chapter's short name ("Patient Endurance"), from Budge's title."""
    for i, (_, _, _, t) in enumerate(topics()):
        if t == title and i < len(SHORT):
            return SHORT[i]
    return re.split(r",| Which | \[A Work\]", title)[0].strip()


@functools.lru_cache(maxsize=1)
def fathers() -> dict:
    """{name: [(book, n), ...]} for every father or mother named in a saying."""
    out = {}
    for book, vs in sayings().items():
        for n, text in vs.items():
            seen = set()
            for m in _NAME.finditer(text):
                name = m.group(1).capitalize() if m.group(1).isupper() else m.group(1)
                name = SAME.get(name, name)
                if name in NOT_NAMES or name in seen:
                    continue
                seen.add(name)
                out.setdefault(name, []).append((book, int(n)))
    return dict(sorted(out.items(), key=lambda kv: (-len(kv[1]), kv[0])))


def body(text: str) -> str:
    """A saying without the chapter heading that leads the first of a chapter."""
    return re.sub(r"^(?:\*[^*\n]+\*\n)+", "", text).strip()


def pages(text: str) -> list:
    out = []
    while len(text) > PAGE:
        cut = text.rfind("\n", 0, PAGE)
        cut = cut if cut > PAGE // 2 else text.rfind(". ", 0, PAGE) + 1
        out.append(text[:cut].strip())
        text = text[cut:].strip()
    return out + [text]


# ── choosing ────────────────────────────────────────────────────────────────

def pool(spec: str) -> list:
    """The sayings a filter allows: "" all; "f:Name" a father's; "t:3" a topic's; "w:words" ones with
    the words."""
    kind, _, arg = spec.partition(":")
    if kind == "f":
        return fathers().get(arg, [])
    if kind == "t":
        b, a, z, _ = topics()[int(arg)]
        return [(b, n) for n in range(a, z + 1) if str(n) in sayings()[b]]
    everything = [(b, int(n)) for b, vs in sayings().items() for n in vs]
    if kind == "w":
        words = _fold(arg).split()
        return [(b, n) for b, n in everything if all(re.search(rf"\b{re.escape(w)}", _fold(sayings()[b][str(n)]))
                                                   for w in words)]
    return everything


def find_father(query: str) -> "str | None":
    names = {_fold(n): n for n in fathers()}
    q = _fold(query).strip()
    q = re.sub(r"^(abba|abbâ|amma|mother|saint|st\.?|abbot)\s+", "", q)
    if q in names:
        return names[q]
    starts = [n for k, n in names.items() if k.startswith(q)] if len(q) >= 3 else []
    if len(starts) == 1:
        return starts[0]
    close = difflib.get_close_matches(q, list(names), n=1, cutoff=0.82)
    return names[close[0]] if close else None


def find_topic(query: str) -> "int | None":
    q = _fold(query).strip()
    m = re.fullmatch(r"(?:topic|chapter)?\s*(\d{1,2})", q)
    if m:
        i = int(m.group(1)) - 1
        return i if 0 <= i < len(topics()) else None
    words = [w for w in q.split() if w not in ("of", "the", "and", "topic", "chapter")]
    if not words:
        return None
    hits = [i for i, (_, _, _, t) in enumerate(topics())
            if all(re.search(rf"\b{re.escape(w)}", _fold(t + " " + brief(t))) for w in words)]
    return hits[0] if len(hits) == 1 else None


def parse(query: str) -> "tuple[str, str]":
    """(filter spec, how it was read) for what follows !desert."""
    q = query.strip()
    if not q:
        return "", ""
    father = find_father(q)
    if father:
        return f"f:{father}", f"by or about {father}"
    topic = find_topic(q)
    if topic is not None:
        return f"t:{topic}", brief(topics()[topic][3])
    return f"w:{q[:40]}", f"with “{q[:40]}”"


# ── showing ─────────────────────────────────────────────────────────────────

class DesertButton(discord.ui.DynamicItem[discord.ui.Button],
                   template=r"desert:(?P<action>pg|bk|again):(?P<book>[12]):(?P<n>\d+):(?P<page>\d+):(?P<spec>.{0,60})"):
    """◀ ▶ through a long saying, and 🎲 another of the same kind. The custom_id carries what it needs,
    so these keep working after a restart."""

    def __init__(self, action, book, n, page, spec, label="", emoji=""):
        super().__init__(discord.ui.Button(label=label or None, emoji=emoji or None, style=discord.ButtonStyle.secondary,
                                           custom_id=f"desert:{action}:{book}:{n}:{page}:{spec}"[:100]))
        self.action, self.book, self.n, self.page, self.spec = action, book, int(n), int(page), spec

    @classmethod
    async def from_custom_id(cls, interaction, item, match):
        return cls(match["action"], match["book"], match["n"], match["page"], match["spec"])

    async def callback(self, interaction: discord.Interaction):
        if self.action == "again":
            choice = _pick(self.spec)
            if choice is None:
                await interaction.response.send_message("I can't find another saying like that.", ephemeral=True)
                return
            await interaction.response.send_message(**message(*choice, spec=self.spec))
        else:
            await interaction.response.edit_message(**message(self.book, self.n, self.page, self.spec))


bot.add_dynamic_items(DesertButton)


def _pick(spec: str):
    found = pool(spec)
    return random.choice(found) if found else None


def message(book: str, n: int, page: int = 0, spec: str = "", heading: str = "") -> dict:
    text = body(sayings()[book][str(n)])
    parts = pages(text)
    page = max(0, min(page, len(parts) - 1))
    embed = discord.Embed(title=f"🏜️ The Desert Fathers — {BOOK_NAMES[book]}, saying {n}",
                          description=parts[page], color=COLOR)
    if heading:
        embed.set_author(name=heading[:256])
    topic = topic_of(book, n)
    footer = (f"{brief(topic)} · " if topic else "") + SOURCE
    if len(parts) > 1:
        footer += f" · page {page + 1} of {len(parts)}"
    embed.set_footer(text=footer[:2048])
    view = discord.ui.View(timeout=None)
    if len(parts) > 1:
        view.add_item(DesertButton("bk", book, n, (page - 1) % len(parts), spec, emoji="◀"))
        view.add_item(DesertButton("pg", book, n, (page + 1) % len(parts), spec, emoji="▶"))
    view.add_item(DesertButton("again", book, n, 0, spec, label="Another", emoji="🎲"))
    return {"embed": embed, "view": view}


def fathers_embed() -> discord.Embed:
    named = fathers()
    lines = [f"{name} ({len(found)})" for name, found in named.items()]
    text = " · ".join(lines)
    if len(text) > 3900:
        text = text[:text.rfind(" · ", 0, 3900)] + " · …"
    embed = discord.Embed(title="🏜️ The Desert Fathers — who is in the sayings",
                          description=text, color=COLOR)
    embed.set_footer(text="How many sayings name each · !desert Poemen for one of his · " + SOURCE)
    return embed


def topics_embed() -> discord.Embed:
    lines, last_book = [], None
    for i, (book, a, z, title) in enumerate(topics(), 1):
        if book != last_book:
            lines.append(f"**{BOOK_NAMES[book]}**")
            last_book = book
        lines.append(f"`{i}` **{brief(title)}** — {z - a + 1} sayings")
    embed = discord.Embed(title="🏜️ The Desert Fathers — topics", description="\n".join(lines), color=COLOR)
    embed.set_footer(text="!desert topic 6, or by name: !desert humility · Budge, The Paradise of the Holy Fathers (1907)")
    return embed


async def send_desert(ctx, query: str = "") -> None:
    if not sayings():
        await ctx.send("⚠️ The sayings of the Desert Fathers aren't loaded.")
        return
    q = query.strip()
    if _fold(q) in ("fathers", "father", "list", "who", "names", "mothers"):
        await ctx.send(embed=fathers_embed())
        return
    if _fold(q) in ("topics", "topic", "chapters", "subjects"):
        await ctx.send(embed=topics_embed())
        return
    m = re.fullmatch(r"(?:book\s*)?([12])\s*[:.]\s*(\d{1,3})", q.lower())
    if m:
        book, n = m.group(1), int(m.group(2))
        if str(n) not in sayings()[book]:
            last = max(map(int, sayings()[book]))
            await ctx.send(f"{BOOK_NAMES[book]} has sayings 1 to {last}"
                           + (" (Budge's numbering skips 133)" if book == "2" else "") + ".")
            return
        await ctx.send(**message(book, n))
        return
    spec, label = parse(q)
    choice = _pick(spec)
    if choice is None:
        await ctx.send(f"I found no saying {label}. Try `!desert fathers`, `!desert topics`, or just `!desert`."
                       if label else "I couldn't find a saying.")
        return
    log.info(f"RNG  desert {spec or 'any':20} → {choice[0]}:{choice[1]} (user: {ctx.author})")
    heading = "" if not label else (f"From “{label}”" if spec.startswith("t:") else f"A saying {label}")
    await ctx.send(**message(*choice, spec=spec, heading=heading))


@bot.command(name="desert", aliases=["apophthegm", "apophthegmata", "desertfathers", "abba"])
async def cmd_desert(ctx, *, query: str = ""):
    """A saying of the Desert Fathers (Budge's Paradise of the Holy Fathers).
    Usage: !desert              — one at random
           !desert Poemen       — one by or about a father
           !desert fathers      — the fathers, and how many sayings each has
           !desert topics       — the chapters; then !desert humility or !desert topic 10
           !desert 1:303        — Book I, saying 303
           !desert anger        — one with those words"""
    await send_desert(ctx, query)
