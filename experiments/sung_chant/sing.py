"""Prototype: sing a GregoBase chant with espeak-ng (Latin) + WORLD (pyworld) re-pitching.
Not used by the bot -- see README.md here.

    python experiments/sung_chant/sing.py          # writes sung/*.wav and *.ogg next to this file
"""
import io, json, os, re, subprocess, sys, unicodedata, wave
from pathlib import Path
import numpy as np
import pyworld

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
import build_chant as bc                   # the GregoBase corpus and gabc helpers

ESPEAK = str(Path.home() / "scoop/apps/espeak-ng/current/espeak-ng.exe")
FS = 22050
FP = 5.0                                   # WORLD frame period, ms
OUT = Path(__file__).parent / "sung"
OUT.mkdir(exist_ok=True)


def syllables(score):
    """[(syllable text, [(pitch, seconds)], pause_after)] from a gabc score."""
    tokens = re.findall(r"([^()]*)\(([^)]*)\)", score)
    clef_letter, clef_note, bflat = "j", 0, False
    flats = set()
    out = []
    for syl, neumes in tokens:
        syl = bc.clean_syllable(syl)
        syl = re.sub(r"\s*\d+\.\s*", " ", syl)
        neumes = re.sub(r"\[[^\]]*\]", "", neumes)
        clef = re.fullmatch(r"\s*([cf])(b?)([1-4])\s*", neumes)
        if clef:
            clef_letter = bc._LINES[int(clef.group(3)) - 1]
            clef_note = 0 if clef.group(1) == "c" else 3
            bflat = bool(clef.group(2))
            continue
        notes, pause = [], 0.0
        i = 0
        while i < len(neumes):
            c = neumes[i]; low = c.lower(); nxt = neumes[i + 1] if i + 1 < len(neumes) else ""
            if c in ",;:":
                double = c == ":" and nxt == ":"
                pause += 1.0 if double else {",": 0.25, ";": 0.4, ":": 0.6}[c]
                flats.clear()
                i += 2 if double else 1
                continue
            if "a" <= low <= "m":
                if nxt in ("x", "y", "#"):
                    (flats.add if nxt == "x" else flats.discard)(low); i += 2; continue
                if nxt == "+":
                    i += 2; continue
                n = clef_note + "abcdefghijklm".index(low) - "abcdefghijklm".index(clef_letter)
                octave, degree = divmod(n, 7)
                pitch = 60 + 12 * octave + bc._SEMIS[degree]
                if low in flats or (bflat and degree == 6):
                    pitch -= 1
                length = 0.42
                j = i + 1
                while j < len(neumes) and neumes[j] in "vVos~<>'_.wWrRq1234-!/@":
                    if neumes[j] == ".": length = 0.84
                    elif neumes[j] == "_": length = max(length, 0.6)
                    j += 1
                notes.append((pitch, length))
                i = j
                continue
            i += 1
        text = re.sub(r"[*†~]", "", syl).strip()
        if notes:
            out.append([text, notes, pause])
        elif out:
            out[-1][2] += pause
    return out


def speak(text):
    """espeak-ng's Latin voice saying text, as float samples (trimmed)."""
    t = unicodedata.normalize("NFKD", text.replace("æ", "ae").replace("œ", "oe").replace("ǽ", "ae"))
    t = "".join(c for c in t if not unicodedata.combining(c))
    t = re.sub(r"[^A-Za-z]", "", t) or "a"
    tmp = OUT / "_syl.wav"
    subprocess.run([ESPEAK, "-v", "la", "-s", "120", "-p", "40", "-w", str(tmp), t], check=True,
                   env={**os.environ, "ESPEAK_DATA_PATH": str(Path(ESPEAK).parent)})
    with wave.open(str(tmp)) as w:
        x = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float64) / 32768
    loud = np.flatnonzero(np.abs(x) > 0.02)
    return x[max(0, loud[0] - 100):loud[-1] + 100] if len(loud) else x


def hz(midi):
    return 440.0 * 2 ** ((midi - 69) / 12)


def sing_syllable(text, notes, shift, detune=1.0):
    x = speak(text)
    f0, sp, ap = pyworld.wav2world(x, FS, frame_period=FP)
    voiced = np.flatnonzero(f0 > 0)
    total = sum(l for _, l in notes)
    frames_total = int(total * 1000 / FP)
    if len(voiced) == 0:
        idx = np.linspace(0, len(f0) - 1, max(frames_total, 1)).astype(int)
        return pyworld.synthesize(np.zeros(len(idx)), sp[idx], ap[idx], FS, FP)
    a, b = voiced[0], voiced[-1] + 1
    head, tail = list(range(0, a)), list(range(b, len(f0)))
    mid_frames = max(frames_total - len(head) - len(tail) // 2, 8)
    mid = np.linspace(a, b - 1, mid_frames).round().astype(int)
    idx = np.array(head + list(mid) + tail)
    # the melody over the voiced part: each note in turn, a short glide between, a little vibrato
    contour = []
    for p, l in notes:
        contour += [hz(p + shift) * detune] * max(1, int(l * 1000 / FP))
    contour = np.interp(np.linspace(0, len(contour) - 1, mid_frames), np.arange(len(contour)), contour)
    k = 6                                                      # 30 ms glides
    smooth = np.convolve(np.pad(contour, k, mode="edge"), np.ones(2 * k + 1) / (2 * k + 1), mode="valid")
    tt = np.arange(mid_frames) * FP / 1000
    smooth *= 2 ** (0.12 * np.sin(2 * np.pi * 5.2 * tt) * np.clip(tt / 0.4, 0, 1) / 12)
    newf0 = np.concatenate([np.zeros(len(head)), smooth, np.zeros(len(tail))])
    return pyworld.synthesize(newf0, np.ascontiguousarray(sp[idx]), np.ascontiguousarray(ap[idx]), FS, FP)


def voice(sylls, shift, detune, delay):
    parts = [np.zeros(int(delay * FS))]
    for text, notes, pause in sylls:
        parts.append(sing_syllable(text, notes, shift, detune))
        if pause:
            parts.append(np.zeros(int(pause * FS)))
    return np.concatenate(parts)


def reverb(x, seconds=2.2):
    n = int(seconds * FS)
    rng = np.random.default_rng(0)
    ir = rng.standard_normal(n) * np.exp(-np.arange(n) / FS * 6.9 / seconds)
    ir[0] = 0
    m = len(x) + n
    wet = np.fft.irfft(np.fft.rfft(x, m) * np.fft.rfft(ir, m), m)
    wet /= np.max(np.abs(wet)) + 1e-9
    dry = np.pad(x, (0, n)) / (np.max(np.abs(x)) + 1e-9)
    return 0.75 * dry + 0.35 * wet


def sing(gid, name):
    z = bc.corpus()
    row = next(r for r in bc.chosen(z) if int(r["id"]) == gid)
    sylls = syllables(bc.full_score(row))
    pitches = [p for _, ns, _ in sylls for p, _ in ns]
    shift = 55 - float(np.median(pitches))                     # a man's voice, around G below middle C
    voices = [voice(sylls, shift, d, dl) for d, dl in ((1.0, 0.0), (1.006, 0.018), (0.995, 0.031))]
    n = max(len(v) for v in voices)
    mix = sum(np.pad(v, (0, n - len(v))) for v in voices)
    mix = reverb(mix)
    mix = (mix / np.max(np.abs(mix)) * 0.9 * 32767).astype(np.int16)
    out = OUT / f"{name}.wav"
    with wave.open(str(out), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(FS); w.writeframes(mix.tobytes())
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", str(out), "-c:a", "libopus", "-b:a", "48k",
                    str(OUT / f"{name}.ogg")], check=True)
    print(name, len(sylls), "syllables", round(n / FS), "s; notes", round(sum(l for _, ns, _ in sylls for _, l in ns)), "s; pauses", round(sum(p for *_, p in sylls)), "s")


if __name__ == "__main__":
    for gid, name in [(1843, "te-lucis")][: 1 if "--one" in sys.argv else 9] + ([] if "--one" in sys.argv else [(2715, "salve-regina"), (2923, "veni-creator")]):
        sing(gid, name)
