"""!dore: Gustave Doré's engravings, and the 🖼️ Doré button under !verse."""
import asyncio
import re

import pytest


@pytest.fixture(scope="module")
def do(bot_module):
    from bot_commands import dore
    return dore


def test_the_whole_set(do, lookup):
    plates = do.plates()
    bible = [p for p in plates if p["set"] == "bible"]
    assert len(bible) == 241                                   # all of the 1866 Bible's plates
    assert {"Tobit", "Judith", "Baruch", "Susanna", "Bel and the Dragon", "1 Maccabees", "2 Maccabees"} \
        <= {p["book"] for p in bible}                         # the Apocrypha too
    assert sum(p["set"] == "milton" for p in plates) == 50
    assert sum(p["set"] == "dante" for p in plates) >= 130
    for p in plates:
        assert re.match(r"https://[a-z.]+\.wikimedia\.org/", p["image"]), p["key"]
    for p in bible:                                            # every reference opens in the bot
        assert lookup.get_verse(f"{p['book']} {p['chapter']}:{p['start']}")["found"], p["key"]
    assert len({p["key"] for p in plates}) == len(plates)


@pytest.mark.parametrize("ref, title", [
    ("Genesis 11:4", "The Tower of Babel"), ("Judith 13:8", "Judith and Holofernes"),
    ("Paradise Lost 12:644", "Paradise Lost 12:644"), ("Mark 14:22", "The Last Supper"),
])
def test_the_button_under_verse(do, lookup, ref, title):
    button = next((b for b in do.art_buttons(lookup.get_verse(ref)) if b.artist == "dore"), None)
    assert button is not None and button.item.custom_id.startswith("dore:")
    shown = [do.by_key()[k] for k in button.keys]
    assert any(do.plate_embed(p).title == f"🖼️ {title}" for p in shown)


def test_every_picture_has_its_text_as_caption(do):
    """Bible plates are captioned with their verses, like Dante's and Milton's with their lines."""
    magi = next(p for p in do.plates() if p["title"] == "The Wise Men Guided by the Star")
    d = do.plate_embed(magi).description
    assert d.startswith("**Matthew 2:1–2**\n1 *Now when Jesus was born in Bethlehem")
    assert "\n2 *Saying, Where is he that is born King of the Jews?" in d
    for p in do.plates() + do.plates("blake"):
        if p["start"]:
            assert "*" in do.plate_embed(p).description.replace("**", ""), p["key"]   # its text, in italics
    sizes = [sum(len(e.description or "") + len(e.title) for e in map(do.plate_embed, ps))
             for ps in zip(*[iter(do.plates() + do.plates("blake"))] * do.MAX_SHOWN)]
    assert max(sizes) < 5000                                                    # (Discord: 6,000 a message)


def test_no_button_without_a_picture(do, lookup):
    assert do.art_buttons(lookup.get_verse("John 3:16")) == []
    assert do.art_buttons(lookup.get_verse("Leviticus 3:1")) == []


def test_dante_by_line(do, lookup):
    """Each Dante plate is tied to the lines it shows (Charon's boat: Inferno 3:82-84)."""
    button = do.art_buttons(lookup.get_verse("Inferno 3:82"))[0]
    assert [(do.by_key()[k]["chapter"], do.by_key()[k]["start"]) for k in button.keys] == [(3, 82)]
    assert do.for_result(lookup.get_verse("Inferno 3:40"), "dore") == []
    dante = [p for p in do.plates() if p["set"] == "dante" and p["book"]]
    assert sum(p["book"] == "Inferno" for p in dante) == 75                  # (all of them)
    for p in dante:                                                         # the lines open in the bot
        assert lookup.get_verse(f"{p['book']} {p['chapter']}:{p['start']}")["found"], p["key"]
        assert p["quote"].count("\n") == p["end"] - p["start"]


def test_several_are_listed_with_their_references(do, fake_ctx):
    asyncio.run(do.send_dore(fake_ctx, "Inferno 1"))
    sent = fake_ctx.sent[-1]
    assert "`!dore Inferno 1:31` — And lo! almost where the ascent began" in sent["content"]
    assert [e.title for e in sent["embeds"]][:2] == ["🖼️ Inferno 1:1–3", "🖼️ Inferno 1:31–33"]
    assert sent["embeds"][1].description.startswith("*And lo! almost where the ascent began,*")
    asyncio.run(do.send_dore(fake_ctx, "Inferno 1:31"))                     # just that one
    sent = fake_ctx.sent[-1]
    assert sent["content"] is None and [e.title for e in sent["embeds"]] == ["🖼️ Inferno 1:31–33"]
    asyncio.run(do.send_dore(fake_ctx, "Genesis 11:30"))                    # none there: the chapter's
    assert "no picture at **Genesis 11:30**" in fake_ctx.sent[-1]["content"]


def test_dante_is_not_a_page_scan(do):
    """The German edition's scans are photographs of whole pages: each Dante plate is a clean copy,
    or the engraving cut out of its scan (attached when the build has made it)."""
    for p in (p for p in do.plates() if p["set"] == "dante"):
        assert p.get("file") or "Gottliche" not in p["image"], p["key"]
    par3 = next(p for p in do.plates() if p["set"] == "dante" and p["book"] == "Paradiso" and p["chapter"] == 3)
    assert (par3["start"], par3["end"]) == (16, 18)                  # "Such saw I many faces prompt to speak"
    message = do.plate_message([par3])
    if (do.ROOT / par3["file"]).exists():
        assert message["files"][0].filename == par3["file"].rsplit("/", 1)[1]
        assert message["embeds"][0].image.url == f"attachment://{message['files'][0].filename}"
    else:                                                        # (not built: the scan, from Commons)
        assert "files" not in message and message["embeds"][0].image.url.startswith("https://")


def test_blakes_art(do, lookup):
    blake = do.plates("blake")
    sets = {p["set"] for p in blake}
    assert sets == {"job", "bible", "pl", "pp", "dante"} and sum(p["set"] == "job" for p in blake) == 21
    ids = [b.item.custom_id for b in do.art_buttons(lookup.get_verse("Genesis 28:12"))]
    assert ids[0].startswith("dore:") and ids[1].startswith("blakeart:")           # Jacob's ladder, by both
    shown = [do.by_key()[k] for k in do.art_buttons(lookup.get_verse("Job 38:7"))[0].keys]
    assert shown[0]["title"] == "When the Morning Stars Sang Together" and do.plate_embed(shown[0]).title.startswith("🎨")
    for p in blake:                                    # every passage opens in the bot
        assert lookup.get_verse(f"{p['book']} {p['chapter']}" + (f":{p['start']}" if p["start"] else ""))["found"], p["key"]


def test_blakes_job_plates_carry_every_verse_engraved_on_them(do, lookup):
    """Plate 1's main text is Job 1:1-5 (not 1:5 alone); plate 2 also carries 29:5, so it shows there."""
    first = next(p for p in do.plates("blake") if p["set"] == "job" and p["n"] == "1")
    assert (first["chapter"], first["start"], first["end"]) == (1, 1, 5)
    d = do.plate_embed(first).description
    assert d.startswith("**Job 1:1–5**\n1 *There was a man in the land of Uz")
    shown = [do.by_key()[k]["n"] for k in do.art_buttons(lookup.get_verse("Job 29:5"))[0].keys]
    assert shown == ["2"]
    second = do.by_key()["kj2"]
    assert "Also engraved on the plate: Job 29:5 · Job 19:26 · Daniel 7:9" in do.plate_embed(second).description
    for p in (p for p in do.plates("blake") if p["set"] == "job"):
        for c, a, b in p["passages"]:
            assert lookup.get_verse(f"Job {c}:{a}-{b}")["found"], p["key"]


def test_blakes_dante_pictures_are_tied_to_their_lines(do, lookup):
    dante = [p for p in do.plates("blake") if p["set"] == "dante"]
    assert len(dante) == 56 and {p["book"] for p in dante} == {"Inferno", "Purgatorio", "Paradiso"}
    for p in dante:
        assert lookup.get_verse(f"{p['book']} {p['chapter']}:{p['start']}-{p['end']}")["found"], p["key"]
    charon = next(p for p in dante if p["title"] == "Charon and the Condemned Souls")
    d = do.plate_embed(charon).description
    assert d == ("**Inferno 3:109–111**\n*Charon the demon, with the eyes of glede,*\n"
                 "*Beckoning to them, collects them all together,*\n*Beats with his oar whoever lags behind.*")
    [button] = do.art_buttons(lookup.get_verse("Inferno 3:109"))                # (Doré has none there)
    assert button.item.custom_id.startswith("blakeart:")
    assert [do.by_key()[k]["title"] for k in button.keys] == ["Charon and the Condemned Souls"]


def test_blake_command_takes_a_passage(bot_module, fake_ctx):
    from bot_commands import blake
    asyncio.run(blake.send_blake(fake_ctx, "Inferno 5"))            # (by canto: no lines to quote)
    assert fake_ctx.sent[-1]["embeds"][0].title.startswith("🎨")
    asyncio.run(blake.send_blake(fake_ctx, "Job 38"))
    assert [e.title for e in fake_ctx.sent[-1]["embeds"]][:1] == ["🎨 The Lord Answering Job out of the Whirlwind"]


@pytest.mark.parametrize("query, first", [("Genesis 11", "🖼️ The Tower of Babel"), ("flood", None),
                                          ("Inferno 3", "🖼️ Inferno 3:7–9"),("Paradise Lost 1", "🖼️ Paradise Lost 1:44–45")])
def test_the_command(do, fake_ctx, query, first):
    asyncio.run(do.send_dore(fake_ctx, query))
    sent = fake_ctx.sent[-1]
    embeds = sent.get("embeds") or [sent["embed"]]
    assert 1 <= len(embeds) <= do.MAX_SHOWN
    assert first is None or embeds[0].title == first
    assert all(e.image.url for e in embeds)


def test_nothing_found(do, fake_ctx):
    asyncio.run(do.send_dore(fake_ctx, "Leviticus 3"))
    assert "no engraving" in fake_ctx.sent[-1]["content"]
    asyncio.run(do.send_dore(fake_ctx, "zzzq"))
    assert "don't have a Doré engraving" in fake_ctx.sent[-1]["content"]


def test_the_button_survives_a_study_button(bot_module):
    """Pressing Notes rebuilds the buttons from the message: the Doré button must come back too."""
    from bot_commands import verse
    import types
    rows = [types.SimpleNamespace(children=[types.SimpleNamespace(custom_id="study:notes:Genesis 11:4", disabled=False),
                                            types.SimpleNamespace(custom_id="dore:b010", disabled=False),
                                            types.SimpleNamespace(custom_id="blakeart:kb1", disabled=False)])]
    view = verse._study_view_from_message(types.SimpleNamespace(components=rows), "study:notes:Genesis 11:4")
    assert [c.custom_id for c in view.children] == ["study:notes:Genesis 11:4", "dore:b010", "blakeart:kb1"]
