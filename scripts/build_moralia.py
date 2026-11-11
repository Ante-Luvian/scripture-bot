"""
St Gregory the Great's Morals on the Book of Job (Moralia in Job, c. 590), in the Oxford "Library of the Fathers"
translation (1844-50), as transcribed by Lectionary Central (lectionarycentral.com/gregorymoraliaindex.html)
-> data/patristics/gregory_moralia.json, one book, "Morals on the Book of Job".

Chapter = Gregory's book (1-35; 0 is his letter to Leander and his Preface), verse = his numbered paragraph. Each
book opens (verse 0) with its summary in italics. The verse of Job a paragraph explains ("Ver. 10. Wilt thou bind the
rhinoceros...") leads it in italics, as Gregory gives it ("*Ver. 10.*"): each book's summary says which chapters of
Job it covers, and a verse comes up to three times (its historical, allegorical and moral senses), so the chapter
isn't guessed here. (Gregory read the Latin Bible: his Job 40-41 are numbered as the Vulgate numbers them.) The section marks ("[iv]")
are left out; the references in brackets ("[Job 1, 1]", "[1 Cor. 1, 27]") are the translators' and stay, as
"[Job 1:1]".

    python scripts/build_moralia.py
"""
import html
import json
import re
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CACHE = Path(__file__).resolve().parent / ".cache" / "moralia"
OUT = ROOT / "data" / "patristics" / "gregory_moralia.json"
SITE = "https://lectionarycentral.com/GregoryMoralia/"
UA = {"User-Agent": "ScriptureBot corpus builder (a personal Discord bot)"}
BOOK = "Morals on the Book of Job"
ROMAN = {v: i for i, v in enumerate(
    "I II III IV V VI VII VIII IX X XI XII XIII XIV XV XVI XVII XVIII XIX XX XXI XXII XXIII XXIV XXV XXVI XXVII "
    "XXVIII XXIX XXX XXXI XXXII XXXIII XXXIV XXXV".split(), 1)}
ORDINAL = {w: i for i, w in enumerate(
    "first second third fourth fifth sixth seventh eighth ninth tenth eleventh twelfth thirteenth fourteenth "
    "fifteenth sixteenth seventeenth eighteenth nineteenth twentieth".split(), 1)}


def expect(ok, message):
    if not ok:
        raise SystemExit(f"unexpected source layout: {message}")


def page(name: str) -> str:
    CACHE.mkdir(parents=True, exist_ok=True)
    f = CACHE / name
    if not f.exists():
        f.write_bytes(urllib.request.urlopen(urllib.request.Request(SITE + name, headers=UA), timeout=120).read())
        time.sleep(1)
    raw = f.read_bytes()
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw.decode("cp1252")                              # (Word's HTML, "windows-1252")


def ordinal(words: str) -> int:
    """"thirty-ninth" -> 39, "first" -> 1, "twentieth" -> 20; 0 if it isn't one."""
    words = words.lower().strip()
    if words in ORDINAL:
        return ORDINAL[words]
    m = re.fullmatch(r"(twenty|thirty|forty)-(\w+)", words)
    if m and m[2] in ORDINAL:
        return {"twenty": 20, "thirty": 30, "forty": 40}[m[1]] + ORDINAL[m[2]]
    return {"thirtieth": 30, "fortieth": 40}.get(words, 0)


def paragraphs(src: str) -> list:
    """The page's paragraphs as text, italics as *...*."""
    out = []
    for m in re.finditer(r"(?is)<p\b[^>]*>(.*?)</p>", src):
        p = m.group(1)
        p = re.sub(r"(?is)<(i|em)\b[^>]*>(.*?)</\1>", lambda x: f"*{x.group(2)}*" if x.group(2).strip() else "", p)
        p = html.unescape(re.sub(r"(?s)<[^>]+>", "", p)).replace("\xa0", " ")
        p = re.sub(r"\s+", " ", p).strip()
        p = re.sub(r"\*(\s*)([^*]*?)(\s*)\*", lambda x: f"{x.group(1)}*{x.group(2)}*{x.group(3)}" if x.group(2) else "",
                   p).strip()
        p = re.sub(r"\[(\d?\s?[A-Z][a-z]+\.?) (\d+), (\d+)", r"[\1 \2:\3", p)    # ([Job 1, 1] -> [Job 1:1])
        if re.fullmatch(r"_{12,}", p):                       # (the translators' footnotes follow: left out)
            break
        p = re.sub(r"\s*\[[a-z]{1,2}\]", "", p).strip()       # (a footnote's mark; or a section's, "[i] [LITERAL...")
        # (the scanner's "1" for "l": "a1ready", "1ife" -- not "1st")
        p = re.sub(r"(?<=[a-z])1(?=[a-z])|\b1(?=[a-z]{2,}\b)(?!st\b|nd\b|rd\b|th\b)", "l", p)
        if p and not re.fullmatch(r"_+", p):
            out.append(p)
    return out


def job_chapters(summary: str) -> list:
    """The chapters of Job a book's summary names, in order: "The ninth, with the remaining verses of the
    thirty-ninth chapter" -> [39]; "the end of the fourth, and the fifth chapter" -> [4, 5]."""
    found = []
    for m in re.finditer(r"([\w-]+)\s+(?:and\s+[\w-]+\s+)?chapters?\b|chapter\s+([\w-]+)", summary, re.I):
        n = ordinal(m[1] or m[2])
        if n and n not in found:
            found.append(n)
    for m in re.finditer(r"\b([\w-]+),?\s+(?:and|to)\s+(?:the\s+)?(?:beginning\s+of\s+the\s+)?([\w-]+)\s+chapters?", summary, re.I):
        for w in (m[1], m[2]):
            n = ordinal(w)
            if n and n not in found:
                found.append(n)
    return sorted(found)


NUMBERED = re.compile(r"(\d[\dlIO]*)(\*?)\s*(?:\.\s*|,\s+)(\S.*)$")


def book(n: int) -> dict:
    src = page(f"Book{n:02d}.html")
    paras = paragraphs(src)
    roman = [k for k, v in ROMAN.items() if v == n][0]
    start = next((i for i, p in enumerate(paras) if p == f"BOOK {roman}."), None)
    expect(start is not None, f"Book {n}: no heading")
    paras = paras[start + 1:]
    # (the summary is a sentence or two; the text begins at a section mark, a heading, a number, a verse, or a long
    # paragraph -- a book's first, printed without its "1.")
    first = next(i for i, p in enumerate(paras)
                 if re.match(r"(\[[ivxlc]+\]|\[[A-Z][A-Z ]+\]|\d+\*?\.\s|Ver\.|Chap\.|[A-Z ]{6,}\.$)", p)
                 or (i and len(p) > 400))                         # (the first paragraph is the summary, however long)
    summary = " ".join(paras[:first])
    chapters = job_chapters(summary)
    verses, lead, cur = {"0": f"*{summary}*"}, [], None

    def add(text):
        """Text that belongs to the paragraph being read (or the summary, before the first)."""
        nonlocal lead
        if cur is None:
            verses["0"] += "\n" + "\n".join(lead + [text])
        else:
            verses[cur] += "\n" + "\n".join(lead + [text])
        lead = []

    body = paras[first:]
    numbered = [(i, int(digits(m[1]))) for i, p in enumerate(body) if (m := NUMBERED.match(p))]

    def following(i):
        """The number of the next numbered paragraph after body[i], or None."""
        return next((k for j, k in numbered if j > i), None)

    for i, p in enumerate(body):
        if re.fullmatch(r"\[[ivxlc]+\]", p):
            continue
        if re.match(r"(Home|Moralia Index|Book [IVXL]+|The Epistle)\b", p) and len(p) < 40:
            continue
        if re.fullmatch(r"\[[A-Z][A-Z ]+\]", p):                              # ("[MYSTICAL INTERPRETATION]")
            lead.append(f"*{p.strip('[]').title()}*")
            continue
        # "Chap. xxvii. 1. *Moreover Job...*", "Chap. xlii. ver. 2. *I know...*": a verse heading with its chapter
        c = re.match(r"Chap\.\s*([xvil]+)\.\s*(?:ver\.\s*)?(.*)$", p, re.I)
        if c:
            ver, rest = verse_heading("Ver. " + c[2])
            lead.append(ver.replace("*Ver. ", f"*Chap. {c[1].lower()}. ver. ", 1))
            if rest:
                add(rest)
            continue
        # a numbered paragraph: "8. ...", "8*. So that..." (the italics begun before the stop), "40, Let us..."; and
        # the transcription's misprints, "5." for "55." and "58." for "53." (taken as the next number when it ends it,
        # or when the paragraph after it carries the number after that)
        m = NUMBERED.match(p)
        if m:
            n = int(digits(m[1]))
            nxt = int(cur) + 1 if cur else 1
            if n != nxt and ((n < nxt and str(nxt).endswith(str(n))) or following(i) == nxt + 1):
                n = nxt
            if cur is None or n == nxt or nxt < n < nxt + 3:
                cur = str(n)
                verses[cur] = ""
                lead_now, lead = lead, []
                ver, rest = verse_heading(m[3]) if m[3].startswith("Ver.") else (None, m[2] + m[3])
                verses[cur] = "\n".join(lead_now + ([ver] if ver else []) + ([rest] if rest else []))
                continue
        if p.startswith("Ver."):
            ver, rest = verse_heading(p)
            lead.append(ver)
            if re.fullmatch(r"\[[A-Z][A-Z ]+\]", rest):                     # ("Ver. 1. *...* [LITERAL INTERPRETATION]")
                lead.append(f"*{rest.strip('[]').title()}*")
            elif rest and cur is None:
                lead.append(rest)                                       # (it leads the first paragraph)
            elif rest:
                add(rest)
            continue
        if re.fullmatch(r"[A-Z][A-Z ,'’-]{4,}\.?", p):                    # ("HISTORICAL INTERPRETATION.")
            lead.append(f"*{p.title().rstrip('.')}*")
            continue
        if cur is None and len(p) > 150:      # (a book's first paragraph, printed without its "1.")
            cur = "1"
            verses[cur] = "\n".join(lead + [p])
            lead = []
            continue
        add(p)
    if lead and cur:
        verses[cur] += "\n" + "\n".join(lead)
    return {"verses": verses, "job": chapters}


def digits(s: str) -> str:
    """A number with the scanner's slips put right: "l0" -> "10", "I5" -> "15", "1O" -> "10"."""
    return s.translate(str.maketrans("lIO", "110"))


def verse_heading(p: str) -> tuple:
    """"Ver. 8, 9. *He is higher than heaven...*" -> ("*Ver. 8, 9.* *He is higher than heaven...*", ""); the verse is
    the italic part, and what follows it on the line (Gregory's comment, in Book I) is returned as the rest.
    "Ver. 11*. For He knoweth...*" (the italics begun before the stop) is read as "Ver. 11. *For He knoweth...*"."""
    p = re.sub(r"^Ver\.\s*\*\s*([\dlIO][\d, –-]*)\.\s*", r"Ver. \1. *", p)     # ("Ver. *7. Who..." : italics too soon)
    p = re.sub(r"^Ver\.\s*([\dlIO]+)", lambda x: "Ver. " + digits(x[1]), p)   # (a scanning slip: "Ver.l0")
    p = re.sub(r"^(Ver\.\s*\d+)\.?\s*\*\s*([—–-]\s*\d+)\.\s*", r"\1\2. *", p)    # ("Ver. 18.* *—20. I am full...")
    m = re.match(r"Ver\.\s*(\d+(?:\s*[,—–-]\s*\d+)*)\s*(\*?)\s*[.,]?\s*(.*)$", p)
    expect(m, f"verse heading {p[:40]!r}")
    nums = re.sub(r"\s*[—–-]\s*", "–", re.sub(r"\s*,\s*", ", ", m[1]))
    body = (m[2] + m[3]).strip()
    if body.startswith("*"):
        j = body.find("*", 1)
        verse, rest = (body[1:j], body[j + 1:]) if j > 0 else (body[1:], "")
    else:
        verse, rest = body, ""
    verse = verse.strip().strip(",").strip()
    rest = rest.lstrip(" .,;").strip()
    head = f"*Ver. {nums}.*" + (f" *{verse}*" if verse else "")
    return head, rest


def front() -> dict:
    """Chapter 0: the letter to Leander, then the Preface, its paragraphs numbered on through both."""
    verses, k = {}, 0
    for name, title in (("Epistle.html", "The Epistle to Leander"), ("Preface.html", "Preface")):
        paras = paragraphs(page(name))
        i = next(i for i, p in enumerate(paras) if re.match(r"([IVXL]+|\d+)\.\s", p))
        lead = [f"*{title}*"]
        for p in paras[i:]:
            if re.match(r"(Home|Moralia Index|Book [IVXL]+|The Epistle|Preface)\b", p) and len(p) < 40:
                continue
            m = re.match(r"(?:[IVXL]+|\d+)\.\s+(.*)$", p)
            if m:
                k += 1
                verses[str(k)] = "\n".join(lead + [m[1]])
                lead = []
            elif k:
                verses[str(k)] += "\n" + p
    return verses


def main():
    chapters, jobs = {"0": front()}, {}
    for n in range(1, 36):
        b = book(n)
        chapters[str(n)] = b["verses"]
        jobs[str(n)] = b["job"]
        print(f"  Book {n}: {len(b['verses']) - 1} paragraphs, Job {b['job']}")
    data = {"source": "trans. Library of the Fathers (1844–50)", "books": {BOOK: chapters}}
    OUT.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{BOOK}: {sum(len(c) for c in chapters.values())} passages -> {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
