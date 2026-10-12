"""!books <name>: a collection, an author, or a single book."""
import asyncio

import pytest

from conftest import FakeCtx


def _books(bot_module, query):
    ctx = FakeCtx()
    asyncio.run(bot_module.bot.get_command("books").callback(ctx, section=query))
    return ctx.sent[0]


@pytest.mark.parametrize("query, book, chapters", [
    ("Genesis", "Genesis", 50), ("Jn", "John", 21), ("Confessions", "Confessions", None), ("Iliad", "Iliad", 24),
])
def test_a_book_opens_its_chapter_picker(bot_module, query, book, chapters):
    msg = _books(bot_module, query)
    view = msg["view"]
    name, labels, mode = view.stack[-1]
    assert name == book and mode == "verse"
    if chapters:
        assert len(labels) == chapters
    assert book in msg["embed"].title
    assert any(getattr(b, "label", "") == "◀ Back" for b in view.children)      # back to the whole library


def test_collections_and_authors_still_come_first(bot_module):
    assert _books(bot_module, "Homer")["embed"].title == "📚 Homer"
    assert _books(bot_module, "Augustine")["embed"].title == "📚 Augustine of Hippo"


def test_unknown(bot_module):
    assert "not found" in _books(bot_module, "xyzzy")["content"]
