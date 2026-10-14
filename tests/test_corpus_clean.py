"""The corpora are free of what came along with them from the web (corpus_clean.py),
and searches for bare symbols don't dredge up the leftovers."""
import json
import re

import pytest

from core import ROOT

# things no passage should contain: page furniture, licences, indexes, markup
JUNK = {
    "a site's script": r"\(function\(\)|!function\(|createElement\(",
    "a style sheet": r"mw-parser-output|font-size: ?\d+px",
    "the Gutenberg licence": r"Project Gutenberg",
    "the KJV site's footer": r"You may copy the King James",
    "a chapter menu": r"Chapter: 1 \| 2 \| 3",
    "a scanner's credit": r"Scanned and Edited by",
    "a site's copyright line": r"Early Christian Writings is copyright|Copyright statement: The Internet Classics|"
                               r"Browse and Comment Search",
    "a page marker": r"<page [^>]+>|\{p\. ?\d+\}",
    "an HTML entity": r"&(?:lt|gt|amp|quot|nbsp|#\d+);",
}


def _corpus_files():
    for path in sorted((ROOT / "data").rglob("*.json")):
        if "New folder" in path.parts or "hymns" in path.parts:
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (ValueError, UnicodeDecodeError):
            continue
        if isinstance(payload, dict) and isinstance(payload.get("books"), dict):
            yield path, payload


def _passages(payload):
    for book, chapters in payload["books"].items():
        for ch, verses in chapters.items():
            if isinstance(verses, str):
                yield f"{book} {ch}", verses
            else:
                for v, text in verses.items():
                    if isinstance(text, str):
                        yield f"{book} {ch}:{v}", text


@pytest.mark.corpus
def test_no_web_leftovers_in_any_corpus():
    found = []
    for path, payload in _corpus_files():
        for ref, text in _passages(payload):
            for what, pat in JUNK.items():
                if re.search(pat, text):
                    found.append(f"{path.relative_to(ROOT / 'data')} {ref}: {what}")
    assert not found, f"{len(found)} passages need scripts/clean_corpora.py: {found[:10]}"


@pytest.mark.corpus
def test_cleaning_is_already_done():
    """Re-running the cleaner changes nothing (rebuild a corpus? run scripts/clean_corpora.py after)."""
    pytest.importorskip("beta_code")
    from corpus_clean import clean_corpus
    dirty = [path.name for path, payload in _corpus_files()
             if clean_corpus(payload, path.relative_to(ROOT / "data").as_posix())]
    assert not dirty, dirty


@pytest.mark.parametrize("text, rel, expected", [
    ("the full term of seventy years. 1 Esdras &lt; 1 &gt; You may copy the King James Version freely.",
     "kjv/kjv_apocrypha.json", "the full term of seventy years."),
    ("as the dove. Go to the Chronological List of all Early Christian Writings (function() var po;",
     "apostolic_fathers/didache.json", "as the dove."),
    ("_Be thou prudent as the serpent_ in all things", "apostolic_fathers/ignatius_polycarp.json",
     "*Be thou prudent as the serpent* in all things"),
    ("called it Ke/ras )Amalqei/as, which is", "classical/perseus/phi1254.json", "called it Κέρας Ἀμαλθείας, which is"),
    ("the anapaest (u u _) or spondee (_ _) cannot", "classical/perseus/phi1002.json",
     "the anapaest (u u _) or spondee (_ _) cannot"),
    ("Pray these (as he did) and/or rest", "classical/perseus/phi0474.json", "Pray these (as he did) and/or rest"),
    ("the Boundary{philo means that ouranos was derived} of everything", "jewish/philo.json",
     "the Boundary of everything"),
    ("w#sper ou]n kai\\ th_n", "classical/julian.json", "ὥσπερ οὖν καὶ τὴν"),
    ("ye have been recog~ nised.", "dharmic/atharva_veda.json", "ye have been recognised."),
])
def test_clean_text(text, rel, expected):
    pytest.importorskip("beta_code")
    from corpus_clean import clean_text
    assert clean_text(text, rel) == expected


def test_trailing_footnotes_and_indexes_go():
    from corpus_clean import clean_corpus
    payload = {"books": {"Letters": {"1": {"1": "The letter itself.", "2": "And its close.",
                                           "3": "1. a See Euseb. H. E. v. 20.", "4": "2. * Thucydides ii. 45."}}}}
    clean_corpus(payload, "patristics/someone.json")
    assert payload["books"]["Letters"]["1"] == {"1": "The letter itself.", "2": "And its close."}
    jataka = {"books": {"Jataka": {"150": {"1": "The story.", "2": "END OF THE FIRST BOOK.",
                                           "3": "INDEX OF PROPER NAMES.", "4": "Abhassara <page 291>"}}}}
    clean_corpus(jataka, "buddhist/jataka.json")
    assert list(jataka["books"]["Jataka"]["150"].values()) == ["The story.", "END OF THE FIRST BOOK."]


@pytest.mark.parametrize("query", ["$", "%", "*", "_", "+", "~", "{", ">", "."])
def test_symbols_are_not_a_theme_or_a_search(lookup, query):
    assert lookup.theme_passages(query) == []
    assert lookup.search_by_corpus(query) == {}


def test_a_number_is_not_a_theme(lookup):
    assert lookup.theme_passages("34") == []
