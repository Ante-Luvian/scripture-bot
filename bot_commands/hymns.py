"""
!hymn: public-domain hymns from the Open Hymnal Project (data/hymns/,
built by scripts/build_hymns.py).
  !hymn amazing grace        by title, first line, or a line from the words
  !hymn christmas            by topic
  !hymn Psalm 23             hymns drawn on a passage
  !hymn                      a random hymn
Each hymn shows its words, who wrote the words and the tune, and the Bible
passages it draws on, with buttons to hear the tune (an organ rendering of
the four-part score, rendered ahead by scripts/render_hymn_audio.py and
sent as an .ogg) and to read those passages.
"""
import functools
import json
import random
import re
import unicodedata
import zlib

import discord
from discord import app_commands

from core import ROOT, bot, lookup

HYMNS_PATH = ROOT / "data" / "hymns" / "hymns.json"
MIDI_DIR = ROOT / "data" / "hymns" / "midi"
AUDIO_DIR = ROOT / "data" / "hymns" / "audio"
COLOR = discord.Color.from_rgb(120, 60, 110)
MAX_LIST = 20


@functools.lru_cache(maxsize=1)
def hymns() -> list:
    return json.loads(HYMNS_PATH.read_text(encoding="utf-8"))["hymns"]


def hymn_key(hymn: dict) -> str:
    """A short, stable id for a hymn's buttons."""
    return f"{zlib.crc32(hymn['title'].encode('utf-8')):08x}"


def by_key(key: str) -> "dict | None":
    return next((h for h in hymns() if hymn_key(h) == key), None)


def _norm(text: str) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()
    text = re.sub(r"[^a-z0-9 ]+", " ", text.replace("'", ""))
    return re.sub(r"\s+", " ", text).strip()


# ── Bible passages ──────────────────────────────────────────────────────────

_REF = re.compile(r"^(.+?)\s+(\d+)(?::(\d+)(?:-(\d+))?)?$")


def _parse_ref(ref: str) -> "tuple | None":
    """'Psalms 63:6-8' -> ('Psalms', 63, 6, 8); 'Psalms 148' -> ('Psalms', 148, 1, 999)"""
    m = _REF.match(ref.strip())
    if not m:
        return None
    corpus, book = lookup._resolve_book(m.group(1))
    if not book:
        return None
    first = int(m.group(3)) if m.group(3) else 1
    last = int(m.group(4)) if m.group(4) else (first if m.group(3) else 999)
    return book, int(m.group(2)), first, last


def hymns_for_passage(ref: str) -> "list | None":
    """Hymns drawing on a passage that overlaps `ref`, or None if `ref` isn't one."""
    want = _parse_ref(ref)
    if want is None:
        return None
    out = []
    for h in hymns():
        for r in h["scripture"]:
            got = _parse_ref(r)
            if got and got[:2] == want[:2] and got[2] <= want[3] and want[2] <= got[3]:
                out.append(h)
                break
    return out


# ── finding a hymn ──────────────────────────────────────────────────────────

def find_hymns(query: str) -> list:
    """Best matches first: title, first line, topic, a passage it draws on, then its words."""
    q = _norm(query)
    if not q:
        return []
    all_hymns = hymns()
    exact = [h for h in all_hymns if q in [_norm(h["title"]), *map(_norm, h["also"]), _norm(h["first_line"])]]
    if exact:
        return exact
    titles = [h for h in all_hymns if any(_norm(t).startswith(q) for t in (h["title"], h["first_line"], *h["also"]))]
    titles += [h for h in all_hymns if h not in titles and any(q in _norm(t) for t in (h["title"], *h["also"]))]
    # a topic ("christmas") lists all its hymns, any with it in the title first
    topical = [h for h in all_hymns if h not in titles and any(q in _norm(t) for t in h["topics"])]
    if titles or topical:
        return titles + topical
    passage = hymns_for_passage(query)
    if passage:
        return passage
    words = [h for h in all_hymns if q in _norm(" ".join(h["stanzas"]) + " " + h["refrain"])]
    if words:
        return words
    terms = q.split()
    return [h for h in all_hymns if all(t in _norm(" ".join(h["stanzas"]) + " " + h["refrain"]).split() for t in terms)]


# ── showing one ─────────────────────────────────────────────────────────────

def words_text(hymn: dict, limit: int = 4000) -> str:
    """The verses, numbered, with the refrain after the first."""
    parts = []
    for i, stanza in enumerate(hymn["stanzas"], 1):
        parts.append(f"**{i}.** {stanza}")
        if i == 1 and hymn["refrain"]:
            parts.append("*Refrain:*\n*" + hymn["refrain"].replace("\n", "*\n*") + "*")
    text = ""
    for n, part in enumerate(parts):
        if len(text) + len(part) + 2 > limit - 60:
            text += f"\n\n*…{len(parts) - n} more verse(s) — too long to show in full.*"
            break
        text = f"{text}\n\n{part}" if text else part
    return text


def credit_lines(hymn: dict) -> list:
    words = hymn["author"] or "Unknown"
    if hymn["translator"]:
        words += f"; translated by {hymn['translator']}"
    tune = hymn["tune"].upper() if hymn["tune"] else ""
    music = hymn["composer"] or ""
    lines = [f"**Words:** {words}"]
    if tune or music:
        lines.append(f"**Tune:** {tune}" + (f" — {music}" if music and tune else music))
    if hymn["meter"]:
        lines.append(f"**Meter:** {hymn['meter']}")
    return lines


def hymn_embed(hymn: dict) -> discord.Embed:
    embed = discord.Embed(title=f"🎵 {hymn['title']}", description=words_text(hymn), color=COLOR)
    embed.add_field(name="About", value="\n".join(credit_lines(hymn))[:1024], inline=False)
    if hymn["scripture"]:
        embed.add_field(name="Drawn from", value=", ".join(hymn["scripture"])[:1024], inline=False)
    played = " · ▶ Play the tune for an organ rendering" if audio_path(hymn) else ""
    embed.set_footer(text=f"Public domain · {hymn.get('source', 'The Open Hymnal Project')}{played}")
    return embed


class HymnButton(discord.ui.DynamicItem[discord.ui.Button],
                 template=r"hymn:(?P<action>play|bible):(?P<key>[0-9a-f]{8})"):
    LOOK = {"play": ("Play the tune", "▶️"), "bible": ("Read the passages", "📖")}

    def __init__(self, action: str, key: str):
        label, emoji = self.LOOK[action]
        super().__init__(discord.ui.Button(label=label, emoji=emoji, style=discord.ButtonStyle.secondary,
                                           custom_id=f"hymn:{action}:{key}"))
        self.action, self.key = action, key

    @classmethod
    async def from_custom_id(cls, interaction, item, match):
        return cls(match["action"], match["key"])

    async def callback(self, interaction: discord.Interaction):
        hymn = by_key(self.key)
        if hymn is None:
            await interaction.response.send_message("⚠️ I can't find that hymn any more.", ephemeral=True)
            return
        if self.action == "play":
            await play(interaction, hymn)
        else:
            await interaction.response.send_message(embed=passages_embed(hymn), ephemeral=True)


bot.add_dynamic_items(HymnButton)


def hymn_view(hymn: dict) -> discord.ui.View:
    view = discord.ui.View(timeout=None)            # persistent buttons: must never time out
    if audio_path(hymn):
        view.add_item(HymnButton("play", hymn_key(hymn)))
    if hymn["scripture"]:
        view.add_item(HymnButton("bible", hymn_key(hymn)))
    return view


def passages_embed(hymn: dict) -> discord.Embed:
    embed = discord.Embed(title=f"📖 The Bible behind “{hymn['title']}”", color=COLOR)
    shown = 0
    for ref in hymn["scripture"]:
        if shown == 4:
            break
        result = lookup.get_verse(ref)
        if not result.get("found"):
            continue
        text = re.sub(r"\*\*\[(\d+)\]\*\*", r"\1", result["text"]).strip()
        embed.add_field(name=result["reference"], value=text[:1000] + ("…" if len(text) > 1000 else ""),
                        inline=False)
        shown += 1
    rest = hymn["scripture"][shown:]
    if rest:
        embed.set_footer(text="Also: " + ", ".join(rest) + " — look them up with !verse")
    return embed


def audio_path(hymn: dict):
    """The tune as Ogg Opus, rendered ahead by scripts/render_hymn_audio.py; None if there isn't one."""
    if not hymn.get("midi"):
        return None
    path = AUDIO_DIR / (hymn["midi"].rsplit(".", 1)[0] + ".ogg")
    return path if path.exists() else None


async def play(interaction: discord.Interaction, hymn: dict) -> None:
    path = audio_path(hymn)
    if path is None:
        await interaction.response.send_message("⚠️ I don't have that tune to play.", ephemeral=True)
        return
    stem = re.sub(r"[^A-Za-z0-9]+", "_", hymn["title"]).strip("_")[:60] or "hymn"
    tune = f" — {hymn['tune'].upper()}" if hymn["tune"] else ""
    await interaction.response.send_message(
        f"🎵 **{hymn['title']}**{tune}: the tune once through, in four parts on an organ.",
        file=discord.File(path, filename=f"{stem}.ogg"))


def list_embed(query: str, found: list) -> discord.Embed:
    lines = [f"• **{h['title']}** — *{h['first_line']}*" for h in found[:MAX_LIST]]
    more = f"\n…and {len(found) - MAX_LIST} more — try a longer search." if len(found) > MAX_LIST else ""
    embed = discord.Embed(title=f"🎵 Hymns for “{query}”", description="\n".join(lines) + more, color=COLOR)
    embed.set_footer(text="Pick one below, or !hymn <title>")
    return embed


class HymnPicker(discord.ui.View):
    def __init__(self, found: list):
        super().__init__(timeout=300)
        options = [discord.SelectOption(label=h["title"][:100], description=h["first_line"][:100], value=hymn_key(h))
                   for h in found[:25]]
        select = discord.ui.Select(placeholder="Choose a hymn…", options=options)
        select.callback = self._chosen
        self.add_item(select)
        self.select = select

    async def _chosen(self, interaction: discord.Interaction):
        hymn = by_key(self.select.values[0])
        await interaction.response.send_message(embed=hymn_embed(hymn), view=hymn_view(hymn))


async def send_hymn_search(ctx, query: str) -> None:
    query = query.strip()
    if not query or query.lower() == "random":
        hymn = random.choice(hymns())
        await ctx.send(embed=hymn_embed(hymn), view=hymn_view(hymn))
        return
    found = find_hymns(query)
    if not found:
        await ctx.send(f"No hymn found for **{query}**. Try a title (`!hymn amazing grace`), a line "
                       f"from the words, a topic (`!hymn christmas`) or a passage (`!hymn Psalm 23`).")
        return
    if len(found) == 1:
        await ctx.send(embed=hymn_embed(found[0]), view=hymn_view(found[0]))
        return
    await ctx.send(embed=list_embed(query, found), view=HymnPicker(found))


@bot.command(name="hymn", aliases=["hymns", "hymnal"])
async def cmd_hymn(ctx, *, query: str = ""):
    """A public-domain hymn: its words, its tune, and the Bible behind it.
    Usage: !hymn amazing grace   — by title, first line, or words
           !hymn christmas       — by topic
           !hymn Psalm 23        — hymns drawn on a passage
           !hymn                 — a random hymn"""
    await send_hymn_search(ctx, query)


async def _title_autocomplete(interaction: discord.Interaction, current: str) -> list:
    q = _norm(current)
    names = [h["title"] for h in hymns() if not q or q in _norm(h["title"])]
    return [app_commands.Choice(name=n[:100], value=n[:100]) for n in names[:25]]


@bot.tree.command(name="hymn", description="A public-domain hymn: words, tune, and the Bible behind it")
@app_commands.describe(query="A title, first line, words, topic (christmas) or passage (Psalm 23); empty for random")
@app_commands.autocomplete(query=_title_autocomplete)
async def hymn_slash(interaction: discord.Interaction, query: str = ""):
    await interaction.response.defer()
    ctx = await bot.get_context(interaction)
    await send_hymn_search(ctx, query)
