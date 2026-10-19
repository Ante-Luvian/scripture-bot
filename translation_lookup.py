"""
translation_lookup.py — bolls.life Bible translation lookups
Features: single verse, range, whole chapter, cross-chapter range,
          multi-chapter range, parallel display, random verse, translation search,
          in-memory chapter cache.
"""
from __future__ import annotations
import re, html as html_mod, json, urllib.request, urllib.error, urllib.parse
import random as _random
from typing import Optional

TRANSLATIONS: dict[str, tuple[str, str]] = {
    "esv":      ("ESV",      "English Standard Version (2016)"),
    "nasb":     ("NASB",     "New American Standard Bible (1995)"),
    "nasb95":   ("NASB",     "New American Standard Bible (1995)"),
    "nrsvce":   ("NRSVCE",   "New Revised Standard Version Catholic Edition (1993)"),
    "nrsv":     ("NRSVCE",   "New Revised Standard Version Catholic Edition (1993)"),
    "rsv":      ("RSV",      "Revised Standard Version (1952)"),
    "rsv2ce":   ("RSV2CE",   "Revised Standard Version Catholic Edition"),
    "nkjv":     ("NKJV",     "New King James Version (1982)"),
    "nlt":      ("NLT",      "New Living Translation (2015)"),
    "net":      ("NET",      "New English Translation (2007)"),
    "csb":      ("CSB17",    "Christian Standard Bible (2017)"),
    "csb17":    ("CSB17",    "Christian Standard Bible (2017)"),
    "amp":      ("AMP",      "Amplified Bible (2015)"),
    "msg":      ("MSG",      "The Message (2002)"),
    "lsb":      ("LSB",      "Legacy Standard Bible"),
    "web":      ("WEB",      "World English Bible"),
    "ylt":      ("YLT",      "Young's Literal Translation (1898)"),
    "asv":      ("ASV",      "American Standard Version (1901)"),
    "gnv":      ("GNV",      "Geneva Bible (1599)"),
    "kjv":      ("KJV",      "King James Version (1769)"),
    "lxxe":     ("LXXE",     "Brenton Septuagint (1851, English)"),
    "brenton":  ("LXXE",     "Brenton Septuagint (1851, English)"),
    "nabre":    ("NABRE",    "New American Bible Revised Edition"),
    "njb":      ("NJB1985",  "New Jerusalem Bible (1985)"),
    "njb1985":  ("NJB1985",  "New Jerusalem Bible (1985)"),
    "jb":       ("NJB1985",  "New Jerusalem Bible (1985)"),
    "jerusalem": ("NJB1985", "New Jerusalem Bible (1985)"),
    "jerusalem bible": ("NJB1985", "New Jerusalem Bible (1985)"),
    "cjb":      ("CJB",      "Complete Jewish Bible (1998)"),
    "tlv":      ("TLV",      "Tree of Life Version"),
    "cev":      ("CEVD",     "Contemporary English Version (2006)"),
    "ceb":      ("CEB",      "Common English Bible (2011)"),
    "gnt":      ("GNTD",     "Good News Translation (2001)"),
    "erv":      ("ERV",      "Easy-to-Read Version (2006)"),
    "mev":      ("MEV",      "Modern English Version"),
    "isv":      ("ISV",      "International Standard Version (2011)"),
    "lsv":      ("LSV",      "Literal Standard Version"),
    "bsb":      ("BSB",      "Berean Standard Bible"),
    # ── Ancient languages ──────────────────────────────────────────────────────
    "vulg":     ("VULG",     "Biblia Sacra Vulgata (Clementine)"),
    "vulgate":  ("VULG",     "Biblia Sacra Vulgata (Clementine)"),
    "vlg":      ("VULG",     "Biblia Sacra Vulgata (Clementine)"),
    "lxx":      ("LXX",      "Septuagint (Greek OT)"),
    "oe":       ("OE",       "Old English (Wessex Gospels / Ælfric, ~990 AD)"),
    "oldenglish": ("OE",     "Old English (Wessex Gospels / Ælfric, ~990 AD)"),
    "ang":      ("OE",       "Old English (Wessex Gospels / Ælfric, ~990 AD)"),
    "anglosaxon": ("OE",     "Old English (Wessex Gospels / Ælfric, ~990 AD)"),
    "csl":       ("CSL",      "Church Slavonic (Elizabeth Bible, 1757)"),
    "cslelizabeth": ("CSL",   "Church Slavonic (Elizabeth Bible, 1757)"),
    "slavonic":  ("CSL",      "Church Slavonic (Elizabeth Bible, 1757)"),
    "ocs":       ("CSL",      "Church Slavonic (Elizabeth Bible, 1757)"),
    "peshitta":  ("PESHITTA", "Peshitta (Aramaic/Syriac)"),
    "syriac":    ("PESHITTA", "Peshitta (Aramaic/Syriac)"),
    "aramaic":   ("PESHITTA", "Peshitta (Aramaic/Syriac)"),
    "syc":       ("PESHITTA", "Peshitta (Aramaic/Syriac)"),
    "septuagint": ("LXX",    "Septuagint (Greek OT)"),
    "heb":      ("WLC",      "Westminster Leningrad Codex (Hebrew OT, with vowels)"),
    "hebrew":   ("WLC",      "Westminster Leningrad Codex (Hebrew OT, with vowels)"),
    "wlc":      ("WLC",      "Westminster Leningrad Codex (Hebrew OT, with vowels)"),
    "wlca":     ("WLCa",     "Westminster Leningrad Codex (Hebrew OT, with Strong's)"),
    "wlcc":     ("WLCC",     "Westminster Leningrad Codex (Hebrew OT, consonants only)"),
    "gnt-gr":   ("NTGT",     "Greek NT: Tischendorf 8th Ed."),
    "greek":    ("NTGT",     "Greek NT: Tischendorf 8th Ed."),
    "grk":      ("NTGT",     "Greek NT: Tischendorf 8th Ed."),
    "tisch":    ("TISCH",    "Greek NT: Tischendorf 8th Ed. (with Strong's)"),
    "tr":       ("TR",       "Textus Receptus (Elzevir 1624, Greek NT)"),
    "textus receptus": ("TR", "Textus Receptus (Elzevir 1624, Greek NT)"),
    "latin":    ("VULG",     "Vulgata Clementina (Latin)"),
}

# Translations bolls.life no longer serves: asked for one, it answers with a notice in place of every
# verse ("Biblica, Inc. has prohibited me from using the NIV translation..."), which the bot then
# showed as the verse. They're still recognised, so asking for one explains why it's gone.
WITHDRAWN: dict[str, str] = {name: (
    "📕 **The NIV isn't available any more.** I get modern translations from a free Bible service "
    "(bolls.life), and Biblica, the publisher that owns the New International Version, has had it stop "
    "offering the NIV, so I can't show it. The **NKJV**, **ESV**, **CSB** or **NLT** are close alternatives "
    "(`!verse John 3:16 NKJV`), and `!translations` lists them all.") for name in ("niv", "niv84", "niv2011")}

TRANSLATION_SUFFIXES: set[str] = set(TRANSLATIONS.keys()) | set(WITHDRAWN)
# what bolls.life puts in place of a verse it may not show
_WITHHELD = re.compile(r"has prohibited me from using|have chosen financial profit", re.I)

_BOOK_IDS: dict[str, int] = {
    "genesis":1,"exodus":2,"leviticus":3,"numbers":4,"deuteronomy":5,
    "joshua":6,"judges":7,"ruth":8,"1 samuel":9,"2 samuel":10,
    "1 kings":11,"2 kings":12,"1 chronicles":13,"2 chronicles":14,
    "ezra":15,"nehemiah":16,"esther":17,"job":18,"psalms":19,"psalm":19,
    "proverbs":20,"ecclesiastes":21,"song of solomon":22,"song of songs":22,
    "isaiah":23,"jeremiah":24,"lamentations":25,"ezekiel":26,"daniel":27,
    "hosea":28,"joel":29,"amos":30,"obadiah":31,"jonah":32,"micah":33,
    "nahum":34,"habakkuk":35,"zephaniah":36,"haggai":37,"zechariah":38,
    "malachi":39,"matthew":40,"mark":41,"luke":42,"john":43,"acts":44,
    "romans":45,"1 corinthians":46,"2 corinthians":47,"galatians":48,
    "ephesians":49,"philippians":50,"colossians":51,
    "1 thessalonians":52,"2 thessalonians":53,"1 timothy":54,"2 timothy":55,
    "titus":56,"philemon":57,"hebrews":58,"james":59,"1 peter":60,
    "2 peter":61,"1 john":62,"2 john":63,"3 john":64,"jude":65,
    "revelation":66,"revelations":66,
    # ── LXX apocrypha (bolls.life real IDs from /get-books/LXX/) ──────────────
    # 67: Ἔσδρας Αʹ  68: Τωβίτ  69: Ἰουδίθ  70: Σοφία Σαλωμῶνος
    # 71: Σοφία Σιράχ  73: Βαρούχ  74: Μακκαβαίων Αʹ  75: Μακκαβαίων Βʹ
    # 76: Μακκαβαίων Γʹ  78: Σουσάννα  79: Βὴλ καὶ Δράκων  80: Μακκαβαίων Δʹ
    # 85: Ψαλμοὶ Σολομῶντος  86: Ὠδαί
    # ── VULG apocrypha (bolls.life real IDs from /get-books/VULG/) ────────────
    # 68: Tobiæ  69: Judith  70: Sapientia  71: Ecclesiasticus
    # 73: Baruch  74: Machabæorum I  75: Machabæorum II
    # ── Shared entries (same ID in both) ──────────────────────────────────────
    "1 esdras":67,"esdras a":67,
    "tobit":68,"tobias":68,"tob":68,
    "judith":69,"jdt":69,
    "wisdom of solomon":70,"wisdom":70,"wis":70,"wisd":70,
    "sapientia":70,
    "sirach":71,"ecclesiasticus":71,"sir":71,
    "baruch":73,"bar":73,
    "1 maccabees":74,"1macc":74,"i maccabees":74,"machabees i":74,"1 machabees":74,
    "2 maccabees":75,"2macc":75,"ii maccabees":75,"machabees ii":75,"2 machabees":75,
    "3 maccabees":76,"3macc":76,
    "susanna":78,"sus":78,
    "bel and the dragon":79,"bel":79,
    "4 maccabees":80,"4macc":80,
    "psalms of solomon":85,
    # Vulgate appendix (no bolls.life ID; handled via local data)
    "prayer of manasseh":1000,"oratio manassae":1000,
    "2 esdras":1001,"4 esdras":1001,"2 ezra":1001,
    "psalm 151":1002,"ps151":1002,"additional psalm":1002,
}

_ID_TO_BOOK: dict[int, str] = {
    1:"Genesis",2:"Exodus",3:"Leviticus",4:"Numbers",5:"Deuteronomy",
    6:"Joshua",7:"Judges",8:"Ruth",9:"1 Samuel",10:"2 Samuel",
    11:"1 Kings",12:"2 Kings",13:"1 Chronicles",14:"2 Chronicles",
    15:"Ezra",16:"Nehemiah",17:"Esther",18:"Job",19:"Psalms",
    20:"Proverbs",21:"Ecclesiastes",22:"Song of Solomon",23:"Isaiah",
    24:"Jeremiah",25:"Lamentations",26:"Ezekiel",27:"Daniel",28:"Hosea",
    29:"Joel",30:"Amos",31:"Obadiah",32:"Jonah",33:"Micah",34:"Nahum",
    35:"Habakkuk",36:"Zephaniah",37:"Haggai",38:"Zechariah",39:"Malachi",
    40:"Matthew",41:"Mark",42:"Luke",43:"John",44:"Acts",45:"Romans",
    46:"1 Corinthians",47:"2 Corinthians",48:"Galatians",49:"Ephesians",
    50:"Philippians",51:"Colossians",52:"1 Thessalonians",53:"2 Thessalonians",
    54:"1 Timothy",55:"2 Timothy",56:"Titus",57:"Philemon",58:"Hebrews",
    59:"James",60:"1 Peter",61:"2 Peter",62:"1 John",63:"2 John",
    64:"3 John",65:"Jude",66:"Revelation",
    # Deuterocanon / Apocrypha (bolls.life real IDs)
    67:"1 Esdras",68:"Tobit",69:"Judith",
    70:"Wisdom of Solomon",71:"Sirach",73:"Baruch",
    74:"1 Maccabees",75:"2 Maccabees",76:"3 Maccabees",
    78:"Susanna",79:"Bel and the Dragon",80:"4 Maccabees",
    85:"Psalms of Solomon",86:"Odes",
    1000:"Prayer of Manasseh",1001:"2 Esdras",1002:"Psalm 151",
}

_CHAPTER_COUNTS: dict[int, int] = {
    1:50,2:40,3:27,4:36,5:34,6:24,7:21,8:4,9:31,10:24,11:22,12:25,
    13:29,14:36,15:10,16:13,17:10,18:42,19:150,20:31,21:12,22:8,23:66,
    24:52,25:5,26:48,27:12,28:14,29:3,30:9,31:1,32:4,33:7,34:3,35:3,
    36:3,37:2,38:14,39:4,40:28,41:16,42:24,43:21,44:28,45:16,46:16,
    47:13,48:6,49:6,50:4,51:4,52:5,53:3,54:6,55:4,56:3,57:1,58:13,
    59:5,60:5,61:3,62:5,63:1,64:1,65:1,66:22,
}

_ALIASES: dict[str, str] = {
    "gen":"genesis","exod":"exodus","ex":"exodus","lev":"leviticus",
    "num":"numbers","deut":"deuteronomy","deu":"deuteronomy","josh":"joshua","judg":"judges",
    "1sam":"1 samuel","2sam":"2 samuel","1kgs":"1 kings","2kgs":"2 kings",
    "1chr":"1 chronicles","2chr":"2 chronicles","neh":"nehemiah",
    "esth":"esther","ps":"psalms","psa":"psalms","prov":"proverbs",
    "eccl":"ecclesiastes","sos":"song of solomon","song":"song of solomon",
    "isa":"isaiah","jer":"jeremiah","lam":"lamentations","ezek":"ezekiel",
    "dan":"daniel","hos":"hosea","obad":"obadiah","jon":"jonah",
    "mic":"micah","nah":"nahum","hab":"habakkuk","zeph":"zephaniah",
    "hag":"haggai","zech":"zechariah","mal":"malachi",
    "matt":"matthew","mt":"matthew","mk":"mark","lk":"luke","jn":"john",
    "rom":"romans","1cor":"1 corinthians","2cor":"2 corinthians",
    "gal":"galatians","eph":"ephesians","phil":"philippians","col":"colossians",
    "1thess":"1 thessalonians","2thess":"2 thessalonians",
    "1tim":"1 timothy","2tim":"2 timothy","tit":"titus","phlm":"philemon",
    "heb":"hebrews","jas":"james","jam":"james",
    "1pet":"1 peter","2pet":"2 peter","1jn":"1 john","2jn":"2 john",
    "3jn":"3 john","rev":"revelation","apoc":"revelation",
    "psalm":"psalms","psa":"psalms","ps":"psalms",
    "prayer of manasseh":"prayer of manasseh","manasseh":"prayer of manasseh","pman":"prayer of manasseh",
    "2 esdras":"2 esdras","4 esdras":"2 esdras","esdras b":"2 esdras",
    "3 esdras":"1 esdras","esdras a":"1 esdras",
}

_BASE_URL = "https://bolls.life"
_TIMEOUT  = 12
_chapter_cache: dict[tuple, list] = {}
# Per-translation book name → id cache (fetched on demand, covers apocrypha)
_trans_books_cache: dict[str, dict[str, int]] = {}  # slug → {lower_name: bookid}

# ── Local Vulgate appendix (Clementine 1592, books not in bolls.life) ────────
_vulg_appendix: Optional[dict] = None

def _load_vulg_appendix() -> Optional[dict]:
    global _vulg_appendix
    if _vulg_appendix is not None:
        return _vulg_appendix
    import pathlib
    for p in [
        pathlib.Path(__file__).parent / "data" / "vulg_appendix.json",
        pathlib.Path("data") / "vulg_appendix.json",
    ]:
        if p.exists():
            _vulg_appendix = json.loads(p.read_text(encoding="utf-8")).get("books", {})
            return _vulg_appendix
    return None

def _fetch_vulg_appendix_chapter(book_raw: str, chapter: int) -> Optional[list]:
    """Return bolls.life-style [{verse, text}] from local Vulgate appendix."""
    data = _load_vulg_appendix()
    if data is None:
        return None
    key = book_raw.strip().lower()
    book_name = None
    for name in data:
        if name.lower() == key:
            book_name = name
            break
    # Also try bid lookup
    if not book_name:
        bid = _resolve_book(book_raw)
        cand = _ID_TO_BOOK.get(bid) if bid else None
        if cand and cand in data:
            book_name = cand
    if not book_name:
        return None
    chap_data = data[book_name].get(str(chapter))
    if not chap_data:
        return None
    return [{"verse": int(v), "text": t}
            for v, t in sorted(chap_data.items(), key=lambda x: int(x[0]))]

# ── Local Peshitta (ETCBC / Peshitta Institute Leiden) ───────────────────────
_peshitta_ot: Optional[dict] = None
_peshitta_nt: Optional[dict] = None

def _load_peshitta(testament: str) -> Optional[dict]:
    """Load OT or NT Peshitta. testament = 'ot' or 'nt'."""
    global _peshitta_ot, _peshitta_nt
    if testament == "ot" and _peshitta_ot is not None:
        return _peshitta_ot
    if testament == "nt" and _peshitta_nt is not None:
        return _peshitta_nt
    import pathlib
    fname = f"peshitta_{testament}.json"
    for p in [
        pathlib.Path(__file__).parent / "data" / fname,
        pathlib.Path("data") / fname,
    ]:
        if p.exists():
            data = json.loads(p.read_text(encoding="utf-8")).get("books", {})
            if testament == "ot":
                _peshitta_ot = data
            else:
                _peshitta_nt = data
            return data
    return None

def _fetch_peshitta_chapter(book_raw: str, chapter: int) -> Optional[list]:
    """Return bolls.life-style [{verse, text}] from local Peshitta."""
    bid = _resolve_book(book_raw)
    book_name = _ID_TO_BOOK.get(bid) if bid else None
    if not book_name:
        key = book_raw.strip().lower()
        # Search both testaments
        for testament in ("ot", "nt"):
            data = _load_peshitta(testament)
            if data:
                for name in data:
                    if name.lower() == key:
                        book_name = name
                        break
    if not book_name:
        return None
    # Determine which testament
    testament = "nt" if (bid and bid >= 40) else "ot"
    data = _load_peshitta(testament)
    if not data or book_name not in data:
        # Try the other testament
        other = "ot" if testament == "nt" else "nt"
        data = _load_peshitta(other)
        if not data or book_name not in data:
            return None
    chap_data = data[book_name].get(str(chapter))
    if not chap_data:
        return None
    return [{"verse": int(v), "text": t}
            for v, t in sorted(chap_data.items(), key=lambda x: int(x[0]))]

# ── Local Church Slavonic (Elizabeth Bible 1757, via scrollmapper) ───────────
_csl_data: Optional[dict] = None

def _load_csl() -> Optional[dict]:
    global _csl_data
    if _csl_data is not None:
        return _csl_data
    import pathlib
    for p in [
        pathlib.Path(__file__).parent / "data" / "csl.json",
        pathlib.Path("data") / "csl.json",
    ]:
        if p.exists():
            _csl_data = json.loads(p.read_text(encoding="utf-8")).get("books", {})
            return _csl_data
    return None

def _fetch_csl_chapter(book_raw: str, chapter: int) -> Optional[list]:
    data = _load_csl()
    if data is None:
        return None
    bid = _resolve_book(book_raw)
    book_name = _ID_TO_BOOK.get(bid) if bid else None
    if not book_name or book_name not in data:
        key = book_raw.strip().lower()
        for name in data:
            if name.lower() == key:
                book_name = name
                break
        else:
            return None
    chap_data = data[book_name].get(str(chapter))
    if not chap_data:
        return None
    return [{"verse": int(v), "text": t}
            for v, t in sorted(chap_data.items(), key=lambda x: int(x[0]))]

# ── Local Old English Bible (Wessex Gospels + Heptateuch + Paris Psalter) ────
_oe_data: Optional[dict] = None

def _load_oe() -> Optional[dict]:
    global _oe_data
    if _oe_data is not None:
        return _oe_data
    import pathlib
    for p in [
        pathlib.Path(__file__).parent / "data" / "oe.json",
        pathlib.Path("data") / "oe.json",
    ]:
        if p.exists():
            _oe_data = json.loads(p.read_text(encoding="utf-8")).get("books", {})
            return _oe_data
    return None

def _fetch_oe_chapter(book_raw: str, chapter: int) -> Optional[list]:
    data = _load_oe()
    if data is None:
        return None
    bid = _resolve_book(book_raw)
    book_name = _ID_TO_BOOK.get(bid) if bid else None
    if not book_name or book_name not in data:
        key = book_raw.strip().lower()
        for name in data:
            if name.lower() == key:
                book_name = name
                break
        else:
            return None
    chap_data = data[book_name].get(str(chapter))
    if not chap_data:
        return None
    return [{"verse": int(v), "text": t}
            for v, t in sorted(chap_data.items(), key=lambda x: int(x[0]))]

# ── Local LXX (Swete 1930) ──────────────────────────────────────────────────
_lxx_swete: Optional[dict] = None

def _load_lxx_swete() -> Optional[dict]:
    global _lxx_swete
    if _lxx_swete is not None:
        return _lxx_swete
    import pathlib
    for p in [
        pathlib.Path(__file__).parent / "data" / "lxx_greek.json",
        pathlib.Path("data") / "lxx_greek.json",
    ]:
        if p.exists():
            _lxx_swete = json.loads(p.read_text(encoding="utf-8")).get("books", {})
            return _lxx_swete
    return None

def _fetch_lxx_chapter(book_raw: str, chapter: int) -> Optional[list]:
    """Return bolls.life-style [{verse, text}] from local Swete LXX."""
    data = _load_lxx_swete()
    if data is None:
        return None

    # Prayer of Manasseh lives in Odes chapter 8 in the Swete LXX
    key_lower = book_raw.strip().lower()
    if key_lower in ("psalm 151", "ps151", "additional psalm"):
        # Psalm 151 is not in the Swete LXX Odes; route to Vulgate appendix text
        return _fetch_vulg_appendix_chapter("Psalm 151", chapter)
    if key_lower in ("prayer of manasseh", "manasseh", "pman", "oratio manassae"):
        chap_data = data.get("Odes", {}).get("8")
        if not chap_data:
            return None
        return [{"verse": int(v), "text": t}
                for v, t in sorted(chap_data.items(), key=lambda x: int(x[0]))]

    bid = _resolve_book(book_raw)
    book_name = _ID_TO_BOOK.get(bid) if bid else None
    if not book_name or book_name not in data:
        # Try direct name match
        for name in data:
            if name.lower() == key_lower:
                book_name = name
                break
        else:
            return None
    chap_data = data.get(book_name, {}).get(str(chapter))
    if not chap_data:
        return None
    return [{"verse": int(v), "text": t}
            for v, t in sorted(chap_data.items(), key=lambda x: int(x[0]))]


def _get_trans_book_id(slug: str, book_raw: str) -> Optional[int]:
    """
    Try to resolve a book name using the translation's own book list from bolls.life.
    Falls back to _resolve_book() for the Protestant canon.
    Useful for deuterocanonical/apocryphal books that have IDs > 66.
    """
    # First try local table (fast, covers all 66 Protestant books)
    bid = _resolve_book(book_raw)
    if bid:
        return bid

    # Lazy-load the translation's book list
    if slug not in _trans_books_cache:
        url = f"{_BASE_URL}/get-books/{slug}/"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "ScriptureBot/1.0"})
            with urllib.request.urlopen(req, timeout=_TIMEOUT) as r:
                books = json.loads(r.read().decode("utf-8"))
            _trans_books_cache[slug] = {b["name"].lower(): b["bookid"] for b in books}
            # Also store canonical capitalised name for display
            _trans_books_cache[slug + "_display"] = {b["bookid"]: b["name"] for b in books}
        except Exception:
            _trans_books_cache[slug] = {}

    book_map = _trans_books_cache.get(slug, {})
    key = book_raw.strip().lower()

    # Exact match
    if key in book_map:
        return book_map[key]

    # Alias expansions for common apocrypha names
    _APOC_ALIASES: dict[str, list[str]] = {
        "tobit": ["tobit", "tob"],
        "judith": ["judith", "jdt"],
        "1 maccabees": ["1 maccabees", "1macc", "1 macc", "i maccabees"],
        "2 maccabees": ["2 maccabees", "2macc", "2 macc", "ii maccabees"],
        "3 maccabees": ["3 maccabees", "3macc"],
        "4 maccabees": ["4 maccabees", "4macc"],
        "wisdom": ["wisdom", "wisdom of solomon", "wis"],
        "sirach": ["sirach", "ecclesiasticus", "sir"],
        "baruch": ["baruch", "bar"],
        "1 esdras": ["1 esdras", "1esd", "esdras"],
        "2 esdras": ["2 esdras", "2esd"],
        "prayer of manasseh": ["prayer of manasseh", "man"],
    }
    for canonical, aliases in _APOC_ALIASES.items():
        if key in aliases:
            bid = book_map.get(canonical)
            if bid:
                return bid
            # Try partial match
            for bname, bid in book_map.items():
                if canonical in bname or bname in canonical:
                    return bid

    # Fuzzy partial match as last resort
    for bname, bid in book_map.items():
        if key in bname or bname.startswith(key[:4]):
            return bid

    return None


def _get_canon_name(slug: str, book_id: int, fallback: str) -> str:
    """Get the canonical book name from the translation's book list, or fallback."""
    display_map = _trans_books_cache.get(slug + "_display", {})
    return display_map.get(book_id, _ID_TO_BOOK.get(book_id, fallback))


def _resolve_book(raw: str) -> Optional[int]:
    key = raw.strip().lower()
    if key in _BOOK_IDS:
        return _BOOK_IDS[key]
    r = _ALIASES.get(key)
    if r:
        return _BOOK_IDS.get(r)
    m = re.match(r"^(\d)\s*([a-z]+)$", key)
    if m:
        exp = f"{m.group(1)} {m.group(2)}"
        bid = _BOOK_IDS.get(exp) or _BOOK_IDS.get(_ALIASES.get(exp, ""), 0)
        if bid:
            return bid
    return None


def _clean(text: str) -> str:
    text = html_mod.unescape(text)
    # Strong's-number tags, e.g. "created<S>1254</S>" or a standalone
    # " <S>853</S> " for an untranslated word (the Hebrew direct-object
    # marker, etc). Must remove tag + digits as one unit -- stripping the
    # <S></S> markup first and guessing at digits afterward (the old
    # approach) left orphaned numbers like "853" behind whenever the tag
    # wasn't glued directly onto a preceding word.
    text = re.sub(r"<S>\d+</S>", "", text)
    text = re.sub(r"<[^>]+>", "", text)  # any other stray HTML tags
    text = re.sub(r"[ \t]+", " ", text)  # collapse whitespace left by removed standalone tags
    return text.strip()



# ── Psalm numbering conversion (Masoretic ↔ Septuagint) ──────────────────────
# KJV/WLC/Peshitta use Masoretic numbering.
# LXX/VULG/CSL use Septuagint numbering.

def _mt_to_lxx_psalm(mt_ps: int) -> list:
    if mt_ps <= 8:        return [(mt_ps, None, None)]
    elif mt_ps == 9:      return [(9, 1, 21)]
    elif mt_ps == 10:     return [(9, 22, 39)]
    elif 11 <= mt_ps <= 113: return [(mt_ps - 1, None, None)]
    elif mt_ps == 114:    return [(113, 1, 8)]
    elif mt_ps == 115:    return [(113, 9, 26)]
    elif mt_ps == 116:    return [(114, None, None), (115, None, None)]
    elif 117 <= mt_ps <= 146: return [(mt_ps - 1, None, None)]
    elif mt_ps == 147:    return [(146, None, None), (147, None, None)]
    else:                 return [(mt_ps, None, None)]

_LXX_NUMBERED = {"LXX", "VULG", "CSL"}

def _fetch_chapter(slug: str, book_id: int, chapter: int, book_raw: str = "") -> Optional[list]:
    # Remap Psalm numbers for LXX-numbered translations
    _ps_vstart = _ps_vend = None
    _book_check = (book_raw or _ID_TO_BOOK.get(book_id, "")).strip().lower()
    if slug in _LXX_NUMBERED and _book_check in ("psalms", "psalm", "ps", "psa"):
        mappings = _mt_to_lxx_psalm(chapter)
        if len(mappings) > 1:
            # MT psalm spans two LXX psalms — fetch both and combine
            combined = []
            for lxx_ps, vs, ve in mappings:
                r = _fetch_chapter(slug, book_id, lxx_ps, book_raw)
                if r:
                    combined.extend(r)
            return combined if combined else None
        lxx_ps, _ps_vstart, _ps_vend = mappings[0]
        chapter = lxx_ps
    # Route LXX to local Swete file
    if slug == "LXX":
        _r = _fetch_lxx_chapter(book_raw or _ID_TO_BOOK.get(book_id, ""), chapter)
        if _r and _ps_vstart is not None:
            _r = [v for v in _r if _ps_vstart <= v.get("verse", 0) <= _ps_vend]
        return _r
    # Route Vulgate appendix books to local file.
    # Synthetic IDs >= 1000 are always appendix. Also intercept named books
    # that bolls.life VULG doesn't carry (1 Esdras, Prayer of Manasseh, Psalm 151).
    _VULG_APPENDIX_NAMES = {
        "prayer of manasseh", "oratio manassae",
        "1 esdras", "3 esdras",
        "2 esdras", "4 esdras",
        "psalm 151", "additional psalm",
    }
    if slug == "VULG":
        _raw_lower = (book_raw or _ID_TO_BOOK.get(book_id, "")).strip().lower()
        if book_id >= 1000 or _raw_lower in _VULG_APPENDIX_NAMES:
            return _fetch_vulg_appendix_chapter(
                book_raw or _ID_TO_BOOK.get(book_id, ""), chapter
            )
    # Route CSL to local file if available, else fall through to bolls.life
    if slug == "CSL":
        result = _fetch_csl_chapter(book_raw or _ID_TO_BOOK.get(book_id, ""), chapter)
        if result is not None:
            if _ps_vstart is not None:
                result = [v for v in result if _ps_vstart <= v.get("verse", 0) <= _ps_vend]
            return result
        # fall through to bolls.life fetch below
    # Route Old English to local file
    if slug == "OE":
        return _fetch_oe_chapter(book_raw or _ID_TO_BOOK.get(book_id, ""), chapter)
    # Route Peshitta to local files
    if slug == "PESHITTA":
        return _fetch_peshitta_chapter(book_raw or _ID_TO_BOOK.get(book_id, ""), chapter)
    key = (slug, book_id, chapter)
    if key in _chapter_cache:
        return _chapter_cache[key]
    url = f"{_BASE_URL}/get-text/{slug}/{book_id}/{chapter}/"
    req = urllib.request.Request(url, headers={"User-Agent": "ScriptureBot/1.0"})
    last_err = None
    for attempt in range(3):
        try:
            if attempt > 0:
                import time
                time.sleep(1.5 * attempt)
            with urllib.request.urlopen(req, timeout=_TIMEOUT) as r:
                data = json.loads(r.read().decode("utf-8"))
            if not isinstance(data, list) or not data:
                return None
            if any(_WITHHELD.search(str(v.get("text", ""))) for v in data[:3]):
                return None                      # a notice that the translation is withheld, not verses
            if _ps_vstart is not None:
                data = [v for v in data if _ps_vstart <= v.get("verse", 0) <= _ps_vend]
            _chapter_cache[key] = data
            return data
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            last_err = e
            continue
        except Exception as e:
            last_err = e
            continue
    # All retries exhausted — log the error for debugging
    import logging
    logging.getLogger(__name__).warning(
        f"_fetch_chapter failed for {slug}/{book_id}/{chapter}: {last_err}"
    )
    return None


def _err(msg: str) -> dict:
    return {"found": False, "error": msg, "suggestions": []}


def get_translation(reference: str, translation: str) -> dict:
    """Look up a Bible passage in the given translation."""
    trans_key = translation.strip().lower()
    if trans_key in WITHDRAWN:
        return _err(WITHDRAWN[trans_key])
    if trans_key not in TRANSLATIONS:
        return _err(f"Unknown translation **{translation}**. Try `!translations` for the full list.")
    slug, display_name = TRANSLATIONS[trans_key]
    ref = reference.strip()

    # Cross-chapter range: "John 7:53-8:11"
    mc = re.match(r"^(.*?)\s+(\d+)[:\.](\d+)\s*[-–—]\s*(\d+)[:\.](\d+)$", ref, re.I)
    if mc:
        bid = _get_trans_book_id(slug, mc.group(1))
        if not bid:
            return _err(f"Unknown book: **{mc.group(1)}**")
        return _fetch_cross(slug, display_name, bid,
                            int(mc.group(2)), int(mc.group(3)),
                            int(mc.group(4)), int(mc.group(5)))

    # Multi-chapter range: "John 3-5"
    mr = re.match(r"^(.*?)\s+(\d+)\s*[-–—]\s*(\d+)$", ref, re.I)
    if mr:
        bid = _get_trans_book_id(slug, mr.group(1))
        c1, c2 = int(mr.group(2)), int(mr.group(3))
        if bid and c1 < c2 and c2 - c1 <= 10:
            return _fetch_multi(slug, display_name, bid, c1, c2)

    # Standard: "Book Chapter[:Verse[-End]]"
    m = re.match(r"^(.*?)\s+(\d+)(?:[:\.](\d+)(?:\s*[-–—]\s*(\d+))?)?$", ref, re.I)
    if not m:
        return _err(f"Could not parse: **{reference}**\nTry: `John 3:16 {translation.upper()}`")

    book_raw    = m.group(1).strip()
    chapter     = int(m.group(2))
    verse_start = int(m.group(3)) if m.group(3) else None
    verse_end   = int(m.group(4)) if m.group(4) else verse_start
    bid = _get_trans_book_id(slug, book_raw)
    if not bid:
        return _err(f"Unknown book: **{book_raw}**")

    canon = _get_canon_name(slug, bid, book_raw.title())
    verses = _fetch_chapter(slug, bid, chapter, book_raw)
    if verses is None:
        return _err(f"Could not retrieve **{canon} {chapter}** in **{slug}**.")

    if verse_start is None:
        texts = [f"**[{v['verse']}]** {_clean(v['text'])}" for v in verses]
        PAGE = 15
        pages = ["\n".join(texts[i:i+PAGE]) for i in range(0, len(texts), PAGE)]
        return {"found": True, "reference": f"{canon} {chapter} ({slug})",
                "text": "\n".join(texts), "source": display_name,
                "pages": pages if len(pages) > 1 else None}

    vm = {v["verse"]: _clean(v["text"]) for v in verses}
    texts = []
    for vn in range(verse_start, verse_end + 1):
        t = vm.get(vn)
        if t:
            texts.append(f"**[{vn}]** {t}" if verse_end != verse_start else t)
    if not texts:
        return _err(f"**{canon} {chapter}:{verse_start}** not found in **{slug}**.")
    v_label = str(verse_start) if verse_start == verse_end else f"{verse_start}–{verse_end}"
    return {"found": True, "reference": f"{canon} {chapter}:{v_label} ({slug})",
            "text": "\n".join(texts), "source": display_name}


def _fetch_cross(slug, display_name, bid, c1, v1, c2, v2) -> dict:
    canon = _ID_TO_BOOK.get(bid, f"Book {bid}")
    texts = []
    for cn in range(c1, c2 + 1):
        vs = _fetch_chapter(slug, bid, cn)
        if not vs:
            continue
        vm = {v["verse"]: _clean(v["text"]) for v in vs}
        vf = v1 if cn == c1 else 1
        vt = v2 if cn == c2 else max(vm)
        for vn in range(vf, vt + 1):
            t = vm.get(vn)
            if t:
                texts.append(f"**[{cn}:{vn}]** {t}")
    if not texts:
        return _err(f"No verses for **{canon} {c1}:{v1}–{c2}:{v2}** in **{slug}**.")
    return {"found": True, "reference": f"{canon} {c1}:{v1}–{c2}:{v2} ({slug})",
            "text": "\n".join(texts), "source": display_name}


def _fetch_multi(slug, display_name, bid, c1, c2) -> dict:
    canon = _ID_TO_BOOK.get(bid, f"Book {bid}")
    all_texts = []
    for cn in range(c1, c2 + 1):
        vs = _fetch_chapter(slug, bid, cn)
        if not vs:
            continue
        all_texts.append(f"**── Chapter {cn} ──**")
        for v in vs:
            all_texts.append(f"**[{v['verse']}]** {_clean(v['text'])}")
    if not all_texts:
        return _err(f"No chapters for **{canon} {c1}–{c2}** in **{slug}**.")
    PAGE = 15
    pages = ["\n".join(all_texts[i:i+PAGE]) for i in range(0, len(all_texts), PAGE)]
    return {"found": True, "reference": f"{canon} {c1}–{c2} ({slug})",
            "text": "\n".join(all_texts), "source": display_name,
            "pages": pages if len(pages) > 1 else None}


def get_parallel(reference: str, translations: list[str]) -> dict:
    """Fetch one verse (or short range) in multiple translations."""
    slugs = []
    for t in translations[:4]:
        key = t.strip().lower()
        if key in WITHDRAWN:
            return _err(WITHDRAWN[key])
        if key not in TRANSLATIONS:
            return _err(f"Unknown translation **{t}**. Try `!translations`.")
        slugs.append((TRANSLATIONS[key][0], TRANSLATIONS[key][1]))  # (slug, display)

    ref = reference.strip()
    m = re.match(r"^(.*?)\s+(\d+)(?:[:\.](\d+)(?:\s*[-–—]\s*(\d+))?)?$", ref, re.I)
    if not m:
        return _err(f"Could not parse: **{reference}**")

    book_raw    = m.group(1).strip()
    chapter     = int(m.group(2))
    verse_start = int(m.group(3)) if m.group(3) else None
    verse_end   = int(m.group(4)) if m.group(4) else verse_start

    bid = _get_trans_book_id(slugs[0][0], book_raw)
    if not bid:
        return _err(f"Unknown book: **{book_raw}**")
    if verse_start is None:
        return _err("Parallel display requires a verse number, e.g. `John 3:16 KJV ESV NASB`.")

    canon = _ID_TO_BOOK.get(bid, book_raw.title())
    results = []
    for slug, display_name in slugs:
        vs = _fetch_chapter(slug, bid, chapter)
        if vs is None:
            results.append((slug, display_name, f"*Could not retrieve {slug}*"))
            continue
        vm = {v["verse"]: _clean(v["text"]) for v in vs}
        if verse_end == verse_start:
            text = vm.get(verse_start, f"*v{verse_start} not found*")
        else:
            parts = [f"**[{vn}]** {vm[vn]}" for vn in range(verse_start, verse_end + 1) if vn in vm]
            text = "\n".join(parts) or "*not found*"
        results.append((slug, display_name, text))

    v_label = str(verse_start) if verse_start == verse_end else f"{verse_start}–{verse_end}"
    return {"found": True, "reference": f"{canon} {chapter}:{v_label}",
            "parallel": results, "source": " · ".join(s for s, _ in slugs)}


def get_random_verse(translation: str) -> dict:
    """Fetch a random verse in the given translation."""
    trans_key = translation.strip().lower()
    if trans_key in WITHDRAWN:
        return _err(WITHDRAWN[trans_key])
    if trans_key not in TRANSLATIONS:
        return _err(f"Unknown translation **{translation}**.")
    slug, display_name = TRANSLATIONS[trans_key]

    bid     = _random.randint(1, 66)
    chapter = _random.randint(1, _CHAPTER_COUNTS.get(bid, 1))
    vs = _fetch_chapter(slug, bid, chapter)
    if not vs:
        bid, chapter = 43, 3  # fallback: John 3
        vs = _fetch_chapter(slug, bid, chapter)
    if not vs:
        return _err(f"Could not reach bolls.life for **{slug}**.")

    v = _random.choice(vs)
    canon = _ID_TO_BOOK.get(bid, f"Book {bid}")
    return {"found": True, "reference": f"{canon} {chapter}:{v['verse']} ({slug})",
            "text": _clean(v["text"]), "source": display_name}


def search_translation(query: str, translation: str, page: int = 1, limit: int = 5) -> dict:
    """Search bolls.life for a word or phrase in a specific translation."""
    trans_key = translation.strip().lower()
    if trans_key in WITHDRAWN:
        return _err(WITHDRAWN[trans_key])
    if trans_key not in TRANSLATIONS:
        return _err(f"Unknown translation **{translation}**.")
    slug, display_name = TRANSLATIONS[trans_key]

    encoded = urllib.parse.quote_plus(query.strip())
    url = (f"{_BASE_URL}/v2/find/{slug}"
           f"?search={encoded}&match_case=false&match_whole=false"
           f"&page={page}&limit={limit}")
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "ScriptureBot/1.0"})
        with urllib.request.urlopen(req, timeout=_TIMEOUT) as r:
            data = json.loads(r.read().decode("utf-8"))
    except Exception as e:
        return _err(f"Could not reach bolls.life: {e}")

    total       = data.get("total", 0)
    total_pages = max(1, (total + limit - 1) // limit)
    results = []
    for item in data.get("results", []):
        bid  = item.get("book", 0)
        canon = _ID_TO_BOOK.get(bid, f"Book {bid}")
        results.append({
            "reference": f"{canon} {item.get('chapter')}:{item.get('verse')}",
            "text":      _clean(item.get("text", "")),
            "source":    display_name,
        })
    return {"found": True, "results": results, "total": total,
            "page": page, "total_pages": total_pages,
            "translation": slug, "display_name": display_name}


def list_translations() -> str:
    seen: set[str] = set()
    lines = []
    for slug, name in sorted(set(TRANSLATIONS.values())):
        if slug not in seen:
            seen.add(slug)
            lines.append(f"**{slug}** — {name}")
    return "\n".join(lines)
