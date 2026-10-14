"""
Builds data/hymns/sacred_harp.json and its audio (data/hymns/audio/harp/): every
song in The Sacred Harp, 1991 Edition, the American shape-note songbook, sung.

    python scripts/build_sacred_harp.py          # needs ffmpeg; about 550 songs, cached as it goes

Words, poet, composer and meter: fasola.org's index of the 1991 edition
(fasola.org/indexes/1991/?p=<page>). Audio: Sacred Harp Bremen's synthesised
four-part recordings with the words sung (sh1991.sacredharpbremen.org, the
"synth-text" track of each song), re-encoded to Ogg Opus. Songs are matched by
their page number in the book (47b, 101t...). Everything downloaded is kept in
scripts/.cache/sacredharp, so a re-run only fetches what's missing.
"""
import html
import json
import re
import shutil
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CACHE = Path(__file__).resolve().parent / ".cache" / "sacredharp"
OUT = ROOT / "data" / "hymns" / "sacred_harp.json"
AUDIO = ROOT / "data" / "hymns" / "audio" / "harp"
UA = {"User-Agent": "ScriptureBotCorpusBuilder/1.0 (Discord bot; low-volume one-off import)"}
BREMEN = "https://sh1991.sacredharpbremen.org/"
FASOLA = "https://fasola.org/indexes/1991/?p="
BITRATE = "32k"

# what the index doesn't say
OVERRIDES = {
    "117": {"also": ["Hail the Day So Long Expected"],
            "author": "From Millennial Praises (the Shaker hymnal, 1813); attributed to Richard McNemar",
            "scripture": ["Revelation 18:2", "Revelation 18:21"], "topics": ["Second Coming"]},
}


def fetch(url: str, cache: Path) -> bytes:
    if cache.exists():
        return cache.read_bytes()
    for attempt in range(3):
        try:
            data = urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=120).read()
            break
        except Exception:
            if attempt == 2:
                raise
            time.sleep(5)
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_bytes(data)
    time.sleep(0.5)                                  # gently
    return data


def songs() -> list:
    """[(page, Bremen song page url)] in book order."""
    home = fetch(BREMEN, CACHE / "bremen-index.html").decode("utf-8", "replace")
    found = dict((m.group(2), m.group(1)) for m in
                 re.finditer(r'href="(https://sh1991\.sacredharpbremen\.org/((\d+)[tb]?)-[^"/]+/)"', home))
    return sorted(found.items(), key=lambda kv: (int(re.match(r"\d+", kv[0]).group()), kv[0][-1] == "b"))


def details(page: str) -> "dict | None":
    """Title, words, poet, composer, meter from fasola.org."""
    text = fetch(FASOLA + page, CACHE / "fasola" / f"{page}.html").decode("utf-8", "replace")
    title = re.search(r"<h2>\s*\S+\s+(.*?)</h2>", text, re.S)
    lyrics = re.search(r'<div class="lyrics">(.*?)</div>', text, re.S)
    if not title or not lyrics:
        return None

    def credit(kind):
        m = re.search(rf'<p class="details {kind}">\w+:\s*(.*?)</p>', text, re.S)
        return html.unescape(re.sub(r"<[^>]+>", "", m.group(1))).strip() if m else ""

    body = html.unescape(re.sub(r"<(?!br)[^>]+>", "", lyrics.group(1)))
    stanzas = [re.sub(r"[ \t]*<br\s*/?>[ \t]*\n?", "\n", s).strip() for s in re.split(r"<br\s*/?>\s*<br\s*/?>", body)]
    stanzas = [re.sub(r"[ \t]+", " ", s) for s in stanzas if s.strip()]
    meter = credit("meter")
    return {"title": html.unescape(re.sub(r"<[^>]+>", "", title.group(1))).strip(), "stanzas": stanzas,
            "author": credit("words"), "composer": credit("music"),
            "meter": re.sub(r"^.*?\(([\d,]+)\)$|^Particular Meter:\s*", r"\1", meter).replace(",", ".") or meter}


def recording(page: str, url: str) -> "Path | None":
    """The sung four-part track, from the song's Bremen page."""
    text = fetch(url, CACHE / "bremen" / f"{page}.html").decode("utf-8", "replace")
    mp3 = re.search(r'https://[^"\']+?-synth-text\.mp3', text)
    if not mp3:
        return None
    return_path = CACHE / "mp3" / mp3.group().rsplit("/", 1)[1]
    fetch(mp3.group(), return_path)
    return return_path


def main():
    if not shutil.which("ffmpeg"):
        sys.exit("ffmpeg isn't on the PATH")
    AUDIO.mkdir(parents=True, exist_ok=True)
    taken = {h["title"].lower() for h in json.loads((ROOT / "data" / "hymns" / "hymns.json").read_text(encoding="utf-8"))["hymns"]}
    more = ROOT / "data" / "hymns" / "more_hymns.json"
    if more.exists():
        taken |= {h["title"].lower() for h in json.loads(more.read_text(encoding="utf-8"))["hymns"]}
    hymns, skipped = [], []
    for page, url in songs():
        try:
            info = details(page)
            mp3 = recording(page, url) if info else None
        except Exception as e:
            skipped.append((page, str(e)[:60]))
            continue
        if not info or not mp3:
            skipped.append((page, "no words" if not info else "no sung track"))
            continue
        out = AUDIO / f"sh-{page}.ogg"
        if not out.exists() or "--all" in sys.argv:
            subprocess.run([shutil.which("ffmpeg"), "-loglevel", "error", "-y", "-i", str(mp3), "-ac", "1",
                            "-c:a", "libopus", "-b:a", BITRATE, "-metadata", f"title={info['title']}", str(out)], check=True)
        seconds = float(subprocess.run([shutil.which("ffprobe") or "ffprobe", "-v", "error", "-show_entries",
                                        "format=duration", "-of", "csv=p=0", str(out)],
                                       capture_output=True, text=True).stdout.strip() or 0)
        title = info["title"]
        if title.lower() in taken:
            title = f"{title} (Sacred Harp)"
        taken.add(title.lower())
        extra = OVERRIDES.get(page, {})
        hymns.append({
            "title": title, "also": extra.get("also", []) + [f"Sacred Harp {page}"],
            "author": extra.get("author", info["author"]), "translator": "",
            "composer": info["composer"], "tune": info["title"], "meter": info["meter"],
            "scripture": extra.get("scripture", []), "topics": ["Sacred Harp", *extra.get("topics", [])],
            "stanzas": info["stanzas"], "refrain": "", "first_line": info["stanzas"][0].split("\n")[0],
            "source": f"The Sacred Harp, 1991 Edition, no. {page} (words via fasola.org); sung by Sacred Harp Bremen",
            "audio": f"harp/{out.name}", "audio_kind": "sung", "seconds": round(seconds), "sacred_harp": page,
        })
        print(page, title, flush=True)
    OUT.write_text(json.dumps({"hymns": hymns}, ensure_ascii=False, indent=1), encoding="utf-8")
    size = sum(f.stat().st_size for f in AUDIO.glob("*.ogg"))
    print(f"wrote {len(hymns)} songs; audio {size / 1e6:.1f} MB; skipped {len(skipped)}: {skipped}")


if __name__ == "__main__":
    main()
