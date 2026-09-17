"""
Build script: converts R.H. Charles' translation of The Assumption of Moses
(also known as The Testament of Moses) into
data/charles/assumption_of_moses.json.

Source text: https://www.pseudepigrapha.com/pseudepigrapha/assumptionofmoses.html
Per the page's own footer: "Translation adapted from R. H. Charles, The
Apocrypha and Pseudepigrapha of the Old Testament (Oxford: University Press,
1913) 2: 407-424" -- the same public-domain 1913 Oxford work this project's
book_of_enoch.json, book_of_jubilees.json, and
testaments_of_twelve_patriarchs.json already come from. This particular web
edition was "edited and adapted by George Lyons" for the Wesley Center for
Applied Theology (Northwest Nazarene University), copyright 2000. Its footer
notice permits free use "for personal or scholarly purposes" provided the
notice is left intact; commercial use requires permission. That fits this
project's non-commercial use, and it is the fullest available online text of
Charles' translation (no cleaner verbatim-1913 scan was found).

Chapters are stored as whole text blocks, not split into individual verses --
same rationale as testaments_of_twelve_patriarchs.json: verse numbers appear
as bare digits inline within continuous prose (e.g. "...their fathers. 3 And
yet they have gone..."), with no reliable delimiter that wouldn't also
misfire on ordinary numbers elsewhere in the text.

Downloads its own source -- run from anywhere:
    python deprecated/build_assumption_of_moses.py
"""
import html as html_mod
import json
import re
import urllib.request
from pathlib import Path

SOURCE_URL = "https://www.pseudepigrapha.com/pseudepigrapha/assumptionofmoses.html"
OUT_DIR = Path(__file__).parent.parent / "data" / "charles"
OUT_PATH = OUT_DIR / "assumption_of_moses.json"


def _strip(fragment):
    text = re.sub(r"<[^>]+>", " ", fragment)
    text = html_mod.unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def main():
    req = urllib.request.Request(SOURCE_URL, headers={"User-Agent": "ScriptureBot/1.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        raw = r.read().decode("utf-8", errors="replace")

    start = raw.index("<TABLE")
    end = raw.index("</TABLE>", start) + len("</TABLE>")
    table = raw[start:end]

    row_re = re.compile(r"<TR>\s*<TD.*?>(.*?)</TD>\s*<TD.*?>(.*?)</TD>\s*</TR>", re.DOTALL)
    rows = row_re.findall(table)
    if len(rows) != 12:
        raise SystemExit(f"Expected 12 chapters, found {len(rows)} -- source page structure may have changed.")

    chapters = {}
    for num_html, text_html in rows:
        num_text = _strip(num_html)
        m = re.match(r"^(\d+)", num_text)
        if not m:
            raise SystemExit(f"Could not find chapter number in row: {num_text!r}")
        chapters[m.group(1)] = _strip(text_html)

    payload = {
        "source": (
            "The Assumption of Moses (Testament of Moses), trans. R.H. Charles "
            "(The Apocrypha and Pseudepigrapha of the Old Testament, vol. II, "
            "Oxford, 1913, public domain); web edition adapted by George Lyons, "
            "Wesley Center for Applied Theology, Northwest Nazarene University"
        ),
        "books": {"Assumption of Moses": chapters},
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {OUT_PATH} -- {len(chapters)} chapters")
    for n in sorted(chapters, key=int):
        print(f"  ch.{n}: {len(chapters[n])} chars")


if __name__ == "__main__":
    main()
