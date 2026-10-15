"""
Sings every Gregorian chant in more_hymns.json with its Latin words, for !chant and the
🎤 Sung button: data/hymns/audio/sung/chant-NNNNN.ogg (the GregoBase id, like the organ's).

    python scripts/build_sung_chant.py            # renders what's missing
    python scripts/build_sung_chant.py --all      # renders everything again
    python scripts/build_sung_chant.py 3326       # just these GregoBase ids

The voice is MBROLA (a diphone synthesiser: deliberately plain and "primitive", which the
owner chose over a more realistic one; see experiments/sung_chant/) with its Italian male
voice it3, singing ecclesiastical Latin, which is pronounced the Italian way. MBROLA reads a
.pho file: a phoneme a line, its length in ms, then pitch points (percent of the phoneme,
Hz). So each sung syllable becomes phonemes, its vowel gets the length of its notes, and the
vowel's pitch is pinned to them, a note at a time. Three copies a hair out of tune and time,
in a synthetic church reverb, make the "schola".

scripts/mbrola/ has mbrola.exe (MBROLA 3.3, github.com/numediart/MBROLA, built with
`zig cc -O2 -w -DLITTLE_ENDIAN -DTARGET_OS_WIN` over Standalone/synth.c and the Database,
Engine, Misc and Parser sources; -w because of an old int/long function-pointer mismatch)
and voices/it3/it3 (github.com/numediart/MBROLA-voices).
"""
import concurrent.futures
import json
import re
import subprocess
import sys
import tempfile
import unicodedata
import wave
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_chant as bc                          # the GregoBase corpus and its gabc helpers

ROOT = bc.ROOT
MBROLA = Path(__file__).resolve().parent / "mbrola" / "mbrola.exe"
VOICE = Path(__file__).resolve().parent / "mbrola" / "voices" / "it3" / "it3"
OUT = ROOT / "data" / "hymns" / "audio" / "sung"
CHANTS = ROOT / "data" / "hymns" / "more_hymns.json"
FS = 16000                                        # it3's sample rate
BITRATE = "48k"                                   # the owner's choice: as in the sample they approved


# ── the score: syllables, their notes, and where words start ────────────────

def syllables(score: str) -> list:
    """[[syllable text, [(midi pitch, seconds)], pause after, starts a word]] from a gabc score."""
    clef_letter, clef_note, bflat = "j", 0, False
    flats, out, word_break = set(), [], True
    for syl, neumes in re.findall(r"([^()]*)\(([^)]*)\)", score):
        raw = syl
        syl = re.sub(r"\s*\d+\.\s*", " ", bc.clean_syllable(syl))
        neumes = re.sub(r"\[[^\]]*\]", "", neumes)
        clef = re.fullmatch(r"\s*([cf])(b?)([1-4])\s*", neumes)
        if clef:
            clef_letter = bc._LINES[int(clef.group(3)) - 1]
            clef_note = 0 if clef.group(1) == "c" else 3
            bflat = bool(clef.group(2))
            word_break = True
            continue
        notes, pause, i = [], 0.0, 0
        while i < len(neumes):
            c = neumes[i]
            low, nxt = c.lower(), neumes[i + 1] if i + 1 < len(neumes) else ""
            if c in ",;:":
                double = c == ":" and nxt == ":"
                pause += 1.0 if double else {",": 0.25, ";": 0.4, ":": 0.6}[c]
                flats.clear()
                i += 2 if double else 1
                continue
            if "a" <= low <= "m":
                if nxt in ("x", "y", "#"):
                    (flats.add if nxt == "x" else flats.discard)(low)
                    i += 2
                    continue
                if nxt == "+":                        # a custos: not sung
                    i += 2
                    continue
                n = clef_note + "abcdefghijklm".index(low) - "abcdefghijklm".index(clef_letter)
                octave, degree = divmod(n, 7)
                pitch = 60 + 12 * octave + bc._SEMIS[degree]
                if low in flats or (bflat and degree == 6):
                    pitch -= 1
                length, j = 0.42, i + 1
                while j < len(neumes) and neumes[j] in "vVos~<>'_.wWrRq1234-!/@":
                    if neumes[j] == ".":
                        length = 0.84
                    elif neumes[j] == "_":
                        length = max(length, 0.6)
                    j += 1
                notes.append((pitch, length))
                i = j
                continue
            i += 1
        text = re.sub(r"[*†~℣℟]", "", syl).strip()
        if notes:
            out.append([text, notes, pause, raw[:1].isspace() or word_break])
            word_break = False
        elif out:
            out[-1][2] += pause
        if not notes and raw.strip() == "":
            word_break = True
    return out


# ── ecclesiastical Latin as Italian phonemes (it3's SAMPA) ──────────────────

VOWELS = "aeiou"
SOFT = ("e", "i")                                 # c, g, sc go soft before these (ae, oe are e by then)


def plain(text: str) -> str:
    t = text.lower().replace("æ", "e").replace("œ", "e").replace("ǽ", "e")
    t = "".join(c for c in unicodedata.normalize("NFKD", t) if not unicodedata.combining(c))
    t = t.replace("ae", "e").replace("oe", "e").replace("y", "i").replace("j", "i").replace("k", "c")
    return re.sub(r"[^a-z]", "", t)


def phonemes(syl: str, before: str, after: str) -> list:
    """One syllable's phonemes; `before`/`after` are the rest of its word, since Latin spelling
    rules look across the syllable break (re-gnum, i-sti-tu-ti-o)."""
    s, out, i = plain(syl), [], 0
    word, k = before + s + after, len(before)

    def at(j):
        return word[j] if 0 <= j < len(word) else ""

    while i < len(s):
        c, n, p, n2 = s[i], at(k + i + 1), at(k + i - 1), at(k + i + 2)
        if c == "h":
            if p == "i" and n == "i":                           # mihi, nihil: "miki"
                out.append("k")
            i += 1
        elif c in VOWELS:
            if c == "i" and n in tuple(VOWELS) and (p == "" or p in VOWELS):
                out.append("j")                                 # Iesu, eius: a consonant i
            elif c == "u" and p in ("q", "g") and n in tuple(VOWELS) and not (p == "g" and at(k + i - 2) != "n"):
                out.append("w")                                 # qui, sanguis (but not "Gubernat")
            else:
                out.append({"e": "E", "o": "O"}.get(c, c))
            i += 1
        elif c == "q":
            out.append("k"); i += 1
        elif c == "x":
            out += ["k", "s"]; i += 1
        elif c == "z":
            out.append("dz"); i += 1
        elif c in "ct" and n == "h":
            out.append("k" if c == "c" else "t"); i += 2
        elif c == "p" and n == "h":
            out.append("f"); i += 2
        elif c == "g" and n == "n":
            out.append("J"); i += 2 if i + 1 < len(s) else 1      # regnum, agnus: "ny"
        elif c == "s" and n == "c" and n2 in SOFT:
            out.append("S"); i += 2 if i + 1 < len(s) else 1      # descendit: "deshendit"
        elif c == "c":
            if n == "c" and n2 in SOFT:                         # ecce: "ettche"
                out.append("t")
            else:
                out.append("tS" if n in SOFT else "k")
            i += 1
        elif c == "g":
            out.append("dZ" if n in SOFT else "g"); i += 1
        elif c == "t" and n == "i" and p not in ("s", "t", "x") and n2 in tuple(VOWELS):
            out.append("ts"); i += 1                            # gratia: "gratsia"
        else:
            if c in "pbtdfvmnlrs":
                out.append(c)
            i += 1
    return out


CONSONANT_MS = {"r": 45, "l": 60, "m": 70, "n": 65, "J": 80, "j": 60, "w": 50, "S": 100, "s": 95,
                "f": 90, "v": 70, "ts": 110, "tS": 105, "dZ": 95, "dz": 100}


def hz(midi: float) -> float:
    return 440.0 * 2 ** ((midi - 69) / 12)


def pho(sylls: list, shift: float, detune: float) -> str:
    lines, words = ["_ 300"], []
    for text, notes, pause, start in sylls:
        if start or not words:
            words.append([])
        words[-1].append((text, notes, pause))
    for word in words:
        letters = [plain(t) for t, _, _ in word]
        for w, (text, notes, pause) in enumerate(word):
            ph = phonemes(text, "".join(letters[:w]), "".join(letters[w + 1:]))
            total = sum(l for _, l in notes) * 1000
            nuc = next((j for j, x in enumerate(ph) if x in "aEiOu"), None)
            if nuc is None:                             # a stray consonant, or a vocalise with no text
                ph, nuc = ph + ["a"], len(ph)
            cons = [(x, CONSONANT_MS.get(x, 70)) for x in ph[:nuc]]
            tail = [(x, CONSONANT_MS.get(x, 70)) for x in ph[nuc + 1:]]
            vowel_ms = max(total - sum(d for _, d in cons) - sum(d for _, d in tail), 120)
            first, last = hz(notes[0][0] + shift) * detune, hz(notes[-1][0] + shift) * detune
            lines += [f"{x} {d} 0 {first:.1f} 100 {first:.1f}" for x, d in cons]
            # the vowel holds each note in turn, with a plain step between (no glide, no vibrato)
            points, t = [], 0.0
            for pitch, length in notes:
                share = length * 1000 / max(total, 1) * vowel_ms
                f = hz(pitch + shift) * detune
                points += [(100 * t / vowel_ms, f), (100 * min(t + share - 15, vowel_ms) / vowel_ms, f)]
                t += share
            lines.append(f"{ph[nuc]} {vowel_ms:.0f} " +
                         " ".join(f"{max(0, min(100, a)):.0f} {f:.1f}" for a, f in points))
            lines += [f"{x} {d} 0 {last:.1f} 100 {last:.1f}" for x, d in tail]
            if pause:
                lines.append(f"_ {pause * 1000:.0f}")
    lines.append("_ 600")
    return "\n".join(lines) + "\n"


# ── the voice, the schola, the church ───────────────────────────────────────

def mbrola(text: str, tmp: Path) -> np.ndarray:
    (tmp / "in.pho").write_text(text, encoding="ascii")
    subprocess.run([str(MBROLA), "-e", str(VOICE), str(tmp / "in.pho"), str(tmp / "out.wav")],
                   check=True, capture_output=True)
    with wave.open(str(tmp / "out.wav")) as w:
        return np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float64) / 32768


def reverb(x: np.ndarray, seconds: float = 2.2) -> np.ndarray:
    n = int(seconds * FS)
    ir = np.random.default_rng(0).standard_normal(n) * np.exp(-np.arange(n) / FS * 6.9 / seconds)
    ir[0] = 0
    m = len(x) + n
    wet = np.fft.irfft(np.fft.rfft(x, m) * np.fft.rfft(ir, m), m)
    wet /= np.max(np.abs(wet)) + 1e-9
    dry = np.pad(x, (0, n)) / (np.max(np.abs(x)) + 1e-9)
    return 0.75 * dry + 0.35 * wet


def sing(gid: int, score: str, title: str) -> str:
    return render(syllables(score), OUT / f"chant-{gid:05d}.ogg", title)


def render(sylls: list, out: Path, title: str) -> str:
    """Sing [[text, [(pitch, seconds)], pause, starts a word]] to an Ogg file, as the schola."""
    pitches = [p for _, ns, _, _ in sylls for p, _ in ns]
    shift = 52 - float(np.median(pitches))                      # a man's range, around E below middle C
    with tempfile.TemporaryDirectory() as tmp:
        voices = [np.pad(mbrola(pho(sylls, shift, detune), Path(tmp)), (int(delay * FS), 0))
                  for detune, delay in ((1.0, 0.0), (1.007, 0.02), (0.994, 0.035))]
    n = max(len(v) for v in voices)
    mix = reverb(sum(np.pad(v, (0, n - len(v))) for v in voices))
    pcm = (mix / (np.max(np.abs(mix)) + 1e-9) * 0.9 * 32767).astype(np.int16)
    buf = Path(tempfile.gettempdir()) / f"sung-{out.stem}.wav"
    with wave.open(str(buf), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(FS); w.writeframes(pcm.tobytes())
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", str(buf), "-c:a", "libopus", "-b:a", BITRATE,
                    "-metadata", f"title={title}", str(out)], check=True)
    buf.unlink()
    return out.name


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    chants = {h["gregobase"]: h["title"] for h in json.loads(CHANTS.read_text(encoding="utf-8"))["hymns"]
              if h.get("gregobase")}
    only = {int(a) for a in sys.argv[1:] if a.isdigit()}
    rows = {int(r["id"]): r for r in bc.chosen(bc.corpus())}
    todo = [g for g in sorted(chants) if (not only or g in only)
            and ("--all" in sys.argv or only or not (OUT / f"chant-{g:05d}.ogg").exists())]
    print(f"{len(todo)} to sing")
    with concurrent.futures.ProcessPoolExecutor() as pool:
        jobs = {pool.submit(sing, g, bc.full_score(rows[g]), chants[g]): g for g in todo}
        for done, job in enumerate(concurrent.futures.as_completed(jobs), 1):
            try:
                job.result()
            except Exception as e:
                print(f"  {jobs[job]} {chants[jobs[job]]}: {e}")
            if done % 50 == 0:
                print(f"  {done}/{len(todo)}", flush=True)
    size = sum(f.stat().st_size for f in OUT.glob("*.ogg"))
    print(f"sung: {len(list(OUT.glob('*.ogg')))} files, {size / 1e6:.1f} MB")


if __name__ == "__main__":
    main()
