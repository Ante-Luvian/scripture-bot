"""
build_neoplatonic3.py — final fixes
Run: python build_neoplatonic3.py

- Porphyry: Life of Plotinus (sacred-texts enn001.htm)
- Hierocles: Commentary on the Golden Verses (sacred-texts gvp04.htm)
- Pythagorean collection from sacred-texts gvp:
    Golden Sentences of Democrates
    Pythagorean Sentences of Demophilus
    Pythagorean Sentences from Stobaeus
    Select Sentences of Sextus the Pythagorean
    Pythagorean Sentences from Iamblichus
    Symbols of Pythagoras
"""

import json, re, time, urllib.request, urllib.error
from pathlib import Path

OUT = Path("data/classical")

def fetch(url, delay=1.0, timeout=25):
    for attempt in range(3):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "ScriptureBot/1.0"})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                data = r.read().decode("utf-8", errors="replace")
            time.sleep(delay)
            return data
        except urllib.error.HTTPError as e:
            if e.code == 429:
                wait = 60*(attempt+1); print(f"\n    429—{wait}s..."); time.sleep(wait)
            elif e.code == 404: return None
            else: print(f"\n    HTTP {e.code}"); return None
        except Exception as ex:
            if attempt == 2: print(f"\n    {ex}")
            else: time.sleep(5)
    return None

def clean(t): return re.sub(r"\s+", " ", t).strip()

def strip_html(html):
    text = re.sub(r'<[^>]+>', ' ', html)
    text = text.replace('&nbsp;',' ').replace('&amp;','&')
    return re.sub(r'&\w+;', '', text).replace('\r','')

def parse_numbered(text):
    """Parse 'N. text' numbered sections."""
    results = {}; current = None; buf = []
    def flush():
        if current is not None and buf:
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
            if s and current is not None and len(s) > 3: buf.append(s)
    flush()
    return results

def update_json(path, book_name, sections):
    data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"books":{}}
    data["books"][book_name] = sections
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    kb = path.stat().st_size // 1024
    total = sum(len(v) for v in data["books"].values())
    print(f"    ✓ {path} ({kb}KB, {len(data['books'])} books, {total} sections)")

def save(path, source, books):
    data = {"source": source, "books": books}
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    kb = path.stat().st_size // 1024
    total = sum(len(v) for v in books.values())
    print(f"    ✓ {path} ({kb}KB, {len(books)} books, {total} sections)")


# ── Porphyry: Life of Plotinus ────────────────────────────────────────────────

def fix_porphyry_life():
    print("\n── Porphyry: Life of Plotinus ───────────────────────────────────────")
    print("  Fetching...", end=" ", flush=True)
    html = fetch("https://sacred-texts.com/cla/plotenn/enn001.htm", delay=1.5)
    if not html: print("not found"); return
    text = strip_html(html)
    sects = parse_numbered(text)
    if not sects: print(f"no sections (got {len(text)} chars)"); return
    print(f"✓ {len(sects)}")
    update_json(OUT / "porphyry.json", "Life of Plotinus", sects)


# ── Hierocles: Commentary — single page ──────────────────────────────────────

def fix_hierocles():
    print("\n── Hierocles: Commentary on the Golden Verses ───────────────────────")
    print("  Fetching gvp04.htm...", end=" ", flush=True)
    html = fetch("https://sacred-texts.com/cla/gvp/gvp04.htm", delay=1.5)
    if not html: print("not found"); return
    text = strip_html(html)
    sects = parse_numbered(text)
    if not sects:
        # It's notes keyed by verse number — try to split by verse reference patterns
        # like "1, 2." or "1-3." at start of line
        results = {}; current = None; buf = []
        def flush2():
            if current is not None and buf:
                t = clean(" ".join(buf))
                if len(t) > 20: results[str(current)] = {"1": t}
        for line in text.split('\n'):
            m = re.match(r'^\s*(\d+)[\.,]\s+(.*)', line)
            if m:
                flush2(); buf = []; current = int(m.group(1))
                rest = m.group(2).strip()
                if rest: buf.append(rest)
            else:
                s = line.strip()
                if s and current is not None and len(s) > 3: buf.append(s)
        flush2()
        sects = results
    if not sects:
        # Store as single section
        lines = [l.strip() for l in text.split('\n') if l.strip() and len(l.strip()) > 30]
        t = clean(" ".join(lines))
        if len(t) > 100: sects = {"1": {"1": t}}
    if not sects: print("no content"); return
    print(f"✓ {len(sects)}")
    save(OUT / "hierocles.json",
         "Hierocles of Alexandria, Commentary on the Golden Verses (notes). Sacred-texts.com (public domain).",
         {"Commentary on the Golden Verses": sects})


# ── Pythagorean Sentences collection from gvp ────────────────────────────────
# These are all in the same volume as the Golden Verses on sacred-texts.com

GVP_WORKS = [
    ("Golden Sentences of Democrates",           "gvp05.htm"),
    ("Pythagorean Sentences of Demophilus",      "gvp06.htm"),
    ("Similitudes of Demophilus",                "gvp07.htm"),
    ("Pythagorean Sentences from Stobaeus",      "gvp08.htm"),
    ("Select Sentences of Sextus the Pythagorean", "gvp09.htm"),
    ("Pythagorean Sentences from Iamblichus",    "gvp10.htm"),
    ("Symbols of Pythagoras",                    "gvp11.htm"),
]

def build_pythagorean_sentences():
    print("\n── Pythagorean Sentences (sacred-texts gvp) ─────────────────────────")
    # Check if file exists already (from golden_verses.json or similar)
    path = OUT / "pythagorean_sentences.json"
    books = {}
    base = "https://sacred-texts.com/cla/gvp/"
    for title, fname in GVP_WORKS:
        print(f"  {title}...", end=" ", flush=True)
        html = fetch(base + fname, delay=1.0)
        if not html: print("not found"); continue
        text = strip_html(html)
        sects = parse_numbered(text)
        if not sects:
            # Try splitting on short intro lines
            lines = [l.strip() for l in text.split('\n') if l.strip() and len(l.strip()) > 20]
            t = clean(" ".join(lines))
            if len(t) > 100: sects = {"1": {"1": t}}
        if not sects: print("no content"); continue
        books[title] = sects
        print(f"✓ {len(sects)}")
    if books:
        save(path,
             "Various Pythagorean authors. Trans. Kenneth Sylvan Guthrie (1920). Sacred-texts.com (public domain).",
             books)


if __name__ == "__main__":
    fix_porphyry_life()
    fix_hierocles()
    build_pythagorean_sentences()
    print("\n✓ Done.")
