"""
Easton's (1897) + Smith's (1863) Bible Dictionary lookup, both public
domain, built from data/dictionary/bible_dictionary.json (see
deprecated/build_bible_dictionary.py).
"""
import json
from pathlib import Path

_DATA_PATH = Path(__file__).parent / "data" / "dictionary" / "bible_dictionary.json"
_data: dict | None = None

SOURCE_NAMES = {
    "EAS": "Easton's Bible Dictionary (1897)",
    "SMI": "Smith's Bible Dictionary (1863)",
}


def _load() -> dict:
    global _data
    if _data is None:
        if _DATA_PATH.exists():
            _data = json.loads(_DATA_PATH.read_text(encoding="utf-8")).get("entries", {})
        else:
            _data = {}
    return _data


def get_definition(term: str) -> dict | None:
    """Case-insensitive exact match on the term name.
    Returns the entry dict ({name, slug, definitions, scripture_refs}) or None."""
    return _load().get(term.strip().upper())


def search_terms(query: str, limit: int = 15) -> list[str]:
    """Term names containing query (case-insensitive), shortest first.
    Returns display names (not the uppercase index keys)."""
    q = query.strip().upper()
    if not q:
        return []
    data = _load()
    matches = [key for key in data if q in key]
    matches.sort(key=len)
    return [data[key]["name"] for key in matches[:limit]]


def entry_count() -> int:
    return len(_load())
