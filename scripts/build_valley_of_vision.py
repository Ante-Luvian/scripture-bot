"""
Builds data/devotions/valley_of_vision.json for !vov: the Puritan prayers collected as The Valley
of Vision, from the epub the owner supplied (scripts/sources/valley_of_vision.epub, gitignored).
The prayers are adapted from the Puritans' own writings, so they are credited to them, not to
the collection's editor. Each prayer keeps its lines; a line the book indents (a continuation)
is indented with em spaces.

    python scripts/build_valley_of_vision.py
"""
import html
import json
import re
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCE = Path(__file__).resolve().parent / "sources" / "valley_of_vision.epub"
OUT = ROOT / "data" / "devotions" / "valley_of_vision.json"
SMALL = {"a", "an", "and", "as", "at", "by", "for", "from", "in", "into", "of", "on", "or", "the", "to", "with"}


def text(fragment: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", "", fragment))).strip()


def title_case(s: str) -> str:
    words = s.lower().split()
    return " ".join(w if (i and w in SMALL) else w[:1].upper() + w[1:] for i, w in enumerate(words))


def main():
    z = zipfile.ZipFile(SOURCE)
    opf = z.read("OEBPS/content.opf").decode("utf-8")
    manifest = dict(re.findall(r'<item[^>]*id="([^"]+)"[^>]*href="([^"]+)"', opf))
    manifest.update({i: h for h, i in re.findall(r'<item[^>]*href="([^"]+)"[^>]*id="([^"]+)"', opf)})
    order = [manifest[i] for i in re.findall(r'<itemref[^>]*idref="([^"]+)"', opf)]
    sections, prayers, section = [], [], None
    for href in order:
        page = z.read("OEBPS/" + href).decode("utf-8", "replace")
        h2 = re.search(r"(?is)<h2[^>]*>(.*?)</h2>", page)
        if h2:
            name = text(h2.group(1))
            if re.match(r"(?i)preface|bibliography|index|contents", name):
                section = None
                continue
            name = re.sub(r"^\d+\.\s*", "", name).replace("Introductory: The Valley of Vision", "Introductory")
            section = {"n": len(sections) + 1, "title": name}
            sections.append(section)
        h3 = re.search(r"(?is)<h3[^>]*>(.*?)</h3>", page)
        if not (h3 and section):
            continue
        lines = []
        for cls, line in re.findall(r'(?is)<p class="([^"]*)"[^>]*>(.*?)</p>', page):
            line = text(line)
            if not line:
                continue
            indent = 0 if cls in ("first_line", "poetry_") else (2 if re.search(r"1\dmm|2\dmm", cls) else 1)
            lines.append(" " * indent + line)
        if lines:
            prayers.append({"n": len(prayers) + 1, "title": title_case(text(h3.group(1))), "section": section["n"],
                            "lines": lines})
    for s in sections:
        s["count"] = sum(p["section"] == s["n"] for p in prayers)
    sections = [s for s in sections if s["count"]]
    assert len(prayers) >= 180 and len(sections) >= 10, (len(prayers), len(sections))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"source": "Puritan prayers and devotions, as collected in The Valley of Vision",
                               "sections": sections, "prayers": prayers}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)}: {len(prayers)} prayers in {len(sections)} sections")
    for s in sections:
        print(f"  {s['n']}. {s['title']}: {s['count']}")


if __name__ == "__main__":
    main()
