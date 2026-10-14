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
    }


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
    opening = norm(" ".join(hymn["stanzas"][:2]))[:200].split() if hymn.get("stanzas") else []
    for latin in translations:
        words = latin.split()[:4] + NEXT_WORD.get(latin, [])
        if len(words) >= 3 and opening[:len(words)] == words:
            return latin
    return None


# Neale's titles too short to tell two hymns apart: the word that settles it
NEXT_WORD = {"pange lingua gloriosi": ["corporis"]}          # (his is Aquinas's, not Venantius's ...proelium)


def stanzas_like(lines: list, hymn: dict) -> list:
    """The English lines in stanzas like the Latin's, where they divide evenly; else one block."""
    count = len(hymn.get("stanzas", []))
    if count > 1 and len(lines) % count == 0:
        size = len(lines) // count
        return ["\n".join(lines[i:i + size]) for i in range(0, len(lines), size)]
    if len(lines) % 4 == 0 and len(lines) > 4:
        return ["\n".join(lines[i:i + 4]) for i in range(0, len(lines), 4)]
    return ["\n".join(lines)]


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
            continue
        latin = neale_match(h, neale_texts)
        if latin:
            out[h["title"]] = {"translator": "J. M. Neale", "source": NEALE_SOURCE,
                               "stanzas": stanzas_like(neale_texts[latin], h)}
            used.add(latin)
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
