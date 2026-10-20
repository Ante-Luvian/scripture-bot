"""Swedenborg's theological works (by his section numbers) and Milton's poems (by book and line)."""
import pytest


@pytest.mark.parametrize("ref, reference, snippet", [
    ("Heaven and Hell 1", "Heaven and Hell 1", "consummation of the age"),
    ("HH 51", "Heaven and Hell 51", "EACH SOCIETY IS A HEAVEN IN A SMALLER FORM"),
    ("Arcana Coelestia 1", "Arcana Coelestia 1", "From the mere letter of the Word"),
    ("Arcana 10837", "Arcana Coelestia 10837", "betrothals and marriages"),
    ("TCR 3", "True Christian Religion 3", "Jehovah God is love itself"),
    ("DLW 1", "Divine Love and Wisdom 1", "LOVE IS THE LIFE OF MAN"),
    ("Earths in the Universe 1", "Earths in the Universe 1", ""),
])
def test_swedenborg(lookup, ref, reference, snippet):
    r = lookup.get_verse(ref)
    assert r["found"] and r["reference"] == reference and snippet in r["text"], r.get("error")
    assert r["source"].startswith("trans. ")                         # his translator


def test_swedenborg_is_whole(lookup):
    """Every work starts at section 1 (a page whose only heading is its footnotes' once lost
    Heaven and Hell 1-50); the few gaps left are gaps in the sacred-texts edition itself."""
    books = {b: c for b, c in lookup._data["medieval"].items()
             if lookup._book_file.get(("medieval", b)) == "swedenborg.json"}
    assert len(books) == 33
    for name, sections in books.items():
        if name != "Spiritual Diary":                    # (sacred-texts' translation begins at 1539)
            assert "1" in sections, name
    assert len(books["Arcana Coelestia"]) > 10_800 and len(books["Heaven and Hell"]) > 600
    assert "Ac" not in [b for b in books] and lookup._resolve_book("Ac")[1] != "Arcana Coelestia"   # Acts' abbreviation


@pytest.mark.parametrize("ref, reference, snippet", [
    ("Paradise Lost 1:1-3", "Paradise Lost 1:1–3", "Of Mans First Disobedience"),
    ("PL 4:299", "Paradise Lost 4:299", "Hee for God only, shee for God in him"),
    ("Paradise Lost 12:648", "Paradise Lost 12:648", "Through Eden took thir solitarie way."),
    ("Paradise Lost 1:0", "Paradise Lost 1:0", "The Argument"),
    ("Paradise Regained 1:1", "Paradise Regained 1:1", "I WHO e're while the happy Garden sung"),
    ("Samson Agonistes 41", "Samson Agonistes 1:41", "Eyeless in Gaza"),
    ("Samson 1:1758", "Samson Agonistes 1:1758", "And calm of mind all passion spent."),
])
def test_milton(lookup, ref, reference, snippet):
    r = lookup.get_verse(ref)
    assert r["found"] and r["reference"] == reference and snippet in r["text"], r.get("error")
    assert "Milton" in r["source"]


def test_no_editors_notes_in_milton(lookup):
    for book in ("Paradise Lost", "Paradise Regained", "Samson Agonistes"):
        for chapter in lookup._data["medieval"][book].values():
            assert not any(v.lstrip().startswith(("Note:", "Notes:")) or "1674." in v for v in chapter.values()), book


@pytest.mark.parametrize("ref, reference, snippet", [
    ("Pilgrim's Progress 1:1", "Pilgrim's Progress 1:1", "As I walk'd through the wilderness of this world"),
    ("Pilgrims Progress 0:1", "Pilgrim's Progress 0:1", "When at the first I took my Pen in hand"),
    ("Pilgrim's Progress Part Two 1:1", "Pilgrim's Progress, Part Two 1:1", "Go now my little Book"),
    ("Christiana 2:1", "Pilgrim's Progress, Part Two 2:1", ""),
])
def test_pilgrims_progress(lookup, ref, reference, snippet):
    r = lookup.get_verse(ref)
    assert r["found"] and r["reference"] == reference and snippet in r["text"], r.get("error")
    assert "Bunyan" in r["source"] and "Section I" not in r["text"]
