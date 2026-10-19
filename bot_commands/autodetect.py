"""
Auto-detection of scripture references in ordinary messages.
"""
import discord
import re
from scripture_lookup import ALIASES, DRB_SUFFIXES, KNOX_SUFFIXES, get_verse_drb, get_verse_knox
from translation_lookup import TRANSLATION_SUFFIXES, get_translation
from bot_commands.dore import art_buttons
from bot_commands.packs import welcome
from bot_commands.verse import (
    _study_buttons,
)
from core import (
    _AUTO_RE,
    _build_embed,
    _get_guild_features,
    _load_bookmarks,
    _save_bookmarks,
    bot,
    lookup,
    tradition_enabled,
)

# ── Auto-detection ─────────────────────────────────────────────────────────────

def _trim_to_book(raw: str) -> str:
    """_AUTO_RE's book group takes every word before the chapter, so in
    "as it says in John 3:16" it captures "as it says in John" -- which made
    auto-detection work only when a reference started the message. Return the
    longest trailing run of those words that is exactly a known book name or
    abbreviation ("John", "1 John", "Song of Solomon"); if none is, the text
    unchanged (the old behaviour, for references the lookup resolves itself)."""
    words = raw.split()
    for i in range(len(words)):
        candidate = " ".join(words[i:])
        # Mid-sentence, a short lowercase abbreviation is more likely an
        # ordinary word ("see ch 2:1", "pm", "ex", "mt") than a book.
        if i > 0 and len(candidate) <= 3 and candidate.islower():
            continue
        if candidate.lower() in ALIASES or candidate.lower() in lookup._book_index:
            return candidate
    return raw.strip()


@bot.event
async def on_guild_join(guild: discord.Guild):
    """Welcome a new server, and ask its admins what it's for (bot_commands/packs.py)."""
    await welcome(guild)


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

    for embed, view in find_verses(message.content, limit=3, guild_id=getattr(getattr(message, "guild", None), "id", None)):
        if view is not None:
            await message.channel.send(embed=embed, view=view)
        else:
            await message.channel.send(embed=embed)


def find_verses(content: str, limit: int = 3, guild_id=None) -> list:
    """[(embed, study-button view or None), ...] for the first `limit`
    references in `content` that resolve to real verses (in the traditions
    the server `guild_id` has)."""
    matches = _AUTO_RE.findall(content)

    # De-duplicate while preserving order
    seen = set()
    unique = []
    for m in matches:
        book, chap, verse, end_verse = m
        ref = f"{_trim_to_book(book)} {chap}:{verse}"
        if end_verse:
            ref += f"-{end_verse}"
        if ref.lower() not in seen:
            seen.add(ref.lower())
            unique.append(ref)

    # Only respond if at least one reference actually resolves to a real verse
    replies = []   # (embed, result)
    for ref in unique[:limit]:
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

        if result["found"] and tradition_enabled(guild_id, result.get("tradition")):
            replies.append((_build_embed(result), result))

    out = []
    for embed, result in replies:
        # Bible verses get the same Notes / Cross-refs / Interlinear / Card
        # buttons as !verse (persistent buttons: the view must never time out)
        buttons = _study_buttons(result) + art_buttons(result)   # 🖼️ Doré · 🎨 Blake, when the passage has one
        view = None
        if buttons:
            view = discord.ui.View(timeout=None)
            for b in buttons:
                view.add_item(b)
        out.append((embed, view))
    return out


# ── Right-click a message → Apps → "Look up verses" ─────────────────────────
# For messages auto-detection didn't answer: ones starting with "!", with
# more than 3 references, or from before I joined. The reply is private.

CONTEXT_MENU_LIMIT = 5


@bot.tree.context_menu(name="Look up verses")
async def look_up_verses(interaction: discord.Interaction, message: discord.Message):
    found = find_verses(message.content or "", limit=CONTEXT_MENU_LIMIT, guild_id=getattr(interaction, "guild_id", None))
    if not found:
        await interaction.response.send_message(
            "I couldn't find any scripture references in that message (like `John 3:16`).", ephemeral=True)
        return
    await interaction.response.defer(ephemeral=True, thinking=True)
    for embed, view in found:
        kwargs = {"view": view} if view is not None else {}
        await interaction.followup.send(embed=embed, ephemeral=True, **kwargs)
