"""
James Ussher's Annals of the World (1658, public domain) chronology lookup,
built from data/timeline/ussher_timeline.json (see
deprecated/build_timeline.py). 1,288 dated entries, 4004 BC - 73 AD.
"""
import json
from pathlib import Path

_DATA_PATH = Path(__file__).parent / "data" / "timeline" / "ussher_timeline.json"
_entries: list[dict] | None = None


def _load() -> list[dict]:
    global _entries
    if _entries is None:
        if _DATA_PATH.exists():
            _entries = json.loads(_DATA_PATH.read_text(encoding="utf-8")).get("entries", [])
        else:
            _entries = []
    return _entries


def search_timeline(query: str, context: int = 1) -> list[dict] | None:
    """Case-insensitive substring search over event text (matches a book
    citation like 'Ge 12' or a keyword like 'Abraham' or 'flood').
    Returns the best match plus `context` entries on either side of it (in
    chronological order), or None if nothing matches."""
    q = query.strip().lower()
    if not q:
        return None
    data = _load()
    for i, e in enumerate(data):
        if q in e["text"].lower():
            lo = max(0, i - context)
            hi = min(len(data), i + context + 1)
            window = data[lo:hi]
            for w in window:
                w["_matched"] = w is e
            return window
    return None


def entry_count() -> int:
    return len(_load())


def year_range() -> tuple[str, str]:
    data = _load()
    if not data:
        return ("", "")
    return (data[0]["year_display"], data[-1]["year_display"])
