"""
build_ancient_fixes2.py — second round of fixes
Run: python build_ancient_fixes2.py
"""
import json, re, sys, time, urllib.request, urllib.error
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
            elif e.code == 404: return None
            else: print(f"\n    HTTP {e.code}"); return None
        except Exception as ex: print(f"\n    {ex}"); return None
    return None

def clean(t): return re.sub(r"\s+", " ", t).strip()

def update_json(path, book_name, sections):
    data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"books":{}}
    data["books"][book_name] = sections
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    kb = path.stat().st_size // 1024
    total = sum(len(v) for v in data["books"].values())
    print(f"    ✓ {path} ({kb}KB, {len(data['books'])} books, {total} sections)")


# ── Plotinus: key insight — sections span multiple blank-line-separated paragraphs
# We need to collect ALL text until the next "N. " marker regardless of blank lines

def fix_plotinus():
    print("\n── Plotinus ──────────────────────────────────────────────────────────")
    print("  Fetching...", end=" ", flush=True)
    text = fetch("https://classics.mit.edu/Plotinus/enneads.mb.txt", delay=1.0)
    if not text: print("failed"); return

    text = re.sub(r'^.*?-{20,}', '', text, flags=re.DOTALL)
    text = re.sub(r'-{20,}.*$', '', text, flags=re.DOTALL)

    ENNEAD = {"FIRST":1,"SECOND":2,"THIRD":3,"FOURTH":4,"FIFTH":5,"SIXTH":6}
    TRACT  = {"First":1,"Second":2,"Third":3,"Fourth":4,"Fifth":5,
              "Sixth":6,"Seventh":7,"Eighth":8,"Ninth":9,"Tenth":10}

    results = {}
    ennead = tractate = section = None
    buf = []  # accumulate ALL lines for current section

    def flush():
        if ennead and tractate and section is not None and buf:
            t = clean(" ".join(buf))
            if len(t) > 20:
                results[f"{ennead}.{tractate}.{section}"] = {"1": t}

    ennead_re   = re.compile(r'^THE\s+(\w+)\s+ENNEAD\s*$')
    tractate_re = re.compile(r'^(\w+)\s+Tractate\s*$')
    section_re  = re.compile(r'^(\d+)\.\s+(.*)')

    for line in text.split('\n'):
        s = line.strip()
        em = ennead_re.match(s)
        tm = tractate_re.match(s)
        sm = section_re.match(s) if s else None

        if em:
            flush(); buf = []; section = None
            ennead = ENNEAD.get(em.group(1).upper())
            tractate = None
        elif tm:
            flush(); buf = []; section = None
            tractate = TRACT.get(tm.group(1))
        elif sm and ennead and tractate:
            flush(); buf = []
            section = int(sm.group(1))
            rest = sm.group(2).strip()
            if rest: buf.append(rest)
        elif ennead and tractate and section is not None:
            # Accumulate everything — blank lines included as spaces
            if s and not s.startswith('*') and not (s.isupper() and len(s.split()) <= 6):
                buf.append(s)
            # Empty lines: just skip, don't flush

    flush()
    print(f"✓ {len(results)}")
    update_json(CLASSICAL_DIR / "plotinus.json", "Enneads", results)


# ── Nicomachean Ethics: "BOOK I\n\n1 \n\ntext paragraphs\n\n2 \n\ntext..."
# The bare number "1" appears as its OWN paragraph (double-newline separated).
# We need: collect all paragraphs that are NOT book headers or bare numbers as text.

def fix_nic_ethics():
    print("\n── Nicomachean Ethics ────────────────────────────────────────────────")
    print("  Fetching...", end=" ", flush=True)
    text = fetch("https://classics.mit.edu/Aristotle/nicomachaen.mb.txt", delay=1.0)
    if not text: print("failed"); return

    text = re.sub(r'^.*?-{20,}', '', text, flags=re.DOTALL)
    text = re.sub(r'-{20,}.*$', '', text, flags=re.DOTALL)

    roman = {'I':1,'II':2,'III':3,'IV':4,'V':5,'VI':6,'VII':7,'VIII':8,'IX':9,'X':10}

    results = {}
    current_book = None
    current_sect = None
    para_buf = []  # paragraphs for current section

    def flush():
        if current_sect is not None and para_buf:
            t = clean(" ".join(para_buf))
            if len(t) > 20:
                key = f"{current_book}.{current_sect}" if current_book else str(current_sect)
                results[key] = {"1": t}

    # Split by double newline (paragraph blocks)
    blocks = re.split(r'\n\s*\n', text)

    for block in blocks:
        b = block.strip()
        if not b:
            continue

        # Book header: "BOOK I" (entire block is just this)
        bm = re.match(r'^BOOK\s+([IVXLCDM]+)\s*$', b, re.IGNORECASE)
        # Bare number: just "1" or "23" (entire block)
        nm = re.match(r'^(\d+)\s*$', b)

        if bm:
            flush(); para_buf = []; current_sect = None
            current_book = roman.get(bm.group(1).upper(), bm.group(1))
        elif nm:
            flush(); para_buf = []
            current_sect = int(nm.group(1))
        else:
            if current_sect is not None:
                # Regular text — join internal newlines, add to buffer
                para_text = clean(b.replace('\n', ' '))
                if para_text:
                    para_buf.append(para_text)

    flush()
    print(f"✓ {len(results)}")

    path = CLASSICAL_DIR / "aristotle_mit.json"
    data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"books":{}}
    data["books"]["Nicomachean Ethics"] = results
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    kb = path.stat().st_size // 1024
    total = sum(len(v) for v in data["books"].values())
    print(f"    ✓ {path} ({kb}KB, {len(data['books'])} books, {total} sections)")


# ── Porphyry: correct URLs for Cave of Nymphs and Auxiliaries/Sententiae

def parse_tertullian(html):
    if not html: return {}
    text = re.sub(r'<[^>]+>', ' ', html)
    text = text.replace('&nbsp;',' ').replace('&amp;','&')
    text = re.sub(r'&\w+;', '', text)
    results = {}; current = None; buf = []

    def flush():
        if current and buf:
            t = clean(" ".join(buf))
            if len(t) > 20: results[str(current)] = {"1": t}

    for line in text.split('\n'):
        m = re.match(r'^\s*(\d+)\.\s+(.*)', line)
        if m:
            flush(); buf = []; current = int(m.group(1))
            rest = m.group(2).strip()
            if rest: buf.append(rest)
        else:
            s = line.strip()
            if s and current and len(s) > 3: buf.append(s)
    flush()
    return results

def fix_porphyry():
    print("\n── Porphyry (correct URLs) ───────────────────────────────────────────")
    path = CLASSICAL_DIR / "porphyry.json"
    data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"books":{}}

    print("  Cave of the Nymphs...", end=" ", flush=True)
    html = fetch("https://www.tertullian.org/fathers/porphyry_cave_of_nymphs_02_translation.htm", delay=1.5)
    sects = parse_tertullian(html)
    if sects:
        data["books"]["On the Cave of the Nymphs"] = sects
        print(f"✓ {len(sects)}")
    else:
        print("no sections")

    print("  Auxiliaries to the Intelligibles...", end=" ", flush=True)
    html = fetch("https://www.tertullian.org/fathers/porphyry_sententiae_02_trans.htm", delay=1.5)
    sects = parse_tertullian(html)
    if sects:
        data["books"]["Auxiliaries to the Intelligibles"] = sects
        print(f"✓ {len(sects)}")
    else:
        print("no sections")

    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    kb = path.stat().st_size // 1024
    total = sum(len(v) for v in data["books"].values())
    print(f"    ✓ {path} ({kb}KB, {len(data['books'])} books, {total} sections)")


# ── MIT Aristotle: correct filenames from the browse page

MIT_CORRECT = [
    ("On the Motion of Animals",          "motion_animals",  False),
    ("On the Gait of Animals",            "gait_anim",       False),
    ("On the Generation of Animals",      "generat_anim",    True),
    ("On Memory and Reminiscence",        "memory",          False),
    ("On Dreams",                         "dreams",          False),
    ("On Sleep and Sleeplessness",        "sleep",           False),
    ("On Prophesying by Dreams",          "prophesying",     False),
    ("On Longevity and Shortness of Life","longev_short",    False),
    ("On Youth, Old Age, Life and Death", "youth",           False),
    ("On the Soul",                       "soul",            True),
]

MIT_BASE = "https://classics.mit.edu"

def parse_mit(text, has_books):
    if not text: return {}
    text = re.sub(r'^.*?-{20,}', '', text, flags=re.DOTALL)
    text = re.sub(r'-{20,}.*$', '', text, flags=re.DOTALL)

    roman = {r:i for i,r in enumerate(['I','II','III','IV','V','VI','VII',
        'VIII','IX','X','XI','XII','XIII','XIV','XV'],1)}
    results = {}; book = None; sect = None; buf = []

    def flush():
        if sect is not None and buf:
            t = clean(" ".join(buf))
            if len(t) > 20:
                key = f"{book}.{sect}" if (has_books and book) else str(sect)
                results[key] = {"1": t}

    blocks = re.split(r'\n\s*\n', text)
    for block in blocks:
        b = block.strip()
        if not b: continue
        bm = re.match(r'^BOOK\s+([IVXLCDM\d]+)\s*$', b, re.IGNORECASE)
        pm = re.match(r'^Part\s+(\d+)\s*$', b, re.IGNORECASE)
        sm = re.match(r'^SECTION\s+(\d+)\s*$', b, re.IGNORECASE)
        nm = re.match(r'^(\d+)\s*$', b)

        if bm:
            flush(); buf = []; sect = None
            r = bm.group(1).upper()
            book = roman.get(r) or (int(r) if r.isdigit() else r)
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

def fix_mit():
    print("\n── MIT Aristotle (correct filenames) ─────────────────────────────────")
    path = CLASSICAL_DIR / "aristotle_mit.json"
    data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"books":{}}

    for title, stem, has_books in MIT_CORRECT:
        print(f"  {title}...", end=" ", flush=True)
        url = f"{MIT_BASE}/Aristotle/{stem}.mb.txt"
        text = fetch(url, delay=1.0)
        if text is None: print("not found"); continue
        sects = parse_mit(text, has_books)
        if not sects: print("no sections"); continue
        data["books"][title] = sects
        print(f"✓ {len(sects)}")

    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    kb = path.stat().st_size // 1024
    total = sum(len(v) for v in data["books"].values())
    print(f"    ✓ {path} ({kb}KB, {len(data['books'])} books, {total} sections)")


# ── Iamblichus On the Mysteries: inspect what's actually in the Gutenberg text

def fix_iamblichus_mysteries():
    print("\n── Iamblichus On the Mysteries ───────────────────────────────────────")
    print("  Fetching...", end=" ", flush=True)
    text = fetch("https://www.gutenberg.org/cache/epub/72815/pg72815.txt", delay=1.5)
    if not text: print("failed"); return

    # Strip PG wrapper
    start = text.find('*** START OF THE PROJECT')
    if start != -1: text = text[text.find('\n', start)+1:]
    end = text.find('*** END OF THE PROJECT')
    if end != -1: text = text[:end]

    # Show first 100 lines to understand structure
    lines = text.split('\n')
    print(f"\n  First 80 lines of Gutenberg Iamblichus:")
    for i, l in enumerate(lines[:80]):
        print(f"  {i:3}: {l!r}")

fix_iamblichus_mysteries()  # diagnostic only first

if __name__ == "__main__":
    fix_plotinus()
    fix_nic_ethics()
    fix_porphyry()
    fix_mit()
    # Iamblichus mysteries needs manual inspection first
    print("\n✓ Done.")
