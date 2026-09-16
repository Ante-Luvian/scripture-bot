#!/usr/bin/env python3
"""
build_data.py
─────────────
Downloads and parses all scripture texts into the JSON schema used by
scripture_lookup.py.  Run once before starting the bot:

    python build_data.py

All sources are public domain.  Re-run any time to refresh a corpus;
existing files are skipped unless you delete them first.

Sources
───────
  KJV (OT + NT)        bcbooks/scriptures-json (GitHub)
  KJV Apocrypha        ebible.org/eng-kjv  (per-chapter HTML)
  LDS Standard Works   bcbooks/scriptures-json (GitHub)
  Brenton extras       ebible.org  (3 & 4 Maccabees, Psalms of Solomon)
  Book of Enoch        pseudepigrapha.com  (R.H. Charles 1917, single page)
  Book of Jubilees     pseudepigrapha.com  (R.H. Charles 1902, 50 pages)
  Apostolic Fathers    earlychristianwritings.com  (Lightfoot translation)
"""

import json
import re
import time
import urllib.request
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data"
FETCH_DELAY = 0.4   # seconds between HTTP requests


# ════════════════════════════════════════════════════════════════════════════════
# Shared utilities
# ════════════════════════════════════════════════════════════════════════════════

def fetch(url: str, retries: int = 3) -> str:
    for attempt in range(retries):
        try:
            print(f"    GET {url}")
            req = urllib.request.Request(url, headers={"User-Agent": "ScriptureBot/1.0"})
            with urllib.request.urlopen(req, timeout=20) as r:
                raw = r.read()
            time.sleep(FETCH_DELAY)
            for enc in ("utf-8", "latin-1", "cp1252"):
                try:
                    return raw.decode(enc)
                except UnicodeDecodeError:
                    continue
            return raw.decode("utf-8", errors="replace")
        except Exception as e:
            if attempt < retries - 1:
                print(f"    ⚠  attempt {attempt+1} failed: {e} – retrying…")
                time.sleep(2 ** attempt)
            else:
                raise


def save(path: Path, payload: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    total = sum(len(vv) for bk in payload["books"].values() for vv in bk.values())
    print(f"  ✓  {path.name}  ({len(payload['books'])} books, {total} verses)")


def skip_if_exists(path: Path) -> bool:
    if path.exists():
        print(f"  ↷  {path.name} already exists – skipping")
        return True
    return False


def strip_tags(html: str) -> str:
    return re.sub(r"<[^>]+>", " ", html)


def normalise(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


# ════════════════════════════════════════════════════════════════════════════════
# 1.  KJV Canon   (getbible.net API – reliable public Bible API)
#
# Primary:  https://getbible.net/v2/kjv/{book_number}.json
#   Returns: { "book_nr": 1, "book_name": "Genesis", "chapters": {
#               "1": { "1": { "verse": "In the beginning..." }, ... } } }
#
# 66 books, numbered 1–66 in canonical order.
# ════════════════════════════════════════════════════════════════════════════════

# Canonical KJV book names in order (1–66)
_KJV_BOOK_NAMES = [
    "Genesis","Exodus","Leviticus","Numbers","Deuteronomy","Joshua","Judges",
    "Ruth","1 Samuel","2 Samuel","1 Kings","2 Kings","1 Chronicles","2 Chronicles",
    "Ezra","Nehemiah","Esther","Job","Psalms","Proverbs","Ecclesiastes",
    "Song of Solomon","Isaiah","Jeremiah","Lamentations","Ezekiel","Daniel",
    "Hosea","Joel","Amos","Obadiah","Jonah","Micah","Nahum","Habakkuk",
    "Zephaniah","Haggai","Zechariah","Malachi",
    "Matthew","Mark","Luke","John","Acts","Romans","1 Corinthians","2 Corinthians",
    "Galatians","Ephesians","Philippians","Colossians","1 Thessalonians",
    "2 Thessalonians","1 Timothy","2 Timothy","Titus","Philemon","Hebrews",
    "James","1 Peter","2 Peter","1 John","2 John","3 John","Jude","Revelation",
]


def _fetch_getbible_book(book_number: int, book_name: str) -> dict:
    """
    Fetch one book from api.getbible.net v2.
    URL:  https://api.getbible.net/v2/kjv/{book_number}.json
    The API returns chapters as either a dict or a list depending on version.
    """
    url = f"https://api.getbible.net/v2/kjv/{book_number}.json"
    raw = json.loads(fetch(url))

    chaps = {}

    # chapters may be a dict {"1": {...}} or a list [{...}, {...}]
    chapters_raw = raw.get("chapters", {})
    if isinstance(chapters_raw, dict):
        chapters_iter = chapters_raw.values()
    else:
        chapters_iter = chapters_raw  # it's already a list

    for chap_obj in chapters_iter:
        chap_num = str(chap_obj.get("chapter", chap_obj.get("chapter_nr", 1)))
        verses = {}

        verses_raw = chap_obj.get("verses", {})
        if isinstance(verses_raw, dict):
            verses_iter = verses_raw.values()
        else:
            verses_iter = verses_raw  # list

        for v_obj in verses_iter:
            v_num = str(v_obj.get("verse", v_obj.get("verse_nr", 1)))
            text = v_obj.get("text", "").strip()
            if text:
                verses[v_num] = text

        if verses:
            chaps[chap_num] = verses

    return chaps


def build_kjv_canon():
    path = DATA_DIR / "kjv" / "kjv_canon.json"
    if skip_if_exists(path):
        return
    books = {}
    for i, name in enumerate(_KJV_BOOK_NAMES, start=1):
        print(f"  {name}…")
        try:
            chaps = _fetch_getbible_book(i, name)
            if chaps:
                books[name] = chaps
            else:
                print(f"    ⚠  no chapters returned for {name}")
        except Exception as e:
            print(f"    ✗  {name}: {e}")
    save(path, {"source": "King James Version", "books": books})


# ════════════════════════════════════════════════════════════════════════════════
# 2.  KJV Apocrypha   (ebible.org per-chapter HTML)
#
# URL pattern:  https://ebible.org/eng-kjv/BOK##.htm
# Verse lines look like:   "1 In the beginning …"
# ════════════════════════════════════════════════════════════════════════════════

_KJV_APOC_BOOKS = {
    "1 Esdras":                  ("1ES", 9,  1),
    "2 Esdras":                  ("2ES", 16, 1),
    "Tobit":                     ("TOB", 14, 1),
    "Judith":                    ("JDT", 16, 1),
    "Additions to Esther":       ("ESG", 16, 10),  # chapters 10–16, code ESG
    "Wisdom of Solomon":         ("WIS", 19, 1),
    "Sirach":                    ("SIR", 51, 1),
    "Baruch":                    ("BAR", 6,  1),
    "Epistle of Jeremiah":       ("LJE", 1,  1),
    "Song of the Three Children":("S3Y", 1,  1),
    "Susanna":                   ("SUS", 1,  1),
    "Bel and the Dragon":        ("BEL", 1,  1),
    "Prayer of Manasseh":        ("MAN", 1,  1),
    "1 Maccabees":               ("1MA", 16, 1),
    "2 Maccabees":               ("2MA", 15, 1),
}

_VERSE_LINE_RE = re.compile(r"^\s*(\d+)\s+(.+)$")


def _parse_ebible_chapter(html: str) -> dict:
    """
    Extract verse dict {verse_num_str: text} from one ebible.org chapter page.

    eBible pages come in several formats:
    Format A: plain text lines "1 verse text here." (KJV apocrypha)
    Format B: all verses in one block separated by "N&#160;" markers
    Format C: inline verse numbers within paragraphs "1 Text 2 Text 3 Text"
              (Brenton pages like 3/4 Maccabees)
    """
    # Truncate at footer — but only after the main content.
    # Use body/article end markers, not domain names (which appear in nav links too).
    for footer_marker in ["Public Domain", "public domain", "This translation is in the Public"]:
        idx = html.find(footer_marker)
        if idx != -1:
            html = html[:idx]

    text = strip_tags(html)
    # Replace non-breaking spaces
    text = re.sub(r"&nbsp;", " ", text)

    # Format B: &#160; separated verses in raw HTML
    if "&#160;" in html or "&nbsp;" in html:
        chunks = re.split(r"(?<!\d)(\d+)(?:&#160;|&nbsp;)", html)
        verses = {}
        i = 1
        while i < len(chunks) - 1:
            vnum = chunks[i].strip()
            vtext = normalise(strip_tags(chunks[i + 1]))
            if vtext and vnum.isdigit() and 1 <= int(vnum) <= 200:
                verses[vnum] = vtext
            i += 2
        if verses:
            return verses

    # Format A: plain "N text" lines (one verse per line)
    verses = {}
    for line in text.splitlines():
        m = _VERSE_LINE_RE.match(line.strip())
        if m:
            vnum, vtext = m.group(1), normalise(m.group(2))
            if vtext and int(vnum) <= 200:
                verses[vnum] = vtext
    if verses:
        return verses

    # Format C: inline verse numbers — "1 Text. 2 Text. 3 Text."
    # Find the chapter number heading (a standalone digit on its own line or paragraph)
    # then split the following text on verse-number boundaries.
    # Find content after the chapter heading by looking for a standalone number
    # that matches the chapter, then grabbing everything after it.
    flat = normalise(text)
    # Strip the page title/nav (everything before the first standalone chapter digit)
    chap_heading = re.search(r"(?<!\d)\d+(?!\d)\s+\d+\s+\w", flat)
    if chap_heading:
        flat = flat[chap_heading.start():]
    # Now split on verse boundaries: digit not preceded by digit, followed by space+word
    parts = re.split(r"(?<!\d)(\d+)\s+(?=[A-Z])", flat)
    verses = {}
    i = 1
    while i < len(parts) - 1:
        vnum  = parts[i].strip()
        vtext = normalise(parts[i + 1]) if i + 1 < len(parts) else ""
        if vnum.isdigit() and 1 <= int(vnum) <= 200 and vtext and len(vtext) > 10:
            verses[vnum] = vtext
        i += 2
    return verses


def build_kjv_apocrypha():
    path = DATA_DIR / "kjv" / "kjv_apocrypha.json"
    if skip_if_exists(path):
        return
    books = {}
    base = "https://ebible.org/eng-kjv/"
    for book_name, (code, end_chapter, start_chapter) in _KJV_APOC_BOOKS.items():
        print(f"  {book_name}…")
        chaps = {}
        for c in range(start_chapter, end_chapter + 1):
            url = f"{base}{code}{c:02d}.htm"
            try:
                html = fetch(url)
                verses = _parse_ebible_chapter(html)
                if verses:
                    chaps[str(c)] = verses
            except Exception as e:
                print(f"    ✗  {url}: {e}")
        if chaps:
            books[book_name] = chaps
    save(path, {"source": "King James Version Apocrypha (eBible.org)", "books": books})


# ════════════════════════════════════════════════════════════════════════════════
# 3.  LDS Standard Works   (bcbooks/scriptures-json – reference edition)
#
# Reference schema: { "1 Nephi": { "1": { "1": "I, Nephi…" } } }
# Exactly matches our internal format — no transformation needed.
# ════════════════════════════════════════════════════════════════════════════════

_BCBOOKS_REF = "https://raw.githubusercontent.com/bcbooks/scriptures-json/master/reference/"


def build_lds():
    targets = [
        ("book_of_mormon.json",        "book-of-mormon-reference.json",        "LDS Book of Mormon",             "Book of Mormon"),
        ("doctrine_and_covenants.json", "doctrine-and-covenants-reference.json","LDS Doctrine and Covenants",     "Doctrine and Covenants"),
        ("pearl_of_great_price.json",  "pearl-of-great-price-reference.json",  "LDS Pearl of Great Price",       None),
    ]
    for fname, remote, source, fallback_name in targets:
        path = DATA_DIR / "lds" / fname
        if skip_if_exists(path):
            continue
        print(f"  {source}…")
        try:
            raw = json.loads(fetch(_BCBOOKS_REF + remote))

            # Detect structure:
            # Type A (Book of Mormon): { "1 Nephi": { "1": { "1": "text" } } }
            #   — top-level keys are book names (strings with letters)
            # Type B (D&C, POGP):      { "1": { "1": "text" } }
            #   — top-level keys are chapter/section numbers
            # Type C (POGP multi):     { "Moses": { "1": { "1": "text" } } }
            #   — same as Type A

            books = {}
            first_key = next(iter(raw), "")

            if first_key.lstrip("0123456789").strip() == "":
                # Type B — numeric top-level keys, wrap in a single book name
                book_name = fallback_name or source
                chaps = {}
                for chap_num, verses in raw.items():
                    if isinstance(verses, dict):
                        chaps[str(chap_num)] = {str(v): str(t) for v, t in verses.items()}
                if chaps:
                    books[book_name] = chaps
            else:
                # Type A/C — book-name top-level keys
                for book_name, chapters in raw.items():
                    if not isinstance(chapters, dict):
                        continue
                    chaps = {}
                    for chap_num, verses in chapters.items():
                        if isinstance(verses, dict):
                            chaps[str(chap_num)] = {str(v): str(t) for v, t in verses.items()}
                    if chaps:
                        books[book_name] = chaps

            save(path, {"source": source, "books": books})
        except Exception as e:
            print(f"    ✗  {e}")


# ════════════════════════════════════════════════════════════════════════════════
# 4.  Brenton Septuagint extras   (ebible.org)
#     3 Maccabees, 4 Maccabees, Psalms of Solomon
# ════════════════════════════════════════════════════════════════════════════════

_BRENTON_HTML = {
    "3 Maccabees": ("https://ebible.org/eng-Brenton/3MA{:02d}.htm", 7),
    "4 Maccabees": ("https://ebible.org/eng-Brenton/4MA{:02d}.htm", 18),
}

_PSS_URL = "https://wesley.nnu.edu/sermons-essays-books/noncanonical-literature/noncanonical-literature-ot-pseudepigrapha/the-psalms-of-solomon/"


def _parse_psalms_of_solomon(html: str) -> dict:
    """
    The entire text arrives as one long normalised string.

    Structure:
      "1 1 1 I cried ... 2 Suddenly ... 8 Their transgressions ...
       2. A Psalm Of Solomon. Concerning Jerusalem. 2 1 When the sinner..."

    Each psalm starts with "N 1 FirstWord" where N is the psalm number 1-18.
    Verses within a psalm are "N text" where N increments.
    Parenthetical verse numbers like "(9)" are alternate numbering — skip.
    Psalm titles like "2. A Psalm Of Solomon..." precede the "N 1" marker.
    """
    text = re.sub(r"&nbsp;", " ", html)
    text = strip_tags(text)
    text = normalise(text)

    # Remove psalm title patterns so they don't bleed into verse text.
    # Titles look like: "15. A Psalm. Of Solomon. With a Song."
    # or "6. In Hope. Of Solomon." or "3. A Psalm. Of Solomon. Concerning the righteous."
    # Strip anything matching "N. [title words]." that precedes "N 1 "
    text = re.sub(r"\d+\.\s+(?:[A-Z][^.]*\.?\s*)+(?=\d+\s+1\s+[A-Z])", "", text)

    # Also strip the footer/copyright at the end
    for marker in ["Edited and slightly adapted", "Copyright", "Wesley Center for Applied"]:
        idx = text.find(marker)
        if idx != -1:
            text = text[:idx]

    chaps = {}

    # Find all psalm start positions: "N 1 Word" where N is 1-18
    psalm_start_re = re.compile(r"(?<!\d)([1-9]|1[0-8])\s+1\s+(?=[A-Z])")
    matches = list(psalm_start_re.finditer(text))

    for idx, m in enumerate(matches):
        ps_num = m.group(1)
        start = m.end()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(text)

        # Trim back the end to before the next psalm's title/header
        block = text[start:end]

        # Remove trailing psalm title that leaked in (e.g. "15. A Psalm. Of Solomon...")
        block = re.sub(r"\s+\d+\.\s.*$", "", block).strip()

        verses = {}
        # verse 1 = everything before the first "2 " marker
        # Split on "N " where N is a verse number preceded by space or start
        # We handle both "N text" and "(N) text" patterns
        # First strip all parenthetical verse numbers "(N)" — they're alt numbering
        block_clean = re.sub(r"\(\d+\)\s*", "", block)

        verse_re = re.compile(r"(?<!\d)(\d+)\s+(?=[A-Z])")
        parts = verse_re.split(block_clean)
        # parts = [verse1_text, '2', verse2_text, '3', ...]

        v1 = normalise(parts[0])
        if v1 and len(v1) > 5:
            verses["1"] = v1

        i = 1
        while i < len(parts) - 1:
            vnum  = parts[i].strip()
            vtext = normalise(parts[i + 1]) if i + 1 < len(parts) else ""
            if vnum.isdigit() and 1 <= int(vnum) <= 200 and vtext and len(vtext) > 5:
                verses[vnum] = vtext
            i += 2

        if verses:
            chaps[ps_num] = verses

    return chaps


def build_brenton_extras():
    path = DATA_DIR / "brenton" / "brenton_extras.json"
    if skip_if_exists(path):
        return
    books = {}

    # 3 & 4 Maccabees from eBible per-chapter HTML
    for book_name, (url_tpl, num_chapters) in _BRENTON_HTML.items():
        print(f"  {book_name}…")
        chaps = {}
        for c in range(1, num_chapters + 1):
            url = url_tpl.format(c)
            try:
                html = fetch(url)
                verses = _parse_ebible_chapter(html)
                if verses:
                    chaps[str(c)] = verses
            except Exception as e:
                print(f"    ✗  {url}: {e}")
        if chaps:
            books[book_name] = chaps
        else:
            print(f"    ⚠  no verses parsed for {book_name}")

    # Psalms of Solomon from Wesley Center (single page, R.H. Charles translation)
    print("  Psalms of Solomon…")
    try:
        html = fetch(_PSS_URL)
        chaps = _parse_psalms_of_solomon(html)
        if chaps:
            books["Psalms of Solomon"] = chaps
            total = sum(len(v) for v in chaps.values())
            print(f"    {len(chaps)} psalms, {total} verses")
        else:
            print("    ⚠  no verses parsed for Psalms of Solomon")
    except Exception as e:
        print(f"    ✗  Psalms of Solomon: {e}")

    # Psalm 151 — Brenton, single eBible page, standard verse format
    print("  Psalm 151…")
    try:
        html = fetch("https://ebible.org/eng-Brenton/PSA151.htm")
        # Strip footnote references like [*Alex. text]
        html_clean = re.sub(r"\[\*[^\]]*\]", "", html)
        verses = _parse_ebible_chapter(html_clean)
        if verses:
            books["Psalm 151"] = {"151": verses}
            print(f"    {len(verses)} verses")
        else:
            print("    ⚠  no verses parsed")
    except Exception as e:
        print(f"    ✗  Psalm 151: {e}")

    # Psalms 152–155 — W. Wright translation, single page
    print("  Psalms 152–155…")
    try:
        html = fetch("https://summascriptura.thebookofenoch.info/html/Psalms_151-155_Wright.html")

        # Each psalm is in its own <td> cell.
        # The psalm number is wrapped in <em>151</em> (or <i> or <b>).
        # Verse 1 text follows immediately after the closing tag.
        # Subsequent verses have no space between number and text: "2My hands"
        # Cells end with a [{Top}](#top...) anchor which we strip first.

        cells = re.findall(r"<td[^>]*>(.*?)</td>", html, re.DOTALL | re.IGNORECASE)

        for cell in cells:
            # Remove the [{Top}] navigation link (appears as [{ or just {)
            cell_clean = re.sub(r"\[?\{[^}]*\}[^<]*", "", cell, flags=re.DOTALL)

            # Find psalm number strictly in an inline formatting tag
            ps_m = re.search(
                r"<(?:em|i|b|strong)[^>]*>\s*(15[1-5])\s*</(?:em|i|b|strong)>",
                cell_clean, re.IGNORECASE
            )
            if not ps_m:
                continue
            ps_num = ps_m.group(1)

            # Everything after the closing psalm-number tag is the verse content
            after = cell_clean[ps_m.end():]
            after = re.sub(r"&nbsp;", " ", after)
            text = normalise(strip_tags(after))

            if not text or len(text) < 10:
                continue

            # Verses are separated by "N " where N is a verse number.
            # Format: "verse1text 2 next verse text 3 next verse..."
            # Split on a digit (not preceded by digit) followed by a space
            # that appears to start a new verse. We use a lookahead to ensure
            # the digit is followed by a space and then a letter (real verse start).
            parts = re.split(r"(?<!\d)(\d+)(?=\s+[A-Za-z])", text)
            # parts = [verse1_text, '2', verse2_text, '3', verse3_text, ...]

            verses = {}
            v1 = normalise(parts[0])
            if v1 and len(v1) > 5:
                verses["1"] = v1
            i = 1
            while i < len(parts) - 1:
                vnum  = parts[i]
                vtext = normalise(parts[i + 1]) if i + 1 < len(parts) else ""
                if vnum.isdigit() and vtext and len(vtext) > 5:
                    verses[vnum] = vtext
                i += 2

            if verses:
                books[f"Psalm {ps_num}"] = {ps_num: verses}
                print(f"    Psalm {ps_num}: {len(verses)} verses")
            else:
                print(f"    ⚠  no verses for Psalm {ps_num}")

    except Exception as e:
        print(f"    ✗  Psalms 152–155: {e}")

    save(path, {"source": "Brenton Septuagint extras (eBible.org / Wesley Center / Wright)", "books": books})


# ════════════════════════════════════════════════════════════════════════════════
# 5.  Book of Enoch   (pseudepigrapha.com – single page, R.H. Charles 1917)
#
# Format:  "Chapter 1, I"  then  "1. The words of…"
# ════════════════════════════════════════════════════════════════════════════════

_ENOCH_CHAP_RE  = re.compile(r"Chapter\s+(\d+)", re.IGNORECASE)
_ENOCH_VERSE_RE = re.compile(r"^\s*(\d+)\.\s+(.+)$")


def build_enoch():
    path = DATA_DIR / "charles" / "book_of_enoch.json"
    if skip_if_exists(path):
        return
    print("  Book of Enoch (single page)…")
    html = fetch("https://www.pseudepigrapha.com/pseudepigrapha/enoch.htm")
    text = strip_tags(html)

    chaps: dict[str, dict] = {}
    current_chap = None

    for line in text.splitlines():
        line = line.strip()
        cm = _ENOCH_CHAP_RE.search(line)
        if cm:
            current_chap = cm.group(1)
            chaps.setdefault(current_chap, {})
            continue
        if current_chap:
            vm = _ENOCH_VERSE_RE.match(line)
            if vm:
                vtext = normalise(vm.group(2))
                if vtext:
                    chaps[current_chap][vm.group(1)] = vtext

    save(path, {
        "source": "Book of Enoch (R.H. Charles, 1917)",
        "books": {"Book of Enoch": chaps}
    })


# ════════════════════════════════════════════════════════════════════════════════
# 6.  Book of Jubilees   (pseudepigrapha.com – one page per chapter)
#
# Format:  "1. And it came to pass…"
# ════════════════════════════════════════════════════════════════════════════════

def build_jubilees():
    path = DATA_DIR / "charles" / "book_of_jubilees.json"
    if skip_if_exists(path):
        return
    print("  Book of Jubilees (50 chapters)…")
    chaps = {}
    failed = []

    for c in range(1, 51):
        url = f"https://www.pseudepigrapha.com/jubilees/{c}.htm"
        try:
            html = fetch(url)

            # Each verse is an unclosed <li> tag — split on <li> openings
            li_splits = re.split(r"<li[^>]*>", html, flags=re.IGNORECASE)
            if len(li_splits) > 2:
                verses = {}
                for i, item in enumerate(li_splits[1:], start=1):  # skip pre-list content
                    vtext = normalise(strip_tags(item))
                    if vtext and len(vtext) > 15:
                        verses[str(i)] = vtext
            else:
                # Fallback: split on ".-" sentence boundaries
                text = normalise(strip_tags(html))
                chap_marker = re.search(r"\[?Chapter\s+\d+\]?", text)
                if chap_marker:
                    text = text[chap_marker.end():]
                text = re.sub(r"^\s*\d+\.\s*", "", text.strip())
                raw_verses = re.split(r"\.-\s*", text)
                verses = {}
                for i, v in enumerate(raw_verses, start=1):
                    vtext = normalise(v)
                    if vtext and len(vtext) > 15:
                        verses[str(i)] = vtext

            if verses:
                chaps[str(c)] = verses
                print(f"    ch {c}: {len(verses)} verses")
            else:
                failed.append(c)
                print(f"    ✗  ch {c}: no verses parsed")
        except Exception as e:
            failed.append(c)
            print(f"    ✗  chapter {c}: {e}")

    if failed:
        print(f"  ⚠  Failed chapters: {failed}")

    if chaps:
        save(path, {
            "source": "Book of Jubilees (R.H. Charles, 1902)",
            "books": {"Book of Jubilees": chaps}
        })
    else:
        print("  ✗  No chapters saved for Jubilees — check network/URL")


# ════════════════════════════════════════════════════════════════════════════════
# 7.  Apostolic Fathers   (earlychristianwritings.com – Lightfoot translation)
#
# All texts (except Hermas) embed verse refs as "1:1 Text  1:2 Text" in <b>
# blocks.  We extract the bold blocks and regex-scan for chapter:verse.
#
# Hermas uses section headers ("Vision 1", "Mandate 1", "Similitude 1") with
# per-section 1:1 numbering.  We split it into three separate books.
# ════════════════════════════════════════════════════════════════════════════════

# Greedy scan: match "C:V text" up to the next "C:V" or end of string
_CV_RE = re.compile(r"(\d+):(\d+)\s+(.*?)(?=\s+\d+:\d+\s|\Z)", re.DOTALL)


def _parse_ecw_text(text: str) -> dict:
    flat = normalise(text)
    chaps: dict[str, dict] = {}
    for m in _CV_RE.finditer(flat):
        chap, verse = m.group(1), m.group(2)
        body = normalise(re.sub(r"[{}]", "", m.group(3)))
        if body:
            chaps.setdefault(chap, {})[verse] = body
    return chaps


def _fetch_ecw_bold(url: str) -> str:
    html = fetch(url)
    bold_blocks = re.findall(r"<b>(.*?)</b>", html, re.DOTALL | re.IGNORECASE)
    if bold_blocks:
        return " ".join(strip_tags(b) for b in bold_blocks)
    return strip_tags(html)


_AF_SIMPLE = [
    ("1 Clement",                      "1_clement.json",               "https://www.earlychristianwritings.com/text/1clement-lightfoot.html"),
    ("2 Clement",                      "2_clement.json",               "https://www.earlychristianwritings.com/text/2clement-lightfoot.html"),
    ("Ignatius to the Ephesians",      "ignatius_ephesians.json",      "https://www.earlychristianwritings.com/text/ignatius-ephesians-lightfoot.html"),
    ("Ignatius to the Magnesians",     "ignatius_magnesians.json",     "https://www.earlychristianwritings.com/text/ignatius-magnesians-lightfoot.html"),
    ("Ignatius to the Trallians",      "ignatius_trallians.json",      "https://www.earlychristianwritings.com/text/ignatius-trallians-lightfoot.html"),
    ("Ignatius to the Romans",         "ignatius_romans.json",         "https://www.earlychristianwritings.com/text/ignatius-romans-lightfoot.html"),
    ("Ignatius to the Philadelphians", "ignatius_philadelphians.json", "https://www.earlychristianwritings.com/text/ignatius-philadelphians-lightfoot.html"),
    ("Ignatius to the Smyrnaeans",     "ignatius_smyrnaeans.json",     "https://www.earlychristianwritings.com/text/ignatius-smyrnaeans-lightfoot.html"),
    ("Ignatius to Polycarp",           "ignatius_polycarp.json",       "https://www.earlychristianwritings.com/text/ignatius-polycarp-lightfoot.html"),
    ("Polycarp to the Philippians",    "polycarp_philippians.json",    "https://www.earlychristianwritings.com/text/polycarp-lightfoot.html"),
    ("Martyrdom of Polycarp",          "martyrdom_of_polycarp.json",   "https://www.earlychristianwritings.com/text/martyrdompolycarp-lightfoot.html"),
    ("Epistle of Barnabas",            "epistle_of_barnabas.json",     "https://www.earlychristianwritings.com/text/barnabas-lightfoot.html"),
    ("Didache",                        "didache.json",                 "https://www.earlychristianwritings.com/text/didache-lightfoot.html"),
    ("Shepherd of Hermas",             "shepherd_of_hermas.json",      "https://www.earlychristianwritings.com/text/shepherd-lightfoot.html"),
]


def _parse_hermas(text: str) -> dict:
    """
    Parse the Shepherd of Hermas using the bracketed global chapter numbers.

    Vision 1 uses plain  "1:1", "2:1" etc.  (chapters 1-4, no brackets)
    Vision 2+ uses       "1[5]:1", "2[6]:1" etc.  — the [N] is the global chapter.

    Rule: if a bracketed number is present, use it as the chapter number.
          Otherwise use the plain number before the colon.
    Both are then treated as a flat sequence:
      Hermas 1:1, Hermas 2:1 … Hermas 4:9, Hermas 5:1, Hermas 6:1 …
    """
    # Match  "optional_num[CHAP]:VERSE"  or plain  "CHAP:VERSE"
    # Followed by text up to the next such marker or end of string
    cv_re = re.compile(
        r"(?:\d+\[(\d+)\]|(?<!\[)(\d+)):(\d+)\s+(.*?)(?=\s+(?:\d+\[?\d*\]?:\d+)|\Z)",
        re.DOTALL
    )
    chaps = {}
    flat = normalise(text)
    for m in cv_re.finditer(flat):
        # group(1) = bracketed chapter, group(2) = plain chapter, group(3) = verse
        chap  = m.group(1) if m.group(1) else m.group(2)
        verse = m.group(3)
        body  = normalise(re.sub(r"[{}]", "", m.group(4)))
        if body:
            chaps.setdefault(chap, {})[verse] = body
    return chaps


def build_apostolic_fathers():
    source = "Apostolic Fathers (J.B. Lightfoot)"

    for canon_name, fname, url in _AF_SIMPLE:
        path = DATA_DIR / "apostolic_fathers" / fname
        if skip_if_exists(path):
            continue
        print(f"  {canon_name}…")
        try:
            html = fetch(url)
            bold_blocks = re.findall(r"<b>(.*?)</b>", html, re.DOTALL | re.IGNORECASE)
            if bold_blocks and len(" ".join(bold_blocks)) >= 500:
                text = " ".join(strip_tags(b) for b in bold_blocks)
            else:
                text = strip_tags(html)

            if canon_name == "Shepherd of Hermas":
                chaps = _parse_hermas(text)
            else:
                chaps = _parse_ecw_text(text)

            if not chaps:
                raise ValueError("No verses parsed – check the URL or page format")
            save(path, {"source": source, "books": {canon_name: chaps}})
        except Exception as e:
            print(f"    ✗  {e}")


# ════════════════════════════════════════════════════════════════════════════════
# 8.  Quran   (Pickthall translation, islam101.com)
#
# Format:  "001.001 verse text"  — sura.ayah both zero-padded to 3 digits.
# One plain-text file, no HTML.
# ════════════════════════════════════════════════════════════════════════════════

_QURAN_URL = "https://www.islam101.com/quran/quranPickthal/trans-pickthal.text"
_QURAN_RE  = re.compile(r"^(\d{3})\.(\d{3})\s+(.+)$")


def build_quran():
    path = DATA_DIR / "quran" / "quran_pickthall.json"
    if skip_if_exists(path):
        return
    print("  Quran (Pickthall)…")
    try:
        text = fetch(_QURAN_URL)
        chaps = {}          # sura_str → {ayah_str: text}
        current_lines = []  # buffer for multi-line verses
        current_sura = None
        current_ayah = None

        def flush():
            if current_sura and current_ayah and current_lines:
                chaps.setdefault(current_sura, {})[current_ayah] = normalise(" ".join(current_lines))

        for line in text.splitlines():
            m = _QURAN_RE.match(line.strip())
            if m:
                flush()
                current_sura = str(int(m.group(1)))   # strip leading zeros → "1", "2"…
                current_ayah = str(int(m.group(2)))
                current_lines = [m.group(3).strip()]
            elif current_ayah and line.strip():
                # Continuation of a wrapped verse
                current_lines.append(line.strip())

        flush()
        save(path, {"source": "The Glorious Quran (Pickthall)", "books": {"Quran": chaps}})
    except Exception as e:
        print(f"    ✗  {e}")


# ════════════════════════════════════════════════════════════════════════════════
# 9.  Golden Verses of Pythagoras   (sacred-texts.com)
#
# Single page, 71 verses numbered "1. First worship..."
# Treated as a single book "Golden Verses of Pythagoras" with one chapter ("1")
# and verses 1–71. So GVP 1:5 = verse 5.
# ════════════════════════════════════════════════════════════════════════════════

def build_golden_verses():
    path = DATA_DIR / "classical" / "golden_verses.json"
    if skip_if_exists(path):
        return
    try:
        html = fetch("https://sacred-texts.com/cla/gvp/gvp03.htm")
        text = normalise(strip_tags(html))
        # Verses: "1. First worship..." split on "N. " boundaries
        parts = re.split(r"(?<!\d)(\d+)\.\s+", text)
        verses = {}
        i = 1
        while i < len(parts) - 1:
            vnum = parts[i].strip()
            vtext = normalise(parts[i + 1])
            if vnum.isdigit() and 1 <= int(vnum) <= 71 and len(vtext) > 5:
                verses[vnum] = vtext
            i += 2
        if not verses:
            raise ValueError("No verses parsed")
        save(path, {
            "source": "Golden Verses of Pythagoras (Florence Firth, 1904)",
            "books": {"Golden Verses of Pythagoras": {"1": verses}}
        })
    except Exception as e:
        print(f"    ✗  {e}")


# ════════════════════════════════════════════════════════════════════════════════
# 10. Orphic Hymns   (theoi.com — Thomas Taylor 1792 translation)
#
# Two pages: OrphicHymns1.html (hymns 0–40) and OrphicHymns2.html (hymns 41–86)
# Each hymn has header "### [N] TITLE" and lines of poetry beneath.
# We store: book="Orphic Hymns", chapter=hymn_number, verse=line_number
# ════════════════════════════════════════════════════════════════════════════════

def _parse_orphic_page(html: str) -> dict:
    """Parse one theoi.com Orphic Hymns page. Returns {hymn_num: {line_num: text}}."""
    text = strip_tags(html)
    chaps = {}
    current_hymn = None
    line_num = 0

    hymn_re = re.compile(r"^\[(\d+)\]\s+[IVXLC]+\.\s+TO\s+", re.IGNORECASE)

    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        hm = hymn_re.match(line)
        if hm:
            current_hymn = hm.group(1)
            line_num = 0
            chaps[current_hymn] = {}
            continue
        # Skip the fumigation/incense line and section headers
        if current_hymn and not line.startswith("[") and len(line) > 10:
            # Skip theoi.com nav/footer lines
            if any(x in line for x in ["Classical Texts", "CONTENTS", "HYMNS", "Theoi Project"]):
                continue
            line_num += 1
            chaps[current_hymn][str(line_num)] = line
    return chaps


def build_orphic_hymns():
    path = DATA_DIR / "classical" / "orphic_hymns.json"
    if skip_if_exists(path):
        return
    try:
        chaps = {}
        for url in [
            "https://www.theoi.com/Text/OrphicHymns1.html",
            "https://www.theoi.com/Text/OrphicHymns2.html",
        ]:
            html = fetch(url)
            chaps.update(_parse_orphic_page(html))
        if not chaps:
            raise ValueError("No hymns parsed")
        save(path, {
            "source": "Orphic Hymns (Thomas Taylor, 1792)",
            "books": {"Orphic Hymns": chaps}
        })
    except Exception as e:
        print(f"    ✗  {e}")


# ════════════════════════════════════════════════════════════════════════════════
# 11. Homeric Hymns   (theoi.com — Evelyn-White 1914 translation)
#
# Three pages covering hymns 1–33.
# Each hymn has header "### HYMN N. TO DEITY" and lines of poetry.
# We store: book="Homeric Hymns", chapter=hymn_number, verse=line_group_number
#
# The actual page format (from inspection) is:
#   ### V. TO APHRODITE          ← hymn header (Roman numeral, no brackets)
#   [1] Muse, tell me...         ← numbered line groups inline in prose
#   [7] Yet there are three...
#   [33] Of these three...
#
# We treat each [N] block as one "verse" — the text from line-marker N up to
# the next line-marker (or end of hymn). Line-marker numbers are the canonical
# reference numbers scholars use (e.g. "Homeric Hymns 5:1" = Hymn 5, line 1).
# ════════════════════════════════════════════════════════════════════════════════

# Roman numeral → Arabic integer, up to XXXIII (33)
_ROMAN = {
    "I":1,"II":2,"III":3,"IV":4,"V":5,"VI":6,"VII":7,"VIII":8,"IX":9,"X":10,
    "XI":11,"XII":12,"XIII":13,"XIV":14,"XV":15,"XVI":16,"XVII":17,"XVIII":18,
    "XIX":19,"XX":20,"XXI":21,"XXII":22,"XXIII":23,"XXIV":24,"XXV":25,
    "XXVI":26,"XXVII":27,"XXVIII":28,"XXIX":29,"XXX":30,"XXXI":31,
    "XXXII":32,"XXXIII":33,
}

# Matches "### V. TO APHRODITE" or "## II. TO DEMETER" (any level heading)
_HH_HYMN_RE  = re.compile(
    r"^#{1,4}\s+([IVXLC]+)\.\s+TO\s+", re.IGNORECASE
)
# Matches an inline line-number like "[1]" or "[75]" at the start of a block
_HH_LINE_RE  = re.compile(r"^\[(\d+)\]\s*(.*)", re.DOTALL)
# Matches footnote refs like "[24]" that appear mid-sentence (no text after)
_HH_NOTE_RE  = re.compile(r"\[(\d+)\]$")


def _parse_homeric_page(markdown_text: str) -> dict:
    """
    Parse one theoi.com Homeric Hymns page delivered as markdown.
    Returns {hymn_num_str: {line_num_str: verse_text}}.

    Strategy: scan for hymn headers ("### V. TO APHRODITE"), then within each
    hymn collect text blocks.  Each block that begins "[N] text..." starts a
    new verse entry keyed by N.  Continuation lines are appended to the current
    verse.  Navigation / boilerplate lines are skipped.
    """
    chaps: dict = {}
    current_hymn: str | None = None
    current_line: str | None = None
    buf: list[str] = []

    _NAV = ("Classical Texts", "CONTENTS", "HYMNS", "Theoi Project",
            "theoi.com", "booklist", "Amazon", "Loeb", "University Press",
            "Evelyn-White", "dating and authorship", "Toggle navigation",
            "LIBRARY HOME", "GREEK MYTHOLOGY", "BESTIARY", "HEROES",
            "MISCELLANY", "GALLERY", ">>")

    def flush():
        if current_hymn and current_line and buf:
            text = normalise(" ".join(buf))
            # strip trailing footnote refs like [24]
            text = re.sub(r"\s*\[\d+\]\s*$", "", text).strip()
            if text:
                chaps[current_hymn][current_line] = text

    for raw_line in markdown_text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if any(nav in line for nav in _NAV):
            continue

        # ── Hymn header ──────────────────────────────────────────────────────
        hm = _HH_HYMN_RE.match(line)
        if hm:
            flush()
            roman_num = hm.group(1).upper()
            hymn_int = _ROMAN.get(roman_num)
            if hymn_int is None:
                continue
            current_hymn = str(hymn_int)
            current_line = None
            buf = []
            chaps.setdefault(current_hymn, {})
            continue

        if current_hymn is None:
            continue

        # ── Line-number block start ──────────────────────────────────────────
        lm = _HH_LINE_RE.match(line)
        if lm:
            flush()
            current_line = lm.group(1)
            rest = lm.group(2).strip()
            buf = [rest] if rest else []
            continue

        # ── Continuation text for current verse ─────────────────────────────
        if current_line and len(line) > 3:
            buf.append(line)

    flush()
    return chaps


def build_homeric_hymns():
    path = DATA_DIR / "classical" / "homeric_hymns.json"
    if skip_if_exists(path):
        return
    try:
        chaps = {}
        for url in [
            "https://www.theoi.com/Text/HomericHymns1.html",
            "https://www.theoi.com/Text/HomericHymns2.html",
            "https://www.theoi.com/Text/HomericHymns3.html",
        ]:
            # Request markdown extraction — theoi pages render cleanly this way
            html = fetch(url)
            # fetch() returns raw HTML; convert to plain text via strip_tags,
            # but we need to preserve the ### headers that markdown gives us.
            # Since fetch() returns HTML, manually build the markdown-style text:
            # find "### TITLE" patterns from the <h3> tags before stripping.
            import html as html_module
            # Decode HTML entities first (fixes &#8212; &amp; &nbsp; etc.)
            html_decoded = html_module.unescape(html)
            # Convert <h3> and <h4> to ### markers so _parse_homeric_page sees them
            html_decoded = re.sub(r"<h3[^>]*>", "\n### ", html_decoded, flags=re.IGNORECASE)
            html_decoded = re.sub(r"<h4[^>]*>", "\n#### ", html_decoded, flags=re.IGNORECASE)
            html_decoded = re.sub(r"</h[34]>", "\n", html_decoded, flags=re.IGNORECASE)
            # Convert <p> and <br> to newlines so line groups stay separate
            html_decoded = re.sub(r"<p[^>]*>|</p>|<br\s*/?>", "\n", html_decoded, flags=re.IGNORECASE)
            text = strip_tags(html_decoded)
            page_chaps = _parse_homeric_page(text)
            print(f"    {url.split('/')[-1]}: {len(page_chaps)} hymns")
            chaps.update(page_chaps)
        if not chaps:
            raise ValueError("No hymns parsed")
        # Renumber verses sequentially (1, 2, 3...) since source line numbers
        # are non-sequential (e.g. 1, 10, 17) which breaks verse lookup
        renumbered = {}
        for hymn_num, verses in chaps.items():
            sorted_verses = sorted(verses.items(), key=lambda x: int(x[0]))
            renumbered[hymn_num] = {str(i+1): text for i, (_, text) in enumerate(sorted_verses)}
        save(path, {
            "source": "Homeric Hymns (H.G. Evelyn-White, 1914)",
            "books": {"Homeric Hymns": renumbered}
        })
        print(f"    Total: {len(renumbered)} hymns saved")
    except Exception as e:
        print(f"    ✗  {e}")


# ════════════════════════════════════════════════════════════════════════════════
# 12. Corpus Hermeticum   (gnosis.org — G.R.S. Mead translation)
#
# One page per tractate. The tractates are at:
#   th203.html = CH I (Poemandres)
#   th205.html = CH II
#   th207.html = CH III
#   th208.html = CH IV
#   th209.html = CH V
#   th210.html = CH VI
#   th211.html = CH VII
#   th212.html = CH VIII
#   th213.html = CH IX
#   th214.html = CH X
#   th215.html = CH XI
#   th216.html = CH XII
#   th217.html = CH XIII
#   th218.html = CH XIV (Asclepius — separate)
#   th221.html = CH XVI
#   th222.html = CH XVII
#   th223.html = CH XVIII
# Paragraphs numbered "1. text 2. text" within each page.
# ════════════════════════════════════════════════════════════════════════════════

_CH_PAGES = {
    "1":  "th203.html",  # Poemandres
    "2":  "th205.html",
    "3":  "th207.html",
    "4":  "th208.html",
    "5":  "th209.html",
    "6":  "th210.html",
    "7":  "th211.html",
    "8":  "th212.html",
    "9":  "th213.html",
    "10": "th214.html",
    "11": "th215.html",
    "12": "th216.html",
    "13": "th217.html",
    "16": "th221.html",
    "17": "th222.html",
    "18": "th223.html",
}
_CH_BASE = "http://www.gnosis.org/library/grs-mead/TGH-v2/"
_PARA_RE = re.compile(r"(?<!\d)(\d+)\.\s+(.+?)(?=\s+\d+\.\s|\Z)", re.DOTALL)


def _parse_gnosis_paragraphs(html: str) -> dict:
    """Extract numbered paragraphs from a gnosis.org page."""
    # Strip page markers like "p. 59" which look like paragraph numbers
    html = re.sub(r"p\.\s*\d+", "", html)
    text = normalise(strip_tags(html))
    # Find content between the tractate title and the footnotes
    # Footnotes start with patterns like "fn_" or "p. NNN" markers
    verses = {}
    for m in _PARA_RE.finditer(text):
        vnum = m.group(1)
        vtext = normalise(re.sub(r"\[\d+\]", "", m.group(2)))  # strip footnote refs
        if vtext and len(vtext) > 10 and int(vnum) <= 200:
            verses[vnum] = vtext
    return verses


def build_corpus_hermeticum():
    path = DATA_DIR / "classical" / "corpus_hermeticum.json"
    if skip_if_exists(path):
        return
    chaps = {}
    for ch_num, page in _CH_PAGES.items():
        url = _CH_BASE + page
        try:
            html = fetch(url)
            verses = _parse_gnosis_paragraphs(html)
            if verses:
                chaps[ch_num] = verses
                print(f"    CH {ch_num}: {len(verses)} paragraphs")
            else:
                print(f"    ⚠  CH {ch_num}: no paragraphs parsed")
        except Exception as e:
            print(f"    ✗  CH {ch_num} ({url}): {e}")
    if chaps:
        save(path, {
            "source": "Corpus Hermeticum (G.R.S. Mead, 1906)",
            "books": {"Corpus Hermeticum": chaps}
        })


# ════════════════════════════════════════════════════════════════════════════════
# 13. Asclepius / The Perfect Sermon   (sacred-texts.com — G.R.S. Mead)
#
# The full Asclepius (The Perfect Sermon) is at sacred-texts.com/gno/th2/
# across 15 pages: th237.htm (Part I) through th251.htm (Part XV).
#
# Paragraph format on each page:
#   "1. [I. M.] [Trismegistus.] God, O Asclepius, hath brought thee..."
#   "2. [Tris.] The soul of every man..."
#   etc.
#
# We store: book="Asclepius", chapter=part_number (1–15), verse=para_number.
# This lets users say "Asclepius 3:2" = Part III, paragraph 2.
#
# Cleaning needed:
#   - HTML entities: &#8212; (em-dash), &nbsp; (space), &amp; etc.
#   - Page number markers like "p. 290" or "p. 291"
#   - Footnote references like "1" or "2" inline, and footnote blocks at bottom
#   - Section headers like "[I. M.]", "[Tris.]", "[Asc.]" — KEEP these as
#     they are part of the dialogue and help identify who is speaking
# ════════════════════════════════════════════════════════════════════════════════

_ASCLEPIUS_PAGES = {str(i): f"https://www.sacred-texts.com/gno/th2/th{236+i}.htm"
                   for i in range(1, 16)}  # th237→Part 1 ... th251→Part 15

_ST_BASE = "https://www.sacred-texts.com/gno/th2/"


def _clean_sacred_texts_html(html: str) -> str:
    """Decode entities and clean sacred-texts HTML down to bare paragraph text."""
    import html as html_mod

    # 1. Remove <script> and <style> blocks entirely (including their content)
    html = re.sub(r"<script\b[^>]*>.*?</script>", " ", html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r"<style\b[^>]*>.*?</style>",  " ", html, flags=re.DOTALL | re.IGNORECASE)

    # 2. Decode HTML entities (&#8212; → —, &nbsp; → space, &amp; → & etc.)
    text = html_mod.unescape(html)

    # 3. Strip remaining HTML tags
    text = strip_tags(text)

    # 4. Strip sacred-texts nav/footer boilerplate.
    # The footer appears between the last paragraph and the closing tags, but
    # on some pages it appears *within* a paragraph's text block (before the
    # closing </p>). It looks like:
    #   "Footnotes Next: Part II Sacred Texts | Gnosticism « Previous: ... »"
    # We excise it in-place (don't truncate) so that any paragraphs that follow
    # it (which do exist on multi-paragraph pages) are preserved.
    # The footer always ends with "»" or at a paragraph boundary.
    text = re.sub(
        r"Footnotes\s+Next:.*?(?:\u00bb|(?=\s*\d{1,2}\.\s))",
        " ",
        text,
        flags=re.DOTALL | re.IGNORECASE,
    )
    # Also strip the "Sacred Texts | ... « Previous: ... »" form
    text = re.sub(
        r"Sacred\s+Texts\s+\|.*?\u00bb",
        " ",
        text,
        flags=re.DOTALL | re.IGNORECASE,
    )

    # 5. Remove page number markers like "p. 290"
    text = re.sub(r"\bp\.\s*\d{2,4}\b", " ", text)

    # 6. Remove mid-sentence Mead footnote markers "· 1", "· 2" etc.
    text = re.sub(r"\s*·\s*\d+\b", "", text)

    # 7. Remove bare superscript footnote numbers.
    #    NOTE: We intentionally do NOT strip these here because the paragraph
    #    splitter needs the "N. " markers intact. The stripping is done per-
    #    paragraph inside _parse_asclepius_page after splitting.

    # 8. Remove footnote block lines at page bottom: "355:1 Some comment..."
    text = re.sub(r"^\s*\d{2,4}:\d+\s+.+$", "", text, flags=re.MULTILINE)

    # 9. Collapse whitespace
    return normalise(text)


def _parse_asclepius_page(raw_html: str) -> list:
    """
    Parse one sacred-texts Asclepius page into a flat list of tokens.
    Returns a list of ('chapter', int) or ('para', int, str) tokens, in order.

    The caller (build_asclepius) accumulates these tokens across pages to
    build the final chapter→paragraph structure.

    Chapter boundaries are standalone Roman numeral headings like:
        "III" or "IV" appearing on their own in the text.
    These appear as isolated Roman numerals — NOT inside brackets (those are
    Mead's own editorial section markers, which we ignore).

    Paragraph tokens are "N. text..." where N is 1–60.
    """
    _R2A = {
        "I":1,"II":2,"III":3,"IV":4,"V":5,"VI":6,"VII":7,"VIII":8,"IX":9,"X":10,
        "XI":11,"XII":12,"XIII":13,"XIV":14,"XV":15,"XVI":16,"XVII":17,"XVIII":18,
        "XIX":19,"XX":20,"XXI":21,"XXII":22,"XXIII":23,"XXIV":24,"XXV":25,
        "XXVI":26,"XXVII":27,"XXVIII":28,"XXIX":29,"XXX":30,"XXXI":31,"XXXII":32,
        "XXXIII":33,"XXXIV":34,"XXXV":35,"XXXVI":36,"XXXVII":37,"XXXVIII":38,
        "XXXIX":39,"XL":40,"XLI":41,
    }
    # Matches a STANDALONE Roman numeral on its own (possibly with surrounding
    # whitespace), NOT preceded/followed by brackets, letters, or digits.
    # This catches "III" as a chapter heading but not "[XIII. M.]" or "xxxii."
    standalone_roman_re = re.compile(
        r"(?<!\[)(?<!\w)(?<!\d)"
        r"\b(XC|XL|L?X{0,3}(?:IX|IV|V?I{0,3}))\b"
        r"(?!\.)(?!\w)(?!\])",
        re.IGNORECASE,
    )

    text = _clean_sacred_texts_html(raw_html)
    tokens = []

    # Split on paragraph number boundaries
    parts = re.split(r"(?<!\d)(\d{1,2})\.\s+", text)
    # parts = [preamble, '1', 'para1_text', '2', 'para2_text', ...]

    def scan_for_chapters(chunk: str) -> list:
        """Find any standalone Roman numeral chapter headings in a text chunk."""
        found = []
        for m in standalone_roman_re.finditer(chunk):
            roman = m.group(1).upper()
            arabic = _R2A.get(roman)
            if arabic:
                found.append(arabic)
        return found

    # Process preamble (text before first paragraph number)
    if parts:
        for ch in scan_for_chapters(parts[0]):
            tokens.append(('chapter', ch))

    i = 1
    while i < len(parts) - 1:
        vnum_str = parts[i].strip()
        vtext_raw = parts[i + 1]
        i += 2

        if not vnum_str.isdigit():
            continue
        vnum = int(vnum_str)
        if vnum < 1 or vnum > 60:
            continue

        # Check for a chapter heading that appears within this text chunk.
        # Chapter headings appear BETWEEN paragraphs, so the heading for
        # the NEXT chapter appears at the END of the current para's raw chunk
        # (after the paragraph text but before the next para number).
        # We emit the paragraph FIRST, then the chapter change, so that
        # the current paragraph stays in the current chapter.
        chapter_changes = scan_for_chapters(vtext_raw)

        vtext = normalise(vtext_raw)
        vtext = re.sub(r"\[(?:XC|XL|L?X{0,3}(?:IX|IV|V?I{0,3}))\.\s*M\..*?\]", "", vtext)
        vtext = re.sub(r"(?<!\d) ([1-9])(?=[ .,;:\u2014]|$)", " ", vtext)
        # Strip the chapter heading itself from the text (e.g. " IV " embedded)
        vtext = re.sub(
            r"\s+(?:XC|XL|L?X{0,3}(?:IX|IV|V?I{0,3}))\s*$", "", vtext, flags=re.IGNORECASE
        )
        vtext = normalise(vtext)

        if len(vtext) >= 15 and not re.match(r"^\d{3}", vtext):
            tokens.append(('para', vnum, vtext))

        # AFTER appending the paragraph, emit any chapter changes that follow it
        for ch in chapter_changes:
            tokens.append(('chapter', ch))

    return tokens


def build_asclepius():
    path = DATA_DIR / "classical" / "asclepius.json"
    if skip_if_exists(path):
        return

    all_chapters: dict[str, dict[str, str]] = {}
    current_chapter: int | None = None

    for page_i, url in _ASCLEPIUS_PAGES.items():
        try:
            html = fetch(url)
            tokens = _parse_asclepius_page(html)
            page_paras = 0
            page_chapters = set()

            for tok in tokens:
                if tok[0] == 'chapter':
                    current_chapter = tok[1]
                    page_chapters.add(current_chapter)
                elif tok[0] == 'para':
                    if current_chapter is None:
                        continue  # paragraphs before any chapter heading
                    _, vnum, vtext = tok
                    ch_str = str(current_chapter)
                    all_chapters.setdefault(ch_str, {})[str(vnum)] = vtext
                    page_paras += 1

            chaps_str = sorted(page_chapters) if page_chapters else ["(continuing)"]
            print(f"    Page {page_i}: chapters {chaps_str}, {page_paras} paragraphs")

        except Exception as e:
            print(f"    ✗  Page {page_i} ({url}): {e}")

    if not all_chapters:
        print("    ✗  No Asclepius content saved")
        return

    save(path, {
        "source": "Asclepius — The Perfect Sermon (G.R.S. Mead, 1906)",
        "books": {"Asclepius": all_chapters}
    })
    print(f"    Saved {len(all_chapters)} chapters total")


# ════════════════════════════════════════════════════════════════════════════════
# 14. Chaldaean Oracles   (esotericarchives.com — Westcott/Taylor/Cory edition)
#
# Single page with all ~198 oracles numbered sequentially.
# Source: https://www.esotericarchives.com/oracle/oraclez.htm
#
# The page has a long Preface and Introduction before the oracles begin.
# The oracles start after the heading "THE ORACLES OF ZOROASTER" or similar.
# Each oracle: "1. But God is He having the head of the Hawk. Z."
# Attribution suffixes like "Z.", "T.", "Z. or T.", "Proc. in Pl. Theol."
# are stripped — we keep only the oracle text itself.
# ════════════════════════════════════════════════════════════════════════════════

# Matches attribution suffixes at end of oracle text in all forms seen on the page:
# Strips trailing source attributions from oracle text. All forms seen on page:
#   "Z."  "T."  "Z. or T."
#   "Psell., 24;"  "- Psellus, 24;"  "Proc. in Pl. Theol."
#   "- Picus de Mirandula, Concl. Z."  (and bracketed follow-ons like "[Giovanni...]")
_COZ_ATTR_RE = re.compile(
    r"[\s\-]*(?:"
    r"Z\. or T\."                                                  # combined marker
    r"|[ZT]\."                                                     # simple Z. or T.
    r"|(?:-\s*)?(?:Psell|Pletho|Proc|Olymp|Lyd|Dam"               # scholar abbreviations
    r"|Synes|Jul|Niceph|Iambl|Stob|Proclus|Psellus|Picus"
    r"|Porphyr|Damasc|Hermias|Simplic|Simp|Anon)[^\n]{0,120}"     # with trailing citation
    r"|Tay(?:lor)?[^\n]{0,80}"                                     # Taylor references
    r")\s*(?:\[[^\]]{0,120}\])?\s*[;.]?\s*$",                     # optional [bracketed note]
    re.IGNORECASE,
)

# Identifies an entry as a section heading, footnote, or annotation — not oracle verse.
_COZ_ANNOTATION_RE = re.compile(
    r"^\s*(?:"
    # Source marker + editorial word (not oracle verse)
    r"(?:Z\. or T\.|[ZT]\.)\s+(?:Taylor|Psellus|Pletho|Proclus|Cory|Stanley|Note|IDEAS|PARTICULAR|MATTER|ORACLES|MAGICAL|SOUL|LIFE|MAN\b|Hyparxis|The\s)"
    # Scholar says/asserts
    r"|(?:Taylor|Psellus|Pletho|Proclus|Cory|Stanley|Simp(?:licius)?|The\s+Oracles\s+assert)\s+(?:says?|asserts?|remarks?|notes?)"
    # Bare editorial openers
    r"|Note[:\s]|See\s|Compare\s"
    r"|The\s+(?:word|term|phrase|passage|text|above|following)"
    # Section headings (may or may not be prefixed with Z./T.)
    r"|(?:Z\. or T\.|[ZT]\.\s+)?(?:ORACLES\s+FROM|IDEAS\b|PARTICULAR\s+SOULS|MATTER\b|MAGICAL\s+AND\s+PHILOSOPHICAL|FOUNTAINS,\s+PRINCIPLES)"
    # All-caps short entries are headings, not verse
    r"|[A-Z,\s]{10,}$"
    r")",
    re.IGNORECASE,
)


def build_chaldaean_oracles():
    path = DATA_DIR / "classical" / "chaldaean_oracles.json"
    if skip_if_exists(path):
        return
    try:
        import html as html_mod
        raw = fetch("https://www.esotericarchives.com/oracle/oraclez.htm")
        text = html_mod.unescape(raw)
        text = strip_tags(text)

        # ── Find where the actual oracles begin ──────────────────────────────
        oracle_start = text.find("1. But God is He")
        if oracle_start == -1:
            oracle_start = text.find("1. There is above")
        if oracle_start == -1:
            raise ValueError("Could not find oracle section start")
        text = text[oracle_start:]

        # ── Parse numbered entries ────────────────────────────────────────────
        # Use the oracle's own printed number as the key (oracle 25 = key "25").
        # If the same number appears twice (once as a false split on a citation
        # like "Pletho, 25." and once as the real oracle), the annotation filter
        # will skip the false one and the real oracle lands on the correct key.
        # If later sections restart at 1, those duplicates are just ignored since
        # the key already exists from the first (Zoroaster) section.
        parts = re.split(r"(?<!\w)(\d{1,3})\.\s+", text)
        all_verses: dict[str, str] = {}

        i = 1
        while i < len(parts) - 1:
            vnum_str = parts[i].strip()
            vtext_raw = parts[i + 1]
            i += 2
            if not vnum_str.isdigit():
                continue
            vnum = int(vnum_str)
            if vnum < 1 or vnum > 220:
                continue

            # Skip if this number is already stored (section restart or footnote dupe)
            if vnum_str in all_verses:
                continue

            vtext = normalise(vtext_raw)

            # Skip section headings and editorial annotations
            if _COZ_ANNOTATION_RE.match(vtext):
                continue

            # Strip trailing source attributions
            vtext = _COZ_ATTR_RE.sub("", vtext).strip()
            # Strip trailing bracketed page references like "[Giovanni Pico...]" or "[114]"
            vtext = re.sub(r"\s*\[[^\]]{0,150}\]\s*$", "", vtext).strip()
            # Strip any remaining trailing dash/punctuation dividers
            vtext = re.sub(r"[\s_\-]+$", "", vtext).strip()

            # Must be substantive oracle text
            if len(vtext) < 10:
                continue

            all_verses[vnum_str] = vtext

        if not all_verses:
            raise ValueError("No oracles parsed")
        print(f"    Parsed {len(all_verses)} oracles")
        # Each oracle number is its own chapter, with verse "1" containing the text
        chapters = {num: {"1": text} for num, text in all_verses.items()}
        save(path, {
            "source": "Chaldaean Oracles (Westcott ed., Taylor/Cory trans., 1895)",
            "books": {"Chaldaean Oracles": chapters}
        })
    except Exception as e:
        print(f"    ✗  {e}")


# ════════════════════════════════════════════════════════════════════════════════
# 15. Hesiod Theogony   (theoi.com — Evelyn-White 1914)
#
# Single page with 15 named sections numbered [1]–[15] via anchor links.
# Each section is a block of continuous prose/poetry.
# We store chapter=section_number, verse=1 (one text block per section).
# ════════════════════════════════════════════════════════════════════════════════

def build_hesiod_theogony():
    path = DATA_DIR / "classical" / "hesiod_theogony.json"
    if skip_if_exists(path):
        return
    try:
        import html as html_mod
        raw = fetch("https://www.theoi.com/Text/HesiodTheogony.html")
        text = html_mod.unescape(raw)

        KNOWN_SECTIONS = {
            "HYMN TO THE MUSES":        "1",
            "THE COSMOGONY":            "2",
            "THE CASTRATION OF URANUS": "3",
            "THE SPIRITS OF NIGHT":     "4",
            "THE SEA GODS":             "5",
            "THE BESTIARY":             "6",
            "THE TITAN GODS":           "7",
            "HYMN TO HECATE":           "8",
            "CHILDREN OF CRONUS":       "9",
            "PROMETHEUS":               "10",
            "THE TITANOMACHY":          "11",
            "COSMOGRAPHY":              "12",
            "TYPHOEUS":                 "13",
            "THE OLYMPIAN GODS":        "14",
            "OF GODDESSES AND MEN":     "15",
        }

        # Convert <p> and <br> to newlines before stripping tags
        text = re.sub(r'<br\s*/?>', '\n', text, flags=re.IGNORECASE)
        text = re.sub(r'<p[^>]*>', '\n', text, flags=re.IGNORECASE)
        text = re.sub(r'</p>', '\n', text, flags=re.IGNORECASE)

        # Split on <h3> tags for section headings
        parts = re.split(r'<h3[^>]*>(.*?)</h3>', text, flags=re.IGNORECASE | re.DOTALL)

        chapters = {}
        i = 1
        while i < len(parts) - 1:
            heading_raw = parts[i]
            body_raw    = parts[i + 1]
            i += 2

            heading = re.sub(r'<[^>]+>', '', heading_raw).strip().upper()
            chap_num = KNOWN_SECTIONS.get(heading)
            if chap_num is None:
                continue

            # Strip remaining tags
            body = re.sub(r'<[^>]+>', ' ', body_raw)
            body = html_mod.unescape(body)
            # Strip footnote refs like [1]
            body = re.sub(r'\[\d+\]', '', body)

            # Cut off at footnotes or end marker
            for cutoff_pat in [r'\n\s*1\.\s+The epithet', r'\n\s*1\.\s+Many', r'THE END', r'---']:
                m = re.search(cutoff_pat, body)
                if m:
                    body = body[:m.start()]
                    break

            # Split into lines, strip each, drop empties and nav garbage
            raw_lines = body.split('\n')
            verses = {}
            verse_num = 1
            for raw_line in raw_lines:
                line = raw_line.strip()
                # Skip empty, short nav lines, or lines with theoi.com URLs
                if not line or len(line) < 5:
                    continue
                if any(skip in line for skip in ['theoi.com', 'Theoi Project', 'SEARCH', 'LIBRARY', 'Toggle']):
                    continue
                verses[str(verse_num)] = line
                verse_num += 1

            if verses:
                chapters[chap_num] = verses

        if len(chapters) < 10:
            raise ValueError(f"Only parsed {len(chapters)} sections (expected 15)")

        total_verses = sum(len(v) for v in chapters.values())
        print(f"    Parsed {len(chapters)} sections, {total_verses} lines total")
        save(path, {
            "source": "Hesiod, Theogony (H.G. Evelyn-White, 1914)",
            "books": {"Theogony": chapters}
        })
    except Exception as e:
        print(f"    ✗  {e}")


# ════════════════════════════════════════════════════════════════════════════════
# 16. Gathas   (zoroastrian.org.uk — Mobed Firouz Azargoshasb translation)
#
# Single page with 17 songs (Songs 1–17 = Yasnas 28–34, 43–53).
# Each song has anchor #S1–#S17.
# Each verse is labelled "Verse N:" followed by the text.
# We store: book="Gathas", chapter=song_number (1–17), verse=verse_number
# ════════════════════════════════════════════════════════════════════════════════

def build_gathas():
    path = DATA_DIR / "classical" / "gathas.json"
    if skip_if_exists(path):
        return
    try:
        html = fetch("http://zoroastrian.org.uk/heritage/gathas/gathas-firouz.html")
        text = strip_tags(html)

        chaps = {}
        current_song = None
        current_verse = None
        buf = []

        def flush():
            if current_song and current_verse and buf:
                chaps.setdefault(current_song, {})[current_verse] = normalise(" ".join(buf))

        song_re  = re.compile(r"^Song\s+(\d+)\s*[-–]\s*Yasna", re.IGNORECASE)
        verse_re = re.compile(r"^Verse\s+(\d+)\s*:", re.IGNORECASE)

        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            sm = song_re.match(line)
            if sm:
                flush()
                current_song = sm.group(1)
                current_verse = None
                buf = []
                continue
            vm = verse_re.match(line)
            if vm:
                flush()
                current_verse = vm.group(1)
                # Text may start on the same line after "Verse N:"
                rest = line[vm.end():].strip()
                buf = [rest] if rest else []
                continue
            if current_verse and line:
                buf.append(line)

        flush()
        if not chaps:
            raise ValueError("No songs parsed")
        save(path, {
            "source": "Gathas — Holy Songs of Zarathushtra (Mobed Firouz Azargoshasb)",
            "books": {"Gathas": chaps}
        })
    except Exception as e:
        print(f"    ✗  {e}")





# ════════════════════════════════════════════════════════════════════════════════
# 17. Delphi — Delphic Maxims + Oracular Statements
#
# Maxims: 147 maxims from hellenion.org (trans. Melissa Gold, Greek from
#   Al. N. Oikonomides, Classical Bulletin 63, 1987).
#   Each maxim = chapter N, verse "1" (English), verse "2" (Greek + transliteration)
#
# Oracles: 23 prominent oracle texts from Wikipedia,
#   "List of oracular statements from Delphi".
#   Each oracle = chapter N, verse "1" (oracle text), verse "2" (context)
#
# Citation: Delphi Maxims 8  →  maxim 8 ("Know yourself")
#           Delphi Oracles 8  →  oracle to Croesus
# ════════════════════════════════════════════════════════════════════════════════

# Hardcoded oracular statements (from Wikipedia, public domain context summaries
# with oracle texts drawn from Herodotus, Thucydides, Plutarch etc.)
_DELPHI_ORACLES = [
    (1,
     "You have come to my rich temple, Lycurgus, a man dear to Zeus and to all who have Olympian homes. I am in doubt whether to pronounce you man or god, but I think rather you are a god, Lycurgus.",
     "To Lycurgus of Sparta, fl. 8th century BC (Herodotus, Histories A.65)"),
    (2,
     "Love of money and nothing else will ruin Sparta.",
     "To Lycurgus of Sparta, on the introduction of iron coinage (Plutarch, Diodorus)"),
    (3,
     "He should found a city in Libya.",
     "To the king of Thera, 630 BC"),
    (4,
     "If they would make a settlement at Cyrene in Libya, things would go better with them.",
     "To the Therans, on the drought, 630 BC"),
    (5,
     "Know you better than I, fair Libya abounding in fleeces? Better the stranger than he who has trod it? Oh! Clever Therans!",
     "To the Therans, third consultation, 630 BC"),
    (6,
     "First sacrifice to the warriors who once had their home in this island, whom now the rolling plain of fair Asopia covers, laid in the tombs of heroes with their faces turned to the sunset.",
     "To Solon of Athens, on capturing Salamis from Megara, 594 BC"),
    (7,
     "Seat yourself now amidships, for you are the pilot of Athens. Grasp the helm fast in your hands; you have many allies in your city.",
     "To Solon of Athens, on his constitutional reforms, 594 BC"),
    (8,
     "I know the number of the sand and the measure of the sea; I understand the speech of the dumb and hear the voiceless. The smell has come to my sense of a hard-shelled tortoise being cooked with a lamb's flesh in a bronze pot: bronze is the cauldron underneath, and bronze is the lid.",
     "To Croesus of Lydia, in the trial of oracles, 560 BC (Herodotus)"),
    (9,
     "If Croesus made war on the Persians, he would destroy a mighty empire.",
     "To Croesus of Lydia, on making war against Persia, 560 BC — the empire destroyed was his own"),
    (10,
     "Whenever a mule shall become sovereign king of the Medians, then, Lydian Delicate-Foot, flee by the stone-strewn Hermus, flee, and think not to stand fast, nor shame to be chicken-hearted.",
     "To Croesus of Lydia, on the duration of his monarchy, 560 BC — Cyrus the Great, half-Mede half-Persian, was the 'mule'"),
    (11,
     "You ask me for Arcadia? You ask too much; I grant it not. There are many men in Arcadia, eaters of acorns, who will hinder you. But I grudge you not. I will give you Tegea to beat with your feet in dancing, and its fair plain to measure with a rope.",
     "To the Spartans, on invading Arcadia (Herodotus 1.66)"),
    (12,
     "When the Prytanies' seat shines white in the island of Siphnos, white-browed all the forum — need then of a true seer's wisdom — danger will threat from a wooden boat, and a herald in scarlet.",
     "To the Siphnians, at the founding of the Siphnian Treasury (Herodotus)"),
    (13,
     "Now your statues are standing and pouring sweat. They shiver with dread. The black blood drips from the highest rooftops. They have seen the necessity of evil. Get out, get out of my sanctum and drown your spirits in woe.",
     "To the Athenians, on the Persian invasion of Xerxes, 480 BC — first consultation"),
    (14,
     "A wall of wood alone shall be uncaptured, a boon to you and your children.",
     "To the Athenians, second consultation on Xerxes, 480 BC — interpreted by Themistocles as the Athenian navy"),
    (15,
     "Await not in quiet the coming of the horses, the marching feet, the armed host upon the land. Slip away. Turn your back. You will meet in battle anyway. O holy Salamis, you will be the death of many a woman's son between the seedtime and the harvest of the grain.",
     "To the Athenians, third consultation on Xerxes, 480 BC — fulfilled at the Battle of Salamis"),
    (16,
     "The strength of bulls or lions cannot stop the foe. No, he will not leave off, I say, until he tears the city or the king limb from limb.",
     "To the Spartans, on the Persian invasion, 480 BC"),
    (17,
     "Hear your fate, O dwellers in Sparta of the wide spaces; either your famed, great town must be sacked by Perseus' sons, or, if that be not, the whole land of Lacedaemon shall mourn the death of a king of the house of Heracles, for not the strength of lions or of bulls shall hold him, strength against strength; for he has the power of Zeus, and will not be checked until one of these two he has consumed.",
     "To the Spartans, on the Persian invasion (Herodotus version), 480 BC — fulfilled at Thermopylae by Leonidas"),
    (18,
     "Pray to the Winds. They will prove to be mighty allies of Greece.",
     "To the Delphians, on defeating Persia, 480 BC"),
    (19,
     "Sophocles is wise, Euripides is wiser, but of all men Socrates is wisest.",
     "To Chaerephon, on behalf of Socrates, c. 440 BC"),
    (20,
     "None.",
     "To Chaerephon, on whether any man is wiser than Socrates, c. 440 BC — Socrates interpreted this as meaning he alone knew his own ignorance"),
    (21,
     "Also the dragon (serpent), earthborn, in craftiness coming behind thee.",
     "To Lysander of Sparta, warning, 403 BC — fulfilled 395 BC when he was slain from behind by a warrior with a serpent on his shield"),
    (22,
     "Sure though thy feet, proud Sparta, have a care, a lame king's reign may see thee trip — Beware! Troubles unlooked for long shall vex thy shore, and rolling Time his tide of carnage pour.",
     "To Sparta, 401 BC — fulfilled under Agesilaus II, the lame king"),
    (23,
     "If Pyrrhus passes over into Italy he will conquer the Romans. If Pyrrhus passes over into Italy the Romans will conquer him.",
     "To Pyrrhus of Epirus, on invading Italy, 280 BC — deliberately ambiguous; both readings are grammatically valid"),
]


def build_delphi():
    path = DATA_DIR / "classical" / "delphi.json"
    if skip_if_exists(path):
        return

    books = {}

    # ── Delphic Maxims ────────────────────────────────────────────────────────
    try:
        html = fetch("https://www.hellenion.org/essays-on-hellenic-polytheism/delphic-maxims/")
        import html as html_mod
        text = html_mod.unescape(html)
        text = re.sub(r"<[^>]+>", " ", text)
        text = normalise(text)

        # Each entry looks like: "N greek transliteration English translation"
        # The bold number starts each maxim. We split on word-boundary N followed
        # by a Greek character run.
        # Strategy: find "N " patterns and capture everything up to next number.
        # The page structure after stripping tags is:
        # "... 1 ἕπου θεῷ epou theo Follow Zeus; follow divinity 2 νόμῳ ..."
        parts = re.split(r'(?<!\d)(\d{1,3})\s+(?=[ἀ-ωΑ-Ωα-ω\u0370-\u03FF])', text)
        # parts = [preamble, '1', 'ἕπου θεῷ epou theo Follow Zeus...', '2', ...]

        maxims = {}
        i = 1
        while i < len(parts) - 1:
            num_str = parts[i].strip()
            content = parts[i + 1]
            i += 2
            if not num_str.isdigit():
                continue
            num = int(num_str)
            if num < 1 or num > 147:
                continue

            content = normalise(content)
            # Split into Greek+transliteration vs English translation
            # Greek characters come first, then transliteration (Latin), then English
            # Find where the English starts — after the transliteration line
            # Transliteration is Latin chars only; English starts with a capital
            # and contains spaces with longer words
            # Simple approach: split on the first sentence that contains no Greek
            greek_end = 0
            for m in re.finditer(r'[ἀ-ωΑ-Ωα-ω\u0370-\u03FF]', content):
                greek_end = m.end()

            if greek_end > 0:
                greek_part = normalise(content[:greek_end + 50]).strip()
                # Find end of transliteration (last Latin word before English begins)
                # English translation starts after transliteration
                # Look for a capital letter starting a longer English phrase
                en_match = re.search(r'\s([A-Z][a-z].*)', content[greek_end:])
                if en_match:
                    english = normalise(en_match.group(1))
                    greek_trans = normalise(content[:greek_end + en_match.start() + greek_end].split(en_match.group(1))[0])
                else:
                    english = normalise(content[greek_end:])
                    greek_trans = normalise(content[:greek_end])
            else:
                english = content
                greek_trans = ""

            if len(english) < 3:
                continue

            maxims[str(num)] = {
                "1": english,
                "2": greek_trans,
            }

        if len(maxims) >= 100:
            books["Delphic Maxims"] = maxims
            print(f"    Maxims: {len(maxims)} parsed")
        else:
            print(f"    ⚠  Only {len(maxims)} maxims parsed — check parser")

    except Exception as e:
        print(f"    ✗  Maxims: {e}")

    # ── Delphic Oracles ───────────────────────────────────────────────────────
    oracles = {}
    for num, text, context in _DELPHI_ORACLES:
        oracles[str(num)] = {
            "1": text,
            "2": context,
        }
    books["Delphic Oracles"] = oracles
    print(f"    Oracles: {len(oracles)} hardcoded")

    if not books:
        print("    ✗  Nothing saved")
        return

    save(path, {
        "source": "Delphi — Maxims (trans. Melissa Gold, Hellenion) & Oracular Statements (Wikipedia/Herodotus/Plutarch)",
        "books": books,
    })



#
# 36 sermon pages, each at:
#   https://en.uesp.net/wiki/Morrowind:36_Lessons_of_Vivec,_Sermon_{N}
#
# Each sermon is stored as chapter N, verse "1" (whole sermon, no sub-verses).
# Citation: Vivec 1  →  Sermon 1 in full.
#
# Licensed under Attribution-ShareAlike 2.5.
# Out-of-game author: Michael Kirkbride. In-game author: Vivec.
# ════════════════════════════════════════════════════════════════════════════════

_VIVEC_BASE = "https://en.uesp.net/wiki/Lore:36_Lessons_of_Vivec,_Sermon_{n}"

# Nav boilerplate that UESP wraps around each book page — handled in parser below.


def _parse_vivec_sermon(raw_html: str, sermon_num: int) -> str:
    """
    Extract just the sermon body text from a UESP wiki page.
    Strips: sidebar metadata, nav boxes, book title/description, footer nav.
    """
    import html as html_mod

    text = html_mod.unescape(raw_html)

    # Extract only the mw-parser-output content
    m = re.search(
        r'class="mw-parser-output">(.*?)(?:class="printfooter"|id="catlinks")',
        text, re.DOTALL
    )
    if m:
        text = m.group(1)

    # Remove infobox/sidebar tables (Book Information, Seen In, etc.)
    text = re.sub(r'<table[^>]*>.*?</table>', ' ', text, flags=re.DOTALL | re.IGNORECASE)

    # Remove navigation boxes (Prev/Next/Up divs)
    text = re.sub(r'<div[^>]*class="[^"]*(?:prevnext|navbar|noprint|toc)[^"]*"[^>]*>.*?</div>',
                  ' ', text, flags=re.DOTALL | re.IGNORECASE)

    # Strip all remaining tags
    text = re.sub(r'<[^>]+>', ' ', text)
    text = html_mod.unescape(text)

    # Remove the book title header line and description line
    text = re.sub(
        r'The\s+Thirty[- ]Six\s+Lessons\s+of\s+Vivec[^.]*?(?:Sermon\s+\w+)?[^.]*?\n?',
        ' ', text, flags=re.IGNORECASE
    )
    text = re.sub(r'Book\s+\d+\s+of\s+a\s+series[^.]*?\.', ' ', text, flags=re.IGNORECASE)
    text = re.sub(r'This\s+book\s+had\s+a\s+companion\s+image[^.]*?\.', ' ', text, flags=re.IGNORECASE)
    text = re.sub(r'by\s+Vivec\b', ' ', text, flags=re.IGNORECASE)

    # Remove nav fragments: "Prev: None", "Up: ...", "Next: Sermon X"
    text = re.sub(r'(?:Prev(?:ious)?|Next|Up)\s*:?\s*[^\n]{0,60}(?:\n|$)', ' ', text, flags=re.IGNORECASE)

    # Remove "Book Information", "Writer", "Seen In" metadata lines
    text = re.sub(r'Book\s+Information.*?(?=He\s+was\s+born|$)', ' ', text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r'(?:Writer|Seen\s+In|Skill\s+Book)[^\n]*\n?', ' ', text, flags=re.IGNORECASE)

    # Normalise whitespace
    text = normalise(text)

    # The actual sermon always starts with "He was born" (sermon 1) or similar.
    # More generally, strip everything before the first sentence that looks like
    # actual prose — identified by starting with a capital letter after cleanup.
    # Find "The ending of the words is ALMSIVI." as the terminus.
    almsivi = text.rfind("The ending of the words is ALMSIVI.")
    if almsivi != -1:
        text = text[:almsivi + len("The ending of the words is ALMSIVI.")].strip()

    return text


def build_vivec_sermons():
    path = DATA_DIR / "classical" / "vivec_sermons.json"
    if skip_if_exists(path):
        return

    sermons = {}
    for n in range(1, 37):
        url = _VIVEC_BASE.format(n=n)
        try:
            html = fetch(url)
            text = _parse_vivec_sermon(html, n)
            if len(text) < 100:
                print(f"    ⚠  Sermon {n}: suspiciously short ({len(text)} chars)")
            else:
                sermons[str(n)] = {"1": text}
                print(f"    Sermon {n}: {len(text)} chars")
        except Exception as e:
            print(f"    ✗  Sermon {n}: {e}")

    if not sermons:
        print("    ✗  No sermons saved")
        return

    save(path, {
        "source": "The 36 Lessons of Vivec — Michael Kirkbride (CC BY-SA 2.5)",
        "books": {"Vivec": sermons}
    })
    print(f"    Saved {len(sermons)} sermons")




# ════════════════════════════════════════════════════════════════════════════════
# 19. Catechism of the Catholic Church (aseemsavio/catholicism-in-json on GitHub)
#
# Source: [{id: 1, text: "..."}, ...] — 2865 paragraphs
# Stored as a flat dict: {paragraph_number: text}
# Citation: CCC 1  →  paragraph 1
# ════════════════════════════════════════════════════════════════════════════════

def build_ccc():
    path = DATA_DIR / "ccc.json"
    if skip_if_exists(path):
        return
    try:
        url = "https://raw.githubusercontent.com/aseemsavio/catholicism-in-json/master/catechism-of-the-catholic-church/catechism-of-the-catholic-church.json"
        raw = fetch(url)
        entries = json.loads(raw)
        paragraphs = {}
        for entry in entries:
            pid = str(entry["id"])
            text = entry.get("text", "").strip()
            if text:
                paragraphs[pid] = text
        if not paragraphs:
            raise ValueError("No paragraphs parsed")
        save(path, {
            "source": "Catechism of the Catholic Church, Second Edition (Libreria Editrice Vaticana)",
            "paragraphs": paragraphs
        })
        print(f"    Saved {len(paragraphs)} paragraphs")
    except Exception as e:
        print(f"    ✗  {e}")



# ════════════════════════════════════════════════════════════════════════════════
# 20. The Aeneid (Virgil, trans. John Dryden, 1697)
#
# 12 books fetched from classics.mit.edu. Each non-blank line is stored
# as a numbered verse. Keyed as book → line_number → text.
# Used by !virgil (Sortes Vergilianae).
# ════════════════════════════════════════════════════════════════════════════════

_AENEID_URLS = [
    "https://classics.mit.edu/Virgil/aeneid.1.i.html",
    "https://classics.mit.edu/Virgil/aeneid.2.ii.html",
    "https://classics.mit.edu/Virgil/aeneid.3.iii.html",
    "https://classics.mit.edu/Virgil/aeneid.4.iv.html",
    "https://classics.mit.edu/Virgil/aeneid.5.v.html",
    "https://classics.mit.edu/Virgil/aeneid.6.vi.html",
    "https://classics.mit.edu/Virgil/aeneid.7.vii.html",
    "https://classics.mit.edu/Virgil/aeneid.8.viii.html",
    "https://classics.mit.edu/Virgil/aeneid.9.ix.html",
    "https://classics.mit.edu/Virgil/aeneid.10.x.html",
    "https://classics.mit.edu/Virgil/aeneid.11.xi.html",
    "https://classics.mit.edu/Virgil/aeneid.12.xii.html",
]


def build_aeneid():
    path = DATA_DIR / "classical" / "aeneid.json"
    if skip_if_exists(path):
        return
    import html as html_mod
    books = {}
    for book_num, url in enumerate(_AENEID_URLS, 1):
        try:
            raw = fetch(url)
            # Each line of verse is separated by <br> tags
            # Extract just the content section (after the table of contents nav)
            # Lines of verse start after the last </table> in the nav
            # Strip all tags to get plain text lines
            text = html_mod.unescape(raw)
            # Remove nav/header cruft: everything before "Arms, and the man" or
            # the book's first line of verse
            # We'll split on <br> to get individual lines
            text = re.sub(r'<br\s*/?>', '\n', text, flags=re.IGNORECASE)
            text = re.sub(r'<[^>]+>', '', text)
            text = html_mod.unescape(text)

            lines_raw = text.split('\n')
            verses = {}
            line_num = 1
            for raw_line in lines_raw:
                line = raw_line.strip()
                # Skip empty lines, nav items, metadata
                if not line:
                    continue
                # Skip lines that are clearly nav/metadata (short, contain URLs etc.)
                if len(line) < 10:
                    continue
                if any(skip in line for skip in [
                    'classics.mit.edu', 'Table of Contents', 'Go to next',
                    'Go to prev', 'Book I', 'Book II', 'Book III', 'Book IV',
                    'Book V', 'Book VI', 'Book VII', 'Book VIII', 'Book IX',
                    'Book X', 'Book XI', 'Book XII', 'By Virgil',
                    'Translated by', 'Written 19', 'The Aeneid',
                    'Commentary:', 'Download:', 'text-only version',
                    'available for download', '© 1994',
                ]):
                    continue
                verses[str(line_num)] = line
                line_num += 1

            books[str(book_num)] = verses
            print(f"    Book {book_num}: {len(verses)} lines")
        except Exception as e:
            print(f"    ✗  Book {book_num}: {e}")

    if not books:
        raise ValueError("No books parsed")

    save(path, {
        "source": "The Aeneid — Virgil (trans. John Dryden, 1697)",
        "books": {"Aeneid": books}
    })
    total = sum(len(v) for v in books.values())
    print(f"    Saved {len(books)} books, {total} lines total")


def main():
    steps = [
        ("[1/20] KJV Canon (OT + NT)",                 build_kjv_canon),
        ("[2/20] KJV Apocrypha",                        build_kjv_apocrypha),
        ("[3/20] LDS Standard Works",                   build_lds),
        ("[4/20] Brenton Septuagint extras",            build_brenton_extras),
        ("[5/20] Book of Enoch (R.H. Charles)",         build_enoch),
        ("[6/20] Book of Jubilees (R.H. Charles)",      build_jubilees),
        ("[7/20] Apostolic Fathers (Lightfoot)",        build_apostolic_fathers),
        ("[8/20] Quran (Pickthall)",                    build_quran),
        ("[9/20] Golden Verses of Pythagoras",          build_golden_verses),
        ("[10/20] Orphic Hymns (Taylor)",               build_orphic_hymns),
        ("[11/20] Homeric Hymns (Evelyn-White)",        build_homeric_hymns),
        ("[12/20] Corpus Hermeticum (Mead)",            build_corpus_hermeticum),
        ("[13/20] Asclepius (Mead)",                    build_asclepius),
        ("[14/20] Chaldaean Oracles (Westcott)",        build_chaldaean_oracles),
        ("[15/20] Hesiod Theogony (Evelyn-White)",      build_hesiod_theogony),
        ("[16/20] Gathas (Azargoshasb)",                build_gathas),
        ("[17/20] Delphi — Maxims & Oracles",           build_delphi),
        ("[18/20] The 36 Lessons of Vivec (Kirkbride)", build_vivec_sermons),
        ("[19/20] Catechism of the Catholic Church",    build_ccc),
        ("[20/20] The Aeneid (Virgil/Dryden)",          build_aeneid),
    ]
    for label, fn in steps:
        print(f"\n{label}")
        try:
            fn()
        except Exception as e:
            print(f"  ✗  FAILED: {e}")
    print("\n✓ Done.  Check data/ for any ✗ failures.")


if __name__ == "__main__":
    main()
