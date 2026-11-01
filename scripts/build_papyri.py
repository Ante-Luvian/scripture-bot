"""
The Demotic Magical Papyrus of London and Leiden (2nd-3rd century AD), in F. Ll. Griffith and Herbert Thompson's
English (1904), from archive.sacred-texts.com/egy/dmp/, into data/esoteric/papyri.json.

A column of the papyrus a chapter (the front's 29 as "The Demotic Magical Papyrus", the back's 33 as "...,
Verso") and a line of it a verse, as the translation numbers them ("(5) Pshoi that is in the abyss..."), so
"!verse demotic papyrus 2:5" is col. II, line 5. Lines the translators gave together ("(1, 2)", "(1-3)") are one
verse under the first number; "(1a)" stays "1a". Kept: the translators' brackets, (?) and (bis). Left out: their introduction and notes, and sacred-texts'
page numbers ("p. 26").

    python scripts/build_papyri.py
"""
import html
import json
import re
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from corpus_clean import clean_corpus  # noqa: E402

CACHE = ROOT / "scripts" / ".cache" / "papyri"
OUT = ROOT / "data" / "esoteric" / "papyri.json"
BASE = "https://archive.sacred-texts.com/egy/dmp/"
UA = {"User-Agent": "ScriptureBotCorpusBuilder/1.0 (Discord bot; low-volume one-off import)"}


def page(n: int) -> str:
    path = CACHE / f"dmp{n:02d}.htm"
    if not path.exists():
        CACHE.mkdir(parents=True, exist_ok=True)
        req = urllib.request.Request(f"{BASE}dmp{n:02d}.htm", headers=UA)
        path.write_bytes(urllib.request.urlopen(req, timeout=60).read())
        time.sleep(1)
    raw = path.read_bytes()
    return raw.decode("utf-8" if b"utf-8" in raw[:2000].lower() else "cp1252", "replace")


def text_of(t: str) -> str:
    t = re.sub(r"(?is)<head.*?</head>|<script.*?</script>", " ", t)
    t = re.sub(r"(?is)<a name=\"page_\d+\">.*?</a>|<font size=\"1\" color=\"green\">.*?</font>", " ", t)
    t = re.sub(r"(?i)<(i|em)>(.*?)</\1>", lambda m: f"*{m.group(2).strip()}*" if m.group(2).strip() else " ", t)
    t = html.unescape(re.sub(r"<[^>]+>", " ", t)).replace("\xa0", " ")
    t = re.sub(r"\bp\. \d+\b|\[paragraph continues\]", " ", t)
    return re.sub(r"\s+", " ", t).strip()


LINE = re.compile(r"\((\d+)([a-z]?)(?:\s*(?:,|-|–)\s*\d+[a-z]?)*\)\s*")


def column(n: int):
    """(column number, {line: text}) of page n."""
    body = text_of(page(n))
    head = re.search(r"(?:VERSO )?COL\.? ([IVXL]+)\.?", body)
    body = body[head.end():]
    body = re.split(r"\s+Next:|\s+Sacred Texts\s+Egyptian\s+Index", body)[0]
    lines, key = {}, None
    parts = LINE.split(body)
    lead = parts[0].strip()
    for i in range(1, len(parts), 3):
        key = parts[i] + parts[i + 1]
        text = parts[i + 2].strip()
        if key in lines:                               # (a number the translation repeats: run on)
            lines[key] += " " + text
        else:
            lines[key] = text
    if lead and lines:                                 # ("(A row of figures...)" before line 1)
        first = next(iter(lines))
        lines[first] = f"{lead} {lines[first]}".strip()
    return roman(head.group(1)), {k: v for k, v in lines.items() if v and not re.fullmatch(r"[.\s…]*", v)}


def roman(s: str) -> int:
    vals = {"I": 1, "V": 5, "X": 10, "L": 50}
    return sum(-vals[c] if i + 1 < len(s) and vals[s[i + 1]] > vals[c] else vals[c] for i, c in enumerate(s))


def main() -> None:
    books = {"The Demotic Magical Papyrus": {}, "The Demotic Magical Papyrus, Verso": {}}
    for n in range(4, 66):
        number, lines = column(n)
        book = "The Demotic Magical Papyrus" if n < 33 else "The Demotic Magical Papyrus, Verso"
        if str(number) in books[book]:
            raise SystemExit(f"{book} col. {number} twice (page {n})")
        books[book][str(number)] = lines
    for book, last in (("The Demotic Magical Papyrus", 29), ("The Demotic Magical Papyrus, Verso", 33)):
        if list(books[book]) != [str(i) for i in range(1, last + 1)]:
            raise SystemExit(f"{book}: {list(books[book])}")
    src = "trans. F. Ll. Griffith and Herbert Thompson (1904)"
    payload = {"source": src, "books": books, "book_sources": {b: src for b in books}}
    clean_corpus(payload, "esoteric/papyri.json")
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    for book, cols in payload["books"].items():
        print(f"  {book}: {len(cols)} columns, {sum(len(c) for c in cols.values())} lines, "
              f"{sum(len(t.split()) for c in cols.values() for t in c.values()):,} words")


if __name__ == "__main__":
    main()
