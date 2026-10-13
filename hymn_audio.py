"""
Play a hymn's MIDI file (data/hymns/midi/, built by scripts/build_hymns.py)
as a WAV that Discord can play in the chat -- Discord shows a .mid as a
download, but has a player for audio files.

A small organ: each note is a few harmonics (the 8', 4', 2 2/3' and 2'
stops), shaped so repeated notes are heard as separate, with a little
room echo. The melody (the highest part) is a touch louder than the others.
"""
import io
import wave

import numpy as np

SAMPLE_RATE = 22050
HARMONICS = ((1, 1.0), (2, 0.5), (3, 0.22), (4, 0.18), (6, 0.07), (8, 0.04))
ATTACK, RELEASE, GAP = 0.025, 0.09, 0.035      # seconds
ECHO_SECONDS = 1.2


def midi_notes(path) -> list:
    """[(start seconds, end seconds, midi pitch, channel)]"""
    import mido
    notes, sounding, now = [], {}, 0.0
    for msg in mido.MidiFile(path):            # merged tracks, times in seconds at the file's tempo
        now += msg.time
        if msg.type == "note_on" and msg.velocity:
            sounding[(msg.channel, msg.note)] = now
        elif msg.type in ("note_off", "note_on"):
            start = sounding.pop((msg.channel, msg.note), None)
            if start is not None and now > start:
                notes.append((start, now, msg.note, msg.channel))
    return notes


def synthesize(notes: list) -> np.ndarray:
    if not notes:
        return np.zeros(SAMPLE_RATE, dtype=np.float32)
    end = max(n[1] for n in notes)
    # the melody is the part that sits highest (the first track in the Open Hymnal's
    # files, but not in every MIDI file)
    by_channel: dict = {}
    for _, _, pitch, channel in notes:
        by_channel.setdefault(channel, []).append(pitch)
    melody = max(by_channel, key=lambda c: sum(by_channel[c]) / len(by_channel[c]))
    out = np.zeros(int((end + RELEASE + ECHO_SECONDS) * SAMPLE_RATE) + 1, dtype=np.float32)
    for start, stop, pitch, channel in notes:
        held = max(stop - start - GAP, 0.06)
        n = int((held + RELEASE) * SAMPLE_RATE)
        t = np.arange(n, dtype=np.float32) / SAMPLE_RATE
        freq = 440.0 * 2 ** ((pitch - 69) / 12)
        tone = np.zeros(n, dtype=np.float32)
        for h, amp in HARMONICS:
            if freq * h < SAMPLE_RATE * 0.45:
                tone += amp * np.sin(2 * np.pi * freq * h * t)
        env = np.minimum(1.0, t / ATTACK)
        env *= np.clip((held + RELEASE - t) / RELEASE, 0.0, 1.0)
        i = int(start * SAMPLE_RATE)
        out[i:i + n] += tone * env * (1.0 if channel == melody else 0.7)
    # a little room: the dry sound plus a decaying noise echo
    rng = np.random.default_rng(7)
    m = int(ECHO_SECONDS * SAMPLE_RATE)
    impulse = rng.standard_normal(m).astype(np.float32) * np.exp(-np.arange(m) / (0.3 * SAMPLE_RATE))
    impulse /= np.sqrt(np.sum(impulse ** 2))
    size = 1 << int(np.ceil(np.log2(len(out) + m)))
    wet = np.fft.irfft(np.fft.rfft(out, size) * np.fft.rfft(impulse, size), size)[:len(out)]
    mixed = out + 0.35 * wet.astype(np.float32)
    peak = float(np.max(np.abs(mixed))) or 1.0
    return mixed * (0.85 / peak)


def to_wav(samples: np.ndarray) -> bytes:
    pcm = (np.clip(samples, -1, 1) * 32767).astype("<i2")
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SAMPLE_RATE)
        w.writeframes(pcm.tobytes())
    return buf.getvalue()


def render(midi_path) -> bytes:
    """A hymn's MIDI file -> WAV bytes."""
    return to_wav(synthesize(midi_notes(midi_path)))
