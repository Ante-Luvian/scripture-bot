"""
hadith_lookup.py
────────────────
Live hadith lookups via the fawazahmed0 CDN (no API key required).

CDN base: https://cdn.jsdelivr.net/gh/fawazahmed0/hadith-api@1/editions/

Available English collections:
  Sahih al-Bukhari    → eng-bukhari   (hadiths 1–7563, 97 books)
  Sahih Muslim        → eng-muslim    (hadiths 1–7563, 56 books)
  Sunan Abu Dawud     → eng-abudawud  (hadiths 1–5274, 43 books)
  Jami at-Tirmidhi    → eng-tirmidhi  (hadiths 1–3956, 49 books)
  Sunan an-Nasa'i    → eng-nasai     (hadiths 1–5761, 51 books)
  Sunan Ibn Majah     → eng-ibnmajah  (hadiths 1–4341, 37 books)
  Muwatta Malik       → eng-malik     (hadiths 1–1852, 61 books)
  Forty Hadith Nawawi → eng-nawawi    (hadiths 1–42)
  Forty Hadith Dehlawi→ eng-dehlawi   (hadiths 1–40)

Citation format: !verse <Collection> <number>
  e.g. !verse Bukhari 1  |  !verse Sunan Abu Dawud 1035  |  !verse Nawawi 1

Response JSON: {"hadiths": [{"hadithnumber": N, "text": "..."}]}
"""

import json
import re
import time
import urllib.request
import urllib.parse
from difflib import get_close_matches

HADITH_CDN  = "https://cdn.jsdelivr.net/gh/fawazahmed0/hadith-api@1/editions/"
FETCH_DELAY = 0.3   # seconds between requests

# In-memory cache: section files keyed as "collection:sec:N" → list of hadith dicts
_COLLECTION_CACHE: dict[str, list] = {}

# ── Collection name map ────────────────────────────────────────────────────────
# Maps user-facing names/aliases → CDN edition key (without "eng-" prefix)

HADITH_COLLECTIONS: dict[str, str] = {
    # Sahih Bukhari
    "bukhari": "bukhari",
    "sahih bukhari": "bukhari",
    "al-bukhari": "bukhari",
    "albukhari": "bukhari",
    "bukhâri": "bukhari",

    # Sahih Muslim
    "muslim": "muslim",
    "sahih muslim": "muslim",
    "al-muslim": "muslim",

    # Sunan Abu Dawud
    "abu dawud": "abudawud",
    "abu dawood": "abudawud",
    "abudawud": "abudawud",
    "sunan abu dawud": "abudawud",

    # Jami at-Tirmidhi
    "tirmidhi": "tirmidhi",
    "at-tirmidhi": "tirmidhi",
    "al-tirmidhi": "tirmidhi",
    "sunan tirmidhi": "tirmidhi",

    # Sunan an-Nasa'i
    "nasai": "nasai",
    "nasa'i": "nasai",
    "an-nasai": "nasai",
    "sunan nasai": "nasai",
    "sunan an-nasa'i": "nasai",

    # Sunan Ibn Majah
    "ibn majah": "ibnmajah",
    "ibnmajah": "ibnmajah",
    "ibn maja": "ibnmajah",
    "sunan ibn majah": "ibnmajah",

    # Muwatta Malik
    "muwatta": "malik",
    "malik": "malik",
    "muwatta malik": "malik",
    "al-muwatta": "malik",
    "muwataa": "malik",

    # Forty Hadith of Nawawi
    "nawawi": "nawawi",
    "nawawi 40": "nawawi",
    "nawawi40": "nawawi",
    "forty hadith nawawi": "nawawi",
    "forty hadith of nawawi": "nawawi",
    "40 hadith nawawi": "nawawi",
    "arba'in nawawi": "nawawi",
    "arbaeen nawawi": "nawawi",

    # Forty Hadith of Shah Waliullah Dehlawi
    "dehlawi": "dehlawi",
    "shah waliullah": "dehlawi",
    "waliullah": "dehlawi",
    "forty hadith dehlawi": "dehlawi",
    "forty hadith of dehlawi": "dehlawi",
    "arba'in dehlawi": "dehlawi",
}

# Display names for each collection key
COLLECTION_DISPLAY: dict[str, str] = {
    "bukhari":           "Sahih al-Bukhari",
    "muslim":            "Sahih Muslim",
    "abudawud":          "Sunan Abu Dawud",
    "tirmidhi":          "Jami at-Tirmidhi",
    "nasai":             "Sunan an-Nasa'i",
    "ibnmajah":          "Sunan Ibn Majah",
    "malik":             "Muwatta Malik",
    "nawawi":            "Forty Hadith of Nawawi",
    "dehlawi":           "Forty Hadith of Dehlawi",
}

# Total hadith counts per collection (for display in !books)
COLLECTION_COUNTS: dict[str, int] = {
    "bukhari":  7563,
    "muslim":   7563,
    "abudawud": 5274,
    "tirmidhi": 3956,
    "nasai":    5761,
    "ibnmajah": 4341,
    "malik":    1852,
    "nawawi":   42,
    "dehlawi":  40,
}

# Section (book) counts per collection
COLLECTION_BOOK_COUNTS: dict[str, int] = {
    "bukhari":  97,
    "muslim":   56,
    "abudawud": 43,
    "tirmidhi": 49,
    "nasai":    51,
    "ibnmajah": 37,
    "malik":    61,
    "nawawi":   1,
    "dehlawi":  1,
}


def resolve_collection(raw: str) -> str | None:
    """Return CDN collection key or None."""
    key = raw.lower().strip()
    if key in HADITH_COLLECTIONS:
        return HADITH_COLLECTIONS[key]
    matches = get_close_matches(key, HADITH_COLLECTIONS.keys(), n=1, cutoff=0.7)
    return HADITH_COLLECTIONS[matches[0]] if matches else None


def parse_hadith_ref(reference: str):
    """
    Parse "Bukhari 1" or "Sahih Muslim 500" into (collection_raw, hadith_number).
    Returns None if not a valid hadith reference.
    """
    ref = reference.strip()
    # Strip optional "Hadith" word: "Bukhari Hadith 1"
    ref = re.sub(r"\bhadith\b", "", ref, flags=re.IGNORECASE).strip()

    # Match "Collection Name(s) NUMBER" — number is always last
    m = re.match(r"^(.*?)\s+(\d+)$", ref, re.UNICODE)
    if not m:
        return None

    collection_raw = m.group(1).strip()
    number         = int(m.group(2))

    if number < 1:
        return None

    return collection_raw, number


def fetch_hadith(collection_key: str, number: int) -> dict:
    """
    Fetch a single hadith. Tries the per-hadith URL first (fast, ~1KB),
    then falls back to scanning section files if the per-hadith file
    returns the full collection (empty text fields) instead.
    """
    display_name = COLLECTION_DISPLAY.get(collection_key, collection_key.title())

    # ── Strategy 1: per-hadith file ──────────────────────────────────────────
    # e.g. eng-bukhari/1.json → {"hadithnumber":1,"text":"Narrated..."}
    per_hadith_key = f"{collection_key}:hadith:{number}"
    if per_hadith_key not in _COLLECTION_CACHE:
        url = f"{HADITH_CDN}eng-{collection_key}/{number}.json"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "ScriptureBot/1.0"})
            with urllib.request.urlopen(req, timeout=15) as r:
                data = json.loads(r.read().decode("utf-8"))
            time.sleep(FETCH_DELAY)
            text = ""
            if isinstance(data, dict):
                # Format: {"metadata":..., "hadiths":[{"hadithnumber":1,"text":"..."}]}
                hadiths = data.get("hadiths", [])
                if hadiths:
                    text = str(hadiths[0].get("text") or "")
                # Fallback: top-level text field
                if not text:
                    text = str(data.get("text") or "")
            _COLLECTION_CACHE[per_hadith_key] = text if text.strip() else None
        except Exception:
            _COLLECTION_CACHE[per_hadith_key] = None

    cached_text = _COLLECTION_CACHE.get(per_hadith_key)
    if cached_text:
        text = re.sub(r"<[^>]+>", "", str(cached_text)).strip()
        if text:
            return {
                "found": True,
                "reference": f"{display_name} {number}",
                "text": text,
                "source": f"{display_name} (fawazahmed0 Hadith API)",
            }

    # ── Strategy 2: section files ─────────────────────────────────────────────
    # Some collections don't have per-hadith files; scan sections instead.
    for section in range(0, 61):
        cache_key = f"{collection_key}:sec:{section}"

        if cache_key not in _COLLECTION_CACHE:
            url = f"{HADITH_CDN}eng-{collection_key}/sections/{section}.json"
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "ScriptureBot/1.0"})
                with urllib.request.urlopen(req, timeout=30) as r:
                    data = json.loads(r.read().decode("utf-8"))
                time.sleep(FETCH_DELAY)
                _COLLECTION_CACHE[cache_key] = data.get("hadiths", [])
            except urllib.error.HTTPError as e:
                if e.code == 404:
                    _COLLECTION_CACHE[cache_key] = []
                    continue
                return {"found": False, "error": f"HTTP error {e.code}.", "suggestions": []}
            except Exception as e:
                return {"found": False, "error": f"CDN error: {e}", "suggestions": []}

        hadiths = _COLLECTION_CACHE.get(cache_key, [])
        if not hadiths:
            continue

        nums = [h.get("hadithnumber", 0) for h in hadiths]
        min_n, max_n = min(nums), max(nums)

        if min_n > number:
            break
        if max_n < number:
            continue

        entry = next((h for h in hadiths if h.get("hadithnumber") == number), None)
        if entry:
            text = re.sub(r"<[^>]+>", "", str(entry.get("text") or "")).strip()
            if text:
                return {
                    "found": True,
                    "reference": f"{display_name} {number}",
                    "text": text,
                    "source": f"{display_name} (fawazahmed0 Hadith API)",
                }
            # Found but empty text
            all_hadiths = _COLLECTION_CACHE.get(cache_key, [])
            first_with_text = next((h for h in all_hadiths if h.get("text", "").strip()), None)
            first_num = first_with_text.get("hadithnumber", "?") if first_with_text else "?"
            return {"found": False, "error": f"No English text available for {display_name} #{number} in this API. Try #{first_num}.", "suggestions": []}

    return {
        "found": False,
        "error": f"Hadith #{number} not found in {display_name}.",
        "suggestions": [],
    }


def get_hadith_section(collection_key: str, section: int) -> dict | None:
    """
    Fetch one whole section ("book") of a collection.
    Returns {"name": str, "hadiths": [(number, text), ...]} or None.
    """
    cache_key = f"{collection_key}:secfull:{section}"
    if cache_key not in _COLLECTION_CACHE:
        url = f"{HADITH_CDN}eng-{collection_key}/sections/{section}.json"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "ScriptureBot/1.0"})
            with urllib.request.urlopen(req, timeout=30) as r:
                data = json.loads(r.read().decode("utf-8"))
            time.sleep(FETCH_DELAY)
            _COLLECTION_CACHE[cache_key] = data
        except Exception:
            _COLLECTION_CACHE[cache_key] = None

    data = _COLLECTION_CACHE.get(cache_key)
    if not data:
        return None
    hadiths = data.get("hadiths", [])
    if not hadiths:
        return None
    meta = data.get("metadata", {}) or {}
    section_name = (meta.get("section") or {}).get(str(section), "")
    items = []
    for h in hadiths:
        text = re.sub(r"<[^>]+>", "", str(h.get("text") or "")).strip()
        if text:
            items.append((h.get("hadithnumber"), text))
    if not items:
        return None
    return {"name": section_name, "hadiths": items}


def get_hadith(reference: str) -> dict | None:
    """
    Top-level hadith lookup. Returns result dict or None if not a hadith ref.
    """
    parsed = parse_hadith_ref(reference)
    if parsed is None:
        return None

    collection_raw, number = parsed
    collection_key = resolve_collection(collection_raw)
    if collection_key is None:
        return None   # Not a recognisable collection

    return fetch_hadith(collection_key, number)
