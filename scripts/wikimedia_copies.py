"""
Local copies of the Wikimedia Commons pictures the bot shows (Doré, Blake, the illustrated editions).

Until November 2026 the bot gave Discord each picture's address on upload.wikimedia.org and Discord
fetched it. Then Wikimedia began refusing requests for full-size originals (HTTP 429: "use thumbnail
images in sizes listed on https://w.wiki/GHai"), and the pictures stopped appearing: !dore, !blake
and the 🖌️ buttons showed embeds with no image. Now each picture is fetched once here, as one of
Wikimedia's standard thumbnail sizes, and the bot attaches the file to its message.

For every entry with an "image" on Wikimedia and no "file" of its own on disk (the Dante plates cut
out of their scans keep theirs), this saves a JPEG at most 1200 px wide in the folder given and
writes its path into the entry's "copy". (Not "file": in Blake's data that's the Commons title.)
The bot attaches "file" if it's a file here, else "copy", else falls back to the address. The
pictures are rebuilt here, so they stay out of git (.gitignore).

    python scripts/wikimedia_copies.py data/blake/plates.json data/blake/copies
"""
import hashlib
import io
import json
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
UA = {"User-Agent": "ScriptureBotCorpusBuilder/1.0 (Discord bot; low-volume one-off import)"}
THUMB_WIDTHS = (1280, 960, 500)          # Wikimedia's standard widths (https://w.wiki/GHai), largest first
MAX_WIDTH = 1200


def thumbnail_url(url: str, width: int) -> str:
    """upload.wikimedia.org/wikipedia/commons/a/ab/Name.jpg -> .../commons/thumb/a/ab/Name.jpg/<width>px-Name.jpg"""
    url = url.split("?")[0]
    if "/thumb/" in url:
        return re.sub(r"/\d+px-", f"/{width}px-", url)
    head, name = url.rsplit("/", 1)
    return f"{head.replace('/commons/', '/commons/thumb/', 1)}/{name}/{width}px-{name}"   # (JPEG, PNG, GIF alike)


def fetch_thumbnail(url: str, title: str = "") -> bytes:
    """The largest standard thumbnail there is (a narrow original has no 1280 px one), paced, and
    waiting out a 429 rather than pressing on."""
    for width in THUMB_WIDTHS:
        thumb = thumbnail_url(url, width)
        for attempt in range(6):
            try:
                return urllib.request.urlopen(urllib.request.Request(thumb, headers=UA), timeout=120).read()
            except urllib.error.HTTPError as e:
                if e.code == 429:
                    print(f"  {title}: 429, waiting {60 * (attempt + 1)} s")
                    time.sleep(60 * (attempt + 1))
                    continue
                break                                   # (400/404: no thumbnail that wide; try a smaller one)
            except Exception as e:
                print(f"  {title}: {e}, retrying")
                time.sleep(20 * (attempt + 1))
    raise SystemExit(f"couldn't fetch a thumbnail of {url}")


def _entries(node):
    """Every dict in the data with an "image" on Wikimedia (upload.wikimedia.org's originals, or
    thumb.wikimedia.org's thumbnails, which most of the Doré Bible plates point at)."""
    if isinstance(node, dict):
        if isinstance(node.get("image"), str) and re.match(r"https://(upload|thumb)\.wikimedia\.org/", node["image"]):
            yield node
        for value in node.values():
            yield from _entries(value)
    elif isinstance(node, list):
        for value in node:
            yield from _entries(value)


def local_copies(data, folder: Path) -> int:
    """Give each picture in `data` a local copy in `folder` (see the module docstring). Returns how many
    were fetched; entries whose copy already exists are only pointed at it."""
    from PIL import Image
    folder.mkdir(parents=True, exist_ok=True)
    fetched = 0
    for entry in _entries(data):
        own = entry.get("file")
        if own and (ROOT / own).is_file():
            continue                                    # (a file of its own, like a cut-out Dante plate)
        url = entry["image"].split("?")[0]
        out = folder / f"{hashlib.md5(url.encode()).hexdigest()[:12]}.jpg"
        if not out.exists():
            img = Image.open(io.BytesIO(fetch_thumbnail(url, entry.get("title", url)))).convert("RGB")
            if img.width > MAX_WIDTH:
                img = img.resize((MAX_WIDTH, round(img.height * MAX_WIDTH / img.width)), Image.LANCZOS)
            img.save(out, quality=85)
            fetched += 1
            time.sleep(2)
        entry["copy"] = out.relative_to(ROOT).as_posix()
    return fetched


def copy_file(path: Path, folder: Path) -> None:
    """Fetch the copies for one data file, and write the "file" paths back into it (same layout)."""
    raw = path.read_bytes().decode("utf-8")
    data = json.loads(raw)
    n = local_copies(data, folder)
    plain = raw.replace("\r\n", "\n")                   # (the data files may have Windows line endings)
    second = plain.split("\n", 2)[1] if plain.count("\n") >= 2 else ""
    indent = (len(second) - len(second.lstrip(" "))) or None if plain.startswith("{\n") else None
    text = json.dumps(data, ensure_ascii=False, indent=indent)
    if plain.endswith("\n"):
        text += "\n"
    if "\r\n" in raw:
        text = text.replace("\n", "\r\n")
    path.write_bytes(text.encode("utf-8"))
    total = sum(1 for e in _entries(data) if local_picture(e))
    print(f"{path.relative_to(ROOT)}: fetched {n}; {total} of {sum(1 for _ in _entries(data))} pictures are here")


def local_picture(entry: dict) -> "Path | None":
    """The picture file to attach for an entry: its own "file" if that's a file here, else its "copy"."""
    for key in ("file", "copy"):
        if entry.get(key) and (ROOT / entry[key]).is_file():
            return ROOT / entry[key]
    return None


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit(__doc__)
    copy_file(ROOT / sys.argv[1], ROOT / sys.argv[2])
