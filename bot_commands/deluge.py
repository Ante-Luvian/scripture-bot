"""
Deluge points: a secret ledger (deliberately left out of !help, INTRODUCTION.md and the
changelog -- the joke is that it has always been there). When someone with mod powers
says "+5 deluge points @someone" (or "50 deluge points from @someone", or replies to a
message with "a deluge point"), the bot quietly writes it down. Nobody else's sayings
count. Mods can summon a random portion of the ledger with !delugepoints, or one
person's tally with !delugepoints @someone; for anyone else the command does nothing.

On its first start in each server the owner is in, it reads back through the server's
history and counts every award already made there.
"""
import asyncio
import datetime
import json
import random
import re
import time
import types

import discord

from core import ROOT, _atomic_write_json, bot, log
from bot_commands.measures import NUMBER_WORDS, words_to_number

DELUGE_PATH = ROOT / "data" / "deluge.json"
# {guild id: {"points": {user id: n}, "counted": [message ids], "backfilled": bool, "log": [...]}}
COLOR = discord.Color.from_rgb(40, 90, 160)

PHRASE = re.compile(r"\bdeluge[\s_-]*(?:points?|pts?)\b", re.I)
_WORD = "|".join(sorted(NUMBER_WORDS | {"a", "an", "and"}, key=len, reverse=True))
BEFORE = re.compile(rf"(?:(?P<sign>[+\-−–])\s*)?(?:(?P<digits>\d[\d,]*)(?P<scale>\s*[km]\b|\s+million\b)?"
                    rf"|(?P<words>(?:\b(?:{_WORD})\b[\s-]*)+))\s*(?:more\s+|extra\s+|whole\s+)?$", re.I)
AFTER = re.compile(r"^\s*[:=]?\s*(?P<sign>[+\-−–])\s*(?P<digits>\d[\d,]*)", re.I)
TAKING = re.compile(r"\b(?:minus|lose[sd]?|losing|lost|take[ns]?|taking|took|remove[sd]?|removing|deduct\w*|dock\w*|"
                    r"subtract\w*|negative|revoke[sd]?|revoking|strip\w*|fined?|that'?ll be)\b", re.I)
OFFER = re.compile(r"\b(?:if|would|i'?ll|i will|will (?:pay|give)|could|offer\w*|bount\w*|any(?:one|body)|whoever|"
                   r"every(?:one|body)|costs?|owe[sd]?|salary|until|how many|once you|per)\b", re.I)
LOOKBACK = datetime.timedelta(minutes=15)           # "15 deluge points", said just after someone's message


def amount(text: str) -> "int | None":
    """How many deluge points a message gives (negative: takes away); None if it names no amount."""
    m = PHRASE.search(text)
    if not m:
        return None
    sign = ""
    before = BEFORE.search(text[:m.start()])
    after = AFTER.search(text[m.end():])
    if before and before.group("digits"):
        n = int(before.group("digits").replace(",", ""))
        scale = (before.group("scale") or "").strip().lower()
        n *= {"k": 1000, "m": 1_000_000, "million": 1_000_000}.get(scale, 1)
        sign = before.group("sign") or ""
    elif before and before.group("words"):
        words = [w for w in re.split(r"[\s-]+", before.group("words").lower()) if w]
        while words and words[0] == "and":
            words.pop(0)
        n = words_to_number(words)
        if n is None:
            return None
        sign = before.group("sign") or ""
    elif after:
        n, sign = int(after.group("digits").replace(",", "")), after.group("sign")
    else:
        return None
    if OFFER.search(text):                              # promises, bounties and what-ifs aren't payments
        return None
    if sign:
        return n if sign == "+" else -n
    taking = TAKING.search(text) or re.match(r"\s*from\b", text[m.end():], re.I)   # "50 points from Gryffindor"
    return -n if taking else n


def recipients(message: discord.Message) -> list:
    """Who a message's points go to: the people it mentions, or else the author of the message it replies to."""
    people = [u for u in message.mentions if not u.bot]
    if people:
        return list({u.id: u for u in people}.values())
    replied = getattr(message.reference, "resolved", None) if message.reference else None
    if getattr(replied, "author", None) and not replied.author.bot:      # (not a deleted message)
        return [replied.author]
    return []


async def previous_author(message, channel) -> list:
    """For a bare "15 deluge points": the last person (not the speaker) to post in the channel just before."""
    if channel is None or re.search(r"\bpoints?\s+to\s+\w", message.content or "", re.I):   # "to cold brah": by name
        return []
    try:
        async for earlier in channel.history(limit=5, before=discord.Object(id=message.id)):
            if earlier.author.bot or earlier.author.id == message.author.id:
                continue
            return [earlier.author] if message.created_at - earlier.created_at <= LOOKBACK else []
    except discord.HTTPException:
        pass
    return []


def is_mod(member) -> bool:
    if getattr(member, "id", None) is not None and member.id == bot.owner_id:
        return True
    perms = getattr(member, "guild_permissions", None)
    return bool(perms and (perms.administrator or perms.manage_guild or perms.manage_messages))


# ── the ledger ────────────────────────────────────────────────────────────────

def _load() -> dict:
    try:
        return json.loads(DELUGE_PATH.read_text(encoding="utf-8")) if DELUGE_PATH.exists() else {}
    except ValueError:
        return {}


def _ledger(data: dict, guild_id: int) -> dict:
    return data.setdefault(str(guild_id), {"points": {}, "counted": [], "backfilled": False, "log": []})


def record(data: dict, message: discord.Message, mod: bool, earlier: list = ()) -> dict:
    """Counts a message into the ledger (once); returns {user id: points} given, empty if none.
    `earlier`: who posted just before, for a message that neither mentions nor replies to anyone."""
    ledger = _ledger(data, message.guild.id)
    if str(message.id) in ledger["counted"]:
        return {}
    n = amount(message.content or "")
    people = (recipients(message) or list(earlier)) if n is not None else []
    given = {str(u.id): n for u in people} if (mod and n) else {}
    for uid, pts in given.items():
        ledger["points"][uid] = ledger["points"].get(uid, 0) + pts
    if PHRASE.search(message.content or ""):
        ledger["counted"].append(str(message.id))
        ledger["log"].append({"id": str(message.id), "at": message.created_at.isoformat(timespec="seconds"),
                              "author": str(message.author), "mod": mod, "text": (message.content or "")[:300],
                              "given": given, "to": [str(u) for u in people] if given else []})
    return given


@bot.listen("on_message")
async def deluge_listener(message: discord.Message):
    if message.author.bot or not message.guild or (message.content or "").startswith("!"):
        return
    if not PHRASE.search(message.content or ""):
        return
    mod = is_mod(message.author)
    earlier = []
    if mod and amount(message.content or "") and not recipients(message):
        earlier = await previous_author(message, message.channel)
    data = _load()
    given = record(data, message, mod, earlier)
    _atomic_write_json(DELUGE_PATH, data)
    if given:
        log.info(f"Deluge points in {message.guild.name}: {given}")


# ── reading back through history, once ───────────────────────────────────────

async def _channels(guild: discord.Guild):
    me = guild.me
    for channel in list(guild.text_channels) + list(guild.forums) + list(guild.voice_channels):
        perms = channel.permissions_for(me)
        if not (perms.view_channel and perms.read_message_history):
            continue
        if not isinstance(channel, discord.ForumChannel):
            yield channel
        if isinstance(channel, (discord.TextChannel, discord.ForumChannel)):
            for thread in channel.threads:
                yield thread
            for private in (False, True):
                try:
                    async for thread in channel.archived_threads(limit=None, private=private):
                        yield thread
                except (discord.Forbidden, discord.HTTPException, AttributeError, TypeError):
                    pass


SEARCH_WORDS = ("deluge", "delugepoints", "delugepoint")


class _User(types.SimpleNamespace):
    def __str__(self):
        return self.name


def _searched(data: dict, guild) -> types.SimpleNamespace:
    """A search result (raw message JSON) as just enough of a Message for record()."""
    def user(u):
        return _User(id=int(u["id"]), bot=bool(u.get("bot")), name=u.get("username", ""))
    replied = data.get("referenced_message")
    return types.SimpleNamespace(
        id=int(data["id"]), content=data.get("content") or "", guild=guild, author=user(data["author"]),
        mentions=[user(u) for u in data.get("mentions", [])],
        reference=types.SimpleNamespace(resolved=types.SimpleNamespace(author=user(replied["author"])))
        if replied else None,
        created_at=datetime.datetime.fromisoformat(data["timestamp"]), channel_id=int(data["channel_id"]))


async def search(guild: discord.Guild, before) -> list:
    """Every message in the server's history that says the word, via Discord's own search (oldest first)."""
    found = {}
    for word in SEARCH_WORDS:
        offset = 0
        while offset <= 9975:
            route = discord.http.Route("GET", "/guilds/{guild_id}/messages/search", guild_id=guild.id)
            params = {"content": word, "limit": 25, "offset": offset, "max_id": discord.utils.time_snowflake(before),
                      "sort_by": "timestamp", "sort_order": "asc", "include_nsfw": "true"}
            page = await bot.http.request(route, params=params)
            if page.get("code") == 110000:                      # Discord is still indexing the server
                await asyncio.sleep(page.get("retry_after", 2) + 1)
                continue
            batch = [m for group in page.get("messages", []) for m in (group if isinstance(group, list) else [group])]
            for m in batch:
                found[m["id"]] = m
            if len(batch) < 25:
                break
            offset += 25
            await asyncio.sleep(0.5)
    return sorted(found.values(), key=lambda m: int(m["id"]))


async def backfill(guild: discord.Guild, before) -> int:
    mods: dict = {}

    async def mod(user) -> bool:
        if user.id not in mods:
            member = user if isinstance(user, discord.Member) else None
            if member is None:
                try:
                    member = await guild.fetch_member(user.id)
                except discord.HTTPException:
                    member = None                       # left the server: their sayings don't count
            mods[user.id] = is_mod(member) if member else user.id == bot.owner_id
        return mods[user.id]

    async def count(data: dict, message, channel) -> bool:
        is_a_mod = await mod(message.author)
        earlier = []
        if is_a_mod and amount(message.content) and not recipients(message):
            earlier = await previous_author(message, channel)
        return bool(record(data, message, is_a_mod, earlier))

    async def channel_of(cid: int):
        try:
            return guild.get_channel_or_thread(cid) or await bot.fetch_channel(cid)
        except discord.HTTPException:
            return None

    found, seen = 0, set()
    try:
        results = await search(guild, before)
    except discord.HTTPException as e:
        log.info(f"Deluge history: search refused ({e}); reading every channel instead")
        results = None
    if results is not None:
        data = _load()
        for raw in results:
            message = _searched(raw, guild)
            if message.author.bot or message.content.startswith("!") or not PHRASE.search(message.content):
                continue
            if await count(data, message, await channel_of(message.channel_id)):
                found += 1
        _ledger(data, guild.id)["backfilled"] = True
        _atomic_write_json(DELUGE_PATH, data)
        return found
    async for channel in _channels(guild):
        if channel.id in seen:
            continue
        seen.add(channel.id)
        try:
            async for message in channel.history(limit=None, before=before, oldest_first=True):
                if message.author.bot or (message.content or "").startswith("!") or not PHRASE.search(message.content or ""):
                    continue
                data = _load()
                if await count(data, message, channel):
                    found += 1
                _atomic_write_json(DELUGE_PATH, data)
        except (discord.Forbidden, discord.HTTPException) as e:
            log.info(f"Deluge history: skipped #{channel} ({e})")
    data = _load()
    _ledger(data, guild.id)["backfilled"] = True
    _atomic_write_json(DELUGE_PATH, data)
    return found


_backfill_started = False


@bot.listen("on_ready")
async def deluge_backfill():
    global _backfill_started
    if _backfill_started:
        return
    _backfill_started = True
    started = discord.utils.utcnow()
    if bot.owner_id is None:
        app = await bot.application_info()
        bot.owner_id = app.owner.id
    for guild in bot.guilds:
        if _load().get(str(guild.id), {}).get("backfilled"):
            continue
        try:
            await guild.fetch_member(bot.owner_id)      # only servers the owner is in
        except discord.HTTPException:
            continue
        t = time.monotonic()
        try:
            n = await backfill(guild, started)
            log.info(f"Deluge history read in {guild.name}: {n} award(s) in {time.monotonic() - t:.0f}s")
        except Exception as e:
            log.warning(f"Deluge history in {guild.name} failed: {e!r}")
        await asyncio.sleep(1)


# ── !delugepoints (mods only; silence for everyone else) ─────────────────────

def _fmt(n: int) -> str:
    return f"{n:+,}" if n else "0"


def ledger_embed(points: dict, rng: random.Random = random, whole: bool = False) -> discord.Embed:
    people = list(points.items())
    share = people if whole else rng.sample(
        people, k=min(len(people), max(1, rng.randint(len(people) // 3, len(people) // 2 + 1))))
    share.sort(key=lambda p: -p[1])
    lines = [f"<@{uid}> — **{_fmt(n)}**" for uid, n in share]
    while len("\n".join(lines)) > 4000:                 # (an embed's limit; dozens of people before it matters)
        lines.pop(-2 if len(lines) > 1 else -1)
    embed = discord.Embed(title="📜 The Ledger of the Delugery", color=COLOR, description="\n".join(lines))
    embed.set_footer(text="The whole ledger." if whole else
                          "An excerpt. The full ledger is kept by the Treasurer of the Delugery.")
    return embed


@bot.command(name="delugepoints", aliases=["delugepoint"], hidden=True)
async def cmd_delugepoints(ctx, *, who: str = ""):
    if not ctx.guild or not is_mod(ctx.author):
        return
    points = _load().get(str(ctx.guild.id), {}).get("points", {})
    member = next((u for u in ctx.message.mentions if not u.bot), None)
    if member is not None:
        await ctx.send(embed=discord.Embed(color=COLOR, description=f"{member.mention}: **{_fmt(points.get(str(member.id), 0))}** "
                                                                     f"deluge points"))
        return
    if not points:
        await ctx.send(embed=discord.Embed(color=COLOR, description="The ledger is empty. For now."))
        return
    owner = ctx.author.id in (bot.owner_id, ctx.guild.owner_id)       # the Treasurer: the whole ledger is theirs alone
    await ctx.send(embed=ledger_embed(points, whole=owner and who.strip().lower() in ("all", "full", "whole", "everyone")))


def board_embed(points: dict) -> discord.Embed:
    """The top three, and whoever is in last place."""
    ranked = sorted(points.items(), key=lambda p: -p[1])
    medals = ["🥇", "🥈", "🥉"]
    lines = [f"{medals[i]} <@{uid}> — **{_fmt(n)}**" for i, (uid, n) in enumerate(ranked[:3])]
    if len(ranked) > 3:
        uid, n = ranked[-1]
        lines += ["⋮", f"🌊 <@{uid}> — **{_fmt(n)}** (last place)"]
    return discord.Embed(title="🏆 Deluge Points: the Leaderboard", color=COLOR, description="\n".join(lines))


@bot.command(name="delugeboard", aliases=["delugeleaderboard", "delugetop"], hidden=True)
async def cmd_delugeboard(ctx):
    if not ctx.guild or not is_mod(ctx.author):
        return
    points = _load().get(str(ctx.guild.id), {}).get("points", {})
    await ctx.send(embed=board_embed(points) if points else
                   discord.Embed(color=COLOR, description="The ledger is empty. For now."))
