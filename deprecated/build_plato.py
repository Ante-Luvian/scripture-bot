"""
build_plato.py — Builds data/classical/plato.json from Perseus Digital Library.

RECOMMENDED (no rate limits):
    git clone https://github.com/PerseusDL/canonical-greekLit
    python build_plato.py --local-repo ./canonical-greekLit

ALTERNATIVE (may hit GitHub rate limits):
    python build_plato.py

Lookup examples once built:
    !verse Apology 17a
    !verse Republic 514a
    !verse Republic 7.514a
    !verse Symposium 210a
    !verse Laws 624a
"""

import json, re, sys, time, urllib.request, urllib.error
import xml.etree.ElementTree as ET
from pathlib import Path

OUTPUT_FILE = Path("data/classical/plato.json")
BASE_URL    = "https://raw.githubusercontent.com/PerseusDL/canonical-greekLit/master/data/tlg0059"

DIALOGUES = [
    ("Euthyphro",       "tlg001", False),
    ("Apology",         "tlg002", False),
    ("Crito",           "tlg003", False),
    ("Phaedo",          "tlg004", False),
    ("Cratylus",        "tlg005", False),
    ("Theaetetus",      "tlg006", False),
    ("Sophist",         "tlg007", False),
    ("Statesman",       "tlg008", False),
    ("Parmenides",      "tlg009", False),
    ("Philebus",        "tlg010", False),
    ("Symposium",       "tlg011", False),
    ("Phaedrus",        "tlg012", False),
    ("Alcibiades I",    "tlg013", False),
    ("Alcibiades II",   "tlg014", False),
    ("Hipparchus",      "tlg015", False),
    ("Rival Lovers",    "tlg016", False),
    ("Theages",         "tlg017", False),
    ("Charmides",       "tlg018", False),
    ("Laches",          "tlg019", False),
    ("Lysis",           "tlg020", False),
    ("Euthydemus",      "tlg021", False),
    ("Protagoras",      "tlg022", False),
    ("Gorgias",         "tlg023", False),
    ("Meno",            "tlg024", False),
    ("Greater Hippias", "tlg025", False),
    ("Lesser Hippias",  "tlg026", False),
    ("Ion",             "tlg027", False),
    ("Menexenus",       "tlg028", False),
    ("Cleitophon",      "tlg029", False),
    ("Republic",        "tlg030", True),
    ("Timaeus",         "tlg031", False),
    ("Critias",         "tlg032", False),
    ("Minos",           "tlg033", False),
    ("Laws",            "tlg034", True),
    ("Epinomis",        "tlg035", False),
    ("Letters",         "tlg036", True),
    ("Axiochus",        "tlg037", False),
    ("On Justice",      "tlg038", False),
    ("On Virtue",       "tlg039", False),
    ("Demodocus",       "tlg040", False),
    ("Sisyphus",        "tlg041", False),
    ("Eryxias",         "tlg042", False),
    ("Definitions",     "tlg043", False),
]


def fetch_remote(tlg_id, retries=3):
    url = f"{BASE_URL}/{tlg_id}/tlg0059.{tlg_id}.perseus-eng2.xml"
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "ScriptureBot/1.0"})
            with urllib.request.urlopen(req, timeout=30) as r:
                return r.read().decode("utf-8")
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            if e.code == 429:
                wait = 60 * (attempt + 1)
                print(f"    Rate limited — waiting {wait}s (retry {attempt+1}/{retries})...")
                time.sleep(wait)
            else:
                print(f"    HTTP {e.code}: {e}")
                return None
        except Exception as e:
            print(f"    Error: {e}")
            return None
    print(f"    Giving up after {retries} retries.")
    return None


def fetch_local(tlg_id, repo):
    path = Path(repo) / "data" / "tlg0059" / tlg_id / f"tlg0059.{tlg_id}.perseus-eng2.xml"
    return path.read_text(encoding="utf-8") if path.exists() else None


def get_all_text(elem):
    SKIP = {"note", "bibl", "foreign"}
    tag = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag
    if tag in SKIP:
        return ""
    parts = [elem.text or ""]
    for child in elem:
        parts.append(get_all_text(child))
        parts.append(child.tail or "")
    return "".join(parts)


def parse_dialogue(xml_text, has_books):
    xml_text = re.sub(r' xmlns[^"]*"[^"]*"', "", xml_text)
    xml_text = re.sub(r"<\?[^>]+\?>", "", xml_text)
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as e:
        print(f"    XML error: {e}")
        return {}

    body = root.find(".//body") or root
    results, current_ref, current_book, chunks = {}, None, None, []

    def flush():
        if current_ref and chunks:
            text = re.sub(r"\s+", " ", " ".join(chunks)).strip()
            if len(text) > 10:
                results[current_ref] = text

    for elem in body.iter():
        tag = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag

        if tag in ("div1", "div") and has_books:
            n = elem.get("n", "")
            if n and n.isdigit():
                current_book = n

        if tag == "milestone" and elem.get("unit", "") in ("stephpage", "section", "Stephanus"):
            steph = elem.get("n", "").strip()
            if steph:
                flush()
                current_ref = (f"{current_book}.{steph}" if has_books and current_book else steph)
                chunks = []
                if elem.tail and elem.tail.strip():
                    chunks.append(elem.tail.strip())

        elif tag in ("p", "sp", "l", "ab", "seg"):
            if current_ref:
                t = re.sub(r"\s+", " ", get_all_text(elem)).strip()
                if t:
                    chunks.append(t)
            if elem.tail and current_ref and elem.tail.strip():
                chunks.append(elem.tail.strip())

    flush()
    return results


def build_plato(repo=None):
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    get_xml = (lambda tid: fetch_local(tid, repo)) if repo else (lambda tid: (time.sleep(0.5), fetch_remote(tid))[1])

    all_dialogues, total = {}, 0
    for name, tlg_id, has_books in DIALOGUES:
        print(f"  {name} ({tlg_id})...", end=" ", flush=True)
        xml = get_xml(tlg_id)
        if not xml:
            print("skipped — no translation found.")
            continue
        sections = parse_dialogue(xml, has_books)
        if not sections:
            print("WARNING: no sections parsed.")
            continue
        all_dialogues[name] = {s: {"1": t} for s, t in sections.items()}
        total += len(sections)
        print(f"✓ {len(sections)} sections")

    OUTPUT_FILE.write_text(
        json.dumps({
            "source": "Plato, trans. Benjamin Jowett (1892). Perseus Digital Library (CC-BY-SA).",
            "books": all_dialogues,
        }, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )
    size = OUTPUT_FILE.stat().st_size // 1024
    print(f"\n✓ {len(all_dialogues)} dialogues, {total} sections → {OUTPUT_FILE} ({size} KB)")


if __name__ == "__main__":
    repo = None
    if "--local-repo" in sys.argv:
        idx = sys.argv.index("--local-repo")
        if idx + 1 < len(sys.argv):
            repo = sys.argv[idx + 1]
            if not Path(repo).exists():
                print(f"Error: {repo} not found"); sys.exit(1)
        else:
            print("Error: --local-repo requires a path"); sys.exit(1)

    if repo:
        print(f"Building Plato from local repo: {repo}")
    else:
        print("Building Plato from GitHub (use --local-repo to avoid rate limits).")
    build_plato(repo)
