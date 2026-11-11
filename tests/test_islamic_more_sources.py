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


@needs_tafsir
def test_commentary_reply_is_public_and_steps_verse_to_verse(bot_module):
    """(2026-11-11) The owner: the commentary should be seen by everyone, and ◀ ▶ "don't do anything" (they were
    page arrows, greyed out on a one-page commentary). Now the page arrows show only when there are pages to turn,
    and buttons go to the verse before and after; every control is persistent."""
    import asyncio
    import types
    from bot_commands import tafsir
    message = tafsir.reply("ibnabbas", 58, 21, 21)
    labels = [getattr(getattr(c, "item", c), "label", None) for c in message["view"].children]
    assert "◀ Page" not in labels and "◀ 58:20" in labels and "58:22 ▶" in labels
    assert all(c.item.custom_id for c in message["view"].children)
    ids = [c.item.custom_id for c in message["view"].children]
    assert len(ids) == len(set(ids))
    assert "58:23 ▶" not in [getattr(c.item, "label", None) for c in tafsir.reply("ibnabbas", 58, 22, 22)["view"].children]
    long = tafsir.reply("ibnkathir", 2, 1, 20)
    assert "Page ▶" in [getattr(c.item, "label", None) for c in long["view"].children]
    edits, sent = [], []

    class Response:
        async def edit_message(self, **kw): edits.append(kw)
        async def send_message(self, *a, **kw): sent.append(kw)
    nxt = next(c.item for c in message["view"].children if getattr(c.item, "label", None) == "58:22 ▶")
    item = asyncio.run(tafsir.CommentaryNav.from_custom_id(
        None, None, tafsir.CommentaryNav.__discord_ui_compiled_template__.fullmatch(nxt.custom_id)))
    asyncio.run(item.callback(types.SimpleNamespace(response=Response())))
    assert "58:22" in edits[-1]["embed"].title
    button = tafsir.CommentaryButton("Quran 2:255")
    asyncio.run(button.callback(types.SimpleNamespace(response=Response())))
    assert sent and not sent[-1].get("ephemeral")
    menu = asyncio.run(tafsir.CommentaryMenu.from_custom_id(
        None, None, tafsir.CommentaryMenu.__discord_ui_compiled_template__.fullmatch("tafk:2:255:255")))
    asyncio.run(menu.callback(types.SimpleNamespace(response=Response(), data={"values": ["ibnkathir"]})))
    assert "Ibn Kathir" in edits[-1]["embed"].title


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


@pytest.mark.parametrize("ref, words", [
    ("Sirat Rasul Allah 1:1", "*His Ancestry and Early Life*\nIt is recorded that when the mother of the apostle"),
    ("Sira 1:3", "on the thirteenth day of the month of Rabi in the year of the Elephant [c. 570]."),   # (slips)
    ("Ibn Ishaq 3:1", "*The Revelation*\nAs the time approached"),               # (not its heading in capitals)
    ("Sira 13:1", "*Badr*\nWhen the apostle of Allah arrived near Badr"),
    ("Life of Muhammad 26:29", "Then Allah roused them again under Abu Bakr."),
])
def test_sira(lookup, ref, words):
    result = lookup.get_verse(ref)
    assert result.get("found"), ref
    assert words in result["text"], (ref, result["text"][:200])
    assert "Rehatsek" in result["source"]


def test_sira_clean(lookup):
    book = lookup._data["quran"]["Sirat Rasul Allah"]
    assert list(book) == [str(n) for n in range(1, 27)]
    text = " ".join(t for vs in book.values() for t in vs.values())
    # Edwardes's introduction and footnotes are not Ibn Ishaq's
    assert "accretion of myth" not in text and "The year of an invasion by the Abyssinians" not in text
    assert not re.search(r"\b[A-Z]{4,} [A-Z]{2,}|­|  |<|>|religlion|punnish", text)
    assert text.count("*") % 2 == 0


def test_stories_clean(lookup):
    book = lookup._data["quran"]["Stories of the Prophets"]
    assert list(book) == [str(n) for n in range(1, 30)]
    for ch, verses in book.items():
        for text in verses.values():
            assert not re.search(r"islambas|disbeliveers|\bfourty\b|postrate|  ", text), (ch, text[:100])
            assert text.count("*") % 2 == 0 and len(text) < 2000, (ch, text[:100])


@pytest.mark.skipif(not (ROOT / "data" / "tafsir" / "wahidi.json").exists(), reason="python scripts/fetch_tafsir.py --altafsir")
def test_wahidi_and_tustari(bot_module):
    """(2026-11-11) From altafsir.com itself: al-Wahidi's occasions of revelation, only for the verses it has a story
    for, each kept once over the verses it covers; al-Tustari's Sufi commentary."""
    from bot_commands import tafsir
    assert {"wahidi", "tustari"} <= set(tafsir.available())
    assert [label for label, _ in tafsir.entries("wahidi", 2, 1, 6)] == ["2:1–2", "2:6"]
    assert "Abu Jahl" in tafsir.entries("wahidi", 2, 6, 6)[0][1]
    assert tafsir.entries("tustari", 2, 255, 255)[0][1].startswith("God, There is no god except Him")
    for key in ("wahidi", "tustari"):
        text = str(tafsir.tafsir(key))
        assert "\ufffd" not in text and "<script" not in text and "http" not in text


@pytest.mark.skipif(not (ROOT / "data" / "tafsir" / "kashani.json").exists(), reason="python scripts/fetch_tafsir.py --altafsir")
def test_kashani_whole_and_paged_commentaries(bot_module):
    """(2026-11-11) altafsir.com splits a long commentary into pages of ~2,300 characters: all of them are kept.
    Kashani's 1:1 runs to three; al-Wahidi's 2:115 to two (it was cut at the first)."""
    from bot_commands import tafsir
    assert "kashani" in tafsir.available()
    basmala = tafsir.entries("kashani", 1, 1, 1)[0][1]
    assert basmala.startswith("In the Name of God: the name of a thing") and "I seek refuge in You from You" in basmala
    assert "the Negus died" in tafsir.entries("wahidi", 2, 115, 115)[0][1]
    text = str(tafsir.tafsir("kashani"))
    assert "\ufffd" not in text and "<script" not in text and "http" not in text
    assert "\u00cc" not in text and "Qur\u02be\u0101n" in text                    # (the site's hamza, put right)
    # Hamza's English Kashani stops at surah 18: past it, the menu says so rather than "nothing on these verses"
    embed = tafsir.embed_for("kashani", "Quran 19:1", [], 0)
    assert "goes only as far as surah 18" in embed.description
