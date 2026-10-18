"""Mishnah tractate names (resolution only -- fetching goes to Sefaria)."""
import pytest

from sefaria_lookup import resolve_tractate


@pytest.mark.parametrize("raw, index", [
    ("berakhot", "Mishnah_Berakhot"),
    ("Mishnah Berakhot", "Mishnah_Berakhot"),   # the form results are labelled with
    ("mishna shabbat", "Mishnah_Shabbat"),
    ("m. berakhot", "Mishnah_Berakhot"),
    ("M Avot", "Mishnah_Avot"),
    ("pirkei avot", "Mishnah_Avot"),
])
def test_resolve_tractate(raw, index):
    assert resolve_tractate(raw) == index


@pytest.mark.parametrize("raw", ["matthew", "mark"])
def test_bible_books_are_not_tractates(raw):
    # (resolve_tractate is fuzzy -- "micah" matches Meilah -- but it's only
    # consulted after a name fails to resolve as a Bible book, so Micah is safe.)
    assert resolve_tractate(raw) is None


def test_anything_else_in_sefarias_library(lookup, monkeypatch):
    import sefaria_lookup
    asked = []
    monkeypatch.setattr(sefaria_lookup, "sefaria_name",
                        lambda q: asked.append(q) or ("Kuzari.1.1" if "Kuzari" in q else None))
    monkeypatch.setattr(sefaria_lookup, "fetch_sefaria_generic", lambda tref: {
        "found": True, "reference": "Kuzari 1:1", "text": "I was asked...", "source": "Hirschfeld (via Sefaria)"})
    r = lookup.get_verse("Kuzari 1:1")
    assert r["found"] and r["reference"] == "Kuzari 1:1" and asked == ["Kuzari 1:1"]
    assert "Unknown book" in lookup.get_verse("Hezzz 1:1")["error"]             # not in Sefaria either
    assert lookup.get_verse("John 3:16")["found"] and len(asked) == 2             # local books never ask


def test_sefaria_text_with_no_english_says_so(lookup, monkeypatch):
    import sefaria_lookup
    monkeypatch.setattr(sefaria_lookup, "sefaria_name", lambda q: "Some_Hebrew_Only_Book.1")
    monkeypatch.setattr(sefaria_lookup, "fetch_sefaria_generic", lambda tref: {
        "found": False, "error": "No English translation found for Some Hebrew Only Book.1.", "suggestions": []})
    assert "No English translation" in lookup.get_verse("Some Hebrew Only Book 1")["error"]


@pytest.mark.live
def test_sefaria_library_live():
    import sefaria_lookup
    r = sefaria_lookup.fetch_sefaria_any("Kuzari 1:1")
    assert r["found"] and r["text"]
    assert sefaria_lookup.fetch_sefaria_any("Hezzzz 1:1") is None
