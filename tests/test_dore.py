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


def test_no_button_without_a_picture(do, lookup):
    assert do.art_buttons(lookup.get_verse("John 3:16")) == []
    assert do.art_buttons(lookup.get_verse("Leviticus 3:1")) == []


def test_dante_by_canto(do, lookup):
    button = do.art_buttons(lookup.get_verse("Inferno 3:1"))[0]
    assert all(do.by_key()[k]["chapter"] == 3 for k in button.keys)


def test_dante_is_not_a_page_scan(do):
    """The German edition's scans are photographs of whole pages: each Dante plate is a clean copy,
    or the engraving cut out of its scan (attached when the build has made it)."""
    for p in (p for p in do.plates() if p["set"] == "dante"):
        assert p.get("file") or "Gottliche" not in p["image"], p["key"]
    par3 = next(p for p in do.plates() if p["set"] == "dante" and p["book"] == "Paradiso" and p["chapter"] == 3)
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


def test_blake_command_takes_a_passage(bot_module, fake_ctx):
    from bot_commands import blake
    asyncio.run(blake.send_blake(fake_ctx, "Job 38"))
    assert [e.title for e in fake_ctx.sent[-1]["embeds"]][:1] == ["🎨 The Lord Answering Job out of the Whirlwind"]


@pytest.mark.parametrize("query, first", [("Genesis 11", "🖼️ The Tower of Babel"), ("flood", None),
                                          ("Inferno 3", "🖼️ Inferno, Canto 3"), ("Paradise Lost 1", "🖼️ Paradise Lost 1:44–45")])
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
