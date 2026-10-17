"""
!divineliturgy -- the Divine Liturgy of St John Chrysostom, the Orthodox Church's Sunday
service, a page at a time (data/liturgy/chrysostom.json, built by scripts/build_liturgy.py
from an 1866 English translation): ◀ ▶ to turn the pages and a menu of its parts.
(!liturgy is already !today's alias.)
"""
import functools
import json
import re

import discord

from core import ROOT, bot

DATA_PATH = ROOT / "data" / "liturgy" / "chrysostom.json"
COLOR = discord.Color.from_rgb(150, 30, 40)


@functools.lru_cache(maxsize=1)
def liturgy() -> dict:
    return json.loads(DATA_PATH.read_text(encoding="utf-8")) if DATA_PATH.exists() else {"pages": []}


def sections() -> list:
    """[(name, its first page)] in order."""
    out = []
    for i, p in enumerate(liturgy()["pages"]):
        if not out or out[-1][0] != p["section"]:
            out.append((p["section"], i))
    return out


def page_embed(page: int) -> discord.Embed:
    pages = liturgy()["pages"]
    p = pages[page]
    embed = discord.Embed(title=f"☦️ {p['section']}", description=p["text"][:4096], color=COLOR)
    embed.set_author(name=liturgy()["title"])
    embed.set_footer(text=f"Page {page + 1} of {len(pages)} · rubrics (what the clergy do) in italics · "
                          f"translation of 1866")
    return embed


class LiturgyButton(discord.ui.DynamicItem[discord.ui.Button], template=r"dlit:(?P<action>back|next):(?P<page>\d+)"):
    """◀ ▶ (distinct "back"/"next" ids); persistent, so they work after a restart."""

    def __init__(self, action: str, page: int):
        super().__init__(discord.ui.Button(emoji="◀" if action == "back" else "▶", style=discord.ButtonStyle.secondary,
                                           custom_id=f"dlit:{action}:{page}"))
        self.page = page

    @classmethod
    async def from_custom_id(cls, interaction, item, match):
        return cls(match["action"], int(match["page"]))

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.edit_message(embed=page_embed(self.page), view=liturgy_view(self.page))


class LiturgyMenu(discord.ui.DynamicItem[discord.ui.Select], template=r"dlitmenu"):
    """Jump to a part of the service. The option values are page numbers, so it keeps working
    after a restart."""

    def __init__(self):
        options = [discord.SelectOption(label=name[:100], value=str(first)) for name, first in sections()][:25]
        super().__init__(discord.ui.Select(placeholder="Go to a part of the Liturgy…", options=options,
                                           custom_id="dlitmenu"))

    @classmethod
    async def from_custom_id(cls, interaction, item, match):
        menu = cls.__new__(cls)
        discord.ui.DynamicItem.__init__(menu, item)
        return menu

    async def callback(self, interaction: discord.Interaction):
        page = int(self.item.values[0])
        await interaction.response.edit_message(embed=page_embed(page), view=liturgy_view(page))


bot.add_dynamic_items(LiturgyButton, LiturgyMenu)


def liturgy_view(page: int) -> discord.ui.View:
    view = discord.ui.View(timeout=None)                 # persistent: must never time out
    n = len(liturgy()["pages"])
    if page > 0:
        view.add_item(LiturgyButton("back", page - 1))
    if page < n - 1:
        view.add_item(LiturgyButton("next", page + 1))
    view.add_item(LiturgyMenu())
    return view


def find_section(query: str) -> "int | None":
    q = re.sub(r"[^a-z ]", "", query.lower()).strip()
    for name, first in sections():
        if q and q in name.lower():
            return first
    return None


async def send_liturgy(ctx, query: str = "") -> None:
    if not liturgy()["pages"]:
        await ctx.send("⚠️ The Divine Liturgy isn't available right now.")
        return
    q = query.strip()
    page = 0
    if q:
        if q.isdigit() and 1 <= int(q) <= len(liturgy()["pages"]):
            page = int(q) - 1
        else:
            found = find_section(q)
            if found is None:
                names = ", ".join(n for n, _ in sections())
                await ctx.send(f"There's no part of the Liturgy called **{discord.utils.escape_markdown(q)}**. "
                               f"The parts: {names}.")
                return
            page = found
    content = None
    if page == 0:
        content = ("☦️ **The Divine Liturgy of St John Chrysostom**: the service most Orthodox churches celebrate "
                   "every Sunday. ◀ ▶ turn the pages; the menu goes to any part.")
    await ctx.send(content=content, embed=page_embed(page), view=liturgy_view(page))


@bot.command(name="divineliturgy", aliases=["chrysostomliturgy", "orthodoxliturgy"])
async def cmd_divineliturgy(ctx, *, query: str = ""):
    """The Divine Liturgy of St John Chrysostom, a page at a time.
    Usage: !divineliturgy           — from the beginning
           !divineliturgy creed     — a part of the service by name
           !divineliturgy 20        — a page"""
    await send_liturgy(ctx, query)


@bot.tree.command(name="divineliturgy", description="The Orthodox Divine Liturgy of St John Chrysostom, page by page")
@discord.app_commands.describe(part="A part of the service (creed, anaphora, communion…) or a page number")
async def divineliturgy_slash(interaction: discord.Interaction, part: str = ""):
    await interaction.response.defer()
    ctx = await bot.get_context(interaction)
    await send_liturgy(ctx, part)
