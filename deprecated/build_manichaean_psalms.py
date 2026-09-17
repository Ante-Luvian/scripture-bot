"""
Build script: converts C.R.C. Allberry's 1938 translation of A Manichaean
Psalm-Book, Part II (the Coptic psalms attributed to Mani's own community
at Medinet Madi, Egypt) into data/gnostic/manichaean_psalms.json.

SOURCE AND COPYRIGHT STATUS -- verified directly, not assumed:
Allberry (Charles Robert Cecil Augustine Allberry, 1911-1943) died in
action with the RAF on 3 April 1943, shot down over Essen. Under UK
copyright law (life of the author + 70 years), his 1938 translation has
been in the public domain since 2013. This is confirmed independently by
the source page itself: gnosis.org/library/manithomas.htm carries the
footer "Referance: A Manichaean Psalm-Book, Edited by C. R. C. Allberry
(Stuttgart, W. Kohlhammer, 1938.) Thanks to Stevan Davies for contributing
this file." -- naming the exact translator, edition, and year, which
matches the death-date-based PD determination made independently first.

This is a DIFFERENT and separable question from the rest of the
Manichaean material on that same gnosis.org index page (manis.htm), most
of which is NOT used here:
  - The Kephalia excerpt on that page is Polotsky & Böhlig's 1940
    translation. Polotsky died 1991, Böhlig died 1996 -- both under
    copyright until 2061/2066. Not public domain. Not included.
  - The "Parthian Hymns and Prayers", "Hymns and Writings Ascribed to
    Mani", "Parables", and most of "Miscellaneous Manichaean Scriptures"
    sections match the style of modern (1970s-1990s) Central Asian
    Manichaean scholarship (the Klimkeit/Boyce/Sundermann generation),
    none of whom are anywhere near 70 years dead. Not public domain. Not
    included.
  - The "Secondary Sources: Anti-Manichaean Writings of Augustine"
    section is Richard Stothert's 1887 Nicene and Post-Nicene Fathers
    translation (confirmed directly against the page text) -- genuinely
    PD, but already present in this bot's patristics corpus under
    data/patristics/augustine.json (On the Morals of the Catholic Church,
    On the Morals of the Manichaeans, On Two Souls Against the
    Manichaeans, Acts/Disputation Against Fortunatus, Reply to Faustus
    the Manichaean, Concerning the Nature of Good, Against the Epistle of
    Manichaeus Called Fundamental). Not duplicated here.

None of the individual short-psalm pages on gnosis.org (the ones actually
used here) carry a translator credit themselves; the Allberry attribution
above was confirmed by cross-checking one longer page on the same site
(the Psalms of Thomas compilation) that does carry it, plus independently
matching the translation's known publication history.

Four "books" are produced from four groupings on gnosis.org/library/manis.htm:
  - Manichaean Psalms to Jesus       (9 psalms, chapter = Allberry's psalm number)
  - Manichaean Bema Psalms           (8 psalms, chapter = Allberry's psalm number)
  - Manichaean Psalms of Thomas      (12 psalms, chapter = psalm number I-XII)
  - Manichaean Psalms (Separate)     (3 untitled-number psalms, chapters 1-3)
Verses are stanza-level (one <p> block/stanza per verse, as laid out on the
source pages), not Allberry's own line numbering, which isn't reproduced
in this HTML.

Downloads its own source -- run from anywhere. Note: gnosis.org's TLS
certificate is currently expired, so this bypasses certificate
verification for that one host only (the content itself is plain old
static HTML, not something sensitive):
    python deprecated/build_manichaean_psalms.py
"""
import html
import re
import ssl
import time
import urllib.request
from pathlib import Path

BASE = "https://www.gnosis.org/library/"
OUT_PATH = Path(__file__).parent.parent / "data" / "gnostic" / "manichaean_psalms.json"

SOURCE_NOTE = (
    "A Manichaean Psalm-Book, Part II, trans. C. R. C. Allberry (1938), "
    "via The Gnostic Society Library"
)

_CTX = ssl.create_default_context()
_CTX.check_hostname = False
_CTX.verify_mode = ssl.CERT_NONE

# (page, book, chapter)
PSALMS_TO_JESUS = [
    ("psaj1.htm", 1), ("psaj2.htm", 2), ("psaj5.htm", 5), ("psaj7.htm", 7),
    ("psaj10.htm", 10), ("psaj11.htm", 11), ("psaj21.htm", 21),
    ("psaj30.htm", 30), ("psaj31.htm", 31),
]
BEMA_PSALMS = [
    ("bc23.htm", 223), ("bc28.htm", 228), ("bc30.htm", 230), ("bc35.htm", 235),
    ("bc37.htm", 237), ("bc39.htm", 239), ("bc40.htm", 240), ("bc41.htm", 241),
]
SEPARATE_PSALMS = [
    ("taste.htm", 1), ("put.htm", 2), ("light.htm", 3),
]

_HEADING_LIKE = re.compile(r"^Psalm\b", re.I)


def _fetch(page):
    req = urllib.request.Request(BASE + page, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
    with urllib.request.urlopen(req, timeout=30, context=_CTX) as r:
        return r.read().decode("iso-8859-1", errors="replace")


def _clean_block(inner: str) -> str:
    inner = re.sub(r"<br[^>]*>", "\n", inner, flags=re.I)
    inner = re.sub(r"<[^>]+>", "", inner)
    inner = html.unescape(inner)
    lines = [re.sub(r"[ \t]+", " ", l).strip() for l in inner.split("\n")]
    lines = [l for l in lines if l and l != "\xa0"]
    return " ".join(lines)


def _extract_paragraphs(segment: str) -> list[str]:
    blocks = re.findall(r"<p\b[^>]*>(.*?)</p>", segment, flags=re.I | re.S)
    out = []
    for b in blocks:
        text = _clean_block(b)
        if text:
            out.append(text)
    return out


def _extract_verses(doc: str) -> list[str]:
    hr_idx = doc.index("<hr")
    head_region = doc[:hr_idx]
    h2_ends = [m.end() for m in re.finditer(r"</h2>", head_region, re.I)]
    start = h2_ends[-1] if h2_ends else 0
    paras = _extract_paragraphs(doc[start:hr_idx])
    return [p for p in paras if not (_HEADING_LIKE.match(p) and len(p) < 40)]


def build_single_psalm_group(pages, label):
    chapters = {}
    for page, chapter in pages:
        doc = _fetch(page)
        verses = _extract_verses(doc)
        chapters[str(chapter)] = {str(i): v for i, v in enumerate(verses, start=1)}
        print(f"  {label} {chapter}: {len(verses)} verses")
        time.sleep(0.5)
    return chapters


def build_thomas():
    doc = _fetch("manithomas.htm")
    parts = doc.split("<hr>")
    sections = parts[1:13]
    if len(sections) != 12:
        raise RuntimeError(f"expected 12 Psalms-of-Thomas sections, got {len(sections)}")
    chapters = {}
    for i, seg in enumerate(sections, start=1):
        cut = re.search(r"Referance:", seg)
        if cut:
            seg = seg[: cut.start()]
        paras = _extract_paragraphs(seg)
        verses = paras[1:]  # drop the "N: Title" heading paragraph
        chapters[str(i)] = {str(v): text for v, text in enumerate(verses, start=1)}
        print(f"  Psalms of Thomas {i}: {len(verses)} verses")
    return chapters


def main():
    print("Psalms to Jesus:")
    psaj = build_single_psalm_group(PSALMS_TO_JESUS, "Psalm")
    print("Bema Psalms:")
    bema = build_single_psalm_group(BEMA_PSALMS, "Psalm")
    print("Separate Psalms:")
    sep = build_single_psalm_group(SEPARATE_PSALMS, "Psalm")
    print("Psalms of Thomas:")
    thomas = build_thomas()

    payload = {
        "source": SOURCE_NOTE,
        "books": {
            "Manichaean Psalms to Jesus": psaj,
            "Manichaean Bema Psalms": bema,
            "Manichaean Psalms (Separate)": sep,
            "Manichaean Psalms of Thomas": thomas,
        },
    }
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(__import__("json").dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    total = sum(len(v) for book in payload["books"].values() for v in book.values())
    print(f"Wrote {OUT_PATH} -- {total} total verses across {sum(len(b) for b in payload['books'].values())} chapters")


if __name__ == "__main__":
    main()
