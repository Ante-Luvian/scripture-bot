"""
!compare, !variants, Strong's helpers and !strong concordance, !parallel.
"""
import asyncio
import discord
import re
import time
from scripture_lookup import BIBLE_OT, get_verse_drb, get_verse_knox
from translation_lookup import TRANSLATIONS, _mt_to_lxx_psalm, get_translation
from discord import app_commands
from poem_lookup import classify_scripture, is_drb_reference, lookup_pair, parse_poem_ref, list_works as poem_list_works, lookup as poem_lookup
from strongs_lookup import get_definition as get_local_strongs_definition
from core import (
    _check_search_cooldown,
    guild_traditions,
    bot,
    lookup,
)

# what !parallel offers a server without the Greek and Roman texts
_BIBLE_ONLY_PARALLEL = ("`!parallel John 3:16` — a Bible verse beside the original: the Greek of the New Testament, "
                        "the Hebrew of the Old.")

# ── !compare — verse in multiple translations, paginated ─────────────────────

# All English translations for !compare, in display order
_COMPARE_ALL = [
    # Major modern
    "KJV", "ESV", "NASB", "NKJV", "NLT", "NET",                  # (no NIV: see translation_lookup.WITHDRAWN)
    "NRSVCE", "RSV", "RSV2CE", "WEB", "CSB17", "AMP", "MSG",
    # Public domain / historical
    "ASV", "YLT", "GNV",
    # Catholic / Jewish / other
    "NABRE", "NJB1985", "CJB", "TLV",
    # Remaining
    "BSB", "LSV", "LSB", "MEV", "ISV", "ERV", "GNTD", "CEVD", "CEB",
]

# Ancient language set — determined per-verse based on OT/NT
# OT abbreviations for _is_ot_reference
_OT_ABBREVS = {
    # Protestant OT
    "gen","exod","ex","lev","num","deut","josh","judg","ru","ruth",
    "1sam","2sam","1kgs","2kgs","1chr","2chr","ezra","neh","esth",
    "job","ps","psa","prov","eccl","song","isa","jer","lam","ezek",
    "dan","hos","joel","amos","obad","jon","mic","nah","hab","zeph",
    "hag","zech","mal",
    # Deuterocanonical / Apocrypha
    "tob","tobit","jdt","judith","wis","wisdom","sir","sirach",
    "ecclesiasticus","bar","baruch","1macc","2macc","3macc","4macc",
    "1maccabees","2maccabees","1esd","2esd","1esdras","2esdras",
    "pman","prayer of manasseh","additions to esther",
}

# Full names of OT + Apocrypha books for _is_ot_reference
_OT_FULL_NAMES = set(BIBLE_OT) | {
    "Tobit","Judith","Wisdom of Solomon","Sirach","Baruch",
    "1 Maccabees","2 Maccabees","3 Maccabees","4 Maccabees",
    "1 Esdras","2 Esdras","Prayer of Manasseh","Additions to Esther",
    "Epistle of Jeremiah","Song of the Three Children","Susanna",
    "Bel and the Dragon","Psalms of Solomon","Book of Enoch","Book of Jubilees",
}

def _is_ot_reference(reference: str) -> bool:
    """Return True if reference is from the OT, Apocrypha, or Pseudepigrapha."""
    m = re.match(r"^((?:\d\s*)?[A-Za-z][A-Za-z\s'&-]{0,30}?)\s+\d", reference.strip())
    if not m:
        return False
    book = m.group(1).strip().lower()
    if book in _OT_ABBREVS:
        return True
    return any(book == b.lower() or b.lower().startswith(book) for b in _OT_FULL_NAMES)


@bot.command(name="compare", aliases=["cmp"])
async def cmd_compare(ctx, *, reference: str = ""):
    """
    Show a verse across translations, paginated.
    Usage: !compare John 3:16
           !compare ancient John 3:16   — KJV + Greek/Hebrew + LXX + Vulgate
           !compare strong John 3:16    — KJV + WLC/TISCH with Strong's numbers
    """
    if not reference:
        await ctx.send("Usage: `!compare John 3:16` or `!compare ancient John 3:16` or `!compare strong John 3:16`")
        return
    if not _check_search_cooldown(ctx.author.id):
        await ctx.send("⏳ Please wait a moment before using !compare again.", delete_after=8)
        return

    # Detect mode: "strong <ref>" > "ancient <ref>" > "<ref>"
    ancient_mode = False
    strong_mode = False
    ref = reference.strip()
    if ref.lower().startswith("strong "):
        strong_mode = True
        ref = ref[len("strong "):].strip()
    elif ref.lower().startswith("ancient "):
        ancient_mode = True
        ref = ref[8:].strip()

    async with ctx.typing():
        if strong_mode:
            await _send_compare_ancient_strong(ctx, ref)
        elif ancient_mode:
            await _send_compare_ancient(ctx, ref)
        else:
            await _send_compare(ctx, ref)

@bot.tree.command(name="compare", description="Show a verse across multiple translations")
@app_commands.describe(reference="e.g. John 3:16  |  ancient John 3:16  |  strong John 3:16")
async def compare_slash(interaction: discord.Interaction, reference: str):
    await interaction.response.defer()
    ctx = await bot.get_context(interaction)
    raw = reference.strip()
    if raw.lower().startswith("strong "):
        await _send_compare_ancient_strong(ctx, raw[len("strong "):].strip())
    elif raw.lower().startswith("ancient "):
        await _send_compare_ancient(ctx, raw[8:].strip())
    else:
        await _send_compare(ctx, raw)


# ── !variants — KJV vs a Dead Sea Scroll witness (+ LXX), when one exists ──────

_DSS_BIBLICAL_BOOKS: dict[str, str] = {
    "Isaiah": "Isaiah (1QIsaa)",
    "Exodus": "Exodus (4Q22)",
    "Deuteronomy": "Deuteronomy (4Q41)",
    "Psalms": "Psalms (4Q86)",
    "Daniel": "Daniel (4Q114)",
}

# Cave/discovery-year/archive-link metadata, verified directly against
# opendeadsea-mss's own manuscripts.json (the same catalog the scroll text
# itself comes from). 1QIsaa has no deadseascrolls.org.il entry in that
# catalog, so it links to Wikipedia instead.
_DSS_SCROLL_META: dict[str, dict] = {
    "Isaiah (1QIsaa)":   {"site": "Qumran, Cave 1", "found": 1947, "url": "https://en.wikipedia.org/wiki/Isaiah_Scroll"},
    "Exodus (4Q22)":     {"site": "Qumran, Cave 4", "found": 1952, "url": "https://www.deadseascrolls.org.il/explore-the-archive/manuscript/4Q22-1"},
    "Deuteronomy (4Q41)":{"site": "Qumran, Cave 4", "found": 1952, "url": "https://www.deadseascrolls.org.il/explore-the-archive/manuscript/4Q41-1"},
    "Psalms (4Q86)":     {"site": "Qumran, Cave 4", "found": 1952, "url": "https://www.deadseascrolls.org.il/explore-the-archive/manuscript/4Q86-1"},
    "Daniel (4Q114)":    {"site": "Qumran, Cave 4", "found": 1952, "url": "https://www.deadseascrolls.org.il/explore-the-archive/manuscript/4Q114-1"},
}


@bot.command(name="variants", aliases=["dss", "scrollcompare"])
async def cmd_variants(ctx, *, reference: str = ""):
    """Compare a verse's KJV, Septuagint (LXX), and Dead Sea Scroll text,
    when a scroll is loaded for that book (currently Isaiah, Exodus,
    Deuteronomy, Psalms, Daniel), with the scroll's discovery history and
    a link to view it.
    Usage: !variants Isaiah 53:5"""
    ref = reference.strip()
    if not ref:
        await ctx.send(
            "Usage: `!variants <reference>` — e.g. `!variants Isaiah 53:5`. "
            f"Scrolls loaded for: {', '.join(_DSS_BIBLICAL_BOOKS)}."
        )
        return

    result = lookup.get_verse(ref)
    if not result.get("found"):
        await ctx.send(f"⚠️ {result.get('error', 'Verse not found.')}")
        return

    m = re.match(r"^(.*?)\s+(\d+):(\d+)", result["reference"])
    if not m:
        await ctx.send("Couldn't determine a chapter:verse for this reference.")
        return
    book, chap, verse = m.group(1), m.group(2), m.group(3)

    scroll_book = _DSS_BIBLICAL_BOOKS.get(book)
    if not scroll_book:
        await ctx.send(
            f"No Dead Sea Scroll witness is loaded for **{book}**. "
            f"Currently available: {', '.join(_DSS_BIBLICAL_BOOKS)}."
        )
        return

    async with ctx.typing():
        dss_result = lookup.get_verse(f"{scroll_book} {chap}:{verse}")
        loop = asyncio.get_event_loop()
        lxx_result = await loop.run_in_executor(None, get_translation, result["reference"], "LXX")

    embed = discord.Embed(title=f"📜 {result['reference']}", color=discord.Color.dark_gold())
    kjv_text = result["text"]
    if len(kjv_text) > 1024:
        kjv_text = kjv_text[:1021] + "…"
    embed.add_field(name=result.get("source") or "King James Version", value=kjv_text, inline=False)

    if dss_result.get("found"):
        dss_text = dss_result["text"]
        if len(dss_text) > 1024:
            dss_text = dss_text[:1021] + "…"
        embed.add_field(name=scroll_book, value=dss_text, inline=False)
    else:
        embed.add_field(
            name=scroll_book,
            value="*This scroll doesn't preserve this specific verse (damaged/fragmentary at this point).*",
            inline=False,
        )

    if lxx_result.get("found"):
        lxx_text = lxx_result["text"]
        if len(lxx_text) > 1024:
            lxx_text = lxx_text[:1021] + "…"
        embed.add_field(name="Septuagint (Greek OT)", value=lxx_text, inline=False)

    meta = _DSS_SCROLL_META.get(scroll_book)
    if meta:
        embed.add_field(
            name="Manuscript",
            value=f"Discovered {meta['found']}, {meta['site']} · [View manuscript]({meta['url']})",
            inline=False,
        )
    embed.set_footer(text=dss_result.get("source", "") or "Open Dead Sea (opendeadsea.org, CC BY-NC 4.0)")
    await ctx.send(embed=embed)


@bot.tree.command(name="variants", description="Compare a verse's KJV text against its Dead Sea Scroll witness")
@app_commands.describe(reference="e.g. Isaiah 53:5")
async def variants_slash(interaction: discord.Interaction, reference: str):
    await interaction.response.defer()
    ctx = await bot.get_context(interaction)
    await cmd_variants(ctx, reference=reference)


async def _fetch_one_translation(slug: str, reference: str) -> tuple[str, str, str]:
    """Fetch a single translation in a thread executor (non-blocking)."""
    loop = asyncio.get_event_loop()

    def _fetch_sync():
        if slug == "KJV":
            r = lookup.get_verse(reference)
            text = r["text"] if r.get("found") else "*Not found*"
            return ("KJV", "King James Version (1769)", text)
        elif slug == "DRB":
            # Try reference as-is first
            r = get_verse_drb(reference)
            if not r.get("found"):
                # Remap KJV apocrypha names to Douay-Rheims equivalents
                _DRB_APOC = {
                    "wisdom of solomon": "Wisdom",
                    "sirach": "Ecclesiasticus",
                    "ecclesiasticus": "Ecclesiasticus",
                    "1 maccabees": "1 Machabees",
                    "2 maccabees": "2 Machabees",
                    "1 esdras": "3 Esdras",
                    "2 esdras": "4 Esdras",
                    "prayer of manasseh": "Prayer of Manasses",
                    "tobit": "Tobias",
                }
                m = re.match(r'^((?:\d\s*)?[A-Za-z][A-Za-z\s]+?)\s+(\d.*)$', reference.strip(), re.I)
                if m:
                    book_raw = m.group(1).strip().lower()
                    rest = m.group(2)
                    remapped = _DRB_APOC.get(book_raw)
                    if remapped:
                        r = get_verse_drb(f"{remapped} {rest}")
            text = r["text"] if r.get("found") else "*Not found*"
            return ("DRB", "Douay-Rheims Bible", text)
        elif slug == "Knox":
            r = get_verse_knox(reference)
            text = r["text"] if r.get("found") else "*Not found*"
            return ("Knox", "Knox Bible (1945–49)", text)
        elif slug == "VULG":
            r = get_translation(reference, "VULG")
            if not r.get("found"):
                time.sleep(0.5)
                r = get_translation(reference, "VULG")  # one retry
            if r.get("found"):
                return ("VULG", "Vulgata Clementina (Latin)", r["text"])
            return ("VULG", "Vulgata Clementina (Latin)", "*Not available*")
        elif slug == "LXX":
            r = get_translation(reference, "LXX")
            if r.get("found"):
                return ("LXX", "Septuagint (Greek OT)", r["text"])
            return ("LXX", "Septuagint (Greek OT)", "*Not available*")
        elif slug == "OE":
            r = get_translation(reference, "OE")
            if r.get("found"):
                return ("OE", "Old English (Ælfric/Wessex Gospels, ~990 AD)", r["text"])
            return ("OE", "Old English (Ælfric/Wessex Gospels, ~990 AD)", "*Not available*")
        elif slug == "PESHITTA":
            r = get_translation(reference, "PESHITTA")
            if r.get("found"):
                return ("PESHITTA", "Peshitta (Classical Syriac/Aramaic)", r["text"])
            return ("PESHITTA", "Peshitta (Classical Syriac/Aramaic)", "*Not available*")
        elif slug == "CSL":
            r = get_translation(reference, "CSL")
            if r.get("found"):
                return ("CSL", "Church Slavonic (Elizabeth Bible, 1757)", r["text"])
            return ("CSL", "Church Slavonic (Elizabeth Bible, 1757)", "*Not available*")
        else:
            r = get_translation(reference, slug)
            if r.get("found"):
                display = TRANSLATIONS.get(slug.lower(), (slug, slug))[1]
                return (slug, display, r["text"])
            return (slug, slug, "*Not available*")

    return await loop.run_in_executor(None, _fetch_sync)


async def _send_compare(ctx, reference: str):
    """Fetch all English translations concurrently and display paginated."""

    tasks = [_fetch_one_translation(slug, reference) for slug in _COMPARE_ALL]
    raw = await asyncio.gather(*tasks)
    results = [(s, d, t) for s, d, t in raw if t not in ("*Not found*", "*Not available*")]

    if not results:
        await ctx.send(f"⚠️ Could not find **{reference}** in any translation.")
        return

    await _display_compare(ctx, reference, results, "All Translations")


async def _send_compare_ancient(ctx, reference: str):
    """Fetch KJV + language-appropriate ancient texts concurrently."""
    from poem_lookup import classify_scripture
    scripture_type = classify_scripture(reference)

    # For Psalms, annotate the title with the LXX/Vulgate numbering
    display_reference = reference
    import re as _re
    _psalm_m = _re.match(r'^Ps(?:alms?)?[.\\s]+(\\d+)(?:[:\\s](\\d+))?', reference.strip(), _re.I)
    if _psalm_m:
        mt_num = int(_psalm_m.group(1))
        verse_part = f":{_psalm_m.group(2)}" if _psalm_m.group(2) else ""
        # Compute LXX number(s)
        lxx_mappings = _mt_to_lxx_psalm(mt_num)
        if len(lxx_mappings) == 1 and lxx_mappings[0][1] is None and lxx_mappings[0][0] != mt_num:
            lxx_num = lxx_mappings[0][0]
            display_reference = f"Psalm {mt_num}{verse_part} [LXX/VULG: {lxx_num}{verse_part}]"
        elif len(lxx_mappings) == 1 and lxx_mappings[0][1] is not None:
            lxx_num, vs, ve = lxx_mappings[0]
            display_reference = f"Psalm {mt_num}{verse_part} [LXX/VULG: {lxx_num}:{vs}-{ve}]"
        elif len(lxx_mappings) > 1:
            lxx_str = " + ".join(str(m[0]) for m in lxx_mappings)
            display_reference = f"Psalm {mt_num}{verse_part} [LXX/VULG: {lxx_str}]"

    # Determine whether Old English has coverage for this book.
    # OE corpus = Wessex Gospels (Matthew, Mark, Luke, John) +
    # Ælfric's Heptateuch (Genesis-Judges) + Paris Psalter (Psalms).
    _OE_BOOKS = {
        "matthew", "matt", "mt",
        "mark", "mk", "mrk",
        "luke", "lk", "luk",
        "john", "jn", "joh",
        "genesis", "gen", "ge", "gn",
        "exodus", "exod", "ex", "exo",
        "leviticus", "lev", "lv",
        "numbers", "num", "nm", "nu",
        "deuteronomy", "deut", "dt",
        "joshua", "josh", "jos",
        "judges", "judg", "jdg", "jgs",
        "psalm", "psalms", "ps", "psa", "pss",
    }
    _book_m = _re.match(r"^\s*((?:[1-3]\s*)?[A-Za-z][A-Za-z\s\.]*?)\s+\d", reference.strip())
    _book_key = _book_m.group(1).strip().lower().replace(".", "") if _book_m else ""
    has_oe = _book_key in _OE_BOOKS

    if scripture_type == 'nt':
        # New order: KJV, TR, VULG, PESHITTA, CSL, OE
        slug_list = ["KJV", "TR", "VULG", "PESHITTA", "CSL"]
        if has_oe:
            slug_list.append("OE")
    elif scripture_type == 'apocrypha':
        # Apocrypha (no OE coverage at all): KJV, LXX, VULG, PESHITTA, CSL
        slug_list = ["KJV", "LXX", "VULG", "PESHITTA", "CSL"]
    else:
        # OT proper. New order: KJV, WLC, LXX, VULG, PESHITTA, CSL, OE
        slug_list = ["KJV", "WLC", "LXX", "VULG", "PESHITTA", "CSL"]
        if has_oe:
            slug_list.append("OE")

    raw = []
    for i, slug in enumerate(slug_list):
        if i > 0:
            await asyncio.sleep(0.3)
        result = await _fetch_one_translation(slug, reference)
        raw.append(result)

    display_overrides = {
        "WLC":  "Hebrew OT (Westminster Leningrad Codex)",
        "OE":   "Old English (Ælfric/Wessex Gospels, ~990 AD)",
        "PESHITTA": "Peshitta (Classical Syriac/Aramaic)",
        "CSL":      "Church Slavonic (Elizabeth Bible, 1757)",
        "LXX":  "Septuagint (Greek OT)",
        "TR":   "Textus Receptus (Greek NT, Elzevir 1624)",
        "VULG": "Vulgata Clementina (Latin)",
    }
    results = []
    for slug, display, text in raw:
        d = display_overrides.get(slug, display)
        results.append((slug, d, text))

    await _display_compare(ctx, display_reference, results, "Ancient Languages", page_size=6)


# ── Strong's lookup helpers ───────────────────────────────────────────────────
#
# Source: bolls.life
#   Strong's-tagged Hebrew OT  →  slug "WLCa"
#   Strong's-tagged Greek NT   →  slug "TISCH"
#   Dictionary endpoint        →  /dictionary-definition/BDBT/<query>
#     (BDB for Hebrew, Thayer's for Greek; also accepts H123 / G456 directly)

_STRONGS_DEF_CACHE: dict[str, dict | None] = {}


def _bolls_fetch_chapter(slug: str, book_id: int, chapter: int) -> list | None:
    """Synchronous bolls.life chapter fetch that preserves the raw text
    (does NOT strip Strong's-number tags). Returns the verse list or None."""
    import urllib.request, urllib.error, json as _json
    url = f"https://bolls.life/get-text/{slug}/{book_id}/{chapter}/"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "ScriptureBot/1.0"})
        with urllib.request.urlopen(req, timeout=15) as r:
            data = _json.loads(r.read().decode("utf-8"))
        return data if isinstance(data, list) else None
    except urllib.error.HTTPError:
        return None
    except Exception:
        return None


def _parse_strongs_text(text: str) -> list[tuple[str, str]]:
    """
    Parse bolls.life Strong's-tagged verse text into [(word, "G####"), ...].

    Bolls returns HTML with one of two encodings:
      1. <S>1234</S> tags after each word (SWORD style)
      2. Inline digits glued to the word, e.g. "λόγος3056"
    We handle both, preferring the <S> form when present.
    """
    import html as html_mod
    text = html_mod.unescape(text)

    # Strip <br>, paragraph tags, etc., but keep <S> for parsing
    text = re.sub(r"<(?!/?[Ss]\b)[^>]+>", " ", text)

    # Decide which book this is so we can tag the prefix correctly
    # (we don't know here; the caller passes the testament marker via slug).
    # We just preserve the raw number; the caller adds "G" or "H".

    pairs: list[tuple[str, str]] = []

    # Try <S>1234</S> form first
    s_pattern = re.compile(
        r"(\S+?)\s*<S>\s*(\d+)\s*</S>",
        re.IGNORECASE
    )
    s_matches = list(s_pattern.finditer(text))
    if s_matches:
        for m in s_matches:
            word = m.group(1).strip().strip(",.:;!?·")
            num = m.group(2)
            if word:
                pairs.append((word, num))
        return pairs

    # Fall back: strip any remaining tags, then scan for word+digits
    text = re.sub(r"<[^>]+>", " ", text)

    # Inline format: word followed immediately by digits
    inline_pattern = re.compile(r"(\S+?)(\d+)(?=\s|$|[,.:;!?])")
    for m in inline_pattern.finditer(text):
        word = m.group(1).strip().strip(",.:;!?·")
        num = m.group(2)
        # Filter out non-Strong's stuff (e.g. footnote markers)
        if word and len(num) <= 5:
            pairs.append((word, num))

    return pairs


def _parse_kjv_reverse_interlinear(text: str) -> list[dict]:
    """
    Parse bolls.life KJV Strong's-tagged text into an ordered list of
    {"phrase": "...", "strong": "1234" or None}, preserving every English
    word in natural KJV reading order -- unlike _parse_strongs_text, which
    keeps only one representative word per Strong's number (fine for a
    reverse lookup, not for displaying the whole verse).

    A "<S>NUM</S>" tag attaches to every word back to the previous tag (or
    the start of the verse): Hebrew/Greek words routinely cover more than
    one English word (e.g. "In the beginning" is one Hebrew word,
    re'shiyth, H7225). Untranslatable grammatical markers (e.g. H853, the
    Hebrew direct object marker) can own an empty phrase; those are
    dropped rather than shown as a blank tag.
    """
    import html as html_mod
    text = html_mod.unescape(text)
    text = re.sub(r"<(?!/?[Ss]\b)[^>]+>", " ", text)

    parts = re.split(r"<S>\s*(\d+)\s*</S>", text)
    entries = []
    for i in range(0, len(parts) - 1, 2):
        phrase = re.sub(r"\s+", " ", parts[i]).strip()
        if phrase:
            entries.append({"phrase": phrase, "strong": parts[i + 1]})
    if len(parts) % 2 == 1:
        trailing = re.sub(r"\s+", " ", parts[-1]).strip()
        if trailing:
            entries.append({"phrase": trailing, "strong": None})
    return entries


def _fetch_strongs_passage(reference: str, testament: str) -> dict:
    """
    Fetch one verse from bolls.life in Strong's-tagged form.

    testament: "nt" → uses TISCH (Greek, "G" prefix)
               "ot" → uses WLCa  (Hebrew, "H" prefix)

    Returns:
      {"found": True, "ref": display_ref, "slug": slug, "pairs": [(word,"G####"), ...]}
      {"found": False, "error": "..."}
    """
    from translation_lookup import _BOOK_IDS, _ALIASES

    # Strip range to first verse for the lookup, since each verse is its own row
    ref_single = re.sub(r"(\d+:\d+)[-–]\d+$", r"\1", reference.strip())

    m = re.match(r"^((?:\d\s*)?[A-Za-z][a-zA-Z\s\.]+?)\s+(\d+):(\d+)$", ref_single)
    if not m:
        chapter_only = re.match(r"^((?:\d\s*)?[A-Za-z][a-zA-Z\s\.]+?)\s+\d+$", ref_single)
        if chapter_only:
            return {"found": False, "error": f"`{ref_single}` is a whole chapter — this needs one verse, e.g. `{ref_single}:1`."}
        return {"found": False, "error": f"Couldn't parse `{ref_single}`. Try a single verse like `John 3:16`."}

    book_raw = m.group(1).strip().lower().replace(".", "")
    chapter = int(m.group(2))
    verse = int(m.group(3))

    book_id = _BOOK_IDS.get(book_raw) or _BOOK_IDS.get(_ALIASES.get(book_raw, ""))
    if not book_id:
        return {"found": False, "error": f"Unknown book: **{m.group(1).strip()}**"}

    if testament == "nt":
        slug = "TISCH"
        prefix = "G"
    else:
        slug = "WLCa"
        prefix = "H"

    rows = _bolls_fetch_chapter(slug, book_id, chapter)
    if not rows:
        return {"found": False, "error": f"Could not fetch {slug} {ref_single} from bolls.life."}

    row = next((v for v in rows if v.get("verse") == verse), None)
    if not row:
        return {"found": False, "error": f"Verse {verse} not found in {slug} chapter."}

    raw_text = row.get("text", "")
    raw_pairs = _parse_strongs_text(raw_text)
    pairs = [(w, f"{prefix}{n}") for (w, n) in raw_pairs]

    return {
        "found": True,
        "ref": f"{m.group(1).strip().title()} {chapter}:{verse}",
        "slug": slug,
        "pairs": pairs,
        "book_id": book_id,
        "chapter": chapter,
        "verse": verse,
    }


def _fetch_kjv_word_map(book_id: int, chapter: int, verse: int) -> dict:
    """Fetch the KJV's own Strong's-tagged English text for one verse and
    return {bare_strongs_number: deque[english_word, ...]} in KJV word
    order. Used to show the actual KJV rendering of each original-language
    word in !interlinear instead of a generic lexicon gloss -- e.g. G2889
    (kosmos) shows "world" here (what the KJV actually wrote in this verse)
    rather than a lexicon pick like "adorning" (also a real KJV rendering,
    just not the one used in this particular verse)."""
    from collections import defaultdict, deque
    by_num: dict[str, deque] = defaultdict(deque)
    rows = _bolls_fetch_chapter("KJV", book_id, chapter)
    if not rows:
        return by_num
    row = next((v for v in rows if v.get("verse") == verse), None)
    if not row:
        return by_num
    for word, num in _parse_strongs_text(row.get("text", "")):
        by_num[num].append(word)
    return by_num


def _fetch_strongs_definition(number: str) -> dict | None:
    """
    Look up a Strong's number (e.g. "G3588" or "H7225"). Tries the local
    OpenScriptures dictionary first (instant, always available, covers the
    full standard Strong's range); falls back to the live bolls.life
    dictionary endpoint only for anything the local copy doesn't have.

    Keys in the returned dict (when found):
      lexeme, transliteration, pronunciation, short_definition, definition
    """
    import urllib.request, urllib.error, json as _json

    key = number.strip().upper()
    if not re.match(r"^[GH]\d+$", key):
        return None

    local = get_local_strongs_definition(key)
    if local:
        return local

    if key in _STRONGS_DEF_CACHE:
        return _STRONGS_DEF_CACHE[key]

    url = f"https://bolls.life/dictionary-definition/BDBT/{key}/"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "ScriptureBot/1.0"})
        with urllib.request.urlopen(req, timeout=10) as r:
            data = _json.loads(r.read().decode("utf-8"))
    except Exception:
        _STRONGS_DEF_CACHE[key] = None
        return None

    if not isinstance(data, list) or not data:
        _STRONGS_DEF_CACHE[key] = None
        return None

    # Pick the entry whose topic matches our number; fall back to first.
    entry = next((d for d in data if str(d.get("topic", "")).upper() == key), data[0])
    _STRONGS_DEF_CACHE[key] = entry
    return entry


async def _send_compare_ancient_strong(ctx, reference: str):
    """KJV + Strong's-tagged Hebrew (OT) or Greek (NT) for one verse."""
    from poem_lookup import classify_scripture

    scripture_type = classify_scripture(reference)
    if scripture_type == "apocrypha":
        await ctx.send("⚠️ Strong's tagging isn't available for apocryphal books.")
        return

    testament = "nt" if scripture_type == "nt" else "ot"

    # KJV verse text
    ref_single = re.sub(r"(\d+:\d+)[-–]\d+$", r"\1", reference.strip())
    kjv = lookup.get_verse(ref_single)
    kjv_text = kjv["text"] if kjv.get("found") else "*Not available*"
    display_ref = kjv.get("reference", ref_single) if kjv.get("found") else ref_single

    # Strong's-tagged original
    loop = asyncio.get_event_loop()
    strongs = await loop.run_in_executor(None, _fetch_strongs_passage, ref_single, testament)

    if not strongs.get("found"):
        err = strongs.get("error", "Strong's lookup failed.")
        await ctx.send(f"⚠️ {err}")
        return

    pairs = strongs["pairs"]
    if not pairs:
        await ctx.send(f"⚠️ No Strong's-tagged words found for **{display_ref}**.")
        return

    slug = strongs["slug"]
    if slug == "TISCH":
        original_label = "Greek NT (Tischendorf 8th, with Strong's)"
        is_rtl = False
    else:
        original_label = "Hebrew OT (WLC, with Strong's)"
        is_rtl = True

    if is_rtl:
        # Hebrew is RTL; inline mixing with ASCII Strong's numbers can leave
        # the number visually orphaned when a wrap splits the pair. Two-part
        # mitigation:
        #   • Non-breaking space (U+00A0) between word and number — Discord
        #     will never wrap a pair.
        #   • Wider separator between pairs ("  ·  ") so the eye groups them.
        # The Strong's number goes FIRST in source order so that bidi resolves
        # it to the visual LEFT of the Hebrew word (which is what Hebrew
        # readers expect when annotations appear with words).
        tokens = [f"[`{n}`]\u00A0**{w}**" for (w, n) in pairs]
        separator = "  ·  "
    else:
        # Greek is LTR; flowing-sentence layout reads naturally.
        tokens = [f"**{w}** [`{n}`]" for (w, n) in pairs]
        separator = " "

    embed = discord.Embed(
        title=f"📖 {display_ref} — Strong's",
        color=discord.Color.dark_gold(),
    )
    embed.add_field(
        name="KJV — King James Version (1769)",
        value=kjv_text[:1020] + ("…" if len(kjv_text) > 1020 else ""),
        inline=False,
    )

    # Discord field cap is 1024 chars; split into chunks at token boundaries.
    chunk = ""
    chunk_idx = 1

    def _flush(c: str, idx: int) -> None:
        embed.add_field(
            name=f"{original_label}" + (f" (cont. {idx})" if idx > 1 else ""),
            value=c.rstrip(),
            inline=False,
        )

    for tok in tokens:
        # +len(separator) accounts for the joiner
        if chunk and len(chunk) + len(separator) + len(tok) > 1020:
            _flush(chunk, chunk_idx)
            chunk = ""
            chunk_idx += 1
        chunk += (separator if chunk else "") + tok
    if chunk:
        _flush(chunk, chunk_idx)

    embed.set_footer(text=f"{len(pairs)} words · use !strong <number> for definitions · bolls.life")
    await ctx.send(embed=embed)


# ── Strong's concordance search: every occurrence of a number in one book ──────
# Scoped to a single book (not the whole Bible) — a full-Bible search would mean
# hundreds of live bolls.life fetches per query, which isn't fair use of a free
# public API or a reasonable wait for a Discord command.
_CONCORDANCE_CHAPTER_CACHE: dict[tuple, list] = {}  # (slug, book_id, chapter) -> [(verse_num, [(word, num), ...]), ...]

async def _send_strongs_concordance(ctx, number: str, book_raw: str):
    from translation_lookup import _BOOK_IDS, _ALIASES, _CHAPTER_COUNTS

    book_key = book_raw.strip().lower().replace(".", "")
    book_id = _BOOK_IDS.get(book_key) or _BOOK_IDS.get(_ALIASES.get(book_key, ""))
    if not book_id:
        await ctx.send(
            f"⚠️ Unknown book: **{book_raw}**. Concordance search works within one canonical "
            "Bible book, e.g. `!strong G26 in John`."
        )
        return

    testament = "nt" if number.startswith("G") else "ot"
    if testament == "nt" and book_id < 40:
        await ctx.send(f"⚠️ **{book_raw}** is an Old Testament book — `G`-prefixed numbers only apply to the NT.")
        return
    if testament == "ot" and book_id >= 40:
        await ctx.send(f"⚠️ **{book_raw}** is a New Testament book — `H`-prefixed numbers only apply to the OT.")
        return

    slug = "TISCH" if testament == "nt" else "WLCa"
    target = number[1:]
    n_chapters = _CHAPTER_COUNTS.get(book_id)
    if not n_chapters:
        await ctx.send(f"⚠️ No chapter data available for **{book_raw}**.")
        return

    book_title = book_raw.strip().title()
    matches = []
    async with ctx.typing():
        loop = asyncio.get_event_loop()
        for chap in range(1, n_chapters + 1):
            key = (slug, book_id, chap)
            per_verse = _CONCORDANCE_CHAPTER_CACHE.get(key)
            if per_verse is None:
                verses = await loop.run_in_executor(None, _bolls_fetch_chapter, slug, book_id, chap)
                per_verse = []
                if verses:
                    for v in verses:
                        per_verse.append((v.get("verse"), _parse_strongs_text(v.get("text", ""))))
                _CONCORDANCE_CHAPTER_CACHE[key] = per_verse
            for verse_num, pairs in per_verse:
                for word, num in pairs:
                    if num == target:
                        matches.append((chap, verse_num, word))

    if not matches:
        await ctx.send(f"No occurrences of **{number}** found in **{book_title}**.")
        return

    lines = [f"{book_title} {c}:{v} — **{w}**" for c, v, w in matches[:40]]
    embed = discord.Embed(
        title=f"🔎 {number} in {book_title}",
        description="\n".join(lines),
        color=discord.Color.dark_gold(),
    )
    footer = f"{len(matches)} occurrence(s)"
    if len(matches) > 40:
        footer += " — showing first 40"
    footer += " · bolls.life"
    embed.set_footer(text=footer)
    await ctx.send(embed=embed)


# ── !strong — Strong's concordance lookup ─────────────────────────────────────

@bot.command(name="strong", aliases=["strongs"])
async def cmd_strong(ctx, *, query: str = ""):
    """Look up a Strong's number, or get a verse with Strong's tagging.
    Usage:
      !strong G3588             — Greek lexicon entry
      !strong H7225             — Hebrew lexicon entry
      !strong John 3:16         — verse with each word tagged (alias for !compare strong)
      !strong Psalm 23:1        — same, for OT
    """
    raw = (query or "").strip()
    if not raw:
        await ctx.send(
            "Usage: `!strong G3588` · `!strong H7225` · `!strong John 3:16` · `!strong G26 in John`"
        )
        return

    # ── Concordance: "!strong G26 in John" — every occurrence within one book ──
    m_concord = re.match(r"^([GH]\d+)\s+in\s+(.+)$", raw, re.IGNORECASE)
    if m_concord:
        await _send_strongs_concordance(ctx, m_concord.group(1).upper(), m_concord.group(2).strip())
        return

    # If it looks like a verse reference (contains "Book Chapter:Verse"),
    # dispatch to the Strong's-tagged comparison.
    if re.search(r"\b\d+:\d+\b", raw):
        async with ctx.typing():
            await _send_compare_ancient_strong(ctx, raw)
        return

    arg = raw.upper().replace(" ", "")

    # Allow user to type "3588" if they want — default to G for ambiguous
    if re.match(r"^\d+$", arg):
        await ctx.send("Please prefix with `G` (Greek NT) or `H` (Hebrew OT): "
                       f"`!strong G{arg}`  or  `!strong H{arg}`")
        return

    if not re.match(r"^[GH]\d+$", arg):
        await ctx.send(f"⚠️ `{arg}` isn't a Strong's number. Try `G3588` or `H7225` — or a verse like `John 3:16`.")
        return

    async with ctx.typing():
        loop = asyncio.get_event_loop()
        entry = await loop.run_in_executor(None, _fetch_strongs_definition, arg)

    if entry is None:
        await ctx.send(f"⚠️ No definition found for **{arg}**.")
        return

    lexeme    = entry.get("lexeme") or entry.get("topic") or arg
    translit  = entry.get("transliteration") or ""
    pron      = entry.get("pronunciation") or ""
    short_def = entry.get("short_definition") or ""
    full_def  = entry.get("definition") or ""

    # Strip any embedded HTML from the long definition.
    # Replace block-level tags with whitespace first so adjacent words don't fuse.
    full_def = re.sub(r"<br\s*/?>", " ", full_def, flags=re.I)
    full_def = re.sub(r"</(p|div|li|ul|ol|tr|td|th|h[1-6])\s*>", " ", full_def, flags=re.I)
    full_def = re.sub(r"<(p|div|li|ul|ol|tr|td|th|h[1-6])\b[^>]*>", " ", full_def, flags=re.I)
    full_def = re.sub(r"<[^>]+>", "", full_def)
    # Collapse the runs of whitespace we just introduced
    full_def = re.sub(r"\s+", " ", full_def).strip()

    is_hebrew = arg.startswith("H")
    src_label = "Brown-Driver-Briggs" if is_hebrew else "Thayer's Greek Lexicon"

    title = f"📚 {arg} — {lexeme}"
    desc_parts = []
    if translit:
        desc_parts.append(f"**Transliteration:** {translit}")
    if pron:
        desc_parts.append(f"**Pronunciation:** {pron}")
    if short_def:
        desc_parts.append(f"**Gloss:** {short_def}")
    base_description = "\n".join(desc_parts) if desc_parts else None

    # Split the full definition into one or more pages of ≤ ~1000 chars each,
    # breaking on sentence boundaries where possible.
    def _paginate_def(text: str, page_size: int = 1000) -> list[str]:
        text = text.strip()
        if not text:
            return []
        if len(text) <= page_size:
            return [text]
        pages: list[str] = []
        remaining = text
        while remaining:
            if len(remaining) <= page_size:
                pages.append(remaining.strip())
                break
            window = remaining[:page_size]
            cut = window.rfind(". ")
            if cut < page_size // 3:  # no good sentence break — fall back to space
                cut = window.rfind(" ")
            if cut <= 0:
                cut = page_size
            pages.append(remaining[:cut + 1].strip())
            remaining = remaining[cut + 1:].lstrip()
        return pages

    pages = _paginate_def(full_def)

    def _build_embed(page_idx: int) -> discord.Embed:
        em = discord.Embed(
            title=title,
            description=base_description,
            color=discord.Color.teal(),
        )
        if pages:
            name = "Definition"
            if len(pages) > 1:
                name = f"Definition (page {page_idx + 1}/{len(pages)})"
            em.add_field(name=name, value=pages[page_idx], inline=False)
        em.set_footer(text=f"{src_label} · via bolls.life")
        return em

    if len(pages) <= 1:
        # Short enough to fit in one embed — no buttons needed.
        await ctx.send(embed=_build_embed(0))
        return

    # Long definition: paginate with prev/next buttons.
    class StrongDefView(discord.ui.View):
        def __init__(self):
            super().__init__(timeout=180)
            self.idx = 0
            self.message: discord.Message | None = None

        @discord.ui.button(emoji="◀", style=discord.ButtonStyle.secondary)
        async def prev(self, interaction: discord.Interaction, button: discord.ui.Button):
            self.idx = (self.idx - 1) % len(pages)
            await interaction.response.edit_message(embed=_build_embed(self.idx), view=self)

        @discord.ui.button(emoji="▶", style=discord.ButtonStyle.secondary)
        async def next(self, interaction: discord.Interaction, button: discord.ui.Button):
            self.idx = (self.idx + 1) % len(pages)
            await interaction.response.edit_message(embed=_build_embed(self.idx), view=self)

        async def on_timeout(self):
            try:
                if self.message is not None:
                    await self.message.edit(view=None)
            except Exception:
                pass

    view = StrongDefView()
    msg = await ctx.send(embed=_build_embed(0), view=view)
    view.message = msg


@bot.tree.command(name="strong", description="Strong's number lookup or verse with Strong's tagging")
@app_commands.describe(query="A Strong's number (G3588 / H7225) or a verse reference (John 3:16)")
async def strong_slash(interaction: discord.Interaction, query: str):
    await interaction.response.defer()
    ctx = await bot.get_context(interaction)
    await cmd_strong(ctx, query=query)


async def _display_compare(ctx, reference: str, results: list, mode: str, page_size: int = 2):
    PAGE = page_size
    pages = [results[i:i+PAGE] for i in range(0, len(results), PAGE)]
    total = len(pages)

    def make_embed(idx: int) -> discord.Embed:
        embed = discord.Embed(
            title=f"📖 {reference} — {mode}",
            color=discord.Color.dark_gold()
        )
        for slug, display, text in pages[idx]:
            if len(text) > 1020:
                text = text[:1017] + "…"
            embed.add_field(name=f"**{slug}** — {display}", value=text, inline=False)
        footer = f"{len(results)} translations · !verse {reference}"
        if total > 1:
            footer = f"Page {idx+1}/{total} · " + footer
        embed.set_footer(text=footer)
        return embed

    # No buttons needed for a single page
    if total == 1:
        await ctx.send(embed=make_embed(0))
        return

    class CompareView(discord.ui.View):
        def __init__(self):
            super().__init__(timeout=180)
            self.idx = 0
            self._update_label()

        def _update_label(self):
            self.page_label.label = f"{self.idx+1}/{total}"

        @discord.ui.button(emoji="◀", style=discord.ButtonStyle.secondary)
        async def prev(self, interaction: discord.Interaction, button: discord.ui.Button):
            self.idx = (self.idx - 1) % total
            self._update_label()
            await interaction.response.edit_message(embed=make_embed(self.idx), view=self)

        @discord.ui.button(style=discord.ButtonStyle.secondary, disabled=True, label="1/1")
        async def page_label(self, interaction: discord.Interaction, button: discord.ui.Button):
            pass

        @discord.ui.button(emoji="▶", style=discord.ButtonStyle.secondary)
        async def next(self, interaction: discord.Interaction, button: discord.ui.Button):
            self.idx = (self.idx + 1) % total
            self._update_label()
            await interaction.response.edit_message(embed=make_embed(self.idx), view=self)

        async def on_timeout(self):
            try:
                await self.message.edit(view=None)
            except Exception:
                pass

    view = CompareView()
    view.message = await ctx.send(embed=make_embed(0), view=view)




# ── !parallel — Bible & classical texts in parallel languages (alias: !poem) ──

LANG_LABEL = {"en": "English", "grc": "Ancient Greek", "lat": "Latin"}
LANG_COLOR = {
    "en":  discord.Color.dark_gold(),
    "grc": discord.Color.teal(),
    "lat": discord.Color.dark_red(),
}


def perseus_parallel(reference: str) -> "tuple[dict, dict] | None":
    """(English, original) for a passage of a Perseus work whose Greek or Latin lines up
    with its translation (perseus_tei.original_for), or None if it isn't one."""
    import perseus_tei
    parsed = lookup._parse_reference(reference)
    if not parsed or len(parsed) != 4:
        return None
    book_raw, chapter, first, last = parsed
    corpus, book = lookup._resolve_book(book_raw)
    if corpus != "classical" or not perseus_tei.has_original(book):
        return None
    chapter = str(chapter)
    verses = lookup._data["classical"].get(book, {}).get(chapter)
    if not verses:
        return None
    first = first if first is not None else min(int(v) for v in verses if v.isdigit())
    last = last or first
    english = lookup.get_verse(f"{book} {chapter}:{first}" + (f"-{last}" if last != first else ""))
    if not english.get("found"):
        return None
    original = perseus_tei.original_for(book, chapter, first, last, verses)
    primary = dict(found=True, reference=english["reference"], lang="en",
                   text=re.sub(r"\*\*\[\d+\]\*\*\s*", "", english["text"]), source=english.get("source", ""))
    if original is None:
        pair = dict(found=False, lang="grc", error="The original isn't available for this passage.")
    else:
        text, lang = original
        pair = dict(found=True, text=text, lang=lang,
                    source=f"{LANG_LABEL[lang]} text, Perseus Digital Library (CC-BY-SA)")
    return primary, pair


@bot.command(name="parallel", aliases=["poem", "po", "par", "classical"])
async def cmd_parallel(ctx, *, reference: str = ""):
    """Look up a Bible verse or classical text in parallel languages. !parallel works for a list."""
    classical = "classical" in guild_traditions(getattr(getattr(ctx, "guild", None), "id", None))
    if not reference or reference.strip().lower() in ("works", "list", "help"):
        embed = discord.Embed(title="📜 Classical Poetry & Prose" if classical else "📜 Parallel texts",
                              description=poem_list_works() if classical else _BIBLE_ONLY_PARALLEL,
                              color=discord.Color.dark_gold())
        await ctx.send(embed=embed)
        return

    ref = reference.strip()
    # Strip -p flag if present (parallel is always on)
    ref = re.sub(r'\s+--?p(?:arallel)?$', '', ref, flags=re.I).strip()

    async with ctx.typing():
        # ── Scripture reference? ───────────────────────────────────────────
        drb = is_drb_reference(ref)
        ref_clean = re.sub(
            r'\s+(drb|drv|dra|dr|douay[-\s]rheims?)\s*$', '', ref, flags=re.I
        ).strip() if drb else ref

        scripture_type = classify_scripture(ref_clean)
        if scripture_type:
            await _send_poem_scripture(ctx, ref_clean, scripture_type, drb)
            return

        # ── Classical poetry reference ─────────────────────────────────────
        if not classical:
            await ctx.send(f"⚠️ Couldn't parse `{ref}`.\nExample: `!parallel John 3:16`")
            return
        spec = parse_poem_ref(ref_clean)
        if spec is None and (both := await asyncio.to_thread(perseus_parallel, ref_clean)):
            await _send_parallel(ctx, *both)           # a Perseus work, with its Greek or Latin
            return
        if spec is None:
            await ctx.send(
                f"⚠️ Couldn't parse `{ref}`.\n"
                f"Examples: `!parallel Il. 6.440` · `!parallel John 3:16` · `!parallel Republic 514a` · `!parallel works`"
            )
            return

        result = poem_lookup(spec)
        if result.get("found") and result.get("pair_spec"):
            pair = lookup_pair(result)
            await _send_parallel(ctx, result, pair)
        else:
            await _send_poem_result(ctx, result)


@bot.tree.command(name="parallel", description="Look up a Bible verse or classical text in parallel languages")
@app_commands.describe(reference="e.g. Il. 6.440  Republic 514a  works",
                       parallel="Show original language alongside")
async def poem_slash(interaction: discord.Interaction,
                     reference: str, parallel: bool = False):
    await interaction.response.defer()
    ctx = await bot.get_context(interaction)
    if reference.strip().lower() in ("works", "list", "help") or "classical" not in guild_traditions(interaction.guild_id):
        await cmd_parallel(ctx, reference=reference)        # (the same answers as the typed command)
        return
    spec = parse_poem_ref(reference.strip())
    ref = reference.strip()
    drb = is_drb_reference(ref)
    ref_clean = re.sub(r'\s+(drb|drv|dra|dr|douay[-\s]rheims?)\s*$', '', ref, flags=re.I).strip() if drb else ref
    scripture_type = classify_scripture(ref_clean)
    if scripture_type:
        await _send_poem_scripture(ctx, ref_clean, scripture_type, drb)
        return
    spec = parse_poem_ref(ref_clean)
    if spec is None and (both := await asyncio.to_thread(perseus_parallel, ref_clean)):
        await _send_parallel(ctx, *both)
        return
    if spec is None:
        await ctx.send(f"⚠️ Couldn't parse `{reference}`.")
        return
    result = poem_lookup(spec)
    if result.get("found") and result.get("pair_spec"):
        pair = lookup_pair(result)
        await _send_parallel(ctx, result, pair)
    else:
        await _send_poem_result(ctx, result)



async def _send_poem_scripture(ctx, reference: str, scripture_type: str, drb: bool):
    """
    Show a scripture verse bilingually.
    KJV mode:  English (KJV) | Hebrew (WLC) for OT
                              | Greek LXX for Apocrypha
                              | Greek TR for NT
    DRB mode:  English (DR)  | Latin (Vulgate) for everything
    """
    if drb:
        slugs = ["DRB", "VULG"]
        labels = {
            "DRB":  "Douay-Rheims Bible",
            "VULG": "Vulgata Clementina (Latin)",
        }
    else:
        if scripture_type == "ot":
            slugs = ["KJV", "WLC"]
            labels = {
                "KJV": "King James Version",
                "WLC": "Hebrew OT (Westminster Leningrad Codex)",
            }
        elif scripture_type == "apocrypha":
            slugs = ["KJV", "LXX"]
            labels = {
                "KJV": "King James Version",
                "LXX": "Septuagint (Brenton)",
            }
        else:  # NT
            slugs = ["KJV", "TR"]
            labels = {
                "KJV": "King James Version",
                "TR":  "Textus Receptus (Greek NT, Elzevir 1624)",
            }

    results = []
    for slug in slugs:
        s, display, text = await _fetch_one_translation(slug, reference)
        results.append((slug, labels.get(slug, display), text))

    embed = discord.Embed(
        title=f"📖 {reference}",
        color=discord.Color.dark_gold()
    )
    for slug, label, text in results:
        if len(text) > 1020:
            text = text[:1017] + "…"
        embed.add_field(name=f"**{slug}** — {label}", value=text, inline=False)

    await ctx.send(embed=embed)


async def _send_poem_result(ctx, result: dict):
    if not result.get("found"):
        embed = discord.Embed(title="❌ Not found",
                              description=result.get("error", "Unknown error"),
                              color=discord.Color.red())
        await ctx.send(embed=embed)
        return

    color = LANG_COLOR.get(result.get("lang", "en"), discord.Color.dark_gold())
    source = result.get("source", "")
    pages  = result.get("pages")

    if not pages:
        text = result["text"]
        if len(text) > 3900:
            text = text[:3897] + "…"
        embed = discord.Embed(title=f"📜 {result['reference']}",
                              description=text, color=color)
        embed.set_footer(text=source)
        await ctx.send(embed=embed)
        return

    total = len(pages)

    def make_embed(idx):
        e = discord.Embed(
            title=f"📜 {result['reference']} ({idx+1}/{total})",
            description=pages[idx], color=color)
        e.set_footer(text=source)
        return e

    class PoemView(discord.ui.View):
        def __init__(self):
            super().__init__(timeout=300)
            self.idx = 0

        @discord.ui.button(emoji="◀", style=discord.ButtonStyle.secondary)
        async def prev(self, interaction, button):
            self.idx = (self.idx - 1) % total
            self.lbl.label = f"{self.idx+1}/{total}"
            await interaction.response.edit_message(embed=make_embed(self.idx), view=self)

        @discord.ui.button(style=discord.ButtonStyle.secondary, disabled=True, label="1/N")
        async def lbl(self, interaction, button):
            pass

        @discord.ui.button(emoji="▶", style=discord.ButtonStyle.secondary)
        async def nxt(self, interaction, button):
            self.idx = (self.idx + 1) % total
            self.lbl.label = f"{self.idx+1}/{total}"
            await interaction.response.edit_message(embed=make_embed(self.idx), view=self)

        async def on_timeout(self):
            try: await self.message.edit(view=None)
            except Exception: pass

    view = PoemView()
    view.lbl.label = f"1/{total}"
    view.message = await ctx.send(embed=make_embed(0), view=view)


async def _send_parallel(ctx, primary: dict, pair: dict):
    """Two-field embed: English on top, original language below."""
    color = LANG_COLOR.get(primary.get("lang", "en"), discord.Color.dark_gold())

    def lang_label(r):
        return LANG_LABEL.get(r.get("lang",""), "")

    embed = discord.Embed(
        title=f"📜 {primary['reference']} — Parallel",
        color=color
    )

    # Primary text
    pt = primary["text"]
    if len(pt) > 1020: pt = pt[:1017] + "…"
    embed.add_field(
        name=f"{lang_label(primary)} — {primary.get('source','')[:60]}",
        value=pt, inline=False
    )

    # Pair text
    if pair.get("found"):
        xt = pair["text"]
        if len(xt) > 1020: xt = xt[:1017] + "…"
        embed.add_field(
            name=f"{lang_label(pair)} — {pair.get('source','')[:60]}",
            value=xt, inline=False
        )
    else:
        err = pair.get("error", "Not available")
        # Only show the field if it's a real error, not just missing build file
        if "build_" not in err and "not found" not in err.lower():
            embed.add_field(
                name=f"{lang_label(pair) or 'Original'} (unavailable)",
                value=f"*{err}*",
                inline=False
            )
        elif "build_" in err or "not found" in err.lower():
            embed.add_field(
                name=f"{lang_label(pair) or 'Original language'} — *pending*",
                value=f"*Run the appropriate build script to enable this.*",
                inline=False
            )

    await ctx.send(embed=embed)
