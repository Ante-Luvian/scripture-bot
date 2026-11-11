"""
Download the English hadith collections into data/hadith/, one file a collection (~30 MB in all). With them there,
!verse reads hadith from disk and Ask the library can search them. Not kept in git: this script fetches them again.

    - the ten on fawazahmed0's hadith-api (the same source !verse reads online for them);
    - five more from AhmedBaset's hadith-json (github.com/AhmedBaset/hadith-json, a JSON copy of sunnah.com), which
      the CDN doesn't have, converted to the same shape: Riyad as-Salihin, al-Adab al-Mufrad, the Shama'il, Bulugh
      al-Maram and Mishkat al-Masabih. They are read only from disk (hadith_lookup.LOCAL_ONLY). Their numbering is
      sunnah.com's: hadith-json files a book's opening section (its chapter 0: Riyad's "Book of Miscellany", 1-679,
      Mishkat's introduction) last, so it is put back first and the hadith numbered again from 1. Each hadith
      carries its section (the "books" !books lists), numbered from 1 in that order, with the names in the metadata.

    python scripts/fetch_hadith.py            (all fifteen)
    python scripts/fetch_hadith.py --other    (only the five from hadith-json)
"""
import json
import re
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from hadith_lookup import COLLECTION_DISPLAY, HADITH_CDN, LOCAL_DIR, LOCAL_ONLY   # noqa: E402

CACHE = Path(__file__).resolve().parent / ".cache" / "hadith_json"
HADITH_JSON = "https://raw.githubusercontent.com/AhmedBaset/hadith-json/main/db/by_book/other_books/"
OTHER_BOOKS = {"riyad": "riyad_assalihin", "adab": "aladab_almufrad", "shamail": "shamail_muhammadiyah",
               "bulugh": "bulugh_almaram", "mishkat": "mishkat_almasabih"}
UA = {"User-Agent": "ScriptureBot/1.0"}


def expect(ok: bool, message: str) -> None:
    if not ok:
        raise SystemExit(f"unexpected source layout: {message}")


def tidy(text: str) -> str:
    """The text's lines run together (the files keep the print's line breaks), without the stray full stop some
    end with ("...part of Iman.\\n\\n."), and without the print's soft hyphens (Mishkat's "un\\xad faithful")."""
    text = re.sub(r"\xad\s*", "", text or "")
    text = re.sub(r"\s+", " ", text).strip()
    return re.sub(r"(?<=[.!?\"”’)\]])\s+\.$", "", text)


def convert(key: str) -> dict:
    CACHE.mkdir(parents=True, exist_ok=True)
    f = CACHE / f"{OTHER_BOOKS[key]}.json"
    if not f.exists():
        f.write_bytes(urllib.request.urlopen(urllib.request.Request(HADITH_JSON + f.name, headers=UA), timeout=120).read())
        time.sleep(1)
    d = json.loads(f.read_text(encoding="utf-8"))
    hs = d["hadiths"]
    expect([h["idInBook"] for h in hs] == list(range(1, len(hs) + 1)), f"{key}: idInBook out of order")
    order = [c["id"] for c in d["chapters"]]
    if order and order[-1] == 0:                     # (the opening section filed last)
        order = [0] + order[:-1]
    names = {c["id"]: c["english"].strip() for c in d["chapters"]}
    used = []
    for cid in order:
        if any(h["chapterId"] == cid for h in hs):
            used.append(cid)
    expect(set(used) == {h["chapterId"] for h in hs}, f"{key}: hadith in a chapter not listed")
    section = {cid: n for n, cid in enumerate(used, start=1)}
    out = []
    for cid in used:
        for h in hs:
            if h["chapterId"] != cid:
                continue
            en = h.get("english") or {}
            text = tidy(" ".join(p for p in (tidy(en.get("narrator")), tidy(en.get("text"))) if p))
            if text:
                out.append({"hadithnumber": len(out) + 1, "section": section[cid], "text": text})
    expect(len(out) >= len(hs) - 5, f"{key}: {len(hs) - len(out)} hadith without English")
    return {"metadata": {"name": COLLECTION_DISPLAY[key], "source": "sunnah.com, via AhmedBaset/hadith-json",
                         "section": {str(section[c]): names[c] for c in used}},
            "hadiths": out}


def main() -> None:
    LOCAL_DIR.mkdir(parents=True, exist_ok=True)
    for key, name in COLLECTION_DISPLAY.items():
        if key in LOCAL_ONLY:
            data = convert(key)
            (LOCAL_DIR / f"eng-{key}.json").write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
            print(f"{name}: {len(data['hadiths'])} hadith, {len(data['metadata']['section'])} sections")
            continue
        if "--other" in sys.argv:
            continue
        url = f"{HADITH_CDN}eng-{key}.min.json"
        req = urllib.request.Request(url, headers=UA)
        data = urllib.request.urlopen(req, timeout=120).read()
        (LOCAL_DIR / f"eng-{key}.json").write_bytes(data)
        print(f"{name}: {len(data) / 1e6:.1f} MB")


if __name__ == "__main__":
    main()
