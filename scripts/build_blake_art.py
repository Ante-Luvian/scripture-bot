"""
Builds data/blake/art.json: William Blake's illustrations to the Book of Job, Paradise Lost,
the Divine Comedy and The Pilgrim's Progress, each tied to the passage it shows, for the 🎨
Blake button under !verse and !blake <passage>. Only image addresses are stored.

  · Job: the 21 engravings (1826), from Wikipedia's table of them, which gives each plate's
    Commons file and the verse Blake engraved on it.
  · Paradise Lost: the Thomas set (1807), titled from Wikipedia's table; each design is tied to
    the passage it shows by finding a line of that scene in the bot's own Milton (SCENES).
  · The Pilgrim's Progress: the watercolours (1824-27) on Commons, tied the same way by a
    phrase found in the bot's own Bunyan.
  · The Divine Comedy: the watercolours (1824-27) whose Commons file name or description
    gives the canto.

    python scripts/build_blake_art.py
"""
import html
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
OUT = ROOT / "data" / "blake" / "art.json"
UA = {"User-Agent": "ScriptureBotCorpusBuilder/1.0 (Discord bot; low-volume one-off import)"}


def api(host: str = "commons.wikimedia.org", **params) -> dict:
    url = f"https://{host}/w/api.php?" + urllib.parse.urlencode({**params, "format": "json", "formatversion": 2})
    for attempt in range(8):
        try:
            data = json.loads(urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60).read())
            time.sleep(1.5)
            return data
        except Exception:
            time.sleep(30 * (attempt + 1))
    raise SystemExit(f"{host} kept refusing: {url}")


def file_info(titles: list) -> dict:
    out = {}
    for i in range(0, len(titles), 40):
        d = api(action="query", prop="imageinfo", iiprop="url|extmetadata", iiurlwidth=1000,
                titles="|".join(titles[i:i + 40]), redirects=1)
        back = {}
        for n in d["query"].get("normalized", []) + d["query"].get("redirects", []):
            back[n["to"]] = back.get(n["from"], n["from"])
        for p in d["query"]["pages"]:
            ii = (p.get("imageinfo") or [{}])[0]
            if ii:
                desc = (ii.get("extmetadata") or {}).get("ImageDescription", {}).get("value", "")
                out[back.get(p["title"], p["title"])] = {
                    "image": ii.get("thumburl") or ii["url"], "page": ii["descriptionurl"],
                    "desc": re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", desc))).strip()}
    return out


def wikitext(page: str) -> str:
    return api("en.wikipedia.org", action="parse", page=page, prop="wikitext")["parse"]["wikitext"]


def art(kind, n, title, book, chapter, start, end, info, cited=""):
    return {"set": kind, "n": str(n), "title": title, "book": book, "chapter": chapter, "start": start, "end": end,
            "cited": cited, "image": info["image"], "page": info["page"]}


def plain(s: str) -> str:
    s = re.sub(r"\{\{bibleverse\|\|(\w+)\|([\d:&ndash;–-]+)\|KJV\}\}", r"\1 \2", s)
    s = re.sub(r"\[\[(?:[^|\]]*\|)?([^\]]*)\]\]", r"\1", s)
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>|''+|&ndash;", " ", s)).strip()


# ── Job ─────────────────────────────────────────────────────────────────────

# The texts Blake engraved around each Job plate, read off the plates and checked against the KJV:
# {plate: [(chapter, first, last), ...]}, the main text (under the picture, or the scene) first.
# Wikipedia's table gives one verse per plate, not always one that's on it (plate 1: 1:5 for 1:1-5).
JOB_TEXTS = {
    1: [(1, 1, 5)], 2: [(1, 6, 8), (29, 5, 5), (19, 26, 26)], 3: [(1, 18, 19), (1, 12, 12), (1, 16, 16)],
    4: [(1, 14, 16), (1, 7, 7)], 5: [(2, 6, 7), (30, 25, 25)], 6: [(2, 7, 7), (1, 21, 21)],
    7: [(2, 12, 12), (2, 10, 10)], 8: [(3, 3, 3), (3, 7, 7), (2, 13, 13)], 9: [(4, 15, 15), (4, 17, 18)],
    10: [(12, 4, 4), (14, 1, 3), (23, 10, 10), (19, 21, 21), (13, 15, 15)],
    11: [(7, 14, 14), (19, 22, 27), (20, 5, 5), (30, 17, 17), (30, 30, 30)],
    12: [(32, 6, 6), (33, 14, 17), (33, 23, 24), (33, 29, 30), (34, 21, 21), (35, 5, 7)],
    13: [(38, 1, 2), (38, 28, 28)], 14: [(38, 7, 7), (38, 31, 31)],
    15: [(40, 15, 15), (41, 34, 34), (36, 29, 29), (37, 11, 12)], 16: [(36, 17, 17), (26, 6, 6), (11, 7, 8)],
    17: [(42, 5, 5)], 18: [(42, 8, 10)], 19: [(42, 11, 11), (38, 41, 41)], 20: [(42, 15, 15)],
    21: [(42, 12, 12), (42, 16, 17)],
}
# and the other books he quoted on them
JOB_ALSO = {2: ["Daniel 7:9", "Psalms 17:15", "Isaiah 63:16"], 5: ["Genesis 6:6", "Psalms 104:4"], 7: ["James 5:11"],
            11: ["2 Corinthians 11:14", "2 Thessalonians 2:4"], 13: ["Psalms 104:3"], 14: ["Genesis 1:3-25"],
            16: ["Revelation 12:10", "John 12:31", "Luke 10:17-18", "1 Corinthians 1:27"],
            17: ["1 John 3:2", "Psalms 8:3-4", "1 Samuel 2:6", "John 14:7-23", "John 10:30"], 18: ["Matthew 5:44-48"],
            19: ["1 Samuel 2:7", "Psalms 136:23"], 20: ["Psalms 139:8", "Psalms 139:17"],
            21: ["Revelation 15:3", "Hebrews 10:6"]}


def job() -> list:
    w = wikitext("William Blake's Illustrations of the Book of Job")
    rows = []
    for block in re.split(r"\n\|-\s*\n", w[w.index("{| class=\"wikitable\""):]):
        files = re.findall(r"\[\[File:([^|\]]+)", block)
        verse = re.search(r"\{\{bibleverse\|\|Job\|(\d+):(\d+)(?:&ndash;(?:\d+:)?(\d+))?", block)
        cells = [c for c in re.split(r"\n\|", "\n" + block) if c.strip()]
        title = next((plain(c) for c in cells if c.strip().startswith("''") and "File:" not in c), "")
        engraving = next((f for f in files if re.match(r"Blake Job A?\d+\.jpg", f)), None)
        if verse and engraving:
            rows.append((engraving, title, int(verse.group(1)), int(verse.group(2)),
                         int(verse.group(3) or verse.group(2))))
    expect(len(rows) >= 21, f"{len(rows)} Job plates")
    info = file_info([f"File:{r[0]}" for r in rows])
    out = []
    for i, (f, title, *_) in enumerate(rows, 1):
        if f"File:{f}" not in info:
            continue
        (ch, v1, v2), *more = JOB_TEXTS[i]
        a = art("job", i, title, "Job", ch, v1, v2, info[f"File:{f}"], f"Job {ch}:{v1}" + (f"-{v2}" if v2 != v1 else ""))
        a["passages"] = [list(t) for t in JOB_TEXTS[i]]
        a["also"] = JOB_ALSO.get(i, [])
        out.append(a)
    return out


# ── found in the bot's own texts ────────────────────────────────────────────

def _norm(s: str) -> str:
    return re.sub(r"[^a-z]", "", s.lower().replace("'d", "ed"))


def locate(book_data: dict, phrase: str):
    """(chapter, verse) of the first verse containing the phrase (spelling-insensitive), or None."""
    want = _norm(phrase)
    keys = sorted(book_data, key=lambda c: int(c))
    for c in keys:
        verses = book_data[c]
        nums = sorted((v for v in verses if v.isdigit()), key=int)
        joined = ""
        starts = []
        for v in nums:                                  # (a phrase may run over a line break)
            starts.append((len(joined), v))
            joined += _norm(verses[v])
        i = joined.find(want)
        if i >= 0:
            v = max((s for s in starts if s[0] <= i), key=lambda s: s[0])[1]
            return int(c), int(v)
    return None


# Blake's Paradise Lost designs (the Thomas set, 1807, numbered as Wikipedia's table) and a line of the
# scene each shows, as Beeching's edition spells it
SCENES = {
    1: ("Satan Arousing the Rebel Angels", "Awake, arise, or be for ever fall'n"),
    2: ("Satan, Sin, and Death: Satan Comes to the Gates of Hell", "Before the Gates there sat"),
    3: ("Christ Offers to Redeem Man", "Behold mee then, mee for him, life for life"),
    4: ("Raphael's Descent into Paradise", "Down thither prone in flight"),
    6: ("Raphael Warns Adam and Eve", "To whom the winged Hierarch repli'd"),
    7: ("The Rout of the Rebel Angels", "Nine dayes they fell"),
    8: ("The Creation of Eve", "Under his forming hands a Creature grew"),
    9: ("The Temptation and Fall of Eve", "she pluck'd, she eat"),
    10: ("The Judgment of Adam and Eve: \"So Judged He Man\"", "So judg'd he Man"),
    11: ("Michael Foretells the Crucifixion", "But to the Cross he nailes thy Enemies"),
    12: ("The Expulsion of Adam and Eve from the Garden of Eden", "They hand in hand with wandring steps and slow"),
}


def paradise_lost() -> list:
    pl = json.loads((ROOT / "data" / "medieval" / "milton.json").read_text(encoding="utf-8"))["books"]["Paradise Lost"]
    info = file_info([f"File:ParadiseLThomas{n}.jpg" for n in SCENES])
    out = []
    for n, (title, phrase) in SCENES.items():
        where = locate(pl, phrase)
        f = f"File:ParadiseLThomas{n}.jpg"
        if where is None or f not in info:
            print(f"  ✗ Paradise Lost design {n}: {'not found in the text' if where is None else 'no file'}")
            continue
        book, line = where
        out.append(art("pl", n, title, "Paradise Lost", book, line, line, info[f], f"Paradise Lost {book}:{line}"))
    return out


# Blake's Pilgrim's Progress watercolours on Commons, and a phrase of the scene each shows (Part One)
PILGRIM = {
    "William Blake - John Bunyan Plate 1 Dreamen Dreams a Dream.jpg": ("The Dreamer Dreams a Dream", "I laid me down in that place to sleep"),
    "William Blake - John Bunyan - Cristian Reading in His Book - Frick Collection New York.jpg": ("Christian Reading in His Book", "a Book in his hand, and a great Burden upon his back"),
    "William Blake - John Bunyan Plate 8 Christian Fears the Fire from the Mountain.jpg": ("Christian Fears the Fire from the Mountain", "flashes of fire out of the Hill"),
    "William Blake - John Bunyan - The Man Sweeping the Interprener's Parlour.jpg": ("The Man Sweeping the Interpreter's Parlour", "a very large Parlour that was full of dust"),
    "William Blake - John Bunyan - The Man in the Iron Cage.gif": ("The Man in the Iron Cage", "a man in an Iron Cage"),
    "William Blake - John Bunyan Plate 13 The Man Who Dreamed of the Day of Judgement.jpg": ("The Man Who Dreamed of the Day of Judgment", "This night as I was in my sleep, I dreamed"),
    "William Blake - John Bunyan Plate 17 The Christian at the Arbor.jpg": ("Christian at the Arbour", "Arbo"),      # (the arbour on the Hill Difficulty: "Arbor" here)
    "William Blake - John Bunyan Plate 20 The Christian Fights Apollyon.jpg": ("Christian Fights Apollyon", "Apollyon straddled quite over the whole breadth of the way"),
    # (Christian with the Shield of Faith is left out: the phrase finds a later conversation, not the scene)
    "William Blake - John Bunyan Plate 28 At the Gates of Heaven.jpg": ("At the Gates of Heaven", "Now when they were come up to the Gate"),
}


def pilgrims_progress() -> list:
    pp = json.loads((ROOT / "data" / "medieval" / "pilgrims_progress.json").read_text(encoding="utf-8"))["books"]["Pilgrim's Progress"]
    info = file_info([f"File:{f}" for f in PILGRIM])
    out = []
    for i, (f, (title, phrase)) in enumerate(PILGRIM.items(), 1):
        where = locate(pp, phrase)
        if where is None or f"File:{f}" not in info:
            print(f"  ✗ Pilgrim's Progress: {title}: {'not found in the text' if where is None else 'no file'}")
            continue
        c, v = where
        out.append(art("pp", i, title, "Pilgrim's Progress", c, v, v, info[f"File:{f}"], f"Pilgrim's Progress {c}:{v}"))
    return out


# ── the Bible ───────────────────────────────────────────────────────────────

# Blake's Bible paintings on Commons (most painted for Thomas Butts, 1799-1810) and a phrase of the
# scene each shows, found in the bot's King James text
BIBLE = [
    ("Blake jacobsladder.jpg", "Jacob's Ladder", "Genesis", "a ladder set up on the earth"),
    ("The Angel of the Divine Presence Clothing Adam and Eve with Coats of Skins, object 1 (Butlin 436).jpg",
     "The Angel of the Divine Presence Clothing Adam and Eve with Coats of Skins", "Genesis", "coats of skins"),
    ("The Body of Abel Found by Adam and Eve by William Blake c1826 Tate.jpg", "The Body of Abel Found by Adam and Eve",
     "Genesis", "rose up against Abel his brother, and slew him"),
    ("William Blake - Abraham and Isaac - Google Art Project.jpg", "Abraham and Isaac", "Genesis", "took the knife to slay his son"),
    ("William Blake - Joseph and Potiphar's Wife - Google Art Project.jpg", "Joseph and Potiphar's Wife", "Genesis",
     "caught him by his garment"),
    ("William Blake - Moses Receiving the Law - Google Art Project.jpg", "Moses Receiving the Law", "Exodus",
     "two tables of testimony"),
    ("William Blake Moses and the brazen serpent.jpg", "Moses Erecting the Brazen Serpent", "Numbers", "serpent of brass"),
    ("Blake The Blasphemer.jpg", "The Blasphemer", "Leviticus", "Bring forth him that hath cursed"),
    ("Mercy and Truth are Met Together, Righteousness and Peace Have Kissed Each Other, object 1 (Butlin 463).jpg",
     "Mercy and Truth Are Met Together", "Psalms", "Mercy and truth are met together"),
    ("Nativity by Blake.jpg", "The Nativity", "Luke", "brought forth her firstborn son"),
    ("The Baptism of Christ, 1803 (Butlin 475) Ashmolean Museum, Oxford.jpg", "The Baptism of Christ", "Matthew",
     "descending like a dove"),
    ("Christ Raising Jairus's Daughter, object 1 (Butlin 417).jpg", "Christ Raising Jairus's Daughter", "Mark", "Talitha cumi"),
    ("Christ in the House of Martha and Mary But Martha Was Cumbered About Much Serving (Butlin 489).jpg",
     "Christ in the House of Martha and Mary", "Luke", "cumbered about much serving"),
    ("The Woman Taken in Adultery but486 1 1 wc 100.jpg", "The Woman Taken in Adultery", "John", "without sin among you"),
    ("William Blake - The Parable of the Wise and Foolish Virgins - Google Art Project.jpg",
     "The Parable of the Wise and Foolish Virgins", "Matthew", "unto ten virgins"),
    ("William Blake - The Last Supper ca 1799.jpg", "The Last Supper", "Matthew", "one of you shall betray me"),
    ("Blake soldiers casting lots.jpg", "The Soldiers Casting Lots for Christ's Garments", "John",
     "for my vesture they did cast lots"),
    ("William Blake Christ Nailed to the Cross.jpg", "Christ Nailed to the Cross", "Luke", "there they crucified him"),
    ("William Blake - Christ in the Sepulchre, Guarded by Angels.jpg", "Christ in the Sepulchre, Guarded by Angels",
     "John", "two angels in white sitting"),
    ("The Four and Twenty Elders by W.Blake.jpg", "The Four and Twenty Elders Casting Their Crowns before the Throne",
     "Revelation", "four and twenty elders sitting"),
    ("William Blake - Death on a Pale Horse - Butlin 517.jpg", "Death on a Pale Horse", "Revelation", "behold a pale horse"),
    ("Angel of the Revelation (Book of Revelation, chapter 10) MET DT5424.jpg", "The Angel of the Revelation",
     "Revelation", "mighty angel come down from heaven, clothed with a cloud"),
    ("William Blake - The Great Red Dragon and the Woman Clothed with the Sun - Google Art Project.jpg",
     "The Great Red Dragon and the Woman Clothed with the Sun", "Revelation", "a woman clothed with the sun"),
    ("The number of the beast is 666 Philadelphia, Rosenbach Museum and Library.jpg", "The Number of the Beast Is 666",
     "Revelation", "six hundred threescore and six"),
    ("Whore-of-babylon-blake-1809.jpg", "The Whore of Babylon", "Revelation", "sit upon a scarlet coloured beast"),
    ("Angel Michael Binding Satan by W.Blake (c. 1805).jpg", "The Angel Michael Binding Satan", "Revelation",
     "laid hold on the dragon"),
    ("W.Blake - He Cast Him into the Bottomless Pit and Shut Him Up, c. 1800.jpg",
     "He Cast Him into the Bottomless Pit, and Shut Him Up", "Revelation", "cast him into the bottomless pit"),
    ("Blake The River of Life Tate Britain.jpg", "The River of Life", "Revelation", "a pure river of water of life"),
]


def bible() -> list:
    kjv = {}
    for name in ("kjv_canon.json",):
        kjv.update(json.loads((ROOT / "data" / "kjv" / name).read_text(encoding="utf-8"))["books"])
    info = file_info([f"File:{f}" for f, *_ in BIBLE])
    out = []
    for i, (f, title, book, phrase) in enumerate(BIBLE, 1):
        where = locate(kjv[book], phrase)
        if where is None or f"File:{f}" not in info:
            print(f"  ✗ Bible: {title}: {'not found in ' + book if where is None else 'no file'}")
            continue
        c, v = where
        out.append(art("bible", i, title, book, c, v, v, info[f"File:{f}"], f"{book} {c}:{v}"))
    return out


# ── Dante ───────────────────────────────────────────────────────────────────

ROMAN = {"i": 1, "v": 5, "x": 10, "l": 50, "c": 100}


def roman(s: str) -> int:
    s, total = s.lower(), 0
    for a, b in zip(s, s[1:] + " "):
        total += -ROMAN[a] if b != " " and ROMAN.get(b, 0) > ROMAN[a] else ROMAN[a]
    return total


PART = {"hell": "Inferno", "inferno": "Inferno", "inverno": "Inferno", "purgatory": "Purgatorio",
        "purgatorio": "Purgatorio", "paradise": "Paradiso", "paradiso": "Paradiso"}


def dante() -> list:
    files = [m["title"] for m in api(action="query", list="categorymembers", cmtype="file", cmlimit=500,
             cmtitle="Category:William Blake's illustrations to the Divine Comedy")["query"]["categorymembers"]]
    info = file_info(files)
    out, seen = [], set()
    for f in sorted(files):
        if f not in info:
            continue
        text = f + " " + info[f]["desc"]
        m = re.search(r"(?i)\b(Hell|Inferno|Inverno|Purgatory|Purgatorio|Paradise|Paradiso)\b,?\s*(?:Canto\s*)?"
                      r"([IVXLC]+|\d+)\b", text)
        if not m:
            continue
        part = PART[m.group(1).lower()]
        canto = int(m.group(2)) if m.group(2).isdigit() else roman(m.group(2))
        if not 1 <= canto <= (34 if part == "Inferno" else 33):
            continue
        title = re.sub(r"(?i)^File:|\.(jpe?g|png|gif|tif)$", "", f)
        title = re.sub(r"(?i)(Illustrations to Dante's Divine Comedy,? object \d+ Butlin [\d-]+\s*(?:recto\)?)?|"
                       r"Blake Dante |\bBlake\b|Hell|Inferno|Inverno|Canto|\b[IVXLC]+\b|\d+)", " ", title)
        title = re.sub(r",? from Dante's.*$|\b(LACMA|MET)\b.*$|\(.*?\)", "", title)
        title = re.sub(r"\s+", " ", title).strip(" -,.;&") or f"{part}, Canto {canto}"
        key = (part, canto, " ".join(re.findall(r"[a-z]+", title.lower())))       # (two impressions: one)
        if key in seen:
            continue
        seen.add(key)
        out.append(art("dante", len(out) + 1, title, part, canto, None, None, info[f], f"{part} {canto}"))
    return out


def expect(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"unexpected: {message}")


def main():
    OUT.parent.mkdir(parents=True, exist_ok=True)
    builders = {"job": job, "bible": bible, "pl": paradise_lost, "pp": pilgrims_progress, "dante": dante}
    only = sys.argv[1:]                     # (e.g. "job": rebuild that set, keep the rest of art.json)
    old = json.loads(OUT.read_text(encoding="utf-8"))["art"] if only and OUT.exists() else []
    sets = {k: (b() if not only or k in only else [a for a in old if a["set"] == k]) for k, b in builders.items()}
    for k, v in sets.items():
        print(f"  {k}: {len(v)}")
    OUT.write_text(json.dumps({"source": "William Blake's illustrations, from Wikimedia Commons",
                               "art": [a for v in sets.values() for a in v]}, ensure_ascii=False, indent=1),
                   encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
