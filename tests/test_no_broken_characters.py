"""No data file holds U+FFFD, the mark a page read in the wrong encoding leaves in place of each curly quote, dash
or accented letter ("Aphr�don" for Aphrêdon), nor a soft hyphen (invisible, but it breaks searching). In
2026-11 Philo, Ephrem, Cyril, the Zadokite Fragments and others were found with 566 between them."""
import pathlib

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
FILES = sorted(p for p in (ROOT / "data").rglob("*.json") if p.stat().st_size < 60_000_000)


@pytest.mark.parametrize("path", FILES, ids=lambda p: str(p.relative_to(ROOT / "data")))
def test_no_broken_characters(path):
    text = path.read_text(encoding="utf-8", errors="strict")
    assert "�" not in text, f"{text.count(chr(0xFFFD))} replacement characters"
    assert "\xad" not in text, f"{text.count(chr(0xAD))} soft hyphens"
