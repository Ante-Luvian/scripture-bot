"""
3 Enoch, the Hebrew Book of Enoch (Sefer Hekhalot): Rabbi Ishmael's ascent and Metatron's revelations, in Source
Library's English (2026): a machine translation (AI) of Vatican MS Ebr. 228, the manuscript on which Hugo Odeberg
based his 1928 edition, not reviewed by any person. The owner chose it (2026-11-07): Odeberg's own English is
online only as scans and error-filled OCR. Into data/charles/3_enoch.json.

The book is scans 94-135 of the manuscript (its folios 45b-66). The manuscript does not number chapters, but each
of Odeberg's 48 opens "Rabbi Ishmael said", and the translation has exactly 48 of them, in his order (3: "What is
your name?", 4: why Metatron bears his Creator's name, 25: the prince of the Ophanim, 42-44: the waters, the souls
of the righteous and of the wicked, 48: the Right Hand): so the chapters are Odeberg's, and his 48A-D are chapter
48. Its paragraphs are the verses; Genesis 5:24, the book's motto, leads chapter 1.

Left out: the transcription's page numbers, running heads, signature marks, marginal notes and the translator's
notes; the zero-width characters Source Library puts in its text (a watermark). Kept: words it marks unclear (as
they are), and its glosses in brackets.

    python scripts/build_3enoch.py
"""
import json
import re
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from corpus_clean import clean_corpus  # noqa: E402

CACHE = ROOT / "scripts" / ".cache" / "sourcelibrary" / "vat_ebr_228.json"
URL = "https://sourcelibrary.org/api/books/69906606ef12272ffdc94dd0/text?content=both&format=json"
OUT = ROOT / "data" / "charles" / "3_enoch.json"
FIRST, LAST = 94, 135                                   # (the scans holding 3 Enoch)
SOURCE = "machine translation (AI) of Vatican MS Ebr. 228, Source Library (2026)"

ZERO_WIDTH = re.compile("[​-‏⁠-⁤﻿]")
DROP = re.compile(r"(?is)<(page-num|header|sig|margin|note)>.*?</\1>|</?margin>")
KEEP = re.compile(r"(?is)</?(unclear|gloss)>")


def pages() -> list:
    if not CACHE.exists():
        CACHE.parent.mkdir(parents=True, exist_ok=True)
        req = urllib.request.Request(URL, headers={"User-Agent": "ScriptureBotCorpusBuilder/1.0 (personal, non-commercial)"})
        CACHE.write_bytes(urllib.request.urlopen(req, timeout=180).read())
    data = json.loads(CACHE.read_text(encoding="utf-8"))
    return [p for p in data["pages"] if FIRST <= int(p["page_number"]) <= LAST]


def clean(t: str) -> str:
    t = ZERO_WIDTH.sub("", t)
    t = DROP.sub("", t)
    t = KEEP.sub("", t)
    t = t.replace("[At 그]", "At that").replace("그", "that")        # (a Korean "that" left in the English)
    t = re.sub(r"\[\s*\]|\[\.\.\.\]\s*", " ", t)
    return t


def gaps(t: str) -> str:
    """The translation's "..." (a gap or doubtful words, inside a page) as one mark."""
    return re.sub(r"\s*\.\.\.\s*", " … ", t).replace("  ", " ")


def text() -> str:
    """The pages run together: a page's "..." where a sentence crosses a page break, dropped."""
    out = ""
    for p in pages():
        t = clean(p.get("translation") or "").strip()
        if not t or t.startswith("[Blank page"):
            continue
        t = re.sub(r"^(?:\.\.\.|…)\s*", "", t)
        out = re.sub(r"\s*(?:\.\.\.|…)\s*$", "", out)
        joiner = " " if out and not out.endswith(("\n", ".", "!", "?", ":", "\"", "”")) else "\n\n"
        out = f"{out}{joiner}{t}" if out else t
    return out


def chapters(t: str) -> dict:
    starts = [m.start() for m in re.finditer(r"Rabbi Ishmael said", t)]
    if len(starts) != 48:
        raise SystemExit(f"unexpected: {len(starts)} chapters, not Odeberg's 48")
    motto = t[:starts[0]].strip()
    out = {}
    for n, (a, b) in enumerate(zip(starts, starts[1:] + [len(t)]), 1):
        body = t[a:b].strip()
        if n == 1 and motto:
            body = f"*{motto}*\n\n{body}"
        paras = [re.sub(r"[ \t]+", " ", p).strip() for p in re.split(r"\n\s*\n", body)]
        paras = [p.replace("\n", " ") if not p.startswith("*") else p for p in paras if p]
        merged = []
        for p in paras:                                  # (a fragment cut off by a page break joins the paragraph)
            if merged and (p[:1].islower() or len(p) < 25) and not p.startswith("Completed"):
                merged[-1] += " " + p
            else:
                merged.append(p)
        verses = [v for p in merged for v in pieces(p)]
        out[str(n)] = {str(i + 1): (f"*{v}*" if v.startswith("Completed, and praise") else v)
                       for i, v in enumerate(verses)}
    return out


SIZE = 1500


def pieces(p: str) -> list:
    """A paragraph over SIZE characters (the translation seldom breaks its paragraphs: up to 4,800) in pieces of
    about that size, at the end of a sentence."""
    if len(p) <= SIZE + 300:
        return [p]
    sentences = re.split(r"(?<=[.!?”\"])\s+(?=[A-Z“\"])", p)
    # (a sentence still too long, the curtain's list of generations in 45: at its semicolons)
    sentences = [x for s in sentences for x in (re.split(r"(?<=;)\s+", s) if len(s) > SIZE else [s])]
    out, cur = [], ""
    for s in sentences:
        if cur and len(cur) + len(s) > SIZE:
            out.append(cur)
            cur = s
        else:
            cur = f"{cur} {s}".strip()
    if cur:
        out.append(cur)
    return out


def main() -> None:
    book = chapters(gaps(text()))
    payload = {"source": SOURCE, "books": {"3 Enoch": book}}
    clean_corpus(payload, "charles/3_enoch.json")
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    words = sum(len(v.split()) for c in book.values() for v in c.values())
    print(f"3 Enoch: {len(book)} chapters, {sum(len(c) for c in book.values())} paragraphs, {words:,} words")


if __name__ == "__main__":
    main()
