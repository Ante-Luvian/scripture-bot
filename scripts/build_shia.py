"""
Shi'ite texts, from files the owner downloaded (2026-11-09; the sites refuse scripts):

    Nahj al-Balagha -- 'Ali's orations, letters and sayings, compiled by al-Sharif al-Radi (d. 1015), in Tahera
        Qutbuddin's translation (Brill, 2024, open access): C:/Users/chris/Downloads/9789004682603-69007.pdf.
        A parallel text, Arabic on the left-hand pages and English on the right: only the English is read. Cited
        as she numbers it -- 1.N an oration, 2.N a letter, 3.N a saying, 0.N Radi's introduction -- each a
        chapter ("Nahj al-Balagha 1.1"), its paragraphs (1.1.1, 1.1.2) its verses; Radi's heading for each piece
        ("From an oration by 'Ali, in which he spoke of the creation...") in italics before its first paragraph.
    Sahifa Sajjadiyya -- the supplications of 'Ali ibn al-Husayn, Zayn al-'Abidin, the fourth Imam.

    python scripts/build_shia.py
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOWNLOADS = Path.home() / "Downloads"
NAHJ_PDF = DOWNLOADS / "9789004682603-69007.pdf"
SAHIFA_PDF = DOWNLOADS / "as-sahifa_al-kamilah_al-sajjadiyya_.pdf"


def expect(ok: bool, message: str) -> None:
    if not ok:
        raise SystemExit(f"unexpected source layout: {message}")


def _arabic_share(text: str) -> float:
    letters = [c for c in text if c.isalpha()]
    return sum(1 for c in letters if "\u0600" <= c <= "\u06ff") / max(1, len(letters))


def _english_pages(reader, first: int, last: int) -> str:
    """The English pages' text, running header and footnotes off."""
    out = []
    for i in range(first, last):
        text = reader.pages[i].extract_text() or ""
        if _arabic_share(text) > 0.2:
            continue
        lines = [line for line in text.split("\n") if re.search(r"[^\W\d_ـ]", line)]     # (not blank or "ـــــ")
        if lines and re.match(r"^\s*\d+\s+(Chapter \d|Raḍī|Text and Translation|Additional Sayings)", lines[0]):
            lines = lines[1:]
        lines = [line for line in lines if not re.fullmatch(r"\s*Additional Sayings\d*\s*", line)]
        kept = []
        for line in lines:
            if re.match(r"^\s*\d{1,3} (?![\d.])\S", line) and kept:      # (the page's footnotes, to its foot)
                break
            kept.append(line)
        out.append("\n".join(kept))
    return "\n".join(out)


def _tidy(text: str) -> str:
    text = re.sub(r"(?<=[A-Za-zā-ūʿʾ.,;:!?’”»)\]])\d{1,3}(?=[\s.,;:’”»)]|$)", "", text)      # (note marks)
    text = re.sub(r"(\w)-\n(\w)", r"\1\2", text)          # (a word broken over a line)
    return re.sub(r"\s+", " ", text).strip()


def nahj() -> dict:
    import pypdf
    reader = pypdf.PdfReader(str(NAHJ_PDF))
    # the translation: from Radi's introduction to the end of the sayings
    pages = [(reader.pages[i].extract_text() or "") for i in range(len(reader.pages))]
    start = next(i for i, t in enumerate(pages) if re.search(r"(?m)^0\.1 ", t) and _arabic_share(t) < 0.2)
    # it ends with Radi's Conclusion (after it, her appendix of sources reuses the texts' numbers)
    end = next(i for i in range(start, len(pages)) if "Raḍī’s Conclusion" in pages[i] and _arabic_share(pages[i]) < .2)
    text = _english_pages(reader, start, end + 1)
    text, conclusion = text.split("Raḍī’s Conclusion", 1)
    # a part's title page ("1 / Orations / Chapter containing selections..."): not the text
    text = re.sub(r"(?ms)^\s*(?:[123]\s*\n\s*)?(Orations|Letters|Sayings)\s*\n.*?(?=^\s*[123]\.1 )", "", text)
    sections, order = {}, []
    current = None
    for m in re.finditer(r"(?m)^([0-3])\.(\d+)(?:\.(\d+))? (.*?)(?=^[0-3]\.\d+(?:\.\d+)? |\Z)", text, re.S):
        part, num, para, body = m.groups()
        key = num if part == "0" else f"{part}.{num}"
        if part == "0":                       # (Radi's introduction: one chapter, "0", its paragraphs)
            key, para = "0", num
        sec = sections.setdefault(key, {"head": None, "paras": {}})
        if key not in order:
            order.append(key)
        if para is None:
            sec["head"] = _tidy(body)
        else:
            sec["paras"][para] = _tidy(body)
        current = key
    book = {}
    for key in order:
        sec = sections[key]
        verses = dict(sec["paras"])
        if not verses:                        # (a saying, or a short piece: its heading line is the text)
            verses = {"1": sec["head"] or ""}
        elif sec["head"]:
            first = next(iter(verses))
            verses[first] = f"*{sec['head']}*\n{verses[first]}"
        book[key] = {k: v for k, v in verses.items() if v}
    # Radi's conclusion, after his introduction in chapter 0, a paragraph a verse
    paras = [_tidy(p) for p in re.split(r"(?<=[.\]])\s*\n(?=[A-Z])", conclusion.strip()) if p.strip()]
    expect(bool(paras) and paras[0].startswith("I come here to the end"), f"conclusion {paras[:1]}")
    intro = book["0"]
    for i, p in enumerate(paras):
        intro[str(len(intro) + 1)] = ("*Raḍī’s Conclusion*\n" if i == 0 else "") + p
    return book


CACHE = Path(__file__).resolve().parent / ".cache" / "shia"
SAHIFA_END = r"^\s*(The )?Treatise on Rights|^\s*Risalat al-Huquq"     # (what follows the supplications)


def _pages(pdf: Path) -> list:
    """The PDF's pages' text, saved after the first reading (this one is slow to parse)."""
    CACHE.mkdir(parents=True, exist_ok=True)
    cached = CACHE / (pdf.stem + ".json")
    if cached.exists():
        return json.loads(cached.read_text(encoding="utf-8"))
    import pypdf
    pages = [(p.extract_text() or "") for p in pypdf.PdfReader(str(pdf)).pages]
    cached.write_text(json.dumps(pages, ensure_ascii=False), encoding="utf-8")
    return pages


def sahifa() -> dict:
    """The Sahifa Sajjadiyya in William Chittick's translation (The Psalms of Islam, 1988), al-islam.org's edition:
    its preface on how the book came down (chapter 0), the 54 supplications, and the supplications added to it
    after them, a chapter each by number, verses by the translator's numbers ("1- Praise belongs to God,"), its
    lines as he sets them. The Arabic, the notes and the editors' introduction are left out."""
    lines = []
    for page in _pages(SAHIFA_PDF):
        for line in page.split("\n"):
            if re.search(r"[؀-ۿﭐ-﻿]", line) or not line.strip():
                continue                                    # (the Arabic)
            lines.append(line.rstrip())
    start = next(i for i, l in enumerate(lines) if re.match(r"1-\s*The greatest sayyid", l))
    begins = next(i for i, l in enumerate(lines) if i > start and l.strip() == "Supplications")
    book, chapter, verse, in_note, title = {"0": {}}, "0", None, False, None
    for i, line in enumerate(lines[start:], start):
        if line.startswith("Source URL:") or re.match(SAHIFA_END, line):
            break
        m = re.match(r"^(\d+)\) (.+)$", line)
        if m and i > begins and int(m.group(1)) == (0 if chapter == "0" else int(chapter)) + 1:
            chapter, verse, in_note, title = m.group(1), None, False, m.group(2).strip()
            book[chapter] = {}
            continue
        v = re.match(r"^(\d+)-\s*(.*)$", line) or (re.match(r"^(1)\.\s+(.*)$", line) if verse is None else None)
        if v and (verse is None and v.group(1) == "1" or verse and int(v.group(1)) == int(verse) + 1):
            verse, in_note = v.group(1), False
            text = v.group(2)
            if verse == "1" and title:
                # (its heading, then al-Hasani's; each joined up -- the PDF breaks them -- and in italics)
                rows = [re.sub(r"(?<=[A-Za-z'’])\d{1,2}$", "", r.strip()) for r in title.split("\n")  # (note marks)
                        if r.strip() and not re.match(r"\d+\) ", r.strip())]   # (the heading again, twice)
                rows = [re.sub(r"(?<=\w)- (?=[A-Z])", "-", r) for r in rows]   # ("Fast- Breaking")
                at = next((i for i, r in enumerate(rows) if i and re.match(
                    r"(His |When |After |A |One of |In |He |Among |This |It )", r)), len(rows))
                head, sub = (re.sub(r"(?<=\w)- (?=[A-Z])", "-", " ".join(x)) for x in (rows[:at], rows[at:]))
                parts = [p for p in (head, sub) if p.strip()]
                text = "\n".join(f"*{p.strip()}*" for p in parts) + "\n" + text
            book[chapter][verse] = text
            continue
        if re.match(r"^\d+\. ", line):                      # (a note, to the next verse or heading)
            in_note = True
            continue
        if verse is None and title and chapter != "0" and not in_note:    # (its heading in al-Hasani's words)
            title += "\n" + line.strip()
            continue
        if in_note or verse is None:
            continue
        book[chapter][verse] += "\n" + line.strip()
    import unicodedata
    for chapter, verses in book.items():
        for k, t in verses.items():
            t = unicodedata.normalize("NFKC", t)                                      # ("ﬁ" ligatures)
            t = re.sub(r"(?<=[A-Za-z.,;:!?'’”)\]])\d{1,3}(?=[\s.,;:’”)]|$)", "", t)     # (the note marks)
            lines = [re.sub(r"\s+", " ", l).strip() for l in t.split("\n")]
            lines = [l for l in lines if l and l != "."]
            if chapter == "0":                  # (the preface is prose: the PDF's line ends aren't the text's)
                verses[k] = " ".join(lines)
            else:
                verses[k] = "\n".join(lines)
    return {c: v for c, v in book.items() if v}


def write(name: str, file: str, source: str, chapters: dict) -> None:
    path = ROOT / "data" / "quran" / file
    path.write_text(json.dumps({"source": source, "books": {name: chapters}}, ensure_ascii=False, indent=1),
                    encoding="utf-8")
    print(f"  {name}: {len(chapters)} chapters, {sum(map(len, chapters.values()))} passages -> {path.name}")


if __name__ == "__main__":
    only = sys.argv[1:]
    if not only or "nahj" in only:
        book = nahj()
        counts = {p: sum(1 for k in book if k.split(".")[0] == p) for p in ("1", "2", "3")}
        print("  orations, letters, sayings:", counts, "intro" if "0" in book else "no intro")
        expect(counts == {"1": 238, "2": 79, "3": 446}, f"counts {counts}")
        write("Nahj al-Balagha", "nahj_al_balagha.json", "trans. Tahera Qutbuddin (2024)", book)
    if not only or "sahifa" in only:
        book = sahifa()
        print("  supplications:", [k for k in book][:3], "...", list(book)[-3:])
        expect(all(str(n) in book for n in range(1, 55)), "a supplication of the 54 missing")
        write("Sahifa Sajjadiyya", "sahifa_sajjadiyya.json", "trans. William C. Chittick (1988)", book)
