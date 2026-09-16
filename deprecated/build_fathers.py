#!/usr/bin/env python3
"""
build_fathers.py — Church Fathers corpus builder
=================================================
Fetches from NewAdvent.org (ANF/NPNF) and CCEL/Pearse.

Run:  python3 build_fathers.py [author_slug ...]
      python3 build_fathers.py               # all 15
      python3 build_fathers.py augustine     # just Augustine

Output: data/patristics/<author>.json
"""

import json, re, time, pathlib, urllib.request, html as html_mod
from typing import Optional

OUT_DIR = pathlib.Path("data/patristics")
OUT_DIR.mkdir(parents=True, exist_ok=True)

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; ScriptureBot/2.0)"}
DELAY = 1.2   # seconds between requests

# ── Core utilities ─────────────────────────────────────────────────────────────

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

def extract_body(html: str) -> str:
    """Strip NewAdvent boilerplate before/after main content."""
    for cut in ["Source. Translated", "MARIÆ IMMACULATÆ", "Contact information",
                "Copyright © 20", "Back to Top", "<address"]:
        idx = html.find(cut)
        if idx > 2000:  # don't cut if it appears in the first 2000 chars (nav)
            html = html[:idx]
    return html

def para_split(html: str) -> list[str]:
    """Extract <p> paragraphs or fall back to double-newline split."""
    paras = re.findall(r"<p[^>]*>(.*?)</p>", html, re.DOTALL|re.IGNORECASE)
    if paras:
        cleaned = [clean(p) for p in paras]
        return [p for p in cleaned if len(p) > 30]
    text = clean(html)
    parts = re.split(r"\n\s*\n", text)
    return [p.strip() for p in parts if len(p.strip()) > 30]

def numbered(paragraphs: list[str]) -> dict:
    return {str(i+1): p for i, p in enumerate(paragraphs)}

def extract_chapters(html: str) -> dict[str, list[str]]:
    """Split page on ## Chapter N or ## Homily N or ## Sermon N headers."""
    body = extract_body(html)
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
        paras = para_split(body_html)
        if paras:
            result[num] = paras
    return result

def na_url(code: str) -> str:
    return f"https://www.newadvent.org/fathers/{code}.htm"

def pearse_url(fn: str) -> str:
    return f"https://www.ccel.org/ccel/pearse/morefathers/files/{fn}.htm"

def save(slug: str, source: str, books: dict):
    path = OUT_DIR / f"{slug}.json"
    path.write_text(json.dumps({"source": source, "books": books},
                               ensure_ascii=False, indent=2), encoding="utf-8")
    total = sum(len(vv) for bk in books.values() for vv in bk.values())
    print(f"  → {path.name}: {len(books)} works, {total} paragraphs")

# ── Fetch helpers ──────────────────────────────────────────────────────────────

def fetch_na_single(code: str, book_prefix: str = "") -> dict:
    """Fetch one NewAdvent page, return {chapter_key: {para_num: text}}."""
    url = na_url(code)
    print(f"    {url}")
    html = fetch(url)
    time.sleep(DELAY)
    if not html:
        return {}
    chapters = extract_chapters(html)
    if book_prefix:
        return {f"{book_prefix}{k}": numbered(v) for k, v in chapters.items()}
    return {k: numbered(v) for k, v in chapters.items()}

def fetch_na_homily_page(code: str, homily_num: int) -> Optional[dict]:
    """Fetch one per-homily page; return {para_num: text} or None."""
    html = fetch(na_url(code))
    time.sleep(DELAY)
    if not html:
        return None
    paras = para_split(extract_body(html))
    return numbered(paras) if paras else None

def fetch_na_index_links(index_code: str) -> list[str]:
    """Fetch an NA index page and extract all /fathers/XXXXX.htm links."""
    html = fetch(na_url(index_code))
    time.sleep(DELAY)
    if not html:
        return []
    links = re.findall(r'/fathers/(\w+)\.htm', html)
    # deduplicate, preserve order, skip the index itself
    seen = set()
    result = []
    for lnk in links:
        if lnk != index_code and lnk not in seen:
            seen.add(lnk)
            result.append(lnk)
    return result

def fetch_pearse(fn: str, book_prefix: str = "") -> dict:
    url = pearse_url(fn)
    print(f"    {url}")
    html = fetch(url)
    time.sleep(DELAY)
    if not html:
        return {}
    chapters = extract_chapters(html)
    if not chapters:
        paras = para_split(extract_body(html))
        if paras:
            return {"1": numbered(paras)}
        return {}
    if book_prefix:
        return {f"{book_prefix}{k}": numbered(v) for k, v in chapters.items()}
    return {k: numbered(v) for k, v in chapters.items()}

def fetch_multibook(codes: list[str], book_prefix_fmt: str = "") -> dict:
    """Fetch multiple per-book pages, combining into one work dict."""
    merged = {}
    for bk, code in enumerate(codes, 1):
        prefix = book_prefix_fmt.format(bk) if book_prefix_fmt else ""
        work = fetch_na_single(code, prefix)
        merged.update(work)
    return merged

def fetch_na_letters(index_code: str, work_name: str = "Letters") -> dict:
    """
    Fetch a letter-collection where the index page lists individual letter links.
    Each letter gets one chapter entry, numbered sequentially.
    """
    links = fetch_na_index_links(index_code)
    result = {}
    for i, link_code in enumerate(links, 1):
        html = fetch(na_url(link_code))
        time.sleep(DELAY)
        if not html:
            continue
        paras = para_split(extract_body(html))
        if paras:
            result[str(i)] = numbered(paras)
    return result

# ══════════════════════════════════════════════════════════════════════════════
# The 15 Fathers
# ══════════════════════════════════════════════════════════════════════════════

def build_clement_of_alexandria():
    print("Building Clement of Alexandria...")
    books = {}
    # Exhortation to the Heathen / Protrepticus (0208)
    books["Exhortation to the Heathen"] = fetch_na_single("0208")
    # The Instructor / Paedagogus — 3 books (02091-02093)
    for bk in range(1, 4):
        for k, v in fetch_na_single(f"0209{bk}", f"{bk}.").items():
            books.setdefault("The Instructor", {})[k] = v
    # Stromateis — 8 books (02101-02108)
    for bk in range(1, 9):
        for k, v in fetch_na_single(f"0210{bk}", f"{bk}.").items():
            books.setdefault("Stromateis", {})[k] = v
    save("clement_of_alexandria",
         "Ante-Nicene Fathers Vol. 2 — trans. Wilson (1885)", books)


def build_tertullian():
    print("Building Tertullian...")
    books = {}
    singles = {
        "Apology": "0301",
        "On the Prescription of Heretics": "0311",
        "On the Soul": "0310",
        "Against Praxeas": "0317",
        "On the Flesh of Christ": "0315",
        "On the Resurrection of the Flesh": "0316",
        "On Baptism": "0321",
        "On Repentance": "0320",
        "On Patience": "0325",
        "On Prayer": "0323",
        "On Idolatry": "0302",
        "Scorpiace": "0319",
        "Against Hermogenes": "0313",
        "On Modesty": "0324",
        "On the Veiling of Virgins": "0327",
    }
    for title, code in singles.items():
        books[title] = fetch_na_single(code)
    # Against Marcion — 5 books
    for bk in range(1, 6):
        for k, v in fetch_na_single(f"0312{bk}", f"{bk}.").items():
            books.setdefault("Against Marcion", {})[k] = v
    save("tertullian",
         "Ante-Nicene Fathers Vols. 3–4 — trans. Holmes (1885)", books)


def build_origen():
    print("Building Origen...")
    books = {}
    # De Principiis: preface + 4 books (04120-04124)
    preface = fetch_na_single("04120")
    if preface:
        books.setdefault("De Principiis", {}).update(
            {f"Pref.{k}": v for k, v in preface.items()})
    for bk in range(1, 5):
        for k, v in fetch_na_single(f"0412{bk}", f"{bk}.").items():
            books.setdefault("De Principiis", {})[k] = v
    # Against Celsus — single page with all 8 books (0416)
    books["Against Celsus"] = fetch_na_single("0416")
    # On Prayer (Pearse)
    work = fetch_pearse("origen_on_prayer_02_text")
    if work:
        books["On Prayer"] = work
    # Philocalia (Pearse)
    work = fetch_pearse("origen_philocalia_02_text")
    if work:
        books["Philocalia"] = work
    save("origen",
         "Ante-Nicene Fathers Vol. 4 — trans. Crombie (1885); Pearse ed.", books)


def build_athanasius():
    print("Building Athanasius...")
    books = {}
    singles = {
        "On the Incarnation": "2802",
        "Against the Heathen": "2801",
        "On the Decrees of Nicaea": "2804",
        "On the Councils": "2820",
        "Life of Antony": "2811",
        "De Sententia Dionysii": "2808",
        "Ad Afros": "2821",
    }
    for title, code in singles.items():
        books[title] = fetch_na_single(code)
    # Apologia Contra Arianos (multi-chapter single page: 2810)
    books["Apologia Contra Arianos"] = fetch_na_single("2810")
    # Four Discourses Against the Arians — 4 books (28161-28164)
    for bk in range(1, 5):
        for k, v in fetch_na_single(f"2816{bk}", f"{bk}.").items():
            books.setdefault("Discourses Against the Arians", {})[k] = v
    # Historia Arianorum (2817)
    books["Historia Arianorum"] = fetch_na_single("2817")
    # Letters — index at 2822
    books["Letters of Athanasius"] = fetch_na_letters("2822")
    save("athanasius",
         "NPNF Series II Vol. 4 — trans. Robertson (1891)", books)


def build_basil():
    print("Building Basil the Great...")
    books = {}
    # Hexaemeron — 9 homilies, each its own page (32011-32019)
    for hom in range(1, 10):
        html = fetch(na_url(f"3201{hom}"))
        time.sleep(DELAY)
        if html:
            paras = para_split(extract_body(html))
            if paras:
                books.setdefault("Hexaemeron", {})[str(hom)] = numbered(paras)
    # On the Holy Spirit (3203)
    books["On the Holy Spirit"] = fetch_na_single("3203")
    # Letters — index at 3204; fetch index links
    books["Letters of Basil"] = fetch_na_letters("3204")
    # Address to Young Men (Pearse)
    work = fetch_pearse("basil_litterature01")
    if work:
        books["Address to Young Men"] = work
    save("basil_the_great",
         "NPNF Series II Vol. 8 — trans. Jackson (1895)", books)


def build_gregory_of_nyssa():
    print("Building Gregory of Nyssa...")
    books = {}
    singles = {
        "On the Soul and the Resurrection": "2915",
        "The Great Catechism": "2908",
        "On the Making of Man": "2914",
        "On the Holy Spirit": "2903",
        "On Virginity": "2907",
        "On the Faith": "2906",
        "Not Three Gods": "2905",
        "On the Holy Trinity": "2904",
        "On Pilgrimages": "2913",
        "On Infant's Early Deaths": "2912",
        "On the Baptism of Christ": "2910",
        "Funeral Oration on Meletius": "2909",
    }
    for title, code in singles.items():
        books[title] = fetch_na_single(code)
    # Against Eunomius — multiple books; fetch index links from 2901
    links = fetch_na_index_links("2901")
    for i, link_code in enumerate(links, 1):
        work = fetch_na_single(link_code, f"{i}.")
        books.setdefault("Against Eunomius", {}).update(work)
    # Life of Macrina (Pearse)
    work = fetch_pearse("gregory_macrina_1_life")
    if work:
        books["Life of Macrina"] = work
    # Letters
    books["Letters of Gregory of Nyssa"] = fetch_na_letters("2911")
    save("gregory_of_nyssa",
         "NPNF Series II Vol. 5 — trans. Moore & Wilson (1893)", books)


def build_gregory_nazianzen():
    print("Building Gregory Nazianzen...")
    books = {}
    # 45 Orations — each at 3102{NN}
    for or_num in range(1, 46):
        code = f"3102{or_num:02d}"
        html = fetch(na_url(code))
        time.sleep(DELAY)
        if html:
            paras = para_split(extract_body(html))
            if paras:
                books.setdefault("Orations", {})[str(or_num)] = numbered(paras)
    # Letters — index at 3103
    books["Letters of Gregory Nazianzen"] = fetch_na_letters("3103")
    # Orations Against Julian (Pearse: Oration 4 & 5)
    for or_num, fn in [(4, "gregory_nazianzen_2_oration4"),
                       (5, "gregory_nazianzen_3_oration5")]:
        work = fetch_pearse(fn)
        if work:
            for k, v in work.items():
                books.setdefault("Orations Against Julian", {})[f"{or_num}.{k}"] = v
    save("gregory_nazianzen",
         "NPNF Series II Vol. 7 — trans. Browne & Swallow (1894)", books)


def build_chrysostom():
    print("Building John Chrysostom...")
    books = {}

    def fetch_homily_series(base: str, count: int, title: str):
        for hom in range(1, count + 1):
            code = f"{base}{hom:02d}"
            html = fetch(na_url(code))
            time.sleep(DELAY)
            if html:
                paras = para_split(extract_body(html))
                if paras:
                    books.setdefault(title, {})[str(hom)] = numbered(paras)

    # Homilies on Matthew — 90 homilies at 200101-200190
    fetch_homily_series("2001", 90, "Homilies on Matthew")
    # Homilies on John — 88 homilies at 240101-240188
    fetch_homily_series("2401", 88, "Homilies on John")
    # Homilies on Acts — 55 homilies at 210101-210155
    fetch_homily_series("2101", 55, "Homilies on Acts")
    # Homilies on Romans — 32 homilies at 210201-210232
    fetch_homily_series("2102", 32, "Homilies on Romans")
    # Homilies on 1 Corinthians — 44 homilies at 220101-220144
    fetch_homily_series("2201", 44, "Homilies on 1 Corinthians")
    # Homilies on 2 Corinthians — 30 homilies at 220201-220230
    fetch_homily_series("2202", 30, "Homilies on 2 Corinthians")
    # Homilies on Ephesians — 24 homilies at 230101-230124
    fetch_homily_series("2301", 24, "Homilies on Ephesians")
    # Homilies on Philippians — 15 homilies at 230201-230215
    fetch_homily_series("2302", 15, "Homilies on Philippians")
    # Homilies on Colossians — 12 homilies at 230301-230312
    fetch_homily_series("2303", 12, "Homilies on Colossians")
    # Homilies on 1 Thessalonians — 11 homilies at 230401-230411
    fetch_homily_series("2304", 11, "Homilies on 1 Thessalonians")
    # Homilies on 1 Timothy — 18 homilies at 230601-230618
    fetch_homily_series("2306", 18, "Homilies on 1 Timothy")
    # Homilies on 2 Timothy — 10 homilies at 230701-230710
    fetch_homily_series("2307", 10, "Homilies on 2 Timothy")
    # Homilies on Titus — 6 homilies at 230801-230806
    fetch_homily_series("2308", 6, "Homilies on Titus")
    # Homilies on Philemon — 3 homilies at 230901-230903
    fetch_homily_series("2309", 3, "Homilies on Philemon")
    # Homilies on Hebrews — 34 homilies at 240201-240234
    fetch_homily_series("2402", 34, "Homilies on Hebrews")
    # Homilies on the Statues — 21 homilies at 190201-190221
    fetch_homily_series("1902", 21, "Homilies on the Statues")
    # On the Priesthood — 6 books at 19221-19226
    for bk in range(1, 7):
        for k, v in fetch_na_single(f"1922{bk}", f"{bk}.").items():
            books.setdefault("On the Priesthood", {})[k] = v
    save("chrysostom",
         "NPNF Series I Vols. 9–14 — trans. various (1889)", books)


def build_augustine():
    print("Building Augustine of Hippo...")
    books = {}

    def fetch_aug_books(prefix: str, count: int, title: str, bp_fmt: str = "{}."):
        for bk in range(1, count + 1):
            bp = bp_fmt.format(bk)
            for k, v in fetch_na_single(f"{prefix}{bk:02d}", bp).items():
                books.setdefault(title, {})[k] = v

    fetch_aug_books("1101", 13, "Confessions")
    fetch_aug_books("1201", 22, "City of God")
    fetch_aug_books("1301", 15, "On the Trinity")
    books["Enchiridion"] = fetch_na_single("1302")
    books["On Christian Doctrine"] = {}
    for bk in range(1, 5):
        for k, v in fetch_na_single(f"1209{bk}", f"{bk}.").items():
            books["On Christian Doctrine"][k] = v
    # Letters — index page 1102; individual letters at 1102{NNN}
    books["Letters of Augustine"] = fetch_na_letters("1102")
    books["On the Morals of the Catholic Church"] = fetch_na_single("1401")
    books["On Nature and Grace"] = fetch_na_single("1503")
    books["On the Spirit and the Letter"] = fetch_na_single("1501")
    books["Retractions"] = fetch_na_single("1120")
    # On Free Will (3 books: 15021-15023)
    for bk in range(1, 4):
        for k, v in fetch_na_single(f"1502{bk}", f"{bk}.").items():
            books.setdefault("On Free Will", {})[k] = v
    # Enchiridion also via Pearse (backup fill-in)
    pearse_enchir = fetch_pearse("augustine_enchiridion_02_trans")
    if pearse_enchir and not books.get("Enchiridion"):
        books["Enchiridion"] = pearse_enchir
    save("augustine",
         "NPNF Series I Vols. 1–8 — trans. various (1887–1888)", books)


def build_jerome():
    print("Building Jerome...")
    books = {}
    # Letters — index at 3001; individual letters at 3001{NNN}
    books["Letters"] = fetch_na_letters("3001")
    singles = {
        "Lives of Illustrious Men": "3010",
        "Against Helvidius": "3007",
        "Against the Luciferians": "3011",
        "On Perpetual Virginity of Mary": "3008",
    }
    for title, code in singles.items():
        books[title] = fetch_na_single(code)
    # Against Jovinianus — 2 books (30091-30092)
    for bk in range(1, 3):
        for k, v in fetch_na_single(f"3009{bk}", f"{bk}.").items():
            books.setdefault("Against Jovinianus", {})[k] = v
    # Against the Pelagians — 3 books (30131-30133)
    for bk in range(1, 4):
        for k, v in fetch_na_single(f"3013{bk}", f"{bk}.").items():
            books.setdefault("Against the Pelagians", {})[k] = v
    # Commentary on Daniel (Pearse)
    work = fetch_pearse("jerome_daniel_02_text")
    if work:
        books["Commentary on Daniel"] = work
    save("jerome",
         "NPNF Series II Vol. 6 — trans. Fremantle (1893); Pearse ed.", books)


def build_cyril_of_alexandria():
    print("Building Cyril of Alexandria... (Pearse/CCEL)")
    books = {}
    # Against Nestorius — 5 books
    for bk in range(1, 6):
        work = fetch_pearse(f"cyril_against_nestorius_0{bk}_book{bk}")
        if work:
            for k, v in work.items():
                books.setdefault("Against Nestorius", {})[f"{bk}.{k}"] = v
    # Commentary on John — 12 books
    for bk in range(1, 13):
        work = fetch_pearse(f"cyril_on_john_{bk:02d}_book{bk}")
        if work:
            for k, v in work.items():
                books.setdefault("Commentary on John", {})[f"{bk}.{k}"] = v
    # Commentary on Luke — 14 parts (confirmed filenames)
    luke_files = [
        ("01", "sermons_01_11"), ("02", "sermons_12_25"),
        ("03", "sermons_26_38"), ("04", "sermons_39_46"),
        ("05", "sermons_47_56"), ("06", "sermons_57_65"),
        ("07", "sermons_66_80"), ("08", "sermons_81_88"),
        ("09", "sermons_89_98"), ("10", "sermons_99_109"),
        ("11", "sermons_110_123"), ("12", "sermons_124_134"),
        ("13", "sermons_135_145"), ("14", "sermons_146_156"),
    ]
    for pt, srange in luke_files:
        work = fetch_pearse(f"cyril_on_luke_{pt}_{srange}")
        if work:
            for k, v in work.items():
                books.setdefault("Commentary on Luke", {})[f"{pt}.{k}"] = v
    # That Christ is One
    work = fetch_pearse("cyril_christ_is_one_01_text")
    if work:
        books["That Christ is One"] = work
    # Scholia on the Incarnation
    work = fetch_pearse("cyril_scholia_incarnation_01_text")
    if work:
        books["Scholia on the Incarnation"] = work
    # Against Julian (partial)
    work = fetch_pearse("cyril_against_julian_02_book2")
    if work:
        books["Against Julian"] = work
    save("cyril_of_alexandria",
         "Pearse / CCEL More Fathers — trans. Pusey (1874–1885)", books)


def build_leo_the_great():
    print("Building Leo the Great...")
    books = {}
    # Sermons — index at 3603; individual sermons at 3603{NN}
    # Fetch index to get exact links
    links = fetch_na_index_links("3603")
    if not links:
        # Try fetching sermons directly: 360301-360396
        for serm in range(1, 97):
            code = f"3603{serm:02d}"
            html = fetch(na_url(code))
            time.sleep(DELAY)
            if html:
                paras = para_split(extract_body(html))
                if paras:
                    books.setdefault("Sermons", {})[str(serm)] = numbered(paras)
    else:
        for i, link_code in enumerate(links, 1):
            html = fetch(na_url(link_code))
            time.sleep(DELAY)
            if html:
                paras = para_split(extract_body(html))
                if paras:
                    books.setdefault("Sermons", {})[str(i)] = numbered(paras)
    # Letters — index at 3604
    books["Letters of Leo"] = fetch_na_letters("3604")
    save("leo_the_great",
         "NPNF Series II Vol. 12 — trans. Feltoe (1895)", books)


def build_john_of_damascus():
    print("Building John of Damascus...")
    books = {}
    # Exposition of the Orthodox Faith — 4 books (33041-33044)
    for bk in range(1, 5):
        for k, v in fetch_na_single(f"3304{bk}", f"{bk}.").items():
            books.setdefault("Exposition of the Orthodox Faith", {})[k] = v
    # Philosophical Chapters / Dialectica (3303)
    books["Philosophical Chapters"] = fetch_na_single("3303")
    # On Holy Images — 3 treatises (index at 3301)
    links = fetch_na_index_links("3301")
    for idx, link_code in enumerate(links[:3], 1):
        work = fetch_na_single(link_code, f"{idx}.")
        books.setdefault("On Holy Images", {}).update(work)
    save("john_of_damascus",
         "NPNF Series II Vol. 9 — trans. Watson & Pullan (1899)", books)


def build_ephrem_the_syrian():
    print("Building Ephrem the Syrian... (Pearse/CCEL)")
    books = {}
    # Discourses to Hypatius (vol 1)
    for disc in range(1, 6):
        work = fetch_pearse(f"ephraim1_{disc}_hypatius{disc}")
        if work:
            for k, v in work.items():
                books.setdefault("Discourses to Hypatius", {})[f"{disc}.{k}"] = v
    # Vol 2: Against Bardaisan, Marcion, Mani
    pearse_works = [
        ("ephraim2_1_bardesan",  "Against Bardaisan"),
        ("ephraim2_2_marcion1",  "Against Marcion"),
        ("ephraim2_3_marcion2",  "Against Marcion"),
        ("ephraim2_4_marcion3",  "Against Marcion"),
        ("ephraim2_7_mani",      "Against Mani"),
        ("ephraim2_6_virginity", "On Virginity"),
    ]
    marcion_bk = 1
    for fn, title in pearse_works:
        work = fetch_pearse(fn)
        if not work:
            continue
        if title == "Against Marcion":
            for k, v in work.items():
                books.setdefault(title, {})[f"{marcion_bk}.{k}"] = v
            marcion_bk += 1
        else:
            books.setdefault(title, {}).update(work)
    # NewAdvent: Nisibene Hymns (3801), Homilies on Our Lord (3803)
    for title, code in [("Nisibene Hymns", "3801"), ("Homilies on Our Lord", "3803")]:
        work = fetch_na_single(code)
        if work:
            books[title] = work
    save("ephrem_the_syrian",
         "NPNF Series II Vol. 13 (partial); Pearse / CCEL — trans. Mitchell (1912–21)", books)


def build_gregory_the_great():
    print("Building Gregory the Great...")
    books = {}
    # Dialogues — 4 books (Pearse: confirmed filenames)
    for bk in range(1, 5):
        fn = f"gregory_0{bk}_dialogues_book{bk}"
        work = fetch_pearse(fn)
        if not work:
            # try alternate padding
            fn = f"gregory_{bk:02d}_dialogues_book{bk}"
            work = fetch_pearse(fn)
        if work:
            for k, v in work.items():
                books.setdefault("Dialogues", {})[f"{bk}.{k}"] = v
    # Pastoral Rule — index at 3501 (NPNF has it)
    for bk in range(1, 5):
        work = fetch_na_single(f"3501{bk}", f"{bk}.")
        if work:
            books.setdefault("Pastoral Rule", {}).update(work)
    # Letters (Registrum Epistolarum) — index at 3602
    # Individual letters have complex URLs like 360201001
    # Use index page to extract links
    books["Letters of Gregory the Great"] = fetch_na_letters("3602")
    save("gregory_the_great",
         "NPNF Series II Vols. 12–13 — trans. various (1895); Pearse ed.", books)


# ══════════════════════════════════════════════════════════════════════════════

ALL_BUILDERS = [
    ("clement_of_alexandria", build_clement_of_alexandria),
    ("tertullian",            build_tertullian),
    ("origen",                build_origen),
    ("athanasius",            build_athanasius),
    ("basil_the_great",       build_basil),
    ("gregory_of_nyssa",      build_gregory_of_nyssa),
    ("gregory_nazianzen",     build_gregory_nazianzen),
    ("chrysostom",            build_chrysostom),
    ("augustine",             build_augustine),
    ("jerome",                build_jerome),
    ("cyril_of_alexandria",   build_cyril_of_alexandria),
    ("leo_the_great",         build_leo_the_great),
    ("john_of_damascus",      build_john_of_damascus),
    ("ephrem_the_syrian",     build_ephrem_the_syrian),
    ("gregory_the_great",     build_gregory_the_great),
]

if __name__ == "__main__":
    import sys
    targets = sys.argv[1:]
    for slug, builder in ALL_BUILDERS:
        if not targets or slug in targets or any(t in slug for t in targets):
            try:
                builder()
            except Exception as e:
                print(f"ERROR building {slug}: {e}")
                import traceback; traceback.print_exc()
    print("\nDone.")
