"""The Old Norse beside Bellows in !edda and !odin, and the ᚱ Runes card (the owner, 2026-11-07/08).
data/norse/edda_norse.json comes from scripts/build_edda_norse.py: Guðni Jónsson's text, matched to Bellows's stanzas by
content, with the pairings the aligner got wrong set by hand (its OVERRIDES)."""
import asyncio
import json
import re
from pathlib import Path

import pytest

import runes

ROOT = Path(__file__).resolve().parent.parent
NORSE = json.loads((ROOT / "data" / "norse" / "edda_norse.json").read_text(encoding="utf-8"))
BELLOWS = json.loads((ROOT / "data" / "norse" / "poetic_edda.json").read_text(encoding="utf-8"))["books"]


@pytest.fixture(scope="module")
def oracles(bot_module):
    from bot_commands import oracles
    return oracles


def test_every_stanza_is_one_of_bellowss():
    for poem, stanzas in NORSE.items():
        assert poem in BELLOWS
        assert set(stanzas) <= set(BELLOWS[poem]), poem
    have = sum(len(s) for s in NORSE.values())
    assert have >= 0.97 * sum(len(s) for s in BELLOWS.values())          # (1539 of 1566 when built)


def test_no_edition_leftovers():
    for poem, stanzas in NORSE.items():
        for stanza, text in stanzas.items():
            assert text.strip() and not re.search(r"\d|--|::|<|&#", text), (poem, stanza, text)


@pytest.mark.parametrize("poem, stanza, opening", [
    ("Hovamol", "1", "Gáttir allar"),
    ("Hovamol", "76", "Fullar grindr"),                  # (Bellows's order of the "Deyr fé" stanzas)
    ("Hovamol", "77", "Deyr fé"),
    ("Hovamol", "138", "Nú eru Háva mál"),               # (Guðni's last stanza, 164)
    ("Hovamol", "139", "Veit ek, at ek hekk"),
    ("Voluspo", "23", "Fleygði Óðinn"),                  # (Bellows swaps 23 and 24)
    ("Voluspo", "24", "Þá gengu regin öll"),
    ("Hyndluljoth", "30", "Váru ellifu"),                # (the Short Völuspá, inside Hyndluljóð in Bellows)
    ("Hyndluljoth", "46", '“Ber þú minnisöl'),
    ("Sigrdrifumol", "4", '“Lengi ek svaf'),
    ("Helgakvitha Hundingsbana II", "17", '“Mun-a þér, Sigrún'),
    ("Fafnismol", "26", '“Fjarri þú gekkt'),
    ("Atlamol en Gronlenzku", "96", '“Lýgr þú nú, Guðrún'),
    ("Hamthesmol", "11", "Hitt kvað þá Hróðrglöð"),
])
def test_pairings_read_by_hand(poem, stanza, opening):
    assert NORSE[poem][stanza].startswith(opening)


@pytest.mark.parametrize("norse, carved", [
    ("maðr", "ᛘᛅᚦᛦ"),                   # (the ending -r, once z: ᛦ)
    ("Þórr", "ᚦᚢᛦ"),                    # (a double letter written once)
    ("steinn", "ᛋᛏᛅᛁᚾ"),                # (ei as ᛅᛁ: "stain" on the runestones)
    ("Yggdrasill", "ᚢᚴᛏᚱᛅᛋᛁᛚ"),          # (g and k one rune: "gg" one ᚴ)
    ("hár baðmr,", "ᚼᛅᚱ᛫ᛒᛅᚦᛘᛦ"),          # (words parted by ᛫, punctuation dropped)
])
def test_runes(norse, carved):
    assert runes.to_runes(norse) == carved


def test_runes_are_only_runes():
    text = runes.to_runes("\n".join(NORSE["Voluspo"].values()))
    assert set(text) <= {chr(c) for c in range(0x16A0, 0x1700)} | {"\n"}


def _ids(view):
    return {getattr(getattr(i, "item", i), "custom_id", ""): getattr(getattr(i, "item", i), "row", None)
            for i in view.children}


def test_the_reply_has_buttons_not_the_norse(oracles, fake_ctx):
    """The owner (2026-11-08): the Norse in the message made it too big; it comes by a button instead."""
    asyncio.run(oracles.cmd_edda.callback(fake_ctx, query="havamal 139"))
    sent = fake_ctx.sent[0]
    assert not sent["embed"].fields and "Veit ek" not in sent["embed"].description
    ids = _ids(sent["view"])
    assert ids["norse:Hovamol|139"] == ids["runes:Hovamol|139"] == ids["ocard:edda:Hovamol|139"] == 1
    assert all(row == 0 for cid, row in ids.items() if cid.startswith(("pnav:", "pics:")))
    for r in (0, 1):
        assert sum(1 for row in ids.values() if row == r) <= 5                 # (Discord's five a row)


def test_the_reply_is_in_half_lines(oracles, fake_ctx):
    asyncio.run(oracles.cmd_edda.callback(fake_ctx, query="vafthruthnismol 8"))
    text = fake_ctx.sent[0]["embed"].description
    assert "·" not in text and text.split("\n")[:2] == ["“Gagnrath they call me,", "and thirsty I come"]


def test_half_lines(oracles):
    assert oracles._half_lines("Gagnrath they call me, · and thirsty I come\nFrom a journey hard to thy hall;") \
        == "Gagnrath they call me,\nand thirsty I come\nFrom a journey hard to thy hall;"


def test_the_norse_view(oracles):
    embed = oracles._norse_embed("Vafthruthnismol", "8")
    english, norse = embed.fields
    assert english.inline and norse.inline                                  # (side by side)
    assert english.value.split("\n")[:2] == ["“Gagnrath they call me,", "and thirsty I come"]
    assert norse.value.startswith('“Gagnráðr ek heiti,') and "·" not in english.value
    assert len(english.value.split("\n")) == len(norse.value.split("\n"))   # (a half-line to a line, both)
    assert "Guðni Jónsson" in embed.footer.text
    odin = oracles._norse_embed("Vafthruthnismol", "1", odin=True)
    assert not any(q in f.value for f in odin.fields for q in '"“”')


def test_parallel_takes_the_edda(bot_module, fake_ctx):
    from bot_commands import translations
    asyncio.run(translations.cmd_parallel.callback(fake_ctx, reference="havamal 139"))
    sent = fake_ctx.sent[-1]
    assert sent["embed"].fields[1].value.startswith("Veit ek, at ek hekk")
    assert "runes:Hovamol|139" in _ids(sent["view"])


@pytest.mark.parametrize("query, expect", [
    ("norse", None),
    ("norse grimnismol 1", "Grimnismol"),
    ("norse havamal 139", "Hovamol"),
])
def test_odin_norse(oracles, fake_ctx, query, expect):
    asyncio.run(oracles.cmd_odin.callback(fake_ctx, query=query))
    sent = fake_ctx.sent[-1]
    assert sent["embed"].fields[1].name == "Old Norse"
    if expect:
        assert sent["embed"].title.startswith(f"🌲 {expect}")


def test_odin_norse_where_there_is_none(oracles, fake_ctx):
    asyncio.run(oracles.cmd_odin.callback(fake_ctx, query="norse riddles"))   # (Hollander's: no Norse here)
    assert "no Old Norse" in fake_ctx.sent[-1]["content"]
    asyncio.run(oracles.cmd_odin.callback(fake_ctx, query="norse havamal 98"))  # (not Odin's)
    assert "isn't Odin speaking" in fake_ctx.sent[-1]["content"]


def test_no_norse_no_buttons(oracles, fake_ctx):
    asyncio.run(oracles.cmd_odin.callback(fake_ctx, query="riddles 1"))
    assert not any(i.startswith(("runes:", "norse:")) for i in _ids(fake_ctx.sent[0]["view"]))


def test_pressing_card_keeps_the_other_buttons(oracles):
    class Row:
        def __init__(self, children):
            self.children = children

    class Message:
        pass

    from bot_commands.verse import PassageButton
    first = [PassageButton("n", "Hovamol 139")]
    second = [oracles.OracleCardButton("edda", "Hovamol|139"), oracles.NorseButton("Hovamol|139"),
              oracles.RunesButton("Hovamol|139")]
    message = Message()
    message.components = [Row([b.item for b in first]), Row([b.item for b in second])]
    after = oracles._view_after(message, "ocard:edda:Hovamol|139")
    state = {i.item.custom_id: (i.item.disabled, i.item.row) for i in after.children}
    assert state == {"pnav:n:Hovamol 139": (False, 0), "ocard:edda:Hovamol|139": (True, 1),
                     "norse:Hovamol|139": (False, 1), "runes:Hovamol|139": (False, 1)}


def test_typewriter_marks_typeset():
    text = "\n".join(t for p in NORSE.values() for t in p.values())
    assert '"' not in text and " - " not in text


def test_the_card_text_is_in_marked_half_lines(oracles):
    """The Edda's card (the owner, 2026-11-08): a half-line to a line, upright, flush left, the second half of each
    of Bellows's lines indented (a tab marks it for the card); a line he leaves whole isn't."""
    _, text, _ = oracles._oracle_card_content("edda", "Vafthruthnismol|8")
    assert text.split("\n") == ["Gagnrath they call me,", "\tand thirsty I come", "From a journey hard to thy hall;",
                                "Welcome I look for,", "\tfor long have I fared,", "And gentle greeting, giant."]
    left = oracles._half_lines(oracles._edda_text("Vafthruthnismol", "8"), mark=True)
    right = oracles._norse_marked(oracles._norse_text("Vafthruthnismol", "8"), left)
    assert [l.startswith("\t") for l in right.split("\n")] == [l.startswith("\t") for l in left.split("\n")]
    assert oracles._norse_marked("a\nb\nc", "x") == "a\n\tb\nc"            # (counts differ: every other line)


def test_hollanders_half_lines(oracles):
    assert oracles._half_lines("I got Valholl ready to make room\n  ’twas neither wine", mark=True) \
        == "I got Valholl ready\n\tto make room\n’twas neither wine"


def test_the_cards_indent_the_marked_lines(bot_module):
    from unittest import mock
    from PIL import ImageDraw
    from bot_commands import card
    drawn = []
    original = ImageDraw.ImageDraw.text
    with mock.patch.object(ImageDraw.ImageDraw, "text",
                           lambda self, xy, text, *a, **k: drawn.append((xy[0], text)) or original(self, xy, text, *a, **k)):
        card._render_verse_card("t", "One half,\n\tthe other half\nA whole line here", "s", "", "norse",
                                verse=True, poem=True)
    x = dict((t, x) for x, t in drawn)
    assert x["the other half"] > x["One half,"] == x["A whole line here"]
    drawn.clear()
    with mock.patch.object(ImageDraw.ImageDraw, "text",
                           lambda self, xy, text, *a, **k: drawn.append((xy[0], text)) or original(self, xy, text, *a, **k)):
        buf = card._render_parallel_card("t", "One half,\n\tthe other", "Ein helft,\n\tin önnur", "s")
    x = dict((t, x) for x, t in drawn)
    assert x["the other"] > x["One half,"] and x["in önnur"] > x["Ein helft,"] > x["the other"]
    assert buf.read(8) == b"\x89PNG\r\n\x1a\n"


def test_the_norse_view_has_a_card_button(oracles):
    class Ctx:
        guild, author, sent = None, "t", []

        async def send(self, *a, **k):
            self.sent.append(k)
    ctx = Ctx()
    asyncio.run(oracles.send_norse(ctx, "Hovamol", "139"))
    assert {"ncard:Hovamol|139", "runes:Hovamol|139"} <= set(_ids(ctx.sent[0]["view"]))


def test_the_runes_card_renders(bot_module):
    from bot_commands.card import _render_verse_card, _script_font
    assert _script_font("C:/Windows/Fonts/", "ᚠᚢᚦ").endswith("BabelStoneRunic.ttf")
    from bot_commands.card import _render_runes_card
    buf = _render_runes_card("Voluspo, stanza 19", runes.carve(NORSE["Voluspo"]["19"]), "note", "a question?")
    assert buf.read(8) == b"\x89PNG\r\n\x1a\n"


def test_carved_as_one_run():
    """The Runes card's text (the owner, 2026-11-08): one run, as on a runestone, no line breaks."""
    assert runes.carve("Ask veit ek standa,\nheitir Yggdrasill,") == "ᛅᛋᚴ᛫ᚢᛅᛁᛏ᛫ᛁᚴ᛫ᛋᛏᛅᚾᛏᛅ᛫ᚼᛅᛁᛏᛁᚱ᛫ᚢᚴᛏᚱᛅᛋᛁᛚ"


def test_no_quotation_marks_on_the_cards(oracles):
    for key in ("Vafthruthnismol|8", "Lokasenna|6"):
        _, text, _ = oracles._oracle_card_content("edda", key)
        assert not any(q in text for q in '"“”'), key


def test_every_rune_is_drawn(bot_module):
    """The Runes card draws the runes itself, with straight strokes (no font without curves was found)."""
    from bot_commands.card import RUNE_STROKES, RUNE_DOTS
    used = {r for v in runes.RUNE.values() for r in v} | {"ᛦ", runes.DOT}
    assert used <= set(RUNE_STROKES) | set(RUNE_DOTS)
    carved = runes.carve("\n".join(t for p in NORSE.values() for t in p.values()))
    assert set(carved) <= set(RUNE_STROKES) | set(RUNE_DOTS)
