"""
The Toledot Yeshu ("The Life of Jesus"), the medieval Jewish counter-gospel, in its two best-known recensions, into
data/jewish/toledot_yeshu.json (2026-11-10):

    Toledot Yeshu -- the version J. C. Wagenseil printed in 1681, trans. G. W. Foote and J. M. Wheeler as "The
        Jewish Life of Christ" (1885), from the Freethought Archives (ftarchives.net/foote/toldoth/): its chapters
        and numbered verses; their notes and the marks to them left out. (They left a few passages in Latin, as
        translators of the time did with sexual matter; those stay as printed.)
    Toledot Yeshu: Strasbourg Manuscript -- the Strasbourg recension, trans. G. R. S. Mead in "Did Jesus Live 100
        B.C.?" (1903), as Jason Colavito's site reprints it: its twelve sections, a paragraph a verse; Mead's and
        the site's surrounding discussion left out.

    python scripts/build_toledot.py
"""
import html
import json
import re
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CACHE = Path(__file__).resolve().parent / ".cache" / "toledot"
OUT = ROOT / "data" / "jewish" / "toledot_yeshu.json"
UA = {"User-Agent": "ScriptureBot corpus builder (a personal Discord bot)"}
ROMAN = {"I": 1, "V": 5, "X": 10, "L": 50}


def expect(ok: bool, message: str) -> None:
    if not ok:
        raise SystemExit(f"unexpected source layout: {message}")


def roman(numeral: str) -> int:
    values = [ROMAN[c] for c in numeral]
    return sum(-v if i + 1 < len(values) and v < values[i + 1] else v for i, v in enumerate(values))


def fetch(url: str) -> str:
    CACHE.mkdir(parents=True, exist_ok=True)
    f = CACHE / re.sub(r"\W+", "_", url.split("//", 1)[1])
    if not f.exists():
        f.write_bytes(urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60).read())
        time.sleep(1)
    raw = f.read_bytes()
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw.decode("cp1252")


def text_of(fragment: str) -> str:
    text = html.unescape(re.sub(r"<[^>]+>", " ", fragment)).replace("\xa0", " ").replace("​", "")
    text = re.sub(r"\s+", " ", text).strip()
    return re.sub(r"(?<=\w)\s+(?=[,.;:!?])", "", text)


def wagenseil() -> dict:
    """Foote and Wheeler's chapters, page by page (tj1.htm, tj2.htm... to the last "Next Section")."""
    book, n = {}, 1
    while True:
        page = fetch(f"https://ftarchives.net/foote/toldoth/tj{n}.htm")
        page = re.sub(r'(?is)<font size="-1">\s*<a name="[^"]*"></a>.*?</font>', "", page)       # (note marks)
        page = re.sub(r'(?is)<a name="[^"]*">\s*</a>', "", page)                                # (page anchors)
        m = re.search(r"(?is)<h3>\s*CHAPTER ([IVXL]+)\.?\s*</h3>", page)
        expect(m is not None, f"tj{n}: no chapter heading")
        body = page[m.end():]
        body = re.split(r'(?is)<hr\b|<a href="tj\d+\.htm">\s*Next', body)[0]
        verses, current = {}, 0
        for chunk in re.split(r"(?i)<p\b[^>]*>", body):
            text = text_of(chunk)
            if not text:
                continue
            vm = re.match(r"(\d{1,3})\.\s*", text)
            if vm and int(vm.group(1)) == current + 1:
                current += 1
                verses[str(current)] = text[vm.end():]
            elif not verses:
                current = 1
                verses["1"] = text
            else:
                verses[str(current)] += " " + text
        verses = {k: re.sub(r"\s*\[\d+:\d+\]\s*", " ", v).strip() for k, v in verses.items()}   # (note marks)
        verses = {k: v.replace("deserveth the worst. 18. Then they narrated", "deserveth the worst. 13. Then they narrated")
                  for k, v in verses.items()}                                      # (II's 13, misprinted "18.")
        # (a verse run on into the one before: "...crushed his head. 55. So perish all thine enemies")
        changed = True
        while changed:
            changed = False
            for k in list(verses):
                nxt = str(int(k) + 1)
                mm = re.search(rf"(?<=[.!?;:,'\"’”])\s+{nxt}\.\s+(?=[A-Z])", verses[k])
                if nxt not in verses and mm:
                    verses[k], verses[nxt] = verses[k][:mm.start()].strip(), verses[k][mm.end():].strip()
                    changed = True
        book[str(roman(m.group(1)))] = dict(sorted(verses.items(), key=lambda kv: int(kv[0])))
        if not re.search(rf'href="tj{n + 1}\.htm"', page):            # (IV's next is the appendix, tj5ap.htm)
            break
        n += 1
    # (four chapters; then their appendix, Lightfoot's extracts of the Talmud on Jesus, not part of the Toledot)
    expect(list(book) == ["1", "2", "3", "4"], f"Wagenseil chapters {list(book)}")
    return book


def strasbourg() -> dict:
    """Mead's twelve sections ("2. His mother gave him to a teacher"), from his heading to the next, a paragraph
    a verse."""
    page = fetch("https://www.jasoncolavito.com/toledot-yeshu.html")
    i = page.find("A JEWISH LIFE OF JESUS")
    expect(i > 0, "no Strasbourg heading")
    end = page.find("The First Notices of the Toledot", i)
    expect(end > i, "no end of the Strasbourg text")
    seg = page[page.find(">", i) + 1:end]
    seg = re.sub(r"(?i)</?(?:p|div)\b[^>]*>|<br\s*/?>", "\n", seg)          # (paragraphs and line breaks alike)
    paras = [text_of(c) for c in seg.split("\n")]
    paras = [p for p in paras if p and not re.fullmatch(r"[\W\d]*", p)]
    book, current = {}, "1"
    for p in paras:
        m = re.match(r"(\d{1,2})\.\s+", p)
        if m and int(m.group(1)) == int(current) + 1:
            current = m.group(1)
            p = p[m.end():]
        book.setdefault(current, {})
        book[current][str(len(book[current]) + 1)] = p
    expect(list(book) == [str(i) for i in range(1, 13)], f"Strasbourg sections {list(book)}")
    return book


def main() -> None:
    books = {"Toledot Yeshu": wagenseil(), "Toledot Yeshu: Strasbourg Manuscript": strasbourg()}
    sources = {"Toledot Yeshu": "Wagenseil's text, trans. G. W. Foote and J. M. Wheeler (1885)",
               "Toledot Yeshu: Strasbourg Manuscript": "trans. G. R. S. Mead (1903)"}
    for name, chapters in books.items():
        print(f"  {name}: {len(chapters)} chapters, {sum(map(len, chapters.values()))} verses")
    OUT.write_text(json.dumps({"source": "various translators", "book_sources": sources, "books": books},
                              ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
