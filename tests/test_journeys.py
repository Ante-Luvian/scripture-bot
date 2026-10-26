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
    """In the bot's own text: the KJV, Skeat's Chaucer, Murray's Odyssey, Dryden's Aeneid."""
    from core import lookup
    places = jo.people.data()["places"]
    for key, (_, _, _, route) in jo.JOURNEYS.items():
        for slug, ref, spelling, note in route:
            result = lookup.get_verse(ref)
            assert result.get("found"), (key, ref)
            assert _squash(spelling) in _squash(result["text"]), (key, ref, spelling)
            if slug.startswith("@"):                            # (a place of PLACES: on the map, Europe to Africa)
                p = jo.place(slug)
                assert 30 < p["lat"] < 57 and -8 < p["lon"] < 30, (key, slug)
                continue
            assert slug in places and places[slug]["lat"] is not None, (key, slug)
            assert ref in places[slug]["verses"] or _squash(spelling) in _squash(places[slug]["name"]) \
                or spelling in ("Sichem", "Pihahiroth", "Kadeshbarnea", "Samothracia", "Cenchrea", "taverns"), \
                (key, slug, ref)


def test_the_places_of_legend_are_ringed_and_say_who_put_them_there(jo):
    """Homer's places are where antiquity put them: each ringed, its note naming who said so."""
    seen = set()
    for slug, ref, _, note in jo.JOURNEYS["odyssey"][3]:
        if jo.place(slug)["approx"] and slug not in seen | {"@ismarus"}:    # (Ismarus is real, only unfound)
            seen.add(slug)
            assert re.search(r"said|taken for", note), (slug, note)
    assert not jo.place("@ithaca")["approx"] and jo.place("@djerba")["approx"]


@pytest.mark.parametrize("query, key", [
    ("paul 2", "paul2"), ("Paul's second missionary journey", "paul2"), ("second journey", "paul2"),
    ("exodus", "exodus"), ("Abraham", "abraham"), ("rome", "rome"), ("shipwreck", "rome"),
    ("flight into egypt", "egypt"), ("paul1", "paul1"), ("zzz", None),
    ("canterbury", "canterbury"), ("Canterbury Tales", "canterbury"), ("odyssey", "odyssey"), ("ulysses", "odyssey"),
    ("aeneid", "aeneid"), ("Aeneas", "aeneid"),
])
def test_finding_a_journey(jo, query, key):
    assert jo.find_journey(query) == key


def test_route_maps(jo):
    import bible_map
    for key in ("abraham", "rome", "jonah"):
        img = Image.open(bible_map.render_route(jo.JOURNEYS[key][0], [p for p, _, _ in jo.stops(key)],
                                                jo.people.located_places()))
        assert img.size == (bible_map.W, bible_map.H)
    for key in ("canterbury", "odyssey", "aeneid"):
        file = asyncio.run(jo.map_file(key))
        assert file is not None and Image.open(file.fp).size == (bible_map.W, bible_map.H)


def test_journey_command(jo, fake_ctx):
    asyncio.run(jo.send_journey(fake_ctx, "paul 1"))
    sent = fake_ctx.sent[-1]
    assert sent["embed"].title == "🧭 Paul's first missionary journey" and sent["file"].filename == "journey.png"
    assert "**1. Antioch** — The church at Antioch sends out Barnabas and Saul (Acts 13:1)" in sent["embed"].description
    asyncio.run(jo.send_journey(fake_ctx, ""))
    listed = fake_ctx.sent[-1]["embed"]
    assert listed.title == "🧭 Journeys" and "**From other books**" in listed.description
    asyncio.run(jo.send_journey(fake_ctx, "odyssey"))
    sent = fake_ctx.sent[-1]["embed"]
    assert "**4. Djerba** — The Lotus-eaters' food makes men forget their homecoming (Djerba, said Polybius and " \
           "Strabo) (Odyssey 9:84)" in sent.description
    assert sent.footer.text.endswith("places: Wikipedia, and as placed in antiquity")
