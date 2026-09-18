"""
Local Strong's Hebrew/Greek dictionary (OpenScriptures, CC-BY-SA, derived
from James Strong's public-domain 1890/1894 original), built from
data/strongs/strongs_dictionary.json (see deprecated/build_strongs.py).
"""
import json
import re
import unicodedata
from pathlib import Path

_DATA_PATH = Path(__file__).parent / "data" / "strongs" / "strongs_dictionary.json"
_data: dict | None = None


def _load() -> dict:
    global _data
    if _data is None:
        if _DATA_PATH.exists():
            _data = json.loads(_DATA_PATH.read_text(encoding="utf-8"))
        else:
            _data = {}
    return _data


def get_definition(number: str) -> dict | None:
    """number like 'G26' or 'H430'. Returns a dict with keys lexeme,
    transliteration, pronunciation, short_definition, definition, derivation
    -- or None if this number isn't in the local dictionary."""
    return _load().get(number.strip().upper())


def entry_count() -> int:
    return len(_load())


def _strip_accents(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s) if not unicodedata.combining(c))


def search_by_word(query: str, testament: str = "") -> list[str]:
    """Find Strong's numbers whose lexeme, transliteration, or short
    definition matches `query` (case-insensitive, accent-insensitive
    substring match -- so "agape" matches a dictionary transliteration of
    "agápē"). testament: "" (both), "G" (Greek only), "H" (Hebrew only).
    Returns numbers ranked with exact/word-boundary short_definition
    matches first, substring matches after."""
    q = _strip_accents(query.strip().lower())
    if not q:
        return []
    exact, partial = [], []
    for num, entry in _load().items():
        if testament and not num.startswith(testament.upper()):
            continue
        translit = _strip_accents((entry.get("transliteration") or "").lower())
        short_def = (entry.get("short_definition") or "").lower()
        lexeme_ascii = _strip_accents((entry.get("lexeme") or "").lower())
        words = re.split(r"[^a-z]+", short_def)
        if q == translit or q in words:
            exact.append(num)
        elif q in translit or q in short_def or q in lexeme_ascii:
            partial.append(num)
    return exact + partial
