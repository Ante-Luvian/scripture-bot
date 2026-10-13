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
import html
import json
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
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
SKIP_BOOK_TITLES = {"Epigrams"}        # Homer's (left by SKIP_GROUPS); placeholder


def local(tag) -> str:
    return tag.rsplit("}", 1)[-1] if isinstance(tag, str) else ""


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
    """'... Perrin, Bernadotte, translator. Cambridge...' -> 'Bernadotte Perrin'."""
    m = re.search(r"([A-Z][\w'\-]+(?: [A-Z][\w'\-]+)?),\s*([A-Z][\w.\- ]+?)(?:\s+and\s+[^,]+)?,\s*(?:translator|editor)",
                  description)
    return f"{m.group(2).strip()} {m.group(1)}".strip() if m else ""


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
                    works.append({"group": group_meta.parent.name, "author": author, "title": title,
                                  "label": label or title, "translator": translator_of(description), "path": path})
    return works


# ── TEI to passages ─────────────────────────────────────────────────────────

_XML_ENTITIES = {"amp", "lt", "gt", "quot", "apos"}


def load_tei(path: Path) -> ET.Element:
    raw = path.read_text(encoding="utf-8", errors="replace")
    raw = re.sub(r"<!DOCTYPE[^>\[]*(\[.*?\])?\s*>", "", raw, flags=re.S)
    raw = re.sub(r"&(\w+);", lambda m: m.group(0) if m.group(1) in _XML_ENTITIES
                 else html.unescape(m.group(0)) if html.unescape(m.group(0)) != m.group(0) else "", raw)
    return ET.fromstring(raw)


# (in <choice>, the editors' regularised form -- "Bodrum [27.466,37.5] (inhabited place)" for the
# translator's "Halicarnassus" -- and an uncorrected <sic> go; <orig> and <corr> stay)
_DROP = {"note", "bibl", "ref", "figure", "gap", "del", "teiHeader", "reg", "sic"}


def drop(el: ET.Element) -> None:
    """Remove notes and the like, keeping the text that follows them."""
    for child in list(el):
        if local(child.tag) in _DROP:
            tail = child.tail or ""
            idx = list(el).index(child)
            if idx:
                prev = el[idx - 1]
                prev.tail = (prev.tail or "") + tail
            else:
                el.text = (el.text or "") + tail
            el.remove(child)
        else:
            drop(child)


def citable(el) -> bool:
    tag = local(el.tag)
    return el.get("n") is not None and (
        (tag == "div" and el.get("type") in ("textpart", None) and el.get("subtype") != "edition")
        or re.fullmatch(r"div[1-7]", tag) is not None)


def has_citable(el) -> bool:
    return any(citable(d) for d in el.iter() if d is not el)


def events(el):
    """("text", s) / ("mark", unit, n) / ("break",) through an element, in order."""
    tag = local(el.tag)
    if tag == "milestone" and el.get("n") is not None:
        yield ("mark", (el.get("unit") or "").lower(), el.get("n"))
    elif tag == "l" and el.get("n") is not None:
        yield ("mark", "l", el.get("n"))
    elif tag in ("head",):
        yield ("text", "")
    # (the file's own line breaks are just spacing; real breaks come from the structure)
    if el.text and tag not in ("head",):
        yield ("text", el.text.replace("\n", " "))
    for child in el:
        yield from events(child)
        if child.tail:
            yield ("text", child.tail.replace("\n", " "))
    if tag == "lb":
        yield ("break",)
    if tag in ("l", "p", "lg", "sp", "speaker", "div", "quote") or re.fullmatch(r"div\d", tag):
        yield ("break",)


def tidy(s: str) -> str:
    lines = [re.sub(r"[ \t\r\f\v]+", " ", l).strip() for l in s.split("\n")]
    out = "\n".join(l for l in lines if l)
    return re.sub(r" ([,.;:!?])", r"\1", out).strip()


def split_leaf(el, unit: str) -> list:
    """[(marker n or None, text)] for one cited division, cut at its markers."""
    # (a marker without a number -- Lucan's translator marks every line "tr" -- is no place to cut)
    evs = [e for e in events(el) if not (e[0] == "mark" and not re.match(r"\d", e[2]))]
    marks = [e for e in evs if e[0] == "mark"]
    units = [m[1] for m in marks]
    # the declared unit's markers, or for verse its numbered lines -- whichever there are
    # more of (The Phoenician Maidens has one stray line milestone among 600 numbered lines)
    candidates = [u for u in ([unit] if unit else []) + (["l", "line"] if unit in ("line", "l", "verse", "") else [])
                  if u in units]
    cut = max(candidates, key=units.count) if candidates else None
    pieces, key, buf = [], None, []
    for e in evs:
        if e[0] == "mark" and e[1] == cut:
            if "".join(buf).strip() or key is not None:
                pieces.append((key, "".join(buf)))
            key, buf = e[2], []
        elif e[0] == "text":
            buf.append(e[1])
        elif e[0] == "break":
            buf.append("\n")
    pieces.append((key, "".join(buf)))
    pieces = [(k, tidy(t)) for k, t in pieces]
    pieces = [(k, t) for k, t in pieces if t]
    # text before the first marker (a heading, a speaker) joins the first passage
    if len(pieces) > 1 and pieces[0][0] is None:
        pieces[1] = (pieces[1][0], pieces[0][1] + "\n" + pieces[1][1])
        pieces = pieces[1:]
    return pieces


def passages(path: Path) -> list:
    """[(citation levels, text)] for a TEI file."""
    root = load_tei(path)
    # (the citation levels are declared in the header, which drop() removes)
    units = [(c.get("n") or "").lower() for c in root.iter() if local(c.tag) == "cRefPattern"][::-1]
    drop(root)
    body = next(el for el in root.iter() if local(el.tag) == "body")
    out = []

    def unit_at(depth):
        return units[depth] if depth < len(units) else (units[-1] if units else "")

    def walk(el, levels):
        cited = [c for c in el if citable(c)]
        if cited:
            ns = [c.get("n") for c in cited]
            for i, c in enumerate(cited, 1):
                unit = (c.get("subtype") or c.get("type") or unit_at(len(levels))).lower()
                n = c.get("n")
                # a container named, not numbered ("Tiberius", "Caius"), or numbered twice
                # (De Officiis's third book is "1"), takes its place among its siblings
                if (not re.fullmatch(r"\d+", n) or ns.count(n) > 1) and has_citable(c):
                    n = "0" if re.match(r"intro|pr(o|ae)f|prolog", n, re.I) else str(i)
                walk(c, levels + [(unit, n)])
            return
        unit = unit_at(len(levels))
        pieces = split_leaf(el, unit)
        if len(pieces) == 1 and pieces[0][0] is None and len(pieces[0][1]) > 3000:
            # a long division with no numbered parts (Claudian's poems): a verse per paragraph
            paras = [p for p in pieces[0][1].split("\n") if p.strip()]
            pieces = [(str(i), p) for i, p in enumerate(paras, 1)]
        for n, text in pieces:
            out.append((levels + ([(unit, n)] if n is not None else []), text))

    start = body
    # the edition / translation wrapper div is not a citation level
    while len(start) == 1 and local(start[0].tag) == "div" and start[0].get("type") in ("edition", "translation"):
        start = start[0]
    walk(start, [])
    cleaned = []
    for levels, text in out:
        # an editor's introduction ("intro") is not the author's text
        if any(re.match(r"intro", str(n), re.I) for _, n in levels):
            continue
        # a "card" is Perseus's page of verse, not part of the citation: Metamorphoses 1:5, not 1.1:5
        if len(levels) > 1:
            levels = [lv for lv in levels[:-1] if lv[0] != "card"] + [levels[-1]]
        cleaned.append(([n for _, n in levels], text))
    return cleaned


def to_book(items: list) -> dict:
    """{chapter: {verse: text}}; the last level is the verse, a single level is chapter 1."""
    book = {}
    if all(len(levels) == 0 for levels, _ in items):              # no structure at all: a verse per paragraph
        paras = [p for _, t in items for p in t.split("\n") if p.strip()]
        return {"1": {str(i): p for i, p in enumerate(paras, 1)}}
    last = None
    for levels, text in items:
        levels = [re.sub(r"\s+", "", str(x)) for x in levels] or ["1"]
        if levels[0] == "front":                                   # a play's cast list and argument
            continue
        # a half-line, part-section or speaker's share ("293b", "12a", "1034_sp2", "159_160") is its number
        levels = [re.sub(r"^(\d+)(?:[a-z]|[_\-].*)$", r"\1", x) for x in levels]
        # a named division in the chapter ("pr", "prologue") is 0
        levels = levels[:-1 if len(levels) > 1 else 0] and \
            [x if re.fullmatch(r"\d+", x) else "0" for x in levels[:-1]] + [levels[-1]] or levels
        chapter, verse = (".".join(levels[:-1]), levels[-1]) if len(levels) > 1 else ("1", levels[0])
        if not re.fullmatch(r"\d+", verse):
            # an unnumbered piece joins the verse before; a preface before verse 1 is verse 0
            chapter, verse = last if last and last[0] == chapter else (chapter, "0")
        verses = book.setdefault(chapter, {})
        verses[verse] = (verses[verse] + "\n" + text) if verse in verses else text
        last = (chapter, verse)
    return book


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


def main(only=None):
    sys.path.insert(0, str(ROOT))
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
    total = sum(len(g["books"]) for g in by_group.values())
    print(f"wrote {total} works by {len(by_group)} authors to {OUT.relative_to(ROOT)}")
    for f in failures:
        print("  FAILED", *f)


if __name__ == "__main__":
    main(set(sys.argv[1:]) or None)
