"""The secret "grok is this true?" reply (bot_commands/grok.py)."""
import datetime

import pytest


@pytest.fixture(scope="module")
def grok(bot_module):
    from bot_commands import grok
    return grok


@pytest.mark.parametrize("text", ["grok is this true", "@grok is that real?", "Grok, is this accurate",
                                  "grok confirm", "GROK IS THIS TRUE??"])
def test_asking_grok(grok, text):
    assert grok.asks_grok(text)


@pytest.mark.parametrize("text", ["I like grok", "is this true", "!grok is this true", "", "grok " + "x" * 400])
def test_not_asking_grok(grok, text):
    assert not grok.asks_grok(text)


def test_the_stamp(grok):
    assert grok.stamp(datetime.datetime(2026, 11, 1, 23, 57)) == "11:57 PM · Nov 1, 2026"
    assert grok.stamp(datetime.datetime(2026, 3, 5, 0, 4)) == "12:04 AM · Mar 5, 2026"


def test_every_answer_draws(grok):
    from PIL import Image
    import io
    for answer, _ in grok.ANSWERS:
        im = Image.open(io.BytesIO(grok.render(answer)))
        assert im.width == 900 and 150 < im.height < 400
    assert grok.pick() in {a for a, _ in grok.ANSWERS}
