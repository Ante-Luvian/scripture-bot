"""
Hekhalot Rabbati, "the Greater Palaces": Rabbi Ishmael's account of the descent to the Chariot through the seven
palaces, their guards and the hymns sung before the Throne, with the two pieces that follow it in the manuscript:
Sar Torah, "the Prince of the Torah", and the Chapter of Rabbi Nehuniah ben Ha-Kanah. In Source Library's English
(2026): a machine translation (AI) of Vatican MS Ebr. 228, not reviewed by any person, the same source as 3 Enoch
(scripts/build_3enoch.py, whose cleaning this uses). Into data/charles/hekhalot_rabbati.json, three books.

They are scans 142-182 of the manuscript, each piece headed and closed in it:
  Hekhalot Rabbati   142-173  "The Palaces of Rabbi Ishmael, which he saw when he ascended on High, and the Work of
                              the Chariot" ... "Completed are the Laws of the Palaces (Hekhalot)"
  Sar Torah          174-180  "Let us begin Sar Torah" ... "Finished: Prince of the Torah"
  Chapter of Rabbi   180-182  "Chapter of Rabbi Nehuniah ben Ha-Kanah, which he taught to Rabbi Ishmael" ... "Finished."
  Nehuniah

Chapters are the manuscript's own ("Chapter 2", "Chapter XVII", "This is Chapter 25:"), counted in order. Its
numbers slip ("Chapter 30." where 10 belongs, a second "Chapter 12" for 13, "Chapter XVII" twice for 16 and 17,
"Chapter 51." for 21) and 26's heading is missing, so counting gives its numbers through 25 and makes its 27 our 26.
"Chapter 5 of Hekhalot" (a reference, mid-chapter) is not a heading. Paragraphs are the verses, long ones in pieces.

    python scripts/build_hekhalot.py
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
import build_3enoch as enoch  # noqa: E402
from corpus_clean import clean_corpus  # noqa: E402

OUT = ROOT / "data" / "charles" / "hekhalot_rabbati.json"
FIRST, LAST = 142, 182
SOURCE = enoch.SOURCE

# (book, its opening words, its closing words: each cut at these, the closing words kept)
PIECES = [("Hekhalot Rabbati", "The Palaces of Rabbi Ishmael", "Completed are the Laws of the Palaces (Hekhalot)"),
          ("Sar Torah", "Let us begin Sar Torah", "Finished: Prince of the Torah"),
          ("Chapter of Rabbi Nehuniah", "Chapter of Rabbi Nehuniah ben Ha-Kanah", "Finished.")]
HEADING = re.compile(r"(?:This is )?Chapter (?:\d+|[XVIL]+)\b(?! of Hekhalot)\.?:?\s*")
TITLES = {"Hekhalot Rabbati": "The Palaces of Rabbi Ishmael, which he saw when he ascended on High, and the Work of the Chariot",
          "Sar Torah": "Let us begin Sar Torah",
          "Chapter of Rabbi Nehuniah": "Chapter of Rabbi Nehuniah ben Ha-Kanah, which he taught to Rabbi Ishmael"}


INSERTION = re.compile(r"(?<=[a-z,])(\s*)<margin>\s*([a-z][^<]*?)\s*</margin>")


def _clean(t: str) -> str:
    """build_3enoch.clean, but a margin that carries on the sentence (the scribe's insertion: "the Prince of
    <margin>the Presence, my friend, the praise</margin> of the King") is kept in the text; the others (labels,
    catchwords, numbers: "<margin>Fixed portion</margin>") are dropped as there."""
    return _enoch_clean(INSERTION.sub(lambda m: f" {m.group(2)} ", t))


_enoch_clean = enoch.clean


def text() -> str:
    """The pages run together (as build_3enoch.text, for these scans)."""
    enoch.FIRST, enoch.LAST = FIRST, LAST
    enoch.clean = _clean
    try:
        t = enoch.text()
    finally:
        enoch.clean = _enoch_clean
    t = re.sub(r"(?is)</?(term|insert)>", "", t)
    # ("Chapter 5 of Hekhalot", a reference, and the "> " the translation marks the passage it introduces with)
    t = re.sub(r"Chapter 5 of Hekhalot\s*", "", t)
    t = re.sub(r"(?m)^>\s*", "", t).replace("~", " ")
    t = re.sub(r"[ \t]{2,}", " ", t)
    return enoch.gaps(t)


def verses(body: str) -> dict:
    paras = [re.sub(r"\s+", " ", p).strip() for p in re.split(r"\n\s*\n", body)]
    merged = []
    for p in (p for p in paras if p):
        if merged and (p[:1].islower() or len(p) < 25):
            merged[-1] += " " + p                       # (a fragment cut off by a page break joins its paragraph)
        else:
            merged.append(p)
    return {str(i + 1): v for i, v in enumerate(v for p in merged for v in enoch.pieces(p))}


def book(t: str, name: str) -> dict:
    """{chapter: {verse: text}} for one piece's text (its title already removed)."""
    cuts = [m for m in HEADING.finditer(t)]
    bodies = [t[:cuts[0].start()] if cuts else t] + [t[a.end():b.start() if b else len(t)]
                                                     for a, b in zip(cuts, cuts[1:] + [None])]
    out = {}
    for n, body in enumerate(bodies, 1):
        v = verses(body)
        if len(v.get("1", "")) < 40 and not v["1"].endswith((".", ":", ",", "?", "!")):
            v["1"] = f"*{v['1']}*"                      # (a heading's own title: "Chapter 24: The Song of the Throne")
        if n == 1:
            v = {"1": f"*{TITLES[name]}*", **{str(int(k) + 1): x for k, x in v.items()}}
        out[str(n)] = v
    return out


def main() -> None:
    t = text()
    books = {}
    for name, start, end in PIECES:
        a = t.index(start)
        b = t.index(end, a) + len(end)
        piece = t[a:b]
        title = TITLES[name]
        if not re.sub(r"\s+", " ", piece).startswith(title):
            raise SystemExit(f"{name}: doesn't open with its title")
        piece = re.sub(r"\s+", " ", piece[:len(title) + 5]).removeprefix(title) + piece[len(title) + 5:]
        books[name] = book(piece.strip(), name)
        t = t[b:]
    want = {"Hekhalot Rabbati": 26, "Sar Torah": 5, "Chapter of Rabbi Nehuniah": 2}
    got = {k: len(v) for k, v in books.items()}
    if got != want:
        raise SystemExit(f"unexpected chapters: {got}, not {want}")
    payload = {"source": SOURCE, "books": books}
    clean_corpus(payload, "charles/hekhalot_rabbati.json")
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    for name, chapters in books.items():
        words = sum(len(v.split()) for c in chapters.values() for v in c.values())
        print(f"{name}: {len(chapters)} chapters, {sum(len(c) for c in chapters.values())} paragraphs, {words:,} words")


if __name__ == "__main__":
    main()
