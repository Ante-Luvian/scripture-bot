"""
Jewish pseudepigrapha the library lacked, from the Wesley Center's editions of Charles's Apocrypha and Pseudepigrapha
of the Old Testament (1913) as pseudepigrapha.com has them, into data/charles/pseudepigrapha_more.json (2026-11-09):

    2 Baruch (the Syriac Apocalypse of Baruch, trans. R. H. Charles), by its chapter and verse anchors -- to 85:2,
    where every copy online stops (the Wesley Center's own, archived in 2010, too, ends "finish");
    3 Baruch (the Greek Apocalypse of Baruch, trans. H. Maldwyn Hughes), chapters at the start of a paragraph
    ("1. 1 Verily I Baruch"), verses numbered in the running text; the prologue is chapter 0. (The Wesley Center
    set each verse number in the line where the verse begins -- "the first full sentence following the number" --
    so a verse can open a few words early, and 10:2 falls empty: "into a fourth 2 3 heaven".)

Also (2026-11-10) from the same site: Charles's Slavonic Life of Adam and Eve, Meir Bar-Ilan's Words of Gad the Seer, and
the Apocalypse of Pseudo-Methodius, Greek and Latin (the page names no translator; its own PDF is Garstad's 2012
Dumbarton Oaks edition, which it matches word for word).

And (2026-11-10) six more from elsewhere, none of them on that site: Joseph and Aseneth (David Cook's translation, from
Mark Goodacre's pages); the Apocalypse of Abraham (Box), the Testament of Job (Kohler), the Lives of the Prophets
(after Torrey) and the Apocalypse of Elijah (Alcock), from TheoDoor's Word files (tohdee.github.io), which modernise
the thees and thous; and the Apocalypse of Zephaniah (Wintermute), from a page of 2010 the Internet Archive kept.
Each builder's docstring says how its verses are numbered.

Charles's section titles over the chapters ("1-4. Announcement of the coming Destruction") and the Wesley
Center's notices are left out.

    python scripts/build_pseudepigrapha.py
"""
import html
import io
import json
import re
import time
import urllib.error
import urllib.request
import zipfile
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


def slavonic_adam() -> dict:
    """The Slavonic Life of Adam and Eve (Charles 1913, ii. 134-136): chapters xxviii-xl, verse numbers at the start
    of the page's lines. The site prints xxix as "xxxix", so the chapters are numbered in order, not by their
    numerals; Charles's closing note (the rest runs parallel to the Apocalypse of Moses) stays, in italics."""
    page = fetch("pseudepigrapha/slanev.htm")
    page = page[page.find("<hr>") + 4:]
    page = page[:page.find("Scanned and Edited")]
    page = re.sub(r"(?is)<hr>.*", "", page)
    paras = [p for p in re.split(r"(?i)<p>", page) if plain(p)]
    note = plain(paras.pop())
    expect(note.startswith("(Passage follows exactly parallel"), f"Slavonic Adam: last paragraph {note[:40]!r}")
    chapters, numerals = [], []
    for p in paras:
        m = re.match(r"\s*([xvil]+)\s*(?=\d)", p)
        if m:
            numerals.append(m.group(1))
            chapters.append(p[m.end():])
        else:
            chapters[-1] += " " + p                   # ("But Adam said:" opens a paragraph inside xxxv)
    expect(numerals[0] == "xxviii" and len(numerals) == 13, f"Slavonic Adam: chapters {numerals}")
    book = {}
    for n, chunk in enumerate(chapters, start=28):
        parts = re.split(r"(?i)(?:^|<br>)\s*(\d+)\s*", chunk)
        book[str(n)] = {v: plain(t).replace("archangcl", "archangel") for v, t in zip(parts[1::2], parts[2::2]) if plain(t)}
    last = book["40"]
    last[max(last, key=int)] += f"\n*{note}*"
    return book


# OCR slips in the page, checked against the printed edition (its PDF): "fo!!eth" is italic "falleth", "lzdes" Izdes
METHODIUS_SLIPS = {"hls": "his", "lshmael": "Ishmael", "oflsrael": "of Israel", "lsrael": "Israel", "lzdes": "Izdes", "folleth": "falleth",
                   "depair": "despair"}
# typing slips in the Words of Gad the Seer page (a letter dropped or swapped; the sense is never in doubt)
GAD_SLIPS = {"shackels": "shackles", "stoped": "stopped", "wunds": "wounds", "tje": "the", "oice": "voice",
             "becuse": "because", "ick": "sick", "iIsrael": "Israel", "plegue": "plague", "peole": "people",
             "peope": "people", "magisty": "majesty", "presereveth": "preserveth", "reevenge": "revenge",
             "they loins": "thy loins", "side o the": "side of the", "hand if impurity": "hand of impurity",
             "he poke": "he spoke", "Mose": "Moses", "kingdome": "kingdom", "sone of man": "son of man",
             "manor of store": "manner of store", "an alter": "an altar", "Swear to my": "Swear to me",
             "thevoice": "the voice"}


def pseudo_methodius() -> tuple:
    """The Apocalypse of Pseudo-Methodius, the Greek and the Latin side by side (the page's two columns: its own
    PDF is Benjamin Garstad's Dumbarton Oaks edition, 2012, Greek first, then Latin). Verses by the anchors
    ("C1.4", and "C1.4a" for the Latin); the page's titles over each column lead verse 1 in italics."""
    page = fetch("pseudepigrapha/ApocalypseOfPseudoMethodius_01.html")
    titles = [plain(t) for t in re.findall(r'(?is)<TD Align="center" Width="50%">(.*?)</TD>', page)]
    expect(len(titles) == 2 and titles[0].startswith("AN ACCURATE RELATION"), f"Pseudo-Methodius titles {titles}")
    greek, latin = {}, {}
    parts = re.split(r'(?is)<FONT Color="blue"><A ID="C(\d+)\.(\d+)(a?)">[^<]*</A></FONT>', page)
    for ch, v, a, chunk in zip(parts[1::4], parts[2::4], parts[3::4], parts[4::4]):
        chunk = re.split(r"(?i)</TD>", chunk)[0]
        text = plain(chunk)
        text = re.sub(r"\b(of|if|himself|patriarch)(?=(?:the|his|Adam|brute|heart|all|godliness|he|openly)\b|[A-Z])",
                      r"\1 ", text)                                       # (the scan's slips: "ofthe", "ofJoppa")
        for slip, word in METHODIUS_SLIPS.items():
            text = re.sub(rf"\b{slip}\b", word, text)
        text = text.replace("{or}", "or")
        (latin if a else greek).setdefault(ch, {})[v] = text
    for book, title in ((greek, titles[0]), (latin, titles[1])):
        expect(list(book) == [str(n) for n in range(1, 15)], f"Pseudo-Methodius chapters {list(book)}")
        title = title[0] + title[1:].lower().replace("methodius", "Methodius").replace("patara", "Patara").replace("adam", "Adam").replace("saint", "Saint")
        book["1"]["1"] = f"*{title}*\n" + book["1"]["1"]
    return greek, latin


def gad_the_seer() -> dict:
    """The Words of Gad the Seer, Meir Bar-Ilan's translation of Cambridge MS Oo.1.20 (copied at Cochin): chapters by
    the Roman numerals on lines of their own (the page has no "XI", so X runs on to XII), verses numbered straight
    through the book. Five numbers misprinted on the page (343-347 for 243-247, 376 for 367) are put in order;
    "265b" is the last line of 265. Psalm verses keep their lines."""
    page = fetch("WordsOfTheSeerGad.html")
    title = re.search(r"<b>Words\s+of Gad the Seer</b>", page)
    expect(title is not None, "Gad: no title")
    page = page[title.end():]
    lines = [plain(p) for p in re.findall(r"(?is)<p\b[^>]*>(.*?)</p>", page)]
    lines = [re.sub(r",(?=[A-Za-z])", ", ", l) for l in lines if l]
    for slip, word in GAD_SLIPS.items():
        lines = [re.sub(rf"\b{slip}\b", word, l) for l in lines]
    book, chapter, prev, fixed = {}, None, 0, []
    for line in lines:
        if re.fullmatch(r"[IVXL]+", line):
            chapter = str(roman(line))
            book[chapter] = {}
            continue
        m = re.match(r"(\d+)(b?)\s+(.*)", line)
        if m and m.group(2):                          # ("265b")
            book[chapter][str(prev)] += "\n" + m.group(3)
        elif m:
            if int(m.group(1)) != prev + 1:
                fixed.append(m.group(1))
            prev += 1
            book[chapter][str(prev)] = m.group(3)
        else:
            book[chapter][str(prev)] += "\n" + line
    expect(fixed == ["343", "344", "345", "346", "347", "376"], f"Gad: numbers out of order {fixed}")
    expect(prev == 375 and list(book) == [str(n) for n in (*range(1, 11), 12, 13, 14)], f"Gad: {list(book)}, {prev}")
    return book


BROWSER = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
                         "Chrome/126.0 Safari/537.36"}
THEODOOR = "https://tohdee.github.io/"


def cached(name: str, url: str) -> bytes:
    """A file from another site, kept in the cache (asked for as a browser where the plain request is refused)."""
    CACHE.mkdir(parents=True, exist_ok=True)
    f = CACHE / name
    if not f.exists():
        try:
            data = urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60).read()
        except urllib.error.HTTPError:
            data = urllib.request.urlopen(urllib.request.Request(url, headers=BROWSER), timeout=60).read()
        f.write_bytes(data)
        time.sleep(1)
    return f.read_bytes()


def docx_paragraphs(name: str, url: str) -> list:
    """A Word file's paragraphs as (kind, text): "head" for a centred one, "line" for an indented one (verse set
    line by line), "text" for the rest."""
    xml = zipfile.ZipFile(io.BytesIO(cached(name, url))).read("word/document.xml").decode("utf-8")
    out = []
    for p in re.findall(r"(?s)<w:p[ >].*?</w:p>", xml):
        runs = re.sub(r"<w:(?:tab|br)\b[^>]*/>", "<w:t> </w:t>", p)
        text = html.unescape("".join(re.findall(r"(?s)<w:t(?: [^>]*)?>(.*?)</w:t>", runs))).replace("\xa0", " ")
        if not text.strip():
            continue
        ppr = re.search(r"(?s)<w:pPr>(.*?)</w:pPr>", p)
        ppr = ppr.group(1) if ppr else ""
        kind = ("head" if '<w:jc w:val="center"/>' in ppr
                else "line" if re.search(r"<w:ind [^>]*w:left=", ppr) else "text")
        out.append((kind, text))
    return out


def untic(text: str) -> str:
    """Without the comma these Word files set after every "for" that opens a clause ("for, the Egyptians held him
    in honour"), which is the files' habit, not the translators'. "For, behold" keeps its comma."""
    return re.sub(r"(?<![A-Za-z] )\b([Ff]or), (?!behold\b|lo\b|for\b)", r"\1 ", text)


def fix_slips(paras: list, slips: dict, book: str) -> list:
    """The paragraphs with each slip put right; the build stops unless every slip is found exactly once."""
    seen, out = dict.fromkeys(slips, 0), []
    for kind, text in paras:
        for slip, right in slips.items():
            seen[slip] += text.count(slip)
            text = text.replace(slip, right)
        out.append((kind, text))
    expect(set(seen.values()) == {1}, f"{book}: slips not found once each {[s for s, n in seen.items() if n != 1]}")
    return out


def counted_verses(text: str, stop: str = "", skips: list = None) -> dict:
    """Verses numbered in the text, like running_verses, but keeping the text's line breaks; `stop` is what stands
    after a number (Cook's "2. And the top storey"). Given a `skips` list, a number may also jump ahead (a text
    that lacks verses its numbering counts), and each jump is added to the list."""
    verses, current = {}, 0
    for piece in re.split(rf"(?:(?<=\s)|^)(\d{{1,2}}){re.escape(stop)}\s+(?=[A-Z“‘(\[])" if skips is not None
                          else rf"(?:(?<=\s)|^)(\d{{1,2}}){re.escape(stop)}\s+(?=\S)", text):
        if piece.isdigit() and (int(piece) == current + 1 or (skips is not None and current < int(piece) <= current + 12)):
            if int(piece) != current + 1:
                skips.append(f"{current}->{piece}")
            current = int(piece)
            verses[str(current)] = ""
        elif current == 0:
            expect(not piece.strip(), f"text before verse 1: {piece[:50]!r}")
        else:
            verses[str(current)] += f"{piece}{stop} " if piece.isdigit() else piece
    return {v: re.sub(r" *\n *", "\n", re.sub(r"[ \t]+", " ", t)).strip() for v, t in verses.items()}


SENTENCE_END = r"(?:(?<=[.!?])|(?<=[.!?][\"'”’)\]]))\s+(?=[A-Z\"“‘(\[])"


def sentence_groups(paras: list, size: int = 450, longest: int = 600) -> list:
    """Paragraphs, with any longer than `longest` cut into runs of whole sentences of about `size` characters (as in
    build_world_texts.py), for a text printed without verse numbers; a short last run joins the one before it."""
    out = []
    for p in paras:
        if len(p) <= longest:
            out.append(p)
            continue
        runs, run = [], ""
        for s in re.split(SENTENCE_END, p):
            if run and len(run) + len(s) > size:
                runs.append(run)
                run = s
            else:
                run = f"{run} {s}".strip()
        if run and runs and len(run) < 120:
            runs[-1] += " " + run
        elif run:
            runs.append(run)
        out += runs
    return out


# Slips in the Word file of the Testament of Job (most of them an older web copy's misreadings of the print: he for
# be, time for the, saving for saying), each checked against Kohler's printed text. 5:14 had lost a line.
JOB_SLIPS = {
    "us all how will I know": "us all? How will I know", "archangel of the God": "archangel of God",
    "the archangel, said": "the archangel said", "that he Lord": "that the Lord",
    "should he firmly": "should be firmly", "who would, take": "who would take", "to time poor": "to the poor",
    "would he robbed": "would be robbed", "servants of the poor.": "servants of the poor?",
    "the bread that it should only have":
        "the bread that it should not be brought to me, insisting that she should only have",
    "live on there for": "live on these for", "behold the memory": "behold your memory",
    "been for nothing 4": "been for nothing? 4", "Behold, her who": "Behold her who", "and Balad,": "and Bildad,",
    "for time first time": "for the first time", "people of the East. 8": "people of the East.” 8",
    "Wither, then": "Whither, then", "challenges it saving": "challenges us saying",
    "And I said, “Upon what": "And he said, “Upon what", "prohibited it, saving": "prohibited it, saying",
    "not he found": "not be found", "darkness. and not": "darkness, and not",
    "and declare unto me": "and you declare unto me", "on account of, the": "on account of the",
    "= Kassia, and": "= Kassia), and", "this, he came He": "this, came He",
    "been taken off the leader": "been taken off, the leader", "man of God? 14": "man of God?” 14",
    "his year’s he": "his years he", "Lord by glory": "Lord be glory",
}


def testament_of_job() -> dict:
    """The Testament of Job in Kaufmann Kohler's translation (Semitic Studies in Memory of Alexander Kohut, 1897;
    the copies online give it to M. R. James, who edited the Greek that year), from TheoDoor's Word file, which
    modernises the thees and thous: its 12 chapters, verses numbered in the running text, Eliphaz's hymn in chapter
    10 line by line. The title leads 1:1 in italics."""
    paras = docx_paragraphs("theodoor_TJb.docx", THEODOOR + "Eaaa-Ttm/A308-TJb.docx")
    title = paras[2][1].strip()
    expect(title.startswith("Book of Job, called Jobab"), f"Job: title {title[:40]!r}")
    chapters, ch = {}, None
    for kind, text in fix_slips(paras[3:], JOB_SLIPS, "Job"):
        m = re.fullmatch(r"\s*Chapter (\d+)\s*", text)
        if kind == "head" and m:
            ch = m.group(1)
            chapters[ch] = ""
        elif kind == "head":
            expect(text.strip() == "Chorus", f"Job: heading {text[:40]!r}")
            chapters[ch] += " @@CHORUS@@"
        elif kind == "line":                          # (a line of the hymn; its half-lines set off by wide spaces)
            chapters[ch] += "\n" + re.sub(r" {2,}", "\n", text.strip())
        else:
            chapters[ch] += " " + text.strip()
    expect(list(chapters) == [str(n) for n in range(1, 13)], f"Job chapters {list(chapters)}")
    book = {}
    for ch, text in chapters.items():
        verses = counted_verses(text.replace("“ ", "“"))
        for v in list(verses):
            if verses[v].endswith("@@CHORUS@@"):       # (the heading over the hymn's last verse)
                verses[v] = verses[v][:-len("@@CHORUS@@")].strip()
                verses[str(int(v) + 1)] = "*Chorus*\n" + verses[str(int(v) + 1)]
        book[ch] = {v: untic(t) for v, t in verses.items()}
    expect("@@" not in json.dumps(book), "Job: a marker left in the text")
    book["1"]["1"] = f"*{title}*\n" + book["1"]["1"]
    return book


# slips in the Word file of the Apocalypse of Abraham: thees its modernising missed, a split word, a stray footnote
# mark and two quotation marks
ABRAHAM_SLIPS = {
    "give thee the proper": "give you the proper", "able-neither": "able neither", "surf ace": "surface",
    "”1 And": "” And", "which dwelleth": "which dwells", "listen to thy voice": "listen to your voice",
    "is in your, so": "is in you, so", "generation of men.": "generation of men.”",
    "“Yet may God reveal": "Yet may God reveal",
}


def apocalypse_of_abraham() -> dict:
    """The Apocalypse of Abraham in G. H. Box's translation (1918), from TheoDoor's Word file, which modernises the
    thees and thous: Box's 32 chapters. He printed no verse numbers, so a verse here is a paragraph of his, or a run
    of whole sentences of a long one; the songs (chapters 7, 17 and 29) are a verse each, line by line. His section
    titles are left out, his brackets (words not in every manuscript) kept; the book's own title leads 1:1."""
    paras = docx_paragraphs("theodoor_AAb.docx", THEODOOR + "Ebbb-Aap/B306-AAb.docx")
    title, chapters, ch = [], {}, None
    for kind, text in fix_slips(paras[2:], ABRAHAM_SLIPS, "Abraham"):
        text = re.sub(r"\s+", " ", text).strip()
        m = re.fullmatch(r"Chapter (\d+)", text)
        if kind == "head":
            if m:
                ch = m.group(1)
                chapters[ch] = []
        elif ch is None:
            title.append(text)
        elif kind == "line" and chapters[ch] and chapters[ch][-1][0] == "line":
            chapters[ch][-1][1] += "\n" + text
        else:
            if text.startswith("See, Abraham, what you have seen"):      # (five lines printed as one)
                text = re.sub(r"(?<=[,.]) (?=(?:And|Go) )", "\n", text)
            chapters[ch].append([kind, text])
    expect(len(title) == 1 and title[0].startswith("The Book of the Revelation of Abraham"), f"Abraham: title {title}")
    expect(list(chapters) == [str(n) for n in range(1, 33)], f"Abraham chapters {list(chapters)}")
    book = {}
    for ch, blocks in chapters.items():
        verses = []
        for kind, text in blocks:
            verses += [text] if kind == "line" else sentence_groups([text])
        book[ch] = {str(n): untic(v) for n, v in enumerate(verses, start=1)}
    book["1"]["1"] = f"*{title[0]}*\n" + book["1"]["1"]
    return book


def lives_of_the_prophets() -> dict:
    """The Lives of the Prophets, adapted from Charles Cutler Torrey's translation (1946), from TheoDoor's Word
    file: a chapter for each of the 23 prophets, his name leading its first verse in italics; verses numbered in
    the running text."""
    paras = docx_paragraphs("theodoor_LtP.docx", THEODOOR + "Eccc-Han/C301-LtP.docx")
    title = paras[2][1].strip()
    expect(title.startswith("The Names of the Prophets"), f"Lives: title {title[:40]!r}")
    names, chunks, ch = {}, {}, None
    for _, text in paras[3:]:
        m = re.fullmatch(r"\s*(\d+) – (.+?)\s*", text)
        if m:
            ch = m.group(1)
            names[ch], chunks[ch] = m.group(2), ""
        else:
            chunks[ch] += " " + text
    expect(list(chunks) == [str(n) for n in range(1, 24)], f"Lives chapters {list(chunks)}")
    book = {}
    for ch, text in chunks.items():
        book[ch] = {v: untic(t.replace("'", "’")) for v, t in counted_verses(text).items()}
        book[ch]["1"] = f"*{names[ch]}*\n" + book[ch]["1"]
    book["1"]["1"] = f"*{title}*\n" + book["1"]["1"]
    return book


def apocalypse_of_elijah() -> dict:
    """The Apocalypse of Elijah, the Akhmimic Coptic text in Anthony Alcock's translation (2013), from TheoDoor's
    Word file. Alcock sets it out by the pages of Steindorff's edition (19 to 44), which break in the middle of
    sentences; here it is one chapter whose verse numbers are those pages, each sentence left whole on the page
    where it begins (so the few words of page 44 end verse 43)."""
    paras = [re.sub(r"\s+", " ", t).strip() for _, t in docx_paragraphs("theodoor_AEj.docx", THEODOOR + "Ebbb-Aap/B304-AEj.docx")]
    expect("Anthony Alcock" in paras[1] and len(paras) == 55 and paras[54] == "The Apocalypse of Elijah",
           f"Elijah: {len(paras)} paragraphs, {paras[1][:40]!r}")
    pages = {}
    for head, text in zip(paras[2:54:2], paras[3:54:2]):
        m = re.fullmatch(r"Page (\d+)", head)
        expect(m is not None, f"Elijah: page heading {head[:40]!r}")
        pages[int(m.group(1))] = re.sub(r"\s+\]", "]", text)
    expect(list(pages) == list(range(19, 45)), f"Elijah pages {list(pages)}")
    for n in range(19, 44):
        if re.search(r"[.!?][”’\])]*$|\[the next line is unreadable\]$", pages[n]):
            continue
        rest = re.match(r".*?[.!?][”’\])]*(?=\s+[A-Z“‘\[(]|$)", pages[n + 1])       # (the sentence's other half)
        expect(rest is not None, f"Elijah: no sentence end on page {n + 1}")
        pages[n] = (pages[n][:-1] if pages[n].endswith("-") else pages[n] + " ") + rest.group(0)   # ("law-" "lessness")
        pages[n + 1] = pages[n + 1][rest.end():].strip()
    expect(not pages.pop(44), "Elijah: page 44 has more than the end of a sentence")
    verses = {str(n): untic(text) for n, text in pages.items()}
    expect(all(verses.values()), "Elijah: an empty page")
    verses["19"] = ("*The Coptic text of Achmim, numbered by the pages of Steindorff’s edition (19 to 43); "
                    "[…] is a gap in the papyrus*\n") + verses["19"]
    return {"1": verses}


def joseph_and_aseneth() -> dict:
    """Joseph and Aseneth in David Cook's translation (in H. F. D. Sparks, The Apocryphal Old Testament, 1984, of
    Philonenko's shorter Greek text), from Mark Goodacre's Aseneth pages, a chapter a page: Cook's 29 chapters and
    his verse numbers ("2. And the top storey"); without the footnotes and their marks."""
    base, book, jumps = "https://markgoodacre.org/wp/aseneth/cook_translation/", {}, {}
    typos = dict.fromkeys(ASENETH_TYPOS, 0)
    for n in range(1, 30):
        page = cached(f"goodacre_cook_{n:02d}.html", base if n == 1 else f"{base}{n}/").decode("utf-8")
        page = re.sub(r"(?is)<(script|style)\b.*?</\1>", "", page)
        head = re.search(r'(?is)<h2 class="wp-block-heading[^>]*>\s*Joseph\s*(?:&amp;|&#0?38;|and)\s*Aseneth:\s*([IVXL]+)\s*</h2>', page)
        expect(head is not None and roman(head.group(1)) == n, f"Aseneth: page {n} is not chapter {n}")
        body = page[head.end():]
        end = next((m for m in (re.search(p, body) for p in (r'(?i)<ol\b[^>]*class="[^"]*footnote',
                                                            r'(?i)<p class="post-nav-links', r"(?i)</div>")) if m), None)
        expect(end is not None, f"Aseneth {n}: no end")
        # paragraphs, and numbered lists (Aseneth's prayer in 12 is one, a verse an item); an indented paragraph or a
        # list item is verse, set line by line, so it starts on a line of its own
        text = ""
        blocks = r'(?is)<p\b([^>]*)>(.*?)</p>|<ol class="wp-block-list"(?: start="(\d+)")?>(.*?)</ol>'
        for m in re.finditer(blocks, body[:end.start()]):
            if m.group(4) is not None:
                for k, item in enumerate(re.findall(r"(?is)<li>(.*?)</li>", m.group(4)), start=int(m.group(3) or 1)):
                    text += f"\n{k}. " + plain(re.sub(r"(?i)<br\s*/?>", " @@BR@@ ", item))
            else:
                para = plain(re.sub(r"(?i)<br\s*/?>", " @@BR@@ ", m.group(2)))
                text += ("\n" if "padding" in m.group(1) else " ") + para
        text = re.sub(r"\s*@@BR@@\s*", "\n", re.sub(r"\s*\[\d+\]", "", text)).strip()
        text = re.sub(r"(?<=\s)(\d{1,2})\.(?=[A-Z])", r"\1. ", text)          # ("5.And")
        for slip, right in ASENETH_SLIPS.get(n, ()):
            expect(text.count(slip) == 1, f"Aseneth {n}: {slip!r}")
            text = text.replace(slip, right)
        for slip, right in ASENETH_TYPOS.items():
            text, k = re.subn(rf"\b{slip}\b", right, text)
            typos[slip] += k
        skips = []
        book[str(n)] = counted_verses(text, stop=".", skips=skips)
        if skips:
            jumps[str(n)] = skips
    expect(all(typos.values()), f"Aseneth: typos not found {[t for t, k in typos.items() if not k]}")
    # (28:13 has no number on the page: not guessed at)
    expect(jumps == {"28": ["12->14"]}, f"Aseneth: verse numbers jump {jumps}")
    # (11 is a single verse in the shorter text: Aseneth's soliloquies are only in the longer)
    expect([n for n, vs in book.items() if len(vs) < 2] == ["11"], f"Aseneth: short chapters")
    return book


# verse numbers the Aseneth pages lost or misprint: 1:13 printed as a second "12."; 4:3, 10:11 and 13:5 have none
# (13:5 is the next of the "Lo, ..." verses; 4:3 and 10:11 open with the next sentence); and a line of 8:10
ASENETH_SLIPS = {
    1: [("yourself? 12. Are you not", "yourself? 13. Are you not")],
    4: [("bride of God. And they took out", "bride of God. 3. And they took out")],
    8: [("this virgin, And renew", "this virgin,\nAnd renew")],                  # (a line break lost)
    10: [("died). And Aseneth took off", "died). 11. And Aseneth took off")],
    13: [("with ashes. Lo, the floor", "with ashes. 5. Lo, the floor")],
}
# typing slips in the Aseneth pages
ASENETH_TYPOS = {"ophanhood": "orphanhood", "jewellry": "jewellery", "Fo lo": "For lo", "irridescent": "iridescent",
                 "Schechem": "Shechem"}


def apocalypse_of_zephaniah() -> dict:
    """The Apocalypse of Zephaniah in O. S. Wintermute's translation (in Charlesworth, The Old Testament
    Pseudepigrapha, 1983), from a page of 2010 kept by the Internet Archive: the Akhmimic text by its 12 chapters and
    verses, then the two shorter remains as chapters of their own -- 13, the quotation in Clement of Alexandria
    (Wintermute's "A"), and 14, the Sahidic fragment (his "B", verses 1-9). The scene headings and his note on the
    lost pages are left out; where pages are missing says so in italics; his <supplied words> are in [brackets]."""
    page = cached("zephaniah_wintermute.html", "http://web.archive.org/web/20100330084339id_/"
                  "http://userpages.burgoyne.com/bdespain/progress/progzeph.htm")
    try:
        page = page.decode("utf-8")
    except UnicodeDecodeError:
        page = page.decode("cp1252")
    page = re.sub(r"\s+", " ", page)
    start, end = re.search(r"(?i)<h3>\s*Clement", page), re.search(r"(?i)<div class=\"?nav\b", page)
    expect(start and end and start.start() < end.start(), "Zephaniah: no text")
    body = re.sub(r"(?is)<h4>.*?</h4>", " ", page[start.start():end.start()])     # (the scene headings)
    body, gaps = re.subn(r"(?is)<i><b>two pages missing</b></i>\s*\(In the missing pages.*?arrival of a boat\.\)",
                         " @@two pages missing@@ ", body)
    body, more = re.subn(r"(?is)<b><i>four pages missing</i></b>", " @@four pages missing@@ ", body)
    expect(gaps == 1 and more == 1, f"Zephaniah: the notes of missing pages ({gaps}, {more})")
    parts = re.split(r"(?is)<h3>(.*?)</h3>", body)
    expect([plain(h) for h in parts[1::2]] == ["Clement, Stromata 5.11.77", "Sahidic fragment", "Akhmimic Text"],
           f"Zephaniah: sections {[plain(h) for h in parts[1::2]]}")

    def text_of(fragment: str) -> str:
        text = re.sub(r"<([^<>@]+)>", r"[\1]", plain(fragment)).replace("… ”", "…”")  # (&lt;thou&gt;: supplied)
        return re.sub(r"\s*@@(.+?)@@\s*", r"\n*\1*", text).strip()

    def verses_of(fragment: str) -> dict:
        pieces = re.split(r"(?i)<sub>(\d+)</sub>", fragment)
        verses = {v: text_of(t) for v, t in zip(pieces[1::2], pieces[2::2])}
        lead = text_of(pieces[0])
        if lead:                                      # ("…" before 8:1, where the text takes up again)
            verses["1"] = f"{lead} {verses['1']}"
        expect(list(verses) == [str(n) for n in range(1, len(verses) + 1)], f"Zephaniah: verses {list(verses)}")
        return verses

    clement, sahidic, akhmimic = parts[2::2]
    book = {}
    chapters = re.split(r"(?i)<b>(\d+)</b>", akhmimic)
    for ch, chunk in zip(chapters[1::2], chapters[2::2]):
        book[ch] = verses_of(chunk)
    expect(list(book) == [str(n) for n in range(1, 13)], f"Zephaniah chapters {list(book)}")
    a = re.split(r"(?i)<b>A</b>", clement)
    b = re.split(r"(?i)<b>B</b>", sahidic)
    expect(len(a) == 2 and len(b) == 2 and not plain(a[0]) and not plain(b[0]), "Zephaniah: fragments A and B")
    book["1"]["1"] = "*The Akhmimic Coptic text, which opens in the middle of a burial*\n" + book["1"]["1"]
    book["13"] = {"1": "*As Clement of Alexandria quotes it (Stromata 5.11.77)*\n" + text_of(a[1])}
    book["14"] = verses_of(b[1])
    book["14"]["1"] = "*The Sahidic Coptic fragment*\n" + book["14"]["1"]
    return book


def main() -> None:
    james = james_more()
    for name, chapters in james.items():
        print(f"  {name}: {sum(map(len, chapters.values()))} verses")
    (ROOT / "data" / "nt_apocrypha" / "james_apocrypha_more.json").write_text(json.dumps(
        {"source": "trans. M. R. James (1924)", "books": james}, ensure_ascii=False, indent=1), encoding="utf-8")
    books = {"2 Baruch": baruch2(), "3 Baruch": baruch3(), "4 Baruch": baruch4(), "Biblical Antiquities": pseudo_philo(),
             "Book of Jasher": jasher(), "Georgian Book of Adam": book_of_adam(),
             "Slavonic Life of Adam and Eve": slavonic_adam(), "Words of Gad the Seer": gad_the_seer()}
    books["Apocalypse of Pseudo-Methodius"], books["Apocalypse of Pseudo-Methodius (Latin)"] = pseudo_methodius()
    books.update({"Joseph and Aseneth": joseph_and_aseneth(), "Apocalypse of Abraham": apocalypse_of_abraham(),
                  "Testament of Job": testament_of_job(), "Lives of the Prophets": lives_of_the_prophets(),
                  "Apocalypse of Zephaniah": apocalypse_of_zephaniah(), "Apocalypse of Elijah": apocalypse_of_elijah()})
    sources = {"2 Baruch": "trans. R. H. Charles (1913); ends at 85:2 (the rest is not online)", "3 Baruch": "trans. H. Maldwyn Hughes (1913)",
               "Biblical Antiquities": "Pseudo-Philo, trans. M. R. James (1917)",
               "4 Baruch": "trans. Robert A. Kraft and Ann Elizabeth Purintun (1972)",
               "Book of Jasher": "anonymous translation (1840; Parry reprint, 1887)",
               "Georgian Book of Adam": "trans. Jean-Pierre Mahé",
               "Slavonic Life of Adam and Eve": "ed. R. H. Charles (1913)",
               "Words of Gad the Seer": "trans. Meir Bar-Ilan",
               "Apocalypse of Pseudo-Methodius": "the Greek, trans. Benjamin Garstad (2012)",
               "Apocalypse of Pseudo-Methodius (Latin)": "the Latin, trans. Benjamin Garstad (2012)",
               "Joseph and Aseneth": "trans. David Cook (1984)",
               "Apocalypse of Abraham": "trans. G. H. Box (1918), lightly modernised",
               "Testament of Job": "trans. Kaufmann Kohler (1897), lightly modernised",
               "Lives of the Prophets": "adapted from Charles Cutler Torrey (1946)",
               "Apocalypse of Zephaniah": "trans. O. S. Wintermute (1983)",
               "Apocalypse of Elijah": "trans. Anthony Alcock (2013), lightly edited"}
    for name, chapters in books.items():
        print(f"  {name}: {len(chapters)} chapters, {sum(map(len, chapters.values()))} verses")
    OUT.write_text(json.dumps({"source": "ed. R. H. Charles (1913)", "book_sources": sources, "books": books},
                              ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
