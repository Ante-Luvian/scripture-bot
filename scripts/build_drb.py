"""Build data/drb.json, the Douay-Rheims Bible (Challoner; the 1899 American printing), from eBible.org's edition
(engDRA, USFM): https://ebible.org/find/show.php?id=engDRA

eBible's text is maintained and numbers the verses as the Vulgate does, which is how the bot keys the Douay-Rheims
(Psalm 22 is "The Lord ruleth me"; a psalm's title is part of its verse 1). It replaced (2026-11-12) a file pieced
together from Project Gutenberg's ebook 8300 and an older file of unknown origin, which had lost chapters, run seven
last verses into the verse before, and had typos ("Jones" for Jonas, "Abrabam", "oountenance").

    python scripts/build_drb.py        # downloads the USFM zip into scripts/.cache/douay/ if it isn't there
"""
import io
import json
import re
import sys
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "scripts" / ".cache" / "douay" / "engDRA_usfm.zip"
URL = "https://ebible.org/Scriptures/engDRA_usfm.zip"
OUT = ROOT / "data" / "drb.json"

# USFM book codes -> the book names drb.json uses (scripture_lookup._KJV_TO_DR maps onto these), in the Douay's order
BOOKS = {
    "GEN": "Genesis", "EXO": "Exodus", "LEV": "Leviticus", "NUM": "Numbers", "DEU": "Deuteronomy", "JOS": "Josue",
    "JDG": "Judges", "RUT": "Ruth", "1SA": "1 Kings", "2SA": "2 Kings", "1KI": "3 Kings", "2KI": "4 Kings",
    "1CH": "1 Paralipomenon", "2CH": "2 Paralipomenon", "EZR": "1 Esdras", "NEH": "2 Esdras", "TOB": "Tobias",
    "JDT": "Judith", "EST": "Esther", "JOB": "Job", "PSA": "Psalms", "PRO": "Proverbs", "ECC": "Ecclesiastes",
    "SNG": "Canticles", "WIS": "Wisdom", "SIR": "Ecclesiasticus", "ISA": "Isaias", "JER": "Jeremias",
    "LAM": "Lamentations", "BAR": "Baruch", "EZK": "Ezechiel", "DAN": "Daniel", "HOS": "Osee", "JOL": "Joel",
    "AMO": "Amos", "OBA": "Abdias", "JON": "Jonas", "MIC": "Micheas", "NAM": "Nahum", "HAB": "Habacuc",
    "ZEP": "Sophonias", "HAG": "Aggeus", "ZEC": "Zacharias", "MAL": "Malachias", "1MA": "1 Machabees",
    "2MA": "2 Machabees", "MAT": "Matthew", "MRK": "Mark", "LUK": "Luke", "JHN": "John", "ACT": "Acts",
    "ROM": "Romans", "1CO": "1 Corinthians", "2CO": "2 Corinthians", "GAL": "Galatians", "EPH": "Ephesians",
    "PHP": "Philippians", "COL": "Colossians", "1TH": "1 Thessalonians", "2TH": "2 Thessalonians",
    "1TI": "1 Timothy", "2TI": "2 Timothy", "TIT": "Titus", "PHM": "Philemon", "HEB": "Hebrews", "JAS": "James",
    "1PE": "1 Peter", "2PE": "2 Peter", "1JN": "1 John", "2JN": "2 John", "3JN": "3 John", "JUD": "Jude",
    "REV": "Apocalypse",
}
HEADINGS = re.compile(r"\\(?:id|h|toc\d|mt\d?|cl|ms\d?|s\d?|d)\b")


def load() -> dict:
    """{book code: USFM text}"""
    if not CACHE.exists():
        CACHE.parent.mkdir(parents=True, exist_ok=True)
        urllib.request.urlretrieve(URL, CACHE)
    out = {}
    with zipfile.ZipFile(io.BytesIO(CACHE.read_bytes())) as z:
        for name in z.namelist():
            m = re.match(r"\d+-(\w+?)engDRA\.usfm$", name)
            if m:
                out[m.group(1)] = z.read(name).decode("utf-8-sig")
    return out


def parse(usfm: str) -> dict:
    """{chapter: {verse: text}}"""
    usfm = re.sub(r"\\f .*?\\f\*|\\x .*?\\x\*", "", usfm, flags=re.S)            # (it has no notes, but in case)
    usfm = re.sub(r"\\\+?w ([^|\\]*)\|[^\\]*\\\+?w\*", r"\1", usfm)              # \w word|strong="H1234"\w*
    book, chapter, verse = {}, None, None
    for line in usfm.splitlines():
        if m := re.match(r"\\c (\d+)", line):
            chapter, verse = book.setdefault(m.group(1), {}), None
        elif m := re.match(r"\\v (\d+)\S*\s?(.*)", line):
            verse = m.group(1)
            if verse in chapter:
                raise SystemExit(f"duplicate verse {verse}")
            chapter[verse] = m.group(2)
        elif verse and not HEADINGS.match(line):
            chapter[verse] += " " + re.sub(r"^\\\w+\s*", "", line)               # \q1 / \p: a new line, same verse
    for verses in book.values():
        for v, text in verses.items():
            verses[v] = re.sub(r"\s+", " ", re.sub(r"\\\+?\w+\*?", "", text)).strip()
    return book


def check(bible: dict) -> list[str]:
    """Every book's chapters and verses run 1..n with no gaps, and no verse is empty."""
    problems = []
    for book, chapters in bible.items():
        if sorted(int(c) for c in chapters) != list(range(1, len(chapters) + 1)):
            problems.append(f"{book}: chapters {sorted(chapters, key=int)}")
        for c, verses in chapters.items():
            if sorted(int(v) for v in verses) != list(range(1, len(verses) + 1)):
                problems.append(f"{book} {c}: verses {sorted(verses, key=int)[:5]}... ({len(verses)})")
            problems += [f"{book} {c}:{v} is empty" for v, t in verses.items() if not t]
    return problems


def main() -> None:
    usfm = load()
    missing = set(BOOKS) - set(usfm)
    if missing:
        raise SystemExit(f"not in the download: {sorted(missing)}")
    bible = {name: parse(usfm[code]) for code, name in BOOKS.items()}
    for book, chapters in bible.items():  # chapters and verses in numeric order
        bible[book] = {c: dict(sorted(v.items(), key=lambda kv: int(kv[0])))
                       for c, v in sorted(chapters.items(), key=lambda kv: int(kv[0]))}
    problems = check(bible)
    if problems:
        print("\n".join(problems))
        sys.exit(1)
    OUT.write_text(json.dumps(bible, ensure_ascii=False, indent=1), encoding="utf-8")
    verses = sum(len(v) for ch in bible.values() for v in ch.values())
    print(f"{len(bible)} books, {verses} verses -> {OUT}")


if __name__ == "__main__":
    main()
