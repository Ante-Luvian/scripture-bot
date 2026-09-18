"""
Scripture Bot for Discord
Supports: KJV + Apocrypha, LDS Standard Works, Brenton Septuagint,
          R.H. Charles' Book of Enoch & Book of Jubilees,
          Apostolic Fathers (J.B. Lightfoot)
"""

import re
import os
import io
import random
import json
import asyncio
import time
import unicodedata
import discord
from pathlib import Path
from discord.ext import commands, tasks
from discord import app_commands
from scripture_lookup import ScriptureLookup, get_verse_drb, DRB_SUFFIXES, KNOX_SUFFIXES, get_verse_knox, BIBLE_OT, BIBLE_NT, BIBLE_APOCRYPHA
from summa_lookup import parse_summa_ref, get_summa, get_summa_random
from translation_lookup import (get_translation, get_parallel, get_random_verse, _mt_to_lxx_psalm,
                                 search_translation, TRANSLATION_SUFFIXES, TRANSLATIONS,
                                 list_translations)
from poem_lookup import (parse_poem_ref, lookup as poem_lookup, lookup_pair,
                         list_works as poem_list_works, classify_scripture, is_drb_reference)
from xref_lookup import get_cross_references
from topics_lookup import get_topic, search_topics, topic_count
from strongs_lookup import get_definition as get_local_strongs_definition
from bible_dictionary_lookup import get_definition as get_dictionary_entry, search_terms as search_dictionary_terms, entry_count as dictionary_entry_count, SOURCE_NAMES as DICTIONARY_SOURCE_NAMES
from timeline_lookup import search_timeline, entry_count as timeline_entry_count, year_range as timeline_year_range
import interlinear_lookup
from hadith_lookup import get_hadith_section

# Load .env file if present
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # dotenv not installed, fall back to environment variable

import logging
import collections

# ── Logging setup ─────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)-7s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("ScriptureBot")

# Suppress discord.py's own verbose gateway noise a little
logging.getLogger("discord.gateway").setLevel(logging.WARNING)
logging.getLogger("discord.client").setLevel(logging.WARNING)
logging.getLogger("discord.http").setLevel(logging.WARNING)

# Track unknown command names so we stop logging after 3 hits
_unknown_cmd_counts: dict[str, int] = collections.defaultdict(int)
_UNKNOWN_CMD_THRESHOLD = 3

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)
lookup = ScriptureLookup()

# Ancient Near East book list for !verse ancient_near_east random
ANE_BOOKS = [
    "Gilgamesh Tablet 1",  "Gilgamesh Tablet 2",  "Gilgamesh Tablet 3",
    "Gilgamesh Tablet 4",  "Gilgamesh Tablet 5",  "Gilgamesh Tablet 6",
    "Gilgamesh Tablet 7",  "Gilgamesh Tablet 8",  "Gilgamesh Tablet 9",
    "Gilgamesh Tablet 10", "Gilgamesh Tablet 11", "Gilgamesh Tablet 12",
    "Baal and Yamm", "The Palace of Baal", "Baal and Mot",
    "The Great Hymn to the Aten",
    "Book of the Dead",
    "The Leiden Hymns",
    "The Instruction of Amenemope",
    "The Book of Two Ways",
    "The Story of Ahikar",
]

@bot.event
async def on_command(ctx):
    log.info(f"CMD  {ctx.command.name:<16} | {ctx.author} | #{ctx.channel} | {ctx.message.content[:80]}")
    _record_guild_activity(ctx)

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        cmd = ctx.invoked_with or ""
        _unknown_cmd_counts[cmd] += 1
        if _unknown_cmd_counts[cmd] <= _UNKNOWN_CMD_THRESHOLD:
            log.warning(f"Unknown command: !{cmd} (from {ctx.author}) — hit {_unknown_cmd_counts[cmd]}/{_UNKNOWN_CMD_THRESHOLD}")
        elif _unknown_cmd_counts[cmd] == _UNKNOWN_CMD_THRESHOLD + 1:
            log.warning(f"Unknown command !{cmd} seen {_UNKNOWN_CMD_THRESHOLD}+ times — suppressing further logs (likely another bot's prefix)")
        # else: silently ignored
        return
    # Re-raise other errors so Discord's default handler sees them
    raise error

# ── VOTD config ────────────────────────────────────────────────────────────────
# Per-guild VOTD channel/time/mode now lives in data/guild_config.json (see
# _get_guild_votd / _update_guild_config), configured per-server via !votdsetup.
# These two are only the one-time migration seed for the server that was
# hardcoded here before per-guild config existed.
_LEGACY_VOTD_CHANNEL_ID: int | None = 921184056341835836
_LEGACY_VOTD_TIME = "04:00"

# VOTD mode persistence: "full" (verse + ancients + commentary) or "basic" (verse only).
# Toggled via the hidden !votdmode command. Default is "full".
VOTD_MODE_PATH = Path(__file__).parent / "data" / "votd_mode.json"

def _load_votd_mode() -> str:
    if VOTD_MODE_PATH.exists():
        try:
            data = json.loads(VOTD_MODE_PATH.read_text(encoding="utf-8"))
            mode = data.get("mode", "full")
            return mode if mode in ("full", "basic", "extended") else "full"
        except Exception:
            pass
    return "full"

def _save_votd_mode(mode: str) -> None:
    VOTD_MODE_PATH.parent.mkdir(parents=True, exist_ok=True)
    VOTD_MODE_PATH.write_text(
        json.dumps({"mode": mode}, indent=2), encoding="utf-8"
    )

# Well-known fallback verses used when verseoftheday.com is unreachable
_VOTD_FALLBACKS = [
    "John 3:16", "Romans 8:28", "Psalm 23:1", "Isaiah 40:31",
    "Philippians 4:13", "Jeremiah 29:11", "Proverbs 3:5", "Matthew 11:28",
    "Romans 12:2", "Joshua 1:9", "Psalm 46:1", "1 Corinthians 13:4",
    "Ephesians 2:8", "Psalm 119:105", "John 14:6", "Romans 6:23",
    "2 Timothy 3:16", "Hebrews 11:1", "James 1:17", "1 John 4:19",
]

# Search/bolls.life rate limiting: 3 requests per 30s per user
_search_cooldowns: dict[int, list] = {}

def _check_search_cooldown(user_id: int) -> bool:
    """Returns True if user is allowed, False if rate-limited."""
    import time as _time
    now = _time.monotonic()
    history = _search_cooldowns.setdefault(user_id, [])
    _search_cooldowns[user_id] = [t for t in history if now - t < 30]
    if len(_search_cooldowns[user_id]) >= 3:
        return False
    _search_cooldowns[user_id].append(now)
    return True

# Cache: (date_str, reference, date_text)
_votd_cache: tuple[str, str | None, str] = ("", None, "")

def _scrape_votd() -> tuple[str | None, str]:
    """
    Scrape verseoftheday.com. Returns (reference, date_text).
    Result is cached for the calendar day; returns None on failure.
    """
    import urllib.request
    import html as html_mod
    import datetime

    global _votd_cache
    today = datetime.date.today().isoformat()
    if _votd_cache[0] == today:
        return _votd_cache[1], _votd_cache[2]

    url = "https://www.verseoftheday.com/"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=15) as r:
            raw = r.read().decode("utf-8")
    except Exception:
        return None, ""
    text = html_mod.unescape(re.sub(r"<[^>]+>", " ", raw))
    text = re.sub(r"[ \t]+", " ", text).strip()
    ref_m = re.search(
        r"[\u2014\-]{1,2}\s*([1-3]?\s*[A-Z][a-zA-Z]+\.?\s+\d+:\d+(?:\s*[-\u2013]\s*\d+)?)",
        text
    )
    if not ref_m:
        _votd_cache = (today, None, "")
        return None, ""
    reference = ref_m.group(1).strip()
    date_m = re.search(
        r"for\s+((?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)[^\[\n]+)",
        text
    )
    date_text = date_m.group(1).strip() if date_m else ""
    _votd_cache = (today, reference, date_text)
    return reference, date_text

# ── Stats tracking ─────────────────────────────────────────────────────────────
STATS_PATH = Path(__file__).parent / "data" / "stats.json"

# ── Per-guild / per-user command activity (owner-only !guildactivity) ───────────
GUILD_ACTIVITY_PATH = Path(__file__).parent / "data" / "guild_activity.json"

def _load_guild_activity() -> dict:
    if GUILD_ACTIVITY_PATH.exists():
        try:
            return json.loads(GUILD_ACTIVITY_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}

def _record_guild_activity(ctx):
    """Per-guild, per-command, per-user usage counts. Called once from the
    global on_command hook so every command is covered without threading a
    new parameter through every individual command handler. Only command
    invocations and identities are recorded here -- never message content,
    keeping this well inside "necessary for stated functionality" territory
    rather than the general conversation logging that would risk it."""
    if not ctx.guild:
        return
    try:
        data = _load_guild_activity()
        gid = str(ctx.guild.id)
        g = data.setdefault(gid, {"name": ctx.guild.name, "commands": {}, "users": {}})
        g["name"] = ctx.guild.name  # keep fresh if the server gets renamed
        g["commands"][ctx.command.name] = g["commands"].get(ctx.command.name, 0) + 1
        uid = str(ctx.author.id)
        u = g["users"].setdefault(uid, {"name": str(ctx.author), "commands": {}})
        u["name"] = str(ctx.author)
        u["commands"][ctx.command.name] = u["commands"].get(ctx.command.name, 0) + 1
        _atomic_write_json(GUILD_ACTIVITY_PATH, data)
    except Exception:
        pass  # never let this break the bot

def _load_stats() -> dict:
    if STATS_PATH.exists():
        try:
            return json.loads(STATS_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {
        "total_commands": 0,
        "unique_users":   [],
        "verse_counts":   {},
        "book_counts":    {},
        "command_counts": {},
    }

def _save_stats(stats: dict):
    STATS_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATS_PATH.write_text(json.dumps(stats, indent=2, ensure_ascii=False), encoding="utf-8")

def _atomic_write_json(path: Path, data) -> None:
    """Write JSON via a temp file + rename so a crash mid-write can't corrupt the file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(path)

# ── Per-guild config (VOTD channel/time/mode) ───────────────────────────────────
GUILD_CONFIG_PATH = Path(__file__).parent / "data" / "guild_config.json"

def _load_guild_config() -> dict:
    if GUILD_CONFIG_PATH.exists():
        try:
            return json.loads(GUILD_CONFIG_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}

def _save_guild_config(cfg: dict) -> None:
    _atomic_write_json(GUILD_CONFIG_PATH, cfg)

# ── Per-user preferred translation ───────────────────────────────────────────────
USER_PREFS_PATH = Path(__file__).parent / "data" / "user_prefs.json"

def _load_user_prefs() -> dict:
    if USER_PREFS_PATH.exists():
        try:
            return json.loads(USER_PREFS_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}

def _save_user_prefs(data: dict) -> None:
    _atomic_write_json(USER_PREFS_PATH, data)

def _get_preferred_translation(user_id: int) -> str | None:
    return _load_user_prefs().get(str(user_id), {}).get("translation")

def _get_guild_votd(guild_id: int) -> dict:
    g = _load_guild_config().get(str(guild_id), {})
    return {
        "channel_id": g.get("votd_channel_id"),
        "time": g.get("votd_time", "04:00"),
        "mode": g.get("votd_mode", "full"),
    }

def _update_guild_config(guild_id: int, **kwargs) -> None:
    """Merge fields into one guild's config — used for VOTD settings and,
    below, opt-in feature flags. Generic despite the old VOTD-only name."""
    cfg = _load_guild_config()
    g = cfg.setdefault(str(guild_id), {})
    g.update(kwargs)
    _save_guild_config(cfg)

# ── Opt-in per-guild feature flags ───────────────────────────────────────────────
# Off by default everywhere; a server's admins turn them on with !features.
GUILD_FEATURES = {
    "react_save": "React 📌 on a verse to bookmark it (no need to type !save)",
    "streaks":    "Show your !plan check-in streak",
    "export":     "Let !saved export your full bookmark list as a text file",
}

def _get_guild_features(guild_id: int) -> dict:
    g = _load_guild_config().get(str(guild_id), {})
    return {key: g.get(f"feature_{key}", False) for key in GUILD_FEATURES}

# ── Personal bookmarks ───────────────────────────────────────────────────────────
BOOKMARKS_PATH = Path(__file__).parent / "data" / "bookmarks.json"

def _load_bookmarks() -> dict:
    if BOOKMARKS_PATH.exists():
        try:
            return json.loads(BOOKMARKS_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}

def _save_bookmarks(data: dict) -> None:
    _atomic_write_json(BOOKMARKS_PATH, data)

# ── Personal reading plans ───────────────────────────────────────────────────────
READING_PLANS_PATH = Path(__file__).parent / "data" / "reading_plans.json"

def _load_reading_plans() -> dict:
    if READING_PLANS_PATH.exists():
        try:
            return json.loads(READING_PLANS_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}

def _save_reading_plans(data: dict) -> None:
    _atomic_write_json(READING_PLANS_PATH, data)

def _plan_current_chapter(plan: dict) -> int:
    """Chapter-a-day since start date, clamped to the book's length."""
    import datetime
    started = datetime.date.fromisoformat(plan["started_at"])
    days_elapsed = (datetime.date.today() - started).days
    return max(1, min(days_elapsed + 1, plan["total_chapters"]))

def record_stat(user_id: int, command: str, result: dict = None):
    """Record a command invocation and optionally a verse lookup result."""
    try:
        stats = _load_stats()
        stats["total_commands"] = stats.get("total_commands", 0) + 1
        uid = str(user_id)
        if uid not in stats.get("unique_users", []):
            stats.setdefault("unique_users", []).append(uid)
        cmd_counts = stats.setdefault("command_counts", {})
        cmd_counts[command] = cmd_counts.get(command, 0) + 1
        if result and result.get("found"):
            book = result.get("book") or result.get("reference", "").split()[0]
            ref  = result.get("reference", "")
            if book:
                bc = stats.setdefault("book_counts", {})
                bc[book] = bc.get(book, 0) + 1
            if ref:
                vc = stats.setdefault("verse_counts", {})
                vc[ref] = vc.get(ref, 0) + 1
        _save_stats(stats)
    except Exception:
        pass  # never let stats break the bot

def record_special_stat(user_id: int, command: str, ref: str):
    """Record a usage of !ccc, !canon, !summa, !virgil, !homer, !delphi, or !oracle."""
    try:
        stats = _load_stats()
        stats["total_commands"] = stats.get("total_commands", 0) + 1
        uid = str(user_id)
        if uid not in stats.get("unique_users", []):
            stats.setdefault("unique_users", []).append(uid)
        cmd_counts = stats.setdefault("command_counts", {})
        cmd_counts[command] = cmd_counts.get(command, 0) + 1
        # Store in a per-command ref counter
        special = stats.setdefault("special_counts", {})
        cmd_refs = special.setdefault(command, {})
        cmd_refs[ref] = cmd_refs.get(ref, 0) + 1
        _save_stats(stats)
    except Exception:
        pass

# ── Auto-detection regex ───────────────────────────────────────────────────────
# Scans ordinary messages for anything that looks like a scripture reference.
# Matches:  Gen 2:22  /  1 Nephi 3:7  /  D&C 76:22  /  Enoch 1:9  /  Herm 4:1-3
# The book part allows letters, digits, spaces, & ' - so abbreviations all work.
# We require a chapter:verse (the colon is mandatory) to avoid false positives
# on things like "Acts 2" or "John 3" which are too common as plain English.

_AUTO_RE = re.compile(
    r"(?<!\w)"                                     # not preceded by a word char
    r"((?:\d\s*)?[A-Za-z][A-Za-z&'\-\s]{0,28}?)"  # book name / abbreviation
    r"\s+(\d{1,3})"                                # chapter
    r":(\d{1,3})"                                  # :verse  (colon required)
    r"(?:\s*[-–]\s*(\d{1,3}))?"                    # optional -endverse
    r"(?!\w)"                                      # not followed by a word char
)


# ── Slash commands ─────────────────────────────────────────────────────────────

@bot.tree.command(name="verse", description="Look up a scripture verse")
@app_commands.describe(reference="e.g. John 3:16 | John 3:16 ESV | John 3:16 Knox | John 3:16 KJV ESV NASB")
async def verse_slash(interaction: discord.Interaction, reference: str):
    await interaction.response.defer()
    ctx = await bot.get_context(interaction)
    await verse_prefix(ctx, reference=reference)

@bot.tree.command(name="ccc", description="Look up a paragraph of the Catechism of the Catholic Church")
@app_commands.describe(number="Paragraph number (1–2865)")
async def ccc_slash(interaction: discord.Interaction, number: int):
    await interaction.response.defer()
    data = _load_ccc()
    if data is None:
        await interaction.followup.send("⚠️ catechism.json not found."); return
    text = data.get(number)
    if text is None:
        await interaction.followup.send(f"⚠️ Paragraph {number} not found."); return
    text = re.sub(r'\*+', '', text)
    if len(text) > 4000: text = text[:3997] + "…"
    embed = discord.Embed(title=f"CCC {number}", description=text, color=discord.Color.gold())
    embed.set_footer(text="Catechism of the Catholic Church")
    await interaction.followup.send(embed=embed)

@bot.tree.command(name="canon", description="Look up a canon of the Code of Canon Law")
@app_commands.describe(number="Canon number (1–1751)")
async def canon_slash(interaction: discord.Interaction, number: int):
    await interaction.response.defer()
    data = _load_canon()
    if data is None:
        await interaction.followup.send("⚠️ canon.json not found."); return
    text = data.get(number)
    if text is None:
        await interaction.followup.send(f"⚠️ Canon {number} not found."); return
    text = re.sub(r'\*+', '', text)
    if len(text) > 4000: text = text[:3997] + "…"
    embed = discord.Embed(title=f"Canon {number}", description=text, color=discord.Color.dark_red())
    embed.set_footer(text="Code of Canon Law (1983)")
    await interaction.followup.send(embed=embed)

@bot.tree.command(name="catena", description="Patristic commentary on a Bible verse from catenabible.com")
@app_commands.describe(reference="e.g. John 3:16 | Romans 8:28 | Matthew 5:3")
async def catena_slash(interaction: discord.Interaction, reference: str):
    await interaction.response.defer()
    ctx = await bot.get_context(interaction)
    await cmd_catena(ctx, reference=reference)

@bot.tree.command(name="gematria", description="Look up gematria values for a word or number")
@app_commands.describe(query="Word, phrase, or number to look up")
async def gematria_slash(interaction: discord.Interaction, query: str):
    await interaction.response.defer()
    ctx = await bot.get_context(interaction)
    await cmd_gematria(ctx, query=query)

@bot.tree.command(name="votd", description="Verse of the Day")
@app_commands.describe(translation='Optional translation (e.g. ESV), "full", or "extended"')
async def votd_slash(interaction: discord.Interaction, translation: str = ""):
    await interaction.response.defer()
    arg = translation.strip()
    if arg.lower() == "full":
        await _send_votd_full(interaction.channel)
    elif arg.lower() == "extended":
        await _send_votd_extended(interaction.channel)
    else:
        await _send_votd(interaction.channel, translation=arg)

@bot.tree.command(name="delphi", description="Random Delphic maxim")
async def delphi_slash(interaction: discord.Interaction):
    await interaction.response.defer()
    ctx = await bot.get_context(interaction)
    await cmd_delphi(ctx)

@bot.tree.command(name="oracle", description="Random verse from an oracular corpus")
@app_commands.describe(question="Optional question for the oracle")
async def oracle_slash(interaction: discord.Interaction, question: str = ""):
    await interaction.response.defer()
    ctx = await bot.get_context(interaction)
    await cmd_oracle(ctx, question=question)

@bot.tree.command(name="homer", description="Roll three dice and receive a Homeric oracle")
@app_commands.describe(question="Optional question for the oracle")
async def homer_slash(interaction: discord.Interaction, question: str = ""):
    await interaction.response.defer()
    ctx = await bot.get_context(interaction)
    await cmd_homer(ctx, question=question)

@bot.tree.command(name="books", description="List available scripture collections")
@app_commands.describe(section="Optional section name to expand")
async def books_slash(interaction: discord.Interaction, section: str = ""):
    await interaction.response.defer()
    ctx = await bot.get_context(interaction)
    await list_books(ctx, section=section)

@bot.tree.command(name="summa", description="Look up an article from the Summa Theologica")
@app_commands.describe(reference="e.g. I.2.3 | I-II.109.1 | II-II.23 | random")
async def summa_slash(interaction: discord.Interaction, reference: str = ""):
    await interaction.response.defer()
    ctx = await bot.get_context(interaction)
    await cmd_summa(ctx, reference=reference.strip())

@bot.tree.command(name="discover", description="Random passage from any loaded tradition (scripture, patristics, classical texts, and more)")
async def discover_slash(interaction: discord.Interaction):
    await interaction.response.defer()
    ctx = await bot.get_context(interaction)
    await cmd_discover(ctx)

@bot.tree.command(name="study", description="Look up a verse and its patristic commentary together")
@app_commands.describe(reference="e.g. John 3:16")
async def study_slash(interaction: discord.Interaction, reference: str):
    await interaction.response.defer()
    ctx = await bot.get_context(interaction)
    await cmd_study(ctx, reference=reference)

@bot.tree.command(name="save", description="Save a verse to your personal bookmark list")
@app_commands.describe(reference="e.g. John 3:16")
async def save_slash(interaction: discord.Interaction, reference: str):
    await interaction.response.defer()
    ctx = await bot.get_context(interaction)
    await cmd_save(ctx, reference=reference)

@bot.tree.command(name="saved", description="List your saved verses")
async def saved_slash(interaction: discord.Interaction):
    await interaction.response.defer()
    ctx = await bot.get_context(interaction)
    await cmd_saved(ctx)

@bot.tree.command(name="subscribe", description="Get the daily Verse of the Day sent to you by DM")
async def subscribe_slash(interaction: discord.Interaction):
    await interaction.response.defer()
    ctx = await bot.get_context(interaction)
    await cmd_subscribe(ctx)

@bot.tree.command(name="unsubscribe", description="Stop the daily DM Verse of the Day")
async def unsubscribe_slash(interaction: discord.Interaction):
    await interaction.response.defer()
    ctx = await bot.get_context(interaction)
    await cmd_unsubscribe(ctx)


# ── Prefix command  !verse ─────────────────────────────────────────────────────
@bot.command(name="verse", aliases=["v", "scripture"])
async def verse_prefix(ctx, *, reference: str = ""):
    ref = reference.strip()

    # No reference — fully random verse
    if not ref:
        result = lookup.random_verse()
        log.info(f"RNG  random_verse          → {result.get('reference', '?')} (user: {ctx.author})")
        await _send_result(ctx, result)
        return

    # ── Bible shortcuts ───────────────────────────────────────────────────────
    ref_lc = ref.lower()
    if ref_lc.startswith("bible"):
        sub = ref_lc[5:].strip()
        if sub in ("ot", "old testament", "old"):
            result = lookup.random_verse_from_books(BIBLE_OT)
            log.info(f"RNG  random OT             → {result.get('reference', '?')} (user: {ctx.author})")
            await _send_result(ctx, result)
        elif sub in ("nt", "new testament", "new"):
            result = lookup.random_verse_from_books(BIBLE_NT)
            log.info(f"RNG  random NT             → {result.get('reference', '?')} (user: {ctx.author})")
            await _send_result(ctx, result)
        elif sub in ("apocrypha", "apoc", "deuterocanon", "deuterocanonical"):
            result = lookup.random_verse_from_books(BIBLE_APOCRYPHA)
            log.info(f"RNG  random Apocrypha      → {result.get('reference', '?')} (user: {ctx.author})")
            await _send_result(ctx, result)
        elif sub in ("otnt", "ot nt", "nt ot"):
            # Return one from OT and one from NT
            r1 = lookup.random_verse_from_books(BIBLE_OT)
            r2 = lookup.random_verse_from_books(BIBLE_NT)
            await _send_result(ctx, r1)
            await _send_result(ctx, r2)
        else:
            # Just "Bible" — random from OT + NT + Apocrypha
            result = lookup.random_verse_from_books(BIBLE_OT + BIBLE_NT + BIBLE_APOCRYPHA)
            await _send_result(ctx, result)
        return

    # ── Ancient Near East shortcut ────────────────────────────────────────────
    if ref_lc in ("ancient_near_east", "ancient near east", "ane"):
        result = lookup.random_verse_from_books(ANE_BOOKS)
        log.info(f"RNG  random ANE             → {result.get('reference', '?')} (user: {ctx.author})")
        await _send_result(ctx, result)
        return

    # ── Suffix detection ──────────────────────────────────────────────────────
    parts = ref.rsplit(None, 1)
    suffix = parts[1].lower() if len(parts) == 2 else ""

    if suffix in KNOX_SUFFIXES:
        result = get_verse_knox(parts[0].strip())
        await _send_result(ctx, result)
        return

    if suffix in DRB_SUFFIXES:
        result = get_verse_drb(parts[0].strip())
        await _send_result(ctx, result)
        return

    if suffix in TRANSLATION_SUFFIXES:
        # Check for parallel: multiple translation suffixes at end
        tokens = ref.split()
        trans_list = []
        i = len(tokens) - 1
        while i >= 0 and tokens[i].lower() in TRANSLATION_SUFFIXES:
            trans_list.insert(0, tokens[i])
            i -= 1
        if len(trans_list) >= 2:
            base_ref = " ".join(tokens[:i + 1])
            async with ctx.typing():
                result = get_parallel(base_ref, trans_list)
            await _send_parallel(ctx, result)
            return
        # Bare translation slug → random verse in that translation
        if not parts[0].strip():
            async with ctx.typing():
                result = get_random_verse(suffix)
            await _send_result(ctx, result)
            return
        # Single translation lookup
        async with ctx.typing():
            result = get_translation(parts[0].strip(), parts[1])
        await _send_result(ctx, result)
        return

    # ── Normal local lookup ───────────────────────────────────────────────────
    # If the user set a default translation with !prefer and gave no explicit
    # suffix, try that translation first; fall through to local KJV/other-corpus
    # lookup if it doesn't have this reference (e.g. Enoch, Mishnah, Quran --
    # anything outside the Protestant canon bolls.life translations cover).
    preferred = _get_preferred_translation(ctx.author.id)
    if preferred:
        async with ctx.typing():
            pref_result = get_translation(ref, preferred)
        if pref_result.get("found"):
            await _send_result(ctx, pref_result)
            return

    result = lookup.get_verse(ref)
    if result["found"]:
        await _send_result(ctx, result)
        return

    # If it failed to parse (no chapter:verse) try it as a book name for random verse
    if "Could not parse" in result.get("error", ""):
        result = lookup.random_verse_from_book(ref)
        if result.get("found"):
            log.info(f"RNG  random_verse_from_book({ref}) → {result.get('reference', '?')} (user: {ctx.author})")

    await _send_result(ctx, result)


@bot.command(name="search", aliases=["find"])
async def search_prefix(ctx, *, query: str = ""):
    if not query:
        await ctx.send("Usage: `!search <phrase>` or `!search <phrase> ESV` to search a specific translation.")
        return
    if not _check_search_cooldown(ctx.author.id):
        await ctx.send("⏳ Search is rate-limited — please wait a moment.", delete_after=8)
        return

    # Translation suffix → bolls.life search
    tokens = query.split()
    if len(tokens) >= 2 and tokens[-1].lower() in TRANSLATION_SUFFIXES:
        phrase = " ".join(tokens[:-1])
        trans  = tokens[-1]
        async with ctx.typing():
            data = search_translation(phrase, trans, page=1)
        if not data.get("found") or not data.get("results"):
            await ctx.send(f"No results for **{phrase}** in **{trans.upper()}**.")
            return
        embed, view = _build_bolls_search_embed(phrase, trans, data)
        view.message = await ctx.send(embed=embed, view=view)
        return

    # Local corpus search — show overview first
    async with ctx.typing():
        by_corpus = lookup.search_by_corpus(query)

    if not by_corpus:
        await ctx.send(f"No results found for **{query}**.")
        return

    total_hits = sum(len(hits) for hits in by_corpus.values())
    await _send_search_overview(ctx, query, by_corpus, total_hits)


async def _send_search_overview(ctx, query: str, by_corpus: dict, total_hits: int):
    """
    Send the corpus overview embed with a button per corpus.
    Each button shows that corpus's results paginated.
    """
    embed = discord.Embed(
        title=f'🔍 "{query}" — {total_hits:,} result{"s" if total_hits != 1 else ""}',
        color=discord.Color.gold()
    )
    # One line per corpus: emoji label + count
    lines = []
    corpus_order = sorted(by_corpus.items(), key=lambda x: -len(x[1]))
    for label, hits in corpus_order:
        lines.append(f"{label} — **{len(hits):,}**")
    embed.description = "\n".join(lines)
    embed.set_footer(text="Click a corpus button to browse results · !search <phrase> ESV to search a translation")

    class SearchOverviewView(discord.ui.View):
        def __init__(self):
            super().__init__(timeout=120)
            # Add one button per corpus (max 5 rows × 5 buttons = 25, but we cap at 20)
            for i, (label, hits) in enumerate(corpus_order[:20]):
                # Strip emoji prefix for button label, keep short
                short = label.split(" ", 1)[-1][:40]  # drop the emoji
                btn = discord.ui.Button(
                    label=f"{short} ({len(hits)})",
                    style=discord.ButtonStyle.primary,
                    row=i // 4,
                )
                btn.callback = self._make_callback(label, hits)
                self.add_item(btn)

        def _make_callback(self, label: str, hits: list):
            async def callback(interaction: discord.Interaction):
                e, v = _build_corpus_results_embed(query, label, hits, offset=0)
                v.message = await interaction.response.send_message(embed=e, view=v)
            return callback

        async def on_timeout(self):
            try:
                await self.message.edit(view=None)
            except Exception:
                pass

    view = SearchOverviewView()
    view.message = await ctx.send(embed=embed, view=view)


def _build_corpus_results_embed(query: str, corpus_label: str, hits: list,
                                 offset: int = 0, page_size: int = 5):
    """Paginated results embed for a single corpus."""
    PAGE = page_size
    total = len(hits)
    page_num    = offset // PAGE + 1
    total_pages = max(1, (total + PAGE - 1) // PAGE)
    page_hits   = hits[offset:offset + PAGE]

    embed = discord.Embed(
        title=f'🔍 "{query}" in {corpus_label}',
        color=discord.Color.gold()
    )
    embed.set_footer(text=f"Page {page_num}/{total_pages} · {total} result{'s' if total != 1 else ''}")

    q_lower = query.lower()
    for r in page_hits:
        snippet = r["text"]
        idx = snippet.lower().find(q_lower)
        if idx != -1:
            snippet = (snippet[:idx] + "**" + snippet[idx:idx+len(query)]
                       + "**" + snippet[idx+len(query):])
        if len(snippet) > 300:
            start = max(0, idx - 80) if idx != -1 else 0
            snippet = ("…" if start else "") + snippet[start:start+300] + "…"
        embed.add_field(name=r["reference"], value=snippet, inline=False)

    class CorpusResultsView(discord.ui.View):
        def __init__(self):
            super().__init__(timeout=180)
            self._offset = offset
            if page_num > 1:
                b = discord.ui.Button(label="◀ Prev", style=discord.ButtonStyle.secondary)
                async def prev(interaction: discord.Interaction):
                    new_off = max(0, self._offset - PAGE)
                    e, v = _build_corpus_results_embed(query, corpus_label, hits, new_off, PAGE)
                    v.message = self.message
                    await interaction.response.edit_message(embed=e, view=v)
                b.callback = prev
                self.add_item(b)

            self.add_item(discord.ui.Button(
                label=f"{page_num}/{total_pages}",
                style=discord.ButtonStyle.secondary,
                disabled=True
            ))

            if page_num < total_pages:
                b = discord.ui.Button(label="Next ▶", style=discord.ButtonStyle.secondary)
                async def nxt(interaction: discord.Interaction):
                    new_off = self._offset + PAGE
                    e, v = _build_corpus_results_embed(query, corpus_label, hits, new_off, PAGE)
                    v.message = self.message
                    await interaction.response.edit_message(embed=e, view=v)
                b.callback = nxt
                self.add_item(b)

        async def on_timeout(self):
            try:
                await self.message.edit(view=None)
            except Exception:
                pass

    return embed, CorpusResultsView()



# ── Stats tracking helpers ───────────────────────────────────────────────────

_CATEGORY_BOOKS = {
    "📖 Bible":            set(BIBLE_OT + BIBLE_NT),
    "👼 Apocrypha":        {
        "1 Esdras","2 Esdras","Tobit","Judith","Wisdom of Solomon",
        "Sirach","Baruch","1 Maccabees","2 Maccabees","Book of Enoch",
        "Book of Jubilees","3 Maccabees","4 Maccabees","Psalms of Solomon",
        "Testament of Reuben","Testament of Simeon","Testament of Levi",
        "Testament of Judah","Testament of Issachar","Testament of Zebulun",
        "Testament of Dan","Testament of Naphtali","Testament of Gad",
        "Testament of Asher","Testament of Joseph","Testament of Benjamin",
        "Assumption of Moses","Ascension of Isaiah","Sibylline Oracles",
        "Letter of Aristeas","Vita Adae et Evae","Apocalypse of Moses",
        "Fragments of a Zadokite Work",
    },
    "✡️ Halakha/Kabbalah": {
        "Zohar","Berakhot","Shabbat","Sanhedrin","Avot","Bava Kamma",
    },
    "☪️ Islamic":          {
        "Quran","Sahih al-Bukhari","Sahih Muslim","Sunan Abu Dawud",
        "Jami at-Tirmidhi","Sunan an-Nasa'i","Sunan Ibn Majah",
        "Muwatta Malik","Forty Hadith of Nawawi",
    },
    "🏛️ Classical":        {
        "Enneads","Republic","Iliad","Odyssey","Theology of Plato",
        "On the Mysteries","On Abstinence","Against the Galilaeans",
        "On the Gods and the World","Nicomachean Ethics","Metaphysics",
        "Corpus Hermeticum","Chaldaean Oracles","Orphic Hymns",
    },
    "📯 LDS":              {
        "1 Nephi","2 Nephi","Mosiah","Alma","Helaman","3 Nephi","4 Nephi",
        "Mormon","Ether","Moroni","Doctrine and Covenants",
        "Moses","Abraham","Articles of Faith",
    },
    "⛪ Patristics":        {
        "Confessions","City of God","On the Trinity","Against Celsus",
        "Adversus haereses","First Apology","Dialogue with Trypho",
        "Homilies on Matthew","Homilies on John","Homilies on Romans",
        "Epistle of Barnabas","Didache","Shepherd of Hermas",
        "1 Clement","2 Clement","Catechetical Lectures",
    },
    "🧿 Gnostic/Hermetic":  {
        "Ginza Rba","Book of John","Asclepius",
        "The Prayer of Paul, the Apostle","The Secret Book of James",
        "Treatise on the Resurrection","The Tripartite Tractate",
        "The Substance of the Archons","On the Origin of the World",
        "The Exegesis on the Soul","The Book of Thomas the Contender",
        "The Sacred Book of the Great Unseen Spirit","Eugnostos the Blessed",
        "The Sophia of Jesus Christ","The Dialogue of the Savior",
        "The Apocalypse of Paul","The Second Apocalypse of James",
        "The Apocalypse of Adam","The Acts of Peter and the Twelve Apostles",
        "The Thunder, Perfect Mind","The Authentic Logos",
        "The Idea of Our Great Power","The Discourse on the Eighth and Ninth",
        "The Prayer of Thanksgiving","Excerpt from the Perfect Discourse",
        "The Paraphrase of Shem","The Second Discourse of the Great Seth",
        "The Apocalypse of Peter","The Teachings of Silvanus",
        "The Three Steles of Seth","Zostrianos","The Letter of Peter to Philip",
        "Melchizedek","The Thought of Norea","The Testimony of Truth",
        "Marsanes","The Interpretation of Knowledge",
        "A Valentinian Exposition and Liturgical Readings",
        "Allogenes (The Stranger)","Hypsiphrone","The Sentences of Sextus",
        "Trimorphic Protennoia (Three Forms of Primal Thought)",
        "Corpus Hermeticum XIII, On Rebirth","The Act of Peter",
        "Manichaean Psalms to Jesus","Manichaean Bema Psalms",
        "Manichaean Psalms of Thomas","Manichaean Psalms (Separate)",
    },
    "☸️ Dharmic":           {"Rig Veda","Yajur Veda","Sama Veda","Atharva Veda"},
    "🌲 Norse":             {"Voluspo","Hovamol","Iliad"},
    "🔥 Zoroastrian":       {"Gathas"},
    "🌍 Baháʼí":            {
        "Kitab-i-Aqdas", "The Hidden Words (Arabic)", "The Hidden Words (Persian)",
        "Gleanings from the Writings of Baha'u'llah", "Prayers and Meditations",
        "Some Answered Questions", "Kitab-i-Iqan", "Epistle to the Son of the Wolf",
    },
    "🏺 Dead Sea Scrolls":  {
        "Hodayot", "Damascus Document", "Community Rule", "War Scroll",
        "Pesher Habakkuk", "Rule of the Congregation", "Rule of Blessings",
    },
}

def _infer_category(book: str) -> str:
    for cat, books in _CATEGORY_BOOKS.items():
        if book in books:
            return cat
    return "Other"


# ── !stats command ─────────────────────────────────────────────────────────────

@bot.command(name="stats", aliases=["botstats"])
async def cmd_stats(ctx):
    """Show scripture bot usage statistics."""
    stats = _load_stats()
    total_cmds  = stats.get("total_commands", 0)
    total_users = len(stats.get("unique_users", []))
    book_counts  = stats.get("book_counts",  {})
    verse_counts = stats.get("verse_counts", {})
    cmd_counts   = stats.get("command_counts", {})
    special      = stats.get("special_counts", {})

    top_books  = sorted(book_counts.items(),  key=lambda x: x[1], reverse=True)[:5]
    top_verses = sorted(verse_counts.items(), key=lambda x: x[1], reverse=True)[:5]
    top_cmds   = sorted(cmd_counts.items(),   key=lambda x: x[1], reverse=True)[:8]

    cat_totals: dict = {}
    for book, count in book_counts.items():
        cat = _infer_category(book)
        cat_totals[cat] = cat_totals.get(cat, 0) + count
    top_cat = max(cat_totals, key=cat_totals.get) if cat_totals else "Not enough data yet"

    scan_note = (
        "" if stats.get("retroactive_scan_done")
        else "\n*Run `!scanstats` to include historical messages.*"
    )

    embed = discord.Embed(title="📊 Scripture Bot Statistics", color=discord.Color.dark_gold())
    embed.add_field(
        name="Overview",
        value=f"**{total_cmds:,}** commands issued\n**{total_users:,}** unique users{scan_note}",
        inline=False,
    )
    if top_cmds:
        embed.add_field(
            name="⚡ Most Used Commands",
            value="\n".join(f"{i+1}. `!{cmd}` ({c:,})" for i, (cmd, c) in enumerate(top_cmds)),
            inline=False,
        )
    if top_books:
        embed.add_field(
            name="📚 Most Cited Books",
            value="\n".join(f"{i+1}. **{b}** ({c:,})" for i, (b, c) in enumerate(top_books)),
            inline=True,
        )
    if top_verses:
        embed.add_field(
            name="📜 Most Cited Verses",
            value="\n".join(f"{i+1}. {v} ({c:,})" for i, (v, c) in enumerate(top_verses)),
            inline=True,
        )
    embed.add_field(name="🏆 Most Popular Category", value=top_cat, inline=False)

    # Special command leaderboards
    SPECIAL_LABELS = {
        "ccc":    ("📖 Top CCC Paragraphs",   5),
        "canon":  ("⚖️ Top Canons",            5),
        "summa":  ("🧠 Top Summa Articles",    5),
        "virgil": ("🕊️ Top Virgil Draws",      5),
        "homer":  ("🎲 Top Homer Rolls",       5),
        "delphi": ("🏛️ Top Delphic Maxims",    5),
        "oracle": ("🔮 Top Oracle Draws",      5),
    }
    for cmd_key, (label, top_n) in SPECIAL_LABELS.items():
        refs = special.get(cmd_key, {})
        if not refs:
            continue
        top_refs = sorted(refs.items(), key=lambda x: x[1], reverse=True)[:top_n]
        embed.add_field(
            name=label,
            value="\n".join(f"{i+1}. {r} ({c:,})" for i, (r, c) in enumerate(top_refs)),
            inline=True,
        )

    await ctx.send(embed=embed)


# ── !guildactivity command (owner-only) ─────────────────────────────────────────

@bot.command(name="guildactivity", aliases=["whoswhere"])
@commands.is_owner()
async def cmd_guild_activity(ctx, *, guild_query: str = ""):
    """Owner-only: per-server command usage. !guildactivity <name> drills
    into one server's per-user breakdown."""
    data = _load_guild_activity()
    if not data:
        await ctx.send("No guild activity recorded yet.")
        return

    if guild_query:
        match = next(
            ((gid, g) for gid, g in data.items()
             if guild_query.lower() in g.get("name", "").lower() or guild_query == gid),
            None,
        )
        if not match:
            await ctx.send(f"No recorded server matching `{guild_query}`.")
            return
        gid, g = match
        embed = discord.Embed(title=f"📊 {g.get('name', 'Unknown')}", color=discord.Color.dark_gold())
        top_cmds = sorted(g.get("commands", {}).items(), key=lambda x: x[1], reverse=True)[:10]
        embed.add_field(
            name="Top commands",
            value="\n".join(f"`!{c}` — {n:,}" for c, n in top_cmds) or "—",
            inline=False,
        )
        top_users = sorted(
            g.get("users", {}).items(),
            key=lambda kv: sum(kv[1].get("commands", {}).values()),
            reverse=True,
        )[:10]
        lines = []
        for uid, u in top_users:
            total = sum(u.get("commands", {}).values())
            top_cmd, top_n = max(u.get("commands", {}).items(), key=lambda x: x[1], default=(None, 0))
            top_note = f" (top: `!{top_cmd}` ×{top_n})" if top_cmd else ""
            lines.append(f"**{u.get('name', '?')}** — {total:,}{top_note}")
        embed.add_field(name="Top users", value="\n".join(lines) or "—", inline=False)
        embed.set_footer(text=f"Guild ID: {gid}")
        await ctx.send(embed=embed)
        return

    rows = []
    for gid, g in sorted(data.items(), key=lambda kv: sum(kv[1].get("commands", {}).values()), reverse=True):
        total = sum(g.get("commands", {}).values())
        top_cmd, top_n = max(g.get("commands", {}).items(), key=lambda x: x[1], default=(None, 0))
        top_note = f" · top: `!{top_cmd}` ×{top_n}" if top_cmd else ""
        rows.append(f"**{g.get('name', 'Unknown')}** — {total:,} commands{top_note}")

    embed = discord.Embed(title="📊 Guild Activity", color=discord.Color.dark_gold())
    embed.description = "\n".join(rows)
    embed.set_footer(text="!guildactivity <server name> for a per-user breakdown")
    await ctx.send(embed=embed)


# ── !scanstats command ─────────────────────────────────────────────────────────

@bot.command(name="scanstats", aliases=["retrostat", "historystats"])
@commands.has_permissions(administrator=True)
async def cmd_scanstats(ctx):
    """(Admin only) One-time retroactive scan of all server history to build stats.
    Subsequent calls do nothing — run !stats to view results."""
    stats = _load_stats()
    if stats.get("retroactive_scan_done"):
        await ctx.send("✅ Retroactive scan already completed. Use `!stats` to view results.")
        return

    msg = await ctx.send("🔍 Scanning server message history… this may take a while.")

    verse_counts:   dict = {}
    book_counts:    dict = {}
    cmd_counts:     dict = {}
    special_counts: dict = {}
    user_ids:       set  = set()
    total = 0

    # Regex for auto-detected inline references (same as bot's _AUTO_RE if defined)
    auto_re = re.compile(
        r"\b((?:\d\s*)?[A-Z][a-zA-Z]{2,}(?:\s+[A-Z][a-zA-Z]+)?)\s+(\d+):(\d+)\b"
    )

    for channel in ctx.guild.text_channels:
        try:
            async for message in channel.history(limit=None, oldest_first=True):
                if message.author.bot:
                    continue
                content = message.content.strip()
                uid = str(message.author.id)

                # !verse / !v / !scripture commands
                m = re.match(
                    r"^[!](?:verse|v|scripture)\s+(.*)", content, re.IGNORECASE
                )
                if m:
                    ref_raw = m.group(1).strip()
                    result  = lookup.get_verse(ref_raw)
                    if result.get("found"):
                        user_ids.add(uid)
                        total += 1
                        book = result.get("book") or result.get("reference", "").split()[0]
                        ref  = result.get("reference", "")
                        if book: book_counts[book] = book_counts.get(book, 0) + 1
                        if ref:  verse_counts[ref] = verse_counts.get(ref, 0) + 1

                # Auto-detected inline references
                for auto_match in auto_re.finditer(content):
                    auto_ref = (
                        f"{auto_match.group(1).strip()} "
                        f"{auto_match.group(2)}:{auto_match.group(3)}"
                    )
                    result = lookup.get_verse(auto_ref)
                    if result.get("found"):
                        user_ids.add(uid)
                        total += 1
                        book = result.get("book") or result.get("reference", "").split()[0]
                        ref  = result.get("reference", "")
                        if book: book_counts[book] = book_counts.get(book, 0) + 1
                        if ref:  verse_counts[ref] = verse_counts.get(ref, 0) + 1

                # !ccc <N>
                m = re.match(r"^[!]ccc\s+(\d+)", content, re.IGNORECASE)
                if m:
                    user_ids.add(uid); total += 1; cmd_counts["ccc"] = cmd_counts.get("ccc", 0) + 1
                    special_counts.setdefault("ccc", {})
                    k = f"CCC {m.group(1)}"
                    special_counts["ccc"][k] = special_counts["ccc"].get(k, 0) + 1

                # !canon <N>
                m = re.match(r"^[!]canon\s+(\d+)", content, re.IGNORECASE)
                if m:
                    user_ids.add(uid); total += 1; cmd_counts["canon"] = cmd_counts.get("canon", 0) + 1
                    special_counts.setdefault("canon", {})
                    k = f"Canon {m.group(1)}"
                    special_counts["canon"][k] = special_counts["canon"].get(k, 0) + 1

                # !summa <ref>
                m = re.match(r"^[!](?:summa|st|aquinas|thomas)\s+(\S+)", content, re.IGNORECASE)
                if m:
                    user_ids.add(uid); total += 1; cmd_counts["summa"] = cmd_counts.get("summa", 0) + 1
                    ref_raw = m.group(1).strip()
                    parsed = parse_summa_ref(ref_raw)
                    if parsed:
                        part, question, article = parsed
                        k = f"ST {part}.{question}" + (f".{article}" if article else "")
                        special_counts.setdefault("summa", {})
                        special_counts["summa"][k] = special_counts["summa"].get(k, 0) + 1

                # !virgil / !aeneid  (random — just count the command, no specific ref)
                m = re.match(r"^[!](?:virgil|sortesvir|aeneid)\b", content, re.IGNORECASE)
                if m:
                    user_ids.add(uid); total += 1; cmd_counts["virgil"] = cmd_counts.get("virgil", 0) + 1
                    # Can't recover the random result from history — skip ref tracking

                # !homer (random — just count)
                m = re.match(r"^[!](?:homer|homeromanteion|sortes)\b", content, re.IGNORECASE)
                if m:
                    user_ids.add(uid); total += 1; cmd_counts["homer"] = cmd_counts.get("homer", 0) + 1

                # !delphi (random)
                m = re.match(r"^[!]delphi\b", content, re.IGNORECASE)
                if m:
                    user_ids.add(uid); total += 1; cmd_counts["delphi"] = cmd_counts.get("delphi", 0) + 1

                # !oracle (random)
                m = re.match(r"^[!]oracle\b", content, re.IGNORECASE)
                if m:
                    user_ids.add(uid); total += 1; cmd_counts["oracle"] = cmd_counts.get("oracle", 0) + 1

                # Other tracked commands (count only)
                for cmd_pat, cmd_name in [
                    (r"^[!](?:books|book)\b",          "books"),
                    (r"^[!](?:random|rand|rv)\b",       "random"),
                    (r"^[!](?:votd|verseoftheday)\b",   "votd"),
                    (r"^[!](?:catena)\b",               "catena"),
                    (r"^[!](?:search|find)\b",          "search"),
                ]:
                    if re.match(cmd_pat, content, re.IGNORECASE):
                        user_ids.add(uid); total += 1
                        cmd_counts[cmd_name] = cmd_counts.get(cmd_name, 0) + 1

        except discord.Forbidden:
            pass
        except Exception:
            pass

    # Merge with any existing live stats
    existing_vc = stats.get("verse_counts", {})
    existing_bc = stats.get("book_counts",  {})
    existing_cc = stats.get("command_counts", {})
    existing_sp = stats.get("special_counts", {})
    for k, v in verse_counts.items():
        existing_vc[k] = existing_vc.get(k, 0) + v
    for k, v in book_counts.items():
        existing_bc[k] = existing_bc.get(k, 0) + v
    for k, v in cmd_counts.items():
        existing_cc[k] = existing_cc.get(k, 0) + v
    for cmd_key, refs in special_counts.items():
        cmd_bucket = existing_sp.setdefault(cmd_key, {})
        for k, v in refs.items():
            cmd_bucket[k] = cmd_bucket.get(k, 0) + v
    for uid in user_ids:
        if uid not in stats.get("unique_users", []):
            stats.setdefault("unique_users", []).append(uid)

    stats["verse_counts"]          = existing_vc
    stats["book_counts"]           = existing_bc
    stats["command_counts"]        = existing_cc
    stats["special_counts"]        = existing_sp
    stats["total_commands"]        = stats.get("total_commands", 0) + total
    stats["retroactive_scan_done"] = True
    _save_stats(stats)

    await msg.edit(content=(
        f"✅ Scan complete! Found **{total:,}** verse references across "
        f"**{len(user_ids):,}** users. Use `!stats` to see the results."
    ))


# ── !books — Hierarchical scripture browser ────────────────────────────────────

BOOKS_TREE = [
    ("📖 The Bible", [
        ("Old Testament", [
            "Genesis","Exodus","Leviticus","Numbers","Deuteronomy","Joshua",
            "Judges","Ruth","1 Samuel","2 Samuel","1 Kings","2 Kings",
            "1 Chronicles","2 Chronicles","Ezra","Nehemiah","Esther","Job",
            "Psalms","Proverbs","Ecclesiastes","Song of Solomon","Isaiah",
            "Jeremiah","Lamentations","Ezekiel","Daniel","Hosea","Joel",
            "Amos","Obadiah","Jonah","Micah","Nahum","Habakkuk","Zephaniah",
            "Haggai","Zechariah","Malachi",
        ]),
        ("New Testament", [
            "Matthew","Mark","Luke","John","Acts","Romans",
            "1 Corinthians","2 Corinthians","Galatians","Ephesians",
            "Philippians","Colossians","1 Thessalonians","2 Thessalonians",
            "1 Timothy","2 Timothy","Titus","Philemon","Hebrews","James",
            "1 Peter","2 Peter","1 John","2 John","3 John","Jude","Revelation",
        ]),
    ]),
    ("👼 Apocrypha / Pseudepigrapha", [
        ("Apocrypha (KJV)", [
            "1 Esdras","2 Esdras","Tobit","Judith","Additions to Esther",
            "Wisdom of Solomon","Sirach","Baruch","Epistle of Jeremiah",
            "Song of the Three Children","Susanna","Bel and the Dragon",
            "Prayer of Manasseh","1 Maccabees","2 Maccabees",
        ]),
        ("Pseudepigrapha", [
            "3 Maccabees","4 Maccabees","Psalms of Solomon",
            "Psalm 151","Psalm 152","Psalm 153","Psalm 154","Psalm 155",
            "Book of Enoch","Book of Jubilees",
            "Testament of Reuben","Testament of Simeon","Testament of Levi",
            "Testament of Judah","Testament of Issachar","Testament of Zebulun",
            "Testament of Dan","Testament of Naphtali","Testament of Gad",
            "Testament of Asher","Testament of Joseph","Testament of Benjamin",
            "Assumption of Moses","Ascension of Isaiah","Sibylline Oracles",
            "Letter of Aristeas","Vita Adae et Evae","Apocalypse of Moses",
            "Fragments of a Zadokite Work",
        ]),
    ]),
    ("✡️ Rabbinic & Kabbalistic", [
        ("Mishnah", [
            ("Seder Zeraim (Agriculture)", [
                "Berakhot","Peah","Demai","Kilayim","Sheviit",
                "Terumot","Maasrot","Maaser Sheni","Challah","Orlah","Bikkurim",
            ]),
            ("Seder Moed (Festivals)", [
                "Shabbat","Eruvin","Pesachim","Shekalim","Yoma","Sukkah",
                "Beitzah","Rosh Hashanah","Taanit","Megillah","Moed Katan","Chagigah",
            ]),
            ("Seder Nashim (Women)", [
                "Yevamot","Ketubot","Nedarim","Nazir","Sotah","Gittin","Kiddushin",
            ]),
            ("Seder Nezikin (Damages)", [
                "Bava Kamma","Bava Metzia","Bava Batra","Sanhedrin","Makkot",
                "Shevuot","Eduyot","Avodah Zarah","Avot","Horayot",
            ]),
            ("Seder Kodashim (Temple)", [
                "Zevachim","Menachot","Chullin","Bechorot","Arachin",
                "Temurah","Keritot","Meilah","Tamid","Middot","Kinnim",
            ]),
            ("Seder Taharot (Purity)", [
                "Keilim","Ohalot","Negaim","Parah","Taharot","Mikvaot",
                "Niddah","Machshirin","Zavim","Tevul Yom","Yadayim","Oktzin",
            ]),
        ]),
        ("Tosefta", [
            ("Seder Zeraim", [
                "Tosefta Berakhot","Tosefta Peah","Tosefta Demai","Tosefta Kilayim",
                "Tosefta Sheviit","Tosefta Terumot","Tosefta Maasrot",
                "Tosefta Maaser Sheni","Tosefta Challah","Tosefta Orlah","Tosefta Bikkurim",
            ]),
            ("Seder Moed", [
                "Tosefta Shabbat","Tosefta Eruvin","Tosefta Pesachim","Tosefta Shekalim",
                "Tosefta Yoma","Tosefta Sukkah","Tosefta Beitzah",
                "Tosefta Rosh Hashanah","Tosefta Taanit","Tosefta Megillah",
                "Tosefta Moed Katan","Tosefta Chagigah",
            ]),
            ("Seder Nashim", [
                "Tosefta Yevamot","Tosefta Ketubot","Tosefta Nedarim","Tosefta Nazir",
                "Tosefta Sotah","Tosefta Gittin","Tosefta Kiddushin",
            ]),
            ("Seder Nezikin", [
                "Tosefta Bava Kamma","Tosefta Bava Metzia","Tosefta Bava Batra",
                "Tosefta Sanhedrin","Tosefta Makkot","Tosefta Shevuot",
                "Tosefta Eduyot","Tosefta Avodah Zarah","Tosefta Horayot",
            ]),
        ]),
        ("Babylonian Talmud", [
            ("Seder Zeraim", ["Berakhot"]),
            ("Seder Moed", [
                "Shabbat","Eruvin","Pesachim","Shekalim","Yoma","Sukkah",
                "Beitzah","Rosh Hashanah","Taanit","Megillah","Moed Katan","Chagigah",
            ]),
            ("Seder Nashim", [
                "Yevamot","Ketubot","Nedarim","Nazir","Sotah","Gittin","Kiddushin",
            ]),
            ("Seder Nezikin", [
                "Bava Kamma","Bava Metzia","Bava Batra","Sanhedrin","Makkot",
                "Shevuot","Avodah Zarah","Horayot",
            ]),
            ("Seder Kodashim", [
                "Zevachim","Menachot","Chullin","Bechorot","Arachin",
                "Temurah","Keritot","Meilah","Tamid","Niddah",
            ]),
        ]),
        ("Jerusalem Talmud", [
            ("Seder Zeraim", [
                "Jerusalem Talmud Berakhot","Jerusalem Talmud Peah",
                "Jerusalem Talmud Demai","Jerusalem Talmud Kilayim",
                "Jerusalem Talmud Sheviit","Jerusalem Talmud Terumot",
                "Jerusalem Talmud Maaserot","Jerusalem Talmud Maaser Sheni",
                "Jerusalem Talmud Challah","Jerusalem Talmud Orlah",
                "Jerusalem Talmud Bikkurim",
            ]),
            ("Seder Moed", [
                "Jerusalem Talmud Shabbat","Jerusalem Talmud Eruvin",
                "Jerusalem Talmud Pesachim","Jerusalem Talmud Shekalim",
                "Jerusalem Talmud Yoma","Jerusalem Talmud Sukkah",
                "Jerusalem Talmud Beitzah","Jerusalem Talmud Rosh Hashanah",
                "Jerusalem Talmud Taanit","Jerusalem Talmud Megillah",
                "Jerusalem Talmud Moed Katan","Jerusalem Talmud Chagigah",
            ]),
            ("Seder Nashim", [
                "Jerusalem Talmud Yevamot","Jerusalem Talmud Ketubot",
                "Jerusalem Talmud Nedarim","Jerusalem Talmud Nazir",
                "Jerusalem Talmud Sotah","Jerusalem Talmud Gittin",
                "Jerusalem Talmud Kiddushin",
            ]),
            ("Seder Nezikin", [
                "Jerusalem Talmud Bava Kamma","Jerusalem Talmud Bava Metzia",
                "Jerusalem Talmud Bava Batra","Jerusalem Talmud Sanhedrin",
                "Jerusalem Talmud Makkot","Jerusalem Talmud Shevuot",
                "Jerusalem Talmud Avodah Zarah","Jerusalem Talmud Horayot",
                "Jerusalem Talmud Niddah",
            ]),
        ]),
        ("Targumim", [
            ("Torah Targumim", [
                "Targum Onkelos Genesis","Targum Onkelos Exodus",
                "Targum Onkelos Leviticus","Targum Onkelos Numbers",
                "Targum Onkelos Deuteronomy",
                "Targum Pseudo-Jonathan Genesis","Targum Pseudo-Jonathan Exodus",
                "Targum Neofiti Genesis","Targum Neofiti Exodus",
            ]),
            ("Prophets & Writings", [
                "Targum Jonathan Isaiah","Targum Jonathan Jeremiah",
                "Targum Jonathan Ezekiel","Targum Jonathan Hosea",
                "Targum Jonathan Psalms","Targum Jonathan Proverbs",
                "Targum Jonathan Job",
            ]),
        ]),
        ("Midrash", [
            ("Midrash Rabbah", [
                "Bereshit Rabbah","Shemot Rabbah","Vayikra Rabbah",
                "Bamidbar Rabbah","Devarim Rabbah","Ruth Rabbah",
                "Esther Rabbah","Eichah Rabbah","Shir HaShirim Rabbah",
                "Kohelet Rabbah",
            ]),
            ("Halachic Midrash", [
                "Mechilta","Sifra","Sifre Bamidbar","Sifre Devarim",
            ]),
            ("Aggadic Midrash", [
                "Pirkei DeRabbi Eliezer","Midrash Tanchuma",
            ]),
        ]),
        ("Maimonides", [
            ("Mishneh Torah — Book 1: HaMadda", [
                "Mishneh Torah, Foundations of the Torah",
                "Mishneh Torah, Human Dispositions",
                "Mishneh Torah, Torah Study",
                "Mishneh Torah, Foreign Worship and Customs of the Nations",
                "Mishneh Torah, Repentance",
            ]),
            ("Mishneh Torah — Book 2: Ahavah", [
                "Mishneh Torah, Reading the Shema",
                "Mishneh Torah, Prayer and the Priestly Blessing",
                "Mishneh Torah, Tefillin, Mezuzah and the Torah Scroll",
                "Mishneh Torah, Fringes",
                "Mishneh Torah, Blessings",
                "Mishneh Torah, Circumcision",
                "Mishneh Torah, The Order of Prayer",
            ]),
            ("Mishneh Torah — Book 3: Zemanim", [
                "Mishneh Torah, Sabbath",
                "Mishneh Torah, Eruvin",
                "Mishneh Torah, Rest on the Tenth of Tishrei",
                "Mishneh Torah, Rest on a Holiday",
                "Mishneh Torah, Leavened and Unleavened Bread",
                "Mishneh Torah, Shofar, Sukkah and Lulav",
                "Mishneh Torah, Sheqel Dues",
                "Mishneh Torah, Sanctification of the New Month",
                "Mishneh Torah, Fasts",
                "Mishneh Torah, Megillah and Hanukkah",
            ]),
            ("Mishneh Torah — Book 4–5: Nashim & Kedushah", [
                "Mishneh Torah, Marriage",
                "Mishneh Torah, Divorce",
                "Mishneh Torah, Levirate Marriage and Release",
                "Mishneh Torah, Virgin Maiden",
                "Mishneh Torah, Sotah",
                "Mishneh Torah, Forbidden Intercourse",
                "Mishneh Torah, Forbidden Foods",
                "Mishneh Torah, Slaughter",
            ]),
            ("Mishneh Torah — Books 6–7: Haflaah & Zeraim", [
                "Mishneh Torah, Oaths",
                "Mishneh Torah, Vows",
                "Mishneh Torah, Naziriteship",
                "Mishneh Torah, Appraisals and Devoted Property",
                "Mishneh Torah, Diverse Species",
                "Mishneh Torah, Gifts to the Poor",
                "Mishneh Torah, Heave Offerings",
                "Mishneh Torah, Tithes",
                "Mishneh Torah, Second Tithe and Fourth Year Produce",
                "Mishneh Torah, First Fruits and other Gifts to Priests Outside the Temple",
                "Mishneh Torah, Sabbatical Year and the Jubilee",
            ]),
            ("Mishneh Torah — Books 8–10: Temple, Offerings & Purity", [
                "Mishneh Torah, The Chosen Temple",
                "Mishneh Torah, Vessels of the Sanctuary and Those who Serve Therein",
                "Mishneh Torah, Admission into the Sanctuary",
                "Mishneh Torah, Sacrificial Procedure",
                "Mishneh Torah, Daily Offerings and Additional Offerings",
                "Mishneh Torah, The Yom Kippur Service",
                "Mishneh Torah, Paschal Offering",
                "Mishneh Torah, Festival Offering",
                "Mishneh Torah, Firstborn",
                "Mishneh Torah, Corpse Impurity",
                "Mishneh Torah, Red Heifer",
                "Mishneh Torah, Leprosy",
                "Mishneh Torah, Immersion Pools",
            ]),
            ("Mishneh Torah — Books 11–14: Civil & Judicial", [
                "Mishneh Torah, Property Damage",
                "Mishneh Torah, Theft",
                "Mishneh Torah, Robbery and Lost Property",
                "Mishneh Torah, Murderers and the Preservation of Life",
                "Mishneh Torah, Sales",
                "Mishneh Torah, Neighbors",
                "Mishneh Torah, Agents and Partners",
                "Mishneh Torah, Hiring",
                "Mishneh Torah, Creditor and Debtor",
                "Mishneh Torah, Inheritance",
                "Mishneh Torah, Courts",
                "Mishneh Torah, Testimony",
                "Mishneh Torah, Mourning",
                "Mishneh Torah, Kings and Wars",
            ]),
            ("Other Works", [
                "Guide for the Perplexed",
                "Mishnah Torah",
            ]),
        ]),
        ("Kabbalah", [
            ("Zohar", [
                "Zohar Introduction",
                "Zohar Bereshit","Zohar Noach","Zohar Lech Lecha",
                "Zohar Vayera","Zohar Chayei Sarah","Zohar Toldot",
                "Zohar Vayetze","Zohar Vayishlach","Zohar Vayeshev",
                "Zohar Miketz","Zohar Vayigash","Zohar Vayechi",
                "Zohar Shemot","Zohar Vaera","Zohar Bo",
                "Zohar Beshalach","Zohar Yitro","Zohar Mishpatim",
                "Zohar Terumah","Zohar Tetzaveh","Zohar Ki Tisa",
                "Zohar Vayakhel","Zohar Pekudei","Zohar Vayikra",
                "Zohar Tzav","Zohar Shmini","Zohar Tazria",
                "Zohar Metzora","Zohar Acharei Mot","Zohar Kedoshim",
                "Zohar Emor","Zohar Behar","Zohar Bechukotai",
                "Zohar Bamidbar","Zohar Nasso","Zohar Behaalotcha",
                "Zohar Shelach Lecha","Zohar Korach","Zohar Chukat",
                "Zohar Balak","Zohar Pinchas","Zohar Matot",
                "Zohar Vaetchanan","Zohar Eikev","Zohar Re'eh",
                "Zohar Shoftim","Zohar Ki Teitzei","Zohar Ki Tavo",
                "Zohar Vayeilech","Zohar Haazinu","Zohar Vezot Haberachah",
            ]),
            ("Other Kabbalah", [
                "Sefer Yetzirah",
                "Sefer HaBahir",
                "Tikkunei Zohar",
                "Zohar Chadash",
                "Tanya",
            ]),
        ]),
    ]),
    ("☪️ Islamic", [
        ("Quran", [
            ("Juz 1–2: Al-Faatiha through Al-Baqara", [
                "Quran 1 — Al-Faatiha (The Opening, 7v)",
                "Quran 2 — Al-Baqara (The Cow, 286v)",
            ]),
            ("Juz 3–5: Aali Imran through An-Nisaa", [
                "Quran 3 — Aali Imran (Family of Imran, 200v)",
                "Quran 4 — An-Nisaa (The Women, 176v)",
            ]),
            ("Juz 6–7: Al-Maaida through Al-Araaf", [
                "Quran 5 — Al-Maaida (The Table, 120v)",
                "Quran 6 — Al-Anaam (The Cattle, 165v)",
                "Quran 7 — Al-Araaf (The Heights, 206v)",
            ]),
            ("Juz 8–10: Al-Anfaal through Yunus", [
                "Quran 8 — Al-Anfaal (The Spoils of War, 75v)",
                "Quran 9 — At-Tawba (The Repentance, 129v)",
                "Quran 10 — Yunus (Jonah, 109v)",
            ]),
            ("Juz 11–13: Hud through Ar-Rad", [
                "Quran 11 — Hud (Hud, 123v)",
                "Quran 12 — Yusuf (Joseph, 111v)",
                "Quran 13 — Ar-Rad (The Thunder, 43v)",
                "Quran 14 — Ibrahim (Abraham, 52v)",
                "Quran 15 — Al-Hijr (The Rocky Tract, 99v)",
            ]),
            ("Juz 14–16: An-Nahl through Taa-Haa", [
                "Quran 16 — An-Nahl (The Bee, 128v)",
                "Quran 17 — Al-Israa (The Night Journey, 111v)",
                "Quran 18 — Al-Kahf (The Cave, 110v)",
                "Quran 19 — Maryam (Mary, 98v)",
                "Quran 20 — Taa-Haa (Ta-Ha, 135v)",
            ]),
            ("Juz 17–20: Al-Anbiyaa through An-Naml", [
                "Quran 21 — Al-Anbiyaa (The Prophets, 112v)",
                "Quran 22 — Al-Hajj (The Pilgrimage, 78v)",
                "Quran 23 — Al-Muminoon (The Believers, 118v)",
                "Quran 24 — An-Noor (The Light, 64v)",
                "Quran 25 — Al-Furqaan (The Criterion, 77v)",
                "Quran 26 — Ash-Shuaraa (The Poets, 227v)",
                "Quran 27 — An-Naml (The Ant, 93v)",
            ]),
            ("Juz 20–23: Al-Qasas through Al-Ahzaab", [
                "Quran 28 — Al-Qasas (The Stories, 88v)",
                "Quran 29 — Al-Ankaboot (The Spider, 69v)",
                "Quran 30 — Ar-Room (The Romans, 60v)",
                "Quran 31 — Luqman (Luqman, 34v)",
                "Quran 32 — As-Sajda (The Prostration, 30v)",
                "Quran 33 — Al-Ahzaab (The Clans, 73v)",
            ]),
            ("Juz 22–26: Saba through Az-Zumar", [
                "Quran 34 — Saba (Sheba, 54v)",
                "Quran 35 — Faatir (The Originator, 45v)",
                "Quran 36 — Yaseen (Ya-Seen, 83v)",
                "Quran 37 — As-Saaffaat (Those Ranged in Ranks, 182v)",
                "Quran 38 — Saad (The Letter Sad, 88v)",
                "Quran 39 — Az-Zumar (The Groups, 75v)",
            ]),
            ("Juz 24–28: Ghafir through Al-Fath", [
                "Quran 40 — Ghafir (The Forgiver, 85v)",
                "Quran 41 — Fussilat (Explained in Detail, 54v)",
                "Quran 42 — Ash-Shura (The Consultation, 53v)",
                "Quran 43 — Az-Zukhruf (The Gold Adornments, 89v)",
                "Quran 44 — Ad-Dukhaan (The Smoke, 59v)",
                "Quran 45 — Al-Jaathiya (The Kneeling, 37v)",
                "Quran 46 — Al-Ahqaf (The Wind-Curved Sandhills, 35v)",
                "Quran 47 — Muhammad (Muhammad, 38v)",
                "Quran 48 — Al-Fath (The Victory, 29v)",
            ]),
            ("Juz 26–29: Al-Hujuraat through Al-Mulk", [
                "Quran 49 — Al-Hujuraat (The Rooms, 18v)",
                "Quran 50 — Qaaf (The Letter Qaf, 45v)",
                "Quran 51 — Adh-Dhaariyat (The Winnowing Winds, 60v)",
                "Quran 52 — At-Toor (The Mount, 49v)",
                "Quran 53 — An-Najm (The Star, 62v)",
                "Quran 54 — Al-Qamar (The Moon, 55v)",
                "Quran 55 — Ar-Rahmaan (The Beneficent, 78v)",
                "Quran 56 — Al-Waaqia (The Inevitable, 96v)",
                "Quran 57 — Al-Hadid (The Iron, 29v)",
                "Quran 58 — Al-Mujaadila (The Pleading Woman, 22v)",
                "Quran 59 — Al-Hashr (The Exile, 24v)",
                "Quran 60 — Al-Mumtahana (She That is Examined, 13v)",
                "Quran 61 — As-Saff (The Ranks, 14v)",
                "Quran 62 — Al-Jumu'a (The Congregation, 11v)",
                "Quran 63 — Al-Munafiqoon (The Hypocrites, 11v)",
                "Quran 64 — At-Taghaabun (The Mutual Disillusion, 18v)",
                "Quran 65 — At-Talaaq (The Divorce, 12v)",
                "Quran 66 — At-Tahrim (The Prohibition, 12v)",
                "Quran 67 — Al-Mulk (The Sovereignty, 30v)",
            ]),
            ("Juz 29–30: Al-Qalam through An-Naas", [
                "Quran 68 — Al-Qalam (The Pen, 52v)",
                "Quran 69 — Al-Haaqqa (The Reality, 52v)",
                "Quran 70 — Al-Maarij (The Ascending Stairways, 44v)",
                "Quran 71 — Nooh (Noah, 28v)",
                "Quran 72 — Al-Jinn (The Jinn, 28v)",
                "Quran 73 — Al-Muzzammil (The Enshrouded One, 20v)",
                "Quran 74 — Al-Muddaththir (The Cloaked One, 56v)",
                "Quran 75 — Al-Qiyaama (The Resurrection, 40v)",
                "Quran 76 — Al-Insaan (The Man, 31v)",
                "Quran 77 — Al-Mursalaat (The Emissaries, 50v)",
                "Quran 78 — An-Naba (The Tidings, 40v)",
                "Quran 79 — An-Naaziat (Those who Drag Forth, 46v)",
                "Quran 80 — Abasa (He Frowned, 42v)",
                "Quran 81 — At-Takwir (The Overthrowing, 29v)",
                "Quran 82 — Al-Infitar (The Cleaving, 19v)",
                "Quran 83 — Al-Mutaffifin (The Defrauding, 36v)",
                "Quran 84 — Al-Inshiqaaq (The Splitting Open, 25v)",
                "Quran 85 — Al-Burooj (The Mansions of the Stars, 22v)",
                "Quran 86 — At-Taariq (The Morning Star, 17v)",
                "Quran 87 — Al-Ala (The Most High, 19v)",
                "Quran 88 — Al-Ghaashiya (The Overwhelming, 26v)",
                "Quran 89 — Al-Fajr (The Dawn, 30v)",
                "Quran 90 — Al-Balad (The City, 20v)",
                "Quran 91 — Ash-Shams (The Sun, 15v)",
                "Quran 92 — Al-Layl (The Night, 21v)",
                "Quran 93 — Ad-Duhaa (The Morning Hours, 11v)",
                "Quran 94 — Ash-Sharh (The Relief, 8v)",
                "Quran 95 — At-Tin (The Fig, 8v)",
                "Quran 96 — Al-Alaq (The Clot, 19v)",
                "Quran 97 — Al-Qadr (The Power, 5v)",
                "Quran 98 — Al-Bayyina (The Clear Proof, 8v)",
                "Quran 99 — Az-Zalzala (The Earthquake, 8v)",
                "Quran 100 — Al-Aadiyaat (The Courser, 11v)",
                "Quran 101 — Al-Qaaria (The Calamity, 11v)",
                "Quran 102 — At-Takaathur (The Rivalry, 8v)",
                "Quran 103 — Al-Asr (The Declining Day, 3v)",
                "Quran 104 — Al-Humaza (The Traducer, 9v)",
                "Quran 105 — Al-Fil (The Elephant, 5v)",
                "Quran 106 — Quraysh (Quraysh, 4v)",
                "Quran 107 — Al-Maaun (The Small Kindnesses, 7v)",
                "Quran 108 — Al-Kawthar (The Abundance, 3v)",
                "Quran 109 — Al-Kaafiroon (The Disbelievers, 6v)",
                "Quran 110 — An-Nasr (The Divine Support, 3v)",
                "Quran 111 — Al-Masad (The Palm Fibre, 5v)",
                "Quran 112 — Al-Ikhlaas (The Sincerity, 4v)",
                "Quran 113 — Al-Falaq (The Daybreak, 5v)",
                "Quran 114 — An-Naas (Mankind, 6v)",
            ]),
        ]),
        ("Hadith", [
            ("The Six Books (Kutub al-Sittah)", [
                "Sahih al-Bukhari",
                "Sahih Muslim",
                "Sunan Abu Dawud",
                "Jami at-Tirmidhi",
                "Sunan an-Nasa'i",
                "Sunan Ibn Majah",
            ]),
            ("Other Collections", [
                "Muwatta Malik",
                "Forty Hadith of Nawawi",
                "Forty Hadith of Dehlawi",
            ]),
        ]),
    ]),
    ("🏛️ Classical", [
        ("Epic Poetry", [
            ("Homer", ["Iliad", "Odyssey"]),
            ("Virgil", ["Aeneid"]),
        ]),
        ("Theogonies & Hymns", [
            ("Hesiod", ["Theogony"]),
            ("Homeric", ["Homeric Hymns"]),
            ("Orphic", ["Orphic Hymns"]),
            ("Pythagorean", ["Golden Verses of Pythagoras"]),
        ]),
        ("Platonic & Neoplatonic", [
            ("Orphic", ["Orphic Hymns"]),
            ("Pythagorean", [
                "Golden Verses of Pythagoras",
                "Golden Sentences of Democrates",
                "Pythagorean Sentences of Demophilus",
                "Similitudes of Demophilus",
                "Pythagorean Sentences from Stobaeus",
                "Select Sentences of Sextus the Pythagorean",
                "Pythagorean Sentences from Iamblichus",
                "Symbols of Pythagoras",
            ]),
            ("Plato", [
                "Euthyphro", "Apology", "Crito", "Phaedo", "Cratylus",
                "Theaetetus", "Sophist", "Statesman", "Parmenides", "Philebus",
                "Symposium", "Phaedrus", "Alcibiades I", "Alcibiades II",
                "Hipparchus", "Rival Lovers", "Theages", "Charmides", "Laches",
                "Lysis", "Euthydemus", "Protagoras", "Gorgias", "Meno",
                "Greater Hippias", "Lesser Hippias", "Ion", "Menexenus",
                "Cleitophon", "Republic", "Timaeus", "Critias", "Minos",
                "Laws", "Epinomis", "Letters",
                "Axiochus", "On Justice", "On Virtue", "Demodocus",
                "Sisyphus", "Eryxias", "Definitions",
            ]),
            ("Philo of Alexandria", [
                "On the Creation",
                "Allegorical Interpretation I",
                "Allegorical Interpretation II",
                "Allegorical Interpretation III",
                "On the Cherubim",
                "On the Birth of Abel",
                "Worse Attacks the Better",
                "On the Posterity of Cain",
                "On the Giants",
                "On the Unchangeableness of God",
                "On Husbandry",
                "On Noah's Work as a Planter",
                "On Drunkenness",
                "On Sobriety",
                "On the Confusion of Tongues",
                "On the Migration of Abraham",
                "Who is the Heir of Divine Things",
                "On Mating",
                "On Flight and Finding",
                "On the Change of Names",
                "On Abraham",
                "On Joseph",
                "On the Life of Moses I",
                "On the Life of Moses II",
                "The Decalogue",
                "The Special Laws I",
                "The Special Laws II",
                "The Special Laws III",
                "The Special Laws IV",
                "On the Virtues",
                "On Rewards and Punishments",
                "Every Good Man is Free",
                "On the Contemplative Life",
                "On the Eternity of the World",
                "Flaccus",
                "On the Embassy to Gaius",
                "Questions on Genesis I",
                "Questions on Genesis II",
                "Questions on Genesis III",
            ]),
            ("Plotinus", ["Enneads"]),
            ("Porphyry", [
                "Life of Plotinus",
                "Life of Pythagoras",
                "On Abstinence",
                "On the Cave of the Nymphs",
                "Auxiliaries to the Intelligibles",
                "Letter to Marcella",
            ]),
            ("Iamblichus", [
                "On the Mysteries",
                "Life of Pythagoras",
            ]),
            ("Julian", [
                "Hymn to King Helios",
                "Hymn to the Mother of Gods",
                "Against the Galilaeans",
                "The Caesars",
            ]),
            ("Sallustius", ["On the Gods and the World"]),
            ("Proclus", [
                "Hymns of Proclus",
                "Theology of Plato",
                "Elements of Theology",
            ]),
            ("Hierocles", ["Commentary on the Golden Verses"]),
            ("Marinus", ["Life of Proclus"]),
            ("Dionysius the Areopagite", [
                "Divine Names",
                "Mystical Theology",
                "On the Heavenly Hierarchy",
                "On the Ecclesiastical Hierarchy",
            ]),
        ]),
        ("Aristotelian", [
            ("Ethics & Politics", [
                "Nicomachean Ethics",
                "Eudemian Ethics",
                "Politics",
                "Economics",
                "Athenian Constitution",
            ]),
            ("Logic (Organon)", [
                "Categories",
                "On Interpretation",
                "Prior Analytics",
                "Posterior Analytics",
                "Topics",
                "On Sophistical Refutations",
            ]),
            ("Natural Philosophy", [
                "Physics",
                "On the Heavens",
                "On Generation and Corruption",
                "Meteorology",
                "On the Soul",
                "On Memory and Reminiscence",
                "On Dreams",
                "On Sleep and Sleeplessness",
                "On Prophesying by Dreams",
                "On Sense and the Sensible",
                "On Longevity and Shortness of Life",
                "On Youth, Old Age, Life and Death",
            ]),
            ("Biology", [
                "History of Animals",
                "On the Parts of Animals",
                "On the Motion of Animals",
                "On the Gait of Animals",
                "On the Generation of Animals",
            ]),
            ("Rhetoric & Poetics", [
                "Rhetoric",
                "Poetics",
                "Metaphysics",
            ]),
        ]),
        ("Hermetic", [
            "Corpus Hermeticum",
            "Asclepius",
        ]),
        ("Oracular", [
            "Delphic Maxims",
            "Oracular Statements",
            "Chaldaean Oracles",
        ]),
    ]),
    ("📯 LDS", [
        ("Book of Mormon", [
            "1 Nephi","2 Nephi","Jacob","Enos","Jarom","Omni",
            "Words of Mormon","Mosiah","Alma","Helaman","3 Nephi","4 Nephi",
            "Mormon","Ether","Moroni",
        ]),
        ("Doctrine & Covenants", [
            "Doctrine and Covenants",
        ]),
        ("Pearl of Great Price", [
            "Moses","Abraham","Joseph Smith—Matthew","Joseph Smith—History",
            "Articles of Faith",
        ]),
    ]),
    ("🌍 Bahá'í", [
        "Kitab-i-Aqdas",
        "The Hidden Words (Arabic)",
        "The Hidden Words (Persian)",
        "Gleanings from the Writings of Baha'u'llah",
        "Prayers and Meditations",
        "Some Answered Questions",
        "Kitab-i-Iqan",
        "Epistle to the Son of the Wolf",
    ]),
    ("🏺 Dead Sea Scrolls", [
        "Hodayot",
        "Damascus Document",
        "Community Rule",
        "War Scroll",
        "Pesher Habakkuk",
        "Rule of the Congregation",
        "Rule of Blessings",
    ]),
    ("🔥 Zoroastrian", [
        "Gathas",
    ]),
    ("🧿 Gnostic", [
        ("Mandaean", [
            "Ginza Rba",
            "Book of John",
        ]),
        ("The Nag Hammadi Library (trans. Samuel Zinner)", [
            "The Prayer of Paul, the Apostle", "The Secret Book of James",
            "Treatise on the Resurrection", "The Tripartite Tractate",
            "The Substance of the Archons", "On the Origin of the World",
            "The Exegesis on the Soul", "The Book of Thomas the Contender",
            "The Sacred Book of the Great Unseen Spirit", "Eugnostos the Blessed",
            "The Sophia of Jesus Christ", "The Dialogue of the Savior",
            "The Apocalypse of Paul", "The Second Apocalypse of James",
            "The Apocalypse of Adam", "The Acts of Peter and the Twelve Apostles",
            "The Thunder, Perfect Mind", "The Authentic Logos",
            "The Idea of Our Great Power", "The Discourse on the Eighth and Ninth",
            "The Prayer of Thanksgiving", "Excerpt from the Perfect Discourse",
            "The Paraphrase of Shem", "The Second Discourse of the Great Seth",
            "The Apocalypse of Peter", "The Teachings of Silvanus",
            "The Three Steles of Seth", "Zostrianos", "The Letter of Peter to Philip",
            "Melchizedek", "The Thought of Norea", "The Testimony of Truth",
            "Marsanes", "The Interpretation of Knowledge",
            "A Valentinian Exposition and Liturgical Readings",
            "Allogenes (The Stranger)", "Hypsiphrone", "The Sentences of Sextus",
            "Trimorphic Protennoia (Three Forms of Primal Thought)",
            "Corpus Hermeticum XIII, On Rebirth", "The Act of Peter",
        ]),
        ("Manichaean (trans. C.R.C. Allberry, 1938)", [
            "Manichaean Psalms to Jesus",
            "Manichaean Bema Psalms",
            "Manichaean Psalms of Thomas",
            "Manichaean Psalms (Separate)",
        ]),
    ]),
    ("🌲 Norse", [
        ("Poetic Edda", [
            "Voluspo", "Hovamol", "Vafthruthnismol", "Grimnismol", "Skirnismol",
            "Harbarthsljoth", "Hymiskvitha", "Lokasenna", "Thrymskvitha", "Alvissmol",
            "Baldrs Draumar", "Rigsthula", "Hyndluljoth", "Svipdagsmol",
            "Völundarkvitha", "Helgakvitha Hjorvarthssonar",
            "Helgakvitha Hundingsbana I", "Helgakvitha Hundingsbana II",
            "Fra Dautha Sinfjotla", "Gripisspo", "Reginsmol", "Fafnismol",
            "Sigrdrifumol", "Brot af Sigurtharkvithu", "Guthrunarkvitha I",
            "Sigurtharkvitha en Skamma", "Helreith Brynhildar", "Drap Niflunga",
            "Guthrunarkvitha II", "Guthrunarkvitha III", "Oddrunargratr",
            "Atlakvitha en Gronlenzka", "Atlamol en Gronlenzku",
            "Guthrunarhvot", "Hamthesmol",
        ]),
    ]),
    ("🌙 Ancient Near East", [
        ("Mesopotamian", [
            ("The Epic of Gilgamesh", [
                "Gilgamesh 1 — The Tyranny of Gilgamesh (6 sec.)",
                "Gilgamesh 2 — The Meeting of Gilgamesh and Enkidu (5 sec.)",
                "Gilgamesh 3 — Expedition to the Forest of Cedars (6 sec.)",
                "Gilgamesh 4 — Arrival at the Gate of the Forest (3 sec.)",
                "Gilgamesh 5 — The Fight with Humbaba (4 sec.)",
                "Gilgamesh 6 — The Goddess Ishtar (1 sec.)",
                "Gilgamesh 7 — The Death of Enkidu (2 sec.)",
                "Gilgamesh 8 — The Mourning of Gilgamesh (1 sec.)",
                "Gilgamesh 9 — Gilgamesh Seeks Eternal Life (2 sec.)",
                "Gilgamesh 10 — How Gilgamesh Reached Uta-Napishtim (5 sec.)",
                "Gilgamesh 11 — The Flood (1 sec.)",
                "Gilgamesh 12 — Gilgamesh Enquires of the Dead (1 sec.)",
            ]),
        ]),
        ("Canaanite", [
            ("The Baal Cycle", [
                "Baal 1 — Baal and Yamm (8 sections)",
                "Baal 2 — The Palace of Baal (10 sections)",
                "Baal 3 — Baal and Mot (8 sections)",
            ]),
        ]),
        ("Egyptian", [
            "The Great Hymn to the Aten",
            "Book of the Dead",
            "The Leiden Hymns",
            "The Instruction of Amenemope",
            "The Book of Two Ways",
        ]),
        ("Aramaic / Syriac", [
            "The Story of Ahikar",
        ]),
        ("Pre-Islamic Arabic", [
            ("The Mu'allaqat — Seven Suspended Odes", [
                "Muallaqat 1 — Imru' al-Qais (60 stanzas)",
                "Muallaqat 2 — Tarafa ibn al-'Abd (33 stanzas)",
                "Muallaqat 3 — Zuhayr ibn Abi Sulma (34 stanzas)",
                "Muallaqat 4 — Labid ibn Rabi'ah (32 stanzas)",
                "Muallaqat 5 — Antara ibn Shaddad (36 stanzas)",
                "Muallaqat 6 — Amr ibn Kulthum (29 stanzas)",
                "Muallaqat 7 — Al-Harith ibn Hilliza (24 stanzas)",
            ]),
        ]),
    ]),
    ("☸️ Dharmic", [
        ("Vedas", [
            "Rig Veda",
            "Yajur Veda",
            "Sama Veda",
            "Atharva Veda",
        ]),
    ]),
    ("⛪ Patristics & Church History", [
        ("Apostolic Fathers", [
            "1 Clement","2 Clement",
            "Ignatius to the Ephesians","Ignatius to the Magnesians",
            "Ignatius to the Trallians","Ignatius to the Romans",
            "Ignatius to the Philadelphians","Ignatius to the Smyrnaeans",
            "Ignatius to Polycarp",
            "Polycarp to the Philippians","Martyrdom of Polycarp",
            "Epistle of Barnabas","Didache","Shepherd of Hermas",
        ]),
        ("Dionysius the Areopagite", [
            "Divine Names","Mystical Theology",
            "On the Heavenly Hierarchy","On the Ecclesiastical Hierarchy",
            "Letters of Dionysius","Liturgy of St. Dionysius",
        ]),
        ("Ante-Nicene Fathers", [
            ("Justin Martyr", [
                "First Apology","Second Apology","Dialogue with Trypho",
                "Hortatory Address to the Greeks","Discourse to the Greeks",
            ]),
            ("Irenaeus of Lyons", [
                "Adversus haereses",
                "Fragments from the Lost Writings of Irenaeus",
            ]),
            ("Clement of Alexandria", [
                "Exhortation to the Heathen","The Instructor","Stromateis",
                "Who is the Rich Man That Shall Be Saved?",
            ]),
            ("Tertullian", [
                "Apology","On the Prescription of Heretics","Against Marcion",
                "On the Soul","On the Resurrection of the Flesh","Against Praxeas",
                "On Baptism","On Repentance","On Patience","On Prayer","On Idolatry",
                "Scorpiace","Against Hermogenes","On Modesty","On the Veiling of Virgins",
                "De Spectaculis (The Shows)","An Answer to the Jews",
                "Against the Valentinians","On Exhortation to Chastity","On Monogamy",
            ]),
            ("Origen", [
                "De Principiis","Against Celsus","Philocalia",
                "Commentary on the Gospel of John",
                "Commentary on the Gospel of Matthew",
            ]),
            ("Hippolytus", [
                "The Refutation of All Heresies","The Antichrist",
                "Against the Heresy of Noetus",
            ]),
            ("Athenagoras", [
                "A Plea for the Christians","The Resurrection of the Dead",
            ]),
            ("Tatian", ["Address to the Greeks","The Diatessaron"]),
            ("Theophilus", ["Theophilus to Autolycus"]),
            ("Minucius Felix", ["Octavius"]),
            ("Lactantius", [
                "The Divine Institutes","The Epitome of the Divine Institutes",
                "On the Anger of God","On the Workmanship of God",
                "Of the Manner In Which the Persecutors Died",
            ]),
            ("Cyprian of Carthage", [
                "The Treatises of Cyprian","The Life and Passion of Cyprian",
            ]),
            ("Novatian", ["Treatise Concerning the Trinity","On the Jewish Meats"]),
            ("Methodius", [
                "The Banquet of the Ten Virgins","Concerning Free Will",
            ]),
            ("Dionysius the Great", [
                "Epistles and Epistolary Fragments",
                "Exegetical Fragments","Miscellaneous Fragments",
            ]),
            ("Arnobius", ["Against the Heathen"]),
            ("Aphrahat", ["Demonstrations"]),
            ("Clement of Rome", [
                "First Epistle","Second Epistle",
                "Recognitions","Clementine Homilies",
            ]),
            ("Julius Africanus", ["Extant Writings"]),
            ("Gregory Thaumaturgus", [
                "The Oration and Panegyric Addressed to Origen",
                "Canonical Epistle","Twelve Topics on the Faith",
            ]),
        ]),
        ("Nicene Fathers", [
            ("Eusebius of Caesarea", [
                "Church History","Life of Constantine",
                "Oration in Praise of Constantine",
            ]),
            ("Athanasius", [
                "On the Incarnation","Discourses Against the Arians",
                "On the Decrees of Nicaea","Apologia Contra Arianos",
                "Life of Antony","Historia Arianorum","De Sententia Dionysii",
                "Letters of Athanasius",
            ]),
            ("Hilary of Poitiers", [
                "On the Trinity","On the Councils, or the Faith of the Easterns",
            ]),
            ("Cyril of Jerusalem", ["Catechetical Lectures"]),
            ("Basil the Great", [
                "Hexaemeron","On the Holy Spirit",
                "Address to Young Men","Letters of Basil",
            ]),
            ("Gregory Nazianzen", [
                "Orations","Orations Against Julian","Letters of Gregory Nazianzen",
            ]),
            ("Gregory of Nyssa", [
                "On the Soul and the Resurrection","The Great Catechism",
                "On the Making of Man","Against Eunomius",
                "On Virginity","Life of Macrina","Letters of Gregory of Nyssa",
            ]),
            ("Ambrose", [
                "On the Christian Faith (De fide)","On the Holy Spirit",
                "On the Mysteries","On the Duties of the Clergy",
                "Concerning Virgins","On Repentance","Letters",
            ]),
            ("John Chrysostom", [
                "On the Priesthood","Homilies on Matthew","Homilies on John",
                "Homilies on Acts","Homilies on Romans",
                "Homilies on 1 Corinthians","Homilies on 2 Corinthians",
                "Homilies on Ephesians","Homilies on Philippians",
                "Homilies on Colossians","Homilies on Hebrews",
                "Homilies on the Statues","Homilies on Titus","Homilies on Philemon",
                "Commentary on Galatians",
            ]),
            ("Ephrem the Syrian", [
                "Discourses to Hypatius","Against Marcion","Against Mani",
                "On Virginity","Nisibene Hymns",
            ]),
        ]),
        ("Post-Nicene Fathers", [
            ("Augustine of Hippo", [
                "Confessions","City of God","On the Trinity","Enchiridion",
                "On Christian Doctrine","On Nature and Grace",
                "On the Spirit and the Letter",
                "On the Morals of the Catholic Church","Letters of Augustine",
                "Tractates on the Gospel of John",
                "The Enarrations, or Expositions, on the Psalms",
                "Reply to Faustus the Manichaean","On Grace and Free Will",
                "On Baptism, Against the Donatists","The Harmony of the Gospels",
            ]),
            ("Jerome", [
                "Letters","Lives of Illustrious Men","Commentary on Daniel",
                "Against Jovinianus","Against Vigilantius","Against the Pelagians",
                "The Life of Malchus, the Captive Monk","The Life of S. Hilarion",
            ]),
            ("John Cassian", [
                "Institutes","Conferences",
                "On the Incarnation of the Lord (Against Nestorius)",
            ]),
            ("Cyril of Alexandria", [
                "Against Nestorius","Commentary on John","Commentary on Luke",
                "That Christ is One","Scholia on the Incarnation","Against Julian",
            ]),
            ("Leo the Great", ["Sermons","Letters of Leo"]),
            ("Theodoret", [
                "Ecclesiastical History","Letters",
                'Dialogues ("Eranistes" or "Polymorphus")',
            ]),
            ("Socrates Scholasticus", ["Ecclesiastical History"]),
            ("Sozomen", ["Ecclesiastical History"]),
            ("Sulpitius Severus", [
                "On the Life of St. Martin","Dialogues","Sacred History",
            ]),
            ("John of Damascus", [
                "Exposition of the Orthodox Faith","Philosophical Chapters",
            ]),
            ("Gregory the Great", [
                "Dialogues","Pastoral Rule","Letters of Gregory the Great",
            ]),
            ("Vincent of Lérins", [
                "Commonitory for the Antiquity and Universality of the Catholic Faith",
            ]),
        ]),
        ("Church History", [
            ("Josephus", [
                "Jewish Antiquities","Jewish War","Against Apion","Life",
            ]),
            ("Eusebius of Caesarea", [
                "Church History","Life of Constantine","Oration in Praise of Constantine",
                "Demonstratio Evangelica","Praeparatio Evangelica","Theophania",
            ]),
            ("Bede the Venerable", [
                "Ecclesiastical History of the English People",
            ]),
            ("Jacobus de Voragine", [
                "The Golden Legend",
            ]),
        ]),
        ("Pearse Collection", [
            ("Hermias", ["Derision of Gentile Philosophers"]),
            ("Eunomius of Cyzicus", ["The First Apology"]),
            ("Philostorgius", ["Ecclesiastical History (Epitome)"]),
            ("Pacian of Barcelona", [
                "Letters to Sympronian","Paraenesis on Penance","Discourse on Baptism",
            ]),
            ("Macarius Magnes", ["Apocriticus"]),
            ("Asterius of Amasea", ["Sermons"]),
            ("Epiphanius of Salamis", ["On Weights and Measures"]),
            ("Pseudo-Hegesippus", ["On the Ruin of Jerusalem"]),
            ("Optatus of Milevis", ["Against the Donatists"]),
            ("Possidius", ["Life of St. Augustine"]),
            ("Theodore of Mopsuestia", [
                "Commentary on the Nicene Creed",
                "Commentary on the Lord's Prayer and Sacraments",
            ]),
            ("Nestorius", ["The Bazaar of Heracleides"]),
            ("Palladius", [
                "The Lausiac History",
                "Dialogue on the Life of St. John Chrysostom",
            ]),
            ("Salvian", ["On the Government of God"]),
            ("Sidonius Apollinaris", ["Letters"]),
            ("Philoxenus of Hierapolis", ["13 Ascetic Discourses"]),
            ("Evagrius Scholasticus", ["Ecclesiastical History"]),
            ("Dioscorus of Alexandria", ["Letter to Shenouda"]),
            ("Gildas the Wise", ["The Ruin of Britain","Penitential"]),
            ("Leontius of Byzantium", ["Against the Frauds of the Apollinarists"]),
            ("Severus of Antioch", ["Letters"]),
            ("John of Ephesus", ["Ecclesiastical History (Third Part)"]),
            ("Cosmas Indicopleustes", ["The Christian Topography"]),
            ("Agapius of Hierapolis", ["Universal History"]),
            ("Photius of Constantinople", ["Bibliotheca (Codices 1-165)"]),
            ("Timothy I", ["Apology for Christianity to Caliph Al-Mahdi"]),
            ("Isidore of Seville", ["Chronicon"]),
            ("John bar Penkaye", ["Summary History of the World (Book 15: Rise of Islam)"]),
        ]),
    ]),
]

# Top-level browsing groups two supergroups on top of BOOKS_TREE without
# reordering it: Abrahamic-descended scripture/commentary traditions (still
# living faiths with a canon + commentary literature) vs. mythological and
# classical-philosophical corpora. Reuses the same nested lists/tuples from
# BOOKS_TREE by reference, so drilling further down is unaffected.
_SUPERGROUP_ORDER = [
    ("📖 Abrahamic Scripture & Commentary", [
        "📖 The Bible", "👼 Apocrypha / Pseudepigrapha", "✡️ Rabbinic & Kabbalistic",
        "☪️ Islamic", "🧿 Gnostic", "📯 LDS", "🌍 Bahá'í", "🏺 Dead Sea Scrolls",
        "⛪ Patristics & Church History",
    ]),
    ("🌐 Mythology & Classical Traditions", [
        "🏛️ Classical", "🌲 Norse", "🌙 Ancient Near East", "☸️ Dharmic",
        "🔥 Zoroastrian",
    ]),
]
_books_tree_by_name = {name: contents for name, contents in BOOKS_TREE}
ROOT_BOOKS_TREE = [
    (group_label, [(name, _books_tree_by_name[name]) for name in names])
    for group_label, names in _SUPERGROUP_ORDER
]


def _count_leaves(node) -> int:
    count = 0
    for item in node:
        if isinstance(item, tuple):
            count += _count_leaves(item[1])
        else:
            count += 1
    return count


# Stephanus page ranges derived from plato.json
_PLATO_STEPHANUS_RANGES: dict[str, tuple[str, str]] = {
    "Euthyphro": ("2a", "16a"),
    "Apology": ("17a", "42a"),
    "Crito": ("43a", "54e"),
    "Phaedo": ("57a", "118a"),
    "Cratylus": ("383a", "440e"),
    "Theaetetus": ("142a", "210d"),
    "Sophist": ("216a", "268d"),
    "Statesman": ("257a", "311c"),
    "Parmenides": ("126a", "166b"),
    "Philebus": ("11a", "67b"),
    "Symposium": ("172a", "223d"),
    "Phaedrus": ("227a", "279c"),
    "Alcibiades I": ("103a", "135e"),
    "Alcibiades II": ("138a", "151c"),
    "Hipparchus": ("225a", "232c"),
    "Rival Lovers": ("132a", "139a"),
    "Theages": ("121a", "131a"),
    "Charmides": ("153a", "176d"),
    "Laches": ("178a", "201c"),
    "Lysis": ("203a", "223b"),
    "Euthydemus": ("271a", "307c"),
    "Protagoras": ("309a", "362a"),
    "Gorgias": ("447a", "527e"),
    "Meno": ("70a", "100c"),
    "Greater Hippias": ("281a", "304e"),
    "Lesser Hippias": ("363a", "376c"),
    "Ion": ("530a", "542b"),
    "Menexenus": ("234a", "249e"),
    "Cleitophon": ("406a", "410e"),
    "Republic": ("327a", "621d"),
    "Timaeus": ("17a", "92c"),
    "Critias": ("106a", "121c"),
    "Minos": ("313a", "321d"),
    "Laws": ("624a", "969d"),
    "Epinomis": ("973a", "992e"),
    "Letters": ("309b", "363d"),
}

# ── Babylonian Talmud daf ranges (Vilna edition, starts at 2a) ───────────────
_BAVLI_RANGES: dict[str, tuple[str, str]] = {
    "Berakhot": ("2a", "64b"), "Shabbat": ("2a", "157b"), "Eruvin": ("2a", "105b"),
    "Pesachim": ("2a", "121b"), "Shekalim": ("2a", "22b"), "Yoma": ("2a", "88b"),
    "Sukkah": ("2a", "56b"), "Beitzah": ("2a", "40b"), "Rosh Hashanah": ("2a", "35b"),
    "Taanit": ("2a", "31b"), "Megillah": ("2a", "32b"), "Moed Katan": ("2a", "29b"),
    "Chagigah": ("2a", "27b"), "Yevamot": ("2a", "122b"), "Ketubot": ("2a", "112b"),
    "Nedarim": ("2a", "91b"), "Nazir": ("2a", "66b"), "Sotah": ("2a", "49b"),
    "Gittin": ("2a", "90b"), "Kiddushin": ("2a", "82b"), "Bava Kamma": ("2a", "119b"),
    "Bava Metzia": ("2a", "119b"), "Bava Batra": ("2a", "176b"), "Sanhedrin": ("2a", "113b"),
    "Makkot": ("2a", "24b"), "Shevuot": ("2a", "49b"), "Avodah Zarah": ("2a", "76b"),
    "Horayot": ("2a", "14b"), "Zevachim": ("2a", "120b"), "Menachot": ("2a", "110b"),
    "Chullin": ("2a", "142b"), "Bechorot": ("2a", "61b"), "Arachin": ("2a", "34b"),
    "Temurah": ("2a", "34b"), "Keritot": ("2a", "28b"), "Meilah": ("2a", "22b"),
    "Tamid": ("2a", "8b"), "Niddah": ("2a", "73b"),
}

# ── Mishnah chapter and mishnah counts ────────────────────────────────────────
_MISHNAH_RANGES: dict[str, tuple[int, int]] = {
    # (chapters, total mishnayot)
    "Berakhot": (9, 57), "Peah": (8, 69), "Demai": (7, 53), "Kilayim": (9, 77),
    "Sheviit": (10, 89), "Terumot": (11, 101), "Maasrot": (5, 40),
    "Maaser Sheni": (5, 57), "Challah": (4, 38), "Orlah": (3, 35), "Bikkurim": (4, 39),
    "Shabbat": (24, 139), "Eruvin": (10, 96), "Pesachim": (10, 89), "Shekalim": (8, 52),
    "Yoma": (8, 61), "Sukkah": (5, 53), "Beitzah": (5, 42), "Rosh Hashanah": (4, 35),
    "Taanit": (4, 34), "Megillah": (4, 33), "Moed Katan": (3, 24), "Chagigah": (3, 23),
    "Yevamot": (16, 128), "Ketubot": (13, 111), "Nedarim": (11, 90), "Nazir": (9, 60),
    "Sotah": (9, 67), "Gittin": (9, 75), "Kiddushin": (4, 47),
    "Bava Kamma": (10, 79), "Bava Metzia": (10, 101), "Bava Batra": (10, 86),
    "Sanhedrin": (11, 71), "Makkot": (3, 34), "Shevuot": (8, 62), "Eduyot": (8, 74),
    "Avodah Zarah": (5, 50), "Avot": (6, 108), "Horayot": (3, 20),
    "Zevachim": (14, 101), "Menachot": (13, 93), "Chullin": (12, 74), "Bechorot": (9, 73),
    "Arachin": (9, 50), "Temurah": (7, 35), "Keritot": (6, 43), "Meilah": (6, 38),
    "Tamid": (7, 34), "Middot": (5, 34), "Kinnim": (3, 15),
    "Keilim": (30, 254), "Ohalot": (18, 134), "Negaim": (14, 115), "Parah": (12, 96),
    "Taharot": (10, 92), "Mikvaot": (10, 71), "Niddah": (10, 79), "Machshirin": (6, 54),
    "Zavim": (5, 32), "Tevul Yom": (4, 26), "Yadayim": (4, 22), "Oktzin": (3, 28),
}

# ── Jerusalem Talmud chapter counts ──────────────────────────────────────────
_YERUSHALMI_RANGES: dict[str, int] = {
    # chapters (cite as: ch:halakhah, halakhah varies by chapter)
    "Berakhot": 9, "Peah": 8, "Demai": 7, "Kilayim": 9, "Sheviit": 10,
    "Terumot": 11, "Maaserot": 5, "Maaser Sheni": 5, "Challah": 4,
    "Orlah": 3, "Bikkurim": 4, "Shabbat": 24, "Eruvin": 10, "Pesachim": 10,
    "Shekalim": 8, "Yoma": 8, "Sukkah": 5, "Beitzah": 5, "Rosh Hashanah": 4,
    "Taanit": 4, "Megillah": 4, "Moed Katan": 3, "Chagigah": 3,
    "Yevamot": 16, "Ketubot": 13, "Nedarim": 11, "Nazir": 9, "Sotah": 9,
    "Gittin": 9, "Kiddushin": 4, "Bava Kamma": 10, "Bava Metzia": 10,
    "Bava Batra": 10, "Sanhedrin": 11, "Makkot": 3, "Shevuot": 8,
    "Avodah Zarah": 5, "Horayot": 3, "Niddah": 2,
}

# ── Zohar max segment counts per parasha ──────────────────────────────────────
_ZOHAR_SEGMENTS: dict[str, int] = {
    "Introduction": 34, "Bereshit": 200, "Noach": 150, "Lech Lecha": 120,
    "Vayera": 130, "Chayei Sarah": 80, "Toldot": 90, "Vayetze": 100,
    "Vayishlach": 90, "Vayeshev": 80, "Miketz": 80, "Vayigash": 60,
    "Vayechi": 100, "Shemot": 100, "Vaera": 80, "Bo": 80,
    "Beshalach": 80, "Yitro": 80, "Mishpatim": 100, "Terumah": 150,
    "Tetzaveh": 60, "Ki Tisa": 80, "Vayakhel": 80, "Pekudei": 80,
    "Vayikra": 60, "Tzav": 50, "Shmini": 50, "Tazria": 50,
    "Metzora": 40, "Acharei Mot": 80, "Kedoshim": 50, "Emor": 80,
    "Behar": 40, "Bechukotai": 40, "Bamidbar": 60, "Nasso": 80,
    "Behaalotcha": 60, "Shelach Lecha": 60, "Korach": 50, "Chukat": 50,
    "Balak": 80, "Pinchas": 120, "Matot": 40, "Vaetchanan": 60,
    "Eikev": 50, "Re'eh": 50, "Shoftim": 50, "Ki Teitzei": 60,
    "Ki Tavo": 50, "Vayeilech": 30, "Haazinu": 50, "Vezot Haberachah": 30,
}

# ── Midrash Rabbah section counts ─────────────────────────────────────────────
_MIDRASH_SECTIONS: dict[str, int] = {
    "Bereshit Rabbah": 100, "Shemot Rabbah": 52, "Vayikra Rabbah": 37,
    "Bamidbar Rabbah": 23, "Devarim Rabbah": 11, "Ruth Rabbah": 8,
    "Esther Rabbah": 10, "Eichah Rabbah": 5, "Shir HaShirim Rabbah": 8,
    "Kohelet Rabbah": 12, "Mechilta": 9, "Sifra": 15,
    "Sifre Bamidbar": 161, "Sifre Devarim": 357,
    "Pirkei DeRabbi Eliezer": 54, "Midrash Tanchuma": 54,
}

# ── Targum book chapter counts (mirrors Bible) ─────────────────────────────────
_TARGUM_CHAPTERS: dict[str, int] = {
    "Targum Onkelos Genesis": 50, "Targum Onkelos Exodus": 40,
    "Targum Onkelos Leviticus": 27, "Targum Onkelos Numbers": 36,
    "Targum Onkelos Deuteronomy": 34,
    "Targum Pseudo-Jonathan Genesis": 50, "Targum Pseudo-Jonathan Exodus": 40,
    "Targum Neofiti Genesis": 50, "Targum Neofiti Exodus": 40,
    "Targum Jonathan Isaiah": 66, "Targum Jonathan Jeremiah": 52,
    "Targum Jonathan Ezekiel": 48, "Targum Jonathan Hosea": 14,
    "Targum Jonathan Psalms": 150, "Targum Jonathan Proverbs": 31,
    "Targum Jonathan Job": 42,
}

# ── Mishneh Torah: 84 sections with chapter counts ────────────────────────────
# Cite as: !verse Mishneh Torah, Repentance 1:1  (section, chapter:halacha)
_MISHNEH_TORAH_SECTIONS: dict[str, int] = {
    # Book 1: HaMadda
    "Mishneh Torah, Foundations of the Torah": 10,
    "Mishneh Torah, Human Dispositions": 7,
    "Mishneh Torah, Torah Study": 7,
    "Mishneh Torah, Foreign Worship and Customs of the Nations": 11,
    "Mishneh Torah, Repentance": 10,
    # Book 2: Ahavah
    "Mishneh Torah, Reading the Shema": 4,
    "Mishneh Torah, Prayer and the Priestly Blessing": 15,
    "Mishneh Torah, Tefillin, Mezuzah and the Torah Scroll": 10,
    "Mishneh Torah, Fringes": 3,
    "Mishneh Torah, Blessings": 11,
    "Mishneh Torah, Circumcision": 3,
    "Mishneh Torah, The Order of Prayer": 5,
    # Book 3: Zemanim
    "Mishneh Torah, Sabbath": 30,
    "Mishneh Torah, Eruvin": 8,
    "Mishneh Torah, Rest on the Tenth of Tishrei": 3,
    "Mishneh Torah, Rest on a Holiday": 8,
    "Mishneh Torah, Leavened and Unleavened Bread": 8,
    "Mishneh Torah, Shofar, Sukkah and Lulav": 8,
    "Mishneh Torah, Sheqel Dues": 4,
    "Mishneh Torah, Sanctification of the New Month": 19,
    "Mishneh Torah, Fasts": 5,
    "Mishneh Torah, Megillah and Hanukkah": 4,
    # Book 4: Nashim
    "Mishneh Torah, Marriage": 25,
    "Mishneh Torah, Divorce": 13,
    "Mishneh Torah, Levirate Marriage and Release": 8,
    "Mishneh Torah, Virgin Maiden": 3,
    "Mishneh Torah, Sotah": 4,
    # Book 5: Kedushah
    "Mishneh Torah, Forbidden Intercourse": 22,
    "Mishneh Torah, Forbidden Foods": 17,
    "Mishneh Torah, Slaughter": 14,
    # Book 6: Haflaah
    "Mishneh Torah, Oaths": 12,
    "Mishneh Torah, Vows": 13,
    "Mishneh Torah, Naziriteship": 10,
    "Mishneh Torah, Appraisals and Devoted Property": 8,
    # Book 7: Zeraim
    "Mishneh Torah, Diverse Species": 10,
    "Mishneh Torah, Gifts to the Poor": 10,
    "Mishneh Torah, Heave Offerings": 15,
    "Mishneh Torah, Tithes": 14,
    "Mishneh Torah, Second Tithe and Fourth Year Produce": 11,
    "Mishneh Torah, First Fruits and other Gifts to Priests Outside the Temple": 12,
    "Mishneh Torah, Sabbatical Year and the Jubilee": 13,
    # Book 8: Avodah
    "Mishneh Torah, The Chosen Temple": 8,
    "Mishneh Torah, Vessels of the Sanctuary and Those who Serve Therein": 10,
    "Mishneh Torah, Admission into the Sanctuary": 9,
    "Mishneh Torah, Things Forbidden on the Altar": 7,
    "Mishneh Torah, Sacrificial Procedure": 19,
    "Mishneh Torah, Daily Offerings and Additional Offerings": 10,
    "Mishneh Torah, Sacrifices Rendered Unfit": 19,
    "Mishneh Torah, The Yom Kippur Service": 5,
    "Mishneh Torah, Trespass": 8,
    # Book 9: Korbanot
    "Mishneh Torah, Paschal Offering": 10,
    "Mishneh Torah, Festival Offering": 3,
    "Mishneh Torah, Firstborn": 8,
    "Mishneh Torah, Offerings for Unintentional Transgressions": 15,
    "Mishneh Torah, Offerings for Those with Incomplete Atonement": 5,
    "Mishneh Torah, Substitution": 4,
    # Book 10: Taharah
    "Mishneh Torah, Corpse Impurity": 25,
    "Mishneh Torah, Red Heifer": 16,
    "Mishneh Torah, Leprosy": 16,
    "Mishneh Torah, Those who Defile Bed or Seat": 8,
    "Mishneh Torah, Other Sources of Defilement": 20,
    "Mishneh Torah, Defilement of Foods": 16,
    "Mishneh Torah, Vessels": 28,
    "Mishneh Torah, Immersion Pools": 11,
    # Book 11: Nezikin
    "Mishneh Torah, Property Damage": 14,
    "Mishneh Torah, Theft": 9,
    "Mishneh Torah, Robbery and Lost Property": 18,
    "Mishneh Torah, One Who Injures a Person or Property": 8,
    "Mishneh Torah, Murderers and the Preservation of Life": 13,
    # Book 12: Kinyan
    "Mishneh Torah, Sales": 30,
    "Mishneh Torah, Ownerless Property and Gifts": 12,
    "Mishneh Torah, Neighbors": 14,
    "Mishneh Torah, Agents and Partners": 10,
    "Mishneh Torah, Slaves": 9,
    # Book 13: Mishpatim
    "Mishneh Torah, Hiring": 13,
    "Mishneh Torah, Borrowing and Deposit": 8,
    "Mishneh Torah, Creditor and Debtor": 27,
    "Mishneh Torah, Plaintiff and Defendant": 16,
    "Mishneh Torah, Inheritance": 11,
    # Book 14: Shoftim
    "Mishneh Torah, Courts": 26,
    "Mishneh Torah, Testimony": 22,
    "Mishneh Torah, Rebels": 3,
    "Mishneh Torah, Mourning": 14,
    "Mishneh Torah, Kings and Wars": 12,
}
_MISHNEH_TORAH_BOOKS = set(_MISHNEH_TORAH_SECTIONS.keys())

# Guide for the Perplexed: 3 parts, varying chapters
_GUIDE_PERPLEXED_CHAPTERS = {
    "Guide for the Perplexed": (3, 179),  # 3 parts, 179 chapters total
}

# ── Other Kabbalah chapter counts ─────────────────────────────────────────────
_KABBALAH_CHAPTERS: dict[str, int] = {
    "Sefer Yetzirah": 6,     # 6 chapters
    "Sefer HaBahir": 1,      # 200 sections in 1 "chapter"
    "Tikkunei Zohar": 70,    # 70 tikkuns
    "Zohar Chadash": 10,     # ~10 sections
    "Tanya": 5,              # 5 parts (Part I: 53 ch., II: 12, III: 12, IV: 32, V: 9)
}

# Tanya part details for display
_TANYA_PARTS: dict[int, tuple[str, int]] = {
    1: ("Likkutei Amarim",          53),
    2: ("Shaar HaYichud VehaEmunah", 12),
    3: ("Iggeret HaTeshuvah",        12),
    4: ("Iggeret HaKodesh",          32),
    5: ("Kuntres Acharon",            9),
}

# Citation format hints per book/corpus
_CITATION_HINTS: dict[str, str] = {
    # Mishnah tractates
    "Berakhot": "!verse Berakhot 1:1  (tractate chapter:mishnah)",
    "Shabbat": "!verse Shabbat 1:1  (tractate chapter:mishnah)",
    "Avot": "!verse Avot 1:1  (tractate chapter:mishnah)",
    # Talmud — same tractate names but daf format
    # (handled via daf detection, so hint is on the Talmud section)
    # Quran
    "Quran": "!verse Quran 2:255  (surah:ayah)",
    # Zohar
    "Zohar": "!verse Zohar Bereshit 5  (parasha + segment number)",
}  # Plato works handled dynamically via _PLATO_STEPHANUS_RANGES below

# Hadith collections
_HADITH_BOOKS = {
    "Sahih al-Bukhari", "Sahih Muslim", "Sunan Abu Dawud",
    "Jami at-Tirmidhi", "Sunan an-Nasa'i", "Sunan Ibn Majah",
    "Muwatta Malik", "Forty Hadith of Nawawi", "Forty Hadith of Dehlawi",
}

# Map display name → collection key for display data
_HADITH_DISPLAY_TO_KEY: dict[str, str] = {
    "Sahih al-Bukhari":         "bukhari",
    "Sahih Muslim":             "muslim",
    "Sunan Abu Dawud":          "abudawud",
    "Jami at-Tirmidhi":         "tirmidhi",
    "Sunan an-Nasa'i":          "nasai",
    "Sunan Ibn Majah":          "ibnmajah",
    "Muwatta Malik":            "malik",
    "Forty Hadith of Nawawi":   "nawawi",
    "Forty Hadith of Dehlawi":  "dehlawi",
}

# Total hadith counts and book counts per collection
_HADITH_COUNTS: dict[str, int] = {
    "bukhari": 7563, "muslim": 7563, "abudawud": 5274,
    "tirmidhi": 3956, "nasai": 5761, "ibnmajah": 4341,
    "malik": 1852, "nawawi": 42, "dehlawi": 40,
}
_HADITH_BOOK_COUNTS: dict[str, int] = {
    "bukhari": 97, "muslim": 56, "abudawud": 43,
    "tirmidhi": 49, "nasai": 51, "ibnmajah": 37,
    "malik": 61, "nawawi": 1, "dehlawi": 1,
}

# Jerusalem Talmud tractates (chapter:halakhah citation)
_YERUSHALMI_BOOKS = {
    "Jerusalem Talmud Berakhot","Jerusalem Talmud Peah","Jerusalem Talmud Demai",
    "Jerusalem Talmud Kilayim","Jerusalem Talmud Sheviit","Jerusalem Talmud Terumot",
    "Jerusalem Talmud Maaserot","Jerusalem Talmud Maaser Sheni","Jerusalem Talmud Challah",
    "Jerusalem Talmud Orlah","Jerusalem Talmud Bikkurim","Jerusalem Talmud Shabbat",
    "Jerusalem Talmud Eruvin","Jerusalem Talmud Pesachim","Jerusalem Talmud Shekalim",
    "Jerusalem Talmud Yoma","Jerusalem Talmud Sukkah","Jerusalem Talmud Beitzah",
    "Jerusalem Talmud Rosh Hashanah","Jerusalem Talmud Taanit","Jerusalem Talmud Megillah",
    "Jerusalem Talmud Moed Katan","Jerusalem Talmud Chagigah","Jerusalem Talmud Yevamot",
    "Jerusalem Talmud Ketubot","Jerusalem Talmud Nedarim","Jerusalem Talmud Nazir",
    "Jerusalem Talmud Sotah","Jerusalem Talmud Gittin","Jerusalem Talmud Kiddushin",
    "Jerusalem Talmud Bava Kamma","Jerusalem Talmud Bava Metzia","Jerusalem Talmud Bava Batra",
    "Jerusalem Talmud Sanhedrin","Jerusalem Talmud Makkot","Jerusalem Talmud Shevuot",
    "Jerusalem Talmud Avodah Zarah","Jerusalem Talmud Horayot","Jerusalem Talmud Niddah",
}

# Tosefta books (chapter:halakhah citation)
_TOSEFTA_BOOKS = {name for name in [
    "Tosefta Berakhot","Tosefta Peah","Tosefta Demai","Tosefta Kilayim",
    "Tosefta Sheviit","Tosefta Terumot","Tosefta Maasrot","Tosefta Maaser Sheni",
    "Tosefta Challah","Tosefta Orlah","Tosefta Bikkurim","Tosefta Shabbat",
    "Tosefta Eruvin","Tosefta Pesachim","Tosefta Shekalim","Tosefta Yoma",
    "Tosefta Sukkah","Tosefta Beitzah","Tosefta Rosh Hashanah","Tosefta Taanit",
    "Tosefta Megillah","Tosefta Moed Katan","Tosefta Chagigah","Tosefta Yevamot",
    "Tosefta Ketubot","Tosefta Nedarim","Tosefta Nazir","Tosefta Sotah",
    "Tosefta Gittin","Tosefta Kiddushin","Tosefta Bava Kamma","Tosefta Bava Metzia",
    "Tosefta Bava Batra","Tosefta Sanhedrin","Tosefta Makkot","Tosefta Shevuot",
    "Tosefta Eduyot","Tosefta Avodah Zarah","Tosefta Horayot",
]}

# Targum books (book-level, cite as: Targum Onkelos Genesis 1:1)
_TARGUM_BOOKS = {
    "Targum Onkelos Genesis","Targum Onkelos Exodus","Targum Onkelos Leviticus",
    "Targum Onkelos Numbers","Targum Onkelos Deuteronomy",
    "Targum Pseudo-Jonathan Genesis","Targum Pseudo-Jonathan Exodus",
    "Targum Neofiti Genesis","Targum Neofiti Exodus",
    "Targum Jonathan Isaiah","Targum Jonathan Jeremiah","Targum Jonathan Ezekiel",
    "Targum Jonathan Hosea","Targum Jonathan Psalms","Targum Jonathan Proverbs",
    "Targum Jonathan Job",
}

# Midrash Rabbah books (section:subsection citation)
_MIDRASH_BOOKS = {
    "Bereshit Rabbah","Shemot Rabbah","Vayikra Rabbah","Bamidbar Rabbah",
    "Devarim Rabbah","Ruth Rabbah","Esther Rabbah","Eichah Rabbah",
    "Shir HaShirim Rabbah","Kohelet Rabbah","Mechilta","Sifra",
    "Sifre Bamidbar","Sifre Devarim","Pirkei DeRabbi Eliezer","Midrash Tanchuma",
}

# Zohar parashot (cited as: Zohar Bereshit 5)
_ZOHAR_BOOKS = {f"Zohar {p}" for p, _ in [
    ("Introduction", 34),("Bereshit", 200),("Noach", 150),("Lech Lecha", 120),
    ("Vayera", 130),("Chayei Sarah", 80),("Toldot", 90),("Vayetze", 100),
    ("Vayishlach", 90),("Vayeshev", 80),("Miketz", 80),("Vayigash", 60),
    ("Vayechi", 100),("Shemot", 100),("Vaera", 80),("Bo", 80),
    ("Beshalach", 80),("Yitro", 80),("Mishpatim", 100),("Terumah", 150),
    ("Tetzaveh", 60),("Ki Tisa", 80),("Vayakhel", 80),("Pekudei", 80),
    ("Vayikra", 60),("Tzav", 50),("Shmini", 50),("Tazria", 50),
    ("Metzora", 40),("Acharei Mot", 80),("Kedoshim", 50),("Emor", 80),
    ("Behar", 40),("Bechukotai", 40),("Bamidbar", 60),("Nasso", 80),
    ("Behaalotcha", 60),("Shelach Lecha", 60),("Korach", 50),("Chukat", 50),
    ("Balak", 80),("Pinchas", 120),("Matot", 40),("Vaetchanan", 60),
    ("Eikev", 50),("Re'eh", 50),("Shoftim", 50),("Ki Teitzei", 60),
    ("Ki Tavo", 50),("Vayeilech", 30),("Haazinu", 50),("Vezot Haberachah", 30),
]}

# Other Kabbalah
_OTHER_KABBALAH_BOOKS = {"Sefer Yetzirah","Sefer HaBahir","Tikkunei Zohar","Zohar Chadash","Tanya"}

# Ancient Near East single-book texts (section counts for display)
_ANE_SINGLE_BOOKS: dict[str, tuple[int, str]] = {
    "The Great Hymn to the Aten":    (13, "section"),
    "Book of the Dead":              (52, "chapter"),
    "The Leiden Hymns":              (22, "stanza"),
    "The Instruction of Amenemope":  (36, "chapter"),
    "The Book of Two Ways":          (19, "spell"),
    "The Story of Ahikar":           (5,  "section"),
}

# Talmud tractates (same names as Mishnah but daf-style citation)
_TALMUD_BOOKS = {
    "Berakhot","Shabbat","Eruvin","Pesachim","Yoma","Sukkah","Beitzah",
    "Rosh Hashanah","Taanit","Megillah","Moed Katan","Chagigah","Yevamot",
    "Ketubot","Nedarim","Nazir","Sotah","Gittin","Kiddushin","Bava Kamma",
    "Bava Metzia","Bava Batra","Sanhedrin","Makkot","Shevuot","Avodah Zarah",
    "Horayot","Zevachim","Menachot","Chullin","Bechorot","Arachin","Temurah",
    "Keritot","Meilah","Tamid","Niddah",
}


_GUIDE_PARTS = {1: 75, 2: 48, 3: 54}  # Guide for the Perplexed


def _daf_range(first: str, last: str) -> list[str]:
    """Expand a Bavli daf range like ("2a", "5b") into ["2a","2b","3a",...]."""
    m1, m2 = re.match(r"(\d+)([ab])", first), re.match(r"(\d+)([ab])", last)
    n, side = int(m1.group(1)), m1.group(2)
    n2, side2 = int(m2.group(1)), m2.group(2)
    out = []
    while (n, side) <= (n2, side2):
        out.append(f"{n}{side}")
        if side == "a":
            side = "b"
        else:
            side = "a"
            n += 1
    return out


def _chapter_options_for_book(book_name: str) -> tuple[list[str], str] | None:
    """
    Return (labels, mode) for the chapter-picker buttons under a book, or
    None if this book isn't chapter-browsable (e.g. one continuous work).
    mode "verse" -> fetch via lookup.get_verse(f"{book_name} {label}")
    mode "hadith" -> fetch via a hadith section lookup
    """
    keys = lookup.chapter_keys(book_name)
    if keys:
        return keys, "verse"
    if book_name in _BAVLI_RANGES:
        first, last = _BAVLI_RANGES[book_name]
        return _daf_range(first, last), "verse"
    if book_name in _MISHNAH_RANGES:
        chaps, _ = _MISHNAH_RANGES[book_name]
        return [str(i) for i in range(1, chaps + 1)], "verse"
    if book_name in _YERUSHALMI_BOOKS:
        tractate = book_name.replace("Jerusalem Talmud ", "")
        chaps = _YERUSHALMI_RANGES.get(tractate)
        if chaps:
            return [str(i) for i in range(1, chaps + 1)], "verse"
    if book_name in _TOSEFTA_BOOKS:
        tractate = book_name.replace("Tosefta ", "")
        base = _MISHNAH_RANGES.get(tractate)
        if base:
            return [str(i) for i in range(1, base[0] + 1)], "verse"
    if book_name in _TARGUM_BOOKS:
        chaps = _TARGUM_CHAPTERS.get(book_name)
        if chaps:
            return [str(i) for i in range(1, chaps + 1)], "verse"
    if book_name in _MIDRASH_BOOKS:
        secs = _MIDRASH_SECTIONS.get(book_name)
        if secs:
            return [str(i) for i in range(1, secs + 1)], "verse"
    if book_name in _MISHNEH_TORAH_BOOKS:
        chaps = _MISHNEH_TORAH_SECTIONS.get(book_name)
        if chaps:
            return [str(i) for i in range(1, chaps + 1)], "verse"
    if book_name == "Guide for the Perplexed":
        return [f"{p}:{c}" for p, n in _GUIDE_PARTS.items() for c in range(1, n + 1)], "verse"
    if book_name == "Tanya":
        return [f"{p}:{c}" for p, (_, n) in _TANYA_PARTS.items() for c in range(1, n + 1)], "verse"
    if book_name in _OTHER_KABBALAH_BOOKS:
        chaps = _KABBALAH_CHAPTERS.get(book_name)
        if chaps:
            return [str(i) for i in range(1, chaps + 1)], "verse"
    if book_name in _ANE_SINGLE_BOOKS:
        count, _ = _ANE_SINGLE_BOOKS[book_name]
        return [str(i) for i in range(1, count + 1)], "verse"
    if book_name in _ZOHAR_BOOKS:
        parasha = book_name.replace("Zohar ", "")
        max_seg = _ZOHAR_SEGMENTS.get(parasha)
        if max_seg:
            return [str(i) for i in range(1, max_seg + 1)], "verse"
    if book_name in _HADITH_BOOKS:
        key = _HADITH_DISPLAY_TO_KEY.get(book_name)
        books = _HADITH_BOOK_COUNTS.get(key) if key else None
        if books:
            return [f"Book {i}" for i in range(1, books + 1)], "hadith"
    return None


def _book_detail_embed(book_name: str) -> discord.Embed:
    """Show chapter-by-chapter verse counts for a single book."""
    counts = lookup.chapter_verse_summary(book_name)
    n_chaps = lookup.chapter_count(book_name)
    embed = discord.Embed(
        title=f"📖 {book_name}",
        color=discord.Color.dark_gold()
    )
    # Show range info from our compiled dicts for non-local texts
    # Baal Cycle: "Baal 1 — Baal and Yamm (9 sections)"
    if book_name.startswith("Baal ") and " — " in book_name:
        import re as _re
        m = _re.match(r"Baal (\d+) — (.+?) \((\d+) sections\)", book_name)
        if m:
            ep_num, ep_title, sec_count = m.group(1), m.group(2), m.group(3)
            embed.title = f"🌙 The Baal Cycle — Episode {ep_num}"
            embed.description = (
                f"**{ep_title}**\n"
                f"**{sec_count} sections** · Cite as: `!verse Baal {ep_num}:1` through `!verse Baal {ep_num}:{sec_count}`\n"
                f"Or: `!parallel Baal {ep_num}.1` for English + Ugaritic"
            )
            return embed
    # Mu'allaqat: "Muallaqat 1 — Imru' al-Qais (61 stanzas)"
    if book_name.startswith("Muallaqat ") and " — " in book_name:
        import re as _re
        m = _re.match(r"Muallaqat (\d+) — (.+?) \((\d+) stanzas\)", book_name)
        if m:
            ode_num, poet, stanza_count = m.group(1), m.group(2), m.group(3)
            roman = ["I","II","III","IV","V","VI","VII"][int(ode_num)-1]
            embed.title = f"🌙 The Mu\'allaqat — Ode {roman}"
            embed.description = (
                f"**{poet}**\n"
                f"**{stanza_count} stanzas** · Cite as: `!verse Muallaqat {ode_num}:1` through `!verse Muallaqat {ode_num}:{stanza_count}`\n"
                f"Or: `!parallel Muallaqat {ode_num}.1` for English + Arabic"
            )
            return embed
    # Quran surah detail: "Quran 2 — Al-Baqara (The Cow, 286v)"
    if book_name.startswith("Quran ") and " — " in book_name:
        m = re.match(r"Quran (\d+) — ([^(]+) \(([^,]+), (\d+)v\)", book_name)
        if m:
            num, arabic, english, verses = m.group(1), m.group(2).strip(), m.group(3).strip(), int(m.group(4))
            embed.title = f"☪️ Quran — Surah {num}: {arabic}"
            embed.description = (
                f"**{arabic}** (*{english}*) · {verses} verses\n"
                f"Cite as: `!verse Quran {num}:1` through `!verse Quran {num}:{verses}`\n"
                f"Or: `!verse Quran {num}` for a random verse from this surah"
            )
            return embed
    if book_name in _BAVLI_RANGES:
        first, last = _BAVLI_RANGES[book_name]
        embed.description = f"**Babylonian Talmud · Daf {first}–{last}**\nCite as: `{book_name} 2a` (whole daf) or `{book_name} 2a:3` (section 3 of daf 2a)"
    elif book_name in _MISHNAH_RANGES and not counts:
        chaps, total = _MISHNAH_RANGES[book_name]
        embed.description = f"**{chaps} chapters · {total} mishnayot**\nCite as: `{book_name} 1:1` (chapter 1, mishnah 1)"
    elif book_name in _YERUSHALMI_BOOKS and not counts:
        tractate = book_name.replace("Jerusalem Talmud ", "")
        chaps = _YERUSHALMI_RANGES.get(tractate, "?")
        embed.description = f"**Jerusalem Talmud · {chaps} chapters**\nCite as: `Jerusalem Talmud {tractate} 1:1` (chapter:halakhah)"
    elif book_name in _ZOHAR_BOOKS and not counts:
        parasha = book_name.replace("Zohar ", "")
        max_seg = _ZOHAR_SEGMENTS.get(parasha, "?")
        embed.description = f"**Zohar · {parasha} · Segments 1–{max_seg}**\nCite as: `Zohar {parasha} 5` (segment number)"
    elif book_name in _MIDRASH_BOOKS and not counts:
        secs = _MIDRASH_SECTIONS.get(book_name, "?")
        embed.description = f"**{secs} sections**\nCite as: `{book_name} 1:1` (section:subsection)"
    elif book_name in _TARGUM_BOOKS and not counts:
        chaps = _TARGUM_CHAPTERS.get(book_name, "?")
        embed.description = f"**{chaps} chapters** (mirrors biblical book)\nCite as: `{book_name} 1:1` (chapter:verse)"
    elif book_name in _TOSEFTA_BOOKS and not counts:
        tractate = book_name.replace("Tosefta ", "")
        base = _MISHNAH_RANGES.get(tractate)
        chaps = base[0] if base else "?"
        embed.description = f"**{chaps} chapters**\nCite as: `Tosefta {tractate} 1:1` (chapter:halakhah)"
    elif book_name in _MISHNEH_TORAH_BOOKS and not counts:
        chaps = _MISHNEH_TORAH_SECTIONS[book_name]
        section = book_name.replace("Mishneh Torah, ", "")
        embed.description = (
            f"**{chaps} chapters**\n"
            f"Cite as: `Mishneh Torah, {section} 1:1` (chapter:halacha)\n"
            f"e.g. `!verse Mishneh Torah, {section} 1:1`"
        )
    elif book_name == "Guide for the Perplexed" and not counts:
        embed.description = (
            "**3 parts · 179 chapters**\n"
            "Cite as: `Guide for the Perplexed 1:1` (part:chapter)\n"
            "Parts: 1 (75 ch.), 2 (48 ch.), 3 (54 ch.)"
        )
    elif book_name == "Tanya" and not counts:
        parts_desc = "\n".join(
            f"  Part {n}: {name} ({chaps} ch.) — `!verse Tanya {n}:1`"
            for n, (name, chaps) in _TANYA_PARTS.items()
        )
        embed.description = f"**5 parts · 118 total chapters**\n{parts_desc}"
    elif book_name in _OTHER_KABBALAH_BOOKS and not counts:
        chaps = _KABBALAH_CHAPTERS.get(book_name, "?")
        embed.description = f"**{chaps} chapters**\nCite as: `{book_name} 1:1`"
    elif book_name in _ANE_SINGLE_BOOKS and not counts:
        count, unit = _ANE_SINGLE_BOOKS[book_name]
        _ane_keywords = {
            "The Great Hymn to the Aten": "Aten",
            "Book of the Dead":           "Book of the Dead",
            "The Leiden Hymns":           "Leiden Hymns",
            "The Instruction of Amenemope": "Amenemope",
            "The Book of Two Ways":       "Two Ways",
            "The Story of Ahikar":        "Ahikar",
        }
        kw = _ane_keywords.get(book_name, book_name)
        embed.description = (
            f"**{count} {unit}s**\n"
            f"Cite as: `!verse {kw} 1` through `!verse {kw} {count}`\n"
            f"Or: `!verse {kw}` for the full text"
        )
    elif book_name in _HADITH_BOOKS and not counts:
        key = _HADITH_DISPLAY_TO_KEY.get(book_name)
        if key:
            total = _HADITH_COUNTS.get(key, "?")
            books = _HADITH_BOOK_COUNTS.get(key, 1)
            embed.description = (
                f"**{total:,} hadiths · {books} books**\n"
                f"Cite by sequential number: `!verse {book_name} 1`\n"
                f"Range: 1–{total:,}"
            )
    elif counts:
        total_verses = sum(counts)
        col_lines = []
        row = []
        for i, vc in enumerate(counts, 1):
            row.append(f"{i}:{vc}")
            if len(row) == 6:
                col_lines.append("  ".join(row))
                row = []
        if row:
            col_lines.append("  ".join(row))
        embed.description = f"**{len(counts)} chapters · {total_verses} verses**\n```\n" + "\n".join(col_lines) + "\n```"
    elif n_chaps:
        embed.description = f"{n_chaps} chapters (verse detail not available locally)"
    else:
        embed.description = "Details not available for this book."

    # Citation hint with actual ranges
    if book_name.startswith("Quran ") and " — " in book_name:
        m = re.match(r"Quran (\d+) — ([^(]+) \(([^,]+), (\d+)v\)", book_name)
        if m:
            num, arabic, verses = m.group(1), m.group(2).strip(), m.group(4)
            hint = f"Verses 1–{verses} · !verse Quran {num}:1  (surah:ayah)"
        else:
            hint = f"!verse Quran <surah>:<ayah>"
    elif book_name in _PLATO_STEPHANUS_RANGES:
        first, last = _PLATO_STEPHANUS_RANGES[book_name]
        hint = f"Stephanus {first}–{last} · e.g. !verse {book_name} {first}"
    elif book_name in _BAVLI_RANGES:
        first, last = _BAVLI_RANGES[book_name]
        hint = f"Daf {first}–{last} · e.g. !verse {book_name} 2a  or  {book_name} 2a:3"
    elif book_name in _MISHNAH_RANGES:
        chaps, total = _MISHNAH_RANGES[book_name]
        hint = f"Chapters 1–{chaps} · {total} mishnayot · e.g. !verse {book_name} 1:1"
    elif book_name in _CITATION_HINTS:
        hint = _CITATION_HINTS[book_name]
    elif book_name in _ANE_SINGLE_BOOKS:
        count, unit = _ANE_SINGLE_BOOKS[book_name]
        # derive the short command keyword
        _ane_keywords = {
            "The Great Hymn to the Aten": "Aten",
            "Book of the Dead":           "Book of the Dead",
            "The Leiden Hymns":           "Leiden Hymns",
            "The Instruction of Amenemope": "Amenemope",
            "The Book of Two Ways":       "Two Ways",
            "The Story of Ahikar":        "Ahikar",
        }
        kw = _ane_keywords.get(book_name, book_name)
        hint = f"{count} {unit}s · !verse {kw} 1 through !verse {kw} {count}"
    elif book_name in _HADITH_BOOKS:
        key = _HADITH_DISPLAY_TO_KEY.get(book_name)
        if key:
            total = _HADITH_COUNTS.get(key, "?")
            books = _HADITH_BOOK_COUNTS.get(key, 1)
            books_str = f" across {books} books" if books > 1 else ""
            hint = f"Hadiths 1–{total:,}{books_str} · !verse {book_name} 1"
        else:
            hint = f"!verse {book_name} 1  (hadith number)"
    elif book_name in _YERUSHALMI_BOOKS:
        tractate = book_name.replace("Jerusalem Talmud ", "")
        chaps = _YERUSHALMI_RANGES.get(tractate, "?")
        hint = f"Chapters 1–{chaps} · !verse Jerusalem Talmud {tractate} 1:1  (ch:halakhah)"
    elif book_name in _TOSEFTA_BOOKS:
        tractate = book_name.replace("Tosefta ", "")
        base = _MISHNAH_RANGES.get(tractate)
        chaps = base[0] if base else "?"
        hint = f"Chapters 1–{chaps} · !verse Tosefta {tractate} 1:1  (ch:halakhah)"
    elif book_name in _TARGUM_BOOKS:
        chaps = _TARGUM_CHAPTERS.get(book_name, "?")
        hint = f"Chapters 1–{chaps} · !verse {book_name} 1:1  (chapter:verse)"
    elif book_name in _MIDRASH_BOOKS:
        secs = _MIDRASH_SECTIONS.get(book_name, "?")
        hint = f"Sections 1–{secs} · !verse {book_name} 1:1  (section:subsection)"
    elif book_name in _ZOHAR_BOOKS:
        parasha = book_name.replace("Zohar ", "")
        max_seg = _ZOHAR_SEGMENTS.get(parasha, "?")
        hint = f"Segments 1–{max_seg} · !verse Zohar {parasha} 1  (segment number)"
    elif book_name in _MISHNEH_TORAH_BOOKS:
        chaps = _MISHNEH_TORAH_SECTIONS[book_name]
        hint = f"Chapters 1–{chaps} · !verse {book_name} 1:1  (chapter:halacha)"
    elif book_name == "Guide for the Perplexed":
        hint = "3 parts · !verse Guide for the Perplexed 1:1  (part:chapter)"
    elif book_name == "Tanya":
        hint = (
            "5 parts · cite as `!verse Tanya <part>:<chapter>`\n"
            "e.g. `!verse Tanya 1:5` (Likkutei Amarim ch. 5) · "
            "`!verse Tanya 2:1` (Shaar HaYichud ch. 1)"
        )
    elif book_name in _OTHER_KABBALAH_BOOKS:
        chaps = _KABBALAH_CHAPTERS.get(book_name, "?")
        hint = f"Chapters 1–{chaps} · !verse {book_name} 1:1  (chapter:verse)"
    elif book_name == "Zohar":
        hint = "!verse Zohar Bereshit 5  (parasha + segment number)"
    else:
        hint = f"!verse {book_name} <ch>:<v> · !verse {book_name} for a random verse"

    embed.set_footer(text=hint)
    return embed


def _book_label(item: str) -> str:
    """Return the display label for a book in the list view."""
    # Baal Cycle and Mu'allaqat entries from BOOKS_TREE
    if item.startswith("Baal ") and " — " in item:
        # "Baal 1 — Baal and Yamm (9 sections)" → show the title part
        parts = item.split(" — ", 1)
        return parts[1] if len(parts) > 1 else item
    if item.startswith("Muallaqat ") and " — " in item:
        parts = item.split(" — ", 1)
        return parts[1] if len(parts) > 1 else item
    # Quran surah entries: "Quran N — Name (English, Mv)"
    if item.startswith("Quran ") and " — " in item:
        # Show as "N. Name (English) — Mv" in the list
        m = re.match(r"Quran (\d+) — ([^(]+) \(([^,]+), (\d+)v\)", item)
        if m:
            num, arabic, english, verses = m.group(1), m.group(2).strip(), m.group(3).strip(), m.group(4)
            return f"{num}. {arabic} · {english} · {verses}v"
        return item
    if item in _PLATO_STEPHANUS_RANGES:
        first, last = _PLATO_STEPHANUS_RANGES[item]
        return f"{item} ({first}–{last})"
    if item in _BAVLI_RANGES:
        first, last = _BAVLI_RANGES[item]
        return f"{item} ({first}–{last})"
    if item in _MISHNAH_RANGES:
        chaps, total = _MISHNAH_RANGES[item]
        return f"{item} ({chaps} ch., {total} m.)"
    if item in _YERUSHALMI_BOOKS:
        tractate = item.replace("Jerusalem Talmud ", "")
        chaps = _YERUSHALMI_RANGES.get(tractate, "?")
        return f"{tractate} ({chaps} ch.)"
    if item in _TOSEFTA_BOOKS:
        tractate = item.replace("Tosefta ", "")
        base = _MISHNAH_RANGES.get(tractate)
        return f"Tosefta {tractate} ({base[0]} ch.)" if base else f"Tosefta {tractate}"
    if item in _TARGUM_BOOKS:
        chaps = _TARGUM_CHAPTERS.get(item)
        return f"{item} ({chaps} ch.)" if chaps else item
    if item in _MIDRASH_BOOKS:
        secs = _MIDRASH_SECTIONS.get(item)
        return f"{item} ({secs} sec.)" if secs else f"{item}"
    if item in _ZOHAR_BOOKS:
        parasha = item.replace("Zohar ", "")
        max_seg = _ZOHAR_SEGMENTS.get(parasha, "?")
        return f"{parasha} (1–{max_seg})"
    if item in _MISHNEH_TORAH_BOOKS:
        chaps = _MISHNEH_TORAH_SECTIONS[item]
        section = item.replace("Mishneh Torah, ", "")
        return f"{section} ({chaps} ch.)"
    if item == "Guide for the Perplexed":
        return "Guide for the Perplexed (3 parts, 179 ch.)"
    if item == "Tanya":
        return "Tanya (5 parts: 53+12+12+32+9 ch.)"
    if item in _OTHER_KABBALAH_BOOKS:
        chaps = _KABBALAH_CHAPTERS.get(item)
        return f"{item} ({chaps} ch.)" if chaps else f"{item}"
    if item in _ANE_SINGLE_BOOKS:
        count, unit = _ANE_SINGLE_BOOKS[item]
        return f"{item} ({count} {unit}s)"
    if item in _HADITH_BOOKS:
        key = _HADITH_DISPLAY_TO_KEY.get(item)
        if key:
            total = _HADITH_COUNTS.get(key, "?")
            books = _HADITH_BOOK_COUNTS.get(key, 1)
            books_str = f", {books} books" if books > 1 else ""
            return f"{item} (1–{total:,}{books_str})"
        return f"{item} (hadith)"
    n = lookup.chapter_count(item)
    if n:
        return f"{item} ({n} ch.)"
    return item


def _chapter_picker_embed(book_name: str, total: int) -> discord.Embed:
    embed = discord.Embed(
        title=f"📖 {book_name}",
        description=f"{total} chapter{'s' if total != 1 else ''} — click one to read it here.",
        color=discord.Color.dark_gold(),
    )
    embed.set_footer(text=f"!verse {book_name} <ch> also works directly")
    return embed


def _books_embed(node, title: str, page: int = 0) -> discord.Embed:
    subcats = [item for item in node if isinstance(item, tuple)]
    strings = [item for item in node if isinstance(item, str)]
    # If node is all strings (e.g. list of saint names), paginate those
    if strings and not subcats:
        total_pages = max(1, (len(strings) + PAGE_SIZE - 1) // PAGE_SIZE)
        page = max(0, min(page, total_pages - 1))
        page_items = strings[page * PAGE_SIZE:(page + 1) * PAGE_SIZE]
        lines = [_book_label(item) for item in page_items]
    else:
        total_pages = max(1, (len(subcats) + PAGE_SIZE - 1) // PAGE_SIZE)
        page = max(0, min(page, total_pages - 1))
        page_items = subcats[page * PAGE_SIZE:(page + 1) * PAGE_SIZE]
        lines = []
        for item in page_items:
            if isinstance(item, tuple):
                sub_name, sub_contents = item
                count = _count_leaves(sub_contents)
                lines.append(f"**{sub_name}** ({count})" if count > 1 else sub_name)
            else:
                lines.append(f"  {_book_label(item)}")

    footer = "!verse <book> for a random verse"
    if total_pages > 1:
        footer = f"Page {page+1}/{total_pages} · " + footer
    else:
        footer = "Click a category to expand it · " + footer

    embed = discord.Embed(
        title=f"📚 {title}",
        description="\n".join(lines) or "Nothing loaded yet.",
        color=discord.Color.dark_gold()
    )
    embed.set_footer(text=footer)
    return embed


def _find_node(tree, label: str):
    for item in tree:
        if isinstance(item, tuple):
            name, contents = item
            if name == label:
                return (name, contents)
            found = _find_node(contents, label)
            if found:
                return found
    return None


PAGE_SIZE = 16  # buttons per page (leaves 1 row for nav/back)

class BooksView(discord.ui.View):
    def __init__(self, stack: list, page: int = 0):
        super().__init__(timeout=120)
        self.stack = stack
        self.page = page
        self._rebuild()

    def _rebuild(self):
        self.clear_items()
        label, node, mode = self.stack[-1]

        # Chapter/section picker — leaf buttons fetch a chapter or hadith book
        if mode in ("verse", "hadith"):
            total_pages = max(1, (len(node) + PAGE_SIZE - 1) // PAGE_SIZE)
            page = max(0, min(self.page, total_pages - 1))
            page_items = node[page * PAGE_SIZE:(page + 1) * PAGE_SIZE]
            for i, chap_label in enumerate(page_items):
                btn = discord.ui.Button(
                    label=chap_label[:80],
                    style=discord.ButtonStyle.primary,
                    row=i // 4
                )
                btn.callback = self._make_chapter_fetch(label, node, page * PAGE_SIZE + i, mode)
                self.add_item(btn)
            self._add_nav(total_pages, page)
            if total_pages > 1:
                jump_btn = discord.ui.Button(label="🔢 Jump to chapter", style=discord.ButtonStyle.secondary, row=4)
                jump_btn.callback = self._make_jump_open(label, node, mode)
                self.add_item(jump_btn)
            return

        subcats = [item for item in node if isinstance(item, tuple)]
        strings = [item for item in node if isinstance(item, str)]

        # Pure string list — paginate; each one opens a chapter picker
        if strings and not subcats:
            total_pages = max(1, (len(strings) + PAGE_SIZE - 1) // PAGE_SIZE)
            page = max(0, min(self.page, total_pages - 1))
            page_items = strings[page * PAGE_SIZE:(page + 1) * PAGE_SIZE]
            for i, book_name in enumerate(page_items):
                btn = discord.ui.Button(
                    label=book_name[:80],
                    style=discord.ButtonStyle.primary,
                    row=i // 4
                )
                btn.callback = self._make_book_open(book_name)
                self.add_item(btn)
        else:
            total_pages = max(1, (len(subcats) + PAGE_SIZE - 1) // PAGE_SIZE)
            page = max(0, min(self.page, total_pages - 1))
            page_items = subcats[page * PAGE_SIZE:(page + 1) * PAGE_SIZE]

            # Content buttons (rows 0-3, 4 per row)
            for i, (sub_name, sub_contents) in enumerate(page_items):
                btn_label = sub_name
                for emoji in ("📖 ","👼 ","✡️ ","☪️ ","🏛️ ","📯 ","🌍 ","🔥 ","🧿 ","⛪ "):
                    btn_label = btn_label.replace(emoji, "")
                btn_label = btn_label[:80]
                btn = discord.ui.Button(
                    label=btn_label,
                    style=discord.ButtonStyle.primary,
                    row=i // 4
                )
                btn.callback = self._make_drill(sub_name, sub_contents)
                self.add_item(btn)

        self._add_nav(total_pages, page)

    def _add_nav(self, total_pages, page):
        # Nav row (row 4): Prev, page indicator, Next, Back
        if total_pages > 1:
            prev_btn = discord.ui.Button(
                label="◀",
                style=discord.ButtonStyle.secondary,
                row=4,
                disabled=(page == 0)
            )
            prev_btn.callback = self._go_prev
            self.add_item(prev_btn)

            page_btn = discord.ui.Button(
                label=f"{page + 1}/{total_pages}",
                style=discord.ButtonStyle.secondary,
                row=4,
                disabled=True
            )
            self.add_item(page_btn)

            next_btn = discord.ui.Button(
                label="▶",
                style=discord.ButtonStyle.secondary,
                row=4,
                disabled=(page >= total_pages - 1)
            )
            next_btn.callback = self._go_next
            self.add_item(next_btn)

        if len(self.stack) > 1:
            back_btn = discord.ui.Button(
                label="◀ Back",
                style=discord.ButtonStyle.secondary,
                row=4
            )
            back_btn.callback = self._go_back
            self.add_item(back_btn)

    async def _open_book(self, interaction: discord.Interaction, book_name: str):
        """Push a chapter/section picker for this book, or fall back to the
        plain detail embed if it isn't chapter-browsable (one continuous work)."""
        options = _chapter_options_for_book(book_name)
        if options is None:
            await interaction.response.edit_message(
                embed=_book_detail_embed(book_name), view=self
            )
            return
        labels, mode = options
        self.stack.append((book_name, labels, mode))
        self.page = 0
        self._rebuild()
        await interaction.response.edit_message(
            embed=_chapter_picker_embed(book_name, len(labels)), view=self
        )

    def _make_book_open(self, book_name: str):
        async def callback(interaction: discord.Interaction):
            await self._open_book(interaction, book_name)
        return callback

    def _make_chapter_fetch(self, book_name: str, chapter_labels: list[str], index: int, mode: str):
        chap_label = chapter_labels[index]

        async def callback(interaction: discord.Interaction):
            if mode == "hadith":
                await interaction.response.defer()
            result = _fetch_chapter_result(book_name, chap_label, mode)
            nav_btns = _make_chapter_nav_buttons(book_name, chapter_labels, index, mode)
            await _send_result(interaction, result, extra_buttons=nav_btns)
        return callback

    def _make_jump_open(self, book_name: str, chapter_labels: list[str], mode: str):
        async def callback(interaction: discord.Interaction):
            await interaction.response.send_modal(_ChapterJumpModal(book_name, chapter_labels, mode))
        return callback

    def _make_drill(self, name, contents):
        async def callback(interaction: discord.Interaction):
            actual_contents = contents
            only_strings = all(isinstance(x, str) for x in contents)
            if only_strings:
                # If this is a single book name, open its chapter picker directly
                if len(contents) == 1:
                    await self._open_book(interaction, contents[0])
                    return
                # Look up works directly from loaded corpus data, bypassing tree
                from collections import defaultdict
                source_books = defaultdict(list)
                for corpus_data in lookup._data.values():
                    for book_name in corpus_data:
                        src = lookup._book_sources.get(book_name, "")
                        if src:
                            source_books[src].append(book_name)
                # Try exact match, then case-insensitive
                works = source_books.get(name) or source_books.get(name.lower())
                if not works:
                    for src_name, src_works in source_books.items():
                        if src_name.lower() == name.lower():
                            works = src_works
                            break
                if works and len(works) > len(contents):
                    actual_contents = sorted(works)
                # If the contents are a list of book names, add detail buttons
                if actual_contents and all(isinstance(x, str) for x in actual_contents):
                    self.stack.append((name, actual_contents, "tree"))
                    self.page = 0
                    self._rebuild()
                    await interaction.response.edit_message(
                        embed=_books_embed(actual_contents, name, page=0), view=self
                    )
                    return
            self.stack.append((name, actual_contents, "tree"))
            self.page = 0
            self._rebuild()
            await interaction.response.edit_message(embed=_books_embed(actual_contents, name, page=0), view=self)
        return callback

    def _current_embed(self) -> discord.Embed:
        label, node, mode = self.stack[-1]
        if mode in ("verse", "hadith"):
            return _chapter_picker_embed(label, len(node))
        return _books_embed(node, label, page=self.page)

    async def _go_prev(self, interaction: discord.Interaction):
        self.page = max(0, self.page - 1)
        self._rebuild()
        await interaction.response.edit_message(embed=self._current_embed(), view=self)

    async def _go_next(self, interaction: discord.Interaction):
        self.page += 1
        self._rebuild()
        await interaction.response.edit_message(embed=self._current_embed(), view=self)

    async def _go_back(self, interaction: discord.Interaction):
        self.stack.pop()
        self.page = 0
        self._rebuild()
        await interaction.response.edit_message(embed=self._current_embed(), view=self)

    async def on_timeout(self):
        try:
            await self.message.edit(view=None)
        except Exception:
            pass


class _ChapterJumpModal(discord.ui.Modal, title="Jump to chapter"):
    def __init__(self, book_name: str, chapter_labels: list[str], mode: str):
        super().__init__()
        self.book_name = book_name
        self.chapter_labels = chapter_labels
        self.mode = mode
        self.chapter_input = discord.ui.TextInput(
            label="Chapter",
            placeholder=f"e.g. {chapter_labels[0]}" if chapter_labels else "1",
            max_length=20,
        )
        self.add_item(self.chapter_input)

    async def on_submit(self, interaction: discord.Interaction):
        raw = self.chapter_input.value.strip()
        match = next((l for l in self.chapter_labels if l.lower() == raw.lower()), None)
        if match is None and self.mode == "hadith" and raw.isdigit():
            candidate = f"Book {raw}"
            match = candidate if candidate in self.chapter_labels else None
        if match is None:
            await interaction.response.send_message(
                f"⚠️ `{raw}` isn't a valid chapter for **{self.book_name}**. "
                f"Range: {self.chapter_labels[0]}–{self.chapter_labels[-1]}.",
                ephemeral=True,
            )
            return
        index = self.chapter_labels.index(match)
        if self.mode == "hadith":
            await interaction.response.defer()
        result = _fetch_chapter_result(self.book_name, match, self.mode)
        nav_btns = _make_chapter_nav_buttons(self.book_name, self.chapter_labels, index, self.mode)
        await _send_result(interaction, result, extra_buttons=nav_btns)


def _author_works_node(author_name: str) -> tuple | None:
    """
    Search loaded patristics data for an author by name (fuzzy).
    Returns (display_name, works_list) or None.
    """
    from difflib import get_close_matches
    from collections import defaultdict

    # Group patristics books by their source (author name)
    # Search all loaded corpora for author→works mapping
    source_books = defaultdict(list)
    for corpus_data in lookup._data.values():
        for book_name in corpus_data:
            src = lookup._book_sources.get(book_name, "")
            if src:
                source_books[src].append(book_name)

    # Collect tree author nodes (tuples with string-only children)
    def collect_tree_authors(tree):
        authors = {}
        for item in tree:
            if isinstance(item, tuple):
                name, contents = item
                has_strings = any(isinstance(x, str) for x in contents)
                has_tuples  = any(isinstance(x, tuple) for x in contents)
                if has_strings and not has_tuples:
                    authors[name] = contents
                else:
                    authors.update(collect_tree_authors(contents))
        return authors

    tree_authors = collect_tree_authors(BOOKS_TREE)
    all_names = list(tree_authors.keys()) + list(source_books.keys())
    query = author_name.strip()

    # Exact match (case-insensitive)
    for name in all_names:
        if name.lower() == query.lower():
            works = tree_authors.get(name) or source_books.get(name, [])
            return (name, works)

    # Fuzzy match
    matches = get_close_matches(query, all_names, n=1, cutoff=0.55)
    if matches:
        name = matches[0]
        works = tree_authors.get(name) or source_books.get(name, [])
        return (name, works)

    return None


@bot.command(name="books")
async def list_books(ctx, *, section: str = ""):
    """Browse available scripture collections. Use !books <author> to list their works."""
    top_label = "Available Scripture"
    top_node  = ROOT_BOOKS_TREE

    if section.strip():
        # 1. Try BOOKS_TREE section match first
        found = _find_node(BOOKS_TREE, section.strip())
        if found:
            label, node = found
            stack = [(top_label, top_node, "tree"), (label, node, "tree")]
            label, node, _mode = stack[-1]
            view = BooksView(stack)
            view.message = await ctx.send(embed=_books_embed(node, label), view=view)
        else:
            # 2. Try author name match against loaded data
            author_result = _author_works_node(section.strip())
            if author_result:
                author_name, works = author_result
                embed = discord.Embed(
                    title=f"📚 {author_name}",
                    color=discord.Color.dark_gold()
                )
                lines = []
                for work in works:
                    if isinstance(work, str):
                        lines.append(f"• **{_book_label(work)}**")
                    elif isinstance(work, tuple):
                        sub_name, sub_works = work
                        lines.append(f"**{sub_name}**")
                        for sw in sub_works:
                            if isinstance(sw, str):
                                lines.append(f"  · {_book_label(sw)}")
                embed.description = "\n".join(lines) or "No works found."
                embed.set_footer(text="!verse <work> <ch>:<v> to look up a passage")
                await ctx.send(embed=embed)
            else:
                await ctx.send(
                    f"**{section}** not found.\n"
                    f"Try `!books` for the full list, or `!books Augustine` to list an author's works."
                )
    else:
        stack = [(top_label, top_node, "tree")]
        label, node, _mode = stack[-1]
        view = BooksView(stack)
        view.message = await ctx.send(embed=_books_embed(node, label), view=view)



# ── !votd — Verse of the Day (reference from verseoftheday.com, text from KJV) -

async def _send_votd(ctx_or_channel, translation: str = ""):
    """
    Core VOTD logic. Scrapes verseoftheday.com, falls back to a random
    well-known verse if the site is unreachable. Supports optional translation.
    """
    reference, date_text = _scrape_votd()
    used_fallback = False
    if reference is None:
        reference = random.choice(_VOTD_FALLBACKS)
        log.info(f"RNG  VOTD fallback          → {reference}")
        used_fallback = True

    # Strip verse range for single-verse lookup
    ref_single = re.sub(r"\s*[-–]\s*\d+$", "", reference)

    # Resolve text — local KJV or live translation
    trans_key = translation.strip().lower()
    if trans_key and trans_key in TRANSLATION_SUFFIXES:
        result = get_translation(ref_single, translation)
    else:
        result = lookup.get_verse(ref_single)
        if not result.get("found"):
            result = lookup.get_verse(reference)

    if not result.get("found"):
        msg = f"⚠️ Today's verse is **{reference}** but couldn't be retrieved."
        if hasattr(ctx_or_channel, "send"):
            await ctx_or_channel.send(msg)
        return

    footer_parts = []
    if used_fallback:
        footer_parts.append("⚠️ verseoftheday.com unavailable — showing a classic verse")
    elif date_text:
        footer_parts.append(f"Verse of the Day — {date_text}")
    footer_parts.append(result.get("source", "King James Version"))

    loop = asyncio.get_event_loop()
    buf = await loop.run_in_executor(
        None, _render_verse_card, result["reference"], result["text"], " · ".join(footer_parts)
    )
    await ctx_or_channel.send(file=discord.File(buf, filename="votd.png"))
    _record_last_cited(ctx_or_channel, result)


@bot.command(name="votd", aliases=["verseoftheday", "dayverse"])
async def cmd_votd(ctx, *, translation: str = ""):
    """Verse of the Day, optionally in a specific translation.
    Usage: !votd  |  !votd ESV  |  !votd full  |  !votd extended"""
    arg = translation.strip()
    if arg.lower() == "full":
        async with ctx.typing():
            await _send_votd_full(ctx)
        return
    if arg.lower() == "extended":
        async with ctx.typing():
            await _send_votd_extended(ctx)
        return
    async with ctx.typing():
        await _send_votd(ctx, translation=arg)


@bot.command(name="votdmode", hidden=True)
@commands.has_permissions(administrator=True)
async def cmd_votdmode(ctx, *, mode: str = ""):
    """Hidden: toggle which VOTD style this server's daily task uses.
    Usage: !votdmode             — show current mode
           !votdmode basic       — verse only (original VOTD)
           !votdmode full        — verse + ancients + first commentary
           !votdmode extended    — full VOTD + today's calendar across five traditions
           !votdmode toggle      — cycle: basic → full → extended → basic
    """
    if not ctx.guild:
        await ctx.send("This command only works in a server.")
        return

    requested = mode.strip().lower()
    current = _get_guild_votd(ctx.guild.id)["mode"]

    if not requested:
        await ctx.send(
            f"VOTD mode is currently **{current}**. "
            "Use `!votdmode basic`, `!votdmode full`, `!votdmode extended`, or `!votdmode toggle`."
        )
        return

    cycle = {"basic": "full", "full": "extended", "extended": "basic"}
    if requested == "toggle":
        new_mode = cycle.get(current, "full")
    elif requested in ("basic", "full", "extended"):
        new_mode = requested
    else:
        await ctx.send(f"Unknown mode `{requested}`. Use `basic`, `full`, `extended`, or `toggle`.")
        return

    if new_mode == current:
        await ctx.send(f"VOTD mode is already **{current}**.")
        return

    _update_guild_config(ctx.guild.id, votd_mode=new_mode)
    await ctx.send(
        f"VOTD mode switched from **{current}** to **{new_mode}**. "
        f"The daily post will use the {new_mode} format from now on."
    )


@bot.command(name="votdsetup", aliases=["votdconfig"])
@commands.has_permissions(administrator=True)
async def cmd_votdsetup(ctx, action: str = "", *, arg: str = ""):
    """Configure this server's daily Verse of the Day post.
    Usage: !votdsetup                — show this server's current config
           !votdsetup channel #chan  — set the announcement channel
           !votdsetup time 04:00     — set the daily post time (24h UTC)
           !votdsetup mode full      — basic | full | extended
           !votdsetup off            — disable daily VOTD for this server
    """
    if not ctx.guild:
        await ctx.send("This command only works in a server.")
        return

    action = action.strip().lower()
    settings = _get_guild_votd(ctx.guild.id)

    if not action:
        channel_desc = f"<#{settings['channel_id']}>" if settings["channel_id"] else "*not set — daily VOTD is off*"
        embed = discord.Embed(title=f"⚙️ VOTD setup — {ctx.guild.name}", color=discord.Color.dark_gold())
        embed.add_field(name="Channel", value=channel_desc, inline=True)
        embed.add_field(name="Time (UTC)", value=settings["time"], inline=True)
        embed.add_field(name="Mode", value=settings["mode"], inline=True)
        embed.set_footer(text="!votdsetup channel #chan · !votdsetup time HH:MM · !votdsetup mode basic|full|extended · !votdsetup off")
        await ctx.send(embed=embed)
        return

    if action == "off":
        _update_guild_config(ctx.guild.id, votd_channel_id=None)
        await ctx.send("Daily VOTD disabled for this server.")
        return

    if action == "channel":
        channel = ctx.message.channel_mentions[0] if ctx.message.channel_mentions else None
        if channel is None:
            await ctx.send("Mention a channel: `!votdsetup channel #general`")
            return
        _update_guild_config(ctx.guild.id, votd_channel_id=channel.id)
        await ctx.send(f"Daily VOTD will post in {channel.mention} at {settings['time']} UTC ({settings['mode']} mode).")
        return

    if action == "time":
        m = re.match(r"^(\d{1,2}):(\d{2})$", arg.strip())
        if not m or not (0 <= int(m.group(1)) <= 23 and 0 <= int(m.group(2)) <= 59):
            await ctx.send("Use 24h UTC format: `!votdsetup time 04:00`")
            return
        hh, mm = int(m.group(1)), int(m.group(2))
        _update_guild_config(ctx.guild.id, votd_time=f"{hh:02d}:{mm:02d}")
        await ctx.send(f"Daily VOTD time set to **{hh:02d}:{mm:02d} UTC**.")
        return

    if action == "mode":
        new_mode = arg.strip().lower()
        if new_mode not in ("basic", "full", "extended"):
            await ctx.send("Mode must be `basic`, `full`, or `extended`.")
            return
        _update_guild_config(ctx.guild.id, votd_mode=new_mode)
        await ctx.send(f"Daily VOTD mode set to **{new_mode}**.")
        return

    await ctx.send("Unknown option. Use `channel`, `time`, `mode`, or `off` — see `!help votdsetup`.")


# ── !features — opt-in per-guild feature flags ──────────────────────────────────

@bot.command(name="features")
@commands.has_permissions(administrator=True)
async def cmd_features(ctx, name: str = "", state: str = ""):
    """Turn optional server features on or off. All default OFF.
    Usage: !features                    — show current state
           !features react_save on      — react 📌 to a verse to bookmark it
           !features streaks off        — !plan check-in streaks
           !features export on          — !saved export as a text file
    """
    if not ctx.guild:
        await ctx.send("This command only works in a server.")
        return

    name = name.strip().lower()
    if not name:
        current = _get_guild_features(ctx.guild.id)
        lines = [f"`{k}` — {'**on**' if current[k] else 'off'} — {desc}" for k, desc in GUILD_FEATURES.items()]
        embed = discord.Embed(
            title=f"⚙️ Optional Features — {ctx.guild.name}",
            description="\n".join(lines),
            color=discord.Color.dark_gold(),
        )
        embed.set_footer(text="!features <name> on|off")
        await ctx.send(embed=embed)
        return

    if name not in GUILD_FEATURES:
        await ctx.send(f"Unknown feature `{name}`. Options: {', '.join(GUILD_FEATURES)}")
        return

    state = state.strip().lower()
    if state not in ("on", "off"):
        await ctx.send(f"Usage: `!features {name} on` or `!features {name} off`")
        return

    _update_guild_config(ctx.guild.id, **{f"feature_{name}": state == "on"})
    await ctx.send(f"`{name}` is now **{state}** for this server.")


# ── !today — Liturgical / religious calendar across traditions ─────────────────

# Which traditions to include for each !today flavour.
# "christian" = all three Christian denominations in one embed.
_TODAY_GROUPS = {
    "all":        ["catholic", "anglican", "orthodox", "jewish", "islamic"],
    "christian":  ["catholic", "anglican", "orthodox"],
    "catholic":   ["catholic"],
    "anglican":   ["anglican"],
    "orthodox":   ["orthodox"],
    "islam":      ["islamic"],
    "islamic":    ["islamic"],
    "muslim":     ["islamic"],
    "jewish":     ["jewish"],
    "judaism":    ["jewish"],
    "jew":        ["jewish"],
}

# Display metadata per tradition key (used in both embeds and help)
_TODAY_META = {
    "catholic": ("✝️", "Catholic (Roman Rite)"),
    "anglican": ("⛪", "Anglican (Common Worship)"),
    "orthodox": ("☦️", "Orthodox"),
    "jewish":   ("✡️", "Jewish"),
    "islamic":  ("☪️", "Islamic"),
}


async def _send_today(ctx_or_channel, target_date, traditions: list[str], title_label: str):
    """
    Build and send a combined embed showing the requested traditions
    for `target_date`.
    """
    import liturgical_calendar as _lcal

    loop = asyncio.get_event_loop()

    fetchers = {
        "catholic": _lcal.catholic_today,
        "anglican": _lcal.anglican_today,
        "orthodox": _lcal.orthodox_today,
        "jewish":   _lcal.jewish_today,
        "islamic":  _lcal.islamic_today,
    }

    # Kick off all requested lookups in parallel
    futures = {name: loop.run_in_executor(None, fetchers[name], target_date)
               for name in traditions if name in fetchers}
    results: dict[str, dict] = {}
    for name, fut in futures.items():
        try:
            results[name] = await fut
        except Exception as e:
            results[name] = {"found": False, "error": f"{e}"}

    pretty = (
        target_date.strftime("%A, ")
        + target_date.strftime("%d").lstrip("0")
        + target_date.strftime(" %B %Y")
    )

    embed = discord.Embed(
        title=f"📅 {pretty} — {title_label}",
        color=discord.Color.dark_gold(),
    )

    for name in traditions:
        emoji, label = _TODAY_META.get(name, ("•", name.title()))
        r = results.get(name) or {}
        if r.get("found"):
            value = r.get("summary", "—")
            details = (r.get("details") or "").strip()
            if details:
                value = f"{value}\n{details}"
        else:
            err = r.get("error", "lookup failed")
            value = f"_{err}_"
        if len(value) > 1020:
            value = value[:1017] + "…"
        embed.add_field(name=f"{emoji} {label}", value=value, inline=False)

    sources = []
    for r in results.values():
        s = (r or {}).get("source")
        if s and s not in sources:
            sources.append(s)
    if sources:
        embed.set_footer(text="Sources: " + " · ".join(sources))

    await ctx_or_channel.send(embed=embed)


def _parse_today_date(raw: str):
    """Return a datetime.date from raw input, or None if unparseable.
    Accepts: "" (today), YYYY-MM-DD, YYYY/MM/DD, MM-DD, MM/DD."""
    import datetime as _dt
    raw = (raw or "").strip()
    if not raw:
        return _dt.date.today()
    today = _dt.date.today()
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y.%m.%d"):
        try:
            return _dt.datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    for fmt in ("%m-%d", "%m/%d"):
        try:
            md = _dt.datetime.strptime(raw, fmt)
            return _dt.date(today.year, md.month, md.day)
        except ValueError:
            continue
    return None


def _parse_today_args(raw: str) -> tuple[str, str] | None:
    """
    Split `!today` arguments into (tradition_key, date_string).
    Either or both may be blank.

    Returns None if the tradition word is unrecognised (and was not a date).
    """
    parts = (raw or "").strip().split(None, 1)
    if not parts:
        return ("all", "")

    first = parts[0].lower()
    rest = parts[1] if len(parts) > 1 else ""

    # First token is a known tradition?
    if first in _TODAY_GROUPS:
        return (first, rest.strip())

    # First token might be a date — try to parse the whole thing as date
    if _parse_today_date(raw) is not None:
        return ("all", raw.strip())

    return None


@bot.command(name="today", aliases=["calendar", "liturgy"])
async def cmd_today(ctx, *, args: str = ""):
    """Liturgical / religious observances for a date.

    Usage:
      !today                        — today, all five traditions
      !today christian              — Catholic + Anglican + Orthodox
      !today anglican               — Anglican (Common Worship) only
      !today catholic               — Catholic (Roman Rite) only
      !today orthodox               — Orthodox only
      !today islam                  — Islamic only
      !today jewish                 — Jewish only
      !today catholic 2026-12-25    — any tradition + a specific date
    """
    parsed = _parse_today_args(args)
    if parsed is None:
        await ctx.send(
            "⚠️ Unknown tradition. Try `christian`, `anglican`, `catholic`, "
            "`orthodox`, `islam`, or `jewish` — or just `!today` for all "
            "five traditions."
        )
        return
    key, date_raw = parsed
    d = _parse_today_date(date_raw)
    if d is None:
        await ctx.send(f"⚠️ Couldn't parse `{date_raw}` as a date. Try `YYYY-MM-DD` or `MM-DD`.")
        return

    traditions = _TODAY_GROUPS[key]
    if key == "all":
        title_label = "All Traditions"
    elif key == "christian":
        title_label = "Christian"
    else:
        _, full_label = _TODAY_META.get(traditions[0], ("", key.title()))
        title_label = full_label

    async with ctx.typing():
        await _send_today(ctx, d, traditions, title_label)


@bot.tree.command(name="today", description="Today's liturgical / religious observances")
@app_commands.describe(
    tradition='Which tradition: all (default), christian, anglican, catholic, orthodox, islam, jewish',
    date='Optional date: YYYY-MM-DD or MM-DD; blank for today',
)
async def today_slash(interaction: discord.Interaction, tradition: str = "all", date: str = ""):
    await interaction.response.defer()
    key = (tradition or "all").strip().lower()
    if key not in _TODAY_GROUPS:
        await interaction.followup.send(
            "⚠️ Unknown tradition. Try `all`, `christian`, `anglican`, `catholic`, "
            "`orthodox`, `islam`, or `jewish`."
        )
        return
    d = _parse_today_date(date)
    if d is None:
        await interaction.followup.send(f"⚠️ Couldn't parse `{date}` as a date.")
        return
    traditions = _TODAY_GROUPS[key]
    if key == "all":
        title_label = "All Traditions"
    elif key == "christian":
        title_label = "Christian"
    else:
        _, full_label = _TODAY_META.get(traditions[0], ("", key.title()))
        title_label = full_label
    await _send_today(interaction.channel, d, traditions, title_label)


# ── !bcp — Book of Common Prayer daily office ────────────────────────────────

def _bcp_normalise_ref(ref: str) -> str:
    """
    Normalise lectionary refs into a form lookup.get_verse can handle.

    Examples:
        "Isa. 11:1-9"            → "Isaiah 11:1-9"
        "Rom. 8:18-end"          → "Romans 8:18-end" (handled by lookup)
        "1 Cor. 12:27-13 end"    → "1 Corinthians 12:27-13:end"
        "Eze. 11:14-20"          → "Ezekiel 11:14-20"
        "Wis. 1:1-7"             → "Wisdom 1:1-7"
        "Acts 18:24-19:7"        → "Acts 18:24-19:7"
    """
    s = ref.strip()
    # Expand common abbreviations
    expansions = [
        ("Gen.",   "Genesis"),    ("Ex.",    "Exodus"),
        ("Exod.",  "Exodus"),     ("Lev.",   "Leviticus"),
        ("Num.",   "Numbers"),    ("Deut.",  "Deuteronomy"),
        ("Josh.",  "Joshua"),     ("Judg.",  "Judges"),
        ("1 Sam.", "1 Samuel"),   ("2 Sam.", "2 Samuel"),
        ("1 Kings","1 Kings"),    ("2 Kings","2 Kings"),
        ("1 Chr.", "1 Chronicles"),("2 Chr.","2 Chronicles"),
        ("Neh.",   "Nehemiah"),   ("Esth.",  "Esther"),
        ("Ps.",    "Psalm"),      ("Prov.",  "Proverbs"),
        ("Eccl.",  "Ecclesiastes"),("Cant.", "Song of Solomon"),
        ("Isa.",   "Isaiah"),     ("Isa ",   "Isaiah "),
        ("Jer.",   "Jeremiah"),   ("Lam.",   "Lamentations"),
        ("Eze.",   "Ezekiel"),    ("Ezek.",  "Ezekiel"),
        ("Dan.",   "Daniel"),     ("Hos.",   "Hosea"),
        ("Joel ",  "Joel "),      ("Amos ",  "Amos "),
        ("Obad.",  "Obadiah"),    ("Jon.",   "Jonah"),
        ("Mic.",   "Micah"),      ("Nah.",   "Nahum"),
        ("Hab.",   "Habakkuk"),   ("Zeph.",  "Zephaniah"),
        ("Hag.",   "Haggai"),     ("Zech.",  "Zechariah"),
        ("Mal.",   "Malachi"),
        # Apocrypha
        ("Tob.",   "Tobit"),      ("Jud.",   "Judith"),
        ("Wis.",   "Wisdom"),     ("Ecclus.","Sirach"),
        ("Sir.",   "Sirach"),     ("Bar.",   "Baruch"),
        ("1 Macc.","1 Maccabees"),("2 Macc.","2 Maccabees"),
        # NT
        ("Mt.",    "Matthew"),    ("Mk.",    "Mark"),
        ("Lk.",    "Luke"),       ("Jn.",    "John"),
        ("Rom.",   "Romans"),     ("1 Cor.", "1 Corinthians"),
        ("2 Cor.", "2 Corinthians"),("Gal.",  "Galatians"),
        ("Eph.",   "Ephesians"),  ("Phil.",  "Philippians"),
        ("Col.",   "Colossians"), ("1 Thes.","1 Thessalonians"),
        ("1 Thess.","1 Thessalonians"),("2 Thess.","2 Thessalonians"),
        ("1 Tim.", "1 Timothy"),  ("2 Tim.", "2 Timothy"),
        ("Tit.",   "Titus"),      ("Philem.","Philemon"),
        ("Heb.",   "Hebrews"),    ("Jas.",   "James"),
        ("1 Pet.", "1 Peter"),    ("2 Pet.", "2 Peter"),
        ("1 Jn.",  "1 John"),     ("2 Jn.",  "2 John"),
        ("3 Jn.",  "3 John"),     ("Rev.",   "Revelation"),
    ]
    for short, long in expansions:
        if s.startswith(short):
            s = long + s[len(short):]
            break

    # Convert "X-Y end" (multi-chapter range) to "X-Y:end"
    s = re.sub(r"(\d+)\s+end\b", r"\1:end", s)
    return s


def _bcp_fetch_text(ref: str) -> tuple[str, str]:
    """
    Look up a lectionary reference and return (display_ref, text).

    Handles BCP lectionary notation that the standard `lookup.get_verse`
    doesn't:
      • "Rom. 8:18-end"      → resolve "end" to the chapter's actual last verse
      • "1 Cor. 12:27-13 end" → cross-chapter to end of chapter 13
      • "Acts 18:24-19:7"    → ordinary cross-chapter (lookup handles natively)
    """
    norm = _bcp_normalise_ref(ref)
    import re as _re

    def _last_verse(book: str, chap: int) -> int | None:
        """Return the highest verse number in (book, chap), or None if unknown."""
        try:
            corpus, canon = lookup._resolve_book(book)
            if canon is None:
                return None
            chap_data = lookup._data[corpus].get(canon, {}).get(str(chap), {})
            nums = [int(k) for k in chap_data if k.isdigit()]
            return max(nums) if nums else None
        except Exception:
            return None

    # Try "Book C:V-end"
    m = _re.match(r"^(.+?)\s+(\d+):(\d+)\s*-\s*end$", norm)
    if m:
        book = m.group(1).strip()
        c, v = int(m.group(2)), int(m.group(3))
        last = _last_verse(book, c) or 200
        try:
            result = lookup.get_verse_range(book, c, v, c, last)
            if result.get("found"):
                return result.get("reference", ref), result.get("text", "")
        except Exception:
            pass

    # Try "Book C:V-C2:end"  (multi-chapter to end of chapter)
    m = _re.match(r"^(.+?)\s+(\d+):(\d+)\s*-\s*(\d+):end$", norm)
    if m:
        book = m.group(1).strip()
        c1, v1, c2 = int(m.group(2)), int(m.group(3)), int(m.group(4))
        last = _last_verse(book, c2) or 200
        try:
            result = lookup.get_verse_range(book, c1, v1, c2, last)
            if result.get("found"):
                return result.get("reference", ref), result.get("text", "")
        except Exception:
            pass

    # Otherwise, hand off to the standard verse lookup
    try:
        result = lookup.get_verse(norm)
        if result.get("found"):
            return result.get("reference", ref), result.get("text", "")
    except Exception:
        pass

    return ref, "*[not available]*"


def _bcp_period_for_now() -> str:
    """Midnight-noon = morning, noon-midnight = evening."""
    import datetime as _dt
    now = _dt.datetime.now()
    return "morning" if now.hour < 12 else "evening"


async def _send_bcp(ctx_or_channel, target_date, period: str):
    """Build and send the BCP daily office embed(s) with pagination."""
    import bcp_lookup as _bcp

    loop = asyncio.get_event_loop()
    info = await loop.run_in_executor(None, _bcp.bcp_for_date, target_date, period)

    if not info.get("found"):
        err = info.get("error", "Lookup failed.")
        await ctx_or_channel.send(f"⚠️ BCP lookup error: {err}")
        return

    pretty_date = (
        target_date.strftime("%A, ")
        + target_date.strftime("%d").lstrip("0")
        + target_date.strftime(" %B %Y")
    )
    period_label = "Morning Prayer" if period == "morning" else "Evening Prayer"

    # ── Compose section header text ──────────────────────────────────────────
    title_bits = []
    if info.get("section_title"):
        title_bits.append(info["section_title"])
    label = info.get("label", "")
    if label and label != "Sunday":
        title_bits.append(label)
    if info.get("year"):
        title_bits.append(f"Year {info['year']}")
    section_line = " · ".join(title_bits) if title_bits else "—"

    # ── Page 1: Psalms ───────────────────────────────────────────────────────
    psalter = info.get("psalter") or {}
    portions = psalter.get("portions", [])

    # Each portion becomes one or more pages depending on length.
    psalter_pages: list[tuple[str, str]] = []
    for portion in portions:
        label = portion.get("label", "Psalm")
        incipit = portion.get("incipit", "")
        verses = portion.get("verses", [])
        if not verses:
            # Fall back to incipit-only if text is missing
            body = f"_{incipit}_" if incipit else "*[text not available]*"
            psalter_pages.append((label, body))
            continue

        # Heading line: incipit
        head = f"_{incipit}_\n\n" if incipit else ""
        # Build verse lines like "1. BLESSED is the man..."
        # The first verse number is the starting verse from the label, if specified.
        first_verse_num = 1
        if ":" in portion.get("ref", ""):
            try:
                rng = portion["ref"].split(":", 1)[1]
                first_verse_num = int(rng.split("-")[0])
            except (ValueError, IndexError):
                pass
        lines = [f"**{first_verse_num + i}.** {v}" for i, v in enumerate(verses)]

        # Paginate: Discord description cap = 4096 chars. Leave headroom for the
        # heading + page indicator metadata. Cap each page at ~3800 chars.
        chunk = head
        part = 1
        for line in lines:
            if len(chunk) + len(line) + 2 > 3800:
                title = label if part == 1 else f"{label} (cont. {part})"
                psalter_pages.append((title, chunk.rstrip()))
                chunk = ""
                part += 1
            chunk += line + "\n"
        if chunk.strip():
            title = label if part == 1 else f"{label} (cont. {part})"
            psalter_pages.append((title, chunk.rstrip()))

    # ── Pages 2 & 3: Lessons (with KJV text) ─────────────────────────────────
    lesson_pages: list[tuple[str, str]] = []  # (heading, body)
    lesson_summary: list[str] = []             # for the summary page
    for les in info.get("lessons", []):
        display_ref, text = await loop.run_in_executor(
            None, _bcp_fetch_text, les["ref"]
        )
        heading = f"{les['slot']} — {display_ref}"
        lesson_summary.append(f"• **{les['slot']}** — {display_ref}")
        body = text or "*[not available]*"
        # If body is too long for one embed description (~4000 chars), split.
        if len(body) <= 3900:
            lesson_pages.append((heading, body))
        else:
            # Split on sentence boundaries
            remaining = body
            part = 1
            while remaining:
                if len(remaining) <= 3900:
                    lesson_pages.append((
                        f"{heading} ({'part ' + str(part) if part > 1 else 'cont.'})" if part > 1 else heading,
                        remaining
                    ))
                    break
                window = remaining[:3900]
                cut = window.rfind(". ")
                if cut < 1000:
                    cut = window.rfind(" ")
                if cut <= 0:
                    cut = 3900
                lesson_pages.append((
                    f"{heading} ({'part ' + str(part)})" if part > 1 else heading,
                    remaining[:cut + 1].strip()
                ))
                remaining = remaining[cut + 1:].lstrip()
                part += 1

    # ── Final page: Collect of the Day ───────────────────────────────────────
    collect_info = info.get("collect")

    # ── Build all pages as (title, body) tuples ──────────────────────────────
    pages: list[tuple[str, str]] = []

    # Page 1: header (section info) — short summary page so the psalms get
    # their own dedicated pages with full text.
    p1_sections = [f"_{section_line}_", ""]
    p1_sections.append(f"**The Psalms appointed for this {period_label}**")
    if portions:
        p1_sections.extend(f"• {p['label']}" for p in portions)
    else:
        p1_sections.append("*No psalms appointed.*")
    if lesson_summary:
        p1_sections.append("")
        p1_sections.append("**The Lessons**")
        # Each lesson on its own line, with a blank between
        for i, line in enumerate(lesson_summary):
            if i > 0:
                p1_sections.append("")
            p1_sections.append(line)
    if collect_info:
        p1_sections.append("")
        c_name = collect_info.get("name", "Collect")
        if collect_info.get("is_saint_day"):
            p1_sections.append(f"**The Collect:** {c_name}")
        else:
            p1_sections.append(f"**The Collect:** {c_name}")
    p1_body = "\n".join(p1_sections)
    pages.append(("BCP Daily Office", p1_body))

    # Psalm-text pages
    for heading, body in psalter_pages:
        pages.append((heading, body))

    # Lessons pages
    for heading, body in lesson_pages:
        pages.append((heading, body))

    # Collect page
    if collect_info:
        collect_name = collect_info.get("name", "Collect")
        collect_text = collect_info.get("collect", "")
        if collect_info.get("is_saint_day"):
            collect_heading = f"The Collect for {collect_name}"
        else:
            collect_heading = f"The Collect: {collect_name}"
        if collect_text:
            pages.append((collect_heading, collect_text))

    if not pages:
        await ctx_or_channel.send("⚠️ Nothing to display.")
        return

    def build_embed(idx: int) -> discord.Embed:
        heading, body = pages[idx]
        e = discord.Embed(
            title=f"📖 {pretty_date} — {period_label}",
            description=body,
            color=discord.Color.dark_blue(),
        )
        # Page indicator + collect note
        footer_bits = [f"Page {idx + 1}/{len(pages)}"]
        footer_bits.append(heading)
        if info.get("section_key"):
            footer_bits.append(f"({info['section_key']}/{info.get('label','')})")
        e.set_footer(text=" · ".join(footer_bits))
        return e

    if len(pages) <= 1:
        await ctx_or_channel.send(embed=build_embed(0))
        return

    class BcpView(discord.ui.View):
        def __init__(self):
            super().__init__(timeout=300)
            self.idx = 0
            self.message: discord.Message | None = None

        @discord.ui.button(emoji="◀", style=discord.ButtonStyle.secondary)
        async def prev(self, interaction: discord.Interaction, button: discord.ui.Button):
            self.idx = (self.idx - 1) % len(pages)
            await interaction.response.edit_message(embed=build_embed(self.idx), view=self)

        @discord.ui.button(emoji="▶", style=discord.ButtonStyle.secondary)
        async def next(self, interaction: discord.Interaction, button: discord.ui.Button):
            self.idx = (self.idx + 1) % len(pages)
            await interaction.response.edit_message(embed=build_embed(self.idx), view=self)

        async def on_timeout(self):
            try:
                if self.message is not None:
                    await self.message.edit(view=None)
            except Exception:
                pass

    view = BcpView()
    msg = await ctx_or_channel.send(embed=build_embed(0), view=view)
    view.message = msg


# ── Subcommand helpers (single-purpose senders) ──────────────────────────────

async def _send_bcp_psalm(ctx_or_channel, target_date, period: str):
    """Send only the Psalm(s) appointed for the given date and period."""
    import bcp_lookup as _bcp
    loop = asyncio.get_event_loop()
    info = await loop.run_in_executor(None, _bcp.bcp_for_date, target_date, period)
    if not info.get("found") or not info.get("psalter"):
        await ctx_or_channel.send("⚠️ Could not look up the Psalter for that date.")
        return

    pretty_date = (target_date.strftime("%A, ")
                   + target_date.strftime("%d").lstrip("0")
                   + target_date.strftime(" %B %Y"))
    period_label = "Morning Prayer" if period == "morning" else "Evening Prayer"
    portions = info["psalter"].get("portions", [])

    # Build pages exactly like the full office's Psalm pages
    psalter_pages: list[tuple[str, str]] = []
    for portion in portions:
        label = portion.get("label", "Psalm")
        incipit = portion.get("incipit", "")
        verses = portion.get("verses", [])
        if not verses:
            body = f"_{incipit}_" if incipit else "*[text not available]*"
            psalter_pages.append((label, body))
            continue
        head = f"_{incipit}_\n\n" if incipit else ""
        first_verse_num = 1
        if ":" in portion.get("ref", ""):
            try:
                rng = portion["ref"].split(":", 1)[1]
                first_verse_num = int(rng.split("-")[0])
            except (ValueError, IndexError):
                pass
        lines = [f"**{first_verse_num + i}.** {v}" for i, v in enumerate(verses)]
        chunk = head
        part = 1
        for line in lines:
            if len(chunk) + len(line) + 2 > 3800:
                title = label if part == 1 else f"{label} (cont. {part})"
                psalter_pages.append((title, chunk.rstrip()))
                chunk = ""
                part += 1
            chunk += line + "\n"
        if chunk.strip():
            title = label if part == 1 else f"{label} (cont. {part})"
            psalter_pages.append((title, chunk.rstrip()))

    if not psalter_pages:
        await ctx_or_channel.send("⚠️ No psalms appointed.")
        return

    def build_embed(idx):
        heading, body = psalter_pages[idx]
        e = discord.Embed(
            title=f"📖 {pretty_date} — {period_label}: Psalms",
            description=body,
            color=discord.Color.dark_blue(),
        )
        e.set_footer(text=f"Page {idx + 1}/{len(psalter_pages)} · {heading}")
        return e

    if len(psalter_pages) == 1:
        await ctx_or_channel.send(embed=build_embed(0))
        return

    class PsalmView(discord.ui.View):
        def __init__(self):
            super().__init__(timeout=300)
            self.idx = 0
            self.message = None
        @discord.ui.button(emoji="◀", style=discord.ButtonStyle.secondary)
        async def prev(self, interaction, button):
            self.idx = (self.idx - 1) % len(psalter_pages)
            await interaction.response.edit_message(embed=build_embed(self.idx), view=self)
        @discord.ui.button(emoji="▶", style=discord.ButtonStyle.secondary)
        async def next(self, interaction, button):
            self.idx = (self.idx + 1) % len(psalter_pages)
            await interaction.response.edit_message(embed=build_embed(self.idx), view=self)
        async def on_timeout(self):
            try:
                if self.message: await self.message.edit(view=None)
            except Exception: pass
    view = PsalmView()
    msg = await ctx_or_channel.send(embed=build_embed(0), view=view)
    view.message = msg


async def _send_bcp_lessons(ctx_or_channel, target_date, period: str,
                            which: str = "both"):
    """Send the lesson(s). which = 'first' | 'second' | 'both'."""
    import bcp_lookup as _bcp
    loop = asyncio.get_event_loop()
    info = await loop.run_in_executor(None, _bcp.bcp_for_date, target_date, period)
    if not info.get("found"):
        await ctx_or_channel.send(f"⚠️ Could not resolve lessons for {target_date}.")
        return

    pretty_date = (target_date.strftime("%A, ")
                   + target_date.strftime("%d").lstrip("0")
                   + target_date.strftime(" %B %Y"))
    period_label = "Morning Prayer" if period == "morning" else "Evening Prayer"

    lessons = info.get("lessons", [])
    if which == "first":
        lessons = lessons[:1]
    elif which == "second":
        lessons = lessons[1:2]
    if not lessons:
        await ctx_or_channel.send("⚠️ No lessons appointed.")
        return

    pages: list[tuple[str, str]] = []
    for les in lessons:
        display_ref, text = await loop.run_in_executor(None, _bcp_fetch_text, les["ref"])
        heading = f"{les['slot']} — {display_ref}"
        body = text or "*[not available]*"
        if len(body) <= 3900:
            pages.append((heading, body))
        else:
            remaining = body
            part = 1
            while remaining:
                if len(remaining) <= 3900:
                    pages.append((
                        f"{heading} (part {part})" if part > 1 else heading,
                        remaining
                    ))
                    break
                window = remaining[:3900]
                cut = window.rfind(". ")
                if cut < 1000:
                    cut = window.rfind(" ")
                if cut <= 0:
                    cut = 3900
                pages.append((
                    f"{heading} (part {part})" if part > 1 else heading,
                    remaining[:cut + 1].strip()
                ))
                remaining = remaining[cut + 1:].lstrip()
                part += 1

    def build_embed(idx):
        heading, body = pages[idx]
        e = discord.Embed(
            title=f"📖 {pretty_date} — {period_label}",
            description=body,
            color=discord.Color.dark_blue(),
        )
        e.set_footer(text=f"Page {idx + 1}/{len(pages)} · {heading}")
        return e

    if len(pages) == 1:
        await ctx_or_channel.send(embed=build_embed(0))
        return

    class LessonView(discord.ui.View):
        def __init__(self):
            super().__init__(timeout=300)
            self.idx = 0
            self.message = None
        @discord.ui.button(emoji="◀", style=discord.ButtonStyle.secondary)
        async def prev(self, interaction, button):
            self.idx = (self.idx - 1) % len(pages)
            await interaction.response.edit_message(embed=build_embed(self.idx), view=self)
        @discord.ui.button(emoji="▶", style=discord.ButtonStyle.secondary)
        async def next(self, interaction, button):
            self.idx = (self.idx + 1) % len(pages)
            await interaction.response.edit_message(embed=build_embed(self.idx), view=self)
        async def on_timeout(self):
            try:
                if self.message: await self.message.edit(view=None)
            except Exception: pass
    view = LessonView()
    msg = await ctx_or_channel.send(embed=build_embed(0), view=view)
    view.message = msg


async def _send_bcp_collect(ctx_or_channel, target_date):
    """Send only the Collect of the Day for the given date."""
    import bcp_lookup as _bcp
    loop = asyncio.get_event_loop()
    # Period doesn't matter for the collect itself, but the resolver needs one.
    info = await loop.run_in_executor(None, _bcp.bcp_for_date, target_date, "morning")
    if not info.get("found"):
        await ctx_or_channel.send(f"⚠️ Could not resolve a collect for {target_date}.")
        return
    collect = info.get("collect")
    if not collect or not collect.get("collect"):
        await ctx_or_channel.send(f"⚠️ No collect found for {target_date}.")
        return

    pretty_date = (target_date.strftime("%A, ")
                   + target_date.strftime("%d").lstrip("0")
                   + target_date.strftime(" %B %Y"))
    name = collect.get("name", "Collect")
    if collect.get("is_saint_day"):
        title = f"📿 The Collect for {name}"
    else:
        title = f"📿 The Collect: {name}"

    embed = discord.Embed(
        title=title,
        description=collect["collect"],
        color=discord.Color.dark_purple(),
    )
    embed.set_footer(text=f"{pretty_date} · Book of Common Prayer 1662")
    await ctx_or_channel.send(embed=embed)


# ── !prayer — random devotional prayer from the BCP ──────────────────────────

_PRAYERS_DATA: dict | None = None

def _load_prayers() -> dict | None:
    global _PRAYERS_DATA
    if _PRAYERS_DATA is not None:
        return _PRAYERS_DATA
    from pathlib import Path as _P
    for p in [_P(__file__).parent / "data" / "bcp_prayers.json",
              _P("data") / "bcp_prayers.json"]:
        if p.exists():
            try:
                _PRAYERS_DATA = json.loads(p.read_text(encoding="utf-8"))
                return _PRAYERS_DATA
            except Exception:
                continue
    return None


async def _send_random_prayer(ctx_or_channel):
    data = _load_prayers()
    if not data or not data.get("prayers"):
        await ctx_or_channel.send("⚠️ Prayer data not loaded.")
        return
    prayer = random.choice(data["prayers"])
    embed = discord.Embed(
        title=f"📿 {prayer['title']}",
        description=prayer["text"],
        color=discord.Color.dark_purple(),
    )
    sec = prayer.get("section", "")
    footer = "Book of Common Prayer 1662"
    if sec and sec not in prayer["title"]:
        footer = f"{sec} · {footer}"
    embed.set_footer(text=footer)
    await ctx_or_channel.send(embed=embed)


# ── !bcp dispatcher and alias commands ───────────────────────────────────────

def _bcp_parse_period(tok: str) -> str | None:
    """Map a period token to 'morning'/'evening' or None if unrecognised."""
    t = tok.lower()
    if t in ("morning", "mp", "matins"):
        return "morning"
    if t in ("evening", "ep", "vespers", "evensong"):
        return "evening"
    return None


@bot.command(name="bcp")
async def cmd_bcp(ctx, *, args: str = ""):
    """BCP daily office (Canadian 1962 lectionary + Coverdale Psalter).

    Usage:
      !bcp                — full office for today, time-appropriate
      !bcp morning        — full Morning Prayer office (alias: mp/matins)
      !bcp evening        — full Evening Prayer office (alias: ep/vespers)
      !bcp 2026-12-25     — full office for a specific date
      !bcp mp             — both lessons for Morning Prayer (alias: !mp)
      !bcp ep             — both lessons for Evening Prayer (alias: !ep)
      !bcp 1 / !bcp 2     — first or second lesson, time-appropriate
      !bcp psalm          — psalm(s) for the current period (alias: !psalm)
      !bcp psalm mp/ep    — psalm(s) for that period
      !bcp collect        — the Collect of the Day (alias: !collect)
      !bcp prayer         — random devotional prayer (alias: !prayer)
    """
    parts = args.strip().split()
    if not parts:
        # Full office, current period
        d = _parse_today_date("")
        async with ctx.typing():
            await _send_bcp(ctx, d, _bcp_period_for_now())
        return

    sub = parts[0].lower()
    rest = parts[1:]

    # !bcp prayer
    if sub == "prayer":
        async with ctx.typing():
            await _send_random_prayer(ctx)
        return

    # !bcp collect [date]
    if sub == "collect":
        date_raw = " ".join(rest)
        d = _parse_today_date(date_raw)
        if d is None:
            await ctx.send(f"⚠️ Couldn't parse `{date_raw}` as a date.")
            return
        async with ctx.typing():
            await _send_bcp_collect(ctx, d)
        return

    # !bcp 1 / !bcp 2  — single lesson, current period
    if sub in ("1", "first"):
        date_raw = " ".join(rest)
        d = _parse_today_date(date_raw)
        if d is None:
            await ctx.send(f"⚠️ Couldn't parse `{date_raw}`.")
            return
        async with ctx.typing():
            await _send_bcp_lessons(ctx, d, _bcp_period_for_now(), "first")
        return
    if sub in ("2", "second"):
        date_raw = " ".join(rest)
        d = _parse_today_date(date_raw)
        if d is None:
            await ctx.send(f"⚠️ Couldn't parse `{date_raw}`.")
            return
        async with ctx.typing():
            await _send_bcp_lessons(ctx, d, _bcp_period_for_now(), "second")
        return

    # !bcp psalm [mp|ep] [date]
    if sub in ("psalm", "psalms", "psalter"):
        period = _bcp_period_for_now()
        date_raw = ""
        if rest:
            maybe_period = _bcp_parse_period(rest[0])
            if maybe_period is not None:
                period = maybe_period
                date_raw = " ".join(rest[1:])
            else:
                date_raw = " ".join(rest)
        d = _parse_today_date(date_raw)
        if d is None:
            await ctx.send(f"⚠️ Couldn't parse `{date_raw}`.")
            return
        async with ctx.typing():
            await _send_bcp_psalm(ctx, d, period)
        return

    # !bcp mp / !bcp ep  — both lessons for that period
    period_only = _bcp_parse_period(sub)
    if period_only is not None and (not rest or _parse_today_date(" ".join(rest)) is not None):
        # If a date follows, parse it; otherwise today
        date_raw = " ".join(rest)
        d = _parse_today_date(date_raw)
        if d is None:
            await ctx.send(f"⚠️ Couldn't parse `{date_raw}`.")
            return
        # If they said "mp" or "ep" specifically (short form), give just the lessons;
        # if they said "morning"/"evening", give the full office.
        if sub in ("mp", "ep"):
            async with ctx.typing():
                await _send_bcp_lessons(ctx, d, period_only, "both")
        else:
            async with ctx.typing():
                await _send_bcp(ctx, d, period_only)
        return

    # Fallback: treat the whole arg as a date for the full office
    date_raw = args.strip()
    d = _parse_today_date(date_raw)
    if d is None:
        await ctx.send(f"⚠️ Unknown subcommand `{sub}`. See `!help bcp`.")
        return
    async with ctx.typing():
        await _send_bcp(ctx, d, _bcp_period_for_now())


@bot.tree.command(name="bcp", description="BCP daily office: psalms, lessons, and collect")
@app_commands.describe(
    period='"morning" or "evening" (defaults to time of day)',
    date='Optional date: YYYY-MM-DD or MM-DD; blank for today',
)
async def bcp_slash(interaction: discord.Interaction, period: str = "", date: str = ""):
    await interaction.response.defer()
    p = _bcp_parse_period(period) if period else None
    if p is None:
        p = _bcp_period_for_now()
    d = _parse_today_date(date)
    if d is None:
        await interaction.followup.send(f"⚠️ Couldn't parse `{date}`.")
        return
    await _send_bcp(interaction.channel, d, p)


# ── Alias commands ───────────────────────────────────────────────────────────

@bot.command(name="prayer")
async def cmd_prayer(ctx):
    """Random devotional prayer or collect from the BCP."""
    async with ctx.typing():
        await _send_random_prayer(ctx)


@bot.command(name="collect")
async def cmd_collect(ctx, *, date_raw: str = ""):
    """The Collect of the Day. Optional date arg."""
    d = _parse_today_date(date_raw)
    if d is None:
        await ctx.send(f"⚠️ Couldn't parse `{date_raw}`.")
        return
    async with ctx.typing():
        await _send_bcp_collect(ctx, d)


@bot.command(name="mp", aliases=["matins"])
async def cmd_mp(ctx, *, date_raw: str = ""):
    """Both lessons for today's Morning Prayer."""
    d = _parse_today_date(date_raw)
    if d is None:
        await ctx.send(f"⚠️ Couldn't parse `{date_raw}`.")
        return
    async with ctx.typing():
        await _send_bcp_lessons(ctx, d, "morning", "both")


@bot.command(name="ep", aliases=["evensong", "vespers"])
async def cmd_ep(ctx, *, date_raw: str = ""):
    """Both lessons for today's Evening Prayer."""
    d = _parse_today_date(date_raw)
    if d is None:
        await ctx.send(f"⚠️ Couldn't parse `{date_raw}`.")
        return
    async with ctx.typing():
        await _send_bcp_lessons(ctx, d, "evening", "both")


@bot.command(name="psalm", aliases=["psalms"])
async def cmd_psalm(ctx, *, args: str = ""):
    """Today's appointed Psalm(s). Optional `mp`/`ep` to override the period.

    Usage:
      !psalm           — current period
      !psalm mp        — Morning Prayer psalms
      !psalm ep        — Evening Prayer psalms
      !psalm mp 12-25  — Morning Prayer psalms for Dec 25
    """
    parts = args.strip().split()
    period = _bcp_period_for_now()
    date_raw = ""
    if parts:
        maybe_period = _bcp_parse_period(parts[0])
        if maybe_period is not None:
            period = maybe_period
            date_raw = " ".join(parts[1:])
        else:
            date_raw = args.strip()
    d = _parse_today_date(date_raw)
    if d is None:
        await ctx.send(f"⚠️ Couldn't parse `{date_raw}`.")
        return
    async with ctx.typing():
        await _send_bcp_psalm(ctx, d, period)


async def _send_votd_full(ctx_or_channel):
    """
    Combined Verse of the Day display:
      • KJV verse text
      • Ancient translations (excluding OE and CSL)
      • First patristic commentary from catenabible.com

    Used by `!votd full` and by the daily midnight task.
    """
    from poem_lookup import classify_scripture

    # ── 1. Get today's reference ──────────────────────────────────────────────
    reference, date_text = _scrape_votd()
    used_fallback = False
    if reference is None:
        reference = random.choice(_VOTD_FALLBACKS)
        log.info(f"RNG  VOTD fallback          → {reference}")
        used_fallback = True

    # Strip verse range (e.g. "John 3:16-18" → "John 3:16") for single-verse work
    ref_single = re.sub(r"\s*[-–]\s*\d+$", "", reference)

    # ── 2. KJV verse text ─────────────────────────────────────────────────────
    kjv_result = lookup.get_verse(ref_single)
    if not kjv_result.get("found"):
        kjv_result = lookup.get_verse(reference)

    if not kjv_result.get("found"):
        msg = f"⚠️ Today's verse is **{reference}** but couldn't be retrieved."
        await ctx_or_channel.send(msg)
        return

    display_ref = kjv_result.get("reference", reference)
    kjv_text = kjv_result["text"]

    # ── 3. Ancient translations (skip OE and CSL per spec) ────────────────────
    scripture_type = classify_scripture(ref_single)
    if scripture_type == "nt":
        ancient_slugs = ["TR", "VULG", "PESHITTA"]
    elif scripture_type == "apocrypha":
        ancient_slugs = ["LXX", "VULG", "PESHITTA"]
    else:
        ancient_slugs = ["WLC", "LXX", "VULG", "PESHITTA"]

    ancient_display_overrides = {
        "WLC":      "Hebrew OT (Westminster Leningrad Codex)",
        "PESHITTA": "Peshitta (Classical Syriac/Aramaic)",
        "LXX":      "Septuagint (Greek OT)",
        "TR":       "Textus Receptus (Greek NT, Elzevir 1624)",
        "VULG":     "Vulgata Clementina (Latin)",
    }

    ancient_results = []
    for i, slug in enumerate(ancient_slugs):
        if i > 0:
            await asyncio.sleep(0.3)
        slug_out, display_out, text_out = await _fetch_one_translation(slug, ref_single)
        if text_out in ("*Not found*", "*Not available*"):
            continue
        display_out = ancient_display_overrides.get(slug_out, display_out)
        ancient_results.append((slug_out, display_out, text_out))

    # ── 4. First catena commentary ────────────────────────────────────────────
    catena_data = _fetch_catena_sections(ref_single)
    catena_section = None    # (father_name, body)
    catena_url = None
    if not catena_data.get("error_send"):
        catena_url = catena_data.get("url")
        secs = catena_data.get("sections") or []
        if secs:
            catena_section = secs[0]

    # ── 5. Build the combined embed ───────────────────────────────────────────
    embed = discord.Embed(
        title=f"📖 {display_ref} — Verse of the Day",
        description=f"**KJV — King James Version (1769)**\n{kjv_text}",
        color=discord.Color.blue(),
        url=None if used_fallback else "https://www.verseoftheday.com/",
    )

    for slug, display, text in ancient_results:
        # Discord field value cap is 1024 chars
        if len(text) > 1020:
            text = text[:1017] + "…"
        embed.add_field(name=f"**{slug}** — {display}", value=text, inline=False)

    if catena_section is not None:
        father, body = catena_section
        # Trim to fit in one field
        if len(body) > 1020:
            trunc = body[:1017]
            last_period = trunc.rfind(". ")
            body = (trunc[:last_period + 1] if last_period > 200 else trunc) + " …"
        embed.add_field(
            name=f"📜 Commentary — {father}",
            value=body,
            inline=False,
        )

    footer_parts = []
    if used_fallback:
        footer_parts.append("⚠️ verseoftheday.com unavailable — showing a classic verse")
    elif date_text:
        footer_parts.append(f"Verse of the Day — {date_text}")
    if catena_url:
        footer_parts.append("Commentary: catenabible.com")
    embed.set_footer(text=" | ".join(footer_parts) if footer_parts else "Verse of the Day")

    await ctx_or_channel.send(embed=embed)


async def _send_votd_extended(ctx_or_channel):
    """
    Extended Verse of the Day: the full VOTD embed followed immediately by
    the !today calendar embed for all five traditions.

    Used by `!votd extended` and by the daily midnight task when its mode
    is set to "extended".
    """
    import datetime as _dt
    # First, send the full VOTD (KJV + ancients + first commentary)
    await _send_votd_full(ctx_or_channel)
    # Then, send today's calendar across all five traditions
    traditions = _TODAY_GROUPS["all"]
    await _send_today(ctx_or_channel, _dt.date.today(), traditions, "All Traditions")


# ── !catena — Patristic commentary from catenabible.com ──────────────────────

# Book name → catenabible.com URL abbreviation
_CATENA_BOOKS = {
    # OT
    "genesis": "gn", "gen": "gn",
    "exodus": "ex", "exod": "ex",
    "leviticus": "lv", "lev": "lv",
    "numbers": "nm", "num": "nm",
    "deuteronomy": "dt", "deut": "dt",
    "joshua": "jo", "josh": "jo",
    "judges": "jg", "judg": "jg",
    "ruth": "rt",
    "1 samuel": "1sm", "1sam": "1sm",
    "2 samuel": "2sm", "2sam": "2sm",
    "1 kings": "1kgs", "1kgs": "1kgs",
    "2 kings": "2kgs", "2kgs": "2kgs",
    "1 chronicles": "1chr", "1chr": "1chr",
    "2 chronicles": "2chr", "2chr": "2chr",
    "ezra": "ezr",
    "nehemiah": "ne", "neh": "ne",
    "tobit": "tb", "tob": "tb",
    "judith": "jdt",
    "esther": "est",
    "1 maccabees": "1mc", "1macc": "1mc",
    "2 maccabees": "2mc", "2macc": "2mc",
    "job": "jb",
    "psalms": "ps", "psalm": "ps",
    "proverbs": "prv", "prov": "prv",
    "ecclesiastes": "eccl", "qoheleth": "eccl",
    "song of songs": "sg", "song of solomon": "sg", "song": "sg",
    "wisdom": "wis", "wisdom of solomon": "wis",
    "sirach": "si", "ecclesiasticus": "si",
    "isaiah": "is", "isa": "is",
    "jeremiah": "jer",
    "lamentations": "lam",
    "baruch": "bar",
    "ezekiel": "ez", "ezek": "ez",
    "daniel": "dn", "dan": "dn",
    "hosea": "hos",
    "joel": "jl",
    "amos": "am",
    "obadiah": "ob",
    "jonah": "jon",
    "micah": "mi",
    "nahum": "na",
    "habakkuk": "hb", "hab": "hb",
    "zephaniah": "zep",
    "haggai": "hg",
    "zechariah": "zec",
    "malachi": "mal",
    # NT
    "matthew": "mt", "matt": "mt",
    "mark": "mk",
    "luke": "lk",
    "john": "jn",
    "acts": "ac", "acts of the apostles": "ac",
    "romans": "rom",
    "1 corinthians": "1cor", "1cor": "1cor",
    "2 corinthians": "2cor", "2cor": "2cor",
    "galatians": "gal",
    "ephesians": "eph",
    "philippians": "phil",
    "colossians": "col",
    "1 thessalonians": "1thes", "1thess": "1thes",
    "2 thessalonians": "2thes", "2thess": "2thes",
    "1 timothy": "1tm", "1tim": "1tm",
    "2 timothy": "2tm", "2tim": "2tm",
    "titus": "ti",
    "philemon": "phm",
    "hebrews": "heb",
    "james": "jas",
    "1 peter": "1pt", "1pet": "1pt",
    "2 peter": "2pt", "2pet": "2pt",
    "1 john": "1jn",
    "2 john": "2jn",
    "3 john": "3jn",
    "jude": "jude",
    "revelation": "rv", "rev": "rv", "apocalypse": "rv",
}

def _catena_book_abbr(book_raw: str) -> str | None:
    """Return the catenabible.com URL abbreviation for a book name."""
    key = book_raw.strip().lower()
    if key in _CATENA_BOOKS:
        return _CATENA_BOOKS[key]
    # Try stripping leading digit+space for numbered books
    for k, v in _CATENA_BOOKS.items():
        if key == k:
            return v
    return None


def _fetch_catena_sections(reference: str) -> dict:
    """
    Pure helper: fetch and parse catenabible.com commentary for a verse.

    Returns a dict with one of:
      {"error_send": "...user-friendly error message..."}   on failure
      {"sections": [(name, body), ...], "url": str,
       "book_raw": str, "chapter": str, "verse": str}       on success
    """
    import urllib.request
    import urllib.error
    import html as html_mod

    # Strip verse range if user passed one (e.g. "John 3:16-18" → "John 3:16")
    reference = re.sub(r"(\d+:\d+)[-–]\d+$", r"\1", reference.strip())

    # Parse "Book Chapter:Verse"
    m = re.match(
        r"^((?:\d\s*)?[A-Za-z][a-zA-Z\s]+?)\s+(\d+):(\d+)$",
        reference.strip()
    )
    if not m:
        return {"error_send": f"⚠️ Couldn't parse `{reference}`. Try: `!catena John 3:16`"}

    book_raw, chapter, verse = m.group(1).strip(), m.group(2), m.group(3)
    abbr = _catena_book_abbr(book_raw)
    if abbr is None:
        return {"error_send": f"⚠️ Book `{book_raw}` not found on catenabible.com."}

    url = f"https://catenabible.com/{abbr}/{chapter}/{verse}"

    try:
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml",
                "Accept-Language": "en-US,en;q=0.9",
            }
        )
        with urllib.request.urlopen(req, timeout=15) as r:
            raw = r.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        return {"error_send": f"⚠️ catenabible.com returned HTTP {e.code} for `{reference}`.\nVisit: <{url}>"}
    except Exception as e:
        return {"error_send": f"⚠️ Could not reach catenabible.com: {e}"}

    # ── Parse commentary sections ─────────────────────────────────────────────
    text = html_mod.unescape(re.sub(r"<[^>]+>", " ", raw))
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()

    # Trim the page footer (recurring nav links) BEFORE other cutoffs,
    # since these appear at the very end of the page and would otherwise leak
    # into the last commentary's body. Markers must be specific enough not to
    # match words that legitimately appear inside commentary text.
    for footer_cut in [
        "About Privacy Policy Donate",
        "About\nPrivacy Policy\nDonate",
    ]:
        idx = text.find(footer_cut)
        if idx != -1:
            text = text[:idx].strip()

    for cutoff in ["All Commentaries on", "Knowing this first", "Go To "]:
        idx = text.find(cutoff)
        if idx != -1:
            text = text[:idx].strip()

    # Start at first "Name AD YYYY" — skips the nav dump
    ad_match = re.search(r"\b[A-Z][a-zA-Z ]+AD \d{3,4}", text)
    if ad_match:
        text = text[ad_match.start():]

    text = re.sub(r"chevron-(?:left|right)", "", text)
    text = re.sub(r"Verse \d+\s+Read Chapter \d+\s+Verse \d+", "", text)
    text = re.sub(r"\d+ min\s+\d+ / \d+\s+Go to Commentary", "", text)
    text = re.sub(r"Read Chapter \d+", "", text)

    entries = re.split(r"\n*([A-Z][a-zA-Z ]+AD \d{3,4})\n*", text)
    sections = []
    i = 1
    while i < len(entries) - 1:
        name = entries[i].strip()
        body = re.sub(r"\s*\d+ min\s*\d* ?/? ?\d*\s*Go to Commentary\s*", "", entries[i + 1]).strip()
        if body and len(body) > 20:
            sections.append((name, body))
        i += 2

    return {
        "sections": sections,
        "url": url,
        "book_raw": book_raw,
        "chapter": chapter,
        "verse": verse,
    }


@bot.command(name="catena")
async def cmd_catena(ctx, *, reference: str = ""):
    """Fetch patristic commentary from catenabible.com. Usage: !catena John 3:16"""
    import urllib.request
    import html as html_mod

    # If no reference given, use today's Verse of the Day reference
    if not reference:
        ref_raw, _ = _scrape_votd()
        if ref_raw is None:
            await ctx.send("⚠️ Could not fetch today's verse reference. Try: `!catena John 3:16`")
            return
        reference = re.sub(r"\s*[-–]\s*\d+$", "", ref_raw.strip())

    async with ctx.typing():
        result = _fetch_catena_sections(reference)

    if result.get("error_send"):
        await ctx.send(result["error_send"])
        return

    sections = result["sections"]
    url = result["url"]
    book_raw = result["book_raw"]
    chapter = result["chapter"]
    verse = result["verse"]

    if not sections:
        await ctx.send(f"⚠️ No commentary found for **{book_raw} {chapter}:{verse}**.\nVisit: <{url}>")
        return

    # ── Get KJV verse text ────────────────────────────────────────────────────
    ref_label = f"{book_raw.title()} {chapter}:{verse}"
    kjv_result = lookup.get_verse(f"{book_raw} {chapter}:{verse}")
    kjv_text = f"*{kjv_result['text']}*\n\n" if kjv_result.get("found") else ""

    # ── Build paginated view ──────────────────────────────────────────────────
    def make_embed(idx: int) -> discord.Embed:
        name, body = sections[idx]
        # Truncate body at sentence boundary if very long
        if len(body) > 3200 - len(kjv_text):
            limit = 3200 - len(kjv_text)
            trunc = body[:limit]
            last_period = trunc.rfind(". ")
            body = (trunc[:last_period + 1] if last_period > 200 else trunc) + " …"

        embed = discord.Embed(
            title=f"📜 {ref_label} — {name}",
            description=kjv_text + body,
            color=discord.Color.dark_gold(),
            url=url
        )
        embed.set_footer(text=f"Commentary {idx + 1} of {len(sections)} — catenabible.com")
        return embed

    class CatenaView(discord.ui.View):
        def __init__(self):
            super().__init__(timeout=120)
            self.idx = 0

        @discord.ui.button(emoji="◀", style=discord.ButtonStyle.secondary)
        async def prev(self, interaction: discord.Interaction, button: discord.ui.Button):
            self.idx = (self.idx - 1) % len(sections)
            await interaction.response.edit_message(embed=make_embed(self.idx), view=self)

        @discord.ui.button(emoji="▶", style=discord.ButtonStyle.secondary)
        async def next(self, interaction: discord.Interaction, button: discord.ui.Button):
            self.idx = (self.idx + 1) % len(sections)
            await interaction.response.edit_message(embed=make_embed(self.idx), view=self)

        async def on_timeout(self):
            # Remove buttons when the view expires
            try:
                await self.message.edit(view=None)
            except Exception:
                pass

    view = CatenaView()
    msg = await ctx.send(embed=make_embed(0), view=view)
    view.message = msg


# ── !gematria — Gematria lookup via gematrix.org ─────────────────────────────

_gematria_cooldowns: dict[int, list] = {}  # user_id → [timestamps]

@bot.command(name="gematria", aliases=["gem", "gematrix"])
async def cmd_gematria(ctx, *, query: str = ""):
    """Look up gematria values. Usage: !gematria love  or  !gematria 666"""
    import urllib.request, urllib.parse
    import html as html_mod

    if not query:
        await ctx.send("Usage: `!gematria <word or phrase or number>`")
        return

    encoded = urllib.parse.quote_plus(query.strip())
    url = f"https://www.gematrix.org/?word={encoded}"

    async with ctx.typing():
        try:
            req = urllib.request.Request(
                url,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                    "Accept": "text/html",
                }
            )
            with urllib.request.urlopen(req, timeout=15) as r:
                raw = r.read().decode("utf-8")
        except Exception as e:
            await ctx.send(f"⚠️ Could not reach gematrix.org: {e}")
            return

    # ── Parse the results table ───────────────────────────────────────────────
    # Each row: word | jewish | english | simple | searches
    row_re = re.compile(
        r'<tr[^>]*>.*?'
        r'<td[^>]*><a[^>]*>([^<]+)</a></td>'   # word
        r'\s*<td[^>]*><a[^>]*>(\d+)</a></td>'  # jewish
        r'\s*<td[^>]*><a[^>]*>(\d+)</a></td>'  # english
        r'\s*<td[^>]*><a[^>]*>(\d+)</a></td>'  # simple
        r'\s*<td[^>]*>(\d+)</td>',              # searches (ignored)
        re.DOTALL
    )
    rows = row_re.findall(raw)

    # Fallback: find computed values for the phrase itself
    computed = {}
    for cipher in ["Jewish", "English", "Simple"]:
        vm = re.search(rf'in {cipher} Gematria equals (\d+)', raw, re.IGNORECASE)
        if vm:
            computed[cipher.lower()] = vm.group(1)

    if not rows and not computed:
        await ctx.send(f"⚠️ No gematria results found for **{query}**.\nTry: <{url}>")
        return

    # ── Format as compact list ────────────────────────────────────────────────
    label = query.strip()

    def fmt_row(word, jewish, english, simple):
        values = f"{jewish:<8} {english:<8} {simple}"
        if len(word) <= 32:
            return f"{word:<32} {values}"
        else:
            return f"{word}\n{'':32} {values}"

    header  = f"{'Word':<32} {'Jew.':<8} {'Eng.':<8} {'Smp.'}"
    divider = "─" * 56
    lines   = [header, divider]
    lines   = [header, divider]

    top_jewish = top_english = top_simple = None

    for i, (word, jewish, english, simple, _) in enumerate(rows[:10]):
        word = html_mod.unescape(word).strip()
        lines.append(fmt_row(word, jewish, english, simple))
        if i == 0:
            top_jewish, top_english, top_simple = jewish, english, simple

    if not rows and computed:
        lines.append(fmt_row(
            label,
            computed.get('jewish', '?'),
            computed.get('english', '?'),
            computed.get('simple', '?')
        ))
        top_jewish  = computed.get("jewish")
        top_english = computed.get("english")
        top_simple  = computed.get("simple")

    table = "```\n" + "\n".join(lines) + "\n```"
    count = len(rows)

    embed = discord.Embed(
        title=f"🔢 Gematria — {label}",
        description=table,
        color=discord.Color.purple(),
        url=url
    )
    embed.set_footer(text=f"{min(count, 10)} of {count} results — gematrix.org")

    # ── Buttons: click to search by that value ────────────────────────────────
    class GematriaButton(discord.ui.Button):
        def __init__(self, label, value, style):
            super().__init__(label=label, style=style)
            self.value = value

        async def callback(self, interaction: discord.Interaction):
            import time
            now = time.monotonic()
            user_id = interaction.user.id

            # Rate limit: max 3 clicks per 10 seconds per user
            history = _gematria_cooldowns.setdefault(user_id, [])
            # Prune entries older than 10 seconds
            _gematria_cooldowns[user_id] = [t for t in history if now - t < 10]
            if len(_gematria_cooldowns[user_id]) >= 3:
                await interaction.response.send_message(
                    "🛑 Slow down! You can only search 3 times per 10 seconds.",
                    ephemeral=True
                )
                return

            _gematria_cooldowns[user_id].append(now)
            await interaction.response.defer(ephemeral=True)

            encoded = urllib.parse.quote_plus(self.value)
            url = f"https://www.gematrix.org/?word={encoded}"
            try:
                req = urllib.request.Request(
                    url,
                    headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
                )
                with urllib.request.urlopen(req, timeout=15) as r:
                    raw2 = r.read().decode("utf-8")
            except Exception as e:
                await interaction.followup.send(f"⚠️ Could not reach gematrix.org: {e}", ephemeral=True)
                return

            rows2 = row_re.findall(raw2)
            computed2 = {}
            for cipher in ["Jewish", "English", "Simple"]:
                vm = re.search(rf'in {cipher} Gematria equals (\d+)', raw2, re.IGNORECASE)
                if vm:
                    computed2[cipher.lower()] = vm.group(1)

            if not rows2 and not computed2:
                await interaction.followup.send(f"⚠️ No results for **{self.value}**.", ephemeral=True)
                return

            lines2 = [header, divider]
            for i, (word, jewish, english, simple, _) in enumerate(rows2[:10]):
                word = html_mod.unescape(word).strip()
                lines2.append(fmt_row(word, jewish, english, simple))

            if not rows2 and computed2:
                lines2.append(fmt_row(
                    self.value,
                    computed2.get('jewish', '?'),
                    computed2.get('english', '?'),
                    computed2.get('simple', '?')
                ))

            count2 = len(rows2)
            table2 = "```\n" + "\n".join(lines2) + "\n```"
            embed2 = discord.Embed(
                title=f"🔢 Gematria — {self.value}",
                description=table2,
                color=discord.Color.purple(),
                url=url
            )
            embed2.set_footer(text=f"{min(count2, 10)} of {count2} results — gematrix.org")
            await interaction.followup.send(embed=embed2, ephemeral=True)

    class GematriaView(discord.ui.View):
        def __init__(self):
            super().__init__(timeout=120)
            seen = set()
            styles = [
                discord.ButtonStyle.primary,
                discord.ButtonStyle.secondary,
                discord.ButtonStyle.success,
            ]
            pairs = [
                (f"Jewish {top_jewish}", top_jewish),
                (f"English {top_english}", top_english),
                (f"Simple {top_simple}", top_simple),
            ]
            for (lbl, val), style in zip(pairs, styles):
                if val and val not in seen:
                    self.add_item(GematriaButton(lbl, val, style))
                    seen.add(val)

    await ctx.send(embed=embed, view=GematriaView())


# ── !virgil — Sortes Vergilianae ──────────────────────────────────────────────

_AENEID_DATA = None

def _load_aeneid():
    global _AENEID_DATA
    if _AENEID_DATA is None:
        import json, pathlib
        path = pathlib.Path(__file__).parent / "data" / "classical" / "aeneid.json"
        if path.exists():
            _AENEID_DATA = json.loads(path.read_text(encoding="utf-8"))["books"]["Aeneid"]
    return _AENEID_DATA

@bot.command(name="virgil", aliases=["sortesvir", "aeneid"])
async def cmd_virgil(ctx, *, question: str = ""):
    """Consult the Sortes Vergilianae. Usage: !virgil [optional question]"""
    aeneid = _load_aeneid()
    if aeneid is None:
        await ctx.send("⚠️ Aeneid data not found. Run `build_data.py` step 20.")
        return

    # Pick a random book then a random line within it
    book_num = str(random.randint(1, 12))
    lines = aeneid.get(book_num, {})
    if not lines:
        await ctx.send("⚠️ No lines found for that book.")
        return

    line_num = random.randint(1, len(lines))
    verse_text = lines.get(str(line_num), "")

    # Visual: 📖 {book} 🕯️ {line} 👈
    display = f"📖 {book_num}  🕯️ {line_num}  👈"

    embed = discord.Embed(
        title="Sortes Vergilianae",
        description=f"{display}\n\n*{verse_text}*",
        color=discord.Color.dark_gold()
    )
    embed.set_footer(text="The Aeneid — Virgil (trans. John Dryden, 1697)")
    record_special_stat(ctx.author.id, "virgil", f"Aeneid {book_num}.{line_num}")
    await ctx.send(embed=embed)


_HOMER_DATA = None

def _load_homer():
    global _HOMER_DATA
    if _HOMER_DATA is None:
        import json, pathlib
        path = pathlib.Path(__file__).parent / "data" / "classical" / "homeromanteion.json"
        if path.exists():
            _HOMER_DATA = json.loads(path.read_text(encoding="utf-8"))["oracle"]
    return _HOMER_DATA

@bot.command(name="homer", aliases=["homeromanteion", "sortes"])
async def cmd_homer(ctx, *, question: str = ""):
    """Roll three dice and receive a Homeric oracle. Usage: !homer"""
    d1, d2, d3 = random.randint(1,6), random.randint(1,6), random.randint(1,6)
    log.info(f"RNG  divination dice        → {d1},{d2},{d3} (user: {ctx.author})")
    roll_str = f"{d1}-{d2}-{d3}"
    key = f"{d1}{d2}{d3}"

    oracle = _load_homer()
    if oracle is None:
        await ctx.send("⚠️ Homeromanteion data not found.")
        return

    text = oracle.get(key)
    dice_display = f"🎲 {d1}  🎲 {d2}  🎲 {d3}"

    if text is None:
        embed = discord.Embed(
            title=f"The Oracle is Silent  ({roll_str})",
            description=f"{dice_display}\n\n*The papyrus is blank for this combination. The gods withhold their answer.*",
            color=discord.Color.dark_gray()
        )
    else:
        embed = discord.Embed(
            title=f"Homeromanteion  ({roll_str})",
            description=f"{dice_display}\n\n*{text}*",
            color=discord.Color.blurple()
        )
    embed.set_footer(text="Sortes Homericae — PMG VII, Oxford Classical Text translations")
    record_special_stat(ctx.author.id, "homer", roll_str)
    await ctx.send(embed=embed)


@bot.command(name="delphi")
async def cmd_delphi(ctx):
    """Return a random Delphic maxim. Usage: !delphi"""
    maxims = lookup._data.get("classical", {}).get("Delphic Maxims", {})
    if not maxims:
        await ctx.send("Delphic Maxims data not found. Have you run `build_data.py`?")
        return
    num, chap = random.choice(list(maxims.items()))
    log.info(f"RNG  maxims                 → Maxim {num} (user: {ctx.author})")
    text = chap.get("1", "")
    embed = discord.Embed(
        title=f"Delphic Maxim {num}",
        description=text,
        color=discord.Color.gold()
    )
    embed.set_footer(text="Delphic Maxims — trans. Melissa Gold (Hellenion)")
    record_special_stat(ctx.author.id, "delphi", f"Maxim {num}")
    await ctx.send(embed=embed)


# ── !oracle — random verse from any oracular corpus ───────────────────────────

@bot.command(name="oracle")
async def cmd_oracle(ctx, *, question: str = ""):
    """Return a random verse from any oracular corpus. Usage: !oracle"""
    classical = lookup._data.get("classical", {})
    oracular_books = {
        "Delphic Maxims":      ("Delphic Maxims — trans. Melissa Gold (Hellenion)", "Delphi 1"),
        "Oracular Statements": ("Oracular Statements from Delphi", "Delphi 2"),
        "Chaldaean Oracles":   ("Chaldaean Oracles — ed. Westcott", "Chaldaean Oracles"),
        "Golden Verses":       ("Golden Verses of Pythagoras", "GVP"),
    }

    pool = []
    for book, (source, ref_prefix) in oracular_books.items():
        for num, chap in classical.get(book, {}).items():
            text = chap.get("1", "")
            if text:
                pool.append((book, num, text, source, ref_prefix))

    if not pool:
        await ctx.send("No oracular data found. Have you run `build_data.py`?")
        return

    book, num, text, source, ref_prefix = random.choice(pool)
    log.info(f"RNG  sortes                 → {ref_prefix} {num} [{source}] (user: {ctx.author})")

    if len(text) > 1800:
        text = text[:1797] + "…"
    embed = discord.Embed(
        title=f"{book} — {num}",
        description=text,
        color=discord.Color.dark_purple()
    )
    embed.set_footer(text=source)
    record_special_stat(ctx.author.id, "oracle", f"{ref_prefix} {num}")
    await ctx.send(embed=embed)


# ── !discover — random passage from any loaded tradition ────────────────────────

@bot.command(name="discover")
async def cmd_discover(ctx):
    """Random passage from any loaded tradition — scripture, patristics, classical texts, and more."""
    result = lookup.random_verse()
    log.info(f"RNG  discover               → {result.get('reference', '?')} (user: {ctx.author})")
    await _send_result(ctx, result)


# ── !study — verse lookup + patristic commentary in one command ─────────────────

@bot.command(name="study")
async def cmd_study(ctx, *, reference: str = ""):
    """Look up a verse and its patristic commentary together. Usage: !study John 3:16"""
    ref = reference.strip()
    if not ref:
        await ctx.send("Usage: `!study <reference>` — e.g. `!study John 3:16`")
        return
    await verse_prefix(ctx, reference=ref)
    await cmd_catena(ctx, reference=ref)


# ── !xref — cross-references (Treasury of Scripture Knowledge) ──────────────────

@bot.command(name="xref", aliases=["crossref", "crossreference", "xrefs"])
async def cmd_xref(ctx, *, reference: str = ""):
    """Cross-references for a verse, from the Treasury of Scripture Knowledge.
    Usage: !xref John 3:16
    """
    ref = reference.strip()
    if not ref:
        await ctx.send("Usage: `!xref <reference>` — e.g. `!xref John 3:16`")
        return

    result = lookup.get_verse(ref)
    if not result.get("found"):
        await ctx.send(f"⚠️ {result.get('error', 'Verse not found.')}")
        return

    canon_ref = result["reference"]
    xrefs = get_cross_references(canon_ref)
    if not xrefs:
        await ctx.send(f"No cross-references found for **{canon_ref}** — the dataset only covers the 66-book Protestant canon.")
        return

    SHOWN = 15
    lines = [f"`{i + 1}.` **{r}**" for i, (r, _votes) in enumerate(xrefs[:SHOWN])]
    embed = discord.Embed(
        title=f"🔗 Cross-references — {canon_ref}",
        description="\n".join(lines),
        color=discord.Color.dark_gold(),
    )
    footer = f"Showing {min(SHOWN, len(xrefs))} of {len(xrefs)}" if len(xrefs) > SHOWN else f"{len(xrefs)} reference(s)"
    embed.set_footer(text=f"{footer} · Treasury of Scripture Knowledge, via openbible.info (CC-BY)")
    record_special_stat(ctx.author.id, "xref", canon_ref)
    await ctx.send(embed=embed)

@bot.tree.command(name="xref", description="Cross-references for a verse (Treasury of Scripture Knowledge)")
@app_commands.describe(reference="e.g. John 3:16")
async def xref_slash(interaction: discord.Interaction, reference: str):
    await interaction.response.defer()
    ctx = await bot.get_context(interaction)
    await cmd_xref(ctx, reference=reference)


# ── !topic — Nave's Topical Bible ────────────────────────────────────────────────

def _topic_display_name(subject: str) -> str:
    """Title-case a Nave's subject without str.title()'s apostrophe bug
    (e.g. "LORD'S PRAYER" -> "Lord'S Prayer")."""
    return " ".join(w[:1] + w[1:].lower() if w else w for w in subject.split(" "))

def _paginate_topic_entry(entry: str, page_size: int = 900) -> list[str]:
    """Pack whole lines into ~page_size-char pages -- never splits a line
    mid-citation-list the way a fixed-size character chunker would. Nave's
    entries are bullet outlines, so even a "short" 3000-char entry is a wall
    of text as a single embed; this keeps each page to a comfortable read."""
    lines = entry.split("\n")
    pages, current = [], ""
    for line in lines:
        candidate = f"{current}\n{line}" if current else line
        if len(candidate) > page_size and current:
            pages.append(current)
            current = line
        else:
            current = candidate
    if current:
        pages.append(current)
    return pages or [""]

@bot.command(name="topic", aliases=["naves", "topical"])
async def cmd_topic(ctx, *, query: str = ""):
    """Browse scripture by subject, from Nave's Topical Bible (1897, public domain).
    Usage: !topic love
    """
    q = query.strip()
    if not q:
        await ctx.send(f"Usage: `!topic <subject>` — e.g. `!topic love`. {topic_count()} subjects available.")
        return

    result = get_topic(q)
    if not result:
        suggestions = search_topics(q)
        if not suggestions:
            await ctx.send(f"No topic found for **{q}**, and nothing similar either.")
            return
        lines = "\n".join(f"• {_topic_display_name(s)}" for s in suggestions)
        await ctx.send(f"No exact topic **{q}**. Did you mean:\n{lines}")
        return

    subject, entry = result
    display = _topic_display_name(subject)
    pages = _paginate_topic_entry(entry)
    total = len(pages)

    def make_embed(idx):
        embed = discord.Embed(
            title=f"📚 {display}" if total == 1 else f"📚 {display} ({idx + 1}/{total})",
            description=pages[idx],
            color=discord.Color.dark_gold(),
        )
        embed.set_footer(text="Nave's Topical Bible (1897, public domain)")
        return embed

    record_special_stat(ctx.author.id, "topic", subject)

    if total == 1:
        await ctx.send(embed=make_embed(0))
        return

    class TopicView(discord.ui.View):
        def __init__(self):
            super().__init__(timeout=120)
            self.idx = 0

        @discord.ui.button(emoji="◀", style=discord.ButtonStyle.secondary)
        async def prev(self, interaction: discord.Interaction, button: discord.ui.Button):
            self.idx = (self.idx - 1) % total
            await interaction.response.edit_message(embed=make_embed(self.idx), view=self)

        @discord.ui.button(emoji="▶", style=discord.ButtonStyle.secondary)
        async def next(self, interaction: discord.Interaction, button: discord.ui.Button):
            self.idx = (self.idx + 1) % total
            await interaction.response.edit_message(embed=make_embed(self.idx), view=self)

        async def on_timeout(self):
            try:
                await self.message.edit(view=None)
            except Exception:
                pass

    view = TopicView()
    view.message = await ctx.send(embed=make_embed(0), view=view)

@bot.tree.command(name="topic", description="Browse scripture by subject (Nave's Topical Bible)")
@app_commands.describe(query="e.g. love, prayer, forgiveness")
async def topic_slash(interaction: discord.Interaction, query: str):
    await interaction.response.defer()
    ctx = await bot.get_context(interaction)
    await cmd_topic(ctx, query=query)


# ── !dictionary — Easton's + Smith's Bible Dictionary ────────────────────────────

def _paginate_dictionary_entry(text: str, page_size: int = 900) -> list[str]:
    """Same whole-line packing as Nave's topics -- avoids splitting mid-sentence."""
    lines = text.split("\n")
    pages, current = [], ""
    for line in lines:
        candidate = f"{current}\n{line}" if current else line
        if len(candidate) > page_size and current:
            pages.append(current)
            current = line
        else:
            current = candidate
    if current:
        pages.append(current)
    return pages or [""]

@bot.command(name="dictionary", aliases=["dict", "define"])
async def cmd_dictionary(ctx, *, term: str = ""):
    """Look up a person, place, or term in Easton's (1897) or Smith's (1863)
    Bible Dictionary. Usage: !dictionary Aaron
    """
    q = term.strip()
    if not q:
        await ctx.send(f"Usage: `!dictionary <term>` — e.g. `!dictionary Aaron`. {dictionary_entry_count()} terms available.")
        return

    entry = get_dictionary_entry(q)
    if not entry:
        suggestions = search_dictionary_terms(q)
        if not suggestions:
            await ctx.send(f"No dictionary entry found for **{q}**, and nothing similar either.")
            return
        lines = "\n".join(f"• {s}" for s in suggestions)
        await ctx.send(f"No exact entry for **{q}**. Did you mean:\n{lines}")
        return

    name = entry["name"]
    sources_used = entry.get("sources") or [d["source"] for d in entry["definitions"]]
    body = "\n\n".join(
        f"**{DICTIONARY_SOURCE_NAMES.get(d['source'], d['source'])}**\n{d['text']}"
        for d in entry["definitions"]
    )
    pages = _paginate_dictionary_entry(body)
    total = len(pages)

    def make_embed(idx):
        embed = discord.Embed(
            title=f"📔 {name}" if total == 1 else f"📔 {name} ({idx + 1}/{total})",
            description=pages[idx],
            color=discord.Color.dark_gold(),
        )
        embed.set_footer(text=" · ".join(DICTIONARY_SOURCE_NAMES.get(s, s) for s in sources_used))
        return embed

    record_special_stat(ctx.author.id, "dictionary", name)

    if total == 1:
        await ctx.send(embed=make_embed(0))
        return

    class DictionaryView(discord.ui.View):
        def __init__(self):
            super().__init__(timeout=120)
            self.idx = 0

        @discord.ui.button(emoji="◀", style=discord.ButtonStyle.secondary)
        async def prev(self, interaction: discord.Interaction, button: discord.ui.Button):
            self.idx = (self.idx - 1) % total
            await interaction.response.edit_message(embed=make_embed(self.idx), view=self)

        @discord.ui.button(emoji="▶", style=discord.ButtonStyle.secondary)
        async def next(self, interaction: discord.Interaction, button: discord.ui.Button):
            self.idx = (self.idx + 1) % total
            await interaction.response.edit_message(embed=make_embed(self.idx), view=self)

        async def on_timeout(self):
            try:
                await self.message.edit(view=None)
            except Exception:
                pass

    view = DictionaryView()
    view.message = await ctx.send(embed=make_embed(0), view=view)

@bot.tree.command(name="dictionary", description="Look up a person, place, or term (Easton's / Smith's Bible Dictionary)")
@app_commands.describe(term="e.g. Aaron, Jericho, Sabbath")
async def dictionary_slash(interaction: discord.Interaction, term: str):
    await interaction.response.defer()
    ctx = await bot.get_context(interaction)
    await cmd_dictionary(ctx, term=term)


# ── !timeline — Ussher's Annals of the World ─────────────────────────────────────

@bot.command(name="timeline", aliases=["chronology"])
async def cmd_timeline(ctx, *, query: str = ""):
    """Chronological placement of a book, person, or event, from James
    Ussher's Annals of the World (1658, public domain).
    Usage: !timeline Abraham
    """
    q = query.strip()
    if not q:
        lo, hi = timeline_year_range()
        await ctx.send(f"Usage: `!timeline <book, person, or event>` — e.g. `!timeline Abraham`. "
                        f"{timeline_entry_count()} dated entries, {lo} to {hi}.")
        return

    window = search_timeline(q)
    if not window:
        await ctx.send(f"No timeline entry mentions **{q}**. Try a Bible book, a name, or an event like `flood` or `exodus`.")
        return

    lines = []
    for e in window:
        text = e["text"]
        if len(text) > 400:
            text = text[:397] + "…"
        marker = "**→ " if e.get("_matched") else ""
        end_marker = " ←**" if e.get("_matched") else ""
        epoch_suffix = f" ({e['epoch']})" if e.get("epoch") and e is window[0] else ""
        lines.append(f"{marker}`{e['year_display']}`{epoch_suffix}{end_marker}\n{text}")

    embed = discord.Embed(
        title=f"🗓️ Timeline — {q}",
        description="\n\n".join(lines),
        color=discord.Color.dark_gold(),
    )
    embed.set_footer(text="James Ussher, Annals of the World (1658, public domain) · dates per Ussher's own chronology")
    record_special_stat(ctx.author.id, "timeline", q)
    await ctx.send(embed=embed)

@bot.tree.command(name="timeline", description="Chronological placement of a book, person, or event (Ussher's Annals of the World)")
@app_commands.describe(query="e.g. Abraham, exodus, flood")
async def timeline_slash(interaction: discord.Interaction, query: str):
    await interaction.response.defer()
    ctx = await bot.get_context(interaction)
    await cmd_timeline(ctx, query=query)


# ── Personal bookmarks: !save / !saved / !unsave ─────────────────────────────────

@bot.command(name="save", aliases=["bookmark"])
async def cmd_save(ctx, *, reference: str = ""):
    """Save a verse to your personal bookmark list, with an optional note.
    Usage: !save John 3:16
           !save John 3:16 | this got me through a hard week
    Running it again on an already-saved verse updates the note.
    """
    raw = reference.strip()
    if not raw:
        await ctx.send("Usage: `!save <reference>` or `!save <reference> | <note>` — e.g. `!save John 3:16 | for later`")
        return

    ref, _, note = raw.partition("|")
    ref = ref.strip()
    note = note.strip()
    if len(note) > 300:
        note = note[:297] + "…"

    result = lookup.get_verse(ref)
    if not result.get("found") and "Could not parse" in result.get("error", ""):
        result = lookup.random_verse_from_book(ref)
    if not result.get("found"):
        await ctx.send(f"⚠️ Could not find **{ref}** — nothing saved.")
        return

    import datetime
    data = _load_bookmarks()
    uid = str(ctx.author.id)
    entries = data.setdefault(uid, [])
    canon_ref = result["reference"]

    existing = next((e for e in entries if e["reference"] == canon_ref), None)
    if existing:
        if note:
            existing["note"] = note
            _save_bookmarks(data)
            await ctx.send(f"Updated your note on **{canon_ref}**.")
        else:
            await ctx.send(f"**{canon_ref}** is already in your saved list. Add `| <note>` to attach or update a note.")
        return

    entries.append({
        "reference": canon_ref,
        "source": result.get("source", ""),
        "saved_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "note": note,
    })
    _save_bookmarks(data)
    suffix = " with your note" if note else ""
    await ctx.send(f"📌 Saved **{canon_ref}**{suffix}. You have {len(entries)} saved verse(s) — see `!saved`.")


@bot.command(name="saved", aliases=["bookmarks"])
async def cmd_saved(ctx, action: str = ""):
    """List your saved verses. Usage: !saved  |  !saved export"""
    entries = _load_bookmarks().get(str(ctx.author.id), [])
    if not entries:
        await ctx.send("You haven't saved any verses yet. Use `!save <reference>` to bookmark one.")
        return

    if action.strip().lower() == "export":
        if ctx.guild and not _get_guild_features(ctx.guild.id).get("export"):
            await ctx.send(
                "Bookmark export isn't enabled on this server. "
                "An admin can turn it on with `!features export on`."
            )
            return
        import io
        lines = []
        for e in entries:
            result = lookup.get_verse(e["reference"])
            text = re.sub(r"\*\*\[\d+\]\*\*\s*", "", result.get("text", "")).replace("**", "") if result.get("found") else ""
            block = f"{e['reference']} ({e.get('source', '')})\n{text}"
            if e.get("note"):
                block += f"\n\nNote: {e['note']}"
            lines.append(block + "\n")
        buf = io.BytesIO("\n".join(lines).encode("utf-8"))
        await ctx.send(file=discord.File(buf, filename="saved_verses.txt"))
        return

    # Length-aware, not a fixed slice -- notes can make individual entries long
    # enough that 25 of them would blow past the embed description limit.
    lines, total_len, shown = [], 0, 0
    for i, e in enumerate(entries):
        line = f"`{i + 1}.` **{e['reference']}** — {e.get('source', '')}"
        if e.get("note"):
            line += f"\n     💬 {e['note']}"
        if total_len + len(line) > 3800:
            break
        lines.append(line)
        total_len += len(line) + 1
        shown += 1

    embed = discord.Embed(
        title=f"{ctx.author.display_name}'s saved verses",
        description="\n".join(lines),
        color=discord.Color.dark_gold(),
    )
    embed.set_footer(text=f"Showing {shown} of {len(entries)}." if shown < len(entries) else "Use !unsave <number> to remove one.")
    await ctx.send(embed=embed)


@bot.command(name="unsave", aliases=["unbookmark"])
async def cmd_unsave(ctx, index: int = 0):
    """Remove a saved verse by its number from !saved. Usage: !unsave 2"""
    data = _load_bookmarks()
    uid = str(ctx.author.id)
    entries = data.get(uid, [])
    if not entries:
        await ctx.send("You have no saved verses.")
        return
    if not (1 <= index <= len(entries)):
        await ctx.send(f"Give a number between 1 and {len(entries)} — see `!saved`.")
        return
    removed = entries.pop(index - 1)
    data[uid] = entries
    _save_bookmarks(data)
    await ctx.send(f"Removed **{removed['reference']}** from your saved list.")


# ── !plan — personal chapter-a-day reading plan ──────────────────────────────────

@bot.command(name="plan")
async def cmd_plan(ctx, action: str = "", *, arg: str = ""):
    """Personal chapter-a-day reading plan.
    Usage: !plan start <book>   — start a plan, e.g. !plan start John
           !plan (or !plan today) — show today's chapter
           !plan status         — show your progress
           !plan stop           — cancel your plan
    """
    action = action.strip().lower()
    uid = str(ctx.author.id)
    data = _load_reading_plans()

    if action == "start":
        book_raw = arg.strip()
        if not book_raw:
            await ctx.send("Usage: `!plan start <book>` — e.g. `!plan start John`")
            return
        _, canon = lookup._resolve_book(book_raw)
        if canon is None:
            await ctx.send(f"⚠️ Unknown book: **{book_raw}**")
            return
        total = lookup.chapter_count(canon)
        if not total:
            await ctx.send(f"⚠️ **{canon}** doesn't have chapter data available for a reading plan.")
            return
        import datetime
        data[uid] = {
            "book": canon,
            "total_chapters": total,
            "started_at": datetime.date.today().isoformat(),
        }
        _save_reading_plans(data)
        await ctx.send(
            f"📅 Reading plan started: **{canon}** — {total} chapter(s), one per day. "
            "Check in with `!plan` each day."
        )
        return

    plan = data.get(uid)
    if not plan:
        await ctx.send("You don't have a reading plan yet. Start one with `!plan start <book>`.")
        return

    if action == "stop":
        del data[uid]
        _save_reading_plans(data)
        await ctx.send(f"Reading plan for **{plan['book']}** cancelled.")
        return

    if action == "status":
        chap = _plan_current_chapter(plan)
        pct = int(100 * chap / plan["total_chapters"])
        msg = f"📖 **{plan['book']}** — day {chap} of {plan['total_chapters']} ({pct}%). Started {plan['started_at']}."
        if ctx.guild and _get_guild_features(ctx.guild.id).get("streaks"):
            msg += f"\n🔥 Current streak: {plan.get('streak', 0)} day(s)."
        await ctx.send(msg)
        return

    if action not in ("", "today"):
        await ctx.send("Usage: `!plan` · `!plan today` · `!plan status` · `!plan stop` · `!plan start <book>`")
        return

    chap = _plan_current_chapter(plan)

    import datetime
    today_iso = datetime.date.today().isoformat()
    if plan.get("last_checkin") != today_iso:
        yesterday_iso = (datetime.date.today() - datetime.timedelta(days=1)).isoformat()
        plan["streak"] = plan.get("streak", 0) + 1 if plan.get("last_checkin") == yesterday_iso else 1
        plan["last_checkin"] = today_iso
        data[uid] = plan
        _save_reading_plans(data)

    result = lookup.get_verse(f"{plan['book']} {chap}")
    await _send_result(ctx, result)
    if ctx.guild and _get_guild_features(ctx.guild.id).get("streaks"):
        await ctx.send(f"🔥 {plan.get('streak', 1)}-day streak!")
    if chap >= plan["total_chapters"]:
        await ctx.send(f"🎉 That's the final chapter of **{plan['book']}**. Start a new plan with `!plan start <book>`.")

@bot.tree.command(name="plan", description="Personal chapter-a-day reading plan")
@app_commands.describe(action="start | today | status | stop", arg="book name, if starting")
async def plan_slash(interaction: discord.Interaction, action: str = "", arg: str = ""):
    await interaction.response.defer()
    ctx = await bot.get_context(interaction)
    await cmd_plan(ctx, action=action, arg=arg)


# ── !export — bundle a book/chapter range into a downloadable text file ─────────

def _export_chapters(book_name: str, labels: list[str]) -> tuple[str, str]:
    """Fetch and concatenate every mode string in `labels` for book_name into
    one text blob. Returns (text, mode). Runs off the event loop."""
    options = _chapter_options_for_book(book_name)
    mode = options[1] if options else "verse"
    parts = []
    for label in labels:
        result = _fetch_chapter_result(book_name, label, mode)
        if not result.get("found"):
            continue
        text = result.get("text", "")
        text = re.sub(r"\*\*\[(.+?)\]\*\*\s*", r"[\1] ", text)
        parts.append(f"{result.get('reference', f'{book_name} {label}')}\n\n{text}")
    return "\n\n\n".join(parts), mode


@bot.command(name="export")
async def cmd_export(ctx, *, arg: str = ""):
    """Bundle a book (or chapter range) into a downloadable text file.
    Usage: !export John          — whole book
           !export John 1-5      — chapters 1 through 5
           !export John 3        — single chapter"""
    arg = arg.strip()
    if not arg:
        await ctx.send("Usage: `!export <book>` or `!export <book> <start>-<end>` (e.g. `!export John 1-5`).")
        return

    m_range = re.match(r"^(.*?)\s+(\S+)-(\S+)$", arg)
    if m_range:
        book_raw, start, end = m_range.group(1), m_range.group(2), m_range.group(3)
    else:
        m_single = re.match(r"^(.*?)\s+(\S+)$", arg)
        if m_single:
            book_raw, start, end = m_single.group(1), m_single.group(2), m_single.group(2)
        else:
            book_raw, start, end = arg, None, None

    _, canon = lookup._resolve_book(book_raw)
    book_name = canon or book_raw

    options = _chapter_options_for_book(book_name)
    if options is None:
        await ctx.send(
            f"⚠️ **{book_name}** isn't chapter-browsable, so there's nothing to bundle. "
            f"Try `!verse {book_name}` instead."
        )
        return
    labels, mode = options

    if start is not None:
        try:
            i1 = labels.index(start)
            i2 = labels.index(end)
        except ValueError:
            await ctx.send(
                f"⚠️ Couldn't find chapter **{start}** or **{end}** in **{book_name}**. "
                f"Range: {labels[0]}–{labels[-1]}."
            )
            return
        if i1 > i2:
            i1, i2 = i2, i1
        chosen = labels[i1:i2 + 1]
    else:
        chosen = labels

    limit = 20 if mode == "hadith" else 200
    if len(chosen) > limit:
        await ctx.send(
            f"That's {len(chosen)} {'hadith books' if mode == 'hadith' else 'chapters'} — "
            f"please narrow the range to {limit} or fewer at a time."
        )
        return

    async with ctx.typing():
        loop = asyncio.get_event_loop()
        text, _mode = await loop.run_in_executor(None, _export_chapters, book_name, chosen)

    if not text.strip():
        await ctx.send(f"⚠️ Couldn't fetch any content for **{book_name}**.")
        return

    buf = io.BytesIO(text.encode("utf-8"))
    filename = re.sub(r"[^\w\-]+", "_", book_name).strip("_") + ".txt"
    await ctx.send(
        f"📄 **{book_name}** — {len(chosen)} chapter(s) exported.",
        file=discord.File(buf, filename=filename)
    )


# ── !leaderboard — most active bookmarkers ───────────────────────────────────────
# !stats already covers bot-wide "most cited verse/book/command" popularity.
# This one is genuinely new: per-user bookmark counts, which nothing else shows.

@bot.command(name="leaderboard", aliases=["lb"])
async def cmd_leaderboard(ctx):
    """Show who has the most saved bookmarks."""
    data = _load_bookmarks()
    counts = [(uid, len(entries)) for uid, entries in data.items() if entries]
    if not counts:
        await ctx.send("No one has saved any verses yet — be the first with `!save <reference>`.")
        return

    counts.sort(key=lambda x: x[1], reverse=True)
    lines = []
    for i, (uid, n) in enumerate(counts[:10]):
        member = ctx.guild.get_member(int(uid)) if ctx.guild else None
        name = member.display_name if member else f"User {uid}"
        lines.append(f"`{i + 1}.` **{name}** — {n} saved verse(s)")

    embed = discord.Embed(
        title="🏆 Bookmark Leaderboard",
        description="\n".join(lines),
        color=discord.Color.dark_gold(),
    )
    embed.set_footer(text="Based on !save across all servers this bot is in.")
    await ctx.send(embed=embed)

@bot.tree.command(name="leaderboard", description="Show who has the most saved bookmarks")
async def leaderboard_slash(interaction: discord.Interaction):
    await interaction.response.defer()
    ctx = await bot.get_context(interaction)
    await cmd_leaderboard(ctx)


# ── !subscribe — personal daily Verse of the Day by DM ───────────────────────────
# Independent of the per-guild channel post (!votdsetup): this is the same daily
# verse, delivered straight to a user's DMs instead of (or as well as) a channel.
SUBSCRIBERS_PATH = Path(__file__).parent / "data" / "subscribers.json"
DM_DIGEST_TIME = "12:00"  # UTC

def _load_subscribers() -> list:
    if SUBSCRIBERS_PATH.exists():
        try:
            return json.loads(SUBSCRIBERS_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    return []

def _save_subscribers(ids: list) -> None:
    _atomic_write_json(SUBSCRIBERS_PATH, ids)

@bot.command(name="subscribe")
async def cmd_subscribe(ctx):
    """Get the daily Verse of the Day sent to you by DM."""
    subs = _load_subscribers()
    uid = ctx.author.id
    if uid in subs:
        await ctx.send("You're already subscribed to the daily DM verse. Use `!unsubscribe` to stop.")
        return
    try:
        await ctx.author.send(
            f"📬 You're now subscribed to the daily Verse of the Day, sent here around {DM_DIGEST_TIME} UTC. "
            "Use `!unsubscribe` in a server with me to stop anytime."
        )
    except discord.Forbidden:
        await ctx.send("⚠️ I couldn't DM you — enable direct messages from server members and try again.")
        return
    subs.append(uid)
    _save_subscribers(subs)
    await ctx.send("📬 Subscribed! Check your DMs.")

@bot.command(name="unsubscribe")
async def cmd_unsubscribe(ctx):
    """Stop the daily DM Verse of the Day."""
    subs = _load_subscribers()
    uid = ctx.author.id
    if uid not in subs:
        await ctx.send("You're not currently subscribed.")
        return
    subs.remove(uid)
    _save_subscribers(subs)
    await ctx.send("Unsubscribed from the daily DM verse.")


_GREEK_TRANSLIT_ROUGH = "̔"       # combining reversed comma above (rough breathing)
_GREEK_TRANSLIT_ACUTE = "́"
_GREEK_TRANSLIT_GRAVE = "̀"
_GREEK_TRANSLIT_CIRCUMFLEX = "͂"  # combining greek perispomeni
_GREEK_TRANSLIT_DIAERESIS = "̈"
_GREEK_TRANSLIT_IOTA_SUB = "ͅ"
_GREEK_TRANSLIT_BASE = {
    "α": "a", "β": "b", "γ": "g", "δ": "d", "ε": "e", "ζ": "z", "η": "e",
    "θ": "th", "ι": "i", "κ": "k", "λ": "l", "μ": "m", "ν": "n", "ξ": "x",
    "ο": "o", "π": "p", "ρ": "r", "σ": "s", "ς": "s", "τ": "t", "υ": "y",
    "φ": "ph", "χ": "ch", "ψ": "ps", "ω": "o",
}
_GREEK_TRANSLIT_LONG = {"η", "ω"}  # get a macron; circumflex is dropped as redundant on these
_GREEK_TRANSLIT_VOWELS = set("αεηιοωυ")
_GREEK_TRANSLIT_DIPHTHONGS = {
    "αι": "ai", "ει": "ei", "οι": "oi", "υι": "ui",
    "αυ": "au", "ευ": "eu", "ου": "ou", "ηυ": "eu",
}


def _greek_translit_accent(marks: str, base_is_long: bool) -> str | None:
    if _GREEK_TRANSLIT_GRAVE in marks:
        return "grave"
    if _GREEK_TRANSLIT_ACUTE in marks:
        return "acute"
    if _GREEK_TRANSLIT_CIRCUMFLEX in marks:
        return None if base_is_long else "circumflex"  # dropped on eta/omega: the macron already shows length
    return None


def _greek_translit_compose(latin: str, is_long: bool, accent: str | None, diaeresis: bool, iota_sub: bool) -> str:
    s = latin
    if is_long:
        s += "̄"  # combining macron
    if diaeresis:
        s += _GREEK_TRANSLIT_DIAERESIS  # must precede the accent mark to match Unicode's precomposed order (e.g. ḯ)
    if accent == "acute":
        s += _GREEK_TRANSLIT_ACUTE
    elif accent == "grave":
        s += _GREEK_TRANSLIT_GRAVE
    elif accent == "circumflex":
        s += "̂"
    s = unicodedata.normalize("NFC", s)
    if iota_sub:
        s += "i"
    return s


def _transliterate_greek(word: str) -> str:
    """Standard scholarly transliteration of an actual Greek word FORM as
    it appears in the text -- not its dictionary lemma. MACULA's Greek
    dataset has no per-instance transliteration column (unlike its Hebrew
    one), so this exists to avoid the alternative of showing a lexicon's
    lemma-form transliteration (e.g. "ho") next to a different inflected
    form actually on screen (e.g. "τὸν", which transliterates to "ton") --
    those don't match, and looked exactly as wrong as it sounds.

    Matches the accent/breathing convention already used by the local
    Strong's dictionary (verified against all 5,523 of its Greek entries
    that have both a lexeme and a transliteration: 99.95% exact match --
    the only misses are one word pair where that dictionary itself is
    internally inconsistent, and one non-alphabetic numeral entry, "666"
    spelled with numeral-letters rather than a word):
      - acute/grave get their own accent mark; circumflex too, EXCEPT on
        eta/omega, where it's dropped as redundant (the macron already
        shows vowel length, and circumflex there marks nothing extra).
      - rough breathing prepends "h" (also on rho: rh, and word-medial
        double-rho, which is smooth+rough by convention: rrh).
      - a diaeresis on what would otherwise be the second half of a
        diphthong breaks it into two separate syllables, each
        transliterated on its own, with the diaeresis preserved.
      - iota subscript is rendered as a trailing "i" rather than dropped.
      - diphthong breathing/accent/diaeresis live on the SECOND Greek
        letter of the pair, per Greek orthography."""
    decomposed = unicodedata.normalize("NFD", word)
    clusters = []
    for ch in decomposed:
        if unicodedata.combining(ch) and clusters:
            clusters[-1] = (clusters[-1][0], clusters[-1][1] + ch)
        else:
            clusters.append((ch, ""))

    out = []
    i, n = 0, len(clusters)
    while i < n:
        base, marks = clusters[i]
        lower = base.lower()
        is_upper = base.isupper()

        if lower not in _GREEK_TRANSLIT_BASE:
            out.append(base)
            i += 1
            continue

        if lower == "γ" and i + 1 < n and clusters[i + 1][0].lower() in ("γ", "κ", "ξ", "χ"):
            out.append("N" if is_upper else "n")
            i += 1
            continue

        if lower == "ρ":
            translit = "rh" if _GREEK_TRANSLIT_ROUGH in marks else "r"
            if is_upper:
                translit = translit[0].upper() + translit[1:]
            out.append(translit)
            i += 1
            continue

        is_diphthong = (
            lower in "αεοηυ" and i + 1 < n and clusters[i + 1][0].lower() in _GREEK_TRANSLIT_VOWELS
            and (lower + clusters[i + 1][0].lower()) in _GREEK_TRANSLIT_DIPHTHONGS
        )
        if is_diphthong and _GREEK_TRANSLIT_DIAERESIS in clusters[i + 1][1]:
            is_diphthong = False  # a trema explicitly breaks the diphthong

        if is_diphthong:
            base2, marks2 = clusters[i + 1]
            pair = lower + base2.lower()
            latin_pair = _GREEK_TRANSLIT_DIPHTHONGS[pair]
            rough = _GREEK_TRANSLIT_ROUGH in marks or _GREEK_TRANSLIT_ROUGH in marks2
            accent = (_greek_translit_accent(marks2, base2.lower() in _GREEK_TRANSLIT_LONG)
                      or _greek_translit_accent(marks, lower in _GREEK_TRANSLIT_LONG))
            iota_sub = _GREEK_TRANSLIT_IOTA_SUB in marks2 or _GREEK_TRANSLIT_IOTA_SUB in marks
            l2 = _greek_translit_compose(latin_pair[1], base2.lower() in _GREEK_TRANSLIT_LONG,
                                          accent, False, iota_sub)
            translit = latin_pair[0] + l2
            if rough:
                translit = "h" + translit
            if is_upper:
                translit = translit[0].upper() + translit[1:]
            out.append(translit)
            i += 2
            continue

        is_long = lower in _GREEK_TRANSLIT_LONG
        accent = _greek_translit_accent(marks, is_long)
        diaeresis = _GREEK_TRANSLIT_DIAERESIS in marks
        iota_sub = _GREEK_TRANSLIT_IOTA_SUB in marks
        translit = _greek_translit_compose(_GREEK_TRANSLIT_BASE[lower], is_long, accent, diaeresis, iota_sub)
        if lower in _GREEK_TRANSLIT_VOWELS and _GREEK_TRANSLIT_ROUGH in marks:
            translit = "h" + translit
        if is_upper:
            translit = translit[0].upper() + translit[1:]
        out.append(translit)
        i += 1

    return "".join(out)


# ── !card — shareable verse image ─────────────────────────────────────────────────

_SYRIAC_FONT_PATH = str(Path(__file__).parent / "fonts" / "NotoSansSyriac-Regular.ttf")

def _script_font(fonts_dir: str, text: str) -> str:
    """Pick a font file that can actually render the text's script.
    Georgia has no Hebrew glyphs at all and drops most polytonic Greek
    diacritics (both render as tofu boxes); Times New Roman covers
    Hebrew, full polytonic Greek, and Cyrillic as well as Latin. No
    Windows-bundled font has any Syriac glyphs at all, so Peshitta text
    uses a bundled copy of Noto Sans Syriac (Google, SIL OFL) instead."""
    for ch in text:
        cp = ord(ch)
        if 0x0700 <= cp <= 0x074F:
            return _SYRIAC_FONT_PATH
        if 0x0590 <= cp <= 0x05FF or 0x0370 <= cp <= 0x03FF or 0x1F00 <= cp <= 0x1FFF or 0x0400 <= cp <= 0x04FF:
            return fonts_dir + "times.ttf"
    return fonts_dir + "georgiai.ttf"

def _is_rtl_script(text: str) -> bool:
    """Hebrew or Syriac -- both right-to-left, both need _rtl_visual()."""
    return any(0x0590 <= ord(ch) <= 0x05FF or 0x0700 <= ord(ch) <= 0x074F for ch in text)

def _rtl_clusters(line: str) -> list[str]:
    """Group each base character with any combining marks that follow it
    (e.g. Hebrew niqqud/cantillation) into a cluster, then reverse cluster
    order, so a consonant keeps its vowel points attached instead of them
    ending up on the wrong side. Returns the clusters as a list (visual
    left-to-right draw order) rather than a joined string -- _draw_rtl_line
    needs the boundaries to position each mark on its own base character."""
    clusters, current = [], ""
    for ch in line:
        if unicodedata.combining(ch) and current:
            current += ch
        else:
            if current:
                clusters.append(current)
            current = ch
    if current:
        clusters.append(current)
    return list(reversed(clusters))

def _rtl_visual(line: str) -> str:
    """Approximate correct RTL visual order for a naive left-to-right renderer
    (Pillow has no bidi/shaping engine). String form of _rtl_clusters(),
    safe for draw.textlength()/textwrap width estimates (combining marks
    have zero advance width, so joining clusters doesn't change the total),
    but NOT safe to pass to draw.text() directly -- see _draw_rtl_line."""
    return "".join(_rtl_clusters(line))

def _draw_rtl_line(draw, x: float, y: float, line: str, font, fill) -> float:
    """Draw RTL (Hebrew/Syriac) text left-to-right on screen, cluster by
    cluster, placing each combining mark at the *same* origin as its base
    character instead of PIL's default of advancing the cursor character by
    character. PIL has no text-shaping engine: a zero-advance-width niqqud
    point drawn via plain draw.text() still gets positioned at the cursor
    position reached *after* its base consonant's own advance, so every
    vowel point silently drifts onto the position of the next letter
    instead of stacking on the letter it belongs to. Returns the total
    width drawn (same value draw.textlength on the flattened string would
    give, since marks have zero advance)."""
    cursor = x
    for cluster in _rtl_clusters(line):
        base, marks = cluster[0], cluster[1:]
        draw.text((cursor, y), base, font=font, fill=fill)
        for mark in marks:
            draw.text((cursor, y), mark, font=font, fill=fill)
        cursor += draw.textlength(base, font=font)
    return cursor - x

def _size_for_length(n: int) -> int:
    """Starting font size for the card body text, scaled so a short quote
    (e.g. a single clause) renders noticeably larger than a full chapter,
    rather than every length maxing out at the same size."""
    anchors = [(20, 68), (100, 58), (200, 50), (400, 44), (800, 36), (2000, 26), (4000, 22)]
    if n <= anchors[0][0]:
        return anchors[0][1]
    for (x0, y0), (x1, y1) in zip(anchors, anchors[1:]):
        if x0 <= n <= x1:
            return int(y0 + (n - x0) / (x1 - x0) * (y1 - y0))
    return anchors[-1][1]

def _render_verse_card(reference: str, text: str, source: str):
    """Render a verse (or a whole chapter) as a parchment-style PNG.
    Runs off the event loop (CPU-bound). Height grows to fit the text
    instead of truncating it -- a chapter-length card is just taller."""
    from PIL import Image, ImageDraw, ImageFont
    import io, textwrap

    W = 1200
    BG, BORDER, TEXT, ACCENT = (245, 239, 224), (178, 34, 34), (59, 42, 22), (178, 34, 34)
    FONTS = "C:/Windows/Fonts/"
    TOP_MARGIN, BOTTOM_RESERVED = 60, 200
    MAX_CHARS = 4000  # safety cap so a pathological request (e.g. Psalm 119) can't produce a runaway image

    # Strip Discord markdown verse-number markers (e.g. "**[1]** ") and any
    # stray bold asterisks — meaningful in an embed, just noise in a plain image.
    quote_text = re.sub(r"\*\*\[\d+\]\*\*\s*", "", text.strip())
    quote_text = quote_text.replace("**", "").strip()
    if len(quote_text) > MAX_CHARS:
        quote_text = quote_text[:MAX_CHARS - 1] + "…"
    is_rtl = _is_rtl_script(quote_text)
    body_font_path = _script_font(FONTS, quote_text)

    # Each verse (separated by the newlines already in whole-chapter text)
    # wraps as its own paragraph, rather than running every verse together.
    paragraphs = quote_text.split("\n")

    dummy = ImageDraw.Draw(Image.new("RGB", (10, 10)))
    max_width = W - 160
    size, MIN_SIZE = _size_for_length(len(quote_text)), 22
    lines, line_height, font = [], 0, None
    while size >= MIN_SIZE:
        font = ImageFont.truetype(body_font_path, size)
        wrap_width = max(10, int(max_width / (size * 0.52)))
        lines = [l for para in paragraphs for l in (textwrap.wrap(para, width=wrap_width) or [""])]
        line_height = int(size * 1.35)
        widest = max((dummy.textlength(l, font=font) for l in lines), default=0)
        if widest <= max_width:
            break
        size -= 2

    text_height = line_height * len(lines)
    H = max(630, TOP_MARGIN + text_height + BOTTOM_RESERVED)

    img = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(img)
    draw.rectangle([16, 16, W - 17, H - 17], outline=BORDER, width=4)

    # Center the text block within the space above the divider/reference/source
    # (a no-op once H has grown to exactly fit -- only matters for short verses
    # on the minimum-height canvas, which would otherwise sit flush at the top).
    available = H - TOP_MARGIN - BOTTOM_RESERVED
    y = TOP_MARGIN + max(0, (available - text_height) // 2)
    for line in lines:
        if is_rtl:
            w = draw.textlength(_rtl_visual(line), font=font)
            _draw_rtl_line(draw, (W - w) / 2, y, line, font, TEXT)
        else:
            w = draw.textlength(line, font=font)
            draw.text(((W - w) / 2, y), line, font=font, fill=TEXT)
        y += line_height

    # Small ornamental divider (drawn, not a glyph, so it never falls back to tofu)
    cx, cy = W // 2, H - 160
    draw.line([(cx - 90, cy), (cx - 14, cy)], fill=BORDER, width=2)
    draw.line([(cx + 14, cy), (cx + 90, cy)], fill=BORDER, width=2)
    draw.polygon([(cx, cy - 7), (cx + 7, cy), (cx, cy + 7), (cx - 7, cy)], fill=BORDER)

    ref_font = ImageFont.truetype(FONTS + "georgiab.ttf", 34)
    ref_w = draw.textlength(reference, font=ref_font)
    draw.text(((W - ref_w) / 2, H - 130), reference, font=ref_font, fill=ACCENT)

    src_font = ImageFont.truetype(FONTS + "georgia.ttf", 20)
    src_w = draw.textlength(source, font=src_font)
    draw.text(((W - src_w) / 2, H - 80), source, font=src_font, fill=ACCENT)

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf


def _render_compare_card(reference: str, entries: list[tuple[str, str]]):
    """Render up to 4 translations of one verse stacked in a single PNG."""
    from PIL import Image, ImageDraw, ImageFont
    import io, textwrap

    entries = entries[:4]
    n = len(entries)
    W, TOP, BAND_H, BOTTOM = 1200, 110, 165, 40
    H = TOP + BAND_H * n + BOTTOM
    BG, BORDER, TEXT, ACCENT = (245, 239, 224), (178, 34, 34), (59, 42, 22), (178, 34, 34)
    FONTS = "C:/Windows/Fonts/"

    img = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(img)
    draw.rectangle([16, 16, W - 17, H - 17], outline=BORDER, width=4)

    title_font = ImageFont.truetype(FONTS + "georgiab.ttf", 40)
    tw = draw.textlength(reference, font=title_font)
    draw.text(((W - tw) / 2, 38), reference, font=title_font, fill=ACCENT)

    label_font = ImageFont.truetype(FONTS + "georgiab.ttf", 24)
    max_width = W - 140

    y = TOP
    for i, (label, text) in enumerate(entries):
        clean = re.sub(r"\*\*\[\d+\]\*\*\s*", "", text.strip()).replace("**", "")
        if len(clean) > 260:
            clean = clean[:257] + "…"

        draw.text((70, y), label, font=label_font, fill=ACCENT)

        body_font_path = _script_font(FONTS, clean)
        size, lines, line_h, body_font = 28, [clean], 36, None
        while size > 16:
            body_font = ImageFont.truetype(body_font_path, size)
            wrap_width = max(10, int(max_width / (size * 0.52)))
            lines = textwrap.wrap(clean, width=wrap_width) or [clean]
            line_h = int(size * 1.3)
            widest = max((draw.textlength(l, font=body_font) for l in lines), default=0)
            if line_h * len(lines) <= BAND_H - 44 and widest <= max_width:
                break
            size -= 2

        is_rtl = _is_rtl_script(clean)
        ty = y + 34
        for line in lines:
            if is_rtl:
                _draw_rtl_line(draw, 70, ty, line, body_font, TEXT)
            else:
                draw.text((70, ty), line, font=body_font, fill=TEXT)
            ty += line_h

        if i < n - 1:
            draw.line([(70, y + BAND_H - 14), (W - 70, y + BAND_H - 14)], fill=BORDER, width=1)
        y += BAND_H

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf

_STRONGS_INFLECTION_FAMILIES = {}
for _fam in [("G1510", "G1511", "G1498", "G2071", "G2258", "G5600", "G2277")]:
    for _n in _fam:
        _STRONGS_INFLECTION_FAMILIES[_n] = _fam
del _fam, _n
# The original-language (Tischendorf) and KJV (separate SWORD module)
# Strong's tagging don't always agree on which number to use for a given
# inflected form -- e.g. Tischendorf tags every form of "to be" as the
# lemma G1510, but the KJV module tags the imperfect "was" as G2258 (its
# own number per Strong's, confirmed by G2258's own derivation field: "imperfect
# of G1510 (eimi)"). Without this, !interlinear's KJV alignment (see
# cmd_interlinear) silently found no match for G1510 in a verse like John
# 1:1 that says "was" three times, and fell back to the lexicon gloss
# "am" -- accurate for G1510's present-tense sense, flatly wrong in
# context. Only eimi's family is covered since it's by far the most
# frequent case; add another only after confirming via each number's own
# derivation field, not by inference.

_SECONDARY_SENSE_MARKERS = ("concrete",)
# NOTE: this list is deliberately short. "by implication" looked like a
# plausible addition but actively broke G2889 (kosmos) -- its definition is
# "orderly arrangement, i.e. decoration; by implication, the world (...)",
# and excluding the "by implication" clause throws away "world", the
# overwhelmingly common NT sense, leaving only "decoration" behind (which
# doesn't match "adorning" either, so it fell back to the wrong entry
# anyway). These Strong's/Thayer lead-in phrases don't consistently mark a
# *rarer* sense -- only "concrete" has actually been verified to (H367
# eymah: "fright; concrete, an idol (as a bugbear)"). Add another marker
# here only after checking it against a real reported case, not on
# suspicion alone.

def _clean_strongs_gloss(short_def: str, full_def: str = "") -> str:
    """OpenScriptures' short_definition is the *full* list of every KJV
    rendering of a word (e.g. G3588 -> "the, this, that, one, he, she, it,
    etc"), not a single gloss -- displayed as-is under an interlinear word
    it just reads as noise, and picking merely the first non-marker entry
    isn't good enough either: G1520 (heis, "one") gave "a(-n, -ny, certain)",
    G3756 (ou, "not") gave "nay" -- both real KJV renderings, both far less
    recognizable than words later in the same list.

    Splits on top-level commas (respecting parens, so "a(-n, -ny, certain)"
    survives as one unit), drops "+"/"X"-prefixed entries (OpenScriptures'
    notation for a rare/idiomatic rendering), then prefers whichever
    surviving candidate's core word (parentheticals stripped) also appears
    in the fuller `definition` field -- an independent cross-check that
    reliably favors the plain, recognizable word over an archaic or
    idiomatic one. Falls back to the first non-marker entry, unstripped, if
    nothing cross-validates (this matters for cases like theos, whose
    `definition` field is itself a fragment that omits "God" entirely)."""
    if not short_def:
        return ""
    parts, depth, current = [], 0, ""
    for ch in short_def:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth = max(0, depth - 1)
        if ch == "," and depth == 0:
            parts.append(current.strip())
            current = ""
        else:
            current += ch
    if current.strip():
        parts.append(current.strip())
    candidates = [p.rstrip(".").strip() for p in parts if p and not p.startswith("+") and not p.startswith("X ")]
    if not candidates:
        candidates = [p.rstrip(".").strip() for p in parts] or [short_def]

    if full_def:
        # Drop any semicolon-delimited clause that *opens* with a Strong's/
        # Thayer secondary-sense marker -- convention for "this is a rare or
        # derived sense, not the plain gloss" (e.g. H367 eymah's definition
        # is "fright; concrete, an idol (as a bugbear)": without excluding
        # the second clause, "idol" -- a real but secondary sense -- matches
        # a short_definition candidate and wrongly outranks "dread"/"fear").
        clauses = full_def.split(";")
        kept = [c for c in clauses
                if not any(c.strip().lower().startswith(m) for m in _SECONDARY_SENSE_MARKERS)]
        searchable = ";".join(kept)
        for cand in candidates:
            core = re.sub(r"\([^)]*\)", "", cand).strip(" -")
            if len(core) >= 3 and re.search(rf"\b{re.escape(core)}\b", searchable, re.IGNORECASE):
                return core
    return candidates[0]

def _render_interlinear_card(reference: str, original_label: str, is_rtl: bool,
                              cells: list[dict], source: str):
    """Render a word-by-word interlinear grid: original word / [lexeme] /
    transliteration / short gloss, stacked per column, wrapping to new rows
    as needed. Hebrew columns fill each row right-to-left (first word of the
    verse ends up on the right, matching how a printed Hebrew interlinear
    reads); Greek fills left-to-right.

    An optional per-cell "lexeme" key inserts an extra row between the word
    and the transliteration, showing the original-language word in its own
    script -- used by the reverse interlinear (!reverseinterlinear), where
    "word" is the English KJV phrase and is_rtl is always False (English
    reads left-to-right regardless of the source language), so the lexeme
    row needs its own independent RTL check and font per cell."""
    from PIL import Image, ImageDraw, ImageFont
    import io, textwrap

    W = 1300
    BG, BORDER, TEXT, ACCENT, MUTED = (245, 239, 224), (178, 34, 34), (59, 42, 22), (178, 34, 34), (110, 90, 60)
    FONTS = "C:/Windows/Fonts/"
    MARGIN = 60
    COL_GAP, ROW_GAP = 28, 22
    GLOSS_WRAP = 14  # max chars per gloss line before wrapping to a second line

    orig_size, lexeme_size, translit_size, gloss_size, strong_size = 34, 26, 20, 17, 15
    orig_font_path = _script_font(FONTS, "".join(c["word"] for c in cells)) if cells else FONTS + "georgia.ttf"
    orig_font = ImageFont.truetype(orig_font_path, orig_size)
    has_lexeme = any(c.get("lexeme") for c in cells)
    lexeme_font_path = _script_font(FONTS, "".join(c.get("lexeme", "") for c in cells)) if has_lexeme else None
    lexeme_font = ImageFont.truetype(lexeme_font_path, lexeme_size) if lexeme_font_path else None
    # Georgia Italic lacks the macron-vowel characters (ō, ē, etc.) that
    # transliteration schemes use -- Times covers Latin Extended-A as well
    # as the Hebrew/Greek/Cyrillic it's already used for elsewhere.
    translit_font = ImageFont.truetype(FONTS + "timesi.ttf", translit_size)
    gloss_font = ImageFont.truetype(FONTS + "georgia.ttf", gloss_size)
    # Georgia's digits are old-style (varying height/descenders) by default,
    # which reads awkwardly at caption size; Times uses lining (even-height)
    # figures, matching plain "[G2258]"-style reference notation.
    strong_font = ImageFont.truetype(FONTS + "times.ttf", strong_size)

    dummy = ImageDraw.Draw(Image.new("RGB", (10, 10)))

    # Precompute each cell's rendered lines and pixel width.
    laid_out = []
    for c in cells:
        word_logical = c["word"]
        word_width = dummy.textlength(_rtl_visual(word_logical) if is_rtl else word_logical, font=orig_font)
        lexeme_logical = c.get("lexeme", "")
        lexeme_is_rtl = bool(lexeme_logical) and _is_rtl_script(lexeme_logical)
        lexeme_width = (dummy.textlength(_rtl_visual(lexeme_logical) if lexeme_is_rtl else lexeme_logical,
                                          font=lexeme_font) if lexeme_logical else 0)
        translit_lines = [c["translit"]] if c["translit"] else []
        gloss_lines = textwrap.wrap(c["gloss"], width=GLOSS_WRAP)[:2] if c["gloss"] else []
        strong_lines = [c["strong"]] if c.get("strong") else []
        widths = [word_width, lexeme_width]
        widths += [dummy.textlength(l, font=translit_font) for l in translit_lines]
        widths += [dummy.textlength(l, font=gloss_font) for l in gloss_lines]
        widths += [dummy.textlength(l, font=strong_font) for l in strong_lines]
        cell_w = max(widths, default=0)
        cell_h = ((orig_size + 6) + ((lexeme_size + 5) if lexeme_logical else 0)
                  + (translit_size + 4) * len(translit_lines)
                  + (gloss_size + 3) * len(gloss_lines) + (strong_size + 3) * len(strong_lines))
        laid_out.append({"word": word_logical, "word_w": word_width,
                          "lexeme": lexeme_logical, "lexeme_w": lexeme_width, "lexeme_is_rtl": lexeme_is_rtl,
                          "translit": translit_lines,
                          "gloss": gloss_lines, "strong": strong_lines, "w": cell_w, "h": cell_h})

    # Wrap into rows.
    max_row_width = W - 2 * MARGIN
    rows, current_row, current_w = [], [], 0
    for cell in laid_out:
        add_w = cell["w"] + (COL_GAP if current_row else 0)
        if current_row and current_w + add_w > max_row_width:
            rows.append(current_row)
            current_row, current_w = [], 0
            add_w = cell["w"]
        current_row.append(cell)
        current_w += add_w
    if current_row:
        rows.append(current_row)

    row_heights = [max(c["h"] for c in row) for row in rows] if rows else [0]
    TOP, BOTTOM = 110, 90
    H = TOP + sum(row_heights) + ROW_GAP * max(0, len(rows) - 1) + BOTTOM

    img = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(img)
    draw.rectangle([16, 16, W - 17, H - 17], outline=BORDER, width=4)

    title_font = ImageFont.truetype(FONTS + "georgiab.ttf", 36)
    tw = draw.textlength(reference, font=title_font)
    draw.text(((W - tw) / 2, 38), reference, font=title_font, fill=ACCENT)

    y = TOP
    for row, row_h in zip(rows, row_heights):
        row_width = sum(c["w"] for c in row) + COL_GAP * (len(row) - 1)
        x = (W - row_width) / 2
        ordered = list(reversed(row)) if is_rtl else row
        for cell in ordered:
            cw = cell["w"]
            wx = x + (cw - cell["word_w"]) / 2
            if is_rtl:
                _draw_rtl_line(draw, wx, y, cell["word"], orig_font, TEXT)
            else:
                draw.text((wx, y), cell["word"], font=orig_font, fill=TEXT)
            ty = y + orig_size + 6
            if cell["lexeme"]:
                lx = x + (cw - cell["lexeme_w"]) / 2
                if cell["lexeme_is_rtl"]:
                    _draw_rtl_line(draw, lx, ty, cell["lexeme"], lexeme_font, TEXT)
                else:
                    draw.text((lx, ty), cell["lexeme"], font=lexeme_font, fill=TEXT)
                ty += lexeme_size + 5
            for line in cell["translit"]:
                lw = draw.textlength(line, font=translit_font)
                draw.text((x + (cw - lw) / 2, ty), line, font=translit_font, fill=ACCENT)
                ty += translit_size + 4
            for line in cell["gloss"]:
                lw = draw.textlength(line, font=gloss_font)
                draw.text((x + (cw - lw) / 2, ty), line, font=gloss_font, fill=MUTED)
                ty += gloss_size + 3
            for line in cell["strong"]:
                lw = draw.textlength(line, font=strong_font)
                draw.text((x + (cw - lw) / 2, ty), line, font=strong_font, fill=BORDER)
                ty += strong_size + 3
            x += cw + COL_GAP
        y += row_h + ROW_GAP

    label_font = ImageFont.truetype(FONTS + "georgia.ttf", 20)
    lw = draw.textlength(original_label, font=label_font)
    draw.text(((W - lw) / 2, H - 68), original_label, font=label_font, fill=ACCENT)

    src_font = ImageFont.truetype(FONTS + "georgia.ttf", 16)
    sw = draw.textlength(source, font=src_font)
    draw.text(((W - sw) / 2, H - 38), source, font=src_font, fill=MUTED)

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf


@bot.command(name="interlinear", aliases=["inter", "il"])
async def cmd_interlinear(ctx, *, reference: str = ""):
    """Word-by-word interlinear image: original Greek/Hebrew word, transliteration,
    and short gloss stacked under each word. Usage: !interlinear John 3:16
    """
    from poem_lookup import classify_scripture

    ref = reference.strip()
    if not ref:
        await ctx.send("Usage: `!interlinear <verse>` — e.g. `!interlinear John 3:16` or `!interlinear Psalm 23:1`.")
        return

    scripture_type = classify_scripture(ref)
    if scripture_type == "apocrypha":
        await ctx.send("⚠️ Interlinear isn't available for apocryphal books (no Strong's tagging).")
        return
    testament = "nt" if scripture_type == "nt" else "ot"

    ref_single = re.sub(r"(\d+:\d+)[-–]\d+$", r"\1", ref)

    async with ctx.typing():
        loop = asyncio.get_event_loop()
        strongs = await loop.run_in_executor(None, _fetch_strongs_passage, ref_single, testament)

        if not strongs.get("found"):
            await ctx.send(f"⚠️ {strongs.get('error', 'Lookup failed.')}")
            return

        pairs = strongs["pairs"]

        is_rtl = testament == "ot"

        canonical_book = (BIBLE_OT + BIBLE_NT)[strongs["book_id"] - 1]
        local_words = interlinear_lookup.get_verse_words(testament, canonical_book, strongs["chapter"], strongs["verse"])

        cells = []
        if local_words:
            # MACULA (Clear-Bible/Biblica, CC BY 4.0): a real word-aligned
            # interlinear built by linguists, with a per-instance English
            # gloss for each occurrence -- not reconstructed by matching
            # Strong's numbers across two independently-tagged texts (the
            # earlier approach, which broke whenever the two tagging systems
            # disagreed on which number a given inflected form gets).
            for w in local_words:
                translit = w["translit"]
                if not translit and not is_rtl:
                    # MACULA's Greek rows have no per-word transliteration
                    # column (unlike Hebrew's, which has a real one).
                    # Compute it directly from the actual inflected form
                    # shown -- a lexicon lookup by Strong's number would
                    # give the dictionary lemma's transliteration (e.g.
                    # "ho" for ὁ) regardless of which inflected form is
                    # actually on screen (e.g. τὸν, which is "ton").
                    translit = _transliterate_greek(w["text"])
                strong_disp = f"[{w['strong']}]" if w["strong"] else ""
                cells.append({"word": w["text"], "translit": translit, "gloss": w["gloss"], "strong": strong_disp})
            original_label = ("Hebrew OT (WLC, with Strong's)" if is_rtl
                              else "Greek NT (SBLGNT, with Strong's)")
            footer = "MACULA (Clear-Bible/Biblica, Inc., CC BY 4.0) · OpenScriptures Strong's"
        else:
            # MACULA doesn't cover this verse (shouldn't normally happen for
            # a canonical Bible book) -- fall back to the older bolls.life
            # Strong's-tagged text, aligned against the KJV's own tagging by
            # Strong's number where possible.
            if not pairs:
                await ctx.send(f"⚠️ No Strong's-tagged words found for **{ref_single}**.")
                return
            kjv_map = await loop.run_in_executor(
                None, _fetch_kjv_word_map, strongs["book_id"], strongs["chapter"], strongs["verse"]
            )
            for word, num in pairs:
                entry = _fetch_strongs_definition(num)
                translit = (entry or {}).get("transliteration", "") or ""
                candidate_nums = _STRONGS_INFLECTION_FAMILIES.get(num, (num,))
                kjv_word = None
                for cand in candidate_nums:
                    cand_bare = cand[1:]
                    if kjv_map.get(cand_bare):
                        kjv_word = kjv_map[cand_bare].popleft()
                        break
                gloss = kjv_word or _clean_strongs_gloss(
                    (entry or {}).get("short_definition", "") or "", (entry or {}).get("definition", "") or "")
                cells.append({"word": word, "translit": translit, "gloss": gloss, "strong": f"[{num}]"})
            original_label = ("Hebrew OT (WLC, with Strong's)" if is_rtl
                              else "Greek NT (Tischendorf 8th, with Strong's)")
            footer = "bolls.life (KJV + OpenScriptures Strong's)"

        if len(cells) > 60:
            await ctx.send(f"⚠️ That verse has {len(cells)} tagged words — too many for one interlinear image. Try a shorter verse.")
            return

        img_buf = await loop.run_in_executor(
            None, _render_interlinear_card, strongs["ref"], original_label, is_rtl, cells, footer
        )

    record_special_stat(ctx.author.id, "interlinear", strongs["ref"])
    await ctx.send(file=discord.File(img_buf, filename="interlinear.png"))

@bot.tree.command(name="interlinear", description="Word-by-word interlinear image (original word + transliteration + gloss)")
@app_commands.describe(reference="e.g. John 3:16")
async def interlinear_slash(interaction: discord.Interaction, reference: str):
    await interaction.response.defer()
    ctx = await bot.get_context(interaction)
    await cmd_interlinear(ctx, reference=reference)


@bot.command(name="reverseinterlinear", aliases=["rinterlinear", "ril", "kjvinterlinear"])
async def cmd_reverse_interlinear(ctx, *, reference: str = ""):
    """Reverse interlinear image: the actual KJV English text in its own
    reading order, with each word/phrase tagged by the Strong's number of
    the Greek/Hebrew word(s) it translates. Usage: !reverseinterlinear John 3:16
    """
    from poem_lookup import classify_scripture

    ref = reference.strip()
    if not ref:
        await ctx.send("Usage: `!reverseinterlinear <verse>` — e.g. `!reverseinterlinear John 3:16`.")
        return

    scripture_type = classify_scripture(ref)
    if scripture_type == "apocrypha":
        await ctx.send("⚠️ Reverse interlinear isn't available for apocryphal books (no Strong's tagging).")
        return
    testament = "nt" if scripture_type == "nt" else "ot"
    prefix = "G" if testament == "nt" else "H"

    ref_single = re.sub(r"(\d+:\d+)[-–]\d+$", r"\1", ref)

    async with ctx.typing():
        loop = asyncio.get_event_loop()
        strongs = await loop.run_in_executor(None, _fetch_strongs_passage, ref_single, testament)
        if not strongs.get("found"):
            await ctx.send(f"⚠️ {strongs.get('error', 'Lookup failed.')}")
            return

        rows = await loop.run_in_executor(None, _bolls_fetch_chapter, "KJV", strongs["book_id"], strongs["chapter"])
        row = next((v for v in (rows or []) if v.get("verse") == strongs["verse"]), None)
        if not row:
            await ctx.send(f"⚠️ Could not fetch the KJV text for **{strongs['ref']}**.")
            return

        entries = _parse_kjv_reverse_interlinear(row.get("text", ""))
        if not entries:
            await ctx.send(f"⚠️ No Strong's-tagged words found for **{strongs['ref']}**.")
            return

        cells = []
        for e in entries:
            lexeme, translit = "", ""
            if e["strong"]:
                entry = await loop.run_in_executor(None, _fetch_strongs_definition, f"{prefix}{e['strong']}")
                if entry:
                    lexeme = entry.get("lexeme") or ""
                    translit = entry.get("transliteration") or ""
            cells.append({
                "word": e["phrase"], "lexeme": lexeme, "translit": translit, "gloss": "",
                "strong": f"[{prefix}{e['strong']}]" if e["strong"] else "",
            })

        if len(cells) > 60:
            await ctx.send(f"⚠️ That verse has {len(cells)} words — too many for one image. Try a shorter verse.")
            return

        img_buf = await loop.run_in_executor(
            None, _render_interlinear_card, strongs["ref"],
            "King James Version (1769) — reverse interlinear", False, cells,
            "bolls.life (KJV + OpenScriptures Strong's)"
        )

    record_special_stat(ctx.author.id, "reverseinterlinear", strongs["ref"])
    await ctx.send(file=discord.File(img_buf, filename="reverse_interlinear.png"))


@bot.tree.command(name="reverseinterlinear", description="Reverse interlinear image (KJV text in reading order, tagged with Strong's numbers)")
@app_commands.describe(reference="e.g. John 3:16")
async def reverse_interlinear_slash(interaction: discord.Interaction, reference: str):
    await interaction.response.defer()
    ctx = await bot.get_context(interaction)
    await cmd_reverse_interlinear(ctx, reference=reference)


@bot.command(name="concordance", aliases=["occurrences", "conc"])
async def cmd_concordance(ctx, *, arg: str = ""):
    """List every verse tagged with a given Strong's number (see !interlinear).
    Usage: !concordance G26   |  !concordance H430"""
    number = arg.strip().upper()
    if not re.match(r"^[GH]\d+[A-Z]?$", number):
        await ctx.send(
            "Usage: `!concordance G26` or `!concordance H430` — a Strong's number "
            "(bracketed in `!interlinear`/`!reverseinterlinear` output)."
        )
        return

    if not interlinear_lookup.available():
        await ctx.send("⚠️ Interlinear data isn't available right now.")
        return

    rows = interlinear_lookup.get_occurrences(number)
    if not rows:
        await ctx.send(f"No occurrences found for **{number}** in the interlinear dataset.")
        return

    order = {b: i for i, b in enumerate(BIBLE_OT + BIBLE_NT)}
    rows = sorted(rows, key=lambda r: (order.get(r[1], 999), r[2], r[3]))
    refs = [f"{book} {chapter}:{verse}" for _testament, book, chapter, verse in rows]

    entry = get_local_strongs_definition(number)
    header = number
    if entry:
        lex = entry.get("lexeme", "")
        translit = entry.get("transliteration", "")
        gloss = entry.get("short_definition", "")
        header = f"{number} — {lex} ({translit})" if lex else number
        if gloss:
            header += f" — {gloss}"

    PAGE = 20
    total = len(refs)
    pages = [refs[i:i + PAGE] for i in range(0, total, PAGE)]

    def make_embed(idx):
        embed = discord.Embed(
            title=f"🔎 {header}"[:256],
            description="\n".join(pages[idx]),
            color=discord.Color.gold(),
        )
        embed.set_footer(text=f"{total} occurrence{'s' if total != 1 else ''} · page {idx + 1}/{len(pages)} · MACULA (CC BY 4.0)")
        return embed

    if len(pages) == 1:
        await ctx.send(embed=make_embed(0))
        return

    class ConcordanceView(discord.ui.View):
        def __init__(self):
            super().__init__(timeout=180)
            self.idx = 0

        @discord.ui.button(emoji="◀", style=discord.ButtonStyle.secondary)
        async def prev(self, interaction: discord.Interaction, button: discord.ui.Button):
            self.idx = (self.idx - 1) % len(pages)
            await interaction.response.edit_message(embed=make_embed(self.idx), view=self)

        @discord.ui.button(emoji="▶", style=discord.ButtonStyle.secondary)
        async def next(self, interaction: discord.Interaction, button: discord.ui.Button):
            self.idx = (self.idx + 1) % len(pages)
            await interaction.response.edit_message(embed=make_embed(self.idx), view=self)

        async def on_timeout(self):
            try:
                await self.message.edit(view=None)
            except Exception:
                pass

    view = ConcordanceView()
    view.message = await ctx.send(embed=make_embed(0), view=view)


@bot.tree.command(name="concordance", description="List every verse tagged with a given Strong's number")
@app_commands.describe(number="e.g. G26 or H430")
async def concordance_slash(interaction: discord.Interaction, number: str):
    await interaction.response.defer()
    ctx = await bot.get_context(interaction)
    await cmd_concordance(ctx, arg=number)


def _make_card_text_button(reference: str, content_lines: list[str]) -> discord.ui.Button:
    """A button under a !card image that posts the same content as copyable
    plain text (ephemeral, so it doesn't clutter the channel)."""
    btn = discord.ui.Button(label="📋 Text version", style=discord.ButtonStyle.secondary)
    text_block = f"**{reference}**\n" + "\n".join(content_lines)
    if len(text_block) > 1900:
        text_block = text_block[:1897] + "…"

    async def callback(interaction: discord.Interaction):
        await interaction.response.send_message(text_block, ephemeral=True)

    btn.callback = callback
    return btn


@bot.command(name="card", aliases=["versecard", "quotecard"])
async def cmd_card(ctx, *, reference: str = ""):
    """Render a verse as a shareable image.
    Usage: !card John 3:16              — KJV
           !card James 2:19 ESV         — a specific translation
           !card John 3:16 KJV ESV NASB — up to 4 translations compared, stacked
    """
    ref = reference.strip()
    if not ref or ref.lower() == "random":
        result = None
        if not ref:
            cached = _LAST_CITED.get(ctx.channel.id)
            if cached and cached.get("text"):
                result = dict(cached, found=True)
        if result is None:
            result = lookup.random_verse()
        if not result.get("found"):
            await ctx.send(f"⚠️ {result.get('error', 'Verse not found.')}")
            return
        async with ctx.typing():
            loop = asyncio.get_event_loop()
            buf = await loop.run_in_executor(
                None, _render_verse_card, result["reference"], result["text"], result.get("source", "")
            )
        text_view = discord.ui.View(timeout=180)
        text_view.add_item(_make_card_text_button(result["reference"], [result["text"], f"*{result.get('source', '')}*"]))
        await ctx.send(file=discord.File(buf, filename="verse.png"), view=text_view)
        record_stat(ctx.author.id, "card", result)
        return

    tokens = ref.split()
    i = len(tokens) - 1
    trans_list = []
    while i >= 0 and tokens[i].lower() in TRANSLATION_SUFFIXES:
        trans_list.insert(0, tokens[i])
        i -= 1
    base_ref = " ".join(tokens[:i + 1])

    if len(trans_list) >= 2:
        async with ctx.typing():
            result = get_parallel(base_ref, trans_list[:4])
        if not result.get("found"):
            await ctx.send(f"⚠️ {result.get('error', 'Verse not found.')}")
            return
        entries = [(label, text) for _slug, label, text in result["parallel"]]
        async with ctx.typing():
            loop = asyncio.get_event_loop()
            buf = await loop.run_in_executor(None, _render_compare_card, result["reference"], entries)
        text_view = discord.ui.View(timeout=180)
        text_view.add_item(_make_card_text_button(result["reference"], [f"**{label}**\n{text}" for label, text in entries]))
        await ctx.send(file=discord.File(buf, filename="compare.png"), view=text_view)
        record_stat(ctx.author.id, "card", result)
        if len(trans_list) > 4:
            await ctx.send("Comparison cards show up to 4 translations at a time — showing the first 4.")
        return

    if len(trans_list) == 1:
        async with ctx.typing():
            result = get_translation(base_ref, trans_list[0])
    else:
        result = lookup.get_verse(ref)
        if not result.get("found") and "Could not parse" in result.get("error", ""):
            result = lookup.random_verse_from_book(ref)

    if not result.get("found"):
        await ctx.send(f"⚠️ {result.get('error', 'Verse not found.')}")
        return

    async with ctx.typing():
        loop = asyncio.get_event_loop()
        buf = await loop.run_in_executor(
            None, _render_verse_card, result["reference"], result["text"], result.get("source", "")
        )
    text_view = discord.ui.View(timeout=180)
    text_view.add_item(_make_card_text_button(result["reference"], [result["text"], f"*{result.get('source', '')}*"]))
    await ctx.send(file=discord.File(buf, filename="verse.png"), view=text_view)
    record_stat(ctx.author.id, "card", result)

@bot.tree.command(name="card", description="Render a verse as a shareable image")
@app_commands.describe(reference="e.g. John 3:16 (leave blank for a random verse)")
async def card_slash(interaction: discord.Interaction, reference: str = ""):
    await interaction.response.defer()
    ctx = await bot.get_context(interaction)
    await cmd_card(ctx, reference=reference)


# ── Auto-detection ─────────────────────────────────────────────────────────────

@bot.event
async def on_guild_join(guild: discord.Guild):
    """Introduce the opt-in features to a new server's admins."""
    channel = guild.system_channel
    if channel is None or not channel.permissions_for(guild.me).send_messages:
        channel = next(
            (c for c in guild.text_channels if c.permissions_for(guild.me).send_messages),
            None,
        )
    if channel is None:
        return

    embed = discord.Embed(
        title="📖 Thanks for adding ScriptureBot!",
        description=(
            "Run `!help` any time for the full command list. A few things worth setting up:\n\n"
            "`!votdsetup channel #general` — a daily Verse of the Day post for this server\n\n"
            "**Optional features (all off by default)** — an admin turns these on with `!features <name> on`:\n"
            + "\n".join(f"• `{k}` — {v}" for k, v in GUILD_FEATURES.items())
        ),
        color=discord.Color.dark_gold(),
    )
    embed.set_footer(text="!features to see current settings · !help votdsetup for VOTD setup")
    try:
        await channel.send(embed=embed)
    except discord.Forbidden:
        pass


@bot.event
async def on_raw_reaction_add(payload: discord.RawReactionActionEvent):
    """React 📌 on a verse embed (opt-in per guild via !features react_save) to bookmark it."""
    if payload.member is None or payload.member.bot:
        return
    if str(payload.emoji) != "📌":
        return
    if not payload.guild_id or not _get_guild_features(payload.guild_id).get("react_save"):
        return

    channel = bot.get_channel(payload.channel_id)
    if channel is None:
        return
    try:
        message = await channel.fetch_message(payload.message_id)
    except (discord.NotFound, discord.Forbidden):
        return
    if message.author.id != bot.user.id or not message.embeds:
        return
    # Only react to messages the bot itself tagged with 📌 on send — scopes this
    # to _send_result's verse embeds, not every embed the bot happens to post.
    if not any(str(r.emoji) == "📌" and r.me for r in message.reactions):
        return

    title = message.embeds[0].title or ""
    reference = re.sub(r"\s*\(\d+/\d+\)\s*$", "", title).strip()
    if not reference:
        return
    result = lookup.get_verse(reference)
    if not result.get("found"):
        return

    data = _load_bookmarks()
    uid = str(payload.user_id)
    entries = data.setdefault(uid, [])
    canon_ref = result["reference"]
    if any(e["reference"] == canon_ref for e in entries):
        return
    import datetime
    entries.append({
        "reference": canon_ref,
        "source": result.get("source", ""),
        "saved_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    })
    _save_bookmarks(data)
    try:
        await channel.send(f"📌 Saved **{canon_ref}** for {payload.member.mention}.", delete_after=8)
    except Exception:
        pass


@bot.event
async def on_message(message: discord.Message):
    # Never respond to ourselves or other bots
    if message.author.bot:
        return

    # Still process !commands normally
    await bot.process_commands(message)

    # Don't double-trigger on explicit !verse commands
    if message.content.startswith("!"):
        return

    # Scan the message for scripture references
    matches = _AUTO_RE.findall(message.content)
    if not matches:
        return

    # De-duplicate while preserving order
    seen = set()
    unique = []
    for m in matches:
        book, chap, verse, end_verse = m
        ref = f"{book.strip()} {chap}:{verse}"
        if end_verse:
            ref += f"-{end_verse}"
        if ref.lower() not in seen:
            seen.add(ref.lower())
            unique.append(ref)

    if not unique:
        return

    # Only respond if at least one reference actually resolves to a real verse
    embeds = []
    content = message.content
    for ref in unique[:3]:
        escaped = re.escape(ref)
        suffix_m = re.search(escaped + r"\s+(\S+)", content, re.IGNORECASE)
        suffix = suffix_m.group(1).lower() if suffix_m else ""

        if suffix in TRANSLATION_SUFFIXES:
            result = get_translation(ref, suffix)
        elif suffix in DRB_SUFFIXES:
            result = get_verse_drb(ref)
        elif suffix in KNOX_SUFFIXES:
            result = get_verse_knox(ref)
        else:
            result = lookup.get_verse(ref)

        if result["found"]:
            embeds.append(_build_embed(result))

    for embed in embeds:
        await message.channel.send(embed=embed)

# ── Helpers ────────────────────────────────────────────────────────────────────

def _build_embed(result: dict) -> discord.Embed:
    """Build a single embed — used by auto-detection in on_message."""
    if result["found"]:
        embed = discord.Embed(
            title=result["reference"],
            description=result["text"][:3900],
            color=discord.Color.dark_gold()
        )
        embed.set_footer(text=result["source"])
    else:
        embed = discord.Embed(
            title="Not found",
            description=result["error"],
            color=discord.Color.red()
        )
        if result.get("suggestions"):
            embed.add_field(
                name="Did you mean?",
                value="\n".join(result["suggestions"]),
                inline=False
            )
    return embed


def _chunk(text: str, size: int) -> list[str]:
    return [text[i:i+size] for i in range(0, len(text), size)]


async def _maybe_react_savable(ctx_or_interaction, msg):
    """Add a 📌 bookmark reaction to a verse embed, if this guild opted into react_save."""
    guild = getattr(ctx_or_interaction, "guild", None)
    if not guild or not msg:
        return
    if not _get_guild_features(guild.id).get("react_save"):
        return
    try:
        await msg.add_reaction("📌")
    except Exception:
        pass


_LAST_CITED: dict[int, dict] = {}  # channel_id -> {"reference","text","source"}


def _record_last_cited(ctx_or_interaction, result: dict):
    """Remember the last single verse successfully shown in this channel,
    so a bare !card can reuse it. Skips whole-chapter/multi-page results --
    a card is meant for one quotable verse, not a chapter."""
    if not result.get("found"):
        return
    pages = result.get("pages")
    if pages and len(pages) > 1:
        return
    channel = getattr(ctx_or_interaction, "channel", None) or ctx_or_interaction
    channel_id = getattr(channel, "id", None)
    if channel_id is None:
        return
    _LAST_CITED[channel_id] = {
        "reference": result.get("reference", ""),
        "text": result.get("text", ""),
        "source": result.get("source", ""),
    }


# ── !books chapter picker: "Next/Prev chapter" buttons ───────────────────────

_chapter_nav_cooldown: dict[int, float] = {}  # user_id -> last-click monotonic time
_CHAPTER_NAV_COOLDOWN_SECONDS = 3.0


def _check_chapter_nav_cooldown(user_id: int) -> bool:
    now = time.monotonic()
    last = _chapter_nav_cooldown.get(user_id, 0.0)
    if now - last < _CHAPTER_NAV_COOLDOWN_SECONDS:
        return False
    _chapter_nav_cooldown[user_id] = now
    return True


def _fetch_chapter_result(book_name: str, chap_label: str, mode: str) -> dict:
    """Fetch one chapter/section, in the same shape _send_result expects,
    for either a local/Sefaria "verse" reference or a hadith section."""
    if mode != "hadith":
        return lookup.get_verse(f"{book_name} {chap_label}")

    key = _HADITH_DISPLAY_TO_KEY.get(book_name)
    try:
        section_num = int(chap_label.replace("Book ", "").strip())
    except ValueError:
        section_num = None
    if not key or section_num is None:
        return {"found": False, "error": "Could not resolve this hadith section.", "suggestions": []}
    data = get_hadith_section(key, section_num)
    if not data:
        return {"found": False, "error": f"Could not fetch {chap_label} of {book_name} right now.", "suggestions": []}

    name = data.get("name") or ""
    items = data["hadiths"]
    title = f"{book_name} — Book {section_num}" + (f": {name}" if name else "")
    MAX = 3500
    pages: list[str] = []
    current = ""
    for num, text in items:
        entry = f"**[{num}]** {text}"
        if current and len(current) + len(entry) + 2 > MAX:
            pages.append(current)
            current = entry
        else:
            current = f"{current}\n\n{entry}" if current else entry
    if current:
        pages.append(current)
    return {
        "found": True,
        "reference": title,
        "text": pages[0] if pages else "",
        "source": f"{book_name} (fawazahmed0 Hadith API)",
        "pages": pages,
    }


def _make_chapter_nav_button(book_name: str, chapter_labels: list[str], index: int, mode: str, direction: str) -> "discord.ui.Button | None":
    """Button that fetches the chapter before/after index as a new message
    with its own nav buttons, or None if index is already at that end."""
    target = index + 1 if direction == "next" else index - 1
    if not (0 <= target < len(chapter_labels)):
        return None
    target_label = chapter_labels[target]
    if direction == "next":
        btn = discord.ui.Button(label=f"Next chapter ▶ {target_label}"[:80], style=discord.ButtonStyle.success)
    else:
        btn = discord.ui.Button(label=f"◀ Prev chapter {target_label}"[:80], style=discord.ButtonStyle.secondary)

    async def callback(interaction: discord.Interaction):
        if not _check_chapter_nav_cooldown(interaction.user.id):
            await interaction.response.send_message(
                "⏳ Please wait a few seconds before requesting another chapter.", ephemeral=True
            )
            return
        # Erase this button from the message it's on so it can't be pressed
        # again -- also serves as the interaction's initial response, so the
        # actual fetch (which may be a slow network call, for hadith) is
        # free to take as long as it needs via followup.send.
        parent_view = btn.view
        if parent_view is not None:
            parent_view.remove_item(btn)
            await interaction.response.edit_message(view=parent_view)
        else:
            await interaction.response.defer()
        result = _fetch_chapter_result(book_name, target_label, mode)
        nav_btns = _make_chapter_nav_buttons(book_name, chapter_labels, target, mode)
        await _send_result(interaction, result, extra_buttons=nav_btns)

    btn.callback = callback
    return btn


def _make_chapter_nav_buttons(book_name: str, chapter_labels: list[str], index: int, mode: str) -> list:
    """[prev_button?, next_button?] for the chapter at this index."""
    btns = []
    prev_btn = _make_chapter_nav_button(book_name, chapter_labels, index, mode, "prev")
    if prev_btn:
        btns.append(prev_btn)
    next_btn = _make_chapter_nav_button(book_name, chapter_labels, index, mode, "next")
    if next_btn:
        btns.append(next_btn)
    return btns


async def _send_result(ctx_or_interaction, result: dict, extra_buttons: "list | None" = None):
    """Send a verse or whole-chapter result, splitting across multiple embeds if needed.
    extra_buttons, if given, are appended to whatever view the result ends up
    using (a bare view is created for them if the result wouldn't otherwise
    have one) -- used for the !books chapter picker's prev/next-chapter buttons."""
    extra_buttons = extra_buttons or []
    try:
        uid = (ctx_or_interaction.user.id
               if hasattr(ctx_or_interaction, "user")
               else ctx_or_interaction.author.id)
        record_stat(uid, "verse", result)
    except Exception:
        pass
    _record_last_cited(ctx_or_interaction, result)

    is_interaction = hasattr(ctx_or_interaction, "response")
    already_responded = is_interaction and ctx_or_interaction.response.is_done()

    async def _reply(**kwargs):
        """Send the first message for this result, respecting whether the
        interaction has already been responded to/deferred."""
        if already_responded:
            return await ctx_or_interaction.followup.send(**kwargs)
        if is_interaction:
            await ctx_or_interaction.response.send_message(**kwargs)
            return await ctx_or_interaction.original_response()
        return await ctx_or_interaction.send(**kwargs)

    if not result["found"]:
        embed = _build_embed(result)
        view = None
        if extra_buttons:
            view = discord.ui.View(timeout=180)
            for b in extra_buttons:
                view.add_item(b)
        await _reply(embed=embed, view=view) if view else await _reply(embed=embed)
        return

    # ── Paginated whole-chapter result ────────────────────────────────────────
    pages = result.get("pages")
    if pages and len(pages) > 1:
        ref    = result["reference"]
        source = result["source"]
        total  = len(pages)

        def make_page_embed(idx):
            text = pages[idx]
            if len(text) > 3900:
                text = text[:3897] + "…"
            embed = discord.Embed(
                title=f"{ref} ({idx + 1}/{total})",
                description=text,
                color=discord.Color.dark_gold()
            )
            embed.set_footer(text=source)
            return embed

        class ChapterView(discord.ui.View):
            def __init__(self):
                super().__init__(timeout=180)
                self.idx = 0
                for b in extra_buttons:
                    self.add_item(b)

            @discord.ui.button(emoji="◀", style=discord.ButtonStyle.secondary, row=0)
            async def prev(self, interaction: discord.Interaction, button: discord.ui.Button):
                self.idx = (self.idx - 1) % total
                await interaction.response.edit_message(embed=make_page_embed(self.idx), view=self)

            @discord.ui.button(emoji="▶", style=discord.ButtonStyle.secondary, row=0)
            async def next(self, interaction: discord.Interaction, button: discord.ui.Button):
                self.idx = (self.idx + 1) % total
                await interaction.response.edit_message(embed=make_page_embed(self.idx), view=self)

            async def on_timeout(self):
                try:
                    await self.message.edit(view=None)
                except Exception:
                    pass

        view = ChapterView()
        view.message = await _reply(embed=make_page_embed(0), view=view)
        await _maybe_react_savable(ctx_or_interaction, view.message)
        return

    MAX = 3900
    text   = result["text"]
    title  = result["reference"]
    source = result["source"]

    if len(text) <= MAX:
        embed = discord.Embed(title=title, description=text, color=discord.Color.dark_gold())
        embed.set_footer(text=source)
        view = None
        if extra_buttons:
            view = discord.ui.View(timeout=180)
            for b in extra_buttons:
                view.add_item(b)
        msg = await (_reply(embed=embed, view=view) if view else _reply(embed=embed))
        await _maybe_react_savable(ctx_or_interaction, msg)
        return

    # Split long text into chunks at sentence or line boundaries
    chunks = []
    current = ""
    # Split on newlines first; if text is one long blob, split on sentences
    lines = text.split("\n")
    if len(lines) == 1 and len(text) > MAX:
        # No newlines — split on sentence boundaries
        sentences = re.split(r'(?<=[.!?])\s+', text)
        lines = sentences

    for line in lines:
        if len(current) + len(line) + 1 > MAX and current:
            chunks.append(current.strip())
            current = line
        else:
            current = (current + "\n" + line) if current else line
    if current:
        chunks.append(current.strip())

    for i, chunk in enumerate(chunks):
        part_title = title if len(chunks) == 1 else f"{title} ({i+1}/{len(chunks)})"
        embed = discord.Embed(title=part_title, description=chunk, color=discord.Color.dark_gold())
        is_last = i == len(chunks) - 1
        if is_last:
            embed.set_footer(text=source)
        view = None
        if is_last and extra_buttons:
            view = discord.ui.View(timeout=180)
            for b in extra_buttons:
                view.add_item(b)
        if i == 0:
            msg = await (_reply(embed=embed, view=view) if view else _reply(embed=embed))
        else:
            channel = ctx_or_interaction.channel if is_interaction else ctx_or_interaction
            msg = await (channel.send(embed=embed, view=view) if view else channel.send(embed=embed))
        if is_last:
            await _maybe_react_savable(ctx_or_interaction, msg)


async def _send_parallel(ctx_or_interaction, result: dict):
    """Send a parallel translation embed."""
    if not result.get("found"):
        embed = discord.Embed(title="Error", description=result.get("error", "Unknown error"),
                              color=discord.Color.red())
        if hasattr(ctx_or_interaction, "followup"):
            await ctx_or_interaction.followup.send(embed=embed)
        else:
            await ctx_or_interaction.send(embed=embed)
        return

    ref = result["reference"]
    embed = discord.Embed(title=f"📖 {ref}", color=discord.Color.dark_gold())
    for slug, display_name, text in result["parallel"]:
        if len(text) > 1024:
            text = text[:1021] + "…"
        embed.add_field(name=f"**{slug}**", value=text, inline=False)
    embed.set_footer(text=" · ".join(display_name for _, display_name, _ in result["parallel"]))

    if hasattr(ctx_or_interaction, "followup"):
        await ctx_or_interaction.followup.send(embed=embed)
    else:
        await ctx_or_interaction.send(embed=embed)


def _build_local_search_embed(query, results, offset, total, page_size):
    PAGE = page_size
    page_num    = offset // PAGE + 1
    total_pages = max(1, (total + PAGE - 1) // PAGE)
    embed = discord.Embed(title=f'🔍 "{query}"', color=discord.Color.gold())
    embed.set_footer(text=f"Page {page_num}/{total_pages} · {total} result{'s' if total != 1 else ''} — local corpus")
    for r in results:
        snippet = r["text"]
        idx = snippet.lower().find(query.lower())
        if idx != -1:
            snippet = snippet[:idx] + "**" + snippet[idx:idx+len(query)] + "**" + snippet[idx+len(query):]
        if len(snippet) > 280:
            start = max(0, idx - 60) if idx != -1 else 0
            snippet = ("…" if start else "") + snippet[start:start+280] + "…"
        embed.add_field(name=r["reference"], value=f"{snippet}\n*{r['source']}*", inline=False)

    class LocalSearchView(discord.ui.View):
        def __init__(self):
            super().__init__(timeout=180)
            self._offset = offset
            if page_num > 1:
                b = discord.ui.Button(label="◀ Prev", style=discord.ButtonStyle.secondary)
                async def prev(interaction: discord.Interaction):
                    new_off = max(0, self._offset - PAGE)
                    res, tot = lookup.search(query, limit=PAGE, offset=new_off)
                    e, v = _build_local_search_embed(query, res, new_off, tot, PAGE)
                    v.message = self.message
                    await interaction.response.edit_message(embed=e, view=v)
                b.callback = prev
                self.add_item(b)
            self.add_item(discord.ui.Button(label=f"{page_num}/{total_pages}",
                                            style=discord.ButtonStyle.secondary, disabled=True))
            if page_num < total_pages:
                b = discord.ui.Button(label="Next ▶", style=discord.ButtonStyle.secondary)
                async def nxt(interaction: discord.Interaction):
                    new_off = self._offset + PAGE
                    res, tot = lookup.search(query, limit=PAGE, offset=new_off)
                    e, v = _build_local_search_embed(query, res, new_off, tot, PAGE)
                    v.message = self.message
                    await interaction.response.edit_message(embed=e, view=v)
                b.callback = nxt
                self.add_item(b)

        async def on_timeout(self):
            try:
                await self.message.edit(view=None)
            except Exception:
                pass

    return embed, LocalSearchView()


def _build_bolls_search_embed(query, trans, data):
    results     = data.get("results", [])
    total       = data.get("total", 0)
    page        = data.get("page", 1)
    total_pages = data.get("total_pages", 1)
    slug        = data.get("translation", trans.upper())
    display     = data.get("display_name", slug)

    embed = discord.Embed(title=f'🔍 "{query}" — {slug}', color=discord.Color.gold())
    embed.set_footer(text=f"Page {page}/{total_pages} · {total} result{'s' if total != 1 else ''} — {display}")
    for r in results:
        snippet = r["text"]
        idx = snippet.lower().find(query.lower())
        if idx != -1:
            snippet = snippet[:idx] + "**" + snippet[idx:idx+len(query)] + "**" + snippet[idx+len(query):]
        if len(snippet) > 280:
            start = max(0, idx - 60) if idx != -1 else 0
            snippet = ("…" if start else "") + snippet[start:start+280] + "…"
        embed.add_field(name=r["reference"], value=snippet, inline=False)

    class BollsSearchView(discord.ui.View):
        def __init__(self):
            super().__init__(timeout=180)
            if page > 1:
                b = discord.ui.Button(label="◀ Prev", style=discord.ButtonStyle.secondary)
                async def prev(interaction: discord.Interaction):
                    new_data = search_translation(query, trans, page=page - 1)
                    e, v = _build_bolls_search_embed(query, trans, new_data)
                    v.message = self.message
                    await interaction.response.edit_message(embed=e, view=v)
                b.callback = prev
                self.add_item(b)
            self.add_item(discord.ui.Button(label=f"{page}/{total_pages}",
                                            style=discord.ButtonStyle.secondary, disabled=True))
            if page < total_pages:
                b = discord.ui.Button(label="Next ▶", style=discord.ButtonStyle.secondary)
                async def nxt(interaction: discord.Interaction):
                    new_data = search_translation(query, trans, page=page + 1)
                    e, v = _build_bolls_search_embed(query, trans, new_data)
                    v.message = self.message
                    await interaction.response.edit_message(embed=e, view=v)
                b.callback = nxt
                self.add_item(b)

        async def on_timeout(self):
            try:
                await self.message.edit(view=None)
            except Exception:
                pass

    return embed, BollsSearchView()


# ── Startup ────────────────────────────────────────────────────────────────────

# ── !ccc / !canon — Catechism and Canon Law ───────────────────────────────────

_CCC_DATA   = None
_CANON_DATA = None

def _load_ccc():
    global _CCC_DATA
    if _CCC_DATA is None:
        import json, pathlib
        path = pathlib.Path(__file__).parent / "data" / "catechism.json"
        if path.exists():
            entries = json.loads(path.read_text(encoding="utf-8"))
            _CCC_DATA = {e["id"]: e["text"].strip() for e in entries}
    return _CCC_DATA

def _load_canon():
    global _CANON_DATA
    if _CANON_DATA is None:
        import json, pathlib
        path = pathlib.Path(__file__).parent / "data" / "canon.json"
        if path.exists():
            entries = json.loads(path.read_text(encoding="utf-8"))
            _CANON_DATA = {}
            for e in entries:
                if "text" in e:
                    _CANON_DATA[e["id"]] = e["text"].strip()
                elif "sections" in e:
                    # Join numbered sub-sections
                    parts = []
                    for s in e["sections"]:
                        parts.append(f"§{s['id']}. {s['text'].strip()}")
                    _CANON_DATA[e["id"]] = "\n\n".join(parts)
    return _CANON_DATA

@bot.command(name="ccc")
async def cmd_ccc(ctx, *, args: str = ""):
    """Look up a paragraph of the Catechism of the Catholic Church. Usage: !ccc 1"""
    try:
        number = int(args.strip())
    except ValueError:
        await ctx.send("Usage: `!ccc <paragraph number>` (1–2865)")
        return
    if number <= 0:
        await ctx.send("Usage: `!ccc <paragraph number>` (1–2865)")
        return
    data = _load_ccc()
    if data is None:
        await ctx.send("⚠️ catechism.json not found in data folder.")
        return
    text = data.get(number)
    if text is None:
        await ctx.send(f"⚠️ Paragraph {number} not found. Valid range: 1–{max(data.keys())}.")
        return
    text = re.sub(r'\*+', '', text)
    if len(text) > 4000:
        text = text[:3997] + "…"
    embed = discord.Embed(
        title=f"CCC {number}",
        description=text,
        color=discord.Color.gold()
    )
    embed.set_footer(text="Catechism of the Catholic Church")
    record_special_stat(ctx.author.id, "ccc", f"CCC {number}")
    await ctx.send(embed=embed)


@bot.command(name="canon")
async def cmd_canon(ctx, *, args: str = ""):
    """Look up a canon of the Code of Canon Law. Usage: !canon 1"""
    try:
        number = int(args.strip())
    except ValueError:
        await ctx.send("Usage: `!canon <canon number>` (1–1751)")
        return
    if number <= 0:
        await ctx.send("Usage: `!canon <canon number>` (1–1751)")
        return
    data = _load_canon()
    if data is None:
        await ctx.send("⚠️ canon.json not found in data folder.")
        return
    text = data.get(number)
    if text is None:
        await ctx.send(f"⚠️ Canon {number} not found. Valid range: 1–{max(data.keys())}.")
        return
    text = re.sub(r'\*+', '', text)
    if len(text) > 4000:
        text = text[:3997] + "…"
    embed = discord.Embed(
        title=f"Canon {number}",
        description=text,
        color=discord.Color.dark_red()
    )
    embed.set_footer(text="Code of Canon Law (1983)")
    record_special_stat(ctx.author.id, "canon", f"Canon {number}")
    await ctx.send(embed=embed)


# ── !creed — The three ecumenical creeds, traditional (1662 BCP) English ────────

CREEDS = {
    "apostles": {
        "title": "The Apostles' Creed",
        "text": (
            "I believe in God the Father Almighty, Maker of heaven and earth:\n\n"
            "And in Jesus Christ his only Son our Lord, Who was conceived by the Holy Ghost, "
            "Born of the Virgin Mary, Suffered under Pontius Pilate, Was crucified, dead, and buried, "
            "He descended into hell; The third day he rose again from the dead, He ascended into heaven, "
            "And sitteth on the right hand of God the Father Almighty; From thence he shall come to judge "
            "the quick and the dead.\n\n"
            "I believe in the Holy Ghost; The holy Catholick Church; The Communion of Saints; "
            "The Forgiveness of sins; The Resurrection of the body, And the life everlasting. Amen."
        ),
        "latin_title": "Symbolum Apostolorum",
        "latin": (
            "Credo in Deum Patrem omnipotentem, Creatorem caeli et terrae.\n\n"
            "Et in Iesum Christum, Filium eius unicum, Dominum nostrum, qui conceptus est de Spiritu Sancto, "
            "natus ex Maria Virgine, passus sub Pontio Pilato, crucifixus, mortuus, et sepultus, "
            "descendit ad inferos, tertia die resurrexit a mortuis, ascendit ad caelos, "
            "sedet ad dexteram Dei Patris omnipotentis, inde venturus est iudicare vivos et mortuos.\n\n"
            "Credo in Spiritum Sanctum, sanctam Ecclesiam catholicam, sanctorum communionem, "
            "remissionem peccatorum, carnis resurrectionem, vitam aeternam. Amen."
        ),
    },
    "nicene": {
        "title": "The Nicene Creed",
        "text": (
            "I believe in one God the Father Almighty, Maker of heaven and earth, And of all things "
            "visible and invisible:\n\n"
            "And in one Lord Jesus Christ, the only-begotten Son of God, Begotten of his Father before "
            "all worlds, God of God, Light of Light, Very God of very God, Begotten, not made, "
            "Being of one substance with the Father, By whom all things were made; Who for us men, "
            "and for our salvation, came down from heaven, And was incarnate by the Holy Ghost of the "
            "Virgin Mary, And was made man, And was crucified also for us under Pontius Pilate; "
            "He suffered and was buried, And the third day he rose again according to the Scriptures, "
            "And ascended into heaven, And sitteth on the right hand of the Father; And he shall come "
            "again with glory to judge both the quick and the dead: Whose kingdom shall have no end.\n\n"
            "And I believe in the Holy Ghost, The Lord and Giver of Life, Who proceedeth from the Father "
            "and the Son, Who with the Father and the Son together is worshipped and glorified, "
            "Who spake by the Prophets. And I believe one Catholick and Apostolick Church. "
            "I acknowledge one Baptism for the remission of sins. And I look for the Resurrection of "
            "the dead, And the life of the world to come. Amen."
        ),
        "latin_title": "Symbolum Nicaenum-Constantinopolitanum",
        "latin": (
            "Credo in unum Deum, Patrem omnipotentem, factorem caeli et terrae, "
            "visibilium omnium et invisibilium.\n\n"
            "Et in unum Dominum Iesum Christum, Filium Dei unigenitum, et ex Patre natum ante omnia saecula. "
            "Deum de Deo, lumen de lumine, Deum verum de Deo vero, genitum, non factum, consubstantialem "
            "Patri: per quem omnia facta sunt. Qui propter nos homines et propter nostram salutem descendit "
            "de caelis. Et incarnatus est de Spiritu Sancto ex Maria Virgine, et homo factus est. "
            "Crucifixus etiam pro nobis sub Pontio Pilato, passus et sepultus est, et resurrexit tertia die, "
            "secundum Scripturas, et ascendit in caelum, sedet ad dexteram Patris. Et iterum venturus est "
            "cum gloria, iudicare vivos et mortuos, cuius regni non erit finis.\n\n"
            "Et in Spiritum Sanctum, Dominum et vivificantem, qui ex Patre Filioque procedit. Qui cum Patre "
            "et Filio simul adoratur et conglorificatur: qui locutus est per prophetas. Et unam, sanctam, "
            "catholicam et apostolicam Ecclesiam. Confiteor unum baptisma in remissionem peccatorum. "
            "Et exspecto resurrectionem mortuorum, et vitam venturi saeculi. Amen."
        ),
        "greek_title": "Σύμβολον τῆς Νικαίας-Κωνσταντινουπόλεως",
        "greek": (
            "Πιστεύω εἰς ἕνα Θεόν, Πατέρα, Παντοκράτορα, ποιητὴν οὐρανοῦ καὶ γῆς, "
            "ὁρατῶν τε πάντων καὶ ἀοράτων.\n\n"
            "Καὶ εἰς ἕνα Κύριον Ἰησοῦν Χριστόν, τὸν Υἱὸν τοῦ Θεοῦ τὸν μονογενῆ, τὸν ἐκ τοῦ Πατρὸς "
            "γεννηθέντα πρὸ πάντων τῶν αἰώνων· φῶς ἐκ φωτός, Θεὸν ἀληθινὸν ἐκ Θεοῦ ἀληθινοῦ, γεννηθέντα "
            "οὐ ποιηθέντα, ὁμοούσιον τῷ Πατρί, δι' οὗ τὰ πάντα ἐγένετο. Τὸν δι' ἡμᾶς τοὺς ἀνθρώπους καὶ "
            "διὰ τὴν ἡμετέραν σωτηρίαν κατελθόντα ἐκ τῶν οὐρανῶν καὶ σαρκωθέντα ἐκ Πνεύματος Ἁγίου καὶ "
            "Μαρίας τῆς Παρθένου καὶ ἐνανθρωπήσαντα. Σταυρωθέντα τε ὑπὲρ ἡμῶν ἐπὶ Ποντίου Πιλάτου, καὶ "
            "παθόντα καὶ ταφέντα. Καὶ ἀναστάντα τῇ τρίτῃ ἡμέρᾳ κατὰ τὰς Γραφάς. Καὶ ἀνελθόντα εἰς τοὺς "
            "οὐρανοὺς καὶ καθεζόμενον ἐκ δεξιῶν τοῦ Πατρός. Καὶ πάλιν ἐρχόμενον μετὰ δόξης κρῖναι ζῶντας "
            "καὶ νεκρούς, οὗ τῆς βασιλείας οὐκ ἔσται τέλος.\n\n"
            "Καὶ εἰς τὸ Πνεῦμα τὸ Ἅγιον, τὸ κύριον, τὸ ζῳοποιόν, τὸ ἐκ τοῦ Πατρὸς ἐκπορευόμενον, τὸ σὺν "
            "Πατρὶ καὶ Υἱῷ συμπροσκυνούμενον καὶ συνδοξαζόμενον, τὸ λαλῆσαν διὰ τῶν προφητῶν. Εἰς μίαν, "
            "Ἁγίαν, Καθολικὴν καὶ Ἀποστολικὴν Ἐκκλησίαν. Ὁμολογῶ ἓν βάπτισμα εἰς ἄφεσιν ἁμαρτιῶν. "
            "Προσδοκῶ ἀνάστασιν νεκρῶν. Καὶ ζωὴν τοῦ μέλλοντος αἰῶνος. Ἀμήν."
        ),
    },
    "athanasian": {
        "title": "The Athanasian Creed (Quicunque Vult)",
        "text": (
            "Whosoever will be saved: before all things it is necessary that he hold the Catholick Faith.\n"
            "Which Faith except every one do keep whole and undefiled: without doubt he shall perish everlastingly.\n\n"
            "And the Catholick Faith is this: That we worship one God in Trinity, and Trinity in Unity;\n"
            "Neither confounding the Persons: nor dividing the Substance.\n"
            "For there is one Person of the Father, another of the Son: and another of the Holy Ghost.\n"
            "But the Godhead of the Father, of the Son, and of the Holy Ghost, is all one: the Glory equal, "
            "the Majesty co-eternal.\n"
            "Such as the Father is, such is the Son: and such is the Holy Ghost.\n"
            "The Father uncreate, the Son uncreate: and the Holy Ghost uncreate.\n"
            "The Father incomprehensible, the Son incomprehensible: and the Holy Ghost incomprehensible.\n"
            "The Father eternal, the Son eternal: and the Holy Ghost eternal.\n"
            "And yet they are not three eternals: but one eternal.\n"
            "As also there are not three incomprehensibles, nor three uncreated: but one uncreated, "
            "and one incomprehensible.\n"
            "So likewise the Father is Almighty, the Son Almighty: and the Holy Ghost Almighty.\n"
            "And yet they are not three Almighties: but one Almighty.\n"
            "So the Father is God, the Son is God: and the Holy Ghost is God.\n"
            "And yet they are not three Gods: but one God.\n"
            "So likewise the Father is Lord, the Son Lord: and the Holy Ghost Lord.\n"
            "And yet not three Lords: but one Lord.\n"
            "For like as we are compelled by the Christian verity: to acknowledge every Person by himself "
            "to be God and Lord;\n"
            "So are we forbidden by the Catholick Religion: to say, There be three Gods, or three Lords.\n"
            "The Father is made of none: neither created, nor begotten.\n"
            "The Son is of the Father alone: not made, nor created, but begotten.\n"
            "The Holy Ghost is of the Father and of the Son: neither made, nor created, nor begotten, "
            "but proceeding.\n"
            "So there is one Father, not three Fathers; one Son, not three Sons: one Holy Ghost, "
            "not three Holy Ghosts.\n"
            "And in this Trinity none is afore, or after other: none is greater, or less than another;\n"
            "But the whole three Persons are co-eternal together: and co-equal.\n"
            "So that in all things, as is aforesaid: the Unity in Trinity, and the Trinity in Unity, "
            "is to be worshipped.\n"
            "He therefore that will be saved: must thus think of the Trinity.\n\n"
            "Furthermore, it is necessary to everlasting salvation: that he also believe rightly the "
            "Incarnation of our Lord Jesus Christ.\n"
            "For the right Faith is, that we believe and confess: that our Lord Jesus Christ, the Son "
            "of God, is God and Man;\n"
            "God, of the Substance of the Father, begotten before the worlds: and Man, of the Substance "
            "of his Mother, born in the world;\n"
            "Perfect God, and perfect Man: of a reasonable soul and human flesh subsisting;\n"
            "Equal to the Father, as touching his Godhead: and inferior to the Father, as touching his "
            "Manhood;\n"
            "Who although he be God and Man: yet he is not two, but one Christ;\n"
            "One; not by conversion of the Godhead into flesh: but by taking of the Manhood into God;\n"
            "One altogether; not by confusion of Substance: but by unity of Person.\n"
            "For as the reasonable soul and flesh is one man: so God and Man is one Christ;\n"
            "Who suffered for our salvation: descended into hell, rose again the third day from the dead;\n"
            "He ascended into heaven, he sitteth on the right hand of the Father, God Almighty: "
            "from whence he shall come to judge the quick and the dead.\n"
            "At whose coming all men shall rise again with their bodies: and shall give account for "
            "their own works.\n"
            "And they that have done good shall go into life everlasting: and they that have done evil "
            "into everlasting fire.\n\n"
            "This is the Catholick Faith: which except a man believe faithfully, he cannot be saved."
        ),
        "latin_title": "Quicunque Vult",
        "latin": (
            "Quicumque vult salvus esse, ante omnia opus est, ut teneat Catholicam fidem: Quam nisi quisque "
            "integram inviolatamque servaverit, absque dubio in aeternum peribit. Fides autem Catholica "
            "haec est: ut unum Deum in Trinitate, et Trinitatem in unitate veneremur. Neque confundentes "
            "personas, neque substantiam separantes. Alia est enim persona Patris alia Filii, alia Spiritus "
            "Sancti: Sed Patris, et Filii, et Spiritus Sancti una est divinitas, aequalis gloria, coeterna "
            "maiestas. Qualis Pater, talis Filius, talis [et] Spiritus Sanctus. Increatus Pater, increatus "
            "Filius, increatus [et] Spiritus Sanctus. Immensus Pater, immensus Filius, immensus [et] "
            "Spiritus Sanctus. Aeternus Pater, aeternus Filius, aeternus [et] Spiritus Sanctus. Et tamen "
            "non tres aeterni, sed unus aeternus. Sicut non tres increati, nec tres immensi, sed unus "
            "increatus, et unus immensus. Similiter omnipotens Pater, omnipotens Filius, omnipotens [et] "
            "Spiritus Sanctus. Et tamen non tres omnipotentes, sed unus omnipotens. Ita Deus Pater, Deus "
            "Filius, Deus [et] Spiritus Sanctus. Et tamen non tres dii, sed unus est Deus. Ita Dominus "
            "Pater, Dominus Filius, Dominus [et] Spiritus Sanctus. Et tamen non tres Domini, sed unus "
            "[est] Dominus. Quia, sicut singillatim unamquamque personam Deum ac Dominum confiteri "
            "christiana veritate compellimur: Ita tres Deos aut [tres] Dominos dicere Catholica religione "
            "prohibemur. Pater a nullo est factus: nec creatus, nec genitus. Filius a Patre solo est: non "
            "factus, nec creatus, sed genitus. Spiritus Sanctus a Patre et Filio: non factus, nec creatus, "
            "nec genitus, sed procedens. Unus ergo Pater, non tres Patres: unus Filius, non tres Filii: "
            "unus Spiritus Sanctus, non tres Spiritus Sancti. Et in hac Trinitate nihil prius aut "
            "posterius, nihil maius aut minus: Sed totae tres personae coaeternae sibi sunt et coaequales. "
            "Ita, ut per omnia, sicut iam supra dictum est, et unitas in Trinitate, et Trinitas in unitate "
            "veneranda sit. Qui vult ergo salvus esse, ita de Trinitate sentiat.\n\n"
            "Sed necessarium est ad aeternam salutem, ut incarnationem quoque Domini nostri Iesu Christi "
            "fideliter credat. Est ergo fides recta ut credamus et confiteamur, quia Dominus noster Iesus "
            "Christus, Dei Filius, Deus [pariter] et homo est. Deus [est] ex substantia Patris ante saecula "
            "genitus: et homo est ex substantia matris in saeculo natus. Perfectus Deus, perfectus homo: "
            "ex anima rationali et humana carne subsistens. Aequalis Patri secundum divinitatem: minor "
            "Patre secundum humanitatem. Qui licet Deus sit et homo, non duo tamen, sed unus est Christus. "
            "Unus autem non conversione divinitatis in carnem, sed assumptione humanitatis in Deum. Unus "
            "omnino, non confusione substantiae, sed unitate personae. Nam sicut anima rationalis et caro "
            "unus est homo: ita Deus et homo unus est Christus. Qui passus est pro salute nostra: "
            "descendit ad inferos: tertia die resurrexit a mortuis. Ascendit ad [in] caelos, sedet ad "
            "dexteram [Dei] Patris [omnipotentis]. Inde venturus [est] judicare vivos et mortuos. Ad cujus "
            "adventum omnes homines resurgere habent cum corporibus suis; Et reddituri sunt de factis "
            "propriis rationem. Et qui bona egerunt, ibunt in vitam aeternam: qui vero mala, in ignem "
            "aeternum. Haec est fides Catholica, quam nisi quisque fideliter firmiterque crediderit, "
            "salvus esse non poterit."
        ),
    },
}
CREED_ALIASES = {
    "apostle": "apostles", "apostles": "apostles", "apostles'": "apostles",
    "nicene": "nicene", "nicaea": "nicene", "nicea": "nicene",
    "athanasius": "athanasian", "athanasian": "athanasian", "quicunque": "athanasian", "quicunquevult": "athanasian",
}

CREED_LANGS = {
    "latin": "latin", "la": "latin", "lat": "latin",
    "greek": "greek", "gr": "greek", "el": "greek", "grc": "greek",
    "parallel": "parallel", "both": "parallel", "all": "parallel",
}

async def _send_creed(ctx, key: str, lang: str = "text"):
    creed = CREEDS[key]

    if lang == "parallel":
        for l in ("text", "greek", "latin"):
            if l == "text" or creed.get(l):
                await _send_creed(ctx, key, l)
        return

    if lang == "greek":
        if not creed.get("greek"):
            await ctx.send(f"No Greek text available for **{creed['title']}**.")
            return
        title = f"{creed['title']} — {creed.get('greek_title', 'Greek')}"
        body = creed["greek"]
        footer = "Greek (original conciliar language, liturgical wording)"
    elif lang == "latin":
        if not creed.get("latin"):
            await ctx.send(f"No Latin text available for **{creed['title']}**.")
            return
        title = f"{creed['title']} — {creed.get('latin_title', 'Latin')}"
        body = creed["latin"]
        footer = "Latin (traditional liturgical text)"
    else:
        title = creed["title"]
        body = creed["text"]
        footer = "Traditional English (Book of Common Prayer, 1662)"

    pages = _chunk(body, 3900)
    for i, page in enumerate(pages):
        embed = discord.Embed(
            title=title if len(pages) == 1 else f"{title} ({i + 1}/{len(pages)})",
            description=page,
            color=discord.Color.dark_gold(),
        )
        embed.set_footer(text=footer)
        await ctx.send(embed=embed)
    record_special_stat(ctx.author.id, "creed", f"{creed['title']} [{lang}]")

@bot.command(name="creed", aliases=["creeds"])
async def cmd_creed(ctx, *, which: str = ""):
    """The three ecumenical creeds, in English, Latin, or (Nicene only) Greek.
    Usage: !creed              — list the creeds
           !creed apostle      — the Apostles' Creed (English)
           !creed nicene latin — the Nicene Creed in Latin
           !creed nicene greek — the Nicene Creed in its original Greek
           !creed athanasius parallel — Athanasian Creed, English then Latin
    """
    tokens = which.strip().split()
    key = CREED_ALIASES.get(tokens[0].lower()) if tokens else None
    if not key:
        embed = discord.Embed(title="📜 The Creeds", color=discord.Color.dark_gold())
        embed.description = (
            "`!creed apostle` — The Apostles' Creed\n"
            "`!creed nicene` — The Nicene Creed\n"
            "`!creed athanasius` — The Athanasian Creed (Quicunque Vult)\n\n"
            "Add `latin` for the traditional Latin text, `greek` for the Nicene Creed's original "
            "conciliar language, or `parallel` for all available: "
            "e.g. `!creed apostle latin`, `!creed nicene parallel`.\n\n"
            "English is traditional, as in the 1662 Book of Common Prayer."
        )
        await ctx.send(embed=embed)
        return
    lang = CREED_LANGS.get(tokens[1].lower(), "text") if len(tokens) > 1 else "text"
    await _send_creed(ctx, key, lang)

@bot.tree.command(name="creed", description="The Apostles', Nicene, or Athanasian Creed, in English, Latin, or Greek")
@app_commands.describe(which="apostle | nicene | athanasius, optionally + latin, greek, or parallel")
async def creed_slash(interaction: discord.Interaction, which: str = ""):
    await interaction.response.defer()
    ctx = await bot.get_context(interaction)
    await cmd_creed(ctx, which=which)


# ── !summa — Summa Theologica via newadvent.org ───────────────────────────────

@bot.command(name="summa", aliases=["st", "aquinas", "thomas"])
async def cmd_summa(ctx, *, reference: str = ""):
    """
    Look up an article from the Summa Theologica.
    Usage:
      !summa I.2.3        → Prima Pars, Q.2, Article 3
      !summa I-II.109.1   → Prima Secundae, Q.109, A.1
      !summa II-II.23     → Secunda Secundae, Q.23 (list articles)
      !summa random       → random article
    """
    ref = reference.strip()

    async with ctx.typing():
        if not ref or ref.lower() in ("random", "rand", "r"):
            result = get_summa_random()
        else:
            parsed = parse_summa_ref(ref)
            if parsed is None:
                await ctx.send(
                    f"⚠️ Could not parse **{ref}**.\n"
                    f"Format: `!summa I.2.3` · `!summa I-II.109.1` · `!summa II-II.23` · `!summa random`"
                )
                return
            part, question, article = parsed
            result = get_summa(part, question, article)

    if not result["found"]:
        embed = discord.Embed(
            title="Summa Theologica — Not found",
            description=result["error"],
            color=discord.Color.red()
        )
        await ctx.send(embed=embed)
        return

    # Question overview (no article specified)
    if result["type"] == "question":
        lines = [f"**{n}.** {title}" for n, title in result["articles"]]
        embed = discord.Embed(
            title=f"ST {result['part_display']}.{result['question']} — {result['title']}",
            description="\n".join(lines) or "No articles found.",
            color=discord.Color.dark_gold(),
            url=result["url"]
        )
        embed.set_footer(text=f"Summa Theologica · {result['part_long']} · newadvent.org")
        record_special_stat(ctx.author.id, "summa", f"ST {result['part_display']}.{result['question']}")
        await ctx.send(embed=embed)
        return

    await _send_summa_article(ctx, result)


async def _send_summa_article(ctx, result: dict):
    """Send a Summa article as a paginated embed: I answer that / Objections / Replies."""
    q_title   = result.get("question_title", "")
    art_title = result["title"]
    url       = result["url"]
    part_long = result["part_long"]

    def _trunc(text: str, limit: int = 3800) -> str:
        if len(text) <= limit:
            return text
        cut = text[:limit].rfind(". ")
        return (text[:cut + 1] if cut > 200 else text[:limit]) + " …"

    pages = []
    body0 = f"*{art_title}*\n\n**I answer that,** {_trunc(result['i_answer_that'])}"
    pages.append(("I answer that", body0))
    if result["objections"]:
        pages.append(("Objections", _trunc("\n\n".join(result["objections"]))))
    body2_parts = []
    if result["on_the_contrary"]:
        body2_parts.append(f"**On the contrary,** {result['on_the_contrary']}")
    body2_parts.extend(result["replies"])
    if body2_parts:
        pages.append(("On the contrary & Replies", _trunc("\n\n".join(body2_parts))))

    total = len(pages)
    footer_base = f"Summa Theologica · {part_long} · Q.{result['question']} A.{result['article']}"

    def make_embed(idx: int) -> discord.Embed:
        page_label, body = pages[idx]
        embed = discord.Embed(
            title=f"ST {result['part_display']}.{result['question']}.{result['article']} — {page_label}",
            description=body,
            color=discord.Color.dark_gold(),
            url=url
        )
        embed.set_footer(text=f"{footer_base} · {idx + 1}/{total} · newadvent.org")
        if idx == 0 and q_title:
            embed.set_author(name=q_title)
        return embed

    if total == 1:
        await ctx.send(embed=make_embed(0))
        return

    class SummaView(discord.ui.View):
        def __init__(self):
            super().__init__(timeout=180)
            self.idx = 0

        @discord.ui.button(emoji="◀", style=discord.ButtonStyle.secondary)
        async def prev(self, interaction: discord.Interaction, button: discord.ui.Button):
            self.idx = (self.idx - 1) % total
            await interaction.response.edit_message(embed=make_embed(self.idx), view=self)

        @discord.ui.button(label="I answer that", style=discord.ButtonStyle.primary)
        async def jump_answer(self, interaction: discord.Interaction, button: discord.ui.Button):
            self.idx = 0
            await interaction.response.edit_message(embed=make_embed(self.idx), view=self)

        @discord.ui.button(emoji="▶", style=discord.ButtonStyle.secondary)
        async def next(self, interaction: discord.Interaction, button: discord.ui.Button):
            self.idx = (self.idx + 1) % total
            await interaction.response.edit_message(embed=make_embed(self.idx), view=self)

        async def on_timeout(self):
            try:
                await self.message.edit(view=None)
            except Exception:
                pass

    view = SummaView()
    ref_label = (f"ST {result.get('part_display','')}"
                 f".{result.get('question','')}"
                 f".{result.get('article','')}")
    record_special_stat(ctx.author.id, "summa", ref_label)
    view.message = await ctx.send(embed=make_embed(0), view=view)


# ── !compare — verse in multiple translations, paginated ─────────────────────

# All English translations for !compare, in display order
_COMPARE_ALL = [
    # Major modern
    "KJV", "ESV", "NASB", "NIV", "NIV2011", "NKJV", "NLT", "NET",
    "NRSVCE", "RSV", "RSV2CE", "WEB", "CSB17", "AMP", "MSG",
    # Public domain / historical
    "ASV", "YLT", "GNV",
    # Catholic / Jewish / other
    "NABRE", "NJB1985", "CJB", "TLV",
    # Remaining
    "BSB", "LSV", "LSB", "MEV", "ISV", "ERV", "GNTD", "CEVD", "CEB",
]

# Ancient language set — determined per-verse based on OT/NT
# OT abbreviations for _is_ot_reference
_OT_ABBREVS = {
    # Protestant OT
    "gen","exod","ex","lev","num","deut","josh","judg","ru","ruth",
    "1sam","2sam","1kgs","2kgs","1chr","2chr","ezra","neh","esth",
    "job","ps","psa","prov","eccl","song","isa","jer","lam","ezek",
    "dan","hos","joel","amos","obad","jon","mic","nah","hab","zeph",
    "hag","zech","mal",
    # Deuterocanonical / Apocrypha
    "tob","tobit","jdt","judith","wis","wisdom","sir","sirach",
    "ecclesiasticus","bar","baruch","1macc","2macc","3macc","4macc",
    "1maccabees","2maccabees","1esd","2esd","1esdras","2esdras",
    "pman","prayer of manasseh","additions to esther",
}

# Full names of OT + Apocrypha books for _is_ot_reference
_OT_FULL_NAMES = set(BIBLE_OT) | {
    "Tobit","Judith","Wisdom of Solomon","Sirach","Baruch",
    "1 Maccabees","2 Maccabees","3 Maccabees","4 Maccabees",
    "1 Esdras","2 Esdras","Prayer of Manasseh","Additions to Esther",
    "Epistle of Jeremiah","Song of the Three Children","Susanna",
    "Bel and the Dragon","Psalms of Solomon","Book of Enoch","Book of Jubilees",
}

def _is_ot_reference(reference: str) -> bool:
    """Return True if reference is from the OT, Apocrypha, or Pseudepigrapha."""
    m = re.match(r"^((?:\d\s*)?[A-Za-z][A-Za-z\s'&-]{0,30}?)\s+\d", reference.strip())
    if not m:
        return False
    book = m.group(1).strip().lower()
    if book in _OT_ABBREVS:
        return True
    return any(book == b.lower() or b.lower().startswith(book) for b in _OT_FULL_NAMES)


@bot.command(name="compare", aliases=["cmp"])
async def cmd_compare(ctx, *, reference: str = ""):
    """
    Show a verse across translations, paginated.
    Usage: !compare John 3:16
           !compare ancient John 3:16   — KJV + Greek/Hebrew + LXX + Vulgate
           !compare strong John 3:16    — KJV + WLC/TISCH with Strong's numbers
    """
    if not reference:
        await ctx.send("Usage: `!compare John 3:16` or `!compare ancient John 3:16` or `!compare strong John 3:16`")
        return
    if not _check_search_cooldown(ctx.author.id):
        await ctx.send("⏳ Please wait a moment before using !compare again.", delete_after=8)
        return

    # Detect mode: "strong <ref>" > "ancient <ref>" > "<ref>"
    ancient_mode = False
    strong_mode = False
    ref = reference.strip()
    if ref.lower().startswith("strong "):
        strong_mode = True
        ref = ref[len("strong "):].strip()
    elif ref.lower().startswith("ancient "):
        ancient_mode = True
        ref = ref[8:].strip()

    async with ctx.typing():
        if strong_mode:
            await _send_compare_ancient_strong(ctx, ref)
        elif ancient_mode:
            await _send_compare_ancient(ctx, ref)
        else:
            await _send_compare(ctx, ref)

@bot.tree.command(name="compare", description="Show a verse across multiple translations")
@app_commands.describe(reference="e.g. John 3:16  |  ancient John 3:16  |  strong John 3:16")
async def compare_slash(interaction: discord.Interaction, reference: str):
    await interaction.response.defer()
    ctx = await bot.get_context(interaction)
    raw = reference.strip()
    if raw.lower().startswith("strong "):
        await _send_compare_ancient_strong(ctx, raw[len("strong "):].strip())
    elif raw.lower().startswith("ancient "):
        await _send_compare_ancient(ctx, raw[8:].strip())
    else:
        await _send_compare(ctx, raw)


async def _fetch_one_translation(slug: str, reference: str) -> tuple[str, str, str]:
    """Fetch a single translation in a thread executor (non-blocking)."""
    loop = asyncio.get_event_loop()

    def _fetch_sync():
        if slug == "KJV":
            r = lookup.get_verse(reference)
            text = r["text"] if r.get("found") else "*Not found*"
            return ("KJV", "King James Version (1769)", text)
        elif slug == "DRB":
            # Try reference as-is first
            r = get_verse_drb(reference)
            if not r.get("found"):
                # Remap KJV apocrypha names to Douay-Rheims equivalents
                _DRB_APOC = {
                    "wisdom of solomon": "Wisdom",
                    "sirach": "Ecclesiasticus",
                    "ecclesiasticus": "Ecclesiasticus",
                    "1 maccabees": "1 Machabees",
                    "2 maccabees": "2 Machabees",
                    "1 esdras": "3 Esdras",
                    "2 esdras": "4 Esdras",
                    "prayer of manasseh": "Prayer of Manasses",
                    "tobit": "Tobias",
                }
                m = re.match(r'^((?:\d\s*)?[A-Za-z][A-Za-z\s]+?)\s+(\d.*)$', reference.strip(), re.I)
                if m:
                    book_raw = m.group(1).strip().lower()
                    rest = m.group(2)
                    remapped = _DRB_APOC.get(book_raw)
                    if remapped:
                        r = get_verse_drb(f"{remapped} {rest}")
            text = r["text"] if r.get("found") else "*Not found*"
            return ("DRB", "Douay-Rheims Bible", text)
        elif slug == "Knox":
            r = get_verse_knox(reference)
            text = r["text"] if r.get("found") else "*Not found*"
            return ("Knox", "Knox Bible (1945–49)", text)
        elif slug == "VULG":
            r = get_translation(reference, "VULG")
            if not r.get("found"):
                time.sleep(0.5)
                r = get_translation(reference, "VULG")  # one retry
            if r.get("found"):
                return ("VULG", "Vulgata Clementina (Latin)", r["text"])
            return ("VULG", "Vulgata Clementina (Latin)", "*Not available*")
        elif slug == "LXX":
            r = get_translation(reference, "LXX")
            if r.get("found"):
                return ("LXX", "Septuagint (Greek OT)", r["text"])
            return ("LXX", "Septuagint (Greek OT)", "*Not available*")
        elif slug == "OE":
            r = get_translation(reference, "OE")
            if r.get("found"):
                return ("OE", "Old English (Ælfric/Wessex Gospels, ~990 AD)", r["text"])
            return ("OE", "Old English (Ælfric/Wessex Gospels, ~990 AD)", "*Not available*")
        elif slug == "PESHITTA":
            r = get_translation(reference, "PESHITTA")
            if r.get("found"):
                return ("PESHITTA", "Peshitta (Classical Syriac/Aramaic)", r["text"])
            return ("PESHITTA", "Peshitta (Classical Syriac/Aramaic)", "*Not available*")
        elif slug == "CSL":
            r = get_translation(reference, "CSL")
            if r.get("found"):
                return ("CSL", "Church Slavonic (Elizabeth Bible, 1757)", r["text"])
            return ("CSL", "Church Slavonic (Elizabeth Bible, 1757)", "*Not available*")
        else:
            r = get_translation(reference, slug)
            if r.get("found"):
                display = TRANSLATIONS.get(slug.lower(), (slug, slug))[1]
                return (slug, display, r["text"])
            return (slug, slug, "*Not available*")

    return await loop.run_in_executor(None, _fetch_sync)


async def _send_compare(ctx, reference: str):
    """Fetch all English translations concurrently and display paginated."""

    tasks = [_fetch_one_translation(slug, reference) for slug in _COMPARE_ALL]
    raw = await asyncio.gather(*tasks)
    results = [(s, d, t) for s, d, t in raw if t not in ("*Not found*", "*Not available*")]

    if not results:
        await ctx.send(f"⚠️ Could not find **{reference}** in any translation.")
        return

    await _display_compare(ctx, reference, results, "All Translations")


async def _send_compare_ancient(ctx, reference: str):
    """Fetch KJV + language-appropriate ancient texts concurrently."""
    from poem_lookup import classify_scripture
    scripture_type = classify_scripture(reference)

    # For Psalms, annotate the title with the LXX/Vulgate numbering
    display_reference = reference
    import re as _re
    _psalm_m = _re.match(r'^Ps(?:alms?)?[.\\s]+(\\d+)(?:[:\\s](\\d+))?', reference.strip(), _re.I)
    if _psalm_m:
        mt_num = int(_psalm_m.group(1))
        verse_part = f":{_psalm_m.group(2)}" if _psalm_m.group(2) else ""
        # Compute LXX number(s)
        lxx_mappings = _mt_to_lxx_psalm(mt_num)
        if len(lxx_mappings) == 1 and lxx_mappings[0][1] is None and lxx_mappings[0][0] != mt_num:
            lxx_num = lxx_mappings[0][0]
            display_reference = f"Psalm {mt_num}{verse_part} [LXX/VULG: {lxx_num}{verse_part}]"
        elif len(lxx_mappings) == 1 and lxx_mappings[0][1] is not None:
            lxx_num, vs, ve = lxx_mappings[0]
            display_reference = f"Psalm {mt_num}{verse_part} [LXX/VULG: {lxx_num}:{vs}-{ve}]"
        elif len(lxx_mappings) > 1:
            lxx_str = " + ".join(str(m[0]) for m in lxx_mappings)
            display_reference = f"Psalm {mt_num}{verse_part} [LXX/VULG: {lxx_str}]"

    # Determine whether Old English has coverage for this book.
    # OE corpus = Wessex Gospels (Matthew, Mark, Luke, John) +
    # Ælfric's Heptateuch (Genesis-Judges) + Paris Psalter (Psalms).
    _OE_BOOKS = {
        "matthew", "matt", "mt",
        "mark", "mk", "mrk",
        "luke", "lk", "luk",
        "john", "jn", "joh",
        "genesis", "gen", "ge", "gn",
        "exodus", "exod", "ex", "exo",
        "leviticus", "lev", "lv",
        "numbers", "num", "nm", "nu",
        "deuteronomy", "deut", "dt",
        "joshua", "josh", "jos",
        "judges", "judg", "jdg", "jgs",
        "psalm", "psalms", "ps", "psa", "pss",
    }
    _book_m = _re.match(r"^\s*((?:[1-3]\s*)?[A-Za-z][A-Za-z\s\.]*?)\s+\d", reference.strip())
    _book_key = _book_m.group(1).strip().lower().replace(".", "") if _book_m else ""
    has_oe = _book_key in _OE_BOOKS

    if scripture_type == 'nt':
        # New order: KJV, TR, VULG, PESHITTA, CSL, OE
        slug_list = ["KJV", "TR", "VULG", "PESHITTA", "CSL"]
        if has_oe:
            slug_list.append("OE")
    elif scripture_type == 'apocrypha':
        # Apocrypha (no OE coverage at all): KJV, LXX, VULG, PESHITTA, CSL
        slug_list = ["KJV", "LXX", "VULG", "PESHITTA", "CSL"]
    else:
        # OT proper. New order: KJV, WLC, LXX, VULG, PESHITTA, CSL, OE
        slug_list = ["KJV", "WLC", "LXX", "VULG", "PESHITTA", "CSL"]
        if has_oe:
            slug_list.append("OE")

    raw = []
    for i, slug in enumerate(slug_list):
        if i > 0:
            await asyncio.sleep(0.3)
        result = await _fetch_one_translation(slug, reference)
        raw.append(result)

    display_overrides = {
        "WLC":  "Hebrew OT (Westminster Leningrad Codex)",
        "OE":   "Old English (Ælfric/Wessex Gospels, ~990 AD)",
        "PESHITTA": "Peshitta (Classical Syriac/Aramaic)",
        "CSL":      "Church Slavonic (Elizabeth Bible, 1757)",
        "LXX":  "Septuagint (Greek OT)",
        "TR":   "Textus Receptus (Greek NT, Elzevir 1624)",
        "VULG": "Vulgata Clementina (Latin)",
    }
    results = []
    for slug, display, text in raw:
        d = display_overrides.get(slug, display)
        results.append((slug, d, text))

    await _display_compare(ctx, display_reference, results, "Ancient Languages", page_size=6)


# ── Strong's lookup helpers ───────────────────────────────────────────────────
#
# Source: bolls.life
#   Strong's-tagged Hebrew OT  →  slug "WLCa"
#   Strong's-tagged Greek NT   →  slug "TISCH"
#   Dictionary endpoint        →  /dictionary-definition/BDBT/<query>
#     (BDB for Hebrew, Thayer's for Greek; also accepts H123 / G456 directly)

_STRONGS_DEF_CACHE: dict[str, dict | None] = {}


def _bolls_fetch_chapter(slug: str, book_id: int, chapter: int) -> list | None:
    """Synchronous bolls.life chapter fetch that preserves the raw text
    (does NOT strip Strong's-number tags). Returns the verse list or None."""
    import urllib.request, urllib.error, json as _json
    url = f"https://bolls.life/get-text/{slug}/{book_id}/{chapter}/"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "ScriptureBot/1.0"})
        with urllib.request.urlopen(req, timeout=15) as r:
            data = _json.loads(r.read().decode("utf-8"))
        return data if isinstance(data, list) else None
    except urllib.error.HTTPError:
        return None
    except Exception:
        return None


def _parse_strongs_text(text: str) -> list[tuple[str, str]]:
    """
    Parse bolls.life Strong's-tagged verse text into [(word, "G####"), ...].

    Bolls returns HTML with one of two encodings:
      1. <S>1234</S> tags after each word (SWORD style)
      2. Inline digits glued to the word, e.g. "λόγος3056"
    We handle both, preferring the <S> form when present.
    """
    import html as html_mod
    text = html_mod.unescape(text)

    # Strip <br>, paragraph tags, etc., but keep <S> for parsing
    text = re.sub(r"<(?!/?[Ss]\b)[^>]+>", " ", text)

    # Decide which book this is so we can tag the prefix correctly
    # (we don't know here; the caller passes the testament marker via slug).
    # We just preserve the raw number; the caller adds "G" or "H".

    pairs: list[tuple[str, str]] = []

    # Try <S>1234</S> form first
    s_pattern = re.compile(
        r"(\S+?)\s*<S>\s*(\d+)\s*</S>",
        re.IGNORECASE
    )
    s_matches = list(s_pattern.finditer(text))
    if s_matches:
        for m in s_matches:
            word = m.group(1).strip().strip(",.:;!?·")
            num = m.group(2)
            if word:
                pairs.append((word, num))
        return pairs

    # Fall back: strip any remaining tags, then scan for word+digits
    text = re.sub(r"<[^>]+>", " ", text)

    # Inline format: word followed immediately by digits
    inline_pattern = re.compile(r"(\S+?)(\d+)(?=\s|$|[,.:;!?])")
    for m in inline_pattern.finditer(text):
        word = m.group(1).strip().strip(",.:;!?·")
        num = m.group(2)
        # Filter out non-Strong's stuff (e.g. footnote markers)
        if word and len(num) <= 5:
            pairs.append((word, num))

    return pairs


def _parse_kjv_reverse_interlinear(text: str) -> list[dict]:
    """
    Parse bolls.life KJV Strong's-tagged text into an ordered list of
    {"phrase": "...", "strong": "1234" or None}, preserving every English
    word in natural KJV reading order -- unlike _parse_strongs_text, which
    keeps only one representative word per Strong's number (fine for a
    reverse lookup, not for displaying the whole verse).

    A "<S>NUM</S>" tag attaches to every word back to the previous tag (or
    the start of the verse): Hebrew/Greek words routinely cover more than
    one English word (e.g. "In the beginning" is one Hebrew word,
    re'shiyth, H7225). Untranslatable grammatical markers (e.g. H853, the
    Hebrew direct object marker) can own an empty phrase; those are
    dropped rather than shown as a blank tag.
    """
    import html as html_mod
    text = html_mod.unescape(text)
    text = re.sub(r"<(?!/?[Ss]\b)[^>]+>", " ", text)

    parts = re.split(r"<S>\s*(\d+)\s*</S>", text)
    entries = []
    for i in range(0, len(parts) - 1, 2):
        phrase = re.sub(r"\s+", " ", parts[i]).strip()
        if phrase:
            entries.append({"phrase": phrase, "strong": parts[i + 1]})
    if len(parts) % 2 == 1:
        trailing = re.sub(r"\s+", " ", parts[-1]).strip()
        if trailing:
            entries.append({"phrase": trailing, "strong": None})
    return entries


def _fetch_strongs_passage(reference: str, testament: str) -> dict:
    """
    Fetch one verse from bolls.life in Strong's-tagged form.

    testament: "nt" → uses TISCH (Greek, "G" prefix)
               "ot" → uses WLCa  (Hebrew, "H" prefix)

    Returns:
      {"found": True, "ref": display_ref, "slug": slug, "pairs": [(word,"G####"), ...]}
      {"found": False, "error": "..."}
    """
    from translation_lookup import _BOOK_IDS, _ALIASES

    # Strip range to first verse for the lookup, since each verse is its own row
    ref_single = re.sub(r"(\d+:\d+)[-–]\d+$", r"\1", reference.strip())

    m = re.match(r"^((?:\d\s*)?[A-Za-z][a-zA-Z\s\.]+?)\s+(\d+):(\d+)$", ref_single)
    if not m:
        chapter_only = re.match(r"^((?:\d\s*)?[A-Za-z][a-zA-Z\s\.]+?)\s+\d+$", ref_single)
        if chapter_only:
            return {"found": False, "error": f"`{ref_single}` is a whole chapter — this needs one verse, e.g. `{ref_single}:1`."}
        return {"found": False, "error": f"Couldn't parse `{ref_single}`. Try a single verse like `John 3:16`."}

    book_raw = m.group(1).strip().lower().replace(".", "")
    chapter = int(m.group(2))
    verse = int(m.group(3))

    book_id = _BOOK_IDS.get(book_raw) or _BOOK_IDS.get(_ALIASES.get(book_raw, ""))
    if not book_id:
        return {"found": False, "error": f"Unknown book: **{m.group(1).strip()}**"}

    if testament == "nt":
        slug = "TISCH"
        prefix = "G"
    else:
        slug = "WLCa"
        prefix = "H"

    rows = _bolls_fetch_chapter(slug, book_id, chapter)
    if not rows:
        return {"found": False, "error": f"Could not fetch {slug} {ref_single} from bolls.life."}

    row = next((v for v in rows if v.get("verse") == verse), None)
    if not row:
        return {"found": False, "error": f"Verse {verse} not found in {slug} chapter."}

    raw_text = row.get("text", "")
    raw_pairs = _parse_strongs_text(raw_text)
    pairs = [(w, f"{prefix}{n}") for (w, n) in raw_pairs]

    return {
        "found": True,
        "ref": f"{m.group(1).strip().title()} {chapter}:{verse}",
        "slug": slug,
        "pairs": pairs,
        "book_id": book_id,
        "chapter": chapter,
        "verse": verse,
    }


def _fetch_kjv_word_map(book_id: int, chapter: int, verse: int) -> dict:
    """Fetch the KJV's own Strong's-tagged English text for one verse and
    return {bare_strongs_number: deque[english_word, ...]} in KJV word
    order. Used to show the actual KJV rendering of each original-language
    word in !interlinear instead of a generic lexicon gloss -- e.g. G2889
    (kosmos) shows "world" here (what the KJV actually wrote in this verse)
    rather than a lexicon pick like "adorning" (also a real KJV rendering,
    just not the one used in this particular verse)."""
    from collections import defaultdict, deque
    by_num: dict[str, deque] = defaultdict(deque)
    rows = _bolls_fetch_chapter("KJV", book_id, chapter)
    if not rows:
        return by_num
    row = next((v for v in rows if v.get("verse") == verse), None)
    if not row:
        return by_num
    for word, num in _parse_strongs_text(row.get("text", "")):
        by_num[num].append(word)
    return by_num


def _fetch_strongs_definition(number: str) -> dict | None:
    """
    Look up a Strong's number (e.g. "G3588" or "H7225"). Tries the local
    OpenScriptures dictionary first (instant, always available, covers the
    full standard Strong's range); falls back to the live bolls.life
    dictionary endpoint only for anything the local copy doesn't have.

    Keys in the returned dict (when found):
      lexeme, transliteration, pronunciation, short_definition, definition
    """
    import urllib.request, urllib.error, json as _json

    key = number.strip().upper()
    if not re.match(r"^[GH]\d+$", key):
        return None

    local = get_local_strongs_definition(key)
    if local:
        return local

    if key in _STRONGS_DEF_CACHE:
        return _STRONGS_DEF_CACHE[key]

    url = f"https://bolls.life/dictionary-definition/BDBT/{key}/"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "ScriptureBot/1.0"})
        with urllib.request.urlopen(req, timeout=10) as r:
            data = _json.loads(r.read().decode("utf-8"))
    except Exception:
        _STRONGS_DEF_CACHE[key] = None
        return None

    if not isinstance(data, list) or not data:
        _STRONGS_DEF_CACHE[key] = None
        return None

    # Pick the entry whose topic matches our number; fall back to first.
    entry = next((d for d in data if str(d.get("topic", "")).upper() == key), data[0])
    _STRONGS_DEF_CACHE[key] = entry
    return entry


async def _send_compare_ancient_strong(ctx, reference: str):
    """KJV + Strong's-tagged Hebrew (OT) or Greek (NT) for one verse."""
    from poem_lookup import classify_scripture

    scripture_type = classify_scripture(reference)
    if scripture_type == "apocrypha":
        await ctx.send("⚠️ Strong's tagging isn't available for apocryphal books.")
        return

    testament = "nt" if scripture_type == "nt" else "ot"

    # KJV verse text
    ref_single = re.sub(r"(\d+:\d+)[-–]\d+$", r"\1", reference.strip())
    kjv = lookup.get_verse(ref_single)
    kjv_text = kjv["text"] if kjv.get("found") else "*Not available*"
    display_ref = kjv.get("reference", ref_single) if kjv.get("found") else ref_single

    # Strong's-tagged original
    loop = asyncio.get_event_loop()
    strongs = await loop.run_in_executor(None, _fetch_strongs_passage, ref_single, testament)

    if not strongs.get("found"):
        err = strongs.get("error", "Strong's lookup failed.")
        await ctx.send(f"⚠️ {err}")
        return

    pairs = strongs["pairs"]
    if not pairs:
        await ctx.send(f"⚠️ No Strong's-tagged words found for **{display_ref}**.")
        return

    slug = strongs["slug"]
    if slug == "TISCH":
        original_label = "Greek NT (Tischendorf 8th, with Strong's)"
        is_rtl = False
    else:
        original_label = "Hebrew OT (WLC, with Strong's)"
        is_rtl = True

    if is_rtl:
        # Hebrew is RTL; inline mixing with ASCII Strong's numbers can leave
        # the number visually orphaned when a wrap splits the pair. Two-part
        # mitigation:
        #   • Non-breaking space (U+00A0) between word and number — Discord
        #     will never wrap a pair.
        #   • Wider separator between pairs ("  ·  ") so the eye groups them.
        # The Strong's number goes FIRST in source order so that bidi resolves
        # it to the visual LEFT of the Hebrew word (which is what Hebrew
        # readers expect when annotations appear with words).
        tokens = [f"[`{n}`]\u00A0**{w}**" for (w, n) in pairs]
        separator = "  ·  "
    else:
        # Greek is LTR; flowing-sentence layout reads naturally.
        tokens = [f"**{w}** [`{n}`]" for (w, n) in pairs]
        separator = " "

    embed = discord.Embed(
        title=f"📖 {display_ref} — Strong's",
        color=discord.Color.dark_gold(),
    )
    embed.add_field(
        name="KJV — King James Version (1769)",
        value=kjv_text[:1020] + ("…" if len(kjv_text) > 1020 else ""),
        inline=False,
    )

    # Discord field cap is 1024 chars; split into chunks at token boundaries.
    chunk = ""
    chunk_idx = 1

    def _flush(c: str, idx: int) -> None:
        embed.add_field(
            name=f"{original_label}" + (f" (cont. {idx})" if idx > 1 else ""),
            value=c.rstrip(),
            inline=False,
        )

    for tok in tokens:
        # +len(separator) accounts for the joiner
        if chunk and len(chunk) + len(separator) + len(tok) > 1020:
            _flush(chunk, chunk_idx)
            chunk = ""
            chunk_idx += 1
        chunk += (separator if chunk else "") + tok
    if chunk:
        _flush(chunk, chunk_idx)

    embed.set_footer(text=f"{len(pairs)} words · use !strong <number> for definitions · bolls.life")
    await ctx.send(embed=embed)


# ── Strong's concordance search: every occurrence of a number in one book ──────
# Scoped to a single book (not the whole Bible) — a full-Bible search would mean
# hundreds of live bolls.life fetches per query, which isn't fair use of a free
# public API or a reasonable wait for a Discord command.
_CONCORDANCE_CHAPTER_CACHE: dict[tuple, list] = {}  # (slug, book_id, chapter) -> [(verse_num, [(word, num), ...]), ...]

async def _send_strongs_concordance(ctx, number: str, book_raw: str):
    from translation_lookup import _BOOK_IDS, _ALIASES, _CHAPTER_COUNTS

    book_key = book_raw.strip().lower().replace(".", "")
    book_id = _BOOK_IDS.get(book_key) or _BOOK_IDS.get(_ALIASES.get(book_key, ""))
    if not book_id:
        await ctx.send(
            f"⚠️ Unknown book: **{book_raw}**. Concordance search works within one canonical "
            "Bible book, e.g. `!strong G26 in John`."
        )
        return

    testament = "nt" if number.startswith("G") else "ot"
    if testament == "nt" and book_id < 40:
        await ctx.send(f"⚠️ **{book_raw}** is an Old Testament book — `G`-prefixed numbers only apply to the NT.")
        return
    if testament == "ot" and book_id >= 40:
        await ctx.send(f"⚠️ **{book_raw}** is a New Testament book — `H`-prefixed numbers only apply to the OT.")
        return

    slug = "TISCH" if testament == "nt" else "WLCa"
    target = number[1:]
    n_chapters = _CHAPTER_COUNTS.get(book_id)
    if not n_chapters:
        await ctx.send(f"⚠️ No chapter data available for **{book_raw}**.")
        return

    book_title = book_raw.strip().title()
    matches = []
    async with ctx.typing():
        loop = asyncio.get_event_loop()
        for chap in range(1, n_chapters + 1):
            key = (slug, book_id, chap)
            per_verse = _CONCORDANCE_CHAPTER_CACHE.get(key)
            if per_verse is None:
                verses = await loop.run_in_executor(None, _bolls_fetch_chapter, slug, book_id, chap)
                per_verse = []
                if verses:
                    for v in verses:
                        per_verse.append((v.get("verse"), _parse_strongs_text(v.get("text", ""))))
                _CONCORDANCE_CHAPTER_CACHE[key] = per_verse
            for verse_num, pairs in per_verse:
                for word, num in pairs:
                    if num == target:
                        matches.append((chap, verse_num, word))

    if not matches:
        await ctx.send(f"No occurrences of **{number}** found in **{book_title}**.")
        return

    lines = [f"{book_title} {c}:{v} — **{w}**" for c, v, w in matches[:40]]
    embed = discord.Embed(
        title=f"🔎 {number} in {book_title}",
        description="\n".join(lines),
        color=discord.Color.dark_gold(),
    )
    footer = f"{len(matches)} occurrence(s)"
    if len(matches) > 40:
        footer += " — showing first 40"
    footer += " · bolls.life"
    embed.set_footer(text=footer)
    await ctx.send(embed=embed)


# ── !strong — Strong's concordance lookup ─────────────────────────────────────

@bot.command(name="strong", aliases=["strongs"])
async def cmd_strong(ctx, *, query: str = ""):
    """Look up a Strong's number, or get a verse with Strong's tagging.
    Usage:
      !strong G3588             — Greek lexicon entry
      !strong H7225             — Hebrew lexicon entry
      !strong John 3:16         — verse with each word tagged (alias for !compare strong)
      !strong Psalm 23:1        — same, for OT
    """
    raw = (query or "").strip()
    if not raw:
        await ctx.send(
            "Usage: `!strong G3588` · `!strong H7225` · `!strong John 3:16` · `!strong G26 in John`"
        )
        return

    # ── Concordance: "!strong G26 in John" — every occurrence within one book ──
    m_concord = re.match(r"^([GH]\d+)\s+in\s+(.+)$", raw, re.IGNORECASE)
    if m_concord:
        await _send_strongs_concordance(ctx, m_concord.group(1).upper(), m_concord.group(2).strip())
        return

    # If it looks like a verse reference (contains "Book Chapter:Verse"),
    # dispatch to the Strong's-tagged comparison.
    if re.search(r"\b\d+:\d+\b", raw):
        async with ctx.typing():
            await _send_compare_ancient_strong(ctx, raw)
        return

    arg = raw.upper().replace(" ", "")

    # Allow user to type "3588" if they want — default to G for ambiguous
    if re.match(r"^\d+$", arg):
        await ctx.send("Please prefix with `G` (Greek NT) or `H` (Hebrew OT): "
                       f"`!strong G{arg}`  or  `!strong H{arg}`")
        return

    if not re.match(r"^[GH]\d+$", arg):
        await ctx.send(f"⚠️ `{arg}` isn't a Strong's number. Try `G3588` or `H7225` — or a verse like `John 3:16`.")
        return

    async with ctx.typing():
        loop = asyncio.get_event_loop()
        entry = await loop.run_in_executor(None, _fetch_strongs_definition, arg)

    if entry is None:
        await ctx.send(f"⚠️ No definition found for **{arg}**.")
        return

    lexeme    = entry.get("lexeme") or entry.get("topic") or arg
    translit  = entry.get("transliteration") or ""
    pron      = entry.get("pronunciation") or ""
    short_def = entry.get("short_definition") or ""
    full_def  = entry.get("definition") or ""

    # Strip any embedded HTML from the long definition.
    # Replace block-level tags with whitespace first so adjacent words don't fuse.
    full_def = re.sub(r"<br\s*/?>", " ", full_def, flags=re.I)
    full_def = re.sub(r"</(p|div|li|ul|ol|tr|td|th|h[1-6])\s*>", " ", full_def, flags=re.I)
    full_def = re.sub(r"<(p|div|li|ul|ol|tr|td|th|h[1-6])\b[^>]*>", " ", full_def, flags=re.I)
    full_def = re.sub(r"<[^>]+>", "", full_def)
    # Collapse the runs of whitespace we just introduced
    full_def = re.sub(r"\s+", " ", full_def).strip()

    is_hebrew = arg.startswith("H")
    src_label = "Brown-Driver-Briggs" if is_hebrew else "Thayer's Greek Lexicon"

    title = f"📚 {arg} — {lexeme}"
    desc_parts = []
    if translit:
        desc_parts.append(f"**Transliteration:** {translit}")
    if pron:
        desc_parts.append(f"**Pronunciation:** {pron}")
    if short_def:
        desc_parts.append(f"**Gloss:** {short_def}")
    base_description = "\n".join(desc_parts) if desc_parts else None

    # Split the full definition into one or more pages of ≤ ~1000 chars each,
    # breaking on sentence boundaries where possible.
    def _paginate_def(text: str, page_size: int = 1000) -> list[str]:
        text = text.strip()
        if not text:
            return []
        if len(text) <= page_size:
            return [text]
        pages: list[str] = []
        remaining = text
        while remaining:
            if len(remaining) <= page_size:
                pages.append(remaining.strip())
                break
            window = remaining[:page_size]
            cut = window.rfind(". ")
            if cut < page_size // 3:  # no good sentence break — fall back to space
                cut = window.rfind(" ")
            if cut <= 0:
                cut = page_size
            pages.append(remaining[:cut + 1].strip())
            remaining = remaining[cut + 1:].lstrip()
        return pages

    pages = _paginate_def(full_def)

    def _build_embed(page_idx: int) -> discord.Embed:
        em = discord.Embed(
            title=title,
            description=base_description,
            color=discord.Color.teal(),
        )
        if pages:
            name = "Definition"
            if len(pages) > 1:
                name = f"Definition (page {page_idx + 1}/{len(pages)})"
            em.add_field(name=name, value=pages[page_idx], inline=False)
        em.set_footer(text=f"{src_label} · via bolls.life")
        return em

    if len(pages) <= 1:
        # Short enough to fit in one embed — no buttons needed.
        await ctx.send(embed=_build_embed(0))
        return

    # Long definition: paginate with prev/next buttons.
    class StrongDefView(discord.ui.View):
        def __init__(self):
            super().__init__(timeout=180)
            self.idx = 0
            self.message: discord.Message | None = None

        @discord.ui.button(emoji="◀", style=discord.ButtonStyle.secondary)
        async def prev(self, interaction: discord.Interaction, button: discord.ui.Button):
            self.idx = (self.idx - 1) % len(pages)
            await interaction.response.edit_message(embed=_build_embed(self.idx), view=self)

        @discord.ui.button(emoji="▶", style=discord.ButtonStyle.secondary)
        async def next(self, interaction: discord.Interaction, button: discord.ui.Button):
            self.idx = (self.idx + 1) % len(pages)
            await interaction.response.edit_message(embed=_build_embed(self.idx), view=self)

        async def on_timeout(self):
            try:
                if self.message is not None:
                    await self.message.edit(view=None)
            except Exception:
                pass

    view = StrongDefView()
    msg = await ctx.send(embed=_build_embed(0), view=view)
    view.message = msg


@bot.tree.command(name="strong", description="Strong's number lookup or verse with Strong's tagging")
@app_commands.describe(query="A Strong's number (G3588 / H7225) or a verse reference (John 3:16)")
async def strong_slash(interaction: discord.Interaction, query: str):
    await interaction.response.defer()
    ctx = await bot.get_context(interaction)
    await cmd_strong(ctx, query=query)


async def _display_compare(ctx, reference: str, results: list, mode: str, page_size: int = 2):
    PAGE = page_size
    pages = [results[i:i+PAGE] for i in range(0, len(results), PAGE)]
    total = len(pages)

    def make_embed(idx: int) -> discord.Embed:
        embed = discord.Embed(
            title=f"📖 {reference} — {mode}",
            color=discord.Color.dark_gold()
        )
        for slug, display, text in pages[idx]:
            if len(text) > 1020:
                text = text[:1017] + "…"
            embed.add_field(name=f"**{slug}** — {display}", value=text, inline=False)
        footer = f"{len(results)} translations · !verse {reference}"
        if total > 1:
            footer = f"Page {idx+1}/{total} · " + footer
        embed.set_footer(text=footer)
        return embed

    # No buttons needed for a single page
    if total == 1:
        await ctx.send(embed=make_embed(0))
        return

    class CompareView(discord.ui.View):
        def __init__(self):
            super().__init__(timeout=180)
            self.idx = 0
            self._update_label()

        def _update_label(self):
            self.page_label.label = f"{self.idx+1}/{total}"

        @discord.ui.button(emoji="◀", style=discord.ButtonStyle.secondary)
        async def prev(self, interaction: discord.Interaction, button: discord.ui.Button):
            self.idx = (self.idx - 1) % total
            self._update_label()
            await interaction.response.edit_message(embed=make_embed(self.idx), view=self)

        @discord.ui.button(style=discord.ButtonStyle.secondary, disabled=True, label="1/1")
        async def page_label(self, interaction: discord.Interaction, button: discord.ui.Button):
            pass

        @discord.ui.button(emoji="▶", style=discord.ButtonStyle.secondary)
        async def next(self, interaction: discord.Interaction, button: discord.ui.Button):
            self.idx = (self.idx + 1) % total
            self._update_label()
            await interaction.response.edit_message(embed=make_embed(self.idx), view=self)

        async def on_timeout(self):
            try:
                await self.message.edit(view=None)
            except Exception:
                pass

    view = CompareView()
    view.message = await ctx.send(embed=make_embed(0), view=view)


@bot.command(name="help", aliases=["h", "commands", "?"])
async def cmd_help(ctx, *, topic: str = ""):
    """Show help for ScriptureBot commands."""
    topic = topic.strip().lower()

    # ── Topic-specific help ───────────────────────────────────────────────────
    if topic in ("verse", "v", "scripture"):
        embed = discord.Embed(title="📖 !verse — Look Up Scripture", color=discord.Color.dark_gold())
        embed.add_field(name="Basic lookup", value=(
            "`!verse John 3:16` — KJV by default\n"
            "`!verse John 3:16 ESV` — any translation slug\n"
            "`!verse John 3:16 KJV ESV NASB` — parallel display\n"
            "`!verse John 3-5` — full chapters\n"
            "`!verse John 7:53-8:11` — cross-chapter range"
        ), inline=False)
        embed.add_field(name="Random verses", value=(
            "`!verse` — fully random\n"
            "`!verse John` — random from a book\n"
            "`!verse bible ot` / `!verse bible nt` / `!verse bible apocrypha`"
        ), inline=False)
        embed.add_field(name="Ancient languages", value=(
            "`!verse John 3:16 OE` — Old English (Wessex Gospels)\n"
            "`!verse Psalm 23 WLC` — Hebrew (Westminster Leningrad Codex)\n"
            "`!verse John 3:16 TR` — Greek NT (Textus Receptus)\n"
            "`!verse Genesis 1:1 LXX` — Septuagint (Greek OT)\n"
            "`!verse John 3:16 VULG` / `vulgate` / `latin` — Vulgata\n"
            "`!verse John 3:16 peshitta` / `syriac` — Peshitta\n"
            "`!verse John 3:16 CSL` / `slavonic` — Church Slavonic"
        ), inline=False)
        embed.add_field(name="Special translations", value=(
            "`!verse John 3:16 Knox` — Knox Bible\n"
            "`!verse Tobit 1:1 DRB` — Douay-Rheims\n"
            "`!translations` — full list of available translation slugs"
        ), inline=False)
        await ctx.send(embed=embed)
        return

    if topic in ("strong", "strongs"):
        embed = discord.Embed(title="📚 !strong — Strong's Lexicon & Concordance", color=discord.Color.dark_gold())
        embed.description = (
            "`!strong G3588` — Greek lexicon entry\n"
            "`!strong H7225` — Hebrew lexicon entry\n"
            "`!strong John 3:16` — verse with every word tagged with its Strong's number\n"
            "`!strong G26 in John` — every occurrence of that number within one book (concordance)\n\n"
            "Concordance search is scoped to a single canonical Bible book at a time — "
            "a whole-Bible search would mean hundreds of live lookups per query."
        )
        await ctx.send(embed=embed)
        return

    if topic in ("compare", "ancient", "cmp"):
        embed = discord.Embed(title="🏛️ !compare — Multi-Translation View", color=discord.Color.dark_gold())
        embed.description = (
            "`!compare John 3:16` — verse across all English translations\n"
            "`!compare ancient John 3:16` — verse across ancient language witnesses\n"
            "`!compare strong John 3:16` — KJV + original Greek (NT) or Hebrew (OT), each word tagged with its Strong's number\n\n"
            "Ancient NT: KJV · Textus Receptus (Greek) · Vulgate · Peshitta · Church Slavonic · Old English\n"
            "Ancient OT: KJV · Hebrew (WLC) · LXX (Greek) · Vulgate · Peshitta · Church Slavonic · Old English\n"
            "Apocrypha: KJV · LXX · Vulgate · Peshitta · Church Slavonic"
        )
        await ctx.send(embed=embed)
        return

    if topic in ("parallel", "poem", "classical", "par"):
        embed = discord.Embed(title="📜 !parallel — Classical & Poetic Texts", color=discord.Color.dark_gold())
        embed.add_field(name="Usage", value="`!parallel <work> <book>.<lines>`", inline=False)
        embed.add_field(name="Examples", value=(
            "`!parallel Il. 6.440-465` — Iliad (Pope EN + Greek)\n"
            "`!parallel Aen. 4.1-30` — Aeneid (Dryden EN + Latin)\n"
            "`!parallel Met. 1.1-20` — Metamorphoses (Garth/Dryden + Latin)\n"
            "`!parallel Heliand 1.1-30` — Heliand (Scott EN + Old Saxon)\n"
            "`!parallel Republic 1.1-20` — Plato (Jowett EN + Greek)\n"
            "`!parallel` — full list of available works"
        ), inline=False)
        embed.add_field(name="Plato — Stephanus ranges", value="\n".join(
            f"`{name}` — {first}–{last}"
            for name, (first, last) in _PLATO_STEPHANUS_RANGES.items()
        ), inline=False)
        await ctx.send(embed=embed)
        return

    if topic in ("books", "book"):
        embed = discord.Embed(title="📚 !books — Browse Collections", color=discord.Color.dark_gold())
        embed.description = (
            "`!books` — browse all loaded scripture collections\n"
            "`!books Genesis` — show Genesis chapter/verse breakdown\n"
            "`!books Augustine` — list works by an author\n\n"
            "The interactive menu lets you drill down into categories. "
            "Click any book name to see its chapter and verse counts."
        )
        embed.add_field(name="Citation formats by corpus", value=(
            "**Bible** — `!verse John 3:16` · `!verse Genesis 1:1-3`\n"
            "**Apocrypha** — `!verse Sirach 24:1` · `!verse 1 Maccabees 2:1`\n"
            "**Mishnah** — `!verse Berakhot 1:1` *(tractate chapter:mishnah)*\n"
            "**Babylonian Talmud** — `!verse Berakhot 2a:3` *(tractate daf-side:section)*\n"
            "**Jerusalem Talmud** — `!verse Jerusalem Talmud Berakhot 1:1` *(ch:halakhah)*\n"
            "**Tosefta** — `!verse Tosefta Berakhot 1:1` *(chapter:halakhah)*\n"
            "**Targum Onkelos** — `!verse Targum Onkelos Genesis 1:1`\n"
            "**Targum Jonathan** — `!verse Targum Jonathan Isaiah 1:1`\n"
            "**Midrash Rabbah** — `!verse Bereshit Rabbah 1:1` *(section:subsection)*\n"
            "**Zohar** — `!verse Zohar Bereshit 5` *(parasha + segment)*\n"
            "**Sefer Yetzirah** — `!verse Sefer Yetzirah 1:1` · **Tanya** — `!verse Tanya 1:1`\n"
            "**Quran** — `!verse Quran 2:255` · **Hadith** — `!verse Sahih al-Bukhari 1:1`\n"
            "**Plato** — `!verse Republic 514a` *(Stephanus)* · `!help books` for full list"
        ), inline=False)
        await ctx.send(embed=embed)
        return

    if topic in ("votd", "verseoftheday", "dayverse"):
        embed = discord.Embed(title="🌅 !votd — Verse of the Day", color=discord.Color.dark_gold())
        embed.description = (
            "`!votd` — today's verse (from verseoftheday.com, KJV)\n"
            "`!votd ESV` — verse of the day in a specific translation\n"
            "`!votd full` — KJV verse + ancient translations + first patristic commentary\n"
            "`!votd extended` — full VOTD + today's calendar across all five traditions\n\n"
            "A new verse is posted automatically each day in this server's configured channel — "
            "server admins can set that up with `!help votdsetup`."
        )
        await ctx.send(embed=embed)
        return

    if topic in ("features", "feature"):
        embed = discord.Embed(title="⚙️ !features — Optional Server Features", color=discord.Color.dark_gold())
        embed.description = (
            "All off by default. Requires Administrator permission to change.\n\n"
            "`!features` — show current on/off state for this server\n"
            "`!features react_save on` — react 📌 to a verse embed to bookmark it\n"
            "`!features streaks on` — show your `!plan` check-in streak\n"
            "`!features export on` — let `!saved export` send your full bookmark list as a text file"
        )
        await ctx.send(embed=embed)
        return

    if topic in ("votdsetup", "votdconfig"):
        embed = discord.Embed(title="⚙️ !votdsetup — Configure Daily VOTD (Admin)", color=discord.Color.dark_gold())
        embed.description = (
            "Each server picks its own channel, time, and mode for the daily Verse of the Day post.\n\n"
            "`!votdsetup` — show this server's current config\n"
            "`!votdsetup channel #general` — set the announcement channel\n"
            "`!votdsetup time 04:00` — set the post time (24h UTC)\n"
            "`!votdsetup mode full` — `basic` (verse only) · `full` (+ ancients + commentary) · `extended` (+ calendar)\n"
            "`!votdsetup off` — disable daily VOTD for this server\n\n"
            "Requires Administrator permission."
        )
        await ctx.send(embed=embed)
        return

    if topic in ("discover",):
        embed = discord.Embed(title="🔭 !discover — Random Passage, Any Tradition", color=discord.Color.dark_gold())
        embed.description = (
            "`!discover` — a random passage from any loaded tradition: scripture, LDS scripture, "
            "Septuagint, Enoch/Jubilees, Apostolic Fathers, Quran, classical texts, Jewish texts, "
            "Baha'i, Gnostic, Dharmic, Norse, Ancient Near Eastern, patristics, and medieval sources.\n\n"
            "Same underlying picker as bare `!verse` — `!discover` is just the more obvious name for it."
        )
        await ctx.send(embed=embed)
        return

    if topic in ("study",):
        embed = discord.Embed(title="🔎 !study — Verse + Patristic Commentary", color=discord.Color.dark_gold())
        embed.description = (
            "`!study John 3:16` — looks up the verse, then shows patristic commentary on it "
            "(from catenabible.com), in one command instead of two.\n\n"
            "Equivalent to running `!verse` followed by `!catena` on the same reference."
        )
        await ctx.send(embed=embed)
        return

    if topic in ("interlinear", "inter", "il"):
        embed = discord.Embed(title="🔤 !interlinear — Word-by-Word Image", color=discord.Color.dark_gold())
        embed.description = (
            "`!interlinear John 3:16` — Greek NT interlinear\n"
            "`!interlinear Psalm 23:1` — Hebrew OT interlinear\n\n"
            "Renders each word of the original text with its transliteration and short gloss "
            "stacked underneath, as an image — built on the same Strong's tagging as `!strong`. "
            "Hebrew columns read right-to-left, matching a printed Hebrew interlinear.\n\n"
            "Capped at 60 tagged words per verse (image width limit)."
        )
        await ctx.send(embed=embed)
        return

    if topic in ("reverseinterlinear", "rinterlinear", "ril", "kjvinterlinear"):
        embed = discord.Embed(title="🔤 !reverseinterlinear — KJV Reading-Order Interlinear", color=discord.Color.dark_gold())
        embed.description = (
            "`!reverseinterlinear John 3:16`\n\n"
            "Shows the actual KJV verse text in its own natural English word order "
            "(unlike `!interlinear`, which orders by the original Greek/Hebrew) — each "
            "English word or phrase tagged with the Strong's number of the word(s) it "
            "translates. A Hebrew or Greek word often covers more than one English word "
            "(e.g. \"In the beginning\" is a single Hebrew word); the tag covers the "
            "whole phrase in that case.\n\n"
            "Capped at 60 tagged words per verse (image width limit)."
        )
        await ctx.send(embed=embed)
        return

    if topic in ("timeline", "chronology"):
        embed = discord.Embed(title="🗓️ !timeline — Chronological Placement", color=discord.Color.dark_gold())
        embed.description = (
            "`!timeline Abraham` — where a person, book, or event falls in James Ussher's "
            "chronology (Annals of the World, 1658, public domain), with the entries just "
            "before and after for context.\n\n"
            "Dates follow Ussher's own reckoning specifically, not a modern scholarly consensus — "
            "useful alongside `!study` for seeing where things fall relative to each other."
        )
        await ctx.send(embed=embed)
        return

    if topic in ("dictionary", "dict", "define"):
        embed = discord.Embed(title="📔 !dictionary — Bible Dictionary", color=discord.Color.dark_gold())
        embed.description = (
            "`!dictionary Aaron` — look up a person, place, or term\n\n"
            "Combines Easton's Bible Dictionary (1897) and Smith's Bible Dictionary (1863), "
            "both public domain — encyclopedia-style background, distinct from `!topic`'s "
            "thematic scripture outlines and `!strong`'s word-level Greek/Hebrew lexicon."
        )
        await ctx.send(embed=embed)
        return

    if topic in ("save", "saved", "unsave", "bookmark", "bookmarks"):
        embed = discord.Embed(title="📌 Personal Bookmarks", color=discord.Color.dark_gold())
        embed.description = (
            "`!save John 3:16` — save a verse to your personal list\n"
            "`!save John 3:16 | this got me through a hard week` — save with a personal note\n"
            "`!saved` — show your saved verses (with any notes)\n"
            "`!unsave 2` — remove saved verse #2 (number from `!saved`)\n\n"
            "Saving an already-saved verse with a new `| note` updates the note instead of "
            "duplicating the entry.\n\n"
            "Bookmarks are personal — only you can see and manage your own list."
        )
        await ctx.send(embed=embed)
        return

    if topic in ("plan", "readingplan"):
        embed = discord.Embed(title="📅 !plan — Reading Plan", color=discord.Color.dark_gold())
        embed.description = (
            "`!plan start John` — start a chapter-a-day plan through a book\n"
            "`!plan` or `!plan today` — show today's assigned chapter\n"
            "`!plan status` — see your progress\n"
            "`!plan stop` — cancel your plan\n\n"
            "One plan per person. The chapter shown advances automatically by date, "
            "not by how often you check in."
        )
        await ctx.send(embed=embed)
        return

    if topic in ("leaderboard", "lb"):
        embed = discord.Embed(title="🏆 !leaderboard — Bookmark Leaderboard", color=discord.Color.dark_gold())
        embed.description = (
            "`!leaderboard` — shows who has saved the most verses with `!save`.\n\n"
            "For overall bot usage (most cited verses/books/commands), see `!stats` instead."
        )
        await ctx.send(embed=embed)
        return

    if topic in ("prefer", "preference", "defaulttranslation"):
        embed = discord.Embed(title="⭐ !prefer — Default Translation", color=discord.Color.dark_gold())
        embed.description = (
            "`!prefer ESV` — set your default translation\n"
            "`!prefer` — show your current default\n"
            "`!prefer off` — clear it (back to local KJV)\n\n"
            "Once set, plain `!verse John 3:16` uses your default automatically. "
            "An explicit suffix (`!verse John 3:16 NASB`) always overrides it for that one lookup.\n\n"
            "Only affects standard Bible books covered by that translation — references like "
            "Enoch, Mishnah, or Quran fall back to their normal local text regardless."
        )
        await ctx.send(embed=embed)
        return

    if topic in ("xref", "xrefs", "crossref", "crossreference"):
        embed = discord.Embed(title="🔗 !xref — Cross-References", color=discord.Color.dark_gold())
        embed.description = (
            "`!xref John 3:16` — up to 15 related verses, most-attested first\n\n"
            "From the Treasury of Scripture Knowledge (public domain, ~340,000 references), "
            "via openbible.info's structured dataset (CC-BY). Covers the 66-book Protestant canon only."
        )
        await ctx.send(embed=embed)
        return

    if topic in ("topic", "topics", "naves", "topical"):
        embed = discord.Embed(title="📚 !topic — Nave's Topical Bible", color=discord.Color.dark_gold())
        embed.description = (
            f"`!topic love` — browse scripture organized by subject ({topic_count()} subjects)\n\n"
            "Gives you the full outline for that subject, with embedded scripture citations, exactly "
            "as Nave arranged it — not individual verse links like `!xref`.\n\n"
            "If your exact wording isn't a subject, you'll get a list of similar subject names to try."
        )
        await ctx.send(embed=embed)
        return

    if topic in ("card", "versecard", "quotecard"):
        embed = discord.Embed(title="🖼️ !card — Shareable Verse Image", color=discord.Color.dark_gold())
        embed.description = (
            "`!card John 3:16` — renders the verse as a parchment-style PNG you can share\n"
            "`!card` — random verse, same style\n\n"
            "Same underlying lookup as `!verse`, just rendered as an image instead of an embed."
        )
        await ctx.send(embed=embed)
        return

    if topic in ("subscribe", "unsubscribe", "dm"):
        embed = discord.Embed(title="📬 Daily Verse by DM", color=discord.Color.dark_gold())
        embed.description = (
            f"`!subscribe` — get the daily Verse of the Day sent to your DMs (around {DM_DIGEST_TIME} UTC)\n"
            "`!unsubscribe` — stop it\n\n"
            "Independent of any server's `!votdsetup` channel post — this goes straight to you."
        )
        await ctx.send(embed=embed)
        return

    if topic in ("today", "calendar", "liturgy", "feast", "saint"):
        embed = discord.Embed(title="📅 !today — Liturgical & Religious Calendar", color=discord.Color.dark_gold())
        embed.description = (
            "What's going on today across religious traditions — feast days, "
            "saints, liturgical seasons, Hebrew/Hijri dates and holidays."
        )
        embed.add_field(name="Usage", value=(
            "`!today` — today, all five traditions\n"
            "`!today christian` — Catholic + Anglican + Orthodox in one embed\n"
            "`!today anglican` — Common Worship calendar (Church of England)\n"
            "`!today catholic` — Roman Rite (General Calendar)\n"
            "`!today orthodox` — Eastern Orthodox commemorations + fasting info\n"
            "`!today jewish` — Hebrew date + Jewish observances\n"
            "`!today islam` — Hijri date + Islamic holidays\n"
            "`!today catholic 2026-12-25` — any tradition + a specific date\n"
            "`!today 12-25` — MM-DD with the current year"
        ), inline=False)
        embed.add_field(name="Sources", value=(
            "Catholic — universalis.com · "
            "Anglican — bundled Common Worship calendar + Easter computus · "
            "Orthodox — orthocal.info · "
            "Jewish — hebcal.com · "
            "Islamic — api.aladhan.com"
        ), inline=False)
        await ctx.send(embed=embed)
        return

    if topic in ("bcp", "office", "matins", "evensong", "vespers", "mp", "ep"):
        embed = discord.Embed(title="📖 !bcp — Book of Common Prayer Daily Office",
                              color=discord.Color.dark_blue())
        embed.description = (
            "The Psalms, lessons, and Collect appointed for Morning or Evening Prayer, "
            "from the Canadian 1962 BCP (with 1922 daily-office lectionary) and the "
            "Coverdale Psalter on its 30-day cycle. KJV text for the lessons.\n\n"
            "Pages are paginated with ◀ ▶ buttons. Midnight–noon defaults to Morning Prayer, "
            "noon–midnight to Evening Prayer."
        )
        embed.add_field(name="The full office", value=(
            "`!bcp` — today, time-appropriate\n"
            "`!bcp morning` / `!bcp evening` — full office for that period\n"
            "`!bcp 2026-12-25` — full office for a specific date"
        ), inline=False)
        embed.add_field(name="Individual pieces", value=(
            "`!bcp mp` / `!mp` — both lessons for Morning Prayer\n"
            "`!bcp ep` / `!ep` — both lessons for Evening Prayer\n"
            "`!bcp 1` / `!bcp 2` — first or second lesson, time-appropriate\n"
            "`!bcp psalm` / `!psalm` — psalms for the current period\n"
            "`!psalm mp` / `!psalm ep` — psalms for that specific period\n"
            "`!bcp collect` / `!collect` — the Collect of the Day\n"
            "`!bcp prayer` / `!prayer` — a random devotional prayer · `!help prayer`"
        ), inline=False)
        embed.add_field(name="Notes", value=(
            "• The lectionary year (I/II) is computed from the most-recent Advent Sunday.\n"
            "• On a Red-Letter Saint's Day the daily lessons are still used, but the "
            "Saint's collect is shown in place of the seasonal one.\n"
            "• Sources: lectionarycentral.com (lessons), BCP 1662 (psalter & collects)."
        ), inline=False)
        await ctx.send(embed=embed)
        return

    if topic in ("prayer", "collect"):
        embed = discord.Embed(title="📿 !prayer — A random BCP prayer or collect",
                              color=discord.Color.dark_purple())
        embed.description = (
            "A random devotional prayer drawn from the Book of Common Prayer 1662."
        )
        embed.add_field(name="Usage", value=(
            "`!prayer` — a random prayer/collect (alias for `!bcp prayer`)\n"
            "`!collect` — the Collect of the Day (alias for `!bcp collect`)\n"
            "`!collect 2026-12-25` — collect for a specific date"
        ), inline=False)
        embed.add_field(name="Sources drawn from", value=(
            "Fixed collects of Morning and Evening Prayer (Collect for Peace, Grace, "
            "Aid against all Perils, Prayer of Saint Chrysostom)\n"
            "Prayers upon Several Occasions and the Thanksgivings\n"
            "The General Confession and Collect for Purity\n"
            "Prayers from the Visitation of the Sick, Burial of the Dead, and "
            "Forms of Prayer at Sea\n"
            "Seasonal Sunday collects (filtered to exclude state and saint's-day collects)"
        ), inline=False)
        await ctx.send(embed=embed)
        return

    if topic in ("strong", "strongs", "concordance"):
        embed = discord.Embed(title="📚 !strong — Strong's Concordance", color=discord.Color.dark_gold())
        embed.description = (
            "Look up a Strong's number for definitions, transliteration, "
            "pronunciation, and gloss — or pass a verse to see each word "
            "tagged with its Strong's number."
        )
        embed.add_field(name="Lexicon lookup", value=(
            "`!strong G3588` — Greek NT (Thayer's Greek Lexicon)\n"
            "`!strong H7225` — Hebrew OT (Brown-Driver-Briggs)"
        ), inline=False)
        embed.add_field(name="Tagged verse (alias for !compare strong)", value=(
            "`!strong John 3:16` — KJV + every Greek word tagged with its Strong's number\n"
            "`!strong Psalm 23:1` — same, for Hebrew OT"
        ), inline=False)
        embed.set_footer(text="Source: bolls.life")
        await ctx.send(embed=embed)
        return

    if topic in ("jewish", "rabbinic", "talmud", "mishnah", "zohar", "kabbalah"):
        embed = discord.Embed(title="✡️ Jewish Texts — Citation Guide", color=discord.Color.dark_gold())
        embed.add_field(name="Mishnah  (chapter:mishnah)", value=(
            "`!verse Berakhot 1:1`\n`!verse Avot 2:1`\n`!verse Pirkei Avot 3:14`"
        ), inline=True)
        embed.add_field(name="Babylonian Talmud  (tractate daf-side[:section])", value=(
            "`!verse Berakhot 2a`  *(whole daf)*\n"
            "`!verse Berakhot 2a:3`  *(section 3)*\n"
            "`!verse Shabbat 31a:1`\n"
            "daf = page + `a` (front) or `b` (back)"
        ), inline=False)
        embed.add_field(name="Jerusalem Talmud  (chapter:halakhah)", value=(
            "`!verse Jerusalem Talmud Berakhot 1:1`\n"
            "`!verse Yerushalmi Shabbat 2:1`\n"
            "39 tractates available via Sefaria (Guggenheimer trans.)"
        ), inline=False)
        embed.add_field(name="Tosefta  (chapter:halakhah)", value=(
            "`!verse Tosefta Berakhot 1:1`\n`!verse Tosefta Shabbat 2:3`"
        ), inline=True)
        embed.add_field(name="Targumim  (chapter:verse)", value=(
            "`!verse Targum Onkelos Genesis 1:1`  *(Torah)*\n"
            "`!verse Targum Jonathan Isaiah 6:1`  *(Prophets)*\n"
            "`!verse Targum Pseudo-Jonathan Genesis 1:1`\n"
            "`!verse Targum Neofiti Genesis 1:1`"
        ), inline=False)
        embed.add_field(name="Midrash  (section:subsection)", value=(
            "`!verse Bereshit Rabbah 1:1`\n"
            "`!verse Shemot Rabbah 1:1`\n"
            "`!verse Mechilta 1:1`  ·  `!verse Sifra 1:1`\n"
            "`!verse Pirkei DeRabbi Eliezer 1:1`"
        ), inline=False)
        embed.add_field(name="Zohar  (parasha + segment)", value=(
            "`!verse Zohar Bereshit 5`\n"
            "`!verse Zohar Introduction 1`\n"
            "`!verse Zohar`  *(random)*\n"
            "54 parashot — use `!books` → Kabbalah → Zohar for full list"
        ), inline=True)
        embed.add_field(name="Other Kabbalah  (chapter:verse)", value=(
            "`!verse Sefer Yetzirah 1:1`\n"
            "`!verse Sefer HaBahir 1:1`\n"
            "`!verse Tikkunei Zohar 1:1`\n"
            "`!verse Tanya 1:1`"
        ), inline=True)
        embed.add_field(name="Maimonides  (section, chapter:halacha)", value=(
            "`!verse Mishneh Torah, Repentance 1:1`\n"
            "`!verse Mishneh Torah, Foundations of the Torah 1:1`\n"
            "`!verse Mishneh Torah, Kings and Wars 1:1`\n"
            "`!verse Guide for the Perplexed 1:1`  *(part:chapter)*\n"
            "84 sections · use `!books` → Maimonides for full list"
        ), inline=False)
        await ctx.send(embed=embed)
        return

    if topic in ("ane", "ancient near east", "ancient_near_east", "mesopotamia", "egypt", "egyptian", "ugaritic", "gilgamesh", "baal"):
        embed = discord.Embed(title="🏺 Ancient Near Eastern Texts — Citation Guide", color=discord.Color.dark_gold())
        embed.add_field(name="Epic of Gilgamesh  (tablet:section)", value=(
            "`!verse Gilgamesh 1:1`  *(Tablet I, section 1)*\n"
            "`!verse Gilgamesh 11`   *(The Flood — whole tablet)*\n"
            "`!parallel Gilgamesh 11.1`  *(English + Akkadian)*\n"
            "12 tablets · cite by tablet number, optionally :section"
        ), inline=False)
        embed.add_field(name="The Baal Cycle  (episode:section)", value=(
            "`!verse Baal 1:1`  *(Baal and Yamm)*\n"
            "`!verse Baal 2:1`  *(The Palace of Baal)*\n"
            "`!verse Baal 3:1`  *(Baal and Mot)*\n"
            "`!parallel Baal 1.5`  *(English + Ugaritic)*\n"
            "3 episodes · cite as Baal <episode>:<section>"
        ), inline=False)
        embed.add_field(name="Egyptian Texts  (section number)", value=(
            "`!verse Aten 1`  *(Great Hymn to the Aten — 13 sections)*\n"
            "`!verse Book of the Dead 1`  *(52 chapters)*\n"
            "`!verse Leiden Hymns 1`  *(22 stanzas)*\n"
            "`!verse Amenemope 1`  *(Instruction of Amenemope — 36 chapters)*\n"
            "`!verse Two Ways 1`  *(Book of Two Ways — 19 spells)*\n"
            "Or omit the number for the full text"
        ), inline=False)
        embed.add_field(name="Aramaic Wisdom", value=(
            "`!verse Ahikar 1`  *(Story of Ahikar — 5 sections)*"
        ), inline=True)
        embed.add_field(name="Random", value=(
            "`!verse ancient_near_east`  *(random from all ANE texts)*"
        ), inline=True)
        await ctx.send(embed=embed)
        return

    if topic in ("islamic", "islam", "quran", "hadith", "muslim"):
        embed = discord.Embed(title="☪️ Islamic Texts — Citation Guide", color=discord.Color.green())
        embed.add_field(name="Quran  (surah:ayah)", value=(
            "`!verse Quran 2:255`  *(Al-Baqara, verse 255 — the Throne Verse)*\n"
            "`!verse Quran 1:1`  *(Al-Faatiha, verse 1)*\n"
            "`!verse Quran 112:1`  *(Al-Ikhlaas)*\n"
            "114 surahs · use `!books` → Quran for full list with names and verse counts"
        ), inline=False)
        embed.add_field(name="The Six Books (Kutub al-Sittah)", value=(
            "`!verse Sahih al-Bukhari 1`  *(1–7,563, 97 books)*\n"
            "`!verse Sahih Muslim 1`  *(1–7,563, 56 books)*\n"
            "`!verse Sunan Abu Dawud 1`  *(1–5,274, 43 books)*\n"
            "`!verse Jami at-Tirmidhi 1`  *(1–3,956, 49 books)*\n"
            "`!verse Sunan an-Nasa'i 1`  *(1–5,761, 51 books)*\n"
            "`!verse Sunan Ibn Majah 1`  *(1–4,341, 37 books)*\n"
            "Cite by sequential hadith number — no chapter needed"
        ), inline=False)
        embed.add_field(name="Other Hadith Collections", value=(
            "`!verse Muwatta Malik 1`  *(1–1,852, 61 books)*\n"
            "`!verse Forty Hadith of Nawawi 1`  *(1–42)*\n"
            "`!verse Forty Hadith of Dehlawi 1`  *(1–40)*\n"
        ), inline=True)
        embed.add_field(name="Aliases", value=(
            "`Bukhari`, `Muslim`, `Abu Dawud`, `Tirmidhi`\n"
            "`Nasai`, `Ibn Majah`, `Muwatta`, `Nawawi`\n"
            "`Dehlawi`, `Shah Waliullah`"
        ), inline=True)
        embed.add_field(name="Sira & Islamic Biography", value=(
            "The Sira (Ibn Ishaq/Ibn Hisham) and Stories of the Prophets (Ibn Kathir) "
            "are not available in a structured API. They exist as PDFs at archive.org. "
            "The Quran and Hadith remain the primary accessible sources."
        ), inline=False)
        await ctx.send(embed=embed)
        return

    if topic in ("search", "find"):
        embed = discord.Embed(title="🔍 !search — Search Scripture", color=discord.Color.dark_gold())
        embed.description = (
            "`!search shepherd` — search KJV for a phrase\n"
            "`!search shepherd ESV` — search a specific translation\n\n"
            "Rate-limited: 3 searches per 30 seconds per user."
        )
        await ctx.send(embed=embed)
        return

    if topic in ("oracle", "delphi", "homer", "virgil", "sortes"):
        embed = discord.Embed(title="🎲 Divination Commands", color=discord.Color.dark_gold())
        embed.add_field(name="!oracle", value="Random verse from an oracular corpus (Sibylline, Enoch, etc.)", inline=False)
        embed.add_field(name="!delphi", value="Random Delphic maxim", inline=False)
        embed.add_field(name="!homer", value="Roll three dice → receive a Homeric oracle", inline=False)
        embed.add_field(name="!virgil", value="Sortes Virgilianae — random passage from the Aeneid", inline=False)
        await ctx.send(embed=embed)
        return

    if topic in ("ccc", "catechism"):
        embed = discord.Embed(title="⛪ !ccc — Catechism of the Catholic Church", color=discord.Color.dark_gold())
        embed.description = (
            "`!ccc 1` — paragraph 1\n"
            "`!ccc 1700-1715` — paragraph range\n"
            "`!ccc random` — random paragraph"
        )
        await ctx.send(embed=embed)
        return

    if topic in ("summa", "st", "aquinas"):
        embed = discord.Embed(title="🏛️ !summa — Summa Theologica", color=discord.Color.dark_gold())
        embed.description = (
            "`!summa I.1.1` — Part I, Question 1, Article 1\n"
            "`!summa II-II.23.1` — Second Part of Part II\n"
            "`!summa random` — random article"
        )
        await ctx.send(embed=embed)
        return

    if topic in ("creed", "creeds"):
        embed = discord.Embed(title="📜 !creed — The Ecumenical Creeds", color=discord.Color.dark_gold())
        embed.description = (
            "`!creed` — list the creeds\n"
            "`!creed apostle` — The Apostles' Creed\n"
            "`!creed nicene` — The Nicene Creed\n"
            "`!creed athanasius` — The Athanasian Creed (Quicunque Vult)\n\n"
            "Add `latin` for the traditional Latin text, `greek` for the Nicene Creed's original "
            "conciliar Greek, or `parallel` for everything available: "
            "`!creed apostle latin` · `!creed nicene greek` · `!creed nicene parallel`\n\n"
            "The Nicene Creed is the only one with a genuine ancient Greek original — the "
            "Athanasian Creed, despite its name, was actually composed in Latin.\n\n"
            "English text is traditional, as in the 1662 Book of Common Prayer."
        )
        await ctx.send(embed=embed)
        return

    if topic in ("catena",):
        embed = discord.Embed(title="📿 !catena — Patristic Commentary", color=discord.Color.dark_gold())
        embed.description = (
            "`!catena John 3:16` — patristic commentary on a verse\n"
            "Sourced from catenabible.com"
        )
        await ctx.send(embed=embed)
        return

    # ── Main help menu ────────────────────────────────────────────────────────
    embed = discord.Embed(
        title="📖 ScriptureBot — Help",
        description="Use `!help <command>` for detailed help on any command.",
        color=discord.Color.dark_gold()
    )
    embed.add_field(name="✡️ Jewish Texts", value=(
        "`!help jewish` — Mishnah · Talmud · Jerusalem Talmud · Tosefta · Targum · Midrash · Zohar · Kabbalah"
    ), inline=False)
    embed.add_field(name="☪️ Islamic Texts", value=(
        "`!help islamic` — Quran (114 surahs) · Hadith (9 collections) · citation formats"
    ), inline=False)
    embed.add_field(name="🏺 Ancient Near Eastern Texts", value=(
        "`!help ane` — Gilgamesh · Baal Cycle · Egyptian texts · Ahikar · citation formats"
    ), inline=False)
    embed.add_field(name="📖 Scripture", value=(
        "`!verse` — look up or randomise a verse · `!help verse`\n"
        "`!compare` — multi-translation view · `!help compare`\n"
        "`!search` — search for a phrase · `!help search`\n"
        "`!votd` — verse of the day · `!help votd`\n"
        "`!today` — liturgical calendar across traditions · `!help today`\n"
        "`!books` — browse collections · `!help books`\n"
        "`!translations` — list translation slugs\n"
        "`!prefer` — set your default translation · `!help prefer`"
    ), inline=False)
    embed.add_field(name="📜 Classical & Poetic", value=(
        "`!parallel` — Homer, Virgil, Ovid, Heliand, Plato + more · `!help parallel`"
    ), inline=False)
    embed.add_field(name="⛪ Catholic", value=(
        "`!ccc` — Catechism · `!help ccc`\n"
        "`!summa` — Summa Theologica · `!help summa`\n"
        "`!canon` — Code of Canon Law\n"
        "`!catena` — Patristic commentary · `!help catena`"
    ), inline=False)
    embed.add_field(name="📜 Creeds", value=(
        "`!creed apostle` / `nicene` / `athanasius` — traditional English · `!help creed`"
    ), inline=False)
    embed.add_field(name="📖 Anglican Daily Office", value=(
        "`!bcp` — psalms, lessons, and collect for Morning/Evening Prayer · `!help bcp`\n"
        "`!mp` / `!ep` — both lessons for that period\n"
        "`!psalm` / `!psalm mp` / `!psalm ep` — appointed Coverdale psalms\n"
        "`!collect` — the Collect of the Day\n"
        "`!prayer` — random devotional prayer from the BCP · `!help prayer`"
    ), inline=False)
    embed.add_field(name="🎲 Divination", value=(
        "`!oracle` `!delphi` `!homer` `!virgil` — oracular & sortes · `!help oracle`"
    ), inline=False)
    embed.add_field(name="🔭 Discovery & Personal", value=(
        "`!discover` — random passage from any loaded tradition · `!help discover`\n"
        "`!study` — verse + patristic commentary together · `!help study`\n"
        "`!xref` — cross-references (Treasury of Scripture Knowledge) · `!help xref`\n"
        "`!topic` — browse scripture by subject (Nave's Topical Bible) · `!help topic`\n"
        "`!save` / `!saved` / `!unsave` — personal bookmarks · `!help save`\n"
        "`!plan` — chapter-a-day reading plan · `!help plan`\n"
        "`!leaderboard` — most active bookmarkers · `!help leaderboard`\n"
        "`!subscribe` / `!unsubscribe` — daily verse by DM · `!help subscribe`\n"
        "`!card` — shareable verse image · `!help card`"
    ), inline=False)
    embed.add_field(name="⚙️ Server Setup (Admin)", value=(
        "`!votdsetup` — configure this server's daily VOTD channel/time/mode · `!help votdsetup`\n"
        "`!features` — turn optional features on/off · `!help features`"
    ), inline=False)
    embed.add_field(name="🏛️ Ancient Languages & Strong's", value=(
        "Append to `!verse`: `OE` `WLC` `LXX` `TR` `VULG` `peshitta` `CSL`\n"
        "`!compare ancient <ref>` — all ancient witnesses at once · `!help compare`\n"
        "`!compare strong <ref>` — KJV + original-language Strong's tagging · `!help compare`\n"
        "`!strong G3588` / `!strong H7225` — Strong's lexicon lookup · `!help strong`"
    ), inline=False)
    embed.set_footer(text="!help verse · !help compare · !help votd · !help votdsetup · !help features · !help today · !help bcp · !help prayer · !help strong · !help books · !help parallel · !help oracle · !help discover · !help study · !help xref · !help topic · !help save · !help plan · !help leaderboard · !help subscribe · !help card · !help creed · !help ccc · !help summa")
    await ctx.send(embed=embed)


@bot.tree.command(name="help", description="Show ScriptureBot command help")
async def help_slash(interaction: discord.Interaction, topic: str = ""):
    await interaction.response.defer()
    ctx = await bot.get_context(interaction)
    await cmd_help(ctx, topic=topic)


@bot.command(name="translations", aliases=["trans", "tl"])
async def cmd_translations(ctx):
    """List all available Bible translations. Usage: !translations"""
    trans_list = list_translations()
    lines = trans_list.split("\n")

    # Balance the split by character count, not line count -- lines vary
    # enough in length that a line-count split let one column silently grow
    # past Discord's 1024-char embed field limit as translations were added.
    total_chars = sum(len(l) + 1 for l in lines)
    col1_lines, running = [], 0
    for l in lines:
        if col1_lines and running >= total_chars / 2:
            break
        col1_lines.append(l)
        running += len(l) + 1
    col2_lines = lines[len(col1_lines):]
    col1 = "\n".join(col1_lines)
    col2 = "\n".join(col2_lines)
    if len(col1) > 1000:
        col1 = col1[:997] + "…"
    if len(col2) > 1000:
        col2 = col2[:997] + "…"

    embed = discord.Embed(
        title="📖 Available Bible Translations",
        color=discord.Color.dark_gold()
    )
    embed.add_field(name="Via bolls.life (A–M)", value=col1, inline=True)
    embed.add_field(name="Via bolls.life (N–Z)", value=col2, inline=True)
    embed.add_field(
        name="Local translations (offline)",
        value=(
            "**DRB** — Douay-Rheims Bible (Challoner revision)\n"
            "**Knox** — Knox Bible, trans. Ronald Knox (1945–49)\n"
            "**KJV** — King James Version (no suffix needed)"
        ),
        inline=False
    )
    embed.add_field(
        name="Ancient languages (local)",
        value=(
            "**OE** — Old English (Wessex Gospels, ~990 AD) — Gospels only\n"
            "**WLC** / **Hebrew** — Westminster Leningrad Codex (Hebrew OT)\n"
            "**LXX** / **Septuagint** — Greek OT (Swete 1930)\n"
            "**TR** — Textus Receptus (Greek NT, Elzevir 1624)\n"
            "**VULG** / **Vulgate** — Vulgata Clementina (Latin)\n"
            "**Peshitta** / **Syriac** — Peshitta (Aramaic)\n"
            "**CSL** / **Slavonic** — Church Slavonic (Elizabeth Bible, 1757)"
        ),
        inline=False
    )
    embed.set_footer(text=(
        "Usage: !verse John 3:16 ESV  ·  !verse Tobit 1:1 NRSVCE  ·  "
        "!verse John 3:16 KJV ESV NASB (parallel)  ·  !verse John 3:16 Knox"
    ))
    await ctx.send(embed=embed)

@bot.tree.command(name="translations", description="List all available Bible translations")
async def translations_slash(interaction: discord.Interaction):
    await interaction.response.defer()
    ctx = await bot.get_context(interaction)
    await cmd_translations(ctx)


# ── !prefer — personal default translation ───────────────────────────────────────

@bot.command(name="prefer", aliases=["preference", "defaulttranslation"])
async def cmd_prefer(ctx, *, translation: str = ""):
    """Set your default Bible translation, so plain !verse lookups use it
    without typing the suffix every time.
    Usage: !prefer ESV   — set your default
           !prefer       — show your current default
           !prefer off   — clear it (back to local KJV)
    An explicit suffix on a lookup (e.g. !verse John 3:16 NASB) always overrides this.
    """
    arg = translation.strip().lower()
    uid = str(ctx.author.id)
    data = _load_user_prefs()

    if not arg:
        current = data.get(uid, {}).get("translation")
        if current:
            await ctx.send(f"Your default translation is **{current.upper()}**. Use `!prefer off` to clear it.")
        else:
            await ctx.send(
                "You don't have a default translation set — plain `!verse` lookups use the local KJV. "
                "Set one with `!prefer ESV` (see `!translations` for all slugs)."
            )
        return

    if arg in ("off", "none", "clear", "reset"):
        if uid in data:
            data[uid].pop("translation", None)
            if not data[uid]:
                del data[uid]
            _save_user_prefs(data)
        await ctx.send("Cleared your default translation. Plain `!verse` lookups will use the local KJV again.")
        return

    if arg not in TRANSLATION_SUFFIXES:
        await ctx.send(f"⚠️ `{arg}` isn't a recognized translation slug. See `!translations` for the full list.")
        return

    data.setdefault(uid, {})["translation"] = arg
    _save_user_prefs(data)
    await ctx.send(
        f"Your default translation is now **{arg.upper()}**. Plain `!verse <ref>` will use it automatically "
        "(an explicit suffix still overrides it)."
    )

@bot.tree.command(name="prefer", description="Set your default Bible translation for plain !verse lookups")
@app_commands.describe(translation="e.g. ESV, NASB — leave blank to check, or 'off' to clear")
async def prefer_slash(interaction: discord.Interaction, translation: str = ""):
    await interaction.response.defer()
    ctx = await bot.get_context(interaction)
    await cmd_prefer(ctx, translation=translation)


# ── Daily VOTD task ────────────────────────────────────────────────────────────

@tasks.loop(minutes=1)
async def _daily_votd_task():
    """Posts VOTD to every guild's configured channel/time (see !votdsetup).
    Dispatches per-guild based on its configured mode:
      basic    — verse only
      full     — verse + ancients + first commentary
      extended — full VOTD + today's calendar across five traditions
    """
    import datetime
    now = datetime.datetime.now(datetime.timezone.utc)
    cur_hm = f"{now.hour:02d}:{now.minute:02d}"
    cfg = _load_guild_config()
    for gid_str, settings in cfg.items():
        channel_id = settings.get("votd_channel_id")
        if not channel_id:
            continue
        if settings.get("votd_time", "04:00") != cur_hm:
            continue
        channel = bot.get_channel(int(channel_id))
        if not channel:
            continue
        mode = settings.get("votd_mode", "full")
        try:
            if mode == "basic":
                await _send_votd(channel)
            elif mode == "extended":
                await _send_votd_extended(channel)
            else:  # default to full for anything else
                await _send_votd_full(channel)
        except Exception:
            log.exception(f"Failed to post daily VOTD for guild {gid_str}")

    # Personal DM digest (independent of any guild's configured time/mode)
    if cur_hm == DM_DIGEST_TIME:
        for uid in list(_load_subscribers()):
            user = bot.get_user(uid)
            if not user:
                continue
            try:
                await _send_votd(user)
            except discord.Forbidden:
                pass  # user closed DMs; leave them subscribed rather than guess why
            except Exception:
                log.exception(f"Failed to DM daily verse to user {uid}")

@_daily_votd_task.before_loop
async def _before_daily_votd():
    await bot.wait_until_ready()




# ── !parallel — Bible & classical texts in parallel languages (alias: !poem) ──

LANG_LABEL = {"en": "English", "grc": "Ancient Greek", "lat": "Latin"}
LANG_COLOR = {
    "en":  discord.Color.dark_gold(),
    "grc": discord.Color.teal(),
    "lat": discord.Color.dark_red(),
}


@bot.command(name="parallel", aliases=["poem", "po", "par", "classical"])
async def cmd_parallel(ctx, *, reference: str = ""):
    """Look up a Bible verse or classical text in parallel languages. !parallel works for a list."""
    if not reference or reference.strip().lower() in ("works", "list", "help"):
        embed = discord.Embed(title="📜 Classical Poetry & Prose",
                              description=poem_list_works(),
                              color=discord.Color.dark_gold())
        await ctx.send(embed=embed)
        return

    ref = reference.strip()
    # Strip -p flag if present (parallel is always on)
    ref = re.sub(r'\s+--?p(?:arallel)?$', '', ref, flags=re.I).strip()

    async with ctx.typing():
        # ── Scripture reference? ───────────────────────────────────────────
        drb = is_drb_reference(ref)
        ref_clean = re.sub(
            r'\s+(drb|drv|dra|dr|douay[-\s]rheims?)\s*$', '', ref, flags=re.I
        ).strip() if drb else ref

        scripture_type = classify_scripture(ref_clean)
        if scripture_type:
            await _send_poem_scripture(ctx, ref_clean, scripture_type, drb)
            return

        # ── Classical poetry reference ─────────────────────────────────────
        spec = parse_poem_ref(ref_clean)
        if spec is None:
            await ctx.send(
                f"⚠️ Couldn't parse `{ref}`.\n"
                f"Examples: `!parallel Il. 6.440` · `!parallel John 3:16` · `!parallel Republic 514a` · `!parallel works`"
            )
            return

        result = poem_lookup(spec)
        if result.get("found") and result.get("pair_spec"):
            pair = lookup_pair(result)
            await _send_parallel(ctx, result, pair)
        else:
            await _send_poem_result(ctx, result)


@bot.tree.command(name="parallel", description="Look up a Bible verse or classical text in parallel languages")
@app_commands.describe(reference="e.g. Il. 6.440  Republic 514a  works",
                       parallel="Show original language alongside")
async def poem_slash(interaction: discord.Interaction,
                     reference: str, parallel: bool = False):
    await interaction.response.defer()
    ctx = await bot.get_context(interaction)
    if reference.strip().lower() in ("works", "list", "help"):
        embed = discord.Embed(title="📜 Classical Poetry & Prose",
                              description=poem_list_works(),
                              color=discord.Color.dark_gold())
        await ctx.send(embed=embed)
        return
    spec = parse_poem_ref(reference.strip())
    ref = reference.strip()
    drb = is_drb_reference(ref)
    ref_clean = re.sub(r'\s+(drb|drv|dra|dr|douay[-\s]rheims?)\s*$', '', ref, flags=re.I).strip() if drb else ref
    scripture_type = classify_scripture(ref_clean)
    if scripture_type:
        await _send_poem_scripture(ctx, ref_clean, scripture_type, drb)
        return
    spec = parse_poem_ref(ref_clean)
    if spec is None:
        await ctx.send(f"⚠️ Couldn't parse `{reference}`.")
        return
    result = poem_lookup(spec)
    if result.get("found") and result.get("pair_spec"):
        pair = lookup_pair(result)
        await _send_parallel(ctx, result, pair)
    else:
        await _send_poem_result(ctx, result)



async def _send_poem_scripture(ctx, reference: str, scripture_type: str, drb: bool):
    """
    Show a scripture verse bilingually.
    KJV mode:  English (KJV) | Hebrew (WLC) for OT
                              | Greek LXX for Apocrypha
                              | Greek TR for NT
    DRB mode:  English (DR)  | Latin (Vulgate) for everything
    """
    if drb:
        slugs = ["DRB", "VULG"]
        labels = {
            "DRB":  "Douay-Rheims Bible",
            "VULG": "Vulgata Clementina (Latin)",
        }
    else:
        if scripture_type == "ot":
            slugs = ["KJV", "WLC"]
            labels = {
                "KJV": "King James Version",
                "WLC": "Hebrew OT (Westminster Leningrad Codex)",
            }
        elif scripture_type == "apocrypha":
            slugs = ["KJV", "LXX"]
            labels = {
                "KJV": "King James Version",
                "LXX": "Septuagint (Brenton)",
            }
        else:  # NT
            slugs = ["KJV", "TR"]
            labels = {
                "KJV": "King James Version",
                "TR":  "Textus Receptus (Greek NT, Elzevir 1624)",
            }

    results = []
    for slug in slugs:
        s, display, text = await _fetch_one_translation(slug, reference)
        results.append((slug, labels.get(slug, display), text))

    embed = discord.Embed(
        title=f"📖 {reference}",
        color=discord.Color.dark_gold()
    )
    for slug, label, text in results:
        if len(text) > 1020:
            text = text[:1017] + "…"
        embed.add_field(name=f"**{slug}** — {label}", value=text, inline=False)

    await ctx.send(embed=embed)


async def _send_poem_result(ctx, result: dict):
    if not result.get("found"):
        embed = discord.Embed(title="❌ Not found",
                              description=result.get("error", "Unknown error"),
                              color=discord.Color.red())
        await ctx.send(embed=embed)
        return

    color = LANG_COLOR.get(result.get("lang", "en"), discord.Color.dark_gold())
    source = result.get("source", "")
    pages  = result.get("pages")

    if not pages:
        text = result["text"]
        if len(text) > 3900:
            text = text[:3897] + "…"
        embed = discord.Embed(title=f"📜 {result['reference']}",
                              description=text, color=color)
        embed.set_footer(text=source)
        await ctx.send(embed=embed)
        return

    total = len(pages)

    def make_embed(idx):
        e = discord.Embed(
            title=f"📜 {result['reference']} ({idx+1}/{total})",
            description=pages[idx], color=color)
        e.set_footer(text=source)
        return e

    class PoemView(discord.ui.View):
        def __init__(self):
            super().__init__(timeout=300)
            self.idx = 0

        @discord.ui.button(emoji="◀", style=discord.ButtonStyle.secondary)
        async def prev(self, interaction, button):
            self.idx = (self.idx - 1) % total
            self.lbl.label = f"{self.idx+1}/{total}"
            await interaction.response.edit_message(embed=make_embed(self.idx), view=self)

        @discord.ui.button(style=discord.ButtonStyle.secondary, disabled=True, label="1/N")
        async def lbl(self, interaction, button):
            pass

        @discord.ui.button(emoji="▶", style=discord.ButtonStyle.secondary)
        async def nxt(self, interaction, button):
            self.idx = (self.idx + 1) % total
            self.lbl.label = f"{self.idx+1}/{total}"
            await interaction.response.edit_message(embed=make_embed(self.idx), view=self)

        async def on_timeout(self):
            try: await self.message.edit(view=None)
            except Exception: pass

    view = PoemView()
    view.lbl.label = f"1/{total}"
    view.message = await ctx.send(embed=make_embed(0), view=view)


async def _send_parallel(ctx, primary: dict, pair: dict):
    """Two-field embed: English on top, original language below."""
    color = LANG_COLOR.get(primary.get("lang", "en"), discord.Color.dark_gold())

    def lang_label(r):
        return LANG_LABEL.get(r.get("lang",""), "")

    embed = discord.Embed(
        title=f"📜 {primary['reference']} — Parallel",
        color=color
    )

    # Primary text
    pt = primary["text"]
    if len(pt) > 1020: pt = pt[:1017] + "…"
    embed.add_field(
        name=f"{lang_label(primary)} — {primary.get('source','')[:60]}",
        value=pt, inline=False
    )

    # Pair text
    if pair.get("found"):
        xt = pair["text"]
        if len(xt) > 1020: xt = xt[:1017] + "…"
        embed.add_field(
            name=f"{lang_label(pair)} — {pair.get('source','')[:60]}",
            value=xt, inline=False
        )
    else:
        err = pair.get("error", "Not available")
        # Only show the field if it's a real error, not just missing build file
        if "build_" not in err and "not found" not in err.lower():
            embed.add_field(
                name=f"{lang_label(pair) or 'Original'} (unavailable)",
                value=f"*{err}*",
                inline=False
            )
        elif "build_" in err or "not found" in err.lower():
            embed.add_field(
                name=f"{lang_label(pair) or 'Original language'} — *pending*",
                value=f"*Run the appropriate build script to enable this.*",
                inline=False
            )

    await ctx.send(embed=embed)


# ── Startup ────────────────────────────────────────────────────────────────────

@bot.event
async def on_ready():
    log.info(f"Logged in as {bot.user} (ID: {bot.user.id})")
    log.info(f"Connected to {len(bot.guilds)} guild(s)")
    synced = await bot.tree.sync()
    log.info(f"Synced {len(synced)} slash command(s)")
    log.info(f"Corpora loaded: {', '.join(lookup.corpora_names())}")

    # One-time migration: seed per-guild config from the old hardcoded channel.
    if not GUILD_CONFIG_PATH.exists() and _LEGACY_VOTD_CHANNEL_ID:
        legacy_channel = bot.get_channel(_LEGACY_VOTD_CHANNEL_ID)
        if legacy_channel and getattr(legacy_channel, "guild", None):
            _update_guild_config(
                legacy_channel.guild.id,
                votd_channel_id=_LEGACY_VOTD_CHANNEL_ID,
                votd_time=_LEGACY_VOTD_TIME,
                votd_mode=_load_votd_mode(),
            )
            log.info(f"Migrated legacy VOTD config to guild '{legacy_channel.guild.name}' ({legacy_channel.guild.id})")

    active_votd = sum(1 for g in _load_guild_config().values() if g.get("votd_channel_id"))
    log.info(f"Daily VOTD configured for {active_votd} guild(s) — admins can run !votdsetup")
    _daily_votd_task.start()

    import pathlib, hashlib
    for ext in ("png", "jpg", "jpeg", "gif", "webp"):
        avatar_path = pathlib.Path(__file__).parent / f"avatar.{ext}"
        if avatar_path.exists():
            avatar_bytes = avatar_path.read_bytes()
            avatar_hash = hashlib.md5(avatar_bytes).hexdigest()
            hash_cache = pathlib.Path(__file__).parent / ".avatar_hash"
            last_hash = hash_cache.read_text().strip() if hash_cache.exists() else ""
            if avatar_hash != last_hash:
                try:
                    await bot.user.edit(avatar=avatar_bytes)
                    hash_cache.write_text(avatar_hash)
                    print(f"Avatar updated from {avatar_path.name}")
                except Exception as e:
                    print(f"Could not update avatar: {e}")
            else:
                print("Avatar unchanged, skipping upload")
            break


if __name__ == "__main__":
    token = os.environ.get("DISCORD_TOKEN")
    if not token:
        raise RuntimeError("Set the DISCORD_TOKEN environment variable.")
    bot.run(token)
