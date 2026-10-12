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


# ── Known bugs (strict xfail: the suite fails once they're fixed, as a
#    reminder to drop the marker) ─────────────────────────────────────────────

@pytest.mark.xfail(strict=True, reason="Psalm 151 label doubles the number: 'Psalm 151 151:1'")
def test_psalm_151_label(lookup):
    res = lookup.get_verse("Psalm 151:1")
    assert res["found"]
    assert res["reference"] == "Psalm 151:1"


# Hermas data uses Lightfoot's continuous chapters (Visions 1-25, Mandates
# 26-49, Similitudes 50-114), but "Herm Man"/"Herm Sim" are plain aliases
# into it, so "Herm Man 1:1" returns continuous chapter 1 (a Vision).
@pytest.mark.xfail(strict=True, reason="'Herm Man N' isn't offset into the Mandates (start at ch. 26)")
def test_hermas_mandate_1(lookup):
    assert "believe that God is One" in lookup.get_verse("Herm Man 1:1")["text"]


@pytest.mark.xfail(strict=True, reason="'Herm Sim N' isn't offset into the Similitudes (start at ch. 50)")
def test_hermas_similitude_1(lookup):
    assert "dwelling in a foreign land" in lookup.get_verse("Herm Sim 1:1")["text"]


# ANE data is stored as section -> {"1": text}, but _ane_fetch still treats
# each section as a plain string.
@pytest.mark.xfail(strict=True, reason="ANE section lookup returns a dict as 'text'")
@pytest.mark.parametrize("ref", ["Gilgamesh 1:1", "Aten 1", "Baal 1:1", "Muallaqat 1:1"])
def test_ane_section_text_is_str(lookup, ref):
    res = lookup.get_verse(ref)
    assert res["found"] and isinstance(res["text"], str)


@pytest.mark.xfail(strict=True, raises=TypeError, reason="ANE whole-book lookup crashes joining dicts")
@pytest.mark.parametrize("ref", ["Gilgamesh 1", "Aten"])
def test_ane_whole_book(lookup, ref):
    assert lookup.get_verse(ref)["found"]
