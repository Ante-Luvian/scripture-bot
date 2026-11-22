"""
Each place's name as the Bibles spell it -> data/people_places/place_names.json, for !place's card ("Names") and
so that a search by any of them finds it (Galaad, Bethsura, Γαλααδ, גלעד):

  hebrew   the Hebrew word (Strong's dictionary form and transliteration), from the Westminster Leningrad Codex as
           data/interlinear/macula.db has it, word by word with Strong's numbers and English glosses: the word in the
           place's verses whose gloss is the place's name
  greek    the Septuagint's spelling (data/lxx_greek.json, Swete) for an Old Testament place; the Greek New
           Testament's (macula, with Strong's) for a New Testament one
  latin    the Vulgate's (Clementine, bolls.life's download, cached in scripts/.cache/bolls/)
  douay    the Douay-Rheims's (data/drb.json), the English most Catholic readers know
  nrsv     a modern English spelling: the New Revised Standard Version's (Catholic Edition, 1993, bolls.life's
           download; the NRSVue isn't downloadable)
  kjv      the KJV's (Theographic's kjvName)

The Septuagint, Vulgate and Douay-Rheims have no word-by-word key, so their spelling is found from the verses that
name the place: the proper name (a capitalised word) in those verses, or the verses either side where the Latin
and Greek number differently, that occurs in most of them and is most like the place's English name
(matched on a rough phonetic skeleton: "Gilead" ~ "Galaad" ~ "Γαλααδ").

    python scripts/build_place_names.py
"""
import difflib
import json
import re
import sqlite3
import unicodedata
import urllib.request
import zipfile
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "scripts" / ".cache"
OUT = ROOT / "data" / "people_places" / "place_names.json"
BOLLS_URL = "https://bolls.life/static/translations/{}.zip"

PROTESTANT = ["Genesis", "Exodus", "Leviticus", "Numbers", "Deuteronomy", "Joshua", "Judges", "Ruth", "1 Samuel",
              "2 Samuel", "1 Kings", "2 Kings", "1 Chronicles", "2 Chronicles", "Ezra", "Nehemiah", "Esther", "Job",
              "Psalms", "Proverbs", "Ecclesiastes", "Song of Solomon", "Isaiah", "Jeremiah", "Lamentations",
              "Ezekiel", "Daniel", "Hosea", "Joel", "Amos", "Obadiah", "Jonah", "Micah", "Nahum", "Habakkuk",
              "Zephaniah", "Haggai", "Zechariah", "Malachi", "Matthew", "Mark", "Luke", "John", "Acts", "Romans",
              "1 Corinthians", "2 Corinthians", "Galatians", "Ephesians", "Philippians", "Colossians",
              "1 Thessalonians", "2 Thessalonians", "1 Timothy", "2 Timothy", "Titus", "Philemon", "Hebrews", "James",
              "1 Peter", "2 Peter", "1 John", "2 John", "3 John", "Jude", "Revelation"]
NT = set(PROTESTANT[39:])
# bolls.life's book numbers past Revelation (translation_lookup.py)
BOLLS_EXTRA = {68: "Tobit", 69: "Judith", 70: "Wisdom of Solomon", 71: "Sirach", 73: "Baruch", 74: "1 Maccabees",
               75: "2 Maccabees"}
DR_NAMES = {"Joshua": "Josue", "1 Samuel": "1 Kings", "2 Samuel": "2 Kings", "1 Kings": "3 Kings",
            "2 Kings": "4 Kings", "1 Chronicles": "1 Paralipomenon", "2 Chronicles": "2 Paralipomenon",
            "Ezra": "1 Esdras", "Nehemiah": "2 Esdras", "Song of Solomon": "Canticles", "Isaiah": "Isaias",
            "Jeremiah": "Jeremias", "Ezekiel": "Ezechiel", "Hosea": "Osee", "Obadiah": "Abdias", "Jonah": "Jonas",
            "Micah": "Micheas", "Habakkuk": "Habacuc", "Zephaniah": "Sophonias", "Haggai": "Aggeus",
            "Zechariah": "Zacharias", "Malachi": "Malachias", "Revelation": "Apocalypse", "Tobit": "Tobias",
            "Wisdom of Solomon": "Wisdom", "Sirach": "Ecclesiasticus", "1 Maccabees": "1 Machabees",
            "2 Maccabees": "2 Machabees"}

GREEK = dict(zip("αβγδεζηθικλμνξοπρστυφχψως", ["a", "b", "g", "d", "e", "z", "e", "th", "i", "k", "l", "m", "n", "x",
                                                  "o", "p", "r", "s", "t", "u", "ph", "ch", "ps", "o", "s"]))
# capitalised words that are not names (sentence openings in the Latin and English, God's titles)
NOT_NAMES = {"Dominus", "Domini", "Domino", "Dominum", "Deus", "Dei", "Deo", "Deum", "Et", "In", "Ego", "Tu", "Ecce",
             "Lord", "God", "And", "The", "Then", "But", "For", "Behold", "Thus", "Now", "So", "Israel", "Israël",
             "Ut", "Si", "Ad", "De", "Ex", "Ab", "Ne", "Is", "Ea", "Id", "He", "It", "Of", "To", "If", "My", "We", "Ye",
             "Lo", "As", "At", "By", "Oh", "Me", "Us", "Do", "Go", "No",
             # (the Greek without its accents: strip_marks)
             "Και", "Εν", "Ο", "Η", "Το", "Οι", "Αι", "Τα", "Κυριος", "Κυριου", "Κυριω", "Κυριον", "Κυριε", "Θεος",
             "Θεου", "Θεω", "Θεον", "Θεε", "Ισραηλ", "Ιακωβ", "Ιουδα", "Ιουδας"}
# the words of a compound name that are not the name itself ("Mount Ebal", "the Brook of Egypt", "the Valley Gate")
GENERIC = {"mount", "mountain", "mountains", "hill", "brook", "river", "valley", "vale", "sea", "lake", "gate", "pool",
           "wilderness", "desert", "plain", "plains", "land", "city", "tower", "well", "spring", "springs", "fountain",
           "wall", "of", "the", "upper", "lower", "great", "mons", "montem", "montis", "monte", "torrens", "vallis",
           "mare", "porta", "desertum", "terra", "civitas", "valle", "vallem", "valles", "torrente", "torrentem",
           "torrentis", "portam", "portæ", "fons", "fontis", "fontem", "campus", "campo", "mari", "maris", "flumen",
           "fluminis", "montes", "montium", "deserto", "solitudo", "solitudinem", "turris", "turrim", "lacus"}


def strip_marks(s: str) -> str:
    return "".join(ch for ch in unicodedata.normalize("NFKD", s) if not unicodedata.combining(ch))


def skeleton(s: str) -> str:
    """A rough sound-shape for comparing a name across languages: Gilead, Galaad and Γαλααδ come out alike."""
    s = strip_marks(s).lower().replace("æ", "ae").replace("œ", "oe")
    s = "".join(GREEK.get(ch, ch) for ch in s)
    s = re.sub(r"[^a-z]", "", s)
    for a, b in (("ph", "f"), ("th", "t"), ("ch", "c"), ("k", "c"), ("q", "c"), ("z", "s"), ("j", "i"), ("y", "i"),
                 ("v", "u"), ("w", "u"), ("ou", "u"), ("ae", "e"), ("ai", "e"), ("oe", "e"), ("h", "")):
        s = s.replace(a, b)
    return re.sub(r"(.)\1+", r"\1", s)


def likeness(a: str, b: str) -> float:
    a, b = skeleton(a), skeleton(b)
    if not a or not b:
        return 0.0
    n = min(len(a), len(b), 4)                       # (declined forms: Αἰγύπτου ~ Egypt, Galaad ~ Galaaditis)
    return max(difflib.SequenceMatcher(None, a, b).ratio(),
               0.9 * difflib.SequenceMatcher(None, a[:len(b) + 1], b).ratio() if a[:n] == b[:n] else 0)


def cached(url: str, name: str) -> Path:
    path = CACHE / name
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        req = urllib.request.Request(url, headers={"User-Agent": "ScriptureBot/1.0"})
        path.write_bytes(urllib.request.urlopen(req, timeout=300).read())
    return path


def bolls(slug: str) -> dict:
    """A whole Bible from bolls.life's download (the Vulgate, the NRSV), as {book: {chapter: {verse: text}}}."""
    with zipfile.ZipFile(cached(BOLLS_URL.format(slug), f"bolls/{slug}.zip")) as z:
        rows = json.loads(z.read(z.namelist()[0]).decode("utf-8"))
    out = {}
    for r in rows:
        name = PROTESTANT[r["book"] - 1] if r["book"] <= 66 else BOLLS_EXTRA.get(r["book"])
        if name:
            text = re.sub(r"<[^>]+>", "", r["text"])
            out.setdefault(name, {}).setdefault(str(r["chapter"]), {})[str(r["verse"])] = text
    return out


def psalm_number(kind: str, n: int) -> int:
    """The Greek and Latin number of a psalm by its Hebrew (KJV) number (near enough for a window of verses)."""
    if kind not in ("greek", "latin", "douay") or n < 10:
        return n
    if n <= 113:
        return n - 1
    if n in (114, 115):
        return 113
    if n == 116:
        return 114
    return n - 1 if n <= 146 else 146


class Text:
    """A Bible as {book: {chapter: {verse: text}}}, its verses in order, for looking near a reference."""

    def __init__(self, books: dict, kind: str, names: dict = None):
        self.kind, self.names = kind, names or {}
        self.order, self.where = {}, {}
        for book, chapters in books.items():
            # (the KJV joins Beth–zur with an en dash)
            seq = [(c, v, re.sub(r"(?<=\w)[‐‑–](?=\w)", "-", unicodedata.normalize("NFC", chapters[c][v])))
                   for c in sorted(chapters, key=int)
                   for v in sorted(chapters[c], key=lambda x: int(re.match(r"\d+", x).group()))]
            self.order[book] = seq
            self.where[book] = {(c, v): i for i, (c, v, _) in enumerate(seq)}

    def near(self, ref: str, reach: int = 2) -> str:
        book, cv = ref.rsplit(" ", 1)
        c, v = cv.split(":")
        book = self.names.get(book, book)
        if book not in self.order:
            return ""
        if book == "Psalms":
            c = str(psalm_number(self.kind, int(c)))
        where = self.where[book]
        i = where.get((c, v))
        if i is None:                               # (a verse the Latin or Greek numbers into the next chapter)
            same = [j for (cc, vv), j in where.items() if cc == c]
            if not same:
                return ""
            i = max(same)
        seq = self.order[book]
        return " ".join(t for _, _, t in seq[max(0, i - reach):i + reach + 1])


def proper_names(text: str) -> list:
    """Capitalised words, each once: the names in a verse (not "Mount" or "Valley" standing alone)."""
    words = re.findall(r"[^\W\d_][^\W\d_'’\-]*(?:-[^\W\d_]+)*", text)
    out = []
    for w in words:
        plain = strip_marks(w)
        if w[0].isupper() and w not in NOT_NAMES and plain not in NOT_NAMES and len(w) > 1 \
                and plain.lower() not in GENERIC:
            out.append(w)
    # two names side by side, for the Latin's and Greek's "Jabes Galaad" (Jabesh-gilead)
    pairs = re.findall(r"(?=\b([^\W\d_][^\W\d_]+[ -][^\W\d_][^\W\d_]+)\b)", text)
    out += [w for w in pairs if all(x[0].isupper() and strip_marks(x).lower() not in GENERIC
                                    and strip_marks(x) not in NOT_NAMES for x in re.split(r"[ -]", w))]
    return list(dict.fromkeys(out))


GREEK_NOMINATIVE = ("ος", "ας", "ης", "α", "η", "ις", "ων")             # (commonest nominatives first)
LATIN_NOMINATIVE = ("us", "a", "is", "um", "on")
# the people of a place, not the place: Γαλααδείτης, Galaaditarum
GENTILIC = ("ιτης", "ιται", "ιτων", "ιτου", "ιτην", "ινος", "ινου", "ινων", "ινοις", "itæ", "itae", "itarum", "ites",
            "itas", "itam", "inus", "inæ", "inorum", "inis", "ian", "ians", "ite", "ans", "æorum", "aeorum", "ensibus",
            "enses", "ensium", "ηνης", "αιοις", "ιτας", "ειτας")
# case endings, stripped so a declined name's forms count together (Roma, Romam, Romae; Αἰγύπτου, Αἴγυπτον)
ENDINGS = sorted(["ου", "ος", "ον", "ας", "ης", "ει", "ων", "οις", "α", "η", "ι", "orum", "arum", "um", "us", "am",
                  "ae", "æ", "is", "em", "es", "i", "o", "a", "e"], key=len, reverse=True)


def stem(word: str) -> str:
    s = strip_marks(word).lower()
    for end in ENDINGS:
        if s.endswith(end) and len(s) - len(end) >= 3:
            s = s[:-len(end)]
            break
    return skeleton(s)[:6]


def spelling(text: Text, refs: list, english: list, kind: str, rivals: dict = None, reach: int = None):
    """The spelling of a place in `text` (see the module's docstring), or None. A word more like another person or
    place named in or beside the verse (`rivals`, by reference) than this one is theirs, not this one's."""
    rivals = rivals or {}
    refs = [r for r in refs if text.near(r)]
    if not refs:
        return None
    if len(refs) == 1 and reach is None:            # the verse itself first; its neighbours only if need be
        found = spelling(text, refs, english, kind, rivals, 0)
        if not found:                               # (numbered differently: only a name very like this one)
            found = spelling(text, refs, english, kind, rivals, 1)
            if found and max(likeness(found, e) for e in english) < 0.8:
                found = None
        return found
    seen = Counter()
    forms = defaultdict(Counter)
    for ref in refs:
        stems = set()
        for w in proper_names(text.near(ref, reach=1 if reach is None else reach)):
            sim = max(likeness(w, e) for e in english)
            if rivals.get(ref) and max(likeness(w, r) for r in rivals[ref]) > sim + 0.05:
                continue
            s = stem(w)
            forms[s][w] += 1
            stems.add(s)
        seen.update(sorted(stems))                  # (sorted: a tie goes the same way every build)
    need = 0.62 if len(refs) < 3 else 0.5
    if all(len(skeleton(e)) <= 3 for e in english):  # (Hor is not "Porro")
        need = 0.8
    best, best_score = None, 0.0
    for s, count in seen.items():
        coverage = count / len(refs)
        if coverage < (0.5 if len(refs) >= 3 else 0.99):
            continue
        word = max(forms[s], key=lambda w: max(likeness(w, e) for e in english))
        sim = max(likeness(word, e) for e in english)
        if sim < need:
            continue

        score = sim + coverage
        if score > best_score:
            best, best_score = s, score
    if best is None:
        return None
    # the form to show: of the commoner forms, the one most like the English name, a nominative by preference
    people = tuple(e.lower() for e in english if strip_marks(e).lower().endswith(GENTILIC))
    ranked = [(w, n) for w, n in forms[best].most_common()
              if not strip_marks(w).lower().endswith(GENTILIC) or strip_marks(w).lower().startswith(people or ("\0",))]
    if not ranked:                                  # (only "the Alexandrian", never Alexandria itself)
        return None
    top = ranked[0][1]
    ends = GREEK_NOMINATIVE if kind == "greek" else LATIN_NOMINATIVE if kind == "latin" else ()

    def rank(item):
        w, n = item
        plain = strip_marks(w).lower()
        tier = next((len(ends) - i for i, e in enumerate(ends) if plain.endswith(e)), 0) if n >= 0.05 * top else 0
        return round(max(likeness(w, e) for e in english), 1) >= 0.5, tier, round(max(likeness(w, e) for e in english), 1), n
    return max((x for x in ranked if x[1] >= 0.05 * top), key=rank)[0]


def core(name: str) -> str:
    """A compound name's name, without its "Mount", "Brook of" and the like: Mount Ebal -> Ebal, Ur of the Chaldees
    -> Ur ("" if nothing's left)."""
    return next((w for w in re.split(r"\s+", name) if w.lower() not in GENERIC), "")

def macula_names(db: Path) -> dict:
    """(book, chapter, verse) -> [(name, Strong's number)] for the words whose gloss holds a capitalised name
    ("Gilead", "of Egypt", "to Babylon": the name alone)."""
    out = defaultdict(list)
    con = sqlite3.connect(db)
    for book, c, v, text, strong, gloss in con.execute("select book, chapter, verse, text, strong, gloss from words"):
        # (not a one-letter prefix glossed with the name after it: the article, "to", "in")
        if gloss and strong and len([ch for ch in text or "" if ch.isalpha()]) > 1:
            for name in re.findall(r"\b[A-Z][\w'-]+", gloss):
                if name not in NOT_NAMES:
                    out[(book, str(c), str(v))].append((name, re.sub(r"[a-z]$", "", strong)))
    return out


APOCRYPHA = ["Tobit", "Judith", "Wisdom of Solomon", "Sirach", "Baruch", "1 Maccabees", "2 Maccabees", "1 Esdras",
             "2 Esdras", "Additions to Esther", "Song of the Three Children", "Susanna", "Bel and the Dragon",
             "Prayer of Manasseh"]


# a name in the Apocrypha that isn't the place of that name elsewhere: (place, book, or "" for all)
APOCRYPHA_NOT = {("Arab", ""): "Zabdiel the Arab, a man", ("Berea", ""): "a Berea in Judea, not Macedonia's",
                 ("Shur", ""): "Judith's Sur is on the coast", ("Tishbe", ""): "Tobit's Thisbe is in Naphtali",
                 ("Bethany", ""): "Judith's Betane is not Bethany", ("Gabbatha", ""): "Gabatha, a eunuch",
                 ("Cuthah", "1 Esdras"): "sons of Coutha, temple servants",
                 ("Elam", "1 Esdras"): "sons of Elam, a family", ("Sur", ""): "Judith's Sur is not the gate of Sur",
                 ("Esau", ""): "the children of Esau, a people", ("Addar", ""): "Adar, the month"}
# the Apocrypha's names for places the rest of the Bible names otherwise, each pairing borne out by Pleiades (the
# same site, or the two names under one entry: "Gazara" at Gezer's coordinates, "Hadid/Ad(d)ida", "Scythopolis"
# at Beth-shan's): name -> slug, or (name, book) -> slug (None: not that place there)
APOCRYPHA_SAME = {"Gazara": "gezer_463", "Jamnia": "jabneh_615", "Askalon": "ashkelon_103",
                  "Ascalon": "ashkelon_103", "Scythopolis": "beth-shan_232", "Esdraelon": "valley_of_jezreel_1211",
                  "Gerizim": "mount_gerizim_836", "Aradus": "arvad_99", "Carnaim": "karnaim_670",
                  "Adida": "hadid_503", "Adora": "adoraim_28", "Aphairema": "ephraim_401",
                  # the KJV's 1 and 2 Esdras: Jewry is Judea, Sion Zion, and Josiah dies at Magiddo (2 Chr 35:22)
                  "Jewry": "judea_657", "Sion": "jerusalem_636", "Magiddo": "megiddo_777",
                  "Carchamis": "carchemish_277", "Land of Judah": "judea_657",
                  # (Theographic's Sinai is a duplicate of Mount Sinai: Judith 5:14, 2 Esdras 3:17)
                  "Sinai": "mount_sinai_855", "Sina": "mount_sinai_855",
                  # the Maccabees' Mount Zion is the temple mount (1 Macc 4:37, 4:60), not Jerusalem at large; the
                  # Mount Sion of Deuteronomy 4:48 is Hermon, so the name goes to Zion here by rule
                  "Mount Zion": "mount_zion_860", "Mount Sion": "mount_zion_860",
                  # Sirach 24:13's "the heights of Hermon"; Wisdom 10:18 and 19:7's Red Sea
                  "Hermon": "mount_hermon_841", "Red Sea": "red_sea_986",
                  # Sirach's Egypt (1:1) is in the translator's prologue, which the NRSV's text runs into 1:1
                  ("Egypt", "Sirach"): None,
                  # Bozrah and Bosor in Gilead (1 Macc 5:26) are Bostra, not Edom's Bozrah; Kadesh of 1 Macc 11 is
                  # in Galilee; Judith's Kadesh (1:9) is not named precisely enough to place
                  ("Bozrah", "1 Maccabees"): "bozrah_257", ("Kadesh", "1 Maccabees"): "kedesh_676",
                  ("Kadesh", "Judith"): None,
                  # 1 Maccabees 10:83's Beth-dagon is Dagon's temple in Azotus, neither town of the name
                  ("Beth-dagon", "1 Maccabees"): None}

# Places only the Apocrypha name: (slug, name, other spellings to look for, kind, Pleiades id or None, books it's
# looked for in (None: all)). The site is Pleiades's where it has the place under that name and the verses fit it
# (Daphne "near Antioch", 2 Macc 4:33; Mallus with Tarsus, 4:30; Orthosia reached by ship, 1 Macc 15:37); where
# Pleiades has no such place, or several that the verses don't choose between (Arbela), the site is left unknown.
APOCRYPHA_PLACES = [
    ("rages_a1", "Rages", [], "City", "903104", ["Tobit"]),
    ("ragau_a2", "Ragau", [], "Region", None, ["Judith"]),
    ("elymais_a3", "Elymais", [], "Region", "912843", None),
    ("kaserin_a4", "Kaserin", [], "City", None, ["Tobit"]),
    ("thisbe_a5", "Thisbe", [], "City", None, ["Tobit"]),
    ("bethulia_a6", "Bethulia", [], "City", None, ["Judith"]),
    ("kona_a7", "Kona", [], "City", None, ["Judith"]),
    ("choba_a8", "Choba", [], "City", None, ["Judith"]),
    ("cyamon_a9", "Cyamon", [], "City", None, ["Judith"]),
    ("betomasthaim_a10", "Betomasthaim", [], "City", None, ["Judith"]),
    ("egrebeh_a11", "Egrebeh", [], "City", None, ["Judith"]),
    ("chusi_a12", "Chusi", [], "City", None, ["Judith"]),
    ("mochmur_a13", "Mochmur", [], "River", None, ["Judith"]),
    ("balbaim_a14", "Balbaim", ["Belmaim"], "City", None, ["Judith"]),   # (the KJV's, Judith 7:3)
    ("bectileth_a15", "Bectileth", [], "Region", None, ["Judith"]),
    ("chelous_a16", "Chelous", [], "City", None, ["Judith"]),
    ("ocina_a17", "Ocina", [], "City", None, ["Judith"]),
    ("sur_a18", "Sur (Judith)", ["Sur"], "City", None, ["Judith"]),
    ("sud_a19", "Sud", [], "River", None, ["Baruch"]),
    ("merran_a20", "Merran", [], "Region", None, ["Baruch"]),
    ("modein_a21", "Modein", [], "City", "687977", None),
    ("coelesyria_a22", "Coelesyria", ["Celosyria"], "Region", "678096", None),
    ("dathema_a23", "Dathema", [], "City", None, ["1 Maccabees"]),
    ("bosor_a24", "Bosor", [], "City", "678072", ["1 Maccabees"]),
    ("chaspho_a25", "Chaspho", [], "City", "678089", ["1 Maccabees"]),
    ("caspin_a26", "Caspin", [], "City", None, ["2 Maccabees"]),
    ("maked_a27", "Maked", [], "City", "678275", ["1 Maccabees"]),
    ("alema_a28", "Alema", [], "City", None, ["1 Maccabees"]),
    ("raphon_a29", "Raphon", [], "City", "678360", ["1 Maccabees"]),
    ("ephron_a30", "Ephron (in Gilead)", ["Ephron"], "City", "678157", ["1 Maccabees", "2 Maccabees"]),
    ("maapha_a31", "Maapha", [], "City", None, ["1 Maccabees"]),
    ("beth-zechariah_a32", "Beth-zechariah", [], "City", None, ["1 Maccabees"]),
    ("adasa_a33", "Adasa", [], "City", None, ["1 Maccabees"]),
    ("bethbasi_a34", "Bethbasi", [], "City", None, ["1 Maccabees"]),
    ("elasa_a35", "Elasa", [], "City", None, ["1 Maccabees"]),
    ("beth-zaith_a36", "Beth-zaith", [], "City", None, ["1 Maccabees"]),
    ("caphar-salama_a37", "Caphar-salama", [], "City", None, ["1 Maccabees"]),
    ("akrabattene_a38", "Akrabattene", [], "Region", None, ["1 Maccabees"]),
    ("mesaloth_a39", "Mesaloth", [], "City", None, ["1 Maccabees"]),
    ("arbela_a40", "Arbela", [], "Region", None, ["1 Maccabees"]),
    ("asphar_a41", "Asphar", [], "Water", None, ["1 Maccabees"]),
    ("nadabath_a42", "Nadabath", [], "City", None, ["1 Maccabees"]),
    ("phasiron_a43", "Phasiron", [], "City", None, ["1 Maccabees"]),
    ("berea_a44", "Berea (in Judea)", ["Berea"], "City", None, ["1 Maccabees"]),
    ("beroea_a45", "Beroea (Aleppo)", ["Beroea"], "City", "658409", ["2 Maccabees"]),
    ("sparta_a46", "Sparta", [], "City", "570685", None),
    ("delos_a47", "Delos", [], "Island", "599587", None),
    ("myndos_a48", "Myndos", [], "City", "599811", None),
    ("sicyon_a49", "Sicyon", [], "City", "570668", None),
    ("caria_a50", "Caria", [], "Region", "599564", None),
    ("halicarnassus_a51", "Halicarnassus", [], "City", "599636", None),
    ("phaselis_a52", "Phaselis", [], "City", "639051", None),
    ("sampsames_a53", "Sampsames", [], "City", None, None),
    ("orthosia_a54", "Orthosia", [], "City", "668325", None),
    ("persepolis_a55", "Persepolis", [], "City", "922695", None),
    ("daphne_a56", "Daphne", [], "City", "658450", ["2 Maccabees"]),
    ("tripolis_a57", "Tripolis", [], "City", "668394", ["2 Maccabees"]),
    ("mallus_a58", "Mallus", [], "City", "648702", ["2 Maccabees"]),
    ("charax_a59", "Charax", [], "City", None, ["2 Maccabees"]),
    # 1 Maccabees 9:15's hill, where Judas drove Bacchides' right wing: not the city of Azotus (Ashdod), on the coast
    ("mount_azotus_a60", "Mount Azotus", [], "Mountain", None, ["1 Maccabees"]),
]
# Sites for Apocrypha-only places that Pleiades has under another name, or not at all: slug -> (a Pleiades id, a
# located place's slug or (lat, lon); whether it's only roughly there; what the card says of it). Each pairing is
# a published identification, named in the comment.
APOCRYPHA_SITES = {
    # Josephus, Antiquities 12.11.1 (data/jewish/josephus.json): Bacchides "pitched his camp at Arbela, a city of
    # Galilee", and took "those that were there in caves". Pleiades 678029 is Galilee's Arbela (Arbel, above the
    # Sea of Galilee, with its caves); 678028 is Transjordan's (Irbid, Theographic's Beth-arbel)
    "arbela_a40": ("678029", False, "Arbela in Galilee, above the Sea of Galilee (Josephus, Antiquities 12.11.1)."),
    "mesaloth_a39": ("678029", True, "“Mesaloth, which is in Arbela” (1 Maccabees 9:2): shown at Arbela in Galilee."),
    # Tyndale's Bible Dictionary, ISBE, Hastings: "usually identified with Il'asa", between the two Beth-horons;
    # the point is Wikipedia's for the battle of Elasa
    "elasa_a35": ((31.8761, 35.2083), True, "Usually identified with Il'asa, near Beth-horon."),
    # Bacchides' camp, near Elasa: commonly taken for Beeroth (el-Bireh); the Jewish Encyclopedia calls the
    # evidence unsatisfactory, and some read Berzetho (Bir Zeit) instead
    "berea_a44": ("beeroth_168", True, "Probably Beeroth (el-Bireh), north of Jerusalem; some read Bir Zeit."),
    # the Jewish Encyclopedia and McClintock and Strong: perhaps "the mountain of Azor" (Baal-hazor), but doubtful
    "mount_azotus_a60": (None, False, "Not the city of Azotus on the coast, but a hill near Elasa; no site is "
                                      "agreed (some read “Mount Azor”, Baal-hazor)."),
}
APOCRYPHA_PLACES_OUT = ROOT / "data" / "people_places" / "apocrypha_places.json"


def pleiades() -> dict:
    """Pleiades's places by id (its CSV download, cached in scripts/.cache/pleiades/)."""
    import csv
    import gzip
    import io
    path = cached("https://atlantides.org/downloads/pleiades/dumps/pleiades-places-latest.csv.gz",
                  "pleiades/pleiades-places-latest.csv.gz")
    with gzip.open(path) as f:
        return {r["id"]: r for r in csv.DictReader(io.TextIOWrapper(f, encoding="utf-8"))}


def apocrypha_places(places: dict) -> dict:
    """APOCRYPHA_PLACES as place records like people_places.json's (their verses are added by apocrypha()), sited
    by Pleiades or APOCRYPHA_SITES."""
    pl = pleiades()
    out = {}
    for slug, name, also, kind, pid, books in APOCRYPHA_PLACES:
        site, rough, note = APOCRYPHA_SITES.get(slug, (None, False, ""))
        if isinstance(site, str) and site in places:                  # the site of a place already located
            pid, lat, lon = None, places[site]["lat"], places[site]["lon"]
        elif isinstance(site, tuple):
            pid, (lat, lon) = None, site
        else:
            pid = site or pid
            lat = lon = None
        r = pl.get(pid) if pid else None
        if pid and not r:
            raise SystemExit(f"Pleiades has no place {pid} ({name})")
        if r and r["reprLat"]:
            lat, lon = float(r["reprLat"]), float(r["reprLong"])
            # (Pleiades's own doubt: "Bosora?", a "rough" location)
            rough = rough or "?" in r["title"] or r["locationPrecision"] != "precise"
        if site is not None and lat is None:
            raise SystemExit(f"APOCRYPHA_SITES: no location for {name} ({site})")
        located = lat is not None
        out[slug] = {"name": name, "also": also, "kind": kind,
                     "lat": round(lat, 4) if located else None,
                     "lon": round(lon, 4) if located else None,
                     "approx": located and bool(rough),
                     "about": "", "within": [], "verses": [], "weight": 0,
                     "pleiades": f"https://pleiades.stoa.org/places/{pid}" if pid else "",
                     "books": books, "note": note}
    return out

# people of the Apocrypha whose names are like a place's (Antiochus, Antioch), without the Greek's accents
APOCRYPHA_PEOPLE = {"Antiochus", "Αντιοχος", "Αντιοχου", "Αντιοχω", "Αντιοχον", "Ptolemæus", "Ptolemaeus",
                    "Ptolemee", "Ptolemy", "Πτολεμαιος", "Πτολεμαιου", "Tobias", "Τωβιας", "Σειραχ", "Sirach",
                    "Jesse", "John", "Joannis", "Ιωαννης"}


def plain(name: str) -> str:
    return re.sub(r"[^a-zæœ]", "", strip_marks(name).lower())


def apocrypha(places, all_names, people, out, texts, new=None):
    """The places the Apocrypha name: a verse of the NRSV's Deuterocanon (or the KJV's Apocrypha, for 1 and 2 Esdras
    and the rest the NRSV's Catholic edition hasn't) that names a place as the NRSV or KJV spells it elsewhere
    (letter for letter, bar case and hyphens), and how each Bible spells it there (the KJV's "Bethsura" and the
    Septuagint's "Βεθσουρά" for Beth-zur). A name that's also a person's is left to the person unless the place is
    named oftener; a word the English also writes in lower case ("There", "Eat") isn't a name."""
    nrsv, kjv = texts["nrsv"], texts["kjv"]
    new = new or {}
    places = {**places, **new}
    all_names = {**all_names, **{s: [re.sub(r"\s*\(.*\)$", "", p["name"]), *p["also"]] for s, p in new.items()}}
    # the Apocrypha-only places, and the Apocrypha's other names for known ones, before any guessing
    fixed = defaultdict(list)                       # plain name -> [(slug or None, books or None)]
    for slug, p in new.items():
        for n in all_names[slug]:
            fixed[plain(n)].append((slug, p["books"]))
    for key, slug in APOCRYPHA_SAME.items():
        name, book = key if isinstance(key, tuple) else (key, None)
        fixed[plain(name)].append((slug, [book] if book else None))
    # (whole words only: "Beth-gilgal" doesn't make "gilgal" a word in lower case, which lost Gilgal, 1 Macc 9:2)
    lower = {w for text in (nrsv, kjv) for seq in text.order.values() for _, _, verse in seq
             for w in re.findall(r"(?<![\w-])[a-z]+(?![\w-])", verse)}
    person_weight = Counter()
    for x in people.values():
        for n in {x["name"], *x.get("also", [])}:
            person_weight[plain(n)] += len(x.get("verses", []))
    index = defaultdict(lambda: defaultdict(set))   # name -> rank (0 the place's own names, 1 its NRSV's) -> slugs
    for slug, names in all_names.items():
        for rank, ns in ((0, [*names, out.get(slug, {}).get("kjv", "")]), (1, [out.get(slug, {}).get("nrsv", "")])):
            for n in ns:
                if n and core(n) == n and len(plain(n)) >= 3 and n not in NOT_NAMES and plain(n) not in lower:
                    index[plain(n)][rank].add(slug)
    best = {}
    for name, ranks in index.items():
        slugs = ranks[min(ranks)]
        top = max(sorted(slugs), key=lambda x: len(places[x]["verses"]))
        if len(places[top]["verses"]) > person_weight[name]:
            best[name] = top
    found = defaultdict(list)
    ruled = defaultdict(set)                        # slug -> the names a rule gave it ("Sion" for Jerusalem)
    for text in (nrsv, kjv):
        for book in APOCRYPHA:
            if text is nrsv and book not in text.order or text is kjv and book in nrsv.order:
                continue
            for c, v, verse in text.order.get(book, []):
                names = proper_names(verse)
                pairs = [w for w in names if " " in w or "-" in w]
                parts = {x for w in pairs if plain(w) in best or plain(w) in fixed for x in re.split(r"[ -]", w)}
                for w in names:
                    ref = f"{book} {c}:{v}"
                    # ("Mount Zion": the verse's words give only "Zion")
                    # (and "Red Sea": "Red")
                    mount = re.search(r"\bmount " + re.escape(w) + r"\b", verse, re.I)
                    sea = re.search(r"\b" + re.escape(w) + r" sea\b", verse, re.I)
                    # (and "the land of Judah", the country, where "Judah" alone is the patriarch's: 1 Macc 9:1)
                    land = re.search(r"\bland of " + re.escape(w) + r"\b", verse, re.I)
                    rule = [s for key in ([plain("Mount " + w)] if mount else []) + \
                            ([plain(w + " Sea")] if sea else []) + ([plain("Land of " + w)] if land else []) + \
                            [plain(w)]
                            for s, books in fixed.get(key, []) if books is None or book in books][:1]
                    if rule:
                        slug = rule[0]
                        if slug and any(s == slug for s, _ in fixed.get(plain(w), [])):
                            ruled[slug].add(w)          # (so `!place Sion` and `!place Gazara` find it)
                    else:
                        slug = best.get(plain(w))
                        if slug:
                            name = re.sub(r"\s*\(.*\)$", "", places[slug]["name"])
                            if (name, "") in APOCRYPHA_NOT or (name, book) in APOCRYPHA_NOT:
                                continue
                    if not slug or w in parts and not rule or ref in found[slug]:
                        continue
                    found[slug].append(ref)
    other_places = {plain(n): s for s, ns in all_names.items() for n in ns}
    named = defaultdict(set)                        # verse -> the places named in it ("Choba" is not Kona's)
    for slug, refs in found.items():
        for r in refs:
            named[r].update((slug, n) for n in all_names[slug])

    def beside(ref):
        book, cv = ref.rsplit(" ", 1)
        c, v = cv.split(":")
        return set().union(*(named.get(f"{book} {c}:{int(v) + d}", set()) for d in (-1, 0, 1)))

    for slug, refs in found.items():
        own = {skeleton(n) for n in all_names[slug]}
        rivals = {r: [n for other, n in beside(r) if other != slug and skeleton(n) not in own] for r in refs}
        entry = out.setdefault(slug, {})
        entry["apocrypha"] = refs
        if slug in new:                             # the Apocrypha's own spellings are its names here
            # verse by verse: a verse that names it only as "the fortress" (1 Maccabees 5:29) doesn't count against it
            got = Counter(s for r in refs if (s := spelling(kjv, [r], all_names[slug], "modern", rivals)))
            entry["kjv"] = got.most_common(1)[0][0] if got else ""
            entry["nrsv"] = all_names[slug][0] if any(r.rsplit(" ", 1)[0] in nrsv.order for r in refs) else ""
            entry = {k: v for k, v in entry.items() if v}
            out[slug] = entry
        known = [n for n in [*all_names[slug], *(entry.get(k) for k in ("kjv", "latin", "douay", "nrsv"))] if n]
        greek = [entry["greek"]] if entry.get("greek") else []
        spellings = []
        for key, text in texts.items():
            names = greek + known if key == "greek" else known
            got = spelling(text, [r for r in refs if r.rsplit(" ", 1)[0] in text.order
                                  or text.names.get(r.rsplit(" ", 1)[0]) in text.order],
                           names, key if key in ("greek", "latin") else "modern", rivals)
            if not got or strip_marks(got) in APOCRYPHA_PEOPLE or other_places.get(plain(got), slug) != slug \
                    or strip_marks(got).lower().endswith(GENTILIC) or max(likeness(got, n) for n in names) < 0.7:
                continue
            if got not in entry.values() and got not in all_names[slug] and got not in spellings:
                spellings.append(got)
        for got in sorted(ruled[slug]):
            if got not in entry.values() and got not in all_names[slug] and got not in spellings:
                spellings.append(got)
        if spellings:
            entry["apocrypha_spellings"] = spellings
    return found

# where the KJV's text gives only part of the name (it writes "Adami, Nekeb", "Atroth, Shophan", "Baale of Judah"),
# or another place's (Babylon for Babylonia; Sharon for Acts 9:35's Saron): Theographic's kjvName stands
KJV_AS_THEOGRAPHIC = {"adami-nekeb_23", "atroth-shophan_119", "baale-judah_139", "babylonia_152", "saron_1063"}


def main():
    theo = json.loads((CACHE / "theographic" / "places.json").read_text(encoding="utf-8"))
    kjv_name = {r["fields"]["slug"]: r["fields"].get("kjvName", "") for r in theo}
    places = json.loads((ROOT / "data" / "people_places" / "people_places.json").read_text(encoding="utf-8"))["places"]
    for p in places.values():                       # each place's spellings from its own verses, not a duplicate's
        merged = set(p.get("merged", []))
        p["verses"] = [r for r in p["verses"] if r not in merged]
    strongs = json.loads((ROOT / "data" / "strongs" / "strongs_dictionary.json").read_text(encoding="utf-8"))
    words = macula_names(ROOT / "data" / "interlinear" / "macula.db")
    lxx = Text(json.loads((ROOT / "data" / "lxx_greek.json").read_text(encoding="utf-8"))["books"], "greek")
    vul = Text(bolls("VULG"), "latin")
    nrsv = Text(bolls("NRSVCE"), "modern")
    dr = Text(json.loads((ROOT / "data" / "drb.json").read_text(encoding="utf-8")), "douay", DR_NAMES)
    # the KJV's own spelling from its text: Theographic's kjvName is sometimes another Bible's (Magadan for the
    # KJV's Magdala), so it is only the fallback
    kjv_text = Text(json.loads((ROOT / "data" / "kjv" / "kjv_canon.json").read_text(encoding="utf-8"))["books"], "kjv")

    common = {w for text in (nrsv, kjv_text) for seq in text.order.values() for _, _, verse in seq
              for w in re.findall(r"(?<![\w-])[a-z]+(?![\w-])", verse)}  # words written in lower case ("tower")

    def names_of(slug, p):
        names = [n for n in dict.fromkeys([re.sub(r"\s*\(.*\)$", "", p["name"]), *p.get("also", []),
                                           kjv_name.get(slug, "")]) if n]
        # Theographic's "Tower" for the Tower of Hananel: the whole name first, or a Bible's "Tower" passes for it
        whole = [n for n in names[1:] if " " not in names[0] and n != names[0]
                 and re.search(r"\b" + re.escape(names[0]) + r"\b", n, re.I) and plain(names[0]) in common]
        return [whole[0], *(n for n in names if n != whole[0])] if whole else names
    all_names = {slug: names_of(slug, p) for slug, p in places.items()}
    people = json.loads((ROOT / "data" / "people_places" / "people_places.json").read_text(encoding="utf-8"))["people"]
    # names a compound name can borrow ("the Gate of Benjamin", "the Sea of Galilee"): other places and people
    every_name = {skeleton(n) for s, ns in all_names.items() for n in ns if core(ns[0]) == ns[0]} \
        | {skeleton(x["name"]) for x in people.values()}
    named = defaultdict(set)                        # verse -> the people's and places' names in it
    for group, key in ((places, "place"), (people, "person")):
        for slug, x in group.items():
            ns = all_names[slug] if key == "place" else [x["name"], *x.get("also", [])]
            for r in x.get("verses", []):
                named[r].update((slug, n) for n in ns)

    def beside(ref):                                # (a neighbour in a list of towns is often a verse away)
        book, cv = ref.rsplit(" ", 1)
        c, v = cv.split(":")
        return set().union(*(named.get(f"{book} {c}:{int(v) + d}", set()) for d in (-1, 0, 1)))

    out = {}
    for slug, p in places.items():
        english = all_names[slug]
        primary = english[0]
        cores = [c for c in dict.fromkeys(core(n) for n in english) if c and c not in english]
        compound = core(primary) != primary
        # the core of "the Brook of Egypt" is another place, so the Greek and Latin for it would be Egypt's
        borrowed = compound and skeleton(core(primary)) in every_name
        match = english + cores
        own = {skeleton(n) for n in match}
        rivals = {r: [n for other, n in beside(r) if other != slug and skeleton(n) not in own
                      and skeleton(core(n)) not in own] for r in p["verses"]}
        refs = p["verses"]
        ot = [r for r in refs if r.rsplit(" ", 1)[0] not in NT]
        nt = [r for r in refs if r.rsplit(" ", 1)[0] in NT]
        entry = {}
        if kjv_name.get(slug) and not (borrowed and kjv_name[slug] == core(primary)):
            entry["kjv"] = kjv_name[slug]
        if borrowed:
            match = [primary]
        # a word in another language for "the Valley" or "the Old Gate" isn't a name (Hor of Mount Hor is)
        heart = [c for c in dict.fromkeys(core(n) for n in english) if c]
        name_part = re.search(r"\b" + re.escape(core(primary)) + r"\b", kjv_name.get(slug) or primary) \
            if core(primary) else None
        foreign_ok = not borrowed and (not compound or bool(name_part and name_part.group()[:1].isupper()))
        # the Hebrew and the New Testament's Greek: the word glossed with the place's name, commonest first
        for key, group, prefix in (("hebrew", ot, "H"), ("greek_nt", nt, "G")):
            if not foreign_ok:
                break
            found = Counter()
            for ref in group:
                book, cv = ref.rsplit(" ", 1)
                c, v = cv.split(":")
                for name, strong in words.get((book, c, v), []):
                    if strong.startswith(prefix) and any(likeness(name, e) >= 0.8 for e in match):
                        found[strong] += 1
            if found:
                strong, n = found.most_common(1)[0]
                lex = strongs.get(strong)
                name = re.sub(r"^[ʻʼ'`]+", "", lex.get("transliteration", "")) if lex else ""
                proper = name[:1].isupper()                 # (not "the", "nations", glossed with a name beside it)
                if lex and proper and n >= max(1, len(group) * 0.3):
                    entry[key] = {"text": lex["lexeme"], "translit": lex.get("transliteration", ""),
                                  "strong": strong}
        for key, text, group, kind in (("kjv", kjv_text, [] if slug in KJV_AS_THEOGRAPHIC else refs, "kjv"),
                                       ("greek", lxx, ot, "greek"),
                                       ("latin", vul, refs, "latin"), ("douay", dr, refs, "douay"),
                                       ("nrsv", nrsv, refs, "modern")):
            english_text = kind in ("douay", "modern", "kjv")
            if not english_text and not foreign_ok:
                continue
            found = spelling(text, group, match if english_text or not compound else heart, kind, rivals)
            if compound and english_text:
                # the whole name, as this Bible writes it: "Mount Hebal" if the verses say so, else nothing
                # (not "Guard" for the Prison Gate or "Beyond" for the River)
                near = " ".join(text.near(r) for r in group).lower()
                phrase = primary.replace(core(primary), found) if found and core(primary) else ""
                found = next((x[:1].upper() + x[1:] for x in (primary, phrase) if x and x.lower() in near), None)
            if found and english_text and plain(found) in common and plain(found) not in {plain(n) for n in english} \
                    and any(re.search(r"(?<![\w-])" + re.escape(found) + r"(?![\w-])", n, re.I) for n in english):
                found = None                        # ("Field" for Akeldama, the Field of Blood; not "Iron" for Yiron)
            if found:
                entry[key] = found
        if "greek" not in entry and "greek_nt" in entry:
            entry["greek"] = entry["greek_nt"]["text"]
            if entry["greek_nt"].get("translit"):
                entry["greek_translit"] = entry["greek_nt"]["translit"]
        entry.pop("greek_nt", None)
        if entry:
            out[slug] = entry
    kjv_apocrypha = Text(json.loads((ROOT / "data" / "kjv" / "kjv_apocrypha.json").read_text(encoding="utf-8"))["books"],
                         "modern")
    new = apocrypha_places(places)
    found = apocrypha(places, all_names, people, out,
                      {"nrsv": nrsv, "kjv": kjv_apocrypha, "douay": dr, "latin": vul, "greek": lxx}, new)
    print(f"the Apocrypha name {len(found)} places, in {sum(map(len, found.values()))} verses")
    # the Apocrypha-only places, each with the KJV's words of the verse that first names it
    missing = [p["name"] for s, p in new.items() if s not in found]
    if missing:
        raise SystemExit(f"named in no verse: {', '.join(missing)}")
    for slug, p in new.items():
        refs = found[slug]
        p["weight"] = len(refs)
        verse = kjv_apocrypha.near(refs[0], 0) if refs[0].rsplit(" ", 1)[0] in kjv_apocrypha.order else ""
        names = [re.sub(r"\s*\(.*\)$", "", p["name"]), *p["also"], out[slug].get("kjv", "")]
        # (only if the KJV's verse of that number names it: the KJV numbers some of Tobit and Judith differently)
        if verse and any(likeness(w, n) >= 0.7 for w in proper_names(verse) for n in names if n):
            p["about"] = f"Named only in the Apocrypha. {refs[0]} (KJV): “{verse.strip()}”"
        else:
            p["about"] = "Named only in the Apocrypha."
        if p["note"]:
            p["about"] += " " + p["note"]
        del p["books"], p["note"]
    APOCRYPHA_PLACES_OUT.write_text(json.dumps(new, ensure_ascii=False, indent=0), encoding="utf-8")
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=0), encoding="utf-8")
    counts = Counter(k for e in out.values() for k in e)
    print(f"{len(out)} of {len(places)} places; {dict(counts)}")


if __name__ == "__main__":
    main()
