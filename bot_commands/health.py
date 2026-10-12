"""
Weekly canary for !notes: netbible.org's endpoints are undocumented and could
change without notice. If the check fails, the bot's owner gets a DM (and
!notes keeps working from its backup source meanwhile).
"""
import asyncio

from discord.ext import tasks

from core import bot, log
from net_notes_lookup import health_check


async def run_notes_check(client) -> bool:
    """Run the !notes source check; DM the application owner if it fails."""
    ok, detail = await asyncio.to_thread(health_check)
    if ok:
        log.info(f"!notes source check OK ({detail})")
        return True
    log.warning(f"!notes source check FAILED: {detail}")
    try:
        app = await client.application_info()
        owner = app.team.owner if getattr(app, "team", None) else app.owner
        await owner.send(
            f"⚠️ **`!notes` check failed:** netbible.org — {detail}.\n"
            "Until it's fixed, `!notes` uses its backup source (no positions in the verse, "
            "and a few notes may be missing). The site may have changed how its reader "
            "loads notes; see `net_notes_lookup.py`."
        )
    except Exception as e:
        log.warning(f"Couldn't DM the owner about the failed !notes check: {e}")
    return False


@tasks.loop(hours=24 * 7)
async def weekly_notes_check():
    await run_notes_check(bot)


@weekly_notes_check.before_loop
async def _wait_until_ready():
    await bot.wait_until_ready()
