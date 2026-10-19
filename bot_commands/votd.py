"""
Verse of the Day: !votd, the daily per-guild task, and !subscribe DM digests.
"""
import asyncio
import discord
import json
import random
import re
from translation_lookup import TRANSLATION_SUFFIXES, get_translation
from discord.ext import commands, tasks
from bot_commands.card import (
    _render_verse_card,
)
from bot_commands.church import (
    _fetch_catena_sections,
)
from core import (
    _VOTD_FALLBACKS,
    _atomic_write_json,
    _get_guild_votd,
    _load_guild_config,
    _record_last_cited,
    _scrape_votd,
    _update_guild_config,
    bot,
    log,
    lookup,
)
from bot_commands.liturgy import (
    _TODAY_GROUPS,
    _send_today,
    readings_view,
)
from bot_commands.translations import (
    _fetch_one_translation,
)
from core import ROOT

# ── !votd — Verse of the Day (reference from verseoftheday.com, text from KJV) -

async def _send_votd(ctx_or_channel, translation: str = ""):
    """
    Core VOTD logic. Scrapes verseoftheday.com, falls back to a random
    well-known verse if the site is unreachable. Supports optional translation.
    """
    reference, date_text = (await asyncio.to_thread(_scrape_votd))
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
        result = (await asyncio.to_thread(get_translation, ref_single, translation))
    else:
        result = (await asyncio.to_thread(lookup.get_verse, ref_single))
        if not result.get("found"):
            result = (await asyncio.to_thread(lookup.get_verse, reference))

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
    await ctx_or_channel.send(file=discord.File(buf, filename="votd.png"), view=_todays_readings())
    _record_last_cited(ctx_or_channel, result)


def _todays_readings() -> discord.ui.View:
    """The 📅 Today's readings button under every Verse of the Day."""
    import datetime
    return readings_view(datetime.datetime.now(datetime.timezone.utc).date())


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
    reference, date_text = (await asyncio.to_thread(_scrape_votd))
    used_fallback = False
    if reference is None:
        reference = random.choice(_VOTD_FALLBACKS)
        log.info(f"RNG  VOTD fallback          → {reference}")
        used_fallback = True

    # Strip verse range (e.g. "John 3:16-18" → "John 3:16") for single-verse work
    ref_single = re.sub(r"\s*[-–]\s*\d+$", "", reference)

    # ── 2. KJV verse text ─────────────────────────────────────────────────────
    kjv_result = (await asyncio.to_thread(lookup.get_verse, ref_single))
    if not kjv_result.get("found"):
        kjv_result = (await asyncio.to_thread(lookup.get_verse, reference))

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
    catena_data = await asyncio.to_thread(_fetch_catena_sections, ref_single, 1)   # just the first Father
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

    await ctx_or_channel.send(embed=embed, view=_todays_readings())


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


# ── !subscribe — personal daily Verse of the Day by DM ───────────────────────────
# Independent of the per-guild channel post (!votdsetup): this is the same daily
# verse, delivered straight to a user's DMs instead of (or as well as) a channel.
SUBSCRIBERS_PATH = ROOT / "data" / "subscribers.json"
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
