#!/usr/bin/env python3
"""
build_vulg_esdras.py
Adds 3 Esdras (= KJV 1 Esdras) and 4 Esdras (= KJV 2 Esdras) Latin text
to data/vulg_appendix.json, sourced from scrollmapper VulgClementine.
"""
import json, urllib.request, sys
from pathlib import Path

DATA = Path("data")
APPENDIX = DATA / "vulg_appendix.json"

URLS = [
    "https://cdn.jsdelivr.net/gh/scrollmapper/bible_databases@master/formats/json/VulgClementine.json",
    "https://raw.githubusercontent.com/scrollmapper/bible_databases/master/formats/json/VulgClementine.json",
]

# Maps scrollmapper book names → our canonical names
# (The script prints all book names below so you can verify.)
# Maps scrollmapper book name → our canonical name
# Includes Prayer of Manasses so vulg_appendix gets all three appendix books
# (Prayer of Manasseh was hardcoded before; scrollmapper version is better source)
ESDRAS_NAME_MAP = {
    "I Esdras":           "1 Esdras",
    "II Esdras":          "2 Esdras",
    "Prayer of Manasses": "Prayer of Manasseh",
    # Fallbacks for other editions
    "3 Esdras":           "1 Esdras",
    "III Esdras":         "1 Esdras",
    "4 Esdras":           "2 Esdras",
    "IV Esdras":          "2 Esdras",
}


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "ScriptureBot/1.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))


def extract_verse(v):
    """Extract (verse_num, text) from a verse dict. Returns (None, '') on failure."""
    vnum = (v.get("verse") if v.get("verse") is not None else
            v.get("v") if v.get("v") is not None else
            v.get("num") if v.get("num") is not None else
            v.get("id"))
    text = (v.get("text") or v.get("t") or v.get("content") or "").strip()
    return vnum, text


def extract_chapters(book_entry, debug=False):
    """
    Parse scrollmapper chapter/verse structure.
    Handles: {"chapters": [{"chapter": N, "verses": [{verse: N, text: "..."}]}]}
    Returns {chapter_str: {verse_str: text}}
    """
    chaps = {}
    raw_chapters = book_entry.get("chapters", [])

    if debug and raw_chapters:
        first = raw_chapters[0]
        print(f"    chapter keys: {list(first.keys())}")
        vv = first.get("verses", [])
        if vv:
            print(f"    first verse entry: {vv[0]}")
        else:
            print(f"    'verses' list empty or missing; full chapter: {str(first)[:300]}")

    for chap in raw_chapters:
        c = (chap.get("chapter") if chap.get("chapter") is not None else
             chap.get("c") if chap.get("c") is not None else
             chap.get("num") if chap.get("num") is not None else
             chap.get("id"))
        if c is None:
            continue
        c = str(c)
        vdict = {}

        verses_list = chap.get("verses") or []

        # Primary path: standard verses list
        for v in verses_list:
            vnum, text = extract_verse(v)
            if vnum is not None and text:
                vdict[str(vnum)] = text

        # Fallback: maybe chapter IS the verse (single-verse chapter entries)
        if not vdict:
            vnum, text = extract_verse(chap)
            if vnum is not None and text:
                vdict[str(vnum)] = text

        if vdict:
            chaps[c] = vdict

    return chaps


def main():
    raw = None
    for url in URLS:
        try:
            raw = fetch(url)
            print(f"Fetched from {url}")
            break
        except Exception as e:
            print(f"  Failed {url}: {e}")

    if raw is None:
        print("ERROR: Could not fetch VulgClementine. Check internet connection.")
        sys.exit(1)

    books_list = raw.get("books", [])
    print(f"Total books in VulgClementine: {len(books_list)}")

    # Print all books so the user can see the names
    print("\nAll book names:")
    for b in books_list:
        name = b.get("name") or b.get("book") or b.get("title") or str(b.get("book_nr","?"))
        nr   = b.get("book_nr") or b.get("nr") or "?"
        print(f"  {nr:>4}  {name!r}")

    # Print structure of first book entry for debugging
    if books_list:
        print(f"\nFirst book entry keys: {list(books_list[0].keys())}")
        first_chaps = books_list[0].get("chapters", [])
        if first_chaps:
            print(f"First chapter keys: {list(first_chaps[0].keys())}")
            first_vv = first_chaps[0].get("verses", [])
            if first_vv:
                print(f"First verse keys:   {list(first_vv[0].keys())}")
                print(f"First verse sample: {first_vv[0]}")

    # Find Esdras books
    new_books = {}
    for b in books_list:
        name = (b.get("name") or b.get("book") or b.get("title") or "").strip()
        target = ESDRAS_NAME_MAP.get(name)
        if not target:
            continue
        chap_data = extract_chapters(b, debug=True)
        if chap_data:
            new_books[target] = chap_data
            total = sum(len(vv) for vv in chap_data.values())
            v1 = chap_data.get("1", {}).get("1", "NOT FOUND")
            print(f"\n✓ {name!r} → {target}: {len(chap_data)} chapters, {total} verses")
            print(f"  1:1 = {v1[:80]}")
        else:
            print(f"\n⚠ {name!r} → {target}: chapters found but no verses extracted")

    if not new_books:
        print("\n⚠ No Esdras books found by name.")
        print("Check the 'All book names' list above and add the correct name(s) to ESDRAS_NAME_MAP.")
        sys.exit(1)

    # Merge into existing appendix
    if APPENDIX.exists():
        existing = json.loads(APPENDIX.read_text(encoding="utf-8"))
    else:
        existing = {
            "source": "Biblia Sacra Vulgata (Sixto-Clementina, 1592). Appendix. Public domain.",
            "lang": "lat",
            "books": {}
        }
    existing["books"].update(new_books)
    APPENDIX.write_text(json.dumps(existing, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nSaved {APPENDIX} (books: {list(existing['books'].keys())})")

if __name__ == "__main__":
    main()
