"""
The rest of the Pythagorean, Platonic, Orphic, Hermetic and Chaldaean shelf: the works the library lacked, from
Gutenberg, Wikisource and tertullian.org (clean transcriptions; no raw OCR). Each step writes one file in
data/classical/; run scripts/clean_corpora.py after.

  pythagoreans   Taylor's Political Fragments of the Pythagoreans and Ethical Fragments of Hierocles (#75184)
  ocellus        Taylor's Ocellus Lucanus, with Taurus, Firmicus's Geniture of the World and Proclus's
                 Theorems on the Perpetuity of Time (#75391)
  theology       Proclus's Theology of Plato, all six books (#77393, #78800: the bot had the first volume, in
                 another's chapters), and the three treatises on providence and evil Taylor printed with it.
                 Taylor's own "seventh book" is left out: he wrote it.
  apuleius       Butler's Apologia and Florida (#26294); Adlington's Golden Ass (#1666)
  scipio         Cicero's Dream of Scipio, Peabody's (#7491)
  boethius       The Consolation of Philosophy, James's (#14328)
  celsus         Celsus's arguments against the Christians, as Taylor gathered them from Origen (#37696)

    python scripts/build_platonists.py [step ...]
"""
import html
import json
import re
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
from build_neoplatonists import _italic, expect   # noqa: E402

CACHE = ROOT / "scripts" / ".cache" / "platonists"
UA = {"User-Agent": "ScriptureBotCorpusBuilder/1.0 (Discord bot; low-volume one-off import)"}
SMALL = {"a", "an", "and", "as", "at", "by", "for", "from", "in", "into", "of", "on", "or", "the", "to", "upon",
         "with", "concerning", "towards"}


def fetch(url: str, name: str) -> str:
    path = CACHE / name
    if not path.exists():
        CACHE.mkdir(parents=True, exist_ok=True)
        for attempt in range(6):
            try:
                path.write_bytes(urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=120).read())
                break
            except urllib.error.HTTPError as e:
                if e.code != 429 or attempt == 5:
                    raise
                time.sleep(10 * (attempt + 1))
        time.sleep(1.5)
    raw = path.read_bytes()
    for enc in ("utf-8", "cp1252"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("latin-1")


def gutenberg(n: int) -> str:
    t = fetch(f"https://www.gutenberg.org/cache/epub/{n}/pg{n}-images.html", f"pg{n}.html")
    return t[t.find("*** START"):t.find("*** END")]


def between(t: str, start: str, end: "str | None" = None) -> str:
    """The stretch of t from the first match of start to the first match of end after it."""
    a = re.search(start, t)
    expect(a is not None, f"no {start!r}")
    if end is None:
        return t[a.start():]
    b = re.compile(end).search(t, a.end())
    expect(b is not None, f"no {end!r} after {start!r}")
    return t[a.start():b.start()]


# ── HTML to text ───────────────────────────────────────────────────────────

NOTE_LINK = re.compile(r'(?is)<a\b[^>]*(?:class="[^"]*fnanchor[^"]*"|href="#(?:Footnote|FN|fn|note|Note|N\d)[^"]*")[^>]*>'
                       r'\s*\[?[\w*†‡§]{1,5}\]?\s*</a>')


def text(fragment: str, lines: bool = False) -> str:
    """One paragraph or stanza as text: italics as *...*, without page numbers or note marks."""
    s = re.sub(r'(?is)<span class="pagenum"[^>]*>.*?</span>', "", fragment)
    s = NOTE_LINK.sub("", s)
    s = re.sub(r"(?is)<sup>\s*[\w*†‡§]{1,4}\s*</sup>", "", s)
    s = re.sub(r"\s+", " ", s)
    s = re.sub(r"(?is)<(i|em)>(.*?)</\1>", _italic, s)
    s = re.sub(r"(?is)<br\s*/?>", "\n" if lines else " ", s)
    s = html.unescape(re.sub(r"<[^>]+>", "", s)).replace("\xa0", " ")
    s = re.sub(r"\s*\[\d{1,3}\]", "", s)                                     # (a note number the markup didn't link)
    s = re.sub(r"\s*\[Greek: [^\]]*\]", "", s)                               # (a transcriber's transliteration)
    s = re.sub(r"(?<=[\w*”’\"')\]])\s+(?=[,;:.](?:\s|$))", "", s)            # ("earthquakes ,": where a note mark was)
    s = re.sub(r"\*\*", "", s)                                               # (italics run together: "*a**b*")
    out = "\n".join(re.sub(r"[ \t]+", " ", line).strip() for line in s.split("\n"))
    return re.sub(r"\n{2,}", "\n", out).strip()


def blocks(fragment: str, skip_class: str = r"center|titlepage|letter|caption|footnote") -> list:
    """The paragraphs and stanzas of a stretch of a Gutenberg book, in order (its notes left out)."""
    fragment = re.sub(r'(?is)<div class="(?:footnote|footnotes|fig|figcenter|figure)[^"]*">.*?</div>|<pre>.*?</pre>'
                      r'|<table.*?</table>', " ", fragment)
    out = []
    for m in re.finditer(r'(?is)<div class="stanza[^"]*">(.*?)</div>|<p\b([^>]*)>(.*?)</p>', fragment):
        if m.group(1) is not None:
            s = text(m.group(1), lines=True)
        else:
            if skip_class and re.search(rf'class="[^"]*\b(?:{skip_class})\b', m.group(2) or ""):
                continue
            s = text(m.group(3))
        if s:
            out.append(s)
    return out


def heading(fragment: str) -> str:
    """A heading in capitals -> title case: "FROM THE TREATISE OF HIPPODAMUS" -> "From the Treatise of Hippodamus"."""
    s = re.sub(r"\s*\[\d+\]\s*", " ", text(fragment).replace("*", "")).strip().rstrip(".,").strip()
    if s.upper() != s:
        return s
    words = s.lower().split()
    out = []
    for i, w in enumerate(words):
        if re.fullmatch(r"[ivxlc]+\.?", w) and w not in {"i", "civil"}:
            out.append(w.upper())
        elif i and w in SMALL and not words[i - 1].endswith("."):
            out.append(w)
        else:
            out.append(re.sub(r"[a-zæœ]", lambda c: c.group(0).upper(), w, count=1))
    return " ".join(out)


def split(fragment: str, head: str) -> list:
    """[(heading html, body html)] at each match of head (a regex whose group 1 is the heading's text)."""
    marks = list(re.finditer(head, fragment))
    return [(m.group(1), fragment[m.end():marks[i + 1].start() if i + 1 < len(marks) else len(fragment)])
            for i, m in enumerate(marks)]


def chapter(title: str, paras: list) -> dict:
    expect(bool(paras), f"no text under {title!r}")
    paras = list(paras)
    if title:
        paras[0] = f"*{title}*\n{paras[0]}"
    return {str(i + 1): p for i, p in enumerate(paras)}


def numbered(paras: list, first: int = 1) -> dict:
    """Paragraphs printed "12. Text..." -> {"12": "Text..."}; an unnumbered one goes with the one before."""
    out, current = {}, None
    for p in paras:
        m = re.match(r"(\d{1,3})\.\s+", p)
        if m:
            current = m.group(1)
            expect(current not in out, f"section {current} twice")
            out[current] = p[m.end():]
        else:
            expect(current is not None, f"text before the first section: {p[:60]!r}")
            out[current] += (" " if p[:1].islower() else "\n") + p           # (" " where a note cut a sentence)
    keys = list(map(int, out))
    expect(keys == list(range(first, first + len(keys))), f"sections out of order: {keys}")
    return out


def roman(s: str) -> int:
    vals = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100}
    s = s.upper().replace("Χ", "X")                     # (a Greek chi set for X)
    total = 0
    for i, c in enumerate(s):
        v = vals[c]
        total += -v if i + 1 < len(s) and vals[s[i + 1]] > v else v
    return total


def save(name: str, source: str, books: dict, book_sources: "dict | None" = None) -> None:
    payload = {"source": source, "books": books}
    if book_sources:
        payload["book_sources"] = book_sources
    (ROOT / "data" / "classical" / f"{name}.json").write_text(json.dumps(payload, ensure_ascii=False, indent=1),
                                                             encoding="utf-8")
    for book, chapters in books.items():
        words = sum(len(v.split()) for c in chapters.values() for v in c.values())
        print(f"  {book}: {len(chapters)} chapters, {words:,} words -> data/classical/{name}.json")


H = r'(?is)<h[1-6][^>]*>(.*?)</h[1-6]>'


# ── Wikisource ─────────────────────────────────────────────────────────────

def wikisource(title: str) -> str:
    """A Wikisource page's text as HTML, without its header box, styles, page numbers or the notes' list."""
    import urllib.parse
    url = "https://en.wikisource.org/w/api.php?" + urllib.parse.urlencode(
        {"action": "parse", "page": title, "prop": "text", "format": "json", "formatversion": 2, "redirects": 1})
    name = "ws_" + "".join(c if c.isalnum() else "_" for c in title)[-120:] + ".json"
    t = json.loads(fetch(url, name))["parse"]["text"]
    t = re.sub(r"(?is)<style.*?</style>|<link [^>]*>", "", t)
    header = re.search(r'(?is)<div class="ws-header.*?<div class="prp-pages-output', t)   # (the header box)
    t = t[header.end() - len('<div class="prp-pages-output'):] if header else t
    t = re.sub(r'(?is)<sup[^>]*class="reference"[^>]*>.*?</sup>', "", t)
    t = re.sub(r'(?is)<span><span class="pagenum.*?</span></span></span>|<span class="pagenum[^"]*"[^>]*>.*?</span>', "", t)
    t = re.sub(r'(?is)<div class="reflist.*$|<ol class="references.*$', "", t)        # (the notes, at the end)
    return t


def ws_blocks(t: str) -> list:
    """Paragraphs as verses; a poem's (or a quoted verse's) lines kept as lines."""
    t = re.sub(r'(?is)<div class="poem[^"]*">(.*?)</div>', lambda m: '<div class="stanza">' + m.group(1) + "</div>", t)
    out = []
    for m in re.finditer(r'(?is)<div class="stanza">(.*?)</div>|<p\b[^>]*>(.*?)</p>', t):
        s = text(m.group(1) if m.group(1) is not None else m.group(2), lines=True)
        if s:
            out.append(s)
    return out


# ── The Pythagoreans ───────────────────────────────────────────────────────

def pythagoreans() -> None:
    t = gutenberg(75184)
    political = between(t, r'id="POLITICAL_FRAGMENTS"', r"<h2[^>]*>\s*ETHICAL FRAGMENTS")
    hierocles = between(t, r"<h2[^>]*>\s*ETHICAL FRAGMENTS", r"<h2[^>]*>\s*FOOTNOTES")
    books = {}
    for name, part in (("Political Fragments of the Pythagoreans", political), ("Ethical Fragments of Hierocles", hierocles)):
        sections = [(heading(h), blocks(b)) for h, b in split(part, r"(?is)<h3[^>]*>(.*?)</h3>")]
        books[name] = {str(i + 1): chapter(title, paras) for i, (title, paras) in enumerate(sections)}
    expect(len(books["Political Fragments of the Pythagoreans"]) == 24 and len(books["Ethical Fragments of Hierocles"]) == 7,
           "sections")
    save("pythagorean_fragments", "trans. Thomas Taylor (1822)", books)


# ── Ocellus, Taurus, Firmicus, Proclus ─────────────────────────────────────

def ocellus() -> None:
    t = gutenberg(75391)
    universe = between(t, r'id="OCELLUS_LUCANUS"', r"<h2[^>]*>\s*OCELLUS LUCANUS ON LAWS")
    chapters = {}
    for h, body in split(universe, r"(?is)<h3>\s*(CHAP\. [IVX]+\.)\s*</h3>"):
        body = re.split(r"(?is)<h3>\s*FOOTNOTES", body)[0]
        chapters[str(len(chapters) + 1)] = chapter("", blocks(body))
    expect(len(chapters) == 4, f"Ocellus: {len(chapters)} chapters")
    def piece(start: str) -> list:
        return blocks(re.split(r"(?is)<h\d[^>]*>\s*FOOTNOTES", between(t, start, r"<h2|\*\*\* END|$"))[0])
    laws = piece(r"<h2[^>]*>\s*OCELLUS LUCANUS ON LAWS")
    taurus = piece(r"<h2[^>]*>\s*FRAGMENTS OF TAURUS")
    geniture = piece(r"<h2[^>]*>\s*MUNDI THEMA")
    theorems = []
    for h, body in split(between(t, r"<h2[^>]*>\s*SELECT THEOREMS"), r"(?is)<h3>(.*?)</h3>"):
        if "FOOTNOTES" in h:
            break
        theorems.extend(chapter(heading(h), blocks(body)).values())
    books = {"Ocellus Lucanus on the Universe": chapters,
             "Ocellus Lucanus on Laws": {"1": chapter("", laws)},
             "Taurus on the Eternity of the World": {"1": chapter("", taurus)},
             "The Geniture of the World": {"1": chapter("", geniture)},
             "Theorems on the Perpetuity of Time": {"1": chapter("", theorems)}}
    save("ocellus", "trans. Thomas Taylor (1831)", books)


# ── Proclus: the Theology of Plato, and on providence and evil ─────────────

def theology() -> None:
    # (some chapter numbers are set in Greek capitals that look like Roman ones: "CHAPTER ΧΧVῚ.")
    latin = str.maketrans({"Χ": "X", "Ι": "I", "Ῐ": "I", "Ὶ": "I"})
    v1, v2 = (re.sub(r"CHAPTER ([^<.]{1,12})\.", lambda m: f"CHAPTER {m.group(1).translate(latin)}.", gutenberg(n))
              for n in (77393, 78800))
    books = {}
    body1 = between(v1, r"<h2[^>]*>\s*<b>BOOK I\.</b>\s*</h2>", r"END OF VOL\. I")
    body2 = between(v2, r'<p class="center">BOOK VI\.</p>', r"BOOK VII\.</b>")
    marks = r'(?is)<(?:h[1-6][^>]*|p class="center[^"]*")>\s*(?:<b>)?\s*(BOOK [IVX]+\.|CHAPTER [IVXLCΧ]+\.)'
    book = None
    found = list(re.finditer(marks, body1)) + [None] + list(re.finditer(marks, body2))
    src, theology_chapters = body1, {}
    for i, m in enumerate(found):
        if m is None:
            src = body2
            continue
        nxt = found[i + 1] if i + 1 < len(found) else None
        end = nxt.start() if nxt is not None else len(src)
        label = m.group(1).upper()
        if label.startswith("BOOK"):
            book = roman(label.split()[1].rstrip("."))
            continue
        n = roman(label.split()[1].rstrip("."))
        start = src.find(">", src.find("</", m.end())) + 1                  # (past the heading's end)
        theology_chapters.setdefault(book, {})[n] = blocks(src[start:end])
    for b, chs in theology_chapters.items():
        # (Taylor's printing goes from chapter III of the third book to IX, though its contents list IV-VIII:
        # the text is whole, the headings were left out. His numbers are kept, for citations from his book.)
        want = [1, 2, 3] + list(range(9, 9 + len(chs) - 3)) if b == 3 else list(range(1, len(chs) + 1))
        expect(list(chs) == want, f"Theology book {b}: chapters {list(chs)}")
    expect(list(theology_chapters) == [1, 2, 3, 4, 5, 6], f"books {list(theology_chapters)}")
    books["Theology of Plato"] = {f"{b}.{n}": chapter("", paras) for b, chs in theology_chapters.items()
                                  for n, paras in chs.items()}
    for name, start, end in (("On Providence and Fate", r"PROVIDENCE AND FATE,", r"EXTRACTS"),
                             ("Ten Doubts Concerning Providence", r"TEN DOUBTS CONCERNING PROVIDENCE\.", r"EXTRACTS"),
                             ("On the Subsistence of Evil", r"SUBSISTENCE OF EVIL\.", r"THE END\.")):
        paras = blocks(between(v2[v2.find("ELEMENTS OF THEOLOGY."):], start, end))
        # (the extracts on evil are numbered as in the whole treatise, with gaps: their numbers stay in the text)
        books[name] = {"1": chapter("", paras) if "Evil" in name else numbered(paras)}
    save("proclus_theology", "trans. Thomas Taylor (1816)", books)


# ── Apuleius ───────────────────────────────────────────────────────────────

def apuleius() -> None:
    t = gutenberg(26294)
    apologia = between(t, r'id="THE_APOLOGIA"', r"<h2[^>]*>\s*(?:<a[^>]*></a>)?\s*THE FLORIDA")
    florida = between(t, r"<h2[^>]*>\s*(?:<a[^>]*></a>)?\s*THE FLORIDA", r"<h2[^>]*>\s*(?:<a[^>]*></a>)?\s*NOTES")
    books = {"Apologia of Apuleius": {"1": numbered(blocks(apologia))},
             "Florida": {}}
    for i, (h, b) in enumerate(split(florida, r"(?is)<h3[^>]*>(.*?)</h3>"), 1):
        paras = blocks(b)
        paras[0] = re.sub(rf"^{i}\.\s+", "", paras[0])                       # (Butler's section number)
        books["Florida"][str(i)] = chapter(heading(h), paras)
    ass = gutenberg(1666)
    ass = between(ass, r"THE FIRST BOOKE", r"\*\*\* END|$")
    chapters = {}
    for h, body in split(ass, H):
        title = heading(h)
        if not title.endswith("Chapter"):
            continue
        paras = [text(m.group(1)) for m in re.finditer(r'(?is)<p class="letter">(.*?)</p>', body)]
        paras = blocks(body)
        summary = " ".join(text(m.group(1)) for m in re.finditer(r'(?is)<p class="letter">(.*?)</p>', body))
        paras[0] = f"*{summary}*\n{paras[0]}" if summary else paras[0]          # (Adlington's argument)
        chapters[str(len(chapters) + 1)] = {str(i + 1): p for i, p in enumerate(paras)}
    expect(len(chapters) == 48, f"Golden Ass: {len(chapters)} chapters")
    books["The Golden Ass"] = chapters
    save("apuleius", "trans. H. E. Butler (1909)", books, {"The Golden Ass": "trans. William Adlington (1566)"})


# ── Cicero ─────────────────────────────────────────────────────────────────

def scipio() -> None:
    t = gutenberg(7491)
    part = t[t.rfind("SCIPIO'S DREAM."):]
    while (a := part.find("[Footnote:")) >= 0:                              # (Peabody's notes, in the text; some
        depth, i = 0, a                                                      # run over a paragraph, some hold [ ])
        while True:
            depth += {"[": 1, "]": -1}.get(part[i], 0)
            if depth == 0:
                break
            i += 1
        part = part[:a].rstrip(" ") + part[i + 1:]
    paras = blocks(part)
    save("scipios_dream", "trans. Andrew P. Peabody (1887)", {"Scipio's Dream": {"1": numbered(paras)}})


# ── Boethius ───────────────────────────────────────────────────────────────

def boethius() -> None:
    t = gutenberg(14328)
    books = {}
    for n, (h, body) in enumerate(split(between(t, r"<h2>BOOK I\.</h2>", r"<h2>EPILOGUE"),
                                        r"(?is)<h2>(?:<a[^>]*></a>)?(BOOK [IVX]+\.)</h2>"), 1):
        body = re.split(r"(?is)<h2>(?:<a[^>]*></a>)?BOOK [IVX]+\.<br>", body)[0]   # (James's summary of the next)
        verses = []
        for head, part in split(body, r"(?is)<h3>(.*?)</h3>"):
            title = re.sub(r"\s*\[[A-Z]\]", "", text(head, lines=True)).replace("\n", " ")
            paras = blocks(part)
            if title.upper().startswith("SONG"):
                paras = chapter(re.sub(r"^SONG ([IVX]+)\.\s*", r"Song \1: ", title).rstrip("."), paras).values()
            verses.extend(paras)
        books[str(n)] = {str(i + 1): v for i, v in enumerate(verses)}
    expect(len(books) == 5, f"Boethius: {len(books)} books")
    save("boethius", "trans. H. R. James (1897)", {"Consolation of Philosophy": books})


# ── Celsus ─────────────────────────────────────────────────────────────────

def celsus() -> None:
    t = gutenberg(37696)
    part = between(t, r"THE ARGUMENTS OF CELSUS AGAINST THE CHRISTIANS\s*</h2>", r"<h2>")
    paras = []
    for p in blocks(part.replace("*", "")):                                 # (the 1880 editor's note marks)
        if re.search(r"[\"”]\s*—\s*[A-Z][^\"”]*$", p):                       # (his notes: a quotation and its source)
            continue
        if paras and (p[:1].islower() or not re.search(r"[.?!:”\"’]$", paras[-1])):
            paras[-1] += " " + p                                            # (a paragraph a page break cut)
        else:
            paras.append(p)
    save("celsus", "trans. Thomas Taylor (1830)", {"Celsus Against the Christians": {"1": chapter("", paras)}})


# ── Maximus of Tyre ────────────────────────────────────────────────────────

def maximus() -> None:
    chapters = {}
    for n in range(1, 42):
        t = wikisource(f"The Dissertations of Maximus Tyrius/Chapter {n}")
        centers = [text(c) for c in re.findall(r'(?is)<div class="wst-center[^"]*">(.*?)</div>', t)]
        titles = [c for c in centers if c and not re.fullmatch(r"\*?DISSERTATION [IVXL]+\.?\*?", c, re.I)]
        expect(bool(titles), f"Maximus {n}: no title in {centers}")
        t = re.sub(r'(?is)<div class="wst-center[^"]*">.*?</div>', "", t)
        paras = [re.sub(r"(?<=\w)<< ?(?=\w)", "", p) for p in ws_blocks(t)]   # ("the lei<< sure": a typo)
        paras[0] =re.sub(r"^([A-ZÆ])([A-ZÆ]+)\b(?= [a-z])", lambda m: m.group(1) + m.group(2).lower(), paras[0])  # ("IN disputing")
        chapters[str(n)] = chapter(heading(titles[0]), paras)
    save("maximus_tyrius", "trans. Thomas Taylor (1804)", {"Dissertations of Maximus of Tyre": chapters})


# ── Julian, the rest of him (Wright's Loeb, 1913-23) ───────────────────────
# The bot has King's hymns to Helios and the Mother and Wright's Against the Galilaeans; these are the other works.
# Wright's introductions and notes are left out, and her bracketed dates on the letters.

JULIAN = {"Panegyric in Honour of Constantius": "Panegyric in honour of Constantius",
          "Panegyric in Honour of Eusebia": "Panegyric in honour of Eusebia",
          "The Heroic Deeds of Constantius": "The heroic deeds of Constantius",
          "Consolation upon the Departure of Sallust": "Consolation upon the departure of Sallust",
          "Letter to Themistius": "Letter to Themistius the philosopher",
          "Letter to the Athenians": "Letter to the senate and people of Athens",
          "Fragment of a Letter to a Priest": "Fragment of a letter to a priest",
          "To the Cynic Heracleios": "To the Cynic Heracleios",
          "To the Uneducated Cynics": "To the uneducated Cynics",
          "The Caesars": "The Caesars",
          "Misopogon": "Misopogon",
          "Epigrams of Julian": "Epigrams",
          "Fragments of Julian": "The Shorter Fragments"}


def _julian_sections(page: str) -> list:
    t = wikisource(f"The Works of the Emperor Julian/{page}")
    out = []
    for h, body in split(t, r"(?is)<h2[^>]*>(.*?)</h2>"):
        title = text(re.sub(r"(?is)<sup.*?</sup>", "", h)).replace("*", "")
        if re.match(r"(?i)introduction|foot ?notes|notes$|references", title):
            continue
        paras = []
        for p in ws_blocks(body):
            if re.fullmatch(r"\[[^\]]*\]", p):                                  # ("[359 AD from Gaul]")
                continue
            p = re.sub(r"\s*\[[A-D]\]", "", p)                                 # (the sections of Spanheim's pages)
            p = re.sub(r"\s*\*(?: \*){2,}", " …", p)                            # (a gap in the manuscripts)
            if p.count("*") % 2:
                p = re.sub(r"(?<=[a-z])\*(?=\s)", "", p)                         # ("prudence* take": a note mark)
            paras.append(p)
        if paras:
            out.append((title, paras))
    if not out:                                                     # (a page with no headings)
        out = [("", [p for p in ws_blocks(t) if not p.startswith("From The Works of the Emperor Julian")])]
    return out


def julian() -> None:
    books = {}
    for name, page in JULIAN.items():
        sections = _julian_sections(page)
        paras = [p for _, ps in sections for p in ps]
        if name in ("Epigrams of Julian", "Fragments of Julian"):              # (Wright's source under each)
            paras = [p for p in paras if not re.match(r"\*?(?:Quoted|Preserved|Occurs|First|Assigned|Palatine|The Greek "
                                                      r"Anthology|Anthology)\b", p)]
        books[name] = {"1": chapter("", paras)}
    letters = {}
    for n in range(1, 84):
        (title, paras), = _julian_sections(f"Letters/Letter {n}")
        letters[str(n)] = chapter(re.sub(r"^\d+\.\s*", "", title), paras)
    books["Letters of Julian"] = letters
    save("julian_wright", "trans. Wilmer Cave Wright (1913–23)", books)


# ── Alcinous's Doctrine of Plato (the Didaskalikos), in Stanley's History of Philosophy (1687) ──

def alcinous() -> None:
    t = wikisource("The History of Philosophy: Containing the Lives, Opinions, Actions and Discourses of the "
                   "Philosophers of every Sect (3rd edition)/Part 5/The Doctrine of Plato delivered by Alcinous")
    chapters, n, titles, body = {}, None, [], []

    def close():
        if n is not None:
            # (the drop capital and the next letter both set in capitals: "WHereas", "F*Riendship*")
            body[0] = re.sub(r"^([A-Z])\*([A-Z])([a-z]+)\*", lambda m: f"*{m.group(1)}{m.group(2).lower()}{m.group(3)}*", body[0])
            body[0] = re.sub(r"^([A-Z])([A-Z])(?=[a-z])", lambda m: m.group(1) + m.group(2).lower(), body[0])
            title = re.sub(r"\b([A-Z])([A-Z]{3,})\b", lambda m: m.group(1) + m.group(2).lower(), ": ".join(titles))
            chapters[str(n)] = chapter(title.rstrip(":"), body)
    for m in re.finditer(r'(?is)<div class="wst-center[^"]*">(.*?)</div>|<div class="poem[^"]*">(.*?)</div>'
                         r'|<p\b[^>]*>(.*?)</p>', t):
        if m.group(1) is not None:
            s = text(m.group(1)).replace("*", "").strip()
            head = re.match(r"CHAP\. ([IVXL]+)\.?$", s)
            if head:
                close()
                n, titles, body = roman(head.group(1)), [], []
            elif n is not None and s and not body:
                titles.append(heading(s) if s.isupper() else s.rstrip("."))
            elif n is not None and s:
                body.append(s)                                       # (a centred line in the text: a verse quoted)
        elif n is not None:
            s = text(m.group(2) if m.group(2) is not None else m.group(3), lines=True)
            if s:
                body.append(s)
    close()
    expect(list(chapters) == [str(i) for i in range(1, len(chapters) + 1)], f"Alcinous chapters {list(chapters)}")
    save("alcinous", "trans. Thomas Stanley (1687)", {"The Doctrine of Plato (Alcinous)": chapters})


# ── Guthrie's Pythagoras Source Book (1920): what Taylor's volumes and the bot lack ──
# Left out: the Lives by Iamblichus and Porphyry and the Golden Verses (the bot has them), Diogenes Laertius's
# biographies (in his Lives, on the Perseus shelf), Ocellus and the political fragments (Taylor's, above), and
# the sentences of Sextus and the rest (pythagorean_sentences.json is this book's).

def _guthrie(page: str) -> list:
    """[("C", centred heading) | ("P", paragraph)] of a page of the Source Book."""
    t = wikisource(f"Pythagoras Source Book and Library/{page}")
    out = []
    for m in re.finditer(r'(?is)<div class="wst-center[^"]*">(.*?)</div>|<div class="poem[^"]*">(.*?)</div>'
                         r'|<p\b[^>]*>(.*?)</p>', t):
        if m.group(1) is not None:
            out.append(("C", text(m.group(1)).replace("*", "").strip()))
        else:
            s = text(m.group(2) if m.group(2) is not None else m.group(3), lines=True).replace("{{ul|", "")  # (a broken template)
            if s and not re.match(r"\(In Photius's work", s):                 # (Guthrie's note)
                out.append(("P", s))
    return out


def _sections(tokens: list, start: str = "", stop: str = "$^") -> list:
    """[(heading, paragraphs)] from the centred heading matching start to the one matching stop."""
    out, on = [], not start
    for kind, s in tokens:
        if kind == "C":
            if start and re.search(start, s):
                on = True
            elif re.search(stop, s):
                on = False
            if on and s:
                out.append((s, []))
        elif on and out:
            out[-1][1].append(s)
        elif on:
            out.append(("", [s]))
    return [(h, ps) for h, ps in out if ps]


def guthrie() -> None:
    books = {}
    (_, philolaus), = _sections(_guthrie("Part 2/Chapter 3"), r"FRAGMENTS OF PHILOLAUS")
    books["Fragments of Philolaus"] = {"1": chapter("", philolaus)}
    archytas = _sections(_guthrie("Part 2/Chapter 4"), r"^SECTION I\b")
    expect(len(archytas) == 5, f"Archytas: {len(archytas)} sections")
    books["Fragments of Archytas"] = {str(i + 1): chapter(heading(re.sub(r"^SECTION [IV]+\s*|\s*\(.*\)$", "", h)), ps)
                                      for i, (h, ps) in enumerate(archytas)}
    timaeus = _sections(_guthrie("Part 2/Chapter 27"), r"^1\. MIND")
    expect(len(timaeus) == 12, f"Timaeus: {len(timaeus)} sections")
    books["Timaeus Locrus on the Soul of the World"] = {
        str(i + 1): chapter(heading(re.sub(r"^\d+\.\s*", "", h)), ps) for i, (h, ps) in enumerate(timaeus)}
    (_, photius), = _sections(_guthrie("Part 1/Chapter 3"))
    books["Anonymous Life of Pythagoras"] = {"1": numbered(photius)}
    ethical = []
    for page, start, stop in (("Part 2/Chapter 6", "FELICITY", "ON A REPUBLIC"), ("Part 2/Chapter 8", "", "$^"),
                              ("Part 2/Chapter 14", "", "$^"), ("Part 2/Chapter 15", "", "$^"),
                              ("Part 2/Chapter 16", "", "$^"), ("Part 2/Chapter 17", "", "$^"),
                              ("Part 2/Chapter 18", "", "$^"), ("Part 2/Chapter 23", "", "$^")):
        (h, ps), = _sections(_guthrie(page), start, stop)
        h = "Hippodamus the Thurian on Felicity" if "FELICITY" in h else heading(h)
        ethical.append(chapter(h, ps))
    books["Ethical Fragments of the Pythagoreans"] = {str(i + 1): c for i, c in enumerate(ethical)}
    save("pythagoras_source_book", "trans. Kenneth Sylvan Guthrie (1920)", books)


# ── tertullian.org's pagan shelf ───────────────────────────────────────────

def tertullian(page: str) -> str:
    t = fetch(f"https://www.tertullian.org/fathers/{page}.htm", f"{page}.htm")
    t = re.sub(r"(?is)<head.*?</head>|<style.*?</style>|<script.*?</script>", " ", t)
    return re.sub(r'(?is)<span class="?pb"?>\s*\|\d+\s*</span>', "", t)


def t_text(fragment: str) -> str:
    return re.sub(r"\s*\|\d+(?=\s|$)", "", text(fragment)).replace("&nbsp", " ").strip()


def against_christians() -> None:
    """Harnack's fragments of Porphyry's Against the Christians, each under the father who quotes it."""
    t = tertullian("porphyry_against_christians_02_fragments")
    t = t[t.find("The order is that of Harnack"):t.rfind("This text was compiled")]
    frags, section, cite, n = {}, "", "", None
    for m in re.finditer(r"(?is)<h3[^>]*>(.*?)</h3>|<blockquote>(.*?)</blockquote>|<p\b[^>]*>(.*?)</p>", t):
        if m.group(1) is not None:
            section = t_text(m.group(1)).replace("*", "")
            continue
        if m.group(2) is not None:
            heads = list(re.finditer(r"(?is)<h3[^>]*>(.*?)</h3>", m.group(2)))
            if heads:
                section = t_text(heads[-1].group(1)).replace("*", "")
            num = re.search(r'(?i)<a name="C?(\d+)">', m.group(2))
            body = re.sub(r"(?is)<h3.*?</h3>", "", m.group(2))
            c = re.sub(r"^\d+\.\s*", "", t_text(body)).rstrip(": ").replace("*", "")
            if num:
                n = int(num.group(1))
                expect(n not in frags, f"fragment {n} twice")
                frags[n] = []
                cite = (f"*{section}*\n" if section else "") + f"*{c}*"
                section = ""
            elif c:
                cite = f"*{c}*"
            continue
        s = t_text(m.group(3))
        if n is None or not s:
            continue
        frags[n].append(f"{cite}\n{s}" if cite else s)
        cite = ""
    # (Harnack's numbers, which the bot keeps; the page has no 90)
    expect(list(frags) == sorted(frags) and len(frags) == 96 and all(frags.values()), f"fragments {list(frags)}")
    return {str(k): {str(i + 1): v for i, v in enumerate(vs)} for k, vs in frags.items()}


def t_paras(page: str, start: str, end: "str | None" = None) -> list:
    """A tertullian.org page's paragraphs from the first matching start to the one before end, without the
    editors' bracketed notes."""
    from build_neoplatonists import tertullian_plain
    paras = [p.strip() for p in tertullian_plain(page).split("¶") if p.strip()]
    a = next(i for i, p in enumerate(paras) if re.search(start, p))
    b = next((i for i, p in enumerate(paras) if i > a and end and re.search(end, p)), len(paras))
    out = []
    for p in paras[a:b]:
        p = re.sub(r"\s*\[\*?(?:Here is|in the original|Translated by)[^\]]*\]", "", p).strip()
        if p and not re.fullmatch(r"\[[^\]]*\]", p):
            out.append(p)
    return out


def _with_heads(paras: list, head: str) -> list:
    """[(heading, paragraphs)]: a paragraph matching head starts a section."""
    out = []
    for p in paras:
        if re.fullmatch(head, p):
            out.append((p, []))
        else:
            expect(bool(out), f"text before the first heading: {p[:60]!r}")
            out[-1][1].append(p)
    return out


def porphyry_more() -> None:
    books = {}
    books["Letter to Anebo"] = {"1": chapter("", t_paras("porphyry_anebo_02_text", r"Porphyry to the Prophet Anebo",
                                                         r"^\[Footnotes"))}
    images = " ".join(t_paras("porphyry_on_images_02_text", r"Fragment 1 \(", r"^THE END"))
    parts = re.split(r"\s*Fragment (\d+) \(=\s*([^)]*)\)\s*", images)[1:]
    books["On Images"] = {parts[i]: {"1": f"*{parts[i + 1].strip()}*\n{parts[i + 2].strip()}"}
                          for i in range(0, len(parts), 3)}
    # (Bidez's numbers; the page has no 9)
    expect(list(books["On Images"]) == [str(n) for n in (1, 2, 3, 4, 5, 6, 7, 8, 10)], "On Images fragments")
    faculties = t_paras("porphyry_psychological_fragment_2_text", r"^\*Object of the Book")
    merged = []
    for p in faculties:                                                      # (a heading goes with what follows)
        if merged and re.fullmatch(r"\*[^*]+\*\s*;?", merged[-1]):
            merged[-1] = merged[-1].rstrip(" ;").replace(" *", "*") + "\n" + p
        else:
            merged.append(p)
    books["On the Faculties of the Soul"] = {"1": chapter("", merged)}
    isagoge = t_paras("porphyry_isagogue_02_translation", r"^\[Translated by Octavius", r"^\[This translation appears")
    sections = []
    for p in isagoge:
        if p == "Chap.":
            sections.append([None, []])
        elif sections and sections[-1][0] is None:
            sections[-1][0] = p.lstrip("- ").replace("*", "").strip().rstrip(".")
        else:
            sections[-1][1].append(p)
    expect(len(sections) == 17, f"Isagoge: {len(sections)} chapters")
    books["Isagoge"] = {str(i + 1): chapter(h, ps) for i, (h, ps) in enumerate(sections)}
    books["Porphyry Against the Christians"] = against_christians()
    save("porphyry_more", "trans. Thomas Taylor (1821)", books, {
        "On Images": "trans. E. H. Gifford (1903)", "On the Faculties of the Soul": "trans. K. S. Guthrie",
        "Isagoge": "trans. O. F. Owen (1853)", "Porphyry Against the Christians": "ed. Harnack, various translators (2004)"})


def proclus_minor() -> None:
    books = {}
    motion = _with_heads(t_paras("proclus_on_motion", r"^BOOK I$", r"^\* - \*"), r"BOOK (?:I|SECOND)")
    books["Proclus on Motion"] = {str(i + 1): chapter("", ps) for i, (_, ps) in enumerate(motion)}
    oracles = _with_heads(t_paras("proclus_chaldaic_oracles", r"^1 THE INVISIBLE ORDERS", r"^CHALDEAN ORACLES$"),
                          r"(?:\d+ )?[A-Z0-9][A-Z0-9 &'\-]+(?<!I)")
    expect(len(oracles) == 12, f"Proclus on the Oracles: {len(oracles)}")
    books["Commentary on the Chaldaean Oracles"] = {
        str(i + 1): chapter(heading(re.sub(r"^\d+ ", "", h).replace("0", "O")), ps) for i, (h, ps) in enumerate(oracles)}
    save("proclus_minor", "trans. K. S. Guthrie (1925)", books)


def eunapius() -> None:
    lives = t_paras("eunapius_02_text", r"^Xenophon the philosopher, who is unique", r"^\[Most of the footnotes")
    lives = [p for p in lives if not p.isupper()]           # ("THE WRITERS WHO HAVE COMPILED...": a heading)
    # (each philosopher's name in small capitals the page spaces after the first letter: "P LOTINUS was")
    lives = [re.sub(r"\b([A-Z]) ([A-Z]{2,})\b", lambda m: m.group(1) + m.group(2).lower(), p) for p in lives]
    save("eunapius", "trans. Wilmer Cave Wright (1921)",
         {"Lives of the Philosophers and Sophists": {"1": chapter("", lives)}})


def libanius() -> None:
    books = {"For the Temples": {"1": chapter("", t_paras("libanius_pro_templis_02_trans", r"^Having already, O Emperor",
                                                          r"^\[Footnotes"))},
             "Monody on Julian": {"1": chapter("", t_paras("libanius_monody", r"^RIGHT were it", r"^\[Footnotes"))}}
    books["Monody on Julian"]["1"]["1"] = books["Monody on Julian"]["1"]["1"].replace("RIGHT were", "Right were", 1)
    for verses in books.values():
        for k, v in verses["1"].items():
            verses["1"][k] = v.replace("----", "—")
    save("libanius", "trans. Nathaniel Lardner (1830)", books, {"Monody on Julian": "trans. C. W. King (1888)"})


# ── The Presocratics: the fragments Burnet translated in Early Greek Philosophy (#67097) ──
# Only the fragments (his "version of the fragments", set as quotations), not his account of them; the
# reference after each to Ritter and Preller ("R. P. 40") is dropped. Numbered as he numbers them (Bywater's for
# Herakleitos, Diels's for the rest), so a number can be missing.

BURNET = {"Fragments of Xenophanes": "The fragments.", "Fragments of Heraclitus": "The fragments.",
          "Fragments of Parmenides": "The poem.", "Fragments of Empedocles": "The remains.",
          "Fragments of Anaxagoras": "The Fragments.", "Fragments of Zeno": "The Fragments.",
          "Fragments of Melissus": "The Fragments.", "Fragments of Diogenes of Apollonia": "The Fragments."}


def _quoted(region: str) -> list:
    """The paragraphs (and the centred fragment numbers) inside the region's <div class="quote">s, in order."""
    out, stack = [], []
    for m in re.finditer(r'(?is)<div([^>]*)>|</div>|<p\b[^>]*>(.*?)</p>', region):
        if m.group(0).lower().startswith("<div"):
            stack.append((m.group(1) or "", m.end()))
        elif m.group(0).lower() == "</div>":
            if stack:
                _, start = stack.pop()
                num = re.fullmatch(r"\s*\((\d+)\)\s*", re.sub(r"<[^>]+>", "", region[start:m.start()]))
                if num and any("quote" in s for s, _ in stack) and out[-1:] != [("n", num.group(1))]:
                    out.append(("n", num.group(1)))                # (a number centred above its fragment)
        elif any("quote" in s for s, _ in stack):
            out.append(("p", m.group(2)))
    return out


def burnet() -> None:
    t = gutenberg(67097)
    t = re.sub(r'(?is)<span class="(?:linenum|pageno)"[^>]*>.*?</span>', "", t)
    notes = list(re.finditer(r'(?is)<div class="sidenote">(.*?)</div>', t))
    books, used = {}, set()
    for name, label in BURNET.items():
        i = next(i for i, m in enumerate(notes) if text(m.group(1)) == label and i not in used)
        used.add(i)
        region = t[notes[i].end():notes[i + 1].start()]
        frags, n = {}, None
        for kind, value in _quoted(region):
            if kind == "n":
                n = value
                frags[n] = []
                continue
            s = text(value)
            num = re.match(r"\((\d+)\)\s*", s)
            if num:
                n, s = num.group(1), s[num.end():]
                frags[n] = []
            s = re.sub(r"\s*R\. P\. [\w .,;]+$", "", s).strip()
            if n is not None and s:
                frags[n].append(s)
        frags = {k: "\n".join(v) for k, v in frags.items() if v}
        expect(len(frags) >= 3 and list(map(int, frags)) == sorted(map(int, frags)), f"{name}: {list(frags)}")
        books[name] = {"1": frags}
    save("presocratics", "trans. John Burnet (1908)", books)


# ── The Orphic gold tablets: Murray's versions, in Jane Harrison's Prolegomena (#78248), ch. XI ──
# Only the tablets' words (the verse under each tablet's heading); VII is a few letters, untranslated.

def orphic_tablets() -> None:
    t = gutenberg(78248)
    region = between(t, r"The Orphic Tablets\.</span></h3>", r"Orphic Vases of Lower Italy")
    heads = []
    for p in re.finditer(r"(?is)<p[^>]*>(.*?)</p>", region):
        m = re.match(r"([IVX]+)\. (.*?[Tt]ablets?\b[^.\[⁠]*)", text(p.group(1)).replace("*", "").replace("grande", "Grande"))
        if m:
            heads.append((p, m))
    tablets = {}
    for i, (p, h) in enumerate(heads):
        end = heads[i + 1][0].start() if i + 1 < len(heads) else len(region)
        body = region[p.end():end]
        poem = re.search(r'(?is)<div class="poetry-container">', body)
        if not poem or re.search(r"(?is)<p\b", body[:poem.start()].split("</p>", 1)[-1]):
            continue                                                     # (no verse straight after the heading)
        stop = re.search(r"(?is)<p\b|<h\d", body[poem.end():])
        block = body[poem.start():poem.end() + (stop.start() if stop else len(body))]
        lines = [text(x) for x in re.findall(r'(?is)<div class="verse[^"]*">(.*?)</div>', block)]
        lines = [x for x in lines if x]
        n = roman(h.group(1))
        title = re.sub(r"\s+", " ", h.group(2)).strip().rstrip(".")
        title = "The " + title[0].upper() + title[1:].replace(" tablet", " Tablet") if not title.startswith("The") else \
            title.replace(" tablet", " Tablet")
        tablets[str(n)] = {"1": f"*{title}*\n" + "\n".join(lines)}
    expect(sorted(map(int, tablets)) == [1, 2, 3, 4, 5, 6, 8], f"tablets {sorted(tablets)}")
    save("orphic_tablets", "trans. Gilbert Murray (1903)",
         {"Orphic Gold Tablets": dict(sorted(tablets.items(), key=lambda kv: int(kv[0])))})


BUILDS = {"pythagoreans": pythagoreans, "ocellus": ocellus, "theology": theology, "apuleius": apuleius,
          "scipio": scipio, "boethius": boethius, "celsus": celsus, "maximus": maximus,
          "julian": julian, "alcinous": alcinous, "guthrie": guthrie,
          "porphyry_more": porphyry_more, "proclus_minor": proclus_minor, "eunapius": eunapius, "libanius": libanius,
          "burnet": burnet, "orphic_tablets": orphic_tablets}


def main(names: list) -> None:
    for name in names or BUILDS:
        print(name)
        BUILDS[name]()


if __name__ == "__main__":
    main(sys.argv[1:])
