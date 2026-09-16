"""
build_ancient.py — Fixed version
=================================
USAGE:
  python build_ancient.py --local-repo ./canonical-greekLit --all
  python build_ancient.py --web-only
"""

import json, re, sys, time, urllib.request, urllib.error
import xml.etree.ElementTree as ET
from pathlib import Path

CLASSICAL_DIR = Path("data/classical")
JEWISH_DIR    = Path("data/jewish")


# ── HTTP helper ────────────────────────────────────────────────────────────────

def fetch(url, delay=0.8):
    for attempt in range(4):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "ScriptureBot/1.0"})
            with urllib.request.urlopen(req, timeout=30) as r:
                data = r.read().decode("utf-8", errors="replace")
            time.sleep(delay)
            return data
        except urllib.error.HTTPError as e:
            if e.code == 429:
                wait = 60 * (attempt + 1)
                print(f"\n    Rate limited — waiting {wait}s..."); time.sleep(wait)
            elif e.code == 404:
                return None
            else:
                print(f"\n    HTTP {e.code}: {url}"); return None
        except Exception as ex:
            print(f"\n    Error: {ex}"); return None
    return None


def clean(text):
    return re.sub(r"\s+", " ", text).strip()


def save(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    kb = path.stat().st_size // 1024
    total = sum(len(v) for v in data["books"].values())
    print(f"    ✓ → {path} ({kb} KB, {len(data['books'])} books, {total} sections)")


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 1 — PERSEUS XML (Homer, Aristotle, Josephus)
# ══════════════════════════════════════════════════════════════════════════════

def get_text_perseus(elem):
    """Recursively get text, skipping notes/foreign/head."""
    SKIP = {"note", "bibl", "foreign", "head", "label", "lb", "term"}
    tag = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag
    if tag in SKIP:
        return ""
    parts = [elem.text or ""]
    for child in elem:
        parts.append(get_text_perseus(child))
        parts.append(child.tail or "")
    return "".join(parts)


def parse_perseus_xml(xml_text):
    """
    Parse Perseus TEI XML.
    Returns {book.section: {"1": text}}.

    Handles two structures:
      A) Josephus/Aristotle: div[subtype=book] > div[subtype=section] > p
      B) Homer: div[subtype=book] > div[subtype=card] > milestone[unit=line] + p
    """
    xml_text = re.sub(r' xmlns(?::\w+)?="[^"]*"', "", xml_text)
    xml_text = re.sub(r"<\?[^>]+\?>", "", xml_text)
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as e:
        print(f"\n    XML error: {e}"); return {}

    body = root.find(".//body")
    if body is None:
        body = root

    results = {}

    # Detect structure type
    # Try subtype-based structure first (Josephus, Aristotle)
    books = body.findall(".//div[@subtype='book']") + body.findall(".//div[@type='Book']")
    if not books:
        # Try div1
        books = body.findall(".//div1")

    for book_elem in books:
        book_n = book_elem.get("n", "1")
        try:
            book_num = int(book_n)
        except ValueError:
            book_num = book_n

        # Check if Homer-style (has cards with line milestones)
        cards = book_elem.findall(".//div[@subtype='card']")
        if cards:
            # Homer: group paragraphs by line milestone
            _parse_homer_book(book_elem, book_num, results)
        else:
            # Josephus/Aristotle: sections with paragraphs
            sections = book_elem.findall(".//div[@subtype='section']")
            if not sections:
                sections = book_elem.findall(".//div[@type='section']")
            if not sections:
                # Fallback: treat paragraphs as sections
                for i, p in enumerate(book_elem.findall(".//p"), 1):
                    t = clean(get_text_perseus(p))
                    if len(t) > 20:
                        results[f"{book_num}.{i}"] = {"1": t}
                continue

            for sect in sections:
                sect_n = sect.get("n", "")
                if not sect_n:
                    continue
                # Collect all paragraph text in this section
                paras = []
                for p in sect.findall(".//p"):
                    t = clean(get_text_perseus(p))
                    if t:
                        paras.append(t)
                if paras:
                    results[f"{book_num}.{sect_n}"] = {"1": " ".join(paras)}

    return results


def _parse_homer_book(book_elem, book_num, results):
    """
    Homer cards: each card groups lines. We extract by card boundary.
    Key: book.card_start_line
    """
    for card in book_elem.findall(".//div[@subtype='card']"):
        card_n = card.get("n", "")
        # Get all text from paragraphs in this card, skip line milestones
        parts = []
        for p in card.findall(".//p"):
            t = clean(get_text_perseus(p))
            if t:
                parts.append(t)
        text = " ".join(parts)
        if len(text) > 10 and card_n:
            results[f"{book_num}.{card_n}"] = {"1": text}


# Works lists
HOMER_WORKS = [
    ("Iliad",   "tlg0012", "tlg001", "perseus-eng4"),
    ("Odyssey", "tlg0012", "tlg002", "perseus-eng4"),
]

ARISTOTLE_PERSEUS_WORKS = [
    ("Eudemian Ethics", "tlg0086", "tlg009", "perseus-eng2"),
    ("Metaphysics",     "tlg0086", "tlg025", "perseus-eng2"),
    ("Economics",       "tlg0086", "tlg029", "perseus-eng2"),
    ("Poetics",         "tlg0086", "tlg034", "perseus-eng2"),
    ("Politics",        "tlg0086", "tlg035", "perseus-eng2"),
    ("Rhetoric",        "tlg0086", "tlg038", "perseus-eng2"),
]

JOSEPHUS_WORKS = [
    ("Jewish Antiquities", "tlg0526", "tlg001", "perseus-eng2"),
    ("Life",               "tlg0526", "tlg002", "perseus-eng2"),
    ("Against Apion",      "tlg0526", "tlg003", "perseus-eng2"),
    ("Jewish War",         "tlg0526", "tlg004", "perseus-eng2"),
]


def build_from_perseus(repo, works, out_path, source):
    all_books = {}
    for title, tg, tw, ver in works:
        path = repo / "data" / tg / tw / f"{tg}.{tw}.{ver}.xml"
        print(f"  {title}...", end=" ", flush=True)
        if not path.exists():
            print("NOT FOUND"); continue
        sections = parse_perseus_xml(path.read_text(encoding="utf-8"))
        if not sections:
            print("no sections"); continue
        all_books[title] = sections
        print(f"✓ {len(sections)}")
    if all_books:
        save(out_path, {"source": source, "books": all_books})


def build_homer(repo):
    print("\n── Homer ─────────────────────────────────────────────────────────────")
    build_from_perseus(repo, HOMER_WORKS, CLASSICAL_DIR / "homer.json",
        "Homer, trans. A. T. Murray (1924). Perseus Digital Library (CC-BY-SA).")


def build_aristotle_perseus(repo):
    print("\n── Aristotle (Perseus) ────────────────────────────────────────────────")
    build_from_perseus(repo, ARISTOTLE_PERSEUS_WORKS, CLASSICAL_DIR / "aristotle_perseus.json",
        "Aristotle, various translators. Perseus Digital Library (CC-BY-SA).")


def build_josephus(repo):
    print("\n── Josephus ───────────────────────────────────────────────────────────")
    build_from_perseus(repo, JOSEPHUS_WORKS, JEWISH_DIR / "josephus.json",
        "Josephus, trans. William Whiston (1737). Perseus Digital Library (CC-BY-SA).")


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 2 — MIT CLASSICS plain text
# Format varies:
#   Nic Ethics: "BOOK I\n\n1 \n\ntext"  (bare number, no dot)
#   Physics:    "BOOK I\n\nPart 1\n\ntext"
#   Plotinus:   "1. text\n continuation"
# ══════════════════════════════════════════════════════════════════════════════

MIT_BASE = "https://classics.mit.edu"

ARISTOTLE_MIT_WORKS = [
    ("Nicomachean Ethics",          "nicomachaen",      True),
    ("Physics",                     "physics",          True),
    ("On the Soul",                 "soul",             True),
    ("Categories",                  "categories",       False),
    ("On Interpretation",           "interpretation",   False),
    ("Prior Analytics",             "prior",            True),
    ("Posterior Analytics",         "posterior",        True),
    ("Topics",                      "topics",           True),
    ("On Sophistical Refutations",  "sophist_refut",    False),
    ("On the Heavens",              "heavens",          True),
    ("On Generation and Corruption","generat_corr",     True),
    ("Meteorology",                 "meteorology",      True),
    ("History of Animals",          "hist_anim",        True),
    ("On the Parts of Animals",     "parts_animals",    True),
    ("On the Motion of Animals",    "motion_anim",      False),
    ("On the Gait of Animals",      "gait_anim",        False),
    ("On the Generation of Animals","generat_anim",     True),
    ("On Memory and Reminiscence",  "memory",           False),
    ("On Dreams",                   "dreams",           False),
    ("On Sleep and Sleeplessness",  "sleep",            False),
    ("On Prophesying by Dreams",    "prophesy_dreams",  False),
    ("On Sense and the Sensible",   "sense",            False),
    ("On Longevity and Shortness of Life", "longev",   False),
    ("On Youth, Old Age, Life and Death",  "youth",    False),
    ("Athenian Constitution",       "athenian_const",   False),
    ("On the Virtues and Vices",    "virt_vices",       False),
]

ROMAN_MAP = {s:v for v,s in [
    (1000,'M'),(900,'CM'),(500,'D'),(400,'CD'),
    (100,'C'),(90,'XC'),(50,'L'),(40,'XL'),
    (10,'X'),(9,'IX'),(5,'V'),(4,'IV'),(1,'I')
]}

def roman_to_int(s):
    s = s.upper()
    result, i = 0, 0
    for sym, val in sorted(ROMAN_MAP.items(), key=lambda x:-x[1]):
        while s[i:i+len(sym)] == sym:
            result += val; i += len(sym)
    return result if result else None


def parse_mit_txt(text, has_books):
    """
    Parse MIT Internet Classics plain text.
    Handles:
      - "BOOK I / BOOK 1" headers
      - "Part N" or bare "N " section headers (Nic Ethics style)
      - Numbered sections like "1 " at start of line
    Returns {key: {"1": text}}
    """
    if not text:
        return {}

    # Strip header/footer boilerplate
    text = re.sub(r'^.*?-{20,}', '', text, flags=re.DOTALL)
    text = re.sub(r'-{20,}.*$', '', text, flags=re.DOTALL)

    results = {}
    current_book = None
    current_sect = None
    chunks = []

    def flush():
        if current_sect is not None and chunks:
            t = clean(" ".join(chunks))
            if len(t) > 20:
                key = f"{current_book}.{current_sect}" if (has_books and current_book) else str(current_sect)
                results[key] = {"1": t}

    book_re  = re.compile(r'^BOOK\s+([IVXLCDM\d]+)\s*$', re.IGNORECASE)
    part_re  = re.compile(r'^Part\s+(\d+)\s*$', re.IGNORECASE)
    sect_re  = re.compile(r'^SECTION\s+(\d+)\s*$', re.IGNORECASE)
    # Bare number: "1 " or "1" alone on a line (Nic Ethics style)
    bare_re  = re.compile(r'^(\d+)\s*$')

    for line in text.split('\n'):
        stripped = line.strip()
        bm = book_re.match(stripped)
        pm = part_re.match(stripped)
        sm = sect_re.match(stripped)
        nm = bare_re.match(stripped)

        if bm:
            flush(); chunks = []
            roman = bm.group(1).upper()
            current_book = roman_to_int(roman) or int(roman) if roman.isdigit() else roman
            current_sect = None
        elif pm:
            flush(); chunks = []; current_sect = int(pm.group(1))
        elif sm:
            flush(); chunks = []; current_sect = int(sm.group(1))
        elif nm and not chunks:
            # Bare number only if we haven't started collecting text yet
            # (avoids treating numbered list items as section breaks)
            flush(); chunks = []; current_sect = int(nm.group(1))
        else:
            if stripped and current_sect is not None:
                chunks.append(stripped)

    flush()
    return results


def build_aristotle_mit():
    print("\n── Aristotle (MIT Classics) ───────────────────────────────────────────")
    books = {}
    for title, stem, has_books in ARISTOTLE_MIT_WORKS:
        url = f"{MIT_BASE}/Aristotle/{stem}.mb.txt"
        print(f"  {title}...", end=" ", flush=True)
        text = fetch(url, delay=1.0)
        if text is None:
            print("not found"); continue
        sections = parse_mit_txt(text, has_books)
        if not sections:
            print("no sections"); continue
        books[title] = sections
        print(f"✓ {len(sections)}")
    if books:
        save(CLASSICAL_DIR / "aristotle_mit.json", {
            "source": "Aristotle, various translators. MIT Internet Classics Archive (public domain).",
            "books": books,
        })


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 3 — PLOTINUS (MIT plain text)
# Format: "THE FIRST ENNEAD\n\nFirst Tractate\n\n1. text\ncontinuation\n\n2. text..."
# ══════════════════════════════════════════════════════════════════════════════

ENNEAD_NUMS = {"FIRST":1,"SECOND":2,"THIRD":3,"FOURTH":4,"FIFTH":5,"SIXTH":6}
TRACT_NUMS  = {"First":1,"Second":2,"Third":3,"Fourth":4,"Fifth":5,
               "Sixth":6,"Seventh":7,"Eighth":8,"Ninth":9,"Tenth":10}


def build_plotinus():
    print("\n── Plotinus (MIT) ─────────────────────────────────────────────────────")
    print("  Fetching Six Enneads...", end=" ", flush=True)
    text = fetch(f"{MIT_BASE}/Plotinus/enneads.mb.txt", delay=1.0)
    if not text:
        print("failed"); return

    text = re.sub(r'^.*?-{20,}', '', text, flags=re.DOTALL)
    text = re.sub(r'-{20,}.*$', '', text, flags=re.DOTALL)

    results = {}
    ennead = tractate = section = None
    chunks = []

    def flush():
        if ennead and tractate and section and chunks:
            t = clean(" ".join(chunks))
            if len(t) > 20:
                results[f"{ennead}.{tractate}.{section}"] = {"1": t}

    ennead_re   = re.compile(r'^THE\s+(\w+)\s+ENNEAD\s*$')
    tractate_re = re.compile(r'^(\w+)\s+Tractate\s*$')
    # Sections: "1. text..." — number followed by dot at start of line
    section_re  = re.compile(r'^(\d+)\.\s+(.*)')

    for line in text.split('\n'):
        s = line.strip()
        em = ennead_re.match(s)
        tm = tractate_re.match(s)
        sm = section_re.match(s)

        if em:
            flush(); chunks = []; section = None
            ennead = ENNEAD_NUMS.get(em.group(1).upper())
            tractate = None
        elif tm:
            flush(); chunks = []; section = None
            tractate = TRACT_NUMS.get(tm.group(1))
        elif sm and ennead and tractate:
            flush(); chunks = []
            section = int(sm.group(1))
            rest = sm.group(2).strip()
            if rest:
                chunks.append(rest)
        elif s and section is not None and ennead and tractate:
            # Skip translator footnotes (lines starting with *)
            if not s.startswith('*'):
                chunks.append(s)

    flush()
    print(f"✓ {len(results)} sections")
    save(CLASSICAL_DIR / "plotinus.json", {
        "source": "Plotinus, The Six Enneads. Trans. Stephen MacKenna & B.S. Page. MIT Classics.",
        "books": {"Enneads": results},
    })


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 4 — IAMBLICHUS (Project Gutenberg plain text)
# And Life of Pythagoras from sacred-texts.com
# ══════════════════════════════════════════════════════════════════════════════

def parse_gutenberg_txt(text, book_marker="BOOK", section_marker=None):
    """
    Generic Gutenberg plain text parser.
    Returns {book.section: {"1": text}}
    Handles "BOOK I / SECTION I" or just numbered paragraphs.
    """
    if not text:
        return {}
    # Strip PG header/footer
    text = re.sub(r'\*\*\* START.*?\*\*\*', '', text, flags=re.DOTALL)
    text = re.sub(r'\*\*\* END.*', '', text, flags=re.DOTALL)
    text = re.sub(r'Transcriber.*?\n\n', '', text, flags=re.DOTALL)

    results = {}
    current_book = None
    current_sect = None
    chunks = []

    def flush():
        if chunks and current_sect is not None:
            t = clean(" ".join(chunks))
            if len(t) > 30:
                key = f"{current_book}.{current_sect}" if current_book else str(current_sect)
                results[key] = {"1": t}

    book_re = re.compile(rf'^{book_marker}\s+([IVXLCDM\d]+)\.?\s*$', re.IGNORECASE)
    # Numbered sections: "I.", "II.", "1.", etc. at line start
    roman_sect_re = re.compile(r'^([IVXLCDM]+)\.\s*$')
    num_sect_re   = re.compile(r'^(\d+)\.\s*$')

    for line in text.split('\n'):
        s = line.strip()
        bm = book_re.match(s)
        rsm = roman_sect_re.match(s)
        nsm = num_sect_re.match(s)

        if bm:
            flush(); chunks = []; current_sect = None
            n = bm.group(1)
            current_book = roman_to_int(n.upper()) or (int(n) if n.isdigit() else n)
        elif rsm:
            flush(); chunks = []
            current_sect = roman_to_int(rsm.group(1)) or rsm.group(1)
        elif nsm:
            flush(); chunks = []
            current_sect = int(nsm.group(1))
        elif s and current_sect is not None:
            chunks.append(s)

    flush()
    return results


def build_iamblichus():
    print("\n── Iamblichus (Gutenberg) ─────────────────────────────────────────────")
    books = {}

    # On the Mysteries — Gutenberg #72815
    print("  On the Mysteries...", end=" ", flush=True)
    text = fetch("https://www.gutenberg.org/cache/epub/72815/pg72815.txt", delay=1.0)
    if text:
        sections = parse_gutenberg_txt(text, book_marker="BOOK")
        if sections:
            books["On the Mysteries"] = sections
            print(f"✓ {len(sections)}")
        else:
            print("no sections")
    else:
        print("not found")

    # Life of Pythagoras — sacred-texts.com (Guthrie translation)
    print("  Life of Pythagoras...", end=" ", flush=True)
    text = fetch("https://sacred-texts.com/cla/iamb/lop/index.htm", delay=1.0)
    if text:
        # sacred-texts has individual chapter pages — fetch them
        chapter_urls = re.findall(r'href="(lop\d+\.htm)"', text)
        all_chunks = {}
        for cu in sorted(set(chapter_urls)):
            url = f"https://sacred-texts.com/cla/iamb/lop/{cu}"
            page = fetch(url, delay=0.8)
            if not page:
                continue
            # Strip HTML tags
            page_text = re.sub(r'<[^>]+>', ' ', page)
            page_text = re.sub(r'&[a-z]+;', ' ', page_text)
            # Find numbered sections
            secs = re.findall(r'(\d+)\.\s+(.{40,}?)(?=\s+\d+\.|$)', page_text, re.DOTALL)
            for n, body in secs:
                t = clean(body)
                if len(t) > 30:
                    all_chunks[str(n)] = {"1": t}
        if all_chunks:
            books["Life of Pythagoras"] = all_chunks
            print(f"✓ {len(all_chunks)}")
        else:
            print("no sections")
    else:
        print("not found")

    if books:
        save(CLASSICAL_DIR / "iamblichus.json", {
            "source": "Iamblichus. Trans. Thomas Taylor (1821). Gutenberg / sacred-texts.com (public domain).",
            "books": books,
        })


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 5 — PORPHYRY (Tertullian.org)
# ══════════════════════════════════════════════════════════════════════════════

PORPHYRY_WORKS = [
    ("On Abstinence", [
        ("1", "https://www.tertullian.org/fathers/porphyry_abstinence_01_book1.htm"),
        ("2", "https://www.tertullian.org/fathers/porphyry_abstinence_02_book2.htm"),
        ("3", "https://www.tertullian.org/fathers/porphyry_abstinence_03_book3.htm"),
        ("4", "https://www.tertullian.org/fathers/porphyry_abstinence_04_book4.htm"),
    ]),
    ("Life of Pythagoras", [
        ("1", "https://www.tertullian.org/fathers/porphyry_life_of_pythagoras_02_text.htm"),
    ]),
    ("On the Cave of the Nymphs", [
        ("1", "https://www.tertullian.org/fathers/porphyry_cave_nymphs_02_text.htm"),
    ]),
    ("Letter to Marcella", [
        ("1", "https://www.tertullian.org/fathers/porphyry_marcella_02_text.htm"),
    ]),
    ("Auxiliaries to the Intelligibles", [
        ("1", "https://www.tertullian.org/fathers/porphyry_auxiliaries_02_text.htm"),
    ]),
]


def parse_tertullian(html):
    if not html:
        return {}
    text = re.sub(r'<[^>]+>', ' ', html)
    for ent, rep in [('&nbsp;',' '),('&amp;','&'),('&#160;',' ')]:
        text = text.replace(ent, rep)
    text = re.sub(r'&\w+;', '', text)

    results = {}
    current_sec = None
    chunks = []

    def flush():
        if current_sec is not None and chunks:
            t = clean(" ".join(chunks))
            if len(t) > 20:
                results[str(current_sec)] = {"1": t}

    sec_re = re.compile(r'^\s*(\d+)\.\s+(.*)')
    for line in text.split('\n'):
        m = sec_re.match(line)
        if m:
            flush(); chunks = []
            current_sec = int(m.group(1))
            rest = m.group(2).strip()
            if rest:
                chunks.append(rest)
        else:
            s = line.strip()
            if s and current_sec is not None and len(s) > 3:
                chunks.append(s)
    flush()
    return results


def build_porphyry():
    print("\n── Porphyry (Tertullian.org) ──────────────────────────────────────────")
    all_books = {}
    for work_title, parts in PORPHYRY_WORKS:
        work_sects = {}
        for book_num, url in parts:
            print(f"  {work_title} §{book_num}...", end=" ", flush=True)
            html = fetch(url, delay=1.5)
            sects = parse_tertullian(html)
            if not sects:
                print("no sections"); continue
            if len(parts) > 1:
                for k, v in sects.items():
                    work_sects[f"{book_num}.{k}"] = v
            else:
                work_sects.update(sects)
            print(f"✓ {len(sects)}")
        if work_sects:
            all_books[work_title] = work_sects
    if all_books:
        save(CLASSICAL_DIR / "porphyry.json", {
            "source": "Porphyry. Trans. Thomas Taylor (1823). Tertullian.org (public domain).",
            "books": all_books,
        })


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 6 — PHILO (earlyjewishwritings.com)
# ══════════════════════════════════════════════════════════════════════════════

PHILO_WORKS = [
    ("On the Creation",                "book1"),
    ("Allegorical Interpretation I",   "book2"),
    ("Allegorical Interpretation II",  "book3"),
    ("Allegorical Interpretation III", "book4"),
    ("On the Cherubim",                "book5"),
    ("On the Birth of Abel",           "book6"),
    ("Worse Attacks the Better",       "book7"),
    ("On the Posterity of Cain",       "book8"),
    ("On the Giants",                  "book9"),
    ("On the Unchangeableness of God", "book10"),
    ("On Husbandry",                   "book11"),
    ("On Noah's Work as a Planter",    "book12"),
    ("On Drunkenness",                 "book13"),
    ("On Sobriety",                    "book14"),
    ("On the Confusion of Tongues",    "book15"),
    ("On the Migration of Abraham",    "book16"),
    ("Who is the Heir of Divine Things","book17"),
    ("On Mating",                      "book18"),
    ("On Flight and Finding",          "book19"),
    ("On the Change of Names",         "book20"),
    ("On Dreams",                      "book21"),
    ("On Abraham",                     "book22"),
    ("On Joseph",                      "book23"),
    ("On the Life of Moses I",         "book24"),
    ("On the Life of Moses II",        "book25"),
    ("The Decalogue",                  "book26"),
    ("The Special Laws I",             "book27"),
    ("The Special Laws II",            "book28"),
    ("The Special Laws III",           "book29"),
    ("The Special Laws IV",            "book30"),
    ("On the Virtues",                 "book31"),
    ("On Rewards and Punishments",     "book32"),
    ("Every Good Man is Free",         "book33"),
    ("On the Contemplative Life",      "book34"),
    ("On the Eternity of the World",   "book35"),
    ("Flaccus",                        "book36"),
    ("On the Embassy to Gaius",        "book40"),
    ("Questions on Genesis I",         "book41"),
    ("Questions on Genesis II",        "book42"),
    ("Questions on Genesis III",       "book43"),
]


def parse_philo(html):
    if not html:
        return {}
    text = re.sub(r'<[^>]+>', ' ', html)
    text = text.replace('&nbsp;',' ').replace('&amp;','&')
    text = re.sub(r'&\w+;', '', text)

    results = {}
    current_sec = None
    chunks = []

    def flush():
        if current_sec is not None and chunks:
            t = clean(" ".join(chunks))
            if len(t) > 20:
                results[str(current_sec)] = {"1": t}

    sec_re = re.compile(r'\((\d+)\)\s*(.*)')
    for line in text.split('\n'):
        m = sec_re.search(line)
        if m:
            flush(); chunks = []
            current_sec = int(m.group(1))
            rest = m.group(2).strip()
            if rest:
                chunks.append(rest)
        else:
            s = line.strip()
            if s and current_sec is not None and len(s) > 5:
                if not re.match(r'^[\*\{\[]', s):
                    chunks.append(s)
    flush()
    return results


def build_philo():
    print("\n── Philo (earlyjewishwritings.com) ────────────────────────────────────")
    all_books = {}
    for title, bid in PHILO_WORKS:
        url = f"https://www.earlyjewishwritings.com/text/philo/{bid}.html"
        print(f"  {title}...", end=" ", flush=True)
        html = fetch(url, delay=0.8)
        sects = parse_philo(html)
        if not sects:
            print("no sections"); continue
        all_books[title] = sects
        print(f"✓ {len(sects)}")
    if all_books:
        save(JEWISH_DIR / "philo.json", {
            "source": "Philo of Alexandria. Trans. C.D. Yonge (1854). earlyjewishwritings.com (public domain).",
            "books": all_books,
        })


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    args = sys.argv[1:]
    repo = None
    web_only = "--web-only" in args
    do_web   = "--all" in args or web_only

    if "--local-repo" in args:
        idx = args.index("--local-repo")
        if idx + 1 < len(args):
            repo = Path(args[idx + 1])
            if not repo.exists():
                print(f"Repo not found: {repo}"); sys.exit(1)

    if not repo and not web_only:
        print(__doc__); sys.exit(0)

    if repo:
        build_homer(repo)
        build_aristotle_perseus(repo)
        build_josephus(repo)

    if do_web or repo:
        build_aristotle_mit()
        build_plotinus()
        build_porphyry()
        build_iamblichus()
        build_philo()

    print("\n✓ Done.")
