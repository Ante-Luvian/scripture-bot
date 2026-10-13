"""!who and !place: people and places of the Bible, and the map cards."""
import asyncio

import pytest
from PIL import Image


@pytest.fixture(scope="module")
def pp(bot_module):
    from bot_commands import people
    return people


def test_one_person(pp):
    [ruth] = pp.find("people", "Ruth")
    embed = pp.person_embed(ruth)
    assert embed.title == "👤 Ruth" and "Moabite" in (embed.description or "") + str(embed.fields)
    family = embed.fields[0].value
    assert "Boaz" in family and "Obed" in family
    named = next(f for f in embed.fields if f.name.startswith("Named in"))
    assert named.value.startswith("Ruth 1:4")


def test_namesakes(pp):
    marys = pp.find("people", "Mary")
    labels = [pp.label("people", s) for s in marys]
    assert "Mary Magdalene" in labels and "Mary (Mother of Jesus)" in labels
    assert not pp._clear_winner("people", marys)                  # ask which one
    assert pp._clear_winner("people", pp.find("people", "David"))
    assert pp.find("people", "John the Baptist")[0] == pp.find("people", "John")[0]
    assert pp.find("people", "Saint Paul") == pp.find("people", "Paul")


def test_family_menu_walks_the_tree(pp):
    [ruth] = pp.find("people", "Ruth")
    view = pp.PersonView(ruth)
    options = {o.label: o.description for o in view.select.options}
    assert options["Obed, son of Boaz"] == "Ruth's child"                 # several Obeds
    assert options["Boaz"] == "Ruth's spouse"


def test_compact_refs(pp):
    assert pp.compact_refs(["Genesis 12:8", "Genesis 13:3", "Joshua 7:2"]) == "Genesis 12:8; 13:3 · Joshua 7:2"
    assert pp.compact_refs([f"Psalms 1:{i}" for i in range(1, 60)], limit=3).endswith("… and 56 more")


def test_place_card(pp):
    bethel = pp.find("places", "Bethel")
    assert pp.data()["places"][bethel[0]]["name"] == "Bethel (of Palestine)"      # the well-known one first
    embed = pp.place_embed(bethel[0], with_map=True)
    facts = embed.fields[0].value
    assert "31.93" in facts and "approximate" not in facts
    assert embed.image.url == "attachment://map.png"
    assert pp.find("places", "Sea of Galilee") and pp.find("places", "Rome")


def test_map_card(pp):
    import bible_map
    places = pp.located_places()
    for name in ("Bethel", "Rome", "Babylon"):
        me = next(p for p in places if p["slug"] == pp.find("places", name)[0])
        img = Image.open(bible_map.render_map(me, places))
        assert img.size == (bible_map.W, bible_map.H)
        assert img.getpixel((bible_map.W // 2, bible_map.H // 2))[0] > 150     # the red marker in the middle
    rome = next(p for p in places if p["slug"] == pp.find("places", "Rome")[0])
    bethel = next(p for p in places if p["slug"] == pp.find("places", "Bethel")[0])
    assert bible_map.span_for(rome, places) > 3 * bible_map.span_for(bethel, places)   # sparse: zoomed out


def test_who_command(pp, fake_ctx):
    asyncio.run(pp.lookup_person(fake_ctx, "Ruth"))
    assert fake_ctx.sent[-1]["embed"].title == "👤 Ruth"
    asyncio.run(pp.lookup_person(fake_ctx, "Mary"))
    assert "people called Mary" in fake_ctx.sent[-1]["embed"].title
    asyncio.run(pp.lookup_person(fake_ctx, "Xyzzy"))
    assert "don't know anyone" in fake_ctx.sent[-1]["content"]


def test_place_command(pp, fake_ctx):
    asyncio.run(pp.lookup_place(fake_ctx, "Jericho"))
    sent = fake_ctx.sent[-1]
    assert sent["embed"].title.startswith("📍 Jericho") and sent["file"].filename == "map.png"
