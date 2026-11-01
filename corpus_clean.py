"""
Scrubbing the corpora of what came along with the texts: web-page furniture
(scripts, style sheets, site menus, ads), licence boilerplate, translators'
footnotes, page markers, back-of-book indexes, and Greek left in Beta Code.

    python scripts/clean_corpora.py        # rewrites the files under data/ in place

clean_corpus(payload, rel) does one corpus file (rel is its path under data/,
e.g. "jewish/philo.json"); it's idempotent, so it's safe to run again after a
rebuild. tests/test_corpus_clean.py checks every loaded file stays clean.
"""
import html
import re
import unicodedata

# ── where page furniture starts: the rest of the verse goes ──────────────────
TAILS = [
    r"(?:[1-4] )?[A-Z][^\s.<]*(?: [A-Z(][^\s.<]*){0,2} < \d+ > You may copy the King James",                       # the KJV Apocrypha's site footer
    r"Chapter: 1 \| 2 \| 3 \|",                                                # Jubilees' chapter menu, credits
    r"Go to the Chronological List of all Early Christian Writings",
    r"Please buy the CD to support the site",
    r"Early Christian Writings is copyright",
    r"(?:#\w+\s*\{?\s*)?font-size: ?\d+px",                                    # earlyjewishwritings.com's ad box
    r"Top \| Index \| Next",                                                    # hermetic.com's menu
    r"\(function\(\)",
    r"!function\(",
    r"RECENT ARTICLES",
    r"(?:THE END )?-{10,} Copyright statement",                                 # the Internet Classics Archive
    r"(?:THE END )?Browse and Comment Search Buy Books",
    r"(?:C[a-z ]{9,16}\. )?The editor of New Advent is Kevin Knight",          # newadvent.org's footer
    r"CONTACT US \| ADVERTISE WITH NEW ADVENT",
    r"Go to the [\w ' ]+ page\. Go to the Early Jewish Writings",
    r"Buy this Book at Amazon\.com",
    r"This (?:text|material) was (?:transcribed|uploaded) by",                 # tertullian.org's credits
    r"Material in square brackets \[\] appears to be glosses",
]
TAIL = re.compile(r"\s*(?:" + "|".join(TAILS) + r").*", re.S)
CSS = re.compile(r"\s*\.mw-parser-output[^{}]*\{[^{}]*\}")                     # Wikisource's inline styles
# the transcribers' notes on tertullian.org ("[Note to the online text: ...]")
EDITOR_NOTE = re.compile(r"\s*\[Notes? (?:to|on) the online (?:text|edition)[^\]]*\]"
                         r"|\s*\(Note contributed to the online text[^)]*\)\.?"
                         r"|\s*\[[^\[\]]{0,160} in online text\.?\]\.?"
                         r"|^(?:\[?\d+\.\s*|\*\*\s*)Note to the online edition.*")

# ── footnotes kept as verses at a chapter's end ("12. a See Euseb. ...") ────
FOOTNOTE = re.compile(r"^\s*\d+\.\s+(?:\d+|[a-z]|\*)\s+\S")
FOOTNOTE_FILES = re.compile(r"^(patristics/.*|classical/julian\.json)$")

# ── Greek in Beta Code (Perseus: <foreign lang="greek">Ke/ras )Amalqei/as) ──
_BETA_TOKEN = re.compile(r"(?<![\w*/\\=)(|+])(\*?[)(]?[/\\=]?[A-Za-z][A-Za-z/\\=)(|+']*)")
_BETA_MARK = re.compile(r"[aehiouwAEHIOUW][)(]?[/\\=|]")              # an accent or iota subscript on a vowel
NOT_GREEK = {"Africa/un", "Hesione/"}                                 # English that only looks like it
BETA_FILES = re.compile(r"^(classical/perseus/.*|patristics/gregory_nazianzen\.json)$")

# one-off repairs, by file: (pattern, replacement)
FIXES = {
    # Latimer: the editor's footnote run onto the word it explains, to the verse's end ("the Rhodes are wonAlluding
    # to the capture of the Island of Rhodes...", "this wesantWind-pipe.")
    # (but "his evenFellow-Christian": the note is "Fellow-", on "even"; "his even Christian" is Latimer's)
    "reformation/latimer.json": [(r"\bevenFellow-Christian\b", "even Christian"),
                                 (r"\b(won|sentine|scalary|tricennals|wesant|appose)"
                                  r"(?:Alluding|Sentine|Masses-|Tricennals|Wind-|Question).*\Z", r"\1.")],
    # Photius: Freese's notes, a verse of them after the passage ("1 For the life and works of Photius see...
    # 2 The genuineness..."), and their numbers in the text ("ambassador to Assyria 3 had been confirmed")
    "patristics/photius.json": [(r"\A\d{1,2} [A-Z(\[].*\Z", ""), (r"(?<=[A-Za-z,;:)\]]) \d{1,2}(?= [a-z(])", "")],
    # LacusCurtius's pop-up note on "digitus" leaked into Varro's text (scripts/build_latin.py)
    "classical/latin.json": [(r"digitus\) gave its name to a unit[^•]*?nd\(\);\">•", "")],
    "classical/perseus/tlg0099.json": [(r"\$", "æ")],                       # Strabo: "Vard$sei" = Vardæi
    "classical/perseus/tlg0008.json": [(r"\$", "æ")],                       # Athenaeus: "Pagas$ean"
    "classical/perseus/tlg0062.json": [(r"(\w)\$", r"\1s"), (r" ~ ", " ")],  # Lucian: "scourge$"
    "classical/perseus/tlg0085.json": [(r"Footprints>matching", "Footprints matching")],
    "classical/perseus/phi1002.json": [(r"admit i>figure", "admit a figure")],
    "dharmic/sama_veda.json": [(r"\$atakratu", "Śatakratu")],
    "dharmic/rig_veda.json": [(r"limit~tion", "limitation")],
    "sikh/guru_granth_sahib.json": [(r"\s*~\s*$", ""), (r" ~ ", " — ")],   # the source's section mark
    "qumran/1qha.json": [(r"<NEG>", "[not]")],
    "qumran/1qisaa.json": [(r"(?<=[a-z])\.(?=[a-z])", " ")],              # one Hebrew word, glossed "is.about.to"
    "jewish/philo.json": [(r"\s*\{[^{}]*\}", ""), (r"\(#(\w)", r"(\1")],   # Yonge's notes in braces; "(#Ge 2:4)"
    "patristics/epiphanius.json": [(r"\s*\{\d+[a-z]?\}", "")],              # page numbers
    "patristics/eusebius_of_caesarea.json": [(r"\s*\{\d+[a-z]?\}", "")],
    "celtic/mabinogion.json": [(r"\s*\{\d+\}", "")],
    "mesoamerican/popol_vuh.json": [(r"\s*\{p\. ?\w+\}", "")],
    "shinto/kojiki.json": [(r"<page (\w+)>", r"page \1")],                  # "(see <page lx>)"
    "buddhist/jataka.json": [(r"\s*<page \w+>(?:\s*-\s*<page \w+>)?", "")],
    "buddhist/lotus_sutra.json": [(r"^(\d+\.) 1 ", r"\1 I ")],               # OCR: "1 see" for "I see"
    "charles/book_of_jubilees.json": [(r"~([^~]+)~", r"\1")],
    "apostolic_fathers/epistle_of_barnabas.json": [(r"\s*~y\b", ""), (r"\s+Barnabas\Z", "")],
    "apostolic_fathers/ignatius_romans.json": [(r"\+([^+]+)\+", r"*\1*"), (r"\s*\bCHAPTER \d+\Z", "")],
    # the source's verse references ("1Clem 25:1") lost their numbers, leaving the
    # abbreviation on the end of the verse before: "...the parts about Arabia. 1Clem"
    "apostolic_fathers/1_clement.json": [(r"\s+1Clem\Z", "")],
    "apostolic_fathers/2_clement.json": [(r"\s+2Clem\Z", "")],
    "apostolic_fathers/polycarp_philippians.json": [(r"\s+Polycarp\Z", "")],
    # the next chapter's heading, run onto the end of a chapter ("...abundant greeting. CHAPTER 1")
    **{f"apostolic_fathers/ignatius_{n}.json": [(r"\s*\bCHAPTER \d+\Z", "")]
       for n in ("ephesians", "magnesians", "philadelphians", "polycarp", "smyrnaeans", "trallians")},
    "classical/vivec_sermons.json": [(r"\s*<div\Z", "")],                    # a cut-off HTML tag
    "classical/porphyry.json": [(r"\s*\|\d+(?=\s|$)", "")],                # the printed edition's page numbers: "|41"
    # the printed pages ("p. 20") and footnote marks ("self-sufficiency, 1 like") of sacred-texts' copies
    "classical/golden_verses.json": [(r"\s*\bp\. \d+\b", "")],
    "classical/pythagorean_sentences.json": [(r"\s*\bp\. \d+\b", ""), (r"(?<=self-sufficiency,) 1(?= like)", ""),
                                             (r"(?<=itself,) 1(?= so)", "")],
    "classical/corpus_hermeticum.json": [(r"\s*\bp\. \d+\b", ""), (r"(?<=mystic-ly,) 1(?= as)", ""),
                                         (r"(?<=If,) 1(?= then)", ""), (r"(?<=made) 1(?= that)", "")],
    "classical/isis_and_osiris.json": [(r"(?<=[a-z][.,;:!?’”)])\d{1,3}(?=\s|$)", ""),      # "time.5": the note numbers
                                       (r"(?<=[a-z])\d{1,3}(?=\s)", "")],                 # "Pythagoras118 and"
    "classical/plotinus.json": [(r"\nAll matter shown in brackets is added by the translator[^\n]*S\.M\.", "")],
    # Dionysius (the same text in both collections): note numbers on the words ("being5 simplified")
    **{f"{c}/{f}.json": [(r"(?<=[a-z])\d{1,3}(?=[\s,.;:)]|$)", "")]
       for c in ("classical", "apostolic_fathers") for f in ("divine_names", "mystical_theology")},
    "classical/meditations_long.json": [(r"\+([^+]+)\+", r"*\1*")],
    "patristics/philoxenus_of_hierapolis.json": [(r"^[\w$)(]{1,6}(?: [\w$)(]{1,6}){3,}$", "")],   # Syriac in ASCII
    "ancient_near_east/instruction_of_amenemope.json": [                  # the Egyptian, transliterated: not a translation
        (r"^\*\*(?:Egyptian \(Egyptological Transliteration\)|Variant Witnesses)\*\*.*", ""),
        (r"^\*\*Variant:.*?(?:\n---\n+|\Z)", "")],
}

# where a book's real text stops (everything after goes): file -> [(book, chapter, verse, cut-at pattern)]
ENDS = {
    # Thomas Taylor's translations end with his notes, which were run on as though they were the text: Iamblichus
    # closes with his prayer for "an immutable guard of true conceptions" (104:6), Porphyry's Cave of the Nymphs
    # with "the present Cave of the Nymphs", before "(1) This Cronius..." (His Theology of Plato is rebuilt whole,
    # without the notes, by scripts/build_platonists.py.)
    "classical/iamblichus.json": [("On the Mysteries", "104", "6", r"$^")],
    "classical/porphyry.json": [("On the Cave of the Nymphs", "18_1", "1", r"\s*\(1\) This Cronius.*")],
    "classical/julian.json": [("Hymn to King Helios", "30", "7", r"$^")],                   # chapters 31-56 are the translator's notes
    # Parker's Divine Names ends "October, 1896.": then his note on Ignatius
    **{f"{c}/divine_names.json": [("Divine Names", "13", "4", r"\s*Note ### NOTE\..*")]
       for c in ("classical", "apostolic_fathers")},
    "jain/jaina_sutras.json": [("Sutrakritanga", "2.7", "40", r"\s*INDEX OF NAMES AND SUBJECTS.*")],
}
INDEX_HEAD = re.compile(r"^(?:INDEX(?: OF [A-Z ]+)?\.?|\*\*\* This Index contains.*)$")
INDEX_FILES = {"buddhist/jataka.json"}                                    # a volume's index at the end of its last chapter


def beta_to_greek(token: str) -> str:
    import beta_code                                     # (pip install beta-code; only the data scripts need it)
    m = re.match(r"^([)(]*[/\\=]?)([A-Z])(.*)$", token)
    if m:                                                # a capital: Beta Code marks it with *
        token = "*" + m.group(1) + m.group(2) + m.group(3)
    return beta_code.beta_code_to_greek(token.lower())


def greek_from_beta(text: str) -> str:
    def swap(m):
        tok = m.group(1)
        core = tok.rstrip("'")
        core = re.sub(r"(?<=[a-z])[)(]$", "", core)       # a closing bracket, not a breathing (none ends a word)
        if not _BETA_MARK.search(core) or core in NOT_GREEK:
            return tok
        return beta_to_greek(core) + tok[len(core):]
    return _BETA_TOKEN.sub(swap, text)


# tertullian.org's own Beta Code, from an old Greek font: e0n, ou]n, th_n, tw~n, dh&pouqen, w#sper, O1ntoj
_TERT = {"0": ")", "1": ")/", "2": ")\\", "3": "(/", "4": "(\\", "#": "(/", "]": ")=", "[": "(=",
         "&": "/", "~": "=", "_": "\\"}
_TERT_TOKEN = re.compile(r"(?<![\w*/\\=)(|+&~#\]\[])([0-4]?[A-Za-z][A-Za-z0-4#\]\[&~_|/\\=)(+]*)")
# a mark sits on a vowel; brackets, digits, # and _ only inside a word -- at its edges they're
# brackets and italics ("[Note to the online text", "_like this_"), and English must stay English
_TERT_MARK = re.compile(r"[aehiouwAEHIOUW][)(|]?(?:[0-4#\]\[_](?=[A-Za-z|])|[&~])|^[0-4](?=[aehiouwAEHIOUW])")
TERT_FILES = re.compile(r"^(patristics/.*|classical/julian\.json)$")


def greek_from_tertullian(text: str) -> str:
    def swap(m):
        tok = m.group(1)
        if re.fullmatch(r"[A-Za-z]+\[[A-Za-z]+\]", tok):           # English, a word completed in brackets:
            return tok                                             # "mouth[s]", "no[thing]", not Beta Code
        core = re.sub(r"(?<=[A-Za-z])[)(\]\[]+$", "", tok)          # a closing bracket, not a breathing
        if not _TERT_MARK.search(core) and not _BETA_MARK.search(core):
            return tok
        if re.search(r"[A-Z].*[A-Z]|[a-z][A-Z]", core):          # not a Greek word: "A.D", "MS"
            return tok
        beta = "".join(_TERT.get(c, c) for c in core)
        beta = re.sub(r"\|([/\\=)(+]+)", r"\1|", beta)               # the iota subscript goes last
        beta = re.sub(r"^([)(][/\\=]?)([A-Za-z])", lambda m: ("*" + m.group(1) + m.group(2)) if m.group(2).isupper()
                      else m.group(2) + m.group(1), beta)
        return beta_to_greek(beta) + tok[len(core):]
    return _TERT_TOKEN.sub(swap, text)


# Two words run together where a line break was lost ("theWorlds", "ofPetavium", "draughtThose"): split where one
# side is one of the commonest English words, so a transliteration ("arRahman", "rahmatAllahi") or Old English
# ("petRes") is left as it is. Not in the files that spell another script in capitals and small letters.
_COMMON = ("the of and to in that as from for be by with is was his her their all which this they them he she it "
           "we you your our my thy thee thou unto upon not but or so are were had have has who whom when where what "
           "then than there these those said also only into among one two three let shall will would may might can "
           "could do did no nor now how why its an at on if").split()
_JOINED_LEFT = re.compile(r"(?<![\w'’\-])(" + "|".join(_COMMON) + r")([A-Z][a-z]{2,})\b")
_JOINED_RIGHT = re.compile(r"(?<![\w'’\-])([a-z]{3,})(" + "|".join(w.capitalize() for w in _COMMON) + r")\b")
JOINED_EXEMPT = re.compile(r"^(ancient_near_east/leiden_hymns\.json|english/.*|arthurian/middle_english\.json|"
                           r"oe\.json|.*/New folder/.*)$")
_VOCAB = {"words": frozenset()}         # (the words of the file being cleaned: clean_corpus sets it)


# OCR's misreadings, each read in its passage before it went in (2026-11-01): a capital inside a word ("wTere",
# "aIl"), two words run together where neither is a common one ("groundCollapsing"), a footnote's reference stuck to
# a word ("lionsIbid."). Whole words only, in every file but those JOINED_EXEMPT.
OCR_WORDS = {
    # T, R, Q, C... read inside a word
    "wTays": "ways", "wTith": "with", "wTere": "were", "twTo": "two", "owTn": "own", "wThich": "which",
    "answTer": "answer", "wTe": "we", "wTas": "was", "wThen": "when", "wRien": "when", "suppQse": "suppose",
    "gLiard": "guard", "horFe": "horse", "prAection": "protection", "bountiUly": "bountifully",
    "measurcIess": "measureless", "undeniabIc": "undeniable", "forQh": "forth", "yGur": "your", "coHimitting":
    "committing", "superHuous": "superfluous", "aiFection": "affection", "anotheF": "another", "arrivinLy":
    "arriving", "transaCtions": "transactions", "acComplished": "accomplished", "desGend": "descend",
    "wMom": "whom", "diflSciles": "difficiles", "afFecta": "affecta", "quEe": "quae", "aEsculapius": "Aesculapius",
    "wiH": "will", "aH": "all", "thinKs": "thinks", "haVe": "have", "reaL": "real", "welL": "well",
    "materiaL": "material", "wHereas": "whereas", "wiThout": "without", "tHis": "this", "sOme": "some",
    "tO": "to", "oF": "of", "yE": "ye", "pThis": "This", "lxviiL": "lxviii.", "proRoman": "pro-Roman",
    "hGude": "Gude", "wLl": "will", "saL": "sail", "g-een": "green", "souis": "souls", "ouick": "quick",
    "mounuains": "mountains", "bebeld": "beheld",
    # a capital I for l
    "aIl": "all", "alI": "all", "aIthough": "although", "bIock": "block", "folIowed": "followed",
    "foIlowed": "followed", "fuIl": "full", "househoIds": "households", "illiberaI": "illiberal",
    "vaIueless": "valueless", "equivaIent": "equivalent", "benevolentIy": "benevolently", "ignobIy": "ignobly",
    "equaIizing": "equalizing", "reguIar": "regular", "respIendent": "resplendent", "fuIfilleth": "fulfilleth",
    "coIour": "colour", "goId": "gold", "felIy": "felly", "nobIy": "nobly", "resistIess": "resistless",
    "highIy": "highly", "cIeavest": "cleavest", "newIy": "newly", "wiId": "wild", "bIent": "blent",
    "miIch": "milch", "waIketh": "walketh", "weIl": "well", "felI": "fell", "acknowIedging": "acknowledging",
    "secuIorum": "seculorum", "dissoIutely": "dissolutely", "peopIe": "people", "telI": "tell",
    "individuaI": "individual", "intellIgence": "intelligence", "wiII": "will", "saiIed": "sailed", "abandonIng": "abandoning", "AIIah": "Allah",
    # two words run together, or a word and an OCR slip
    "stalCthat": "stalk that", "thGods": "the Gods", "oLcontradictories": "of contradictories",
    "untrulySvho": "untruly, who", "nymphsT": "nymphs.", "aLuscius": "a Luscius", "authorityasGod":
    "authority as God", "letFG": "let FG", "themI": "them I", "butI": "but I", "isI": "is", "triumphI": "triumph I",
    "sentA": "sent A", "carO": "car O", "heavenA": "heaven A", "meThis": "me This", "usThat": "us That",
    "aHoly": "a Holy", "asSt": "as St", "thatSt": "that St", "thEmpress": "the Empress", "thM at": "that",
    "aMe n": "ame in", "exceptGRIPUS": "except GRIPUS", "scaRABEE": "Scarabee", "LenC iESA tulus": "Lentulus",
    "anoTuer": "another", "aNoTHER": "another", "aNoruer": "another", "Zo nErmeEs": "To Hermes",
    "imperioCaesaris": "imperio Caesaris", "mambuhaMana": "mambuha Mana", "diwansMasiqta": "diwans Masiqta",
    **{w: re.sub(r"(?<=[a-z])(?=[A-Z])", " ", w, count=1) for w in (
        "groundCollapsing", "waterFood", "sonsPresent", "favourAgni", "existSoma", "downGuard", "flowingSoma",
        "filterIndu", "horseLaud", "rainEven", "feastAgni", "falsehoodDistilling", "handFour", "worshipAdding",
        "manyVerily", "barleyLoving", "blessingsWealth", "bootyEven", "sacrificerWorship", "formedOnce",
        "safelyVaruna", "oilApproach", "manyHymn", "canstRiches", "thusSudatha", "postulatingHomestead",
        "entitledLaw", "flyPalestra", "realDionysus", "magnificentGreat", "wordAfter", "friendsVincentius",
        "ownFlaccus", "lovesMe", "whenHe", "banquetAntipater", "queenCatherine")},
    # a footnote's reference stuck to a word
    "lionsIbid.,": "lions,", "eaglesIbid.,": "eagles,", "visiblePs. xix.": "visible",
}
_OCR = re.compile(r"(?<![\w'’])(" + "|".join(re.escape(w) for w in sorted(OCR_WORDS, key=len, reverse=True))
                  + r")(?![\w])")


def ocr_words(text: str) -> str:
    return _OCR.sub(lambda m: OCR_WORDS[m.group(1)], text)


# Greek typed for an old Greek font (the transcriptions of Calvin and the Book of Concord): a breathing as j / J after
# the vowel, the accents as v ; ' [ { (acute, grave, circumflex, smooth or rough with one), a final sigma as ".
# Only the words found and read there (2026-11-01), and "kai;" "pro;" "tw’n" "prov"" between two of them.
_FONT_LETTERS = dict(zip("abgdezhqiklmnxoprstufcyw", "αβγδεζηθικλμνξοπρστυφχψω"))
_FONT_MARKS = {"j": "̓", "J": "̔", "v": "́", ";": "̀", "'": "͂", "’": "͂",
               "[": "̓́", "]": "̔́", "{": "̓̀", "}": "̔̀"}
FONT_GREEK = {
    "reformation/calvin.json": (
        'ajkolasiva ajkrasiva ajntivlutron ajpoluvtrwsi" aujtexouvsion aujtov" ejp ejthelodou\'lo" emma" filautiva '
        'filoneikiva ijdiwmavtwn ijdiwvmata kaqarmavton koinoniva pavtho" oJion oJmoouvsion iJlasthvrion a[geisi'),
    "reformation/book_of_concord.json": (
        'Leitourgiva Sunergou’te" parakalou’men ajkhdia ajkoinwnhvtou" ajpievnai duvo ejpieikeiva ejpieivkeian '
        'eujtaxiva fuvsei" kaqavrmata koinwniva mavgeiroi musthrivwn e{nwsi" pantavpasin periyhvmata eJauta;"'),
}
_FONT_BETWEEN = {"kai;", "kai", "pro;", "tw’n", "tw'n", 'prov"'}


def font_greek(word: str) -> str:
    out = []
    for ch in word:
        if ch.lower() in _FONT_LETTERS:
            g = _FONT_LETTERS[ch.lower()]
            out.append(g.upper() if ch.isupper() and ch not in "J" else g)
        elif ch == '"':
            out.append("ς")
        elif ch in _FONT_MARKS:
            out.append(_FONT_MARKS[ch])
    s = re.sub(r"σ$", "ς", "".join(out))
    return unicodedata.normalize("NFC", s)


def greek_from_font(text: str, rel: str) -> str:
    words = set(FONT_GREEK.get(rel, "").split())
    if not words:
        return text
    tokens = list(re.finditer(r"(?<![\w’'])[A-Za-z][A-Za-z'’;\"\[\]{}]*", text))
    greek = [t.group(0) in words for t in tokens]
    for i, t in enumerate(tokens):                     # ("filautiva kai; filoneikiva")
        if t.group(0) in _FONT_BETWEEN and 0 < i < len(tokens) - 1:
            left = next((j for j in range(i - 1, -1, -1) if tokens[j].group(0) not in _FONT_BETWEEN), None)
            right = next((j for j in range(i + 1, len(tokens)) if tokens[j].group(0) not in _FONT_BETWEEN), None)
            if left is not None and right is not None and greek[left] and greek[right]:
                greek[i] = True
    for i, t in reversed(list(enumerate(tokens))):
        if greek[i]:
            text = text[:t.start()] + font_greek(t.group(0)) + text[t.end():]
    return text


def plain_greek(latin: str) -> str:
    """Unaccented Greek in Latin letters, as Cureton's Eusebius gives two inscriptions ("Dioklhtianou kai efexhV"):
    h η, w ω, q θ, x ξ, f φ, y ψ, c χ, V a final σ."""
    table = dict(zip("abgdezhqiklmnxoprstufcyw", "αβγδεζηθικλμνξοπρστυφχψω"))
    out = "".join((table[ch.lower()].upper() if ch.isupper() else table[ch]) if ch.lower() in table and ch != "V"
                  else "ς" if ch == "V" else ch for ch in latin)
    return re.sub(r"σ(?=\W|$)", "ς", out)


_EUSEBIUS_GREEK = [
    "Eusebiou suggramma peri twn kat' auton marturhsantwn en twi oktaetei Dioklhtianou kai efexhV Galeriou tou "
    "Maximinou diwgmou",
    "Eusebiou tou Pamfilou peri twn en Palaistinhi marturhsantwn teloV",
    "OiV ge mhn autoV paregenomen, toutouV kai toiV meq hmaV gnwrimouV di eteraV poihsomai grafhV",
]


# tertullian.org's page numbers in its transcriptions of the Fathers ("the rich man and the |20 beggar", "|iii"),
# not in a table's lines (Sepharial's)
PAGE_MARK = re.compile(r"[ \t]?\|(?:\d{1,4}|[ivxlc]{1,7})\b(?=[ \t]?)")
PAGE_FILES = re.compile(r"^patristics/.*$")


# tertullian.org's footnote numbers left beside the punctuation in the Fathers ("his covenant in my mouth 6 .",
# "Interocrina 25 ;", "the son-in-law to the king?» 4 ,"): not a chapter cited bare ("the pool John 5 ,")
_BIBLE_BOOKS = set("""Genesis Gen Exodus Ex Exod Leviticus Lev Numbers Num Deuteronomy Deut Joshua Josh Judges Judg
Ruth Samuel Sam Kings Kgs Chronicles Chron Ezra Nehemiah Neh Esther Esth Job Psalm Psalms Ps Proverbs Prov
Ecclesiastes Eccl Song Songs Canticles Isaiah Isa Jeremiah Jer Lamentations Lam Ezekiel Ezek Daniel Dan Hosea Hos
Joel Amos Obadiah Jonah Micah Nahum Habakkuk Zephaniah Haggai Zechariah Zech Malachi Mal Matthew Matt Mark Luke
John Acts Romans Rom Corinthians Cor Galatians Gal Ephesians Eph Philippians Phil Colossians Col Thessalonians
Thess Timothy Tim Titus Philemon Hebrews Heb James Peter Pet Jude Revelation Rev Apocalypse Tobit Tob Judith
Wisdom Wis Sirach Ecclesiasticus Ecclus Baruch Maccabees Macc Esdras chapter chap ch book Book vol p pp page canon
Canon Epistle Letter Homily Psalm Ode verse ver""".split())
# (a year or a count, not a footnote: "in the year 553 .", "about 30 ,")
_BEFORE_A_NUMBER = {"year", "years", "in", "a.d", "ad", "about", "c", "circa", "until", "till", "since", "from",
                    "to", "after", "before", "anno", "died", "born", "of", "the", "and", "or", "than", "nearly",
                    "some", "over", "under", "aged", "age", "number", "no", "nos", "fol", "col", "line", "lines",
                    "ver", "vv", "v", "vers", "cap", "lib", "sect", "art", "q", "chap", "ch", "can", "ep", "hom"}
_FN_NUM = re.compile(r"(\b[\w’']+)?([.,;:!?»”\"’)]?) (\d{1,4}) (?=[.,;:»\]])|(?<=[»]) ?(\d{1,4})\b")


def footnote_numbers_out(text: str) -> str:
    def one(m):
        if m.group(4):                                  # (after a closing guillemet)
            return ""
        word, punct = m.group(1) or "", m.group(2)
        if punct in ("", ".") and (word in _BIBLE_BOOKS or word.lower() in _BEFORE_A_NUMBER
                                   or re.fullmatch(r"[ivxlcIVXLC]+", word)) \
                or re.search(r"\d", word):                  # ("Ver. 35 .", "c. vi. 63 ]", "[ John 11:6, 39 ]")
            return m.group(0)
        return f"{word}{punct}"
    text = _FN_NUM.sub(one, text)
    return re.sub(r"(?<=[a-z][.!?”\"]) \d{1,4}$", "", text)            # (one ending the passage: "a deacon. 154")


def page_marks_out(text: str) -> str:
    # (a table's line has a pipe standing free, " | " or "| |"; a page number never does)
    return "\n".join(line if re.search(r"\s\|\s|\|\s*\|", line)
                     else re.sub(r"[ \t]{2,}", " ", PAGE_MARK.sub("", line)).rstrip()
                     for line in text.split("\n"))


def split_joined(text: str, vocab=None) -> str:
    """ "theWorlds" -> "the Worlds"; but "ofFering", "beAuteous" (a capital the OCR put inside one word, where the
    book has "offering", "beauteous" elsewhere) -> the word."""
    vocab = _VOCAB["words"] if vocab is None else vocab

    def one(m):
        whole = m.group(1) + m.group(2)
        if len(m.group(2)) == 2 and m.group(1) in _COMMON:    # ("Pater te theOn te": Greek, not "the On")
            return whole
        return whole.lower() if whole.lower() in vocab else f"{m.group(1)} {m.group(2)}"
    return _JOINED_RIGHT.sub(one, _JOINED_LEFT.sub(one, text))


def _words_of(payload: dict) -> frozenset:
    out = set()

    def walk(node):
        if isinstance(node, str):
            out.update(re.findall(r"(?<![\w'’])[a-z]{4,}\b", node))
        elif isinstance(node, dict):
            for v in node.values():
                walk(v)
    walk(payload.get("books", {}))
    return frozenset(out)


def clean_text(text: str, rel: str) -> str:
    before = None
    while before != text:                               # "&amp;gt;" -> "&gt;" -> ">"
        before, text = text, html.unescape(text)
    text = CSS.sub("", text)
    text = EDITOR_NOTE.sub("", text)
    text = TAIL.sub("", text)
    for pat, rep in FIXES.get(rel, []):
        text = re.sub(pat, rep, text, flags=re.S | re.M)
    if TERT_FILES.match(rel):
        text = greek_from_tertullian(text)
    if BETA_FILES.match(rel):
        text = greek_from_beta(text)
    # _italic_ (Gutenberg's markup) -> Discord's *italic*; a stray one between words -> a space
    text = re.sub(r"(?<![\w*])_(?=[^\s)])([^_\n]{1,400}?)(?<=[^\s(])_(?![\w*])", r"*\1*", text)
    text = re.sub(r"(?<=\w)_(?=\w)", " ", text)
    text = re.sub(r"(?<![\w*])_(?=\w)|(?<=[\w.,;:!?])_(?![\w*])", "", text)   # an unpaired one
    text = re.sub(r"(\w)~ (\w)", r"\1\2", text)          # a broken hyphenation: "recog~ nised"
    text = re.sub(r"[ \t]*\}\}-->[ \t]*", " ", text).strip()    # the end of an HTML comment (NewAdvent)
    text = re.sub(r"\[\[([^\[\]\n]*)\]\]", r"[\1]", text)        # "[[Greek: aktines]]"
    if not JOINED_EXEMPT.match(rel):
        text = split_joined(ocr_words(text))
    if PAGE_FILES.match(rel):
        before = None
        while before != text:                           # (one gone can bare another: "deacon. 154 |36")
            before, text = text, footnote_numbers_out(page_marks_out(text))
    text = greek_from_font(text, rel)
    if rel == "patristics/eusebius_of_caesarea.json":
        for latin in _EUSEBIUS_GREEK:
            text = text.replace(latin, plain_greek(latin))
    return _unpaired_stars(text)


_PAIRED = re.compile(r"\*\*(?=\S)[^*\n]+?(?<=\S)\*\*|(?<!\*)\*(?=[^\s*])[^*\n]*?(?<=[^\s*])\*(?!\*)")


def _unpaired_stars(text: str) -> str:
    """Without the asterisks that italicise nothing (footnote marks: "thoughts,* he"; "* * *"), which
    would leave Discord's italics open."""
    if "*" not in text:
        return text
    keep = {i for m in _PAIRED.finditer(text) for i in range(m.start(), m.end())}
    out = "".join(ch if ch != "*" or i in keep else
                  (" " if 0 < i < len(text) - 1 and text[i - 1].isalnum() and text[i + 1].isalnum() else "")
                  for i, ch in enumerate(text))
    if out != text:
        out = re.sub(r"[ \t]{2,}", " ", out)
        out = "\n".join(line.strip() for line in out.split("\n")).strip()
    return out


def clean_corpus(payload: dict, rel: str) -> int:
    """Clean one loaded corpus file in place; returns how many verses changed or went."""
    rel = rel.replace("\\", "/")
    changed = 0
    _VOCAB["words"] = _words_of(payload)
    for book, chapters in payload.get("books", {}).items():
        for (b, ch, v, cut) in ENDS.get(rel, []):
            if b != book or ch not in chapters:
                continue
            keys = list(chapters)
            for later in keys[keys.index(ch) + 1:]:
                changed += len(chapters[later]) if isinstance(chapters[later], dict) else 1
                del chapters[later]
            verses = chapters[ch]
            vkeys = list(verses)
            if v in verses:
                for later in vkeys[vkeys.index(v) + 1:]:
                    del verses[later]
                    changed += 1
                cut_text = re.sub(cut, "", verses[v], flags=re.S)
                if cut_text != verses[v]:
                    verses[v] = cut_text
                    changed += 1
        for ch in list(chapters):
            verses = chapters[ch]
            if isinstance(verses, str):                  # a chapter kept as one text
                new = clean_text(verses, rel)
                if new != verses:
                    changed += 1
                    if new:
                        chapters[ch] = new
                    else:
                        del chapters[ch]
                continue
            keys = list(verses)
            if FOOTNOTE_FILES.match(rel):                # the trailing run of footnotes
                i = len(keys)
                while i and FOOTNOTE.match(verses[keys[i - 1]] or ""):
                    i -= 1
                for k in keys[i:]:
                    del verses[k]
                    changed += 1
                keys = keys[:i]
            if rel in INDEX_FILES:
                start = next((n for n, k in enumerate(keys) if INDEX_HEAD.match(verses[k].strip())), None)
                if start is not None:
                    for k in keys[start:]:
                        del verses[k]
                        changed += 1
                    keys = keys[:start]
            for k in keys:
                new = clean_text(verses[k], rel)
                if new != verses[k]:
                    changed += 1
                    if new:
                        verses[k] = new
                    else:
                        del verses[k]
            if not verses:
                del chapters[ch]
    return changed
