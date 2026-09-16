"""
build_ancient_fixes.py
Run this AFTER build_ancient.py to patch the remaining issues:
  - Plotinus (fix section parsing)
  - Nicomachean Ethics (fix bare-number sections)
  - Iamblichus (fix Gutenberg URLs and format)
  - Josephus Life (fix XML parsing)
  - Porphyry Cave of Nymphs + Auxiliaries (fix URLs)
  - MIT "not found" works (fix filenames)

Usage: python build_ancient_fixes.py [--local-repo ./canonical-greekLit]
"""

import json, re, sys, time, urllib.request, urllib.error
import xml.etree.ElementTree as ET
from pathlib import Path

CLASSICAL_DIR = Path("data/classical")
JEWISH_DIR    = Path("data/jewish")


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
                wait = 60*(attempt+1); print(f"\n    429 — waiting {wait}s..."); time.sleep(wait)
            elif e.code == 404:
                return None
            else:
                print(f"\n    HTTP {e.code}: {url}"); return None
        except Exception as ex:
            print(f"\n    Error: {ex}"); return None
    return None


def clean(t):
    return re.sub(r"\s+", " ", t).strip()


def merge_json(path, new_books):
    """Merge new_books into existing JSON at path, or create fresh."""
    if path.exists():
        existing = json.loads(path.read_text(encoding="utf-8"))
        existing["books"].update(new_books)
        data = existing
    else:
        data = {"books": new_books}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    kb = path.stat().st_size // 1024
    total = sum(len(v) for v in data["books"].values())
    print(f"    ✓ → {path} ({kb} KB, {len(data['books'])} books, {total} sections)")


# ══════════════════════════════════════════════════════════════════════════════
# FIX 1: Plotinus — sections are "N. text" where N is at start of line
# The issue: continuation lines were being dropped because they look like
# blank/noise. Need to accumulate until next numbered section.
# ══════════════════════════════════════════════════════════════════════════════

ENNEAD_NUMS = {"FIRST":1,"SECOND":2,"THIRD":3,"FOURTH":4,"FIFTH":5,"SIXTH":6}
TRACT_NUMS  = {"First":1,"Second":2,"Third":3,"Fourth":4,"Fifth":5,
               "Sixth":6,"Seventh":7,"Eighth":8,"Ninth":9,"Tenth":10}

def fix_plotinus():
    print("\n── Plotinus (fix) ─────────────────────────────────────────────────────")
    print("  Fetching...", end=" ", flush=True)
    text = fetch("https://classics.mit.edu/Plotinus/enneads.mb.txt", delay=1.0)
    if not text:
        print("failed"); return

    # Strip header/footer
    text = re.sub(r'^.*?-{20,}', '', text, flags=re.DOTALL)
    text = re.sub(r'-{20,}.*$', '', text, flags=re.DOTALL)

    results = {}
    ennead = tractate = section = None
    chunks = []

    def flush():
        if ennead and tractate and section is not None and chunks:
            t = clean(" ".join(chunks))
            if len(t) > 20:
                results[f"{ennead}.{tractate}.{section}"] = {"1": t}

    ennead_re   = re.compile(r'^THE\s+(\w+)\s+ENNEAD\s*$')
    tractate_re = re.compile(r'^(\w+)\s+Tractate\s*$')
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
            # Skip translator footnotes and section titles (ALL CAPS short lines)
            if not s.startswith('*') and not (s.isupper() and len(s) < 60):
                chunks.append(s)
        # Empty lines: don't clear chunks — section continues across blank lines

    flush()
    print(f"✓ {len(results)} sections")
    merge_json(CLASSICAL_DIR / "plotinus.json", {"Enneads": results})


# ══════════════════════════════════════════════════════════════════════════════
# FIX 2: Nicomachean Ethics — "1 \n\ntext" format (bare number then blank then text)
# The old parser treated blank lines between number and text as ending the section.
# Solution: collect the whole file as blocks separated by double-newlines,
# then identify which blocks are section headers.
# ══════════════════════════════════════════════════════════════════════════════

def fix_nicomachean():
    print("\n── Nicomachean Ethics (fix) ───────────────────────────────────────────")
    print("  Fetching...", end=" ", flush=True)
    text = fetch("https://classics.mit.edu/Aristotle/nicomachaen.mb.txt", delay=1.0)
    if not text:
        print("failed"); return

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
                key = f"{current_book}.{current_sect}" if current_book else str(current_sect)
                results[key] = {"1": t}

    book_re = re.compile(r'^BOOK\s+([IVXLCDM]+)\s*$', re.IGNORECASE)
    # Section: just a number alone (possibly with trailing space)
    bare_re = re.compile(r'^(\d+)\s*$')

    # Split into paragraphs (double-newline separated)
    paragraphs = re.split(r'\n\s*\n', text)

    for para in paragraphs:
        para_stripped = para.strip()
        if not para_stripped:
            continue

        bm = book_re.match(para_stripped)
        nm = bare_re.match(para_stripped)

        if bm:
            flush(); chunks = []
            roman = bm.group(1).upper()
            vals = {'I':1,'II':2,'III':3,'IV':4,'V':5,'VI':6,'VII':7,'VIII':8,'IX':9,'X':10}
            current_book = vals.get(roman, roman)
            current_sect = None
        elif nm:
            flush(); chunks = []
            current_sect = int(nm.group(1))
        else:
            # Regular text paragraph
            if current_sect is not None:
                # Join lines within paragraph
                para_text = clean(para_stripped.replace('\n', ' '))
                if para_text:
                    chunks.append(para_text)

    flush()
    print(f"✓ {len(results)} sections")

    # Merge into aristotle_mit.json
    path = CLASSICAL_DIR / "aristotle_mit.json"
    if path.exists():
        data = json.loads(path.read_text(encoding="utf-8"))
        data["books"]["Nicomachean Ethics"] = results
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        kb = path.stat().st_size // 1024
        total = sum(len(v) for v in data["books"].values())
        print(f"    ✓ Updated {path} ({kb} KB, {len(data['books'])} books, {total} sections)")
    else:
        merge_json(path, {"Nicomachean Ethics": results})


# ══════════════════════════════════════════════════════════════════════════════
# FIX 3: Iamblichus — On the Mysteries from Gutenberg (correct URL + format)
# Life of Pythagoras from Gutenberg #63300
# ══════════════════════════════════════════════════════════════════════════════

def parse_gutenberg_iamblichus(text):
    """
    Gutenberg Iamblichus On the Mysteries.
    Structure: BOOK I, BOOK II... with sections labeled by Roman numerals.
    Actually structured as SECTION I, II, III with chapters within.
    Parse by looking at actual paragraph structure.
    """
    if not text:
        return {}

    # Strip PG header/footer
    start = text.find('*** START')
    if start != -1:
        text = text[text.find('\n', start)+1:]
    end = text.find('*** END')
    if end != -1:
        text = text[:end]

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

    # Book headers like "BOOK I.", "SECTION I."
    book_re = re.compile(r'^(?:BOOK|SECTION)\s+([IVXLCDM]+)\.?\s*$', re.IGNORECASE)
    # Chapter/section like "I.", "II.", "III." alone on a line
    roman_re = re.compile(r'^([IVXLCDM]+)\.\s*$')
    # Numbered sections
    num_re = re.compile(r'^(\d+)\.\s*$')

    roman_vals = {}
    for i, r in enumerate(['I','II','III','IV','V','VI','VII','VIII','IX','X',
                           'XI','XII','XIII','XIV','XV','XVI','XVII','XVIII',
                           'XIX','XX','XXI','XXII','XXIII','XXIV','XXV'], 1):
        roman_vals[r] = i

    paragraphs = re.split(r'\n\s*\n', text)
    for para in paragraphs:
        s = para.strip()
        if not s:
            continue
        bm = book_re.match(s)
        rm = roman_re.match(s)
        nm = num_re.match(s)

        if bm:
            flush(); chunks = []
            roman = bm.group(1).upper()
            current_book = roman_vals.get(roman, roman)
            current_sect = None
        elif rm and len(s) <= 6:
            flush(); chunks = []
            current_sect = roman_vals.get(rm.group(1).upper(), rm.group(1))
        elif nm:
            flush(); chunks = []
            current_sect = int(nm.group(1))
        else:
            if current_sect is not None:
                para_text = clean(s.replace('\n', ' '))
                if para_text:
                    chunks.append(para_text)

    flush()
    return results


def parse_gutenberg_iamb_life(text):
    """
    Gutenberg Iamblichus Life of Pythagoras #63300.
    Chapters labeled CHAP. I, CHAP. II etc.
    """
    if not text:
        return {}
    start = text.find('*** START')
    if start != -1:
        text = text[text.find('\n', start)+1:]
    end = text.find('*** END')
    if end != -1:
        text = text[:end]

    results = {}
    current_chap = None
    chunks = []

    def flush():
        if current_chap and chunks:
            t = clean(" ".join(chunks))
            if len(t) > 30:
                results[str(current_chap)] = {"1": t}

    chap_re = re.compile(r'^CHAP(?:TER|\.?)\s+([IVXLCDM]+)\.?\s*$', re.IGNORECASE)
    roman_vals = {r:i for i,r in enumerate(['I','II','III','IV','V','VI','VII',
        'VIII','IX','X','XI','XII','XIII','XIV','XV','XVI','XVII','XVIII',
        'XIX','XX','XXI','XXII','XXIII','XXIV','XXV','XXVI','XXVII','XXVIII',
        'XXIX','XXX','XXXI','XXXII','XXXIII','XXXIV','XXXV'],1)}

    paragraphs = re.split(r'\n\s*\n', text)
    for para in paragraphs:
        s = para.strip()
        if not s:
            continue
        cm = chap_re.match(s)
        if cm:
            flush(); chunks = []
            current_chap = roman_vals.get(cm.group(1).upper(), cm.group(1))
        elif current_chap is not None:
            t = clean(s.replace('\n', ' '))
            if t and not t.startswith('_'):
                chunks.append(t)

    flush()
    return results


def fix_iamblichus():
    print("\n── Iamblichus (fix) ───────────────────────────────────────────────────")
    books = {}

    # On the Mysteries — Gutenberg plain text
    print("  On the Mysteries...", end=" ", flush=True)
    text = fetch("https://www.gutenberg.org/cache/epub/72815/pg72815.txt", delay=1.5)
    if not text:
        # Try alternate URL
        text = fetch("https://www.gutenberg.org/files/72815/72815-0.txt", delay=1.5)
    if text:
        sects = parse_gutenberg_iamblichus(text)
        if sects:
            books["On the Mysteries"] = sects
            print(f"✓ {len(sects)}")
        else:
            print("no sections — trying alternate parse")
            # Fallback: treat as flat numbered sections
            sects = _flat_numbered_parse(text)
            if sects:
                books["On the Mysteries"] = sects
                print(f"✓ {len(sects)} (flat)")
    else:
        print("not found")

    # Life of Pythagoras — Gutenberg #63300
    print("  Life of Pythagoras...", end=" ", flush=True)
    text = fetch("https://www.gutenberg.org/cache/epub/63300/pg63300.txt", delay=1.5)
    if not text:
        text = fetch("https://www.gutenberg.org/files/63300/63300-0.txt", delay=1.5)
    if text:
        sects = parse_gutenberg_iamb_life(text)
        if sects:
            books["Life of Pythagoras"] = sects
            print(f"✓ {len(sects)}")
        else:
            print("no sections")
    else:
        print("not found")

    if books:
        merge_json(CLASSICAL_DIR / "iamblichus.json", books)


def _flat_numbered_parse(text):
    """Fallback: find paragraphs starting with 'N.' pattern."""
    text = re.sub(r'\*\*\* START.*?\*\*\*', '', text, flags=re.DOTALL)
    text = re.sub(r'\*\*\* END.*', '', text, flags=re.DOTALL)
    results = {}
    current = None
    chunks = []

    def flush():
        if current and chunks:
            t = clean(" ".join(chunks))
            if len(t) > 30:
                results[str(current)] = {"1": t}

    for line in text.split('\n'):
        s = line.strip()
        m = re.match(r'^(\d+)\.\s+(.*)', s)
        if m:
            flush(); chunks = []
            current = int(m.group(1))
            rest = m.group(2).strip()
            if rest:
                chunks.append(rest)
        elif s and current:
            chunks.append(s)
    flush()
    return results


# ══════════════════════════════════════════════════════════════════════════════
# FIX 4: Josephus Life — different XML structure (no book div?)
# ══════════════════════════════════════════════════════════════════════════════

def fix_josephus_life(repo):
    if not repo:
        return
    print("\n── Josephus Life (fix) ────────────────────────────────────────────────")
    path = repo / "data/tlg0526/tlg002/tlg0526.tlg002.perseus-eng2.xml"
    if not path.exists():
        print("  file not found"); return

    xml = path.read_text(encoding="utf-8")
    xml = re.sub(r' xmlns(?::\w+)?="[^"]*"', "", xml)
    xml = re.sub(r"<\?[^>]+\?>", "", xml)
    try:
        root = ET.fromstring(xml)
    except ET.ParseError as e:
        print(f"  XML error: {e}"); return

    body = root.find(".//body")
    if body is None:
        body = root

    def get_text(elem):
        SKIP = {"note","bibl","foreign","head","label","lb"}
        tag = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag
        if tag in SKIP: return ""
        parts = [elem.text or ""]
        for child in elem:
            parts.append(get_text(child))
            parts.append(child.tail or "")
        return "".join(parts)

    results = {}

    # Try finding sections at any level
    for div in body.iter():
        tag = div.tag.split("}")[-1] if "}" in div.tag else div.tag
        if tag == "div":
            subtype = div.get("subtype","")
            n = div.get("n","")
            if subtype == "section" and n:
                paras = []
                for p in div.findall(".//p"):
                    t = clean(get_text(p))
                    if t: paras.append(t)
                if paras:
                    results[f"1.{n}"] = {"1": " ".join(paras)}

    if not results:
        # Last resort: collect all paragraphs numbered by position
        for i, p in enumerate(body.findall(".//p"), 1):
            t = clean(get_text(p))
            if len(t) > 20:
                results[str(i)] = {"1": t}

    print(f"  Life... ✓ {len(results)} sections")

    path_out = JEWISH_DIR / "josephus.json"
    if path_out.exists():
        data = json.loads(path_out.read_text(encoding="utf-8"))
        data["books"]["Life"] = results
        path_out.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        kb = path_out.stat().st_size // 1024
        total = sum(len(v) for v in data["books"].values())
        print(f"    ✓ Updated {path_out} ({kb} KB, {len(data['books'])} books, {total} sections)")


# ══════════════════════════════════════════════════════════════════════════════
# FIX 5: Porphyry — Cave of Nymphs + Auxiliaries correct URLs
# ══════════════════════════════════════════════════════════════════════════════

def parse_tertullian(html):
    if not html: return {}
    text = re.sub(r'<[^>]+>', ' ', html)
    text = text.replace('&nbsp;',' ').replace('&amp;','&')
    text = re.sub(r'&\w+;', '', text)
    results = {}; current = None; chunks = []

    def flush():
        if current and chunks:
            t = clean(" ".join(chunks))
            if len(t) > 20:
                results[str(current)] = {"1": t}

    for line in text.split('\n'):
        m = re.match(r'^\s*(\d+)\.\s+(.*)', line)
        if m:
            flush(); chunks = []; current = int(m.group(1))
            rest = m.group(2).strip()
            if rest: chunks.append(rest)
        else:
            s = line.strip()
            if s and current and len(s) > 3:
                chunks.append(s)
    flush()
    return results


def fix_porphyry():
    print("\n── Porphyry (fix missing works) ───────────────────────────────────────")

    # Try various URL patterns for Cave of the Nymphs
    cave_urls = [
        "https://www.tertullian.org/fathers/porphyry_cave_nymphs_02_text.htm",
        "https://www.tertullian.org/fathers/porphyry_nymphs_02_text.htm",
        "https://www.tertullian.org/fathers/porphyry_cave_02_text.htm",
    ]
    aux_urls = [
        "https://www.tertullian.org/fathers/porphyry_auxiliaries_02_text.htm",
        "https://www.tertullian.org/fathers/porphyry_isagoge_02_text.htm",
        "https://www.tertullian.org/fathers/porphyry_select_works_02_text.htm",
    ]

    new_books = {}

    print("  Cave of the Nymphs...", end=" ", flush=True)
    for url in cave_urls:
        html = fetch(url, delay=1.0)
        if html:
            sects = parse_tertullian(html)
            if sects:
                new_books["On the Cave of the Nymphs"] = sects
                print(f"✓ {len(sects)} (from {url.split('/')[-1]})")
                break
    else:
        print("not found — trying sacred-texts")
        html = fetch("https://sacred-texts.com/cla/plotenn/index.htm", delay=1.0)
        if not html:
            print("failed")

    print("  Auxiliaries to the Intelligibles...", end=" ", flush=True)
    for url in aux_urls:
        html = fetch(url, delay=1.0)
        if html:
            sects = parse_tertullian(html)
            if sects:
                new_books["Auxiliaries to the Intelligibles"] = sects
                print(f"✓ {len(sects)} (from {url.split('/')[-1]})")
                break
    else:
        print("not found")

    if new_books:
        merge_json(CLASSICAL_DIR / "porphyry.json", new_books)


# ══════════════════════════════════════════════════════════════════════════════
# FIX 6: MIT Aristotle — correct filenames for "not found" works
# ══════════════════════════════════════════════════════════════════════════════

MIT_MISSING_WORKS = [
    # (title, try_these_stems, has_books)
    ("On Generation and Corruption", ["generat_corr", "de_gen_corr", "gener_corr"], True),
    ("History of Animals",           ["hist_anim", "history_anim", "historia_anim"], True),
    ("On the Motion of Animals",     ["motion_anim", "mot_anim", "de_motu_anim"], False),
    ("On the Gait of Animals",       ["gait_anim", "de_incess_anim", "incess_anim"], False),
    ("On the Generation of Animals", ["generat_anim", "de_gen_anim", "gen_anim"], True),
    ("On Memory and Reminiscence",   ["memory", "de_mem", "mem_rem"], False),
    ("On Dreams",                    ["dreams", "de_somn", "somn"], False),
    ("On Sleep and Sleeplessness",   ["sleep", "de_somno", "somno"], False),
    ("On Prophesying by Dreams",     ["prophesy_dreams", "de_divin_somn", "divin_somn"], False),
    ("On Longevity and Shortness of Life", ["longev", "de_long", "long_short"], False),
    ("On Youth, Old Age, Life and Death",  ["youth", "de_juv", "juv_sen"], False),
    ("On the Virtues and Vices",     ["virt_vices", "de_virt", "virt"], False),
]

MIT_BASE = "https://classics.mit.edu"

def parse_mit(text, has_books):
    if not text: return {}
    text = re.sub(r'^.*?-{20,}', '', text, flags=re.DOTALL)
    text = re.sub(r'-{20,}.*$', '', text, flags=re.DOTALL)

    results = {}
    current_book = None; current_sect = None; chunks = []

    def flush():
        if current_sect is not None and chunks:
            t = clean(" ".join(chunks))
            if len(t) > 20:
                key = f"{current_book}.{current_sect}" if (has_books and current_book) else str(current_sect)
                results[key] = {"1": t}

    book_re = re.compile(r'^BOOK\s+([IVXLCDM\d]+)\s*$', re.IGNORECASE)
    part_re = re.compile(r'^Part\s+(\d+)\s*$', re.IGNORECASE)
    sect_re = re.compile(r'^SECTION\s+(\d+)\s*$', re.IGNORECASE)

    roman_vals = {r:i for i,r in enumerate(['I','II','III','IV','V','VI','VII',
        'VIII','IX','X','XI','XII','XIII','XIV','XV'],1)}

    for line in text.split('\n'):
        s = line.strip()
        bm = book_re.match(s); pm = part_re.match(s); sm = sect_re.match(s)
        if bm:
            flush(); chunks = []; current_sect = None
            r = bm.group(1).upper()
            current_book = roman_vals.get(r) or (int(r) if r.isdigit() else r)
        elif pm:
            flush(); chunks = []; current_sect = int(pm.group(1))
        elif sm:
            flush(); chunks = []; current_sect = int(sm.group(1))
        elif s and current_sect is not None:
            chunks.append(s)
    flush()
    return results


def fix_mit_missing():
    print("\n── MIT Aristotle missing works (fix) ─────────────────────────────────")
    path = CLASSICAL_DIR / "aristotle_mit.json"
    data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"books":{}}

    for title, stems, has_books in MIT_MISSING_WORKS:
        print(f"  {title}...", end=" ", flush=True)
        found = False
        for stem in stems:
            url = f"{MIT_BASE}/Aristotle/{stem}.mb.txt"
            text = fetch(url, delay=1.0)
            if text and len(text) > 500:
                sects = parse_mit(text, has_books)
                if sects:
                    data["books"][title] = sects
                    print(f"✓ {len(sects)} (stem={stem})")
                    found = True
                    break
        if not found:
            print("not found")

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    kb = path.stat().st_size // 1024
    total = sum(len(v) for v in data["books"].values())
    print(f"    ✓ {path} ({kb} KB, {len(data['books'])} books, {total} sections)")


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    args = sys.argv[1:]
    repo = None
    if "--local-repo" in args:
        idx = args.index("--local-repo")
        if idx+1 < len(args):
            repo = Path(args[idx+1])
            if not repo.exists():
                print(f"Repo not found: {repo}"); sys.exit(1)

    fix_plotinus()
    fix_nicomachean()
    fix_iamblichus()
    fix_porphyry()
    fix_mit_missing()
    if repo:
        fix_josephus_life(repo)

    print("\n✓ Done.")
