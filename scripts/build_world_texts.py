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


_UA = {"User-Agent": "ScriptureBotCorpusBuilder/1.0 (Discord bot; low-volume one-off text import)"}


def wikisource(title: str) -> str:
    """A Wikisource page's wikitext (cached; politely spaced requests)."""
    import time
    import urllib.parse
    CACHE.mkdir(exist_ok=True)
    path = CACHE / ("ws_" + re.sub(r"[^\w]+", "_", title)[:150] + ".txt")
    if not path.exists():
        url = ("https://en.wikisource.org/w/api.php?action=parse&prop=wikitext&format=json&redirects=1&page="
               + urllib.parse.quote(title))
        for attempt in range(6):
            try:
                req = urllib.request.Request(url, headers=_UA)
                data = json.loads(urllib.request.urlopen(req, timeout=60).read())
                break
            except urllib.error.HTTPError as e:
                if e.code != 429 or attempt == 5:
                    raise
                time.sleep(int(e.headers.get("Retry-After") or 0) or 15 * (attempt + 1))
        if "error" in data:
            raise SystemExit(f"Wikisource: {title}: {data['error'].get('info')}")
        path.write_text(data["parse"]["wikitext"]["*"], encoding="utf-8")
        time.sleep(3)
    return path.read_text(encoding="utf-8")


def wiki_plain(w: str) -> str:
    """Wikitext to plain text: no footnotes, templates, links or markup."""
    import html
    w = re.sub(r"<ref[^>/]*/>", "", w)
    w = re.sub(r"<ref[^>]*>.*?</ref>", "", w, flags=re.S)
    for _ in range(3):                                   # nested templates
        w = re.sub(r"\{\{[^{}]*\}\}", "", w)
    w = re.sub(r"\[\[(?:Category|File|Image):[^\]]*\]\]", "", w)
    w = re.sub(r"\[\[(?:[^|\]]*\|)?([^\]]*)\]\]", r"\1", w)
    w = re.sub(r"\[https?://\S+ ([^\]]*)\]", r"\1", w)
    w = re.sub(r"<[^>]+>", "", w)
    w = w.replace("'''", "").replace("''", "")
    return html.unescape(w).replace("\xa0", " ")


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


def sutta_nipata():
    """Fausbøll (SBE 10 part 2, 1881), sacred-texts.com archive. Five vaggas
    of suttas; chapters are "vagga.sutta" and verses keep Fausbøll's running
    numbers, so "Sutta Nipata 2.1" is a sutta and "Sutta Nipata 221" a verse.
    His one-line summary under each title and his footnotes are left out;
    prose framing (e.g. "Thus I heard...") leads the verse after it."""
    text = sacred_text("bud/sbe10/sbe10.txt.gz")
    text = text[[m.start() for m in re.finditer(r"(?m)^I\. URAGAVAGGA\.", text)][-1]:]
    text = re.sub(r"(?m)^\s*Sacred Books of the East, Vol\. 10.*$|^\s*p\. \d+\s*$", "", text)
    text = re.sub(r"(?ms)^\[\d+\. .*?\]\s*$", "", text)                 # footnotes
    text = re.sub(r"\[\d+\]", "", text)
    vaggas = re.split(r"(?m)^([IVX]+)\. [A-Z]+VAGGA\.\s*$", text)[1:]
    book, numbers = {}, []
    for vnum, vchunk in zip(vaggas[0::2], vaggas[1::2]):
        # "1. RATANASUTTA." -- in the Parayana "2. AGITAMANAVAPUKKHA." (titles are all capitals)
        # (some have spaces: "3. KHAGGA VISANASUTTA.", "6. DHAMMAKARIYASUTTA OR KAPILASUTTA.")
        suttas = re.split(r"(?m)^\s*(\d+)\. [A-Z][A-Z\- ]+\.?\s*$", vchunk)[1:]
        for snum, schunk in zip(suttas[0::2], suttas[1::2]):
            body = schunk.strip()
            # Most suttas open with Fausbøll's one-line summary (the Parayana's don't):
            # unless the text starts straight in with verse 1, drop up to the summary's end
            if not re.match(r"\d+[.:] ", body):
                first_break = re.search(r"\n\s*\n|\s{2,}(?=1\. )", body)
                body = body[first_break.end():] if first_break else body
            body = re.sub(r"\s+", " ", body)
            verses, prose = {}, ""
            pos = 0
            for m in re.finditer(r"(?:^|\s)\d+(?:, \d+)*[.:] (.*?)\((\d+)(?:(?:, |-)(\d+))?\)", body):
                prose = body[pos:m.start()].strip()
                prose = re.sub(r"^\S+ is ended\.\s*", "", prose)          # "Pingiyamanavapukkha is ended."
                first, last = m.group(2), m.group(3)
                if numbers and int(first) <= numbers[-1] and not last:
                    # a misprint going backwards (1047 is printed "(1041)"): it is the next verse
                    print(f"  note: Sutta Nipata verse {numbers[-1] + 1} is misprinted ({first})")
                    first = str(numbers[-1] + 1)
                # verses rendered as one ("(1123, 1124)", "(1006-1008)"): kept under the first,
                # labelled like the Dhammapada's pairs
                verse = (f"(vv. {first}–{last}) " if last else "") + tidy(m.group(1))
                verses[first] = f"*{tidy(prose)}*\n{verse}" if prose else verse
                numbers += list(range(int(first), int(last or first) + 1))
                pos = m.end()
            if verses:
                book[f"{roman(vnum)}.{snum}"] = verses
    print(f"  {len(book)} suttas, {len(numbers)} verses, {numbers[0]}-{numbers[-1]}; "
          f"missing: {sorted(set(range(1, numbers[-1] + 1)) - set(numbers))[:20]}")
    expect(len(book) >= 70 and numbers[-1] >= 1140, "suttas/verses")
    write("buddhist", "sutta_nipata.json", "The Sutta-Nipata, trans. V. Fausbøll (Sacred Books of the East 10, 1881)",
          {"Sutta Nipata": book})


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
            book.setdefault(chap, {})[verse] = re.sub(r"^Revised:\s*", "", tidy(t["description"]))   # (2.48: an editor's note in the source)
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


# ── Classical ───────────────────────────────────────────────────────────────

def _drop_footnotes(chunk: str) -> str:
    """Remove indented "[A] ..." footnote blocks and their [A] / [12] markers
    (but not a translator's [supplied words])."""
    chunk = re.sub(r"(?:^ {2,}\[\w{1,3}\].*\n(?:^ {2,}\S.*\n|^\s*\n(?= {2,}\S))*)", "", chunk + "\n", flags=re.M)
    return re.sub(r"\[(?:[A-Z]|\d{1,3})\]", "", chunk)


def meditations():
    """Marcus Aurelius, trans. George Long (1862), Gutenberg #15877: twelve
    books, sections numbered as in all modern editions (the Gutenberg
    "Meditations" #2680 is Casaubon's 1634 version, numbered differently).
    Each book's first section is unnumbered in the print; footnotes dropped."""
    text = gutenberg(15877)
    text = text[:text.index("\nINDEXES.\n")]
    starts = [m for m in re.finditer(r"^([IVX]+)\.\s*$", text, flags=re.M)]
    expect([roman(m.group(1)) for m in starts] == list(range(1, 13)), f"books {[m.group(1) for m in starts]}")
    book = {}
    for i, m in enumerate(starts):
        end = starts[i + 1].start() if i + 1 < len(starts) else len(text)
        chunk = _drop_footnotes(text[m.end():end])
        sections = {}
        for p in paragraphs(chunk):
            n = re.match(r"^(\d+)\.\s+(.*)$", p)
            if n and int(n.group(1)) == len(sections) + 1:
                sections[n.group(1)] = n.group(2)
            elif not sections:
                sections["1"] = p
            else:
                last = list(sections)[-1]
                sections[last] += " " + p
        book[str(i + 1)] = {k: tidy(v) for k, v in sections.items()}
    counts = [len(book[str(i)]) for i in range(1, 13)]
    # (Long prints Book V's last two sections, 36-37, as one)
    expect(counts == [17, 17, 16, 51, 36, 59, 75, 61, 42, 38, 39, 36], f"sections per book {counts}")
    write("classical", "meditations_long.json", "Marcus Aurelius, Meditations (Thoughts), trans. George Long (1862)",
          {"Meditations": book})


def _perseus_lines(path: Path) -> dict:
    """{first line: text} from a Perseus TEI translation marked <l n="..."> every
    few lines (notes dropped)."""
    import xml.etree.ElementTree as ET
    ns = "{http://www.tei-c.org/ns/1.0}"
    root = ET.parse(path).getroot()
    for note in root.iter(f"{ns}note"):
        note.text = ""
        for child in list(note):
            note.remove(child)
    out = {}
    for l in root.iter(f"{ns}l"):
        out[l.get("n")] = tidy("".join(l.itertext()))
    return out


def hesiod():
    """Works and Days and the Shield of Heracles, trans. Hugh G. Evelyn-White
    (Loeb, 1914), from the Perseus TEI in the canonical-greekLit submodule.
    Passages run from one 5-line marker to the next, keyed "1.line" so the
    lookup treats them like Homer's (and "Works and Days 289" finds line 289)."""
    base = ROOT / "canonical-greekLit" / "data" / "tlg0020"
    out = {}
    for name, work in (("Works and Days", "tlg002"), ("Shield of Heracles", "tlg003")):
        lines = _perseus_lines(base / work / f"tlg0020.{work}.perseus-eng2.xml")
        expect(len(lines) > 50 and "1" in lines, f"{name}: {len(lines)} passages")
        passages = {}
        for n, t in lines.items():
            if not t:
                continue
            if n.isdigit():
                passages[f"1.{n}"] = {"1": t}
            elif passages:                       # an interpolated line ("169a") joins the passage before it
                last = list(passages)[-1]
                passages[last]["1"] += " " + t
        out[name] = passages
    write("classical", "hesiod_evelyn_white.json", "Hesiod, trans. Hugh G. Evelyn-White (Loeb Classical Library, 1914). Perseus Digital Library (CC-BY-SA).", out)


def enchiridion():
    """Epictetus, trans. T. W. Higginson (1865; Library of Liberal Arts ed.),
    Gutenberg #45109: his 51 chapters (the usual count is 53: his last
    chapter holds the final three). Chapters by his numbering, a verse per
    paragraph; the footnotes are left out."""
    text = gutenberg(45109)
    body = text[text.index("THE ENCHIRIDION", text.index("Wenley")):text.index("\n                               Footnotes\n")]
    parts = re.split(r"^ +([IVXL]+)(?:\[\d+\])?\s*$", body, flags=re.M)[1:]
    book = {}
    for num, chunk in zip(parts[0::2], parts[1::2]):
        chunk = re.sub(r"\[\d+\]", "", chunk)
        book[str(roman(num))] = {str(i): tidy(p) for i, p in enumerate(paragraphs(chunk), 1)}
    expect(list(book) == [str(i) for i in range(1, 52)], f"chapters {list(book)}")
    write("classical", "enchiridion_higginson.json", "Epictetus, The Enchiridion, trans. Thomas Wentworth Higginson (1865)",
          {"Enchiridion of Epictetus": book})


# ── Christian classics ──────────────────────────────────────────────────────

def imitation_of_christ():
    """Thomas à Kempis, trans. William Benham, Gutenberg #1653. Four books;
    chapters keyed "book.chapter" ("Imitation of Christ 1.1:2", like the Rig
    Veda's "10.121:9"), sections by Benham's numbers, the chapter title
    leading its first section. Scripture footnotes ("(1) John viii. 12.")
    and their markers are left out."""
    text = gutenberg(1653)
    books = list(re.finditer(r"^THE (FIRST|SECOND|THIRD|FOURTH) BOOK\s*$", text, flags=re.M))
    expect(len(books) == 4, f"{len(books)} books")
    out = {}
    for b, m in enumerate(books, 1):
        end = books[b].start() if b < 4 else len(text)
        chapters = re.split(r"^CHAPTER ([IVXL]+)\s*$", text[m.end():end], flags=re.M)[1:]
        for num, chunk in zip(chapters[0::2], chapters[1::2]):
            paras = [p for p in paragraphs(chunk) if not re.match(r"^\(\d+\)", p)]
            title, sections = paras[0], {}
            for p in paras[1:]:
                p = re.sub(r"\(\d+\)", "", p)
                n = re.match(r"^(\d+)\.\s+(.*)$", p)
                if n and int(n.group(1)) == len(sections) + 1:
                    sections[n.group(1)] = n.group(2)
                elif not sections:
                    sections["1"] = p
                else:
                    last = list(sections)[-1]
                    sections[last] += " " + p
            sections = {k: tidy(v) for k, v in sections.items()}
            sections["1"] = f"*{tidy(title)}*\n{sections['1']}"
            out[f"{b}.{roman(num)}"] = sections
    counts = [sum(1 for k in out if k.startswith(f"{b}.")) for b in range(1, 5)]
    expect(counts == [25, 12, 59, 18], f"chapters per book {counts}")
    write("medieval", "imitation_of_christ.json", "Thomas à Kempis, The Imitation of Christ, trans. William Benham",
          {"Imitation of Christ": out})


def rule_of_benedict():
    """St Benedict's Rule for Monasteries, trans. Leonard J. Doyle (1948),
    Gutenberg #50040: the Prologue (chapter 0) and 73 chapters, a verse per
    paragraph, the chapter title leading the first. The lines of dates for
    reading the Rule through three times a year ("Jan. 8—May 9—Sept. 8")
    are left out."""
    text = gutenberg(50040)
    starts = list(re.finditer(r"^ +(PROLOGUE|CHAPTER (\d+))\s*$", text, flags=re.M))
    expect([m.group(2) for m in starts] == [None] + [str(i) for i in range(1, 74)],
           f"headings {[m.group(1) for m in starts][:3]}... ({len(starts)})")
    book = {}
    for i, m in enumerate(starts):
        chunk = text[m.end():starts[i + 1].start() if i + 1 < len(starts) else len(text)]
        blocks = re.split(r"\n\s*\n", chunk.strip("\n"))
        title = tidy(" ".join(l.strip() for l in blocks[0].splitlines())) if m.group(2) else ""
        paras = [p for p in paragraphs("\n\n".join(blocks[1:] if m.group(2) else blocks))
                 if not re.match(r"^[A-Z][a-z]{2}\. \d+", p)]
        verses = {str(n): tidy(p) for n, p in enumerate(paras, 1)}
        if title:
            verses["1"] = f"*{title}*\n{verses['1']}"
        book[m.group(2) or "0"] = verses
    write("medieval", "rule_of_benedict.json", "St Benedict's Rule for Monasteries, trans. Leonard J. Doyle (1948)",
          {"Rule of Benedict": book})


def divine_comedy():
    """Dante, trans. Henry Wadsworth Longfellow (1867), Gutenberg #1004:
    line for line with the Italian, in tercets. Each tercet is stored under
    "canto.firstline" -- the same scheme as Homer -- so the lookup cites
    "Inferno 1.1" by canto and line. 34 + 33 + 33 cantos."""
    text = gutenberg(1004)
    heads = list(re.finditer(r"^(Inferno|Purgatorio|Paradiso): Canto ([IVXL]+)\s*$", text, flags=re.M))
    out: dict = {}
    for i, m in enumerate(heads):
        chunk = text[m.end():heads[i + 1].start() if i + 1 < len(heads) else len(text)]
        canto, line = roman(m.group(2)), 1
        cantica = out.setdefault(m.group(1), {})
        for s in stanzas(chunk):
            n = len(s.splitlines())
            cantica[f"{canto}.{line}"] = {"1": s}
            line += n
            if n == 1:      # every canto closes on a single line; what follows is a heading, a note or the appendix
                break
    counts = [len({k.split(".")[0] for k in out[c]}) for c in ("Inferno", "Purgatorio", "Paradiso")]
    expect(counts == [34, 33, 33], f"cantos {counts}")
    lines = {c: sum(len(v["1"].splitlines()) for v in out[c].values()) for c in out}
    expect(lines == {"Inferno": 4720, "Purgatorio": 4755, "Paradiso": 4758}, f"lines {lines}")
    write("medieval", "divine_comedy_longfellow.json", "Dante Alighieri, The Divine Comedy, trans. Henry Wadsworth Longfellow (1867)", out)


# ── New Testament Apocrypha ─────────────────────────────────────────────────

_ANF8 = "Ante-Nicene Fathers/Volume VIII/Apocrypha of the New Testament"
_ANF8_SKIP = {"Title Page", "Introductory Notice", "Translator's Introductory Notice"}


def _numbered_chapters(text: str) -> dict:
    """{chapter: {verse: paragraph}} from paragraphs opening "12. ..." (a
    chapter); unnumbered paragraphs continue the current chapter. Text with
    no numbers at all is one chapter."""
    book, chap = {}, None
    for p in paragraphs(text):
        m = re.match(r"^(\d+)\.\s+(.*)$", p)
        if m and int(m.group(1)) == (int(chap) + 1 if chap else 1):
            chap = m.group(1)
            book[chap] = {"1": tidy(m.group(2))}
        elif chap:
            book[chap][str(len(book[chap]) + 1)] = tidy(p)
        else:
            book.setdefault("0", {})[str(len(book.get("0", {})) + 1)] = tidy(p)
    if "0" in book and len(book) > 1:
        del book["0"]                                     # title lines before chapter 1
    elif "0" in book:
        book = {"1": book.pop("0")}
    return book


def nt_apocrypha():
    """The New Testament apocrypha of the Ante-Nicene Fathers, vol. VIII
    (trans. Alexander Walker, 1870; ed. Coxe, 1886), from Wikisource: the
    infancy gospels (Protevangelium of James, Pseudo-Matthew, the Infancy
    Gospel of Thomas...), the Pilate cycle (Acts of Pilate / Gospel of
    Nicodemus, Descent into Hell...), apocryphal Acts, Revelations and the
    Passing of Mary. Footnotes are left out."""
    def page_text(title):
        raw = re.sub(r"^\{\{header.*?\n\}\}", "", wikisource(title), flags=re.S)
        raw = raw.split("==Footnotes==")[0]
        return re.sub(r"^[—\-]{3,}\s*$", "", wiki_plain(raw), flags=re.M)

    def contents(title):
        raw = wikisource(title)
        return re.findall(r"^\* \[\[/([^|\]]+)\|", raw, flags=re.M) if "== Contents ==" in raw else []

    index = wikisource(_ANF8)
    titles = [t for t in re.findall(r"\[\[/([^|\]]+)\|", index) if t not in _ANF8_SKIP]
    out, flat = {}, []
    for title in titles:
        page = f"{_ANF8}/{title}"
        subpages = contents(page)
        if subpages:
            # one subpage per chapter ("Chapter 12"), or per part ("Further Acts of Thomas")
            book = {}
            for sub in subpages:
                m = re.fullmatch(r"Chapter (\d+)", sub)
                front = sub in ("Preface", "Prologue", "Introduction")
                key = m.group(1) if m else ("0" if front else str(len([k for k in book if k != "0"]) + 1))
                # the page repeats its own heading ("Chapter 1.") as its first line
                paras = [tidy(p) for p in paragraphs(page_text(f"{page}/{sub}"))
                         if not re.fullmatch(r"(Chapter \d+|Prologue|Preface)\.?", tidy(p))]
                if not m and not front:
                    paras = [f"*{sub}*"] + paras
                book[key] = {str(n): p for n, p in enumerate(paras, 1)}
        else:
            book = _numbered_chapters(page_text(page))
            if len(book) == 1:
                flat.append(title)
        out[title.replace("Barnabus", "Barnabas")] = book
    print(f"  {len(out)} texts; one chapter only (no chapter numbers in the source): {flat}")
    write("nt_apocrypha", "anf8_apocrypha.json",
          "Apocrypha of the New Testament, trans. Alexander Walker (Ante-Nicene Fathers VIII, 1886), via Wikisource", out)


# ── Pseudepigrapha ──────────────────────────────────────────────────────────

def secrets_of_enoch():
    """2 Enoch (the Slavonic Book of the Secrets of Enoch), in the Forgotten
    Books of Eden (ed. Platt, 1926; after Morfill and Charles, 1896), from
    Wikisource: "==Chapter N==" sections of numbered verses."""
    raw = wikisource("The Forgotten Books of Eden/The Book of the Secrets of Enoch")
    parts = re.split(r"^==\s*Chapter (\d+)\s*==\s*$", raw, flags=re.M)[1:]
    book = {}
    for num, chunk in zip(parts[0::2], parts[1::2]):
        verses = {}
        for p in paragraphs(wiki_plain(chunk)):
            m = re.match(r"^(\d+)\s+(.*)$", p)
            if m:
                verses[m.group(1)] = tidy(m.group(2))
            elif verses:
                last = list(verses)[-1]
                verses[last] += " " + tidy(p)
        book[num] = verses
    expect(list(book) == [str(i) for i in range(1, len(book) + 1)] and len(book) >= 60, f"{len(book)} chapters")
    write("charles", "secrets_of_enoch.json",
          "2 Enoch (The Book of the Secrets of Enoch), in The Forgotten Books of Eden, ed. Rutherford H. Platt (1926), via Wikisource",
          {"2 Enoch": book})


_ST = "https://archive.sacred-texts.com/"


def sacred_text(path: str) -> str:
    """A file from the archive of sacred-texts.com (cached); .txt.gz unpacked."""
    import gzip
    import time
    CACHE.mkdir(exist_ok=True)
    cached = CACHE / ("st_" + path.replace("/", "_"))
    if not cached.exists():
        req = urllib.request.Request(_ST + path, headers=_UA)
        cached.write_bytes(urllib.request.urlopen(req, timeout=60).read())
        time.sleep(2)
    data = cached.read_bytes()
    if path.endswith(".gz"):
        data = gzip.decompress(data)
    return data.decode("utf-8", errors="replace").replace("\r\n", "\n")


def _fbe_verses(chunk: str) -> dict:
    """Numbered verses of one Forgotten Books of Eden chapter. Platt opens a
    chapter with a one-line summary and leaves verse 1 unnumbered, so the last
    unnumbered paragraph before verse 2 is verse 1; other unnumbered
    paragraphs are his notes and are left out."""
    chunk = re.sub(r"(?m)^.*Forgotten Books of Eden, by Rutherford H\. Platt.*$|^\[p\. \d+\]$", "", chunk)
    chunk = re.sub(r"\n[ \t]*(\d+) ", r"\n\n\1 ", chunk)       # the Odes put a verse on each line
    verses, before = {}, []
    for p in paragraphs(chunk):
        m = re.match(r"^(\d+)\s+(.*)$", p)
        if m and int(m.group(1)) == len(verses) + 1:
            verses[m.group(1)] = tidy(m.group(2))
        elif m and m.group(1) == "2" and not verses and before:
            verses["1"] = tidy(before[-1])
            verses["2"] = tidy(m.group(2))
        elif not verses:
            before.append(p)
        elif p[:1].islower():
            last = list(verses)[-1]
            verses[last] += " " + tidy(p)
    return verses


def forgotten_books_of_eden():
    """From The Forgotten Books of Eden (ed. Platt, 1926; sacred-texts.com
    archive): the First and Second Books of Adam and Eve (the Ethiopic
    "Conflict of Adam and Eve with Satan", trans. Malan) and the Odes of
    Solomon (trans. Harris). Platt's own chapter summaries are left out."""
    text = sacred_text("bib/fbe/fbe.txt.gz")
    second = text.index("THE SECOND BOOK OF\n")
    enoch = text.index("THE BOOK OF THE SECRETS OF ENOCH.")
    odes_start, odes_end = text.index("ODE 1.\n"), text.index("THE LETTER OF ARISTEAS")
    out = {}
    for name, a, b, pattern, count in (
            ("First Book of Adam and Eve", text.index("THE FIRST BOOK OF\n"), second, r"(?mi)^ *CHAP(?:TER|\.)? *([IVXL]+)\b\.?.*$", 79),
            ("Second Book of Adam and Eve", second, enoch, r"(?mi)^ *CHAP(?:TER|\.)? *([IVXL]+)\b\.?.*$", 22),
            ("Odes of Solomon", odes_start, odes_end, r"(?m)^ *ODE (\d+)\.\s*$", 42)):
        parts = re.split(pattern, text[a:b])[1:]
        book = {}
        for num, chunk in zip(parts[0::2], parts[1::2]):
            n = num if num.isdigit() else str(roman(num.upper()))
            verses = _fbe_verses(chunk)
            if not verses:              # e.g. Ode 2: "(No part of this Ode has ever been identified.)"
                note = [tidy(p) for p in paragraphs(chunk) if p.startswith("(")]
                verses = {"1": note[0] if note else "(This part has not survived.)"}
            book[n] = verses
        expect(list(book) == [str(i) for i in range(1, count + 1)], f"{name}: {list(book)[:3]}... ({len(book)})")
        out[name] = book
    write("charles", "forgotten_books_of_eden.json",
          "The Forgotten Books of Eden, ed. Rutherford H. Platt (1926): Adam and Eve trans. S. C. Malan, Odes of Solomon trans. J. Rendel Harris",
          out)


def _html_text(page: str) -> str:
    import html
    page = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", "", page)
    return html.unescape(re.sub(r"<[^>]+>", "", page)).replace("\r\n", "\n")


def gospel_of_thomas():
    """The Coptic Gospel of Thomas, trans. Thomas O. Lambdin, as posted on
    sacred-texts.com (chr/thomas.htm, typed by Craig Schenk): the prologue
    (saying 0) and sayings 1-114, each a chapter, so "Gospel of Thomas 77"
    is saying 77. Lambdin's brackets for damaged text are kept."""
    text = _html_text(sacred_text("chr/thomas.htm"))
    body = text[text.index("II: Coptic Gospel of Thomas"):text.index("III: Fragments of Greek Gospel of Thomas")]
    parts = re.split(r"(?m)^ *(P|\d+)\)\s+", body)[1:]
    book = {}
    for num, chunk in zip(parts[0::2], parts[1::2]):
        book["0" if num == "P" else num] = {"1": re.sub(r"\s*-{5,}\s*$", "", tidy(chunk))}
    expect(list(book) == [str(i) for i in range(0, 115)], f"sayings {list(book)[:3]}...{list(book)[-3:]}")
    write("gnostic", "gospel_of_thomas.json", "The Gospel of Thomas (Coptic, Nag Hammadi), trans. Thomas O. Lambdin",
          {"Gospel of Thomas": book})


def enuma_elish():
    """The Enuma Elish, trans. L. W. King (The Seven Tablets of Creation,
    1902), sacred-texts.com (ane/enuma.htm). Seven tablets; each is cut into
    passages of about eight lines keyed "tablet.firstline" like Homer, so
    "Enuma Elish 4" is the fourth tablet. Lines are counted in this text
    (King marks gaps with dots, not line numbers)."""
    text = _html_text(sacred_text("ane/enuma.htm"))
    ordinals = ["FIRST", "SECOND", "THIRD", "FOURTH", "FIFTH", "SIXTH", "SEVENTH"]
    heads = list(re.finditer(r"(?m)^\s*THE (" + "|".join(ordinals) + r") TABLET\s*$", text))
    expect([m.group(1) for m in heads] == ordinals, f"tablets {[m.group(1) for m in heads]}")
    book = {}
    for i, m in enumerate(heads):
        end = heads[i + 1].start() if i + 1 < len(heads) else text.index("Sacred Texts |", m.end())
        lines = [l.strip() for l in text[m.end():end].splitlines() if l.strip()]
        tablet = ordinals.index(m.group(1)) + 1
        for start in range(0, len(lines), 8):
            book[f"{tablet}.{start + 1}"] = {"1": "\n".join(lines[start:start + 8])}
    write("ancient_near_east", "enuma_elish.json",
          "Enuma Elish, trans. L. W. King (The Seven Tablets of Creation, 1902)", {"Enuma Elish": book})


_ORDINALS = ["FIRST", "SECOND", "THIRD", "FOURTH", "FIFTH", "SIXTH", "SEVENTH", "EIGHTH", "NINTH"]


def enneads():
    """Plotinus, The Six Enneads, trans. MacKenna and Page, from the
    sacred-texts.com archive (cla/plotenn/, one page per section). Replaces
    an older plotinus.json whose numbering was scrambled (duplicated and
    misplaced treatises, a second run numbered 1.9-5.16 with empty gaps).
    Chapters are "ennead.tractate" in Porphyry's standard order (6 x 9); the
    tractate's title leads its first section."""
    import html
    index = sacred_text("cla/plotenn/index.htm")
    links = re.findall(r'(?is)<a\s+href="?(enn\d+\.htm)"?[^>]*>(.*?)</a>', index)
    book, ennead, tractate, title, seen = {}, 0, 0, "", set()
    tractate_text = ""          # a tractate with no sections (I.9) has its text on its own page

    def close_tractate():
        key = f"{ennead}.{tractate}"
        if ennead and tractate and key not in book and tractate_text:
            book[key] = {"1": f"*{title}*\n{tractate_text}" if title else tractate_text}

    for href, label in links:
        label = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", "", label))).strip()
        if href in seen:
            continue
        seen.add(href)
        m = re.fullmatch(r"THE (\w+) ENNEAD", label)
        if m:
            close_tractate()
            ennead, tractate = _ORDINALS.index(m.group(1)) + 1, 0
            continue
        m = re.fullmatch(r"(\w+) TRACTATE\.?", label)
        if m and m.group(1) in _ORDINALS:
            close_tractate()
            tractate = _ORDINALS.index(m.group(1)) + 1
            page = _html_text(sacred_text(f"cla/plotenn/{href}"))
            heading = re.search(rf"(?m)^\s*{m.group(1)} TRACTATE\.?\s*$", page)    # (the footer mentions it too)
            body = page[heading.start():] if heading else ""
            body = re.split(r"(?m)^\s*(?:Next: |Sacred Texts \|)", body)[0]
            paras = [tidy(p) for p in paragraphs(body)][1:]          # after the "NINTH TRACTATE." heading
            title = paras[0].strip('".') if paras and paras[0].isupper() else ""
            tractate_text = "\n".join(paras[1:] if title else paras)
            continue
        m = re.fullmatch(r"Section (\d+)", label)
        if not (m and ennead and tractate):
            continue
        page = _html_text(sacred_text(f"cla/plotenn/{href}"))
        start = re.search(rf"(?m)^\s*Section {m.group(1)}\s*$", page)
        body = page[start.end():] if start else page
        body = re.split(r"(?m)^\s*(?:Next: |Sacred Texts \|)", body)[0]
        paras = [tidy(p) for p in paragraphs(body)]
        if paras:
            paras[0] = re.sub(r"^\d+\.\s*", "", paras[0])
        text = "\n".join(p for p in paras if p)
        chapter = book.setdefault(f"{ennead}.{tractate}", {})
        if not chapter and title:
            text = f"*{title}*\n{text}"
        chapter[m.group(1)] = text
    close_tractate()
    book = dict(sorted(book.items(), key=lambda kv: tuple(map(int, kv[0].split(".")))))
    expect(sorted(book, key=lambda k: tuple(map(int, k.split(".")))) ==
           [f"{e}.{t}" for e in range(1, 7) for t in range(1, 10)], f"tractates {list(book)}")
    expect(all(chapter for chapter in book.values()), "an empty tractate")
    write("classical", "plotinus.json", "Plotinus, The Six Enneads, trans. Stephen MacKenna and B. S. Page", {"Enneads": book})


def enoch_missing_chapters():
    """Fills chapters the existing Book of Enoch (Charles 1917) left empty --
    3, 4, 35 and 44 are single verses, which its original build dropped --
    from the same translation on the sacred-texts.com archive (bib/boe).
    Every other chapter is left exactly as it is."""
    path = DATA / "charles" / "book_of_enoch.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    book = data["books"]["Book of Enoch"]
    empty = [c for c, v in book.items() if not v]
    text = sacred_text("bib/boe/boe.txt.gz")
    for chap in empty:
        numeral = {3: "III", 4: "IV", 35: "XXXV", 44: "XLIV"}.get(int(chap))
        m = re.search(rf"(?m)^\s*(?:CHAPTER|Chapter) {numeral}\.?\s*$(.*?)(?=^\s*(?:CHAPTER|Chapter) [IVXLC]+\.?\s*$)",
                      text, flags=re.S)
        expect(m is not None, f"Enoch chapter {chap} in the archive text")
        lines = [l for l in m.group(1).splitlines() if l.strip() and not re.match(r"\s*(\[p\. \d+\]|.*sacred-texts\.com)", l)]
        verse = tidy(" ".join(lines))
        verse = re.sub(r"^1\.\s*", "", verse)
        # match the rest of this file: Charles's editorial marks ("[[[[", "+east+") are
        # not kept, nor the next section's heading ("XXXVI. The Journey to the South.")
        verse = re.sub(r"\s+[IVXLC]+(?:-[IVXLC]+)?\. [A-Z].*$", "", verse)
        verse = re.sub(r"\[{2,}|\]{2,}|\+(\w+)\+", lambda m: m.group(1) or "", verse)
        verse = re.sub(r"\s{2,}", " ", verse).strip()
        book[chap] = {"1": verse}
        print(f"  Enoch {chap}: {verse[:70]}...")
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")   # the file's own layout


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


# ── Sacred Books of the East (sacred-texts.com .txt.gz) ─────────────────────

_ORD_WORDS = ["FIRST", "SECOND", "THIRD", "FOURTH", "FIFTH", "SIXTH", "SEVENTH", "EIGHTH", "NINTH", "TENTH",
              "ELEVENTH", "TWELFTH", "THIRTEENTH", "FOURTEENTH", "FIFTEENTH", "SIXTEENTH", "SEVENTEENTH",
              "EIGHTEENTH", "NINETEENTH"]
_TENS_ORD = {"TWENTIETH": 20, "THIRTIETH": 30, "FORTIETH": 40, "FIFTIETH": 50}
_TENS_CARD = {"TWENTY": 20, "THIRTY": 30, "FORTY": 40, "FIFTY": 50}
ORDINAL = (r"(?:(?:TWENTY|THIRTY|FORTY|FIFTY)-)?(?:" + "|".join(_ORD_WORDS) + r")|TWENTIETH|THIRTIETH|FORTIETH|FIFTIETH")


def ordinal(word: str) -> int:
    """'TWENTY-THIRD' -> 23; also a plain number or a Roman numeral."""
    word = word.upper().strip(" .,")
    if word.isdigit():
        return int(word)
    if re.fullmatch(r"[IVXLC]+", word):
        return roman(word)
    if word in _TENS_ORD:
        return _TENS_ORD[word]
    tens, _, unit = word.rpartition("-")
    return _TENS_CARD.get(tens, 0) + _ORD_WORDS.index(unit) + 1


def sbe_clean(text: str) -> str:
    """A sacred-texts.com SBE text without its page furniture: the running
    header after each page group, the footnotes gathered under it, page
    numbers, and footnote markers."""
    text = re.sub(r"(?ms)^Footnotes\s*\n.*?(?=^.*at sacred-texts\.com\s*$|\Z)", "", text)
    text = re.sub(r"(?m)^Footnotes\s*$|^\^\d+\w*:\w+.*$", "", text)             # any left ("^15:1", "^168hume:1")
    text = re.sub(r"(?m)^.*at sacred-texts\.com\s*$", "", text)
    text = re.sub(r"\[p\. [\divxlc]+\]|\s*\[\*\d+\]|\[paragraph continues\]", "", text)
    # a paragraph cut by a page break: the next "paragraph" carries on in lower case
    # (only after a lower-case word, so a heading such as "EIGHTH LECTURE," keeps its line)
    text = re.sub(r"(?:(?<=[a-z])|(?<=[a-z][,\-]))[ \t]*\n(?:[ \t]*\n)+(?=[ \t]*[a-z(])", " ", text)
    return text


def sentence_groups(paras: list, size: int = 700, longest: int = 1200) -> list:
    """Paragraphs, with any longer than `longest` cut into runs of whole
    sentences of about `size` characters (for texts with no verse numbers
    whose paragraphs run on for pages)."""
    out = []
    for p in paras:
        if len(p) <= longest:
            out.append(p)
            continue
        run = ""
        for s in re.split(r"(?:(?<=[.!?])|(?<=[.!?][\"'”’)\]]))\s+(?=[A-Z\"“‘(\[])", p):
            if run and len(run) + len(s) > size:
                out.append(run)
                run = s
            else:
                run = f"{run} {s}".strip()
        if run:
            out.append(run)
    return out


def heading_at(text: str, *lines: str, after: int = 0) -> int:
    """Where a heading starts that is these lines in a row (blank lines between
    allowed), at or after `after` -- to find a text's real start rather than
    its entry in the contents."""
    m = re.compile(r"(?m)^\s*" + r"\s*\n\s*".join(re.escape(l) for l in lines) + r"\s*$").search(text, after)
    expect(m is not None, f"heading {lines}")
    return m.start()


def last_verse(verses: dict) -> int:
    """The highest verse number in a numbered_verses result, ranges included."""
    ends = [int(m.group(1)) for v in verses.values() if (m := re.match(r"(?:\*.*\*\n)?\(vv\. \d+–(\d+)\)", v))]
    return max([int(k) for k in verses] + ends)


def numbered_verses(chunk: str, last: int = 0) -> dict:
    """Verses that end in a running "(n)" marker, the SBE's usual way of
    numbering. A marker counts only if it moves the count on (by up to 20:
    translators print several verses as one, "(7-9)", and skip numbers), so a
    stray "(2)" inside a sentence is text; an OCR'd "(t)" or "(l)" is "(1)".
    Verses printed as one are kept under the first number, labelled with the
    range, as the Dhammapada's are. Without markers, each paragraph is a verse.
    `last` continues a count that runs on from an earlier part."""
    verses, pos = {}, 0
    flat = " ".join(" ".join(l.strip() for l in p.splitlines()) for p in re.split(r"\n\s*\n", chunk))
    for m in re.finditer(r"\((?:(\d+)(?:\s*[-–,]\s*(\d+))?|([tlI]))\)", flat):
        n = 1 if m.group(3) else int(m.group(1))
        end = int(m.group(2)) if m.group(2) else None
        if last < n <= last + 20 and (end is None or n < end <= n + 20):
            body = tidy(flat[pos:m.start()])
            if body:
                verses[str(n)] = (f"(vv. {n}–{end}) " if end else "") + body
                last, pos = end or n, m.end()
    tail = tidy(flat[pos:])
    if not verses or (len(flat) / len(verses) > 2500 and len(paragraphs(chunk)) > 2 * len(verses)):
        # unnumbered, or numbered only here and there (the Kalpa Sutra's List of Sthaviras)
        return {str(i): tidy(p) for i, p in enumerate(paragraphs(chunk), 1)}
    if tail and len(tail) > 3:
        verses[list(verses)[-1]] += " " + tail
    return verses


def sbe_sections(text: str, levels: list, title_pattern: str = r"^[A-Z][A-Z0-9 ,;:'’\-()&.!?]+$",
                 verses_of=None) -> dict:
    """{chapter key: {verse: text}} from a cleaned SBE text whose headings are
    lines matching `levels` -- a list of regexes, outermost first, each with a
    group for its number (an ordinal word, digits or a Roman numeral). The
    key joins the numbers of the levels in force ("1.2.3"). An all-capitals
    line after a heading is its title and leads the section's first verse.
    Verses are numbered_verses ("...text. (3)") unless `verses_of` says
    otherwise (leading_numbered for "3. text...")."""
    counters = [0] * len(levels)
    sections, current, title, body = {}, None, "", []
    verses_of = verses_of or numbered_verses

    def flush():
        if current is not None and "".join(body).strip():
            verses = verses_of("\n".join(body))
            first = next(iter(verses))
            if title:
                verses[first] = f"*{title}*\n{verses[first]}"
            sections[current] = verses

    for line in text.splitlines():
        s = line.strip()
        hit = next(((i, m) for i, lv in enumerate(levels) if (m := re.fullmatch(lv, s))), None)
        if hit:
            flush()
            i, m = hit
            counters[i] = ordinal(m.group(1))
            for j in range(i + 1, len(levels)):
                counters[j] = 0
            current = ".".join(str(c) for c in counters if c)
            # a lecture's title, given before its first lesson, leads that lesson
            title = title if not "".join(body).strip() else ""
            body = []
        elif current is not None and not "".join(body).strip() and s and re.fullmatch(title_pattern, s) \
                and len(s) < 90:
            if s.rstrip(".,") not in ("CALLED",):
                title = (title + " " if title else "") + s.rstrip(".,").title()
        elif current is not None:
            body.append(line)
    flush()
    return sections


# ── sacred-texts.com books with a page per chapter ─────────────────────────

def st_index(path: str) -> list:
    """[(page, label)] of an archive index, in order, without repeats."""
    import html
    page = sacred_text(path)
    base = path.rsplit("/", 1)[0] + "/"
    out, seen = [], set()
    for href, label in re.findall(r'(?is)<a\s+href="?([^"\s>#]+)"?[^>]*>(.*?)</a>', page):
        label = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", "", label))).strip()
        # (a page can be linked twice -- once as a highlight, "Mithra", once in the contents)
        if href.startswith(("http", "/", "..")) or (href, label) in seen or not href.endswith(".htm") or "index" in href:
            continue
        seen.add((href, label))
        out.append((base + href, label))
    return out


def st_page(path: str) -> str:
    """A chapter page's text: from after the site's navigation to its
    footnotes, without page numbers or the plain-number footnote markers the
    HTML pages leave in the text ("did converse 1, whom")."""
    text = _html_text(sacred_text(path))
    nav = list(re.finditer(r"(?m)^\s*Next\s*$", text[:3000]))
    text = text[nav[0].end() if nav else 0:]
    text = re.split(r"(?m)^\s*(?:Footnotes|Next: .*|Sacred Texts \|.*)\s*$", text)[0]
    text = re.sub(r"(?m)^\s*p\. [\divxlc]+\s*$|\[paragraph continues\]", "", text)
    text = re.sub(r"(?m)^[^\n]*?\bat sacred-texts\.com\s*", "", text)              # the running header
    text = re.sub(r"\s+p\. \d+(?=\s|$)", "", text)                                 # a page number left inline
    text = text.replace("\xa0", " ")
    text = re.sub(r"(?:(?<=[^\W\d_])|(?<=[,;:!?'’”)\]]))[ \t]+\d{1,2}(?=[\s,.;:!?'’”)]|$)", "", text)
    text = re.sub(r"\n[ \t]*\n(?=[ \t]*[a-z])", "\n", text)        # a paragraph cut by a page number
    return text


def leading_numbered(text: str) -> dict:
    """Verses that start with their number ("12. ..." or "12 (40). ..."), as
    the Avesta and Pahlavi texts print them; a number counts only if it moves
    the count on, and what comes before verse 1 (the translator's summary)
    is left out. Without numbers, a verse per paragraph."""
    lines = [l.strip() for l in text.splitlines() if l.strip()]       # the HTML puts each paragraph on a line
    flat = "\n".join(lines)
    # a number opens a verse at the start of a line, or after a sentence ends
    # (West runs the Bundahishn's verses on: "...goodness. 2. As revealed...")
    starts, last = [], -1
    for m in re.finditer(r"(^|\n|[.!?'’”)\]][ \t]+)(\d+)(?:\s*\(\d+\))?\s*[.:][ \t]+(?=\S)", flat):
        n = int(m.group(2))
        # the first number can be anything (Milinda's similes run on from 11, 21...)
        if (last == -1 and n <= 500) or (last < n <= last + 10 and n > 0):
            starts.append((n, m.start(2), m.end()))
            last = n
    verses = {}
    for i, (n, at, body) in enumerate(starts):
        end = starts[i + 1][1] if i + 1 < len(starts) else len(flat)
        verse = "\n".join(tidy(l) for l in flat[body:end].split("\n") if l.strip())
        verses[str(n)] = re.sub(r"\n(?=[a-z])", " ", verse)              # a sentence carried over a page break
    if not verses:
        verses = {str(i): tidy(p) for i, p in enumerate(lines, 1)}
    return {k: v for k, v in verses.items() if v}


# ── Chinese, more ───────────────────────────────────────────────────────────

def zhuangzi():
    """The Zhuangzi (Kwang-dze), trans. James Legge (SBE 39-40, 1891),
    sacred-texts.com archive: 33 books, Legge's paragraph numbers as verses,
    each book's title leading its first. (The site's index calls Book XXIX
    "XXIV", so the books are numbered in order.)"""
    pages = [(p, l) for p, l in st_index("tao/sbe39/index.htm") if re.match(r"Book [IVXL]+[:.] .*, or ", l)]
    pages += [(p, l) for p, l in st_index("tao/sbe40/index.htm") if re.match(r"Book [IVXL]+\. ", l)]
    book = {}
    for n, (page, label) in enumerate(pages, 1):
        verses = leading_numbered(st_page(page))
        title = re.search(r"or '(.*?)'?\.?'?$", label)
        title = title.group(1).strip(".'") if title else re.sub(r"^Book [IVXL]+[.:]\s*", "", label).strip(". ")
        verses["1"] = f"*{title}*\n{verses['1']}"
        book[str(n)] = verses
    expect(len(book) == 33, f"{len(book)} books")
    write("chinese", "zhuangzi.json", "The Zhuangzi (Writings of Kwang-dze), trans. James Legge (Sacred Books of the East 39-40, 1891)",
          {"Zhuangzi": book})


def mencius():
    """The Works of Mencius, trans. James Legge, sacred-texts.com archive
    (cfu/menc, 28 pages: each of the 7 books' two parts spans two pages).
    Cited the usual way, book.part.chapter -- "Mencius 1.1.1" is Book I,
    Part A (King Hui of Liang I), chapter 1 -- with Legge's paragraph
    numbers as verses. Chapters are set apart by a wider gap (Legge leaves a
    one-paragraph chapter unnumbered).

    This copy has lost some chapters (mostly one-sentence sayings) and a few
    opening paragraphs, but each lost chapter left two more blank lines in
    the gap (four lines between chapters, six where one is missing, eight
    for two...), so counting them keeps every chapter on its standard
    number; the lost ones are simply absent, and checked against the
    standard count of chapters in each part."""
    book, page_last = {}, {}
    for page in range(1, 29):
        b, part = (page - 1) // 4 + 1, (page - 1) // 2 % 2 + 1
        text = _html_text(sacred_text(f"cfu/menc/menc{page:02d}.htm"))
        text = text[text.index("\n", text.index(f"Mencius Chapter {page}")):]
        text = re.split(r"(?m)^\s*(?:Next: |Sacred Texts \|)", text)[0]
        chapter = page_last.get((b, part), 0)
        # paragraphs are two lines apart, verse quotations three, chapters four or more
        # (a chapter after a quotation can be three apart, but then opens "1." or "Mencius said")
        pieces = re.split(r"(\n(?:[ \t]*\n){3,}|\n(?:[ \t]*\n){2}(?=[ \t]*(?:1\. |Mencius said)))", "\n" + text)
        gap = 4
        for i, chunk in enumerate(pieces):
            if i % 2:
                gap = chunk.count("\n")
                continue
            paras = paragraphs(chunk)
            if not paras:
                continue
            chapter += 1 + max(0, gap - 4) // 2 if chapter or gap > 4 else 1
            verses = book.setdefault(f"{b}.{part}.{chapter}", {})
            for p in paras:
                p = re.sub(r"\b0 (?=[a-z])", "O ", p)                     # OCR: "0 prince" for "O prince"
                m = re.match(r"^(\d+)\.\s+(.*)$", p)
                last = max(map(int, verses), default=0)
                if m and last < int(m.group(1)) <= last + 3:
                    verses[m.group(1)] = tidy(m.group(2))
                elif verses:
                    verses[str(last)] += "\n" + tidy(p)
                else:
                    verses["1"] = tidy(p)
        page_last[(b, part)] = chapter
    standard = {(1, 1): 7, (1, 2): 16, (2, 1): 9, (2, 2): 14, (3, 1): 5, (3, 2): 10, (4, 1): 28, (4, 2): 33,
                (5, 1): 9, (5, 2): 9, (6, 1): 20, (6, 2): 16, (7, 1): 46, (7, 2): 38}
    print(f"  Mencius: last chapter of each part {page_last} (standard {standard}); "
          f"{len(book)} of {sum(standard.values())} chapters")
    # 6B's last chapter (16, "There are many arts in teaching") is lost at the end of its page,
    # where no gap shows it -- checked by hand: 6B.1-15 open where they should
    expect(all(page_last[k] == v - (k == (6, 2)) for k, v in standard.items()), "chapter numbering")
    write("chinese", "mencius.json", "The Works of Mencius, trans. James Legge (The Chinese Classics, 1861-1895)", {"Mencius": book})


def great_learning_and_mean():
    """The Great Learning and the Doctrine of the Mean, trans. James Legge
    (1893), sacred-texts.com archive (cfu/conf2.htm, conf3.htm). This copy
    has lost the traditional chapter numbers, so each is kept by paragraph:
    the Great Learning's classic text is chapter 1 and the commentary of
    the philosopher Tsang chapter 2; the Doctrine of the Mean is chapter 1."""
    out = {}
    for path, name in (("cfu/conf2.htm", "Great Learning"), ("cfu/conf3.htm", "Doctrine of the Mean")):
        text = _html_text(sacred_text(path))
        text = text[text.index("translated by James Legge"):text.rindex("THE END")]
        text = text[text.index("\n"):]
        parts = re.split(r"(?m)^\s*COMMENTARY OF THE PHILOSOPHER TSANG\s*$", text)
        book = {}
        for c, part in enumerate(parts, 1):
            paras = [tidy(p) for p in re.split(r"\n(?=[ \t]{2,}\S)|\n\s*\n", part) if p.strip()]
            book[str(c)] = {str(i): p for i, p in enumerate(paras, 1)}
        out[name] = book
    print(f"  {[(k, [len(c) for c in v.values()]) for k, v in out.items()]}")
    write("chinese", "great_learning_mean.json", "The Great Learning and The Doctrine of the Mean, trans. James Legge (1893)", out)


# ── Hindu, more ─────────────────────────────────────────────────────────────

def upanishads_muller():
    """The principal Upanishads in F. Max Müller's translation (SBE 1, 1879;
    SBE 15, 1884), sacred-texts.com archive -- those not already here in
    Paramananda's (the Isa, Katha and Kena: Müller's Vagasaneyi and
    Talavakara are those two). Chapters follow each Upanishad's own
    divisions (Chandogya 1.1 = first prapathaka, first khanda; Brihadaranyaka
    4.3 = fourth adhyaya, third brahmana...), verses Müller's numbers."""
    sbe01 = sbe_clean(sacred_text("hin/sbe01/sbe01.txt.gz"))
    sbe15 = sbe_clean(sacred_text("hin/sbe15/sbe15.txt.gz"))
    O = rf"({ORDINAL})"
    plan = [  # (book, text, heading, first division, levels, the heading that ends it)
        ("Chandogya Upanishad", sbe01, "KHANDOGYA-UPANISHAD.", "FIRST PRAPATHAKA.",
         [rf"{O} PRAPATHAKA\.?", rf"{O} KHANDA\.?"], "TALAVAKARA"),
        ("Aitareya Aranyaka", sbe01, "AITAREYA-ARANYAKA.", "FIRST ARANYAKA.",
         [rf"{O} ARANYAKA\.?", rf"{O} ADHYAYA\.?", rf"{O} KHANDA\.?"], "KAUSHITAKI-BRAHMANA-UPANISHAD."),
        ("Kaushitaki Upanishad", sbe01, "KAUSHITAKI-BRAHMANA-UPANISHAD.", "KAUSHITAKI-UPANISHAD.",
         [rf"{O} ADHYAYA\.?"], "VAGASANEYI-SAMHITA-UPANISHAD,"),
        ("Mundaka Upanishad", sbe15, "MUNDAKA-UPANISHAD.", "FIRST MUNDAKA.",
         [rf"{O} MUNDAKA\.?", rf"{O} KHANDA\.?"], "TAITTIRIYAKA-UPANISHAD."),
        ("Taittiriya Upanishad", sbe15, "TAITTIRIYAKA-UPANISHAD.", "FIRST VALLI,",
         [rf"{O} VALLI[.,]?", rf"{O} ANUVAKA\.?"], "BRIHADARANYAKA-UPANISHAD."),
        ("Brihadaranyaka Upanishad", sbe15, "BRIHADARANYAKA-UPANISHAD.", "FIRST ADHYAYA.",
         [rf"{O} ADHYAYA\.?", rf"{O} BRAHMANA\.?"], "SVETASVATARA-UPANISHAD."),
        ("Svetasvatara Upanishad", sbe15, "SVETASVATARA-UPANISHAD.", "FIRST ADHYAYA.",
         [rf"{O} ADHYAYA\.?"], "PRASNA-UPANISHAD."),
        ("Prasna Upanishad", sbe15, "PRASNA-UPANISHAD.", "FIRST QUESTION.",
         [rf"{O} QUESTION\.?"], "Maitrayana-Brahmana-Upanishad"),
        ("Maitrayana Upanishad", sbe15, "Maitrayana-Brahmana-Upanishad", "FIRST PRAPATHAKA.",
         [rf"{O} PRAPATHAKA\.?"], None),
    ]
    out = {}
    for name, text, heading, first, levels, end in plan:
        a = heading_at(text, heading, first)
        b = heading_at(text, end, after=a + 10) if end else len(text)
        out[name] = sbe_sections(text[a:b], levels, verses_of=leading_numbered)
    counts = {k: (len(v), sum(map(len, v.values()))) for k, v in out.items()}
    print(f"  Upanishads (chapters, verses): {counts}")
    expect(all(c > 0 and v >= 2 * c for c, v in counts.values()), "an Upanishad with too few verses")
    write("dharmic", "upanishads_muller.json", "The Upanishads, trans. F. Max Müller (Sacred Books of the East 1 and 15, 1879-1884)", out)


def laws_of_manu():
    """The Laws of Manu (Manusmriti), trans. Georg Bühler (SBE 25, 1886),
    sacred-texts.com archive (hin/manu/manu01-12.htm): 12 chapters, verses
    by Bühler's numbers."""
    book = {}
    for n in range(1, 13):
        book[str(n)] = leading_numbered(st_page(f"hin/manu/manu{n:02d}.htm"))
    counts = [len(v) for v in book.values()]
    print(f"  Manu verses per chapter: {counts}")
    expect(sum(counts) >= 2600, f"{sum(counts)} verses")      # the Manusmriti has 2,684
    write("dharmic", "laws_of_manu.json", "The Laws of Manu, trans. Georg Bühler (Sacred Books of the East 25, 1886)",
          {"Laws of Manu": book})


def yoga_sutras():
    """The Yoga Sutras of Patanjali, trans. BonGiovanni ("The Threads of
    Union"), sacred-texts.com archive (hin/yogasutr.htm): four chapters, the
    sutras numbered as everywhere ("Yoga Sutras 1.2")."""
    text = _html_text(sacred_text("hin/yogasutr.htm"))
    book = {}
    for m in re.finditer(r"(?ms)^\s*([1-4])\.(\d+)\.?\s+(.*?)(?=^\s*[1-4]\.\d+\.?\s|^\s*(?:Sacred Texts|Next:)|\Z)", text):
        book.setdefault(m.group(1), {})[m.group(2)] = tidy(m.group(3))
    counts = [len(v) for v in book.values()]
    expect(counts == [51, 55, 56, 34] or sum(counts) >= 190, f"sutras per chapter {counts}")
    print(f"  Yoga Sutras: {counts}")
    write("dharmic", "yoga_sutras.json", "The Yoga Sutras of Patanjali, trans. BonGiovanni (The Threads of Union)",
          {"Yoga Sutras": book})


# ── Zoroastrian ─────────────────────────────────────────────────────────────

def avesta():
    """The Zend-Avesta and Pahlavi texts of the Sacred Books of the East,
    sacred-texts.com archive (a page per chapter): the Vendidad (22
    fargards) and the Yashts (the 21 hymns) trans. James Darmesteter (SBE 4,
    1880; SBE 23, 1883), the Yasna (72 chapters) trans. L. H. Mills (SBE 31,
    1887), and the Bundahishn, the Zoroastrian account of creation, trans.
    E. W. West (SBE 5, 1880). Verses by the translators' numbers; their
    introductions to each chapter and their footnotes are left out."""
    out = {}

    def collect(index, pattern, name, numbering=lambda m: str(roman(m.group(1)))):
        book = {}
        for page, label in st_index(index):
            m = re.fullmatch(pattern, label)
            if m:
                key = numbering(m)
                if key in book:
                    continue
                verses = leading_numbered(st_page(page))
                if verses:
                    book[key] = verses
        out[name] = dict(sorted(book.items(), key=lambda kv: int(kv[0])))

    collect("zor/sbe04/index.htm", r"Fargard ([IVXL]+)\b.*", "Vendidad")
    collect("zor/sbe23/index.htm", r"([IVXL]+)\. .*Yast\b.*", "Yashts")
    collect("zor/sbe31/index.htm", r"Yasna ([IVXL]+)\b.*", "Yasna")
    collect("zor/sbe05/index.htm", r"Chapter ([IVXL]+)\b.*", "Bundahishn")
    counts = {k: len(v) for k, v in out.items()}
    print(f"  chapters: {counts}")
    expect(counts["Vendidad"] == 22 and counts["Yashts"] >= 19 and counts["Yasna"] >= 70 and counts["Bundahishn"] >= 30,
           f"chapters {counts}")
    write("zoroastrian", "avesta.json",
          "The Zend-Avesta (Vendidad, Yashts trans. James Darmesteter; Yasna trans. L. H. Mills) and the Bundahishn "
          "(trans. E. W. West), Sacred Books of the East 4, 5, 23, 31 (1880-1887)", out)


# ── Jain ────────────────────────────────────────────────────────────────────

def jaina_sutras():
    """The Jaina Sutras, trans. Hermann Jacobi (SBE 22, 1884; SBE 45, 1895),
    sacred-texts.com archive: the Akaranga Sutra (book.lecture.lesson; the
    second book's last lectures have no lessons), the Kalpa Sutra (its parts,
    with Jacobi's running section numbers as verses), the Uttaradhyayana (36
    lectures) and the Sutrakritanga (book.lecture.chapter). Verses are the
    "(n)" numbers Jacobi prints; his footnotes are left out."""
    sbe22 = sbe_clean(sacred_text("jai/sbe22/sbe22.txt.gz"))
    sbe45 = sbe_clean(sacred_text("jai/sbe45/sbe45.txt.gz"))
    out = {}

    aka = sbe22[heading_at(sbe22, "AKARANGA SUTRA.", "FIRST BOOK.", "FIRST LECTURE,"):heading_at(sbe22, "THE KALPA SUTRA")]
    out["Akaranga Sutra"] = sbe_sections(aka, [rf"({ORDINAL}) BOOK\.?", rf"({ORDINAL}) LECTURE[.,]?",
                                               rf"({ORDINAL}) LESSON\.?"])
    kalpa = sbe22[heading_at(sbe22, "LIFE OF MAHAVIRA."):sbe22.rindex("INDEX")]
    parts = ["LIFE OF MAHAVIRA", "LIFE OF PARSVA", "LIFE OF ARISHTANEMI", "EPOCHS OF THE INTERMEDIATE TIRTHAKARAS",
             "LIFE OF RISHABHA", "LIST OF THE STHAVIRAS", "RULES FOR YATIS"]
    book, last = {}, 0
    for i, name in enumerate(parts):
        a = kalpa.index(name + ".") if name + "." in kalpa else kalpa.index(name)
        b = kalpa.index(parts[i + 1]) if i + 1 < len(parts) else len(kalpa)
        chunk = re.sub(r"(?m)^\s*(End of the .*|Life of Mahavira, Lecture \d+|" + re.escape(name) + r"\.?)\s*$", "", kalpa[a:b])
        # the Lives number their sections straight through; the List and the Rules start again
        verses = numbered_verses(chunk, 0 if name in ("RULES FOR YATIS", "LIST OF THE STHAVIRAS") else last)
        last = last_verse(verses)
        first = next(iter(verses))
        verses[first] = f"*{name.title()}*\n{verses[first]}"
        book[str(i + 1)] = verses
    out["Kalpa Sutra"] = book

    utt_at = heading_at(sbe45, "UTTARADHYAYANA.", "FIRST LECTURE.")
    sut_at = heading_at(sbe45, "SUTRAKRITANGA.", "FIRST BOOK.", after=utt_at)
    utt = sbe45[utt_at:sut_at]
    out["Uttaradhyayana Sutra"] = sbe_sections(utt, [rf"({ORDINAL}) LECTURE\.?"])
    sut = sbe45[sut_at:sbe45.rindex("INDEX")]
    out["Sutrakritanga"] = sbe_sections(sut, [rf"({ORDINAL}) BOOK\.?", rf"({ORDINAL}) LECTURE[.,]?",
                                              rf"({ORDINAL}) CHAPTER\.?"])
    counts = {k: len(v) for k, v in out.items()}
    print(f"  chapters: {counts}")
    expect(counts["Uttaradhyayana Sutra"] == 36, f"Uttaradhyayana {counts}")
    write("jain", "jaina_sutras.json", "The Jaina Sutras, trans. Hermann Jacobi (Sacred Books of the East 22 and 45, 1884-1895)", out)


# ── Shinto ──────────────────────────────────────────────────────────────────

def kojiki():
    """The Kojiki, trans. Basil Hall Chamberlain (1882; 1919 ed.), sacred-texts.com
    archive. Chamberlain's 180 sections are the chapters, a verse per
    paragraph, the section's title leading the first. The headings' numbers
    have OCR slips (two "XLI"s, a "SECT. ."), so sections are numbered in
    order and the count checked. The appendix and footnotes are left out."""
    text = sbe_clean(sacred_text("shi/kj/kj.txt.gz"))
    text = text[heading_at(text, "RECORDS OF ANCIENT MATTERS"):]
    text = text[:re.search(r"(?m)^\s*I\. \(SECT\. ", text).start()]
    text = re.sub(r"\s\[\d+\](?=\s)", " ", text)                           # the original's page numbers
    # "[SECT. XIX.--...]", and two with "SECT" lost: "[ XVIII.--...]", "[. CXLI.--...]"
    heads = list(re.finditer(r"(?m)^\s*(?:\[?SECT\b|\[[\s.]*[IVXLC]+\.--)[^\n]*$", text))
    book = {}
    for i, m in enumerate(heads, 1):
        title = re.sub(r"^\s*\[?(?:SECT)?[\s.]*[IVXLC ]*[.:]?\s*[-—.:]*\s*|\]?\s*$", "", m.group(0)).strip()
        body = text[m.end():heads[i].start() if i < len(heads) else len(text)]
        paras = [tidy(p) for p in paragraphs(body) if not re.fullmatch(r"(VOL\.|VOLUME) [IVX]+\.?.*|\[?END.*", p.strip())]
        verses = {str(n): p for n, p in enumerate(sentence_groups([p for p in paras if p]), 1)}
        if verses:
            verses["1"] = f"*{title.rstrip('.').title()}*\n{verses['1']}"
        book[str(i)] = verses
    expect(len(book) == 180, f"{len(book)} sections")
    write("shinto", "kojiki.json", "The Kojiki (Records of Ancient Matters), trans. Basil Hall Chamberlain (1882)",
          {"Kojiki": book})


def nihongi():
    """The Nihongi (Chronicles of Japan), trans. W. G. Aston (1896), as given on
    the sacred-texts.com archive (shi/nihon0-3.htm): selections -- the Age of
    the Gods (Books I-II), the first Emperor Jimmu (Book III) and the Taika
    reforms (Books XXV-XXVI) -- not the whole. Chapter = Aston's book, a
    verse per paragraph."""
    book, current = {}, None
    for n in range(4):
        text = _html_text(sacred_text(f"shi/nihon{n}.htm"))
        text = text[text.index("Internet Sacred Text Archive") + 30:]           # after the page title
        text = re.split(r"(?m)^\s*(?:Next: |Sacred Texts \||END OF THE NIHONGI)", text)[0]
        text = re.sub(r"(?m)^\s*(?:Sacred-texts|Shinto|Index|Previous|Next)\s*$", "", text)
        for p in paragraphs(text):
            m = re.fullmatch(r"(?:Book|BOOK) ([IVXL]+)\.?", p.strip())
            if m:
                current = str(roman(m.group(1)))
                book.setdefault(current, {})
                continue
            if p.strip() == "THE NIHONGI" or current is None or re.fullmatch(r"[A-Z][A-Z ,.'\-]+", p.strip()):
                if current and book[current] == {}:
                    book[current]["title"] = p.strip().title()
                continue
            verses = book[current]
            verses[str(len([k for k in verses if k != "title"]) + 1)] = tidy(p)
    for key, verses in book.items():
        title = verses.pop("title", "")
        if title and "1" in verses:
            verses["1"] = f"*{title}*\n{verses['1']}"
    print(f"  Nihongi books: {[(k, len(v)) for k, v in book.items()]}")
    expect(set(book) >= {"1", "3", "25", "26"}, f"books {list(book)}")
    write("shinto", "nihongi.json", "The Nihongi (Chronicles of Japan), trans. W. G. Aston (1896): selections, as on sacred-texts.com",
          {"Nihongi": book})


# ── Mesoamerican ────────────────────────────────────────────────────────────

def popol_vuh():
    """The Popol Vuh, the K'iche' Maya book of creation, in Lewis Spence's
    rendering (The Popol Vuh, 1908; sacred-texts.com nam/pvuheng.htm): his
    retelling of its four books, with passages translated, not a
    line-by-line translation. Chapter = book, a verse per paragraph (long
    ones cut into runs of sentences); his commentary and notes after the
    fourth book are left out."""
    text = _html_text(sacred_text("nam/pvuheng.htm"))
    body = text[text.index("THE FIRST BOOK"):text.index("THE VUKUB-CAKIX MYTH")]
    parts = re.split(r"(?m)^\s*THE (FIRST|SECOND|THIRD|FOURTH) BOOK\s*$", body)[1:]
    book = {}
    for word, chunk in zip(parts[0::2], parts[1::2]):
        chunk = re.sub(r'\s11\s(\w+)\s"', r' "\1"', chunk)                 # OCR: 'term 11 hurricane "' (an opening quote)
        paras = [tidy(re.sub(r"\s?\[\d+\]", "", p)) for p in paragraphs(chunk)
                 if p.strip() and not re.fullmatch(r"[A-Z][A-Z ,.'\-:]+", p.strip())]   # sub-headings
        book[str(_ORD_WORDS.index(word) + 1)] = {str(i): p for i, p in enumerate(sentence_groups(paras), 1)}
    expect(list(book) == ["1", "2", "3", "4"], f"books {list(book)}")
    write("mesoamerican", "popol_vuh.json",
          "The Popol Vuh, retold with translated passages by Lewis Spence (The Popol Vuh, 1908)", {"Popol Vuh": book})


# ── Sikh ────────────────────────────────────────────────────────────────────

def guru_granth_sahib():
    """Shri Guru Granth Sahib, English of Sant Singh Khalsa, sacred-texts.com
    archive (skh/granth/gr01-45.htm). The site splits each section into
    "Part NNN", numbered afresh in each section but one per Ang (page) of
    the standard 1,430-page edition -- the 45 sections' parts total exactly
    1,430 -- so counting parts straight through gives the Ang, which is how
    the Granth is cited: chapter = Ang, verse = line on that Ang. The
    Japji (Jup), the morning prayer that opens it, is also kept as its own
    book, by pauri (stanza): its prologue is 0, pauris 1-38, closing salok 39."""
    angs: dict = {}
    jup = ""
    for n in range(1, 46):
        text = _html_text(sacred_text(f"skh/granth/gr{n:02d}.htm"))
        text = re.split(r"(?m)^\s*(?:Next: |Sacred Texts \|)", text[text.index("Shri Guru Granth Sahib:"):])[0]
        parts = re.split(r"(?m)^\s*Section \d+ - .*? - Part (\d+)\s*$", text)[1:]
        for num, chunk in zip(parts[0::2], parts[1::2]):
            lines = [tidy(l) for l in chunk.splitlines() if l.strip()]
            page = angs.setdefault(str(len(angs) + 1), {})
            for line in lines:
                page[str(len(page) + 1)] = line
            if n == 1:
                jup += "\n".join(lines) + "\n"
    expect(sorted(map(int, angs)) == list(range(1, 1431)), f"angs {min(map(int, angs))}-{max(map(int, angs))} ({len(angs)})")
    # The Japji: the prologue (Mool Mantar) ends at the first ||1||, then each pauri ends ||n||
    pieces = re.split(r"\|\|(\d+)\|\|\s*\n?", jup.strip())
    japji, pauri = {}, 0
    expect(pieces[1] == "1", "the Japji's prologue")
    japji["0"] = {str(i): l for i, l in enumerate(pieces[0].splitlines(), 1)}       # "One Universal Creator God...  ||1||"
    japji["0"][str(len(japji["0"]))] += " ||1||"
    for body, num in zip(pieces[2::2], pieces[3::2]):
        lines = body.strip().splitlines()
        if int(num) == pauri + 1:
            pauri += 1
            japji[num] = {str(i): l for i, l in enumerate(lines, 1)}
            japji[num][str(len(lines))] += f" ||{num}||"
        else:                                       # the closing Shalok ("Air is the Guru...") ends ||1||
            japji["39"] = {str(i): l for i, l in enumerate(lines, 1)}
            japji["39"][str(len(lines))] += " ||1||"
            break
    expect(pauri == 38 and "39" in japji, f"Japji: {pauri} pauris")
    write("sikh", "guru_granth_sahib.json",
          "Shri Guru Granth Sahib, English translation by Sant Singh Khalsa (sacred-texts.com)",
          {"Guru Granth Sahib": angs, "Japji": japji})


# ── Buddhist, more ──────────────────────────────────────────────────────────

def lotus_sutra():
    """The Saddharma-pundarika (Lotus Sutra), trans. H. Kern (SBE 21, 1884),
    sacred-texts.com archive: 27 chapters (Kern's numbering, from the
    Sanskrit), a verse per paragraph of prose or numbered stanza (the
    stanza's number is kept in its text, as it restarts in each group), the
    chapter's title leading the first."""
    book = {}
    for n in range(1, 28):
        text = st_page(f"bud/lotus/lot{n:02d}.htm")
        lines = [l.strip() for l in text.splitlines() if l.strip()]
        start = next(i for i, l in enumerate(lines) if re.fullmatch(r"CHAPTER [IVXL]+\.?", l))
        title, body = lines[start + 1].title(), lines[start + 2:]
        verses = {str(i): tidy(l) for i, l in enumerate(body, 1)}
        verses["1"] = f"*{title}*\n{verses['1']}"
        book[str(n)] = verses
    write("buddhist", "lotus_sutra.json", "The Saddharma-pundarika or Lotus of the True Law, trans. H. Kern (Sacred Books of the East 21, 1884)",
          {"Lotus Sutra": book})


def milinda():
    """The Questions of King Milinda, trans. T. W. Rhys Davids (SBE 35-36,
    1890-1894), sacred-texts.com archive. Chapters are "book.chapter" from
    each page's own heading ("BOOK II. CHAPTER 2."; a book with no chapters
    is chapter 1), verses Rhys Davids's paragraph numbers; the bracketed page
    numbers of the Pali edition are left out."""
    book = {}
    for index in ("bud/sbe35/index.htm", "bud/sbe36/index.htm"):
        for page, label in st_index(index):
            if not re.match(r"(Book [IVX]+|Chapter \d+)", label):
                continue
            # (the heading from the raw page: st_page's footnote-marker cleaning would take "CHAPTER 2"'s 2)
            raw = _html_text(sacred_text(page))
            head = re.search(r"(?m)^\s*BOOK ([IVX]+)\b", raw)
            if not head:
                continue
            chap = re.search(r"CHAPTER (\d+)", raw[head.start():head.start() + 400])
            key = f"{roman(head.group(1))}.{chap.group(1) if chap else 1}"
            text = re.sub(r"\[\d+\]\s*", "", st_page(page))
            text = text[re.search(r"(?m)^\s*BOOK [IVX]+\b.*$", text).end():]
            text = re.sub(r"^\s*(?:[A-Z][A-Z\-ÂÎÛÑ' .,]+\n)*\s*CHAPTER \d*\.?", "", text)      # the rest of the heading
            # (a chapter can run over two pages: II.3 continues at its verse 15)
            book.setdefault(key, {}).update(leading_numbered(text))
    book = dict(sorted(book.items(), key=lambda kv: tuple(map(int, kv[0].split(".")))))
    print(f"  Milinda: {list(book)}")
    expect(len(book) >= 20, f"{len(book)} chapters")
    write("buddhist", "milinda.json", "The Questions of King Milinda, trans. T. W. Rhys Davids (Sacred Books of the East 35-36, 1890-1894)",
          {"Questions of King Milinda": book})


def jataka():
    """The Jataka, or Stories of the Buddha's Former Births, ed. E. B. Cowell
    (1895-1907), sacred-texts.com archive (six volumes, bud/j1-j6): all 547
    tales, each a chapter by its number, a verse per paragraph (long ones
    cut into runs of sentences), the tale's name leading the first."""
    book = {}
    for vol in range(1, 7):
        text = sbe_clean(sacred_text(f"bud/j{vol}/j{vol}.txt.gz"))
        text = re.sub(r"\[j\d+\]|\[\d+\.?\]|^_{5,}\s*$", "", text, flags=re.M)
        heads = list(re.finditer(r"(?m)^\s*No\. (\d+)\.\s*$", text))
        for i, m in enumerate(heads):
            body = text[m.end():heads[i + 1].start() if i + 1 < len(heads) else len(text)]
            if i + 1 == len(heads):
                body = re.split(r"(?m)^\s*(?:INDEX|Index)\s*$", body)[0]
            paras = [tidy(p) for p in paragraphs(body)]
            title = paras.pop(0).rstrip(".").title() if paras and re.fullmatch(r"[A-Z][A-Z\-' ]+\.?", paras[0]) else ""
            verses = {str(n): p for n, p in enumerate(sentence_groups([p for p in paras if p]), 1)}
            if title and verses:
                verses["1"] = f"*{title}*\n{verses['1']}"
            book.setdefault(m.group(1), verses)
    numbers = sorted(map(int, book))
    print(f"  Jataka: {len(book)} tales, {numbers[0]}-{numbers[-1]}; missing {sorted(set(range(1, 548)) - set(numbers))[:20]}")
    expect(len(book) >= 540, f"{len(book)} tales")
    write("buddhist", "jataka.json", "The Jataka, or Stories of the Buddha's Former Births, ed. E. B. Cowell (1895-1907)",
          {"Jataka": dict(sorted(book.items(), key=lambda kv: int(kv[0])))})


def masnavi():
    """Rumi's Masnavi, abridged and trans. E. H. Whinfield (1898),
    sacred-texts.com archive (isl/masnavi/msn.txt.gz). Chapters are
    "book.story" (the prologue 0, an epilogue after the last story);
    Whinfield's prose summary of each story, after its title, is the first
    verse, then the couplets in runs of eight lines (his sub-headings, such
    as "Description of Love.", can't be told from a couplet line ending in a
    full stop, so they stay in the run). His notes are left out."""
    text = sacred_text("isl/masnavi/msn.txt.gz")
    text = re.split(r"(?m)^\s*Note on Apocryphal Supplements", text)[0]       # Whinfield's appendix
    text = re.sub(r"(?m)^.*at sacred-texts\.com\s*$", "", text)
    text = re.sub(r"(?m)^[ \t]*\*NOTES:[ \t]*\n(?:[ \t]*\d+\..*\n|[ \t]*\n)*", "", text)
    # note numbers: "Adam, l" / "Pure One! 2" at a line's end, "willing,1 we" inside it
    # (an OCR'd "l" for "1" only after a space: "Adam, l" -- never the end of "Soul")
    text = re.sub(r"(?:(?<=[^\W\d_])|(?<=[,;:!?'’\"]))(?:[ \t]?\d{1,2}|[ \t]l)(?=[ \t]*$|[ \t]*[,.;:])", "", text, flags=re.M)
    text = re.sub(r"(?<=[,;:.!?'’\"])[ \t]?\d{1,2}(?=\s)", "", text)       # (this text has no verse numbers)
    text = re.sub(r"(?:(?<=[^\W\d_])|(?<=\)))[ \t]\d{1,2}(?=[ \t]+\S)", "", text)   # mid-line: "the Dragon's tail 2 dulls"
    text = re.sub(r"\bA11\b", "All", text)                                     # OCR
    books = re.split(r"(?m)^\s*Book ([IVX]+)\.\s*$", text)[1:]
    out = {}
    for num, chunk in zip(books[0::2], books[1::2]):
        b = roman(num)
        parts = re.split(r"(?m)^\s*(PROLOGUE\.|STORY ([IVXL]+)\.|Epilogue to Book [IVX]+\.)\s*$", chunk)
        stories = len(re.findall(r"(?m)^\s*STORY [IVXL]+\.\s*$", chunk))
        for i in range(1, len(parts), 3):
            head, story_num, body = parts[i], parts[i + 1], parts[i + 2]
            key = "0" if head.startswith("PROLOGUE") else str(roman(story_num)) if story_num else str(stories + 1)
            lines = [l.strip() for l in body.splitlines() if l.strip()]
            if not lines:
                continue
            verses, run = [], []
            title = lines.pop(0) if story_num else head.rstrip(".").title()
            for line in lines:
                prose = len(line) > 160
                if prose or len(run) >= 8:
                    if run:
                        verses.append("\n".join(run))
                    run = []
                if prose:
                    verses.append(tidy(line))
                else:
                    run.append(line)
            if run:
                verses.append("\n".join(run))
            book = {str(n): v for n, v in enumerate(verses, 1)}
            if book:
                book["1"] = f"*{title.rstrip('.')}*\n{book['1']}"
            out[f"{b}.{key}"] = book
    counts = [sum(1 for k in out if k.startswith(f"{b}.")) for b in range(1, 7)]
    print(f"  Masnavi stories per book: {counts}")
    expect(len(counts) == 6 and min(counts) >= 8, f"stories {counts}")
    write("sufi", "masnavi_whinfield.json", "Rumi, The Masnavi, abridged and trans. E. H. Whinfield (1898)", {"Masnavi": out})


def rubaiyat():
    """The Rubaiyat of Omar Khayyam, trans. Edward FitzGerald, as on the
    sacred-texts.com archive (isl/khayyam.txt), one chapter of numbered
    quatrains. (The file says 1859 but runs past that edition's 75.)"""
    text = sacred_text("isl/khayyam.txt")
    parts = re.split(r"(?m)^([IVXLC]+)[.:]\s*$", text)[1:]
    book = {str(roman(n)): "\n".join(l.strip() for l in q.strip().splitlines() if l.strip())
            for n, q in zip(parts[0::2], parts[1::2])}
    expect(list(book) == [str(i) for i in range(1, len(book) + 1)] and len(book) >= 75,
           f"quatrains {list(book)[:3]}...{list(book)[-3:]}")
    write("sufi", "rubaiyat_fitzgerald.json", "The Rubaiyat of Omar Khayyam, trans. Edward FitzGerald",
          {"Rubaiyat": {"1": book}})


# ── European myth ──────────────────────────────────────────────────────────

def kalevala():
    """The Kalevala, the Finnish national epic, trans. John Martin Crawford
    (1888), sacred-texts.com archive (neu/kveng/kv.txt.gz): the proem
    (chapter 0) and 50 runes, in runs of eight lines (the poem has no
    stanzas), the rune's title leading the first."""
    text = re.sub(r"(?m)^.*at sacred-texts\.com\s*$|\[p\. \d+\]", "", sacred_text("neu/kveng/kv.txt.gz"))
    text = text.replace("whirlpoo4", "whirlpool,").replace("adjuste4", "adjusted,")      # OCR
    heads = [m for m in re.finditer(r"(?m)^\s*(PROEM|RUNE ([IVXL]+))\.?(.*)$", text)]
    body_heads, seen = [], set()
    for m in reversed(heads):                       # the last of each is the text's own (the first, the contents)
        key = "0" if m.group(1) == "PROEM" else str(roman(m.group(2)))
        if key not in seen:
            seen.add(key)
            body_heads.append((key, m))
    body_heads = sorted(body_heads, key=lambda km: km[1].start())
    book = {}
    for i, (key, m) in enumerate(body_heads):
        end = body_heads[i + 1][1].start() if i + 1 < len(body_heads) else len(text)
        lines = [l.strip() for l in text[m.end():end].splitlines() if l.strip()]
        lines = [l for l in lines if not re.fullmatch(r"(?:END OF|THE END|Footnotes|\^.*|Next:.*)", l)]
        title = m.group(3).strip(" .").title() if m.group(3).strip(" .") else ("Proem" if key == "0" else "")
        if lines and not title and re.fullmatch(r"[A-Z][A-Z' ,\-]+\.?", lines[0]):
            title = lines.pop(0).strip(".").title()
        runs = ["\n".join(lines[j:j + 8]) for j in range(0, len(lines), 8)]
        verses = {str(n): r for n, r in enumerate(runs, 1)}
        if verses and title:
            verses["1"] = f"*{title}*\n{verses['1']}"
        book[key] = verses
    expect(sorted(map(int, book)) == list(range(0, 51)), f"runes {sorted(map(int, book))[:3]}... ({len(book)})")
    write("finnish", "kalevala.json", "The Kalevala, trans. John Martin Crawford (1888)",
          {"Kalevala": dict(sorted(book.items(), key=lambda kv: int(kv[0])))})


def mabinogion():
    """The Mabinogion, the medieval Welsh tales, trans. Lady Charlotte Guest
    (1838-1849), Project Gutenberg #5160: the twelve tales (Kilhwch and
    Olwen with its Twrch Trwyth) and Taliesin, each a chapter in the
    order of this edition, a verse per paragraph; her notes are left out."""
    text = gutenberg(5160)
    text = text[:text.rindex("FOOTNOTES")]
    names = ["THE LADY OF THE FOUNTAIN", "PEREDUR THE SON OF EVRAWC", "GERAINT THE SON OF ERBIN", "KILHWCH AND OLWEN",
             "THE DREAM OF RHONABWY", "PWYLL PRINCE OF DYVED", "BRANWEN THE DAUGHTER OF LLYR", "MANAWYDDAN THE SON OF LLYR",
             "MATH THE SON OF MATHONWY", "THE DREAM OF MAXEN WLEDIG", "HERE IS THE STORY OF LLUDD AND LLEVELYS", "TALIESIN"]
    starts = [heading_at(text, n, after=15000) for n in names]
    expect(starts == sorted(starts), "tale order")
    book = {}
    for i, (name, a) in enumerate(zip(names, starts)):
        body = text[a + len(name) + 3:starts[i + 1] if i + 1 < len(starts) else len(text)]
        body = re.sub(r"\[\d+\]|\[Footnote.*?\]", "", body)
        paras = [tidy(p) for p in paragraphs(body)
                 if not re.fullmatch(r"[A-Z][A-Z ,'\-]+|[*\s]+", p.strip())]       # headings, "* * * * *"
        # a stray capital printed as its own paragraph ("N" before "In times past") is dropped
        joined = [p for i, p in enumerate(paras)
                  if not (len(p) <= 2 and p.isalpha() and i + 1 < len(paras) and paras[i + 1][:1].isupper())]
        verses = {str(n): p for n, p in enumerate(sentence_groups(joined), 1)}
        verses["1"] = f"*{name.replace('HERE IS THE STORY OF ', '').title()}*\n{verses['1']}"
        book[str(i + 1)] = verses
    write("celtic", "mabinogion.json", "The Mabinogion, trans. Lady Charlotte Guest (1849)", {"Mabinogion": book})


# ── Christian mystics ──────────────────────────────────────────────────────

def cloud_of_unknowing():
    """The Cloud of Unknowing, ed. Evelyn Underhill (1922), sacred-texts.com
    archive (chr/cou): 75 chapters, a verse per paragraph, the chapter's
    own heading (its summary) leading the first."""
    book = {}
    for page, label in st_index("chr/cou/index.htm"):
        m = re.match(r"Chapter (\d+): (.*)", label)
        if not m or m.group(1) in book:
            continue
        text = re.sub(r"\[[a-z]+-p\d+\]", "", st_page(page))
        lines = [tidy(l) for l in text.splitlines() if l.strip()]
        # the page opens "HERE BEGINNETH THE FIRST CHAPTER" and repeats its summary
        start = next((i for i, l in enumerate(lines) if re.fullmatch(r"(HERE BEGINNETH )?(THE )?[A-Z\-]+ CHAPTER\.?", l)), -1)
        lines = lines[start + 2:] if start >= 0 else lines
        verses = {str(i): l for i, l in enumerate(lines, 1)}
        if verses:
            verses["1"] = f"*{m.group(2).strip(' .')}*\n{verses['1']}"
        book[m.group(1)] = verses
    expect(sorted(map(int, book)) == list(range(1, 76)), f"chapters ({len(book)})")
    write("medieval", "cloud_of_unknowing.json", "The Cloud of Unknowing, ed. Evelyn Underhill (1922)",
          {"Cloud of Unknowing": dict(sorted(book.items(), key=lambda kv: int(kv[0])))})


def julian_of_norwich():
    """Julian of Norwich, Revelations of Divine Love, ed. Grace Warrack
    (1901), Project Gutenberg #52958: 86 chapters, a verse per paragraph;
    the editor's summary under each chapter number and her notes are left
    out."""
    text = gutenberg(52958)
    text = text[:text.rindex("CHAPTER LXXXVI")] + text[text.rindex("CHAPTER LXXXVI"):].split("\nINDEX")[0]
    heads = list(re.finditer(r"(?m)^\s*CHAPTER ([IVXL]+)\s*$", text))
    book = {}
    for i, m in enumerate(heads):
        body = text[m.end():heads[i + 1].start() if i + 1 < len(heads) else len(text)]
        body = re.split(r"(?m)^\s*(?:FOOTNOTES?:?|\[Footnote)", body)[0]
        body = re.sub(r"(?m)^\s*THE [A-Z\-]+ REVELATION_?\s*$", "", body)
        body = re.split(r"(?m)^\s*GLOSSARY\s*$", body)[0]                  # after the last chapter
        # the editor's notes follow each chapter, the first opening "[1] ..." (a note can run
        # to several paragraphs): the chapter ends there; then the markers go from the text
        paras = paragraphs(body)
        first_note = next((k for k, p in enumerate(paras) if re.match(r"\[\d+\]", p.strip())), len(paras))
        paras = [tidy(re.sub(r"\[\d+\]", "", p)) for p in paras[:first_note]]
        if paras and paras[0].startswith(('"', "“")) and len(paras) > 1:
            paras = paras[1:]                             # the editor's summary, in quotation marks
        book[str(roman(m.group(1)))] = {str(n): p for n, p in enumerate(paras, 1) if p}
    expect(sorted(map(int, book)) == list(range(1, 87)), f"chapters ({len(book)})")
    write("medieval", "julian_revelations.json", "Julian of Norwich, Revelations of Divine Love, ed. Grace Warrack (1901)",
          {"Revelations of Divine Love": book})


def brother_lawrence():
    """Brother Lawrence, The Practice of the Presence of God, Project
    Gutenberg #5657: chapter 1 the four Conversations (recorded by Joseph de
    Beaufort), chapter 2 the Letters, a verse per conversation or letter
    paragraph -- "1.2" is the second conversation."""
    text = gutenberg(5657)
    convs = text[text.index("First Conversation:"):text.index("\nLetters")]
    letters = text[text.index("\nLetters"):]
    book = {}
    for c, (part, word) in enumerate(((convs, "Conversation"), (letters, "Letter")), 1):
        pieces = re.split(rf"(?m)^(\w+ {word}):\s*", part)[1:]
        for n, (head, body) in enumerate(zip(pieces[0::2], pieces[1::2]), 1):
            paras = [tidy(p) for p in paragraphs(body)]
            verses = {str(i): p for i, p in enumerate(paras, 1) if p}
            verses["1"] = f"*{head}*\n{verses['1']}"
            book[f"{c}.{n}"] = verses
    print(f"  Brother Lawrence: {list(book)}")
    expect(sum(1 for k in book if k.startswith("1.")) == 4, "four conversations")
    write("medieval", "practice_of_presence.json", "Brother Lawrence, The Practice of the Presence of God (Project Gutenberg)",
          {"Practice of the Presence of God": book})


# ── Swedenborg ──────────────────────────────────────────────────────────────

# sacred-texts folder: the book's name here (its usual English title)
SWEDENBORG = {
    "ac": "Arcana Coelestia", "hh": "Heaven and Hell", "dlw": "Divine Love and Wisdom",
    "dpr": "Divine Providence", "tcr": "True Christian Religion", "cjl": "Conjugial Love",
    "ar": "Apocalypse Revealed", "ae": "Apocalypse Explained", "eiu": "Earths in the Universe",
    "tnj": "The New Jerusalem and its Heavenly Doctrine", "lj": "The Last Judgment",
    "ljc": "The Last Judgment Continued", "ljp": "The Last Judgment (Posthumous)", "wh": "The White Horse",
    "dld": "Doctrine of the Lord", "dss": "Doctrine of the Sacred Scripture", "dol": "Doctrine of Life",
    "dof": "Doctrine of Faith", "be": "Brief Exposition of the Doctrine of the New Church",
    "isb": "Interaction of the Soul and Body", "cor": "Coronis", "inc": "Invitation to the New Church",
    "sd": "Spiritual Diary", "ath": "On the Athanasian Creed", "ddm": "De Domino", "pps": "Prophets and Psalms",
    "dvr": "De Verbo", "dl": "Divine Love", "dw": "Divine Wisdom", "cha": "Doctrine of Charity",
    "dcj": "De Conjugio", "gts": "God the Saviour", "can": "Canons of the New Church",
}


def _swedenborg_page(html_page: str) -> dict:
    """{section: [paragraphs]} from one sacred-texts page, where each numbered section
    starts at a margin note: <span class="margnote">...<a name="51.">51.</a>...</span>."""
    import html as html_lib
    start = re.search(r'(?i)<span class="margnote">', html_page)
    body = html_page[start.start():] if start else ""
    footnotes = re.search(r"(?i)<h\d[^>]*>\s*Footnotes\s*</h\d>", body)      # (the translator's notes, at the end)
    body = body[:footnotes.start()] if footnotes else body
    for footer in ("<nav", "<script"):                       # the page's navigation bar and scripts
        end = body.lower().find(footer)
        body = body[:end] if end > 0 else body
    parts = re.split(r'(?is)<span class="margnote">(.*?)</span>', body)
    out = {}
    for marker, chunk in zip(parts[1::2], parts[2::2]):
        num = html_lib.unescape(re.sub(r"<[^>]+>", "", marker)).strip().rstrip(".").strip()
        if not num:
            continue
        chunk = re.sub(r"(?is)<h\d[^>]*>.*?</h\d>", "", chunk)          # chapter headings between sections
        chunk = re.sub(r"(?is)<a[^>]*>\s*(?:Next|Previous):.*?</a>", "", chunk)
        paras = []
        for p in re.split(r"(?i)<p[^>]*>|<br\s*/?>\s*<br\s*/?>", chunk):
            text = tidy(html_lib.unescape(re.sub(r"<[^>]+>", " ", p)))
            if text and not re.fullmatch(r"\[p\. [\divxlc]+\]", text):
                paras.append(text)
        if paras:
            out.setdefault(num, []).extend(paras)
    return out


def swedenborg():
    """The theological works of Emanuel Swedenborg (sacred-texts.com archive, the Standard
    Edition translations), each cited as Swedenborg is: by his own section numbers."""
    import html as html_lib
    books, sources = {}, {}
    for folder, title in SWEDENBORG.items():
        index = sacred_text(f"swd/{folder}/index.htm")
        pages = []
        for href, _ in re.findall(r'(?is)<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', index):
            if "/" not in href and href.endswith(".htm") and href != "index.htm" and href not in pages:
                pages.append(href)
        book = {}
        translator = ""
        for page in pages:
            html_page = sacred_text(f"swd/{folder}/{page}")
            if not translator:
                m = re.search(r"tr\. by ([^<\[]+?)\s*\[(\d{4}(?:-\d+)?)\]", html_page)
                translator = f"{m.group(1).strip()} ({m.group(2)})" if m else ""
            for num, paras in _swedenborg_page(html_page).items():
                book.setdefault(num, {})
                for p in paras:
                    book[num][str(len(book[num]) + 1)] = p
        expect(len(book) >= 5, f"{title}: {len(book)} sections")
        books[title] = book
        sources[title] = f"Emanuel Swedenborg, {title}" + (f", trans. {translator}" if translator else "") + " (sacred-texts.com)"
        print(f"  {title}: {len(book)} sections, {sum(len(v) for v in book.values())} paragraphs ({translator})")
    path = DATA / "medieval" / "swedenborg.json"
    path.write_text(json.dumps({"source": "Emanuel Swedenborg, the theological works (sacred-texts.com)",
                                "book_sources": sources, "books": books}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"wrote {path.relative_to(ROOT)}: {len(books)} works, {path.stat().st_size // 1_000_000} MB")


# ── John Milton ─────────────────────────────────────────────────────────────

def _milton_book(chunk: str, label: str) -> dict:
    """{line number: line} for one book of a poem in Beeching's edition: the verse is indented,
    and every tenth line is numbered in the margin (checked against our own count). The book's
    prose Argument becomes line 0; the editor's notes on variant readings, after the verse, are
    left out. A line of verse shared by two speakers, printed on two lines, is one line."""
    argument, lines = [], {}
    for raw in chunk.split("\n"):
        line = raw.rstrip()
        text = line.strip()
        if re.match(r"(?i)^(notes?:|the end(?: of the \w+ book)?\.?$)", text):   # (not "The end of all thy Ofspring")
            if lines:                                    # the notes after the verse: the book is over
                break
            continue                                     # (a note on the Argument)
        if not text or text.upper() in ("THE ARGUMENT.", "THE ARGUMENT"):
            continue
        if not line.startswith("  "):                    # unindented: the Argument's prose
            if not lines:
                argument.append(text)
            continue
        if not lines and argument and not re.search(r"[a-z]", text):
            continue
        m = re.match(r"^(.*?\S)\s{3,}(\d+)$", text)
        verse = (m.group(1) if m else text).replace("_", "")
        if lines and (line.startswith(" " * 10) or verse.startswith("Man:  That still lessens")):
            lines[str(len(lines))] += "  " + verse        # (Samson 1564: one line, three speakers)
            continue
        n = len(lines) + 1
        if m and int(m.group(2)) != n:                  # a misprinted margin number (the totals are checked)
            print(f"    {label}: the margin says {m.group(2)}, the count {n} ({verse[:40]})")
        lines[str(n)] = verse
    out = {"0": "*The Argument*\n" + " ".join(argument)} if argument else {}
    out.update(lines)
    return out


def milton():
    """John Milton's Paradise Lost (1674), Paradise Regain'd and Samson Agonistes (1671), in
    H. C. Beeching's edition of Milton's own spelling (Project Gutenberg #1745), a line to a
    verse: "Paradise Lost 1:1-26" is the invocation; Samson Agonistes is all one chapter."""
    t = gutenberg(1745)
    pl, pr = t.index("\nPARADISE LOST.\n", 100_000), t.index("\nPARADISE REGAIN'D.\n", 700_000)
    sa = t.index("\nSAMSON AGONISTES\n", pr)
    end = t.index("\nAPPENDIX.\n", sa)
    books = {}
    for name, a, b, pattern, count in (("Paradise Lost", pl, pr, r"\n(BOOK [IVX]+)\.\n", 12),
                                       ("Paradise Regained", pr, sa, r"\n(The (?:First|Second|Third|Fourth) Book)\.\n", 4)):
        parts = re.split(pattern, t[a:b])[1:]
        expect(len(parts) // 2 == count, f"{name}: {len(parts) // 2} books")
        books[name] = {str(i): _milton_book(chunk, f"{name} {i}") for i, chunk in enumerate(parts[1::2], 1)}
    books["Samson Agonistes"] = {"1": _milton_book(t[t.index("  Sam:  A little onward", sa):end], "Samson")}
    # the line counts of this edition. Books V, XI and XII are 904, 897 and 648 here, not 907, 901 and 649,
    # as Beeching prints the 1667 text where 1674 added lines (giving those in his notes); his own margin
    # numbers, checked line by line, agree with every count in Paradise Lost
    lengths = {"Paradise Lost": [798, 1055, 742, 1015, 904, 912, 640, 653, 1189, 1104, 897, 648],
               "Paradise Regained": [502, 486, 443, 639], "Samson Agonistes": [1758]}
    for name, book in books.items():
        got = [max(int(k) for k in book[str(i)]) for i in range(1, len(lengths[name]) + 1)]
        expect(got == lengths[name], f"{name}: {got}")
    sources = {"Paradise Lost": "John Milton, Paradise Lost (1674), ed. H. C. Beeching (Project Gutenberg)",
               "Paradise Regained": "John Milton, Paradise Regain'd (1671), ed. H. C. Beeching (Project Gutenberg)",
               "Samson Agonistes": "John Milton, Samson Agonistes (1671), ed. H. C. Beeching (Project Gutenberg)"}
    path = DATA / "medieval" / "milton.json"
    path.write_text(json.dumps({"source": "John Milton, ed. H. C. Beeching (Project Gutenberg)", "book_sources": sources,
                                "books": books}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"wrote {path.relative_to(ROOT)}: " + ", ".join(f"{n} ({sum(len(c) for c in b.values())} lines)"
                                                         for n, b in books.items()))


# ── William Blake ───────────────────────────────────────────────────────────

def _stanzas(block: str) -> list:
    """Blank-line separated stanzas, keeping each line of verse (prose paragraphs are joined)."""
    out = []
    for p in re.split(r"\n\s*\n", block.strip("\n")):
        lines = [l.strip().replace("_", "") for l in p.splitlines() if l.strip()]
        if not lines:
            continue
        verse = len(lines) > 1 and max(map(len, lines)) < 62
        out.append(("\n" if verse else " ").join(lines))
    return out


def _titled(block: str, title_re: str) -> list:
    """[(title, stanzas)] for a run of poems or sections, each headed by a capitalised title."""
    parts = re.split(title_re, block)
    return [(t.strip(), _stanzas(body)) for t, body in zip(parts[1::2], parts[2::2]) if _stanzas(body)]


def _numbered(poems: list) -> dict:
    book = {}
    for n, (title, stanzas) in enumerate(poems, 1):
        verses = {str(i): s for i, s in enumerate(stanzas, 1)}
        words = title.lower().split()                                          # (not .title(): "Earth'S")
        name = " ".join(w if i and w in ("of", "and", "the", "a", "in", "to") else w.capitalize() for i, w in enumerate(words))
        verses["1"] = f"*{name}*\n{verses['1']}"
        book[str(n)] = verses
    return book


def blake():
    """William Blake from Project Gutenberg: the Songs of Innocence and of Experience (#1934,
    by poem and stanza), The Marriage of Heaven and Hell (#45315, by section and paragraph:
    the Proverbs of Hell one to a verse) and The Book of Thel (#574, by part)."""
    title = r"\n{3,}([A-Z][A-Z’'‘ ,.!:-]{2,})\n{2,}"
    songs = gutenberg(1934)
    start = songs.index("SONGS OF INNOCENCE\n", songs.index("CONTENTS") + 200)
    middle = songs.index("SONGS OF EXPERIENCE\n", start)
    innocence = _titled("\n\n\n" + songs[start + len("SONGS OF INNOCENCE\n"):middle], title)
    experience = _titled("\n\n\n" + songs[middle + len("SONGS OF EXPERIENCE\n"):], title)
    expect(len(innocence) == 19 and len(experience) >= 26, f"{len(innocence)} + {len(experience)} songs")
    mhh = gutenberg(45315)
    body = mhh[mhh.index("THE ARGUMENT") - 4:].split("End of Project Gutenberg")[0]
    sections = _titled("\n\n\n" + body, title)
    expect(sections[0][0] == "THE ARGUMENT" and any(t == "PROVERBS OF HELL" for t, _ in sections),
           f"Marriage sections: {[t for t, _ in sections]}")
    pg574 = gutenberg(574)
    thel = pg574[pg574.index("  THEL'S Motto"):]
    motto = _stanzas(thel[len("  THEL'S Motto"):thel.index("THE BOOK of THEL")])
    parts = re.split(r"(?m)^[ \t]*(IV|III|II|I)\.?[ \t]*$", thel[thel.index("\n  THEL\n"):])
    book_of_thel = {"0": {str(i): s for i, s in enumerate(motto, 1)}}
    for numeral, chunk in zip(parts[1::2], parts[2::2]):
        book_of_thel[str(roman(numeral))] = {str(i): s for i, s in enumerate(_stanzas(chunk), 1)}
    expect(list(book_of_thel) == ["0", "1", "2", "3", "4"], f"Thel: {list(book_of_thel)}")
    book_of_thel["0"]["1"] = "*Thel's Motto*\n" + book_of_thel["0"]["1"]
    path = DATA / "medieval" / "blake.json"
    path.write_text(json.dumps({
        "source": "William Blake (Project Gutenberg)",
        "book_sources": {"Songs of Innocence": "William Blake, Songs of Innocence (1789), Project Gutenberg",
                         "Songs of Experience": "William Blake, Songs of Experience (1794), Project Gutenberg",
                         "The Marriage of Heaven and Hell": "William Blake, The Marriage of Heaven and Hell (c. 1790), Project Gutenberg",
                         "The Book of Thel": "William Blake, The Book of Thel (1789), Project Gutenberg"},
        "books": {"Songs of Innocence": _numbered(innocence), "Songs of Experience": _numbered(experience),
                  "The Marriage of Heaven and Hell": _numbered(sections), "The Book of Thel": book_of_thel}},
        ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"wrote {path.relative_to(ROOT)}: {len(innocence)} + {len(experience)} songs, {len(sections)} sections of "
          f"the Marriage, Thel in {len(book_of_thel) - 1} parts")
    print("  ", [t for t, _ in experience])
    print("  ", [t for t, _ in sections])


BUILDERS = {f.__name__: f for f in (dhammapada, diamond_sutra, tao_te_ching, analects, i_ching, hafiz,
                                    bhagavad_gita, upanishads, meditations, enchiridion, imitation_of_christ,
                                    rule_of_benedict, divine_comedy, hesiod, nt_apocrypha, secrets_of_enoch,
                                    forgotten_books_of_eden, sutta_nipata, gospel_of_thomas, enuma_elish,
                                    enneads, enoch_missing_chapters, guru_granth_sahib,
                                    jaina_sutras, kojiki, nihongi, popol_vuh, avesta,
                                    zhuangzi, mencius, great_learning_and_mean, masnavi, rubaiyat,
                                    lotus_sutra, milinda, jataka, upanishads_muller, laws_of_manu, yoga_sutras,
                                    kalevala, mabinogion, cloud_of_unknowing, julian_of_norwich, brother_lawrence, swedenborg, blake, milton)}

if __name__ == "__main__":
    for name in sys.argv[1:] or BUILDERS:
        BUILDERS[name]()
