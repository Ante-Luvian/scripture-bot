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
    latin_works = []
    for f in sorted(PATRISTICS.glob("*.json")):
        if f.name in SKIP_FILES or f.name in ("catena_aurea.json", "breviary_readings.json"):
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

    for entries in index.values():
        entries.sort(key=lambda e: (e[0], e[1], int(e[2].split(".")[0]) if e[2].split(".")[0].isdigit() else 0))
    OUT.write_text(json.dumps(index, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    n = sum(len(e) for e in index.values())
    by_rank = {r: sum(1 for es in index.values() for e in es if e[0] == r) for r in (1, 2, 3)}
    unresolved = sorted(k for k, v in resolved.items() if v is None)
    print(f"{len(index)} verses, {n} entries {by_rank} -> {OUT.relative_to(ROOT)} ({OUT.stat().st_size // 1024} KB)")
    print(f"book names not resolved ({len(unresolved)}):", unresolved[:60])
    print("Psalms numbered as the Latin Bible numbers them, in:", latin_works)


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
    m = re.search(r"(first|second|1|2)?\s*(?:epistle\s+(?:of\s+(?:st\.\s+)?)?)?john", w)
    if "epistle" in w and "john" in w:
        return "1 John"
    for word, book in (("matthew", "Matthew"), ("mark", "Mark"), ("luke", "Luke"), ("john", "John"),
                       ("acts", "Acts"), ("romans", "Romans"), ("galatians", "Galatians"), ("ephesians", "Ephesians"),
                       ("philippians", "Philippians"), ("colossians", "Colossians"), ("hebrews", "Hebrews"),
                       ("titus", "Titus"), ("philemon", "Philemon"), ("daniel", "Daniel"), ("genesis", "Genesis"),
                       ("isaiah", "Isaiah"), ("song of songs", "Song of Solomon")):
        if word in w:
            prefix = re.search(rf"(first|second|1|2)\s+(?:epistle\s+(?:to\s+the\s+)?)?{word}", w)
            if word in ("corinthians", "thessalonians", "timothy"):
                pass
            return book
    for word, book in (("corinthians", "Corinthians"), ("thessalonians", "Thessalonians"), ("timothy", "Timothy")):
        if word in w:
            return ("2 " if re.search(r"(second|2)\s+(?:epistle\s+(?:to\s+)?)?", w) and
                    re.search(rf"(second|2)\b.*{word}", w) else "1 ") + book
    return None


if __name__ == "__main__":
    main()
