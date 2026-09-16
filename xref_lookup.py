"""
Cross-reference lookup: Treasury of Scripture Knowledge dataset via
openbible.info (https://www.openbible.info/labs/cross-references/, CC-BY),
built from data/cross_references/cross_references.json (see
deprecated/build_cross_references.py for how that file was generated).
"""
import json
from pathlib import Path

_DATA_PATH = Path(__file__).parent / "data" / "cross_references" / "cross_references.json"
_data: dict | None = None


def _load() -> dict:
    global _data
    if _data is None:
        if _DATA_PATH.exists():
            _data = json.loads(_DATA_PATH.read_text(encoding="utf-8"))
        else:
            _data = {}
    return _data


def get_cross_references(reference: str) -> list[tuple[str, int]]:
    """reference: canonical "Book Chapter:Verse" string (single verse only --
    the source dataset doesn't key on verse ranges).
    Returns [(to_reference, votes), ...] sorted by votes descending, or []
    if this verse has no entries."""
    entries = _load().get(reference, [])
    return [(ref, votes) for ref, votes in entries]
