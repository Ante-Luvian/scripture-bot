"""Classics of Islam and Sufism from sacred-texts.com (scripts/build_islamic.py): the text without the site's header,
navigation, page numbers, line numbers or the translators' notes."""
import re

import pytest


@pytest.mark.parametrize("ref, words", [
    ("Alchemy of Happiness 1:1", "KNOWLEDGE of self is the key to the knowledge of God"),
    ("Mishkat 1:2", "The Real Light is Allâh"),
    ("Conference of the Birds 1", "Once on a time from all the Circles seven\nBetween the stedfast Earth and rolling Heaven"),
    ("Bustan 0:2", "In the name of Him Who created and sustains the world"),
    ("Gospel of Barnabas 1:1", "*In this first chapter is contained the annunciation"),
    ("Gospel of Barnabas 222", "among whom is Paul deceived"),
    ("Gulistan 1:1", "*The Manners Of Kings*\nI heard a padshah giving orders to kill a prisoner"),
    ("Gulistan 8:76", "The first sovereign who laid stress on costume"),            # ("Maxim 76")
    ("Secret Rose Garden 1:1", "*THE EYE AND THE LIP*"),
    ("Tarjuman al-Ashwaq 34:1", "At the hill among the mountains of Zarúd"),       # (indexed as "XXIV")
    ("Tarjuman 2:1", "On the day of parting they did not saddle"),
    ("Salaman and Absal 1:1", "Oh Thou whose Memory quickens Lovers"),
    ("Hadiqa 1:1", "*ON THE KNOWLEDGE OF GOD.*\nOf himself no one can know Him"),
    ("Scroll of Wisdom 1:1", "In the Name of God, the Merciful and Compassionate"),
])
def test_passages(lookup, ref, words):
    result = lookup.get_verse(ref)
    assert result.get("found"), ref
    assert words in result["text"], (ref, result["text"][:300])


def test_no_site_furniture(lookup):
    for corpus, book in (("sufi", "Alchemy of Happiness"), ("sufi", "Niche for Lights"), ("sufi", "Bird Parliament"),
                         ("sufi", "Bustan"), ("quran", "Gospel of Barnabas"), ("sufi", "Gulistan"),
                         ("sufi", "Secret Rose Garden"), ("sufi", "Tarjuman al-Ashwaq"), ("sufi", "Salaman and Absal"),
                         ("sufi", "Hadiqat al-Haqiqat"), ("sufi", "Scroll of Wisdom")):
        for verses in lookup._data[corpus][book].values():
            for text in verses.values():
                assert not re.search(r"sacred-texts|Next:|Previous|\bIndex\b|Buy this Book|\{p\.|\[p\. |\[\d+\]|"
                                     r"Footnotes|THE END|\n\d{1,4}\n|\s\d{2,4}$", text), (book, text[:120])
    # (Gairdner's own preface is not al-Ghazali's)
    assert "my general equipment was insufficient" not in str(lookup._data["sufi"]["Niche for Lights"])
    assert "Click to enlarge" not in str(lookup._data["sufi"]["Salaman and Absal"])
    assert "Printed by" not in str(lookup._data["sufi"]["Scroll of Wisdom"])
    assert len(lookup._data["sufi"]["Tarjuman al-Ashwaq"]) == 61
