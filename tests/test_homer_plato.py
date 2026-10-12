"""Homer (Murray, by book and line) and Plato (Loeb translators, by Stephanus section)."""
import asyncio

import pytest


@pytest.mark.parametrize("ref, reference, starts", [
    ("Iliad 1:1", "Iliad 1:1–4", "**[1]** The wrath sing, goddess"),
    ("Iliad 1.7", "Iliad 1:5–9", "**[5]** from the time when first"),       # the passage containing line 7
    ("Iliad 6.440-450", "Iliad 6:440–454", "**[440]** Then spake to her great Hector"),
    ("Odyssey 1:1", "Odyssey 1:1–4", "**[1]** Tell me, O Muse"),
])
def test_homer_by_book_and_line(lookup, ref, reference, starts):
    r = lookup.get_verse(ref)
    assert r["found"] and r["reference"] == reference and r["text"].startswith(starts)
    assert "Murray" in r["source"] and "[]" not in r["text"]


def test_homer_whole_book_and_missing_line(lookup):
    r = lookup.get_verse("Iliad 1")
    assert r["found"] and len(r["pages"]) > 1 and r["pages"][0].startswith("**[1]** The wrath")
    missing = lookup.get_verse("Odyssey 16.580")
    assert not missing["found"] and "no line 580" in missing["error"]


@pytest.mark.parametrize("ref, translator", [
    ("Euthyphro 2a", "Fowler"), ("Apology 17a", "Fowler"), ("Republic 514a", "Shorey"),
    ("Laws 624a", "Bury"), ("Letters 309a", "Bury"), ("Symposium 201d", "Lamb"),
])
def test_plato_sections_and_translators(lookup, ref, translator):
    r = lookup.get_verse(ref)
    assert r["found"] and r["reference"] == ref and translator in r["source"]


def test_plato_section_ends_where_the_next_begins(lookup):
    two_a, two_b = lookup.get_verse("Euthyphro 2a")["text"], lookup.get_verse("Euthyphro 2b")["text"]
    assert two_a.endswith("brought an indictment against you;")
    assert two_b.startswith("for I don")


def test_stephanus_ranges_match_the_text(bot_module, lookup):
    from bot_commands.books import _PLATO_STEPHANUS_RANGES
    for dialogue, (first, last) in _PLATO_STEPHANUS_RANGES.items():
        keys = list(lookup._data["classical"][dialogue])
        assert (keys[0], keys[-1]) == (first, last), dialogue
