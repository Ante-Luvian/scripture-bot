"""
Build script: converts Clear-Bible/Biblica's MACULA Greek and Hebrew
linguistic datasets (CC BY 4.0) into data/interlinear/macula.db, a SQLite
database of every word in the Greek NT (SBLGNT) and Hebrew OT (WLC) with
its real per-instance transliteration, Strong's number, and English gloss
-- a genuine word-aligned interlinear built by linguists, not reconstructed
by matching Strong's numbers across two independently-tagged texts (the
project's earlier approach, which broke whenever the two tagging systems
disagreed -- e.g. Tischendorf tags every form of "to be" as G1510, but the
KJV's own Strong's tagging gives the imperfect "was" its own number, G2258,
so the alignment silently found no match and fell back to a lexicon gloss
of "am" for John 1:1's three "was"es).

Sources (both CC BY 4.0, Clear-Bible / Biblica, Inc., 2022-2024):
  https://github.com/Clear-Bible/macula-greek  (SBLGNT/tsv/macula-greek-SBLGNT.tsv)
  https://github.com/Clear-Bible/macula-hebrew (WLC/tsv/macula-hebrew.tsv, Git LFS)
The Greek dataset's `english`/`mandarin` columns are Cherith Analytics'
"Cherith Glosses for the Greek New Testament" (Andi Wu, CC BY 4.0),
incorporated into MACULA with attribution. The Hebrew dataset's
`transliteration` column is MACULA's own; its `english` column is the
Hebrew Cherith Glosses (Andi Wu, CC BY 4.0). Required attribution per both
LICENSE.md files:
  "MACULA Greek Linguistic Datasets, available at https://github.com/Clear-Bible/macula-greek/"
  "MACULA Hebrew Linguistic Datasets, available at https://github.com/Clear-Bible/macula-hebrew/"

The Greek TSV has no transliteration column (Greek transliteration in this
project's !interlinear comes from the existing local Strong's dictionary,
keyed by Strong's number -- lexeme-level, same as before). The Hebrew TSV
has a genuine per-word transliteration column, used directly.

Downloads its own source -- run from anywhere (needs `requests` for the
Hebrew file, which is Git-LFS-backed and must go through media.githubusercontent.com):
    python deprecated/build_macula_interlinear.py
"""
import re
import sqlite3
import urllib.request
from pathlib import Path

GREEK_URL = "https://raw.githubusercontent.com/Clear-Bible/macula-greek/main/SBLGNT/tsv/macula-greek-SBLGNT.tsv"
HEBREW_URL = "https://media.githubusercontent.com/media/Clear-Bible/macula-hebrew/main/WLC/tsv/macula-hebrew.tsv"
OUT_DIR = Path(__file__).parent.parent / "data" / "interlinear"
OUT_PATH = OUT_DIR / "macula.db"

# USFM 3-letter codes, in canonical Bible order -- confirmed directly against
# both TSVs (39 OT codes, 27 NT codes; both sets matched exactly). Zipped
# with scripture_lookup.py's BIBLE_OT/BIBLE_NT, which use the same order.
OT_CODES = ["GEN","EXO","LEV","NUM","DEU","JOS","JDG","RUT","1SA","2SA","1KI","2KI",
            "1CH","2CH","EZR","NEH","EST","JOB","PSA","PRO","ECC","SNG","ISA",
            "JER","LAM","EZK","DAN","HOS","JOL","AMO","OBA","JON","MIC","NAM","HAB",
            "ZEP","HAG","ZEC","MAL"]
NT_CODES = ["MAT","MRK","LUK","JHN","ACT","ROM","1CO","2CO","GAL","EPH",
            "PHP","COL","1TH","2TH","1TI","2TI","TIT","PHM","HEB","JAS",
            "1PE","2PE","1JN","2JN","3JN","JUD","REV"]
BIBLE_OT = ["Genesis","Exodus","Leviticus","Numbers","Deuteronomy","Joshua",
            "Judges","Ruth","1 Samuel","2 Samuel","1 Kings","2 Kings",
            "1 Chronicles","2 Chronicles","Ezra","Nehemiah","Esther","Job",
            "Psalms","Proverbs","Ecclesiastes","Song of Solomon","Isaiah",
            "Jeremiah","Lamentations","Ezekiel","Daniel","Hosea","Joel",
            "Amos","Obadiah","Jonah","Micah","Nahum","Habakkuk","Zephaniah",
            "Haggai","Zechariah","Malachi"]
BIBLE_NT = ["Matthew","Mark","Luke","John","Acts","Romans",
            "1 Corinthians","2 Corinthians","Galatians","Ephesians",
            "Philippians","Colossians","1 Thessalonians","2 Thessalonians",
            "1 Timothy","2 Timothy","Titus","Philemon","Hebrews","James",
            "1 Peter","2 Peter","1 John","2 John","3 John","Jude","Revelation"]
CODE_TO_BOOK = dict(zip(OT_CODES, BIBLE_OT)) | dict(zip(NT_CODES, BIBLE_NT))

REF_RE = re.compile(r"^([A-Z0-9]+) (\d+):(\d+)!(\d+)")


def _fetch_lines(url):
    req = urllib.request.Request(url, headers={"User-Agent": "ScriptureBot/1.0"})
    with urllib.request.urlopen(req, timeout=120) as r:
        for line in r:
            yield line.decode("utf-8", errors="replace")


def _norm_greek_strong(raw: str) -> str:
    raw = raw.strip()
    if not raw or not raw[0].isdigit():
        return ""
    return f"G{raw}"


def _norm_hebrew_strong(raw: str) -> str:
    raw = raw.strip()
    m = re.match(r"0*(\d+)([a-z]?)", raw)
    if not m:
        return ""
    return f"H{m.group(1)}{m.group(2)}"


def _process(url, testament, cur):
    lines = _fetch_lines(url)
    header = next(lines).rstrip("\n").split("\t")
    idx = {name: i for i, name in enumerate(header)}
    count = 0
    batch = []
    for line in lines:
        cols = line.rstrip("\n").split("\t")
        ref = cols[idx["ref"]] if idx["ref"] < len(cols) else ""
        m = REF_RE.match(ref)
        if not m:
            continue
        code, chapter, verse, word_order = m.group(1), int(m.group(2)), int(m.group(3)), int(m.group(4))
        book = CODE_TO_BOOK.get(code)
        if not book:
            continue

        def get(col):
            i = idx.get(col)
            return cols[i].strip() if i is not None and i < len(cols) else ""

        text = get("text")
        english = get("english") or get("gloss")
        if testament == "nt":
            strong = _norm_greek_strong(get("strong"))
            translit = ""  # filled in from the local Strong's dictionary at query time (lexeme-level)
        else:
            strong = _norm_hebrew_strong(get("strongnumberx"))
            translit = get("transliteration")

        batch.append((testament, book, chapter, verse, word_order, text, translit, strong, english))
        count += 1
        if len(batch) >= 5000:
            cur.executemany(
                "INSERT INTO words (testament, book, chapter, verse, word_order, text, translit, strong, gloss) "
                "VALUES (?,?,?,?,?,?,?,?,?)", batch)
            batch = []
    if batch:
        cur.executemany(
            "INSERT INTO words (testament, book, chapter, verse, word_order, text, translit, strong, gloss) "
            "VALUES (?,?,?,?,?,?,?,?,?)", batch)
    return count


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    if OUT_PATH.exists():
        OUT_PATH.unlink()
    con = sqlite3.connect(OUT_PATH)
    cur = con.cursor()
    cur.execute("""
        CREATE TABLE words (
            testament TEXT, book TEXT, chapter INTEGER, verse INTEGER, word_order INTEGER,
            text TEXT, translit TEXT, strong TEXT, gloss TEXT
        )
    """)

    nt_count = _process(GREEK_URL, "nt", cur)
    print(f"Greek NT: {nt_count} words")
    ot_count = _process(HEBREW_URL, "ot", cur)
    print(f"Hebrew OT: {ot_count} words")

    cur.execute("CREATE INDEX idx_verse ON words (book, chapter, verse, word_order)")
    con.commit()
    con.close()
    print(f"Wrote {OUT_PATH} -- {nt_count + ot_count} total words")


if __name__ == "__main__":
    main()
