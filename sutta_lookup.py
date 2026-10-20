"""
sutta_lookup.py
───────────────
The Pali Canon -- the earliest Buddhist scriptures -- from SuttaCentral, in Bhikkhu
Sujato's English translation (no key needed). Cited the way Buddhists cite them:

    !verse MN 1         the Middle Discourses (Majjhima Nikaya), sutta 1
    !verse DN 16        the Long Discourses (Digha Nikaya)
    !verse SN 56.11     the Linked Discourses (Samyutta Nikaya), chapter 56, sutta 11
    !verse AN 3.65      the Numbered Discourses (Anguttara Nikaya)
    !verse Ud 1.1 · Iti 1 · Thag 1.1 · Thig 1.1 · Kp 9
    !verse MN 1:3       just section 3 of the sutta
    !verse Dhp 183 sujato · Snp 1.8 sujato   (Dhp and Snp alone stay the bot's own older translations)

API: https://suttacentral.net/api/bilarasuttas/{uid}/sujato?lang=en  -> segments
     https://suttacentral.net/api/suttaplex/{book}?language=en       -> a book's suttas (for grouped
     short suttas like AN 1.1-10, which SuttaCentral keeps together)
"""
import json
import re
import urllib.request
from collections import OrderedDict

API = "https://suttacentral.net/api/"
TRANSLATOR = "sujato"
SOURCE = "trans. Bhikkhu Sujato"

# uid prefix: (names people use, what it's called)
COLLECTIONS = {
    "dn":   (("dn", "digha nikaya", "digha", "dīgha nikāya"), "Long Discourses (Dīgha Nikāya)"),
    "mn":   (("mn", "majjhima nikaya", "majjhima", "majjhima nikāya"), "Middle Discourses (Majjhima Nikāya)"),
    "sn":   (("sn", "samyutta nikaya", "samyutta", "saṁyutta nikāya"), "Linked Discourses (Saṁyutta Nikāya)"),
    "an":   (("an", "anguttara nikaya", "anguttara", "aṅguttara nikāya"), "Numbered Discourses (Aṅguttara Nikāya)"),
    "ud":   (("ud", "udana", "udāna"), "Heartfelt Sayings (Udāna)"),
    "iti":  (("iti", "itivuttaka"), "So It Was Said (Itivuttaka)"),
    "thag": (("thag", "theragatha", "theragāthā"), "Verses of the Senior Monks (Theragāthā)"),
    "thig": (("thig", "therigatha", "therīgāthā"), "Verses of the Senior Nuns (Therīgāthā)"),
    "kp":   (("kp", "khuddakapatha", "khuddakapāṭha"), "Basic Passages (Khuddakapāṭha)"),
    "snp":  (("snp",), "Anthology of Discourses (Sutta Nipāta)"),
    "dhp":  (("dhp",), "Sayings of the Dhamma (Dhammapada)"),
}
LOCAL_TOO = {"snp", "dhp"}            # the bot has its own; SuttaCentral's only when "sujato" is asked for
NAMES = {name: uid for uid, (names, _) in COLLECTIONS.items() for name in names}

REF = re.compile(r"^(?P<name>[a-zāīūṁṅñṭḍṇḷ ]+?)\s*(?P<num>\d+(?:\.\d+)?(?:\s*[-–]\s*\d+)?)"
                 r"(?::(?P<sec>\d+)(?:\s*[-–]\s*(?P<sec2>\d+))?)?(?P<sujato>\s+sujato)?$", re.I)

_CACHE: "OrderedDict[str, dict]" = OrderedDict()


def _get(path: str):
    if path in _CACHE:
        _CACHE.move_to_end(path)
        return _CACHE[path]
    req = urllib.request.Request(API + path, headers={"User-Agent": "ScriptureBot/1.0"})
    with urllib.request.urlopen(req, timeout=20) as r:
        data = json.loads(r.read().decode("utf-8"))
    _CACHE[path] = data
    while len(_CACHE) > 100:
        _CACHE.popitem(last=False)
    return data


def parse(reference: str):
    """"SN 56.11:2" -> ("sn", "sn56.11", 2, 2); None if it isn't a SuttaCentral reference."""
    m = REF.match(reference.strip())
    if not m:
        return None
    coll = NAMES.get(re.sub(r"\s+", " ", m.group("name").strip().lower()))
    if coll is None or (coll in LOCAL_TOO and not m.group("sujato")):
        return None
    uid = coll + re.sub(r"\s+", "", m.group("num")).replace("–", "-")
    sec = int(m.group("sec")) if m.group("sec") else None
    sec2 = int(m.group("sec2")) if m.group("sec2") else sec
    return coll, uid, sec, sec2


def _number(uid: str) -> "tuple[str, float] | None":
    m = re.match(r"^([a-z]+(?:\d+\.)?)(\d+)$", uid)
    return (m.group(1), int(m.group(2))) if m else None


def find_group(uid: str) -> "str | None":
    """For a short sutta SuttaCentral keeps in a group ("an1.5" is in "an1.1-10"), the group's uid."""
    split = _number(uid)
    if split is None:
        return None
    prefix, n = split
    book = prefix.rstrip(".") if "." in prefix else prefix
    try:
        listing = _get(f"suttaplex/{book}?language=en")
    except Exception:
        return None
    for item in listing if isinstance(listing, list) else []:
        m = re.match(rf"^{re.escape(prefix)}(\d+)-(\d+)$", item.get("uid") or "")
        if m and int(m.group(1)) <= n <= int(m.group(2)):
            return item["uid"]
    return None


def render(data: dict, only: str = "", sec=None, sec2=None) -> "tuple[str, list]":
    """(title, lines) from SuttaCentral's segments: headings in bold, paragraphs and verse lines kept."""
    text, html = data.get("translation_text") or {}, data.get("html_text") or {}
    title_bits, lines, para = [], [], ""
    for seg in data.get("keys_order") or list(text):
        uid, _, pos = seg.partition(":")
        if only and uid != only:
            continue
        words = re.sub(r"<[^>]+>", "", text.get(seg) or "").strip()     # ("<j>": a line-break hint)
        markup = html.get(seg) or ""
        if pos.startswith("0."):                            # the heading block: collection, chapter, title
            if words:
                title_bits.append(words)
            continue
        if sec is not None:
            head = pos.split(".")[0]
            if not head.isdigit() or not sec <= int(head) <= sec2:
                continue
        if not words:
            continue
        if re.search(r"<h\d", markup):
            if only and words.rstrip(".") == uid.rsplit(".", 1)[-1].lstrip("dhpan"):
                continue                                # the bare number heading of a sutta in a group
            if para:
                lines.append(para); para = ""
            lines.append(f"**{words}**")
            continue
        if re.search(r"<(p|blockquote|li)\b", markup) and para:
            lines.append(para); para = ""
        if "verse-line" in markup or "<br" in markup:
            para += ("\n" if para else "") + words
        else:
            para += (" " if para else "") + words
        if re.search(r"</(p|blockquote|li)>", markup):
            lines.append(para); para = ""
    if para:
        lines.append(para)
    return (title_bits[-1] if title_bits else ""), lines


def pack(lines: list, limit: int = 3800, sep: str = "\n\n") -> list:
    """Paragraphs into embed-sized pages; a paragraph longer than a page is cut at a sentence."""
    pieces = []
    for line in lines:
        while len(line) > limit:
            cut = line.rfind(". ", 0, limit)
            cut = cut + 1 if cut > 0 else limit
            pieces.append(line[:cut])
            line = line[cut:].strip()
        pieces.append(line)
    pages, page = [], ""
    for piece in pieces:
        if page and len(page) + len(sep) + len(piece) > limit:
            pages.append(page)
            page = ""
        page = f"{page}{sep}{piece}" if page else piece
    if page:
        pages.append(page)
    return pages

def get_sutta(reference: str) -> "dict | None":
    """A sutta (or a section of one) from SuttaCentral; None if the reference isn't one."""
    parsed = parse(reference)
    if parsed is None:
        return None
    coll, uid, sec, sec2 = parsed
    cite = f"{coll.upper() if coll in ('dn', 'mn', 'sn', 'an') else coll.capitalize()} {uid[len(coll):]}" + (
        f":{sec}" + (f"–{sec2}" if sec2 != sec else "") if sec else "")
    try:
        data, only = _get(f"bilarasuttas/{uid}/{TRANSLATOR}?lang=en"), ""
        if not data.get("translation_text"):
            group = find_group(uid)
            if group is None:
                return {"found": False, "error": f"SuttaCentral has no **{cite}** in Sujato's translation.",
                        "suggestions": []}
            data, only = _get(f"bilarasuttas/{group}/{TRANSLATOR}?lang=en"), uid
    except Exception as e:
        return {"found": False, "error": f"⚠️ Couldn't reach SuttaCentral ({e}).", "suggestions": []}
    title, lines = render(data, only, sec, sec2)
    if not lines:
        return {"found": False, "error": f"**{cite}** has no section {sec}." if sec else
                f"SuttaCentral has no **{cite}** in Sujato's translation.", "suggestions": []}
    pages = pack(lines)
    return {"found": True, "reference": f"{cite} · {title}" if title else cite, "text": pages[0],
            "source": SOURCE, "pages": pages if len(pages) > 1 else None,
            "book": COLLECTIONS[coll][1], "chapter": uid[len(coll):], "verse": sec or 1}
