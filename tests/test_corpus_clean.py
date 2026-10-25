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
    "a site's breadcrumb menu": r"Sacred Texts [A-Z][\w ]* Index",
    "a page marker":r"<page [^>]+>|\{p\. ?\d+\}",
    "an HTML entity": r"&(?:lt|gt|amp|quot|nbsp|#\d+);",
    "a website's footer or credits": r"The editor of New Advent|ADVERTISE WITH NEW ADVENT|Buy this Book at Amazon|"
                                     r"This (?:text|material) was (?:transcribed|uploaded) by|in online text|"
                                     r"Go to the Early Jewish Writings|Note to the online",
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


_MARKER = re.compile(r"[0-9]?[A-Za-z]+[0-9]*")      # a bare word or siglum, no punctuation: "1Clem", "Barnabas"


def _stray_markers(paths):
    """Books where one unpunctuated token ends most passages: a scraped site's reference
    abbreviation ("...about Arabia. 1Clem"), not the author's words."""
    found = []
    for path, payload in paths:
        for book, chapters in payload["books"].items():
            last = [text.split()[-1] for ref, text in _passages({"books": {book: chapters}}) if text.split()]
            if len(last) < 10:
                continue
            token = max(set(last), key=last.count)
            if _MARKER.fullmatch(token) and last.count(token) >= len(last) / 2:
                found.append(f"{path.relative_to(ROOT / 'data')} {book}: {last.count(token)}/{len(last)} end {token!r}")
    return found


def test_no_stray_markers_in_the_apostolic_fathers():
    files = [(p, json.loads(p.read_text(encoding="utf-8")))
             for p in sorted((ROOT / "data" / "apostolic_fathers").glob("*.json"))]
    files = [(p, d) for p, d in files if isinstance(d, dict) and isinstance(d.get("books"), dict)]
    assert files
    assert not _stray_markers(files)
    for path, payload in files:                             # a heading run onto a chapter's end
        bad = [ref for ref, text in _passages(payload) if re.search(r"\bCHAPTER \d+\s*$", text)]
        assert not bad, f"{path.name}: {bad[:5]}"


@pytest.mark.corpus
def test_no_stray_markers_in_any_corpus():
    found = _stray_markers(_corpus_files())
    assert not found, found


def test_the_marker_check_catches_one():
    payload = {"books": {"1 Clement": {"25": {str(v): f"Verse {v} of the phoenix. 1Clem" for v in range(1, 12)}}}}
    assert _stray_markers([(ROOT / "data" / "x.json", payload)])
    payload["books"]["1 Clement"]["25"] = {str(v): f"Verse {v} of the phoenix." for v in range(1, 12)}
    assert not _stray_markers([(ROOT / "data" / "x.json", payload)])


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
    ("Persius i. 4. [Note to the online text: there is an error here.] See", "patristics/basil_the_great.json",
     "Persius i. 4. See"),
    ("the [un]fathomable river, _like this_", "patristics/jerome.json", "the [un]fathomable river, *like this*"),
    ("ye have been recog~ nised.", "dharmic/atharva_veda.json", "ye have been recognised."),
    ("in the parts about Arabia. 1Clem", "apostolic_fathers/1_clement.json", "in the parts about Arabia."),
    ("in peace. Barnabas", "apostolic_fathers/epistle_of_barnabas.json", "in peace."),
    ("Barnabas said\nthis. Barnabas", "apostolic_fathers/epistle_of_barnabas.json", "Barnabas said\nthis."),
    ("abundant greeting. CHAPTER 1", "apostolic_fathers/ignatius_trallians.json", "abundant greeting."),
    ("The ending of the words is ALMSIVI . <div", "classical/vivec_sermons.json",
     "The ending of the words is ALMSIVI ."),
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


@pytest.mark.parametrize("word, finds, skips", [
    ("care", ["cares", "cared", "caring", "careth", "careful"], ["carry", "cart", "caress", "car"]),
    ("mercy", ["mercies", "merciful"], ["merchant"]),
    ("forgiveness", ["forgive", "forgiven", "forgiveth"], ["forget"]),
])
def test_a_theme_word_finds_its_forms_not_every_word_it_starts(lookup, word, finds, skips):
    pattern = re.compile(lookup.word_regex(word), re.IGNORECASE)
    assert all(pattern.fullmatch(w) for w in finds) and not any(pattern.fullmatch(w) for w in skips)
