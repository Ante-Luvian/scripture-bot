"""Jewish pseudepigrapha added from Charles's edition and M. R. James (scripts/build_pseudepigrapha.py), and the
Apocalypse of Sedrach from ANF 9."""
import re

import pytest


@pytest.mark.parametrize("ref, words", [
    ("2 Baruch 1:1", "And it came to pass in the twenty-fifth year of Jeconiah"),
    ("2 Baruch 32:1", "if you prepare your hearts, so as to sow in them the fruits of the law"),   # (anchored "32.1")
    ("2 Baruch 85:2", "No more, we were in our own land"),          # (where every copy online stops)
    ("3 Baruch 0:1", "A narrative and revelation of Baruch"),
    ("3 Baruch 1:1", "Verily I Baruch was weeping"),
    ("Greek Apocalypse of Baruch 17:1", ""),
    ("Biblical Antiquities 1:1", "The beginning of the world. Adam begat three sons and one daughter"),
    ("Pseudo-Philo 43:1", "Eluma conceived and bare a son and called his name Samson"),   # (no heading of its own)
    ("Pseudo-Philo 29:1", "the people appointed Zebul ruler"),                            # ("XXIX And": no stop)
    ("Apocalypse of Sedrach 1:1", "Beloved, let us prefer nothing in honour except sincere love"),
    ("History of the Rechabites 1:1", ""),
    ("4 Baruch 1:1", "Jeremiah, my chosen one, arise and depart from this city"),        # (the longer version)
    ("Paraleipomena Jeremiou 9:32", "This is the stone that was the ally of Jeremiah"),
    ("Jasher 1:1", "And God said, Let us make man in our image"),
    ("Jasher 2:32", "And the wives of Lamech heard what Lamech had done"),            # (run on in the source)
    ("Georgian Book of Adam 1:1", "when Adam went out from paradise with his wife Eve"),
    ("Epistle of the Apostles 1", "The book which Jesus Christ revealed unto his disciples"),
    ("Epistula Apostolorum 41", "He answered and said unto us: Go and preach"),     # (run on in the source)
    ("Laodiceans 6", "And now are my bonds seen of all men"),                         # (printed as a second 5)
    ("Paul and Seneca 10", "*TO SENECA, PAUL, greeting*"),
    ("1 Meqabyan 1:1", "There was a man whose name was called Tseerutsaydan"),
    ("1 Meqabyan 2:1", "There was a man born from the tribe of Benjamin whose name was called Maccaebeus"),
    ("2 Meqabyan 1:1", "This is a book that describes how Meqabis met with Israel"),
    ("3 Meqabyan 10:28", "Prepare goodly Work - that you might cross from death toward Life"),
    ("3 Meqabyan 10:29", "the third book that speaks the words of Meqabyan are fulfilled"),
])
def test_passages(lookup, ref, words):
    result = lookup.get_verse(ref)
    assert result.get("found"), ref
    assert words in result["text"], (ref, result["text"][:300])


def test_no_site_furniture(lookup):
    charles = lookup._data["charles"]
    assert "It is not easy to imagine" not in lookup.get_verse("Laodiceans 20")["text"]      # (James's comment)
    assert "In those days the Lord spoke to Jeremiah" not in lookup.get_verse("4 Baruch 1:1")["text"]   # (shorter)
    for book in ("2 Baruch", "3 Baruch", "4 Baruch", "Biblical Antiquities", "Book of Jasher", "Georgian Book of Adam"):
        for verses in charles[book].values():
            for text in verses.values():
                assert not re.search(r"Wesley|Copyright|finish$|Gen\. \d+:\d+|p\. \d+|Next:|(?<!\.)\s[,;:]", text)    # (". . . ," is Charles's gap), (book, text[:100])
    assert "ends at 85:2" in lookup.get_verse("2 Baruch 1:1")["source"]
    # Meqabyan: the editor's chapter summaries ("Chapter 5: An extended attack on...") are not in the verses
    meq = lookup._data["charles"]
    for book, count in (("1 Meqabyan", 36), ("2 Meqabyan", 21), ("3 Meqabyan", 10)):
        assert list(meq[book]) == [str(n) for n in range(1, count + 1)], book
        for verses in meq[book].values():
            assert not any(re.search(r"\bChapter \d+:", t) for t in verses.values()), book
