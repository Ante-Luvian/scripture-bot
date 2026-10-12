"""ScriptureLookup._parse_reference -- splitting a free-form reference into
(book, chapter, verse_start, verse_end), or a 6-tuple range sentinel."""
import pytest


@pytest.mark.parametrize("ref, expected", [
    ("John 3:16",          ("John", 3, 16, None)),
    ("John 3:16-21",       ("John", 3, 16, 21)),
    ("John 3:16–18",       ("John", 3, 16, 18)),          # en dash
    ("John 3:16 -18",      ("John", 3, 16, 18)),          # space before dash
    ("John 3",             ("John", 3, None, None)),      # whole chapter
    ("1 Nephi 3:7",        ("1 Nephi", 3, 7, None)),      # leading digit in book
    ("D&C 76:22",          ("D&C", 76, 22, None)),
    ("John 7:53-8:11",     ("John", 7, 53, 8, 11, "cross_chapter")),
    ("John 3-5",           ("John", 3, None, 5, None, "chap_range")),
    ("Rig Veda 10.121:9",  ("Rig Veda", "10.121", 9, None)),   # dotted chapter
    ("Rig Veda 10.121.9",  ("Rig Veda", "10.121", 9, None)),
    ("Psalm 151",          ("Psalm 151", 151, None, None)),     # Ps 151-155 are own books
])
def test_parse(lookup, ref, expected):
    assert lookup._parse_reference(ref) == expected


@pytest.mark.parametrize("ref", ["Genesis", "hello", "", "3:16"])
def test_unparseable(lookup, ref):
    assert lookup._parse_reference(ref) is None


# Regression: a greedy book group used to swallow "John 3:16 -" as the book
# name whenever whitespace followed the dash ("Unknown book").
@pytest.mark.parametrize("ref", ["John 3:16 - 18", "John 3:16- 18", "John 3:16 – 18"])
def test_space_after_range_dash(lookup, ref):
    assert lookup._parse_reference(ref) == ("John", 3, 16, 18)
    assert lookup.get_verse(ref)["reference"] == "John 3:16–18"


@pytest.mark.parametrize("ref, expected", [
    ("Song of Solomon 2:1",  ("Song of Solomon", 2, 1, None)),   # multi-word book
    ("1 Clement 5:1",        ("1 Clement", 5, 1, None)),
    ("3 John 1:4",           ("3 John", 1, 4, None)),
])
def test_lazy_book_group_keeps_multiword_books(lookup, ref, expected):
    assert lookup._parse_reference(ref) == expected


def test_backwards_chapter_range_is_not_a_chapter_range(lookup):
    # "John 5-3" must not be read as chapters 5..3
    assert lookup._parse_reference("John 5-3") != ("John", 5, None, 3, None, "chap_range")
