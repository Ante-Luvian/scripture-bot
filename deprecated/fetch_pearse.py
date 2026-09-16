#!/usr/bin/env python3
"""
fetch_pearse.py — Fetch patristic texts from tertullian.org/fathers (Roger Pearse ed.)
These are out-of-copyright English translations not in the standard ANF/NPNF set.

Run:
    python3 fetch_pearse.py data/patristics
    python3 fetch_pearse.py data/patristics chrysostom   # single author
"""

import json, re, sys, time, pathlib, urllib.request, html as html_mod

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
DELAY = 1.3

def fetch(url):
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=25) as r:
            return r.read().decode("utf-8", errors="replace")
    except Exception as e:
        print(f"    ERROR: {e}")
        return None

def hclean(h):
    h = re.sub(r"<a\b[^>]*>(.*?)</a>", r"\1", h, flags=re.DOTALL|re.IGNORECASE)
    h = re.sub(r"<[^>]+>", " ", h)
    h = html_mod.unescape(h)
    return re.sub(r"\s+", " ", h).strip()

BAD_STARTS = (
    "Footnote", "fn.", "[Footnote", "Back to text",
    "Previous section", "Next section", "Table of Contents",
    "Preface to the online edition", "Roger Pearse",
    "This text was", "Return to", "Translator",
    "The Tertullian Project", "Buy a CDROM",
)

def is_bad(t):
    return len(t) < 30 or any(t.startswith(b) for b in BAD_STARTS)

def strip_footer(html):
    for cut in ["Roger Pearse", "Preface to the online edition",
                "Return to the", "The Tertullian Project",
                "<!--", "Previous section", "Next section"]:
        idx = html.find(cut)
        if idx > 5000:
            html = html[:idx]
    return html

def get_paras(html):
    raw = re.findall(r"<p[^>]*>(.*?)</p>", html, re.DOTALL|re.IGNORECASE)
    return [hclean(p) for p in raw if not is_bad(hclean(p))]

def numbered(paras):
    return {str(i+1): p for i, p in enumerate(paras)}

def fetch_page(url):
    print(f"    {url}")
    html = fetch(url)
    time.sleep(DELAY)
    if not html:
        return []
    body = strip_footer(html)

    # Try h2/h3 chapter splits
    for htag in ["h2", "h3"]:
        parts = re.split(rf"<{htag}[^>]*>", body, flags=re.IGNORECASE)
        if len(parts) < 3:
            continue
        chapters = {}
        for part in parts[1:]:
            end = part.find(f"</{htag}>")
            header = hclean(part[:end]) if end > 0 else ""
            m = re.search(r"(\d+)", header)
            if not m:
                continue
            paras = get_paras(part[end+5:] if end > 0 else part)
            if paras:
                chapters[m.group(1)] = numbered(paras)
        if chapters:
            return list(chapters.items())

    # Fall back to flat paragraphs
    paras = get_paras(body)
    return [("1", numbered(paras))] if paras else []

def load_json(path):
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return None

def save_json(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

# ── Catalog ────────────────────────────────────────────────────────────────────
# (slug, display_name, work_title, [urls], supplement_existing)
CATALOG = [
    ("irenaeus_of_lyons", "Irenaeus of Lyons",
     "The Proof of the Apostolic Preaching",
     ["https://www.tertullian.org/fathers/irenaeus_02_proof.htm"], True),

    ("hermias", "Hermias the Philosopher",
     "Derision of Gentile Philosophers",
     ["https://www.tertullian.org/fathers/hermias_1_satire.htm"], False),

    ("eunomius", "Eunomius of Cyzicus",
     "The First Apology",
     ["https://www.tertullian.org/fathers/eunomius_apology01.htm"], False),

    ("eusebius_of_caesarea", "Eusebius of Caesarea",
     "Demonstratio Evangelica",
     [f"https://www.tertullian.org/fathers/eusebius_de_{n:02d}_book{b}.htm"
      for n, b in zip(range(3,13), range(1,11))], True),

    ("eusebius_of_caesarea", "Eusebius of Caesarea",
     "Praeparatio Evangelica",
     [f"https://www.tertullian.org/fathers/eusebius_pe_{n:02d}_book{b}.htm"
      for n, b in zip(range(1,16), range(1,16))], True),

    ("eusebius_of_caesarea", "Eusebius of Caesarea",
     "Theophania",
     [f"https://www.tertullian.org/fathers/eusebius_theophania_{n:02d}book{b}.htm"
      for n, b in zip(range(2,7), range(1,6))], True),

    ("eusebius_of_caesarea", "Eusebius of Caesarea",
     "Against Hierocles",
     ["https://www.tertullian.org/fathers/eusebius_against_hierocles.htm"], True),

    ("eusebius_of_caesarea", "Eusebius of Caesarea",
     "History of the Martyrs in Palestine",
     ["https://www.tertullian.org/fathers/eusebius_martyrs.htm"], True),

    ("philostorgius", "Philostorgius",
     "Ecclesiastical History (Epitome)",
     ["https://www.tertullian.org/fathers/philostorgius.htm"], False),

    ("ambrose", "Ambrose",
     "Letters of Ambrose",
     [f"https://www.tertullian.org/fathers/ambrose_letters_{n:02d}_letters{a}_{b}.htm"
      for n, (a, b) in enumerate([
          ("01","10"),("11","20"),("21","30"),("31","40"),("41","50"),
          ("51","60"),("61","70"),("71","80"),("81","91")], 1)], True),

    ("pacian_of_barcelona", "Pacian of Barcelona",
     "Letters to Sympronian",
     ["https://www.tertullian.org/fathers/pacian_1_letter1.htm",
      "https://www.tertullian.org/fathers/pacian_2_letter2.htm",
      "https://www.tertullian.org/fathers/pacian_3_letter3.htm"], False),

    ("pacian_of_barcelona", "Pacian of Barcelona",
     "Paraenesis on Penance",
     ["https://www.tertullian.org/fathers/pacian_4_paraenesis.htm"], False),

    ("pacian_of_barcelona", "Pacian of Barcelona",
     "Discourse on Baptism",
     ["https://www.tertullian.org/fathers/pacian_5_baptism.htm"], False),

    ("macarius_magnes", "Macarius Magnes",
     "Apocriticus",
     ["https://www.tertullian.org/fathers/macarius_apocriticus.htm"], False),

    ("asterius_of_amasea", "Asterius of Amasea",
     "Sermons",
     [f"https://www.tertullian.org/fathers/asterius_{n:02d}_sermon{n}.htm"
      for n in range(1, 6)], False),

    ("chrysostom", "John Chrysostom",
     "Against the Jews",
     [f"https://www.tertullian.org/fathers/chrysostom_adversus_judaeos_{n:02d}_homily{n}.htm"
      for n in range(1, 9)], True),

    ("chrysostom", "John Chrysostom",
     "Four Discourses on Lazarus",
     [f"https://www.tertullian.org/fathers/chrysostom_four_discourses_{n:02d}_discourse{n}.htm"
      for n in range(1, 5)], True),

    ("palladius", "Palladius",
     "The Lausiac History",
     ["https://www.tertullian.org/fathers/palladius_lausiac_02_text.htm"], False),

    ("palladius", "Palladius",
     "Dialogue on the Life of St. John Chrysostom",
     ["https://www.tertullian.org/fathers/palladius_dialogus_02_text.htm"], False),

    ("salvian", "Salvian",
     "On the Government of God",
     [f"https://www.tertullian.org/fathers/salvian_gov_{n:02d}_book{n}.htm"
      for n in range(1, 9)], False),

    ("sidonius_apollinaris", "Sidonius Apollinaris",
     "Letters",
     [f"https://www.tertullian.org/fathers/sidonius_letters_{n:02d}book{n}.htm"
      for n in range(1, 10)], False),

    ("nestorius", "Nestorius",
     "The Bazaar of Heracleides",
     ["https://www.tertullian.org/fathers/nestorius_bazaar_1_book1_part1.htm",
      "https://www.tertullian.org/fathers/nestorius_bazaar_2_book1_part2.htm",
      "https://www.tertullian.org/fathers/nestorius_bazaar_3_book1_part3.htm",
      "https://www.tertullian.org/fathers/nestorius_bazaar_4_book2_part1.htm",
      "https://www.tertullian.org/fathers/nestorius_bazaar_5_book2_part2.htm"], False),

    ("theodore_of_mopsuestia", "Theodore of Mopsuestia",
     "Commentary on the Nicene Creed",
     ["https://www.tertullian.org/fathers/theodore_of_mopsuestia_nicene_02_text.htm"], False),

    ("theodore_of_mopsuestia", "Theodore of Mopsuestia",
     "Commentary on the Lord's Prayer and Sacraments",
     ["https://www.tertullian.org/fathers/theodore_of_mopsuestia_lordsprayer_02_text.htm"], False),

    ("epiphanius", "Epiphanius of Salamis",
     "On Weights and Measures",
     ["https://www.tertullian.org/fathers/epiphanius_weights_03_text.htm"], False),

    ("pseudo_hegesippus", "Pseudo-Hegesippus",
     "On the Ruin of Jerusalem",
     [f"https://www.tertullian.org/fathers/hegesippus_{n:02d}_book{n}.htm"
      for n in range(1, 6)], False),

    ("optatus_of_milevis", "Optatus of Milevis",
     "Against the Donatists",
     [f"https://www.tertullian.org/fathers/optatus_{n:02d}_book{n}.htm"
      for n in range(1, 8)], False),

    ("philoxenus_of_hierapolis", "Philoxenus of Hierapolis",
     "13 Ascetic Discourses",
     [f"https://www.tertullian.org/fathers/philoxenus_discourse{n:02d}.htm"
      for n in range(1, 14)], False),

    ("evagrius_scholasticus", "Evagrius Scholasticus",
     "Ecclesiastical History",
     [f"https://www.tertullian.org/fathers/evagrius_{n}_book{n}.htm"
      for n in range(1, 7)], False),

    ("photius", "Photius of Constantinople",
     "Bibliotheca (Codices 1-165)",
     ["https://www.tertullian.org/fathers/photius_03bibliotheca.htm"], False),

    ("possidius", "Possidius",
     "Life of St. Augustine",
     ["https://www.tertullian.org/fathers/possidius_life_of_augustine_02_text.htm"], False),

    ("theodoret", "Theodoret",
     "Commentary on Romans",
     ["https://www.tertullian.org/fathers/theodoret_commentary_on_romans_01.htm",
      "https://www.tertullian.org/fathers/theodoret_commentary_on_romans_02.htm"], True),

    ("cyril_of_alexandria", "Cyril of Alexandria",
     "Against Diodore and Theodore (Fragments)",
     ["https://www.tertullian.org/fathers/cyril_against_diodore_01_text.htm",
      "https://www.tertullian.org/fathers/cyril_against_theodore_01_text.htm",
      "https://www.tertullian.org/fathers/cyril_against_theodore_02_text.htm"], True),

    ("dioscorus_of_alexandria", "Dioscorus of Alexandria",
     "Letter to Shenouda",
     ["https://www.tertullian.org/fathers/dioscorus_of_alexandria_letter_to_shenoute.htm"], False),

    ("gildas", "Gildas the Wise",
     "The Ruin of Britain",
     ["https://www.tertullian.org/fathers/gildas_02_ruin_of_britain.htm"], False),

    ("gildas", "Gildas the Wise",
     "Penitential",
     ["https://www.tertullian.org/fathers/gildas_06_penitential.htm"], False),

    ("leontius_of_byzantium", "Leontius of Byzantium",
     "Against the Frauds of the Apollinarists",
     ["https://www.tertullian.org/fathers/leontius_byzantinus_adversus_fraudes_apollinistarum_02_text.htm"], False),

    ("severus_of_antioch", "Severus of Antioch",
     "Letters",
     ["https://www.tertullian.org/fathers/severus_coll_2_letters.htm",
      "https://www.tertullian.org/fathers/severus_coll_3_letters.htm"], False),

    ("john_of_ephesus", "John of Ephesus",
     "Ecclesiastical History (Third Part)",
     [f"https://www.tertullian.org/fathers/ephesus_{n}_book{b}.htm"
      for n, b in [(1,1),(2,2),(3,3),(4,4),(6,5),(7,6)]], False),

    ("cosmas_indicopleustes", "Cosmas Indicopleustes",
     "The Christian Topography",
     [f"https://www.tertullian.org/fathers/cosmas_{n:02d}_book{n}.htm"
      for n in range(1, 13)], False),

    ("agapius_of_hierapolis", "Agapius of Hierapolis",
     "Universal History",
     ["https://www.tertullian.org/fathers/agapius_history_01_part1.htm",
      "https://www.tertullian.org/fathers/agapius_history_02_part2.htm"], False),

    ("timothy_i", "Timothy I (Patriarch of Baghdad)",
     "Apology for Christianity to Caliph Al-Mahdi",
     ["https://www.tertullian.org/fathers/timothy_i_apology_01_text.htm"], False),

    ("isidore_of_seville", "Isidore of Seville",
     "Chronicon",
     ["https://www.tertullian.org/fathers/isidore_chronicon_01_trans.htm"], False),

    ("john_bar_penkaye", "John bar Penkaye",
     "Summary History of the World (Book 15: Rise of Islam)",
     ["https://www.tertullian.org/fathers/john_bar_penkaye_history_15_trans.htm"], False),
]

def slugify(name):
    s = name.lower()
    s = re.sub(r"['\",\.\(\)]+", "", s)
    s = re.sub(r"[\s\-]+", "_", s)
    return re.sub(r"[^a-z0-9_]", "", s).strip("_")

def main():
    data_dir = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else pathlib.Path("data/patristics")
    targets  = sys.argv[2:] if len(sys.argv) > 2 else []
    data_dir.mkdir(parents=True, exist_ok=True)

    # Group catalog by slug so we load/save each file once
    from collections import defaultdict
    by_slug = defaultdict(list)
    for entry in CATALOG:
        by_slug[entry[0]].append(entry)

    for slug, entries in by_slug.items():
        if targets and not any(t in slug for t in targets):
            continue

        display_name = entries[0][1]
        is_supplement = entries[0][4]
        path = data_dir / f"{slug}.json"

        print(f"\n{'='*55}")
        print(f"{'SUPPLEMENT' if is_supplement else 'NEW'}: {display_name} → {slug}.json")

        if is_supplement and path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
            books = data.get("books", {})
        else:
            data = {"source": display_name, "books": {}}
            books = {}

        for _, _, work_title, urls, _ in entries:
            if work_title in books and sum(len(v) for v in books[work_title].values()) > 5:
                print(f"  SKIP {work_title} (already populated)")
                continue

            print(f"  Fetching {work_title} ({len(urls)} page(s))...")
            work_chapters = {}
            ch_offset = 0

            for url in urls:
                chapters = fetch_page(url)
                if not chapters:
                    print(f"    → empty")
                    continue
                for ch_key, ch_content in chapters:
                    # If multiple pages and chapters restart at 1, offset them
                    try:
                        new_key = str(int(ch_key) + ch_offset)
                    except ValueError:
                        new_key = ch_key
                    work_chapters[new_key] = ch_content
                # Advance offset by highest chapter number seen
                if chapters:
                    try:
                        ch_offset = max(int(k) for k, _ in chapters)
                    except ValueError:
                        pass

            n_p = sum(len(v) for v in work_chapters.values())
            if n_p > 0:
                books[work_title] = work_chapters
                print(f"    → {len(work_chapters)} chapters, {n_p} paras")
            else:
                print(f"    → failed / empty")

        data["books"] = books
        total = sum(len(v) for bk in books.values() for v in bk.values())
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"  Saved: {len(books)} works, {total} paras")

    print("\nDone.")

if __name__ == "__main__":
    main()
