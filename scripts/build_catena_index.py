"""
The Fathers on each verse of the Bible, from the library's own texts -> data/catena_index.json, for !catena (and the
Catena button): {"John 3:16": [[rank, book, chapter, verse, offset], ...]}, strongest first, where book/chapter/verse
is a passage of the library and offset where in it the verse is taken up.

    rank 1  Aquinas's Catena Aurea: the Fathers on that Gospel verse, gathered (its passages and the verses they cover)
    rank 2  a commentary or homily on that book of the Bible that cites the verse (Chrysostom's Homilies on Matthew
            citing Matthew, Augustine on the Psalms, Gregory's Morals on Job...), and the Breviary's homily on that
            Gospel passage
    rank 3  a Father quoting the verse anywhere else

The translators of the Fathers mark the Bible they quote ("[ Matthew 5:3 ]", "[Ps. 22:1]", "[Job 1:1]"); those marks
are read, their book names resolved as !verse resolves them. Left out: Tatian's Diatessaron (the Gospels themselves,
harmonised: not comment on them).

    python scripts/build_catena_index.py
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
OUT = ROOT / "data" / "catena_index.json"
PATRISTICS = ROOT / "data" / "patristics"
SKIP_FILES = {"tatian.json"}                     # (the Diatessaron: the Gospels, not comment on them)
REF = re.compile(r"\[\s*((?:[1-4]\s?)?[A-Z][A-Za-z.]*(?:\s(?:of\s)?[A-Z][a-z.]+)*)\s+(\d{1,3}):(\d{1,3})"
                 r"(?:\s*[-–]\s*(\d{1,3}))?(?:[,;][^\]]*)?\s*\]")
MAX_SPAN = 40
# abbreviations !verse doesn't know, as the translators wrote them (and their slips: "Rrov.", "Hev.")
EXTRA = {"Cant.": "Song of Solomon", "Eccles.": "Ecclesiastes", "Ez.": "Ezekiel", "Is": "Isaiah", "Is.": "Isaiah",
         "Lament.": "Lamentations", "Mat.": "Matthew", "Numb.": "Numbers", "Rrov.": "Proverbs", "Hev.": "Hebrews",
         "From Acts": "Acts", "See Acts": "Acts", "From Psalm": "Psalms", "Perhaps Jeremiah": "Jeremiah",
         "In Jer.": "Jeremiah"}


def vulgate_psalm(n: int) -> int:
    """A psalm's number in the Latin Bible (the Septuagint's) as the KJV numbers it: Vulgate 22 is KJV 23. (Where one
    Latin psalm is two Hebrew ones -- 9, 113 -- the first.)"""
    if n <= 8 or n >= 148:
        return n
    if n == 9:
        return 9
    if n <= 112:
        return n + 1
    if n == 113:
        return 114
    if n in (114, 115):
        return 116
    if n <= 145:
        return n + 1
    return 147


def words(s: str) -> set:
    return {w for w in re.findall(r"[a-z]{4,}", s.lower())} - {"that", "them", "they", "unto", "shall", "with", "have",
                                                                 "thou", "thee", "thine", "from", "which", "there"}                                    # (a reference to a whole stretch counts for its first 40 verses)


def lookup():
    import scripture_lookup
    return scripture_lookup.ScriptureLookup()


def canonical_books(L) -> dict:
    """Bible book name -> itself, for the books a reference may name (the Protestant canon and the Apocrypha)."""
    names = {}
    for corpus in ("kjv",):
        for b in L._data.get(corpus, {}):
            names[b] = b
    return names


def main():
    L = lookup()
    bible = canonical_books(L)
    resolved = {}

    def book_of(name: str):
        """A reference's book name as the Bible's ("Ps." -> Psalms, "1 Cor" -> 1 Corinthians), or None."""
        if name in EXTRA:
            return EXTRA[name]
        if name not in resolved:
            got = None
            try:
                r = L._resolve_book(name.rstrip("."))
                got = r[1] if r and r[1] in bible else None
            except Exception:
                got = None
            resolved[name] = got
        return resolved[name]

    index: dict = {}

    def add(book, ch, first, last, entry):
        for v in range(first, min(last, first + MAX_SPAN - 1) + 1):
            index.setdefault(f"{book} {ch}:{v}", []).append(entry)

    # rank 1: the Catena Aurea
    ca = json.loads((PATRISTICS / "catena_aurea.json").read_text(encoding="utf-8"))
    for name, chapters in ca["books"].items():
        gospel = name.rsplit(" ", 1)[-1]
        spans = ca.get("spans", {}).get(name, {})
        for ch, verses in chapters.items():
            for v in verses:
                add(gospel, int(ch), int(v), spans.get(f"{ch}:{v}", int(v)), [1, name, ch, v, 0])

    # rank 2: the Glossa Ordinaria, verse by verse (its books' verses already on the KJV's numbering)
    gl = PATRISTICS / "glossa_ordinaria.json"
    if gl.exists():
        for name, chapters in json.loads(gl.read_text(encoding="utf-8"))["books"].items():
            book = name.replace("Glossa Ordinaria on ", "")
            for ch, verses in chapters.items():
                for v in verses:
                    add(book, int(ch), int(v), int(v), [2, name, ch, v, 0])

    # rank 2: the Breviary's homilies on their Gospel
    br = json.loads((PATRISTICS / "breviary_readings.json").read_text(encoding="utf-8"))
    brname = next(iter(br["books"]))
    for key, note in br.get("gospels", {}).items():
        ch_v = key.split(":")
        m = re.match(r"(.+?)\s+(\d+):(\d+)(?:\s*[-–]\s*(\d+))?", note["gospel"])
        book = book_of(m[1]) if m else None
        if book:
            text = br["books"][brname][ch_v[0]][ch_v[1]]
            homily = text.find("\n", text.find("*On "))                     # (the homily, after its Gospel)
            add(book, int(m[2]), int(m[3]), int(m[4] or m[3]), [2, brname, ch_v[0], ch_v[1], max(homily, 0)])

    kjv_psalms = L._data["kjv"]["Psalms"]

    def latin_numbered(chapters) -> bool:
        """Whether a work's translator numbered the Psalms as the Latin Bible does: the words before its Psalm marks
        agree better with the KJV's verse under the Latin numbering than under its own."""
        own = latin = 0
        for verses in chapters.values():
            for text in verses.values():
                for m in REF.finditer(text):
                    if book_of(m[1]) != "Psalms":
                        continue
                    before = words(text[max(0, m.start() - 220):m.start()])
                    n, v = int(m[2]), m[3]
                    a = words(kjv_psalms.get(str(n), {}).get(v, ""))
                    b = words(kjv_psalms.get(str(vulgate_psalm(n)), {}).get(v, ""))
                    own += len(before & a) > len(before & b)
                    latin += len(before & b) > len(before & a)
        return latin > own * 2 and latin >= 5

    # ranks 2 and 3: the Fathers' own references
    latin_works, lemma_counts = [], {}
    for f in sorted(PATRISTICS.glob("*.json")):
        if f.name in SKIP_FILES or f.name in ("catena_aurea.json", "breviary_readings.json", "glossa_ordinaria.json"):
            continue
        data = json.loads(f.read_text(encoding="utf-8"))
        for work, chapters in data.get("books", {}).items():
            on = commentary_on(work)
            latin = latin_numbered(chapters)
            if latin:
                latin_works.append(work)
            for ch, verses in chapters.items():
                for v, text in verses.items():
                    seen = set()
                    for m in REF.finditer(text):
                        book = book_of(m[1])
                        if not book:
                            continue
                        ch_n = vulgate_psalm(int(m[2])) if latin and book == "Psalms" else int(m[2])
                        key = (book, ch_n, m[3])
                        if key in seen:
                            continue
                        seen.add(key)
                        rank = 2 if on and on == book else 3
                        add(book, ch_n, int(m[3]), int(m[4] or m[3]), [rank, work, ch, v, m.start()])
            # Chrysostom's homilies on Acts go over their verses again under "Recapitulation, Acts 9:26"
            if on:
                for ch, verses in chapters.items():
                    for v, text in verses.items():
                        for m in re.finditer(r"Recapitulation,?\s+([1-3]?\s?[A-Z][a-z]+)\s+(\d+):(\d+)(?:\s*[-–]\s*(\d+))?",
                                             text):
                            if book_of(m[1]) == on:
                                add(on, int(m[2]), int(m[3]), int(m[4] or m[3]), [2, work, ch, v, m.start()])
            # a commentary's own verse, where it quotes it rather than marking it (Chrysostom's homilies, the Morals)
            if on and on in L._data["kjv"]:
                found = lemmas(L._data["kjv"][on], chapters, job=(on == "Job"))
                for (bch, bv), (ch, v) in found:
                    add(on, bch, bv, bv, [2, work, ch, v, 0])
                lemma_counts[work] = len(found)

    for entries in index.values():
        entries.sort(key=lambda e: (e[0], e[1], int(e[2].split(".")[0]) if e[2].split(".")[0].isdigit() else 0))
    OUT.write_text(json.dumps(index, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    n = sum(len(e) for e in index.values())
    by_rank = {r: sum(1 for es in index.values() for e in es if e[0] == r) for r in (1, 2, 3)}
    unresolved = sorted(k for k, v in resolved.items() if v is None)
    print(f"{len(index)} verses, {n} entries {by_rank} -> {OUT.relative_to(ROOT)} ({OUT.stat().st_size // 1024} KB)")
    print(f"book names not resolved ({len(unresolved)}):", unresolved[:60])
    print("Psalms numbered as the Latin Bible numbers them, in:", latin_works)
    print("verses found by their quotation:", sorted(((n, w) for w, n in lemma_counts.items() if n), reverse=True)[:25])


def shingles(s: str, n: int = 3) -> set:
    w = re.findall(r"[a-z]+", s.lower())
    return {" ".join(w[i:i + n]) for i in range(len(w) - n + 1)}


def lemmas(book: dict, chapters: dict, job: bool = False) -> list:
    """[((the book's chapter, verse), (the work's chapter, verse))]: the paragraphs of a commentary that take up a verse
    of its book by quoting it -- a homily's section opening with the verse it explains (Chrysostom), or the Morals'
    "*Ver. 10.* *Wilt thou bind...*" -- and the paragraphs after it, to the next. The quotation must share at least half
    of the verse's three-word runs (the translations are near the KJV's) and the search moves on through the book as
    the commentary does, a little back or well forward from the last verse found, so a stray echo isn't taken."""
    order = [(int(c), int(v)) for c in sorted(book, key=int) for v in sorted(book[c], key=int)]
    # (word pairs: the translators' wording differs from the KJV's in small ways -- "You men of Israel, hear these my
    # words" -- that break longer runs; the search's moving on through the book keeps a chance match out)
    n = 3 if job else 2
    sh = [shingles(book[str(c)][str(v)], n) for c, v in order]
    pos = 0
    out, current, carried = [], None, 0
    for wch in sorted(chapters, key=lambda c: [int(x) if x.isdigit() else 0 for x in re.split(r"\D+", c) if x] or [0]):
        for wv in sorted(chapters[wch], key=lambda x: int(x) if x.isdigit() else 0):
            text = chapters[wch][wv]
            hit = None
            if job:
                m = re.search(r"\*(?:Chap\. [xvil]+\. ver\.|Ver\.) (\d+)[^*]*\* \*([^*]+)\*", text)
                if m:
                    n, q = int(m[1]), shingles(m[2])
                    best = max(((len(q & sh[i]) / max(1, len(sh[i])), i) for i, (c, v) in enumerate(order)
                                if v == n and pos - 40 <= i <= pos + 400), default=(0, None))
                    if best[1] is not None and best[0] >= 0.25:
                        hit = best[1]
            elif re.match(r"\*?Ver(?:se)?s?\.\s*\d", text):
                # "Ver. 19, 20. That I might live..." (Chrysostom on Paul): the verse is given; its chapter is the one
                # being read or the next, whichever the words agree with better
                nums = [int(n) for n in re.findall(r"\d+", re.match(r"\*?Ver(?:se)?s?\.\s*([\d,\s–-]+)", text)[1])]
                q = shingles(text[:400], n)
                here = order[pos][0] if pos < len(order) else 1
                options = [i for i, (c, v) in enumerate(order) if v == nums[0] and c in (here, here + 1)]
                if not options and current is None:
                    options = [i for i, (c, v) in enumerate(order) if v == nums[0]]
                if options:
                    best = max(options, key=lambda i: (len(q & sh[i]), -i))
                    if not (order[best][0] == here + 1 and not (q & sh[best]) and nums[0] > order[pos][1]):
                        hit = best
                    else:
                        hit = next((i for i in options if order[i][0] == here), best)
            else:
                head = shingles(" ".join(re.findall(r"\S+", text)[:70]), n)
                best = (0, None)
                for i in range(max(0, pos - 3), min(len(order), pos + 80)):
                    if len(sh[i]) < 4:
                        continue
                    # (shared pairs against the verse's, up to 10: a homily often quotes the start of a long verse only)
                    score = len(head & sh[i]) / min(len(sh[i]), 10)
                    if score > best[0]:
                        best = (score, i)
                if best[1] is not None and best[0] >= 0.5:
                    hit = best[1]
                elif len(head) >= 6:
                    # (fallen behind -- a section the search missed -- or a homily out of order: anywhere in the
                    # book, if the quotation is closer still)
                    far = max(((len(head & s) / min(len(s), 10), i) for i, s in enumerate(sh) if len(s) >= 5),
                              default=(0, None))
                    if far[1] is not None and far[0] >= 0.7:
                        hit = far[1]
            if hit is not None:
                pos, current, carried = hit, order[hit], 0
                out.append((current, (wch, wv)))
            elif current is not None and carried < 3:
                carried += 1                                   # (the paragraphs after it explain it too)
                out.append((current, (wch, wv)))
        current, carried = None, 0                             # (a new chapter of the work: a new homily)
    return out


def commentary_on(work: str) -> "str | None":
    """The book of the Bible a work is a commentary or homilies on, from its title, or None."""
    w = work.lower()
    if not re.search(r"homil|commentar|exposition|enarration|tractate|sermons on|moral|hexa[eë]meron|on the "
                     r"(?:gospel|epistle|apocalypse|psalms)|^on (?:luke|matthew|john|mark)", w):
        return None
    if "hexa" in w:
        return "Genesis"
    if "job" in w:
        return "Job"
    if "apocalypse" in w or "revelation" in w:
        return "Revelation"
    if "psalm" in w:
        return "Psalms"
    if "epistle" in w and "john" in w and "gospel" not in w:
        return "1 John"
    for word, book in (("matthew", "Matthew"), ("mark", "Mark"), ("luke", "Luke"), ("john", "John"),
                       ("acts", "Acts"), ("romans", "Romans"), ("galatians", "Galatians"), ("ephesians", "Ephesians"),
                       ("philippians", "Philippians"), ("colossians", "Colossians"), ("hebrews", "Hebrews"),
                       ("titus", "Titus"), ("philemon", "Philemon"), ("daniel", "Daniel"), ("genesis", "Genesis"),
                       ("isaiah", "Isaiah"), ("song of songs", "Song of Solomon")):
        if word in w:
            return book
    for word, book in (("corinthians", "Corinthians"), ("thessalonians", "Thessalonians"), ("timothy", "Timothy")):
        if word in w:
            return ("2 " if re.search(rf"\b(second|2)\b.*{word}", w) else "1 ") + book
    return None


if __name__ == "__main__":
    main()
