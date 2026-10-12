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
    assert img.getpixel((600, 300)) == card.CARD_STYLES[style]["bg"]          # its own background colour


def test_parchment_is_unchanged_for_the_bible(card):
    img = Image.open(card._render_verse_card("John 3:16", "For God so loved the world.", "KJV"))
    assert img.getpixel((5, 5)) == (245, 239, 224)
