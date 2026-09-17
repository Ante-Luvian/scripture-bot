"""
Build script: converts several core Bahá'í texts from the Bahá'í World
Centre's own 1990s etext server (mirrored today at
https://archive.sacred-texts.com/bhi/) into data/bahai/*.json.

License basis (verified directly, https://archive.sacred-texts.com/bhi/cnote.txt):
"The entire contents of the Baha'i World Centre Etext Server are
copyrighted by the Baha'i International Community, Copyright (c) 1994,
All Rights Reserved... They may be freely redistributed in their
entirety provided that this copyright notice is not removed. These
documents may not be sold for profit or incorporated in commercial
documents without the written permission of the Baha'i International
Community." This is a direct, explicit grant from the actual rights
holder (not an age-based public-domain claim) covering exactly this use:
a free, non-commercial redistribution. Each file's own header names its
specific print edition (quoted in the "source" field below).

Texts built here (all still-numbered/citable units, faithfully
preserved from the electronic text -- no numbering invented):
  - The Hidden Words of Bahá'u'lláh (Arabic, Persian) -- numbered 1-N each
  - Gleanings from the Writings of Bahá'u'lláh -- roman-numeral sections I-CLXVI
  - Prayers and Meditations by Bahá'u'lláh -- roman-numeral prayers I-CLXXXIV
  - Some Answered Questions ('Abdu'l-Bahá, trans. Laura Clifford Barney,
    1908) -- 84 numbered chapters
  - Kitáb-i-Íqán (The Book of Certitude) -- Part One / Part Two, stored
    as two whole-part blocks (this etext has no finer paragraph markers)
  - Epistle to the Son of the Wolf -- single continuous work, one block

Markup notes (from https://archive.sacred-texts.com/bhi/format.txt):
  +Pn   = start of published page n (dropped)
  +Fn   = footnote n, both the inline reference and the footnote's own
          text are tagged this way (both dropped -- not needed for
          verse-lookup use)
  &word = a word that had a diacritic stripped for plain ASCII (the
          ampersand itself is dropped, the plain-ASCII spelling is kept)

Downloads its own source -- run from anywhere:
    python deprecated/build_bahai_worldcentre.py
"""
import json
import re
import time
import urllib.request
from pathlib import Path

BASE = "https://archive.sacred-texts.com/bhi"
OUT_DIR = Path(__file__).parent.parent / "data" / "bahai"

SOURCE_NOTE = "Bahá'í World Centre"


def _fetch(path: str) -> str:
    req = urllib.request.Request(
        f"{BASE}/{path}",
        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", errors="replace").replace("\r\n", "\n").replace("\r", "\n")


def _clean(t: str) -> str:
    t = re.sub(r"\+F\d+", "", t)
    t = re.sub(r"\+P\d+\{?~?", "", t)
    t = re.sub(r"&", "", t)
    t = re.sub(r"\{~", "", t)
    t = re.sub(r"[ \t]+", " ", t)
    t = re.sub(r" *\n *", " ", t)
    t = re.sub(r"\s{2,}", " ", t)
    return t.strip()


def _clean_block(t: str) -> str:
    """Like _clean but keeps paragraph breaks (for whole-part blocks)."""
    t = re.sub(r"\+F\d+[^\n]*", "", t)
    t = re.sub(r"\+P\d+\{?~?", "", t)
    t = re.sub(r"&", "", t)
    t = re.sub(r"\{~", "", t)
    t = re.sub(r"[ \t]+", " ", t)
    t = re.sub(r" *\n *", " ", t)
    t = re.sub(r"\n{2,}", "\n\n", t)
    return t.strip()


def _roman_to_int(s: str) -> int:
    vals = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100, "D": 500, "M": 1000}
    total, prev = 0, 0
    for ch in reversed(s):
        v = vals[ch]
        total = total - v if v < prev else total + v
        prev = max(prev, v)
    return total


def build_hidden_words():
    data = _fetch("bahaullah/hw.txt")
    ar_start = data.find("From the Arabic")
    pe_start = data.find("From the Persian")
    arabic_block, persian_block = data[ar_start:pe_start], data[pe_start:]

    def split_items(block):
        parts = re.split(r"\n\s*(\d{1,3})\.\s+", block)
        items = {}
        for i in range(1, len(parts) - 1, 2):
            items[parts[i]] = {"1": _clean(parts[i + 1])}
        return items

    ar_items, pe_items = split_items(arabic_block), split_items(persian_block)
    print(f"Hidden Words (Arabic): {len(ar_items)} items")
    print(f"Hidden Words (Persian): {len(pe_items)} items")

    (OUT_DIR / "hidden_words_arabic.json").write_text(json.dumps({
        "source": f"The Hidden Words of Bahá'u'lláh, Part I: From the Arabic -- trans. Shoghi Effendi, {SOURCE_NOTE}",
        "books": {"The Hidden Words (Arabic)": ar_items},
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    (OUT_DIR / "hidden_words_persian.json").write_text(json.dumps({
        "source": f"The Hidden Words of Bahá'u'lláh, Part II: From the Persian -- trans. Shoghi Effendi, {SOURCE_NOTE}",
        "books": {"The Hidden Words (Persian)": pe_items},
    }, ensure_ascii=False, indent=2), encoding="utf-8")


def build_gleanings():
    data = _fetch("bahaullah/gwb.txt")
    body = data[re.search(r"\n\s*I\.\s+", data).start():]
    parts = re.split(r"\n\s*([IVXLCDM]{1,8})\.\s+(?=[A-Z])", body)
    items = {}
    for i in range(1, len(parts) - 1, 2):
        items[str(_roman_to_int(parts[i]))] = {"1": _clean(parts[i + 1])}
    print(f"Gleanings: {len(items)} sections")
    (OUT_DIR / "gleanings.json").write_text(json.dumps({
        "source": f"Gleanings from the Writings of Bahá'u'lláh -- trans. Shoghi Effendi, {SOURCE_NOTE}",
        "books": {"Gleanings from the Writings of Baha'u'llah": items},
    }, ensure_ascii=False, indent=2), encoding="utf-8")


def build_prayers_and_meditations():
    data = _fetch("bahaullah/pm.txt")
    body = data[re.search(r"\n\s*I\s*\n", data).start():]
    parts = re.split(r"\n\s*([IVXLCDM]{1,8})\s*\n", body)
    items = {}
    for i in range(1, len(parts) - 1, 2):
        text = _clean(parts[i + 1])
        if text:
            items[str(_roman_to_int(parts[i]))] = {"1": text}
    print(f"Prayers and Meditations: {len(items)} prayers")
    (OUT_DIR / "prayers_and_meditations.json").write_text(json.dumps({
        "source": f"Prayers and Meditations by Bahá'u'lláh -- trans. Shoghi Effendi, {SOURCE_NOTE}",
        "books": {"Prayers and Meditations": items},
    }, ensure_ascii=False, indent=2), encoding="utf-8")


def build_some_answered_questions():
    data = _fetch("abdulbaha/saq01.txt")
    body = data[data.find("Part One"):]
    # Chapter headers are a bare number alone on its own line (surrounded by
    # blank lines), immediately followed by an all-caps title (which may
    # itself span more than one line, so it isn't captured separately).
    parts = re.split(r"\n[ \t]*(\d{1,3})[ \t]*\n(?=\s*\n\s*[A-Z&])", body)
    items = {}
    for i in range(1, len(parts) - 1, 2):
        num, chunk = parts[i], parts[i + 1]
        # Strip the title lines (all-caps lines) off the front of the chunk.
        lines = chunk.split("\n")
        j = 0
        while j < len(lines) and (not lines[j].strip() or lines[j].strip().lstrip("&") == lines[j].strip().lstrip("&").upper()):
            j += 1
        text = _clean("\n".join(lines[j:]))
        if text:
            items[num] = {"1": text}
    print(f"Some Answered Questions: {len(items)} chapters")
    (OUT_DIR / "some_answered_questions.json").write_text(json.dumps({
        "source": f"Some Answered Questions -- 'Abdu'l-Bahá, trans. Laura Clifford Barney (1908), {SOURCE_NOTE}",
        "books": {"Some Answered Questions": items},
    }, ensure_ascii=False, indent=2), encoding="utf-8")


def build_iqan():
    data = _fetch("bahaullah/iqa.txt")
    p1 = data.find("PART ONE")
    p2 = data.find("PART TWO")
    part_one, part_two = data[p1:p2], data[p2:]
    items = {
        "1": {"1": _clean_block(part_one[part_one.find("\n", 20):])},
        "2": {"1": _clean_block(part_two[part_two.find("\n", 20):])},
    }
    print(f"Kitab-i-Iqan: Part One {len(items['1']['1'])} chars, Part Two {len(items['2']['1'])} chars")
    (OUT_DIR / "kitab_i_iqan.json").write_text(json.dumps({
        "source": f"Kitáb-i-Íqán (The Book of Certitude) -- trans. Shoghi Effendi, {SOURCE_NOTE}",
        "books": {"Kitab-i-Iqan": items},
    }, ensure_ascii=False, indent=2), encoding="utf-8")


def build_esw():
    data = _fetch("bahaullah/esw.txt")
    body = data[data.find("In the name of God"):]
    text = _clean_block(body)
    print(f"Epistle to the Son of the Wolf: {len(text)} chars")
    (OUT_DIR / "epistle_to_son_of_wolf.json").write_text(json.dumps({
        "source": f"Epistle to the Son of the Wolf -- Bahá'u'lláh, trans. Shoghi Effendi, {SOURCE_NOTE}",
        "books": {"Epistle to the Son of the Wolf": {"1": {"1": text}}},
    }, ensure_ascii=False, indent=2), encoding="utf-8")


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    build_hidden_words()
    time.sleep(1)
    build_gleanings()
    time.sleep(1)
    build_prayers_and_meditations()
    time.sleep(1)
    build_some_answered_questions()
    time.sleep(1)
    build_iqan()
    time.sleep(1)
    build_esw()


if __name__ == "__main__":
    main()
