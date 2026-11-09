"""
The Bahá'í scriptures, from the Bahá'í Reference Library (bahai.org/library), the authoritative English texts of
the Bahá'í World Centre: every work there of the three Central Figures of the Faith -- the Báb, Bahá'u'lláh and
'Abdu'l-Bahá -- whose writings Bahá'ís hold to be their sacred text, and the prayer book drawn from them.
(Shoghi Effendi's and the Universal House of Justice's writings are authoritative interpretation, not scripture,
and aren't here; the Hidden Words and the Kitáb-i-Aqdas were built before and are kept.)

    python scripts/build_bahai.py            all of them
    python scripts/build_bahai.py iqan saq   those whose name has one of these in it

Each work comes as one .xhtml file (cached in scripts/.cache/bahai/). Its numbers aren't in the file -- the library
counts paragraphs as its reader does -- so each work is read one of these ways:

    sections    numbered selections ("– I –", "– 7 –"), each a chapter of paragraphs, its title and date first
                (Gleanings, Prayers and Meditations, Some Answered Questions, the talks)
    paragraphs  a chapter a paragraph, as Bahá'ís cite these ("Kitáb-i-Íqán ¶213"), as the Aqdas already is
    headings    a chapter a tablet, at its heading (the Summons, Tablets of Bahá'u'lláh, Tablets of the Divine Plan)
    numbered    a chapter a numbered piece, its number a heading (The Call of the Divine Beloved, Days of Remembrance)
    dotted      paragraphs numbered by part, "3.13" (the Will and Testament): part 3, paragraph 13
    titled      a chapter at each title (a letter's, a chapter's), what comes before the first chapter 0 (Shoghi
                Effendi's letters, God Passes By)
    items       a chapter a prayer or extract, each opening with the book's drop capital (the additional prayers and
                tablets, the Báb's Selections, Bahá'í Prayers)

and checked against the numbers they're known by (the Íqán's 290 paragraphs, the Gleanings' 166 selections...).
"""
import html
import json
import re
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CACHE = Path(__file__).resolve().parent / ".cache" / "bahai"
LIBRARY = "https://www.bahai.org/library/authoritative-texts/"
UA = {"User-Agent": "Mozilla/5.0 (ScriptureBot corpus builder)"}

BACK = ("Notes", "Endnotes", "Note on the Translation", "Key to Passages", "Passages Translated by Shoghi Effendi",
        "Notes on Translations", "Abbreviation", "Glossary")
FRONT = ("Preface", "Foreword", "Introduction", "Author’s Preface", "A Description of the Kitáb-i-Aqdas")

# (library path, data file, the bot's name for the book, how it's read, what it must come to, translator)
WORKS = [
    ("bahaullah/gleanings-writings-bahaullah", "gleanings.json", "Gleanings from the Writings of Baha'u'llah",
     "sections", 166, "trans. Shoghi Effendi"),
    ("bahaullah/kitab-i-aqdas", "aqdas_questions_and_answers.json", "Questions and Answers (Aqdas)",
     "questions", 107, "Bahá'í World Centre (1992)"),          # (the Aqdas itself was built before and is kept)
    ("bahaullah/prayers-meditations", "prayers_and_meditations.json", "Prayers and Meditations",
     "sections", 184, "trans. Shoghi Effendi"),
    ("bahaullah/kitab-i-iqan", "kitab_i_iqan.json", "Kitab-i-Iqan", "paragraphs", 290, "trans. Shoghi Effendi"),
    ("bahaullah/epistle-son-wolf", "epistle_to_son_of_wolf.json", "Epistle to the Son of the Wolf",
     "paragraphs", None, "trans. Shoghi Effendi"),
    ("bahaullah/gems-divine-mysteries", "gems_of_divine_mysteries.json", "Gems of Divine Mysteries",
     "paragraphs", None, "Bahá'í World Centre (2002)"),
    ("bahaullah/call-divine-beloved", "call_of_the_divine_beloved.json", "Call of the Divine Beloved",
     "numbered", None, "Bahá'í World Centre (2018)"),
    ("bahaullah/days-remembrance", "days_of_remembrance.json", "Days of Remembrance",
     "numbered", None, "Bahá'í World Centre (2017)"),
    ("bahaullah/summons-lord-hosts", "summons_of_the_lord_of_hosts.json", "Summons of the Lord of Hosts",
     "headings", 5, "Bahá'í World Centre (2002)"),
    ("bahaullah/tabernacle-unity", "tabernacle_of_unity.json", "Tabernacle of Unity",
     "headings", None, "Bahá'í World Centre (2006)"),
    ("bahaullah/tablets-bahaullah", "tablets_of_bahaullah.json", "Tablets of Baha'u'llah",
     "headings", 17, "trans. Habib Taherzadeh et al. (1978)"),     # (16 tablets, and excerpts from others)
    ("bahaullah/additional-tablets-extracts-from-tablets-revealed-bahaullah", "bahaullah_additional_tablets.json",
     "Additional Tablets of Baha'u'llah", "items", None, "Bahá'í World Centre"),
    ("bahaullah/additional-prayers-revealed-bahaullah", "bahaullah_additional_prayers.json",
     "Additional Prayers of Baha'u'llah", "items", None, "Bahá'í World Centre"),
    ("the-bab/selections-writings-bab", "selections_from_the_bab.json", "Selections from the Writings of the Bab",
     "items", None, "trans. Habib Taherzadeh et al. (1976)"),
    ("the-bab/persian-bayan", "persian_bayan.json", "Persian Bayan", "bayan", 162,
     "unofficial: trans. Peter Terry (2020) from Nicolas's French"),
    ("abdul-baha/selections-writings-abdul-baha", "selections_from_abdul_baha.json",
     "Selections from the Writings of Abdu'l-Baha", "sections", 237, "Bahá'í World Centre (1978)"),
    ("abdul-baha/some-answered-questions", "some_answered_questions.json", "Some Answered Questions",
     "sections", 84, "Bahá'í World Centre (2014)"),
    ("abdul-baha/secret-divine-civilization", "secret_of_divine_civilization.json", "Secret of Divine Civilization",
     "paragraphs", None, "trans. Marzieh Gail (1957)"),
    ("abdul-baha/travelers-narrative", "travelers_narrative.json", "A Traveler's Narrative",
     "paragraphs", None, "trans. E. G. Browne (1891)"),
    ("abdul-baha/memorials-faithful", "memorials_of_the_faithful.json", "Memorials of the Faithful",
     "sections", 69, "trans. Marzieh Gail (1971)"),
    ("abdul-baha/light-of-the-world", "light_of_the_world.json", "Light of the World",
     "sections", 76, "Bahá'í World Centre (2021)"),
    ("abdul-baha/tablets-divine-plan", "tablets_of_the_divine_plan.json", "Tablets of the Divine Plan",
     "headings", 14, "Bahá'í World Centre (1993)"),
    ("abdul-baha/tablets-hague-abdul-baha", "tablets_to_the_hague.json", "Tablets to The Hague",
     "headings", 2, "Bahá'í World Centre"),
    ("abdul-baha/tablet-auguste-forel", "tablet_to_auguste_forel.json", "Tablet to Auguste Forel",
     "paragraphs", None, "Bahá'í World Centre"),
    ("abdul-baha/will-testament-abdul-baha", "will_and_testament.json", "Will and Testament of Abdu'l-Baha",
     "dotted", 3, "trans. Shoghi Effendi"),
    ("abdul-baha/additional-tablets-extracts-talks", "abdul_baha_additional_tablets.json",
     "Additional Tablets of Abdu'l-Baha", "items", None, "Bahá'í World Centre"),
    ("abdul-baha/additional-prayers-revealed-abdul-baha", "abdul_baha_additional_prayers.json",
     "Additional Prayers of Abdu'l-Baha", "items", None, "Bahá'í World Centre"),
    ("abdul-baha/paris-talks", "paris_talks.json", "Paris Talks", "sections", None, "talks, 1911-1912"),
    ("abdul-baha/promulgation-universal-peace", "promulgation_of_universal_peace.json",
     "Promulgation of Universal Peace", "sections", 140, "talks, 1912"),
    ("abdul-baha/twelve-table-talks-abdul-baha", "twelve_table_talks.json", "Twelve Table Talks",
     "sections", 12, "Bahá'í World Centre (2018)"),
    ("prayers/bahai-prayers", "bahai_prayers.json", "Baha'i Prayers", "items", None, "Bahá'í World Centre"),
    # Shoghi Effendi, the Guardian: authoritative interpretation (not revelation), as the Talmud or the Church
    # Fathers are to theirs -- the owner's call (2026-11-09). Written in English.
    ("shoghi-effendi/god-passes-by", "god_passes_by.json", "God Passes By", "titled", None, "Shoghi Effendi (1944)"),
    ("shoghi-effendi/advent-divine-justice", "advent_of_divine_justice.json", "The Advent of Divine Justice",
     "paragraphs", None, "Shoghi Effendi (1939)"),
    ("shoghi-effendi/promised-day-come", "promised_day_is_come.json", "The Promised Day Is Come",
     "titled", None, "Shoghi Effendi (1941)"),
    ("shoghi-effendi/world-order-bahaullah", "world_order_of_bahaullah.json", "The World Order of Baha'u'llah",
     "headings", None, "Shoghi Effendi (1938)"),
    ("shoghi-effendi/bahai-administration", "bahai_administration.json", "Baha'i Administration",
     "titled", None, "Shoghi Effendi (1928)"),
    ("shoghi-effendi/citadel-faith", "citadel_of_faith.json", "Citadel of Faith", "titled", None,
     "Shoghi Effendi (1965)"),
    ("shoghi-effendi/decisive-hour", "decisive_hour.json", "The Decisive Hour", "sections", 165,
     "Shoghi Effendi (2002)"),
]


def expect(ok: bool, message: str) -> None:
    if not ok:
        raise SystemExit(f"unexpected source layout: {message}")


def fetch(path: str) -> str:
    """A work's .xhtml (its page names the file, with a version mark)."""
    CACHE.mkdir(parents=True, exist_ok=True)
    cached = CACHE / (path.replace("/", "_") + ".xhtml")
    if not cached.exists():
        page = urllib.request.urlopen(urllib.request.Request(LIBRARY + path + "/", headers=UA), timeout=60).read()
        m = re.search(r'href="([^"]+\.xhtml[^"]*)"', page.decode("utf-8", "replace"))
        expect(bool(m), f"{path}: no .xhtml on its page")
        url = "https://www.bahai.org" + m.group(1)
        cached.write_bytes(urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=120).read())
        time.sleep(1)
    return cached.read_text(encoding="utf-8")


def blocks(xhtml: str) -> list:
    """[(tag, {classes}, text)]: the body's headings, paragraphs and list items in order, footnote marks out."""
    body = xhtml[xhtml.find("<body"):]
    out = []
    for m in re.finditer(r"(?s)<(h[1-6]|p|li)\b([^>]*)>(.*?)</\1>", body):
        cls = re.search(r'class="([^"]*)"', m.group(2))
        inner = re.sub(r"(?s)<sup\b.*?</sup>", "", m.group(3))
        inner = re.sub(r"(?i)<br\s*/?>", "\n", inner)
        text = html.unescape(re.sub(r"<[^>]+>", "", inner))
        text = "\n".join(re.sub(r"[ \t ]+", " ", line).strip() for line in text.split("\n")).strip()
        out.append((m.group(1), set(cls.group(1).split()) if cls else set(), text))
    return out


def _marker(cls: set, text: str) -> "str | None":
    """A numbered selection's number ("– I –" -> "1", "– 7 –" -> "7"), or None."""
    if not ({"c", "q"} <= cls):
        return None
    t = re.sub(r"[⁠​‌‍﻿]", "", text).strip(" –-")      # (a word joiner in "20⁠")
    if t.isdigit():
        return t
    if re.fullmatch(r"[IVXLC]+", t):
        values = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100}
        n = 0
        for a, b in zip(t, t[1:] + " "):
            n += -values[a] if b != " " and values.get(b, 0) > values[a] else values[a]
        return str(n)
    return None


def _is_title(cls: set) -> bool:
    """A title, a date, a place: put in italics before the chapter's first paragraph."""
    return bool(({"c", "l"} <= cls) or ("ub" in cls and ({"c", "hb"} & cls) and "w" not in cls)
                or cls in ({"c"}, {"c", "j"}, {"c", "dd", "j"}))


def _skip(cls: set, text: str) -> bool:
    """Not text: a tablet's number over its heading, a "* * *" between pieces, "END" closing a part, the
    library's footer, and the editors' notes on a work's first page."""
    return bool("te" in cls or re.fullmatch(r"[*\s]+", text) or re.fullmatch(r"END( OF PART \w+)?", text)
                or not text or text.startswith(("Last modified:", "This document has been downloaded"))
                or text.startswith(EDITORIAL))


EDITORIAL = ("Original Persian text first published",                 # (the Tablet to Forel's source)
             "Written to Illustrate the Episode of the Báb")           # (A Traveler's Narrative's subtitle)


def _italic(lines: list) -> str:
    """Titles in italics, a line at a time (Discord's italics don't cross a line break)."""
    return "\n".join(f"*{part}*" for line in lines for part in line.split("\n") if part.strip())


def read_questions(work: str) -> dict:
    """The Kitáb-i-Aqdas volume's Questions and Answers: each its number ("1."), then the question and the answer,
    a chapter each, as they're cited ("Q&A 1")."""
    bl = blocks(fetch(work))
    start = next(i for i, (t, c, x) in enumerate(bl) if t == "h2" and x.startswith("Questions and Answers"))
    end = next(i for i, (t, c, x) in enumerate(bl) if i > start and t == "h2")
    book, chapter = {}, None
    for tag, cls, text in bl[start + 1:end]:
        m = re.fullmatch(r"(\d+)\.", text)
        if m:
            chapter = m.group(1)
            expect(chapter not in book, f"Q&A {chapter} twice")
            book[chapter] = {}
        elif chapter and tag == "p" and text:
            text = re.sub(rf"^{chapter}\s+(?=\S)", "", text)
            book[chapter][str(len(book[chapter]) + 1)] = text
    return book


def read(work: str, mode: str) -> dict:
    """{chapter: {verse: text}} by the work's mode."""
    if mode == "questions":
        return read_questions(work)
    if mode == "bayan":
        return read_bayan()
    bl = blocks(fetch(work))
    # the body: after the front matter, before the notes
    end = next((i for i, (t, c, x) in enumerate(bl) if t == "h2" and x.startswith(BACK)), len(bl))
    bl = bl[:end]
    if mode == "sections":
        start = next(i for i, (t, c, x) in enumerate(bl) if t == "p" and _marker(c, x))
    elif mode == "numbered":
        start = next(i for i, (t, c, x) in enumerate(bl) if t == "h3" and x.isdigit())
    else:
        heads = [i for i, (t, c, x) in enumerate(bl) if t == "h2" and not x.startswith(FRONT)]
        if heads and mode != "titled":
            start = heads[0]
        else:                                   # (no headings: after the title page's lines)
            start = next(i for i, (t, c, x) in enumerate(bl)
                         if t == "p" and not ({"se", "re", "j"} & c) and i > 0 and not _skip(c, x))
    book, chapter, pending, n = {}, None, [], 0
    in_front = False

    def new_chapter(key=None):
        nonlocal chapter, n
        n += 1
        chapter = key or str(n)
        expect(chapter not in book, f"{work}: chapter {chapter} twice")
        book[chapter] = {}

    def add(text, cls=frozenset()):
        nonlocal pending, chapter
        if mode == "dotted":                     # ("3.13 The Glory of Glories": part 3, paragraph 13)
            m = re.match(r"(\d+)\.(\d+)\s?(?=\S)", text)
            if not m:
                pending.append(text)
                return
            chapter = m.group(1)
            verses = book.setdefault(chapter, {})
            if pending:
                text = _italic(pending) + "\n" + text[m.end():]
                pending = []
            else:
                text = text[m.end():]
            expect(m.group(2) not in verses, f"{work}: {m.group()} twice")
            verses[m.group(2)] = text
            return
        if mode in ("paragraphs", "items") and (chapter is None or mode == "paragraphs" or "zd" in cls):
            new_chapter()
        verses = book[chapter]
        # the paragraph's own number, where the library prints it ("1 Nature is...", "59Were I...", "1.1 Praise"):
        # taken off when it's the number the count expects here
        expected = chapter if mode == "paragraphs" else str(len(verses) + 1)
        m = re.match(r"(\d+)(?:\.(\d+))?\s?(?=[^\s\d.])", text)
        if m and (m.group(2) is None and m.group(1) == expected
                  or m.group(2) is not None and m.group(1) == chapter and m.group(2) == expected):
            text = text[m.end():]
        if pending:
            text = _italic(pending) + "\n" + text
            pending = []
        verses[str(len(verses) + 1)] = text

    for tag, cls, text in bl[start:]:
        if tag == "li" or (tag == "p" and _skip(cls, text)) or not text:
            continue
        if tag in ("h2", "h3", "h4"):
            if tag == "h2":
                in_front = text.startswith(FRONT)
            if in_front:
                continue
            if mode == "numbered" and tag == "h3" and text.isdigit():
                new_chapter(text)
                continue
            if mode == "headings" and tag == "h2":
                new_chapter()
            pending.append(text)
            continue
        if in_front:
            continue
        key = _marker(cls, text) if mode in ("sections", "headings") else None
        if key:
            if mode == "headings" and chapter is not None and not book[chapter]:
                del book[chapter]                   # ("Two Other Tablets", then "– 4 –": the tablet's own number)
                n -= 1
            new_chapter(key)
            continue
        if mode == "titled" and (_is_title(cls) or {"c", "p"} <= cls):
            if chapter is None or book[chapter]:     # (a chapter's number and its title are one heading)
                new_chapter()
            pending.append(text)
            continue
        if _is_title(cls):
            pending.append(text)
            continue
        if "w" in cls:                          # an invocation ("IN THE NAME OF OUR LORD"): before what follows
            pending.append(text)
            continue
        if "ac" in cls and "hb" in cls and chapter and book[chapter]:     # "—Bahá'u'lláh" after a prayer
            last = str(len(book[chapter]))
            book[chapter][last] += "\n" + text
            continue
        if chapter is None and mode in ("headings", "numbered", "sections"):
            continue
        if chapter is None and mode == "titled":    # (before the first title: a foreword, chapter 0)
            book["0"] = {}
            chapter = "0"
        add(text, cls)
    book = {c: v for c, v in book.items() if v}
    if mode == "titled":                        # (God Passes By: "- Chapter XIII -" is chapter 13, its Foreword 0)
        numbered = {}
        for c, verses in book.items():
            first = next(iter(verses.values()))
            heading = re.match(r"(?:\*[^\n]*\*\n)*", first).group()          # (its italic lines: "First Period"...)
            m = re.search(r"(?m)^\*\W*Chapter ([IVXLC]+)\W*\*$", heading)
            key = _marker({"c", "q"}, m.group(1)) if m else ("0" if first.startswith("*Foreword*") else None)
            numbered[key or c] = verses
        if len(numbered) == len(book):
            book = numbered
    return book


# The Persian Bayán, the Báb's book of laws: no authorized English translation exists (the Selections has excerpts),
# so this is an unofficial one, plainly labelled -- Peter Terry's English (2020) of A. L. M. Nicolas's French (Le
# Béyan persan, 1911-14), on Bahá'í Library Online. The owner chose it (2026-11-09). Its translator sets the Báb's
# words in bold and Nicolas's notes, the footnotes and the Qur'án's Arabic in plain type: only the bold is kept.
# Cited by Váḥid (unity) and Báb (gate): 8 unities of 19 gates and a ninth of 10, where the Báb left it.
BAYAN_DOCX = "https://bahai-library.com/docs/b/bab_bayan_nicolas_anonymous.docx"


def read_bayan() -> dict:
    import zipfile
    cached = CACHE / "persian_bayan.docx"
    if not cached.exists():
        CACHE.mkdir(parents=True, exist_ok=True)
        cached.write_bytes(urllib.request.urlopen(urllib.request.Request(BAYAN_DOCX, headers=UA), timeout=120).read())
    xml = zipfile.ZipFile(cached).read("word/document.xml").decode("utf-8")
    book, chapter = {}, None
    numerals = {"I": 1, "II": 2, "III": 3, "IV": 4, "V": 5, "VI": 6, "VII": 7, "VIII": 8, "IX": 9}
    for p in re.findall(r"(?s)<w:p[ >].*?</w:p>", xml):
        runs = []
        for r in re.findall(r"(?s)<w:r[ >].*?</w:r>", p):
            text = html.unescape("".join(re.findall(r"(?s)<w:t(?: [^>]*)?>(.*?)</w:t>", r)))
            runs.append((text, bool(re.search(r'<w:b/>|<w:b w:val="(?:1|true)"/>', r))))
        whole = "".join(t for t, _ in runs).strip()
        m = re.fullmatch(r"Vahid ([IVX]+) - Bab (\d+)", whole)
        if m:
            chapter = f"{numerals[m.group(1)]}.{m.group(2)}"
            book[chapter] = {}
            continue
        if whole.startswith("HERE ENDS THE PERSIAN BAYAN"):
            break
        bold = sum(len(t) for t, b in runs if b)
        if chapter is None or not whole or bold * 2 < len(whole) or re.fullmatch(r"[*_\s]+", whole):
            continue                                # (Nicolas's notes, footnotes, the Arabic, separators)
        text = re.sub(r"\[\^\d+(?:[\])]|\.(?=\s))", "", whole)  # (the footnote marks: "[^30]", "[^30.", "[^657)")
        text = re.sub(r"[ \t]{2,}", " ", text).strip()
        if text and not re.match(r":?\s*Note:", text):         # (a footnote of Nicolas's set in bold, twice)
            book[chapter][str(len(book[chapter]) + 1)] = text
    return book


def write(file: str, name: str, source: str, chapters: dict) -> None:
    path = ROOT / "data" / "bahai" / file
    path.write_text(json.dumps({"source": source, "books": {name: chapters}}, ensure_ascii=False, indent=1),
                    encoding="utf-8")
    print(f"  {name}: {len(chapters)} chapters, {sum(map(len, chapters.values()))} passages -> {path.name}")


def main(only: list) -> None:
    for work, file, name, mode, count, source in WORKS:
        if only and not any(o.lower() in (work + name).lower() for o in only):
            continue
        chapters = read(work, mode)
        expect(count is None or len(chapters) == count, f"{name}: {len(chapters)} chapters, not {count}")
        write(file, name, source, chapters)


if __name__ == "__main__":
    main(sys.argv[1:])
