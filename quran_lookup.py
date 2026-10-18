"""
quran_lookup.py
───────────────
The Quran in every English translation of the fawazahmed0 Quran API (no key needed),
like the Bible translations: `!verse Quran 2:255` is M.A.S. Abdel Haleem's translation
(Oxford, 2004); a translation's name after the reference picks another
(`!verse Quran 2:255 arberry`), and several give them side by side
(`!verse Quran 1:1 haleem arberry studyquran`). Pickthall is local (data/quran) and is
also what's shown if the API can't be reached.

CDN: https://cdn.jsdelivr.net/gh/fawazahmed0/quran-api@1/editions/{edition}/{surah}.json
     -> {"chapter": [{"chapter": 1, "verse": 1, "text": "..."}, ...]}
"""
import json
import re
import urllib.request
from collections import OrderedDict

QURAN_CDN = "https://cdn.jsdelivr.net/gh/fawazahmed0/quran-api@1/editions/"
DEFAULT = "haleem"
PICKTHALL = "pickthall"

# slug: (API edition, name shown). Every English edition the API has; the slug is the
# translator's best-known name. "pickthall" is the local copy.
EDITIONS: dict[str, tuple[str, str]] = {
    "haleem":       ("eng-abdelhaleem", "M.A.S. Abdel Haleem (Oxford, 2004)"),
    "studyquran":   ("eng-thestudyquran", "The Study Quran (Nasr et al., 2015)"),
    "arberry":      ("eng-ajarberry", "A. J. Arberry, The Koran Interpreted (1955)"),
    "asad":         ("eng-muhammadasad", "Muhammad Asad, The Message of the Qur'an (1980)"),
    "pickthall":    ("eng-mohammedmarmadu", "Marmaduke Pickthall, The Glorious Quran (1930)"),
    "sahih":        ("eng-ummmuhammad", "Saheeh International (1997)"),
    "yusufali":     ("eng-abdullahyusufal", "Abdullah Yusuf Ali (revised)"),
    "yusufaliorig": ("eng-yusufaliorig", "Abdullah Yusuf Ali (original, 1934)"),
    "khattab":      ("eng-mustafakhattaba", "Mustafa Khattab, The Clear Quran"),
    "khattabgod":   ("eng-mustafakhattabg", "Mustafa Khattab, The Clear Quran (\"God\" edition)"),
    "hilalikhan":   ("eng-muhammadtaqiudd", "Muhammad Taqi-ud-Din al-Hilali & Muhammad Muhsin Khan"),
    "shakir":       ("eng-mohammadhabibsh", "M. H. Shakir"),
    "sarwar":       ("eng-muhammadsarwar", "Muhammad Sarwar"),
    "dawood":       ("eng-njdawood", "N. J. Dawood"),
    "sale":         ("eng-georgesale", "George Sale (1734)"),
    "rodwell":      ("eng-johnmedowsrodwe", "J. M. Rodwell (1861)"),
    "palmer":       ("eng-edwardhenrypalm", "E. H. Palmer (1880)"),
    "bewley":       ("eng-aishabewley", "Aisha Bewley"),
    "maududi":      ("eng-maududi", "Abul A'la Maududi"),
    "maududi2":     ("eng-abulalamaududi", "Abul A'la Maududi (Tafhim al-Qur'an)"),
    "daryabadi":    ("eng-abdulmajiddarya", "Abdul Majid Daryabadi"),
    "ahmedali":     ("eng-ahmedali", "Ahmed Ali"),
    "usmani":       ("eng-muftitaqiusmani", "Mufti Taqi Usmani"),
    "usmani2":      ("eng-muhammadtaqiusm", "Muhammad Taqi Usmani"),
    "qarai":        ("eng-aliquliqarai", "Ali Quli Qara'i"),
    "qarai2":       ("eng-aliquliqarai1", "Ali Quli Qara'i (second edition)"),
    "unal":         ("eng-aliunal", "Ali Ünal"),
    "ghali":        ("eng-muhammadmahmoud", "Muhammad Mahmoud Ghali"),
    "wahiduddin":   ("eng-wahiduddinkhan", "Wahiduddin Khan"),
    "bakhtiar":     ("eng-drlalehbakhtiar", "Laleh Bakhtiar"),
    "itani":        ("eng-talalitani", "Talal Itani"),
    "itaninew":     ("eng-talalaitaninewt", "Talal Itani (new translation)"),
    "kaskas":       ("eng-safikaskas", "Safi Kaskas"),
    "mubarakpuri":  ("eng-safiurrahmanalm", "Safi-ur-Rahman al-Mubarakpuri"),
    "irving":       ("eng-tbirving", "T. B. Irving"),
    "monotheist":   ("eng-themonotheistgr", "The Monotheist Group"),
    "monotheist2":  ("eng-themonotheistgr1", "The Monotheist Group (second edition)"),
    "literal":      ("eng-literal", "A literal translation"),
    "muntakhab":    ("eng-almuntakhabfita", "Al-Muntakhab fi Tafsir al-Quran al-Karim"),
    "abdulhye":     ("eng-abdulhye", "Abdul Hye"),
    "bilalmuhammad": ("eng-albilalmuhammad", "Al-Bilal Muhammad et al."),
    "bakhtiarinejad": ("eng-alibakhtiarinej", "Ali Bakhtiari Nejad"),
    "kamalomar":    ("eng-drkamalomar", "Kamal Omar"),
    "munshey":      ("eng-drmunirmunshey", "Munir Munshey"),
    "farookmalik":  ("eng-farookmalik", "Farook Malik"),
    "hamidaziz":    ("eng-hamidsaziz", "Hamid S. Aziz"),
    "aneesuddin":   ("eng-miraneesuddin", "Mir Aneesuddin"),
    "aneesuddinorig": ("eng-miraneesorigina", "Mir Aneesuddin (original)"),
    "shafi":        ("eng-mohammadshafi", "Mohammad Shafi"),
    "shabbirahmed": ("eng-shabbirahmed", "Shabbir Ahmed"),
    "ahamed":       ("eng-syedvickarahame", "Syed Vickar Ahamed"),
    "rowwad":       ("eng-rowwadtranslati", "Rowwad Translation Center"),
}

# other names people will type for the well-known ones
ALIASES = {
    "abdelhaleem": "haleem", "abdel-haleem": "haleem", "oxford": "haleem",
    "study": "studyquran", "nasr": "studyquran", "tsq": "studyquran",
    "pick": "pickthall", "pickthal": "pickthall",
    "saheeh": "sahih", "sahihinternational": "sahih", "si": "sahih",
    "yusuf": "yusufali", "ali": "yusufali",
    "clearquran": "khattab", "clear": "khattab",
    "hilali": "hilalikhan", "muhsinkhan": "hilalikhan", "noblequran": "hilalikhan",
}

BOOK = re.compile(r"^(?:the\s+)?(?:quran|qur'?an|koran|sura|surah|qur|qran)\s+", re.I)
REF = re.compile(r"^(\d{1,3})(?::(\d{1,3})(?:\s*[-–]\s*(\d{1,3}))?)?$")

_CACHE: "OrderedDict[tuple, list]" = OrderedDict()      # (edition, surah) -> [text of verse 1, 2, ...]
_CACHE_SIZE = 200


def slug(word: str) -> "str | None":
    w = word.lower().strip()
    w = ALIASES.get(w, w)
    return w if w in EDITIONS else None


def parse(reference: str):
    """("Quran 2:255-257 arberry asad") -> (2, 255, 257, ["arberry", "asad"]); None if not a Quran reference."""
    m = BOOK.match(reference.strip())
    if not m:
        return None
    tokens = reference.strip()[m.end():].split()
    chosen = []
    while tokens and slug(tokens[-1]):
        chosen.insert(0, slug(tokens.pop()))
    r = REF.match(" ".join(tokens))
    if not r:
        return None
    surah = int(r.group(1))
    first = int(r.group(2)) if r.group(2) else None
    last = int(r.group(3)) if r.group(3) else first
    if not 1 <= surah <= 114 or (first is not None and last < first):
        return None
    return surah, first, last, list(dict.fromkeys(chosen)) or [DEFAULT]


def _tidy(text: str) -> str:
    text = re.sub(r"<[^>]+>", "", text or "")
    text = re.sub(r"(?<=[a-z][.!?;:])(?=[A-Z])", " ", text)      # "Watchful.Neither" (the API's run-ons)
    return re.sub(r"\s+", " ", text).strip()


def fetch_surah(edition: str, surah: int) -> "list | None":
    """A surah's verses in one translation (cached); None if the API can't be reached."""
    key = (edition, surah)
    if key in _CACHE:
        _CACHE.move_to_end(key)
        return _CACHE[key]
    try:
        req = urllib.request.Request(f"{QURAN_CDN}{edition}/{surah}.json", headers={"User-Agent": "ScriptureBot/1.0"})
        with urllib.request.urlopen(req, timeout=15) as r:
            data = json.loads(r.read().decode("utf-8"))
        verses = [_tidy(v.get("text", "")) for v in sorted(data["chapter"], key=lambda v: v["verse"])]
    except Exception:
        return None
    _CACHE[key] = verses
    while len(_CACHE) > _CACHE_SIZE:
        _CACHE.popitem(last=False)
    return verses


def _passage(verses: list, first, last) -> "str | None":
    if first is None:
        first, last = 1, len(verses)
    if first > len(verses):
        return None
    picked = list(range(first, min(last, len(verses)) + 1))
    if len(picked) == 1:
        return verses[first - 1]
    return "\n".join(f"**[{n}]** {verses[n - 1]}" for n in picked)


def get_quran(reference: str, local) -> "dict | None":
    """The Quran by API, in the translation(s) asked for. `local(ref)` gives the bot's own Pickthall
    for "pickthall", and as the fallback when the API can't be reached. None if not a Quran reference."""
    parsed = parse(reference)
    if parsed is None:
        return None
    surah, first, last, chosen = parsed
    cite = f"Quran {surah}" + (f":{first}" + (f"–{last}" if last != first else "") if first else "")
    local_ref = f"Quran {surah}" + (f":{first}" + (f"-{last}" if last != first else "") if first else "")
    parts = []
    for name in chosen:
        if name == PICKTHALL:
            r = local(local_ref)
            if not r.get("found"):
                return r
            parts.append((EDITIONS[PICKTHALL][1], r["text"]))
            continue
        verses = fetch_surah(EDITIONS[name][0], surah)
        if verses is None:
            if len(chosen) == 1:                        # can't reach it: our own Pickthall instead
                return local(local_ref)
            continue
        text = _passage(verses, first, last)
        if text is None:
            return {"found": False, "error": f"Surah {surah} has only {len(verses)} verses.", "suggestions": []}
        parts.append((EDITIONS[name][1], text))
    if not parts:
        return local(local_ref)
    if len(parts) == 1:
        return {"found": True, "reference": cite, "text": parts[0][1], "source": parts[0][0],
                "book": "Quran", "chapter": surah, "verse": first or 1}
    return {"found": True, "reference": cite, "book": "Quran", "chapter": surah, "verse": first or 1,
            "text": "\n\n".join(f"__{name}__\n{text}" for name, text in parts),
            "source": " · ".join(name.split(",")[0].split(" (")[0] for name, _ in parts)}
