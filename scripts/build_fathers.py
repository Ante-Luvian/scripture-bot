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


def find(v: str, title: str, under: str = "") -> dict:
    """The div titled `title` (with `under` among the titles above it) in volume `v`."""
    found = [e for e in index(v, volume(v)) if e["title"].rstrip(".") == title.rstrip(".")
             and (not under or any(under in p for p in e["path"]))]
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


def write() -> None:
    update("augustine.json", replace={"Tractates on the Gospel of John": tractates_on_john()})
    update("gregory_of_nyssa.json", replace={"The Great Catechism": great_catechism()})
    update("origen.json", replace={"On Prayer": origen_on_prayer()}, extend={"De Principiis": de_principiis_books_3_and_4()},
           sources={"On Prayer": "Origen, On Prayer, trans. William A. Curtis, from CCEL"})
    update("cyprian_of_carthage.json", replace={"Three Books of Testimonies Against the Jews": testimonies()})
    update("john_of_damascus.json", remove=("Philosophical Chapters",))


if __name__ == "__main__":
    {"download": download, "compare": compare, "write": write}[sys.argv[1] if len(sys.argv) > 1 else "download"]()
