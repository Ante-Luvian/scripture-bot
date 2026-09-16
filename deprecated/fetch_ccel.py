#!/usr/bin/env python3
"""
fetch_ccel.py  —  fetches missing works from CCEL as alternative to NewAdvent.

CCEL hosts the same ANF/NPNF translations at ccel.org/ccel/schaff/
Works that failed from NewAdvent due to blocking.

Run:
    python3 fetch_ccel.py data\\patristics
    python3 fetch_ccel.py data\\patristics augustine   # one author
"""

import json, re, sys, time, pathlib, urllib.request, html as html_mod
from typing import Optional

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; research-bot/1.0)"}
DELAY = 1.5

def fetch(url: str) -> Optional[str]:
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=25) as r:
            return r.read().decode("utf-8", errors="replace")
    except Exception as e:
        print(f"    ERROR {url}: {e}")
        return None

def hclean(h: str) -> str:
    h = re.sub(r"<a\b[^>]*>(.*?)</a>", r"\1", h, flags=re.DOTALL|re.IGNORECASE)
    h = re.sub(r"<[^>]+>", " ", h)
    h = html_mod.unescape(h)
    return re.sub(r"\s+", " ", h).strip()

BAD = (
    "Please help support",
    "Click here to see the list",
    "Source. Translated by",
    "This file is part of the Christian Classics",
    "This document is from the Christian Classics",
    "CCEL",
)

def is_bad(t: str) -> bool:
    return len(t) < 30 or any(t.startswith(b) for b in BAD)

def strip_nav(html: str) -> str:
    # Cut at common footer markers
    for cut in ["Previous sectionNext section", "This document is from",
                "Christian Classics Ethereal Library", "Send a message"]:
        idx = html.find(cut)
        if idx > 5000:
            html = html[:idx]
    return html

def get_paras(html: str) -> list:
    raw = re.findall(r"<p[^>]*>(.*?)</p>", html, re.DOTALL|re.IGNORECASE)
    result = []
    for p in raw:
        t = hclean(p)
        if not is_bad(t):
            result.append(t)
    return result

def numbered(paras: list) -> dict:
    return {str(i+1): p for i, p in enumerate(paras)}

def fetch_and_split(url: str, book_prefix: str = "") -> dict:
    """Fetch a CCEL page and split by headers or inline numbers."""
    print(f"    {url}")
    html = fetch(url)
    time.sleep(DELAY)
    if not html:
        return {}
    body = strip_nav(html)

    # Try h3/h4 section splits (CCEL uses these for chapters)
    for htag in ["h3", "h4", "h2"]:
        parts = re.split(rf"<{htag}[^>]*>", body, flags=re.IGNORECASE)
        if len(parts) < 3:
            continue
        result = {}
        for part in parts[1:]:
            end = part.find(f"</{htag}>")
            header = hclean(part[:end]) if end > 0 else ""
            m = re.search(r"(\d+)", header)
            if not m:
                continue
            paras = get_paras(part[end+5:] if end > 0 else part)
            if paras:
                key = f"{book_prefix}{m.group(1)}" if book_prefix else m.group(1)
                result[key] = numbered(paras)
        if result:
            return result

    # Fall back to inline numbers
    paras = get_paras(body)
    if not paras:
        return {}
    sections, cur_sec, cur_lines = {}, None, []
    for para in paras:
        m = re.match(r"^(\d+)\.\s+", para)
        if m:
            if cur_sec is not None and cur_lines:
                sections[str(cur_sec)] = numbered(cur_lines)
            cur_sec = int(m.group(1)); cur_lines = [para]
        else:
            if cur_sec is None: cur_sec = 1
            cur_lines.append(para)
    if cur_sec is not None and cur_lines:
        sections[str(cur_sec)] = numbered(cur_lines)
    if sections:
        if book_prefix:
            sections = {f"{book_prefix}{k}": v for k, v in sections.items()}
        return sections

    return {"1": numbered(paras)} if paras else {}

# CCEL URL patterns
# ANF = Ante-Nicene Fathers: ccel.org/ccel/schaff/anf0N.html (N=vol)
# NPNF1 = Nicene & Post-Nicene, Series 1: ccel.org/ccel/schaff/npnf1NN
# NPNF2 = Nicene & Post-Nicene, Series 2: ccel.org/ccel/schaff/npnf2NN

def ccel(path): return f"https://ccel.org/ccel/{path}"

# ── Fetch functions per work ───────────────────────────────────────────────────

def fetch_augustine_on_christian_doctrine():
    """NPNF1-02, On Christian Doctrine — 4 books"""
    # Each book is a separate page on CCEL
    result = {}
    book_paths = [
        "schaff/npnf102.iv.ii.html",   # Book 1
        "schaff/npnf102.iv.iii.html",  # Book 2
        "schaff/npnf102.iv.iv.html",   # Book 3
        "schaff/npnf102.iv.v.html",    # Book 4
    ]
    for bk, path in enumerate(book_paths, 1):
        work = fetch_and_split(ccel(path), f"{bk}.")
        if not work:
            # Try alternate indexing
            work = fetch_and_split(ccel(f"schaff/npnf102.iv.ii.i.html"), f"{bk}.")
        result.update(work)
    return result

def fetch_augustine_on_free_will():
    """ANF Vol 5, On Free Choice of the Will"""
    result = {}
    for bk in range(1, 4):
        work = fetch_and_split(ccel(f"schaff/anf05.ix.iii.{bk}.html"), f"{bk}.")
        result.update(work)
    return result

def fetch_augustine_spirit_letter():
    """NPNF1-05, On the Spirit and the Letter"""
    return fetch_and_split(ccel("schaff/npnf105.vii.html"))

def fetch_augustine_retractions():
    """NPNF1-01, Retractions"""
    result = {}
    for bk in [1, 2]:
        work = fetch_and_split(ccel(f"schaff/npnf101.xii.{bk}.html"), f"{bk}.")
        result.update(work)
    return result

def fetch_basil_letters():
    """NPNF2-08, Letters of Basil — index page"""
    # Try index page first
    base = "https://ccel.org/ccel/schaff/npnf208.xi"
    result = {}
    # Basil's letters are numbered; fetch from index
    html_idx = fetch(ccel("schaff/npnf208.xi.html"))
    time.sleep(DELAY)
    if html_idx:
        # Extract letter links
        links = re.findall(r'href="([^"]+\.html)"', html_idx)
        letter_links = [l for l in links if re.search(r'\.\d+\.html$', l)]
        for i, link in enumerate(letter_links[:366], 1):
            url = f"https://ccel.org/ccel/{link}" if not link.startswith("http") else link
            html_l = fetch(url)
            time.sleep(DELAY)
            if html_l:
                paras = get_paras(strip_nav(html_l))
                if paras:
                    result[str(i)] = numbered(paras)
    return result

def fetch_chrysostom_titus():
    """NPNF1-13, Homilies on Titus"""
    result = {}
    for hom in range(1, 7):
        work = fetch_and_split(ccel(f"schaff/npnf113.viii.{hom}.html"))
        if work:
            result[str(hom)] = list(work.values())[0]
    return result

def fetch_chrysostom_philemon():
    """NPNF1-13, Homilies on Philemon"""
    result = {}
    for hom in range(1, 4):
        work = fetch_and_split(ccel(f"schaff/npnf113.ix.{hom}.html"))
        if work:
            result[str(hom)] = list(work.values())[0]
    return result

def fetch_chrysostom_statues():
    """NPNF1-09, Homilies on the Statues"""
    result = {}
    for hom in range(1, 22):
        work = fetch_and_split(ccel(f"schaff/npnf109.v.{hom}.html"))
        if work:
            result[str(hom)] = list(work.values())[0]
    return result

def fetch_clement_exhortation():
    """ANF Vol 2, Exhortation to the Heathen"""
    result = {}
    for ch in range(1, 13):
        work = fetch_and_split(ccel(f"schaff/anf02.vi.ii.{ch}.html"))
        result.update(work)
    if not result:
        result = fetch_and_split(ccel("schaff/anf02.vi.ii.html"))
    return result

def fetch_gregory_great_pastoral_rule():
    """NPNF2-12, Pastoral Rule"""
    result = {}
    parts = [
        ("schaff/npnf212.iii.html", "1."),
        ("schaff/npnf212.iv.html",  "2."),
        ("schaff/npnf212.v.html",   "3."),
        ("schaff/npnf212.vi.html",  "4."),
    ]
    for path, prefix in parts:
        work = fetch_and_split(ccel(path), prefix)
        result.update(work)
    return result

def fetch_jerome_against_luciferians():
    """NPNF2-06, Against the Luciferians"""
    return fetch_and_split(ccel("schaff/npnf206.vi.html"))

def fetch_athanasius_de_sententia():
    """NPNF2-04, De Sententia Dionysii"""
    return fetch_and_split(ccel("schaff/npnf204.xiv.html"))

def fetch_athanasius_letters():
    """NPNF2-04, Letters of Athanasius"""
    result = {}
    # Letters are scattered across the volume; try the letters index
    html_idx = fetch(ccel("schaff/npnf204.vi.html"))
    time.sleep(DELAY)
    if html_idx:
        links = re.findall(r'href="(npnf204\.vi\.\d+\.html)"', html_idx)
        for i, link in enumerate(links, 1):
            html_l = fetch(ccel(f"schaff/{link}"))
            time.sleep(DELAY)
            if html_l:
                paras = get_paras(strip_nav(html_l))
                if paras:
                    result[str(i)] = numbered(paras)
    return result

def fetch_origen_against_celsus():
    """ANF Vol 4, Against Celsus — 8 books"""
    result = {}
    book_paths = [
        "schaff/anf04.vi.iii.i.html",
        "schaff/anf04.vi.iii.ii.html",
        "schaff/anf04.vi.iii.iii.html",
        "schaff/anf04.vi.iii.iv.html",
        "schaff/anf04.vi.iii.v.html",
        "schaff/anf04.vi.iii.vi.html",
        "schaff/anf04.vi.iii.vii.html",
        "schaff/anf04.vi.iii.viii.html",
    ]
    for bk, path in enumerate(book_paths, 1):
        work = fetch_and_split(ccel(path), f"{bk}.")
        result.update(work)
    return result

def fetch_origen_on_prayer():
    """ANF Vol 4, On Prayer"""
    return fetch_and_split(ccel("schaff/anf04.vi.v.html"))

def fetch_tertullian_veiling():
    """ANF Vol 4, On the Veiling of Virgins"""
    result = {}
    for ch in range(1, 18):
        work = fetch_and_split(ccel(f"schaff/anf04.iv.x.{ch}.html"))
        result.update(work)
    if not result:
        result = fetch_and_split(ccel("schaff/anf04.iv.x.html"))
    return result

def fetch_gregory_naz_missing_orations(orat: dict) -> dict:
    """NPNF2-07, missing orations"""
    # CCEL oration paths: schaff/npnf207.ii.N.html
    missing = [n for n in [4,5,6,9,10,11,13,14,15,17,19,20,
                            22,23,24,25,26,32,35,36,44]
               if str(n) not in orat]
    print(f"    Fetching {len(missing)} missing orations from CCEL")
    for or_num in missing:
        work = fetch_and_split(ccel(f"schaff/npnf207.ii.{or_num}.html"))
        if work:
            # Flatten to single oration entry
            all_paras = []
            for v in work.values():
                all_paras.extend(v.values())
            if all_paras:
                orat[str(or_num)] = numbered(all_paras)
                print(f"      ✓ Oration {or_num}: {len(all_paras)} paras")
        else:
            print(f"      ✗ Oration {or_num}: failed")
    return orat

# ── Dispatch ───────────────────────────────────────────────────────────────────

TASKS = {
    "augustine": [
        ("On Christian Doctrine",      fetch_augustine_on_christian_doctrine),
        ("On Free Will",               fetch_augustine_on_free_will),
        ("On the Spirit and the Letter", fetch_augustine_spirit_letter),
        ("Retractions",                fetch_augustine_retractions),
    ],
    "basil_the_great": [
        ("Letters of Basil",           fetch_basil_letters),
    ],
    "chrysostom": [
        ("Homilies on Titus",          fetch_chrysostom_titus),
        ("Homilies on Philemon",       fetch_chrysostom_philemon),
        ("Homilies on the Statues",    fetch_chrysostom_statues),
    ],
    "clement_of_alexandria": [
        ("Exhortation to the Heathen", fetch_clement_exhortation),
    ],
    "gregory_the_great": [
        ("Pastoral Rule",              fetch_gregory_great_pastoral_rule),
    ],
    "jerome": [
        ("Against the Luciferians",    fetch_jerome_against_luciferians),
    ],
    "athanasius": [
        ("De Sententia Dionysii",      fetch_athanasius_de_sententia),
        ("Letters of Athanasius",      fetch_athanasius_letters),
    ],
    "origen": [
        ("Against Celsus",             fetch_origen_against_celsus),
        ("On Prayer",                  fetch_origen_on_prayer),
    ],
    "tertullian": [
        ("On the Veiling of Virgins",  fetch_tertullian_veiling),
    ],
}

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
            missing = [n for n in [4,5,6,9,10,11,13,14,15,17,19,20,
                                   22,23,24,25,26,32,35,36,44]
                       if str(n) not in orat]
            if missing:
                books["Orations"] = fetch_gregory_naz_missing_orations(orat)
                data["books"] = books
                path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            total = sum(len(v) for bk in books.values() for v in bk.values())
            print(f"  → Orations now has {len(books['Orations'])} entries, {total} total paras")

    for slug, task_list in TASKS.items():
        if targets and not any(t in slug for t in targets):
            continue
        path = data_dir / f"{slug}.json"
        if not path.exists():
            print(f"SKIP: {path}")
            continue
        print(f"\n{slug}")
        data  = json.loads(path.read_text(encoding="utf-8"))
        books = data.get("books", {})
        changed = False
        for work_name, fetch_fn in task_list:
            existing_p = sum(len(v) for v in books.get(work_name, {}).values())
            if existing_p > 10:
                print(f"  SKIP {work_name} (already {existing_p} paras)")
                continue
            print(f"  Fetching {work_name}...")
            result = fetch_fn()
            if result:
                n_p = sum(len(v) for v in result.values())
                books[work_name] = result
                print(f"  ✓ {work_name}: {len(result)} chapters, {n_p} paras")
                changed = True
            else:
                print(f"  ✗ {work_name}: failed")
        if changed:
            data["books"] = books
            path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        total = sum(len(v) for bk in books.values() for v in bk.values())
        print(f"  → {len(books)} works, {total} paras")

    print("\nDone.")

if __name__ == "__main__":
    main()
