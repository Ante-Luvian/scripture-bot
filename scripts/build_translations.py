"""
Builds data/hymns/translations.json: published English translations of the
Latin chants in more_hymns.json, keyed by the chant's title, for !hymn's
🇬🇧 English button. Only published, credited translations (the owner's rule):
chants with none stay Latin only.

    python scripts/build_translations.py

- The Book of Common Prayer (the 1662 texts, as printed in the Scottish
  Episcopal Church's 1912 Prayer Book, Project Gutenberg #29622): the Kyrie,
  Gloria, Creed, Sanctus and Agnus Dei for every setting of the Mass Ordinary;
  the Lord's Prayer; the Te Deum, Magnificat and Nunc dimittis.
- J. M. Neale, Mediaeval Hymns and Sequences (1867), on Wikisource: matched to
  a chant by its Latin first words.
"""
import html
import json
import re
import sys
import time
import unicodedata
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CACHE = Path(__file__).resolve().parent / ".cache"
CHANT = ROOT / "data" / "hymns" / "more_hymns.json"
OUT = ROOT / "data" / "hymns" / "translations.json"
UA = {"User-Agent": "ScriptureBotCorpusBuilder/1.0 (Discord bot; low-volume one-off import)"}
BCP_URL = "https://www.gutenberg.org/cache/epub/29622/pg29622.txt"
BCP_SOURCE = "The Book of Common Prayer (1662 text; Scottish Episcopal Church edition, 1912)"
NEALE_SOURCE = "J. M. Neale, Mediaeval Hymns and Sequences (1867)"


def norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s.lower().replace("æ", "ae").replace("œ", "oe"))
    s = "".join(c for c in s if not unicodedata.combining(c)).replace("j", "i").replace("coel", "cael")
    return re.sub(r"\s+", " ", re.sub(r"[^a-z ]", " ", s)).strip()


# ── the Prayer Book ─────────────────────────────────────────────────────────

def bcp_text() -> str:
    f = CACHE / "bcp1662" / "scottish.txt"
    if not f.exists():
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_bytes(urllib.request.urlopen(urllib.request.Request(BCP_URL, headers=UA), timeout=120).read())
    return f.read_text(encoding="utf-8").replace("\r\n", "\n")


def between(text: str, start: str, end: str) -> str:
    """From `start` to the end of `end`, either matched across line breaks."""
    def loose(s):
        return r"\s+".join(re.escape(w) for w in s.split())
    i = re.search(loose(start), text).start()
    j = re.compile(loose(end)).search(text, i).end()
    passage = re.sub(r"\[Margin Note:\][^\n]*\n?", "", text[i:j])
    passage = re.sub(r"_([^_]+)_", r"\1", passage)                         # italic marks
    paras = [re.sub(r" {2,}", " ", re.sub(r"\s*\n\s*", " ", p)).strip() for p in re.split(r"\n\s*\n", passage) if p.strip()]
    return "\n".join(paras)


def bcp_passages() -> dict:
    t = bcp_text()
    return {
        "kyrie": "Lord, have mercy upon us.\nChrist, have mercy upon us.\nLord, have mercy upon us."
                 if "Christ, have mercy upon us." in t and "Lord, have mercy upon us." in t else None,
        "gloria": between(t, "Glory be to God on high, and in earth peace", "glory of God the Father. Amen."),
        "credo": between(t, "I believe in one God the Father Almighty", "the life of the world to come. Amen."),
        "sanctus": between(t, "Holy, holy, holy, Lord God of hosts", "O Lord most high. Amen."),
        "agnus": between(t, "O Lamb of God: that takest away the sins of the world;",
                         "O Lamb of God: that takest away the sins of the world;\n\n_Have mercy upon us_."),
        "pater": between(t, "Our Father, which art in heaven", "deliver us from evil. Amen."),
        "te deum": between(t, "We praise thee, O God", "let me never be confounded."),
        "magnificat": between(t, "My soul doth magnify the Lord", "world without end. Amen."),
        "nunc dimittis": between(t, "Lord, now lettest thou thy servant depart", "world without end. Amen."),
        "media vita": between(t, "In the midst of life we are in death", "bitter pains of eternal death."),
    }


BCP_NOTES = {"media vita": "The Prayer Book's anthem at the grave; the chant's closing verse (In te speraverunt) isn't in it."}


def bcp_key(hymn: dict) -> "str | None":
    """Which Prayer Book text a chant takes, by what it is."""
    title, part = norm(hymn["title"]), hymn["topics"][0] if hymn.get("topics") else ""
    if part == "Mass Ordinary":
        for key, words in (("kyrie", "kyrie"), ("gloria", "gloria"), ("credo", "credo"), ("sanctus", "sanctus"),
                           ("agnus", "agnus")):
            if title.startswith(words):
                return key
        return None
    if title == "pater noster":
        return "pater"
    if title == "media vita":
        return "media vita"
    for key in ("te deum", "magnificat", "nunc dimittis"):
        if title.startswith(key) and not title.startswith("te deum patrem"):
            return key
    return None


# ── Neale ───────────────────────────────────────────────────────────────────

def wikisource(**params) -> dict:
    url = "https://en.wikisource.org/w/api.php?" + urllib.parse.urlencode({**params, "format": "json"})
    for attempt in range(6):
        try:
            data = json.loads(urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60).read())
            time.sleep(2.5)
            return data
        except Exception:
            time.sleep(30 * (attempt + 1))
    raise SystemExit(f"Wikisource kept refusing: {url}")


def neale() -> dict:
    """{normalised Latin first line: [English lines]}"""
    cache = CACHE / "wikisource_neale"
    cache.mkdir(parents=True, exist_ok=True)
    pages = [p["title"] for p in wikisource(action="query", list="allpages", aplimit=500,
                                             apprefix="Mediaeval Hymns and Sequences/")["query"]["allpages"]]
    out = {}
    for title in pages:
        f = cache / (re.sub(r"[^\w]+", "_", title)[:150] + ".html")
        if not f.exists():
            f.write_text(wikisource(action="parse", page=title, prop="text")["parse"]["text"]["*"], encoding="utf-8")
        t = re.sub(r"(?s)<style.*?</style>", "", f.read_text(encoding="utf-8"))
        t = re.sub(r'(?s)<span[^>]*class="pagenum[^"]*"[^>]*>.*?</span></span>', "", t)
        body = t[t.find('class="prp-pages-output"'):]
        body = re.sub(r"(?s)<div class=\"reflist.*", "", body)
        body = re.sub(r'(?s)<sup[^>]*class="reference".*?</sup>', "", body)
        body = re.sub(r"(?s)<div class=\"wst-size-block wst-smaller wst-smaller-block\">.*?</div>", "\n", body)
        text = html.unescape(re.sub(r"<[^>]+>", "", re.sub(r"<br\s*/?>|</p>|</div>", "\n", body)))
        lines = [l.strip() for l in text.split("\n") if l.strip() and not l.startswith('class="prp')]
        if len(lines) < 3:
            continue
        latin, english = lines[0].rstrip("."), lines[1:]
        out[norm(latin)] = english
    return out


def neale_match(hymn: dict, translations: dict) -> "str | None":
    """The Neale translation whose Latin title begins the chant (first words agree)."""
    # the chant's own opening words, not its title: "Pange lingua" is two different hymns
    # (Aquinas's ...gloriosi corporis, Venantius's ...gloriosi proelium), told apart at word four
    # sung syllables are hyphenated ("cru-cis"); a refrain may come first (O filii's "Alleluia")
    opening = norm(" ".join(hymn["stanzas"][:3]).replace("-", ""))[:300].split() if hymn.get("stanzas") else []
    while opening[:1] == ["alleluia"]:
        opening = opening[1:]
    for latin in translations:
        for begins in [latin] + ALSO_BEGINS.get(latin, []):
            words = begins.split()[:4] + NEXT_WORD.get(latin, [])
            if len(words) >= 3 and opening[:len(words)] == words:
                return latin
    return None


# Neale's titles too short to tell two hymns apart: the word that settles it
NEXT_WORD = {"pange lingua gloriosi": ["corporis"]}          # (his is Aquinas's, not Venantius's ...proelium)
# the same hymn, its opening words in another order in the chant books
ALSO_BEGINS = {"urbs beata ierusalem": ["urbs ierusalem beata dicta"]}


def stanzas_like(lines: list, hymn: dict) -> list:
    """The English lines in stanzas like the Latin's, where they divide evenly; else one block."""
    count = len(hymn.get("stanzas", []))
    if count > 1 and len(lines) % count == 0:
        size = len(lines) // count
        return ["\n".join(lines[i:i + size]) for i in range(0, len(lines), size)]
    if len(lines) % 4 == 0 and len(lines) > 4:
        return ["\n".join(lines[i:i + 4]) for i in range(0, len(lines), 4)]
    return ["\n".join(lines)]


# ── Wikipedia: translations its hymn articles print and credit to a named translator ──
# (chant titles, article, the English block's first words, translator, note, which stanzas).
# Each pairing checked against the chant's own Latin: the Urban VIII "En clara vox" is
# Caswall's (his doxology renders its "Virtus, honor, laus, gloria"); the older "Vox clara
# ecce intonat" is Neale's ("To the most high Parent" = "Summo Parenti"). The Tantum ergo is
# the last two stanzas of Caswall's Pange lingua.
WIKIPEDIA = [
    (["Te lucis ante terminum"], "Te lucis ante terminum", "Before the ending of the day", "J. M. Neale",
     "Translated from the older Latin text; the chant sings the 1632 revision.", None),
    (["Veni Creator Spiritus"], "Veni Creator Spiritus", "Come, Holy Ghost, Creator blest", "Edward Caswall",
     "As altered in The Lutheran Hymnal (1941).", None),
    (["Stabat Mater"], "Stabat Mater", "At the Cross her station keeping", "Edward Caswall", None, None),
    (["Victimae paschali", "Victimae Paschali laudes"], "Victimae paschali laudes", "Christ the Lord is risen today",
     "Jane E. Leeson", "A metrical paraphrase, made for singing.", None),
    (["Veni Sancte Spiritus et emitte"], "Veni Sancte Spiritus", "Come, Thou holy Paraclete", "J. M. Neale", None, None),
    (["Puer natus in Bethlehem"], "Puer natus in Bethlehem", "A Child is born in Bethlehem",
     "Hamilton Montgomerie MacGill (1876)", None, None),
    (["Adeste fideles"], "O Come, All Ye Faithful", "O come, all ye faithful", "Frederick Oakeley (1841)", None, None),
    (["Tantum ergo"], "Pange lingua gloriosi corporis mysterium", "Sing, my tongue, the Saviour's glory",
     "Edward Caswall", "The last two verses of his Pange lingua.", slice(-2, None)),
    (["Vox clara"], "Vox clara ecce intonat", "A thrilling voice by Jordan rings", "J. M. Neale", None, None),
    (["En clara vox", "En clara vox redarguit"], "Vox clara ecce intonat", "Hark! a thrilling voice is sounding",
     "Edward Caswall", None, None),
    (["Pange lingua gloriosi proelium", "Pange lingua… Praelium"], "Pange lingua gloriosi proelium certaminis",
     "Sing, my tongue, the glorious battle", "J. M. Neale", "Five of the hymn's verses.", None),
]


def wikipedia_text(title: str) -> str:
    f = CACHE / "wikipedia" / (re.sub(r"[^A-Za-z0-9]+", "_", title).strip("_") + ".wiki")
    if not f.exists():
        url = ("https://en.wikipedia.org/w/api.php?action=query&prop=revisions&rvprop=content&rvslots=main"
               "&format=json&formatversion=2&redirects=1&titles=" + urllib.parse.quote(title))
        page = json.loads(urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60).read())
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(page["query"]["pages"][0]["revisions"][0]["slots"]["main"]["content"], encoding="utf-8")
        time.sleep(1)
    return f.read_text(encoding="utf-8")


def clean_wikitext(block: str) -> str:
    block = re.sub(r"(?s)<ref[^>]*/>|<ref[^>]*>.*?</ref>", "", block)
    block = re.sub(r"\[\[(?:[^\]|]*\|)?([^\]]*)\]\]", r"\1", block)        # [[target|shown]] -> shown
    block = re.sub(r"(?m)^\s*'''[^']+'''\s*$", "", block)                    # a translator's name as a heading
    block = block.replace("'''", "").replace("''", "").replace("&nbsp;", " ")
    block = re.sub(r"(?m)^[ \t]*\d+\.?[ \t]+", "", block)                    # stanza numbers
    lines = [l.strip() for l in block.split("\n")]
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()


def wikipedia_block(article: str, start: str) -> list:
    """The stanzas of the <poem> in `article` whose English begins with `start`."""
    for m in re.finditer(r"(?s)<poem[^>]*>(.*?)</poem>", wikipedia_text(article)):
        text = clean_wikitext(m.group(1))
        if norm(text).startswith(norm(start)):
            return text.split("\n\n")
    raise SystemExit(f"No English block starting {start!r} in Wikipedia's {article!r}")


def main():
    chants = json.loads(CHANT.read_text(encoding="utf-8"))["hymns"]
    bcp = bcp_passages()
    neale_texts = neale()
    out, used = {}, set()
    for h in chants:
        if h.get("audio_kind") != "chant":
            continue
        key = bcp_key(h)
        if key and bcp.get(key):
            out[h["title"]] = {"translator": "The Book of Common Prayer", "source": BCP_SOURCE,
                               "stanzas": bcp[key].split("\n\n") if "\n\n" in bcp[key] else [bcp[key]]}
            if key in BCP_NOTES:
                out[h["title"]]["note"] = BCP_NOTES[key]
            continue
        latin = neale_match(h, neale_texts)
        if latin:
            out[h["title"]] = {"translator": "J. M. Neale", "source": NEALE_SOURCE,
                               "stanzas": stanzas_like(neale_texts[latin], h)}
            used.add(latin)
    titles = {h["title"] for h in chants if h.get("audio_kind") == "chant"}
    for chant_titles, article, start, translator, note, part in WIKIPEDIA:
        stanzas = wikipedia_block(article, start)
        for title in chant_titles:
            if title not in titles:
                raise SystemExit(f"WIKIPEDIA names a chant that isn't there: {title!r}")
            if title not in out:
                out[title] = {"translator": translator, "source": f"as printed in Wikipedia's article “{article}”",
                              "stanzas": stanzas[part] if part else stanzas}
                if note:
                    out[title]["note"] = note
    OUT.write_text(json.dumps({"about": "Published English translations of the Latin chants, by chant title "
                                        "(scripts/build_translations.py).", "translations": out},
                              ensure_ascii=False, indent=1), encoding="utf-8")
    by = {}
    for v in out.values():
        by[v["translator"]] = by.get(v["translator"], 0) + 1
    print(f"{len(out)} chants translated: {by}; Neale's not matched to a chant: "
          f"{sorted(set(neale_texts) - used)}")


if __name__ == "__main__":
    main()
