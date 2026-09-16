"""
Build script: converts Nave's Topical Bible (Orville J. Nave, public domain,
early 1900s) into data/topics/naves_topical.json for the scripture bot's
!topic command.

Source: https://github.com/BradyStephenson/bible-data (CC BY 4.0),
NavesTopicalDictionary.csv -- a browsable outline per subject with embedded
scripture citations, not a verse-to-verse index like the TSK cross-references.
Entries are stored and displayed as-is (matching how Nave's is actually used
-- a topical reading outline, not a database to mine citations out of).

Known limitation of the source CSV: one entry ("JESUS, THE CHRIST", by far
the largest topic) is truncated at exactly 32767 characters -- the classic
Excel/Sheets per-cell character limit, hit when this dataset was exported.
That's flagged in the stored entry itself rather than silently shipped.

Downloads its own source -- run from anywhere:
    python deprecated/build_topics.py
"""
import csv
import io
import json
import re
import urllib.request
from pathlib import Path

SOURCE_URL = "https://raw.githubusercontent.com/BradyStephenson/bible-data/main/NavesTopicalDictionary.csv"
OUT_DIR = Path(__file__).parent.parent / "data" / "topics"
OUT_PATH = OUT_DIR / "naves_topical.json"

TRUNCATED_AT_SOURCE = 32767  # Excel/Sheets per-cell character limit


def main():
    req = urllib.request.Request(SOURCE_URL, headers={"User-Agent": "ScriptureBot/1.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        raw = r.read().decode("utf-8-sig")

    reader = csv.DictReader(io.StringIO(raw))
    result: dict[str, str] = {}
    truncated_topics = []
    for row in reader:
        subject = row["subject"].strip()
        entry = row["entry"].strip()
        if not subject or not entry:
            continue
        # Internal topic-cross-reference IDs from the original numbering scheme
        # (e.g. "[2601]GOD, LOVE OF") -- meaningless without that number->topic
        # key, which this CSV doesn't include, and the topic name right after
        # the bracket already reads fine on its own without it.
        entry = re.sub(r"\[\d+\](?=[A-Z])", "", entry)
        if len(entry) == TRUNCATED_AT_SOURCE:
            entry += "\n\n[Entry truncated at the source dataset's export limit -- incomplete beyond this point.]"
            truncated_topics.append(subject)
        result[subject] = entry

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
    print(f"Wrote {OUT_PATH} — {len(result)} topics")
    if truncated_topics:
        print(f"Truncated at source (flagged in the entry text): {truncated_topics}")


if __name__ == "__main__":
    main()
