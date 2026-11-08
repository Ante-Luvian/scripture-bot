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
                     "Baldrs Draumar": 4, "Lokasenna": 3}
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


def test_harbarthsljoth_whole(lookup):
    """It had stanzas 1-16 of its 60; and the long lines printed over two are one line again."""
    assert "Get hence where every evil thing" in lookup.get_verse("Harbarthsljoth 60")["text"]
    assert "on the farther shore of the sound?" in lookup.get_verse("Harbarthsljoth 1")["text"]
