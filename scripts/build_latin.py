"""
Latin authors the library lacked, into data/classical/latin.json (run scripts/clean_corpora.py after):

  old_age     Cicero's Cato Maior, On Old Age (Shuckburgh), from Gutenberg #2808 (his On Friendship the bot has)
  distichs    The Distichs of Cato (Chase, 1922), from Wikisource
  cato        Cato the Elder's On Agriculture, complete (Hooper and Ash's Loeb, 1934), from LacusCurtius: Harrison's
              translation on Gutenberg (#12140) is a digest of about a third of it
  varro       Varro's On Agriculture (the same Loeb), from LacusCurtius
  historia_augusta   the Historia Augusta, the thirty lives (Magie's Loeb, 1921-32), from LacusCurtius
  stratagems, aqueducts   Frontinus (Bennett's Loeb, 1925), from LacusCurtius
  velleius    Velleius Paterculus, Roman History (Shipley's Loeb, 1924), from LacusCurtius
  florus      Florus, Epitome of Roman History (Forster's Loeb, 1929), from LacusCurtius
  seneca_dialogues   Seneca's Minor Dialogues and On Clemency (Stewart, 1889), Gutenberg #64576
  benefits    Seneca's On Benefits (Stewart, 1887), Gutenberg #3794
  natural_questions  Seneca's Natural Questions (Clarke, 1910), Gutenberg #76392
  moral_letters      Seneca's Moral Letters to Lucilius (Gummere's Loeb), from Wikisource
  seneca_tragedies   Seneca's nine tragedies (Miller's Loeb, 1917), from theoi.com
  pliny_letters      Pliny the Younger's Letters and the Trajan correspondence (Melmoth/Bosanquet), Gutenberg #2811
  satyricon   Petronius (Firebaugh, 1922), Gutenberg #5225
  natural_history    Pliny the Elder's Natural History (Bostock and Riley, 1855-57), Gutenberg's six volumes
  fasti, thebaid, achilleid, argonautica   Ovid, Statius and Valerius Flaccus (Frazer's and Mozley's Loebs), theoi.com
  fabulae, astronomica   Hyginus (Grant, 1960), from ToposText: theoi.com's own pages now hold only a few fables
  dares, dictys, fulgentius   the Trojan War "eyewitnesses" (Frazer, 1966) and the Mythologies (Whitbread), theoi.com
  juvenal     Juvenal's Satires (Ramsay's Loeb, 1918), from Wikisource, by the Latin lines
  martial     Martial's Epigrams (Bohn, 1897; Ker's Loeb where Bohn gave Italian), Roger Pearse's tertullian.org

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

TAG = r'(?:[^>"]|"[^"]*")*'                       # (a tag's attributes: Thayer's pop-ups put ">" inside quotes)
HEAD, HEAD_END = "\x01", "\x02"                  # (a heading, kept through the cleaning, then set before what follows)


def _lacus_text(s: str) -> str:
    import html as _html
    s = re.sub(r"\s+", " ", s)                                       # (the source's own line wrapping)
    s = re.sub(rf"(?is)<(i|em)\b{TAG}>(.*?)</\1>", lambda x: f"*{x.group(2).strip()}*" if x.group(2).strip() else "", s)
    s = re.sub(rf"(?is)<P\b{TAG}>|<BR\b{TAG}>|</?TR\b{TAG}>", "\n", s)
    s = _html.unescape(re.sub(rf"<{TAG}>", "", s)).replace("\xa0", " ")
    # (Thayer's pointer to the next page: "(For the end of chapter 14, see Part 2.)", "...continue on...")
    s = re.sub(r"(?s)\*?\(For the (?:beginning|end|rest) of chapter [^)]*\)\*?", "", s)
    s = "\n".join(re.sub(r"\s+", " ", line).strip() for line in s.split("\n"))
    s = re.sub(r"(?:\*\s+){2,}\*|(?:\.\s+){2,}\.", "…", s)           # (a gap, "* * *" or ". . .": one mark)
    s = re.sub(r"(?<=\w)\*\*(?=\w)", "", s)                          # (two italic runs meeting: "*a**b*")
    s = re.sub(r" ([,.;:!?])", r"\1", s)
    return re.sub(r"\n{2,}", "\n", s).strip()


def lacus(pages: list, prefix: str = "", book_in_label: bool = False) -> dict:
    """{chapter: {section: text}} of a work's pages; `prefix` before each chapter ("2." for Varro's second book), or
    with `book_in_label` the book named in the chapter's mark (Florus's "III, 5" is "3.5").

    A chapter's mark is <A CLASS="chapter" NAME="12">12</A> (or with no NAME, or the book's number in a <SPAN>:
    Florus's "I, 12"), a section's <A CLASS="sec" NAME="12.3">3</A>. The text before a page's first mark is the
    work's (or book's) preface, chapter 0, unless the first mark is a "N.2" (Cato's preface: section 1 unmarked).
    Headings (<H3>, <H4>: Frontinus's chapter titles, the Thirty Pretenders' names) lead the next section in italics,
    without their Roman numeral. Left out: the page's own title (H1, H2), the link to the Latin beside each
    paragraph, the cross-references to another translation, page numbers, note numbers and the notes, the unit
    conversions (pop-ups), the tables of contents, and Thayer's own remarks ("For the end of chapter 14, see...")."""
    from fetch_lacus import fetch
    out, pending, chap = {}, [], None
    for page in pages:
        t = fetch(page)
        ends = [i for i in (t.find('<HR CLASS="endnotes"'), t.find('<TABLE CLASS="footer"')) if i > 0]
        t = t[:min(ends)] if ends else t
        t = re.sub(r"(?s)<!--.*?-->", "", t)
        t = re.sub(rf'(?is)<A HREF="\s*L/[^"]*"{TAG}>\s*<IMG{TAG}>\s*</A>', " ", t)       # (the Latin page's link)
        t = re.sub(rf'(?is)<A CLASS="(?:parallel|ref|conversion)"{TAG}>.*?</A>|<SPAN CLASS="pagenum">.*?</SPAN>', "", t)
        t = re.sub(rf'(?is)<A\b{TAG}>\s*•\s*</A>|<SPAN CLASS="(?:ref|superscript)">•</SPAN>', "", t)   # (Thayer's • pop-ups and marks)
        t = t.replace("&shy;", "").replace("&#8288;", "").replace("­", "")
        t = re.sub(rf'(?is)<SPAN CLASS="[^"]*">\s*\*\s*(?:</SPAN>\s*)?<IMG{TAG}ALT="lacuna"{TAG}>(?:\s*</SPAN>)?',
                   " … ", t)                                                               # (a gap in the text)
        t = re.sub(rf'(?is)<TABLE(?! CLASS="verse"){TAG}>.*?</TABLE>', "", t)          # (a table of contents)
        t = re.sub(rf"(?is)<(H[34])\b{TAG}>(.*?)</\1>",
                   lambda m: HEAD + re.sub(r"^[IVXL]+\.\s+", "", _lacus_text(m.group(2)).replace("\n", " ")) + HEAD_END,
                   t)
        mark = re.compile(rf'(?is)<A CLASS="(chapter|sec)"(?: NAME="([^"]*)")?{TAG}>((?:[^<]|<SPAN{TAG}>[^<]*</SPAN>)*)</A>')
        marks = [(m.group(1).lower(), m.group(2), m.group(3), m.start(), m.end()) for m in mark.finditer(t)]
        if not marks:
            print(f"    {page}: no marks")
            continue
        # the text starts after the last title (H1/H2) before the first mark
        start = max(t.rfind("</H1>", 0, marks[0][3]), t.rfind("</H2>", 0, marks[0][3]))
        start = start + 5 if start >= 0 else 0
        if marks[0][0] == "sec" and marks[0][1].endswith(".2"):
            marks.insert(0, ("sec", marks[0][1][:-2] + ".1", "", start, start))
        else:                          # (a later page's top: a heading, or the end of the last page's section)
            marks.insert(0, ("preface" if chap is None else "continue", "0", "", start, start))
        for i, (kind, name, label, _, after) in enumerate(marks):
            end = marks[i + 1][3] if i + 1 < len(marks) else len(t)
            pieces = re.split(f"{HEAD}(.*?){HEAD_END}", t[after:end])
            body = _lacus_text(pieces[0])
            if kind == "preface":
                key, s = prefix + "0", "1"
            elif kind == "continue":
                key, s = chap, list(out[chap])[-1] if out.get(chap) else "1"
            elif kind == "chapter":
                book = re.match(r"\(?([IVX]+),\s", re.sub(r"<[^>]*>", "", label))
                if book_in_label and book:                 # (Florus's "III, 5": Book 3, chapter 5)
                    prefix = f"{roman(book.group(1))}."
                number = name or re.sub(r"<[^>]*>[^<]*<[^>]*>|\D", "", label)
                chap = prefix + ("0" if number == "Introduction" else number)
                # (a chapter's mark again at the top of a page: what follows continues its last section)
                key, s = chap, list(out[chap])[-1] if out.get(chap) else "1"
            else:
                c, _, s = name.rpartition(".")
                c = "0" if c == "Introduction" else c
                # a section belongs to the chapter it sits in (the page names one "3131.2", in chapter 31)
                key = chap if chap is not None else prefix + c
                if chap is not None and prefix + c != chap:
                    print(f"    {page}: section {name} in chapter {chap}")
            if kind == "preface" and body == "…":          # (the Two Valerians: a row of dots, then 1:1's own "…")
                body = ""
            if body and kind == "preface":                  # (an unnumbered preface: a paragraph a verse)
                lines = body.split("\n")
                lines[0], pending = "\n".join(pending + [lines[0]]), []
                out[key] = {str(n): p for n, p in enumerate(lines, 1)}
                s = str(len(lines))
            elif body:
                body = "\n".join(pending + [body])
                pending = []
                out.setdefault(key, {})[s] = (out.get(key, {}).get(s, "") + " " + body).strip()
            elif kind == "chapter":
                out.setdefault(key, {})
            # headings after the section's text: the next section's title, or, with text after it, inside this one
            for j in range(1, len(pieces), 2):
                head, rest = f"*{pieces[j].strip()}*", _lacus_text(pieces[j + 1])
                if rest and key in out and s in out[key]:
                    out[key][s] += f"\n{head}\n{rest}"
                elif head != "**":
                    pending.append(head)
                    if rest:
                        print(f"    {page}: text after heading {head} with no section: {rest[:60]!r}")
    return {c: v for c, v in out.items() if v}


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


def _numbered(chapters: dict) -> dict:
    return dict(sorted(chapters.items(), key=lambda kv: tuple(int(x) for x in kv[0].split("."))))


# The Historia Augusta (Magie's Loeb, 1921-32): a life a book, "Historia Augusta: Hadrian 14:7". The Loeb's titles,
# as Thayer gives them; the pages of a long life (Hadrian's two) run on.
HISTORIA_AUGUSTA = [
    ("Hadrian", ["Hadrian/1", "Hadrian/2"]), ("Aelius", ["Aelius"]), ("Antoninus Pius", ["Antoninus_Pius"]),
    ("Marcus Aurelius", ["Marcus_Aurelius/1", "Marcus_Aurelius/2"]), ("Lucius Verus", ["Lucius_Verus"]),
    ("Avidius Cassius", ["Avidius_Cassius"]), ("Commodus", ["Commodus"]), ("Pertinax", ["Pertinax"]),
    ("Didius Julianus", ["Didius_Julianus"]), ("Septimius Severus", ["Septimius_Severus"]),
    ("Pescennius Niger", ["Pescennius_Niger"]), ("Clodius Albinus", ["Clodius_Albinus"]), ("Caracalla", ["Caracalla"]),
    ("Geta", ["Geta"]), ("Opellius Macrinus", ["Macrinus"]), ("Diadumenianus", ["Diadumenianus"]),
    ("Elagabalus", ["Elagabalus/1", "Elagabalus/2"]),
    ("Severus Alexander", ["Severus_Alexander/1", "Severus_Alexander/2", "Severus_Alexander/3"]),
    ("The Two Maximini", ["Maximini_duo"]), ("The Three Gordians", ["Gordiani_tres"]),
    ("Maximus and Balbinus", ["Maximus_et_Balbinus"]), ("The Two Valerians", ["Valeriani_duo"]),
    ("The Two Gallieni", ["Gallieni_duo"]), ("The Thirty Pretenders", ["Tyranni_XXX"]),
    ("The Deified Claudius", ["Claudius"]), ("Aurelian", ["Aurelian/1", "Aurelian/2", "Aurelian/3"]),
    ("Tacitus", ["Tacitus"]), ("Probus", ["Probus"]),
    ("Firmus, Saturninus, Proculus and Bonosus", ["Firmus_et_al"]), ("Carus, Carinus and Numerian", ["Carus_et_al"]),
]


def historia_augusta() -> None:
    for name, pages in HISTORIA_AUGUSTA:
        chapters = lacus([f"E/Roman/Texts/Historia_Augusta/{p}*.html" for p in pages])
        expect(len(chapters) >= 5, f"Historia Augusta {name}: {len(chapters)} chapters")
        _put(f"Historia Augusta: {name}", _numbered(chapters), "trans. David Magie (1921-32)")


# Frontinus (Bennett's Loeb, 1925): the Stratagems by book and chapter ("Stratagems 1.4:2", a book's preface its
# chapter 0), each chapter's title leading it; the Aqueducts by Frontinus's own chapters, 1-130, straight through
# the two books. (Thayer also has R. H. Rodgers's 2003 Aqueducts; the bot takes the Loeb, like the Stratagems.)

def stratagems() -> None:
    chapters = {}
    for book in (1, 2, 3, 4):
        chapters.update(lacus([f"E/Roman/Texts/Frontinus/Strategemata/{book}*.html"], prefix=f"{book}."))
    expect(sorted({c.split(".")[0] for c in chapters}) == ["1", "2", "3", "4"] and len(chapters) > 45,
           f"Stratagems: {len(chapters)} chapters")
    _put("Stratagems", _numbered(chapters), "Frontinus, trans. Charles E. Bennett (1925)")


def aqueducts() -> None:
    raw = lacus([f"E/Roman/Texts/Frontinus/De_Aquis/Bennett/{p}*.html" for p in (1, 2)])
    note = raw.pop("0", {})                                       # (Thayer's: "The flags in the text are links...")
    expect(all("links to" in v for v in note.values()), f"Aqueducts: a preface? {note}")
    chapters = {c.rpartition(".")[2]: v for c, v in raw.items()}
    expect(len(chapters) == len(raw) and sorted(map(int, chapters)) == list(range(1, 131)),
           f"Aqueducts: {sorted(raw)[:3]}...{sorted(raw)[-3:]}")
    _put("The Aqueducts of Rome", _numbered(chapters), "Frontinus, trans. Charles E. Bennett (1925)")


# Velleius Paterculus, the Roman History (Shipley's Loeb, 1924): "Roman History 2.94:1". Book 1 survives only in
# part (its opening and the chapters after 8 are lost).

def velleius() -> None:
    chapters = lacus(["E/Roman/Texts/Velleius_Paterculus/1*.html"], prefix="1.")
    chapters.update(lacus([f"E/Roman/Texts/Velleius_Paterculus/2{x}*.html" for x in "ABCD"], prefix="2."))
    expect(len([c for c in chapters if c.startswith("2.")]) == 131, f"Velleius: {len(chapters)} chapters")
    _put("Roman History", _numbered(chapters), "Velleius Paterculus, trans. Frederick W. Shipley (1924)")


# Florus, the Epitome of Roman History (Forster's Loeb, 1929). Forster prints it in two books of titled chapters
# (Book II's 22nd to 34th all within one chapter of the other numbering), but numbers the sections, as Thayer's
# marks do, by the older division into four books: so "Epitome of Roman History 4.2:13" (Halm's numbers; the
# introduction 1.0), each of Forster's chapter titles leading the section it starts at.

def florus() -> None:
    chapters = lacus([f"E/Roman/Texts/Florus/Epitome/{x}*.html" for x in
                      [f"1{c}" for c in "ABCDEFGHIJKLM"] + [f"2{c}" for c in "ABCDEFGHI"]], prefix="1.", book_in_label=True)
    # (Thayer sets Forster's first title above the introduction; it belongs to chapter 1, Romulus)
    title, _, rest = chapters["1.0"]["1"].partition("\n")
    expect(title.startswith("*The period of the Seven Kings"), f"Florus: introduction {title!r}")
    chapters["1.0"]["1"], chapters["1.1"]["1"] = rest, f"{title}\n{chapters['1.1']['1']}"
    books = {b: sum(c.startswith(f"{b}.") for c in chapters) for b in "1234"}
    expect(books == {"1": 27, "2": 20, "3": 23, "4": 12}, f"Florus: {books}")
    _put("Epitome of Roman History", _numbered(chapters), "Florus, trans. E. S. Forster (1929)")


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
    s = re.sub(r"\b(Of|The|And|To|In|With|A|An|On|By|For|From|Or|As)\b", lambda w: w.group(1).lower(), s.strip().title())
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


# ── Pliny the Elder, Natural History (Bostock and Riley, 1855-57) ──────────────────────────────────────────
# Gutenberg, six volumes. A book an <h2> ("BOOK II. AN ACCOUNT OF THE WORLD..."), a chapter an <h3> ("CHAP. 5. (7.)—
# OF GOD."): Bostock's chapter numbers (the bracketed ones are the other numbering, left out), so "Natural History
# 2.5" is Book 2 chapter 5, its title leading it. Book 1, Pliny's dedication, is "1.1". Left out: the translators'
# preface, life of Pliny, tables of money and measures, footnotes, index and errata.

NATURAL_HISTORY = (57493, 60230, 59131, 61113, 60688, 62704)


def natural_history() -> None:
    chapters = {}
    for vol in NATURAL_HISTORY:
        t = NOTE_REF.sub("", gutenberg(vol))
        for head, body in split(t, r"(?is)<h2[^>]*>(.*?)</h2>"):
            m = re.match(r"BOOK ([IVXL]+)\.", text(head))
            if not m:
                continue
            book = roman(m.group(1))
            parts = split(body, r"(?is)<h3[^>]*>(.*?)</h3>")
            if not parts:                                          # (Book 1: the dedication, no chapters)
                chapters[f"{book}.1"] = blocks(body)
                continue
            for h3, part in parts:
                # ("CHAP 90.", "27.—CARMANIA.", "CHAPS. 1 & 2. (1.)—THE NATURE OF THE VINE": the first number)
                c = re.match(r"(?:CHAPS?[.,]?\s*)?(\d+)(?:\s*&\s*\d+)?\s*[.,]?\s*(?:\(\d+\.?\)\s*)?[—-]*\s*(.*)", text(h3))
                expect(c, f"Natural History {book}: heading {text(h3)!r}")
                # (Bostock's "* * * *", a gap in Pliny's text, shown as one; italics inside a title dropped, the
                # title being in italics)
                paras = [re.sub(r"\s*\*(?:\s+\*)+(?=[\s.,;:)]|$)", " … ", p).replace("  ", " ").strip() for p in blocks(part)]
                title = _title(c.group(2).replace("*", "").rstrip(". "))
                key = f"{book}.{c.group(1)}"
                if key in chapters:                                # (a number printed twice: keep both, in order)
                    chapters[key] += [f"*{title}*"] + paras
                else:
                    chapters[key] = [f"*{title}*\n{paras[0]}" if paras else f"*{title}*"] + paras[1:]
    books = sorted({int(k.split(".")[0]) for k in chapters})
    expect(books == list(range(1, 38)), f"Natural History: books {books}")
    ordered = dict(sorted(chapters.items(), key=lambda kv: tuple(int(x) for x in kv[0].split("."))))
    _put("Natural History", verses(ordered), "Pliny the Elder, trans. John Bostock and H. T. Riley (1855-57)")


# ── Juvenal, Satires (Ramsay's Loeb, 1918), from Wikisource ────────────────────────────────────────────────
# A satire a page ("Juvenal and Persius/The Satires of Juvenal/Satire 10"), its paragraphs marked with the Latin line
# each begins at (<span class="wst-verse" id="23">), so a satire is stored as passages from each ("10.23") and
# "Juvenal 10:356" is the passage holding line 356. The heading ("SATIRE X") and Ramsay's title ("The Vanity of
# Human Wishes") lead line 1. The Oxford fragment in Satire 6 (lines "O1"-"O34", after 365) goes with the passage
# it stands in.

def juvenal() -> None:
    passages = {}
    for n in range(1, 17):
        t = wikisource(f"Juvenal and Persius/The Satires of Juvenal/Satire {n}")
        paras = []
        for m in re.finditer(r"(?is)<p\b[^>]*>(.*?)</p>", t):
            ids = re.findall(r'class="wst-verse[^"]*" id="([^"]+)"', m.group(1))
            s = text(m.group(1))
            if s:
                paras.append((ids[0] if ids else None, s))
        head = next((i for i, (_, p) in enumerate(paras) if re.fullmatch(r"SATIRE [IVXL]+", p)), None)
        expect(head is not None and paras[head][1] == f"SATIRE {_ROMAN_OF[n]}", f"Satire {n}: no heading")
        title, body = paras[head + 1][1], paras[head + 2:]
        expect(len(title) < 80 and not title.endswith("."), f"Satire {n}: title {title!r}")
        title = JUVENAL_LATIN_TITLES.get(title.lower(), title)
        key, lead = f"{n}.1", [f"*{_title(title)}*"]
        for line, p in body:
            if line and line.isdigit() and int(line) > int(key.split(".")[1]):
                key = f"{n}.{line}"
            passages.setdefault(key, {"1": ""})
            passages[key]["1"] = "\n".join(([passages[key]["1"]] if passages[key]["1"] else []) + lead + [p])
            lead = []
    satires = {k.split(".")[0] for k in passages}
    expect(len(satires) == 16 and len(passages) > 200, f"Juvenal: {len(satires)} satires, {len(passages)} passages")
    # each satire's last line, so a line in its last passage is found ("Juvenal 10:356"): from the Perseus Latin
    # (canonical-latinLit, its satires cited "book.satire"), Ramsay's pages not saying where a satire ends
    sys.path.insert(0, str(ROOT))
    from perseus_tei import passages as tei_passages, to_book
    latin = to_book(tei_passages(ROOT / "canonical-latinLit/data/phi1276/phi001/phi1276.phi001.perseus-lat2.xml"))
    last = {c.split(".")[1]: max(int(re.match(r"\d+", k).group()) for k in v) for c, v in latin.items()}
    expect(sorted(last, key=int) == [str(n) for n in range(1, 17)], f"Juvenal's Latin: satires {sorted(last)}")
    for k in passages:
        sat, line = k.split(".")
        expect(int(line) <= last[sat], f"Juvenal {k}: past the satire's last line, {last[sat]}")
    payload = _load()
    payload["books"]["Juvenal"] = _sorted_lines(passages)
    payload["book_sources"]["Juvenal"] = "Satires, trans. G. G. Ramsay (Loeb, 1918)"
    payload.setdefault("last_lines", {})["Juvenal"] = last
    _save(payload)


# Ramsay titles three satires with their famous Latin tags: given instead in his own English for those lines
# (1.30, 3.41, 8.1), the library being English
JUVENAL_LATIN_TITLES = {"difficile est saturam non scribere": "It Is Hard Not to Write Satire",
                        "quid romae faciam?": "What Can I Do at Rome?",
                        "stemmata quid faciunt?": "What Avail Your Pedigrees?"}
_ROMAN_OF = {n: r for n, r in enumerate("I II III IV V VI VII VIII IX X XI XII XIII XIV XV XVI".split(), 1)}


# ── Martial, Epigrams (Bohn's Classical Library, 1897), from tertullian.org ─────────────────────────────────
# Roger Pearse's transcription (2008), a book a page: an epigram a heading ("<A NAME="C46"></A>XLVI. TO HEDYLUS."),
# its prose under it, its notes in a <blockquote> (left out). Where Bohn printed an epigram in Italian, not English,
# Pearse gives the Loeb's (Ker, 1919-20) and says so ("[From the Loeb translation]"): kept, after the title. A book
# is a chapter, an epigram a verse ("Martial 1:47"); a book's prose preface (1, 2, 8, 9, 12) is verse 0.
MARTIAL_CACHE = ROOT / "scripts" / ".cache" / "martial"
MARTIAL_COUNTS = {1: 118, 2: 93, 3: 100, 4: 89, 5: 84, 6: 94, 7: 99, 8: 82, 9: 103, 10: 104, 11: 108, 12: 98, 13: 127,
                  14: 223}


def _martial_page(n: int) -> str:
    import urllib.request
    f = MARTIAL_CACHE / f"book{n:02d}.htm"
    if not f.exists():
        f.parent.mkdir(parents=True, exist_ok=True)
        url = f"https://www.tertullian.org/fathers/martial_epigrams_book{n:02d}.htm"
        f.write_bytes(urllib.request.urlopen(urllib.request.Request(
            url, headers={"User-Agent": "ScriptureBotCorpusBuilder/1.0 (Discord bot; low-volume one-off import)"}),
            timeout=120).read())
    return f.read_bytes().decode("latin-1")


def _martial_body(seg: str) -> "tuple[str, str]":
    """(the title, the epigram's text) of one heading's stretch."""
    # (the notes' blockquotes, which open with a note number or are "smallish"; one holding an epigram's own text,
    # 11.58's verse rendering, stays)
    def quote(m):
        body = m.group(1)
        note = re.match(r"(?is)\s*<p[^>]*>\s*(?:&nbsp;|\s)*<sup>", body) or not re.search(r"(?i)<p align=\"?justify", body)
        return " " if note else body
    seg = re.sub(r"(?is)<blockquote>(.*?)</blockquote>", quote, seg)
    seg = re.split(r"(?i)This text was transcribed by Roger Pearse|<hr", seg)[0]
    title_html, _, rest = seg.partition("</p>")             # (the heading's paragraph: some have no title, no <b>)
    title = text(re.sub(r"(?is)^.*?</SPAN>", "", title_html))
    note, out = [], []
    for m in re.finditer(r"(?is)<p\b([^>]*)>(.*?)</p>", rest):
        s = text(m.group(2), lines=True)                    # (a verse rendering's lines kept)
        if not s:
            continue
        if "smallish" in m.group(1):
            if s.startswith("["):
                note.append(f"*{s}*")                    # ("[From the Loeb translation]")
            continue
        if _latin(s):                                   # (Bohn leaves the coarsest lines in Latin: 1.92)
            if not out or out[-1] != LEFT_IN_LATIN:
                out.append(LEFT_IN_LATIN)
            continue
        out.append(s)
    body = "\n".join(note + out)
    body = re.sub(r"\*\s+([^*\n]+?)\*", r"*\1*", body)          # ("* Anon.* 1695": the italics' stray space)
    body = re.sub(r"(\d+)\*(th [Cc]ent(?:ury)?\.?)\*", r"\1\2", body)   # ("16*th cent.*")
    body = re.sub(r"(?<=[a-z]{3})\d(?=[\s,.;:])", "", body)     # (a note mark the markup didn't raise: "Paccius1")
    return re.sub(r"[*.\s]+$", "", title.replace("*", "")).strip(), body


LEFT_IN_LATIN = "*[The rest is left in Latin in Bohn's translation.]*"
LATIN_WORDS = set("et est in non qui quae quod sed nec neque te tibi me mihi tu ego cum ad ut si sit esse enim olim "
                  "vel aut atque hic haec hoc ille illa nisi quid quam ne iam nam".split())
ENGLISH_WORDS = set("the and of to you your is that it he she his her with for not but as be have".split())


def _latin(s: str) -> bool:
    words = re.findall(r"[a-z]+", s.lower())
    lat = sum(w in LATIN_WORDS for w in words)
    eng = sum(w in ENGLISH_WORDS for w in words)
    return len(words) >= 6 and lat >= 3 and eng <= lat // 4


def martial() -> None:
    books = {}
    for n, count in MARTIAL_COUNTS.items():
        t = _martial_page(n)
        start = re.search(r"(?is)<h3[^>]*>\s*BOOK [IVXL]+\.?\s*</h3>", t)
        expect(start, f"Martial {n}: no BOOK heading")
        parts = re.split(r'<A NAME="C(\d+)"></A>', t[start.end():])
        epigrams = {}
        preface = []
        for m in re.finditer(r"(?is)<p\b([^>]*)>(.*?)</p>", parts[0]):
            s = text(m.group(2))
            if s and "smallish" not in m.group(1) and not s.startswith("BOOK"):
                preface.append(f"*{_title(s.rstrip('.'))}*" if re.search(r"<b>", m.group(2)) else s)
        if preface:
            epigrams["0"] = "\n".join(preface)
        for i in range(1, len(parts), 2):
            title, body = _martial_body(parts[i + 1])
            expect(body, f"Martial {n}.{parts[i]}: no text")
            epigrams[parts[i]] = f"*{_title(title)}*\n{body}" if title else body
        numbers = [int(k) for k in epigrams if k != "0"]
        expect(numbers == list(range(1, count + 1)), f"Martial {n}: epigrams {numbers[:5]}…{numbers[-3:]}")
        books[str(n)] = epigrams
    _put("Martial", books, "Epigrams, Bohn's Classical Library (1897), with Ker (1919-20)")


BUILDS = {"old_age": old_age, "distichs": distichs, "cato": cato, "varro": varro, "seneca_dialogues": seneca_dialogues,
          "benefits": benefits, "natural_questions": natural_questions, "pliny_letters": pliny_letters,
          "satyricon": satyricon, "fasti": fasti, "thebaid": thebaid, "achilleid": achilleid,
          "argonautica": argonautica, "seneca_tragedies": seneca_tragedies, "fabulae": fabulae, "dares": dares,
          "dictys": dictys, "fulgentius": fulgentius, "astronomica": astronomica, "moral_letters": moral_letters,
          "natural_history": natural_history, "historia_augusta": historia_augusta, "stratagems": stratagems,
          "aqueducts": aqueducts, "velleius": velleius, "florus": florus, "juvenal": juvenal, "martial": martial}


def main(names: list) -> None:
    for name in names or BUILDS:
        print(name)
        BUILDS[name]()


if __name__ == "__main__":
    main(sys.argv[1:])
