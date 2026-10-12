"""
Image commands: !card shareable verse images, !interlinear and
!reverseinterlinear word-by-word images, plus !concordance and the Greek
transliteration they use.
"""
import asyncio
import discord
import interlinear_lookup
import re
import unicodedata
from scripture_lookup import BIBLE_NT, BIBLE_OT
from translation_lookup import TRANSLATION_SUFFIXES, get_parallel, get_translation
from discord import app_commands
from strongs_lookup import get_definition as get_local_strongs_definition, search_by_word as strongs_search_by_word
from core import (
    _LAST_CITED,
    bot,
    lookup,
    record_special_stat,
    record_stat,
)
from bot_commands.translations import (
    _bolls_fetch_chapter,
    _fetch_kjv_word_map,
    _fetch_strongs_definition,
    _fetch_strongs_passage,
    _parse_kjv_reverse_interlinear,
)
from core import ROOT
from greek_translit import _transliterate_greek



# ── !card — shareable verse image ─────────────────────────────────────────────────

_SYRIAC_FONT_PATH = str(ROOT / "fonts" / "NotoSansSyriac-Regular.ttf")

def _script_font(fonts_dir: str, text: str) -> str:
    """Pick a font file that can actually render the text's script.
    Georgia has no Hebrew glyphs at all and drops most polytonic Greek
    diacritics (both render as tofu boxes); Times New Roman covers
    Hebrew, full polytonic Greek, and Cyrillic as well as Latin. No
    Windows-bundled font has any Syriac glyphs at all, so Peshitta text
    uses a bundled copy of Noto Sans Syriac (Google, SIL OFL) instead."""
    for ch in text:
        cp = ord(ch)
        if 0x0700 <= cp <= 0x074F:
            return _SYRIAC_FONT_PATH
        if 0x0590 <= cp <= 0x05FF or 0x0370 <= cp <= 0x03FF or 0x1F00 <= cp <= 0x1FFF or 0x0400 <= cp <= 0x04FF:
            return fonts_dir + "times.ttf"
    return fonts_dir + "georgiai.ttf"

def _is_rtl_script(text: str) -> bool:
    """Hebrew or Syriac -- both right-to-left, both need _rtl_visual()."""
    return any(0x0590 <= ord(ch) <= 0x05FF or 0x0700 <= ord(ch) <= 0x074F for ch in text)

def _rtl_clusters(line: str) -> list[str]:
    """Group each base character with any combining marks that follow it
    (e.g. Hebrew niqqud/cantillation) into a cluster, then reverse cluster
    order, so a consonant keeps its vowel points attached instead of them
    ending up on the wrong side. Returns the clusters as a list (visual
    left-to-right draw order) rather than a joined string -- _draw_rtl_line
    needs the boundaries to position each mark on its own base character."""
    clusters, current = [], ""
    for ch in line:
        if unicodedata.combining(ch) and current:
            current += ch
        else:
            if current:
                clusters.append(current)
            current = ch
    if current:
        clusters.append(current)
    return list(reversed(clusters))

def _rtl_visual(line: str) -> str:
    """Approximate correct RTL visual order for a naive left-to-right renderer
    (Pillow has no bidi/shaping engine). String form of _rtl_clusters(),
    safe for draw.textlength()/textwrap width estimates (combining marks
    have zero advance width, so joining clusters doesn't change the total),
    but NOT safe to pass to draw.text() directly -- see _draw_rtl_line."""
    return "".join(_rtl_clusters(line))

def _draw_rtl_line(draw, x: float, y: float, line: str, font, fill) -> float:
    """Draw RTL (Hebrew/Syriac) text left-to-right on screen, cluster by
    cluster, placing each combining mark at the *same* origin as its base
    character instead of PIL's default of advancing the cursor character by
    character. PIL has no text-shaping engine: a zero-advance-width niqqud
    point drawn via plain draw.text() still gets positioned at the cursor
    position reached *after* its base consonant's own advance, so every
    vowel point silently drifts onto the position of the next letter
    instead of stacking on the letter it belongs to. Returns the total
    width drawn (same value draw.textlength on the flattened string would
    give, since marks have zero advance)."""
    cursor = x
    for cluster in _rtl_clusters(line):
        base, marks = cluster[0], cluster[1:]
        draw.text((cursor, y), base, font=font, fill=fill)
        for mark in marks:
            draw.text((cursor, y), mark, font=font, fill=fill)
        cursor += draw.textlength(base, font=font)
    return cursor - x

def _size_for_length(n: int) -> int:
    """Starting font size for the card body text, scaled so a short quote
    (e.g. a single clause) renders noticeably larger than a full chapter,
    rather than every length maxing out at the same size."""
    anchors = [(20, 68), (100, 58), (200, 50), (400, 44), (800, 36), (2000, 26), (4000, 22)]
    if n <= anchors[0][0]:
        return anchors[0][1]
    for (x0, y0), (x1, y1) in zip(anchors, anchors[1:]):
        if x0 <= n <= x1:
            return int(y0 + (n - x0) / (x1 - x0) * (y1 - y0))
    return anchors[-1][1]

# ── Card styles ──────────────────────────────────────────────────────────────
# A card dresses in its tradition: colours, a frame and a small drawn ornament
# (all drawn, never glyphs, so nothing falls back to tofu). "parchment" is the
# original look, kept for the Bible and anything without a style of its own.
CARD_STYLES = {
    "parchment": dict(bg=(245, 239, 224), border=(178, 34, 34), text=(59, 42, 22), accent=(178, 34, 34),
                      frame="single", ornament="diamond"),
    "ink":       dict(bg=(244, 241, 232), border=(40, 40, 40), text=(28, 28, 28), accent=(176, 32, 32),
                      frame="double", ornament="seal"),
    "persian":   dict(bg=(249, 243, 228), border=(28, 62, 118), text=(36, 36, 64), accent=(170, 124, 22),
                      frame="double", ornament="star"),
    "buddhist":  dict(bg=(250, 241, 222), border=(122, 20, 34), text=(62, 30, 20), accent=(205, 120, 10),
                      frame="double", ornament="wheel"),
    "hindu":     dict(bg=(252, 242, 226), border=(196, 84, 8), text=(70, 30, 10), accent=(160, 30, 20),
                      frame="double", ornament="sun"),
    "norse":     dict(bg=(232, 231, 226), border=(48, 58, 70), text=(30, 34, 40), accent=(80, 98, 116),
                      frame="corners", ornament="knot"),
    "classical": dict(bg=(247, 245, 240), border=(128, 102, 58), text=(50, 44, 36), accent=(110, 84, 44),
                      frame="key", ornament="diamond"),
}
_STYLE_BY_CORPUS = {"chinese": "ink", "sufi": "persian", "quran": "persian", "buddhist": "buddhist",
                    "dharmic": "hindu", "norse": "norse", "classical": "classical"}


def style_for_reference(reference: str) -> str:
    """The card style for a reference's book ("Dhammapada 14:183" -> buddhist)."""
    book = re.sub(r"(\s+[\d.:–\-]+[a-e]?)+$", "", reference.strip())
    corpus, _ = lookup._resolve_book(book) if book else (None, None)
    return _STYLE_BY_CORPUS.get(corpus, "parchment")


def _draw_frame(draw, W: int, H: int, s: dict) -> None:
    c = s["border"]
    draw.rectangle([16, 16, W - 17, H - 17], outline=c, width=4)
    if s["frame"] == "double":
        draw.rectangle([28, 28, W - 29, H - 29], outline=c, width=1)
    elif s["frame"] == "corners":
        for x, dx in ((30, 1), (W - 31, -1)):
            for y, dy in ((30, 1), (H - 31, -1)):
                draw.line([(x, y), (x + 60 * dx, y)], fill=c, width=3)
                draw.line([(x, y), (x, y + 60 * dy)], fill=c, width=3)
    elif s["frame"] == "key":                         # a Greek-key band along the top and bottom
        for y0, flip in ((26, 1), (H - 27, -1)):
            for x in range(40, W - 60, 24):
                pts = [(x, y0), (x, y0 + 12 * flip), (x + 16, y0 + 12 * flip), (x + 16, y0 + 4 * flip),
                       (x + 8, y0 + 4 * flip)]
                draw.line(pts, fill=c, width=2)


def _draw_ornament(draw, cx: int, cy: int, s: dict) -> None:
    import math
    c, kind = s["border"], s["ornament"]
    draw.line([(cx - 90, cy), (cx - 16, cy)], fill=c, width=2)
    draw.line([(cx + 16, cy), (cx + 90, cy)], fill=c, width=2)
    if kind == "diamond":
        draw.polygon([(cx, cy - 7), (cx + 7, cy), (cx, cy + 7), (cx - 7, cy)], fill=c)
    elif kind == "seal":                              # a red seal stamp
        a = s["accent"]
        draw.rectangle([cx - 10, cy - 10, cx + 10, cy + 10], fill=a)
        draw.rectangle([cx - 6, cy - 6, cx + 6, cy + 6], outline=s["bg"], width=2)
    elif kind == "star":                              # eight-pointed star
        pts = [(cx + (11 if i % 2 == 0 else 5) * math.cos(i * math.pi / 8),
                cy + (11 if i % 2 == 0 else 5) * math.sin(i * math.pi / 8)) for i in range(16)]
        draw.polygon(pts, fill=s["accent"])
    elif kind == "wheel":                             # dharma wheel
        draw.ellipse([cx - 11, cy - 11, cx + 11, cy + 11], outline=s["accent"], width=2)
        for i in range(8):
            ang = i * math.pi / 4
            draw.line([(cx, cy), (cx + 11 * math.cos(ang), cy + 11 * math.sin(ang))], fill=s["accent"], width=2)
    elif kind == "sun":
        draw.ellipse([cx - 6, cy - 6, cx + 6, cy + 6], fill=s["accent"])
        for i in range(12):
            ang = i * math.pi / 6
            draw.line([(cx + 8 * math.cos(ang), cy + 8 * math.sin(ang)),
                       (cx + 13 * math.cos(ang), cy + 13 * math.sin(ang))], fill=s["accent"], width=2)
    elif kind == "knot":                              # two interlaced squares
        draw.polygon([(cx - 8, cy - 8), (cx + 8, cy - 8), (cx + 8, cy + 8), (cx - 8, cy + 8)], outline=c, width=2)
        draw.polygon([(cx, cy - 11), (cx + 11, cy), (cx, cy + 11), (cx - 11, cy)], outline=c, width=2)


def _render_verse_card(reference: str, text: str, source: str, question: str = "", style: str = ""):
    """Render a verse (or a whole chapter) as a PNG in its tradition's style
    (CARD_STYLES; by default chosen from the reference's book). Runs off the
    event loop (CPU-bound). Height grows to fit the text instead of
    truncating it -- a chapter-length card is just taller.
    `question` (oracle answers): shown in italics above the text."""
    from PIL import Image, ImageDraw, ImageFont
    import io, textwrap

    W = 1200
    s = CARD_STYLES.get(style or style_for_reference(reference), CARD_STYLES["parchment"])
    BG, BORDER, TEXT, ACCENT = s["bg"], s["border"], s["text"], s["accent"]
    FONTS = "C:/Windows/Fonts/"
    TOP_MARGIN, BOTTOM_RESERVED = 60, 200

    question_lines, q_font, q_line_height = [], None, 0
    if question.strip():
        q_font = ImageFont.truetype(FONTS + "georgiai.ttf", 30)
        q_line_height = 40
        question_lines = textwrap.wrap(f"“{question.strip()}”", width=60)[:4]
        TOP_MARGIN = 50 + q_line_height * len(question_lines) + 40
    MAX_CHARS = 4000  # safety cap so a pathological request (e.g. Psalm 119) can't produce a runaway image

    # Strip Discord markdown verse-number markers (e.g. "**[1]** ") and any
    # stray bold asterisks — meaningful in an embed, just noise in a plain image.
    quote_text = re.sub(r"\*\*\[\d+\]\*\*\s*", "", text.strip())
    quote_text = quote_text.replace("**", "").strip()
    if len(quote_text) > MAX_CHARS:
        quote_text = quote_text[:MAX_CHARS - 1] + "…"
    is_rtl = _is_rtl_script(quote_text)
    body_font_path = _script_font(FONTS, quote_text)

    # Each verse (separated by the newlines already in whole-chapter text)
    # wraps as its own paragraph, rather than running every verse together.
    paragraphs = quote_text.split("\n")

    dummy = ImageDraw.Draw(Image.new("RGB", (10, 10)))
    max_width = W - 160
    size, MIN_SIZE = _size_for_length(len(quote_text)), 22
    lines, line_height, font = [], 0, None
    while size >= MIN_SIZE:
        font = ImageFont.truetype(body_font_path, size)
        wrap_width = max(10, int(max_width / (size * 0.52)))
        lines = [l for para in paragraphs for l in (textwrap.wrap(para, width=wrap_width) or [""])]
        line_height = int(size * 1.35)
        widest = max((dummy.textlength(l, font=font) for l in lines), default=0)
        if widest <= max_width:
            break
        size -= 2

    text_height = line_height * len(lines)
    H = max(630, TOP_MARGIN + text_height + BOTTOM_RESERVED)

    img = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(img)
    _draw_frame(draw, W, H, s)

    qy = 50
    for q_line in question_lines:
        q_w = draw.textlength(q_line, font=q_font)
        draw.text(((W - q_w) / 2, qy), q_line, font=q_font, fill=ACCENT)
        qy += q_line_height

    # Center the text block within the space above the divider/reference/source
    # (a no-op once H has grown to exactly fit -- only matters for short verses
    # on the minimum-height canvas, which would otherwise sit flush at the top).
    available = H - TOP_MARGIN - BOTTOM_RESERVED
    y = TOP_MARGIN + max(0, (available - text_height) // 2)
    for line in lines:
        if is_rtl:
            w = draw.textlength(_rtl_visual(line), font=font)
            _draw_rtl_line(draw, (W - w) / 2, y, line, font, TEXT)
        else:
            w = draw.textlength(line, font=font)
            draw.text(((W - w) / 2, y), line, font=font, fill=TEXT)
        y += line_height

    # Small ornamental divider (drawn, not a glyph, so it never falls back to tofu)
    _draw_ornament(draw, W // 2, H - 160, s)

    ref_font = ImageFont.truetype(FONTS + "georgiab.ttf", 34)
    ref_w = draw.textlength(reference, font=ref_font)
    draw.text(((W - ref_w) / 2, H - 130), reference, font=ref_font, fill=ACCENT)

    src_font = ImageFont.truetype(FONTS + "georgia.ttf", 20)
    src_w = draw.textlength(source, font=src_font)
    draw.text(((W - src_w) / 2, H - 80), source, font=src_font, fill=ACCENT)

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf


def _render_compare_card(reference: str, entries: list[tuple[str, str]]):
    """Render up to 4 translations of one verse stacked in a single PNG."""
    from PIL import Image, ImageDraw, ImageFont
    import io, textwrap

    entries = entries[:4]
    n = len(entries)
    W, TOP, BAND_H, BOTTOM = 1200, 110, 165, 40
    H = TOP + BAND_H * n + BOTTOM
    BG, BORDER, TEXT, ACCENT = (245, 239, 224), (178, 34, 34), (59, 42, 22), (178, 34, 34)
    FONTS = "C:/Windows/Fonts/"

    img = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(img)
    draw.rectangle([16, 16, W - 17, H - 17], outline=BORDER, width=4)

    title_font = ImageFont.truetype(FONTS + "georgiab.ttf", 40)
    tw = draw.textlength(reference, font=title_font)
    draw.text(((W - tw) / 2, 38), reference, font=title_font, fill=ACCENT)

    label_font = ImageFont.truetype(FONTS + "georgiab.ttf", 24)
    max_width = W - 140

    y = TOP
    for i, (label, text) in enumerate(entries):
        clean = re.sub(r"\*\*\[\d+\]\*\*\s*", "", text.strip()).replace("**", "")
        if len(clean) > 260:
            clean = clean[:257] + "…"

        draw.text((70, y), label, font=label_font, fill=ACCENT)

        body_font_path = _script_font(FONTS, clean)
        size, lines, line_h, body_font = 28, [clean], 36, None
        while size > 16:
            body_font = ImageFont.truetype(body_font_path, size)
            wrap_width = max(10, int(max_width / (size * 0.52)))
            lines = textwrap.wrap(clean, width=wrap_width) or [clean]
            line_h = int(size * 1.3)
            widest = max((draw.textlength(l, font=body_font) for l in lines), default=0)
            if line_h * len(lines) <= BAND_H - 44 and widest <= max_width:
                break
            size -= 2

        is_rtl = _is_rtl_script(clean)
        ty = y + 34
        for line in lines:
            if is_rtl:
                _draw_rtl_line(draw, 70, ty, line, body_font, TEXT)
            else:
                draw.text((70, ty), line, font=body_font, fill=TEXT)
            ty += line_h

        if i < n - 1:
            draw.line([(70, y + BAND_H - 14), (W - 70, y + BAND_H - 14)], fill=BORDER, width=1)
        y += BAND_H

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf

_STRONGS_INFLECTION_FAMILIES = {}
for _fam in [("G1510", "G1511", "G1498", "G2071", "G2258", "G5600", "G2277")]:
    for _n in _fam:
        _STRONGS_INFLECTION_FAMILIES[_n] = _fam
del _fam, _n
# The original-language (Tischendorf) and KJV (separate SWORD module)
# Strong's tagging don't always agree on which number to use for a given
# inflected form -- e.g. Tischendorf tags every form of "to be" as the
# lemma G1510, but the KJV module tags the imperfect "was" as G2258 (its
# own number per Strong's, confirmed by G2258's own derivation field: "imperfect
# of G1510 (eimi)"). Without this, !interlinear's KJV alignment (see
# cmd_interlinear) silently found no match for G1510 in a verse like John
# 1:1 that says "was" three times, and fell back to the lexicon gloss
# "am" -- accurate for G1510's present-tense sense, flatly wrong in
# context. Only eimi's family is covered since it's by far the most
# frequent case; add another only after confirming via each number's own
# derivation field, not by inference.

_SECONDARY_SENSE_MARKERS = ("concrete",)
# NOTE: this list is deliberately short. "by implication" looked like a
# plausible addition but actively broke G2889 (kosmos) -- its definition is
# "orderly arrangement, i.e. decoration; by implication, the world (...)",
# and excluding the "by implication" clause throws away "world", the
# overwhelmingly common NT sense, leaving only "decoration" behind (which
# doesn't match "adorning" either, so it fell back to the wrong entry
# anyway). These Strong's/Thayer lead-in phrases don't consistently mark a
# *rarer* sense -- only "concrete" has actually been verified to (H367
# eymah: "fright; concrete, an idol (as a bugbear)"). Add another marker
# here only after checking it against a real reported case, not on
# suspicion alone.

def _clean_strongs_gloss(short_def: str, full_def: str = "") -> str:
    """OpenScriptures' short_definition is the *full* list of every KJV
    rendering of a word (e.g. G3588 -> "the, this, that, one, he, she, it,
    etc"), not a single gloss -- displayed as-is under an interlinear word
    it just reads as noise, and picking merely the first non-marker entry
    isn't good enough either: G1520 (heis, "one") gave "a(-n, -ny, certain)",
    G3756 (ou, "not") gave "nay" -- both real KJV renderings, both far less
    recognizable than words later in the same list.

    Splits on top-level commas (respecting parens, so "a(-n, -ny, certain)"
    survives as one unit), drops "+"/"X"-prefixed entries (OpenScriptures'
    notation for a rare/idiomatic rendering), then prefers whichever
    surviving candidate's core word (parentheticals stripped) also appears
    in the fuller `definition` field -- an independent cross-check that
    reliably favors the plain, recognizable word over an archaic or
    idiomatic one. Falls back to the first non-marker entry, unstripped, if
    nothing cross-validates (this matters for cases like theos, whose
    `definition` field is itself a fragment that omits "God" entirely)."""
    if not short_def:
        return ""
    parts, depth, current = [], 0, ""
    for ch in short_def:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth = max(0, depth - 1)
        if ch == "," and depth == 0:
            parts.append(current.strip())
            current = ""
        else:
            current += ch
    if current.strip():
        parts.append(current.strip())
    candidates = [p.rstrip(".").strip() for p in parts if p and not p.startswith("+") and not p.startswith("X ")]
    if not candidates:
        candidates = [p.rstrip(".").strip() for p in parts] or [short_def]

    if full_def:
        # Drop any semicolon-delimited clause that *opens* with a Strong's/
        # Thayer secondary-sense marker -- convention for "this is a rare or
        # derived sense, not the plain gloss" (e.g. H367 eymah's definition
        # is "fright; concrete, an idol (as a bugbear)": without excluding
        # the second clause, "idol" -- a real but secondary sense -- matches
        # a short_definition candidate and wrongly outranks "dread"/"fear").
        clauses = full_def.split(";")
        kept = [c for c in clauses
                if not any(c.strip().lower().startswith(m) for m in _SECONDARY_SENSE_MARKERS)]
        searchable = ";".join(kept)
        for cand in candidates:
            core = re.sub(r"\([^)]*\)", "", cand).strip(" -")
            if len(core) >= 3 and re.search(rf"\b{re.escape(core)}\b", searchable, re.IGNORECASE):
                return core
    return candidates[0]

def _render_interlinear_card(reference: str, original_label: str, is_rtl: bool,
                              cells: list[dict], source: str):
    """Render a word-by-word interlinear grid: original word / [lexeme] /
    transliteration / short gloss, stacked per column, wrapping to new rows
    as needed. Hebrew columns fill each row right-to-left (first word of the
    verse ends up on the right, matching how a printed Hebrew interlinear
    reads); Greek fills left-to-right.

    An optional per-cell "lexeme" key inserts an extra row between the word
    and the transliteration, showing the original-language word in its own
    script -- used by the reverse interlinear (!reverseinterlinear), where
    "word" is the English KJV phrase and is_rtl is always False (English
    reads left-to-right regardless of the source language), so the lexeme
    row needs its own independent RTL check and font per cell."""
    from PIL import Image, ImageDraw, ImageFont
    import io, textwrap

    W = 1300
    BG, BORDER, TEXT, ACCENT, MUTED = (245, 239, 224), (178, 34, 34), (59, 42, 22), (178, 34, 34), (110, 90, 60)
    FONTS = "C:/Windows/Fonts/"
    MARGIN = 60
    COL_GAP, ROW_GAP = 28, 22
    GLOSS_WRAP = 14  # max chars per gloss line before wrapping to a second line

    orig_size, lexeme_size, translit_size, gloss_size, strong_size = 34, 26, 20, 17, 15
    orig_font_path = _script_font(FONTS, "".join(c["word"] for c in cells)) if cells else FONTS + "georgia.ttf"
    orig_font = ImageFont.truetype(orig_font_path, orig_size)
    has_lexeme = any(c.get("lexeme") for c in cells)
    lexeme_font_path = _script_font(FONTS, "".join(c.get("lexeme", "") for c in cells)) if has_lexeme else None
    lexeme_font = ImageFont.truetype(lexeme_font_path, lexeme_size) if lexeme_font_path else None
    # Georgia Italic lacks the macron-vowel characters (ō, ē, etc.) that
    # transliteration schemes use -- Times covers Latin Extended-A as well
    # as the Hebrew/Greek/Cyrillic it's already used for elsewhere.
    translit_font = ImageFont.truetype(FONTS + "timesi.ttf", translit_size)
    gloss_font = ImageFont.truetype(FONTS + "georgia.ttf", gloss_size)
    # Georgia's digits are old-style (varying height/descenders) by default,
    # which reads awkwardly at caption size; Times uses lining (even-height)
    # figures, matching plain "[G2258]"-style reference notation.
    strong_font = ImageFont.truetype(FONTS + "times.ttf", strong_size)

    dummy = ImageDraw.Draw(Image.new("RGB", (10, 10)))

    # Precompute each cell's rendered lines and pixel width.
    laid_out = []
    for c in cells:
        word_logical = c["word"]
        word_width = dummy.textlength(_rtl_visual(word_logical) if is_rtl else word_logical, font=orig_font)
        lexeme_logical = c.get("lexeme", "")
        lexeme_is_rtl = bool(lexeme_logical) and _is_rtl_script(lexeme_logical)
        lexeme_width = (dummy.textlength(_rtl_visual(lexeme_logical) if lexeme_is_rtl else lexeme_logical,
                                          font=lexeme_font) if lexeme_logical else 0)
        translit_lines = [c["translit"]] if c["translit"] else []
        gloss_lines = textwrap.wrap(c["gloss"], width=GLOSS_WRAP)[:2] if c["gloss"] else []
        strong_lines = [c["strong"]] if c.get("strong") else []
        widths = [word_width, lexeme_width]
        widths += [dummy.textlength(l, font=translit_font) for l in translit_lines]
        widths += [dummy.textlength(l, font=gloss_font) for l in gloss_lines]
        widths += [dummy.textlength(l, font=strong_font) for l in strong_lines]
        cell_w = max(widths, default=0)
        cell_h = ((orig_size + 6) + ((lexeme_size + 5) if lexeme_logical else 0)
                  + (translit_size + 4) * len(translit_lines)
                  + (gloss_size + 3) * len(gloss_lines) + (strong_size + 3) * len(strong_lines))
        laid_out.append({"word": word_logical, "word_w": word_width,
                          "lexeme": lexeme_logical, "lexeme_w": lexeme_width, "lexeme_is_rtl": lexeme_is_rtl,
                          "translit": translit_lines,
                          "gloss": gloss_lines, "strong": strong_lines, "w": cell_w, "h": cell_h})

    # Wrap into rows.
    max_row_width = W - 2 * MARGIN
    rows, current_row, current_w = [], [], 0
    for cell in laid_out:
        add_w = cell["w"] + (COL_GAP if current_row else 0)
        if current_row and current_w + add_w > max_row_width:
            rows.append(current_row)
            current_row, current_w = [], 0
            add_w = cell["w"]
        current_row.append(cell)
        current_w += add_w
    if current_row:
        rows.append(current_row)

    row_heights = [max(c["h"] for c in row) for row in rows] if rows else [0]
    TOP, BOTTOM = 110, 90
    H = TOP + sum(row_heights) + ROW_GAP * max(0, len(rows) - 1) + BOTTOM

    img = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(img)
    draw.rectangle([16, 16, W - 17, H - 17], outline=BORDER, width=4)

    title_font = ImageFont.truetype(FONTS + "georgiab.ttf", 36)
    tw = draw.textlength(reference, font=title_font)
    draw.text(((W - tw) / 2, 38), reference, font=title_font, fill=ACCENT)

    y = TOP
    for row, row_h in zip(rows, row_heights):
        row_width = sum(c["w"] for c in row) + COL_GAP * (len(row) - 1)
        x = (W - row_width) / 2
        ordered = list(reversed(row)) if is_rtl else row
        for cell in ordered:
            cw = cell["w"]
            wx = x + (cw - cell["word_w"]) / 2
            if is_rtl:
                _draw_rtl_line(draw, wx, y, cell["word"], orig_font, TEXT)
            else:
                draw.text((wx, y), cell["word"], font=orig_font, fill=TEXT)
            ty = y + orig_size + 6
            if cell["lexeme"]:
                lx = x + (cw - cell["lexeme_w"]) / 2
                if cell["lexeme_is_rtl"]:
                    _draw_rtl_line(draw, lx, ty, cell["lexeme"], lexeme_font, TEXT)
                else:
                    draw.text((lx, ty), cell["lexeme"], font=lexeme_font, fill=TEXT)
                ty += lexeme_size + 5
            for line in cell["translit"]:
                lw = draw.textlength(line, font=translit_font)
                draw.text((x + (cw - lw) / 2, ty), line, font=translit_font, fill=ACCENT)
                ty += translit_size + 4
            for line in cell["gloss"]:
                lw = draw.textlength(line, font=gloss_font)
                draw.text((x + (cw - lw) / 2, ty), line, font=gloss_font, fill=MUTED)
                ty += gloss_size + 3
            for line in cell["strong"]:
                lw = draw.textlength(line, font=strong_font)
                draw.text((x + (cw - lw) / 2, ty), line, font=strong_font, fill=BORDER)
                ty += strong_size + 3
            x += cw + COL_GAP
        y += row_h + ROW_GAP

    label_font = ImageFont.truetype(FONTS + "georgia.ttf", 20)
    lw = draw.textlength(original_label, font=label_font)
    draw.text(((W - lw) / 2, H - 68), original_label, font=label_font, fill=ACCENT)

    src_font = ImageFont.truetype(FONTS + "georgia.ttf", 16)
    sw = draw.textlength(source, font=src_font)
    draw.text(((W - sw) / 2, H - 38), source, font=src_font, fill=MUTED)

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf


@bot.command(name="interlinear", aliases=["inter", "il"])
async def cmd_interlinear(ctx, *, reference: str = ""):
    """Word-by-word interlinear image: original Greek/Hebrew word, transliteration,
    and short gloss stacked under each word. Usage: !interlinear John 3:16
    """
    from poem_lookup import classify_scripture

    ref = reference.strip()
    if not ref:
        await ctx.send("Usage: `!interlinear <verse>` — e.g. `!interlinear John 3:16` or `!interlinear Psalm 23:1`.")
        return

    scripture_type = classify_scripture(ref)
    if scripture_type == "apocrypha":
        await ctx.send("⚠️ Interlinear isn't available for apocryphal books (no Strong's tagging).")
        return
    testament = "nt" if scripture_type == "nt" else "ot"

    ref_single = re.sub(r"(\d+:\d+)[-–]\d+$", r"\1", ref)

    async with ctx.typing():
        loop = asyncio.get_event_loop()
        strongs = await loop.run_in_executor(None, _fetch_strongs_passage, ref_single, testament)

        if not strongs.get("found"):
            await ctx.send(f"⚠️ {strongs.get('error', 'Lookup failed.')}")
            return

        pairs = strongs["pairs"]

        is_rtl = testament == "ot"

        canonical_book = (BIBLE_OT + BIBLE_NT)[strongs["book_id"] - 1]
        local_words = interlinear_lookup.get_verse_words(testament, canonical_book, strongs["chapter"], strongs["verse"])

        cells = []
        if local_words:
            # MACULA (Clear-Bible/Biblica, CC BY 4.0): a real word-aligned
            # interlinear built by linguists, with a per-instance English
            # gloss for each occurrence -- not reconstructed by matching
            # Strong's numbers across two independently-tagged texts (the
            # earlier approach, which broke whenever the two tagging systems
            # disagreed on which number a given inflected form gets).
            for w in local_words:
                translit = w["translit"]
                if not translit and not is_rtl:
                    # MACULA's Greek rows have no per-word transliteration
                    # column (unlike Hebrew's, which has a real one).
                    # Compute it directly from the actual inflected form
                    # shown -- a lexicon lookup by Strong's number would
                    # give the dictionary lemma's transliteration (e.g.
                    # "ho" for ὁ) regardless of which inflected form is
                    # actually on screen (e.g. τὸν, which is "ton").
                    translit = _transliterate_greek(w["text"])
                strong_disp = f"[{w['strong']}]" if w["strong"] else ""
                cells.append({"word": w["text"], "translit": translit, "gloss": w["gloss"], "strong": strong_disp})
            original_label = ("Hebrew OT (WLC, with Strong's)" if is_rtl
                              else "Greek NT (SBLGNT, with Strong's)")
            footer = "MACULA (Clear-Bible/Biblica, Inc., CC BY 4.0) · OpenScriptures Strong's"
        else:
            # MACULA doesn't cover this verse (shouldn't normally happen for
            # a canonical Bible book) -- fall back to the older bolls.life
            # Strong's-tagged text, aligned against the KJV's own tagging by
            # Strong's number where possible.
            if not pairs:
                await ctx.send(f"⚠️ No Strong's-tagged words found for **{ref_single}**.")
                return
            kjv_map = await loop.run_in_executor(
                None, _fetch_kjv_word_map, strongs["book_id"], strongs["chapter"], strongs["verse"]
            )
            for word, num in pairs:
                entry = _fetch_strongs_definition(num)
                translit = (entry or {}).get("transliteration", "") or ""
                candidate_nums = _STRONGS_INFLECTION_FAMILIES.get(num, (num,))
                kjv_word = None
                for cand in candidate_nums:
                    cand_bare = cand[1:]
                    if kjv_map.get(cand_bare):
                        kjv_word = kjv_map[cand_bare].popleft()
                        break
                gloss = kjv_word or _clean_strongs_gloss(
                    (entry or {}).get("short_definition", "") or "", (entry or {}).get("definition", "") or "")
                cells.append({"word": word, "translit": translit, "gloss": gloss, "strong": f"[{num}]"})
            original_label = ("Hebrew OT (WLC, with Strong's)" if is_rtl
                              else "Greek NT (Tischendorf 8th, with Strong's)")
            footer = "bolls.life (KJV + OpenScriptures Strong's)"

        if len(cells) > 60:
            await ctx.send(f"⚠️ That verse has {len(cells)} tagged words — too many for one interlinear image. Try a shorter verse.")
            return

        img_buf = await loop.run_in_executor(
            None, _render_interlinear_card, strongs["ref"], original_label, is_rtl, cells, footer
        )

    record_special_stat(ctx.author.id, "interlinear", strongs["ref"])
    await ctx.send(file=discord.File(img_buf, filename="interlinear.png"))

@bot.tree.command(name="interlinear", description="Word-by-word interlinear image (original word + transliteration + gloss)")
@app_commands.describe(reference="e.g. John 3:16")
async def interlinear_slash(interaction: discord.Interaction, reference: str):
    await interaction.response.defer()
    ctx = await bot.get_context(interaction)
    await cmd_interlinear(ctx, reference=reference)


@bot.command(name="reverseinterlinear", aliases=["rinterlinear", "ril", "kjvinterlinear"])
async def cmd_reverse_interlinear(ctx, *, reference: str = ""):
    """Reverse interlinear image: the actual KJV English text in its own
    reading order, with each word/phrase tagged by the Strong's number of
    the Greek/Hebrew word(s) it translates. Usage: !reverseinterlinear John 3:16
    """
    from poem_lookup import classify_scripture

    ref = reference.strip()
    if not ref:
        await ctx.send("Usage: `!reverseinterlinear <verse>` — e.g. `!reverseinterlinear John 3:16`.")
        return

    scripture_type = classify_scripture(ref)
    if scripture_type == "apocrypha":
        await ctx.send("⚠️ Reverse interlinear isn't available for apocryphal books (no Strong's tagging).")
        return
    testament = "nt" if scripture_type == "nt" else "ot"
    prefix = "G" if testament == "nt" else "H"

    ref_single = re.sub(r"(\d+:\d+)[-–]\d+$", r"\1", ref)

    async with ctx.typing():
        loop = asyncio.get_event_loop()
        strongs = await loop.run_in_executor(None, _fetch_strongs_passage, ref_single, testament)
        if not strongs.get("found"):
            await ctx.send(f"⚠️ {strongs.get('error', 'Lookup failed.')}")
            return

        rows = await loop.run_in_executor(None, _bolls_fetch_chapter, "KJV", strongs["book_id"], strongs["chapter"])
        row = next((v for v in (rows or []) if v.get("verse") == strongs["verse"]), None)
        if not row:
            await ctx.send(f"⚠️ Could not fetch the KJV text for **{strongs['ref']}**.")
            return

        entries = _parse_kjv_reverse_interlinear(row.get("text", ""))
        if not entries:
            await ctx.send(f"⚠️ No Strong's-tagged words found for **{strongs['ref']}**.")
            return

        cells = []
        for e in entries:
            lexeme, translit = "", ""
            if e["strong"]:
                entry = await loop.run_in_executor(None, _fetch_strongs_definition, f"{prefix}{e['strong']}")
                if entry:
                    lexeme = entry.get("lexeme") or ""
                    translit = entry.get("transliteration") or ""
            cells.append({
                "word": e["phrase"], "lexeme": lexeme, "translit": translit, "gloss": "",
                "strong": f"[{prefix}{e['strong']}]" if e["strong"] else "",
            })

        if len(cells) > 60:
            await ctx.send(f"⚠️ That verse has {len(cells)} words — too many for one image. Try a shorter verse.")
            return

        img_buf = await loop.run_in_executor(
            None, _render_interlinear_card, strongs["ref"],
            "King James Version (1769) — reverse interlinear", False, cells,
            "bolls.life (KJV + OpenScriptures Strong's)"
        )

    record_special_stat(ctx.author.id, "reverseinterlinear", strongs["ref"])
    await ctx.send(file=discord.File(img_buf, filename="reverse_interlinear.png"))


@bot.tree.command(name="reverseinterlinear", description="Reverse interlinear image (KJV text in reading order, tagged with Strong's numbers)")
@app_commands.describe(reference="e.g. John 3:16")
async def reverse_interlinear_slash(interaction: discord.Interaction, reference: str):
    await interaction.response.defer()
    ctx = await bot.get_context(interaction)
    await cmd_reverse_interlinear(ctx, reference=reference)


@bot.command(name="concordance", aliases=["occurrences", "conc"])
async def cmd_concordance(ctx, *, arg: str = ""):
    """List every verse tagged with a given Strong's number or word.
    Usage: !concordance G26   |  !concordance H430   |  !concordance agape   |  !concordance love"""
    raw = arg.strip()
    number = raw.upper()
    if not re.match(r"^[GH]\d+[A-Z]?$", number):
        # Not a bare Strong's number -- try resolving it as a word/transliteration
        word = raw.lower()
        matches = strongs_search_by_word(word)
        if not matches:
            await ctx.send(
                f"No Strong's entry matches **{raw}**. Usage: `!concordance G26`, "
                "`!concordance H430`, or a word like `!concordance agape`."
            )
            return
        if len(matches) > 1:
            preview = ", ".join(
                f"{n} ({get_local_strongs_definition(n).get('lexeme', '')})" for n in matches[:10]
            )
            await ctx.send(
                f"**{len(matches)} matches** for **{raw}** — pick one: {preview}"
                + (", …" if len(matches) > 10 else "")
            )
            return
        number = matches[0]

    if not interlinear_lookup.available():
        await ctx.send("⚠️ Interlinear data isn't available right now.")
        return

    rows = interlinear_lookup.get_occurrences(number)
    if not rows:
        await ctx.send(f"No occurrences found for **{number}** in the interlinear dataset.")
        return

    order = {b: i for i, b in enumerate(BIBLE_OT + BIBLE_NT)}
    rows = sorted(rows, key=lambda r: (order.get(r[1], 999), r[2], r[3]))
    refs = [f"{book} {chapter}:{verse}" for _testament, book, chapter, verse in rows]

    entry = get_local_strongs_definition(number)
    header = number
    if entry:
        lex = entry.get("lexeme", "")
        translit = entry.get("transliteration", "")
        gloss = entry.get("short_definition", "")
        header = f"{number} — {lex} ({translit})" if lex else number
        if gloss:
            header += f" — {gloss}"

    PAGE = 20
    total = len(refs)
    pages = [refs[i:i + PAGE] for i in range(0, total, PAGE)]

    def make_embed(idx):
        embed = discord.Embed(
            title=f"🔎 {header}"[:256],
            description="\n".join(pages[idx]),
            color=discord.Color.gold(),
        )
        embed.set_footer(text=f"{total} occurrence{'s' if total != 1 else ''} · page {idx + 1}/{len(pages)} · MACULA (CC BY 4.0)")
        return embed

    if len(pages) == 1:
        await ctx.send(embed=make_embed(0))
        return

    class ConcordanceView(discord.ui.View):
        def __init__(self):
            super().__init__(timeout=180)
            self.idx = 0

        @discord.ui.button(emoji="◀", style=discord.ButtonStyle.secondary)
        async def prev(self, interaction: discord.Interaction, button: discord.ui.Button):
            self.idx = (self.idx - 1) % len(pages)
            await interaction.response.edit_message(embed=make_embed(self.idx), view=self)

        @discord.ui.button(emoji="▶", style=discord.ButtonStyle.secondary)
        async def next(self, interaction: discord.Interaction, button: discord.ui.Button):
            self.idx = (self.idx + 1) % len(pages)
            await interaction.response.edit_message(embed=make_embed(self.idx), view=self)

        async def on_timeout(self):
            try:
                await self.message.edit(view=None)
            except Exception:
                pass

    view = ConcordanceView()
    view.message = await ctx.send(embed=make_embed(0), view=view)


@bot.tree.command(name="concordance", description="List every verse tagged with a given Strong's number")
@app_commands.describe(number="e.g. G26 or H430")
async def concordance_slash(interaction: discord.Interaction, number: str):
    await interaction.response.defer()
    ctx = await bot.get_context(interaction)
    await cmd_concordance(ctx, arg=number)


def _make_card_text_button(reference: str, content_lines: list[str]) -> discord.ui.Button:
    """A button under a !card image that posts the same content as copyable
    plain text (ephemeral, so it doesn't clutter the channel)."""
    btn = discord.ui.Button(label="📋 Text version", style=discord.ButtonStyle.secondary)
    text_block = f"**{reference}**\n" + "\n".join(content_lines)
    if len(text_block) > 1900:
        text_block = text_block[:1897] + "…"

    async def callback(interaction: discord.Interaction):
        await interaction.response.send_message(text_block, ephemeral=True)

    btn.callback = callback
    return btn


@bot.command(name="card", aliases=["versecard", "quotecard"])
async def cmd_card(ctx, *, reference: str = ""):
    """Render a verse as a shareable image.
    Usage: !card John 3:16              — KJV
           !card James 2:19 ESV         — a specific translation
           !card John 3:16 KJV ESV NASB — up to 4 translations compared, stacked
    """
    ref = reference.strip()
    if not ref or ref.lower() == "random":
        result = None
        if not ref:
            cached = _LAST_CITED.get(ctx.channel.id)
            if cached and cached.get("text"):
                result = dict(cached, found=True)
        if result is None:
            result = lookup.random_verse()
        if not result.get("found"):
            await ctx.send(f"⚠️ {result.get('error', 'Verse not found.')}")
            return
        async with ctx.typing():
            loop = asyncio.get_event_loop()
            buf = await loop.run_in_executor(
                None, _render_verse_card, result["reference"], result["text"], result.get("source", "")
            )
        text_view = discord.ui.View(timeout=180)
        text_view.add_item(_make_card_text_button(result["reference"], [result["text"], f"*{result.get('source', '')}*"]))
        await ctx.send(file=discord.File(buf, filename="verse.png"), view=text_view)
        record_stat(ctx.author.id, "card", result)
        return

    tokens = ref.split()
    i = len(tokens) - 1
    trans_list = []
    while i >= 0 and tokens[i].lower() in TRANSLATION_SUFFIXES:
        trans_list.insert(0, tokens[i])
        i -= 1
    base_ref = " ".join(tokens[:i + 1])

    if len(trans_list) >= 2:
        async with ctx.typing():
            result = get_parallel(base_ref, trans_list[:4])
        if not result.get("found"):
            await ctx.send(f"⚠️ {result.get('error', 'Verse not found.')}")
            return
        entries = [(label, text) for _slug, label, text in result["parallel"]]
        async with ctx.typing():
            loop = asyncio.get_event_loop()
            buf = await loop.run_in_executor(None, _render_compare_card, result["reference"], entries)
        text_view = discord.ui.View(timeout=180)
        text_view.add_item(_make_card_text_button(result["reference"], [f"**{label}**\n{text}" for label, text in entries]))
        await ctx.send(file=discord.File(buf, filename="compare.png"), view=text_view)
        record_stat(ctx.author.id, "card", result)
        if len(trans_list) > 4:
            await ctx.send("Comparison cards show up to 4 translations at a time — showing the first 4.")
        return

    if len(trans_list) == 1:
        async with ctx.typing():
            result = get_translation(base_ref, trans_list[0])
    else:
        result = lookup.get_verse(ref)
        if not result.get("found") and "Could not parse" in result.get("error", ""):
            result = lookup.random_verse_from_book(ref)

    if not result.get("found"):
        await ctx.send(f"⚠️ {result.get('error', 'Verse not found.')}")
        return

    async with ctx.typing():
        loop = asyncio.get_event_loop()
        buf = await loop.run_in_executor(
            None, _render_verse_card, result["reference"], result["text"], result.get("source", "")
        )
    text_view = discord.ui.View(timeout=180)
    text_view.add_item(_make_card_text_button(result["reference"], [result["text"], f"*{result.get('source', '')}*"]))
    await ctx.send(file=discord.File(buf, filename="verse.png"), view=text_view)
    record_stat(ctx.author.id, "card", result)

@bot.tree.command(name="card", description="Render a verse as a shareable image")
@app_commands.describe(reference="e.g. John 3:16 (leave blank for a random verse)")
async def card_slash(interaction: discord.Interaction, reference: str = ""):
    await interaction.response.defer()
    ctx = await bot.get_context(interaction)
    await cmd_card(ctx, reference=reference)
