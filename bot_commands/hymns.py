"""
!hymn: public-domain hymns from the Open Hymnal Project (data/hymns/,
built by scripts/build_hymns.py).
  !hymn amazing grace        by title, first line, or a line from the words
  !hymn christmas            by topic
  !hymn Psalm 23             hymns drawn on a passage
  !hymn                      a random hymn
  !chant pater noster        a Latin chant, sung (scripts/build_sung_chant.py)
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

from core import ROOT, bot, log, lookup
from bot_commands import latin_psalms

HYMNS_PATH = ROOT / "data" / "hymns" / "hymns.json"
# the ancient Latin hymns in Gregorian chant, and pieces like Babylon Is Fallen (scripts/build_chant.py)
MORE_PATH = ROOT / "data" / "hymns" / "more_hymns.json"
# the Sacred Harp, every song sung (scripts/build_sacred_harp.py)
HARP_PATH = ROOT / "data" / "hymns" / "sacred_harp.json"
MIDI_DIR = ROOT / "data" / "hymns" / "midi"
AUDIO_DIR = ROOT / "data" / "hymns" / "audio"
COLOR = discord.Color.from_rgb(120, 60, 110)
MAX_LIST = 20


@functools.lru_cache(maxsize=1)
def hymns() -> list:
    found = json.loads(HYMNS_PATH.read_text(encoding="utf-8"))["hymns"]
    for extra in (MORE_PATH, HARP_PATH):
        if extra.exists():
            found = found + json.loads(extra.read_text(encoding="utf-8"))["hymns"]
    return found


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
    exact.sort(key=lambda h: q != _norm(h["title"]))         # a title match before a first line
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
    played = " · ▶ Play the tune to hear it" if audio_path(hymn) else ""
    language = f"In {hymn['language']} · " if hymn.get("language") else ""
    embed.set_footer(text=f"{language}Public domain · {hymn.get('source', 'The Open Hymnal Project')}{played}")
    return embed


class HymnButton(discord.ui.DynamicItem[discord.ui.Button],
                 template=r"hymn:(?P<action>play|sung|score|bible|english):(?P<key>[0-9a-f]{8})"):
    LOOK = {"play": ("Play the tune", "▶️"), "sung": ("Sung", "🎤"), "score": ("Score", "🎼"),
            "bible": ("Read the passages", "📖"), "english": ("English", "🇬🇧")}

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
        if self.action in ("play", "sung"):
            await play(interaction, hymn, sung=self.action == "sung")
        elif self.action == "score":
            await interaction.response.send_message(**score_message(hymn, 0))
        elif self.action == "english":
            await interaction.response.send_message(embed=english_embed(hymn))
        else:
            await interaction.response.send_message(embed=passages_embed(hymn), ephemeral=True)


bot.add_dynamic_items(HymnButton)


def hymn_view(hymn: dict) -> discord.ui.View:
    view = discord.ui.View(timeout=None)            # persistent buttons: must never time out
    if audio_path(hymn):
        view.add_item(HymnButton("play", hymn_key(hymn)))
    if sung_path(hymn):
        view.add_item(HymnButton("sung", hymn_key(hymn)))
    if score_paths(hymn):
        view.add_item(HymnButton("score", hymn_key(hymn)))
    if hymn["scripture"]:
        view.add_item(HymnButton("bible", hymn_key(hymn)))
    if translation(hymn):
        view.add_item(HymnButton("english", hymn_key(hymn)))
    return view


# published English translations of the Latin chants (scripts/build_translations.py), by title
TRANSLATIONS_PATH = ROOT / "data" / "hymns" / "translations.json"


@functools.lru_cache(maxsize=1)
def _translations() -> dict:
    if not TRANSLATIONS_PATH.exists():
        return {}
    return json.loads(TRANSLATIONS_PATH.read_text(encoding="utf-8"))["translations"]


def translation(hymn: dict) -> "dict | None":
    return _translations().get(hymn["title"])


def english_embed(hymn: dict) -> discord.Embed:
    t = translation(hymn)
    text = "\n\n".join(t["stanzas"])
    if len(text) > 4000:
        text = text[:4000].rsplit("\n", 1)[0] + "\n…"
    embed = discord.Embed(title=f"🇬🇧 {hymn['title']}, in English", description=text, color=COLOR)
    footer = (f"Translated by {t['translator']} · {t['source']}" if t["translator"] != "The Book of Common Prayer"
              else t["source"])
    embed.set_footer(text=footer + (f"\n{t['note']}" if t.get("note") else ""))
    return embed


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
    """The tune as Ogg Opus, rendered ahead (scripts/render_hymn_audio.py, build_chant.py); None if there isn't one."""
    if hymn.get("audio"):
        path = AUDIO_DIR / hymn["audio"]
    elif hymn.get("midi"):
        path = AUDIO_DIR / (hymn["midi"].rsplit(".", 1)[0] + ".ogg")
    else:
        return None
    return path if path.exists() else None


def sung_path(hymn: dict):
    """A chant sung with its Latin words (scripts/build_sung_chant.py); None if there isn't one."""
    if not hymn.get("gregobase"):
        return None
    path = AUDIO_DIR / "sung" / f"chant-{hymn['gregobase']:05d}.ogg"
    return path if path.exists() else None


SCORE_DIR = ROOT / "data" / "hymns" / "scores"


def score_paths(hymn: dict) -> list:
    """A chant's score in square notation, a page an image (scripts/build_chant_scores.py); [] if none."""
    if not hymn.get("gregobase"):
        return []
    found = SCORE_DIR.glob(f"chant-{hymn['gregobase']:05d}-*.png")
    return sorted(found, key=lambda p: int(p.stem.rsplit("-", 1)[1]))


def score_message(hymn: dict, page: int) -> dict:
    """send()/edit kwargs for one page of a chant's score, with ◀ ▶ when there are more."""
    paths = score_paths(hymn)
    page = page % len(paths)
    content = f"🎼 **{hymn['title']}** in square notation, the way chant books print it" + \
              (f" · page {page + 1} of {len(paths)}" if len(paths) > 1 else "")
    message = {"content": content, "file": discord.File(paths[page], filename=f"score_{page + 1}.png")}
    if len(paths) > 1:
        view = discord.ui.View(timeout=None)            # persistent: must never time out
        view.add_item(ScoreButton("back", hymn_key(hymn), (page - 1) % len(paths)))
        view.add_item(ScoreButton("next", hymn_key(hymn), (page + 1) % len(paths)))
        message["view"] = view
    return message


class ScoreButton(discord.ui.DynamicItem[discord.ui.Button],
                  template=r"hymnscore:(?P<action>back|next):(?P<key>[0-9a-f]{8}):(?P<page>\d+)"):
    """◀ ▶ through a score's pages. "back" and "next" keep the two custom_ids apart on a
    two-page score, where both lead to the same page (Discord refuses duplicate ids)."""

    def __init__(self, action: str, key: str, page: int):
        super().__init__(discord.ui.Button(emoji="◀" if action == "back" else "▶", style=discord.ButtonStyle.secondary,
                                           custom_id=f"hymnscore:{action}:{key}:{page}"))
        self.key, self.page = key, page

    @classmethod
    async def from_custom_id(cls, interaction, item, match):
        return cls(match["action"], match["key"], int(match["page"]))

    async def callback(self, interaction: discord.Interaction):
        hymn = by_key(self.key)
        if hymn is None or not score_paths(hymn):
            await interaction.response.send_message("⚠️ I can't find that score any more.", ephemeral=True)
            return
        message = score_message(hymn, self.page)
        await interaction.response.edit_message(content=message["content"], attachments=[message["file"]],
                                                view=message.get("view"))


bot.add_dynamic_items(ScoreButton)


PLAYED = {"chant": "the chant melody, on an organ",
          "sung": "sung in four parts (a synthesised choir)",
          None: "the tune once through, in four parts on an organ"}


def audio_message(hymn: dict, sung: bool = False) -> "tuple | None":
    """(caption, file) for posting a hymn's tune, or a chant sung; None if it has none."""
    path = sung_path(hymn) if sung else audio_path(hymn)
    if path is None:
        return None
    stem = re.sub(r"[^A-Za-z0-9]+", "_", unicodedata.normalize("NFKD", hymn["title"])).strip("_")[:60] or "hymn"
    if sung:
        return (f"🎤 **{hymn['title']}**: sung in Latin by a synthesised schola (a small choir of chanters).",
                discord.File(path, filename=f"{stem}_sung.ogg"))
    tune = f" — {hymn['tune'].upper()}" if hymn.get("tune") else ""
    return (f"🎵 **{hymn['title']}**{tune}: {PLAYED.get(hymn.get('audio_kind'), PLAYED[None])}.",
            discord.File(path, filename=f"{stem}.ogg"))


async def play(interaction: discord.Interaction, hymn: dict, sung: bool = False) -> None:
    message = audio_message(hymn, sung)
    if message is None:
        await interaction.response.send_message("⚠️ I don't have that tune to play.", ephemeral=True)
        return
    await interaction.response.send_message(message[0], file=message[1])


def list_embed(query: str, found: list) -> discord.Embed:
    lines = [f"• **{h['title']}** — *{h['first_line']}*" for h in found[:MAX_LIST]]
    more = f"\n…and {len(found) - MAX_LIST} more — try a longer search." if len(found) > MAX_LIST else ""
    embed = discord.Embed(title=f"🎵 Hymns for “{query}”", description="\n".join(lines) + more, color=COLOR)
    embed.set_footer(text="Pick one below, or !hymn <title>")
    return embed


class HymnPicker(discord.ui.View):
    def __init__(self, found: list, tune_only: bool = False, sung: bool = False):
        super().__init__(timeout=300)
        self.tune_only, self.sung = tune_only or sung, sung
        options = [discord.SelectOption(label=h["title"][:100], description=h["first_line"][:100], value=hymn_key(h))
                   for h in found[:25]]
        select = discord.ui.Select(placeholder="Choose a hymn…", options=options)
        select.callback = self._chosen
        self.add_item(select)
        self.select = select

    async def _chosen(self, interaction: discord.Interaction):
        hymn = by_key(self.select.values[0])
        if self.tune_only:
            await play(interaction, hymn, sung=self.sung)
            return
        await interaction.response.send_message(embed=hymn_embed(hymn), view=hymn_view(hymn))


async def send_hymn_search(ctx, query: str) -> None:
    query = query.strip()
    if not query or query.lower() == "random":
        hymn = random.choice(hymns())
        await ctx.send(embed=hymn_embed(hymn), view=hymn_view(hymn))
        return
    if _norm(query) in ("harp", "sacred harp", "random harp", "shape note"):   # a random Sacred Harp song
        hymn = random.choice([h for h in hymns() if shelf(h) == "harp"])
        await ctx.send(embed=hymn_embed(hymn), view=hymn_view(hymn))
        return
    if query.lower() in ("list", "index", "all"):                # people try this before !hymnlist
        await send_hymn_list(ctx, "")
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


async def send_hymn_tune(ctx, query: str) -> None:
    """Just the tune: the audio straight away, no words."""
    query = query.strip()
    if not query or query.lower() == "random":
        found = [h for h in hymns() if audio_path(h)]
        found = [random.choice(found)] if found else []
    else:
        found = [h for h in find_hymns(query) if audio_path(h)]
    if not found:
        await ctx.send(f"I have no tune to play for **{query}**. Try `!hymn {query}` for the words, "
                       f"or a title such as `!midi amazing grace` or `!midi Salve Regina`.")
        return
    exact = [h for h in found if _norm(h["title"]) == _norm(query)]
    if len(found) == 1 or exact:
        caption, file = audio_message((exact or found)[0])
        await ctx.send(caption, file=file)
        return
    await ctx.send(embed=list_embed(query, found), view=HymnPicker(found, tune_only=True))


async def send_chant(ctx, query: str) -> None:
    """A Latin chant sung, straight away: the audio, no words."""
    query = query.strip()
    psalm = re.match(r"^(?:psalm|ps)\.?\s*(\d.*)$", query, re.I)
    if psalm:                                                     # !chant psalm 110: the chanted psalter
        await latin_psalms.send_psalm_chant(ctx, psalm.group(1))
        return
    if not query or query.lower() == "random":
        found = [h for h in hymns() if sung_path(h)]
        found = [random.choice(found)] if found else []
    else:
        found = [h for h in find_hymns(query) if sung_path(h)]
    if not found:
        await ctx.send(f"I have no sung chant for **{query}**. `!chant` sings the Latin chants: try "
                       f"`!chant Pater noster` or `!chant Salve Regina`, or `!hymnlist chant` for them all.")
        return
    exact = [h for h in found if _norm(h["title"]) == _norm(query)]
    if len(found) == 1 or exact:
        caption, file = audio_message((exact or found)[0], sung=True)
        await ctx.send(caption, file=file)
        return
    await ctx.send(embed=list_embed(query, found), view=HymnPicker(found, sung=True))


@bot.command(name="chant", aliases=["sing", "sungchant"])
async def cmd_chant(ctx, *, query: str = ""):
    """Hear a Latin chant sung, with its words, straight away.
    Usage: !chant pater noster   — by title, words or kind (sequence, antiphon)
           !chant                — a random chant"""
    await send_chant(ctx, query)


@bot.command(name="midi", aliases=["tune"])
async def cmd_midi(ctx, *, query: str = ""):
    """Play a hymn's tune straight away, without the words.
    Usage: !midi amazing grace   — by title, first line, words, topic or passage
           !midi                 — a random hymn's tune"""
    await send_hymn_tune(ctx, query)


# ── the whole hymnal, listed ────────────────────────────────────────────────

LIST_PAGE = 20
SHELVES = {"hymns": "Hymns and carols", "chant": "Ancient hymns in Gregorian chant", "harp": "The Sacred Harp"}
PLURALS = {"Invitatory": "Invitatories", "Chant": "Other chants", "Mass Ordinary": "Mass Ordinary",
           "Offertory": "Offertories", "Responsory": "Responsories"}   # the rest just add an s
SHELF_WORDS = {"hymns": "hymns", "hymn": "hymns", "carols": "hymns", "english": "hymns",
               "chant": "chant", "chants": "chant", "latin": "chant", "gregorian": "chant",
               "harp": "harp", "sacred harp": "harp", "shape note": "harp"}


def shelf(hymn: dict) -> str:
    return {"chant": "chant", "sung": "harp"}.get(hymn.get("audio_kind"), "hymns")


def chant_part(hymn: dict) -> str:
    """Hymn, Sequence, Antiphon... (a chant's first topic)."""
    return hymn["topics"][0] if shelf(hymn) == "chant" and hymn["topics"] else ""


def plural(part: str) -> str:
    return PLURALS.get(part, part + "s")


def hymn_list(query: str) -> "tuple[str, list]":
    """(heading, hymns sorted by title) for !hymnlist: a shelf, a kind of chant, or titles containing the words."""
    q = _norm(query)
    every = sorted(hymns(), key=lambda h: _norm(h["title"]))
    if not q:
        return "Every hymn", every
    if q in SHELF_WORDS:
        key = SHELF_WORDS[q]
        return SHELVES[key], [h for h in every if shelf(h) == key]
    parts = {_norm(chant_part(h)) for h in every} - {""}
    p = re.sub(r"^(chant|latin|gregorian) ", "", q)                # "chant hymns": the Latin ones, not the English
    named = {_norm(x): x for x in parts} | {_norm(plural(chant_part(h))): _norm(chant_part(h)) for h in every if chant_part(h)}
    part = named.get(p)
    if part:
        found = [h for h in every if _norm(chant_part(h)) == part]
        return f"Chant: {plural(chant_part(found[0]))}", found
    return f"Titles with “{query}”", [h for h in every if q in _norm(h["title"]) or any(q in _norm(a) for a in h["also"])]


def hymn_list_overview() -> discord.Embed:
    every = hymns()
    count = {k: sum(shelf(h) == k for h in every) for k in SHELVES}
    parts = {}
    for h in every:
        if chant_part(h):
            parts[chant_part(h)] = parts.get(chant_part(h), 0) + 1
    embed = discord.Embed(title=f"🎵 The hymnal — {len(every)} hymns", color=COLOR)
    embed.description = (
        f"**{SHELVES['hymns']}** — {count['hymns']}, in English · `!hymnlist hymns`\n"
        f"**{SHELVES['chant']}** — {count['chant']}, in Latin · `!hymnlist chant`\n"
        + "".join(f"  ↳ {plural(p)} — {n} · `!hymnlist chant {plural(p).lower()}`\n" for p, n in sorted(parts.items(), key=lambda x: -x[1]))
        + f"**{SHELVES['harp']}** — {count['harp']} · `!hymnlist harp`\n\n"
        "`!hymnlist all` lists every title; `!hymnlist <words>` lists titles containing them. "
        "Open one with `!hymn <title>`, or play just its tune with `!midi <title>`.")
    return embed


def hymn_list_embed(heading: str, found: list, page: int) -> discord.Embed:
    pages = max(1, -(-len(found) // LIST_PAGE))
    chunk = found[page * LIST_PAGE:(page + 1) * LIST_PAGE]
    lines = [f"• **{h['title']}**" + (f" — *{chant_part(h).lower()}*" if chant_part(h) else "") for h in chunk]
    embed = discord.Embed(title=f"🎵 {heading} ({len(found)})", description="\n".join(lines), color=COLOR)
    embed.set_footer(text=f"Page {page + 1} of {pages} · pick one below to open it, or !hymn <title>")
    return embed


class HymnListView(discord.ui.View):
    def __init__(self, heading: str, found: list):
        super().__init__(timeout=600)
        self.heading, self.found, self.page = heading, found, 0
        self.pages = max(1, -(-len(found) // LIST_PAGE))
        # the same three items for the view's whole life: replacing them would leave the message's
        # old ones unanswered (Discord's "This interaction failed") if an edit didn't go through
        if self.pages == 1:
            self.remove_item(self.turn_back)
            self.remove_item(self.turn_on)
        self.select.callback = self._chosen
        self._fill()

    def _fill(self):
        chunk = self.found[self.page * LIST_PAGE:(self.page + 1) * LIST_PAGE]
        self.select.options = [
            discord.SelectOption(label=h["title"][:100], description=h["first_line"][:100] or None, value=hymn_key(h))
            for h in chunk]

    @discord.ui.button(emoji="◀", style=discord.ButtonStyle.secondary)
    async def turn_back(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._turn(interaction, -1)

    @discord.ui.button(emoji="▶", style=discord.ButtonStyle.secondary)
    async def turn_on(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._turn(interaction, 1)

    @discord.ui.select(placeholder="Open a hymn…", options=[discord.SelectOption(label="-")])
    async def select(self, interaction: discord.Interaction, select: discord.ui.Select):
        pass                                                   # (replaced by _chosen in __init__)

    async def _turn(self, interaction: discord.Interaction, step: int):
        late = (discord.utils.utcnow() - interaction.created_at).total_seconds()
        if late > 2:
            log.warning("hymnlist: page turn reached the bot %.1fs after the click", late)
        self.page = (self.page + step) % self.pages
        self._fill()
        await interaction.response.edit_message(embed=hymn_list_embed(self.heading, self.found, self.page), view=self)

    async def _chosen(self, interaction: discord.Interaction):
        hymn = by_key(self.select.values[0])
        await interaction.response.send_message(embed=hymn_embed(hymn), view=hymn_view(hymn))

    async def on_timeout(self):
        try:
            await self.message.edit(view=None)
        except Exception:
            pass


async def send_hymn_list(ctx, query: str) -> None:
    query = query.strip()
    if not query:
        await ctx.send(embed=hymn_list_overview())
        return
    heading, found = hymn_list("" if query.lower() in ("all", "every", "everything") else query)
    if not found:
        await ctx.send(f"No hymn titles with **{query}**. Try `!hymnlist` to see the sections, "
                       f"or `!hymn {query}` to search the words too.")
        return
    view = HymnListView(heading, found)
    view.message = await ctx.send(embed=hymn_list_embed(heading, found, 0), view=view)


@bot.command(name="hymnlist", aliases=["hymnindex", "listhymns"])
async def cmd_hymnlist(ctx, *, query: str = ""):
    """Every hymn the bot has, by title.
    Usage: !hymnlist              — the sections, with how many hymns in each
           !hymnlist all          — every title, a page at a time
           !hymnlist chant        — one section (hymns, chant, harp) or kind of chant (sequences, antiphons)
           !hymnlist veni         — titles containing a word"""
    await send_hymn_list(ctx, query)


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


@bot.tree.command(name="midi", description="Play a hymn's tune straight away, without the words")
@app_commands.describe(query="A title, first line, words, topic or passage; empty for random")
@app_commands.autocomplete(query=_title_autocomplete)
async def midi_slash(interaction: discord.Interaction, query: str = ""):
    await interaction.response.defer()
    ctx = await bot.get_context(interaction)
    await send_hymn_tune(ctx, query)


async def _chant_autocomplete(interaction: discord.Interaction, current: str) -> list:
    q = _norm(current)
    names = [h["title"] for h in hymns() if h.get("gregobase") and (not q or q in _norm(h["title"]))]
    return [app_commands.Choice(name=n[:100], value=n[:100]) for n in names[:25]]


@bot.tree.command(name="chant", description="Hear a Latin chant sung, with its words")
@app_commands.describe(query="A title, words or kind of chant (sequence); empty for a random chant")
@app_commands.autocomplete(query=_chant_autocomplete)
async def chant_slash(interaction: discord.Interaction, query: str = ""):
    await interaction.response.defer()
    ctx = await bot.get_context(interaction)
    await send_chant(ctx, query)


@bot.tree.command(name="hymnlist", description="Every hymn the bot has, by title, a page at a time")
@app_commands.describe(query="all, hymns, chant, harp, a kind of chant (sequences), or words in the title; empty for the sections")
async def hymnlist_slash(interaction: discord.Interaction, query: str = ""):
    await interaction.response.defer()
    ctx = await bot.get_context(interaction)
    await send_hymn_list(ctx, query)
