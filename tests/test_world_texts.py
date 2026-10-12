"""Texts added from Project Gutenberg (scripts/build_world_texts.py)."""
import pytest


@pytest.mark.parametrize("ref, reference, starts", [
    ("Dhammapada 1:5", "Dhammapada 1:5", "**[5]** For hatred does not cease by hatred"),
    ("Dhammapada 183", "Dhammapada 14:183", "**[183]** Not to commit any sin"),      # cited by verse number
    ("Dhp 2:183", "Dhammapada 14:183", "**[183]** Not to commit any sin"),          # wrong chapter given
    ("Dhammapada 59", "Dhammapada 4:58–59", "**[58]** (vv. 58–59) As on a heap of rubbish"),  # a paired verse
    ("Diamond Sutra 32:2", "Diamond Sutra 32:2", "**[2]** “In what attitude of mind"),
])
def test_buddhist(lookup, ref, reference, starts):
    r = lookup.get_verse(ref)
    assert r["found"], r
    assert r["reference"] == reference and r["text"].startswith(starts)


@pytest.mark.parametrize("ref, reference, starts", [
    ("Tao Te Ching 1:1", "Tao Te Ching 1:1", "**[1]** The Tao that can be trodden"),
    ("Analects 2.4", "Analects 2:4", "**[4]** The Master said, 'At fifteen"),
    ("Analects 7:17", "Analects 7:17", "**[17]** The Master's frequent themes"),   # its heading lacked a full stop
    ("I Ching 1:1", "I Ching 1:1", "**[1]** The Judgment: Qian (represents) what is great"),
    ("Yijing 64:2", "I Ching 64:2", "**[2]** The Image:"),
])
def test_chinese(lookup, ref, reference, starts):
    r = lookup.get_verse(ref)
    assert r["found"], r
    assert r["reference"] == reference and r["text"].startswith(starts)


@pytest.mark.parametrize("ref, reference, starts", [
    ("Bhagavad Gita 2:47", "Bhagavad Gita 2:47", "**[47]** But you have only the right to work"),
    ("Gita 18:78", "Bhagavad Gita 18:78", "**[78]**"),
    ("Isa Upanishad 1:1", "Isa Upanishad 1:1", "**[1]** All this, whatsoever exists"),
    ("Katha 1:22", "Katha Upanishad 1:22", "**[22]** Nachiketas said: O Death"),
    ("Kena 4:9", "Kena Upanishad 4:9", "**[9]** He who knows this"),
])
def test_hindu(lookup, ref, reference, starts):
    r = lookup.get_verse(ref)
    assert r["found"], r
    assert r["reference"] == reference and r["text"].startswith(starts)


@pytest.mark.parametrize("ref, reference, starts", [
    ("Meditations 4.3", "Meditations 4:3", "**[3]** Men seek retreats for themselves"),
    ("Marcus Aurelius 1:1", "Meditations 1:1", "**[1]** From my grandfather Verus [I learned]"),   # his own brackets kept
    ("Epictetus 1:1", "Enchiridion of Epictetus 1:1", "**[1]** There are things which are within our power"),
    ("Imitation of Christ 1.1:2", "Imitation of Christ 1.1:2", "**[2]** His teaching surpasseth"),
    ("Imitation of Christ 3.5", "Imitation of Christ 3.5", "**[1]** *Of the wonderful power of the Divine Love*"),
    ("Rule of Benedict 0:1", "Rule of Benedict 0:1", "**[1]** Listen, my son"),
    ("Inferno 1.1", "Inferno 1:1–3", "**[1]** Midway upon the journey of our life\nI found myself"),
    ("Inferno 1:5", "Inferno 1:4–6", "**[4]** Ah me!"),                              # the tercet containing line 5
    ("Paradiso 33.145", "Paradiso 33:145", "**[145]** The Love which moves the sun and the other stars."),
    ("Works and Days 289", "Works and Days 1:285–289", "**[285]** But the generation of the man who swears truly"),
    ("Shield 140", "Shield of Heracles 1:140–144", "**[140]**"),
])
def test_classics(lookup, ref, reference, starts):
    r = lookup.get_verse(ref)
    assert r["found"], r
    assert r["reference"] == reference and r["text"].startswith(starts)


def test_dante_ends_each_canto_on_its_last_line(lookup):
    for cantica, cantos, total in (("Inferno", 34, 4720), ("Purgatorio", 33, 4755), ("Paradiso", 33, 4758)):
        data = lookup._data["medieval"][cantica]
        assert len(data) == cantos
        assert sum(len(t.splitlines()) for c in data.values() for t in c.values()) == total
    assert "APPENDIX" not in str(lookup._data["medieval"]["Paradiso"]["33"])


@pytest.mark.parametrize("ref, reference, starts", [
    ("2 Enoch 1:1", "2 Enoch 1:1", "**[1]** There was a wise man, a great artificer"),
    ("Secrets of Enoch 1:2", "2 Enoch 1:2", "**[2]** At that time"),
    ("Protevangelium 1:1", "The Protevangelium of James 1:1", "**[1]** In the records of the twelve tribes"),
    ("Gospel of Nicodemus 1:1", "Acts of Pilate: First Greek Form 1:1", "**[1]** Having called a council"),
    ("Infancy Gospel of Thomas 1:1", "Gospel of Thomas: First Greek Form 1:1", "**[1]**"),
    ("Thecla 1:1", "Acts of Paul and Thecla 1:1", "**[1]**"),
])
def test_apocrypha(lookup, ref, reference, starts):
    r = lookup.get_verse(ref)
    assert r["found"], r
    assert r["reference"] == reference and r["text"].startswith(starts)


def test_apocrypha_have_no_wiki_markup(lookup):
    import re
    for corpus, book in (("nt_apocrypha", None), ("charles", "2 Enoch")):
        books = lookup._data[corpus] if book is None else {book: lookup._data[corpus][book]}
        for b in books.values():
            for chapter in b.values():
                for text in chapter.values():
                    assert not re.search(r"\{\{|\}\}|<ref|\[\[|Category:|&#\d+;", text), text[:80]
    # "Apocalypse of Moses" stays Charles's book, not the ANF "Revelation of Moses"
    assert lookup._resolve_book("Apocalypse of Moses") == ("charles", "Apocalypse of Moses")


@pytest.mark.parametrize("ref, reference, starts", [
    ("Sutta Nipata 221", "Sutta Nipata 2.1:221", "**[221]** Whatever spirits have come together"),
    ("Sutta Nipata 1007", "Sutta Nipata 5.1:1006–1008", "**[1006]** (vv. 1006–1008)"),      # a group of verses
    ("Snp 1047", "Sutta Nipata 5.4:1047", "**[1047]** 'Having considered everything"),        # printed "(1041)"
    ("Odes of Solomon 1:1", "Odes of Solomon 1:1", "**[1]** The Lord is on my head like a crown"),
    ("First Book of Adam and Eve 1:1", "First Book of Adam and Eve 1:1", "**[1]** ON the third day, God planted"),
    ("Gospel of Thomas 77", "Gospel of Thomas 77", "**[1]** Jesus said, \"It is I who am the light"),
    ("Enuma Elish 1:1", "Enuma Elish 1:1–8", "**[1]** When in the height heaven was not named"),
])
def test_sacred_texts_archive(lookup, ref, reference, starts):
    r = lookup.get_verse(ref)
    assert r["found"], r
    assert r["reference"] == reference and r["text"].startswith(starts)


def test_sutta_nipata_is_complete(lookup):
    import re
    numbers = set()
    for sutta in lookup._data["buddhist"]["Sutta Nipata"].values():
        for key, text in sutta.items():
            m = re.match(r"(?:\*[^\n]*\*\n)?\(vv\. (\d+)–(\d+)\)", text)
            numbers.update(range(int(m.group(1)), int(m.group(2)) + 1) if m else [int(key)])
    assert numbers == set(range(1, 1149))
    assert len(lookup._data["charles"]["Odes of Solomon"]) == 42
    assert "Infancy" not in lookup.get_verse("Gospel of Thomas 1")["source"]       # the sayings gospel, not the ANF one


def test_isa_still_means_isaiah(lookup):
    assert lookup.get_verse("Isa 53:5")["reference"] == "Isaiah 53:5"


def test_analects_follows_legges_numbering(lookup):
    books = lookup._data["chinese"]["Analects"]
    assert [len(books[str(b)]) for b in range(1, 21)] == [16, 24, 26, 26, 27, 28, 37, 21, 30, 18,
                                                           25, 24, 30, 47, 41, 14, 26, 11, 25, 3]


def test_whole_chapters_and_sources(lookup):
    r = lookup.get_verse("Dhammapada 1")
    assert r["found"] and r["text"].startswith("**[1]** All that we are is the result")
    assert "Müller" in r["source"]
    assert "Gemmell" in lookup.get_verse("Diamond Sutra 1")["source"]
    assert "translated together" in lookup.get_verse("Diamond Sutra 4:1")["text"]
