"""
build_ancient_fixes3.py
Run: python build_ancient_fixes3.py
"""
import json, re, time, urllib.request, urllib.error
from pathlib import Path

CLASSICAL_DIR = Path("data/classical")

def fetch(url, delay=0.8, timeout=20):
    for attempt in range(3):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "ScriptureBot/1.0"})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                data = r.read().decode("utf-8", errors="replace")
            time.sleep(delay)
            return data
        except urllib.error.HTTPError as e:
            if e.code == 429:
                wait = 60*(attempt+1); print(f"\n    429—waiting {wait}s..."); time.sleep(wait)
            elif e.code == 404: return None
            else: print(f"\n    HTTP {e.code}"); return None
        except Exception as ex: print(f"\n    {ex}"); return None
    return None

def clean(t): return re.sub(r"\s+", " ", t).strip()

def save_book(path, book_name, sections):
    data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"books":{}}
    data["books"][book_name] = sections
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    kb = path.stat().st_size // 1024
    total = sum(len(v) for v in data["books"].values())
    print(f"    ✓ {path} ({kb}KB, {len(data['books'])} books, {total} sections)")


# ══════════════════════════════════════════════════════════════════════
# FIX 1: Plotinus — the real problem
# Looking at the raw text: sections ARE "1. text" on one line, then
# continuation on following lines WITHOUT a number prefix.
# The issue: tractate titles like "THE ANIMATE AND THE MAN." are being
# mistaken for content OR flushing incorrectly.
# Real fix: scan the whole file as one pass, accumulating per-section.
# ══════════════════════════════════════════════════════════════════════

def fix_plotinus():
    print("\n── Plotinus ──────────────────────────────────────────────────────────")
    print("  Fetching...", end=" ", flush=True)
    text = fetch("https://classics.mit.edu/Plotinus/enneads.mb.txt", delay=1.0)
    if not text: print("failed"); return

    # Strip header/footer
    text = re.sub(r'^.*?-{60,}', '', text, flags=re.DOTALL)
    text = re.sub(r'-{60,}.*$', '', text, flags=re.DOTALL)
    lines = [l.rstrip() for l in text.split('\n')]

    ENNEAD = {"FIRST":1,"SECOND":2,"THIRD":3,"FOURTH":4,"FIFTH":5,"SIXTH":6}
    TRACT  = {"First":1,"Second":2,"Third":3,"Fourth":4,"Fifth":5,
              "Sixth":6,"Seventh":7,"Eighth":8,"Ninth":9,"Tenth":10}

    results = {}
    ennead = tractate = section = None
    words = []  # word buffer for current section

    def flush():
        if ennead and tractate and section is not None and words:
            t = clean(" ".join(words))
            if len(t) > 20:
                results[f"{ennead}.{tractate}.{section}"] = {"1": t}

    ennead_re   = re.compile(r'^THE\s+(\w+)\s+ENNEAD\s*$')
    tractate_re = re.compile(r'^(\w+)\s+Tractate\s*$')
    # Section lines: "N. text..." — number + dot + space at very start
    section_re  = re.compile(r'^(\d+)\.\s+(.*)')

    for line in lines:
        s = line.strip()
        if not s:
            continue  # blank line — skip but DON'T flush

        em = ennead_re.match(s)
        tm = tractate_re.match(s)
        sm = section_re.match(s)

        if em:
            flush(); words = []; section = None
            ennead = ENNEAD.get(em.group(1).upper())
            tractate = None
        elif tm:
            flush(); words = []; section = None
            tractate = TRACT.get(tm.group(1))
        elif sm and ennead and tractate:
            flush(); words = []
            section = int(sm.group(1))
            rest = sm.group(2).strip()
            if rest:
                words.extend(rest.split())
        elif ennead and tractate and section is not None:
            # Skip translator footnotes (* lines) and ALL-CAPS titles
            if s.startswith('*'):
                continue
            # Skip short all-caps lines (tractate titles like "THE ANIMATE AND THE MAN.")
            if s.isupper() and len(s) < 80:
                continue
            words.extend(s.split())

    flush()
    print(f"✓ {len(results)}")
    save_book(CLASSICAL_DIR / "plotinus.json", "Enneads", results)


# ══════════════════════════════════════════════════════════════════════
# FIX 2: Nicomachean Ethics — paragraph-block approach
# Structure confirmed: "BOOK I\n\n1 \n\ntext\n\n2 \n\ntext..."
# Problem: "1 " (number with trailing space) not matching "^\d+\s*$"
# because the block also contains \r on Windows.
# ══════════════════════════════════════════════════════════════════════

def fix_nic_ethics():
    print("\n── Nicomachean Ethics ────────────────────────────────────────────────")
    print("  Fetching...", end=" ", flush=True)
    text = fetch("https://classics.mit.edu/Aristotle/nicomachaen.mb.txt", delay=1.0)
    if not text: print("failed"); return

    text = re.sub(r'^.*?-{60,}', '', text, flags=re.DOTALL)
    text = re.sub(r'-{60,}.*$', '', text, flags=re.DOTALL)
    text = text.replace('\r', '')  # strip CR

    roman = {'I':1,'II':2,'III':3,'IV':4,'V':5,'VI':6,'VII':7,'VIII':8,'IX':9,'X':10}
    results = {}
    book = None; sect = None; buf = []

    def flush():
        if sect is not None and buf:
            t = clean(" ".join(buf))
            if len(t) > 20:
                key = f"{book}.{sect}" if book else str(sect)
                results[key] = {"1": t}

    blocks = re.split(r'\n{2,}', text)
    for block in blocks:
        b = block.strip()
        if not b: continue
        bm = re.match(r'^BOOK\s+([IVXLCDM]+)$', b, re.IGNORECASE)
        # bare number — possibly with trailing space
        nm = re.match(r'^(\d+)\s*$', b)
        if bm:
            flush(); buf = []; sect = None
            book = roman.get(bm.group(1).upper(), bm.group(1))
        elif nm:
            flush(); buf = []; sect = int(nm.group(1))
        else:
            if sect is not None:
                buf.append(clean(b.replace('\n', ' ')))

    flush()
    print(f"✓ {len(results)}")

    path = CLASSICAL_DIR / "aristotle_mit.json"
    data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"books":{}}
    data["books"]["Nicomachean Ethics"] = results
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    kb = path.stat().st_size // 1024
    total = sum(len(v) for v in data["books"].values())
    print(f"    ✓ {path} ({kb}KB, {len(data['books'])} books, {total} sections)")


# ══════════════════════════════════════════════════════════════════════
# FIX 3: Iamblichus On the Mysteries — from Gutenberg
# Format: no *** markers, sections labeled "SECTION THE FIRST." etc.
# or just Roman numeral chapter headers within each section.
# ══════════════════════════════════════════════════════════════════════

def fix_iamblichus():
    print("\n── Iamblichus On the Mysteries ───────────────────────────────────────")
    print("  Fetching...", end=" ", flush=True)
    text = fetch("https://www.gutenberg.org/cache/epub/72815/pg72815.txt",
                 delay=1.0, timeout=30)
    if not text: print("failed"); return
    text = text.replace('\r', '')

    # Find actual content start — skip front matter
    # Look for "EPISTLE OF PORPHYRY" or "SECTION THE FIRST"
    content_start = re.search(r'(EPISTLE OF PORPHYRY|SECTION THE FIRST)', text)
    if content_start:
        text = text[content_start.start():]

    # Structure: "SECTION THE FIRST." ... "SECTION THE SECOND." etc. (10 sections)
    # Within each section: Roman numeral chapters "I.", "II." etc.
    # Within each chapter: numbered paragraphs or just prose

    SECT_WORDS = {'FIRST':1,'SECOND':2,'THIRD':3,'FOURTH':4,'FIFTH':5,
                  'SIXTH':6,'SEVENTH':7,'EIGHTH':8,'NINTH':9,'TENTH':10}
    ROMAN = {r:i for i,r in enumerate(['I','II','III','IV','V','VI','VII','VIII',
        'IX','X','XI','XII','XIII','XIV','XV','XVI','XVII','XVIII','XIX','XX',
        'XXI','XXII','XXIII','XXIV','XXV','XXVI','XXVII','XXVIII'],1)}

    results = {}
    section = None; chapter = None; buf = []

    def flush():
        if section is not None and chapter is not None and buf:
            t = clean(" ".join(buf))
            if len(t) > 30:
                results[f"{section}.{chapter}"] = {"1": t}

    sect_re  = re.compile(r'^SECTION\s+THE\s+(\w+)\.?\s*$', re.IGNORECASE)
    # Roman numeral alone on a line: "I.", "II.", "XXVIII." etc.
    chap_re  = re.compile(r'^([IVXLCDM]+)\.\s*$')
    # Also handle "THE EPISTLE OF PORPHYRY" as section 0
    epist_re = re.compile(r'^(?:THE\s+)?EPISTLE\s+OF\s+PORPHYRY', re.IGNORECASE)

    blocks = re.split(r'\n{2,}', text)
    for block in blocks:
        b = block.strip()
        if not b: continue

        sm = sect_re.match(b)
        cm = chap_re.match(b)
        em = epist_re.match(b)

        if em and section is None:
            flush(); buf = []; section = 0; chapter = 1
        elif sm:
            flush(); buf = []; chapter = None
            section = SECT_WORDS.get(sm.group(1).upper())
        elif cm and section is not None:
            flush(); buf = []
            chapter = ROMAN.get(cm.group(1).upper())
        else:
            if section is not None and chapter is not None:
                # Skip page numbers, headers, short lines
                t = clean(b.replace('\n', ' '))
                if len(t) > 30 and not re.match(r'^\d+$', t):
                    buf.append(t)

    flush()
    print(f"✓ {len(results)}")
    save_book(CLASSICAL_DIR / "iamblichus.json", "On the Mysteries", results)


# ══════════════════════════════════════════════════════════════════════
# FIX 4: MIT Aristotle shorter works — fetch HTML pages directly
# since .mb.txt doesn't exist for many of them
# ══════════════════════════════════════════════════════════════════════

MIT_HTML_WORKS = [
    ("On Memory and Reminiscence", "memory",         False),
    ("On Dreams",                  "dreams",          False),
    ("On Sleep and Sleeplessness", "sleep",           False),
    ("On Prophesying by Dreams",   "prophesying",     False),
    ("On Longevity and Shortness of Life", "longev_short", False),
    ("On Youth, Old Age, Life and Death",  "youth",   False),
    ("On the Motion of Animals",   "motion_animals",  False),
    ("On the Gait of Animals",     "gait_anim",       False),
    ("On the Generation of Animals", "generat_anim",  True),
]

MIT_BASE = "https://classics.mit.edu"

def parse_mit_html(html, has_books):
    """Parse MIT HTML page — text is in <p> or plain paragraphs."""
    if not html: return {}
    # Strip tags
    text = re.sub(r'<[^>]+>', ' ', html)
    text = re.sub(r'&nbsp;', ' ', text)
    text = re.sub(r'&amp;', '&', text)
    text = re.sub(r'&\w+;', '', text)
    text = text.replace('\r', '')

    roman = {r:i for i,r in enumerate(['I','II','III','IV','V','VI','VII',
        'VIII','IX','X','XI','XII'],1)}
    results = {}; book = None; sect = None; buf = []

    def flush():
        if sect is not None and buf:
            t = clean(" ".join(buf))
            if len(t) > 20:
                key = f"{book}.{sect}" if (has_books and book) else str(sect)
                results[key] = {"1": t}

    blocks = re.split(r'\n{2,}', text)
    for block in blocks:
        b = block.strip()
        if not b or len(b) < 5: continue
        bm = re.match(r'^BOOK\s+([IVXLCDM]+)$', b, re.IGNORECASE)
        pm = re.match(r'^Part\s+(\d+)$', b, re.IGNORECASE)
        sm = re.match(r'^SECTION\s+(\d+)$', b, re.IGNORECASE)
        nm = re.match(r'^(\d+)\s*$', b)
        if bm:
            flush(); buf = []; sect = None
            book = roman.get(bm.group(1).upper(), bm.group(1))
        elif pm:
            flush(); buf = []; sect = int(pm.group(1))
        elif sm:
            flush(); buf = []; sect = int(sm.group(1))
        elif nm and not buf:
            flush(); buf = []; sect = int(nm.group(1))
        else:
            if sect is not None:
                t = clean(b.replace('\n', ' '))
                if t: buf.append(t)
    flush()
    return results

def fix_mit_html():
    print("\n── MIT Aristotle (HTML fetch) ─────────────────────────────────────────")
    path = CLASSICAL_DIR / "aristotle_mit.json"
    data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"books":{}}

    for title, stem, has_books in MIT_HTML_WORKS:
        print(f"  {title}...", end=" ", flush=True)
        # Try .mb.txt first, then .html
        text = fetch(f"{MIT_BASE}/Aristotle/{stem}.mb.txt", delay=0.8)
        if text and len(text) > 500:
            # plain text parse
            sects = _parse_mit_txt(text, has_books)
        else:
            html = fetch(f"{MIT_BASE}/Aristotle/{stem}.html", delay=0.8)
            sects = parse_mit_html(html, has_books) if html else {}

        if not sects:
            print("not found/no sections"); continue
        data["books"][title] = sects
        print(f"✓ {len(sects)}")

    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    kb = path.stat().st_size // 1024
    total = sum(len(v) for v in data["books"].values())
    print(f"    ✓ {path} ({kb}KB, {len(data['books'])} books, {total} sections)")

def _parse_mit_txt(text, has_books):
    text = re.sub(r'^.*?-{60,}', '', text, flags=re.DOTALL)
    text = re.sub(r'-{60,}.*$', '', text, flags=re.DOTALL)
    text = text.replace('\r','')
    roman = {r:i for i,r in enumerate(['I','II','III','IV','V','VI','VII',
        'VIII','IX','X','XI','XII'],1)}
    results = {}; book = None; sect = None; buf = []

    def flush():
        if sect is not None and buf:
            t = clean(" ".join(buf))
            if len(t) > 20:
                key = f"{book}.{sect}" if (has_books and book) else str(sect)
                results[key] = {"1": t}

    blocks = re.split(r'\n{2,}', text)
    for block in blocks:
        b = block.strip()
        if not b: continue
        bm = re.match(r'^BOOK\s+([IVXLCDM]+)$', b, re.IGNORECASE)
        pm = re.match(r'^Part\s+(\d+)$', b, re.IGNORECASE)
        sm = re.match(r'^SECTION\s+(\d+)$', b, re.IGNORECASE)
        nm = re.match(r'^(\d+)\s*$', b)
        if bm:
            flush(); buf = []; sect = None
            book = roman.get(bm.group(1).upper(), bm.group(1))
        elif pm:
            flush(); buf = []; sect = int(pm.group(1))
        elif sm:
            flush(); buf = []; sect = int(sm.group(1))
        elif nm and not buf:
            flush(); buf = []; sect = int(nm.group(1))
        else:
            if sect is not None:
                t = clean(b.replace('\n', ' '))
                if t: buf.append(t)
    flush()
    return results


if __name__ == "__main__":
    fix_plotinus()
    fix_nic_ethics()
    fix_iamblichus()
    fix_mit_html()
    print("\n✓ Done.")
