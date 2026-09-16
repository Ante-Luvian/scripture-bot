"""
Build script: converts OpenBible.info's Treasury of Scripture Knowledge
cross-reference dataset (https://www.openbible.info/labs/cross-references/,
CC-BY, ~340k rows, derived from the public-domain Treasury of Scripture
Knowledge) into data/cross_references/cross_references.json for the
scripture bot's !xref command.

Downloads the source itself -- run from anywhere:
    python deprecated/build_cross_references.py
"""
import io
import json
import re
import urllib.request
import zipfile
from pathlib import Path

SOURCE_URL = "https://a.openbible.info/data/cross-references.zip"
OUT_DIR = Path(__file__).parent.parent / "data" / "cross_references"
OUT_PATH = OUT_DIR / "cross_references.json"

BOOK_MAP = {
    "1Chr": "1 Chronicles", "1Cor": "1 Corinthians", "1John": "1 John", "1Kgs": "1 Kings",
    "1Pet": "1 Peter", "1Sam": "1 Samuel", "1Thess": "1 Thessalonians", "1Tim": "1 Timothy",
    "2Chr": "2 Chronicles", "2Cor": "2 Corinthians", "2John": "2 John", "2Kgs": "2 Kings",
    "2Pet": "2 Peter", "2Sam": "2 Samuel", "2Thess": "2 Thessalonians", "2Tim": "2 Timothy",
    "3John": "3 John", "Acts": "Acts", "Amos": "Amos", "Col": "Colossians", "Dan": "Daniel",
    "Deut": "Deuteronomy", "Eccl": "Ecclesiastes", "Eph": "Ephesians", "Esth": "Esther",
    "Exod": "Exodus", "Ezek": "Ezekiel", "Ezra": "Ezra", "Gal": "Galatians", "Gen": "Genesis",
    "Hab": "Habakkuk", "Hag": "Haggai", "Heb": "Hebrews", "Hos": "Hosea", "Isa": "Isaiah",
    "Jas": "James", "Jer": "Jeremiah", "Job": "Job", "Joel": "Joel", "John": "John",
    "Jonah": "Jonah", "Josh": "Joshua", "Jude": "Jude", "Judg": "Judges", "Lam": "Lamentations",
    "Lev": "Leviticus", "Luke": "Luke", "Mal": "Malachi", "Mark": "Mark", "Matt": "Matthew",
    "Mic": "Micah", "Nah": "Nahum", "Neh": "Nehemiah", "Num": "Numbers", "Obad": "Obadiah",
    "Phil": "Philippians", "Phlm": "Philemon", "Prov": "Proverbs", "Ps": "Psalms",
    "Rev": "Revelation", "Rom": "Romans", "Ruth": "Ruth", "Song": "Song of Solomon",
    "Titus": "Titus", "Zech": "Zechariah", "Zeph": "Zephaniah",
}

REF_RE = re.compile(r"^([1-3]?[A-Za-z]+)\.(\d+)\.(\d+)$")


def parse_single(ref: str):
    m = REF_RE.match(ref)
    if not m:
        return None
    book, chap, verse = m.groups()
    canon = BOOK_MAP.get(book)
    if not canon:
        return None
    return canon, int(chap), int(verse)


def format_to_ref(raw: str) -> str | None:
    if "-" in raw:
        left, right = raw.split("-", 1)
        lp, rp = parse_single(left), parse_single(right)
        if not lp or not rp:
            return None
        lbook, lchap, lverse = lp
        rbook, rchap, rverse = rp
        if lbook == rbook and lchap == rchap:
            return f"{lbook} {lchap}:{lverse}-{rverse}"
        elif lbook == rbook:
            return f"{lbook} {lchap}:{lverse}-{rchap}:{rverse}"
        else:
            return f"{lbook} {lchap}:{lverse}-{rbook} {rchap}:{rverse}"
    else:
        p = parse_single(raw)
        if not p:
            return None
        book, chap, verse = p
        return f"{book} {chap}:{verse}"


def main():
    req = urllib.request.Request(SOURCE_URL, headers={"User-Agent": "ScriptureBot/1.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        zip_bytes = r.read()
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        name = next(n for n in zf.namelist() if n.endswith(".txt"))
        raw_text = zf.read(name).decode("utf-8")

    result: dict[str, list] = {}
    skipped = 0
    lines = raw_text.split("\n")
    for line in lines[1:]:  # skip header
        if not line.strip():
            continue
        parts = line.rstrip("\r").split("\t")
        if len(parts) < 3:
            continue
        from_raw, to_raw, votes_raw = parts[0], parts[1], parts[2]
        from_p = parse_single(from_raw)
        if not from_p:
            skipped += 1
            continue
        fbook, fchap, fverse = from_p
        from_key = f"{fbook} {fchap}:{fverse}"
        to_display = format_to_ref(to_raw)
        if not to_display:
            skipped += 1
            continue
        try:
            votes = int(votes_raw)
        except ValueError:
            votes = 0
        result.setdefault(from_key, []).append([to_display, votes])

    for key in result:
        result[key].sort(key=lambda x: x[1], reverse=True)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
    print(f"Wrote {OUT_PATH} — {len(result)} source verses, "
          f"{sum(len(v) for v in result.values())} total references, {skipped} rows skipped")


if __name__ == "__main__":
    main()
