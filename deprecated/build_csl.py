#!/usr/bin/env python3
"""
build_csl.py — Download CSlElizabeth from scrollmapper and save as data/csl.json
Run from your bot directory: python build_csl.py
"""
import json, urllib.request
from pathlib import Path

URLS = [
    "https://cdn.jsdelivr.net/gh/scrollmapper/bible_databases@master/formats/json/CSlElizabeth.json",
    "https://raw.githubusercontent.com/scrollmapper/bible_databases/master/formats/json/CSlElizabeth.json",
]

# scrollmapper book names → canonical bot names
BOOK_NAME_MAP = {
    "Genesis":"Genesis","Exodus":"Exodus","Leviticus":"Leviticus",
    "Numbers":"Numbers","Deuteronomy":"Deuteronomy","Joshua":"Joshua",
    "Judges":"Judges","Ruth":"Ruth",
    "I Samuel":"1 Samuel","II Samuel":"2 Samuel",
    "I Kings":"1 Kings","II Kings":"2 Kings",
    "I Chronicles":"1 Chronicles","II Chronicles":"2 Chronicles",
    "Ezra":"Ezra","Nehemiah":"Nehemiah","Esther":"Esther",
    "Job":"Job","Psalms":"Psalms","Proverbs":"Proverbs",
    "Ecclesiastes":"Ecclesiastes","Song of Solomon":"Song of Solomon",
    "Isaiah":"Isaiah","Jeremiah":"Jeremiah","Lamentations":"Lamentations",
    "Ezekiel":"Ezekiel","Daniel":"Daniel","Hosea":"Hosea","Joel":"Joel",
    "Amos":"Amos","Obadiah":"Obadiah","Jonah":"Jonah","Micah":"Micah",
    "Nahum":"Nahum","Habakkuk":"Habakkuk","Zephaniah":"Zephaniah",
    "Haggai":"Haggai","Zechariah":"Zechariah","Malachi":"Malachi",
    "Tobit":"Tobit","Judith":"Judith","Esther (Greek)":"Esther",
    "Wisdom":"Wisdom of Solomon","Sirach":"Sirach","Baruch":"Baruch",
    "I Maccabees":"1 Maccabees","II Maccabees":"2 Maccabees",
    "I Esdras":"1 Esdras","II Esdras":"2 Esdras",
    "Matthew":"Matthew","Mark":"Mark","Luke":"Luke","John":"John",
    "Acts":"Acts","Romans":"Romans",
    "I Corinthians":"1 Corinthians","II Corinthians":"2 Corinthians",
    "Galatians":"Galatians","Ephesians":"Ephesians",
    "Philippians":"Philippians","Colossians":"Colossians",
    "I Thessalonians":"1 Thessalonians","II Thessalonians":"2 Thessalonians",
    "I Timothy":"1 Timothy","II Timothy":"2 Timothy",
    "Titus":"Titus","Philemon":"Philemon","Hebrews":"Hebrews",
    "James":"James","I Peter":"1 Peter","II Peter":"2 Peter",
    "I John":"1 John","II John":"2 John","III John":"3 John",
    "Jude":"Jude","Revelation of John":"Revelation",
}

def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent":"ScriptureBot/1.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))

def main():
    raw = None
    for url in URLS:
        try:
            raw = fetch(url)
            print(f"Fetched from {url}")
            break
        except Exception as e:
            print(f"  {url}: {e}")

    if not raw:
        print("ERROR: Could not fetch CSlElizabeth")
        return

    books_out = {}
    for b in raw.get("books", []):
        name = b.get("name", "")
        canon = BOOK_NAME_MAP.get(name, name)
        chaps = {}
        for chap in b.get("chapters", []):
            c = str(chap.get("chapter", ""))
            vdict = {}
            for v in chap.get("verses", []):
                vnum = v.get("verse")
                text = (v.get("text") or "").strip()
                if vnum is not None and text:
                    vdict[str(vnum)] = text
            if vdict:
                chaps[c] = vdict
        if chaps:
            books_out[canon] = chaps

    total = sum(sum(len(v) for v in c.values()) for c in books_out.values())
    print(f"{len(books_out)} books, {total:,} verses")

    # Spot checks
    for ref, book, c, v in [
        ("Judges 21:25", "Judges", "21", "25"),
        ("John 3:16",    "John",   "3",  "16"),
        ("Genesis 1:1",  "Genesis","1",  "1"),
    ]:
        text = books_out.get(book,{}).get(c,{}).get(v,"NOT FOUND")
        print(f"  {ref}: {text[:70]}")

    out = Path("data") / "csl.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps({
        "source": "Church Slavonic Elizabeth Bible, 1757. Via scrollmapper/bible_databases. Public domain.",
        "lang": "cu",
        "books": books_out,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Saved {out} ({out.stat().st_size/1024/1024:.1f} MB)")

if __name__ == "__main__":
    main()
