"""
!today liturgical calendar, !bcp daily office (its psalms, lessons and collect), and !prayer.
"""
import asyncio
import discord
import json
import random
import re
from discord import app_commands
from core import (
    bot,
    guild_calendars,
    lookup,
)
from core import ROOT
from bot_commands import prayers

# ── !today — Liturgical / religious calendar across traditions ─────────────────

# Which traditions to include for each !today flavour.
# "christian" = all three Christian denominations in one embed.
_TODAY_GROUPS = {
    "all":        ["catholic", "anglican", "orthodox", "jewish", "islamic"],
    "christian":  ["catholic", "anglican", "orthodox"],
    "catholic":   ["catholic"],
    "anglican":   ["anglican"],
    "orthodox":   ["orthodox"],
    "islam":      ["islamic"],
    "islamic":    ["islamic"],
    "muslim":     ["islamic"],
    "jewish":     ["jewish"],
    "judaism":    ["jewish"],
    "jew":        ["jewish"],
}

# Display metadata per tradition key (used in both embeds and help)
_TODAY_META = {
    "catholic": ("✝️", "Catholic (Roman Rite)"),
    "anglican": ("⛪", "Anglican (Common Worship)"),
    "orthodox": ("☦️", "Orthodox"),
    "jewish":   ("✡️", "Jewish"),
    "islamic":  ("☪️", "Islamic"),
}


async def _send_today(ctx_or_channel, target_date, traditions: list[str], title_label: str):
    """
    Build and send a combined embed showing the requested traditions
    for `target_date`.
    """
    import liturgical_calendar as _lcal

    loop = asyncio.get_event_loop()

    fetchers = {
        "catholic": _lcal.catholic_today,
        "anglican": _lcal.anglican_today,
        "orthodox": _lcal.orthodox_today,
        "jewish":   _lcal.jewish_today,
        "islamic":  _lcal.islamic_today,
    }

    # Kick off all requested lookups in parallel
    futures = {name: loop.run_in_executor(None, fetchers[name], target_date)
               for name in traditions if name in fetchers}
    results: dict[str, dict] = {}
    for name, fut in futures.items():
        try:
            results[name] = await fut
        except Exception as e:
            results[name] = {"found": False, "error": f"{e}"}

    pretty = (
        target_date.strftime("%A, ")
        + target_date.strftime("%d").lstrip("0")
        + target_date.strftime(" %B %Y")
    )

    embed = discord.Embed(
        title=f"📅 {pretty} — {title_label}",
        color=discord.Color.dark_gold(),
    )

    for name in traditions:
        emoji, label = _TODAY_META.get(name, ("•", name.title()))
        r = results.get(name) or {}
        if r.get("found"):
            value = r.get("summary", "—")
            details = (r.get("details") or "").strip()
            if details:
                value = f"{value}\n{details}"
        else:
            err = r.get("error", "lookup failed")
            value = f"_{err}_"
        if len(value) > 1020:
            value = value[:1017] + "…"
        embed.add_field(name=f"{emoji} {label}", value=value, inline=False)

    sources = []
    for r in results.values():
        s = (r or {}).get("source")
        if s and s not in sources:
            sources.append(s)
    if sources:
        embed.set_footer(text="Sources: " + " · ".join(sources))

    await ctx_or_channel.send(embed=embed)


def _parse_today_date(raw: str):
    """Return a datetime.date from raw input, or None if unparseable.
    Accepts: "" (today), YYYY-MM-DD, YYYY/MM/DD, MM-DD, MM/DD."""
    import datetime as _dt
    raw = (raw or "").strip()
    if not raw:
        return _dt.date.today()
    today = _dt.date.today()
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y.%m.%d"):
        try:
            return _dt.datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    for sep in ("-", "/"):
        try:
            # (parsed with this year added: "02-29" alone has no year, and failed on the 29th of February)
            return _dt.datetime.strptime(f"{today.year}-{raw}", f"%Y-%m{sep}%d").date()
        except ValueError:
            continue
    return None


def _parse_today_args(raw: str) -> tuple[str, str] | None:
    """
    Split `!today` arguments into (tradition_key, date_string).
    Either or both may be blank.

    Returns None if the tradition word is unrecognised (and was not a date).
    """
    parts = (raw or "").strip().split(None, 1)
    if not parts:
        return ("all", "")

    first = parts[0].lower()
    rest = parts[1] if len(parts) > 1 else ""

    # First token is a known tradition?
    if first in _TODAY_GROUPS:
        return (first, rest.strip())

    # First token might be a date — try to parse the whole thing as date
    if _parse_today_date(raw) is not None:
        return ("all", raw.strip())

    return None


@bot.command(name="today", aliases=["calendar"])
async def cmd_today(ctx, *, args: str = ""):
    """Liturgical / religious observances for a date.

    Usage:
      !today                        — today, all five traditions
      !today christian              — Catholic + Anglican + Orthodox
      !today anglican               — Anglican (Common Worship) only
      !today catholic               — Catholic (Roman Rite) only
      !today orthodox               — Orthodox only
      !today islam                  — Islamic only
      !today jewish                 — Jewish only
      !today catholic 2026-12-25    — any tradition + a specific date
    """
    parsed = _parse_today_args(args)
    if parsed is None:
        await ctx.send(
            "⚠️ Unknown tradition. Try `christian`, `anglican`, `catholic`, "
            "`orthodox`, `islam`, or `jewish` — or just `!today` for all "
            "five traditions."
        )
        return
    key, date_raw = parsed
    d = _parse_today_date(date_raw)
    if d is None:
        await ctx.send(f"⚠️ Couldn't parse `{date_raw}` as a date. Try `YYYY-MM-DD` or `MM-DD`.")
        return

    traditions = guild_calendars(getattr(getattr(ctx, "guild", None), "id", None), _TODAY_GROUPS[key])
    if key == "all":
        title_label = "All Traditions"
    elif key == "christian":
        title_label = "Christian"
    else:
        _, full_label = _TODAY_META.get(traditions[0], ("", key.title()))
        title_label = full_label

    async with ctx.typing():
        await _send_today(ctx, d, traditions, title_label)


@bot.tree.command(name="today", description="Today's liturgical / religious observances")
@app_commands.describe(
    tradition='Which tradition: all (default), christian, anglican, catholic, orthodox, islam, jewish',
    date='Optional date: YYYY-MM-DD or MM-DD; blank for today',
)
async def today_slash(interaction: discord.Interaction, tradition: str = "all", date: str = ""):
    await interaction.response.defer()
    key = (tradition or "all").strip().lower()
    if key not in _TODAY_GROUPS:
        await interaction.followup.send(
            "⚠️ Unknown tradition. Try `all`, `christian`, `anglican`, `catholic`, "
            "`orthodox`, `islam`, or `jewish`."
        )
        return
    d = _parse_today_date(date)
    if d is None:
        await interaction.followup.send(f"⚠️ Couldn't parse `{date}` as a date.")
        return
    traditions = guild_calendars(interaction.guild_id, _TODAY_GROUPS[key])
    if key == "all":
        title_label = "All Traditions"
    elif key == "christian":
        title_label = "Christian"
    else:
        _, full_label = _TODAY_META.get(traditions[0], ("", key.title()))
        title_label = full_label
    await _send_today(interaction.channel, d, traditions, title_label)


# ── !bcp — Book of Common Prayer daily office ────────────────────────────────

# The lectionary's books, as it abbreviates them (compared without dots or spaces, in lower case: "Jere." "jere",
# "S. of Sol." "sofsol", "1Sam." "1sam"); anything else is tried as the bot's own name or alias for a book.
BCP_BOOKS = {
    "gen": "Genesis", "ex": "Exodus", "exod": "Exodus", "lev": "Leviticus", "num": "Numbers", "deut": "Deuteronomy",
    "josh": "Joshua", "judg": "Judges", "ruth": "Ruth", "1sam": "1 Samuel", "2sam": "2 Samuel", "1kings": "1 Kings",
    "2kings": "2 Kings", "1kgs": "1 Kings", "2kgs": "2 Kings", "1chr": "1 Chronicles", "2chr": "2 Chronicles",
    "1chron": "1 Chronicles", "2chron": "2 Chronicles", "1chrn": "1 Chronicles", "2chrn": "2 Chronicles",
    "prayerofmanasses": "Prayer of Manasseh", "prayerofmanasseh": "Prayer of Manasseh", "ezra": "Ezra",
    "softhethreechildren": "Song of the Three Children", "songofthethreechildren": "Song of the Three Children", "neh": "Nehemiah", "esth": "Esther",
    "job": "Job", "ps": "Psalms", "prov": "Proverbs", "eccl": "Ecclesiastes", "eccles": "Ecclesiastes",
    "cant": "Song of Solomon", "sofsol": "Song of Solomon", "songofsol": "Song of Solomon", "isa": "Isaiah",
    "jer": "Jeremiah", "jere": "Jeremiah", "lam": "Lamentations", "eze": "Ezekiel", "ezek": "Ezekiel",
    "dan": "Daniel", "hos": "Hosea", "joel": "Joel", "amos": "Amos", "obad": "Obadiah", "jon": "Jonah",
    "jonah": "Jonah", "mic": "Micah", "nah": "Nahum", "hab": "Habakkuk", "zeph": "Zephaniah", "hag": "Haggai",
    "zech": "Zechariah", "mal": "Malachi",
    "tob": "Tobit", "jud": "Judith", "judith": "Judith", "wis": "Wisdom of Solomon", "wisd": "Wisdom of Solomon",
    "ecclus": "Sirach", "sir": "Sirach", "bar": "Baruch", "1macc": "1 Maccabees", "2macc": "2 Maccabees",
    "mt": "Matthew", "matt": "Matthew", "mk": "Mark", "lk": "Luke", "jn": "John", "acts": "Acts", "rom": "Romans",
    "1cor": "1 Corinthians", "2cor": "2 Corinthians", "gal": "Galatians", "eph": "Ephesians", "phil": "Philippians",
    "col": "Colossians", "1thes": "1 Thessalonians", "2thes": "2 Thessalonians", "1thess": "1 Thessalonians",
    "2thess": "2 Thessalonians", "1tim": "1 Timothy", "2tim": "2 Timothy", "tit": "Titus", "philem": "Philemon",
    "philemon": "Philemon", "heb": "Hebrews", "jas": "James", "jam": "James", "1pet": "1 Peter", "2pet": "2 Peter",
    "1jn": "1 John", "2jn": "2 John", "3jn": "3 John", "1john": "1 John", "2john": "2 John", "3john": "3 John",
    "jude": "Jude", "rev": "Revelation",
}


def _bcp_book(raw: str) -> "str | None":
    """The lectionary's name for a book -> the bot's ("I Pet." -> "1 Peter", "Jam." -> "James")."""
    s = re.sub(r"^(III|II|I)(?=\s|\.)", lambda m: str(len(m.group(1))), raw.strip())      # ("I Pet.", "II Cor.")
    key = re.sub(r"[\s.]", "", s).lower()
    if key in BCP_BOOKS:
        return BCP_BOOKS[key]
    corpus, canon = lookup._resolve_exact(s.rstrip("."))
    return canon


def _bcp_segments(ref: str) -> "tuple[str | None, list]":
    """A lectionary reference -> (book, [(c1, v1, c2, v2)]), v2 "end" for a chapter's last verse, (c, None, c, None)
    a whole chapter. Its notation: "Gen. 11:1-9; 27-12:10" (11:1-9, then 11:27-12:10), "Ex. 6:2-23 7:1-7",
    "Job 25 26" (two chapters), "1 Tim.1:18-2 end", "Prov. 8:1, 22-end", "Acts 9:1-22 (23-31)" (the brackets an
    optional longer reading: the set one is read), "Ruth 2:1-20 a" (half a verse: the verse), "Num. 24;1-19" (a
    misprint for 24:1), "Philemon" (a one-chapter book, whole)."""
    s = re.sub(r"\([^)]*\)", " ", ref).replace("=", "-")                  # (the optional longer reading; "1=26")
    s = re.sub(r"(?<=\d)\s*[ab]\b", "", s)                                  # (half verses)
    m = re.match(r"^\s*((?:III|II|I|[123])?\s*[A-Za-z][A-Za-z.\s]*?)\s*\.?\s*(?=\d|$)", s)
    if not m:
        return None, []
    book = _bcp_book(m.group(1))
    spec = s[m.end():].strip()
    spec = re.sub(r"(\d+)\s*-\s*end", r"\1-end", spec)
    spec = re.sub(r"(\d+)\s+end\b", r"\1:end", spec)                       # ("2 end" -> "2:end")
    spec = re.sub(r":\s+", ":", spec)                                       # ("24: 13-35")
    if re.match(r"^\d+;\d", spec) and ":" not in spec.split(";")[0]:
        spec = spec.replace(";", ":", 1)                                    # ("24;1-19")
    if not spec:
        return book, [(1, None, 1, None)]                                   # (Philemon, Jude, 2 John)
    one_chapter = bool(book) and lookup._one_chapter(book)
    segments, chapter = [], (1 if one_chapter and ":" not in spec else None)   # ("Jude 17-end": its verses)
    # (after a comma or semicolon a bare number is a verse of the same chapter, "Prov. 8:1, 22-end"; after a space,
    # a chapter, "Deut. 32:48-end 34")
    for sep, item in re.findall(r"(^|[;,]\s*|\s+)([^;,\s]+)", spec):
        if sep.strip() == "" and sep and ":" not in item and not one_chapter:
            chapter = None
        a, _, b = item.partition("-")

        def point(p, default_chapter):
            if ":" in p:
                c, v = p.split(":", 1)
                return int(c), (v if v == "end" else int(v))
            return default_chapter, (p if p == "end" else int(p))

        try:
            if ":" in a:
                c1, v1 = point(a, None)
            elif chapter is None:                                           # (a whole chapter, or chapters "25-26")
                c1 = int(a)
                if b and ":" not in b:
                    for c in range(c1, int(b) + 1):
                        segments.append((c, None, c, None))
                    chapter = int(b)
                    continue
                if not b:
                    segments.append((c1, None, c1, None))
                    continue
                v1 = 1
            else:
                c1, v1 = chapter, int(a)
            if not b:
                c2, v2 = c1, v1
            elif ":" in b:
                c2, v2 = point(b, c1)
            else:
                c2, v2 = c1, (b if b == "end" else int(b))
        except ValueError:
            return book, []
        segments.append((c1, v1, c2, v2))
        chapter = c2
    return book, segments


def _bcp_fetch_text(ref: str) -> tuple[str, str]:
    """A lectionary reference -> (display reference, text): each of its pieces read and run together."""
    book, segments = _bcp_segments(ref)
    if not book or not segments:
        return ref, "*[not available]*"

    def last_verse(chap: int) -> int:
        corpus, canon = lookup._resolve_book(book)
        nums = [int(k) for k in lookup._data[corpus].get(canon, {}).get(str(chap), {}) if k.isdigit()] if canon else []
        return max(nums) if nums else 200

    refs, texts = [], []
    for c1, v1, c2, v2 in segments:
        v1 = 1 if v1 is None else v1
        v2 = last_verse(c2) if v2 in (None, "end") else v2
        try:
            result = lookup.get_verse_range(book, c1, v1, c2, v2)
        except Exception:
            result = {}
        if result.get("found"):
            refs.append(result.get("reference", ""))
            texts.append(result.get("text", ""))
    if not texts:
        return ref, "*[not available]*"
    return "; ".join(r for r in refs if r) or ref, "\n\n".join(texts)


def _bcp_period_for_now() -> str:
    """Midnight-noon = morning, noon-midnight = evening."""
    import datetime as _dt
    now = _dt.datetime.now()
    return "morning" if now.hour < 12 else "evening"


async def _send_bcp(ctx_or_channel, target_date, period: str):
    """Build and send the BCP daily office embed(s) with pagination."""
    import bcp_lookup as _bcp

    loop = asyncio.get_event_loop()
    info = await loop.run_in_executor(None, _bcp.bcp_for_date, target_date, period)

    if not info.get("found"):
        err = info.get("error", "Lookup failed.")
        await ctx_or_channel.send(f"⚠️ BCP lookup error: {err}")
        return

    pretty_date = (
        target_date.strftime("%A, ")
        + target_date.strftime("%d").lstrip("0")
        + target_date.strftime(" %B %Y")
    )
    period_label = "Morning Prayer" if period == "morning" else "Evening Prayer"

    # ── Compose section header text ──────────────────────────────────────────
    title_bits = []
    if info.get("section_title"):
        title_bits.append(info["section_title"])
    label = info.get("label", "")
    if label and label != "Sunday":
        title_bits.append(label)
    if info.get("year"):
        title_bits.append(f"Year {info['year']}")
    section_line = " · ".join(title_bits) if title_bits else "—"

    # ── Page 1: Psalms ───────────────────────────────────────────────────────
    psalter = info.get("psalter") or {}
    portions = psalter.get("portions", [])

    # Each portion becomes one or more pages depending on length.
    psalter_pages: list[tuple[str, str]] = []
    for portion in portions:
        label = portion.get("label", "Psalm")
        incipit = portion.get("incipit", "")
        verses = portion.get("verses", [])
        if not verses:
            # Fall back to incipit-only if text is missing
            body = f"_{incipit}_" if incipit else "*[text not available]*"
            psalter_pages.append((label, body))
            continue

        # Heading line: incipit
        head = f"_{incipit}_\n\n" if incipit else ""
        # Build verse lines like "1. BLESSED is the man..."
        # The first verse number is the starting verse from the label, if specified.
        first_verse_num = 1
        if ":" in portion.get("ref", ""):
            try:
                rng = portion["ref"].split(":", 1)[1]
                first_verse_num = int(rng.split("-")[0])
            except (ValueError, IndexError):
                pass
        lines = [f"**{first_verse_num + i}.** {v}" for i, v in enumerate(verses)]

        # Paginate: Discord description cap = 4096 chars. Leave headroom for the
        # heading + page indicator metadata. Cap each page at ~3800 chars.
        chunk = head
        part = 1
        for line in lines:
            if len(chunk) + len(line) + 2 > 3800:
                title = label if part == 1 else f"{label} (cont. {part})"
                psalter_pages.append((title, chunk.rstrip()))
                chunk = ""
                part += 1
            chunk += line + "\n"
        if chunk.strip():
            title = label if part == 1 else f"{label} (cont. {part})"
            psalter_pages.append((title, chunk.rstrip()))

    # ── Pages 2 & 3: Lessons (with KJV text) ─────────────────────────────────
    lesson_pages: list[tuple[str, str]] = []  # (heading, body)
    lesson_summary: list[str] = []             # for the summary page
    for les in info.get("lessons", []):
        display_ref, text = await loop.run_in_executor(
            None, _bcp_fetch_text, les["ref"]
        )
        heading = f"{les['slot']} — {display_ref}"
        lesson_summary.append(f"• **{les['slot']}** — {display_ref}")
        body = text or "*[not available]*"
        # If body is too long for one embed description (~4000 chars), split.
        if len(body) <= 3900:
            lesson_pages.append((heading, body))
        else:
            # Split on sentence boundaries
            remaining = body
            part = 1
            while remaining:
                if len(remaining) <= 3900:
                    lesson_pages.append((
                        f"{heading} ({'part ' + str(part) if part > 1 else 'cont.'})" if part > 1 else heading,
                        remaining
                    ))
                    break
                window = remaining[:3900]
                cut = window.rfind(". ")
                if cut < 1000:
                    cut = window.rfind(" ")
                if cut <= 0:
                    cut = 3900
                lesson_pages.append((
                    f"{heading} ({'part ' + str(part)})" if part > 1 else heading,
                    remaining[:cut + 1].strip()
                ))
                remaining = remaining[cut + 1:].lstrip()
                part += 1

    # ── Final page: Collect of the Day ───────────────────────────────────────
    collect_info = info.get("collect")

    # ── Build all pages as (title, body) tuples ──────────────────────────────
    pages: list[tuple[str, str]] = []

    # Page 1: header (section info) — short summary page so the psalms get
    # their own dedicated pages with full text.
    p1_sections = [f"_{section_line}_", ""]
    p1_sections.append(f"**The Psalms appointed for this {period_label}**")
    if portions:
        p1_sections.extend(f"• {p['label']}" for p in portions)
    else:
        p1_sections.append("*No psalms appointed.*")
    if lesson_summary:
        p1_sections.append("")
        p1_sections.append("**The Lessons**")
        # Each lesson on its own line, with a blank between
        for i, line in enumerate(lesson_summary):
            if i > 0:
                p1_sections.append("")
            p1_sections.append(line)
    if collect_info:
        p1_sections.append("")
        c_name = collect_info.get("name", "Collect")
        if collect_info.get("is_saint_day"):
            p1_sections.append(f"**The Collect:** {c_name}")
        else:
            p1_sections.append(f"**The Collect:** {c_name}")
    p1_body = "\n".join(p1_sections)
    pages.append(("BCP Daily Office", p1_body))

    # Psalm-text pages
    for heading, body in psalter_pages:
        pages.append((heading, body))

    # Lessons pages
    for heading, body in lesson_pages:
        pages.append((heading, body))

    # Collect page
    if collect_info:
        collect_name = collect_info.get("name", "Collect")
        collect_text = collect_info.get("collect", "")
        if collect_info.get("is_saint_day"):
            collect_heading = f"The Collect for {collect_name}"
        else:
            collect_heading = f"The Collect: {collect_name}"
        if collect_text:
            pages.append((collect_heading, collect_text))

    if not pages:
        await ctx_or_channel.send("⚠️ Nothing to display.")
        return

    def build_embed(idx: int) -> discord.Embed:
        heading, body = pages[idx]
        e = discord.Embed(
            title=f"📖 {pretty_date} — {period_label}",
            description=body,
            color=discord.Color.dark_blue(),
        )
        # Page indicator + collect note
        footer_bits = [f"Page {idx + 1}/{len(pages)}"]
        footer_bits.append(heading)
        if info.get("section_key"):
            footer_bits.append(f"({info['section_key']}/{info.get('label','')})")
        e.set_footer(text=" · ".join(footer_bits))
        return e

    if len(pages) <= 1:
        await ctx_or_channel.send(embed=build_embed(0))
        return

    class BcpView(discord.ui.View):
        def __init__(self):
            super().__init__(timeout=300)
            self.idx = 0
            self.message: discord.Message | None = None

        @discord.ui.button(emoji="◀", style=discord.ButtonStyle.secondary)
        async def prev(self, interaction: discord.Interaction, button: discord.ui.Button):
            self.idx = (self.idx - 1) % len(pages)
            await interaction.response.edit_message(embed=build_embed(self.idx), view=self)

        @discord.ui.button(emoji="▶", style=discord.ButtonStyle.secondary)
        async def next(self, interaction: discord.Interaction, button: discord.ui.Button):
            self.idx = (self.idx + 1) % len(pages)
            await interaction.response.edit_message(embed=build_embed(self.idx), view=self)

        async def on_timeout(self):
            try:
                if self.message is not None:
                    await self.message.edit(view=None)
            except Exception:
                pass

    view = BcpView()
    msg = await ctx_or_channel.send(embed=build_embed(0), view=view)
    view.message = msg


# ── Subcommand helpers (single-purpose senders) ──────────────────────────────

async def _send_bcp_psalm(ctx_or_channel, target_date, period: str):
    """Send only the Psalm(s) appointed for the given date and period."""
    import bcp_lookup as _bcp
    loop = asyncio.get_event_loop()
    info = await loop.run_in_executor(None, _bcp.bcp_for_date, target_date, period)
    if not info.get("found") or not info.get("psalter"):
        await ctx_or_channel.send("⚠️ Could not look up the Psalter for that date.")
        return

    pretty_date = (target_date.strftime("%A, ")
                   + target_date.strftime("%d").lstrip("0")
                   + target_date.strftime(" %B %Y"))
    period_label = "Morning Prayer" if period == "morning" else "Evening Prayer"
    portions = info["psalter"].get("portions", [])

    # Build pages exactly like the full office's Psalm pages
    psalter_pages: list[tuple[str, str]] = []
    for portion in portions:
        label = portion.get("label", "Psalm")
        incipit = portion.get("incipit", "")
        verses = portion.get("verses", [])
        if not verses:
            body = f"_{incipit}_" if incipit else "*[text not available]*"
            psalter_pages.append((label, body))
            continue
        head = f"_{incipit}_\n\n" if incipit else ""
        first_verse_num = 1
        if ":" in portion.get("ref", ""):
            try:
                rng = portion["ref"].split(":", 1)[1]
                first_verse_num = int(rng.split("-")[0])
            except (ValueError, IndexError):
                pass
        lines = [f"**{first_verse_num + i}.** {v}" for i, v in enumerate(verses)]
        chunk = head
        part = 1
        for line in lines:
            if len(chunk) + len(line) + 2 > 3800:
                title = label if part == 1 else f"{label} (cont. {part})"
                psalter_pages.append((title, chunk.rstrip()))
                chunk = ""
                part += 1
            chunk += line + "\n"
        if chunk.strip():
            title = label if part == 1 else f"{label} (cont. {part})"
            psalter_pages.append((title, chunk.rstrip()))

    if not psalter_pages:
        await ctx_or_channel.send("⚠️ No psalms appointed.")
        return

    def build_embed(idx):
        heading, body = psalter_pages[idx]
        e = discord.Embed(
            title=f"📖 {pretty_date} — {period_label}: Psalms",
            description=body,
            color=discord.Color.dark_blue(),
        )
        e.set_footer(text=f"Page {idx + 1}/{len(psalter_pages)} · {heading}")
        return e

    if len(psalter_pages) == 1:
        await ctx_or_channel.send(embed=build_embed(0))
        return

    class PsalmView(discord.ui.View):
        def __init__(self):
            super().__init__(timeout=300)
            self.idx = 0
            self.message = None
        @discord.ui.button(emoji="◀", style=discord.ButtonStyle.secondary)
        async def prev(self, interaction, button):
            self.idx = (self.idx - 1) % len(psalter_pages)
            await interaction.response.edit_message(embed=build_embed(self.idx), view=self)
        @discord.ui.button(emoji="▶", style=discord.ButtonStyle.secondary)
        async def next(self, interaction, button):
            self.idx = (self.idx + 1) % len(psalter_pages)
            await interaction.response.edit_message(embed=build_embed(self.idx), view=self)
        async def on_timeout(self):
            try:
                if self.message: await self.message.edit(view=None)
            except Exception: pass
    view = PsalmView()
    msg = await ctx_or_channel.send(embed=build_embed(0), view=view)
    view.message = msg


async def _send_bcp_lessons(ctx_or_channel, target_date, period: str,
                            which: str = "both"):
    """Send the lesson(s). which = 'first' | 'second' | 'both'."""
    import bcp_lookup as _bcp
    loop = asyncio.get_event_loop()
    info = await loop.run_in_executor(None, _bcp.bcp_for_date, target_date, period)
    if not info.get("found"):
        await ctx_or_channel.send(f"⚠️ Could not resolve lessons for {target_date}.")
        return

    pretty_date = (target_date.strftime("%A, ")
                   + target_date.strftime("%d").lstrip("0")
                   + target_date.strftime(" %B %Y"))
    period_label = "Morning Prayer" if period == "morning" else "Evening Prayer"

    lessons = info.get("lessons", [])
    if which == "first":
        lessons = lessons[:1]
    elif which == "second":
        lessons = lessons[1:2]
    if not lessons:
        await ctx_or_channel.send("⚠️ No lessons appointed.")
        return

    pages: list[tuple[str, str]] = []
    for les in lessons:
        display_ref, text = await loop.run_in_executor(None, _bcp_fetch_text, les["ref"])
        heading = f"{les['slot']} — {display_ref}"
        body = text or "*[not available]*"
        if len(body) <= 3900:
            pages.append((heading, body))
        else:
            remaining = body
            part = 1
            while remaining:
                if len(remaining) <= 3900:
                    pages.append((
                        f"{heading} (part {part})" if part > 1 else heading,
                        remaining
                    ))
                    break
                window = remaining[:3900]
                cut = window.rfind(". ")
                if cut < 1000:
                    cut = window.rfind(" ")
                if cut <= 0:
                    cut = 3900
                pages.append((
                    f"{heading} (part {part})" if part > 1 else heading,
                    remaining[:cut + 1].strip()
                ))
                remaining = remaining[cut + 1:].lstrip()
                part += 1

    def build_embed(idx):
        heading, body = pages[idx]
        e = discord.Embed(
            title=f"📖 {pretty_date} — {period_label}",
            description=body,
            color=discord.Color.dark_blue(),
        )
        e.set_footer(text=f"Page {idx + 1}/{len(pages)} · {heading}")
        return e

    if len(pages) == 1:
        await ctx_or_channel.send(embed=build_embed(0))
        return

    class LessonView(discord.ui.View):
        def __init__(self):
            super().__init__(timeout=300)
            self.idx = 0
            self.message = None
        @discord.ui.button(emoji="◀", style=discord.ButtonStyle.secondary)
        async def prev(self, interaction, button):
            self.idx = (self.idx - 1) % len(pages)
            await interaction.response.edit_message(embed=build_embed(self.idx), view=self)
        @discord.ui.button(emoji="▶", style=discord.ButtonStyle.secondary)
        async def next(self, interaction, button):
            self.idx = (self.idx + 1) % len(pages)
            await interaction.response.edit_message(embed=build_embed(self.idx), view=self)
        async def on_timeout(self):
            try:
                if self.message: await self.message.edit(view=None)
            except Exception: pass
    view = LessonView()
    msg = await ctx_or_channel.send(embed=build_embed(0), view=view)
    view.message = msg


async def _send_bcp_collect(ctx_or_channel, target_date):
    """Send only the Collect of the Day for the given date."""
    import bcp_lookup as _bcp
    loop = asyncio.get_event_loop()
    # Period doesn't matter for the collect itself, but the resolver needs one.
    info = await loop.run_in_executor(None, _bcp.bcp_for_date, target_date, "morning")
    if not info.get("found"):
        await ctx_or_channel.send(f"⚠️ Could not resolve a collect for {target_date}.")
        return
    collect = info.get("collect")
    if not collect or not collect.get("collect"):
        await ctx_or_channel.send(f"⚠️ No collect found for {target_date}.")
        return

    pretty_date = (target_date.strftime("%A, ")
                   + target_date.strftime("%d").lstrip("0")
                   + target_date.strftime(" %B %Y"))
    name = collect.get("name", "Collect")
    if collect.get("is_saint_day"):
        title = f"📿 The Collect for {name}"
    else:
        title = f"📿 The Collect: {name}"

    embed = discord.Embed(
        title=title,
        description=collect["collect"],
        color=discord.Color.dark_purple(),
    )
    embed.set_footer(text=f"{pretty_date} · Book of Common Prayer 1662")
    await ctx_or_channel.send(embed=embed)


# ── 📅 "Today's readings" button (under the Verse of the Day) ────────────────
# One look at the day's whole daily office -- psalms and lessons for morning
# and evening, and the collect -- as references; !bcp morning / evening /
# collect give the full texts. The button carries its date, so it shows that day's
# readings (and keeps working after a restart: see verse.StudyButton).

def _pretty_date(d) -> str:
    return d.strftime("%A, ") + d.strftime("%d").lstrip("0") + d.strftime(" %B %Y")


def readings_embed(d) -> "discord.Embed | None":
    import bcp_lookup as _bcp
    offices = {p: _bcp.bcp_for_date(d, p) for p in ("morning", "evening")}
    morning = offices["morning"]
    if not morning.get("found"):
        return None
    heading = morning.get("label", "")
    if morning.get("section_title") and morning["section_title"] != heading:
        heading = f"{heading} — {morning['section_title']}" if heading else morning["section_title"]
    embed = discord.Embed(title=f"📅 Readings for {_pretty_date(d)}", description=f"**{heading}**" if heading else None,
                          color=discord.Color.dark_blue())
    for period, info in offices.items():
        lines = []
        psalms = (info.get("psalter") or {}).get("psalms") or []
        if psalms:
            lines.append(("Psalm " if len(psalms) == 1 else "Psalms ") + ", ".join(psalms))
        for les in info.get("lessons", []):
            lines.append(f"{les['slot']}: {les['ref']}")
        name = "🌅 Morning Prayer" if period == "morning" else "🌙 Evening Prayer"
        embed.add_field(name=name, value="\n".join(lines) or "—", inline=False)
    collect = morning.get("collect") or {}
    if collect.get("name"):
        # Weekdays use the Sunday's collect, which the data just calls "Sunday"
        week = (morning.get("section_title") or "").removeprefix("The Week of ").strip()
        generic = collect["name"] in ("Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday")
        name = f"the collect of {week}" if generic and week else collect["name"]
        embed.add_field(name="📿 Collect", value=f"{name[0].upper()}{name[1:]} (`!bcp collect`)", inline=False)
    embed.set_footer(text="Book of Common Prayer (Canada 1962) · full texts: !bcp morning · !bcp evening · !bcp collect")
    return embed


class ReadingsButton(discord.ui.DynamicItem[discord.ui.Button],
                     template=r"readings:(?P<date>\d{4}-\d{2}-\d{2})"):
    def __init__(self, date_iso: str):
        super().__init__(discord.ui.Button(label="Today's readings", emoji="📅", style=discord.ButtonStyle.secondary,
                                           custom_id=f"readings:{date_iso}"))
        self.date_iso = date_iso

    @classmethod
    async def from_custom_id(cls, interaction, item, match):
        return cls(match["date"])

    async def callback(self, interaction: discord.Interaction):
        import datetime as _dt
        embed = await asyncio.to_thread(readings_embed, _dt.date.fromisoformat(self.date_iso))
        if embed is None:
            await interaction.response.send_message("⚠️ I couldn't find the readings for that day.", ephemeral=True)
            return
        await interaction.response.send_message(embed=embed, ephemeral=True)


bot.add_dynamic_items(ReadingsButton)


def readings_view(d) -> discord.ui.View:
    view = discord.ui.View(timeout=None)      # holds a DynamicItem: must never time out
    view.add_item(ReadingsButton(d.isoformat()))
    return view


# ── !prayer — random devotional prayer from the BCP ──────────────────────────

_PRAYERS_DATA: dict | None = None

def _load_prayers() -> dict | None:
    global _PRAYERS_DATA
    if _PRAYERS_DATA is not None:
        return _PRAYERS_DATA
    from pathlib import Path as _P
    for p in [ROOT / "data" / "bcp_prayers.json",
              _P("data") / "bcp_prayers.json"]:
        if p.exists():
            try:
                _PRAYERS_DATA = json.loads(p.read_text(encoding="utf-8"))
                return _PRAYERS_DATA
            except Exception:
                continue
    return None


async def _send_random_prayer(ctx_or_channel):
    data = _load_prayers()
    if not data or not data.get("prayers"):
        await ctx_or_channel.send("⚠️ Prayer data not loaded.")
        return
    prayer = random.choice(data["prayers"])
    embed = discord.Embed(
        title=f"📿 {prayer['title']}",
        description=prayer["text"],
        color=discord.Color.dark_purple(),
    )
    sec = prayer.get("section", "")
    footer = "Book of Common Prayer 1662"
    if sec and sec not in prayer["title"]:
        footer = f"{sec} · {footer}"
    embed.set_footer(text=footer)
    await ctx_or_channel.send(embed=embed)


# ── !bcp dispatcher and alias commands ───────────────────────────────────────

def _bcp_parse_period(tok: str) -> str | None:
    """Map a period token to 'morning'/'evening' or None if unrecognised."""
    t = tok.lower()
    if t in ("morning", "mp", "matins"):
        return "morning"
    if t in ("evening", "ep", "vespers", "evensong"):
        return "evening"
    return None


@bot.command(name="bcp")
async def cmd_bcp(ctx, *, args: str = ""):
    """BCP daily office (Canadian 1962 lectionary + Coverdale Psalter).

    Usage:
      !bcp                — full office for today, time-appropriate
      !bcp morning        — full Morning Prayer office (also mp/matins)
      !bcp evening        — full Evening Prayer office (also ep/evensong)
      !bcp 2026-12-25     — full office for a specific date
      !bcp 1 / !bcp 2     — first or second lesson, time-appropriate
      !bcp psalm          — psalm(s) for the current period
      !bcp psalm evening  — psalm(s) for that period (a date may follow)
      !bcp collect        — the Collect of the Day
      !bcp prayer         — random devotional prayer (also !prayer)
    (!mp, !ep, !psalm and !collect were folded into this on 2026-11-08.)
    """
    parts = args.strip().split()
    if not parts:
        # Full office, current period
        d = _parse_today_date("")
        async with ctx.typing():
            await _send_bcp(ctx, d, _bcp_period_for_now())
        return

    sub = parts[0].lower()
    rest = parts[1:]

    # !bcp prayer
    if sub == "prayer":
        async with ctx.typing():
            await _send_random_prayer(ctx)
        return

    # !bcp collect [date]
    if sub == "collect":
        date_raw = " ".join(rest)
        d = _parse_today_date(date_raw)
        if d is None:
            await ctx.send(f"⚠️ Couldn't parse `{date_raw}` as a date.")
            return
        async with ctx.typing():
            await _send_bcp_collect(ctx, d)
        return

    # !bcp 1 / !bcp 2  — single lesson, current period
    if sub in ("1", "first"):
        date_raw = " ".join(rest)
        d = _parse_today_date(date_raw)
        if d is None:
            await ctx.send(f"⚠️ Couldn't parse `{date_raw}`.")
            return
        async with ctx.typing():
            await _send_bcp_lessons(ctx, d, _bcp_period_for_now(), "first")
        return
    if sub in ("2", "second"):
        date_raw = " ".join(rest)
        d = _parse_today_date(date_raw)
        if d is None:
            await ctx.send(f"⚠️ Couldn't parse `{date_raw}`.")
            return
        async with ctx.typing():
            await _send_bcp_lessons(ctx, d, _bcp_period_for_now(), "second")
        return

    # !bcp psalm [mp|ep] [date]
    if sub in ("psalm", "psalms", "psalter"):
        period = _bcp_period_for_now()
        date_raw = ""
        if rest:
            maybe_period = _bcp_parse_period(rest[0])
            if maybe_period is not None:
                period = maybe_period
                date_raw = " ".join(rest[1:])
            else:
                date_raw = " ".join(rest)
        if re.fullmatch(r"\d{1,3}", date_raw.strip()):     # "!bcp psalm 23": a psalm, not a date
            n = date_raw.strip()
            await ctx.send(f"`!bcp psalm` gives the psalms appointed for today. For Psalm {n} itself: "
                           f"`!verse Psalm {n}`, sung in metre `!metrical {n}`, or chanted in Latin `!chant psalm {n}`.")
            return
        d = _parse_today_date(date_raw)
        if d is None:
            shown = date_raw.replace("`", "'")[:40]
            await ctx.send(f"⚠️ Couldn't parse `{shown}` as a date. Try `YYYY-MM-DD` or `MM-DD`.")
            return
        async with ctx.typing():
            await _send_bcp_psalm(ctx, d, period)
        return

    # !bcp morning / !bcp ep [date]  — the full office for that period
    period_only = _bcp_parse_period(sub)
    if period_only is not None:
        date_raw = " ".join(rest)
        d = _parse_today_date(date_raw)
        if d is None:
            await ctx.send(f"⚠️ Couldn't parse `{date_raw}` as a date. Try `YYYY-MM-DD` or `MM-DD`.")
            return
        async with ctx.typing():
            await _send_bcp(ctx, d, period_only)
        return

    # Fallback: treat the whole arg as a date for the full office
    date_raw = args.strip()
    d = _parse_today_date(date_raw)
    if d is None:
        shown = sub.replace("`", "'")[:40]
        await ctx.send(f"⚠️ I don't know `{shown}`. Try `!bcp morning`, `!bcp evening`, `!bcp psalm`, "
                       "`!bcp collect`, or a date like `!bcp 12-25`; `!help bcp` has the rest.")
        return
    async with ctx.typing():
        await _send_bcp(ctx, d, _bcp_period_for_now())


@bot.tree.command(name="bcp", description="Book of Common Prayer daily office: psalms, lessons and collect")
@app_commands.describe(
    part="The whole office (default), or just the psalms or the collect",
    period="Morning or evening (default: by time of day)",
    date="Optional date: YYYY-MM-DD or MM-DD; blank for today",
)
@app_commands.choices(
    part=[app_commands.Choice(name="Whole office", value="office"),
          app_commands.Choice(name="Psalms", value="psalm"),
          app_commands.Choice(name="Collect", value="collect")],
    period=[app_commands.Choice(name="Morning", value="morning"),
            app_commands.Choice(name="Evening", value="evening")],
)
async def bcp_slash(interaction: discord.Interaction, part: str = "", period: str = "", date: str = ""):
    """(Took over /mp, /ep, /psalm and /collect on 2026-11-08.)"""
    await interaction.response.defer()
    ctx = await bot.get_context(interaction)
    if part == "collect":
        args = f"collect {date}"
    elif part == "psalm":
        args = f"psalm {period or _bcp_period_for_now()} {date}"
    else:
        args = f"{period or _bcp_period_for_now()} {date}"
    await cmd_bcp(ctx, args=args.strip())


# ── !prayer ──────────────────────────────────────────────────────────────────

@bot.command(name="prayer")
async def cmd_prayer(ctx, *, name: str = ""):
    """A traditional prayer by name, or a random devotional prayer from the BCP.
    Usage: !prayer st michael   — a prayer by name, in English and Latin
           !prayer list         — the prayers I have
           !prayer              — a random Prayer Book prayer"""
    if name.strip():
        await prayers.send_prayer(ctx, name)
        return
    async with ctx.typing():
        await _send_random_prayer(ctx)
