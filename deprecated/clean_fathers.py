#!/usr/bin/env python3
"""
clean_fathers.py
----------------
Post-processing cleaner for the patristics JSON files.
Fixes boilerplate pollution without re-fetching anything.

Run from the directory containing the JSON files:
    python3 clean_fathers.py data/patristics/

Or:
    python3 clean_fathers.py  # defaults to data/patristics/
"""

import json, re, sys, pathlib

# ── Boilerplate patterns to strip ─────────────────────────────────────────────

# NewAdvent paywall/promo (exact text)
NA_PROMO = "Please help support the mission of New Advent"

# NewAdvent alternate promo (newer pages with blog posts)
NA_ALTERNATE = "How Catholic Underground"

# NewAdvent "Source. Translated by..." attribution lines at para end  
NA_SOURCE = re.compile(r"Source\.\s+Translated by.*?newadvent\.org.*", re.DOTALL)

# Pearse/CCEL citation headers — start with author name + year
PEARSE_CITATION = re.compile(
    r"^(S\.\s*Ephrai?m|Cyril of Alexandria|Gregory (the Great|of Nyssa|Naz)|"
    r"Basil|Origen|Athanasius|Augustine|Jerome|Leo|John of Damascus)\b.*?"
    r"(pp?\.\s*[\d\-–]+|LFC \d+|\(\d{4}\))[^.]*\.",
    re.IGNORECASE
)

# Gregory Great Dialogues Pearse citation (shorter form)
GREG_DIAL = re.compile(r"^Gregory the Great, Dialogues \(\d{4}\) Book \d\. pp\.")

# Basil Address to Young Men Yale citation
YALE_CITATION = re.compile(r"^Frederick Morgan PADELFORD|^Yale Studies in Engl")

# Augustine Enchiridion front matter
ENCHIR_FRONT = re.compile(
    r"^(Enchiridion On Faith|Professor of Theology|Perkins School|"
    r"Library of Congress|Southern Methodist|Dallas, Texas)",
    re.IGNORECASE
)

# Life of Macrina Pearse citation
MACRINA_CITE = re.compile(r"^Gregory of Nyssa, Life of St\. Macrina")

# Jerome Commentary on Daniel Pearse citation
JEROME_DAN = re.compile(r"^St\. Jerome, Commentary on Daniel")

# Origen On Prayer citation
ORIGEN_PRAY = re.compile(r"^Origen, On Prayer")

# Augustine Enchiridion (Pearse) title header
AUG_ENCHIR_TITLE = re.compile(r"^St\. Augustine, Enchiridion")

def is_boilerplate(text: str, work_name: str = "", para_num: str = "1") -> bool:
    """Return True if this paragraph is known boilerplate to remove."""
    t = text.strip()

    # NewAdvent promo (always para 1 from NA pages)
    if t.startswith(NA_PROMO) or t.startswith(NA_ALTERNATE):
        return True

    # Pearse bibliographic citation headers (typically para 1)
    if para_num in ("1", "2") and PEARSE_CITATION.match(t):
        return True
    if GREG_DIAL.match(t):
        return True
    if YALE_CITATION.match(t):
        return True
    if MACRINA_CITE.match(t):
        return True
    if JEROME_DAN.match(t):
        return True
    if ORIGEN_PRAY.match(t):
        return True
    if AUG_ENCHIR_TITLE.match(t):
        return True

    # Enchiridion front matter (series of short paras at start)
    if "Enchiridion" in work_name and ENCHIR_FRONT.match(t):
        return True

    # Ephrem Prose Refutations citation (every work)
    if t.startswith("S. Ephrai") and "Prose Refutations" in t:
        return True

    # Cyril citation variants
    if t.startswith("Cyril of Alexandria,") and ("LFC" in t or "Oxford" in t or "pp." in t):
        return True

    # Augustine Enchiridion table of contents line
    if "Enchiridion" in work_name and re.match(r"^\d+\.\s+The\s+", t):
        # these are TOC entries like "1. The Occasion and Purpose..."
        if len(t) < 200 and t.count("\n") == 0:
            # Only strip if it looks like a short TOC line
            pass  # keep — might be actual content

    return False


def strip_inline_section_numbers(text: str) -> str:
    """
    Optionally strip leading section numbers from paragraph text.
    e.g. "1. Great are You..." -> "Great are You..."
    But only if it's a clean number at the very start.
    """
    # Don't strip — the section numbers are useful for the user to see.
    return text


def renumber_paras(para_dict: dict) -> dict:
    """Renumber paragraphs 1..N after removal of boilerplate ones."""
    kept = [(k, v) for k, v in sorted(para_dict.items(), key=lambda x: int(x[0]))
            if v.strip()]
    return {str(i+1): v for i, (_, v) in enumerate(kept)}


def clean_work(work_name: str, chapters: dict) -> dict:
    """Clean all chapters in a single work."""
    cleaned = {}
    for chap_key, para_dict in chapters.items():
        new_paras = {}
        new_idx = 1
        for para_key in sorted(para_dict.keys(), key=lambda x: int(x)):
            text = para_dict[para_key].strip()
            if not text:
                continue
            if is_boilerplate(text, work_name=work_name, para_num=para_key):
                continue
            # Strip inline "Source. Translated by..." tails
            text = NA_SOURCE.sub("", text).strip()
            if text:
                new_paras[str(new_idx)] = text
                new_idx += 1
        if new_paras:
            cleaned[chap_key] = new_paras
    return cleaned


def fix_athanasius_life_of_antony(chapters: dict) -> dict:
    """
    Life of Antony has garbled chapter keys (paragraph numbers from the text).
    Collapse all content into sequential numbered chapters.
    """
    # Gather all paras across the bogus chapter keys
    all_paras = []
    for bogus_key in sorted(chapters.keys(), key=lambda x: int(x)):
        for para_key in sorted(chapters[bogus_key].keys(), key=lambda x: int(x)):
            text = chapters[bogus_key][para_key].strip()
            if text:
                all_paras.append(text)

    if not all_paras:
        return {}

    # Try to split into proper sections using the leading number pattern "N. "
    # The text has embedded section numbers like "7. This was Antony..."
    sections = {}
    sec_num = None
    current_parts = []

    for para in all_paras:
        # Check if para starts with a section number
        m = re.match(r'^(\d+)\.\s+', para)
        if m:
            if sec_num is not None and current_parts:
                sections[str(sec_num)] = {"1": " ".join(current_parts)}
            sec_num = int(m.group(1))
            current_parts = [para]
        else:
            if sec_num is None:
                sec_num = 1
            current_parts.append(para)

    if sec_num is not None and current_parts:
        sections[str(sec_num)] = {"1": " ".join(current_parts)}

    return sections if sections else {"1": {str(i+1): p for i, p in enumerate(all_paras)}}


def fix_enchiridion_structure(chapters: dict) -> dict:
    """
    Enchiridion was scraped as one giant chapter. The text has embedded chapter
    numbers like "CHAPTER I." or "1. The Occasion..." — split on those.
    """
    if not chapters:
        return {}

    # Get all text, already a flat list
    all_paras = []
    if "1" in chapters:
        for pk in sorted(chapters["1"].keys(), key=lambda x: int(x)):
            t = chapters["1"][pk].strip()
            if t:
                all_paras.append(t)

    if not all_paras:
        return {}

    # Find where real content starts (skip front matter)
    start = 0
    for i, p in enumerate(all_paras):
        if re.match(r'^\d+\.\s+[A-Z]', p) and not re.match(r'^\d+\.\s+(The Occasion|The Creed)', p):
            start = i
            break
        # Or starts with "I cannot say" / actual Augustine content
        if p.startswith("I cannot say") or p.startswith("1. I cannot say"):
            start = i
            break

    content_paras = all_paras[start:]

    # Split on numbered section starts "N. text..." or "CHAPTER N"
    sections = {}
    current_sec = None
    current_lines = []

    for para in content_paras:
        # Section number at start: "1. text" or "2. text"
        m = re.match(r'^(\d+)\.\s+(.+)', para, re.DOTALL)
        if m:
            if current_sec is not None and current_lines:
                sections[str(current_sec)] = {"1": " ".join(current_lines)}
            current_sec = int(m.group(1))
            current_lines = [m.group(2).strip()]
        elif re.match(r'^CHAPTER\s+[IVX]+', para, re.IGNORECASE):
            # Skip chapter heading lines
            continue
        else:
            if current_sec is None:
                current_sec = 1
            current_lines.append(para)

    if current_sec is not None and current_lines:
        sections[str(current_sec)] = {"1": " ".join(current_lines)}

    return sections if sections else {"1": {str(i+1): p for i, p in enumerate(content_paras)}}


def fix_gregory_dialogues(chapters: dict) -> dict:
    """
    Dialogues: each book is one giant chapter (1.1, 2.1, 3.1, 4.1).
    The Pearse citation is para 1. After stripping it, renumber.
    Try to split on ## Chapter N style if present in text.
    """
    result = {}
    for bk_key, para_dict in chapters.items():
        bk_num = bk_key.split(".")[0]
        clean_paras = {}
        idx = 1
        for pk in sorted(para_dict.keys(), key=lambda x: int(x)):
            t = para_dict[pk].strip()
            if not t:
                continue
            if GREG_DIAL.match(t):
                continue
            clean_paras[str(idx)] = t
            idx += 1

        if clean_paras:
            # Try to split into chapters based on embedded "Chapter N" markers
            # For now, keep as one big chapter but cleanly numbered
            result[bk_key] = clean_paras
    return result


# ── Main processing ────────────────────────────────────────────────────────────

def process_file(path: pathlib.Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    books = data.get("books", {})
    cleaned_books = {}
    changes = []

    for work_name, chapters in books.items():
        if not chapters:
            cleaned_books[work_name] = chapters
            continue

        # Special cases first
        if work_name == "Life of Antony" and path.stem == "athanasius":
            fixed = fix_athanasius_life_of_antony(chapters)
            cleaned_books[work_name] = fixed
            changes.append(f"  ✓ Life of Antony: restructured ({len(fixed)} sections)")
            continue

        if work_name == "Enchiridion" and path.stem == "augustine":
            fixed = fix_enchiridion_structure(chapters)
            cleaned_books[work_name] = fixed
            changes.append(f"  ✓ Enchiridion: restructured ({len(fixed)} sections)")
            continue

        if work_name == "Dialogues" and path.stem == "gregory_the_great":
            fixed = fix_gregory_dialogues(chapters)
            cleaned_books[work_name] = fixed
            changes.append(f"  ✓ Dialogues: Pearse headers stripped")
            continue

        # Standard cleaning
        original_para_count = sum(len(v) for v in chapters.values())
        cleaned = clean_work(work_name, chapters)
        new_para_count = sum(len(v) for v in cleaned.values())
        removed = original_para_count - new_para_count

        cleaned_books[work_name] = cleaned
        if removed > 0:
            changes.append(f"  ✓ {work_name}: removed {removed} boilerplate paras")

    return {"source": data.get("source", ""), "books": cleaned_books}, changes


def main():
    data_dir = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else pathlib.Path("data/patristics")

    if not data_dir.exists():
        print(f"Directory not found: {data_dir}")
        sys.exit(1)

    json_files = sorted(data_dir.glob("*.json"))
    if not json_files:
        print(f"No JSON files found in {data_dir}")
        sys.exit(1)

    total_changes = 0
    for path in json_files:
        print(f"\n{path.name}")
        result, changes = process_file(path)
        if changes:
            for c in changes:
                print(c)
            total_changes += len(changes)
        else:
            print("  (no boilerplate found)")
        path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\n✓ Done. {total_changes} fixes across {len(json_files)} files.")


if __name__ == "__main__":
    main()
