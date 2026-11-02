"""Citations stay short: who translated it and when, not the title, publisher, licence or website
(the owner found 'The Paradise, or Garden of the Holy Fathers, trans. E. A. Wallis Budge (1907), from
Wikisource' far too long). The reference above a passage already names the work."""
import re

KEYS = ("source", "sources", "book_sources")
WEB = re.compile(r"Wikisource|Wikimedia|Gutenberg|CCEL|sacred-texts|tertullian\.org|\bvia\b|public domain|CC[- ]BY|"
                 r"https?:|www\.|\.com\b|\.org\b", re.I)
NAMES = ("Hymnary.org", "OpenBible.info", "Choral Public Domain Library")      # sources, not web debris
LONGEST = 80


def citations_in(o, depth=0):
    """The source strings in a file's data (its "source", "sources", "book_sources"), however deep they sit."""
    if isinstance(o, dict):
        for k, v in o.items():
            if k in KEYS and isinstance(v, str):
                yield v
            elif k in KEYS and isinstance(v, dict):
                yield from (x for x in v.values() if isinstance(x, str))
            elif depth < 3:
                yield from citations_in(v, depth + 1)
    elif isinstance(o, list) and depth < 3:
        for x in o:
            yield from citations_in(x, depth + 1)


def bad_citations(data) -> list:
    """The file's citations that are too long or name a website or licence."""
    names = "|".join(map(re.escape, NAMES))
    return sorted(s for s in set(citations_in(data)) if len(s) > LONGEST or WEB.search(re.sub(names, "", s)))


def test_a_long_citation_is_caught():
    assert bad_citations({"source": "trans. W. D. Hooper and H. B. Ash (1934)"}) == []
    assert bad_citations({"book_sources": {"X": "trans. Someone (1900), from Wikisource"}})
    assert bad_citations({"books": {}, "source": "x" * (LONGEST + 1)})

# (the check on every data file is tests/test_corpus_files.py, a test a file)
