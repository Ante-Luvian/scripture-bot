"""Old Norse in the Younger Futhark, the sixteen runes of the Viking Age, for the Edda's ᚱ Runes card.

A modern transcription, not the poems as they were ever written: the Edda comes down in Icelandic manuscripts of
the 13th century, in the Latin alphabet. It follows how Viking-Age carvers spelled, as the handbooks set it out:
sixteen runes for all the sounds, so one rune serves several letters (ᚴ k and g, ᛐ t and d, ᛒ b and p, ᚢ u, o, v
and y, ᛁ i, e and j, ᛆ a and æ, ᚦ þ and ð; the diphthongs ei and ey as ᛆᛁ and ᛆᚢ, as on the runestones' "stain"
for steinn); length unmarked; a rune never written twice running, even across
letters it stands for alike ("gk", "dt"); ᛦ for the r of endings that was once z (word-final after a consonant:
"maðr", "Baldr"), ᚱ elsewhere; ᚮ for ö and ǫ. Words are parted by ᛫, the carvers' dot.

The runes are Norway's mixed set (the owner's choice, 2026-11-08): the Edda's poems are West Norse, and Iceland took
its runes from Norway, where carvers wrote the short-twig forms of a, n, t and o (ᛆ ᚿ ᛐ ᚮ) beside the long-branch
h, m, b and s (ᚼ ᛘ ᛒ ᛋ). The card uses BabelStone Runic Norse, the typeface made for them.
"""
import re
import unicodedata

RUNE = {
    "f": "ᚠ", "u": "ᚢ", "ú": "ᚢ", "o": "ᚢ", "ó": "ᚢ", "v": "ᚢ", "w": "ᚢ", "y": "ᚢ", "ý": "ᚢ",
    "þ": "ᚦ", "ð": "ᚦ", "ö": "ᚮ", "ǫ": "ᚮ", "ø": "ᚮ", "œ": "ᚮ", "r": "ᚱ", "k": "ᚴ", "g": "ᚴ", "c": "ᚴ",
    "q": "ᚴ", "x": "ᚴᛋ", "h": "ᚼ", "n": "ᚿ", "i": "ᛁ", "í": "ᛁ", "e": "ᛁ", "é": "ᛁ", "j": "ᛁ",
    "a": "ᛆ", "á": "ᛆ", "æ": "ᛆ", "ę": "ᛆ", "s": "ᛋ", "z": "ᛋ", "t": "ᛐ", "d": "ᛐ", "b": "ᛒ", "p": "ᛒ",
    "m": "ᛘ", "l": "ᛚ",
}
DOT = "᛫"
VOWELS = set("aáæeéiíoóöǫøœuúyý")


def _word(word: str) -> str:
    w = unicodedata.normalize("NFC", word.lower())
    w = w.replace("ei", "ai").replace("ey", "au")        # (the diphthongs as carved: "stain" for steinn)
    out = []
    for n, ch in enumerate(w):
        rune = RUNE.get(ch, "")
        # (the ending -r, once z: ᛦ when the word ends in r after a consonant, or in rr)
        if ch == "r" and n == len(w) - 1 and n and w[n - 1] not in VOWELS:
            rune = "ᛦ"
        for r in rune:
            if r == "ᛦ" and out and out[-1] == "ᚱ":         # ("Þórr": the doubled r is one ᛦ)
                out[-1] = r
            elif not out or out[-1] != r:                   # (no rune twice running)
                out.append(r)
    return "".join(out)


def carve(text: str) -> str:
    """Old Norse text as one continuous run of runes, as on a runestone: no line breaks, every word parted by ᛫."""
    return DOT.join(w for w in (_word(w) for w in re.findall(r"[^\W\d_]+", text)) if w)


def to_runes(text: str) -> str:
    """Old Norse text, line for line, in Younger Futhark runes; punctuation dropped, words parted by ᛫."""
    lines = []
    for line in text.split("\n"):
        words = [_word(w) for w in re.findall(r"[^\W\d_]+", line)]
        lines.append(DOT.join(w for w in words if w))
    return "\n".join(lines)
