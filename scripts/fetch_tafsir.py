"""
Download English Qur'an commentaries (tafsir) into data/tafsir/, one file each, for the 📖 Commentary button under
Qur'an verses (bot_commands/tafsir.py). Not kept in git: this script fetches them again (~25 MB).

From spa5k's tafsir_api (github.com/spa5k/tafsir_api, served by jsDelivr), only the editions whose text checked out
(2026-11-10): its altafsir.com copies are scrambled (the "Jalalayn" there is Kashani's commentary, the Wahidi and
Kashani files for surah 1 are both al-Qushayri) or have hundreds of characters lost as U+FFFD, so the Jalalayn
and Ibn Kathir come from its copies of quran.com's QUL, which are clean.

    jalalayn   Tafsir al-Jalalayn, trans. Feras Hamza (QUL resource 573)
    ibnkathir  Tafsir Ibn Kathir (abridged), Darussalam (QUL resource 35); one commentary covers a run of verses,
               so each run is kept once, on its first verse, with the verses it covers
    ibnabbas   Tanwir al-Miqbas min Tafsir Ibn 'Abbas, trans. Mokrane Guezzou (from altafsir.com)

Each file: {"name", "source", "surahs": {surah: {ayah: text}}} -- an ayah with nothing of its own isn't there.

    python scripts/fetch_tafsir.py
"""
import json
import re
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CACHE = Path(__file__).resolve().parent / ".cache" / "tafsir"
OUT = ROOT / "data" / "tafsir"
CDN = "https://cdn.jsdelivr.net/gh/spa5k/tafsir_api@main/tafsir/"
UA = {"User-Agent": "ScriptureBot corpus builder (a personal Discord bot)"}
EDITIONS = {
    "jalalayn": ("tafsir-al-jalalayn", "Tafsir al-Jalalayn", "al-Mahalli and al-Suyuti, trans. Feras Hamza"),
    "ibnkathir": ("en-tafisr-ibn-kathir", "Tafsir Ibn Kathir", "Ibn Kathir, abridged (Darussalam)"),
    "ibnabbas": ("en-tafsir-ibn-abbas", "Tanwir al-Miqbas", "attributed to Ibn 'Abbas, trans. Mokrane Guezzou"),
}


def expect(ok: bool, message: str) -> None:
    if not ok:
        raise SystemExit(f"unexpected source layout: {message}")


def rows(slug: str, surah: int) -> list:
    CACHE.mkdir(parents=True, exist_ok=True)
    f = CACHE / f"{slug}_{surah}.json"
    if not f.exists():
        f.write_bytes(urllib.request.urlopen(urllib.request.Request(f"{CDN}{slug}/{surah}.json", headers=UA),
                                             timeout=60).read())
        time.sleep(0.3)
    d = json.loads(f.read_text(encoding="utf-8"))
    return d["ayahs"] if isinstance(d, dict) else d


def tidy(text: str) -> str:
    text = re.sub(r"[ \t]+", " ", (text or "").replace("\r", "")).strip()
    return re.sub(r"\n{3,}", "\n\n", re.sub(r" *\n *", "\n", text))


def mend(text: str) -> str:
    """Characters the Ibn 'Abbas copy lost as U+FFFD, which their place tells: "vis-�-vis" is à; one against a
    bracket ("(�so that", "mankind�)", "[�]") or between spaces is an ellipsis (a verse quoted in part); one before a
    word opens a quotation; one after a word closes the quotation that is open (even before a bracket: "(say not
    “Three”)"), and if none is open, it's an ellipsis."""
    text = text.replace("vis-�-vis", "vis-à-vis")
    out, open_quote = [], False
    for i, ch in enumerate(text):
        if ch != "�":
            out.append(ch)
            if ch in "“”":
                open_quote = ch == "“"
            continue
        before, after = text[i - 1] if i else " ", text[i + 1] if i + 1 < len(text) else " "
        if before.isspace() and after.isspace():
            out.append("…")
        elif open_quote and not before.isspace():
            out.append("”")
            open_quote = False
        elif before in "([" or after in ")]":
            out.append("…")
        elif before.isspace() or before in "“‘\"'—-:":
            out.append("“")
            open_quote = True
        else:
            out.append("…")
    return "".join(out)


def build(key: str) -> dict:
    slug, name, source = EDITIONS[key]
    surahs = {}
    for s in range(1, 115):
        verses, last = {}, None
        for r in sorted(rows(slug, s), key=lambda r: int(r["ayah"])):
            expect(int(r.get("surah", s)) == s, f"{key} {s}: a row of surah {r.get('surah')}")
            text = tidy(mend(r.get("text") or ""))
            if not text:
                continue
            a = int(r["ayah"])
            if last and text == verses[last]["text"]:          # (Ibn Kathir: one commentary for a run of verses)
                verses[last]["to"] = a
                continue
            verses[a] = {"text": text, "to": a}
            last = a
        surahs[str(s)] = {str(a): (v["text"] if v["to"] == a else {"text": v["text"], "to": v["to"]})
                          for a, v in verses.items()}
    return {"name": name, "source": source, "surahs": surahs}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for key in EDITIONS:
        data = build(key)
        n = sum(len(v) for v in data["surahs"].values())
        bad = json.dumps(data, ensure_ascii=False).count("�")
        print(f"  {data['name']}: {n} entries")
        expect(not bad, f"{key}: {bad} broken characters left")
        (OUT / f"{key}.json").write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
