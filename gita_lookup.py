"""
gita_lookup.py
──────────────
More English translations of the Bhagavad Gita, and the great commentaries on it, from
the vedicscriptures Gita API (no key needed). `!verse Gita 2:47` stays the bot's own
Shri Purohit Swami; a name after the reference picks another, and several compare them:

    !verse Gita 2:47 sivananda        !verse Gita 2:47 purohit gambirananda prabhupada
    !verse Gita 2:47 shankara         (Shankara's commentary on the verse, in English)

API: https://vedicscriptures.github.io/slok/{chapter}/{verse}
     -> {"siva": {"author": "Swami Sivananda", "et": "2.47 Thy right is..."}, ...}
     Only the English ("et"/"ec") fields are used.
"""
import json
import re
import urllib.request
from collections import OrderedDict

API = "https://vedicscriptures.github.io/slok/"
VERSES = [47, 72, 43, 42, 29, 47, 30, 28, 34, 42, 55, 20, 35, 27, 20, 24, 28, 78]   # per chapter
MAX_VERSES = 20

# slug: (API key, field, name shown)
EDITIONS = {
    "purohit":        ("purohit", "et", "Shri Purohit Swami (1935)"),
    "sivananda":      ("siva", "et", "Swami Sivananda"),
    "gambirananda":   ("gambir", "et", "Swami Gambirananda"),
    "adidevananda":   ("adi", "et", "Swami Adidevananda"),
    "sankaranarayan": ("san", "et", "Dr. S. Sankaranarayan"),
    "prabhupada":     ("prabhu", "et", "A. C. Bhaktivedanta Swami Prabhupada (Bhagavad-gītā As It Is)"),
    # commentaries, in English
    "shankara":       ("sankar", "et", "Shankara's commentary (tr. Gambirananda)"),
    "ramanuja":       ("raman", "et", "Ramanuja's commentary (tr. Adidevananda)"),
    "abhinavagupta":  ("abhinav", "et", "Abhinavagupta's commentary"),
    "purport":        ("prabhu", "ec", "Prabhupada's purport"),
}
ALIASES = {"siva": "sivananda", "gambhirananda": "gambirananda", "gambir": "gambirananda", "adi": "adidevananda",
           "asitis": "prabhupada", "iskcon": "prabhupada", "sankara": "shankara", "shankaracharya": "shankara",
           "ramanujacharya": "ramanuja", "abhinava": "abhinavagupta"}

BOOK = re.compile(r"^(?:the\s+)?(?:bhagavad[\s-]*gita|bhagavadgita|gita|bg)\s+", re.I)
REF = re.compile(r"^(\d{1,2}):(\d{1,2})(?:\s*[-–]\s*(\d{1,2}))?$")

_CACHE: "OrderedDict[tuple, dict]" = OrderedDict()


def slug(word: str) -> "str | None":
    w = ALIASES.get(word.lower().strip(), word.lower().strip())
    return w if w in EDITIONS else None


def parse(reference: str):
    """"Gita 2:47-48 sivananda shankara" -> (2, 47, 48, ["sivananda", "shankara"]); None unless a
    translation is named (plain references stay the bot's own Purohit)."""
    m = BOOK.match(reference.strip())
    if not m:
        return None
    tokens = reference.strip()[m.end():].split()
    chosen = []
    while tokens and slug(tokens[-1]):
        chosen.insert(0, slug(tokens.pop()))
    r = REF.match(" ".join(tokens))
    if not r or not chosen:
        return None
    ch, first = int(r.group(1)), int(r.group(2))
    last = int(r.group(3)) if r.group(3) else first
    return ch, first, last, list(dict.fromkeys(chosen))


def fetch(chapter: int, verse: int) -> "dict | None":
    key = (chapter, verse)
    if key in _CACHE:
        return _CACHE[key]
    try:
        req = urllib.request.Request(f"{API}{chapter}/{verse}", headers={"User-Agent": "ScriptureBot/1.0"})
        with urllib.request.urlopen(req, timeout=15) as r:
            data = json.loads(r.read().decode("utf-8"))
    except Exception:
        return None
    _CACHE[key] = data
    while len(_CACHE) > 500:
        _CACHE.popitem(last=False)
    return data


def _clean(text: str, chapter: int, verse: int) -> str:
    text = re.sub(rf"^\s*{chapter}\.{verse}\.?\s*", "", text or "")       # each starts "2.47 "
    return re.sub(r"\s+", " ", text).strip()


def get_gita(reference: str, local) -> "dict | None":
    """The Gita in the translation(s) or commentaries named; `local(ref)` is the bot's own Purohit.
    None if this isn't a Gita reference naming a translation."""
    parsed = parse(reference)
    if parsed is None:
        return None
    ch, first, last = parsed[:3]
    chosen = parsed[3]
    if not 1 <= ch <= 18 or not 1 <= first <= last <= VERSES[ch - 1]:
        limit = VERSES[ch - 1] if 1 <= ch <= 18 else None
        return {"found": False, "suggestions": [],
                "error": f"Chapter {ch} of the Gita has {limit} verses." if limit else "The Gita has 18 chapters."}
    last = min(last, first + MAX_VERSES - 1)
    cite = f"Bhagavad Gita {ch}:{first}" + (f"–{last}" if last != first else "")
    blocks = []
    for name in chosen:
        key, field, shown = EDITIONS[name]
        if name == "purohit":
            r = local(f"Bhagavad Gita {ch}:{first}" + (f"-{last}" if last != first else ""))
            if r.get("found"):
                blocks.append((shown, r["text"]))
            continue
        verses = []
        for v in range(first, last + 1):
            data = fetch(ch, v)
            if data is None:
                return {"found": False, "error": "⚠️ Couldn't reach the Gita API just now.", "suggestions": []}
            text = _clean((data.get(key) or {}).get(field, ""), ch, v)
            if text and "did not comment" not in text:
                verses.append(text if first == last else f"**[{v}]** {text}")
        blocks.append((shown, "\n".join(verses) or "*(nothing on this verse)*"))
    text = blocks[0][1] if len(blocks) == 1 else "\n\n".join(f"__{n}__\n{t}" for n, t in blocks)
    pages = _pages(text)
    return {"found": True, "reference": cite, "text": pages[0], "pages": pages if len(pages) > 1 else None,
            "source": " · ".join(n for n, _ in blocks), "book": "Bhagavad Gita", "chapter": ch, "verse": first}


def _pages(text: str, limit: int = 3800) -> list:
    import sutta_lookup
    return sutta_lookup.pack(text.split("\n"), limit) if len(text) > limit else [text]
