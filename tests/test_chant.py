"""The ancient hymns (scripts/build_chant.py): Gregorian chant from GregoBase; and the Sacred Harp,
every song sung (scripts/build_sacred_harp.py)."""
import json

import pytest

from core import ROOT

MORE = ROOT / "data" / "hymns" / "more_hymns.json"


@pytest.fixture(scope="module")
def hymns(bot_module):
    from bot_commands import hymns
    return hymns


@pytest.fixture(scope="module")
def more():
    return json.loads(MORE.read_text(encoding="utf-8"))["hymns"]


def _one(hymns, query):
    found = hymns.find_hymns(query)
    assert found, query
    return found[0]


@pytest.mark.parametrize("query, opening", [
    ("Te lucis ante terminum", "Te lucis ante términum,"),
    ("Pater noster", "Præcéptis salutáribus móniti,"),              # the Mass one, from the Graduale Romanum
    ("Salve Regina", "Salve, Regína,"),
    ("Veni Creator Spiritus", "Veni Creátor Spíritus,"),
    ("Dies irae", "Dies iræ, dies illa,"),
    ("Ubi caritas", "Ubi cáritas et amor"),
    ("Vexilla Regis", "Vexílla Regis pródeunt"),
])
def test_the_requested_chants(hymns, query, opening):
    hymn = _one(hymns, query)
    assert hymn["stanzas"][0].startswith(opening), hymn["stanzas"][0][:60]
    assert hymn.get("language") == "Latin" and hymns.audio_path(hymn) is not None


def test_stanzas_and_melody(hymns):
    veni = _one(hymns, "Veni Creator Spiritus")
    assert len(veni["stanzas"]) == 7                                  # its later verses, kept apart in the corpus
    te_lucis = _one(hymns, "Te lucis ante terminum")
    assert "(" not in te_lucis["title"] and len(te_lucis["stanzas"]) == 3      # the plain version, not a variant
    assert te_lucis["seconds"] > 40                                   # every stanza is sung, not just the first


def test_babylon_is_fallen(hymns):
    hymn = _one(hymns, "Babylon is fallen")
    assert hymn["stanzas"][0].startswith("Hail the day so long expected")
    assert "Chute" in hymn["composer"] and hymns.audio_path(hymn) is not None and hymn["audio_kind"] == "sung"
    assert hymn["scripture"] == ["Revelation 18:2", "Revelation 18:21"] and "Shaker" in hymn["author"]


def test_the_sacred_harp(hymns):
    _, harp = hymns.hymn_list("harp")
    assert len(harp) >= 500
    idumea = _one(hymns, "Idumea")
    assert idumea["stanzas"][0].split("\n") == ["And am I born to die?", "To lay this body down!",
                                                "And must my trembling spirit fly", "Into a world unknown?"]
    assert "Wesley" in idumea["author"] and "Davisson" in idumea["composer"] and idumea["meter"] == "6.6.8.6"
    assert _one(hymns, "Sacred Harp 155")["title"] == "Northfield"                # by its number in the book
    for h in harp:
        assert hymns.audio_path(h) is not None and h["audio_kind"] == "sung", h["title"]
        assert all(s.strip() and "\n\n" not in s for s in h["stanzas"]), h["title"]


def test_names_keys_and_audio(hymns, more):
    titles = [h["title"] for h in hymns.hymns()]
    assert len(titles) == len(set(titles))
    keys = [hymns.hymn_key(h) for h in hymns.hymns()]
    assert len(keys) == len(set(keys))                                # each hymn's buttons find it
    assert len(more) >= 400
    for h in more:
        assert h["stanzas"] and all(s.strip() for s in h["stanzas"]), h["title"]
        if h.get("audio"):
            assert hymns.audio_path(h) is not None, h["title"]
        assert "<" not in " ".join(h["stanzas"]), h["title"]          # no gabc markup left


def test_midi_posts_just_the_tune(hymns, fake_ctx):
    import asyncio
    asyncio.run(hymns.send_hymn_tune(fake_ctx, "Salve Regina"))
    sent = fake_ctx.sent[-1]
    assert "Salve Regina" in sent["content"] and sent["file"].filename.endswith(".ogg")
    assert "embed" not in sent                                   # no words


def test_midi_with_no_tune_says_so(hymns, fake_ctx):
    import asyncio
    asyncio.run(hymns.send_hymn_tune(fake_ctx, "zzzz no such hymn"))
    assert "no tune" in fake_ctx.sent[-1]["content"]


def test_hymnlist_sections(hymns):
    heading, chant = hymns.hymn_list("chant")
    assert len(chant) >= 400 and all(h["language"] == "Latin" for h in chant)
    _, english = hymns.hymn_list("hymns")
    assert "Amazing Grace" in [h["title"] for h in english] and not set(map(id, english)) & set(map(id, chant))
    _, sequences = hymns.hymn_list("chant sequences")
    assert "Dies irae" in [h["title"] for h in sequences]
    _, harp = hymns.hymn_list("harp")
    assert "Babylon Is Fallen" in [h["title"] for h in harp] and "Idumea" in [h["title"] for h in harp]
    _, every = hymns.hymn_list("")
    assert len(every) == len(hymns.hymns())
    assert "Babylon Is Fallen" in hymns.hymn_list_overview().description or "Sacred Harp" in hymns.hymn_list_overview().description
    page = hymns.hymn_list_embed("Every hymn", every, 0)
    assert page.description.count("\n") == hymns.LIST_PAGE - 1


def test_hymnlist_pages_keep_their_items(hymns):
    """Turning a page refills the same menu instead of replacing it: a replaced menu left the
    message's old one unanswered ("This interaction failed") when an edit didn't go through."""
    import asyncio

    async def check():
        view = hymns.HymnListView(*hymns.hymn_list("chant"))
        items, first = list(view.children), view.select.options[0].label
        assert len(items) == 3 and len(view.select.options) == hymns.LIST_PAGE
        view.page = 1
        view._fill()
        assert list(view.children) == items and view.select.options[0].label != first
        assert view.select.callback == view._chosen
        single = hymns.HymnListView(*hymns.hymn_list("babylon"))        # one page: no arrows
        assert single.children == [single.select] and len(single.select.options) == 1
    asyncio.run(check())


def test_hymn_harp_is_a_random_sacred_harp_song(hymns, fake_ctx):
    import asyncio
    titles = {h["title"] for h in hymns.hymns() if hymns.shelf(h) == "harp"}
    for query in ("harp", "Sacred Harp"):
        asyncio.run(hymns.send_hymn_search(fake_ctx, query))
        assert fake_ctx.sent[-1]["embed"].title.split(" — ")[0].lstrip("🎵 ").strip() in titles or \
            any(t in fake_ctx.sent[-1]["embed"].title for t in titles)


@pytest.mark.parametrize("title", ["Credo I", "Credo III", "Kyrie VIII", "Gloria XV", "Sanctus XVIII", "Agnus XVIII",
                                   "Requiem aeternam (Introit of the Requiem Mass)", "Libera me (Responsory of the Requiem)"])
def test_the_mass_and_the_requiem(hymns, title):
    hymn = next(h for h in hymns.hymns() if h["title"] == title)
    assert hymns.audio_path(hymn) is not None and hymn["stanzas"]


def test_english_translations(hymns):
    credo = next(h for h in hymns.hymns() if h["title"] == "Credo III")
    t = hymns.translation(credo)
    assert t and t["stanzas"][0].startswith("I believe in one God the Father Almighty")
    assert "Book of Common Prayer" in t["source"]
    view_buttons = [getattr(i, "item", i).label for i in hymns.hymn_view(credo).children]
    assert "English" in view_buttons
    embed = hymns.english_embed(credo)
    assert embed.title == "🇬🇧 Credo III, in English" and "Pontius Pilate" in embed.description
    stabat = next(h for h in hymns.hymns() if h["title"] == "Stabat Mater")
    assert hymns.translation(stabat)["stanzas"][0].startswith("At the Cross her station keeping")
    assert "Edward Caswall" in hymns.english_embed(stabat).footer.text
    tantum = hymns.translation(next(h for h in hymns.hymns() if h["title"] == "Tantum ergo"))
    assert tantum["stanzas"][0].startswith("Down in adoration falling") and len(tantum["stanzas"]) == 2
    media = next(h for h in hymns.hymns() if h["title"] == "Media vita")
    assert "In te speraverunt" in hymns.english_embed(media).footer.text
    salve = next(h for h in hymns.hymns() if h["title"] == "Amazing Grace")
    assert hymns.translation(salve) is None and "English" not in [getattr(i, "item", i).label for i in hymns.hymn_view(salve).children]
