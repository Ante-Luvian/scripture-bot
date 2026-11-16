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
BOOKS = {"03": "Genesis", "04": "Exodus", "05": "Leviticus", "06": "Numbers", "07": "Deuteronomy", "08": "Joshua",
         "09": "Judges", "10": "Ruth", "12": "1 Samuel", "13": "2 Samuel", "14": "1 Kings", "15": "2 Kings",
         "16": "1 Chronicles", "17": "2 Chronicles", "18": "Ezra", "19": "Nehemiah", "20": "1 Esdras",
         "21": "2 Esdras", "22": "Tobit", "23": "Judith", "24": "Esther", "25": "Job","28": "Proverbs", "29": "Ecclesiastes", "30": "Song of Solomon", "31": "Wisdom of Solomon", "32": "Sirach", "33": "Isaiah", "34": "Jeremiah", "35": "Lamentations", "36": "Baruch", "37": "Ezekiel", "38": "Daniel", "40": "Hosea", "41": "Joel", "42": "Amos", "43": "Obadiah", "44": "Jonah", "45": "Micah", "46": "Nahum", "47": "Habakkuk", "48": "Zephaniah", "49": "Haggai", "50": "Zechariah", "51": "Malachi", "52": "1 Maccabees", "53": "2 Maccabees", "74": "Acts", "60": "Romans", "61": "1 Corinthians", "62": "2 Corinthians", "63": "Galatians", "64": "Ephesians", "65": "Philippians", "66": "Colossians", "67": "1 Thessalonians", "68": "2 Thessalonians", "69": "1 Timothy", "70": "2 Timothy", "71": "Titus", "72": "Philemon", "73": "Hebrews", "76": "James", "77": "1 Peter", "78": "2 Peter", "79": "1 John", "80": "2 John", "81": "3 John", "82": "Jude", "83": "Revelation"}  # Gloss-e's numbers -> the KJV's names (the books translated so far)
LABELS = {"[allegorically]": "Allegorically", "[the moral sense]": "In the moral sense", "[Jerome]": "Jerome",
          "[Haimo]": "Haimo", "[Gregory]": "Gregory", "[Paschasius]": "Paschasius", "[mystically]": "Mystically",
          "[historically]": "Historically", "[Gilbert]": "Gilbert", "[Alcuin]": "Alcuin"}
# (the later books' lemmas give these headings plainly: a source or a sense, not words of the verse)
LABELS.update({w: w for w in ("Allegorically", "Morally", "Mystically", "Historically", "Jerome", "Gregory", "Bede",
                              "Augustine", "Strabo", "Isidore", "Alcuin", "Rabanus", "Haimo", "Origen", "Ambrose",
                              "Pliny", "Gilbert", "The same", "Otherwise")})


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


def genesis(c: int, v: int) -> tuple:
    """The Vulgate's Genesis 49:31 holds the KJV's 49:31-32 (so its 49:32 is the KJV's 49:33), and its 50:22 holds the
    KJV's 50:22-23 (so its 50:23-25 are the KJV's 50:24-26)."""
    if c == 49 and v == 32:
        return 49, 33
    if c == 50 and v >= 23:
        return 50, v + 1
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


def judith_douay(c: int, v: int) -> tuple:
    """The edition splits the Douay-Rheims's Judith 4:5 in two (its 4:6 begins "that they should take possession of
    the ascents"), so its 4:6 is the Douay-Rheims's 4:5 and its 4:7-17 the Douay-Rheims's 4:6-16."""
    if c == 4 and v >= 6:
        return 4, v - 1
    return c, v


def jeremiah(c: int, v: int) -> tuple:
    """The Vulgate's Jeremiah 37:4 is the KJV's 37:4-5 (Jeremias walking free, and Pharao's army coming up), so its
    37:5-20 are the KJV's 37:6-21."""
    return (37, v + 1) if c == 37 and v >= 5 else (c, v)


def daniel(c: int, v: int) -> tuple:
    """The Vulgate's Daniel 3:91-97 are the KJV's 3:24-30 (its 3:24-90, the Prayer of Azarias and the Song of the
    Three Children, are a book of the KJV's Apocrypha: song_of_three), its 3:98-100 the KJV's 4:1-3, and its 4:1-34
    the KJV's 4:4-37. (Its 13 and 14, Susanna and Bel and the Dragon, are other books of the Apocrypha too.)"""
    if c == 3 and v >= 98:
        return 4, v - 97
    if c == 3 and v >= 91:
        return 3, v - 67
    if c == 4:
        return 4, v + 3
    return c, v


# The Vulgate's Daniel 3:24-90 as the verses of the KJV's Song of the Three Children: one ahead from 3:53 (the
# Vulgate's 3:52 is the KJV's 29-30), and where the two put the canticle's lines in another order, by the line
SONG_OF_THREE_ORDER = {54: 33, 55: 32, 58: 37, 59: 36, 69: 49, 70: 50, 71: 47, 72: 48}


def song_of_three(c: int, v: int) -> tuple:
    return 1, SONG_OF_THREE_ORDER.get(v, v - 23 if v <= 52 else v - 22)


def bel(c: int, v: int) -> tuple:
    """The Vulgate's Daniel 13:65 ("And king Astyages was gathered to his fathers") is the KJV's Bel 1, and its 14:1-41
    are Bel 2-42; its 14:42 ends the KJV's 42."""
    return (1, 1) if c == 13 else (1, min(v + 1, 42))


def isaiah_douay(c: int, v: int) -> tuple:
    """The edition numbers Isaiah as the KJV does, but the Douay-Rheims splits 45:23 in two ("For every knee shall be
    bowed to me" is its 45:24) and joins the KJV's 46:12 to 46:11, so the edition's 45:24-25 are the Douay-Rheims's
    45:25-26 and its 46:13 the Douay-Rheims's 46:12 (its 46:12 is the end of the Douay-Rheims's 46:11)."""
    if c == 45 and v >= 24:
        return 45, v + 1
    if c == 46 and v >= 12:
        return 46, v - 1 if v == 13 else 11
    return c, v


def table(n: str, douay_numbers=None):
    """The KJV verse for each Douay-Rheims verse, from scripts/glossa/versification/<n>.json, which lists only the
    verses the two number differently. Made (2026-11-15) by lining the two translations up a book at a time by their
    words (monotonic, by word overlap, weighted towards keeping a verse's own number), then checked against the
    glosses' words by tests/test_glossa.py. Jerome's Latin often splits and joins verses differently from the Hebrew
    the KJV follows (Exodus 38-40 most of all), and his Tobias and Judith are a different, longer text from the Greek
    the KJV's Tobit and Judith translate: their extra lines go with the KJV verse nearest them."""
    diffs = json.loads((Path(__file__).resolve().parent / "glossa" / "versification" / f"{n}.json")
                       .read_text(encoding="utf-8"))

    def to_kjv(c: int, v: int) -> tuple:
        if douay_numbers:
            c, v = douay_numbers(c, v)
        found = diffs.get(str(c), {}).get(str(v))
        if not found:
            return c, v
        kc, kv = found.split(":")
        return int(kc), int(kv)
    return to_kjv


# 3 Esdras (the KJV's 1 Esdras) has no Douay-Rheims; from its chapter 8 the edition numbers a verse to three ahead of
# the KJV (checked by hand against the KJV for each verse with notes)
ESDRAS1 = {(8, 11): (8, 10), (8, 26): (8, 23), (8, 32): (8, 29), (8, 33): (8, 30), (8, 37): (8, 34), (8, 38): (8, 35),
           (8, 45): (8, 43), (8, 52): (8, 51), (8, 75): (8, 74), (8, 93): (8, 92), (9, 49): (9, 48)}


def esdras1(c: int, v: int) -> tuple:
    return ESDRAS1.get((c, v), (c, v))


def esdras2(c: int, v: int) -> tuple:
    """The edition's 4 Esdras (the KJV's 2 Esdras) numbers chapter 7 as modern editions do, leaving out 7:36-105, a
    passage the KJV's text lacked too; so its 7:106-139 are the KJV's 7:36-69."""
    if c == 7 and v >= 106:
        return 7, v - 70
    return c, v


VERSIFICATION = {"Exodus": table("04"), "Leviticus": table("05"), "Numbers": table("06"),
                 "Deuteronomy": table("07"), "Joshua": table("08"), "1 Chronicles": table("16"),
                 "Judges": table("09"), "1 Samuel": table("12"), "1 Kings": table("14"), "Nehemiah": table("19"),
                 "Tobit": table("22"), "Judith": table("23", judith_douay), "1 Esdras": esdras1, "2 Esdras": esdras2,
                 "Genesis": genesis, "Job": job, "Sirach": sirach, "Wisdom of Solomon": wisdom, "Proverbs": proverbs,"Hosea": hosea, "Amos": amos, "Jonah": jonah, "Micah": micah, "Haggai": haggai,
                 "Song of Solomon": song, "Ecclesiastes": ecclesiastes,
                 "Jeremiah": jeremiah, "Daniel": daniel, "Song of the Three Children": song_of_three,
                 "Susanna": lambda c, v: (1, v), "Bel and the Dragon": bel, "1 Maccabees": table("52"),
                 "2 Maccabees": table("53"),
                 # the Vulgate joins the KJV's 2 Corinthians 13:12-13 ("all the saints salute you") into its 13:12, and
                 # splits the KJV's 3 John 14 and Revelation 13:1 ("And I stood upon the sand of the sea" is its 12:18)
                 "2 Corinthians": lambda c, v: (13, 14) if (c, v) == (13, 13) else (c, v),
                 "3 John": lambda c, v: (1, 14) if v == 15 else (c, v),
                 "Revelation": lambda c, v: (13, 1) if (c, v) == (12, 18) else (c, v),
                 # the Vulgate's Acts 7:55 and 14:6 each hold two of the KJV's verses, so the verses after are one on
                 "Acts": lambda c, v: (c, v + 1) if (c == 7 and v >= 56) or (c == 14 and v >= 7) else (c, v)}
# ... and where the edition's own verse numbers differ from the Douay-Rheims's (for the card's Douay-Rheims text)
DOUAY_NUMBERS = {"Sirach": sirach_douay, "Judith": judith_douay, "Isaiah": isaiah_douay}
# The edition's 2 Paralipomenon 37 is the Prayer of Manasses (the KJV's "Prayer of Manasseh", in its Apocrypha):
# Gloss-e's book number -> {chapter: (the KJV book it belongs to, its chapter there)}
SPLIT = {"17": {"37": ("Prayer of Manasseh", "1")}}
# ... and books of the KJV's Apocrypha that are verses of a Vulgate book: (KJV book, which (chapter, verse) are its)
VERSE_SPLIT = {"38": (("Song of the Three Children", lambda c, v: c == 3 and 24 <= v <= 90),
                      ("Susanna", lambda c, v: c == 13 and v <= 64),
                      ("Bel and the Dragon", lambda c, v: (c == 13 and v == 65) or c == 14))}

# Where a Vulgate verse straddles two of the KJV's, the glosses on the words the KJV puts in the other verse go there
# (gloss id -> KJV chapter and verse). Hosea 6:1 begins with the end of KJV 5:15 ("In their affliction they will rise
# early to me"), and Hosea 11:1 with the end of KJV 10:15 ("As the morning passeth, so hath the king of Israel passed
# away"); two long notes filed under those words are about another verse.
MOVES = {
    # Isaiah: notes the edition files a verse or two early (found by which Douay-Rheims verse has their words)
    # where the Vulgate divides verses differently from the KJV: "their land is filled with horses" (the KJV's 2:7),
    # "Manasses Ephraim, and Ephraim Manasses ... against Juda" (9:21), "Her time is near at hand" (13:22)
    "33_interl296": (2, 7), "33_interl297": (2, 7), "33_interl298": (2, 7), "33_marg120": (2, 7), "33_marg121": (2, 7),
    "33_interl1278": (9, 21), "33_interl1279": (9, 21), "33_interl1280": (9, 21), "33_interl1281": (9, 21),
    "33_interl1771": (13, 22), "33_interl1772": (13, 22), "33_interl1773": (13, 22), "33_marg461": (13, 22),
    "33_interl1774": (13, 22), "33_interl1775": (13, 22),
    # Lucifer's "I will ascend into heaven", filed under 14:12
    "33_interl1853": (14, 13), "33_interl1854": (14, 13), "33_interl1855": (14, 13), "33_marg483": (14, 13), "33_marg484": (14, 13), "33_interl1856": (14, 13), "33_interl1857": (14, 13), "33_interl1858": (14, 13), "33_interl1859": (14, 13), "33_marg485": (14, 13),
    # chapter 15's margins, gathered under its last verse, each by the Douay-Rheims words of its heading
    "33_marg533": (15, 2), "33_marg535": (15, 3), "33_marg536": (15, 4), "33_marg537": (15, 4),
    "33_marg538": (15, 5), "33_marg539": (15, 5), "33_marg540": (15, 6), "33_marg541": (15, 7),
    "33_marg542": (15, 7), "33_marg543": (15, 8),
    # "to the place of the name of the Lord of hosts, mount Sion" (18:7), filed under 18:2, which it echoes
    "33_interl2279": (18, 7), "33_interl2280": (18, 7), "33_marg616": (18, 7),
    # the watchman "upon the watchtower of the Lord", filed under 21:7
    "33_interl2583": (21, 8), "33_marg670": (21, 8), "33_interl2584": (21, 8), "33_interl2585": (21, 8), "33_marg671": (21, 8), "33_interl2586": (21, 8), "33_interl2587": (21, 8), "33_interl2588": (21, 8), "33_interl2589": (21, 8), "33_marg672": (21, 8),
    # "Take a harp, go about the city", filed under 23:15
    "33_interl2927": (23, 16), "33_interl2928": (23, 16), "33_marg751": (23, 16), "33_interl2929": (23, 16), "33_interl2930": (23, 16), "33_interl2931": (23, 16), "33_interl2932": (23, 16), "33_interl2933": (23, 16), "33_interl2934": (23, 16), "33_interl2935": (23, 16), "33_interl2936": (23, 16), "33_interl2937": (23, 16), "33_interl2938": (23, 16), "33_marg752": (23, 16),
    # "the earth shall be utterly laid waste", filed under 24:2
    "33_interl2972": (24, 3), "33_interl2973": (24, 3), "33_interl2974": (24, 3), "33_interl2975": (24, 3),
    # "they shall rush in unto Jacob" and "hath he struck him", filed under 27:5
    "33_interl3390": (27, 6), "33_interl3391": (27, 6), "33_interl3392": (27, 6), "33_interl3393": (27, 6), "33_interl3394": (27, 6), "33_interl3395": (27, 6), "33_interl3396": (27, 6), "33_interl3397": (27, 6), "33_interl3398": (27, 6), "33_interl3399": (27, 6),
    "33_interl3400": (27, 7), "33_interl3401": (27, 7), "33_interl3402": (27, 7), "33_interl3403": (27, 7), "33_interl3404": (27, 7), "33_interl3405": (27, 7),
    # "from the channel of the river", filed under 27:11
    "33_interl3444": (27, 12), "33_interl3445": (27, 12), "33_interl3446": (27, 12), "33_interl3447": (27, 12), "33_interl3448": (27, 12), "33_marg829": (27, 12), "33_marg830": (27, 12), "33_interl3449": (27, 12), "33_interl3450": (27, 12), "33_interl3451": (27, 12),
    # "as a storm of hail", filed under 28:1
    "33_interl3475": (28, 2), "33_interl3476": (28, 2), "33_interl3477": (28, 2), "33_interl3478": (28, 2), "33_interl3479": (28, 2), "33_interl3480": (28, 2),
    # "a spirit of judgment", filed under 28:5
    "33_interl3491": (28, 6), "33_interl3492": (28, 6), "33_interl3493": (28, 6), "33_interl3494": (28, 6), "33_marg837": (28, 6),
    # "them that are weaned from the milk", filed under 28:8
    "33_interl3512": (28, 9), "33_interl3513": (28, 9), "33_interl3514": (28, 9), "33_interl3515": (28, 9), "33_interl3516": (28, 9), "33_marg838": (28, 9),
    # "scatter cummin", filed under 28:24
    "33_interl3617": (28, 25), "33_interl3618": (28, 25), "33_marg845": (28, 25),
    # "this people draw near me" and "the wisdom of their wise men shall perish", filed under 29:12
    "33_interl3682": (29, 13), "33_interl3683": (29, 13), "33_interl3684": (29, 13), "33_interl3685": (29, 13), "33_interl3686": (29, 13), "33_interl3687": (29, 13), "33_marg855": (29, 13),
    "33_interl3688": (29, 14), "33_marg856": (29, 14), "33_interl3689": (29, 14), "33_interl3690": (29, 14),
    # "shall cry without", filed under 33:6
    "33_interl4149": (33, 7), "33_interl4150": (33, 7), "33_interl4151": (33, 7), "33_interl4152": (33, 7),
    # "Hearken unto me, O house of Jacob" (the edition's 46:3 is empty), filed under 46:2
    "33_interl5792": (46, 3), "33_marg1173": (46, 3), "33_interl5793": (46, 3), "33_interl5794": (46, 3), "33_interl5795": (46, 3), "33_interl5796": (46, 3), "33_interl5797": (46, 3), "33_interl5798": (46, 3), "33_interl5799": (46, 3), "33_interl5800": (46, 3), "33_marg1174": (46, 3),
    # "Look unto Abraham your father", filed under 51:1
    "33_interl6405": (51, 2), "33_interl6406": (51, 2), "33_interl6407": (51, 2), "33_interl6408": (51, 2), "33_interl6409": (51, 2),
    # "he put on justice as a breastplate", filed under 59:16
    "33_interl7624": (59, 17), "33_interl7625": (59, 17), "33_interl7626": (59, 17), "33_interl7627": (59, 17),
    # "a seed out of Jacob", filed under 65:8
    "33_marg1547": (65, 9),
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
    # Genesis: notes the edition files a verse late: Noe begetting Sem, Cham and Japheth (5:32), "And on the third
    # day" (22:4), and Jacob's twenty years' service and his wages changed ten times (31:41)
    "03_marg402": (5, 32), "03_marg689": (22, 4), **{f"03_interl{n}": (31, 41) for n in range(1600, 1604)},
    # Exodus to Tobit: a long note the edition files a verse late or early (each read against its words: "If a thief
    # be found breaking up", Exodus 22:2; "the Levites ... instead of every firstborn", Numbers 3:12; "And they served
    # Baalim", Judges 2:11; Hanon shaving David's messengers, 1 Chronicles 19:1-5, filed at the chapter's end), or
    # words the Latin verse has that the KJV puts in the verse before or after ("the Egyptians dead upon the sea
    # shore", Exodus 14:30; "I will give you rain", Leviticus 26:4; "And the seventh month was come", Nehemiah 7:73;
    # Tobias's city in the upper parts of Galilee, Tobit 1:2)
    "04_interl3058": (14, 30), "04_marg1405": (22, 2), "04_marg1668": (29, 1), "04_interl4718": (32, 32),
    "04_interl4917": (37, 2), "04_interl4949": (40, 14),
    "05_marg2041": (8, 7), "05_marg2273": (15, 19), "05_marg2344": (18, 7), "05_interl6788": (25, 15),
    "05_marg2577": (25, 15), "05_interl6902": (26, 4), "05_interl6903": (26, 4), "05_marg2621": (26, 4),
    "05_marg2699": (27, 17), "05_marg2671": (26, 46), "05_marg2672": (26, 46), "06_marg621": (30, 4),
    "07_marg852": (6, 13),
    "06_marg72": (3, 12), "06_marg75": (3, 12), "06_marg236": (11, 21), "06_marg284": (15, 24), "06_marg293": (16, 37),
    "06_marg294": (16, 37), "06_marg297": (16, 39), "06_interl321": (16, 42), "06_marg300": (16, 42),
    "06_marg455": (22, 6),
    "07_interl705": (1, 9),
    "09_marg193": (2, 11), "09_marg204": (3, 14), "09_marg220": (4, 8),
    "12_marg554": (5, 4), "12_marg559": (6, 4), "12_marg579": (7, 5),
    "12_interl961": (26, 10),   # (on 1 Samuel 26:10's "unless the Lord shall strike him", which the edition has at 24:7)
    "13_interl1050": (3, 7),
    "15_marg1314": (18, 29),
    "16_marg1596": (19, 1),
    "17_marg1750": (5, 1), "17_marg1791": (9, 20),
    "18_interl28": (2, 5),
    "19_interl201": (7, 73), "19_marg249": (7, 73),
    **{f"22_{g}": (1, 2) for g in ("interl324", "marg369", "interl325", "interl327")},
    "22_interl338": (1, 6), "22_interl359": (1, 12), "22_interl360": (1, 12), "22_interl734": (13, 18),
    "22_interl735": (13, 18), "22_marg433": (14, 2), "22_marg436": (14, 12),
    "23_marg442": (1, 5), "23_interl809": (2, 27), "23_interl862": (4, 2), "23_interl867": (4, 1),
    "23_interl873": (4, 5), "23_interl874": (4, 5), "23_interl944": (5, 10), "23_interl952": (5, 12), "23_marg463": (8, 5),
    **{f"23_interl{n}": (10, 4) for n in range(1123, 1127)}, "23_interl1154": (12, 10), "23_interl1190": (13, 9),
    "23_interl1243": (14, 13),
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
    # Jeremiah: notes the edition files a verse off (their words are in the next or last Douay verse), and 28:12's
    # "And Jeremias the prophet went his way", which ends the KJV's 28:11
    "34_interl8924": (4, 30), "34_interl8925": (4, 30), "34_interl8928": (4, 30), "34_interl8929": (4, 30),
    "34_interl8930": (4, 30), "34_marg1770": (4, 30), "34_interl9172": (7, 20), "34_marg2170": (24, 1),
    "34_interl10168": (24, 5), "34_interl10169": (24, 5), "34_interl10172": (24, 5), "34_interl10212": (25, 27),
    "34_marg2194": (25, 27), "34_marg2245": (28, 15), "34_interl10285": (28, 11),
    # Ezekiel: the Douay's 2:1 begins with the end of the KJV's 1:28 ("This was the vision of the likeness of the
    # glory of the Lord ... I fell upon my face") and its 2:9 runs on into the KJV's 2:10, its 28:11 into 28:12 ("take
    # up a lamentation") and its 40:8 holds the end of the KJV's 40:7 (the threshold by the porch); and a few notes
    # filed a verse off
    "37_interl12275": (1, 28), "37_interl12276": (1, 28), "37_interl12279": (1, 28), "37_marg2972": (2, 1),
    "37_interl12331": (2, 10), "37_interl12334": (2, 10), "37_marg2991": (2, 10), "37_interl12612": (7, 2),
    "37_marg3121": (7, 2), "37_marg3214": (11, 13), "37_marg3604": (28, 12), "37_interl15019": (36, 3),
    "37_marg3874": (40, 7),
    # Daniel: notes filed a verse off, and "the king thought to set him over all the kingdom", which ends the KJV's 6:3
    "38_marg4259": (1, 7), "38_marg4260": (1, 7), "38_interl16398": (2, 47), "38_interl16399": (2, 47),
    "38_interl16714": (6, 3), "38_interl16945": (8, 17),
    # The epistles and the Apocalypse: notes the edition files a verse off, or gathers at the end of a passage
    # (1 John 1:2 and 2:29), each found by which Douay verse has its words; and where the Douay divides a verse
    # differently from the KJV (Romans 3:25-26, 5:8-9, 16:10-11, 1 Corinthians 15:26-27, Galatians 4:31-5:1,
    # Apocalypse 20:7-9), under the KJV verse that has the words
    "60_marg220": (3, 25), "60_marg322": (6, 21), "60_interl515": (3, 25), "60_marg569": (11, 10),
    "60_marg570": (11, 10), "60_marg679": (14, 14), "60_marg710": (15, 15), "60_interl726": (5, 8),
    "60_marg726": (16, 10), "60_marg727": (16, 10), "60_marg741": (16, 25), "60_interl978": (6, 21),
    "60_interl979": (6, 21), "60_interl980": (6, 21), "60_interl981": (6, 21), "60_interl984": (6, 21),
    "60_interl985": (6, 21), "60_interl1523": (9, 11), "60_interl1813": (11, 10), "60_interl1815": (11, 10),
    "60_interl2243": (14, 14), "60_interl2470": (16, 10), "60_interl2520": (16, 25), "60_interl2521": (16, 25),
    "61_marg1240": (14, 33), "61_interl3136": (6, 16), "61_interl3137": (6, 16), "61_interl3139": (6, 16),
    "61_interl3608": (10, 21), "61_interl3614": (10, 23), "61_interl4226": (15, 15), "61_interl4227": (15, 15),
    "61_interl4274": (15, 27), "61_interl4290": (15, 29), "62_interl5286": (7, 16), "62_interl5392": (8, 19),
    "63_marg63": (2, 20), "63_interl95": (1, 18), "63_interl98": (1, 18), "63_marg129": (4, 6),
    "63_interl230": (2, 20), "63_marg232": (6, 8), "63_marg233": (6, 8), "63_marg234": (6, 8), "63_interl495": (5, 1),
    "63_interl679": (6, 8), "63_interl681": (6, 8), "65_marg461": (1, 16), "65_marg553": (3, 13),
    "65_interl1607": (1, 17), "65_interl1609": (1, 16), "67_interl2610": (1, 3), "67_interl2648": (1, 10),
    "67_interl2650": (1, 10), "67_interl2652": (1, 10), "67_interl2653": (1, 10), "67_interl2657": (2, 2),
    "67_interl2658": (2, 2), "67_interl2673": (2, 6), "67_interl2675": (2, 6), "67_interl2803": (3, 10),
    "67_interl2804": (3, 10), "67_interl2805": (3, 10), "67_interl2841": (4, 3), "69_marg970": (5, 19),
    "69_marg971": (5, 19), "69_interl3651": (5, 19), "70_marg1043": (2, 11), "73_marg1209": (2, 7),
    "73_marg1336": (7, 13), "73_marg1548": (12, 24), "73_interl4570": (1, 10), "73_interl4571": (1, 10),
    "73_interl4733": (2, 18), "73_interl4734": (2, 18), "73_interl4735": (2, 18), "73_interl4782": (3, 9),
    "73_interl4819": (3, 18), "73_interl4822": (3, 19), "73_interl5217": (7, 10), "73_interl5235": (7, 13),
    "73_interl5236": (7, 13), "73_interl5237": (7, 13), "73_interl5267": (7, 19), "73_interl5268": (7, 19),
    "73_interl5817": (11, 16), "73_interl5846": (11, 25), "73_interl5847": (11, 25), "73_interl6010": (12, 18),
    "73_interl6011": (12, 18), "73_interl6037": (12, 24), "73_interl6038": (12, 24), "73_interl6039": (12, 24),
    "76_marg990": (1, 23), "77_marg1172": (2, 19), "77_interl3307": (2, 19), "79_marg1331": (1, 3),
    "79_marg1332": (1, 5), "79_marg1333": (1, 5), "79_marg1338": (1, 7), "79_marg1352": (2, 4),
    "79_marg1358": (2, 12), "79_marg1359": (2, 28), "79_marg1360": (2, 28), "79_marg1365": (2, 15),
    "79_marg1366": (2, 15), "79_marg1374": (2, 19), "79_marg1423": (3, 19), "79_marg1424": (3, 19),
    "79_interl3702": (1, 3), "79_interl3717": (1, 7), "79_interl3718": (1, 7), "79_interl3720": (1, 7),
    "79_interl3737": (2, 28), "79_interl3744": (2, 4), "79_interl3779": (2, 11), "79_interl3780": (2, 11),
    "79_interl3782": (2, 12), "79_interl3783": (2, 12), "79_interl3788": (2, 13), "79_interl3789": (2, 12),
    "79_interl3790": (2, 13), "79_interl3792": (2, 14), "79_interl3796": (2, 15), "79_interl3797": (2, 15),
    "79_interl3798": (2, 15), "79_interl3799": (2, 15), "79_interl3803": (2, 16), "79_interl3804": (2, 16),
    "79_interl3805": (2, 17), "79_interl3816": (2, 19), "79_interl3948": (3, 24), "80_interl4100": (1, 5),
    "83_marg1731": (2, 28), "83_marg1835": (5, 9), "83_marg1836": (5, 9), "83_marg2083": (13, 10),
    "83_marg2293": (20, 9), "83_interl5365": (13, 5), "83_interl5366": (13, 7), "83_interl5993": (20, 8),
    "83_interl5996": (20, 8), "83_interl5998": (20, 8), "83_interl6001": (20, 9), "83_interl6003": (20, 9),
    "83_interl6004": (20, 9),
    "61_interl2781": (3, 5), "61_interl2782": (3, 5), "61_interl3103": (6, 9), "61_interl4276": (15, 27), "64_interl969": (2, 15),
    "65_marg498": (2, 8), "83_interl4611": (2, 27), "83_interl5992": (20, 8), "83_interl6009": (20, 10),
    # Acts: notes filed a verse off, and where the Douay divides verses differently (7:59 / 8:1 "Saul was consenting")
    "74_interl53": (1, 10), "74_interl470": (3, 19), "74_interl471": (3, 19), "74_interl185": (2, 10), "74_marg399": (8, 1), "74_interl1045": (8, 9),
    "74_marg468": (9, 6), "74_marg469": (9, 6), "74_interl1341": (10, 25), "74_interl1428": (10, 46),
    "74_interl1482": (11, 26), "74_interl1702": (13, 31), "74_interl1732": (13, 39), "74_marg704": (15, 34),
    "74_interl2056": (16, 37), "74_interl2249": (19, 14), "74_marg789": (19, 14), "74_interl2572": (24, 18),
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
DR_NAMES = {"Revelation": "Apocalypse", "Hosea": "Osee", "Obadiah": "Abdias", "Jonah": "Jonas", "Micah": "Micheas", "Habakkuk": "Habacuc",
            "Zephaniah": "Sophonias", "Haggai": "Aggeus", "Zechariah": "Zacharias", "Malachi": "Malachias",
            "Song of Solomon": "Canticles", "Isaiah": "Isaias", "Jeremiah": "Jeremias", "Ezekiel": "Ezechiel",
            "Wisdom of Solomon": "Wisdom", "Sirach": "Ecclesiasticus", "Joshua": "Josue", "1 Samuel": "1 Kings",
            "2 Samuel": "2 Kings", "1 Kings": "3 Kings", "2 Kings": "4 Kings", "1 Chronicles": "1 Paralipomenon",
            "2 Chronicles": "2 Paralipomenon", "Ezra": "1 Esdras", "Nehemiah": "2 Esdras", "Tobit": "Tobias",
            # (the KJV's 1-2 Esdras are the Vulgate's 3-4 Esdras, which the Douay-Rheims doesn't have)
            "1 Esdras": "3 Esdras", "2 Esdras": "4 Esdras", "Prayer of Manasseh": "Prayer of Manasses",
            "Song of the Three Children": "Daniel", "Susanna": "Daniel", "Bel and the Dragon": "Daniel",
            "1 Maccabees": "1 Machabees", "2 Maccabees": "2 Machabees"}


def douay(name: str, latin: dict, to_kjv, moved_from: dict) -> dict:
    """The Douay-Rheims's words for each KJV verse the Glossa comments on, since its notes quote that Bible, not the
    KJV: the Vulgate verse(s) numbered as that KJV verse ({ch: {v: "text"}}); a KJV verse no Vulgate verse maps onto
    (its words begin a Vulgate verse filed under the one before) gets the Vulgate verse its notes were moved from."""
    dr = json.loads(DRB.read_text(encoding="utf-8")).get(DR_NAMES.get(name, name), {})
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
    parts = []                                      # (Gloss-e's number, the KJV's book, its chapters)
    for n, name in BOOKS.items():
        chapters = json.loads((LATIN / f"{n}.json").read_text(encoding="utf-8"))["chapters"]
        split = SPLIT.get(n, {})
        own = {c: vs for c, vs in chapters.items() if c not in split}
        for other, belongs in VERSE_SPLIT.get(n, ()):
            # (kept under the edition's own numbers, which the other book's VERSIFICATION maps)
            part = {c: {v: gs for v, gs in vs.items() if belongs(int(c), int(v))} for c, vs in own.items()}
            own = {c: {v: gs for v, gs in vs.items() if not belongs(int(c), int(v))} for c, vs in own.items()}
            parts.append((n, other, {c: vs for c, vs in part.items() if vs}))
        parts.append((n, name, {c: vs for c, vs in own.items() if vs}))
        for c, (other, kc) in split.items():
            parts.append((n, other, {kc: chapters[c]}))
    for n, name, latin_chapters in parts:
        english = json.loads((ENGLISH / f"{n}.json").read_text(encoding="utf-8"))
        lemmas = json.loads((LEMMAS / f"{n}.json").read_text(encoding="utf-8"))
        to_kjv = VERSIFICATION.get(name, lambda c, v: (c, v))
        notes = {}                                  # (KJV chapter, verse) -> [(words, kind, English)]
        moved_from = {}                             # KJV verse -> the Vulgate verses of the notes moved there
        missing = []
        for c, verses in latin_chapters.items():
            for v, glosses in verses.items():
                for g in glosses:
                    if not g["latin"].strip():
                        continue                    # blank in the edition (e.g. Sirach marg1883): nothing to translate
                    if re.fullmatch(r"\+?\s*\[(?:[^\[\]]|\[[^\]]*\])*\]\s*", g["latin"]):
                        continue                    # only the editor's bracketed pointer (Daniel marg4586: "see the
                                                    # tables in the prologues"), not the Gloss's own words
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
        verses = douay(name, latin_chapters, to_kjv, moved_from)
        if verses:                                  # (the Douay-Rheims has no 3-4 Esdras or Prayer of Manasses)
            douays[name] = {"book": DR_NAMES.get(name, name), "verses": verses}
    data = {"source": "trans. for ScriptureBot from the Latin (ed. Morard, 1480/81 text)", "books": books,
            "douay": douays}
    OUT.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{len(books)} books, {sum(len(v) for c in books.values() for v in c.values())} verses -> "
          f"{OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
