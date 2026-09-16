"""
bcp_lookup.py
─────────────
Resolve a calendar date to the BCP Canada 1962 daily-office lectionary row
(morning & evening lessons) and the Coverdale Psalter day-portion.

Public API:
    bcp_for_date(d: datetime.date, period: "morning" | "evening") -> dict

Returns a dict with:
    {
      "found":         bool,
      "date":          ISO date,
      "period":        "morning" | "evening",
      "section_key":   anchor name in bcp_lectionary.json (e.g. "P", "T01")
      "section_title": "The Week of Whitsunday"
      "label":         "Whitsunday" / "Monday" / "Christmas Day" / …
      "year":          "I" | "II" | null
      "lessons": [
          {"slot": "First Lesson",  "ref": "Isa. 11:1-9"},
          {"slot": "Second Lesson", "ref": "Rom. 8:18-end"},
      ],
      "psalter": {
          "day_of_month": 24,
          "period":       "evening",
          "psalms":       ["119:1-32"],  # normalised reference list
          "incipits":     {"119": "Beati immaculati · ..."},
      },
    }

The lectionary year (I/II) is determined by the calendar year of the most-
recent Advent Sunday: if that year is even → Year I, else Year II.

Movable-feast computation uses the same Gregorian computus as
liturgical_calendar.py.
"""

from __future__ import annotations

import datetime
import json
from pathlib import Path
from typing import Optional

# ── Data loading ──────────────────────────────────────────────────────────────

_LECT_DATA: Optional[dict] = None
_PSALTER_DATA: Optional[dict] = None
_COLLECTS_DATA: Optional[dict] = None
_COVERDALE_TEXT: Optional[dict] = None


def _load_lectionary() -> Optional[dict]:
    global _LECT_DATA
    if _LECT_DATA is not None:
        return _LECT_DATA
    for p in [
        Path(__file__).parent / "data" / "bcp_lectionary.json",
        Path("data") / "bcp_lectionary.json",
    ]:
        if p.exists():
            try:
                _LECT_DATA = json.loads(p.read_text(encoding="utf-8"))
                return _LECT_DATA
            except Exception:
                continue
    return None


def _load_psalter() -> Optional[dict]:
    global _PSALTER_DATA
    if _PSALTER_DATA is not None:
        return _PSALTER_DATA
    for p in [
        Path(__file__).parent / "data" / "coverdale_psalter.json",
        Path("data") / "coverdale_psalter.json",
    ]:
        if p.exists():
            try:
                _PSALTER_DATA = json.loads(p.read_text(encoding="utf-8"))
                return _PSALTER_DATA
            except Exception:
                continue
    return None


def _load_coverdale_text() -> Optional[dict]:
    """Load the full Coverdale Psalter verse text."""
    global _COVERDALE_TEXT
    if _COVERDALE_TEXT is not None:
        return _COVERDALE_TEXT
    for p in [
        Path(__file__).parent / "data" / "coverdale_text.json",
        Path("data") / "coverdale_text.json",
    ]:
        if p.exists():
            try:
                _COVERDALE_TEXT = json.loads(p.read_text(encoding="utf-8"))
                return _COVERDALE_TEXT
            except Exception:
                continue
    return None


def _expand_psalm_ref(ref: str) -> list[tuple[str, list[str]]]:
    """
    Given a psalter reference like "119:1-32" or "23" or "120", return
    [(label, [verse_text, ...])] — usually a single tuple, but a ref
    written as "104:1-25" still returns one.

    Falls back to [(ref, [])] if the text isn't loaded.
    """
    data = _load_coverdale_text()
    if not data:
        return [(ref, [])]
    psalms = data.get("psalms", {})

    if ":" in ref:
        ps, range_part = ref.split(":", 1)
        ps = ps.strip()
        if ps not in psalms:
            return [(ref, [])]
        verses = psalms[ps]
        # range_part like "1-32" or "1-end" or just "5"
        if "-" in range_part:
            a, b = range_part.split("-", 1)
            try:
                start = int(a)
            except ValueError:
                start = 1
            if b.strip().lower() == "end":
                end = len(verses)
            else:
                try:
                    end = int(b)
                except ValueError:
                    end = len(verses)
            sliced = verses[start - 1:end]
            label = f"Psalm {ps}:{start}-{end}"
            return [(label, sliced)]
        else:
            try:
                v = int(range_part)
                return [(f"Psalm {ps}:{v}", [verses[v - 1]] if 0 < v <= len(verses) else [])]
            except ValueError:
                return [(ref, [])]

    # Whole-psalm form like "23" or "100"
    ps = ref.strip()
    if ps in psalms:
        return [(f"Psalm {ps}", psalms[ps])]
    return [(ref, [])]


def _load_collects() -> Optional[dict]:
    global _COLLECTS_DATA
    if _COLLECTS_DATA is not None:
        return _COLLECTS_DATA
    for p in [
        Path(__file__).parent / "data" / "bcp_collects.json",
        Path("data") / "bcp_collects.json",
    ]:
        if p.exists():
            try:
                _COLLECTS_DATA = json.loads(p.read_text(encoding="utf-8"))
                return _COLLECTS_DATA
            except Exception:
                continue
    return None


def _collect_for(d: datetime.date, section_key: str, label: str) -> Optional[dict]:
    """Return {'name': str, 'collect': str, 'is_saint_day': bool} or None."""
    data = _load_collects()
    if not data:
        return None

    # 1) Saint's day match by (mm-dd)
    key_md = f"{d.month:02d}-{d.day:02d}"
    saint = data.get("by_saint_date", {}).get(key_md)
    if saint:
        return {
            "name": saint.get("name", "Holy Day"),
            "collect": saint.get("collect", ""),
            "is_saint_day": True,
        }

    # 2) Section/label match (Sundays + major movable days)
    sec = data.get("by_section", {}).get(section_key)
    if sec:
        # Try exact label, then "Sunday" fallback for Sundays in non-Sunday-labelled days
        if label in sec:
            return {"name": label, "collect": sec[label], "is_saint_day": False}
        # For weekday rows, fall back to the Sunday collect of the same section
        if "Sunday" in sec:
            return {"name": "Sunday", "collect": sec["Sunday"], "is_saint_day": False}
        # Some sections have a unique entry (e.g. Whitsunday, Easter Day)
        # — take the only entry if there is one
        if len(sec) == 1:
            only_label, only_collect = next(iter(sec.items()))
            return {"name": only_label, "collect": only_collect, "is_saint_day": False}

    return None


# ── Movable-feast computation (Gregorian computus) ────────────────────────────

def easter_sunday(year: int) -> datetime.date:
    """Anonymous Gregorian computus. Accurate for years 1583+."""
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


def advent_sunday(year: int) -> datetime.date:
    """The Sunday on or nearest to Nov 30 (start of the liturgical year)."""
    nov30 = datetime.date(year, 11, 30)
    # weekday(): Mon=0..Sun=6
    delta = (nov30.weekday() + 1) % 7  # days since previous Sunday
    candidate = nov30 - datetime.timedelta(days=delta)
    # "nearest" — if candidate is more than 3 days before nov30, jump forward
    if (nov30 - candidate).days > 3:
        candidate = candidate + datetime.timedelta(days=7)
    return candidate


def most_recent_advent_year(d: datetime.date) -> int:
    """Return the calendar year of the most recent Advent Sunday on or before d."""
    this_year_advent = advent_sunday(d.year)
    if d >= this_year_advent:
        return d.year
    return d.year - 1


def lectionary_year(d: datetime.date) -> str:
    """Return 'I' (even Advent year) or 'II' (odd Advent year)."""
    return "I" if most_recent_advent_year(d) % 2 == 0 else "II"


# ── Section key resolution ───────────────────────────────────────────────────

# Map day-of-week (Monday=0…Sunday=6) → label as it appears in the lectionary
_WEEKDAY_LABEL = {
    0: "Monday", 1: "Tuesday", 2: "Wednesday",
    3: "Thursday", 4: "Friday", 5: "Saturday", 6: "Sunday",
}

# Named fixed days that have their own row inside Christmastide / Whitsun-week / etc.
_FIXED_NAMED_DAYS: dict[tuple[int, int], tuple[str, str]] = {
    # (month, day): (section_key, label_in_section)
    (12, 24): ("Christmastide", "Christmas Eve"),
    (12, 25): ("Christmastide", "Christmas Day"),
    (12, 26): ("Christmastide", "St. Stephen"),
    (12, 27): ("Christmastide", "St. John"),
    (12, 28): ("Christmastide", "The Innocents"),
    (12, 29): ("Christmastide", "Dec. 29"),
    (12, 30): ("Christmastide", "Dec. 30"),
    (12, 31): ("Christmastide", "Dec. 31"),
    (1, 1):   ("Christmastide", "Octave Day of Christmas (Jan 1)"),
    (1, 2):   ("Christmas II", "Jan 2"),
    (1, 3):   ("Christmas II", "Jan 3"),
    (1, 4):   ("Christmas II", "Jan 4"),
    (1, 5):   ("Christmas II", "Jan 5"),
    (1, 6):   ("Epiphany",     "Epiphany (Jan 6)"),
}


def _trinity_week_count(d: datetime.date) -> int:
    """For dates after Trinity Sunday and before Advent: which Trinity week (1..26)?"""
    easter = easter_sunday(d.year)
    trinity_sunday = easter + datetime.timedelta(days=56)
    # First Sunday after Trinity Sunday = Trinity 1
    days_since_trinity = (d - trinity_sunday).days
    # Trinity 1 starts on the Sunday after Trinity Sunday (day 7)
    # week index = (days_since_trinity - 1) // 7  → on Trinity Sunday itself, returns -1
    week = (days_since_trinity - 1) // 7 + 1
    return week


def _epiphany_week_count(d: datetime.date) -> int:
    """For dates between Epiphany week start and Septuagesima: which Epiphany week (1..6)?"""
    # First Sunday after Epiphany = Epiphany 1
    epiphany = datetime.date(d.year, 1, 6)
    days_after_epiphany = (d - epiphany).days
    if days_after_epiphany < 0:
        # Previous year's Epiphany
        epiphany = datetime.date(d.year - 1, 1, 6)
        days_after_epiphany = (d - epiphany).days
    # Find the Sunday on/after Epiphany
    first_sun_after = epiphany + datetime.timedelta(
        days=(6 - epiphany.weekday()) % 7
    )
    if first_sun_after == epiphany:
        first_sun_after += datetime.timedelta(days=7)
    # That is "First Sunday after Epiphany" → week 1 starts that day
    week = (d - first_sun_after).days // 7 + 1
    return max(1, week)


def _section_for_date(d: datetime.date) -> tuple[str, str]:
    """
    Return (section_key, label) for the given date.
    Examples:
      May 24 2026 (Whitsunday)              → ("P", "Whitsunday")
      May 23 2026 (Sat after Ascension)     → ("A1", "Saturday")
      Dec 25                                → ("Christmastide", "Christmas Day")
      Aug 10                                → ("T08", "Monday") [or whichever Trinity wk]
    """
    # 1) Fixed named days first (Christmastide, early January)
    key_ymd = (d.month, d.day)
    if key_ymd in _FIXED_NAMED_DAYS:
        section_key, label = _FIXED_NAMED_DAYS[key_ymd]
        return section_key, label

    easter = easter_sunday(d.year)
    ash_wednesday = easter - datetime.timedelta(days=46)
    palm_sunday = easter - datetime.timedelta(days=7)
    ascension = easter + datetime.timedelta(days=39)        # Thursday
    pentecost = easter + datetime.timedelta(days=49)        # Whitsunday
    trinity_sunday = easter + datetime.timedelta(days=56)
    adv1 = advent_sunday(d.year)
    # For dates after Advent of *this* year, the ecclesiastical year is next
    if d >= adv1:
        # Use this year's Advent
        pass

    wkday = _WEEKDAY_LABEL[d.weekday()]

    # 2) Whitsun week: from Whitsunday through Saturday after
    if pentecost <= d < pentecost + datetime.timedelta(days=7):
        return ("P", "Whitsunday" if d == pentecost else wkday)

    # 3) Easter week: from Easter Day through Easter Saturday
    if easter <= d < easter + datetime.timedelta(days=7):
        # Easter Day itself
        if d == easter:
            return ("E", "Easter Day")
        return ("E", wkday)

    # 4) Holy Week: Palm Sunday through Holy Saturday
    if palm_sunday <= d < easter:
        # Section "L6" — Holy Week
        if d == palm_sunday:
            return ("L6", "Palm Sunday")
        if d == easter - datetime.timedelta(days=1):
            return ("L6", "Easter Eve")
        special = {
            -3: "Maundy Thursday",
            -2: "Good Friday",
        }
        off = (d - easter).days
        if off in special:
            return ("L6", special[off])
        return ("L6", wkday)

    # 5) Lent weeks 1-5 (Sundays of Lent + their weeks)
    # Lent 1 Sunday = first Sunday in Lent = Ash Wednesday's following Sunday
    lent1_sun = ash_wednesday + datetime.timedelta(days=(6 - ash_wednesday.weekday()) % 7)
    if lent1_sun == ash_wednesday:
        lent1_sun += datetime.timedelta(days=7)
    # Ash Wed and the days up to Lent 1 Sunday belong to the "Quinquagesima/Lent 1" overlap;
    # the lectionary puts Ash Wed under "Quinquagesima" week.
    if d == ash_wednesday:
        return ("Quin", "Ash Wednesday")
    if ash_wednesday < d < lent1_sun:
        return ("Quin", wkday)  # Thursday/Friday/Saturday after Ash Wed
    # Lent 1-5
    for lent_n in range(1, 6):
        wk_start = lent1_sun + datetime.timedelta(days=7 * (lent_n - 1))
        wk_end = wk_start + datetime.timedelta(days=7)
        if wk_start <= d < wk_end:
            return (f"L{lent_n}", "Sunday" if d == wk_start else wkday)

    # 6) Septuagesima / Sexagesima / Quinquagesima — three Sundays before Lent
    sept_sun = ash_wednesday - datetime.timedelta(days=17)  # = 2.5 weeks before Ash Wed?
    # Actually: Septuagesima = 3rd Sunday before Lent = 9 weeks before Easter (Easter - 63)
    septuagesima = easter - datetime.timedelta(days=63)
    sexagesima   = easter - datetime.timedelta(days=56)
    quinquagesima = easter - datetime.timedelta(days=49)
    if septuagesima <= d < sexagesima:
        return ("Sept", "Sunday" if d == septuagesima else wkday)
    if sexagesima <= d < quinquagesima:
        return ("Sexa", "Sunday" if d == sexagesima else wkday)
    if quinquagesima <= d < ash_wednesday:
        return ("Quin", "Sunday" if d == quinquagesima else wkday)

    # 7) Easter 1-5: from Easter+7 (Easter Sunday + 1 week = Easter 1 Sunday) onward
    for e_n in range(1, 6):
        wk_start = easter + datetime.timedelta(days=7 * e_n)
        wk_end = wk_start + datetime.timedelta(days=7)
        if wk_start <= d < wk_end:
            return (f"E{e_n}", "Sunday" if d == wk_start else wkday)

    # 8) Ascension week (Ascension Day through Saturday after) — section A1.
    # The lectionary table calls this "The Week of Ascension Sunday" — meaning
    # the week containing Ascension Day. Ascension Thursday = Easter+39.
    ascension_sun_start = ascension - datetime.timedelta(days=ascension.weekday() + 1)
    if ascension_sun_start.weekday() != 6:
        # Force to Sunday before Ascension
        ascension_sun_start = ascension - datetime.timedelta(days=(ascension.weekday() + 1) % 7)
    # The "Sunday after Ascension" = Easter+42. A1 week = Ascension Sun (Easter+42 - actually...)
    # Per the lectionary table, A1 = "The Week of Ascension Sunday" runs from
    # Ascension Day through the following Saturday (8 days, the Sunday is in there).
    # Simpler: if Ascension <= d < Pentecost, we're in A1.
    if ascension <= d < pentecost:
        if d == ascension:
            return ("A1", "Ascension Day")
        # Sunday after Ascension
        sunday_after_ascension = easter + datetime.timedelta(days=42)
        if d == sunday_after_ascension:
            return ("A1", "Sunday")
        return ("A1", wkday)

    # 9) Trinity Sunday + week (T = Trinity Sunday week)
    if trinity_sunday <= d < trinity_sunday + datetime.timedelta(days=7):
        return ("T", "Trinity Sunday" if d == trinity_sunday else wkday)

    # 10) Trinity 1-25 (or 26)
    weeks_after_trinity = ((d - trinity_sunday).days - 7) // 7 + 1
    if 1 <= weeks_after_trinity <= 26:
        # Sunday of that week = trinity_sunday + 7 * weeks_after_trinity (the next Sunday)
        sun_of_week = trinity_sunday + datetime.timedelta(days=7 * weeks_after_trinity)
        # Trinity N week runs from that Sunday through the following Saturday
        return (f"T{weeks_after_trinity:02d}",
                "Sunday" if d == sun_of_week else wkday)

    # 11) Sunday next before Advent (A0): the week up to Advent 1
    if d < adv1 and (adv1 - d).days <= 7:
        return ("A0", "Sunday" if d.weekday() == 6 else wkday)

    # 12) Advent 1-4
    for av_n in range(1, 5):
        wk_start = adv1 + datetime.timedelta(days=7 * (av_n - 1))
        wk_end = wk_start + datetime.timedelta(days=7)
        if wk_start <= d < wk_end:
            section = {1: "Advent I", 2: "Advent II", 3: "Advent III", 4: "Advent IV"}[av_n]
            return (section, "Sunday" if d == wk_start else wkday)

    # 13) Epiphany weeks 1-6 (between Epiphany and Septuagesima)
    epiphany_day = datetime.date(d.year, 1, 6)
    if d > epiphany_day and d < septuagesima:
        # Find which Epiphany Sunday
        first_sun = epiphany_day + datetime.timedelta(days=(6 - epiphany_day.weekday()) % 7)
        if first_sun == epiphany_day:
            first_sun += datetime.timedelta(days=7)
        ep_n = (d - first_sun).days // 7 + 1
        ep_n = max(1, min(6, ep_n))
        keys = {1: "Epiphany I", 2: "Epiphany II", 3: "EpIII",
                4: "EpIV", 5: "EpV", 6: "EpVI"}
        section = keys[ep_n]
        # First-week-of-Epiphany Sunday or weekday
        # Between Jan 7 and the first Sunday after Epiphany = "Weekdays between Epiphany and Epiphany I"
        # These belong to section "Epiphany" rather than "Epiphany I"
        if d < first_sun:
            return ("Epiphany", wkday)
        return (section, "Sunday" if (d - first_sun).days % 7 == 0 else wkday)

    # Weekdays between Epiphany (Jan 6) and the first Sunday after Epiphany
    if epiphany_day < d < epiphany_day + datetime.timedelta(days=7):
        # First Sunday after Epiphany start
        return ("Epiphany", wkday)

    # Fallback
    return ("?", wkday)


# ── Lessons lookup ───────────────────────────────────────────────────────────

def _find_row(section_key: str, label: str, year: str) -> Optional[dict]:
    """Pick the matching row from the lectionary section."""
    data = _load_lectionary()
    if not data:
        return None
    sec = data.get("sections", {}).get(section_key)
    if not sec:
        return None
    rows = sec.get("rows", [])

    # First, try exact label match
    matches = [r for r in rows if _norm_label(r["label"]) == _norm_label(label)]

    # If label-match yields multiple, filter by year for Sundays
    if len(matches) > 1:
        if label.lower().startswith("sunday") or _norm_label(label) == "sunday":
            yr_matches = [r for r in matches if r["year"] == year]
            if yr_matches:
                matches = yr_matches[:1]
        else:
            matches = matches[:1]

    if matches:
        return {**matches[0], "section_key": section_key, "section_title": sec.get("title", "")}

    # Fallback: case-insensitive partial
    label_l = label.lower()
    for r in rows:
        if r["label"].lower().startswith(label_l) or label_l.startswith(r["label"].lower()):
            return {**r, "section_key": section_key, "section_title": sec.get("title", "")}

    return None


def _norm_label(s: str) -> str:
    return (s or "").strip().lower().replace(".", "").replace("  ", " ")


# ── Psalter lookup ───────────────────────────────────────────────────────────

def _psalter_for_date(d: datetime.date, period: str) -> Optional[dict]:
    data = _load_psalter()
    if not data:
        return None
    days = data.get("days", {})
    incipits = data.get("incipits", {})
    # The 31st day: per BCP rubric, the Psalms of the preceding day are read again.
    dom = d.day
    if dom == 31:
        dom = 30
    key = str(dom)
    if key not in days:
        return None
    psalms = days[key].get(period, [])

    # Expand each appointed portion into full Coverdale verse text
    portions = []
    for ref in psalms:
        for label, verses in _expand_psalm_ref(ref):
            ps_num = ref.split(":")[0]
            portions.append({
                "ref": ref,
                "label": label,
                "incipit": incipits.get(ps_num, ""),
                "verses": verses,
            })

    return {
        "day_of_month": dom,
        "period": period,
        "psalms": psalms,
        "portions": portions,
    }


# ── Public API ───────────────────────────────────────────────────────────────

def bcp_for_date(d: datetime.date, period: str) -> dict:
    """Resolve `d` + `period` ('morning' or 'evening') into the full result dict."""
    if period not in ("morning", "evening"):
        return {"found": False, "error": "period must be 'morning' or 'evening'"}

    section_key, label = _section_for_date(d)
    year = lectionary_year(d)
    row = _find_row(section_key, label, year)

    if not row:
        return {
            "found": False,
            "error": f"No lectionary row found for {d} ({section_key}/{label}, year {year}).",
            "date": d.isoformat(),
            "period": period,
            "section_key": section_key,
            "label": label,
            "year": year,
            "psalter": _psalter_for_date(d, period),
        }

    if period == "morning":
        lessons = [
            {"slot": "First Lesson",  "ref": row["mp_ot"]},
            {"slot": "Second Lesson", "ref": row["mp_nt"]},
        ]
    else:
        lessons = [
            {"slot": "First Lesson",  "ref": row["ep_ot"]},
            {"slot": "Second Lesson", "ref": row["ep_nt"]},
        ]

    collect = _collect_for(d, section_key, row["label"])

    return {
        "found": True,
        "date": d.isoformat(),
        "period": period,
        "section_key": section_key,
        "section_title": row.get("section_title", ""),
        "label": row["label"],
        "year": row.get("year") or year,
        "lessons": lessons,
        "psalter": _psalter_for_date(d, period),
        "collect": collect,
    }
