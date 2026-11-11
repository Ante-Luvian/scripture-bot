"""
Percy's Reliques of Ancient English Poetry (1765), in H. B. Wheatley's edition (1886), from Project Gutenberg
(#45939-45941, the three volumes): the ballads and poems only -> data/ballads/percy.json, one book, "Percy's
Reliques", a chapter a poem in Percy's order (Series I, Book I, no. I is chapter 1), a verse a stanza.

Left out: Percy's and Wheatley's notes on each poem (and the verse they quote), the footnotes, the essays and
appendices (on the minstrels, the English stage, the alliterative metre, the metrical romances), the glossary, and
the older versions from Percy's folio manuscript that Wheatley prints after some of the poems. The Wanton Wife of
Bath, which Percy dropped from later editions and Wheatley prints as an appendix, is kept, last.

A poem's own verse is told from the verse its notes quote by where it stands: the poem comes after a section rule
(or a part heading, or a label such as a speaker's name), a quotation directly after the prose or note quoting it.
The poem ends at its end mark (⁂, "finis"), the editor's "[The following is the original...", or the footnotes.

    python scripts/build_percy.py
"""
import json
import re
import sys
import urllib.request
from pathlib import Path

from bs4 import BeautifulSoup, NavigableString, Tag

ROOT = Path(__file__).resolve().parent.parent
CACHE = Path(__file__).resolve().parent / ".cache" / "percy"
OUT = ROOT / "data" / "ballads" / "percy.json"
VOLUMES = {45939: "I", 45940: "II", 45941: "III"}
UA = {"User-Agent": "ScriptureBot corpus builder (a personal Discord bot)"}
BOOK = "Percy's Reliques"
# notes the poem follows directly, with no rule between (Edom o' Gordon)
NOTE_THEN_POEM = ("This ballad is found in various versions",)
MAX_LINES = 40                  # (a stanza-less stretch longer than this is cut into passages at a blank-free line)


def expect(ok, message):
    if not ok:
        raise SystemExit(f"unexpected source layout: {message}")


def page(n: int) -> str:
    CACHE.mkdir(parents=True, exist_ok=True)
    f = CACHE / f"{n}.html"
    if not f.exists():
        url = f"https://www.gutenberg.org/cache/epub/{n}/pg{n}-images.html"
        f.write_bytes(urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=120).read())
    return f.read_text(encoding="utf-8")


def words(el) -> str:
    return re.sub(r"\s+", " ", el.get_text(" ")).strip()


SMALL = {"a", "an", "and", "as", "at", "by", "for", "from", "in", "into", "of", "on", "or", "the", "to", "upon",
         "with", "o'", "o’"}


def title_case(s: str) -> str:
    """"THE NOT-BROWNE MAYD." -> "The Not-Browne Mayd"; Roman numerals (K. Edward IV.) kept."""
    s = re.sub(r"\s*\[\d+\]", "", re.sub(r"\s+", " ", s)).strip().rstrip(".,:;").strip()
    out = []
    for i, w in enumerate(s.split(" ")):
        if re.fullmatch(r"[IVXL]+\.?", w) and i:
            out.append(w)
            continue
        low = w.lower()
        if i and low in SMALL:
            out.append(low)
        else:
            out.append("-".join(p[:1].upper() + p[1:] for p in low.split("-")))
    t = " ".join(out)
    t = re.sub(r"\bO' (\w)", lambda m: "o' " + m.group(1).upper(), t)
    return t.replace("'", "’")


def clean_line(span: Tag) -> str:
    for junk in span.select("span.linenum, span.pagenum, a.fnanchor, a[id^=FNanchor]"):
        junk.decompose()
    t = re.sub(r"\s+", " ", span.get_text("")).strip()
    t = re.sub(r"\s*\[\d+\]", "", t)                       # (a footnote's number)
    if re.fullmatch(r"(\*\s*)+", t):                       # (a gap in the text: "* * * * *", not markdown)
        return "· · · · ·"
    # (a word the 1886 printer starred out -- "sh*te", "Ja**s", "* * *" -- in an asterisk Discord doesn't read as bold)
    return t.replace("*", "∗")


def stanzas(poem: Tag) -> list:
    """[[line, ...], ...] for each stanza of a div.poem."""
    out = []
    groups = poem.find_all("div", class_="stanza") or [poem]
    for g in groups:
        lines = []
        for span in g.find_all("span", recursive=False):
            if "pagenum" in (span.get("class") or []):
                continue
            line = clean_line(span)
            if line:
                lines.append(line)
        if lines:
            out.append(lines)
    return out


def label(text: str):
    """A centred line inside a poem: ("speaker", name), ("note", text) or None (a stanza's number)."""
    text = re.sub(r"\s*\[\d+\]", "", text).strip().replace(" .", ".")
    # (a stanza's or section's number -- "I.", "I. 1.", "2." -- and the editor's "The following is printed from...")
    if not text or re.fullmatch(r"(?:[IVXLC]+\.\s*)?\d*\.?", text) or text.startswith("The following"):
        return None
    if text.startswith("["):
        return ("note", text)
    if len(text.split()) <= 3 and text.endswith(".") and (text[0].isupper() or text[0].isdigit()) and not re.search(r"\b(Part|Fytte|Fit|Cap)\b", text, re.I):
        return ("speaker", text.rstrip(".").strip())
    return ("note", text)


def blocks(soup) -> list:
    """The body's top-level blocks in order, as (kind, element)."""
    out = []
    for el in soup.body.find_all(["h2", "h3", "h4", "p", "div", "hr"]):
        if el.find_parent("div", class_=["blockquot", "footnotes", "poem"]) is not None or el.find_parent("p"):
            continue
        cls = el.get("class") or []
        txt = words(el)
        if el.name in ("h2", "h3", "h4"):
            out.append((el.name, el))
        elif el.name == "hr":
            if "tb" in cls or "chap" in cls:
                out.append(("rule", el))
        elif el.name == "div":
            kind = "verse" if "poem" in cls else "note" if "blockquot" in cls else "footnotes" if "footnotes" in cls \
                else None
            if kind:
                out.append((kind, el))
        elif el.name == "p" and txt and not re.fullmatch(r"\[ ?Pg [\w]+ ?\]", txt):
            if "center" in cls or "ph4" in cls:
                out.append(("label", el))
            elif "right" in cls or "stageright" in cls:
                out.append(("mark", el))
            elif "ph1" in cls:
                continue
            else:
                out.append(("prose", el))
    return out


def poems_of(n: int) -> list:
    """[(series, book, number, title, [(kind, payload)])] for one volume; payload items: ("stanza", lines),
    ("part", heading), ("speaker", name), ("note", text)."""
    soup = BeautifulSoup(page(n), "lxml")
    found, book, cur = [], None, None
    state = None            # None: before the poem, "in": reading it, "out": past it (a part heading resumes it)
    prev = None             # the kind of the last block that counts (figures don't)
    pending = []            # labels and part headings waiting for the poem's next stanza

    def finish():
        if cur and cur[4]:
            found.append(cur)

    for kind, el in blocks(soup):
        txt = words(el)
        if kind == "h2":
            finish()
            cur, state, prev, pending = None, None, None, []
            m = re.match(r"BOOK (\w+)", txt)
            book = {"1": "I"}.get(m.group(1), m.group(1)) if m else None
            if "WANTON WIFE OF BATH" in txt:
                book = "Appendix"
                cur = [VOLUMES[n], book, "", title_case(re.sub(r"^APPENDIX I\.\s*", "", txt)), []]
            continue
        if kind == "h3":
            if book is None:
                continue
            finish()
            m = re.match(r"([IVXLC]+)\.\s*(.*)$", txt)
            if not m:                                       # ("Poems on King Arthur, etc.": a heading, no poem)
                cur, state = None, None
                continue
            cur = [VOLUMES[n], book, m.group(1), title_case(m.group(2)), []]
            state, prev, pending = None, "h3", []
            continue
        if cur is None:
            continue
        if kind == "footnotes":
            state = "done"
        if state == "done":
            continue
        if kind == "h4":
            if state is not None:                           # (a part heading inside the poem: resume)
                state = "in"
            pending.append(("part", title_case(txt)))
            prev = "h4"
            continue
        if kind == "rule":
            prev = "rule"
            continue
        if kind == "label":
            # (a label opens the poem only where the poem could begin: Percy's notes have their own centred lines,
            # the names of the ballads they quote -- "The Ballad of Constant Susanna.")
            if prev in ("rule", "h4", "h3", "label", "verse-ours"):
                lab = label(txt)
                if lab:
                    pending.append(lab)
                prev = "label"
            else:
                prev = "prose"
            continue
        if kind == "mark":
            if re.fullmatch(r"⁂|f+in(i)?s\.?\]?", txt.strip(), re.I) and state == "in":
                state = "done"
            prev = "mark"
            continue
        if kind in ("prose", "note"):
            if re.match(r"\[?The following (is|version|forms|stanzas)", txt) and state is not None:
                state = "done"
                continue
            # (a note straight after a part heading is the part's subtitle: Gernutus's "Of the Jews crueltie...")
            if kind == "note" and prev == "h4" and state is not None and len(txt) < 200:
                pending.append(("note", txt.strip("[]")))
                prev = "h4"
                continue
            if kind == "note" and txt.startswith(NOTE_THEN_POEM) and state is None:
                prev = "rule"                               # (the poem follows this note directly)
                continue
            if state == "in":
                state = "out"
            if kind == "prose" or state is None:
                pending = [p for p in pending if p[0] == "part"] if state is not None else []
            prev = kind
            continue
        if kind == "verse":
            ours = prev in ("rule", "h4", "label", "verse-ours") or (prev == "h3")
            if state == "out" and prev != "h4":
                ours = False
            if not ours:
                prev = "verse"
                continue
            state = "in"
            for lines in stanzas(el):
                cur[4].extend(pending)
                pending = []
                cur[4].append(("stanza", lines))
            prev = "verse-ours"
    finish()
    return found


def passages(items: list) -> list:
    """The poem's verses: each stanza with whatever leads it (a part heading, a speaker, a note); a long stanza-less
    stretch cut every ~MAX_LINES lines."""
    out, lead = [], []
    for kind, value in items:
        if kind == "stanza":
            lines = value
            while lines:
                chunk, lines = lines[:MAX_LINES], lines[MAX_LINES:]
                if lines and len(lines) < 10:                # (no stub at the end)
                    chunk, lines = chunk + lines, []
                out.append("\n".join(lead + chunk))
                lead = []
        elif kind == "part":
            lead.append(f"*{value}*")
        elif kind == "speaker":
            lead.append(f"**{value}**")
        else:
            lead.append(f"*{value}*")
    if lead and out:
        out[-1] += "\n" + "\n".join(lead)
    return out


def main():
    chapters, titles, sources = {}, {}, {}
    n = 0
    for vol in VOLUMES:
        for series, book, number, title, items in poems_of(vol):
            verses = passages(items)
            expect(verses, f"{title}: no verse")
            n += 1
            where = f"Series {series}, Book {book}, no. {number}" if book != "Appendix" else f"Series {series}, Appendix"
            verses[0] = f"*{title}* ({where})\n" + verses[0]
            chapters[str(n)] = {str(i): v for i, v in enumerate(verses, 1)}
            titles[str(n)] = title
    data = {"source": "Thomas Percy (1765), ed. Henry B. Wheatley (1886)",
            "titles": titles, "books": {BOOK: chapters}}
    OUT.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{BOOK}: {n} poems, {sum(len(c) for c in chapters.values())} passages -> {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    sys.exit(main())
