"""
Repairs and rebuilds for the Neoplatonists, whose first build (deprecated/build_neoplatonic*.py) left them full
of the web: translators' footnote numbers in the text ("O Firmus 1 , that you"), page numbers ("|18"), Greek
words dropped ("Apollo is called the , slayer of wolves"), italics lost.

  iamblichus_gaps   On the Mysteries: Taylor prints Porphyry's questions, which Iamblichus answers, in italics, and
                    the first build lost them: 'you say, “.” Thus to speak, however, is not right'. Each verse with a
                    gap is found in Gutenberg's copy of the same translation (#72815) and filled from it. The bot's
                    chapters and verses stay as they are (citations don't change), and a fill is only taken when
                    the old verse's letters all appear, in order, in the new: it may only add what was lost.

    python scripts/build_neoplatonists.py [step ...]
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
CACHE = ROOT / "scripts" / ".cache" / "neoplatonists"
UA = {"User-Agent": "ScriptureBotCorpusBuilder/1.0 (Discord bot; low-volume one-off import)"}


def expect(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"unexpected: {message}")


def fetch(url: str, name: str) -> str:
    path = CACHE / name
    if not path.exists():
        CACHE.mkdir(parents=True, exist_ok=True)
        path.write_bytes(urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=120).read())
        time.sleep(1.5)
    raw = path.read_bytes()
    for enc in ("utf-8", "cp1252"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("latin-1")


def load(rel: str) -> dict:
    return json.loads((ROOT / "data" / rel).read_text(encoding="utf-8"))


def save(rel: str, payload: dict) -> None:
    raw = (ROOT / "data" / rel).read_text(encoding="utf-8")
    indent = 1 if raw.startswith('{\n "') else 2
    (ROOT / "data" / rel).write_text(json.dumps(payload, ensure_ascii=False, indent=indent), encoding="utf-8")


def key(text: str) -> str:
    """Letters only, lower case: for finding one text's words in another's, whatever the punctuation."""
    return re.sub(r"[^a-z]", "", text.lower())


def subsequence(short: str, long: str) -> bool:
    it = iter(long)
    return all(c in it for c in short)


# ── Iamblichus: the lost italics ───────────────────────────────────────────

GAP = re.compile(r"“\s*[,.;:]?\s*”|\s(?=[,;.:)])|\(\s*\)|\[\s*\]")
FIND_GAP = re.compile(r"“\s*[,.;:]?\s*”|\b(?:the|of|a|an|to|in|is|and|or|by|with|from|as|be|called|says|say)\s+[,;.:)]"
                      r"(?!\d)|\(\s*\)|\[\s*\]|^The of |, , ")
BOUND = re.compile(r"(?<=[.?!])\*?”?\s|¶")
# five verses where a word went with no punctuation beside it, so the gaps can't be told from the text:
# where each begins and ends in Taylor's
IAMBLICHUS_SPANS = {
    ("21", "13"): ("Farther still, having said", "no others than these."),
    ("26", "3"): ("Since, however, the order of all the Gods is profoundly united", "accedes to all of them."),
    ("85", "18"): ("*first* species of prayer is", "a knowledge of, divinity."),
    ("86", "3"): ("of these pertains to", "of divine fire*."),
    ("86", "14"): ("Again, from hence the", "imparted by the Gods."),
}


def taylor_plain(n: int = 72815) -> str:
    """A Gutenberg book of Taylor's as one run of text: italics as *...*, without page numbers, note numbers or
    headings."""
    t = fetch(f"https://www.gutenberg.org/cache/epub/{n}/pg{n}-images.html", f"pg{n}.html")
    t = t[t.find("*** START"):t.find("*** END")]
    t = re.sub(r'(?is)<a[^>]*class="fnanchor"[^>]*>.*?</a>|<span class="(?:page(?:num|no)|pb)"[^>]*>.*?</span>', "", t)
    t = re.sub(r"(?is)<(em|i)>(.*?)</\1>", lambda m: "*" + m.group(2).strip() + "*" if m.group(2).strip() else "", t)
    t = re.sub(r"(?is)<br\s*/?>", " ", t)
    t = re.sub(r"(?is)<h\d[^>]*>.*?</h\d>", " ¶ ", t)
    t = html.unescape(re.sub(r"<[^>]+>", " ", t))
    t = re.sub(r"\bCHAP\. [IVXL]+\.", " ¶ ", t)
    t = re.sub(r"\s*\[\d+\]", "", t)
    t = re.sub(r"(?<=[A-Za-z*”\"')\]])\s+(?=[,;:](?:\s|$))", "", t)         # ("earthquakes ,": where a note mark was)
    return re.sub(r"\s+", " ", t)


class Finder:
    def __init__(self, plain: str):
        self.plain = plain
        self.pos = [i for i, c in enumerate(plain) if c.isascii() and c.isalpha()]
        self.K = "".join(plain[i].lower() for i in self.pos)

    def _line_up(self, pieces: list, at: int):
        found = []
        for p in pieces:
            k = key(p)
            if len(k) < 12:
                continue
            i = self.K.find(k, at)
            if i < 0 or (found and i - at > 400):
                return None
            found.append((i, i + len(k)))
            at = i + len(k)
        return found or None

    def fill(self, t: str) -> "str | None":
        """The verse as Taylor printed it, found by its gap-free pieces, from the start of its first sentence to
        the end of its last."""
        pieces = GAP.split(t)
        first = next((key(p) for p in pieces if len(key(p)) >= 12), None)
        if first is None:
            return None
        found, at = None, 0
        while found is None:                     # (each place the first piece occurs, till the rest follow it)
            at = self.K.find(first, at)
            if at < 0:
                return None
            found = self._line_up(pieces, at)
            at += 1
        plain, pos = self.plain, self.pos
        a, b = pos[found[0][0]], pos[found[-1][1] - 1] + 1
        if len(key(pieces[0])) < 12:                          # a gap at the start: back to the sentence's start
            prior = [m.end() for m in BOUND.finditer(plain, max(0, a - 300), a)]
            a = prior[-1] if prior else a
        if len(key(pieces[-1])) < 12 or not t.rstrip().endswith(plain[b - 1:b]):
            m = re.search(r"[.?!](?:\*?”)?(?=\s|$)", plain[b - 1:b + 300])
            b = b - 1 + m.end() if m else b
        else:
            b += re.match(r"[^\sA-Za-z]*", plain[b:]).end()
        return re.sub(r"\s*¶\s*", " ", plain[a:b]).strip()

    def span(self, start: str, end: str) -> "str | None":
        i = self.plain.find(start)
        j = self.plain.find(end, i)
        if i < 0 or j < 0:
            return None
        prior = [m.end() for m in BOUND.finditer(self.plain, max(0, i - 300), i + 1)]
        i = prior[-1] if prior and not start[:1].isupper() else i
        return re.sub(r"\s*¶\s*", " ", self.plain[i:j + len(end)]).strip()


def iamblichus_gaps() -> None:
    _fill_gaps("On the Mysteries", 72815, IAMBLICHUS_SPANS)
    _fill_gaps("Life of Pythagoras", 63300, {})                     # (Taylor's too, with the same losses)


def _fill_gaps(book_name: str, gutenberg: int, spans: dict) -> None:
    rel = "classical/iamblichus.json"
    payload = load(rel)
    book = payload["books"][book_name]
    finder = Finder(taylor_plain(gutenberg))
    filled, left = 0, []
    for ch, verses in book.items():
        for v, t in verses.items():
            if not FIND_GAP.search(t):
                continue
            new = finder.span(*spans[(ch, v)]) if (ch, v) in spans else finder.fill(t)
            if new is None or not subsequence(key(t), key(new)) or len(key(new)) > len(key(t)) * 2.5 + 40:
                left.append(f"{ch}:{v}")
                continue
            if new != t:
                verses[v] = new
                filled += 1
    save(rel, payload)
    print(f"  {book_name}: {filled} verses filled" + (f"; not settled: {', '.join(left)}" if left else ""))


# ── Repairs from tertullian.org (Porphyry, Marinus, Julian) ────────────────
# These came from Roger Pearse's transcriptions on tertullian.org, which mark each footnote with a link and each
# printed page with "|17", and set Greek in its own spans: the first build kept the numbers and lost the Greek.
# Each verse is found in the page's own text by its letters alone (so the stray numbers and the missing Greek
# don't hinder finding it) and replaced by that stretch of the page, cleanly read: the footnote links and page
# numbers left out, the Greek and italics kept. The chapters and verses stay as they are. A verse is only
# replaced when its old letters all appear, in order, in the new text.

TERTULLIAN = "https://www.tertullian.org/fathers/{}.htm"


def _italic(m) -> str:
    """<i>, slayer of wolves; </i> -> ", *slayer of wolves*; ": the space and stops outside the asterisks."""
    inner = re.sub(r"<[^>]+>", "", m.group(2))
    lead = re.match(r"^[\s,;:]*", inner).group(0)
    trail = re.search(r"[\s,;:]*$", inner[len(lead):]).group(0)
    core = inner[len(lead):len(inner) - len(trail)]
    return f"{lead}*{core}*{trail}" if core.strip() else inner


def _spionic(m) -> str:
    """Greek set in the old SPIonic font, as tertullian.org's own Beta Code ("fro&nimoj"), as Greek: φρόνιμος."""
    import corpus_clean
    text = corpus_clean.greek_from_tertullian(html.unescape(re.sub(r"<[^>]+>", "", m.group(1))))
    text = re.sub(r"(?<![\w])9(?=[A-Za-z])", ")", text)          # ("9Ai+dhj": the breathing on a capital)
    return re.sub(r"[A-Za-z0-9#\]\[&~_|/\\=)(+]*[A-Za-z][A-Za-z0-9#\]\[&~_|/\\=)(+]*",
                  lambda t: corpus_clean.beta_to_greek("".join(corpus_clean._TERT.get(c, c) for c in t.group(0)).lower()),
                  text)


def tertullian_plain(page: str, chapters: bool = False) -> str:
    t = fetch(TERTULLIAN.format(page), f"{page}.htm")
    t = re.sub(r"(?is)<head.*?</head>|<style.*?</style>|<script.*?</script>", " ", t)
    notes = re.search(r'(?is)<a\s+name="?#?1"?\s*>|This text was transcribed by', t)   # (the notes, the credits)
    t = t[:notes.start()] if notes else t
    first = re.search(r'(?is)<span class="chapterno">', t) if chapters else None   # (the title and header)
    t = t[first.start():] if first else t
    t = re.sub(r'(?is)<font face="?SPIonic"?>(.*?)</font>', _spionic, t)
    t = re.sub(r'(?is)<a\s+href="#[^"]*">\s*<sup>.*?</sup>\s*</a>|<sup>\s*<a\s+href="#[^"]*">.*?</a>\s*</sup>|<a\s+name="p\d+[a-z]?">\s*<span class=["\']?pb["\']?>[^<]*</span>\s*</a>', " ", t)
    t = re.sub(r"(?is)<span class=\"?pb\"?>\s*\|\d+\s*</span>|<sup>\s*\d+\s*</sup>", " ", t)   # (and unlinked note numbers)
    t = re.sub(r'(?is)<span class="chapterno">.*?</span>', " ¶ ", t)
    t = re.sub(r"(?is)<(i|em)>(.*?)</\1>", _italic, t)
    t = re.sub(r"(?is)<br\s*/?>", " ", t)
    t = re.sub(r"(?is)</?p[^>]*>|<h\d[^>]*>.*?</h\d>|<hr[^>]*>", " ¶ ", t)
    t = html.unescape(re.sub(r"<[^>]+>", " ", t)).replace("\xa0", " ")
    t = re.sub(r"\|\d+", " ", t)                                        # (a page number the markup didn't wrap)
    t = re.sub(r"\*\s+([,.;:!?])", r"*\1", t)
    t = re.sub(r"(?<=[A-Za-z*”\"')\]])\s+(?=[,;:.](?:\s|$))", "", t)      # ("says , it": where a note mark was)
    t = re.sub(r"[ \t]+", " ", t)
    t = re.sub(r"\s*¶\s*(\d{1,3}\.\s)?", " ¶ ", t)                       # (Marinus numbers his paragraphs)
    return re.sub(r"\s+", " ", t)


def old_key(t: str) -> str:
    """A verse's letters, less the font-code Greek the first build left in it ("9Ai+dhj"): the source has Greek
    there now, whose letters aren't these."""
    return key(re.sub(r"\S*(?:[0-9+&#~|\]\[][A-Za-z]|[A-Za-z][0-9+&#~|\]\[])\S*", " ", t))


def _candidates(finder: "Finder", t: str):
    """Stretches of the source that may be this verse, most likely first: its letters found whole (and only once);
    found by the pieces between its gaps; or from where its beginning is to where its end is."""
    k = old_key(t)
    i = finder.K.find(k) if len(k) >= 20 else -1
    if i >= 0 and finder.K.find(k, i + 1) < 0:
        a, b = finder.pos[i], finder.pos[i + len(k) - 1] + 1
        lead = re.search(r"[“‘\"'*(\[]*$", finder.plain[max(0, a - 3):a])          # (opening quotes, italics)
        a -= len(lead.group(0)) if lead else 0
        b += re.match(r"[^\sA-Za-z¶]*", finder.plain[b:]).end()
        yield finder.plain[a:b]
    yield finder.fill(t)
    if len(k) >= 50:                                    # whole phrases dropped, with no trace: by its two ends
        for size in (30, 15):
            yield _between_ends(finder, k, size)


def _between_ends(finder: "Finder", k: str, size: int) -> "str | None":
    """The stretch from where the verse's first letters are to where its last are (a little longer than the verse,
    not more), for a verse that lost whole phrases ("this deity (although very much...) has now been")."""
    head, tail = k[:size], k[-30:]
    i = finder.K.find(head)
    while i >= 0:
        j = finder.K.find(tail, i + len(k) - 60)
        if 0 <= j <= i + len(k) * 1.5 + 200:
            a, b = finder.pos[i], finder.pos[j + len(tail) - 1] + 1
            b += re.match(r"[^\sA-Za-z¶]*", finder.plain[b:]).end()
            return finder.plain[a:b]
        i = finder.K.find(head, i + 1)
    return None


def _span_of(finder: "Finder", t: str) -> "str | None":
    """The first candidate the old verse's letters all appear in, in order, that isn't much longer than it."""
    k = old_key(t)
    for new in _candidates(finder, t):
        if new and subsequence(k, key(new)) and len(key(new)) <= len(k) * 1.5 + 60:
            return re.sub(r"(?:\s*¶\s*)+", "\n\n", new).strip()
    return None


def _letter_index(text: str, n: int) -> int:
    """Where the nth letter (as key() counts them) of a text is."""
    seen = -1
    for i, c in enumerate(text):
        if c.isascii() and c.isalpha():
            seen += 1
            if seen == n:
                return i
    return len(text)


def _cut_before(new: str, next_head: str) -> str:
    """The text up to where the next verse begins in it, if it does (past its own first letters)."""
    k = key(new)
    p = k.find(next_head, 20) if len(next_head) >= 15 else -1
    return new[:_letter_index(new, p)].rstrip(" “\"*(\n") if p > 0 else new


def _cut_after(new: str, prev_tail: str) -> str:
    """The text from where the verse before ends in it, if it does (before its own last letters)."""
    k = key(new)
    p = k.find(prev_tail) if len(prev_tail) >= 15 else -1
    if p < 0 or p + len(prev_tail) >= len(k) - 20:
        return new
    i = _letter_index(new, p + len(prev_tail))
    return new[i:].lstrip(" ,.;:!?”\"*)\n") if i < len(new) else new


def repair(rel: str, sources: dict, chapters: bool = False) -> None:
    """sources: {book: [tertullian.org pages]}."""
    payload = load(rel)
    for book, pages in sources.items():
        finder = Finder(" ¶ ".join(tertullian_plain(p, chapters) for p in pages))
        verses_changed, left = 0, []
        order = [(ch, v) for ch, verses in payload["books"][book].items() for v in verses]
        old = {(ch, v): t for ch, verses in payload["books"][book].items() for v, t in verses.items()}
        for n, (ch, v) in enumerate(order):
            verses, t = payload["books"][book][ch], old[(ch, v)]
            new = _span_of(finder, t)
            if new is None:
                left.append(f"{ch}:{v}")
                continue
            # not into the verse before or after: a stretch that ran on is cut where its neighbour begins or ends
            if n + 1 < len(order):
                new = _cut_before(new, old_key(old[order[n + 1]])[:25])
            if n:
                new = _cut_after(new, old_key(old[order[n - 1]])[-25:])
            if not subsequence(old_key(t), key(new)):
                left.append(f"{ch}:{v}")
                continue
            new = re.sub(r"[ \t]+\n", "\n", new)
            if new != t:
                verses[v] = new
                verses_changed += 1
        print(f"  {book}: {verses_changed} verses repaired" + (f"; not found, left as they were: {', '.join(left)}" if left else ""))
    save(rel, payload)


PORPHYRY = {"On Abstinence": [f"porphyry_abstinence_0{n}_book{n}" for n in range(1, 5)],
            "On the Cave of the Nymphs": ["porphyry_cave_of_nymphs_02_translation"],
            "Auxiliaries to the Intelligibles": ["porphyry_sententiae_02_trans"],
            "Letter to Marcella": ["porphyry_marcella_02_text"],
            "Life of Pythagoras": ["porphyry_life_of_pythagoras_02_text"]}


# each book's own translator (the file was credited "Taylor (1823), MacKenna (1917)" throughout), as the source
# pages say
PORPHYRY_CREDITS = {"On Abstinence": "trans. Thomas Taylor (1823)", "On the Cave of the Nymphs": "trans. Thomas Taylor (1823)",
                    "Auxiliaries to the Intelligibles": "trans. Thomas Taylor (1823)",
                    "Letter to Marcella": "trans. Alice Zimmern (1896)", "Life of Pythagoras": "trans. K. S. Guthrie (1920)",
                    "Life of Plotinus": "trans. Stephen MacKenna (1917)"}


def porphyry() -> None:
    repair("classical/porphyry.json", PORPHYRY, chapters=True)
    payload = load("classical/porphyry.json")
    rest = {k: v for k, v in payload.items() if k not in ("source", "book_sources")}
    save("classical/porphyry.json", {"source": "trans. Thomas Taylor (1823)", "book_sources": PORPHYRY_CREDITS, **rest})


def marinus() -> None:
    repair("classical/marinus.json", {"Life of Proclus": ["marinus_01_life_of_proclus"]})


def julian() -> None:
    repair("classical/julian.json", {"Hymn to King Helios": ["julian_apostate_1_sun"],
                                     "Hymn to the Mother of Gods": ["julian_apostate_2_mother"],
                                     "Against the Galilaeans": ["julian_apostate_galileans_1_text"]})


# ── Porphyry's Life of Plotinus, MacKenna's (1917) ─────────────────────────
# The first build took it from sacred-texts.com and got it in pieces: chapters 1-4 and 7-8 missing, the titles of
# Plotinus's treatises made chapters of their own, the rest out of order, the site's links on the end. Rebuilt
# from Wikisource's transcription of the 1917 volume: its 26 chapters, a verse a paragraph, the lists of treatises
# a line each.

def life_of_plotinus() -> None:
    import urllib.parse
    url = "https://en.wikisource.org/w/api.php?" + urllib.parse.urlencode({
        "action": "parse", "page": "Plotinus (MacKenna)/Volume 1/Porphyry's Life of Plotinus", "prop": "text",
        "format": "json", "formatversion": 2})
    page = json.loads(fetch(url, "life_of_plotinus.json"))["parse"]["text"]
    page = re.sub(r'(?is)<span[^>]*class="[^"]*pagenum[^"]*"[^>]*>.*?</span>|<sup[^>]*class="reference"[^>]*>.*?</sup>',
                  "", page)
    page = re.sub(r"(?is)<(i|em)>(.*?)</\1>", _italic, page)
    # (a chapter that begins a scanned page has its number outside any paragraph: "</p>7. <p>Plotinus had...")
    page = re.sub(r"(?is)(</p>|</div>|>)\s*(\d{1,2})\.\s*(?=<p>)", r"\1<p>\2.</p>", page)
    chapters, current = {}, None
    for p in re.findall(r"(?is)<p>(.*?)</p>", page):
        p = re.sub(r"(?is)<br\s*/?>", "\n", p)
        text = html.unescape(re.sub(r"<[^>]+>", "", p)).replace("\xa0", " ")
        text = "\n".join(re.sub(r"\s+", " ", line).strip() for line in text.split("\n"))
        text = re.sub(r"\n{2,}", "\n", text).strip()
        m = re.fullmatch(r"(\d{1,2})\.", text)
        if m:
            current = m.group(1)
            chapters[current] = {}
            continue
        if current and text:
            chapters[current][str(len(chapters[current]) + 1)] = text
    expect(list(chapters) == [str(n) for n in range(1, 27)], f"chapters {list(chapters)}")
    payload = load("classical/porphyry.json")
    payload["books"]["Life of Plotinus"] = chapters
    save("classical/porphyry.json", payload)
    print(f"  Life of Plotinus: {len(chapters)} chapters, {sum(len(c) for c in chapters.values())} paragraphs")


BUILDS = {"iamblichus_gaps": iamblichus_gaps, "porphyry": porphyry, "marinus": marinus, "julian": julian,
          "life_of_plotinus": life_of_plotinus}


def main(names: list) -> None:
    for name in names or BUILDS:
        print(name)
        BUILDS[name]()


if __name__ == "__main__":
    main(sys.argv[1:])
