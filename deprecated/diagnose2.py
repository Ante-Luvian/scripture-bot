"""
diagnose2.py — run from your scripture-bot directory
Usage: python diagnose2.py ./canonical-greekLit
Shows raw XML structure and MIT txt samples to fix parsers.
"""
import sys, re, urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

repo = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("./canonical-greekLit")

def show_xml(path, label, n=40):
    print(f"\n{'='*60}\n{label}\n{'='*60}")
    if not path.exists():
        print("NOT FOUND"); return
    text = path.read_text(encoding="utf-8")
    text = re.sub(r' xmlns[^"]*"[^"]*"', "", text)
    text = re.sub(r"<\?[^>]+\?>", "", text)
    try:
        root = ET.fromstring(text)
    except ET.ParseError as e:
        print(f"XML ERROR: {e}"); return
    body = root.find(".//body") or root
    count = 0
    for elem in body.iter():
        tag = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag
        txt = (elem.text or "").strip()[:80]
        print(f"  <{tag} {dict(elem.attrib)}> {txt!r}")
        count += 1
        if count >= n: print("  ..."); break

def show_txt_sample(url, label, lines=60):
    print(f"\n{'='*60}\n{label}\n{'='*60}")
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Bot/1.0"})
        with urllib.request.urlopen(req, timeout=15) as r:
            text = r.read().decode("utf-8", errors="replace")
        for i, line in enumerate(text.split('\n')[:lines]):
            print(f"  {i:3}: {line!r}")
    except Exception as e:
        print(f"  ERROR: {e}")

# Josephus samples
show_xml(repo/"data/tlg0526/tlg001/tlg0526.tlg001.perseus-eng2.xml", "Josephus Antiquities", 30)
show_xml(repo/"data/tlg0526/tlg004/tlg0526.tlg004.perseus-eng2.xml", "Josephus Jewish War", 30)

# Homer sample
show_xml(repo/"data/tlg0012/tlg001/tlg0012.tlg001.perseus-eng4.xml", "Homer Iliad", 30)

# Plotinus - show raw txt around section breaks
show_txt_sample("https://classics.mit.edu/Plotinus/enneads.mb.txt", "Plotinus txt sample", 80)

# Iamblichus - check actual Tertullian URL
show_txt_sample("https://www.tertullian.org/fathers/iamblichus_de_mysteriis_01.htm", "Iamblichus Mysteries §1 attempt", 30)
show_txt_sample("https://www.tertullian.org/fathers/iamblichus_mysteries_01_text.htm", "Iamblichus alt URL", 30)

# Nicomachean Ethics MIT URL
show_txt_sample("https://classics.mit.edu/Aristotle/nicomachaen.mb.txt", "Nic Ethics MIT", 30)
