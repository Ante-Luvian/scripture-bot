"""
Medieval English poetry, in the original Middle English (and Spenser) -> data/english/*.json (book -> chapter ->
verse, each chapter's first verse led by its title in italics); the Arthurian ones go to data/arthurian/:

  from the National Library of Scotland's transcription of the Auchinleck manuscript (c. 1331-40),
  auchinleck.nls.uk: its romances, saints' lives and shorter poems, each a book of one chapter, a verse a
  paragraph of the manuscript (its paraph marks or the edition's breaks). Lines lost from the manuscript are
  shown once as [...]; the edition's notes, folio and line numbers are left out.

    python scripts/build_english.py
"""
import html
import json
import math
import re
import sys
import time
import unicodedata
import urllib.request

import build_arthurian as ba

ROOT = ba.ROOT
OUT = ROOT / "data" / "english"
AUCH = ROOT / "scripts" / ".cache" / "auchinleck"
UA = {"User-Agent": "Mozilla/5.0 (ScriptureBot corpus builder, personal Discord bot)"}


def save(name: str, source: str, books: dict, out=OUT, book_sources=None) -> None:
    """Every book here is cited by line ("line_chunked": the bot reads "Sir Orfeo 233" as line 233); a source is
    short, editor and date (tests/test_citations.py), and book_sources gives each book its own in a mixed file."""
    out.mkdir(parents=True, exist_ok=True)
    payload = {"source": source, "line_chunked": True, "books": books}
    if book_sources:
        payload["book_sources"] = book_sources
    (out / f"{name}.json").write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    for book, chapters in books.items():
        words = sum(len(v.split()) for c in chapters.values() for v in c.values())
        print(f"{book}: {len(chapters)} chapters, {words:,} words -> {out.relative_to(ROOT).as_posix()}/{name}.json")


# ── The Auchinleck manuscript ──────────────────────────────────────────────

# page -> the book's name in the bot (the edition's own title, its thorns and yoghs kept, where it is the usual one)
AUCHINLECK = {
    "abc": "Alphabetical Praise of Women", "adameve": "The Life of Adam and Eve", "alisaunder": "Kyng Alisaunder",
    "amiloun": "Amis and Amiloun", "assumpt": "The Assumption of the Blessed Virgin",
    "bernard": "The Sayings of St Bernard", "beues": "Sir Beues of Hamtoun",
    "bodysoul": "The Debate of the Body and the Soul", "clerkvirg": "The Clerk Who Would See the Virgin",
    "degare": "Sir Degare", "floris": "Floris and Blancheflour", "foes": "The Four Foes of Mankind",
    "freine": "Lay le Freine", "gregory": "The Legend of Pope Gregory", "guy_cp": "Guy of Warwick",
    "guy_st": "Guy of Warwick (the stanzas)", "harrow": "The Harrowing of Hell",
    "horn": "Horn Childe and Maiden Rimnild", "katerine": "Seynt Katerine",
    "magdalen": "The Life of St Mary Magdalene", "mergrete": "Seynt Mergrete",
    "nativity": "The Nativity and Early Life of Mary", "otuel": "Otuel a Knight",
    "pater": "The Paternoster", "patrick": "St Patrick's Purgatory", "penny": "A Peniworth of Witt",
    "philos": "The Sayings of the Four Philosophers", "psalm": "Dauid the King", "reinbrun": "Reinbroun",
    "richard": "King Richard", "roland": "Roland and Vernagu", "sages": "The Seven Sages of Rome",
    "saute": "How Our Lady's Sauter Was First Found", "simonie": "The Simonie",
    "sins": "On the Seven Deadly Sins", "smc": "The Short English Metrical Chronicle",
    "speculum": "Speculum Gy de Warewyke", "tars": "The King of Tars",
    "thrush": "The Thrush and the Nightingale",
    # Arthurian: -> data/arthurian
    "tristrem": "Sir Tristrem", "arthur": "Of Arthour and of Merlin",
}
AUCH_ARTHURIAN = {"tristrem", "arthur"}
# left out: the Battle Abbey Roll (a list of Norman names) and the Wenche that Loved the King (two lines survive);
# Sir Orfeo comes from Sisam instead (the same text, its lost opening supplied from Harley 3810)
LACUNA = "[…]"


def auch_page(name: str) -> str:
    path = AUCH / f"{name}.html"
    if not path.exists():
        AUCH.mkdir(parents=True, exist_ok=True)
        req = urllib.request.Request(f"https://auchinleck.nls.uk/mss/{name}.html", headers=UA)
        path.write_bytes(urllib.request.urlopen(req, timeout=60).read())
        time.sleep(1)
    return path.read_text(encoding="utf-8", errors="replace")


def auch_text(s: str) -> str:
    s = re.sub(r'(?is)<font color="red">.*?</font>', "", s)               # folio marks {f.300ra}
    s = re.sub(r"\{(?:stub )?f\.[^}]*\}", "", s)
    s = re.sub(r'(?is)<font color="#E1DDD0">.*?</font>', "", s)           # the line number's padding
    s = re.sub(r"(?is)<a\b[^>]*>.*?</a>", "", s)                          # facsimile and note icons
    # italics (the Latin): hugging their words, and none left open over a line break (Discord shows neither)
    s = re.sub(r"(?is)<i>(.*?)</i>", lambda m: f"*{m.group(1).strip()}*" if m.group(1).strip() else " ", s)
    s = re.sub(r"(?is)</?i>", "", s)
    s = html.unescape(re.sub(r"<[^>]+>", "", s))
    s = s.replace(" ", " ")
    s = re.sub(r"\*\s*\*", "", s)
    s = re.sub(r"\s+", " ", s).strip()
    if s.count("*") % 2:
        s = s.replace("*", "")
    return s


MAX_LINES = 30          # a longer paragraph is cut into passages of about this many lines (at a couplet)


def passages(paras: list) -> list:
    """[(first line number, [(number, line)])] -> the same with no passage over MAX_LINES lines (cut evenly)."""
    out = []
    for start, lines in paras:
        n = len(lines)
        if n <= MAX_LINES + 10:
            out.append((start, lines))
            continue
        pieces = -(-n // MAX_LINES)
        size = -(-n // pieces)
        size += size % 2                                                      # (keep couplets together)
        for i in range(0, n, size):
            out.append((start if i == 0 else lines[i][0], lines[i:i + size]))
    return out


def line_chunked(title: str, paras: list, part: int = 1, heading: str = "") -> dict:
    """{"<part>.<first line>": {"1": passage}} (the bot's line-chunked layout: "Sir Orfeo 1:233" is the passage
    holding line 233, "Troilus 3:1" the first of Book III); lost lines shown once as [...], the title (or the
    part's heading) leading its first passage."""
    book = {}
    title = title if part == 1 and not heading else heading
    for i, (start, lines) in enumerate(passages(paras)):
        shown = []
        for _, x in lines:
            if not (x == LACUNA and shown and shown[-1] == LACUNA):
                shown.append(x)
        text = "\n".join(shown)
        if i == 0 and title:
            text = f"*{title}*\n{text}"
        if book and start <= int(list(book)[-1].split(".")[1]):              # (lines sharing a number: one passage)
            last = list(book)[-1]
            book[last]["1"] += "\n\n" + text
            print(f"  {title}: the passage at line {start} joins {last} (numbered no later)")
            continue
        book[f"{part}.{start}"] = {"1": text}
    return book


def skeat_poem(body: str) -> list:
    """numbered_poem for Skeat's Chaucer (Oxford, 1894-7) on Gutenberg: his line numbers in
    <div class="rel"><div class="linenum35">n</div></div> before their line, his stanza numbers ("2. To thee
    clepe I") dropped, and his footnoted variant readings (outside the poem's divs); a section heading (<h2>)
    kept in italics, and lines from a parallel text set in smaller type left out (the Legend's Prologue)."""
    body = re.sub(r"(?is)<h2[^>]*>(.*?)</h2>",
                  lambda m: f'<div class="poem"><p class="heading">{ba.title_case(text(m.group(1)))}</p></div>', body)
    body = keep(body, "div", "poem")
    body = re.sub(r'(?is)<p\b[^>]*>\s*(?:<span class="pagenum"[^>]*>[^<]*</span>\s*)?<span class="smaller">.*?</p>',
                  "", body)
    body = re.sub(r'(?is)<div class="rel">\s*<div class="linenum\d*[^"]*">\s*(\d+)\s*</div>\s*</div>\s*(<p\b[^>]*>)',
                  r'\2<span class="linenum">\1</span>', body)
    body = drop(body, "div", "rel")
    body = re.sub(r'(?is)(<p class="[^"]*stanza[^"]*">(?:\s*<span class="(?:pagenum|linenum)"[^>]*>[^<]*</span>)*\s*)'
                  r"(?:<a\b[^>]*>)?\d+(?:</a>)?\.\s*", r"\1", body)               # (his stanza numbers)
    paras = numbered_poem(body)
    # (and a book's first, which has no stanza class)
    # (and his marks for lines in one text only, *, or the same in both, †)
    return [(s, [(n, x if n == 0 else re.sub(r"^\d+\.\s+(?=\S)", "", x).lstrip("*†")) for n, x in lines])
            for s, lines in paras]


def number_lines(marks: list) -> list:
    """Each line's number, from the edition's (on every fifth line or so: marks[i] is None between): between two
    marks counted evenly, so a text numbered by long lines (two of the page's half-lines, as Seynt Katerine) or
    after a gap in another edition's numbering (the fragments of Kyng Alisaunder) still comes out right; before
    the first and after the last, at the rate of the nearest stretch."""
    known = [(i, m) for i, m in enumerate(marks) if m is not None]
    if not known:
        return list(range(1, len(marks) + 1))
    if len(known) == 1:
        (i0, m0), = known
        return [max(m0 + i - i0, 1) for i in range(len(marks))]
    out, k = [], 0
    for i in range(len(marks)):
        while k < len(known) - 2 and i > known[k + 1][0]:
            k += 1
        (a, ma), (b, mb) = known[k], known[k + 1]
        rate = (mb - ma) / (b - a)
        if not 0 < rate <= 1.5:                                  # (a gap, or the numbering starting again: by ones)
            rate = 1
        # (rounded up: the half-line after line 210 begins line 211, the one before it is 210's first half)
        if marks[i] is not None:
            out.append(marks[i])
        elif i > b:
            out.append(mb + math.ceil((i - b) * rate - 1e-9))
        else:
            out.append(ma + math.ceil((i - a) * rate - 1e-9))
    return [max(x, 1) for x in out]


def auchinleck(name: str) -> list:
    """[(first line number, [lines])] of one text, a paragraph each (a paraph ¶ or a gap in the edition starts
    one), the lines numbered as the edition numbers them."""
    t = auch_page(name)
    t = t[re.search(r"<h1[^>]*>", t).start():t.rfind("</td></tr></table>")]
    t = re.sub(r'(?is)<div id="myLayer\w+" class="myStyle">.*?</table>\s*</div>', "", t)   # the editor's notes
    t = re.sub(r"(?is)<h\d[^>]*>.*?</h\d>", "", t)
    items = []                                     # ("break",) | ("note", text) | ("line", text, edition's number)
    for m in re.finditer(r'(?is)<div class="divvy50">(.*?)</div>|<span class="mssspan">\s*L?(\d*)(.*?)</span>|<p\b[^>]*>',
                         t):
        if m.group(0).lower().startswith("<p"):
            items.append(("break",))
            continue
        raw = m.group(1) if m.group(1) is not None else m.group(3)
        line = auch_text(raw)
        if not line:
            continue
        mark = int(m.group(2)) if m.group(2) else None
        line = re.sub(r"\s*\{\d+\}\s*", " ", line).strip()                  # (another edition's line numbers)
        note = re.fullmatch(r"\{\s*\[?(.*?)\]?\s*\}", line)                  # "{12 lines lost where miniature cut out}"
        if re.search(r"(?i)<font size", raw) or note:                       # "Edinburgh Fragments Commence"
            items.append(("note", f"*[{(note.group(1) if note else line).rstrip('.')}]*"))
            continue
        if line.startswith("¶"):
            items.append(("break",))
            line = line.lstrip("¶ ").strip()
        line = re.sub(r"^\.{3,}\s*", "… ", line.replace("¶", "").strip())
        if re.fullmatch(r"[.\s…]+", line):                                  # a line lost
            line = LACUNA
        items.append(("line", line, mark))
    for i, item in enumerate(items):                 # a speaker, "dominus ait.", a paragraph to itself: unnumbered
        if (item[0] == "line" and item[2] is None and item[1] != LACUNA
                and (re.fullmatch(r"\*[^*]+\*", item[1]) or len(item[1].split()) <= 3)
                and 0 < i < len(items) - 1 and items[i - 1] == ("break",) and items[i + 1] == ("break",)):
            items[i] = ("note", item[1] if item[1].startswith("*") else f"*{item[1]}*")
    return group_lines(items)


# ── Gutenberg editions: tools ──────────────────────────────────────────────

def drop(s: str, tag: str, cls: str = "") -> str:
    """s without every <tag class="...cls..."> element (and what is nested in it), however deeply nested."""
    opener = re.compile(rf'(?is)<{tag}\b[^>]*class="[^"]*\b(?:{cls})\b[^"]*"[^>]*>' if cls else rf"(?is)<{tag}\b[^>]*>")
    tok = re.compile(rf"(?is)<{tag}\b[^>]*?(/?)>|</{tag}\s*>")
    out, pos = [], 0
    while True:
        m = opener.search(s, pos)
        if not m:
            break
        out.append(s[pos:m.start()])
        if m.group(0).endswith("/>"):
            pos = m.end()
            continue
        depth, j = 1, m.end()
        while depth:
            k = tok.search(s, j)
            if not k:
                j = len(s)
                break
            if k.group(0).startswith("</"):
                depth -= 1
            elif not k.group(1):
                depth += 1
            j = k.end()
        pos = j
    out.append(s[pos:])
    return "".join(out)


def keep(s: str, tag: str, cls: str) -> str:
    """The insides of every <tag class="...cls..."> element of s, in order (nesting allowed)."""
    return "".join(keep_each(s, tag, cls))


def keep_each(s: str, tag: str, cls: str) -> list:
    """[the inside of each <tag class="...cls..."> element of s], in order."""
    opener = re.compile(rf'(?is)<{tag}\b[^>]*class="[^"]*\b(?:{cls})\b[^"]*"[^>]*>')
    tok = re.compile(rf"(?is)<{tag}\b[^>]*?(/?)>|</{tag}\s*>")
    out, pos = [], 0
    while (m := opener.search(s, pos)):
        depth, j = 1, m.end()
        while depth:
            k = tok.search(s, j)
            if not k:
                k = None
                break
            depth += -1 if k.group(0).startswith("</") else (0 if k.group(1) else 1)
            j = k.end()
        end = k.start() if k else len(s)
        out.append(s[m.end():end] + "\n")
        pos = j
    return out


def text(s: str) -> str:
    """Markup -> one line of text; every tag unwrapped (in these editions italic marks the editor's expansion of an
    abbreviation, so is not shown)."""
    s = re.sub(r"(?i)<br\s*/?>", " ", s)
    s = html.unescape(re.sub(r"<[^>]+>", "", s)).replace(" ", " ")
    # a mark left over a letter once accents are composed (l̴, r̛): an abbreviation sign, dropped
    s = "".join(c for c in unicodedata.normalize("NFC", s) if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", s).strip()


def heading_case(s: str) -> str:
    """An editor's heading in capitals -> title case, its Roman numerals kept ("BOOK II" -> "Book II")."""
    return re.sub(r"(?i)\b(?=\w\w)L?X{0,3}(?:IX|IV|V?I{0,3})\b", lambda m: m.group(0).upper(), ba.title_case(s))


def gutenberg_poem(body: str, **kw) -> list:
    """numbered_poem for Gutenberg's usual verse markup: <div class="stanza"> of <span class="i0">line<br></span>,
    the line numbers <span class="linenum">n</span> before or inside."""
    body = re.sub(r'(?is)<span class="i\d+[^"]*">(.*?)<br\s*/?>\s*</span>', r"<p>\1</p>", body)
    body = re.sub(r'(?i)<div class="stanza[^"]*">', '<p class="stanza"></p>', body)
    return numbered_poem(body, **kw)


def gutenberg_file(n: int, name: str) -> str:
    """A further file of a Gutenberg HTML edition split into several (#30282's poems.html)."""
    path = ba.CACHE / f"{n}_{name}"
    if not path.exists():
        req = urllib.request.Request(f"https://www.gutenberg.org/files/{n}/{n}-h/{name}", headers=UA)
        path.write_bytes(urllib.request.urlopen(req, timeout=120).read())
    return path.read_text(encoding="utf-8")


def numbered_poem(body: str, junk: str = "sidenote|pagenum|headnote|mynote|footnote|fnanchor",
                  line_tag: str = "p", stanza_cls: str = "stanza|section", section=None) -> list:
    """[(first line number, [(number, line)])] of a poem whose lines are <p>s (a stanza opening at class "stanza"),
    numbered here and there by <span class="linenum">n</span>: the numbers between counted from those, and a
    section heading (the regex `section`, naming the heading's text "name") put in italics before the stanza it
    opens."""
    for cls in junk.split("|"):
        body = drop(body, "span", cls)
        body = drop(body, "p", cls)
        body = drop(body, "div", cls)
    body = re.sub(r"(?is)<sup>\s*[\d*†‡]+\s*</sup>", "", body)              # (a footnote's number)
    body = drop(body, "a", r"tag|texttag|fnanchor")                   # (footnote marks; not "noteref", which
    #                                                                      wraps words of the text)
    # a line number standing before its line goes into it
    body = re.sub(rf'(?is)(<span class="linenum[^"]*">.*?</span>)\s*(<{line_tag}\b[^>]*>)', r"\2\1", body)
    items = []
    pat = rf"<{line_tag}\b(?P<attrs>[^>]*)>(?P<inner>.*?)</{line_tag}>"
    if section:                                                      # (its own pattern names its heading "name")
        pat = f"(?P<sec>{section})|{pat}"
    for m in re.finditer(pat, body, re.I | re.S):
        if section and m.group("sec"):
            items.append(("break",))
            items.append(("note", f"*{heading_case(text(m.group('name')))}*"))
            continue
        attrs, inner = m.group("attrs"), m.group("inner")
        if re.search(r'class="heading"', attrs or ""):                       # (a section's heading, unnumbered)
            items.append(("break",))
            items.append(("note", f"*{text(inner)}*"))
            continue
        num = re.search(r'(?is)<span class="linenum[^"]*">(.*?)</span>', inner)
        mark = None
        if num:
            d = re.search(r"\d+", text(num.group(1)))
            mark = int(d.group()) if d else None
            inner = inner[:num.start()] + inner[num.end():]
        line = text(inner)
        if re.search(rf'class="[^"]*\b(?:{stanza_cls})\b', attrs or ""):
            items.append(("break",))
        if line and re.fullmatch(r"[\s.…\[\]*]+", line):                    # (the editor's dots: lines lost)
            line = LACUNA
        if line:
            items.append(("line", line, mark))
    return group_lines(items)


def group_lines(items: list) -> list:
    """[("break",) | ("note", text) | ("line", text, the edition's number or None)] -> [(first line, [(n, line)])]"""
    numbers = iter(number_lines([x[2] for x in items if x[0] == "line"]))
    paras, cur, start = [], [], 0

    def flush():
        if all(n == 0 for n, _ in cur):
            return
        if any(x != LACUNA for _, x in cur):
            paras.append((start, cur[:]))
        elif paras:
            paras[-1][1].extend(cur)
        cur.clear()

    for item in items:
        if item[0] == "break":
            flush()
        elif item[0] == "note":
            flush()
            cur.append((0, item[1]))
        else:
            n = next(numbers)
            # a drop capital and the capital after it, "GOd", "MAn": the second as the word goes on
            item = (item[0], re.sub(r"^([A-Z])([A-Z])(?=[a-z])", lambda k: k.group(1) + k.group(2).lower(),
                                    item[1]))
            if not cur or cur[-1][0] == 0:
                if paras and n <= paras[-1][0]:
                    start = paras[-1][0]
                    cur[:0] = paras.pop()[1]
                else:
                    start = n
            cur.append((n, item[1]))
    flush()
    if cur and paras:
        paras[-1][1].extend((paras[-1][1][-1][0], x) for _, x in cur)
    return paras


# ── Pearl, Cleanness, Patience ─────────────────────────────────────────────

def pearl_poet() -> dict:
    """Morris's text (EETS 1, 1864, rev. 1869), Gutenberg #30282: the three poems of the Gawain manuscript besides
    Sir Gawain, each line-numbered as he numbers it; his fitt numbers lead their stanzas, his sidenotes, headings
    and notes are left out."""
    t = gutenberg_file(30282, "poems.html")
    out = {}
    for anchor, title in (("pearl", "Pearl"), ("cleanness", "Cleanness"), ("patience", "Patience")):
        m = re.search(rf'(?is)<h3><a name="{anchor}"[^>]*>.*?</h3>(.*?)<div class="notes">', t)
        out[title] = line_chunked(title, numbered_poem(
            m.group(1), section=r'<h4[^>]*><a name="\w+_[IVXL]+"[^>]*>\s*(?P<name>[IVXL]+)\.?\s*</a>\s*</h4>'))
    return out


def build_auchinleck():
    english, arthurian = {}, {}
    for page, title in AUCHINLECK.items():
        (arthurian if page in AUCH_ARTHURIAN else english)[title] = line_chunked(title, auchinleck(page))
    src = "the Auchinleck manuscript (c. 1335), National Library of Scotland"
    save("auchinleck", src, english)
    save("auchinleck_arthur", src, arthurian, ROOT / "data" / "arthurian")


def havelok() -> dict:
    """Skeat's text (EETS ES 4, 1868), Gutenberg #32049, numbered as he numbers it; his sidenotes, headings,
    footnotes and notes are left out."""
    t = ba.gutenberg(32049)
    body = t[t.index('<div class="havelok">'):t.index('<div class="notes">')]
    paras = numbered_poem(body)
    # (his * on an emended word: the word kept, the mark not)
    paras = [(s, [(n, re.sub(r"\s*\*", "", x) if n else x) for n, x in lines]) for s, lines in paras]
    return {"Havelok the Dane": line_chunked("Havelok the Dane", paras)}


def king_horn() -> dict:
    """McKnight's King Horn (EETS 14, re-ed. 1901), Gutenberg #42713, from the three manuscripts he prints side by
    side the Cambridge one (Gg. 4. 27. 2), the oldest and his first column; a paragraph each of his groups. (His
    Floris and Blauncheflur and Assumption are in the Auchinleck manuscript's texts already.)"""
    t = gutenberg_file(42713, "KingHorn_KH.html")
    t = re.sub(r'\s*=\s*"', '="', t)                                      # (this file writes class = "...")
    t = t[t.index('id="kinghorn"'):t.index('<div class="notes"')]
    t = re.sub(r'(?is)<p>\[<i>No gap in MS\.</i>.*?\]</p>', "<p>. . .</p>", t)    # (a gap the MS doesn't mark)
    blocks = re.findall(r'(?is)<div class="onetext msgg[^"]*">(.*?)</div>', t)
    body = "".join(f'<p class="stanza"></p>{b}' for b in blocks)
    return {"King Horn": line_chunked("King Horn", numbered_poem(body, junk="sidenote|pagenum|headnote|mynote|"
                                                                        "footnote|textnote|folionote"))}


def torrent() -> dict:
    """Adam's text (EETS ES 51, 1887), Gutenberg #35190, the Chetham MS., numbered as he numbers it; his stanza
    numbers, sidenotes, line notes and headings left out, and the printed fragments after it."""
    t = ba.gutenberg(35190)
    start = t.index('<div class="torrent">')
    t = t[start:t.index("THE FRAGMENTS", start)]
    t = re.sub(r'(?i)<div class="stanza">', '<p class="stanza"></p>', t)
    t = re.sub(r"(?is)<h5\b.*?</h5>|<sup>.*?</sup>", "", t)               # (stanza numbers; abbreviation marks)
    t = re.sub("[̴̵̶]", "", t)                              # (a stroke through a letter, likewise)
    return {"Torrent of Portyngale": line_chunked("Torrent of Portyngale", numbered_poem(
        t, junk="sidenote|pagenum|headnote|mynote|footnote|linenote|subhead|halliwell"))}   # (Halliwell's numbers)


def genesis_exodus() -> dict:
    """Morris's text (EETS 7, rev. 1873), Gutenberg #50685, each line numbered as he numbers it, a passage a
    section of his (his headings, sidenotes and footnotes left out); his long s printed as s."""
    t = ba.gutenberg(50685)
    start = t.index("THE STORY OF GENESIS AND EXODUS, ETC.")
    t = t[start:re.search(r"(?i)<h3[^>]*>\s*NOTES\.", t[start:]).start() + start]
    t = drop(t, "div", "foot|rel")
    t = drop(t, "span", "pagenum")
    t = re.sub(r"(?is)<a [^>]*href=\"#Nt_\d+\"[^>]*>.*?</a>", "", t)         # footnote marks
    items = []
    for table in re.findall(r"(?is)<table[^>]*>(.*?)</table>", t):
        items.append(("break",))
        cells = "".join(re.findall(r'(?is)<td style="width:24em">(.*?)</td>', table))
        for line, n in re.findall(r'(?is)(.*?)<a id="L(\d+)"></a>', cells):
            line = text(line).replace("ſ", "s")
            if line:
                items.append(("line", line, int(n)))
    return {"Genesis and Exodus": line_chunked("Genesis and Exodus", group_lines(items))}


def wrights_wife() -> dict:
    """Furnivall's text (EETS 12, 1865), Gutenberg #17400, numbered as he numbers it; his sidenotes and headings
    left out."""
    t = ba.gutenberg(17400)
    start = t.index("<h2>THE WRIGHT'S CHASTE WIFE.</h2>")
    t = t[start:t.index("<h2>NOTES.</h2>", start)]
    return {"The Wright's Chaste Wife": line_chunked("The Wright's Chaste Wife", gutenberg_poem(
        t, junk="sidenote|pagenum|headnote|leafinfo|footnote"))}


ROMAN_NUMS = ["I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X", "XI", "XII"]


def in_books(title: str, t: str, book_re: str = r"(?is)<h2[^>]*>\s*(?:<span[^>]*>)?\s*BOOK\s+([IVXL]+)\.?",
             reader=None) -> dict:
    """A poem in books, each numbered from 1 ("Troilus 3:1"): its text t cut at the books' headings, each read
    by reader (Skeat's markup by default)."""
    reader = reader or skeat_poem
    heads = list(re.finditer(book_re, t))
    out = {}
    for i, h in enumerate(heads):
        n = ba.roman(h.group(1))
        part = t[h.end():heads[i + 1].start() if i + 1 < len(heads) else len(t)]
        heading = f"{title} — Book {h.group(1).upper()}" if i == 0 else f"Book {h.group(1).upper()}"
        out.update(line_chunked(title, reader(part), part=n, heading=heading))
    return out


def verse_divs(body: str, junk: str = "sidenote|pagenum|footnote") -> list:
    """numbered_poem for the <div class="stanza"> of <div class="verse ..."> markup (Macaulay's Gower, Jamieson's
    Wallace)."""
    body = drop(body, "a", "fnanchor")
    for cls in junk.split("|"):
        body = drop(body, "div", cls)
    out = []
    for st in keep_each(body, "div", "stanza|stanzabreak"):
        out.append('<p class="stanza"></p>' + "".join(
            f"<p>{x}</p>" for x in re.findall(r'(?is)<div class="verse[^"]*">(.*?)</div>', st)))
    return numbered_poem("".join(out))


WALLACE_BOOKS = ["FYRST", "SECUND", "THRYD", "FEYRD", "FYFTE", "SEXT", "SEWYND", "AUCHT", "NYNTE", "TEND",
                 "ELEUENTH"]


def wallace() -> dict:
    """Blind Hary's Wallace (Scots, about 1477), ed. John Jamieson (1820, repr. 1869), Gutenberg #49580: eleven
    books, each numbered as he numbers it; his arguments, notes and sidenotes left out."""
    t = ba.gutenberg(49580)
    start = t.index("BUKE FYRST.")
    start = t.rfind("<h2", 0, start)
    t = t[start:re.search(r"(?is)<h2[^>]*>\s*(?:<a[^>]*>\s*(?:</a>)?\s*)?NOTES\s+ON\s+WALLACE", t).start()]
    heads = list(re.finditer(r"(?is)<h2[^>]*>\s*(?:<a[^>]*>)?\s*BUKE\s+(\w+)\.\s*(?:</a>)?\s*</h2>", t))
    out = {}
    for i, h in enumerate(heads):
        n = WALLACE_BOOKS.index(h.group(1).upper()) + 1
        part = t[h.end():heads[i + 1].start() if i + 1 < len(heads) else len(t)]
        heading = (f"Wallace — Book {ROMAN_NUMS[n - 1]}" if i == 0 else f"Book {ROMAN_NUMS[n - 1]}") \
            if n <= 12 else ""
        out.update(line_chunked("Wallace", verse_divs(part), part=n, heading=heading))
    return {"Wallace": out}


def bruce() -> dict:
    """Barbour's Bruce (Scots, 1375), ed. W. M. Mackenzie (1909), Gutenberg #44292: twenty books, each numbered
    as he numbers it; his headings, sidenotes and notes left out."""
    t = ba.gutenberg(44292)
    start = t.index("BOOK I.</h2>")
    start = t.rfind("<h2", 0, start)
    end = re.search(r"(?is)<h2[^>]*>(?!\s*BOOK)", t[start + 10:]).start() + start + 10
    def rubric(m):                                       # (the manuscript's rhymed rubric, *How the King slew...)
        return '<p class="heading">' + " ".join(text(x) for x in re.findall(
            r'(?is)<span class="i\d+">(.*?)<br', drop(m.group(1), "a", "fnanchor"))).lstrip("*") + "</p>"

    def reader(part):
        paras = gutenberg_poem(re.sub(r'(?is)<div class="stanza header">(.*?)</div>', rubric, drop(part, "h3")),
                               junk="sidenote|pagenum|footnote")
        # (his * on lines supplied from another text: the line kept, the mark not)
        return [(s, [(n, x.lstrip("*") if n else x) for n, x in lines]) for s, lines in paras]
    return {"The Bruce": in_books("The Bruce", t[start:end], r"(?is)<h2[^>]*>\s*BOOK\s+([IVXL]+)\b", reader)}


def troilus() -> dict:
    """Skeat's text (Chaucer's Works, vol. II, 1894), Gutenberg #44833, each book numbered as he numbers it; his
    notes left out."""
    t = ba.gutenberg(44833)
    start = re.search(r"TROILUS\s+AND\s+CRISEYDE\.", t).start()
    t = t[start:re.search(r"NOTES\s+TO\s+BOETHIUS", t[start:]).start() + start]
    return {"Troilus and Criseyde": in_books("Troilus and Criseyde", t)}


def fame_and_legend() -> dict:
    """Skeat's House of Fame and Legend of Good Women (Chaucer's Works, vol. III, 1894), Gutenberg #45027, each
    numbered straight through as he numbers them; of the Legend's Prologue his later text, B (the one his
    numbering of the legends follows), not A."""
    t = ba.gutenberg(45027)
    fame = re.search(r"THE\s+HOUS\s+OF\s+FAME\.", t).start()
    legend = [m.start() for m in re.finditer(r"THE\s+LEGEND\s+OF\s+GOOD\s+WOMEN\.", t) if m.start() > fame][0]
    end = re.search(r"A\s+TREATISE\s+ON\s+THE\s+ASTROLABE\.", t[legend:]).start() + legend
    lg = t[legend:end]
    b = lg.index("The prologe of .ix.", lg.index("Explicit prohemium"))           # (text B)
    return {"The House of Fame": line_chunked("The House of Fame", skeat_poem(t[fame:legend])),
            "The Legend of Good Women": line_chunked("The Legend of Good Women", skeat_poem(lg[b:]))}


def skeat1_poem(body: str, headings=None) -> list:
    """numbered_poem for Skeat's vol. I (the Romaunt, the minor poems): his line numbers in
    <div class="x1"><div class="linenumr">n</div></div> before their line (a sidenote there is dropped), only
    the first column of a table (the English, not Le Roman de la Rose beside it), only the stanzas (not his
    variant readings); a heading of his in a stanza to itself ("FRAGMENT A.", "The Proem.") kept in italics."""
    headings = headings or SKEAT_HEADING
    body = re.sub(r"(?is)<tr\b[^>]*>\s*<td\b[^>]*>(.*?)</td>\s*<td\b.*?</tr>", r"\1", body)   # (first column)
    # a drop capital (an image) into its line: <div class="droppo"><img alt="W"></div>...<p>HAT -> <p>WHAT
    body = re.sub(r'(?is)<div class="droppo">\s*<img[^>]*\balt="(\w)"[^>]*>\s*</div>(.*?)(<p\b[^>]*>)', r"\2\3\1",
                  body)
    body = re.sub(r'(?is)<div class="x1">\s*<div class="linenumr"[^>]*>\s*(\d+)\s*</div>\s*</div>\s*(<p\b[^>]*>)',
                  r'\2<span class="linenum">\1</span>', body)
    body = drop(body, "div", "x1")
    out = []

    def heading(m):
        h = text(m.group(1))
        if not headings.match(h):                                     # (an italic refrain: a line)
            return m.group(0)
        h = re.sub(r"(?<=Fragment )([a-c])\b", lambda k: k.group(1).upper(), ba.title_case(h).rstrip("."))
        return f'<p class="heading">{h}</p>'

    for st in keep_each(body, "div", "stanza"):
        st = re.sub(r"(?is)<p\b[^>]*>\s*(<b>[^<]*</b>|<i>(?:(?!</?i>|</p>).)*</i>\.?|[IVX]+\.)\s*</p>", heading, st)
        out.append(f'<p class="stanza"></p>{st}')
    return numbered_poem("".join(out))


# Skeat's headings within a poem (his and the manuscripts'), told from italic lines of verse (a roundel's refrain)
SKEAT_HEADING = re.compile(
    r"(?i)^(?:the |a |an )?(?:proem|story|dream|envoy|lenvoy|l'envoy|balades?|bille|conclusion|devotion|fragment"
    r"|explicit|incipit|comm?ent|compleynt|compleint|complaint|moral|proverbe|counseil|amorous|la respounse"
    r"|le pleintif|[ivx]+\.\s|lady in fear|instability|brooch|appeal|qui bien|story continued)")


CHAUCER_MINOR = {3: "The Book of the Duchess", 5: "The Parliament of Fowls", 7: "Anelida and Arcite"}


def chaucer_vol1() -> dict:
    """Skeat's Romaunt of the Rose and minor poems (Chaucer's Works, vol. I, 1894), Gutenberg #43089, numbered as
    he numbers them; the Book of the Duchess, the Parliament of Fowls and Anelida and Arcite as books, the rest
    as the parts of "Chaucer's Shorter Poems", numbered as his (I. An A. B. C. ... XXIII. A Balade of
    Compleynt)."""
    t = ba.gutenberg(43089)
    titles = [(m.start(), m.end(), text(m.group(1))) for m in re.finditer(r'(?is)<p class="ac lg1[25][05]">(.*?)</p>', t)]
    out, shorter = {}, {}
    rom = [s for s, e, x in titles if x == "THE ROMAUNT OF THE ROSE."][1]
    first = next(s for s, e, x in titles if x.startswith("I. AN A. B. C."))
    out["The Romaunt of the Rose"] = line_chunked("The Romaunt of the Rose", skeat1_poem(t[rom:first]))
    poems = [(s, e, x) for s, e, x in titles if re.match(r"[IVXL]+\. ", x) and s >= first]
    stop = next(s for s, e, x in titles if s > first and x == "THE ROMAUNT OF THE ROSE.")
    for i, (s, e, x) in enumerate(poems):
        end = poems[i + 1][0] if i + 1 < len(poems) else stop
        num, name = re.match(r"([IVXL]+)\.\s+(.*)", x).groups()
        n = ba.roman(num)
        paras = skeat1_poem(t[e:end])
        if n in CHAUCER_MINOR:
            out[CHAUCER_MINOR[n]] = line_chunked(CHAUCER_MINOR[n], paras)
        else:
            name = ba.title_case(name.rstrip("."))
            heading = f"Chaucer's Shorter Poems — {num}. {name}" if not shorter else f"{num}. {name}"
            shorter.update(line_chunked("Chaucer's Shorter Poems", paras, part=n, heading=heading))
    out["Chaucer's Shorter Poems"] = shorter
    return out


def gower_part(body: str) -> list:
    """Macaulay's verse markup (<div class="stanza"> of <div class="verse ...">, numbers in <span class="linenum">)
    -> [(first line, [(n, line)])]; his Latin verses (stanzas wholly in italics) and Latin sidenotes left out."""
    body = re.split(r"(?i)<h3[^>]*>\s*(?:LINENOTES|FOOTNOTES):?", body)[0]
    body = drop(body, "a", "fnanchor")
    body = re.sub(r'(?is)<span class="linenum">\s*\(\d+\*?\)\s*</span>', "", body)   # (the other recension's)
    entries = []                                                     # "break" | a line's markup
    for st in keep_each(body, "div", "stanza|stanzabreak"):
        st = drop(st, "div", "sidenote|sidenote2")
        lines = re.findall(r'(?is)<div class="verse[^"]*">(.*?)</div>', st)
        if not lines or all(re.fullmatch(r"(?is)\s*(?:[ivxl]+\.\s*)?<i>.*</i>[\s.,;:]*(?:<span class=\"linenum\">\d+</span>)?\s*",
                                         x) for x in lines):
            continue                                                         # (Latin)
        entries.append("break")
        entries.extend(lines)
    # A passage between stars (*Thapostle James ... wise.*) is either his text, which other manuscripts replace,
    # or (numbered 3150*, 3160*) theirs, printed after it: the first is kept, its stars dropped, the second not.
    out, seg = [], None

    def starred(lines):
        return any(re.search(r'<span class="linenum">\s*\d+\*', y) for y in lines if y != "break")

    for x in entries:
        if x == "break":
            if seg is not None and starred(seg):                              # (theirs ends with its stanza)
                seg = None
            (seg if seg is not None else out).append(x)
            continue
        plain = text(re.sub(r'(?is)<span class="linenum">.*?</span>', "", x))     # (not the number's star)
        if seg is None and plain.startswith("*"):
            seg = []
        if seg is not None:
            seg.append(x)
            if plain.rstrip().endswith("*") and not (len(seg) == 1 and plain.count("*") < 2):
                if not starred(seg):
                    out.extend(seg)
                seg = None
        else:
            out.append(x)
    if seg and not starred(seg):
        out.extend(seg)
    html_ = "".join('<p class="stanza"></p>' if x == "break" else
                    "<p>" + re.sub(r'(<span class="linenum">\s*\d+)\*', r"\1", x).replace("*", "") + "</p>"
                    for x in out)
    html_ = html_.replace("&lt;", "[").replace("&gt;", "]")                 # (his supplied words, <so>)
    return numbered_poem(html_)


def gower() -> dict:
    """Macaulay's Confessio Amantis (The Complete Works of John Gower, vols. II-III, 1901), Gutenberg #71162 and
    #71433: the Prologue as part 0, Books I-VIII as 1-8, each numbered as he numbers it (Book V runs over both
    volumes); and In Praise of Peace, to Henry IV. His Latin verses and sidenotes, and his notes, left out."""
    conf, peace = {}, {}
    for n in (71162, 71433):
        t = ba.gutenberg(n)
        start = re.search(r'<h2[^>]*>\s*CONFESSIO AMANTIS', t).start()
        heads = [(m.start(), m.end(), text(m.group(1))) for m in re.finditer(r"(?is)<h2[^>]*>(.*?)</h2>", t[start:])]
        heads = [(s + start, e + start, x) for s, e, x in heads]
        part = 0 if n == 71162 else 5
        for i, (s, e, x) in enumerate(heads):
            if re.match(r"(?i)NOTES|GLOSSARY|INDEX", x):
                break
            end = heads[i + 1][0] if i + 1 < len(heads) else len(t)
            body = t[e:end]
            if x.upper().startswith("TO KING HENRY"):
                # (its 385 lines; the Latin poems after it left out)
                peace = line_chunked("In Praise of Peace", [p for p in gower_part(body) if p[0] <= 385])
                continue
            b = re.match(r"(?i)Incipit Liber (\w+)", x)
            if b:
                part = ["primus", "secundus", "tercius", "quartus", "quintus", "sextus", "septimus",
                        "octavus"].index(b.group(1).lower().rstrip(".")) + 1
            heading = ("Confessio Amantis — Prologue" if part == 0 else
                       f"Book {ROMAN_NUMS[part - 1]}") if b or part == 0 else ""
            chunk = line_chunked("Confessio Amantis", gower_part(body), part=part, heading=heading or " ")
            if not heading:                                         # (Book V's second half: no heading)
                chunk = {k: {"1": v["1"].replace("* *\n", "", 1)} for k, v in chunk.items()}
            conf.update(chunk)
    return {"Confessio Amantis": conf, "In Praise of Peace": peace}


def piers() -> dict:
    """Wright's Vision of Piers Ploughman (2nd ed., 1856; the B-text, from Trinity College Cambridge MS. B.15.17),
    Gutenberg #43660-1, its half-lines numbered as he numbers them; and the Creed of Piers Ploughman (Pierce the
    Ploughman's Crede, c. 1394, not Langland's), printed after it. His notes left out."""
    passus = re.compile(r"(?i)^(?:passus|explicit|incipit|prologus)")
    v1, v2 = ba.gutenberg(43660), ba.gutenberg(43661)
    a = v1.rfind("THE VISION OF", 0, v1.index("Passus Primus de Visione"))
    vision = v1[a:v1.index(">Notes<", a) if ">Notes<" in v1[a:] else len(v1)]
    creed = v2.index("THE CREED OF PIERS")
    vision += v2[v2.rfind('<div class="center"', 0, v2.index("Passus Decimus Quartus")):creed]
    creed_body = v2[creed:v2.index("NOTES AND GLOSSARY", creed)]
    return {"Piers Plowman": line_chunked("Piers Plowman", skeat1_poem(vision, passus)),
            "Pierce the Ploughman's Crede": line_chunked("Pierce the Ploughman's Crede",
                                                         skeat1_poem(creed_body, passus))}


def sisam_verse(region: str, breaks: str = "stanza|indent2") -> list:
    """Sisam's verse (<p class="verse ...">, a paragraph opening at a stanza div, or in the narrative poems at
    "indent2"; in the lyrics that is only an indented line), his introduction to the piece (plain <p>s) left out,
    and his ⟨lines supplied from another MS⟩ in square brackets."""
    body = "".join(re.findall(r'(?is)<div class="stanza">|<p class="verse[^"]*">.*?</p>', region))
    body = body.replace('<div class="stanza">', '<p class="stanza"></p>')
    body = body.replace("&lt;", "[").replace("&gt;", "]")
    paras = numbered_poem(body, stanza_cls=breaks)
    # (the plays' stanza numbers, "1. [Iesus. M]anne on molde")
    return [(s, [(n, re.sub(r"^\d+\.\s+(?=\S)", "", x)) for n, x in lines]) for s, lines in paras]


def sisam() -> dict:
    """The complete poems in Sisam's Fourteenth Century Verse & Prose (Oxford, 1921), Gutenberg #43736: Sir
    Orfeo (the Auchinleck text, its lost opening supplied from Harley 3810), the Dancers of Colbek from Mannyng's
    Handlyng Synne, the political poems and lyrics, and the York and Towneley plays. (His extracts from longer
    works, and the prose, left out: the whole of most of those is here already.)"""
    t = ba.gutenberg(43736)
    t = t[:t.index('<a id="NOTES"') if '<a id="NOTES"' in t else re.search(r"<h2[^>]*>\s*NOTES", t).start()]
    heads = [(m.start(), m.end(), text(m.group(1))) for m in re.finditer(r"(?is)<h[23][^>]*>(.*?)</h[23]>", t)]
    sec = {}
    for i, (s, e, x) in enumerate(heads):
        sec[x] = t[e:heads[i + 1][0] if i + 1 < len(heads) else len(t)]

    def find(prefix):
        return next(v for k, v in sec.items() if k.upper().startswith(prefix))

    def name(k):
        k = re.sub(r"^[A-I]\.\s+", "", k)
        k = re.split(r",\s*A\.D\.|\.\s|\s\(|\s+BY\s", k)[0]
        return heading_case(k.rstrip("."))

    out = {"Sir Orfeo": line_chunked("Sir Orfeo", sisam_verse(find("II SIR ORFEO"))),
           "The Dancers of Colbek": line_chunked("The Dancers of Colbek", sisam_verse(find("THE DANCERS OF COLBEK"))),
           "The York Play of the Harrowing of Hell": line_chunked("The York Play of the Harrowing of Hell",
                                                                 sisam_verse(find("XVI THE YORK PLAY"))),
           "The Towneley Play of Noah": line_chunked("The Towneley Play of Noah",
                                                    sisam_verse(find("XVII THE TOWNELEY PLAY")))}
    for book, keys in (("Political Poems", "ABCDE"), ("Middle English Lyrics", "ABCDEFGHI")):
        start = list(sec).index(next(k for k in sec if k.startswith("XIV" if book[0] == "P" else "XV ")))
        parts = {}
        for n, k in enumerate(list(sec)[start + 1:start + 1 + len(keys)], 1):
            heading = f"{book} — {n}. {name(k)}" if n == 1 else f"{n}. {name(k)}"
            parts.update(line_chunked(book, sisam_verse(sec[k], "stanza"), part=n, heading=heading))
        out[book] = parts
    return out


def until_heading(t: str, start: int, word: str, tag: str = "h2") -> str:
    """t from start to the next <tag> heading beginning with word (an anchor inside it allowed)."""
    m = re.search(rf"(?is)<{tag}[^>]*>\s*(?:<a[^>]*>\s*(?:</a>\s*)?)?{word}", t[start:])
    return t[start:m.start() + start]


def lancelot_laik() -> dict:
    """Skeat's Lancelot of the Laik (EETS 6, 1865; Scots, about 1490, from the Prose Lancelot), Gutenberg #36848,
    numbered as he numbers it; his sidenotes, headings and notes left out, his long s printed as s."""
    t = ba.gutenberg(36848)
    start = t.index('<div class="lancelot">')
    t = until_heading(t, start, r"NOTES\.").replace("ſ", "s")
    paras = numbered_poem(t, junk="sidenote|pagenum|headnote|footnote|feuillet",
                          section=r"<h3[^>]*>\s*\[(?P<name>(?:PROLOGUE|BOOK [IVX]+))\.\]\s*</h3>")
    # the scribe's y for thorn (yat, yar, yis), as þ ("Yis," capital, is "yes"; ye and yow are "you")
    # (and his * on an emended word dropped)
    paras = [(s, [(n, re.sub(r"\by(at|ar|is|aim)\b", r"þ\1", x).replace("*", "") if n else x) for n, x in lines])
             for s, lines in paras]
    return {"Lancelot of the Laik": line_chunked("Lancelot of the Laik", paras)}


def arthur_bath() -> dict:
    """Furnivall's Arthur (EETS 2, 1864; English verse of about 1425 in a Latin chronicle at Longleat), Gutenberg
    #16845, numbered as he numbers it; his sidenotes left out."""
    t = ba.gutenberg(16845)
    start = t.index("From the Marquis of Bath's MS.</h2>")
    t = until_heading(t, start, "Words")
    t = t.replace('<div class="linegroup">', '<p class="stanza"></p>')
    t = re.sub(r"(?is)<p[^>]*>\s*BEF\. 1450.*?</p>|<p style=\"font-weight: bold\">.*?</p>", "", t)
    return {"Arthur": line_chunked("Arthur", numbered_poem(t, junk="marginnote|sidenote_right|footnoteref"))}


def gawayne_me() -> dict:
    """Morris's Sir Gawayne and the Green Knight (EETS 4, 1864; the poem in its own Middle English, beside
    Weston's translation), Gutenberg #14568, numbered as he numbers it; his fitts kept, his stanza numerals and
    sidenotes left out. (The e-book has the poem twice, the first time with 3 for the yogh: the second, with ȝ,
    is taken.)"""
    t = ba.gutenberg(14568)
    start = re.search(r"SYR GAWAYN AND THE GRENE KNYȜT\.\s*</h2>", t).end()
    end = re.search(r"(?is)<h[12][^>]*>\s*(?:NOTES|GLOSSARY|Sir Gawayne)", t[start:])
    t = t[start:end.start() + start if end else len(t)]
    t = t[:re.search(r">\s*NOTES\.\s*<", t).start() + 1] if re.search(r">\s*NOTES\.\s*<", t) else t
    t = t.replace('<div class="stanza">', '<p class="stanza"></p>')
    t = re.sub(r"(?is)<h2[^>]*>\s*[IVXL]+\.\s*</h2>", "", t)                    # (his stanza numbers)
    paras = numbered_poem(t, section=r"<h2[^>]*>\s*\[(?P<name>FYTTE THE \w+)\.\]\s*</h2>")
    # (the etext's 1 for l: "Bot I wy1 to þe chape1")
    paras = [(s, [(n, re.sub(r"(?<=[a-zþȝ])1\b", "l", x)) for n, x in lines]) for s, lines in paras]
    return {"Sir Gawayn and the Grene Knyȝt": line_chunked("Sir Gawayn and the Grene Knyȝt", paras)}


# Skeat's Chaucerian and Other Pieces (vol. VII): number -> the book's name (the longer poems); the rest are the
# parts of "Chaucerian Shorter Poems". I and III are prose, IV Gower's In Praise of Peace (from Macaulay here).
CHAUCERIAN = {2: "The Plowman's Tale", 5: "The Letter of Cupid", 8: "The Complaint of the Black Knight",
              16: "La Belle Dame sans Mercy", 17: "The Testament of Cresseid",
              18: "The Cuckoo and the Nightingale", 20: "The Flower and the Leaf", 21: "The Assembly of Ladies",
              24: "The Court of Love"}
CHAUCERIAN_SKIP = {1, 3, 4}


def chaucerian() -> dict:
    """Skeat's Chaucerian and Other Pieces (Oxford, 1897), Gutenberg #43195: the poems once printed with
    Chaucer's (Hoccleve's Letter of Cupid, Lydgate's Black Knight, Henryson's Testament of Cresseid, Clanvowe's
    Cuckoo and the Nightingale, the Flower and the Leaf...), numbered as he numbers them."""
    t = ba.gutenberg(43195)
    titles = [(m.start(), m.end(), text(m.group(1))) for m in re.finditer(r'(?is)<p class="ac lg1[0-9]+">(.*?)</p>', t)]
    poems = [(s, e, x) for s, e, x in titles if re.match(r"[IVXL]+\.", x)]
    stop = next(s for s, e, x in titles if x == "NOTES.")
    out, shorter = {}, {}
    for i, (s, e, x) in enumerate(poems):
        num = re.match(r"([IVXL]+)\.", x).group(1)
        n = ba.roman(num)
        if n in CHAUCERIAN_SKIP:
            continue
        end = poems[i + 1][0] if i + 1 < len(poems) else stop
        paras = skeat1_poem(t[e:end])
        if n in CHAUCERIAN:
            out[CHAUCERIAN[n]] = line_chunked(CHAUCERIAN[n], paras)
        else:
            name = heading_case(re.sub(r"^[IVXL]+\.\s*", "", x).rstrip("."))
            heading = f"Chaucerian Shorter Poems — {num}. {name}" if not shorter else f"{num}. {name}"
            shorter.update(line_chunked("Chaucerian Shorter Poems", paras, part=n, heading=heading))
    out["Chaucerian Shorter Poems"] = shorter
    return out


def letter_images(s: str) -> str:
    """An edition's letters printed as images (a drop capital; an abbreviation mark, "upright letter n with
    macron") -> the letter, the mark dropped as the other editions drop it in expanding."""
    def one(m):
        alt = m.group(1).strip()
        if re.fullmatch(r"\W?[A-Za-z]", alt):
            return alt
        if alt.startswith("ae with"):
            return "æ"
        k = re.search(r"letters? (\w+) with", alt)
        return k.group(1) if k else alt
    return re.sub(r'(?is)<img\b[^>]*\balt="([^"]*)"[^>]*>', one, s)


def sowdone() -> dict:
    """Hausknecht's text (EETS ES 38, 1881), Gutenberg #48531: each line numbered as he numbers it, a passage a
    page of his; his sidenotes, running heads and footnotes left out."""
    t = ba.gutenberg(48531)
    start = t.index('<h2 id="p001">')
    t = t[start:t.index('<div class="footnotes">', start)]
    t = drop(t, "a", "fnanchor")
    items = []
    for table in re.findall(r"(?is)<table[^>]*>(.*?)</table>", t):
        items.append(("break",))
        for n, row in re.findall(r'(?is)<tr id="l(\d+)">(.*?)</tr>', table):
            cells = [c for a, c in re.findall(r"(?is)<td([^>]*)>(.*?)</td>", row)
                     if not re.search(r'class="(?:dropcap|plnum|psidenote)"', a)]
            dropcap = re.search(r'(?is)<td class="dropcap"[^>]*>(.*?)</td>', row)
            line = text(letter_images((dropcap.group(1) if dropcap else "") + (cells[0] if cells else "")))
            line = line.replace("ħ", "h")                                  # (a crossed h: an abbreviation)
            if line:
                items.append(("line", line, int(n)))
    end = re.search(r'(?is)<p class="[^"]*\bfirst">(Here endithe.*?)</p>', t)
    if end:
        items.append(("line", f"*{text(end.group(1))}*", None))
    return {"The Sowdone of Babylone": line_chunked("The Sowdone of Babylone", group_lines(items))}


BUILDS = {
    "auchinleck": build_auchinleck,
    "pearl": lambda: save("pearl_poet", "ed. Richard Morris, Early English Alliterative Poems (EETS 1, 1869)",
                          pearl_poet()),
    "havelok": lambda: save("havelok", "ed. Walter W. Skeat, The Lay of Havelok the Dane (EETS ES 4, 1868)",
                            havelok()),
    "horn": lambda: save("king_horn", "ed. Joseph Hall and George H. McKnight, King Horn (EETS 14, re-ed. 1901)",
                         king_horn()),
    "sowdone": lambda: save("sowdone", "ed. Emil Hausknecht, The Romaunce of the Sowdone of Babylone (EETS ES 38, "
                                       "1881)", sowdone()),
    "torrent": lambda: save("torrent", "ed. E. Adam, Torrent of Portyngale (EETS ES 51, 1887)", torrent()),
    "genesis": lambda: save("genesis_exodus", "ed. Richard Morris, The Story of Genesis and Exodus (EETS 7, "
                                              "rev. 1873)", genesis_exodus()),
    "wright": lambda: save("wrights_wife", "ed. F. J. Furnivall, The Wright's Chaste Wife, by Adam of Cobsam "
                                           "(EETS 12, 1865)", wrights_wife()),
    "troilus": lambda: save("troilus", "ed. Walter W. Skeat, Chaucer's Works, vol. II (Oxford, 1894)", troilus()),
    "fame": lambda: save("chaucer_fame_legend", "ed. Walter W. Skeat, Chaucer's Works, vol. III (Oxford, 1894)",
                         fame_and_legend()),
    "chaucer1": lambda: save("chaucer_minor", "ed. Walter W. Skeat, Chaucer's Works, vol. I (Oxford, 1894)",
                             chaucer_vol1()),
    "arthur_me": lambda: save("middle_english", "Early English Text Society (1864-5)",
                              {**lancelot_laik(), **arthur_bath(), **gawayne_me()}, ROOT / "data" / "arthurian",
                              {"Lancelot of the Laik": "ed. W. W. Skeat (EETS 6, 1865)",
                               "Arthur": "ed. F. J. Furnivall (EETS 2, 1864)",
                               "Sir Gawayn and the Grene Knyȝt": "ed. Richard Morris (EETS 4, 1864)"}),
    "chaucerian": lambda: save("chaucerian", "ed. Walter W. Skeat, Chaucerian and Other Pieces (Oxford, 1897)",
                               chaucerian()),
    "wallace": lambda: save("wallace", "Blind Hary, Wallace, ed. John Jamieson (1820; 1869)", wallace()),
    "bruce": lambda: save("bruce", "John Barbour, The Bruce, ed. W. M. Mackenzie (London, 1909)", bruce()),
    "sisam": lambda: save("sisam", "ed. Kenneth Sisam, Fourteenth Century Verse & Prose (Oxford, 1921)", sisam()),
    "piers": lambda: save("piers", "ed. Thomas Wright, The Vision and Creed of Piers Ploughman (2nd ed., 1856)",
                          piers()),
    "gower": lambda: save("gower", "ed. G. C. Macaulay, The English Works of John Gower (Oxford, 1901)", gower()),
}


def main(which=()):
    for name, build in BUILDS.items():
        if not which or name in which:
            build()


if __name__ == "__main__":
    main(sys.argv[1:])
