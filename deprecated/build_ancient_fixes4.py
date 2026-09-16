"""
build_ancient_fixes4.py — fixes Plotinus and Nicomachean Ethics
Run: python build_ancient_fixes4.py
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


# ── Plotinus ──────────────────────────────────────────────────────────
# Issue: tractate regex requires trailing space but only "First Tractate "
# has one — "Second Tractate" through "Ninth Tractate" don't.
# Fix: match "Tractate" anywhere on a line that has nothing else.

def fix_plotinus():
    print("\n── Plotinus ──────────────────────────────────────────────────────────")
    print("  Fetching...", end=" ", flush=True)
    text = fetch("https://classics.mit.edu/Plotinus/enneads.mb.txt", delay=1.0)
    if not text: print("failed"); return
    text = text.replace('\r', '')

    # Strip header/footer
    text = re.sub(r'^.*?-{60,}', '', text, flags=re.DOTALL)
    text = re.sub(r'-{60,}.*$',  '', text, flags=re.DOTALL)

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

    ennead_re  = re.compile(r'^THE\s+(\w+)\s+ENNEAD\s*$')
    # Match any line that is ONLY "Word Tractate" with optional trailing space
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
            if s.isupper() and len(s.split()) <= 8: continue  # skip ALL-CAPS titles
            words.extend(s.split())

    flush()
    print(f"✓ {len(results)}")
    save_book(CLASSICAL_DIR / "plotinus.json", "Enneads", results)


# ── Nicomachean Ethics ────────────────────────────────────────────────
# Issue: \r in the fetched text turns "1 \r" into a block that after
# strip() becomes "1" — but \r needs stripping BEFORE the split.
# Also the block regex needs to handle "1 " (with trailing space pre-strip).

def fix_nic_ethics():
    print("\n── Nicomachean Ethics ────────────────────────────────────────────────")
    print("  Fetching...", end=" ", flush=True)
    text = fetch("https://classics.mit.edu/Aristotle/nicomachaen.mb.txt", delay=1.0)
    if not text: print("failed"); return

    # Strip CR before doing anything else
    text = text.replace('\r', '')
    text = re.sub(r'^.*?-{60,}', '', text, flags=re.DOTALL)
    text = re.sub(r'-{60,}.*$',  '', text, flags=re.DOTALL)

    roman = {'I':1,'II':2,'III':3,'IV':4,'V':5,'VI':6,'VII':7,'VIII':8,'IX':9,'X':10}
    results = {}
    book = None; sect = None; buf = []

    def flush():
        if sect is not None and buf:
            t = clean(" ".join(buf))
            if len(t) > 20:
                key = f"{book}.{sect}" if book else str(sect)
                results[key] = {"1": t}

    # Split on two or more newlines
    blocks = re.split(r'\n{2,}', text)
    for block in blocks:
        b = block.strip()
        if not b: continue

        bm = re.match(r'^BOOK\s+([IVXLCDM]+)$', b, re.IGNORECASE)
        # bare number: digits only, possibly trailing space (already stripped)
        nm = re.match(r'^\d+$', b)

        if bm:
            flush(); buf = []; sect = None
            book = roman.get(bm.group(1).upper(), bm.group(1))
        elif nm:
            flush(); buf = []
            sect = int(b)
        else:
            if sect is not None:
                t = clean(b.replace('\n', ' '))
                if t: buf.append(t)

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
