"""
Builds data/tarot/: the 78 cards of the Rider tarot (Rider-Waite-Smith, 1909), for !tarot.

  · the pictures: Pamela Colman Smith's designs, scanned from the 1909 deck, from
    Wikimedia Commons ("RWS Tarot 01 Magician.jpg", "Wands10.jpg"...), saved 600 pixels wide;
  · the words: A. E. Waite's own Pictorial Key to the Tarot (1911), from the sacred-texts.com
    archive: what each card shows, and its divinatory meaning, upright and reversed.

    python scripts/build_tarot.py
"""
import html
import io
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_world_texts import ROOT, expect, sacred_text, tidy   # noqa: E402

OUT = ROOT / "data" / "tarot"
UA = {"User-Agent": "ScriptureBotCorpusBuilder/1.0 (Discord bot; low-volume one-off import)"}

MAJOR = ["The Fool", "The Magician", "The High Priestess", "The Empress", "The Emperor", "The Hierophant",
         "The Lovers", "The Chariot", "Strength", "The Hermit", "Wheel of Fortune", "Justice", "The Hanged Man",
         "Death", "Temperance", "The Devil", "The Tower", "The Star", "The Moon", "The Sun", "Judgement", "The World"]
COMMONS_MAJOR = ["Fool", "Magician", "High Priestess", "Empress", "Emperor", "Hierophant", "Lovers", "Chariot",
                 "Strength", "Hermit", "Wheel of Fortune", "Justice", "Hanged Man", "Death", "Temperance", "Devil",
                 "Tower", "Star", "Moon", "Sun", "Judgement", "World"]
SUITS = {"Wands": ("wa", "Wands"), "Cups": ("cu", "Cups"), "Swords": ("sw", "Swords"), "Pentacles": ("pe", "Pents")}
RANKS = ["Ace", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine", "Ten", "Page", "Knight", "Queen", "King"]
PAGE_RANK = ["ac", "02", "03", "04", "05", "06", "07", "08", "09", "10", "pa", "kn", "qu", "ki"]


def page_text(name: str) -> str:
    """A card's page in the Pictorial Key, as text: what follows the picture, up to "Next:"."""
    t = sacred_text(f"tarot/pkt/{name}")
    t = re.sub(r"(?is)<(script|style|head)[^>]*>.*?</\1>", "", t)
    t = t[:t.lower().find("<nav")] if "<nav" in t.lower() else t
    t = html.unescape(re.sub(r"<[^>]+>", " ", t))
    t = t[t.find("Click to enlarge") + len("Click to enlarge"):]
    return tidy(re.split(r"\s+Next:", t)[0])


def split_reversed(text: str) -> "tuple[str, str]":
    parts = re.split(r"Reversed\s*:", text, maxsplit=1)
    return parts[0].strip(), (parts[1] if len(parts) > 1 else "").strip()


def major_meanings() -> dict:
    """{number: (upright, reversed)} from Part III § 3, "The Greater Arcana and their Divinatory Meanings"."""
    raw = sacred_text("tarot/pkt/pkt0303.htm")
    raw = re.sub(r"(?is)<(script|style|head)[^>]*>.*?</\1>", "", raw)
    raw = tidy(html.unescape(re.sub(r"<[^>]+>", " ", raw)))
    out = {}
    head = r"(?:(\d+)|ZERO)\.\s+([A-Z][A-Z ,']+?)\.?--?"         # "10. WHEEL OF FORTUNE.-" has one dash
    for m in re.finditer(head + rf"(.*?)(?=\s{head}|\s+Next:|$)", raw):
        num = int(m.group(1)) if m.group(1) else 0
        upright, reversed_ = split_reversed(m.group(3).split(" It will be seen")[0])   # (the section's closing remarks)
        out[num] = (upright, reversed_)
    return out


def commons_file(name: str) -> "dict":
    url = "https://commons.wikimedia.org/w/api.php?" + urllib.parse.urlencode({
        "action": "query", "prop": "imageinfo", "iiprop": "url", "iiurlwidth": 600, "titles": f"File:{name}",
        "format": "json", "formatversion": 2})
    for attempt in range(6):
        try:
            page = json.loads(urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60).read())
            time.sleep(1.5)
            return page["query"]["pages"][0]["imageinfo"][0]
        except Exception:
            time.sleep(20 * (attempt + 1))
    raise SystemExit(f"Commons kept refusing {name}")


def save_image(name: str, path: Path) -> None:
    if path.exists():
        return
    info = commons_file(name)
    data = urllib.request.urlopen(urllib.request.Request(info.get("thumburl") or info["url"], headers=UA), timeout=120).read()
    img = Image.open(io.BytesIO(data)).convert("RGB")
    img.thumbnail((600, 1200))
    img.save(path, "JPEG", quality=85, optimize=True)
    time.sleep(1.5)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    meanings = major_meanings()
    expect(sorted(meanings) == list(range(22)), f"major meanings: {sorted(meanings)}")
    cards = []
    for n, title in enumerate(MAJOR):
        key = f"major{n:02d}"
        description = page_text(f"pktar{n:02d}.htm")
        upright, reversed_ = meanings[n]
        save_image(f"RWS Tarot {n:02d} {COMMONS_MAJOR[n]}.jpg", OUT / f"{key}.jpg")
        cards.append({"key": key, "name": title, "arcana": "major", "number": n, "file": f"{key}.jpg",
                      "description": description, "upright": upright, "reversed": reversed_})
    for suit, (st, commons) in SUITS.items():
        for i, rank in enumerate(RANKS):
            key = f"{suit.lower()}{i + 1:02d}"
            text = page_text(f"pkt{st}{PAGE_RANK[i]}.htm")
            parts = re.split(r"Div[ai]n\w*tory Meanings?\s*:", text, maxsplit=1)      # ("Divanatory": the Five of Cups)
            description, meaning = parts[0], (parts[1] if len(parts) > 1 else "")
            upright, reversed_ = split_reversed(meaning)
            expect(upright.strip() and (reversed_.strip() or (rank, suit) == ("Two", "Cups")),   # (Waite gives none for it)
                   f"{rank} of {suit}: {text[:80]}")
            save_image(f"{commons}{i + 1:02d}.jpg", OUT / f"{key}.jpg")
            cards.append({"key": key, "name": f"{rank} of {suit}", "arcana": "minor", "suit": suit, "number": i + 1,
                          "file": f"{key}.jpg", "description": description.strip(), "upright": upright.strip(),
                          "reversed": reversed_.strip()})
        print(suit, "done")
    expect(len(cards) == 78, f"{len(cards)} cards")
    (OUT / "cards.json").write_text(json.dumps({
        "source": "The Rider tarot (1909), drawn by Pamela Colman Smith (scans: Wikimedia Commons); meanings from "
                  "A. E. Waite, The Pictorial Key to the Tarot (1911), via sacred-texts.com",
        "cards": cards}, ensure_ascii=False, indent=1), encoding="utf-8")
    size = sum(p.stat().st_size for p in OUT.glob("*.jpg"))
    print(f"wrote {len(cards)} cards, {size // 1_000_000} MB of pictures")


if __name__ == "__main__":
    main()
