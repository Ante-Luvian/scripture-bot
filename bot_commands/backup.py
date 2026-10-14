"""
Daily backup of the bot's runtime state (stats, bookmarks, reading plans,
server settings, quiz scores...): each file is a single JSON document, so one
bad write or accidental delete would otherwise lose it for good.

Once a day (the first check after midnight UTC, or at startup) the files are
copied into backups/YYYY-MM-DD/; the newest KEEP_DAYS folders are kept.
"""
import datetime
import shutil
import sys

from discord.ext import tasks

from core import ROOT, log

BACKUP_DIR = ROOT / "backups"
KEEP_DAYS = 14

# Module attributes holding a runtime-state path (tests/conftest.py keeps the
# same list, and a test checks the two agree).
RUNTIME_STATE = ["VOTD_MODE_PATH", "STATS_PATH", "GUILD_ACTIVITY_PATH", "GUILD_CONFIG_PATH",
                 "USER_PREFS_PATH", "BOOKMARKS_PATH", "READING_PLANS_PATH", "SUBSCRIBERS_PATH",
                 "ERROR_LOG_PATH", "REPORT_STATE_PATH", "QUIZ_SCORES_PATH", "DAILY_QUIZ_PATH",
                 "MEMORIZE_PATH", "VERSLE_PATH", "HYMNDAY_PATH"]


def runtime_paths() -> list:
    """Where each runtime file currently lives (looked up at call time)."""
    found = {}
    for name, module in list(sys.modules.items()):
        if name in ("core", "bot") or name.startswith("bot_commands."):
            for attr in RUNTIME_STATE:
                if hasattr(module, attr):
                    found.setdefault(attr, getattr(module, attr))
    return [found[a] for a in RUNTIME_STATE if a in found]


def backup_data(sources, backup_dir, today: datetime.date, keep: int = KEEP_DAYS) -> "int | None":
    """Copy the existing sources into backup_dir/<today>/ unless today's
    backup exists; drop all but the newest `keep` days. Returns the number of
    files copied, or None if today's backup was already made."""
    target = backup_dir / today.isoformat()
    if target.exists():
        return None
    tmp = backup_dir / (today.isoformat() + ".partial")
    shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir(parents=True)
    copied = 0
    for src in sources:
        if src.exists():
            shutil.copy2(src, tmp / src.name)
            copied += 1
    tmp.rename(target)          # a half-finished backup never looks complete
    days = sorted(p for p in backup_dir.iterdir() if p.is_dir() and not p.name.endswith(".partial"))
    for old in days[:-keep]:
        shutil.rmtree(old, ignore_errors=True)
    return copied


@tasks.loop(hours=1)
async def daily_backup_task():
    today = datetime.datetime.now(datetime.timezone.utc).date()
    try:
        copied = backup_data(runtime_paths(), BACKUP_DIR, today)
        if copied is not None:
            log.info(f"Backup: copied {copied} data file(s) to backups/{today.isoformat()}")
    except Exception:
        log.exception("Daily backup failed")
