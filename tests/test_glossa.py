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
    assert jonah["1"]["1"].startswith("**“And it came to pass”**\n• The conjunction “and” joins this")


def test_each_phrase_once_short_notes_first():
    """Every note on the same words goes under one heading, the interlinear ones before the margin's."""
    for book in DATA["books"].values():
        for ch, verses in book.items():
            for v, text in verses.items():
                heads = re.findall(r"^\*\*“(.+?)”\*\*", text, re.M)
                assert len(heads) == len(set(heads)), (ch, v)
    hosea = DATA["books"]["Glossa Ordinaria on Hosea"]
    assert "**“Because Israel was a child”**\n• he sets out the benefits" in hosea["11"]["1"]


def test_hosea_notes_follow_their_words_across_a_split_verse():
    """The Vulgate's Hosea 11:1 begins with the end of KJV 10:15, its 6:1 with the end of KJV 5:15."""
    hosea = DATA["books"]["Glossa Ordinaria on Hosea"]
    assert "As the morning" not in hosea["11"]["1"] and "**“As the morning”**" in hosea["10"]["15"]
    assert "Matthew uses this testimony" in hosea["11"]["1"]
    assert "In their affliction" not in hosea["6"]["1"] and "**“In their affliction”**" in hosea["5"]["15"]
    assert "salvation is promised on the third day" in hosea["6"]["2"]


def test_hosea_on_the_kjvs_numbering():
    """The Vulgate's Hosea 14:1 (Samaria perishes) is the KJV's 13:16, its 14:2-10 the KJV's 14:1-9; its 6:2-3 the KJV's
    6:1-2; its 2:24 the end of the KJV's 2:23."""
    hosea = DATA["books"]["Glossa Ordinaria on Hosea"]
    assert len(hosea) == 14 and "10" not in hosea["14"] and "24" not in hosea["2"]
    assert hosea["13"]["16"].count("Let Samaria perish") >= 1
    assert "Return, O Israel" in hosea["14"]["1"] and "Who is wise" in hosea["14"]["9"]
    assert "he hath taken us" in hosea["6"]["1"] and "He will revive us" in hosea["6"]["2"]
    assert "Thou art my people" in hosea["2"]["23"]


STOP = set("the and that this with from them they their shall will have hath unto upon thee thou thy your you which into "
           "were what when there for not but his her him all are was".split())
# Phrases checked by hand that do belong where they are, though their words look more like a neighbouring verse's
# (the Douay-Rheims and the KJV word it differently, or the edition files a note introducing the next verse there)
CHECKED = {("Hosea", "7", "7", "They were all heated like an oven"), ("Hosea", "13", "11", "I will give thee a king"),
           ("Hosea", "11", "10", "because I am God, and not man: the holy one in the midst of thee, and I will not "
                                 "enter into the city"),
           ("Joel", "1", "17", "The beasts have rotted in their dung"), ("Joel", "2", "8", "yea, and … through the windows"),
           ("Joel", "3", "9", "rouse up the strong"), ("Jonah", "1", "6", "and said to him: Why art thou fast asleep?"),
           ("Jonah", "4", "9", "And the Lord said"),
           ("Amos", "1", "5", "and … shall be carried away"), ("Amos", "3", "11", "and … shall be taken away from thee"),
           ("Amos", "6", "1", "ye great men, heads of the people")}


def _words(s):
    return {w for w in re.findall(r"[a-z]+", s.lower()) if len(w) > 3 and w not in STOP}


def test_every_note_under_the_kjv_verse_it_explains():
    """Each phrase's words are compared with the KJV verse it's shown under and that verse's neighbours: a phrase that
    fits a neighbour much better means the Latin Bible's numbering (or a verse it splits differently) has put the notes
    under the wrong verse. Check a new book with this before building on it (VERSIFICATION, MOVES)."""
    kjv = json.loads((ROOT / "data" / "kjv" / "kjv_canon.json").read_text(encoding="utf-8"))
    kjv = kjv.get("books", kjv)
    wrong = []
    for title, chapters in DATA["books"].items():
        name = title.removeprefix("Glossa Ordinaria on ")
        order = [(c, v) for c in kjv[name] for v in kjv[name][c]]
        for c, verses in chapters.items():
            for v, text in verses.items():
                assert (c, v) in order, (name, c, v)
                i = order.index((c, v))
                for head in re.findall(r"^\*\*“(.+?)”\*\*", text, re.M):
                    w = _words(head)
                    if len(w) < 2 or (name, c, v, head) in CHECKED:
                        continue
                    fit = {o: len(w & _words(kjv[name][o[0]][o[1]])) / len(w) for o in order[max(0, i - 1):i + 2]}
                    best = max(fit, key=fit.get)
                    if fit[best] > fit[(c, v)] + 0.25:
                        wrong.append(f"{name} {c}:{v} “{head}” fits {best[0]}:{best[1]}")
    assert not wrong, wrong


def test_joel_whole():
    """Joel's three chapters number alike in the Vulgate and the KJV; Pentecost's verse (2:28) is there."""
    joel = DATA["books"]["Glossa Ordinaria on Joel"]
    assert sorted(joel, key=int) == ["1", "2", "3"] and "21" in joel["3"]
    assert joel["2"]["28"].startswith("**“And it shall come to pass after this, that I will pour out my spirit")


def test_amos_on_the_kjvs_numbering():
    """The Vulgate's Amos 6:10-11 are the KJV's 6:10, its 6:12-15 the KJV's 6:11-14; its 5:1 ends with the start of the
    KJV's 5:2 ("is fallen, and it shall rise no more")."""
    amos = DATA["books"]["Glossa Ordinaria on Amos"]
    assert sorted(amos, key=int) == [str(c) for c in range(1, 10)] and "15" not in amos["6"]
    assert "Is there yet any with thee?" in amos["6"]["10"] and "There is an end" in amos["6"]["10"]
    assert "Can horses run upon the rocks" in amos["6"]["12"] and "from the entrance of Emath" in amos["6"]["14"]
    assert "**“is fallen”**" in amos["5"]["2"] and "**“is fallen”**" not in amos["5"]["1"]
    assert "And I will plant them" in amos["9"]["15"]


def test_every_gloss_in_english_and_clean():
    for f in ENGLISH.glob("*.json"):
        for gid, text in json.loads(f.read_text(encoding="utf-8")).items():
            assert text.strip() and not re.search(r"\{t\.|[<>]", text), (f.name, gid)
    for book in DATA["books"].values():
        for ch, verses in book.items():
            for v, text in verses.items():
                assert text.count("**") % 2 == 0 and "{t." not in text, (ch, v)


def test_glossa_card_shows_the_douay_rheims(bot_module):
    """The Glossa's notes quote the Douay-Rheims, so its card shows the verse in those words, and by the Latin Bible's
    number where it differs; other commentaries keep the KJV."""
    from bot_commands import bible_commentary as B
    desc = B.reply("Jonah", 1, 3)["embed"].description
    assert desc.startswith("*And Jonas rose up to flee into Tharsis") and "— Douay-Rheims\n" in desc
    assert "Tarshish" not in desc.split("— Douay-Rheims")[0]
    fish = B.reply("Jonah", 1, 17)["embed"].description
    assert fish.startswith("*Now the Lord prepared a great fish") and "— Douay-Rheims, Jonas 2:1" in fish
    assert "Amos 6:10, 6:11" in B.reply("Amos", 6, 10)["embed"].description
    gospel = B.reply("John", 3, 16)["embed"].description
    assert "Douay-Rheims" not in gospel


def test_in_the_commentary_menu(bot_module):
    from bot_commands import bible_commentary as B
    labels = [label for label, _, _ in B.groups("Jonah", 1, 3)]
    assert labels[0] == "The Glossa Ordinaria"
    assert "to flee into Tharsis" in B.reply("Jonah", 1, 3)["embed"].description
