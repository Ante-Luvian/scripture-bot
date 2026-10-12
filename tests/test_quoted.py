"""!quoted -- the reference-matching helpers, and that every entry in the
curated quotation tables actually resolves against the local corpus."""
import re

import pytest


def test_quotation_norm(bot_module):
    assert bot_module._quotation_norm("Isaiah 53:5") == ("Isaiah", 53, 5, 5)
    assert bot_module._quotation_norm("Jude 1:14-15") == ("Jude", 1, 14, 15)
    assert bot_module._quotation_norm("Book of Enoch") == ("Book of Enoch", 0, 0, 0)


@pytest.mark.parametrize("a, b, overlaps", [
    ("Isaiah 53:4-6", "Isaiah 53:5",   True),
    ("Isaiah 53:5",   "Isaiah 53:5",   True),
    ("Isaiah 53:5",   "Isaiah 53:6",   False),
    ("Isaiah 53:5",   "Isaiah 54:5",   False),   # same verse, other chapter
    ("Isaiah 53:5",   "Jeremiah 53:5", False),   # same numbers, other book
])
def test_quotation_overlaps(bot_module, a, b, overlaps):
    assert bot_module._quotation_overlaps(a, b) is overlaps


@pytest.mark.parametrize("query, table_ref, matches", [
    ("Book of Enoch 1:9",        "Book of Enoch 1:9",       True),   # exact
    ("Book of Enoch 10:3-5",     "Book of Enoch 10:4",      True),   # range overlap
    ("Book of Enoch 10:5",       "Book of Enoch 10:4",      False),
    ("Apocalypse of Moses 17:2", "Apocalypse of Moses 17",  True),   # chapter-only entry
    ("Apocalypse of Moses 18:1", "Apocalypse of Moses 17",  False),
    ("Assumption of Moses",      "Assumption of Moses",     True),   # book-only entry
])
def test_apocrypha_ref_matches(bot_module, query, table_ref, matches):
    assert bot_module._apocrypha_ref_matches(query, table_ref) is matches


def _verse_refs(bot_module):
    """Every chapter:verse reference in both curated tables (book-only and
    chapter-only entries are deliberate -- non-extant or loosely cited)."""
    refs = set()
    for ot, nt in bot_module._OT_NT_QUOTATIONS:
        refs.update((ot, nt))
    for nt, apoc, _note in bot_module._NT_APOCRYPHA_QUOTATIONS:
        refs.update((nt, apoc))
    return sorted(r for r in refs if re.search(r"\d+:\d+", r))


def test_every_quotation_table_ref_resolves(bot_module, lookup):
    missing = [r for r in _verse_refs(bot_module) if not lookup.get_verse(r).get("found")]
    assert not missing, f"Quotation table refs not found in local corpus: {missing}"


def test_quotation_tables_have_no_duplicates(bot_module):
    pairs = bot_module._OT_NT_QUOTATIONS
    assert len(pairs) == len(set(pairs))
    apoc = [(nt, src) for nt, src, _ in bot_module._NT_APOCRYPHA_QUOTATIONS]
    assert len(apoc) == len(set(apoc))
