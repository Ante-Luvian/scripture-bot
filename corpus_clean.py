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
    "apostolic_fathers/epistle_of_barnabas.json": [(r"\s*~y\b", "")],
    "apostolic_fathers/ignatius_romans.json": [(r"\+([^+]+)\+", r"*\1*")],
    "classical/meditations_long.json": [(r"\+([^+]+)\+", r"*\1*")],
    "patristics/philoxenus_of_hierapolis.json": [(r"^[\w$)(]{1,6}(?: [\w$)(]{1,6}){3,}$", "")],   # Syriac in ASCII
    "ancient_near_east/instruction_of_amenemope.json": [                  # the Egyptian, transliterated: not a translation
        (r"^\*\*(?:Egyptian \(Egyptological Transliteration\)|Variant Witnesses)\*\*.*", ""),
        (r"^\*\*Variant:.*?(?:\n---\n+|\Z)", "")],
}

# where a book's real text stops (everything after goes): file -> [(book, chapter, verse, cut-at pattern)]
ENDS = {
    "classical/iamblichus.json": [("On the Mysteries", "150", "4", r"\s*-{10,}.*")],   # then a publisher's catalogue, the Gutenberg licence
    "classical/julian.json": [("Hymn to King Helios", "30", "7", r"$^")],                   # chapters 31-56 are the translator's notes
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
