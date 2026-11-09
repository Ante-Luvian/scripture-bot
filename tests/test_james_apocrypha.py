"""M. R. James's Apocryphal New Testament (1924) (scripts/build_gnosis.py james): cited by the sections he gives,
without his notes, and with the bracketed words the Gnostic Society's copy garbles put back in order."""
import re

import pytest


@pytest.mark.parametrize("ref, words", [
    ("Acts of John 18", "Now John was hastening to Ephesus"),             # (the beginning is lost)
    ("Acts of John 94", "let us sing an hymn to the Father"),
    ("Acts of John 23", "Now when she had arisen [who had lain incurable for] seven days"),
    ("Virtues of John 14", "Craton, a philosopher"),
    ("Acts of Andrew 1:1", "After the Ascension the apostles dispersed"),
    ("Acts of Andrew 2:1", "is there in you altogether slackness"),
    ("Acts of Paul 2:1", "When Paul went up unto Iconium"),
    ("Acts of Paul 2:33", "But Thecla, being taken out of the hand of Tryphaena"),     # (printed "38")
    ("Acts of Paul 10:1", "Now there were awaiting Paul at Rome"),
    ("Third Corinthians 1:11", "and that God is not Almighty"),           # (numbered mid-sentence)
    ("3 Corinthians 3:36", "And whoso receiveth"),                       # (printed "86")
    ("Acts of Peter 35", "Lord, whither goest thou"),
    ("Acts of Peter 17", "I drove this Simon out of Judaea"),             # (James's bracketed note before it, gone)
    ("Acts of Thomas 1", "*The First Act: When he went into India with Abbanes the merchant.*"),
    ("Acts of Thomas 108", "When I was an infant child in the palace of my Father"),
    ("Acts of Thomas 144", "[give us the constant bread of the day, Syr.]"),
    ("Hymn of the Pearl 111", "[and my letter was a letter] and the King [as ambassador] sealed it [with his right hand]"),
    ("Questions of Bartholomew 1:1", "After the resurrection from the dead of our Lord Jesus Christ, Bartholomew"),
    ("Questions of Bartholomew 5:1", "Declare unto us, Lord what sin"),      # (printed "VI")
    ("Apocalypse of Thomas 1:1", "Here beginneth the epistle of the Lord unto Thomas"),
    ("Ethiopic Apocalypse of Peter 1", "And he (Peter) pondered thereon"),
    ("Secret Mark 1", "From the letters of the most holy Clement"),
])
def test_passages(lookup, ref, words):
    result = lookup.get_verse(ref)
    assert result.get("found"), ref
    assert words in result["text"], (ref, result["text"][:300])


def test_no_garbled_brackets_or_notes(lookup):
    books = lookup._data["nt_apocrypha"]
    for book in ("Acts of John", "Acts of Andrew", "Acts of Paul", "Acts of Peter", "Acts of Thomas",
                 "Questions of Bartholomew", "Apocalypse of Thomas", "Ethiopic Apocalypse of Peter"):
        for verses in books[book].values():
            for text in verses.values():
                assert not re.search(r"\[[A-Z]{2,}\b(?! [A-Z]{2,})", text) or book != "Acts of Thomas", text[:80]
                assert not re.search(r"Bonnet|Archive|Scanned and|Flamion|Vouaux|The Slavonic", text), (book, text[:80])
    assert "[in the midst of the sea]" in books["Acts of Thomas"]["1"]["108"]


def test_the_secret_gospel_says_its_disputed(lookup):
    assert "forgery" in lookup.get_verse("Letter to Theodore 1")["source"]
    assert lookup._resolve_book("acts of thomas")[1] == "Acts of Thomas"           # (James's whole text)
    assert lookup._resolve_book("various acts of thomas")[1] == "Various Acts of Thomas"
