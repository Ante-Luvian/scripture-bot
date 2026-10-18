"""
Builds data/blake/plate_texts.json: the words on each plate of Blake's illuminated books in
data/blake/plates.json, so !blake can show a plate's text under it: {book: [plate 1's text, ...]}
("" for a plate that is all picture).

  · Songs of Innocence and of Experience: Wikisource's transcription of the very copy shown
    (copy Z, 1826, Library of Congress), one page per plate.
  · The prophetic books: the whole text, cut at the words where each plate begins and ends, read
    off the plates of the copies shown (PLATES below; a title page is given as engraved). The text
    is Wikisource's (Visions; America; Europe; Urizen, from copy G itself; Ahania), and for Thel
    the bot's own (Gutenberg, Blake's spelling), with its run-together lines broken where
    Sampson's edition breaks them. A few lines are added or mended where the plate shows
    otherwise (America's stern Bard, which only some copies have; typos: FIXES).

    python scripts/build_blake_texts.py
"""
import difflib
import html
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "blake" / "plate_texts.json"
UA = {"User-Agent": "ScriptureBotCorpusBuilder/1.0 (Discord bot; low-volume one-off import)"}

SONGS_INDEX = "Songs of Innocence and of Experience, copy Z, 1826 (Library of Congress).pdf/"
PAGES = {"visions": ["Visions of the Daughters of Albion"],
         "america": ["America a Prophecy/Preludium", "America a Prophecy/A Prophecy"],
         "europe": ["Europe a Prophecy", "Europe a Prophecy/Preludium", "Europe a Prophecy/A Prophecy"],
         "urizen": ["The Book of Urizen"], "ahania": ["The Book of Ahania"],
         "thel": ["Poetical works of William Blake (Sampson, 1913)/The Book of Thel"]}     # (Thel's lineation)
FIXES = [("secret palce", "secret place"), ("Of iron, form the dismal", "Of iron, from the dismal"),
         ("bones form the birth", "bones from the birth"), ("Ethinthus,,", "Ethinthus,"),
         ("they why should Thel", "then why should Thel")]

# Where each plate's words begin and end, read off the plates: None (no words), a string (a title
# page, as engraved), or (first words, last words[, lines to add]), found in order in the text. An end
# given as (words, n) runs n lines past the line holding them.
PLATES = {
    "thel": [
        ("Does the Eagle know", "Or Love in a golden bowl"),
        "THE BOOK of THEL\nThe Author & Printer Willm Blake. 1789.",
        ("The daughters of Mne Seraphim", "then why should Thel complain"),
        ("Why should the mistress of the vales of Har", "among the verdant grass"),
        ("O little Cloud the virgin said", "to find his partner in the vale"),
        ("Then Thel astonish", "and of itself is dark"),
        ("he that loves the lowly", "enter with thy virgin feet"),
        ("eternal gates terrific porter", "into the vales of Har"),
    ],
    "visions": [
        None,
        "VISIONS of the Daughters of Albion\nThe Eye sees more than the Heart knows.\nPrinted by Willm Blake: 1793.",
        ("The Argument", "My virgin mantle in twain"),
        ("Enslav", "worship terrors and obey the violent"),
        ("Now thou maist marry", "a morning of fresh tears"),
        ("none but Bromion can hear", "and upon what mountains"),
        ("Wave shadows of discontent", "Then Oothoon waited silent"),
        ("But when the morn arose", "pillar in the mouldering church"),
        ("a palace of eternity", "there my eyes are fix"),
        ("In happy copulation", "Does the sun walk in glorious raiment"),
        ("Where the cold miser", "eccho back her sighs"),
    ],
    "america": [
        None,
        "AMERICA a PROPHECY\nLAMBETH\nPrinted by William Blake in the year 1793.",
        ("shadowy daughter of Urthona", "hide thee from my sight"),
        ("Silent as despairing love", "the torment long foretold",
         "The stern Bard ceas'd, asham'd of his own song; enrag'd he swung\nHis harp aloft sounding, then dash'd "
         "its shining frame against\nA ruin'd pillar in glittring fragments; silent he turn'd away,\n"
         "And wander'd down the vales of Kent in sick & drear lamentings."),
        ("Guardian Prince of Albion burns", "and his glowing eyes"),
        ("Appear to the Americans upon the cloudy night", "trembles at the vision"),
        ("Albions Angel stood beside the Stone", "shook the temple"),
        ("The morning comes, the night decays", "Lion & Wolf shall cease"),
        ("In thunders ends the voice", "in this terrific form"),
        ("The terror answerd", "his breast and head like gold"),
        ("Sound! sound! my loud war", ("Thy mother lays her length", 2)),
        ("Fiery the Angels rose", "no more obedience pay"),
        ("So cried he, rending off his robe", "from North to South"),
        ("What time the thirteen Governors", "in the eastern sky"),
        ("In the flames stood", "rolld they back with fury"),
        ("On Albions Angels: then the Pestilence", "the tender grape appears"),
        ("Over the hills, the vales, the cities", "round the abodes of men"),
    ],
    "europe": [
        None,
        "EUROPE a PROPHECY\nLAMBETH\nPrinted by Will: Blake: 1794.",
        ("Five windows light the cavern", "dictated EUROPE"),
        ("nameless shadowy female rose", "prolific pains"),
        ("Unwilling I look up to heaven", ("rolld her shady clouds", 1)),
        "LORD HAVE MERCY ON US",
        None,
        ("The deep of winter came", "Awake the thunders of the deep"),
        ("The shrill winds wake", "the distant heavens reply"),
        ("Now comes the night of Enitharmons joy", "my bliss is yet but new"),
        ("Arise O Rintrah eldest born", "O Rintrah furious king"),
        ("Enitharmon slept", "terrors of struggling times"),
        ("In thoughts perturb", "dizzy enquirer to his grave"),
        ("Albions Angel rose upon the Stone of Night", "from North to South"),
        ("And the clouds & fires pale rolld round", "Heavens of Albion. Furious"),
        ("The red limb'd Angel seiz'd", "human solitude is past"),
        ("Ethinthus queen of waters", "beheld the morning in the east"),
        ("Shot from the heights of Enitharmon", "to the strife of blood"),
    ],
    "urizen": [
        ("PRELUDIUM TO THE", "dark visions of torment"),
        ("Lo, a shadow of horror", "myriads of Eternity"),
        None,
        ("In living creations appear", "For Eternity stood wide apart"),
        None,
        ("As the stars are apart from the earth", "Urizen is a clod of clay"),
        None,
        ("Los smitten with astonishment", "And these were the changes of Urizen"),
        None,
        ("Ages on ages roll", ("And a first Age passed over", 1)),
        ("From the caverns of his jointed Spine", ("In ghastly torment sick", 1)),
        None,
        ("Two Nostrils bent down to the deep", "Trembling upon the Void"),
        ("Thus the Eternal Prophet was divided", "globe of life blood trembling"),
        None,
        ("They call'd her Pity", "beat down the stakes"),
        ("Stretch'd for a work of eternity", "By cruel enormities"),
        None,
        ("Of life on his forsaken mountains", "life liv'd upon death"),
        None,
        ("The Ox in the slaughter house", ("No more could they rise at will", 2)),
        None,
        ("They lived a period of years", ("salt ocean rolled englob", 1)),
    ],
    "ahania": [
        None,
        "THE BOOK of AHANIA\nLAMBETH\nPrinted by W Blake 1795",
        ("CHAP: 1ST", "With the body of the sun"),
        ("But the forehead of Urizen gathering", "Brought his Books, all but the Book"),
        ("Of iron, from the dismal shade", "Whereon his bright feet have trod"),
        ("But I wander on the rocks", "Before they see the light"),
    ],
}


def api(**params) -> dict:
    url = "https://en.wikisource.org/w/api.php?" + urllib.parse.urlencode({**params, "format": "json", "formatversion": 2})
    for attempt in range(8):
        try:
            data = json.loads(urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60).read())
            time.sleep(1)
            return data
        except Exception:
            time.sleep(20 * (attempt + 1))
    raise SystemExit(f"Wikisource kept refusing: {url}")


def expect(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"unexpected: {message}")


# ── Songs: the transcription page by page ───────────────────────────────────

_INLINE = (r"(?:x*-?larger|x*-?smaller|larger|smaller|c|center|sc|small-caps|uc|lc|em|gap|smaller block|larger block|"
           r"nowrap|nop|right|left|sic|lps|spaced|letter-spacing|u|i|bold)")


def wikitext_lines(t: str) -> list:
    """A Wikisource page's transcription as lines (the plate's image and the page furniture dropped)."""
    t = re.sub(r"<noinclude>.*?</noinclude>|<ref[^>]*>.*?</ref>|<ref[^>]*/>", "", t, flags=re.S)
    t = re.sub(r"\[\[(?:File|Image):[^\[\]]*(?:\[\[[^\]]*\]\][^\[\]]*)*\]\]", "", t)
    t = re.sub(r"\{\{\s*(?:em|gap)[^{}]*\}\}", "", t)
    for _ in range(12):                                  # one-line templates, innermost first
        new = re.sub(r"\{\{\s*(?:hws|hwe)\s*\|([^{}|\n]*)\|[^{}\n]*\}\}", r"\1", t)
        new = re.sub(r"\{\{\s*" + _INLINE + r"\s*\|(?:\s*\d+=)?([^{}\n]*)\}\}",
                     lambda m: m.group(1).split("|")[-1], new, flags=re.I)
        new = re.sub(r"\{\{[^{}\n|]*\}\}", "", new)       # ({{dhr}}, {{center block/s}})
        if new == t:
            break
        t = new
    t = re.sub(r"\{\{\s*[A-Za-z /-]+\s*\|(?:\s*(?:title|width|image|x\d|y\d|item\d|1)\s*=[^|\n]*\|)*", "\n", t)
    t = re.sub(r"\|\s*item\d+\s*=", "\n", t)
    t = re.sub(r"^\s*\|\s*[a-z]+\d*\s*=.*$", "", t, flags=re.M)
    t = t.replace("{{", "").replace("}}", "\n")
    t = re.sub(r"<br\s*/?>[ \t]*\n?", "\n", t)
    t = re.sub(r"<[^>]+>", "", t)
    t = re.sub(r"\[\[(?:[^|\]]*\|)?([^\]]*)\]\]", r"\1", t).replace("'''", "").replace("''", "")
    out = []
    for line in t.splitlines():
        line = re.sub(r"\s+", " ", html.unescape(line)).strip(" :|")
        if re.fullmatch(r"\w+\s*=.*|\d+(?:\.\d+)?(?:em|px|%)", line):    # (template arguments left over)
            continue
        if line or (out and out[-1]):
            out.append(line)
    while out and not out[-1]:
        out.pop()
    while out and not out[0]:
        out.pop(0)
    return out


def songs() -> list:
    d = api(action="query", list="allpages", apprefix=SONGS_INDEX, apnamespace=104, aplimit=500)
    titles = sorted((p["title"] for p in d["query"]["allpages"]), key=lambda t: int(t.rsplit("/", 1)[1]))
    pages = {}
    for i in range(0, len(titles), 40):
        r = api(action="query", prop="revisions", rvprop="content", rvslots="main", titles="|".join(titles[i:i + 40]))
        for p in r["query"]["pages"]:
            pages[int(p["title"].rsplit("/", 1)[1])] = p["revisions"][0]["slots"]["main"]["content"]
    return ["\n".join(wikitext_lines(pages[n])) for n in sorted(pages)]


# ── the prophetic books: one text, cut at each plate ───────────────────────

CLUTTER = re.compile(r"^\[(?:Plate|plate)[^\]]*\]$|copy G, c\. 1818|^This work |^Public domain|source document|"
                     r"talk page|standardized|help pages|scan-backed|Match and split|^\[edit\]$|^CONTENTS:|"
                     r"^Inroduction \[|^\* \* \*$|^\|\}$|^THE END\.$")


def rendered_lines(page: str) -> list:
    h = api(action="parse", page=page, prop="text")["parse"]["text"]
    h = re.sub(r"<(script|style)[^>]*>.*?</\1>", "", h, flags=re.S)
    h = re.sub(r"<sup[^>]*>.*?</sup>", "", h, flags=re.S)
    h = re.sub(r"<br\s*/?>|</p>|</div>|</h\d>|</li>|</tr>", "\n", h)
    out = []
    for line in html.unescape(re.sub(r"<[^>]+>", "", h)).splitlines():
        line = re.sub(r"\s+", " ", line).strip()
        line = re.sub(r"\[(?:[a-z]|first|FIRST|the)\]\s?", "", line)          # (editors' marks and insertions)
        line = re.sub(r"^\d+\s?(?=[‘’'A-Za-z])", "", line)                     # (line numbers; not Blake's "1.")
        if line and not CLUTTER.search(line):
            out.append(line)
    return out


def _n(s: str) -> str:
    return re.sub(r"[^a-z]", "", s.lower())


def relineate(text: str, model_lines: list) -> str:
    """Break text's run-together lines where the model (the same poem, other spelling) breaks them."""
    words = [(m.start(), m.end(), _n(m.group())) for m in re.finditer(r"\S+", text)]
    model, ends = [], set()
    for line in model_lines:
        ws = [_n(w) for w in line.split() if _n(w)]
        model += ws
        if ws:
            ends.add(len(model) - 1)
    breaks = set()
    for blk in difflib.SequenceMatcher(None, model, [w[2] for w in words], autojunk=False).get_matching_blocks():
        breaks |= {blk.b + k for k in range(blk.size) if blk.a + k in ends}
    out, last = [], 0
    for i, (s, e, _) in enumerate(words):
        if i in breaks and i + 1 < len(words) and "\n" not in text[e:words[i + 1][0]]:
            out.append(text[last:e] + "\n")
            last = words[i + 1][0]
    out.append(text[last:])
    return "".join(out)


def cut(text: str, plates: list) -> list:
    letters, where = [], []
    for i, ch in enumerate(text.lower().replace("’", "'")):
        if ch.isalpha():
            letters.append(ch)
            where.append(i)
    letters = "".join(letters)
    cursor, out = 0, []
    for plate in plates:
        if plate is None or isinstance(plate, str):
            out.append(plate or "")
            continue
        start, end, *added = plate
        extra = 0
        if isinstance(end, tuple):
            end, extra = end
        s = letters.find(_n(start), cursor)
        expect(s >= 0, f"plate start not found: {start}")
        e = letters.find(_n(end), s)
        expect(e >= 0, f"plate end not found: {end}")
        a = text.rfind("\n", 0, where[s]) + 1
        b = text.find("\n", where[e + len(_n(end)) - 1])
        b = len(text) if b < 0 else b
        for _ in range(extra):
            nb = text.find("\n", b + 1)
            b = len(text) if nb < 0 else nb
        out.append(text[a:b].strip() + ("\n\n" + added[0] if added else ""))
        cursor = e + len(_n(end))
    return out


def fix(text: str) -> str:
    for wrong, right in FIXES:
        text = text.replace(wrong, right)
    return text


def prophetic(key: str) -> list:
    lines = [line for page in PAGES[key] for line in rendered_lines(page)]
    if key == "thel":                                   # the bot's own text, in Blake's spelling
        book = json.loads((ROOT / "data" / "medieval" / "blake.json").read_text(encoding="utf-8"))["books"]["The Book of Thel"]
        text = "\n".join(v for c in sorted(book, key=int) for _, v in sorted(book[c].items(), key=lambda kv: int(kv[0])))
        text = relineate(fix(re.sub(r"[ \t]+", " ", text.replace("*", ""))), lines)
    else:
        text = fix("\n".join(lines))
    return cut(text, PLATES[key])


def main():
    shown = json.loads((ROOT / "data" / "blake" / "plates.json").read_text(encoding="utf-8"))["illuminated"]
    out = {"songs": songs(), **{k: prophetic(k) for k in PLATES}}
    for key, texts in out.items():
        expect(key in shown and len(texts) == len(shown[key]["plates"]),
               f"{key}: {len(texts)} texts for {len(shown.get(key, {}).get('plates', []))} plates")
        print(f"  {shown[key]['title']}: {sum(bool(t) for t in texts)} of {len(texts)} plates have words")
    OUT.write_text(json.dumps({"source": "Wikisource transcriptions (Songs: copy Z); Thel: Project Gutenberg",
                               "texts": out}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    sys.exit(main())
