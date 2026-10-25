"""
Tunes for the Child Ballads (!ballad), from the Digital Tradition (Mudcat's folk song database, Spring 2002
edition, mudcat.org/download/DTSpring2002MSDOS.zip): its songs say which Child ballad they are ("Child #12"), and
about half have a tune, kept in TUNE.ZIP in SongWright IV's text notation. Each becomes a MIDI file and an Ogg
file (as the hymns are), so the bot only attaches it. Also each ballad's recording in a YouTube playlist of them
in order ("Child's Ballads (in Order)", the owner's find), matched to the ballad by number and title.

SongWright's notation, as worked out from the player (PERFORM.EXE's tables) and checked on every tune (--check):
    N- title   K- key   B- metre   S- speed (crotchets a minute)   F- source   L- the words under the notes
    M- a line of melody: its first character is layout (ignored); then notes such as "E-8":
       pitch  <=>?@AB = C3 D3 E3 F3 G3 A3 B3,  CDEFGab = C4 .. B4,  cdefghi = C5 .. B5,  jklmnop = C6 .. B6
       accidental  "-" as the key says, "#" sharp, "&" flat, "%" natural
       length  1 semibreve, 2 minim, 3 dotted minim, 4 crotchet, 5 dotted crotchet, 6 crotchet triplet,
               7 quaver triplet, 8 quaver, 9 dotted quaver, 0 semiquaver, ) semiquaver triplet,
               = demisemiquaver
       "R-8" a rest; "a-8+G-8" a chord (the first note is the tune); "_" joins two notes (a tie if the same pitch);
       "S-6" the first bar line; "STnn" a new time signature; "W-n" endings; "P", "X", "x" marks taking no time.

    python scripts/build_child_tunes.py           download (cached in scripts/.cache/), build, render
    python scripts/build_child_tunes.py --check   parse every tune in the database and report what doesn't add up
"""
import collections
import io
import json
import re
import shutil
import subprocess
import sys
import time
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
CACHE = ROOT / "scripts" / ".cache" / "digitrad"
DT_URL = "https://mudcat.org/download/DTSpring2002MSDOS.zip"
OUT = ROOT / "data" / "ballads"
UA = {"User-Agent": "ScriptureBot corpus builder (personal Discord bot)"}
BITRATE = "24k"
PPQ = 480

PITCHES = "<=>?@ABCDEFGabcdefghijklmnop"           # diatonic steps from C3
STEP = [0, 2, 4, 5, 7, 9, 11]
LENGTH = {"1": 4, "2": 2, "3": 3, "4": 1, "5": 1.5, "6": 2 / 3, "7": 1 / 3, "8": 0.5, "9": 0.75, "0": 0.25,
          "=": 0.125, ")": 1 / 6}
SHARPS = "FCGDAEB"
MAJOR_SHARPS = {"C": 0, "G": 1, "D": 2, "A": 3, "E": 4, "B": 5, "F#": 6, "C#": 7,
                "F": -1, "Bb": -2, "Eb": -3, "Ab": -4, "Db": -5, "Gb": -6, "Cb": -7}
MINOR_SHARPS = {"A": 0, "E": 1, "B": 2, "F#": 3, "C#": 4, "G#": 5, "D#": 6,
                "D": -1, "G": -2, "C": -3, "F": -4, "Bb": -5, "Eb": -6}


def download() -> zipfile.ZipFile:
    path = CACHE / "DTSpring2002MSDOS.zip"
    if not path.exists():
        CACHE.mkdir(parents=True, exist_ok=True)
        path.write_bytes(urllib.request.urlopen(urllib.request.Request(DT_URL, headers=UA), timeout=300).read())
    return zipfile.ZipFile(path)


def key_signature(key: str) -> "dict | None":
    """{"F": 1, "B": -1, ...}: what "-" means for each letter in a key ("Ab", "Em", "D"); None if unknown."""
    k = key.strip().replace("maj", "")
    minor = k.endswith("m") and not k.endswith("dim")
    k = k[:-1] if minor else k
    n = (MINOR_SHARPS if minor else MAJOR_SHARPS).get(k)
    if n is None:
        return None
    sig = {}
    for letter in (SHARPS[:n] if n > 0 else SHARPS[::-1][:-n]):
        sig[letter] = 1 if n > 0 else -1
    return sig


def tonic(key: str) -> "int | None":
    """The key's home note as a pitch class."""
    m = re.match(r"([A-G])([#b]?)", key.strip())
    if not m:
        return None
    return (STEP["CDEFGAB".index(m.group(1))] + {"#": 1, "b": -1, "": 0}[m.group(2)]) % 12


def parse(text: str) -> dict:
    """A tune file -> {"title", "key", "meter", "speed", "source", "notes": [(midi pitch or None, beats)],
    "pickup": beats before the first bar line, "unknown": [tokens not understood]}."""
    head, lines = {}, []
    for line in text.replace("\r", "").split("\n"):
        if len(line) > 1 and line[1] == "-":
            if line[0] == "M":
                lines.append(line[3:])          # (the character after "M-" is layout)
            elif line[0] not in head:
                head[line[0]] = line[2:].strip()
    sig = key_signature(head.get("K", "C")) or {}
    notes, unknown, pickup, bar = [], [], None, False
    held = {}                                   # accidentals so far in this bar: {(letter, octave): shift}
    beats_in_bar = _bar_beats(head.get("B", "4/4"))
    pos = 0.0
    tie = False
    for raw in " ".join(lines).replace(".S-", " S-").split():
        raw = re.sub(r"^ST\d\d", "", raw)        # (a new time signature)
        for j, part in enumerate(raw.split("_")):
            part = re.sub(r"^ST\d\d", "", part)
            k = re.match(r"SK([A-G][b#]?m?)(?=[<=>?@A-Ga-p][-&#%]|$)(.*)", part)
            if k:                                # (a new key: "SKD", "SKBbF-4")
                sig, held, part = key_signature(k.group(1)) or sig, {}, k.group(2)
            if not part:
                continue
            m = re.fullmatch(r"([<=>?@A-Ga-p])([-&#%])([0-9=)])\.?((?:\+[<=>?@A-Ga-p][-&#%][0-9=)])*)\.?", part)
            if m:
                letter_i = PITCHES.index(m.group(1))
                octave, degree = divmod(letter_i, 7)
                letter = "CDEFGAB"[degree]
                acc = {"#": 1, "&": -1, "%": 0}.get(m.group(2))
                if acc is None:
                    acc = held.get((letter, octave), sig.get(letter, 0))
                else:
                    held[(letter, octave)] = acc
                pitch = 48 + 12 * octave + STEP[degree] + acc
                beats = LENGTH[m.group(3)]
                if j > 0 and notes and notes[-1][0] == pitch:
                    notes[-1] = (pitch, notes[-1][1] + beats)     # (a tie)
                else:
                    notes.append((pitch, beats))
                pos += beats
            elif re.fullmatch(r"R-([0-9=)])\.?", part):
                notes.append((None, LENGTH[part[2]]))
                pos += LENGTH[part[2]]
            elif part.startswith("S-"):
                if pickup is None:
                    pickup = pos
                    held = {}
            elif re.fullmatch(r"[WPXx][-+]\w\.?|\.|", part):
                pass
            else:
                unknown.append(part)
                continue
            # bar lines by the metre, after the first: accidentals last to the end of their bar
            start = pickup or 0.0
            if pos > start and beats_in_bar and abs(((pos - start) % beats_in_bar)) < 1e-6:
                held = {}
    return {"title": head.get("N", ""), "key": head.get("K", ""), "meter": head.get("B", ""),
            "speed": _speed(head.get("S", "")), "source": head.get("F", ""), "notes": notes,
            "pickup": pickup or 0.0, "unknown": unknown}


def _bar_beats(meter: str) -> "float | None":
    m = re.match(r"\s*(\d+)\s*/\s*(\d+)", meter)
    return int(m.group(1)) * 4 / int(m.group(2)) if m and int(m.group(1)) and int(m.group(2)) else None


def _speed(s: str) -> int:
    m = re.match(r"\s*(\d+)", s)
    return min(max(int(m.group(1)), 40), 200) if m else 100


def child_tunes(z: zipfile.ZipFile) -> dict:
    """{Child number: [(song file, tune file)]}: the songs whose notes name a Child ballad ("Child #12", "Child
    No. 12") and have a tune; then the tune-only files B10_.., B11_.., B12_.. (versions of Child 10-12), last."""
    text = z.read("Z02.ASK").decode("cp1252", "replace")
    names = {n.upper(): n for n in zipfile.ZipFile(io.BytesIO(z.read("TUNE.ZIP"))).namelist()}
    parts = re.split(r"filename\[\s*([A-Z0-9_.']+)", text)   # (a song's text, then its file name)
    found = collections.defaultdict(list)
    for i in range(1, len(parts) - 1, 2):
        body, song, after = parts[i - 1], parts[i], parts[i + 1][:40]
        m = re.search(r"play\.exe.([A-Z0-9_.']+)", after)
        tune = names.get(m.group(1).upper()) if m else None
        if not tune:
            continue
        # (the notes are at the end of a song's text; a number must be the Child number, not a page)
        nums = {int(n) for n in re.findall(r"\bChild(?:'s)?\s*(?:#|No\.?|number|ballad)\s*(\d{1,3})\b",
                                           body[-3000:], re.I) if 1 <= int(n) <= 305}
        for n in nums:
            found[n].append((song, tune))
    for name in sorted(names.values()):
        m = re.fullmatch(r"B(1[012])_\d+", name)
        if m:
            found[int(m.group(1))].append((None, name))
    return found


def check(z: zipfile.ZipFile) -> None:
    """Every tune: whole bars after the pickup, and the last note on the key's home note (most folk tunes end
    there), as a test of the reading. Lists what doesn't fit."""
    tunes = zipfile.ZipFile(io.BytesIO(z.read("TUNE.ZIP")))
    stats = collections.Counter()
    odd = collections.defaultdict(list)
    for name in tunes.namelist():
        t = parse(tunes.read(name).decode("cp1252", "replace"))
        played = [n for n in t["notes"] if n[0] is not None]
        if not played:
            stats["no notes"] += 1
            continue
        stats["tunes"] += 1
        bar = _bar_beats(t["meter"])
        total = sum(b for _, b in t["notes"]) - t["pickup"]
        if bar:
            rest = total % bar
            whole = rest < 0.01 or bar - rest < 0.01 or abs(rest - (bar - t["pickup"])) < 0.01
            stats["whole bars" if whole else "bars don't add up"] += 1
            if not whole:
                odd["bars"].append(name)
        home = tonic(t["key"])
        if home is not None:
            last = played[-1][0] % 12
            # (a minor tune written in its relative major ends on the sixth)
            if last == home:
                stats["ends on the tonic"] += 1
            elif last == (home + 9) % 12:
                stats["ends on the relative minor"] += 1
            else:
                stats["ends elsewhere"] += 1
                odd["ending"].append(name)
        if t["unknown"]:
            stats["with tokens not understood"] += 1
            odd["unknown"].append(f"{name}: {t['unknown'][:4]}")
    for k, v in stats.most_common():
        print(f"{v:6}  {k}")
    for k, v in odd.items():
        print(k, len(v), v[:12])


# The database's own slips: a song filed under the wrong Child number, or a tune it gives a ballad that isn't one
# of its tunes ("Bold Dickie", Child 187/188's kin, is noted as Child 117 and 118, the Robin Hood gests).
MOVED = {("WETHSKIN", 227): 277}
DROPPED = {("BOLDARC3", 117), ("BOLDARC3", 118)}


def tune_lists(z: zipfile.ZipFile) -> dict:
    """{Child number: [{"file", "song", "title", "source", "notes", "speed"}]}: each tune once, a song's own tunes
    before those it borrows ("Captain Wedderburn" is sung to "Paddy West")."""
    tunes = zipfile.ZipFile(io.BytesIO(z.read("TUNE.ZIP")))
    found = collections.defaultdict(list)
    for n, items in child_tunes(z).items():
        for song, tune in items:
            if (song, n) in DROPPED:
                continue
            found[MOVED.get((song, n), n)].append((song, tune))
    out = {}
    for n, items in sorted(found.items()):
        own = [x for x in items if x[0] is None or x[1].split(".")[0][:5] == x[0][:5]]
        seen, kept = set(), []
        for song, tune in own + [x for x in items if x not in own]:
            if tune in seen:
                continue
            seen.add(tune)
            t = parse(tunes.read(tune).decode("cp1252", "replace"))
            if not any(p is not None for p, _ in t["notes"]):
                continue
            kept.append({"file": tune, "song": song, "title": t["title"], "source": t["source"],
                         "notes": t["notes"], "speed": t["speed"], "key": t["key"], "meter": t["meter"]})
        if kept:
            out[n] = kept
    return out


def write_midi(tune: dict, path: Path) -> float:
    """The melody alone, on one channel, at the tune's speed; returns its length in seconds."""
    import mido
    mid = mido.MidiFile(ticks_per_beat=PPQ)
    track = mido.MidiTrack()
    track.append(mido.MetaMessage("set_tempo", tempo=mido.bpm2tempo(tune["speed"]), time=0))
    track.append(mido.Message("program_change", program=73, time=0))        # (a flute, for a sung line)
    wait = 0
    notes = list(tune["notes"])
    while notes and notes[0][0] is None:            # (no silence before the first note)
        notes.pop(0)
    for pitch, beats in notes:
        ticks = round(beats * PPQ)
        if pitch is None:
            wait += ticks
            continue
        track.append(mido.Message("note_on", note=pitch, velocity=80, time=wait))
        track.append(mido.Message("note_off", note=pitch, velocity=0, time=ticks))
        wait = 0
    mid.tracks.append(track)
    path.parent.mkdir(parents=True, exist_ok=True)
    mid.save(path)
    return round(mid.length, 1)


def render_ogg(midi: Path, ogg: Path, title: str) -> None:
    import hymn_audio
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        sys.exit("ffmpeg isn't on the PATH")
    ogg.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run([ffmpeg, "-loglevel", "error", "-y", "-f", "wav", "-i", "-", "-ac", "1",
                    "-c:a", "libopus", "-b:a", BITRATE, "-metadata", f"title={title}", str(ogg)],
                   input=hymn_audio.render(midi), check=True)


def stem(tune_file: str) -> str:
    """A tune's file name on disk ("BARBALEN.2" -> "BARBALEN_2")."""
    return re.sub(r"[^A-Za-z0-9_]", "_", tune_file)


# ── each ballad's recording on YouTube ────────────────────────────────────────────────────────────────
PLAYLIST = "https://www.youtube.com/playlist?list=PLeNQU_GgARdQ"        # "Child's Ballads (in Order)"


def playlist() -> list:
    """The playlist's videos [{"id", "title", "channel"}], listed once with yt-dlp (pip install yt-dlp)."""
    path = ROOT / "scripts" / ".cache" / "child_yt" / "playlist.json"
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        out = subprocess.run([sys.executable, "-m", "yt_dlp", "--flat-playlist", "-J", PLAYLIST],
                             capture_output=True, check=True).stdout
        path.write_bytes(out)
    return json.loads(path.read_text(encoding="utf-8"))["entries"]


def _norm_title(s: str) -> str:
    s = re.sub(r"\(.*?\)|\[.*?\]|child(?:'s)?(?: ballad)?\s*(?:no\.?|#)?\s*\d+|^\d+\.\s*|traditional \w+", " ", s.lower())
    s = s.split(" - ", 1)[1] if " - " in s else s
    return re.sub(r"[^a-z]", "", s.replace("the ", ""))


def _child_no(title: str) -> "int | None":
    m = re.search(r"child(?:'s)?(?: ballad)?\s*(?:no\.?|#|number)?\s*(\d{1,3})\b", title, re.I)
    return int(m.group(1)) if m else None


def match_videos(videos: list, titles: dict) -> dict:
    """{Child number: video}: the playlist is in Child's order, with gaps and a few doubles, so the videos are lined
    up with the ballads in order (a video naming its Child number goes there; else the nearest title), then any
    video left over that names a ballad still without one goes to it."""
    import difflib
    names = {n: {t, *alts} for n, (t, alts) in titles.items()}

    def score(v, n):
        k = _child_no(v.get("title") or "")
        if k is not None:
            return 3.0 if k == n else -3.0
        return max(difflib.SequenceMatcher(None, _norm_title(v.get("title") or ""), _norm_title(x)).ratio()
                   for x in names[n])

    N, M = len(videos), 305
    best = [[0.0] * (M + 1) for _ in range(N + 1)]
    step = [[None] * (M + 1) for _ in range(N + 1)]
    for i in range(1, N + 1):
        best[i][0], step[i][0] = best[i - 1][0] - 0.3, "skip video"
        for j in range(1, M + 1):
            best[i][j], step[i][j] = max((best[i - 1][j - 1] + score(videos[i - 1], j) - 0.5, "match"),
                                         (best[i - 1][j] - 0.3, "skip video"), (best[i][j - 1], "skip ballad"))
    i, j, out, used = N, M, {}, set()
    while i > 0 and j > 0:
        if step[i][j] == "match":
            out[j] = videos[i - 1]; used.add(i - 1); i, j = i - 1, j - 1
        elif step[i][j] == "skip video":
            i -= 1
        else:
            j -= 1
    for k, v in enumerate(videos):
        n = _child_no(v.get("title") or "")
        if k not in used and n and n not in out:
            out[n] = v
    return {n: {"id": v["id"], "title": v.get("title") or "", "channel": v.get("channel") or ""}
            for n, v in sorted(out.items())}


def main():
    z = download()
    child = json.loads((OUT / "child.json").read_text(encoding="utf-8"))
    titles = {}
    for v, stanzas in child["books"]["Child Ballads"].items():
        n = int(re.match(r"\d+", v).group())
        first = re.match(r"\*([^*]+)\*", next(iter(stanzas.values())))
        titles.setdefault(n, (child["titles"][str(n)], set()))[1].add(first.group(1) if first else "")
    found = tune_lists(z)
    out = {}
    for n, tunes in found.items():
        out[str(n)] = []
        for t in tunes:
            midi = OUT / "midi" / f"{stem(t['file'])}.mid"
            ogg = OUT / "audio" / f"{stem(t['file'])}.ogg"
            seconds = write_midi(t, midi)
            if not ogg.exists() or "--all" in sys.argv:
                render_ogg(midi, ogg, t["title"])
            out[str(n)].append({"file": stem(t["file"]), "song": t["song"], "title": t["title"],
                                "source": t["source"], "key": t["key"], "meter": t["meter"], "seconds": seconds})
    videos = match_videos(playlist(), titles)
    (OUT / "tunes.json").write_text(json.dumps({"tunes": out, "youtube": {str(n): v for n, v in videos.items()}},
                                               ensure_ascii=False, indent=1), encoding="utf-8")
    size = sum(f.stat().st_size for f in (OUT / "audio").glob("*.ogg"))
    print(f"{len(out)} ballads with {sum(map(len, out.values()))} tunes ({size / 1e6:.1f} MB of audio); "
          f"{len(videos)} with a recording")
    print("no recording:", [n for n in range(1, 306) if n not in videos])


if __name__ == "__main__":
    if "--check" in sys.argv:
        check(download())
    else:
        main()
