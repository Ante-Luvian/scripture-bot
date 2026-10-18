"""The Quran in every English translation of the Quran API; Abdel Haleem by default."""
import pytest

import quran_lookup as ql

FAKE = {("eng-abdelhaleem", 1): ["In the name of God, the Lord of Mercy, the Giver of Mercy!", "Praise belongs to God,"],
        ("eng-ajarberry", 1): ["In the Name of God, the Merciful, the Compassionate", "Praise belongs to God, the Lord"]}


@pytest.fixture
def api(monkeypatch):
    monkeypatch.setattr(ql, "fetch_surah", lambda edition, surah: FAKE.get((edition, surah)))


@pytest.mark.parametrize("ref, parsed", [
    ("Quran 2:255", (2, 255, 255, ["haleem"])), ("Surah 2:255-257 arberry asad", (2, 255, 257, ["arberry", "asad"])),
    ("Qur'an 112", (112, None, None, ["haleem"])), ("koran 1:1 Pickthall", (1, 1, 1, ["pickthall"])),
    ("Quran 1:1 saheeh study", (1, 1, 1, ["sahih", "studyquran"])),
    ("Quran 115:1", None), ("John 3:16", None), ("Quran 2:5-3", None),
])
def test_parse(ref, parsed):
    assert ql.parse(ref) == parsed


def test_default_is_haleem(lookup, api):
    r = lookup.get_verse("Quran 1:1")
    assert r["text"].startswith("In the name of God, the Lord of Mercy") and "Haleem" in r["source"]


def test_side_by_side_and_pickthall(lookup, api):
    r = lookup.get_verse("Quran 1:1-2 haleem arberry pickthall")
    assert r["reference"] == "Quran 1:1–2"
    assert "__M.A.S. Abdel Haleem (Oxford, 2004)__" in r["text"] and "__A. J. Arberry" in r["text"]
    assert "**[2]** Praise belongs to God, the Lord" in r["text"] and "__Marmaduke Pickthall" in r["text"]


def test_offline_falls_back_to_pickthall(lookup):
    r = lookup.get_verse("Quran 2:255")                  # (conftest: the API can't be reached)
    assert r["found"] and "Pickthall" in r["source"]


def test_tidy():
    assert ql._tidy("the Ever Watchful.Neither slumber") == "the Ever Watchful. Neither slumber"
    assert ql._tidy("U.S.A") == "U.S.A"


def test_no_clash_with_bible_translations():
    from scripture_lookup import DRB_SUFFIXES, KNOX_SUFFIXES
    from translation_lookup import TRANSLATION_SUFFIXES
    names = set(ql.EDITIONS) | set(ql.ALIASES)
    assert not names & (TRANSLATION_SUFFIXES | DRB_SUFFIXES | KNOX_SUFFIXES)
    assert all(ql.slug(a) for a in ql.ALIASES)


@pytest.mark.live
def test_every_translation_is_live():
    for name, (edition, _) in ql.EDITIONS.items():
        verses = ql.fetch_surah(edition, 112)
        assert verses and len(verses) == 4 and all(verses), name
