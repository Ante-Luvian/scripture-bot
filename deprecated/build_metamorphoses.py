#!/usr/bin/env python3
"""
build_metamorphoses.py — scrape Ovid's Metamorphoses from Wikisource.

Two translations:
  1. Garth/Dryden et al. (1717) — data/classical/metamorphoses_garth.json
  2. Golding (1567) — data/classical/metamorphoses_golding.json

URL patterns:
  Garth: https://en.wikisource.org/wiki/Metamorphoses_(tr._Garth,_Dryden,_et_al.)/Book_I  (Roman)
  Golding: https://en.wikisource.org/wiki/Metamorphoses_(tr._Golding)/Book_1               (Arabic)

Citation: Met. 1.1  (book.line) — Ovid's own line numbers are not on the page;
we assign sequential line numbers per book based on couplet position.

Run: python build_metamorphoses.py
"""

import json, re, time, html as html_mod, urllib.request, urllib.error
from pathlib import Path

ROMAN = ["I","II","III","IV","V","VI","VII","VIII","IX","X","XI","XII","XIII","XIV","XV"]

WORKS = [
    {
        "name":    "Metamorphoses (Garth/Dryden)",
        "abbrev":  "Met.",
        "url_tmpl": "https://en.wikisource.org/wiki/Metamorphoses_(tr._Garth,_Dryden,_et_al.)/Book_{roman}",
        "outfile":  "data/classical/metamorphoses_garth.json",
        "books":    15,
        "roman":    True,
        "source":   (
            "Ovid, Metamorphoses. Trans. John Dryden, Alexander Pope, Joseph Addison, "
            "William Congreve, and other eminent hands. Ed. Sir Samuel Garth (1717). "
            "Public domain."
        ),
    },
    {
        "name":    "Metamorphoses (Golding)",
        "abbrev":  "Met.",
        "url_tmpl": "https://en.wikisource.org/wiki/Metamorphoses_(tr._Golding)/Book_{n}",
        "outfile":  "data/classical/metamorphoses_golding.json",
        "books":    15,
        "roman":    False,
        "source":   (
            "Ovid, Metamorphoses. Trans. Arthur Golding (1567). "
            "Public domain. Wikisource."
        ),
    },
]


def _fetch(url: str) -> str:
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (compatible; ScriptureBot/1.0)",
        "Accept": "text/html,application/xhtml+xml",
    })
    with urllib.request.urlopen(req, timeout=20) as r:
        return r.read().decode("utf-8", errors="replace")


def _parse_book(raw: str) -> dict[str, str]:
    """
    Parse couplets from a Wikisource Metamorphoses page.
    Returns {line_range: text}.
    """
    h = re.sub(r"<script[^>]*>.*?</script>", " ", raw, flags=re.S|re.I)
    h = re.sub(r"<style[^>]*>.*?</style>",   " ", h,   flags=re.S|re.I)
    h = re.sub(r"<!--.*?-->",                 " ", h,   flags=re.S)

    # Remove footnote superscripts and LaTeX display-math blocks (used for braces)
    h = re.sub(r"<sup[^>]*>.*?</sup>", "", h, flags=re.S|re.I)
    h = re.sub(r'\{\s*\\displaystyle.*?\}', "", h, flags=re.S)

    # Find main content
    content_m = re.search(r'<div[^>]*id="mw-content-text"[^>]*>(.*)', h, re.S|re.I)
    if content_m:
        h = content_m.group(1)

    # Cut at footer
    for cutoff in ["Retrieved from", "Hidden categories", "printfooter", "mw-hidden-cats"]:
        idx = h.find(cutoff)
        if 0 < idx:
            h = h[:idx]
            break

    # Convert block elements to newlines
    h = re.sub(r"<br\s*/?>", "\n", h, flags=re.I)
    h = re.sub(r"</(?:p|div|li|tr|td|th)>", "\n", h, flags=re.I)

    plain = html_mod.unescape(re.sub(r"<[^>]+>", "", h))
    plain = re.sub(r"\u200b|\u200c|\u200d|\ufeff", "", plain)  # zero-width chars

    # Collect verse lines
    lines = []
    for raw_line in plain.splitlines():
        line = re.sub(r"[ \t]+", " ", raw_line).strip()
        if not line or len(line) < 8:
            continue
        # Skip navigation / headings
        if re.match(r"^(BOOK|Metamorphoses|METAMORPHOSES|←|→|\|)", line, re.I):
            continue
        if re.match(r"^Book\s+[IVX\d]+", line, re.I):
            continue
        if re.search(r"(wikisource|wikipedia|creative commons|jump to|navigation|Translated by)", line, re.I):
            continue
        lines.append(line)

    if not lines:
        return {}

    # Skip argument/heading prose — find where verse starts
    # Heuristic: look for first block of lines averaging 45–100 chars
    verse_start = 0
    for i in range(max(0, len(lines) - 4)):
        chunk = lines[i:i+4]
        avg = sum(len(l) for l in chunk) / 4
        if 35 <= avg <= 110:
            verse_start = i
            break

    verse_lines = lines[verse_start:]

    # Group into couplets
    entries: dict[str, str] = {}
    line_num = 1
    i = 0
    while i < len(verse_lines):
        l1 = verse_lines[i]
        if i + 1 < len(verse_lines):
            l2 = verse_lines[i + 1]
            entries[f"{line_num}-{line_num+1}"] = l1 + "\n" + l2
            i += 2
            line_num += 2
        else:
            entries[str(line_num)] = l1
            i += 1
            line_num += 1

    return entries


def main():
    out_dir = Path("data") / "classical"
    out_dir.mkdir(parents=True, exist_ok=True)

    for work in WORKS:
        out_path = Path(work["outfile"])
        print(f"\n{'='*60}")
        print(f"{work['name']} ({work['books']} books)")
        print(f"Output: {out_path}")
        print(f"{'='*60}")

        if out_path.exists():
            payload = json.loads(out_path.read_text(encoding="utf-8"))
            books_done = payload.get("books", {})
            print(f"Resuming: {len(books_done)} books already done.")
        else:
            books_done = {}

        for book_n in range(1, work["books"] + 1):
            if str(book_n) in books_done:
                print(f"  Book {book_n:2}: skip")
                continue

            if work["roman"]:
                url = work["url_tmpl"].format(roman=ROMAN[book_n - 1])
            else:
                url = work["url_tmpl"].format(n=book_n)

            print(f"  Book {book_n:2}:", end=" ", flush=True)
            try:
                raw = _fetch(url)
                entries = _parse_book(raw)
                if entries:
                    books_done[str(book_n)] = entries
                    print(f"{len(entries)} couplets (~{len(entries)*2} lines)")
                else:
                    print("⚠ no verse parsed")
            except urllib.error.HTTPError as e:
                print(f"HTTP {e.code}")
            except Exception as e:
                print(f"ERROR: {e}")
            finally:
                out_path.write_text(
                    json.dumps({
                        "source": work["source"],
                        "abbrev": work["abbrev"],
                        "books":  books_done,
                    }, indent=2, ensure_ascii=False),
                    encoding="utf-8"
                )
            time.sleep(0.8)

        total = sum(len(ch) for ch in books_done.values())
        print(f"\nDone: {len(books_done)} books, {total:,} couplets → {out_path}")


if __name__ == "__main__":
    main()
