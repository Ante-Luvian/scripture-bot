"""
Budge's "The Paradise, or Garden of the Holy Fathers" (1907), both volumes, from Wikisource's transcription
(https://en.wikisource.org/wiki/The_Paradise), into data/patristics/paradise_of_the_fathers.json:

  python scripts/build_paradise.py          fetch every page (cached in scripts/.cache/paradise_ws_html), build

The pages are fetched as Wikisource renders them (Volume I's text is transcluded from its proofread scan
pages), and only taken apart here: the header, page numbers and footnote marks left out, paragraphs and
italics kept. Budge's introduction and preface (his own essays) are left out.
"""
import json
import re
import time
import urllib.parse
import urllib.request
from html import unescape
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "scripts" / ".cache" / "paradise_ws_html"
OUT = ROOT / "data" / "patristics" / "paradise_of_the_fathers.json"
UA = {"User-Agent": "ScriptureBot-library-builder/1.0"}
API = "https://en.wikisource.org/w/api.php"


def page(title: str) -> str:
    path = CACHE / (title.replace("/", "__") + ".html")
    if not path.exists():
        CACHE.mkdir(parents=True, exist_ok=True)
        url = f"{API}?action=parse&format=json&prop=text|displaytitle&redirects=1&disablelimitreport=1&page={urllib.parse.quote(title)}"
        for attempt in range(6):
            try:
                data = json.load(urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=90))
                break
            except Exception as e:
                if attempt == 5:
                    raise SystemExit(f"{title}: {e}")
                time.sleep(10 * (attempt + 1))
        if "parse" not in data:
            raise SystemExit(f"{title}: {data.get('error')}")
        got = re.sub(r"<[^>]+>", "", data["parse"].get("displaytitle", ""))
        want = title.replace("The Life of St. Anthony", "")
        if got and not (got == title or got.endswith(title.split("/")[-1])):
            raise SystemExit(f"{title}: Wikisource answered with {got!r}")
        path.write_text(data["parse"]["text"]["*"], encoding="utf-8")
        time.sleep(1)
    return path.read_text(encoding="utf-8")


def _without_divs(html: str, cls: str) -> str:
    """The HTML without each <div> whose class matches `cls`, nested divs and all."""
    while True:
        m = re.search(rf'<div[^>]*class="[^"]*(?:{cls})[^"]*"', html)
        if not m:
            return html
        depth, i = 0, m.start()
        for t in re.finditer(r"<div\b|</div>", html[m.start():]):
            depth += 1 if t.group(0) == "<div" else -1
            if depth == 0:
                i = m.start() + t.end()
                break
        html = html[:m.start()] + html[i:]


class _Text(HTMLParser):
    """Paragraphs of a rendered page: the Wikisource header, page numbers, footnote marks and notes left
    out; italics as *...*."""
    SKIP = re.compile(r"ws-header|ws-noexport|noprint|reference|mw-cite|mw-references|ambox|wst-toc|mw-editsection")
    BLOCK = {"p", "div", "h1", "h2", "h3", "h4", "h5", "h6", "li", "dd", "dt", "tr", "table", "center"}
    VOID = {"br", "img", "hr", "meta", "link", "input", "wbr", "col", "area", "source"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack, self.skip, self.paras, self.cur = [], 0, [], []

    def handle_starttag(self, tag, attrs):
        if tag in ("style", "script"):
            self.stack.append((tag, True)); self.skip += 1; return
        if tag in self.VOID:
            if tag == "br" and not self.skip:
                self.cur.append(" ")
            return
        skip = bool(self.SKIP.search(dict(attrs).get("class", "") or "")) or (tag == "sup")
        self.stack.append((tag, skip))
        if skip:
            self.skip += 1
        elif tag in self.BLOCK:
            self.flush()
        elif tag in ("i", "em") and not self.skip:
            self.cur.append("*")

    def handle_endtag(self, tag):
        while self.stack:
            t, skip = self.stack.pop()
            if skip:
                self.skip -= 1
            elif t in ("i", "em") and not self.skip:
                self.cur.append("*")
            if t in self.BLOCK and not self.skip:
                self.flush()
            if t == tag:
                break

    def handle_data(self, data):
        if not self.skip:
            self.cur.append(data)

    def flush(self):
        text = re.sub(r"\s+", " ", "".join(self.cur)).strip()
        text = re.sub(r"\*\s*\*", " ", text)                         # (empty italics)
        if text.count("*") % 2:
            text = text.replace("*", "")
        else:                                                        # ("*or *peace" -> "*or* peace")
            text = re.sub(r"\*(\s*)([^*]*?)(\s*)\*", lambda m: f"{m.group(1)}*{m.group(2)}*{m.group(3)}", text)
            text = re.sub(r"\s{2,}", " ", text)
        if text and text not in ("*", "&#8203;", "​"):
            self.paras.append(text.replace("​", "").strip())
        self.cur = []


def paragraphs(title: str) -> list:
    p = _Text()
    html = re.sub(r"(?s)<style.*?</style>", "", page(title))
    p.feed(_without_divs(html, r"ws-header|ambox|wst-toc"))
    p.flush()
    return [re.sub(r"\*\s+([^*]*?)\s*\*", r"*\1*", t) for t in p.paras if t]


# ── the works ───────────────────────────────────────────────────────────────

def numbered(paras: list, first: int) -> "tuple[dict, int]":
    """Volume II: {saying: text}, a saying opening with its number ("230. A brother..."); a heading or an
    unnumbered first paragraph leads the saying after it. Returns the sayings and the next number."""
    out, lead, n = {}, [], first - 1
    for t in paras:
        m = re.match(r"^(\d{1,4})\.\s+(.*)", t, re.S)
        if m and int(m.group(1)) > n:
            n = int(m.group(1))
            out[str(n)] = "\n".join(lead + [m.group(2)])
            lead = []
        elif not out or lead or _heading(t):
            lead.append(f"*{t.strip('*')}*" if _heading(t) else t)
            if not _heading(t) and not out:              # (the first saying, printed without its number)
                n += 1
                out[str(n)] = "\n".join(lead)
                lead = []
        else:
            out[str(n)] += "\n" + t                       # (a saying of more than one paragraph)
    return out, n + 1


def _heading(t: str) -> bool:
    return bool(re.match(r"^\*?(Chapter|Book|Here (begin|end)|Questions (And|By|of)|Appendix$)\b", t)) and len(t) < 260


def prose(paras: list) -> dict:
    """A narrative chapter: its paragraphs as verses, any heading leading the first."""
    out, lead = {}, []
    for t in paras:
        if _heading(t) or (len(t) < 140 and not re.search(r"[.;:,?!]”?$", t.strip("*"))):
            lead.append(f"*{t.strip('*')}*")
            continue
        out[str(len(out) + 1)] = "\n".join(lead + [t])
        lead = []
    return out


V1, V2 = "The Paradise/Volume 1", "The Paradise/Volume 2"

# Slips in the Wikisource transcription, each checked against the University of Toronto scan of the book
# (archive.org theparadiseorgar00unkwuoft): (book, chapter, verse, as transcribed, as printed). Most are words
# the printer set so tight that their space is a hair's breadth; "ot" and "thyselt" are an f broken in the
# type. Left as printed: Budge's own "undertand" (1:575). The build stops if one no longer matches.
CORRECTIONS = [
    ("Sayings of the Desert Fathers", "1", "444", "And Of Bow A Man", "And Of How A Man"),   # (black letter h)
    ("Sayings of the Desert Fathers", "1", "444", "Himself The Interior Of", "Himself The Inferior Of"),
    ("Sayings of the Desert Fathers", "1", "49", "man tohold his", "man to hold his"),
    ("Sayings of the Desert Fathers", "1", "89", "layest aheavy load", "layest a heavy load"),
    ("Sayings of the Desert Fathers", "1", "179", "give theecounsel", "give thee counsel"),
    ("Sayings of the Desert Fathers", "1", "248", "be notnegligent", "be not negligent"),
    ("Sayings of the Desert Fathers", "1", "316", "these boders", "these borders"),
    ("Sayings of the Desert Fathers", "1", "390", "an oldman", "an old man"),
    ("Sayings of the Desert Fathers", "1", "524", "the Bishopheard", "the Bishop heard"),
    ("Sayings of the Desert Fathers", "2", "37", "one ot the old men", "one of the old men"),
    ("Sayings of the Desert Fathers", "2", "11", "‘Whatdost Thou", "‘What dost Thou"),
    ("Sayings of the Desert Fathers", "2", "220", "raised upto heaven", "raised up to heaven"),
    ("Sayings of the Desert Fathers", "2", "378", "“Whatshall I do", "“What shall I do"),
    ("Sayings of the Desert Fathers", "2", "603", "Triumpbant", "Triumphant"),      # (h read as b in black letter)
    ("Sayings of the Desert Fathers", "2", "630", "wings ot ravens", "wings of ravens"),
    ("Sayings of the Desert Fathers", "2", "630", "state ot sluggishness", "state of sluggishness"),
    ("Sayings of the Desert Fathers", "2", "680", "through transagression", "through transgression"),
    ("Sayings of the Desert Fathers", "2", "381", "offended thyselt", "offended thyself"),
    ("Sayings of the Desert Fathers", "2", "413", "The Emperor said unto for ye are saved and freed from thim, “Verily blessed "
     "are ye, he cares of the world,", "The Emperor said unto him, “Verily blessed are ye, for ye are saved and freed from "
     "the cares of the world,"),
    ("Sayings of the Desert Fathers", "2", "416", "man sawthem, hewailed andcried,", "man saw them, he wailed and cried,"),
    ("Sayings of the Desert Fathers", "2", "438", "which aresent unto", "which are sent unto"),
    ("Sayings of the Desert Fathers", "2", "536", "a wormeaten beam", "a worm-eaten beam"),
    ("Sayings of the Desert Fathers", "2", "575", "the holymen who", "the holy men who"),
    ("Sayings of the Desert Fathers", "2", "619", "certain ot the Fathers", "certain of the Fathers"),
    ("Sayings of the Desert Fathers", "2", "656", "The demongoeth", "The demon goeth"),
    ("Sayings of the Desert Fathers", "2", "691", "money befaithful", "money be faithful"),
    ("Sayings of the Desert Fathers", "2", "705", "preventethit from", "preventeth it from"),
    ("Sayings of the Desert Fathers", "2", "706", "sign of Hismerit", "sign of His merit"),
    # Volume I (checked on Wikisource's own scan, Theparadiseoftheholyfathers.djvu): "ove" has lost its l in the
    # printing; "excel-lence" lost one at the line break; the drop capitals ran into the next word.
    ("The Paradise of Palladius", "0.2", "1", "manifestation and ove,", "manifestation and love,"),
    ("The Rule of Pachomius", "9", "1", "great excelence", "great excellence"),
    ("The Life of St. Anthony (Budge)", "1", "31", "(Psam 118:10)", "(Psalm 118:10)"),
    ("The Paradise of Palladius", "29", "1", "ACERTAIN", "A CERTAIN"),
    ("The Paradise of Palladius", "59", "1", "ACERTAIN", "A CERTAIN"),
    ("The Paradise of Palladius: Book II", "18", "4", "ACERTAIN", "A CERTAIN"),
    ("The Paradise of Palladius: Book II", "19", "1", "ACERTAIN", "A CERTAIN"),
    ("The Paradise of Palladius: Book II", "27", "1", "ACERTAIN", "A CERTAIN"),
    ("The Paradise of Palladius: Book II", "31", "1", "ACERTAIN", "A CERTAIN"),
    ("The Paradise of Palladius: Book II", "37", "1", "ACERTAIN", "A CERTAIN"),
    ("The Paradise of Palladius: Book II", "39", "1", "ACERTAIN", "A CERTAIN"),
    ("The History of the Monks of Egypt", "2", "1", "ISAW", "I SAW"),
    ("The Paradise of Palladius: Book II", "9", "1", "IUSED", "I USED"),
]


def correct(books: dict) -> None:
    for book, chapter, verse, was, now in CORRECTIONS:
        text = books[book][chapter][verse]
        if was not in text:
            raise SystemExit(f"correction no longer matches: {book} {chapter}:{verse} {was!r}")
        books[book][chapter][verse] = text.replace(was, now)


def volume_2() -> dict:
    book1, nxt = {}, 1
    for c in range(1, 15):
        sayings, nxt = numbered(paragraphs(f"{V2}/Book 1/Chapter {c}"), nxt)
        book1.update(sayings)
    book2, nxt = {}, 1
    for t in ("Questions And Answers On The Rule Of Life Of The Holy Men",
              "Questions By The Pupils And The Answers To The Same By The Holy Fathers And Monks",
              "Questions And Answers On The Vision Of The Mind", "Appendix"):     # (604-706)
        sayings, nxt = numbered(paragraphs(f"{V2}/Book 2/{t}"), nxt)
        book2.update(sayings)
    return {"1": book1, "2": book2}


def chapters(base: str, n: int, extra: dict = None) -> dict:
    out = {str(c): prose(paragraphs(f"{base}/Chapter {c}")) for c in range(1, n + 1)}
    for key, title in (extra or {}).items():
        out[key] = prose(paragraphs(title))
    return out


def volume_1() -> dict:
    pal = f"{V1}/Book 1/The Paradise of Palladius"
    palladius = {f"0.{c}": prose(paragraphs(f"{pal}/Chapter {c}")) for c in range(1, 4)}
    palladius.update({str(h): prose(paragraphs(f"{pal}/The Histories of the Holy Men/History {h}")) for h in range(1, 69)})
    return {
        "The Life of St. Anthony (Budge)": {"1": prose(paragraphs(f"{V1}/The Life of St. Anthony"))},
        "The Paradise of Palladius": palladius,
        "The Paradise of Palladius: Book II": chapters(f"{V1}/Book 2", 44),
        "The Rule of Pachomius": chapters(f"{V1}/The Rule of Pachomius at Tabenna", 21,
                                          {"22": f"{V1}/The Rule of Pachomius at Tabenna/Further Remarks by Palladius"}),
        "The History of the Monks of Egypt": chapters(f"{V1}/The history of the Monks", 30),
    }


def main() -> None:
    books = {"Sayings of the Desert Fathers": volume_2(), **volume_1()}
    correct(books)
    for name, chs in books.items():
        print(f"{name:42} {len(chs):4} chapters {sum(len(v) for v in chs.values()):6} verses "
              f"{sum(len(t) for v in chs.values() for t in v.values()) // 1000:6} kB")
    s = books["Sayings of the Desert Fathers"]
    for b, vs in s.items():
        nums = sorted(map(int, vs))
        print(f"  Sayings book {b}: {nums[0]}-{nums[-1]}, missing {sorted(set(range(1, nums[-1] + 1)) - set(nums))[:30]}")
    payload = {"source": "trans. E. A. Wallis Budge (1907)",
               "books": books}
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
