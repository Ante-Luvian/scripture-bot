"""
The Sayings of the Desert Fathers (data/patristics/desert_fathers.json): E. A. Wallis Budge's translation
of the Syriac "Book of Paradise", Vol. II (1907): the sayings of the fathers (Book I, sayings 1-635, in
fourteen chapters by subject) and the questions and answers on the ascetic rule (Book II).

  python scripts/build_desert_fathers.py          download, OCR, build (each step cached)

No transcription exists, so the text is read from the University of Toronto's scan on the Internet
Archive with Tesseract (installed at C:\\Program Files\\Tesseract-OCR), one page image at a time,
as a single block of text (Tesseract's default page layout drops and reorders lines on these pages).
What the OCR gets wrong in a regular way is put right here: Budge's old-style figures ("Ir." for 11,
"go." for 90), the quotation mark he repeats at the start of every line of a quotation, words broken
at the ends of lines, and "Abbâ". The decorated capital that opens each chapter, and the chapters'
black-letter headings, are corrected by hand (OPENINGS, CHAPTERS below), checked against the scans.
"""
import difflib
import json
import re
import subprocess
import sys
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "scripts" / ".cache" / "paradise_v2"
OUT = ROOT / "data" / "patristics" / "desert_fathers.json"
ITEM = "theparadiseorgar00unkwuoft"
FIRST, LAST = 12, 345                    # the page images holding the text (the index follows)
TESSERACT = r"C:\Program Files\Tesseract-OCR\tesseract.exe"


# ── the pages ───────────────────────────────────────────────────────────────

def image(n: int) -> Path:
    path = CACHE / "img" / f"n{n:03d}.jpg"
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        url = f"https://archive.org/download/{ITEM}/page/n{n}_w1100.jpg"
        path.write_bytes(urllib.request.urlopen(url, timeout=120).read())
    return path


def ocr(n: int) -> str:
    path = CACHE / "ocr" / f"n{n:03d}.txt"
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run([TESSERACT, str(image(n)), str(path.with_suffix("")), "--psm", "6", "-l", "eng"],
                       capture_output=True, check=True)
    return path.read_text(encoding="utf-8")


def all_pages() -> dict:
    with ThreadPoolExecutor(6) as ex:
        texts = list(ex.map(ocr, range(FIRST, LAST + 1)))
    return dict(zip(range(FIRST, LAST + 1), texts))


# ── corrections by hand, read from the scans ────────────────────────────────
# Each chapter: (page image, Budge's heading, the number printed in the margin against its first
# saying (None: the first of a book, unnumbered), and the first three lines, which run beside the
# decorated capital and come out of the OCR mangled).

CHAPTERS = [
    (12, 1, "Chapter I. Of Flight from Men, and of Silent Contemplation, and of Dwelling continually in the Cell, "
            "[a work] which was composed by Bishop Palladius for the Prefect Lausus", None,
     "When Abbâ Arsenius was in the palace, he prayed to God, and said, “O Lord, direct me how to live”; and "
     "a voice came to him, saying, “Arsenius, flee from"),
    (25, 1, "Chapter II. Of Fasting and Abstinence and of other [similar] Labours", 63,
     "They used to say about Abbâ Paphnutius that he would not readily drink wine, and that on one occasion he "
     "came by chance upon a band of thieves, and found them"),
    (33, 1, "Chapter III. Of the Reading of the Scriptures, and of watching by Night, and of the Service of the Psalms, "
            "and of constant Prayers", 105,
     "They used to say about Abbâ Arsenius that no man was able to attain to the manner of life in his abode. And they "
     "also said about him that on the night of the Sabbath"),
    (40, 1, "Chapter IV. Of how it is meet for us to Weep for our Sins and to Mourn for them always", 136,
     "A brother asked Abbâ Ammon, and said unto him, “Tell me some word whereby I may live”; and Abbâ "
     "Ammon said unto him, “Go and make thy mind like"),
    (44, 1, "Chapter V. Of Voluntary Poverty", 158,
     "Abbâ Arsenius once fell sick at Scete, and he was in need of a bowl of pottage; and since this was not to "
     "be found there, he took the remains of the Eucharist"),
    (49, 1, "Chapter VI. Of Patient Endurance", 183,
     "On one occasion certain brethren went to Abbâ Agathon, because they had heard that he took the greatest possible "
     "care that his mind should not be disturbed by anything,"),
    (61, 1, "Chapter VII. Of Obedience towards God, and towards our Fathers and Brethren", 238,
     "They say that Abbâ John, the disciple of Abbâ Paulê, possessed great obedience. Now in the place where "
     "they used to live there was a sepulchre, wherein dwelt"),
    (65, 1, "Chapter VIII. Of Scrupulous Watchfulness in our Thoughts and Words and Deeds", 248,
     "Abbâ Poemen used to say, “Satan hath three kinds of power which precede all sin. The first is error, and "
     "the second is neglect (*or* laxity), and the third is lust."),
    (97, 1, "Chapter IX. Of Love, and Charity, and of the Welcoming of Strangers", 393,
     "A certain old man used to dwell with a brother in a cell in a friendly manner, and he was a man of "
     "compassionate disposition; now a famine broke out, and"),
    (112, 1, "Chapter X. Of Humility and of how a Man should think lightly of himself, and should esteem himself "
             "the Inferior of every Man", 444,
     "Abbâ Isaac, the priest of the Cells, used to say: When I was a young man I used to dwell with Abbâ "
     "Chronius, and he never at any time told me to do any"),
    (135, 1, "Chapter XI. Of Fornication", 559,
     "A certain monk was engaged, on one occasion, in a war against fornication, and he had in his heart, as it "
     "were, a burning fire by day and by night; but he bore"),
    (145, 1, "Chapter XII. Of the Acceptance of Repentance, and of how it is right for us to Repent in Truth", 598,
     "Two brethren were in restraint to the lust of fornication, and they went and took to themselves wives. At "
     "length, however, they repented, and said to each other,"),
    (150, 1, "Chapter XIII. Of [the Fathers who] wrought Wonderful Works", 614,
     "Abbâ Sisoes said: When we were in Scete, with Abbâ Macarius, seven of us went up to reap with him, and "
     "behold, a certain widow followed after us gleaning, and"),
    (155, 1, "Chapter XIV. Of the Greatness of the Sublime Rule of the Solitary Life", 631,
     "There was a certain old man amongst the fathers who used to see visions, and this man testified, and said, "
     "“That power which I have seen existing in baptism, I"),
    (158, 2, "Chapter I. Questions and Answers on the Rule of Life of the Holy Men which they taught before the "
             "Multitude and in their Cells on every kind of Spiritual Excellence", None,
     "Two of the fathers entreated God to inform them as to the measure [of spiritual excellence] to which they had "
     "arrived, and a voice came to them which said, “In"),
    (271, 2, "Chapter XVI. Questions by the Pupils and the Answers [to the same] by the holy Fathers and Monks", 541,
     "Brother. How is love (*or* charity) acquired by men of understanding?"),
    (280, 2, "Chapter XVIII. Questions and Answers on the Vision of the Mind", 578,
     "A brother asked an old man, saying, In what manner ought a monk to dwell in silent contemplation in "
     "his cell? The old man said, He should have no re-"),
]


# ── reading the OCR ─────────────────────────────────────────────────────────

_RUNNING = re.compile(r"(?i)^\W*(the sa[vy]ings of the|questions and .nswers on the|of [a-z])")
_FIGURES = str.maketrans({"I": "1", "l": "1", "i": "1", "r": "1", "t": "1", "T": "1", "|": "1", "o": "0", "O": "0",
                          "g": "9", "z": "2", "Z": "2", "A": "4"})


def body_lines(n: int, text: str) -> list:
    """A page's lines without its running head, page number and signature."""
    # marks in the left margin, from the facing page showing through ("| ", "_ ", "} ")
    lines = [re.sub(r"^(?:[|_}\\;:~]+\s+|[\d|]{1,2}\s+(?=[a-z]))+", "", l.rstrip()) for l in text.splitlines()]
    junk = re.compile(r"\W*\S{0,3}\W*")
    while lines and (not lines[0].strip() or junk.fullmatch(lines[0].strip())):
        lines.pop(0)
    if lines and len(lines[0]) < 70 and _RUNNING.search(lines[0]) and not re.search(r"[.;,]\s*$", lines[0]):
        lines.pop(0)
    while lines and (not lines[-1].strip() or junk.fullmatch(lines[-1].strip())
                     or re.fullmatch(r"\W*\S?\W*[\dIl]{1,3}\W*(\S{1,8})?\W*", lines[-1].strip())):
        lines.pop()
    return lines


_NUMBER = re.compile(r"^(?:\S{1,2}\s+)?[^\w\[(]{0,3}([0-9IlirtTo|OgzA]{1,4})[.,]\s+(?=\S)")


def candidate(line: str):
    """(match, the figures it reads as, whether they were printed as figures) for a line that may open a
    saying: Budge's old-style figures come out as letters ("Ir." 11, "go." 90, "tor." 101)."""
    m = _NUMBER.match(line)
    if not m:
        return None
    value = m.group(1).translate(_FIGURES)
    return (m, value, m.group(1).isdigit()) if value.isdigit() else None


# Figures the OCR mangled past reading, checked against the scans: (book, how the line begins, saying).
# (Book II has no saying 133: Budge's numbering goes from 132 to 134.)
BY_HAND = [(2, r"^Ig\. An old man was asked", 191), (2, r"^me The brethren said", 702)]


def numbering(evs: list) -> dict:
    """{index of an event: the saying it opens}. A candidate is taken if it reads as the next number; or
    as one a little further on (sayings whose figure the OCR lost entirely are then missing, and
    reported); or as the next with a lost leading figure ("58." for 358); or with one figure misread,
    when the candidate after it carries on from it."""
    def by_hand(line, book):
        return next((n for b, pattern, n in BY_HAND if b == book and re.match(pattern, line)), None)
    marks = [(i, e) for i, e in enumerate(evs)
             if e[0] == "chapter" or (e[0] == "line" and (candidate(e[1]) or any(re.match(p, e[1]) for _, p, _ in BY_HAND)))]
    out, expected, book = {}, 1, 1
    for k, (i, e) in enumerate(marks):
        if e[0] == "chapter":
            if e[1] != book:
                book, expected = e[1], 1
            expected = (e[3] or expected) + 1
            continue
        if by_hand(e[1], book):
            out[i] = by_hand(e[1], book)
            expected = out[i] + 1
            continue
        m, value, figures = candidate(e[1])
        want = str(expected)
        later = next((candidate(f[1]) for j, f in marks[k + 1:] if f[0] == "line" and candidate(f[1])), None)
        nxt = later[1] if later else ""
        v = int(value)
        if v == expected:
            take = v
        elif figures and expected < v <= expected + 3:
            take = v
        elif len(value) < len(want) and want.endswith(value):
            take = expected
        elif (len(value) == len(want) and sum(a != b for a, b in zip(value, want)) == 1
              and nxt.isdigit() and int(nxt) == expected + 1):
            take = expected
        else:
            continue
        out[i] = take
        expected = take + 1
    return out


# ── putting the sayings together ────────────────────────────────────────────

_OPEN = re.compile(r"(?:‘‘|““|“|\*\*|\*‘|‘\*|“\*|\*“|‘“|“‘|¢|\"|(?<![\w’])‘)\s?(?=[\w\[(‘])")
_CLOSE = re.compile(r"(?<=[\w.,;:!?\])—’'])(?:’’|””|”|’”|”’|\"|''|’(?![\w]))")
# (Budge's line-start quotation marks come out of the OCR as any of these)
_LEAD = re.compile(r"^[\s‘’“”\"'*¢|_\\~«»©€<>{}§%°®¥$#=/@]+")
_JUNK = re.compile(r"(?:(?<=\s)|^)[«»©€¢<>{}§%~°®¥$#=/\\@|_]+(?=\s|$)|(?<=\s)[«»©€¢<>§%~°®¥$#=@]+(?=[“‘\w])"
                   r"|(?<=[\s“‘])[«*]+(?=[“‘\w])")


def dictionary() -> set:
    """Words known to be words (for rejoining words broken at line ends, and parting words run
    together): the KJV's, and any the OCR read three times or more in this book."""
    import collections
    words = set(re.findall(r"[a-z]+", (ROOT / "data" / "kjv" / "kjv_canon.json").read_text(encoding="utf-8").lower()))
    _KJV.update(words)
    counts = collections.Counter(re.findall(r"[a-z]+", "\n".join(all_pages().values()).lower()))
    return words | {w for w, n in counts.items() if n >= 3}


def quotes(line: str, depth: int, starts: bool) -> "tuple[str, int]":
    """The line with Budge's repeated line-start quotation marks gone and the rest made “curly”, and
    whether a quotation is still open at its end."""
    lead = _LEAD.match(line)
    if lead and not starts:
        marks = re.sub(r"[\s|_\\~]", "", lead.group(0))
        line = line[lead.end():]
        if marks and depth == 0:                          # (a quotation opening at the start of a line)
            line, depth = "“" + line, 1
    elif lead:
        marks = re.sub(r"[\s|_\\~]", "", lead.group(0))
        line = ("“" if marks else "") + line[lead.end():]
        depth = 1 if marks else depth

    def opened(m):
        nonlocal depth
        if m.group(0).strip() == "‘" and depth:
            return m.group(0)                             # (a quotation within one)
        depth += 1
        return "“"

    def closed(m):
        nonlocal depth
        if m.group(0) == "’" and depth != 1:
            return m.group(0)
        depth = max(0, depth - 1)
        return "”"
    line = _OPEN.sub(opened, line)
    line = _CLOSE.sub(closed, line)
    line = re.sub(r"([”’])[’”']+", r"\1", line)         # ("?’”’")
    return re.sub(r"“\s+", "“", line), depth


_KJV: set = set()                     # (filled by dictionary())
_SMALL = set("a i to of the and in is he it be was do go my me we ye at on an or as so no by his him her".split())


def split_runs(text: str, words: set) -> str:
    """Words the OCR ran together ("Havea", "tospit", "thoseevil"): an unknown word that divides one
    way only into two known ones."""
    def fix(m):
        w = m.group(0)
        if w.lower() in words or len(w) < 4:
            return w
        splits = [(w[:i], w[i:]) for i in range(1, len(w))
                  if w[:i].lower() in words and w[i:].lower() in words
                  and (w[:i].lower() in _SMALL or w[i:].lower() in _SMALL)]
        both = [s for s in splits if s[0].lower() in _SMALL and s[1].lower() in _SMALL]   # ("ofthe": not "oft he")
        return " ".join(splits[0]) if len(splits) == 1 else " ".join(both[0]) if len(both) == 1 else w
    return re.sub(r"\b[A-Za-z]+\b", fix, text)


def tidy(text: str) -> str:
    text = _JUNK.sub("", text)
    text = re.sub(r"\[([^\[\]|{}]*)[|}]", r"[\1]", text)              # ("[the third cup|")
    text = re.sub(r"\{([^{}\[\]]*)\]", r"[\1]", text)                 # ("{trouble]")
    # the printed "ct" ligature: "direét", "correé&t", "distin@", "striG@t"
    text = re.sub(r"(?<=[a-z])(?:é&|é|G@|@)t", "ct", text)
    text = re.sub(r"(?<=[a-z])@", "ct", text)
    text = re.sub(r"(?<=[a-z]{3})é(?=[\s,.;:!?])", "ct", text)        # ("perfeé labour")
    text = re.sub(r"(?<=[a-z])&(?=\W)", "ct", text)                   # ("condu&")
    text = re.sub(r"\bAbb[aAâàáäéèe&4]{1,2}(?=\W)", "Abbâ", text)
    # "[" read as "T" ("T and if we have]", "Tf or us to have]"), then "I" read as "T" ("and T pray",
    # "T possessed", "Tf I can find")
    text = re.sub(r"(?<![\w\[])T(f?) ?(?=[a-z][^\[\]\n]{0,80}\])", lambda m: "[" + m.group(1), text)
    text = re.sub(r"(?<![\w.])T(?= [a-z])", "I", text)
    text = re.sub(r"\bTf\b", "If", text)
    text = re.sub(r"\bO[lt][dp]\s+M[a@]n\b", "Old Man", text)
    accent = str.maketrans("áàéèíìóòúù", "ââêêîîôôûû")
    text = re.sub(r"\b[A-Z][a-z]*[áàéèíìóòúù][a-zâêîôû]*\b", lambda m: m.group(0).translate(accent), text)
    # runs of small capitals ("BOAST OF THEIR ALMS.") in sentence case
    text = re.sub(r"\b[A-Z]{2,}(?:[ ,]+[A-Z]{2,})+\b", lambda m: m.group(0).capitalize(), text)
    text = re.sub(r"\s+([,;:.!?])(?=\s|$)", r"\1", text)
    text = re.sub(r"\[\s+", "[", text)
    text = re.sub(r"\s+\]", "]", text)
    text = re.sub(r"\s{2,}", " ", text)
    text = re.sub(r"“{2,}", "“", text)
    text = re.sub(r"”{2,}", "”", text)
    return text.strip()



def events(pages: dict) -> list:
    """The volume as one stream: ("line", text), ("blank",), ("chapter", book, heading, number, opening)."""
    openings = {n: rest for n, *rest in CHAPTERS}
    out = []
    for n, text in pages.items():
        lines = body_lines(n, text)
        if n in openings:
            book, heading, number, opening = openings[n]
            at = next(i for i, l in enumerate(lines) if re.search(r"hapter|bapter", l))
            want = re.sub(r"\W", "", opening[1:30]).lower()
            first = next(i for i in range(at + 1, len(lines))
                         if difflib.SequenceMatcher(None, re.sub(r"\W", "", lines[i]).lower()[:len(want)], want).ratio() > 0.5)
            out += [("blank",) if not l.strip() else ("line", l) for l in lines[:at] if not re.match(r"\W*Book\b", l)]
            out.append(("chapter", book, heading, number, opening))
            nonblank = [i for i in range(first, len(lines)) if lines[i].strip()]
            skip = 2 if heading.startswith("Chapter XVI.") else 3
            rest = lines[nonblank[skip]:] if len(nonblank) > skip else []
            for i, l in enumerate(rest[:4]):              # (the first saying's number, in the margin)
                if number and re.match(rf"^\W{{0,3}}{number}[.,]\s", l):
                    rest[i] = re.sub(rf"^\W{{0,3}}{number}[.,]\s*", "", l)
                    break
            out += [("blank",) if not l.strip() else ("line", l) for l in rest]
            continue
        out += [("blank",) if not l.strip() else ("line", l) for l in lines]
    return out


def build() -> dict:
    words = dictionary()
    books = {1: {}, 2: {}}
    state = {"book": 1, "expected": 1, "depth": 0, "number": None, "paras": [], "lines": []}

    def end_paragraph():
        if state["lines"]:
            state["paras"].append(" ".join(state["lines"]))
            state["lines"] = []

    def finish():
        end_paragraph()
        if state["number"] is not None:
            text = "\n".join(t for t in (split_runs(tidy(p), words) for p in state["paras"]) if t)
            books[state["book"]][str(state["number"])] = text
        state.update(number=None, paras=[], lines=[], depth=0)

    def add(line: str, starts: bool = False):
        if not starts and re.match(r"^\W{0,2}(O\.\s?M\.|B\.|Brother\.|O[lt][dp] Man\.)\s", line) and state["lines"]:
            end_paragraph()
        line, state["depth"] = quotes(line, state["depth"], starts)
        if not line.strip():
            return
        lines = state["lines"]
        broken = re.search(r"([A-Za-z]+)-$", lines[-1]) if lines else None
        if broken and re.match(r"[a-z]", line):
            whole = broken.group(1) + re.match(r"[a-z]+", line).group(0)
            head, tail = broken.group(1).lower(), re.match(r"[a-z]+", line).group(0)
            compound = head in words and tail in words and len(head) > 1 and whole.lower() not in words
            lines[-1] = (lines[-1] if compound else lines[-1][:-1]) + line   # ("self-denial", but "contemplateth")
            return
        lines.append(line)

    evs = events(all_pages())
    numbers = numbering(evs)
    for i, event in enumerate(evs):
        if event[0] == "blank":
            pass                                          # (Budge starts a paragraph only with a saying or a speaker)
        elif event[0] == "chapter":
            _, book, heading, number, opening = event
            finish()
            if book != state["book"]:
                state.update(book=book, expected=1)
            number = number or state["expected"]
            if number != state["expected"]:
                raise SystemExit(f"{heading[:30]}: opens at saying {number}, expected {state['expected']}")
            state.update(number=number, expected=number + 1, paras=[f"*{heading}*"])
            add(opening, starts=True)
        else:
            line = event[1]
            if i in numbers:
                finish()
                state.update(number=numbers[i], expected=numbers[i] + 1)
                opener = candidate(line)
                add(line[opener[0].end():] if opener else re.sub(r"^\S+\s+", "", line), starts=True)
            elif state["number"] is not None:
                add(line)
    finish()
    return books


def main() -> None:
    books = build()
    for b, sayings in books.items():
        nums = sorted(map(int, sayings))
        missing = sorted(set(range(1, nums[-1] + 1)) - set(nums))
        print(f"Book {b}: sayings {nums[0]}-{nums[-1]}, {len(nums)} found, missing {missing}")
    payload = {"source": "The Paradise of the Holy Fathers, Vol. II, trans. E. A. Wallis Budge (Chatto & Windus, 1907); "
                         "read from the University of Toronto's scan",
               "books": {"Sayings of the Desert Fathers": {str(b): s for b, s in books.items()}}}
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()

