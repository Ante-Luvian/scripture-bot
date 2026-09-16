"""
Nave's Topical Bible lookup (Orville J. Nave, public domain), built from
data/topics/naves_topical.json (see deprecated/build_topics.py for how that
file was generated). A browsable outline per subject with embedded scripture
citations -- displayed as-is, not mined for individual verse links.
"""
import json
from pathlib import Path

_DATA_PATH = Path(__file__).parent / "data" / "topics" / "naves_topical.json"
_data: dict | None = None


def _load() -> dict:
    global _data
    if _data is None:
        if _DATA_PATH.exists():
            _data = json.loads(_DATA_PATH.read_text(encoding="utf-8"))
        else:
            _data = {}
    return _data


def get_topic(name: str) -> tuple[str, str] | None:
    """Case-insensitive exact match. Returns (canonical_subject, entry_text) or None."""
    data = _load()
    key = name.strip().upper()
    if key in data:
        return key, data[key]
    return None


def search_topics(query: str, limit: int = 15) -> list[str]:
    """Subject names containing query (case-insensitive), shortest first."""
    q = query.strip().upper()
    if not q:
        return []
    matches = [s for s in _load() if q in s]
    matches.sort(key=len)
    return matches[:limit]


def topic_count() -> int:
    return len(_load())
