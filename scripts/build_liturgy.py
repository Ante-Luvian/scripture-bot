"""
Builds data/liturgy/chrysostom.json: the Divine Liturgy of St John Chrysostom in English,
for !liturgy, a page at a time with the part of the service each page is in.

    python scripts/build_liturgy.py

Text: "Service of the Divine and Sacred Liturgy of our Holy Father John Chrysostom"
(London: Joseph Masters, 1866; "translated from the Greek according to the Euchologion,
and compared with the Slavonic"), on Wikisource. Its rubrics, printed in red italics, stay
italic; the page numbers of the scan are dropped.
"""
import html
import json
import re
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CACHE = Path(__file__).resolve().parent / ".cache" / "liturgy" / "chrysostom_1866.html"
OUT = ROOT / "data" / "liturgy" / "chrysostom.json"
PAGE_TITLE = "Service of the Divine and Sacred Liturgy of our Holy Father John Chrysostom/Liturgy"
SOURCE = ("Service of the Divine and Sacred Liturgy of our Holy Father John Chrysostom (London: Joseph Masters, "
          "1866), on Wikisource")
UA = {"User-Agent": "ScriptureBotCorpusBuilder/1.0 (Discord bot; low-volume one-off import)"}
PAGE = 1800                       # characters a page (Discord's embed holds 4096; shorter reads better)

# the parts of the service, each starting at the first paragraph that contains its words
SECTIONS = [
    ("Bless, Master.", "The Great Litany"),
    ("Prayer of the first Antiphon", "The Antiphons"),
    ("Prayer of the Entrance of the Holy Gospel", "The Little Entrance"),
    ("Master, bless the time of the Trisagion", "The Trisagion"),
    ("the Prokimenon of the Epistle", "The Epistle and the Gospel"),
    ("Let us all say, with our whole heart", "The Litany after the Gospel"),
    ("Catechumens, pray to the Lord", "The Litany of the Catechumens"),
    ("We, who mystically represent the Cherubim", "The Cherubic Hymn and the Great Entrance"),
    ("I believe in One God", "The Creed"),
    ("Let us stand worthily, let us stand with fear", "The Anaphora"),
    ("Our Father, who art in the heavens", "The Lord's Prayer"),
    ("Holy things for holy persons", "Holy Communion"),
    ("Let us depart in peace", "The Dismissal"),
]


def page_html() -> str:
    if not CACHE.exists():
        CACHE.parent.mkdir(parents=True, exist_ok=True)
        url = ("https://en.wikisource.org/w/api.php?action=parse&prop=text&format=json&page="
               + urllib.parse.quote(PAGE_TITLE))
        CACHE.write_text(json.loads(urllib.request.urlopen(urllib.request.Request(url, headers=UA),
                                                           timeout=60).read())["parse"]["text"]["*"],
                         encoding="utf-8")
    return CACHE.read_text(encoding="utf-8")


def paragraphs(page: str) -> list:
    page = re.sub(r'(?s)<span class="pagenum.*?</span></span>', "", page)            # the scan's page numbers
    page = re.sub(r'(?s)<span[^>]*class="[^"]*pagenum[^"]*"[^>]*>.*?</span>', "", page)
    page = re.sub(r"(?s)<style.*?</style>", "", page)                                 # page styling
    page = page[page.find("LITURGY."):] if "LITURGY." in page else page
    out = []
    for p in re.findall(r"(?s)<p>(.*?)</p>", page):
        p = re.sub(r'(?s)<i>\s*<span style="color:#8B0000;">(.*?)</span>\s*</i>',
                   lambda m: "\x01" + m.group(1) + "\x02", p)                         # the rubrics, marked
        p = re.sub(r"<br\s*/?>", "\n", p)
        text = html.unescape(re.sub(r"<[^>]+>", "", p)).replace("​", "")
        text = re.sub(r"[ \t\xa0]+", " ", text).strip()
        text = re.sub(r"\x01\s*(.*?)\s*\x02", lambda m: f"*{m.group(1).strip()}*" if m.group(1).strip() else "", text,
                      flags=re.S)
        if text and text not in ("*", "**"):
            out.append(text)
    return out


def main():
    paras = paragraphs(page_html())
    starts = {}
    for marker, name in SECTIONS:
        i = next((i for i, p in enumerate(paras) if marker.lower() in p.lower() and i not in starts), None)
        if i is None:
            raise SystemExit(f"section marker not found: {marker!r}")
        starts[i] = name
    pages, section, current = [], SECTIONS[0][1], []
    for i, p in enumerate(paras):
        if i in starts and current:
            pages.append({"section": section, "text": "\n\n".join(current)})
            current = []
        section = starts.get(i, section)
        if current and len("\n\n".join(current + [p])) > PAGE:
            pages.append({"section": section, "text": "\n\n".join(current)})
            current = []
        current.append(p)
    if current:
        pages.append({"section": section, "text": "\n\n".join(current)})
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"title": "The Divine Liturgy of Saint John Chrysostom", "source": SOURCE,
                               "pages": pages}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{len(paras)} paragraphs, {len(pages)} pages; sections at {sorted(starts)}")


if __name__ == "__main__":
    main()
