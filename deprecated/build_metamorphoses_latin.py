#!/usr/bin/env python3
"""
build_metamorphoses_latin.py
Builds data/poetry/metamorphoses_latin.json from Perseus TEI XML.

Expected input (try these filenames):
  ov.met_lat.xml  OR  ovid.metamorphoses.perseus-lat2.xml  OR similar

Usage:
    python build_metamorphoses_latin.py                    # auto-detects
    python build_metamorphoses_latin.py path/to/file.xml   # explicit path

The script also accepts plain-text files with format:
    book 1
    1 In nova fert animus ...
    2 ...
"""
import json, re, sys
from pathlib import Path
from xml.etree import ElementTree as ET

BASE = Path.cwd()
OUT  = BASE / "data" / "poetry" / "metamorphoses_latin.json"

# Places to look for the XML
SEARCH_PATHS = [
    BASE / "ov.met_lat.xml",
    BASE / "ovid.metamorphoses.perseus-lat2.xml",
    BASE / "ovid.met.lat.xml",
    BASE / "data" / "ov.met_lat.xml",
    BASE / "data" / "ovid.metamorphoses.perseus-lat2.xml",
    BASE / "Perseus" / "ov.met_lat.xml",
    BASE / "Perseus" / "ovid.metamorphoses.perseus-lat2.xml",
]

# ── XML parser (Perseus TEI) ──────────────────────────────────────────────────

def parse_tei(path: Path) -> dict:
    """Parse Perseus TEI XML into {book: {start-end: text}} couplets."""
    tree = ET.parse(path)
    root = tree.getroot()

    # Strip namespace
    def strip_ns(tag):
        return tag.split('}', 1)[-1] if '}' in tag else tag

    # Find all <l> elements with n= attribute, grouped by <div> with n= (book)
    books = {}
    current_book = None

    # Try two structures:
    # 1. <div1 type="book" n="1"> ... <l n="1">text</l>
    # 2. <div type="textpart" subtype="book" n="1"> ... <l n="1">text</l>

    def get_n(el):
        return el.get('n') or el.get('N')

    def collect_lines(div_el, book_num):
        """Collect all <l> elements in a div, return {line_num: text}."""
        lines = {}
        for el in div_el.iter():
            tag = strip_ns(el.tag)
            if tag == 'l':
                n = get_n(el)
                if n and n.isdigit():
                    text = ''.join(el.itertext()).strip()
                    if text:
                        lines[int(n)] = text
        return lines

    for el in root.iter():
        tag = strip_ns(el.tag)
        # Match book-level divs
        if tag in ('div1', 'div') and get_n(el):
            etype = el.get('type', '') + el.get('subtype', '')
            if 'book' in etype.lower() or tag == 'div1':
                n = get_n(el)
                if n and n.isdigit():
                    raw_lines = collect_lines(el, int(n))
                    if raw_lines:
                        books[int(n)] = raw_lines

    if not books:
        raise ValueError("No book/line structure found in XML")
    return books


# ── Plain-text parser fallback ────────────────────────────────────────────────

def parse_plaintext(path: Path) -> dict:
    """
    Parse a plain-text Metamorphoses where each line is:
        1 In nova fert animus mutatas dicere formas
    and books are separated by a header like "book 1" or "LIBER I".
    """
    books = {}
    current_book = None
    with open(path, encoding='utf-8', errors='replace') as f:
        for raw in f:
            line = raw.strip()
            if not line:
                continue
            # Book header
            m = re.match(r'^(?:book|liber)\s+(\d+)', line, re.I)
            if m:
                current_book = int(m.group(1))
                books[current_book] = {}
                continue
            # Roman numeral header
            m2 = re.match(r'^(?:LIBER|BOOK)\s+([IVXLCDM]+)$', line, re.I)
            if m2:
                rom = m2.group(1).upper()
                # Convert Roman numeral
                vals = {'I':1,'V':5,'X':10,'L':50,'C':100,'D':500,'M':1000}
                n = 0
                prev = 0
                for ch in reversed(rom):
                    v = vals.get(ch, 0)
                    n += v if v >= prev else -v
                    prev = v
                current_book = n
                books[current_book] = {}
                continue
            # Verse line: starts with a number
            m3 = re.match(r'^(\d+)\s+(.*)', line)
            if m3 and current_book is not None:
                books[current_book][int(m3.group(1))] = m3.group(2).strip()

    return books


# ── Couplet grouping ──────────────────────────────────────────────────────────

def group_into_couplets(raw_lines: dict) -> dict:
    """
    Group sorted lines into couplets (pairs): {start-end: "line1\nline2"}
    Single lines at the end get their own entry.
    """
    sorted_nums = sorted(raw_lines.keys())
    couplets = {}
    i = 0
    while i < len(sorted_nums):
        a = sorted_nums[i]
        if i + 1 < len(sorted_nums):
            b = sorted_nums[i + 1]
            key = f"{a}-{b}"
            couplets[key] = raw_lines[a] + "\n" + raw_lines[b]
            i += 2
        else:
            couplets[str(a)] = raw_lines[a]
            i += 1
    return couplets


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    # Find the source file
    if len(sys.argv) > 1:
        candidates = [Path(sys.argv[1])]
    else:
        candidates = SEARCH_PATHS

    src = None
    for p in candidates:
        if p.exists():
            src = p
            break

    if src is None:
        print("ERROR: Could not find Metamorphoses Latin source file.")
        print("Tried:")
        for p in SEARCH_PATHS:
            print(f"  {p}")
        print("\nProvide the path explicitly:")
        print("  python build_metamorphoses_latin.py path/to/ov.met_lat.xml")
        sys.exit(1)

    print(f"Reading: {src}")

    # Parse
    if src.suffix.lower() == '.xml':
        try:
            raw_books = parse_tei(src)
            print(f"  Parsed TEI XML: {len(raw_books)} books")
        except Exception as e:
            print(f"  TEI parse failed ({e}), trying plain-text fallback...")
            raw_books = parse_plaintext(src)
    else:
        raw_books = parse_plaintext(src)
        print(f"  Parsed plain text: {len(raw_books)} books")

    # Group into couplets and build output
    books_out = {}
    total_lines = 0
    for book_num in sorted(raw_books.keys()):
        raw = raw_books[book_num]
        couplets = group_into_couplets(raw)
        books_out[str(book_num)] = couplets
        total_lines += len(raw)
        print(f"  Book {book_num:2d}: {len(raw)} lines → {len(couplets)} couplets")

    # Sample
    b1 = books_out.get("1", {})
    first_key = next(iter(b1)) if b1 else None
    if first_key:
        print(f"\n  Book 1, first entry ({first_key}):")
        print(f"  {b1[first_key][:100]}")

    # Write
    OUT.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "source": "Ovid, Metamorphoses. Ed. Hugo Magnus. Gotha: Friedr. Andr. Perthes, 1892. Public domain.",
        "abbrev": "Met.",
        "lang": "lat",
        "books": books_out,
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f"\nSaved {OUT} ({OUT.stat().st_size / 1024:.0f} KB)")
    print(f"Total: {len(books_out)} books, {total_lines} lines")

if __name__ == "__main__":
    main()
