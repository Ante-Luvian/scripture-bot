"""
Jewish pseudepigrapha the library lacked, from the Wesley Center's editions of Charles's Apocrypha and Pseudepigrapha
of the Old Testament (1913) as pseudepigrapha.com has them, into data/charles/pseudepigrapha_more.json (2026-11-09):

    2 Baruch (the Syriac Apocalypse of Baruch, trans. R. H. Charles), by its chapter and verse anchors -- to 85:2,
    where every copy online stops (the Wesley Center's own, archived in 2010, too, ends "finish");
    3 Baruch (the Greek Apocalypse of Baruch, trans. H. Maldwyn Hughes), chapters at the start of a paragraph
    ("1. 1 Verily I Baruch"), verses numbered in the running text; the prologue is chapter 0. (The Wesley Center
    set each verse number in the line where the verse begins -- "the first full sentence following the number" --
    so a verse can open a few words early, and 10:2 falls empty: "into a fourth 2 3 heaven".)

Charles's section titles over the chapters ("1-4. Announcement of the coming Destruction") and the Wesley
Center's notices are left out.

    python scripts/build_pseudepigrapha.py
"""
import html
import json
import re
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CACHE = Path(__file__).resolve().parent / ".cache" / "pseudepigrapha"
OUT = ROOT / "data" / "charles" / "pseudepigrapha_more.json"
UA = {"User-Agent": "ScriptureBot corpus builder (a personal Discord bot)"}


def expect(ok: bool, message: str) -> None:
    if not ok:
        raise SystemExit(f"unexpected source layout: {message}")


def fetch(path: str) -> str:
    CACHE.mkdir(parents=True, exist_ok=True)
    f = CACHE / path.replace("/", "_")
    if not f.exists():
        req = urllib.request.Request("https://pseudepigrapha.com/" + path, headers=UA)
        f.write_bytes(urllib.request.urlopen(req, timeout=60).read())
        time.sleep(1)
    raw = f.read_bytes()
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw.decode("cp1252")


def plain(fragment: str) -> str:
    text = re.sub(r"(?is)<(script|style)\b.*?</\1>|<!\[[^\]]*\]>", "", fragment)
    text = html.unescape(re.sub(r"<[^>]+>", " ", text)).replace("\xa0", " ")
    text = re.sub(r"\s+", " ", text).strip()
    return re.sub(r"(?<=\w)\s+(?=[,;:!?]|\.(?!\s*\.))", "", text)     # ("700 years ," where a tag was taken out)


def baruch2() -> dict:
    page = fetch("pseudepigrapha/2Baruch.html")
    page = re.sub(r"(?is)<i>.*?</i>", "", page[page.find('ID="C1"'):])          # (Charles's section titles)
    page = re.split(r"(?i)HTML Layout|Translation from the Syriac", page)[0]
    # (32 and 33 are anchored "32.1", the rest "C1.1")
    parts = re.split(r'(?i)<A ID="C?(\d+)\.(\d+)">\s*<FONT[^>]*>\s*\d+\s*</FONT>\s*</A>', page)
    book = {}
    for ch, v, chunk in zip(parts[1::3], parts[2::3], parts[3::3]):
        chunk = re.sub(r'(?is)<A ID="C?\d+">.*?</A>', "", chunk)                # ("Chapter 2")
        text = plain(chunk)
        text = re.sub(r"\s*finish\s*$", "", text)
        if text:
            book.setdefault(ch, {})[v] = text
    expect(list(book) == [str(n) for n in range(1, 86)], f"2 Baruch: chapters {list(book)[-3:]}")   # (85:3-87 not online)
    return book


def running_verses(text: str) -> dict:
    """Verses numbered in the text ("...and that 2 Nebuchadnezzar the king"): a number is a verse's only if it is
    the next one."""
    verses, current = {"1": ""}, 1
    for piece in re.split(r"(?:(?<=\s)|^)(\d{1,2})\s+(?=\S)", text):
        if piece.isdigit() and int(piece) == current + 1:
            current += 1
            verses[str(current)] = ""
        elif piece.isdigit() and int(piece) == 1 and current == 1 and not verses["1"].strip():
            continue
        else:
            verses[str(current)] += piece
    return {k: re.sub(r"\s+", " ", v).strip() for k, v in verses.items() if v.strip()}


def baruch3() -> dict:
    page = fetch("pseudepigrapha/3Baruch.html")
    page = page[page.find("Prologue."):]
    page = re.split(r"Edited by Wesley Caspers", page)[0]
    # the chapter numbers are the red ones ("1.", "2", "3"); the verse numbers are in black in the text
    page = re.sub(r"(?is)<SPAN[^>]*COLOR:\s*red[^>]*>\s*(\d{1,2})\.?", r" @@CH\1@@ ", page)
    text = plain(page).replace("Prologue.", "", 1)
    parts = re.split(r"@@CH(\d+)@@", text)
    chunks = {"0": [parts[0]]}
    for num, chunk in zip(parts[1::2], parts[2::2]):
        chunks[num] = [chunk]
    book = {}
    for ch, ps in chunks.items():
        book[ch] = running_verses(" ".join(ps))
    expect(list(book) == [str(n) for n in range(0, 18)], f"3 Baruch chapters {list(book)}")
    return book


ROMAN = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100}


def roman(numeral: str) -> int:
    values = [ROMAN[c] for c in numeral]
    return sum(-v if i + 1 < len(values) and v < values[i + 1] else v for i, v in enumerate(values))


def sacred(path: str) -> str:
    CACHE.mkdir(parents=True, exist_ok=True)
    f = CACHE / ("st_" + path.replace("/", "_"))
    if not f.exists():
        req = urllib.request.Request("https://archive.sacred-texts.com/" + path, headers=UA)
        f.write_bytes(urllib.request.urlopen(req, timeout=60).read())
        time.sleep(1)
    return f.read_bytes().decode("utf-8", errors="strict")


def pseudo_philo() -> dict:
    """The Biblical Antiquities (Pseudo-Philo), M. R. James's translation (1917), from sacred-texts (bib/bap,
    pages 17-79): a chapter for each of his Roman numerals, verses by his numbers ("2. And Adam lived"); without
    the marginal Bible references, footnotes and their marks, and page numbers."""
    book = {}
    for n in range(17, 80):
        page = sacred(f"bib/bap/bap{n:02d}.htm")
        page = re.split(r"(?i)<H3[^>]*>\s*Footnotes\s*</H3>", page)[0]
        page = re.sub(r"(?is)<TABLE\b.*?</TABLE>", " ", page)                       # (the marginal references)
        page = re.sub(r'(?is)<A NAME="fr_\d+"></A>\s*<A HREF="#fn_\d+">.*?</A>', "", page)   # (footnote marks)
        page = re.sub(r'(?is)<A NAME="page_\d+">.*?</A>', "", page)                   # (page numbers)
        page = re.sub(r"(?is)<H3\b.*?</H3>", " ", page)
        # each chapter opens a paragraph with its numeral ("<P>XLII. Now there was"); XLIII and XLVII have no
        # heading of their own, so the numeral, not the heading, is what's split on
        chunks = re.split(r"(?s)<P>\s*([IVXLC]+)\.?(?:&nbsp;|\s)", page)       # ("XXIX And after": no stop)
        expect(len(chunks) > 1, f"bap{n}: no chapter")
        for num, chunk in zip(chunks[1::2], chunks[2::2]):
            text = plain(re.split(r"(?is)<nav\b|<HR\b", chunk)[0])
            verses, current = {"1": ""}, 1
            for piece in re.split(r"(?:(?<=\s)|^)(\d{1,2})\.\s+", text):
                if piece.isdigit() and int(piece) == current + 1:
                    current += 1
                    verses[str(current)] = ""
                else:
                    verses[str(current)] += (piece + ". ") if piece.isdigit() else piece
            book[str(roman(num))] = {k: re.sub(r"\s+", " ", v).strip() for k, v in verses.items() if v.strip()}
    expect(list(book) == [str(n) for n in range(1, 66)], f"Pseudo-Philo chapters {[k for k in map(str, range(1, 66)) if k not in book]}")
    return book


def lines_text(fragment: str) -> str:
    """A page as plain text keeping its line breaks (for numbers set on lines of their own)."""
    text = re.sub(r"(?is)<(script|style)\b.*?</\1>|<!--.*?-->", "", fragment)
    text = re.sub(r"(?i)<br\s*/?>|</p>|<p\b[^>]*>|</h\d>", "\n", text)
    text = html.unescape(re.sub(r"<[^>]+>", " ", text)).replace("\xa0", " ")
    return re.sub(r"[ \t]+", " ", text)


def baruch4() -> dict:
    """4 Baruch (Paraleipomena Jeremiou), the longer version, in Kraft and Purintun's translation (1971-72), from
    Kraft's public-domain CATSS edition; chapter and verse numbers on lines of their own. (The site's other copy,
    from an "Ethiopian Bible" PDF, is the same translation with Kraft's alternative readings run in.)"""
    text = lines_text(fetch("EtheopianBible/ParaleipomenaJeremiou.html"))
    start = text.find("THE THINGS OMITTED FROM JEREMIAH THE PROPHET")
    expect(start > 0, "4 Baruch: no title")
    text = text[start:]
    end = re.search(r"Paraleipomena Jeremiou\s+The S\w*orter Version", text)          # (printed "The Sorter Version")
    expect(end is not None, "4 Baruch: no shorter version after the longer")
    text = text[:end.start()]
    book = {}
    for ch, chunk in zip(*[iter(re.split(r"(?m)^\s*Chapter (\d+)\s*$", text)[1:])] * 2):
        parts = re.split(r"(?m)^\s*(\d+)\s*$", chunk)
        book[ch] = {v: re.sub(r"\s+", " ", t).strip() for v, t in zip(parts[1::2], parts[2::2]) if t.strip()}
    expect(list(book) == [str(n) for n in range(1, 10)], f"4 Baruch chapters {list(book)}")
    return book


def jasher() -> dict:
    """The Book of Jasher (Sefer ha-Yashar, the medieval Hebrew retelling of Genesis to Judges), in the anonymous
    English of 1840 as J. H. Parry reprinted it (1887): 91 chapters, verses by their numbers."""
    page = fetch("pseudepigrapha/jasher.html")
    page = page[page.find('Name="CH1"') - 20:]
    book = {}
    for ch, chunk in zip(*[iter(re.split(r'(?is)<H3>\s*<A Name="CH(\d+)">.*?</H3>', page)[1:])] * 2):
        text = lines_text(chunk)
        text = re.split(r"\bTHE END\b", text)[0]
        parts = re.split(r"(?m)^\s*(\d{1,3})\s+(?=\S)", text)
        verses = {v: re.sub(r"\s+", " ", t).strip() for v, t in zip(parts[1::2], parts[2::2]) if t.strip()}
        # (a few run on into the verse before: "...caused his death. 32. And the wives of Lamech")
        for v in list(verses):
            n = int(v) + 1
            m = re.search(rf"\s{n}\.\s+(?=[A-Z])", verses[v])
            if str(n) not in verses and m:
                verses[v], verses[str(n)] = verses[v][:m.start()].strip(), verses[v][m.end():].strip()
        book[ch] = dict(sorted(verses.items(), key=lambda kv: int(kv[0])))
    expect(list(book) == [str(n) for n in range(1, 92)], f"Jasher chapters {list(book)[-3:]}")
    return book


def book_of_adam() -> dict:
    """The Georgian Book of Adam (the Life of Adam and Eve in Georgian), J.-P. Mahé's translation made for the
    site: its sections "1.1", "2.2" (chapter.verse); his synoptic numbers in brackets ("[51]43.4") left out."""
    page = fetch("pseudepigrapha/TheBookOfAdam.htm")
    page = re.sub(r"(?is)<h2>.*?</h2>", "", page)
    book = {}
    for ref, chunk in zip(*[iter(re.split(r"(?is)<b>\s*(?:\[\d+\])?\s*(\d+\.\d+)\s*</b>", page)[1:])] * 2):
        ch, v = ref.split(".")
        text = re.sub(r"\[\d+\]\s*$", "", plain(chunk)).strip()
        if text:
            book.setdefault(ch, {})[v] = text
    expect(len(book) >= 40, f"Book of Adam: {len(book)} chapters")
    return book


def line_numbered(text: str, start: str, end: str = None) -> dict:
    """Verses numbered at the start of a line ("1 The book which Jesus Christ revealed"), from `start` on."""
    i = text.find(start)
    expect(i >= 0, f"no {start!r}")
    text = text[i:]
    if end and end in text:
        text = text[:text.find(end)]
    parts = re.split(r"(?m)^\s*(\d{1,2})\s+(?=\S)", text)
    out = {}
    for v, t in zip(parts[1::2], parts[2::2]):
        if v in out:                                  # (Laodiceans prints its 6 as a second "5")
            v = str(int(v) + 1)
        out[v] = re.sub(r"\s+", " ", t).strip()
    # a number run on into the verse before it ("...Eth.) 41 He answered and said")
    for v in sorted(map(int, out)):
        n = v + 1
        while str(n) not in out and n < max(map(int, out)):
            m = re.search(rf"(?<=[\s.)])\s*{n}\s+(?=[A-Z(\[])", out[str(n - 1)] if str(n - 1) in out else "")
            if not m:
                break
            prev = out[str(n - 1)]
            out[str(n - 1)], out[str(n)] = prev[:m.start()].strip(), prev[m.end():].strip()
            n += 1
    return dict(sorted(out.items(), key=lambda kv: int(kv[0])))


def james_more() -> dict:
    """Three more of M. R. James's Apocryphal New Testament (1924), as pseudepigrapha.com has them (the Lost Books
    pages): the Epistle of the Apostles (by its 51 sections), the Epistle to the Laodiceans, and the Correspondence
    of Paul and Seneca (a verse each letter, its heading in italics); his introductions left out."""
    books = {}
    text = lines_text(fetch("apocrypha_nt/episaps.htm"))
    books["Epistle of the Apostles"] = {"1": line_numbered(text, "1 The book which Jesus Christ revealed")}
    text = lines_text(fetch("LostBooks/paul2laodiceans.htm"))
    books["Epistle to the Laodiceans"] = {"1": line_numbered(text, "1 Paul, an apostle not of men", "It is not easy to imagine")}
    text = lines_text(fetch("LostBooks/lettersPaulSeneca.htm"))
    text = text[text.find("1. SENECA TO PAUL"):]
    letters = {}
    who = r"(?:SENECA|PAUL|ANNAEUS|TO SENECA)"                  # (10 is headed "TO SENECA, PAUL, greeting")
    for n, head, body in re.findall(rf"(?ms)^\s*(\d{{1,2}})\.\s+({who}[^\n]*)\n(.*?)(?=^\s*\d{{1,2}}\.\s+{who}|\Z)", text):
        letters[n] = f"*{head.strip()}*\n" + re.sub(r"\s+", " ", body).strip()
    books["Correspondence of Paul and Seneca"] = {"1": letters}
    expect(len(books["Epistle to the Laodiceans"]["1"]) == 20, f"Laodiceans: {len(books['Epistle to the Laodiceans']['1'])}")
    expect(len(letters) == 14, f"Paul and Seneca: {len(letters)} letters")
    expect(len(books["Epistle of the Apostles"]["1"]) >= 50, f"Epistle of the Apostles: {len(books['Epistle of the Apostles']['1'])}")
    return books


def main() -> None:
    james = james_more()
    for name, chapters in james.items():
        print(f"  {name}: {sum(map(len, chapters.values()))} verses")
    (ROOT / "data" / "nt_apocrypha" / "james_apocrypha_more.json").write_text(json.dumps(
        {"source": "trans. M. R. James (1924)", "books": james}, ensure_ascii=False, indent=1), encoding="utf-8")
    books = {"2 Baruch": baruch2(), "3 Baruch": baruch3(), "4 Baruch": baruch4(), "Biblical Antiquities": pseudo_philo(),
             "Book of Jasher": jasher(), "Georgian Book of Adam": book_of_adam()}
    sources = {"2 Baruch": "trans. R. H. Charles (1913); ends at 85:2 (the rest is not online)", "3 Baruch": "trans. H. Maldwyn Hughes (1913)",
               "Biblical Antiquities": "Pseudo-Philo, trans. M. R. James (1917)",
               "4 Baruch": "trans. Robert A. Kraft and Ann Elizabeth Purintun (1972)",
               "Book of Jasher": "anonymous translation (1840; Parry reprint, 1887)",
               "Georgian Book of Adam": "trans. Jean-Pierre Mahé"}
    for name, chapters in books.items():
        print(f"  {name}: {len(chapters)} chapters, {sum(map(len, chapters.values()))} verses")
    OUT.write_text(json.dumps({"source": "ed. R. H. Charles (1913)", "book_sources": sources, "books": books},
                              ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
