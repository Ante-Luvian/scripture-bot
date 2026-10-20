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


def test_every_work_in_the_library_is_in_the_tree(bot_module, lookup):
    """The hand-kept !books tree had drifted (~200 of the Fathers' treatises weren't in it);
    books._complete_tree adds what it leaves out."""
    from bot_commands import books
    listed = set()

    def walk(node):
        for item in node:
            if isinstance(item, tuple):
                walk(item[1])
            else:
                listed.add(item)
                listed.add(lookup._resolve_exact(item)[1])
    walk(books.ROOT_BOOKS_TREE)
    left_out = [(c, b) for c, bs in lookup._data.items() for b, ch in bs.items()
                if b not in listed and b not in books._SHOWN_ELSEWHERE and any(ch.values())
                and lookup._resolve_exact(b) == (c, b)]
    assert not left_out, left_out[:20]


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


def test_works_that_share_a_title_can_all_be_read(lookup):
    """Two Fathers' works of one title: the later file's used to replace the earlier's (some 25 lost).
    The one that answered to the title before still does; the others carry their author's name."""
    assert lookup.get_verse("On Prayer 1:1")["source"] == "trans. William A. Curtis"       # Origen's
    assert lookup.get_verse("On Prayer (Tertullian) 1:1")["found"]
    assert lookup.get_verse("Ecclesiastical History (Socrates Scholasticus) 1:1")["found"]
    assert lookup.get_verse("ecclesiastical history socrates 1:1")["reference"].startswith("Ecclesiastical History (Socrates")
    assert lookup.get_verse("On the Holy Spirit (Basil the Great) 1:1")["found"]
    assert len(lookup._renamed["Letters"]) >= 4 and len(lookup._renamed["Fragments"]) >= 5


@pytest.mark.parametrize("book, chapters", [
    ("Tractates on the Gospel of John", 124),        # held one index line (scripts/build_fathers.py)
    ("The Great Catechism", 41),                    # held only its one-page summary
    ("On Prayer", 20),                              # Origen's: held a title line
])
def test_the_fathers_repaired(lookup, book, chapters):
    corpus, name = lookup._resolve_book(book)
    assert corpus == "patristics" and len(lookup._data[corpus][name]) == chapters


def test_de_principiis_has_all_four_books(lookup):
    keys = lookup._data["patristics"]["De Principiis"]
    assert {k.split(".")[0] for k in keys} >= {"1", "2", "3", "4"}
    assert "1. I know that some" in lookup.get_verse("De Principiis 1.1:1")["text"][:40]    # (Books I-II untouched)


def test_saint_names_are_no_longer_books(lookup):
    for ref in ("Lucy 1:1", "Book I 1:1"):
        assert not lookup.get_verse(ref)["found"]
