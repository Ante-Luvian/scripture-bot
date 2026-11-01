"""
Download pages of Bill Thayer's LacusCurtius (penelope.uchicago.edu/Thayer) into scripts/.cache/latin/, one at a
time: the site is slow (a page can take a minute and a half), so this runs ahead of the builder.

    python scripts/fetch_lacus.py E/Roman/Texts/Cato/De_Agricultura/A*.html ...
"""
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "scripts" / ".cache" / "latin"
BASE = "https://penelope.uchicago.edu/Thayer/"
UA = {"User-Agent": "ScriptureBotCorpusBuilder/1.0 (Discord bot; low-volume one-off import)"}


def cached_name(page: str) -> str:
    return page.replace("/", "_").replace("*", "_")


def fetch(page: str) -> str:
    path = CACHE / cached_name(page)
    if not path.exists():
        CACHE.mkdir(parents=True, exist_ok=True)
        for attempt in range(3):
            try:
                data = urllib.request.urlopen(urllib.request.Request(BASE + page, headers=UA), timeout=300).read()
                path.write_bytes(data)
                break
            except Exception as e:
                if attempt == 2:
                    raise
                print(f"  retry {page}: {e}")
                time.sleep(10)
    return path.read_text(encoding="utf-8", errors="replace")


if __name__ == "__main__":
    for page in sys.argv[1:]:
        started = time.time()
        fetch(page)
        print(f"{page}: {time.time() - started:.0f}s", flush=True)
