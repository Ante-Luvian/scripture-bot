"""
Marsilio Ficino's De vita libri tres (Three Books on Life), with what the 1529 Basel edition prints after it (his
Apology, a letter on tranquillity of mind, his Antidote against the plague, and a regimen for the seasons), in
Source Library's English (2026): a machine translation (AI, from an OCR of the Latin), not reviewed by any person,
as its own record says. The owner chose it: there is no other complete English text online. From the PDF at
zenodo.org/records/21460148 (CC BY-SA 4.0), into data/esoteric/ficino.json.

Only the main text's type (10 pt) is kept: footnotes, their numbers, page numbers and margin numbers are set
smaller. A text block is a paragraph; a sentence broken over a page ("...joyful…" / "…gifts") is joined.

    python scripts/build_ficino.py [--list]
"""
import json
import re
import sys
import urllib.request
from pathlib import Path

import fitz

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from corpus_clean import clean_corpus  # noqa: E402

PDF = ROOT / "scripts" / ".cache" / "ficino" / "de_vita.pdf"
OUT = ROOT / "data" / "esoteric" / "ficino.json"
URL = ("https://zenodo.org/records/21460148/files/de-vita-libri-tres-three-books-on-life-1529-ficino-scholarly-"
       "v1.0.0.pdf?download=1")


def paragraphs() -> list:
    """The main text's blocks, in order, as paragraphs; from the first chapter of Book One to the end."""
    if not PDF.exists():
        PDF.parent.mkdir(parents=True, exist_ok=True)
        req = urllib.request.Request(URL, headers={"User-Agent": "ScriptureBotCorpusBuilder/1.0"})
        PDF.write_bytes(urllib.request.urlopen(req, timeout=120).read())
    out = []
    for page in fitz.open(PDF):
        for block in page.get_text("dict")["blocks"]:
            lines = []
            for line in block.get("lines", []):
                text = "".join(s["text"] for s in line["spans"] if s["size"] >= 9.5)
                if text.strip():
                    lines.append(text.strip())
            if not lines:
                continue
            para = ""
            for line in lines:                         # (a word broken at a line's end: "Studio- sorum")
                para = para[:-1] + line if para.endswith("-") and line[:1].islower() else f"{para} {line}".strip()
            out.append(re.sub(r"\s+", " ", para))
    start = next(i for i, p in enumerate(out) if p == "BOOK ONE.")
    end = next(i for i, p in enumerate(out) if p.startswith("Colophon"))
    joined = []
    for p in out[start:end]:
        if joined and joined[-1].endswith("…") and p.startswith("…"):
            joined[-1] = joined[-1][:-1] + p[1:]       # (a sentence over a page break)
        else:
            joined.append(p)
    return joined


# the edition's running heads and page furniture: "MAR. F. DE VITA COELITVS", "COMPARANDA LIB. III.", "ANTIDOTVS."
RUNNING = re.compile(r"(?i)^(?:\d+|.*\blib\.\s*[iv]+\.?|mars?\.?\s*f(?:ic)?\w*\.?[:.]?\s*(?:de vita|on the health|epidemics)"
                     r".*|mar\.? fic\.? epidemics|(?:comparanda|prodvcenda|sanitate tvenda)\b.*|antidot(?:e|vs)\.|"
                     r"mons fici.*|on gold|divine thomas|bezoar stones\.|men who are solar|p r e f a c e\.)$")
MARK = re.compile(r"(?i)\s*\b(?:chap(?:ter)?|ch|cap)\.?\s*:?\s*([ivxlc]+|\d+|one|two)\b\.?\s*(?::\s*(.*))?$")
WORDS = {"one": 1, "two": 2}


def roman(s: str):
    s = s.lower()
    if s.isdigit():
        return int(s)
    if s in WORDS:
        return WORDS[s]
    vals = {"i": 1, "v": 5, "x": 10, "l": 50, "c": 100}
    if not all(c in vals for c in s):
        return None
    return sum(-vals[c] if i + 1 < len(s) and vals[s[i + 1]] > vals[c] else vals[c] for i, c in enumerate(s))


def parts(paras: list) -> list:
    """[(book, [paragraphs])] by the edition's own beginnings and ends."""
    cuts = [("Three Books on Life 1", "Concerning the nine guides of scholars"),
            ("Three Books on Life 2", "MARSILIO FICINO OF FLORENCE, in the Second Book on Protracting Life"),
            ("Three Books on Life 3", "MARSILIO FICINO OF FLORENCE An epistolary preface to the third book"),
            ("Ficino's Apology", "MARSILIUS FICINO’S APOLOGY"),
            ("On the Tranquillity of Life", "THAT SECURITY AND TRANQUILITY OF MIND"),
            (None, "ANDREAS LEENNIUS TO THOSE STUDYING MEDICINE"),        # (the 1529 editor's letter: out)
            ("Antidote against Epidemics", "I deemed it necessary, urged by a sense of duty"),   # (his preface)
            ("On the Regimen of Life According to the Seasons", "The regimen of life useful at any time of the year.")]
    at = [(name, next(i for i, p in enumerate(paras) if p.startswith(start))) for name, start in cuts]
    return [(name, paras[i:(at[k + 1][1] if k + 1 < len(at) else len(paras))])
            for k, (name, i) in enumerate(at) if name]


def chapters(paras: list) -> dict:
    """{chapter: [paragraphs]}: "0" what comes before the first chapter, then a chapter at each "Chapter II." (at a
    heading's end or on a line of its own after it); a number out of order (the edition's misprints) is the next."""
    out, current, last = {"0": []}, "0", 0
    for p in paras:
        m = MARK.search(p)
        if m and len(p.split()) <= 45 and roman(m.group(1)) is not None:
            n = last + 1                               # (in sequence: the Antidote prints "XXV" for XXIII)
            heading = p[:m.start()].strip() or (m.group(2) or "").strip()
            if not heading and out[current] and len(out[current][-1].split()) <= 30:
                heading = out[current].pop()           # (the heading, the line before "Cap. VIII.")
            last, current = n, str(n)
            out[current] = [f"*{heading.rstrip('.:')}*"] if heading else []
            continue
        out[current].append(p)
    return {c: ps for c, ps in out.items() if ps}


def tidy(paras: list) -> list:
    out = []
    for p in paras:
        if RUNNING.match(p.strip()) or re.match(r"(?i)^(?:the end|end of the book|the end of|the book on lengthening|"
                                                r"book one\.$)", p):
            continue
        if out and (p[:1].islower() or re.match(r"[.,;:]\s", p)):
            out[-1] += ("" if re.match(r"[.,;:]", p) else " ") + p   # (a paragraph that ran over a page)
        else:
            out.append(p)
    return out


def main() -> None:
    paras = tidy(paragraphs())
    books = {"Three Books on Life": {}}
    for name, ps in parts(paras):
        chs = chapters(ps)
        if name.startswith("Three Books on Life"):
            n = name[-1]
            for c, cps in chs.items():
                books["Three Books on Life"][f"{n}.{c}"] = cps
        else:
            books[name] = chs if len(chs) > 1 else {"1": next(iter(chs.values()))}
    out = {}
    for name, chs in books.items():
        out[name] = {}
        for c, ps in chs.items():
            merged = []
            for p in ps:                               # (a heading line leads the paragraph after it)
                if merged and re.fullmatch(r"\*[^*\n]+\*", merged[-1]):
                    merged[-1] += "\n" + p
                else:
                    merged.append(p)
            out[name][c] = {str(i + 1): p for i, p in enumerate(merged)}
    src = "Marsilio Ficino, machine translation (AI), Source Library (2026)"
    payload = {"source": src, "books": out, "book_sources": {b: src for b in out}}
    clean_corpus(payload, "esoteric/ficino.json")
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    for name, chs in payload["books"].items():
        print(f"  {name}: {len(chs)} chapters ({', '.join(list(chs)[:4])}...), "
              f"{sum(len(v.split()) for c in chs.values() for v in c.values()):,} words")


if __name__ == "__main__" and "--list" not in sys.argv:
    main()

if __name__ == "__main__" and "--list" in sys.argv:
    for i, p in enumerate(paragraphs()):
        if len(p.split()) <= 25 or p.isupper() or re.search(r"(?i)\b(chap(?:ter)?|cap)\.? [ivxlc\d]+\.?$|chapter \w+\.$", p):
            print(i, p[:140])
