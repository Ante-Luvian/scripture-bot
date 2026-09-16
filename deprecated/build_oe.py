#!/usr/bin/env python3
"""
build_oe.py — Build data/oe.json from textusreceptusbibles.com (Wessex Gospels only)
The site only has Matthew, Mark, Luke, John.
For OT (Genesis-Judges, Psalms), a separate source is needed — see notes below.

Run: python build_oe.py
"""
import json, re, time, urllib.request, html as html_module
from pathlib import Path

BASE = "https://www.textusreceptusbibles.com/Wessex"
OUT  = Path("data") / "oe.json"

# Only Gospels are on this site
BOOKS = {
    40: ("Matthew", 28),
    41: ("Mark",    16),
    42: ("Luke",    24),
    43: ("John",    21),
}

HEADERS = {"User-Agent": "ScriptureBot/1.0 (academic use)"}

def fetch_chapter(book_num: int, chap: int) -> dict:
    url = f"{BASE}/{book_num}/{chap}"
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            raw = r.read().decode("utf-8", errors="replace")
    except Exception as e:
        print(f"    error {book_num}/{chap}: {e}")
        return {}

    verses = {}
    # Format: markdown table rows like "| 20:1 | verse text |"
    # After web_fetch converts to markdown
    for m in re.finditer(r'\|\s*\d+:(\d+)\s*\|\s*(.+?)\s*\|', raw):
        vnum = m.group(1)
        text = m.group(2).strip()
        text = re.sub(r'<[^>]+>', ' ', text)
        text = html_module.unescape(text)
        text = re.sub(r'\s+', ' ', text).strip()
        if text:
            verses[vnum] = text

    if not verses:
        # Raw HTML fallback: table cells with chapter:verse pattern
        for m in re.finditer(r'<td[^>]*>\s*\d+:(\d+)\s*</td>\s*<td[^>]*>(.*?)</td>',
                              raw, re.DOTALL):
            vnum = m.group(1)
            text = re.sub(r'<[^>]+>', ' ', m.group(2))
            text = html_module.unescape(text)
            text = re.sub(r'\s+', ' ', text).strip()
            if text:
                verses[vnum] = text

    return verses

def main():
    books_out = {}
    total = 0

    for book_num, (book_name, num_chaps) in BOOKS.items():
        print(f"{book_name} ({num_chaps} chapters)...")
        chaps_out = {}
        for chap in range(1, num_chaps + 1):
            verses = fetch_chapter(book_num, chap)
            if verses:
                chaps_out[str(chap)] = verses
                total += len(verses)
            time.sleep(0.8)
        
        if chaps_out:
            books_out[book_name] = chaps_out
            vcount = sum(len(v) for v in chaps_out.values())
            print(f"  {len(chaps_out)} chapters, {vcount} verses")
        else:
            print(f"  NO DATA")

    print(f"\nTotal: {len(books_out)} books, {total:,} verses")

    jn316 = books_out.get("John", {}).get("3", {}).get("16", "NOT FOUND")
    print(f"John 3:16: {jn316[:80]}")

    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps({
        "source": "Old English Wessex Gospels (~990 AD, Ælfric of Eynsham). "
                  "Text via textusreceptusbibles.com. Public domain.",
        "lang": "ang",
        "note": "Only the four Gospels exist in Old English translation (Wessex Gospels). "
                "Heptateuch and Psalms require a separate source (see Ælfric Society editions).",
        "books": books_out,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    sz = OUT.stat().st_size
    print(f"Saved {OUT} ({sz/1024:.0f} KB)")

if __name__ == "__main__":
    main()
