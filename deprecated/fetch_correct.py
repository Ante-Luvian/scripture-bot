#!/usr/bin/env python3
"""
fetch_correct.py  —  fetches missing works with VERIFIED correct URLs.

Run:
    python3 fetch_correct.py data\\patristics
    python3 fetch_correct.py data\\patristics augustine
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
    """Fetch one NA page, try h2-split then inline-number split then flat."""
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

    # Inline-number split
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

def fetch_against_celsus():
    roman = {r: i for i, r in enumerate(
        ["I","II","III","IV","V","VI","VII","VIII"], 1)}
    print(f"    {na('0416')}")
    html = fetch(na("0416"))
    time.sleep(DELAY)
    if not html: return {}
    body = strip_footer(html)
    parts = re.split(r"<h2[^>]*>", body, flags=re.IGNORECASE)
    result = {}
    for part in parts[1:]:
        end = part.find("</h2>")
        header = hclean(part[:end]) if end > 0 else ""
        m = re.search(r"\bBook\s+([IVX]+)\b", header, re.IGNORECASE) or \
            re.match(r"([IVX]+)\.?\s*$", header.strip())
        if not m: continue
        book_num = roman.get(m.group(1).upper(), 0)
        if not book_num: continue
        paras = get_paras(part[end+5:] if end > 0 else part)
        if not paras: continue
        sections, cur, lines = {}, None, []
        for para in paras:
            sm = re.match(r"^(\d+)\.\s+", para)
            if sm:
                if cur is not None and lines:
                    sections[f"{book_num}.{cur}"] = numbered(lines)
                cur = int(sm.group(1)); lines = [para]
            else:
                if cur is None: cur = 1
                lines.append(para)
        if cur is not None and lines:
            sections[f"{book_num}.{cur}"] = numbered(lines)
        result.update(sections if sections else {str(book_num): numbered(paras)})
    return result

MISSING_ORATIONS = [4,5,6,9,10,11,13,14,15,17,19,20,22,23,24,25,26,32,35,36,44]

# ── Per-author tasks ───────────────────────────────────────────────────────────

TASKS = {
    "augustine": [
        # On Christian Doctrine: VERIFIED 12020 (preface), 12021-12024 (books 1-4)
        ("On Christian Doctrine", lambda: {
            **fetch_page(na("12020"), "Pref."),
            **fetch_page(na("12021"), "1."),
            **fetch_page(na("12022"), "2."),
            **fetch_page(na("12023"), "3."),
            **fetch_page(na("12024"), "4."),
        }),
        # On the Spirit and the Letter: VERIFIED 1502.htm
        ("On the Spirit and the Letter", lambda: fetch_page(na("1502"))),
        # On Free Will (De libero arbitrio): NOT on NewAdvent as standalone.
        # Retractions: NOT on NewAdvent as standalone.
        # Skipping both — not available as complete texts on NA.
    ],
    "chrysostom": [
        # Titus: VERIFIED 23081-23086
        ("Homilies on Titus", lambda: {
            str(hom): numbered(get_paras(strip_footer(fetch(na(f"2308{hom}")) or "")))
            for hom in range(1, 7)
            if fetch(na(f"2308{hom}")) and get_paras(strip_footer(fetch(na(f"2308{hom}")) or ""))
        }),
        # Philemon: VERIFIED 23091-23093
        ("Homilies on Philemon", lambda: {
            str(hom): numbered(get_paras(strip_footer(fetch(na(f"2309{hom}")) or "")))
            for hom in range(1, 4)
            if fetch(na(f"2309{hom}")) and get_paras(strip_footer(fetch(na(f"2309{hom}")) or ""))
        }),
        # Statues: VERIFIED 19011-19021 (index is 1901, not 1902)
        ("Homilies on the Statues", lambda: {
            str(hom): numbered(get_paras(strip_footer(fetch(na(f"1901{hom}")) or "")))
            for hom in range(1, 22)
            if fetch(na(f"1901{hom}")) and get_paras(strip_footer(fetch(na(f"1901{hom}")) or ""))
        }),
    ],
    "clement_of_alexandria": [
        # Exhortation: 0208.htm
        ("Exhortation to the Heathen", lambda: fetch_page(na("0208"))),
    ],
    "gregory_the_great": [
        # Pastoral Rule: 35011-35014
        ("Pastoral Rule", lambda: {
            **fetch_page(na("35011"), "1."),
            **fetch_page(na("35012"), "2."),
            **fetch_page(na("35013"), "3."),
            **fetch_page(na("35014"), "4."),
        }),
    ],
    "jerome": [
        # Against the Luciferians: 3011.htm
        ("Against the Luciferians", lambda: fetch_page(na("3011"))),
    ],
    "athanasius": [
        # De Sententia Dionysii: 2808.htm
        ("De Sententia Dionysii", lambda: fetch_page(na("2808"))),
        # Letters: index at 2822
        ("Letters of Athanasius", lambda: fetch_index_letters("2822")),
    ],
    "basil_the_great": [
        # Letters: index at 3204
        ("Letters of Basil", lambda: fetch_index_letters("3204")),
    ],
    "origen": [
        # Against Celsus: 0416.htm (Roman numeral Book I-VIII headers)
        ("Against Celsus", fetch_against_celsus),
        # On Prayer: Pearse
        ("On Prayer", lambda: (lambda html: (
            {"1": numbered([p for p in get_paras(strip_footer(html))
                           if not p.startswith("[Translated by")])}
            if html else {}
        ))(fetch("https://www.ccel.org/ccel/pearse/morefathers/files/origen_on_prayer_02_text.htm"))),
    ],
    "tertullian": [
        # On the Veiling of Virgins: 0327.htm
        ("On the Veiling of Virgins", lambda: fetch_page(na("0327"))),
    ],
    "john_of_damascus": [
        # Philosophical Chapters: 3303.htm
        ("Philosophical Chapters", lambda: fetch_page(na("3303"))),
    ],
}

def fetch_chrysostom_series(base, count):
    """Fetch homily series properly with delays between each."""
    result = {}
    for hom in range(1, count + 1):
        url = na(f"{base}{hom}")
        print(f"    {url}")
        html = fetch(url)
        time.sleep(DELAY)
        if html:
            paras = get_paras(strip_footer(html))
            if paras:
                result[str(hom)] = numbered(paras)
    return result

def main():
    data_dir = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else pathlib.Path("data/patristics")
    targets  = sys.argv[2:] if len(sys.argv) > 2 else []

    # Gregory Nazianzen missing orations
    if not targets or any(t in "gregory_nazianzen" for t in targets):
        path = data_dir / "gregory_nazianzen.json"
        if path.exists():
            print("\ngregory_nazianzen")
            data  = json.loads(path.read_text(encoding="utf-8"))
            books = data.get("books", {})
            orat  = books.get("Orations", {})
            missing = [n for n in MISSING_ORATIONS if str(n) not in orat]
            if missing:
                print(f"  Fetching {len(missing)} missing orations")
                for or_num in missing:
                    r = fetch_page(na(f"3102{or_num:02d}"))
                    if r:
                        all_paras = [p for ch in r.values() for p in ch.values()]
                        if all_paras:
                            orat[str(or_num)] = numbered(all_paras)
                            print(f"    ✓ Oration {or_num}: {len(all_paras)} paras")
                        else:
                            print(f"    ✗ Oration {or_num}: empty")
                    else:
                        print(f"    ✗ Oration {or_num}: failed")
                books["Orations"] = orat
                data["books"] = books
                path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"  → Orations: {len(orat)}/45")

    # Chrysostom needs special handling (lambdas with fetch calls inside don't delay properly)
    if not targets or any(t in "chrysostom" for t in targets):
        path = data_dir / "chrysostom.json"
        if path.exists():
            print("\nchrysostom")
            data  = json.loads(path.read_text(encoding="utf-8"))
            books = data.get("books", {})
            changed = False
            for work, base, count in [
                ("Homilies on Titus",       "2308", 6),
                ("Homilies on Philemon",    "2309", 3),
                ("Homilies on the Statues", "1901", 21),  # FIXED: 1901 not 1902
            ]:
                if sum(len(v) for v in books.get(work, {}).values()) > 10:
                    print(f"  SKIP {work} (already populated)")
                    continue
                print(f"  Fetching {work}...")
                r = fetch_chrysostom_series(base, count)
                if r:
                    books[work] = r
                    print(f"  ✓ {work}: {len(r)} homilies")
                    changed = True
                else:
                    print(f"  ✗ {work}: failed")
            if changed:
                data["books"] = books
                path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            total = sum(len(v) for bk in books.values() for v in bk.values())
            print(f"  → {len(books)} works, {total} paras")

    # All other tasks
    for slug, task_list in TASKS.items():
        if slug == "chrysostom": continue  # already handled
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
                    print(f"  ✗ {work_name}: fetched but empty")
            else:
                print(f"  ✗ {work_name}: failed")
        if changed:
            data["books"] = books
            path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        total = sum(len(v) for bk in books.values() for v in bk.values())
        print(f"  → {len(books)} works, {total} paras")

    print("\nNotes:")
    print("  - 'On Free Will' (De libero arbitrio) is NOT on NewAdvent as standalone text")
    print("  - 'Retractions' is NOT on NewAdvent as standalone text")
    print("  - These two are simply not available from this source")
    print("\nDone.")

if __name__ == "__main__":
    main()
