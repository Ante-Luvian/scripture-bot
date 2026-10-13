"""!journey: every stop is a real place on the map, named in its verse."""
import asyncio
import re

import pytest
from PIL import Image


@pytest.fixture(scope="module")
def jo(bot_module):
    from bot_commands import journeys
    return journeys


def _squash(text: str) -> str:
    return re.sub(r"[^a-z]", "", text.lower())


def test_every_stop_is_named_in_its_verse(jo):
    from core import lookup
    places = jo.people.data()["places"]
    for key, (_, _, _, route) in jo.JOURNEYS.items():
        for slug, ref, spelling, note in route:
            assert slug in places and places[slug]["lat"] is not None, (key, slug)
            result = lookup.get_verse(ref)
            assert result.get("found"), (key, ref)
            assert _squash(spelling) in _squash(result["text"]), (key, ref, spelling)
            assert ref in places[slug]["verses"] or _squash(spelling) in _squash(places[slug]["name"]) \
                or spelling in ("Sichem", "Pihahiroth", "Kadeshbarnea", "Samothracia", "Cenchrea", "taverns"), \
                (key, slug, ref)


@pytest.mark.parametrize("query, key", [
    ("paul 2", "paul2"), ("Paul's second missionary journey", "paul2"), ("second journey", "paul2"),
    ("exodus", "exodus"), ("Abraham", "abraham"), ("rome", "rome"), ("shipwreck", "rome"),
    ("flight into egypt", "egypt"), ("paul1", "paul1"), ("zzz", None),
])
def test_finding_a_journey(jo, query, key):
    assert jo.find_journey(query) == key


def test_route_maps(jo):
    import bible_map
    for key in ("abraham", "rome", "jonah"):
        img = Image.open(bible_map.render_route(jo.JOURNEYS[key][0], [p for p, _, _ in jo.stops(key)],
                                                jo.people.located_places()))
        assert img.size == (bible_map.W, bible_map.H)


def test_journey_command(jo, fake_ctx):
    asyncio.run(jo.send_journey(fake_ctx, "paul 1"))
    sent = fake_ctx.sent[-1]
    assert sent["embed"].title == "🧭 Paul's first missionary journey" and sent["file"].filename == "journey.png"
    assert "**1. Antioch** — The church at Antioch sends out Barnabas and Saul (Acts 13:1)" in sent["embed"].description
    asyncio.run(jo.send_journey(fake_ctx, ""))
    assert fake_ctx.sent[-1]["embed"].title == "🧭 Journeys of the Bible"
