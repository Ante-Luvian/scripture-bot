"""The Old Norse of the Poetic Edda beside Bellows's English: data/norse/edda_norse.json, {poem: {stanza: text}},
keyed by the bot's poem names and Bellows's stanza numbers.

The Norse is Guðni Jónsson's normalised edition (Eddukvæði, Sæmundar-Edda, 1949) as heimskringla.no prints it, a page
per poem (cached in scripts/.cache/heimskringla). Bellows numbers the stanzas his own way in places (he moves stanzas
about in Völuspá, splits or joins some, and counts Svipdagsmol as one poem where Guðni has two), so stanzas are matched
by content, not by number: see align(). A stanza of Bellows's with no confident match gets no Norse. Where the aligner
went wrong, the pairing was read by hand and set in OVERRIDES. 1539 of Bellows's 1566 stanzas have their Norse; Brot af
Sigurðarkviðu has none (no page for it on heimskringla.no). The bot shows it under Bellows in !edda and !odin, and
runes.py carves it in Younger Futhark for the ᚱ Runes card.

    python scripts/build_edda_norse.py            # build
    python scripts/build_edda_norse.py --report   # show each poem's alignment
"""
import functools
import html
import json
import re
import sys
import time
import unicodedata
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "scripts" / ".cache" / "heimskringla"
OUT = ROOT / "data" / "norse" / "edda_norse.json"
UA = "Mozilla/5.0 (ScriptureBot corpus builder, personal Discord bot)"

# The bot's poem -> heimskringla.no page(s), in order (Svipdagsmol is Grógaldr then Fjölsvinnsmál), or a page's
# stanzas lo..hi (Bellows prints the Short Völuspá inside Hyndluljóð, after Guðni's 28).
PAGES = {
    "Voluspo": ["Völuspá"], "Hovamol": ["Hávamál"], "Vafthruthnismol": ["Vafþrúðnismál"],
    "Grimnismol": ["Grímnismál"], "Skirnismol": ["Skírnismál"], "Harbarthsljoth": ["Hárbarðsljóð"],
    "Hymiskvitha": ["Hymiskviða"], "Lokasenna": ["Lokasenna"], "Thrymskvitha": ["Þrymskviða"],
    "Alvissmol": ["Alvíssmál"], "Baldrs Draumar": ["Baldrs draumar"], "Rigsthula": ["Rígsþula"],
    "Hyndluljoth": [("Hyndluljóð", 1, 28), "Völuspá in skamma", ("Hyndluljóð", 29, 99)], "Svipdagsmol": ["Grógaldr", "Fjölsvinnsmál"],
    "Völundarkvitha": ["Völundarkviða"], "Helgakvitha Hjorvarthssonar": ["Helgakviða Hjörvarðssonar"],
    "Helgakvitha Hundingsbana I": ["Helgakviða Hundingsbana I"],
    "Helgakvitha Hundingsbana II": ["Völsungakviða in forna"], "Gripisspo": ["Grípisspá"],
    "Reginsmol": ["Reginsmál"], "Fafnismol": ["Fáfnismál"], "Sigrdrifumol": ["Sigrdrífumál"],
    # (the Brot: Guðni prints it as "Sigurðarkviða in meiri", the longer lay it is the end of, after stanzas of
    #  the Völsunga saga's that he puts before it)
    "Brot af Sigurtharkvithu": ["Sigurðarkviða in meiri"], "Guthrunarkvitha I": ["Guðrúnarkviða in fyrsta"],
    "Sigurtharkvitha en Skamma": ["Sigurðarkviða in skamma"], "Helreith Brynhildar": ["Helreið Brynhildar"],
    "Guthrunarkvitha II": ["Guðrúnarkviða in forna"], "Guthrunarkvitha III": ["Guðrúnarkviða in þriðja"],
    "Oddrunargratr": ["Oddrúnarkviða"], "Atlakvitha en Gronlenzka": ["Atlakviða"],
    "Atlamol en Gronlenzku": ["Atlamál in grænlenzku"], "Guthrunarhvot": ["Guðrúnarhvöt"],
    "Hamthesmol": ["Hamðismál"],
}


def fetch(title):
    CACHE.mkdir(parents=True, exist_ok=True)
    path = CACHE / (re.sub(r"\W", "_", title) + ".html")
    if not path.exists():
        url = "https://heimskringla.no/wiki/" + urllib.parse.quote(title.replace(" ", "_"))
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        path.write_bytes(urllib.request.urlopen(req, timeout=60).read())
        time.sleep(1)
    return path.read_text(encoding="utf-8")


def stanzas(page):
    """{number: [lines]} from a page: each line a <dd>, a stanza opened by a <dd> holding just its number."""
    body = page[page.find("bjó til prentunar"):]
    out, cur = {}, None
    for m in re.finditer(r"<dd>(.*?)</dd>|<p>(.*?)</p>", body, re.S):
        if m.group(2) is not None:                           # prose between stanzas ends the one before
            if re.sub(r"<[^>]+>|\s|&#160;", "", m.group(2)):
                cur = None
            continue
        text = html.unescape(re.sub(r"<[^>]+>", "", m.group(1))).replace("\xa0", " ").strip()
        text = re.sub(r"(?:\s*--)+(?=\s|$|[,;:.])", " …", text).replace(".::", ".").strip()     # (his lacunae)
        num = re.fullmatch(r"(\d+)\s*\.?", text) or re.match(r"(\d+)\.\s+(?=\S)", text)  # (or the number on the line)
        if num:
            cur = num.group(1)
            out.setdefault(cur, [])
            text = text[num.end():]
        if (text and cur is not None and re.search(r"\w", text)            # (not "---------", Guðni's gap marker,
              and not re.fullmatch(r"[IVX]+\.", text)):                # nor his section numbers in Hávamál)
            out[cur].append(text)
    return {k: [typeset(line) for line in v] for k, v in out.items() if v}


def typeset(line):
    """Guðni's typewriter marks as Bellows's printed ones: "…" as “…”, a spaced hyphen as an en dash."""
    line = re.sub(r'(^|[\s(\[])"', "\\1“", line)
    line = line.replace('"', "”")
    return re.sub(r"(^|\s)-(?=\s|$)", "\\1–", line)


def fold(word, whole=False):
    """A name as both editions can be brought to: Bellows anglicises (Othin, Heimdall, Valfather), Guðni doesn't
    (Óðinn, Heimdallar, Valföðr; Rati, Rata). Three letters of the folded stem tell a stanza's few names apart."""
    w = word.lower().replace("þ", "th").replace("ð", "th").replace("æ", "ae").replace("ǫ", "o").replace("ø", "o")
    w = "".join(c for c in unicodedata.normalize("NFKD", w) if c.isascii() and c.isalpha())
    return w if whole else w[:3]


NOT_NAMES = {"i", "o", "thou", "thee", "thy", "he", "she", "we", "ye", "they", "my", "me", "the", "a", "and", "now",
             "then", "there", "who", "what", "where", "when", "hail", "yet", "but", "so", "to"}


def names(lines, every=False):
    """The capitalised words, but not those starting a line (every line of Bellows's starts with one), unless
    every: then all but the stanza's first."""
    return _names(tuple(lines), every)


@functools.lru_cache(maxsize=None)
def _names(lines, every):
    out = set()
    for n, line in enumerate(lines):
        words = re.findall(r"[^\W\d_][\w’'-]*", line)
        for w in words[0 if (every and n) else 1:]:
            if w[0].isupper() and w.lower() not in NOT_NAMES:
                out.add(fold(w))
    return out - {""}


# Norse word-stems (folded as fold() folds, but whole) -> what Bellows writes for them: evidence for stanzas with no
# names (Hávamál's sayings). A stem matches a Norse word it begins; an English word matches if it begins with one.
COGNATES = {
    "ulf": "wolf wolves", "ask": "ash", "gull": "gold golden", "sol": "sun", "mani": "moon", "jorth": "earth",
    "mathr": "man men", "mann": "man men", "menn": "men", "hest": "horse steed", "hross": "horse steed",
    "fe": "cattle wealth", "deyr": "die dies", "dauth": "dead death", "daut": "dead death", "frand": "kinsm",
    "vin": "friend", "vinr": "friend", "kona": "woman wife", "konu": "woman wife", "mey": "maid", "mar": "maid",
    "sver": "sword", "hjor": "sword", "geir": "spear", "spjot": "spear", "skjold": "shield", "skild": "shield",
    "hond": "hand", "hend": "hand", "hug": "mind thought heart", "hjart": "heart", "hof": "head", "haus": "skull",
    "auga": "eye", "augu": "eyes", "eld": "fire", "vatn": "water", "sae": "sea", "sjo": "sea", "fjall": "mountain fell",
    "tre": "tree", "vith": "tree wood", "stein": "stone", "nott": "night", "naetr": "night", "dag": "day", "morg": "morn",
    "kveld": "evening", "aftn": "evening", "vetr": "winter", "sumar": "summer", "ol": "ale beer", "mjoth": "mead",
    "bjor": "beer", "drekk": "drink", "drukk": "drunk drink", "eta": "eat", "mat": "food meat", "brauth": "bread",
    "hleif": "loaf", "horn": "horn", "hus": "house", "hall": "hall", "sal": "hall", "gest": "guest", "gang": "go goes",
    "fara": "fare", "for": "fared", "kom": "came come", "kem": "come", "sat": "sat", "sit": "sit",
    "sa": "saw", "sja": "see", "veit": "know", "vit": "wit wise know", "froth": "wise", "snot": "wise", "osnot": "fool",
    "osvith": "witless", "heim": "home", "mal": "speech word", "orth": "word", "ljoth": "song", "galdr": "charm song",
    "run": "rune", "eith": "oath", "baug": "ring", "hring": "ring", "barn": "child bairn", "son": "son",
    "sonr": "son", "systir": "sister", "brothur": "brother", "brothir": "brother", "brothr": "brother",
    "fathir": "father", "fathr": "father", "foth": "father", "mothir": "mother", "moth": "mother", "dottir": "daughter",
    "dott": "daughter", "kunung": "king", "konung": "king", "jarl": "earl", "thrall": "thrall", "thral": "thrall",
    "hund": "hound dog", "orn": "eagle", "ari": "eagle", "hrafn": "raven", "orm": "serpent worm", "naeth": "serpent",
    "fisk": "fish", "fugl": "bird fowl", "svan": "swan", "gras": "grass", "lauk": "leek", "akr": "field acre",
    "voll": "field plain", "grund": "ground", "mold": "mold earth", "himin": "heaven sky", "vind": "wind",
    "regn": "rain", "snae": "snow", "is": "ice", "kalt": "cold", "kald": "cold", "lif": "live life",
    "liv": "life", "bloth": "blood", "blot": "sacrific", "nafn": "name", "nofn": "names", "heit": "name call hot",
    "niu": "nine", "atta": "eight", "tolf": "twelve", "thri": "three", "fjor": "four", "fimm": "five", "sex": "six",
    "sjau": "seven", "tiu": "ten", "ellif": "eleven", "tveir": "two", "ein": "one alone", "fyrst": "first",
    "annat": "second", "thrith": "third", "fjorth": "fourth", "fimmt": "fifth", "sett": "sixth", "sjaund": "seventh",
    "att": "eighth", "niund": "ninth", "tiund": "tenth", "ellift": "eleventh", "tolft": "twelfth",
    "threttand": "thirteenth", "fjogurtand": "fourteenth", "fimmtand": "fifteenth", "sextand": "sixteenth",
    "sjautjand": "seventeenth", "atjand": "eighteenth", "kann": "know", "bok": "book", "vaf": "weave wove",
    "bor": "bore borne", "ung": "young", "gamal": "old", "alda": "old ages", "forn": "old ancient", "riki": "might",
    "regin": "gods powers", "ase": "god", "aes": "gods", "jotun": "giant", "thurs": "giant",
    "dverg": "dwarf", "alf": "elf elves", "val": "slain", "her": "host army", "folk": "folk host", "vig": "fight war",
    "berj": "fight", "bana": "slayer bane death", "sar": "wound", "sorg": "sorrow", "grat": "weep", "glath": "glad",
    "gaman": "joy delight", "ast": "love", "unn": "love", "kos": "kiss", "beth": "bed", "sof": "sleep", "draum": "dream",
    "skip": "ship", "kjol": "keel ship", "ar": "oar", "bru": "bridge", "dyr": "door", "gatt": "gate door",
    "grind": "gate", "vegr": "way road", "veg": "way road", "dal": "dale", "skog": "wood forest", "lund": "grove",
    "brunn": "well spring", "vel": "well", "illr": "evil ill", "ill": "evil ill", "goth": "god good", "got": "good",
    "betr": "better", "bazt": "best", "verr": "worse", "mest": "most", "mikil": "great mighty much", "litil": "little",
    "lang": "long", "skamm": "short", "haltr": "lame", "blind": "blind", "dauf": "deaf", "hold": "flesh",
    "bein": "bone", "har": "hair", "skegg": "beard", "klaeth": "cloth garment", "vath": "garment",
}


@functools.lru_cache(maxsize=None)
def _stems(norse_lines):
    stems = set()
    for w in re.findall(r"[^\W\d_]+", " ".join(norse_lines)):
        f = fold(w, whole=True)
        stems |= {s for s in COGNATES if len(s) >= 3 and f.startswith(s) or f == s}
    return frozenset(stems)


@functools.lru_cache(maxsize=None)
def cognates(english, norse_lines):
    """How many of the Norse stanza's cognate stems show up in the English."""
    eng = set(re.findall(r"[a-z]+", english.lower()))
    return sum(1 for s in _stems(tuple(norse_lines)) if any(e.startswith(t) for t in COGNATES[s].split() for e in eng))


def halves(english):
    """Half-lines in a Bellows stanza: each line, plus one for each caesura bar. A Norse <dd> is a half-line."""
    return sum(1 + line.count("|") + line.count("·") for line in english.split("\n") if line.strip())


def score(eng_text, eng_pos, norse_lines, norse_pos):
    """How alike a Bellows stanza and a Guðni stanza are: shared names, the same number of half-lines, and
    being at much the same place in the poem (positions in each list, as the numbering differs)."""
    en, nn = names(eng_text.split("\n")), names(norse_lines)
    shared = len(names(eng_text.split("\n"), True) & names(norse_lines, True))
    s = 3.0 * shared - 1.0 * len(en ^ nn) * (0.3 if shared else 0.15)
    s += 1.0 * cognates(eng_text, tuple(norse_lines))
    s -= 0.6 * abs(halves(eng_text) - len(norse_lines))
    s -= 0.25 * abs(norse_pos - eng_pos)
    return s


KEEP = -1.0          # a pairing scoring below this is left out (that stanza gets no Norse)
PAIR = 2.0           # what pairing two stanzas is worth over leaving both unpaired (a split or merge counts once)


def align(english, norse):
    """Align Bellows's stanzas to Guðni's (Needleman-Wunsch), with three moves beyond one-to-one, for what Bellows
    does: two neighbours swapped ("swap"), one of Guðni's stanzas printed as two ("split"), two as one ("merge").
    english, norse: [(number, text)] / [(number, lines)] in order.
    Returns {bellows number: (norse lines, the Guðni numbers they come from)}, only for pairings scoring >= KEEP."""
    E, N = len(english), len(norse)
    GAP = -1.5
    NEG = float("-inf")
    best = [[NEG] * (N + 1) for _ in range(E + 1)]
    move = [[None] * (N + 1) for _ in range(E + 1)]
    best[0][0] = 0.0
    et = [e[1] for e in english]
    nl = [n[1] for n in norse]

    @functools.lru_cache(maxsize=None)
    def pair(i, j):                         # english i-1 with norse j-1
        return score(et[i - 1], i, nl[j - 1], j)

    for i in range(E + 1):
        for j in range(N + 1):
            if i == j == 0:
                continue
            options = []
            if i:
                options.append((best[i - 1][j] + GAP, "e"))
            if j:
                options.append((best[i][j - 1] + GAP, "n"))
            if i and j:
                options.append((best[i - 1][j - 1] + PAIR + pair(i, j), "d"))
            if i >= 2 and j >= 2:
                s = pair(i - 1, j) + pair(i, j - 1)
                if s > pair(i - 1, j - 1) + pair(i, j) + 2:          # (only when clearly better than in order)
                    options.append((best[i - 2][j - 2] + 2 * PAIR + s - 0.5, "swap"))
            if i >= 2 and j:
                both = et[i - 2] + "\n" + et[i - 1]
                options.append((best[i - 2][j - 1] + PAIR + score(both, i - 0.5, nl[j - 1], j) + 1.0, "split"))
            if i and j >= 2:
                both = nl[j - 2] + nl[j - 1]
                options.append((best[i - 1][j - 2] + PAIR + score(et[i - 1], i, both, j - 0.5) + 1.0, "merge"))
            best[i][j], move[i][j] = max(options, key=lambda o: o[0])
    out, i, j = {}, E, N
    while i or j:
        m = move[i][j]
        if m == "d":
            if pair(i, j) >= KEEP:
                out[english[i - 1][0]] = (nl[j - 1], [norse[j - 1][0]])
            i, j = i - 1, j - 1
        elif m == "swap":
            out[english[i - 2][0]] = (nl[j - 1], [norse[j - 1][0]])
            out[english[i - 1][0]] = (nl[j - 2], [norse[j - 2][0]])
            i, j = i - 2, j - 2
        elif m == "split":                  # Guðni's stanza cut where Bellows's first one ends, by half-lines
            cut = halves(et[i - 2])
            if 0 < cut < len(nl[j - 1]) and score(et[i - 2] + "\n" + et[i - 1], i, nl[j - 1], j) >= KEEP:
                out[english[i - 2][0]] = (nl[j - 1][:cut], [norse[j - 1][0]])
                out[english[i - 1][0]] = (nl[j - 1][cut:], [norse[j - 1][0]])
            i, j = i - 2, j - 1
        elif m == "merge":
            if score(et[i - 1], i, nl[j - 2] + nl[j - 1], j) >= KEEP:
                out[english[i - 1][0]] = (nl[j - 2] + nl[j - 1], [norse[j - 2][0], norse[j - 1][0]])
            i, j = i - 1, j - 2
        elif m == "e":
            i -= 1
        else:
            j -= 1
    return out


# Pairings read by hand (2026-11-08), where the aligner went wrong: Bellows's stanza -> Guðni's, as "N" (his stanza N),
# "N:a-b" (its lines a to b, from 0, as Bellows divides a stanza of Guðni's at another place), joined by "+"; "-" for
# none. A letter before the number names the poem's other page (see PAGE_LETTERS). Every other stanza is as align()
# pairs it: python scripts/build_edda_norse.py --report lists them all, and those out of sequence were each read
# against the Norse; these are what that turned up. Bellows moves stanzas about (by his notes, following the editors
# of his day), and Guðni divides some stanzas at other places.
OVERRIDES = {
    "Voluspo": "34=33",                          # (Guðni 34, the binding of Vali's son, is Hauksbók's: Bellows hasn't it)
    "Hovamol": "76=78 77=76 78=77 79=80 80=79 138=164",
    "Skirnismol": "15=15 30=30 35=35:0-3 36=35:3-10",
    "Harbarthsljoth": "50=50 51=51 52=52",
    "Rigsthula": "26=26+27:0-2 27=27:2-6+28:0-4 28=28:4-8+29 47=46+47:0-4 48=47:4-8 49=48",
    "Hyndluljoth": "22=22+25:0-4 23=23 24=24 25=25:4-10 28=v4:0-4 29=28 30=v1 31=v2:0-2 32=v2:2-10 33=v3 34=v4:4-6 "
                   "35=v5 36=v6 37=v7 38=v8 39=v9 40=v14 41=v10 42=v11 43=v12 44=v13 45=v15 46=29",
    "Svipdagsmol": "17=f1:0-3 18=f2 19=f3:0-3",
    "Völundarkvitha": "2=15 11=8:0-4 12=8:4-8+9 14=11 15=12 16=14 17=16 18=17 28=27 29=28:0-4 30=29:0-4 31=29:4-10",
    "Helgakvitha Hundingsbana I": "19=18 20=19 21=20 22=21",
    "Helgakvitha Hundingsbana II": "15=16 16=18 17=25 18=26 19=27 20=28 21=29 22=19 23=20 24=21 25=22 26=23 27=24 28=30 "
                                   "29=31 30=32 31=33:0-4 32=33:4-12 33=34",
    "Fafnismol": "26=28 27=29 28=30 29=31 30=26 31=27",
    "Sigrdrifumol": "3=4 4=2",
    "Sigurtharkvitha en Skamma": "8=8:0-8 9=8:8-10+9 43=43+44:0-4 44=44:4-12 46=46",
    "Guthrunarkvitha II": "14=13+14:0-4 15=14:4-8+15 17=17:0-4 18=17:4-12 35=- 36=35 37=36 38=37",
    "Guthrunarkvitha III": "7=6+7",
    "Oddrunargratr": "19=20+21:0-4 20=21:4-8+22:0-4 21=22:4-8+23:0-4 22=23:4-8+24 23=25 24=26 25=27",
    "Atlakvitha en Gronlenzka": "27=26:0-4 28=26:4-8+27:0-4 29=27:4-12 30=28 31=29 32=30:0-8 33=30:8-12",
    "Atlamol en Gronlenzku": "17=18 18=19 29=32 35=38+39:0-2 36=39:2-10 51=55+56:0-4 52=56:4-10 87=92+93:0-6 88=93:6-8+94 95=101",
    "Hamthesmol": "11=22 12=11 13=12 14=13:0-4 15=13:4-8",
}
PAGE_LETTERS = {"v": "Völuspá in skamma", "f": "Fjölsvinnsmál"}


def overridden(poem, pages):
    """{bellows: lines or None} for the poem's OVERRIDES; pages: {title: {number: lines}}, the first its main page."""
    out = {}
    main = next(iter(pages))
    for item in OVERRIDES.get(poem, "").split():
        b, spec = item.split("=")
        if spec == "-":
            out[b] = None
            continue
        lines = []
        for part in spec.split("+"):
            m = re.fullmatch(r"([a-z]?)(\d+)(?::(\d+)-(\d+))?", part)
            st = pages[PAGE_LETTERS[m.group(1)] if m.group(1) else main][m.group(2)]
            lines += st[int(m.group(3)):int(m.group(4))] if m.group(3) else st
        out[b] = lines
    return out


def finnur(page):
    """{number: [lines]} from a page in Finnur Jónsson's Carmina Scaldica layout: a <blockquote> of <br />-parted
    lines, a stanza opened by a line "N."."""
    body = page[page.find("<blockquote>"):page.find("</blockquote>")]
    out, cur = {}, None
    for line in re.split(r"<br\s*/?>", body):
        text = html.unescape(re.sub(r"<[^>]+>", "", line)).replace("\xa0", " ").strip()
        if m := re.fullmatch(r"(\d+)\.", text):
            cur = m.group(1)
            out[cur] = []
        elif text and cur:
            out[cur].append(text)
    return out


def outside_quotes(lines):
    """The lines outside "…": in Finnur's Eiríksmál, Odin's own, the other speakers' words (Bragi's, Sigmund's)
    being quoted."""
    keep, inside = [], False
    for line in lines:
        opens, closes = line.startswith('"'), line.rstrip(".,;:?!").endswith('"') or line.endswith('".')
        if not inside and not opens:
            keep.append(line)
        if opens and not closes:
            inside = True
        elif closes:
            inside = False
    return keep


# Hollander's poems in !odin (data/norse/old_norse_poems.json), with the Norse of Odin's speech in each stanza:
# Eiríksmál in Finnur Jónsson's text (Carmina Scaldica, 1929: Guðni's Eddukvæði hasn't it), Odin's lines being those
# outside quotation marks; the Riddles of King Heithrek in Guðni's, a riddle each (his stanza runs on into the
# start of the king's answer, "Góð er gáta þín…", cut off). Eiríksmál's stanzas match Hollander's one to one; the
# riddles to 22 too, but Hollander's 23 (the widows banding together) isn't in Guðni's text, so from there his n is
# Guðni's n-1, to the last, the question of what Odin said in Baldr's ear (Guðni 36); Guðni's 37 is the king's reply.
def riddles(page):
    out = {}
    for n, v in stanzas(page).items():
        k = int(n)
        if k <= 36:
            out[str(k if k <= 22 else k + 1)] = \
                v[:next((i for i, l in enumerate(v) if l.lstrip('"“').startswith("Góð er gáta")), len(v))]
    return out


HOLLANDER = {
    "Eiriksmol": ("Eiríksmál", lambda page: {n: outside_quotes(v) for n, v in finnur(page).items()}),
    "Heithreksgatur": ("Heiðreksgátur", riddles),
}


def build(report=False):
    books = json.loads((ROOT / "data" / "norse" / "poetic_edda.json").read_text(encoding="utf-8"))["books"]
    out = {}
    for poem, titles in PAGES.items():
        norse, pages, whole = [], [], {}
        for t in titles:
            t, lo, hi = (t, 1, 9999) if isinstance(t, str) else t
            try:
                page = stanzas(fetch(t))
            except urllib.error.HTTPError:
                print(f"  no page for {t}", file=sys.stderr)
                continue
            # (two pages make one poem: Guðni's numbers carry on so they stay distinct)
            norse += [(str(int(n) + 1000 * len(pages)), lines) for n, lines in page.items() if lo <= int(n) <= hi]
            pages.append(t)
            whole[t] = page
        if not norse:
            continue
        english = [(n, ch["1"]) for n, ch in books[poem].items()]
        pairs = align(english, norse)
        for b, lines in overridden(poem, whole).items():
            if lines is None:
                pairs.pop(b, None)
            else:
                pairs[b] = (lines, ["=hand"])
        pairs = dict(sorted(pairs.items(), key=lambda kv: int(kv[0])))
        out[poem] = {b: "\n".join(lines) for b, (lines, _) in pairs.items()}
        print(f"{poem}: {len(pairs)}/{len(english)} matched (Norse {len(norse)})")
        if report:
            eng = dict(english)
            for b in eng:
                e = eng[b].splitlines()
                lines, src = pairs.get(b, (["-"], ["-"]))
                print(f"  {b:>3} {e[0][:44]:<45} {'+'.join(str(int(s) % 1000) if s[0].isdigit() else s for s in src):>6}"
                      f" {lines[0][:28]:<29} ~ {e[-1][-26:]:<27} | {lines[-1][-26:]}")
    hollander = json.loads((ROOT / "data" / "norse" / "old_norse_poems.json").read_text(encoding="utf-8"))["books"]
    for poem, (title, parse) in HOLLANDER.items():
        norse = parse(fetch(title))
        out[poem] = {n: "\n".join(typeset(l) for l in lines) for n, lines in norse.items()
                     if n in hollander[poem] and lines}
        print(f"{poem}: {len(out[poem])}/{len(hollander[poem])} (Norse {len(norse)})")
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return out


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    build(report="--report" in sys.argv)
