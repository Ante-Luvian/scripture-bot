"""
!story -- the same story as different traditions tell it: the Flood in Genesis,
Gilgamesh, Ovid, the Quran and the Popol Vuh, side by side; and the pagan texts
early Christians read as foretelling Christ, each with the Christian who read it so.

The stories are a curated table, data/stories.json: a reference and a quotation
for each passage, both checked against the loaded text by tests/test_stories.py.
"""
import functools
import json
import re
import unicodedata

import discord
from discord import app_commands

from core import ROOT, _build_embed, bot, lookup

STORIES_PATH = ROOT / "data" / "stories.json"
COLOR = discord.Color.from_rgb(70, 90, 120)
EMOJI = {"flood": "🌊", "creation": "🌌", "humans": "🏺", "tower": "🗼", "underworld": "🔥", "ages": "⏳",
         "end": "🌑", "christ": "✝️"}
EXCERPT = 230


@functools.lru_cache(maxsize=1)
def stories() -> dict:
    return json.loads(STORIES_PATH.read_text(encoding="utf-8"))["stories"]


def _norm(text: str) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()
    return re.sub(r"\s+", " ", re.sub(r"[^a-z ]+", " ", text)).strip()


def find_story(query: str) -> "dict | None":
    q = _norm(query)
    q = re.sub(r"^the ", "", q)
    for key, story in stories().items():
        names = [key, story["title"], *story.get("aliases", [])]
        if q in {re.sub(r"^the ", "", _norm(n)) for n in names}:
            return {**story, "key": key}
    for key, story in stories().items():                      # a word of the title: "flood", "underworld"
        if q and q in _norm(story["title"]).split():
            return {**story, "key": key}
    return None


def _flat(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"\*\*\[[\w:.]+\]\*\*|\*\*|──[^─]*──", " ", text)).strip()


@functools.lru_cache(maxsize=256)
def excerpt(ref: str, quote: str, length: int = EXCERPT) -> str:
    """The passage from its quotation on, cut at a word near `length`."""
    result = lookup.get_verse(ref)
    text = _flat(result.get("text", "")) if result.get("found") else ""
    at = text.lower().find(_flat(quote).lower())
    if at >= 0:
        # a quotation near the end of its passage ("like a great cross;") keeps some of what leads up to it
        start = at if len(text) - at > length // 2 else max(0, len(text) - length)
        text = ("…" + text[start:].split(" ", 1)[-1]) if start > 0 and start != at else text[start:]
    if len(text) > length:
        text = text[:length].rsplit(" ", 1)[0] + "…"
    return text


def story_embed(story: dict) -> discord.Embed:
    emoji = EMOJI.get(story["key"], "📚")
    embed = discord.Embed(title=f"{emoji} {story['title']}", description=story["intro"], color=COLOR)
    for p in story["passages"]:
        value = f"*{excerpt(p['ref'], p['quote'])}*"
        for r in p.get("read_by", []):
            value += f"\n↳ **{r['who']}** ({r.get('cite', r['ref'])}): “{excerpt(r['ref'], r['quote'], 140)}”"
        if p.get("note"):
            value += f"\n-# {p['note']}"
        embed.add_field(name=f"{p['tradition']} · {p['title']} — {p['ref']}"[:256], value=value[:1024], inline=False)
    embed.set_footer(text="Choose one below to read it in full · !story for the list")
    return embed


class StoryPicker(discord.ui.DynamicItem[discord.ui.Select], template=r"story:(?P<key>[a-z]+)"):
    """Read one of a story's passages in full. Persistent (its options carry the passage's
    number), so it works after a restart."""

    def __init__(self, key: str):
        options = [discord.SelectOption(label=f"{p['title']}"[:100], description=p["ref"][:100], value=str(i))
                   for i, p in enumerate(stories()[key]["passages"][:25])]
        super().__init__(discord.ui.Select(placeholder="Read one in full…", options=options, custom_id=f"story:{key}"))
        self.key = key

    @classmethod
    async def from_custom_id(cls, interaction, item, match):
        picker = cls.__new__(cls)
        discord.ui.DynamicItem.__init__(picker, item)
        picker.key = match["key"]
        return picker

    async def callback(self, interaction: discord.Interaction):
        story = stories().get(self.key)
        if story is None:
            await interaction.response.send_message("I can't find that story any more.", ephemeral=True)
            return
        p = story["passages"][int(self.item.values[0])]
        await interaction.response.send_message(embed=_build_embed(lookup.get_verse(p["ref"])))


bot.add_dynamic_items(StoryPicker)


def list_embed() -> discord.Embed:
    lines = [f"{EMOJI.get(k, '📚')} **{s['title']}** — `!story {k}`\n{s['intro']}" for k, s in stories().items()]
    embed = discord.Embed(title="📚 Stories across the traditions", description="\n\n".join(lines), color=COLOR)
    embed.set_footer(text="The same story as each tradition tells it, side by side")
    return embed


async def send_story(ctx, query: str = "") -> None:
    query = query.strip()
    if not query:
        await ctx.send(embed=list_embed())
        return
    story = find_story(query)
    if story is None:
        await ctx.send(f"I don't have a story called **{discord.utils.escape_markdown(query)}**. "
                       f"`!story` lists them: " + ", ".join(f"`{k}`" for k in stories()))
        return
    view = discord.ui.View(timeout=None)
    view.add_item(StoryPicker(story["key"]))
    await ctx.send(embed=story_embed(story), view=view)


@bot.command(name="story", aliases=["stories", "myth", "myths"])
async def cmd_story(ctx, *, query: str = ""):
    """The same story as different traditions tell it, side by side.
    Usage: !story            — the list
           !story flood      — the Flood in Genesis, Gilgamesh, Ovid, the Quran...
           !story christ     — pagan texts early Christians read as foretelling Christ"""
    await send_story(ctx, query)


async def _story_autocomplete(interaction: discord.Interaction, current: str) -> list:
    q = _norm(current)
    return [app_commands.Choice(name=s["title"][:100], value=k) for k, s in stories().items()
            if not q or q in _norm(s["title"]) or q in k][:25]


@bot.tree.command(name="story", description="The same story as different traditions tell it, side by side")
@app_commands.describe(story="flood, creation, humans, tower, underworld, ages, end, christ (empty for the list)")
@app_commands.autocomplete(story=_story_autocomplete)
async def story_slash(interaction: discord.Interaction, story: str = ""):
    await interaction.response.defer()
    ctx = await bot.get_context(interaction)
    await send_story(ctx, story)
