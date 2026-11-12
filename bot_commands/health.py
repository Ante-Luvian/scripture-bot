"""
Weekly check of every outside source the bot reads from. Each is asked for something it's known to
have, through the same code a command uses; if any fails, the bot's owner gets one DM listing them.
Sources change without notice: netbible.org's endpoints are undocumented, bolls.life began answering
every NIV request with a refusal in place of the verse (which the bot posted as scripture), and a
documented hadith citation turned out not to work at all. `!checksources` (owner only) runs it now.
"""
import asyncio
import datetime
import json
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor

from discord.ext import commands, tasks

import core
from core import bot, log, lookup
from net_notes_lookup import health_check


def _found(result) -> bool:
    return bool(result) and bool(result.get("found"))


def check_bolls():
    """Every translation bolls.life serves, fresh (not from the cache): John 3, or Genesis 1 for the
    Old-Testament-only ones. A withheld translation's notice reads as no text (translation_lookup)."""
    import translation_lookup as tl
    local = {"LXX", "VULG", "CSL", "OE", "PESHITTA"}
    slugs = sorted({slug for slug, _ in tl.TRANSLATIONS.values()} - local)

    def works(slug):
        for book, chapter in ((43, 3), (1, 1)):
            tl._chapter_cache.pop((slug, book, chapter), None)
            if tl._fetch_chapter(slug, book, chapter):
                return True
        return False
    with ThreadPoolExecutor(6) as pool:
        failing = [s for s, ok in zip(slugs, pool.map(works, slugs)) if not ok]
    if failing:
        return False, f"no text for {', '.join(failing)} (of {len(slugs)} translations)"
    return True, f"all {len(slugs)} translations"


def check_sefaria():
    import bot_commands.jewish_learning as jl
    if not _found(lookup.get_verse("Berakhot 2a")):
        return False, "Berakhot 2a not found"
    if not jl.calendar(datetime.date.today()):
        return False, "the learning calendar came back empty"
    return True, "Berakhot 2a and today's learning"


def check_quran():
    import quran_lookup as q
    verses = q.fetch_surah(q.EDITIONS[q.DEFAULT][0], 1)
    return (True, "Surah 1") if verses else (False, "Surah 1 didn't come back")


def check_hadith():
    import hadith_lookup as h
    return (True, "Sahih al-Bukhari 1") if _found(h.get_hadith("Sahih al-Bukhari 1")) else (False, "Sahih al-Bukhari 1 failed")


def check_suttas():
    import sutta_lookup as s
    return (True, "MN 1") if _found(s.get_sutta("MN 1")) else (False, "MN 1 failed")


def check_banidb():
    import banidb_lookup as b
    result = b.get_bani("Dasam Granth 1", lambda ref: {"found": False})
    return (True, "Dasam Granth 1") if _found(result) else (False, "Dasam Granth 1 failed")


def check_gita():
    import gita_lookup as g
    return (True, "Gita 2:47") if g.fetch(2, 47) else (False, "Gita 2:47 failed")


def check_votd():
    core._votd_cache = ("", None, "")                   # (today's is cached once fetched)
    reference, _ = core._scrape_votd()
    return (True, reference) if reference else (False, "no verse found on the page")


def check_oca():
    import bot_commands.troparion as t
    return (True, "today's troparia") if t.commemorations(datetime.date.today()) else (False, "no troparia for today")


def check_aladhan():
    import bot_commands.salah as s
    return (True, "London") if s.fetch("London") else (False, "no times for London")


def check_summa():
    import summa_lookup as s
    return (True, "I.2.3") if _found(s.get_summa(1, 2, 3)) else (False, "Summa I.2.3 failed")


def check_gematrix():
    req = urllib.request.Request("https://www.gematrix.org/?word=love", headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=20) as r:
        page = r.read().decode("utf-8", "replace")
    return (True, "love") if "love" in page.lower() else (False, "the page didn't have the word")


def check_calendars():
    """!today's sites (universalis, orthocal, hebcal, aladhan), as !today itself asks them."""
    import liturgical_calendar as lc
    failed, asked = [], []
    real = lc._http_get

    def watched(url, timeout=15):
        data = real(url, timeout=timeout)
        host = url.split("/")[2]
        asked.append(host)
        if data is None:
            failed.append(host)
        return data
    lc._http_get = watched
    try:
        lc.all_traditions(datetime.date.today())
    finally:
        lc._http_get = real
    if failed:
        return False, f"no answer from {', '.join(sorted(set(failed)))}"
    return True, ", ".join(sorted(set(asked))) or "nothing asked (all cached)"


PICTURE_DATA = {"Doré": ["data/dore/plates.json"], "Blake": ["data/blake/plates.json", "data/blake/art.json"],
                "the 🖌️ pictures": ["data/illustrations/*.json"]}


def _wikimedia_entries(node):
    if isinstance(node, dict):
        if str(node.get("image", "")).startswith(("https://upload.wikimedia.org/", "https://thumb.wikimedia.org/")):
            yield node
        for value in node.values():
            yield from _wikimedia_entries(value)
    elif isinstance(node, list):
        for value in node:
            yield from _wikimedia_entries(value)


def check_pictures():
    """Every Wikimedia picture has its local copy (core.local_picture). Discord can't show Wikimedia's
    addresses any more (2026-11-08), so a missing copy is an empty embed: the copies are out of git, and
    a fresh checkout or a deleted folder loses them (README: rebuild with scripts/wikimedia_copies.py)."""
    missing, total = {}, 0
    for label, patterns in PICTURE_DATA.items():
        for pattern in patterns:
            for path in sorted(core.ROOT.glob(pattern)):
                for entry in _wikimedia_entries(json.loads(path.read_text(encoding="utf-8"))):
                    total += 1
                    if not core.local_picture(entry):
                        missing[label] = missing.get(label, 0) + 1
    if missing:
        return False, (f"{sum(missing.values())} of {total} have no local copy ("
                       + ", ".join(f"{label} {n}" for label, n in missing.items())
                       + "); rebuild with scripts/wikimedia_copies.py (README)")
    return True, f"all {total} here"


# (source, the commands that use it, check)
SOURCES = [
    ("bolls.life", "!verse with a translation, !compare, !search ... ESV", check_bolls),
    ("Sefaria", "the Talmud, Mishnah and other rabbinic texts, !parsha, !dafyomi, !learning", check_sefaria),
    ("Quran API (jsDelivr)", "the Quran's translations", check_quran),
    ("Hadith API (jsDelivr)", "the hadith collections", check_hadith),
    ("SuttaCentral", "the Pali Canon (MN 1, SN 56.11...)", check_suttas),
    ("BaniDB", "the Dasam Granth and other Sikh texts", check_banidb),
    ("Gita API", "the Gita's other translations and commentaries", check_gita),
    ("netbible.org", "!notes", lambda: health_check()),
    ("verseoftheday.com", "!votd and the daily verse", check_votd),
    ("oca.org", "!troparion", check_oca),
    ("aladhan.com", "!salah", check_aladhan),
    ("newadvent.org", "!summa", check_summa),
    ("gematrix.org", "!gematria", check_gematrix),
    ("Church calendars", "!today", check_calendars),
    ("Picture copies", "!dore, !blake, the 🖌️ buttons", check_pictures),
]


def _run(check):
    try:
        return check()
    except Exception as e:                                   # a check that crashes is a failed check
        return False, f"{type(e).__name__}: {str(e)[:100]}"


def run_checks(sources=SOURCES) -> list:
    """[(source, used by, ok, detail)], every source checked at once."""
    with ThreadPoolExecutor(8) as pool:
        results = list(pool.map(lambda s: _run(s[2]), sources))
    return [(name, used, ok, detail) for (name, used, _), (ok, detail) in zip(sources, results)]


def report(results: list) -> str:
    failed = [r for r in results if not r[2]]
    lines = [f"❌ **{name}** ({used}): {detail}" for name, used, _, detail in failed]
    head = (f"⚠️ **{len(failed)} of {len(results)} outside sources failed their weekly check.** "
            "Those commands may be broken until they're fixed:" if failed else
            f"✅ All {len(results)} outside sources answered.")
    return "\n".join([head] + lines)[:1900]


async def run_source_checks(client, sources=SOURCES) -> list:
    """Check every source; DM the owner only if something failed. Returns the results."""
    results = await asyncio.to_thread(run_checks, sources)
    for name, _, ok, detail in results:
        (log.info if ok else log.warning)(f"Source check {'OK' if ok else 'FAILED'}: {name} ({detail})")
    if not all(r[2] for r in results):
        try:
            app = await client.application_info()
            owner = app.team.owner if getattr(app, "team", None) else app.owner
            await owner.send(report(results))
        except Exception as e:
            log.warning(f"Couldn't DM the owner about the failed source check: {e}")
    return results


async def run_notes_check(client) -> bool:
    """netbible.org alone (the weekly report uses it)."""
    results = await run_source_checks(client, [s for s in SOURCES if s[0] == "netbible.org"])
    return results[0][2]


SOURCE_CHECK_PATH = core.ROOT / "data" / "source_check.json"      # when the sources were last checked
WEEK = 7 * 24 * 3600


def _due() -> bool:
    """A week since the last check (the bot restarts often; checking every source each time is too much)."""
    try:
        last = json.loads(SOURCE_CHECK_PATH.read_text(encoding="utf-8")).get("at", 0)
    except (OSError, ValueError):
        last = 0
    return time.time() - last > WEEK - 3600


@tasks.loop(hours=6)
async def weekly_notes_check():
    """(name kept: bot.py starts it) every source, once a week."""
    if not _due():
        return
    await run_source_checks(bot)
    try:
        SOURCE_CHECK_PATH.write_text(json.dumps({"at": time.time()}), encoding="utf-8")
    except OSError as e:
        log.warning(f"Couldn't record the source check: {e}")


@weekly_notes_check.before_loop
async def _wait_until_ready():
    await bot.wait_until_ready()


@bot.command(name="checksources", hidden=True)
@commands.is_owner()
async def cmd_checksources(ctx):
    """Owner only: check every outside source now."""
    async with ctx.typing():
        results = await asyncio.to_thread(run_checks)
    await ctx.send(report(results))
