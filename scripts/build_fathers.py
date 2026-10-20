"""
The Church Fathers (data/patristics), rebuilt from Schaff's Ante-Nicene and Nicene & Post-Nicene Fathers
(38 volumes, CCEL's ThML), where the original one-off scripts (now in deprecated/) left works empty or
cut short.

  python scripts/build_fathers.py download      fetch the 38 volumes into scripts/sources/ (cached)
  python scripts/build_fathers.py compare       rebuild every work found in them and compare it with
                                                data/patristics: a report, nothing written
  python scripts/build_fathers.py write         replace the works the comparison shows are better rebuilt

A work is only replaced when its rebuild keeps the chapter numbers people cite (the same chapters,
starting the same way) and is at least as complete, or when the work as stored is plainly broken
(next to empty, or missing most of its chapters). Everything else stays as it is.
"""
import difflib
import html
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_reformation import ccel, clean, thml_divs, tidy  # noqa: E402
from build_reformation import thml_flat as _thml_flat  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "patristics"
REPORT = ROOT / "scripts" / "sources" / "fathers_report.json"

VOLUMES = ([f"anf{n:02d}" for n in range(1, 11)] + [f"npnf1{n:02d}" for n in range(1, 15)]
           + [f"npnf2{n:02d}" for n in range(1, 15)])


def thml_flat(fragment: str) -> list:
    """Paragraphs of a ThML fragment, without the editors' notes (which CCEL nests inside them)."""
    return _thml_flat(re.sub(r"(?is)<note\b.*?</note>", "", fragment))


def volume(v: str) -> str:
    return ccel(f"schaff/{v}")


def download() -> None:
    for v in VOLUMES:
        try:
            print(f"{v}: {len(volume(v)) // 1000:,} kB")
        except Exception as e:
            print(f"{v}: FAILED ({e})")


# ── finding a work in the volumes ────────────────────────────────────────────

def norm(title: str) -> str:
    """A title for comparing: lower case, no parenthesised Latin, articles, punctuation or "Chapter I."."""
    t = re.sub(r"\(.*?\)|\[.*?\]", " ", title.lower())
    t = re.sub(r"[^a-z0-9 ]+", " ", t)
    t = re.sub(r"\b(the|a|an|of|on|to|and|st|saint)\b", " ", t)
    return " ".join(t.split())


def alt_titles(title: str) -> list:
    """The title, and any title given in parentheses ("Against the Heathen. (Contra Gentes.)")."""
    return [title] + re.findall(r"\(([^()]{4,})\)", title)


def index(v: str, xml: str) -> list:
    """[{vol, level, title, path, frag}] for every div in a volume, at any depth."""
    out = []

    def walk(fragment, level, path):
        for title, frag in thml_divs(fragment, level):
            out.append({"vol": v, "level": level, "title": tidy(title).strip("*"), "path": path, "frag": frag})
            if level < 5:
                walk(frag, level + 1, path + [tidy(title).strip("*")])
    walk(xml, 1, [])
    return out


def chapters_of(entry: dict) -> dict:
    """{chapter key: {paragraph: text}} for a work's div: its child divs as chapters ("1", "2"...), or, where
    those hold divs of their own (books of chapters), "book.chapter"; the work itself as chapter 1 if it
    has no child divs. Introductions, notes and indexes are left out."""
    skip = re.compile(r"(?i)^(introductory note|introduction|translator|elucidation|footnotes|notes|index|"
                      r"prolegomena|preface to the translation)")
    level = entry["level"] + 1
    kids = [(t, f) for t, f in thml_divs(entry["frag"], level) if not skip.search(tidy(t).strip("*"))]
    if not kids:
        paras = thml_flat(entry["frag"])
        return {"1": numbered(paras)} if paras else {}
    out = {}
    for b, (title, frag) in enumerate(kids, 1):
        grand = [(t, f) for t, f in thml_divs(frag, level + 1) if not skip.search(tidy(t).strip("*"))]
        if grand and len(grand) > 1:
            for c, (t2, f2) in enumerate(grand, 1):
                paras = thml_flat(f2)
                if paras:
                    out[f"{b}.{c}"] = numbered(paras)
        else:
            paras = thml_flat(frag)
            if paras:
                out[str(b)] = numbered(paras)
    return out


def numbered(paras: list) -> dict:
    return {str(i): clean(p) for i, p in enumerate((p for p in paras if clean(p)), 1)}


def text_size(chapters: dict) -> int:
    return sum(len(t) for v in chapters.values() for t in (v.values() if isinstance(v, dict) else [v]))


def opening(chapters: dict) -> str:
    """The first words of a work, without any heading in italics."""
    for v in chapters.values():
        for t in (v.values() if isinstance(v, dict) else [v]):
            t = re.sub(r"^\*[^*\n]*\*\n", "", t)
            if len(t) > 40:
                return norm(t)[:200]
    return ""


def paragraphs(chapters: dict) -> list:
    """A work's paragraphs in order, without headings in italics, compared as norm() text."""
    out = []
    for v in chapters.values():
        for t in (v.values() if isinstance(v, dict) else [v]):
            t = norm(re.sub(r"^\*[^*\n]*\*\n", "", t))
            if len(t) > 60:
                out.append(t)
    return out


def coverage(ours: dict, theirs: dict) -> "tuple[bool, float]":
    """(is it the same work, how far into the Schaff text ours reaches): our first paragraph has to be
    found in theirs, and where our last one is found says how much of the work we have."""
    mine, text = paragraphs(ours), " ".join(paragraphs(theirs))
    if not mine or not text:
        return False, 0.0

    def find(p):
        for probe in (p[:90], p[20:90], p[:50]):
            at = text.find(probe)
            if at >= 0:
                return at
        return -1
    start = find(mine[0])
    if start < 0:
        return False, 0.0
    last = next((find(p) for p in reversed(mine[-5:]) if find(p) >= 0), -1)
    return True, (max(last, start) + len(mine[-1])) / len(text)


def author_words(stem: str) -> set:
    return {w for w in stem.split("_") if len(w) > 3 and w not in ("great", "saint", "pope", "bishop")}


_TITLES: dict = {}                  # norm(title) -> [entries], built once for the whole index


def candidates(book: str, stem: str, everything: list) -> list:
    """[(score, entry)] for divs whose title matches `book`, best first: title likeness, plus a little
    for the author's name appearing above it in the volume."""
    if not _TITLES:
        for e in everything:
            for t in alt_titles(e["title"]):
                if norm(t):
                    _TITLES.setdefault(norm(t), []).append(e)
    want = norm(book)
    if not want:
        return []
    words = author_words(stem)
    found = []
    for title in difflib.get_close_matches(want, list(_TITLES), n=12, cutoff=0.72):
        likeness = difflib.SequenceMatcher(None, want, title).ratio()
        for e in _TITLES[title]:
            above = " ".join(e["path"]).lower()
            found.append((likeness + (0.15 if any(w in above for w in words) else 0), e))
    return sorted(found, key=lambda x: -x[0])


def compare() -> None:
    everything = []
    cached_only = "--cached" in sys.argv                 # (only the volumes already downloaded)
    for v in VOLUMES:
        if cached_only and not (ROOT / "scripts" / ".cache" / f"ccel_schaff_{v}.xml").exists():
            continue
        try:
            everything += index(v, volume(v))
        except Exception as e:
            print(f"{v}: not available ({e})")
    print(f"indexed {len(everything):,} sections in the volumes")
    report = []
    for f in sorted(DATA.glob("*.json")):
        books = json.loads(f.read_text(encoding="utf-8")).get("books", {})
        for book, ours in books.items():
            row = {"file": f.name, "book": book, "ours_chapters": len(ours), "ours_chars": text_size(ours)}
            best = None
            for score, e in candidates(book, f.stem, everything)[:8]:
                theirs = chapters_of(e)
                if not text_size(theirs):
                    continue
                same, reach = coverage(ours, theirs)
                key = (same, score)
                if best is None or key > (best["same_work"], best["score"]):
                    best = {"score": round(score, 2), "vol": e["vol"], "title": e["title"], "path": e["path"],
                            "ccel_chapters": len(theirs), "ccel_chars": text_size(theirs),
                            "same_work": same, "reach": round(reach, 2)}
            if best:
                row.update(best)
                row["verdict"] = ("broken" if row["ours_chars"] < 500 and best["score"] >= 0.95 else
                                  "cut short" if best["same_work"] and best["reach"] < 0.75 else
                                  "fine" if best["same_work"] else
                                  "not found")
            else:
                row["verdict"] = "not in Schaff"
            report.append(row)
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    from collections import Counter
    print(Counter(r["verdict"] for r in report))
    for r in report:
        if r["verdict"] in ("broken", "cut short"):
            print(f"{r['verdict']:<9} {r['file']:<26} {r['book'][:46]:<46} ours {r['ours_chars']:>9,} / "
                  f"Schaff {r['ccel_chars']:>9,}  reaches {r['reach']:.0%}  ({r['vol']} {r['title'][:36]!r})")


# ── the repairs ────────────────────────────────────────────────────────────
# What the comparison found broken, checked by hand (the full report is scripts/sources/fathers_report.json):
# the Tractates on John, Origen's On Prayer and the Great Catechism held only scraps (an index line, a
# title, the Catechism's one-page summary); De Principiis stopped after Book II; Cyprian's twelfth
# treatise was missing. John of Damascus's Philosophical Chapters held only an index line too, and
# has no public-domain English translation, so it goes.

ROMAN = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100}


def roman(s: str) -> int:
    total = 0
    for a, b in zip(s, s[1:] + " "):
        total += -ROMAN[a] if ROMAN.get(b, 0) > ROMAN[a] else ROMAN[a]
    return total


def sections_by_title(frag: str, level: int, key_of) -> dict:
    """{key: {paragraph: text}} for the divs at `level`, keyed by key_of(title) (None: skip it); divs
    with the same key (one chapter in two translations, side by side) are run together under it."""
    out = {}
    for title, sub in thml_divs(frag, level):
        key = key_of(tidy(title).strip("*"))
        if key is None:
            continue
        paras = thml_flat(sub)
        if not paras:
            continue
        if not paras[0].startswith("*"):
            paras[0] = f"*{tidy(title).strip('*').rstrip('.')}*\n{paras[0]}"
        verses = out.setdefault(key, {})
        for p in paras:
            if clean(p):
                verses[str(len(verses) + 1)] = clean(p)
    return out


def chapter_number(title: str):
    """"Chapter XIV.", "XVI", "Chapter I. 1–5." -> 14, 16, 1; "Prologue", "Preface..." -> 0."""
    if re.match(r"(?i)(prologue|preface)", title):
        return "0"
    m = re.match(r"(?i)(?:chapter\s+)?([IVXLC]+)\b", title)
    return str(roman(m.group(1).upper())) if m else None


def find(v: str, title: str, under: str = "", level: int = None) -> dict:
    """The div titled `title` (with `under` among the titles above it; at `level`) in volume `v`."""
    found = [e for e in index(v, volume(v)) if e["title"].rstrip(".") == title.rstrip(".")
             and (not under or any(under in p for p in e["path"])) and (level is None or e["level"] == level)]
    if len(found) != 1:
        raise SystemExit(f"{v}: {len(found)} sections titled {title!r} under {under!r}")
    return found[0]


def tractates_on_john() -> dict:
    """124 tractates, numbered in order (their titles name the chapter of John they expound)."""
    e = find("npnf107", "Lectures or Tractates on the Gospel According to St. John.")
    count = iter(range(1, 1000))
    work = sections_by_title(e["frag"], e["level"] + 1,
                             lambda t: None if t.lower().startswith("title page") else str(next(count)))
    if len(work) != 124:
        raise SystemExit(f"Tractates on John: {len(work)} tractates")
    return work


def great_catechism() -> dict:
    e = find("npnf205", "The Great Catechism.")
    work = sections_by_title(e["frag"], e["level"] + 1,
                             lambda t: None if t.lower().startswith("summary") else chapter_number(t))
    if len(work) != 41:                                   # the Prologue and forty chapters
        raise SystemExit(f"Great Catechism: {len(work)} parts")
    return work


def de_principiis_books_3_and_4() -> dict:
    """Books III and IV, as "3.N" and "4.N" (Books I and II are stored already, and stay as they are)."""
    e = find("anf04", "Origen De Principiis.")
    out = {}
    for book_title, frag in thml_divs(e["frag"], e["level"] + 1):
        number = {"Book III": 3, "IV": 4}.get(tidy(book_title).strip("*").rstrip("."))
        if not number:
            continue
        last = {"n": "1"}

        def key(t):
            n = chapter_number(t)
            if n is None and t.lower().startswith("sections"):        # (Book IV: "Sections 24-End ...")
                n = last["n"]
            if n is not None:
                last["n"] = n
                return f"{number}.{n}"
            return None
        out.update(sections_by_title(frag, e["level"] + 2, key))
    if not any(k.startswith("3.") for k in out) or not any(k.startswith("4.") for k in out):
        raise SystemExit(f"De Principiis: {sorted(out)}")
    return out


def testimonies() -> dict:
    """Cyprian's twelfth treatise: the Preface (0) and its three books."""
    e = find("anf05", "Three Books of Testimonies Against the Jews.")
    books = {"Preface": "0", "Book I": "1", "Book II": "2", "Book III": "3"}
    work = sections_by_title(e["frag"], e["level"] + 1, lambda t: books.get(t.rstrip(".")))
    if sorted(work) != ["0", "1", "2", "3"]:
        raise SystemExit(f"Testimonies: {sorted(work)}")
    return work


def origen_on_prayer() -> dict:
    """Not in Schaff: William A. Curtis's translation, from CCEL's own edition."""
    xml = ccel("origen/prayer")
    work = sections_by_title(xml, 1, lambda t: None if t.lower().startswith("title") else chapter_number(t))
    if len(work) != 20:                                   # (Curtis divides it into twenty)
        raise SystemExit(f"On Prayer: {len(work)} chapters")
    return work


# ── abridged works, made whole ──────────────────────────────────────────────
# Comparing 8-word phrases with Schaff found works kept only in part: whole chapters or homilies
# missing, or each chapter cut to its first lines (On the Making of Man held 26,000 characters of
# 206,000; the Harmony of the Gospels 32,000 of 809,000). The coverage check above missed them, since
# their first and last paragraphs were there. They are rebuilt whole, in Schaff's divisions.

_FRONT = re.compile(r"(?i)^(title page|introduct(ion|ory note|ory notice)\.?$|preface to the (benedictine|translation)|"
                    r"translator|elucidation|notes?\b|index|prolegomena|analysis|summary|synopsis|list of)")
_ZERO = re.compile(r"(?i)^(prologue|preface|dedication|prefatory|gregory, bishop of nyssa, to his brother)")


def whole(vol: str, title: str, under: str = "", level: int = None) -> dict:
    """A work as Schaff divides it: its divisions as chapters, numbered as printed ("Homily XIV.") where
    every one is, otherwise in order; a prologue or dedication is chapter 0; books of chapters "b.c"."""
    e = find(vol, title, under, level)
    level = e["level"] + 1
    kids = [(tidy(t).strip("*"), f) for t, f in thml_divs(e["frag"], level)
            if not _FRONT.search(tidy(t).strip("*")) and thml_flat(f)]          # (Nisibene "Hymns XXII-XXXIV": lost)
    if not kids:
        return {"1": numbered(thml_flat(e["frag"]))}

    zero = kids[0][0] if _ZERO.search(kids[0][0]) and not all(_ZERO.search(t) for t, _ in kids) else None
    size = {id(f): sum(len(p) for p in thml_flat(f)) for _, f in kids}
    kids = [(t, f) for t, f in kids if size[id(f)] >= 200 or len(kids) < 3]    # (a stray heading: "Hymn XIII.")

    def number(t):
        m = re.match(r"(?i)^(?:chapter|homily|book|letter|tractate|sermon|lecture|part|instruction|epistle|hymn)\s+"
                     r"([IVXLC]+)\b", t) or re.match(r"^([IVXLC]+)\.?(?:\s|$)", t)
        return roman(m.group(1).upper()) if m else None
    numbers = [number(t) for t, _ in kids if t != zero]
    printed = all(numbers) and len(set(numbers)) == len(numbers)
    words = {"first": 1, "second": 2, "third": 3, "fourth": 4, "fifth": 5}
    if not printed:                                       # ("First Instruction.", "Second Instruction.")
        numbers = [words.get(t.split()[0].lower()) for t, _ in kids if t != zero]
        printed = all(numbers) and len(set(numbers)) == len(numbers)
    out, n = {}, 0
    for t, f in kids:
        if t == zero:
            key = "0"
        else:
            n += 1
            key = str(numbers[n - 1] if printed else n)
        grand = [(tidy(g).strip("*"), gf) for g, gf in thml_divs(f, level + 1) if not _FRONT.search(tidy(g).strip("*"))]
        if len(grand) > 1:
            for c, (g, gf) in enumerate(grand, 1):
                paras = _flat(gf, e["title"])
                if paras:
                    out[f"{key}.{c}"] = _with_title(numbered(paras), g)
        else:
            paras = _flat(f, e["title"])
            if paras:
                out[key] = _with_title(numbered(paras), t)
    return out


def _flat(frag: str, title: str = "") -> list:
    """thml_flat, without the bare numerals ANF prints over a treatise ("VII."), the work's title over its
    first chapter, or the translator's credit."""
    out = []
    for p in thml_flat(frag):
        body = re.sub(r"^\*[^*\n]*\*\n", "", p)
        if (re.fullmatch(r"[IVXLC]+\.?|[—–_\-\s]+", body) or (title and norm(body) == norm(title))
                or body.startswith("[Translated by")):
            continue
        out.append(p)
    return out


def _with_title(verses: dict, title: str) -> dict:
    if verses and not verses["1"].startswith("*"):
        verses["1"] = f"*{title.rstrip('.')}*\n{verses['1']}"
    return verses


# ── the councils (NPNF2-14) ─────────────────────────────────────────────────
# Percival's volume prints each canon followed by Notes: an "Ancient Epitome" and pages of commentary
# (Hefele, Balsamon, Van Espen...), with excursuses between the canons. Only the councils' own words are
# kept: the creeds, definitions, letters and extracts from the acts, and each canon's text up to its notes.

_NOT_THE_COUNCIL = re.compile(r"(?i)^(title page|historical|introductory note|introduction on|note on|excursus|"
                              r"general introduction|elucidation)")
_STOP = re.compile(r"(?i)^(notes?|note [ivx]+)\.?$|^ancient epitome|^for ancient epitome|^this canon is (found|in)\b|"
                   r"^hefele’s epitome|^johnson thus condenses")
_COMMENT = re.compile(r"^The reader should know")       # (the editor, before the creed of Constantinople)
_CITATION = re.compile(r"(?s)^\(.*\)\.?$|^a\.d\. [\d–-]+\.?$")             # sources, in parentheses
# the editor's [*summaries of what the extracts leave out*], in italics (a canon in [plain brackets] is
# one that some manuscripts lack, and stays)
_EDITOR = re.compile(r"(?s)^(\*\[|\[\*).*\][*.:]*$|^\[(?=.*\b(Hefele|Johnson|Bright|Beveridge|Labbe|Mansi)\b).*\]\.?$")


def _strip_commentary_divs(frag: str) -> str:
    for level in range(3, 6):
        frag = re.sub(rf'(?is)<div{level}\b[^>]*title="([^"]*)"[^>]*>.*?</div{level}>',
                      lambda m: "" if _NOT_THE_COUNCIL.search(tidy(html.unescape(m.group(1))).strip("*")) else m.group(0),
                      frag)
    return frag


def council_paragraphs(frag: str) -> list:
    """[(canon number or None, text)] for a council's document: a canon heading ("Canon XII.") gives the
    number of the paragraphs after it; the notes after each canon, and headings and citations, are left out."""
    from build_reformation import text_of
    frag = _strip_commentary_divs(re.sub(r"(?is)<note\b.*?</note>", "", frag))
    out, canon, stopped = [], None, False
    for m in re.finditer(r"(?is)<p\b([^>]*)>(.*?)</p>", frag):
        cls = (re.search(r'class="([^"]+)"', m.group(1)) or [None, ""])[1]
        text = tidy(text_of(m.group(2))).strip()
        bare = text.strip("*").strip()
        if not bare:
            continue
        heading = re.fullmatch(r"(?:Canon|Question)\s+([IVXLC]+)\.?(?:\s+and\s+[IVXLC]+\.?)?\s*(\([^)]*\))?\.?", bare)
        if cls == "c34" or heading:                       # "Canon I.", "Canon III. (III. and IV.)", "Question I."
            if heading and "latin text" in (heading.group(2) or "").lower():
                canon, stopped = (canon or 0) + 1, False    # (Sardica: "Canon XII. (Of the Latin Texts)", after XX)
            elif heading:
                canon, stopped = roman(heading.group(1)), False
            continue
        if stopped:
            continue
        if _STOP.search(bare):
            stopped = True
            continue
        if re.fullmatch(r"\(?\*?(Greek|Latin)\*?\.?\)?\.?", bare):          # Sardica's two versions
            out.append((canon, f"*({bare.strip('()*.')})*"))
            continue
        if _COMMENT.search(bare) or _CITATION.search(bare) or _EDITOR.search(text):
            continue
        if cls in ("c35", "c50"):                         # a canon's caption (Carthage), a creed's title
            out.append((canon, f"*{bare}*"))
            continue
        if cls in ("c14", "c10", "c12", "c28", "c5", "c2", "c51", "c30", "c31", "c36", "c40", ""):
            continue                                      # (titles, "Session I.", commentators' names)
        out.append((canon, text))
    # a version label ("(Greek)") or a caption leads the paragraph after it
    merged = []
    for canon, text in out:
        last = merged[-1][1] if merged else ""
        if merged and merged[-1][0] == canon and re.fullmatch(r"\*[^*\n]+\*", last):
            merged[-1] = (canon, f"{merged[-1][1]}\n{text}")
        else:
            merged.append((canon, text))
    return merged


def canons(frag: str, expect: int, joined=()) -> dict:
    """{canon number: {paragraph: text}}; any preamble before the first canon is chapter 0. `joined`: numbers
    printed together with the one before ("Canon XII. and XIII")."""
    out = {}
    for canon, text in council_paragraphs(frag):
        verses = out.setdefault(str(canon or 0), {})
        verses[str(len(verses) + 1)] = clean(text)
    numbers = sorted([int(k) for k in out if k != "0"] + list(joined))
    if numbers != list(range(1, expect + 1)):
        missing = sorted(set(range(1, expect + 1)) - set(numbers))
        raise SystemExit(f"canons: expected 1-{expect}, missing {missing}, extra {[n for n in numbers if n > expect]}")
    return out


def documents(parts: list) -> dict:
    """{1: first document, 2: ...}: each document's paragraphs, its title leading the first."""
    out = {}
    for title, frag in parts:
        paras = [t for _, t in council_paragraphs(frag)]
        if not paras:
            raise SystemExit(f"nothing kept of {title!r}")
        title = re.sub(r"\.$", "", tidy(title).strip("*"))
        paras[0] = f"*{title}*\n{paras[0]}"
        out[str(len(out) + 1)] = {str(i): clean(p) for i, p in enumerate(paras, 1)}
    return out


def councils() -> dict:
    xml = volume("npnf214")
    top = {tidy(t).strip("*"): f for t, f in thml_divs(xml, 1)}

    def council(prefix):
        f = next(f for t, f in top.items() if t.startswith(prefix))
        return [(tidy(t).strip("*"), f2) for t, f2 in thml_divs(f, 2)]

    def pick(parts, *wanted, exclude=None):
        got = [(t, f) for t, f in parts if any(t.startswith(w) for w in wanted) and not (exclude and exclude.search(t))]
        return got

    def the(parts, start):
        found = [f for t, f in parts if t.startswith(start)]
        if len(found) != 1:
            raise SystemExit(f"{len(found)} parts starting {start!r}")
        return found[0]

    books = {}
    nicaea = council("The First Ecumenical Council")
    books["Council of Nicaea"] = documents(pick(nicaea, "The Nicene Creed", "The Synodal Letter", "On the Keeping of Easter"))
    books["Canons of Nicaea"] = canons(the(nicaea, "The Canons of the 318"), 20)

    local = council("The Canons of the Councils of Ancyra")
    for name, start, n in (("Canons of Ancyra", "The Council of Ancyra", 25),
                           ("Canons of Neocaesarea", "The Council of Neoc", 15),
                           ("Canons of Gangra", "The Council of Grangra", 20),
                           ("Canons of Antioch", "The Synod of Antioch", 25),
                           ("Canons of Laodicea", "Synod of Laodicea", 60)):
        books[name] = canons(the(local, start), n)

    con1 = council("The Second Ecumenical Council")
    books["First Council of Constantinople"] = documents(pick(con1, "The Holy Creed", "Letter of the Same", "The Synodical Letter"))
    books["Canons of Constantinople"] = canons(the(con1, "Canons of the One Hundred and Fifty"), 7)

    eph = council("The Third Ecumenical Council")
    docs = [(t, f) for t, f in eph if not _NOT_THE_COUNCIL.search(t) and not t.startswith("The Canons")]
    books["Council of Ephesus"] = documents(docs)
    books["Canons of Ephesus"] = canons(the(eph, "The Canons of the Two Hundred"), 8)

    chal = council("The Fourth Ecumenical Council")
    docs = [(t, f) for t, f in chal if not _NOT_THE_COUNCIL.search(t) and not t.startswith("The XXX Canons")]
    books["Council of Chalcedon"] = documents(docs)
    books["Canons of Chalcedon"] = canons(the(chal, "The XXX Canons"), 30)

    con2 = council("The Fifth Ecumenical Council")
    docs = [(t, f) for t, f in con2 if not _NOT_THE_COUNCIL.search(t) and not t.startswith("The Decretal Epistle of Pope Vigilius in")]
    books["Second Council of Constantinople"] = documents(docs)

    con3 = council("The Sixth Ecumenical Council")
    docs = [(t, f) for t, f in con3 if not _NOT_THE_COUNCIL.search(t) and not t.startswith("The Letter of Agatho, Pope of Old Rome")]
    books["Third Council of Constantinople"] = documents(docs)

    books["Canons of the Council in Trullo"] = canons(the(council("The Canons of the Council in Trullo"), "The Canons of the Council in Trullo"), 102)

    west = council("The Canons of the Synods of Sardica")
    books["Canons of Sardica"] = canons(the(west, "The Council of Sardica"), 21)
    books["Canons of Carthage"] = canons(the(west, "The Canons of the CCXVII"), 138)
    books["Council of Constantinople under Nectarius"] = documents(pick(west, "Council of Constantinople held under Nectarius"))

    nic2 = council("The Seventh Ecumenical Council")
    docs = [(t, f) for t, f in nic2 if not _NOT_THE_COUNCIL.search(t) and not t.startswith(("The Canons of the Holy", "Introduction"))
            and not t.startswith("Examination of the Caroline")]
    books["Second Council of Nicaea"] = documents(docs)
    books["Canons of the Second Council of Nicaea"] = canons(the(nic2, "The Canons of the Holy and Ecumenical Seventh"), 22)

    books["Apostolic Canons"] = canons(the(council("Appendix containing Canons"), "The Canons of the Holy and Altogether August"), 85, joined=(13,))
    return books


# ── numbered chapters inside running text (ANF7) ───────────────────────────
# The Apostolic Constitutions and the liturgies number their chapters in the text ("XII. Let the
# bishop..."), not with divisions of their own.

_LABEL = re.compile(r"^(The (People|Deacon|Priest|Singers|Clergy|Bishop|Archdeacon)\b.{0,40}|\([^)]{1,30}\)|"
                    r"Prayer\b.{0,60}\.|.{1,30}:—|Then,|Another\.|Canon\.|On [A-Za-z ,-]{3,40}\.)$")


def tidy_heading(p: str, drop=()) -> str:
    """A paragraph's heading in italics without the titles above it (`drop`) or the same title twice
    ("Sec. I.—General Commandments · Sec. I.—General Commandments.")."""
    m = re.match(r"^\*([^*\n]*)\*\n", p)
    if not m:
        return p
    parts = []
    for part in m.group(1).split(" · "):
        key = norm(part)
        if part.strip() and key not in {norm(d) for d in drop} and key not in {norm(x) for x in parts}:
            parts.append(part.strip().rstrip("."))
    return (f"*{' · '.join(parts)}*\n" if parts else "") + p[m.end():]


def numbered_chapters(paras: list, prefix: str = "", labels: bool = False, drop=(), arabic: bool = False) -> dict:
    """{prefix + n: {paragraph: text}}, a new chapter at each paragraph opening with the next Roman
    numeral (one out of sequence is taken as a misprint when the one after it carries on from it, and a
    skipped number as a chapter run into the one before); what comes before the first is chapter 0.
    labels: a speaker or rubric ("The Deacon.", "(Aloud.)") leads the line after it, in italics."""
    heads = []
    for i, p in enumerate(paras):
        m = re.match(r"^(?:\*[^*\n]*\*\n)?(\d+)\.\s+(?=\S)" if arabic else
                     r"^(?:\*[^*\n]*\*\n)?([IVXLC]+)(?:\.\s*|\s+)(?=\S)", p)    # ("XII. Let...", "XLVII.1. Let...")
        if m:
            heads.append((i, int(m.group(1)) if arabic else roman(m.group(1)), m))
        elif p.startswith("*"):                           # a chapter's title, its number left out
            heads.append((i, None, re.match(r"^\*[^*\n]*\*\n()()", p)))
    heads = [(i, v, m) for i, v, m in heads if m]
    starts, prev = {}, 0
    for k, (i, v, m) in enumerate(heads):
        nxt = next((h[1] for h in heads[k + 1:] if h[1] is not None), None)
        if v is None:
            if nxt == prev + 2:
                prev += 1
                starts[i] = (prev, m)
            continue
        if v == prev + 1 or (v != prev and nxt == prev + 2):
            prev = prev + 1                               # (a misprinted number)
        elif v > prev + 1 and nxt == v + 1:
            prev = v                                      # (a chapter run into the one before)
        else:
            continue
        starts[i] = (prev, m)
    out, chapter = {}, 0
    pending = ""
    for i, p in enumerate(paras):
        if i in starts:
            chapter, m = starts[i]
            p = p[:m.start(1)] + p[m.end():]
        p = tidy_heading(p, drop)
        if labels and _LABEL.match(p.strip()) and len(p) < 80:
            pending = f"{pending} {p.strip()}".strip()
            continue
        if pending:
            p, pending = f"*{pending}*\n{p}", ""
        verses = out.setdefault(f"{prefix}{chapter}", {})
        if clean(p):
            verses[str(len(verses) + 1)] = clean(p)
    return {k: v for k, v in out.items() if v}


def constitutions() -> dict:
    """The eight books, as "book.chapter"; each book's opening before its first chapter is "book.0"."""
    e = find("anf07", "Constitutions of the Holy Apostles")
    out = {}
    for b, (title, frag) in enumerate([d for d in thml_divs(e["frag"], 2) if d[0].startswith("Book")], 1):
        frag = re.sub(r'(?is)<div3\b[^>]*title="Elucidation[^"]*"[^>]*>.*?</div3>', "", frag)
        out.update(numbered_chapters(thml_flat(frag), f"{b}.", drop=("Constitutions of the Holy Apostles", tidy(title),
                                                                        *tidy(title).split(". ", 1))))
    if sorted({k.split(".")[0] for k in out}) != [str(n) for n in range(1, 9)]:
        raise SystemExit(f"Constitutions: books {sorted({k.split('.')[0] for k in out})}")
    return out


def liturgies() -> dict:
    e = find("anf07", "Early Liturgies")
    names = {"The Divine Liturgy of James": "Liturgy of St. James", "The Divine Liturgy of the Holy Apostle and Evangelist Mark":
             "Liturgy of St. Mark", "The Liturgy of the Blessed Apostles": "Liturgy of Addai and Mari"}
    out = {}
    for title, frag in thml_divs(e["frag"], 2):
        name = next((n for t, n in names.items() if tidy(title).startswith(t)), None)
        if name:
            out[name] = numbered_chapters(thml_flat(frag), labels=True, drop=("Early Liturgies", tidy(title)))
    if len(out) != 3:
        raise SystemExit(f"Liturgies: {sorted(out)}")
    return out


# ── smaller works: ANF6's minor writers, ANF8's Syriac documents and fragments, ANF9's apocrypha ──
# These volumes print the editor's introduction to each piece in the same division as the text ("[a.d.
# 180.] This Rhodon was supposed..."), and running heads and rules between them; the paragraph classes
# tell them apart.

_HEADS = {"anf06": {"c27", "c28", "c30", "c41", "c25"}, "anf08": {"c34", "c35", "c42", "c15", "c58", "c51", "c63", "c54"},
          "anf09": set()}
_RUNNING = {"c2", "c11", "c14", "c16", "c19", "c20", "c24", "c33", "c44", "c56", "Centered"}
_EDITOR_DIVS = re.compile(r"(?i)^(introduct|translator|elucidation|note\b|syriac calendar|synoptical table)")


def piece(vol: str, frag: str) -> list:
    """A piece's paragraphs: its headings leading the paragraph after them in italics; the editor's
    introduction, running heads and rules left out."""
    from build_reformation import text_of
    frag = re.sub(r"(?is)<note\b.*?</note>", "", frag)
    for level in range(3, 6):
        frag = re.sub(rf'(?is)<div{level}\b[^>]*title="([^"]*)"[^>]*>.*?</div{level}>',
                      lambda m: "" if _EDITOR_DIVS.search(html.unescape(m.group(1))) else m.group(0), frag)
    out, pending, intro = [], [], False
    for m in re.finditer(r"(?is)<p\b([^>]*)>(.*?)</p>|<verse\b[^>]*>(.*?)</verse>", frag):
        if m.group(3) is not None:
            text = "\n".join(text_of(l) for l in re.findall(r"(?is)<l\b[^>]*>(.*?)</l>", m.group(3)))
            cls = "verse"
        else:
            cls = (re.search(r'class="([^"]+)"', m.group(1)) or [None, "-"])[1]
            text = tidy(text_of(m.group(2))).strip()
        bare = text.strip("*").strip()
        if not bare or re.fullmatch(r"[—–_\-•·.\s]+", bare) or cls in _RUNNING or re.match(r"\[Translated by", bare):
            continue
        if bare.startswith("[a.d."):                      # the editor's introduction, to the next heading
            intro = True
            continue
        heading = cls in _HEADS.get(vol, ()) and len(bare) < 200 and not re.match(r"\*?Here\*? end", bare)
        if intro and (heading or cls == "c21"):
            intro = False
        if intro:
            continue
        if heading:
            pending.append(bare.rstrip("."))
            continue
        if pending:
            text, pending = f"*{' · '.join(pending)}*\n{text}", []
        out.append(text)
    return out


def _work(vol: str, title: str, under: str = "", chapters: bool = False, numbered: bool = False, drop=(),
          arabic: bool = False) -> dict:
    """A work in one division of a volume: its child divisions as chapters (chapters=True), chapters
    numbered in its text (numbered=True), or else all of it as chapter 1."""
    e = find(vol, title, under)
    if chapters:
        kids = [(t, f) for t, f in thml_divs(e["frag"], e["level"] + 1) if not _EDITOR_DIVS.search(tidy(t))]
        out = {}
        for n, (t, f) in enumerate(kids, 1):
            paras = [tidy_heading(p, (title, *drop)) for p in piece(vol, f)]
            if paras:
                out[str(n)] = {str(i): clean(p) for i, p in enumerate(paras, 1) if clean(p)}
        return out
    paras = piece(vol, e["frag"])
    if numbered:
        return numbered_chapters(paras, drop=(title, *drop), arabic=arabic)
    paras = [p for p in (tidy_heading(p, (title, *drop)) for p in paras) if norm(p) not in {norm(title), *map(norm, drop)}]
    return {"1": {str(i): clean(p) for i, p in enumerate(paras, 1) if clean(p)}}


def syriac_documents() -> dict:
    edessa = "Memoirs of Edessa"
    return {
        "The Story Concerning the King of Edessa": _work("anf08", "The Story Concerning the King of Edessa.", edessa),
        "Extracts Concerning Abgar the King and Addaeus the Apostle":
            _work("anf08", "Extracts from Various Books Concerning Abgar the King and Addæus the Apostle.", edessa, chapters=True),
        "The Teaching of Addaeus the Apostle": _work("anf08", "The Teaching of Addæus the Apostle.", "The Teaching of Addæus"),
        "The Teaching of the Apostles": _work("anf08", "The Teaching of the Apostles.", edessa),
        "The Teaching of Simon Cephas in the City of Rome": _work("anf08", "The Teaching of Simon Cephas in the City of Rome.", edessa),
        "Acts of Sharbil": _work("anf08", "Acts of Sharbil.", edessa),
        "Martyrdom of Barsamya": _work("anf08", "Further, the Martyrdom of Barsamya, the Bishop of the Blessed City Edessa.", edessa),
        "Martyrdom of Habib the Deacon": _work("anf08", "Martyrdom of Habib the Deacon.", edessa),
        "Martyrdom of Shamuna, Guria and Habib":
            _work("anf08", "Martyrdom of the Holy Confessors Shamuna, Guria, and Habib, from Simeon Metaphrastes.", edessa),
        "Letter of Mara, Son of Serapion": _work("anf08", "A Letter of Mara, Son of Serapion.", edessa),
        "Memorial of Ambrose, a Chief Man of Greece": _work("anf08", "Ambrose.", edessa),
    }


def remains() -> dict:
    r = "Remains of the Second and Third Centuries"
    out = {}
    for name, title in (("Quadratus", "Quadratus, Bishop of Athens."), ("Aristo of Pella", "Aristo of Pella."),
                        ("Dionysius of Corinth", "Dionysius, Bishop of Corinth."), ("Rhodon", "Rhodon."),
                        ("Maximus of Jerusalem", "Maximus, Bishop of Jerusalem."),
                        ("Claudius Apollinaris", "Claudius Apollinaris, Bishop of Hierapolis, and Apologist."),
                        ("Polycrates", "Polycrates, Bishop of Ephesus."), ("Theophilus of Caesarea", "Theophilus, Bishop of Cæsarea in Palestine."),
                        ("Serapion of Antioch", "Serapion, Bishop of Antioch."), ("Apollonius", "Apollonius."),
                        ("Pantaenus", "Pantænus, the Alexandrian Philosopher.")):
        out[f"Fragments of {name}"] = _work("anf08", title, r, drop=(title,))
    out["Fragments of Melito"] = _work("anf08", "Melito, the Philosopher.", r, chapters=True)
    out["Fragments of Hegesippus"] = _work("anf08", "Hegesippus.", r, drop=("Hegesippus",))
    return out


def minor_writers() -> dict:
    m = "Anatolius and Minor Writers"
    return {
        "The Paschal Canon of Anatolius": _work("anf06", "The Paschal Canon of Anatolius of Alexandria.", m, chapters=True),
        "Fragments of Anatolius on Arithmetic": _work("anf06", "Fragments of the Books on Arithmetic.", m),
        "Fragments of Alexander of Cappadocia": _work("anf06", "From the Epistles of Alexander.", m),
        "Fragments of Theognostus": _work("anf06", "From His Seven Books of Hypotyposes or Outlines.", m),
        "Fragments of Pierius": _work("anf06", "Pierus of Alexandria.", m, chapters=True),
        "Epistle of Theonas to Lucianus": _work("anf06", "The Epistle of Theonas, Bishop of Alexandria, to Lucianus, the Chief Chamberlain.", m, chapters=True),
        "Fragments of Phileas": _work("anf06", "Phileas.", m, chapters=True),
    }


def anf9_apocrypha() -> dict:
    return {
        "The Gospel of Peter": _gospel_of_peter(),
        # (named apart from the Gnostic Apocalypse of Peter from Nag Hammadi, a different work)
        "The Greek Apocalypse of Peter": _work("anf09", "The Apocalypse of Peter.", "The Apocalypse of Peter"),
        "Fragments of the Apocalypse of Peter": _work("anf09", "Fragments of the Apocalypse of Peter."),
        "The Vision of Paul": _work("anf09", "The Vision of Paul.", "The Vision of Paul", numbered=True, arabic=True),
        "The Apocalypse of the Virgin": _work("anf09", "The Apocalypse of the Holy Mother of God Concerning the Chastisements.", numbered=True),
        "The Testament of Abraham: First Version": _work("anf09", "Version I", numbered=True, drop=("The Testament of Abraham", "Version I")),
        "The Testament of Abraham: Second Version": _work("anf09", "Version II", numbered=True, drop=("Version II",)),
        "The Acts of Xanthippe and Polyxena": _work("anf09", "Life and Conduct of the Holy Women, Xanthippe, Polyxena, and Rebecca.", numbered=True),
        "The Narrative of Zosimus": _work("anf09", "The Narrative of Zosimus Concerning the Life of the Blessed.", numbered=True),
    }


def _gospel_of_peter() -> dict:
    """Robinson's fourteen sections ("1 But of the Jews none washed his hands..."), as verses of one chapter."""
    paras = piece("anf09", find("anf09", "The Gospel According to Peter.")["frag"])
    verses = {}
    for p in paras:
        m = re.match(r"^(\d+)\s+(.*)", p, re.S)
        if m:
            verses[m.group(1)] = clean(m.group(2))
    if sorted(map(int, verses)) != list(range(1, 15)):
        raise SystemExit(f"Gospel of Peter: sections {sorted(map(int, verses))}")
    return {"1": verses}


def update(filename: str, replace: dict = None, extend: dict = None, remove=(), sources: dict = None) -> None:
    path = DATA / filename
    payload = json.loads(path.read_text(encoding="utf-8"))
    for name in remove:
        payload["books"].pop(name, None)
    for name, chapters in (replace or {}).items():
        payload["books"][name] = chapters
    for name, chapters in (extend or {}).items():
        payload["books"][name].update({k: v for k, v in chapters.items() if k not in payload["books"][name]})
    if sources:
        payload.setdefault("book_sources", {}).update(sources)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    for name in list(replace or {}) + list(extend or {}):
        chapters = payload["books"][name]
        print(f"{filename}: {name}: {len(chapters)} chapters, {sum(len(v) for v in chapters.values())} passages")
    for name in remove:
        print(f"{filename}: {name}: removed")


def create(path: Path, source: str, books: dict, sources: dict = None) -> None:
    """A new data file of works not in the library before."""
    books = {b: {c: {v: t for v, t in vs.items() if t} for c, vs in chs.items()} for b, chs in books.items()}
    books = {b: {c: vs for c, vs in chs.items() if vs} for b, chs in books.items()}
    empty = [b for b, chs in books.items() if not chs]
    if empty:
        raise SystemExit(f"{path.name}: nothing in {empty}")
    payload = {"source": source, **({"book_sources": sources} if sources else {}), "books": books}
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    n = sum(len(v) for chs in books.values() for v in chs.values())
    print(f"{path.relative_to(ROOT)}: {len(books)} works, {n} passages, {path.stat().st_size // 1000:,} kB")


# The works found kept only in part (see "abridged works" above): (file, book, volume, Schaff's title, level).
WHOLE = [
    ("augustine.json", "The Harmony of the Gospels", "npnf106", "The Harmony of the Gospels.", 1),
    ("augustine.json", "Acts or Disputation Against Fortunatus the Manichaean", "npnf104",
     "Acts or Disputation Against Fortunatus the Manichæan.", None),
    ("chrysostom.json", "Commentary on Galatians", "npnf113", "Commentary on Galatians.", None),
    ("chrysostom.json", "Two Letters to Theodore After His Fall", "npnf109", "An Exhortation to Theodore After His Fall.", None),
    ("chrysostom.json", "Correspondence with Pope Innocent I", "npnf109", "Correspondence of St. Chrysostom with the Bishop of Rome.", None),
    ("chrysostom.json", "Homilies on the Statues", "npnf109", "The Homilies on the Statues to the People of Antioch.", None),
    ("chrysostom.json", "Instructions to Catechumens", "npnf109", "Instructions to Catechumens.", None),
    ("chrysostom.json", "Three Homilies on the Power of Satan", "npnf109", "Three Homilies Concerning the Power of Demons.", None),
    ("gregory_of_nyssa.json", "On the Making of Man", "npnf205", "On the Making of Man.", 3),
    ("jerome.json", "Prefaces", "npnf206", "Prefaces.", None),
    ("clement_of_alexandria.json", "Exhortation to the Heathen", "anf02", "Exhortation to the Heathen", None),
    ("clement_of_rome.json", "Two Epistles Concerning Virginity", "anf08", "Two Epistles Concerning Virginity.", None),
    ("alexander_of_alexandria.json", "Epistles on the Arian Heresy and the Deposition of Arius", "anf06",
     "Epistles on the Arian Heresy and the Deposition of Arius.", None),
    ("dionysius_of_rome.json", "Against the Sabellians", "anf07", "Against the Sabellians", None),
    ("dionysius_the_great.json", "Exegetical Fragments", "anf06", "Exegetical Fragments.", None),
    ("methodius.json", "Three Fragments from the Homily on the Cross", "anf06",
     "Three Fragments from the Homily on the Cross and Passion of Christ.", None),
    ("archelaus.json", "Acts of the Disputation with the Heresiarch Manes", "anf06", "The Acts of the Disputation with the Heresiarch Manes.", None),
    ("ephrem_the_syrian.json", "Nisibene Hymns", "npnf213", "Ephraim Syrus: The Nisibene Hymns.", None),
    ("ephrem_the_syrian.json", 'On the Faith ("The Pearl")', "npnf213", "Ephraim Syrus: The Pearl. Seven Hymns on the Faith.", None),
    # and works stored under another work's title (the old scripts fetched the wrong NewAdvent pages): "On Modesty"
    # held the Passion of Perpetua, "Scorpiace" Against All Heresies, "On Prayer" To the Martyrs, Jerome's "Lives of
    # Illustrious Men" Against Vigilantius and "On Perpetual Virginity" the Life of Paul; Athanasius's "On the Decrees
    # of Nicaea" Eusebius's letter, "On the Councils" the Historia Acephala, "Ad Afros" the Statement of Faith,
    # "Apologia Contra Arianos" De Sententia Dionysii and "Historia Arianorum" De Synodis. Each of those is in the
    # library under its own title already; these get the works their titles name.
    ("tertullian.json", "On Modesty", "anf04", "On Modesty.", 2),
    ("tertullian.json", "Scorpiace", "anf03", "Scorpiace.", 2),
    ("tertullian.json", "On Prayer", "anf03", "On Prayer.", 2),
    ("jerome.json", "Lives of Illustrious Men", "npnf203", "Jerome. Lives of Illustrious Men.", 2),
    ("jerome.json", "On Perpetual Virginity of Mary", "npnf206", "The Perpetual Virginity of Blessed Mary.", 2),
    ("athanasius.json", "On the Decrees of Nicaea", "npnf204", "De Decretis. (Defence of the Nicene Definition.)", 2),
    ("athanasius.json", "On the Councils", "npnf204", "On the Councils of Ariminum and Seleucia. (De Synodis.)", 2),
    ("athanasius.json", "Ad Afros", "npnf204", "Synodal Letter to the Bishops of Africa. (Ad Afros Epistola Synodica.)", 2),
    ("athanasius.json", "Apologia Contra Arianos", "npnf204", "Apologia Contra Arianos. (Defence Against the Arians.)", 2),
    ("athanasius.json", "Historia Arianorum", "npnf204", "Arian History. (Historia Arianorum ad Monachos.)", 2),
]


def additions() -> None:
    """The works added from Schaff in October 2026: the councils, ANF7's Constitutions and liturgies,
    ANF8's Syriac documents and fragments, ANF6's minor writers, ANF9's apocrypha, Ephrem's hymns, the
    treatises once credited to Cyprian, and the abridged works made whole."""
    create(DATA / "church_councils.json", "Nicene and Post-Nicene Fathers, Series II, Vol. 14: The Seven Ecumenical Councils, "
           "ed. Henry R. Percival (1900); the councils' own texts, without the commentary", councils())
    create(DATA / "apostolic_constitutions.json", "Ante-Nicene Fathers, Vol. 7, trans. James Donaldson (1886)",
           {"Apostolic Constitutions": constitutions()})
    create(DATA / "early_liturgies.json", "Ante-Nicene Fathers, Vol. 7 (1886)", liturgies())
    create(DATA / "ancient_syriac_documents.json", "Ante-Nicene Fathers, Vol. 8, trans. B. P. Pratten (1886)", syriac_documents())
    create(DATA / "remains_of_the_second_and_third_centuries.json", "Ante-Nicene Fathers, Vol. 8, trans. B. P. Pratten (1886)",
           remains())
    create(DATA / "anatolius_and_minor_writers.json", "Ante-Nicene Fathers, Vol. 6, trans. S. D. F. Salmond (1886)",
           minor_writers())
    create(ROOT / "data" / "nt_apocrypha" / "anf9_apocrypha.json", "Ante-Nicene Fathers, Vol. 9, ed. Allan Menzies (1896)",
           anf9_apocrypha())
    update("ephrem_the_syrian.json", replace={
        "Hymns on the Nativity": whole("npnf213", "Ephraim Syrus: Nineteen Hymns on the Nativity of Christ in the Flesh."),
        "Hymns for the Feast of the Epiphany": whole("npnf213", "Ephraim Syrus: Fifteen Hymns For the Feast of the Epiphany."),
        "Homily on Our Lord": whole("npnf213", "On Our Lord."),
        "Homily on Admonition and Repentance": whole("npnf213", "On Admonition and Repentance."),
    })
    update("cyprian_of_carthage.json", replace={
        "Treatises Attributed to Cyprian": whole("anf05", "Treatises Attributed to Cyprian on Questionable Authority.")})
    by_file = {}
    for filename, book, vol, title, level in WHOLE:
        by_file.setdefault(filename, {})[book] = whole(vol, title, level=level)
    for filename, books in by_file.items():
        update(filename, replace=books)


def write() -> None:
    update("augustine.json", replace={"Tractates on the Gospel of John": tractates_on_john()})
    update("gregory_of_nyssa.json", replace={"The Great Catechism": great_catechism()})
    update("origen.json", replace={"On Prayer": origen_on_prayer()}, extend={"De Principiis": de_principiis_books_3_and_4()},
           sources={"On Prayer": "Origen, On Prayer, trans. William A. Curtis, from CCEL"})
    update("cyprian_of_carthage.json", replace={"Three Books of Testimonies Against the Jews": testimonies()})
    update("john_of_damascus.json", remove=("Philosophical Chapters",))
    additions()


if __name__ == "__main__":
    {"download": download, "compare": compare, "write": write}[sys.argv[1] if len(sys.argv) > 1 else "download"]()
