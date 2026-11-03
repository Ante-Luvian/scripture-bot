"""The Prayer Book lessons (!bcp, !mp, !ep): every reference in the lectionary read, in its own notation. A
bug-tester's random !ep found "[not available]"; 114 references (and 12 days) had never been read."""
import datetime

import pytest


@pytest.fixture(scope="module")
def liturgy(bot_module):
    from bot_commands import liturgy
    return liturgy


@pytest.mark.parametrize("ref, book, segments", [
    ("Gen. 11:1-9; 27-12:10", "Genesis", [(11, 1, 11, 9), (11, 27, 12, 10)]),     # (27: verse 27 of chapter 11)
    ("Ex. 6:2-23 7:1-7", "Exodus", [(6, 2, 6, 23), (7, 1, 7, 7)]),
    ("Job 25 26", "Job", [(25, None, 25, None), (26, None, 26, None)]),           # (two whole chapters)
    ("Deut. 32:48-end 34", "Deuteronomy", [(32, 48, 32, "end"), (34, None, 34, None)]),
    ("Prov. 8:1, 22-end", "Proverbs", [(8, 1, 8, 1), (8, 22, 8, "end")]),        # (after a comma: a verse)
    ("1 Tim.1:18-2 end", "1 Timothy", [(1, 18, 2, "end")]),
    ("Acts 9:1-22 (23-31)", "Acts", [(9, 1, 9, 22)]),                             # (the bracketed longer reading)
    ("Ruth 2:1-20 a (4:13-17)", "Ruth", [(2, 1, 2, 20)]),                         # (half a verse: the verse)
    ("Num. 24;1-19", "Numbers", [(24, 1, 24, 19)]),                               # (a misprint for 24:1)
    ("Acts 27:1=26", "Acts", [(27, 1, 27, 26)]),
    ("Philemon", "Philemon", [(1, None, 1, None)]),                               # (a one-chapter book, whole)
    ("Jude 17-end", "Jude", [(1, 17, 1, "end")]),
    ("I Pet. 1:1-12", "1 Peter", [(1, 1, 1, 12)]), ("Jam. 3", "James", [(3, None, 3, None)]),
    ("S. of Sol. 2:8-end", "Song of Solomon", [(2, 8, 2, "end")]),
    ("Lk. 24: 13-35", "Luke", [(24, 13, 24, 35)]),
])
def test_the_lectionarys_notation(liturgy, ref, book, segments):
    assert liturgy._bcp_segments(ref) == (book, segments)


def test_a_reading_in_pieces_is_read_whole(liturgy):
    shown, text = liturgy._bcp_fetch_text("Deut. 32:48-end 34")
    assert shown == "Deuteronomy 32:48–32:52; Deuteronomy 34:1–34:12" and text.count("**[") == 17


def test_every_lesson_of_a_year_reads(liturgy):
    import bcp_lookup
    missing, empty = [], []
    d = datetime.date(2026, 1, 1)
    while d.year == 2026:
        for period in ("morning", "evening"):
            lessons = bcp_lookup.bcp_for_date(d, period)["lessons"]
            if not lessons and d != datetime.date(2026, 12, 24):     # (Christmas Eve morning has none appointed)
                empty.append(f"{d} {period}")
            for les in lessons:
                if liturgy._bcp_fetch_text(les["ref"])[1] == "*[not available]*":
                    missing.append(f"{d} {period}: {les['ref']}")
        d += datetime.timedelta(days=1)
    assert not empty, empty                     # (Good Friday, Easter Eve, the Rogation days, Ascension Day)
    assert not missing, missing


def test_every_day_has_its_collect():
    """By the 1662 rubrics where the day has none of its own (about 55 days a year had none at all)."""
    import bcp_lookup
    names, d = {}, datetime.date(2026, 1, 1)
    while d.year == 2026:
        collect = bcp_lookup.bcp_for_date(d, "morning").get("collect") or {}
        assert collect.get("collect"), d
        names[d.isoformat()] = collect["name"]
        d += datetime.timedelta(days=1)
    assert names["2026-04-03"] == "Good Friday"                      # (its three, from the 1662 book)
    assert names["2026-03-31"] == "Palm Sunday" and names["2026-04-08"] == "Easter Day"
    assert names["2026-11-29"] == "Sunday next before Advent" and names["2026-12-30"] == "Christmas Day"
    assert "Jews, Turks, Infidels" in bcp_lookup.bcp_for_date(datetime.date(2026, 4, 3), "morning")["collect"]["collect"]


def test_a_month_and_day_alone(liturgy):
    year = datetime.date.today().year
    assert liturgy._parse_today_date("12-25") == datetime.date(year, 12, 25)
    assert liturgy._parse_today_date("12/25") == datetime.date(year, 12, 25)
    assert liturgy._parse_today_date("13-45") is None
