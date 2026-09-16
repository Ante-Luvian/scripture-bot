#!/usr/bin/env python3
"""
build_virgil_minor.py — scrape Dryden's Eclogues and Georgics from Wikisource.

Output (run from your bot directory):
  data/poetry/eclogues_dryden.json    — 10 Eclogues
  data/poetry/georgics_dryden.json    — 4 books

URL patterns:
  https://en.wikisource.org/wiki/The_Works_of_Virgil_(Dryden)/Pastorals_(Dryden)/Book_1
  https://en.wikisource.org/wiki/The_Works_of_Virgil_(Dryden)/Georgics_(Dryden)/Book_1

Citation:
  Ecl. 1.1-20     (Eclogue number . line range)
  G. 2.1-50       (Georgic book . line range)

Couplets and triplets are detected and stored as 2- or 3-line entries,
keyed by source line numbers (e.g. "1-2", "33-35").

Run: python build_virgil_minor.py
"""

import json, re, time, html as html_mod, urllib.request, urllib.error
from pathlib import Path

WORKS = [
    {
        "name":     "Eclogues (Dryden)",
        "abbrev":   "Ecl.",
        "outfile":  "data/poetry/eclogues_dryden.json",
        "source":   "Virgil, Eclogues (Pastorals). Trans. John Dryden (1697). Public domain.",
        "books":    10,
        "url_tmpl": "https://en.wikisource.org/wiki/The_Works_of_Virgil_(Dryden)/Pastorals_(Dryden)/Book_{n}",
    },
    {
        "name":     "Georgics (Dryden)",
        "abbrev":   "G.",
        "outfile":  "data/poetry/georgics_dryden.json",
        "source":   "Virgil, Georgics. Trans. John Dryden (1697). Public domain.",
        "books":    4,
        "url_tmpl": "https://en.wikisource.org/wiki/The_Works_of_Virgil_(Dryden)/Georgics_(Dryden)/Book_{n}",
    },
]


def _fetch(url: str) -> str:
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (compatible; ScriptureBot/1.0)",
        "Accept": "text/html,application/xhtml+xml",
    })
    with urllib.request.urlopen(req, timeout=20) as r:
        return r.read().decode("utf-8", errors="replace")


def _is_latex(line: str) -> bool:
    return bool(re.search(r'\\displaystyle|\\end\{matrix\}|\\right\\?\}|^\\\s*\\\\', line))


def _clean_latex(line: str) -> str:
    line = re.sub(r'\{\s*\\displaystyle.*?\}\s*', '', line, flags=re.S)
    line = re.sub(r'\\\s*\\\\+.*', '', line)
    line = re.sub(r'\\end\{matrix\}.*', '', line)
    line = re.sub(r'\\right\\?\}.*', '', line)
    line = re.sub(r'\\\\\s*$', '', line)
    return line.strip()


def _is_garbage(line: str) -> bool:
    """Lines to discard entirely (navigation, headings, argument prose markers)."""
    s = line.strip()
    if not s or len(s) < 5:
        return True
    # Wikisource page IDs that leak in
    if re.match(r'^\d{6,}The Works', s):
        return True
    # Navigation arrows
    if re.match(r'^[←→]', s):
        return True
    return False


def _last_word(line: str) -> str:
    w = line.rstrip(',:;.!? "\'').split()
    return w[-1].lower().rstrip('.,!?"\'') if w else ''


def _rhymes(a: str, b: str) -> bool:
    wa, wb = _last_word(a), _last_word(b)
    if not wa or not wb or wa == wb:
        return False
    return wa[-3:] == wb[-3:] or wa[-4:] == wb[-4:]


def _parse_page(raw: str) -> list[str]:
    """
    Extract verse lines from a Wikisource page as a flat list of strings.
    Removes argument/header prose, speaker labels, footnotes, and LaTeX braces.
    Marks LaTeX triplet-brace positions with the sentinel 'TRIPLET_MARKER'.
    """
    h = re.sub(r'<script[^>]*>.*?</script>', ' ', raw, flags=re.S | re.I)
    h = re.sub(r'<style[^>]*>.*?</style>',   ' ', h,   flags=re.S | re.I)
    h = re.sub(r'<!--.*?-->',                 ' ', h,   flags=re.S)
    h = re.sub(r'<sup[^>]*>.*?</sup>',        '',  h,   flags=re.S | re.I)

    # Find main content
    m = re.search(r'<div[^>]*id="mw-content-text"[^>]*>(.*)', h, re.S | re.I)
    if m:
        h = m.group(1)

    # Cut at footer
    for cut in ('Retrieved from', 'Hidden categories', 'printfooter'):
        idx = h.find(cut)
        if 0 < idx:
            h = h[:idx]
            break

    # Replace <br> and block elements with newlines
    h = re.sub(r'<br\s*/?>', '\n', h, flags=re.I)
    h = re.sub(r'</(?:p|div|li|tr)>', '\n', h, flags=re.I)

    plain = html_mod.unescape(re.sub(r'<[^>]+>', '', h))
    plain = re.sub(r'[\u200b\u200c\u200d\ufeff]', '', plain)

    lines = []
    for raw_line in plain.splitlines():
        stripped = re.sub(r'[ \t]+', ' ', raw_line).strip()
        if not stripped:
            continue

        # LaTeX brace — keep as marker to preserve triplet positions
        if _is_latex(stripped):
            lines.append('TRIPLET_MARKER')
            continue

        if _is_garbage(stripped):
            continue

        lines.append(stripped)

    return lines


def _find_verse_start(lines: list[str]) -> int:
    """
    Skip argument/prose header lines before the verse begins.
    Heuristic: find first run of lines averaging 40-100 chars that looks like verse.
    """
    for i in range(len(lines) - 4):
        chunk = [l for l in lines[i:i+6] if l != 'TRIPLET_MARKER']
        if not chunk:
            continue
        avg = sum(len(l) for l in chunk) / len(chunk)
        if 35 <= avg <= 105:
            return i
    return 0


def _build_entries(lines: list[str]) -> dict[str, str]:
    """
    Given a flat list of verse lines (with TRIPLET_MARKER sentinels),
    group into couplets (2-line) or triplets (3-line) and key by
    source line numbers. Returns {line_range_key: text}.
    """
    # Find which line indices are followed by a TRIPLET_MARKER
    # Those lines' NEXT line belongs in the same group (forming a triplet)
    triplet_after: set[int] = set()
    real_lines = []  # only actual verse lines, no markers

    line_idx = 0
    for i, token in enumerate(lines):
        if token == 'TRIPLET_MARKER':
            # The most recently added real line should be in a triplet
            if real_lines:
                triplet_after.add(line_idx - 1)
        else:
            real_lines.append(token)
            line_idx += 1

    # Also detect triplets by rhyme (catches cases where LaTeX marker was missing)
    i = 0
    while i < len(real_lines) - 2:
        a, b, c = real_lines[i], real_lines[i+1], real_lines[i+2]
        if _rhymes(a, b) and _rhymes(b, c) and i not in triplet_after:
            triplet_after.add(i)
        i += 1

    # Build entries
    entries: dict[str, str] = {}
    line_num = 1
    i = 0
    while i < len(real_lines):
        if i in triplet_after and i + 2 < len(real_lines):
            key = f"{line_num}-{line_num + 2}"
            entries[key] = real_lines[i] + '\n' + real_lines[i+1] + '\n' + real_lines[i+2]
            line_num += 3
            i += 3
        elif i + 1 < len(real_lines):
            key = f"{line_num}-{line_num + 1}"
            entries[key] = real_lines[i] + '\n' + real_lines[i+1]
            line_num += 2
            i += 2
        else:
            entries[str(line_num)] = real_lines[i]
            line_num += 1
            i += 1

    return entries


def scrape_work(work: dict) -> None:
    out_path = Path(work['outfile'])
    out_path.parent.mkdir(parents=True, exist_ok=True)

    # Resume support
    if out_path.exists():
        payload = json.loads(out_path.read_text(encoding='utf-8'))
        books_done = payload.get('books', {})
    else:
        books_done = {}

    print(f"\n{'='*60}")
    print(f"{work['name']}")
    print(f"{'='*60}")

    for book_n in range(1, work['books'] + 1):
        if str(book_n) in books_done:
            print(f"  Book {book_n:2}: skip (done)")
            continue

        url = work['url_tmpl'].format(n=book_n)
        print(f"  Book {book_n:2}: {url}")
        try:
            raw = _fetch(url)
            all_lines = _parse_page(raw)
            verse_start = _find_verse_start(
                [l for l in all_lines if l != 'TRIPLET_MARKER']
            )
            # Apply verse_start to the full list including markers
            # Count verse_start non-marker lines, then find that position in all_lines
            non_marker_count = 0
            start_idx = 0
            for idx, token in enumerate(all_lines):
                if token != 'TRIPLET_MARKER':
                    if non_marker_count >= verse_start:
                        start_idx = idx
                        break
                    non_marker_count += 1

            verse_lines = all_lines[start_idx:]
            entries = _build_entries(verse_lines)

            if entries:
                books_done[str(book_n)] = entries
                n_couplets = sum(1 for v in entries.values() if '\n' in v and len(v.split('\n')) == 2)
                n_triplets = sum(1 for v in entries.values() if '\n' in v and len(v.split('\n')) == 3)
                print(f"           {n_couplets} couplets, {n_triplets} triplets")
            else:
                print(f"           ⚠ no verse parsed")

        except urllib.error.HTTPError as e:
            print(f"           HTTP {e.code}")
        except Exception as e:
            print(f"           ERROR: {e}")
        finally:
            out_path.write_text(
                json.dumps({
                    'source': work['source'],
                    'abbrev': work['abbrev'],
                    'books':  books_done,
                }, indent=2, ensure_ascii=False),
                encoding='utf-8'
            )
        time.sleep(0.8)

    total_entries = sum(len(b) for b in books_done.values())
    triplets = sum(1 for b in books_done.values()
                   for v in b.values() if '\n' in v and len(v.split('\n')) == 3)
    print(f"\nDone: {len(books_done)} books, {total_entries:,} entries "
          f"({triplets} triplets) → {out_path}")


def main():
    for work in WORKS:
        scrape_work(work)


if __name__ == '__main__':
    main()
