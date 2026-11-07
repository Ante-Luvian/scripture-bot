"""The Poetic Edda is in Bellows's spellings ("Hovamol"); the usual ones and the English titles find it too (the
owner, 2026-11-07: "havamal")."""
import pytest


@pytest.mark.parametrize("ref, book", [
    ("havamal 1", "Hovamol"), ("Hávamál 138", "Hovamol"), ("Sayings of the High One 2", "Hovamol"),
    ("voluspa 1", "Voluspo"), ("Völuspá 3", "Voluspo"), ("Prophecy of the Seeress 1", "Voluspo"),
    ("Loki's Quarrel 1", "Lokasenna"), ("thrymskvida 1", "Thrymskvitha"), ("Baldr's Dreams 1", "Baldrs Draumar"),
    ("the lay of wayland 1", "Völundarkvitha"), ("Hovamol 1", "Hovamol"),
])
def test_an_edda_poem_by_its_other_names(lookup, ref, book):
    res = lookup.get_verse(ref)
    assert res.get("found") and res["reference"].startswith(book), (ref, res.get("error"))
