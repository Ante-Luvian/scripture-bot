"""The Glossa Ordinaria in English (scripts/build_glossa.py, data/patristics/glossa_ordinaria.json)."""
import json
import re

from core import ROOT

DATA = json.loads((ROOT / "data" / "patristics" / "glossa_ordinaria.json").read_text(encoding="utf-8"))
ENGLISH = ROOT / "scripts" / "glossa" / "english"


def test_jonah_on_the_kjvs_numbering():
    """The Vulgate's Jonah 2:1 (the fish) is the KJV's 1:17; its 2:2-11 the KJV's 2:1-10."""
    jonah = DATA["books"]["Glossa Ordinaria on Jonah"]
    assert jonah["1"]["17"].startswith("**“Now the Lord prepared a great fish")
    assert "2" in jonah and "11" not in jonah["2"] and "10" in jonah["2"]
    assert jonah["1"]["1"].startswith("**“And it came to pass”** — The conjunction “and” joins this")


def test_hosea_on_the_kjvs_numbering():
    """The Vulgate's Hosea 14:1 (Samaria perishes) is the KJV's 13:16, its 14:2-10 the KJV's 14:1-9; its 6:2-3 the KJV's
    6:1-2; its 2:24 the end of the KJV's 2:23."""
    hosea = DATA["books"]["Glossa Ordinaria on Hosea"]
    assert len(hosea) == 14 and "10" not in hosea["14"] and "24" not in hosea["2"]
    assert hosea["13"]["16"].count("Let Samaria perish") >= 1
    assert "Return, O Israel" in hosea["14"]["1"] and "Who is wise" in hosea["14"]["9"]
    assert "he hath taken us" in hosea["6"]["1"] and "He will revive us" in hosea["6"]["2"]
    assert "Thou art my people" in hosea["2"]["23"]


def test_joel_whole():
    """Joel's three chapters number alike in the Vulgate and the KJV; Pentecost's verse (2:28) is there."""
    joel = DATA["books"]["Glossa Ordinaria on Joel"]
    assert sorted(joel, key=int) == ["1", "2", "3"] and "21" in joel["3"]
    assert joel["2"]["28"].startswith("**“And it shall come to pass after this, that I will pour out my spirit")


def test_every_gloss_in_english_and_clean():
    for f in ENGLISH.glob("*.json"):
        for gid, text in json.loads(f.read_text(encoding="utf-8")).items():
            assert text.strip() and not re.search(r"\{t\.|[<>]", text), (f.name, gid)
    for book in DATA["books"].values():
        for ch, verses in book.items():
            for v, text in verses.items():
                assert text.count("**") % 2 == 0 and "{t." not in text, (ch, v)


def test_in_the_commentary_menu(bot_module):
    from bot_commands import bible_commentary as B
    labels = [label for label, _, _ in B.groups("Jonah", 1, 3)]
    assert labels[0] == "The Glossa Ordinaria"
    assert "to flee into Tharsis" in B.reply("Jonah", 1, 3)["embed"].description
