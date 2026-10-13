"""
Render every hymn tune (data/hymns/midi/) to an Ogg Opus file in
data/hymns/audio/, which Discord plays in the chat. Done once here, so the
bot itself only attaches a file. Needs numpy and mido (hymn_audio.py) and
ffmpeg on the PATH. Run after scripts/build_hymns.py:

    python scripts/render_hymn_audio.py          # only tunes not yet rendered
    python scripts/render_hymn_audio.py --all    # all of them again
"""
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import hymn_audio  # noqa: E402

HYMNS = ROOT / "data" / "hymns" / "hymns.json"
MIDI = ROOT / "data" / "hymns" / "midi"
AUDIO = ROOT / "data" / "hymns" / "audio"
BITRATE = "24k"                     # mono Opus: clean enough for an organ, ~3-4 KB a second


def audio_name(midi_name: str) -> str:
    return Path(midi_name).stem + ".ogg"


def main():
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        sys.exit("ffmpeg isn't on the PATH")
    AUDIO.mkdir(parents=True, exist_ok=True)
    hymns = json.loads(HYMNS.read_text(encoding="utf-8"))["hymns"]
    wanted = {audio_name(h["midi"]) for h in hymns if h.get("midi")}
    done = 0
    for h in hymns:
        if not h.get("midi"):
            continue
        out = AUDIO / audio_name(h["midi"])
        if out.exists() and "--all" not in sys.argv:
            continue
        wav = hymn_audio.render(MIDI / h["midi"])
        subprocess.run([ffmpeg, "-loglevel", "error", "-y", "-f", "wav", "-i", "-", "-ac", "1",
                        "-c:a", "libopus", "-b:a", BITRATE, "-metadata", f"title={h['title']}", str(out)],
                       input=wav, check=True)
        done += 1
    for stale in AUDIO.glob("*.ogg"):
        if stale.name not in wanted:
            stale.unlink()
    total = sum(f.stat().st_size for f in AUDIO.glob("*.ogg"))
    print(f"Rendered {done}; {len(wanted)} tunes, {total / 1e6:.1f} MB in {AUDIO}")


if __name__ == "__main__":
    main()
