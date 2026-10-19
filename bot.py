"""
Scripture Bot for Discord -- entry point.

Shared state lives in core.py; each module in bot_commands/ registers its
commands on the shared `bot` when imported.
"""
import os
from core import (
    GUILD_CONFIG_PATH,
    _LEGACY_VOTD_CHANNEL_ID,
    _LEGACY_VOTD_TIME,
    _load_guild_config,
    _load_votd_mode,
    _update_guild_config,
    bot,
    log,
    lookup,
)
from bot_commands.votd import (
    _daily_votd_task,
)
from bot_commands.changelog import (
    announce_changelog,
    refresh_introductions,
)
from bot_commands.backup import (
    daily_backup_task,
)
from bot_commands.health import (
    weekly_notes_check,
)
from bot_commands.memorize import (
    memorize_review_task,
)
from bot_commands.oracles import (
    daily_oracle_task,
)
from bot_commands.personal import (
    plan_reminder_task,
)
from bot_commands.quiz import (
    daily_quiz_task,
)
from bot_commands.games import (
    daily_versle_task,
)
from bot_commands.hymnday import (
    daily_hymn_task,
)
from bot_commands.troparion import (
    daily_troparion_task,
)
from bot_commands.jewish_learning import (
    daily_learning_task,
)
from bot_commands.angelus import (
    angelus_task,
)
from bot_commands.saints import (
    daily_saint_task,
)
from bot_commands.report import (
    weekly_report_task,
)
# Importing a feature module registers its commands.
from bot_commands import (  # noqa: F401
    angelus,
    autodetect,
    blake,
    books,
    card,
    changelog,
    church,
    deluge,
    cloud,
    divine_liturgy,
    dore,
    vov,
    games,
    harmony,
    report,
    help,
    hymnday,
    hymns,
    icons,
    jewish_learning,
    journeys,
    kings,
    latin_psalms,
    liturgy,
    measures,
    memorize,
    oracles,
    packs,
    people,
    personal,
    psalter,
    quiz,
    rosary,
    salah,
    troparion,
    reference,
    saints,
    slash,
    stories,
    stats,
    tarot,
    translations,
    verse,
    votd,
)

# ── Startup ────────────────────────────────────────────────────────────────────

_startup_done = False

@bot.event
async def on_ready():
    # on_ready fires again after every full gateway reconnect, not just at
    # launch; re-running startup re-synced slash commands each time and
    # crashed on _daily_votd_task.start() ("Task is already launched").
    global _startup_done
    if _startup_done:
        log.info(f"Reconnected to Discord ({len(bot.guilds)} guild(s))")
        return
    _startup_done = True

    log.info(f"Logged in as {bot.user} (ID: {bot.user.id})")
    log.info(f"Connected to {len(bot.guilds)} guild(s)")
    # the global slash commands, then each server's pack commands (bot_commands/packs.py)
    synced = await packs.sync_all()
    log.info(f"Synced {synced} slash command(s)")
    bot.add_view(packs.WelcomeView())          # the welcome message's Set me up button
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
    daily_oracle_task.start()
    daily_quiz_task.start()
    daily_versle_task.start()
    daily_hymn_task.start()
    daily_saint_task.start()
    angelus_task.start()
    daily_troparion_task.start()
    daily_learning_task.start()
    plan_reminder_task.start()
    memorize_review_task.start()
    weekly_report_task.start()
    daily_backup_task.start()    # backs up data/ now if today's copy is missing
    weekly_notes_check.start()   # first check now, then weekly

    # Post any CHANGELOG.md entries each server hasn't seen yet, and bring
    # posted introductions up to date with INTRODUCTION.md
    try:
        await announce_changelog(bot)
        await refresh_introductions(bot)
    except Exception as e:
        log.warning(f"Changelog/introduction update failed: {e}")

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
