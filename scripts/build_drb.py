"""Build data/drb.json, the Douay-Rheims Bible (Challoner), from Project Gutenberg ebook 8300.

The old drb.json (of unrecorded origin) had lost or misnumbered chapters in 25 books: Osee had 11 chapters, its
chapter 5 missing and 6 keyed as "5" from verse 17, and so on. Gutenberg's text marks every verse "C:V. text", so
each verse's chapter comes from its own number (two chapter headings, Job 39 and 1 Machabees 2, are missing there).
Challoner's notes and the chapter summaries are paragraphs without a verse number, and are left out.

Where the old file has the same verse at the same reference (most of them), its wording is kept: see overlay_old().
Gutenberg's text fills only the verses the old file lost or misplaced.

    python scripts/build_drb.py        # downloads pg8300.txt into scripts/.cache/douay/ if it isn't there
"""
import json
import re
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "scripts" / ".cache" / "douay" / "pg8300.txt"
URL = "https://www.gutenberg.org/cache/epub/8300/pg8300.txt"
OUT = ROOT / "data" / "drb.json"

# Gutenberg's heading name -> the book name drb.json uses (scripture_lookup._KJV_TO_DR maps onto these).
RENAME = {"Canticle of Canticles": "Canticles"}

HEADING = re.compile(r"^(.+?) Chapter \d+\s*$")
VERSE = re.compile(r"^(\d+):(\d+)[.:]?\s+(.*)$", re.S)  # "18:18." and a few "18:18:" or "12:20 "


def load_text() -> str:
    if not CACHE.exists():
        CACHE.parent.mkdir(parents=True, exist_ok=True)
        urllib.request.urlretrieve(URL, CACHE)
    text = CACHE.read_text(encoding="utf-8-sig")
    start = text.index("*** START OF")
    end = text.index("*** END OF")
    return text[text.index("\n", start):end]


def parse(text: str) -> dict:
    bible: dict = {}
    book = None
    offset = 0  # Psalm 9's second half (Hebrew Psalm 10) restarts at "9:1." but is 9:22-39 in the Douay
    for para in re.split(r"\n\s*\n", text.replace("\r\n", "\n")):
        para = para.strip()
        if not para:
            continue
        m = HEADING.match(para)
        if m and "\n" not in para:
            book = RENAME.get(m.group(1), m.group(1))
            bible.setdefault(book, {})
            offset = 0
            continue
        if para.startswith("(") and "according to the Hebrews" in para and book:
            last = max(bible[book], key=int)
            offset = len(bible[book][last])
            continue
        if not VERSE.match(para) or not book:
            continue
        # A few paragraphs hold two verses ("...horsemen.  4:32. Strike them...").
        for piece in re.split(r"\s{2,}(?=\d+:\d+[.:]?\s)", para):
            m = VERSE.match(piece)
            if not m:
                continue
            ch, vs, body = m.groups()
            if ch not in bible[book]:
                offset = 0
                # Psalms 115 and 147 keep the Hebrew numbering (115:10-19, 147:12-20); the Douay counts from 1.
                if book == "Psalms" and int(vs) > 1:
                    offset = 1 - int(vs)
            vs = str(int(vs) + offset)
            body = re.sub(r"\s+", " ", body).strip()
            chapter = bible[book].setdefault(ch, {})
            if vs in chapter:
                raise SystemExit(f"duplicate verse {book} {ch}:{vs}")
            chapter[vs] = body
    return bible


def check(bible: dict) -> list[str]:
    """Every book's chapters and verses run 1..n with no gaps."""
    problems = []
    for book, chapters in bible.items():
        nums = sorted(int(c) for c in chapters)
        if nums != list(range(1, len(nums) + 1)):
            problems.append(f"{book}: chapters {nums}")
        for c, verses in chapters.items():
            vnums = sorted(int(v) for v in verses)
            if vnums != list(range(1, len(vnums) + 1)):
                problems.append(f"{book} {c}: verses {vnums[:5]}... ({len(vnums)})")
    return problems


BASE_COMMIT = "afaeb9d"  # the old drb.json, as first committed


def words(s: str) -> list:
    return re.findall(r"[a-z']+", s.lower())


def clean_old(s: str) -> str:
    s = re.sub(r"\s*\[\s*(?:K\.|Kings|Title:)[^\]]*\]", "", s)   # its cross-references, "[ Kings xxiv.]"
    s = s.replace("()", "").replace("*", "")                      # its note marks
    return re.sub(r"\s+", " ", s).strip()


def overlay_old(bible: dict) -> int:
    """Keep the old file's wording wherever its verse is the same verse as Gutenberg's: it is the printing users had
    read, and Gutenberg's has its own typos ("acbab", "Banli", "languish with the heat of the field" for "beasts").
    A verse counts as the same when most of its words match; the old file's misnumbered chapters fail that test and
    keep Gutenberg's text."""
    import difflib
    import subprocess
    old = json.loads(subprocess.run(["git", "show", f"{BASE_COMMIT}:data/drb.json"], cwd=ROOT, capture_output=True,
                                    check=True).stdout.decode("utf-8"))
    kept = 0
    for book, chapters in bible.items():
        for c, verses in chapters.items():
            for v, text in verses.items():
                was = old.get(book, {}).get(c, {}).get(v)
                if was and difflib.SequenceMatcher(None, words(was), words(text)).ratio() >= 0.6:
                    verses[v] = clean_old(was)
                    kept += 1
    return kept


def main() -> None:
    bible = parse(load_text())
    kept = overlay_old(bible)
    for book, chapters in bible.items():  # chapters and verses in numeric order
        bible[book] = {c: dict(sorted(v.items(), key=lambda kv: int(kv[0])))
                       for c, v in sorted(chapters.items(), key=lambda kv: int(kv[0]))}
    problems = check(bible)
    if problems:
        print("\n".join(problems))
        sys.exit(1)
    OUT.write_text(json.dumps(bible, ensure_ascii=False, indent=1), encoding="utf-8")
    verses = sum(len(v) for ch in bible.values() for v in ch.values())
    print(f"{len(bible)} books, {verses} verses ({kept} in the old file's wording) -> {OUT}")


if __name__ == "__main__":
    main()
