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
    ("Hyndluljoth", "46", '"Ber þú minnisöl'),
    ("Sigrdrifumol", "4", '"Lengi ek svaf'),
    ("Helgakvitha Hundingsbana II", "17", '"Mun-a þér, Sigrún'),
    ("Fafnismol", "26", '"Fjarri þú gekkt'),
    ("Atlamol en Gronlenzku", "96", '"Lýgr þú nú, Guðrún'),
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


def test_the_reply_has_the_norse_and_a_runes_button(oracles, fake_ctx):
    asyncio.run(oracles.cmd_edda.callback(fake_ctx, query="havamal 139"))
    sent = fake_ctx.sent[0]
    field = next(f for f in sent["embed"].fields if f.name == "In Old Norse")
    assert field.value.startswith("Veit ek, at ek hekk")
    assert "Guðni Jónsson" in sent["embed"].footer.text
    ids = [getattr(getattr(item, "item", item), "custom_id", "") or "" for item in sent["view"].children]
    assert "runes:Hovamol|139" in ids and len(ids) <= 5               # (all on one row: Discord's limit is 5)


def test_odin_unquoted_norse_too(oracles, fake_ctx):
    asyncio.run(oracles.cmd_odin.callback(fake_ctx, query="vafthruthnismol 1"))
    field = next(f for f in fake_ctx.sent[0]["embed"].fields if f.name == "In Old Norse")
    assert '"' not in field.value and field.value.startswith("Ráð þú mér nú, Frigg")


def test_no_norse_no_button(oracles, fake_ctx):
    asyncio.run(oracles.cmd_odin.callback(fake_ctx, query="riddles 1"))     # (Hollander's: no Norse here)
    sent = fake_ctx.sent[0]
    assert not any(f.name == "In Old Norse" for f in sent["embed"].fields)
    ids = [getattr(getattr(item, "item", item), "custom_id", "") or "" for item in sent["view"].children]
    assert not any(i.startswith("runes:") for i in ids)


def test_pressing_card_keeps_the_other_buttons(oracles):
    class Row:
        def __init__(self, children):
            self.children = children

    class Message:
        pass

    view = oracles._card_view("edda", "Hovamol|139")
    view.add_item(oracles.RunesButton("Hovamol|139"))
    from bot_commands.verse import PassageButton
    view.add_item(PassageButton("n", "Hovamol 139"))
    message = Message()
    message.components = [Row([getattr(i, "item", i) for i in view.children])]
    after = oracles._view_after(message, "ocard:edda:Hovamol|139")
    state = {getattr(i, "item", i).custom_id: getattr(i, "item", i).disabled for i in after.children}
    assert state == {"ocard:edda:Hovamol|139": True, "runes:Hovamol|139": False, "pnav:n:Hovamol 139": False}


def test_the_runes_card_renders(bot_module):
    from bot_commands.card import _render_verse_card, _script_font
    assert _script_font("C:/Windows/Fonts/", "ᚠᚢᚦ").endswith("seguihis.ttf")
    buf = _render_verse_card("Voluspo, stanza 19", runes.to_runes(NORSE["Voluspo"]["19"]), "note", "", "norse",
                             verse=True)
    assert buf.read(8) == b"\x89PNG\r\n\x1a\n"
