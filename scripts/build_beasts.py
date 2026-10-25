"""
Two medieval books of beasts:

  * The Physiologus, in Olga M. Mladenova and Vesselin Stoykov's English (from Ana Stoykova's translation of the
    Old Bulgarian, Byzantine recension, checked against the Greek), physiologus.proab.info/?pg=in-english
    -> data/medieval/physiologus.json, "Physiologus": a chapter a beast in the site's order (1 the introduction),
       a verse a paragraph, each with its Christian reading. Its footnotes (Bible references) go in brackets.
  * Reynard the Fox, William Caxton's translation (1481) as Henry Morley edited it (1889), modern spelling, as
    David Badke transcribed it for bestiary.ca -> data/ballads/reynard.json, "Reynard the Fox": a chapter a
    chapter, a verse a paragraph; Morley's glosses of old words, footnotes there, close each chapter as
    "Old words: ...".

    python scripts/build_beasts.py
"""
import html
import json
import re
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "scripts" / ".cache" / "beasts"
UA = {"User-Agent": "ScriptureBot corpus builder (personal Discord bot)"}
SOURCES = {"physiologus.html": "https://physiologus.proab.info/?pg=in-english",
           "reynard.txt": "https://bestiary.ca/etexts/morley-history-of-reynard-the-fox.txt"}
MISSED = []
ROMAN = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100}


def fetch(name: str) -> str:
    path = CACHE / name
    if not path.exists():
        CACHE.mkdir(parents=True, exist_ok=True)
        path.write_bytes(urllib.request.urlopen(urllib.request.Request(SOURCES[name], headers=UA), timeout=60).read())
    return path.read_text(encoding="utf-8")


def roman(s: str) -> int:
    total = 0
    for a, b in zip(s, s[1:] + " "):
        total += -ROMAN[a] if ROMAN.get(b, 0) > ROMAN[a] else ROMAN[a]
    return total


# ── the Physiologus ─────────────────────────────────────────────────────────

def physiologus() -> dict:
    t = fetch("physiologus.html")
    boxes = re.split(r'(?=<h3 class="ccap"><a id="anc\d+"></a>)', t)[1:]
    chapters = []
    for box in boxes:
        m = re.match(r'<h3 class="ccap"><a id="anc(\d+)"></a>(.*?)</h3>', box, re.S)
        n, title = int(m.group(1)), html.unescape(re.sub(r"<sup>.*?</sup>|<[^>]+>", "", m.group(2))).strip()
        title_marks = re.findall(r"<sup>(\d+)</sup>", m.group(2))
        # A box can hold two translations of the chapter, each with its own footnotes (numbered afresh) after
        # it: each run of text takes the notes that follow it.
        parts = re.split(r'(?s)(<div class="cbels">.*?</div>)', box[m.end():])
        body, title_notes = "", []
        for i in range(0, len(parts), 2):
            notes = dict(re.findall(r"<sup>(\d+)</sup>\s*([^<]+)", parts[i + 1])) if i + 1 < len(parts) else {}
            notes = {k: re.sub(r"\s+", " ", v).strip().rstrip(".") for k, v in notes.items()}
            if i == 0:
                title_notes = [notes[k] for k in title_marks if k in notes]
            body += re.sub(r"<sup>(\d+)</sup>", lambda s: f" ({notes[s.group(1)]})" if s.group(1) in notes else "",
                           parts[i])
        # a second translation of the chapter in the same box, under its own heading
        body = re.sub(r'(?is)<h3 class="">(.*?)</h3>', r"<p>**\1**</p>", body)
        paras = []
        for p in re.findall(r"(?is)<p[^>]*>(.*?)</p>", body):
            p = html.unescape(re.sub(r"<[^>]+>", "", re.sub(r"(?i)<br\s*/?>", "\n", p)))
            p = re.sub(r"[ \t\r\n]+", " ", p).replace(" •", "").replace("•", "").strip()
            p = re.sub(r"\s+([.,;:!?])", r"\1", p)
            if p:
                paras.append(p)
        if not paras:
            raise SystemExit(f"Physiologus: {title} has no text")
        paras[0] = f"*{title}*\n{paras[0]}"
        if title_notes:                                 # (the translators' note on the title)
            paras.append("-# Note: " + "; ".join(title_notes) + ".")
        chapters.append((n, {str(i + 1): p for i, p in enumerate(paras)}))
    chapters.sort()
    if len(chapters) < 33:
        raise SystemExit(f"Physiologus: only {len(chapters)} chapters")
    return {str(i + 1): c for i, (_, c) in enumerate(chapters)}


# ── Reynard the Fox ─────────────────────────────────────────────────────────

def reynard() -> dict:
    t = fetch("reynard.txt").replace("\r", "")
    start = t.index("CHAPTER I.")
    notes_at = re.search(r"\n\s*1 \S[^\n]*\n\s*2 \S", t[start:])
    text, notes_text = t[start:start + notes_at.start()], t[start + notes_at.start():]
    notes = {int(m.group(1)): m.group(2).strip() for m in re.finditer(r"(?m)^\s*(\d+) (.+?)\s*$", notes_text)}
    # Each footnote mark is the next number in turn after a word ("Dasse 9", "Eme11"): found in order, so
    # the book's own numbers (a year, "three") are never taken for one.
    # (the notes begin with some on Morley's introduction, which isn't here: the story's first mark is found
    # by trying each start, keeping the one that matches most marks in turn)
    def marks_from(first):
        found, pos, k, out = {}, 0, first, []
        while k in notes:
            # after a word or its punctuation (a closing quote too); never a page number such as "[116]"
            m = re.compile(r"(?<=[A-Za-z\u2019'\u201d\".,;:!?)])[ \u00a0]?" + str(k) + r"(?![\d\]])").search(text, pos)
            if not m:                                   # (a mark the digital edition lost: its note is left out)
                k += 1
                continue
            out.append(text[pos:m.start()])
            found[k] = m.start()
            pos, k = m.end(), k + 1
        return found, "".join(out) + text[pos:]
    found, text = max((marks_from(first) for first in range(1, 12)), key=lambda r: len(r[0]))
    MISSED[:] = [k for k in range(min(found), max(notes) + 1) if k not in found]
    print("Reynard: footnote marks not found:", MISSED, "first:", min(found))
    if len(found) < len(notes) - 12:
        raise SystemExit(f"Reynard: only {len(found)} of {len(notes)} footnote marks found")
    chapters = {}
    heads = list(re.finditer(r"(?m)^\s*CHAPTER ([IVXLC]+)\.\s*\n\s*(.+?)\n", text))
    for h, nxt in zip(heads, heads[1:] + [None]):
        n, title = roman(h.group(1)), h.group(2).strip()
        if str(n) in chapters:                          # (Morley prints "CHAPTER XXVI." twice: the second is XXVII)
            n = max(map(int, chapters)) + 1
        body = text[h.end():nxt.start() if nxt else len(text)]
        body = re.sub(r"\[\d+\]\s*", "", body)                    # (the printed book's page numbers)
        paras = [re.sub(r"\s+", " ", p).strip() for p in re.split(r"\n\s*\n|\n(?=\s{3,}\S)", body)]
        paras = [p for p in paras if p]
        if not paras:
            raise SystemExit(f"Reynard {n} has no text")
        paras[0] = f"*{title}*\n{paras[0]}"
        chapters[str(n)] = paras
    # the glosses, chapter by chapter: a mark belongs to the chapter whose text it fell in (positions in the
    # text as it was, marks and all)
    marks = sorted(found.items(), key=lambda kv: kv[1])
    original = t[start:start + notes_at.start()]
    bounds = [(roman(h.group(1)), h.start()) for h in re.finditer(r"(?m)^\s*CHAPTER ([IVXLC]+)\.", original)]
    for n, at in marks:
        chapter = max((c for c, b in bounds if b <= at), default=None)
        if chapter and notes.get(n) and not re.fullmatch(r"\d{4}\.?", notes[n]):
            chapters[str(chapter)].append(("note", notes[n]))
    out = {}
    for c, paras in chapters.items():
        words = [p[1] for p in paras if isinstance(p, tuple)]
        verses = [p for p in paras if not isinstance(p, tuple)]
        if words:
            verses.append("-# Old words: " + "; ".join(w.rstrip(".") for w in words) + ".")
        out[c] = {str(i + 1): v for i, v in enumerate(verses)}
    return dict(sorted(out.items(), key=lambda kv: int(kv[0])))


def save(path: Path, source: str, book: str, chapters: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"source": source, "books": {book: chapters}}, ensure_ascii=False, indent=1),
                    encoding="utf-8")
    words = sum(len(v.split()) for c in chapters.values() for v in c.values())
    print(f"{book}: {len(chapters)} chapters, {words:,} words -> {path.relative_to(ROOT)}")


def main():
    save(ROOT / "data" / "medieval" / "physiologus.json",
         "trans. Olga M. Mladenova and Vesselin Stoykov, from Ana Stoykova's", "Physiologus", physiologus())
    save(ROOT / "data" / "ballads" / "reynard.json", "Caxton's translation (1481), ed. Henry Morley (1889)",
         "Reynard the Fox", reynard())


if __name__ == "__main__":
    sys.exit(main())
