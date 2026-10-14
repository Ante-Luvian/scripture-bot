"""
perseus_tei.py
--------------
Turns a Perseus (CapiTainS) TEI file into passages keyed the way the text is
cited -- used by scripts/build_perseus.py to build the library, and by
!parallel to read a work's Greek or Latin original beside the translation.
See build_perseus.py for the citation rules.
"""
import html
import re
import xml.etree.ElementTree as ET
from pathlib import Path


def local(tag) -> str:
    return tag.rsplit("}", 1)[-1] if isinstance(tag, str) else ""



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
    cleaned, carded = [], []
    for levels, text in out:
        # an editor's introduction ("intro") is not the author's text
        if any(re.match(r"intro", str(n), re.I) for _, n in levels):
            continue
        # a "card" is Perseus's page of verse, not part of the citation: Metamorphoses 1:5, not 1.1:5
        card = None
        if len(levels) > 1:
            card = next((n for unit, n in levels[:-1] if unit == "card"), None)
            levels = [lv for lv in levels[:-1] if lv[0] != "card"] + [levels[-1]]
        cleaned.append(([n for _, n in levels], text))
        carded.append(card)
    return _renumber_restarting(cleaned, carded)


def _renumber_restarting(items: list, cards: list) -> list:
    """Where a translation's line numbers start again on each card (Golding's Ovid), dropping
    the card would put every card's line 2 together in one "verse 2", lines from all over the
    book. In such a chapter the verses are numbered straight through, in reading order."""
    seen, clash = {}, set()
    for (levels, _), card in zip(items, cards):
        if card is None or len(levels) < 2:
            continue
        chapter, verse = tuple(levels[:-1]), levels[-1]
        other = seen.setdefault((chapter, verse), card)
        if other != card:
            clash.add(chapter)
    if not clash:
        return items
    count, out = {}, []
    for levels, text in items:
        chapter = tuple(levels[:-1])
        if chapter in clash and len(levels) > 1:
            count[chapter] = count.get(chapter, 0) + 1
            levels = list(chapter) + [str(count[chapter])]
        out.append((levels, text))
    return out


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


# ── the original beside the translation (!parallel) ──────────────────────────

import functools  # noqa: E402
import json  # noqa: E402

_ROOT = Path(__file__).resolve().parent


@functools.lru_cache(maxsize=1)
def _originals() -> dict:
    """book -> {"file", "lang", "match"} for the works whose original lines up (build_perseus.py)."""
    path = _ROOT / "data" / "classical" / "perseus" / "originals.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


@functools.lru_cache(maxsize=6)
def _original_book(rel: str) -> dict:
    return to_book(passages(_ROOT / rel))


def has_original(book: str) -> bool:
    return book in _originals()


def original_for(book: str, chapter: str, first: int, last: int, english_keys) -> "tuple[str, str] | None":
    """(Greek or Latin text, "grc"/"lat") for verses first..last of a translated book: the
    original's passages from `first` up to the translation's next verse after `last` (a
    play translated in chunks of lines, the original line by line), or None."""
    info = _originals().get(book)
    if not info:
        return None
    original = _original_book(info["file"]).get(chapter)
    if not original:
        return None
    later = sorted(k for k in (int(v) for v in english_keys if str(v).isdigit()) if k > last)
    upto = later[0] if later else float("inf")
    keys = sorted((int(k), k) for k in original if k.isdigit())
    text = "\n".join(original[k] for n, k in keys if first <= n < upto)
    return (text, info["lang"]) if text.strip() else None
