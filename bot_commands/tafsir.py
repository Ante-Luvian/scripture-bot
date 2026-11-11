"""
The 📖 Commentary button under Qur'an verses in !verse: what the classical commentators (tafsir) say about them.
Six English commentaries, downloaded into data/tafsir/ by scripts/fetch_tafsir.py:

    Tafsir al-Jalalayn (al-Mahalli and al-Suyuti, trans. Feras Hamza) -- short, a gloss on every verse;
    Tafsir Ibn Kathir (abridged) -- long, one commentary on a run of verses, with the hadith it cites;
    Tanwir al-Miqbas, attributed to Ibn 'Abbas (trans. Mokrane Guezzou);
    al-Wahidi's Asbab al-Nuzul, the occasions on which verses were revealed (trans. Mokrane Guezzou) -- only the
    verses it has a story for (2026-11-11);
    the Sufi commentary of Sahl al-Tustari (trans. Annabel and Ali Keeler) -- selected verses (2026-11-11);
    the Sufi commentary of al-Kashani (trans. Feras Hamza), long, a page or more on most verses (2026-11-11).

The reply is posted for everyone (the owner, 2026-11-11), opens on the Jalalayn, and has a menu to switch
commentary, ◀ ▶ through its pages when it has more than one, and buttons to the verse before and after. Every control
carries its state in its custom_id, so they all work after a restart.
"""
import json
import re

import discord

from core import ROOT, bot

TAFSIR_DIR = ROOT / "data" / "tafsir"
ORDER = ["jalalayn", "ibnkathir", "ibnabbas", "wahidi", "tustari", "kashani"]
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
    empty = "This commentary has nothing on these verses."
    parsed = parse(ref)
    if not pages and data.get("covers") and parsed and parsed[0] > data["covers"]:
        # (Hamza's English Kashani goes only to surah 18)
        empty = f"This translation of {data.get('name', key)} goes only as far as surah {data['covers']}."
    embed = discord.Embed(title=f"📖 {data.get('name', key)} on {ref}", color=COLOR,
                          description=pages[page] if pages else empty)
    footer = data.get("source", "")
    if len(pages) > 1:
        footer += f" · page {page + 1} of {len(pages)}"
    embed.set_footer(text=footer)
    return embed


# How many verses each surah has (for the ▶ next verse at a surah's end)
AYAH_COUNTS = [7, 286, 200, 176, 120, 165, 206, 75, 129, 109, 123, 111, 43, 52, 99, 128, 111, 110, 98, 135, 112, 78,
               118, 64, 77, 227, 93, 88, 69, 60, 34, 30, 73, 54, 45, 83, 182, 88, 75, 85, 54, 53, 89, 59, 37, 35, 38, 29,
               18, 45, 60, 49, 62, 55, 78, 96, 29, 22, 24, 13, 14, 11, 11, 18, 12, 12, 30, 52, 52, 44, 28, 28, 20, 56,
               40, 31, 50, 40, 46, 42, 29, 19, 36, 25, 22, 17, 19, 26, 30, 20, 15, 21, 11, 8, 8, 19, 5, 8, 8, 11, 11, 8,
               3, 9, 5, 4, 7, 3, 6, 3, 5, 4, 5, 6]


def ref_of(surah: int, first: int, last) -> str:
    if last is None:
        return f"Quran {surah}"
    return f"Quran {surah}:{first}" + (f"–{last}" if last != first else "")


def reply(key: str, surah: int, first: int, last, page: int = 0) -> dict:
    """The commentary message (public, 2026-11-11: the owner wants everyone to see it): its embed and its controls --
    a menu of commentaries, ◀ ▶ through the pages when there's more than one, and the verses either side. Every
    control is a DynamicItem carrying its whole state, so they all still work after a restart."""
    keys = available()
    key = key if key in keys else keys[0]
    pages = pages_of(key, surah, first, last)
    page = max(0, min(page, len(pages) - 1))
    view = discord.ui.View(timeout=None)
    view.add_item(CommentaryMenu(key, surah, first, last))
    b = "" if last is None else str(last)
    if len(pages) > 1:
        view.add_item(CommentaryNav(key, surah, first, b, page - 1, "p", "◀ Page", page <= 0))
        view.add_item(CommentaryNav(key, surah, first, b, page + 1, "n", "Page ▶", page >= len(pages) - 1))
    if last is not None:
        covered = max([last] + [int(re.split(r"[:–]", label)[-1]) for label, _ in entries(key, surah, first, last)])
        if first > 1:
            view.add_item(CommentaryNav(key, surah, first - 1, str(first - 1), 0, "v", f"◀ {surah}:{first - 1}"))
        if covered < AYAH_COUNTS[surah - 1]:
            view.add_item(CommentaryNav(key, surah, covered + 1, str(covered + 1), 0, "w", f"{surah}:{covered + 1} ▶"))
    return {"embed": embed_for(key, ref_of(surah, first, last), pages, page), "view": view}


_STATE = r"(?P<s>\d{1,3}):(?P<a>\d{1,3}):(?P<b>\d{0,3})"


def _state(match) -> tuple:
    s, a = int(match["s"]), int(match["a"])
    return s, a, int(match["b"]) if match["b"] else None


class CommentaryNav(discord.ui.DynamicItem[discord.ui.Button],
                    template=r"tafn:(?P<key>[a-z]{1,20}):" + _STATE + r":(?P<p>\d{1,3}):(?P<tag>[pnvw])"):
    """◀ ▶ through a commentary's pages, or to the verse before or after."""

    def __init__(self, key, surah, first, last: str, page, tag, label="▶", disabled=False):
        super().__init__(discord.ui.Button(label=label, style=discord.ButtonStyle.secondary, row=1, disabled=disabled,
                                           custom_id=f"tafn:{key}:{surah}:{first}:{last}:{max(page, 0)}:{tag}"))
        self.key, self.surah, self.first, self.page = key, surah, first, max(page, 0)
        self.last = int(last) if last else None

    @classmethod
    async def from_custom_id(cls, interaction, item, match):
        s, a, b = _state(match)
        return cls(match["key"], s, a, "" if b is None else str(b), int(match["p"]), match["tag"])

    async def callback(self, interaction: discord.Interaction):
        if not available():
            await interaction.response.send_message("The commentaries aren't available right now.", ephemeral=True)
            return
        await interaction.response.edit_message(**reply(self.key, self.surah, self.first, self.last, self.page))


class CommentaryMenu(discord.ui.DynamicItem[discord.ui.Select], template=r"tafk:" + _STATE):
    """The menu of commentaries."""

    def __init__(self, key, surah, first, last):
        super().__init__(discord.ui.Select(
            placeholder="Another commentary…", row=0,
            custom_id=f"tafk:{surah}:{first}:{'' if last is None else last}",
            options=[discord.SelectOption(label=tafsir(k)["name"], value=k, description=tafsir(k)["source"][:100],
                                          default=k == key) for k in available()] or
                    [discord.SelectOption(label="(none)", value="none")]))
        self.surah, self.first, self.last = surah, first, last

    @classmethod
    async def from_custom_id(cls, interaction, item, match):
        s, a, b = _state(match)
        return cls("", s, a, b)

    async def callback(self, interaction: discord.Interaction):
        values = (interaction.data or {}).get("values") or []
        if not available() or not values:
            await interaction.response.send_message("The commentaries aren't available right now.", ephemeral=True)
            return
        await interaction.response.edit_message(**reply(values[0], self.surah, self.first, self.last))


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
        await interaction.response.send_message(**reply(keys[0], *parsed))


bot.add_dynamic_items(CommentaryButton, CommentaryNav, CommentaryMenu)


def commentary_buttons(result: dict) -> list:
    """The 📖 Commentary button for a Qur'an passage that a commentary covers; [] for anything else."""
    if not result.get("found"):
        return []
    ref = re.sub(r" \([^)]*\)$", "", result.get("reference", ""))
    parsed = parse(ref)
    if not parsed or not any(entries(k, *parsed) for k in available()):
        return []
    return [CommentaryButton(ref)]
