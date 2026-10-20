"""
Aesop's Fables, in George Fyler Townsend's translation ("Three Hundred Aesop's Fables", 1867), from
Project Gutenberg #21 -> data/classical/aesop.json: one chapter a fable, its paragraphs the verses, the
first led by the fable's title in italics (as the Jataka's are).

Gutenberg, not sacred-texts: sacred-texts' Townsend has lost letters and words at line ends ("bound him
by st ropes", "came gnawed the rope", "to con benefits", in The Lion and the Mouse alone); Gutenberg's
is the volunteer-proofread text of the same translation.

    python scripts/build_aesop.py
"""
import json
import re
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "scripts" / ".cache" / "aesop_pg21.txt"
OUT = ROOT / "data" / "classical" / "aesop.json"
URL = "https://www.gutenberg.org/cache/epub/21/pg21.txt"
BOOK = "Aesop's Fables"


def source_text() -> str:
    if not CACHE.exists():
        CACHE.parent.mkdir(parents=True, exist_ok=True)
        req = urllib.request.Request(URL, headers={"User-Agent": "ScriptureBot corpus builder (personal Discord bot)"})
        CACHE.write_bytes(urllib.request.urlopen(req, timeout=60).read())
    text = CACHE.read_text(encoding="utf-8").replace("\r\n", "\n")
    return text[text.index("*** START"):text.index("*** END")]


def contents(text: str) -> list:
    """The fables' titles as the contents page lists them, in order."""
    block = text[text.index("CONTENTS"):]
    block = block[block.index("AESOP’S FABLES") + len("AESOP’S FABLES"):block.index("FOOTNOTES")]
    return [line.strip() for line in block.split("\n") if line.strip()]


SMALL = {"and", "the", "of", "a", "an", "in", "on", "to", "with", "his", "her", "its", "at", "by", "for", "from",
         "into", "who", "were", "was", "under", "their", "him"}


def titled(title: str) -> str:
    """Gutenberg capitalises some titles' small words ("The Lion And The Mouse"), not others: make them
    all like "The Fox and the Lion"."""
    words = title.split(" ")
    return " ".join([words[0]] + [w.lower() if w.lower() in SMALL else w for w in words[1:]])


def unwrap(paragraph: str) -> str:
    return re.sub(r"\s+", " ", paragraph).strip()


def fables(text: str) -> list:
    """[(title, [paragraph, ...])] in the book's order."""
    start = text.index("AESOP’S FABLES", text.index("LIFE OF AESOP", text.index("CONTENTS") + 400))
    body = text[start + len("AESOP’S FABLES"):text.index("FOOTNOTES", start)]
    blocks = [b for b in re.split(r"\n{3,}", body) if b.strip()]
    out = []
    for block in blocks:
        paras = [unwrap(p) for p in re.split(r"\n\s*\n", block) if p.strip()]
        is_title = len(paras) == 1 and "\n" not in block.strip() and len(paras[0]) < 80 and not paras[0].endswith((".", "”", "?", "!"))
        if is_title:
            out.append((paras[0], []))
        else:
            if not out:
                raise SystemExit(f"text before the first title: {block[:80]!r}")
            out[-1][1].extend(paras)
    return out


def main():
    text = source_text()
    listed = contents(text)
    found = fables(text)
    titles = [t for t, _ in found]
    if [t.lower() for t in titles] != [t.lower() for t in listed]:
        for i, (a, b) in enumerate(zip(titles, listed)):
            if a.lower() != b.lower():
                raise SystemExit(f"fable {i + 1}: text has {a!r}, contents {b!r}")
        raise SystemExit(f"{len(titles)} fables in the text, {len(listed)} in the contents")
    empty = [t for t, paras in found if not paras]
    if empty:
        raise SystemExit(f"no text for: {empty}")
    chapters = {}
    for n, (title, paras) in enumerate(found, 1):
        chapters[str(n)] = {str(i): (f"*{titled(title)}*\n{p}" if i == 1 else p) for i, p in enumerate(paras, 1)}
    payload = {"source": "trans. George Fyler Townsend (1867)", "books": {BOOK: chapters}}
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{len(chapters)} fables -> {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    sys.exit(main())
