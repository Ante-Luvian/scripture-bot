"""/verse book-name suggestions."""
import asyncio

import pytest


@pytest.fixture(scope="module")
def slash(bot_module):
    from bot_commands import slash
    return slash


def test_prefix_suggests_the_book(slash):
    assert slash.book_suggestions("Hab")[0] == "Habakkuk"
    assert slash.book_suggestions("gen")[0] == "Genesis"          # case-insensitive


def test_bible_books_first_in_bible_order(slash):
    got = slash.book_suggestions("")
    assert got[:3] == ["Genesis", "Exodus", "Leviticus"] and len(got) == 25
    jo = slash.book_suggestions("Jo")
    assert jo.index("Joshua") < jo.index("Job") < jo.index("Joel") < jo.index("Jonah") < jo.index("John")


def test_abbreviation_suggests_its_book(slash):
    assert "John" in slash.book_suggestions("Jn")


def test_partial_match_finds_non_bible_works(slash):
    assert "Book of Enoch" in slash.book_suggestions("Enoch")


def test_once_a_chapter_is_typed_text_is_kept(slash):
    assert slash.book_suggestions("John 3:16") == ["John 3:16"]
    assert slash.book_suggestions("1 John 4") == ["1 John 4"]


def test_numbered_books_still_suggested(slash):
    assert slash.book_suggestions("1 Jo")[0] == "1 John"


def test_limits(slash):
    assert all(len(b) <= 100 for b in slash.book_suggestions("a"))
    assert len(slash.book_suggestions("a")) <= 25


def test_autocomplete_returns_choices(slash):
    choices = asyncio.run(slash._verse_autocomplete(None, "Hab"))
    assert choices[0].name == choices[0].value == "Habakkuk"
