"""
Build script: converts OpenScriptures' Strong's Hebrew and Greek dictionaries
(https://github.com/openscriptures/strongs, CC-BY-SA, derived from James
Strong's 1890/1894 public-domain original) into a single local
data/strongs/strongs_dictionary.json for the scripture bot's !strong command.

Replaces the previous live-only bolls.life dictionary fetch with a local,
always-available copy (bolls.life stays as a fallback for any number this
dataset happens to miss).

Downloads its own source -- run from anywhere:
    python deprecated/build_strongs.py
"""
import json
import urllib.request
from pathlib import Path

HEBREW_URL = "https://raw.githubusercontent.com/openscriptures/strongs/master/hebrew/strongs-hebrew-dictionary.js"
GREEK_URL = "https://raw.githubusercontent.com/openscriptures/strongs/master/greek/strongs-greek-dictionary.js"
OUT_DIR = Path(__file__).parent.parent / "data" / "strongs"
OUT_PATH = OUT_DIR / "strongs_dictionary.json"


def fetch_js_object(url: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": "ScriptureBot/1.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        text = r.read().decode("utf-8")
    body = text.split("module.exports")[0]
    start = body.index("{")
    end = body.rindex("}")
    return json.loads(body[start:end + 1])


def main():
    hebrew = fetch_js_object(HEBREW_URL)
    greek = fetch_js_object(GREEK_URL)

    result = {}
    for key, entry in {**hebrew, **greek}.items():
        result[key] = {
            "lexeme": entry.get("lemma", ""),
            "transliteration": entry.get("xlit") or entry.get("translit") or "",
            "pronunciation": entry.get("pron", ""),
            "short_definition": entry.get("kjv_def", ""),
            "definition": (entry.get("strongs_def") or "").strip(),
            "derivation": entry.get("derivation", ""),
        }

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
    print(f"Wrote {OUT_PATH} — {len(hebrew)} Hebrew + {len(greek)} Greek = {len(result)} entries")


if __name__ == "__main__":
    main()
