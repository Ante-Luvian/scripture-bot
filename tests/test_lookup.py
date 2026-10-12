"""ScriptureLookup.get_verse against the local corpus -- every reference
format the README promises, plus the error paths."""
import pytest


@pytest.mark.parametrize("ref, canonical, snippet", [
    # Bible + aliases + case
    ("John 3:16",            "John 3:16",                        "For God so loved the world"),
    ("Jn 3:16",              "John 3:16",                        "For God so loved the world"),
    ("john 3:16",            "John 3:16",                        "For God so loved the world"),
    ("Gen 1:1",              "Genesis 1:1",                      "In the beginning God created"),
    ("Ps 23:1",              "Psalms 23:1",                      "The Lord is my shepherd"),
    ("Revelation 22:21",     "Revelation 22:21",                 "The grace of our Lord"),
    # Apocrypha
    ("Wisdom 7:22",          "Wisdom of Solomon 7:22",           "wisdom"),
    ("Tobit 1:1",            "Tobit 1:1",                        "Tobit"),
    ("1 Maccabees 1:1",      "1 Maccabees 1:1",                  "Alexander"),
    ("Ps Sol 17:1",          "Psalms of Solomon 17:1",           "our King"),
    # LDS
    ("1 Nephi 3:7",          "1 Nephi 3:7",                      "I, Nephi"),
    ("1Ne 3:7",              "1 Nephi 3:7",                      "I, Nephi"),
    ("D&C 76:22",            "Doctrine and Covenants 76:22",     "testimonies"),
    ("Moses 1:39",           "Moses 1:39",                       "my work and my glory"),
    ("Articles of Faith 1:13", "Articles of Faith 1:13",         "honest, true, chaste"),
    # Charles
    ("Enoch 1:9",            "Book of Enoch 1:9",                "ten thousands"),
    ("Jubilees 3:4",         "Book of Jubilees 3:4",             "It is not good"),
    # Apostolic Fathers
    ("1 Clem 5:1",           "1 Clement 5:1",                    "examples of ancient days"),
    ("Ign Eph 7:2",          "Ignatius to the Ephesians 7:2",    "one only physician"),
    ("Ign Rom 4:1",          "Ignatius to the Romans 4:1",       "I write to all the churches"),
    ("Pol Phil 2:1",         "Polycarp to the Philippians 2:1",  "gird up your loins"),
    ("Mart Pol 9:1",         "Martyrdom of Polycarp 9:1",        "entered into the stadium"),
    ("Barn 4:1",             "Epistle of Barnabas 4:1",          "investigate"),
    ("Did 9:1",              "Didache 9:1",                      "eucharistic thanksgiving"),
    ("Herm Vis 1:1",         "Shepherd of Hermas 1:1",           "Rhoda"),
    # Other corpora with special handling
    ("Quran 1:1",            "Quran 1:1",                        "Beneficent"),
    ("Surah 1:1",            "Quran 1:1",                        "Beneficent"),
    ("Rig Veda 10.121:9",    "Rig Veda 10.121:9",                "Begetter"),
    ("Delphi 1:1",           "Delphi 1:1",                       "Follow"),
    ("Kitab-i-Aqdas 1:1",    "Kitáb-i-Aqdas ¶1",                 "first duty"),
])
def test_found(lookup, ref, canonical, snippet):
    res = lookup.get_verse(ref)
    assert res["found"], res.get("error")
    assert res["reference"] == canonical
    assert isinstance(res["text"], str)
    assert snippet.lower() in res["text"].lower()


def test_verse_range_includes_every_verse(lookup):
    res = lookup.get_verse("Genesis 1:1-3")
    assert res["reference"] == "Genesis 1:1–3"
    for v in (1, 2, 3):
        assert f"**[{v}]**" in res["text"]


def test_cross_chapter_range(lookup):
    res = lookup.get_verse("John 7:53-8:11")
    assert res["found"]
    assert "**[7:53]**" in res["text"] and "**[8:11]**" in res["text"]


def test_whole_chapter_is_paginated(lookup):
    res = lookup.get_verse("Psalm 119")
    assert res["found"]
    assert len(res["pages"]) > 1


@pytest.mark.parametrize("ref, error_fragment", [
    ("Genesis 51:1",  "has no chapter 51"),
    ("Genesis 1:999", "Max verse: 31"),
    ("Notabook 1:1",  "Unknown book"),
    ("hello",         "Could not parse"),
    ("",              "Could not parse"),
])
def test_not_found(lookup, ref, error_fragment):
    res = lookup.get_verse(ref)
    assert not res["found"]
    assert error_fragment in res["error"]


@pytest.mark.parametrize("ref, label", [
    ("Psalm 151:1", "Psalm 151:1"),     # was "Psalm 151 151:1"
    ("Psalm 151",   "Psalm 151"),       # was "Psalm 151 151"
    ("Psalm 155:1", "Psalm 155:1"),
    ("Psalm 23:1",  "Psalms 23:1"),     # ordinary psalms unaffected
])
def test_extra_psalm_labels(lookup, ref, label):
    res = lookup.get_verse(ref)
    assert res["found"]
    assert res["reference"] == label


# ANE data is stored as section -> {"1": text}; _ane_fetch must unwrap it.
@pytest.mark.parametrize("ref, reference, snippet", [
    ("Gilgamesh 1:1",  "Gilgamesh Tablet 1 1", "He who the heart of all matters"),
    ("Baal 1:1",       "Baal and Yamm 1",      "El Grants Yamm Dominion"),
    ("Aten 1",         "The Great Hymn to the Aten 1", ""),
    ("Muallaqat 1:1",  "Muallaqat: Imru' al-Qais 1", ""),
])
def test_ane_section(lookup, ref, reference, snippet):
    res = lookup.get_verse(ref)
    assert res["found"]
    assert res["reference"] == reference
    assert isinstance(res["text"], str) and res["text"].strip()
    assert snippet in res["text"]


@pytest.mark.parametrize("ref", ["Gilgamesh 1", "Aten", "Book of the Dead"])
def test_ane_whole_book(lookup, ref):
    res = lookup.get_verse(ref)
    assert res["found"]
    assert isinstance(res["text"], str) and res["text"].strip()
    for page in res["pages"] or []:
        assert isinstance(page, str)


def test_ane_missing_section(lookup):
    res = lookup.get_verse("Gilgamesh 1:99")
    assert not res["found"]
    assert "has no section 99" in res["error"]


# ── Known bugs (strict xfail: the suite fails once they're fixed, as a
#    reminder to drop the marker) ─────────────────────────────────────────────


# Hermas data uses Lightfoot's continuous chapters (Visions 1-25, Mandates
# 26-49, Similitudes 50-114), but "Herm Man"/"Herm Sim" are plain aliases
# into it, so "Herm Man 1:1" returns continuous chapter 1 (a Vision).
@pytest.mark.xfail(strict=True, reason="'Herm Man N' isn't offset into the Mandates (start at ch. 26)")
def test_hermas_mandate_1(lookup):
    assert "believe that God is One" in lookup.get_verse("Herm Man 1:1")["text"]


@pytest.mark.xfail(strict=True, reason="'Herm Sim N' isn't offset into the Similitudes (start at ch. 50)")
def test_hermas_similitude_1(lookup):
    assert "dwelling in a foreign land" in lookup.get_verse("Herm Sim 1:1")["text"]

