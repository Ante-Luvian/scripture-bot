"""
Builds data/reformation/: the Protestant Reformation and its heirs, in English.

  · book_of_concord.json   The Lutheran confessions, in the Concordia Triglotta translation (1921)
                           as bookofconcord.org gives it, with the Triglotta's paragraph numbers
                           (the way they're cited: Augsburg Confession 4:1-3)
  · luther.json            Luther's principal works
  · calvin.json            The Institutes (Beveridge), cited Book.Chapter.Section; the Treatise on Relics
  · confessions.json       The Reformed, Anglican, Methodist and Baptist confessions and catechisms
  · knox.json, latimer.json, anglican_divines.json, wesley.json

Sources, in the owner's order of preference: sacred-texts.com (archive mirror), then Project
Gutenberg and Wikisource, then the Christian Classics Ethereal Library (its ThML editions, which
keep the books' divisions) and bookofconcord.org for what the others lack. Left out, for want of
any clean English text (only raw OCR or page images exist): Hooker's Laws of Ecclesiastical
Polity, Zwingli's works, Cranmer's own writings, Herbert's Country Parson, the Wesleys' hymnbook
(36 of Charles Wesley's hymns are in !hymn already).

    python scripts/build_reformation.py            # all
    python scripts/build_reformation.py concord    # one file
"""
import html as html_lib
import json
import re
import sys
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_world_texts import (CACHE, DATA, ROOT, _UA, cached_url, expect, gutenberg, paragraphs, roman,
                               sacred_text, st_index, st_page, tidy, wikisource)

OUT = DATA / "reformation"


LEFTOVERS = [r"\{\d+\}",                                           # page numbers ({97})
             r"(?m)^.*End of (?:the )?Project Gutenberg.*$",
             r"(?m)^.*\| Internet Sacred Text Archive.*$",
             r"THE SERMONS OF MARTIN LUTHER, VOL\. [IVX]+, PAGE \d+ ?",   # a running header
             r"(?m)\s+>$", r"(?m)^END OF THE INSTITUTES\.$", r"(?m)^THE END\.?$", r"(?m)^FINIS\.?$", r"\[\d+\]",
             r"(?s)^.*(?:cover art for this book|Edited by George Lyons|No part of this publication|"
             r"personal convenience of our readers).*$",                    # (modern editors' notices)
             r"(?m)^: .*$",                                                  # (the First Blast's margin notes)
             r"(?m)^\[Sidenote:[^\]]*\]\s*"]                                # the editors' margin summaries


def clean(text: str) -> str:
    for pattern in LEFTOVERS:
        text = re.sub(pattern, "", text)
    return re.sub(r"\n{2,}", "\n", text).strip()


def save(filename: str, source: str, books: dict, book_sources: dict = None) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    books = {b: {c: {v: clean(t) for v, t in vs.items() if clean(t)} for c, vs in chs.items()}
             for b, chs in books.items()}
    books = {b: {c: vs for c, vs in chs.items() if vs} for b, chs in books.items()}
    path = OUT / filename
    payload = {"source": source, **({"book_sources": book_sources} if book_sources else {}), "books": books}
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    n = sum(len(v) for b in books.values() for v in b.values())
    print(f"wrote {path.relative_to(ROOT)}: {len(books)} works, {n} passages, {path.stat().st_size // 1000} kB")


def text_of(fragment: str) -> str:
    """HTML or ThML to plain text: notes and page breaks dropped, italics kept as *...*."""
    f = re.sub(r"\s*\n\s*", " ", fragment)                        # (the source's own line wrapping)
    f = re.sub(r"(?is)<note\b.*?</note>|<sup\b.*?</sup>|<pb\b[^>]*/?>|<script\b.*?</script>", "", f)
    f = re.sub(r"(?is)<(i|em)\b[^>]*>\s*(.*?)\s*</\1>", lambda m: f"*{m.group(2)}*" if m.group(2) else "", f)
    f = re.sub(r"(?is)<br\s*/?>", "\n", f)
    f = re.sub(r"(?s)<[^>]+>", "", f)
    f = html_lib.unescape(f).replace("\xa0", " ")
    lines = [re.sub(r"[ \t]+", " ", l).strip() for l in f.split("\n")]
    return "\n".join(l for l in lines if l).replace("**", "")


def numbered(paras: list, title: str = "") -> dict:
    """{1: first, 2: ...}, the title (if any) in italics leading the first."""
    out = {str(i): p for i, p in enumerate((p for p in paras if p), 1)}
    if title and out:
        out["1"] = f"*{title}*\n{out['1']}"
    return out


def fetch(name: str, url: str) -> str:
    path = CACHE / name
    if not path.exists():
        for attempt in range(6):
            try:
                path.write_bytes(urllib.request.urlopen(urllib.request.Request(url, headers=_UA), timeout=90).read())
                break
            except Exception:
                if attempt == 5:
                    raise
                time.sleep(15 * (attempt + 1))
        time.sleep(1.5)
    return path.read_text(encoding="utf-8", errors="replace")


# ── the Book of Concord ─────────────────────────────────────────────────────

CONCORD = [("preface", "Preface to the Book of Concord"), ("augsburg-confession", "Augsburg Confession"),
           ("defense", "Apology of the Augsburg Confession"), ("smalcald-articles", "Smalcald Articles"),
           ("power-and-primacy", "Treatise on the Power and Primacy of the Pope"),
           ("small-catechism", "Small Catechism"), ("large-catechism", "Large Catechism"),
           ("epitome", "Formula of Concord, Epitome"), ("solid-declaration", "Formula of Concord, Solid Declaration")]
BOC = "https://bookofconcord.org"


def _boc_page(path: str) -> str:
    return fetch("boc_" + (path.strip("/").replace("/", "_") or "home") + ".html", BOC + path)


_BOC_NUMBER = re.compile(r'<span[^>]*class="[^"]*-content"[^>]*>(\d+)[a-z]?</span>')


def _boc_sections(page: str) -> list:
    """[(title, {paragraph number: text})] from one page, a section for each <h2> (usually one). The
    Triglotta's paragraph numbers are the verses ("1b", an answer under 1, joins 1); smaller headings
    lead the next paragraph in italics, unless they hold numbered text themselves (a Commandment)."""
    main = re.search(r"(?s)<main>(.*?)</main>", page)
    body = main.group(1) if main else ""
    body = re.sub(r'(?s)<div class="next-previous-box">.*?</div>', "", body)
    sections, title, current, number, pending = [], "", {}, "0", ""
    for m in re.finditer(r"(?is)<(h[2-6]|p|li)\b[^>]*>(.*?)</\1>", body):
        tag, inner = m.group(1).lower(), m.group(2)
        if tag == "h2":
            if current:
                sections.append((title, current))
            title, current, number, pending = text_of(inner), {}, "0", ""
            continue
        if tag.startswith("h") and not _BOC_NUMBER.search(inner):
            text = text_of(inner).strip("*")
            pending = f"{pending} · {text}" if pending else text
            continue
        parts = _BOC_NUMBER.split(inner)
        chunks = [(number, parts[0])] + list(zip(parts[1::2], parts[2::2]))
        for num, chunk in chunks:
            number = num
            text = text_of(chunk)
            if tag.startswith("h") and text:
                text = f"*{text}*"
            if not text:
                continue
            if pending:
                text, pending = f"*{pending}*\n{text}", ""
            joiner = "\n" if tag.startswith("h") or current.get(num, "").endswith("*") else " "
            current[num] = (current.get(num, "") + joiner + text).strip()
    if current:
        sections.append((title, current))
    return sections


def gutenberg_sections(text: str, heading: str, first: int = 1) -> dict:
    """{n: {paragraph: text}}: a chapter at each line matching `heading` (numbered from `first`),
    its heading in italics leading its first paragraph; paragraphs at blank lines."""
    marks = list(re.finditer(rf"(?m)^[ \t]*(?:{heading})[ \t]*$", text))
    out = {}
    for i, m in enumerate(marks):
        chunk = text[m.end():marks[i + 1].start() if i + 1 < len(marks) else len(text)]
        paras = [tidy(p) for p in paragraphs(chunk) if tidy(p) and not re.fullmatch(r"\d{4}\.?", tidy(p))]
        if "INTRODUCTION" in paras[1:]:                 # (an editor's introduction to what comes next)
            paras = paras[:paras.index("INTRODUCTION", 1)]
        while paras and re.fullmatch(r"[A-Z0-9 ,.;:'()\-]+", paras[-1]):   # (the next title's tail, a date)
            paras.pop()
        if paras:
            out[str(first + i)] = numbered(paras, tidy(m.group(0)).rstrip(":"))
    return out


def smalcald() -> dict:
    """The Smalcald Articles from Gutenberg #273 (the Triglotta's translation, by Bente and Dau, as on
    bookofconcord.org, whose pages repeat the articles inside each part's opening page): the Preface,
    Part I, Part II's four articles and Part III's fifteen, as chapters 0-20."""
    text = gutenberg(273)
    text = text[text.index("Preface of Dr. Martin Luther."):]
    heads = (r"Preface of Dr\. Martin Luther\.|THE (?:FIRST|SECOND|THIRD) PART[^\n]*|Article [IVX]+: [^\n]+|"
             r"[IVX]+\. (?:Of|How) [^\n]+")
    out = gutenberg_sections(text, heads, first=0)
    expect(len(out) >= 20, f"Smalcald: {len(out)} parts")
    return out


def book_of_concord():
    home = _boc_page("/")
    books = {}
    for slug, title in CONCORD:
        if slug == "smalcald-articles":
            books[title] = smalcald()
            print(f"  {title}: {len(books[title])} parts (Gutenberg)")
            continue
        pages = [p for p in dict.fromkeys(re.findall(rf'href="(/{slug}/[\w/-]+/)"', home))
                 if not re.search(r"prefaratory-notes|signatories", p)] or [f"/{slug}/"]
        chapters, n = {}, 0
        for path in pages:
            for heading, paras in _boc_sections(_boc_page(path)):
                if not paras:
                    continue
                m = re.match(r"(?i)Article\s+([IVXL]+)\b", heading)
                n = roman(m.group(1)) if m and slug == "augsburg-confession" else n + 1
                chapter = {}
                for k, v in sorted(paras.items(), key=lambda kv: int(kv[0])):
                    v = "\n".join(re.sub(r"[ \t]+", " ", line).strip() for line in v.split("\n"))
                    if v.strip():
                        chapter[str(max(int(k), 1))] = (chapter.get(str(max(int(k), 1)), "") + "\n" + v).strip()
                first = next(iter(chapter))
                chapter[first] = f"*{heading}*\n{chapter[first]}" if heading else chapter[first]
                chapters[str(n)] = chapter
        expect(len(chapters) >= 1, f"{title}: nothing found")
        books[title] = chapters
        print(f"  {title}: {len(chapters)} articles/parts, {sum(map(len, chapters.values()))} paragraphs")
    save("book_of_concord.json", "Concordia Triglotta (1921)", books)


# ── Wikisource, rendered (so pages built from scans come with their text) ──────

def ws_html(title: str) -> str:
    import urllib.parse
    url = ("https://en.wikisource.org/w/api.php?action=parse&prop=text&format=json&formatversion=2&redirects=1&page="
           + urllib.parse.quote(title))
    raw = fetch("wsh_" + re.sub(r"[^\w]+", "_", title)[:150] + ".json", url)
    data = json.loads(raw)
    expect("parse" in data, f"Wikisource: {title}: {data.get('error', {}).get('info')}")
    return data["parse"]["text"]


def ws_elements(title: str) -> list:
    """[("h", heading) | ("p", paragraph)] of a rendered Wikisource page, without its header box,
    notes, page numbers and navigation; a paragraph wholly in bold counts as a heading."""
    h = ws_html(title)
    h = re.sub(r'(?is)<(div|table|span)[^>]*class="[^"]*(?:ws-noexport|header|navbox|licenseContainer|wst-header|'
               r'pagenum|ws-pagenum|reference|mw-editsection|wst-sidenote|sidenote)[^"]*"[^>]*>.*?</\1>', "", h)
    h = re.sub(r"(?is)<sup\b.*?</sup>|<style\b.*?</style>|<ol class=\"references\".*?</ol>", "", h)
    out = []
    for m in re.finditer(r"(?is)<(h[2-6])\b[^>]*>(.*?)</\1>|<(p|dd|li)\b[^>]*>(.*?)</\3>", h):
        if m.group(1):
            t = tidy(text_of(m.group(2)))
            if t:
                out.append(("h", t))
            continue
        inner = m.group(4)
        bold = re.fullmatch(r"(?is)\s*<(b|strong)\b[^>]*>(.*?)</\1>\s*", inner)
        t = text_of(inner)
        t = "\n".join(tidy(l) for l in t.split("\n") if tidy(l))
        if t and not re.search(r"Public domain|This work (?:was published|is in the public)|talk page for details|"
                               r"Layout \d$|PD-old|source document of this text", t):
            out.append(("h" if bold and len(t) < 160 else "p", t.strip("*") if bold else t))
    return out


def ws_chapters(elements: list, chapter: str, first: int = 1, title_lines: int = 1) -> dict:
    """{n: {paragraph: text}} with a chapter at each heading matching `chapter` (numbered on from
    `first`); other headings lead the next paragraph in italics; what precedes the first is dropped."""
    out, n, pending = {}, first - 1, ""

    def flush():
        # a short last line ("Amen."), but not a table of contents left over at the end
        if pending and " · " not in pending and n >= first and out[str(n)]:
            verses = out[str(n)]
            verses[str(len(verses) + 1)] = pending

    for kind, text in elements:
        if re.match(chapter, text) and "\n" not in text and len(text) < 200:
            flush()
            n += 1
            out[str(n)] = {}
            pending = text.replace("*", "")
            continue
        if kind == "h" or (len(text) < 70 and "\n" not in text and not re.search(r"[;,]$", text)):
            text = text.replace("*", "")
            pending = f"{pending} · {text}" if pending else text
            continue
        if n < first:
            continue
        verses = out[str(n)]
        verses[str(len(verses) + 1)] = (f"*{pending}*\n" if pending else "") + text
        pending = ""
    flush()
    return {k: v for k, v in out.items() if v}


# ── CCEL ThML ────────────────────────────────────────────────────────────────

def ccel(ref: str) -> str:
    author, work = ref.split("/")
    return fetch(f"ccel_{author}_{work}.xml", f"https://ccel.org/ccel/{author[0]}/{author}/{work}.xml")


def thml_paragraphs(fragment: str) -> list:
    """The paragraphs (and verse, line by line) of a ThML fragment, in order; headings left out."""
    out = []
    for m in re.finditer(r"(?is)<p\b[^>]*>(.*?)</p>|<verse\b[^>]*>(.*?)</verse>|<li\b[^>]*>(.*?)</li>", fragment):
        if m.group(2) is not None:
            lines = [text_of(l) for l in re.findall(r"(?is)<l\b[^>]*>(.*?)</l>", m.group(2))]
            text = "\n".join(l for l in lines if l)
        else:
            text = tidy(text_of(m.group(1) if m.group(1) is not None else m.group(3)))
        if text:
            out.append(text)
    return out


def thml_divs(xml: str, level: int) -> list:
    """[(title, fragment)] for every <div{level}> in order (its title, or its first heading)."""
    out = []
    for m in re.finditer(rf'(?is)<div{level}\b([^>]*)>(.*?)</div{level}>', xml):
        title = re.search(r'title="([^"]*)"', m.group(1))
        title = html_lib.unescape(title.group(1)).strip() if title else ""
        if not title:
            h = re.search(r"(?is)<h\d[^>]*>(.*?)</h\d>", m.group(2))
            title = text_of(h.group(1)) if h else ""
        out.append((title, m.group(2)))
    return out


def thml_flat(fragment: str) -> list:
    """A fragment's paragraphs with its inner headings (<hN> and inner divs' titles) in italics
    leading the paragraph after them."""
    out, pending = [], ""
    for m in re.finditer(r'(?is)<div\d\b[^>]*title="([^"]*)"|<h\d[^>]*>(.*?)</h\d>|<p\b[^>]*>.*?</p>|'
                         r'<verse\b[^>]*>.*?</verse>', fragment):
        if m.group(1) is not None or m.group(2) is not None:
            t = html_lib.unescape(m.group(1)) if m.group(1) is not None else text_of(m.group(2))
            t = tidy(t).strip("*")
            if t and t.lower() not in pending.lower():
                pending = f"{pending} · {t}" if pending else t
            continue
        for p in thml_paragraphs(m.group(0)):
            out.append(f"*{pending}*\n{p}" if pending else p)
            pending = ""
    return out


# ── Martin Luther ───────────────────────────────────────────────────────────

def between(text: str, start: str, end: str = None, nth: int = 1) -> str:
    """text from the nth line matching `start` to the first line after it matching `end`."""
    starts = list(re.finditer(rf"(?m)^[ \t]*(?:{start})[ \t]*$", text))
    expect(len(starts) >= nth, f"no {start!r} (#{nth})")
    s = starts[nth - 1].end()
    e = re.search(rf"(?m)^[ \t]*(?:{end})[ \t]*$", text[s:]) if end else None
    return text[s:s + e.start() if e else len(text)]


def drop_footnotes(t: str) -> str:
    """Without the editors' footnote blocks (from "FOOTNOTES" to the next heading in capitals) or
    the [n] markers in the text."""
    t = re.sub(r"(?ms)^[ \t]*FOOTNOTES[ \t]*$.*?(?=^[ \t]*[A-Z][A-Z ,.;:'\-]{8,}[ \t]*$|\Z)", "", t)
    return re.sub(r"\[\d+\]", "", t)


def paras_of(chunk: str) -> list:
    return [t for t in (tidy(p) for p in paragraphs(chunk)) if t and not re.fullmatch(r"\[?Footnote.*", t)]


def ninety_five_theses() -> dict:
    """sacred-texts.com: 'Out of love for the truth...' (0), then each thesis by its number."""
    raw = html_lib.unescape(re.sub(r"<[^>]+>", "", sacred_text("chr/the9510.txt")))
    body = raw[raw.find("Out of love"):]
    body = body[:body.find("_____")]                      # (then the Latin text and the transcriber's notes)
    parts = re.split(r"(?m)^\s*(\d{1,2}) ?\.\s+", body)                # ("71 . He who speaks")
    out = {"0": {"1": tidy(parts[0])}}
    for n, t in zip(parts[1::2], parts[2::2]):
        out[str(int(n))] = {"1": tidy(t)}
    expect(len(out) == 96, f"95 Theses: {len(out) - 1}")
    return out


def luther_works_ii() -> dict:
    """The three treatises of 1520 and the Wittenberg sermons, from the Philadelphia edition's
    second volume (Gutenberg #34904), each from its title (after the translator's introduction)."""
    t = drop_footnotes(gutenberg(34904))
    letter = between(t, "AN OPEN LETTER TO THE CHRISTIAN NOBILITY OF THE GERMAN NATION",
                     "A PRELUDE ON THE BABYLONIAN CAPTIVITY OF THE CHURCH", nth=2)
    nobility = gutenberg_sections("DEDICATION TO NICHOLAS VON AMSDORF\n" + letter.split("NICHOLAS VON AMSDORF,", 1)[-1],
                                  r"DEDICATION TO NICHOLAS VON AMSDORF|I\. THE THREE WALLS OF THE ROMANISTS|II\. ABUSES TO BE DISCUSSED IN "
                                  r"COUNCILS|III\. PROPOSALS FOR REFORM", first=0)
    captivity = gutenberg_sections(
        "INTRODUCTION\n" + between(t, "THE BABYLONIAN CAPTIVITY OF THE CHURCH", "A TREATISE ON CHRISTIAN LIBERTY WITH.*"),
        r"INTRODUCTION|THE SACRAMENT OF [A-Z ]+|CONFIRMATION|MARRIAGE|ORDERS|INDULGENCES ARE A KNAVISH TRICK.*")
    liberty = gutenberg_sections(
        between(t, "LETTER TO POPE LEO X.", "A BRIEF EXPLANATION OF THE TEN COMMANDMENTS.*", nth=1)
        .replace("\nLETTER", "\nLETTER"), r"A TREATISE ON CHRISTIAN LIBERTY", first=1)
    leo = paras_of(between(t, "LETTER TO POPE LEO X.", "A TREATISE ON CHRISTIAN LIBERTY"))
    liberty = {"0": numbered(leo, "Letter to Pope Leo X"), **liberty}
    sermons = gutenberg_sections(between(t, "EIGHT SERMONS BY DR. MARTIN LUTHER", r"THAT DOCTRINES OF MEN ARE TO BE REJECTED"),
                                 r"THE (?:FIRST|SECOND|THIRD|FOURTH|FIFTH|SIXTH|SEVENTH) SERMON\b.*|A SHORT SUMMARY.*")
    for name, book, least in (("Nobility", nobility, 4), ("Captivity", captivity, 4), ("Liberty", liberty, 2),
                              ("Wittenberg Sermons", sermons, 8)):
        expect(len(book) >= least, f"{name}: {len(book)} parts")
    return {"An Open Letter to the Christian Nobility": nobility, "The Babylonian Captivity of the Church": captivity,
            "A Treatise on Christian Liberty": liberty, "The Eight Wittenberg Sermons": dict(list(sermons.items())[:8])}


def good_works() -> dict:
    """Gutenberg #418: the dedication (0), then a part for each run of Luther's numbered paragraphs
    (the numbering starts again at I with each commandment)."""
    t = gutenberg(418)
    dedication = paras_of(between(t, "DEDICATION", "THE TREATISE"))
    body = t[t.index("THE TREATISE") + len("THE TREATISE"):]
    body = body[:body.find("FOOTNOTES")] if "FOOTNOTES" in body else body
    pieces = re.split(r"\n\n *([IVXL]+)\. ", "\n\n" + body)
    out, part, last = {"0": numbered(dedication, "Dedication")}, 0, 10 ** 6
    for num, chunk in zip(pieces[1::2], pieces[2::2]):
        n = roman(num)
        if n <= last:
            part += 1
            out[str(part)] = {}
        last = n
        out[str(part)][str(n)] = "\n".join(paras_of(chunk))
    expect(part >= 4, f"Good Works: {part} parts")
    return out


def bondage_of_the_will() -> dict:
    """CCEL (Cole's translation, 1823): the translator's and Luther's sections, a chapter each (the
    prefatory matter as 0)."""
    xml = ccel("luther/bondage")
    out, front = {}, []
    for title, frag in thml_divs(xml, 1):
        if re.search(r"(?i)title page|^index", title):
            continue
        subs = thml_divs(frag, 2)
        if not subs:
            front += thml_flat(frag) if re.search(r"(?i)^introduction", title) else []     # (Luther's letter to Erasmus)
            continue
        for stitle, sfrag in subs:
            m = re.match(r"(?i)Section ([IVXLC]+)", stitle)
            if m:
                out[str(roman(m.group(1)))] = numbered(thml_flat(sfrag), f"{title} · {stitle}")
    if front:
        out = {"0": numbered(front), **out}
    expect(len(out) >= 150, f"Bondage: {len(out)} sections")
    return out


def galatians() -> dict:
    """Gutenberg #1549 (Graebner's abridgment of the 1575 translation): by chapter and verse of
    Galatians, each verse's comments together."""
    t = gutenberg(1549)
    out = {}
    for ch in re.finditer(r"(?ms)^CHAPTER (\d)\s*$(.*?)(?=^CHAPTER \d\s*$|\Z)", t):
        verses = {}
        for v in re.finditer(r"(?ms)^[ \t]*VERSE (\d+)\.(.*?)(?=^[ \t]*VERSE \d+\.|\Z)", ch.group(2)):
            paras = paras_of(v.group(2))
            if paras:
                paras[0] = f"*{paras[0]}*" if len(paras) > 1 and len(paras[0]) < 160 else paras[0]
                verses[v.group(1)] = (verses.get(v.group(1), "") + "\n" + "\n".join(paras)).strip()
        out[ch.group(1)] = verses
    expect(list(out) == [str(i) for i in range(1, 7)], f"Galatians chapters {list(out)}")
    return out


def table_talk() -> dict:
    """Gutenberg #9841 (Hazlitt's selection from Bell's translation): a chapter for each of its
    headings ("Of Prayer"), each entry under its own italic title a verse."""
    t = gutenberg(9841)
    t = t[t.index("OF THE NATURE OF THE WORLD."):]
    t = t[:t.find("FOOTNOTES")] if "FOOTNOTES" in t else t
    out, topic, title, verses = {}, "", "", None
    for p in paragraphs(t):
        if re.fullmatch(r"[A-Z][A-Z ,.;'-]{6,}", p):                      # a topic ("OF PRAYER.")
            topic = p.rstrip(".").title()
            verses = out.setdefault(str(len(out) + 1), {})
            continue
        if re.fullmatch(r"_[^_]+_\.?", p):                                 # an entry's title
            title = p.strip("_. ")
            continue
        if verses is None:
            continue
        if title or not verses:
            lead = " · ".join(x for x in (topic if not verses else "", title) if x)
            verses[str(len(verses) + 1)] = (f"*{lead}*\n" if lead else "") + tidy(p)
            title = ""
        else:
            last = str(len(verses))
            verses[last] += "\n" + tidy(p)
    out = {k: v for k, v in out.items() if v}
    out = {str(i): v for i, v in enumerate(out.values(), 1)}
    expect(len(out) >= 8, f"Table Talk: {len(out)} chapters")
    return out


def luther_sermons() -> dict:
    """sacred-texts.com: Luther's sermons (Lenker's translation), one a chapter."""
    pages = [("enemies.htm", "Enemies of the Cross of Christ"), ("highpre.htm", "Christ Our Great High Priest"),
             ("lawgosp.htm", "The Twofold Use of the Law and Gospel"), ("preoff.htm", "Of the Office of Preaching"),
             ("sower.htm", "The Parable of the Sower"), ("chrsuff.htm", "Christ's Holy Sufferings"),
             ("tochrist.htm", "On Faith and Coming to Christ"), ("wheat.htm", "The Wheat and the Tares")]
    out = {}
    for i, (page, title) in enumerate(pages, 1):
        text = st_page(f"chr/luther/{page}")
        paras = [tidy(p) for p in re.split(r"\n\s*\n", text) if len(tidy(p)) > 40
                 and not re.fullmatch(r"Sacred Texts .* Index", tidy(p))]     # the site's breadcrumb menu
        out[str(i)] = numbered(paras, title)
    return out


def luther():
    books = {"Ninety-Five Theses": ninety_five_theses(), **luther_works_ii(),
             "Treatise on Good Works": good_works(), "The Bondage of the Will": bondage_of_the_will(),
             "Luther on Galatians": galatians(), "Table Talk": table_talk(), "Sermons of Martin Luther": luther_sermons()}
    sources = {"Ninety-Five Theses": "Martin Luther (1517)",
               "Treatise on Good Works": "Philadelphia edition (1915)",
               "The Bondage of the Will": "trans. Henry Cole (1823)",
               "Luther on Galatians": "trans. Theodore Graebner",
               "Table Talk": "trans. William Hazlitt",
               "Sermons of Martin Luther": "trans. J. N. Lenker"}
    for b in ("An Open Letter to the Christian Nobility", "The Babylonian Captivity of the Church",
              "A Treatise on Christian Liberty", "The Eight Wittenberg Sermons"):
        sources[b] = "Philadelphia edition (1915)"
    for b, ch in books.items():
        print(f"  {b}: {len(ch)} chapters, {sum(map(len, ch.values()))} passages")
    save("luther.json", "Martin Luther", books, sources)


# ── John Calvin ─────────────────────────────────────────────────────────────

ORDINALS = {"FIRST": 1, "SECOND": 2, "THIRD": 3, "FOURTH": 4}
SMALL = {"a", "an", "and", "as", "at", "by", "for", "from", "in", "into", "of", "on", "or", "the", "to", "with", "is",
         "are", "be", "not", "but", "its", "his", "their", "that", "this", "which", "who", "what", "how", "when"}


def smart_title(s: str) -> str:
    """"THE KNOWLEDGE OF GOD AND OF OURSELVES" -> "The Knowledge of God and of Ourselves"."""
    words = re.split(r"(\s+|—|-)", s.lower())
    return "".join(w if (i and w in SMALL) else w[:1].upper() + w[1:] for i, w in enumerate(words))


def _institutes_chapter(text: str, title: str) -> dict:
    """{section: text} from a chapter page: the page lists its sections' summaries ("1. The sum of
    true wisdom..."), then gives the sections, numbered again from 1."""
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    starts = [i for i, l in enumerate(lines) if re.match(r"1\.\s", l)]
    expect(starts, f"{title}: no sections")
    body = lines[starts[-1]:] if len(starts) > 1 else lines[starts[0]:]
    out, current = {}, None
    for l in body:
        m = re.match(r"(\d+)\.\s+(.*)", l)
        if m and (current is None or int(m.group(1)) == int(current) + 1):
            current = m.group(1)
            out[current] = tidy(m.group(2))
        elif current:
            out[current] += "\n" + tidy(l)
    first = next(iter(out))
    out[first] = f"*{title}*\n{out[first]}"
    return out


def institutes() -> tuple:
    """sacred-texts.com (Beveridge's translation, 1845): {"book.chapter": {section: text}}, cited
    as Calvin's readers do (Institutes 1.15.3); and the prefatory address to Francis I apart."""
    book, out, address = 0, {}, {}
    for page, label in st_index("chr/calvin/inst/index.htm"):
        m = re.match(r"BOOK (FIRST|SECOND|THIRD|FOURTH)", label)
        if m:
            book = ORDINALS[m.group(1)]
            continue
        text = st_page(page)
        if label.startswith("PREFATORY ADDRESS"):
            address = numbered(paras_of(text.split("\n", 2)[-1] if text.count("\n") > 2 else text))
            continue
        m = re.match(r"CHAPTER (\d+)\.?\s*-?\s*(.*)", label)            # ("CHAPTER 18 - OF THE POPISH MASS")
        if m and book:
            title = smart_title(m.group(2).strip().rstrip("."))
            out[f"{book}.{m.group(1)}"] = _institutes_chapter(text, f"Book {book}, Chapter {m.group(1)}: {title}")
    expect(len(out) >= 80, f"Institutes: {len(out)} chapters")                # (18 + 17 + 25 + 20)
    return out, address


def calvin():
    inst, address = institutes()
    relics = gutenberg(32136)                       # (after the translator's long Introductory Dissertation)
    relics = relics[relics.index("CALVIN’S TREATISE ON RELICS"):relics.index("POSTSCRIPT.")]
    relics = gutenberg_sections("ADMONITION\n" + relics.split("\n", 1)[1],
                                r"ADMONITION|ST [A-Z][A-Z ,.—]+\.|THE OTHER APOSTLES\.|LAZARUS, MARY MAGDALENE, ETC\.|"
                                r"THE HOLY INNOCENTS\.")
    relics = {c: {v: re.sub(r"\(\d+\)", "", t) for v, t in vs.items()} for c, vs in relics.items()}   # (the notes' markers)
    address = {k: re.sub(r"(?<=[.,;:])\s\d{1,2}(?=\s|$)", "", v) for k, v in address.items()}       # ("CHRIST. 2")
    books = {"Institutes of the Christian Religion": inst,
             "Prefatory Address to Francis I": {str(i): {"1": p} for i, p in enumerate(address.values(), 1)},
             "A Treatise on Relics": relics}
    for b, ch in books.items():
        print(f"  {b}: {len(ch)} chapters, {sum(map(len, ch.values()))} passages")
    save("calvin.json", "John Calvin", books, {
        "Institutes of the Christian Religion": "trans. Henry Beveridge (1845)",
        "Prefatory Address to Francis I": "trans. Henry Beveridge (1845)",
        "A Treatise on Relics": "trans. Valerian Krasinski (1854)"})


# ── the Reformed and other confessions ──────────────────────────────────────

def st_elements(path: str) -> list:
    """[("h"|"p", text)] of a sacred-texts.com page, by its HTML paragraphs and headings."""
    page = sacred_text(path)
    page = re.sub(r"(?is)<(script|style|nav)\b.*?</\1>", "", page)
    out = []
    for m in re.finditer(r"(?is)<(h[1-6]|p)\b[^>]*>(.*?)(?=<(?:/?p\b|h[1-6]\b|/h[1-6]|hr|div|/body)[^>]*>)", page):
        t = "\n".join(tidy(l) for l in text_of(m.group(2)).split("\n") if tidy(l))
        if t and "Sacred Text" not in t and not re.fullmatch(r"(?:Next|Previous|Index)[^\n]*", t):
            out.append(("h" if m.group(1).lower().startswith("h") else "p", t))
    return out


def heidelberg() -> dict:
    """sacred-texts.com: the 129 questions, each with its answer, the Lord's Day leading its first
    question; the letters keying the proof-texts, and the proof-texts, left out."""
    text = st_page("chr/heidcat.htm")
    text = text[text.index("1. Lord's Day"):]
    # numbered by their order: the first is set out "Question." and the page misprints 52 as "Q. 62."
    marks = list(re.finditer(r"(?m)^\s*(?:Q\. \d+\.|Question\.)\s*$|^\s*(\d+)\. Lord's Day\s*$", text))
    out, day = {}, ""
    for i, m in enumerate(marks):
        if m.group(1):
            day = f"Lord's Day {m.group(1)}"
            continue
        body = text[m.end():marks[i + 1].start() if i + 1 < len(marks) else len(text)]
        body = re.split(r"(?m)^\s*The (?:First|Second|Third) Part\b.*$|^\s*Of (?:God|The|Prayer)\b[^\n]*$", body)[0]
        q, _, a = re.split(r"(?m)^\s*(A\.|Answer\.)\s*$", body, maxsplit=1)[0::1][:3] if re.search(
            r"(?m)^\s*(?:A\.|Answer\.)\s*$", body) else (body, "", "")
        a = re.split(r"(?m)^\s*\(a\)", a)[0]                                    # (the proof-texts)
        a = re.sub(r"\s*\([a-z]\)", "", a)
        n = str(len(out) + 1)
        out[n] = {"1": (f"*{day}*\n" if day else "") + f"*{tidy(q)}*\n{tidy(a)}"}
        day = ""
    expect(len(out) == 129, f"Heidelberg: {len(out)} questions")
    return out


def westminster_shorter() -> dict:
    text = st_page("chr/westcat1.htm")
    out = {}
    for m in re.finditer(r"(?s)Q(\d+)[:.]\s*(.*?)\s*A\1[:.]\s*(.*?)(?=\s*Q\d+[:.]|\Z)", text):     # ("Q20." or "Q45:")
        out[m.group(1)] = {"1": f"*{tidy(m.group(2))}*\n{tidy(m.group(3))}"}
    expect(len(out) == 107, f"Shorter Catechism: {len(out)} questions")
    return out


def westminster_larger() -> dict:
    """Wikisource (sacred-texts.com's copy stops at question 99)."""
    out = {}
    for kind, text in ws_elements("Westminster Larger Catechism"):
        m = re.match(r"(?s)Question (\d+):\s*(.*?)\nAnswer:\s*(.*)", text)
        if m:
            out[m.group(1)] = {"1": f"*{tidy(m.group(2))}*\n{tidy(m.group(3))}"}
    expect(len(out) == 196, f"Larger Catechism: {len(out)} questions")
    return out


def second_helvetic() -> dict:
    els = st_elements("chr/2helvcnf.htm")
    return ws_chapters(els, r"CHAPTER\s+[IVXL]+$")


def baptist_1689() -> dict:
    xml = ccel("anonymous/bcf")
    out = {}
    for title, frag in thml_divs(xml, 2):
        m = re.match(r"Chapter ([IVXL]+)\.\s*(.*)", title)
        if m:
            paras = [p for p in thml_paragraphs(frag)]
            out[str(roman(m.group(1)))] = numbered(paras, f"Chapter {m.group(1)}. {m.group(2)}".rstrip("."))
    expect(len(out) == 32, f"1689: {len(out)} chapters")
    return out


RDC = "The Constitution of the Reformed Dutch Church of North America/"
CONFESSIONS = {
    "Heidelberg Catechism": ("1563 text", heidelberg),
    "Second Helvetic Confession": ("1566 text", second_helvetic),
    "Belgic Confession": ("The Belgic Confession (1561), as revised at Dort (1619), from The Constitution of the "
                          "Reformed Dutch Church (1840), Wikisource",
                          lambda: ws_chapters(ws_elements(RDC + "The Confession of Faith"), r"(?:Article )?[IVXL]+\.(?:\s|$)")),
    "Canons of Dort": ("The Canons of the Synod of Dort (1619), from The Constitution of the Reformed Dutch Church "
                       "(1840), Wikisource",
                       lambda: ws_chapters(ws_elements(RDC + "Canons of the Synod of Dordrecht"),
                                           r"(?:FIRST|SECOND|THIRD|FOURTH|FIFTH)(?: AND FOURTH)? HEADS? OF DOCTRINE")),
    "Scots Confession": ("1560 text",
                         lambda: ws_chapters(ws_elements("Scots Confession"), r"The Preface|Chapter \d+:", first=0)),
    "Westminster Confession of Faith": ("The Westminster Confession of Faith (1646), Wikisource (transcribed from the "
                                        "1646 manuscript, tercentenary edition, 1946)",
                                        lambda: ws_chapters(ws_elements("The Confession of Faith of the Assembly of "
                                                                        "Divines at Westminster"), r"CHAPTER [IVXL]+\.?$")),
    "Westminster Shorter Catechism": ("1647 text", westminster_shorter),
    "Westminster Larger Catechism": ("1647 text", westminster_larger),
    "Thirty-Nine Articles": ("Church of England (1571)",
                             lambda: ws_chapters(ws_elements("Thirty-Nine Articles of Religion"), r"[IVXL]+\. ")),
    "Methodist Articles of Religion": ("John Wesley (1784)",
                                       lambda: ws_chapters(ws_elements("Articles of Religion (Methodist)"),
                                                           r"Article [IVXL]+")),
    "Second London Baptist Confession": ("1689 text", baptist_1689),
}
EXPECTED = {"Second Helvetic Confession": 30, "Belgic Confession": 37, "Canons of Dort": 4, "Scots Confession": 26,
            "Westminster Confession of Faith": 33, "Thirty-Nine Articles": 39, "Methodist Articles of Religion": 25}


def confessions():
    books, sources = {}, {}
    for title, (source, build) in CONFESSIONS.items():
        books[title] = build()
        sources[title] = source
        n = len(books[title])
        expect(n >= EXPECTED.get(title, 1), f"{title}: {n} chapters")
        print(f"  {title}: {n} chapters, {sum(map(len, books[title].values()))} passages")
    save("confessions.json", "Protestant confessions of faith", books, sources)


# ── Knox, Latimer, the Anglican divines, the Wesleys ─────────────────────────

FRONT = r"(?i)title page|^indexes|^index of|^contents$|prefatory material|^a sketch of the life|^introductory note|" \
        r"^editor'?s note|^list of works"


def ccel_chapters(ref: str, level: int, inside: str = None, skip: str = FRONT, first: int = 1) -> dict:
    """{n: {paragraph: text}}: a chapter for each <div{level}> of a CCEL book (only those inside the
    <div{level-1}> titled `inside`, if given), with its title and inner headings in italics."""
    xml = ccel(ref)
    if inside:
        parent = next((f for t, f in thml_divs(xml, level - 1) if re.search(inside, t)), None)
        expect(parent is not None, f"{ref}: no {inside!r}")
        xml = parent
    out = {}
    for title, frag in thml_divs(xml, level):
        if skip and re.search(skip, title):
            continue
        paras = thml_flat(frag)
        if paras:
            out[str(first + len(out))] = numbered(paras, title if title and not paras[0].startswith("*") else "")
    return out


def numbered_sections(chapters: dict) -> dict:
    """Paragraphs that begin with their section's number ("12. ...") regrouped as {section: paragraphs}."""
    out, current = {}, "0"
    for vs in chapters.values():
        for text in vs.values():
            m = re.match(r"(?:\*[^*\n]*\*\n)?(\d+)\.\s", text)
            if m and int(m.group(1)) == int(current) + 1:
                current = m.group(1)
            out.setdefault(current, {})
            out[current][str(len(out[current]) + 1)] = text
    return out


def knox():
    blast = gutenberg(9660)
    blast = blast[blast.find("THE FIRST BLAST OF THE TRUMPET"):]
    books = {
        "The History of the Reformation in Scotland": ccel_chapters(
            "knox/history_reformation", 2, inside=r"Reformation of Religion in Scotland"),
        "The First Blast of the Trumpet": {str(i): {"1": p} for i, p in enumerate(paras_of(drop_footnotes(blast)), 1)},
        "A Treatise on Prayer": {str(i): {"1": p} for i, p in
                                 enumerate((p for c in ccel_chapters("knox/prayer", 1).values() for p in c.values()), 1)},
    }
    report(books)
    save("knox.json", "John Knox", books, {
        "The History of the Reformation in Scotland": "John Knox (1587)",
        "The First Blast of the Trumpet": "John Knox (1558)",
        "A Treatise on Prayer": "John Knox (1554)"})


def latimer():
    xml = ccel("latimer/sermons")
    out = {}
    for title, frag in thml_divs(xml, 1):
        if re.search(FRONT, title):
            continue
        subs = thml_divs(frag, 2)
        for stitle, sfrag in (subs or [(title, frag)]):
            paras = thml_flat(sfrag)
            if len(paras) > 2:
                out[str(len(out) + 1)] = numbered(paras, stitle if not paras[0].startswith("*") else "")
    books = {"Sermons of Hugh Latimer": out}
    report(books)
    save("latimer.json", "Everyman edition (1906)", books)


def _poem_lines(html: str) -> list:
    """Stanzas ([lines]) of a rendered Wikisource poem."""
    html = re.sub(r"(?is)<style\b.*?</style>", "", html)
    html = re.sub(r'(?is)<span class="dropinitial[^"]*">(.*?)</span></span></span>\s*', r"\1", html)
    stanzas = []
    for st in re.findall(r'(?is)<div class="ws-poem-stanza"[^>]*>(.*?)</div>', html):
        lines = [tidy(text_of(l)) for l in re.findall(r'(?is)<span class="ws-poem-line"[^>]*>(.*?)<span class="ws-poem-break"', st)]
        lines = [l for l in lines if l]
        if lines:
            stanzas.append(lines)
    if not stanzas:                                     # (a poem set as paragraphs, with <br> lines)
        for p in re.findall(r"(?is)<p\b[^>]*>(.*?)</p>", html.split('class="prp-pages-output"', 1)[-1]):
            lines = [tidy(l) for l in text_of(p).split("\n") if tidy(l) and not tidy(l).startswith("§")]
            if lines:
                stanzas.append(lines)
    return stanzas


def herbert_temple() -> dict:
    """Wikisource (the 1633 second edition): each poem a chapter, each stanza a verse."""
    index = wikisource("The Temple: Sacred Poems and Private Ejaculations")
    titles = re.findall(r"\[\[(?:The Temple: Sacred Poems and Private Ejaculations)?/([^|\]]+)\|([^\]]+)\]\]", index)
    out = {}
    for page, label in titles:
        if re.search(r"(?i)\btable\b|\bindex\b", page + " " + label):          # (the book's own index of poems)
            continue
        html = ws_html(f"The Temple: Sacred Poems and Private Ejaculations/{page}")
        stanzas = _poem_lines(html)
        if not stanzas:
            print(f"  ? no text: {label}")
            continue
        verses = {str(i): "\n".join(s) for i, s in enumerate(stanzas, 1)}
        verses["1"] = f"*{label}*\n{verses['1']}"
        out[str(len(out) + 1)] = verses
    expect(len(out) >= 150, f"The Temple: {len(out)} poems")
    return out


def anglican_divines():
    books = {
        "The Temple": herbert_temple(),
        "Private Devotions of Lancelot Andrewes": ccel_chapters("andrewes/devotions1", 2,
                                                                skip=FRONT + r"|^title$|original preface|intoduction|^contents"),
        "Holy Living": ccel_chapters("taylor/holy_living", 1),
        "Holy Dying": ccel_chapters("taylor/holy_dying", 1, skip=FRONT + r"|^dedication"),
        "A Serious Call to a Devout and Holy Life": ccel_chapters("law/serious_call", 1),
        "Laws of Ecclesiastical Polity": hooker(),
        **homilies(),
        **donne(),
    }
    report(books)
    save("anglican_divines.json", "The Anglican divines", books, {
        "The Temple": "George Herbert (1633)",
        "Private Devotions of Lancelot Andrewes": "trans. J. H. Newman and J. M. Neale",
        "Holy Living": "Jeremy Taylor (1650)",
        "Holy Dying": "Jeremy Taylor (1651)",
        "A Serious Call to a Devout and Holy Life": "William Law (1729)",
        "Laws of Ecclesiastical Polity": "ed. John Keble",
        "The Book of Homilies, First Book": "Thomas Cranmer et al. (1547)",
        "Bonner's Homilies": "Edmund, Bishop of London (1555)",
        "The Book of Homilies, Second Book": "John Jewel et al. (1563)",
        "Donne's LXXX Sermons": "John Donne (1640)",
        "Donne's Fifty Sermons": "John Donne (1649)",
        "Donne's XXVI Sermons": "John Donne (1661)",
        "Holy Sonnets": "John Donne"})


def wesley():
    sermons = {}
    for title, frag in thml_divs(ccel("wesley/sermons"), 2):
        m = re.search(r"(?is)<h\d[^>]*>(?:<[^>]+>)*\s*Sermon (\d+)", frag)       # (by his own numbering)
        if m:
            frag = re.sub(r"(?is)<h\d[^>]*>.*?</h\d>", "", frag, count=2)
            paras = thml_flat(frag)
            if paras:
                sermons[m.group(1)] = numbered(paras, f"Sermon {m.group(1)}: {smart_title(title)}")
    books = {
        "Sermons of John Wesley": sermons,
        "A Plain Account of Christian Perfection": numbered_sections(
            ccel_chapters("wesley/perfection", 2, inside=r"Plain Account")),
        "The Journal of John Wesley": ccel_chapters("wesley/journal", 2, inside=r"^The Journal of John Wesley"),
    }
    expect(len(sermons) >= 100, f"Wesley: {len(sermons)} sermons")
    report(books)
    save("wesley.json", "John Wesley", books, {
        "Sermons of John Wesley": "John Wesley",
        "A Plain Account of Christian Perfection": "John Wesley (1766)",
        "The Journal of John Wesley": "John Wesley"})


# ── texts the owner supplied (scripts/sources/, not in git) ──────────────────

SOURCES = Path(__file__).resolve().parent / "sources"


def homilies() -> dict:
    """scripts/sources/homilies.json: [{num, title, paragraphs}] in three runs -- the First Book of
    Homilies (1547, largely Cranmer's), Bishop Bonner's Catholic homilies under Mary (1555), and
    the Second Book (1563, largely Jewel's); each homily a chapter, each paragraph a verse."""
    items = json.loads((SOURCES / "homilies.json").read_text(encoding="utf-8"))
    runs, current, last = [], None, 10 ** 6
    for h in items:
        if h["num"] <= last:
            current = {}
            runs.append(current)
        last = h["num"]
        paras = [tidy(p) for p in h["paragraphs"] if tidy(p)]
        blurb = next((i for i, p in enumerate(paras) if re.match(r"The Reformation period has long been seen|ISBN|Gerald Bray \(ed\.\)$", p)), None)
        paras = paras[:blurb] if blurb is not None else paras      # (a modern book's jacket copy, at the end)
        current[str(h["num"])] = numbered(paras, h["title"])
    expect([len(r) for r in runs] == [12, 13, 21], f"homilies: runs {[len(r) for r in runs]}")
    return dict(zip(["The Book of Homilies, First Book", "Bonner's Homilies", "The Book of Homilies, Second Book"], runs))


def donne() -> dict:
    """scripts/sources/donne_modernized.txt: the LXXX, Fifty and XXVI Sermons and the Holy Sonnets,
    in modernized spelling. Each sermon is found by the number its heading gives ("SERMON XIV.",
    "SERM. I.", "Serm. 26."); the 1661 XXVI Sermons misnumbers (no 9, 20 or 24, an unnumbered
    "Second Sermon"), so its sermons are numbered in the order they come."""
    text = (SOURCES / "donne_modernized.txt").read_text(encoding="utf-8")
    parts = re.split(r"(?m)^={10,}\n(.+)\n={10,}$", text)
    names = {"LXXX SERMONS (1640)": "Donne's LXXX Sermons", "FIFTY SERMONS (1649)": "Donne's Fifty Sermons",
             "XXVI SERMONS (1661)": "Donne's XXVI Sermons", "HOLY SONNETS": "Holy Sonnets"}
    books = {}
    for name, body in zip(parts[1::2], parts[2::2]):
        title = names[name.strip()]
        if title == "Holy Sonnets":
            out = {}
            for m in re.finditer(r"(?ms)^SONNET ([IVXL]+)\s*$(.*?)(?=^SONNET [IVXL]+\s*$|\Z)", body):
                lines = [l.strip() for l in m.group(2).split("\n") if l.strip() and l.strip() != "* * *"]
                out[str(roman(m.group(1)))] = {"1": "\n".join(lines)}
            books[title] = out
            continue
        lines = body.split("\n")
        heads, last = [], 0
        for i, l in enumerate(lines):
            if len(l) > 220 or not l.strip():
                continue
            nums = [roman(x) for x in re.findall(r"\bSERM(?:ON|\.)\s*([IVXLC]+)\b", l)]
            nums += [int(x) for x in re.findall(r"\bSerm\.\s*(\d+)", l)] + [int(x) for x in re.findall(r"^The (\d+) Sermon", l)]
            second = re.match(r"THE SECOND SERMON\b", l)
            if (nums and any(last < n <= last + 3 for n in nums)) or second:
                last = min(n for n in nums if n > last) if nums and not second else last
                heads.append((i, l.strip()))
        out = {}
        for k, (i, head) in enumerate(heads):
            end = heads[k + 1][0] if k + 1 < len(heads) else len(lines)
            paras = [tidy(p) for p in paragraphs("\n".join(lines[i + 1:end])) if tidy(p)]
            if paras:
                n = str(len(out) + 1)
                head = re.sub(r"\s*Serm\.\s*\d+\.?\s*", " ", head).strip()
                out[n] = numbered(paras, smart_title(head) if head.isupper() else head)
        books[title] = out
    counts = {b: len(v) for b, v in books.items()}
    expect(counts.get("Donne's LXXX Sermons") == 80 and counts.get("Donne's Fifty Sermons") == 50
           and counts.get("Donne's XXVI Sermons", 0) >= 23 and counts.get("Holy Sonnets", 0) >= 19, f"Donne: {counts}")
    return books


def hooker() -> dict:
    """scripts/sources/hooker_works_vol1.epub (Keble's edition, Online Library of Liberty): the
    Preface and Books I-IV of the Laws of Ecclesiastical Polity, a chapter per chapter of Hooker's
    ("Laws of Ecclesiastical Polity 1.3", the Preface as book 0), a verse per paragraph; the
    editors' footnotes, margin summaries and page numbers left out."""
    import zipfile
    page = zipfile.ZipFile(SOURCES / "hooker_works_vol1.epub").read("Hooker_0172-01.html").decode("utf-8", "replace")
    page = page[page.index("TO THEM THAT SEEK (AS THEY TERM IT)"):]
    page = page[page.index("</h2>") + 5:]
    notes = page.find('class="type-footnote')                         # (the notes, all gathered after Book IV)
    page = page[:notes] if notes > 0 else page
    page = re.sub(r'(?is)<div[^>]*class="type-footnote[^"]*"[^>]*>.*?</div>', "", page)
    page = re.sub(r'(?is)<span class="pb">.*?</span></span>|<span[^>]*class="type-margin"[^>]*><span>.*?</span></span>|'
                  r'<a[^>]*class="footnote-link[^"]*"[^>]*>.*?</a>|<ul\b.*?</ul>', "", page)
    out, book, chapter = {}, 0, 0
    for m in re.finditer(r"(?is)<h2[^>]*>(.*?)</h2>|<p\b[^>]*>(.*?)</p>", page):
        if m.group(1) is not None:
            h = text_of(m.group(1))
            b = re.match(r"THE (FIRST|SECOND|THIRD|FOURTH) BOOK", h)
            if b:
                book, chapter = ORDINALS[b.group(1)], 0
            continue
        inner = m.group(2)
        label = re.match(r'(?is)\s*<span id="[^"]*_label_\d+">([IVXL]+)\.</span>', inner)
        if label:
            chapter = roman(label.group(1))
            inner = inner[label.end():]
        text = tidy(text_of(inner))
        if not text or re.fullmatch(r"\[.*\]", text):                      # (an editor's bracketed note)
            continue
        chapter = chapter or 1                                             # (a book's first chapter has no numeral)
        key = f"{book}.{chapter}"
        verses = out.setdefault(key, {})
        if not verses:
            text = f"*{'Preface' if book == 0 else f'Book {book}'}, Chapter {chapter}*\n{text}"
        verses[str(len(verses) + 1)] = text
    books_found = sorted({k.split(".")[0] for k in out})
    expect(books_found == ["0", "1", "2", "3", "4"], f"Hooker: books {books_found}")
    return out


def report(books: dict) -> None:
    for b, ch in books.items():
        print(f"  {b}: {len(ch)} chapters, {sum(map(len, ch.values()))} passages")


BUILDERS = {"concord": book_of_concord, "luther": luther, "calvin": calvin, "confessions": confessions,
            "knox": knox, "latimer": latimer, "divines": anglican_divines, "wesley": wesley}

if __name__ == "__main__":
    for name in (sys.argv[1:] or BUILDERS):
        BUILDERS[name]()
