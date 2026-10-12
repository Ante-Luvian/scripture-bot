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


# ── Chinese ─────────────────────────────────────────────────────────────────

def _legge_numbered(paras, first_marker=r"(?:Ch\. )?"):
    """Legge's layout: a chapter opens "12. 1. text" (chapter, then its first
    paragraph number), later paragraphs "2. text"; a lone "3." is followed
    by indented verse lines. Returns {chapter: {para: text}}."""
    book, chap, verses = {}, None, None
    for p in paras:
        m = re.match(rf"^{first_marker}(\d+)\. (\d+)\.\s*(.*)$", p)
        if m and m.group(2) == "1":
            chap, verses = m.group(1), {}
            book[chap] = verses
            verses["1"] = m.group(3)
            continue
        m = re.match(r"^(\d+)\.\s*(.*)$", p)
        if m and verses is not None and int(m.group(1)) == len(verses) + 1:
            verses[m.group(1)] = m.group(2)
        elif m and verses is not None and chap and int(m.group(1)) == int(chap) + 1:
            chap, verses = m.group(1), {"1": m.group(2)}       # a chapter with no paragraph numbers
            book[chap] = verses
        elif verses:
            last = list(verses)[-1]
            verses[last] = (verses[last] + " " + p).strip()
    return {c: {v: tidy(t) for v, t in vs.items()} for c, vs in book.items()}


def tao_te_ching():
    """Legge (SBE 39, 1891). 81 chapters, cited by chapter."""
    text = gutenberg(216)
    body = text[text.index("Ch. 1. 1."):]
    paras = [p for p in paragraphs(body) if not re.match(r"^PART \d\.?$", p)]
    book = _legge_numbered(paras)
    expect(list(book) == [str(i) for i in range(1, 82)], f"chapters {list(book)[:3]}...{list(book)[-3:]} ({len(book)})")
    write("chinese", "tao_te_ching.json", "Tao Te Ching (The Tao Teh King), Laozi, trans. James Legge (Sacred Books of the East 39, 1891)",
          {"Tao Te Ching": book})


def roman(s: str) -> int:
    vals = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100}
    total = 0
    for a, b in zip(s, s[1:] + " "):
        total += -vals[a] if b != " " and vals[a] < vals[b] else vals[a]
    return total


def analects():
    """Legge (The Chinese Classics, 1861). 20 books, cited book.chapter
    ("Analects 2.4"): stored as chapter = book, verse = Legge's chapter, his
    paragraph numbers within a chapter dropped."""
    text = gutenberg(3330)
    body = text[[m.start() for m in re.finditer(r"^BOOK I\.", text, flags=re.M)][-1]:]
    books = re.split(r"^BOOK ([IVXL]+)\.[^\n]*\n", body, flags=re.M)[1:]
    out = {}
    for num, chunk in zip(books[0::2], books[1::2]):
        chunk = re.sub(r"^\s+\d+\.\s", " ", chunk, flags=re.M)        # paragraph numbers
        chaps = re.split(r"^\s*CHAP(?:TER)?\.? ([IVXL]+)\.?\s+(?:\d+\.\s)?", chunk, flags=re.M)[1:]
        printed = [roman(c) for c in chaps[0::2]]
        verses, prev = {}, 0
        for i, (n, ctext) in enumerate(zip(printed, chaps[1::2])):
            nxt = printed[i + 1] if i + 1 < len(printed) else None
            if n != prev + 1 and (nxt == prev + 2 or nxt is None and n <= prev):
                # a misprint (Book II has "XVII" twice): its neighbours fix it
                print(f"  note: Analects {roman(num)}.{prev + 1} is misprinted {n}")
                n = prev + 1
            elif n != prev + 1:
                # a chapter heading missing from the transcription: that
                # chapter's text is inside the one before
                print(f"  note: Analects {roman(num)}.{prev + 1}-{n - 1}: no heading, text is in {roman(num)}.{prev}")
            verses[str(n)] = tidy(ctext)
            prev = n
        out[str(roman(num))] = verses
    expect(list(out) == [str(i) for i in range(1, 21)], f"books {list(out)}")
    write("chinese", "analects.json", "The Analects of Confucius, trans. James Legge (The Chinese Classics, 1861)",
          {"Analects": out})


def cached_url(name: str, url: str) -> str:
    CACHE.mkdir(exist_ok=True)
    path = CACHE / name
    if not path.exists():
        path.write_bytes(urllib.request.urlopen(url, timeout=60).read())
    return path.read_text(encoding="utf-8")


_ICHING_REPO = "https://raw.githubusercontent.com/root-house-code/yijing-quiet-oracle/HEAD/src/data/"
_LINE_NAMES = {1: "first (bottom)", 2: "second", 3: "third", 4: "fourth", 5: "fifth", 6: "sixth (top)"}


def i_ching():
    """Legge (SBE 16, 1882), as digitised by the Chinese Text Project and
    assembled per hexagram by github.com/root-house-code/yijing-quiet-oracle.
    Each hexagram is a chapter: 1 = the Judgment, 2 = the Image ("Great
    Symbolism"), 3-8 = the six lines, bottom to top. The figures and names go
    to iching_hexagrams.json for !iching."""
    legge = json.loads(cached_url("iching_legge.json", _ICHING_REPO + "translations/legge.json"))["hexagrams"]
    figures = json.loads(cached_url("iching_hexagrams.json", _ICHING_REPO + "hexagrams.json"))
    expect(sorted(map(int, legge)) == list(range(1, 65)) and len(figures) == 64, "64 hexagrams")
    book, meta = {}, {}
    for h in figures:
        n = str(h["king_wen"])
        entry = legge[n]
        expect(sorted(entry["lines"]) == [str(i) for i in range(1, 7)], f"hexagram {n} lines")
        verses = {"1": "The Judgment: " + entry["judgment"], "2": "The Image: " + entry["image"]}
        for i in range(1, 7):
            verses[str(i + 2)] = entry["lines"][str(i)]
        book[n] = verses
        meta[n] = {"name": h["name_pinyin"], "chinese": h["name_zh"], "english": h["name_en"],
                   "lines": h["lines"]}          # bottom to top; 1 = unbroken (yang)
    book = dict(sorted(book.items(), key=lambda kv: int(kv[0])))
    write("chinese", "i_ching.json", "The I Ching (Yi King), trans. James Legge (Sacred Books of the East 16, 1882), via the Chinese Text Project",
          {"I Ching": book})
    (DATA / "chinese" / "iching_hexagrams.json").write_text(
        json.dumps(dict(sorted(meta.items(), key=lambda kv: int(kv[0]))), ensure_ascii=False, indent=1), encoding="utf-8")


# ── Hindu ───────────────────────────────────────────────────────────────────

_GITA_REPO = "https://raw.githubusercontent.com/gita/gita/HEAD/data/"
GITA_TRANSLATOR = "Shri Purohit Swami"


def bhagavad_gita():
    """Shri Purohit Swami (1935), verse by verse, from github.com/gita/gita.
    18 chapters, 701 verses (the count that includes 13.1 "Arjuna said...")."""
    verses = json.loads(cached_url("gita_verse.json", _GITA_REPO + "verse.json"))
    translations = json.loads(cached_url("gita_translation.json", _GITA_REPO + "translation.json"))
    where = {v["id"]: (str(v["chapter_number"]), str(v["verse_number"])) for v in verses}
    book: dict = {}
    for t in translations:
        if t["authorName"] == GITA_TRANSLATOR and t["lang"] == "english":
            chap, verse = where[t["verse_id"]]
            book.setdefault(chap, {})[verse] = tidy(t["description"])
    for chap in book:
        book[chap] = dict(sorted(book[chap].items(), key=lambda kv: int(kv[0])))
    book = dict(sorted(book.items(), key=lambda kv: int(kv[0])))
    expect(list(book) == [str(i) for i in range(1, 19)] and sum(map(len, book.values())) == 701,
           f"{len(book)} chapters, {sum(map(len, book.values()))} verses")
    write("dharmic", "bhagavad_gita.json", "The Bhagavad Gita, trans. Shri Purohit Swami (1935)", {"Bhagavad Gita": book})


def upanishads():
    """Swami Paramananda, The Upanishads (1919), Gutenberg #3283: the Isa,
    Katha and Kena. Each verse is printed first, then his commentary; only
    the verses are kept. Katha's six parts and Kena's four are its chapters."""
    text = gutenberg(3283)

    def heading(word):          # the centred section headings (the contents list isn't indented)
        return [m.start() for m in re.finditer(rf"^ +{word}\s*$", text, flags=re.M)]
    isa, katha = heading("Isa-Upanishad")[-1], heading("Katha-Upanishad")
    kena = text.index("KENA-UPANISHAD")
    bodies = {"Isa Upanishad": text[isa:katha[0]],
              "Katha Upanishad": text[katha[-1]:text.index("PEACE CHANT", katha[-1])],
              "Kena Upanishad": text[kena:]}
    out = {}
    for name, body in bodies.items():
        parts = re.split(r"^\s*Part \w+\s*$", body, flags=re.M)
        parts = parts[1:] if len(parts) > 1 else parts
        book = {}
        for c, part in enumerate(parts, 1):
            pieces = re.split(r"^ *([IVXL]+)\s*$", part, flags=re.M)[1:]
            verses = {}
            for num, chunk in zip(pieces[0::2], pieces[1::2]):
                paras = paragraphs(chunk)
                if paras:
                    verses[str(roman(num))] = tidy(paras[0])
            expect(list(verses) == [str(i) for i in range(1, len(verses) + 1)], f"{name} part {c}: {list(verses)}")
            book[str(c)] = verses
        out[name] = book
    expect([len(out["Katha Upanishad"]), len(out["Kena Upanishad"]), len(out["Isa Upanishad"]["1"])] == [6, 4, 18],
           f"parts {[len(b) for b in out.values()]}, Isa verses {len(out['Isa Upanishad']['1'])}")
    write("dharmic", "upanishads_paramananda.json", "The Upanishads, trans. Swami Paramananda (1919)", out)


# ── Persian ─────────────────────────────────────────────────────────────────

def stanzas(block: str) -> list:
    """Verse stanzas, keeping their line breaks."""
    out = []
    for s in re.split(r"\n\s*\n", block):
        lines = [l.strip() for l in s.strip().splitlines() if l.strip()]
        if lines:
            out.append("\n".join(lines).replace("_", ""))
    return out


def hafiz():
    """Gertrude Bell, Poems from the Divan of Hafiz (1897), Gutenberg
    #74883: 43 ghazals, each a chapter of stanzas. Her notes are left out."""
    text = gutenberg(74883)
    start = text.index("DIVAN OF HAFIZ", text.index("POEMS FROM THE\n", text.index("\n                                   I\n") - 400))
    body = text[start:text.index("\n                                 NOTES\n")]
    parts = re.split(r"^\s+([IVXL]+)\s*$", body, flags=re.M)[1:]
    book = {}
    for num, chunk in zip(parts[0::2], parts[1::2]):
        book[str(roman(num))] = {str(i): s for i, s in enumerate(stanzas(chunk), 1)}
    expect(list(book) == [str(i) for i in range(1, 44)], f"poems {list(book)}")
    write("sufi", "hafiz_bell.json", "Hafiz, Poems from the Divan of Hafiz, trans. Gertrude Lowthian Bell (1897)",
          {"Divan of Hafiz": book})


BUILDERS = {f.__name__: f for f in (dhammapada, diamond_sutra, tao_te_ching, analects, i_ching, hafiz,
                                    bhagavad_gita, upanishads)}

if __name__ == "__main__":
    for name in sys.argv[1:] or BUILDERS:
        BUILDERS[name]()
