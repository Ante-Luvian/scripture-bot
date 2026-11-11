"""
St Thomas Aquinas's Catena Aurea, the "Golden Chain": the Fathers on the four Gospels, verse by verse, in the
Oxford translation edited by J. H. Newman (1841-45) -> data/patristics/catena_aurea.json, a book a Gospel
("Catena Aurea on Matthew"...), a chapter a chapter of the Gospel, a verse a verse: the Gospel's words in italics, then
each Father in turn, his name in bold.

Matthew and Mark from CCEL's ThML (catena1.xml, catena2.xml); Luke and John from the Dominican House of Studies'
pages (isidore.co/aquinas/english/CALuke.htm, CAJohn.htm). (CCEL has only the first two; isidore.co's Matthew and Mark
have thousands of characters lost as U+FFFD.) A passage on several verses ("Ver. 2-6", "3-5.") is kept on its first,
with the verses it covers in its heading; one verse in parts ("1a.", "1b.") is kept as one.

    python scripts/build_catena_aurea.py
"""
import codecs
import html
import json
import re
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CACHE = Path(__file__).resolve().parent / ".cache" / "catena_aurea"
OUT = ROOT / "data" / "patristics" / "catena_aurea.json"
UA = {"User-Agent": "ScriptureBot corpus builder (a personal Discord bot)"}
SOURCES = {
    "Matthew": "https://ccel.org/ccel/a/aquinas/catena1.xml",
    "Mark": "https://ccel.org/ccel/a/aquinas/catena2.xml",
    "Luke": "https://isidore.co/aquinas/english/CALuke.htm",
    "John": "https://isidore.co/aquinas/english/CAJohn.htm",
}
CHAPTERS = {"Matthew": 28, "Mark": 16, "Luke": 24, "John": 21}

# The Fathers as the two copies write them (CCEL in full or shortened, typos and all; isidore.co in capitals)
NAMES = {
    "chrys": "Chrysostom", "chrysostom": "Chrysostom", "chyrs": "Chrysostom",
    "pseudo-chrys": "Pseudo-Chrysostom", "pseudo-chyrs": "Pseudo-Chrysostom", "psuedo-chrys": "Pseudo-Chrysostom",
    "jerome": "Jerome", "pseudo-jerome": "Pseudo-Jerome", "hier": "Jerome",
    "aug": "Augustine", "augustine": "Augustine", "pseudo-aug": "Pseudo-Augustine", "pseudo-augustine": "Pseudo-Augustine",
    "bede": "Bede", "remig": "Remigius", "remigius": "Remigius",
    "theophylact": "Theophylact", "theophlyact": "Theophylact", "theophyl": "Theophylact",
    "hilary": "Hilary", "hil": "Hilary", "origen": "Origen", "origin": "Origen", "pseudo-origen": "Pseudo-Origen",
    "raban": "Rabanus Maurus", "rabanus": "Rabanus Maurus", "greg": "Gregory the Great", "gregory": "Gregory the Great",
    "gloss": "The Gloss", "gloss. ord": "The Gloss", "gloss. ordinaria": "The Gloss", "gloss. interlin": "The Gloss",
    "gloss. ap. anselm": "The Gloss", "gloss. non occ": "The Gloss",
    "ambrose": "Ambrose", "leo": "Leo the Great", "cyprian": "Cyprian", "chrysol": "Peter Chrysologus",
    "chrysologus": "Peter Chrysologus", "severianus": "Severian", "cassian": "Cassian", "cyril": "Cyril of Alexandria",
    "cyril of alexandria": "Cyril of Alexandria", "haymo": "Haymo", "euseb": "Eusebius", "eusebius": "Eusebius",
    "isidore": "Isidore", "theodotus": "Theodotus", "ambrosiaster": "Ambrosiaster", "damascenus": "John Damascene",
    "damas": "John Damascene", "damascene": "John Damascene", "pseudo-athan": "Pseudo-Athanasius",
    "gennadius": "Gennadius", "the council of ephesus": "The Council of Ephesus", "alcuin": "Alcuin",
    "basil": "Basil", "pseudo-basil": "Pseudo-Basil", "greek ex": "A Greek Expositor",
    "greek expositor": "A Greek Expositor", "titus bost": "Titus of Bostra", "titus bostrensis": "Titus of Bostra",
    "greg nyss": "Gregory of Nyssa", "greg. nyss": "Gregory of Nyssa", "greg naz": "Gregory Nazianzen",
    "greg. naz": "Gregory Nazianzen", "athan": "Athanasius", "athanasius": "Athanasius", "maxim": "Maximus",
    "isidore peleus": "Isidore of Pelusium", "epiphan": "Epiphanius", "dionysius ar": "Dionysius the Areopagite",
    "ex gestis conc. eph": "The Council of Ephesus", "ex gestis concilii ephesini": "The Council of Ephesus",
}


def expect(ok, message):
    if not ok:
        raise SystemExit(f"unexpected source layout: {message}")


def _cp1252(err):
    return err.object[err.start:err.end].decode("cp1252", "replace"), err.end


def page(gospel: str) -> str:
    CACHE.mkdir(parents=True, exist_ok=True)
    url = SOURCES[gospel]
    f = CACHE / url.rsplit("/", 1)[1]
    if not f.exists():
        f.write_bytes(urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=180).read())
    codecs.register_error("cp1252-fallback", _cp1252)
    return f.read_bytes().decode("utf-8", "cp1252-fallback")


def text(markup: str) -> str:
    t = html.unescape(re.sub(r"(?s)<[^>]+>", "", markup)).replace("\xa0", " ")
    t = re.sub(r"\s*\[p \d+[”\"]\s*/(?:>|&gt;)", "", t)             # (a page mark's broken tag: "[p 223” />")
    t = t.replace("Esro1n", "Esrom")                               # (Luke 3:33's name, misread)
    t = re.sub(r"(?<=[a-z])1(?=[a-z])", "l", t)                    # (the scanner's "1" for "l": "indu1gence")
    return re.sub(r"\s+", " ", t).strip()


def father(prefix: str):
    """The Father a passage opens with ("Chrys., Hom. in Matt., Hom. ii" -> ("Chrysostom", "Hom. in Matt., Hom. ii")),
    or None if the words aren't a Father's name ("It goes on")."""
    p = prefix.strip()
    for key in sorted(NAMES, key=len, reverse=True):
        m = re.match(re.escape(key).replace(r"\.", r"\.?") + r"\.?(?=$|[,\s(])", p, re.I)
        if m:
            cite = p[m.end():].strip(" ,.")
            if key.startswith("gloss") and key != "gloss":                 # ("Gloss. interlin." -> the Gloss, interlin.)
                cite = (key[len("gloss"):].strip(" .") + (", " + cite if cite else "")).strip(", ")
            return NAMES[key], cite
    return None


def verses_key(spec: str) -> "tuple[int, int]":
    """"2-6" -> (2, 6); "1a" -> (1, 1); "18, 19" -> (18, 19)."""
    spec = spec.translate(str.maketrans("lIO", "110"))                   # (scanning slips: "3l." is 31)
    nums = [int(n) for n in re.findall(r"\d+", spec)]
    return nums[0], nums[-1]


# ── CCEL (Matthew, Mark) ────────────────────────────────────────────────────

def without_notes(t: str, depth: int) -> "tuple[str, int]":
    """A paragraph with the 1841 editors' notes taken out ("[ed. note: ...]", "[ed. note, h: Leah full of labour,
    Jerom. ...]"), their brackets matched (a note quotes Scripture in brackets); `depth` > 0 if a note left open in the
    paragraph before runs on into this one. Returns the text and the depth it leaves open."""
    out, i = [], 0
    while i < len(t):
        if depth == 0:
            found = [x for x in (t.find("[ed. note", i), t.find("[margin note", i)) if x >= 0]   # (and margin notes)
            j = min(found) if found else -1
            if j < 0:
                out.append(t[i:])
                break
            out.append(t[i:j])
            i, depth = j, 0
        c = t[i]
        if c == "[":
            depth += 1
        elif c == "]":
            depth -= 1
        i += 1
    return re.sub(r"\s+([,.;:])", r"\1", re.sub(r"\s{2,}", " ", "".join(out))).strip(), max(depth, 0)


def ccel(gospel: str) -> list:
    """[(chapter, first verse, last verse, the Gospel's words, [(Father, cite, text)])]."""
    src = page(gospel)
    out = []
    for chap in re.finditer(r'(?s)<div2\b[^>]*title="Chapter (\d+)"[^>]*>(.*?)</div2>', src):
        ch = int(chap[1])
        cur = None
        depth = 0
        for m in re.finditer(r'(?s)<p class="(scripture|normal)"[^>]*>(.*?)</p>', chap[2]):
            t = text(m[2])
            if m[1] == "scripture":
                depth = 0                                       # (a note never runs past a heading)
            else:
                t, depth = without_notes(t, depth)
            if not t:
                continue
            if m[1] == "scripture":
                # ("Ver. 1. The book...", "2. Abraham begat...", "Ver. 1: The beginning..."; a heading's next lines)
                # ("21, And in his name...", "65 Pilate said...": the stop a comma, or none)
                v = re.match(r"(?:Ver(?:se)?s?\.?\s*)?([\dlIO][\dlIO]*(?:\s*[-–]\s*[\dlIO][\dlIO]*|,\s*\d+(?=[.:]))*)"
                             r"(?:\s*[.:,]\s*|\s+(?=[“\"‘A-Z]))(.*)$", t) \
                    or re.match(r"\[(\d+(?:\s*[-–,]\s*\d+)*)\]\s*(.*)$", t)          # ("[30] And they shall see...")
                if not v:
                    expect(cur and not cur[4], f"{gospel} {ch}: verse heading {t[:50]!r}")
                    cur[3] += " " + t
                    continue
                cur = heading(out, cur, ch, v[1], v[2])
                continue
            expect(cur, f"{gospel} {ch}: comment before any verse: {t[:60]!r}")
            pm = re.match(r"([A-Z][A-Za-z.\- ]{1,40}?(?:,[^:]{0,140})?):\s+(.*)$", t)
            who = father(pm[1]) if pm else None
            if who:
                cur[4].append([who[0], who[1], pm[2]])
            elif cur[4]:
                cur[4][-1][2] += "\n" + t                               # (the same Father, or Aquinas's "It goes on")
            else:
                cur[4].append(["", "", t])
    return out


# ── isidore.co (Luke, John) ─────────────────────────────────────────────────

def isidore(gospel: str) -> list:
    src = page(gospel)
    out, ch, cur = [], 0, None
    # (the page in order: a chapter's heading, then for each passage its words in red, then the Fathers in bold)
    for m in re.finditer(r'(?is)<p\b[^>]*>(.*?)(?=<p\b|<hr|</body|$)', src):
        raw = m[1]
        t = text(raw)
        if not t:
            continue
        c = re.fullmatch(r"CHAPTER ([IVXL]+)", t)
        if c:
            ch = roman(c[1])
            continue
        if not ch:
            continue
        # (a passage's words are a paragraph in red; red inside a comment is the Gospel quoted)
        # ("1a.", "3-5.", and the slips "38 And she coming...", "l6. These things...")
        v = re.match(r"([\dlIO][\dlIO]*[a-z]?(?:\s*[-–,]\s*\d+[a-z]?)*)(?:\.\s*|\s+(?=[“\"‘A-Z]))(.*)$", t)
        if re.match(r"(?is)\s*(?:<span[^>]*>\s*)*?<span[^>]*(?:#ff0000|color:\s*red)", raw) and v \
                and "<b>" not in raw.lower():
            cur = heading(out, cur, ch, v[1], v[2])
            continue
        if cur is None or t in ("THE END",):
            continue
        # the Fathers run on in one paragraph, each opening with his name in bold: "<b>CHRYS</b>. While all..."
        parts = re.split(r"(?is)<b>\s*([^<]{1,40}?)\s*</b>\s*[.;:,]?", raw)
        if text(parts[0]):
            if cur[4]:
                cur[4][-1][2] += "\n" + text(parts[0])
            else:
                cur[4].append(["", "", text(parts[0])])
        for name, body in zip(parts[1::2], parts[2::2]):
            key = name.strip().rstrip(".").lower()
            if key in ("id", "idem"):                                   # ("ID.": the same Father again)
                who = cur[4][-1][0] if cur[4] else ""
            else:
                f = father(name)
                expect(f, f"{gospel} {ch}: who is {name!r}?")
                who = f[0]
            cur[4].append([who, "", text(body)])
    return out


def heading(out: list, cur, ch: int, spec: str, words: str) -> list:
    """A passage's heading: a new passage, or -- straight after another with no comment between ("1. Forasmuch...",
    "2. Even as...", "3.", "4.", then the Fathers on all four) -- the same passage, now covering this verse too."""
    first, last = verses_key(spec)
    if cur is not None and cur[0] == ch and not cur[4] and first > cur[2]:
        cur[2] = last
        cur[3] = (cur[3] + f" {spec}. " + words.strip()).strip()
        return cur
    cur = [ch, first, last, words.strip(), []]
    out.append(cur)
    return cur


def roman(s: str) -> int:
    vals = {"I": 1, "V": 5, "X": 10, "L": 50}
    n = 0
    for a, b in zip(s, s[1:] + " "):
        n += -vals[a] if b != " " and vals[a] < vals[b] else vals[a]
    return n


# ── the book ────────────────────────────────────────────────────────────────

def passage(gospel: str, ch: int, first: int, last: int, words: str, comments: list) -> str:
    where = f"{first}" if first == last else f"{first}–{last}"
    lines = [f"*{gospel} {ch}:{where}. {words}*" if words else f"*{gospel} {ch}:{where}.*"]
    for who, cite, body in comments:
        body = body.strip()
        if not body:
            continue
        if who:
            lines.append(f"**{who}**" + (f" ({cite})" if cite else "") + f": {body}")
        else:
            lines.append(body)
    return "\n".join(lines)


def main():
    books, spans = {}, {}
    for gospel in SOURCES:
        items = ccel(gospel) if gospel in ("Matthew", "Mark") else isidore(gospel)
        chapters = {}
        for ch, first, last, words, comments in items:
            verses = chapters.setdefault(str(ch), {})
            text_ = passage(gospel, ch, first, last, words, comments)
            if str(first) in verses:                                    # ("1a.", "1b.": one verse in parts)
                verses[str(first)] += "\n\n" + text_
            else:
                verses[str(first)] = text_
            if last > first:
                spans.setdefault(f"Catena Aurea on {gospel}", {})[f"{ch}:{first}"] = last
        expect(sorted(int(c) for c in chapters) == list(range(1, CHAPTERS[gospel] + 1)),
               f"{gospel}: chapters {sorted(int(c) for c in chapters)}")
        books[f"Catena Aurea on {gospel}"] = chapters
        print(f"  {gospel}: {len(items)} passages, {sum(len(c[4]) for c in items)} comments")
    data = {"source": "Thomas Aquinas, ed. J. H. Newman (1841–45)", "books": books, "spans": spans}
    OUT.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"-> {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
