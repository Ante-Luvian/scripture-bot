"""
Per-user and per-guild settings and data: !features, !save / !saved / !unsave,
!plan, !leaderboard, !prefer.
"""
import discord
import re
from translation_lookup import TRANSLATION_SUFFIXES
from discord import app_commands
from discord.ext import commands
from core import (
    GUILD_FEATURES,
    _get_guild_features,
    _load_bookmarks,
    _load_reading_plans,
    _load_user_prefs,
    _plan_current_chapter,
    _save_bookmarks,
    _save_reading_plans,
    _save_user_prefs,
    _send_result,
    _update_guild_config,
    bot,
    lookup,
)

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
