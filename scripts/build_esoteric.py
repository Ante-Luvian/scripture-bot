"""
Western magic and esotericism, from Joseph H. Peterson's esotericarchives.com (careful transcriptions of the old
English printings and manuscripts), into data/esoteric/. English only: the Latin of the bilingual pages (the
second column of their tables) is left out, and so are Peterson's introductions and notes.

  agrippa     Agrippa's Three Books of Occult Philosophy (trans. J. F., 1651) and the Fourth Book (Turner, 1655).
              Left out: the chapters of his Vanity of Arts and Sciences the 1651 edition added after Book III.
  arbatel     Arbatel of Magic (Turner, 1655)
  heptameron  Peter of Abano's Heptameron (Turner, 1655)

    python scripts/build_esoteric.py [step ...]
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
CACHE = ROOT / "scripts" / ".cache" / "esoteric"
OUT = ROOT / "data" / "esoteric"
BASE = "https://www.esotericarchives.com/"
UA = {"User-Agent": "ScriptureBotCorpusBuilder/1.0 (Discord bot; low-volume one-off import)"}
COMMON = set("the and of to in that is it be for with as his he which by this are not or from but they all shall "
             "thou thee thy you your him them their there when what then have hath be".split())


def expect(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"unexpected: {message}")


def page(name: str, english_column: bool = False) -> str:
    """A page of the archive, without its head, scripts, comments (Peterson's page markers) or notes' cells; with
    english_column, a bilingual page's tables keep only their first cell in each row (the English)."""
    path = CACHE / name.replace("/", "_")
    if not path.exists():
        CACHE.mkdir(parents=True, exist_ok=True)
        path.write_bytes(urllib.request.urlopen(urllib.request.Request(BASE + name, headers=UA), timeout=120).read())
        time.sleep(1.5)
    raw = path.read_bytes()
    t = raw.decode("utf-8", "replace") if b"charset=utf-8" in raw[:3000].lower() else raw.decode("cp1252", "replace")
    t = re.sub(r"(?is)<head.*?</head>|<script.*?</script>|<style.*?</style>|<!--.*?-->|<pre>.*?</pre>", " ", t)
    t = re.sub(r'(?is)<td[^>]*class=["\']?note["\']?[^>]*>.*?(?=<td|</tr>|</table>)', " ", t)
    if english_column:
        def first_cell(row):
            cells = re.split(r"(?i)<td\b", row.group(0))
            return cells[0] + ("<td" + cells[1] if len(cells) > 1 else "")
        t = re.sub(r"(?is)<tr\b.*?(?=<tr\b|</table>)", first_cell, t)
    return t


def clean(fragment: str) -> str:
    s = re.sub(r'(?is)<img[^>]*\balt=["\']?([A-Za-z]{1,2})["\']?[^>]*>', r"\1", fragment)   # (a drop capital)
    s = re.sub(r"(?is)<sup>.*?</sup>|<a[^>]*href=[\"']?#(?:fn|note|n)\w*[^>]*>.*?</a>", "", s)
    s = re.sub(r"(?is)<(i|em)>(.*?)</\1>", lambda m: f"*{m.group(2).strip()}*" if m.group(2).strip() else " ", s)
    s = html.unescape(re.sub(r"<[^>]+>", " ", s)).replace("\xa0", " ")
    s = re.sub(r"\s*\[\*?[^\[\]\s]*(\s[^\[\]\s]*){0,4}\]", "", s)     # (Peterson's short glosses first: "[*seat]")
    # (Turner prints a conjuration in Latin, then his English of it in brackets: the English is the text)
    long = [m for m in re.finditer(r"\[([^\[\]]+)\]", s) if len(m.group(1).split()) > 25]
    if long and latin_words(re.sub(r"\[[^\[\]]+\]", " ", s)) >= 8:
        s = " ".join(m.group(1) for m in long)
    elif re.fullmatch(r"\s*\[[^\[\]]+\]\s*", s):
        s = s.strip()[1:-1]                                                 # (a whole paragraph in his brackets)
    # Peterson's apparatus: [modern spellings and glosses], {variants}, [sic], [Greek text omitted]; <words> he
    # restored from the old printing keep their words
    s = re.sub(r"\s*\[[^\[\]]{0,150}\]|\s*\{[^{}]*\}", "", s)
    s = re.sub(r"<([^<>]*)>", r"\1", s)
    s = re.sub(r"\s+", " ", s).strip()
    # (a drop capital set apart: "T Hey", "M usical"; but "A simple point" is a word)
    s = re.sub(r"^([B-HJ-NP-Z]) (?=[A-Za-z])|^([AIO]) (?=[A-Z][a-z])", lambda m: m.group(1) or m.group(2), s)
    s = re.sub(r"^([A-Z])([A-Z])(?=[a-z])", lambda m: m.group(1) + m.group(2).lower(), s)        # ("THey")
    s = re.sub(r"\*\s*\*", " ", s)
    if s.count("*") % 2:
        s = s.replace("*", "")                                              # (an italic across a paragraph break)
    return re.sub(r"\s+([,.;:])", r"\1", s).strip()


LATIN = set("et est sunt ad cum non qui quae quod de ex per autem enim vel sed ut nec aut eius sicut hoc haec "
            "ipse quam atque ac etiam tamen sive seu super sub inter apud ab cuius quibus omnes omnia vero ita "
            "sit esse erit deus dei domini nomine nomen spiritus angeli".split())


def latin_words(s: str) -> int:
    return sum(w in LATIN or re.search(r"(orum|arum|ibus|ione|atur|itur|untur)$", w) is not None
               for w in re.findall(r"[a-z]+", s.lower()))


def english(s: str) -> bool:
    """Not Latin: a bilingual page's Latin lines are left out (short ones by their Latin words and endings)."""
    words = re.findall(r"[a-z]+", s.lower())
    if not words:
        return True
    latin = latin_words(s)
    common = sum(w in COMMON for w in words)
    if latin > common:
        return False
    if not common and latin < 2 and len(words) >= 4:
        return True                                     # (a list of names, Abramelin's spirits: not Latin either)
    if len(words) < 6 and not common:                    # (a short Latin line: "Linea recta Stans", "Punctus simplex")
        endings = sum(re.search(r"(us|um|ae|que|ex|ix|ens|is|ta|ra|lis)$", w) is not None for w in words)
        if endings * 2 >= len(words) and not re.search(r"(?i)\b(right|line|letter|figure|point|whole)\b", s):
            return False
    return len(words) < 4 or common / len(words) >= 0.1


def paras(fragment: str) -> list:
    """Paragraphs: the old pages open <P> without closing it, so a paragraph runs to the next block. A table row of
    short cells is one line ("Ashtaroth and Asmodeus — 53")."""
    def row(m):
        cells = [clean(c) for c in re.split(r"(?i)<t[dh]\b[^>]*>", m.group(1))[1:]]
        cells = [c for c in cells if c]
        if len(cells) >= 2 and all(len(c.split()) <= 8 for c in cells):
            return "<P>" + " — ".join(cells) + "<P>"
        return m.group(0)
    fragment = re.sub(r"(?is)<tr\b[^>]*>(.*?)(?=<tr\b|</table>)", row, fragment)
    parts = re.split(r"(?is)<p\b[^>]*>|<br\s*/?>\s*<br\s*/?>|</?td\b[^>]*>|</?div\b[^>]*>|</?center>|<h\d[^>]*>.*?</h\d>"
                     r"|</?table[^>]*>|</?tr[^>]*>|<hr[^>]*>", fragment)
    return [p for p in (clean(x) for x in parts) if p and english(p)]


def sections(t: str, keep=lambda title: True, levels: str = "1-5") -> list:
    """[(heading, paragraphs)] at each heading, from those `keep` accepts."""
    heads = list(re.finditer(rf"(?is)<h([{levels}])[^>]*>(.*?)</h\1>", t))
    out = []
    for i, m in enumerate(heads):
        inner = m.group(2).strip()
        if re.match(r"(?s)^(<[^>]+>)*\[", inner) and re.search(r"\]\.?(<[^>]+>|\s)*$", inner):
            inner = inner.replace("[", "", 1)[::-1].replace("]", "", 1)[::-1]   # (a heading Peterson supplied)
        title = clean(inner).replace("*", "")
        if not keep(title):
            continue
        end = heads[i + 1].start() if i + 1 < len(heads) else len(t)
        out.append((title, paras(t[m.end():end])))
    return out


def drop_short_foreign(secs: list) -> list:
    """A bilingual page's short Latin lines ("Linea recta Stans"): most of their words are never used in the page's
    long English paragraphs."""
    vocab = {w for _, ps in secs for p in ps if len(p.split()) >= 12 for w in re.findall(r"[a-z]+", p.lower())}

    def foreign(p):
        words = re.findall(r"[a-z]+", p.lower())
        return (0 < len(words) < 6 and sum(w in vocab for w in words) * 2 < len(words)
                and not any(w in COMMON for w in words)
                and any(re.search(r"(a|us|um|ae|io|ex|ens|que)$", w) for w in words))
    return [(t, [p for p in ps if not foreign(p)]) for t, ps in secs]


def roman(s: str) -> int:
    vals = {"i": 1, "v": 5, "x": 10, "l": 50, "c": 100}
    s = s.lower()
    return sum(-vals[c] if i + 1 < len(s) and vals[s[i + 1]] > vals[c] else vals[c] for i, c in enumerate(s))


def chapter(title: str, ps: list) -> dict:
    ps = list(ps)
    if title:
        ps = [f"*{title}*\n{ps[0]}"] + ps[1:] if ps else [f"*{title}*"]
    return {str(i + 1): p for i, p in enumerate(ps)}


def english_of(verse: str) -> str:
    """A verse that is a Latin conjuration followed by Turner's English of it in brackets: the English."""
    if verse.count("[") > verse.count("]"):                     # (a bracket whose other half was another column's)
        verse = re.sub(r"(^|\n)\[\s*", r"\1", verse, count=1)
    elif verse.count("]") > verse.count("["):
        verse = re.sub(r"\s*\](?=[^\]]*$)", "", verse, count=1)
    m = re.search(r"\[([^\[\]]{200,})\]\s*$", verse, re.S)
    if not m:
        return verse
    head, _, body = verse[:m.start()].partition("\n") if verse.startswith("*") else ("", "", verse[:m.start()])
    if latin_words(body) < 8:
        return verse
    return (head + "\n" if head else "") + m.group(1).strip()


def footnote_free(verse: str) -> str:
    """A footnote number left on an italic heading ("*…reigning on Friday.3*"): gone; and "* Sarabotes *, King"
    (italics with spaces inside, which the cleaner would unwrap to "Sarabotes , King") closed up."""
    verse = re.sub(r"(?<!\S)\*[ \t]+([^*\n]+?)[ \t]+\*(?!\w)", r"*\1*", verse)   # (not "*a* and *b*")
    return re.sub(r"(?m)^(\*[^\n*]*[a-z][.)]?)\d{1,2}\*", r"\1*", verse)


def save(name: str, books: dict, sources: dict) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    books = {b: {c: {v: footnote_free(english_of(t)) for v, t in vs.items()} for c, vs in chs.items()}
             for b, chs in books.items()}
    payload = {"source": next(iter(sources.values())), "books": books, "book_sources": sources}
    clean_corpus(payload, f"esoteric/{name}.json")       # (the library's own cleaner: nothing left for it to do later)
    (OUT / f"{name}.json").write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    for book, chapters in books.items():
        words = sum(len(v.split()) for c in chapters.values() for v in c.values())
        print(f"  {book}: {len(chapters)} chapters, {words:,} words -> data/esoteric/{name}.json")


# ── Agrippa ────────────────────────────────────────────────────────────────

CHAP = re.compile(r"(?i)^chap(?:ter)?\.?\s+([ivxlc]+)\b\.?\s*(.*)")


def agrippa() -> None:
    three = {}
    for book, name in ((1, "agrippa/op1.htm"), (2, "agrippa/op2.htm"), (3, "agrippa/op3.htm")):
        for title, ps in sections(page(name), keep=lambda t: bool(CHAP.match(t))):
            m = CHAP.match(title)
            n = roman(m.group(1))
            expect(f"{book}.{n}" not in three, f"Agrippa {book}.{n} twice")
            three[f"{book}.{n}"] = chapter(m.group(2).strip().rstrip("."), ps)
    for book, last in ((1, 74), (2, 60), (3, 65)):
        found = sorted(int(k.split(".")[1]) for k in three if k.startswith(f"{book}."))
        expect(found == list(range(1, last + 1)), f"Agrippa book {book}: {found[:3]}...{found[-3:]} ({len(found)})")
    fourth = {}
    for title, ps in drop_short_foreign(sections(page("agrippa/agrippa4.htm", english_column=True))):
        if re.match(r"(?i)\[?contents\]?$|heinrich cornelius agrippa|the end of the fourth", title) or not ps \
                or not english(title):
            continue
        fourth[str(len(fourth) + 1)] = chapter(title.strip("[] ").rstrip("."), ps)
    save("agrippa", {"Three Books of Occult Philosophy": three, "Fourth Book of Occult Philosophy": fourth},
         {"Three Books of Occult Philosophy": "Agrippa, trans. J. F. (1651)",
          "Fourth Book of Occult Philosophy": "pseudo-Agrippa, trans. Robert Turner (1655)"})


# ── Arbatel ────────────────────────────────────────────────────────────────
# From the outline of its nine tomes to the end of Aphorism 49 (Turner's preface to the reader is left out);
# chapter 0 the outline and invocation, then an aphorism a chapter.

APHOR = re.compile(r"(?i)^\*?\s*(the first aphorism|aphor\.?\s*\*?\s*\.?\s*(\d+))\b")


def arbatel() -> None:
    ps = paras(page("solomon/arbatel.htm", english_column=True))
    start = next(i for i, p in enumerate(ps) if p.startswith("*Containing nine Tomes"))
    end = next(i for i, p in enumerate(ps) if p.startswith("Courteous Reader")) + 1
    chapters, current = {"0": []}, "0"
    for p in ps[start:end]:
        m = APHOR.match(p)
        if m:
            current = "1" if m.group(1).lower().startswith("the first") else m.group(2)
            expect(current not in chapters, f"Arbatel aphorism {current} twice")
            chapters[current] = []
            continue
        chapters[current].append(p)
    expect(list(chapters) == [str(n) for n in range(0, 50)], f"Arbatel: {list(chapters)}")
    head = []                                           # (the outline's title lines lead its first paragraph)
    while chapters["0"] and len(chapters["0"][0].split()) <= 10 and chapters["0"][0].startswith("*"):
        head.append(chapters["0"].pop(0).strip("* "))
    if head:
        chapters["0"][0] = f"*{' '.join(head)}*\n{chapters['0'][0]}"
    books = {"Arbatel of Magic": {c: chapter("", ps) for c, ps in chapters.items()}}
    save("arbatel", books, {"Arbatel of Magic": "trans. Robert Turner (1655)"})


# ── Heptameron ─────────────────────────────────────────────────────────────
# Peterson numbers the chapters ("[I.] Of the Circle"): each starts one; then each day's considerations. English
# subheadings ("The Angels of the Spring") go into the chapter in italics; the Latin headings are left out.

def heptameron() -> None:
    t = page("solomon/heptamer.htm", english_column=True)
    start = t.find("of Peter de Abano, philosopher")
    expect(start > 0, "the Heptameron's title")
    t = t[start:]
    chapters, current = {}, None
    heads = list(re.finditer(r"(?is)<h([1-5])[^>]*>(.*?)</h\1>", t))
    for i, m in enumerate(heads):
        raw = html.unescape(re.sub(r"<[^>]+>", "", m.group(2))).strip()
        body = paras(t[m.end():heads[i + 1].start() if i + 1 < len(heads) else len(t)])
        num = re.match(r"\[([IVXL]+)\.?", raw)
        day = re.match(r"(?i)^(the )?considerations? of", raw) or \
            re.fullmatch(r"(?i)(sun|mon|mun|tues|wednes|thurs|fri|satur)day\.?", raw)    # (Turner's "Munday")
        if num or (day and current):
            current = str(roman(num.group(1))) if num else str(len(chapters) + 1)
            title = clean(re.sub(r"^\[[IVXL]+\.?\]?\s*", "", raw)).strip("[]() .")
            title = re.sub(r"[.)\]]*\d+$", "", title).strip("[]() .").replace("Aprayer", "A prayer")   # ("Air.1")
            chapters[current] = [f"*{title}*"] if title else []
        elif current is None or not english(raw) or re.match(r"(?i)finis|elementorum", raw):
            if current is None:
                continue
        else:
            chapters[current].append(f"*{clean(raw).strip('[] ')}*")
        if current:
            chapters[current].extend(body)
    numbered = [int(c) for c in chapters]
    expect(numbered[:18] == list(range(1, 19)), f"Heptameron: {numbered[:20]}")
    out = {}
    for c, ps in chapters.items():
        merged = []
        for p in ps:                                   # (a heading line leads the paragraph after it)
            if merged and re.fullmatch(r"\*[^*]+\*", merged[-1]):
                merged[-1] += "\n" + p
            else:
                merged.append(p)
        out[c] = {str(i + 1): p for i, p in enumerate(merged)}
    save("heptameron", {"Heptameron": out}, {"Heptameron": "Peter of Abano, trans. Robert Turner (1655)"})


# ── The Book of Abramelin (Mathers, 1898) ──────────────────────────────────
# From Book I to the end of Book III's symbols: Mathers's introduction, appendices, notes to each chapter and his
# "Essential Remarks upon the Foregoing Symbols" are left out (the symbols themselves are pictures). Chapters "1.0"
# a book's prologue, then "1.1"...; a chapter's headings in italics.

ORDINALS = ["first", "second", "third", "fourth", "fifth", "sixth", "seventh", "eighth", "ninth", "tenth",
            "eleventh", "twelfth", "thirteenth", "fourteenth", "fifteenth", "sixteenth", "seventeenth", "eighteenth",
            "nineteenth", "twentieth"]


def ordinal(word: str) -> int:
    word = word.lower().replace("twenty-", "twenty ").replace("thirtieth", "thirty").strip()
    if word == "thirty":
        return 30
    if word.startswith("twenty "):
        return 20 + ORDINALS.index(word.split()[1]) + 1
    return ORDINALS.index(word) + 1


def walk(t: str, on_heading) -> None:
    """Call on_heading(level, raw title, paragraphs after it) for each heading in order."""
    heads = list(re.finditer(r"(?is)<h([1-5])[^>]*>(.*?)</h\1>", t))
    for i, m in enumerate(heads):
        raw = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", "", m.group(2)))).strip()
        on_heading(int(m.group(1)), raw, paras(t[m.end():heads[i + 1].start() if i + 1 < len(heads) else len(t)]))


def abramelin() -> None:
    t = page("abramelin/abramelin.htm")
    t = t[re.search(r"(?i)<h1[^>]*>\s*THE FIRST BOOK OF THE HOLY MAGIC", t).start():
          re.search(r"(?i)<h3[^>]*>\s*ESSENTIAL REMARKS", t).start()]
    chapters, state = {}, {"book": 0, "chap": None, "skip": False}

    def on(level, raw, ps):
        book = re.match(r"(?i)THE (FIRST|SECOND|THIRD) BOOK", raw)
        chap = re.match(r"(?i)THE ([A-Z-]+) CHAPTER", raw)
        if book:
            state.update(book=ORDINALS.index(book.group(1).lower()) + 1, chap=None, skip=False)
            state["chap"] = f"{state['book']}.0"
            chapters[state["chap"]] = list(ps)
            return
        if chap:
            state.update(chap=f"{state['book']}.{ordinal(chap.group(1))}", skip=False)
            chapters[state["chap"]] = list(ps)
            return
        if re.match(r"(?i)\(?the prologue|prologue", raw):
            state.update(chap=f"{state['book']}.0", skip=False)
            chapters.setdefault(state["chap"], []).extend(ps)
            return
        if re.search(r"(?i)\bnotes?\b.*|mathers", raw) and re.match(r"(?i)notes?\b", raw):
            state["skip"] = True                       # (Mathers's notes, to the next chapter)
            return
        if state["skip"] or state["chap"] is None:
            return
        title = re.sub(r"\d+$", "", clean(raw)).strip()
        if re.match(r"(?i)end of the (first|second|third) book|the end of the second book|end$", title):
            return
        chapters[state["chap"]].extend([f"*{title}*"] + list(ps))

    walk(t, on)
    for b, last in ((1, 12), (2, 20), (3, 30)):
        found = sorted(int(c.split(".")[1]) for c in chapters if c.startswith(f"{b}."))
        expect(found[-1] == last and found == list(range(found[0], last + 1)), f"Abramelin book {b}: {found}")
    out = {}
    for c, ps in chapters.items():
        merged = []
        for p in ps:
            if merged and re.fullmatch(r"\*[^*]+\*", merged[-1]):
                merged[-1] += "\n" + p
            else:
                merged.append(p)
        if merged:
            out[c] = {str(i + 1): p for i, p in enumerate(merged)}
    save("abramelin", {"The Book of Abramelin": out}, {"The Book of Abramelin": "trans. S. L. MacGregor Mathers (1898)"})


BUILDS = {"agrippa": agrippa, "arbatel": arbatel, "heptameron": heptameron, "abramelin": abramelin}


def main(names: list) -> None:
    for name in names or BUILDS:
        print(name)
        BUILDS[name]()


if __name__ == "__main__":
    main(sys.argv[1:])
