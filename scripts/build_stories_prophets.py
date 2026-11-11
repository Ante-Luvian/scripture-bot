"""
Ibn Kathir's Stories of the Prophets (Qisas al-Anbiya, compiled from his al-Bidayah wa'l-Nihayah) in the English of
Muhammad Mustapha Geme'ah of al-Azhar, from the typeset PDF islambasics.com and kalamullah.com issued (2004; a copy
is kept on the Internet Archive -- a digital edition, not a scan), into data/quran/stories_of_the_prophets.json
(2026-11-10).

A chapter for each of its 29 prophets, Adam to Muhammad, its heading ("Prophet Adam") leading verse 1 in italics.
The book prints no verse numbers: a verse is a paragraph, or a run of whole sentences of a long one; a paragraph
broken by a page is joined again. Its section headings ("Informing the Angels About Adam") lead the paragraph that
follows, in italics. Left out: the contents page and the site's address at the foot of the pages. The PDF's
typing slips are put right (SLIPS); where it lost letters the sense makes certain they are restored in [brackets],
and where it lost a word that can't be known, […] marks the place.

    python scripts/build_stories_prophets.py
"""
import json
import re
import sys
import time
import urllib.request
from pathlib import Path

import fitz   # PyMuPDF

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_budge import groups               # noqa: E402
from build_pseudepigrapha import expect      # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
CACHE = Path(__file__).resolve().parent / ".cache" / "stories_prophets"
OUT = ROOT / "data" / "quran" / "stories_of_the_prophets.json"
URL = ("https://ia600406.us.archive.org/7/items/StoriesOfTheProphetsByIbnKathir_20160627/"
       "Stories%20Of%20The%20Prophets%20By%20Ibn%20Kathir.pdf")
UA = {"User-Agent": "ScriptureBot corpus builder (a personal Discord bot)"}
BOOK = "Stories of the Prophets"


def pdf() -> fitz.Document:
    CACHE.mkdir(parents=True, exist_ok=True)
    f = CACHE / "stories_of_the_prophets.pdf"
    if not f.exists():
        f.write_bytes(urllib.request.urlopen(urllib.request.Request(URL, headers=UA), timeout=120).read())
        time.sleep(1)
    return fitz.open(f)


def lines(doc) -> list:
    """Every line of the text as (page, y, size, bold, text), without the footer and the title and contents pages."""
    out = []
    for pno in range(2, doc.page_count):                     # (pages 1-2: blank, title and contents)
        for blk in doc[pno].get_text("dict")["blocks"]:
            for ln in blk.get("lines", []):
                spans = [s for s in ln["spans"] if s["text"].strip()]
                text = re.sub(r"\s+", " ", "".join(s["text"] for s in ln["spans"])).strip()
                if not spans or "islambasics.com" in text:
                    continue
                bold = all("Bold" in s["font"] for s in spans)
                out.append((pno, ln["bbox"][1], max(s["size"] for s in spans), bold, text))
    return out


# Typing slips in the PDF, each required to be found. Letters it lost where the sense is certain are put back in
# [brackets] ("bl[ood] flowed"); where a word is lost and can't be known, […] marks the gap.
SLIPS = {
    "disbeliveers": "disbelievers", "fourty": "forty", "progency": "progeny", "postrate": "prostrate",
    "to prostate before": "to prostrate before", "people prostate before": "people prostrate before",
    "rainments": "raiments", "thrist": "thirst", "firious": "furious", "comfounded": "confounded",
    "trustworth servant": "trustworthy servant", "searious": "serious", "surrended": "surrendered",
    "inovocation": "invocation", "humilty": "humility", "generousity": "generosity", "repentanc.": "repentance.",
    "cheifs": "chiefs", "peolple": "people", "perfom": "perform", "doiciled": "domiciled", "tings": "things",
    "hyour": "your", "thepeople": "the people", "wihim": "with him", "witthe": "with the", "vand ": "and ",
    "hagiven": "has given", "thopened": "they opened", "irevenge": "in revenge", "sharinhis": "sharing his",
    "innernself": "inner self", "Canaanites brav,": "Canaanites bravely,", "his soth Seth": "his son Seth",
    "he sai:": "he said:", "one of theo other": "one of the other", "seventy en out": "seventy men out",
    "Murimun": "Mujrimun", "absent mindly": "absent-mindedly",
    "blflowedwithouttheir": "bl[ood] flowed without their", "gone in sof our": "gone in s[earch] of our",
    "ithe wolves within them": "[Did he mean] the wolves within them", "from tthey": "from t[here] they",
    "wyou have some": "w[hile] you have some", "and bthem to": "and b[rought] them to",
    "ladiesnursthe to possess": "ladies nurs[ed] the […] to possess", "if evil athem": "if evil […] them",
    "cothe afflicted": "[…] the afflicted", "and everlost his life": "and ev[entually] lost his life",
}


def mend(book: dict) -> None:
    seen = dict.fromkeys(SLIPS, 0)
    for verses in book.values():
        for v, t in list(verses.items()):
            t = re.sub(r"\s*www\.islambas\w*\.com\s*", " ", t).strip()     # (the address, misspelt on one page)
            for slip, right in SLIPS.items():
                seen[slip] += t.count(slip)
                t = t.replace(slip, right)
            verses[v] = t
    expect(all(seen.values()), f"slips not found {[s for s, n in seen.items() if not n]}")
    for c, verses in book.items():                    # (a verse that was only the address)
        kept = [t for t in verses.values() if t.strip("* \n")]
        book[c] = {str(n): t for n, t in enumerate(kept, start=1)}


def build() -> dict:
    book, chapter, paras, pending_head = {}, None, [], None
    current, last_y, last_page = "", None, None

    def flush():
        nonlocal current, pending_head
        if current.strip():
            text = re.sub(r"\s+", " ", current).strip()
            paras.append((pending_head, text))
            pending_head = None
        current = ""

    def close_chapter():
        if chapter is None:
            return
        flush()
        merged = []                                   # ("Allah the Almighty revealed:" joins the quotation it opens)
        for head, text in paras:
            if merged and merged[-1][1].endswith(":") and len(merged[-1][1]) < 150 and not head:
                merged[-1] = (merged[-1][0], f"{merged[-1][1]} {text}")
            else:
                merged.append((head, text))
        verses = []
        for head, text in merged:
            runs = groups(text)
            if head:
                runs[0] = f"*{head}*\n{runs[0]}"
            verses += runs
        verses[0] = f"*{book_titles[chapter]}*\n{verses[0]}"
        book[str(chapter)] = {str(n): v for n, v in enumerate(verses, start=1)}

    book_titles = {}
    for page, y, size, bold, text in lines(pdf()):
        # a chapter: "Prophet Adam", 13-22 pt (Noah's is 13, the text 12 or 14 in Adam's opening pages), the line
        # nothing but the name
        if size >= 12.9 and not bold and re.fullmatch(r"Prophet [A-Z][\w’' -]*(?:\([^)]*\))?(?: and [^()]+\([^)]*\))?", text):
            close_chapter()
            chapter = (chapter or 0) + 1
            book_titles[chapter] = re.sub(r"\s*-\s*", "-", text)   # ("Dhul - Kifl")
            paras, pending_head, current, last_y, last_page = [], None, "", None, page
            continue
        expect(chapter is not None, f"text before the first prophet: {text[:50]!r}")
        if bold and len(text) < 100 and not text.endswith(":"):   # (a section heading; "...revealed:" is text)
            flush()
            pending_head = text
            last_y, last_page = y, page
            continue
        # a new paragraph at a gap of more than a line and a half, or a new page whose first line doesn't
        # carry on a sentence left open at the foot of the last
        if last_page is not None and page != last_page:
            if re.search(r"[.!?:\"”')\]]\s*$", current):
                flush()
        elif last_y is not None and y - last_y > 1.6 * size:
            flush()
        current += " " + text
        last_y, last_page = y, page
    close_chapter()
    expect(list(book) == [str(n) for n in range(1, 30)], f"chapters {list(book)}")
    mend(book)
    return book


def main() -> None:
    book = build()
    print(f"  {BOOK}: {len(book)} chapters, {sum(map(len, book.values()))} verses")
    OUT.write_text(json.dumps({"source": "Ibn Kathir, trans. Muhammad Mustapha Geme'ah", "books": {BOOK: book}},
                              ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
