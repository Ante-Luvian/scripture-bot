#!/usr/bin/env python3
"""
fetch_missing.py  —  fetches the 10 works that are still empty/wrong.

These failed in the sandbox due to IP blocking. Run this locally.

    python3 fetch_missing.py data\\patristics

Works targeted:
  Athanasius:       De Sententia Dionysii (2808), Letters (index 2822)
  Augustine:        On Christian Doctrine (12091-4), On Free Will (15021-3),
                    On the Spirit and the Letter (1501), Retractions (1120)
  Basil:            Letters (index 3204)
  Chrysostom:       Homilies on Titus (230801-06), Philemon (230901-03),
                    Statues (190201-21)
  Clement:          Exhortation to the Heathen (0208)  [real multi-chapter page]
  Gregory Great:    Pastoral Rule (35011-4)
  Gregory Nazianzen:21 missing Orations (310204-310244 selectively)
  Jerome:           Against the Luciferians (3011)
  John Damascus:    Philosophical Chapters (3303)
  Origen:           Against Celsus (0416), On Prayer (Pearse)
  Tertullian:       On the Veiling of Virgins (0327)
"""

import json, re, sys, time, pathlib, urllib.request, html as html_mod
from typing import Optional

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; ScriptureBot/2.0)"}
DELAY = 1.0   # be polite

def fetch(url: str) -> Optional[str]:
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=20) as r:
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
    "Please help support the mission of New Advent",
    "How Catholic Underground",
    "Click here to see the list of",
    "Source. Translated by",
    "Contact Us | Advertise",
    "This text was reformatted by Roger Pearse",
    "[Translated by William",
    "Origen, On Prayer",
)

def is_bad(t: str) -> bool:
    return any(t.startswith(b) for b in BAD)

def strip_footer(html: str) -> str:
    for cut in ["Source. Translated", "This text was reformatted by Roger Pearse",
                "Contact information", "Copyright © 20"]:
        idx = html.find(cut)
        if idx > 3000:
            html = html[:idx]
    return html

def get_paras(html: str) -> list:
    raw = re.findall(r"<p[^>]*>(.*?)</p>", html, re.DOTALL|re.IGNORECASE)
    return [hclean(p) for p in raw if len(hclean(p)) >= 30 and not is_bad(hclean(p))]

def numbered(paras: list) -> dict:
    return {str(i+1): p for i, p in enumerate(paras)}

def na(code): return f"https://www.newadvent.org/fathers/{code}.htm"
def pearse(fn): return f"https://www.ccel.org/ccel/pearse/morefathers/files/{fn}.htm"

def fetch_smart(url: str, book_prefix: str = "") -> dict:
    print(f"    {url}")
    html = fetch(url)
    time.sleep(DELAY)
    if not html: return {}
    body = strip_footer(html)

    # h2 chapter split
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

    return {"1": numbered(paras)}

def fetch_homilies(base: str, count: int) -> dict:
    result = {}
    for hom in range(1, count + 1):
        html = fetch(na(f"{base}{hom:02d}"))
        time.sleep(DELAY)
        if html:
            paras = get_paras(strip_footer(html))
            if paras:
                result[str(hom)] = numbered(paras)
    return result

def fetch_index_letters(index_code: str) -> dict:
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
            if paras:
                result[str(i)] = numbered(paras)
    return result

def fetch_against_celsus() -> dict:
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
        # Sub-split by inline section numbers
        sections, cur_sec, cur_lines = {}, None, []
        for para in paras:
            sm = re.match(r"^(\d+)\.\s+", para)
            if sm:
                if cur_sec is not None and cur_lines:
                    sections[f"{book_num}.{cur_sec}"] = numbered(cur_lines)
                cur_sec = int(sm.group(1)); cur_lines = [para]
            else:
                if cur_sec is None: cur_sec = 1
                cur_lines.append(para)
        if cur_sec is not None and cur_lines:
            sections[f"{book_num}.{cur_sec}"] = numbered(cur_lines)
        result.update(sections if sections else {str(book_num): numbered(paras)})
    return result

def fetch_origen_prayer() -> dict:
    html = fetch(pearse("origen_on_prayer_02_text"))
    time.sleep(DELAY)
    if not html: return {}
    body = strip_footer(html)
    paras = get_paras(body)
    if not paras: return {}
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
    return sections if len(sections) > 1 else ({"1": numbered(paras)} if paras else {})

# ── Missing Orations for Gregory Nazianzen ─────────────────────────────────────

MISSING_ORATIONS = [4,5,6,9,10,11,13,14,15,17,19,20,22,23,24,25,26,32,35,36,44]

def fetch_missing_orations(orat: dict) -> dict:
    for or_num in MISSING_ORATIONS:
        if str(or_num) in orat:
            continue
        html = fetch(na(f"3102{or_num:02d}"))
        time.sleep(DELAY)
        if html:
            paras = get_paras(strip_footer(html))
            if paras:
                orat[str(or_num)] = numbered(paras)
                print(f"      ✓ Oration {or_num}: {len(paras)} paras")
    return orat

# ── Per-file tasks ─────────────────────────────────────────────────────────────

TASKS = {
    "athanasius": [
        ("De Sententia Dionysii", lambda: fetch_smart(na("2808"))),
        ("Letters of Athanasius", lambda: fetch_index_letters("2822")),
    ],
    "augustine": [
        ("On Christian Doctrine", lambda: {
            **fetch_smart(na("12091"), "1."),
            **fetch_smart(na("12092"), "2."),
            **fetch_smart(na("12093"), "3."),
            **fetch_smart(na("12094"), "4."),
        }),
        ("On Free Will", lambda: {
            **fetch_smart(na("15021"), "1."),
            **fetch_smart(na("15022"), "2."),
            **fetch_smart(na("15023"), "3."),
        }),
        ("On the Spirit and the Letter", lambda: fetch_smart(na("1501"))),
        ("Retractions", lambda: fetch_smart(na("1120"))),
    ],
    "basil_the_great": [
        ("Letters of Basil", lambda: fetch_index_letters("3204")),
    ],
    "chrysostom": [
        ("Homilies on Titus",       lambda: fetch_homilies("2308", 6)),
        ("Homilies on Philemon",    lambda: fetch_homilies("2309", 3)),
        ("Homilies on the Statues", lambda: fetch_homilies("1902", 21)),
    ],
    "clement_of_alexandria": [
        ("Exhortation to the Heathen", lambda: fetch_smart(na("0208"))),
    ],
    "gregory_the_great": [
        ("Pastoral Rule", lambda: {
            **fetch_smart(na("35011"), "1."),
            **fetch_smart(na("35012"), "2."),
            **fetch_smart(na("35013"), "3."),
            **fetch_smart(na("35014"), "4."),
        }),
    ],
    "jerome": [
        ("Against the Luciferians", lambda: fetch_smart(na("3011"))),
    ],
    "john_of_damascus": [
        ("Philosophical Chapters", lambda: fetch_smart(na("3303"))),
    ],
    "origen": [
        ("Against Celsus", fetch_against_celsus),
        ("On Prayer",      fetch_origen_prayer),
    ],
    "tertullian": [
        ("On the Veiling of Virgins", lambda: fetch_smart(na("0327"))),
    ],
}

def main():
    data_dir = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else pathlib.Path("data/patristics")
    targets  = sys.argv[2:] if len(sys.argv) > 2 else []

    # Handle Gregory Nazianzen separately (special oration logic)
    if not targets or any(t in "gregory_nazianzen" for t in targets):
        path = data_dir / "gregory_nazianzen.json"
        if path.exists():
            print("\ngregory_nazianzen")
            data  = json.loads(path.read_text(encoding="utf-8"))
            books = data.get("books", {})
            orat  = books.get("Orations", {})
            missing = [n for n in MISSING_ORATIONS if str(n) not in orat]
            if missing:
                print(f"  Fetching {len(missing)} missing orations: {missing}")
                books["Orations"] = fetch_missing_orations(orat)
            else:
                print("  Orations complete — nothing to fetch")
            data["books"] = books
            path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            total = sum(len(v) for bk in books.values() for v in bk.values())
            print(f"  → {len(books)} works, {total} paras")

    # Handle all other tasks
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
            existing = books.get(work_name, {})
            existing_p = sum(len(v) for v in existing.values())
            # Only fetch if empty or trivially small
            if existing_p > 5:
                print(f"  SKIP {work_name} (already has {existing_p} paras)")
                continue
            result = fetch_fn()
            if result:
                books[work_name] = result
                n_ch = len(result)
                n_p  = sum(len(v) for v in result.values())
                print(f"  ✓ {work_name}: {n_ch} chapters, {n_p} paras")
                changed = True
            else:
                print(f"  ✗ {work_name}: fetch failed")
        if changed:
            data["books"] = books
            path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        total = sum(len(v) for bk in books.values() for v in bk.values())
        print(f"  → {len(books)} works, {total} paras")

    print("\nDone.")

if __name__ == "__main__":
    main()
