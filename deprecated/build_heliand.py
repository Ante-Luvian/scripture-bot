#!/usr/bin/env python3
"""
build_heliand.py — Scrape hieronymus.us.com/latinweb/Mediaevum/Heliand.htm
Produces:
  data/poetry/heliand_english.json   — Scott English translation
  data/poetry/heliand_oldsaxon.json  — Old Saxon text (Regan normalisation)

Both use the same schema as other poetry files.
"books" keys = fitt number (1-71).
"verse" keys = line ranges (couplets) using continuous line numbers 1-5968.

Run: python build_heliand.py
"""
import json, re, urllib.request, html as html_module
from pathlib import Path

URL = "https://www.hieronymus.us.com/latinweb/Mediaevum/Heliand.htm"
HEADERS = {"User-Agent": "ScriptureBot/1.0 (academic use)"}
OUT_EN = Path("data") / "poetry" / "heliand_english.json"
OUT_OS = Path("data") / "poetry" / "heliand_oldsaxon.json"

def fetch():
    req = urllib.request.Request(URL, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", errors="replace")

def parse(html: str):
    """
    Parse rows like:
      | 1:1 | Old Saxon text | English text |
    Store each numbered line individually (not in couplets) to avoid
    drift from blank-ref overflow rows.
    Returns two dicts: {fitt_str: {line_str: text}}
    """
    html = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL|re.IGNORECASE)
    html = re.sub(r'<style[^>]*>.*?</style>',  '', html, flags=re.DOTALL|re.IGNORECASE)
    html = re.sub(r'<br\s*/?>', ' ', html, flags=re.IGNORECASE)

    rows = re.findall(r'<tr[^>]*>(.*?)</tr>', html, re.DOTALL|re.IGNORECASE)

    lines_os = {}
    lines_en = {}
    line_to_fitt = {}

    for row in rows:
        cells = re.findall(r'<td[^>]*>(.*?)</td>', row, re.DOTALL|re.IGNORECASE)
        if len(cells) < 3:
            continue
        ref_cell = re.sub(r'<[^>]+>', '', cells[0]).strip()
        m = re.match(r'^(\d+):(\d+)$', ref_cell)
        if not m:
            continue  # skip blank-ref overflow rows entirely
        fitt = int(m.group(1))
        line = int(m.group(2))

        def clean(c):
            c = re.sub(r'<[^>]+>', ' ', c)
            c = html_module.unescape(c)
            return re.sub(r'\s+', ' ', c).strip()

        os_text = clean(cells[1])
        en_text = clean(cells[2])

        line_to_fitt[line] = fitt
        if os_text:
            lines_os[line] = os_text
        if en_text:
            lines_en[line] = en_text

    if not lines_os and not lines_en:
        return {}, {}

    def build_fitts(lines_dict):
        from collections import defaultdict
        fitt_lines = defaultdict(dict)
        for ln in sorted(lines_dict.keys()):
            fitt = line_to_fitt.get(ln, 1)
            fitt_lines[fitt][str(ln)] = lines_dict[ln]
        return {str(k): v for k, v in sorted(fitt_lines.items()) if v}

    return build_fitts(lines_en), build_fitts(lines_os)

def main():
    print(f"Fetching {URL}...")
    html = fetch()
    print(f"  {len(html):,} bytes")

    fitts_en, fitts_os = parse(html)

    def stats(fitts):
        lines = sum(sum(2 if '-' in k else 1 for k in f.keys()) for f in fitts.values())
        return f"{len(fitts)} fitts, ~{lines} lines"

    print(f"  English: {stats(fitts_en)}")
    print(f"  Old Saxon: {stats(fitts_os)}")

    # Spot checks
    f1en = fitts_en.get("1", {})
    f1os = fitts_os.get("1", {})
    if f1en:
        first = next(iter(f1en))
        print(f"\n  EN Fitt 1 ({first}): {f1en[first][:80]}")
    if f1os:
        first = next(iter(f1os))
        print(f"  OS Fitt 1 ({first}): {f1os[first][:80]}")

    fitt1_lines = sum(2 if '-' in k else 1 for k in f1en.keys())
    print(f"\n  Fitt 1: ~{fitt1_lines} lines ({len(f1en)} couplets)")

    OUT_EN.parent.mkdir(parents=True, exist_ok=True)

    OUT_EN.write_text(json.dumps({
        "source": "Heliand. Trans. Mariana Scott (1966/1969). Via hieronymus.us.com. Public domain.",
        "abbrev": "Heliand",
        "lang": "en",
        "books": fitts_en,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nSaved {OUT_EN} ({OUT_EN.stat().st_size/1024:.0f} KB)")

    OUT_OS.write_text(json.dumps({
        "source": "Heliand (~830 AD). Old Saxon text, orthography partially normalised by Brian T. Regan. Via hieronymus.us.com. Public domain.",
        "abbrev": "Heliand.os",
        "lang": "osx",
        "books": fitts_os,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Saved {OUT_OS} ({OUT_OS.stat().st_size/1024:.0f} KB)")

if __name__ == "__main__":
    main()
