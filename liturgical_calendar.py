"""
liturgical_calendar.py
──────────────────────
Daily liturgical / calendar lookups across five traditions:

  • Catholic   — scraped from universalis.com (General Calendar)
  • Anglican   — bundled data/anglican_calendar.json (Common Worship)
                 + Python computus for movable feasts (Easter & dependents)
  • Orthodox   — orthocal.info REST API
  • Jewish     — hebcal.com REST API
  • Islamic    — api.aladhan.com REST API

All entry-points are synchronous; callers in bot.py wrap them in
`loop.run_in_executor(None, …)` to keep the event loop free.

The five tradition helpers each return a dict with shape:
    {"found": bool, "summary": str, "details": str, "source": str}
or {"found": False, "error": str}

"summary" is a single short line (the main observance/season).
"details" can be a multi-line string with secondary commemorations or
notes; callers truncate as needed.
"""

from __future__ import annotations

import datetime
import html as html_mod
import json
import re
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Optional

# ── Shared HTTP helper ────────────────────────────────────────────────────────

_USER_AGENT = "ScriptureBot/1.0 (calendar lookup; non-commercial)"


def _http_get(url: str, timeout: int = 15) -> Optional[bytes]:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read()
    except Exception:
        return None


def _http_get_json(url: str, timeout: int = 15) -> Optional[dict | list]:
    raw = _http_get(url, timeout=timeout)
    if raw is None:
        return None
    try:
        return json.loads(raw.decode("utf-8"))
    except Exception:
        return None


# ── Anglican: bundled Common Worship calendar + computus ─────────────────────

_ANGLICAN_DATA: Optional[dict] = None


def _load_anglican() -> Optional[dict]:
    global _ANGLICAN_DATA
    if _ANGLICAN_DATA is not None:
        return _ANGLICAN_DATA
    for p in [
        Path(__file__).parent / "data" / "anglican_calendar.json",
        Path("data") / "anglican_calendar.json",
    ]:
        if p.exists():
            try:
                _ANGLICAN_DATA = json.loads(p.read_text(encoding="utf-8"))
                return _ANGLICAN_DATA
            except Exception:
                continue
    return None


def _easter_sunday(year: int) -> datetime.date:
    """Anonymous Gregorian (computus) — exact for years 1583 onward."""
    a = year % 19
    b = year // 100
    c = year % 100
    d = b // 4
    e = b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i = c // 4
    k = c % 4
    L = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * L) // 451
    month = (h + L - 7 * m + 114) // 31
    day = ((h + L - 7 * m + 114) % 31) + 1
    return datetime.date(year, month, day)


def _advent_sunday(year: int) -> datetime.date:
    """The Sunday nearest 30 November (also the start of the liturgical year)."""
    nov30 = datetime.date(year, 11, 30)
    # nov30.weekday(): Mon=0 ... Sun=6
    delta = nov30.weekday() + 1  # Sun=0 in our offset
    if delta == 7:
        delta = 0
    nearest = nov30 - datetime.timedelta(days=delta)
    if abs((nov30 - nearest).days) > 3:
        nearest = nearest + datetime.timedelta(days=7)
    return nearest


def _anglican_movable(d: datetime.date) -> Optional[tuple[str, str]]:
    """
    Return (rank, title) if `d` is one of the named movable feasts/seasons.
    rank is one of P/F/L/C (matching the JSON ranks).
    """
    year = d.year
    easter = _easter_sunday(year)

    # Anchor days relative to Easter
    deltas: dict[int, tuple[str, str]] = {
        -46: ("P", "Ash Wednesday"),
        -7:  ("P", "Palm Sunday"),
        -3:  ("P", "Maundy Thursday"),
        -2:  ("P", "Good Friday"),
        -1:  ("P", "Holy Saturday (Easter Eve)"),
        0:   ("P", "Easter Day"),
        39:  ("P", "Ascension Day"),
        49:  ("P", "The Day of Pentecost (Whitsunday)"),
        56:  ("P", "Trinity Sunday"),
        60:  ("F", "Corpus Christi (The Day of Thanksgiving for the Institution of Holy Communion)"),
    }
    offset = (d - easter).days
    if offset in deltas:
        return deltas[offset]

    # Sundays of Lent (1st–5th)
    for i in range(1, 6):
        sun = easter - datetime.timedelta(days=7 * (6 - i))
        if d == sun:
            ord_word = {1: "First", 2: "Second", 3: "Third", 4: "Fourth", 5: "Fifth"}[i]
            return ("F", f"The {ord_word} Sunday of Lent")

    # Sundays of Easter (2nd–7th) — 7th is the Sunday after Ascension
    for i in range(2, 8):
        sun = easter + datetime.timedelta(days=7 * (i - 1))
        if d == sun:
            ord_word = {2: "Second", 3: "Third", 4: "Fourth", 5: "Fifth",
                        6: "Sixth", 7: "Seventh"}[i]
            return ("F", f"The {ord_word} Sunday of Easter")

    # Easter Octave — Mon–Sat after Easter Day (Easter Week)
    for i in range(1, 7):
        day_in_week = easter + datetime.timedelta(days=i)
        if d == day_in_week:
            name = ["Monday", "Tuesday", "Wednesday", "Thursday",
                    "Friday", "Saturday"][i - 1]
            return ("F", f"{name} of Easter Week")

    # Days between Ascension and Pentecost (a traditional week of prayer)
    # Ascension = Easter + 39 days; Pentecost = Easter + 49 days
    if 40 <= (d - easter).days <= 48:
        offset = (d - easter).days
        # Saturday before Pentecost is "Eve of Pentecost"
        if offset == 48:
            return ("C", "Eve of Pentecost (Saturday after Ascension Day)")
        return ("C", "Day in the Octave of the Ascension")

    # Advent Sundays 1–4 (Advent Sunday is the start of the liturgical year)
    advent1 = _advent_sunday(year)
    for i in range(0, 4):
        sun = advent1 + datetime.timedelta(days=7 * i)
        if d == sun:
            ord_word = {0: "First", 1: "Second", 2: "Third", 3: "Fourth"}[i]
            return ("P", f"The {ord_word} Sunday of Advent")

    # Christ the King — Sunday before Advent Sunday
    christ_king = advent1 - datetime.timedelta(days=7)
    if d == christ_king:
        return ("F", "Christ the King (The Sunday Next before Advent)")

    return None


_RANK_LABELS = {
    "P": "Principal Feast",
    "F": "Festival",
    "L": "Lesser Festival",
    "C": "Commemoration",
}


def anglican_today(d: datetime.date) -> dict:
    """Lookup the Common Worship calendar for date `d`."""
    data = _load_anglican()
    if data is None:
        return {"found": False, "error": "Anglican calendar data not loaded."}

    key = f"{d.month:02d}-{d.day:02d}"

    entries: list[tuple[str, str]] = []
    movable = _anglican_movable(d)
    if movable is not None:
        entries.append(movable)
    for e in data.get("fixed", {}).get(key, []):
        if isinstance(e, list) and len(e) == 2:
            entries.append((e[0], e[1]))

    if not entries:
        return {
            "found": True,
            "summary": "Feria (no special observance)",
            "details": "",
            "source": "Common Worship",
        }

    # Order by rank: P > F > L > C
    rank_order = {"P": 0, "F": 1, "L": 2, "C": 3}
    entries.sort(key=lambda x: rank_order.get(x[0], 9))

    rank, title = entries[0]
    summary = f"**{title}** _({_RANK_LABELS.get(rank, rank)})_"

    detail_lines = []
    for r, t in entries[1:]:
        detail_lines.append(f"• {t} _({_RANK_LABELS.get(r, r)})_")
    details = "\n".join(detail_lines)

    return {
        "found": True,
        "summary": summary,
        "details": details,
        "source": "Common Worship",
    }


# ── Catholic: scrape universalis.com ──────────────────────────────────────────

def catholic_today(d: datetime.date) -> dict:
    """Fetch today's celebration from universalis.com.

    Universalis URL patterns:
      • https://universalis.com/today.htm                              (today)
      • https://universalis.com/YYYYMMDD/today.htm                     (any date)
    """
    today = datetime.date.today()
    if d == today:
        url = "https://universalis.com/today.htm"
    else:
        url = f"https://universalis.com/{d.year:04d}{d.month:02d}{d.day:02d}/today.htm"

    raw = _http_get(url)
    if raw is None:
        return {"found": False, "error": "Could not reach universalis.com"}

    try:
        html = raw.decode("utf-8", errors="replace")
    except Exception:
        return {"found": False, "error": "Failed to decode Universalis response"}

    # Strip tags → plain text we can scan line by line.
    text = re.sub(r"<(script|style)\b[^>]*>.*?</\1>", " ",
                  html, flags=re.I | re.S)
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.I)
    text = re.sub(r"</p\s*>|</div\s*>|</li\s*>|</h[1-6]\s*>", "\n",
                  text, flags=re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = html_mod.unescape(text)
    # Collapse whitespace within lines, preserve line breaks
    lines = [re.sub(r"\s+", " ", line).strip() for line in text.splitlines()]
    lines = [line for line in lines if line]

    # Universalis prints the date headline near the top, e.g.:
    #   "Sunday 24 May 2026 (other days)  Pentecost"
    # or split across two adjacent items / lines.  Build a forgiving matcher.
    weekday = d.strftime("%A")
    month = d.strftime("%B")
    day_num = d.day
    year = d.year

    # Regex matching the date line; the feast follows it directly.
    # Allow inner spaces inside the (other days) parenthetical, since Universalis
    # actually renders it as "( other days )" with spaces.
    date_pat = re.compile(
        rf"^{weekday}\s+0?{day_num}\s+{month}\s+{year}\b\s*"
        rf"(?:\(\s*other\s+days\s*\))?\s*(.*)$",
        re.I,
    )

    feast = ""
    for i, line in enumerate(lines):
        m = date_pat.match(line)
        if not m:
            continue
        # Feast may be on same line (after date) OR on a following short line.
        candidate = m.group(1).strip(" ·-—")
        if not candidate:
            # Look at the next few short, non-nav lines
            for follow in lines[i + 1 : i + 5]:
                if not follow:
                    continue
                if _looks_like_nav(follow):
                    continue
                candidate = follow
                break
        if candidate and not _looks_like_nav(candidate):
            feast = candidate.strip(" ·-—")
            break

    # Fallback: flatten all text and scan for the date pattern there.
    if not feast:
        flat = " ".join(lines)
        m = re.search(
            rf"{weekday}\s+0?{day_num}\s+{month}\s+{year}\b\s*"
            rf"(?:\(other\s+days\))?\s*[·•\-—:]?\s*([^·•\n]+?)(?:\s+[·•]|$)",
            flat, re.I,
        )
        if m:
            cand = m.group(1).strip(" ·-—")
            if cand and not _looks_like_nav(cand):
                feast = cand

    # Liturgical colour, if present
    colour = ""
    m_col = re.search(r"Liturgical\s+Colour:\s*([A-Za-z][A-Za-z /]+?)[.\n]",
                      "\n".join(lines), flags=re.I)
    if m_col:
        colour = m_col.group(1).strip()

    if not feast:
        return {"found": False, "error": "Could not parse Universalis page"}

    details = ""
    if colour:
        details = f"Liturgical colour: {colour}"

    return {
        "found": True,
        "summary": feast,
        "details": details,
        "source": "universalis.com (General Calendar)",
    }


def _looks_like_nav(s: str) -> bool:
    """True if the line looks like Universalis navigation rather than content."""
    s_low = s.lower().strip()
    if len(s_low) < 2:
        return True
    # Strip surrounding parens and collapse inner whitespace so
    # "( other days )" → "other days"
    normalised = s_low.strip("() \t")
    normalised = re.sub(r"\s+", " ", normalised)
    nav_terms = {
        "today", "about today", "readings at mass", "office of readings",
        "morning prayer", "evening prayer", "night prayer", "terce", "sext",
        "none", "mid-morning prayer", "midday prayer", "afternoon prayer",
        "yearly calendar", "spoken word", "donate", "tweet",
        "show qr code", "listen to the podcast!", "podcast", "universalis",
        "apps & programs", "e-books", "email service", "free services",
        "about universalis", "blog", "other days",
    }
    if normalised in nav_terms or s_low in nav_terms:
        return True
    # Lines that are mostly dot/middot separators are nav menus
    if s.count("·") >= 3 and len(s) < 200:
        return True
    return False


# ── Orthodox: orthocal.info ──────────────────────────────────────────────────

def orthodox_today(d: datetime.date) -> dict:
    """Fetch today's commemorations from orthocal.info."""
    url = f"https://orthocal.info/api/gregorian/{d.year}/{d.month}/{d.day}/"
    data = _http_get_json(url)
    if not isinstance(data, dict):
        return {"found": False, "error": "Could not reach orthocal.info"}

    title = (data.get("summary_title") or "").strip()
    if not title:
        title = (data.get("titles") or [""])[0]

    saints = data.get("saints") or []
    feasts = data.get("feasts") or []

    # Build a secondary line of saints (excluding what's already in the title)
    detail_items = []
    title_lower = title.lower()
    for s in saints:
        if s and s.lower() not in title_lower:
            detail_items.append(s)
    for f in feasts:
        if f and f.lower() not in title_lower:
            detail_items.append(f)

    # Fast info
    fast_desc = (data.get("fast_level_desc") or "").strip()
    fast_exc  = (data.get("fast_exception_desc") or "").strip()
    fast_line = ""
    if fast_desc:
        if fast_exc and fast_exc.lower() not in ("no fast", "none"):
            fast_line = f"Fast: {fast_desc} — {fast_exc}"
        else:
            fast_line = f"Fast: {fast_desc}"

    details_parts = []
    if detail_items:
        # Cap to avoid runaway length; one bullet per item
        for item in detail_items[:6]:
            details_parts.append(f"• {item}")
        if len(detail_items) > 6:
            details_parts.append(f"…and {len(detail_items) - 6} more")
    if fast_line:
        details_parts.append(fast_line)

    if not title and not details_parts:
        return {"found": False, "error": "No data returned from orthocal.info"}

    return {
        "found": True,
        "summary": title or "(no headline feast)",
        "details": "\n".join(details_parts),
        "source": "orthocal.info",
    }


# ── Jewish: hebcal.com ───────────────────────────────────────────────────────

def jewish_today(d: datetime.date) -> dict:
    """Fetch today's Hebrew date and events from hebcal.com."""
    url = (
        "https://www.hebcal.com/converter?cfg=json"
        f"&gy={d.year}&gm={d.month}&gd={d.day}&g2h=1"
    )
    data = _http_get_json(url)
    if not isinstance(data, dict):
        return {"found": False, "error": "Could not reach hebcal.com"}

    # Date description, e.g. "3rd of Sivan, 5786"
    hd = data.get("hd")
    hm = data.get("hm")
    hy = data.get("hy")
    hebrew = data.get("hebrew", "")
    if hd is not None and hm and hy:
        suffix = "th"
        if 10 <= hd <= 20:
            suffix = "th"
        elif hd % 10 == 1:
            suffix = "st"
        elif hd % 10 == 2:
            suffix = "nd"
        elif hd % 10 == 3:
            suffix = "rd"
        date_str = f"{hd}{suffix} of {hm}, {hy}"
    else:
        date_str = hebrew or "—"

    events = data.get("events") or []
    # First event is the "headline"; rest go in details
    if events:
        summary = f"{date_str} — {events[0]}"
    else:
        summary = date_str

    details_lines = []
    for e in events[1:]:
        details_lines.append(f"• {e}")
    if hebrew and hebrew not in summary:
        details_lines.append(f"Hebrew: {hebrew}")

    return {
        "found": True,
        "summary": summary,
        "details": "\n".join(details_lines),
        "source": "hebcal.com",
    }


# ── Islamic: api.aladhan.com ─────────────────────────────────────────────────

def islamic_today(d: datetime.date) -> dict:
    """Fetch today's Hijri date and holidays from api.aladhan.com."""
    # Aladhan expects DD-MM-YYYY
    date_str = f"{d.day:02d}-{d.month:02d}-{d.year:04d}"
    url = f"https://api.aladhan.com/v1/gToH?date={date_str}"
    data = _http_get_json(url)
    if not isinstance(data, dict):
        return {"found": False, "error": "Could not reach api.aladhan.com"}

    if data.get("code") != 200:
        return {"found": False, "error": f"Aladhan returned status {data.get('code')}"}

    hijri = (data.get("data") or {}).get("hijri") or {}
    day_num = hijri.get("day", "")
    month_obj = hijri.get("month") or {}
    month_en = month_obj.get("en", "")
    year_num = hijri.get("year", "")
    holidays = hijri.get("holidays") or []

    if day_num and month_en and year_num:
        date_str_out = f"{day_num} {month_en} {year_num} AH"
    else:
        date_str_out = hijri.get("date", "")

    if holidays:
        summary = f"{date_str_out} — {holidays[0]}"
        extras = holidays[1:]
    else:
        summary = date_str_out or "—"
        extras = []

    details_lines = [f"• {h}" for h in extras]

    return {
        "found": True,
        "summary": summary,
        "details": "\n".join(details_lines),
        "source": "api.aladhan.com",
    }


# ── Combined ────────────────────────────────────────────────────────────────

def all_traditions(d: datetime.date) -> dict[str, dict]:
    """Convenience: run all five lookups serially and return a dict keyed by name."""
    return {
        "catholic": catholic_today(d),
        "anglican": anglican_today(d),
        "orthodox": orthodox_today(d),
        "jewish":   jewish_today(d),
        "islamic":  islamic_today(d),
    }
