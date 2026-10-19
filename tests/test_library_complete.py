"""Everything the library lists can be read. Found while building the library PDF: works listed
in !books with no text (Basil's letters), aliases to books that never existed ("bede", "moralia",
which fell through to Xenophon's Memorabilia), Aristotle cut off after Book I, chapters numbered
"I.1" that no reference could reach, and Bede and the Golden Legend stored a part per "book"."""
import pytest

# aliases handled before the alias table (ScriptureLookup._try_ancient_near_east)
SPECIAL_TARGETS = {"Gilgamesh — Tablet First"}
# collections read from online libraries rather than local files (the path in the !books tree)
ONLINE = ("Quran", "Hadith", "Mishnah", "Babylonian Talmud", "Jerusalem Talmud", "Tosefta", "Targumim",
          "Midrash", "Maimonides", "Kabbalah", "Mesopotamian", "Canaanite")


def test_every_alias_names_a_book(lookup):
    from scripture_lookup import ALIASES
    books = {b for corpus in lookup._data.values() for b in corpus}
    dead = sorted({t for t in ALIASES.values() if not t.startswith("_") and t not in books} - SPECIAL_TARGETS)
    assert not dead, f"aliases to books that don't exist: {dead}"


def test_no_work_is_empty(lookup):
    empty = [(c, b) for c, books in lookup._data.items() for b, chapters in books.items()
             if not any(v for v in (chapters or {}).values())]
    assert not empty, empty


def test_every_listed_work_can_be_read(bot_module, lookup):
    from bot_commands import books
    unreadable = []

    def walk(node, path):
        for item in node:
            if isinstance(item, tuple):
                walk(item[1], path + [item[0]])
            elif (lookup._resolve_book(item)[1] is None and not any(k in p for p in path for k in ONLINE)
                  and not lookup.get_verse(f"{item} 1")["found"]):
                unreadable.append((" > ".join(path[-2:]), item))
    walk(books.ROOT_BOOKS_TREE, [])
    assert not unreadable, unreadable


@pytest.mark.parametrize("ref, expect", [
    ("Physics 8.10:1", "Physics 8.10:1"),              # Book VIII: the import had stopped after Book I
    ("Topics 8.14", "Topics 8.14"),
    ("History of Animals 9.1", "History of Animals 9.1"),
    ("Bede 3.5:1", "Ecclesiastical History of the English People 3.5:1"),
    ("Golden Legend 54", "The Golden Legend 54"),
    ("Against Heresies 3.3:1", "Against Heresies 3.3:1"),
    ("Letters of Basil 38", "Letters of Basil 38"),
    ("Festal Letters 10", "Festal Letters of Athanasius 10"),
    ("Epistle of Jeremiah 1:5", "Baruch 6:5"),
    ("Epistle of Jeremiah 1", "Baruch 6"),
    ("Axiochus 3", "Axiochus 3"),
    ("Generation of Animals 2.1:1", "On the Generation of Animals 2.1:1"),
])
def test_works_that_couldnt_be_reached(lookup, ref, expect):
    result = lookup.get_verse(ref)
    assert result["found"] and result["reference"] == expect, result.get("error")


def test_saint_names_are_no_longer_books(lookup):
    for ref in ("Lucy 1:1", "Book I 1:1"):
        assert not lookup.get_verse(ref)["found"]
