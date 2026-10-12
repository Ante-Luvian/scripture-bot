"""
!stats, !guildactivity, !scanstats.
"""
import discord
import re
from discord.ext import commands
from summa_lookup import parse_summa_ref
from core import (
    _infer_category,
    _load_guild_activity,
    _load_stats,
    _save_stats,
    book_from_reference,
    bot,
    lookup,
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
                        book = result.get("book") or book_from_reference(result.get("reference", ""))
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
                        book = result.get("book") or book_from_reference(result.get("reference", ""))
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
