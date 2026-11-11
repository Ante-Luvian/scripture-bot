"""
Three books in E. A. Wallis Budge's translations, from sacred-texts (chr/kn, chr/bct, chr/bb), into
data/charles/budge.json (2026-11-10):

    the Kebra Nagast ("The Glory of Kings", 1932 edition), Ethiopia's national epic of Solomon, the Queen of Sheba
    and their son Menelik, who brings the Ark of the Covenant to Ethiopia: its 117 chapters and the translator's
    colophon (118), each chapter's own title leading its first verse;
    the Cave of Treasures (1927), the Syriac history of the world from Creation to Pentecost: its six periods (the
    five thousand years and the five hundred from Cyrus to Christ) as chapters 1-6;
    the Book of the Bee (1886), Solomon of Akhlat's Syriac compendium (c. 1222): its 60 chapters, each with its own
    title, and the author's preface as chapter 0.

None of them has verse numbers in Budge: a verse is a paragraph, or a run of whole sentences of a long one. Left
out: Budge's footnotes and their marks, the page and manuscript-folio numbers, and, in the Cave, his bracketed
section headings and the "[NOTES.--...]" commentary set between its paragraphs. Names Budge prints in small
capitals ("SOLOMON") are in ordinary capitals ("Solomon"); the few whole sentences in small capitals are recased
by CASE_FIXES (the build checks that only the case changes).

    python scripts/build_budge.py
"""
import html
import json
import re
import sys
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_pseudepigrapha import SENTENCE_END, expect, roman  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
CACHE = Path(__file__).resolve().parent / ".cache" / "budge"
OUT = ROOT / "data" / "charles" / "budge.json"
UA = {"User-Agent": "ScriptureBot corpus builder (a personal Discord bot)"}


def fetch(path: str) -> str:
    CACHE.mkdir(parents=True, exist_ok=True)
    f = CACHE / path.replace("/", "_")
    if not f.exists():
        req = urllib.request.Request("https://archive.sacred-texts.com/chr/" + path, headers=UA)
        f.write_bytes(urllib.request.urlopen(req, timeout=60).read())
        time.sleep(1)
    return f.read_bytes().decode("utf-8")


# the site's typing slips
SLIPS = {"Grek Palace": "Greek Palace", 'said unto him) "One hundred': 'said unto him, "One hundred',
         "eveything": "everything", "childreh": "children", "fomication": "fornication", "puried hill": "buried him",
         "familles of": "families of", "phophet": "prophet", "thirty yeats": "thirty years", "tbeir": "their",
         "own pature": "own nature"}
SLIPS_SEEN = dict.fromkeys(SLIPS, 0)


def small_caps(m: re.Match) -> str:
    """Budge's small capitals: after a capital letter they finish its word ("T" "HEN": Then); on their own they are
    a name ("SOLOMON": Solomon) or an abbreviation ("A.D.")."""
    before, inner = m.group(1), html.unescape(re.sub(r"<[^>]+>", "", m.group(2)))
    if before:
        return before + inner.lower()
    if re.fullmatch(r"\s*(?:[A-Z]\.)+\s*", inner):
        return inner
    return re.sub(r"[^\W\d_]+", lambda w: w.group(0)[0] + w.group(0)[1:].lower(), inner)


def text_of(fragment: str) -> str:
    s = re.sub(r'(?is)<a name="[^"]*_fr_\d+">\s*</a>\s*<a href="#[^"]*">.*?</a>', "", fragment)   # (footnote marks)
    s = re.sub(r'(?is)<a name="page_\d+">.*?</a>', " ", s)                                       # (page numbers)
    s = re.sub(r'(?is)\[\s*<font color="?green"?>\s*<a name="fol_[^"]*">\s*</a>.*?</font>\s*\.?\s*\]', " @@F@@ ", s)
    s = re.sub(r"(?is)(\w?)<small>(.*?)</small>", small_caps, s)
    s = re.sub(r"(?is)</?(?:u|sup|sub|i|b|big|em|strong|font|a|span|img)\b[^>]*>", "", s)
    s = html.unescape(re.sub(r"<[^>]+>", " ", s)).replace("\xa0", " ")
    s = re.sub(r"([.!?])\s*@@F@@\s*\.", r"\1", s)          # ("them. [Fol. 50 b, col. 2]. Here endeth")
    s = re.sub(r"\s+", " ", s.replace("@@F@@", " ")).strip()
    s = re.sub(r"\s*\{(?:Greek|Hebrew|Syriac|sic)\b[^}]*\}", "", s)       # (the site's transliterations and sics)
    s = re.sub(r"\s*[\[(]\s*(?:Compare|See)\b[^\])]*[\])]", "", s)       # (Budge's cross-references)
    s = re.sub(r"\*(?: ?\*)+", "…", s)                                  # (Budge's mark of a passage left out)
    for slip, right in SLIPS.items():
        SLIPS_SEEN[slip] += s.count(slip)
        s = s.replace(slip, right)
    return re.sub(r"(?<=[\w\])”\"'])\s+(?=[,;:!?]|\.(?!\s*\.))", "", s)


def blocks(page: str) -> list:
    """The page's paragraphs and headings in order, as (tag, centred, text), without the site's furniture."""
    page = re.split(r"(?i)<h3[^>]*>\s*Footnotes|<nav\b", page)[0]
    page = re.sub(r"(?is)<!--.*?-->|<(script|style)\b.*?</\1>", "", page)
    out = []
    for m in re.finditer(r"(?is)<table\b[^>]*>(.*?)</table>|<(p|h1|h2|h3|blockquote)\b([^>]*)>(.*?)"
                         r"(?=<(?:p|h\d|hr|div|blockquote|table)\b|</blockquote>|</body>|$)", page):
        if m.group(1) is not None:                    # (a list set as a table: a line for each row or line break)
            rows = re.split(r"(?i)<br\s*/?>|</tr>", m.group(1))
            text = "\n".join(t for t in map(text_of, rows) if t)
            if text:
                out.append(("table", False, text))
            continue
        text = text_of(m.group(4))
        if text and not re.fullmatch(r"Sacred[- ]Texts.*|Next|Previous|.*sacred-texts\.com.*", text):
            out.append((m.group(2).lower(), "center" in m.group(3).lower(), text))
    return out


def sentences(p: str) -> list:
    """A paragraph's sentences, never broken inside brackets or parentheses or after "i.e." ("(i.e. Light)") --
    unless a bracket the text never closes has held them together for 1,000 characters."""
    out = []
    for piece in re.split(SENTENCE_END, p):
        prev = out[-1] if out else ""
        if prev and len(prev) < 1000 and (prev.count("(") > prev.count(")") or prev.count("[") > prev.count("]")
                                          or re.search(r"\b(?:i\.e|e\.g|viz|cf|Mâr|St)\.$", prev)):
            out[-1] = f"{prev} {piece}"
        else:
            out.append(piece)
    return out


def groups(p: str, size: int = 700, longest: int = 1200) -> list:
    """A paragraph, or if longer than `longest` runs of its whole sentences of about `size` characters (as
    build_world_texts.sentence_groups)."""
    if len(p) <= longest:
        return [p]
    out, run = [], ""
    for s in sentences(p):
        if run and len(run) + len(s) > size:
            out.append(run)
            run = s
        else:
            run = f"{run} {s}".strip()
    return out + [run] if run else out


def verses_of(paras: list) -> list:
    """Paragraphs as verses: long prose cut into runs of whole sentences, a list (lines) into runs of whole lines."""
    out = []
    for p in paras:
        if "\n" not in p:
            out += groups(p)
            continue
        run = ""
        for line in p.split("\n"):
            if run and len(run) + len(line) > 1000:
                out.append(run)
                run = line
            else:
                run = f"{run}\n{line}" if run else line
        out.append(run)
    return out


def editorial(text: str) -> str:
    """Whether a paragraph opens with Budge's own bracketed matter: "whole" if the bracket closes at its end, "open"
    if it runs on into the paragraphs after, "" if the bracket closes inside the text ("[And] he said") or none."""
    if not text.startswith("["):
        return ""
    depth = 0
    for i, ch in enumerate(text):
        depth += (ch == "[") - (ch == "]")
        if depth == 0:
            return "whole" if not text[i + 1:].strip(" .") else ""
    return "open"


# whole sentences Budge sets in capitals, with the case they would have in his ordinary type (only the case may
# change: the build checks)
CASE_FIXES = [
    "In praising God the Father, the Sustainer of the universe, and His Son Jesus Christ, through Whom everything "
    "came into being, and without Whom nothing came into being, and the Holy Triune Spirit, the Paraclete, Who goeth "
    "forth from the Father, and deriveth from the Son, we believe in and adore the Trinity, one God, the Father, and "
    "the Son, and the Holy Spirit.",
    "And in the fortieth year of Yârêd the first thousand years, from Adam to Yârêd, came to an end.",
    "Of the transmission of the art of playing the harp, that is to say, of music, and singing and dancing.",
    "the second thousand years of the posterity of Adam to the time of the Flood came to an end",
    "In the days of Reu the third thousand years came to an end.",
    "And in the twenty-sixth year of his life the fourth thousand years came to an end.",
    "Cyrus, and the fifth thousand years came to an end.",
    "the fifth thousand [years] came to an end.",
    "Book of the Order of the Succession of Families from Adam to Christ",
    '(i.e. "Cave of Treasures")',
    "and Râmyâ (Roma?)",
]


def recase(books: dict) -> None:
    seen = dict.fromkeys(CASE_FIXES, 0)
    for chapters in books.values():
        for verses in chapters.values():
            for v, t in verses.items():
                t = re.sub(r"(?i)\bFamilles from", "Families from", t)    # (the site's slip: "FAMILlES")
                for right in CASE_FIXES:
                    t, k = re.subn(re.escape(right), lambda m: right, t, flags=re.I)
                    seen[right] += k
                verses[v] = t
    expect(all(n == 1 for n in seen.values()), f"case fixes not found once {[r[:40] for r, n in seen.items() if n != 1]}")


def kebra_nagast() -> dict:
    book = {}
    for n in range(1, 119):
        bl = blocks(fetch(f"kn/kn{n:03d}.htm"))
        heads = [t for tag, _, t in bl if tag == "h3"]
        expect(len(heads) == 1, f"Kebra Nagast {n}: headings {heads}")
        if n == 118:
            expect(heads[0] == "Colophon", f"Kebra Nagast: {heads[0]!r}")
            title = "Colophon"
        else:
            m = re.fullmatch(rf"{n}\. (.+)", heads[0])
            expect(m is not None, f"Kebra Nagast {n}: heading {heads[0]!r}")
            title = m.group(1)
        verses = []
        if n == 1:                                    # (the book's title and its opening praise come first)
            expect([t for tag, _, t in bl[:2]] == ["THE GLORY OF KINGS", bl[1][2]] and bl[0][0] == "h1", "Kebra Nagast: opening")
            verses.append("*The Glory of Kings*\n" + bl[1][2])
            bl = bl[2:]
        expect(not any(tag == "table" for tag, _, _ in bl), f"Kebra Nagast {n}: a table")
        paras = verses_of([t for tag, _, t in bl if tag == "p"])
        expect(paras, f"Kebra Nagast {n}: no text")
        paras[0] = f"*{title}*\n" + paras[0]
        book[str(n)] = {str(k): t for k, t in enumerate(verses + paras, start=1)}
    return book


def index_titles(path: str, pattern: str) -> dict:
    page = fetch(path)
    return {f: text_of(t) for f, t in re.findall(rf'(?is)<a href="({pattern})">(.*?)</a>', page)}


def cave_of_treasures() -> dict:
    titles = index_titles("bct/index.htm", r"bct\d+\.htm")
    book = {}
    for n in range(4, 10):
        verses, in_note = [], False
        for tag, centred, text in blocks(fetch(f"bct/bct{n:02d}.htm")):
            # Budge's notes and headings, in brackets: "[NOTES.--...]", "[The Birth of Seth.]", and notes that run on
            # over several paragraphs and tables ("[The names of the Babylonian Signs of the Zodiac were:--")
            if in_note:
                in_note = not (tag != "table" and text.endswith("]"))
                continue
            kind = editorial(text)
            if kind:
                in_note = kind == "open"
                continue
            if tag == "h1" or text in ("TRANSLATION", "(Brit. Mus. MS. Add. 25875.)"):
                continue
            if centred and not re.search(r"(?i)came to an end|to God be glory", text):
                expect(n == 9 and text.startswith("THE FIVE HUNDRED YEARS"), f"Cave {n}: centred {text[:60]!r}")
                continue
            text = re.sub(r"\s*\(\s*See Book of Adam[^)]*\)", "", text)       # (Budge's cross-reference)
            if tag == "blockquote":
                text = f"*{text}*"
            verses.append(text)
        expect(not in_note, f"Cave {n}: a note never closes")
        verses = verses_of(verses)
        verses[0] = f"*{titles[f'bct{n:02d}.htm']}*\n" + verses[0]
        book[str(n - 3)] = {str(k): t for k, t in enumerate(verses, start=1)}
    expect(book["1"]["1"].split("\n")[1].startswith("By the might of our Lord Jesus Christ"), "Cave: the scribe's prayer")
    return book


def book_of_the_bee() -> dict:
    titles = index_titles("bb/index.htm", r"bb\d+\.htm")
    book = {}
    for n in range(0, 61):
        bl = blocks(fetch(f"bb/bb{n:02d}.htm"))
        heads = [t for tag, _, t in bl if tag == "h1"]
        if n == 0:
            expect(heads == ["THE BOOK OF THE BEE."], f"Bee 0: {heads}")
            title = "The Book of the Bee"
        else:
            m = re.fullmatch(r"CHAPTER ([IVXL]+)\s*\.", heads[0]) if len(heads) == 1 else None
            expect(m is not None and roman(m.group(1)) == n, f"Bee {n}: {heads}")
            title = re.sub(r"^Chapter [IVXL]+ - ", "", titles[f"bb{n:02d}.htm"])
        paras = [t for tag, centred, t in bl if tag in ("p", "table") and not centred]
        if n == 0:                                    # (the list of the chapters, a table, is the index, not text)
            expect(paras[-1].startswith("I. Of God's eternal intention"), f"Bee 0: {paras[-1][:40]!r}")
            paras = paras[:-1]
        paras = verses_of(paras)
        expect(paras, f"Bee {n}: no text")
        paras[0] = f"*{title}*\n" + paras[0]
        book[str(n)] = {str(k): t for k, t in enumerate(paras, start=1)}
    return book


def main() -> None:
    books = {"Kebra Nagast": kebra_nagast(), "Cave of Treasures": cave_of_treasures(),
             "Book of the Bee": book_of_the_bee()}
    recase(books)
    expect(all(n == 1 for n in SLIPS_SEEN.values()), f"slips not found once {[s for s, n in SLIPS_SEEN.items() if n != 1]}")
    for name, chapters in books.items():
        print(f"  {name}: {len(chapters)} chapters, {sum(map(len, chapters.values()))} verses")
    sources = {"Kebra Nagast": "trans. E. A. Wallis Budge (1932)",
               "Cave of Treasures": "trans. E. A. Wallis Budge (1927)",
               "Book of the Bee": "Solomon of Akhlat, trans. E. A. Wallis Budge (1886)"}
    OUT.write_text(json.dumps({"source": "trans. E. A. Wallis Budge", "book_sources": sources, "books": books},
                              ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
