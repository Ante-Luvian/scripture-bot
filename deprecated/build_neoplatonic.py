"""
build_neoplatonic.py
====================
Builds JSON data for:
  - Julian the Apostate: Hymn to King Helios, Hymn to the Mother of the Gods,
                         Against the Galilaeans, The Caesars
  - Sallustius: On the Gods and the World
  - Proclus: Theology of Plato, Elements of Theology
  - Hierocles: Commentary on the Golden Verses  (sacred-texts)
  - Marinus: Life of Proclus  (tertullian.org)
  - Porphyry: Life of Plotinus  (tertullian.org)

Output: data/classical/julian.json, sallustius.json, proclus_theology.json,
        proclus_elements.json, hierocles.json, marinus.json,
        porphyry_life_of_plotinus.json

Usage: python build_neoplatonic.py
"""

import json, re, time, urllib.request, urllib.error
from pathlib import Path

OUT = Path("data/classical")
OUT.mkdir(parents=True, exist_ok=True)

# ── HTTP ───────────────────────────────────────────────────────────────────────

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
                wait = 60*(attempt+1); print(f"\n    429—waiting {wait}s..."); time.sleep(wait)
            elif e.code == 404: return None
            else: print(f"\n    HTTP {e.code}: {url}"); return None
        except Exception as ex: print(f"\n    {ex}"); return None
    return None

def clean(t): return re.sub(r"\s+", " ", t).strip()

def save(path, source, books):
    data = {"source": source, "books": books}
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    kb = path.stat().st_size // 1024
    total = sum(len(v) for v in books.values())
    print(f"    ✓ {path} ({kb}KB, {len(books)} books, {total} sections)")


# ── Parsers ────────────────────────────────────────────────────────────────────

def parse_html_sections(html, sec_pattern=r'^\s*(\d+)\.\s+(.*)'):
    """Generic numbered-section parser for HTML pages."""
    if not html: return {}
    text = re.sub(r'<[^>]+>', ' ', html)
    text = text.replace('&nbsp;',' ').replace('&amp;','&')
    text = re.sub(r'&\w+;', '', text).replace('\r','')
    results = {}; current = None; buf = []

    def flush():
        if current is not None and buf:
            t = clean(" ".join(buf))
            if len(t) > 20: results[str(current)] = {"1": t}

    sec_re = re.compile(sec_pattern)
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


def parse_sacred_texts_chapters(base_url, chapter_urls, chapter_key_fn=None):
    """
    Fetch multiple sacred-texts.com chapter pages and combine into one book dict.
    Returns {chapter_key: {"1": text}}  (one entry per chapter, full text).
    """
    results = {}
    for i, url in enumerate(chapter_urls, 1):
        html = fetch(url, delay=1.2)
        if not html: continue
        text = re.sub(r'<[^>]+>', ' ', html)
        text = text.replace('&nbsp;',' ').replace('&amp;','&')
        text = re.sub(r'&\w+;', '', text).replace('\r','')
        # Find the main body — strip nav headers/footers
        lines = [l.strip() for l in text.split('\n') if l.strip() and len(l.strip()) > 20]
        body = clean(" ".join(lines[:200]))  # first ~200 non-empty lines
        if len(body) > 50:
            key = chapter_key_fn(i) if chapter_key_fn else str(i)
            results[key] = {"1": body}
    return results


def strip_pg(text):
    """Strip Project Gutenberg header/footer."""
    text = text.replace('\r','')
    start = re.search(r'\*\*\* START OF THE PROJECT', text)
    if start: text = text[text.find('\n', start.start())+1:]
    end = re.search(r'\*\*\* END OF THE PROJECT', text)
    if end: text = text[:end.start()]
    return text


def parse_pg_by_book_chapter(text, book_re_str, chapter_re_str, has_chapters=True):
    """
    Parse a Gutenberg text into {book.chapter: {"1": text}} or {chapter: {"1": text}}.
    book_re: regex with group(1) = book number/name
    chapter_re: regex with group(1) = chapter number/name
    """
    text = strip_pg(text)
    results = {}
    book = None; chap = None; buf = []
    book_re = re.compile(book_re_str, re.IGNORECASE)
    chap_re = re.compile(chapter_re_str, re.IGNORECASE)

    ROMAN = {r:i for i,r in enumerate(['I','II','III','IV','V','VI','VII','VIII',
        'IX','X','XI','XII','XIII','XIV','XV','XVI','XVII','XVIII','XIX','XX',
        'XXI','XXII','XXIII','XXIV','XXV','XXVI','XXVII','XXVIII'],1)}

    def to_int(s):
        s = s.strip().upper()
        return ROMAN.get(s) or (int(s) if s.isdigit() else s)

    def flush():
        if chap is not None and buf:
            t = clean(" ".join(buf))
            if len(t) > 30:
                key = f"{book}.{chap}" if (has_chapters and book is not None) else str(chap)
                results[key] = {"1": t}

    blocks = re.split(r'\n{2,}', text)
    for block in blocks:
        b = block.strip()
        if not b: continue
        bm = book_re.match(b)
        cm = chap_re.match(b)
        if bm:
            flush(); buf = []; chap = None
            book = to_int(bm.group(1))
        elif cm:
            flush(); buf = []
            chap = to_int(cm.group(1))
        else:
            if chap is not None or (not has_chapters and book is not None):
                t = clean(b.replace('\n', ' '))
                if t: buf.append(t)
    flush()
    return results


# ══════════════════════════════════════════════════════════════════════════════
# JULIAN
# Source: sacred-texts.com (Taylor trans.) for Hymns
#         Wikisource (Wright trans.) for Against Galilaeans + Caesars
# ══════════════════════════════════════════════════════════════════════════════

JULIAN_SACRED_TEXTS = {
    "Hymn to King Helios":        "https://sacred-texts.com/cla/toj/toj03.htm",
    "Hymn to the Mother of Gods": "https://sacred-texts.com/cla/toj/toj04.htm",
    "Against the Galilaeans":     "https://sacred-texts.com/cla/toj/toj05.htm",
    "The Caesars":                "https://sacred-texts.com/cla/toj/toj06.htm",
}

def build_julian():
    print("\n── Julian ────────────────────────────────────────────────────────────")
    books = {}
    for title, url in JULIAN_SACRED_TEXTS.items():
        print(f"  {title}...", end=" ", flush=True)
        html = fetch(url, delay=1.5)
        if not html: print("not found"); continue
        sects = parse_html_sections(html)
        if not sects:
            # Fall back: whole text as one section
            text = re.sub(r'<[^>]+>', ' ', html)
            text = re.sub(r'&\w+;', '', text).replace('\r','')
            lines = [l.strip() for l in text.split('\n') if l.strip() and len(l.strip()) > 20]
            t = clean(" ".join(lines))
            if len(t) > 100:
                sects = {"1": {"1": t}}
        if not sects: print("no sections"); continue
        books[title] = sects
        print(f"✓ {len(sects)}")
    if books:
        save(OUT / "julian.json",
             "Julian the Apostate (Emperor), trans. Thomas Taylor (1793) & Wilmer Cave Wright (1913). Sacred-texts.com.",
             books)


# ══════════════════════════════════════════════════════════════════════════════
# SALLUSTIUS
# Source: sacred-texts.com — Murray translation, numbered chapters
# ══════════════════════════════════════════════════════════════════════════════

def build_sallustius():
    print("\n── Sallustius ────────────────────────────────────────────────────────")
    print("  On the Gods and the World...", end=" ", flush=True)

    # Try sacred-texts first (Murray trans.)
    html = fetch("https://sacred-texts.com/cla/sallu/sallu.htm", delay=1.0)
    if not html:
        html = fetch("https://hermetic.com/texts/on_the_gods-1", delay=1.0)

    if not html:
        print("not found"); return

    # Chapters labeled "I.", "II." etc. or numbered sections
    text = re.sub(r'<[^>]+>', ' ', html)
    text = text.replace('&nbsp;',' ').replace('&amp;','&')
    text = re.sub(r'&\w+;', '', text).replace('\r','')

    ROMAN = {r:i for i,r in enumerate(['I','II','III','IV','V','VI','VII','VIII',
        'IX','X','XI','XII','XIII','XIV','XV','XVI','XVII','XVIII','XIX','XX'],1)}

    results = {}; current = None; buf = []

    def flush():
        if current is not None and buf:
            t = clean(" ".join(buf))
            if len(t) > 20: results[str(current)] = {"1": t}

    blocks = re.split(r'\n{2,}', text)
    for block in blocks:
        b = block.strip()
        if not b: continue
        # Roman numeral chapter header
        rm = re.match(r'^([IVXLCDM]+)\.\s*(.*)', b, re.IGNORECASE)
        # Decimal chapter header "1." etc
        nm = re.match(r'^(\d+)\.\s+(.*)', b)
        if rm and rm.group(1).upper() in ROMAN:
            flush(); buf = []
            current = ROMAN[rm.group(1).upper()]
            rest = rm.group(2).strip()
            if rest: buf.append(clean(rest.replace('\n',' ')))
        elif nm:
            flush(); buf = []
            current = int(nm.group(1))
            rest = nm.group(2).strip()
            if rest: buf.append(clean(rest.replace('\n',' ')))
        else:
            if current is not None:
                t = clean(b.replace('\n',' '))
                if t: buf.append(t)
    flush()

    if not results:
        print("no sections"); return
    print(f"✓ {len(results)}")
    save(OUT / "sallustius.json",
         "Sallustius, On the Gods and the World. Trans. Gilbert Murray (1925). Public domain.",
         {"On the Gods and the World": results})


# ══════════════════════════════════════════════════════════════════════════════
# PROCLUS — Theology of Plato + Elements of Theology
# Source: Gutenberg #77393 (Taylor trans., both in same volume)
# ══════════════════════════════════════════════════════════════════════════════

def build_proclus_theology():
    print("\n── Proclus: Theology of Plato ────────────────────────────────────────")
    print("  Fetching Gutenberg #77393...", end=" ", flush=True)
    text = fetch("https://www.gutenberg.org/cache/epub/77393/pg77393.txt", delay=2.0, timeout=40)
    if not text:
        print("not found"); return
    text = strip_pg(text)
    print(f"got {len(text)//1024}KB")

    # Theology of Plato: "BOOK I.", "BOOK II." ... "BOOK VI."
    # Chapters within: "CHAP. I.", "CHAP. II." etc.
    # Elements of Theology comes after, labeled differently

    # Split off Elements of Theology
    elem_marker = re.search(r'ELEMENTS?\s+OF\s+THEOLOGY', text, re.IGNORECASE)
    if elem_marker:
        theology_text = text[:elem_marker.start()]
        elements_text = text[elem_marker.start():]
    else:
        theology_text = text
        elements_text = ""

    # Parse Theology of Plato
    print("  Parsing Theology of Plato...", end=" ", flush=True)
    theol = parse_pg_by_book_chapter(
        theology_text,
        book_re_str    = r'^BOOK\s+([IVXLCDM]+)\.?\s*$',
        chapter_re_str = r'^CHAP(?:TER)?\.?\s+([IVXLCDM\d]+)\.?\s*$',
        has_chapters   = True,
    )
    print(f"✓ {len(theol)}")

    # Parse Elements of Theology
    print("  Parsing Elements of Theology...", end=" ", flush=True)
    # Propositions labeled "PROP. I.", "PROP. II." etc.
    elem = {}
    if elements_text:
        elem = parse_pg_by_book_chapter(
            elements_text,
            book_re_str    = r'^(?:PROP(?:OSITION)?\.?\s+)([IVXLCDM\d]+)\.?\s*$',
            chapter_re_str = r'^(?:COROLLARY|SCHOLIUM|NOTE)\s*$',
            has_chapters   = False,
        )
        if not elem:
            # Try flat numbered propositions
            blocks = re.split(r'\n{2,}', strip_pg(elements_text))
            current = None; buf = []
            for block in blocks:
                b = block.strip()
                pm = re.match(r'^PROP(?:OSITION)?\.?\s+([IVXLCDM\d]+)\.?\s*$', b, re.IGNORECASE)
                if pm:
                    if current and buf:
                        t = clean(" ".join(buf))
                        if len(t)>20: elem[str(current)] = {"1": t}
                    buf = []; current = pm.group(1)
                elif current:
                    t = clean(b.replace('\n',' '))
                    if t: buf.append(t)
            if current and buf:
                t = clean(" ".join(buf))
                if len(t)>20: elem[str(current)] = {"1": t}
    print(f"✓ {len(elem)}")

    books = {}
    if theol: books["Theology of Plato"] = theol
    if elem:  books["Elements of Theology"] = elem

    if books:
        save(OUT / "proclus_theology.json",
             "Proclus, Theology of Plato & Elements of Theology. Trans. Thomas Taylor (1816). Gutenberg #77393.",
             books)


# ══════════════════════════════════════════════════════════════════════════════
# HIEROCLES — Commentary on the Golden Verses
# Source: sacred-texts.com
# ══════════════════════════════════════════════════════════════════════════════

def build_hierocles():
    print("\n── Hierocles ─────────────────────────────────────────────────────────")
    print("  Commentary on the Golden Verses...", end=" ", flush=True)

    # sacred-texts has this as individual chapter pages
    base = "https://sacred-texts.com/cla/hgv/"
    index_html = fetch(base + "index.htm", delay=1.0)
    if not index_html:
        index_html = fetch(base, delay=1.0)

    if index_html:
        # Find chapter links
        links = re.findall(r'href="(hgv\d+\.htm)"', index_html, re.IGNORECASE)
        links = sorted(set(links))
    else:
        # Generate them
        links = [f"hgv{i:02d}.htm" for i in range(1, 30)]

    results = {}
    for link in links:
        url = base + link
        html = fetch(url, delay=1.0)
        if not html: continue
        sects = parse_html_sections(html)
        for k, v in sects.items():
            # Offset by link number to avoid collisions
            results[k] = v
        if sects:
            num = re.search(r'\d+', link)
            print(f"  {num.group() if num else link}:{len(sects)}", end=" ", flush=True)

    if not results:
        # Try direct Taylor translation from sacred-texts
        html = fetch("https://sacred-texts.com/cla/gvp/gvp04.htm", delay=1.0)
        sects = parse_html_sections(html)
        if sects: results = sects

    if not results:
        print("not found"); return
    print(f"\n  Total: {len(results)}")
    save(OUT / "hierocles.json",
         "Hierocles of Alexandria, Commentary on the Golden Verses. Trans. N. Rowe (1906). Sacred-texts.com.",
         {"Commentary on the Golden Verses": results})


# ══════════════════════════════════════════════════════════════════════════════
# MARINUS — Life of Proclus
# Source: tertullian.org
# ══════════════════════════════════════════════════════════════════════════════

def build_marinus():
    print("\n── Marinus: Life of Proclus ─────────────────────────────────────────")
    print("  Fetching...", end=" ", flush=True)
    html = fetch("https://www.tertullian.org/fathers/marinus_life_of_proclus_02_text.htm", delay=1.5)
    if not html: print("not found"); return
    sects = parse_html_sections(html)
    if not sects: print("no sections"); return
    print(f"✓ {len(sects)}")
    save(OUT / "marinus.json",
         "Marinus of Neapolis, Life of Proclus. Trans. Kenneth S. Guthrie (1925). Tertullian.org.",
         {"Life of Proclus": sects})


# ══════════════════════════════════════════════════════════════════════════════
# PORPHYRY — Life of Plotinus
# (already on tertullian.org, companion to the Enneads)
# ══════════════════════════════════════════════════════════════════════════════

def build_porphyry_life_plotinus():
    print("\n── Porphyry: Life of Plotinus ───────────────────────────────────────")
    print("  Fetching...", end=" ", flush=True)
    html = fetch("https://www.tertullian.org/fathers/porphyry_life_of_plotinus_02_text.htm", delay=1.5)
    if not html: print("not found"); return
    sects = parse_html_sections(html)
    if not sects: print("no sections"); return
    print(f"✓ {len(sects)}")

    # Merge into existing porphyry.json
    path = OUT / "porphyry.json"
    if path.exists():
        data = json.loads(path.read_text(encoding="utf-8"))
        data["books"]["Life of Plotinus"] = sects
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        kb = path.stat().st_size // 1024
        total = sum(len(v) for v in data["books"].values())
        print(f"    ✓ Updated porphyry.json ({kb}KB, {len(data['books'])} books, {total} sections)")
    else:
        save(path,
             "Porphyry. Trans. Thomas Taylor. Tertullian.org (public domain).",
             {"Life of Plotinus": sects})


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    build_julian()
    build_sallustius()
    build_proclus_theology()
    build_hierocles()
    build_marinus()
    build_porphyry_life_plotinus()
    print("\n✓ Done.")
