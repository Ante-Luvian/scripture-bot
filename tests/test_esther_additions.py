"""The Additions to Esther in other Bibles' styles (letters A-F, "Greek Esther", "Rest of Esther"), and ranges
written "6:18–6:47" in ordinary messages."""
import pytest

from scripture_lookup import esther_additions, vulgate_esther


@pytest.mark.parametrize("ref, want", [
    ("Esther C:2", "Additions to Esther 13:9"), ("Esther C 2", "Additions to Esther 13:9"),
    ("Esth A:1", "Additions to Esther 11:2"), ("Esther A:12", "Additions to Esther 12:1"),
    ("Esther F:11", "Additions to Esther 11:1"), ("Esther C:11-12", "Additions to Esther 13:18-14:1"),
    ("Esther D", "Additions to Esther 15:1-16"), ("Esther E:1-3", "Additions to Esther 16:1-3"),
    ("Greek Esther 13:9", "Additions to Esther 13:9"), ("Rest of Esther 14:3", "Additions to Esther 14:3"),
    ("Greek Esther 10:4", "Additions to Esther 10:4"), ("Greek Esther 10:2", "Esther 10:2"),
    ("Greek Esther 3:1", "Esther 3:1"), ("Esther (Greek) 15:1", "Additions to Esther 15:1"),
    # left alone: no such addition or verse, and ordinary references
    ("Esther G:1", "Esther G:1"), ("Esther C:31", "Esther C:31"), ("Esther 3:1", "Esther 3:1"),
    ("Add Esth 16:1", "Add Esth 16:1"), ("John 3:16", "John 3:16"),
])
def test_esther_styles(ref, want):
    assert esther_additions(ref) == want


def test_vulgate_numbering_keeps_the_additions_in_esther():
    assert vulgate_esther("Esther C:2") == "Esther 13:9"
    assert vulgate_esther("Additions to Esther 13:9") == "Esther 13:9"
    assert vulgate_esther("Rest of Esther 14:3") == "Esther 14:3"


@pytest.mark.parametrize("ref, title", [
    ("Esther C:2", "Additions to Esther 13:9"), ("Greek Esther 13:9", "Additions to Esther 13:9"),
    ("Rest of Esther 14:3", "Additions to Esther 14:3"),
])
def test_lookup(ref, title):
    import scripture_lookup
    r = scripture_lookup.ScriptureLookup().get_verse(ref)
    assert r["found"] and "Almighty" in r["text"] if "13:9" in title else r["found"]


@pytest.mark.parametrize("get", ["drb", "knox"])
def test_douay_and_knox(get):
    import scripture_lookup
    f = scripture_lookup.get_verse_drb if get == "drb" else scripture_lookup.get_verse_knox
    assert f("Esther C:2")["found"] and f("Greek Esther 13:9")["found"]


def test_auto_detect_same_chapter_range():
    from core import _AUTO_RE
    assert _AUTO_RE.findall("read 1 Maccabees 6:18–6:47 tonight") == [("1 Maccabees", "6", "18", "47")]
    assert _AUTO_RE.findall("John 7:53-8:11") == [("John", "7", "53", "")]
