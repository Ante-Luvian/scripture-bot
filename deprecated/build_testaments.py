"""
Build script: converts R.H. Charles' translation of The Testaments of the
Twelve Patriarchs (from The Apocrypha and Pseudepigrapha of the Old Testament,
vol. II, Oxford, 1913 -- the same public-domain work this project's
book_of_enoch.json and book_of_jubilees.json already come from) into
data/charles/testaments_of_twelve_patriarchs.json.

Source text: https://earlychristianwritings.com/text/patriarchs-charles.html
(explicitly headed "From The Apocrypha and Pseudepigrapha of the Old
Testament by R. H. Charles, vol. II, Oxford Press" on the page itself).

Each chapter is stored as a single text block (not split into individual
verses) -- the source marks chapter numbers clearly in the markup, but verse
numbers are just bare digits inline within continuous prose (e.g. "...he
gave his sons before he 2 died in the..."), with no reliable delimiter to
split on that wouldn't also misfire on ordinary numbers in the text ("thirty
years old", "seven months"). scripture_lookup.py already normalizes a bare-
string chapter value into {"1": text} at load time (added for a similar
ancient_near_east case), so this loads and looks up cleanly as-is.

Downloads its own source -- run from anywhere:
    python deprecated/build_testaments.py
"""
import html as html_mod
import json
import re
import urllib.request
from pathlib import Path

SOURCE_URL = "https://earlychristianwritings.com/text/patriarchs-charles.html"
OUT_DIR = Path(__file__).parent.parent / "data" / "charles"
OUT_PATH = OUT_DIR / "testaments_of_twelve_patriarchs.json"


def main():
    req = urllib.request.Request(SOURCE_URL, headers={"User-Agent": "ScriptureBot/1.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        raw = r.read().decode("utf-8", errors="replace")

    start = raw.index("THE TESTAMENT OF REUBEN")
    end = raw.index('<hr width="50%">', start)
    content = raw[start:end]

    header_re = re.compile(r"THE TESTAMENT OF ([A-Z][^\n<]*)")
    headers = list(header_re.finditer(content))
    if len(headers) != 12:
        raise SystemExit(f"Expected 12 testaments, found {len(headers)} -- source page structure may have changed.")

    chapter_re = re.compile(r"<P><B>(\d+)</B>\s*(.*?)(?=<P><B>\d+</B>|$)", re.DOTALL)
    books = {}
    for i, m in enumerate(headers):
        name_raw = m.group(1).strip().rstrip(".")
        name_match = re.match(r"^([A-Z']+)", name_raw)
        patriarch = name_match.group(1).title() if name_match else name_raw.title()
        book_name = f"Testament of {patriarch}"

        seg_start = m.end()
        seg_end = headers[i + 1].start() if i + 1 < len(headers) else len(content)
        segment = content[seg_start:seg_end]

        chapters = {}
        for cm in chapter_re.finditer(segment):
            text = re.sub(r"<[^>]+>", " ", cm.group(2))
            text = html_mod.unescape(text)
            text = re.sub(r"\s+", " ", text).strip()
            if text:
                chapters[cm.group(1)] = text
        books[book_name] = chapters

    payload = {
        "source": "The Testaments of the Twelve Patriarchs, trans. R.H. Charles (1913, public domain)",
        "books": books,
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    total_chapters = sum(len(v) for v in books.values())
    print(f"Wrote {OUT_PATH} — {len(books)} testaments, {total_chapters} chapters")
    for name, chaps in books.items():
        print(f"  {name}: {len(chaps)} chapters")


if __name__ == "__main__":
    main()
