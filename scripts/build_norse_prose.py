"""The Norse prose: Snorri's Heimskringla (trans. Samuel Laing, 1844), his Prose Edda (trans. Arthur Gilchrist
Brodeur, 1916) and the Völsunga saga (trans. William Morris and Eiríkr Magnússon, 1888), from archive.sacred-texts.com
(pages cached in scripts/.cache/sacred_norse): data/norse/norse_prose.json.

A saga (or part of the Prose Edda) is a book, its chapters chapters, its paragraphs verses; a skald's verse quoted in
the prose is a paragraph of its own with its lines kept.

    python scripts/build_norse_prose.py
"""
import html
import json
import re
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "scripts" / ".cache" / "sacred_norse"
OUT = ROOT / "data" / "norse" / "norse_prose.json"
UA = "Mozilla/5.0 (ScriptureBot corpus builder, personal Discord bot)"


def fetch(path):
    CACHE.mkdir(parents=True, exist_ok=True)
    local = CACHE / path.replace("/", "_")
    if not local.exists():
        url = f"https://archive.sacred-texts.com/neu/{path}"
        local.write_bytes(urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA}),
                                                 timeout=60).read())
        time.sleep(1)
    return local.read_text(encoding="utf-8", errors="replace")


def body(page):
    """The page's text between the site's navigation bars."""
    page = re.sub(r"(?is)<script.*?</script>|<style.*?</style>", "", page)
    start = page.find("<HR>") if "<HR>" in page else page.lower().find("<body")
    end = page.rfind("<HR>")
    return page[start:end if end > start else len(page)]


LAING = "Heimskringla, trans. Samuel Laing (1844)"
BRODEUR = "The Prose Edda, trans. Arthur Gilchrist Brodeur (1916)"
MORRIS = "The Story of the Volsungs, trans. William Morris & Eiríkr Magnússon (1888)"

# Heimskringla page -> book (Laing's titles, as "X's Saga" throughout)
HEIMSKRINGLA = {
    "02ynglga": "Ynglinga Saga", "03halfdn": "Halfdan the Black's Saga", "04harfgr": "Harald Harfager's Saga",
    "05hakon": "Hakon the Good's Saga", "06grafld": "Harald Grafeld's Saga", "07olaftr": "Olaf Trygvason's Saga",
    "08stolaf": "Olaf Haraldson's Saga", "09magnus": "Magnus the Good's Saga", "10harald": "Harald Hardrade's Saga",
    "11olfkyr": "Olaf Kyrre's Saga", "12magbar": "Magnus Barefoot's Saga", "13sigurd": "Sigurd the Crusader's Saga",
    "14magbnd": "Magnus the Blind's Saga", "15siging": "The Sons of Harald's Saga",
    "16hakbrd": "Hakon Herdebreid's Saga", "17magerl": "Magnus Erlingson's Saga",
}


def unwrap(lines):
    """A paragraph's lines as one; a word broken at its hyphen across two lines ("hay-" "fork") whole again."""
    text = ""
    for l in (l.strip() for l in lines):
        text += ("" if text.endswith("-") or not text else " ") + l
    return re.sub(r"\s+", " ", text).strip()


def heimskringla(page):
    """{chapter: {verse: paragraph}} from a saga's <PRE> text: chapters "12. OF ODIN'S LAWS.", each followed by its
    ENDNOTES (Laing's, left out) and footnote marks "(1)" (taken out); Laing's PRELIMINARY REMARKS before chapter 1
    left out. A paragraph indented (a skald's verse) keeps its lines."""
    text = html.unescape(re.sub(r"<[^>]+>", "", page[page.find("<PRE>"):page.rfind("</PRE>")]))
    chapters, cur, para, in_notes = {}, None, [], False

    def flush():
        nonlocal para
        if cur and para and not in_notes:
            verse = all(re.match(r"\s{4,}\S", l) for l in para)
            t = "\n".join(l.strip() for l in para) if verse else unwrap(para)
            t = re.sub(r"\s*\(\d+\)", "", t).replace("--", "—").strip()
            t = re.sub(r"\s*—\s*$", ":", t)                  # ("So says Thjodolf: --" before his verse)
            if re.search(r"\w", t) and not re.fullmatch(r"\[End of [^\]]*\]", t):
                chapters[cur][str(len(chapters[cur]) + 1)] = t
        para = []

    for line in text.split("\n"):
        line = line.rstrip()
        head = re.fullmatch(r"\s*(\d+)\.[\s\-]*([A-Z][^a-z]*?)\.?\s*", line)      # ("29.GUTHORM'S", "36.---OF")
        if head and line.strip().upper() == line.strip():
            flush()
            last = cur
            cur, in_notes = head.group(1), False
            if (last and str(int(last) + 1) not in chapters
                    and (cur in chapters or int(cur) > int(last) + 5)):
                cur = str(int(last) + 1)                    # (misprints: Ynglinga's 12 printed "11", Magnus the
                                                            #  Good's 15 "115")
            while cur in chapters:                          # (otherwise a number printed twice: kept apart)
                cur += "a"
            chapters[cur] = {}
            continue
        if re.fullmatch(r"\s*(END)?NOTES?:?\s*", line) or re.fullmatch(r"\s*FOOTNOTES?:?\s*", line):
            flush()
            in_notes = True
            continue
        if not line.strip():
            flush()
            continue
        para.append(line)
    flush()
    return {c: v for c, v in chapters.items() if v}


ROMAN = re.compile(r"^([IVXLC]+)\.\s+")


def html_paragraphs(page, notes_mark=r"\s*\[\d+\.?(?:\s[^\]]*)?\]"):
    """(text, is_verse) for each <P> of a page: verse inside <DIR> keeps its lines; page marks ("{p. 14}") dropped
    and a paragraph they cut in two joined again; footnote marks ("[1]") and Brodeur's notes printed in the text
    ("[1. Earth.]") taken out; the footnotes at the end left out."""
    b = body(page)
    cut = re.search(r"(?i)<H\d[^>]*>\s*Footnotes|<P>\s*<A NAME=\"fn_", b)
    if cut:
        b = b[:cut.start()]
    out, depth = [], 0
    for m in re.finditer(r"(?is)<(/?)DIR>|<P[^>]*>(.*?)</P>", b):
        if m.group(2) is None:
            depth += -1 if m.group(1) else 1
            continue
        raw = re.sub(r"(?i)<BR\s*/?>", "\n", m.group(2))
        raw = re.sub(r"(?is)<A[^>]*HREF=\"#fn_\d+\"[^>]*>.*?</A>|<SUP>.*?</SUP>", "", raw)
        t = html.unescape(re.sub(r"<[^>]+>", "", raw)).replace("\xa0", " ")
        t = re.sub(notes_mark, "", t)
        t = re.sub(r"^\s*\[(?=[IVXLC]+\.)", "", t)           # ("[XXI." in Skáldskaparmál)
        t = re.sub(r"^([IVXLC]+\.)\"\s*", r'\1 "', t)       # ("XIX.\" How should": the quote misplaced)
        if re.fullmatch(r"\s*\{p\.\s*[\divxlc]+\}\s*", t, re.I):
            out.append(("{page}", False))
            continue
        t = re.sub(r"\{p\.\s*[\divxlc]+\}", "", t, flags=re.I)
        lines = [re.sub(r"\s+", " ", l).strip() for l in t.split("\n")]
        verse = depth > 0
        t = "\n".join(l for l in lines if l) if verse else re.sub(r"\s+", " ", t).strip()
        if t:
            out.append((t, verse))
    # (Völsunga's ENDNOTES, and two editors' notes, "[End of Snorri Sturlson's Heimskringla]"-like, left out)
    if any(re.match(r"ENDNOTES?:?$", t) for t, _ in out):
        out = out[:next(i for i, (t, _) in enumerate(out) if re.match(r"ENDNOTES?:?$", t))]
    out = [(t, v) for t, v in out if not re.match(r"\[Here Wilken closes his edition", t)]
    # (a note of Brodeur's running over several paragraphs: "[1. High." ... "3. Third.]": all of it dropped)
    kept, in_note = [], False
    for t, verse in out:
        if not in_note and re.match(r"\[\d", t) and "]" not in t:
            in_note = True
            continue
        if in_note:
            if "]" in t:
                in_note = False
                t = t[t.index("]") + 1:].strip()
                if t:
                    kept.append((t, verse))
            continue
        kept.append((t, verse))
    out = kept
    joined = []                                              # (a page mark between halves of one paragraph)
    for i, (t, verse) in enumerate(out):
        if t == "{page}":
            continue
        if (joined and i and out[i - 1][0] == "{page}" and not verse and not joined[-1][1]
                and not re.search(r"[.!?:\"”’)]$", joined[-1][0])):
            joined[-1] = (joined[-1][0] + " " + t, False)
        else:
            joined.append((t, verse))
    return joined


def roman_chapters(paras, first="I"):
    """Brodeur's chapters: a paragraph opening "XIV. " begins chapter XIV (numbered 14 here)."""
    chapters, cur = {}, None
    for t, verse in paras:
        m = ROMAN.match(t) if not verse else None
        if m and (roman(m.group(1)) == roman(first) if not cur else int(cur) < roman(m.group(1)) <= int(cur) + 3):
            cur = str(roman(m.group(1)))
            chapters[cur] = {}
            t = t[m.end():]
        if cur:
            chapters[cur][str(len(chapters[cur]) + 1)] = t
    return chapters


def roman(s):
    values = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100}
    n = 0
    for a, b in zip(s, s[1:] + " "):
        n += -values[a] if values.get(b, 0) > values[a] else values[a]
    return n


def build():
    books, sources = {}, {}
    for page, book in HEIMSKRINGLA.items():
        books[book] = heimskringla(fetch(f"heim/{page}.htm"))
        sources[book] = LAING
    for page, book in (("pre03", "Prologue to the Prose Edda"), ("pre04", "Gylfaginning"),
                       ("pre05", "Skaldskaparmal")):
        paras = html_paragraphs(fetch(f"pre/{page}.htm"))
        chapters = roman_chapters(paras)
        if not chapters:                                     # (the Prologue: chapters unnumbered, one chapter)
            chapters = {"1": {str(i + 1): t for i, (t, _) in enumerate(paras)}}
        books[book] = chapters
        sources[book] = BRODEUR
    volsung = {}
    for n in range(3, 46):                                   # (chapters I-XLIII; the appendices are Edda poems)
        paras = html_paragraphs(fetch(f"vlsng/vlsng{n:02d}.htm"))
        volsung[str(n - 2)] = {str(i + 1): t for i, (t, _) in enumerate(paras)}
    books["Volsunga Saga"] = volsung
    sources["Volsunga Saga"] = MORRIS
    for chapters in books.values():                          # (the pages' own slips)
        for verses in chapters.values():
            for v, t in verses.items():
                for typo, fixed in (("half- mark", "half-mark"), ("and- clad", "and clad"), ("set- the", "set the"),
                                    ("Skald- Despoiler", "Skald-Despoiler")):
                    t = t.replace(typo, fixed)
                verses[v] = t
    for book, chapters in books.items():
        print(f"{book}: {len(chapters)} chapters, {sum(len(v) for v in chapters.values())} paragraphs")
    OUT.write_text(json.dumps({"source": LAING, "book_sources": sources, "books": books}, ensure_ascii=False,
                              indent=1) + "\n", encoding="utf-8")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    build()
