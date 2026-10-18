"""
Shared state and helpers used across the bot: the Bot instance, the
ScriptureLookup engine, logging, per-guild/per-user persistence, stats,
and the common result/embed senders.
"""
import collections
import discord
import json
import logging
import re
import time
import traceback
from scripture_lookup import BIBLE_NT, BIBLE_OT, ScriptureLookup
from pathlib import Path
from discord.ext import commands
from hadith_lookup import get_hadith_section
from translation_lookup import search_translation

# Project root (data/, fonts/, ...) for modules living in bot_commands/.
ROOT = Path(__file__).parent

# Load .env file if present
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # dotenv not installed, fall back to environment variable

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

# "I can't find that" replies, which get a server's own :sowwy: emoji where it has one (the
# owner's server has her avatar making an apologetic face); elsewhere they're unchanged
APOLOGY = re.compile(r"^(?:I don't (?:know|have|recognise)|I couldn't|I can't|I have no|I found no|"
                     r"No (?:\S+ ){0,3}(?:found|for)\b|No results|Couldn't|Could not|Unknown (?:book|option|"
                     r"subcommand|mode|feature)|There's no|There is no|Sorry|Something went wrong|"
                     r"(?:Paragraph|Canon) \S+ not found|That verse has no)", re.I)
SORRY_EMOJI = "sowwy"


def apologetic(guild, content):
    """`content` with the guild's :sowwy: emoji in front (in place of a ⚠️) when it's an
    apology and the guild has that emoji; otherwise unchanged."""
    if not isinstance(content, str) or guild is None:
        return content
    body = content[2:].lstrip() if content.startswith("⚠️") else content
    if not APOLOGY.match(body):
        return content
    emoji = discord.utils.get(getattr(guild, "emojis", ()), name=SORRY_EMOJI)
    return f"{emoji} {body}" if emoji else content


# Characters no query needs, which only break the replies that quote it back: a backtick or a
# backslash in "**{query}**" or "`{query}`" unbalances the formatting around it (found by
# stress.py), and invisible or right-to-left controls make a reference look like another one.
_UNWANTED_INPUT = re.compile("[`\\\\​-‏‪-‮⁠-⁩﻿]")
MAX_INPUT = 500                      # longer than any reference list, search or question needs


def clean_input(text: str) -> str:
    """What someone typed, without the characters above, and cut at MAX_INPUT after the command."""
    text = _UNWANTED_INPUT.sub("", text)
    return text[:MAX_INPUT + 40]


def fit_for_discord(content, kwargs: dict):
    """A last safety net: trim anything over Discord's limits (2,000 to a message; an embed's
    256-character title, 4,096 description, 1,024 field) rather than have Discord refuse the
    whole reply. Commands should keep within them themselves; this only catches what slips by."""
    def clip(s, n):
        return s if s is None or len(s) <= n else s[:n - 1] + "…"
    if isinstance(content, str):
        content = clip(content, 2000)
    for embed in list(kwargs.get("embeds") or []) + ([kwargs["embed"]] if kwargs.get("embed") else []):
        embed.title = clip(embed.title, 256)
        embed.description = clip(embed.description, 4096)
        for i, field in enumerate(embed.fields):
            if len(field.value or "") > 1024 or len(field.name or "") > 256:
                embed.set_field_at(i, name=clip(field.name, 256), value=clip(field.value, 1024), inline=field.inline)
    return content


class ScriptureContext(commands.Context):
    async def send(self, content=None, **kwargs):
        content = fit_for_discord(content, kwargs)
        return await super().send(apologetic(self.guild, content), **kwargs)


class ScriptureTree(discord.app_commands.CommandTree):
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """Slash commands' text options get the same cleaning as typed commands (this runs before
        discord.py reads the options out of the interaction)."""
        def clean(options):
            for opt in options or []:
                if isinstance(opt.get("value"), str):
                    opt["value"] = clean_input(opt["value"])[:MAX_INPUT]
                clean(opt.get("options"))
        clean((interaction.data or {}).get("options"))
        return True


class ScriptureBot(commands.Bot):
    async def get_context(self, origin, *, cls=ScriptureContext):
        if isinstance(origin, discord.Message) and origin.content.startswith("!"):
            origin.content = clean_input(origin.content)
        return await super().get_context(origin, cls=cls)


# Never ping @everyone, @here or a role, whatever a reply happens to quote back.
bot = ScriptureBot(command_prefix="!", intents=intents, help_command=None, tree_cls=ScriptureTree,
                   allowed_mentions=discord.AllowedMentions(everyone=False, roles=False, users=True, replied_user=True))
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
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("🔒 Only server admins can use that command.")
        return
    if isinstance(error, commands.CheckFailure):
        await ctx.send("🔒 That command can't be used here.")
        return
    if isinstance(error, commands.UserInputError):
        name = ctx.command.name if ctx.command else ctx.invoked_with
        await ctx.send(f"⚠️ {error} — see `!help {name}`.")
        return
    # A real bug: tell the user, log it, and let the owner know
    name = ctx.command.qualified_name if ctx.command else ctx.invoked_with
    await report_error(f"!{name}", getattr(error, "original", error))
    try:
        await ctx.send(USER_ERROR_MESSAGE)
    except Exception:
        pass


# ── Unexpected errors: tell the user, log, DM the owner ───────────────────────
# Before this, a failing command or button just went quiet -- e.g. all four
# study buttons greyed out and did nothing, and only the log knew.

USER_ERROR_MESSAGE = "⚠️ Sorry — something went wrong with that. My owner has been told about it."
ERROR_LOG_PATH = Path(__file__).parent / "data" / "error_log.json"   # recent errors, for the weekly report
_ERROR_LOG_KEEP = 500


def _append_error_log(where: str, error: BaseException) -> None:
    import datetime
    try:
        entries = json.loads(ERROR_LOG_PATH.read_text(encoding="utf-8")) if ERROR_LOG_PATH.exists() else []
    except Exception:
        entries = []
    entries.append({"at": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
                    "where": where, "error": type(error).__name__,
                    "detail": str(error)[:200], "location": _error_location(error)})
    try:
        _atomic_write_json(ERROR_LOG_PATH, entries[-_ERROR_LOG_KEEP:])
    except Exception as e:
        log.warning(f"Couldn't write the error log: {e}")
_ERROR_DM_INTERVAL = 6 * 60 * 60   # the same error DMs the owner at most once per 6 hours
_last_error_dm: dict[str, float] = {}


def _error_location(error: BaseException) -> str:
    frames = traceback.extract_tb(error.__traceback__)
    return f"{Path(frames[-1].filename).name}:{frames[-1].lineno}" if frames else "?"


async def report_error(where: str, error: BaseException) -> None:
    """Log an unexpected error with its traceback and DM the bot's owner a
    one-line summary -- at most once per 6 hours for the same error (same
    place, type, and line), so a recurring bug can't flood the DMs."""
    log.error(f"Unhandled error in {where}: {type(error).__name__}: {error}\n"
              + "".join(traceback.format_exception(type(error), error, error.__traceback__)))
    _append_error_log(where, error)
    location = _error_location(error)
    signature = f"{where}|{type(error).__name__}|{location}"
    now = time.monotonic()
    if signature in _last_error_dm and now - _last_error_dm[signature] < _ERROR_DM_INTERVAL:
        return
    _last_error_dm[signature] = now
    try:
        app = await bot.application_info()
        owner = app.team.owner if getattr(app, "team", None) else app.owner
        await owner.send(f"⚠️ **Error in {where}** — `{type(error).__name__}: {str(error)[:300]}` at `{location}`.\n"
                         "The full traceback is in the bot's log. (This same error won't DM you again for 6 hours.)")
    except Exception as e:
        log.warning(f"Couldn't DM the owner about an error: {e}")


async def _tell_interaction_user(interaction: discord.Interaction) -> None:
    """Show USER_ERROR_MESSAGE to whoever pressed the button / ran the slash command."""
    try:
        if interaction.response.is_done():
            await interaction.followup.send(USER_ERROR_MESSAGE, ephemeral=True)
        else:
            await interaction.response.send_message(USER_ERROR_MESSAGE, ephemeral=True)
    except Exception:
        pass


async def _view_on_error(self, interaction: discord.Interaction, error: Exception, item) -> None:
    label = getattr(item, "label", None) or getattr(getattr(item, "item", None), "label", None)
    await report_error(f"the “{label}” button" if label else f"a {type(item).__name__}", error)
    await _tell_interaction_user(interaction)


# Every button and menu in the bot (including the persistent dynamic-item
# buttons, which discord.py runs inside a View too) reports errors through
# View.on_error; nothing in the project overrides it, so set it once here.
discord.ui.View.on_error = _view_on_error


@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: Exception) -> None:
    from discord import app_commands
    if isinstance(error, app_commands.CheckFailure):
        msg = "🔒 You can't use that command here."
        try:
            await (interaction.followup.send(msg, ephemeral=True) if interaction.response.is_done()
                   else interaction.response.send_message(msg, ephemeral=True))
        except Exception:
            pass
        return
    name = interaction.command.name if interaction.command else "?"
    await report_error(f"/{name}", getattr(error, "original", error))
    await _tell_interaction_user(interaction)

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

def book_from_reference(ref: str) -> str:
    """The book part of a result's reference: "1 Corinthians 13:4" -> "1 Corinthians",
    "The Thunder, Perfect Mind 1:1" -> "The Thunder, Perfect Mind", "John 3:16 (ESV)"
    -> "John". (Taking the first word, as stats used to, counted "1", "Song", "The".)"""
    ref = re.sub(r"\s*\([^)]*\)\s*$", "", ref.strip())          # trailing "(ESV)", "(ch. 78)"
    while True:
        stripped = re.sub(r"[\s,]+[^\s,]*\d[^\s,]*$", "", ref)   # trailing "3:16", "2a", "9.1.3", "¶1"
        if stripped == ref or not stripped:
            return ref
        ref = stripped


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
            book = result.get("book") or book_from_reference(result.get("reference", ""))
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
        "Fragments of a Zadokite Work","2 Enoch","First Book of Adam and Eve","Second Book of Adam and Eve","Odes of Solomon",
        "The Protevangelium of James","The Gospel of Pseudo-Matthew","Gospel of Thomas: First Greek Form",
        "The Arabic Gospel of the Infancy of the Saviour","Acts of Pilate: First Greek Form",
        "Acts of Paul and Thecla","Revelation of Paul",
    },
    "✡️ Halakha/Kabbalah": {
        "Zohar","Berakhot","Shabbat","Sanhedrin","Avot","Bava Kamma",
    },
    "☪️ Islamic":          {
        "Quran","Sahih al-Bukhari","Sahih Muslim","Sunan Abu Dawud",
        "Jami at-Tirmidhi","Sunan an-Nasa'i","Sunan Ibn Majah",
        "Muwatta Malik","Forty Hadith of Nawawi","Divan of Hafiz",
    },
    "🏛️ Classical":        {
        "Enneads","Republic","Iliad","Odyssey","Theology of Plato",
        "On the Mysteries","On Abstinence","Against the Galilaeans",
        "On the Gods and the World","Nicomachean Ethics","Metaphysics",
        "Corpus Hermeticum","Chaldaean Oracles","Orphic Hymns","Meditations","Enchiridion of Epictetus",
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
        "Imitation of Christ","Rule of Benedict","Inferno","Purgatorio","Paradiso",
    },
    "🧿 Gnostic/Hermetic":  {
        "Ginza Rba","Book of John","Asclepius","Gospel of Thomas",
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
    "☸️ Dharmic":           {"Rig Veda","Yajur Veda","Sama Veda","Atharva Veda","Bhagavad Gita",
                             "Isa Upanishad","Katha Upanishad","Kena Upanishad",
                             "Chandogya Upanishad","Aitareya Aranyaka","Kaushitaki Upanishad","Mundaka Upanishad",
                             "Taittiriya Upanishad","Brihadaranyaka Upanishad","Svetasvatara Upanishad",
                             "Prasna Upanishad","Maitrayana Upanishad","Laws of Manu","Yoga Sutras"},
    "☸️ Buddhist":          {"Dhammapada","Diamond Sutra","Sutta Nipata","Lotus Sutra","Questions of King Milinda","Jataka"},
    "☯️ Chinese":           {"Tao Te Ching","Analects","I Ching","Zhuangzi","Mencius","Great Learning","Doctrine of the Mean"},
    "🌲 Norse":             {"Voluspo","Hovamol","Iliad"},
    "🔥 Zoroastrian":       {"Gathas","Vendidad","Yashts","Yasna","Bundahishn"},
    "🪯 Sikh":              {"Guru Granth Sahib","Japji"},
    "🤚 Jain":              {"Akaranga Sutra","Kalpa Sutra","Uttaradhyayana Sutra","Sutrakritanga"},
    "⛩️ Shinto":            {"Kojiki","Nihongi"},
    "🌽 Mesoamerican":      {"Popol Vuh"},
    "🦢 Finnish":           {"Kalevala"},
    "☘️ Celtic":            {"Mabinogion"},
    "🌹 Sufi":              {"Divan of Hafiz","Masnavi","Rubaiyat"},
    "🌍 Baháʼí":            {
        "Kitab-i-Aqdas", "The Hidden Words (Arabic)", "The Hidden Words (Persian)",
        "Gleanings from the Writings of Baha'u'llah", "Prayers and Meditations",
        "Some Answered Questions", "Kitab-i-Iqan", "Epistle to the Son of the Wolf",
    },
    "🏺 Dead Sea Scrolls":  {
        "Hodayot", "Damascus Document", "Community Rule", "War Scroll",
        "Pesher Habakkuk", "Rule of the Congregation", "Rule of Blessings",
        "Isaiah (1QIsaa)", "Exodus (4Q22)", "Deuteronomy (4Q41)",
        "Psalms (4Q86)", "Daniel (4Q114)",
    },
}

def _infer_category(book: str) -> str:
    for cat, books in _CATEGORY_BOOKS.items():
        if book in books:
            return cat
    return "Other"

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
    "Forty Hadith Qudsi":       "qudsi",
}

# ── Helpers ────────────────────────────────────────────────────────────────────

_VERSE_MARK = re.compile(r"\*\*\[[\d:]+\]\*\* ?")


def _without_lone_verse_number(result: dict) -> dict:
    """One verse doesn't need its number beside it ("**[16]** For God so loved"):
    the title already says John 3:16. Two or more keep theirs."""
    text = result.get("text")
    if isinstance(text, str) and len(_VERSE_MARK.findall(text)) == 1 and _VERSE_MARK.match(text.lstrip()):
        return {**result, "text": _VERSE_MARK.sub("", text.lstrip(), count=1)}
    return result


def _build_embed(result: dict) -> discord.Embed:
    """Build a single embed — used by auto-detection in on_message."""
    result = _without_lone_verse_number(result)
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


def fetch_chapter_result(lookup: "ScriptureLookup", get_hadith_section_fn, book_name: str, chap_label: str, mode: str) -> dict:
    """Fetch one chapter/section, in the same shape _send_result expects,
    for either a local/Sefaria "verse" reference or a hadith section.
    Dependency-injected -- see chapter_options_for_book() above."""
    if mode != "hadith":
        return lookup.get_verse(f"{book_name} {chap_label}")

    key = _HADITH_DISPLAY_TO_KEY.get(book_name)
    try:
        section_num = int(chap_label.replace("Book ", "").strip())
    except ValueError:
        section_num = None
    if not key or section_num is None:
        return {"found": False, "error": "Could not resolve this hadith section.", "suggestions": []}
    data = get_hadith_section_fn(key, section_num)
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
        result = fetch_chapter_result(lookup, get_hadith_section, book_name, target_label, mode)
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


def _extra_view_timeout(extra_buttons: list) -> "float | None":
    """Views carrying persistent (dynamic-item) buttons must never time out:
    when a view times out, discord.py unregisters the dynamic-item patterns it
    contains bot-wide, which would break those buttons on every message."""
    return None if any(isinstance(b, discord.ui.DynamicItem) for b in extra_buttons) else 180


async def _send_result(ctx_or_interaction, result: dict, extra_buttons: "list | None" = None):
    """Send a verse or whole-chapter result, splitting across multiple embeds if needed.
    extra_buttons, if given, are appended to whatever view the result ends up
    using (a bare view is created for them if the result wouldn't otherwise
    have one) -- used for the !books chapter picker's prev/next-chapter buttons."""
    extra_buttons = extra_buttons or []
    result = _without_lone_verse_number(result)
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
            view = discord.ui.View(timeout=_extra_view_timeout(extra_buttons))
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
                super().__init__(timeout=_extra_view_timeout(extra_buttons))
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
            view = discord.ui.View(timeout=_extra_view_timeout(extra_buttons))
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
            view = discord.ui.View(timeout=_extra_view_timeout(extra_buttons))
            for b in extra_buttons:
                view.add_item(b)
        if i == 0:
            msg = await (_reply(embed=embed, view=view) if view else _reply(embed=embed))
        else:
            channel = ctx_or_interaction.channel if is_interaction else ctx_or_interaction
            msg = await (channel.send(embed=embed, view=view) if view else channel.send(embed=embed))
        if is_last:
            await _maybe_react_savable(ctx_or_interaction, msg)


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
