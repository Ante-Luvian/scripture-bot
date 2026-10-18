"""The Reformation library (scripts/build_reformation.py): every work loads, the usual citations
open the right passage, and the texts carry none of their sources' furniture."""
import re

import pytest

WORKS = {
    "Ninety-Five Theses": 96, "Institutes of the Christian Religion": 80, "Augsburg Confession": 28,
    "Heidelberg Catechism": 129, "Westminster Shorter Catechism": 107, "Westminster Larger Catechism": 196,
    "Westminster Confession of Faith": 33, "Thirty-Nine Articles": 39, "Belgic Confession": 37,
    "Second London Baptist Confession": 32, "Sermons of John Wesley": 141, "The Temple": 160,
    "Smalcald Articles": 20, "Formula of Concord, Solid Declaration": 12,
    "Laws of Ecclesiastical Polity": 58, "The Book of Homilies, First Book": 12, "Bonner's Homilies": 13,
    "The Book of Homilies, Second Book": 21, "Donne's LXXX Sermons": 80, "Donne's Fifty Sermons": 50,
    "Donne's XXVI Sermons": 23, "Holy Sonnets": 19,
}


@pytest.mark.parametrize("book, least", WORKS.items())
def test_each_work_is_whole(lookup, book, least):
    assert len(lookup._data["reformation"][book]) >= least


@pytest.mark.parametrize("ref, book, words", [
    ("Calvin's Institutes 1.1.1", "Institutes of the Christian Religion", "two parts: the knowledge of God and of ourselves"),
    ("Heidelberg 1", "Heidelberg Catechism", "What is thy only comfort in life and death?"),
    ("WSC 1", "Westminster Shorter Catechism", "Man's chief end is to glorify God"),
    ("Augsburg Confession 4:1", "Augsburg Confession", "cannot be justified before God by their own strength"),
    ("95 Theses 1", "Ninety-Five Theses", "Poenitentiam agite"),
    ("Luther on Galatians 2:20", "Luther on Galatians", "crucified with Christ"),
    ("39 Articles 11", "Thirty-Nine Articles", "accounted righteous before God"),
    ("Herbert 15", "The Temple", "Easter-wings"),
    ("Hooker 1.3:1", "Laws of Ecclesiastical Polity", "law"),
    ("Homilies 1:1", "The Book of Homilies, First Book", "knowledge of Holy Scripture"),
    ("Holy Sonnets 1", "Holy Sonnets", "THOU hast made me"),
])
def test_citations(lookup, ref, book, words):
    r = lookup.get_verse(ref)
    assert r["found"] and r["reference"].startswith(book), r.get("reference")
    assert words in r["text"]


def test_institutes_alone_is_still_cassian(lookup):
    assert not lookup.get_verse("Institutes 1:1")["reference"].startswith("Institutes of the Christian")


def test_no_source_furniture(lookup):
    junk = re.compile(r"Project Gutenberg|Public domain|Internet Sacred Text|\[Sidenote|\[\d+\]|FOOTNOTES|"
                      r"cover art|No part of this publication|Edited by George Lyons|\{\d+\}")
    for book, chapters in lookup._data["reformation"].items():
        for ch, verses in chapters.items():
            for v, text in verses.items():
                assert not junk.search(text), (book, ch, v, text[:120])
