"""
Local Strong's Hebrew/Greek dictionary (OpenScriptures, CC-BY-SA, derived
from James Strong's public-domain 1890/1894 original), built from
data/strongs/strongs_dictionary.json (see deprecated/build_strongs.py).
"""
import json
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
