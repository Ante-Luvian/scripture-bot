"""
MACULA Greek/Hebrew word-level interlinear data (Clear-Bible/Biblica, Inc.,
CC BY 4.0), built from data/interlinear/macula.db (see
deprecated/build_macula_interlinear.py). Real per-instance transliteration
(Hebrew) and English gloss for every word in the Greek NT (SBLGNT) and
Hebrew OT (WLC) -- a genuine word-aligned interlinear, not one
reconstructed by matching Strong's numbers across independently-tagged
texts.
"""
import sqlite3
from pathlib import Path

_DB_PATH = Path(__file__).parent / "data" / "interlinear" / "macula.db"
_con: sqlite3.Connection | None = None


def _connect() -> sqlite3.Connection | None:
    global _con
    if _con is None and _DB_PATH.exists():
        _con = sqlite3.connect(str(_DB_PATH), check_same_thread=False)
    return _con


def get_verse_words(testament: str, book: str, chapter: int, verse: int) -> list[dict]:
    """testament: 'nt' or 'ot'. Returns a list of
    {"text", "translit", "strong", "gloss"} dicts in reading order, or []
    if this verse isn't in the dataset."""
    con = _connect()
    if con is None:
        return []
    cur = con.cursor()
    cur.execute(
        "SELECT text, translit, strong, gloss FROM words "
        "WHERE testament=? AND book=? AND chapter=? AND verse=? ORDER BY word_order",
        (testament, book, chapter, verse),
    )
    return [{"text": t, "translit": tr, "strong": s, "gloss": g} for t, tr, s, g in cur.fetchall()]


def available() -> bool:
    return _connect() is not None
