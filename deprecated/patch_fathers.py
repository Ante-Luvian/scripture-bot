#!/usr/bin/env python3
"""
patch_fathers.py  —  final single-pass repair for all 15 patristics JSONs.

Issues fixed WITHOUT network:
  - Strip "Source. Translated by..." tail paragraphs throughout
  - Strip Pearse footer ("This text was reformatted by Roger Pearse")
  - Enchiridion: strip front-matter paras, split on inline section numbers
  - Clement Exhortation: only a table-of-contents; mark as index text
  - Origen On Prayer: strip intro/footer, keep only real content
  - Greg Nyssa Pilgrimages/Funeral Oration: strip Source para
  - Tertullian Apology/Praxeas etc: 1-para/chap is FINE — leave alone

Issues fixed WITH network:
  - Corrupt (cardinal-electors / pope-election promo): re-fetch entirely
      Augustine: On Christian Doctrine, On Free Will, Retractions,
                 On the Spirit and the Letter
      Chrysostom: Homilies on Titus, Philemon, Statues
      Gregory the Great: Pastoral Rule
      Jerome: Against the Luciferians
      Athanasius: De Sententia Dionysii
  - Wrong content: re-fetch with correct URL
      Tertullian: On Prayer (0323), On Modesty (0324)
  - Empty: fetch fresh
      Tertullian: On the Veiling of Virgins (0327)
      John of Damascus: Philosophical Chapters (3303)
      Origen: Against Celsus (0416, Roman-numeral parser)
      Basil: Letters of Basil (index 3204)
      Athanasius: Letters of Athanasius (index 2822)

Run:
    python3 patch_fathers.py data\\patristics
    python3 patch_fathers.py data\\patristics augustine   # one author
"""

import json, re, sys, time, pathlib, urllib.request, html as html_mod
from typing import Optional

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; ScriptureBot/2.0)"}
DELAY = 1.2

# ── Boilerplate strings ────────────────────────────────────────────────────────

CORRUPT_STARTS = (
    "Click here to see the list of",   # pope-election promo
)
STRIP_STARTS = (
    "Please help support the mission of New Advent",
    "How Catholic Underground",
    "Source. Translated by",
    "This text was reformatted by Roger Pearse",
    "Contact Us | Advertise",
)

def is_corrupt_para(t: str) -> bool:
    return any(t.startswith(b) for b in CORRUPT_STARTS)

def is_strip_para(t: str) -> bool:
    return any(t.startswith(b) for b in STRIP_STARTS)

def is_bad_para(t: str) -> bool:
    return is_corrupt_para(t) or is_strip_para(t)

def all_chapters_corrupt(chapters: dict) -> bool:
    if not chapters:
        return False
    return all(is_corrupt_para(v.get("1", "")) for v in chapters.values())

def strip_bad_paras(para_dict: dict) -> dict:
    """Remove bad paragraphs and renumber."""
    def sort_key(k):
        try:
            return int(k)
        except ValueError:
            return 0
    kept = []
    for k in sorted(para_dict.keys(), key=sort_key):
        t = para_dict[k].strip()
        if t and not is_bad_para(t):
            kept.append(t)
    return {str(i+1): t for i, t in enumerate(kept)}

def clean_work(chapters: dict) -> dict:
    """Strip bad paras from a single work's chapter dict."""
    result = {}
    for k, v in chapters.items():
        if isinstance(v, dict):
            cleaned = strip_bad_paras(v)
            if cleaned:
                result[k] = cleaned
    return result

def clean_books(books: dict) -> dict:
    """Strip bad paras from all works in a books dict."""
    return {wname: clean_work(chaps) for wname, chaps in books.items()}

# ── Network ────────────────────────────────────────────────────────────────────

def fetch(url: str) -> Optional[str]:
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.read().decode("utf-8", errors="replace")
    except Exception as e:
        print(f"    FETCH ERROR {url}: {e}")
        return None

def html_clean(h: str) -> str:
    h = re.sub(r"<a\b[^>]*>(.*?)</a>", r"\1", h, flags=re.DOTALL|re.IGNORECASE)
    h = re.sub(r"<[^>]+>", " ", h)
    h = html_mod.unescape(h)
    return re.sub(r"\s+", " ", h).strip()

def strip_footer(html: str) -> str:
    for cut in ["Source. Translated", "MARIÆ IMMACULATÆ",
                "This text was reformatted by Roger Pearse",
                "Contact information", "Copyright © 20"]:
        idx = html.find(cut)
        if idx > 3000:
            html = html[:idx]
    return html

def get_paras(html: str) -> list:
    raw = re.findall(r"<p[^>]*>(.*?)</p>", html, re.DOTALL|re.IGNORECASE)
    result = []
    for p in raw:
        t = html_clean(p)
        if len(t) >= 30 and not is_bad_para(t):
            result.append(t)
    return result

def numbered(paras: list) -> dict:
    return {str(i+1): p for i, p in enumerate(paras)}

def na(code): return f"https://www.newadvent.org/fathers/{code}.htm"
def pearse(fn): return f"https://www.ccel.org/ccel/pearse/morefathers/files/{fn}.htm"

def fetch_smart(url: str, book_prefix: str = "") -> dict:
    """Fetch + try h2-split, then inline-number split, then flat."""
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
        header = html_clean(part[:end]) if end > 0 else ""
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
    sections = {}
    current_sec, current_lines = None, []
    for para in paras:
        m = re.match(r"^(\d+)\.\s+(.+)", para, re.DOTALL)
        if m:
            if current_sec is not None and current_lines:
                sections[str(current_sec)] = numbered(current_lines)
            current_sec = int(m.group(1))
            current_lines = [para]
        else:
            if current_sec is None:
                current_sec = 1
            current_lines.append(para)
    if current_sec is not None and current_lines:
        sections[str(current_sec)] = numbered(current_lines)
    if sections:
        if book_prefix:
            sections = {f"{book_prefix}{k}": v for k, v in sections.items()}
        return sections

    return {"1": numbered(paras)}

def fetch_homily_series(base: str, count: int) -> dict:
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
            seen.add(lnk)
            codes.append(lnk)
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
    """0416 uses Book I/II Roman numeral h2s with inline numbered sections within."""
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
        header = html_clean(part[:end]) if end > 0 else ""
        m = re.search(r"\bBook\s+([IVX]+)\b", header, re.IGNORECASE)
        if not m:
            m = re.search(r"^([IVX]+)$", header.strip())
        if not m:
            continue
        book_num = roman.get(m.group(1).upper(), 0)
        if not book_num:
            continue
        body_html = part[end+5:] if end > 0 else part
        paras = get_paras(body_html)
        if not paras:
            continue
        # Try to split by inline section numbers within the book
        sections = {}
        current_sec, current_lines = None, []
        for para in paras:
            sm = re.match(r"^(\d+)\.\s+(.+)", para, re.DOTALL)
            if sm:
                if current_sec is not None and current_lines:
                    sections[f"{book_num}.{current_sec}"] = numbered(current_lines)
                current_sec = int(sm.group(1))
                current_lines = [para]
            else:
                if current_sec is None:
                    current_sec = 1
                current_lines.append(para)
        if current_sec is not None and current_lines:
            sections[f"{book_num}.{current_sec}"] = numbered(current_lines)
        result.update(sections if sections else {str(book_num): numbered(paras)})
    return result

# ── Enchiridion special handling ───────────────────────────────────────────────

def restructure_enchiridion(chapters: dict) -> dict:
    """
    Enchiridion is flat (1 chapter, 127 paras).
    Paras 0-3 are front-matter notes from the 1955 translator.
    Actual Augustine starts at "I cannot express..." — keep flat but strip front matter.
    """
    if not chapters or "1" not in chapters:
        return chapters
    all_paras = [chapters["1"][k] for k in sorted(chapters["1"].keys(), key=int)]

    # Drop front-matter paras (translator intro notes before Augustine speaks)
    content = []
    found_start = False
    for p in all_paras:
        if not found_start:
            if re.match(r"^(I cannot express|The true wisdom|Now if I should|You are anxious)", p, re.IGNORECASE):
                found_start = True
        if found_start and not is_bad_para(p):
            content.append(p)

    if not content:
        content = all_paras  # fallback: keep everything

    return {"1": numbered(content)}

# ── Per-author patch functions ─────────────────────────────────────────────────

def patch_augustine(books):
    # Enchiridion: restructure
    books["Enchiridion"] = restructure_enchiridion(books.get("Enchiridion", {}))
    n = len(books["Enchiridion"])
    print(f"    ✓ Enchiridion restructured: {n} sections")

    # Corrupt works: re-fetch
    corrupt_refetch = {
        "On Christian Doctrine":       [("1209{}", 4)],
        "On Free Will":                [("1502{}", 3)],
    }
    for work, specs in corrupt_refetch.items():
        if all_chapters_corrupt(books.get(work, {})):
            result = {}
            code_tmpl, count = specs[0]
            for bk in range(1, count + 1):
                r = fetch_smart(na(code_tmpl.format(bk)), f"{bk}.")
                result.update(r)
            if result:
                books[work] = result
                print(f"    ✓ {work}: {len(result)} chapters")

    # On the Spirit and the Letter: was Source-only
    if all_chapters_corrupt(books.get("On the Spirit and the Letter", {})) or \
       sum(len(v) for v in books.get("On the Spirit and the Letter", {}).values()) <= 2:
        r = fetch_smart(na("1501"))
        if r:
            books["On the Spirit and the Letter"] = r
            print(f"    ✓ On the Spirit and the Letter: {len(r)} chapters")

    # Retractions: corrupt
    if all_chapters_corrupt(books.get("Retractions", {})):
        r = fetch_smart(na("1120"))
        if r:
            books["Retractions"] = r
            print(f"    ✓ Retractions: {len(r)} chapters")

    return clean_books(books)  # strip any remaining bad paras globally


def patch_tertullian(books):
    # On Prayer: wrong content (To the Martyrs / Passion of Perpetua)
    op = books.get("On Prayer", {})
    p1 = next(iter(next(iter(op.values()), {}).values()), "") if op else ""
    if "Blessed Martyrs Designate" in p1 or "provision which our lady mother" in p1:
        r = fetch_smart(na("0323"))
        if r:
            books["On Prayer"] = r
            print(f"    ✓ On Prayer (correct text): {len(r)} chapters")

    # On Modesty: wrong content (Passion of Perpetua)
    om = books.get("On Modesty", {})
    p1 = next(iter(next(iter(om.values()), {}).values()), "") if om else ""
    if "young catechumens" in p1 or "Revocatus" in p1:
        r = fetch_smart(na("0324"))
        if r:
            books["On Modesty"] = r
            print(f"    ✓ On Modesty (correct text): {len(r)} chapters")

    # On the Veiling of Virgins: empty
    if not books.get("On the Veiling of Virgins"):
        r = fetch_smart(na("0327"))
        if r:
            books["On the Veiling of Virgins"] = r
            print(f"    ✓ On the Veiling of Virgins: {len(r)} chapters")

    return clean_books(books)


def patch_origen(books):
    # Against Celsus: empty
    if not books.get("Against Celsus"):
        r = fetch_against_celsus()
        if r:
            books["Against Celsus"] = r
            print(f"    ✓ Against Celsus: {len(r)} sections")

    # On Prayer: only 2 paras (intro line + Pearse footer), need real content
    op = books.get("On Prayer", {})
    total_p = sum(len(v) for v in op.values())
    if total_p <= 3:
        # The Pearse file is a translation preface + actual text
        # Strip the intro line and footer, keep the rest
        html = fetch(pearse("origen_on_prayer_02_text"))
        time.sleep(DELAY)
        if html:
            body = strip_footer(html)
            paras = get_paras(body)
            # Drop lines that are pure header/translator note
            paras = [p for p in paras
                     if not re.match(r"^\[Translated by", p)
                     and not p.startswith("Origen, On Prayer")]
            if paras:
                # Try inline split
                sections = {}
                cur_sec, cur_lines = None, []
                for para in paras:
                    sm = re.match(r"^(\d+)\.\s+(.+)", para, re.DOTALL)
                    if sm:
                        if cur_sec is not None and cur_lines:
                            sections[str(cur_sec)] = numbered(cur_lines)
                        cur_sec = int(sm.group(1))
                        cur_lines = [para]
                    else:
                        if cur_sec is None:
                            cur_sec = 1
                        cur_lines.append(para)
                if cur_sec is not None and cur_lines:
                    sections[str(cur_sec)] = numbered(cur_lines)
                books["On Prayer"] = sections if len(sections) > 1 else {"1": numbered(paras)}
                print(f"    ✓ On Prayer: {len(books['On Prayer'])} sections")

    return clean_books(books)


def patch_chrysostom(books):
    # Titus, Philemon, Statues: all corrupt — re-fetch
    refetch = {
        "Homilies on Titus":       ("2308", 6),
        "Homilies on Philemon":    ("2309", 3),
        "Homilies on the Statues": ("1902", 21),
    }
    for work, (base, count) in refetch.items():
        if all_chapters_corrupt(books.get(work, {})):
            r = fetch_homily_series(base, count)
            if r:
                books[work] = r
                print(f"    ✓ {work}: {len(r)} homilies")

    return clean_books(books)


def patch_john_of_damascus(books):
    if not books.get("Philosophical Chapters"):
        r = fetch_smart(na("3303"))
        if r:
            books["Philosophical Chapters"] = r
            print(f"    ✓ Philosophical Chapters: {len(r)} chapters")
    return clean_books(books)


def patch_basil(books):
    if not books.get("Letters of Basil"):
        print("    Fetching Letters of Basil (index 3204)...")
        r = fetch_index_letters("3204")
        if r:
            books["Letters of Basil"] = r
            print(f"    ✓ Letters of Basil: {len(r)} letters")
    return clean_books(books)


def patch_athanasius(books):
    # De Sententia Dionysii: Source-only
    dsd = books.get("De Sententia Dionysii", {})
    if all_chapters_corrupt(dsd) or sum(len(v) for v in dsd.values()) <= 2:
        r = fetch_smart(na("2808"))
        if r:
            books["De Sententia Dionysii"] = r
            print(f"    ✓ De Sententia Dionysii: {len(r)} chapters")

    # Letters: empty
    if not books.get("Letters of Athanasius"):
        print("    Fetching Letters of Athanasius (index 2822)...")
        r = fetch_index_letters("2822")
        if r:
            books["Letters of Athanasius"] = r
            print(f"    ✓ Letters of Athanasius: {len(r)} letters")

    return clean_books(books)


def patch_clement(books):
    # Exhortation: only 2 paras (chapter listing + Source line) — re-fetch
    ext = books.get("Exhortation to the Heathen", {})
    total_p = sum(len(v) for v in ext.values())
    if total_p <= 3:
        r = fetch_smart(na("0208"))
        if r:
            books["Exhortation to the Heathen"] = r
            print(f"    ✓ Exhortation to the Heathen: {len(r)} chapters")
    return clean_books(books)


def patch_jerome(books):
    # Against the Luciferians: Source-only
    atl = books.get("Against the Luciferians", {})
    if all_chapters_corrupt(atl) or sum(len(v) for v in atl.values()) <= 2:
        r = fetch_smart(na("3011"))
        if r:
            books["Against the Luciferians"] = r
            print(f"    ✓ Against the Luciferians: {len(r)} chapters")
    return clean_books(books)


def patch_gregory_great(books):
    # Pastoral Rule: all corrupt
    if all_chapters_corrupt(books.get("Pastoral Rule", {})):
        result = {}
        for bk in range(1, 5):
            r = fetch_smart(na(f"3501{bk}"), f"{bk}.")
            result.update(r)
        if result:
            books["Pastoral Rule"] = result
            print(f"    ✓ Pastoral Rule: {len(result)} chapters")
    return clean_books(books)


def patch_generic(books):
    """Just strip bad paras — no refetch needed."""
    return clean_books(books)


# ── Dispatch ───────────────────────────────────────────────────────────────────

PATCHERS = {
    "augustine":             patch_augustine,
    "tertullian":            patch_tertullian,
    "origen":                patch_origen,
    "chrysostom":            patch_chrysostom,
    "john_of_damascus":      patch_john_of_damascus,
    "basil_the_great":       patch_basil,
    "athanasius":            patch_athanasius,
    "clement_of_alexandria": patch_clement,
    "jerome":                patch_jerome,
    "gregory_the_great":     patch_gregory_great,
    # Generic strip only:
    "gregory_of_nyssa":      patch_generic,
    "gregory_nazianzen":     patch_generic,
    "ephrem_the_syrian":     patch_generic,
    "cyril_of_alexandria":   patch_generic,
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
            print(f"SKIP (not found): {path}")
            continue
        print(f"\n{slug}")
        data  = json.loads(path.read_text(encoding="utf-8"))
        books = patcher(data.get("books", {}))
        data["books"] = books
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        total = sum(len(v) for bk in books.values() for v in bk.values())
        print(f"  → {len(books)} works, {total} paragraphs")

    print("\nDone.")


if __name__ == "__main__":
    main()
