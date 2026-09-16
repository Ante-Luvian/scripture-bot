#!/usr/bin/env python3
"""
final_patch.py  —  fixes the remaining issues after patch_fathers.py.

NO-NETWORK fixes:
  - Cyril Against Julian: strip Pearse citation p1
  - Gregory Nazianzen Orations: restore missing orations (21 were false-positive stripped)
  - Origen On Prayer: strip translator note, keep content

NETWORK fixes (re-fetch with corrected approach):
  - Augustine: On Christian Doctrine, On Free Will, On the Spirit and Letter, Retractions
  - Chrysostom: Homilies on Titus, Philemon, Statues
  - Gregory Great: Pastoral Rule
  - Jerome: Against the Luciferians
  - Athanasius: De Sententia Dionysii, Letters of Athanasius
  - Basil: Letters of Basil
  - Tertullian: On the Veiling of Virgins
  - Origen: Against Celsus (improved parser)
  - Clement: Exhortation to the Heathen (0208 is a real multi-chapter page)
  - John Damascus: Philosophical Chapters (wrong content — retry 3303)

Run:
    python3 final_patch.py data\\patristics
"""

import json, re, sys, time, pathlib, urllib.request, html as html_mod
from typing import Optional

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; ScriptureBot/2.0)"}
DELAY = 1.2

# ── Helpers ────────────────────────────────────────────────────────────────────

def fetch(url: str) -> Optional[str]:
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.read().decode("utf-8", errors="replace")
    except Exception as e:
        print(f"    FETCH ERROR {url}: {e}")
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
    "Cyril of Alexandria, Against Julian",
    "[Translated by William",
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
    if not html:
        return {}
    body = strip_footer(html)

    # h2 split
    parts = re.split(r"<h2[^>]*>", body, flags=re.IGNORECASE)
    result = {}
    for part in parts[1:]:
        end = part.find("</h2>")
        header = hclean(part[:end]) if end > 0 else ""
        m = re.search(r"(\d+)", header)
        if not m:
            continue
        body_html = part[end+5:] if end > 0 else part
        paras = get_paras(body_html)
        if paras:
            key = f"{book_prefix}{m.group(1)}" if book_prefix else m.group(1)
            result[key] = numbered(paras)
    if result:
        return result

    # inline-number split
    paras = get_paras(body)
    if not paras:
        return {}
    sections, cur_sec, cur_lines = {}, None, []
    for para in paras:
        m = re.match(r"^(\d+)\.\s+", para)
        if m:
            if cur_sec is not None and cur_lines:
                sections[str(cur_sec)] = numbered(cur_lines)
            cur_sec = int(m.group(1))
            cur_lines = [para]
        else:
            if cur_sec is None:
                cur_sec = 1
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
    if not html_idx:
        return {}
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
    """0416: Book I–VIII h2 headers, inline numbered sections within."""
    roman = {r: i for i, r in enumerate(
        ["I","II","III","IV","V","VI","VII","VIII"], 1)}
    print(f"    {na('0416')}")
    html = fetch(na("0416"))
    time.sleep(DELAY)
    if not html:
        return {}
    body = strip_footer(html)
    parts = re.split(r"<h2[^>]*>", body, flags=re.IGNORECASE)
    result = {}
    for part in parts[1:]:
        end = part.find("</h2>")
        header = hclean(part[:end]) if end > 0 else ""
        # Match "Book I", "BOOK II", or bare "I."
        m = re.search(r"\bBook\s+([IVX]+)\b", header, re.IGNORECASE) or \
            re.match(r"([IVX]+)\.?\s*$", header.strip())
        if not m:
            continue
        book_num = roman.get(m.group(1).upper(), 0)
        if not book_num:
            continue
        body_html = part[end+5:] if end > 0 else part
        paras = get_paras(body_html)
        if not paras:
            continue
        # Split by inline section numbers within each book
        sections, cur_sec, cur_lines = {}, None, []
        for para in paras:
            sm = re.match(r"^(\d+)\.\s+", para)
            if sm:
                if cur_sec is not None and cur_lines:
                    sections[f"{book_num}.{cur_sec}"] = numbered(cur_lines)
                cur_sec = int(sm.group(1))
                cur_lines = [para]
            else:
                if cur_sec is None: cur_sec = 1
                cur_lines.append(para)
        if cur_sec is not None and cur_lines:
            sections[f"{book_num}.{cur_sec}"] = numbered(cur_lines)
        result.update(sections if sections else {str(book_num): numbered(paras)})
    return result

# ── No-network fixes ───────────────────────────────────────────────────────────

def fix_cyril_julian(books: dict) -> dict:
    """Strip the Pearse citation from Against Julian para 1."""
    aj = books.get("Against Julian", {})
    for chap_key in list(aj.keys()):
        para_dict = aj[chap_key]
        kept = {str(i+1): v for i, (k, v) in enumerate(
            sorted(para_dict.items(), key=lambda x: int(x[0]))
        ) if not is_bad(v)}
        if kept:
            aj[chap_key] = kept
        else:
            del aj[chap_key]
    books["Against Julian"] = aj
    return books

def fix_origen_prayer(books: dict) -> dict:
    """On Prayer has only the translator intro line — strip it, result will be empty."""
    op = books.get("On Prayer", {})
    # If there's real content beyond the intro, keep it
    total = sum(len(v) for v in op.values())
    if total <= 2:
        books["On Prayer"] = {}  # mark empty; will re-fetch
    return books

def fix_gregory_naz_orations(books: dict, path: pathlib.Path) -> dict:
    """
    The generic clean_books stripped 21 orations as false positives.
    The original uploaded file had 45 orations — read chapter count
    from what we have and note which oration numbers are missing.
    Present keys: 1,2,3,7,8,12,16,18,21,27-31,33,34,37-43,45
    Missing: 4,5,6,9,10,11,13,14,15,17,19,20,22-26,32,35,36,44
    These were stripped because their p1 started with boilerplate.
    We need to re-fetch them individually.
    """
    orat = books.get("Orations", {})
    present = set(int(k) for k in orat.keys())
    all_45 = set(range(1, 46))
    missing = sorted(all_45 - present)
    if not missing:
        return books
    print(f"    Re-fetching {len(missing)} missing Orations: {missing}")
    for or_num in missing:
        code = f"3102{or_num:02d}"
        html = fetch(na(code))
        time.sleep(DELAY)
        if html:
            paras = get_paras(strip_footer(html))
            if paras:
                orat[str(or_num)] = numbered(paras)
                print(f"      ✓ Oration {or_num}: {len(paras)} paras")
    books["Orations"] = orat
    return books

# ── Main patch functions ───────────────────────────────────────────────────────

def patch_cyril(books, path):
    books = fix_cyril_julian(books)
    aj = books.get("Against Julian", {})
    n = sum(len(v) for v in aj.values())
    print(f"    ✓ Against Julian: {n} paras after citation strip")
    return books

def patch_gregory_nazianzen(books, path):
    return fix_gregory_naz_orations(books, path)

def patch_origen(books, path):
    books = fix_origen_prayer(books)
    # Re-fetch On Prayer
    html = fetch(pearse("origen_on_prayer_02_text"))
    time.sleep(DELAY)
    if html:
        body = strip_footer(html)
        paras = [p for p in get_paras(body)
                 if not re.match(r"^\[Translated by", p)]
        if paras:
            # Split on section numbers
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
            result = sections if len(sections) > 1 else {"1": numbered(paras)}
            books["On Prayer"] = result
            print(f"    ✓ On Prayer: {len(result)} sections, {sum(len(v) for v in result.values())} paras")

    # Against Celsus
    if not books.get("Against Celsus"):
        r = fetch_against_celsus()
        if r:
            books["Against Celsus"] = r
            print(f"    ✓ Against Celsus: {len(r)} sections")
    return books

def patch_augustine(books, path):
    refetch = {
        "On Christian Doctrine": ("1209{}", 4),
        "On Free Will":          ("1502{}", 3),
    }
    for work, (tmpl, count) in refetch.items():
        if not books.get(work):
            result = {}
            for bk in range(1, count + 1):
                r = fetch_smart(na(tmpl.format(bk)), f"{bk}.")
                result.update(r)
            if result:
                books[work] = result
                print(f"    ✓ {work}: {len(result)} chapters")

    for work, code in [("On the Spirit and the Letter", "1501"),
                       ("Retractions", "1120")]:
        if not books.get(work):
            r = fetch_smart(na(code))
            if r:
                books[work] = r
                print(f"    ✓ {work}: {len(r)} chapters")
    return books

def patch_chrysostom(books, path):
    refetch = {
        "Homilies on Titus":       ("2308", 6),
        "Homilies on Philemon":    ("2309", 3),
        "Homilies on the Statues": ("1902", 21),
    }
    for work, (base, count) in refetch.items():
        if not books.get(work):
            r = fetch_homilies(base, count)
            if r:
                books[work] = r
                print(f"    ✓ {work}: {len(r)} homilies")
    return books

def patch_gregory_great(books, path):
    if not books.get("Pastoral Rule"):
        result = {}
        for bk in range(1, 5):
            r = fetch_smart(na(f"3501{bk}"), f"{bk}.")
            result.update(r)
        if result:
            books["Pastoral Rule"] = result
            print(f"    ✓ Pastoral Rule: {len(result)} chapters")
    return books

def patch_jerome(books, path):
    if not books.get("Against the Luciferians"):
        r = fetch_smart(na("3011"))
        if r:
            books["Against the Luciferians"] = r
            print(f"    ✓ Against the Luciferians: {len(r)} chapters")
    return books

def patch_athanasius(books, path):
    if not books.get("De Sententia Dionysii"):
        r = fetch_smart(na("2808"))
        if r:
            books["De Sententia Dionysii"] = r
            print(f"    ✓ De Sententia Dionysii: {len(r)} chapters")
    if not books.get("Letters of Athanasius"):
        print("    Fetching Letters of Athanasius (index 2822)...")
        r = fetch_index_letters("2822")
        if r:
            books["Letters of Athanasius"] = r
            print(f"    ✓ Letters of Athanasius: {len(r)} letters")
    return books

def patch_basil(books, path):
    if not books.get("Letters of Basil"):
        print("    Fetching Letters of Basil (index 3204)...")
        r = fetch_index_letters("3204")
        if r:
            books["Letters of Basil"] = r
            print(f"    ✓ Letters of Basil: {len(r)} letters")
    return books

def patch_tertullian(books, path):
    if not books.get("On the Veiling of Virgins"):
        r = fetch_smart(na("0327"))
        if r:
            books["On the Veiling of Virgins"] = r
            print(f"    ✓ On the Veiling of Virgins: {len(r)} chapters")
    return books

def patch_clement(books, path):
    ext = books.get("Exhortation to the Heathen", {})
    total_p = sum(len(v) for v in ext.values())
    if total_p <= 2:
        r = fetch_smart(na("0208"))
        if r:
            books["Exhortation to the Heathen"] = r
            print(f"    ✓ Exhortation to the Heathen: {len(r)} chapters")
    return books

def patch_john_of_damascus(books, path):
    # Current content is wrong (Psalm numbers) — re-fetch
    pc = books.get("Philosophical Chapters", {})
    total_p = sum(len(v) for v in pc.values())
    p1 = ""
    if pc:
        k = list(pc.keys())[0]
        p1 = pc[k].get("1", "")
    if total_p <= 2 or "Psalm" in p1:
        r = fetch_smart(na("3303"))
        if r:
            books["Philosophical Chapters"] = r
            print(f"    ✓ Philosophical Chapters: {len(r)} chapters")
    return books

def patch_generic(books, path):
    return books

# ── Dispatch ───────────────────────────────────────────────────────────────────

PATCHERS = {
    "cyril_of_alexandria":   patch_cyril,
    "gregory_nazianzen":     patch_gregory_nazianzen,
    "origen":                patch_origen,
    "augustine":             patch_augustine,
    "chrysostom":            patch_chrysostom,
    "gregory_the_great":     patch_gregory_great,
    "jerome":                patch_jerome,
    "athanasius":            patch_athanasius,
    "basil_the_great":       patch_basil,
    "tertullian":            patch_tertullian,
    "clement_of_alexandria": patch_clement,
    "john_of_damascus":      patch_john_of_damascus,
    # No changes needed:
    "gregory_of_nyssa":      patch_generic,
    "ephrem_the_syrian":     patch_generic,
    "leo_the_great":         patch_generic,
}

def main():
    data_dir = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else pathlib.Path("data/patristics")
    targets  = sys.argv[2:] if len(sys.argv) > 2 else []

    for slug, patcher in PATCHERS.items():
        if targets and not any(t in slug for t in targets):
            continue
        path = data_dir / f"{slug}.json"
        if not path.exists():
            print(f"SKIP: {path}")
            continue
        print(f"\n{slug}")
        data  = json.loads(path.read_text(encoding="utf-8"))
        books = patcher(data.get("books", {}), path)
        data["books"] = books
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        total = sum(len(v) for bk in books.values() for v in bk.values())
        print(f"  → {len(books)} works, {total} paras")

    print("\nDone.")

if __name__ == "__main__":
    main()
