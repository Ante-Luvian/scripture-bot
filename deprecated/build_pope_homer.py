#!/usr/bin/env python3
"""
build_pope_homer.py — scrape Pope's Iliad and Odyssey from Wikisource.

Output (run from your bot directory):
  data/classical/iliad_pope.json
  data/classical/odyssey_pope.json

Structure: book → line_range → couplet text
Citation format: Il. 6.441  (book.line)
Lines are Pope's, grouped in couplets (2 lines per entry).
Line numbers are sequential within each book.

Run: python build_pope_homer.py
"""

import json, re, time, html as html_mod, urllib.request, urllib.error
from pathlib import Path

ILIAD_BOOKS  = 24
ODYSSEY_BOOKS = 24

WORKS = [
    {
        "name":    "Iliad (Pope)",
        "abbrev":  "Il.",
        "url_tmpl": "https://en.wikisource.org/wiki/The_Iliad_of_Homer_(Pope)/Book_{n}",
        "outfile":  "data/classical/iliad_pope.json",
        "books":    ILIAD_BOOKS,
        "source":   "Homer, The Iliad. Trans. Alexander Pope (1715–1720). Public domain.",
    },
    {
        "name":    "Odyssey (Pope)",
        "abbrev":  "Od.",
        "url_tmpl": "https://en.wikisource.org/wiki/Odyssey_(Pope)/Book_{n}",
        "outfile":  "data/classical/odyssey_pope.json",
        "books":    ODYSSEY_BOOKS,
        "source":   "Homer, The Odyssey. Trans. Alexander Pope (1725–1726). Public domain.",
    },
]


def _fetch(url: str) -> str:
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (compatible; ScriptureBot/1.0)",
        "Accept": "text/html,application/xhtml+xml",
    })
    with urllib.request.urlopen(req, timeout=20) as r:
        return r.read().decode("utf-8", errors="replace")


def _parse_book(raw: str, book_num: int) -> dict[str, str]:
    """
    Extract Pope's couplets from a Wikisource page.
    Returns {line_range: text} where line_range is e.g. "1-2", "3-4" etc.

    The text on Wikisource is prose-formatted HTML with the poem lines
    separated by <br> tags or in <p> tags. We extract all non-empty
    text lines from the main content div and pair them into couplets.
    """
    # Strip scripts/styles/footnotes
    h = re.sub(r"<script[^>]*>.*?</script>", " ", raw, flags=re.S|re.I)
    h = re.sub(r"<style[^>]*>.*?</style>",   " ", h,   flags=re.S|re.I)
    h = re.sub(r"<!--.*?-->",                 " ", h,   flags=re.S)

    # Remove footnote superscripts like <sup><a ...>[1]</a></sup>
    h = re.sub(r"<sup[^>]*>.*?</sup>", "", h, flags=re.S|re.I)

    # Find the main content block — Wikisource uses <div id="mw-content-text">
    content_m = re.search(r'<div[^>]*id="mw-content-text"[^>]*>(.*)', h, re.S|re.I)
    if content_m:
        h = content_m.group(1)

    # Cut at the "Retrieved from" footer
    for cutoff in ["Retrieved from", "Hidden categories", "mw-hidden-cats", "printfooter"]:
        idx = h.find(cutoff)
        if idx > 0:
            h = h[:idx]
            break

    # Replace <br> and </p> with newlines so lines are separated
    h = re.sub(r"<br\s*/?>", "\n", h, flags=re.I)
    h = re.sub(r"</p>",      "\n", h, flags=re.I)
    h = re.sub(r"</div>",    "\n", h, flags=re.I)

    # Strip remaining HTML tags
    plain = html_mod.unescape(re.sub(r"<[^>]+>", "", h))

    # Normalise whitespace on each line
    lines = []
    for raw_line in plain.splitlines():
        line = re.sub(r"[ \t]+", " ", raw_line).strip()
        # Skip blank lines, navigation artefacts, chapter headings
        if not line:
            continue
        if len(line) < 8:
            continue
        if re.match(r"^(BOOK|THE ILIAD|THE ODYSSEY|ARGUMENT|←|→|\|)", line, re.I):
            continue
        if re.match(r"^\s*(Book\s+\d|Book [IVX]+)", line, re.I):
            continue
        if re.search(r"(wikisource|wikipedia|creative commons|jump to|navigation)", line, re.I):
            continue
        # Skip lines that look like argument/summary prose (very long, no poetic rhythm)
        # We keep lines that look like verse: usually < 120 chars, often end with punctuation
        lines.append(line)

    if not lines:
        return {}

    # Find where the verse actually starts — skip the ARGUMENT/summary prose.
    # Pope's verse lines typically scan as iambic pentameter couplets,
    # averaging 50–90 chars. The argument/summary prose lines are longer and
    # use different punctuation. Heuristic: verse starts after the first line
    # that begins with a capital letter following a short (<= 80 char) line
    # that itself follows a blank region. Simpler: skip lines until we hit the
    # rhyming couplets. We detect the verse start by looking for a section
    # where most lines are 40–100 chars.
    verse_start = 0
    window = 6
    for i in range(len(lines) - window):
        chunk = lines[i:i+window]
        avg_len = sum(len(l) for l in chunk) / window
        if 35 <= avg_len <= 105:
            verse_start = i
            break

    verse_lines = lines[verse_start:]

    # Group into couplets (pairs of lines) — Pope's translation is in
    # heroic couplets, but sometimes a thought spans 4 lines (two couplets).
    # We store each couplet as one entry.
    entries: dict[str, str] = {}
    line_num = 1
    i = 0
    while i < len(verse_lines):
        line1 = verse_lines[i]
        if i + 1 < len(verse_lines):
            line2 = verse_lines[i + 1]
            text = line1 + "\n" + line2
            key = f"{line_num}-{line_num + 1}"
            entries[key] = text
            i += 2
            line_num += 2
        else:
            # Orphaned last line
            entries[str(line_num)] = line1
            i += 1
            line_num += 1

    return entries


def scrape_work(work: dict) -> dict:
    """Scrape all books for one work. Returns {book_str: {line_range: text}}."""
    books_data: dict[str, dict] = {}
    for book_n in range(1, work["books"] + 1):
        url = work["url_tmpl"].format(n=book_n)
        print(f"  Book {book_n:2}: {url}")
        try:
            raw = _fetch(url)
            entries = _parse_book(raw, book_n)
            if entries:
                books_data[str(book_n)] = entries
                print(f"           {len(entries)} couplets, ~{len(entries)*2} lines")
            else:
                print(f"           ⚠ no verse parsed — check page structure")
        except urllib.error.HTTPError as e:
            print(f"           HTTP {e.code}")
        except Exception as e:
            print(f"           ERROR: {e}")
        time.sleep(0.8)   # polite delay for Wikisource
    return books_data


def main():
    out_dir = Path("data") / "classical"
    out_dir.mkdir(parents=True, exist_ok=True)

    for work in WORKS:
        out_path = Path(work["outfile"])
        print(f"\n{'='*60}")
        print(f"{work['name']} ({work['books']} books)")
        print(f"Output: {out_path}")
        print(f"{'='*60}")

        # Resume support
        if out_path.exists():
            payload = json.loads(out_path.read_text(encoding="utf-8"))
            books_done = payload.get("books", {})
            print(f"Resuming: {len(books_done)} books already scraped.")
        else:
            books_done = {}

        for book_n in range(1, work["books"] + 1):
            if str(book_n) in books_done:
                print(f"  Book {book_n:2}: skip (done)")
                continue
            url = work["url_tmpl"].format(n=book_n)
            print(f"  Book {book_n:2}:", end=" ", flush=True)
            try:
                raw = _fetch(url)
                entries = _parse_book(raw, book_n)
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
                # Save after every book
                out_path.write_text(
                    json.dumps({
                        "source": work["source"],
                        "abbrev": work["abbrev"],
                        "books":  books_done,
                    }, indent=2, ensure_ascii=False),
                    encoding="utf-8"
                )
            time.sleep(0.8)

        total_couplets = sum(len(ch) for ch in books_done.values())
        print(f"\nDone: {len(books_done)} books, {total_couplets:,} couplets → {out_path}")


if __name__ == "__main__":
    main()
