"""The Roman Breviary's Matins readings from the Fathers (scripts/build_breviary.py, data/patristics/
breviary_readings.json)."""
import json
import re

from core import ROOT

DATA = json.loads((ROOT / "data" / "patristics" / "breviary_readings.json").read_text(encoding="utf-8"))
BOOK = DATA["books"]["Readings from the Breviary"]


def test_the_year_in_order():
    """The seasons from Advent, Christmas between Advent and the Epiphany; then the saints' days; then the Commons."""
    days = [c["1"].split("\n")[0].strip("*") for c in BOOK.values()]
    assert len(days) > 300 and sum(len(c) for c in BOOK.values()) > 400
    assert days[0] == "First Sunday of Advent"
    assert days.index("Fourth Sunday of Advent") < days.index("30 December") < days.index("Second Sunday after the Epiphany")
    assert days.index("Pentecost Sunday") < days.index("First Sunday of November") < days.index("2 January: Octave of St. Stephen")
    assert days[-1].startswith("Common of") and not any(re.search(r"\b(Commune|Beatae|Dominica)\b", d) for d in days)


def test_a_homily_on_the_gospel():
    """A homily names the Gospel it explains (kept in "gospels" for the verse-linked catena)."""
    advent = next(c for c in BOOK.values() if c["1"].startswith("*First Sunday of Advent*"))
    homily = next(v for v in advent.values() if "*On Luke 21:25-33*" in v)
    assert "Gregory" in homily and "Our Lord and Saviour wisheth to find us ready" in homily
    assert len(DATA["gospels"]) > 250


def test_clean():
    for ch, verses in BOOK.items():
        for v, text in verses.items():
            assert text.count("*") % 2 == 0, (ch, v)
            assert not re.search(r"<|&#?\w+;|^\s*[$&@!]", text, re.M), (ch, v, text[:80])


def test_lookup(lookup):
    assert lookup.get_verse("Readings from the Breviary 1:1").get("found")
    assert lookup.get_verse("Breviary 1:1").get("found")
