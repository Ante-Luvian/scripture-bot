"""
Sepharial (Walter Gorn Old), "Astrology: How to Make and Read Your Own Horoscope" (1920), from Project
Gutenberg #46963 -> data/medieval/sepharial_astrology.json: "Sepharial's Astrology", by section.chapter
(4.2 = Section IV, Chapter II, "The Effects of Transits"), one paragraph a verse, each chapter led by its
title in italics. !horoscope quotes his transits (Mars over Venus "will engender passionate love").

Italics (_x_) become *x*; the one [Illustration] goes; tables keep their lines.

    python scripts/build_sepharial.py
"""
import json
import re
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "scripts" / ".cache" / "sepharial_pg46963.txt"
OUT = ROOT / "data" / "medieval" / "sepharial_astrology.json"
URL = "https://www.gutenberg.org/cache/epub/46963/pg46963.txt"
BOOK = "Sepharial's Astrology"
ROMAN = {"I": 1, "II": 2, "III": 3, "IV": 4, "V": 5, "VI": 6, "VII": 7, "VIII": 8, "IX": 9, "X": 10, "XI": 11,
         "XII": 12}
CHAPTERS = {1: 4, 2: 5, 3: 12, 4: 7}


def source() -> str:
    if not CACHE.exists():
        CACHE.parent.mkdir(parents=True, exist_ok=True)
        req = urllib.request.Request(URL, headers={"User-Agent": "ScriptureBot corpus builder (personal Discord bot)"})
        CACHE.write_bytes(urllib.request.urlopen(req, timeout=60).read())
    text = CACHE.read_text(encoding="utf-8").replace("\r\n", "\n")
    return text[text.index("*** START"):text.index("*** END")]


def tabular(block: str) -> bool:
    lines = [l for l in block.split("\n") if l.strip()]
    return len(lines) > 1 and sum(bool(re.search(r"\S {3,}\S", l)) for l in lines) >= len(lines) / 2


def paragraph(block: str) -> str:
    block = re.sub(r"_([^_\n]+(?:\n[^_\n]+)*)_", lambda m: "*" + re.sub(r"\s+", " ", m.group(1)) + "*", block)
    if re.fullmatch(r"[\s*]+", block):
        return ""                                          # a "* * * * *" break between parts
    if tabular(block):
        import textwrap
        return "\n".join(l.rstrip() for l in textwrap.dedent(block.strip("\n")).split("\n"))
    return re.sub(r"\s+", " ", block).strip()


def main():
    text = source()
    body = text[[m.start() for m in re.finditer(r"(?m)^SECTION I\s*$", text)][1]:]      # (past the contents)
    body = re.split(r"(?m)^\s*(?:FOOTNOTES?|INDEX)\s*$", body)[0]
    chapters, section = {}, 0
    parts = re.split(r"(?m)^(SECTION [IVX]+|CHAPTER [IVX]+)\s*$", body)
    for i in range(1, len(parts), 2):
        mark, content = parts[i], parts[i + 1]
        if mark.startswith("SECTION"):
            section = ROMAN[mark.split()[1]]
            continue
        blocks = [b for b in re.split(r"\n\s*\n", content) if b.strip() and b.strip() != "[Illustration]"]
        title = re.sub(r"\s+", " ", blocks[0]).strip()
        paras = [paragraph(b) for b in blocks[1:]]
        paras = [p for p in paras if p]
        small = {"and", "of", "the", "in", "a", "an", "to", "its", "how"}
        words = title.lower().split()
        heading = "*" + " ".join(w if i and w.rstrip(",.") in small else w.capitalize() for i, w in enumerate(words)) + "*"
        verses = [f"{heading}\n{paras[0]}"] + paras[1:]
        chapters[f"{section}.{ROMAN[mark.split()[1]]}"] = {str(n): v for n, v in enumerate(verses, 1)}
    for s, count in CHAPTERS.items():
        got = sorted(int(k.split(".")[1]) for k in chapters if k.startswith(f"{s}."))
        if got != list(range(1, count + 1)):
            raise SystemExit(f"Section {s}: chapters {got}, expected 1-{count}")
    payload = {"source": "Sepharial (1920)", "books": {BOOK: chapters}}
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{len(chapters)} chapters -> {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    sys.exit(main())
