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
    if not only or "pistis" in only:
        write("pistis_sophia.json", {"Pistis Sophia": pistis_sophia()}, {}, "trans. G. R. S. Mead (1921)")
