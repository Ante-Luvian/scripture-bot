"""
G. R. S. Mead's "A Mithraic Ritual" (Echoes from the Gnosis VI, 1907): the "Mithras Liturgy" of the Great Paris
Magical Papyrus, in his English, with his preamble. From the Hermetic Library's page (hermetic.com/pgm/mithraic),
which refuses automated downloads: the owner saved it from a browser to scripts/.cache/mithraic/mithraic.htm.

Into data/esoteric/mithraic.json as "A Mithraic Ritual": chapter 0 the preamble, then a chapter for each of the
ritual's sections, I-XIII (the page leaves out the numerals of VI and VII, the Second and Third Utterances,
between V and VIII), a paragraph a verse. Left out: Mead's page numbers ("{9}") and the site's furniture. His
two Greek words, typed for a Greek font ("surigmoj"), are Greek.

    python scripts/build_mithraic.py
"""
import html
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from corpus_clean import clean_corpus  # noqa: E402

SRC = ROOT / "scripts" / ".cache" / "mithraic" / "mithraic.htm"
OUT = ROOT / "data" / "esoteric" / "mithraic.json"
NUMERALS = ["I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X", "XI", "XII", "XIII"]


def main() -> None:
    t = SRC.read_text(encoding="utf-8", errors="replace")
    t = re.sub(r"(?is)<head.*?</head>|<script.*?</script>|<style.*?</style>|<nav.*?</nav>|<footer.*?</footer>", "", t)
    t = t[t.find("G.R.S. Mead"):]
    t = re.sub(r"(?i)<(i|em)>(\s*)(.*?)(\s*)</\1>",
               lambda m: f"{m.group(2)}*{m.group(3)}*{m.group(4)}" if m.group(3).strip() else " ", t)
    chapters, current = {"0": []}, "0"
    for p in re.split(r"(?i)<p\b[^>]*>|<h\d[^>]*>|<blockquote[^>]*>|<li[^>]*>", t):
        s = html.unescape(re.sub(r"<[^>]+>", " ", p)).replace("\xa0", " ")
        s = re.sub(r"\{\d+\}|[\d.]+pt'>", " ", s)
        s = s.replace("surigmoj", "συριγμός").replace("poppusmoj", "ποππυσμός")
        s = re.sub(r"\s+", " ", s).strip()
        s = re.sub(r"^Preamble\s+", "", s)
        s = re.sub(r"\*(\s*)\*", r"\1", s)             # (italics broken at each mark: "*†* *,*")
        s = re.sub(r" {2,}", " ", s)
        s = re.sub(r"\s+([,.;:!?])", r"\1", s)
        if not s or s in ("G.R.S. Mead", "The Ritual") or s.startswith(("Last modified:", "by John Bell")):
            continue
        if s.rstrip(".") in NUMERALS:                  # (a section's numeral)
            current = str(NUMERALS.index(s.rstrip(".")) + 1)
            chapters[current] = []
            continue
        utterance = re.match(r"(?i)THE \[?(SECOND|THIRD)\]? UTTERANCE", s)
        if utterance and current == "5":               # (VI and VII, unnumbered on the page)
            current = "6"
            chapters[current] = []
        elif utterance and current == "6" and utterance.group(1).upper() == "THIRD":
            current = "7"
            chapters[current] = []
        if s.isupper() or re.fullmatch(r"\[[A-Z .’']+\]", s):    # (a heading: "[THE FIRST INSTRUCTION.]")
            s = re.sub(r"[A-Za-z][A-Za-z'’]*", lambda m: m.group(0)[0].upper() + m.group(0)[1:].lower(),
                       s.strip("[]").rstrip("."))      # ("The Father's Prayer", not "Father'S")
            s = f"*{re.sub(r'(?<=[a-z ])(Of|The|And)(?= )', lambda m: m.group(1).lower(), s)}*"
        chapters[current].append(s)
    if list(chapters) != [str(i) for i in range(14)]:
        raise SystemExit(f"sections: {list(chapters)}")
    book = {}
    for c, ps in chapters.items():
        merged = []
        for p in ps:                                   # (a heading line leads the paragraph after it)
            if merged and re.fullmatch(r"\*[^*]+\*", merged[-1]):
                merged[-1] += "\n" + p
            else:
                merged.append(p)
        book[c] = {str(i + 1): p for i, p in enumerate(merged)}
    src = "trans. G. R. S. Mead (1907)"
    payload = {"source": src, "books": {"A Mithraic Ritual": book}, "book_sources": {"A Mithraic Ritual": src}}
    clean_corpus(payload, "esoteric/mithraic.json")
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"  A Mithraic Ritual: {len(book)} chapters, "
          f"{sum(len(v.split()) for c in book.values() for v in c.values()):,} words")


if __name__ == "__main__":
    main()
