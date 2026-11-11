"""The five hadith collections from sunnah.com (scripts/fetch_hadith.py), the 📖 Commentary button's tafsir
(scripts/fetch_tafsir.py, bot_commands/tafsir.py) and Ibn Kathir's Stories of the Prophets
(scripts/build_stories_prophets.py). The downloads aren't in git: their checks skip on a fresh clone."""
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
HAVE_HADITH = (ROOT / "data" / "hadith" / "eng-riyad.json").exists()
HAVE_TAFSIR = (ROOT / "data" / "tafsir" / "jalalayn.json").exists()
needs_hadith = pytest.mark.skipif(not HAVE_HADITH, reason="python scripts/fetch_hadith.py --other")
needs_tafsir = pytest.mark.skipif(not HAVE_TAFSIR, reason="python scripts/fetch_tafsir.py")


@needs_hadith
@pytest.mark.parametrize("ref, words", [
    ("Riyad as-Salihin 1", "The deeds are considered by the intentions"),     # (sunnah.com's numbering: the opening
    ("Riyad as-Salihin 680", "modesty is a part of Iman"),                    #  section first, Good Manners at 680)
    ("Riyad 1896", "Have You not made our faces bright?"),
    ("Al-Adab al-Mufrad 1", "Prayer at its proper time"),
    ("Shama'il Muhammadiyah 1", "was neither very tall of stature"),
    ("Bulugh al-Maram 1", "regarding the sea"),
    ("Mishkat al-Masabih 1", "Deeds are to be judged only by intentions"),   # (its introduction, filed last)
])
def test_hadith(lookup, ref, words):
    result = lookup.get_verse(ref)
    assert result.get("found"), ref
    assert words in result["text"], (ref, result["text"][:200])


@needs_hadith
def test_hadith_local_only(lookup):
    import hadith_lookup as h
    # a number past the end says so at once, with no fallback to the CDN (which hasn't these books)
    missing = h.fetch_hadith("riyad", 5000)
    assert not missing["found"] and "1 to 1896" in missing["error"]
    sec = h.get_hadith_section("riyad", 2)
    assert sec["name"] == "The Book of Good Manners" and sec["hadiths"][0][0] == 680
    for key in h.LOCAL_ONLY:
        assert len(h.local_collection(key)) == h.COLLECTION_COUNTS[key], key
    # "Mishkat" alone is still al-Ghazali's Niche for Lights, and "Adam" isn't taken for al-Adab al-Mufrad
    assert lookup.get_verse("Mishkat 2")["reference"].startswith("Niche for Lights")
    assert h.resolve_collection("adam") is None


def test_tafsir_mending():
    from fetch_tafsir import mend
    assert mend("the hypocrites vis-�-vis Muhammad") == "the hypocrites vis-à-vis Muhammad"
    assert mend("who said: �Repentance� (changed") == "who said: “Repentance” (changed"
    assert mend("by the verse: (� a life for a life)") == "by the verse: (… a life for a life)"
    assert mend("(and say not �Three�) a son") == "(and say not “Three”) a son"         # (closes before ")")
    assert mend("(The reckoning draws near for mankind�) [21:1]") == "(The reckoning draws near for mankind…) [21:1]"


def test_tafsir_parse():
    from bot_commands.tafsir import parse
    assert parse("Quran 2:255") == (2, 255, 255)
    assert parse("Quran 2:1–5") == (2, 1, 5)
    assert parse("Quran 112") == (112, 1, None)
    assert parse("Quran 115:1") is None and parse("Genesis 1:1") is None


@needs_tafsir
def test_commentary_button():
    from bot_commands.tafsir import CommentaryButton, commentary_buttons, entries, pages_of
    buttons = commentary_buttons({"found": True, "reference": "Quran 2:255"})
    assert len(buttons) == 1 and isinstance(buttons[0], CommentaryButton)
    assert commentary_buttons({"found": True, "reference": "Genesis 1:1"}) == []
    assert commentary_buttons({"found": True, "reference": "Quran 2:999"}) == []
    # Ibn Kathir's one commentary on 112:1-4 comes once, labelled with the verses it covers
    assert [label for label, _ in entries("ibnkathir", 112, 1, None)] == ["112:1–4"]
    assert entries("jalalayn", 2, 255, 255)[0][1].startswith("God, there is no god")
    for key in ("jalalayn", "ibnkathir", "ibnabbas"):
        for page in pages_of(key, 2, 1, 20):
            assert len(page) <= 4096 and "`" not in page and "�" not in page


@pytest.mark.parametrize("ref, words", [
    ("Stories of the Prophets 1:1", "*Prophet Adam*\n*Informing the Angels About Adam*\nAllah the Almighty revealed:"),
    ("Stories of the Prophets 3:1", "*Prophet Nuh (Noah)*"),                  # (its heading in a smaller type)
    ("Qisas al-Anbiya 12:75", "bl[ood] flowed without their feeling pain"),   # (letters the PDF lost)
    ("Stories of the Prophets 29:1", "*Prophet Muhammad*"),
])
def test_stories(lookup, ref, words):
    result = lookup.get_verse(ref)
    assert result.get("found"), ref
    assert words in result["text"], (ref, result["text"][:200])


def test_stories_clean(lookup):
    book = lookup._data["quran"]["Stories of the Prophets"]
    assert list(book) == [str(n) for n in range(1, 30)]
    for ch, verses in book.items():
        for text in verses.values():
            assert not re.search(r"islambas|disbeliveers|\bfourty\b|postrate|  ", text), (ch, text[:100])
            assert text.count("*") % 2 == 0 and len(text) < 2000, (ch, text[:100])
