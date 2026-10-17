"""
Builds data/icons/: famous Orthodox icons and the icons of the Great Feasts, for !icon.
Each image is a public-domain icon on Wikimedia Commons (the file named here, or the
main image of the icon's Wikipedia article), saved at most 1200 pixels wide; its
explanation is the summary of the matching Wikipedia article.

    python scripts/build_icons.py
"""
import json
import time
import urllib.parse
import urllib.request
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "icons"
UA = {"User-Agent": "ScriptureBotCorpusBuilder/1.0 (Discord bot; low-volume one-off import)"}

# key: (title, image: "File:..." on Commons or "article:..." for that article's main image,
#       the Wikipedia article explaining it, feast it's shown on ("MM-DD", or "pascha+N"), other names)
ICONS = {
    "trinity": ("The Holy Trinity, by Andrei Rublev", "article:Trinity (Andrei Rublev)", "Trinity (Andrei Rublev)",
                "pascha+49", ["rublev", "hospitality of abraham", "pentecost"]),
    "vladimir": ("The Theotokos of Vladimir", "article:Theotokos of Vladimir", "Theotokos of Vladimir", "",
                 ["virgin of vladimir", "our lady of vladimir", "mary"]),
    "pantocrator": ("Christ Pantocrator of Sinai", "article:Christ Pantocrator (Sinai)", "Christ Pantocrator (Sinai)",
                    "", ["sinai", "christ", "pantokrator"]),
    "hodegetria": ("The Hodegetria (She Who Shows the Way), by Dionisius", "article:Hodegetria", "Hodegetria", "",
                   ["smolensk", "theotokos of smolensk", "mary"]),
    "kazan": ("Our Lady of Kazan", "article:Our Lady of Kazan", "Our Lady of Kazan", "", ["kazan icon", "mary"]),
    "tikhvin": ("The Theotokos of Tikhvin", "article:Theotokos of Tikhvin", "Theotokos of Tikhvin", "", ["mary"]),
    "sign": ("Our Lady of the Sign", "article:Our Lady of the Sign", "Our Lady of the Sign", "", ["znamenie", "orans", "mary"]),
    "ladder": ("The Ladder of Divine Ascent", "article:The Ladder of Divine Ascent", "The Ladder of Divine Ascent", "",
               ["climacus", "ladder of paradise"]),
    "iveron": ("The Iveron Theotokos (Portaitissa)", "File:Iveron.jpg", "Panagia Portaitissa", "",
               ["portaitissa", "iviron", "mary"]),
    "zvenigorod": ("The Saviour of Zvenigorod, by Andrei Rublev", "File:Rublev's saviour.jpg", "Andrei Rublev", "",   # (no article of its own)
                   ["saviour", "savior", "rublev's saviour"]),
    "st george": ("The Miracle of St George and the Dragon (Novgorod)",
                  "File:Unknow - Miracle of St George and the Dragon. Novgorod - Google Art Project.jpg",
                  "Saint George and the Dragon", "04-23", ["george", "dragon"]),
    "st nicholas": ("Saint Nicholas (Novgorod school)",
                    "File:Novgorod School - Saint Nicholas - NG.M.02422 - National Museum of Art, Architecture and "
                    "Design.jpg", "Saint Nicholas", "12-06", ["nicholas"]),
    # the twelve Great Feasts and Pascha, in the Church year's order (from 1 September)
    "nativity of the theotokos": ("The Nativity of the Theotokos",
                                  "File:Nikola-Obrazopisov-Belyova-church-Nativity-of-the-Theotokos-icon-1863.jpg",
                                  "Nativity of Mary", "09-08", ["birth of mary", "nativity of mary", "mary"]),
    "exaltation of the cross": ("The Exaltation of the Holy Cross", "File:Exaltation of the Cross - Palekh icon (19 c, "
                                "priv.coll).jpg", "Elevation of the Holy Cross", "09-14",
                                ["elevation of the cross", "holy cross", "cross"]),
    "entry of the theotokos": ("The Entry of the Theotokos into the Temple", "File:Russian - Presentation of the Virgin in the "
                               "Temple - Walters 372410.jpg",
                               "Presentation of Mary", "11-21", ["presentation of mary", "entrance of the theotokos", "mary"]),
    "nativity": ("The Nativity of Christ", "File:Nativity (15th c., Annunciation Cathedral in Moscow).jpg",
                 "Nativity of Jesus", "12-25", ["christmas", "birth of christ"]),
    "theophany": ("Theophany: the Baptism of Christ", "File:Baptism (15th c., Annunciation Cathedral in Moscow).jpg",
                  "Baptism of Jesus", "01-06", ["baptism", "epiphany", "baptism of christ"]),
    "meeting": ("The Meeting of the Lord in the Temple", "File:Candlemas (1420s, Sergiev Posad).jpg",
                "Presentation of Jesus", "02-02", ["candlemas", "presentation of christ", "presentation"]),
    "annunciation": ("The Annunciation of Ustyug", "article:Annunciation of Ustyug", "Annunciation of Ustyug", "03-25",
                     ["ustyug", "annunciation", "mary"]),
    "entry into jerusalem": ("The Entry into Jerusalem (Palm Sunday)",
                             "File:Entry into Jerusalem (Annunciation Cathedral in Moscow).jpg",
                             "Triumphal entry into Jerusalem", "pascha-7", ["palm sunday", "palms"]),
    "resurrection": ("The Resurrection: Christ's Descent into Hades (Chora)", "File:Anastasis fresco (Chora Church).jpg",
                     "Harrowing of Hell", "pascha+0", ["pascha", "easter", "anastasis", "descent into hades"]),
    "ascension": ("The Ascension", "File:Ascension from Vasilyevskiy chin (15th c., GTG).jpg", "Ascension of Jesus",
                  "pascha+39", []),
    "transfiguration": ("The Transfiguration", "File:Transfiguration (Annunciation Cathedral, Kremlin).jpg",
                        "Transfiguration of Jesus", "08-06", ["mount tabor", "tabor"]),
    "dormition": ("The Dormition of the Theotokos, by Theophanes the Greek", "File:Theofanus uspenie.jpg",
                  "Dormition of the Mother of God", "08-15", ["assumption", "falling asleep", "uspenie", "mary"]),
}


def api(host: str, **params) -> dict:
    url = f"https://{host}/w/api.php?" + urllib.parse.urlencode({**params, "format": "json", "formatversion": 2})
    for attempt in range(6):
        try:
            data = json.loads(urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60).read())
            time.sleep(1.5)
            return data
        except Exception:
            time.sleep(15 * (attempt + 1))
    raise SystemExit(f"{host} kept refusing: {url}")


def image_file(spec: str) -> str:
    if spec.startswith("File:"):
        return spec
    page = api("en.wikipedia.org", action="query", prop="pageimages", piprop="name", redirects=1,
               titles=spec.split(":", 1)[1])["query"]["pages"][0]
    return "File:" + page["pageimage"]


def summary(article: str) -> str:
    page = api("en.wikipedia.org", action="query", prop="extracts", exintro=1, explaintext=1, exsentences=4,
               redirects=1, titles=article)["query"]["pages"][0]
    return (page.get("extract") or "").strip()


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    out = {}
    for key, (title, spec, article, feast, names) in ICONS.items():
        name = image_file(spec)
        info = api("commons.wikimedia.org", action="query", prop="imageinfo", iiprop="url", iiurlwidth=1200,
                   titles=name)["query"]["pages"][0]["imageinfo"][0]
        path = OUT / (key.replace(" ", "_") + ".jpg")
        if not path.exists():
            path.write_bytes(urllib.request.urlopen(urllib.request.Request(info.get("thumburl") or info["url"],
                                                                           headers=UA), timeout=120).read())
            img = Image.open(path).convert("RGB")                  # (small originals come back as they are)
            img.thumbnail((1200, 1200))
            img.save(path, "JPEG", quality=85, optimize=True)
            time.sleep(1.5)
        out[key] = {"title": title, "file": path.name, "commons": name, "page": info["descriptionurl"],
                    "article": article, "about": summary(article), "feast": feast, "names": names}
        print(key, path.stat().st_size // 1024, "KB")
    (OUT / "icons.json").write_text(json.dumps({"icons": out}, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
