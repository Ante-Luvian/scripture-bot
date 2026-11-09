"""
Gnostic and apocryphal texts from the Gnostic Society Library (gnosis.org), to fill in what the bot's other
editions leave out (2026-11-09):

    the Nag Hammadi tractates missing from Zinner's translation (data/gnostic/nag_hammadi_zinner.json) --
    the Secret Book (Apocryphon) of John, the Gospel of Truth, the Gospel of Philip, the First Apocalypse of
    James -- in the Coptic Gnostic Library Project's translations, as gnosis.org gives them (each translator
    cited); a chapter each, a paragraph a verse.

    python scripts/build_gnosis.py
"""
import html
import json
import re
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CACHE = Path(__file__).resolve().parent / ".cache" / "gnosis"
SITE = "http://gnosis.org/"
UA = {"User-Agent": "ScriptureBot corpus builder (a personal Discord bot)"}


def expect(ok: bool, message: str) -> None:
    if not ok:
        raise SystemExit(f"unexpected source layout: {message}")


def fetch(path: str) -> str:
    CACHE.mkdir(parents=True, exist_ok=True)
    cached = CACHE / path.replace("/", "_")
    if not cached.exists():
        cached.write_bytes(urllib.request.urlopen(urllib.request.Request(SITE + path, headers=UA), timeout=60).read())
        time.sleep(1)
    return cached.read_bytes().decode("utf-8", errors="replace")


def paragraphs(fragment: str) -> list:
    out = []
    for p in re.split(r"(?i)<p\b[^>]*>", fragment):
        p = re.sub(r"(?i)<br\s*/?>", " ", p)
        text = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", "", p))).strip()
        if text and not re.fullmatch(r"[\s ]*", text):
            out.append(text)
    return out


def nhl_page(path: str) -> "tuple[str, list]":
    """A Coptic Gnostic Library Project page: (its translators, its paragraphs)."""
    page = fetch(path)
    # (the "Translated by" line just before the text, not the one in the page's title)
    found = [m for m in re.finditer(r"Translated(?:&nbsp;|\s)+by\s+(.+?)(?:<br|</)", page, re.S)
             if "<blockquote" in page[m.end():m.end() + 400]]
    expect(bool(found), f"{path}: no translator over the text")
    m = found[0]
    body = page[page.find("<blockquote", m.end()):]
    body = body[:body.find("</blockquote>")]
    translators = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", "", m.group(1)))).strip()
    return translators, paragraphs(body)


def numbered_sections(paras: list) -> dict:
    """Paragraphs under section numbers set as paragraphs of their own ("1", then its text): a verse each;
    what comes before section 1 (the editor's note) left out."""
    verses, current = {}, None
    for p in paras:
        m = re.match(r"(\d{1,3})(?:\s+|$)(.*)", p, re.S)
        if m and int(m.group(1)) == (int(current) + 1 if current else 1):
            current = m.group(1)
            verses[current] = m.group(2).strip()
        elif current:
            verses[current] = (verses[current] + "\n" + p).strip()
    return {k: v for k, v in verses.items() if v}


# (page, the bot's name for it -- Zinner's style -- and the name its translators give it)
NHL_MISSING = [
    ("naghamm/apocjn-long.html", "The Secret Book of John"),       # (the long version, Codex II)
    ("naghamm/gostruth.html", "The Gospel of Truth"),
    ("naghamm/gop.html", "The Gospel of Philip"),
    ("naghamm/1ja.html", "The First Apocalypse of James"),
]


def pistis_sophia() -> dict:
    """The Pistis Sophia, trans. G. R. S. Mead (1921), a page a chapter (ps005-ps153, chapters 1-148): Mead's
    marginal summaries, the Coptic manuscript's page marks ("|5.") and the printed page numbers left out, a
    paragraph broken over a printed page put back together; each of its six books named before its first
    chapter. A chapter each, a paragraph a verse."""
    book, title = {}, None
    for n in range(5, 154):
        page = fetch(f"library/pistis-sophia/ps{n:03d}.htm")
        page = re.sub(r'(?is)<span class="r?margnote">.*?</span>|<a name="page_\d+">.*?</a>', "", page)
        heading = re.findall(r"(?is)<h\d[^>]*>(.*?)</h\d>", page)
        heads = [re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", "", h))).strip() for h in heading]
        m = next((re.fullmatch(r"(?i)chapter (\d+)\.?", h) for h in heads if re.fullmatch(r"(?i)chapter \d+\.?", h)), None)
        at = next((i for i, h in enumerate(heads) if re.fullmatch(r"(?i)chapter \d+\.?", h)), len(heads))
        new_book = " ".join(h.strip("[]") for h in heads[:at]) or None     # (a book's title, over its first chapter)
        ends = [x.end() for x in re.finditer(r"(?is)<h\d[^>]*>(.*?)</h\d>", page)
                if not m or re.search(rf"(?i)chapter\s+{m.group(1)}\b", re.sub(r"<[^>]+>", "", x.group(1)))]
        expect(bool(ends), f"ps{n:03d}: no heading")
        body = page[ends[0] if m else ends[-1]:]
        body = re.split(r"(?i)<hr\b", body)[0]
        if not m:                       # (a page between books, "The Note of a Scribe": after the chapter before)
            expect(bool(book) and bool(new_book), f"ps{n:03d}: no chapter heading in {heads}")
            note = [p for p in paragraphs(body) if not re.fullmatch(r"p\. \d+|\|?", p)]
            verses = book[str(len(book))]
            for i, p in enumerate(note):
                verses[str(len(verses) + 1)] = (f"*{new_book}*\n" if i == 0 else "") + p
            continue
        chapter = m.group(1)
        paras = [p for p in paragraphs(body) if not re.fullmatch(r"p\. \d+|\|?", p)]
        joined = []
        for p in paras:
            p = re.sub(r"\s*\|\s*", " ", p).strip()            # (the Coptic page marks)
            if joined and re.match(r"[a-z]", p):                # (a paragraph broken over a printed page)
                joined[-1] += " " + p
            else:
                joined.append(p)
        verses = {str(i): p for i, p in enumerate(joined, 1)}
        expect(bool(verses), f"chapter {chapter}: no text")
        if new_book:
            verses["1"] = f"*{new_book}*\n{verses['1']}"
        book[chapter] = verses
    book = dict(sorted(book.items(), key=lambda kv: int(kv[0])))     # (the site has 115 before 114, 128 before 127)
    expect(list(book) == [str(i) for i in range(1, 149)], f"chapters {list(book)[:5]}...{list(book)[-5:]}")
    return book


def library_text(path: str, title: str) -> list:
    """A Gnostic Society Library page's text: after the last heading that names the work (its archive notes come
    before), to the site's footer; a paragraph an item."""
    page = re.sub(r"(?is)<(script|style)\b.*?</\1>", "", fetch(path))
    key = re.sub(r"\W+", " ", title).lower().strip()
    heads = [m for m in re.finditer(r"(?is)<h\d[^>]*>(.*?)</h\d>", page)
             if key in re.sub(r"\W+", " ", html.unescape(re.sub(r"<[^>]+>", "", m.group(1)))).lower()]
    expect(bool(heads), f"{path}: no heading naming {title!r}")
    # the page's middle: from the title to the footer's navigation (the last "Archive | Library")
    body = page[heads[0].end():]
    paras = [p for p in paragraphs(re.sub(r"(?is)<h\d[^>]*>(.*?)</h\d>", r"<p>\1</p>", body))
             if not re.fullmatch(r"[\s. <]*", p)]
    # (the site's navigation, "Archive | Library | Bookstore...", at the top and as the footer)
    navigation = [i for i, p in enumerate(paras) if p.startswith("Archive | Library")]
    if navigation and navigation[0] < 2:
        paras = paras[navigation[0] + 1:]
        navigation = [i - navigation[0] - 1 for i in navigation[1:]]
    if navigation:
        paras = paras[:navigation[-1]]
    # its archive notes, then the title again over the text; and a second work's notes end it
    def is_title(p):
        return re.sub(r"\W+", " ", p).lower().strip().startswith(key)
    if paras and paras[0].strip() == "Archive Notes":
        again = next((i for i, p in enumerate(paras) if i and is_title(p)), None)
        paras = paras[again + 1:] if again is not None else paras[2:]
    while paras and is_title(paras[0]):
        paras = paras[1:]
    if "Archive Notes" in paras:
        paras = paras[:paras.index("Archive Notes")]
    return paras


def numbered(paras: list, pattern: str = r"(\d+)[.)]\s+") -> dict:
    """Items opening with their numbers ("22) The Savior said", "1. He set him up"), a verse each; text before
    the first number joins the first, after it the one before."""
    verses, current, lead = {}, None, []
    for p in paras:
        m = re.match(pattern, p)
        if m and (current is None or int(m.group(1)) > int(current)):
            current = m.group(1)
            verses[current] = ("\n".join(lead) + "\n" if lead else "") + p[m.end():].strip()
            lead = []
        elif current:
            verses[current] += "\n" + p
        else:
            lead.append(p)
    return verses


def sequential(text: str, dot: bool) -> dict:
    """Sections numbered in running text ("...as well 83 It is fitting", "1. He set him up"): a number opens
    the next section only if it is the next number and a capital follows."""
    pattern = r"(?:(?<=^)|(?<=\s))(\d{1,3})" + (r"\." if dot else "") + r"\s+(?=[“\"‘'A-Z(\[])"
    sections, last = {}, 0
    for piece in re.split(pattern, text):
        if piece.isdigit() and int(piece) == last + 1:
            last = int(piece)
            sections[piece] = ""
        elif last:
            sections[str(last)] += piece
        elif piece.isdigit():
            pass
    return {k: re.sub(r"\s+", " ", v).strip() for k, v in sections.items()}


def gospel_of_mary() -> dict:
    """The Gospel of Mary (the Berlin Codex), as gnosis.org has it, unattributed: chapters 4-9 (pages 1-6 of the
    manuscript, chapters 1-3, are lost, and 11-14, most of 5 to 8), its verses by their numbers."""
    page = re.sub(r"(?is)<(script|style)\b.*?</\1>", "", fetch("library/marygosp.htm"))
    parts = re.split(r"(?is)<h4[^>]*>\s*(?:<[^>]+>\s*)*Chapter\s+(\d+):?\s*(?:<[^>]+>\s*)*</h4>", page)
    book = {}
    for num, body in zip(parts[1::2], parts[2::2]):
        body = re.split(r"(?is)Archive \| Library|<h3\b", body)[0]
        paras = paragraphs(body)
        verses = numbered(paras, r"(\d+)\)\s*")
        expect(bool(verses), f"Mary {num}: no verses")
        book[num] = {k: re.sub(r"\s+\(?\s*$", "", v) for k, v in verses.items()}
    expect(list(book) == ["4", "5", "8", "9"], f"Mary chapters {list(book)}")       # (pages 11-14 lost too)
    return book


def write(file: str, books: dict, sources: dict, source: str) -> None:
    path = ROOT / "data" / "gnostic" / file
    path.write_text(json.dumps({"source": source, "book_sources": sources, "books": books}, ensure_ascii=False,
                               indent=1), encoding="utf-8")
    print(f"  {path.name}: " + ", ".join(f"{b} ({sum(map(len, c.values()))})" for b, c in books.items()))


def nag_hammadi_more() -> None:
    books, sources = {}, {}
    for path, name in NHL_MISSING:
        translators, paras = nhl_page(path)
        expect(len(paras) > 10, f"{name}: {len(paras)} paragraphs")
        if any(re.match(r"1 [A-Z\[]", p) for p in paras):   # (the Apocryphon: Karen King's section numbers)
            books[name] = {"1": numbered_sections(paras)}
        else:
            books[name] = {"1": {str(i): p for i, p in enumerate(paras, 1)}}
        sources[name] = f"trans. {translators}"[:80]
    write("nag_hammadi_more.json", books, sources, "The Nag Hammadi Library, ed. James M. Robinson")


if __name__ == "__main__":
    only = sys.argv[1:]
    if not only or "nhl" in only:
        nag_hammadi_more()
    if not only or "fragments" in only:
        books, sources = {}, {}
        books["Gospel of Mary"] = gospel_of_mary()
        sources["Gospel of Mary"] = "unattributed translation (Gnostic Society Library)"
        untitled = library_text("library/untitl.htm", "The Untitled Text in the Bruce Codex")
        # its sections headed by a bare "2." paragraph, or opening one ("1. He set him up", "20. And those",
        # "21 ...."); the lists in them ("1. The first deep is the all-wise", "2. The second deep") numbered too: a
        # number is a list's if the paragraph before has the one before it
        chapters, last, before = {}, 0, ""
        for p in untitled:
            m = re.match(r"(\d{1,2})(?:\.(?:\s+|$)|\s(?=\.\.\.))", p.strip())
            listed = m and p.strip()[m.end():] and re.match(rf"{int(m.group(1)) - 1}\.\s+\S", before)
            before = p.strip()
            if m and not listed and int(m.group(1)) == last + 1:
                last = int(m.group(1))
                chapters[str(last)] = {}
                p = p[m.end():].strip()
            if p and last:
                chapters[str(last)][str(len(chapters[str(last)]) + 1)] = p
        expect(last >= 20, f"Untitled Text: {last} sections")
        books["Untitled Text of the Bruce Codex"] = chapters
        ieou = library_text("library/1ieo.htm", "The First Book of IEOU")
        books["First Book of Ieou"] = {"1": {str(i): p for i, p in enumerate(ieou, 1)}}
        for path, title, name in (("library/flora.htm", "Ptolemy's Letter to Flora", "Ptolemy's Letter to Flora"),
                                  ("library/ephip.htm", "On Righteousness", "Epiphanes, On Righteousness"),
                                  ("library/naas.htm", "The Naassene Psalm", "The Naassene Psalm"),
                                  ("library/basilide.htm", "Fragments from the Writings of Basilides",
                                   "Fragments of Basilides")):
            paras = [p for p in library_text(path, title)       # (the link to Jung's "Basilides", not his)
                     if not re.search(r"Septem Sermones|Modern Pseudepigraph", p)]
            books[name] = {"1": {str(i): p for i, p in enumerate(paras, 1)}}
        excerpta = library_text("library/excr.htm", "Excerpta ex Theodoto")
        # (one long paragraph, its sections numbered bare: "...spirit. 2 The Valentinians...")
        text = " ".join(p for p in excerpta if not p.startswith('"Extracts from the Works'))
        sections = sequential(text, dot=False)
        expect(len(sections) == 86, f"Theodotus: {len(sections)} sections")    # (Casey's 86)
        books["Excerpts from Theodotus"] = {"1": sections}
        sources["Excerpts from Theodotus"] = "trans. Robert Pierce Casey (1934)"
        for name, chapters in books.items():
            # the site's footer, where it shares a paragraph with the text ("...to preach.\nThe Gospel of
            # Mary\nArchive | Library | ...", "(lacuna of four lines) | GNOSIS ARCHIVE | ...")
            for verses in chapters.values():
                for v in list(verses):
                    text = re.split(r"(?:\n[^\n]*)?\nArchive \| Library|\s*\|\s*GNOSIS ARCHIVE", verses[v])[0].strip()
                    if text:
                        verses[v] = text
                    else:
                        expect(v == list(verses)[-1], f"{name} {v}: emptied")
                        del verses[v]
            print(f"  {name}: {sum(map(len, chapters.values()))} passages")
        write("gnostic_fragments.json", books, sources, "Gnostic Society Library")
        write("pistis_sophia.json", {"Pistis Sophia": pistis_sophia()}, {}, "trans. G. R. S. Mead (1921)")
