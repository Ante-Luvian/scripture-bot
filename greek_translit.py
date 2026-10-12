"""
Scholarly transliteration of polytonic Greek word forms (used by
!interlinear and !notes).
"""
import unicodedata

_GREEK_TRANSLIT_ROUGH = "̔"       # combining reversed comma above (rough breathing)
_GREEK_TRANSLIT_ACUTE = "́"
_GREEK_TRANSLIT_GRAVE = "̀"
_GREEK_TRANSLIT_CIRCUMFLEX = "͂"  # combining greek perispomeni
_GREEK_TRANSLIT_DIAERESIS = "̈"
_GREEK_TRANSLIT_IOTA_SUB = "ͅ"
_GREEK_TRANSLIT_BASE = {
    "α": "a", "β": "b", "γ": "g", "δ": "d", "ε": "e", "ζ": "z", "η": "e",
    "θ": "th", "ι": "i", "κ": "k", "λ": "l", "μ": "m", "ν": "n", "ξ": "x",
    "ο": "o", "π": "p", "ρ": "r", "σ": "s", "ς": "s", "τ": "t", "υ": "y",
    "φ": "ph", "χ": "ch", "ψ": "ps", "ω": "o",
}
_GREEK_TRANSLIT_LONG = {"η", "ω"}  # get a macron; circumflex is dropped as redundant on these
_GREEK_TRANSLIT_VOWELS = set("αεηιοωυ")
_GREEK_TRANSLIT_DIPHTHONGS = {
    "αι": "ai", "ει": "ei", "οι": "oi", "υι": "ui",
    "αυ": "au", "ευ": "eu", "ου": "ou", "ηυ": "eu",
}


def _greek_translit_accent(marks: str, base_is_long: bool) -> str | None:
    if _GREEK_TRANSLIT_GRAVE in marks:
        return "grave"
    if _GREEK_TRANSLIT_ACUTE in marks:
        return "acute"
    if _GREEK_TRANSLIT_CIRCUMFLEX in marks:
        return None if base_is_long else "circumflex"  # dropped on eta/omega: the macron already shows length
    return None


def _greek_translit_compose(latin: str, is_long: bool, accent: str | None, diaeresis: bool, iota_sub: bool) -> str:
    s = latin
    if is_long:
        s += "̄"  # combining macron
    if diaeresis:
        s += _GREEK_TRANSLIT_DIAERESIS  # must precede the accent mark to match Unicode's precomposed order (e.g. ḯ)
    if accent == "acute":
        s += _GREEK_TRANSLIT_ACUTE
    elif accent == "grave":
        s += _GREEK_TRANSLIT_GRAVE
    elif accent == "circumflex":
        s += "̂"
    s = unicodedata.normalize("NFC", s)
    if iota_sub:
        s += "i"
    return s


def _transliterate_greek(word: str) -> str:
    """Standard scholarly transliteration of an actual Greek word FORM as
    it appears in the text -- not its dictionary lemma. MACULA's Greek
    dataset has no per-instance transliteration column (unlike its Hebrew
    one), so this exists to avoid the alternative of showing a lexicon's
    lemma-form transliteration (e.g. "ho") next to a different inflected
    form actually on screen (e.g. "τὸν", which transliterates to "ton") --
    those don't match, and looked exactly as wrong as it sounds.

    Matches the accent/breathing convention already used by the local
    Strong's dictionary (verified against all 5,523 of its Greek entries
    that have both a lexeme and a transliteration: 99.95% exact match --
    the only misses are one word pair where that dictionary itself is
    internally inconsistent, and one non-alphabetic numeral entry, "666"
    spelled with numeral-letters rather than a word):
      - acute/grave get their own accent mark; circumflex too, EXCEPT on
        eta/omega, where it's dropped as redundant (the macron already
        shows vowel length, and circumflex there marks nothing extra).
      - rough breathing prepends "h" (also on rho: rh, and word-medial
        double-rho, which is smooth+rough by convention: rrh).
      - a diaeresis on what would otherwise be the second half of a
        diphthong breaks it into two separate syllables, each
        transliterated on its own, with the diaeresis preserved.
      - iota subscript is rendered as a trailing "i" rather than dropped.
      - diphthong breathing/accent/diaeresis live on the SECOND Greek
        letter of the pair, per Greek orthography."""
    decomposed = unicodedata.normalize("NFD", word)
    clusters = []
    for ch in decomposed:
        if unicodedata.combining(ch) and clusters:
            clusters[-1] = (clusters[-1][0], clusters[-1][1] + ch)
        else:
            clusters.append((ch, ""))

    out = []
    i, n = 0, len(clusters)
    while i < n:
        base, marks = clusters[i]
        lower = base.lower()
        is_upper = base.isupper()

        if lower not in _GREEK_TRANSLIT_BASE:
            out.append(base)
            i += 1
            continue

        if lower == "γ" and i + 1 < n and clusters[i + 1][0].lower() in ("γ", "κ", "ξ", "χ"):
            out.append("N" if is_upper else "n")
            i += 1
            continue

        if lower == "ρ":
            translit = "rh" if _GREEK_TRANSLIT_ROUGH in marks else "r"
            if is_upper:
                translit = translit[0].upper() + translit[1:]
            out.append(translit)
            i += 1
            continue

        is_diphthong = (
            lower in "αεοηυ" and i + 1 < n and clusters[i + 1][0].lower() in _GREEK_TRANSLIT_VOWELS
            and (lower + clusters[i + 1][0].lower()) in _GREEK_TRANSLIT_DIPHTHONGS
        )
        if is_diphthong and _GREEK_TRANSLIT_DIAERESIS in clusters[i + 1][1]:
            is_diphthong = False  # a trema explicitly breaks the diphthong

        if is_diphthong:
            base2, marks2 = clusters[i + 1]
            pair = lower + base2.lower()
            latin_pair = _GREEK_TRANSLIT_DIPHTHONGS[pair]
            rough = _GREEK_TRANSLIT_ROUGH in marks or _GREEK_TRANSLIT_ROUGH in marks2
            accent = (_greek_translit_accent(marks2, base2.lower() in _GREEK_TRANSLIT_LONG)
                      or _greek_translit_accent(marks, lower in _GREEK_TRANSLIT_LONG))
            iota_sub = _GREEK_TRANSLIT_IOTA_SUB in marks2 or _GREEK_TRANSLIT_IOTA_SUB in marks
            l2 = _greek_translit_compose(latin_pair[1], base2.lower() in _GREEK_TRANSLIT_LONG,
                                          accent, False, iota_sub)
            translit = latin_pair[0] + l2
            if rough:
                translit = "h" + translit
            if is_upper:
                translit = translit[0].upper() + translit[1:]
            out.append(translit)
            i += 2
            continue

        is_long = lower in _GREEK_TRANSLIT_LONG
        accent = _greek_translit_accent(marks, is_long)
        diaeresis = _GREEK_TRANSLIT_DIAERESIS in marks
        iota_sub = _GREEK_TRANSLIT_IOTA_SUB in marks
        translit = _greek_translit_compose(_GREEK_TRANSLIT_BASE[lower], is_long, accent, diaeresis, iota_sub)
        if lower in _GREEK_TRANSLIT_VOWELS and _GREEK_TRANSLIT_ROUGH in marks:
            translit = "h" + translit
        if is_upper:
            translit = translit[0].upper() + translit[1:]
        out.append(translit)
        i += 1

    return "".join(out)
