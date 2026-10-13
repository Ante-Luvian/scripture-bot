"""
Build data/psalter/ for !metrical: the Scottish Metrical Psalter of 1650 (the
Psalms in rhymed, regular verse for congregations to sing, still sung in
Scotland), and the traditional tunes it is sung to, in four parts.

Everything comes from the Open 1650 project (github.com/kadencartwright/open-1650):
the psalm texts (the Free Church of Scotland's received text), its tune for
each psalm, and 27 public-domain four-part tunes encoded as note events
(mostly from the Christian Classics Ethereal Hymnary). Each tune becomes a
MIDI file and then an Ogg file, as for the hymns, so the bot only attaches it.
Needs numpy and mido (hymn_audio.py) and ffmpeg on the PATH.

    python scripts/build_psalter.py
"""
import json
import re
import shutil
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

REPO = "kadencartwright/open-1650"
RAW = f"https://raw.githubusercontent.com/{REPO}/main/"
UA = {"User-Agent": "ScriptureBot/1.0 (https://github.com/Ante-Luvian/scripture-bot)"}
CACHE = ROOT / "scripts" / ".cache" / "open1650"
OUT = ROOT / "data" / "psalter"
BITRATE = "24k"


def _get(url: str) -> bytes:
    for wait in (5, 30, 0):
        try:
            return urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60).read()
        except Exception:
            if not wait:
                raise
            time.sleep(wait)


def _cached(path: str) -> bytes:
    """A file from the repository, downloaded once."""
    local = CACHE / path
    if not local.exists():
        local.parent.mkdir(parents=True, exist_ok=True)
        local.write_bytes(_get(RAW + path))
    return local.read_bytes()


def repo_files() -> list:
    listing = CACHE / "tree.json"
    if not listing.exists():
        CACHE.mkdir(parents=True, exist_ok=True)
        listing.write_bytes(_get(f"https://api.github.com/repos/{REPO}/git/trees/main?recursive=1"))
    return [t["path"] for t in json.loads(listing.read_text(encoding="utf-8"))["tree"] if t["type"] == "blob"]


# ── the words ───────────────────────────────────────────────────────────────

_FILE = re.compile(r"corpus/text/psalm-(\d{3})\.(primary|alternate)\.json$")
_SETTING = re.compile(r"corpus/music/settings/psalm-(\d{3})\.(primary|alternate)\.([a-z0-9-]+)\.json$")


def tidy(line: str) -> str:
    line = line.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
    return re.sub(r"\s+", " ", line).strip()


def read_psalm(raw: dict) -> dict:
    stanzas = []
    for s in raw["stanzas"]:
        lines = [tidy(l["text"]["normalized"]) for l in s["lines"]]
        stanzas.append({"verses": s.get("biblical_verses") or [], "lines": lines})
    return {
        "number": raw["psalm_number"],
        "version": raw["version"],
        "meter": raw["meter"]["pattern"],
        "meter_name": raw["meter"].get("name") or "",
        "first_line": tidy(raw["opening_line"]),
        "stanzas": stanzas,
    }


# ── the tunes ───────────────────────────────────────────────────────────────

def write_midi(tune: dict, path: Path) -> float:
    """Melody and its three harmony parts -> a four-channel MIDI file; returns seconds."""
    import mido
    ppq, bpm = tune["ppq"], tune.get("default_bpm") or 80
    parts = [tune["notes"]] + [tune["harmony"]["voices"][v] for v in ("alto", "tenor", "bass")
                               if v in (tune.get("harmony") or {}).get("voices", {})]
    mid = mido.MidiFile(ticks_per_beat=ppq)
    for channel, notes in enumerate(parts):
        track = mido.MidiTrack()
        if channel == 0:
            track.append(mido.MetaMessage("set_tempo", tempo=mido.bpm2tempo(bpm), time=0))
        track.append(mido.Message("program_change", program=19, channel=channel, time=0))
        events = []
        for n in notes:
            events.append((n["start_tick"], 1, n["midi"]))
            events.append((n["start_tick"] + n["duration_ticks"], 0, n["midi"]))
        now = 0
        for tick, on, pitch in sorted(events):        # note-offs before note-ons at the same tick
            track.append(mido.Message("note_on" if on else "note_off", note=pitch, velocity=80 if on else 0,
                                      channel=channel, time=tick - now))
            now = tick
        mid.tracks.append(track)
    path.parent.mkdir(parents=True, exist_ok=True)
    mid.save(path)
    return round(mid.length, 1)


def read_tune(raw: dict) -> dict:
    src = raw.get("source") or {}
    return {
        "title": raw["title"],
        "meter": raw["meter"],
        "attribution": src.get("attribution") or "",
        "source": src.get("provider") or "",
    }


def render_ogg(midi: Path, ogg: Path, title: str) -> None:
    import hymn_audio
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        sys.exit("ffmpeg isn't on the PATH")
    ogg.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run([ffmpeg, "-loglevel", "error", "-y", "-f", "wav", "-i", "-", "-ac", "1",
                    "-c:a", "libopus", "-b:a", BITRATE, "-metadata", f"title={title}", str(ogg)],
                   input=hymn_audio.render(midi), check=True)


def main():
    files = repo_files()
    settings = {}
    for f in files:
        m = _SETTING.search(f)
        if m:
            settings.setdefault((int(m.group(1)), m.group(2)), m.group(3))

    psalms = []
    for f in sorted(files):
        if _FILE.search(f):
            psalms.append(read_psalm(json.loads(_cached(f))))

    tunes = {}
    for f in sorted(files):
        m = re.search(r"corpus/music/tunes/([a-z0-9-]+)\.json$", f)
        if m:
            raw = json.loads(_cached(f))
            tune = read_tune(raw)
            tune["seconds"] = write_midi(raw, OUT / "midi" / f"{m.group(1)}.mid")
            tunes[m.group(1)] = tune

    # the project's tune for each psalm; one of the same meter where it has none
    by_meter = {}
    for tid, t in tunes.items():
        by_meter.setdefault(t["meter"], tid)
    unset = []
    for p in psalms:
        tid = settings.get((p["number"], p["version"])) or by_meter.get(p["meter"])
        p["tune"] = tid if tid in tunes else ""
        if not p["tune"]:
            unset.append(f"{p['number']}{'b' if p['version'] == 'alternate' else ''} ({p['meter']})")

    for tid, t in tunes.items():
        ogg = OUT / "audio" / f"{tid}.ogg"
        if not ogg.exists() or "--all" in sys.argv:
            render_ogg(OUT / "midi" / f"{tid}.mid", ogg, t["title"])
    used = {p["tune"] for p in psalms}
    for stale in (OUT / "audio").glob("*.ogg"):
        if stale.stem not in tunes:
            stale.unlink()

    (OUT / "psalter.json").write_text(json.dumps({"psalms": psalms, "tunes": tunes}, ensure_ascii=False, indent=1),
                                      encoding="utf-8")
    size = sum(f.stat().st_size for f in (OUT / "audio").glob("*.ogg"))
    print(f"{len(psalms)} psalm versions, {len(tunes)} tunes ({len(used & set(tunes))} used), "
          f"{size / 1e6:.1f} MB of audio")
    if unset:
        print("No tune for:", ", ".join(unset))


if __name__ == "__main__":
    main()
