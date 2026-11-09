"""
!stats, !guildactivity. (!scanstats, the one-time count of old messages, was done long ago and
removed on 2026-11-08.)
"""
import discord
from discord.ext import commands
from core import (
    _infer_category,
    _load_guild_activity,
    _load_stats,
    bot,
)

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

    embed = discord.Embed(title="📊 Scripture Bot Statistics", color=discord.Color.dark_gold())
    embed.add_field(
        name="Overview",
        value=f"**{total_cmds:,}** commands issued\n**{total_users:,}** unique users",
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
        "sortesbiblicae": ("📖 Top Sortes Biblicae Draws", 5),
        "iching": ("☯️ Top I Ching Hexagrams", 5),
        "hafez": ("🌹 Top Hafez Poems", 5),
        "gathas": ("🔥 Top Gathas Verses", 5),
        "rumi": ("🌹 Top Masnavi Passages", 5),
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
