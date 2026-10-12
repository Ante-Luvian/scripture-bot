"""
NET Bible translators' notes for a verse (!notes), from bolls.life's
get-chapter endpoint -- the get-text endpoint used for ordinary NET lookups
omits the notes.

The NET's free non-commercial quotation permission covers the Scripture text
only, not the notes. The bot owner chose to show one passage's notes on
request with full credit: every display carries the copyright notice and a
link to the chapter on netbible.org. Keep both.
"""
import html as html_mod
import json
import logging
import re
import unicodedata
import urllib.error
import urllib.request
from collections import OrderedDict
from typing import Optional

from greek_translit import _transliterate_greek
from translation_lookup import _BASE_URL, _TIMEOUT, _get_canon_name, _get_trans_book_id

log = logging.getLogger(__name__)

NOTE_KINDS = {
    "tn": "Translator's note",
    "sn": "Study note",
    "tc": "Text-critical note",
    "map": "Map note",
}
NET_COPYRIGHT = ("NET Bible® text and notes copyright ©1996, 2019 by Biblical Studies "
                 "Press, L.L.C. All rights reserved. netbible.com")
MAX_VERSES = 5

# ── fetching ────────────────────────────────────────────────────────────────

_CACHE_SIZE = 200
_chapter_cache: "OrderedDict[tuple[int, int], dict[int, dict]]" = OrderedDict()


def _fetch_chapter(book_id: int, chapter: int) -> Optional[dict[int, dict]]:
    """{verse_number: {"text", "comment"}} for one NET chapter, or None."""
    key = (book_id, chapter)
    if key in _chapter_cache:
        _chapter_cache.move_to_end(key)
        return _chapter_cache[key]
    url = f"{_BASE_URL}/get-chapter/NET/{book_id}/{chapter}/"
    req = urllib.request.Request(url, headers={"User-Agent": "ScriptureBot/1.0"})
    last_err = None
    for _attempt in range(2):
        try:
            with urllib.request.urlopen(req, timeout=_TIMEOUT) as r:
                data = json.loads(r.read().decode("utf-8"))
            break
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            last_err = e
        except Exception as e:
            last_err = e
    else:
        log.warning(f"NET notes fetch failed for {book_id}/{chapter}: {last_err}")
        return None
    if not isinstance(data, list) or not data:
        return None
    verses = {v["verse"]: {"text": v.get("text") or "", "comment": v.get("comment") or ""}
              for v in data if "verse" in v}
    _chapter_cache[key] = verses
    if len(_chapter_cache) > _CACHE_SIZE:
        _chapter_cache.popitem(last=False)
    return verses


# ── cleaning ────────────────────────────────────────────────────────────────

_GREEK = r"[Ͱ-Ͽἀ-῿]"
# A Greek word or phrase, then its transliteration in the legacy Greek-font
# encoding (J = rough breathing, w = omega, q = theta, h = eta, c = chi,
# " = final sigma, ...), either in parentheses -- "οὕτως (Joutws)" -- or after
# a comma inside them -- "(τέκνα θεοῦ, tekna qeou)".
_GREEK_THEN_TRANSLIT = re.compile(
    rf"(?P<greek>{_GREEK}(?:(?:{_GREEK}|[ ’'·+])*{_GREEK})?)(?P<sep>\s*\(|,\s+)"
    rf"(?P<latin>[A-Za-z'\"][A-Za-z'\" +-]*?)(?=[,)])"
)
# Manuscript sigla the legacy font encodes as Latin-1 letters (text-critical notes).
_SIGLA = {"Ì": "𝔓", "Ï": "𝔐", "Ë": "f"}
# Two notes sometimes run together with no <br>: "...(see Gen 7:11).sn The watery deep."
_RUN_TOGETHER = re.compile(r"(?<=[.)”’\]!?])(?=(?:tn|sn|tc|map) [A-Z“‘(])")
_STRIP_ACCENTS = {"́", "̀", "̂", "͂"}   # keep macrons and diaeresis


def _plain_translit(greek: str) -> str:
    """NET-style transliteration: macrons for long vowels, no accent marks."""
    t = unicodedata.normalize("NFD", _transliterate_greek(greek))
    return unicodedata.normalize("NFC", "".join(c for c in t if c not in _STRIP_ACCENTS))


def _fix_translit(match: re.Match) -> str:
    greek, sep, latin = match.group("greek"), match.group("sep"), match.group("latin")
    if len(greek.split()) != len(latin.split()):
        return match.group(0)   # not a one-to-one transliteration; leave it alone
    return f"{greek}{sep}{_plain_translit(greek)}"


def clean_note(body: str, kind: str = "") -> str:
    text = re.sub(r"<a\b[^>]*>(.*?)</a>", r"\1", body, flags=re.S)   # keep link text
    text = re.sub(r"<[^>]+>", "", text)
    text = html_mod.unescape(text)
    if kind == "tc":
        for legacy, real in _SIGLA.items():
            text = text.replace(legacy, real)
    text = text.replace("ÿ", "ᵉ")   # legacy Hebrew vocal shewa: tÿhom -> tᵉhom
    text = _GREEK_THEN_TRANSLIT.sub(_fix_translit, text)
    return re.sub(r"\s+", " ", text).strip()


def split_notes(comment: str) -> list[tuple[str, str]]:
    """[(kind, cleaned_text)] for one verse's raw bolls `comment` field.
    kind is a NOTE_KINDS key, or "" if the note has no recognised prefix."""
    notes = []
    pieces = [p for chunk in re.split(r"<br\s*/?>", comment or "") for p in _RUN_TOGETHER.split(chunk)]
    for raw in pieces:
        raw = raw.strip()
        if not raw:
            continue
        m = re.match(r"(tn|sn|tc|map)\s+(.*)", raw, re.S)
        kind, body = (m.group(1), m.group(2)) if m else ("", raw)
        notes.append((kind, clean_note(body, kind)))
    return notes


# ── lookup ──────────────────────────────────────────────────────────────────

def _err(msg: str) -> dict:
    return {"found": False, "error": msg}


def get_net_notes(reference: str) -> dict:
    """NET text and notes for a verse or short range (up to MAX_VERSES).
    -> {"found", "reference", "url", "verses": [(n, text, [(kind, note)])]}"""
    m = re.match(r"^(.*?)\s+(\d+)[:.](\d+)(?:\s*[-–—]\s*(\d+))?$", reference.strip())
    if not m:
        return _err(f"Give a verse, e.g. `!notes John 3:16` or `!notes Genesis 1:1-3` "
                    f"(up to {MAX_VERSES} verses).")
    book_raw, chapter = m.group(1).strip(), int(m.group(2))
    v1 = int(m.group(3))
    v2 = int(m.group(4)) if m.group(4) else v1
    if v2 < v1:
        return _err(f"Verse range **{v1}–{v2}** runs backwards.")
    if v2 - v1 + 1 > MAX_VERSES:
        return _err(f"That's {v2 - v1 + 1} verses; `!notes` shows up to {MAX_VERSES} at a time.")

    book_id = _get_trans_book_id("NET", book_raw)
    if not book_id:
        return _err(f"The NET doesn't have a book called **{book_raw}**.")
    canon = _get_canon_name("NET", book_id, book_raw.title())

    verses = _fetch_chapter(book_id, chapter)
    if verses is None:
        return _err(f"Couldn't retrieve **{canon} {chapter}** from the NET right now. Try again shortly.")

    out = []
    for n in range(v1, v2 + 1):
        v = verses.get(n)
        if v:
            text = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", html_mod.unescape(v["text"]))).strip()
            out.append((n, text, split_notes(v["comment"])))
    if not out:
        return _err(f"**{canon} {chapter}:{v1}** isn't in the NET.")

    label = f"{v1}" if v1 == v2 else f"{v1}–{v2}"
    return {
        "found": True,
        "reference": f"{canon} {chapter}:{label}",
        "url": f"https://netbible.org/bible/{canon.replace(' ', '+')}+{chapter}",
        "verses": out,
    }
