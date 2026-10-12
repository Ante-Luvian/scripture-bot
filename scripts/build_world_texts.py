"""
Builds the corpus files for texts added from Project Gutenberg (and similar
plain-text sources) into the standard schema:
    {"source": ..., "books": {book: {chapter: {verse: text}}}}

    python scripts/build_world_texts.py              # build everything
    python scripts/build_world_texts.py dhammapada   # just one

Downloads are cached in scripts/.cache/ (gitignored). Each builder checks the
counts it expects, so a changed upstream file fails loudly instead of
producing a quietly broken corpus.
"""
import json
import re
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CACHE = Path(__file__).resolve().parent / ".cache"
DATA = ROOT / "data"


# ── helpers ─────────────────────────────────────────────────────────────────

def gutenberg(book_id: int) -> str:
    """The text of a Gutenberg ebook, without its licence header/footer."""
    CACHE.mkdir(exist_ok=True)
    path = CACHE / f"pg{book_id}.txt"
    if not path.exists():
        url = f"https://www.gutenberg.org/cache/epub/{book_id}/pg{book_id}.txt"
        path.write_bytes(urllib.request.urlopen(url, timeout=60).read())
    text = path.read_text(encoding="utf-8-sig").replace("\r\n", "\n")
    start = re.search(r"\*\*\* ?START OF (THE|THIS) PROJECT GUTENBERG.*?\*\*\*", text)
    end = re.search(r"\*\*\* ?END OF (THE|THIS) PROJECT GUTENBERG", text)
    return text[start.end() if start else 0:end.start() if end else len(text)]


def paragraphs(block: str) -> list:
    """Blank-line separated paragraphs, each joined onto one line."""
    out = []
    for p in re.split(r"\n\s*\n", block):
        p = " ".join(line.strip() for line in p.strip().splitlines())
        if p:
            out.append(p)
    return out


def tidy(text: str) -> str:
    text = text.replace("_", "")                    # Gutenberg's _italics_
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def write(corpus: str, filename: str, source: str, books: dict) -> None:
    path = DATA / corpus / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"source": source, "books": books}, ensure_ascii=False, indent=1), encoding="utf-8")
    n = sum(len(v) for b in books.values() for v in b.values())
    print(f"wrote {path.relative_to(ROOT)}: {', '.join(books)} ({n} passages)")


def expect(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"unexpected source layout: {message}")


# ── Buddhist ────────────────────────────────────────────────────────────────

def dhammapada():
    """Müller (SBE 10, 1881). 26 chapters; verses 1-423 numbered straight
    through, as the Dhammapada is cited ("Dhammapada 5")."""
    text = gutenberg(2017)
    body = text[text.index("Chapter I. The Twin-Verses"):]
    chapters = re.split(r"^Chapter [IVXL]+\.[^\n]*\n", body, flags=re.M)[1:]
    expect(len(chapters) == 26, f"{len(chapters)} chapters")
    book, numbers = {}, []
    for n, chunk in enumerate(chapters, 1):
        verses = {}
        for p in paragraphs(chunk):
            # Müller renders 9 pairs of verses as one ("58, 59. As on a heap..."):
            # kept under the first number, labelled with both
            m = re.match(r"^(\d+)(?:, (\d+))?\.\s+(.*)$", p)
            if m:
                first, second, text = m.groups()
                verses[first] = (f"(vv. {first}–{second}) " if second else "") + tidy(text)
                numbers += [int(first)] + ([int(second)] if second else [])
            elif verses:                            # a verse continued after a blank line
                last = list(verses)[-1]
                verses[last] += " " + tidy(p)
        book[str(n)] = verses
    expect(numbers == list(range(1, 424)), f"verses run {numbers[:3]}...{numbers[-3:]} ({len(numbers)})")
    write("buddhist", "dhammapada.json", "The Dhammapada, trans. F. Max Müller (Sacred Books of the East 10, 1881)",
          {"Dhammapada": book})


def diamond_sutra():
    """Gemmell (1912), from Kumarajiva's Chinese. 32 chapters; the
    translator's footnotes (indented "[n] ..." blocks) and their in-text
    markers are left out."""
    text = gutenberg(64623)
    body = text[text.index("[Chapter 1]"):]
    body = body[:body.index("\n\n\n\n\n", body.index("[Chapter 32]"))] if "[Chapter 32]" in body else body
    parts = re.split(r"^\[Chapter (\d+)(?: and \d+)?\]\s*$", body, flags=re.M)[1:]
    book = {}
    for num, chunk in zip(parts[0::2], parts[1::2]):
        paras = [p for p in re.split(r"\n\s*\n", chunk) if p.strip() and not p.startswith("  ")]
        verses = {}
        for p in paras:
            p = re.sub(r"\[\d+\]", "", p)
            p = tidy(" ".join(l.strip() for l in p.splitlines()))
            if p:
                verses[str(len(verses) + 1)] = p
        book[num] = verses
    # Gemmell translates chapters 3 and 4 as one passage ("[Chapter 3 and 4]")
    book["4"] = {"1": "(Chapters 3 and 4 are translated together: see Diamond Sutra 3.)"}
    book = dict(sorted(book.items(), key=lambda kv: int(kv[0])))
    expect(list(book) == [str(i) for i in range(1, 33)], f"chapters {list(book)[:3]}...{list(book)[-3:]}")
    write("buddhist", "diamond_sutra.json", "The Diamond Sutra, trans. William Gemmell (1912), from the Chinese of Kumarajiva",
          {"Diamond Sutra": book})


BUILDERS = {f.__name__: f for f in (dhammapada, diamond_sutra)}

if __name__ == "__main__":
    for name in sys.argv[1:] or BUILDERS:
        BUILDERS[name]()
