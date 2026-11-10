"""
Gnostic and apocryphal texts from the Gnostic Society Library (gnosis.org), to fill in what the bot's other
editions leave out (2026-11-09):

    the Nag Hammadi tractates missing from Zinner's translation (data/gnostic/nag_hammadi_zinner.json) --
    the Secret Book (Apocryphon) of John, the Gospel of Truth, the Gospel of Philip, the First Apocalypse of
    James -- in the Coptic Gnostic Library Project's translations, as gnosis.org gives them (each translator
    cited); a chapter each, a paragraph a verse (nhl);
    the Pistis Sophia, in Mead's translation (pistis);
    the Gospel of Mary, the Bruce Codex, and the teachers the Fathers quote -- Ptolemy, Basilides, Epiphanes, the
    Naassenes, Theodotus (fragments);
    M. R. James's Apocryphal New Testament (1924): the apocryphal Acts, Third Corinthians, Bartholomew, the
    Apocalypses of Thomas and of Peter (the Ethiopic), and the letter with the Secret Gospel of Mark, into
    data/nt_apocrypha/james_apocrypha.json (james).

    python scripts/build_gnosis.py [nhl] [pistis] [fragments] [james]
"""
import html
import json
import re
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CACHE = Path(__file__).resolve().parent / ".cache" / "gnosis"
SITE = "http://gnosis.org/"
UA = {"User-Agent": "ScriptureBot corpus builder (a personal Discord bot)"}


def expect(ok: bool, message: str) -> None:
    if not ok:
        raise SystemExit(f"unexpected source layout: {message}")


def fetch(path: str) -> str:
    CACHE.mkdir(parents=True, exist_ok=True)
    cached = CACHE / path.replace("/", "_")
    if not cached.exists():
        cached.write_bytes(urllib.request.urlopen(urllib.request.Request(SITE + path, headers=UA), timeout=60).read())
        time.sleep(1)
    raw = cached.read_bytes()
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:                  # (some pages are Windows-1252: Heracleon's quotation marks)
        return raw.decode("cp1252", errors="replace")


def paragraphs(fragment: str) -> list:
    out = []
    for p in re.split(r"(?i)<p\b[^>]*>", fragment):
        p = re.sub(r"(?i)<br\s*/?>", " ", p)
        text = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", "", p)).replace("\xad", "")).strip()  # (soft hyphens)
        if text and not re.fullmatch(r"[\s ]*", text):
            out.append(text)
    return out


def nhl_page(path: str) -> "tuple[str, list]":
    """A Coptic Gnostic Library Project page: (its translators, its paragraphs)."""
    page = fetch(path)
    # (the "Translated by" line just before the text, not the one in the page's title)
    found = [m for m in re.finditer(r"Translated(?:&nbsp;|\s)+by\s+(.+?)(?:<br|</)", page, re.S)
             if "<blockquote" in page[m.end():m.end() + 400]]
    expect(bool(found), f"{path}: no translator over the text")
    m = found[0]
    body = page[page.find("<blockquote", m.end()):]
    body = body[:body.find("</blockquote>")]
    translators = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", "", m.group(1)))).strip()
    return translators, paragraphs(body)


def numbered_sections(paras: list) -> dict:
    """Paragraphs under section numbers set as paragraphs of their own ("1", then its text): a verse each;
    what comes before section 1 (the editor's note) left out."""
    verses, current = {}, None
    for p in paras:
        m = re.match(r"(\d{1,3})(?:\s+|$)(.*)", p, re.S)
        if m and int(m.group(1)) == (int(current) + 1 if current else 1):
            current = m.group(1)
            verses[current] = m.group(2).strip()
        elif current:
            verses[current] = (verses[current] + "\n" + p).strip()
    return {k: v for k, v in verses.items() if v}


# (page, the bot's name for it -- Zinner's style -- and the name its translators give it)
NHL_MISSING = [
    ("naghamm/apocjn-long.html", "The Secret Book of John"),       # (the long version, Codex II)
    ("naghamm/gostruth.html", "The Gospel of Truth"),
    ("naghamm/gop.html", "The Gospel of Philip"),
    ("naghamm/1ja.html", "The First Apocalypse of James"),
]


def pistis_sophia() -> dict:
    """The Pistis Sophia, trans. G. R. S. Mead (1921), a page a chapter (ps005-ps153, chapters 1-148): Mead's
    marginal summaries, the Coptic manuscript's page marks ("|5.") and the printed page numbers left out, a
    paragraph broken over a printed page put back together; each of its six books named before its first
    chapter. A chapter each, a paragraph a verse."""
    book, title = {}, None
    for n in range(5, 154):
        page = fetch(f"library/pistis-sophia/ps{n:03d}.htm")
        page = re.sub(r'(?is)<span class="r?margnote">.*?</span>|<a name="page_\d+">.*?</a>', "", page)
        heading = re.findall(r"(?is)<h\d[^>]*>(.*?)</h\d>", page)
        heads = [re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", "", h))).strip() for h in heading]
        m = next((re.fullmatch(r"(?i)chapter (\d+)\.?", h) for h in heads if re.fullmatch(r"(?i)chapter \d+\.?", h)), None)
        at = next((i for i, h in enumerate(heads) if re.fullmatch(r"(?i)chapter \d+\.?", h)), len(heads))
        new_book = " ".join(h.strip("[]") for h in heads[:at]) or None     # (a book's title, over its first chapter)
        ends = [x.end() for x in re.finditer(r"(?is)<h\d[^>]*>(.*?)</h\d>", page)
                if not m or re.search(rf"(?i)chapter\s+{m.group(1)}\b", re.sub(r"<[^>]+>", "", x.group(1)))]
        expect(bool(ends), f"ps{n:03d}: no heading")
        body = page[ends[0] if m else ends[-1]:]
        body = re.split(r"(?i)<hr\b", body)[0]
        if not m:                       # (a page between books, "The Note of a Scribe": after the chapter before)
            expect(bool(book) and bool(new_book), f"ps{n:03d}: no chapter heading in {heads}")
            note = [p for p in paragraphs(body) if not re.fullmatch(r"p\. \d+|\|?", p)]
            verses = book[str(len(book))]
            for i, p in enumerate(note):
                verses[str(len(verses) + 1)] = (f"*{new_book}*\n" if i == 0 else "") + p
            continue
        chapter = m.group(1)
        paras = [p for p in paragraphs(body) if not re.fullmatch(r"p\. \d+|\|?", p)]
        joined = []
        for p in paras:
            p = re.sub(r"\s*\|\s*", " ", p).strip()            # (the Coptic page marks)
            if joined and re.match(r"[a-z]", p):                # (a paragraph broken over a printed page)
                joined[-1] += " " + p
            else:
                joined.append(p)
        verses = {str(i): p for i, p in enumerate(joined, 1)}
        expect(bool(verses), f"chapter {chapter}: no text")
        if new_book:
            verses["1"] = f"*{new_book}*\n{verses['1']}"
        book[chapter] = verses
    book = dict(sorted(book.items(), key=lambda kv: int(kv[0])))     # (the site has 115 before 114, 128 before 127)
    expect(list(book) == [str(i) for i in range(1, 149)], f"chapters {list(book)[:5]}...{list(book)[-5:]}")
    return book


def library_text(path: str, title: str) -> list:
    """A Gnostic Society Library page's text: after the last heading that names the work (its archive notes come
    before), to the site's footer; a paragraph an item."""
    page = re.sub(r"(?is)<(script|style)\b.*?</\1>", "", fetch(path))
    key = re.sub(r"\W+", " ", title).lower().strip()
    heads = [m for m in re.finditer(r"(?is)<h\d[^>]*>(.*?)</h\d>", page)
             if key in re.sub(r"\W+", " ", html.unescape(re.sub(r"<[^>]+>", "", m.group(1)))).lower()]
    expect(bool(heads), f"{path}: no heading naming {title!r}")
    # the page's middle: from the title to the footer's navigation (the last "Archive | Library")
    body = page[heads[0].end():]
    paras = [p for p in paragraphs(re.sub(r"(?is)<h\d[^>]*>(.*?)</h\d>", r"<p>\1</p>", body))
             if not re.fullmatch(r"[\s. <]*", p)]
    # (the site's navigation, "Archive | Library | Bookstore...", at the top and as the footer)
    navigation = [i for i, p in enumerate(paras) if p.startswith("Archive | Library")]
    if navigation and navigation[0] < 2:
        paras = paras[navigation[0] + 1:]
        navigation = [i - navigation[0] - 1 for i in navigation[1:]]
    if navigation:
        paras = paras[:navigation[-1]]
    # its archive notes, then the title again over the text; and a second work's notes end it
    def is_title(p):
        return re.sub(r"\W+", " ", p).lower().strip().startswith(key)
    if paras and paras[0].strip() == "Archive Notes":
        again = next((i for i, p in enumerate(paras) if i and is_title(p)), None)
        paras = paras[again + 1:] if again is not None else paras[2:]
    while paras and is_title(paras[0]):
        paras = paras[1:]
    if "Archive Notes" in paras:
        paras = paras[:paras.index("Archive Notes")]
    return paras


def numbered(paras: list, pattern: str = r"(\d+)[.)]\s+") -> dict:
    """Items opening with their numbers ("22) The Savior said", "1. He set him up"), a verse each; text before
    the first number joins the first, after it the one before."""
    verses, current, lead = {}, None, []
    for p in paras:
        m = re.match(pattern, p)
        if m and (current is None or int(m.group(1)) > int(current)):
            current = m.group(1)
            verses[current] = ("\n".join(lead) + "\n" if lead else "") + p[m.end():].strip()
            lead = []
        elif current:
            verses[current] += "\n" + p
        else:
            lead.append(p)
    return verses


def sequential(text: str, dot: bool) -> dict:
    """Sections numbered in running text ("...as well 83 It is fitting", "1. He set him up"): a number opens
    the next section only if it is the next number and a capital follows."""
    pattern = r"(?:(?<=^)|(?<=\s))(\d{1,3})" + (r"\." if dot else "") + r"\s+(?=[“\"‘'A-Z(\[])"
    sections, last = {}, 0
    for piece in re.split(pattern, text):
        if piece.isdigit() and int(piece) == last + 1:
            last = int(piece)
            sections[piece] = ""
        elif last:
            sections[str(last)] += piece
        elif piece.isdigit():
            pass
    return {k: re.sub(r"\s+", " ", v).strip() for k, v in sections.items()}


def gospel_of_mary() -> dict:
    """The Gospel of Mary (the Berlin Codex), as gnosis.org has it, unattributed: chapters 4-9 (pages 1-6 of the
    manuscript, chapters 1-3, are lost, and 11-14, most of 5 to 8), its verses by their numbers."""
    page = re.sub(r"(?is)<(script|style)\b.*?</\1>", "", fetch("library/marygosp.htm"))
    parts = re.split(r"(?is)<h4[^>]*>\s*(?:<[^>]+>\s*)*Chapter\s+(\d+):?\s*(?:<[^>]+>\s*)*</h4>", page)
    book = {}
    for num, body in zip(parts[1::2], parts[2::2]):
        body = re.split(r"(?is)Archive \| Library|<h3\b", body)[0]
        paras = paragraphs(body)
        verses = numbered(paras, r"(\d+)\)\s*")
        expect(bool(verses), f"Mary {num}: no verses")
        book[num] = {k: re.sub(r"\s+\(?\s*$", "", v) for k, v in verses.items()}
    expect(list(book) == ["4", "5", "8", "9"], f"Mary chapters {list(book)}")       # (pages 11-14 lost too)
    return book


ROMAN = {"I": 1, "V": 5, "X": 10, "L": 50}


def roman(numeral: str) -> int:
    values = [ROMAN[c] for c in numeral]
    return sum(-v if i + 1 < len(values) and v < values[i + 1] else v for i, v in enumerate(values))


def page_paragraphs(path: str) -> list:
    """A page's paragraphs, its headings among them ("## The Acts of John")."""
    page = re.sub(r"(?is)<(script|style)\b.*?</\1>", "", fetch(path))
    return paragraphs(re.sub(r"(?is)<h\d[^>]*>(.*?)</h\d>", r"<p>## \1</p>", page))


def segment(paras: list, start: str, end: str = None, drop: tuple = ()) -> list:
    """The paragraphs from the one starting `start` to the one before the one starting `end`, without those
    starting with any of `drop` (James's notes among the text) or a heading."""
    first = [i for i, p in enumerate(paras) if p.startswith(start)]
    expect(len(first) == 1, f"start {start!r}: {len(first)} matches")
    out = []
    for p in paras[first[0]:]:
        if end and p.startswith(end) and out:
            break
        if not p.startswith(drop) and not p.startswith("## "):
            out.append(p)
    expect(not end or len(out) < len(paras) - first[0], f"end {end!r} not found")
    for d in drop:
        expect(any(p.startswith(d) for p in paras), f"drop {d!r} matches nothing")
    return out


def by_number(paras: list, numerals: str = "arabic", titles: tuple = (), inline: bool = True) -> dict:
    """James's sections: a paragraph opening with its number ("18 Now John", "XVII. And", "(144) My Lord",
    "Greek. 16-17 And") opens it, and the unnumbered ones after it are its own, a line each; a number in the
    running text that comes before the next paragraph's ("2 And they shall become sons of perdition. 3 And
    then") opens one too. A paragraph starting one of `titles` (an act's title) heads the next, in italics."""
    if numerals == "roman":
        pattern = r"\(?(?:Lat\. )?([IVXL]+)\.\)?\s*"
    else:
        pattern = r"(?:Greek\.\s+)?\(?(\d{1,3})\)?(?:-\d+)?\s*(?:\.\s*|:\s+|\s+)(?:\(continued\.\)\s*)?"
    verses, last, title = {}, 0, ""
    for p in paras:
        if p.startswith(titles):
            title += f"*{p.strip()}*\n"
            continue
        m = re.match(pattern, p)
        n = (roman(m.group(1)) if numerals == "roman" else int(m.group(1))) if m else None
        if m and n > last:
            last = n
            verses[str(n)] = title + p[m.end():]
        elif m and n == last:                                 # ("37 (continued.)", "(144)": a second part)
            verses[str(n)] += "\n" + title + p[m.end():]
        elif verses:
            verses[str(last)] += "\n" + title + p
        else:                                                  # (an unnumbered opening is the first)
            last = 1
            verses["1"] = title + p
        title = ""
    # a whole paragraph of James's brackets after a number ("XVII. [This episode, inserted most abruptly...]")
    verses = {k: re.sub(r"^\[[^\[\]]*[\])]\s*(?:\n|$)", "", v).strip() for k, v in verses.items()}
    if numerals == "arabic" and inline:
        keys, split = list(verses), {}
        for k, following in zip(keys, keys[1:] + [None]):
            parts = re.split(r"(?<=[.;:,?!’”'\"\)\]\s])\s*(?<!\S)(\d{1,3})\s+(?=[A-Za-z“\"‘'(\[])", verses[k])
            current = k
            split[current] = parts[0]
            for num, text in zip(parts[1::2], parts[2::2]):
                # (before a small letter, only the very next number: "that we must not use the prophets, 11 and")
                if (int(current) < int(num) < (int(following) if following else 10 ** 4)
                        and (not text[:1].islower() or int(num) == int(current) + 1)):
                    current = num
                    split[current] = text
                else:
                    split[current] += num + " " + text
            # (re.split eats the space before a number that turned out to be no section's)
        verses = {k: re.sub(r"[ \t]+", " ", v).strip() for k, v in split.items()}
    return verses


def by_paragraph(paras: list, titles: tuple = ()) -> dict:
    verses, title = {}, ""
    for p in paras:
        if p.startswith(titles):
            title += f"*{p.strip()}*\n"
            continue
        verses[str(len(verses) + 1)] = title + p
        title = ""
    return verses


JAMES = "trans. M. R. James (1924)"
JAMES_REMARKS = ("It is evident from what follows", "So the Latin, which has", "so the MS.; I would read",
                 "this last clause in the MS.", "this cannot be the author's", "At about this point we must place",
                 "From the Ascension of Isaiah", "Gundaphorus is a historical", "This description of hell-torments",
                 "Here and elsewhere there is a marked", "P has nothing of this", "something is wrong here",
                 "Hermas, Vision III", "Probably: in the time of rain", "These are the worshippers of idols")

# The site's Acts of Thomas garbles James's bracketed words (its own note says so): each phrase's words, once each,
# the first in capitals, the rest in reverse order. Put back in order from the 1924 printing (a scan at
# gospelstudies.org.uk), each checked to have the same words as the garbled one; nothing else taken from it.
THOMAS_BRACKETS = {
    "SYR. is the of God rest temperance and": "Syr. and temperance is the rest of God",
    "THE of land": "the land of", "WHICH iron breaketh": "which breaketh iron",
    "IN the of sea midst": "in the midst of the sea",
    "AND the of Sarbug walls unto came": "and came unto the walls of Sarbug",
    "AND the and thyself deck shouldest thou wherewith wear which mantle glorious":
        "and the glorious mantle which thou shouldest wear and wherewith thou shouldest deck thyself",
    "THOU be shalt": "thou shalt be", "AND letter a was my": "and my letter was a letter",
    "WITH hand right his": "with his right hand", "AND the seal brake": "and brake the seal",
    "HIM it brought that": "him that brought it", "EVEN be a it Syr. lamp, in if": "even if it be in a lamp, Syr.",
    "AND Syr. nurse, her": "and her nurse, Syr.",
    "CANNOT chastely live they except well": "cannot live well except they live chastely",
    "TO name": "to name", "THOU things these sayest": "thou sayest these things",
    "WHO and a tower buildeth": "who buildeth a tower and", "MAKETH him": "maketh him", "GOOD hope": "good hope",
    "UNTO Syr. one,": "unto one, Syr.", "THEE of my Syr. rest, giver": "thee my giver of rest, Syr.",
    "LO, and my raiment, on off put I": "lo, I put off and on my raiment,",
    "GIVE the of Syr. day, bread constant us": "give us the constant bread of the day, Syr.",
    "SOW in": "sow in", "OR Syr. die,": "or die, Syr.", "NOT, Syr.": "not, Syr.", "THEY, Syr.": "they, Syr.",
    "BELIEVE, the of God and my his Syr. in giver I servants, helper life believe preach; whom Christ Jesus "
    "proclaim, children.": "believe, my children, in the God whom I proclaim; believe in Jesus Christ whom I preach; "
                          "believe in the giver of life and helper of his servants, Syr.",
    "a man poor": "a poor man",
    # (and three in the Acts of John)
    "who for incurable lain had": "who had lain incurable for", "enduring for things": "enduring things for",
    "nor of spoken": "nor spoken of",
}


def james() -> None:
    """M. R. James's Apocryphal New Testament (1924), as the Gnostic Society Library has it: the books the
    bot's ANF 8-9 translations lack or give only in part. His introductions, his notes among the text (whole
    paragraphs, some in italics, some not) and his summaries of what is lost are left out; the text is cited by
    the sections he gives (Bonnet's, Lipsius's), a paragraph or a verse each. Left out: the Revelation of
    Stephen and the Martyrdom of Matthew (only his summaries), the Book of the Resurrection by Bartholomew (the
    same), the Akhmim Apocalypse of Peter and the infancy gospels (ANF 8-9 have them)."""
    books, sources = {}, {}
    # The Acts of John: Bonnet's sections 18-115 (the beginning is lost); the Latin Virtutes between 105 and
    # 106, its own book
    p = page_paragraphs("library/actjohn.htm")
    john_notes = ("There need be no portion", "This sentence must be an abridgement", "[Another manuscript",
                  "'We' remained four years", "[Q has the above", "Now one day as John was seated",
                  "Then the elder, hearing", "Cassian, Collation", "It is told that the most blessed",
                  "The only common point", "Our best manuscript prefixes", "From Laodicca to Ephesus",
                  "'John therefore was with the brethren", "There cannot be much of a gap",
                  "The greater part of this episode")
    books["Acts of John"] = {"1": by_number(
        segment(p, "18 Now John was hastening", "The remaining episode which is extant", john_notes)
        + segment(p, "106 John therefore continued", "The less good Greek manuscripts"))}
    books["Virtues of John"] = {"1": by_number(segment(
        p, "(Lat. XIV.)", "The last episode of these Acts",
        ("XIX tells shortly", "Then follows the episode of the poison-cup", "This bracketed sentence",
         "[M.R. James gives")), "roman")}
    # The Acts of Andrew: Gregory of Tours' epitome, the Vatican fragment, the Martyrdom
    p = [re.sub(r"^## Text (?=1 )", "", x) for x in page_paragraphs("library/actandy.htm")]
    books["Acts of Andrew"] = {
        "1": by_number(segment(p, "1 After the Ascension", "(The Passion to which Gregory", ("(I feel sure",))),
        "2": by_number(segment(p, "1 . . . is there in you", "THE MARTYRDOM")),
        "3": by_paragraph(segment(p, "And after he had thus discoursed throughout the night", "[Not much of this")),
    }
    # The Acts of Paul, by James's episodes (I, VI and VIII are only described, or quoted by others); the
    # Corinthian correspondence (3 Corinthians), from VII, its own book
    p = [x.replace("38 But Thecla, being taken", "33 But Thecla, being taken")       # (misprinted)
         for x in page_paragraphs("library/actpaul.htm")]
    episode_titles = ("When he was departed", "When Paul was departed")
    books["Acts of Paul"] = {
        "2": by_number(segment(p, "1 When Paul went up unto Iconium", "A good many manuscripts add")),
        "3": by_paragraph(segment(p, "When he was departed from Antioch and taught in Myra", "IV",
                                  ("A leaf lost", "A leaf gone", ". . . concord and peace")), episode_titles),
        "4": by_paragraph(segment(p, "When he was departed from Myra", "The purpose of confining Paul",
                                  ("Two leaves at least gone", "(Paul is speaking)", "About two leaves gone",
                                   "... (Paul speaking) through me")), episode_titles),
        "5": by_paragraph(segment(p, "When he was departed out of Sidon", "On the next page is a proper name"),
                          episode_titles),
        "7": by_paragraph(segment(p, "When he was departed from . . .", "On the following page begins"),
                          episode_titles),
        "9": by_paragraph(segment(p, "The grace of the Lord will walk with me", "Next page, first extant line")),
        "10": by_number(segment(p, "I. Now there were awaiting Paul at Rome", "The Coptic MS. has a colophon"),
                        "roman"),
    }
    corinth = [x.replace("86 And whoso receiveth", "36 And whoso receiveth")            # (misprinted)
               for x in segment(p, "I. 1 Stephanus and the elders", "[Laon adds")]
    parts = {"1": [], "2": [], "3": []}
    for x in corinth:
        m = re.match(r"(I{1,3})\.\s*(?=1 )", x)
        key = str(len(m.group(1))) if m else key
        parts[key].append(x[m.end():] if m else x)
    books["Third Corinthians"] = {k: by_number(v) for k, v in parts.items()}
    # The Acts of Peter: the Coptic fragment (Peter's daughter), and the Vercelli Acts by their chapters
    p = page_paragraphs("library/actpete.htm")
    books["Acts of Peter: Peter's Daughter"] = {"1": by_paragraph(segment(
        p, "But Peter smiled and said unto him", "The scene of this episode", ("[Here a leaf is lost", "Ptolemaeus, unable"))
    )}
    books["Acts of Peter"] = {"1": by_number(segment(
        p, "I. At the time when Paul", None,
        ("There has been great dispute", "If they are from the Acts of Paul", "The question is a difficult",
         "The writer of Paul obviously", "Here begins the original Greek text", "[Here the Martyrdom proper")),
        "roman")}
    # The Acts of Thomas: Bonnet's sections 1-170 (the Hymn of the Soul, 108-113), each act's title over it
    p = page_paragraphs("library/actthom.htm")
    thomas_notes = ("Note by Professor F. C. Burliitt", "In the Acts of Thomas, 27, the apostle",
                    "'Come, O elder of the five members", "What is the essential distinction",
                    "'Come, Messenger of reconciliation", "The word for 'Come' is fem.",
                    "As for the five words for 'mind'", "hauna means", "The Greek terms, used here", "[",
                    "My Lord and God, hope and confidence")                # (the shorter text: he follows P's)
    acts = tuple(x for x in p if re.match(r"(?:The \w+ Act|Act the \w+):", x))
    expect(len(acts) == 13, f"Thomas: {len(acts)} acts")
    thomas = by_number(segment(p, "The First Act:", "## Archive", thomas_notes), titles=acts)
    for v, text in thomas.items():     # (a garbled single word is only in capitals: "[GARLANDS]")
        thomas[v] = re.sub(r"\[([A-Z]{2,})\]", lambda m: f"[{m.group(1).capitalize() if m.group(1) in ('JESUS', 'GOD') else m.group(1).lower()}]", text)
    books["Acts of Thomas"] = {"1": thomas}
    # The Questions of Bartholomew (the Greek where James gives it with the Slavonic and Latin), I-V
    p = page_paragraphs("library/gosbart.htm")
    bart = segment(p, "Greek. 1 After the resurrection", "THE BOOK OF THE RESURRECTION",
                   ("3 Om.", "Slavonic.", "Latin 2.", "[Slav", "[Slavonic"))
    bart = [x for x in bart if not re.fullmatch(r"\d \S.{0,80}", x) or not x.startswith(("2 And Jesus said unto them",
            "3 But when he was buried", "4 But Bartholomew, &c.", "2 But Jesus answered", "3 But after that"))]
    chapters, current = {}, "1"
    for x in bart:
        if re.fullmatch(r"[IV]+", x):
            current = str(min(roman(x), 5))         # (V is printed "VI")
            chapters[current] = []
            continue
        chapters.setdefault(current, []).append(x)
    books["Questions of Bartholomew"] = {k: by_number(v) for k, v in chapters.items()}
    # The Apocalypse of Thomas: the longer text (Wilhelm's) and the shorter (Bihlmeyer's)
    p = page_paragraphs("library/apcthom.htm")
    books["Apocalypse of Thomas"] = {
        "1": by_paragraph(segment(p, "Here beginneth the epistle of the Lord unto Thomas", "(Here Wilhelm's text ends",
                                  ("[Here is a break",))),
        "2": by_paragraph(segment(p, "Hear thou, O Thomas, for I am the Son", "None of the Latin texts")),
    }
    # The Apocalypse of Peter in the Ethiopic (the Akhmim Greek is ANF 9's)
    p = page_paragraphs("library/apocpeter.htm")
    books["Ethiopic Apocalypse of Peter"] = {"1": by_paragraph(segment(
        p, "The Second Coming of Christ and Resurrection", "There is a great deal more of the Ethiopic",
        ("[And this that dieth", "(Here begins the description", "(Parts of these two sections",
         "(We now have the section")), ("The Second Coming of Christ",))}
    for name in books:
        sources[name] = JAMES
    # Clement's letter to Theodore, with the Secret Gospel of Mark (Morton Smith's find and translation)
    p = page_paragraphs("library/secm.htm")
    books["Letter to Theodore"] = {"1": by_paragraph(segment(
        p, "From the letters of the most holy Clement", "[Here the fragment ends"))}
    sources["Letter to Theodore"] = "trans. Morton Smith (1973); many hold it a modern forgery"
    unscrambled, remarks = 0, 0
    for name, chapters in books.items():
        for verses in chapters.values():
            for v, text in verses.items():
                # James's remarks in brackets among the text (his variant readings, also bracketed, stay)
                text, n = re.subn(r"\s*\[(?:" + "|".join(map(re.escape, JAMES_REMARKS)) + r")[^\]]*\]", "", text)
                remarks += n
                verses[v] = re.sub(r"\[([^\]]+)\]", lambda m: f"[{THOMAS_BRACKETS.get(m.group(1), m.group(1))}]", text)
                unscrambled += sum(f"[{k}]" in text for k in THOMAS_BRACKETS)
    expect(unscrambled == len(THOMAS_BRACKETS), f"{unscrambled} brackets put in order")
    expect(remarks == len(JAMES_REMARKS), f"{remarks} of James's remarks taken out")
    expect(not any(re.search(r"\[[A-Z]{2,}\b", t) for t in books["Acts of Thomas"]["1"].values()),
           "Thomas: a garbled bracket left")
    for name, chapters in books.items():
        expect(all(chapters.values()), f"{name}: an empty chapter")
        for c, verses in chapters.items():
            for v, text in verses.items():
                expect(bool(text.strip()), f"{name} {c}:{v} empty")
                expect(not re.search(r"Archive \||Scanned and [Ee]dited|Bonnet, Act", text), f"{name} {c}:{v}: {text[:60]}")
        print(f"  {name}: " + ", ".join(f"{c} ({len(v)})" for c, v in chapters.items()))
    write("james_apocrypha.json", books, sources, JAMES, folder="nt_apocrypha")


# gnosis.org's short Manichaean texts from Central Asia (Turfan) and elsewhere, in its index's order; the Coptic
# psalms it also has (Taste and Know, Light Your Lamps...) are Allberry's, already in (manichaean_psalms.json)
MANI_SHORT = [
    ("3messarch.htm", "The Hymn on the Third Messenger and the Archons"), ("hymnfa.htm", "Hymn to the Father of Greatness"),
    ("hymncapt.htm", "The Hymn about the Captivity of Light"), ("invjesus.htm", "Invocation of Jesus the Splendor"),
    ("hymn2c.htm", "Hymn on the Second Coming of Jesus"), ("hymnfs.htm", "Hymn on the Fate of the Living Soul"),
    ("hymnexh.htm", "Hymn Exhorting the Soul to Remembrance"), ("hymntlivs.htm", "Hymn to the Living Soul"),
    ("hymn3mess.htm", "Hymn to the Third Messenger"), ("hymnmani.htm", "Hymn in Praise of Mani"),
    ("hymncm.htm", "Commemorative Hymn for Mar Zaku"), ("homeuch.htm", "Homily on the Correct Preparations for the Sacred Meal"),
    ("invocang.htm", "Invocation of the Angels"), ("invocbar.htm", "The Invocation of Bar Simus"),
    ("invocgod.htm", "Invocation of the Gods in the Moon"), ("confpr.htm", "A Confessional Prayer for the Elect"),
    ("hymnend.htm", "The Hymn on the End of the World"), ("hymnbody.htm", "The Hymn on Body-and-Soul"),
    ("funerh.htm", "The Funerary Hymn"), ("hymnssoul.htm", "Hymns to the Soul"),
    ("hymndom.htm", "Hymn in Honor of the Dominions of Light"), ("parthhymn.htm", "Verses from a Parthian Hymn"),
    ("crucihymn.htm", "The Crucifixion Hymn"), ("praislesser.htm", "The Praise of the Lesser Ones"),
    ("praisegreater.htm", "The Praise of the Greater Ones"), ("wwf.htm", "We Would Fulfill: Mani's Hymn to Jesus, the King"),
    ("praisejesus.htm", "The Praise of Jesus the Life-giver"), ("unps.htm", "Untitled Psalm Fragment"),
    ("kins.htm", "Come to Me, My Kinsman, the Light, My Guide"), ("primal.htm", "The Hymn of the First Primal Man"),
    ("salvat.htm", "Salvation of the Soul"),
    ("livgosp.htm", "The Opening Words of the Living Gospel"), ("epistmar.html", "The Sweet Teaching of the Sinless (Letter to Mar Ammo)"),
    ("fund.htm", "From the Fundamental Epistle of Mani"), ("keph.htm", "From the Kephalaia: The Three Blows Struck at the Enemy"),
    ("parabaud.htm", "Parables about the Auditors"), ("parafarm.htm", "Parable about the Farmer"),
    ("parapear.htm", "Parable of the Pearl-Borer"), ("paramonk.htm", "The Parable of the Monk and the Girl"),
    ("parsnak.htm", "The Parable about the Two Snakes"),
]
MANDA_SHORT = [
    ("tmes.htm", "The Messenger of Light Creates the Way of Salvation"), ("adamd.htm", "The Deliverance of Adam"),
    ("adamb.htm", "The Baptism of Adam"), ("tsod.htm", "The Soul's Deliverance"), ("bap.htm", "Bliss and Peace"),
    ("thesou.htm", "The Soul in its Coat of All Colors"), ("wrap.htm", "Wrapped in Sleep"),
    ("tsoa.htm", "The Song of Ascent"), ("inst.htm", "Instruction of Adam by an Uthra"),
]
# a page's own line on what the text is ("- A Manichaean hymn in Parthian.", "A fragment of a writing ascribed to Mani")
ABOUT = re.compile(r"(?:.*?\s[-–]\s)?((?:A |An )?(?:Manichaean|fragment|hymn|text|liturgical|Turkish)[^.]*\b(?:in|to) [A-Z]\w+[^.]*\.|"
                   r"(?:A )?[Hh]ymn ascribed to Mani[^.]*\.)$")


def short_text(path: str, title: str) -> list:
    """One of gnosis.org's short pages: its title in italics, the line saying what it is and in what language (if
    any) the same, then its paragraphs; without the site's navigation and footer, or a paragraph only of dots."""
    paras = page_paragraphs("library/" + path)
    nav = [i for i, p in enumerate(paras) if re.match(r"## (?:Gnosis? Archive|Archive) \|", p)]
    expect(bool(nav), f"{path}: no navigation")
    out, about = [], None
    for p in paras[nav[0] + 1:]:
        if out and (p.startswith("## |") or "GNOSTIC SOCIETY LIBRARY" in p or p.startswith("## Archive |")):
            break                                               # (the footer, the navigation again)
        if (p.startswith("##") or re.fullmatch(r"[\s.…]*", p) or p.startswith("Here ends the")
                or p.startswith(("(Source document", "(From the Ginza"))):        # (the site's notes on its sources)
            continue
        key = lambda s: re.sub(r"\W+", "", re.sub(r"(?i)^the\s+", "", s)).lower()[:18]
        if (not out and about is None and len(p) < 160 and key(p).startswith(key(title)[:12])
                or not out and p.startswith(("Verses from a", "Hymn in Praise of Jesus, the King"))):
            # the page's own heading: its title again, then what it is ("- a hymn ascribed to Mani, in Parthian.")
            words, names = p.split(), {w.lower().strip(",.:") for w in title.split()} | {"the", "great"}
            while words and words[0].lower().strip(",.:") in names:
                words.pop(0)
            rest = re.split(r"\s[-–]\s", " ".join(words))[-1].lstrip("-–, ").strip()     # ("Mâr Zaku - A Manichaean")
            rest = re.sub(r'^"[^"]*"\s*', "", rest)                                         # ('"Pearl-borer" A ...')
            about = rest[:1].upper() + rest[1:]
            continue
        if not out and ABOUT.fullmatch(p.strip()) and len(p) < 120:
            about = (about + " " if about else "") + p.strip()
            continue
        out.append(p)
    expect(bool(out), f"{path}: no text")
    head = f"*{title}*" + (f"\n*{about.strip()}*" if about else "")
    return [head + "\n" + out[0]] + out[1:]


def manichaean_mandaean() -> None:
    books = {
        "Manichaean Hymns and Fragments": {str(i): {str(j): p for j, p in enumerate(short_text(path, title), 1)}
                                           for i, (path, title) in enumerate(MANI_SHORT, 1)},
        "Mandaean Prayers": {str(i): {str(j): p for j, p in enumerate(short_text(path, title), 1)}
                             for i, (path, title) in enumerate(MANDA_SHORT, 1)},
    }
    p = page_paragraphs("library/haran.htm")
    books["Haran Gawaita"] = {"1": by_paragraph(segment(p, "My Lord be praised. In the name of the Great Life", "## Archive"))}
    sources = {"Manichaean Hymns and Fragments": "various translators (Gnostic Society Library)",
               "Mandaean Prayers": "various translators (Gnostic Society Library)",
               "Haran Gawaita": "trans. E. S. Drower (1953)"}
    for name, chapters in books.items():
        print(f"  {name}: {len(chapters)} chapters, {sum(map(len, chapters.values()))} passages")
    write("manichaean_mandaean_more.json", books, sources, "Gnostic Society Library")


def valentinians_and_cathars() -> None:
    """Valentinus's fragments and his psalm, Ptolemy's commentary on the prologue of John, Heracleon's fragments
    (quoted by Origen and Clement), and the Cathars' scripture and rites in English: the Secret Supper
    (Interrogatio Iohannis, in M. R. James's translation), the Book of the Two Principles, and the Cathar Ritual's
    confession and its rite for handing on the Lord's Prayer. (The site's Consolamentum and the Ritual's other
    parts are only in Occitan; its Vision of Isaiah is the Ascension of Isaiah's, already in.)"""
    books, sources = {}, {}
    # Valentinus: a verse a fragment, its title over it; then the psalm, without the site's words on it or the
    # "later teacher's" explanation (Hippolytus's)
    p = page_paragraphs("library/valentinus/Fragments_Valentinus.htm")
    verses, title, on = {}, "", False
    for x in p:
        m = re.match(r"## (?:Fragment (\d+): (.+)|(Summer Harvest: A Psalm By Valentinus))$", x)
        if x.startswith("## Explanation By a Later Teacher"):
            break
        if m:
            on, title = True, m.group(2) or m.group(3)
            continue
        if on and not x.startswith(("##", "This hymn was written")):
            n = str(len(verses) + 1) if title else str(len(verses))
            if title:
                verses[n] = f"*{title}*\n{x}"
                title = ""
            else:
                verses[n] += "\n" + x
    expect(len(verses) == 8, f"Valentinus: {len(verses)} fragments")
    books["Fragments of Valentinus"] = {"1": verses}
    sources["Fragments of Valentinus"] = "trans. Bentley Layton (1987)"
    p = page_paragraphs("library/ptl.htm")
    books["Ptolemy's Commentary on John"] = {"1": by_paragraph(segment(p, "John, the disciple of the Lord", "## Archive"))}
    sources["Ptolemy's Commentary on John"] = "trans. Bentley Layton (1987)"
    # Heracleon: by the fragment numbers ("Fragment 17, on John 4:12-15 (In John 4:13, ..."), the verse it's on in
    # italics; 29, 36 and 38 are not on the page
    p = page_paragraphs("library/fragh.htm")
    frags = {}
    for x in p:
        m = re.match(r"Fragment (\d+), on ((?:John|Matthew|Luke) [\d:\-ab]+(?: continued)?)\s*", x)
        if m:
            frags[m.group(1)] = f"*On {m.group(2)}*\n" + x[m.end():]
    expect(len(frags) == 47 and "50" in frags, f"Heracleon: {len(frags)} fragments")
    books["Fragments of Heracleon"] = {"1": frags}
    sources["Fragments of Heracleon"] = "comp. David Brons (Gnostic Society Library)"
    # the Cathars
    p = page_paragraphs("library/Interrogatio_Johannis.html")
    books["The Secret Supper"] = {"1": by_paragraph(segment(p, "I, John, your brother and partaker in tribulation", "##"))}
    sources["The Secret Supper"] = JAMES
    p = page_paragraphs("library/cathar-two-principles.htm")
    parts, current = {}, None
    for x in segment(p, "Part 1. On Free Will", "## Archive"):
        m = re.match(r"Part ([IVX]+|\d+)\. ", x)
        if m:
            current = str(int(m.group(1)) if m.group(1).isdigit() else roman(m.group(1)))
            parts[current] = [f"*{x}*"]
            continue
        if x.startswith("[In the manuscript"):                     # (the editors' note)
            continue
        x = x.replace('us." 84 And to the Galatians', 'us." And to the Galatians')    # (a stray note number)
        parts[current].append(re.sub(r"^\[(\d+)\.?\]\s*", r"\1 ", x))
    expect(list(parts) == [str(n) for n in range(1, 8)], f"Two Principles parts {list(parts)}")
    books["Book of the Two Principles"] = {}
    for k, v in parts.items():
        heading, rest = v[0], v[1:]
        chapter = by_number(rest, inline=False)
        first = next(iter(chapter))
        chapter[first] = heading + "\n" + chapter[first]
        books["Book of the Two Principles"][k] = chapter
    sources["Book of the Two Principles"] = "trans. Walter L. Wakefield and Austin P. Evans (1969)"
    service = segment(page_paragraphs("library/appa.htm"), "We have come before God", "The Occitan text is found")
    traditio = segment(page_paragraphs("library/traditio.htm"), "...You must realize", "The following original Occitan text")
    books["Cathar Ritual"] = {"1": by_paragraph(service), "2": by_paragraph(traditio)}
    sources["Cathar Ritual"] = "Lyon Ritual, unattributed translation (Gnostic Society Library)"
    for name, chapters in books.items():
        print(f"  {name}: " + ", ".join(f"{c} ({len(v)})" for c, v in chapters.items()))
    write("valentinian_cathar.json", books, sources, "Gnostic Society Library")


def write(file: str, books: dict, sources: dict, source: str, folder: str = "gnostic") -> None:
    path = ROOT / "data" / folder / file
    path.write_text(json.dumps({"source": source, "book_sources": sources, "books": books}, ensure_ascii=False,
                               indent=1), encoding="utf-8")
    print(f"  {path.name}: " + ", ".join(f"{b} ({sum(map(len, c.values()))})" for b, c in books.items()))


def nag_hammadi_more() -> None:
    books, sources = {}, {}
    for path, name in NHL_MISSING:
        translators, paras = nhl_page(path)
        expect(len(paras) > 10, f"{name}: {len(paras)} paragraphs")
        if any(re.match(r"1 [A-Z\[]", p) for p in paras):   # (the Apocryphon: Karen King's section numbers)
            books[name] = {"1": numbered_sections(paras)}
        else:
            books[name] = {"1": {str(i): p for i, p in enumerate(paras, 1)}}
        sources[name] = f"trans. {translators}"[:80]
    write("nag_hammadi_more.json", books, sources, "The Nag Hammadi Library, ed. James M. Robinson")


if __name__ == "__main__":
    only = sys.argv[1:]
    if not only or "nhl" in only:
        nag_hammadi_more()
    if not only or "james" in only:
        james()
    if not only or "mani" in only:
        manichaean_mandaean()
    if not only or "cathar" in only:
        valentinians_and_cathars()
    if not only or "fragments" in only:
        books, sources = {}, {}
        books["Gospel of Mary"] = gospel_of_mary()
        sources["Gospel of Mary"] = "unattributed translation (Gnostic Society Library)"
        untitled = library_text("library/untitl.htm", "The Untitled Text in the Bruce Codex")
        # its sections headed by a bare "2." paragraph, or opening one ("1. He set him up", "20. And those",
        # "21 ...."); the lists in them ("1. The first deep is the all-wise", "2. The second deep") numbered too: a
        # number is a list's if the paragraph before has the one before it
        chapters, last, before = {}, 0, ""
        for p in untitled:
            m = re.match(r"(\d{1,2})(?:\.(?:\s+|$)|\s(?=\.\.\.))", p.strip())
            listed = m and p.strip()[m.end():] and re.match(rf"{int(m.group(1)) - 1}\.\s+\S", before)
            before = p.strip()
            if m and not listed and int(m.group(1)) == last + 1:
                last = int(m.group(1))
                chapters[str(last)] = {}
                p = p[m.end():].strip()
            if p and last:
                chapters[str(last)][str(len(chapters[str(last)]) + 1)] = p
        expect(last >= 20, f"Untitled Text: {last} sections")
        books["Untitled Text of the Bruce Codex"] = chapters
        ieou = library_text("library/1ieo.htm", "The First Book of IEOU")
        books["First Book of Ieou"] = {"1": {str(i): p for i, p in enumerate(ieou, 1)}}
        for path, title, name in (("library/flora.htm", "Ptolemy's Letter to Flora", "Ptolemy's Letter to Flora"),
                                  ("library/ephip.htm", "On Righteousness", "Epiphanes, On Righteousness"),
                                  ("library/naas.htm", "The Naassene Psalm", "The Naassene Psalm"),
                                  ("library/basilide.htm", "Fragments from the Writings of Basilides",
                                   "Fragments of Basilides")):
            paras = [p for p in library_text(path, title)       # (the link to Jung's "Basilides", not his)
                     if not re.search(r"Septem Sermones|Modern Pseudepigraph", p)]
            books[name] = {"1": {str(i): p for i, p in enumerate(paras, 1)}}
        # the Naassene Psalm in two translations, the site's remarks before each: the modern one (1), and ANF's
        # verse from Hippolytus (2), without the Hippolytus prose that introduces it
        naas = list(books["The Naassene Psalm"]["1"].values())
        cut = [i for i, p in enumerate(naas) if p.startswith(("This is a modern", "This is the nineteenth-century"))]
        verse = next(i for i, p in enumerate(naas) if p.startswith("The world's producing law"))
        expect(cut and cut[0] == 0 and len(cut) == 2 and cut[1] < verse, "Naassene Psalm layout")
        books["The Naassene Psalm"] = {"1": {str(i): p for i, p in enumerate(naas[1:cut[1]], 1)},
                                       "2": {str(i): p for i, p in enumerate(naas[verse:], 1)}}
        excerpta = library_text("library/excr.htm", "Excerpta ex Theodoto")
        # (one long paragraph, its sections numbered bare: "...spirit. 2 The Valentinians...")
        text = " ".join(p for p in excerpta if not p.startswith('"Extracts from the Works'))
        sections = sequential(text, dot=False)
        expect(len(sections) == 86, f"Theodotus: {len(sections)} sections")    # (Casey's 86)
        books["Excerpts from Theodotus"] = {"1": sections}
        sources["Excerpts from Theodotus"] = "trans. Robert Pierce Casey (1934)"
        for name, chapters in books.items():
            # the site's footer, where it shares a paragraph with the text ("...to preach.\nThe Gospel of
            # Mary\nArchive | Library | ...", "(lacuna of four lines) | GNOSIS ARCHIVE | ...")
            for verses in chapters.values():
                for v in list(verses):
                    text = re.split(r"(?:\n[^\n]*)?\nArchive \| Library|\s*\|\s*GNOSIS ARCHIVE", verses[v])[0].strip()
                    if text:
                        verses[v] = text
                    else:
                        expect(v == list(verses)[-1], f"{name} {v}: emptied")
                        del verses[v]
            print(f"  {name}: {sum(map(len, chapters.values()))} passages")
        write("gnostic_fragments.json", books, sources, "Gnostic Society Library")
        write("pistis_sophia.json", {"Pistis Sophia": pistis_sophia()}, {}, "trans. G. R. S. Mead (1921)")
