"""
Latin authors the library lacked, into data/classical/latin.json (run scripts/clean_corpora.py after):

  old_age     Cicero's Cato Maior, On Old Age (Shuckburgh), from Gutenberg #2808 (his On Friendship the bot has)
  distichs    The Distichs of Cato (Chase, 1922), from Wikisource
  cato        Cato the Elder's On Agriculture, complete (Hooper and Ash's Loeb, 1934), from LacusCurtius: Harrison's
              translation on Gutenberg (#12140) is a digest of about a third of it
  varro       Varro's On Agriculture (the same Loeb), from LacusCurtius
  seneca_dialogues   Seneca's Minor Dialogues and On Clemency (Stewart, 1889), Gutenberg #64576
  benefits    Seneca's On Benefits (Stewart, 1887), Gutenberg #3794
  natural_questions  Seneca's Natural Questions (Clarke, 1910), Gutenberg #76392
  moral_letters      Seneca's Moral Letters to Lucilius (Gummere's Loeb), from Wikisource
  seneca_tragedies   Seneca's nine tragedies (Miller's Loeb, 1917), from theoi.com
  pliny_letters      Pliny the Younger's Letters and the Trajan correspondence (Melmoth/Bosanquet), Gutenberg #2811
  satyricon   Petronius (Firebaugh, 1922), Gutenberg #5225
  fasti, thebaid, achilleid, argonautica   Ovid, Statius and Valerius Flaccus (Frazer's and Mozley's Loebs), theoi.com
  fabulae, astronomica   Hyginus (Grant, 1960), from ToposText: theoi.com's own pages now hold only a few fables
  dares, dictys, fulgentius   the Trojan War "eyewitnesses" (Frazer, 1966) and the Mythologies (Whitbread), theoi.com

LacusCurtius is slow (a page can take a minute and a half): scripts/fetch_lacus.py downloads its pages first.
theoi.com's pages are cached by scripts/fetch_theoi.py.

    python scripts/build_latin.py [step ...]
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from build_platonists import blocks, chapter, expect, gutenberg, numbered, split, text, wikisource, ws_blocks  # noqa: E402

OUT = ROOT / "data" / "classical" / "latin.json"


def _load() -> dict:
    return json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else {"source": "various translators",
                                                                            "books": {}, "book_sources": {}}


def _save(payload: dict) -> None:
    # the books stored as passages keyed "book.firstline" (a poem's lines, a play's, Seneca's letters' sections):
    # the bot reads "Fasti 1:30" as the passage holding line 30
    payload["line_chunked"] = sorted(b for b, chapters in payload["books"].items()
                                     if chapters and all(re.fullmatch(r"\d+\.\d+", k) and list(v) == ["1"]
                                                         for k, v in chapters.items()))
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    for book, chapters in payload["books"].items():
        words = sum(len(v.split()) for c in chapters.values() for v in c.values())
        print(f"  {book}: {len(chapters)} chapters, {words:,} words")


def _put(book: str, chapters: dict, source: str) -> None:
    payload = _load()
    payload["books"][book] = chapters
    payload["book_sources"][book] = source
    _save(payload)


# ── Cicero, On Old Age ─────────────────────────────────────────────────────
# Sections numbered as Shuckburgh prints them ("2. Scipio. Many a time..."); the verse Cicero quotes is set apart
# (<pre>) in the middle of a section, and goes with it.

def old_age() -> None:
    t = gutenberg(2808)
    start = re.search(r"<h2>\s*ON OLD AGE\s*</h2>", t)
    part = t[start.end() if start else 0:t.find("*** END")] if start else ""
    expect(len(part) > 10000, "On Old Age not found")
    paras = []
    for m in re.finditer(r"(?is)<pre>(.*?)</pre>|<p\b[^>]*>(.*?)</p>", part):
        if m.group(1) is not None:
            s = "\n".join(line.strip() for line in m.group(1).strip().splitlines() if line.strip())
        else:
            s = text(m.group(2))
            s = re.sub(r"^([A-Z])([A-Z]+)\b(?= [a-z])", lambda w: w.group(1) + w.group(2).lower(), s)   # ("FOR I may")
        if s:
            paras.append(s)
    _put("On Old Age", {"1": numbered(paras)}, "Cicero, trans. E. S. Shuckburgh (1900)")


# ── The Distichs of Cato ───────────────────────────────────────────────────
# Chapter 0: the introduction, then the short precepts (the Monostichs); 1-4: the four books, a couplet a verse,
# each book's prose preface (bracketed in Chase) leading its first couplet.

def distichs() -> None:
    t = wikisource("Distichs of Cato")
    sections = {text(h): ws_blocks(body) for h, body in split(t, r"(?is)<h2[^>]*>(.*?)</h2>")}
    zero = sections["Introduction"] + sections["Monostichs"]
    books = {"0": {str(i + 1): s for i, s in enumerate(zero)}}
    for n, name in enumerate(("Book I", "Book II", "Book III", "Book IV"), 1):
        lines = "\n".join(p for p in sections[name] if not re.match(r"This work|Public domain", p)).split("\n")
        preface, couplets = [], []
        for line in lines:
            m = re.match(r"(\d+)\.\s+(.*)", line)
            if m:
                couplets.append([m.group(1), m.group(2)])
            elif couplets:
                couplets[-1][1] += "\n" + line
            else:
                preface.append(line)
        numbers = [int(k) for k, _ in couplets]
        expect(numbers == list(range(1, len(numbers) + 1)), f"{name}: couplets {numbers}")
        verses = {k: v.strip() for k, v in couplets}
        if preface:
            verses["1"] = "*" + " ".join(preface).strip("[] ") + "*\n" + verses["1"]
        books[str(n)] = verses
    _put("Distichs of Cato", books, "trans. Wayland Johnson Chase (1922)")


# ── LacusCurtius (Bill Thayer's transcriptions of the Loeb) ────────────────
# A chapter starts at <A CLASS="chapter" NAME="12">, a section at <A CLASS="sec" NAME="12.3">: the Loeb's numbers,
# kept, so "On Agriculture 12:3" is Cato 12.3. Left out: the link to the Latin page beside each chapter, page
# numbers, note numbers, and the notes (after <HR CLASS="endnotes">).

def lacus(pages: list, prefix: str = "") -> dict:
    """{chapter: {section: text}} of a work's pages; `prefix` before each chapter ("2." for Varro's second book)."""
    from fetch_lacus import fetch
    import html as _html
    out = {}
    for page in pages:
        t = fetch(page)
        t = t[:t.find('<HR CLASS="endnotes"')] if '<HR CLASS="endnotes"' in t else t
        t = t[t.find("</H1>"):] if "</H1>" in t else t
        t = re.sub(r'(?is)<A HREF="\s*L/[^"]*"[^>]*>\s*<IMG[^>]*>\s*</A>', " ", t)       # (the Latin page's link)
        t = re.sub(r'(?is)<SPAN CLASS="pagenum">.*?</SPAN>|<A CLASS="ref"[^>]*>.*?</A>', "", t)
        t = t.replace("&shy;", "").replace("&#8288;", "").replace("­", "")
        marks = [(m.group(1).lower(), m.group(2), m.start(), m.end())
                 for m in re.finditer(r'(?is)<A CLASS="(chapter|sec)" NAME="([^"]+)">[^<]*</A>', t)]
        # (Cato's preface has no chapter mark: its first section is the text before the mark "0.2")
        if marks and marks[0][0] == "sec" and marks[0][1].endswith(".2"):
            marks.insert(0, ("sec", marks[0][1][:-2] + ".1", 0, 0))
        chap = None
        for i, (kind, name, _, after) in enumerate(marks):
            end = marks[i + 1][2] if i + 1 < len(marks) else len(t)
            body = t[after:end]
            body = re.sub(r"(?is)<(i|em)>(.*?)</\1>", lambda x: f"*{x.group(2).strip()}*", body)
            body = re.sub(r"(?is)<P[^>]*>|<BR[^>]*>", "\n", body)
            body = _html.unescape(re.sub(r"<[^>]+>", "", body))
            body = "\n".join(re.sub(r"\s+", " ", line).strip() for line in body.split("\n"))
            body = re.sub(r"\n{2,}", "\n", body).strip()
            if kind == "chapter":
                chap = prefix + name
                out.setdefault(chap, {})
                if body:                                     # (a chapter whose first section isn't marked)
                    out[chap]["1"] = body
                continue
            c, _, s = name.rpartition(".")
            # a section belongs to the chapter it sits in (the page names one "3131.2", in chapter 31)
            key = chap if chap is not None else prefix + c
            if chap is not None and prefix + c != chap:
                print(f"    {page}: section {name} in chapter {chap}")
            if body:
                out.setdefault(key, {})[s] = (out.get(key, {}).get(s, "") + " " + body).strip()
    return out


def cato() -> None:
    pages = [f"E/Roman/Texts/Cato/De_Agricultura/{x}*.html" for x in "ABCDEFGHIJKL"]
    chapters = lacus(pages)
    numbers = sorted(int(c) for c in chapters if c.isdigit())
    expect(numbers[0] in (0, 1) and numbers[-1] == 162, f"Cato's chapters {numbers[:3]}...{numbers[-3:]}")
    _put("On Agriculture", dict(sorted(chapters.items(), key=lambda kv: int(kv[0]))),
         "Cato the Elder, trans. W. D. Hooper and H. B. Ash (1934)")


def varro() -> None:
    chapters = {}
    for book in (1, 2, 3):
        chapters.update(lacus([f"E/Roman/Texts/Varro/de_Re_Rustica/{book}*.html"], prefix=f"{book}."))
    expect(len(chapters) > 50, f"Varro: {len(chapters)} chapters")
    _put("On Farming", chapters, "Varro, trans. W. D. Hooper and H. B. Ash (1934)")


# ── Seneca, the Minor Dialogues and On Clemency (Stewart, 1889) ────────────
# Gutenberg #64576. A dialogue a book; its chapters as Stewart numbers them ("II. Why do many things..."), the
# paragraphs after a numbered one going with it. On Anger's three books and On Clemency's two: "1.1", "2.1"...

ROMAN_CHAPTER = re.compile(r"([IVXL]+)\.\s+(?=\S)")
DIALOGUES = [("PROVIDENC", "On Providence", None), ("FIRMNESS", "On the Firmness of the Wise Man", None),
             ("OF ANGER. Book I.", "On Anger", "1"), ("OF ANGER. Book II.", "On Anger", "2"),
             ("OF ANGER. Book III.", "On Anger", "3"), ("MARCIA", "To Marcia, On Consolation", None),
             ("HAPPY LIFE", "On the Happy Life", None), ("OF LEISURE", "On Leisure", None),
             ("PEACE OF MIND", "On Peace of Mind", None), ("SHORTNESS OF LIFE", "On the Shortness of Life", None),
             ("HELVIA", "To Helvia, On Consolation", None), ("POLYBIUS", "To Polybius, On Consolation", None),
             ("FIRST BOOK OF THE DIALOGUE OF L. ANNAEUS SENECA, ADDRESSED TO NERO", "On Clemency", "1"),
             ("SECOND BOOK OF THE DIALOGUE OF L. ANNAEUS SENECA, ADDRESSED TO NERO", "On Clemency", "2")]


def roman_chapters(paras: list, prefix: str = "") -> dict:
    """Paragraphs "IV. Text..." -> {"4": [...]}: a chapter at each, the unnumbered after it going with it."""
    out, current = {}, None
    for p in paras:
        m = ROMAN_CHAPTER.match(p)
        n = roman(m.group(1)) if m else None
        if n and (current is None or n == int(current.split(".")[-1]) + 1):
            current = f"{prefix}{n}"
            out[current] = [p[m.end():]]
        elif current is not None:
            out[current].append(p)
        else:
            current = f"{prefix}1"
            out[current] = [p]
    return out


def roman(s: str) -> int:
    vals = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100}
    return sum(-vals[c] if i + 1 < len(s) and vals[s[i + 1]] > vals[c] else vals[c] for i, c in enumerate(s))


def verses(chapters: dict) -> dict:
    return {c: {str(i + 1): p for i, p in enumerate(ps)} for c, ps in chapters.items()}


def seneca_dialogues() -> None:
    t = gutenberg(64576)
    books = {}
    for head, body in split(t, r"(?is)<h2[^>]*>(.*?)</h2>"):
        h = text(head)
        match = next(((name, part) for key, name, part in DIALOGUES if key in h), None)
        if not match:
            continue
        name, part = match
        chapters = roman_chapters(blocks(body), prefix=f"{part}." if part else "")
        expect(len(chapters) >= 3, f"{name} {part}: {len(chapters)} chapters")
        books.setdefault(name, {}).update(chapters)
    expect(len(books) == 11, f"Seneca: {sorted(books)}")
    for name, chapters in books.items():
        _put(name, verses(chapters), "Seneca, trans. Aubrey Stewart (1889)")


NOTE_REF = re.compile(r'(?is)<a [^>]*class="(?:pginternal|fnanchor[^"]*)"[^>]*>\s*\[?\d+\]?\s*</a>'
                      r'|<span class="pagenum"[^>]*>.*?</span>')


# ── Seneca, On Benefits (Stewart, 1887) ────────────────────────────────────
# Gutenberg #3794: a book an <h2>, its chapters "II. ..." in the text (the first unnumbered): "On Benefits 4.2:1".

def benefits() -> None:
    t = NOTE_REF.sub("", gutenberg(3794))
    chapters = {}
    for head, body in split(t, r"(?is)<h2[^>]*>(.*?)</h2>"):
        m = re.fullmatch(r"BOOK ([IVX]+)\.", text(head))
        if m:
            chapters.update(roman_chapters(blocks(body), prefix=f"{roman(m.group(1))}."))
    books = sorted({c.split(".")[0] for c in chapters})
    expect(books == [str(n) for n in range(1, 8)] and len(chapters) > 200, f"On Benefits: {books}, {len(chapters)}")
    _put("On Benefits", verses(chapters), "Seneca, trans. Aubrey Stewart (1887)")


# ── Seneca, Natural Questions (Clarke, 1910) ───────────────────────────────
# Gutenberg #76392. A book an <h2>, a chapter an <h3> ("PREFACE" is chapter 0), and the sections Clarke numbers in
# the margin (<span class="sidenote-l">3</span>) the verses: "Natural Questions 2.1:3". Left out: his introduction
# and notes.

def natural_questions() -> None:
    t = NOTE_REF.sub("", gutenberg(76392))
    chapters = {}
    for head, body in split(t, r"(?is)<h2[^>]*>(.*?)</h2>"):
        m = re.match(r"BOOK ([IVX]+)\b", text(head))
        if not m:
            continue
        book = roman(m.group(1))
        for h3, part in split(body, r"(?is)<h3[^>]*>(.*?)</h3>"):
            name = text(h3)
            n = 0 if name == "PREFACE" else roman(name) if re.fullmatch(r"[IVXL]+", name) else None
            expect(n is not None, f"Natural Questions {book}: heading {name!r}")
            part = re.sub(r'(?is)<span class="sidenote-[lr]">\s*(\d+)\s*</span>', r" SECTION\1MARK ", part)
            sections, current = {}, "1"
            for p, para in enumerate(blocks(part)):
                for piece in re.split(r"\s*SECTION(\d+)MARK\s*", para):
                    if piece.isdigit():
                        current = piece
                    elif piece.strip():
                        sections.setdefault(current, []).append((p, piece.strip()))
            # (a section starting mid-paragraph: the paragraph's earlier part ends the section before; pieces of one
            # paragraph either side of a margin number in the same section run on)
            chapters[f"{book}.{n}"] = {k: "".join(("" if i == 0 else " " if v[i - 1][0] == p else "\n") + s
                                                  for i, (p, s) in enumerate(v)) for k, v in sections.items()}
    expect(len(chapters) > 200, f"Natural Questions: {len(chapters)} chapters")
    _put("Natural Questions", chapters, "Seneca, trans. John Clarke (1910)")


# ── Pliny the Younger, Letters (Melmoth, revised Bosanquet) ────────────────
# Gutenberg #2811, the Harvard Classics selection: 109 letters numbered straight through, then the correspondence
# with Trajan. A letter a chapter, its addressee in italics leading it.

MISPRINTS = {"SEPTITTUS": "SEPTITIUS", "JUNSUS": "JUNIUS", "PAISCUS": "PRISCUS", "MAIMUS": "MAXIMUS"}


def _addressee(head: str) -> str:
    """ "To CATILIUS SEVERUS [27]" -> "To Catilius Severus"."""
    who = re.sub(r"\[\d+\]", "", head).strip()
    who = re.sub(r"[A-Z]+", lambda w: MISPRINTS.get(w.group(0), w.group(0)), who)
    who = re.sub(r"\b(And|The|To|His)\b", lambda w: w.group(1).lower(), who.title()).replace("'S", "'s")
    return who[0].upper() + who[1:]


def _small_caps(s: str) -> str:
    """A letter's opening words set in capitals: "I HAVE received", "YOUR letter" -> "I have received", "Your letter"."""
    words = s.split(" ")
    for i, w in enumerate(words):
        if not (w.isupper() and re.fullmatch(r"[A-Z']+[,.;:!?]?", w)):
            break
        words[i] = w if w == "I" else (w[0] + w[1:].lower() if i == 0 else w.lower())
    return " ".join(words)


def pliny_letters() -> None:
    t = NOTE_REF.sub("", gutenberg(2811))
    books = {"Letters of Pliny": {}, "Correspondence with Trajan": {}}
    book = "Letters of Pliny"
    for head, body in split(t, r"(?is)<h2[^>]*>(.*?)</h2>"):
        h = text(head)
        if h.startswith("CORRESPONDENCE WITH THE EMPEROR"):
            book = "Correspondence with Trajan"
        # (some headings misprinted: "LX VII — To MACER", "XXI To PAISCUS")
        m = re.match(r"([IVXLC][IVXLC ]*?)\s*(?:—\s*)?(?=(?:To|TO|TRAJAN)\b)", h)
        if not m:
            continue
        paras = blocks(body)
        expect(paras, f"{book}: letter {h} empty")
        paras[0] = f"*{_addressee(h[m.end():])}*\n{_small_caps(paras[0])}"
        books[book][str(roman(m.group(1).replace(" ", "")))] = {str(i + 1): p for i, p in enumerate(paras)}
    # (the edition numbers its letters straight on from XLIII to XLV: there is no XLIV, and none is missing)
    for name, letters in books.items():
        expect(list(letters) == [str(n) for n in range(1, int(list(letters)[-1]) + 1) if (name, n) != ("Letters of Pliny", 44)],
               f"{name}: {list(letters)}")
    expect(len(books["Letters of Pliny"]) == 109 and len(books["Correspondence with Trajan"]) == 122,
           f"Pliny: {[len(v) for v in books.values()]}")
    for name, letters in books.items():
        _put(name, letters, "Pliny the Younger, trans. William Melmoth, rev. F. C. T. Bosanquet")


# ── Petronius, the Satyricon (Firebaugh, 1922) ─────────────────────────────
# Gutenberg #5225: "CHAPTER THE FIRST." to "...FORTY-FIRST.", their paragraphs the verses. Firebaugh's brackets,
# marking what later forgers or editors supplied, are kept. Left out: his introduction, notes and bibliography.

def satyricon() -> None:
    t = NOTE_REF.sub("", gutenberg(5225))
    t = t[:t.find("VOLUME VI.")]
    chapters = [blocks(body) for head, body in split(t, r"(?is)<h2[^>]*>(.*?)</h2>")
                if text(head).startswith("CHAPTER THE ")]
    expect(len(chapters) == 141 and all(chapters), f"Satyricon: {len(chapters)} chapters")
    _put("Satyricon", {str(n): {str(i + 1): p for i, p in enumerate(ps)} for n, ps in enumerate(chapters, 1)},
         "Petronius, trans. W. C. Firebaugh (1922)")


# ── theoi.com (Aaron Atsma's transcriptions of the Loeb and other translations) ──
# A page's text runs from its <h2>"... TRANSLATED BY ..." to the footnotes. The translators' line or section numbers
# are in the text ("[27] When the founder..."). Left out: note numbers (<sup>), the notes, the cast lists and
# arguments of the plays (<p class="footnotes">). Headings inside the text (the Fasti's dates) are kept, in italics,
# leading what follows them, and a play's speakers in bold.

def theoi_items(page: str) -> list:
    """[(kind, text)] of a page's text in order: kind "h" a heading, "p" a paragraph."""
    from fetch_theoi import fetch
    import html as _html
    t = fetch(page)
    start = re.search(r"(?is)<h[23][^>]*>(?:(?!</h[23]>).)*?TRANSLATED BY", t)   # (an <h3> on one page)
    expect(start, f"theoi {page}: no text")
    t = t[start.start():]
    ends = [i for i in (t.find("SEARCH THEOI"), t.find('<div id="footer')) if i > 0]
    t = t[:min(ends)] if ends else t
    t = re.sub(r'(?is)<div id="book-contents">.*?</div>|<sup>.*?</sup>|<p class="footnotes".*?</p>', "", t)
    items = []
    for m in re.finditer(r"(?is)<(h[2-4]|p)\b[^>]*>(.*?)</\1>", t):
        body = re.sub(r"\s+", " ", m.group(2))                         # (the source's own line wrapping)
        body = re.sub(r"(?is)<(i|em)>\s*(.*?)\s*</\1>", lambda x: f"*{x.group(2)}*" if x.group(2) else "", body)
        body = re.sub(r"(?is)<br\s*/?>", "\n", body)
        body = _html.unescape(re.sub(r"<[^>]+>", "", body)).replace("\xa0", " ")
        body = "\n".join(re.sub(r"\s+", " ", line).strip() for line in body.split("\n")).strip()
        if body:
            items.append(("h" if m.group(1).lower() != "p" else "p", body))
    return items


SPEAKER = re.compile(r"([A-Z][A-Z' ,.&-]{1,40}?)\.?\n")


def _speaker(s: str) -> str:
    """A play's paragraph "CHORUS\n[57] ..." -> "**Chorus**\n[57] ..."."""
    m = SPEAKER.match(s)
    if not m or not m.group(1).isupper():
        return s
    name = re.sub(r"\b(Of|The|And|To)\b", lambda w: w.group(1).lower(), m.group(1).strip().title())
    return f"**{name[0].upper() + name[1:]}**\n" + s[m.end():]


def numbered_passages(items: list, book: str, play: bool = False, skip_headings: int = 1) -> dict:
    """The items cut at each "[N]": {"book.N": {"1": text}}, the shape the bot reads as line-numbered passages."""
    out, key, pending = {}, None, []
    for kind, s in items[skip_headings:]:
        if kind == "h":
            if s not in ("DRAMATIS PERSONAE", "ARGUMENT"):           # (a play's: their text is left out)
                pending.append(f"*{s}*")                         # (the Fasti's dates, as printed: "*KAL. IAN. 1st*")
            continue
        if play:
            s = _speaker(s)
        for piece in re.split(r"\s*\[(\d+)\]\s*", s):
            if piece.isdigit():
                key = f"{book}.{piece}"
                out.setdefault(key, {"1": ""})
                continue
            if not piece.strip():
                continue
            text_ = "\n".join(pending + [piece.strip()])
            pending = []
            if key is None:                                        # (before the first number: line 1)
                key = f"{book}.1"
                out.setdefault(key, {"1": ""})
            joined = out[key]["1"]
            out[key]["1"] = f"{joined}\n{text_}" if joined else text_
    return {k: v for k, v in out.items() if v["1"]}


def _sorted_lines(passages: dict) -> dict:
    return dict(sorted(passages.items(), key=lambda kv: tuple(int(x) for x in kv[0].split("."))))


def theoi_poem(name: str, pages: list, source: str, min_lines: int) -> None:
    from fetch_theoi import contents
    books = []                                   # [(book, items)]: a page's <h2> "... BOOK 2 ..." starts that book
    for page in contents(pages[0]):              # (the Achilleid's second page holds the rest of 1 and all of 2)
        for kind, s in theoi_items(page):
            m = re.search(r"BOOK (\d+)", s) if kind == "h" and "TRANSLATED BY" in s else None
            if m:
                books.append((m.group(1), [(kind, s)]))
            elif books:
                books[-1][1].append((kind, s))
    out = {}
    for book, items in books:
        for k, v in numbered_passages(items, book).items():
            out[k] = {"1": (out[k]["1"] + "\n" + v["1"]) if k in out else v["1"]}
    expect(len(out) >= min_lines, f"{name}: {len(out)} passages")
    _put(name, _sorted_lines(out), source)


def fasti() -> None:
    theoi_poem("Fasti", ["OvidFasti1"], "Ovid, trans. James G. Frazer (1931)", 200)


def thebaid() -> None:
    theoi_poem("Thebaid", ["StatiusThebaid1"], "Statius, trans. J. H. Mozley (1928)", 300)


def achilleid() -> None:
    theoi_poem("Achilleid", ["StatiusAchilleid1A"], "Statius, trans. J. H. Mozley (1928)", 20)


def argonautica() -> None:
    theoi_poem("Argonautica", ["ValeriusFlaccus1"], "Valerius Flaccus, trans. J. H. Mozley (1934)", 200)


# Seneca's tragedies (Miller, 1917): a play a book, its lines in one "chapter 1" ("Thyestes 1:300"). Miller's
# Latin titles, except the three that are also Euripides' and Aeschylus's (Phoenissae is the Perseus catalogue's
# Latin title for Euripides').
TRAGEDIES = {"SenecaAgamemnon": "Agamemnon (Seneca)", "SenecaHerculesFurens": "Hercules Furens",
             "SenecaHerculesOetaeus": "Hercules Oetaeus", "SenecaMedea": "Medea (Seneca)", "SenecaOedipus": "Oedipus",
             "SenecaPhaedra": "Phaedra", "SenecaPhoenissae": "Phoenissae (Seneca)", "SenecaThyestes": "Thyestes",
             "SenecaTroades": "Troades"}


def seneca_tragedies() -> None:
    for page, name in TRAGEDIES.items():
        items = theoi_items(page)
        if page == "SenecaHerculesOetaeus":
            items += theoi_items("SenecaHerculesOetaeus2")[1:]
        passages = numbered_passages(items, "1", play=True)
        expect(len(passages) >= 25, f"{name}: {len(passages)} passages")
        _put(name, _sorted_lines(passages), "Seneca, trans. Frank Justus Miller (1917)")


# ── ToposText (topostext.org: theoi.com's transcriptions, complete where theoi's own pages now aren't) ───────
# A paragraph a <div class="pSelector" id=50>, "§ 50  ADMETUS: When great numbers...". Left out: its links to
# places and people (the words kept), and its "Event Date" lines.

def topos(work: int) -> list:
    """[(id, title, text)] of a ToposText work's paragraphs; the work cached in scripts/.cache/topos/."""
    import html as _html
    import urllib.request
    path = ROOT / "scripts" / ".cache" / "topos" / f"{work}.html"
    if not path.exists():
        req = urllib.request.Request(f"https://topostext.org/work/{work}",
                                     headers={"User-Agent": "ScriptureBot corpus builder (personal Discord bot)"})
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(urllib.request.urlopen(req, timeout=120).read().decode("utf-8", "replace"), encoding="utf-8")
    out = []
    for pid, body in re.findall(r'(?s)<div class="pSelector" id=([^\s>]+)>(.*?)</div>', path.read_text(encoding="utf-8")):
        body = re.sub(r"(?is)<b>\s*&sect;[^<]*</b>", "", body)
        body = re.sub(r"(?is)<br\s*/?>", "\n", re.sub(r"\s+", " ", body))
        body = _html.unescape(re.sub(r"<[^>]+>", "", body)).replace("\xa0", " ")
        body = "\n".join(re.sub(r" +", " ", line).strip() for line in body.split("\n")).strip()
        body = re.sub(r" ([,.;:!?)])", r"\1", body)                # (a space left where a link ended: "Cyclopes .")
        body = re.sub(r"^(?:\d+[A-Z]?|[CLXVI]+)\.?\s+(?=[A-Z]{2})", "", body)   # ("1 THEMISTO:", "CCLXXIII. THOSE...")
        # "ADMETUS: When...", "PHAETHON Phaethon, son...", "NIOBA [NIOBE] OR IO: ...", "THOSE WHO WERE MOST FAMOUS:... son"
        m = re.match(r"([A-Z][A-Z0-9 ,.'’&()\[\]-]+?)(?::(?:\.\.\.)?\s*(?=\S)|\s+(?=[A-Z][a-z]))", body)
        title = _title(m.group(1)) if m and m.group(1).isupper() and not body.isupper() else ""
        if title:
            rest = body[m.end():]
            # (the text beginning mid-list, "FAMOUS:... son of Jove": the gap shown)
            body = ("… " + rest) if body[len(m.group(1)):].startswith(":...") else rest
        if body:
            out.append((pid, title, body))
    return out


# ── Hyginus, Fabulae (Grant, 1960): a fable a chapter, its title leading it; the Preface chapter 0 ─────────
# 245 of the 277: the rest (208-218, 227-237, 259-266...) are lost, known only from the ancient list of titles.

def fabulae() -> None:
    chapters = {}
    for pid, title, body in topos(206):
        if pid == "E":                                             # (ToposText's "END")
            continue
        if body.isupper():                                         # ("CCVII — CCXVIII ARE MISSING": a note)
            body = "*" + re.sub(r"\b(?![CLXVI]+\b)([A-Z]+)\b", lambda w: w.group(1).lower(), body).replace(
                "servius", "Servius").replace("seven", "Seven") + "*"
        m = re.fullmatch(r"(\d+)([A-Z]?|\.\d+)", pid)
        entry = f"*{title}*\n{body}" if title else body
        if m:                                       # ("152A", Grant's: a second fable in 152; "14.2", 14 going on)
            chapters.setdefault(m.group(1), []).append(entry)
        else:                                                      # ("0.2", "p.4": the preface's paragraphs)
            chapters.setdefault("0", []).append(entry)
    numbers = sorted(int(c) for c in chapters)
    expect(numbers[0] == 0 and numbers[-1] == 277 and len(numbers) >= 245, f"Fabulae: {numbers[:3]}...{numbers[-3:]}")
    _put("Fabulae", {str(c): {str(i + 1): p for i, p in enumerate(chapters[str(c)])} for c in numbers},
         "Hyginus, trans. Mary Grant (1960)")


# ── Hyginus, Astronomica, Book 2: the myths of the constellations (Grant, 1960) ─────────────────────────────
# All ToposText (and theoi) have of it: Books 1, 3 and 4 are the astronomy proper. "2.1.3" is chapter "2.1" verse 3.

def astronomica() -> None:
    chapters = {}
    for pid, title, body in topos(207):
        m = re.fullmatch(r"(\d+\.\d+)\.(\d+)", pid)
        if m:
            chapters.setdefault(m.group(1), {})[m.group(2)] = f"*{title}*\n{body}" if title else body
    expect(len(chapters) == 43, f"Astronomica: {len(chapters)} chapters")
    _put("Astronomica", chapters, "Hyginus, trans. Mary Grant (1960)")


# ── Dares and Dictys, the "eyewitness" histories of the Trojan War (Frazer, 1966) ─────────────────────────

def dares() -> None:
    chapters, key = {}, "0"
    for kind, s in theoi_items("DaresPhrygius")[1:]:
        for piece in re.split(r"\s*\[(LETTER|\d+)\]\s*", s):
            if piece == "LETTER" or piece.isdigit():
                key = "0" if piece == "LETTER" else piece
            elif piece.strip():
                chapters.setdefault(key, []).append(piece.strip())
    expect(len(chapters) >= 44, f"Dares: {len(chapters)}")
    _put("The Fall of Troy", verses(chapters), "Dares Phrygius, trans. R. M. Frazer (1966)")


def dictys() -> None:
    from fetch_theoi import contents
    words = {"ONE": 1, "TWO": 2, "THREE": 3, "FOUR": 4, "FIVE": 5, "SIX": 6}
    chapters, book, key = {}, None, None
    for page in contents("DictysCretensis1"):
        for kind, s in theoi_items(page):
            if kind == "h":
                m = re.search(r"BOOK (\w+)", s)
                book = str(words.get(m.group(1), m.group(1))) if m else "0" if re.match(r"LETTER|PREFACE", s) else book
                key = "1" if book == "0" and s.startswith("LETTER") else "2" if book == "0" else None
                continue
            if book is None:
                continue
            for piece in re.split(r"\s*\[(\d+)\]\s*", s):
                if piece.isdigit():
                    key = piece
                elif piece.strip() and key:
                    v = chapters.setdefault(book, {})
                    v[key] = f"{v[key]}\n{piece.strip()}" if key in v else piece.strip()
    expect(sorted(chapters) == ["0", "1", "2", "3", "4", "5", "6"], f"Dictys: {sorted(chapters)}")
    _put("Journal of the Trojan War", chapters, "Dictys Cretensis, trans. R. M. Frazer (1966)")


# ── Fulgentius, Mythologies (Whitbread, 1971): "1.1 THE ORIGIN OF IDOLS" chapter "1.1", a prologue "1.0" ───

def _title(s: str) -> str:
    """ "THE ORIGIN OF IDOLS" -> "The Origin of Idols"."""
    s = re.sub(r"\b(Of|The|And|To|In|With|A|An|On|By|For|From|Or)\b", lambda w: w.group(1).lower(), s.strip().title())
    return s[0].upper() + s[1:]


def fulgentius() -> None:
    from fetch_theoi import contents
    chapters, key = {}, None
    for page in contents("FulgentiusMythologies1"):
        for kind, s in theoi_items(page)[1:]:
            if kind == "h":
                m = re.match(r"(\d)\.(\d+)\.?\s+(.*)|BOOK (\d) PROLOGUE", s)
                if m:
                    key = f"{m.group(1)}.{m.group(2)}" if m.group(1) else f"{m.group(4)}.0"
                    title = _title(m.group(3)) if m.group(1) else "Prologue"
                    chapters[key] = [f"*{title}*"]
                    continue
            if key:
                chapters[key].append(f"*{s}*" if kind == "h" else s)
    for key, paras in chapters.items():                           # (the title leading the first paragraph)
        if len(paras) > 1:
            chapters[key] = [paras[0] + "\n" + paras[1]] + paras[2:]
    expect(len(chapters) > 40, f"Fulgentius: {len(chapters)}")
    _put("Mythologies", verses(chapters), "Fulgentius, trans. Leslie George Whitbread (1971)")


# ── Seneca, Moral Letters to Lucilius (Gummere, 1917-25), from Wikisource ──────────────────────────────────
# A letter a page; Gummere's section numbers ("4. You may desire...") are where the Loeb prints them, not at every
# paragraph, so a letter is stored as passages from each number ("1.4"), the shape the bot reads like a poem's
# lines: "Moral Letters 1:5" is the passage holding section 5. The letter's title and greeting lead its first.

def moral_letters() -> None:
    passages = {}
    for n in range(1, 125):
        paras = ws_blocks(wikisource(f"Moral letters to Lucilius/Letter {n}"))
        paras = [p for p in paras if p != "THE EPISTLES OF SENECA"]
        head = next((i for i, p in enumerate(paras) if p.isupper() and len(p) < 150), None)   # ("XCI. ON THE...")
        expect(head is not None, f"Letter {n}: no title in {[p[:30] for p in paras[:3]]}")
        title = _title(re.sub(r"^[CLXVI]+\.\s*", "", paras[head]))
        lead, key = [f"*{title}*"], f"{n}.1"
        for p in paras[head + 1:]:
            m = re.match(r"(\d+)\.\s+(?=\S)", p)
            if m and int(m.group(1)) > int(key.split(".")[1]):
                key = f"{n}.{m.group(1)}"
                p = p[m.end():]
            elif m and key == f"{n}.1" and m.group(1) == "1":
                p = p[m.end():]
            passages.setdefault(key, {"1": ""})
            joined = "\n".join(([passages[key]["1"]] if passages[key]["1"] else []) + lead + [p])
            passages[key]["1"], lead = joined, []
    letters = {k.split(".")[0] for k in passages}
    expect(len(letters) == 124, f"Moral Letters: {len(letters)} letters")
    _put("Moral Letters to Lucilius", _sorted_lines(passages), "Seneca, trans. Richard M. Gummere (1917-25)")


BUILDS = {"old_age": old_age, "distichs": distichs, "cato": cato, "varro": varro, "seneca_dialogues": seneca_dialogues,
          "benefits": benefits, "natural_questions": natural_questions, "pliny_letters": pliny_letters,
          "satyricon": satyricon, "fasti": fasti, "thebaid": thebaid, "achilleid": achilleid,
          "argonautica": argonautica, "seneca_tragedies": seneca_tragedies, "fabulae": fabulae, "dares": dares,
          "dictys": dictys, "fulgentius": fulgentius, "astronomica": astronomica, "moral_letters": moral_letters}


def main(names: list) -> None:
    for name in names or BUILDS:
        print(name)
        BUILDS[name]()


if __name__ == "__main__":
    main(sys.argv[1:])
