"""
The Arthurian legend in medieval texts, in English translation -> data/arthurian/*.json (book -> chapter -> verse,
each chapter's first paragraph led by its title in italics):

  from Project Gutenberg
    Malory, Le Morte d'Arthur (Caxton's text, 1485), #1251-1252            chapters "book.chapter" (1.5)
    Chrétien de Troyes, Erec, Cligès, Yvain, Lancelot, tr. W. W. Comfort, #831
    Wolfram von Eschenbach, Parzival, tr. Jessie L. Weston (1894), #47297-47298
    The High History of the Holy Graal (Perlesvaus), tr. Sebastian Evans, #750   chapters "branch.title"
    Bédier, The Romance of Tristan and Iseult, tr. Hilaire Belloc, #14244 (retold from the medieval poems)
    Sir Gawain and the Green Knight, tr. Jessie L. Weston (prose), #66084
    Marie de France, the Lays, tr. Eugene Mason (1911), #11417
    Wace, Roman de Brut (the Arthurian part), tr. Eugene Mason, #10472
    Nennius, History of the Britons, tr. J. A. Giles, #1972
    Geoffrey of Monmouth, History of the Kings of Britain, tr. Thompson rev. Giles, in Old English Chronicles #37848
  from In Parentheses (York University, www.yorku.ca/inpar), transcribed texts as PDF
    Layamon's Brut (the Arthurian portions), tr. Frederic Madden; The Quest of the Holy Grail (the Vulgate Queste),
    tr. W. W. Comfort; Morien, Sir Libeaus Desconus, The Adventures of Arthur at the Tarn Wadeling, tr. Jessie L.
    Weston; Sir Launfal, tr. James Weldon; Tyolet, tr. Ross G. Arthur

(sacred-texts, the first choice, has blocked this machine.) Footnote marks and page numbers are dropped.

    python scripts/build_arthurian.py
"""
import html
import json
import re
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "scripts" / ".cache" / "arthur"
OUT = ROOT / "data" / "arthurian"
UA = {"User-Agent": "ScriptureBot corpus builder (personal Discord bot)"}
ROMAN = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100, "D": 500, "M": 1000}
SMALL = {"a", "an", "and", "the", "of", "to", "in", "on", "at", "by", "for", "with", "or", "his", "her", "who", "which",
         "as", "from", "into", "that", "how"}


def roman(s: str) -> int:
    s = s.upper()
    total = 0
    for a, b in zip(s, s[1:] + " "):
        total += -ROMAN[a] if ROMAN.get(b, 0) > ROMAN[a] else ROMAN[a]
    return total


def gutenberg(n: int) -> str:
    path = CACHE / f"{n}.html"
    if not path.exists():
        CACHE.mkdir(parents=True, exist_ok=True)
        url = f"https://www.gutenberg.org/cache/epub/{n}/pg{n}-images.html"
        path.write_bytes(urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=120).read())
    t = path.read_text(encoding="utf-8")
    return t.split("*** END OF THE PROJECT GUTENBERG")[0]


def clean(s: str) -> str:
    """HTML -> text: page numbers and footnote marks dropped, a verse's line breaks kept."""
    s = re.sub(r'(?is)<span class="(?:pagenum|pb)[^"]*"[^>]*>.*?</span>', "", s)       # (page numbers)
    s = re.sub(r'(?is)<a[^>]*class="[^"]*(?:fnanchor|footnote|noteref)[^"]*"[^>]*>.*?</a>', "", s)
    s = re.sub(r"(?is)<a[^>]*href=\"#(?:fn|note|Footnote|FN|linknote)[^\"]*\"[^>]*>.*?</a>", "", s)
    s = re.sub(r"(?is)<sup>.*?</sup>", "", s)
    s = re.sub(r"\s+", " ", s)
    s = re.sub(r"(?i)<br\s*/?>\s*", "\n", s)
    s = html.unescape(re.sub(r"<[^>]+>", "", s))
    return "\n".join(x.strip() for x in s.split("\n") if x.strip())


def title_case(t: str) -> str:
    t = t.strip().rstrip(".")
    if t.isupper():
        words = t.lower().split(" ")
        t = " ".join(w if i and w in SMALL else w[:1].upper() + w[1:] for i, w in enumerate(words))
    return t


def chapter(title: str, paras: list) -> dict:
    paras = [p for p in paras if p]
    if not paras:
        raise SystemExit(f"no text under {title!r}")
    paras[0] = f"*{title}*\n{paras[0]}" if title else paras[0]
    return {str(i + 1): p for i, p in enumerate(paras)}


def paras_of(html_part: str, skip=()) -> list:
    out = []
    for m in re.finditer(r"(?is)<p(\s[^>]*)?>(.*?)</p>", html_part):      # (not <pre>: notes)
        if any(k in (m.group(1) or "") for k in skip):
            continue
        p = clean(m.group(2))
        if p and not END.match(p):
            out.append(p)
    return out


# what isn't the book: notes and the printer's or the etext's last words
END = re.compile(r"(?i)^(?:printed by|the temple press|end of (?:the )?project gutenberg|\[footnote \d+:)")


def save(name: str, source: str, books: dict) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"{name}.json").write_text(json.dumps({"source": source, "books": books}, ensure_ascii=False, indent=1),
                                      encoding="utf-8")
    for book, chapters in books.items():
        words = sum(len(v.split()) for c in chapters.values() for v in c.values())
        print(f"{book}: {len(chapters)} chapters, {words:,} words -> data/arthurian/{name}.json")


# ── Malory ─────────────────────────────────────────────────────────────────

def malory() -> dict:
    chapters = {}
    for n in (1251, 1252):
        t = gutenberg(n)
        t = t[:t.rfind(">GLOSSARY<")]                    # (the glossary at the end; the contents name it too)
        marks = [(m.start(), m.end(), "book", roman(m.group(1)), "")
                 for m in re.finditer(r"(?is)<h2[^>]*>\s*(?:<a[^>]*></a>)?\s*BOOK ([IVXLC]+)\.?\s*</h2>", t)]
        marks += [(m.start(), m.end(), "chapter", roman(m.group(1)), clean(m.group(2)))
                  for m in re.finditer(r"(?is)<h3[^>]*>\s*(?:<a[^>]*></a>)?\s*CHAPTER ([IVXLC]+)\.?\s*(?:<br\s*/?>)?(.*?)</h3>", t)]
        marks.sort()
        book, k = None, 0
        for i, (start, end, kind, num, title) in enumerate(marks):
            if kind == "book":
                book, k = num, 0
                continue
            # a book's chapters run in order: taken by place (the etext misprints Book XII's VIII as "LV."; Book
            # III's "CHAPTER VII" lacks its stop), the printed number noted where it differs
            k += 1
            if num != k:
                print(f"Malory: Book {book}, chapter {k} is headed {num}")
            stop = marks[i + 1][0] if i + 1 < len(marks) else len(t)
            body = re.split(r"(?is)<h[1-5][^>]*>", t[end:stop])[0]
            chapters[f"{book}.{k}"] = chapter(title.replace("\n", " "), paras_of(body))
    if len(chapters) < 450:
        raise SystemExit(f"Malory: only {len(chapters)} chapters")
    return {"Le Morte d'Arthur": chapters}


# ── Bédier's Tristan ───────────────────────────────────────────────────────

def tristan() -> dict:
    t = gutenberg(14244)
    heads = list(re.finditer(r"(?is)<h2[^>]*>(.*?)</h2>", t))
    out, n = {}, 0
    for h, nxt in zip(heads, heads[1:] + [None]):
        name = clean(h.group(1))
        if not name.isupper() or name.startswith("PART ") or "Bédier" in name or "ROMAN" in name:
            continue
        body = t[h.end():nxt.start() if nxt else len(t)]
        paras = paras_of(body, skip=("toc",))
        if paras:
            n += 1
            out[str(n)] = chapter(title_case(name), paras)
    return {"Tristan and Iseult": out}


# ── Marie de France ────────────────────────────────────────────────────────

def marie() -> dict:
    t = gutenberg(11417)
    heads = list(re.finditer(r"(?is)<h2[^>]*>\s*(?:<a[^>]*></a>)?\s*([IVXL]+)\.?\s*</h2>", t))
    out = {}
    for h, nxt in zip(heads, heads[1:] + [None]):
        body = t[h.end():nxt.start() if nxt else len(t)]
        # the lay's title is the first line set apart (h3 or a centred paragraph) after its number
        title_m = re.search(r"(?is)<h3[^>]*>(.*?)</h3>", body[:600])
        title = title_case(clean(title_m.group(1))) if title_m else ""
        paras = paras_of(body[title_m.end():] if title_m else body)
        if not title and paras and len(paras[0]) < 60:
            title, paras = title_case(paras[0]), paras[1:]
        out[str(roman(h.group(1)))] = chapter(title, paras)
    return {"Lays of Marie de France": out}


# ── Nennius ────────────────────────────────────────────────────────────────

def nennius() -> dict:
    t = gutenberg(1972)
    heads = list(re.finditer(r"(?is)<h2[^>]*>(.*?)</h2>", t))
    out, n = {}, 0
    for h, nxt in zip(heads, heads[1:] + [None]):
        name = clean(h.group(1))
        if name.lower().startswith(("the project", "by nennius", "contents", "history of the britons")):
            continue
        body = t[h.end():nxt.start() if nxt else len(t)]
        paras = [re.sub(r"(?<=[A-Za-z.,;])\s?(?:\(\d+\)|\*)", "", p) for p in paras_of(body, skip=("toc",))]
        if paras:                                       # (Giles's note marks: "Columeille(1)", "Elbotus,*")
            n += 1
            out[str(n)] = chapter(title_case(re.sub(r"^[IVX]+\.\s*", "", name).rstrip("*")), paras)
    return {"Nennius, History of the Britons": out}


# ── The High History of the Holy Graal ─────────────────────────────────────

def high_history() -> dict:
    t = gutenberg(750)
    t = t[re.search(r"(?s)THE HIGH HISTORY OF THE HOLY GRAAL\s*</h1>", t).start():]
    marks = list(re.finditer(r"(?is)<h3[^>]*>(.*?)</h3>", t))
    out, branch, title_n = {}, 0, 0
    for h, nxt in zip(marks, marks[1:] + [None]):
        name = clean(h.group(1))
        b = re.match(r"BRANCH ([IVXLC]+)\.?", name)
        if b:
            branch, title_n = roman(b.group(1)), 0
            continue
        body = t[h.end():nxt.start() if nxt else len(t)]
        paras = paras_of(body, skip=("endnote",))
        if not paras:
            continue
        m = re.match(r"(?:TITLE )?([IVXLC]+)\.$", name)
        title_n = roman(m.group(1)) if m else title_n + 1
        label = "" if m else title_case(name)
        out[f"{branch}.{title_n}"] = chapter(label, paras)
    return {"The High History of the Holy Graal": out}


# ── Chrétien de Troyes ─────────────────────────────────────────────────────

CHRETIEN = [("EREC ET ENIDE", "Erec and Enide"), ("CLIG", "Cligès"), ("YVAIN", "Yvain, the Knight with the Lion"),
            ("LANCELOT", "Lancelot, the Knight of the Cart")]


def chretien() -> dict:
    """Comfort's prose, in his sections ("(Vv. 1-26.)": the lines of the poem each renders), a chapter each."""
    t = gutenberg(831)
    heads = [(m.start(), m.end(), clean(m.group(1))) for m in re.finditer(r"(?is)<h2[^>]*>(.*?)</h2>", t)]
    starts = []
    for key, name in CHRETIEN:
        found = [h for h in heads if h[2].upper().startswith(key)]
        starts.append((found[-1], name))                    # (the last: the first is in the contents)
    books = {}
    for i, ((s, e, _), name) in enumerate(starts):
        stop = starts[i + 1][0][0] if i + 1 < len(starts) else len(t)
        body = t[e:stop]
        body = re.split(r'(?is)<p class="foot">|<h2[^>]*>\s*(?:End|Footnotes|Notes)|——\s*Endnotes', body)[0]
        sections, current = [], []
        for p in paras_of(body, skip=("toc", "foot")):
            m = re.match(r"\(Vv\.\s*([\d\-–]+)\.?\)\s*", p)
            if m:
                if current:
                    sections.append(current)
                current = [p[m.end():]]
            elif current:
                current.append(p)
        if current:
            sections.append(current)
        books[name] = {str(k + 1): chapter("", s) for k, s in enumerate(sections)}
    return books


# ── Parzival ───────────────────────────────────────────────────────────────

def parzival() -> dict:
    """Weston's verse, a chapter a book (I-XVI), a verse a stanza; her argument heading each book is left out."""
    out = {}
    for n in (47297, 47298):
        t = gutenberg(n)
        heads = list(re.finditer(r"(?is)<h2[^>]*>\s*BOOK ([IVXL]+)\s*(?:<br\s*/?>)?\s*(.*?)</h2>", t))
        for h, nxt in zip(heads, heads[1:] + [None]):
            body = t[h.end():nxt.start() if nxt else len(t)]
            body = re.split(r"(?is)<h2[^>]*>", body)[0]
            body = re.sub(r'(?is)<span class="linenum">.*?</span>', "", body)
            stanzas = [clean(s) for s in re.findall(r'(?is)<div class="stanza">(.*?)</div>', body)]
            stanzas = [s for s in stanzas if s]
            if stanzas:
                out[str(roman(h.group(1)))] = chapter(f"Book {h.group(1)}: {title_case(clean(h.group(2)))}", stanzas)
    return {"Parzival": dict(sorted(out.items(), key=lambda kv: int(kv[0])))}


# ── Sir Gawain and the Green Knight ────────────────────────────────────────

def gawain() -> dict:
    """Weston's prose, a chapter a section (her headings), through the poem's four parts."""
    t = gutenberg(66084)
    t = t[:t.rfind(">Notes<")] if ">Notes<" in t else t
    marks = list(re.finditer(r"(?is)<h([23])[^>]*>(.*?)</h\1>", t))
    out, part = {}, 0
    for h, nxt in zip(marks, marks[1:] + [None]):
        name = clean(h.group(2))
        if h.group(1) == "2":
            if re.fullmatch(r"[IV]+", name):
                part = roman(name)
            continue
        if not part:
            continue
        body = t[h.end():nxt.start() if nxt else len(t)]
        paras = paras_of(body)
        if paras:
            out[str(len(out) + 1)] = chapter(f"{name} ({['I', 'II', 'III', 'IV'][part - 1]})", paras)
    return {"Sir Gawain and the Green Knight": out}


# ── Wace ───────────────────────────────────────────────────────────────────

def wace() -> dict:
    """The Arthurian part of the Roman de Brut, Mason's prose: one run of paragraphs, so one chapter."""
    t = gutenberg(10472)
    i = [m.end() for m in re.finditer(r"(?is)WACE'S ROMAN DE BRUT\s*</h2>", t)][-1]
    paras = [re.sub(r"\s?\[\d+\]", "", p) for p in paras_of(t[i:])]               # (note marks)
    return {"Wace, Roman de Brut": {"1": chapter("Roman de Brut (the Arthurian portion)", paras)}}


# ── Geoffrey of Monmouth ───────────────────────────────────────────────────

def geoffrey() -> dict:
    """The History of the Kings of Britain (Thompson's translation, revised by Giles), from Old English Chronicles:
    chapters "book.chapter"; Giles's footnotes left out."""
    t = gutenberg(37848)
    starts = [m.end() for m in re.finditer(r"(?is)BRITISH HISTORY\.\s*</h2>", t)]
    end = [m.start() for m in re.finditer(r"(?is)<h2[^>]*>\s*WORKS OF GILDAS", t)]
    t = t[starts[-1]:end[0]]
    t = re.sub(r'(?is)<div class="footnote">.*?</div>', "", t)
    marks = list(re.finditer(r"(?is)<h3[^>]*>(.*?)</h3>", t))
    out, book = {}, 0
    for h, nxt in zip(marks, marks[1:] + [None]):
        name = clean(h.group(1))
        b = re.match(r"BOOK ([IVXL]+)\.?$", name)
        if b:
            book = roman(b.group(1))
            continue
        c = re.match(r"Chap\.\s*([IVXL]+)\.\s*[—-]\s*(.*)", name)
        if not c or not book:
            continue
        body = t[h.end():nxt.start() if nxt else len(t)]
        out[f"{book}.{roman(c.group(1))}"] = chapter(c.group(2).strip().rstrip("."), paras_of(body))
    return {"Geoffrey of Monmouth, History of the Kings of Britain": out}


# ── In Parentheses (York University) PDFs ──────────────────────────────────
INPAR = "https://www.yorku.ca/inpar/"
SKIP_SECTIONS = {"introduction", "preface", "notes", "bibliography", "endnotes", "appendix"}
# {(file, page, the line's first words): its drop capital, an image, read on the page}: see inpar()
DROP_CAPS = {("launfal_weldon.pdf", 1, "n the days"): "I", ("morien-weston.pdf", 6, "erein doth the"): "H"}


def macroman(s: str) -> str:
    """The PDFs' text is Mac Roman read as Windows-1252 ("ChrŽtien", "ÒquotedÓ"): read it as Mac Roman."""
    out = []
    for ch in s:
        if ord(ch) >= 0x80:
            try:
                ch = ch.encode("cp1252").decode("mac_roman")
            except UnicodeError:
                pass
        out.append(ch)
    return "".join(out)


def inpar(name: str, verse: bool = False) -> list:
    """[(section heading or "", [paragraphs])] of an In Parentheses PDF: its title page, running titles, page
    numbers and note marks (smaller digits) dropped, and its introduction, preface and notes left out. A paragraph
    begins at an indent (or, for verse, a stanza after a gap); a drop capital is an image, so the letter is supplied
    from DROP_CAPS, read on the page."""
    import fitz
    path = CACHE / name
    if not path.exists():
        CACHE.mkdir(parents=True, exist_ok=True)
        path.write_bytes(urllib.request.urlopen(urllib.request.Request(INPAR + name, headers=UA), timeout=120).read())
    doc = fitz.open(path)
    lines = []                                          # (page, x, y, size, text)
    for pno, page in enumerate(doc):
        if pno == 0:
            continue                                    # (the title page)
        for b in page.get_text("dict")["blocks"]:
            for l in b.get("lines", []):
                spans = [s for s in l["spans"] if s["text"]]
                body = [s for s in spans if not (s["size"] < 13 and s["text"].strip().isdigit())]   # (note marks)
                text = macroman("".join(s["text"] for s in body)).replace(" ", " ").rstrip()
                if not text.strip():
                    continue
                size = max(round(s["size"]) for s in spans)
                lines.append((pno, l["bbox"][0], l["bbox"][1], size, text))
    # the running title: the line most often at the top of a page
    tops = {}
    for pno, x, y, size, text in lines:
        if y < 85:
            tops[text.strip()] = tops.get(text.strip(), 0) + 1
    running = {t for t, n in tops.items() if n >= 3}
    sections, heading, paras, para, last = [], "", [], [], None
    skipping = False

    def flush_para():
        nonlocal para
        if para:
            paras.append(re.sub(r"[ \t]{2,}", " ", ("\n" if verse else " ").join(para)).strip())
            para = []

    def flush_section():
        nonlocal paras
        flush_para()
        if paras and not skipping:
            sections.append((heading, paras))
        paras = []

    first_on_page = {}
    for pno, x, y, size, text in lines:
        if not ((y < 85 and text.strip() in running) or (text.strip().isdigit() and y > 640)):
            first_on_page.setdefault(pno, y)
    for pno, x, y, size, text in lines:
        t = text.strip()
        if (y < 85 and t in running) or (t.isdigit() and y > 640):
            continue
        named = len(t) < 30 and t.lower().rstrip(".") in SKIP_SECTIONS
        is_heading = size >= 17 or (named and (x > 200 or y == first_on_page.get(pno)))   # ("Notes", "Preface")
        # a section can begin with no heading, lower down a fresh page (Libeaus's tale, after its introduction)
        drop_cap = x >= 125 and t[:1].islower() and not verse
        if not is_heading and y == first_on_page.get(pno) and (y > 140 or drop_cap) \
                and (last is None or last[0] != pno):
            flush_section()
            heading, skipping, last = "", False, None
        if is_heading:
            flush_section()
            heading = t
            skipping = t.lower().rstrip(".") in SKIP_SECTIONS
            last = None
            continue
        gap = last is not None and last[0] == pno and y - last[1] > 26
        indent = 88 < x < 125
        if verse:
            if gap or (last is not None and last[0] != pno and False):
                flush_para()
        elif indent or gap or x >= 125 and not para:
            flush_para()
        if x >= 125 and not verse and not para and t[:1].islower():
            key = (name, pno, " ".join(t.split()[:3]))
            if key not in DROP_CAPS:
                MISSING_CAPS.append(key)
            t = DROP_CAPS.get(key, "") + t
        # a word broken across lines: joined where the break was the line's own ("medi-\neval")
        if para and not verse and para[-1].endswith("-") and t[:1].islower() and not para[-1].endswith("--"):
            para[-1] = para[-1][:-1] + t
        else:
            para.append(t)
        last = (pno, y)
    flush_section()
    return sections


MISSING_CAPS = []


def inpar_book(name: str, title: str, verse: bool = False, by_heading: bool = False) -> dict:
    sections = inpar(name, verse)
    if by_heading:                                       # (the Queste's chapters)
        return {str(i + 1): chapter(h, p) for i, (h, p) in enumerate(sections)}
    paras = [re.sub(r"^\(\d+\)\s*", "", p) for _, ps in sections for p in ps]   # (Tyolet's "(25)": its lines)
    paras = [p for p in paras if not p.startswith("In Parentheses Publications")]
    return {"1": chapter(title, paras)}


def main():
    save("malory", "Caxton's text (1485)", malory())
    save("tristan_bedier", "Joseph Bédier, tr. Hilaire Belloc (1913)", tristan())
    save("marie_de_france", "trans. Eugene Mason (1911)", marie())
    save("nennius", "trans. J. A. Giles", nennius())
    save("high_history", "trans. Sebastian Evans (1898)", high_history())
    save("chretien", "trans. W. W. Comfort (1914)", chretien())
    save("parzival", "trans. Jessie L. Weston (1894)", parzival())
    save("gawain", "trans. Jessie L. Weston (1898)", gawain())
    save("wace", "trans. Eugene Mason (1912)", wace())
    save("geoffrey", "trans. Aaron Thompson, rev. J. A. Giles", geoffrey())
    save("layamon", "trans. Sir Frederic Madden (In Parentheses)",
         {"Layamon's Brut": inpar_book("layamon_madden.pdf", "The Brut (the Arthurian portions)")})
    save("queste", "trans. W. W. Comfort (In Parentheses)",
         {"The Quest of the Holy Grail": inpar_book("quest_comfort.pdf", "", by_heading=True)})
    save("morien", "trans. Jessie L. Weston (In Parentheses)", {"Morien": inpar_book("morien-weston.pdf", "Morien")})
    save("libeaus", "trans. Jessie L. Weston (In Parentheses)",
         {"Sir Libeaus Desconus": inpar_book("libeaus_weston.pdf", "Sir Libeaus Desconus")})
    save("launfal", "trans. James Weldon (In Parentheses)",
         {"Sir Launfal": inpar_book("launfal_weldon.pdf", "Sir Launfal")})
    save("tarn_wadeling", "trans. Jessie L. Weston (In Parentheses)",
         {"The Adventures of Arthur at the Tarn Wadeling":
          inpar_book("tarn_wadeling_weston.pdf", "The Adventures of Arthur at the Tarn Wadeling", verse=True)})
    save("tyolet", "trans. Ross G. Arthur (In Parentheses)", {"Tyolet": inpar_book("tyolet_arthur.pdf", "Tyolet")})
    if MISSING_CAPS:
        print("drop capitals to read on the page:", MISSING_CAPS)


if __name__ == "__main__":
    sys.exit(main())
