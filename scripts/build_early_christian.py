"""
The earlychristianwritings.com gaps (2026-11-10), into two files:

data/nt_apocrypha/gospel_fragments.json -- lost gospels known from fragments:
    from M. R. James's Apocryphal New Testament (1924), as Wikisource has it (every page proofread): the Gospel
    according to the Hebrews, the Gospel of the Ebionites, the Gospel according to the Egyptians, the Preaching of
    Peter, the Fayoum fragment and Oxyrhynchus papyrus 840. James prints his own comments in smaller type
    ({{fine}} / {{fine block}}): those are left out, and so are the few he set in ordinary type (JAMES_NOTES, each
    of which must be found, so a change at Wikisource fails loudly). Each paragraph of his is a verse.
    From earlychristianwritings.com: the Egerton Gospel (Bell and Skeat, 1935), Oxyrhynchus 1224 (Andrew
    Bernhard's translation, the running text), the Gospel of the Nazoreans (Vielhauer and Ogg's fragments, as Ron
    Cameron printed them).

data/patristics/early_church_more.json:
    the Didascalia Apostolorum (R. H. Connolly, 1929, from earlychristianwritings.com: a chapter for each of
    Connolly's 26, a verse a paragraph; the transcriber's page numbers and Bible references, and Lagarde's page
    numbers, left out), the Passion of the Scillitan Martyrs (J. A. Robinson, as in ANF 9), the Inscription of
    Abercius (Quasten's translation, a verse a line), the 'Marcionite' prologues to Paul's letters (F. C. Burkitt,
    1906) and the 'Anti-Marcionite' prologues to the Gospels (Roger Pearse, 2006) from tertullian.org, and the
    Muratorian Canon -- taken from the library's own copy of ANF 5 (data/patristics/caius.json, where it sits as
    Caius's "Fragments" and can't be reached by that name). And the Acts of Apollonius (F. C. Conybeare, 1894,
    from the Armenian), from scripts/transcripts/acts_of_apollonius.tsv: OCR of the 1894 scan, proofread against every
    page image (2026-11-11, the owner's go-ahead), a verse for each of Harnack's sections, the prologue as verse 0.

    python scripts/build_early_christian.py
"""
import html
import json
import re
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CACHE = Path(__file__).resolve().parent / ".cache" / "early_christian"
UA = {"User-Agent": "ScriptureBot corpus builder (a personal Discord bot)"}
WS_INDEX = "Page:The Apocryphal New Testament (1924).djvu/"


def expect(ok: bool, message: str) -> None:
    if not ok:
        raise SystemExit(f"unexpected source layout: {message}")


def fetch(url: str, name: str) -> str:
    CACHE.mkdir(parents=True, exist_ok=True)
    f = CACHE / name
    if not f.exists():
        f.write_bytes(urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60).read())
        time.sleep(1.5)
    raw = f.read_bytes()
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw.decode("cp1252")


def ws_page(n: int) -> str:
    title = urllib.parse.quote(WS_INDEX + str(n))
    return fetch(f"https://en.wikisource.org/w/index.php?title={title}&action=raw", f"james_p{n}.txt")


# ── James 1924, from Wikisource ──────────────────────────────────────────────────────────────────────────────────

def wikitext(pages: range) -> str:
    """The pages' wikitext joined, without James's small-type notes, footnotes and the pages' headers."""
    parts = []
    for n in pages:
        t = re.sub(r"(?s)<noinclude>.*?</noinclude>|<section [^>]*/>", "", ws_page(n))
        ends = t.rstrip().endswith("{{nop}}")              # (a page-end {{nop}}: the next page opens a paragraph)
        parts.append((t.replace("{{nop}}", "").rstrip(), ends))
    text, broke = "", False
    for t, ends in parts:               # (a page joins the last with a space, unless a paragraph ends between them)
        text = t if not text else text + ("\n\n" if broke or re.match(r"[ \t]*\n", t) else " ") + t.lstrip()
        broke = ends
    text = re.sub(r"(?s)\{\{fine block/s\}\}.*?\{\{fine block/e\}\}", "\n\n", text)
    text = re.sub(r"(?s)\{\{fine\|(?:[^{}]|\{\{[^{}]*\}\})*\}\}", "\n\n", text)
    text = re.sub(r"(?s)<ref>.*?</ref>|<section [^>]*/>|\{\{nop\}\}|\{\{sic\}\}", "", text)
    return text


def inline(t: str) -> str:
    t = re.sub(r"\{\{[Ss]c\|([^{}]*)\}\}", r"\1", t)
    t = re.sub(r"\{\{(?:gap|separator|hr)\}\}", " ", t)
    t = re.sub(r"\[\[[^\]|]*\|([^\]]*)\]\]|\[\[([^\]]*)\]\]", lambda m: m.group(1) or m.group(2), t)
    t = t.replace("'''", "**").replace("''", "*").replace("&mdash;", "—")
    t = html.unescape(t)
    t = re.sub(r"[ \t]*\n[ \t]*", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    t = re.sub(r"\*(\s*)\*", r"\1", t)                      # ("*Gospel*'' *to*" adjacent italics run together)
    return t.replace("* *", " ")


def headings(text: str) -> list:
    """[(heading, body)] split at the {{c|{{xl|...}}}} / {{larger|...}} section titles."""
    pieces = re.split(r"\{\{c\|\{\{(?:xxl|xl|larger)\|([^{}]*)\}\}\}\}", text)
    return list(zip(pieces[1::2], pieces[2::2]))


def paragraphs(body: str) -> list:
    body = re.sub(r"(?s)<poem>(.*?)</poem>", lambda m: m.group(1).strip().replace("\n", "<br>"), body)
    body = re.sub(r"\{\{blockquote/[se]\}\}", "", body)
    out = []
    for p in re.split(r"\n\s*\n", body):
        p = inline(p).replace("<br>", "\n").strip()
        p = re.sub(r" *\n *", "\n", p)
        if p:
            out.append(p)
    return out


# James's comments printed in ordinary type, by their openings (each must be found)
JAMES_NOTES = (
    "Jerome ''on Matt.'' xxi. 12 says that", "When I published the note", "One other mention of this Gospel",
    "These Ebionites were vegetarians", "There are allusions to the saying in the Apocryphal Acts",
    "Shortly after this he cites Paul",
)
# ...and inside paragraphs of the text: (James's words, what stays)
JAMES_IN_TEXT = (
    ("Jerome. He is our principal authority in this matter.", "Jerome."),
    ("The borrowing from St. Luke is very evident here. He goes on: ", ""),
    ("Epiphanius goes on to say that he had heard of Hebrew versions of John and Acts kept privately in the "
     "treasuries (Geniza ?) at Tiberias, and continues:", None),
)


JOIN_NEXT = ("Stichometry of Nicephorus", "Apocalypse of John, Apocalypse of Peter", "Jerome.", "*Of illustrious men*, 2",
             "*On Matt.* vi. 11 (the Lord's prayer).", "*Latin version of Origen", "The second of the rich men",
             "He answered him: I have", "Clem. Alex. *Strom.* iii. 9. 64.", "(The so-called Second Epistle of Clement")
# the transcription's slips (each checked against the sense; the scan has "and", "do ye", "a new")
JAMES_SLIPS = (("Greek arid Latin", "Greek and Latin"), ("So then do. ye", "So then do ye"), ("in anew way", "in a new way"),
               ("the Lord said. unto him", "the Lord said unto him"), ("day-and night", "day and night"),
               ("(retribution),-", "(retribution),"))


def james_books() -> dict:
    text = wikitext(range(39, 58))
    for opening in JAMES_NOTES:
        expect(opening.replace("''", "") in inline(text) or opening in text, f"James note {opening!r}")
    sections = dict((inline(h), b) for h, b in headings(text))
    expect({"THE GOSPEL ACCORDING TO THE HEBREWS", "THE GOSPEL OF THE EBIONITES", "THE GOSPEL ACCORDING TO THE EGYPTIANS",
            "THE PREACHING OF PETER"} <= set(sections), f"James sections {list(sections)}")
    books = {}
    for heading, name in (("THE GOSPEL ACCORDING TO THE HEBREWS", "Gospel according to the Hebrews"),
                          ("THE GOSPEL OF THE EBIONITES", "Gospel of the Ebionites"),
                          ("THE GOSPEL ACCORDING TO THE EGYPTIANS", "Gospel according to the Egyptians"),
                          ("THE PREACHING OF PETER", "Preaching of Peter")):
        body = sections[heading]
        if name == "Preaching of Peter":
            body = body.split("LOST HERETICAL BOOKS")[0]
        paras = []
        for p in paragraphs(body):
            if any(p.startswith(inline(o)) for o in JAMES_NOTES):
                continue
            for words, keep in JAMES_IN_TEXT:
                if p.startswith(words):
                    p = None if keep is None else keep + p[len(words):]
                if p is None:
                    break
            if p:
                paras.append(p)
        books[name] = paras
    # the Hebrews' Budge passage: James's narration around the monk's words is kept (it says who quotes what), but
    # not his closing verdict on it
    heb = books["Gospel according to the Hebrews"]
    i = next(i for i, p in enumerate(heb) if p.startswith("In Budge's"))
    cut = heb[i].find(" (Cyril convinced him")
    expect(cut > 0, "Hebrews: Budge passage")
    tail = re.search(r"'After they had raised him up on the cross, the Father took him up into heaven unto himself\.'", heb[i])
    expect(tail is not None, "Hebrews: the monk's last sentence")
    heb[i] = heb[i][:cut] + " … " + tail.group(0)
    # a heading, a citation or an introduction ("...is:") joins the passage it leads into
    for name, paras in books.items():
        j = 0
        while j < len(paras) - 1:
            if paras[j].endswith((":", " and")) or paras[j].startswith(JOIN_NEXT) and "\n" not in paras[j]:
                paras[j:j + 2] = [paras[j] + "\n" + paras[j + 1]]
                if paras[j].endswith((":", " and")) or paras[j].split("\n")[-1].startswith(JOIN_NEXT):
                    continue
            j += 1
        for k, p in enumerate(paras):
            p = re.sub(r"(?: ?\. ){2,}\.", "…", p + " ").strip()                       # (". . . ." / ". . .")
            for slip, word in JAMES_SLIPS:
                p = p.replace(slip, word)
            paras[k] = p
    return {name: {"1": {str(i): p for i, p in enumerate(paras, 1)}} for name, paras in books.items()}


def fayoum_and_840() -> dict:
    # the Fayoum fragment: James gives "what may be regarded as certain" as lines, with two places read two ways
    # (his braces); the alternatives are shown with "or"
    p63 = ws_page(63)
    rows = re.findall(r"\|\s*(?:\{\{brace\|l\|h([tb])\}\})?\s*\|\|(?:\{\{gap\}\})?([^\n|]+)", p63)
    expect(len(rows) == 9, f"Fayoum: {len(rows)} lines")
    lines, i = [], 0
    while i < len(rows):
        brace, line = rows[i]
        if brace == "t":
            lines.append(f"{line.strip()} *or* {rows[i + 1][1].strip()}")
            i += 2
        else:
            lines.append(line.strip())
            i += 1
    fayoum = {"1": "\n".join(lines)}
    text = wikitext(range(67, 69))
    body = text.split("FRAGMENT OF ANOTHER GOSPEL}}}}")[1].split("{{c|{{xl|B. COPTIC}}}}")[0]
    paras = [p for p in paragraphs(body) if not p.startswith("*Oxyrhynchus Papyri*")]
    expect(paras[0].startswith("first, before he doeth wrong") and len(paras) == 3, f"Oxy 840: {[p[:30] for p in paras]}")
    paras[0] = "… " + paras[0]
    return {"Fayoum Gospel Fragment": {"1": fayoum},
            "Oxyrhynchus Gospel 840": {"1": {str(i): p for i, p in enumerate(paras, 1)}}}


# ── earlychristianwritings.com ───────────────────────────────────────────────────────────────────────────────────

def ecw(path: str) -> str:
    return fetch("http://www.earlychristianwritings.com/" + path, "ecw_" + path.replace("/", "_"))


def lines_of(fragment: str) -> list:
    t = re.sub(r"(?is)<(script|style)\b.*?</\1>|<!--.*?-->", "", fragment)
    t = re.sub(r"(?i)<br\s*/?>|</p>|<p\b[^>]*>|</h\d>|<h\d[^>]*>|</div>|</li>|</blockquote>", "\n", t)
    t = html.unescape(re.sub(r"<[^>]+>", " ", t)).replace("\xa0", " ")
    out = []
    for l in t.split("\n"):
        l = re.sub(r"\s+", " ", l).strip()
        if l.startswith(("Go to the Chronological List", "Please buy the CD")):        # (the site's footer)
            break
        out.append(l)
    return out


def grouped(lines: list) -> list:
    """Lines into paragraphs at the blank ones."""
    out, cur = [], []
    for l in lines + [""]:
        if l:
            cur.append(l)
        elif cur:
            out.append(" ".join(cur))
            cur = []
    return out


def body_of(page: str) -> str:
    """An earlychristianwritings text page without its site furniture (title box, footer)."""
    page = re.split(r"(?i)Go to the Chronological List|Please buy the CD", page)[0]
    return page


def egerton() -> dict:
    page = body_of(ecw("text/egerton.html"))
    parts = re.split(r"(?i)(Fragment \d: (?:Recto|Verso) \(\?\))", page)
    expect(len(parts) == 9, f"Egerton: {len(parts)}")
    verses = {}
    for n, (head, chunk) in enumerate(zip(parts[1::2], parts[2::2]), 1):
        text = " ".join(l for l in lines_of(chunk) if l)
        text = text.split("Translation reprinted from")[0].strip()
        text = re.sub(r"(?:\. ){2,}\.", "…", text).replace("transgessor", "transgressor")
        verses[str(n)] = f"*{head}*\n{text}"
    return {"Egerton Gospel": {"1": verses}}


def oxy1224() -> dict:
    page = body_of(ecw("text/oxyrhynchus1224.html"))
    page = page[page.find("the possibility cannot be ruled out"):]
    page = page[:page.find("Fragment 1: recto")]
    paras = grouped(lines_of(page.replace("the possibility cannot be ruled out", "", 1)))
    expect(len(paras) == 4, f"Oxy 1224: {paras}")
    paras = [re.sub(r'"\s*…\s*"', '"…"', re.sub(r"\s*\.\s*\.\s*\.\s*", " … ", p)).strip() for p in paras]
    paras = [re.sub(r'^" …', '"…', re.sub(r'… "$', '…"', p)) for p in paras]
    return {"Oxyrhynchus Gospel 1224": {"1": {str(i): p for i, p in enumerate(paras, 1)}}}


def nazoreans() -> dict:
    page = body_of(ecw("text/nazoreans-ogg.html"))
    ls = [l for l in lines_of(page) if l]
    start = next(i for i, l in enumerate(ls) if l.startswith("To these (citations"))
    verses, frag = {}, []
    for l in ls[start:]:
        frag.append(l)
        if re.fullmatch(r"\(.*\)", l):                       # (the source, on a line of its own, closes a fragment)
            verses[str(len(verses) + 1)] = " ".join(frag[:-1]) + f"\n*{l}*"
            frag = []
    expect(len(verses) >= 20 and not frag, f"Nazoreans: {len(verses)} fragments, {frag[:2]}")
    for v, t in verses.items():
        verses[v] = re.sub(r"\bhte\b", "the", re.sub(r"\bord\b", "word", t.replace("moter of the Lord", "mother of the Lord")))
    return {"Gospel of the Nazoreans": {"1": verses}}


def didascalia() -> dict:
    page = body_of(ecw("text/didascalia.html"))
    page = page[page.find("THE CATHOLIC DIDASCALIA"):]
    chapters = re.split(r"(?:<[^>]+>\s*)*CHAPTER ([IVXL]+)\s*(?:<[^>]+>\s*)*", page)
    expect(len(chapters) == 53, f"Didascalia: {len(chapters) // 2} chapters")
    book = {}
    for num, chunk in zip(chapters[1::2], chapters[2::2]):
        paras = re.split(r"(?i)</p>\s*<p[^>]*>|<p[^>]*>|<br>\s*<br>", chunk)
        verses = []
        for p in paras:
            t = " ".join(l for l in lines_of(p) if l)
            t = re.sub(r"\[\[\d+\]\]", " ", t)                                 # (Connolly's pages)
            t = re.sub(r"\(p\. \d+\)", " ", t)                                 # (Lagarde's)
            t = re.sub(r"\[(?:cf\. )?(?:\d ?)?[A-Z][a-z]{1,5}\.? ?\d+[^\]]*\]", " ", t)   # (Bible references)
            t = re.sub(r"\[[ivx]+\.\s*\d+\]", " ", t)                           # (Funk's sections)
            t = re.sub(r"\s+([,.;:?!])", r"\1", re.sub(r"\s+", " ", t)).strip()
            if t:
                verses.append(t)
        title, *rest = verses
        book[str(roman(num))] = {"1": f"*{title}*\n" + rest[0], **{str(i): v for i, v in enumerate(rest[1:], 2)}}
    expect(list(book) == [str(n) for n in range(1, 27)], f"Didascalia chapters {list(book)}")
    return book


ROMAN = {"I": 1, "V": 5, "X": 10, "L": 50}


def roman(numeral: str) -> int:
    values = [ROMAN[c] for c in numeral]
    return sum(-v if i + 1 < len(values) and v < values[i + 1] else v for i, v in enumerate(values))


def scillitan() -> dict:
    page = body_of(ecw("text/scillitan.html"))
    page = page[page.find("WHEN Praesens"):]
    ls, verses, cur = lines_of(page), [], []
    for l in ls:
        if not l:
            if cur:
                verses.append(" ".join(cur))
            cur = []
        else:
            cur.append(l)
    if cur:
        verses.append(" ".join(cur))
    verses = [v.replace("persist m being", "persist in being").replace("WHEN Praesens", "When Praesens") for v in verses]
    expect(verses[-1].endswith("for ever and ever. Amen.") and len(verses) > 25, f"Scillitan: {len(verses)}")
    return {"Passion of the Scillitan Martyrs": {"1": {str(i): v for i, v in enumerate(verses, 1)}}}


def apollonius() -> dict:
    rows = (Path(__file__).resolve().parent / "transcripts" / "acts_of_apollonius.tsv").read_text(encoding="utf-8")
    verses = dict(line.split("\t", 1) for line in rows.splitlines() if line.strip())
    expect(list(verses) == [str(n) for n in range(0, 48)], f"Apollonius: {list(verses)[:3]}...")
    return {"Acts of Apollonius": {"1": verses}}


def abercius() -> dict:
    page = body_of(ecw("text/abercius.html"))
    found = re.findall(r"(?m)^\s*(\d{1,2})\. (.+?)\s*(?:<br>|$)", re.sub(r"<(?!br)[^>]+>", "", page))
    lines = {n: html.unescape(t).strip() for n, t in found}
    expect(list(lines) == [str(n) for n in range(1, 23)], f"Abercius: {list(lines)}")
    lines["9"] = lines["9"].replace("splended", "splendid")
    lines["6"] = lines["6"].replace(" . . . ", " … ")
    return {"Inscription of Abercius": {"1": lines}}


def prologues() -> dict:
    page = fetch("https://www.tertullian.org/fathers/marcionite_prologues_01_text.htm", "tt_marcionite.htm")
    page = page[page.find("[Translated by F.C. Burkitt]"):page.find("This text was transcribed")]
    parts = re.split(r"(?is)<b>\s*<u>\s*(To [^<]+?)\s*</u>\s*</b>", page)
    marc = {}
    for head, chunk in zip(parts[1::2], parts[2::2]):
        marc[str(len(marc) + 1)] = f"*{head.strip()}*\n" + " ".join(l for l in lines_of(chunk) if l)
    expect(len(marc) == 7, f"Marcionite prologues: {len(marc)}")
    page = fetch("https://www.tertullian.org/fathers/anti_marcionite_prologues.htm", "tt_anti_marcionite.htm")
    page = page[page.find("[Translated by Roger Pearse]"):page.find("The translation was made from")]
    parts = re.split(r"(?is)<b>\s*(?:<u>\s*)?(Mark|Luke|John)\s*(?:</u>\s*)?</b>", page)
    anti = {}
    for head, chunk in zip(parts[1::2], parts[2::2]):
        chunk = re.sub(r"(?is)<a href=\"#\d+\">\s*<sup>\d+</sup>\s*</a>", "", chunk)        # (footnote marks)
        text = " ".join(l for l in lines_of(chunk) if l)
        anti[str(len(anti) + 1)] = f"*{head}*\n" + text.replace(" ,", ",")
    expect(len(anti) == 3, f"Anti-Marcionite prologues: {len(anti)}")
    return {"Marcionite Prologues": {"1": marc}, "Anti-Marcionite Prologues": {"1": anti}}


def muratorian() -> dict:
    caius = json.loads((ROOT / "data" / "patristics" / "caius.json").read_text(encoding="utf-8"))["books"]["Fragments"]["2"]
    expect(caius["2"].startswith("I. ...those things at which he was present"), "Muratorian: not in caius.json")
    verses = {}
    for v, t in caius.items():
        if t.startswith("[(In Muratori"):
            continue
        t = re.sub(r"^(?:I\.|\d+\.)\s*", "", t).replace("Catholic epistles .", "Catholic epistles.")
        verses[str(len(verses) + 1)] = re.sub(r"—\s+(?=or bearing|are reckoned)", "—", t)
    expect(len(verses) == 4, f"Muratorian: {len(verses)}")
    return {"Muratorian Canon": {"1": verses}}


def ellipses(books: dict) -> dict:
    """Spaced dots (". . ." and ". . . .") as one ellipsis."""
    for chapters in books.values():
        for verses in chapters.values():
            for v, t in verses.items():
                verses[v] = re.sub(r"(?<=\w)…", " …", re.sub(r" ?\.(?: \.){2,}", " …", t)).replace("… …", "…")
    return books


def main() -> None:
    fragments = ellipses({**james_books(), **fayoum_and_840(), **egerton(), **oxy1224(), **nazoreans()})
    order = ["Gospel according to the Hebrews", "Gospel of the Nazoreans", "Gospel of the Ebionites",
             "Gospel according to the Egyptians", "Egerton Gospel", "Oxyrhynchus Gospel 840", "Oxyrhynchus Gospel 1224",
             "Fayoum Gospel Fragment", "Preaching of Peter"]
    fragments = {k: fragments[k] for k in order}
    james = "trans. M. R. James (1924)"
    sources = {k: james for k in order}
    sources.update({"Egerton Gospel": "trans. H. I. Bell and T. C. Skeat (1935)",
                    "Oxyrhynchus Gospel 1224": "trans. Andrew Bernhard",
                    "Gospel of the Nazoreans": "trans. Philipp Vielhauer and George Ogg"})
    for name, chapters in fragments.items():
        print(f"  {name}: {sum(map(len, chapters.values()))} verses")
    (ROOT / "data" / "nt_apocrypha" / "gospel_fragments.json").write_text(json.dumps(
        {"source": james, "book_sources": sources, "books": fragments}, ensure_ascii=False, indent=1), encoding="utf-8")

    # (didascalia() is held back: the transcription lost a symbol of Connolly's to "?" some 650 times, and those
    # can't be told from real question marks without the printed book -- waiting on the owner)
    church = ellipses({**muratorian(), **prologues(), **abercius(), **scillitan(), **apollonius()})
    sources = {"Muratorian Canon": "trans. S. D. F. Salmond (ANF 5, 1886)",
               "Marcionite Prologues": "trans. F. C. Burkitt (1906)",
               "Anti-Marcionite Prologues": "trans. Roger Pearse (2006)",
               "Inscription of Abercius": "trans. Johannes Quasten (1950)",
               "Passion of the Scillitan Martyrs": "trans. J. Armitage Robinson (ANF 9, 1896)",
               "Acts of Apollonius": "trans. F. C. Conybeare (1894)"}
    for name, chapters in church.items():
        print(f"  {name}: {len(chapters)} chapters, {sum(map(len, chapters.values()))} verses")
    (ROOT / "data" / "patristics" / "early_church_more.json").write_text(json.dumps(
        {"source": "early Christian writings", "book_sources": sources, "books": church}, ensure_ascii=False, indent=1),
        encoding="utf-8")


if __name__ == "__main__":
    main()
