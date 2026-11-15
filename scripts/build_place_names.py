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
            seq = [(c, v, unicodedata.normalize("NFC", chapters[c][v])) for c in sorted(chapters, key=int)
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
        seen.update(stems)
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


# (not Wisdom or Sirach: their places are figures of speech, Sirach 24's rivers and Lebanon)
APOCRYPHA = ["Tobit", "Judith", "Baruch", "1 Maccabees", "2 Maccabees", "1 Esdras",
             "2 Esdras", "Additions to Esther", "Song of the Three Children", "Susanna", "Bel and the Dragon",
             "Prayer of Manasseh"]


# a name in the Apocrypha that isn't the place of that name elsewhere: (place, book, or "" for all)
APOCRYPHA_NOT = {("Arab", ""): "Zabdiel the Arab, a man", ("Berea", ""): "a Berea in Judea, and Beroea (Aleppo)",
                 ("Shur", ""): "Judith's Sur is on the coast", ("Tishbe", ""): "Tobit's Thisbe is in Naphtali",
                 ("Emmaus", ""): "the Maccabees' Emmaus (Nicopolis) is not Luke's",
                 ("Bethany", ""): "Judith's Betane is not Bethany", ("Gabbatha", ""): "Gabatha, a eunuch",
                 ("Cuthah", "1 Esdras"): "sons of Coutha, temple servants",
                 ("Elam", "1 Esdras"): "sons of Elam, a family", ("Sur", ""): "Judith's Sur, not the gate of Sur",
                 ("Esau", ""): "the children of Esau, a people", ("Addar", ""): "Adar, the month"}
# people of the Apocrypha whose names are like a place's (Antiochus, Antioch), without the Greek's accents
APOCRYPHA_PEOPLE = {"Antiochus", "Αντιοχος", "Αντιοχου", "Αντιοχω", "Αντιοχον", "Ptolemæus", "Ptolemaeus",
                    "Ptolemee", "Ptolemy", "Πτολεμαιος", "Πτολεμαιου", "Tobias", "Τωβιας", "Σειραχ", "Sirach",
                    "Jesse", "John", "Joannis", "Ιωαννης"}


def plain(name: str) -> str:
    return re.sub(r"[^a-zæœ]", "", strip_marks(name).lower())


def apocrypha(places, all_names, people, out, texts):
    """The places the Apocrypha name: a verse of the NRSV's Deuterocanon (or the KJV's Apocrypha, for 1 and 2 Esdras
    and the rest the NRSV's Catholic edition hasn't) that names a place as the NRSV or KJV spells it elsewhere
    (letter for letter, bar case and hyphens), and how each Bible spells it there (the KJV's "Bethsura" and the
    Septuagint's "Βεθσουρά" for Beth-zur). A name that's also a person's is left to the person unless the place is
    named oftener; a word the English also writes in lower case ("There", "Eat") isn't a name."""
    nrsv, kjv = texts["nrsv"], texts["kjv"]
    lower = {w for text in (nrsv, kjv) for seq in text.order.values() for _, _, verse in seq
             for w in re.findall(r"\b[a-z]+\b", verse)}
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
        top = max(slugs, key=lambda x: len(places[x]["verses"]))
        if len(places[top]["verses"]) > person_weight[name]:
            best[name] = top
    found = defaultdict(list)
    for text in (nrsv, kjv):
        for book in APOCRYPHA:
            if text is nrsv and book not in text.order or text is kjv and book in nrsv.order:
                continue
            for c, v, verse in text.order.get(book, []):
                names = proper_names(verse)
                pairs = [w for w in names if " " in w or "-" in w]
                parts = {x for w in pairs if plain(w) in best for x in re.split(r"[ -]", w)}
                for w in names:
                    slug = best.get(plain(w))
                    ref = f"{book} {c}:{v}"
                    if not slug or w in parts or ref in found[slug]:
                        continue
                    name = re.sub(r"\s*\(.*\)$", "", places[slug]["name"])
                    if (name, "") in APOCRYPHA_NOT or (name, book) in APOCRYPHA_NOT:
                        continue
                    found[slug].append(ref)
    other_places = {plain(n): s for s, ns in all_names.items() for n in ns}
    for slug, refs in found.items():
        entry = out.setdefault(slug, {})
        entry["apocrypha"] = refs
        known = [n for n in [*all_names[slug], *(entry.get(k) for k in ("kjv", "latin", "douay", "nrsv"))] if n]
        greek = [entry["greek"]] if entry.get("greek") else []
        spellings = []
        for key, text in texts.items():
            names = greek + known if key == "greek" else known
            got = spelling(text, [r for r in refs if r.rsplit(" ", 1)[0] in text.order
                                  or text.names.get(r.rsplit(" ", 1)[0]) in text.order],
                           names, key if key in ("greek", "latin") else "modern")
            if not got or strip_marks(got) in APOCRYPHA_PEOPLE or other_places.get(plain(got), slug) != slug \
                    or strip_marks(got).lower().endswith(GENTILIC) or max(likeness(got, n) for n in names) < 0.7:
                continue
            if got not in entry.values() and got not in all_names[slug] and got not in spellings:
                spellings.append(got)
        if spellings:
            entry["apocrypha_spellings"] = spellings
    return found

def main():
    theo = json.loads((CACHE / "theographic" / "places.json").read_text(encoding="utf-8"))
    kjv_name = {r["fields"]["slug"]: r["fields"].get("kjvName", "") for r in theo}
    places = json.loads((ROOT / "data" / "people_places" / "people_places.json").read_text(encoding="utf-8"))["places"]
    strongs = json.loads((ROOT / "data" / "strongs" / "strongs_dictionary.json").read_text(encoding="utf-8"))
    words = macula_names(ROOT / "data" / "interlinear" / "macula.db")
    lxx = Text(json.loads((ROOT / "data" / "lxx_greek.json").read_text(encoding="utf-8"))["books"], "greek")
    vul = Text(bolls("VULG"), "latin")
    nrsv = Text(bolls("NRSVCE"), "modern")
    dr = Text(json.loads((ROOT / "data" / "drb.json").read_text(encoding="utf-8")), "douay", DR_NAMES)

    def names_of(slug, p):
        return [n for n in dict.fromkeys([re.sub(r"\s*\(.*\)$", "", p["name"]), *p.get("also", []),
                                          kjv_name.get(slug, "")]) if n]
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
        for key, text, group, kind in (("greek", lxx, ot, "greek"), ("latin", vul, refs, "latin"),
                                       ("douay", dr, refs, "douay"), ("nrsv", nrsv, refs, "modern")):
            english_text = kind in ("douay", "modern")
            if not english_text and not foreign_ok:
                continue
            found = spelling(text, group, match if english_text or not compound else heart, kind, rivals)
            if compound and english_text:
                # the whole name, as this Bible writes it: "Mount Hebal" if the verses say so, else nothing
                # (not "Guard" for the Prison Gate or "Beyond" for the River)
                near = " ".join(text.near(r) for r in group).lower()
                phrase = primary.replace(core(primary), found) if found and core(primary) else ""
                found = next((x[:1].upper() + x[1:] for x in (primary, phrase) if x and x.lower() in near), None)
            if found:
                entry[key] = found
        if "greek" not in entry and "greek_nt" in entry:
            entry["greek"] = entry["greek_nt"]["text"]
        entry.pop("greek_nt", None)
        if entry:
            out[slug] = entry
    kjv_apocrypha = Text(json.loads((ROOT / "data" / "kjv" / "kjv_apocrypha.json").read_text(encoding="utf-8"))["books"],
                         "modern")
    found = apocrypha(places, all_names, people, out,
                      {"nrsv": nrsv, "kjv": kjv_apocrypha, "douay": dr, "latin": vul, "greek": lxx})
    print(f"the Apocrypha name {len(found)} places, in {sum(map(len, found.values()))} verses")
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=0), encoding="utf-8")
    counts = Counter(k for e in out.values() for k in e)
    print(f"{len(out)} of {len(places)} places; {dict(counts)}")


if __name__ == "__main__":
    main()
