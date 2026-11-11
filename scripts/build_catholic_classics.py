"""
The medieval and Catholic Reformation classics the library lacked (2026-11-10), each from a real text, not a scan:

  data/medieval/medieval_writers.json
    Anselm: Proslogium, Monologium, Gaunilo's In Behalf of the Fool and Anselm's answer, Cur Deus Homo (trans. S. N.
      Deane, 1903; sacred-texts chr/ans)
    Francis of Assisi: his Writings (trans. Paschal Robinson, 1906; chr/wosf), only Francis's own words -- each
      piece's text begins at its own heading, after Robinson's introduction, which is left out
    The Little Flowers of St. Francis, with the Considerations on the Holy Stigmata, the Life of Friar Juniper and
      the Sayings of Friar Giles (trans. T. W. Arnold, 1898; chr/lff)
    Bernard of Clairvaux, On Loving God; Bonaventure, The Mind's Road to God; Meister Eckhart's Sermons (trans. Claud
      Field); The Dialogue of Catherine of Siena (trans. Algar Thorold) -- from CCEL's ThML editions
  data/reformation/catholic_reformation.json
    The Canons and Decrees of the Council of Trent (trans. J. Waterworth, 1848; history.hanover.edu)
    Ignatius of Loyola, The Spiritual Exercises (trans. Elder Mullan, 1914; chr/seil)
    Teresa of Ávila, The Interior Castle (sacred-texts chr/tic) and her Life (CCEL)
    John of the Cross, Ascent of Mount Carmel, Dark Night of the Soul, Spiritual Canticle (trans. David Lewis; CCEL)
    Francis de Sales, Introduction to the Devout Life; Pascal, Pensées (trans. W. F. Trotter) -- CCEL

Chapters are the works' own (Book.Chapter where a work has books: "Ascent of Mount Carmel 2.5"; Teresa's Castle by
Mansion: "Interior Castle 6.4"; Pascal by his numbered thoughts, as cited: "Pensées 233"). A verse is a paragraph,
or a run of whole sentences of a long one; a paragraph a page break cut in two is joined again. Chapter titles lead
verse 1 in italics. Left out: translators' introductions, prefaces and notes, footnotes, indexes, page numbers.

    python scripts/build_catholic_classics.py
"""
import html
import json
import re
import sys
import time
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_budge import blocks, groups, text_of as st_text   # noqa: E402  (sacred-texts pages)
from build_pseudepigrapha import expect, roman                # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
CACHE = Path(__file__).resolve().parent / ".cache"
UA = {"User-Agent": "ScriptureBot corpus builder (a personal Discord bot)"}
OUT_MEDIEVAL = ROOT / "data" / "medieval" / "medieval_writers.json"
OUT_REFORMATION = ROOT / "data" / "reformation" / "catholic_reformation.json"
END = r"[.!?:;'’”\"\])…*]\s*$"


def fetch(url: str, path: Path) -> bytes:
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=120).read())
        time.sleep(1)
    return path.read_bytes()


def tidy(text: str) -> str:
    text = re.sub(r"\s*\u2011\u2011\s*", "\u2014", text)              # (Deane's dashes)
    text = re.sub(r"[ \t\r\f\v]+", " ", text.replace("\xa0", " ").replace("\xad", ""))
    text = re.sub(r" *\n *", "\n", text).strip()
    return re.sub(r"(?<=\w)\s+(?=[,;:!?]|\.(?!\s*\.))", "", text)


def joined(paras: list) -> list:
    """Paragraphs a page break cut in two put back together (one ends without closing punctuation, or the next
    is marked "[paragraph continues]")."""
    out = []
    for p in paras:
        cont = p.startswith("[paragraph continues]")
        p = re.sub(r"^\[paragraph continues\]\s*", "", p)
        if out and (cont or not re.search(END, out[-1])) and not p.startswith("*"):
            out[-1] = f"{out[-1]} {p}"
        else:
            out.append(p)
    return out


COLOPHON = r"(?i)here endeth|printed by|the end\.?$|.*translated and printed by"
NAMES = {"god", "lord", "christ", "ghost", "spirit", "virgin", "mary", "francis", "st", "saint", "teresa", "jesus",
         "clare", "friar", "giles", "leo", "church", "trinity", "i", "ii", "iii", "iv", "v", "vi", "vii", "viii",
         "ix", "x", "xi", "xii", "xiii", "xiv", "xv", "lateran", "pius", "paul", "julius", "peter", "trent", "rome", "roman", "apostolic", "see"}


def sentence_case(text: str) -> str:
    """ "TREATS OF SEVERAL WAYS WHEREBY OUR LORD..." -> "Treats of several ways whereby our Lord..." """
    if not text.isupper():
        return text
    words = re.split(r"(\W+)", text.lower())
    words = [(w.upper() if re.fullmatch(r"[ivx]+", w) and w != "i" or w == "i" else w.capitalize())
             if w in NAMES else w for w in words]
    text = re.sub(r"\bholy (?=Ghost|Spirit|Church|See|Trinity)", "Holy ", "".join(words))
    return re.sub(r"(^|[.!?]\s+)([a-z])", lambda m: m.group(1) + m.group(2).upper(), text)


def chapter(paras: list, lead: str = "") -> dict:
    """A chapter's verses: its paragraphs (long ones as runs of whole sentences), the lead in italics on the first;
    a heading on a line of its own leads the paragraph after it; headings in capitals put in sentence case; the
    chapter's title again, a title in capitals at its head, and printers' colophons left out."""
    lead = sentence_case(re.sub(r"\s*\u2011\u2011\s*", "\u2014", lead).strip())
    paras = [re.sub(r"\s*\u2011\u2011\s*", "\u2014", p).strip() for p in paras                  # (Deane's dashes)
             if p.strip() and not re.match(COLOPHON, p.strip("* "))]
    while paras and re.sub(r"\W", "", paras[0]).isupper() and len(paras[0]) < 80 and "\n" not in paras[0]:
        paras = paras[1:]                                      # ("APPENDIX.", "HERE BEGIN THE CHAPTERS")
    if paras and lead and re.sub(r"\W", "", paras[0]).lower() == re.sub(r"\W", "", lead).lower():
        paras = paras[1:]
    paras = [re.sub(r"(?m)^\*([^*\n]+)\*$", lambda m: f"*{sentence_case(m.group(1))}*", p) for p in paras]
    merged = []
    for p in paras:
        if merged and re.fullmatch(r"(\*[^*\n]+\*\n?)+", merged[-1] + "\n"):
            merged[-1] = f"{merged[-1]}\n{p}"                   # (a heading alone: with what it heads)
        else:
            merged.append(p)
    verses = []
    for p in joined(merged):
        head = re.match(r"((?:\*[^*\n]+\*\n)+)(?=[^\n]+$)", p)          # (a heading over a paragraph of prose)
        if head:
            runs = groups(p[head.end():])
            verses += [head.group(1) + runs[0]] + runs[1:]
        else:
            verses += groups(p) if "\n" not in p else [p]
    expect(verses, f"an empty chapter ({lead[:40]!r})")
    if lead:
        verses[0] = f"*{lead}*\n{verses[0]}"
    return {str(n): v for n, v in enumerate(verses, start=1)}


# ── CCEL ThML ──────────────────────────────────────────────────────────────────────────────────────────────────
def thml(path: str) -> ET.Element:
    raw = fetch(f"https://ccel.org/ccel/{path}.xml", CACHE / "ccel" / (path.replace("/", "_") + ".xml"))
    return ET.fromstring(raw)


def ptext(el) -> str:
    """An element's text without its footnotes (<note>); a ThML <verse>'s lines (<l>) on lines of their own."""
    if el.tag == "note":
        return ""
    parts = [el.text or ""]
    for ch in el:
        if ch.tag == "l":
            parts.append("\x00" + ptext(ch))
        elif ch.tag == "br":
            parts.append("\x00")
        else:
            parts.append(ptext(ch))
        parts.append(ch.tail or "")
    return "".join(parts)


def div_paras(div) -> list:
    """The paragraphs of a division, not of the divisions inside it; verse (<verse>, <l>) by its lines."""
    out = []
    for ch in div:
        if re.fullmatch(r"div\d|h\d|note", ch.tag):
            continue
        if ch.tag == "p":
            if ch.get("class") in ("footnote", "bbook", "bref"):
                continue
            out.append(ccel(ptext(ch)))
        else:                                         # (<verse>, <blockquote>, <table>...: their text, line by line)
            text = "\n".join(t for t in (ccel(ptext(p)) for p in ch.iter() if p.tag in ("p", "l")) if t)
            out.append(text or ccel(ptext(ch)))
    return [p for p in out if p]


def ccel(text: str) -> str:
    """The XML's line wrapping undone; only its real line breaks (a poem's lines) kept."""
    text = re.sub(r"\s*\[\d+\]", "", text)                    # (a footnote's mark, "[8]": the note itself is left out)
    return tidy(re.sub(r"\s+", " ", text).replace("\x00", "\n"))


def divs(el, level: str) -> list:
    return [d for d in el.iter(level)]


def title_of(div) -> str:
    return tidy(html.unescape(div.get("title") or "")).lstrip("> ")


def after_label(title: str) -> str:
    """ "Chapter IV. Of those who find comfort..." -> "Of those who find comfort..." """
    return re.sub(r"^\s*(?:chapter|stanza|book)\s+[\w]+\.?\s*", "", title, flags=re.I).strip()


def heads(div) -> list:
    return [ccel(ptext(h)) for h in div if re.fullmatch(r"h\d", h.tag)]


def bernard() -> dict:
    root, book = thml("b/bernard/loving_god"), {}
    for d in divs(root, "div1"):
        t = title_of(d)
        m = re.match(r"chapter ([IVXL]+)\.\s*(.*)", t, re.I)
        if t.upper().startswith("DEDICATION"):
            book["0"] = chapter(div_paras(d), "Dedication")
        elif m:
            book[str(roman(m.group(1).upper()))] = chapter(div_paras(d), m.group(2))
    expect(list(book) == [str(n) for n in range(0, 16)], f"Bernard {list(book)}")
    return book


def bonaventure() -> dict:
    root, book = thml("b/bonaventure/mindsroad"), {}
    numbers = ["one", "two", "three", "four", "five", "six", "seven"]
    for d in divs(root, "div1"):
        t = title_of(d).lower()
        if t == "prologue":
            book["0"] = chapter(div_paras(d), "Prologue")
        elif t.startswith("chapter ") and t.split()[1] in numbers:
            h, paras = [], div_paras(d)                   # (its title is its first paragraph, in capitals)
            caps = re.match(r"([A-Z][A-Z ,;'-]+?)\s+(1\.\s.*)", paras[0], re.S)   # (the title run on: "OF THE REFLECTION... 1. But")
            if caps and not h:
                h, paras = [caps.group(1)], [caps.group(2)] + paras[1:]
                if paras[0].strip() == "1.":                       # (its number apart from its text)
                    paras = [f"1. {paras[1]}"] + paras[2:]
            elif not h and paras[0].isupper():
                h, paras = [paras[0].rstrip(" 1.")], paras[1:]
            book[str(numbers.index(t.split()[1]) + 1)] = chapter(paras, h[0] if h else "")
    expect(list(book) == [str(n) for n in range(0, 8)], f"Bonaventure {list(book)}")
    return book


def eckhart() -> dict:
    root, book = thml("e/eckhart/sermons"), {}
    for d in divs(root, "div1"):
        h = heads(d)
        numeral = next((x for x in h if re.fullmatch(r"[IVX]+", x)), None)
        if numeral:
            name = h[h.index(numeral) + 1] if h.index(numeral) + 1 < len(h) else ""
            name = re.sub(r"\s{2,}", ". ", name).title().replace("’S", "’s")
            book[str(roman(numeral))] = chapter(div_paras(d), name)
    expect(list(book) == [str(n) for n in range(1, 8)], f"Eckhart {list(book)}")
    return book


def catherine() -> dict:
    root, book, n = thml("c/catherine/dialog"), {}, 0
    dialogue = next(d for d in divs(root, "div1") if title_of(d).upper().startswith("THE DIALOGUE OF ST. CATHERINE"))
    for treatise in divs(dialogue, "div2"):
        if title_of(treatise).upper().startswith("INTRODUCTION"):   # (Thorold's)
            continue
        first = True
        for d in divs(treatise, "div3"):
            t = title_of(d)
            if t.startswith("Letter of Ser Barduccio"):            # (an account of her death by another hand)
                continue
            n += 1
            lead = (f"{title_of(treatise).title()}*\n*" if first else "") + t
            book[str(n)] = chapter(div_paras(d), lead)
            first = False
    expect(len(book) >= 90, f"Catherine: {len(book)} chapters")
    return book


def books_and_chapters(path: str, book_level: str, chapter_level: str, front: list) -> dict:
    """A work in Books of Chapters ("Book The First" > "Chapter I."): chapters "1.1"...; the divisions named in
    `front` (its own prologue, argument, stanzas) together make chapter "0"."""
    root, book, zero = thml(path), {}, []
    for d in root.iter():
        if d.tag == book_level and any(title_of(d).lower().startswith(f.lower()) for f in front):
            parts = [d] + [x for x in d if re.fullmatch(r"div\d", x.tag)]
            for part in parts:
                paras = div_paras(part)
                if paras:
                    zero += [f"*{title_of(part).rstrip('.')}*"] + paras
    if zero:
        book["0"] = chapter(zero)
    numbers = {"first": 1, "second": 2, "third": 3}
    for b in divs(root, book_level):
        m = re.match(r"book the (first|second|third)", title_of(b), re.I)
        if not m:
            continue
        bn, cn = numbers[m.group(1).lower()], 0
        for d in divs(b, chapter_level):
            t = title_of(d)
            cm = re.match(r"chapter ([IVXL]+)\.?\s*(.*)", t, re.I)
            if cm:
                cn = roman(cm.group(1).upper())
                book[f"{bn}.{cn}"] = chapter(div_paras(d), cm.group(2).strip())
    return book


def ascent() -> dict:
    book = books_and_chapters("j/john_cross/ascent", "div1", "div2", ["Ascent of Mount Carmel"])
    expect({"0", "1.1", "2.32", "3.45"} <= set(book), f"Ascent {list(book)[:3]}...{list(book)[-3:]}")
    return book


def dark_night() -> dict:
    root, book = thml("j/john_cross/dark_night"), {}
    for d in divs(root, "div1"):
        if title_of(d).lower().startswith("prologue"):
            book["0"] = chapter(div_paras(d), "Prologue")
    rest = books_and_chapters("j/john_cross/dark_night", "div1", "div2", [])
    book.update(rest)
    expect({"0", "1.1", "1.14", "2.25"} <= set(book), f"Dark Night {list(book)[:3]}...{list(book)[-3:]}")
    return book


def canticle() -> dict:
    root, book, zero = thml("j/john_cross/canticle"), {}, []
    for d in divs(root, "div1"):
        t = title_of(d)
        m = re.match(r"stanza ([IVXL]+)(?:, ([IVXL]+))?\.?", t, re.I)
        if t.lower() in ("prologue", "song of the soul and the bridegroom", "argument"):
            zero += [f"*{t.rstrip('.')}*"] + div_paras(d)
        elif m:
            # Lewis explains stanzas 14 and 15 together (finishing 15 on its own) and 20 and 21 together
            lead = f"Stanzas {m.group(1)} and {m.group(2)}" if m.group(2) else f"Stanza {m.group(1)}"
            book[str(roman(m.group(1).upper()))] = chapter(div_paras(d), lead)
    book = {"0": chapter(zero), **book}
    expect(list(book) == [str(n) for n in range(0, 41) if n != 21], f"Canticle {list(book)}")
    return book


def teresa_life() -> dict:
    root, book = thml("t/teresa/life"), {}
    life = next(d for d in divs(root, "div1") if title_of(d) == "The Life")
    for d in divs(life, "div2"):
        t = title_of(d)
        m = re.match(r"chapter ([IVXL]+)", t, re.I)
        if t.lower() == "prologue":
            book["0"] = chapter(div_paras(d), "Prologue")
        elif m:
            h, paras = [x for x in heads(d) if x and not re.match(r"chapter ", x, re.I)], div_paras(d)
            if not h and len(paras[0]) < 300 and not re.match(r"\d", paras[0]):     # (its summary)
                h, paras = [paras[0]], paras[1:]
            book[str(roman(m.group(1).upper()))] = chapter(paras, h[0] if h else "")
    expect(list(book) == [str(n) for n in range(0, 41)], f"Teresa's Life {list(book)[-3:]}")
    return book


def devout_life() -> dict:
    root, book = thml("d/desales/devout_life"), {}
    for d in divs(root, "div2"):
        if title_of(d).lower().startswith("preface by the author"):
            book["0"] = chapter(div_paras(d), "Preface by the Author")
    for part in divs(root, "div1"):
        m = re.match(r"PART ([IVX]+)\.\s*(.*)", title_of(part))
        if not m:
            continue
        pn, first = roman(m.group(1)), True
        for d in divs(part, "div2"):
            cm = re.match(r"chapter ([IVXL]+)\.?\s*(.*)", title_of(d), re.I)
            if cm:
                lead = (f"Part {m.group(1)}. {m.group(2).capitalize()}*\n*" if first else "") + cm.group(2).strip()
                book[f"{pn}.{roman(cm.group(1).upper())}"] = chapter(div_paras(d), lead)
                first = False
    expect({"0", "1.1", "5.18"} <= set(book), f"de Sales {list(book)[-3:]}")
    return book


def pensees() -> dict:
    """Pascal's thoughts by their numbers (Brunschvicg's, as cited: Pensées 233 is the wager), in one chapter;
    the paragraphs after a numbered one go with it; each section's title leads its first thought."""
    root, verses, current = thml("p/pascal/pensees"), {}, None
    for d in divs(root, "div1"):
        sm = re.match(r"SECTION ([IVX]+):\s*(.*)", title_of(d))
        if not sm:
            continue
        lead = f"Section {sm.group(1)}. {sm.group(2).strip().capitalize()}"
        for p in div_paras(d):
            m = re.match(r"(\d{1,3})\.(\.\.\.)?\s+(.*)", p, re.S)    # ("488.... But": a fragment's opening lost)
            if m and 0 < int(m.group(1)) - int(current or 0) <= 3:      # (not a figure in the text)
                current = m.group(1)
                verses[current] = (f"*{lead}*\n" if lead else "") + ("… " if m.group(2) else "") + m.group(3)
                lead = ""
            elif current:
                verses[current] += "\n\n" + p
    expect(len(verses) >= 900 and "233" in verses, f"Pensées: {len(verses)} thoughts")
    out = {}
    for k, v in verses.items():                     # (a thought a chapter: Pensées 233 is the wager, whole)
        lead = re.match(r"\*(.*?)\*\n", v)
        paras = (v[lead.end():] if lead else v).split("\n\n")
        out[k] = chapter(paras, lead.group(1) if lead else "")
    return out


# ── sacred-texts ───────────────────────────────────────────────────────────────────────────────────────────────
def st(work: str, page: str) -> str:
    """A sacred-texts page, a paragraph begun after each heading (some pages run the text on straight after one,
    which would otherwise be read as part of it), and its small headings (<h5>) as italic lines."""
    page = fetch(f"https://archive.sacred-texts.com/chr/{work}/{page}",
                 CACHE / "st_classics" / f"{work}_{page}").decode("utf-8", errors="strict")
    page = re.sub(r'(?is)(?:&nbsp;)?<a href="[^"]*#fn_\d+"[^>]*>.*?</a>', "", page)      # (footnote markers)
    page = re.sub(r"(?is)<h5[^>]*>(.*?)</h5>", r"<p>*\1*</p><p>", page)
    page = re.sub(r"(?i)</?div\b[^>]*>", "", page)                 # (an indented poem is a <div> in a <p>)
    page = re.sub(r"(?i)<br\s*/?>", "\ue000", page)                    # (its lines: kept, see st_paras)
    return re.sub(r"(?i)</h[1-4]>", r"\g<0><p>", page)


def small_heads(page: str) -> str:
    """<h4> subheadings ("1. Of the Lord's Body") as italic lines of the text."""
    return re.sub(r"(?is)<h4[^>]*>(.*?)</h4>\s*(?:<p>)?", r"<p>*\1*</p><p>", page)


def st_paras(page: str, keep_heads: bool = False) -> tuple:
    """(headings, centred lines, paragraphs) of a sacred-texts page."""
    hs, centred, paras = [], [], []
    for tag, c, text in blocks(page):
        text = re.sub(r"\s*\ue000\s*", "\n", text).strip()
        if tag.startswith("h"):
            hs.append(text)
        elif c and not paras:
            centred.append(text)
        else:
            paras.append(text)
    return hs, centred, paras


def st_chapter(work: str, page: str, lead: str = "", summary: bool = False) -> dict:
    """A page as a chapter: its centred title (or the first paragraph, a summary, when `summary`) leads it."""
    hs, centred, paras = st_paras(st(work, page))
    if centred:
        lead = lead or " ".join(centred)
    elif summary and paras:
        lead, paras = paras[0].rstrip(" ."), paras[1:]
    elif hs and not lead:
        lead = hs[-1]
    return chapter(paras, lead)


def summed(paras: list) -> dict:
    """A Cur Deus Homo chapter: its summary leads it (and a second part's summary, after None, leads that part)."""
    paras = [f"*{paras[i + 1].rstrip(' .')}*" if p is None else p for i, p in enumerate(paras)
             if not (i and paras[i - 1] is None)]
    return chapter(paras[1:], paras[0].rstrip(" ."))


def anselm() -> dict:
    out = {}
    out["Proslogium"] = {"0": st_chapter("ans", "ans006.htm", "Preface"),
                         **{str(n): st_chapter("ans", f"ans{6 + n:03d}.htm", summary=True) for n in range(1, 27)}}
    out["Monologium"] = {"0": st_chapter("ans", "ans033.htm", "Preface"),
                         **{str(n): st_chapter("ans", f"ans{33 + n:03d}.htm", summary=True) for n in range(1, 80)}}
    out["In Behalf of the Fool"] = {"1": st_chapter("ans", "ans113.htm", "Gaunilo, a monk of Marmoutier, in answer to the Proslogium")}
    out["Anselm's Apologetic"] = {"1": st_chapter("ans", "ans114.htm", "Anselm's reply to Gaunilo")}
    cur = {"0": st_chapter("ans", "ans116.htm", "Preface")}
    for bn, page in ((1, "ans117.htm"), (2, "ans118.htm")):
        current, paras, lead = None, [], ""
        for tag, c, text in blocks(st("ans", page)):
            m = re.fullmatch(r"CHAPTER ([IVXL]+)\.?(?: ?\(b\.?\)\.?| ?\(a\)\.?)?", text) if tag.startswith("h") else None
            if m and current == roman(m.group(1)):        # (II. 18 in two parts, (a) and (b): one chapter)
                paras.append(None)
            elif m:
                if current:
                    cur[f"{bn}.{current}"] = summed(paras)
                current, paras = roman(m.group(1)), []
            elif current and not tag.startswith("h"):
                paras.append(text)
        if current:
            cur[f"{bn}.{current}"] = summed(paras)
    expect("1.25" in cur and "2.22" in cur, f"Cur Deus Homo {list(cur)[-3:]}")
    out["Cur Deus Homo"] = cur
    return out


def francis() -> dict:
    """His own words: each page's text from its heading (<h4>, or the Canticle's anchor) on."""
    titles = {3: "Words of Admonition", 4: "Salutation of the Virtues",
              5: "On Reverence for the Lord's Body and on the Cleanliness of the Altar", 6: "First Rule of the Friars Minor",
              7: "Second Rule of the Friars Minor", 8: "Fragments from the Rule of the Sisters of St. Clare",
              9: "The Testament", 10: "Of Living Religiously in a Hermitage", 12: "Letter to All the Faithful",
              13: "Letter to All the Friars", 14: "Letter to a Certain Minister", 15: "Letter to the Rulers of the People",
              16: "Letter to All the Custodes", 17: "Letter to Brother Leo", 18: "The Praises",
              19: "Salutation of the Blessed Virgin", 20: "Prayer to Obtain Divine Love",
              21: "The Sheet Which St. Francis Gave Brother Leo", 22: "The Canticle of the Sun", 23: "The Office of the Passion"}
    book = {}
    for n, (num, title) in enumerate(titles.items(), start=1):
        page = st("wosf", f"wosf{num:02d}.htm")
        # Robinson heads each piece with its number and title, introduces it, then gives the title again and the
        # text (the Second Rule's page, a continuation, starts with the text)
        marks = list(re.finditer(r'(?is)<h[34][^>]*>(.*?)</h[34]>|<a name="an_[^"]*"', page))
        first = re.sub(r"<[^>]+>", "", marks[0].group(1) or "").strip() if marks else ""
        start = marks[2] if re.fullmatch(r"[IVX]+\.", first) else marks[0] if marks else None
        expect(start is not None, f"Francis wosf{num:02d}: no start of the text")
        end = re.search(r"(?is)<h\d[^>]*>\s*Footnotes", page)
        body = page[:page.lower().find("<body")] + "<body>" + page[start.start():end.start() if end else None]
        hs, centred, paras = st_paras(small_heads(body))
        paras = [p for p in centred + paras if not p.strip("* ").isupper()]   # (not its title again)
        book[str(n)] = chapter(paras, title)
    return book


def little_flowers() -> dict:
    out = {}
    out["Little Flowers of St. Francis"] = {str(n): st_chapter("lff", f"lff{p:03d}.htm")
                                            for n, p in enumerate([*range(4, 57), *range(105, 108)], start=1)}
    for name, pages in (("Considerations on the Holy Stigmata", range(57, 63)), ("Life of Friar Juniper", range(63, 87)),
                        ("Sayings of Friar Giles", range(87, 105))):
        out[name] = {str(n): st_chapter("lff", f"lff{p:03d}.htm") for n, p in enumerate(pages, start=1)}
    return out


def exercises() -> dict:
    """Its sections one to a chapter, in the book's order, each led by its headings ("First Week", "Fifth
    Exercise")."""
    book = {}
    for num in range(5, 83):
        hs, centred, paras = st_paras(st("seil", f"seil{num:02d}.htm"))
        hs = [h if not h.isupper() else h.title().replace("'S", "'s") for h in hs
              if h != "Spiritual Exercises of St. Ignatius of Loyola"]
        # (his references to a Gospel's verses, "the second Chapter [21]", marked as verses: not footnotes)
        paras = [re.sub(r"\[(\d+)\]", r"[v. \1]", re.sub(r"\[(\d+-\d+)\]", r"[vv. \1]", p)) for p in centred + paras]
        book[str(len(book) + 1)] = chapter(paras, "*\n*".join(hs))
    expect(len(book) == 78, f"Spiritual Exercises: {len(book)} pages")
    return book


def interior_castle() -> dict:
    mansions = {1: (5, 6), 2: (7, 7), 3: (8, 9), 4: (10, 12), 5: (13, 16), 6: (17, 28), 7: (29, 32)}
    names = ["First", "Second", "Third", "Fourth", "Fifth", "Sixth", "Seventh"]
    book = {"0": st_chapter("tic", "tic04.htm", "Preface")}
    for m, (a, b) in mansions.items():
        c = 0
        for p in range(a, b + 1):
            if p == 19:                                   # (the editor's note before vi. 3)
                continue
            c += 1
            hs, centred, paras = st_paras(st("tic", f"tic{p:02d}.htm"))
            # the chapter's summary (in capitals) and Teresa's numbered outline lead it
            lead = paras[0] if paras and paras[0].isupper() else ""
            body = paras[1:] if lead else paras
            if body and re.match(r"1\.\s.*\b2\.\s", body[0]):                  # ("1. Locutions. 2. Sometimes...")
                body = body[1:]
            lead = (f"The {names[m - 1]} Mansions*\n*" if c == 1 else "") + (lead or (hs[-1] if hs else ""))
            book[f"{m}.{c}"] = chapter(body, lead)
    book["8"] = st_chapter("tic", "tic33.htm", "Epilogue")
    expect("6.11" in book and "7.4" in book, f"Interior Castle {list(book)[-4:]}")
    return book


# ── Trent ──────────────────────────────────────────────────────────────────────────────────────────────────────
def trent() -> dict:
    page = fetch("https://history.hanover.edu/texts/trent/trentall.html", CACHE / "st_classics" / "trentall.html").decode(
        "utf-8", errors="replace")
    page = re.sub(r"(?is)<B>\s*\[Page \d+\]\s*</B>", " ", page)
    for slip, right in (("ReguIars", "Regulars"), ("themseIves", "themselves"), ("SAlNTS", "SAINTS"),
                        ("TO TRANFER", "TO TRANSFER")):           # (the scan's slips)
        expect(page.count(slip) == 1, f"Trent: {slip!r}")
        page = page.replace(slip, right)
    page = page[:page.find('<a href="/texts/trent.html">')]
    parts = re.split(r'(?is)(?:<CENTER>\s*<FONT SIZE="4">|<FONT SIZE="4">\s*<CENTER>)\s*SESSION THE ([A-Z\-]+)\b.*?'
                     r'</CENTER>(?:\s*</FONT>)?', page)
    ordinals = ["FIRST", "SECOND", "THIRD", "FOURTH", "FIFTH", "SIXTH", "SEVENTH", "EIGHTH", "NINTH", "TENTH",
                "ELEVENTH", "TWELFTH", "THIRTEENTH", "FOURTEENTH", "FIFTEENTH", "SIXTEENTH", "SEVENTEENTH",
                "EIGHTEENTH", "NINETEENTH", "TWENTIETH", "TWENTY-FIRST", "TWENTY-SECOND", "TWENTY-THIRD",
                "TWENTY-FOURTH", "TWENTY-FIFTH"]
    expect(parts[1::2] == ordinals, f"Trent sessions {parts[1::2]}")

    def session(fragment: str) -> list:
        """A session's paragraphs, a centred heading ("CHAPTER I", "CANON III") leading the paragraph after it."""
        fragment = re.sub(r'(?is)<center>\s*<img src="/pictures/longline\.jpg">\s*</center>', "<P>", fragment)
        out, pending = [], ""
        for chunk in re.split(r"(?i)<P>", fragment):
            heads = [tidy(re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", h))))
                     for h in re.findall(r"(?is)<CENTER>(.*?)</CENTER>", chunk)]
            text = tidy(re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", re.sub(r"(?is)<CENTER>.*?</CENTER>", " ", chunk)))))
            for h in heads:
                h = re.sub(r"^\[(.*)\] Note: This title is missing.*", r"\1", h)   # (Hanover's note on a title)
                h = re.sub(r"^(CHAPTER|CANON)\b", lambda m: m.group(1).capitalize(), h)
                if h:
                    pending = f"{pending} · {h}" if pending else h
            if text:
                out.append((f"*{' · '.join(sentence_case(x) for x in pending.split(' · '))}*\n" if pending else "")
                           + text.replace("--", "—"))
                pending = ""
        return out

    book = {}
    bull = parts[0][parts[0].find("UNDER THE SOVEREIGN PONTIFF, PAUL III"):]
    bull = bull[bull.upper().find("</CENTER>") + 9:]
    book["0"] = chapter(session(bull), "The Bull of Indiction of the Council, by Pope Paul III")
    for n, (_, fragment) in enumerate(zip(parts[1::2], parts[2::2]), start=1):
        book[str(n)] = chapter(session(fragment), f"Session {roman_str(n)}")
    return book


def roman_str(n: int) -> str:
    out = ""
    for value, numeral in ((10, "X"), (9, "IX"), (5, "V"), (4, "IV"), (1, "I")):
        while n >= value:
            out, n = out + numeral, n - value
    return out


FIXES = [                                         # (each must be found exactly once)
    ("later on. 8 It takes place", "later on.\n8. It takes place"),    # (Interior Castle vi. 3: a paragraph run on)
    ("and I am His. 1 A bundle", "and I am His. A bundle"),            # (de Sales iv. 12: a footnote's number)
    ("good pleasure, 0 God", "good pleasure, O God"),                  # (Trent, the Bull of Indiction)
    ("may Me Lord bless thee", "may the Lord bless thee"),             # (Francis, to a minister)
    ("it cannotbe forgotten", "it cannot be forgotten"),              # (Teresa, Life xxvi)
]


def mended(books: dict) -> dict:
    text = json.dumps(books, ensure_ascii=False)
    for old, new in FIXES:
        old_j, new_j = json.dumps(old, ensure_ascii=False)[1:-1], json.dumps(new, ensure_ascii=False)[1:-1]
        if old_j in text:
            expect(text.count(old_j) == 1, f"fix {old!r} found {text.count(old_j)} times")
            text = text.replace(old_j, new_j)
    return json.loads(text)


def main() -> None:
    medieval = {**anselm(), "Writings of St. Francis": francis(), **little_flowers(), "On Loving God": bernard(),
                "The Mind's Road to God": bonaventure(), "Sermons of Meister Eckhart": eckhart(),
                "Dialogue of Catherine of Siena": catherine()}
    reformation = {"Canons and Decrees of the Council of Trent": trent(), "Spiritual Exercises": exercises(),
                   "Interior Castle": interior_castle(), "Life of St. Teresa": teresa_life(),
                   "Ascent of Mount Carmel": ascent(), "Dark Night of the Soul": dark_night(),
                   "Spiritual Canticle": canticle(), "Introduction to the Devout Life": devout_life(),
                   "Pensées": pensees()}
    sources = {
        "Proslogium": "Anselm, trans. S. N. Deane (1903)", "Monologium": "Anselm, trans. S. N. Deane (1903)",
        "In Behalf of the Fool": "Gaunilo, trans. S. N. Deane (1903)",
        "Anselm's Apologetic": "Anselm, trans. S. N. Deane (1903)", "Cur Deus Homo": "Anselm, trans. S. N. Deane (1903)",
        "Writings of St. Francis": "trans. Paschal Robinson (1906)",
        "Little Flowers of St. Francis": "trans. T. W. Arnold (1898)",
        "Considerations on the Holy Stigmata": "trans. T. W. Arnold (1898)",
        "Life of Friar Juniper": "trans. T. W. Arnold (1898)", "Sayings of Friar Giles": "trans. T. W. Arnold (1898)",
        "On Loving God": "Bernard of Clairvaux, trans. M. C. and C. Patmore", "The Mind's Road to God": "Bonaventure",
        "Sermons of Meister Eckhart": "trans. Claud Field (1909)",
        "Dialogue of Catherine of Siena": "trans. Algar Thorold (1907)",
        "Canons and Decrees of the Council of Trent": "trans. J. Waterworth (1848)",
        "Spiritual Exercises": "Ignatius of Loyola, trans. Elder Mullan (1914)",
        "Interior Castle": "Teresa of Ávila, trans. the Benedictines of Stanbrook (1921)",
        "Life of St. Teresa": "trans. David Lewis (1904)",
        "Ascent of Mount Carmel": "John of the Cross, trans. E. Allison Peers",
        "Dark Night of the Soul": "John of the Cross, trans. E. Allison Peers",
        "Spiritual Canticle": "John of the Cross, trans. David Lewis",
        "Introduction to the Devout Life": "Francis de Sales", "Pensées": "Blaise Pascal, trans. W. F. Trotter",
    }
    for out, books in ((OUT_MEDIEVAL, medieval), (OUT_REFORMATION, reformation)):
        for name, chapters in books.items():
            print(f"  {name}: {len(chapters)} chapters, {sum(map(len, chapters.values()))} verses")
        books = mended(books)
        out.write_text(json.dumps({"source": "", "book_sources": {k: sources[k] for k in books}, "books": books},
                                  ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
