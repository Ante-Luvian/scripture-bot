"""
Build data/people_places/ for !who and !place:

  people_places.json  biblical people (family, tribe, a short description,
                      every verse naming them) and places (kind, location,
                      description, verses), from Theographic Bible Metadata
                      (github.com/robertrouse/theographic-bible-metadata),
                      whose descriptions are Easton's Bible Dictionary and
                      whose locations come from OpenBible.info and Pleiades.
  basemap.json        coastlines, lakes and rivers of the Mediterranean and
                      Near East for the map cards, from Natural Earth
                      (naturalearthdata.com), clipped and simplified.

    python scripts/build_people_places.py
"""
import json
import re
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "scripts" / ".cache"
OUT = ROOT / "data" / "people_places"
THEO = "https://raw.githubusercontent.com/robertrouse/theographic-bible-metadata/master/json/{}.json"
NE = "https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/{}.geojson"
BBOX = (-15.0, 5.0, 80.0, 58.0)        # lon/lat: Tarshish (Spain) to India, Sheba to past the Black Sea

OSIS = {
    "Gen": "Genesis", "Exod": "Exodus", "Lev": "Leviticus", "Num": "Numbers", "Deut": "Deuteronomy",
    "Josh": "Joshua", "Judg": "Judges", "Ruth": "Ruth", "1Sam": "1 Samuel", "2Sam": "2 Samuel",
    "1Kgs": "1 Kings", "2Kgs": "2 Kings", "1Chr": "1 Chronicles", "2Chr": "2 Chronicles", "Ezra": "Ezra",
    "Neh": "Nehemiah", "Esth": "Esther", "Job": "Job", "Ps": "Psalms", "Prov": "Proverbs",
    "Eccl": "Ecclesiastes", "Song": "Song of Solomon", "Isa": "Isaiah", "Jer": "Jeremiah",
    "Lam": "Lamentations", "Ezek": "Ezekiel", "Dan": "Daniel", "Hos": "Hosea", "Joel": "Joel", "Amos": "Amos",
    "Obad": "Obadiah", "Jonah": "Jonah", "Mic": "Micah", "Nah": "Nahum", "Hab": "Habakkuk", "Zeph": "Zephaniah",
    "Hag": "Haggai", "Zech": "Zechariah", "Mal": "Malachi", "Matt": "Matthew", "Mark": "Mark", "Luke": "Luke",
    "John": "John", "Acts": "Acts", "Rom": "Romans", "1Cor": "1 Corinthians", "2Cor": "2 Corinthians",
    "Gal": "Galatians", "Eph": "Ephesians", "Phil": "Philippians", "Col": "Colossians",
    "1Thess": "1 Thessalonians", "2Thess": "2 Thessalonians", "1Tim": "1 Timothy", "2Tim": "2 Timothy",
    "Titus": "Titus", "Phlm": "Philemon", "Heb": "Hebrews", "Jas": "James", "1Pet": "1 Peter", "2Pet": "2 Peter",
    "1John": "1 John", "2John": "2 John", "3John": "3 John", "Jude": "Jude", "Rev": "Revelation",
}
BOOK_ORDER = list(OSIS.values())


def cached(url: str, name: str) -> Path:
    path = CACHE / name
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        req = urllib.request.Request(url, headers={"User-Agent": "ScriptureBot/1.0"})
        path.write_bytes(urllib.request.urlopen(req, timeout=120).read())
    return path


def theographic(name: str) -> list:
    return json.loads(cached(THEO.format(name), f"theographic/{name}.json").read_text(encoding="utf-8"))


def _list(value) -> list:
    """Some link fields are lists, some a list written out as a string."""
    if isinstance(value, list):
        return value
    if isinstance(value, str) and value.startswith("["):
        return re.findall(r"'([^']+)'", value)
    return []


def describe(field) -> str:
    """Easton's entry, markdown links unwrapped, cut to its first sentences."""
    text = field[0] if isinstance(field, list) and field else field if isinstance(field, str) else ""
    text = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", text or "")
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return ""
    out = ""
    for sentence in re.split(r"(?<=[.!?])\s+(?=[A-Z“(])", text):
        if out and len(out) + len(sentence) > 450:
            break
        out = (out + " " + sentence).strip()
    if len(out) > 600:
        out = out[:597].rsplit(" ", 1)[0] + "…"
    return out


def refs(record_ids: list, verse_osis: dict) -> list:
    """Theographic verse records -> ['Genesis 12:8', ...] in Bible order."""
    out = []
    for rid in record_ids:
        osis = verse_osis.get(rid)
        if not osis:
            continue
        book, chap, verse = osis.split(".")
        out.append((BOOK_ORDER.index(OSIS[book]), int(chap), int(verse), f"{OSIS[book]} {chap}:{verse}"))
    return [r[3] for r in sorted(set(out))]


def build_entities() -> dict:
    verse_osis = {v["id"]: v["fields"]["osisRef"] for v in theographic("verses")}
    people = theographic("people")
    places = theographic("places")
    groups = theographic("peopleGroups")
    person_slug = {p["id"]: p["fields"]["slug"] for p in people}
    place_slug = {p["id"]: p["fields"]["slug"] for p in places}
    group_of = {}
    for g in groups:
        for member in g["fields"].get("members", []):
            group_of.setdefault(member, []).append(g["fields"]["groupName"])

    out_people = {}
    for rec in people:
        f = rec["fields"]                  # (most are marked "wip" in Theographic's editing; the data is complete)
        links = lambda key: [person_slug[i] for i in f.get(key, []) if i in person_slug]
        out_people[f["slug"]] = {
            "name": f.get("displayTitle") or f["name"],
            "short": f["name"],
            "also": [a.strip() for a in (f.get("alsoCalled") or "").split(",") if a.strip()],
            "gender": f.get("gender", ""),
            "about": describe(f.get("dictText") or f.get("dictionaryText")),
            "father": links("father"), "mother": links("mother"), "partners": links("partners"),
            "children": links("children"), "siblings": links("siblings")
                + links("halfSiblingsSameFather") + links("halfSiblingsSameMother"),
            "groups": group_of.get(rec["id"], []),
            "born": [place_slug[i] for i in f.get("birthPlace", []) if i in place_slug],
            "died": [place_slug[i] for i in f.get("deathPlace", []) if i in place_slug],
            "verses": refs(_list(f.get("verses")), verse_osis),
        }

    out_places = {}
    duplicates = {}
    for rec in places:
        f = rec["fields"]
        if f.get("duplicate_of"):
            duplicates[f["slug"]] = place_slug.get(_list(f["duplicate_of"])[0])
            continue
        lat, lon = f.get("latitude"), f.get("longitude")
        precision = f.get("precision", "")
        located = lat and lon and precision != "Unlocated"
        names = [f.get("esvName", ""), f.get("kjvName", "")] + [a.strip() for a in (f.get("aliases") or "").split(",")]
        out_places[f["slug"]] = {
            "name": f["displayTitle"],
            "also": [n for n in dict.fromkeys(names) if n and n != f["displayTitle"]],
            "kind": f.get("featureSubType") or f.get("featureType") or f.get("comment", "").capitalize() or "",
            "lat": round(float(lat), 4) if located else None,
            "lon": round(float(lon), 4) if located else None,
            # "Rough" or placed by a related site: shown as an approximate location
            "approx": bool(located and (precision.startswith(("Rough", "Related")) or f.get("ambiguous"))),
            "about": describe(f.get("dictText") or f.get("dictionaryText")),
            "within": [place_slug[i] for i in _list(f.get("rootID")) if i in place_slug and i != rec["id"]],
            "verses": refs(_list(f.get("verses")), verse_osis),
            "weight": f.get("verseCount", 0),
        }
    for dup, original in duplicates.items():
        if original in out_places:
            out_places[original]["verses"] = sorted(set(out_places[original]["verses"]))
    for p in out_people.values():
        p["born"] = [duplicates.get(s, s) for s in p["born"]]
        p["died"] = [duplicates.get(s, s) for s in p["died"]]
    return {"source": "Theographic Bible Metadata (theographic.com); descriptions from Easton's Bible "
                      "Dictionary; locations from OpenBible.info and Pleiades",
            "people": out_people, "places": out_places}


def build_basemap() -> dict:
    from shapely.geometry import box, shape, mapping
    clip = box(*BBOX)
    out = {"bbox": BBOX, "source": "Natural Earth"}
    for layer, name, tolerance in (("land", "ne_10m_land", 0.01), ("lakes", "ne_10m_lakes", 0.005),
                                   ("rivers", "ne_10m_rivers_lake_centerlines", 0.01)):
        geo = json.loads(cached(NE.format(name), f"naturalearth/{name}.geojson").read_text(encoding="utf-8"))
        shapes = []
        for feat in geo["features"]:
            props = feat.get("properties") or {}
            if layer == "rivers" and (props.get("scalerank") or 9) > 6:
                continue                                 # just the major rivers
            geom = shape(feat["geometry"])
            if not geom.intersects(clip):
                continue
            geom = geom.intersection(clip).simplify(tolerance, preserve_topology=True)
            if geom.is_empty or (layer == "lakes" and geom.area < 0.004):
                continue
            parts = getattr(geom, "geoms", [geom])
            for part in parts:
                if part.geom_type == "Polygon":
                    if part.area < 0.002:
                        continue
                    shapes.append([[round(x, 3), round(y, 3)] for x, y in part.exterior.coords])
                elif part.geom_type == "LineString":
                    shapes.append([[round(x, 3), round(y, 3)] for x, y in part.coords])
        out[layer] = shapes
    return out


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    data = build_entities()
    (OUT / "people_places.json").write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")),
                                            encoding="utf-8")
    basemap = build_basemap()
    (OUT / "basemap.json").write_text(json.dumps(basemap, separators=(",", ":")), encoding="utf-8")
    print(f"{len(data['people'])} people, {len(data['places'])} places; basemap "
          f"{sum(len(s) for s in basemap['land'])} land points, {len(basemap['rivers'])} rivers, "
          f"{len(basemap['lakes'])} lakes")


if __name__ == "__main__":
    main()
