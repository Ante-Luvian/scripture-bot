#!/usr/bin/env python3
"""
build_knox.py — scrape the Knox Bible from catholicbible.online
Output: data/kjv/knox.json

Run from your bot directory: python build_knox.py
Saves after every book so it can be safely interrupted and resumed.
"""

import json, re, time, html as html_mod, urllib.request, urllib.error
from pathlib import Path

BASE = "https://catholicbible.online/knox"

BOOKS = [
    # (section, abbr, canonical_name, chapters)
    ("OT", "Gen",   "Genesis",            50),
    ("OT", "Ex",    "Exodus",             40),
    ("OT", "Lev",   "Leviticus",          27),
    ("OT", "Num",   "Numbers",            36),
    ("OT", "Dt",    "Deuteronomy",        34),
    ("OT", "Jos",   "Joshua",             24),
    ("OT", "Judg",  "Judges",             21),
    ("OT", "Ru",    "Ruth",                4),
    ("OT", "1_Kgs", "1 Samuel",           31),
    ("OT", "2_Kgs", "2 Samuel",           24),
    ("OT", "3_Kgs", "1 Kings",            22),
    ("OT", "4_Kgs", "2 Kings",            25),
    ("OT", "1_Par", "1 Chronicles",       29),
    ("OT", "2_Par", "2 Chronicles",       36),
    ("OT", "Esd",   "Ezra",               10),
    ("OT", "Neh",   "Nehemiah",           13),
    ("OT", "Tob",   "Tobit",              14),
    ("OT", "Jdt",   "Judith",             16),
    ("OT", "Est",   "Esther",             16),
    ("OT", "Job",   "Job",                42),
    ("OT", "Ps",    "Psalms",            150),
    ("OT", "Prov",  "Proverbs",           31),
    ("OT", "Eccl",  "Ecclesiastes",       12),
    ("OT", "Cant",  "Song of Solomon",     8),
    ("OT", "Wis",   "Wisdom of Solomon",  19),
    ("OT", "Eccle", "Sirach",             51),
    ("OT", "Isa",   "Isaiah",             66),
    ("OT", "Jer",   "Jeremiah",           52),
    ("OT", "Lam",   "Lamentations",        5),
    ("OT", "Bar",   "Baruch",              6),
    ("OT", "Eze",   "Ezekiel",            48),
    ("OT", "Dan",   "Daniel",             14),
    ("OT", "Os",    "Hosea",              14),
    ("OT", "Jo",    "Joel",                3),
    ("OT", "Am",    "Amos",                9),
    ("OT", "Abd",   "Obadiah",             1),
    ("OT", "Jon",   "Jonah",               4),
    ("OT", "Mic",   "Micah",               7),
    ("OT", "Nah",   "Nahum",               3),
    ("OT", "Hab",   "Habakkuk",            3),
    ("OT", "Sop",   "Zephaniah",           3),
    ("OT", "Agg",   "Haggai",              2),
    ("OT", "Zac",   "Zechariah",          14),
    ("OT", "Mal",   "Malachi",             4),
    ("OT", "1_Mac", "1 Maccabees",        16),
    ("OT", "2_Mac", "2 Maccabees",        15),
    ("NT", "Mat",   "Matthew",            28),
    ("NT", "Mk",    "Mark",               16),
    ("NT", "Lk",    "Luke",               24),
    ("NT", "Jn",    "John",               21),
    ("NT", "Act",   "Acts",               28),
    ("NT", "Rom",   "Romans",             16),
    ("NT", "1_Cor", "1 Corinthians",      16),
    ("NT", "2_Cor", "2 Corinthians",      13),
    ("NT", "Gal",   "Galatians",           6),
    ("NT", "Eph",   "Ephesians",           6),
    ("NT", "Phl",   "Philippians",         4),
    ("NT", "Col",   "Colossians",          4),
    ("NT", "1_Th",  "1 Thessalonians",     5),
    ("NT", "2_Th",  "2 Thessalonians",     3),
    ("NT", "1_Tim", "1 Timothy",           6),
    ("NT", "2_Tim", "2 Timothy",           4),
    ("NT", "Tit",   "Titus",               3),
    ("NT", "Phm",   "Philemon",             1),
    ("NT", "Heb",   "Hebrews",            13),
    ("NT", "Jas",   "James",               5),
    ("NT", "1_Pet", "1 Peter",             5),
    ("NT", "2_Pet", "2 Peter",             3),
    ("NT", "1_Jn",  "1 John",              5),
    ("NT", "2_Jn",  "2 John",              1),
    ("NT", "3_Jn",  "3 John",              1),
    ("NT", "Jud",   "Jude",                1),
    ("NT", "Apoc",  "Revelation",         22),
]


def _fetch(url: str) -> str:
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "en-US,en;q=0.9",
    })
    with urllib.request.urlopen(req, timeout=20) as r:
        return r.read().decode("utf-8", errors="replace")


def _parse_chapter(raw: str) -> dict[str, str]:
    """
    Extract verses from a Knox chapter page.
    Structure: <div class="vers-no">N</div><div class="vers-content">text</div>
    """
    # Find all verse number / content pairs
    pairs = re.findall(
        r'<div[^>]*class="vers-no"[^>]*>(\d{1,3})</div>\s*'
        r'<div[^>]*class="vers-content"[^>]*>(.*?)</div>',
        raw, re.S
    )
    verses = {}
    for vnum, raw_text in pairs:
        text = html_mod.unescape(re.sub(r"<[^>]+>", " ", raw_text))
        text = re.sub(r"\s+", " ", text).strip()
        text = re.sub(r"[✻†‡]|\[\w\]", "", text).strip()
        if text:
            verses[vnum] = text
    return verses





def scrape_book(section: str, abbr: str, canon_name: str, num_chapters: int) -> dict:
    chapters: dict[str, dict] = {}
    for chap in range(1, num_chapters + 1):
        url = f"{BASE}/{section}/{abbr}/ch_{chap}"
        try:
            raw = _fetch(url)
            verses = _parse_chapter(raw)
            if verses:
                chapters[str(chap)] = verses
                print(f"  ch {chap:3}: {len(verses)} verses")
            else:
                print(f"  ch {chap:3}: ⚠  no verses parsed")
        except urllib.error.HTTPError as e:
            print(f"  ch {chap:3}: HTTP {e.code}")
        except Exception as e:
            print(f"  ch {chap:3}: ERROR {e}")
        time.sleep(0.4)
    return chapters


def main():
    out_dir = Path("data") / "kjv"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "knox.json"

    if out_path.exists():
        payload = json.loads(out_path.read_text(encoding="utf-8"))
        books = payload.get("books", {})
        print(f"Resuming — {len(books)} books already done.")
    else:
        books = {}

    source = ("Knox Bible, trans. Msgr. Ronald Knox (1945–49). "
              "© Baronius Press Ltd. catholicbible.online.")

    for section, abbr, canon_name, num_chapters in BOOKS:
        if canon_name in books:
            print(f"Skip {canon_name}")
            continue
        print(f"\n{canon_name}  [{section}/{abbr}]  {num_chapters} ch")
        chapters = scrape_book(section, abbr, canon_name, num_chapters)
        if chapters:
            books[canon_name] = chapters
        out_path.write_text(
            json.dumps({"source": source, "books": books}, indent=2, ensure_ascii=False),
            encoding="utf-8"
        )
        print(f"  → Saved ({len(chapters)} chapters)")

    total_v = sum(len(v) for b in books.values() for v in b.values())
    print(f"\nDone. {len(books)} books, {total_v:,} verses → {out_path}")


if __name__ == "__main__":
    main()
