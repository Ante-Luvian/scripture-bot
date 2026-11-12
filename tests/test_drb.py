"""The Douay-Rheims (data/drb.json, scripts/build_drb.py)."""
import json

from core import ROOT

DRB = json.loads((ROOT / "data" / "drb.json").read_text(encoding="utf-8"))
# How many verses each chapter has in eBible.org's Douay-Rheims (engDRA, fetched 2026-11-11), which numbers the verses
# as ours does: a chapter with one fewer has run a verse into the one before it.
COUNTS = json.loads((ROOT / "tests" / "drb_verse_counts.json").read_text(encoding="utf-8"))


def test_every_chapter_has_all_its_verses():
    wrong = [f"{book} {i}: {len(DRB[book].get(str(i), {}))} verses, not {n}"
             for book, counts in COUNTS.items() for i, n in enumerate(counts, 1)
             if sorted(DRB[book].get(str(i), {}), key=int) != [str(v) for v in range(1, n + 1)]]
    assert not wrong and set(DRB) == set(COUNTS), wrong


def test_last_verses_no_longer_run_on():
    assert DRB["Amos"]["9"]["15"].startswith("And I will plant them upon their own land")
    assert DRB["Amos"]["9"]["14"].endswith("eat the fruits of them.")
    assert DRB["John"]["11"]["57"].startswith("And the chief priests and Pharisees")
    assert DRB["Genesis"]["5"]["32"] == "And Noe, when he was five hundred years old, begot Sem, Cham, and Japheth."
