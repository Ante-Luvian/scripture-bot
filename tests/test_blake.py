"""William Blake: his texts in the library, and !blake for the illuminated books."""
import asyncio
import re

import pytest

BOOKS = {
    "songs": {"title": "Songs of Innocence and of Experience", "year": "1794", "about": "Contrary states.",
              "copy": "Z", "plates": [{"object": n, "file": f"File:Songs {n}.jpg",
                                       "image": f"https://upload.wikimedia.org/songs{n}.jpg", "page": f"https://c/{n}"}
                                      for n in range(1, 55)]},
    "thel": {"title": "The Book of Thel", "year": "1789", "about": "Thel asks why she must fade.", "copy": "F",
             "plates": [{"object": n, "file": f"File:Thel {n}.jpg", "image": f"https://u/thel{n}.jpg",
                         "page": f"https://c/t{n}"} for n in range(1, 9)]},
}


@pytest.fixture
def bl(bot_module, monkeypatch):
    from bot_commands import blake
    monkeypatch.setattr(blake, "books", lambda: BOOKS)
    return blake


@pytest.mark.parametrize("query, key", [("songs", "songs"), ("Songs of Innocence and of Experience", "songs"),
                                        ("tyger", "songs"), ("The Book of Thel", "thel"), ("book of thel", "thel"),
                                        ("thel", "thel"), ("zz", None)])
def test_find(bl, query, key):
    assert bl.find(query) == key


def test_plates_turn(bl, fake_ctx):
    asyncio.run(bl.send_blake(fake_ctx, "songs 42"))
    sent = fake_ctx.sent[-1]
    assert sent["embed"].title == "Songs of Innocence and of Experience — plate 42 of 54"
    assert sent["embed"].image.url == "https://upload.wikimedia.org/songs42.jpg"
    ids = [b.item.custom_id for b in sent["view"].children]
    assert ids == ["blake:back:songs:40", "blake:next:songs:42"]
    first = bl.plate_message("thel", 0)["embed"]
    assert first.description.startswith("*Thel asks why she must fade.*\n\nDoes the Eagle know")   # then its words
    assert "copy F" in first.footer.text
    two = bl.plate_message("thel", 7)["view"].children                   # the last plate's ▶ goes round to the first
    assert two[1].item.custom_id == "blake:next:thel:0"


def test_errors_and_list(bl, fake_ctx):
    asyncio.run(bl.send_blake(fake_ctx, "thel 9"))
    assert "has 8 plates" in fake_ctx.sent[-1]["content"]
    asyncio.run(bl.send_blake(fake_ctx, "zz"))
    assert "don't have a Blake book" in fake_ctx.sent[-1]["content"]
    asyncio.run(bl.send_blake(fake_ctx, "list"))
    assert "`!blake thel`" in fake_ctx.sent[-1]["embed"].description
    asyncio.run(bl.send_blake(fake_ctx, ""))
    assert "plate" in fake_ctx.sent[-1]["embed"].title


def test_the_built_plates(bot_module):
    from bot_commands import blake
    books = blake.books()
    assert {"songs", "thel", "visions", "europe", "urizen"} <= set(books)
    for key, book in books.items():
        assert len(book["plates"]) >= 5, key
        assert all(re.match(r"https://[a-z.]+\.wikimedia\.org/", p["image"]) for p in book["plates"]), key
        objects = [p["object"] for p in book["plates"]]
        assert objects == sorted(objects), key


@pytest.mark.parametrize("ref, start", [
    ("Songs of Experience 12", "*The Tiger*\nTiger, tiger, burning bright"),
    ("Songs of Innocence 4", "*The Lamb*"), ("Thel 0", "*Thel's Motto*"),
    ("Marriage of Heaven and Hell 4:2", "Drive your cart and your plough over the bones of the dead."),
])
def test_blakes_words(lookup, ref, start):
    assert start in lookup.get_verse(ref)["text"]
