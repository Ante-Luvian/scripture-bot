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
          {"Enchiridion": book})


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
                                    bhagavad_gita, upanishads, meditations, enchiridion, imitation_of_christ,
                                    rule_of_benedict, divine_comedy, hesiod, nt_apocrypha, secrets_of_enoch,
                                    forgotten_books_of_eden, sutta_nipata, gospel_of_thomas, enuma_elish)}

if __name__ == "__main__":
    for name in sys.argv[1:] or BUILDERS:
        BUILDERS[name]()
