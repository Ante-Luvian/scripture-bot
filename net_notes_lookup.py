"""
NET Bible translators' notes for a verse (!notes).

Primary source: netbible.org's own reader endpoints, which serve the current
NET edition with verse text, note markers, and notes all from one place:
  /resource/netTexts/<Book Ch>?bible1Translation=net_strongs2   (JSON; "bible1" is the text HTML)
  /resource/netNotes/<Book Ch>?bible1Translation=net_strongs2   (notes HTML)
Each marker in the text carries its chapter-wide note number and verse; the
notes HTML has one <div class="note"> per number (an unnumbered div continues
the note before it, e.g. a study note after a translator's note). These
endpoints are undocumented -- the site's reader uses them -- and fail (HTTP
500) without the bible1Translation parameter. Requests are cached per chapter.

Backup: if netbible.org is unreachable, the notes come from bolls.life's
get-chapter endpoint instead, without positions (bolls has no markers, and
has gaps -- e.g. Psalm 23:1-4).

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
import urllib.parse
import urllib.request
from collections import OrderedDict
from html.parser import HTMLParser
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
_NETBIBLE = "https://netbible.org/resource"
_NETBIBLE_QUERY = "?bible1Translation=net_strongs2"

# ── fetching ────────────────────────────────────────────────────────────────

_CACHE_SIZE = 200
_caches: dict[str, "OrderedDict"] = {"netbible": OrderedDict(), "bolls": OrderedDict()}


def _cached(kind: str, key, fetch):
    cache = _caches[kind]
    if key in cache:
        cache.move_to_end(key)
        return cache[key]
    value = fetch()
    if value is not None:
        cache[key] = value
        if len(cache) > _CACHE_SIZE:
            cache.popitem(last=False)
    return value


def _get(url: str) -> Optional[str]:
    """GET as text, two attempts. None on failure."""
    req = urllib.request.Request(url, headers={"User-Agent": "ScriptureBot/1.0 (Discord bot)"})
    last_err = None
    for _attempt in range(2):
        try:
            with urllib.request.urlopen(req, timeout=_TIMEOUT) as r:
                return r.read().decode("utf-8")
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            last_err = e
        except Exception as e:
            last_err = e
    log.warning(f"NET notes fetch failed for {url}: {last_err}")
    return None


def _fetch_netbible(book: str, chapter: int) -> Optional[tuple[str, str]]:
    """(text_html, notes_html) for one chapter from netbible.org, or None."""
    def fetch():
        ref = urllib.parse.quote(f"{book} {chapter}")
        texts = _get(f"{_NETBIBLE}/netTexts/{ref}{_NETBIBLE_QUERY}")
        notes = _get(f"{_NETBIBLE}/netNotes/{ref}{_NETBIBLE_QUERY}")
        try:
            text_html = json.loads(texts)["bible1"] if texts else None
        except (ValueError, KeyError, TypeError):
            text_html = None
        if not text_html or "netVerse" not in text_html or notes is None:
            return None
        return text_html, notes
    return _cached("netbible", (book, chapter), fetch)


def _fetch_bolls_chapter(book_id: int, chapter: int) -> Optional[dict[int, dict]]:
    """bolls.life backup: {verse_number: {"text", "comment"}}, or None."""
    def fetch():
        raw = _get(f"{_BASE_URL}/get-chapter/NET/{book_id}/{chapter}/")
        try:
            data = json.loads(raw) if raw else None
        except ValueError:
            return None
        if not isinstance(data, list) or not data:
            return None
        return {v["verse"]: {"text": v.get("text") or "", "comment": v.get("comment") or ""}
                for v in data if "verse" in v}
    return _cached("bolls", (book_id, chapter), fetch)


# ── netbible.org markup -> Discord text ─────────────────────────────────────

_SUPERSCRIPT = str.maketrans("0123456789,+-()", "⁰¹²³⁴⁵⁶⁷⁸⁹˒⁺⁻⁽⁾")
# span.uncial holds Greek capitals in a legacy font: "qMs" = ΘΣ with the
# nomina sacra overline (M).
_UNCIAL = dict(zip("abgdezhqiklmnxoprstufcyw", "ΑΒΓΔΕΖΗΘΙΚΛΜΝΞΟΠΡΣΤΥΦΧΨΩ"))
_APPARATUS = {"M": "𝔐", "P": "𝔓"}   # Majority text, papyri
_MARKDOWN = re.compile(r"([*_~`|\\])")


def _uncial(s: str) -> str:
    overline = "M" in s
    letters = [_UNCIAL.get(c, c) for c in s.replace("M", "")]
    return "".join(c + "̅" for c in letters) if overline else "".join(letters)


class _NoteHTML(HTMLParser):
    """One note's HTML -> Discord markdown: italics kept, literal markdown
    characters escaped (tc notes have sigla like "א*"), superscripts and
    apparatus sigla rendered as Unicode."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.out, self.stack = [], []

    def handle_starttag(self, tag, attrs):
        cls = dict(attrs).get("class", "") or ""
        self.stack.append((tag, cls))
        if tag == "i":
            self.out.append("*")
        elif tag in ("p", "br") and self.out:
            self.out.append("\n")

    def handle_endtag(self, tag):
        while self.stack:
            t, _ = self.stack.pop()
            if t == tag:
                break
        if tag == "i":
            self.out.append("*")

    def handle_data(self, data):
        classes = {c for _, cls in self.stack for c in cls.split()}
        tags = {t for t, _ in self.stack}
        if "uncial" in classes:
            data = _uncial(data)
        elif "Apparatus" in classes:
            data = "".join(_APPARATUS.get(c, c) for c in data)
        elif "sup" in tags:
            data = data.translate(_SUPERSCRIPT)
        self.out.append(_MARKDOWN.sub(r"\\\1", data))

    def text(self) -> str:
        s = "".join(self.out).replace("**", "")   # drop empty italics
        s = re.sub(r"[ \t\xa0]+", " ", s)
        s = re.sub(r" *\n *", "\n", s)
        return _HEBREW_RUN_END.sub(rf"\1{_LRM}", s).strip()


def _parse_netbible_notes(notes_html: str) -> dict[int, list[tuple[str, str]]]:
    """{note_number: [(kind, text), ...]} from netbible.org's notes HTML."""
    notes: dict[int, list[tuple[str, str]]] = {}
    current = None
    for div in re.findall(r'<div class="note">(.*?)</div>(?=\s*<div class="note">|\s*$)', notes_html, re.S):
        m = re.search(r'class="noteNoteSuper"[^>]*>(\d+)<', div)
        if m:
            current = int(m.group(1))
            notes[current] = []
            div = re.sub(r"^\s*<sup>.*?</sup>", "", div, count=1, flags=re.S)
        if current is None:
            continue
        for kind, body in re.findall(r'<span class="notetype">(\w+)</span>(.*?)(?=<span class="notetype">|$)', div, re.S):
            parser = _NoteHTML()
            parser.feed(body)
            parser.close()
            notes[current].append((kind, parser.text()))
    return notes


_MARKER = "\x00"


class _VerseHTML(HTMLParser):
    """netbible.org's chapter text HTML -> per-verse plain text with a marker
    placeholder (and its note number) wherever a note attaches, plus notes
    attached to section headings (e.g. "Psalm 23")."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.verses: dict[int, list] = {}      # verse -> pieces: str or ("note", n)
        self.heading_notes: dict[int, list[tuple[str, int]]] = {}   # verse -> [(heading text, n)]
        self.verse = None
        self.stack = []
        self.heading = None                    # text of the <h3> being read, or None
        self.marker = None                     # (verse, collecting note-number digits)

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        cls = a.get("class", "") or ""
        self.stack.append((tag, cls))
        m = re.match(r"netText_.+_(\d+)$", a.get("id", "") or "")
        if tag == "span" and m:
            self.verse = int(m.group(1))
            self.verses.setdefault(self.verse, [])
        elif tag == "h3":
            self.heading = ""
        elif tag == "a" and "netNoteSuper" in cls:
            self.marker = [int(a.get("data-verse") or self.verse or 0), ""]

    def handle_endtag(self, tag):
        while self.stack:
            t, _ = self.stack.pop()
            if t == tag:
                break
        if tag == "a" and self.marker:
            verse, digits = self.marker
            self.marker = None
            if digits.isdigit():
                if self.heading is not None:
                    self.heading_notes.setdefault(verse, []).append((self.heading.strip(), int(digits)))
                else:
                    self.verses.setdefault(verse, []).append(("note", int(digits)))
        elif tag == "h3":
            self.heading = None

    def handle_data(self, data):
        if self.marker is not None:
            self.marker[1] += data.strip()
            return
        if self.heading is not None:
            self.heading += data
            return
        classes = {c for _, cls in self.stack for c in cls.split()}
        if "vref" in classes or self.verse is None:
            return   # verse/chapter numbers
        if "smcaps" in classes:
            data = data.upper()   # LORD
        self.verses[self.verse].append(data)


def _parse_netbible_text(text_html: str) -> tuple[dict[int, tuple[list[str], list[int]]], dict]:
    """({verse: (segments, note_numbers)}, heading_notes): the verse text split
    at its markers (n markers -> n+1 segments) and the note number of each."""
    p = _VerseHTML()
    p.feed(text_html)
    p.close()
    out = {}
    for verse, pieces in p.verses.items():
        text, numbers = "", []
        for piece in pieces:
            if isinstance(piece, tuple):
                text += _MARKER
                numbers.append(piece[1])
            else:
                text += piece
        text = re.sub(r"[ \t\n\xa0]+", " ", text)
        text = re.sub(rf" (?={_MARKER})", "", text)        # no space before a marker
        segments = [s for s in text.split(_MARKER)]
        segments[0] = segments[0].lstrip()
        segments[-1] = segments[-1].rstrip()
        out[verse] = (segments, numbers)
    return out, p.heading_notes


# ── bolls.life backup: cleaning its legacy-encoded notes ───────────────────

_GREEK = r"[Ͱ-Ͽἀ-῿]"
# A Greek word or phrase, then its transliteration in the legacy Greek-font
# encoding (J = rough breathing, w = omega, q = theta, " = final sigma, ...).
_GREEK_THEN_TRANSLIT = re.compile(
    rf"(?P<greek>{_GREEK}(?:(?:{_GREEK}|[ ’'·+])*{_GREEK})?)(?P<sep>\s*\(|,\s+)"
    rf"(?P<latin>[A-Za-z'\"][A-Za-z'\" +-]*?)(?=[,)])"
)
_SIGLA = {"Ì": "𝔓", "Ï": "𝔐", "Ë": "f"}
# Several parts of one note can run together with no <br>: "...7:11).sn The watery deep."
_NEXT_PART = re.compile(r"(?<=[.)”’\]!?])(?=(?:tn|sn|tc|map) [A-Z“‘(])")
_STRIP_ACCENTS = {"́", "̀", "̂", "͂"}
# End of a Hebrew run followed by left-to-right text: without a left-to-right
# mark there, Discord pulls the following punctuation into the RTL run.
_HEBREW_RUN_END = re.compile(r"([֐-׿])(?=\s*[^\s֐-׿])")
_LRM = "‎"


def _plain_translit(greek: str) -> str:
    t = unicodedata.normalize("NFD", _transliterate_greek(greek))
    return unicodedata.normalize("NFC", "".join(c for c in t if c not in _STRIP_ACCENTS))


def _fix_translit(match: re.Match) -> str:
    greek, sep, latin = match.group("greek"), match.group("sep"), match.group("latin")
    if len(greek.split()) != len(latin.split()):
        return match.group(0)
    return f"{greek}{sep}{_plain_translit(greek)}"


def clean_note(body: str, kind: str = "") -> str:
    """A bolls.life note -> plain text (backup source only)."""
    text = re.sub(r"<a\b[^>]*>(.*?)</a>", r"\1", body, flags=re.S)
    text = re.sub(r"<[^>]+>", "", text)
    text = html_mod.unescape(text)
    if kind == "tc":
        for legacy, real in _SIGLA.items():
            text = text.replace(legacy, real)
    text = text.replace("ÿ", "ᵉ")
    text = _GREEK_THEN_TRANSLIT.sub(_fix_translit, text)
    text = re.sub(r"([֐-׿]),(?=\S)", r"\1, ", text)
    text = re.sub(r"\s+\)", ")", text)
    text = _MARKDOWN.sub(r"\\\1", text)
    text = _HEBREW_RUN_END.sub(rf"\1{_LRM}", text)
    return re.sub(r"\s+", " ", text).strip()


def split_note_groups(comment: str) -> list[list[tuple[str, str]]]:
    """bolls.life: one group per note, each [(kind, cleaned_text), ...]."""
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


# ── lookup ──────────────────────────────────────────────────────────────────

def _err(msg: str) -> dict:
    return {"found": False, "error": msg}


def _anchor_word(segment: str) -> Optional[str]:
    words = re.findall(r"[\w’'-]+", segment)
    return words[-1] if words else None


def _from_netbible(book: str, chapter: int, v1: int, v2: int) -> Optional[list[dict]]:
    """None if netbible.org couldn't be fetched; [] if it was but has no such verse."""
    fetched = _fetch_netbible(book, chapter)
    if not fetched:
        return None
    verses, heading_notes = _parse_netbible_text(fetched[0])
    notes = _parse_netbible_notes(fetched[1])
    out = []
    for n in range(v1, v2 + 1):
        if n not in verses:
            continue
        segments, numbers = verses[n]
        out.append({
            "verse": n,
            "text": "".join(segments),
            "segments": segments,
            "notes": [{"anchor": _anchor_word(segments[i]), "parts": notes.get(num, [])}
                      for i, num in enumerate(numbers)],
            "intro": [{"title": title, "parts": notes.get(num, [])}
                      for title, num in heading_notes.get(n, [])],
        })
    return out


def _from_bolls(book_id: int, chapter: int, v1: int, v2: int) -> Optional[list[dict]]:
    verses = _fetch_bolls_chapter(book_id, chapter)
    if verses is None:
        return None
    out = []
    for n in range(v1, v2 + 1):
        v = verses.get(n)
        if not v:
            continue
        text = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", html_mod.unescape(v["text"]))).strip()
        groups = split_note_groups(v["comment"])
        intro = []
        # bolls files a psalm's overview note ("Psalm 22. The psalmist...") as verse 1's first note
        if groups and re.match(rf"Psalm {chapter}\.", groups[0][0][1]):
            intro = [{"title": f"Psalm {chapter}", "parts": groups.pop(0)}]
        out.append({"verse": n, "text": text, "segments": None,
                    "notes": [{"anchor": None, "parts": parts} for parts in groups],
                    "intro": intro})
    return out


def get_net_notes(reference: str) -> dict:
    """NET text and notes for a verse or short range (up to MAX_VERSES).
    -> {"found", "reference", "url", "source": "netbible" | "bolls",
        "verses": [{"verse": n, "text": str,
                    "segments": [str, ...] | None,   # text split at note markers (None: positions unknown)
                    "notes": [{"anchor": str | None, "parts": [(kind, text), ...]}, ...],
                    "intro": [{"title": str, "parts": [...]}, ...]}]}   # notes on a section heading"""
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

    verses, source = _from_netbible(canon, chapter, v1, v2), "netbible"
    if verses is None:
        verses, source = _from_bolls(book_id, chapter, v1, v2), "bolls"
    if verses is None:
        return _err(f"Couldn't retrieve **{canon} {chapter}** from the NET right now. Try again shortly.")
    if not verses:
        return _err(f"**{canon} {chapter}:{v1}** isn't in the NET.")

    label = f"{v1}" if v1 == v2 else f"{v1}–{v2}"
    return {
        "found": True,
        "reference": f"{canon} {chapter}:{label}",
        "url": f"https://netbible.org/bible/{canon.replace(' ', '+')}+{chapter}",
        "source": source,
        "verses": verses,
    }
