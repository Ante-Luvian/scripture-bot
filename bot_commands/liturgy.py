"""
!today liturgical calendar, !bcp daily office, !prayer, and the office alias commands.
"""
import asyncio
import discord
import json
import random
import re
from discord import app_commands
from core import (
    bot,
    lookup,
)
from core import ROOT

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
    for fmt in ("%m-%d", "%m/%d"):
        try:
            md = _dt.datetime.strptime(raw, fmt)
            return _dt.date(today.year, md.month, md.day)
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


@bot.command(name="today", aliases=["calendar", "liturgy"])
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

    traditions = _TODAY_GROUPS[key]
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
    traditions = _TODAY_GROUPS[key]
    if key == "all":
        title_label = "All Traditions"
    elif key == "christian":
        title_label = "Christian"
    else:
        _, full_label = _TODAY_META.get(traditions[0], ("", key.title()))
        title_label = full_label
    await _send_today(interaction.channel, d, traditions, title_label)


# ── !bcp — Book of Common Prayer daily office ────────────────────────────────

def _bcp_normalise_ref(ref: str) -> str:
    """
    Normalise lectionary refs into a form lookup.get_verse can handle.

    Examples:
        "Isa. 11:1-9"            → "Isaiah 11:1-9"
        "Rom. 8:18-end"          → "Romans 8:18-end" (handled by lookup)
        "1 Cor. 12:27-13 end"    → "1 Corinthians 12:27-13:end"
        "Eze. 11:14-20"          → "Ezekiel 11:14-20"
        "Wis. 1:1-7"             → "Wisdom 1:1-7"
        "Acts 18:24-19:7"        → "Acts 18:24-19:7"
    """
    s = ref.strip()
    # Expand common abbreviations
    expansions = [
        ("Gen.",   "Genesis"),    ("Ex.",    "Exodus"),
        ("Exod.",  "Exodus"),     ("Lev.",   "Leviticus"),
        ("Num.",   "Numbers"),    ("Deut.",  "Deuteronomy"),
        ("Josh.",  "Joshua"),     ("Judg.",  "Judges"),
        ("1 Sam.", "1 Samuel"),   ("2 Sam.", "2 Samuel"),
        ("1 Kings","1 Kings"),    ("2 Kings","2 Kings"),
        ("1 Chr.", "1 Chronicles"),("2 Chr.","2 Chronicles"),
        ("Neh.",   "Nehemiah"),   ("Esth.",  "Esther"),
        ("Ps.",    "Psalm"),      ("Prov.",  "Proverbs"),
        ("Eccl.",  "Ecclesiastes"),("Cant.", "Song of Solomon"),
        ("Isa.",   "Isaiah"),     ("Isa ",   "Isaiah "),
        ("Jer.",   "Jeremiah"),   ("Lam.",   "Lamentations"),
        ("Eze.",   "Ezekiel"),    ("Ezek.",  "Ezekiel"),
        ("Dan.",   "Daniel"),     ("Hos.",   "Hosea"),
        ("Joel ",  "Joel "),      ("Amos ",  "Amos "),
        ("Obad.",  "Obadiah"),    ("Jon.",   "Jonah"),
        ("Mic.",   "Micah"),      ("Nah.",   "Nahum"),
        ("Hab.",   "Habakkuk"),   ("Zeph.",  "Zephaniah"),
        ("Hag.",   "Haggai"),     ("Zech.",  "Zechariah"),
        ("Mal.",   "Malachi"),
        # Apocrypha
        ("Tob.",   "Tobit"),      ("Jud.",   "Judith"),
        ("Wis.",   "Wisdom"),     ("Ecclus.","Sirach"),
        ("Sir.",   "Sirach"),     ("Bar.",   "Baruch"),
        ("1 Macc.","1 Maccabees"),("2 Macc.","2 Maccabees"),
        # NT
        ("Mt.",    "Matthew"),    ("Mk.",    "Mark"),
        ("Lk.",    "Luke"),       ("Jn.",    "John"),
        ("Rom.",   "Romans"),     ("1 Cor.", "1 Corinthians"),
        ("2 Cor.", "2 Corinthians"),("Gal.",  "Galatians"),
        ("Eph.",   "Ephesians"),  ("Phil.",  "Philippians"),
        ("Col.",   "Colossians"), ("1 Thes.","1 Thessalonians"),
        ("1 Thess.","1 Thessalonians"),("2 Thess.","2 Thessalonians"),
        ("1 Tim.", "1 Timothy"),  ("2 Tim.", "2 Timothy"),
        ("Tit.",   "Titus"),      ("Philem.","Philemon"),
        ("Heb.",   "Hebrews"),    ("Jas.",   "James"),
        ("1 Pet.", "1 Peter"),    ("2 Pet.", "2 Peter"),
        ("1 Jn.",  "1 John"),     ("2 Jn.",  "2 John"),
        ("3 Jn.",  "3 John"),     ("Rev.",   "Revelation"),
    ]
    for short, long in expansions:
        if s.startswith(short):
            s = long + s[len(short):]
            break

    # Convert "X-Y end" (multi-chapter range) to "X-Y:end"
    s = re.sub(r"(\d+)\s+end\b", r"\1:end", s)
    return s


def _bcp_fetch_text(ref: str) -> tuple[str, str]:
    """
    Look up a lectionary reference and return (display_ref, text).

    Handles BCP lectionary notation that the standard `lookup.get_verse`
    doesn't:
      • "Rom. 8:18-end"      → resolve "end" to the chapter's actual last verse
      • "1 Cor. 12:27-13 end" → cross-chapter to end of chapter 13
      • "Acts 18:24-19:7"    → ordinary cross-chapter (lookup handles natively)
    """
    norm = _bcp_normalise_ref(ref)
    import re as _re

    def _last_verse(book: str, chap: int) -> int | None:
        """Return the highest verse number in (book, chap), or None if unknown."""
        try:
            corpus, canon = lookup._resolve_book(book)
            if canon is None:
                return None
            chap_data = lookup._data[corpus].get(canon, {}).get(str(chap), {})
            nums = [int(k) for k in chap_data if k.isdigit()]
            return max(nums) if nums else None
        except Exception:
            return None

    # Try "Book C:V-end"
    m = _re.match(r"^(.+?)\s+(\d+):(\d+)\s*-\s*end$", norm)
    if m:
        book = m.group(1).strip()
        c, v = int(m.group(2)), int(m.group(3))
        last = _last_verse(book, c) or 200
        try:
            result = lookup.get_verse_range(book, c, v, c, last)
            if result.get("found"):
                return result.get("reference", ref), result.get("text", "")
        except Exception:
            pass

    # Try "Book C:V-C2:end"  (multi-chapter to end of chapter)
    m = _re.match(r"^(.+?)\s+(\d+):(\d+)\s*-\s*(\d+):end$", norm)
    if m:
        book = m.group(1).strip()
        c1, v1, c2 = int(m.group(2)), int(m.group(3)), int(m.group(4))
        last = _last_verse(book, c2) or 200
        try:
            result = lookup.get_verse_range(book, c1, v1, c2, last)
            if result.get("found"):
                return result.get("reference", ref), result.get("text", "")
        except Exception:
            pass

    # Otherwise, hand off to the standard verse lookup
    try:
        result = lookup.get_verse(norm)
        if result.get("found"):
            return result.get("reference", ref), result.get("text", "")
    except Exception:
        pass

    return ref, "*[not available]*"


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
      !bcp morning        — full Morning Prayer office (alias: mp/matins)
      !bcp evening        — full Evening Prayer office (alias: ep/vespers)
      !bcp 2026-12-25     — full office for a specific date
      !bcp mp             — both lessons for Morning Prayer (alias: !mp)
      !bcp ep             — both lessons for Evening Prayer (alias: !ep)
      !bcp 1 / !bcp 2     — first or second lesson, time-appropriate
      !bcp psalm          — psalm(s) for the current period (alias: !psalm)
      !bcp psalm mp/ep    — psalm(s) for that period
      !bcp collect        — the Collect of the Day (alias: !collect)
      !bcp prayer         — random devotional prayer (alias: !prayer)
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
        d = _parse_today_date(date_raw)
        if d is None:
            await ctx.send(f"⚠️ Couldn't parse `{date_raw}`.")
            return
        async with ctx.typing():
            await _send_bcp_psalm(ctx, d, period)
        return

    # !bcp mp / !bcp ep  — both lessons for that period
    period_only = _bcp_parse_period(sub)
    if period_only is not None and (not rest or _parse_today_date(" ".join(rest)) is not None):
        # If a date follows, parse it; otherwise today
        date_raw = " ".join(rest)
        d = _parse_today_date(date_raw)
        if d is None:
            await ctx.send(f"⚠️ Couldn't parse `{date_raw}`.")
            return
        # If they said "mp" or "ep" specifically (short form), give just the lessons;
        # if they said "morning"/"evening", give the full office.
        if sub in ("mp", "ep"):
            async with ctx.typing():
                await _send_bcp_lessons(ctx, d, period_only, "both")
        else:
            async with ctx.typing():
                await _send_bcp(ctx, d, period_only)
        return

    # Fallback: treat the whole arg as a date for the full office
    date_raw = args.strip()
    d = _parse_today_date(date_raw)
    if d is None:
        await ctx.send(f"⚠️ Unknown subcommand `{sub}`. See `!help bcp`.")
        return
    async with ctx.typing():
        await _send_bcp(ctx, d, _bcp_period_for_now())


@bot.tree.command(name="bcp", description="BCP daily office: psalms, lessons, and collect")
@app_commands.describe(
    period='"morning" or "evening" (defaults to time of day)',
    date='Optional date: YYYY-MM-DD or MM-DD; blank for today',
)
async def bcp_slash(interaction: discord.Interaction, period: str = "", date: str = ""):
    await interaction.response.defer()
    p = _bcp_parse_period(period) if period else None
    if p is None:
        p = _bcp_period_for_now()
    d = _parse_today_date(date)
    if d is None:
        await interaction.followup.send(f"⚠️ Couldn't parse `{date}`.")
        return
    await _send_bcp(interaction.channel, d, p)


# ── Alias commands ───────────────────────────────────────────────────────────

@bot.command(name="prayer")
async def cmd_prayer(ctx):
    """Random devotional prayer or collect from the BCP."""
    async with ctx.typing():
        await _send_random_prayer(ctx)


@bot.command(name="collect")
async def cmd_collect(ctx, *, date_raw: str = ""):
    """The Collect of the Day. Optional date arg."""
    d = _parse_today_date(date_raw)
    if d is None:
        await ctx.send(f"⚠️ Couldn't parse `{date_raw}`.")
        return
    async with ctx.typing():
        await _send_bcp_collect(ctx, d)


@bot.command(name="mp", aliases=["matins"])
async def cmd_mp(ctx, *, date_raw: str = ""):
    """Both lessons for today's Morning Prayer."""
    d = _parse_today_date(date_raw)
    if d is None:
        await ctx.send(f"⚠️ Couldn't parse `{date_raw}`.")
        return
    async with ctx.typing():
        await _send_bcp_lessons(ctx, d, "morning", "both")


@bot.command(name="ep", aliases=["evensong", "vespers"])
async def cmd_ep(ctx, *, date_raw: str = ""):
    """Both lessons for today's Evening Prayer."""
    d = _parse_today_date(date_raw)
    if d is None:
        await ctx.send(f"⚠️ Couldn't parse `{date_raw}`.")
        return
    async with ctx.typing():
        await _send_bcp_lessons(ctx, d, "evening", "both")


@bot.command(name="psalm", aliases=["psalms"])
async def cmd_psalm(ctx, *, args: str = ""):
    """Today's appointed Psalm(s). Optional `mp`/`ep` to override the period.

    Usage:
      !psalm           — current period
      !psalm mp        — Morning Prayer psalms
      !psalm ep        — Evening Prayer psalms
      !psalm mp 12-25  — Morning Prayer psalms for Dec 25
    """
    parts = args.strip().split()
    period = _bcp_period_for_now()
    date_raw = ""
    if parts:
        maybe_period = _bcp_parse_period(parts[0])
        if maybe_period is not None:
            period = maybe_period
            date_raw = " ".join(parts[1:])
        else:
            date_raw = args.strip()
    d = _parse_today_date(date_raw)
    if d is None:
        await ctx.send(f"⚠️ Couldn't parse `{date_raw}`.")
        return
    async with ctx.typing():
        await _send_bcp_psalm(ctx, d, period)
