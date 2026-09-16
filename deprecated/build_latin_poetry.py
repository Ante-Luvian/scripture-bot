#!/usr/bin/env python3
"""
build_latin_poetry.py — convert Latin Virgil and Ovid from canonical-latinLit to JSON.

Run from your scripture bot directory:
    python build_latin_poetry.py

Reads from: canonical-latinLit/data/
  phi0690/phi001/ — Virgil, Eclogues   (lat)
  phi0690/phi002/ — Virgil, Georgics   (lat)
  phi0690/phi003/ — Virgil, Aeneid     (lat)
  phi0474/phi027/ — Ovid, Metamorphoses (lat)

Writes to: data/poetry/
  eclogues_latin.json
  georgics_latin.json
  aeneid_latin.json
  metamorphoses_latin.json

All output files use the same schema as iliad_greek.json:
  { "source": "...", "lang": "lat",
    "books": { "1": { "1": "Arma virumque...", "2": "..." } } }
"""

import json, re, sys, xml.etree.ElementTree as ET
from pathlib import Path

NS = '{http://www.tei-c.org/ns/1.0}'

WORKS = [
    {
        "name":    "Eclogues (Latin)",
        "phi_grp": "phi0690",
        "phi_wk":  "phi001",
        "outfile": "data/poetry/eclogues_latin.json",
        "source":  "Virgil, Eclogues. Ed. J.B. Greenough. Boston: Ginn & Co., 1895. Perseus Digital Library.",
        "abbrev":  "Ecl.",
        # Eclogues have no books — each eclogue is a poem numbered 1-10
        # The XML uses subtype="poem" or subtype="chapter" — we treat each as a "book"
        "subtype_hints": ["poem", "chapter", "section", "Book", "book"],
    },
    {
        "name":    "Georgics (Latin)",
        "phi_grp": "phi0690",
        "phi_wk":  "phi002",
        "outfile": "data/poetry/georgics_latin.json",
        "source":  "Virgil, Georgics. Ed. J.B. Greenough. Boston: Ginn & Co., 1895. Perseus Digital Library.",
        "abbrev":  "G.",
        "subtype_hints": ["Book", "book", "chapter"],
    },
    {
        "name":    "Aeneid (Latin)",
        "phi_grp": "phi0690",
        "phi_wk":  "phi003",
        "outfile": "data/poetry/aeneid_latin.json",
        "source":  "Virgil, Aeneid. Ed. J.B. Greenough. Boston: Ginn & Co., 1900. Perseus Digital Library.",
        "abbrev":  "Aen.",
        "subtype_hints": ["Book", "book", "chapter"],
    },
    {
        "name":    "Metamorphoses (Latin)",
        "phi_grp": "phi0474",
        "phi_wk":  "phi027",
        "outfile": "data/poetry/metamorphoses_latin.json",
        "source":  "Ovid, Metamorphoses. Ed. Hugo Magnus. Gotha: Friedr. Andr. Perthes, 1892. Perseus Digital Library.",
        "abbrev":  "Met.",
        "subtype_hints": ["Book", "book", "chapter"],
    },
]


def find_base_dir() -> Path | None:
    cwd = Path.cwd()
    for candidate in [
        cwd / "canonical-latinLit",
        cwd / "canonical-latinLit-master",
        Path(r"C:/Users/chris/OneDrive/Desktop/scripture bot/canonical-latinLit"),
    ]:
        if candidate.exists() and (candidate / "data").exists():
            return candidate
    return None


def find_xml(base_dir: Path, phi_grp: str, phi_wk: str) -> Path | None:
    work_dir = base_dir / "data" / phi_grp / phi_wk
    if not work_dir.exists():
        print(f"    Directory not found: {work_dir}")
        return None
    # Try dot-separated first (like canonical-greekLit), then underscore
    for sep in [".", "_"]:
        for variant in ["lat1", "lat2", "lat3", "lat"]:
            if sep == ".":
                p = work_dir / f"{phi_grp}.{phi_wk}.perseus-{variant}.xml"
            else:
                p = work_dir / f"{phi_grp}_{phi_wk}_perseus-{variant}.xml"
            if p.exists():
                return p
    # Fallback glob
    matches = sorted(work_dir.glob("*.xml"))
    # Prefer lat files over eng files
    lat = [m for m in matches if "lat" in m.name and "eng" not in m.name]
    return lat[0] if lat else (matches[0] if matches else None)


def extract_lines(xml_path: Path, subtype_hints: list[str]) -> dict[str, dict[str, str]]:
    """
    Parse a Latin poetry XML and return {book_str: {line_str: text}}.
    Handles multiple possible XML structures across different works.
    """
    try:
        tree = ET.parse(xml_path)
    except ET.ParseError as e:
        print(f"    XML error: {e}")
        return {}

    root = tree.getroot()

    # ── Strategy 1: find textpart divs with line children ─────────────────────
    # Try each subtype hint in order
    books: dict[str, dict[str, str]] = {}

    for subtype in subtype_hints:
        divs = (root.findall(f'.//{NS}div[@type="textpart"][@subtype="{subtype}"]') or
                root.findall(f'.//{NS}div[@subtype="{subtype}"]'))
        if not divs:
            continue

        for div in divs:
            bn = div.get("n", "1")
            lines_el = div.findall(f".//{NS}l")
            if not lines_el:
                continue
            book_lines: dict[str, str] = {}
            for l in lines_el:
                n = l.get("n")
                if not n or not n.isdigit():
                    continue
                text = "".join(l.itertext()).strip()
                # Strip footnote markers and editorial brackets
                text = re.sub(r"\[.*?\]", "", text)
                text = re.sub(r"\s+", " ", text).strip()
                if text:
                    book_lines[n] = text
            if book_lines:
                books[bn] = book_lines

        if books:
            break  # found a working subtype

    # ── Strategy 2: flat list of <l> elements (no book divs) ──────────────────
    if not books:
        all_lines = root.findall(f".//{NS}l")
        if all_lines:
            book_lines: dict[str, str] = {}
            for l in all_lines:
                n = l.get("n")
                if not n or not n.isdigit():
                    continue
                text = "".join(l.itertext()).strip()
                text = re.sub(r"\[.*?\]", "", text)
                text = re.sub(r"\s+", " ", text).strip()
                if text:
                    book_lines[n] = text
            if book_lines:
                books["1"] = book_lines

    return books


def main():
    base_dir = find_base_dir()
    if base_dir is None:
        print(f"ERROR: Cannot find canonical-latinLit from {Path.cwd()}")
        print("Make sure you have cloned it and are running from your bot directory.")
        sys.exit(1)

    print(f"Found: {base_dir}\n")

    out_dir = Path("data") / "poetry"
    out_dir.mkdir(parents=True, exist_ok=True)

    for work in WORKS:
        print(f"=== {work['name']} ===")
        xml_path = find_xml(base_dir, work["phi_grp"], work["phi_wk"])

        if xml_path is None:
            print(f"  MISSING — skipping\n")
            continue

        print(f"  File: {xml_path.name}")
        books = extract_lines(xml_path, work["subtype_hints"])

        if not books:
            print(f"  WARNING: no lines extracted — check XML structure\n")
            continue

        total = sum(len(b) for b in books.values())
        for bn in sorted(books.keys(), key=lambda x: int(x) if x.isdigit() else 0):
            b = books[bn]
            first = list(b.values())[0][:60] if b else ""
            print(f"  Book {bn:>2}: {len(b):>4} lines   {first!r}")

        payload = {
            "source": work["source"],
            "abbrev": work["abbrev"],
            "lang":   "lat",
            "books":  books,
        }

        out_path = Path(work["outfile"])
        out_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False),
                            encoding="utf-8")
        print(f"  → {total:,} lines saved to {out_path}\n")


if __name__ == "__main__":
    main()
