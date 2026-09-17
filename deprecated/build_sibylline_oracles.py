"""
Build script: converts Milton S. Terry's 1899 English blank-verse
translation of The Sibylline Oracles into data/charles/sibylline_oracles.json.

R.H. Charles' own 1913 Apocrypha and Pseudepigrapha only includes an
excerpted/summarized rendering of the Jewish portions (books 3-5, by H.C.O.
Lanchester). Terry's complete translation (1899, public domain -- Terry died
in 1914, and the work has long been in the US public domain) is the fuller
and more commonly cited English text, covering all 12 surviving books (9 and
10 are lost/omitted in Terry's edition, consistent with standard editions).

Source: Wikisource's transcription of Terry's translation --
https://en.wikisource.org/wiki/The_Sibylline_Oracles_(Terry,_2nd_edition)
(one page per book, e.g. .../Book_1 .. Book_8, Book_11 .. Book_14). The
underlying 1899 translation is public domain; this script only extracts the
plain verse-line text (no Wikisource markup/formatting is reproduced).

Each book is stored as a flat mapping of sequential line number -> line
text (the standard Sibylline Oracles citation form is book:line, e.g.
"Sib. Or. 3.63"), not further subdivided into chapters.

Downloads its own source -- run from anywhere:
    python deprecated/build_sibylline_oracles.py
"""
import html as html_mod
import json
import re
import time
import urllib.request
from pathlib import Path

BOOK_NUMBERS = [1, 2, 3, 4, 5, 6, 7, 8, 11, 12, 13, 14]
URL_TEMPLATE = "https://en.wikisource.org/wiki/The_Sibylline_Oracles_(Terry,_2nd_edition)/Book_{n}"
OUT_DIR = Path(__file__).parent.parent / "data" / "charles"
OUT_PATH = OUT_DIR / "sibylline_oracles.json"

LINE_RE = re.compile(r'<span class="ws-poem-line">(.*?)<span class="ws-poem-break">', re.DOTALL)
FOOTNOTE_RE = re.compile(r'<sup[^>]*class="reference"[^>]*>.*?</sup>', re.DOTALL)


def _fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "ScriptureBot/1.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", errors="replace")


def _extract_lines(raw):
    start = raw.find('<div class="ws-poem')
    if start == -1:
        raise SystemExit("Could not find poem content -- source page structure may have changed.")
    end = raw.find("wst-smallrefs", start)
    if end == -1:
        end = len(raw)
    content = raw[start:end]
    content = FOOTNOTE_RE.sub("", content)

    lines = []
    for m in LINE_RE.finditer(content):
        text = re.sub(r"<[^>]+>", "", m.group(1))
        text = html_mod.unescape(text)
        text = re.sub(r"\s+", " ", text).strip()
        if text:
            lines.append(text)
    return lines


def main():
    chapters = {}
    for n in BOOK_NUMBERS:
        url = URL_TEMPLATE.format(n=n)
        raw = _fetch(url)
        lines = _extract_lines(raw)
        if not lines:
            raise SystemExit(f"Book {n}: extracted zero lines -- aborting.")
        chapters[str(n)] = {str(i + 1): line for i, line in enumerate(lines)}
        print(f"Book {n}: {len(lines)} lines")
        time.sleep(1)

    payload = {
        "source": (
            "The Sibylline Oracles, trans. Milton S. Terry, 2nd ed. "
            "(New York: Eaton & Mains, 1899, public domain); text via "
            "Wikisource. Books 9 and 10 are not extant in Terry's edition."
        ),
        "books": {"Sibylline Oracles": chapters},
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    total = sum(len(v) for v in chapters.values())
    print(f"\nWrote {OUT_PATH} -- {len(chapters)} books, {total} lines")


if __name__ == "__main__":
    main()
