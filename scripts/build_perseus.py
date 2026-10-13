"""
Builds the Greek and Latin works that the Perseus Digital Library has in
English translation, from the canonical-greekLit and canonical-latinLit
submodules (TEI XML), into data/classical/perseus/<author>.json in the
standard schema, plus index.json ({author: [book names]}) for !books.

    python scripts/build_perseus.py            # everything
    python scripts/build_perseus.py tlg0007    # one author (textgroup)

One English translation per work: Perseus's own before First1K's, then the
fullest. Works the library already has (Homer, Plato, Aristotle, the
Apostolic Fathers, Josephus, Philo...) and the Bible books in these repos
are left out. A book is named by its translation's English title ("On
Brotherly Love"), with the author's name added where two works would share
one ("Sophocles: Electra" / "Euripides: Electra").

Citation: the texts' numbered divisions (book, chapter, section...) and the
markers inside them (section and line milestones, numbered verse lines)
give each passage its place. The last level is the verse, the rest the
chapter ("Histories 1.5:3" is book 1, chapter 5, section 3); a work cited by
one level is chapter 1 ("On the Murder of Eratosthenes 1:4" is section 4).
Verse translations keyed by line number begin at that line. Notes are left
out.
"""
import json
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from perseus_tei import passages, to_book  # noqa: E402

OUT = ROOT / "data" / "classical" / "perseus"
REPOS = ("canonical-greekLit", "canonical-latinLit")
CTS = "{http://chs.harvard.edu/xmlns/cts}"
XML_LANG = "{http://www.w3.org/XML/1998/namespace}lang"

# Already in the library (another file, translation or corpus), or not classical
SKIP_GROUPS = {"New Testament", "Old Testament", "Homeric Hymns", "Flavius Josephus", "Clemens Romanus (Clement of Rome)",
               "Barnabae Epistula", "Hermas, 2nd cent.", "Ignatius of Antioch", "Polycarp", "Pseudo-Justinus Martyr",
               "Philo Judaeus", "Homer", "Hesiod"}
SKIP_WORKS = {("Plato", "Alcibiades 1"), ("Plato", "Alcibiades 2"), ("Plato", "Lovers"), ("Epictetus", "The Handbook")}
SKIP_LABELS = {"The Martydom of St. Polycarp",      # the Martyrdom of Polycarp is with the Apostolic Fathers
               'The "Art" of Rhetoric'}             # Aristotle's Rhetoric is in aristotle_perseus.json


def text_of(el, tag) -> str:
    for child in el.iter(CTS + tag):
        if child.text and child.text.strip():
            return re.sub(r"\s+", " ", child.text.strip())
    return ""


def short_author(name: str) -> str:
    """'Cicero, Marcus Tullius' -> 'Cicero'; 'Titus Livius (Livy)' -> 'Livy'; 'Lucian of Samosata' -> 'Lucian'."""
    m = re.search(r"\(([^)]+)\)", name)
    if m and not re.search(r"\d", m.group(1)):
        return m.group(1).replace("Clement of Rome", "Clement")
    name = name.split(",")[0]
    name = re.sub(r"\s+(of|the)\s+.*$", "", name)
    return {"Appianus": "Appian", "Pseudo-Lucian": "Pseudo-Lucian"}.get(name, name)


def translator_of(description: str) -> str:
    """'... Perrin, Bernadotte, translator.' -> 'Bernadotte Perrin'; also 'Frazer, James George, Sir, editor',
    'Shuckburgh, Evelyn S, 1843-1906, editor, translator', 'Watson, J. S. (John Selby), translator',
    'translated by W.R.M. Lamb'."""
    m = re.search(r"([A-Z][\w'\-]+(?: [A-Z][\w'\-]+)?),\s*(Sir\s+)?([A-Z][\w.\- ]*?)\s*(?:\([^)]*\))?"
                  r"(,\s*Sir)?(?:,\s*[\d\-]+)?(?:\s+and\s+[^,]+)?,\s*(?:editor,\s*)?(?:translator|editor)", description)
    if m:
        sir = "Sir " if (m.group(2) or m.group(4)) else ""
        return f"{sir}{m.group(3).strip()} {m.group(1)}".strip()
    m = re.search(r"translated by ((?:[A-Z]\.\s?)*[A-Z][a-z'\-]+(?: [A-Z][a-z'\-]+)*)", description)
    return m.group(1).strip() if m else ""


# ── which works, which translation ──────────────────────────────────────────

def catalogue() -> list:
    works = []
    for repo in REPOS:
        for group_meta in sorted((ROOT / repo / "data").glob("*/__cts__.xml")):
            author = text_of(ET.parse(group_meta).getroot(), "groupname")
            if author in SKIP_GROUPS:
                continue
            for work_meta in sorted(group_meta.parent.glob("*/__cts__.xml")):
                root = ET.parse(work_meta).getroot()
                title = text_of(root, "title")
                if (author, title) in SKIP_WORKS:
                    continue
                options = []
                for t in root.iter(CTS + "translation"):
                    if t.get(XML_LANG) != "eng":
                        continue
                    path = work_meta.parent / (t.get("urn", "").split(":")[-1] + ".xml")
                    if path.exists():
                        options.append((("perseus" not in path.name), -path.stat().st_size, path,
                                        text_of(t, "label"), text_of(t, "description")))
                if options:
                    _, _, path, label, description = sorted(options)[0]
                    if label in SKIP_LABELS:
                        continue
                    # the original: Perseus's Greek or Latin edition, the fullest if several
                    # (some catalogue entries give no language: "phi0448.phi001.perseus-lat2" says it)
                    originals = sorted((-p.stat().st_size, p) for e in root.iter(CTS + "edition")
                                       if e.get(XML_LANG) in ("grc", "lat")
                                       or (not e.get(XML_LANG) and re.search(r"-(lat|grc)\d+$", e.get("urn", "")))
                                       for p in [work_meta.parent / (e.get("urn", "").split(":")[-1] + ".xml")]
                                       if p.exists())
                    works.append({"group": group_meta.parent.name, "author": author, "title": title,
                                  "label": label or title, "translator": translator_of(description), "path": path,
                                  "original": originals[0][1] if originals else None,
                                  "lang": "lat" if repo.endswith("latinLit") else "grc"})
    return works


# ── naming and writing ──────────────────────────────────────────────────────

_ROMAN = {1: "I", 2: "II", 3: "III", 4: "IV", 5: "V", 6: "VI", 7: "VII", 8: "VIII", 9: "IX", 10: "X"}


def book_name(work: dict) -> str:
    name = re.sub(r"\s+", " ", work["label"]).strip(" .")
    # labels that run on into the volume's title ("De Officiis, De officiis",
    # "Letters to Atticus, The letters of Cicero the whole extant correspondence...")
    if ", " in name and not re.search(r", or\b", name):
        name = name.split(", ")[0]
    name = re.sub(r"\s*;.*$", "", name)
    name = re.sub(r"^The Roman History:\s*", "", name)             # Appian's parts
    # a trailing number would read as a chapter ("Hymn 2"): make it Roman
    name = re.sub(r"\s(\d{1,2})$", lambda m: " " + _ROMAN.get(int(m.group(1)), m.group(1)), name)
    return name


def coverage(book: dict, original: dict) -> float:
    """How much of a translation the original lines up with: the share of its
    passages whose chapter is in the original with a verse from that passage's
    number up to the next one's (an English play keyed every few lines, the
    Greek at every line)."""
    hits = total = 0
    for chapter, verses in book.items():
        nums = sorted(int(v) for v in verses)
        theirs = sorted(int(v) for v in original.get(chapter, {}) if v.isdigit())
        for i, v in enumerate(nums):
            total += 1
            upto = nums[i + 1] if i + 1 < len(nums) else float("inf")
            hits += any(v <= k < upto for k in theirs)
    return hits / total if total else 0.0


PARALLEL_MIN = 0.8          # below this the two don't line up well enough to show side by side


def proportion(book: dict, original: dict) -> "tuple[float, float]":
    """(share of passages in proportion, median original/English length): numbers can line
    up while the texts don't -- Golding numbers only his first 113 lines of Metamorphoses 1,
    so "his" line 113 faces 600 lines of Latin; Claudian's English is numbered by paragraph,
    his Latin by line. Aligned works keep the original at a steady ~0.6-0.9 of the English."""
    import statistics
    ratios = []
    for chapter, verses in book.items():
        theirs = original.get(chapter, {})
        nums = sorted(int(v) for v in verses)
        keys = sorted((int(k), k) for k in theirs if k.isdigit())
        for i, v in enumerate(nums):
            upto = nums[i + 1] if i + 1 < len(nums) else float("inf")
            text = "".join(theirs[k] for n, k in keys if v <= n < upto)
            if text:
                ratios.append(len(text) / max(1, len(verses[str(v)])))
    if not ratios:
        return 0.0, 0.0
    median = statistics.median(ratios)
    return sum(1 for r in ratios if median / 4 <= r <= median * 4) / len(ratios), median


def main(only=None):
    works = catalogue()
    if only:
        works = [w for w in works if w["group"] in only]
    existing = {}                       # book name (lower case) -> its source line, to tell whose it is
    data_dir = ROOT / "data"
    for f in data_dir.glob("*/*.json"):
        try:
            payload = json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            continue
        for b in payload.get("books", {}) if isinstance(payload, dict) else {}:
            existing[b.lower()] = (payload.get("book_sources", {}).get(b) or payload.get("source", "")) + " " + f.stem
    names = {}
    for w in works:
        names.setdefault(book_name(w).lower(), []).append(w)
    OUT.mkdir(parents=True, exist_ok=True)
    by_group, index, failures, alias_votes = {}, {}, [], {}
    originals, unmatched = {}, []          # book -> its Greek/Latin original, where the citations line up
    for w in works:
        name = book_name(w)
        author = short_author(w["author"])
        if name.lower() in existing:
            # the same work already here (Plato's Euthyphro) -- or another author's of that name
            # (Xenophon's Apology beside Plato's), which keeps its author in its name
            if author.lower() in existing[name.lower()].lower():
                continue
            name = f"{author}: {name}"
        elif len(names[name.lower()]) > 1:
            name = f"{author}: {name}"
        if name.lower() in existing:
            continue
        # two works of one author under one label (Demosthenes's two speeches Against Onetor): II, III...
        taken = {n.lower() for g in by_group.values() for n in g["books"]}
        if name.lower() in taken:
            name = next(f"{name} {_ROMAN[k]}" for k in range(2, 11) if f"{name} {_ROMAN[k]}".lower() not in taken)
        try:
            book = to_book(passages(w["path"]))
        except Exception as e:                                    # a malformed file: report, carry on
            failures.append((w["path"].name, str(e)[:80]))
            continue
        n = sum(len(v) for v in book.values())
        if n == 0:
            failures.append((w["path"].name, "no text"))
            continue
        g = by_group.setdefault(w["group"], {"author": w["author"], "books": {}, "book_sources": {}})
        g["books"][name] = book
        credit = f"{w['author']}, {w['label']}" + (f", trans. {w['translator']}" if w["translator"] else "")
        g["book_sources"][name] = credit + ". Perseus Digital Library (CC-BY-SA)."
        index.setdefault(short_author(w["author"]), []).append(name)
        if w["original"]:
            try:
                original = to_book(passages(w["original"]))
                match = coverage(book, original)
                steady, median = proportion(book, original)
            except Exception:
                match = steady = median = 0.0
            if match >= PARALLEL_MIN and steady >= 0.9 and 0.4 <= median <= 2.5:
                originals[name] = {"file": w["original"].relative_to(ROOT).as_posix(), "lang": w["lang"],
                                   "match": round(match, 3)}
            else:
                unmatched.append((name, round(match, 2)))
        # the catalogue's own title ("Germania", "Annales") and the name without "The" also find it
        for alias in {w["title"].lower(), re.sub(r"^the ", "", name.lower())} - {name.lower()}:
            alias_votes.setdefault(alias, set()).add(name)
    for group, g in by_group.items():
        path = OUT / f"{group}.json"
        path.write_text(json.dumps({"source": f"{g['author']}. Perseus Digital Library (CC-BY-SA).",
                                    "author": g["author"], "books": g["books"], "book_sources": g["book_sources"]},
                                   ensure_ascii=False, indent=1), encoding="utf-8")
    if not only:
        (OUT / "index.json").write_text(json.dumps(dict(sorted(index.items())), ensure_ascii=False, indent=1),
                                        encoding="utf-8")
        # an alias only where it means one book, and isn't already some book's name
        all_names = set(existing) | {n.lower() for g in by_group.values() for n in g["books"]}
        aliases = {a: next(iter(books)) for a, books in sorted(alias_votes.items())
                   if len(books) == 1 and a not in all_names and not re.search(r"\d$", a)}
        (OUT / "aliases.json").write_text(json.dumps(aliases, ensure_ascii=False, indent=1), encoding="utf-8")
        (OUT / "originals.json").write_text(json.dumps(originals, ensure_ascii=False, indent=1), encoding="utf-8")
    total = sum(len(g["books"]) for g in by_group.values())
    print(f"wrote {total} works by {len(by_group)} authors to {OUT.relative_to(ROOT)}; "
          f"{len(originals)} with their original lined up, {len(unmatched)} without")
    print("  not lined up:", sorted(unmatched, key=lambda x: -x[1])[:40])
    for f in failures:
        print("  FAILED", *f)


if __name__ == "__main__":
    main(set(sys.argv[1:]) or None)
