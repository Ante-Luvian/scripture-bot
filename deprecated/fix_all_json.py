"""
fix_all_json.py — systematic fix for all quality issues
Run: python fix_all_json.py
"""
import json, re, time, urllib.request, urllib.error
from pathlib import Path

OUT = Path("data/classical")

def fetch(url, delay=1.0, timeout=35):
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
    return re.sub(r"\s+", " ", t).strip()

def strip_html(html):
    html = re.sub(r'<script[^>]*>.*?</script>', ' ', html, flags=re.DOTALL|re.IGNORECASE)
    html = re.sub(r'<style[^>]*>.*?</style>', ' ', html, flags=re.DOTALL|re.IGNORECASE)
    html = re.sub(r'<[^>]+>', ' ', html)
    for ent, rep in [('&nbsp;',' '),('&amp;','&'),('&lt;','<'),('&gt;','>'),
                     ('&#39;',"'"),('&quot;','"')]:
        html = html.replace(ent, rep)
    html = re.sub(r'&#x[0-9a-fA-F]+;', '', html)
    html = re.sub(r'&#\d+;', '', html)
    html = re.sub(r'&\w+;', '', html)
    return html.replace('\r','')

def is_garbage(text):
    """True if this text is nav/schema/footnote/boilerplate garbage."""
    t = text.strip()
    return (
        '@context' in t or 'BreadcrumbList' in t or
        t.startswith('{') or
        'Internet Sacred Text Archive' in t and len(t) < 200 or
        'All material on this page is in the public domain' in t or
        'copy freely' in t and len(t) < 300 or
        'Sacred Texts | Classics' in t or
        'Next: ' in t and len(t) < 150 or
        len(t) < 20
    )

def is_footnote(text):
    """True if this looks like a translator's footnote (starts with number+space or *)."""
    t = text.strip()
    return bool(re.match(r'^\d+\s+[A-Z]', t) or t.startswith('* ') or
                (re.match(r'^\d+\s', t) and len(t) < 200))

def save(path, source, books):
    data = {"source": source, "books": books}
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    kb = path.stat().st_size // 1024
    total = sum(len(v) for v in books.values())
    print(f"    ✓ {path} ({kb}KB, {len(books)} books, {total} sections)")

def update(path, updates):
    """Update specific books in existing JSON."""
    data = json.loads(path.read_text(encoding="utf-8"))
    data["books"].update(updates)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    kb = path.stat().st_size // 1024
    total = sum(len(v) for v in data["books"].values())
    print(f"    ✓ {path} ({kb}KB, {len(data['books'])} books, {total} sections)")

# ══════════════════════════════════════════════════════════════════════════════
# Generic numbered-section parser with footnote and garbage filtering
# ══════════════════════════════════════════════════════════════════════════════

def parse_sections(text, min_content=60, skip_footnotes=True):
    """
    Parse numbered sections, filtering out footnotes and garbage.
    A real section has substantial text (>min_content chars after stripping footnotes).
    """
    results = {}; current = None; buf = []; in_footnotes = False

    def flush():
        if current is not None and buf:
            t = clean(" ".join(buf))
            if len(t) >= min_content and not is_garbage(t):
                results[str(current)] = {"1": t}

    sec_re = re.compile(r'^\s*(\d+)\.\s+(.*)')

    for line in text.split('\n'):
        s = line.strip()
        if not s:
            continue

        # Stop at obvious footer markers
        if any(x in s for x in ['All material on this page', 'copy freely',
                                  'Sacred Texts | Classics', 'Internet Sacred Text Archive'
                                  ]) and len(s) < 300:
            break

        m = sec_re.match(s)
        if m:
            num = int(m.group(1))
            rest = m.group(2).strip()

            # Is this a footnote? Footnotes tend to be short and follow the main text
            # Heuristic: if we already have content and the number resets small, it's footnotes
            if skip_footnotes and current is not None and num < current and len(buf) > 2:
                # This is a footnote section restart — stop collecting
                break

            flush(); buf = []; current = num; in_footnotes = False
            if rest and not is_garbage(rest):
                buf.append(rest)
        elif s and current is not None:
            if is_garbage(s):
                continue
            # Skip lines that look like footnote numbers (e.g. "1 For the saying..." short)
            if skip_footnotes and re.match(r'^\d{1,3}\s+[A-Z]', s) and len(s) < 300:
                continue
            buf.append(s)

    flush()
    # Remove sections that are just headings (very short, no real content)
    results = {k: v for k, v in results.items()
               if len(v["1"]) >= min_content}
    return results


def parse_by_paragraphs(text, min_len=100):
    """Split into paragraph blocks, return as sequential sections."""
    # Clean boilerplate
    text = re.sub(r'All material on this page.*', '', text, flags=re.DOTALL)
    text = re.sub(r'Sacred Texts \| Classics.*', '', text, flags=re.DOTALL)
    blocks = re.split(r'\n{2,}', text)
    results = {}
    i = 1
    for block in blocks:
        t = clean(block.replace('\n', ' '))
        if len(t) >= min_len and not is_garbage(t) and not is_footnote(t):
            results[str(i)] = {"1": t}
            i += 1
    return results


# ══════════════════════════════════════════════════════════════════════════════
# JULIAN — re-fetch Hymns from Tertullian properly
# The issue: footnotes were being captured as sections
# Tertullian pages have main text with inline footnote markers like "^1"
# ══════════════════════════════════════════════════════════════════════════════

def fix_julian():
    print("\n── Julian ────────────────────────────────────────────────────────────")
    books = {}

    # Hymns from Tertullian — numbered sections are the real text
    hymn_urls = {
        "Hymn to King Helios":        "https://www.tertullian.org/fathers/julian_apostate_1_sun.htm",
        "Hymn to the Mother of Gods": "https://www.tertullian.org/fathers/julian_apostate_2_mother.htm",
    }
    for title, url in hymn_urls.items():
        print(f"  {title}...", end=" ", flush=True)
        html = fetch(url, delay=1.5)
        if not html: print("not found"); continue
        text = strip_html(html)

        # On Tertullian, the main text sections are numbered like "1." "2." etc.
        # Footnotes appear AFTER a horizontal rule or "---" separator
        # Split at footnote boundary
        lines = text.split('\n')
        main_lines = []
        for line in lines:
            # Footnote sections on Tertullian start with a line of all dashes or "NOTES"
            if re.match(r'^[\-_=]{5,}', line.strip()) or line.strip().upper() == 'NOTES':
                break
            main_lines.append(line)
        main_text = '\n'.join(main_lines)

        sects = parse_sections(main_text, min_content=80, skip_footnotes=True)
        if not sects:
            # Try paragraph splitting
            sects = parse_by_paragraphs(main_text, min_len=100)
        if not sects: print("no content"); continue
        books[title] = sects
        print(f"✓ {len(sects)}")

    # Against Galilaeans — Stephanus-numbered fragments
    print("  Against the Galilaeans...", end=" ", flush=True)
    html = fetch("https://www.tertullian.org/fathers/julian_apostate_galileans_1_text.htm", delay=1.5)
    if html:
        text = strip_html(html)
        sects = parse_sections(text, min_content=80, skip_footnotes=True)
        if sects:
            books["Against the Galilaeans"] = sects
            print(f"✓ {len(sects)}")
        else:
            print("no sections")

    # The Caesars — extract actual text from the one-section dump
    print("  The Caesars...", end=" ", flush=True)
    path = OUT / "julian.json"
    existing = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"books":{}}
    caes_raw = existing.get("books", {}).get("The Caesars", {}).get("1", {}).get("1", "")
    if caes_raw:
        # Strip the schema garbage prefix — find start of actual text
        # "The beauteous offspring" or after "Internet Sacred Text Archive"
        idx = caes_raw.find('The beauteous offspring')
        if idx == -1:
            idx = caes_raw.find('Kronos')
        if idx == -1:
            idx = caes_raw.find('Romulus')
        if idx > 0:
            caes_raw = caes_raw[idx:]
        # Strip trailing footnote section
        fn_idx = caes_raw.rfind(' 1 ')
        if fn_idx > len(caes_raw) * 0.8:
            caes_raw = caes_raw[:fn_idx]
        caes_clean = clean(caes_raw)
        if len(caes_clean) > 500:
            books["The Caesars"] = {"1": {"1": caes_clean}}
            print(f"✓ 1 (cleaned)")
        else:
            print("too short after cleaning")

    if books:
        update(path, books)


# ══════════════════════════════════════════════════════════════════════════════
# PORPHYRY — fix On Abstinence (footnote sections), Auxiliaries (footnotes),
#             Life of Plotinus (chapter titles not content), Cave of Nymphs (one block)
# ══════════════════════════════════════════════════════════════════════════════

def fix_porphyry():
    print("\n── Porphyry ──────────────────────────────────────────────────────────")
    books = {}

    # On Abstinence — re-fetch, skip footnote sections
    abstinence = {}
    for book_num, url in [
        ("1", "https://www.tertullian.org/fathers/porphyry_abstinence_01_book1.htm"),
        ("2", "https://www.tertullian.org/fathers/porphyry_abstinence_02_book2.htm"),
        ("3", "https://www.tertullian.org/fathers/porphyry_abstinence_03_book3.htm"),
        ("4", "https://www.tertullian.org/fathers/porphyry_abstinence_04_book4.htm"),
    ]:
        print(f"  On Abstinence §{book_num}...", end=" ", flush=True)
        html = fetch(url, delay=1.5)
        if not html: print("not found"); continue
        text = strip_html(html)
        # Split at footnote boundary (Tertullian puts footnotes after "---" or "NOTES")
        main_text = text
        for sep in ['----', '____', 'NOTES\n', 'Footnotes\n']:
            idx = text.find(sep)
            if idx > len(text) * 0.3:  # only split if separator is well into the text
                main_text = text[:idx]
                break
        sects = parse_sections(main_text, min_content=80, skip_footnotes=True)
        for k, v in sects.items():
            abstinence[f"{book_num}.{k}"] = v
        print(f"✓ {len(sects)}")
    if abstinence:
        books["On Abstinence"] = abstinence

    # Cave of the Nymphs — split the one giant block into paragraphs
    print("  Cave of the Nymphs...", end=" ", flush=True)
    html = fetch("https://www.tertullian.org/fathers/porphyry_cave_of_nymphs_02_translation.htm", delay=1.5)
    if html:
        text = strip_html(html)
        main_text = text
        for sep in ['----', 'NOTES\n', 'Footnotes\n']:
            idx = text.find(sep)
            if idx > len(text) * 0.3:
                main_text = text[:idx]; break
        sects = parse_sections(main_text, min_content=80, skip_footnotes=True)
        if sects:
            books["On the Cave of the Nymphs"] = sects
            print(f"✓ {len(sects)}")
        else:
            print("no sections")

    # Auxiliaries — footnotes as first sections; re-fetch and filter
    print("  Auxiliaries to the Intelligibles...", end=" ", flush=True)
    html = fetch("https://www.tertullian.org/fathers/porphyry_sententiae_02_trans.htm", delay=1.5)
    if html:
        text = strip_html(html)
        main_text = text
        for sep in ['----', 'NOTES\n', 'Footnotes\n']:
            idx = text.find(sep)
            if idx > len(text) * 0.3:
                main_text = text[:idx]; break
        sects = parse_sections(main_text, min_content=60, skip_footnotes=True)
        if sects:
            books["Auxiliaries to the Intelligibles"] = sects
            print(f"✓ {len(sects)}")
        else:
            print("no sections")

    # Life of Plotinus — sections are chapter titles, real text is in section 23+
    # The MacKenna translation has numbered sections (1-38) as real biographical sections
    print("  Life of Plotinus...", end=" ", flush=True)
    html = fetch("https://sacred-texts.com/cla/plotenn/enn001.htm", delay=1.5)
    if html:
        text = strip_html(html)
        main_text = text
        for sep in ['----', 'NOTES\n', 'Footnotes\n']:
            idx = text.find(sep)
            if idx > len(text) * 0.3:
                main_text = text[:idx]; break
        sects = parse_sections(main_text, min_content=80, skip_footnotes=True)
        if sects:
            books["Life of Plotinus"] = sects
            print(f"✓ {len(sects)}")
        else:
            print("no sections")

    # Keep good books from existing file
    path = OUT / "porphyry.json"
    existing = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"books":{}}
    for keep in ["Life of Pythagoras", "Letter to Marcella"]:
        if keep in existing["books"] and keep not in books:
            books[keep] = existing["books"][keep]

    if books:
        existing["books"].update(books)
        path.write_text(json.dumps(existing, indent=2, ensure_ascii=False), encoding="utf-8")
        kb = path.stat().st_size // 1024
        total = sum(len(v) for v in existing["books"].values())
        print(f"    ✓ {path} ({kb}KB, {len(existing['books'])} books, {total} sections)")


# ══════════════════════════════════════════════════════════════════════════════
# MARINUS — sections are footnotes, not biography sections
# Tertullian page has numbered paragraphs of actual text
# ══════════════════════════════════════════════════════════════════════════════

def fix_marinus():
    print("\n── Marinus ───────────────────────────────────────────────────────────")
    print("  Life of Proclus...", end=" ", flush=True)
    html = fetch("https://www.tertullian.org/fathers/marinus_01_life_of_proclus.htm", delay=1.5)
    if not html: print("not found"); return
    text = strip_html(html)
    # Split off footnotes
    main_text = text
    for sep in ['----', 'NOTES\n', 'Footnotes\n', 'p. 55']:
        idx = text.find(sep)
        if idx > len(text) * 0.4:
            main_text = text[:idx]; break
    sects = parse_sections(main_text, min_content=80, skip_footnotes=True)
    if not sects:
        sects = parse_by_paragraphs(main_text, min_len=100)
    if not sects: print("no sections"); return
    print(f"✓ {len(sects)}")
    save(OUT / "marinus.json",
         "Marinus of Neapolis, Life of Proclus. Trans. K.S. Guthrie (1925). Tertullian.org.",
         {"Life of Proclus": sects})


# ══════════════════════════════════════════════════════════════════════════════
# IAMBLICHUS — On the Mysteries is one giant blob; Life of Pythagoras has
# one enormous last section. Split properly.
# ══════════════════════════════════════════════════════════════════════════════

def fix_iamblichus():
    print("\n── Iamblichus ────────────────────────────────────────────────────────")
    path = OUT / "iamblichus.json"
    data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"books":{}}

    # On the Mysteries — the single section contains the entire text
    # Re-parse from Gutenberg with proper book/section structure
    print("  On the Mysteries (Gutenberg)...", end=" ", flush=True)
    text = fetch("https://www.gutenberg.org/files/72815/72815-0.txt", delay=2.0, timeout=45)
    if not text:
        text = fetch("https://www.gutenberg.org/cache/epub/72815/pg72815.txt", delay=2.0, timeout=45)
    if text:
        text = text.replace('\r','')
        # Strip PG wrapper
        start = re.search(r'\*\*\* START OF THE PROJECT', text)
        if start: text = text[text.find('\n', start.start())+1:]
        end = re.search(r'\*\*\* END OF THE PROJECT', text)
        if end: text = text[:end.start()]

        ROMAN = {r:i for i,r in enumerate(['I','II','III','IV','V','VI','VII','VIII',
            'IX','X','XI','XII','XIII','XIV','XV','XVI','XVII','XVIII','XIX','XX',
            'XXI','XXII','XXIII','XXIV','XXV','XXVI','XXVII','XXVIII'],1)}

        results = {}; book = None; chap = None; buf = []

        def flush_imb():
            if book is not None and chap is not None and buf:
                t = clean(" ".join(buf))
                if len(t) > 50:
                    results[f"{book}.{chap}"] = {"1": t}

        book_re = re.compile(r'^(?:SECTION\s+THE\s+)?BOOK\s+([IVXLCDM]+)\.?\s*$', re.IGNORECASE)
        sect_re = re.compile(r'^([IVXLCDM]+)\.\s*$')

        blocks = re.split(r'\n{2,}', text)
        for block in blocks:
            b = block.strip()
            if not b or is_garbage(b): continue
            bm = book_re.match(b)
            sm = sect_re.match(b) if len(b) < 10 else None
            if bm:
                flush_imb(); buf = []; chap = None
                roman = bm.group(1).upper()
                book = ROMAN.get(roman, roman)
            elif sm:
                flush_imb(); buf = []
                chap = ROMAN.get(sm.group(1).upper(), sm.group(1))
            else:
                if book is not None:
                    t = clean(b.replace('\n',' '))
                    if t and len(t) > 20 and not is_footnote(t): buf.append(t)
        flush_imb()

        if results:
            data["books"]["On the Mysteries"] = results
            print(f"✓ {len(results)}")
        else:
            print("no sections — keeping existing")
    else:
        print("fetch failed")

    # Life of Pythagoras — fix the giant last section
    # Split the existing sections that are too large
    if "Life of Pythagoras" in data["books"]:
        lop = data["books"]["Life of Pythagoras"]
        # Remove any section that is absurdly large (>50KB text) — it ate the whole rest of file
        cleaned = {}
        for k, v in lop.items():
            t = v["1"] if isinstance(v, dict) else str(v)
            if len(t) < 50000:  # keep reasonable sections
                cleaned[k] = v
            else:
                # Split it into paragraph blocks
                paras = re.split(r'\n{2,}', t)
                for j, para in enumerate(paras[:200], 1):
                    pt = clean(para.replace('\n',' '))
                    if len(pt) > 80 and not is_garbage(pt):
                        cleaned[f"{k}_{j}"] = {"1": pt}
        data["books"]["Life of Pythagoras"] = cleaned
        print(f"  Life of Pythagoras: cleaned to {len(cleaned)} sections")

    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    kb = path.stat().st_size // 1024
    total = sum(len(v) for v in data["books"].values())
    print(f"    ✓ {path} ({kb}KB, {len(data['books'])} books, {total} sections)")


# ══════════════════════════════════════════════════════════════════════════════
# PYTHAGOREAN SENTENCES — remove garbage last sections from each collection
# ══════════════════════════════════════════════════════════════════════════════

def fix_pythagorean_sentences():
    print("\n── Pythagorean Sentences ────────────────────────────────────────────")
    path = OUT / "pythagorean_sentences.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    for book, sects in data["books"].items():
        cleaned = {k: v for k, v in sects.items()
                   if not is_garbage(v["1"] if isinstance(v, dict) else str(v))}
        removed = len(sects) - len(cleaned)
        data["books"][book] = cleaned
        if removed:
            print(f"  {book}: removed {removed} garbage sections ({len(cleaned)} remain)")
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    kb = path.stat().st_size // 1024
    total = sum(len(v) for v in data["books"].values())
    print(f"    ✓ {path} ({kb}KB, {len(data['books'])} books, {total} sections)")


# ══════════════════════════════════════════════════════════════════════════════
# HIEROCLES — sections that are just headings need their content merged in
# Also remove navigation garbage from section 70
# ══════════════════════════════════════════════════════════════════════════════

def fix_hierocles():
    print("\n── Hierocles ─────────────────────────────────────────────────────────")
    path = OUT / "hierocles.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    sects = data["books"]["Commentary on the Golden Verses"]

    # Remove sections that are just headings (< 60 chars) or nav garbage
    cleaned = {}
    for k, v in sects.items():
        t = v["1"] if isinstance(v, dict) else str(v)
        if is_garbage(t) or len(t) < 60:
            continue
        # Clean trailing navigation from section 67/70
        t = re.sub(r'Next: .*$', '', t).strip()
        t = re.sub(r'Sacred Texts \| Classics.*$', '', t).strip()
        if len(t) >= 60:
            cleaned[k] = {"1": t}

    data["books"]["Commentary on the Golden Verses"] = cleaned
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    kb = path.stat().st_size // 1024
    total = sum(len(v) for v in data["books"].values())
    print(f"    ✓ {path} ({kb}KB, 1 books, {total} sections)")


# ══════════════════════════════════════════════════════════════════════════════
# ARISTOTLE MIT — works that parsed as 1 section need paragraph splitting
# ══════════════════════════════════════════════════════════════════════════════

def fix_aristotle_mit():
    print("\n── Aristotle MIT (split large sections) ─────────────────────────────")
    path = OUT / "aristotle_mit.json"
    data = json.loads(path.read_text(encoding="utf-8"))

    # Works where each "section" is actually the entire work
    single_section_works = [
        "On Memory and Reminiscence", "On Dreams", "On Sleep and Sleeplessness",
        "On Prophesying by Dreams", "On Longevity and Shortness of Life",
        "On the Motion of Animals", "On the Gait of Animals",
    ]

    for work in single_section_works:
        if work not in data["books"]: continue
        sects = data["books"][work]
        if len(sects) == 1:
            # Split the single section into paragraphs
            raw = list(sects.values())[0]
            t = raw["1"] if isinstance(raw, dict) else str(raw)
            # Split on double-space or sentence boundaries
            paras = [p.strip() for p in re.split(r'\s{2,}|\n', t) if len(p.strip()) > 80]
            if len(paras) > 3:
                new_sects = {str(i): {"1": p} for i, p in enumerate(paras, 1)}
                data["books"][work] = new_sects
                print(f"  {work}: split into {len(new_sects)} sections")

    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    kb = path.stat().st_size // 1024
    total = sum(len(v) for v in data["books"].values())
    print(f"    ✓ {path} ({kb}KB, {len(data['books'])} books, {total} sections)")


# ══════════════════════════════════════════════════════════════════════════════
# PROCLUS THEOLOGY — fix oversized sections (5.XXXIX = 52KB)
# ══════════════════════════════════════════════════════════════════════════════

def fix_proclus_theology():
    print("\n── Proclus Theology ──────────────────────────────────────────────────")
    path = OUT / "proclus_theology.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    sects = data["books"]["Theology of Plato"]
    cleaned = {}
    split_count = 0
    for k, v in sects.items():
        t = v["1"] if isinstance(v, dict) else str(v)
        if len(t) > 30000:
            # Split into ~5000-char chunks at sentence boundaries
            chunks = []
            while len(t) > 5000:
                # Find sentence end near 5000 chars
                split_at = t.rfind('. ', 3000, 5500)
                if split_at == -1:
                    split_at = 5000
                chunks.append(t[:split_at+1].strip())
                t = t[split_at+1:].strip()
            if t: chunks.append(t)
            for j, chunk in enumerate(chunks, 1):
                cleaned[f"{k}_{j}"] = {"1": chunk}
            split_count += 1
        else:
            cleaned[k] = v
    data["books"]["Theology of Plato"] = cleaned
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    kb = path.stat().st_size // 1024
    total = sum(len(v) for v in data["books"].values())
    print(f"    ✓ {path} ({kb}KB, 1 books, {total} sections, {split_count} large sections split)")


if __name__ == "__main__":
    fix_julian()
    fix_porphyry()
    fix_marinus()
    fix_iamblichus()
    fix_pythagorean_sentences()
    fix_hierocles()
    fix_aristotle_mit()
    fix_proclus_theology()
    print("\n✓ Done.")
