"""
Builds data/blake/plates.json: William Blake's illuminated books, plate by plate, for !blake.

Blake printed his poems himself, text and picture etched together on copper and coloured by
hand, so no two copies are alike. For each book this takes the most complete copy on
Wikimedia Commons (its files are named after the William Blake Archive's object numbers:
"..., copy Z, object 1 (Bentley 1, ...)"), and keeps the plates in order. Only the image
addresses are saved; Discord shows the pictures from Wikimedia.

    python scripts/build_blake_plates.py
"""
import json
import re
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "blake" / "plates.json"
UA = {"User-Agent": "ScriptureBotCorpusBuilder/1.0 (Discord bot; low-volume one-off import)"}

# key: (title, what Commons calls it, year, about)
BOOKS = {
    "religion": ("All Religions are One", "All Religions are One", "c. 1788",
                 "Blake's first experiment in relief etching: ten tiny plates of principles."),
    "natural": ("There is No Natural Religion", "There is No Natural Religion", "c. 1788",
                "The companion to All Religions are One, against the reasoning of the philosophers."),
    "songs": ("Songs of Innocence and of Experience", "Songs of Innocence and Experience", "1794",
              "\"Shewing the two contrary states of the human soul\": the Songs of Innocence with their answers, "
              "The Tyger, London and the rest."),
    "thel": ("The Book of Thel", "The Book of Thel", "1789",
             "Thel, a maiden of the vales of Har, asks why she must fade, and visits the grave."),
    "marriage": ("The Marriage of Heaven and Hell", "The Marriage of Heaven and Hell", "c. 1790",
                 "Blake's satire on Swedenborg, with the Proverbs of Hell."),
    "visions": ("Visions of the Daughters of Albion", "Visions of the Daughters of Albion", "1793",
                "Oothoon's cry for freedom in love and against slavery."),
    "america": ("America a Prophecy", "America a Prophecy", "1793",
                "The American Revolution as a cosmic uprising, led by the fiery spirit Orc."),
    "europe": ("Europe a Prophecy", "Europe a Prophecy", "1794", "Eighteen hundred years of Europe's sleep, and its waking."),
    "urizen": ("The Book of Urizen", "The Book of Urizen", "1794",
               "Blake's dark Genesis: Urizen, the god of reason and law, divides himself from eternity."),
    "songoflos": ("The Song of Los", "The Song of Los", "1795", "The history of religions, from Africa to Asia."),
    "ahania": ("The Book of Ahania", "The Book of Ahania", "1795", "The sequel to Urizen."),
    "los": ("The Book of Los", "The Book of Los", "1795", "The fall of Los, the prophet of imagination."),
    "milton": ("Milton a Poem", "Milton a Poem", "1804–1811",
               "The poet Milton returns from heaven to correct his errors; its preface is \"And did those feet\"."),
    "jerusalem": ("Jerusalem The Emanation of the Giant Albion", "Jerusalem The Emanation of the Giant Albion",
                  "1804–1820", "Blake's longest book: a hundred plates of Albion's fall and awakening."),
}


def api(**params) -> dict:
    url = "https://commons.wikimedia.org/w/api.php?" + urllib.parse.urlencode({**params, "format": "json", "formatversion": 2})
    for attempt in range(8):
        try:
            data = json.loads(urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60).read())
            time.sleep(2)
            return data
        except Exception:
            time.sleep(30 * (attempt + 1))
    raise SystemExit(f"Commons kept refusing: {url}")


def category_files(category: str) -> list:
    files, cont = [], {}
    while True:
        data = api(action="query", list="categorymembers", cmtitle=category, cmtype="file", cmlimit=500, **cont)
        files += [m["title"] for m in data["query"]["categorymembers"]]
        if "continue" not in data:
            return files
        cont = data["continue"]


# what a book's files have in their names (Commons isn't consistent: "Songs of Innocence and Experience",
# "Book of Thel copy F plate 01", "William Blake, Plate 01 Jerusalem (copy E)")
SEARCH = {"songs": "Songs of Innocence", "thel": "Thel", "marriage": "Marriage of Heaven and Hell",
          "visions": "Daughters of Albion", "america": "America a Prophecy", "europe": "Europe a Prophecy",
          "urizen": "Urizen", "songoflos": "Song of Los", "ahania": "Ahania", "los": "Book of Los", "milton": "Milton",
          "jerusalem": "Jerusalem", "religion": "All Religions are One", "natural": "Natural Religion"}
IMAGE = (".jpg", ".jpeg", ".png", ".tif", ".tiff")


def search_files(words: str) -> list:
    files, offset = [], 0
    while offset is not None and offset < 2000:
        data = api(action="query", list="search", srsearch=f'intitle:"{words}"', srnamespace=6, srlimit=500,
                   sroffset=offset)
        files += [r["title"] for r in data["query"]["search"]]
        offset = data.get("continue", {}).get("sroffset")
    return files


def copies(files: list, words: str) -> dict:
    """{(copy, "object"|"plate"): {number: file}} from the file names that give a copy and a plate or object number."""
    out = {}
    for f in files:
        low = f.lower()
        if words.lower() not in low or "detail" in low or not low.endswith(IMAGE):
            continue
        copy = re.search(r"(?i)\bcopy\s+([a-z]{1,2})\b", f)
        num = re.search(r"(?i)\b(object|plate)\s*(\d+)\b", f)
        if copy and num:
            out.setdefault((copy.group(1).upper(), num.group(1).lower()), {}).setdefault(int(num.group(2)), f)
    return out


def best_copy(key: str, name: str) -> "tuple[str, dict]":
    """The copy with the most plates, among the book's files found by name and its copies' categories."""
    words = SEARCH[key]
    files = search_files(words)
    found = api(action="query", list="search", srsearch=f'"{name}" copy', srnamespace=14, srlimit=30)
    for r in found["query"]["search"]:
        if "copy" in r["title"].lower() and words.lower() in r["title"].lower():
            files += category_files(r["title"])
    groups = copies(files, words)
    if not groups:
        return "", {}
    (copy, _), plates = max(groups.items(), key=lambda kv: len(kv[1]))
    return copy, plates


def image_urls(files: list) -> dict:
    out = {}
    for i in range(0, len(files), 40):
        batch = files[i:i + 40]
        data = api(action="query", prop="imageinfo", iiprop="url", iiurlwidth=1000, titles="|".join(batch))
        for page in data["query"]["pages"]:
            info = (page.get("imageinfo") or [{}])[0]
            if info:
                out[page["title"]] = {"image": info.get("thumburl") or info["url"], "page": info["descriptionurl"]}
    return out


# how many plates a whole copy has (copies differ a little: Blake added, dropped and reordered plates)
WHOLE = {"religion": 10, "natural": 19, "songs": 54, "thel": 8, "marriage": 27, "visions": 11, "america": 18,
         "europe": 18, "urizen": 28, "songoflos": 8, "ahania": 6, "los": 5, "milton": 50, "jerusalem": 100}


def main():
    OUT.parent.mkdir(parents=True, exist_ok=True)
    books = json.loads(OUT.read_text(encoding="utf-8"))["illuminated"] if OUT.exists() else {}
    for key, (title, commons, year, about) in BOOKS.items():
        if key in books:
            if len(books[key]["plates"]) < 0.8 * WHOLE[key]:          # a partial copy: left out, not shown half
                print(f"  {title}: only {len(books[key]['plates'])} of {WHOLE[key]} plates on Commons, left out")
                del books[key]
            continue
        copy, plates = best_copy(key, commons)
        if not plates:
            print(f"  {title}: no numbered copy on Commons, left out")
            continue
        urls = image_urls([plates[n] for n in sorted(plates)])
        books[key] = {"title": title, "year": year, "about": about, "copy": copy,
                      "plates": [{"object": n, "file": plates[n], **urls[plates[n]]} for n in sorted(plates)
                                 if plates[n] in urls]}
        print(f"  {title}: copy {copy}, {len(books[key]['plates'])} plates")
        save(books)                                     # (as it goes: Commons is slow, and a rerun resumes)
    save({k: b for k, b in books.items() if len(b["plates"]) >= 0.8 * WHOLE[k]})


def save(books: dict) -> None:
    OUT.write_text(json.dumps({"source": "William Blake's illuminated books, from Wikimedia Commons "
                                         "(numbered as in the William Blake Archive)",
                               "illuminated": books},      # (not "books": that would make it a text corpus)
                              ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
