"""Citations stay short: who translated it and when, not the title, publisher, licence or website
(the owner found 'The Paradise, or Garden of the Holy Fathers, trans. E. A. Wallis Budge (1907), from
Wikisource' far too long). The reference above a passage already names the work."""
import json
import re

import pytest

from core import ROOT

KEYS = ("source", "sources", "book_sources")
WEB = re.compile(r"Wikisource|Wikimedia|Gutenberg|CCEL|sacred-texts|tertullian\.org|\bvia\b|public domain|CC[- ]BY|"
                 r"https?:|www\.|\.com\b|\.org\b", re.I)
NAMES = ("Hymnary.org", "OpenBible.info", "Choral Public Domain Library")      # sources, not web debris
LONGEST = 80


def citations():
    def walk(o, depth=0):
        if isinstance(o, dict):
            for k, v in o.items():
                if k in KEYS and isinstance(v, str):
                    yield v
                elif k in KEYS and isinstance(v, dict):
                    yield from (x for x in v.values() if isinstance(x, str))
                elif depth < 3:
                    yield from walk(v, depth + 1)
        elif isinstance(o, list) and depth < 3:
            for x in o:
                yield from walk(x, depth + 1)

    for path in sorted((ROOT / "data").rglob("*.json")):
        if "New folder" in path.parts or path.stat().st_size > 50_000_000:
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except ValueError:
            continue
        for s in set(walk(data)):
            yield path.relative_to(ROOT / "data").as_posix(), s


@pytest.mark.corpus
def test_citations_are_short():
    bad = [(f, s) for f, s in citations() if len(s) > LONGEST or WEB.search(re.sub("|".join(map(re.escape, NAMES)), "", s))]
    assert not bad, "\n".join(f"{f}: {s}" for f, s in bad[:40])
