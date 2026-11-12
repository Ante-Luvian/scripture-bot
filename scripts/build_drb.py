"""Build data/drb.json, the Douay-Rheims Bible (Challoner; the 1899 John Murphy printing), from drbo.org (Douay-Rheims
Bible Online, https://www.drbo.org/about.htm), whose text was typed from a hardcopy of that printing.

drbo.org numbers the verses as the Vulgate does, which is how the bot keys the Douay-Rheims (Psalm 22 is "The Lord
ruleth me"; a psalm's title is part of its verse 1). It replaced (2026-11-12) eBible.org's engDRA, a scan of the same
printing with hundreds of slips ("offer leaves" for loaves, "the Lard", "Israel Israel was a child"), which had
itself replaced a file pieced together from Project Gutenberg's ebook 8300 and an older file of unknown origin.

drbo.org's typing slips ("Amen" for Amon, "the sills of" for sins, "Machir beget Galaad", "and and") are corrected
from scripts/drb_fixes.json, {"Book c:v": [[wrong, right], ...]}: only readings Project Gutenberg's ebook 8300 and
EntireBible-DR.json agree on, and only where drbo.org's word is plainly a slip (a wrong name, a non-word, a dropped or
doubled word); where it's a grammatical reading of its own (drbo.org's "Palestines", "to hell") it's left alone. Each
fix's first half must occur exactly once in its verse, so a fix that no longer fits stops the build instead of going
astray. TITLES restores psalm titles drbo.org leaves out (Psalms 123-133's "A gradual canticle").

    python scripts/build_drb.py        # downloads the chapter pages into scripts/.cache/douay/drbo/ if not there
"""
import html
import json
import re
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "scripts" / ".cache" / "douay" / "drbo"
SITE = "https://www.drbo.org/chapter/"
OUT = ROOT / "data" / "drb.json"

# drbo.org's book numbers (1-73, the Douay's order) -> the book names drb.json uses
BOOKS = ["Genesis", "Exodus", "Leviticus", "Numbers", "Deuteronomy", "Josue", "Judges", "Ruth", "1 Kings", "2 Kings",
         "3 Kings", "4 Kings", "1 Paralipomenon", "2 Paralipomenon", "1 Esdras", "2 Esdras", "Tobias", "Judith",
         "Esther", "Job", "Psalms", "Proverbs", "Ecclesiastes", "Canticles", "Wisdom", "Ecclesiasticus", "Isaias",
         "Jeremias", "Lamentations", "Baruch", "Ezechiel", "Daniel", "Osee", "Joel", "Amos", "Abdias", "Jonas",
         "Micheas", "Nahum", "Habacuc", "Sophonias", "Aggeus", "Zacharias", "Malachias", "1 Machabees", "2 Machabees",
         "Matthew", "Mark", "Luke", "John", "Acts", "Romans", "1 Corinthians", "2 Corinthians", "Galatians",
         "Ephesians", "Philippians", "Colossians", "1 Thessalonians", "2 Thessalonians", "1 Timothy", "2 Timothy",
         "Titus", "Philemon", "Hebrews", "James", "1 Peter", "2 Peter", "1 John", "2 John", "3 John", "Jude",
         "Apocalypse"]
FIXES = json.loads((ROOT / "scripts" / "drb_fixes.json").read_text(encoding="utf-8"))
# Psalm titles drbo.org leaves out (it shows a summary of the psalm instead), as Gutenberg's ebook 8300 has them
TITLES = {"109": "A psalm for David.", "123": "A gradual canticle.", "124": "A gradual canticle.",
          "125": "A gradual canticle.", "126": "A gradual canticle of Solomon.", "127": "A gradual canticle.",
          "128": "A gradual canticle.", "129": "A gradual canticle.", "130": "A gradual canticle of David.",
          "131": "A gradual canticle.", "132": "A gradual canticle of David.", "133": "A gradual canticle.",
          "134": "Alleluia.", "135": "Alleluia.", "137": "For David himself.", "138": "Unto the end, a psalm of David.",
          "142": "A psalm of David, when his son Absalom pursued him.", "144": "Praise, for David himself.",
          "146": "Alleluia."}
UA = {"User-Agent": "Mozilla/5.0 (ScriptureBot; building a local copy of the Douay-Rheims)"}


def page(name: str) -> str:
    f = CACHE / name
    if not f.exists():
        CACHE.mkdir(parents=True, exist_ok=True)
        req = urllib.request.Request(SITE + name, headers=UA)
        f.write_bytes(urllib.request.urlopen(req, timeout=60).read())
        time.sleep(0.3)
    return f.read_text(encoding="latin-1" if b"charset=iso-8859-1" in f.read_bytes()[:2000].lower() else "utf-8")


def chapters():
    """(book number, chapter, page) for every chapter; a book's chapters are the chapter-number links on its first."""
    for b in range(1, len(BOOKS) + 1):
        first = page(f"{b:02d}001.htm")
        last = max([1] + [int(c) for c in re.findall(rf'class=chapnum href="{b:02d}(\d{{3}})\.htm"', first)])
        for c in range(1, last + 1):
            yield b, c, first if c == 1 else page(f"{b:02d}{c:03d}.htm")


def parse(text: str) -> dict:
    """{verse: text} from a chapter page (the verse anchors run '<a class=vn ...>&nbsp;N&nbsp;</a>text')."""
    body = text[text.index("class=textarea"):]
    body = body[:body.index("</td>")]
    body = re.sub(r"<p class=note>.*?</p>", "", body, flags=re.S)             # Challoner's notes, after the text
    body = re.sub(r"<p class=k999>.*?</p>", "", body, flags=re.S)             # "Hebrews Psalm 10": the Hebrew numbering
    # Psalm 118's Hebrew letters head their stanzas: "BETH. By what doth a young man correct his way?"
    body = re.sub(r"<p class=k888>([^<]+)</p>\s*<p>\s*(<a class=vn [^>]*>&nbsp;\d+&nbsp;</a>)", r"\2\1. ", body)
    parts = re.split(r'<a class=vn [^>]*>&nbsp;(\d+)&nbsp;</a>', body)
    verses = {}
    for v, raw in zip(parts[1::2], parts[2::2]):
        t = html.unescape(re.sub(r"<[^>]+>", "", raw))
        t = re.sub(r"\s+", " ", t).strip().replace("'", "’")
        if v in verses:
            raise SystemExit(f"duplicate verse {v}")
        verses[v] = t
    return verses


def renumber(bible: dict) -> None:
    """drbo.org numbers Psalm 9's second half (the Hebrew Psalm 10) 101-118, and Psalms 115 and 147 (which the Hebrew
    joins to the psalm before) from 10 and 12; the bot numbers them on, 9:22-39, 115:1-10 and 147:1-9."""
    ps = bible["Psalms"]
    ps["9"] = {str(int(v) - 79 if int(v) > 100 else int(v)): t for v, t in ps["9"].items()}
    for c in ("115", "147"):
        first = min(int(v) for v in ps[c])
        ps[c] = {str(int(v) - first + 1): t for v, t in ps[c].items()}


# Seven chapters whose last verse drbo.org runs into the one before (as the old file did): where it begins
SPLITS = {"Genesis 5": "And Noe, when he was five hundred years old", "2 Kings 13": "And king David ceased to pursue",
          "Psalms 28": "The Lord will give strength to his people", "Psalms 150": "let every spirit praise the Lord",
          "Amos 9": "And I will plant them upon their own land", "John 11": "And the chief priests and Pharisees had",
          "2 Corinthians 1": "not because we exercise dominion"}


def split(bible: dict) -> None:
    for ref, start in SPLITS.items():
        book, c = ref.rsplit(" ", 1)
        verses = bible[book][c]
        last = str(len(verses))
        text = verses[last]
        if text.count(start) != 1:
            raise SystemExit(f"{ref}: {start!r} found {text.count(start)} times in its last verse")
        i = text.index(start)
        verses[last], verses[str(len(verses) + 1)] = text[:i].rstrip(), text[i:]


def correct(bible: dict) -> None:
    for c, title in TITLES.items():
        if bible["Psalms"][c]["1"].startswith(title):
            raise SystemExit(f"Psalm {c} has its title already")
        bible["Psalms"][c]["1"] = f"{title} {bible['Psalms'][c]['1']}"
    for ref, edits in FIXES.items():
        book, cv = ref.rsplit(" ", 1)
        c, v = cv.split(":")
        text = bible[book][c][v]
        for wrong, right in edits:
            if text.count(wrong) != 1:
                raise SystemExit(f"{ref}: {wrong!r} found {text.count(wrong)} times in {text!r}")
            text = text.replace(wrong, right)
        bible[book][c][v] = text


def check(bible: dict) -> list[str]:
    """Every book's chapters and verses run 1..n with no gaps, and no verse is empty."""
    problems = []
    for book, chapters_ in bible.items():
        if sorted(int(c) for c in chapters_) != list(range(1, len(chapters_) + 1)):
            problems.append(f"{book}: chapters {sorted(chapters_, key=int)}")
        for c, verses in chapters_.items():
            if sorted(int(v) for v in verses) != list(range(1, len(verses) + 1)):
                problems.append(f"{book} {c}: verses {sorted(verses, key=int)[:5]}... ({len(verses)})")
            problems += [f"{book} {c}:{v} is empty" for v, t in verses.items() if not t]
    return problems


def main() -> None:
    bible = {name: {} for name in BOOKS}
    for b, c, text in chapters():
        bible[BOOKS[b - 1]][str(c)] = parse(text)
    renumber(bible)
    split(bible)
    correct(bible)
    problems = check(bible)
    if problems:
        print("\n".join(problems))
        sys.exit(1)
    OUT.write_text(json.dumps(bible, ensure_ascii=False, indent=1), encoding="utf-8")
    verses = sum(len(v) for ch in bible.values() for v in ch.values())
    print(f"{len(bible)} books, {verses} verses -> {OUT}")


if __name__ == "__main__":
    main()
