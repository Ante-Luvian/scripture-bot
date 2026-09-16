"""
fetch_golden_legend.py — scrape The Golden Legend (all 7 vols) from CCEL
Output: golden_legend.json  (place in data/patristics/)

Run from your bot root:
    pip install requests lxml cssselect
    python fetch_golden_legend.py
"""

import json, re, time
import requests
from lxml import html as lhtml

SESSION = requests.Session()
SESSION.headers["User-Agent"] = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

# CCEL Golden Legend — volume chapter URL patterns
# Vol 1: goldleg1.ii.html, goldleg1.iii.html, etc.
VOLUMES = [
    ("https://ccel.org/ccel/voragine/goldleg1/goldleg1.ii.html",  "goldleg1", 1),
    ("https://ccel.org/ccel/voragine/goldleg2/goldleg2.ii.html",  "goldleg2", 2),
    ("https://ccel.org/ccel/voragine/goldleg3/goldleg3.ii.html",  "goldleg3", 3),
    ("https://ccel.org/ccel/voragine/goldleg4/goldleg4.ii.html",  "goldleg4", 4),
    ("https://ccel.org/ccel/voragine/goldleg5/goldleg5.ii.html",  "goldleg5", 5),
    ("https://ccel.org/ccel/voragine/goldleg6/goldleg6.ii.html",  "goldleg6", 6),
    ("https://ccel.org/ccel/voragine/goldleg7/goldleg7.ii.html",  "goldleg7", 7),
]

def get(url):
    time.sleep(0.7)
    r = SESSION.get(url, timeout=30)
    r.raise_for_status()
    return r.text

def clean(text):
    text = re.sub(r'\s+', ' ', text).strip()
    text = re.sub(r'\[pg\s*\d+\]', '', text, flags=re.I)
    text = re.sub(r'·\s*', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def extract_paras(tree):
    paras = []
    for p in tree.xpath('//p'):
        t = clean(p.text_content())
        if len(t) < 80:
            continue
        if re.match(r'^(Next|Previous|Table|Contents|Chapter \d)', t):
            continue
        paras.append(t)
    return paras

def get_title_from_page(tree):
    """Find the saint/chapter title from h1/h2/h3 on the page."""
    for tag in ('h1', 'h2', 'h3'):
        els = tree.xpath(f'//{tag}')
        for el in els:
            t = clean(el.text_content())
            if len(t) > 4 and not re.match(r'^(Next|Prev|Table|Golden Legend)', t, re.I):
                return t[:100]
    return None

def get_next_url(tree, current_url):
    """Find the 'Next' chapter link."""
    base = current_url.rsplit('/', 1)[0] + '/'
    for a in tree.xpath('//a[@href]'):
        txt = clean(a.text_content()).lower()
        if 'next' in txt:
            href = a.get('href', '')
            if href.endswith('.html'):
                if href.startswith('http'):
                    return href
                return base + href
    return None

def scrape_volume(start_url, stem, vol_num):
    """Follow Next links through an entire volume, collecting saint entries."""
    entries = {}  # title -> {ch_key -> {para_key -> text}}
    url = start_url
    visited = set()

    print(f"  Starting at {start_url}")

    while url and url not in visited:
        visited.add(url)
        # Only follow pages within this volume
        if stem not in url:
            break

        try:
            html = get(url)
        except Exception as e:
            print(f"  ERROR {url}: {e}")
            break

        tree = lhtml.fromstring(html)
        title = get_title_from_page(tree)
        paras = extract_paras(tree)

        if title and paras:
            print(f"    [{title[:55]}] {len(paras)} paras")
            if title not in entries:
                entries[title] = {}
            ch_key = str(len(entries[title]) + 1)
            entries[title][ch_key] = {str(i+1): p for i, p in enumerate(paras)}
        elif paras:
            # No title found — use URL as key
            fallback = f"Vol{vol_num}-{url.split('.')[-2]}"
            print(f"    [untitled: {fallback}] {len(paras)} paras")
            entries[fallback] = {"1": {str(i+1): p for i, p in enumerate(paras)}}

        url = get_next_url(tree, url)

    return entries

def scrape_golden_legend():
    all_entries = {}

    for start_url, stem, vol_num in VOLUMES:
        print(f"\n=== Volume {vol_num} ===")
        try:
            entries = scrape_volume(start_url, stem, vol_num)
            print(f"  Volume {vol_num}: {len(entries)} entries")
            all_entries.update(entries)
        except Exception as e:
            print(f"  Volume {vol_num} FAILED: {e}")

    return all_entries

if __name__ == '__main__':
    books = scrape_golden_legend()

    if not books:
        print("\nERROR: Nothing scraped.")
        print("Try opening https://ccel.org/ccel/voragine/goldleg1/goldleg1.ii.html")
        print("in your browser and check the URL pattern for chapter links.")
    else:
        total_p = sum(len(v) for bk in books.values() for v in bk.values())
        print(f"\nTotal: {len(books)} entries, {total_p:,} chapter-sections")
        out = {"source": "Jacobus de Voragine", "books": books}
        with open("golden_legend.json", "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=2)
        print("Written: golden_legend.json")
