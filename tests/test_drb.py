"""The Douay-Rheims (data/drb.json, scripts/build_drb.py)."""
import json

from core import ROOT

DRB = json.loads((ROOT / "data" / "drb.json").read_text(encoding="utf-8"))
# How many verses each chapter has in eBible.org's Douay-Rheims (engDRA, fetched 2026-11-11), which numbers the verses
# as ours (and drbo.org) does: a chapter with one fewer has run a verse into the one before it.
COUNTS = json.loads((ROOT / "tests" / "drb_verse_counts.json").read_text(encoding="utf-8"))


def test_every_chapter_has_all_its_verses():
    wrong = [f"{book} {i}: {len(DRB[book].get(str(i), {}))} verses, not {n}"
             for book, counts in COUNTS.items() for i, n in enumerate(counts, 1)
             if sorted(DRB[book].get(str(i), {}), key=int) != [str(v) for v in range(1, n + 1)]]
    assert not wrong and set(DRB) == set(COUNTS), wrong


def test_the_old_files_typos_are_gone():
    """It had "Jones" for Jonas, "Abrabam", "oountenance" (Jonas 1:5, Genesis 28:4, 40:7)."""
    assert "Jonas went down" in DRB["Jonas"]["1"]["5"]
    assert "Abraham" in DRB["Genesis"]["28"]["4"] and "countenance" in DRB["Genesis"]["40"]["7"]


def test_eBibles_scanning_slips_are_gone():
    """The eBible.org scan this replaced had "offer leaves", "Israel Israel was a child", "comedown"."""
    assert "they shall offer loaves without leaven" in DRB["Leviticus"]["7"]["12"]
    assert "king of Israel passed away. Because Israel was a child" in DRB["Osee"]["11"]["1"]
    assert "torrent Arnon" in DRB["Deuteronomy"]["2"]["36"] and "comedown" not in DRB["Psalms"]["7"]["17"]


def test_drbos_typing_slips_are_corrected():
    """scripts/drb_fixes.json, applied by build_drb.py: drbo.org has "said me", "and and", "the streams of Amen",
    "Machir beget Galaad", and no title on Psalm 129; its own readings stay ("anathema")."""
    assert "said to me: Buy my field, which is in Anathoth in the land" in DRB["Jeremias"]["32"]["8"]
    assert "a reproach: and they will not" in DRB["Jeremias"]["6"]["10"]
    assert DRB["Numbers"]["21"]["14"].endswith("the streams of Arnon.")
    assert "Machir begot Galaad" in DRB["Numbers"]["26"]["29"]
    assert DRB["Psalms"]["129"]["1"].startswith("A gradual canticle. Out of the depths")
    assert "of the anathema" in DRB["Josue"]["7"]["1"]


def test_psalm_headings():
    """Psalm 118's Hebrew letters head their stanzas; drbo.org's "Hebrews Psalm 10" marker isn't text."""
    assert DRB["Psalms"]["118"]["9"].startswith("BETH. By what doth a young man")
    assert DRB["Psalms"]["118"]["8"].endswith("utterly forsake me.")
    assert DRB["Psalms"]["9"]["21"].endswith("to be but men.")


def test_last_verses_no_longer_run_on():
    assert DRB["Amos"]["9"]["15"].startswith("And I will plant them upon their own land")
    assert DRB["Amos"]["9"]["14"].endswith("eat the fruits of them.")
    assert DRB["John"]["11"]["57"].startswith("And the chief priests and Pharisees")
    assert DRB["Genesis"]["5"]["32"] == "And Noe, when he was five hundred years old, begot Sem, Cham, and Japheth."
