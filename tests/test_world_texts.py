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
    ("Epictetus 1:1", "Enchiridion 1:1", "**[1]** There are things which are within our power"),
    ("Imitation of Christ 1.1:2", "Imitation of Christ 1.1:2", "**[2]** His teaching surpasseth"),
    ("Imitation of Christ 3.5", "Imitation of Christ 3.5", "**[1]** *Of the wonderful power of the Divine Love*"),
    ("Rule of Benedict 0:1", "Rule of Benedict 0:1", "**[1]** Listen, my son"),
    ("Inferno 1.1", "Inferno 1:1–3", "**[1]** Midway upon the journey of our life\nI found myself"),
    ("Inferno 1:5", "Inferno 1:4–6", "**[4]** Ah me!"),                              # the tercet containing line 5
    ("Paradiso 33.145", "Paradiso 33:145", "**[145]** The Love which moves the sun and the other stars."),
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
