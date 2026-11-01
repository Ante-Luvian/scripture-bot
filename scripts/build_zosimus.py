"""
Zosimus's New History (c. AD 500) in the anonymous English of 1814 (London: Green and Chaplin), as Roger Pearse
transcribed it for tertullian.org; fetched from its mirror on earlychristianwritings.com (tertullian.org itself
answers 404). Into data/classical/zosimus.json as "New History": a chapter for each of the six books and a verse
for each of the translator's paragraphs, so "New History 1:1" is the opening. (The 1814 printing has no chapter
numbers; the modern ones, as in "New History 1.46", don't fall on its paragraphs.)

Kept: the 1814 editor's passages filling the lost parts ("The remainder of this book... is lost"). Left out:
Pearse's notes to the online edition, the translator's footnotes, page numbers. Where the manuscript breaks off
(a row of asterisks) the verse says "[…]". The odd Greek word, typed for the SPIonic font ("aiw_n"), is Greek.

    python scripts/build_zosimus.py
"""
import html
import json
import re
import sys
import time
import unicodedata
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from corpus_clean import clean_corpus  # noqa: E402

CACHE = ROOT / "scripts" / ".cache" / "zosimus"
OUT = ROOT / "data" / "classical" / "zosimus.json"
BASE = "https://earlychristianwritings.com/fathers/zosimus0{n}_book{n}.html"
UA = {"User-Agent": "ScriptureBotCorpusBuilder/1.0 (Discord bot; low-volume one-off import)"}

GREEK = dict(zip("abgdezhqiklmncoprstufxyw", "αβγδεζηθικλμνξοπρστυφχψω"))
MARKS = {"/": "́", "_": "́", "\\": "̀", "=": "͂", "(": "̔", ")": "̓", "|": "ͅ"}


def page(n: int) -> str:
    path = CACHE / f"book{n}.html"
    if not path.exists():
        CACHE.mkdir(parents=True, exist_ok=True)
        req = urllib.request.Request(BASE.format(n=n), headers=UA)
        path.write_bytes(urllib.request.urlopen(req, timeout=120).read())
        time.sleep(1)
    return path.read_bytes().decode("cp1252", "replace")


def spionic(m) -> str:
    """Greek typed for the SPIonic font ("aiw_n", "Qessali/an") as Greek: αἰών, Θεσσαλίαν."""
    out = []
    for ch in m.group(1):
        if ch.lower() in GREEK:
            g = GREEK[ch.lower()]
            out.append(g.upper() if ch.isupper() else g)
        elif ch == "j":
            out.append("ς")
        elif ch in MARKS:
            out.append(MARKS[ch])
        else:
            out.append(ch)
    word = re.sub(r"σ(?=$|[^\ẁ-ͯ])", "ς", "".join(out))
    return unicodedata.normalize("NFC", word)


def paragraphs(t: str) -> list:
    t = t[re.search(r"(?i)BOOK THE FIRST|[A-Z]+ BOOK\.", t).start():]
    t = t[:t.find("<pre")] if "<pre" in t else t
    t = re.sub(r"(?is)<p[^>]*class=\"?editorial\"?[^>]*>.*?(?=<p\b|<hr|$)", " ", t)       # (Pearse's notes)
    t = re.sub(r"(?is)<font color=\"?#FF0000\"?>.*?</font>", " ", t)                       # (his, in red)
    t = re.sub(r"(?is)<p>\s*<a name=\"?#?\d+\"?>.*?(?=<p\b|<hr|$)", " ", t)                 # (the footnotes)
    t = re.sub(r"(?is)<a href=\"?#\d+\"?>.*?</a>", "", t)                                    # (their markers)
    t = re.sub(r"(?is)<a name=\"?p\d+\"?>\s*<span class=\"?pb\"?>.*?</span>\s*</a>", "", t)   # (page numbers)
    t = re.sub(r"(?is)<span class=\"?pb\"?>.*?</span>", "", t)
    t = re.sub(r"(?is)<(i|em)>\s*(\w)</\1>(?=\w)", r" \2", t)                                   # ("<I>s</I>ailed")
    t = re.sub(r"(?is)<font face=\"?SPIonic\"?>(.*?)</font>", spionic, t)
    t = re.sub(r"(?is)<(i|em)>(\s*)(.*?)(\s*)</\1>", lambda m: f"{m.group(2)}*{m.group(3)}*{m.group(4)}"
               if m.group(3).strip() else " ", t)
    out = []
    for p in re.split(r"(?i)<p\b[^>]*>|<hr[^>]*>", t):
        s = html.unescape(re.sub(r"<[^>]+>", " ", p)).replace("\xa0", " ")
        s = re.sub(r"(?:\*\s*){3,}", " […] ", s)                                           # (a lacuna)
        s = re.sub(r"[=-]{5,}", " ", s)
        s = re.sub(r"\s+", " ", s).strip()
        s = re.sub(r"\s+([,.;:])", r"\1", s)
        if s.count("*") % 2:
            s = s.replace("*", "")
        if not s or re.fullmatch(r"[\[\]…\s.]+", s):
            continue
        if re.fullmatch(r"\*?(BOOK THE FIRST|[A-Z]+ BOOK)\.?\*?", s):                       # (the book's title)
            continue
        out.append(s)
    return out


def main() -> None:
    books = {str(n): {str(i + 1): p for i, p in enumerate(paragraphs(page(n)))} for n in range(1, 7)}
    payload = {"source": "anonymous translation (London: Green and Chaplin, 1814)",
               "books": {"New History": books},
               "book_sources": {"New History": "Zosimus, trans. anon. (1814)"}}
    clean_corpus(payload, "classical/zosimus.json")
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    for n, ps in payload["books"]["New History"].items():
        print(f"  book {n}: {len(ps)} paragraphs, {sum(len(p.split()) for p in ps.values()):,} words")


if __name__ == "__main__":
    main()
