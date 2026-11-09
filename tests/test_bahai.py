"""The Bahá'í writings (scripts/build_bahai.py): every work of the Báb, Bahá'u'lláh and 'Abdu'l-Bahá in the Bahá'í
Reference Library, numbered as they're cited."""
import re

import pytest

BOOKS = ["Selections from the Writings of the Bab", "Kitab-i-Aqdas", "Kitab-i-Iqan", "The Hidden Words (Arabic)",
         "The Hidden Words (Persian)", "Call of the Divine Beloved", "Gems of Divine Mysteries",
         "Gleanings from the Writings of Baha'u'llah", "Prayers and Meditations", "Summons of the Lord of Hosts",
         "Tablets of Baha'u'llah", "Tabernacle of Unity", "Days of Remembrance", "Epistle to the Son of the Wolf",
         "Additional Tablets of Baha'u'llah", "Additional Prayers of Baha'u'llah",
         "Selections from the Writings of Abdu'l-Baha", "Some Answered Questions", "Secret of Divine Civilization",
         "A Traveler's Narrative", "Memorials of the Faithful", "Light of the World", "Tablets of the Divine Plan",
         "Tablets to The Hague", "Tablet to Auguste Forel", "Will and Testament of Abdu'l-Baha",
         "Additional Tablets of Abdu'l-Baha", "Additional Prayers of Abdu'l-Baha", "Paris Talks",
         "Promulgation of Universal Peace", "Twelve Table Talks", "Baha'i Prayers"]


def test_every_work_is_here(lookup):
    assert set(BOOKS) <= set(lookup._data["bahai"])


@pytest.mark.parametrize("ref, words", [
    ("Kitab-i-Iqan 1", "No man shall attain the shores of the ocean of true understanding"),
    ("Kitab-i-Iqan 213", "But, O my brother, when a true seeker determineth"),       # (the famous ¶213)
    ("Kitab-i-Iqan 290", "Glorified be our Lord, the Most High!"),
    ("Gleanings 1", "Lauded and glorified art Thou, O Lord, my God!"),
    ("Some Answered Questions 1:1", "Nature is that condition or reality"),
    ("Selections from the Writings of the Bab 1", "This is an epistle from this lowly servant"),
    ("Will and Testament of Abdu'l-Baha 3:13", "The Glory of Glories rest upon you!"),
    ("Gems of Divine Mysteries 59", "Were I to recount all the verses"),          # (its own "59" taken off)
    ("Summons of the Lord of Hosts 3:1", "The Pen of the Most High proclaimeth"),
    ("Tablets of Baha'u'llah 1", "All glory be to this Day"),
    ("Paris Talks 1:1", "When a man turns his face to God he finds sunshine everywhere"),
    ("Promulgation of Universal Peace 140:1", "This is my last meeting with you"),
    ("Tablets of the Divine Plan 1", "Tablet to the Bahá’ís of the Northeastern States"),
    ("Seven Valleys 2", "*The Seven Valleys*"),                          # (now in The Call of the Divine Beloved)
    ("Call of the Divine Beloved 7", "*The Four Valleys*"),
])
def test_passages(lookup, ref, words):
    result = lookup.get_verse(ref)
    assert result.get("found"), ref
    assert words in result["text"], (ref, result["text"][:200])


def test_numbered_as_cited(lookup):
    data = lookup._data["bahai"]
    assert len(data["Kitab-i-Iqan"]) == 290 and len(data["Gleanings from the Writings of Baha'u'llah"]) == 166
    assert len(data["Prayers and Meditations"]) == 184 and len(data["Some Answered Questions"]) == 84
    assert list(data["Will and Testament of Abdu'l-Baha"]) == ["1", "2", "3"]


def test_no_library_furniture(lookup):
    """Not the library's footer, not a paragraph number left in the text, not a stray marker."""
    for book in BOOKS:
        for chapter, verses in lookup._data["bahai"][book].items():
            for v, text in verses.items():
                assert not re.search(r"Last modified:|downloaded from the Bahá’í Reference Library", text), book
                assert not re.match(rf"(?:\*[^\n]*\*\n)*{re.escape(v)}\s?[A-Z‘“]", text) or v == "1", (book, chapter, v)
                assert not re.fullmatch(r"\s*–\s*\d+\s*–\s*", text), (book, chapter, v)
