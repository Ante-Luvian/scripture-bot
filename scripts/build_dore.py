"""
Builds data/dore/plates.json: Gustave Doré's engravings for the Bible (Apocrypha included), the
Divine Comedy and Paradise Lost, each tied to the passage it illustrates, for !dore and the 🖼️
button on !verse. Only image addresses are stored; Discord shows the pictures from Wikimedia.

  · The Bible (241 plates, 1866). The Old Testament and Apocrypha are Commons' numbered series
    ("001.The Creation of Light.jpg" ... "152.", with "041A." etc.), whose descriptions give the
    title and reference ("The Creation of Light (Gen. 1:1-5)"). The New Testament follows the
    Russian Wikipedia list of all 241 plates ("Иллюстрации Гюстава Доре к Библии"), which names
    a Commons file for each; the English titles are translated from it.
  · The Divine Comedy (1861-68). The plates of the German edition of 1870-71 on Commons, each
    tied to its canto by Commons' "Gustave Doré - Inferno Canto NN" categories (the few without
    one were identified by eye: see CANTO). Those are photographs of whole pages, so each plate is
    shown from a clean copy elsewhere on Commons (CLEAN_COPIES) or cut out of its scan into
    data/dore/dante/ (see clean_dante).
  · Paradise Lost (1866). "Paradise Lost 1.jpg" ... "50.jpg", with the lines each one quotes, from
    the Wikisource transcription of the illustrated edition; the lines are found in the bot's own
    Milton, so the numbers agree with !verse Paradise Lost.

    python scripts/build_dore.py
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
sys.path.insert(0, str(ROOT))
OUT = ROOT / "data" / "dore" / "plates.json"
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


def members(category: str, kind: str = "file") -> list:
    out, cont = [], {}
    while True:
        d = api(action="query", list="categorymembers", cmtitle=category, cmtype=kind, cmlimit=500, **cont)
        out += [m["title"] for m in d["query"]["categorymembers"]]
        if "continue" not in d:
            return out
        cont = d["continue"]


def file_info(titles: list) -> dict:
    """{title: {"image", "page", "desc", "categories"}} (image 1000 px wide), following redirects."""
    out = {}
    for i in range(0, len(titles), 40):
        batch = titles[i:i + 40]
        d = api(action="query", prop="imageinfo|categories", iiprop="url|extmetadata", iiurlwidth=1000,
                cllimit=500, titles="|".join(batch), redirects=1)
        back = {}
        for n in d["query"].get("normalized", []) + d["query"].get("redirects", []):
            back[n["to"]] = back.get(n["from"], n["from"])
        for p in d["query"]["pages"]:
            ii = (p.get("imageinfo") or [{}])[0]
            if not ii:
                continue
            desc = (ii.get("extmetadata") or {}).get("ImageDescription", {}).get("value", "")
            out[back.get(p["title"], p["title"])] = {
                "image": ii.get("thumburl") or ii["url"], "page": ii["descriptionurl"],
                "desc": re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", desc))).strip(),
                "categories": [c["title"] for c in p.get("categories", [])]}
    return out


# ── the Bible ──────────────────────────────────────────────────────────────

CYRILLIC = str.maketrans("МАСЕаосерхТКН", "MACEaocepxTKH")


def parse_ref(text: str):
    """"Gen. 37:13-36" -> ("Genesis", 37, 13, 36), with the bot's book names; None if it can't be read."""
    m = re.match(r"^\s*((?:[1-4]\s?)?[A-Za-z][A-Za-z .]*?)\.?\s*(\d+):(\d+)(?:\s*[-–]\s*(?:(\d+):)?(\d+))?",
                 text.translate(CYRILLIC))
    if not m:
        return None
    name = re.sub(r"^([1-4])\s?", r"\1 ", m.group(1).strip().rstrip("."))         # "1Sam" -> "1 Sam"
    name = {"Is": "Isaiah", "Ez": "Ezekiel", "Est": "Esther", "2 King": "2 Kings", "1 King": "1 Kings",
            "Jud": "Judges", "Judg": "Judges"}.get(name, name)                      # (not Jude)
    book = LOOKUP._resolve_book(name)[1]
    if book is None:
        return None
    chapter, start = int(m.group(2)), int(m.group(3))
    end = int(m.group(5)) if m.group(5) and not m.group(4) else start
    if book == "Daniel" and chapter in (13, 14):          # the Greek chapters: Susanna, and Bel and the Dragon
        book, chapter = ("Susanna" if chapter == 13 else "Bel and the Dragon"), 1
    return book, chapter, start, max(end, start)


# the Russian list's New Testament plates: their English titles (translated) and references
NT = {
    161: ("The Wise Men Guided by the Star", "Matthew 2:1-2"), 162: ("The Flight into Egypt", "Matthew 2:13-14"),
    163: ("The Massacre of the Innocents", "Matthew 2:16"), 164: ("The Sermon on the Mount", "Matthew 5:7-10"),
    165: ("Jesus Healing a Dumb Man Possessed", "Matthew 12:22-25"), 166: ("Christ in the Synagogue", "Matthew 13:54"),
    167: ("The Daughter of Herodias Receives the Head of John the Baptist", "Matthew 14:8-10"),
    168: ("Christ Feeding the Multitude", "Matthew 14:19"), 169: ("Jesus Healing the Sick", "Matthew 15:31"),
    170: ("The Transfiguration", "Matthew 17:2-3"), 171: ("Jesus Healing the Lunatic", "Matthew 17:14-15"),
    172: ("The Entry of Jesus into Jerusalem", "Matthew 21:7-8"), 173: ("Christ and the Tribute Money", "Matthew 22:20-21"),
    174: ("Jesus Praying in the Garden", "Matthew 26:40-41"), 175: ("Jesus Scourged", "Matthew 27:26"),
    176: ("Christ Mocked", "Matthew 27:29-30"), 177: ("The Arrival at Calvary", "Matthew 27:33-34"),
    178: ("The Erection of the Cross", "Matthew 27:35"), 179: ("The Descent from the Cross", "Matthew 27:57-58"),
    180: ("The Dead Christ", "Matthew 27:59"), 181: ("The Burial of Christ", "Matthew 27:60-61"),
    182: ("The Resurrection", "Matthew 28:5-6"), 183: ("John the Baptist Preaching in the Wilderness", "Mark 1:6-7"),
    184: ("The Baptism of Jesus", "Mark 1:9-11"), 185: ("The Disciples Plucking Corn on the Sabbath", "Mark 2:23-25"),
    186: ("Jesus Stilling the Tempest", "Mark 4:37-38"), 187: ("Christ Blessing the Little Children", "Mark 10:13-14"),
    188: ("The Widow's Mite", "Mark 12:42-43"), 189: ("The Last Supper", "Mark 14:22-24"),
    190: ("The Judas Kiss", "Mark 14:45-46"), 191: ("Jesus Falling beneath the Cross", "Mark 15:21"),
    192: ("The Ascension", "Mark 16:19"), 193: ("The Annunciation", "Luke 1:26-28"), 194: ("The Nativity", "Luke 2:15-16"),
    195: ("Jesus Questioning the Doctors", "Luke 2:46-47"), 196: ("The Temptation of Jesus", "Luke 4:7-8"),
    197: ("Jesus Healing the Man Possessed with a Devil", "Luke 4:36-37"),
    198: ("Jesus Preaching at the Sea of Galilee", "Luke 5:3"), 199: ("Mary Magdalene Repentant", "Luke 8:2"),
    200: ("The Daughter of Jairus Raised", "Luke 8:52-54"), 201: ("The Good Samaritan", "Luke 10:33"),
    202: ("The Good Samaritan Arriving at the Inn", "Luke 10:34-35"),
    203: ("Jesus in the House of Martha and Mary", "Luke 10:41-42"), 204: ("Jesus Preaching to the Multitude", "Luke 12:29-31"),
    205: ("The Prodigal Son Resolves to Return", "Luke 15:17"), 206: ("The Return of the Prodigal Son", "Luke 15:20-21"),
    207: ("Lazarus at the Rich Man's House", "Luke 16:20-21"), 208: ("The Pharisee and the Publican", "Luke 18:11-13"),
    209: ("The Agony in the Garden", "Luke 22:43-44"), 210: ("The Crucifixion", "Luke 23:34-35"),
    211: ("The Darkness at the Crucifixion", "Luke 23:44-45"), 212: ("The Journey to Emmaus", "Luke 24:26-27"),
    213: ("The Marriage in Cana", "John 2:5-7"), 214: ("The Buyers and Sellers Driven out of the Temple", "John 2:15"),
    215: ("Jesus and the Woman of Samaria", "John 4:13-14"), 216: ("Jesus Walking on the Sea", "John 6:19-20"),
    217: ("Jesus and the Woman Taken in Adultery", "John 8:3-5"), 218: ("The Resurrection of Lazarus", "John 11:41-43"),
    219: ("St Peter Denying Christ", "John 18:26-27"), 220: ("The Crown of Thorns", "John 19:2-3"),
    221: ("Christ Presented to the People", "John 19:15"), 222: ("Jesus Nailed to the Cross", "John 19:18-19"),
    223: ("The Miraculous Draught of Fishes", "John 21:10-11"), 224: ("The Descent of the Spirit", "Acts 2:2-3"),
    225: ("The Apostles Preaching the Gospel", "Acts 2:32-33"), 226: ("Peter and John at the Beautiful Gate", "Acts 3:6-7"),
    227: ("The Death of Ananias", "Acts 5:4-5"), 228: ("The Martyrdom of St Stephen", "Acts 7:59-60"),
    229: ("The Conversion of Saul", "Acts 9:3-5"), 230: ("St Peter in the House of Cornelius", "Acts 10:28"),
    231: ("St Peter Delivered from Prison", "Acts 12:7-8"), 232: ("St Paul at Ephesus", "Acts 19:19"),
    233: ("St Paul Rescued from the Multitude", "Acts 21:34-35"), 234: ("St Paul Shipwrecked", "Acts 27:43-44"),
    235: ("St Paul Preaching to the Thessalonians", "1 Thessalonians 2:11-12"), 236: ("St John at Patmos", "Revelation 1:9"),
    237: ("Death on the Pale Horse", "Revelation 6:7-8"), 238: ("The Crowned Virgin: A Vision of John", "Revelation 12:1-3"),
    239: ("Babylon Fallen", "Revelation 18:2"), 240: ("The Last Judgment", "Revelation 20:12"),
    241: ("The New Jerusalem", "Revelation 21:1-2"),
}


def readable_ref(cited: str):
    """The first part of a caption's reference that the bot's Bible has ("Josh. 5:16, 6:1-10": 5:16 is
    only in the Latin numbering, so 6:1-10)."""
    ref = parse_ref(cited)
    if ref and LOOKUP.get_verse(f"{ref[0]} {ref[1]}:{ref[2]}").get("found"):
        return ref
    book = ref[0] if ref else None
    for part in re.findall(r"(\d+):(\d+)(?:\s*[-–]\s*(\d+))?", cited)[1:]:
        if book and LOOKUP.get_verse(f"{book} {part[0]}:{part[1]}").get("found"):
            return book, int(part[0]), int(part[1]), int(part[2] or part[1])
    return None


# plates whose Commons files give no reference: the Russian list's
NO_DESCRIPTION = {"003": "Gen. 3:24", "004": "Gen. 4:3-5", "005": "Gen. 4:8-9", "007": "Gen. 8:3-4",
                  "024": "Gen. 32:24", "112": "Judith 13:8", "123": "Jer. 1:14-15"}


def bible() -> list:
    plates, seen = [], set()
    # the Old Testament and Apocrypha: the numbered series
    cats = ["Category:Doré's English Bible", "Category:Art depicting the Old Testament by Gustave Doré"]
    files = set()
    for cat in cats:
        files |= set(members(cat))
        for sub in members(cat, "subcat"):
            files |= set(members(sub))
    series = {}
    for f in files:
        m = re.match(r"^File:(\d{3}[A-Z]?)\.\s*(.*?)(?:\s*\((?:retusche|cropped)\))?\.(jpg|jpeg|png)$", f, re.I)
        if m and int(m.group(1)[:3]) <= 152 and "retusche" not in f.lower():
            series.setdefault((m.group(1), m.group(2).strip()), f)
    info = file_info(sorted(series.values()))
    for (num, title), f in sorted(series.items()):
        desc = info.get(f, {}).get("desc", "")
        m = re.search(r"\(([^()]*\d+:\d+[^()]*)\)", desc)
        cited = m.group(1) if m else NO_DESCRIPTION.get(num)
        ref = parse_ref(cited) if cited else None
        if ref is None:
            print(f"  ✗ no reference for {f}: {desc[:80]}")
            continue
        plates.append(plate("bible", num, title, ref, info[f], cited))
    # the New Testament: the Russian list's files
    w = api("ru.wikipedia.org", action="parse", page="Иллюстрации Гюстава Доре к Библии", prop="wikitext")["parse"]["wikitext"]
    nt_files = {}
    for block in re.split(r"\n\|-\s*\n", w):
        n = re.search(r"<small>\s*(\d+)\s*</small>", block)
        f = re.search(r"\[\[(?:File|Файл|Изображение):([^|\]]+)", block)
        if n and f and int(n.group(1)) in NT:
            nt_files[int(n.group(1))] = "File:" + f.group(1).strip().replace("_", " ")
    expect(len(nt_files) == len(NT), f"{len(nt_files)} of {len(NT)} New Testament plates in the Russian list")
    info = file_info(list(nt_files.values()))
    for n, f in sorted(nt_files.items()):
        title, ref = NT[n]
        parsed = parse_ref(ref)
        if f not in info or parsed is None:
            print(f"  ✗ {n} {title}: {f} not found on Commons")
            continue
        plates.append(plate("bible", f"{n}", title, parsed, info[f], ref))
    return plates


def plate(kind: str, num: str, title: str, ref: tuple, info: dict, cited: str = "") -> dict:
    book, chapter, start, end = ref
    return {"set": kind, "n": num, "title": title, "book": book, "chapter": chapter, "start": start, "end": end,
            "cited": cited, "image": info["image"], "page": info["page"]}


# ── the Divine Comedy ──────────────────────────────────────────────────────

GERMAN = {"Inferno": "Category:Göttliche Komödie. T. 1, Die Hölle (1870)",
          "Purgatorio": "Category:Göttliche Komödie. T. 2, Das Fegefeuer (1871)",
          "Paradiso": "Category:Göttliche Komödie. T. 3, Das Paradies (1871)"}
# scans Commons hasn't put in a canto's category, identified by eye (Inferno; by scan number)
CANTO = {"148618558": 10, "148618573": 11, "148618608": 12, "148618629": 12, "148618643": 12, "148618661": 13,
         "148619488": 31, "148619513": 31, "148619530": 32, "148619564": 32, "148619571": 33, "148619672": 34}
TITLE_PAGES = {"148974060", "148199729", "148617969"}
PORTRAIT = "148617962"
DANTE_TITLES = {"Inferno": "Inferno", "Purgatorio": "Purgatorio", "Paradiso": "Paradiso"}


def dante() -> list:
    plates, twins = [], cantos_from_twins()
    for part, cat in GERMAN.items():
        files = [f for f in members(cat) if f.startswith("File:Gottliche Komodie")]
        info = file_info(files)
        n = 0
        for f in sorted(files, key=lambda f: int(re.search(r"\((\d+)\)", f).group(1))):
            sid = re.search(r"\((\d+)\)", f).group(1)
            if sid in TITLE_PAGES or f not in info:
                continue
            if sid == PORTRAIT:
                plates.append({"set": "dante", "n": "portrait", "title": "Dante Alighieri", "book": None, "chapter": None,
                               "start": None, "end": None, "cited": "", **{k: info[f][k] for k in ("image", "page")}})
                continue
            # (twins of this scan elsewhere on Commons carry the canto category too)
            cantos = [int(m.group(1)) for c in info[f]["categories"]
                      for m in [re.search(rf"{part} Canto (\d+)", c)] if m]
            canto = cantos[0] if cantos else twins.get((part, sid)) or CANTO.get(sid)
            if canto is None:
                print(f"  ✗ {part}: no canto for {f}")
                continue
            n += 1
            plates.append(plate("dante", f"{part[:3].lower()}{n}", f"{part}, Canto {canto}",
                                (part, canto, 1, 1), info[f], f"{part} {canto}"))
        print(f"  {part}: {n} plates")
    return plates


# The German scans are whole book pages (margins, binding, the page edge), so each plate is shown
# instead from a clean copy on Commons where one is bigger than the crop below (found by matching
# the pictures, checked by eye), and otherwise as the engraving cut out of its scan, saved in
# data/dore/dante/ (not in git: rebuilt by this script, ~30 MB; without it the bot shows the scan).
CLEAN_COPIES = {
    "148618027": "Dante lost in the dark forest, illustration to Dante’s Inferno by Gustave Doré.jpg",
    "148618051": "Inferno Canto 1 - Leopard (148618051).jpg",
    "148618067": "Gustave Doré - Dante Alighieri - Inferno - Plate 3 (The lion).jpg",
    "148618079": "Gustave Doré - Dante Alighieri - Inferno - Plate 4 (Dante meets Virgil).jpg",
    "148618085": "Gustave Doré - Dante Alighieri - Inferno - Plate 5 (End of Canto I).jpg",
    "148618089": "Gustave Doré - Dante Alighieri - Inferno - Plate 6 (Start of Canto II - Day was departing).jpg",
    "148618104": "Gustave Doré - Dante Alighieri - Inferno - Plate 7 (Beatrice).jpg",
    "148618126": "Gustave Doré - Dante Alighieri - Inferno - Plate 8 (Canto III - Abandon all hope ye who enter here).jpg",
    "148618170": "DVinfernoDoomedSoulsCrossAcheron.jpg",
    "148618192": "Gustave Doré - Dante Alighieri - Inferno - Plate 11 (Canto IV - Limbo, the Viruous Pagans).jpg",
    "148618206": "Gustave Doré - Dante Alighieri - Inferno - Plate 12 (Canto IV - Limbo, Dante is accepted as an equal by the great Greek and Roman poets).jpg",
    "148618228": "Gustave Doré - Dante Alighieri - Inferno - Plate 13 (Canto V - Minos).jpg",
    "148618250": "Francesca da Rimini and Paolo among the lustful, carried by the infernal whirlwind, illustration to Dante’s Inferno by Gustave Doré.jpg",
    "148618265": "Gustave Doré - Dante Alighieri - Inferno - Plate 15 (Canto V - Francesca di Rimini).jpg",
    "148618301": "Gustave Doré - The Inferno, Canto 5-2.jpg",
    "148618330": "Inferno Canto 6 (148618330).jpg",
    "148618401": "Gustave Doré - Dante Alighieri - Inferno - Plate 22 (Canto VII - Hoarders and Wasters).png",
    "148618415": "DVinfernoVirgilShowSoulsOfWrathful m.jpg",
    "148618431": "Inferno Canto 08 - Styx (148618431).jpg",
    "148618496": "DVinfernoMegaeraTisifphoneAlecto m.jpg",
    "148618558": "Dore woodcut Divine Comedy 01.jpg",
    "148618629": "Gustave Doré - The Inferno, Canto 12-1.jpg",
    "148618661": "DVinfernoForestOfSuicides m.jpg",
    "148618667": "Gustave Doré - The Inferno, Canto 13.jpg",
    "148618679": "DVinfernoViolentInRainOfFire m.jpg",
    "148618685": "Inferno Canto 15 (148618685).jpg",
    "148618710": "DVinfernoShadeOfThais m.jpg",
    "148618830": "DVinfernoCiampoloDemonAlichino m.jpg",
    "148618926": "DVinfernoHypocritesAddressDante m.jpg",
    "148619014": "Inferno Canto 24 (148619014).jpg",
    "148619071": "DVinfernoAgnelloChangingIntoSerpent m.jpg",
    "148619179": "Mohammed (148619179).jpg",
    "148619246": "DVinfernoSeveredHeadOfBertranddeBorn m.jpg",
    "148619272": "DVinfernoVirgilReprovesDantesCuriosity m.jpg",
    "148619488": "Gustave Doré - Dante Alighieri - Inferno - Plate 65 (Canto XXXI - The Titans).png",
    "148619513": "DVinfernoGiantAntaeusLoweringDanteAndVirgil m.jpg",
    "148619555": "Inferno Canto 32 (148619555).jpg",
    "148619564": "DVinfernoUgolinoGnawingHeadOfRuggieari m.jpg",
    "148619628": "Inferno Canto 34 (148619628).jpg",
}
# The lines each plate shows, in the numbering of the bot's Dante (Longfellow's, line for line with
# the Italian): {scan: (canto, first line, last line)}. Found where Gutenberg's illustrated Cary
# (#8789, #8795, #8799) prints or places each plate, carried over to Longfellow, and every one checked
# against a printed caption -- Hell's in the Cassell edition (Cary's numbers), Purgatory's and
# Paradise's in the Italian edition of the Biblioteca Classica Illustrata (the Italian numbers) -- or,
# where those disagree (Purgatorio 1), against the picture. (Purgatorio 9:1, Aurora, was in Commons'
# canto 8 category.)
DANTE_LINES = {
    "148199779": (3, 16, 18),
    "148199795": (5, 103, 105),
    "148199820": (8, 58, 60),
    "148199891": (12, 19, 21),
    "148199950": (14, 82, 84),
    "148199966": (14, 103, 105),
    "148200021": (16, 145, 147),
    "148200062": (18, 82, 87),
    "148200085": (18, 124, 126),
    "148200104": (19, 1, 3),
    "148200138": (20, 10, 12),
    "148200170": (21, 1, 3),
    "148200204": (21, 40, 42),
    "148200292": (26, 7, 9),
    "148200320": (27, 1, 3),
    "148200346": (28, 88, 90),
    "148200393": (31, 1, 3),
    "148200440": (31, 133, 135),
    "148618027": (1, 1, 3),
    "148618051": (1, 31, 33),
    "148618067": (1, 46, 48),
    "148618079": (1, 91, 93),
    "148618085": (1, 136, 136),
    "148618089": (2, 1, 3),
    "148618104": (2, 70, 72),
    "148618126": (3, 7, 9),
    "148618170": (3, 115, 117),
    "148618192": (4, 40, 42),
    "148618206": (4, 94, 96),
    "148618228": (5, 4, 6),
    "148618250": (5, 31, 33),
    "148618265": (5, 73, 75),
    "148618279": (5, 106, 108),
    "148618301": (5, 136, 138),
    "148618330": (6, 25, 27),
    "148618352": (6, 49, 51),
    "148618374": (7, 7, 9),
    "148618401": (7, 64, 66),
    "148618415": (7, 115, 117),
    "148618431": (8, 28, 30),
    "148618452": (8, 40, 42),
    "148618466": (8, 112, 114),
    "148618496": (9, 46, 48),
    "148618511": (9, 88, 90),
    "148618533": (9, 127, 129),
    "148618558": (10, 40, 42),
    "148618573": (11, 4, 9),
    "148618608": (12, 10, 12),
    "148618629": (12, 61, 63),
    "148618643": (12, 76, 78),
    "148618661": (13, 10, 12),
    "148618667": (13, 31, 33),
    "148618673": (13, 118, 120),
    "148618679": (14, 40, 42),
    "148618685": (15, 28, 30),
    "148618698": (17, 7, 9),
    "148618706": (17, 121, 123),
    "148618710": (18, 133, 135),
    "148618716": (19, 49, 51),
    "148618726": (18, 37, 39),
    "148618732": (18, 118, 120),
    "148618760": (21, 52, 54),
    "148618780": (21, 70, 72),
    "148618830": (22, 124, 126),
    "148618853": (22, 139, 141),
    "148618897": (23, 52, 54),
    "148618926": (23, 91, 93),
    "148618970": (23, 115, 117),
    "148619014": (24, 91, 93),
    "148619071": (25, 67, 69),
    "148619124": (26, 46, 48),
    "148619179": (28, 28, 33),
    "148619207": (28, 73, 75),
    "148619246": (28, 121, 123),
    "148619272": (29, 4, 6),
    "148619313": (29, 55, 57),
    "148619342": (29, 82, 84),
    "148619397": (30, 31, 33),
    "148619425": (30, 37, 39),
    "148619471": (31, 70, 72),
    "148619488": (31, 91, 93),
    "148619513": (31, 142, 144),
    "148619530": (32, 19, 21),
    "148619555": (32, 97, 99),
    "148619564": (32, 130, 132),
    "148619571": (33, 64, 66),
    "148619575": (33, 67, 69),
    "148619585": (33, 73, 75),
    "148619628": (34, 19, 21),
    "148619672": (34, 133, 135),
    "148619695": (34, 139, 139),
    "148974097": (1, 19, 21),
    "148974123": (1, 49, 51),
    "148974150": (2, 28, 30),
    "148974163": (2, 43, 45),
    "148974172": (3, 58, 60),
    "148974180": (4, 31, 33),
    "148974184": (4, 103, 105),
    "148974193": (5, 43, 45),
    "148974251": (5, 124, 126),
    "148974278": (5, 133, 135),
    "148974286": (7, 22, 24),
    "148974292": (7, 82, 84),
    "148974300": (8, 106, 108),
    "148974325": (9, 1, 3),
    "148974358": (9, 31, 33),
    "148974378": (9, 79, 81),
    "148974417": (10, 82, 84),
    "148974464": (12, 1, 3),
    "148974491": (12, 43, 45),
    "148974537": (13, 61, 63),
    "148974581": (13, 130, 132),
    "148974648": (15, 106, 108),
    "148974683": (16, 25, 27),
    "148974730": (16, 34, 36),
    "148974835": (18, 88, 90),
    "148974906": (19, 52, 54),
    "148974959": (19, 133, 135),
    "148974996": (20, 16, 18),
    "148975153": (23, 52, 54),
    "148975200": (24, 4, 6),
    "148975239": (24, 112, 114),
    "148975289": (25, 112, 114),
    "148975326": (25, 121, 123),
    "148975345": (25, 124, 126),
    "148975403": (27, 97, 99),
    "148975446": (28, 22, 24),
    "148975531": (29, 82, 84),
    "148975583": (29, 121, 126),
    "148975620": (30, 28, 33),
    "148975643": (31, 100, 102),
    "148975659": (32, 151, 153),
    "148975676": (33, 136, 138),
}
# two Hell plates the German scans lack: clean copies elsewhere on Commons
NOT_SCANNED = [("Inferno", 3, 82, 84, "Gustave Doré - Dante Alighieri - Inferno - Plate 9 (Canto III - Charon).jpg"),
               ("Inferno", 5, 139, 142, "Gustave Doré - Dante Alighieri - Inferno - Plate 18 (Canto V - Dante has a touch of the vapours).jpg")]
CROPS = ROOT / "data" / "dore" / "dante"


def engraving_box(img) -> tuple:
    """The engraving on a scanned page: the biggest area darker than the paper that doesn't touch
    the edge of the scan (the binding and the table it lies on do)."""
    import numpy as np
    from scipy import ndimage
    a = np.asarray(img, dtype=float)
    mean = ndimage.uniform_filter(a, 9)
    texture = np.sqrt(np.maximum(ndimage.uniform_filter(a * a, 9) - mean * mean, 0))   # (the engraver's lines)
    mask = (mean < np.percentile(a, 92) - 30) | (texture > 12)
    mask = ndimage.binary_closing(ndimage.binary_opening(mask, iterations=3), iterations=6)
    mask = ndimage.binary_fill_holes(mask)
    lab, _ = ndimage.label(mask)
    H, W = a.shape
    best, best_area = None, 0
    for i, (ys, xs) in enumerate(ndimage.find_objects(lab), 1):
        if ys.start <= 2 or xs.start <= 2 or ys.stop >= H - 2 or xs.stop >= W - 2:
            continue
        area = int((lab[ys, xs] == i).sum())
        if area > best_area:
            best, best_area = (ys, xs), area
    expect(best is not None, "no engraving on the page")
    ys, xs = best
    inside = lab[ys, xs] > 0
    rows, cols = np.where(inside.mean(1) > 0.5)[0], np.where(inside.mean(0) > 0.5)[0]
    box = (xs.start + cols[0], ys.start + rows[0], xs.start + cols[-1] + 1, ys.start + rows[-1] + 1)
    inset = int(min(box[2] - box[0], box[3] - box[1]) * 0.012)        # (the plate's ragged edge)
    return box[0] + inset, box[1] + inset, box[2] - inset, box[3] - inset


def crop_scan(image_url: str, out: Path) -> None:
    import io
    from PIL import Image, ImageOps
    url = re.sub(r"/\d+px-", "/1920px-", image_url.split("?")[0])
    for attempt in range(8):
        try:
            data = urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=120).read()
            break
        except Exception:
            time.sleep(20 * (attempt + 1))
    else:
        raise SystemExit(f"couldn't fetch {url}")
    img = Image.open(io.BytesIO(data)).convert("L")
    x0, y0, x1, y1 = engraving_box(img)
    share = (x1 - x0) * (y1 - y0) / (img.width * img.height)
    expect(0.3 < share < 0.6, f"{out.name}: the engraving found is {share:.0%} of the page")
    img = ImageOps.autocontrast(img.crop((x0, y0, x1, y1)), cutoff=(0.3, 0.3))   # (the scans are faded)
    if img.width > 1000:
        img = img.resize((1000, round(img.height * 1000 / img.width)), Image.LANCZOS)
    img.save(out, quality=85)
    time.sleep(1)


def dante_lines(part: str, canto: int, start: int, end: int) -> str:
    """Those lines of the bot's Dante (stored by tercet, under "canto.first line")."""
    books = json.loads((ROOT / "data" / "medieval" / "divine_comedy_longfellow.json").read_text(encoding="utf-8"))["books"]
    out = []
    for key, v in books[part].items():
        c, first = map(int, key.split("."))
        if c == canto:
            out += [(first + i, line) for i, line in enumerate(v["1"].splitlines())]
    lines = [line for n, line in sorted(out) if start <= n <= end]
    expect(len(lines) == end - start + 1, f"{part} {canto}:{start}-{end}")
    return "\n".join(lines)


def clean_dante(plates: list) -> list:
    """Each plate's lines, and its picture: a clean copy on Commons, or the engraving cut out of its scan."""
    CROPS.mkdir(parents=True, exist_ok=True)
    copies = file_info([f"File:{f}" for f in list(CLEAN_COPIES.values()) + [x[4] for x in NOT_SCANNED]])
    out = []
    for p in plates:
        sid = re.search(r"\((\d{9})\)", urllib.parse.unquote(p["page"])).group(1)
        p.pop("file", None)
        if sid in CLEAN_COPIES:
            info = copies[f"File:{CLEAN_COPIES[sid]}"]
            p["image"], p["page"] = info["image"], info["page"]
        else:
            crop = CROPS / f"{sid}.jpg"
            if not crop.exists():
                crop_scan(p["image"], crop)
            p["file"] = crop.relative_to(ROOT).as_posix()
        if p["book"]:                                   # (not the portrait)
            expect(sid in DANTE_LINES, f"no lines for {p['book']} plate {sid}")
            p["chapter"], p["start"], p["end"] = DANTE_LINES[sid]
        out.append(p)
    for part, canto, start, end, f in NOT_SCANNED:
        info = copies[f"File:{f}"]
        out.append({"set": "dante", "n": "", "title": "", "book": part, "chapter": canto, "start": start, "end": end,
                    "cited": "", "image": info["image"], "page": info["page"]})
    order = {"Inferno": 0, "Purgatorio": 1, "Paradiso": 2, None: -1}
    out.sort(key=lambda p: (order[p["book"]], p["chapter"] or 0, p["start"] or 0))
    for p in out:
        if p["book"]:
            # a stable short name for the button ids ("inf1l31": Inferno 1:31)
            p["n"] = f"{p['book'][:3].lower()}{p['chapter']}l{p['start']}"
            p["cited"] = f"{p['book']} {p['chapter']}:{p['start']}-{p['end']}"
            p["quote"] = dante_lines(p["book"], p["chapter"], p["start"], p["end"])
            p["title"] = p["quote"].splitlines()[0].rstrip(",;:")
    print(f"  the Divine Comedy: {len(out)} plates, {sum('file' in p for p in out)} cut out of their scans")
    return out


def cantos_from_twins() -> dict:
    """{scan number: canto} from the canto categories, whose files share the German scans' numbers."""
    out = {}
    for part in GERMAN:
        for sub in members(f"Category:Gustave Doré - {part}", "subcat"):
            m = re.search(r"Canto (\d+)", sub)
            if not m:
                continue
            for f in members(sub):
                sid = re.search(r"\((\d{9})\)", f)
                if sid:
                    out.setdefault((part, sid.group(1)), int(m.group(1)))
    return out


# ── Paradise Lost ──────────────────────────────────────────────────────────

INDEX = "Milton - Milton's Paradise Lost, tra il 1882 e il 1891.djvu/"


def _norm(line: str) -> str:
    line = line.lower().replace("'d", "ed").replace("’d", "ed")
    return re.sub(r"[^a-z]", "", line)


def milton() -> list:
    pl = json.loads((ROOT / "data" / "medieval" / "milton.json").read_text(encoding="utf-8"))["books"]["Paradise Lost"]
    lines = [(int(b), int(n), _norm(t)) for b, ch in pl.items() for n, t in ch.items() if n != "0"]
    d = api("en.wikisource.org", action="query", list="allpages", apprefix=INDEX, apnamespace=104, aplimit=500)
    titles = sorted((p["title"] for p in d["query"]["allpages"]), key=lambda t: int(t.rsplit("/", 1)[1]))
    texts = []
    for i in range(0, len(titles), 40):
        r = api("en.wikisource.org", action="query", prop="revisions", rvprop="content", rvslots="main",
                titles="|".join(titles[i:i + 40]))
        texts += [p["revisions"][0]["slots"]["main"]["content"] for p in r["query"]["pages"]]
    found = {}
    for t in texts:
        m = re.search(r"\[\[File:Paradise[ _]Lost[ _](\d+)\.jpg", t)
        if not m:
            continue
        body = re.sub(r"<noinclude>.*?</noinclude>|\{\{[^{}]*\}\}|\[\[File:[^\]]*\]\]|<[^>]+>", "\n", t, flags=re.S)
        quote = [l.strip() for l in body.splitlines()
                 if len(_norm(l)) > 6 and not re.search(r"(?i)\b(book|hook|hoot|line|lina|lints|lines)\b", l)
                 and len(re.findall(r"[a-z]", l)) > 0.6 * len(l.strip())]
        found[int(m.group(1))] = quote
    # the transcription skips plate 24, the battle in Heaven; Commons has the same plate as
    # "6-207 Now storming fury rose.jpg", i.e. Book VI, line 207
    found.setdefault(24, ["Now storming furie rose,", "And clamour such as heard in Heav'n till now"])
    expect(sorted(found) == list(range(1, 51)), f"Paradise Lost plates in the transcription: {sorted(found)}")
    info = file_info([f"File:Paradise Lost {n}.jpg" for n in range(1, 51)])
    plates = []
    for n, quote in sorted(found.items()):
        # the whole quotation against every run of as many lines (it may start or end mid-line)
        want, k = _norm(" ".join(quote)), max(1, len(quote))
        best, score = None, 0.0
        for i in range(len(lines) - k + 1):
            window = lines[i:i + k]
            if len({w[0] for w in window}) > 1:
                continue
            text = "".join(w[2] for w in window)
            if not (set(want[:6]) & set(text)) or want[:4] not in text and want[-4:] not in text:
                continue
            r = difflib.SequenceMatcher(None, want, text).ratio()
            if r > score:
                best, score = window, r
        if best is None or score < 0.6:
            print(f"  ✗ Paradise Lost plate {n}: lines not found ({quote[:2]}, best {score:.2f})")
            continue
        b, start, end = best[0][0], best[0][1], best[-1][1]
        plates.append(plate("milton", str(n), " / ".join(quote)[:120], ("Paradise Lost", b, start, end),
                            info[f"File:Paradise Lost {n}.jpg"], f"Paradise Lost {b}:{start}" + (f"-{end}" if end != start else "")))
    return plates


def expect(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"unexpected: {message}")


def main():
    global LOOKUP
    import logging
    logging.disable(logging.WARNING)
    from scripture_lookup import ScriptureLookup
    LOOKUP = ScriptureLookup()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    cache = ROOT / "scripts" / ".cache" / "dore_bible_dante.json"     # (the slow part; delete to fetch again)
    if cache.exists():
        plates, d = json.loads(cache.read_text(encoding="utf-8"))
    else:
        plates = bible()
        d = dante()
        cache.parent.mkdir(exist_ok=True)
        cache.write_text(json.dumps([plates, d], ensure_ascii=False), encoding="utf-8")
    for p in plates:                                    # (references read again: cheap, and the reader improves)
        ref = readable_ref(p["cited"])
        expect(ref is not None, f"{p['n']} {p['title']}: {p['cited']}")
        p["book"], p["chapter"], p["start"], p["end"] = ref
    print(f"  the Bible: {len(plates)} plates; the Divine Comedy: {len(d)}")
    d = clean_dante(d)
    m = milton()
    print(f"  Paradise Lost: {len(m)} plates")
    OUT.write_text(json.dumps({"source": "Gustave Doré's engravings, from Wikimedia Commons",
                               "plates": plates + d + m}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)}: {len(plates) + len(d) + len(m)} plates")


if __name__ == "__main__":
    main()
