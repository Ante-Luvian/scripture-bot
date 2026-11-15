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


def test_other_bibles_spellings_find_the_place(pp, fake_ctx):
    """A user typed Galaad (the Vulgate's and Douay-Rheims's Gilead) and Bethsura (the KJV Apocrypha's Beth-zur)."""
    gilead = pp.find("places", "Gilead")[0]
    for spelling in ("Galaad", "Γαλααδ", "Γαλαάδ", "גלעד", "Gilead"):
        assert pp.find("places", spelling)[0] == gilead, spelling
    assert pp.data()["places"][pp.find("places", "Bethsura")[0]]["name"] == "Beth-zur"
    # (not by another case of a Latin name: Magdala is not Migdol's Magdalum)
    assert pp.data()["places"][pp.find("places", "Magdala")[0]]["name"] != "Migdol"
    asyncio.run(pp.lookup_place(fake_ctx, "Galaad"))
    note = next(s["content"] for s in fake_ctx.sent if s.get("content"))
    assert note.startswith("**Galaad** is how the Vulgate and the Douay-Rheims spell **Gilead**")
    assert fake_ctx.sent[-1]["embed"].title.startswith("📍 Gilead")


def test_place_card_names_in_each_bible(pp):
    embed = pp.place_embed(pp.find("places", "Gilead")[0], with_map=False)
    names = next(f.value for f in embed.fields if f.name == "In each Bible")
    assert pp.data()["places"][pp.find("places", "Gilead")[0]]["names"]["hebrew"]["text"] in names
    assert "(Gilʻâd)" in names and "Γαλαάδ" in names and "**Latin (Vulgate):** Galaad" in names
    assert "**KJV, NRSV:** Gilead · **Douay-Rheims:** Galaad" in names
    bethzur = pp.place_embed(pp.find("places", "Beth-zur")[0], with_map=False)
    apocrypha = next(f for f in bethzur.fields if f.name.startswith("In the Apocrypha"))
    assert "1 Maccabees 4:29" in apocrypha.value
    assert "Bethsura" in next(f.value for f in bethzur.fields if f.name == "In each Bible")


def test_book_map(pp, fake_ctx):
    assert pp.book_query("Acts") == ("Acts", None, None)
    assert pp.book_query("Genesis 12") == ("Genesis", (12, 0), (12, 999))
    assert pp.book_query("1 Macc") == ("1 Maccabees", None, None)
    assert pp.book_query("1 Maccabees 4:36-61") == ("1 Maccabees", (4, 36), (4, 61))
    assert pp.book_query("Genesis 12 - 13") == ("Genesis", (12, 0), (13, 999))
    assert pp.book_query("Acts 13:1-14:28") == ("Acts", (13, 1), (14, 28))
    assert pp.book_query("Genesis 12:8") == ("Genesis", (12, 8), (12, 8))
    assert pp._where("Acts", (13, 1), (14, 28)) == "Acts 13:1-14:28"
    passage = dict(pp.book_places("1 Maccabees", (4, 36), (4, 61)))
    assert pp.find("places", "Beth-zur")[0] in passage                 # 4:61, Judas fortifies Beth-zur
    assert pp.find("places", "Gezer")[0] not in passage                 # Gazara is 4:15, before the passage
    assert pp.find("places", "Dan", prefix=False)                     # a place before a book (Daniel)
    acts = dict(pp.book_places("Acts"))
    assert acts[pp.find("places", "Jerusalem")[0]] > acts[pp.find("places", "Antioch")[0]] > 0
    asyncio.run(pp.lookup_place(fake_ctx, "Acts"))
    sent = fake_ctx.sent[-1]
    assert sent["embed"].title == "🗺️ The places of Acts" and sent["file"].filename == "map.png"
    assert "Jerusalem" in sent["embed"].description
    asyncio.run(pp.lookup_place(fake_ctx, "Genesis 12"))
    assert fake_ctx.sent[-1]["embed"].title == "🗺️ The places of Genesis 12"
    asyncio.run(pp.lookup_place(fake_ctx, "1 Maccabees 4:36-61"))
    assert fake_ctx.sent[-1]["embed"].title == "🗺️ The places of 1 Maccabees 4:36-61"
    asyncio.run(pp.lookup_place(fake_ctx, "Genesis 13-12"))
    assert "runs backwards" in fake_ctx.sent[-1]["content"]
    asyncio.run(pp.lookup_place(fake_ctx, "Genesis 99"))
    assert "has no chapter 99: it has 50" in fake_ctx.sent[-1]["content"]


def test_places_only_the_apocrypha_name(pp, fake_ctx):
    places = pp.data()["places"]
    modein = places[pp.find("places", "Modein")[0]]
    assert modein["lat"] and "1 Maccabees 2:1" in modein["apocrypha"] and not modein["verses"]
    bethulia = places[pp.find("places", "Bethulia")[0]]
    assert bethulia["lat"] is None and len(bethulia["apocrypha"]) > 10       # Judith's town: never found
    embed = pp.place_embed(bethulia["slug"], with_map=False)
    assert "not known" in embed.fields[0].value and "Pleiades" not in embed.footer.text
    assert "Pleiades" in pp.place_embed(modein["slug"], with_map=True).footer.text
    asyncio.run(pp.lookup_place(fake_ctx, "Modein"))
    assert fake_ctx.sent[-1]["file"].filename == "map.png"
    # the Apocrypha's other names for known places, and its Bozrah in Gilead (1 Macc 5:26), not Edom's
    assert "1 Maccabees 4:15" in places[pp.find("places", "Gezer")[0]]["apocrypha"]           # Gazara
    assert "1 Maccabees 5:26" in places["bozrah_257"]["apocrypha"]
    assert "1 Maccabees 5:26" not in places["bozrah_256"]["apocrypha"]


def test_kjv_spelling_from_its_text(pp):
    magdala = pp.find("places", "Magdala")
    assert pp.data()["places"][magdala[0]]["verses"] == ["Matthew 15:39"]                      # not Migdol
    assert pp.find("places", "Shushan")[0] == pp.find("places", "Susa")[0]
