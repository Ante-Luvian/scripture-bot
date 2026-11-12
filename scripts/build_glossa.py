"""
The Glossa Ordinaria in English -> data/patristics/glossa_ordinaria.json: a book a book of the Bible ("Glossa Ordinaria
on Jonah"), numbered as the KJV numbers its verses, each verse's glosses in the order the edition has them, each under
the words of the verse it explains.

The Latin is Martin Morard's edition of the editio princeps (Strasbourg, 1480/81) on Gloss-e (IRHT-CNRS), fetched by
scripts/fetch_glossa.py into scripts/.cache/glossa/. The English is ours, made for ScriptureBot (2026-11-11 on): the
glosses in scripts/glossa/english/<NN>.json ({gloss id: English}), the words of the Bible they explain in
scripts/glossa/lemmas/<NN>.json ({Latin: English}, in the Douay-Rheims's English, since it's the same Latin Bible).
Those files are the only copy of that work: they're kept in git.

The Glossa follows the Latin Bible's verse numbers, which differ from the KJV's in places: VERSIFICATION gives the
differences, a book at a time.

    python scripts/build_glossa.py
"""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LATIN = Path(__file__).resolve().parent / ".cache" / "glossa"
ENGLISH = Path(__file__).resolve().parent / "glossa" / "english"
LEMMAS = Path(__file__).resolve().parent / "glossa" / "lemmas"
OUT = ROOT / "data" / "patristics" / "glossa_ordinaria.json"
BOOKS = {"10": "Ruth", "24": "Esther", "25": "Job","28": "Proverbs", "29": "Ecclesiastes", "30": "Song of Solomon", "31": "Wisdom of Solomon", "32": "Sirach", "35": "Lamentations", "40": "Hosea", "41": "Joel", "42": "Amos", "43": "Obadiah", "44": "Jonah", "45": "Micah", "46": "Nahum", "47": "Habakkuk", "48": "Zephaniah", "49": "Haggai", "50": "Zechariah", "51": "Malachi"}  # Gloss-e's numbers -> the KJV's names (the books translated so far)
LABELS = {"[allegorically]": "Allegorically", "[the moral sense]": "In the moral sense", "[Jerome]": "Jerome",
          "[Haimo]": "Haimo", "[Gregory]": "Gregory", "[Paschasius]": "Paschasius", "[mystically]": "Mystically",
          "[historically]": "Historically", "[Gilbert]": "Gilbert", "[Alcuin]": "Alcuin"}
# (the later books' lemmas give these headings plainly: a source or a sense, not words of the verse)
LABELS.update({w: w for w in ("Allegorically", "Morally", "Mystically", "Historically", "Jerome", "Gregory", "Bede",
                              "Augustine", "Strabo", "Isidore", "Alcuin", "Rabanus", "Haimo", "Origen", "Ambrose")})


def jonah(c: int, v: int) -> tuple:
    """The Vulgate's Jonah 2:1 is the KJV's 1:17, and its 2:2-11 the KJV's 2:1-10."""
    if c == 2:
        return (1, 17) if v == 1 else (2, v - 1)
    return c, v


def hosea(c: int, v: int) -> tuple:
    """The Vulgate's Hosea 2:24 is the end of the KJV's 2:23; its 6:2-3 the KJV's 6:1-2 (its 6:1 begins with the end of
    the KJV's 5:15, but is mostly the KJV's 6:1); its 14:1 the KJV's 13:16, and its 14:2-10 the KJV's 14:1-9."""
    if c == 2 and v == 24:
        return 2, 23
    if c == 6 and v in (2, 3):
        return 6, v - 1
    if c == 14:
        return (13, 16) if v == 1 else (14, v - 1)
    return c, v


def amos(c: int, v: int) -> tuple:
    """The Vulgate's Amos 6:10-11 are the KJV's 6:10, and its 6:12-15 the KJV's 6:11-14."""
    if c == 6 and v >= 11:
        return 6, v - 1
    return c, v


def micah(c: int, v: int) -> tuple:
    """The Vulgate's Micah 5:11 is the KJV's 5:11-12 (the sorceries are the KJV's 5:12), its 5:12-14 the KJV's
    5:13-15."""
    if c == 5 and v >= 12:
        return 5, v + 1
    return c, v


def haggai(c: int, v: int) -> tuple:
    """The Vulgate's Haggai 2:1 (the work begun on the 24th day) is the KJV's 1:15, its 2:2-24 the KJV's 2:1-23."""
    if c == 2:
        return (1, 15) if v == 1 else (2, v - 1)
    return c, v


def song(c: int, v: int) -> tuple:
    """The KJV's Song 1:1 is the title, so the Vulgate's 1:n is its 1:n+1; the Vulgate's 5:17 is its 6:1, and the
    Vulgate's 6:n its 6:n+1."""
    if c == 1:
        return 1, v + 1
    if c == 5 and v == 17:
        return 6, 1
    if c == 6:
        return 6, v + 1
    return c, v


def job(c: int, v: int) -> tuple:
    """The Vulgate's Job 16:5 ("and would wag my head over you") is the end of the KJV's 16:4, so its 16:6-23 are the
    KJV's 16:5-22; its 39:31-35 are the KJV's 40:1-5, its 40:1-19 the KJV's 40:6-24, its 40:20-28 (the leviathan) the
    KJV's 41:1-9, and its 41:1-25 the KJV's 41:10-34. Its 42:16 holds the KJV's 42:16-17."""
    if c == 16 and v >= 5:
        return 16, 4 if v == 5 else v - 1
    if c == 39 and v >= 31:
        return 40, v - 30
    if c == 40:
        return (40, v + 5) if v <= 19 else (41, v - 19)
    if c == 41:
        return 41, v + 9
    return c, v


def proverbs(c: int, v: int) -> tuple:
    """The Vulgate's Proverbs 4:28 is the end of the KJV's 4:27 ("Make straight the paths of thy feet")."""
    if c == 4 and v == 28:
        return 4, 27
    return c, v


def ecclesiastes(c: int, v: int) -> tuple:
    """The Vulgate's Ecclesiastes 4:17 is the KJV's 5:1, so its 5:n is the KJV's 5:n+1; its 7:1 is the KJV's 6:12,
    so its 7:n is the KJV's 7:n-1."""
    if c == 4 and v == 17:
        return 5, 1
    if c == 5:
        return 5, v + 1
    if c == 7:
        return (6, 12) if v == 1 else (7, v - 1)
    return c, v


def wisdom(c: int, v: int) -> tuple:
    """The Vulgate's Wisdom against the KJV's (Wisdom of Solomon): 2:25 is the end of the KJV's 2:24; 5:14 is a line
    the KJV lacks, after 5:13, so 5:15 on is one verse back; 6:1 ("Wisdom is better than strength") and 6:23 are lines
    the KJV lacks, put with the verses beside them; 9:19 is the end of the KJV's 9:18; the Vulgate's 11:5-6 are the
    KJV's 11:5; its 17:9 is the KJV's 17:9-10 and its 19:12 the KJV's 19:12-13, so the verses after them are one on."""
    if c == 2 and v == 25:
        return 2, 24
    if c == 5 and v >= 14:
        return 5, max(13, v - 1)
    if c == 6:
        if v == 1:
            return 6, 1
        if v <= 22:
            return 6, v - 1
        return 6, max(21, v - 2)
    if c == 9 and v == 19:
        return 9, 18
    if c == 11 and v >= 6:
        return 11, v - 1
    if c == 17 and v >= 10:
        return 17, v + 1
    if c == 19 and v >= 13:
        return 19, v + 1
    return c, v


SIRACH = json.loads((Path(__file__).resolve().parent / "glossa" / "versification" / "32.json").read_text(encoding="utf-8"))


def sirach(c: int, v: int) -> tuple:
    """The Vulgate's Ecclesiasticus against the KJV's Sirach: 1,209 of its 1,591 verses number differently (it has lines
    the KJV lacks, and the two split many verses differently), so scripts/glossa/versification/32.json gives the KJV verse
    for each Douay-Rheims verse, found by lining the two translations up by their words (monotonic, by word overlap)
    and checked against the glosses' words. The edition's 29:16-35 differ from the Douay-Rheims's (sirach_douay)."""
    c, v = sirach_douay(c, v)
    if str(v) not in SIRACH.get(str(c), {}):
        return c, v                                 # the edition's empty chapter 52 (no Douay-Rheims verse, no notes)
    kc, kv = SIRACH[str(c)][str(v)].split(":")
    return int(kc), int(kv)


def sirach_douay(c: int, v: int) -> tuple:
    """The edition's Ecclesiasticus 29:16-17 are lines the Douay-Rheims has at 17:18-19 ("The alms of a man is as a
    signet"), kept where they stand; its 29:18 is the Douay-Rheims's 29:16 ("Better than the shield"), and its 29:19-35
    the Douay-Rheims's 29:18-34."""
    if c == 29 and v == 18:
        return 29, 16
    return (c, v - 1) if c == 29 and v >= 19 else (c, v)


VERSIFICATION = {"Job": job, "Sirach": sirach, "Wisdom of Solomon": wisdom, "Proverbs": proverbs,"Hosea": hosea, "Amos": amos, "Jonah": jonah, "Micah": micah, "Haggai": haggai,
                 "Song of Solomon": song, "Ecclesiastes": ecclesiastes}
# ... and where the edition's own verse numbers differ from the Douay-Rheims's (for the card's Douay-Rheims text)
DOUAY_NUMBERS = {"Sirach": sirach_douay}

# Where a Vulgate verse straddles two of the KJV's, the glosses on the words the KJV puts in the other verse go there
# (gloss id -> KJV chapter and verse). Hosea 6:1 begins with the end of KJV 5:15 ("In their affliction they will rise
# early to me"), and Hosea 11:1 with the end of KJV 10:15 ("As the morning passeth, so hath the king of Israel passed
# away"); two long notes filed under those words are about another verse.
MOVES = {
    "49_marg3426": (2, 23),     # Haggai: "and will make thee as a signet", on the Vulgate's 2:24, filed under 2:23
    "50_marg3491": (5, 5), "50_marg3492": (5, 5),   # Zechariah: the angel's going forth and "lift up thy eyes", filed under 5:7
    "50_marg3493": (5, 6),      # "This is the vessel", filed under 5:8
    "51_interl7280": (3, 13), "51_interl7281": (3, 13),   # Malachi: "What have we spoken against thee?" ends the KJV's 3:13
    # Song of Songs: the Vulgate's 5:1 begins with the KJV's 4:16b ("Let my beloved come into his garden"), its 7:1
    # with the KJV's 6:13b ("What shalt thou see in the Sulamitess")
    **{f"30_{g}": (4, 16) for g in ("marg1124", "marg1125", "interl2905", "interl2906", "interl2907", "interl2908",
                                    "interl2909", "marg1126", "interl2910", "interl2911", "interl2912", "interl2913")},
    **{f"30_{g}": (6, 13) for g in ("interl3129", "interl3130", "interl3131", "marg1216", "marg1217")},
    # Ecclesiastes: the notes on 4:9 ("Better therefore that two should be together") filed under 4:8, with the
    # Laodicean's reading of 4:13-16 (one of Jerome's series on those verses); the introduction to the three readings
    # of 12:1-7, filed under 11:10; the note on "the conclusion of the discourse" (12:13), filed under 12:14
    "29_marg715": (4, 9), "29_marg716": (4, 9), "29_marg717": (4, 13), "29_marg800": (12, 1), "29_marg811": (12, 13),
    # Lamentations: Paschasius' and Gilbert's introduction to the third alphabet, filed under 3:66
    **{f"35_{g}": (3, 1) for g in ("marg2712", "marg2713", "marg2714")},
    **{f"40_{g}": (5, 15) for g in ("interl3821", "marg2339", "interl3822", "interl3823", "interl3824", "interl3825")},
    "40_marg2340": (6, 2), "40_marg2341": (6, 2),
    **{f"40_{g}": (10, 15) for g in ("interl4129", "marg2449", "marg2450", "interl4130", "interl4131", "interl4132")},
    # the Vulgate's Hosea 6:3 is the KJV's 6:2 up to "we shall live in his sight"; "We shall know, and we shall follow on"
    # begins the KJV's 6:3
    **{f"40_{g}": (6, 3) for g in ("interl3841", "interl3842", "interl3843", "interl3844", "interl3845", "marg2342",
                                    "marg2343", "interl3846", "interl3847", "marg2344")},
    # the Vulgate's Hosea 10:15 begins with the end of the KJV's 10:14 ("the mother was dashed upon her children")
    "40_marg2448": (10, 14),
    # the Vulgate's Amos 5:1 ends "is fallen, and it shall rise no more", which the KJV puts in 5:2
    **{f"42_{g}": (5, 2) for g in ("interl4895", "interl4896", "interl4897", "interl4898", "marg2761")},
    # the notes on the Vulgate's Micah 5:11's sorceries and divinations go to the KJV's 5:12, which has those words; two
    # long notes the edition files a verse or so early ("How shall he depart", "And they shall beat") go to their verse
    "45_interl5698": (5, 12), "45_interl5699": (5, 12),
    "45_marg3013": (2, 4), "45_marg3041": (4, 3),
    # the edition's Habakkuk 1:3 carries a doublet of 1:13-14 ("Why lookest thou upon the despisers ... And thou wilt
    # make men as the fishes of the sea"); the glosses on those words go to the verses that have them
    **{f"47_interl{n}": (1, 13) for n in range(6053, 6061)},
    **{f"47_interl{n}": (1, 14) for n in range(6061, 6064)},
    # Proverbs: the note on "and he shall have no need of spoils" (the end of 31:11), filed under 31:12
    "28_marg589": (31, 11),
    # Job: long notes the edition files a verse or two late, under the next verse ("neither shall his place know him",
    # 7:10; "why hast thou set me opposite", 7:20; "stripped the naked", 22:6; "Who shut up the sea with doors" and
    # "When I made a cloud the garment", 38:8-9; "fourteen thousand sheep", 42:12), and the Vulgate's 30:16 ("And now
    # my soul fadeth"), which the edition runs into 30:15
    "25_marg839": (7, 10), "25_marg851": (7, 20), "25_marg1355": (22, 6), "25_marg1974": (38, 8),
    "25_marg1975": (38, 9), "25_marg2201": (42, 12),
    "25_interl3072": (30, 16), "25_marg1663": (30, 16), "25_interl3073": (30, 16),
    # Wisdom: words the KJV has in the verse before or after the Vulgate's: "a reproach among the dead" (4:18), "the
    # care of discipline is love" (6:17), "But thy wrath endured not for ever" (16:5), "for they suffered justly"
    # (19:13), "For in all things thou didst magnify thy people" (19:22); and the note on Joseph sold (10:13), filed
    # under 10:14
    "31_interl3509": (4, 18), "31_interl3605": (6, 17), "31_marg1405": (10, 13),
    "31_interl3973": (16, 5), "31_marg1458": (16, 5), "31_marg1497": (19, 13), "31_marg1500": (19, 22),
    # Sirach: words the KJV has in the verse before or after the one the Vulgate's verse maps to (the two split many
    # verses differently), each checked against both; and notes the edition files a verse early ("There is one that
    # holdeth his peace", 20:5; "With what wisdom shall he be furnished", 38:25)
    "32_interl4482": (12, 6), "32_marg1713": (17, 3), "32_interl4656": (17, 3), "32_marg1714": (17, 3),
    "32_interl4764": (19, 5), "32_interl4561": (15, 5), "32_interl4760": (19, 6), "32_interl4761": (19, 6), "32_interl6012": (41, 23), "32_interl6204": (47, 15),
    "32_interl4240": (6, 35), "32_interl4485": (12, 5), "32_interl4545": (14, 24), "32_interl4618": (16, 11),
    "32_interl4769": (19, 16), "32_marg1760": (20, 5), "32_interl4923": (22, 8), "32_interl5280": (28, 8),
    "32_interl5311": (28, 24), "32_marg1908": (28, 24), "32_marg1925": (30, 15),
    "32_marg1956": (33, 9), "32_marg1959": (33, 14), "32_interl5548": (34, 16), "32_interl5549": (34, 16),
    "32_interl5599": (35, 17), "32_interl5647": (36, 17), "32_interl5750": (38, 7), "32_interl5764": (38, 12),
    "32_interl5795": (38, 25),
    "32_marg2011": (38, 12), "32_interl5924": (40, 5), "32_interl5925": (40, 5), "32_marg2063": (42, 6),
    "32_marg2070": (42, 18), "32_marg2076": (43, 4), "32_marg2089": (43, 16), "32_interl6129": (44, 20),
    "32_interl6153": (45, 8), "32_interl6154": (45, 8), "32_interl6155": (45, 8),   # the long robe, breeches, ephod
    "32_interl6200": (47, 14), "32_interl6201": (47, 14), "32_interl6226": (47, 23), "32_interl6227": (47, 23),
    "32_interl6283": (50, 4), "32_interl6284": (50, 4), "32_interl6289": (50, 7), "32_marg2146": (50, 14),
    "32_marg2165": (51, 15),
}
# ... and the words those long notes are about, in the Douay-Rheims's English
WORDS = {"29_marg717": "Better is a child that is poor and wise, than a king that is old and foolish, who knoweth not "
                       "to foresee for hereafter",
         "29_marg800": "Remember thy Creator",
         "29_marg811": "Let us all … together the conclusion of the discourse",
         "40_marg2340": "He will revive us after two days: on the third day he will raise us up",
         "40_marg2341": "He will revive us after two days: on the third day he will raise us up",
         "40_marg2451": "and I loved him: and I called … out of Egypt",
         "45_interl5698": "and I will take away sorceries out of thy hand",
         "45_interl5699": "and there shall be no divinations in thee",
         "45_marg3013": "how shall he depart from me, whereas he is returning that will divide our land?",
         "45_marg3041": "and they shall beat their swords into ploughshares, and their spears into spades",
         "46_interl6006": "her",
         # (the doublet's own words, so that they follow the notes on the verse's first half)
         "47_interl6053": "Why lookest thou upon the despisers", "47_interl6054": "Why lookest thou upon the despisers",
         "47_interl6055": "and holdest thy peace", "47_interl6056": "and holdest thy peace",
         "47_interl6057": "when … treadeth down", "47_interl6058": "the wicked", "47_interl6059": "the wicked",
         "47_interl6060": "the man that is more just than himself?",
         "47_interl6279": "Let rottenness enter into my bones",   # (a "but" the edition files under no words)
         "48_interl6394": "Her princes are in the midst of her",  # introduces 3:3, under 3:2's last words
         # Proverbs: one Latin "et" is "and" in most verses but "but" in 1:30; "egestas" is "want" except in 13:18
         "28_interl110": "but", "28_interl111": "but", "28_interl866": "Poverty"}  # introduces 3:3, under 3:2's last words
# ... and those of them that stay where the edition has them: a gloss only on a short word ("eius") that the book's
# lemmas give in another verse's sense ("his" in Nahum 1:13, "her" in 3:10)
IN_PLACE = {"46_interl6006", "47_interl6279", "48_interl6394"}


def render(notes: list) -> str:
    """A verse's notes, each phrase of the verse once, in the order the edition first explains it, with all its notes
    under it: the short ones written between the lines first, then the long ones from the margin. A note under a
    heading ("Jerome", "Allegorically") or under no words stands on its own where it falls."""
    groups, order = {}, []
    for i, (words, kind, text) in enumerate(notes):
        key = words if words and words not in LABELS else i
        if key not in groups:
            groups[key] = []
            order.append(key)
        groups[key].append((kind != "interl", text))
    lines = []
    for key in order:
        if not isinstance(key, str):
            words, _, text = notes[key]
            lines.append(f"*{LABELS[words]}:* {text}" if words in LABELS else text)
            continue
        texts = [t for _, t in sorted(groups[key], key=lambda g: g[0])]
        if len(texts) == 1:
            lines.append(f"**“{key}”** — {texts[0]}")
        else:
            lines.append(f"**“{key}”**")
            lines.extend(f"• {t}" for t in texts)
    return "\n".join(lines)


def clean(s: str) -> str:
    return re.sub(r"\s*\{t\. [^}]*\}\s*", " ", s).strip()


DRB = ROOT / "data" / "drb.json"
DR_NAMES = {"Hosea": "Osee", "Obadiah": "Abdias", "Jonah": "Jonas", "Micah": "Micheas", "Habakkuk": "Habacuc",
            "Zephaniah": "Sophonias", "Haggai": "Aggeus", "Zechariah": "Zacharias", "Malachi": "Malachias",
            "Song of Solomon": "Canticles", "Isaiah": "Isaias", "Jeremiah": "Jeremias", "Ezekiel": "Ezechiel",
            "Wisdom of Solomon": "Wisdom", "Sirach": "Ecclesiasticus"}


def douay(name: str, latin: dict, to_kjv, moved_from: dict) -> dict:
    """The Douay-Rheims's words for each KJV verse the Glossa comments on, since its notes quote that Bible, not the
    KJV: the Vulgate verse(s) numbered as that KJV verse ({ch: {v: "text"}}); a KJV verse no Vulgate verse maps onto
    (its words begin a Vulgate verse filed under the one before) gets the Vulgate verse its notes were moved from."""
    dr = json.loads(DRB.read_text(encoding="utf-8"))[DR_NAMES.get(name, name)]
    found = {}
    for c, verses in latin.items():
        for v in verses:
            found.setdefault(to_kjv(int(c), int(v)), []).append((c, v))
    for where, sources in moved_from.items():
        found.setdefault(where, sorted(sources, key=lambda cv: (int(cv[0]), int(cv[1]))))
    out = {}
    renumber = DOUAY_NUMBERS.get(name)
    if renumber:
        found = {k: list(dict.fromkeys(tuple(map(str, renumber(int(c), int(v)))) for c, v in s))
                 for k, s in found.items()}
    for (kc, kv), sources in sorted(found.items()):
        text = " ".join(dr.get(c, {}).get(v, "") for c, v in sources).strip()
        if text:
            refs = ", ".join(f"{c}:{v}" for c, v in sources)
            out.setdefault(str(kc), {})[str(kv)] = {"ref": refs, "text": text}
    return out


def main():
    books, douays = {}, {}
    for n, name in BOOKS.items():
        latin = json.loads((LATIN / f"{n}.json").read_text(encoding="utf-8"))
        english = json.loads((ENGLISH / f"{n}.json").read_text(encoding="utf-8"))
        lemmas = json.loads((LEMMAS / f"{n}.json").read_text(encoding="utf-8"))
        to_kjv = VERSIFICATION.get(name, lambda c, v: (c, v))
        notes = {}                                  # (KJV chapter, verse) -> [(words, kind, English)]
        moved_from = {}                             # KJV verse -> the Vulgate verses of the notes moved there
        missing = []
        for c, verses in latin["chapters"].items():
            for v, glosses in verses.items():
                for g in glosses:
                    if not g["latin"].strip():
                        continue                    # blank in the edition (e.g. Sirach marg1883): nothing to translate
                    text = english.get(g["id"])
                    if not text:
                        missing.append(g["id"])
                        continue
                    words = WORDS.get(g["id"]) or lemmas.get(clean(g["lemma"]), "")
                    where = MOVES.get(g["id"]) or to_kjv(int(c), int(v))
                    if g["id"] in MOVES:
                        moved_from.setdefault(where, set()).add((c, v))
                    notes.setdefault(where, []).append((words, g["type"], text, g["id"]))
        chapters = {}
        for (kc, kv), verse_notes in sorted(notes.items()):
            # a note refiled under other words (WORDS) takes its place among that phrase's notes, not where it stood
            verse_notes.sort(key=lambda note: note[3] in WORDS and note[3] not in IN_PLACE)
            chapters.setdefault(str(kc), {})[str(kv)] = render([note[:3] for note in verse_notes])
        if missing:
            raise SystemExit(f"{name}: {len(missing)} glosses not yet in English, e.g. {missing[:3]}")
        books[f"Glossa Ordinaria on {name}"] = chapters
        douays[name] = {"book": DR_NAMES.get(name, name),
                        "verses": douay(name, latin["chapters"], to_kjv, moved_from)}
    data = {"source": "trans. for ScriptureBot from the Latin (ed. Morard, 1480/81 text)", "books": books,
            "douay": douays}
    OUT.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{len(books)} books, {sum(len(v) for c in books.values() for v in c.values())} verses -> "
          f"{OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
