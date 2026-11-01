"""
Western magic and esotericism, from Joseph H. Peterson's esotericarchives.com (careful transcriptions of the old
English printings and manuscripts), into data/esoteric/. English only: the Latin of the bilingual pages (the
second column of their tables) is left out, and so are Peterson's introductions and notes.

  agrippa     Agrippa's Three Books of Occult Philosophy (trans. J. F., 1651) and the Fourth Book (Turner, 1655).
              Left out: the chapters of his Vanity of Arts and Sciences the 1651 edition added after Book III.
  arbatel     Arbatel of Magic (Turner, 1655)
  heptameron  Peter of Abano's Heptameron (Turner, 1655)
  abramelin   The Book of Abramelin (Mathers, 1898)
  testament   The Testament of Solomon (Conybeare, 1898)
  keyofsolomon  The Key of Solomon, Books I-II (Mathers, 1889)
  lemegeton   The Lesser Key: Goetia, Theurgia Goetia, Ars Paulina, Ars Almadel (Sloane 3825) and Ars Notoria
              (Turner, 1657)
  sword       The Sword of Moses (Gaster, 1896)
  weyer       Weyer's Pseudomonarchia Daemonum in Reginald Scot's English (1584)
  raziel      Sepher Raziel: Liber Salomonis (Sloane 3846)
  dee         John Dee: De Heptarchia Mystica, The Hieroglyphic Monad (Hamilton-Jones), A Letter (1599)

    python scripts/build_esoteric.py [step ...]
"""
import difflib
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


def drop_note_cells(t: str) -> str:
    """Peterson's notes' cells (<TD CLASS=NOTE>), to the next cell, row or table end of their own table: a note
    with a table inside it (the SATOR square in the Key of Solomon) runs on past that table's cells."""
    out, pos = [], 0
    for m in re.finditer(r'(?i)<td[^>]*class=["\']?note["\']?[^>]*>', t):
        if m.start() < pos:
            continue
        out.append(t[pos:m.start()])
        depth, end = 0, len(t)
        for tag in re.finditer(r"(?i)<(/?)(table|td|tr)\b", t[m.end():]):
            closing, name = tag.group(1), tag.group(2).lower()
            if name == "table":
                if closing and depth == 0:
                    end = m.end() + tag.start()
                    break
                depth += -1 if closing else 1
            elif depth == 0:
                end = m.end() + tag.start()
                break
        out.append(" ")
        pos = end
    return "".join(out) + t[pos:]


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
    t = drop_note_cells(re.sub(r'(?is)<div id="menu">.*?</div>', " ", t))
    if english_column is True:
        return first_cells(t)
    return first_cells(t, english_column) if english_column else t


def first_cells(t: str, column: int = 0) -> str:
    """A bilingual page: in each row of the outermost tables only the English cell (the first; Weyer's the second);
    a table inside a kept cell (the Heptameron's "The Sun | The Moon") stays whole, one inside a dropped cell goes
    with it."""
    out, pos, depth, cell, keep = [], 0, 0, -1, True
    for m in re.finditer(r"(?i)<(/?)(table|tr|td|th)\b[^>]*>", t):
        if keep:
            out.append(t[pos:m.start()])
        pos = m.end()
        closing, name = m.group(1), m.group(2).lower()
        if name == "table":
            depth += -1 if closing else 1
            if depth == 0:
                cell, keep = -1, True
        elif depth == 1:
            if name == "tr" and not closing:
                cell, keep = -1, True
            elif name in ("td", "th") and not closing:
                cell += 1
                keep = cell == column
        if keep:
            out.append(m.group(0))
    if keep:
        out.append(t[pos:])
    return "".join(out)


SUPERSCRIPT = dict(zip("abcdefghijklmnoprstuvwxyz", "ᵃᵇᶜᵈᵉᶠᵍʰⁱʲᵏˡᵐⁿᵒᵖʳˢᵗᵘᵛʷˣʸᶻ"))
PLANETS = {"sol": "☉", "lun": "☽", "ven": "♀", "jup": "♃", "sat": "♄", "mer": "☿", "mar": "♂",
           "ari": "♈", "tau": "♉", "gem": "♊", "can": "♋", "leo": "♌", "vir": "♍", "lib": "♎", "sco": "♏",
           "sag": "♐", "cap": "♑", "aqu": "♒", "pis": "♓", "cnj": "☌", "opp": "☍", "qua": "□", "tri": "△",
           "sex": "⚹"}
SUPPLIED = {"keep": False}      # (the Lemegeton: Peterson's [words] supplied from other manuscripts are text)


def superscript(m) -> str:
    """A scribe's raised letters ("y<SUP>e</SUP>", "w<SUP>ch</SUP>", "4<SUP>th</SUP>") stay raised; a footnote
    number goes."""
    inner = re.sub(r"<[^>]+>", "", m.group(1)).strip()
    if re.fullmatch(r"[a-pr-z]{1,3}", inner):
        return "".join(SUPERSCRIPT[c] for c in inner)
    return ""


def supplied(m) -> str:
    """A [bracket] in the Lemegeton: words Peterson supplied ("into [a] deep lake") stay, as words; a modern or
    variant spelling of the words before it ("vesall [vessel]", "Bileth [Beleth]", "the other [others]") goes."""
    before, gap, inner = m.group(1) or "", m.group(2), m.group(3).strip()
    if re.fullmatch(r"[\d\s.,§-]+", inner):            # (his section numbers: "[1]")
        return before
    n = len(inner.split())
    prev = " ".join(re.sub(r"[^\w\s]", "", before).split()[-n:]).lower()
    if prev and difflib.SequenceMatcher(None, prev, inner.lower()).ratio() >= 0.5:
        return before
    return f"{before}{gap or ' ' if before else ''}{inner}"


def clean(fragment: str) -> str:
    s = re.sub(r'(?is)<img[^>]*\bsrc=["\']?(?:[^"\'>]*/)?(' + "|".join(PLANETS) + r')\.gif[^>]*>',
               lambda m: PLANETS[m.group(1).lower()], fragment)                # (the planets' and signs' symbols)
    s = re.sub(r'(?is)<img[^>]*\balt=(["\']?)([A-Za-z]{1,2})\1(?=[\s>/])[^>]*>', r"\2", s)   # (a drop capital)
    # (a big capital: "<FONT SIZE=5>H</FONT><I>Ely Scemath" is "*Hely Scemath*"; "<FONT SIZE=6>I</FONT> <I>Apollonius"
    # a word of its own)
    s = re.sub(r"(?is)<font size=[\"']?[4-7][\"']?>\s*([A-Z])\s*</font>(<i>|<em>)?([A-Z])(?=[a-z])",
               lambda m: f"{m.group(2) or ''}{m.group(1)}{m.group(3).lower()}", s)
    s = re.sub(r"(?is)<font size=[\"']?[4-7][\"']?>\s*([A-Z])\s*</font>(<i>|<em>)?(?=[A-Za-z])",
               lambda m: f"{m.group(2) or ''}{m.group(1)}", s)
    s = re.sub(r"(?is)\s*\^\s*<sup>(.*?)</sup>", r" \1", s)          # (a word the scribe wrote above: "^in order")
    s = re.sub(r"(?is)<sup>(.*?)</sup>", superscript, s)
    s = re.sub(r"(?is)<a[^>]*href=[\"']?#(?:fn|note|n)\w*[^>]*>.*?</a>", "", s)
    s = re.sub(r"\[\+\s*([^\[\]]+?)\s*\]", r"\1", s)                  # ("they are [+not] ignorant": his addition)
    s = re.sub(r"(?<=[A-Za-z])\[([a-z]{1,8})\]", r"\1", s)            # ("Mich[ael]": the rest of a word)
    if SUPPLIED["keep"]:
        # (not a note of another manuscript's reading: "[Sl.2731: Chomiel]", "[P adds: ...]")
        s = re.sub(r"(\S+(?:\s+\S+){0,3})?(\s*)\[(?![*=+?!]|sic\b)([^\[\]:]{1,40})\]", supplied, s)
    s = re.sub(r"(?is)<(i|em)>(\s*)(.*?)(\s*)</\1>",                   # ("<I>see Figure </I>61": the space stays)
               lambda m: f"{m.group(2)}*{m.group(3)}*{m.group(4)}" if m.group(3) else " ", s)
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
    # (a drop capital set apart: "T Hey", "M usical"; but "A simple point", "O Holy Father" and "I Invocate" are words)
    s = re.sub(r"^([B-HJ-NP-Z]) (?=[A-Za-z])", r"\1", s)
    s = re.sub(r"^([A-Z])([A-Z])(?=[a-z])", lambda m: m.group(1) + m.group(2).lower(), s)        # ("THey")
    s = re.sub(r"\*\s*\*", " ", s)
    if s.count("*") % 2:
        s = s.replace("*", "")                                              # (an italic across a paragraph break)
    s = re.sub(r",\s*,", ",", s)                                            # (a gloss gone from between commas)
    return re.sub(r"\s+([,.;:])", r"\1", s).strip()


LATIN = set("et est sunt ad cum non qui quae quod de ex per autem enim vel sed ut nec aut eius sicut hoc haec "
            "ipse quam atque ac etiam tamen sive seu super sub inter apud ab cuius quibus omnes omnia vero ita "
            "sit esse erit deus dei domini nomine nomen spiritus angeli mihi tibi nobis vobis meis tuis estote "
            "vos tu ego".split())


def latin_words(s: str) -> int:
    return sum(w in LATIN or re.search(r"(orum|orvm|arum|arvm|ibus|ione|atur|itur|untur)$", w) is not None
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
    out = []
    for x in parts:
        p = clean(x)
        if not p:
            continue
        bare = re.sub(r"(?is)<sup>.*?</sup>|<[^>]+>", "", x).strip()
        # (Turner's English of the Latin before it, a paragraph of its own in brackets: the Latin goes)
        if out and bare.startswith("[") and bare.endswith("]") and len(bare.split()) > 12 \
                and latin_words(out[-1]) >= 2:
            out.pop()
        if english(p):
            out.append(p)
    return out


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


def latin_quotes_out(verse: str) -> str:
    """A Latin incipit quoted in italics before the English ("*Dixit Angelus adæ fac thymiamata &c.* The Angell
    said to Adam..."): gone, when it's plainly Latin."""
    def quote(m):
        inner = m.group(1)
        incipit = re.search(r"&c\.?\s*$", inner) or m.group(2)
        lat = latin_words(inner)
        if incipit:                                    # ("*In nomini dei potentis vivi & veri &c.*")
            common = sum(w in COMMON for w in re.findall(r"[a-z]+", inner.lower()))
            return "" if lat >= 1 and lat >= common else m.group(0)
        return "" if lat >= 2 and not english(inner) else m.group(0)
    # (only one that opens a line: a Latin phrase inside an English sentence stays, or the sentence breaks)
    out = re.sub(r"(?m)^\*([^*\n]{8,})\*[ \t]*(&c\.?[ \t]*)?", quote, verse)
    out = re.sub(r"\n{2,}", "\n", out).strip()
    return out or verse


def save(name: str, books: dict, sources: dict) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    books = {b: {c: {v: latin_quotes_out(footnote_free(english_of(t))) for v, t in vs.items()}
                 for c, vs in chs.items()} for b, chs in books.items()}
    books = {b: {c: {v: t for v, t in vs.items() if t.strip()} for c, vs in chs.items()} for b, chs in books.items()}
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


# ── The Testament of Solomon (Conybeare, 1898) ─────────────────────────────
# His 130 numbered paragraphs, a chapter each. His own square brackets (words he supplied: "[He brought me] a little
# ring") stay; Peterson's footnotes are in the notes cells, which page() drops.

def testament() -> None:
    t = page("solomon/testamen.htm")
    t = re.sub(r"(?is)<em class=pg[^>]*>.*?</em>", " ", t)
    t = t[t.find("<H1>The Testament of Solomon"):t.rfind('<div id="menu"')]
    t = t.replace("[", "⟦").replace("]", "⟧")       # (out of reach of clean()'s gloss-stripping)
    chapters, current = {}, None
    for p in paras(t):
        p = p.replace("⟦", "[").replace("⟧", "]")
        p = re.sub(r"\s*\[\?[^\]]*\]", "", p)                    # (Peterson's guesses: "[?shabtai/Saturn?]")
        m = re.match(r"\*?(\d+)\.\s+(.*)", p, re.S)
        if m:
            current = m.group(1)
            expect(current not in chapters and int(current) == len(chapters) + 1, f"Testament paragraph {current}")
            body = m.group(2)
            if p.startswith("*"):
                body = "*" + body
            chapters[current] = [body]
        elif current:
            chapters[current].append(p)
    expect(len(chapters) == 130, f"Testament: {len(chapters)} paragraphs")
    save("testament", {"Testament of Solomon": {c: chapter("", ps) for c, ps in chapters.items()}},
         {"Testament of Solomon": "trans. F. C. Conybeare (1898)"})


# ── The Key of Solomon (Mathers, 1889) ─────────────────────────────────────
# Chapter "0" Solomon's introduction (to Roboam); "1.1"-"1.18" Book I, the descriptions of the pentacles staying in
# 1.18 where Mathers put them; "2.1"-"2.23" Book II. Left out: Mathers's preface and notes, the planetary tables
# he compiled, his appendices (the "Ancient Fragment" and "Qabalistical Invocation" from Lévi), Peterson's
# introduction and the captions of the figures (pictures), and the French "Books 3 and 4" (another work).

FIGURE = re.compile(r"(?i)^\[|^(figures?|circle|magic circle|ritual implements|sacred names|seal|sigil|"
                    r"symbols?|the hebrew lettering|pentacle from|plate)\b"
                    r"|\b(from|in) (ad|add|sl|sloane|coxe|vsg|ghent|gg|aub|aub24|bnf|lans|harl|or|m276|mich)\b\.?\s*\d"
                    r"|\bsymbols from\b")


def merged(ps: list) -> dict:
    out = []
    for p in ps:                                       # (a heading line leads the paragraph after it)
        if out and re.fullmatch(r"\*[^*]+\*", out[-1]):
            out[-1] += "\n" + p
        else:
            out.append(p)
    return {str(i + 1): p for i, p in enumerate(out)}


def key_of_solomon() -> None:
    chapters = {}

    def book(name, n, start, stop=None):
        t = page(name)
        at = t.find(start)
        expect(at > 0, f"{name}: {start}")
        t = t[t.rfind("<H", 0, at):t.find(stop) if stop else len(t)]
        state = {"chap": "0" if n == 0 else None, "skip": False}
        if n == 0:
            chapters["0"] = []

        def on(level, raw, ps):
            title = re.sub(r"(?<=[A-Za-z.])\d+$", "", raw).strip()
            m = re.match(r"(?i)CHAPTER ([IVXL]+)$", title)
            if m and n:
                state.update(chap=f"{n}.{roman(m.group(1))}", skip=False)
                chapters[state["chap"]] = list(ps)
                return
            if re.match(r"(?i)table of|note by editor", title):
                state["skip"] = True
                return
            if state["chap"] is None or state["skip"]:
                return
            if FIGURE.search(title):                   # (a picture's caption: the text after it goes on)
                chapters[state["chap"]].extend(ps)
                return
            if re.match(r"(?i)book i+$|introduction\.?$", title):
                chapters[state["chap"]].extend(ps)
                return
            label = re.sub(r"(?<=[A-Za-z,])\d+\b", "", clean(title)).strip("[]. ").replace("*", "")   # ("Of1")
            label = label.capitalize() if label.isupper() else label
            chapters[state["chap"]].extend([f"*{label}*"] + list(ps))
        walk(t, on)

    book("solomon/ksol.htm", 0, ">INTRODUCTION.</A>", "BOOK I</")
    if chapters["0"] and chapters["0"][0].startswith("*From Add. MSS"):
        chapters["0"].pop(0)                           # (Mathers's note of his manuscript)
    book("solomon/ksol.htm", 1, "BOOK I</")
    book("solomon/ksol2.htm", 2, "PREFATORY NOTE", "ANCIENT FRAGMENT OF THE KEY")
    for b, last in ((1, 18), (2, 23)):
        found = sorted(int(c.split(".")[1]) for c in chapters if c.startswith(f"{b}."))
        expect(found == list(range(1, last + 1)), f"Key of Solomon book {b}: {found}")
    chapters["1.18"] = [p for p in chapters["1.18"] if not p.startswith("This is the end of the holy pentacles")]
    save("keyofsolomon", {"The Key of Solomon": {c: merged(ps) for c, ps in chapters.items() if ps}},
         {"The Key of Solomon": "ed. and trans. S. L. MacGregor Mathers (1889)"})


# ── The Lemegeton, or Lesser Key of Solomon (Sloane 3825, ed. Peterson) ────
# A book for each of its five parts. Goetia: "0" the definition of magic and the Lemegeton's own opening (its five
# parts), "1"-"72" a spirit each, then the observations, figures and conjurations a section each. Theurgia
# Goetia: "0" its opening, then each of the 31 emperors, kings and princes with his dukes and conjuration, then the
# closing conjurations. Ars Paulina and Ars Almadel: a section each. The manuscript's spellings and its raised
# letters ("yᵉ", "wᶜʰ") are kept; Peterson's words supplied from other manuscripts are text, his modern
# spellings go.

def lemegeton_sections(t: str, first: list = None) -> list:
    """[[paragraphs]] at each <H3>; <H4>s inside one are italic headings; the captions of figures are dropped."""
    out = [list(first)] if first else []
    h = re.search(r"(?i)<h[1-5]\b", t)
    lead = paras(t[:h.start()] if h else t)                 # (the text before the first heading)
    if lead:
        out = out or [[]]
        out[-1].extend(lead)
    if not h:
        return [s for s in out if s]

    def on(level, raw, ps):
        title = re.sub(r"(?<=[A-Za-z.\]])\d+[a-z]?$", "", raw).strip()
        if FIGURE.search(title) and not re.match(r"(?i)\[(the|of|other|oration|concerning)", title) \
                or re.match(r"(?i)\[?(sloane|harl|abbreviations|contents)", title):
            if out:
                out[-1].extend(ps)
            return
        label = clean(re.sub(r"^\[(.*)\]\.?$", r"\1", title)).replace("*", "").strip(" .:-")
        if level <= 3 or not out:
            out.append([f"*{label}*"] + list(ps) if label else list(ps))
        else:
            out[-1].extend([f"*{label}*"] + list(ps) if label else list(ps))
    walk(t, on)
    return [s for s in out if s]


def goetia() -> dict:
    pre = page("solomon/lemegeton.htm")
    pre = pre[pre.rfind("<H", 0, pre.find("The definition of Magic")):pre.find("APPENDIX - Other")]
    pre = pre[:pre.rfind("<H2")]
    chapters = {"0": [p for s in lemegeton_sections(pre) for p in s]}
    t = page("solomon/goetia.htm")
    cat = t.find("seventy-two infernal spirits")
    head_end = t.find("</H2>", cat) + 5
    obs = t.find("These be the seventy two")
    spirits = paras(t[head_end:obs])
    n = 0
    for p in spirits:
        if re.match(r"(?i)the (first|second|third|\d+\S*) (principall )?spirit\b", p):
            n += 1
            chapters[str(n)] = [p]
        elif n:
            chapters[str(n)].append(p)
    expect(n == 72, f"Goetia: {n} spirits")
    rest = t[t.rfind("<P", 0, obs):t.find("The End of the First Part")]
    rest = rest[:rest.rfind("<H")] if rest.rfind("<H3") > rest.rfind("</H3>") else rest
    for s in lemegeton_sections("<H3>[The seventy-two kings]</H3>" + rest):
        chapters[str(len(chapters))] = s
    return chapters


def theurgia() -> dict:
    t = page("solomon/theurgia.htm")
    t = t[t.find("Here beginneth the second Part"):t.find("And so ends the second Book")]
    t = t[t.find("</H3>", t.find("of Kinge Salomon")) + 5:]
    chapters, current = {"0": []}, "0"
    # (each emperor, king or prince begins a paragraph: "<STRONG>Caspiel</STRONG> is the...", or "...is called
    # <STRONG>Padiel</STRONG>")
    starts = (r"<P>(?=\s*(?:<em class=pg[^>]*>[^<]*</em>\s*(?:<P>)?\s*)?(?:<STRONG>[^<]+</STRONG>\s*(?:\[[^\]]*\]\s*)?is\b"
              r"|(?:(?!<P|<H|</?T[DR]|<BLOCKQUOTE).){0,250}?called\s*<STRONG>))")
    pieces = re.split(f"(?is)({starts})", t)
    princes = sum(bool(re.fullmatch(r"(?i)<P>", p)) for p in pieces)
    for piece in pieces:
        if re.fullmatch(r"(?i)<P>", piece):
            princes -= 1
            if chapters[current]:                      # (a page mark between two <P>s splits twice)
                current = str(len(chapters))
                chapters[current] = []
            continue
        sections = lemegeton_sections(piece)
        for i, s in enumerate(sections):
            if i and not princes:                      # (after the last prince: the closing conjurations)
                current = str(len(chapters))
                chapters[current] = []
            chapters[current].extend(s)
    expect(len(chapters) >= 32, f"Theurgia Goetia: {len(chapters) - 1} princes")
    return chapters


def by_sections(name: str, start: str, stop: str) -> dict:
    t = page(name)
    at = t.find(start)
    expect(at > 0 and t.find(stop) > at, f"{name}: {start} / {stop}")
    t = t[t.rfind("<H", 0, at):t.find(stop)]
    t = t[:t.rfind("<H")] if t.rfind("<H") > t.rfind("</H") else t
    out, held = [], []
    for s in lemegeton_sections(t):                    # (a section that is only a heading leads the next)
        if all(re.fullmatch(r"\*[^*]+\*", p) for p in s):
            held.extend(s)
            continue
        out.append(held + s)
        held = []
    return {str(i + 1): s for i, s in enumerate(out)}


def notoria() -> dict:
    """Ars Notoria in Robert Turner's English (1657), the left column of Peterson's page: a section at each of
    Turner's headings, from the first treatise to the end (his dedication and Peterson's introduction left out)."""
    t = page("notoria/notoria.htm", english_column=True)
    t = t[t.rfind("<H", 0, t.find("Here beginneth the first Treatise")):t.find("[Finis.]")]
    t = t[:t.rfind("<H")]
    out, held = [], []

    def on(level, raw, ps):
        nonlocal held
        title = re.sub(r"(?<=[A-Za-z.])\d+$", "", raw).strip()
        if re.fullmatch(r"\[[^\]]*\]", title):        # (Peterson's headings: "[Some excerpts from Ars Brevis]")
            title = ""
        label = clean(title).replace("*", "").strip()
        lines = ([f"*{label}*"] if label else []) + list(ps)
        if not ps:                                     # (a heading with nothing under it leads the next)
            held += lines
            return
        out.append(held + lines)
        held = []
    walk(t, on)
    return {str(i + 1): s for i, s in enumerate(out)}


def lemegeton() -> None:
    SUPPLIED["keep"] = True
    try:
        books = {"Goetia": goetia(), "Theurgia Goetia": theurgia(),
                 "Ars Paulina": by_sections("solomon/paulina.htm", "Here Beginneth", "So Endeth the second Part"),
                 "Ars Almadel": by_sections("solomon/almadel.htm", "Here beginneth the fourth part",
                                            "So endeth the Booke Almadel")}
    finally:
        SUPPLIED["keep"] = False
    sources = {b: "Lemegeton (Sloane 3825), ed. Joseph H. Peterson" for b in books}
    books["Ars Notoria"] = notoria()                   # (Turner's printed English: his brackets are glosses)
    sources["Ars Notoria"] = "trans. Robert Turner (1657)"
    save("lemegeton", {b: {c: merged(ps) for c, ps in chs.items() if ps} for b, chs in books.items()}, sources)


def chapters_at(t: str, starts, first: str = None, skip=lambda title: False) -> dict:
    """A chapter at each heading `starts` accepts (it may return the chapter's own name, else they're numbered); the
    other headings are italic lines inside the chapter. Text before the first such heading goes in chapter `first`,
    or is left out."""
    chapters = {first: []} if first is not None else {}
    state = {"chap": first}
    h = re.search(r"(?i)<h[1-5]\b", t)
    if first is not None and h:
        chapters[first].extend(paras(t[:h.start()]))

    def on(level, raw, ps):
        title = re.sub(r"(?<=[A-Za-z.:\]])\d+$", "", raw).strip()
        name = starts(title)
        if name:
            state["chap"] = name if isinstance(name, str) else str(len([c for c in chapters if c != first]) + 1)
            expect(state["chap"] not in chapters, f"chapter {state['chap']} twice")
            chapters[state["chap"]] = []
        if state["chap"] is None:
            return
        label = "" if skip(title) or FIGURE.search(title) else \
            clean(re.sub(r"^\[(.*)\]\.?$", r"\1", title)).replace("*", "").strip(" .:-")
        if label and len(label.split()) >= 3 and not english(label):     # (not "THEOREM IX", "APPENDIX I")
            label = ""
        chapters[state["chap"]].extend(([f"*{label}*"] if label else []) + list(ps))
    walk(t, on)
    return {c: ps for c, ps in chapters.items() if ps}


def between(name: str, start: str, stop: str = None, column=False) -> str:
    t = page(name, column)
    at = t.find(start)
    expect(at >= 0, f"{name}: {start!r}")
    end = t.find(stop, at) if stop else len(t)
    expect(end > at, f"{name}: {stop!r}")
    return t[t.rfind("<H", 0, at) if t.rfind("<H", 0, at) > t.rfind(">", 0, at) - 400 else at:end]


# ── The Sword of Moses (Gaster, 1896) ──────────────────────────────────────
# Gaster's translation: its three parts and his two appendices (fragments of the same kind), a chapter each. Where
# Gaster printed a name in Hebrew letters Peterson writes "X [ABDUHU]": the name, transliterated, is the text.

def sword() -> None:
    t = between("solomon/sword.htm", "I. The Sword of Moses.")
    t = re.sub(r"(?is)<em class=pg[^>]*>.*?</em>", " ", t)
    t = re.sub(r"\bX(?:<SUP>\w+</SUP>)?\s*\[([^\[\]]{1,80})\]", r"\1", t)
    t = t[:t.rfind('<div id="menu"')] if '<div id="menu"' in t else t
    chapters = chapters_at(t, lambda title: bool(re.match(r"(?i)(I{1,3}\.|APPENDIX I{1,2}\.)", title)))
    expect(len(chapters) == 5, f"Sword of Moses: {len(chapters)} parts")
    save("sword", {"The Sword of Moses": {c: merged(ps) for c, ps in chapters.items()}},
         {"The Sword of Moses": "trans. Moses Gaster (1896)"})


# ── Weyer's Pseudomonarchia Daemonum, in Reginald Scot's English (1584) ─────
# The right-hand column (the left is Weyer's Latin). "0" Scot's opening, then a spirit a chapter (each entry begins
# with the spirit's name), then the closing chapters on binding and calling them.

def weyer() -> None:
    t = between("solomon/weyer.htm", "Salomons notes of conjuration", column=1)
    t = re.sub(r"(?is)<P>\s*\[(\d+)\]", r"<P>§§\1§§ ", t)          # (Peterson numbers the entries as Weyer does)
    # (passages Scot left out, which Peterson translated himself, in brackets: not Scot's)
    t = re.sub(r"(?s)(<P>\s*(?:§§\d+§§\s*)?)\[(?:[^\[\]<]|<[^>]*>|\[[^\[\]]*\])*\](?:\s*<SUP>[^<]*</SUP>)?"
               r"(?=\s*(?:<|$))", r"\1", t)
    sections = []
    walk(t, lambda level, raw, body: sections.append((re.sub(r"(?<=[A-Za-z.\]])\d+$", "", raw).strip(), body)))
    chapters, current, catalogue = {"0": []}, "0", True
    for title, body in sections:
        label = clean(re.sub(r"^\[(.*)\]\.?$", r"\1", title)).replace("*", "").strip(" .:")
        if re.match(r"(?i)chapter", label):            # (after the catalogue: a chapter at each of Scot's)
            catalogue = False                          # (numbered on from the last entry)
            current = str(max(int(c) for c in chapters) + 1)
            chapters[current] = []
        if label and english(label) and not re.match(r"(?i)salomons notes|chapter", label):
            chapters[current].append(f"*{label.capitalize() if label.isupper() else label}*")
        for p in body:
            m = re.match(r"§§(\d+)§§\s*(.*)", p, re.S)
            if m and catalogue:                        # (a spirit's entry)
                current = m.group(1)
                expect(current not in chapters, f"Weyer entry {current} twice")
                chapters[current] = []
                p = m.group(2)
            elif m:
                p = m.group(2)
            if p:
                chapters[current].append(p)
    if "1" not in chapters:                            # (Baëll's entry carries no number: it follows the title)
        chapters = {"1": chapters.pop("0"), **chapters}
    entries = [int(c) for c in chapters if c != "0"]
    expect(len(entries) >= 68, f"Weyer: {len(entries)} entries")
    save("weyer", {"Pseudomonarchia Daemonum": {c: merged(ps) for c, ps in chapters.items() if ps}},
         {"Pseudomonarchia Daemonum": "Johann Weyer, trans. Reginald Scot (1584)"})


# ── Sepher Raziel: Liber Salomonis (Sloane 3846, ed. Peterson) ─────────────
# Elizabethan English; its seven books ("treatises"), a chapter each. Its Latin headings with Peterson's English
# ("De tertia Ala. [The third wing.]") keep the English.

def raziel() -> None:
    t = between("raziel/raziel.htm", "Liber Salomonis</H1>", "Here beginneth names that be necessary")
    books = {"first": "1", "secundus": "2", "tertius": "3", "4 booke": "4", "5 booke": "5", "6. booke": "6",
             "7th booke": "7"}

    def starts(title):
        if re.match(r"(?i)liber salomonis", title):
            return "1"
        for key, n in books.items():
            if re.search(rf"(?i)\b{re.escape(key)}\b", title) and n != "1" and \
                    re.match(r"(?i)(liber|here beginneth|heere beginneth)", title):
                return n
        return None
    chapters = chapters_at(t, starts, skip=lambda title: bool(re.match(r"(?i)\[?contents|\[?liber temporum|liber salomonis", title)))
    expect(list(chapters) == [str(n) for n in range(1, 8)], f"Raziel: {list(chapters)}")
    SUPPLIED["keep"] = False
    save("raziel", {"Sepher Raziel": {c: merged(ps) for c, ps in chapters.items()}},
         {"Sepher Raziel": "Liber Salomonis (Sloane 3846), ed. Joseph H. Peterson"})


# ── John Dee ───────────────────────────────────────────────────────────────
# His English works on the archive: De Heptarchia Mystica (Sloane 3191, his own hand; a chapter at each "Cap."), the
# Hieroglyphic Monad (Hamilton-Jones's English, 1947; a theorem a chapter) and his Letter... Apologeticall (1599;
# the letter, then its list of his books and the closing sections). Left out: the Latin works (Tuba Veneris, the
# invocations), the two earlier drafts of the Heptarchia, and the excerpts from Casaubon's True and Faithful Relation.

def dee() -> None:
    hm = between("dee/hm.htm", "Liber primus.</H1>")
    hm = chapters_at(hm, lambda title: (m := re.match(r"(?i)cap(?:ut)?\.?\s*(\d+)", title)) and m.group(1))
    expect(list(hm) == [str(n) for n in range(1, 8)], f"Heptarchia: {list(hm)}")
    monad = between("dee/monad.htm", "by Dr. JOHN DEE")
    monad = chapters_at(monad, lambda title: (m := re.match(r"THEOREM ([IVXL]+)$", title)) and str(roman(m.group(1))))
    expect(list(monad) == [str(n) for n in range(1, 25)], f"Monad: {list(monad)}")
    letter = between("dee/aletter.htm", "A LETTER,</H1>")
    letter = chapters_at(letter, lambda title: not re.match(r"(?i)some, perfectly|iohn dee", title),
                         skip=lambda title: bool(re.match(r"(?i)a letter,?$", title)))
    save("dee", {b: {c: merged(ps) for c, ps in chs.items()} for b, chs in
                 (("De Heptarchia Mystica", hm), ("The Hieroglyphic Monad", monad), ("A Letter Apologeticall", letter))},
         {"De Heptarchia Mystica": "John Dee (Sloane 3191), ed. Joseph H. Peterson",
          "The Hieroglyphic Monad": "John Dee, trans. J. W. Hamilton-Jones (1947)",
          "A Letter Apologeticall": "John Dee (1599)"})


BUILDS = {"agrippa": agrippa, "arbatel": arbatel, "heptameron": heptameron, "abramelin": abramelin,
          "testament": testament, "keyofsolomon": key_of_solomon, "lemegeton": lemegeton, "sword": sword,
          "weyer": weyer, "raziel": raziel, "dee": dee}


def main(names: list) -> None:
    for name in names or BUILDS:
        print(name)
        BUILDS[name]()


if __name__ == "__main__":
    main(sys.argv[1:])
