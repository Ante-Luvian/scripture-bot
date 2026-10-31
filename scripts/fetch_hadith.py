"""
Download the English hadith collections (fawazahmed0's hadith-api, the same source !verse reads online) into
data/hadith/, one file a collection (~20 MB in all). With them there, !verse reads hadith from disk and Ask the
library can search them. Not kept in git: this script fetches them again.

    python scripts/fetch_hadith.py
"""
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from hadith_lookup import COLLECTION_DISPLAY, HADITH_CDN, LOCAL_DIR   # noqa: E402


def main() -> None:
    LOCAL_DIR.mkdir(parents=True, exist_ok=True)
    for key, name in COLLECTION_DISPLAY.items():
        url = f"{HADITH_CDN}eng-{key}.min.json"
        req = urllib.request.Request(url, headers={"User-Agent": "ScriptureBot/1.0"})
        data = urllib.request.urlopen(req, timeout=120).read()
        (LOCAL_DIR / f"eng-{key}.json").write_bytes(data)
        print(f"{name}: {len(data) / 1e6:.1f} MB")


if __name__ == "__main__":
    main()
