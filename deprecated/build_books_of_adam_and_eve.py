"""
Build script: converts R.H. Charles' 1913 translations of the two Books of
Adam and Eve -- the Latin "Vita Adae et Evae" and the Greek "Apocalypse of
Moses" -- into data/charles/books_of_adam_and_eve.json.

Source: wesley.nnu.edu's transcriptions (still live under their original
Wesley Center for Applied Theology URLs, unlike the newer pseudepigrapha.com
mirror used for the Assumption of Moses):
  https://wesley.nnu.edu/.../the-books-of-adam-and-eve/       (Vita Adae et Evae)
  https://wesley.nnu.edu/.../the-apocalypse-of-moses/         (Apocalypse of Moses)
Both pages header themselves: 'From "The Apocrypha and Pseudepigrapha of the
Old Testament" R.H. Charles, Oxford: Clarendon Press, 1913' -- the same
public-domain work this project's other Charles texts come from.

Each work's chapters (roman numerals i.. in the source, e.g. "xxi 1 And
behold...") are marked inline in the HTML, sometimes mid-paragraph rather
than at a <p> boundary, and in the Apocalypse of Moses two chapters'
fragments appear out of physical order in the page (chapter 37's back half
is transposed after chapter 39's opening). To handle this correctly and
safely:

  - All paragraph text is joined into one continuous stream per work, and
    chapter markers (a run of roman-numeral letters immediately followed by
    a verse number) are located anywhere in that stream, not just at
    paragraph starts -- this is what catches the Apocalypse of Moses'
    mid-paragraph "xxvii" marker that a paragraph-start-only scan would miss.
  - Text is grouped by parsed chapter number (not by scan position), so a
    chapter whose fragments appear out of order (Apocalypse of Moses ch. 37)
    is correctly reassembled in the right reading order regardless of where
    each fragment physically sits in the page.
  - A roman-numeral candidate is only accepted if it parses to a number
    within a plausible chapter range for that work AND is immediately
    followed by a verse number -- this was checked by hand against the full
    list of accepted matches for both works (printed during development) and
    produced zero false positives.
  - Verse numbers themselves are not used to split chapters into verses
    (same rationale as testaments_of_twelve_patriarchs.json and
    assumption_of_moses.json: they're bare inline digits, not a reliable
    delimiter), so each chapter is stored as one whole text block.

Known transcription gaps (verified by direct inspection of the source HTML,
not inferred): Vita Adae et Evae chapters 32 and 37 have no marker anywhere
in the page at all (not even mid-paragraph) -- their content is silently
appended to the end of chapters 31 and 36 respectively in this source, and
this script does not attempt to guess where a boundary should fall. This
means "Vita Adae et Evae" has 49 addressable chapters (1-51 except 32, 37),
while "Apocalypse of Moses" has the full 43.

Downloads its own source -- run from anywhere:
    python deprecated/build_books_of_adam_and_eve.py
"""
import html as html_mod
import json
import re
import urllib.request
from collections import defaultdict
from pathlib import Path

VITA_URL = "https://wesley.nnu.edu/sermons-essays-books/noncanonical-literature/noncanonical-literature-ot-pseudepigrapha/the-books-of-adam-and-eve/"
APOC_URL = "https://wesley.nnu.edu/sermons-essays-books/noncanonical-literature/noncanonical-literature-ot-pseudepigrapha/the-apocalypse-of-moses/"
OUT_DIR = Path(__file__).parent.parent / "data" / "charles"
OUT_PATH = OUT_DIR / "books_of_adam_and_eve.json"

ROMAN_VALUES = {"i": 1, "v": 5, "x": 10, "l": 50, "c": 100, "d": 500, "m": 1000}
MARKER_RE = re.compile(r"(?<![A-Za-z])([ivxlcdm]+)\s(\d+(?:,\s*\d+)*|I)(?![A-Za-z0-9])")
PARA_RE = re.compile(r"<p>(.*?)</p>", re.DOTALL)


def _roman_to_int(s):
    s = s.lower()
    if not s or any(ch not in ROMAN_VALUES for ch in s):
        return None
    total, prev = 0, 0
    for ch in reversed(s):
        v = ROMAN_VALUES[ch]
        if v < prev:
            total -= v
        else:
            total += v
            prev = v
    return total


def _fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "ScriptureBot/1.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", errors="replace")


def _extract_chapters(raw, start_marker, end_marker, max_chapter):
    start = raw.index(start_marker)
    end = raw.index(end_marker, start)
    content = raw[start:end]

    texts = []
    for m in PARA_RE.finditer(content):
        text = re.sub(r"<[^>]+>", "", m.group(1))
        text = html_mod.unescape(text)
        text = re.sub(r"\s+", " ", text).strip()
        if text:
            texts.append(text)
    joined = " ".join(texts)

    matches = []
    for m in MARKER_RE.finditer(joined):
        num = _roman_to_int(m.group(1))
        if num is not None and 0 < num <= max_chapter:
            matches.append((m.start(), m.end(), num))
    if not matches:
        raise SystemExit("No chapter markers found -- source page structure may have changed.")

    chapters = defaultdict(list)
    for i, (_, seg_start, num) in enumerate(matches):
        seg_end = matches[i + 1][0] if i + 1 < len(matches) else len(joined)
        chapters[num].append(joined[seg_start:seg_end].strip())

    return {str(k): re.sub(r"\s+", " ", " ".join(v)).strip() for k, v in chapters.items()}


def main():
    vita_raw = _fetch(VITA_URL)
    vita = _extract_chapters(vita_raw, "<p>i 1 When they were driven", "Scanned and Edited by", 51)
    expected_vita_gaps = {"32", "37"}
    missing_vita = ({str(i) for i in range(1, 52)} - expected_vita_gaps) - set(vita)
    if missing_vita:
        raise SystemExit(f"Vita Adae et Evae: unexpected missing chapters {sorted(missing_vita, key=int)}")

    apoc_raw = _fetch(APOC_URL)
    apoc = _extract_chapters(apoc_raw, "<p>i 1 This is the story of Adam", "Scanned and Edited by", 43)
    missing_apoc = {str(i) for i in range(1, 44)} - set(apoc)
    if missing_apoc:
        raise SystemExit(f"Apocalypse of Moses: unexpected missing chapters {sorted(missing_apoc, key=int)}")

    payload = {
        "source": (
            "Vita Adae et Evae and Apocalypse of Moses (the Latin and Greek "
            "Books of Adam and Eve), trans. R.H. Charles (The Apocrypha and "
            "Pseudepigrapha of the Old Testament, vol. II, Oxford, 1913, "
            "public domain). Vita Adae et Evae ch. 32 and 37 have no "
            "chapter marker in the source transcription and are merged "
            "into the ends of ch. 31 and 36 respectively -- a transcription "
            "gap, not a translation gap."
        ),
        "books": {
            "Vita Adae et Evae": vita,
            "Apocalypse of Moses": apoc,
        },
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {OUT_PATH}")
    print(f"  Vita Adae et Evae: {len(vita)} chapters")
    print(f"  Apocalypse of Moses: {len(apoc)} chapters")


if __name__ == "__main__":
    main()
