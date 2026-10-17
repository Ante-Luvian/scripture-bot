"""!divineliturgy: the Liturgy of St John Chrysostom, page by page."""
import asyncio

import pytest


@pytest.fixture(scope="module")
def dl(bot_module):
    from bot_commands import divine_liturgy
    return divine_liturgy


def test_the_text(dl):
    pages = dl.liturgy()["pages"]
    assert len(pages) > 30 and all(len(p["text"]) <= 4096 for p in pages)
    names = [n for n, _ in dl.sections()]
    assert names[0] == "The Great Litany" and names[-1] == "The Dismissal" and "The Creed" in names
    text = "\n".join(p["text"] for p in pages)
    assert "Blessed be the kingdom of the Father" in text and "I believe in One God" in text
    assert "*The Choir.* Amen." in text                                     # rubrics in italics
    assert "mw-parser" not in text and "pagenum" not in text and "<" not in text


def test_find_section(dl):
    creed = dl.find_section("creed")
    assert dl.liturgy()["pages"][creed]["section"] == "The Creed"
    assert dl.find_section("anaphora") is not None and dl.find_section("zzz") is None


def test_the_view(dl):
    n = len(dl.liturgy()["pages"])
    for page in (0, 5, n - 1):
        items = [getattr(i, "item", i) for i in dl.liturgy_view(page).children]
        ids = [i.custom_id for i in items]
        assert len(ids) == len(set(ids))
        assert len(items) == (2 if page in (0, n - 1) else 3)            # ◀ / ▶ and the menu
    menu = [getattr(i, "item", i) for i in dl.liturgy_view(0).children][-1]
    assert len(menu.options) == len(dl.sections())


def test_command(dl, fake_ctx):
    asyncio.run(dl.send_liturgy(fake_ctx, ""))
    sent = fake_ctx.sent[-1]
    assert "Divine Liturgy" in sent["content"] and sent["embed"].title == "☦️ The Great Litany"
    asyncio.run(dl.send_liturgy(fake_ctx, "creed"))
    assert fake_ctx.sent[-1]["embed"].title == "☦️ The Creed"
    asyncio.run(dl.send_liturgy(fake_ctx, "purple"))
    assert "no part of the Liturgy" in fake_ctx.sent[-1]["content"]
