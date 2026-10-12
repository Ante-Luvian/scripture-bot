"""Usage stats: which book a looked-up reference counts toward."""
import pytest


@pytest.mark.parametrize("ref, book", [
    ("John 3:16", "John"),
    ("1 Corinthians 13:4", "1 Corinthians"),          # was counted as "1"
    ("Song of Solomon 2:1–3", "Song of Solomon"),      # was "Song"
    ("The Thunder, Perfect Mind 1:1", "The Thunder, Perfect Mind"),   # was "The"
    ("Book of Enoch 1:9", "Book of Enoch"),            # was "Book"
    ("Psalms 23", "Psalms"),
    ("John 3:16 (ESV)", "John"),
    ("Rig Veda 10.121:9", "Rig Veda"),
    ("Berakhot 2a", "Berakhot"),
    ("Kitáb-i-Aqdas ¶1", "Kitáb-i-Aqdas"),
    ("Shepherd of Hermas, Similitude 9.1.3 (ch. 78)", "Shepherd of Hermas, Similitude"),
    ("Gilgamesh Tablet 1 1", "Gilgamesh Tablet"),
])
def test_book_from_reference(bot_module, ref, book):
    from core import book_from_reference
    assert book_from_reference(ref) == book
