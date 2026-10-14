"""
Builds data/hymns/more_hymns.json and its audio (data/hymns/audio/more/): the
ancient Latin hymns of the Church in Gregorian chant.

    python scripts/build_chant.py          # needs numpy (hymn_audio.py) and ffmpeg

Chant: the GregoBase Corpus (github.com/bacor/gregobasecorpus, a packaged
export of gregobase.selapa.net, cached in scripts/.cache/gregobase): every
hymn, sequence, canticle and invitatory, and the best-loved antiphons (the
four Marian antiphons, Ubi caritas...). Each chant's gabc score gives both
its Latin words (the syllables between the neumes) and its melody, which is
played on hymn_audio's organ, the whole piece. Versions of one chant (Solesmes,
Vatican, Dominican...; "simple tone") are one entry: the Liber Usualis's
first, then the version with the most stanzas.

(The Sacred Harp's songs, Babylon Is Fallen among them, are build_sacred_harp.py's.)
"""
import collections
import csv
import io
import json
import re
import shutil
import statistics
import subprocess
import sys
import unicodedata
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
CACHE = Path(__file__).resolve().parent / ".cache" / "gregobase"
CORPUS_URL = "https://github.com/bacor/gregobasecorpus/releases/download/v0.4/gregobasecorpus-v0.4.zip"
OUT = ROOT / "data" / "hymns" / "more_hymns.json"
AUDIO = ROOT / "data" / "hymns" / "audio" / "more"
UA = {"User-Agent": "ScriptureBotCorpusBuilder/1.0 (Discord bot; low-volume one-off import)"}
BITRATE = "16k"                      # one voice: smaller than the four-part hymns' 24k

PARTS = {"hy": "Hymn", "se": "Sequence", "ca": "Canticle", "im": "Invitatory", "an": "Antiphon", "va": "Chant",
         "ky": "Mass Ordinary", "in": "Introit", "gr": "Gradual", "tr": "Tract", "of": "Offertory",
         "co": "Communion", "re": "Responsory", "or": "Prayer"}
# chants taken by GregoBase id, with their titles: the Requiem Mass and the burial (the Liber Usualis
# versions), and the Magnificat (filed with the psalm tones)
NAMED = {"766": "Requiem aeternam (Introit of the Requiem Mass)",
           "1261": "Requiem aeternam (Gradual of the Requiem Mass)",
           "338": "Absolve, Domine (Tract of the Requiem Mass)",
           "1199": "Domine Jesu Christe (Offertory of the Requiem Mass)",
           "241": "Lux aeterna (Communion of the Requiem Mass)",
           "376": "Libera me (Responsory of the Requiem)",
           "1152": "Subvenite (Responsory of the Requiem)",
         "8149": "Magnificat"}
# the antiphons and other pieces people know by name (GregoBase files them with thousands of others)
# a version chosen by hand: the Pater noster sung at Mass (Graduale Romanum), not the monastic one
PREFERRED = {"pater noster": "3326"}
FAVOURITES = ["salve regina", "alma redemptoris", "ave regina caelorum", "regina caeli", "ubi caritas", "sub tuum",
              "ave verum", "parce domine", "attende domine", "rorate caeli", "asperges me", "vidi aquam",
              "christus vincit", "inviolata", "o sanctissima", "media vita", "in paradisum", "nunc dimittis",
              "ecce sacerdos", "o sacrum convivium", "regina caeli laetare", "pater noster"]


# ── the corpus ──────────────────────────────────────────────────────────────

def corpus() -> zipfile.ZipFile:
    CACHE.mkdir(parents=True, exist_ok=True)
    path = CACHE / "corpus.zip"
    if not path.exists():
        path.write_bytes(urllib.request.urlopen(urllib.request.Request(CORPUS_URL, headers=UA), timeout=300).read())
    return zipfile.ZipFile(path)


def norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s.lower().replace("æ", "ae").replace("œ", "oe"))
    s = "".join(c for c in s if not unicodedata.combining(c)).replace("coel", "cael").replace("j", "i")
    return re.sub(r"\s+", " ", re.sub(r"[^a-z. ]", " ", s)).strip()


def base_incipit(incipit: str) -> str:
    """'Te lucis ante terminum (In Tempore Paschali)' -> 'te lucis ante terminum'; 'O salutaris Hostia II' -> ..."""
    s = re.sub(r"\([^)]*\)", "", incipit)
    s = re.sub(r"\b[IVX]+\.?\s*$", "", s.strip())
    return norm(s).strip(" .")


def chosen(z) -> list:
    rows = list(csv.DictReader(io.TextIOWrapper(z.open("csv/chants.csv"), "utf-8")))
    sources = {r["id"]: r.get("title", "") for r in csv.DictReader(io.TextIOWrapper(z.open("csv/sources.csv"), "utf-8"))}
    books = collections.defaultdict(list)
    for r in csv.DictReader(io.TextIOWrapper(z.open("csv/chant_sources.csv"), "utf-8")):
        books[r["chant_id"]].append(sources.get(r["source"], ""))
    # the Mass Ordinary ("ky": every Kyrie, Gloria, Credo, Sanctus, Agnus Dei, Ite missa est) is in whole
    picked = [r for r in rows if r["office_part"] in ("hy", "se", "ca", "im", "va", "ky") or r["id"] in NAMED
              or (r["office_part"] in ("an", "or") and any(norm(r["incipit"]).startswith(f) for f in FAVOURITES))]   # ("or": the Pater noster is a prayer of the Mass)
    groups = collections.defaultdict(list)
    for r in picked:
        if r["gabc"].strip():
            if r["id"] in NAMED:
                key = "named " + r["id"]
            elif r["office_part"] == "ky":     # each setting is its own (Credo I, Credo III...), the numeral kept
                key = norm(re.sub(r"\(forma ordinaria\)", "", r["incipit"])).strip(" .")
            else:
                key = base_incipit(r["incipit"])
            groups[key].append(r)

    def rank(r):
        # the plain version ("Te lucis ante terminum", not "... (Sacred Heart)"), from the Liber
        # Usualis, with all its stanzas
        liber = any("Liber Usualis" in b for b in books[r["id"]])
        variant = "(" in r["incipit"] or "another" in r["incipit"].lower()
        return (variant, not liber, -stanza_count(r), -len(r["gabc"]), int(r["id"]))

    out = []
    for key, versions in groups.items():
        if not key:
            continue
        best = next((r for r in versions if r["id"] == PREFERRED.get(key)), None) or sorted(versions, key=rank)[0]
        best["_books"] = books[best["id"]]
        best["_versions"] = len(versions)
        out.append(best)
    return out


# ── gabc: words and melody ──────────────────────────────────────────────────

def gabc_body(gabc: str) -> str:
    text = gabc.strip()
    if text.startswith('"'):                           # the corpus stores each score as a JSON string
        text = json.loads(text)
    if text.lstrip().startswith('[["'):                # a score in parts: [["gabc", "..."], ["tex", "..."], ...]
        text = "\n".join(json.loads(s) for s in re.findall(r'\["gabc",\s*("(?:[^"\\]|\\.)*")', text))
        text = re.sub(r"(?m)^\s*[A-Za-z][\w-]*:[^(\n]*;\s*$", "", text)   # each part's own header lines
    if "%%" in text:
        text = text.split("%%", 1)[1]
    return text


def full_score(row: dict) -> str:
    """The score with its later stanzas, which the corpus keeps apart (gabc_verses)."""
    verses = row.get("gabc_verses", "").strip()
    if verses.startswith('"'):
        verses = json.loads(verses)
    return gabc_body(row["gabc"]) + ("\n" + verses if verses else "")


def stanza_count(row: dict) -> int:
    return len(re.findall(r"(?<!\d)\d+\.\s*(?:</v>)?\s*\(", full_score(row)))


def clean_syllable(s: str) -> str:
    s = re.sub(r"<v>\s*(\d+\.)\s*</v>", r"\1", s)        # a stanza number set as "<v>2.</v>"
    for a, b in (("'ae", "ǽ"), ("'æ", "ǽ"), ("'oe", "œ́"), ("'œ", "œ́"), ("ae", "æ"), ("oe", "œ")):
        s = s.replace(f"<sp>{a}</sp>", b)
    s = s.replace("<sp>V/</sp>", "℣").replace("<sp>R/</sp>", "℟").replace("<sp>+</sp>", "†").replace("<sp>*</sp>", "*")
    s = re.sub(r"<v>.*?</v>|<alt>.*?</alt>", "", s)
    s = re.sub(r"</?[a-z]+>", "", s)
    return s.replace("{", "").replace("}", "")


_LINES = "dfhjl"                     # gabc letters on the staff's five lines, bottom to top
_SEMIS = [0, 2, 4, 5, 7, 9, 11]


def parse(score: str, strophic: bool) -> "tuple[list, list]":
    """(stanzas as text, notes [(start, end, pitch, 0)] for the part to play) from a score
    (full_score: the chant and its later stanzas)."""
    body = score
    tokens = re.findall(r"([^()]*)\(([^)]*)\)", body)                 # syllable(neumes) pairs
    stanzas, words, line = [], [], ""
    notes, t = [], 0.0
    clef_letter, clef_note, bflat = "j", 0, False       # c4: do (C) on the fourth line
    flats = set()

    def close_line():
        nonlocal line
        if line.strip():
            words.append(line.strip())
        line = ""

    def close_stanza():
        close_line()
        if words:
            stanzas.append("\n".join(words))
            words.clear()

    for syl, neumes in tokens:
        syl = clean_syllable(syl)
        m = re.fullmatch(r"\s*(\d+)\.\s*", syl)
        if m:                                           # "2." starts the next stanza
            close_stanza()
            syl = ""
        line += syl
        neumes = re.sub(r"\[[^\]]*\]", "", neumes)
        clef = re.fullmatch(r"\s*([cf])(b?)([1-4])\s*", neumes)
        if clef:
            clef_letter = _LINES[int(clef.group(3)) - 1]
            clef_note = 0 if clef.group(1) == "c" else 3   # do = C, fa = F
            bflat = bool(clef.group(2))
            continue
        i = 0
        chars = neumes
        while i < len(chars):
            c = chars[i]
            low = c.lower()
            nxt = chars[i + 1] if i + 1 < len(chars) else ""
            if c in ",;:":                                 # a bar: a breath, longer for the bigger ones
                double = c == ":" and nxt == ":"
                if c in ";:" or (c == "," and strophic):
                    close_line()                           # (a hymn's lines end at every bar; prose at the bigger ones)
                t += 1.0 if double else {",": 0.25, ";": 0.4, ":": 0.6}[c]
                if double and strophic:                    # a hymn's double bar ends a stanza (many scores don't number them)
                    close_stanza()
                flats.clear()
                i += 2 if double else 1
                continue
            if "a" <= low <= "m":
                if nxt in ("x", "y", "#"):                 # an accidental, not a note
                    (flats.add if nxt == "x" else flats.discard)(low)
                    i += 2
                    continue
                if nxt == "+":                             # a custos: the next line's first note, not sung
                    i += 2
                    continue
                steps = "abcdefghijklm".index(low) - "abcdefghijklm".index(clef_letter)
                n = clef_note + steps
                octave, degree = divmod(n, 7)
                pitch = 60 + 12 * octave + _SEMIS[degree]
                if low in flats or (bflat and degree == 6):  # a flat written before it, or a B-flat clef
                    pitch -= 1
                length = 0.42
                j = i + 1
                while j < len(chars) and chars[j] in "vVos~<>'_.wWrRq1234-!/@":
                    if chars[j] == ".":
                        length = 0.84
                    elif chars[j] == "_":
                        length = max(length, 0.6)
                    j += 1
                notes.append((t, t + length, pitch, 0))
                t += length
                i = j
                continue
            i += 1
    close_stanza()
    stanzas = [re.sub(r"\s*[*†]", "", s).replace("~", " ") for s in stanzas]   # cue marks out; "~" a fixed space       # the choir's cue marks, not words
    stanzas = [re.sub(r"(?m)^\s*or\s*:.*\n?", "", s) for s in stanzas]     # a psalm tone's alternative endings ("or : Dóminum.")
    stanzas = [re.sub(r"[ \t]+", " ", s.replace("\r", "")).replace(" ,", ",").replace(" .", ".").strip() for s in stanzas]
    if len(stanzas) > 1 and re.fullmatch(r"(?:In fine: )?Amen\.?", stanzas[-1]):
        stanzas[-2:] = [stanzas[-2] + "\n" + stanzas[-1]]       # a closing Amen belongs to the last verse
    # chant books set an opening's first two letters as capitals ("TE lucis", "SAlve"): "Te", "Salve"
    stanzas = [re.sub(r"\b([A-ZÆ])([A-ZÆÁÉÍÓÚ]+)(?=[a-zæœáéíóúýǽ])", lambda m: m.group(1) + m.group(2).lower(), s)
               for s in stanzas]
    stanzas = [re.sub(r"^([A-ZÆ])([A-ZÆÁÉÍÓÚ]+)\b", lambda m: m.group(1) + m.group(2).lower(), s) for s in stanzas]
    stanzas = [s for s in stanzas if s]
    if notes:                                          # chant has no fixed pitch: centre it for the organ
        med = statistics.median(p for _, _, p, _ in notes)
        shift = 12 * round((62 - med) / 12)
        notes = [(a, b, p + shift, ch) for a, b, p, ch in notes]   # the whole piece, never cut short
    return stanzas, notes


def render(notes: list, out: Path, title: str) -> float:
    import hymn_audio
    wav = hymn_audio.to_wav(hymn_audio.synthesize(notes))
    subprocess.run([shutil.which("ffmpeg"), "-loglevel", "error", "-y", "-f", "wav", "-i", "-", "-ac", "1",
                    "-c:a", "libopus", "-b:a", BITRATE, "-metadata", f"title={title}", str(out)], input=wav, check=True)
    return max(b for _, b, _, _ in notes)


# ── putting it together ─────────────────────────────────────────────────────

def main():
    if not shutil.which("ffmpeg"):
        sys.exit("ffmpeg isn't on the PATH")
    AUDIO.mkdir(parents=True, exist_ok=True)
    existing = {h["title"].lower() for h in json.loads((ROOT / "data" / "hymns" / "hymns.json").read_text(encoding="utf-8"))["hymns"]}
    z = corpus()
    hymns, skipped = [], []
    titles = collections.Counter()
    for r in sorted(chosen(z), key=lambda r: norm(r["incipit"])):
        part = r["office_part"]
        strophic = part == "hy"                         # a hymn: its lines and stanzas end at bars
        try:
            stanzas, notes = parse(full_score(r), strophic)
        except Exception as e:
            skipped.append((r["id"], r["incipit"], str(e)[:60]))
            continue
        if not stanzas or len(notes) < 8:
            skipped.append((r["id"], r["incipit"], "no words or melody"))
            continue
        title = re.sub(r"\s*\((?:simple tone|another chant|\d|[A-Z])\)\s*", " ", r["incipit"]).strip()
        title = re.sub(r"\.\.\.\s*", "… ", title)
        title = NAMED.get(r["id"], title)
        if title.lower() in existing or titles[title.lower()]:
            title = f"{title} (chant)" if title.lower() in existing else f"{title} ({r['version'] or r['id']})"
        titles[title.lower()] += 1
        name = f"chant-{int(r['id']):05d}.ogg"
        if (AUDIO / name).exists() and "--all" not in sys.argv:        # already rendered
            seconds = max(b for _, b, _, _ in notes)
        else:
            seconds = render(notes, AUDIO / name, title)
        book = next((b for b in r["_books"] if b), "")
        hymns.append({
            "title": title, "also": [], "author": "", "translator": "",
            "composer": "Gregorian chant" + (f", mode {r['mode']}" if r["mode"] else ""),
            "tune": "", "meter": "", "scripture": [], "topics": [PARTS.get(part, "Chant"), "Latin", "Gregorian chant"],
            "stanzas": stanzas, "refrain": "", "first_line": stanzas[0].split("\n")[0][:90],
            "source": "GregoBase" + (f", from {book}" if book else "") + (f" ({r['version']})" if r["version"] else ""),
            "audio": f"more/{name}", "audio_kind": "chant", "seconds": round(seconds), "language": "Latin",
            "gregobase": int(r["id"]),
        })
    OUT.write_text(json.dumps({"hymns": hymns}, ensure_ascii=False, indent=1), encoding="utf-8")
    size = sum(f.stat().st_size for f in AUDIO.glob("*.ogg"))
    print(f"wrote {len(hymns)} hymns; audio {size / 1e6:.1f} MB; skipped {len(skipped)}: {skipped[:10]}")


if __name__ == "__main__":
    main()
