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
