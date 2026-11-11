"""
The Fathers on a verse from the library's own texts (data/catena_index.json, from scripts/build_catena_index.py), in
the shape !catena shows: [(who, text)], strongest first -- Aquinas's Catena Aurea on a Gospel verse, each Father of it
in turn; then the commentaries and homilies on that book; then the Fathers quoting the verse elsewhere, one passage a
work.
"""
import functools
import json
import re

from core import ROOT, lookup

INDEX_PATH = ROOT / "data" / "catena_index.json"
PATRISTICS = ROOT / "data" / "patristics"
EXCERPT = 1400
MOST = 30
# who wrote the works in a file, where the file's name doesn't say it plainly
WRITERS = {"chrysostom": "John Chrysostom", "augustine": "Augustine", "gregory_the_great": "Gregory the Great",
           "gregory_moralia": "Gregory the Great", "gregory_nazianzen": "Gregory Nazianzen",
           "gregory_of_nyssa": "Gregory of Nyssa", "gregory_thaumaturgus": "Gregory Thaumaturgus",
           "cyril_of_alexandria": "Cyril of Alexandria", "cyril_of_jerusalem": "Cyril of Jerusalem",
           "john_of_damascus": "John of Damascus", "basil_the_great": "Basil the Great", "john_cassian": "John Cassian",
           "clement_of_alexandria": "Clement of Alexandria", "clement_of_rome": "Clement of Rome",
           "hilary_of_poitiers": "Hilary of Poitiers", "ephrem_the_syrian": "Ephrem the Syrian",
           "theodore_of_mopsuestia": "Theodore of Mopsuestia", "eusebius_of_caesarea": "Eusebius",
           "isidore_of_seville": "Isidore of Seville", "leo_the_great": "Leo the Great", "mar_jacob": "Jacob of Serugh",
           "philokalia": "The Philokalia", "paradise_of_the_fathers": "The Desert Fathers",
           "apostolic_constitutions": "The Apostolic Constitutions", "church_councils": "The Councils",
           "early_liturgies": "The early liturgies"}


@functools.lru_cache(maxsize=1)
def index() -> dict:
    try:
        return json.loads(INDEX_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


@functools.lru_cache(maxsize=1)
def writer_of() -> dict:
    """work -> who wrote it, from the file it's in."""
    out = {}
    for f in PATRISTICS.glob("*.json"):
        try:
            books = json.loads(f.read_text(encoding="utf-8")).get("books", {})
        except ValueError:
            continue
        who = WRITERS.get(f.stem) or " ".join(w.capitalize() if w not in ("of", "the") else w for w in f.stem.split("_"))
        for work in books:
            out[work] = who
    return out


def passage(work: str, chapter: str, verse: str) -> str:
    for corpus in lookup._data.values():
        if work in corpus:
            return corpus[work].get(chapter, {}).get(verse, "")
    return ""


def excerpt(text: str, at: int) -> str:
    """The paragraph of `text` around character `at`, trimmed to about EXCERPT characters at sentence ends."""
    start = text.rfind("\n", 0, at) + 1
    end = text.find("\n", at)
    para = text[start:end if end >= 0 else len(text)].strip()
    if len(para) < 200 and end >= 0:                               # (a short line: take the next with it)
        nxt = text.find("\n", end + 1)
        para = text[start:nxt if nxt >= 0 else len(text)].strip()
    if len(para) <= EXCERPT:
        return para
    rel = at - start
    lo = max(0, rel - EXCERPT // 2)
    lo = para.rfind(". ", 0, lo) + 2 if para.rfind(". ", 0, lo) > 0 else 0
    hi = para.find(". ", lo + EXCERPT - 200)
    hi = hi + 1 if 0 < hi < lo + EXCERPT + 300 else lo + EXCERPT
    return ("… " if lo else "") + para[lo:hi].strip() + (" …" if hi < len(para) else "")


def catena_aurea(text: str) -> list:
    """A Catena Aurea passage as its Fathers' comments: [(who, comment)] ("**Chrysostom**: While all...")."""
    out = []
    for line in text.split("\n"):
        m = re.match(r"\*\*([^*]+)\*\*(?:\s*\(([^)]*)\))?:\s*(.*)$", line)
        if m:
            out.append([m[1], m[3]])
        elif out and line and not line.startswith("*"):
            out[-1][1] += "\n" + line
    return out


def sections(book: str, chapter: int, verse: int) -> list:
    """[(who, text)] for a verse: what !catena shows, from the library."""
    entries = index().get(f"{book} {chapter}:{verse}", [])
    out, seen_works, seen_text = [], set(), set()
    for rank, work, ch, v, at in entries:
        text = passage(work, ch, v)
        if not text:
            continue
        if rank == 1:
            for who, comment in catena_aurea(text):
                key = comment[:80]
                if key in seen_text:
                    continue
                seen_text.add(key)
                body = comment if len(comment) <= EXCERPT * 2 else excerpt(comment, 0)
                out.append((f"{who} (in the Catena Aurea)", f"{body}\n\n— *Aquinas, {work}*"))
            continue
        if (work, ch) in seen_works or (rank == 3 and work in {w for w, _ in seen_works}):
            continue                                                 # (one passage a work, for a quotation)
        seen_works.add((work, ch))
        who = writer_of().get(work, "")
        if work == "Readings from the Breviary":
            head = next((l.strip("*") for l in text.split("\n") if l.startswith("*") and not l.startswith("*On ")
                         and re.search(r"Homily|Sermon|From", l)), "")
            who = re.sub(r"\s*\(.*", "", head) or "The Breviary"
            body = excerpt(text, at + 1)
        else:
            body = excerpt(text, at)
        if len(body) < 60:
            continue
        out.append((who or work, f"{body}\n\n— *{work}*"))
        if len(out) >= MOST:
            break
    return out[:MOST]
