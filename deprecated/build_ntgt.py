#!/usr/bin/env python3
"""
build_ntgt.py — Build data/ntgt.json from morphgnt/tischendorf-data
Clones the repo (shallow) and parses the word-per-line Unicode files.

Run from your bot directory:
    python build_ntgt.py
Requires git to be installed.
"""
import subprocess, json, re
from pathlib import Path
from collections import defaultdict

REPO_URL = "https://github.com/morphgnt/tischendorf-data.git"
CLONE_DIR = Path("tischendorf-data")
TEXT_DIR  = CLONE_DIR / "word-per-line" / "1.5" / "Unicode"
OUT       = Path("data") / "ntgt.json"

BOOK_MAP = {
    "MAT":"Matthew","MRK":"Mark","LUK":"Luke","JOH":"John",
    "ACT":"Acts","ROM":"Romans","1CO":"1 Corinthians","2CO":"2 Corinthians",
    "GAL":"Galatians","EPH":"Ephesians","PHP":"Philippians","COL":"Colossians",
    "1TH":"1 Thessalonians","2TH":"2 Thessalonians","1TI":"1 Timothy",
    "2TI":"2 Timothy","TIT":"Titus","PHM":"Philemon","HEB":"Hebrews",
    "JAS":"James","1PE":"1 Peter","2PE":"2 Peter","1JO":"1 John",
    "2JO":"2 John","3JO":"3 John","JUD":"Jude","REV":"Revelation",
}

def clone():
    if TEXT_DIR.exists():
        print(f"Using existing {CLONE_DIR}")
        return True
    print(f"Cloning {REPO_URL} (shallow)...")
    r = subprocess.run(
        ["git", "clone", "--depth=1", REPO_URL, str(CLONE_DIR)],
        capture_output=True, text=True
    )
    if r.returncode != 0:
        print(f"git clone failed:\n{r.stderr}")
        return False
    return True

def parse():
    books_out = {}
    for txt in sorted(TEXT_DIR.glob("*.txt")):
        abbr = txt.stem  # e.g. "JOH"
        canon = BOOK_MAP.get(abbr)
        if not canon:
            print(f"  Skipping unknown book: {abbr}")
            continue

        verse_words = defaultdict(list)
        for line in txt.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            parts = line.split()
            if len(parts) < 2:
                continue
            ref = parts[0]        # e.g. JOH 3:16.1 — but ref is first token
            word = parts[1]       # Greek word form
            # ref format: BOOK CHAP:VERSE.WORDNUM  but split on whitespace
            # actually the file has: BOOK CHAP:VERSE.WORDNUM  word  parse strongs lemma ! lemma
            # with space-separated columns — ref is parts[0] e.g. "JOH" and parts[1] is "3:16.1"?
            # Let's check: line example: "JOH 3:16.1 οὕτως ADV 3779 οὕτως ! οὕτως"
            if len(parts) >= 3 and ':' in parts[1]:
                cv_word = parts[1]   # "3:16.1"
                greek   = parts[2]   # "οὕτως"
                m = re.match(r'^(\d+):(\d+)\.\d+$', cv_word)
                if m:
                    chap, verse = m.group(1), m.group(2)
                    # strip trailing punctuation from word
                    greek = re.sub(r'[·,.;·]$', '', greek)
                    verse_words[(chap, verse)].append(greek)

        if not verse_words:
            print(f"  No verses parsed for {abbr}")
            continue

        chaps_out = {}
        for (chap, verse), words in sorted(verse_words.items(),
                                            key=lambda x: (int(x[0][0]), int(x[0][1]))):
            chaps_out.setdefault(chap, {})[verse] = " ".join(words)

        books_out[canon] = chaps_out
        total = sum(len(v) for v in chaps_out.values())
        print(f"  {canon}: {len(chaps_out)} chapters, {total} verses")

    return books_out

def main():
    if not clone():
        return

    print("Parsing...")
    books = parse()
    if not books:
        print("No books parsed — check TEXT_DIR path")
        return

    # Spot check
    jn316 = books.get("John", {}).get("3", {}).get("16", "NOT FOUND")
    print(f"\nJohn 3:16: {jn316[:80]}")

    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps({
        "source": "Tischendorf 8th ed. Greek NT. morphgnt/tischendorf-data. Public domain.",
        "lang": "grc",
        "books": books,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nSaved {OUT} ({OUT.stat().st_size/1024/1024:.1f} MB)")

if __name__ == "__main__":
    main()
