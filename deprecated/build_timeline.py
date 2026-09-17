"""
Build script: converts James Ussher's "Annals of the World" (1658 English
translation, public domain) into data/timeline/ussher_timeline.json.

Source: the `usshraw` dataset from github.com/DataSciNet/ussherR (an R
package; MIT-licensed per its DESCRIPTION), which transcribes Ussher's dated
chronological entries with their original numbering and inline scripture
citations intact. A sibling "cleaned" dataset in the same package
(`ussher.rda`) turned out to have a real data-quality defect -- most inline
numbers (day-of-month, ages, verse numbers) were stripped out, e.g. "the 23rd
day of October" became "the  rd day of October" -- so this script uses the
less-processed `usshraw` dataset instead, which does not have that problem.

Only entries with an actual BC/AD date are kept (1,288 of the raw dataset's
6,998 entries) -- the rest are connective narrative between dated milestones
with no date of their own in the source, and this script does not guess a
date for them.

Requires `pyreadr` (pip install pyreadr) to read the .rda file.

Downloads its own source -- run from anywhere:
    python deprecated/build_timeline.py
"""
import json
import re
import urllib.request
from pathlib import Path

import pyreadr

SOURCE_URL = "https://raw.githubusercontent.com/DataSciNet/ussherR/main/data/usshraw.rda"
OUT_DIR = Path(__file__).parent.parent / "data" / "timeline"
OUT_PATH = OUT_DIR / "ussher_timeline.json"
RAW_CACHE = Path(__file__).parent / "_usshraw_cache.rda"

YEAR_RE = re.compile(r"([\d ]+?)\s*(BC|AD)\b")
LEADING_NUM_RE = re.compile(r"^\s*\d+\.\s*")


def main():
    req = urllib.request.Request(SOURCE_URL, headers={"User-Agent": "ScriptureBot/1.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        RAW_CACHE.write_bytes(r.read())

    result = pyreadr.read_r(str(RAW_CACHE))
    df = result["usshraw"]
    RAW_CACHE.unlink()

    entries = []
    for _, row in df.iterrows():
        dating = row["Dating"]
        if not dating or dating == "DateBlank":
            continue
        m = YEAR_RE.search(dating)
        if not m:
            continue
        numstr, era = m.group(1).replace(" ", ""), m.group(2)
        year = int(numstr)
        year_signed = -year if era == "BC" else year

        text = LEADING_NUM_RE.sub("", row["Event"].strip())
        epoch = row["Epoch"] if row["Epoch"] != "AgeBlank" else ""

        entries.append({
            "year": year_signed,
            "year_display": f"{year} {era}",
            "epoch": epoch,
            "text": text,
        })

    entries.sort(key=lambda e: e["year"])

    payload = {
        "source": (
            "James Ussher, Annals of the World (1658 English translation, "
            "public domain). Dated entries only, via the usshraw dataset "
            "in github.com/DataSciNet/ussherR (MIT-licensed)."
        ),
        "entries": entries,
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {OUT_PATH} -- {len(entries)} dated entries "
          f"({entries[0]['year_display']} to {entries[-1]['year_display']})")


if __name__ == "__main__":
    main()
