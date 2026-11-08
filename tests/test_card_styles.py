"""Cards dressed in their tradition's style."""
import pytest
from PIL import Image


@pytest.fixture(scope="module")
def card(bot_module):
    from bot_commands import card
    return card


@pytest.mark.parametrize("reference, style", [
    ("John 3:16", "parchment"), ("Tao Te Ching 1:1", "ink"), ("I Ching 1:1", "ink"),
    ("Dhammapada 14:183", "buddhist"), ("Bhagavad Gita 2:47", "hindu"), ("Divan of Hafiz 1:1", "persian"),
    ("Quran 1:1", "persian"), ("Hovamol 77", "norse"), ("Meditations 4:3", "classical"),
    ("Republic 514a", "classical"), ("Sutta Nipata 2.1:221", "buddhist"), ("Confessions 1.1:1", "parchment"),
])
def test_style_follows_the_book(card, reference, style):
    assert card.style_for_reference(reference) == style


@pytest.mark.parametrize("style", ["parchment", "ink", "persian", "buddhist", "hindu", "norse", "classical"])
def test_every_style_renders(card, style):
    buf = card._render_verse_card("Test 1:1", "A short test passage.", "Test source", "a question?", style)
    img = Image.open(buf)
    assert img.size[0] == 1200
    assert img.getpixel((70, 300)) == card.CARD_STYLES[style]["bg"]           # its own background colour (beside the text)


def test_verse_keeps_its_lines(card):
    """A poem's card (the Edda's): each line whole, never wrapped, the caesura a spaced middle dot, not a bar."""
    from unittest import mock
    drawn = []
    from PIL import ImageDraw
    original = ImageDraw.ImageDraw.text
    with mock.patch.object(ImageDraw.ImageDraw, "text", lambda self, xy, text, *a, **k: drawn.append(text) or original(self, xy, text, *a, **k)):
        card._render_verse_card("Hovamol 110", "On his ring swore Othin · the oath, methinks;\nWho now his troth shall trust?",
                                "Bellows", "", "norse", verse=True)
    assert "On his ring swore Othin · the oath, methinks;" in drawn and "Who now his troth shall trust?" in drawn


def test_a_poem_is_set_as_printed(card):
    """Shakespeare's poems (the owner, 2026-11-07): upright, flush left, every other line of a stanza indented."""
    from unittest import mock
    from PIL import ImageDraw
    placed, original = [], ImageDraw.ImageDraw.text
    with mock.patch.object(ImageDraw.ImageDraw, "text",
                           lambda self, xy, text, *a, **k: placed.append((xy[0], text, k.get("font"))) or original(self, xy, text, *a, **k)):
        card._render_verse_card("Sonnet 1", "One line here,\nTwo line here,\nThree line here,\nFour line here,\n\nFive",
                                "Folger", "", "parchment", poem=True)
    x = {t: (left, f) for left, t, f in placed}
    assert x["One line here,"][0] == x["Three line here,"][0] < x["Two line here,"][0] == x["Four line here,"][0]
    assert x["Five"][0] == x["One line here,"][0]                                  # (a new stanza starts flush)
    assert "georgia.ttf" in x["One line here,"][1].path                            # (upright: not georgiai)


def test_parchment_is_unchanged_for_the_bible(card):
    img = Image.open(card._render_verse_card("John 3:16", "For God so loved the world.", "KJV"))
    assert img.getpixel((5, 5)) == (245, 239, 224)
