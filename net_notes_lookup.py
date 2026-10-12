"""
NET Bible translators' notes for a verse (!notes).

Two sources, combined:
- bolls.life's get-chapter endpoint has the notes themselves (the get-text
  endpoint used for ordinary NET lookups omits them), one <br>-separated
  group per note marker.
- labs.bible.org (the publisher's API) has the verse text with an inline
  <n id="k"/> marker where each note attaches, so the verse can show which
  word each note is about. Markers are only placed when the two sources
  agree on that verse (same number of notes, same text) -- otherwise the
  notes are shown unanchored rather than risk pointing at the wrong word.

The NET's free non-commercial quotation permission covers the Scripture text
only, not the notes. The bot owner chose to show one passage's notes on
request with full credit: every display carries the copyright notice and a
link to the chapter on netbible.org. Keep both.
"""
import difflib
import html as html_mod
import json
import logging
import re
import unicodedata
import urllib.error
import urllib.parse
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
_LABS_URL = "https://labs.bible.org/api/"

# ── fetching ────────────────────────────────────────────────────────────────

_CACHE_SIZE = 200
_chapter_cache: "OrderedDict[tuple[int, int], dict[int, dict]]" = OrderedDict()
_labs_cache: "OrderedDict[tuple[str, int], dict[int, str]]" = OrderedDict()


def _cache_put(cache: OrderedDict, key, value):
    cache[key] = value
    if len(cache) > _CACHE_SIZE:
        cache.popitem(last=False)


def _get_json(url: str):
    """GET + parse JSON, two attempts. None on failure (404 included)."""
    req = urllib.request.Request(url, headers={"User-Agent": "ScriptureBot/1.0"})
    last_err = None
    for _attempt in range(2):
        try:
            with urllib.request.urlopen(req, timeout=_TIMEOUT) as r:
                return json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            last_err = e
        except Exception as e:
            last_err = e
    log.warning(f"NET notes fetch failed for {url}: {last_err}")
    return None


def _fetch_chapter(book_id: int, chapter: int) -> Optional[dict[int, dict]]:
    """bolls.life: {verse_number: {"text", "comment"}} for one NET chapter, or None."""
    key = (book_id, chapter)
    if key in _chapter_cache:
        _chapter_cache.move_to_end(key)
        return _chapter_cache[key]
    data = _get_json(f"{_BASE_URL}/get-chapter/NET/{book_id}/{chapter}/")
    if not isinstance(data, list) or not data:
        return None
    verses = {v["verse"]: {"text": v.get("text") or "", "comment": v.get("comment") or ""}
              for v in data if "verse" in v}
    _cache_put(_chapter_cache, key, verses)
    return verses


def _fetch_labs_chapter(book_name: str, chapter: int) -> Optional[dict[int, str]]:
    """labs.bible.org: {verse_number: raw text with <n id/> markers}, or None."""
    key = (book_name, chapter)
    if key in _labs_cache:
        _labs_cache.move_to_end(key)
        return _labs_cache[key]
    passage = urllib.parse.quote(f"{book_name} {chapter}")
    data = _get_json(f"{_LABS_URL}?passage={passage}&formatting=full&type=json")
    if not isinstance(data, list) or not data:
        return None
    verses = {int(v["verse"]): v.get("text") or "" for v in data
              if str(v.get("chapter")) == str(chapter) and str(v.get("verse", "")).isdigit()}
    _cache_put(_labs_cache, key, verses)
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
# One note marker can carry several notes run together with no <br>, e.g.
# a translator's note then a study note: "...(see Gen 7:11).sn The watery deep."
_NEXT_PART = re.compile(r"(?<=[.)”’\]!?])(?=(?:tn|sn|tc|map) [A-Z“‘(])")
_STRIP_ACCENTS = {"́", "̀", "̂", "͂"}   # keep macrons and diaeresis
# End of a Hebrew run that's followed by left-to-right text: without a
# left-to-right mark there, punctuation after the Hebrew gets pulled into
# the right-to-left run ("(אֱלֹהִים,’elohim )").
_HEBREW_RUN_END = re.compile(r"([֐-׿])(?=\s*[^\s֐-׿])")
_LRM = "‎"


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
    # The source sometimes misplaces spaces around Hebrew -- "(אֱלֹהִים,’elohim )"
    text = re.sub(r"([֐-׿]),(?=\S)", r"\1, ", text)
    text = re.sub(r"\s+\)", ")", text)
    text = _HEBREW_RUN_END.sub(rf"\1{_LRM}", text)
    return re.sub(r"\s+", " ", text).strip()


def split_note_groups(comment: str) -> list[list[tuple[str, str]]]:
    """One group per note marker, each a list of (kind, cleaned_text) parts
    -- usually one, sometimes e.g. a translator's note plus a study note.
    kind is a NOTE_KINDS key, or "" if the part has no recognised prefix."""
    groups = []
    for chunk in re.split(r"<br\s*/?>", comment or ""):
        parts = []
        for raw in _NEXT_PART.split(chunk):
            raw = raw.strip()
            if not raw:
                continue
            m = re.match(r"(tn|sn|tc|map)\s+(.*)", raw, re.S)
            kind, body = (m.group(1), m.group(2)) if m else ("", raw)
            parts.append((kind, clean_note(body, kind)))
        if parts:
            groups.append(parts)
    return groups


def _plain_verse(raw: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", html_mod.unescape(raw))).strip()


_MARKER = "\x00"


def _marked_segments(labs_raw: str) -> list[str]:
    """Verse text split at note markers: n markers -> n+1 segments."""
    text = re.sub(r"<n\b[^>]*/?>", _MARKER, labs_raw)
    return _plain_verse(text).split(_MARKER)


def _anchor_word(segment: str) -> Optional[str]:
    words = re.findall(r"[\w’'-]+", segment)
    return words[-1] if words else None


def _same_text(a: str, b: str) -> bool:
    norm = lambda s: re.sub(r"\W+", " ", s).lower().strip()
    return difflib.SequenceMatcher(None, norm(a), norm(b)).ratio() >= 0.9


# ── lookup ──────────────────────────────────────────────────────────────────

def _err(msg: str) -> dict:
    return {"found": False, "error": msg}


def get_net_notes(reference: str) -> dict:
    """NET text and notes for a verse or short range (up to MAX_VERSES).
    -> {"found", "reference", "url", "verses": [
          {"verse": n, "text": str,
           "segments": [str, ...] | None,   # text split at note markers, if placed
           "notes": [{"anchor": str | None, "parts": [(kind, text), ...]}, ...],
           "marker_count": int}]}           # notes the publisher's text marks (0 if unknown)"""
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
    labs = _fetch_labs_chapter(canon, chapter) or {}   # markers are a bonus; notes work without

    out = []
    for n in range(v1, v2 + 1):
        v = verses.get(n)
        if not v:
            continue
        text = _plain_verse(v["text"])
        groups = split_note_groups(v["comment"])
        segments = _marked_segments(labs[n]) if n in labs else None
        marker_count = len(segments) - 1 if segments else 0
        if not (segments and marker_count == len(groups) and _same_text("".join(segments), text)):
            segments = None
        notes = [{"anchor": _anchor_word(segments[i]) if segments else None, "parts": parts}
                 for i, parts in enumerate(groups)]
        out.append({"verse": n, "text": text, "segments": segments, "notes": notes,
                    "marker_count": marker_count})
    if not out:
        return _err(f"**{canon} {chapter}:{v1}** isn't in the NET.")

    label = f"{v1}" if v1 == v2 else f"{v1}–{v2}"
    return {
        "found": True,
        "reference": f"{canon} {chapter}:{label}",
        "url": f"https://netbible.org/bible/{canon.replace(' ', '+')}+{chapter}",
        "verses": out,
    }
