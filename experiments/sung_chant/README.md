# Sung chant (experiment, not used by the bot)

A prototype that *sings* Gregorian chant with its Latin words, built on
2026-10-13 to see whether the bot's chants could be sung instead of played on
the organ. The owner didn't want it in the bot ("not a fan of the chanting"),
but it's kept here because the eerie, not-quite-human sound might suit a horror
game.

`samples/` has what it made: *Te lucis ante terminum*, *Salve Regina* and
*Veni Creator Spiritus*.

## How it works

1. The chant's score comes from the GregoBase corpus (`scripts/build_chant.py`,
   which downloads and caches it). Each syllable of the gabc score has its notes.
2. **espeak-ng**'s Latin voice says each syllable on its own.
3. **WORLD** (the `pyworld` vocoder) takes that speech apart into pitch, timbre
   and breath, stretches the vowel to the length of the syllable's notes, replaces
   the pitch with the melody (short glides between notes, a little vibrato), and
   puts it back together.
4. Three copies, slightly detuned and delayed, make a small "choir"; a synthetic
   reverb adds the church. The melody is moved down to a man's range.

## Running it (Windows)

```
scoop install espeak-ng
pip install pyworld "setuptools<81" numpy
python experiments/sung_chant/sing.py
```

espeak-ng crashes without `ESPEAK_DATA_PATH`; the script sets it to the scoop
install folder. pyworld still imports `pkg_resources`, hence the old setuptools.
Change the list at the bottom of `sing.py` to sing other chants (GregoBase ids).

Things to try for a horror game: lower the pitch shift, slow it down, more
voices with wider detuning, reverse the reverb, or feed it other Latin text.
