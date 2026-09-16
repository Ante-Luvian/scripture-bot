"""
fix_json.py — rebuild all broken neoplatonic JSON files from scratch
Run: python fix_json.py
"""
import json, re, time, urllib.request, urllib.error
from pathlib import Path

OUT = Path("data/classical")

def fetch(url, delay=1.0, timeout=30):
    for attempt in range(4):
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": "Mozilla/5.0 (compatible; ScriptureBot/1.0)"
            })
            with urllib.request.urlopen(req, timeout=timeout) as r:
                raw = r.read()
            time.sleep(delay)
            return raw.decode("utf-8", errors="replace")
        except urllib.error.HTTPError as e:
            if e.code == 429:
                wait = 60*(attempt+1); print(f"\n    429—{wait}s..."); time.sleep(wait)
            elif e.code == 404: return None
            else: print(f"\n    HTTP {e.code}: {url}"); return None
        except Exception as ex:
            if attempt < 3: time.sleep(8)
            else: print(f"\n    {ex}"); return None
    return None

def clean(t):
    t = re.sub(r"\s+", " ", t)
    return t.strip()

def strip_html(html):
    # Remove script and style blocks entirely
    html = re.sub(r'<script[^>]*>.*?</script>', ' ', html, flags=re.DOTALL|re.IGNORECASE)
    html = re.sub(r'<style[^>]*>.*?</style>', ' ', html, flags=re.DOTALL|re.IGNORECASE)
    # Remove tags
    html = re.sub(r'<[^>]+>', ' ', html)
    # Decode common entities
    html = html.replace('&nbsp;',' ').replace('&amp;','&').replace('&lt;','<').replace('&gt;','>')
    html = html.replace('&#39;',"'").replace('&quot;','"')
    # Remove remaining entities
    html = re.sub(r'&#x[0-9a-fA-F]+;', '', html)
    html = re.sub(r'&#\d+;', '', html)
    html = re.sub(r'&\w+;', '', html)
    return html.replace('\r','')

def parse_numbered(text, min_len=30):
    """Parse 'N. text' numbered sections, accumulating across blank lines."""
    results = {}; current = None; buf = []
    def flush():
        if current is not None and buf:
            t = clean(" ".join(buf))
            if len(t) >= min_len:
                results[str(current)] = {"1": t}
    sec_re = re.compile(r'^\s*(\d+)\.\s+(.*)')
    for line in text.split('\n'):
        m = sec_re.match(line)
        if m:
            flush(); buf = []; current = int(m.group(1))
            rest = m.group(2).strip()
            if rest: buf.append(rest)
        else:
            s = line.strip()
            # Skip short lines, nav cruft, and JSON-LD garbage
            if (s and current is not None and len(s) > 4
                    and not s.startswith('@') and not s.startswith('{')):
                buf.append(s)
    flush()
    return results

def save(path, source, books):
    data = {"source": source, "books": books}
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    kb = path.stat().st_size // 1024
    total = sum(len(v) for v in books.values())
    print(f"    ✓ {path} ({kb}KB, {len(books)} books, {total} sections)")

def update(path, book_name, sections):
    data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"books":{}}
    data["books"][book_name] = sections
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    kb = path.stat().st_size // 1024
    total = sum(len(v) for v in data["books"].values())
    print(f"    ✓ {path} ({kb}KB, {len(data['books'])} books, {total} sections)")


# ══════════════════════════════════════════════════════════════════════════════
# JULIAN — fetch from Tertullian.org (Taylor translation, clean HTML)
# ══════════════════════════════════════════════════════════════════════════════

JULIAN_URLS = {
    "Hymn to King Helios":        "https://www.tertullian.org/fathers/julian_apostate_1_sun.htm",
    "Hymn to the Mother of Gods": "https://www.tertullian.org/fathers/julian_apostate_2_mother.htm",
    "Against the Galilaeans":     "https://www.tertullian.org/fathers/julian_apostate_against_galileans.htm",
    "The Caesars":                "https://www.tertullian.org/fathers/julian_apostate_caesars.htm",
}

def fix_julian():
    print("\n── Julian ────────────────────────────────────────────────────────────")
    books = {}
    for title, url in JULIAN_URLS.items():
        print(f"  {title}...", end=" ", flush=True)
        html = fetch(url, delay=1.5)
        if not html: print("not found"); continue
        text = strip_html(html)
        sects = parse_numbered(text)
        if not sects:
            # Store as single section — long prose without numbering
            lines = [l.strip() for l in text.split('\n')
                     if l.strip() and len(l.strip()) > 40
                     and not l.strip().startswith('@')]
            t = clean(" ".join(lines))
            # Strip obvious header/footer boilerplate
            t = re.sub(r'^.*?(?:JULIAN|Julian|Apostate)', '', t).strip()
            if len(t) > 200:
                sects = {"1": {"1": t}}
        if not sects: print("no content"); continue
        books[title] = sects
        print(f"✓ {len(sects)}")

    if books:
        save(OUT / "julian.json",
             "Julian the Apostate. Trans. Thomas Taylor (1793). Tertullian.org (public domain).",
             books)


# ══════════════════════════════════════════════════════════════════════════════
# PORPHYRY — fix On Abstinence (HTML entities) and Auxiliaries
# Re-fetch from Tertullian.org, strip entities properly
# ══════════════════════════════════════════════════════════════════════════════

PORPHYRY_URLS = {
    "On Abstinence": [
        ("1", "https://www.tertullian.org/fathers/porphyry_abstinence_01_book1.htm"),
        ("2", "https://www.tertullian.org/fathers/porphyry_abstinence_02_book2.htm"),
        ("3", "https://www.tertullian.org/fathers/porphyry_abstinence_03_book3.htm"),
        ("4", "https://www.tertullian.org/fathers/porphyry_abstinence_04_book4.htm"),
    ],
    "Life of Pythagoras": [
        ("1", "https://www.tertullian.org/fathers/porphyry_life_of_pythagoras_02_text.htm"),
    ],
    "On the Cave of the Nymphs": [
        ("1", "https://www.tertullian.org/fathers/porphyry_cave_of_nymphs_02_translation.htm"),
    ],
    "Letter to Marcella": [
        ("1", "https://www.tertullian.org/fathers/porphyry_marcella_02_text.htm"),
    ],
    "Auxiliaries to the Intelligibles": [
        ("1", "https://www.tertullian.org/fathers/porphyry_sententiae_02_trans.htm"),
    ],
}

def fix_porphyry():
    print("\n── Porphyry ──────────────────────────────────────────────────────────")
    books = {}

    for work_title, parts in PORPHYRY_URLS.items():
        work_sects = {}
        for book_num, url in parts:
            print(f"  {work_title} §{book_num}...", end=" ", flush=True)
            html = fetch(url, delay=1.5)
            if not html: print("not found"); continue
            text = strip_html(html)
            sects = parse_numbered(text)
            if not sects: print("no sections"); continue
            if len(parts) > 1:
                for k, v in sects.items():
                    work_sects[f"{book_num}.{k}"] = v
            else:
                work_sects.update(sects)
            print(f"✓ {len(sects)}")
        if work_sects:
            books[work_title] = work_sects

    # Life of Plotinus — from sacred-texts, MacKenna trans.
    # Each section is clearly numbered 1-38
    print(f"  Life of Plotinus...", end=" ", flush=True)
    html = fetch("https://sacred-texts.com/cla/plotenn/enn001.htm", delay=1.5)
    if html:
        text = strip_html(html)
        sects = parse_numbered(text)
        if sects:
            books["Life of Plotinus"] = sects
            print(f"✓ {len(sects)}")
        else:
            print("no sections")

    if books:
        save(OUT / "porphyry.json",
             "Porphyry. Trans. Thomas Taylor (1823) & Stephen MacKenna (1917). Tertullian.org / sacred-texts.com.",
             books)


# ══════════════════════════════════════════════════════════════════════════════
# MARINUS — re-fetch, sections are numbered clearly in the Tertullian text
# ══════════════════════════════════════════════════════════════════════════════

def fix_marinus():
    print("\n── Marinus ───────────────────────────────────────────────────────────")
    print("  Life of Proclus...", end=" ", flush=True)
    html = fetch("https://www.tertullian.org/fathers/marinus_01_life_of_proclus.htm", delay=1.5)
    if not html: print("not found"); return
    text = strip_html(html)
    sects = parse_numbered(text)
    if not sects: print("no sections"); return
    print(f"✓ {len(sects)}")
    save(OUT / "marinus.json",
         "Marinus of Neapolis, Life of Proclus. Trans. K.S. Guthrie (1925). Tertullian.org.",
         {"Life of Proclus": sects})


# ══════════════════════════════════════════════════════════════════════════════
# PROCLUS THEOLOGY — Gutenberg text, already worked (191 sections)
# Problem: sections are chapter headings. The actual content follows.
# Re-parse using paragraph blocks, not just chapter title lines.
# ══════════════════════════════════════════════════════════════════════════════

def fix_proclus_theology():
    print("\n── Proclus Theology of Plato ────────────────────────────────────────")
    print("  Fetching...", end=" ", flush=True)
    text = fetch("https://www.gutenberg.org/files/77393/77393-0.txt", delay=2.0, timeout=45)
    if not text:
        text = fetch("https://www.gutenberg.org/cache/epub/77393/pg77393.txt", delay=2.0, timeout=45)
    if not text: print("failed"); return
    text = text.replace('\r','')

    # Strip PG wrapper
    start = re.search(r'\*\*\* START OF THE PROJECT', text)
    if start: text = text[text.find('\n', start.start())+1:]
    end = re.search(r'\*\*\* END OF THE PROJECT', text)
    if end: text = text[:end.start()]

    ROMAN = {r:i for i,r in enumerate(['I','II','III','IV','V','VI','VII','VIII',
        'IX','X','XI','XII','XIII','XIV','XV','XVI','XVII','XVIII','XIX','XX',
        'XXI','XXII','XXIII','XXIV','XXV','XXVI','XXVII','XXVIII','XXIX','XXX'],1)}

    def to_num(s):
        s = s.strip().upper()
        return ROMAN.get(s) or (int(s) if s.isdigit() else s)

    theol = {}; book = None; chap = None; chap_title = None; buf = []

    def flush():
        if book is not None and chap is not None and buf:
            t = clean(" ".join(buf))
            if len(t) > 50:
                key = f"{book}.{chap}"
                # Prepend chapter title if we have one
                if chap_title:
                    t = f"{chap_title} — {t}"
                theol[key] = {"1": t}

    book_re = re.compile(r'^BOOK\s+([IVXLCDM]+)\.?\s*$', re.IGNORECASE)
    chap_re = re.compile(r'^CHAP(?:TER)?\.?\s+([IVXLCDM\d]+)\.?\s*$', re.IGNORECASE)

    blocks = re.split(r'\n{2,}', text)
    i = 0
    while i < len(blocks):
        b = blocks[i].strip()
        i += 1
        if not b: continue

        bm = book_re.match(b)
        cm = chap_re.match(b)

        if bm:
            flush(); buf = []; chap = None; chap_title = None
            book = to_num(bm.group(1))
        elif cm:
            flush(); buf = []; chap_title = None
            chap = to_num(cm.group(1))
            # Next block is often the chapter title (all caps or sentence)
            if i < len(blocks):
                next_b = blocks[i].strip()
                if next_b and not book_re.match(next_b) and not chap_re.match(next_b):
                    chap_title = clean(next_b.replace('\n',' '))
                    i += 1  # consume it
        else:
            if book is not None and chap is not None:
                t = clean(b.replace('\n',' '))
                if t and len(t) > 20: buf.append(t)

    flush()
    print(f"✓ {len(theol)} sections")
    save(OUT / "proclus_theology.json",
         "Proclus, Theology of Plato. Trans. Thomas Taylor (1816). Gutenberg #77393.",
         {"Theology of Plato": theol})


# ══════════════════════════════════════════════════════════════════════════════
# HIEROCLES — rebuild as verse-by-verse commentary
# The page has notes keyed by verse numbers, e.g. "1.", "7, 8.", "45."
# We'll store each note block as a section keyed sequentially
# ══════════════════════════════════════════════════════════════════════════════

def fix_hierocles():
    print("\n── Hierocles ─────────────────────────────────────────────────────────")
    print("  Fetching...", end=" ", flush=True)
    html = fetch("https://sacred-texts.com/cla/gvp/gvp04.htm", delay=1.5)
    if not html: print("not found"); return
    text = strip_html(html)

    # Sections are keyed by verse number: "1.", "7, 8.", "11, 12." etc.
    # We use verse start number as key
    results = {}; current = None; buf = []
    def flush():
        if current is not None and buf:
            t = clean(" ".join(buf))
            if len(t) > 20:
                results[str(current)] = {"1": t}

    # Match verse references like "1.", "7, 8.", "21-23.", "45."
    verse_re = re.compile(r'^\s*(\d+)(?:[\s,\-]+\d+)*\.\s+(.*)')

    for line in text.split('\n'):
        m = verse_re.match(line)
        if m:
            flush(); buf = []
            current = int(m.group(1))
            rest = m.group(2).strip()
            if rest and not rest.startswith('@') and not rest.startswith('{'):
                buf.append(rest)
        else:
            s = line.strip()
            if (s and current is not None and len(s) > 4
                    and not s.startswith('@') and not s.startswith('{')):
                buf.append(s)

    flush()
    # Remove any JS/schema garbage that crept in
    results = {k: v for k, v in results.items()
               if len(v["1"]) > 30 and '@context' not in v["1"]}

    if not results: print("no sections"); return
    print(f"✓ {len(results)}")
    save(OUT / "hierocles.json",
         "Hierocles of Alexandria, Commentary on the Golden Verses. Sacred-texts.com (public domain).",
         {"Commentary on the Golden Verses": results})


# ══════════════════════════════════════════════════════════════════════════════
# PYTHAGOREAN SENTENCES — fix Symbols of Pythagoras (schema garbage)
# ══════════════════════════════════════════════════════════════════════════════

def fix_pythagorean_sentences():
    print("\n── Pythagorean Sentences (fix Symbols) ──────────────────────────────")
    path = OUT / "pythagorean_sentences.json"
    data = json.loads(path.read_text(encoding="utf-8"))

    print("  Symbols of Pythagoras...", end=" ", flush=True)
    html = fetch("https://sacred-texts.com/cla/gvp/gvp11.htm", delay=1.0)
    if not html: print("not found"); return
    text = strip_html(html)
    sects = parse_numbered(text)
    if not sects:
        # Symbols are short aphorisms, may not be numbered — try splitting on lines
        lines = [l.strip() for l in text.split('\n')
                 if l.strip() and len(l.strip()) > 20
                 and not l.strip().startswith('@')]
        # Find content start (after boilerplate)
        content = []
        in_content = False
        for l in lines:
            if 'Symbols' in l or 'Pythagoras' in l:
                in_content = True
            if in_content and len(l) > 30:
                content.append(l)
        sects = {str(i): {"1": l} for i, l in enumerate(content[:100], 1) if len(l) > 20}

    data["books"]["Symbols of Pythagoras"] = sects
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    kb = path.stat().st_size // 1024
    total = sum(len(v) for v in data["books"].values())
    print(f"✓ {len(sects)} | {path} ({kb}KB, {len(data['books'])} books, {total} sections)")


if __name__ == "__main__":
    fix_julian()
    fix_porphyry()
    fix_marinus()
    fix_proclus_theology()
    fix_hierocles()
    fix_pythagorean_sentences()
    print("\n✓ Done.")
