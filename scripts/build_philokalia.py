"""
The Philokalia (data/patristics/philokalia.json), from the owner's PDF of the English translation by
G.E.H. Palmer, Philip Sherrard and Kallistos Ware (four volumes):

  python scripts/build_philokalia.py "C:/path/to/Philokalia-Complete-Text.pdf"

The PDF is the four printed volumes reflowed: "[V2] 53" marks where printed page 53 of volume 2 begins,
followed by that page's running heads; the text is 10pt, the editors' introductions 9pt, footnotes
smaller, headings 14pt. Some printed pages appear twice or out of order, so the text is gathered page
by printed page and read in the printed order. Each work is a book: its numbered texts are verses
("6. Sometimes thoughts..."), and its centuries, parts or discourses are chapters (a foreword or
prologue before the first is chapter 0). Works without numbered texts have their paragraphs as verses.
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "patristics" / "philokalia.json"

# The works, in the order printed: (author, title, [other heading lines that belong to the title]).
# A book is named "Title (Author)" where the title alone would be ambiguous.
WORKS = [
    ("St Isaiah the Solitary", "On Guarding the Intellect", ["Twenty-Seven Texts"]),
    ("Evagrios the Solitary", "Outline Teaching on Asceticism and Stillness in the Solitary Life", []),
    ("Evagrios the Solitary", "Texts on Discrimination in Respect of Passions and Thoughts", []),
    ("Evagrios the Solitary", "Extracts from the Texts on Watchfulness", []),
    ("Evagrios the Solitary", "On Prayer: One Hundred and Fifty-Three Texts", ["On Prayer:", "One Hundred and Fifty-Three Texts"]),
    ("St John Cassian", "On the Eight Vices", ["Written for Bishop Kastor"]),
    ("St John Cassian", "On the Holy Fathers of Sketis and on Discrimination", ["And on Discrimination", "Written for Abba Leontios"]),
    ("St Mark the Ascetic", "On the Spiritual Law: Two Hundred Texts", ["On the Spiritual Law", "Two Hundred Texts"]),
    ("St Mark the Ascetic", "On Those who Think that They are Made Righteous by Works: Two Hundred and Twenty-Six Texts",
     ["On Those who Think that They are Made Righteous by Works", "Two Hundred and Twenty-Six Texts", "Two Hundred and Twenty- Six Texts"]),
    ("St Mark the Ascetic", "Letter to Nicolas the Solitary", []),
    ("St Hesychios the Priest", "On Watchfulness and Holiness", ["Written for Theodoulos"]),
    ("St Neilos the Ascetic", "Ascetic Discourse", []),
    ("St Diadochos of Photiki", "On Spiritual Knowledge and Discrimination: One Hundred Texts",
     ["On Spiritual Knowledge and Discrimination", "One Hundred Texts"]),
    ("St John of Karpathos", "For the Encouragement of the Monks in India: One Hundred Texts",
     ["For the Encouragement of the Monks in India who had Written to Him", "One Hundred Texts"]),
    ("St John of Karpathos", "Ascetic Discourse Sent at the Request of the Same Monks in India", []),
    ("St Antony the Great", "On the Character of Men and on the Virtuous Life: One Hundred and Seventy Texts",
     ["On the Character of Men and on the Virtuous Life", "One Hundred and Seventy Texts"]),
    ("St Theodoros the Great Ascetic", "A Century of Spiritual Texts", []),
    ("St Theodoros the Great Ascetic", "Theoretikon", []),
    ("St Maximos the Confessor", "Four Hundred Texts on Love", []),
    ("St Maximos the Confessor", "Two Hundred Texts on Theology and the Incarnate Dispensation of the Son of God",
     ["Two Hundred Texts on Theology", "and the", "Incarnate Dispensation of the Son of God", "Written for Thalassios"]),
    ("St Maximos the Confessor", "Various Texts on Theology, the Divine Economy, and Virtue and Vice", []),
    ("St Maximos the Confessor", "On the Lord's Prayer", ["A Short Interpretation", "Addressed to a Devout Christian"]),
    ("St Thalassios the Libyan", "On Love, Self-control and Life in Accordance with the Intellect",
     ["On Love, Self-control and Life", "in Accordance with the Intellect"]),
    ("St John of Damaskos", "On the Virtues and the Vices", []),
    ("Abba Philimon", "A Discourse on Abba Philimon", []),
    ("St Theognostos", "On the Practice of the Virtues, Contemplation and the Priesthood", []),
    ("St Philotheos of Sinai", "Forty Texts on Watchfulness", []),
    ("Ilias the Presbyter", "A Gnomic Anthology", []),
    ("Theophanis the Monk", "The Ladder of Divine Graces", []),
    ("St Peter of Damaskos", "A Treasury of Divine Knowledge", ["Book1", "Book l", "Book 1"]),
    ("St Peter of Damaskos", "Twenty-Four Discourses", ["Book ll", "Book II"]),
    ("St Symeon Metaphrastis", "Paraphrase of the Homilies of St Makarios of Egypt",
     ["Paraphrase of the Homilies", "of St Makarios of Egypt", "of", "St Makarios of Egypt"]),
    ("St Symeon the New Theologian", "On Faith", []),
    ("St Symeon the New Theologian", "One Hundred and Fifty-Three Practical and Theological Texts", []),
    ("St Symeon the New Theologian", "The Three Methods of Prayer", []),
    ("Nikitas Stithatos", "On the Practice of the Virtues: One Hundred Texts", ["On the Practice of the Virtues:", "One Hundred Texts"]),
    ("Nikitas Stithatos", "On the Inner Nature of Things and on the Purification of the Intellect: One Hundred Texts", []),
    ("Nikitas Stithatos", "On Spiritual Knowledge, Love and the Perfection of Living: One Hundred Texts", []),
    ("Theoliptos, Metropolitan of Philadelphia", "On Inner Work in Christ and the Monastic Profession",
     ["On Inner Work in Christ", "And the Monastic Profession"]),
    ("Theoliptos, Metropolitan of Philadelphia", "Texts", []),
    ("Nikiphoros the Monk", "On Watchfulness and the Guarding of the Heart", []),
    ("St Gregory of Sinai", "On Commandments and Doctrines, Warnings and Promises; On Thoughts, Passions and Virtues, "
     "and Also on Stillness and Prayer: One Hundred and Thirty-Seven Texts",
     ["On Commandments and Doctrines, Warnings and Promises; On Thoughts,", "Passions and Virtues, and Also on Stillness and Prayer:",
      "One Hundred and Thirty-Seven Texts"]),
    ("St Gregory of Sinai", "Further Texts", []),
    ("St Gregory of Sinai", "On the Signs of Grace and Delusion, Written for the Confessor Longinos: Ten Texts", []),
    ("St Gregory of Sinai", "On Stillness: Fifteen Texts", []),
    ("St Gregory of Sinai", "On Prayer: Seven Texts", []),
    ("St Gregory Palamas", "To the Most Reverend Nun Xenia", []),
    ("St Gregory Palamas", "A New Testament Decalogue", []),
    ("St Gregory Palamas", "In Defense of Those who Devoutly Practice a Life of Stillness", []),
    ("St Gregory Palamas", "Three Texts on Prayer and Purity of Heart", []),
    ("St Gregory Palamas", "Topics of Natural and Theological Science and on the Moral and Ascetic Life: One Hundred and Fifty Texts",
     ["Topics of Natural and Theological Science and on the Moral and Ascetic Life:", "One Hundred and Fifty Texts"]),
    ("St Gregory Palamas", "The Declaration of the Holy Mountain in Defense of Those who Devoutly Practice A Life of Stillness", []),
]
AMBIGUOUS = {"On Prayer: One Hundred and Fifty-Three Texts", "Ascetic Discourse", "On Faith", "Texts", "Further Texts",
             "On the Virtues and the Vices", "On Watchfulness and Holiness", "On the Eight Vices", "Theoretikon",
             "A Century of Spiritual Texts", "On Prayer: Seven Texts", "On Stillness: Fifteen Texts", "A Gnomic Anthology",
             "On the Practice of the Virtues: One Hundred Texts", "Forty Texts on Watchfulness"}

ORDINALS = {w: n for n, w in enumerate("first second third fourth fifth sixth seventh eighth ninth tenth".split(), 1)}
ROMAN = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100}


def roman(s: str):
    s = s.upper().replace("L", "I") if re.fullmatch(r"[lI1]+", s) else s.upper()   # (the PDF prints "ll" for "II")
    s = s.replace("1", "I")
    if not re.fullmatch(r"[IVXLC]+", s):
        return None
    total = 0
    for a, b in zip(s, s[1:] + " "):
        total += -ROMAN[a] if ROMAN.get(b, 0) > ROMAN[a] else ROMAN[a]
    return total


def key(s: str) -> str:
    """For comparing headings: letters and digits only (the PDF sometimes runs words together: "St JohnCassian")."""
    return re.sub(r"[^a-z0-9]+", "", s.lower())


def chapter_of(heading: str):
    """"Second Century" -> 2, "Part lll" -> 3, "XIV Dispassion" -> 14, "Prologue" -> 0, else None."""
    h = heading.strip()
    m = re.match(r"(?i)^(\w+) century\b", h)
    if m and m.group(1).lower() in ORDINALS:
        return ORDINALS[m.group(1).lower()]
    m = re.match(r"(?i)^part\s+([0-9]+|[ivxl1 ]+)\b", h)
    if m:
        v = m.group(1).replace(" ", "")
        return int(v) if v.isdigit() else roman(v)
    if re.match(r"(?i)^(prologue|foreword|preface|definitions)\b", h):
        return 0
    m = re.match(r"^([IVXl1]+|v|vi{0,3})\b(?:\s|$)", h)
    if m:
        return roman(m.group(1))
    return None


# ── reading the PDF ─────────────────────────────────────────────────────────

def printed_pages(pdf: str) -> list:
    """[((volume, page), [line, ...])] in printed order, each page once; a line is (kind, text, x, gap):
    kind "text" (10pt), "head" (14pt, or a 12pt heading), "run" (a running head), "start" (where the
    printed page begins); the editors' introductions, footnotes and page lists are left out."""
    import fitz
    doc = fitz.open(pdf)
    pages, current, last_y, after_mark = {}, (0, 0), None, False
    for i in range(doc.page_count):
        lines = []
        for block in doc[i].get_text("dict")["blocks"]:
            for line in block.get("lines", []):
                spans = [s for s in line["spans"] if s["text"].strip()]
                if spans:
                    lines.append((line["bbox"][1], line["bbox"][0], spans))
        lines.sort(key=lambda l: (round(l[0]), l[1]))
        last_y = None
        for y, x, spans in lines:
            size = max(round(s["size"]) for s in spans)
            text = "".join(s["text"] for s in spans if not (s["flags"] & 1 and re.fullmatch(r"[\d*†‡\s]+", s["text"])))
            text = re.sub(r"\s+", " ", text).strip()
            if not text:
                continue
            m = re.fullmatch(r"\[V(\d)\]\s*(\d+)", text)
            if m:
                current = (int(m.group(1)), int(m.group(2)))
                if current not in pages:
                    pages[current] = []
                    seen_here = True
                else:
                    seen_here = False                     # (a printed page met again: its copy is skipped)
                pages.setdefault(current, [])
                after_mark, last_y = seen_here, None
                if seen_here:
                    pages[current].append(("start", "", x, 0))
                else:
                    current = (current[0], -current[1])   # (somewhere to put the copy, out of the way)
                    pages[current] = []
                continue
            if size >= 15:                                # the Glossary: the end
                return [(k, v) for k, v in sorted(pages.items()) if k[1] > 0]
            if size >= 13:
                pages.setdefault(current, []).append(("run" if after_mark else "head", text, x, 0))
                continue
            if size == 12:
                if re.match(r"(?i)^(contents|blank or non|\[v\d\])", text) or len(text) > 90:
                    continue
                pages.setdefault(current, []).append(("run" if after_mark else "sub", text, x, 0))
                continue
            after_mark = False
            if size <= 9:
                continue
            gap = (y - last_y) if last_y is not None else None
            last_y = y
            pages.setdefault(current, []).append(("text", text, x, gap))
    return [(k, v) for k, v in sorted(pages.items()) if k[1] > 0]


# ── putting the works together ──────────────────────────────────────────────

def build(pdf: str) -> list:
    authors = {key(a) for a, _, _ in WORKS} | {key(a.replace("St ", "St. ")) for a, _, _ in WORKS}
    works = [{"author": a, "title": t, "parts": {key(t)} | {key(p) for p in extra}, "chapters": {}} for a, t, extra in WORKS]
    w = -1                                                # the work being read
    state = {}

    def reset():
        state.update(chapter=None, verse=None, numbered=False, section=None, pending=[], last=0, skipping=False)
    reset()

    def belongs_to_title(line: str) -> bool:
        k = key(line)
        if not k or k in authors or k in works[w]["parts"]:
            return True
        return len(k) >= 5 and (any(a.startswith(k) for a in authors) or any(k in p for p in works[w]["parts"]))

    def heading(lines: list, kind: str):
        """kind: "head" (a heading), "run" (a printed page's running heads), "sub" (a 12pt heading)."""
        nonlocal w
        joined = key(" ".join(lines))
        nxt = works[w + 1] if w + 1 < len(works) else None
        if kind != "sub" and nxt and key(nxt["title"])[:32] in joined:
            w += 1
            reset()
            lines = [l for l in lines if not belongs_to_title(l)]
            if lines:                                     # (a first section's heading, with the title)
                state["pending"].append(" ".join(lines))
            return
        if w < 0:
            return
        if state["skipping"] and key(works[w]["title"])[:32] in joined:
            state["skipping"] = False                     # (the work itself begins, after its introduction)
        if any(key(l) in ("introductory note", "inroductory note") for l in lines):
            state["skipping"] = True
            return
        if "contents" in [key(l) for l in lines] or any(key(l) in authors and key(l) != key(works[w]["author"])
                                                        and key(l) != key(works[w]["author"].replace("St ", "St. ")) for l in lines):
            state["skipping"] = True                      # (the next author's contents and dates, before his first work)
            return
        if state["skipping"]:
            return
        rest = [l for l in lines if not belongs_to_title(l)]
        if not rest:
            return
        section = " ".join(rest)
        if kind == "run" and (key(section) == key(state["section"] or "")
                              or (state["section"] and key(section) in key(state["section"]))
                              or (chapter_of(section) is not None and str(chapter_of(section)) == state["chapter"])):
            return                                        # (the running head naming the part we are in)
        state["pending"].append(section)

    def open_section(numbered_next: int = None):
        """Start the chapter a pending heading names, once its text begins; a heading over a single text
        that carries on the numbering ("2. How to Say the Prayer") leads that text instead."""
        section = " ".join(state["pending"])
        state["pending"] = []
        chapters = works[w]["chapters"]
        if numbered_next is not None and state["last"] and numbered_next == state["last"] + 1 and chapter_of(section) is None:
            state["section"] = section
            return section                                # (to lead the text, in italics)
        n = chapter_of(section)
        if n is not None and str(n) == state["chapter"]:
            state["section"] = section
            return None
        if n is None or str(n) in chapters:
            n = max([int(c) for c in chapters] or [0]) + 1
        state.update(chapter=str(n), verse=None, section=section)
        chapters.setdefault(str(n), {})["_title"] = section
        return None

    def add_text(text: str, continuing: bool):
        if w >= 0 and re.match(r"^\((Volume \d|c\. ?\d|\d{1,2}th|\d{3,4}\b)", text):
            state["skipping"] = True                      # (an author's dates: his introduction follows)
        if w < 0 or state["skipping"]:
            return
        m = re.match(r"^(\d{1,3})\s?\.\s*(?=[^\d\s])", text)
        n = int(m.group(1)) if m else None
        if n is not None and not (state["last"] < n <= state["last"] + 6 or n == 1):
            m, n = None, None
        lead = None
        if state["pending"]:
            lead = open_section(n)
        chapters = works[w]["chapters"]
        if state["chapter"] is None:
            state["chapter"] = "1" if n == 1 else "0"
            chapters.setdefault(state["chapter"], {})
        verses = chapters[state["chapter"]]
        if n is not None:
            if n == 1 and any(k != "_title" for k in verses):     # the numbering starts again: a new chapter
                c = max(int(k) for k in chapters) + 1
                state["chapter"] = str(c)
                verses = chapters.setdefault(str(c), {})
            state.update(numbered=True, last=n, verse=str(n))
            body = re.sub(r"^[.\s]+", "", text[m.end():])
            verses[str(n)] = f"*{lead}*\n{body}" if lead else body
            return
        if lead:
            text = f"*{lead}*\n{text}"
        if state["verse"] is not None and state["verse"] in verses and (continuing or state["numbered"]) and not lead:
            prev = verses[state["verse"]]
            joiner = " " if continuing else "\n"
            if continuing and re.search(r"[A-Za-z]-$", prev) and text[:1].islower():
                joiner = ""
            verses[state["verse"]] = prev + joiner + text
            return
        v = 1
        while str(v) in verses:
            v += 1
        state["verse"] = str(v)
        verses[str(v)] = text

    for (vol, page), lines in printed_pages(pdf):
        group, kind, page_start = [], None, False
        for k, text, x, gap in lines + [("end", "", 0, 0)]:
            if k in ("head", "run", "sub"):
                if group and kind != k:
                    heading(group, kind)
                    group = []
                group.append(text)
                kind = k
                continue
            if group:
                heading(group, kind)
                group, kind = [], None
            if k == "start":
                page_start = True
                continue
            if k == "end":
                break
            if page_start or gap is None:
                prev = _last_text(works, w, state)
                continuing = bool(prev) and not re.search(r"[.!?:;’'\"”)]\s*$", prev)
                page_start = False
            else:
                continuing = gap < 18
            add_text(text, continuing)
    return works


def _last_text(works, w, state) -> str:
    if w < 0 or state["chapter"] is None or state["verse"] is None:
        return ""
    return works[w]["chapters"].get(state["chapter"], {}).get(state["verse"], "")


def tidy(text: str) -> str:
    text = re.sub(r"\s+([,.;:!?])", r"\1", text)
    text = re.sub(r"[ \t]+", " ", text)
    return text.strip()


def main(pdf: str) -> None:
    works = build(pdf)
    books, missing = {}, []
    for work in works:
        if not work["chapters"]:
            missing.append(work["title"])
            continue
        name = f"{work['title']} ({re.sub(r'^St ', '', work['author'])})" if work["title"] in AMBIGUOUS else work["title"]
        chapters = {}
        for c, verses in sorted(work["chapters"].items(), key=lambda kv: int(kv[0])):
            title = verses.pop("_title", None)
            vs = {v: tidy(t) for v, t in verses.items() if tidy(t)}
            if not vs:
                continue
            if title and not chapter_of(title) == int(c) and chapter_of(title) is None:
                first = min(vs, key=int)
                vs[first] = f"*{title}*\n{vs[first]}"
            chapters[c] = dict(sorted(vs.items(), key=lambda kv: int(kv[0])))
        books[name] = chapters
    if missing:
        raise SystemExit(f"no text found for: {missing}")
    sources = {name: "trans. Palmer, Sherrard and Ware" for name in books}
    payload = {"source": "trans. Palmer, Sherrard and Ware",
               "book_sources": sources, "books": books}
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    for name, chapters in books.items():
        print(f"{name[:70]:70} {len(chapters):3} ch {sum(len(v) for v in chapters.values()):4} texts")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else str(ROOT.parent / "Philokalia-Complete-Text.pdf"))
