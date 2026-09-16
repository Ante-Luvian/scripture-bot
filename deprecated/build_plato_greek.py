#!/usr/bin/env python3
"""
build_plato_greek.py

Run from your scripture bot directory:
    python build_plato_greek.py

Reads:  canonical-greekLit/data/tlg0059/tlgNNN/tlg0059_tlgNNN_perseus-grcX.xml
Writes: data/poetry/plato_greek.json
"""

import json, re, sys, xml.etree.ElementTree as ET
from pathlib import Path

NS = '{http://www.tei-c.org/ns/1.0}'

PLATO_WORKS = [
    ("tlg001", "Euthyphro"),
    ("tlg002", "Apology"),
    ("tlg003", "Crito"),
    ("tlg004", "Phaedo"),
    ("tlg005", "Cratylus"),
    ("tlg006", "Theaetetus"),
    ("tlg007", "Sophist"),
    ("tlg008", "Statesman"),
    ("tlg009", "Parmenides"),
    ("tlg010", "Philebus"),
    ("tlg011", "Symposium"),
    ("tlg012", "Phaedrus"),
    ("tlg013", "Alcibiades I"),
    ("tlg014", "Alcibiades II"),
    ("tlg015", "Hipparchus"),
    ("tlg016", "Rival Lovers"),
    ("tlg017", "Theages"),
    ("tlg018", "Charmides"),
    ("tlg019", "Laches"),
    ("tlg020", "Lysis"),
    ("tlg021", "Euthydemus"),
    ("tlg022", "Protagoras"),
    ("tlg023", "Gorgias"),
    ("tlg024", "Meno"),
    ("tlg025", "Greater Hippias"),
    ("tlg026", "Lesser Hippias"),
    ("tlg027", "Ion"),
    ("tlg028", "Menexenus"),
    ("tlg029", "Cleitophon"),
    ("tlg030", "Republic"),
    ("tlg031", "Timaeus"),
    ("tlg032", "Critias"),
    ("tlg033", "Minos"),
    ("tlg034", "Laws"),
    ("tlg035", "Epinomis"),
    ("tlg036", "Letters"),
]

_LABEL_RE = re.compile(r'^\s*[Α-Ω]{1,5}\.\s*')


def find_base_dir():
    cwd = Path.cwd()
    for candidate in [
        cwd / 'canonical-greekLit',
        cwd / 'canonical-greekLit-master',
        Path('C:/Users/chris/OneDrive/Desktop/scripture bot/canonical-greekLit'),
    ]:
        if candidate.exists() and (candidate / 'data' / 'tlg0059').exists():
            return candidate
    return None


def find_xml(base_dir, tlg_num):
    # Files live in: data/tlg0059/tlg001/tlg0059_tlg001_perseus-grc1.xml
    work_dir = base_dir / 'data' / 'tlg0059' / tlg_num
    if not work_dir.exists():
        return None
    for variant in ['grc1', 'grc2', 'grc3', 'grc']:
        # Try dot-separated filename (tlg0059.tlg001.perseus-grc1.xml)
        p = work_dir / f'tlg0059.{tlg_num}.perseus-{variant}.xml'
        if p.exists():
            return p
        # Try underscore-separated filename (tlg0059_tlg001_perseus-grc1.xml)
        p = work_dir / f'tlg0059_{tlg_num}_perseus-{variant}.xml'
        if p.exists():
            return p
    # Fallback: any grc file in that folder
    matches = sorted(work_dir.glob(f'tlg0059*{tlg_num}*perseus-grc*.xml'))
    return matches[0] if matches else None


def extract_stephanus(xml_path):
    try:
        tree = ET.parse(xml_path)
    except ET.ParseError as e:
        print(f"    XML error: {e}")
        return {}

    root = tree.getroot()
    sections = {}
    current = [None]

    def add(text):
        if current[0] is None or not text.strip():
            return
        t = _LABEL_RE.sub('', text.strip()).strip()
        if t:
            sections.setdefault(current[0], []).append(t)

    def walk(el):
        tag = el.tag.replace(NS, '')
        if tag == 'milestone':
            if el.get('unit') == 'section' and el.get('resp') == 'Stephanus':
                current[0] = el.get('n')
        if tag in ('label', 'note', 'bibl', 'head', 'figDesc', 'figure'):
            if el.tail:
                add(el.tail)
            return
        if el.text:
            add(el.text)
        for child in el:
            walk(child)
        if el.tail:
            add(el.tail)

    walk(root)

    return {
        ref: ' '.join(' '.join(frags).split())
        for ref, frags in sections.items()
        if frags
    }


def main():
    base_dir = find_base_dir()
    if base_dir is None:
        print(f"ERROR: Cannot find canonical-greekLit from {Path.cwd()}")
        sys.exit(1)

    print(f"Found: {base_dir}")

    out_dir = Path('data') / 'poetry'
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / 'plato_greek.json'

    all_dialogues = {}

    for tlg_num, name in PLATO_WORKS:
        xml_path = find_xml(base_dir, tlg_num)
        if xml_path is None:
            print(f"  MISSING  {tlg_num}  {name}")
            continue
        sections = extract_stephanus(xml_path)
        if not sections:
            print(f"  EMPTY    {tlg_num}  {name}")
            continue
        all_dialogues[name] = sections
        refs = list(sections.keys())
        print(f"  OK  {name:20}  {len(sections):4} sections  ({refs[0]}-{refs[-1]})")

    payload = {
        "source": "Plato. Perseus Digital Library. TLG 0059. Greek text. Stephanus pagination.",
        "lang": "grc",
        "books": all_dialogues,
    }

    out_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding='utf-8')
    total = sum(len(s) for s in all_dialogues.values())
    print(f"\nDone: {len(all_dialogues)} dialogues, {total:,} sections -> {out_path}")


if __name__ == '__main__':
    main()
