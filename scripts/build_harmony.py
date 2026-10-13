"""
Build data/harmony.json for !harmony from A. T. Robertson's "A Harmony of the
Gospels for Students of the Life of Christ" (1922, Project Gutenberg #36264):
its analytical outline lists the life of Christ in 184 sections, each with the
passages in Matthew, Mark, Luke and John that tell it.

    python scripts/build_harmony.py
"""
import json
import re
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
URL = "https://www.gutenberg.org/cache/epub/36264/pg36264.txt"
CACHE = ROOT / "scripts" / ".cache" / "harmony" / "pg36264.txt"
OUT = ROOT / "data" / "harmony.json"
UA = {"User-Agent": "ScriptureBot/1.0 (https://github.com/Ante-Luvian/scripture-bot)"}

BOOKS = {"Matt.": "Matthew", "Mark": "Mark", "Luke": "Luke", "John": "John", "Acts": "Acts",
         "1 Cor.": "1 Corinthians"}


def text() -> str:
    if not CACHE.exists():
        CACHE.parent.mkdir(parents=True, exist_ok=True)
        CACHE.write_bytes(urllib.request.urlopen(urllib.request.Request(URL, headers=UA), timeout=60).read())
    return CACHE.read_text(encoding="utf-8")


def outline(full: str) -> list:
    """The 'ANALYTICAL OUTLINE' lines, up to the harmony itself."""
    start = full.index("ANALYTICAL OUTLINE OF THE HARMONY")
    lines = full[start:].splitlines()
    out = []
    for line in lines[1:]:
        if re.match(r"\s*(PART I:|PART I\b)", line) and out and any("Sect. 184" in l for l in out):
            break
        out.append(line)
        if re.match(r"\s*Sect\. 184\b", line):
            # keep its title and references, then stop
            continue
        if any("Sect. 184" in l for l in out[:-1]) and line.strip().endswith("."):
            break
    return out


_REF = re.compile(r"(Matt\.|Mark|Luke|John|Acts|1 Cor\.)\s+([\d:,\-\s]+?)(?=;|\.$|$| and )")


def parse_refs(raw: str) -> list:
    """'Mark 1:2-6; Matt. 3:1-6; Luke 3:3-6.' -> [{"book": "Mark", "ref": "Mark 1:2-6"}, ...]"""
    out = []
    # a long section lists its sub-parts after the whole ("Luke 8:4-18. _Introduction to the Group_ ...")
    raw = re.split(r"\.\s+(?=[_(])", raw.replace("–", "-"))[0].rstrip(".")
    for part in re.split(r";\s*", raw):
        part = re.sub(r"^(?:cf\.|also)\s+", "", part.strip(), flags=re.I)
        m = re.match(r"(Matt\.|Mark|Luke|John|Acts|1 Cor\.)\s+(\d.*)$", part)
        if not m:
            continue
        book = BOOKS[m.group(1)]
        out.append({"book": book, "ref": f"{book} {m.group(2).strip().rstrip('.')}"})
    return out


def sentence_case(title: str, proper: set) -> str:
    words = title.lower().split()
    out = []
    for i, w in enumerate(words):
        core = re.sub(r"[^a-z']", "", w).replace("'s", "")
        if i == 0 or core in proper or out[-1].endswith("."):
            w = w[0].upper() + w[1:] if w[0].isalpha() else w[0] + w[1:2].upper() + w[2:]
        out.append(w)
    return " ".join(out)


def proper_words() -> set:
    """Words the KJV Gospels only ever capitalise: names, places, God."""
    kjv = json.loads((ROOT / "data" / "kjv" / "kjv_canon.json").read_text(encoding="utf-8"))["books"]
    upper, lower = set(), set()
    for book in ("Matthew", "Mark", "Luke", "John", "Acts"):
        for ch in kjv[book].values():
            for v in ch.values():
                for i, w in enumerate(re.findall(r"[A-Za-z']+", v)):
                    w = w.replace("'s", "")
                    (upper if w[0].isupper() else lower).add(w.lower())
    return (upper - lower) | {"god", "christ", "jesus", "messiah", "logos", "baptist", "john", "lord", "jews",
                              "pharisees", "sadducees", "galilee", "judea", "samaria", "jerusalem", "passover",
                              "sabbath", "satan", "son", "magi", "mount", "olives", "virgin", "luke", "matthew",
                              "mark", "caesarea", "zacchaeus", "sunday", "friday", "saturday", "tuesday",
                              "wednesday", "thursday", "monday", "perea", "perean", "judean", "galilean",
                              "pharisaic", "roman", "romans", "logia", "baptist's",
                              "messiahship", "sanhedrin", "transfiguration", "temple",
                              "tabernacles", "hermon", "jewish", "aenon", "salim", "decapolis", "tyre", "sidon", "nain", "cana"}


def main():
    full = text()
    proper = proper_words()
    sections, part, cur = [], "", None
    lines = outline(full)
    i = 0
    while i < len(lines):
        line = lines[i].rstrip()
        m_part = re.match(r"\s*PART ([IVXL]+):\s*(.+)", line)
        m_sect = re.match(r"\s*Sect\. (\d+[a-z]?):\s*(.+)", line)
        if m_part:
            heading = m_part.group(2).strip()
            nxt = lines[i + 1].strip() if i + 1 < len(lines) else ""
            if nxt and nxt.isupper() and not nxt.startswith("SECT"):     # "…IN DISTRICTS AROUND / GALILEE"
                heading += " " + nxt
            part = sentence_case(heading, proper)
        elif m_sect:
            title = m_sect.group(2).strip()
            j = i + 1
            # a long title runs on, indented further than the references
            while j < len(lines) and lines[j].startswith("            ") and lines[j].strip() and \
                    not re.match(r"\s*(Matt\.|Mark|Luke|John)\s+\d", lines[j]):
                title += " " + lines[j].strip()
                j += 1
            # the whole section's passages sit ten spaces in; its sub-parts (the Sermon on the
            # Mount's) are indented further and are skipped
            refs = ""
            while j < len(lines) and lines[j].strip() and not re.match(r"\s*(Sect\.|PART|SECTIONS)", lines[j]):
                if re.match(r" {10}\S", lines[j]) and not refs.rstrip().endswith("."):
                    refs += " " + lines[j].strip()
                j += 1
            cur = {"section": m_sect.group(1), "part": part, "title": sentence_case(title, proper),
                   "refs": parse_refs(refs.strip())}
            sections.append(cur)
            i = j
            continue
        i += 1
    OUT.write_text(json.dumps({"source": "A. T. Robertson, A Harmony of the Gospels for Students of the Life "
                                         "of Christ (1922)", "sections": sections}, ensure_ascii=False, indent=1),
                   encoding="utf-8")
    print(f"{len(sections)} sections; {sum(1 for s in sections if not s['refs'])} without references")
    for s in sections:
        if not s["refs"]:
            print("  no refs:", s["section"], s["title"])


if __name__ == "__main__":
    sys.exit(main())
