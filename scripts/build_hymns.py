"""
Build data/hymns/hymns.json for !hymn from the Open Hymnal Project
(openhymnal.org, mirrored at github.com/mzealey/openhymnal): ~300
public-domain hymns as ABC music files. Each carries its Bible references
(%OHSCRIP), topics, author and composer; the words are pulled out of the
lyric lines under the melody and set out in their poetic lines using the
hymn's meter.

    python scripts/build_hymns.py
"""
import html
import json
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "scripts" / ".cache" / "openhymnal"
OUT = ROOT / "data" / "hymns" / "hymns.json"
MIDI = ROOT / "data" / "hymns" / "midi"
REPO = "mzealey/openhymnal"

# Open Hymnal's book abbreviations -> the bot's book names
BOOKS = {
    "Gen": "Genesis", "Ex": "Exodus", "Lev": "Leviticus", "Lv": "Leviticus", "Num": "Numbers", "Dt": "Deuteronomy",
    "Deut": "Deuteronomy", "Josh": "Joshua", "Jos": "Joshua", "Judg": "Judges", "Jdg": "Judges", "Ruth": "Ruth",
    "1Sam": "1 Samuel", "2Sam": "2 Samuel", "1Kgs": "1 Kings", "2Kgs": "2 Kings", "1Ki": "1 Kings", "2Ki": "2 Kings",
    "1Chr": "1 Chronicles", "2Chr": "2 Chronicles", "Ezra": "Ezra", "Neh": "Nehemiah", "Est": "Esther",
    "Esth": "Esther", "Job": "Job", "Ps": "Psalms", "Psa": "Psalms", "Pr": "Proverbs", "Prov": "Proverbs",
    "Ecc": "Ecclesiastes", "Eccl": "Ecclesiastes", "Song": "Song of Solomon", "SS": "Song of Solomon", "So": "Song of Solomon",
    "Is": "Isaiah", "Isa": "Isaiah", "Jer": "Jeremiah", "Lam": "Lamentations", "Ez": "Ezekiel",
    "Ezek": "Ezekiel", "Dan": "Daniel", "Hos": "Hosea", "Joel": "Joel", "Amos": "Amos", "Ob": "Obadiah",
    "Jon": "Jonah", "Jonah": "Jonah", "Mic": "Micah", "Nah": "Nahum", "Hab": "Habakkuk", "Zeph": "Zephaniah",
    "Hag": "Haggai", "Zech": "Zechariah", "Zec": "Zechariah", "Mal": "Malachi",
    "Mt": "Matthew", "Matt": "Matthew", "Mk": "Mark", "Mar": "Mark", "Lk": "Luke", "Luk": "Luke", "Jn": "John",
    "Joh": "John", "Acts": "Acts", "Act": "Acts", "Rom": "Romans", "1Cor": "1 Corinthians",
    "2Cor": "2 Corinthians", "Gal": "Galatians", "Eph": "Ephesians", "Phil": "Philippians", "Col": "Colossians",
    "1Th": "1 Thessalonians", "2Th": "2 Thessalonians", "1Thess": "1 Thessalonians", "2Thess": "2 Thessalonians",
    "1Tim": "1 Timothy", "2Tim": "2 Timothy", "Tit": "Titus", "Titus": "Titus", "Phm": "Philemon",
    "Philem": "Philemon", "Heb": "Hebrews", "Jas": "James", "Jam": "James", "1Pet": "1 Peter",
    "2Pet": "2 Peter", "1Pe": "1 Peter", "2Pe": "2 Peter", "1Pt": "1 Peter", "2Pt": "2 Peter", "1Jn": "1 John", "2Jn": "2 John", "3Jn": "3 John",
    "Jude": "Jude", "Rev": "Revelation",
}


def download() -> list:
    CACHE.mkdir(parents=True, exist_ok=True)
    files = sorted(CACHE.glob("*.abc"))
    if files:
        return files
    req = urllib.request.Request(f"https://api.github.com/repos/{REPO}/git/trees/master?recursive=1",
                                 headers={"User-Agent": "ScriptureBot/1.0"})
    tree = json.load(urllib.request.urlopen(req, timeout=60))["tree"]
    for entry in tree:
        if entry["path"].startswith("Complete/") and entry["path"].endswith(".abc"):
            url = f"https://raw.githubusercontent.com/{REPO}/master/" + urllib.parse.quote(entry["path"])
            (CACHE / Path(entry["path"]).name).write_bytes(urllib.request.urlopen(url, timeout=60).read())
    return sorted(CACHE.glob("*.abc"))


# ── scripture references ────────────────────────────────────────────────────

def parse_scripture(field: str) -> list:
    """'Lk 24:29, Ps 63:6-8, 73:23-26, Ps 148' -> ['Luke 24:29', 'Psalms 63:6-8', 'Psalms 73:23-26', 'Psalms 148']"""
    out, book = [], None
    for part in re.split(r"[,;]", html.unescape(field)):
        part = part.strip().rstrip(".")
        if not part:
            continue
        m = re.match(r"^([1-3]?\s?[A-Za-z]+)\.?\s*(\d.*)$", part)
        if m:
            name = BOOKS.get(m.group(1).replace(" ", ""))
            if name is None:
                print(f"  unknown book in scripture field: {part!r}", file=sys.stderr)
                book = None
                continue
            book, rest = name, m.group(2)
        elif book and re.match(r"^\d", part):
            rest = part
        else:
            continue
        rest = re.sub(r"\s+", "", rest).replace("–", "-")
        if re.match(r"^\d+(:\d+(-\d+(:\d+)?)?)?$", rest):
            out.append(f"{book} {rest}")
    return list(dict.fromkeys(out))


# ── lyrics ──────────────────────────────────────────────────────────────────

def syllables(line: str) -> list:
    """An ABC lyric line -> its syllables, each (text, joins_next). '-' between
    syllables of a word, '~' joins words on one note, '*' and '_' are notes
    with no new syllable, '\\-' a printed hyphen, '|' a bar marker."""
    return [s for s in note_syllables(line) if s not in ("*", "_")]


def note_syllables(line: str) -> list:
    """As syllables(), but one entry per note: "*" where a note gets no
    syllable, "_" where the last one is held over it."""
    line = re.sub(r"^\s*\d+\.\s*~?", "", line.strip())          # the verse number
    line = line.replace("\\-", "\x00")
    out = []
    for token in line.split():
        if token in ("*", "_"):
            out.append(token)
            continue
        if token in ("|", "-"):
            continue
        pieces = token.split("-")
        for i, piece in enumerate(pieces):
            piece = piece.strip("_*|")
            if piece:
                out.append([piece.replace("~", " ").replace("\x00", "-"), i < len(pieces) - 1])
            elif out and out[-1] not in ("*", "_") and i == len(pieces) - 1 and len(pieces) > 1:
                out[-1][1] = True                            # "Fath- er": the hyphen ends the token
    return out


def verse_line(own: str, first: str) -> list:
    """Verse n's syllables in one music system. Where its line ends in notes
    with no words ("...my soul. * *") it sings what verse 1 has there -- the
    start of a refrain printed only once."""
    mine, top = note_syllables(own), note_syllables(first)
    end = len(mine)
    while end and mine[end - 1] == "*":
        end -= 1
    filled = mine[:end] + top[end:] if end < len(mine) else mine
    return [s for s in filled if s not in ("*", "_")]


def to_words(sylls: list) -> list:
    """[(text, joins_next)] -> [(word, syllable count)]"""
    words, current, count = [], "", 0
    for text, joins in sylls:
        current += text
        count += 1
        if not joins or text.endswith("-"):
            words.append((current, count))
            current, count = "", 0
    if current:
        words.append((current, count))
    # a printed hyphen after punctuation ("full,\- He") is a dash
    return [(re.sub(r"([,;:.!?])-$", r"\1—", w), n) for w, n in words]


def parse_meter(meter: str) -> "list | None":
    nums = meter.split()
    if not nums or not all(n.isdigit() for n in nums):
        return None
    return [int(n) for n in nums]


def set_lines(words: list, meter: "list | None") -> str:
    """Break a stanza into its poetic lines by the meter's syllable counts;
    if the count doesn't fit, break after each sentence-ending or clause
    punctuation followed by a capital, which is how hymn lines are printed."""
    total = sum(n for _, n in words)
    targets = None
    if meter and total % sum(meter) == 0:
        targets = meter * (total // sum(meter))
    elif meter:                          # a meter that counts the refrain too: the stanza is its first lines
        targets = next((meter[:k] for k in range(1, len(meter)) if sum(meter[:k]) == total), None)
    if targets:
        lines, current, count, t = [], [], 0, 0
        ok = True
        for word, n in words:
            current.append(word)
            count += n
            if t < len(targets) and count == targets[t]:
                lines.append(" ".join(current))
                current, count, t = [], 0, t + 1
            elif t < len(targets) and count > targets[t]:
                ok = False
                break
        if ok and not current:
            return "\n".join(lines)
    text = " ".join(w for w, _ in words)
    return re.sub(r"([,;:.!?])\s+(?=[A-Z‘“'\"])", r"\1\n", text)


def split_refrain(verses: list) -> tuple:
    """The words every verse ends with, from the start of a line, are the
    refrain: printed once rather than after each verse. -> (stanzas, refrain)"""
    if len(verses) < 2:
        return verses, []
    n = 0
    while n < min(len(v) for v in verses) and len({v[-1 - n][0].lower() for v in verses}) == 1:
        n += 1
    # start it where a line starts: after a word ending a clause, at a capital
    n = min(n, min(len(v) for v in verses) - 1)
    while n > 0 and not (re.search(r"[;:.!?,]$", verses[0][-n - 1][0]) and re.match(r"[‘“'\"]?[A-Z]", verses[0][-n][0])):
        n -= 1
    if n < 10:                        # a shared last line ("The Babe, the Son of Mary") stays in each verse
        return verses, []
    return [v[:-n] for v in verses], verses[0][-n:]


def lyric_systems(lines: list) -> list:
    """The lyric lines under the melody, grouped by music system: [[line, ...], ...]."""
    systems, current, first_voice, voice = [], None, None, None
    for raw in lines:
        m = re.match(r"^\[V:\s*([^\]]+)\]", raw)
        if m:
            voice = m.group(1).strip()
            first_voice = first_voice or voice
            if voice == first_voice:
                current = []
                systems.append(current)
            continue
        if raw.startswith("w:") and voice == first_voice and current is not None:
            current.append(raw[2:])
    return [s for s in systems if s]


def _read(path: Path) -> str:
    raw = path.read_bytes()
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw.decode("cp1252")                 # a few files are Windows-1252 ("Bless\xe8d")


def parse_hymn(path: Path) -> "dict | None":
    text = _read(path)

    lines = text.splitlines()
    head = {}
    for line in lines:
        m = re.match(r"^%OH([A-Z]+)\s*(.*)$", line)
        if m:
            head[m.group(1)] = html.unescape(m.group(2).strip())
    titles = [html.unescape(l[2:].strip()) for l in lines if l.startswith("T:")]
    if not titles:
        return None
    credits = " ".join(html.unescape(l[2:].strip()) for l in lines if l.startswith("C:") and "copyright" not in l.lower())

    # Each verse as sung: a system with fewer lyric lines than verses is sung
    # by them all (a refrain, or a line every verse repeats).
    # Lines past the verses ("Far, Far Away": six lines for four verses) are
    # the lower voices' echoes, as is the second line of a shorter system.
    systems = lyric_systems(lines)
    numbers = [int(m.group(1)) for s in systems for l in s if (m := re.match(r"^\s*(\d+)\.", l))]
    verses_n = max(numbers, default=len(systems[0]) if systems else 0)
    sung = [[] for _ in range(verses_n)]
    for s in systems:
        for i in range(verses_n):
            sung[i] += verse_line(s[i], s[0]) if len(s) >= verses_n else syllables(s[0])
    sung = [to_words(v) for v in sung if v]
    stanzas, refrain = split_refrain(sung)
    meter = parse_meter(head.get("METRICAL", ""))
    out = [set_lines(st, meter) for st in stanzas if st]

    # verses printed as text after the music ("W: 6.I need Thy presence ...")
    extra, current = [], []
    for line in lines:
        if line.startswith("W:"):
            body = line[2:].strip()
            if not body:
                if current:
                    extra.append(current)
                current = []
            else:
                body = re.sub(r"^\d+(?:\(alt\))?[.,]\s*", "", body).replace("_", "")
                body = body.replace("heavy\\- hearted", "heavy-hearted").replace("\\- ", "— ").replace("\\-", "—")
                current.append(body)
    if current:
        extra.append(current)
    out += ["\n".join(st) for st in extra]
    if not out:
        return None

    title = re.sub(r"\s+", " ", titles[0])
    also = [re.sub(r"^\((?:also known as\s*)?|\)$", "", t, flags=re.I).strip() for t in titles[1:]]
    tune = re.search(r"Music(?: and Setting)?:\s*['‘\"]([^'’\"]+)['’\"]", credits)
    return {
        "title": title,
        "also": [a for a in also if a and a.lower() != title.lower()],
        "author": _person(head.get("AUTHOR", "")),
        "translator": _person(head.get("TRANSLATOR", "")),
        "composer": _person(head.get("COMPOSER", "")),
        "tune": tune.group(1).strip() if tune else "",
        "meter": head.get("METRICAL", ""),
        "scripture": parse_scripture(head.get("SCRIP", "")),
        "topics": [re.sub(r"\s*\(.*\)$", "", t.strip()) for t in re.findall(r"\{([^}]*)\}", head.get("TOPICS", ""))
                   if t.strip()],
        "stanzas": out,
        "refrain": set_lines(refrain, None) if refrain else "",
        "first_line": out[0].split("\n")[0],
        "file": path.name,
        "source": "The Open Hymnal Project",
    }


# ── music: ABC -> MIDI ──────────────────────────────────────────────────────
# Just the part of ABC these files use (checked over all of them): major
# keys, unit lengths, ties, triplets, broken rhythm, fermatas, chords,
# |: :| repeats, inline [Q:]/[K:]/[L:] fields; slurs, decorations, chord
# symbols and grace notes don't change what's played.

KEY_SHARPS = {"C": 0, "G": 1, "D": 2, "A": 3, "E": 4, "B": 5, "F#": 6,
              "F": -1, "Bb": -2, "Eb": -3, "Ab": -4, "Db": -5, "Gb": -6}
SHARP_ORDER, FLAT_ORDER = "FCGDAEB", "BEADGCF"
STEP = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}
FERMATA = ("!fermata!", "!ferm!", "!invertedfermata!", "H")
TOKEN = re.compile(r"""
    (?P<chordsym>"[^"]*")
  | (?P<deco>![^!]*!)
  | (?P<field>\[[KLMQ]:[^\]]*\])
  | (?P<grace>\{[^}]*\})
  | (?P<tuplet>\((?P<p>\d)(?::(?P<q>\d*))?(?::(?P<r>\d*))?)
  | (?P<bar>::|:\||\|:|\|\]|\|\||\[\d|\|)
  | (?P<chord>\[(?P<cnotes>[^\]:]+)\](?P<clen>\d*/*\d*))
  | (?P<note>(?P<acc>[_^=]*)(?P<letter>[A-Ga-gzx])(?P<oct>[,']*)(?P<len>\d*/*\d*))
  | (?P<broken>[<>]+)
  | (?P<tie>-)
  | (?P<overlay>&)
""", re.X)
NOTE = re.compile(r"([_^=]*)([A-Ga-g])([,']*)(\d*/*\d*)")


def _length(spec: str) -> float:
    if not spec:
        return 1.0
    m = re.match(r"^(\d*)(/*)(\d*)$", spec)
    num = int(m.group(1)) if m.group(1) else 1
    if not m.group(2):
        return float(num)
    den = int(m.group(3)) if m.group(3) else 2 ** len(m.group(2))
    return num / den


def _key_signature(key: str) -> dict:
    n = KEY_SHARPS.get(key.strip().split()[0] if key.strip() else "C", 0)
    return {l: 1 for l in SHARP_ORDER[:n]} if n >= 0 else {l: -1 for l in FLAT_ORDER[:-n]}


def _tempo(field: str) -> "float | None":
    """'1/4=120' -> whole notes per minute"""
    m = re.match(r"^\s*(\d+)/(\d+)\s*=\s*(\d+)", field)
    return int(m.group(3)) * int(m.group(1)) / int(m.group(2)) if m else None


def abc_music(text: str) -> tuple:
    """-> (whole notes per minute, {voice: [(start, duration, midi pitch)]}),
    times in whole notes."""
    unit, key, tempo = 1 / 8, {}, None
    voices: dict = {}
    for line in text.splitlines():
        m = re.match(r"^([LKQ]):\s*(.*)$", line)
        if m and not voices:
            field = re.sub(r"%.*", "", m.group(2)).strip()
            if m.group(1) == "L":
                unit = 1 / int(field.split("/")[1])
            elif m.group(1) == "K":
                key = _key_signature(field)
            elif m.group(1) == "Q":
                tempo = tempo or _tempo(field)
        m = re.match(r"^\[V:\s*([^\]]+)\](.*)$", line)
        if m:
            voices.setdefault(m.group(1).strip(), []).append(re.sub(r"%.*", "", m.group(2)))
    out = {}
    for name, lines in voices.items():
        notes, q = _play_voice(" ".join(lines), unit, dict(key))
        tempo = tempo or q
        out[name] = notes
    return tempo or 30.0, out


def _play_voice(music: str, unit: float, key: dict) -> tuple:
    tokens = list(TOKEN.finditer(music))
    notes, t, i = [], 0.0, 0
    bar_acc: dict = {}
    tuplet_left, tuplet_mult = 0, 1.0
    fermata, tie_open, broken_next = False, False, 1.0
    repeat_start, repeated = 0, set()
    bar_start, overlay_end = 0.0, None
    tempo = None
    while i < len(tokens):
        tok = tokens[i]
        kind = next(k for k in ("chordsym", "deco", "field", "grace", "tuplet", "bar", "chord", "note", "broken", "tie", "overlay")
                    if tok.group(k) is not None)
        s = tok.group(kind)
        if kind == "deco":
            fermata = fermata or s in FERMATA
        elif kind == "field":
            f, val = s[1], s[3:-1]
            if f == "Q":
                tempo = tempo or _tempo(val)
            elif f == "K":
                key = _key_signature(val)
            elif f == "L":
                unit = 1 / int(val.split("/")[1])
        elif kind == "tuplet":                       # (p:q:r -- p notes in the time of q, over the next r
            p = int(tok.group("p"))
            q = int(tok.group("q")) if tok.group("q") else {2: 3, 3: 2, 4: 3, 6: 2}.get(p, 2)
            tuplet_left, tuplet_mult = int(tok.group("r")) if tok.group("r") else p, q / p
        elif kind == "overlay":                      # "&": a second line of notes in the same bar
            overlay_end = max(overlay_end or 0, t)
            t = bar_start
        elif kind == "bar":
            if overlay_end is not None:
                t, overlay_end = max(t, overlay_end), None
            bar_start = t
            bar_acc = {}
            if s in (":|", "::") and i not in repeated:
                repeated.add(i)
                i = repeat_start
                continue
            if s in ("|:", "::"):
                repeat_start = i + 1
        elif kind == "broken":
            if notes and s[0] == ">":
                factor = 1 - 0.5 ** len(s)
                last = notes[-1]
                notes[-1] = (last[0], last[1] * (1 + factor), last[2])
                t += last[1] * factor
                broken_next = 1 - factor
            elif notes:
                factor = 1 - 0.5 ** len(s)
                last = notes[-1]
                notes[-1] = (last[0], last[1] * (1 - factor), last[2])
                t -= last[1] * factor
                broken_next = 1 + factor
        elif kind == "tie":
            tie_open = True
        elif kind in ("note", "chord"):
            if kind == "note":
                parts = [(tok.group("acc"), tok.group("letter"), tok.group("oct"), tok.group("len"))]
                length = _length(tok.group("len"))
            else:
                parts = NOTE.findall(tok.group("cnotes"))
                length = _length(parts[0][3]) * _length(tok.group("clen")) if parts else 0
            dur = length * unit * broken_next * (tuplet_mult if tuplet_left else 1) * (1.5 if fermata else 1)
            if tuplet_left:
                tuplet_left -= 1
            broken_next, fermata = 1.0, False
            for acc, letter, octave, _ in parts:
                if letter in "zx":
                    continue
                pitch = _pitch(acc, letter, octave, key, bar_acc)
                if tie_open and notes and notes[-1][2] == pitch and abs(notes[-1][0] + notes[-1][1] - t) < 1e-6:
                    notes[-1] = (notes[-1][0], notes[-1][1] + dur, pitch)
                else:
                    notes.append((t, dur, pitch))
            tie_open = False
            t += dur
        i += 1
    return notes, tempo


def _pitch(acc: str, letter: str, octave: str, key: dict, bar_acc: dict) -> int:
    base = letter.upper()
    octv = 5 if letter.islower() else 4
    octv += octave.count("'") - octave.count(",")
    if acc:
        alter = {"^": 1, "^^": 2, "_": -1, "__": -2, "=": 0}.get(acc, 0)
        bar_acc[(base, octv)] = alter
    else:
        alter = bar_acc.get((base, octv), key.get(base, 0))
    return 12 * (octv + 1) + STEP[base] + alter


def write_midi(tempo: float, voices: dict, path: Path) -> float:
    """A type-1 MIDI file, one track per voice on a church organ; -> length in seconds."""
    import mido
    tpb = 480
    mid = mido.MidiFile(type=1, ticks_per_beat=tpb)
    quarter_us = int(60_000_000 / (tempo * 4))
    meta = mido.MidiTrack()
    meta.append(mido.MetaMessage("set_tempo", tempo=quarter_us, time=0))
    mid.tracks.append(meta)
    for ch, (name, notes) in enumerate(voices.items()):
        track = mido.MidiTrack()
        track.append(mido.MetaMessage("track_name", name=name, time=0))
        track.append(mido.Message("program_change", program=19, channel=ch, time=0))
        events = []
        for start, dur, pitch in notes:
            on, off = round(start * 4 * tpb), round((start + dur) * 4 * tpb)
            events += [(on, 1, pitch), (off, 0, pitch)]
        now = 0
        for tick, is_on, pitch in sorted(events):
            track.append(mido.Message("note_on" if is_on else "note_off", note=pitch,
                                      velocity=80 if is_on else 0, channel=ch, time=tick - now))
            now = tick
        mid.tracks.append(track)
    mid.save(path)
    end = max((s + d for notes in voices.values() for s, d, _ in notes), default=0)
    return end * 60 / tempo


# ── hymns from Hymnary.org ──────────────────────────────────────────────────
# Well-loved hymns the Open Hymnal doesn't have: the words ("Representative
# Text"), author and meter from the hymn's Hymnary.org page, with the Bible
# passages at least two of the hymnals listed there give for it. Hymnary's
# MIDI downloads sit behind a browser check, so a tune comes from Wikimedia
# Commons where it has a complete one; otherwise the hymn is words only.

HYMNARY = "https://hymnary.org"
HYMNARY_CACHE = ROOT / "scripts" / ".cache" / "hymnary"
COMMONS_CACHE = ROOT / "scripts" / ".cache" / "commons"
USER_AGENT = "ScriptureBot/1.0 (https://github.com/Ante-Luvian/scripture-bot)"
EXTRA_HYMNS = [
    {"text": "once_in_royal_davids_city_stood_a_lowly", "tune": "Irby",
     "composer": "Henry J. Gauntlett (1805–1876)", "commons": "Once in Royal David's City.mid"},
    {"text": "and_did_those_feet_in_ancient_time", "title": "Jerusalem (And Did Those Feet in Ancient Time)",
     "tune": "Jerusalem", "composer": "C. Hubert H. Parry (1848–1918)",
     "commons": "And Did Those Feet In Ancient Time (Jerusalem).mid"},
    {"text": "i_heard_the_voice_of_jesus_say_come_unto", "tune": "Kingsfold",
     "composer": "English traditional melody", "local": "Kingsfold.mid"},
    {"text": "each_day_ill_do_a_golden_deed", "title": "A Beautiful Life", "tune": "A Beautiful Life",
     "composer": "William M. Golden (1878–1934)", "local": "A_Beautiful_Life.mid"},
    # Hymnary refuses this page outright, so the words come from Wikipedia's article
    {"wikipedia": "I Vow to Thee, My Country", "title": "I Vow to Thee, My Country", "tune": "Thaxted",
     "author": "Cecil Spring Rice (1918)", "meter": "13 13 13 13 13 13",
     "scripture": ["Proverbs 3:17", "Genesis 22:2"],          # the article's notes on its last line and its altar
     "composer": "Gustav Holst (1874–1934)", "local": "Thaxted.mid"},
    # the Phos Hilaron, the Greek evening hymn, in Robert Bridges's translation; Hymnary refuses
    # scripts, so the words are Wikipedia's (which cites Hymnary) and the owner fetched the tune
    {"wikipedia": "Phos Hilaron", "section": "by Robert Bridges", "title": "O Gladsome Light (Phos Hilaron)",
     "tune": "Nunc Dimittis", "author": "Ancient Greek, 3rd century or earlier; translated by Robert Bridges (1899)",
     "meter": "6 6 7 6 6 7", "scripture": [],
     "composer": "Louis Bourgeois (1551); harmony by Claude Goudimel", "local": "Nunc_Dimittis_Bourgeois.mid"},
]
WIKIPEDIA_CACHE = ROOT / "scripts" / ".cache" / "wikipedia"


def wikipedia_hymn(spec: dict) -> dict:
    """Words from the {{poemquote}} block of a hymn's Wikipedia article."""
    name = re.sub(r"[^A-Za-z0-9]+", "_", spec["wikipedia"]).strip("_")
    url = ("https://en.wikipedia.org/w/api.php?action=query&prop=revisions&rvprop=content&rvslots=main"
           "&format=json&formatversion=2&redirects=1&titles=" + urllib.parse.quote(spec["wikipedia"]))
    cached = WIKIPEDIA_CACHE / f"{name}.wiki"
    if cached.exists():
        wikitext = cached.read_text(encoding="utf-8")
    else:
        page = json.loads(_fetch(url, WIKIPEDIA_CACHE / f"{name}.json"))["query"]["pages"][0]
        wikitext = page["revisions"][0]["slots"]["main"]["content"]
        cached.write_text(wikitext, encoding="utf-8")
    wikitext = re.sub(r"<ref[^>]*>.*?</ref>|<ref[^>]*/>", "", wikitext, flags=re.S)
    if spec.get("section"):             # one translation of several: the <poem> under its heading
        m = re.search(rf"=+\s*{re.escape(spec['section'])}\s*=+\s*<poem[^>]*>(.*?)</poem>", wikitext, re.S)
    else:
        m = re.search(r"\{\{poemquote\|(.*?)\}\}", wikitext, re.S)
    if not m:
        raise RuntimeError(f"no {{{{poemquote}}}} in Wikipedia's {spec['wikipedia']}")
    text = re.sub(r"\[\[(?:[^|\]]*\|)?([^\]]*)\]\]", r"\1", m.group(1)).replace("''", "")
    stanzas = ["\n".join(l.strip() for l in s.strip().splitlines()) for s in re.split(r"\n\s*\n", text) if s.strip()]
    hymn = {
        "title": spec["title"], "also": [], "author": spec["author"], "translator": "",
        "composer": spec["composer"], "tune": spec["tune"], "meter": spec["meter"],
        "scripture": spec["scripture"], "topics": [], "stanzas": stanzas, "refrain": "",
        "first_line": stanzas[0].split("\n")[0].rstrip(",;"),
        "file": f"en.wikipedia.org/wiki/{spec['wikipedia'].replace(' ', '_')}", "source": "Wikipedia",
    }
    return _local_tune(hymn, spec)


def _local_tune(hymn: dict, spec: dict) -> dict:
    midi = (LOCAL_MIDI / spec["local"]).read_bytes()
    if not midi.startswith(b"MThd"):
        raise RuntimeError(f"{spec['local']} isn't a MIDI file")
    MIDI.mkdir(parents=True, exist_ok=True)
    (MIDI / spec["local"]).write_bytes(midi)
    import mido
    hymn.update(midi=spec["local"], seconds=round(mido.MidiFile(MIDI / spec["local"]).length))
    return hymn
LOCAL_MIDI = ROOT / "scripts" / "hymn_midi"      # tunes the owner supplied, where no source could be fetched


def _fetch(url: str, cached: Path, refusals=(403,)) -> bytes:
    """A page or file, cached. Hymnary refuses requests that come too fast
    (with a 403, as for a page that doesn't exist): wait and retry."""
    import time
    if cached.exists():
        return cached.read_bytes()
    cached.parent.mkdir(parents=True, exist_ok=True)
    for wait in (5, 30, 90):
        time.sleep(wait)
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        try:
            body = urllib.request.urlopen(req, timeout=60).read()
        except urllib.error.HTTPError as e:
            if e.code in refusals or e.code == 429:
                continue
            raise
        cached.write_bytes(body)
        return body
    raise RuntimeError(f"kept being refused: {url}")


def hymnary_words(block: str) -> tuple:
    """Hymnary's "Representative Text" HTML -> (stanzas, refrain). Verses are
    numbered ("1 Each day...", "2. To be..."), sometimes several to a
    paragraph; "Refrain:" starts the refrain; "[Refrain]" marks a repeat."""
    text = html.unescape(re.sub(r"<br\s*/?>|</p>", "\n", block))
    text = re.sub(r"<[^>]+>", "", text).replace("[Refrain]", "")
    stanzas, refrain, current, in_refrain = [], [], None, False
    for line in (l.strip() for l in text.splitlines()):
        if not line:
            continue
        m = re.match(r"^(\d+)\.?\s+(.*)$", line)
        if m:
            current, in_refrain = [m.group(2)], False
            stanzas.append(current)
        elif re.match(r"^(Refrain|Chorus):?$", line, re.I):
            in_refrain = True
        elif in_refrain:
            refrain.append(line)
        elif current is not None:
            current.append(line)
    return ["\n".join(s) for s in stanzas], "\n".join(refrain)


def hymnary_scripture(page: str) -> list:
    """The passages at least two of the hymnals on the page give, most-cited first
    (or, if they never agree, the first few any of them gives)."""
    from collections import Counter
    counts = Counter()
    for field in re.findall(r"Scripture</b>:\s*([^<]+)</span>", page):
        for ref in html.unescape(field).split(";"):
            ref = ref.strip().replace("–", "-")
            m = re.match(r"^([1-3]?\s?[A-Z][a-z]+(?: of [A-Z][a-z]+)?)\s+(\d+(?::\d+(?:-\d+)?)?)$", ref)
            if m and m.group(1) in BOOKS.values():
                counts[f"{m.group(1)} {m.group(2)}"] += 1
    agreed = [ref for ref, n in counts.most_common() if n >= 2]
    return (agreed or [ref for ref, _ in counts.most_common()])[:8]


def hymnary_hymn(spec: dict) -> dict:
    page = _fetch(f"{HYMNARY}/text/{spec['text']}", HYMNARY_CACHE / f"text__{spec['text']}.html")
    page = page.decode("utf-8", "replace")
    info = {label.strip().rstrip(":"): html.unescape(re.sub(r"<[^>]+>", "", value)).strip()
            for label, value in re.findall(
                r'hy_infoLabel">([^<]+)</span></td>\s*<td><span class="hy_infoItem">(.*?)</span></td>', page, re.S)}
    block = re.search(r"id='at_fulltext'>.*?<div property='text'>(.*?)(?:<br/><br/>Source:|</div></div>)", page, re.S)
    if not block:
        raise RuntimeError(f"no words on Hymnary's page for {spec['text']}")
    stanzas, refrain = hymnary_words(block.group(1))
    if not stanzas:
        raise RuntimeError(f"no verses found in Hymnary's text of {spec['text']}")
    hymn = {
        "title": spec.get("title") or info.get("Title") or spec["text"],
        "also": [],
        "author": re.sub(r"\s*\((\d{4})\)$", r" (\1)", info.get("Author", "")),
        "translator": info.get("Translator", ""),
        "composer": spec["composer"],
        "tune": spec["tune"],
        "meter": info.get("Meter", "").replace(".", " "),
        "scripture": hymnary_scripture(page),
        "topics": [],
        "stanzas": stanzas,
        "refrain": refrain,
        "first_line": stanzas[0].split("\n")[0],
        "file": f"hymnary.org/text/{spec['text']}",
        "source": "Hymnary.org",
    }
    if spec.get("commons"):
        name = re.sub(r"[^A-Za-z0-9.]+", "_", spec["commons"])
        midi = _fetch("https://commons.wikimedia.org/wiki/Special:FilePath/" + urllib.parse.quote(spec["commons"]),
                      COMMONS_CACHE / name)
        if not midi.startswith(b"MThd"):
            raise RuntimeError(f"{spec['commons']} isn't a MIDI file")
        MIDI.mkdir(parents=True, exist_ok=True)
        (MIDI / name).write_bytes(midi)
        import mido
        hymn.update(midi=name, seconds=round(mido.MidiFile(MIDI / name).length))
        hymn["source"] = "Hymnary.org; tune from Wikimedia Commons"
    elif spec.get("local"):
        hymn = _local_tune(hymn, spec)
    return hymn


def _person(field: str) -> str:
    """'Buell, Harriet Eugenia Peck (1834-1910)' -> 'Harriet Eugenia Peck Buell (1834–1910)'"""
    field = field.strip()
    if not field or field.lower() in ("none", "unknown", "traditional"):
        return {"traditional": "Traditional", "unknown": "Unknown"}.get(field.lower(), "")
    m = re.match(r"^([^,(]+),\s*([^(]+?)\s*(\(.*\))?$", field)
    if m:
        dates = (" " + m.group(3).replace("-", "–")) if m.group(3) else ""
        return f"{m.group(2).strip()} {m.group(1).strip()}{dates}"
    return field


def main():
    hymns = {}
    misaligned = []
    unmetered = 0
    for path in download():
        h = parse_hymn(path)
        if h is None:
            print(f"  no words: {path.name}", file=sys.stderr)
            continue
        if not parse_meter(h["meter"]) or any("\n" not in s for s in h["stanzas"]):
            unmetered += 1
        # the same words set to two tunes (A Mighty Fortress, rhythmic and isorhythmic): keep the first
        if h["title"].lower() in hymns:
            continue
        tempo, voices = abc_music(_read(path))
        ends = {round(max((s + d for s, d, _ in n), default=0), 3) for n in voices.values() if n}
        if len(ends) > 1:
            misaligned.append((path.name, sorted(ends)))
        MIDI.mkdir(parents=True, exist_ok=True)
        h["midi"] = path.stem + ".mid"
        h["seconds"] = round(write_midi(tempo, voices, MIDI / h["midi"]))
        hymns[h["title"].lower()] = h
    for spec in EXTRA_HYMNS:
        h = wikipedia_hymn(spec) if spec.get("wikipedia") else hymnary_hymn(spec)
        hymns.setdefault(h["title"].lower(), h)
    for name, ends in misaligned:
        print(f"  voices end at different times: {name} {ends}", file=sys.stderr)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    data = {"source": "The Open Hymnal Project (openhymnal.org) and Hymnary.org, public-domain hymns",
            "hymns": sorted(hymns.values(), key=lambda h: h["title"].lower())}
    OUT.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"Wrote {len(hymns)} hymns ({unmetered} set out by punctuation, not meter) to {OUT}")


if __name__ == "__main__":
    main()
