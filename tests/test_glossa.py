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
           ("Amos", "6", "1", "ye great men, heads of the people"), ("Obadiah", "1", "13", "Neither shalt thou enter"),
           ("Micah", "7", "14", "according to the days of old"),
           ("Habakkuk", "2", "6", "and it shall be said: Woe to him that heapeth together that which is not his own"),
           ("Habakkuk", "2", "19", "there is no … in the bowels thereof"),
           ("Zephaniah", "3", "19", "and I will get them praise, and a name"),
           ("Zechariah", "11", "11", "And it was made void in that day"),
           ("Zechariah", "13", "1", "and of the unclean woman"),
           ("Zechariah", "13", "8", "shall be scattered, and shall perish"),
           ("Zechariah", "14", "8", "And it shall come to pass in that day"),
           ("Malachi", "2", "12", "The Lord will cut off the man that hath done this"),
           ("Ruth", "2", "2", "that escape the hands of the reapers"),
           # the Song: the DR's words differ from the KJV's where its verses split differently
           ("Song of Solomon", "1", "4", "to the odour of thy ointments"),
           ("Song of Solomon", "1", "11", "chains of gold"),
           ("Song of Solomon", "2", "10", "Behold my beloved"),
           ("Song of Solomon", "3", "4", "and I will not let him go, till I bring"),
           ("Song of Solomon", "5", "1", "with my aromatical spices"),
           ("Song of Solomon", "6", "1", "thy beloved, O thou most beautiful"),
           ("Song of Solomon", "7", "8", "and the odour of thy mouth"),
           # speaker labels for the next verse, hung on the last words of the one before
           ("Song of Solomon", "3", "6", "till she please"),
           ("Song of Solomon", "8", "14", "make me hear thy voice")}


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


def test_obadiah_whole():
    """Obadiah's one chapter numbers alike in the Vulgate and the KJV (21 verses)."""
    obadiah = DATA["books"]["Glossa Ordinaria on Obadiah"]
    assert list(obadiah) == ["1"] and sorted(obadiah["1"], key=int)[-1] == "21"
    assert "the kingdom shall be for the Lord" not in obadiah["1"]["1"]
    assert "**“saviours”**" in obadiah["1"]["21"]


def test_micah_on_the_kjvs_numbering():
    """The Vulgate's Micah 5:11 is the KJV's 5:11-12 (its sorceries are the KJV's 5:12), its 5:12-14 the KJV's
    5:13-15; the card's Douay-Rheims verse follows."""
    micah = DATA["books"]["Glossa Ordinaria on Micah"]
    assert sorted(micah, key=int) == [str(c) for c in range(1, 8)] and "21" not in micah["7"]
    assert "deceived by others" in micah["5"]["12"] and "deceived by others" not in micah["5"]["11"]
    assert "graven things" in micah["5"]["13"] and "execute vengeance" in micah["5"]["15"]
    assert "**“AND THOU, BETHLEHEM Ephrata”**" in micah["5"]["2"]
    verses = DATA["douay"]["Micah"]["verses"]["5"]
    assert verses["12"]["ref"] == "5:11" and verses["15"]["ref"] == "5:14"
    assert "swords into ploughshares" in micah["4"]["3"]


def test_nahum_whole():
    """Nahum numbers alike in the Vulgate and the KJV; the gloss on 3:10's "eius" reads "her" (Alexandria's) there,
    though the book's lemma for it is 1:13's "his", and stays in its place among that verse's notes."""
    nahum = DATA["books"]["Glossa Ordinaria on Nahum"]
    assert {c: len(v) for c, v in nahum.items()} == {"1": 15, "2": 13, "3": 19}
    assert "**“her”** — Alexandria's" in nahum["3"]["10"]
    assert nahum["3"]["10"].index("Alexandria's") < nahum["3"]["10"].index("by the enemy")
    assert "**“his”** — of the Assyrian" in nahum["1"]["13"]


def test_habakkuk_doublet_glosses_under_1_13_and_14():
    """The edition's 1:3 repeats 1:13-14's words; their glosses go to 1:13-14 (after 1:13's own first half), and the
    KJV's 1:14 has notes."""
    hab = DATA["books"]["Glossa Ordinaria on Habakkuk"]
    assert {c: len(v) for c, v in hab.items()} == {"1": 17, "2": 20, "3": 19}
    assert "despisers" not in hab["1"]["3"] and "fishes of the sea" not in hab["1"]["3"]
    assert hab["1"]["13"].index("Thy eyes are too pure") < hab["1"]["13"].index("Why lookest thou upon the despisers")
    assert "Boethius" in hab["1"]["14"]
    assert "**“Let rottenness enter into my bones”**\n• but" in hab["3"]["16"]


def test_zephaniah_whole():
    """Zephaniah numbers alike in the Vulgate and the KJV; the gloss that opens 3:3 (filed under 3:2's last words)
    heads 3:3's notes."""
    zeph = DATA["books"]["Glossa Ordinaria on Zephaniah"]
    assert sorted(zeph, key=int) == ["1", "2", "3"] and "20" in zeph["3"]
    assert zeph["3"]["3"].startswith("**“Her princes are in the midst of her”**\n• After the general rebuke")
    assert "drew not near" not in zeph["3"]["3"]
    assert "Chusi" in zeph["1"]["1"]


def test_haggai_on_the_kjvs_numbering(bot_module):
    """The Vulgate's Haggai 2:1 (the work begun on the 24th day) is the KJV's 1:15, its 2:2-24 the KJV's 2:1-23; the
    signet gloss filed under the Vulgate's 2:23 goes with its words to the KJV's 2:23."""
    hag = DATA["books"]["Glossa Ordinaria on Haggai"]
    assert sorted(hag, key=int) == ["1", "2"] and "24" not in hag["2"]
    assert "twenty-two days between" in hag["1"]["15"]
    assert "**“And in the seventh month" in hag["2"]["1"] and "signet" in hag["2"]["23"]
    assert "signet" not in hag["2"]["22"]
    from bot_commands import bible_commentary as B
    assert "— Douay-Rheims, Aggeus 2:1" in B.reply("Haggai", 1, 15)["embed"].description

def test_zechariah_whole():
    """Zechariah numbers alike in the Vulgate and the KJV; the notes on the angel going forth and on the vessel, which
    the edition files under 5:7-8, go to 5:5-6, where those words are."""
    zech = DATA["books"]["Glossa Ordinaria on Zechariah"]
    assert sorted(zech, key=int) == [str(c) for c in range(1, 15)]
    assert zech["5"]["5"].startswith("**“And the angel went forth”**")
    assert "This is a vessel" in zech["5"]["6"]
    assert "And the angel went forth" not in zech["5"].get("7", "")
    assert "bridle of the horse" in zech["14"]["20"]

def test_malachi_whole():
    """Malachi has four chapters in the Vulgate as in the KJV; "What have we spoken against thee?", the Douay-Rheims's
    3:14, ends the KJV's 3:13, and its notes go with it."""
    mal = DATA["books"]["Glossa Ordinaria on Malachi"]
    assert sorted(mal, key=int) == ["1", "2", "3", "4"]
    assert "What have we spoken against thee?" in mal["3"]["13"]
    assert "What have we spoken against thee?" not in mal["3"].get("14", "")
    assert "Elias" in mal["4"]["6"] and "Sun of justice" in mal["4"]["2"]

def test_ruth_whole():
    """Ruth numbers alike in the Vulgate and the KJV; the genealogy's note closes the book."""
    ruth = DATA["books"]["Glossa Ordinaria on Ruth"]
    assert sorted(ruth, key=int) == ["1", "2", "3", "4"]
    assert "Rabanus" in ruth["1"]["1"] and "whither" not in ruth["1"]["1"]
    assert "whithersoever thou shalt go, I will go" in ruth["1"]["16"]
    assert "ten generations" in ruth["4"]["22"]


def test_song_on_the_kjvs_numbering():
    """The KJV's Song 1:1 is the title, so the Vulgate's chapter 1 and 6 are one verse behind; its 5:17 is the KJV's
    6:1, and its 5:1 and 7:1 begin with the ends of the KJV's 4:16 and 6:13."""
    song = DATA["books"]["Glossa Ordinaria on Song of Solomon"]
    assert sorted(song, key=int) == [str(c) for c in range(1, 9)] and "1" not in song["1"] and "17" not in song["5"]
    assert "**“Let him kiss me”**" in song["1"]["2"]
    assert "**“Let my beloved come”**" in song["4"]["16"] and "Let my beloved come" not in song["5"]["1"]
    assert "**“Whither is … gone”**" in song["6"]["1"] and "13" in song["6"]
    assert "Flee away, O my beloved" in song["8"]["14"]


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
