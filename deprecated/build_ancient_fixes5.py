"""
build_ancient_fixes5.py
Run: python build_ancient_fixes5.py
"""
import json, re, time, urllib.request, urllib.error
from pathlib import Path

CLASSICAL_DIR = Path("data/classical")

def fetch(url, delay=0.8, timeout=30):
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


def strip_header_footer(text):
    """Strip only the FIRST dashes line (header), not all of them."""
    text = text.replace('\r', '')
    # Remove everything up to and including the first long dashes line
    m = re.search(r'-{20,}', text)
    if m:
        text = text[m.end():]
    # Remove from the last long dashes line to end
    m2 = re.search(r'-{20,}[^-]*$', text, re.DOTALL)
    if m2:
        text = text[:m2.start()]
    return text


# ── Plotinus ──────────────────────────────────────────────────────────
# Root cause: greedy strip was eating all but Ennead 1.
# Fix: strip only first dashes line, keep rest of file intact.

def fix_plotinus():
    print("\n── Plotinus ──────────────────────────────────────────────────────────")
    print("  Fetching...", end=" ", flush=True)
    text = fetch("https://classics.mit.edu/Plotinus/enneads.mb.txt", delay=1.0)
    if not text: print("failed"); return

    text = strip_header_footer(text)

    ENNEAD = {"FIRST":1,"SECOND":2,"THIRD":3,"FOURTH":4,"FIFTH":5,"SIXTH":6}
    TRACT  = {"First":1,"Second":2,"Third":3,"Fourth":4,"Fifth":5,
              "Sixth":6,"Seventh":7,"Eighth":8,"Ninth":9,"Tenth":10}

    results = {}
    ennead = tractate = section = None
    words = []

    def flush():
        if ennead and tractate and section is not None and words:
            t = clean(" ".join(words))
            if len(t) > 20:
                results[f"{ennead}.{tractate}.{section}"] = {"1": t}

    ennead_re   = re.compile(r'^THE\s+(\w+)\s+ENNEAD\s*$')
    tractate_re = re.compile(r'^(\w+)\s+Tractate\s*$')
    section_re  = re.compile(r'^(\d+)\.\s+(.*)')

    for line in text.split('\n'):
        s = line.strip()
        if not s:
            continue

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
            if s.startswith('*'): continue
            if s.isupper() and len(s.split()) <= 8: continue
            words.extend(s.split())

    flush()
    print(f"✓ {len(results)}")
    save_book(CLASSICAL_DIR / "plotinus.json", "Enneads", results)


# ── Nicomachean Ethics ────────────────────────────────────────────────
# Root cause: only 12 of 116 section numbers are double-newline separated.
# The rest have only single \n before/after the number.
# Pattern in file: "...sentence end. \n\n2 \n\nNext sentence..."
# But some are: "...sentence end.\n2 \n\nNext sentence..."
# Fix: use line-by-line parsing, treat a line that is ONLY a number
# (with optional space) as a section break.

def fix_nic_ethics():
    print("\n── Nicomachean Ethics ────────────────────────────────────────────────")
    print("  Fetching...", end=" ", flush=True)
    text = fetch("https://classics.mit.edu/Aristotle/nicomachaen.mb.txt", delay=1.0)
    if not text: print("failed"); return

    text = strip_header_footer(text)

    roman = {'I':1,'II':2,'III':3,'IV':4,'V':5,'VI':6,'VII':7,'VIII':8,'IX':9,'X':10}
    results = {}
    book = None; sect = None; lines_buf = []

    def flush():
        if sect is not None and lines_buf:
            t = clean(" ".join(lines_buf))
            if len(t) > 20:
                key = f"{book}.{sect}" if book else str(sect)
                results[key] = {"1": t}

    for line in text.split('\n'):
        s = line.strip()

        bm = re.match(r'^BOOK\s+([IVXLCDM]+)$', s, re.IGNORECASE)
        # A line that is ONLY digits (section number), possibly with trailing space
        nm = re.match(r'^(\d+)\s*$', s) if s else None

        if bm:
            flush(); lines_buf = []; sect = None
            book = roman.get(bm.group(1).upper(), bm.group(1))
        elif nm and s:  # non-empty line that's just a number
            flush(); lines_buf = []
            sect = int(nm.group(1))
        elif s and sect is not None:
            lines_buf.append(s)
        # empty lines: skip, don't flush

    flush()
    print(f"✓ {len(results)}")

    path = CLASSICAL_DIR / "aristotle_mit.json"
    data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"books":{}}
    data["books"]["Nicomachean Ethics"] = results
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    kb = path.stat().st_size // 1024
    total = sum(len(v) for v in data["books"].values())
    print(f"    ✓ {path} ({kb}KB, {len(data['books'])} books, {total} sections)")


if __name__ == "__main__":
    fix_plotinus()
    fix_nic_ethics()
    print("\n✓ Done.")
