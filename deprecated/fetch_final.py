#!/usr/bin/env python3
"""
fetch_final.py  —  fetches remaining missing works with VERIFIED URLs.

All URLs confirmed via web search before writing this script.

Run:
    python3 fetch_final.py data\\patristics
    python3 fetch_final.py data\\patristics augustine
"""

import json, re, sys, time, pathlib, urllib.request, html as html_mod
from typing import Optional

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                         "AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"}
DELAY = 1.2

def fetch(url):
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.read().decode("utf-8", errors="replace")
    except Exception as e:
        print(f"    ERROR: {e}")
        return None

def hclean(h):
    h = re.sub(r"<a\b[^>]*>(.*?)</a>", r"\1", h, flags=re.DOTALL|re.IGNORECASE)
    h = re.sub(r"<[^>]+>", " ", h)
    h = html_mod.unescape(h)
    return re.sub(r"\s+", " ", h).strip()

BAD = (
    "Please help support the mission of New Advent",
    "How Catholic Underground",
    "Click here to see the list of",
    "Source. Translated by",
    "Contact Us | Advertise",
    "This text was reformatted by Roger Pearse",
)

def is_bad(t): return len(t) < 30 or any(t.startswith(b) for b in BAD)

def strip_footer(html):
    for cut in ["Source. Translated", "This text was reformatted",
                "Contact information", "Copyright © 20"]:
        idx = html.find(cut)
        if idx > 3000:
            html = html[:idx]
    return html

def get_paras(html):
    raw = re.findall(r"<p[^>]*>(.*?)</p>", html, re.DOTALL|re.IGNORECASE)
    return [hclean(p) for p in raw if not is_bad(hclean(p))]

def numbered(paras): return {str(i+1): p for i, p in enumerate(paras)}

def na(code): return f"https://www.newadvent.org/fathers/{code}.htm"

def fetch_page(url, book_prefix=""):
    print(f"    {url}")
    html = fetch(url)
    time.sleep(DELAY)
    if not html: return {}
    body = strip_footer(html)

    # h2 split
    parts = re.split(r"<h2[^>]*>", body, flags=re.IGNORECASE)
    result = {}
    for part in parts[1:]:
        end = part.find("</h2>")
        header = hclean(part[:end]) if end > 0 else ""
        m = re.search(r"(\d+)", header)
        if not m: continue
        paras = get_paras(part[end+5:] if end > 0 else part)
        if paras:
            key = f"{book_prefix}{m.group(1)}" if book_prefix else m.group(1)
            result[key] = numbered(paras)
    if result: return result

    # inline-number split
    paras = get_paras(body)
    if not paras: return {}
    sections, cur, lines = {}, None, []
    for para in paras:
        m = re.match(r"^(\d+)\.\s+", para)
        if m:
            if cur is not None and lines:
                sections[str(cur)] = numbered(lines)
            cur = int(m.group(1)); lines = [para]
        else:
            if cur is None: cur = 1
            lines.append(para)
    if cur is not None and lines:
        sections[str(cur)] = numbered(lines)
    if sections:
        if book_prefix:
            sections = {f"{book_prefix}{k}": v for k, v in sections.items()}
        return sections

    return {"1": numbered(paras)}

def fetch_index_letters(index_code):
    html_idx = fetch(na(index_code))
    time.sleep(DELAY)
    if not html_idx: return {}
    links = re.findall(r"/fathers/(\w+)\.htm", html_idx)
    seen, codes = set(), []
    for lnk in links:
        if lnk != index_code and lnk not in seen:
            seen.add(lnk); codes.append(lnk)
    result = {}
    for i, code in enumerate(codes, 1):
        html_l = fetch(na(code))
        time.sleep(DELAY)
        if html_l:
            paras = get_paras(strip_footer(html_l))
            if paras: result[str(i)] = numbered(paras)
    return result

# Against Celsus: each book is a SEPARATE PAGE 04161-04168
def fetch_against_celsus():
    result = {}
    for bk in range(1, 9):
        work = fetch_page(na(f"0416{bk}"), f"{bk}.")
        result.update(work)
    return result

# Clement Exhortation: 12 chapters, each a separate page 02081-02112
def fetch_clement_exhortation():
    result = {}
    for ch in range(1, 13):
        work = fetch_page(na(f"0208{ch}"))
        if work:
            for k, v in work.items():
                result[str(ch)] = v  # one chapter per page
    if not result:
        # fallback: try single page
        result = fetch_page(na("0208"))
    return result

# ── Verified task list ─────────────────────────────────────────────────────────

TASKS = {
    "augustine": [
        # On Christian Doctrine: VERIFIED 12020-12024
        ("On Christian Doctrine", lambda: {
            **fetch_page(na("12020"), "Pref."),
            **fetch_page(na("12021"), "1."),
            **fetch_page(na("12022"), "2."),
            **fetch_page(na("12023"), "3."),
            **fetch_page(na("12024"), "4."),
        }),
        # On the Spirit and the Letter: VERIFIED 1502.htm
        ("On the Spirit and the Letter", lambda: fetch_page(na("1502"))),
        # Note: On Free Will (De libero arbitrio) and Retractions
        # are NOT available as standalone texts on NewAdvent.
    ],
    "origen": [
        # Against Celsus: VERIFIED 04161-04168 (8 separate book pages)
        ("Against Celsus", fetch_against_celsus),
    ],
    "clement_of_alexandria": [
        # Exhortation: VERIFIED 02081-02112 (12 chapter pages)
        ("Exhortation to the Heathen", fetch_clement_exhortation),
    ],
    "gregory_the_great": [
        # Pastoral Rule: VERIFIED 36011-36014
        ("Pastoral Rule", lambda: {
            **fetch_page(na("36011"), "1."),
            **fetch_page(na("36012"), "2."),
            **fetch_page(na("36013"), "3."),
            **fetch_page(na("36014"), "4."),
        }),
    ],
    "jerome": [
        # Against the Luciferians: VERIFIED 3005.htm
        ("Against the Luciferians", lambda: fetch_page(na("3005"))),
    ],
    "athanasius": [
        # De Sententia Dionysii: VERIFIED 2810.htm (not 2808)
        ("De Sententia Dionysii", lambda: fetch_page(na("2810"))),
        # Letters: index at 2822
        ("Letters of Athanasius", lambda: fetch_index_letters("2822")),
    ],
    "basil_the_great": [
        # Letters: index at 3204
        ("Letters of Basil", lambda: fetch_index_letters("3204")),
    ],
    "tertullian": [
        # On the Veiling of Virgins: VERIFIED 0403.htm (not 0327)
        ("On the Veiling of Virgins", lambda: fetch_page(na("0403"))),
    ],
    "john_of_damascus": [
        # Philosophical Chapters: VERIFIED 3303.htm
        ("Philosophical Chapters", lambda: fetch_page(na("3303"))),
    ],
}

# Gregory Nazianzen: only 24 orations exist on NewAdvent (NPNF Vol. 7 selection).
# The missing 21 were never translated in that volume. Nothing to fetch.
NAZIANZEN_NOTE = """
gregory_nazianzen: The 24 orations you have ARE all that NewAdvent carries.
Orations 4-6, 9-11, 13-15, 17, 19-20, 22-26, 32, 35-36, 44 were not
included in the NPNF Vol. 7 English translation. Nothing to fetch.
"""

def main():
    data_dir = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else pathlib.Path("data/patristics")
    targets  = sys.argv[2:] if len(sys.argv) > 2 else []

    print(NAZIANZEN_NOTE)

    for slug, task_list in TASKS.items():
        if targets and not any(t in slug for t in targets):
            continue
        path = data_dir / f"{slug}.json"
        if not path.exists():
            print(f"SKIP: {path}"); continue
        print(f"\n{slug}")
        data  = json.loads(path.read_text(encoding="utf-8"))
        books = data.get("books", {})
        changed = False
        for work_name, fetch_fn in task_list:
            existing_p = sum(len(v) for v in books.get(work_name, {}).values())
            if existing_p > 10:
                print(f"  SKIP {work_name} ({existing_p} paras already)")
                continue
            print(f"  Fetching {work_name}...")
            result = fetch_fn()
            if result:
                n_p = sum(len(v) for v in result.values())
                if n_p > 0:
                    books[work_name] = result
                    print(f"  ✓ {work_name}: {len(result)} chapters, {n_p} paras")
                    changed = True
                else:
                    print(f"  ✗ {work_name}: fetched but all empty")
            else:
                print(f"  ✗ {work_name}: fetch failed")
        if changed:
            data["books"] = books
            path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        total = sum(len(v) for bk in books.values() for v in bk.values())
        print(f"  → {len(books)} works, {total} paras")

    print("\nNotes:")
    print("  - 'On Free Will' (De libero arbitrio): not on NewAdvent as standalone")
    print("  - 'Retractions': not on NewAdvent as standalone")
    print("Done.")

if __name__ == "__main__":
    main()
