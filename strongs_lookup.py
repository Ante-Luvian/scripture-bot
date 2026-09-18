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


_DERIV_REF = re.compile(r"\b([GH]\d+[a-z]?)\b")
_PRIMITIVE_RE = re.compile(r"primitive (?:root|word)", re.IGNORECASE)


def find_root(number: str, max_hops: int = 8) -> str:
    """Follow a Strong's entry's `derivation` field back to its root: the
    entry marked "a primitive root/word", or the last entry reachable
    before the chain stops referencing another number. Returns `number`
    itself if it has no entry or no derivation reference."""
    number = number.strip().upper()
    seen = {number}
    current = number
    for _ in range(max_hops):
        entry = _load().get(current)
        if not entry:
            return current
        deriv = entry.get("derivation") or ""
        if _PRIMITIVE_RE.search(deriv):
            return current
        # Only follow the primary derivation ("from/of H123"), not a
        # "(compare H456)" aside pointing to a merely related word --
        # those aren't ancestry and can point at withdrawn/nonexistent
        # numbers (e.g. G25's "(or compare G5689)", where G5689 doesn't
        # exist in this dataset at all).
        primary_part = re.split(r"compare", deriv, maxsplit=1, flags=re.IGNORECASE)[0]
        m = _DERIV_REF.search(primary_part)
        if not m or m.group(1).upper() == current:
            return current
        nxt = m.group(1).upper()
        if nxt in seen:
            return current  # cycle guard
        seen.add(nxt)
        current = nxt
    return current


def get_root_family(number: str) -> tuple[str, list[str]]:
    """(root_number, [direct-derivative numbers]) for the Strong's number's
    root word -- every entry whose `derivation` field cites the root
    directly (one level, not the full multi-generation cognate tree)."""
    root = find_root(number)
    family = []
    for num, entry in _load().items():
        if num == root:
            continue
        deriv = entry.get("derivation") or ""
        if re.search(rf"\b{re.escape(root)}\b", deriv):
            family.append(num)
    return root, family


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
