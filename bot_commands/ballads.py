"""
!ballad -- Child's English and Scottish Popular Ballads (1882-98): all 305, each in the versions he printed
(data/ballads/child.json, scripts/build_child.py), with tunes from the Digital Tradition where it has them and a
recording on YouTube (data/ballads/tunes.json and audio/, scripts/build_child_tunes.py).

    !ballad                  one at random
    !ballad 12               Lord Randal, its first version
    !ballad 12B              its second version
    !ballad barbara allen    by title, or a name it goes by (matty groves, scarborough fair, the golden vanity)
    !ballad list             all 305 titles, a page at a time

◀ ▶ turn a long version's pages; 🔀 goes to the next version; ▶️ plays its tune (again for the next tune, where
there are several); 📺 opens a recording on YouTube (from a playlist of them in Child's order).
"""
import difflib
import functools
import json
import random
import re
import unicodedata

import discord

from core import ROOT, bot, log, lookup, tradition_enabled

BOOK = "Child Ballads"
SOURCE = "Francis James Child, The English and Scottish Popular Ballads (1882–98)"
TUNES_PATH = ROOT / "data" / "ballads" / "tunes.json"
AUDIO_DIR = ROOT / "data" / "ballads" / "audio"
COLOR = discord.Color.from_rgb(90, 120, 80)
PAGE = 1500                                        # characters of verse a page
LIST_PAGE = 40
STOP = {"the", "a", "an", "of", "o", "and", "or", "in", "on", "to"}


def _fold(text: str) -> str:
    return unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower().replace("’", "'")


def _words(text: str) -> list:
    return [w for w in re.findall(r"[a-z]+", _fold(text)) if w not in STOP]


@functools.lru_cache(maxsize=1)
def versions() -> dict:
    """{"12A": {"1": "*Lord Rendal*\\n‘O where...", ...}, ...}, or {} if the ballads aren't loaded."""
    return lookup._data.get("ballads", {}).get(BOOK, {})


@functools.lru_cache(maxsize=1)
def by_number() -> dict:
    """{12: ["12A", "12B", ...]}: each ballad's versions in order ("22": a ballad printed in one version)."""
    out = {}
    for key in versions():
        m = re.fullmatch(r"(\d+)([A-Z]*)", key)
        if m:
            out.setdefault(int(m.group(1)), []).append(key)
    return {n: sorted(keys, key=lambda k: (len(k), k)) for n, keys in sorted(out.items())}


@functools.lru_cache(maxsize=1)
def _extras() -> dict:
    """tunes.json: {"tunes": {"12": [{"file", "title", "source", ...}]}, "youtube": {"12": {"id", "title"}}}."""
    if not TUNES_PATH.exists():
        return {"tunes": {}, "youtube": {}}
    return json.loads(TUNES_PATH.read_text(encoding="utf-8"))


def tunes(n: int) -> list:
    """The ballad's tunes that have been rendered to audio."""
    return [t for t in _extras()["tunes"].get(str(n), []) if (AUDIO_DIR / f"{t['file']}.ogg").exists()]


def video(n: int) -> "dict | None":
    return _extras()["youtube"].get(str(n))


def version_title(key: str) -> str:
    m = re.match(r"\*([^*\n]+)\*", next(iter(versions()[key].values()), ""))
    return m.group(1) if m else ""


def title(n: int) -> str:
    """The ballad's title, as Child heads it (its first version's)."""
    return version_title(by_number()[n][0]) or f"Child {n}"


def letter(key: str) -> str:
    return re.sub(r"^\d+", "", key)


# ── finding one ─────────────────────────────────────────────────────────────

@functools.lru_cache(maxsize=1)
def _names() -> list:
    """[(folded words, ballad number, version key or None)]: every name a ballad goes by -- Child's titles, his
    versions' titles, its tunes' titles in the Digital Tradition, and its recording's title."""
    out = []
    for n, keys in by_number().items():
        for key in keys:
            out.append((_words(version_title(key)), n, key))
        for t in _extras()["tunes"].get(str(n), []):
            out.append((_words(t["title"]), n, None))
        v = video(n)
        if v:
            name = re.sub(r"\(.*?\)|\[.*?\]|child\W*(ballad)?\W*(no\.?|#)?\s*\d+|^\d+\.\s*|traditional \w+", " ",
                          v["title"], flags=re.I)
            name = name.split(" - ", 1)[-1]
            out.append((_words(name), n, None))
    return [x for x in out if x[0]]


def find(query: str) -> "tuple | None":
    """(ballad number, version key or None, the name it was found by) for a title or a name it goes by."""
    words = _words(query)
    if not words:
        return None
    names = _names()
    for exact in (True, False):
        hits = [(n, key, w) for w, n, key in names
                if (w == words if exact else all(any(x.startswith(q) for x in w) for q in words))]
        if hits:
            n, key, w = min(hits, key=lambda h: (len(h[2]), h[0]))
            return n, key, " ".join(w)
    joined = " ".join(words)
    best = max(names, key=lambda x: difflib.SequenceMatcher(None, joined, " ".join(x[0])).ratio())
    if difflib.SequenceMatcher(None, joined, " ".join(best[0])).ratio() >= 0.8:
        return best[1], best[2], " ".join(best[0])
    return None


# ── showing ─────────────────────────────────────────────────────────────────

def pages(key: str) -> list:
    """The version's stanzas, numbered, a page of about PAGE characters (never a stanza split)."""
    out, page = [], ""
    for k, text in versions()[key].items():
        text = re.sub(r"^\*[^*\n]+\*\n", "", text)
        stanza = f"**{k}** {text}"
        if page and len(page) + len(stanza) + 2 > PAGE:
            out.append(page)
            page = ""
        page = f"{page}\n\n{stanza}" if page else stanza
    return out + [page] if page else out or [""]


class BalladButton(discord.ui.DynamicItem[discord.ui.Button],
                   template=r"ballad:(?P<action>back|next|ver|play|again|list):(?P<key>\d{1,3}[A-Z]{0,2}):(?P<arg>\d+)"):
    """◀ ▶ pages, 🔀 the next version, ▶️ a tune (arg: which), 🎲 another ballad, ◀ ▶ the list (key 0, arg the page).
    The custom_id carries all it needs, so they keep working after a restart."""

    def __init__(self, action: str, key: str, arg: int, label: str = "", emoji: str = ""):
        super().__init__(discord.ui.Button(label=label or None, emoji=emoji or None, style=discord.ButtonStyle.secondary,
                                           custom_id=f"ballad:{action}:{key}:{arg}"))
        self.action, self.key, self.arg = action, key, int(arg)

    @classmethod
    async def from_custom_id(cls, interaction, item, match):
        return cls(match["action"], match["key"], match["arg"])

    async def callback(self, interaction: discord.Interaction):
        if self.action == "list":
            await interaction.response.edit_message(**list_message(self.arg))
            return
        if self.action == "again":
            n = random.choice([m for m in by_number() if str(m) != re.sub(r"\D", "", self.key)])
            await interaction.response.send_message(**message(by_number()[n][0]))
            return
        if self.key not in versions():
            await interaction.response.send_message("⚠️ I can't find that ballad any more.", ephemeral=True)
            return
        if self.action in ("back", "next"):
            await interaction.response.edit_message(**message(self.key, self.arg))
        elif self.action == "ver":
            keys = by_number()[int(re.sub(r"\D", "", self.key))]
            await interaction.response.edit_message(**message(keys[(keys.index(self.key) + 1) % len(keys)]))
        else:
            await play(interaction, int(re.sub(r"\D", "", self.key)), self.arg)


bot.add_dynamic_items(BalladButton)


def message(key: str, page: int = 0, heading: str = "") -> dict:
    """send()/edit kwargs for one page of a version, with its buttons."""
    n = int(re.sub(r"\D", "", key))
    keys, texts = by_number()[n], pages(key)
    page %= len(texts)
    which = f" · version {letter(key)}, {keys.index(key) + 1} of {len(keys)}" if len(keys) > 1 else ""
    name = version_title(key) or title(n)
    embed = discord.Embed(title=f"🎻 {n}. {name}"[:256], description=texts[page], color=COLOR)
    if heading:
        embed.set_author(name=heading[:256])
    found = tunes(n)
    about = [f"Child {key}", f"page {page + 1} of {len(texts)}" if len(texts) > 1 else "",
             (f"{len(found)} tunes" if len(found) > 1 else "a tune to play") if found else "I have no tune for this one",
             SOURCE]
    embed.set_footer(text=" · ".join(x for x in about if x))
    view = discord.ui.View(timeout=None)                # persistent buttons: must never time out
    if len(texts) > 1:
        view.add_item(BalladButton("back", key, (page - 1) % len(texts), emoji="◀"))
        view.add_item(BalladButton("next", key, (page + 1) % len(texts), emoji="▶"))
    if len(keys) > 1:
        nxt = keys[(keys.index(key) + 1) % len(keys)]
        view.add_item(BalladButton("ver", key, 0, label=f"Version {letter(nxt)}", emoji="🔀"))
    if found:
        view.add_item(BalladButton("play", key, 0, label="Play the tune", emoji="▶️"))
    v = video(n)
    if v:
        view.add_item(discord.ui.Button(label="Recording", emoji="📺", style=discord.ButtonStyle.link,
                                        url=f"https://www.youtube.com/watch?v={v['id']}"))
    view.add_item(BalladButton("again", key, 0, label="Another", emoji="🎲"))
    return {"embed": embed, "view": view}


def tune_message(n: int, i: int) -> "dict | None":
    """send() kwargs for the ballad's i-th tune, with a button for the next where there are more."""
    found = tunes(n)
    if not found:
        return None
    i %= len(found)
    t = found[i]
    stem = re.sub(r"[^A-Za-z0-9]+", "_", _fold(t["title"] or title(n))).strip("_")[:60] or "tune"
    where = f" ({t['source']})" if t.get("source") else ""
    count = f", tune {i + 1} of {len(found)}" if len(found) > 1 else ""
    caption = (f"🎵 **{t['title'] or title(n)}**: a tune for Child {n}, *{title(n)}*{count}, from the Digital "
               f"Tradition{where}. The melody alone, once through.")
    kwargs = {"content": caption[:2000], "file": discord.File(AUDIO_DIR / f"{t['file']}.ogg", filename=f"{stem}.ogg")}
    if len(found) > 1:
        view = discord.ui.View(timeout=None)
        view.add_item(BalladButton("play", by_number()[n][0], (i + 1) % len(found),
                                   label=f"Next tune ({(i + 1) % len(found) + 1} of {len(found)})", emoji="▶️"))
        kwargs["view"] = view
    return kwargs


async def play(interaction: discord.Interaction, n: int, i: int) -> None:
    kwargs = tune_message(n, i)
    if kwargs is None:
        await interaction.response.send_message("I have no tune for this ballad.", ephemeral=True)
        return
    # Acknowledge first: Discord drops a reply not begun within 3 seconds, and an upload can take longer
    await interaction.response.defer(thinking=True)
    await interaction.followup.send(**kwargs)


def list_message(page: int = 0) -> dict:
    ns = list(by_number())
    count = max(1, -(-len(ns) // LIST_PAGE))
    page %= count
    shown = ns[page * LIST_PAGE:(page + 1) * LIST_PAGE]
    lines = [f"`{n}` {title(n)}" + (" 🎵" if tunes(n) else "") for n in shown]
    embed = discord.Embed(title="🎻 Child's Ballads", description="\n".join(lines), color=COLOR)
    embed.set_footer(text=f"Page {page + 1} of {count} · 🎵 has a tune · !ballad 12 or !ballad barbara allen")
    view = discord.ui.View(timeout=None)
    view.add_item(BalladButton("list", "0", (page - 1) % count, emoji="◀"))
    view.add_item(BalladButton("list", "1", (page + 1) % count, emoji="▶"))    # ("0"/"1": the ids apart)
    return {"embed": embed, "view": view}


async def send_ballad(ctx, query: str = "") -> None:
    if not versions():
        await ctx.send("⚠️ The ballads aren't loaded.")
        return
    guild = getattr(ctx, "guild", None)
    if not tradition_enabled(guild.id if guild else None, "ballads"):
        await ctx.send("The folk ballads are turned off on this server.")
        return
    q = query.strip()[:80]
    if _fold(q) in ("list", "all", "titles", "index", "contents"):
        await ctx.send(**list_message(0))
        return
    if not q:
        n = random.choice(list(by_number()))
        log.info(f"RNG  ballad → {n} (user: {ctx.author})")
        await ctx.send(**message(by_number()[n][0]))
        return
    m = re.fullmatch(r"(?:child\s*)?#?(\d{1,4})\s*([A-Za-z]{0,2})", q, re.IGNORECASE)
    if m:
        n, want = int(m.group(1)), m.group(2).upper()
        if n not in by_number():
            await ctx.send("Child's ballads are numbered 1 to 305.")
            return
        keys = by_number()[n]
        if want and f"{n}{want}" not in keys:
            have = ", ".join(letter(k) for k in keys if letter(k))
            await ctx.send(f"Child {n}, *{title(n)}*, " + (f"has versions {have}." if have else "has only one version."))
            return
        await ctx.send(**message(f"{n}{want}" if want else keys[0]))
        return
    hit = find(q)
    if hit is None:
        await ctx.send(f"I couldn't find a ballad called “{discord.utils.escape_markdown(q)}”. "
                       f"Try `!ballad list`, or a number such as `!ballad 84`.")
        return
    n, key, name = hit
    shown = _words(version_title(key) if key else title(n))
    named = not all(any(w.startswith(q) for w in shown) for q in _words(q))   # (say how a name was read)
    heading = f"“{q}” is Child {n}, {title(n)}" if named else ""
    await ctx.send(**message(key or by_number()[n][0], heading=heading))


@bot.command(name="ballad", aliases=["ballads", "child"])
async def cmd_ballad(ctx, *, query: str = ""):
    """One of Child's 305 English and Scottish ballads, with its tune where there is one.
    Usage: !ballad                  — one at random
           !ballad 12               — by Child's number (12B: its second version)
           !ballad barbara allen    — by title, or a name it goes by
           !ballad list             — all the titles"""
    await send_ballad(ctx, query)
