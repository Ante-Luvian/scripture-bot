"""
theoi.com's Loeb transcriptions, cached in scripts/.cache/theoi/ (a page fetched once; a pause between fetches).

    python scripts/fetch_theoi.py OvidFasti1 [...]       (or imported: fetch("OvidFasti1"), contents("OvidFasti1"))
"""
import re
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "scripts" / ".cache" / "theoi"
UA = "ScriptureBot corpus builder (personal Discord bot)"
_last = [0.0]


def fetch(page: str) -> str:
    path = CACHE / f"{page}.html"
    if path.exists():
        return path.read_text(encoding="utf-8")
    wait = 2 - (time.time() - _last[0])
    if wait > 0:
        time.sleep(wait)
    req = urllib.request.Request(f"https://www.theoi.com/Text/{page}.html", headers={"User-Agent": UA})
    t = urllib.request.urlopen(req, timeout=120).read().decode("utf-8", "replace")
    _last[0] = time.time()
    CACHE.mkdir(parents=True, exist_ok=True)
    path.write_text(t, encoding="utf-8")
    return t


def contents(page: str) -> list:
    """The pages of a work, in order, from the contents box on its first page."""
    t = fetch(page)
    box = re.search(r'(?is)<div id="book-contents">(.*?)</div>', t)
    pages = re.findall(r'href="(?:https://www\.theoi\.com/Text/)?([A-Za-z0-9]+)\.html', box.group(1)) if box else []
    return list(dict.fromkeys(pages)) or [page]


if __name__ == "__main__":
    for p in sys.argv[1:]:
        print(p, contents(p))
