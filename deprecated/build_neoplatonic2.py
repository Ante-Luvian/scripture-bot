"""
build_neoplatonic2.py — fixes and additions for missing items
Run: python build_neoplatonic2.py

Fixes:
  - Julian: Caesars (correct URL), numbered sections for Hymns
  - Proclus Theology: Gutenberg timed out, use archive.org mirror
  - Hierocles: fetch all chapter pages properly
  - Marinus Life of Proclus: correct URL
  - Porphyry Life of Plotinus: correct URL
"""

import json, re, time, urllib.request, urllib.error
from pathlib import Path

OUT = Path("data/classical")


def fetch(url, delay=1.0, timeout=30):
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
            else: print(f"\n    HTTP {e.code}: {url}"); return None
        except Exception as ex:
            if attempt == 2: print(f"\n    {ex}")
            else: time.sleep(10)
    return None


def clean(t): return re.sub(r"\s+", " ", t).strip()


def strip_html(html):
    text = re.sub(r'<[^>]+>', ' ', html)
    text = text.replace('&nbsp;',' ').replace('&amp;','&')
    return re.sub(r'&\w+;', '', text).replace('\r','')


def parse_numbered_sections(text):
    """Parse 'N. text...' numbered sections from plain text."""
    results = {}; current = None; buf = []

    def flush():
        if current is not None and buf:
            t = clean(" ".join(buf))
            if len(t) > 20: results[str(current)] = {"1": t}

    sec_re = re.compile(r'^\s*(\d+)\.\s+(.*)')
    for line in text.split('\n'):
        m = sec_re.match(line)
        if m:
            flush(); buf = []
            current = int(m.group(1))
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


# ── Julian: fix Caesars URL + re-parse hymns with paragraph numbers ─────────────

JULIAN_URLS = {
    "Hymn to King Helios":        "https://sacred-texts.com/cla/toj/toj03.htm",
    "Hymn to the Mother of Gods": "https://sacred-texts.com/cla/toj/toj04.htm",
    "Against the Galilaeans":     "https://sacred-texts.com/cla/toj/toj05.htm",
    "The Caesars":                "https://sacred-texts.com/cla/toj/toj02.htm",
}

def fix_julian():
    print("\n── Julian (fix) ──────────────────────────────────────────────────────")
    books = {}
    for title, url in JULIAN_URLS.items():
        print(f"  {title}...", end=" ", flush=True)
        html = fetch(url, delay=1.5)
        if not html: print("not found"); continue
        text = strip_html(html)
        sects = parse_numbered_sections(text)
        if not sects:
            # Store whole text as single section
            lines = [l.strip() for l in text.split('\n') if l.strip() and len(l.strip()) > 20]
            t = clean(" ".join(lines))
            if len(t) > 100:
                sects = {"1": {"1": t}}
        if not sects: print("no content"); continue
        books[title] = sects
        print(f"✓ {len(sects)}")

    if books:
        save(OUT / "julian.json",
             "Julian the Apostate, trans. Thomas Taylor (1793) & Wilmer Cave Wright (1913). Sacred-texts.com.",
             books)


# ── Marinus: Life of Proclus — correct URL ────────────────────────────────────

def fix_marinus():
    print("\n── Marinus: Life of Proclus ─────────────────────────────────────────")
    print("  Fetching...", end=" ", flush=True)
    html = fetch("https://www.tertullian.org/fathers/marinus_01_life_of_proclus.htm", delay=1.5)
    if not html: print("not found"); return
    text = strip_html(html)
    sects = parse_numbered_sections(text)
    if not sects: print("no sections"); return
    print(f"✓ {len(sects)}")
    save(OUT / "marinus.json",
         "Marinus of Neapolis, Life of Proclus. Trans. K.S. Guthrie (1925). Tertullian.org.",
         {"Life of Proclus": sects})


# ── Porphyry: Life of Plotinus — from sacred-texts (MacKenna trans.) ──────────

def fix_porphyry_life():
    print("\n── Porphyry: Life of Plotinus ───────────────────────────────────────")
    # sacred-texts has MacKenna's translation as part of the Plotinus Enneads
    print("  Fetching...", end=" ", flush=True)
    html = fetch("https://sacred-texts.com/cla/plotenn/plotenn01.htm", delay=1.5)
    if not html:
        html = fetch("https://www.tertullian.org/fathers/porphyry_life_plotinus_02_text.htm", delay=1.5)
    if not html: print("not found"); return
    text = strip_html(html)
    sects = parse_numbered_sections(text)
    if not sects:
        # Try paragraph-break splitting
        blocks = re.split(r'\n{2,}', text)
        for i, b in enumerate(blocks[:5], 1):
            print(f"\n  block {i}: {b[:80]!r}")
    if not sects: print("no sections"); return
    print(f"✓ {len(sects)}")
    path = OUT / "porphyry.json"
    update_json(path, "Life of Plotinus", sects)


# ── Hierocles: fetch all chapter pages ───────────────────────────────────────

def fix_hierocles():
    print("\n── Hierocles: Commentary on the Golden Verses ───────────────────────")
    # sacred-texts has individual pages hgv01.htm through hgv28.htm or so
    base = "https://sacred-texts.com/cla/hgv/"
    results = {}
    chap_num = 0
    for i in range(1, 35):
        url = f"{base}hgv{i:02d}.htm"
        html = fetch(url, delay=0.8)
        if not html: break
        text = strip_html(html)
        # Each page is one chapter — strip boilerplate and store as one section
        lines = [l.strip() for l in text.split('\n') if l.strip() and len(l.strip()) > 20]
        # Skip nav lines (short lines at top/bottom)
        content_lines = [l for l in lines if len(l) > 40]
        if not content_lines: continue
        chap_num += 1
        t = clean(" ".join(content_lines))
        if len(t) > 50:
            results[str(chap_num)] = {"1": t}
        print(f"  {i}:{len(t)//100}00chars", end=" ", flush=True)

    if not results:
        print("\n  not found"); return
    print(f"\n  Total chapters: {len(results)}")
    save(OUT / "hierocles.json",
         "Hierocles of Alexandria, Commentary on the Golden Verses. Trans. N. Rowe (1906). Sacred-texts.com.",
         {"Commentary on the Golden Verses": results})


# ── Proclus Theology: try archive.org plain text ─────────────────────────────

def fix_proclus_theology():
    print("\n── Proclus Theology of Plato ────────────────────────────────────────")
    print("  Trying archive.org...", end=" ", flush=True)

    # Try archive.org text version
    urls = [
        "https://archive.org/stream/sixbooksofproclus01procuoft/sixbooksofproclus01procuoft_djvu.txt",
        "https://www.gutenberg.org/files/77393/77393-0.txt",
    ]
    text = None
    for url in urls:
        text = fetch(url, delay=2.0, timeout=40)
        if text and len(text) > 10000:
            print(f"got {len(text)//1024}KB from {url.split('/')[2]}")
            break
    if not text:
        print("not found — skipping (will try again later)")
        return

    text = text.replace('\r','')
    # Strip PG wrapper if present
    start = re.search(r'\*\*\* START OF THE PROJECT', text)
    if start: text = text[text.find('\n', start.start())+1:]
    end = re.search(r'\*\*\* END OF THE PROJECT', text)
    if end: text = text[:end.start()]

    ROMAN = {r:i for i,r in enumerate(['I','II','III','IV','V','VI','VII','VIII',
        'IX','X','XI','XII','XIII','XIV','XV','XVI','XVII','XVIII','XIX','XX',
        'XXI','XXII','XXIII','XXIV','XXV'],1)}

    def to_num(s):
        s = s.strip().upper()
        return ROMAN.get(s) or (int(s) if s.isdigit() else s)

    theol = {}; book = None; chap = None; buf = []

    def flush():
        if chap is not None and buf:
            t = clean(" ".join(buf))
            if len(t) > 30:
                key = f"{book}.{chap}" if book else str(chap)
                theol[key] = {"1": t}

    book_re = re.compile(r'^BOOK\s+([IVXLCDM]+)\.?\s*$', re.IGNORECASE)
    chap_re = re.compile(r'^CHAP(?:TER)?\.?\s+([IVXLCDM\d]+)\.?\s*$', re.IGNORECASE)

    for block in re.split(r'\n{2,}', text):
        b = block.strip()
        if not b: continue
        bm = book_re.match(b); cm = chap_re.match(b)
        if bm:
            flush(); buf = []; chap = None; book = to_num(bm.group(1))
        elif cm:
            flush(); buf = []; chap = to_num(cm.group(1))
        else:
            if chap is not None:
                t = clean(b.replace('\n',' '))
                if t: buf.append(t)
    flush()

    print(f"  Theology of Plato: {len(theol)} sections")
    if theol:
        save(OUT / "proclus_theology.json",
             "Proclus, Theology of Plato. Trans. Thomas Taylor (1816). Public domain.",
             {"Theology of Plato": theol})


if __name__ == "__main__":
    fix_julian()
    fix_marinus()
    fix_porphyry_life()
    fix_hierocles()
    fix_proclus_theology()
    print("\n✓ Done.")
