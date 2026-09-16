"""
sefaria_lookup.py
─────────────────
Live lookups against the Sefaria API for rabbinic texts not in our local
JSON data — Mishnah, Babylonian Talmud, Jerusalem Talmud, Zohar, Targumim,
Midrash Rabbah, Tosefta, and other Kabbalistic texts.

No API key required. Rate limit: be polite (we add a small delay).

Citation formats:
  Mishnah Berakhot 1:1           → Mishnah_Berakhot.1.1
  Talmud Berakhot 2a:3           → Berakhot.2a  (section 3)
  Jerusalem Talmud Berakhot 1:1  → Jerusalem_Talmud_Berakhot.1.1
  Zohar Bereshit 5               → Zohar, Bereshit.5
  Targum Onkelos Genesis 1:1     → Targum_Onkelos,_Genesis.1.1
  Bereshit Rabbah 1:1            → Bereshit_Rabbah.1.1
  Tosefta Berakhot 1:1           → Tosefta_Berakhot.1.1
  Sefer Yetzirah 1:1             → Sefer_Yetzirah.1.1

API endpoint:
  GET https://www.sefaria.org/api/v3/texts/{tref}?version=english
"""

import json
import re
import time
import urllib.request
import urllib.parse
from difflib import get_close_matches

SEFARIA_BASE = "https://www.sefaria.org/api/v3/texts/"
FETCH_DELAY  = 0.3   # seconds between requests


# ── Mishnah tractate name map ──────────────────────────────────────────────────
# Maps every reasonable user-facing name/abbreviation → Sefaria index title.
# Sefaria titles are "Mishnah_Tractate" with underscores.

MISHNAH_TRACTATES: dict[str, str] = {
    # ── Seder Zeraim (Agricultural laws) ──────────────────────────────────────
    "berakhot":         "Mishnah_Berakhot",
    "berachot":         "Mishnah_Berakhot",
    "blessings":        "Mishnah_Berakhot",
    "peah":             "Mishnah_Peah",
    "pe'ah":            "Mishnah_Peah",
    "demai":            "Mishnah_Demai",
    "kilayim":          "Mishnah_Kilayim",
    "sheviit":          "Mishnah_Sheviit",
    "shevi'it":         "Mishnah_Sheviit",
    "terumot":          "Mishnah_Terumot",
    "terumoth":         "Mishnah_Terumot",
    "maasrot":          "Mishnah_Maasrot",
    "maasrot":          "Mishnah_Maasrot",
    "maaser sheni":     "Mishnah_Maaser_Sheni",
    "maaser rishon":    "Mishnah_Maasrot",
    "challah":          "Mishnah_Challah",
    "hallah":           "Mishnah_Challah",
    "orlah":            "Mishnah_Orlah",
    "bikkurim":         "Mishnah_Bikkurim",
    "first fruits":     "Mishnah_Bikkurim",
    # ── Seder Moed (Festivals) ─────────────────────────────────────────────────
    "shabbat":          "Mishnah_Shabbat",
    "sabbath":          "Mishnah_Shabbat",
    "eruvin":           "Mishnah_Eruvin",
    "eruvim":           "Mishnah_Eruvin",
    "pesachim":         "Mishnah_Pesachim",
    "passover":         "Mishnah_Pesachim",
    "shekalim":         "Mishnah_Shekalim",
    "yoma":             "Mishnah_Yoma",
    "yom kippur":       "Mishnah_Yoma",
    "sukkah":           "Mishnah_Sukkah",
    "sukkot":           "Mishnah_Sukkah",
    "beitzah":          "Mishnah_Beitzah",
    "betzah":           "Mishnah_Beitzah",
    "rosh hashanah":    "Mishnah_Rosh_Hashanah",
    "rosh hashana":     "Mishnah_Rosh_Hashanah",
    "taanit":           "Mishnah_Taanit",
    "taanith":          "Mishnah_Taanit",
    "fast":             "Mishnah_Taanit",
    "megillah":         "Mishnah_Megillah",
    "moed katan":       "Mishnah_Moed_Katan",
    "chagigah":         "Mishnah_Chagigah",
    "hagigah":          "Mishnah_Chagigah",
    # ── Seder Nashim (Women) ───────────────────────────────────────────────────
    "yevamot":          "Mishnah_Yevamot",
    "yebamot":          "Mishnah_Yevamot",
    "ketubot":          "Mishnah_Ketubot",
    "ketubbot":         "Mishnah_Ketubot",
    "nedarim":          "Mishnah_Nedarim",
    "nazir":            "Mishnah_Nazir",
    "nazirite":         "Mishnah_Nazir",
    "sotah":            "Mishnah_Sotah",
    "gittin":           "Mishnah_Gittin",
    "get":              "Mishnah_Gittin",
    "kiddushin":        "Mishnah_Kiddushin",
    "betrothal":        "Mishnah_Kiddushin",
    # ── Seder Nezikin (Damages) ────────────────────────────────────────────────
    "bava kamma":       "Mishnah_Bava_Kamma",
    "baba kamma":       "Mishnah_Bava_Kamma",
    "bk":               "Mishnah_Bava_Kamma",
    "bava metzia":      "Mishnah_Bava_Metzia",
    "baba metzia":      "Mishnah_Bava_Metzia",
    "bm":               "Mishnah_Bava_Metzia",
    "bava batra":       "Mishnah_Bava_Batra",
    "baba batra":       "Mishnah_Bava_Batra",
    "bb":               "Mishnah_Bava_Batra",
    "sanhedrin":        "Mishnah_Sanhedrin",
    "makkot":           "Mishnah_Makkot",
    "makkoth":          "Mishnah_Makkot",
    "shevuot":          "Mishnah_Shevuot",
    "shevu'ot":         "Mishnah_Shevuot",
    "eduyot":           "Mishnah_Eduyot",
    "eduyyot":          "Mishnah_Eduyot",
    "avodah zarah":     "Mishnah_Avodah_Zarah",
    "avoda zarah":      "Mishnah_Avodah_Zarah",
    "az":               "Mishnah_Avodah_Zarah",
    "avot":             "Mishnah_Avot",
    "pirkei avot":      "Mishnah_Avot",
    "pirke avot":       "Mishnah_Avot",
    "ethics of the fathers": "Mishnah_Avot",
    "fathers":          "Mishnah_Avot",
    "horayot":          "Mishnah_Horayot",
    # ── Seder Kodashim (Temple service) ───────────────────────────────────────
    "zevachim":         "Mishnah_Zevachim",
    "zebachim":         "Mishnah_Zevachim",
    "menachot":         "Mishnah_Menachot",
    "menahot":          "Mishnah_Menachot",
    "chullin":          "Mishnah_Chullin",
    "hullin":           "Mishnah_Chullin",
    "bechorot":         "Mishnah_Bechorot",
    "bekhorot":         "Mishnah_Bechorot",
    "arachin":          "Mishnah_Arachin",
    "arakin":           "Mishnah_Arachin",
    "temurah":          "Mishnah_Temurah",
    "keritot":          "Mishnah_Keritot",
    "karetot":          "Mishnah_Keritot",
    "meilah":           "Mishnah_Meilah",
    "tamid":            "Mishnah_Tamid",
    "middot":           "Mishnah_Middot",
    "kinnim":           "Mishnah_Kinnim",
    # ── Seder Taharot (Purity) ─────────────────────────────────────────────────
    "keilim":           "Mishnah_Keilim",
    "kelim":            "Mishnah_Keilim",
    "ohalot":           "Mishnah_Ohalot",
    "oholot":           "Mishnah_Ohalot",
    "negaim":           "Mishnah_Negaim",
    "parah":            "Mishnah_Parah",
    "taharot":          "Mishnah_Tahorot",
    "tohorot":          "Mishnah_Tahorot",
    "mikvaot":          "Mishnah_Mikvaot",
    "mikvot":           "Mishnah_Mikvaot",
    "niddah":           "Mishnah_Niddah",
    "machshirin":       "Mishnah_Machshirin",
    "makhshirin":       "Mishnah_Machshirin",
    "zavim":            "Mishnah_Zavim",
    "tevul yom":        "Mishnah_Tevul_Yom",
    "yadayim":          "Mishnah_Yadayim",
    "hands":            "Mishnah_Yadayim",
    "uktzin":           "Mishnah_Oktzin",
    "oktzin":           "Mishnah_Oktzin",
    "uktsin":           "Mishnah_Oktzin",
}

# All canonical Sefaria Mishnah index names (for display/suggestions)
ALL_MISHNAH_TITLES = sorted(set(MISHNAH_TRACTATES.values()))


# ── Reference parsing ──────────────────────────────────────────────────────────

def parse_mishnah_ref(reference: str):
    """
    Parse a user reference into (tractate_key, chapter, mishna) or None.

    Accepts:
      "Mishnah Berakhot 1:1"
      "Berakhot 1:1"
      "m. Berakhot 1:1"       (common scholarly abbreviation)
      "Pirkei Avot 2:1"
      "Avot 3:14"
    """
    ref = reference.strip()

    # Strip leading "Mishnah", "m.", "M." prefixes
    ref = re.sub(r"^(?:Mishnah|m\.?)\s+", "", ref, flags=re.IGNORECASE).strip()

    # Now match "Tractate Chapter:Mishna" or "Tractate Chapter Mishna"
    m = re.match(
        r"^(.*?)\s+(\d+)[:\.](\d+)$",
        ref, re.UNICODE
    )
    if not m:
        return None

    tractate_raw = m.group(1).strip().lower()
    chapter      = int(m.group(2))
    mishna       = int(m.group(3))

    return tractate_raw, chapter, mishna


def resolve_tractate(tractate_raw: str):
    """
    Return Sefaria index title for a tractate name, or None.
    Tries direct lookup, then fuzzy match.
    """
    key = tractate_raw.lower().strip()
    if key in MISHNAH_TRACTATES:
        return MISHNAH_TRACTATES[key]

    # Fuzzy match against known keys
    matches = get_close_matches(key, MISHNAH_TRACTATES.keys(), n=1, cutoff=0.7)
    if matches:
        return MISHNAH_TRACTATES[matches[0]]

    return None


# ── API fetch ──────────────────────────────────────────────────────────────────

def fetch_mishnah(tractate_index: str, chapter: int, mishna: int) -> dict:
    """
    Fetch a single Mishnah passage from the Sefaria API.
    Returns {"found": True/False, "reference": ..., "text": ..., "source": ...}
    """
    tref = f"{tractate_index}.{chapter}.{mishna}"
    url  = SEFARIA_BASE + urllib.parse.quote(tref) + "?version=english"

    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "ScriptureBot/1.0 (Discord bot; contact via GitHub)"}
        )
        with urllib.request.urlopen(req, timeout=10) as r:
            raw = json.loads(r.read().decode("utf-8"))
        time.sleep(FETCH_DELAY)
    except Exception as e:
        return {"found": False, "error": f"Sefaria API error: {e}", "suggestions": []}

    # Extract English text from versions array
    versions = raw.get("versions", [])
    text = ""
    version_title = "Sefaria"
    for v in versions:
        if v.get("language") == "en" and v.get("text"):
            text = v["text"]
            version_title = v.get("versionTitle", "Sefaria")
            break

    # Strip HTML tags that Sefaria sometimes includes
    text = re.sub(r"<[^>]+>", "", text).strip()

    if not text:
        return {
            "found": False,
            "error": f"No English translation found for {tref}.",
            "suggestions": [],
        }

    # Sefaria returns the human-readable ref in raw["ref"]
    display_ref = raw.get("ref", tref.replace("_", " ").replace(".", " "))

    return {
        "found": True,
        "reference": display_ref,
        "text": text,
        "source": f"Mishnah — {version_title} (via Sefaria)",
    }


def fetch_mishnah_chapter(tractate_index: str, chapter: int) -> dict:
    """
    Fetch an entire Mishnah chapter from the Sefaria API.
    Returns {"found": True/False, "reference": ..., "text": ..., "source": ...}
    """
    tref = f"{tractate_index}.{chapter}"
    url  = SEFARIA_BASE + urllib.parse.quote(tref) + "?version=english"

    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "ScriptureBot/1.0"}
        )
        with urllib.request.urlopen(req, timeout=15) as r:
            raw = json.loads(r.read().decode("utf-8"))
        time.sleep(FETCH_DELAY)
    except Exception as e:
        return {"found": False, "error": f"Sefaria API error: {e}", "suggestions": []}

    versions = raw.get("versions", [])
    texts = []
    version_title = "Sefaria"
    for v in versions:
        if v.get("language") == "en" and v.get("text"):
            raw_texts = v["text"]
            version_title = v.get("versionTitle", "Sefaria")
            if isinstance(raw_texts, list):
                for i, t in enumerate(raw_texts, start=1):
                    clean = re.sub(r"<[^>]+>", "", str(t)).strip()
                    if clean:
                        texts.append(f"**[{i}]** {clean}")
            else:
                clean = re.sub(r"<[^>]+>", "", str(raw_texts)).strip()
                if clean:
                    texts.append(clean)
            break

    if not texts:
        return {
            "found": False,
            "error": f"No English translation found for {tref}.",
            "suggestions": [],
        }

    display_ref = raw.get("ref", tref.replace("_", " ").replace(".", " "))
    return {
        "found": True,
        "reference": display_ref,
        "text": "\n".join(texts),
        "source": f"Mishnah — {version_title} (via Sefaria)",
    }


# ── Main entry point ───────────────────────────────────────────────────────────

def get_mishnah(reference: str) -> dict:
    """
    Top-level function. Parse reference, resolve tractate, fetch from API.
    Handles both single mishna (1:1) and whole chapter (chapter only).
    """
    parsed = parse_mishnah_ref(reference)
    if parsed is None:
        return {
            "found": False,
            "error": f'Could not parse Mishnah reference: **{reference}**\n'
                     f'Try: `Mishnah Berakhot 1:1` or `Avot 2:1`',
            "suggestions": [],
        }

    tractate_raw, chapter, mishna = parsed
    index = resolve_tractate(tractate_raw)
    if index is None:
        candidates = get_close_matches(tractate_raw, MISHNAH_TRACTATES.keys(), n=3, cutoff=0.4)
        return {
            "found": False,
            "error": f'Unknown Mishnah tractate: **{tractate_raw}**',
            "suggestions": [MISHNAH_TRACTATES[c].replace("Mishnah_", "").replace("_", " ") for c in candidates],
        }

    return fetch_mishnah(index, chapter, mishna)


def get_mishnah_chapter(reference: str) -> dict:
    """Fetch a whole chapter. Reference format: 'Berakhot 1' or 'Mishnah Shabbat 2'."""
    ref = re.sub(r"^(?:Mishnah|m\.?)\s+", "", reference.strip(), flags=re.IGNORECASE).strip()
    m = re.match(r"^(.*?)\s+(\d+)$", ref, re.UNICODE)
    if not m:
        return {"found": False, "error": f"Could not parse: {reference}", "suggestions": []}

    tractate_raw = m.group(1).strip().lower()
    chapter      = int(m.group(2))
    index = resolve_tractate(tractate_raw)
    if index is None:
        return {"found": False, "error": f"Unknown tractate: {tractate_raw}", "suggestions": []}

    return fetch_mishnah_chapter(index, chapter)


# ══════════════════════════════════════════════════════════════════════════════
# BABYLONIAN TALMUD
# ══════════════════════════════════════════════════════════════════════════════
#
# Citation format:  Talmud Berakhot 2a:3   (tractate, daf, section)
#                   Gemara Shabbat 31a:1
#                   Talmud Berakhot 2a      (whole daf)
#
# Sefaria tref:  Berakhot.2a   (returns all sections of that daf as an array)
#
# The sections array is zero-indexed: section 1 = text[0], section 3 = text[2].
# We use the v3 API which returns {"versions": [{"language":"en","text":[...]}]}
# ══════════════════════════════════════════════════════════════════════════════

# All 37 tractates of Talmud Bavli with common name variants
TALMUD_TRACTATES: dict[str, str] = {
    # Seder Zeraim
    "berakhot": "Berakhot", "berachot": "Berakhot", "brachot": "Berakhot",
    # Seder Moed
    "shabbat": "Shabbat", "sabbath": "Shabbat", "shabbos": "Shabbat",
    "eruvin": "Eruvin", "eiruvin": "Eruvin",
    "pesachim": "Pesachim", "pesahim": "Pesachim",
    "shekalim": "Shekalim",
    "yoma": "Yoma",
    "sukkah": "Sukkah",
    "beitzah": "Beitzah", "betzah": "Beitzah", "beitsah": "Beitzah",
    "rosh hashanah": "Rosh Hashanah", "rosh hashana": "Rosh Hashanah",
    "taanit": "Taanit", "ta'anit": "Taanit", "fast": "Taanit",
    "megillah": "Megillah",
    "moed katan": "Moed Katan", "mo'ed katan": "Moed Katan",
    "chagigah": "Chagigah", "hagigah": "Chagigah",
    # Seder Nashim
    "yevamot": "Yevamot", "yebamot": "Yevamot",
    "ketubot": "Ketubot", "ketubbot": "Ketubot", "ketuboth": "Ketubot",
    "nedarim": "Nedarim",
    "nazir": "Nazir",
    "sotah": "Sotah",
    "gittin": "Gittin",
    "kiddushin": "Kiddushin",
    # Seder Nezikin
    "bava kamma": "Bava Kamma", "baba kamma": "Bava Kamma", "bk": "Bava Kamma",
    "bava metzia": "Bava Metzia", "baba metzia": "Bava Metzia", "bm": "Bava Metzia",
    "bava batra": "Bava Batra", "baba batra": "Bava Batra", "bb": "Bava Batra",
    "sanhedrin": "Sanhedrin",
    "makkot": "Makkot", "makkoth": "Makkot",
    "shevuot": "Shevuot", "shevu'ot": "Shevuot",
    "avodah zarah": "Avodah Zarah", "avoda zarah": "Avodah Zarah", "az": "Avodah Zarah",
    "horayot": "Horayot",
    # Seder Kodashim
    "zevachim": "Zevachim", "zebachim": "Zevachim",
    "menachot": "Menachot", "menahot": "Menachot",
    "chullin": "Chullin", "hullin": "Chullin",
    "bechorot": "Bechorot", "bekhorot": "Bechorot",
    "arachin": "Arachin", "arakin": "Arachin",
    "temurah": "Temurah",
    "keritot": "Keritot", "karetot": "Keritot",
    "meilah": "Meilah",
    "tamid": "Tamid",
    "niddah": "Niddah",
}

# Valid daf notation: digits + a or b, e.g. "2a", "31b", "100a"
_DAF_RE = re.compile(r"^(\d+)([ab])$", re.IGNORECASE)


def resolve_talmud_tractate(raw: str) -> str | None:
    """Return canonical Sefaria tractate name or None."""
    key = raw.lower().strip()
    if key in TALMUD_TRACTATES:
        return TALMUD_TRACTATES[key]
    matches = get_close_matches(key, TALMUD_TRACTATES.keys(), n=1, cutoff=0.75)
    return TALMUD_TRACTATES[matches[0]] if matches else None


def _fetch_sefaria_daf(tref: str, section: int | None, tractate_display: str,
                        daf: str, source_label: str) -> dict:
    """
    Shared fetch for Talmud/Zohar. Fetches the full daf/page then extracts section.
    tref: e.g. "Berakhot.2a" or "Zohar.1.1a"
    section: 1-indexed section number, or None for whole daf
    """
    url = SEFARIA_BASE + urllib.parse.quote(tref) + "?version=english"
    try:
        req = urllib.request.Request(
            url, headers={"User-Agent": "ScriptureBot/1.0"}
        )
        with urllib.request.urlopen(req, timeout=15) as r:
            raw = json.loads(r.read().decode("utf-8"))
        time.sleep(FETCH_DELAY)
    except Exception as e:
        return {"found": False, "error": f"Sefaria API error: {e}", "suggestions": []}

    # Extract text array from versions
    texts_arr = []
    version_title = "Sefaria"
    for v in raw.get("versions", []):
        if v.get("language") == "en" and v.get("text"):
            t = v["text"]
            version_title = v.get("versionTitle", "Sefaria")
            if isinstance(t, list):
                texts_arr = [re.sub(r"<[^>]+>", "", str(x)).strip() for x in t]
            else:
                texts_arr = [re.sub(r"<[^>]+>", "", str(t)).strip()]
            break

    if not texts_arr:
        return {"found": False, "error": f"No English text found for {tref}.", "suggestions": []}

    if section is None:
        # Whole daf — return all sections
        lines = [f"**[{i+1}]** {t}" for i, t in enumerate(texts_arr) if t]
        return {
            "found": True,
            "reference": f"{tractate_display} {daf}",
            "text": "\n".join(lines),
            "source": f"{source_label} — {version_title} (via Sefaria)",
        }
    else:
        # Single section — zero-indexed
        idx = section - 1
        if idx < 0 or idx >= len(texts_arr):
            return {
                "found": False,
                "error": f"{tractate_display} {daf} has {len(texts_arr)} sections. "
                         f"(Requested: {section})",
                "suggestions": [],
            }
        text = texts_arr[idx]
        if not text:
            return {"found": False, "error": f"Section {section} is empty.", "suggestions": []}
        return {
            "found": True,
            "reference": f"{tractate_display} {daf}:{section}",
            "text": text,
            "source": f"{source_label} — {version_title} (via Sefaria)",
        }


def fetch_talmud(tractate: str, daf: str, section: int | None) -> dict:
    """
    Fetch a Talmud passage. tractate is canonical name e.g. "Berakhot".
    daf is e.g. "2a". section is 1-indexed, or None for whole daf.
    """
    tref = f"{tractate}.{daf}"
    return _fetch_sefaria_daf(tref, section, tractate, daf,
                               "Babylonian Talmud (Steinsaltz/William Davidson)")


def parse_talmud_ref(reference: str):
    """
    Parse "Talmud Berakhot 2a:3" or "Gemara Shabbat 31a" into
    (tractate_raw, daf, section_or_None).
    Returns None if not a valid Talmud reference.
    """
    ref = reference.strip()
    # Strip leading "Talmud", "Gemara", "Bavli", "BT" prefixes
    ref = re.sub(r"^(?:talmud|gemara|bavli|bt|talmud bavli)\s+",
                 "", ref, flags=re.IGNORECASE).strip()

    # Match: "Tractate Name 2a:3" or "Tractate Name 2a"
    # The daf (e.g. "2a") must come at the end, optionally followed by :section
    m = re.match(
        r"^(.*?)\s+(\d+[ab])(?::(\d+))?$",
        ref, re.IGNORECASE
    )
    if not m:
        return None

    tractate_raw = m.group(1).strip()
    daf          = m.group(2).lower()        # e.g. "2a"
    section      = int(m.group(3)) if m.group(3) else None

    return tractate_raw, daf, section


def get_talmud(reference: str) -> dict | None:
    """
    Top-level Talmud lookup. Returns result dict or None if not a Talmud ref.
    """
    parsed = parse_talmud_ref(reference)
    if parsed is None:
        return None
    tractate_raw, daf, section = parsed
    tractate = resolve_talmud_tractate(tractate_raw)
    if tractate is None:
        return None   # Not a recognisable tractate — let caller try elsewhere
    return fetch_talmud(tractate, daf, section)


# ══════════════════════════════════════════════════════════════════════════════
# ZOHAR
# ══════════════════════════════════════════════════════════════════════════════
#
# Citation format:  Zohar 1:1a:3    (volume, daf, section)
#                   Zohar 2:15b     (whole daf)
#
# Sefaria tref:  Zohar.1.1a
# Volumes: 1 = Bereshit, 2 = Shemot, 3 = Vayikra/Bamidbar/Devarim
# ══════════════════════════════════════════════════════════════════════════════

# Zohar parashot as they appear on Sefaria (Zohar, [Parasha].[segment])
ZOHAR_PARASHOT = [
    ("Introduction", 34),
    ("Bereshit", 200),
    ("Noach", 150),
    ("Lech Lecha", 120),
    ("Vayera", 130),
    ("Chayei Sarah", 80),
    ("Toldot", 90),
    ("Vayetze", 100),
    ("Vayishlach", 90),
    ("Vayeshev", 80),
    ("Miketz", 80),
    ("Vayigash", 60),
    ("Vayechi", 100),
    ("Shemot", 100),
    ("Vaera", 80),
    ("Bo", 80),
    ("Beshalach", 80),
    ("Yitro", 80),
    ("Mishpatim", 100),
    ("Terumah", 150),
    ("Tetzaveh", 60),
    ("Ki Tisa", 80),
    ("Vayakhel", 80),
    ("Pekudei", 80),
    ("Vayikra", 60),
    ("Tzav", 50),
    ("Shmini", 50),
    ("Tazria", 50),
    ("Metzora", 40),
    ("Acharei Mot", 80),
    ("Kedoshim", 50),
    ("Emor", 80),
    ("Behar", 40),
    ("Bechukotai", 40),
    ("Bamidbar", 60),
    ("Nasso", 80),
    ("Behaalotcha", 60),
    ("Shelach Lecha", 60),
    ("Korach", 50),
    ("Chukat", 50),
    ("Balak", 80),
    ("Pinchas", 120),
    ("Matot", 40),
    ("Vaetchanan", 60),
    ("Eikev", 50),
    ("Re'eh", 50),
    ("Shoftim", 50),
    ("Ki Teitzei", 60),
    ("Ki Tavo", 50),
    ("Vayeilech", 30),
    ("Haazinu", 50),
    ("Vezot Haberachah", 30),
]


def parse_zohar_ref(reference: str):
    """
    Parse a Zohar reference into (parasha, segment_or_None).
    Accepts: "Zohar Bereshit 5", "Zohar Introduction 1"
    Returns None if not parseable.
    """
    ref = reference.strip()
    ref = re.sub(r"^(?:the\s+)?zohar[,\s]*", "", ref, flags=re.IGNORECASE).strip()
    if not ref:
        return None

    # Try "Parasha N"
    m = re.match(r"^(.+?)\s+(\d+)$", ref)
    if m:
        return m.group(1).strip(), int(m.group(2))

    # Just a parasha name
    return ref, None


def fetch_zohar(parasha: str, segment: int | None) -> dict:
    """Fetch a Zohar passage by parasha name and optional segment number."""
    # Sefaria ref format: "Zohar, Introduction.1" or "Zohar, Bereshit.5"
    tref = f"Zohar, {parasha.strip()}"
    if segment is not None:
        tref += f".{segment}"

    import urllib.request, json as _json
    url = f"https://www.sefaria.org/api/v3/texts/{urllib.parse.quote(tref)}?version=english"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "ScriptureBot/1.0"})
        with urllib.request.urlopen(req, timeout=10) as r:
            data = _json.loads(r.read().decode("utf-8"))
    except Exception as e:
        return {"found": False, "error": f"Sefaria API error: {e}", "suggestions": []}

    if "error" in data:
        return {"found": False, "error": f"Sefaria: {data['error']}", "suggestions": []}

    # Extract English text — may be a single string or list of segments
    versions = data.get("versions", [])
    raw_text = None
    for v in versions:
        if v.get("actualLanguage") == "en":
            raw_text = v.get("text", "")
            break

    if raw_text is None:
        return {"found": False, "error": f"No English translation found for Zohar {parasha} {segment or ''}.", "suggestions": []}

    def clean(t):
        t = re.sub(r"<[^>]+>", " ", str(t))
        return re.sub(r"\s+", " ", t).strip()

    ref_label = f"Zohar, {parasha}"
    if segment:
        ref_label += f" {segment}"

    # Single segment — return as plain text
    if isinstance(raw_text, str) or segment is not None:
        if isinstance(raw_text, list):
            # segment was specified but API returned a list (shouldn't happen often)
            text = " ".join(clean(x) for x in raw_text if x)
        else:
            text = clean(raw_text)
        if not text:
            return {"found": False, "error": f"No text found for {ref_label}.", "suggestions": []}
        return {
            "found": True,
            "reference": ref_label,
            "text": text,
            "source": "Zohar (Pritzker Edition, via Sefaria)",
            "book": "Zohar",
        }

    # Multiple segments (whole parasha) — paginate 3 segments per page
    PAGE_SIZE = 3
    segments = [clean(x) for x in raw_text if x and clean(x)]
    if not segments:
        return {"found": False, "error": f"No text found for {ref_label}.", "suggestions": []}

    if len(segments) == 1:
        return {
            "found": True,
            "reference": ref_label,
            "text": segments[0],
            "source": "Zohar (Pritzker Edition, via Sefaria)",
            "book": "Zohar",
        }

    pages = []
    for i in range(0, len(segments), PAGE_SIZE):
        chunk = segments[i:i+PAGE_SIZE]
        page_text = "\n\n".join(
            f"**[{i+j+1}]** {s}" for j, s in enumerate(chunk)
        )
        if len(page_text) > 3900:
            page_text = page_text[:3897] + "…"
        pages.append(page_text)

    return {
        "found": True,
        "reference": ref_label,
        "text": segments[0],  # fallback
        "source": "Zohar (Pritzker Edition, via Sefaria)",
        "book": "Zohar",
        "pages": pages,
    }


def get_zohar(reference: str) -> dict | None:
    """Top-level Zohar lookup. Returns result dict or None if not a Zohar ref."""
    parsed = parse_zohar_ref(reference)
    if parsed is None:
        return None
    parasha, segment = parsed
    return fetch_zohar(parasha, segment)

# ══════════════════════════════════════════════════════════════════════════════
# GENERIC SEFARIA FETCH
# ══════════════════════════════════════════════════════════════════════════════
#
# Used for Jerusalem Talmud, Targumim, Midrash Rabbah, Tosefta, Kabbalah,
# and any other Sefaria text not needing special parsing.
#
# tref format examples:
#   Jerusalem_Talmud_Berakhot.1.1        (chapter.halakhah)
#   Targum_Onkelos,_Genesis.1.1          (book.chapter.verse)
#   Bereshit_Rabbah.1.1                  (section.subsection)
#   Tosefta_Berakhot.1.1                 (chapter.halakhah)
#   Sefer_Yetzirah.1.1                   (chapter.mishnah)
# ══════════════════════════════════════════════════════════════════════════════

def fetch_sefaria_generic(tref: str) -> dict | None:
    """
    Fetch any Sefaria text by raw tref string.
    Returns result dict with found/text/reference/source, or None on hard failure.
    On soft failure (no English text) returns {found: False, error: ...}.
    """
    url = SEFARIA_BASE + urllib.parse.quote(tref) + "?version=english"
    try:
        req = urllib.request.Request(
            url, headers={"User-Agent": "ScriptureBot/1.0"}
        )
        with urllib.request.urlopen(req, timeout=15) as r:
            raw = json.loads(r.read().decode("utf-8"))
        time.sleep(FETCH_DELAY)
    except Exception as e:
        return {"found": False, "error": f"Sefaria API error: {e}", "suggestions": []}

    if "error" in raw:
        return {"found": False, "error": f"Sefaria: {raw['error']}", "suggestions": []}

    # Extract English text
    versions = raw.get("versions", [])
    text = ""
    version_title = "Sefaria"
    for v in versions:
        if v.get("language") == "en" and v.get("text"):
            raw_text = v["text"]
            version_title = v.get("versionTitle", "Sefaria")
            if isinstance(raw_text, list):
                # Flatten nested lists (e.g. chapter-level fetch returns list of verses)
                parts = []
                for i, item in enumerate(raw_text, 1):
                    if isinstance(item, list):
                        for j, sub in enumerate(item, 1):
                            clean = re.sub(r"<[^>]+>", "", str(sub)).strip()
                            if clean:
                                parts.append(f"**[{i}.{j}]** {clean}")
                    else:
                        clean = re.sub(r"<[^>]+>", "", str(item)).strip()
                        if clean:
                            parts.append(f"**[{i}]** {clean}")
                text = "\n".join(parts)
            else:
                text = re.sub(r"<[^>]+>", "", str(raw_text)).strip()
            break

    if not text:
        return {
            "found": False,
            "error": f"No English translation found for {tref.replace('_', ' ')}.",
            "suggestions": [],
        }

    display_ref = raw.get("ref", tref.replace("_", " ").replace(".", " "))

    return {
        "found": True,
        "reference": display_ref,
        "text": text,
        "source": version_title + " (via Sefaria)",
    }
