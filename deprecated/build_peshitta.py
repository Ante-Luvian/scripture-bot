#!/usr/bin/env python3
"""
build_peshitta.py
Builds data/peshitta_ot.json and data/peshitta_nt.json from ETCBC repos.

Prerequisites (run in your bot directory first):
    git clone https://github.com/ETCBC/peshitta.git
    git clone https://github.com/ETCBC/syrnt.git

Then:
    python build_peshitta.py
"""
import json, re
from pathlib import Path

BASE = Path.cwd()

def find_repo(name):
    p = BASE / name
    if p.exists():
        return p
    raise FileNotFoundError(
        f"Cannot find {name}/ in {BASE}\n"
        f"Run: git clone https://github.com/ETCBC/{name}.git"
    )

# ── Book name maps ─────────────────────────────────────────────────────────────

OT_BOOK_MAP = {
    "Genesis":"Genesis","Exodus":"Exodus","Leviticus":"Leviticus",
    "Numbers":"Numbers","Deuteronomy":"Deuteronomy","Joshua":"Joshua",
    "Judges":"Judges","Ruth":"Ruth",
    "Samuel_1":"1 Samuel","Samuel_2":"2 Samuel",
    "Kings_1":"1 Kings","Kings_2":"2 Kings",
    "Chronicles_1":"1 Chronicles","Chronicles_2":"2 Chronicles",
    "Ezra":"Ezra","Nehemia":"Nehemiah","Esther":"Esther",
    "Job":"Job","Psalms":"Psalms","Proverbs":"Proverbs",
    "Ecclesiastes":"Ecclesiastes","Song_of_Songs":"Song of Solomon",
    "Isaiah":"Isaiah","Jeremiah":"Jeremiah","Lamentations":"Lamentations",
    "Ezekiel":"Ezekiel","Daniel":"Daniel","Hosea":"Hosea","Joel":"Joel",
    "Amos":"Amos","Obadiah":"Obadiah","Jonah":"Jonah","Micah":"Micah",
    "Nahum":"Nahum","Habakkuk":"Habakkuk","Zephaniah":"Zephaniah",
    "Haggai":"Haggai","Zechariah":"Zechariah","Malachi":"Malachi",
    # Deuterocanon — prefer _A recension
    "Tobit_A":"Tobit","Judith":"Judith",
    "Wisdom_of_Solomon":"Wisdom of Solomon","Sirach":"Sirach",
    "Baruch":"Baruch","Letter_of_Jeremiah":"Epistle of Jeremiah",
    "Susanna":"Susanna","Bel_and_the_Dragon":"Bel and the Dragon",
    "Maccabees_1_A":"1 Maccabees","Maccabees_2":"2 Maccabees",
    "Maccabees_3":"3 Maccabees","Maccabees_4":"4 Maccabees",
    "Esdras_3":"1 Esdras","Esdras_4":"2 Esdras",
    "Prayer_of_Manasseh_A":"Prayer of Manasseh",
    "Psalms_of_Solomon":"Psalms of Solomon",
    "Apocalypse_of_Baruch":"2 Baruch",
    # Intentionally skipped: Tobit_B, Maccabees_1_B, Prayer_of_Manasseh_B,
    # Apocryphal_Psalms*, Letter_of_Baruch_*, Odes
}

NT_BOOK_MAP = {
    "Matthew":"Matthew","Mark":"Mark","Luke":"Luke","John":"John",
    "Acts":"Acts","Romans":"Romans",
    "1_Corinthians":"1 Corinthians","2_Corinthians":"2 Corinthians",
    "Galatians":"Galatians","Ephesians":"Ephesians",
    "Philippians":"Philippians","Colossians":"Colossians",
    "1_Thessalonians":"1 Thessalonians","2_Thessalonians":"2 Thessalonians",
    "1_Timothy":"1 Timothy","2_Timothy":"2 Timothy",
    "Titus":"Titus","Philemon":"Philemon","Hebrews":"Hebrews",
    "James":"James","1_Peter":"1 Peter","2_Peter":"2 Peter",
    "1_John":"1 John","2_John":"2 John","3_John":"3 John",
    "Jude":"Jude","Revelation":"Revelation",
}

# Chapter header patterns:
#   OT: "Chapter 1"  or  "Chapter 1\r"
#   NT: "Matt 1"  or  "1 Cor 2"  (book abbrev + space + number)
#       also the first line "Matthew (Matt)" is a book title — skip it
_CHAP_HEADER_OT = re.compile(r'^Chapter\s+(\d+)', re.I)
_VERSE_LINE     = re.compile(r'^(\d+)\s+(.*)')


def parse_plain(path, is_nt=False):
    """
    Parse ETCBC plain/0.1 format.

    OT: "Chapter N" headers, then "N text" verse lines, continuations on next line.
    NT: "Book N" chapter headers (e.g. "Matt 1"), then "N text" verse lines.
    Book title lines like "Matthew (Matt)" are skipped (no trailing integer).

    Returns {chapter_str: {verse_str: text}}
    """
    chaps = {}
    current_chap = None
    current_verse = None
    current_text = []

    def flush():
        if current_chap and current_verse and current_text:
            chaps.setdefault(str(current_chap), {})[str(current_verse)] = (
                " ".join(current_text).strip()
            )

    with open(path, encoding="utf-8") as f:
        for raw in f:
            line = raw.rstrip()

            if not line:
                flush()
                current_verse = None
                current_text = []
                continue

            # OT chapter header: "Chapter N"
            m = _CHAP_HEADER_OT.match(line)
            if m:
                flush(); current_verse = None; current_text = []
                current_chap = int(m.group(1))
                continue

            # NT chapter header: any line whose last token is a bare integer
            # and that doesn't look like a verse line (verse lines start digit+space+Syriac)
            if is_nt:
                parts = line.split()
                if parts and parts[-1].isdigit() and not _VERSE_LINE.match(line):
                    flush(); current_verse = None; current_text = []
                    current_chap = int(parts[-1])
                    continue

            # Verse line: starts with an integer
            m3 = _VERSE_LINE.match(line)
            if m3 and current_chap is not None:
                flush()
                current_verse = int(m3.group(1))
                current_text = [m3.group(2).strip()]
                continue

            # Continuation (wrapped Syriac text)
            if current_verse is not None:
                current_text.append(line.strip())

    flush()
    return chaps


def build(repo_path, book_map, is_nt=False):
    plain_dir = repo_path / "plain" / "0.1"
    txt_files = sorted(plain_dir.glob("*.txt"))
    print(f"  Reading {len(txt_files)} files from {plain_dir}")

    books = {}
    used = set()
    skipped_intentional = []
    skipped_unknown = []

    for txt_file in txt_files:
        stem = txt_file.stem
        target = book_map.get(stem)
        if not target:
            skipped_unknown.append(stem)
            continue
        if target in used:
            skipped_intentional.append(f"{stem}(dup)")
            continue
        chaps = parse_plain(txt_file, is_nt=is_nt)
        if chaps:
            books[target] = chaps
            used.add(target)
        else:
            print(f"  WARNING: {stem} parsed but got 0 chapters")

    total = sum(sum(len(v) for v in c.values()) for c in books.values())
    print(f"  Loaded: {len(books)} books, {total:,} verses")
    if skipped_intentional:
        print(f"  Skipped duplicates: {', '.join(skipped_intentional)}")
    if skipped_unknown:
        print(f"  Unknown stems (not in map): {', '.join(sorted(skipped_unknown))}")
    return books


def main():
    out_dir = Path("data")
    out_dir.mkdir(exist_ok=True)

    # ── Peshitta OT ──────────────────────────────────────────────────────────
    try:
        repo = find_repo("peshitta")
        print(f"Building Peshitta OT from {repo.name}/")
        books = build(repo, OT_BOOK_MAP, is_nt=False)

        for label, book, c, v in [
            ("Genesis 1:1",          "Genesis",            "1","1"),
            ("Genesis 1:2",          "Genesis",            "1","2"),
            ("Psalms 23:1",          "Psalms",             "23","1"),
            ("Sirach 1:1",           "Sirach",             "1","1"),
            ("Tobit 1:1",            "Tobit",              "1","1"),
            ("Prayer of Manasseh 1", "Prayer of Manasseh", "1","1"),
            ("1 Esdras 1:1",         "1 Esdras",           "1","1"),
        ]:
            text = books.get(book,{}).get(c,{}).get(v,"NOT FOUND")
            print(f"  {label}: {text[:70]}")

        out = out_dir / "peshitta_ot.json"
        out.write_text(json.dumps({
            "source": "Peshitta OT (ETCBC / Peshitta Institute Leiden). Non-commercial research use.",
            "lang": "syc",
            "books": books,
        }, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"  Saved {out} ({out.stat().st_size/1024/1024:.1f} MB)")
    except FileNotFoundError as e:
        print(f"Peshitta OT skipped: {e}")

    # ── Syriac NT ─────────────────────────────────────────────────────────────
    try:
        repo = find_repo("syrnt")
        print(f"\nBuilding Syriac NT from {repo.name}/")
        books = build(repo, NT_BOOK_MAP, is_nt=True)

        for label, book, c, v in [
            ("John 3:16",   "John",       "3","16"),
            ("Matt 1:1",    "Matthew",    "1","1"),
            ("Rev 22:21",   "Revelation", "22","21"),
        ]:
            text = books.get(book,{}).get(c,{}).get(v,"NOT FOUND")
            print(f"  {label}: {text[:70]}")

        out = out_dir / "peshitta_nt.json"
        out.write_text(json.dumps({
            "source": "Syriac NT Peshitta (ETCBC/SEDRA, George Kiraz & James Bennett). Non-commercial research use.",
            "lang": "syc",
            "books": books,
        }, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"  Saved {out} ({out.stat().st_size/1024/1024:.1f} MB)")
    except FileNotFoundError as e:
        print(f"Syriac NT skipped: {e}")


if __name__ == "__main__":
    main()
