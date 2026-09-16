#!/usr/bin/env python3
"""
fixup.py — final targeted fixes for the remaining issues.

Fixes:
1. Athanasius: remove duplicate De Sententia Dionysii (= Apologia)
2. Clement: fetch missing Exhortation chapters 1-9 (correct zero-padded URLs)
3. Chrysostom: fetch missing Statues homilies 1-9 (correct zero-padded URLs)
4. Augustine: remove empty Retractions / On Free Will (not on NewAdvent)
5. John of Damascus: try correct Philosophical Chapters URL
6. Basil/Athanasius Letters: try fetching individual letter URLs from index

Run:
    python3 fixup.py data\\patristics
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

def fetch_page_flat(url):
    """Fetch a page and return flat {para_num: text} dict."""
    print(f"    {url}")
    html = fetch(url)
    time.sleep(DELAY)
    if not html: return {}
    paras = get_paras(strip_footer(html))
    return numbered(paras) if paras else {}

def load(data_dir, slug):
    path = data_dir / f"{slug}.json"
    return json.loads(path.read_text(encoding="utf-8")), path

def save(data, path):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

def main():
    data_dir = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else pathlib.Path("data/patristics")
    targets  = sys.argv[2:] if len(sys.argv) > 2 else []

    def want(slug):
        return not targets or any(t in slug for t in targets)

    # ── 1. Athanasius: remove De Sententia (duplicate of Apologia) ─────────────
    if want("athanasius"):
        print("\nathanasius: removing duplicate De Sententia Dionysii")
        data, path = load(data_dir, "athanasius")
        dsd  = data["books"].get("De Sententia Dionysii", {})
        apol = data["books"].get("Apologia Contra Arianos", {})
        # Check if they're identical
        dsd_p1  = next(iter(next(iter(dsd.values()), {}).values()), "") if dsd else ""
        apol_p1 = next(iter(next(iter(apol.values()), {}).values()), "") if apol else ""
        if dsd_p1 and dsd_p1 == apol_p1:
            # They're the same — clear De Sententia (real one needs different URL)
            data["books"]["De Sententia Dionysii"] = {}
            print("  ✓ Cleared duplicate De Sententia Dionysii")
        else:
            print("  (not duplicates — leaving as-is)")
        save(data, path)

    # ── 2. Clement: fetch missing Exhortation chapters 1-9 ────────────────────
    if want("clement"):
        print("\nclement_of_alexandria: fetching Exhortation chapters 1-9")
        data, path = load(data_dir, "clement_of_alexandria")
        ext = data["books"].get("Exhortation to the Heathen", {})
        present = set(ext.keys())
        missing = [str(ch) for ch in range(1, 13) if str(ch) not in present]
        if missing:
            print(f"  Missing chapters: {missing}")
            for ch in missing:
                # Try zero-padded two-digit: 020801, 020802 ... 020812
                code = f"0208{int(ch):02d}"
                para_dict = fetch_page_flat(na(code))
                if para_dict:
                    ext[str(ch)] = para_dict
                    print(f"    ✓ Chapter {ch}: {len(para_dict)} paras")
                else:
                    print(f"    ✗ Chapter {ch}: failed")
            data["books"]["Exhortation to the Heathen"] = ext
            save(data, path)

    # ── 3. Chrysostom: fetch missing Statues homilies 1-9 ─────────────────────
    if want("chrysostom"):
        print("\nchrysostom: fetching Statues homilies 1-9")
        data, path = load(data_dir, "chrysostom")
        stat = data["books"].get("Homilies on the Statues", {})
        present = set(stat.keys())
        missing = [str(h) for h in range(1, 10) if str(h) not in present]
        if missing:
            print(f"  Missing homilies: {missing}")
            for hom in missing:
                # Zero-padded: 190101, 190102 ... 190109
                code = f"1901{int(hom):02d}"
                para_dict = fetch_page_flat(na(code))
                if para_dict:
                    stat[str(hom)] = para_dict
                    print(f"    ✓ Homily {hom}: {len(para_dict)} paras")
                else:
                    print(f"    ✗ Homily {hom}: failed")
            data["books"]["Homilies on the Statues"] = stat
            save(data, path)

    # ── 4. Augustine: remove empty non-existent works ─────────────────────────
    if want("augustine"):
        print("\naugustine: removing empty Retractions / On Free Will")
        data, path = load(data_dir, "augustine")
        for work in ["Retractions", "On Free Will"]:
            if work in data["books"] and not data["books"][work]:
                del data["books"][work]
                print(f"  ✓ Removed empty {work}")
        save(data, path)

    # ── 5. John of Damascus: try correct Philosophical Chapters URL ────────────
    if want("john"):
        print("\njohn_of_damascus: re-fetching Philosophical Chapters")
        data, path = load(data_dir, "john_of_damascus")
        # 3303.htm returned garbage. Try fetching and check raw content.
        html = fetch(na("3303"))
        time.sleep(DELAY)
        if html:
            # Check what we actually get
            paras = get_paras(strip_footer(html))
            print(f"  Got {len(paras)} paras from 3303.htm")
            if paras:
                print(f"  p1: {paras[0][:100]}")
            # Build chapter structure
            parts = re.split(r"<h2[^>]*>", strip_footer(html), flags=re.IGNORECASE)
            result = {}
            for part in parts[1:]:
                end = part.find("</h2>")
                header = hclean(part[:end]) if end > 0 else ""
                m = re.search(r"(\d+)", header)
                if not m: continue
                ps = get_paras(part[end+5:] if end > 0 else part)
                if ps:
                    result[m.group(1)] = numbered(ps)
            if result:
                data["books"]["Philosophical Chapters"] = result
                n_p = sum(len(v) for v in result.values())
                print(f"  ✓ Philosophical Chapters: {len(result)} chapters, {n_p} paras")
            elif paras:
                data["books"]["Philosophical Chapters"] = {"1": numbered(paras)}
                print(f"  ✓ Philosophical Chapters: flat, {len(paras)} paras")
            else:
                print("  ✗ Still empty — page may require JavaScript")
        save(data, path)

    # ── 6. Basil Letters: try fetching via index ───────────────────────────────
    if want("basil"):
        print("\nbasil_the_great: attempting Letters of Basil via index 3204")
        data, path = load(data_dir, "basil_the_great")
        if not data["books"].get("Letters of Basil"):
            html_idx = fetch(na("3204"))
            time.sleep(DELAY)
            if html_idx:
                # Extract all /fathers/ links
                links = re.findall(r'/fathers/(\w+)\.htm', html_idx)
                seen, codes = set(), []
                for lnk in links:
                    if lnk != "3204" and lnk not in seen and lnk.startswith("32"):
                        seen.add(lnk); codes.append(lnk)
                print(f"  Found {len(codes)} letter links: {codes[:5]}...")
                result = {}
                for i, code in enumerate(codes, 1):
                    html_l = fetch(na(code))
                    time.sleep(DELAY)
                    if html_l:
                        paras = get_paras(strip_footer(html_l))
                        if paras:
                            result[str(i)] = numbered(paras)
                if result:
                    data["books"]["Letters of Basil"] = result
                    print(f"  ✓ Letters of Basil: {len(result)} letters")
                else:
                    print(f"  ✗ No letters fetched (index had {len(codes)} links)")
        save(data, path)

    print("\nDone.")

if __name__ == "__main__":
    main()
