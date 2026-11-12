"""!catena and the 📖 Commentary under a Bible verse: the Fathers from the library (bot_commands/bible_commentary.py),
no longer catenabible.com (2026-11-11)."""
import asyncio


def test_the_verse_of_the_days_shape(bot_module):
    """The Verse of the Day's full mode reads one Father from _fetch_catena_sections."""
    from bot_commands import church
    r = church._fetch_catena_sections("John 3:16", 1)
    assert not r.get("error_send") and len(r["sections"]) == 1 and r["book_raw"] == "John"
    assert church._fetch_catena_sections("Hezekiah 9:9").get("error_send")


def test_commentary_menu_pages_and_neighbours(bot_module):
    from bot_commands import bible_commentary as B
    r = B.reply("Matthew", 5, 3)
    assert r["embed"].title == "📖 The Catena Aurea on Matthew 5:3"
    assert r["embed"].description.startswith("*Blessed are the poor in spirit")
    kinds = [type(c).__name__ for c in r["view"].children]
    assert kinds[0] == "Menu" and kinds.count("Nav") >= 3                  # (pages, and the verses either side)
    labels = [o.label for o in r["view"].children[0].item.options]
    assert labels[0] == "The Catena Aurea" and any("Homilies" in l or "Commentary" in l for l in labels)
    assert all(len(r["embed"].description) <= 4096 for _ in [0])


def test_a_verse_without_commentary_says_so(bot_module):
    from bot_commands import bible_commentary as B
    assert B.button_for("1 Chronicles", 2, 5) == []                   # (a genealogy: no one comments on it)
    assert "no commentary" in B.reply("1 Chronicles", 2, 5)["embed"].description


def test_the_button_under_a_verse(bot_module):
    from bot_commands import verse
    result = bot_module.lookup.get_verse("John 3:16")
    ids = [getattr(b, "custom_id", "") or b.item.custom_id for b in verse._study_buttons(result)]
    assert "bcom:John 3:16" in ids and not any(i.startswith("study:catena") for i in ids)


def test_catena_command(bot_module, fake_ctx):
    from bot_commands import church
    asyncio.run(church.cmd_catena.callback(fake_ctx, reference="Jn 3:16"))
    assert fake_ctx.sent and "John 3:16" in fake_ctx.sent[-1]["embed"].title
