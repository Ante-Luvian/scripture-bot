"""
fix_remaining.py — fix what's still broken after fix_all_json.py
Run: python fix_remaining.py
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

def clean(t): return re.sub(r"\s+", " ", t).strip()

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

def parse_paragraphs(text, min_len=80):
    """Split text into paragraph-sized sections, filtered for quality."""
    # Remove boilerplate
    for marker in ['All material on this page', 'Sacred Texts | Classics',
                   'Internet Sacred Text Archive', 'copy freely']:
        idx = text.find(marker)
        if idx > 0: text = text[:idx]
    
    blocks = re.split(r'\n{2,}', text)
    results = {}
    i = 1
    for block in blocks:
        t = clean(block.replace('\n', ' '))
        if len(t) < min_len: continue
        if '@context' in t or 'BreadcrumbList' in t: continue
        if t.startswith('{'): continue
        results[str(i)] = {"1": t}
        i += 1
    return results

def split_large(text, chunk_size=4000):
    """Split a large text into sentence-boundary chunks."""
    chunks = []
    while len(text) > chunk_size:
        # Find good split point: end of sentence near chunk_size
        split_at = text.rfind('. ', chunk_size//2, chunk_size + 500)
        if split_at == -1:
            split_at = chunk_size
        chunks.append(clean(text[:split_at+1]))
        text = text[split_at+1:].strip()
    if text.strip():
        chunks.append(clean(text))
    return chunks

def update_book(path, book_name, sections):
    data = json.loads(path.read_text(encoding="utf-8"))
    data["books"][book_name] = sections
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    total = sum(len(v) for v in data["books"].values())
    kb = path.stat().st_size // 1024
    print(f"    ✓ {path} ({kb}KB, {len(data['books'])} books, {total} sections)")

def remove_section(path, book_name, section_key):
    data = json.loads(path.read_text(encoding="utf-8"))
    if book_name in data["books"] and section_key in data["books"][book_name]:
        del data["books"][book_name][section_key]
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


# ══════════════════════════════════════════════════════════════════════════════
# JULIAN — Hymns are prose texts; parse by paragraphs not footnote numbers
# Against Galilaeans: fetch fresh, parse as prose
# ══════════════════════════════════════════════════════════════════════════════

def fix_julian():
    print("\n── Julian ────────────────────────────────────────────────────────────")
    path = OUT / "julian.json"
    data = json.loads(path.read_text(encoding="utf-8"))

    hymn_urls = {
        "Hymn to King Helios":        "https://www.tertullian.org/fathers/julian_apostate_1_sun.htm",
        "Hymn to the Mother of Gods": "https://www.tertullian.org/fathers/julian_apostate_2_mother.htm",
    }
    for title, url in hymn_urls.items():
        print(f"  {title}...", end=" ", flush=True)
        html = fetch(url, delay=1.5)
        if not html: print("not found"); continue
        text = strip_html(html)
        
        # Find where footnotes start — Tertullian footnotes begin with a line
        # that is JUST a number followed by short text, after the main content
        # Strategy: find the main text body by looking for first substantial paragraph
        # The hymn text starts after the title/preamble
        
        # Split at footnote section — footnotes on Tertullian often start after
        # a paragraph that ends with "copy freely" or begins the notes
        lines = text.split('\n')
        main_lines = []
        footnote_started = False
        for line in lines:
            s = line.strip()
            if not s: 
                main_lines.append('')
                continue
            # Detect footnote section start
            if 'copy freely' in s or 'All material on this page' in s:
                break
            # Detect if we're hitting pure footnote numbers (short lines starting N space text)
            if len(main_lines) > 20 and re.match(r'^\d{1,3} [A-Z]', s) and len(s) < 200:
                footnote_started = True
            if footnote_started and re.match(r'^\d{1,3} [A-Z]', s):
                continue  # skip footnotes
            main_lines.append(line)
        
        main_text = '\n'.join(main_lines)
        sects = parse_paragraphs(main_text, min_len=100)
        if sects:
            data["books"][title] = sects
            print(f"✓ {len(sects)}")
        else:
            print("no content")

    # Against the Galilaeans — fetch fresh, parse as paragraphs
    print("  Against the Galilaeans...", end=" ", flush=True)
    html = fetch("https://www.tertullian.org/fathers/julian_apostate_galileans_1_text.htm", delay=1.5)
    if html:
        text = strip_html(html)
        sects = parse_paragraphs(text, min_len=100)
        if sects:
            data["books"]["Against the Galilaeans"] = sects
            print(f"✓ {len(sects)}")
        else:
            print("no content")

    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    kb = path.stat().st_size // 1024
    total = sum(len(v) for v in data["books"].values())
    print(f"    ✓ {path} ({kb}KB, {len(data['books'])} books, {total} sections)")


# ══════════════════════════════════════════════════════════════════════════════
# PORPHYRY — fix remaining issues:
# - Life of Plotinus: sections 1, 9 are chapter titles — remove short title sections
# - Letter to Marcella: remove section 2007 (boilerplate)
# - Life of Pythagoras: remove boilerplate from section 61
# ══════════════════════════════════════════════════════════════════════════════

def fix_porphyry():
    print("\n── Porphyry ──────────────────────────────────────────────────────────")
    path = OUT / "porphyry.json"
    data = json.loads(path.read_text(encoding="utf-8"))

    # Life of Plotinus — remove sections that are just Enneads chapter titles (< 80 chars)
    if "Life of Plotinus" in data["books"]:
        lop = data["books"]["Life of Plotinus"]
        cleaned = {}
        for k, v in lop.items():
            t = v["1"] if isinstance(v, dict) else str(v)
            # Skip chapter title stubs and nav lines
            if len(t) < 80: continue
            if 'Internet Sacred Text Archive' in t and len(t) < 200: continue
            if re.match(r'^On (the|The) [A-Z]', t) and len(t) < 100: continue
            cleaned[k] = v
        data["books"]["Life of Plotinus"] = cleaned
        print(f"  Life of Plotinus: {len(lop)} → {len(cleaned)} sections")

    # Letter to Marcella — remove boilerplate section 2007
    if "Letter to Marcella" in data["books"]:
        marcella = data["books"]["Letter to Marcella"]
        if "2007" in marcella:
            del marcella["2007"]
            print(f"  Letter to Marcella: removed boilerplate section 2007")

    # Life of Pythagoras — clean boilerplate from last section
    if "Life of Pythagoras" in data["books"]:
        lop = data["books"]["Life of Pythagoras"]
        for k, v in lop.items():
            t = v["1"] if isinstance(v, dict) else str(v)
            if 'copy freely' in t or 'All material on this page' in t:
                # Strip the boilerplate suffix
                for marker in ['All material on this page', 'copy freely']:
                    idx = t.find(marker)
                    if idx > 50:
                        t = clean(t[:idx])
                        lop[k] = {"1": t}
                        print(f"  Life of Pythagoras §{k}: stripped boilerplate")

    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    kb = path.stat().st_size // 1024
    total = sum(len(v) for v in data["books"].values())
    print(f"    ✓ {path} ({kb}KB, {len(data['books'])} books, {total} sections)")


# ══════════════════════════════════════════════════════════════════════════════
# IAMBLICHUS — On the Mysteries still 523KB; Life of Pythagoras XXXVI_1 = 216KB
# For Mysteries: split the blob into paragraphs since Gutenberg isn't working
# For Life: split the huge section
# ══════════════════════════════════════════════════════════════════════════════

def fix_iamblichus():
    print("\n── Iamblichus ────────────────────────────────────────────────────────")
    path = OUT / "iamblichus.json"
    data = json.loads(path.read_text(encoding="utf-8"))

    # On the Mysteries — split the single huge blob
    myst = data["books"].get("On the Mysteries", {})
    blob_key = list(myst.keys())[0] if myst else None
    if blob_key:
        blob = myst[blob_key]["1"] if isinstance(myst[blob_key], dict) else str(myst[blob_key])
        if len(blob) > 100000:
            print(f"  On the Mysteries: splitting {len(blob)//1024}KB blob...", end=" ", flush=True)
            chunks = split_large(blob, chunk_size=3000)
            new_sects = {str(i): {"1": c} for i, c in enumerate(chunks, 1)
                        if len(c) > 80}
            data["books"]["On the Mysteries"] = new_sects
            print(f"✓ {len(new_sects)} sections")

    # Life of Pythagoras — split huge XXXVI_1
    lop = data["books"].get("Life of Pythagoras", {})
    huge_keys = [k for k, v in lop.items()
                 if len((v["1"] if isinstance(v, dict) else str(v))) > 50000]
    for k in huge_keys:
        t = lop[k]["1"] if isinstance(lop[k], dict) else str(lop[k])
        print(f"  Life of Pythagoras §{k}: splitting {len(t)//1024}KB...", end=" ", flush=True)
        del lop[k]
        chunks = split_large(t, chunk_size=3000)
        for i, chunk in enumerate(chunks, 1):
            if len(chunk) > 80:
                lop[f"{k}_{i}"] = {"1": chunk}
        print(f"✓ {len(chunks)} chunks")
    data["books"]["Life of Pythagoras"] = lop

    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    kb = path.stat().st_size // 1024
    total = sum(len(v) for v in data["books"].values())
    print(f"    ✓ {path} ({kb}KB, {len(data['books'])} books, {total} sections)")


# ══════════════════════════════════════════════════════════════════════════════
# ARISTOTLE ECONOMICS — section 2.2 is 36KB, split it
# ARISTOTLE MIT — split the single-section short works
# ══════════════════════════════════════════════════════════════════════════════

def fix_aristotle():
    print("\n── Aristotle ─────────────────────────────────────────────────────────")
    
    # Economics 2.2 — in aristotle_perseus.json
    path_p = OUT / "aristotle_perseus.json"
    data_p = json.loads(path_p.read_text(encoding="utf-8"))
    econ = data_p["books"].get("Economics", {})
    if "2.2" in econ:
        t = econ["2.2"]["1"]
        if len(t) > 20000:
            print(f"  Economics 2.2: splitting {len(t)//1024}KB...", end=" ", flush=True)
            del econ["2.2"]
            chunks = split_large(t, chunk_size=3000)
            for i, chunk in enumerate(chunks, 1):
                if len(chunk) > 80:
                    econ[f"2.2_{i}"] = {"1": chunk}
            data_p["books"]["Economics"] = econ
            print(f"✓ {len(chunks)} chunks")
            path_p.write_text(json.dumps(data_p, indent=2, ensure_ascii=False), encoding="utf-8")
            kb = path_p.stat().st_size // 1024
            total = sum(len(v) for v in data_p["books"].values())
            print(f"    ✓ {path_p} ({kb}KB, {len(data_p['books'])} books, {total} sections)")

    # Aristotle MIT short works — split single sections into paragraphs
    path_m = OUT / "aristotle_mit.json"
    data_m = json.loads(path_m.read_text(encoding="utf-8"))
    
    short_works = ["On Memory and Reminiscence", "On Dreams", "On Sleep and Sleeplessness",
                   "On Prophesying by Dreams", "On Longevity and Shortness of Life",
                   "On the Motion of Animals", "On the Gait of Animals"]
    
    for work in short_works:
        if work not in data_m["books"]: continue
        sects = data_m["books"][work]
        if len(sects) != 1: continue
        only_key = list(sects.keys())[0]
        t = sects[only_key]["1"] if isinstance(sects[only_key], dict) else str(sects[only_key])
        if len(t) < 1000: continue  # Already small enough
        print(f"  {work}: splitting {len(t)//1024}KB...", end=" ", flush=True)
        chunks = split_large(t, chunk_size=3000)
        new_sects = {str(i): {"1": c} for i, c in enumerate(chunks, 1) if len(c) > 80}
        data_m["books"][work] = new_sects
        print(f"✓ {len(new_sects)} sections")
    
    path_m.write_text(json.dumps(data_m, indent=2, ensure_ascii=False), encoding="utf-8")
    kb = path_m.stat().st_size // 1024
    total = sum(len(v) for v in data_m["books"].values())
    print(f"    ✓ {path_m} ({kb}KB, {len(data_m['books'])} books, {total} sections)")


# ══════════════════════════════════════════════════════════════════════════════
# PROCLUS THEOLOGY — last section 5.XXXIX_10 is footnotes, remove
# Also remove any other sections that are clearly footnote-only
# ══════════════════════════════════════════════════════════════════════════════

def fix_proclus():
    print("\n── Proclus Theology ──────────────────────────────────────────────────")
    path = OUT / "proclus_theology.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    sects = data["books"]["Theology of Plato"]
    
    cleaned = {}
    removed = 0
    for k, v in sects.items():
        t = v["1"] if isinstance(v, dict) else str(v)
        # Remove footnote-only sections: start with [N] pattern (footnote refs)
        if re.match(r'^\[\d+\]', t) and len(t) < 500:
            removed += 1; continue
        cleaned[k] = v
    
    data["books"]["Theology of Plato"] = cleaned
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    kb = path.stat().st_size // 1024
    total = sum(len(v) for v in data["books"].values())
    print(f"    ✓ {path} ({kb}KB, 1 books, {total} sections, {removed} footnote sections removed)")


# ══════════════════════════════════════════════════════════════════════════════
# PYTHAGOREAN SENTENCES — Symbols: remove footnote section 100
# ══════════════════════════════════════════════════════════════════════════════

def fix_pythagorean():
    print("\n── Pythagorean Sentences ────────────────────────────────────────────")
    path = OUT / "pythagorean_sentences.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    
    symbols = data["books"].get("Symbols of Pythagoras", {})
    # Remove sections that are footnote text (start with number:N pattern)
    cleaned = {k: v for k, v in symbols.items()
               if not re.match(r'^\d+:\d+', (v["1"] if isinstance(v, dict) else str(v)))}
    removed = len(symbols) - len(cleaned)
    if removed:
        data["books"]["Symbols of Pythagoras"] = cleaned
        print(f"  Symbols: removed {removed} footnote sections ({len(cleaned)} remain)")
    
    # Also remove the sacred-texts nav line from first section if present
    symbols2 = data["books"].get("Symbols of Pythagoras", {})
    if "1" in symbols2:
        t = symbols2["1"]["1"]
        if 'Internet Sacred Text Archive' in t:
            del symbols2["1"]
            data["books"]["Symbols of Pythagoras"] = {
                str(int(k)-1 if k != "1" else k): v
                for k, v in symbols2.items()
            }

    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    kb = path.stat().st_size // 1024
    total = sum(len(v) for v in data["books"].values())
    print(f"    ✓ {path} ({kb}KB, {len(data['books'])} books, {total} sections)")


if __name__ == "__main__":
    fix_julian()
    fix_porphyry()
    fix_iamblichus()
    fix_aristotle()
    fix_proclus()
    fix_pythagorean()
    print("\n✓ Done.")
