"""
📖 Commentary under a Bible verse, as under a Qur'an verse: what the Fathers and the Church's tradition say about it,
from the library's own texts (data/catena_index.json; bot_commands/catena_local.py). A menu of the commentaries on
that verse -- Aquinas's Catena Aurea, a commentary or homilies on that book (Chrysostom, Augustine, Gregory...), the
Breviary's homily, and the Fathers quoting it -- ◀ ▶ through one's pages, and the verses either side. Every control
carries its state in its custom_id, so they work after a restart. (It replaced the 📜 Catena button and !catena's
scraping of catenabible.com, 2026-11-11.)
"""
import functools
import re

import discord

from bot_commands import catena_local as C
from core import bot, lookup

COLOR = discord.Color.dark_gold()
PAGE = 3600


@functools.lru_cache(maxsize=1)
def books() -> list:
    """The Bible's books in order (a button carries a book as its place here)."""
    return list(lookup._data.get("kjv", {}))


def verse_count(book: str, ch: int) -> int:
    return len(lookup._data.get("kjv", {}).get(book, {}).get(str(ch), {}))


@functools.lru_cache(maxsize=512)
def groups(book: str, ch: int, v: int) -> list:
    """[(menu label, its description, [section texts])] for a verse: the Catena Aurea; each commentary on the book;
    the Breviary's homilies; the Fathers quoting it."""
    entries = C.index().get(f"{book} {ch}:{v}", [])
    out, quoted = [], []
    for who, body in C.sections(book, ch, v):
        work = body.rsplit("— *", 1)[-1].rstrip("*")
        who = who.replace("*", "").strip()
        text = f"**{who}**\n{body}"
        if who.endswith("(in the Catena Aurea)"):
            if not out or out[0][0] != "The Catena Aurea":
                out.insert(0, ("The Catena Aurea", "Aquinas's chain of the Fathers on the Gospels", []))
            plain = body.rsplit("\n\n— *", 1)[0]                          # (the group says whose chain it is)
            out[0][2].append(f"**{who.replace(' (in the Catena Aurea)', '')}**\n{plain}")
            continue
        rank = next((e[0] for e in entries if e[1] == work or work.startswith("Aquinas")), 3)
        if work == "Readings from the Breviary" or rank == 2:
            label = f"{who}: {work}" if work != "Readings from the Breviary" else f"The Breviary: {who}"
            found = next((g for g in out if g[0] == label[:100]), None)
            if found:
                found[2].append(text)
            else:
                out.append((label[:100], who[:100] if work != "Readings from the Breviary" else "Read at Matins",
                            [text]))
        else:
            quoted.append(text)
    if quoted:
        out.append((f"Quoted by the Fathers ({len(quoted)})", "Where the Fathers quote this verse", quoted))
    return out


def pages_of(texts: list) -> list:
    pages, cur = [], ""
    for t in texts:
        while len(t) > PAGE:
            cut = t.rfind("\n", 0, PAGE)
            cut = cut if cut > PAGE // 2 else PAGE
            if cur:
                pages.append(cur)
                cur = ""
            pages.append(t[:cut])
            t = t[cut:].lstrip()
        if cur and len(cur) + len(t) + 2 > PAGE:
            pages.append(cur)
            cur = t
        else:
            cur = f"{cur}\n\n{t}" if cur else t
    return pages + ([cur] if cur else [])


def reply(book: str, ch: int, v: int, g: int = 0, page: int = 0) -> dict:
    found = groups(book, ch, v)
    ref = f"{book} {ch}:{v}"
    verse = lookup._data.get("kjv", {}).get(book, {}).get(str(ch), {}).get(str(v), "")
    view = discord.ui.View(timeout=None)
    b = books().index(book)
    if found:
        g = max(0, min(g, len(found) - 1))
        label, desc, texts = found[g]
        pages = pages_of(texts)
        page = max(0, min(page, len(pages) - 1))
        body = (f"*{verse}*\n\n" if verse and page == 0 else "") + pages[page]
        embed = discord.Embed(title=f"📖 {label} on {ref}"[:256], description=body[:4096], color=COLOR)
        embed.set_footer(text=f"{desc}" + (f" · page {page + 1} of {len(pages)}" if len(pages) > 1 else "")
                              + " · from the library's Fathers")
        view.add_item(Menu(b, ch, v, found, g))
        if len(pages) > 1:
            view.add_item(Nav(b, ch, v, g, page - 1, "p", "◀ Page", page <= 0))
            view.add_item(Nav(b, ch, v, g, page + 1, "n", "Page ▶", page >= len(pages) - 1))
    else:
        embed = discord.Embed(title=f"📖 {ref}", color=COLOR,
                              description=(f"*{verse}*\n\n" if verse else "") + "The library has no commentary from the "
                              "Fathers on this verse yet. (The Gospels and the Psalms are covered fully, most of the "
                              "New Testament, and parts of the Old.)")
    if v > 1:
        view.add_item(Nav(b, ch, v - 1, 0, 0, "v", f"◀ {ch}:{v - 1}"))
    if v < verse_count(book, ch):
        view.add_item(Nav(b, ch, v + 1, 0, 0, "w", f"{ch}:{v + 1} ▶"))
    return {"embed": embed, "view": view}


_STATE = r"(?P<b>\d{1,2}):(?P<c>\d{1,3}):(?P<v>\d{1,3})"


class Nav(discord.ui.DynamicItem[discord.ui.Button],
          template=r"bcn:" + _STATE + r":(?P<g>\d{1,2}):(?P<p>\d{1,3}):(?P<tag>[pnvw])"):
    """◀ ▶ through a commentary's pages, or to the verse before or after."""

    def __init__(self, b, ch, v, g, page, tag, label="▶", disabled=False):
        super().__init__(discord.ui.Button(label=label, style=discord.ButtonStyle.secondary, row=1, disabled=disabled,
                                           custom_id=f"bcn:{b}:{ch}:{v}:{g}:{max(page, 0)}:{tag}"))
        self.b, self.ch, self.v, self.g, self.page = b, ch, v, g, max(page, 0)

    @classmethod
    async def from_custom_id(cls, interaction, item, m):
        return cls(int(m["b"]), int(m["c"]), int(m["v"]), int(m["g"]), int(m["p"]), m["tag"])

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.edit_message(**reply(books()[self.b], self.ch, self.v, self.g, self.page))


class Menu(discord.ui.DynamicItem[discord.ui.Select], template=r"bck:" + _STATE):
    """The menu of commentaries on the verse."""

    def __init__(self, b, ch, v, found=None, g=0):
        found = found if found is not None else groups(books()[b], ch, v)
        super().__init__(discord.ui.Select(
            placeholder="Another commentary…", row=0, custom_id=f"bck:{b}:{ch}:{v}",
            options=[discord.SelectOption(label=label[:100], value=str(i), description=desc[:100], default=i == g)
                     for i, (label, desc, _) in enumerate(found[:25])] or [discord.SelectOption(label="(none)",
                                                                                              value="0")]))
        self.b, self.ch, self.v = b, ch, v

    @classmethod
    async def from_custom_id(cls, interaction, item, m):
        return cls(int(m["b"]), int(m["c"]), int(m["v"]))

    async def callback(self, interaction: discord.Interaction):
        values = (interaction.data or {}).get("values") or ["0"]
        await interaction.response.edit_message(**reply(books()[self.b], self.ch, self.v, int(values[0])))


class Button(discord.ui.DynamicItem[discord.ui.Button], template=r"bcom:(?P<ref>[1-3]?[A-Za-z ]{2,30} \d{1,3}:\d{1,3})"):
    """📖 Commentary under a Bible verse."""

    def __init__(self, ref: str):
        super().__init__(discord.ui.Button(label="Commentary", emoji="📖", style=discord.ButtonStyle.secondary,
                                           row=1, custom_id=f"bcom:{ref}"))
        self.ref = ref

    @classmethod
    async def from_custom_id(cls, interaction, item, match):
        return cls(match["ref"])

    async def callback(self, interaction: discord.Interaction):
        book, ch, v = parse(self.ref)
        await interaction.response.send_message(**reply(book, ch, v))


bot.add_dynamic_items(Button, Nav, Menu)


def parse(ref: str):
    m = re.match(r"(.+?) (\d+):(\d+)", ref)
    return (m[1], int(m[2]), int(m[3])) if m else (None, 0, 0)


def button_for(book: str, ch: int, v: int) -> list:
    """The 📖 Commentary button for a Bible verse the library has commentary on; [] otherwise."""
    if book in books() and C.index().get(f"{book} {ch}:{v}"):
        return [Button(f"{book} {ch}:{v}")]
    return []
