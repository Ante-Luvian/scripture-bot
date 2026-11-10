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
    ("Slavonic Life of Adam and Eve 28:1", "And we sat together before the gate of paradise"),
    ("Slavonic Adam 29:1", "Rise up! my lord, that we may seek us food"),         # (printed "xxxix")
    ("Slavonic Adam 35:1", "But Adam said: 'Eve, since thou repentest of"),          # (a paragraph inside xxxv)
    ("Slavonic Adam 40:1", "*(Passage follows exactly parallel to Apocalypsis Mosis"),
    ("Words of Gad the Seer 1:1", "In the thirty-first year of King David in Jerusalem"),
    ("Gad the Seer 10:243", "The eyes of all look to you expectantly"),               # (printed "343")
    ("Gad the Seer 14:367", "And the man dressed in linen cried like a ram’s horn"),  # (printed "376")
    ("Gad the Seer 10:265", "Happy is he who waiteth (for the time)"),                # ("265b")
    ("Gad the Seer 1:63", "And I lifted up my voice"),                                # (the page: "oice")
    ("Apocalypse of Pseudo-Methodius 1:1", "Know that when Adam and Eve left Paradise they were virgins"),
    ("Apocalypse of Pseudo-Methodius 1:2", "[Adam knew his wife Eve"),
    ("Apocalypse of Pseudo-Methodius 4:5", "his descendant Izdes took his own mother"),
    ("Apocalypse of Pseudo-Methodius 13:39", "then sudden destruction falleth upon them"),
    ("Apocalypse of Pseudo-Methodius (Latin) 1:1", "Surely it ought to be known that when they left paradise"),
    ("Latin Pseudo-Methodius 14:23", "Amen."),
    ("Apocalypse of Methodius 14:22", "the grace and love for mankind of our Lord"),
    ("Joseph and Aseneth 1:1", "It came to pass in the first year of the seven years of plenty"),
    ("Aseneth 1:13", "Are you not king of all the earth?"),                           # (printed as a second 12)
    ("Asenath 4:3", "And they took out all the good things"),                        # (no number on the page)
    ("Aseneth 12:2", "“O Lord, God of the ages, that didst give to all the breath of life,\nThat didst bring"),  # (a list)
    ("Aseneth 13:1", "Look upon my orphanhood, O Lord"),                             # (the page: "ophanhood")
    ("Aseneth 24:5", "And Pharaoh’s son was overjoyed"),                             # ("5.And")
    ("Aseneth 29:11", "And Joseph was king of Egypt for forty-eight years."),
    ("Apocalypse of Abraham 1:1", "*The Book of the Revelation of Abraham, the son of Terah"),
    ("Apocalypse of Abraham 17:3", "Eternal, mighty, Holy, El, God only – Supreme!\nYou who are self-originated"),
    ("Apocalypse of Abraham 29:12", "See, Abraham, what you have seen,\nAnd [hear] what you have heard"),
    ("Testament of Job 1:1", "*Book of Job, called Jobab, his life and the transcript of his Testament*"),
    ("Testament of Job 5:14", "that it should not be brought to me, insisting that she should only have"),   # (a lost line)
    ("Testament of Job 7:4", "the king of Teman, and Bildad, and Sophar"),            # (the copy: "Balad")
    ("Testament of Job 10:23", "*Chorus*\n“Our sins are forgiven"),
    ("Testament of Job 12:19", "To our Lord be glory. Amen."),
    ("Lives of the Prophets 1:1", "*Isaiah*\nHe was of Jerusalem."),
    ("Lives of the Prophets 23:4", "Upon his death he was buried in Samaria."),
    ("Apocalypse of Zephaniah 1:1", "… dead. We will bury him like any man."),
    ("Apocalypse of Zephaniah 7:11", "in my (own) language …\n*two pages missing*"),
    ("Apocalypse of Zephaniah 4:9", "because [thou] are pure before him"),
    ("Apocalypse of Zephaniah 13:1", "And a spirit took me and brought me up into the fifth heaven"),
    ("Apocalypse of Zephaniah 14:1", "I saw a soul which five thousand angels punished and guarded."),
    ("Apocalypse of Elijah 19", "The word of the Lord happened to me, saying, “Son of man"),
    ("Apocalypse of Elijah 35", "He will not overcome them, the son of lawlessness."),        # ("law-" "lessness")
    ("Apocalypse of Elijah 43", "and with Christ a thousand years."),                          # (page 44's words)
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
    # the Greek and Latin Pseudo-Methodius are the page's two columns, kept apart; the verse prophecy keeps its alias
    greek, latin = charles["Apocalypse of Pseudo-Methodius"], charles["Apocalypse of Pseudo-Methodius (Latin)"]
    assert list(greek) == list(latin) == [str(n) for n in range(1, 15)]
    assert greek["1"]["1"] != latin["1"]["1"]
    assert "Garstad" in lookup.get_verse("Apocalypse of Pseudo-Methodius 1:1")["source"]
    assert lookup.get_verse("pseudo-methodius 326")["reference"].startswith("The Revelations of Methodius")
    for book in ("Apocalypse of Pseudo-Methodius", "Apocalypse of Pseudo-Methodius (Latin)", "Words of Gad the Seer",
                 "Slavonic Life of Adam and Eve"):
        for verses in charles[book].values():
            for text in verses.values():
                assert not re.search(r"\b(?:of|if)(?:the|his|all|[A-Z])\w*|\bl(?:shmael|srael|zdes)\b|\boice\b|\d+[ab]?\s*$", text), (book, text[:100])
    # Gad's verses run on through the book (the page has no chapter XI heading)
    gad = charles["Words of Gad the Seer"]
    assert [int(v) for vs in gad.values() for v in vs] == list(range(1, 376))
    # the six of 2026-11-10: whole books, chapters in order, no footnote marks, markers or page furniture
    for book, chapters in (("Joseph and Aseneth", 29), ("Apocalypse of Abraham", 32), ("Testament of Job", 12),
                           ("Lives of the Prophets", 23), ("Apocalypse of Zephaniah", 14), ("Apocalypse of Elijah", 1)):
        assert list(charles[book]) == [str(n) for n in range(1, chapters + 1)], book
        for verses in charles[book].values():
            for text in verses.values():
                assert not re.search(r"@@|\[\d+\]|  |<|>|&\w+;|\bPage \d|tohdee|Goodacre", text), (book, text[:100])
                assert text.count("*") % 2 == 0, (book, text[:100])
    # Job's verses run on as the print numbers them; the copy's he-for-be and time-for-the slips are put right
    job = charles["Testament of Job"]
    assert [len(job[str(c)]) for c in range(1, 13)] == [28, 17, 37, 28, 24, 31, 39, 26, 20, 26, 29, 19]
    assert not any(re.search(r"\b(?:should|would|not) he (?:firmly|robbed|found)\b|\bsaving\b|for time", t)
                   for vs in job.values() for t in vs.values())
    assert "Kohler" in lookup.get_verse("Testament of Job 1:1")["source"]
    # Elijah: one chapter numbered by Steindorff's pages 19-43, every verse a whole sentence or more
    elijah = charles["Apocalypse of Elijah"]["1"]
    assert list(elijah) == [str(n) for n in range(19, 44)]
    assert all(re.search(r"[.!?”\]]$", t) for t in elijah.values()), [t[-40:] for t in elijah.values()]
    # Aseneth: Cook's numbers, with the one the page leaves out (28:13) not guessed at
    aseneth = charles["Joseph and Aseneth"]
    assert "13" not in aseneth["28"] and "14" in aseneth["28"]
    assert list(aseneth["12"]) == [str(n) for n in range(1, 13)]
    # the "for," the Word files put after a clause-opening "for" is gone; "For, behold" keeps its comma
    for book in ("Apocalypse of Abraham", "Testament of Job", "Lives of the Prophets", "Apocalypse of Elijah"):
        for verses in charles[book].values():
            assert not any(re.search(r"(?<![A-Za-z] )\b[Ff]or, (?!behold\b|lo\b|for\b)", t) for t in verses.values()), book
    # Meqabyan: the editor's chapter summaries ("Chapter 5: An extended attack on...") are not in the verses
    meq = lookup._data["charles"]
    for book, count in (("1 Meqabyan", 36), ("2 Meqabyan", 21), ("3 Meqabyan", 10)):
        assert list(meq[book]) == [str(n) for n in range(1, count + 1)], book
        for verses in meq[book].values():
            assert not any(re.search(r"\bChapter \d+:", t) for t in verses.values()), book
