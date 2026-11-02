"""The slow corpus checks, a test a data file, so a change is checked where it was made:

    python -m pytest -m corpus -k latin          (data/classical/latin.json only)
    python -m pytest -m corpus                   (every file: when shared cleaning or building code changed)

Each file: no web leftovers in its passages (test_corpus_clean.JUNK), no siglum ending most of a book's passages,
its citations short and free of website names (test_citations), and scripts/clean_corpora.py has nothing left to
do in it. The hymnal is only checked for its citations."""
import json
import sys

import pytest

from core import ROOT
from tests.test_citations import bad_citations
from tests.test_corpus_clean import _stray_markers, web_leftovers

DATA = ROOT / "data"
FILES = sorted(p.relative_to(DATA).as_posix() for p in DATA.rglob("*.json") if "New folder" not in p.parts)


@pytest.mark.corpus
@pytest.mark.parametrize("rel", FILES)
def test_corpus_file(rel):
    path = DATA / rel
    if path.stat().st_size > 50_000_000:
        pytest.skip("too big to be a corpus")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, UnicodeDecodeError):
        pytest.skip("not JSON text")
    assert not bad_citations(data), bad_citations(data)
    if not (isinstance(data, dict) and isinstance(data.get("books"), dict)) or "hymns" in path.parts:
        return
    junk = web_leftovers(data)
    assert not junk, f"{len(junk)} passages need scripts/clean_corpora.py: {junk[:10]}"
    assert not _stray_markers([(path, data)])
    pytest.importorskip("beta_code")
    sys.path.insert(0, str(ROOT / "scripts"))
    import clean_corpora
    assert clean_corpora.clean_file(path, dry=True) == 0, "run scripts/clean_corpora.py"
