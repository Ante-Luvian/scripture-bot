"""
poem_lookup.py
--------------
Lookup module for the !poem command.

Handles two citation styles:

  1. book.line  — Homer, Virgil, Ovid
       !poem Il. 6.440          single couplet
       !poem Il. 6.440-460      line range
       !poem Il. 6              whole book (paginated)

  2. stephanus  — Plato
       !poem Republic 514a      single section
       !poem Republic 514a-515b section range

Add -p to any of the above for parallel display.
"""

from __future__ import annotations
import json, re
from pathlib import Path

_BASE         = Path(__file__).parent
_POETRY_DIR   = _BASE / "data" / "poetry"
_CLASSICAL_DIR = _BASE / "data" / "classical"

def _data_path(filename: str) -> Path:
    for d in (_POETRY_DIR, _CLASSICAL_DIR, _BASE / "data"):
        p = d / filename
        if p.exists():
            return p
    return _POETRY_DIR / filename

# ── Registry ───────────────────────────────────────────────────────────────────

_WORKS:  dict[str, dict] = {}
_ABBREVS: dict[str, str] = {}

def _reg(name, abbrevs, filename, author, lang, style, pair=None):
    _WORKS[name] = dict(name=name, filename=filename, author=author,
                        lang=lang, style=style, pair=pair, abbrevs=abbrevs)
    for a in abbrevs:
        _ABBREVS[a.lower()] = name

_reg("Iliad (Pope)",    ["Il","Il.","Iliad","Homer Iliad"],
     "iliad_pope.json",    "Homer",  "en",  "book.line", "Iliad (Greek)")
_reg("Odyssey (Pope)",  ["Od","Od.","Odyssey","Homer Odyssey"],
     "odyssey_pope.json",  "Homer",  "en",  "book.line", "Odyssey (Greek)")
_reg("Iliad (Greek)",   ["Il.gr","Iliad Greek"],
     "iliad_greek.json",   "Homer",  "grc", "book.line", "Iliad (Pope)")
_reg("Odyssey (Greek)", ["Od.gr","Odyssey Greek"],
     "odyssey_greek.json", "Homer",  "grc", "book.line", "Odyssey (Pope)")

_reg("Aeneid (Dryden)",   ["Aen","Aen.","Aeneid","Virgil","Vergil"],
     "aeneid_couplets.json", "Virgil", "en", "book.line", "Aeneid (Latin)")
_reg("Aeneid (Latin)",    ["Aen.lat","Aeneid Latin"],
     "aeneid_latin.json",   "Virgil", "lat", "book.line", "Aeneid (Dryden)")
_reg("Eclogues (Dryden)", ["Ecl","Ecl.","Eclogues","Pastorals","Eclogue"],
     "eclogues_dryden.json",  "Virgil", "en", "book.line", "Eclogues (Latin)")
_reg("Eclogues (Latin)",  ["Ecl.lat","Eclogues Latin"],
     "eclogues_latin.json",   "Virgil", "lat", "book.line", "Eclogues (Dryden)")
_reg("Georgics (Dryden)", ["G.","Geo","Georgics","Georgic"],
     "georgics_dryden.json",  "Virgil", "en", "book.line", "Georgics (Latin)")
_reg("Georgics (Latin)",  ["G.lat","Georgics Latin"],
     "georgics_latin.json",   "Virgil", "lat", "book.line", "Georgics (Dryden)")

_reg("Metamorphoses (Garth/Dryden)", ["Met","Met.","Metamorphoses","Ovid"],
     "metamorphoses_garth.json",   "Ovid", "en", "book.line", "Metamorphoses (Latin)")
_reg("Metamorphoses (Latin)",       ["Met.lat","Metamorphoses Latin"],
     "metamorphoses_latin.json",    "Ovid", "lat", "book.line", "Metamorphoses (Garth/Dryden)")
_reg("Metamorphoses (Golding)",     ["Met.g","Golding","Met.Golding"],
     "metamorphoses_golding.json", "Ovid", "en", "book.line")

# Heliand — Old Saxon Gospel epic (~830 AD)
_reg("Heliand (Scott)",    ["Heliand", "Hel", "Hel.", "heliand"],
     "heliand_english.json",  "Anonymous (Old Saxon)", "en", "book.line",
     pair="Heliand (Old Saxon)")
_reg("Heliand (Old Saxon)", ["Hel.os", "Heliand OS", "heliand-os"],
     "heliand_oldsaxon.json", "Anonymous (Old Saxon)", "osx", "book.line",
     pair="Heliand (Scott)")


_reg("Plato (English)", [
        "Plato","Republic","R.","Apology","Ap.","Crito","Cri.",
        "Phaedo","Phd.","Cratylus","Cra.","Theaetetus","Tht.",
        "Sophist","Soph.","Statesman","Plt.","Parmenides","Prm.",
        "Philebus","Phlb.","Symposium","Smp.","Phaedrus","Phdr.",
        "Alcibiades I","Alc.","Alcibiades II","Alc2.",
        "Hipparchus","Hipparch.","Rival Lovers","Amat.",
        "Theages","Thg.","Charmides","Chrm.","Laches","La.",
        "Lysis","Ly.","Euthydemus","Euthd.","Protagoras","Prt.",
        "Gorgias","Grg.","Meno","Men.","Greater Hippias","HP Ma.",
        "Lesser Hippias","HP Mi.","Ion","Menexenus","Mx.",
        "Cleitophon","Clit.","Timaeus","Ti.","Critias","Criti.",
        "Minos","Min.","Laws","Lg.","Epinomis","Epin.",
        "Letters","Ep.","Euthyphro","Euthphr.",
    ],
    "plato.json", "Plato", "en", "stephanus", "Plato (Greek)")

_reg("Plato (Greek)", ["Plato.gr","Plato Greek"],
     "plato_greek.json", "Plato", "grc", "stephanus", "Plato (English)")

# Baal Cycle — Canaanite mythological epic, c.1400–1200 BCE
_reg("Baal Cycle (GWT)",    ["Baal", "Baal Cycle", "KTU"],
     "baal_cycle_en.json",    "Anonymous (Ugaritic)", "en",  "book.line",
     pair="Baal Cycle (Ugaritic)")
_reg("Baal Cycle (Ugaritic)", ["Baal.ug", "Baal Ugaritic", "KTU.ug"],
     "baal_cycle_ugaritic.json", "Anonymous (Ugaritic)", "uga", "book.line",
     pair="Baal Cycle (GWT)")

# Mu'allaqat — Seven Suspended Odes, pre-Islamic Arabia, c. 6th century CE
_reg("Mu'allaqat (GWT)",     ["Muallaqat", "Mu'allaqat", "Muallaqa", "Suspended Odes"],
     "muallaqat_en.json",      "Various (pre-Islamic Arabic)", "en",  "book.line",
     pair="Mu'allaqat (Arabic)")
_reg("Mu'allaqat (Arabic)",  ["Muallaqat.ar", "Mu'allaqat Arabic"],
     "muallaqat_ar.json",      "Various (pre-Islamic Arabic)", "ar",  "book.line",
     pair="Mu'allaqat (GWT)")

# ── Dialogue name normalisation ────────────────────────────────────────────────

_DIALOGUE_MAP: dict[str, str] = {
    k.lower(): v for k, v in {
        "Republic": "Republic", "R.": "Republic",
        "Apology": "Apology", "Ap.": "Apology",
        "Crito": "Crito", "Cri.": "Crito",
        "Phaedo": "Phaedo", "Phd.": "Phaedo",
        "Cratylus": "Cratylus", "Cra.": "Cratylus",
        "Theaetetus": "Theaetetus", "Tht.": "Theaetetus",
        "Sophist": "Sophist", "Soph.": "Sophist",
        "Statesman": "Statesman", "Plt.": "Statesman",
        "Parmenides": "Parmenides", "Prm.": "Parmenides",
        "Philebus": "Philebus", "Phlb.": "Philebus",
        "Symposium": "Symposium", "Smp.": "Symposium",
        "Phaedrus": "Phaedrus", "Phdr.": "Phaedrus",
        "Alcibiades I": "Alcibiades I", "Alc.": "Alcibiades I",
        "Alcibiades II": "Alcibiades II", "Alc2.": "Alcibiades II",
        "Hipparchus": "Hipparchus", "Hipparch.": "Hipparchus",
        "Rival Lovers": "Rival Lovers", "Amat.": "Rival Lovers",
        "Theages": "Theages", "Thg.": "Theages",
        "Charmides": "Charmides", "Chrm.": "Charmides",
        "Laches": "Laches", "La.": "Laches",
        "Lysis": "Lysis", "Ly.": "Lysis",
        "Euthydemus": "Euthydemus", "Euthd.": "Euthydemus",
        "Protagoras": "Protagoras", "Prt.": "Protagoras",
        "Gorgias": "Gorgias", "Grg.": "Gorgias",
        "Meno": "Meno", "Men.": "Meno",
        "Greater Hippias": "Greater Hippias", "HP Ma.": "Greater Hippias",
        "Lesser Hippias": "Lesser Hippias", "HP Mi.": "Lesser Hippias",
        "Ion": "Ion",
        "Menexenus": "Menexenus", "Mx.": "Menexenus",
        "Cleitophon": "Cleitophon", "Clit.": "Cleitophon",
        "Timaeus": "Timaeus", "Ti.": "Timaeus",
        "Critias": "Critias", "Criti.": "Critias",
        "Minos": "Minos", "Min.": "Minos",
        "Laws": "Laws", "Lg.": "Laws",
        "Epinomis": "Epinomis", "Epin.": "Epinomis",
        "Letters": "Letters", "Ep.": "Letters",
        "Euthyphro": "Euthyphro", "Euthphr.": "Euthyphro",
    }.items()
}

def _resolve_dialogue(raw: str) -> str | None:
    return _DIALOGUE_MAP.get(raw.strip().lower())

# ── Cache ──────────────────────────────────────────────────────────────────────

_CACHE: dict[str, dict] = {}

def _load(name: str) -> dict | None:
    if name in _CACHE:
        return _CACHE[name]
    meta = _WORKS.get(name)
    if not meta:
        return None
    path = _data_path(meta["filename"])
    if not path.exists():
        return None
    _CACHE[name] = json.loads(path.read_text(encoding="utf-8"))
    return _CACHE[name]

# ── book.line internals ────────────────────────────────────────────────────────

def _parse_key(key: str) -> tuple[int, int]:
    if "-" in key:
        a, b = key.split("-", 1)
        return int(a), int(b)
    n = int(key)
    return n, n

def _get_book(raw: dict, book: int) -> dict | None:
    books = raw.get("books", {})
    b = books.get(str(book))
    if b is not None:
        return b
    # aeneid-style nesting: books -> "Aeneid" -> "1" -> entries
    for v in books.values():
        if isinstance(v, dict):
            inner = v.get(str(book))
            if inner is not None:
                return inner
    return None

def _find_entries(book_data: dict, line_s: int, line_e: int):
    results = []
    for key, text in book_data.items():
        a, b = _parse_key(key)
        if a <= line_e and b >= line_s:
            results.append((a, key, text))
    results.sort(key=lambda x: x[0])
    return results

# ── Stephanus internals ────────────────────────────────────────────────────────

def _steph_hits(sections: dict, ref_s: str, ref_e: str | None) -> list[tuple[str, str]]:
    keys = list(sections.keys())
    try:
        i_s = keys.index(ref_s)
    except ValueError:
        return []
    i_e = keys.index(ref_e) if ref_e and ref_e in keys else i_s
    return [(k, sections[k]) for k in keys[i_s:i_e + 1]]

def _steph_text(val) -> str:
    """plato.json stores {"1": text}; plato_greek.json stores text directly."""
    if isinstance(val, dict):
        return list(val.values())[0] if val else ""
    return val or ""

# ── Parsing ────────────────────────────────────────────────────────────────────

_STEPH_PAT = r'(\d{1,4}[a-e])'

def parse_poem_ref(s: str) -> dict | None:
    """
    Parse a user reference string into a spec dict.
    Returns None if unparseable.
    """
    s = s.strip()

    # Stephanus: "Republic 514a"  "Republic 514a-515b"  "R. 514a"
    m = re.match(
        r'^(.+?)\s+' + _STEPH_PAT + r'(?:\s*[-–]\s*' + _STEPH_PAT + r')?$',
        s, re.I
    )
    if m:
        dialogue = _resolve_dialogue(m.group(1))
        if dialogue:
            return dict(style="stephanus", work="Plato (English)",
                        dialogue=dialogue,
                        ref_s=m.group(2), ref_e=m.group(3))

    # book.line: "Il. 6.440"  "Il. 6.440-460"  "Il. 6"  "Iliad 6 440"
    m = re.match(
        r'^([A-Za-z][A-Za-z0-9\.\s]*?)\s+'
        r'(\d+)'
        r'(?:[.\s](\d+)(?:\s*[-–]\s*(\d+))?)?$',
        s, re.I
    )
    if m:
        raw_work = m.group(1).strip().rstrip(".")
        work = (_ABBREVS.get(raw_work.lower())
                or _ABBREVS.get(raw_work.lower() + "."))
        if work:
            line_s = int(m.group(3)) if m.group(3) else None
            line_e = int(m.group(4)) if m.group(4) else line_s
            return dict(style="book.line", work=work,
                        book=int(m.group(2)), line_s=line_s, line_e=line_e)

    return None

# ── Lookup ─────────────────────────────────────────────────────────────────────

def lookup(spec: dict) -> dict:
    if spec["style"] == "stephanus":
        return _lookup_steph(spec, spec["work"])
    return _lookup_bl(spec)

def lookup_pair(primary_result: dict) -> dict:
    spec = primary_result.get("pair_spec")
    if not spec:
        return {"found": False, "error": "No parallel text available for this work."}
    if spec["style"] == "stephanus":
        return _lookup_steph(spec, spec["work"])
    return _lookup_bl(spec)

def _lookup_bl(spec: dict) -> dict:
    name   = spec["work"]
    book   = spec["book"]
    line_s = spec.get("line_s")
    line_e = spec.get("line_e")
    meta   = _WORKS[name]
    raw    = _load(name)

    if raw is None:
        return {"found": False, "error": f"**{name}** data file not found."}

    book_data = _get_book(raw, book)
    if book_data is None:
        return {"found": False, "error": f"**{name}** has no Book {book}."}

    abbrev = meta["abbrevs"][0].rstrip(".")

    # Use book title from data if available (raw already loaded above)
    book_title = raw.get("book_titles", {}).get(str(book), "") if raw else ""
    book_label = book_title if book_title else f"Book {book}"

    # Whole book
    if line_s is None:
        items = sorted(book_data.items(), key=lambda x: _parse_key(x[0])[0])
        PAGE = 20
        pages, chunk = [], []
        for _, v in items:
            chunk.append(v)
            if len(chunk) >= PAGE:
                pages.append("\n".join(chunk))
                chunk = []
        if chunk:
            pages.append("\n".join(chunk))
        pair_spec = (dict(style="book.line", work=meta["pair"],
                          book=book, line_s=None, line_e=None)
                     if meta.get("pair") else None)
        return dict(found=True,
                    reference=f"{abbrev}. {book_label}",
                    text="\n".join(v for _, v in items),
                    source=raw.get("source", name),
                    lang=meta["lang"],
                    pages=pages if len(pages) > 1 else None,
                    pair_spec=pair_spec)

    # Line range
    hits = _find_entries(book_data, line_s, line_e)
    if not hits:
        return {"found": False,
                "error": f"Lines {line_s}–{line_e} not found in **{name}** Book {book}."}

    actual_s = hits[0][0]
    actual_e = _parse_key(hits[-1][1])[1]
    ref = (f"{abbrev}. {book}.{actual_s}"
           if actual_s == actual_e
           else f"{abbrev}. {book}.{actual_s}–{actual_e}")
    text = "\n".join(t for _, _, t in hits)

    pair_spec = (dict(style="book.line", work=meta["pair"],
                      book=book, line_s=actual_s, line_e=actual_e)
                 if meta.get("pair") else None)

    return dict(found=True, reference=ref, text=text,
                source=raw.get("source", name), lang=meta["lang"],
                pages=None, pair_spec=pair_spec)

def _lookup_steph(spec: dict, work_name: str) -> dict:
    dialogue = spec["dialogue"]
    ref_s    = spec["ref_s"]
    ref_e    = spec.get("ref_e")
    meta     = _WORKS[work_name]
    raw      = _load(work_name)

    if raw is None:
        f = meta["filename"]
        script = "build_plato_greek.py" if "Greek" in work_name else ""
        msg = f"**{work_name}** not found ({f})"
        if script:
            msg += f". Run `{script}`."
        return {"found": False, "error": msg}

    books = raw.get("books", {})
    if dialogue not in books:
        return {"found": False, "error": f"**{dialogue}** not found."}

    hits = _steph_hits(books[dialogue], ref_s, ref_e)
    if not hits:
        return {"found": False,
                "error": f"**{dialogue}** {ref_s} not found."}

    text = "\n\n".join(_steph_text(v) for _, v in hits if _steph_text(v))
    ref  = f"{dialogue} {ref_s}" + (f"–{ref_e}" if ref_e and ref_e != ref_s else "")

    pair_spec = (dict(style="stephanus", work=meta["pair"],
                      dialogue=dialogue, ref_s=ref_s, ref_e=ref_e)
                 if meta.get("pair") else None)

    return dict(found=True, reference=ref, text=text,
                source=raw.get("source", work_name), lang=meta["lang"],
                pages=None, pair_spec=pair_spec)

# ── list_works ─────────────────────────────────────────────────────────────────

def list_works() -> str:
    lines = [
        "**📜 Classical Poetry & Prose**",
        "Each result shows English translation with original language.",
        "",
        "**Homer** (Pope tr. / Greek)",
        "  `Il.`  Iliad          `Od.`  Odyssey",
        "",
        "**Virgil** (Dryden tr. / Latin)",
        "  `Aen.`  Aeneid        `Ecl.`  Eclogues        `G.`  Georgics",
        "",
        "**Ovid** (Garth/Dryden tr. / Latin)",
        "  `Met.`  Metamorphoses",
        "  `Met.g`  Metamorphoses (Golding tr.)",
        "",
        "**Anonymous Old Saxon**",
        "  `Heliand`  Heliand (~830 AD)",
        "",
        "**Plato** (Loeb translations / Greek)",
        "  `Republic`  `Apology`  `Phaedo`  `Symposium`  `Phaedrus`",
        "  `Meno`  `Crito`  `Timaeus`  `Laws`  — and all other dialogues",
        "",
        "**About 470 more Greek and Latin works** from the Perseus library",
        "  Sophocles, Thucydides, Plutarch, Aristophanes, Cicero, Livy… by their usual citation:",
        "  `!parallel Antigone 1:450`  `!parallel History of the Peloponnesian War 2.40:1`",
        "",
        "**Usage**",
        "  `!poem Il. 6.440`  `!poem Il. 6.440-460`  `!poem Il. 6`",
        "  `!poem Aen. 1.1-20`  `!poem Met. 3.1-50`",
        "  `!poem Republic 514a`  `!poem Republic 514a-515b`",
        "  `!poem Euthyphro 2a-3b`",
    ]
    return "\n".join(lines)


# ── Scripture detection ────────────────────────────────────────────────────────
# Used by bot.py to decide which ancient language pair to fetch

_APOCRYPHA_ABBREVS = {
    "tob","tobit","jdt","judith","wis","wisdom","sir","sirach",
    "ecclesiasticus","bar","baruch","1macc","2macc","3macc","4macc",
    "1esd","2esd","1esdras","2esdras","pman","addesth","sg3","sus",
    "bel","epjer","prayer of manasseh","additions to esther",
    "epistle of jeremiah","song of the three children","susanna",
    "bel and the dragon","psalms of solomon",
}

_OT_ABBREVS = {
    "gen","exod","ex","lev","num","deut","josh","judg","ru","ruth",
    "1sam","2sam","1kgs","2kgs","1chr","2chr","ezra","neh","esth",
    "job","ps","psa","prov","eccl","song","isa","jer","lam","ezek",
    "dan","hos","joel","amos","obad","jon","mic","nah","hab","zeph",
    "hag","zech","mal","ge","gn","nm","dt","jos","jdg","rth",
    "1ki","2ki","1ch","2ch","qoh","eze",
}

_NT_ABBREVS = {
    "matt","mt","mark","mrk","luke","lk","john","jn","acts","rom",
    "1cor","2cor","gal","eph","phil","col","1thess","2thess",
    "1tim","2tim","titus","tit","phlm","philem","heb","jas","jam",
    "1pet","2pet","1john","2john","3john","jude","rev","apoc",
}


def classify_scripture(reference: str) -> str | None:
    """
    Given a scripture reference, return:
      'ot'        — Old Testament proper (pair: WLC Hebrew)
      'apocrypha' — Deuterocanon / Apocrypha (pair: LXX Greek)
      'nt'        — New Testament (pair: TR Greek)
      None        — not a scripture reference
    """
    import re as _re
    m = _re.match(r'^((?:\d\s*)?[A-Za-z][A-Za-z\s\'&-]{0,30}?)\s+\d', reference.strip())
    if not m:
        return None
    book = m.group(1).strip().lower().replace(' ', '')
    # Normalise: "1 samuel" -> "1samuel", etc.
    book_spaced = m.group(1).strip().lower()

    if book in _APOCRYPHA_ABBREVS or book_spaced in _APOCRYPHA_ABBREVS:
        return 'apocrypha'
    if book in _OT_ABBREVS:
        return 'ot'
    if book in _NT_ABBREVS:
        return 'nt'
    # Full name fallback
    from scripture_lookup import BIBLE_OT, BIBLE_NT, BIBLE_APOCRYPHA
    for b in BIBLE_APOCRYPHA:
        if book_spaced == b.lower() or book_spaced in b.lower():
            return 'apocrypha'
    for b in BIBLE_OT:
        if book_spaced == b.lower():
            return 'ot'
    for b in BIBLE_NT:
        if book_spaced == b.lower():
            return 'nt'
    return None


def is_drb_reference(reference: str) -> bool:
    """Check if reference ends with a DRB suffix."""
    import re as _re
    return bool(_re.search(
        r'\b(drb|drv|dra|dr|douay|douay-rheims|douay rheims)\s*$',
        reference.strip(), _re.I
    ))
