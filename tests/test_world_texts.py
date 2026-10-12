"""Texts added from Project Gutenberg (scripts/build_world_texts.py)."""
import pytest


@pytest.mark.parametrize("ref, reference, starts", [
    ("Dhammapada 1:5", "Dhammapada 1:5", "**[5]** For hatred does not cease by hatred"),
    ("Dhammapada 183", "Dhammapada 14:183", "**[183]** Not to commit any sin"),      # cited by verse number
    ("Dhp 2:183", "Dhammapada 14:183", "**[183]** Not to commit any sin"),          # wrong chapter given
    ("Dhammapada 59", "Dhammapada 4:58–59", "**[58]** (vv. 58–59) As on a heap of rubbish"),  # a paired verse
    ("Diamond Sutra 32:2", "Diamond Sutra 32:2", "**[2]** “In what attitude of mind"),
])
def test_buddhist(lookup, ref, reference, starts):
    r = lookup.get_verse(ref)
    assert r["found"], r
    assert r["reference"] == reference and r["text"].startswith(starts)


def test_whole_chapters_and_sources(lookup):
    r = lookup.get_verse("Dhammapada 1")
    assert r["found"] and r["text"].startswith("**[1]** All that we are is the result")
    assert "Müller" in r["source"]
    assert "Gemmell" in lookup.get_verse("Diamond Sutra 1")["source"]
    assert "translated together" in lookup.get_verse("Diamond Sutra 4:1")["text"]
