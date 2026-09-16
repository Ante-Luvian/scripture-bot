"""
fetch_bede.py — scrape Bede's Ecclesiastical History from CCEL
Output: bede.json  (place in data/patristics/)

Run from your bot root:
    pip install requests lxml cssselect
    python fetch_bede.py
"""

import json, re, time
import requests
from lxml import html as lhtml

SESSION = requests.Session()
SESSION.headers["User-Agent"] = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

# Start at Book I first chapter and follow Next links all the way through
# CCEL Bede chapters look like history.i.i.html, history.i.ii.html, history.ii.i.html, etc.
START_URL = "https://ccel.org/ccel/bede/history/history.i.i.html"

# Book headings map — detect which book we're in from page content
BOOK_NAMES = {
    "i":   "Book I",
    "ii":  "Book II",
    "iii": "Book III",
    "iv":  "Book IV",
    "v":   "Book V",
}

def get(url):
    time.sleep(0.7)
    r = SESSION.get(url, timeout=30)
    r.raise_for_status()
    return r.text

def clean(text):
    text = re.sub(r'\s+', ' ', text).strip()
    text = re.sub(r'\[pg\s*\d+\]', '', text, flags=re.I)
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def get_book_from_url(url):
    """Extract book number from URL like history.iii.v.html -> Book III"""
    m = re.search(r'history\.([ivx]+)\.([ivx]+)\.html', url)
    if m:
        book_roman = m.group(1)
        return BOOK_NAMES.get(book_roman, f"Book {book_roman.upper()}")
    return None

def get_chapter_title(tree, url):
    """Get the chapter heading from page."""
    for tag in ('h2', 'h3', 'h4', 'h1'):
        for el in tree.xpath(f'//{tag}'):
            t = clean(el.text_content())
            if len(t) > 5 and not re.match(r'^(Next|Prev|Table|Bede|History)', t, re.I):
                return t[:100]
    # Fallback: use chapter number from URL
    m = re.search(r'history\.[ivx]+\.([ivx]+)\.html', url)
    if m:
        return f"Chapter {m.group(1).upper()}"
    return None

def get_next_url(tree, current_url):
    """Find the Next chapter link."""
    base = current_url.rsplit('/', 1)[0] + '/'
    for a in tree.xpath('//a[@href]'):
        txt = clean(a.text_content())
        href = a.get('href', '')
        if re.search(r'next|»|→', txt, re.I) and href.endswith('.html'):
            if href.startswith('http'):
                return href
            return base + href
    return None

def extract_paras(tree):
    paras = []
    for p in tree.xpath('//p'):
        t = clean(p.text_content())
        if len(t) < 80:
            continue
        if re.match(r'^(Next|Previous|Table|Contents)\b', t, re.I):
            continue
        paras.append(t)
    return paras

def scrape_bede():
    books = {}   # book_name -> {ch_key -> {para_key -> text}}
    book_ch_counters = {}  # track chapter numbers per book

    url = START_URL
    visited = set()
    total_chapters = 0

    print(f"Starting at {url}")
    print("Following Next links through all books...\n")

    while url and url not in visited:
        # Only stay within Bede's history pages
        if 'bede/history' not in url:
            break
        visited.add(url)

        try:
            html = get(url)
        except Exception as e:
            print(f"  ERROR {url}: {e}")
            break

        tree = lhtml.fromstring(html)
        book_name = get_book_from_url(url)
        ch_title = get_chapter_title(tree, url)
        paras = extract_paras(tree)

        if book_name and paras:
            if book_name not in books:
                books[book_name] = {}
                book_ch_counters[book_name] = 0
            book_ch_counters[book_name] += 1
            ch_key = str(book_ch_counters[book_name])
            books[book_name][ch_key] = {str(i+1): p for i, p in enumerate(paras)}
            total_chapters += 1
            print(f"  {book_name} ch{ch_key}: {ch_title or '?'[:50]} ({len(paras)} paras)")
        elif not book_name:
            print(f"  SKIP (unrecognized URL pattern): {url}")
        else:
            print(f"  SKIP (no paras): {url}")

        url = get_next_url(tree, url)

    return books

if __name__ == '__main__':
    books = scrape_bede()

    if not books:
        print("\nERROR: Nothing scraped.")
        print("Try opening this URL in your browser to check it works:")
        print("  https://ccel.org/ccel/bede/history/history.i.i.html")
    else:
        total_ch = sum(len(b) for b in books.values())
        total_p = sum(len(v) for bk in books.values() for v in bk.values())
        print(f"\nDone: {len(books)} books, {total_ch} chapters, {total_p:,} paragraphs")
        out = {"source": "Bede the Venerable", "books": books}
        with open("bede.json", "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=2)
        print("Written: bede.json")
