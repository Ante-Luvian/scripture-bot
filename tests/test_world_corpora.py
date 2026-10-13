"""The texts added from the Sacred Books of the East and elsewhere (scripts/build_world_texts.py):
each opens at a known passage, by its usual citation, with the words that are there."""
import pytest


@pytest.mark.parametrize("ref, words", [
    ("Japji 1:6", "Hukam of His Command"),
    ("Guru Granth Sahib 1:1", "One Universal Creator God"),
    ("Guru Granth Sahib 2:1", "Some sing that He watches over us"),
    ("Akaranga Sutra 1.1.1:1", "I (Sudharman) have heard the following discourse"),
    ("Uttaradhyayana Sutra 1:1", "discipline of a houseless monk"),
    ("Kalpa Sutra 1:2", "Venerable Ascetic Mahavira"),
    ("Kojiki 1:1", "Plain of High Heaven"),
    ("Nihongi 1:1", "Heaven and Earth were not yet separated"),
    ("Popol Vuh 1:1", "Hurakan"),
    ("Vendidad 2:2", "The fair Yima, the great shepherd"),
    ("Bundahishn 1:2", "Aûharmazd is supreme in omniscience and goodness"),
    ("Zhuangzi 1:1", "In the Northern Ocean there is a fish"),
    ("Mencius 1.1.1:1", "Mencius went to see king Hûi of Liang"),
    ("Mencius 4.2.11:1", "The great man does not think beforehand of his words"),     # numbered across the lost chapters
    ("Mencius 7.2.38:1", "From Yâo and Shun down to T'ang"),
    ("Great Learning 1:1", "illustrate illustrious virtue"),
    ("Doctrine of the Mean 1:1", "What Heaven has conferred is called The Nature"),
    ("Masnavi 1.0:1", "HEARKEN to the reed-flute"),
    ("Rubaiyat 1:12", "A Book of Verses underneath the Bough"),
    ("Lotus Sutra 2:1", "The Buddha knowledge, Sâriputra, is profound"),
    ("Questions of King Milinda 2.2:1", "He who is born, Nâgasena"),
    ("Jataka 7:1", "Your son am I"),
    ("Chandogya Upanishad 1.1:1", "meditate on the syllable"),
    ("Mundaka Upanishad 1.1:1", "BRAHMA was the first of the Devas"),
    ("Laws of Manu 1:1", "The great sages approached Manu"),
    ("Yoga Sutras 1:2", "Union is restraining the thought-streams"),
    ("Kalevala 1:1", "IN primeval times, a maiden"),
    ("Mabinogion 1:1", "King Arthur was at Caerlleon upon Usk"),
    ("Cloud of Unknowing 1:1", "GHOSTLY friend in God"),
    ("Revelations of Divine Love 5:1", "spiritual sight of His homely loving"),
    ("Practice of the Presence of God 1.1:1", "3rd of August, 1666"),
    ("Gathas 1:1", ""),                                       # moved to the Zoroastrian group, still found
])
def test_passages(lookup, ref, words):
    result = lookup.get_verse(ref)
    assert result.get("found"), ref
    assert words in result["text"], (ref, result["text"][:200])


def test_traditions(lookup):
    from scripture_lookup import TRADITIONS, tradition
    for key in ("sikh", "jain", "shinto", "zoroastrian", "mesoamerican", "finnish", "celtic"):
        _, corpora = TRADITIONS[key]
        assert all(lookup._data.get(c) for c in corpora), key
    assert tradition("Sikhism") == "sikh" and tradition("Maya") == "mesoamerican" and tradition("Welsh") == "celtic"
    hits = lookup.search_by_corpus("dharma", ("jain",))
    assert hits and all(label == "🤚 Jain" for label in hits)


def test_aliases(lookup):
    for name, book in (("Chuang Tzu", "Zhuangzi"), ("Manusmriti", "Laws of Manu"), ("Nihon Shoki", "Nihongi"),
                       ("Mathnawi", "Masnavi"), ("Japji Sahib", "Japji"), ("Milindapanha", "Questions of King Milinda")):
        assert lookup._resolve_book(name)[1] == book, name


def test_no_page_furniture(lookup):
    import re
    new = ["Guru Granth Sahib", "Akaranga Sutra", "Kojiki", "Vendidad", "Yasna", "Zhuangzi", "Mencius", "Masnavi",
           "Lotus Sutra", "Jataka", "Chandogya Upanishad", "Laws of Manu", "Kalevala", "Mabinogion", "Cloud of Unknowing"]
    for book in new:
        corpus, _ = lookup._resolve_book(book)
        for chapter in lookup._data[corpus][book].values():
            for text in chapter.values():
                assert not re.search(r"sacred-texts\.com|\[\*\d+\]|\[p\. \d+\]|^Footnotes$|^\^\d+:", text, re.M), book
