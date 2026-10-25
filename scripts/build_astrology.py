"""
The astrologers' own books, from archive.sacred-texts.com:

  * Ptolemy's Tetrabiblos, trans. J. M. Ashmand (1822)   -> data/classical/tetrabiblos.json
      "Tetrabiblos" by book.chapter (3.18 = Book III, Chapter XVIII), and his "Centiloquy" (100 aphorisms)
  * William Lilly, An Introduction to Astrology, ed. Zadkiel (1852)  -> data/medieval/lilly_astrology.json
      Lilly's Christian Astrology (1647), abridged and modernised by "Zadkiel" (R. J. Morrison): its
      chapters I-XXXV, and the appendix (Zadkiel's aphorisms; persons by sign; the aspects' effects...)

One page of sacred-texts a chapter, its paragraphs the verses; headings in italics leading their
paragraph. Dropped: page numbers, footnotes, the translators' prefaces and contents, the Almagest extracts
and star chart, the Life of Lilly, and Lilly's example charts (images). Tables become a line a row.
Pages are cached in scripts/.cache/astro/.

    python scripts/build_astrology.py            fetch (if needed) and build
    python scripts/build_astrology.py --fetch    just fetch
"""
import html
import json
import re
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "scripts" / ".cache" / "astro"
BASE = "https://archive.sacred-texts.com/astro/"
UA = {"User-Agent": "ScriptureBot corpus builder (personal Discord bot)"}
PAGES = {"ptb": 78, "aia": 47}
ROMAN = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100}
SMALL = {"and", "the", "of", "a", "an", "in", "on", "to", "or", "by", "for", "from", "with", "as", "at", "his",
         "her", "its", "their", "be", "is", "are", "may", "viz", "etc", "into", "which", "what", "whether"}


# Where the transcription has "###" for a glyph it couldn't render, and the book itself shows what it was
CORRECTIONS = {
    # Lilly's own horary chart (Ch. XXVII): "he" is ♃, and his exaltation is ♋ -- Lilly's table of
    # essential dignities (Ch. XVIII), the ♋ row: "Exaltations ... ♃ 15"
    "when he entered ###, his exaltation": "when he entered ♋, his exaltation",
    # The appendix's headings ("♄ in ♈"...), as every other one is set: !planets' daily post finds Lilly's
    # readings by them. "pi" stands where ♓ should, the Sun's twelfth sign between ☉ in ♒ and Venus.
    '<p align="center">♄ <i>in</i> ♏.</p>': '<p align="center">♄ <i>in</i> ♏</p>',
    '<p align="center">☉ <i>i</i>n ♎</p>': '<p align="center">☉ <i>in</i> ♎</p>',
    '<p align="center">☉ <i>in</i> pi</p>': '<p align="center">☉ <i>in</i> ♓</p>',
    '<p align="center">♀ <i>i</i>n ♉</p>': '<p align="center">♀ <i>in</i> ♉</p>',
    '<p align="center">♄ ✶ or △ ☽</p>': '<p align="center">♄ ✶ <i>or</i> △ ☽</p>',
}


def corrected(page: str) -> str:
    for wrong, right in CORRECTIONS.items():
        page = page.replace(wrong, right)
    return page


def fetch(book: str, n: int) -> str:
    path = CACHE / f"{book}{n:02d}.htm"
    if not path.exists():
        CACHE.mkdir(parents=True, exist_ok=True)
        for attempt in range(4):
            try:
                req = urllib.request.Request(f"{BASE}{book}/{book}{n:02d}.htm", headers=UA)
                data = urllib.request.urlopen(req, timeout=60).read()
                break
            except Exception as e:                       # (never reuse a failed page's data)
                if attempt == 3:
                    raise SystemExit(f"{book}{n:02d}: {e}")
                time.sleep(3 * (attempt + 1))
        path.write_bytes(data)
        time.sleep(0.7)
    return corrected(path.read_bytes().decode("utf-8", errors="replace"))


def roman(s: str) -> int:
    total, prev = 0, 0
    for ch in reversed(s.upper()):
        v = ROMAN[ch]
        total, prev = (total - v, prev) if v < prev else (total + v, v)
    return total


def titled(text: str) -> str:
    """"OF THE PLANET MARS, AND HIS SEVERAL SIGNIFICATIONS." -> "Of the Planet Mars, and His Several Significations"."""
    text = re.sub(r"\s+", " ", text).strip().rstrip(".")
    if text != text.upper():
        return text
    words = text.lower().split(" ")
    out = []
    for i, w in enumerate(words):
        core = re.sub(r"^\W+", "", w)
        if i and core in SMALL:
            out.append(w)
        else:
            j = len(w) - len(core)
            out.append(w[:j] + core[:1].upper() + core[1:])
    return " ".join(out)


def inline(fragment: str) -> str:
    """One paragraph's HTML as text: italics as *...*, no footnote marks or links, entities decoded."""
    s = re.sub(r'(?is)<a name="fr_\d+"></a>|<a href="[^"]*#fn_\d+"[^>]*>.*?</a>', "", fragment)   # footnote marks
    s = re.sub(r"(?is)<a\b[^>]*>(.*?)</a>", r"\1", s)
    s = re.sub(r"(?is)<br\s*/?>", "\n", s)
    s = re.sub(r"(?is)<(i|em)>\s*(.*?)\s*</\1>", lambda m: f"*{m.group(2)}*" if m.group(2).strip() else "", s)
    s = re.sub(r"(?is)<img[^>]*>", "", s)
    s = re.sub(r"(?s)<[^>]+>", "", s)
    s = html.unescape(s).replace(" ", " ")
    s = re.sub(r"[ \t]+", " ", s).replace(" \n", "\n").replace("\n ", "\n").strip()
    s = re.sub(r"(?<=\w)--(?=\w)", "—", s).replace("--", "—")
    s = re.sub(r"\*\s*\*", "", s)                      # an empty pair of italics
    return s


SIGNS = ["Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo", "Libra", "Scorpio", "Sagittarius", "Capricorn",
         "Aquarius", "Pisces"]
PLANETS = {"Sat": "Saturn", "Jup": "Jupiter", "Mars": "Mars", "Ven": "Venus", "Mer": "Mercury"}


def _sign(cell: str) -> str:
    c = re.sub(r"[*.\s]", "", cell)
    return c if c in SIGNS else ""


def sign_table(rows: list) -> "list | None":
    """Ptolemy's tables with a column a sign, read across they're nonsense: turned round, a line a sign.
    The Terms (1.23, 1.24): under each sign, (planet, degrees, running total) triples ->
    "Aries: Jupiter to 6°, Venus to 12°, ...". The regions (2.3): a label, then a value a sign ->
    "Aries: Triplicity, North West; ..."."""
    out, signs, labelled, cols = [], [], False, {}
    for cells in rows:
        named = [_sign(c) for c in cells]
        if all(named) and cells:                                   # a row of sign names
            signs, labelled = named, False
            continue
        if not all(named) and all(named[1:]) and len(cells) > 1:   # "Signs. | Aries. | Taurus. ..."
            signs, labelled = named[1:], True
            continue
        if not signs:
            return None
        if labelled:
            label, values = cells[0].strip("*").rstrip("."), cells[1:]
            if len(values) != len(signs):
                return None
            for s, v in zip(signs, values):
                cols.setdefault(s, []).append(f"{label}, {v.rstrip('.')}")
        else:
            if len(cells) != 3 * len(signs):
                return None
            for k, s in enumerate(signs):
                planet, _, upto = cells[3 * k:3 * k + 3]
                names = " and ".join(PLANETS.get(p.rstrip("."), p.rstrip(".")) for p in planet.split())
                cols.setdefault(s, []).append(f"{names} to {upto.rstrip('.')}°")
    if not cols:
        return None
    return [f"*{s}*: " + ("; ".join(cols[s]) if labelled else ", ".join(cols[s])) for s in SIGNS if s in cols]


def table_lines(fragment: str) -> list:
    rows = []
    for row in re.findall(r"(?is)<tr\b.*?</tr>", fragment):
        cells = [inline(c) for c in re.findall(r"(?is)<t[dh]\b[^>]*>(.*?)</t[dh]>", row)]
        cells = [c.replace("\n", " ") for c in cells if c.strip()]
        if cells:
            rows.append(cells)
    turned = sign_table(rows) if any(all(_sign(c) for c in r) or all(_sign(c) for c in r[1:]) for r in rows[:1]) else None
    return turned if turned is not None else [" · ".join(r) for r in rows]


def blocks(page: str) -> list:
    """[("h", text) | ("p", text)] of a page's own content, in order."""
    page = re.sub(r"(?is)<script.*?</script>|<style.*?</style>", "", page)
    body = re.split(r'(?i)<h3[^>]*>\s*Footnotes\s*</h3>', page)[0]
    start = re.search(r"(?i)<h[1-4]\b", body)
    if not start:
        return []
    body = body[start.start():]
    body = re.split(r'(?is)<hr\b[^>]*>\s*(?:<center>\s*)?(?:<a href="[^"]+">\s*)?Next:|<nav\b', body)[0]
    out = []
    for m in re.finditer(r"(?is)<h([1-4])\b[^>]*>(.*?)</h\1>|<p\b[^>]*>(.*?)</p>|<table\b.*?</table>", body):
        if m.group(2) is not None:
            text = inline(m.group(2))
            if text:
                out.append(("h", text))
        elif m.group(3) is not None:
            raw = m.group(3)
            if re.search(r'(?i)<a name="page_\w+">', raw) and not inline(re.sub(r"(?is)<a name=\"page_.*?</a>", "", raw)):
                out.append(("page", ""))                  # a page-number marker: may split a paragraph
                continue
            text = inline(raw)
            if text:
                out.append(("p", text))
        else:
            out += [("p", line) for line in table_lines(m.group(0))]
    return out


def paragraphs(items: list) -> list:
    """Paragraphs, with headings as italic lines leading the next, and a paragraph that a page break cut
    in two joined again ("neither fearing God nor" | p. 41 | "caring for man")."""
    out, heading, broke = [], [], False
    for kind, text in items:
        if kind == "page":
            broke = True
            continue
        if kind == "h":
            heading.append(titled(text))
            broke = False
            continue
        if re.fullmatch(r"p\. \d+|END OF THE [A-Z ]+\.?|[_\-*\s]+", text) or text.startswith("Click to enlarge"):
            continue                                   # a page number; a printer's line or rule; a chart's leftovers
        if text.startswith("[paragraph continues]") and out:
            out[-1] = f"{out[-1]} {text[len('[paragraph continues]'):].strip()}"   # (sacred-texts' own mark)
            broke = False
            continue
        if broke and out and not heading and (re.match(r"[a-z]", text) or re.search(r"[A-Za-z,]$", out[-1])):
            out[-1] = f"{out[-1]} {text}"               # (a new paragraph never starts in lower case, nor
                                                        #  does one end on a bare word or a comma)
        elif broke and out and not heading and not re.search(r"[.!?:;”\"’')\]]\s*$", out[-1]) and re.match(r"\(", text):
            out[-1] = f"{out[-1]} {text}"
        else:
            lead = "\n".join(f"*{h}*" for h in heading)
            out.append(f"{lead}\n{text}" if lead else text)
            heading = []
        broke = False
    if heading:
        out.append("\n".join(f"*{h}*" for h in heading))
    return out


def chapter(paras: list) -> dict:
    return {str(i): p for i, p in enumerate(paras, 1)}


def tetrabiblos() -> dict:
    books, book = {}, 0
    for n in range(4, 74):
        items = blocks(fetch("ptb", n))
        heads = [t for k, t in items if k == "h"]
        if any(re.match(r"(?i)book the", h) for h in heads):
            book += 1
        num = next((roman(m.group(1)) for h in heads for m in [re.match(r"(?i)chapter ([ivxl]+)\b", h)] if m), None)
        if num is None:
            raise SystemExit(f"ptb{n:02d}: no chapter number in {heads}")
        # keep only the chapter's own title (not "Ptolemy's Tetrabiblos / Four Books / Book the First / Chapter I")
        title = heads[-1] if not re.match(r"(?i)chapter [ivxl]+$", heads[-1]) else ""
        body = [(k, t) for k, t in items if k != "h" or (t not in heads[: heads.index(title) + 1] if title else True)]
        body = [("h", title)] + body if title else body
        books[f"{book}.{num}"] = chapter(paragraphs(body))
    expected = {1: 27, 2: 14, 3: 19, 4: 10}
    for b, count in expected.items():
        got = len([k for k in books if k.startswith(f"{b}.")])
        if got != count:
            raise SystemExit(f"Tetrabiblos Book {b}: {got} chapters, expected {count}")
    # the Centiloquy: a hundred aphorisms, numbered "I." to "C."
    items = blocks(fetch("ptb", 76))
    text = [t for k, t in items if k == "p" and not re.fullmatch(r"END OF THE [A-Z ]+\.?", t)]
    aph = {}
    for t in text:
        m = re.match(r"^([IVXLC]+)\.\s+(.+)", t, re.S)
        if m and roman(m.group(1)) == (max(aph) + 1 if aph else 1):
            aph[roman(m.group(1))] = m.group(2).strip()
        elif aph:
            last = max(aph)
            aph[last] += "\n" + t
    if sorted(aph) != list(range(1, 101)):
        missing = sorted(set(range(1, 101)) - set(aph))
        raise SystemExit(f"Centiloquy: missing aphorisms {missing}")
    return {"Tetrabiblos": books, "Centiloquy": {"1": {str(k): v for k, v in sorted(aph.items())}}}


def lilly() -> dict:
    chapters = {}
    for n in range(4, 39):
        items = blocks(fetch("aia", n))
        heads = [t for k, t in items if k == "h"]
        num = next((roman(m.group(1)) for h in heads for m in [re.match(r"(?i)chapter ([ivxl]+)\b", h)] if m), None)
        if num is None:
            raise SystemExit(f"aia{n:02d}: no chapter number in {heads}")
        items = [(k, t) for k, t in items if not (k == "h" and (re.match(r"(?i)chapter [ivxl]+\.?$", t)
                                                                 or t.upper() in ("INTRODUCTION TO ASTROLOGY.",
                                                                                  "THE RESOLUTION OF ALL MANNER OF QUESTIONS AND DEMANDS.")))]
        chapters[str(num)] = chapter(paragraphs(items))
    if sorted(map(int, chapters)) != list(range(1, 36)):
        raise SystemExit(f"Lilly: chapters {sorted(map(int, chapters))}")
    appendix = {}
    for i, n in enumerate(range(39, 47), 1):
        appendix[str(i)] = chapter(paragraphs(blocks(fetch("aia", n))))
    return {"Lilly's Introduction to Astrology": chapters, "Lilly's Introduction to Astrology, Appendix": appendix}


def write(path: Path, source: str, books: dict) -> None:
    path.write_text(json.dumps({"source": source, "books": books}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{path.relative_to(ROOT)}: " + ", ".join(f"{b} ({len(c)} ch.)" for b, c in books.items()))


def main():
    for book, pages in PAGES.items():
        for n in range(pages):
            fetch(book, n)
    if "--fetch" in sys.argv:
        return
    write(ROOT / "data" / "classical" / "tetrabiblos.json", "trans. J. M. Ashmand (1822)", tetrabiblos())
    write(ROOT / "data" / "medieval" / "lilly_astrology.json", "William Lilly (1647), ed. Zadkiel (1852)", lilly())


if __name__ == "__main__":
    sys.exit(main())
