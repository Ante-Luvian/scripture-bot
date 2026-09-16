#!/usr/bin/env python3
"""
refetch_fathers.py
------------------
Re-fetches the works that were empty, wrong, or structurally broken
in the initial build. Uses a more robust parser than the original
build_fathers.py — handles pages without <h2> chapter headers by
detecting inline chapter numbers or treating the whole page as one work.

Run:
    python3 refetch_fathers.py data/patristics/
    python3 refetch_fathers.py data/patristics/ athanasius   # one author only
"""

import json, re, time, sys, pathlib, urllib.request, html as html_mod
from typing import Optional

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; ScriptureBot/2.0)"}
DELAY = 1.2

def fetch(url: str) -> Optional[str]:
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.read().decode("utf-8", errors="replace")
    except Exception as e:
        print(f"  FETCH ERROR {url}: {e}")
        return None

def clean(html: str) -> str:
    html = re.sub(r"<a\b[^>]*>(.*?)</a>", r"\1", html, flags=re.DOTALL|re.IGNORECASE)
    html = re.sub(r"<[^>]+>", " ", html)
    html = html_mod.unescape(html)
    return re.sub(r"\s+", " ", html).strip()

def strip_boilerplate_head(html: str) -> str:
    """Remove NewAdvent promo/nav from start; Source attribution from end."""
    # Cut at Source attribution
    for cut in ["Source. Translated", "MARIÆ IMMACULATÆ",
                "Contact information", "Copyright © 20"]:
        idx = html.find(cut)
        if idx > 3000:
            html = html[:idx]
    return html

def get_paras(html: str) -> list[str]:
    """Extract <p> paragraphs, filter boilerplate."""
    paras = re.findall(r"<p[^>]*>(.*?)</p>", html, re.DOTALL|re.IGNORECASE)
    result = []
    for p in paras:
        t = clean(p)
        if len(t) < 30:
            continue
        if t.startswith("Please help support the mission of New Advent"):
            continue
        if t.startswith("How Catholic Underground"):
            continue
        result.append(t)
    return result

def na_url(code: str) -> str:
    return f"https://www.newadvent.org/fathers/{code}.htm"

def pearse_url(fn: str) -> str:
    return f"https://www.ccel.org/ccel/pearse/morefathers/files/{fn}.htm"

def numbered(paras: list[str]) -> dict:
    return {str(i+1): p for i, p in enumerate(paras)}

def split_by_inline_chapters(paras: list[str]) -> dict[str, dict]:
    """
    Many NA pages have no <h2> headers but embed chapter/section numbers
    in the text itself: "1. The knowledge...", "2. Since...", etc.
    Split on those.
    """
    sections = {}
    current_sec = None
    current_lines = []

    for para in paras:
        m = re.match(r'^(\d+)\.\s+(.+)', para, re.DOTALL)
        if m:
            if current_sec is not None and current_lines:
                sections[str(current_sec)] = numbered(current_lines)
            current_sec = int(m.group(1))
            current_lines = [para]  # keep full text including number
        else:
            if current_sec is None:
                current_sec = 1
            current_lines.append(para)

    if current_sec is not None and current_lines:
        sections[str(current_sec)] = numbered(current_lines)

    return sections

def split_by_h2(html: str, book_prefix: str = "") -> dict[str, dict]:
    """Standard h2-based chapter split."""
    body = strip_boilerplate_head(html)
    parts = re.split(r"<h2[^>]*>", body, flags=re.IGNORECASE)
    result = {}
    for part in parts[1:]:
        end = part.find("</h2>")
        header = clean(part[:end]) if end > 0 else ""
        m = re.search(r"(\d+)", header)
        if not m:
            continue
        num = m.group(1)
        body_html = part[end+5:] if end > 0 else part
        paras = get_paras(body_html)
        if paras:
            key = f"{book_prefix}{num}" if book_prefix else num
            result[key] = numbered(paras)
    return result

def fetch_page_smart(url: str, book_prefix: str = "") -> dict:
    """
    Fetch a page and try h2 splitting first; fall back to inline-number splitting.
    """
    print(f"    {url}")
    html = fetch(url)
    time.sleep(DELAY)
    if not html:
        return {}

    # Try h2 first
    result = split_by_h2(html, book_prefix)
    if result:
        return result

    # Fall back: inline chapter numbers
    body = strip_boilerplate_head(html)
    paras = get_paras(body)
    if not paras:
        return {}

    result = split_by_inline_chapters(paras)
    if result:
        if book_prefix:
            result = {f"{book_prefix}{k}": v for k, v in result.items()}
        return result

    # Last resort: one big chapter
    return {"1": numbered(paras)}

def fetch_roman_numeral_page(url: str) -> dict:
    """
    For pages that use Book I, Book II style h2 headers (e.g. Against Celsus).
    """
    roman = {"I":1,"II":2,"III":3,"IV":4,"V":5,"VI":6,"VII":7,"VIII":8,
             "IX":9,"X":10,"XI":11,"XII":12}
    print(f"    {url}")
    html = fetch(url)
    time.sleep(DELAY)
    if not html:
        return {}

    body = strip_boilerplate_head(html)
    parts = re.split(r"<h2[^>]*>", body, flags=re.IGNORECASE)
    result = {}
    for part in parts[1:]:
        end = part.find("</h2>")
        header = clean(part[:end]) if end > 0 else ""
        # Match "Book I", "Book II", etc.
        m = re.search(r"\bBook\s+([IVX]+)\b", header, re.IGNORECASE)
        if not m:
            m = re.search(r"\b([IVX]+)\b", header)
        if not m:
            continue
        num_str = m.group(1).upper()
        num = roman.get(num_str, 0)
        if num == 0:
            continue
        body_html = part[end+5:] if end > 0 else part
        paras = get_paras(body_html)
        if paras:
            result[str(num)] = numbered(paras)
    return result


# ════════════════════════════════════════════════════════════════════════════════
# Per-author repair functions
# ════════════════════════════════════════════════════════════════════════════════

def repair_athanasius(books: dict) -> dict:
    print("  Repairing Athanasius...")
    repairs = {
        "On the Decrees of Nicaea": "2804",
        "Apologia Contra Arianos":  "2810",
        "De Sententia Dionysii":    "2808",
        "Ad Afros":                 "2821",
        "On the Councils":          "2820",
    }
    for work, code in repairs.items():
        if not books.get(work):
            result = fetch_page_smart(na_url(code))
            if result:
                books[work] = result
                print(f"    ✓ {work}: {len(result)} chapters")

    # Fix Life of Antony — re-fetch and parse properly
    print("    Re-fetching Life of Antony (2811)...")
    html = fetch(na_url("2811"))
    time.sleep(DELAY)
    if html:
        body = strip_boilerplate_head(html)
        paras = get_paras(body)
        sections = split_by_inline_chapters(paras)
        if sections:
            books["Life of Antony"] = sections
            print(f"    ✓ Life of Antony: {len(sections)} sections")

    # Letters
    if not books.get("Letters of Athanasius"):
        letters = {}
        # Fetch index to get letter links
        html_idx = fetch(na_url("2822"))
        time.sleep(DELAY)
        if html_idx:
            links = re.findall(r'/fathers/(\w+)\.htm', html_idx)
            seen = set()
            letter_codes = []
            for lnk in links:
                if lnk != "2822" and lnk not in seen:
                    seen.add(lnk)
                    letter_codes.append(lnk)
            for i, code in enumerate(letter_codes[:60], 1):
                html_l = fetch(na_url(code))
                time.sleep(DELAY)
                if html_l:
                    paras = get_paras(strip_boilerplate_head(html_l))
                    if paras:
                        letters[str(i)] = numbered(paras)
        if letters:
            books["Letters of Athanasius"] = letters
            print(f"    ✓ Letters of Athanasius: {len(letters)} letters")

    return books


def repair_gregory_of_nyssa(books: dict) -> dict:
    print("  Repairing Gregory of Nyssa...")
    repairs = {
        "On the Soul and the Resurrection": "2915",
        "The Great Catechism":              "2908",
        "On the Making of Man":             "2914",
        "On the Holy Spirit":               "2903",
        "On the Faith":                     "2906",
        "Not Three Gods":                   "2905",
        "On the Holy Trinity":              "2904",
        "On Pilgrimages":                   "2913",
        "On Infant's Early Deaths":         "2912",
        "On the Baptism of Christ":         "2910",
        "Funeral Oration on Meletius":      "2909",
    }
    for work, code in repairs.items():
        if not books.get(work):
            result = fetch_page_smart(na_url(code))
            if result:
                books[work] = result
                print(f"    ✓ {work}: {len(result)} chapters")
    return books


def repair_origen(books: dict) -> dict:
    print("  Repairing Origen...")
    # Against Celsus — uses Book I/II Roman numeral h2 headers
    if not books.get("Against Celsus"):
        result = fetch_roman_numeral_page(na_url("0416"))
        if result:
            books["Against Celsus"] = result
            print(f"    ✓ Against Celsus: {len(result)} books")

    # On Prayer (Pearse) — was fetched wrong code
    print("    Re-fetching On Prayer (Pearse)...")
    html = fetch(pearse_url("origen_on_prayer_02_text"))
    time.sleep(DELAY)
    if html:
        body = strip_boilerplate_head(html)
        paras = get_paras(body)
        # Filter Pearse citation header
        paras = [p for p in paras if not p.startswith("Origen, On Prayer")]
        sections = split_by_inline_chapters(paras)
        if sections:
            books["On Prayer"] = sections
            print(f"    ✓ On Prayer: {len(sections)} sections")

    return books


def repair_augustine(books: dict) -> dict:
    print("  Repairing Augustine...")
    repairs = {
        "On Christian Doctrine":      [("1209{}", range(1, 5))],
        "On the Spirit and the Letter": [("1501", None)],
        "Retractions":                [("1120", None)],
    }

    # On Christian Doctrine — 4 books
    if not books.get("On Christian Doctrine"):
        result = {}
        for bk in range(1, 5):
            work = fetch_page_smart(na_url(f"1209{bk}"), f"{bk}.")
            result.update(work)
        if result:
            books["On Christian Doctrine"] = result
            print(f"    ✓ On Christian Doctrine: {len(result)} chapters")

    # On the Spirit and the Letter
    if not books.get("On the Spirit and the Letter"):
        result = fetch_page_smart(na_url("1501"))
        if result:
            books["On the Spirit and the Letter"] = result
            print(f"    ✓ On the Spirit and the Letter: {len(result)} chapters")

    # Retractions
    if not books.get("Retractions"):
        result = fetch_page_smart(na_url("1120"))
        if result:
            books["Retractions"] = result
            print(f"    ✓ Retractions: {len(result)} chapters")

    # Enchiridion — re-fetch the proper NA version (not Pearse)
    print("    Re-fetching Enchiridion from NewAdvent (1302)...")
    result = fetch_page_smart(na_url("1302"))
    if result:
        books["Enchiridion"] = result
        print(f"    ✓ Enchiridion: {len(result)} chapters")

    # On Free Will — 3 books (15021-15023)
    if not books.get("On Free Will"):
        result = {}
        for bk in range(1, 4):
            work = fetch_page_smart(na_url(f"1502{bk}"), f"{bk}.")
            result.update(work)
        if result:
            books["On Free Will"] = result
            print(f"    ✓ On Free Will: {len(result)} chapters")

    return books


def repair_jerome(books: dict) -> dict:
    print("  Repairing Jerome...")
    repairs = {
        "Lives of Illustrious Men":     "3010",
        "Against Helvidius":            "3007",
        "Against the Luciferians":      "3011",
        "On Perpetual Virginity of Mary": "3008",
    }
    for work, code in repairs.items():
        if not books.get(work):
            result = fetch_page_smart(na_url(code))
            if result:
                books[work] = result
                print(f"    ✓ {work}: {len(result)} chapters")
    return books


def repair_tertullian(books: dict) -> dict:
    print("  Repairing Tertullian...")
    # On Prayer (0323) and On Modesty (0324) got wrong content
    fixes = {
        "On Prayer":    "0323",
        "On Modesty":   "0324",
    }
    for work, code in fixes.items():
        result = fetch_page_smart(na_url(code))
        if result:
            books[work] = result
            print(f"    ✓ {work}: {len(result)} chapters (re-fetched)")
    return books


def repair_clement(books: dict) -> dict:
    print("  Repairing Clement of Alexandria...")
    # Exhortation to the Heathen (0208)
    if not books.get("Exhortation to the Heathen"):
        result = fetch_page_smart(na_url("0208"))
        if result:
            books["Exhortation to the Heathen"] = result
            print(f"    ✓ Exhortation to the Heathen: {len(result)} chapters")
    return books


def repair_basil(books: dict) -> dict:
    print("  Repairing Basil the Great...")
    # Letters — fetch index links
    if not books.get("Letters of Basil"):
        letters = {}
        html_idx = fetch(na_url("3204"))
        time.sleep(DELAY)
        if html_idx:
            links = re.findall(r'/fathers/(\w+)\.htm', html_idx)
            seen = set()
            letter_codes = []
            for lnk in links:
                if lnk != "3204" and lnk not in seen:
                    seen.add(lnk)
                    letter_codes.append(lnk)
            for i, code in enumerate(letter_codes, 1):
                html_l = fetch(na_url(code))
                time.sleep(DELAY)
                if html_l:
                    paras = get_paras(strip_boilerplate_head(html_l))
                    if paras:
                        letters[str(i)] = numbered(paras)
        if letters:
            books["Letters of Basil"] = letters
            print(f"    ✓ Letters of Basil: {len(letters)} letters")
    return books


def repair_gregory_great(books: dict) -> dict:
    print("  Repairing Gregory the Great...")
    # Pastoral Rule — 4 parts: 35011-35014
    if not books.get("Pastoral Rule"):
        result = {}
        for bk in range(1, 5):
            work = fetch_page_smart(na_url(f"3501{bk}"), f"{bk}.")
            result.update(work)
        if result:
            books["Pastoral Rule"] = result
            print(f"    ✓ Pastoral Rule: {len(result)} chapters")
    return books


# ── Main ────────────────────────────────────────────────────────────────────────

REPAIRS = {
    "athanasius":            repair_athanasius,
    "gregory_of_nyssa":      repair_gregory_of_nyssa,
    "origen":                repair_origen,
    "augustine":             repair_augustine,
    "jerome":                repair_jerome,
    "tertullian":            repair_tertullian,
    "clement_of_alexandria": repair_clement,
    "basil_the_great":       repair_basil,
    "gregory_the_great":     repair_gregory_great,
}

def main():
    data_dir = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else pathlib.Path("data/patristics")
    targets = sys.argv[2:] if len(sys.argv) > 2 else []

    for slug, repair_fn in REPAIRS.items():
        if targets and not any(t in slug for t in targets):
            continue
        path = data_dir / f"{slug}.json"
        if not path.exists():
            print(f"  SKIP (not found): {path}")
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        books = data.get("books", {})
        books = repair_fn(books)
        data["books"] = books
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"  Saved {path.name}")

    print("\nDone.")

if __name__ == "__main__":
    main()
