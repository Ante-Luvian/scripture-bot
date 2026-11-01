"""
The alchemists, in A. E. Waite's English and the old translations sacred-texts.com gives, from its mirror at
neonvagabond.xyz (sacred-texts.com itself blocked this machine after the papyrus was fetched), into
data/esoteric/alchemy.json: Paracelsus, The Hermetic Museum (Waite, 1893), Collectanea Chemica (Waite, 1893) and
the shorter tracts. Each treatise a book.

    python scripts/build_alchemy.py [--list]
"""
import html
import json
import re
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from corpus_clean import clean_corpus  # noqa: E402

CACHE = ROOT / "scripts" / ".cache" / "alchemy"
OUT = ROOT / "data" / "esoteric" / "alchemy.json"
BASE = "https://neonvagabond.xyz/mirrors/sacred-texts/alc/"
UA = {"User-Agent": "ScriptureBotCorpusBuilder/1.0 (Discord bot; a page every two seconds)"}

TRACTS = ["paracel1", "paracel2", "paracel3", "coelum", "tschoudy", "antimony", "catena1", "emerglor", "eudoxus",
          "freher", "goldtrac", "harcanum", "hortulan", "kellystn", "maryprof", "mass", "mirror", "philadel",
          "rbacon2", "turba", "turba2"]
PAGES = TRACTS + [f"hm1/hm1{n:02d}" for n in range(0, 15)] + [f"hm2/hm2{n:02d}" for n in range(0, 15)] + \
    [f"cc/cc{n:02d}" for n in range(0, 24)]


def page(name: str) -> str:
    path = CACHE / (name.replace("/", "_") + ".htm")
    if not path.exists():
        CACHE.mkdir(parents=True, exist_ok=True)
        req = urllib.request.Request(f"{BASE}{name}.htm", headers=UA)
        path.write_bytes(urllib.request.urlopen(req, timeout=60).read())
        time.sleep(2)
    raw = path.read_bytes()
    return raw.decode("utf-8" if b"utf-8" in raw[:3000].lower() else "cp1252", "replace")


def title_of(t: str) -> str:
    m = re.search(r"(?is)<title>(.*?)</title>", t)
    return re.sub(r"\s+", " ", html.unescape(m.group(1))).strip() if m else ""


# book -> (author or collection, the pages it's on). Left out: the title pages, contents and Waite's prefaces; the
# "Glory of the World" extract (emerglor: the Hermetic Museum's whole text has it, the library the Emerald Tablet)
BOOKS = {
    "The Treasure of Treasures for Alchemists": ("Paracelsus", ["paracel1"]),
    "The Tincture of the Philosophers": ("Paracelsus", ["paracel2"]),
    "The Aurora of the Philosophers": ("Paracelsus", ["paracel3"]),
    "Coelum Philosophorum": ("Paracelsus", ["coelum"]),
    "Alchemical Catechism": ("Baron Tschoudy", ["tschoudy"]),
    "The Triumphal Chariot of Antimony": ("Basil Valentine", ["antimony"]),
    "The Golden Chain of Homer": ("anonymous", ["catena1"]),
    "The Six Keys of Eudoxus": ("anonymous", ["eudoxus"]),
    "Freher's Process in the Philosophical Work": ("Dionysius Andreas Freher", ["freher"]),
    "The Golden Tractate of Hermes Trismegistus": ("Hermes", ["goldtrac"]),
    "The Hermetic Arcanum": ("anonymous", ["harcanum"]),
    "Hortulanus' Commentary on the Emerald Tablet": ("Hortulanus", ["hortulan"]),
    "The Stone of the Philosophers": ("Edward Kelly", ["kellystn"]),
    "The Practice of Mary the Prophetess": ("Mary the Prophetess", ["maryprof"]),
    "An Alchemical Mass": ("Melchior Cibinensis", ["mass"]),
    "The Mirror of Alchemy": ("Roger Bacon", ["mirror"]),
    "On the Philadelphian Gold": ("anonymous", ["philadel"]),
    "Tract on the Tincture and Oil of Antimony": ("Roger Bacon", ["rbacon2"]),
    "Turba Philosophorum": ("anonymous", ["turba", "turba2"]),
    "The Golden Tract": ("The Hermetic Museum", ["hm1/hm104"]),
    "The Golden Age Restored": ("The Hermetic Museum", ["hm1/hm105"]),
    "The Sophic Hydrolith": ("The Hermetic Museum", ["hm1/hm106"]),
    "A Demonstration of Nature": ("The Hermetic Museum", ["hm1/hm107"]),
    "Flamel's Short Tract": ("The Hermetic Museum", ["hm1/hm108"]),
    "The Only True Way": ("The Hermetic Museum", ["hm1/hm109"]),
    "The Glory of the World": ("The Hermetic Museum", ["hm1/hm110"]),
    "A Tract of Great Price": ("The Hermetic Museum", ["hm1/hm111"]),
    "The Book of Alze": ("The Hermetic Museum", ["hm1/hm112"]),
    "The Book of Lambspring": ("The Hermetic Museum", ["hm1/hm113"]),
    "The Golden Tripod": ("The Hermetic Museum", ["hm1/hm114"]),
    "The Ordinal of Alchemy": ("The Hermetic Museum", ["hm2/hm202"]),
    "The Testament of Cremer": ("The Hermetic Museum", ["hm2/hm203"]),
    "The New Chemical Light": ("The Hermetic Museum", ["hm2/hm204", "hm2/hm205"]),
    "An Open Entrance to the Closed Palace of the King": ("The Hermetic Museum", ["hm2/hm206"]),
    "A Subtle Allegory Concerning the Secrets of Alchemy": ("The Hermetic Museum", ["hm2/hm207"]),
    "The Metamorphosis of Metals": ("The Hermetic Museum", ["hm2/hm209"]),
    "A Brief Guide to the Celestial Ruby": ("The Hermetic Museum", ["hm2/hm210"]),
    "The Fount of Chemical Truth": ("The Hermetic Museum", ["hm2/hm211"]),
    "Helvetius' Golden Calf": ("The Hermetic Museum", ["hm2/hm212"]),
    "The All-Wise Doorkeeper": ("The Hermetic Museum", ["hm2/hm213"]),
    "The Secret of the Immortal Liquor Called Alkahest": ("Collectanea Chemica", ["cc/cc03"]),
    "Aurum Potabile": ("Collectanea Chemica", ["cc/cc04"]),
    "The Oil of Sulphur": ("Collectanea Chemica", ["cc/cc05"]),
    "The Stone of the Philosophers and the First Matter": ("Collectanea Chemica",
                                                           [f"cc/cc{n:02d}" for n in range(8, 22)]),
    "The Bosom Book of Sir George Ripley": ("Collectanea Chemica", ["cc/cc22"]),
    "Preparations of the Sophic Mercury": ("Collectanea Chemica", ["cc/cc23"]),
}
# a heading that begins a chapter: "CHAPTER III.", "Section I", "THE FIRST KEY", "The Third Dictum", "PART II"
CHAPTER = re.compile(r"(?i)^(?:chapter|section|part|book|dictum|sermon|canon)\b\.?\s*[ivxlc\d]+\b|^the [\w-]+ (?:key|"
                     r"dictum|chapter|section|part|treatise|sermon|canon)\b|^(?:first|second|third|fourth|fifth|"
                     r"sixth|seventh|eighth|ninth|tenth|eleventh|twelfth) (?:key|dictum|chapter|part|treatise|canon)\b")


def body_of(t: str) -> str:
    """A sacred-texts page's text, as HTML with only its paragraphs and headings: no navigation, page numbers,
    footnotes or their markers, pictures' captions."""
    t = re.sub(r"(?is)<head.*?</head>|<script.*?</script>|<style.*?</style>", " ", t)
    t = re.split(r"(?is)<h\d[^>]*>\s*Footnotes\s*</h\d>", t)[0]
    t = re.sub(r"(?is)<a name=\"?page_\w+\"?>.*?</a>|<font size=\"?1\"? color=\"?green\"?>.*?</font>", " ", t)
    t = re.sub(r"(?is)<a href=\"?#fn_\w+\"?>.*?</a>|<a name=\"?fr_\w+\"?>.*?</a>", "", t)
    t = re.sub(r"(?is)Click to enlarge", " ", t)
    t = re.sub(r"(?is)^.*?(?=<h\d)", "", t, count=1)                    # (the page's header, before the title)
    t = re.split(r"(?is)<hr[^>]*>\s*(?:<center>)?\s*(?:<font[^>]*>)?\s*(?:<a href=\"[^\"]*\">)?\s*Next", t)[0]
    return t


def text(fragment: str) -> str:
    s = re.sub(r"(?is)<(i|em)>(\s*)(.*?)(\s*)</\1>",
               lambda m: f"{m.group(2)}*{m.group(3)}*{m.group(4)}" if m.group(3).strip() else " ", fragment)
    s = html.unescape(re.sub(r"<[^>]+>", " ", s)).replace("\xa0", " ")
    s = re.sub(r"\s+", " ", s).strip()
    s = re.sub(r"\*(\s*)\*", r"\1", s)
    s = re.sub(r"\s+([,.;:!?])", r"\1", s)
    s = re.sub(r"^p\. \d+\s*", "", s)
    return s if s.count("*") % 2 == 0 else s.replace("*", "")


def heading_label(s: str) -> str:
    s = s.strip(" .:_")
    if s.isupper():
        s = re.sub(r"[A-Za-z][A-Za-z'’]*", lambda m: m.group(0)[0] + m.group(0)[1:].lower(), s)
        s = re.sub(r"(?<= )(Of|The|And|In|To|A|An|On|For|With|By)(?= )", lambda m: m.group(1).lower(), s)
    # (a division's numeral stays a numeral: "Chapter II", not "Chapter Ii")
    return re.sub(r"(?i)\b(chapter|part|section|book|canon|sermon|dictum)\s+([ivxlc]+)\b",
                  lambda m: f"{m.group(1)} {m.group(2).upper()}", s)


def capitals(s: str) -> bool:
    """Mostly capitals: a title line ("By PHILIPPUS THEOPHRASTUS PARACELSUS. THE SCIENCE AND NATURE...")."""
    letters = [c for c in s if c.isalpha()]
    return len(letters) >= 4 and sum(c.isupper() for c in letters) / len(letters) > 0.7


def book(pages: list, title: str = "") -> dict:
    """{chapter: {verse: text}}: a chapter at each heading CHAPTER takes, the other headings italic lines in it; with
    none, chapter "1". The headings before the first paragraph (the title block) are left out."""
    chapters, current, started = {}, None, False
    for name in pages:
        t = body_of(page(name))
        for part in re.split(r"(?is)(<h\d[^>]*>.*?</h\d>)", t):
            if re.match(r"(?is)<h\d", part):
                label = heading_label(text(part))
                if not label or re.fullmatch(r"[_\-\s.]*|\[?\d{4}\]?", label):
                    continue
                if CHAPTER.match(label):
                    current = str(len(chapters) + 1)
                    chapters[current] = [f"*{label}*"]
                    started = True
                elif started and current:
                    chapters[current].append(f"*{label}*")
                continue
            for p in re.split(r"(?i)<p\b[^>]*>|<br\s*/?>\s*<br\s*/?>|</?blockquote[^>]*>", part):
                s = text(p)
                if not s or re.fullmatch(r"[\W\d_]*", s):
                    continue
                if re.fullmatch(r"(?i)notes\.?", s):           # (Waite's notes, to the page's end)
                    break
                short = len(s.split()) <= 12
                label = heading_label(re.sub(r"(?<=[A-Za-z.])\s?\d{1,2}$", "", s))   # ("MONARCHIA. 1")
                s = re.split(r"\s*Sacred Texts \| ", s)[0].strip()     # (the site's footer: "« Previous...")
                if not s or re.fullmatch(r"(?i)\*?(?:finis|the end|end of volume \w+)\.?\*?", s):
                    continue
                if not started and (s.rstrip(".").lower() == title.lower() or short and s.startswith("By ")):
                    continue                           # (the book's own title, its byline)
                # (Kirkringus's heads in the Chariot of Antimony: "1. [GOD TO BE FIRST INVOKED]", "[DOCTORS REPREHENDED]")
                numbered = re.fullmatch(r"(?:\d{1,3}\.\s*)?\[([A-Z][A-Z ,;:'’&-]+)\]", s)
                if short and CHAPTER.match(label) or numbered:   # (a division set as a paragraph: "The First Dictum.")
                    current = str(len(chapters) + 1)
                    chapters[current] = [f"*{heading_label(numbered.group(1)) if numbered else label}*"]
                    started = True
                    continue
                if short and (capitals(s.replace("*", "")) or re.fullmatch(r"\[[^\]]+\]", s)) \
                        or not started and (capitals(s) or len(s.split()) <= 5):
                    if started and current:            # (a heading; the title block before the text goes)
                        chapters[current].append(f"*{label.strip('[]')}*")
                    continue
                if current is None:
                    current = "1"
                    chapters[current] = []
                started = True
                chapters[current].append(s)
    out = {}
    for c, ps in chapters.items():
        merged = []
        for p in ps:                                   # (a heading line leads the paragraph after it)
            if merged and re.fullmatch(r"\*[^*\n]+\*(?:\n\*[^*\n]+\*)*", merged[-1]):
                merged[-1] += "\n" + p
            else:
                merged.append(p)
        if merged and not re.fullmatch(r"\*[^*\n]+\*(?:\n\*[^*\n]+\*)*", merged[0] if len(merged) > 1 else ""):
            pass
        out[c] = {str(i + 1): p for i, p in enumerate(merged)}
    return {c: vs for c, vs in out.items() if vs}


def main() -> None:
    books, sources = {}, {}
    for name, (who, pages) in BOOKS.items():
        books[name] = book(pages, name)
        sources[name] = (f"{who}, trans. A. E. Waite (1893)" if who in ("The Hermetic Museum", "Collectanea Chemica")
                         else f"{who}, trans. A. E. Waite (1894)" if who == "Paracelsus" else
                         "anonymous" if who == "anonymous" else who)
    payload = {"source": "alchemical treatises in English", "books": books, "book_sources": sources}
    clean_corpus(payload, "esoteric/alchemy.json")
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    for name, chs in payload["books"].items():
        words = sum(len(v.split()) for c in chs.values() for v in c.values())
        print(f"  {name}: {len(chs)} chapters, {words:,} words")


if __name__ == "__main__" and "--list" not in sys.argv:
    main()

if __name__ == "__main__" and "--list" in sys.argv:
    for name in PAGES:
        try:
            t = page(name)
        except Exception as e:
            print(name, "ERR", e)
            continue
        heads = [re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", "", m.group(2)))).strip()[:50]
                 for m in re.finditer(r"(?is)<h([1-5])[^>]*>(.*?)</h\1>", t)]
        words = len(re.sub(r"<[^>]+>", " ", re.sub(r"(?is)<head.*?</head>", "", t)).split())
        print(f"{name:12} {words:6} | {title_of(t)[:60]} | {heads[:6]}")
