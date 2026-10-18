"""
banidb_lookup.py
────────────────
Sikh scripture from BaniDB (no key needed), in English:

  · the Guru Granth Sahib in more translations than the bot's own Sant Singh Khalsa:
        !verse Guru Granth Sahib 1:1 manmohan     (Manmohan Singh)
        !verse Guru Granth Sahib 1:1 banidb       (BaniDB's revision of Khalsa)
        !verse Guru Granth Sahib 1:1 khalsa manmohan   (side by side)
  · the Dasam Granth, the writings of Guru Gobind Singh, by page and line:
        !verse Dasam Granth 1        !verse Dasam Granth 1:5-8
  · the Vaaran of Bhai Gurdas, the "key to the Guru Granth Sahib", by vaar and pauri:
        !verse Bhai Gurdas 1:1       !verse Vaaran 1

API: https://api.banidb.com/v2/angs/{page}/{source}  (source G, D or B)
     -> {"page": [{"lineNo": n, "translation": {"en": {"bdb": ..., "ms": ..., "ssk": ...}}}, ...]}
"""
import json
import re
import urllib.request
from collections import OrderedDict

API = "https://api.banidb.com/v2/angs/"

# source: (names, what it's called, pages, how lines are numbered)
SOURCES = {
    "G": (("guru granth sahib", "sri guru granth sahib", "ggs", "sggs", "adi granth"),
          "Guru Granth Sahib", 1430, "line"),
    "D": (("dasam granth", "dasam granth sahib", "dasam bani", "sri dasam granth"),
          "Dasam Granth", 1428, "line"),
    "B": (("bhai gurdas", "vaaran bhai gurdas", "vaaran", "vaars of bhai gurdas", "vaar", "varan bhai gurdas",
           "bhai gurdas vaaran"), "Vaaran of Bhai Gurdas", 40, "pauri"),
}
NAMES = {name: src for src, (names, *_) in SOURCES.items() for name in names}

TRANSLATIONS = {   # slug: (field, name shown)
    "khalsa":   ("ssk", "Sant Singh Khalsa"),
    "manmohan": ("ms", "Manmohan Singh"),
    "banidb":   ("bdb", "BaniDB"),
}
ALIASES = {"ssk": "khalsa", "santsingh": "khalsa", "ms": "manmohan", "manmohansingh": "manmohan", "bdb": "banidb"}

REF = re.compile(r"^(?P<name>[a-z ]+?)\s+(?P<page>\d{1,4})(?::(?P<a>\d{1,4})(?:\s*[-–]\s*(?P<b>\d{1,4}))?)?$", re.I)

_CACHE: "OrderedDict[tuple, list]" = OrderedDict()


def slug(word: str) -> "str | None":
    w = ALIASES.get(word.lower().strip(), word.lower().strip())
    return w if w in TRANSLATIONS else None


def parse(reference: str):
    """"Bhai Gurdas 1:1" -> ("B", 1, 1, 1, ["banidb"]); the Guru Granth Sahib only when a translation
    is named (plain references stay the bot's own copy). None if it isn't one of these."""
    tokens = reference.strip().split()
    chosen = []
    while tokens and slug(tokens[-1]):
        chosen.insert(0, slug(tokens.pop()))
    m = REF.match(" ".join(tokens))
    if not m:
        return None
    src = NAMES.get(re.sub(r"\s+", " ", m.group("name").strip().lower()))
    if src is None or (src == "G" and not chosen):
        return None
    a = int(m.group("a")) if m.group("a") else None
    b = int(m.group("b")) if m.group("b") else a
    return src, int(m.group("page")), a, b, list(dict.fromkeys(chosen)) or ["banidb"]


def fetch_page(src: str, page: int) -> "list | None":
    key = (src, page)
    if key in _CACHE:
        _CACHE.move_to_end(key)
        return _CACHE[key]
    try:
        req = urllib.request.Request(f"{API}{page}/{src}", headers={"User-Agent": "ScriptureBot/1.0"})
        with urllib.request.urlopen(req, timeout=20) as r:
            lines = json.loads(r.read().decode("utf-8")).get("page") or []
    except Exception:
        return None
    _CACHE[key] = lines
    while len(_CACHE) > 100:
        _CACHE.popitem(last=False)
    return lines


def _english(line: dict, field: str) -> str:
    en = (line.get("translation") or {}).get("en") or {}
    return re.sub(r"\s+", " ", (en.get(field) or "")).strip().rstrip("~").strip()      # ("~": a pause mark)


def get_bani(reference: str, local) -> "dict | None":
    """`local(ref)` is the bot's own Guru Granth Sahib, shown if BaniDB can't be reached. None if not a BaniDB reference."""
    parsed = parse(reference)
    if parsed is None:
        return None
    src, page, a, b, chosen = parsed
    _, title, pages, unit = SOURCES[src]
    if not 1 <= page <= pages:
        return {"found": False, "suggestions": [], "error": f"The {title} has {pages} "
                + ("vaars." if unit == "pauri" else "pages.")}
    cite = f"{title} {page}" + (f":{a}" + (f"–{b}" if b != a else "") if a else "")
    lines = fetch_page(src, page)
    if lines is None:
        if src == "G":
            return local(f"Guru Granth Sahib {page}" + (f":{a}" + (f"-{b}" if b != a else "") if a else ""))
        return {"found": False, "error": "⚠️ Couldn't reach BaniDB just now.", "suggestions": []}
    if unit == "pauri":                                 # Bhai Gurdas: lineNo is the pauri
        picked = [l for l in lines if a is None or a <= (l.get("lineNo") or 0) <= b]
        number = lambda i, l: l.get("lineNo")
    else:                                               # a page's lines, counted from 1
        picked = [l for i, l in enumerate(lines, 1) if a is None or a <= i <= b]
        number = lambda i, l: (a or 1) + i
    if not picked:
        return {"found": False, "suggestions": [], "error": f"**{cite}** isn't there: "
                + (f"vaar {page} has {max((l.get('lineNo') or 0) for l in lines)} pauris." if unit == "pauri"
                   else f"page {page} has {len(lines)} lines.")}
    blocks = []
    for name in chosen:
        field, shown = TRANSLATIONS[name]
        out, last = [], None
        for i, line in enumerate(picked):
            text = _english(line, field)
            if not text:
                continue
            n = number(i, line)
            if unit == "pauri" and n != last:
                out.append(f"**[{n}]** {text}")
                last = n
            elif unit == "pauri":
                out.append(text)
            else:
                out.append(f"**[{n}]** {text}" if len(picked) > 1 else text)
        if out:
            blocks.append((shown, "\n".join(out)))
    if not blocks:
        return {"found": False, "error": f"No English translation of **{cite}** in "
                + " or ".join(TRANSLATIONS[c][1] for c in chosen) + ".", "suggestions": []}
    text = blocks[0][1] if len(blocks) == 1 else "\n\n".join(f"__{n}__\n{t}" for n, t in blocks)
    import sutta_lookup
    pages_ = sutta_lookup.pack(text.split("\n"), 3800, sep="\n") if len(text) > 3800 else [text]
    return {"found": True, "reference": cite, "text": pages_[0], "pages": pages_ if len(pages_) > 1 else None,
            "source": f"{title} — " + " · ".join(f"{n}'s translation" if n != "BaniDB" else "BaniDB's translation"
                                                for n, _ in blocks) + " (via BaniDB)",
            "book": title, "chapter": page, "verse": a or 1}
