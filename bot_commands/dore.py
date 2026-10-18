"""
Pictures tied to passages: Gustave Doré's engravings for the Bible (with the Apocrypha), the
Divine Comedy and Paradise Lost (data/dore/plates.json, built by scripts/build_dore.py), and
William Blake's illustrations to Job, the Bible, Paradise Lost, The Pilgrim's Progress and the
Divine Comedy (data/blake/art.json, scripts/build_blake_art.py).

!dore shows Doré's (Blake's are in !blake, bot_commands/blake.py), and under !verse a 🖼️ Doré
and a 🎨 Blake button appear wherever a passage has one. The pictures are shown from Wikimedia,
except the Dante plates that only exist there as whole-page book scans: those are attached, cut
out of their scans by the build (data/dore/dante/).
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
        if p["book"] != book:
            continue
        # (Blake's Job plates carry several passages of Job; the first is the main one)
        for ch, a, b in p.get("passages") or [(p["chapter"], p["start"], p["end"])]:
            if ch == chapter and (start is None or a is None or (a <= (end or start) and start <= b)):
                hits.append(p)
                break
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


def reference(p: dict, dash: str = "–") -> str:
    """"Genesis 11:1–4", "Inferno 1:31–33", "Paradise Lost 1:44"."""
    if not p["book"]:
        return ""
    if p["start"] is None:
        return f"{p['book']} {p['chapter']}"
    return f"{p['book']} {p['chapter']}:{p['start']}" + (f"{dash}{p['end']}" if p["end"] != p["start"] else "")


def caption(p: dict) -> str:
    """A line saying what the picture shows: the title, or the opening of the lines it illustrates."""
    if p.get("quote"):
        return p["quote"].splitlines()[0].rstrip(",;:")
    return p["title"].split(" / ")[0].rstrip(",;:") if p["set"] == "milton" else p["title"]


CAPTION_CHARS = 600                 # (four pictures to a message, and Discord allows 6,000 characters)


@functools.lru_cache(maxsize=512)
def passage_caption(span: str) -> str:
    """The verses a picture shows, from the bot's own text (the KJV for the Bible), in italics; a long
    passage is cut after the verse, or sentence, that passes CAPTION_CHARS ("Read it" has the rest)."""
    result = lookup.get_verse(span)
    if not result.get("found"):
        return ""
    parts = re.split(r"\*\*\[(\d+)\]\*\*\s*", result["text"])          # ["", "1", text, "2", text, ...]
    verses = list(zip(parts[1::2], parts[2::2])) or [("", result["text"])]
    poetry = "\n" in verses[0][1].strip()               # (a verse of several lines: Dante's tercets, Milton)
    out, size = [], 0
    for n, text in verses:
        if size > CAPTION_CHARS:
            out.append("*…*")
            break
        text = text.replace("*", "").strip()
        if poetry:                                      # (Dante, Milton: keep the lines, a number on each group)
            rows = [line.strip() for line in text.splitlines() if line.strip()]
            out.append("\n".join((f"{n} " if i == 0 and len(verses) > 1 else "") + f"*{r}*" for i, r in enumerate(rows)))
        else:
            text = " ".join(text.split())
            if len(text) > CAPTION_CHARS + 200:         # (one long paragraph: Bunyan's)
                cut = max(text.rfind(". ", 0, CAPTION_CHARS), text.rfind("; ", 0, CAPTION_CHARS))
                text = text[:cut + 1 if cut > 0 else CAPTION_CHARS] + " …"
            out.append((f"{n} " if len(verses) > 1 else "") + f"*{text}*")
        size += len(text)
    return "\n".join(out)


def plate_embed(p: dict) -> discord.Embed:
    name, emoji, _ = ARTIST[p["artist"]]
    if p["set"] == "milton":
        title = reference(p)
        description = f"*{p['title']}*"
        read = f"!verse {reference(p, '-')}"
    elif p["set"] == "dante":
        if p.get("quote"):                             # Doré's: the lines it shows, from the bot's Longfellow
            title, read = reference(p), f"!verse {reference(p, '-')}"
            description = "\n".join(f"*{line}*" for line in p["quote"].splitlines())
        elif p["book"]:                                # Blake's: its title, then the lines it shows
            title, read = p["title"], f"!verse {reference(p, '-')}"
            text = passage_caption(reference(p, "-"))
            description = f"**{reference(p)}**" + (f"\n{text}" if text else "")
        else:                                          # (Doré's portrait of Dante)
            title, description, read = p["title"], None, ""
    else:
        span = f"{p['book']} {p['chapter']}:{p['start']}" + (f"-{p['end']}" if p["end"] != p["start"] else "") \
            if p["start"] else f"{p['book']} {p['chapter']}"
        text = passage_caption(span) if p["start"] else ""
        title, read = p["title"], f"!verse {span}"
        description = f"**{reference(p)}**" + (f"\n{text}" if text else "")
        more = [f"{p['book']} {c}:{a}" + (f"–{b}" if b != a else "") for c, a, b in (p.get("passages") or [])[1:]]
        more += [r.replace("-", "–") for r in p.get("also", [])]
        if more:
            description += "\n\nAlso engraved on the plate: " + " · ".join(more)
    embed = discord.Embed(title=f"{emoji} {title}", url=p["page"], description=description,
                          color=COLOR if p["artist"] == "dore" else BLAKE_COLOR)
    if read:
        embed.add_field(name="Read it", value=f"`{read}`", inline=False)
    local = _local_file(p)
    embed.set_image(url=f"attachment://{local.name}" if local else p["image"])
    embed.set_footer(text=f"{name}, {WORKS[(p['artist'], p['set'])]} · "
                          + ("scan: Wikimedia Commons" if local else "image: Wikimedia Commons"))
    return embed


def _local_file(p: dict):
    """The engraving cut out of its page scan (most Dante plates), if the build made it."""
    path = ROOT / p["file"] if p.get("file") else None
    return path if path and path.exists() else None


def plate_message(shown: list) -> dict:
    """send() arguments for some plates: their embeds, and the cut-out engravings attached."""
    files = [discord.File(_local_file(p)) for p in shown if _local_file(p)]
    return {"embeds": [plate_embed(p) for p in shown], **({"files": files} if files else {})}


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
        found = [by_key()[k] for k in self.keys if k in by_key()]
        if not found:
            await interaction.response.send_message("⚠️ I can't find that picture any more.", ephemeral=True)
            return
        artist = "dore" if self.artist == "dore" else "blake"
        await interaction.response.send_message(index(found, artist), **plate_message(found[:MAX_SHOWN]))


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
    return [p for p in plates(artist) if words and all(
        w in " ".join((p["title"], p.get("cited", ""), p.get("quote", ""))).lower() for w in words)]


async def send_art(ctx, query: str, artist: str = "dore") -> bool:
    """A passage's pictures, a book's, or ones found by name; False (nothing sent) if there are none."""
    q = query.strip()
    found, note = [], None
    m = REF.match(q)
    if m:
        book = lookup._resolve_book(m["book"])[1]
        if book:
            start = int(m["v1"]) if m["v1"] else None
            found = for_passage(book, int(m["ch"]), start, int(m["v2"]) if m["v2"] else start, artist)
            if not found and start is not None:         # nothing at that verse: the chapter's, then
                found = for_passage(book, int(m["ch"]), artist=artist)
                if found:
                    note = f"There's no picture at **{book} {m['ch']}:{m['v1']}** itself; here are chapter {m['ch']}'s."
    if not found:
        book = lookup._resolve_book(q)[1]
        if book:
            found = [p for p in plates(artist) if p["book"] == book]
    found = found or search(q, artist)
    if not found:
        return False
    text = "\n".join(t for t in (note, index(found, artist)) if t) or None
    await ctx.send(text, **plate_message(found[:MAX_SHOWN]))
    return True


MAX_LISTED = 20


def index(found: list, artist: str = "dore") -> "str | None":
    """For several pictures: each one's reference and what it shows, with the command for it alone."""
    if len(found) < 2:
        return None
    command = "!dore" if artist == "dore" else "!blake"
    lines = [f"**{len(found)} pictures** — ask for one by its reference:"]
    for p in found[:MAX_LISTED]:
        ref = reference(p, "-")
        pick = ref.split("-")[0] if ref else ""
        lines.append(f"`{command} {pick}` — {caption(p)}" if pick else f"· {caption(p)}")
    if len(found) > MAX_LISTED:
        lines.append(f"…and {len(found) - MAX_LISTED} more: ask for a chapter to narrow it.")
    if len(found) > MAX_SHOWN:
        lines.append(f"*Showing the first {MAX_SHOWN}.*")
    return "\n".join(lines)[:1990]


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
            "`!dore Genesis 11` · `!dore Inferno 3` · `!dore Paradise Lost 1` — a chapter's engravings, "
            "listed with the verse or line each one shows\n"
            "`!dore Genesis 11:4` · `!dore Inferno 3:82` — just the one at that verse or line\n"
            "`!dore babel` — by name\n\n"
            "Under `!verse`, a 🖼️ Doré button appears whenever the passage has one.")))
        return
    if not q:
        await ctx.send(**plate_message([random.choice(plates())]))
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
           !dore Genesis 11    — a chapter's engravings, listed (also Inferno 3, Paradise Lost 1)
           !dore Genesis 11:4  — the one at that verse (also Inferno 3:82)
           !dore babel         — by name · !dore list"""
    await send_dore(ctx, query)


@bot.tree.command(name="dore", description="Gustave Doré's engravings for the Bible, Dante and Milton")
@discord.app_commands.describe(query="A passage (Genesis 11, Inferno 3, Paradise Lost 1), a name, or 'list'; empty for a random one")
async def dore_slash(interaction: discord.Interaction, query: str = ""):
    await interaction.response.defer()
    await send_dore(await bot.get_context(interaction), query)
