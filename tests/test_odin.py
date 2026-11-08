"""!odin: only Odin's own words (the owner, 2026-11-07, worried that other speakers' lines would creep in). Bellows's
speaker headings (data/norse/edda_speakers.json, scripts/build_edda_speakers.py) decide the dialogue poems."""
import json
import random
from collections import Counter

import pytest

from core import ROOT


@pytest.fixture(scope="module")
def oracles(bot_module):
    from bot_commands import oracles
    return oracles


def test_his_stanzas(oracles):
    stanzas = set(oracles._odin_stanzas())
    poems = Counter(p for p, _ in stanzas)
    assert poems == {"Hovamol": 160, "Grimnismol": 54, "Harbarthsljoth": 28, "Vafthruthnismol": 26,
                     "Baldrs Draumar": 4, "Lokasenna": 3, "Eiriksmol": 7, "Heithreksgatur": 37}
    assert ("Vafthruthnismol", "8") in stanzas and ("Vafthruthnismol", "7") not in stanzas      # (Gagnrath; the giant)
    assert ("Vafthruthnismol", "1") in stanzas                     # (the page prints "1," for "1.": still his)
    assert ("Harbarthsljoth", "38") in stanzas and ("Harbarthsljoth", "37") not in stanzas      # (Harbarth; Thor)
    assert ("Lokasenna", "21") in stanzas and ("Lokasenna", "22") not in stanzas               # (Odin; Loki)
    for not_his in ("98", "109", "110", "138", "144"):                                          # (others' words)
        assert ("Hovamol", not_his) not in stanzas


def test_every_dialogue_stanza_he_has_is_headed_for_him():
    table = json.loads((ROOT / "data" / "norse" / "edda_speakers.json").read_text(encoding="utf-8"))
    assert Counter(table["Vafthruthnismol"].values())["Othin"] == 26
    assert Counter(table["Harbarthsljoth"].values())["Thor"] == 29


def test_picks(oracles):
    rng = random.Random(3)
    assert oracles._odin_pick("grimnismal 49", rng) == ("Grimnismol", "49", "")
    assert "isn't Odin speaking" in oracles._odin_pick("vafthruthnismal 7", rng)
    assert oracles._odin_pick("138", rng).startswith("Stanza 138 of **Hovamol**")
    poem, stanza, question = oracles._odin_pick("should I travel?", rng)
    assert question == "should I travel?" and (poem, stanza) in oracles._odin_stanzas()


def test_hollander_speeches(oracles):
    """Odin's part of a Hollander stanza alone, his label off; the riddles' answers kept apart (verse 2)."""
    assert oracles._edda_text("Eiriksmol", "6", "2").startswith("“Because in many a liege-land")
    assert "Bragi" not in oracles._edda_text("Eiriksmol", "3", "1").split("\n")[0][:6]
    assert oracles._edda_text("Heithreksgatur", "37", "1").startswith("“Guess one more riddle")
    assert oracles._edda_text("Heithreksgatur", "37", "2").startswith("“But wicked spells")
    assert ("Eiriksmol", "8") not in oracles._odin_stanzas()                 # (Sigmund's)
    assert "doesn't speak in **Hakonarmol**" in oracles._odin_pick("hakonarmal", random.Random(1))
    assert oracles._odin_pick("riddles 36", random.Random(1)) == ("Heithreksgatur", "36", "")


def test_no_quotation_marks(oracles):
    """!odin's text has no quotation marks (the owner, 2026-11-08); apostrophes stay; !edda keeps them."""
    title, text, source = oracles._oracle_card_content("edda", "Vafthruthnismol|1||o")
    assert "“" not in text and "”" not in text and text.startswith("Counsel me, Frigg")
    assert "“" in oracles._oracle_card_content("edda", "Vafthruthnismol|1")[1]
    riddle = oracles._oracle_card_content("edda", "Heithreksgatur|5|1|o")[1]
    assert riddle.startswith("Who is the great one") and "”" not in riddle and "o’er" in riddle
    assert oracles._unquoted("“ ’Tis folly,”") == "’Tis folly,"


def test_interpuncts(lookup):
    """The caesura is a middle dot, not a bar (the owner, 2026-11-08)."""
    text = lookup.get_verse("Voluspo 1")["text"]
    assert "Hearing I ask · from the holy races" in text and "|" not in text


def test_prose_books(oracles, lookup):
    """Snorri and the sagas are in the library, not in !odin (verse only) nor !edda."""
    assert "is prose" in oracles._odin_pick("gylfaginning", random.Random(1))
    assert "Gylfaginning" not in oracles._edda()
    assert "Odin" in lookup.get_verse("Ynglinga Saga 2")["text"]
    assert lookup.get_verse("heimskringla 1")["reference"].startswith("Ynglinga Saga")
    assert "Fafnir" in lookup.get_verse("story of the volsungs 18")["text"]
    assert lookup.get_verse("prose edda 3")["found"]


def test_edda_is_bellows_only(oracles):
    assert "Eiriksmol" not in oracles._edda() and len(oracles._edda()) == 35
    assert "isn't in the Poetic Edda" in oracles._edda_pick("eiriksmal")


def test_hollander_text(lookup):
    """The book whole (15 poems; the prose truce formula left out), no stray markup, speakers named only where
    Hollander heads the speech."""
    import json as _json
    books = _json.loads((ROOT / "data" / "norse" / "old_norse_poems.json").read_text(encoding="utf-8"))["books"]
    assert len(books) == 15 and len(books["Heithreksgatur"]) == 37 and len(books["Solarlioth"]) == 82
    text = _json.dumps(books, ensure_ascii=False)
    assert "*" not in text and "<" not in text and "&" not in text
    assert books["Hlothskvitha"]["6"]["1"].startswith("Rose outcry in hall")    # (narration: no speaker carried on)
    assert "Then Gestumblindi said" not in books["Heithreksgatur"]["37"]["1"]
    assert lookup.get_verse("Hakonarmol 1")["found"]


def test_harbarthsljoth_whole(lookup):
    """It had stanzas 1-16 of its 60; and the long lines printed over two are one line again."""
    assert "Get hence where every evil thing" in lookup.get_verse("Harbarthsljoth 60")["text"]
    assert "on the farther shore of the sound?" in lookup.get_verse("Harbarthsljoth 1")["text"]
