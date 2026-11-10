"""
The three books of Meqabyan (the "Ethiopian Maccabees" of the Ethiopian Orthodox Old Testament, unrelated to the
Greek Maccabees), into data/charles/meqabyan.json (2026-11-09), from the owner's copy:

    ~/Downloads/1st, 2nd, 3rd Book of Meqabyan.pdf  (an unattributed English translation in common circulation,
    made from a Google Doc; it keeps a few Rastafari words: YAH for God, "Irie", "overstand")

Each book there opens with a summary of its chapters, then the text, a chapter opening with "Chapter N: <summary>"
(the first has none) and its verses numbered "1;". The summaries are the editor's and are left out; the verses go
by their numbers. pypdf gives the text a word a line; the lines are joined.

    python scripts/build_meqabyan.py
"""
import json
import re
from pathlib import Path

import pypdf

ROOT = Path(__file__).resolve().parent.parent
PDF = Path.home() / "Downloads" / "1st, 2nd, 3rd Book of Meqabyan.pdf"
OUT = ROOT / "data" / "charles" / "meqabyan.json"
ENDS = ("first book that speaks the words of Meqabyan is filled and fulfilled",
        "second book of Meqabyan arrived and was fulfilled",
        "third book that speaks the words of Meqabyan are fulfilled")
CHAPTERS = (36, 21, 10)


def expect(ok: bool, message: str) -> None:
    if not ok:
        raise SystemExit(f"unexpected source layout: {message}")


def text_of_pdf() -> str:
    pages = []
    for page in pypdf.PdfReader(str(PDF)).pages:
        t = re.sub(r"[ \t]*\n[ \t]*", " ", page.extract_text() or "")
        pages.append(re.sub(r" {2,}", " ", t).strip())
    return " ".join(pages)


def book(text: str, chapters: int) -> dict:
    """One book: from its first verse ("1; There was a man") to its closing words, cut at each "Chapter N:" heading
    (the heading's summary runs to the chapter's first verse)."""
    first = re.search(rf"Chapter {chapters}:.*?(?=\s1;\s)", text)          # (the summary's last entry)
    expect(first is not None, f"no summary of chapter {chapters}")
    body = text[first.end():]
    parts = re.split(r"\bChapter (\d+):.*?(?=\s1;\s)", body)
    out = {"1": parts[0]}
    out.update({n: chunk for n, chunk in zip(parts[1::2], parts[2::2])})
    result = {}
    for ch, chunk in out.items():
        verses, current = {}, 0
        for piece in re.split(r"(?:^|(?<=\s))(\d{1,2});\s*", chunk.strip()):
            if piece.isdigit() and int(piece) == current + 1:
                current += 1
                verses[str(current)] = ""
            elif current:
                verses[str(current)] += piece
        result[ch] = {k: re.sub(r"\s+", " ", v).strip() for k, v in verses.items() if v.strip()}
    expect(list(result) == [str(n) for n in range(1, chapters + 1)], f"chapters {list(result)}")
    return result


def main() -> None:
    text = text_of_pdf()
    books, start = {}, 0
    for n, (end, chapters) in enumerate(zip(ENDS, CHAPTERS), 1):
        stop = text.find(end, start)
        expect(stop > 0, f"book {n}: no ending {end!r}")
        stop = text.find(".", stop) + 1
        books[f"{n} Meqabyan"] = book(text[start:stop], chapters)
        start = stop
    for name, chapters in books.items():
        print(f"  {name}: {len(chapters)} chapters, {sum(map(len, chapters.values()))} verses")
    source = "unattributed English translation (in common circulation)"
    OUT.write_text(json.dumps({"source": source, "book_sources": {b: source for b in books}, "books": books},
                              ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
