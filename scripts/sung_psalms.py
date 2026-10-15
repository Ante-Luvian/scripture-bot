"""
The psalms chanted in Latin to the Gregorian psalm tones, sung by the same voice as
the chants (build_sung_chant.py): `python scripts/sung_psalms.py 109 8G` renders Psalm
109 (Vulgate numbering; Dixit Dominus) in tone 8, ending G.

Sources, all from Benjamin Bloomfield's jgabc (github.com/bbloomf/jgabc), cached in
scripts/.cache/jgabc/:
- psalms/NNN.txt: the Vulgate psalms as the Breviary prints them, a verse a line,
  accents marked, "*" at the mediant and "†" at a flex;
- psalmtone.js: the tones of the Liber Usualis (g_tones, copied below as TONES) and the
  Gloria Patri; its getGabcTones() gives the flex note (FLEX below follows it);
- douay-rheims/Psalmi.txt: the Douay-Rheims English, for showing beside the Latin.

Pointing (fitting a half-verse's syllables to a tone) follows jgabc's rules: the tone's
first notes intone the first verse; a reciting note ("hr": "r" marks a note sung to as
many syllables as need it) carries the middle; each accented cadence note ("'") falls
on a stressed syllable no more than three syllables before the next fixed note, the
syllables between taking the filler note before it ("hr" after an accent), or else two
syllables back; a half-verse ending on a stressed monosyllable takes the cadence's last
notes together on it.
"""
import re
import sys
import unicodedata
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_chant as bc
import build_sung_chant as sung

CACHE = Path(__file__).resolve().parent / ".cache" / "jgabc"
BASE = "https://raw.githubusercontent.com/bbloomf/jgabc/master/"
UA = {"User-Agent": "ScriptureBotCorpusBuilder/1.0 (Discord bot; low-volume one-off import)"}

# jgabc psalmtone.js g_tones (the Liber Usualis tones), as written there
TONES = {
    "1": {"clef": "c4", "mediant": "f gh hr 'ixi hr 'g hr h.",
          "terminations": {"D": "hr g f 'gh gr gvFED.", "D-": "hr g f 'g gr gvFED.", "D2": "hr g f gr 'gf d.",
                           "f": "hr g f 'gh gr gf..", "g": "hr g f 'gh gr g.", "g2": "hr g f 'g gr ghg.",
                           "g3": "hr g f 'g gr g.", "a": "hr g f 'g hr h.", "a2": "hr g f 'g gr gh..",
                           "a3": "hr g f 'gh gr gh.."}},
    "2": {"clef": "f3", "mediant": "e f hr 'i hr h.", "terminations": {"D": "hr g 'e fr f."}},
    "3": {"clef": "c4", "mediant": "g hj jr 'k jr jr 'ih j.",
          "terminations": {"b": "jr h 'j jr i.", "a": "jr h 'j jr ih..", "a2": "jr ji hi 'h gr gh..",
                           "g": "jr ji hi 'h gr g.", "g2": "jr h j i 'h gr g."}},
    "4": {"clef": "c4", "mediant": "h gh hr g h 'i hr h.",
          "terminations": {"g": "hr 'h gr g.", "E": "hr g h ih gr 'gf e."}},
    "5": {"clef": "c3", "mediant": "d f hr 'i hr h.", "terminations": {"a": "hr 'i gr 'h fr f."}},
    "6": {"clef": "c4", "mediant": "f gh hr 'ixi hr 'g hr h.", "terminations": {"F": "hr f gh 'g fr f."}},
    "7": {"clef": "c3", "mediant": "hg hi ir 'k jr 'i jr j.",
          "terminations": {"a": "ir 'j ir 'h hr gf..", "b": "ir 'j ir 'h hr g.", "c": "ir 'j ir 'h hr gh..",
                           "c2": "ir 'j ir 'h hr ih..", "d": "ir 'j ir 'h hr gi.."}},
    "8": {"clef": "c4", "mediant": "g h jr 'k jr j.",
          "terminations": {"G": "jr i j 'h gr g.", "G*": "jr i j 'h gr gh..", "c": "jr h j 'k jr j."}},
}
GLORIA_PATRI = ["Glória Patri, et Fílio, * et Spirítui Sancto.",
                "Sicut erat in princípio, et nunc, et semper, * et in sǽcula sæculórum. Amen."]

RECITE, NOTE = 0.30, 0.38                      # seconds: a reciting syllable, a note of the cadence


# ── the sources ─────────────────────────────────────────────────────────────

def fetch(path: str) -> str:
    f = CACHE / path.replace("/", "_")
    if not f.exists():
        CACHE.mkdir(parents=True, exist_ok=True)
        f.write_bytes(urllib.request.urlopen(urllib.request.Request(BASE + path, headers=UA), timeout=60).read())
    return f.read_text(encoding="utf-8")


def latin_psalm(n: int) -> list:
    """The verses of a psalm (Vulgate numbering), as the Breviary divides them."""
    lines = [l.strip().lstrip("﻿") for l in fetch(f"psalms/{n:03d}.txt").splitlines()]   # (a BOM on line 1)
    return [l for l in lines if l]


def english_psalm(n: int) -> list:
    """[(verse, Douay-Rheims text)] for a psalm (Vulgate numbering)."""
    out = []
    for line in fetch("douay-rheims/Psalmi.txt").splitlines():
        parts = line.split("\t")
        if len(parts) >= 3 and parts[0] == str(n):
            out.append((int(parts[1]), parts[2].strip()))
    return out


# ── the tones ───────────────────────────────────────────────────────────────

def clef_pitch(clef: str):
    """gabc letter -> MIDI pitch under a clef (as build_chant.parse does)."""
    letter, base = bc._LINES[int(clef[1]) - 1], 0 if clef[0] == "c" else 3

    def pitch(c: str, flat: bool) -> int:
        n = base + "abcdefghijklm".index(c.lower()) - "abcdefghijklm".index(letter)
        octave, degree = divmod(n, 7)
        return 60 + 12 * octave + bc._SEMIS[degree] - (1 if flat else 0)
    return pitch


def tokens(formula: str, clef: str) -> list:
    """jgabc tone notation -> [{"accent", "open", "notes": [(pitch, seconds)], "letter"}]."""
    pitch, out = clef_pitch(clef), []
    for tok in formula.split():
        accent, body = tok.startswith("'"), tok.lstrip("'")
        open_ = body.endswith("r")
        body = body.rstrip("r")
        notes, flats, i = [], set(), 0
        while i < len(body):
            c = body[i]
            if c.lower() in "abcdefghijklm":
                if i + 1 < len(body) and body[i + 1] == "x":           # a flat sign before the note
                    flats.add(c.lower()); i += 2; continue
                notes.append([pitch(c, c.lower() in flats), RECITE if open_ else NOTE])
            elif c == "." and notes:
                notes[-1][1] = NOTE * 2                                 # a dotted (held) note
            i += 1
        out.append({"accent": accent, "open": open_, "notes": [tuple(n) for n in notes],
                    "letter": body[0].lower() if body else "", "gabc": body})
    return out


def flex_formula(tenor: str, clef: str) -> str:
    """jgabc getGabcTones(): the flex drops a step below the tenor, or a third where the step
    below is a semitone (tenor on do or fa)."""
    line = int(clef[-1])
    tone_number = (int(tenor, 36) - 10 + 16 - ((6 if clef[0] == "f" else 1) + line * 2)) % 8
    flex = chr(ord(tenor) - (2 if tone_number in (0, 3) else 1))
    return f"{tenor} {tenor}r '{tenor} {flex}r {flex}."


# ── Latin words: syllables and stress ───────────────────────────────────────

ACCENTED = "áéíóúýǽ"
VOWEL = "aeiouyæœëïü" + ACCENTED                  # (ë, ï, ü: sounded apart, never a diphthong)


def base(c: str) -> str:
    return "".join(x for x in unicodedata.normalize("NFKD", c.lower()) if not unicodedata.combining(x)) or c


def syllabify(word: str) -> list:
    """['Dó', 'mi', 'nus'], roughly as the chant books divide them (only the count and the
    stressed one matter here; the pronunciation looks across the breaks anyway)."""
    w, nuclei, i = word, [], 0
    low = w.lower()
    while i < len(w):
        c = low[i]
        if c in VOWEL:
            prev = base(low[i - 1]) if i else ""
            if c in "uú" and prev in ("q", "g") and i + 1 < len(w) and low[i + 1] in VOWEL and \
                    (prev == "q" or (i >= 2 and base(low[i - 2]) == "n")):
                i += 1; continue                                        # qui, sanguis: u is a consonant
            if c in "ií" and i + 1 < len(w) and low[i + 1] in VOWEL and (i == 0 or low[i - 1] in VOWEL):
                i += 1; continue                                        # a consonant i (eius, Iesu)
            j = i + 1
            if j < len(w) and low[j] in "ëïü":
                pass
            elif j < len(w) and base(c) in ("a", "o") and base(low[j]) == "e" or \
                    j < len(w) and base(c) == "a" and base(low[j]) == "u":
                j += 1                                                  # ae, oe, au
            nuclei.append((i, j))
            i = j
        else:
            i += 1
    if len(nuclei) <= 1:
        return [w]
    cuts = []
    for (a, b), (c, d) in zip(nuclei, nuclei[1:]):
        cons = c - b
        if cons <= 1:
            cuts.append(b)
        else:
            pair = base(low[c - 2]) + base(low[c - 1])
            keep = 2 if pair[0] in "bcdgptf" and pair[1] in "lr" or pair in ("ch", "ph", "th") else 1
            cuts.append(c - keep)
    pieces, start = [], 0
    for cut in cuts:
        pieces.append(w[start:cut]); start = cut
    pieces.append(w[start:])
    return pieces


def syllables(half: str) -> list:
    """[{"text", "accent", "start"}] for a half-verse."""
    out = []
    for word in half.split():
        letters = re.sub(r"[^\w]", "", word)
        if not letters:
            continue
        sy = syllabify(word)
        marked = [any(ch in ACCENTED for ch in s.lower()) for s in sy]
        if not any(marked) and len(sy) >= 2:
            marked[-2] = True                                           # an unmarked two-syllable word
        for k, s in enumerate(sy):
            out.append({"text": s, "accent": marked[k], "start": k == 0})
    if out and len([s for s in out[-1:] if s["start"]]) and not out[-1]["accent"]:
        out[-1]["accent"] = True                                        # a closing monosyllable is stressed
    return out


# ── pointing ────────────────────────────────────────────────────────────────

class Notes(list):
    """A syllable's notes [(pitch, seconds)], also carrying them as gabc for the score."""

    def __init__(self, notes, gabc: str):
        super().__init__(notes)
        self.gabc = gabc


def _n(tok: dict) -> Notes:
    return Notes(tok["notes"], tok["gabc"])


def point(sylls: list, formula: str, clef: str, intone: bool) -> list:
    """Each syllable's notes [(pitch, seconds)] under a tone's mediant, termination or flex."""
    toks = tokens(formula, clef)
    tenor_i = next(i for i, t in enumerate(toks) if t["open"])
    intonation, tenor, cadence = toks[:tenor_i], toks[tenor_i], toks[tenor_i + 1:]
    n = len(sylls)
    notes = [None] * n
    pos = n - 1
    if n and sylls[-1]["accent"] and len(sylls[-1]["text"]) and any(t["accent"] for t in cadence) \
            and sylls[-1]["start"]:
        k = max(i for i, t in enumerate(cadence) if t["accent"])        # a final monosyllable: the rest together
        rest = [t for t in cadence[k:] if not t["open"]]
        notes[pos] = Notes([x for t in rest for x in t["notes"]], "".join(t["gabc"].rstrip(".") for t in rest) + ".")
        pos -= 1
        cadence = cadence[:k]
    filler, i = None, len(cadence) - 1
    while i >= 0 and pos >= 0:
        t = cadence[i]
        if t["open"]:
            filler = t
        elif t["accent"]:
            a = pos
            if filler:
                nxt = pos + 1
                a = next((j for j in range(pos, max(nxt - 3, 0) - 1, -1) if sylls[j]["accent"]), max(nxt - 2, 0))
                a = min(a, pos)
                for j in range(a + 1, pos + 1):
                    notes[j] = _n(filler)
                filler = None
            notes[a] = _n(t)
            pos = a - 1
        else:
            notes[pos] = _n(t)
            pos -= 1
        i -= 1
    k = 0
    if intone:
        for t in intonation:
            if k <= pos:
                notes[k] = _n(t); k += 1
    for j in range(k, pos + 1):
        notes[j] = _n(tenor)
    return notes


def _pointed(lines: list, tone: str, ending: str, gloria: bool) -> list:
    """[[syllable, Notes, pause after, starts a word, bar after]] for the whole psalm."""
    t = TONES[tone]
    clef, termination = t["clef"], t["terminations"][ending]
    tenor = next(tok["letter"] for tok in tokens(t["mediant"], clef) if tok["open"])
    out = []
    for v, line in enumerate(lines + (GLORIA_PATRI if gloria else [])):
        first, _, second = line.partition("*")
        parts = []
        if "†" in first:
            flex, _, first = first.partition("†")
            parts.append((flex, flex_formula(tenor, clef), 0.3, False, "†(,)"))
        parts += [(first, t["mediant"], 0.6, v == 0 and not parts, "*(:)"), (second, termination, 1.0, False, "(::)")]
        for text, formula, pause, intone, bar in parts:
            sy = syllables(text)
            if not sy:
                continue
            for s, ns in zip(sy, point(sy, formula, clef, intone)):
                out.append([s["text"], ns or Notes([(60, RECITE)], "h"), 0.0, s["start"], ""])
            out[-1][2], out[-1][4] = pause, bar
    return out


def chant_lines(lines: list, tone: str, ending: str, gloria: bool = True) -> list:
    """The psalm as sung syllables [[text, notes, pause, starts a word]] for build_sung_chant.render."""
    return [s[:4] for s in _pointed(lines, tone, ending, gloria)]


def score_gabc(lines: list, tone: str, ending: str, gloria: bool = True) -> str:
    """The pointed psalm as gabc, for drawing its score (scripts/score/render.js)."""
    out = [f"({TONES[tone]['clef']})"]
    for text, notes, _, start, bar in _pointed(lines, tone, ending, gloria):
        syl = f"{text.replace('(', '').replace(')', '')}({notes.gabc})"
        out.append((" " if start else "") + syl)
        if bar:
            out.append(" " + bar)
    return "".join(out).strip()


if __name__ == "__main__":
    psalm = int(sys.argv[1]) if len(sys.argv) > 1 else 109
    tone, ending = (re.match(r"(\d)(.*)", sys.argv[2]).groups() if len(sys.argv) > 2 else ("8", "G"))
    out = Path(sys.argv[3]) if len(sys.argv) > 3 else Path(f"psalm-{psalm:03d}-{tone}{ending}.ogg")
    sylls = chant_lines(latin_psalm(psalm), tone, ending)
    for s in sylls[:40]:
        print(s[0], [round(p) for p, _ in s[1]], s[2] or "", "|" if s[3] else "")
    print(sung.render(sylls, out, f"Psalm {psalm} (tone {tone}{ending})"))
