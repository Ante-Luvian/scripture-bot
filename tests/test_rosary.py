"""!rosary: the day's mysteries, a decade a page."""
import asyncio
import datetime

import pytest

from tests.conftest import needs_sung_chant

D = datetime.date


@pytest.fixture(scope="module")
def ro(bot_module):
    from bot_commands import rosary
    return rosary


@pytest.mark.parametrize("day, kind", [
    (D(2026, 10, 12), "joyful"), (D(2026, 10, 13), "sorrowful"), (D(2026, 10, 14), "glorious"),
    (D(2026, 10, 15), "luminous"), (D(2026, 10, 16), "sorrowful"), (D(2026, 10, 17), "joyful"),
    (D(2026, 10, 18), "glorious"),
])
def test_the_week(ro, day, kind):
    assert ro.mysteries_for(day) == kind


# each mystery's passage really tells it (checked in the bot's own Bible text)
KEYWORDS = {"Luke 1:26-38": "Gabriel", "Luke 1:39-56": "Elisabeth", "Luke 2:1-20": "manger",
            "Luke 2:22-38": "Simeon", "Luke 2:41-52": "doctors", "Matthew 3:13-17": "baptized",
            "John 2:1-11": "Cana", "Mark 1:14-15": "kingdom", "Matthew 17:1-8": "transfigured",
            "Matthew 26:26-29": "bread", "Matthew 26:36-46": "Gethsemane", "John 19:1": "scourged",
            "Matthew 27:27-31": "thorns", "Luke 23:26-32": "cross", "Luke 23:33-46": "Calvary",
            "Matthew 28:1-10": "risen", "Acts 1:6-11": "taken up", "Acts 2:1-13": "tongues",
            "Revelation 12:1": "crown"}


def test_the_passages(ro):
    refs = [ref for ms in ro.MYSTERIES.values() for _, _, ref in ms if ref]
    assert sorted(refs) == sorted(KEYWORDS)
    for ref, word in KEYWORDS.items():
        assert word.lower() in ro._passage(ref).lower(), ref


def test_the_pages(ro):
    first = ro.page_embed("glorious", 0)
    assert "Apostles' Creed" in first.description and "The Resurrection" in first.fields[0].value
    decade = ro.page_embed("joyful", 1)
    assert "The First Joyful Mystery: The Annunciation" in decade.title
    assert "Gabriel" in decade.fields[0].value and "ten times" in decade.fields[1].value
    assumption = ro.page_embed("glorious", 4)
    assert "tradition" in assumption.fields[0].value
    assert "Hail, Holy Queen" in ro.page_embed("joyful", 6).description
    for page in range(ro.PAGES):
        ids = [getattr(b, "item", b).custom_id for b in ro.rosary_view("sorrowful", page).children]
        assert len(ids) == len(set(ids)) == (1 if page in (0, ro.PAGES - 1) else 2)


@needs_sung_chant                      # (it sends the sung chant)
def test_the_command(ro, fake_ctx):
    asyncio.run(ro.send_rosary(fake_ctx, "sorrowful"))
    sent = fake_ctx.sent[-1]
    assert "Sorrowful" in sent["content"] and sent["file"].filename == "Ave_Maria_sung.ogg"
    asyncio.run(ro.send_rosary(fake_ctx, ""))
    assert "mysteries, the" in fake_ctx.sent[-1]["content"]
    asyncio.run(ro.send_rosary(fake_ctx, "purple"))
    assert "Which mysteries?" in fake_ctx.sent[-1]["content"]
