"""
!changelog, !changelogsetup, and announcing new CHANGELOG.md entries in each
server's changelog channel when the bot starts after an update.

Per-guild state lives in guild_config.json: "changelog_channel_id", and
"changelog_seen" -- the headings of entries already posted there.
"""
import re

import discord
from discord.ext import commands

from core import ROOT, _load_guild_config, _update_guild_config, bot, log

CHANGELOG_PATH = ROOT / "CHANGELOG.md"
MAX_PER_STARTUP = 3   # if a server missed many updates, post only the newest few


def parse_changelog(text: str) -> list[dict]:
    """Entries newest first: {"id": heading, "date": "YYYY-MM-DD" | "", "title", "items": [str]}.
    Bullets may wrap onto indented continuation lines."""
    entries = []
    for block in re.split(r"^## ", text, flags=re.M)[1:]:
        heading, _, body = block.partition("\n")
        heading = heading.strip()
        m = re.match(r"(\d{4}-\d{2}-\d{2})\s*[·—-]\s*(.+)", heading)
        date, title = (m.group(1), m.group(2).strip()) if m else ("", heading)
        items = []
        for line in body.splitlines():
            if line.startswith("- "):
                items.append(line[2:].strip())
            elif items and line.startswith((" ", "\t")) and line.strip():
                items[-1] += " " + line.strip()
        entries.append({"id": heading, "date": date, "title": title, "items": items})
    return entries


def load_changelog() -> list[dict]:
    try:
        return parse_changelog(CHANGELOG_PATH.read_text(encoding="utf-8"))
    except OSError:
        return []


def entry_embed(entry: dict) -> discord.Embed:
    embed = discord.Embed(
        title=f"📜 What's new — {entry['title']}",
        description="\n".join(f"• {item}" for item in entry["items"])[:4000] or "*(no details)*",
        color=discord.Color.dark_gold(),
    )
    embed.set_footer(text=(f"{entry['date']} · " if entry["date"] else "") + "!changelog for recent updates")
    return embed


def pending_entries(entries: list[dict], seen: list[str]) -> list[dict]:
    """Entries not yet posted, oldest first, capped to the newest MAX_PER_STARTUP."""
    unseen = [e for e in reversed(entries) if e["id"] not in seen]
    return unseen[-MAX_PER_STARTUP:]


async def announce_changelog(client) -> int:
    """Post unseen entries to every server's changelog channel. Returns how
    many messages were sent. Called once per startup from on_ready."""
    entries = load_changelog()
    if not entries:
        return 0
    all_ids = [e["id"] for e in entries]
    sent = 0
    for guild_id, g in _load_guild_config().items():
        channel_id = g.get("changelog_channel_id")
        if not channel_id:
            continue
        seen = g.get("changelog_seen", [])
        pending = pending_entries(entries, seen)
        if not pending:
            continue
        channel = client.get_channel(channel_id)
        if channel is None:
            log.warning(f"Changelog channel {channel_id} for guild {guild_id} not found; skipping")
            continue
        try:
            for entry in pending:
                await channel.send(embed=entry_embed(entry))
                sent += 1
        except discord.HTTPException as e:   # includes Forbidden: no permission to post there
            log.warning(f"Couldn't post changelog in guild {guild_id}: {e}")
            continue   # not marked seen -- retried next startup
        # Everything is now "seen", including older entries skipped by the cap
        _update_guild_config(int(guild_id), changelog_seen=sorted(set(seen) | set(all_ids)))
    if sent:
        log.info(f"Changelog: posted {sent} update message(s)")
    return sent


@bot.command(name="changelog", aliases=["whatsnew"])
async def cmd_changelog(ctx):
    """Recent bot updates. Usage: !changelog"""
    entries = load_changelog()
    if not entries:
        await ctx.send("No changelog yet.")
        return
    embed = discord.Embed(title="📜 Recent updates", color=discord.Color.dark_gold())
    for entry in entries[:4]:
        value = "\n".join(f"• {item}" for item in entry["items"]) or "*(no details)*"
        if len(value) > 1024:
            value = value[:1021] + "…"
        embed.add_field(name=f"{entry['title']} ({entry['date']})" if entry["date"] else entry["title"],
                        value=value, inline=False)
    await ctx.send(embed=embed)


@bot.tree.command(name="changelog", description="Recent bot updates")
async def changelog_slash(interaction: discord.Interaction):
    await interaction.response.defer()
    ctx = await bot.get_context(interaction)
    await cmd_changelog(ctx)


@bot.command(name="changelogsetup", aliases=["changelogconfig"])
@commands.has_permissions(administrator=True)
async def cmd_changelogsetup(ctx, *, arg: str = ""):
    """Choose where this server gets the bot's update announcements.
    Usage: !changelogsetup            — show the current channel
           !changelogsetup #channel   — post updates there
           !changelogsetup off        — stop posting updates"""
    if not ctx.guild:
        await ctx.send("This command only works in a server.")
        return
    g = _load_guild_config().get(str(ctx.guild.id), {})
    arg = arg.strip().lower()

    if arg == "off":
        _update_guild_config(ctx.guild.id, changelog_channel_id=None)
        await ctx.send("Update announcements are off for this server.")
        return

    channel = ctx.message.channel_mentions[0] if ctx.message.channel_mentions else None
    if channel is None:
        current = g.get("changelog_channel_id")
        await ctx.send(f"Update announcements: {f'<#{current}>' if current else '*off*'}.\n"
                       "Set with `!changelogsetup #channel`, or `!changelogsetup off`.")
        return

    # Don't flood a newly configured channel with the whole history: count
    # everything as seen, and post just the latest entry as a confirmation --
    # unless this server has already seen it (e.g. the channel is being
    # moved), so nothing is ever posted twice.
    entries = load_changelog()
    seen = g.get("changelog_seen", [])
    _update_guild_config(ctx.guild.id, changelog_channel_id=channel.id,
                         changelog_seen=sorted(set(seen) | {e["id"] for e in entries}))
    try:
        if entries and entries[0]["id"] not in seen:
            await channel.send("I'll post my updates here. Here's the latest:", embed=entry_embed(entries[0]))
    except discord.HTTPException:
        await ctx.send(f"⚠️ I can't post in {channel.mention} — check my permissions there "
                       "(View Channel, Send Messages, Embed Links).")
        return
    await ctx.send(f"Update announcements will be posted in {channel.mention}.")
