"""
Build script: downloads the merged Easton's (1897) + Smith's (1863) Bible
Dictionary dataset from github.com/neuu-org/bible-dictionary-dataset into
data/dictionary/bible_dictionary.json.

Both source dictionaries are public domain (per the dataset's own README);
the dataset/parsing scripts themselves are CC BY 4.0 (github.com/neuu-org/
bible-dictionary-dataset), attributed here accordingly. Source XML for both
dictionaries originates from CCEL (Christian Classics Ethereal Library) ThML
markup, via jncraton/ccel-paragraphs.

Downloads the 25 alphabetical files in data/01_parsed/ (a.json .. z.json,
merged by term across both dictionaries) and combines them into one file.

Downloads its own source -- run from anywhere:
    python deprecated/build_bible_dictionary.py
"""
import json
import urllib.request
from pathlib import Path

BASE_URL = "https://raw.githubusercontent.com/neuu-org/bible-dictionary-dataset/main/data/01_parsed/"
LETTERS = "abcdefghijklmnopqrstuvwyz"  # dataset has no x.json (no terms begin with X)
OUT_DIR = Path(__file__).parent.parent / "data" / "dictionary"
OUT_PATH = OUT_DIR / "bible_dictionary.json"


def _fetch_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": "ScriptureBot/1.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))


def main():
    entries = {}
    for letter in LETTERS:
        data = _fetch_json(f"{BASE_URL}{letter}.json")
        entries.update(data)
        print(f"{letter}.json: {len(data)} entries")

    payload = {
        "source": (
            "Easton's Bible Dictionary (1897) and Smith's Bible Dictionary "
            "(1863), both public domain. Dataset compiled from CCEL ThML "
            "sources by github.com/neuu-org/bible-dictionary-dataset "
            "(CC BY 4.0)."
        ),
        "entries": entries,
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nWrote {OUT_PATH} -- {len(entries)} total entries")


if __name__ == "__main__":
    main()
