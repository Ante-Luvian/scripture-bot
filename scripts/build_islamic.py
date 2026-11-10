"""
Classics of Islam and Sufism the library lacked, from the archive of sacred-texts.com (isl/), into
data/sufi/islamic_classics.json (2026-11-09).

    python scripts/build_islamic.py [names...]

Each page is read from its HTML: the text between the site's header ("... at sacred-texts.com") and its
footer, without the translators' footnotes and their marks, page numbers, or the line numbers in the margin; a
paragraph a verse (a stanza, for verse, its lines kept), the chapter's headings in italics over the paragraph
after them.
"""
import html
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_world_texts as w            # (its sacred_text() and st_index() fetch and cache the archive)

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "sufi" / "islamic_classics.json"


def expect(ok: bool, message: str) -> None:
    if not ok:
        raise SystemExit(f"unexpected source layout: {message}")


def pages(work: str) -> list:
    return w.st_index(f"isl/{work}/index.htm")


def paras(path: str) -> list:
    """A page's paragraphs and headings ("## ..."), in order."""
    page = w.sacred_text(path)
    page = re.sub(r"(?is)<(script|style|head)\b.*?</\1>", "", page)
    head = re.search(r"(?is)at sacred-texts\.com.*?<HR>|Next</A>.*?<HR>", page)
    page = page[head.end():] if head else page
    end = re.search(r'(?is)<H\d[^>]*>\s*Footnotes|<HR>\s*(?:<P[^>]*>)?\s*(?:<CENTER>)?\s*<A HREF="[^"]*">Next:'
                    r'|<A HREF="[^"]*">\s*Next:|<nav\b', page)
    page = page[:end.start()] if end else page
    page = re.sub(r'(?is)<span class="margnote">.*?</span>', "", page)                    # (line numbers)
    page = re.sub(r'(?is)<a\s+href="?[^">]*#(?:fn|an|fr)_[^>]*>.*?</a>', "", page)          # (note marks)
    page = re.sub(r'(?is)<a\s+name="?page_[^>]*>.*?</a>', "", page)                         # (page numbers)
    page = re.sub(r"(?is)<P[^>]*>\s*\{p\. [\divxlc]+\}\s*</P>|\{p\. [\divxlc]+\}", "", page)
    page = re.sub(r"(?is)<P[^>]*>\s*\[\d+\.\s.*?\]\s*</P>", "", page)                       # ("[1. Traditional saying...]")
    page = re.sub(r"(?is)<H\d[^>]*>(.*?)</H\d>", lambda m: "<P>## " + m.group(1) + "</P>", page)
    out = []
    for chunk in re.split(r"(?i)<P\b[^>]*>", page):
        chunk = re.sub(r"(?i)<br\s*/?>", "\n", chunk)
        text = html.unescape(re.sub(r"<[^>]+>", "", chunk)).replace("\xa0", " ")
        lines = [re.sub(r"[ \t]+", " ", l).strip() for l in text.split("\n")]
        text = "\n".join(l for l in lines if l)
        text = re.sub(r"\[\d+\]", "", text)                                                   # ("God,"[1] and)
        text = re.sub(r"\s*\[p\. [\divxlc]+\]\s*", " ", text).strip()                        # ("is [p. 6] marked")
        if not text or re.fullmatch(r"[\W\d]*|p\. \d+|THE END\.?", text):
            continue
        if re.search(r"(?i)at sacred-texts\.com|^Sacred[- ]Texts\b|^Buy this Book", text):     # (the site's own lines)
            continue
        if out and not text.startswith("## ") and re.match(r"[a-z]", text) and not out[-1].startswith("## "):
            out[-1] += " " + text                                           # (a paragraph cut by a page break)
        else:
            out.append(text)
    return out


def verses(ps: list, drop_heads: int = 0) -> dict:
    """Paragraphs as verses, each heading in italics over the next; the first `drop_heads` headings (the
    chapter's own number and title, which the chapter's citation already gives) dropped."""
    out, pending, heads = {}, [], 0
    for p in ps:
        if p.startswith("## "):
            heads += 1
            if heads > drop_heads:
                pending.append(f"*{p[3:].strip()}*")
            continue
        out[str(len(out) + 1)] = "\n".join(pending + [p])
        pending = []
    return out


def alchemy_of_happiness() -> dict:
    """Al-Ghazali, The Alchemy of Happiness, trans. Claud Field (1910): its eight chapters."""
    chapters = [(p, l) for p, l in pages("tah") if l.startswith("Chapter ")]
    expect(len(chapters) == 8, f"Alchemy: {len(chapters)} chapters")
    return {str(n): verses(paras(p), drop_heads=2) for n, (p, _) in enumerate(chapters, 1)}


def mishkat() -> dict:
    """Al-Ghazali, The Niche for Lights (Mishkat al-Anwar), trans. W. H. T. Gairdner (1924): its three parts;
    Gairdner's long introduction and his own preface ("Author's Preface") left out."""
    idx = pages("mishkat")
    picks = [(p, l) for p, l in idx if l.startswith(("PART I.", "PART II.", "PART III."))]
    expect(len(picks) == 3, f"Mishkat: {[l for _, l in picks]}")
    return {str(n): verses(paras(p), drop_heads=1) for n, (p, _) in enumerate(picks, 1)}


def bird_parliament() -> dict:
    """Attar's Conference of the Birds in Edward FitzGerald's version, Bird Parliament (1889): a stanza a verse."""
    ps = [p for p in paras("isl/bp/bp01.htm") if not p.startswith("## ")]
    expect(len(ps) > 40, f"Bird Parliament: {len(ps)} stanzas")
    return {"1": {str(n): p for n, p in enumerate(ps, 1)}}


def bustan() -> dict:
    """Sa'di's Bustan, trans. A. Hart Edwards (1911): the prologue (0) and the ten chapters; each story's title
    in italics over it."""
    idx = pages("bus")
    picks = [(p, l) for p, l in idx if l.startswith(("Prologue", "Chapter "))]
    expect(len(picks) == 11, f"Bustan: {[l for _, l in picks]}")
    return {str(n): verses(paras(p), drop_heads=2 if n else 1) for n, (p, _) in enumerate(picks)}


def gospel_of_barnabas() -> dict:
    """The Gospel of Barnabas (the Italian manuscript, probably of the 16th century, with an Islamic Jesus), trans.
    Lonsdale and Laura Ragg (1907): its 222 chapters, each chapter's title in italics over its first verse."""
    idx = [(p, l) for p, l in pages("gbar") if re.match(r"\d+\.", l)]
    expect(len(idx) == 222, f"Barnabas: {len(idx)} chapters")
    out = {}
    for p, l in idx:
        n = re.match(r"(\d+)\.", l).group(1)
        ps = paras(p)
        heads = [x for x in ps if x.startswith("## ")]
        body = verses(ps, drop_heads=1)
        title = re.sub(r"^\d+\.\s*", "", heads[0][3:]) if heads else ""
        if body and title:
            body["1"] = f"*{title}*\n" + body["1"]
        out[n] = body
    return out


ROMAN = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100}


def roman(numeral: str) -> int:
    values = [ROMAN[c] for c in numeral]
    return sum(-v if i + 1 < len(values) and v < values[i + 1] else v for i, v in enumerate(values))


def salaman_and_absal() -> dict:
    """Jami's Salaman and Absal, Edward FitzGerald's version (1879 text): its numbered sections, a stanza a verse;
    the plates' captions ("Click to enlarge"), his preface, life of Jami, appendix and notes left out."""
    out = {}
    for p, l in pages("saab"):
        m = re.match(r"([IVXL]+)\b", l)
        if not m or l.startswith("Index"):
            continue
        ps = [x for x in paras(p) if x != "Click to enlarge" and not x.startswith(("## ", "The several Spellings"))]
        if ps:
            out[str(roman(m.group(1)))] = {str(i): x for i, x in enumerate(ps, 1)}
    expect(len(out) >= 25 and "1" in out, f"Salaman and Absal: {len(out)} sections")
    return out


def secret_rose_garden() -> dict:
    """Mahmud Shabistari's Secret Rose Garden (Gulshan-i Raz), trans. Florence Lederer (1920): its fourteen parts
    and the epilogue (15), each part's own headings over the stanzas after them."""
    picks = [(p, l) for p, l in pages("srg") if l.startswith(("Part ", "Epilogue"))]
    expect(len(picks) == 15, f"Rose Garden: {[l for _, l in picks]}")
    return {str(n): verses([x for x in paras(p) if x != "IN THE NAME OF GOD, THE COMPASSIONATE, THE MERCIFUL"],
                           drop_heads=2 if n < 15 else 1) for n, (p, _) in enumerate(picks, 1)}


def scroll_of_wisdom() -> dict:
    """Sa'di's Scroll of Wisdom (the Pand-nama), trans. Arthur N. Wollaston (1906): a chapter for each of its
    sections, its title in italics over it."""
    idx = pages("ssw")
    start = next(i for i, (_, l) in enumerate(idx) if l.startswith("Sadi's Scroll of Wisdom"))
    picks = [(p, l) for p, l in idx[start:] if not l.startswith(("Next", "«", "Index"))]
    out = {str(n): verses([x for x in paras(p) if not x.lstrip("_").strip().startswith("Printed by")])
           for n, (p, _) in enumerate(picks, 1)}                     # (the printer's imprint at the end)
    return {k: v for k, v in out.items() if v}


def gulistan() -> dict:
    """Sa'di's Gulistan (the Rose Garden), trans. Edward Rehatsek (1888), from the archive's plain text: its eight
    chapters, a verse each story; the verses of poetry in it kept as lines."""
    text = w.sacred_text("isl/gulistan.txt")
    text = re.sub(r"\s*-THE END-\s*\.?", "", text)
    parts = re.split(r"(?m)^\s*CHAPTER ([IVX]+)\s*$", text)
    expect(len(parts) == 17, f"Gulistan: {len(parts) // 2} chapters")
    out = {}
    for num, chunk in zip(parts[1::2], parts[2::2]):
        stories = re.split(r"(?m)^\s*(?:Story|Maxim) (\d+)\s*$", chunk)             # (VIII is maxims)
        title = stories[0].strip().splitlines()[0].strip().title()
        book = {}
        for n, body in zip(stories[1::2], stories[2::2]):
            lines, para = [], []
            for line in body.rstrip().splitlines():
                if not line.strip():
                    continue
                if line.startswith("        "):          # (a line of verse)
                    if para:
                        lines.append(" ".join(para))
                        para = []
                    lines.append(line.strip())
                elif line.startswith("  ") and para:      # (a new paragraph)
                    lines.append(" ".join(para))
                    para = [line.strip()]
                else:
                    para.append(line.strip())
            if para:
                lines.append(" ".join(para))
            book[n] = "\n".join(lines)
        if book:
            book["1"] = f"*{title}*\n" + book["1"]
        out[str(roman(num))] = book
    expect(list(out) == [str(n) for n in range(1, 9)], f"Gulistan chapters {list(out)}")
    return out


def tarjuman() -> dict:
    """Ibn Arabi's Tarjuman al-Ashwaq (The Interpreter of Desires), trans. R. A. Nicholson (1911): its sixty-one
    odes, by their numbered verses; Nicholson's commentary under each (from Ibn Arabi's own) left out."""
    out = {}
    for p, l in pages("taa"):
        if not re.fullmatch(r"[IVXL]+", l):
            continue
        ps = paras(p)
        head = next((re.fullmatch(r"## ([IVXL]+)\.?", x) for x in ps if re.fullmatch(r"## ([IVXL]+)\.?", x)), None)
        l = head.group(1) if head else l                # (the index lists XXXIV as "XXIV"; the page's heading is right)
        lines = {}
        for x in ps:
            m = re.match(r"(\d{1,2})\.\s+(.*)", x, re.S)
            if m and int(m.group(1)) == len(lines) + 1:
                lines[m.group(1)] = m.group(2).strip()
        if lines:
            out[str(roman(l))] = lines
    expect(len(out) == 61, f"Tarjuman: {len(out)} odes")
    return out


def hadiqa() -> dict:
    """Sana'i's Hadiqat al-Haqiqat (The Enclosed Garden of the Truth), the first book, trans. J. Stephenson (1910):
    a chapter for each of its headed sections; Stephenson's introduction and Sana'i's prose preface left out."""
    idx = pages("egt")
    start = next(i for i, (_, l) in enumerate(idx) if l.startswith("The First Book of the Had"))
    picks = [(p, l) for p, l in idx[start + 1:] if not l.startswith(("Next", "«", "Index"))]
    out = {str(n): verses(paras(p)) for n, (p, _) in enumerate(picks, 1)}
    return {k: v for k, v in out.items() if v}


QURAN_OUT = ROOT / "data" / "quran" / "islamic_more.json"
# (name: builder, citation, file -- the Sufi works on the Sufi shelf's file, the rest with the Islamic books)
BUILDERS = {
    "Alchemy of Happiness": (alchemy_of_happiness, "al-Ghazali, trans. Claud Field (1910)", OUT),
    "Niche for Lights": (mishkat, "al-Ghazali, trans. W. H. T. Gairdner (1924)", OUT),
    "Bird Parliament": (bird_parliament, "Attar, trans. Edward FitzGerald (1889)", OUT),
    "Bustan": (bustan, "Sa'di, trans. A. Hart Edwards (1911)", OUT),
    "Gospel of Barnabas": (gospel_of_barnabas, "trans. Lonsdale and Laura Ragg (1907)", QURAN_OUT),
    "Salaman and Absal": (salaman_and_absal, "Jami, trans. Edward FitzGerald", OUT),
    "Secret Rose Garden": (secret_rose_garden, "Shabistari, trans. Florence Lederer (1920)", OUT),
    "Scroll of Wisdom": (scroll_of_wisdom, "Sa'di, trans. Arthur N. Wollaston (1906)", OUT),
    "Gulistan": (gulistan, "Sa'di, trans. Edward Rehatsek (1888)", OUT),
    "Tarjuman al-Ashwaq": (tarjuman, "Ibn Arabi, trans. R. A. Nicholson (1911)", OUT),
    "Hadiqat al-Haqiqat": (hadiqa, "Sana'i, trans. J. Stephenson (1910)", OUT),
}


def main(names: list) -> None:
    payloads = {}
    for name, (fn, source, out) in BUILDERS.items():
        if names and name not in names:
            continue
        if out not in payloads:
            payloads[out] = (json.loads(out.read_text(encoding="utf-8")) if out.exists()
                             else {"source": "sacred-texts.com", "book_sources": {}, "books": {}})
        book = fn()
        expect(all(book.values()), f"{name}: an empty chapter")
        payloads[out]["source"] = "various translators"           # (each book's own is in book_sources)
        payloads[out]["books"][name] = book
        payloads[out]["book_sources"][name] = source
        print(f"  {name}: {len(book)} chapters, {sum(map(len, book.values()))} passages")
    for out, payload in payloads.items():
        if out != QURAN_OUT:                     # (Barnabas moved out of the Sufi file)
            payload["books"].pop("Gospel of Barnabas", None)
            payload["book_sources"].pop("Gospel of Barnabas", None)
        out.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main(sys.argv[1:])
