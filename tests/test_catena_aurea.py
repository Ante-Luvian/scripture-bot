"""Aquinas's Catena Aurea (scripts/build_catena_aurea.py, data/patristics/catena_aurea.json): the Fathers on the four
Gospels, verse by verse."""
import json
import re

from core import ROOT

DATA = json.loads((ROOT / "data" / "patristics" / "catena_aurea.json").read_text(encoding="utf-8"))
KJV = json.loads((ROOT / "data" / "kjv" / "kjv_canon.json").read_text(encoding="utf-8"))["books"]
# verses the copies used have no passage for: Matthew 5:15-16 have no heading in CCEL's (5:31 is printed among the
# comments); isidore.co's Luke has lost 12:49-53
KNOWN_GAPS = {"Matthew": {(5, 15), (5, 16), (5, 31)}, "Luke": {(12, v) for v in range(49, 54)}}


def test_every_verse_of_every_gospel():
    for g in ("Matthew", "Mark", "Luke", "John"):
        book = DATA["books"][f"Catena Aurea on {g}"]
        spans = DATA["spans"].get(f"Catena Aurea on {g}", {})
        missing = set()
        for ch, verses in KJV[g].items():
            covered = set()
            for v in book.get(ch, {}):
                covered |= set(range(int(v), spans.get(f"{ch}:{v}", int(v)) + 1))
            missing |= {(int(ch), int(v)) for v in verses if int(v) not in covered}
        assert missing == KNOWN_GAPS.get(g, set()), (g, sorted(missing))


def test_a_passage():
    """The Gospel's words in italics, then each Father, named in full; several verses printed together are one
    passage; one verse in parts ("1a.", "1b.") is one."""
    john = DATA["books"]["Catena Aurea on John"]["1"]["1"]
    assert john.startswith("*John 1:1. In the beginning was the Word,*\n**Chrysostom**: While all the other")
    assert "*John 1:1. And the Word was with God.*" in john
    luke = DATA["books"]["Catena Aurea on Luke"]["1"]["1"]
    assert luke.startswith("*Luke 1:1–4. Forasmuch as many") and "**Eusebius**: St. Luke" in luke
    matt = DATA["books"]["Catena Aurea on Matthew"]["1"]["1"]
    assert "**Pseudo-Chrysostom** (Hom. in Matt., Hom. i): Matthew wrote for the Jews" in matt


def test_clean():
    for book in DATA["books"].values():
        for ch, verses in book.items():
            for v, text in verses.items():
                assert text.count("**") % 2 == 0, (ch, v)
                assert not re.search(r"<|&\w+;|�|\[ed\. note|\[p \d+|\[margin note|(?<=[a-z])1(?=[a-z])|[a-z][Ͱ-Ͽἀ-῿]|[Ͱ-Ͽἀ-῿][a-z]",
                                 text), \
                    (ch, v, text[:80])


def test_lookup(lookup):
    r = lookup.get_verse("Catena Aurea on John 1:1")
    assert r.get("found") and "Chrysostom" in r["text"]
    assert lookup.get_verse("Golden Chain on Mark 1:1").get("found")
