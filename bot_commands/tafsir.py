"""
The 📖 Commentary button under Qur'an verses in !verse: what the classical commentators (tafsir) say about them.
Three English commentaries, downloaded into data/tafsir/ by scripts/fetch_tafsir.py:

    Tafsir al-Jalalayn (al-Mahalli and al-Suyuti, trans. Feras Hamza) -- short, a gloss on every verse;
    Tafsir Ibn Kathir (abridged) -- long, one commentary on a run of verses, with the hadith it cites;
    Tanwir al-Miqbas, attributed to Ibn 'Abbas (trans. Mokrane Guezzou).

The reply is private (ephemeral), opens on the Jalalayn, and has a menu to switch commentary and ◀ ▶ through
its pages. The button carries the reference, so it works after a restart.
"""
import json
import re

import discord

from core import ROOT, bot

TAFSIR_DIR = ROOT / "data" / "tafsir"
ORDER = ["jalalayn", "ibnkathir", "ibnabbas"]
COLOR = discord.Color.dark_green()
PAGE = 3500
_DATA: dict = {}
_REF = re.compile(r"^Quran (\d{1,3})(?::(\d{1,3})(?:[–-](\d{1,3}))?)?(?: \([^)]*\))?$")


def tafsir(key: str) -> dict:
    """{"name", "source", "surahs": {surah: {ayah: text | {"text", "to"}}}} or {} if it isn't downloaded."""
    if key not in _DATA:
        try:
            _DATA[key] = json.loads((TAFSIR_DIR / f"{key}.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            _DATA[key] = {}
    return _DATA[key]


def available() -> list:
    return [k for k in ORDER if tafsir(k).get("surahs")]


def parse(ref: str):
    """(surah, first ayah, last ayah) from "Quran 2:255", "Quran 2:1–5" or "Quran 112" (the whole surah: last is
    None), or None."""
    m = _REF.match(ref or "")
    if not m or not 1 <= int(m[1]) <= 114:
        return None
    first = int(m[2]) if m[2] else 1
    last = int(m[3]) if m[3] else (first if m[2] else None)
    return int(m[1]), first, last


def entries(key: str, surah: int, first: int, last) -> list:
    """[(label, text)] of one commentary for the verses: each entry once, labelled with the verses it covers."""
    verses = tafsir(key).get("surahs", {}).get(str(surah), {})
    out = []
    for a in sorted(verses, key=int):
        v = verses[a]
        text, to = (v, int(a)) if isinstance(v, str) else (v["text"], int(v["to"]))
        if to < first or (last is not None and int(a) > last):
            continue
        out.append((f"{surah}:{a}" + (f"–{to}" if to != int(a) else ""), text))
    return out


def clean(text: str) -> str:
    """Safe for Discord: Ibn Kathir's ` for ʿayn would open code formatting, so it's ‘; other markdown escaped."""
    return discord.utils.escape_markdown(text.replace("`", "‘"))


def pages_of(key: str, surah: int, first: int, last) -> list:
    pages, current = [], ""
    for label, text in entries(key, surah, first, last):
        block = f"**{label}**\n{clean(text)}"
        while len(block) > PAGE:                       # (a commentary longer than a page: cut at a paragraph)
            cut = block.rfind("\n", 0, PAGE)
            cut = cut if cut > PAGE // 2 else block.rfind(" ", 0, PAGE)
            if current:
                pages.append(current)
                current = ""
            pages.append(block[:cut].rstrip())
            block = block[cut:].lstrip()
        if current and len(current) + len(block) + 2 > PAGE:
            pages.append(current)
            current = block
        else:
            current = f"{current}\n\n{block}" if current else block
    if current:
        pages.append(current)
    return pages


def embed_for(key: str, ref: str, pages: list, page: int) -> discord.Embed:
    data = tafsir(key)
    embed = discord.Embed(title=f"📖 {data.get('name', key)} on {ref}", color=COLOR,
                          description=pages[page] if pages else "This commentary has nothing on these verses.")
    footer = data.get("source", "")
    if len(pages) > 1:
        footer += f" · page {page + 1} of {len(pages)}"
    embed.set_footer(text=footer)
    return embed


class CommentaryView(discord.ui.View):
    """The private reply: a menu of commentaries and ◀ ▶ through the pages. (Not persistent: an ephemeral
    message doesn't outlive the session, and a timed-out view must hold no dynamic items.)"""

    def __init__(self, ref: str, parsed: tuple, key: str):
        super().__init__(timeout=900)
        self.ref, self.parsed, self.key, self.page = ref, parsed, key, 0
        self.pages = pages_of(key, *parsed)
        menu = discord.ui.Select(placeholder="Another commentary…", row=0, options=[
            discord.SelectOption(label=tafsir(k)["name"], value=k, description=tafsir(k)["source"][:100],
                                 default=k == key) for k in available()])
        menu.callback = self.switch
        self.add_item(menu)
        self.menu = menu
        self.prev = discord.ui.Button(label="◀", style=discord.ButtonStyle.secondary, row=1)
        self.next = discord.ui.Button(label="▶", style=discord.ButtonStyle.secondary, row=1)
        self.prev.callback, self.next.callback = self.back, self.forward
        self.add_item(self.prev)
        self.add_item(self.next)
        self.refresh()

    def refresh(self):
        self.prev.disabled = self.page <= 0
        self.next.disabled = self.page >= len(self.pages) - 1
        for o in self.menu.options:
            o.default = o.value == self.key

    async def show(self, interaction: discord.Interaction):
        self.refresh()
        await interaction.response.edit_message(embed=embed_for(self.key, self.ref, self.pages, self.page), view=self)

    async def switch(self, interaction: discord.Interaction):
        self.key, self.page = self.menu.values[0], 0
        self.pages = pages_of(self.key, *self.parsed)
        await self.show(interaction)

    async def back(self, interaction: discord.Interaction):
        self.page = max(0, self.page - 1)
        await self.show(interaction)

    async def forward(self, interaction: discord.Interaction):
        self.page = min(len(self.pages) - 1, self.page + 1)
        await self.show(interaction)


class CommentaryButton(discord.ui.DynamicItem[discord.ui.Button], template=r"tafsir:(?P<ref>Quran [0-9:–-]{1,12})"):
    """📖 Commentary under a Qur'an passage."""

    def __init__(self, ref: str):
        super().__init__(discord.ui.Button(label="Commentary", emoji="📖", style=discord.ButtonStyle.secondary,
                                           row=1, custom_id=f"tafsir:{ref}"))
        self.ref = ref

    @classmethod
    async def from_custom_id(cls, interaction, item, match):
        return cls(match["ref"])

    async def callback(self, interaction: discord.Interaction):
        parsed, keys = parse(self.ref), available()
        if not parsed or not keys:
            await interaction.response.send_message("The commentaries aren't available right now.", ephemeral=True)
            return
        view = CommentaryView(self.ref, parsed, keys[0])
        await interaction.response.send_message(embed=embed_for(view.key, self.ref, view.pages, 0), view=view,
                                                ephemeral=True)


bot.add_dynamic_items(CommentaryButton)


def commentary_buttons(result: dict) -> list:
    """The 📖 Commentary button for a Qur'an passage that a commentary covers; [] for anything else."""
    if not result.get("found"):
        return []
    ref = re.sub(r" \([^)]*\)$", "", result.get("reference", ""))
    parsed = parse(ref)
    if not parsed or not any(entries(k, *parsed) for k in available()):
        return []
    return [CommentaryButton(ref)]
