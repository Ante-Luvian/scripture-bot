"""
Weekly report for the bot's owner, by DM every Monday morning (UTC): usage
this week, top commands and verses, errors, and the !notes source check.

stats.json only keeps running totals, so each report saves a snapshot of
them (data/weekly_report.json) and the next one reports the difference.
Errors come from data/error_log.json, written by core.report_error.
`!weeklyreport` (owner only, hidden) previews it without moving the snapshot.
"""
import asyncio
import datetime
import json
from collections import Counter

import discord
from discord.ext import commands, tasks

from core import ERROR_LOG_PATH, ROOT, _atomic_write_json, _load_stats, bot, log
from bot_commands.quiz import week_key, weekly_top
from net_notes_lookup import health_check

REPORT_STATE_PATH = ROOT / "data" / "weekly_report.json"
REPORT_WEEKDAY, REPORT_HOUR = 0, 9   # Monday, 09:00 UTC


def _load_json(path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default
    except Exception:
        return default


def _snapshot(stats: dict) -> dict:
    return {
        "total_commands": stats.get("total_commands", 0),
        "users": len(stats.get("unique_users", [])),
        "command_counts": dict(stats.get("command_counts", {})),
        "verse_counts": dict(stats.get("verse_counts", {})),
    }


def _delta(now: dict, before: dict) -> Counter:
    return Counter({k: v - before.get(k, 0) for k, v in now.items() if v - before.get(k, 0) > 0})


def _top(counter: Counter, n: int = 5) -> str:
    return "\n".join(f"{i}. {name} — {count}" for i, (name, count) in enumerate(counter.most_common(n), 1)) or "—"


def build_report(stats: dict, previous: "dict | None", errors: list, since: datetime.datetime,
                 guild_count: int, notes_check: tuple, quiz_top: "list | None" = None) -> discord.Embed:
    """quiz_top: [(server name, [(user id, right, answered), ...]), ...]"""
    now = _snapshot(stats)
    first = previous is None
    before = previous or {"total_commands": 0, "users": 0, "command_counts": {}, "verse_counts": {}}
    embed = discord.Embed(
        title="📊 Weekly report" + (" (first one: all-time totals)" if first else ""),
        color=discord.Color.dark_gold(),
    )
    embed.add_field(name="Usage", value=(
        f"**{now['total_commands'] - before['total_commands']:,}** commands · "
        f"**{now['users'] - before['users']:,}** new users · {guild_count} servers"), inline=False)
    embed.add_field(name="Top commands", value=_top(_delta(now["command_counts"], before["command_counts"])))
    embed.add_field(name="Top verses", value=_top(_delta(now["verse_counts"], before["verse_counts"])))

    recent = [e for e in errors if e.get("at", "") >= since.isoformat(timespec="seconds")]
    if recent:
        places = Counter(e["where"] for e in recent).most_common(5)
        error_text = f"**{len(recent)}** — " + ", ".join(f"{w} ×{n}" for w, n in places)
    else:
        error_text = "None 🎉"
    embed.add_field(name="Errors", value=error_text[:1024], inline=False)
    if quiz_top:
        lines = [f"**{name}:** " + ", ".join(f"<@{uid}> {right}/{answered}" for uid, right, answered in top)
                 for name, top in quiz_top]
        embed.add_field(name="Quiz champions last week", value="\n".join(lines)[:1024], inline=False)
    ok, detail = notes_check
    embed.add_field(name="!notes source (netbible.org)", value=("✅ " if ok else "⚠️ ") + detail, inline=False)
    embed.set_footer(text=f"Since {since:%Y-%m-%d %H:%M} UTC")
    return embed


def _quiz_champions(client, week: str) -> list:
    out = []
    for gid, top in weekly_top(week).items():
        guild = client.get_guild(int(gid)) if gid.isdigit() and hasattr(client, "get_guild") else None
        out.append((guild.name if guild else ("DMs" if gid == "dm" else f"server {gid}"), top))
    return out


async def make_report(client, now: datetime.datetime) -> tuple[discord.Embed, dict]:
    """(report embed, snapshot to save if it's sent as the weekly report)."""
    stats = _load_stats()
    state = _load_json(REPORT_STATE_PATH, {})
    previous = state.get("snapshot")
    since = (datetime.datetime.fromisoformat(state["sent_at"]) if state.get("sent_at")
             else now - datetime.timedelta(days=7))
    notes_check = await asyncio.to_thread(health_check)
    last_sunday = now.date() - datetime.timedelta(days=now.weekday() + 1)
    embed = build_report(stats, previous, _load_json(ERROR_LOG_PATH, []), since,
                         len(getattr(client, "guilds", [])), notes_check,
                         _quiz_champions(client, week_key(last_sunday)))
    return embed, {"sent_at": now.isoformat(timespec="seconds"), "snapshot": _snapshot(stats)}


async def send_weekly_report_if_due(client, now: datetime.datetime) -> bool:
    """Send the report on Monday from 09:00 UTC, once (remembered across restarts)."""
    state = _load_json(REPORT_STATE_PATH, {})
    if now.weekday() != REPORT_WEEKDAY or now.hour < REPORT_HOUR:
        return False
    if state.get("sent_at", "")[:10] == now.date().isoformat():
        return False
    embed, new_state = await make_report(client, now)
    try:
        app = await client.application_info()
        owner = app.team.owner if getattr(app, "team", None) else app.owner
        await owner.send(embed=embed)
    except Exception as e:
        log.warning(f"Couldn't send the weekly report: {e}")
        return False
    _atomic_write_json(REPORT_STATE_PATH, new_state)
    return True


@tasks.loop(minutes=30)
async def weekly_report_task():
    await send_weekly_report_if_due(bot, datetime.datetime.now(datetime.timezone.utc))


@weekly_report_task.before_loop
async def _before_weekly_report():
    await bot.wait_until_ready()


@bot.command(name="weeklyreport", hidden=True)
@commands.is_owner()
async def cmd_weeklyreport(ctx):
    """Owner only: preview the weekly report now (doesn't reset its week)."""
    embed, _ = await make_report(bot, datetime.datetime.now(datetime.timezone.utc))
    await ctx.send(embed=embed)
