"""
Study references: !xref, !quoted, !root, !topic, !dictionary, !timeline,
!notes.
"""
import asyncio
import discord
import re
from net_notes_lookup import NET_COPYRIGHT, NOTE_KINDS, get_net_notes
from bible_dictionary_lookup import SOURCE_NAMES as DICTIONARY_SOURCE_NAMES, entry_count as dictionary_entry_count, get_definition as get_dictionary_entry, search_terms as search_dictionary_terms
from discord import app_commands
from xref_lookup import get_cross_references
from strongs_lookup import get_definition as get_local_strongs_definition, get_root_family as strongs_get_root_family, search_by_word as strongs_search_by_word
from topics_lookup import get_topic, search_topics, topic_count
from timeline_lookup import search_timeline, entry_count as timeline_entry_count, year_range as timeline_year_range
from core import (
    bot,
    lookup,
    record_special_stat,
)

# ── !xref — cross-references (Treasury of Scripture Knowledge) ──────────────────

@bot.command(name="xref", aliases=["crossref", "crossreference", "xrefs"])
async def cmd_xref(ctx, *, reference: str = ""):
    """Cross-references for a verse, from the Treasury of Scripture Knowledge.
    Usage: !xref John 3:16
    """
    ref = reference.strip()
    if not ref:
        await ctx.send("Usage: `!xref <reference>` — e.g. `!xref John 3:16`")
        return

    result = lookup.get_verse(ref)
    if not result.get("found"):
        await ctx.send(f"⚠️ {result.get('error', 'Verse not found.')}")
        return

    canon_ref = result["reference"]
    xrefs = get_cross_references(canon_ref)
    if not xrefs:
        await ctx.send(f"No cross-references found for **{canon_ref}** — the dataset only covers the 66-book Protestant canon.")
        return

    SHOWN = 15
    lines = [f"`{i + 1}.` **{r}**" for i, (r, _votes) in enumerate(xrefs[:SHOWN])]
    embed = discord.Embed(
        title=f"🔗 Cross-references — {canon_ref}",
        description="\n".join(lines),
        color=discord.Color.dark_gold(),
    )
    footer = f"Showing {min(SHOWN, len(xrefs))} of {len(xrefs)}" if len(xrefs) > SHOWN else f"{len(xrefs)} reference(s)"
    embed.set_footer(text=f"{footer} · Treasury of Scripture Knowledge, via openbible.info (CC-BY)")
    record_special_stat(ctx.author.id, "xref", canon_ref)
    await ctx.send(embed=embed)

@bot.tree.command(name="xref", description="Cross-references for a verse (Treasury of Scripture Knowledge)")
@app_commands.describe(reference="e.g. John 3:16")
async def xref_slash(interaction: discord.Interaction, reference: str):
    await interaction.response.defer()
    ctx = await bot.get_context(interaction)
    await cmd_xref(ctx, reference=reference)


# ── !quoted — OT passages directly quoted in the NT, and vice versa ────────────
# A curated set of well-established direct quotations (not just thematic
# cross-references, which !xref already covers far more exhaustively via
# the Treasury of Scripture Knowledge). Deliberately not exhaustive --
# scholarly lists of OT-in-NT quotations run to 250-350+ entries depending
# on how loosely "quotation" is counted; this covers the passages virtually
# every source agrees are direct quotations, not the full list.
_OT_NT_QUOTATIONS: list[tuple[str, str]] = [
    ("Genesis 2:24", "Matthew 19:5"),
    ("Genesis 2:24", "Ephesians 5:31"),
    ("Genesis 15:6", "Romans 4:3"),
    ("Genesis 15:6", "Galatians 3:6"),
    ("Genesis 15:6", "James 2:23"),
    ("Genesis 21:12", "Romans 9:7"),
    ("Exodus 20:12-16", "Matthew 19:18-19"),
    ("Exodus 20:13-17", "Romans 13:9"),
    ("Leviticus 19:18", "Matthew 22:39"),
    ("Leviticus 19:18", "Romans 13:9"),
    ("Leviticus 19:18", "Galatians 5:14"),
    ("Leviticus 19:18", "James 2:8"),
    ("Deuteronomy 6:4-5", "Mark 12:29-30"),
    ("Deuteronomy 6:13", "Matthew 4:10"),
    ("Deuteronomy 6:16", "Matthew 4:7"),
    ("Deuteronomy 8:3", "Matthew 4:4"),
    ("Deuteronomy 25:4", "1 Corinthians 9:9"),
    ("Deuteronomy 25:4", "1 Timothy 5:18"),
    ("Deuteronomy 32:35", "Romans 12:19"),
    ("Deuteronomy 32:43", "Hebrews 1:6"),
    ("Psalms 2:7", "Acts 13:33"),
    ("Psalms 2:7", "Hebrews 1:5"),
    ("Psalms 8:4-6", "Hebrews 2:6-8"),
    ("Psalms 16:8-11", "Acts 2:25-28"),
    ("Psalms 22:1", "Matthew 27:46"),
    ("Psalms 22:1", "Mark 15:34"),
    ("Psalms 22:18", "John 19:24"),
    ("Psalms 24:1", "1 Corinthians 10:26"),
    ("Psalms 34:20", "John 19:36"),
    ("Psalms 40:6-8", "Hebrews 10:5-7"),
    ("Psalms 41:9", "John 13:18"),
    ("Psalms 45:6-7", "Hebrews 1:8-9"),
    ("Psalms 68:18", "Ephesians 4:8"),
    ("Psalms 69:9", "John 2:17"),
    ("Psalms 69:9", "Romans 15:3"),
    ("Psalms 69:25", "Acts 1:20"),
    ("Psalms 78:2", "Matthew 13:35"),
    ("Psalms 82:6", "John 10:34"),
    ("Psalms 91:11-12", "Matthew 4:6"),
    ("Psalms 95:7-11", "Hebrews 3:7-11"),
    ("Psalms 102:25-27", "Hebrews 1:10-12"),
    ("Psalms 104:4", "Hebrews 1:7"),
    ("Psalms 109:8", "Acts 1:20"),
    ("Psalms 110:1", "Matthew 22:44"),
    ("Psalms 110:1", "Acts 2:34-35"),
    ("Psalms 110:1", "Hebrews 1:13"),
    ("Psalms 110:4", "Hebrews 5:6"),
    ("Psalms 118:22-23", "Matthew 21:42"),
    ("Psalms 118:22", "Acts 4:11"),
    ("Psalms 118:22", "1 Peter 2:7"),
    ("Psalms 118:25-26", "Matthew 21:9"),
    ("Isaiah 6:9-10", "Matthew 13:14-15"),
    ("Isaiah 6:9-10", "John 12:40"),
    ("Isaiah 6:9-10", "Acts 28:26-27"),
    ("Isaiah 7:14", "Matthew 1:23"),
    ("Isaiah 9:1-2", "Matthew 4:15-16"),
    ("Isaiah 29:13", "Matthew 15:8-9"),
    ("Isaiah 40:3-5", "Matthew 3:3"),
    ("Isaiah 40:3-5", "Luke 3:4-6"),
    ("Isaiah 42:1-4", "Matthew 12:18-21"),
    ("Isaiah 53:1", "John 12:38"),
    ("Isaiah 53:1", "Romans 10:16"),
    ("Isaiah 53:4", "Matthew 8:17"),
    ("Isaiah 53:5-6", "1 Peter 2:24-25"),
    ("Isaiah 53:7-8", "Acts 8:32-33"),
    ("Isaiah 53:9", "1 Peter 2:22"),
    ("Isaiah 53:12", "Luke 22:37"),
    ("Isaiah 54:13", "John 6:45"),
    ("Isaiah 61:1-2", "Luke 4:18-19"),
    ("Isaiah 62:11", "Matthew 21:5"),
    ("Jeremiah 31:15", "Matthew 2:18"),
    ("Jeremiah 31:31-34", "Hebrews 8:8-12"),
    ("Hosea 6:6", "Matthew 9:13"),
    ("Hosea 11:1", "Matthew 2:15"),
    ("Joel 2:28-32", "Acts 2:17-21"),
    ("Amos 5:25-27", "Acts 7:42-43"),
    ("Amos 9:11-12", "Acts 15:16-17"),
    ("Micah 5:2", "Matthew 2:6"),
    ("Habakkuk 1:5", "Acts 13:41"),
    ("Habakkuk 2:4", "Romans 1:17"),
    ("Habakkuk 2:4", "Galatians 3:11"),
    ("Habakkuk 2:4", "Hebrews 10:38"),
    ("Zechariah 9:9", "Matthew 21:5"),
    ("Zechariah 9:9", "John 12:15"),
    ("Zechariah 11:12-13", "Matthew 27:9-10"),
    ("Zechariah 12:10", "John 19:37"),
    ("Zechariah 13:7", "Matthew 26:31"),
    ("Malachi 3:1", "Mark 1:2"),
    ("Malachi 4:5-6", "Matthew 11:14"),
]


def _quotation_norm(ref: str) -> tuple[str, int, int, int]:
    """('Book', chapter, verse_start, verse_end) for range-overlap matching."""
    m = re.match(r"^(.*?)\s+(\d+):(\d+)(?:-(\d+))?$", ref.strip())
    if not m:
        return (ref.strip(), 0, 0, 0)
    book, chap, v1, v2 = m.group(1), int(m.group(2)), int(m.group(3)), m.group(4)
    return (book, chap, v1, int(v2) if v2 else v1)


def _quotation_overlaps(a: str, b: str) -> bool:
    ba, ca, s1, e1 = _quotation_norm(a)
    bb, cb, s2, e2 = _quotation_norm(b)
    return ba == bb and ca == cb and s1 <= e2 and s2 <= e1


# NT passages that quote or closely echo non-canonical Second Temple/early
# Jewish literature already loaded in this bot (charles corpus), rather than
# the Old Testament. Distinct epistemic status per entry, noted explicitly:
#   "quotation"     -- the NT text verbally quotes the source, extant and
#                       checkable (verified directly against the loaded text).
#   "referenced"     -- a NT verse alludes to an episode ancient sources
#                       (e.g. Origen) attribute to this work, but the
#                       specific portion hasn't survived to quote.
#   "close parallel" -- a real, often-cited literary/thematic parallel, not
#                       a verbatim quotation.
_NT_APOCRYPHA_QUOTATIONS: list[tuple[str, str, str]] = [
    ("Jude 1:14-15", "Book of Enoch 1:9",
     "Direct quotation -- explicitly attributed to \"Enoch, the seventh from Adam\" (Jude 1:14)."),
    ("Jude 1:9", "Assumption of Moses",
     "Referenced, not extant -- early sources (e.g. Origen) attribute the Michael/devil dispute over "
     "Moses' body to this work, but that portion is lost from the surviving text."),
    ("2 Corinthians 11:14", "Apocalypse of Moses 17",
     "Close parallel, not a verbatim quotation -- both describe Satan disguising himself as an angel of light."),
    ("Hebrews 11:37", "Ascension of Isaiah 5",
     "Close parallel -- \"were sawn asunder\" alludes to this work's account of Isaiah's martyrdom, "
     "sawn in half by order of Manasseh."),
    ("2 Peter 2:4", "Book of Enoch 10:4",
     "Close parallel, not a verbatim quotation -- both describe rebellious angels bound in darkness "
     "awaiting judgment (this work's Watchers narrative)."),
    ("Jude 1:6", "Book of Enoch 10:4",
     "Close parallel, not a verbatim quotation -- both describe rebellious angels bound in darkness "
     "awaiting judgment (this work's Watchers narrative)."),
]


def _apocrypha_ref_matches(query_ref: str, table_ref: str) -> bool:
    """table_ref may be "Book Ch:V[-V2]", bare "Book Ch", or just "Book"
    (used when no specific extant passage exists to cite)."""
    qb, qc, qs, qe = _quotation_norm(query_ref)
    m_full = re.match(r"^(.*?)\s+(\d+):(\d+)(?:-(\d+))?$", table_ref.strip())
    if m_full:
        tb, tc, ts, te = m_full.group(1), int(m_full.group(2)), int(m_full.group(3)), m_full.group(4)
        te = int(te) if te else ts
        return qb == tb and qc == tc and qs <= te and ts <= qe
    m_chap = re.match(r"^(.*?)\s+(\d+)$", table_ref.strip())
    if m_chap:
        return qb == m_chap.group(1) and qc == int(m_chap.group(2))
    return qb == table_ref.strip()


@bot.command(name="quoted", aliases=["otnt", "quotedin"])
async def cmd_quoted(ctx, *, reference: str = ""):
    """Old Testament <-> New Testament quotations involving a verse, plus NT
    quotations of / close parallels with non-canonical works (Enoch, the
    Ascension of Isaiah, etc.), each labelled with its evidential status.
    A curated, non-exhaustive set -- see !xref for the much larger general
    cross-reference dataset.
    Usage: !quoted Isaiah 53:5   |   !quoted Matthew 1:23"""
    ref = reference.strip()
    if not ref:
        await ctx.send("Usage: `!quoted <reference>` — e.g. `!quoted Isaiah 53:5` or `!quoted Matthew 1:23`")
        return

    result = lookup.get_verse(ref)
    if not result.get("found"):
        await ctx.send(f"⚠️ {result.get('error', 'Verse not found.')}")
        return
    canon_ref = result["reference"]

    matches = [
        (ot, nt, "") for ot, nt in _OT_NT_QUOTATIONS
        if _quotation_overlaps(canon_ref, ot) or _quotation_overlaps(canon_ref, nt)
    ]
    matches += [
        (nt, apoc, note) for nt, apoc, note in _NT_APOCRYPHA_QUOTATIONS
        if _apocrypha_ref_matches(canon_ref, nt) or _apocrypha_ref_matches(canon_ref, apoc)
    ]
    if not matches:
        await ctx.send(
            f"No direct quotation pair on record for **{canon_ref}** in this curated set. "
            f"Try `!xref {canon_ref}` for the full cross-reference dataset."
        )
        return

    SHOWN = 6
    embed = discord.Embed(title=f"📖 Quotations — {canon_ref}", color=discord.Color.dark_gold())
    for side_a, side_b, note in matches[:SHOWN]:
        for side_ref in (side_a, side_b):
            side_result = lookup.get_verse(side_ref)
            if side_result.get("found"):
                text = side_result["text"]
                if len(text) > 1000:
                    text = text[:997] + "…"
            else:
                text = "*Not extant / not found locally.*"
            embed.add_field(name=side_ref, value=text, inline=False)
        if note:
            embed.add_field(name="​", value=f"*{note}*", inline=False)
    footer = "Curated set of well-established quotations and parallels, not exhaustive"
    if len(matches) > SHOWN:
        footer = f"Showing {SHOWN} of {len(matches)} pairs · {footer}"
    embed.set_footer(text=footer)
    await ctx.send(embed=embed)


@bot.tree.command(name="quoted", description="OT <-> NT quotations, and NT parallels with Enoch and other works, for a verse")
@app_commands.describe(reference="e.g. Isaiah 53:5")
async def quoted_slash(interaction: discord.Interaction, reference: str):
    await interaction.response.defer()
    ctx = await bot.get_context(interaction)
    await cmd_quoted(ctx, reference=reference)


# ── !root — Hebrew/Greek root word and its direct derivatives ───────────────────

@bot.command(name="root", aliases=["cognates"])
async def cmd_root(ctx, *, arg: str = ""):
    """Show a Strong's word's root and every word directly derived from it
    (one generation, not the full cognate tree), per the dictionary's own
    derivation notes.
    Usage: !root H6   |  !root G26   |  !root love"""
    raw = arg.strip()
    if not raw:
        await ctx.send("Usage: `!root H6`, `!root G26`, or `!root <word>` — e.g. `!root abad`")
        return

    number = raw.upper()
    if not re.match(r"^[GH]\d+[A-Z]?$", number):
        matches = strongs_search_by_word(raw.lower())
        if not matches:
            await ctx.send(f"No Strong's entry matches **{raw}**.")
            return
        if len(matches) > 1:
            preview = ", ".join(
                f"{n} ({get_local_strongs_definition(n).get('lexeme', '')})" for n in matches[:10]
            )
            await ctx.send(f"**{len(matches)} matches** for **{raw}** — pick one: {preview}")
            return
        number = matches[0]

    entry = get_local_strongs_definition(number)
    if not entry:
        await ctx.send(f"**{number}** isn't in the local Strong's dictionary.")
        return

    root, family = strongs_get_root_family(number)
    root_entry = get_local_strongs_definition(root) or {}

    embed = discord.Embed(
        title=f"🌳 Root: {root} — {root_entry.get('lexeme', '')} ({root_entry.get('transliteration', '')})",
        description=root_entry.get("short_definition", "") or root_entry.get("definition", "")[:300],
        color=discord.Color.dark_gold(),
    )
    if root != number:
        embed.add_field(name="You looked up", value=f"{number} — {entry.get('lexeme', '')} ({entry.get('transliteration', '')})", inline=False)

    if family:
        lines = []
        for n in sorted(family, key=lambda x: int(re.sub(r"\D", "", x) or 0))[:25]:
            e = get_local_strongs_definition(n) or {}
            lines.append(f"**{n}** {e.get('lexeme', '')} ({e.get('transliteration', '')}) — {e.get('short_definition', '')}")
        embed.add_field(
            name=f"Direct derivatives ({len(family)})",
            value="\n".join(lines)[:1024],
            inline=False,
        )
    else:
        embed.add_field(name="Direct derivatives", value="*None on record.*", inline=False)
    embed.set_footer(text="One generation of direct derivatives only, per the dictionary's own derivation notes — not the full cognate tree · OpenScriptures Strong's (CC-BY-SA)")
    await ctx.send(embed=embed)


@bot.tree.command(name="root", description="Show a Strong's word's root and its direct derivatives")
@app_commands.describe(word="e.g. H6, G26, or a word like love")
async def root_slash(interaction: discord.Interaction, word: str):
    await interaction.response.defer()
    ctx = await bot.get_context(interaction)
    await cmd_root(ctx, arg=word)


# ── !topic — Nave's Topical Bible ────────────────────────────────────────────────

def _topic_display_name(subject: str) -> str:
    """Title-case a Nave's subject without str.title()'s apostrophe bug
    (e.g. "LORD'S PRAYER" -> "Lord'S Prayer")."""
    return " ".join(w[:1] + w[1:].lower() if w else w for w in subject.split(" "))

def _paginate_topic_entry(entry: str, page_size: int = 900) -> list[str]:
    """Pack whole lines into ~page_size-char pages -- never splits a line
    mid-citation-list the way a fixed-size character chunker would. Nave's
    entries are bullet outlines, so even a "short" 3000-char entry is a wall
    of text as a single embed; this keeps each page to a comfortable read."""
    lines = entry.split("\n")
    pages, current = [], ""
    for line in lines:
        candidate = f"{current}\n{line}" if current else line
        if len(candidate) > page_size and current:
            pages.append(current)
            current = line
        else:
            current = candidate
    if current:
        pages.append(current)
    return pages or [""]

@bot.command(name="topic", aliases=["naves", "topical"])
async def cmd_topic(ctx, *, query: str = ""):
    """Browse scripture by subject, from Nave's Topical Bible (1897, public domain).
    Usage: !topic love
    """
    q = query.strip()
    if not q:
        await ctx.send(f"Usage: `!topic <subject>` — e.g. `!topic love`. {topic_count()} subjects available.")
        return

    result = get_topic(q)
    if not result:
        suggestions = search_topics(q)
        if not suggestions:
            await ctx.send(f"No topic found for **{q}**, and nothing similar either.")
            return
        lines = "\n".join(f"• {_topic_display_name(s)}" for s in suggestions)
        await ctx.send(f"No exact topic **{q}**. Did you mean:\n{lines}")
        return

    subject, entry = result
    display = _topic_display_name(subject)
    pages = _paginate_topic_entry(entry)
    total = len(pages)

    def make_embed(idx):
        embed = discord.Embed(
            title=f"📚 {display}" if total == 1 else f"📚 {display} ({idx + 1}/{total})",
            description=pages[idx],
            color=discord.Color.dark_gold(),
        )
        embed.set_footer(text="Nave's Topical Bible (1897, public domain)")
        return embed

    record_special_stat(ctx.author.id, "topic", subject)

    if total == 1:
        await ctx.send(embed=make_embed(0))
        return

    class TopicView(discord.ui.View):
        def __init__(self):
            super().__init__(timeout=120)
            self.idx = 0

        @discord.ui.button(emoji="◀", style=discord.ButtonStyle.secondary)
        async def prev(self, interaction: discord.Interaction, button: discord.ui.Button):
            self.idx = (self.idx - 1) % total
            await interaction.response.edit_message(embed=make_embed(self.idx), view=self)

        @discord.ui.button(emoji="▶", style=discord.ButtonStyle.secondary)
        async def next(self, interaction: discord.Interaction, button: discord.ui.Button):
            self.idx = (self.idx + 1) % total
            await interaction.response.edit_message(embed=make_embed(self.idx), view=self)

        async def on_timeout(self):
            try:
                await self.message.edit(view=None)
            except Exception:
                pass

    view = TopicView()
    view.message = await ctx.send(embed=make_embed(0), view=view)

@bot.tree.command(name="topic", description="Browse scripture by subject (Nave's Topical Bible)")
@app_commands.describe(query="e.g. love, prayer, forgiveness")
async def topic_slash(interaction: discord.Interaction, query: str):
    await interaction.response.defer()
    ctx = await bot.get_context(interaction)
    await cmd_topic(ctx, query=query)


# ── !notes — NET Bible translators' notes ─────────────────────────────────────────

_SUPERSCRIPT_DIGITS = str.maketrans("0123456789", "⁰¹²³⁴⁵⁶⁷⁸⁹")


def _superscript(n: int) -> str:
    return str(n).translate(_SUPERSCRIPT_DIGITS)


def _split_at_sentence(text: str, size: int) -> tuple[str, str]:
    """(head, tail) with len(head) <= size, cut after a sentence when one
    ends in the back half of the window, else hard at `size`."""
    cut = max(text.rfind(". ", 0, size), text.rfind("; ", 0, size))
    cut = cut + 1 if cut > size // 2 else size
    return text[:cut].rstrip(), text[cut:].lstrip()


def _paginate_blocks(blocks: list[str], limit: int = 3800) -> list[str]:
    """Pack text blocks into pages of at most `limit` chars (embed descriptions
    allow 4096), separated by blank lines. A block longer than a page -- a few
    NET notes run to 4,000+ chars -- fills the rest of the current page and
    continues ("…") on the next, breaking at sentence ends."""
    pages, current = [], ""
    for block in blocks:
        while block:
            sep = "\n\n" if current else ""
            room = limit - len(current) - len(sep)
            if len(block) <= room:
                current += sep + block
                break
            if len(block) <= limit or room < limit // 4:
                # fits on a fresh page, or too little room left here to start it
                pages.append(current)
                current = ""
                continue
            head, tail = _split_at_sentence(block, room)
            pages.append(current + sep + head)
            current = ""
            block = "…" + tail if tail else ""
    if current or not pages:
        pages.append(current)
    return pages


@bot.command(name="notes", aliases=["netnotes", "netnote"])
async def cmd_notes(ctx, *, reference: str = ""):
    """The NET Bible's translators' notes for a verse: translation choices,
    study notes, and text-critical notes.
    Usage: !notes John 3:16   |   !notes Genesis 1:1-3   (up to 5 verses)"""
    ref = reference.strip()
    if not ref:
        await ctx.send("Usage: `!notes <verse>` — e.g. `!notes John 3:16` or `!notes Genesis 1:1-3`")
        return

    async with ctx.typing():
        result = await asyncio.to_thread(get_net_notes, ref)
    if not result.get("found"):
        await ctx.send(f"⚠️ {result['error']}")
        return

    multi = len(result["verses"]) > 1
    blocks, number = [], 0
    for verse in result["verses"]:
        first = number + 1
        if verse["segments"]:
            # interleave superscript note numbers where the NET places them
            segs = verse["segments"]
            text = segs[0] + "".join(_superscript(first + i) + seg for i, seg in enumerate(segs[1:]))
        else:
            text = verse["text"]
        lines = [f"**[{verse['verse']}]** *{text}*" if multi else f"*{text}*"]
        if not verse["notes"] and verse.get("marker_count"):
            lines.append(f"*The NET has {verse['marker_count']} note(s) on this verse, but the notes "
                         f"source is missing them — see [netbible.org]({result['url']}).*")
        elif not verse["notes"]:
            lines.append("*No notes on this verse.*")
        elif verse.get("marker_count", 0) > len(verse["notes"]):
            lines.append(f"*(The NET marks {verse['marker_count']} notes on this verse; only "
                         f"{len(verse['notes'])} could be retrieved, so where they attach can't be "
                         f"shown — full notes at [netbible.org]({result['url']}).)*")
        elif not verse["segments"]:
            lines.append("*(Where each note attaches isn't available for this verse.)*")
        blocks.append("\n".join(lines))
        for note in verse["notes"]:
            number += 1
            head = f"**{_superscript(number)} {note['anchor']}**" if note["anchor"] else f"**Note {number}**"
            body = "\n".join(f"*{NOTE_KINDS.get(kind, 'Note')}:* {txt}" for kind, txt in note["parts"])
            blocks.append(f"{head}\n{body}")
    pages = _paginate_blocks(blocks)
    total = len(pages)

    def make_embed(idx):
        title = f"📝 NET Notes — {result['reference']}"
        embed = discord.Embed(
            title=title if total == 1 else f"{title} ({idx + 1}/{total})",
            url=result["url"],
            description=pages[idx],
            color=discord.Color.dark_gold(),
        )
        embed.set_footer(text=NET_COPYRIGHT)
        return embed

    record_special_stat(ctx.author.id, "notes", result["reference"])

    if total == 1:
        await ctx.send(embed=make_embed(0))
        return

    class NotesView(discord.ui.View):
        def __init__(self):
            super().__init__(timeout=180)
            self.idx = 0

        @discord.ui.button(emoji="◀", style=discord.ButtonStyle.secondary)
        async def prev(self, interaction: discord.Interaction, button: discord.ui.Button):
            self.idx = (self.idx - 1) % total
            await interaction.response.edit_message(embed=make_embed(self.idx), view=self)

        @discord.ui.button(emoji="▶", style=discord.ButtonStyle.secondary)
        async def next(self, interaction: discord.Interaction, button: discord.ui.Button):
            self.idx = (self.idx + 1) % total
            await interaction.response.edit_message(embed=make_embed(self.idx), view=self)

        async def on_timeout(self):
            try:
                await self.message.edit(view=None)
            except Exception:
                pass

    view = NotesView()
    view.message = await ctx.send(embed=make_embed(0), view=view)


@bot.tree.command(name="notes", description="The NET Bible's translators' notes for a verse")
@app_commands.describe(reference="e.g. John 3:16 or Genesis 1:1-3")
async def notes_slash(interaction: discord.Interaction, reference: str):
    await interaction.response.defer()
    ctx = await bot.get_context(interaction)
    await cmd_notes(ctx, reference=reference)


# ── !dictionary — Easton's + Smith's Bible Dictionary ────────────────────────────

def _paginate_dictionary_entry(text: str, page_size: int = 900) -> list[str]:
    """Same whole-line packing as Nave's topics -- avoids splitting mid-sentence."""
    lines = text.split("\n")
    pages, current = [], ""
    for line in lines:
        candidate = f"{current}\n{line}" if current else line
        if len(candidate) > page_size and current:
            pages.append(current)
            current = line
        else:
            current = candidate
    if current:
        pages.append(current)
    return pages or [""]

@bot.command(name="dictionary", aliases=["dict", "define"])
async def cmd_dictionary(ctx, *, term: str = ""):
    """Look up a person, place, or term in Easton's (1897) or Smith's (1863)
    Bible Dictionary. Usage: !dictionary Aaron
    """
    q = term.strip()
    if not q:
        await ctx.send(f"Usage: `!dictionary <term>` — e.g. `!dictionary Aaron`. {dictionary_entry_count()} terms available.")
        return

    entry = get_dictionary_entry(q)
    if not entry:
        suggestions = search_dictionary_terms(q)
        if not suggestions:
            await ctx.send(f"No dictionary entry found for **{q}**, and nothing similar either.")
            return
        lines = "\n".join(f"• {s}" for s in suggestions)
        await ctx.send(f"No exact entry for **{q}**. Did you mean:\n{lines}")
        return

    name = entry["name"]
    sources_used = entry.get("sources") or [d["source"] for d in entry["definitions"]]
    body = "\n\n".join(
        f"**{DICTIONARY_SOURCE_NAMES.get(d['source'], d['source'])}**\n{d['text']}"
        for d in entry["definitions"]
    )
    pages = _paginate_dictionary_entry(body)
    total = len(pages)

    def make_embed(idx):
        embed = discord.Embed(
            title=f"📔 {name}" if total == 1 else f"📔 {name} ({idx + 1}/{total})",
            description=pages[idx],
            color=discord.Color.dark_gold(),
        )
        embed.set_footer(text=" · ".join(DICTIONARY_SOURCE_NAMES.get(s, s) for s in sources_used))
        return embed

    record_special_stat(ctx.author.id, "dictionary", name)

    if total == 1:
        await ctx.send(embed=make_embed(0))
        return

    class DictionaryView(discord.ui.View):
        def __init__(self):
            super().__init__(timeout=120)
            self.idx = 0

        @discord.ui.button(emoji="◀", style=discord.ButtonStyle.secondary)
        async def prev(self, interaction: discord.Interaction, button: discord.ui.Button):
            self.idx = (self.idx - 1) % total
            await interaction.response.edit_message(embed=make_embed(self.idx), view=self)

        @discord.ui.button(emoji="▶", style=discord.ButtonStyle.secondary)
        async def next(self, interaction: discord.Interaction, button: discord.ui.Button):
            self.idx = (self.idx + 1) % total
            await interaction.response.edit_message(embed=make_embed(self.idx), view=self)

        async def on_timeout(self):
            try:
                await self.message.edit(view=None)
            except Exception:
                pass

    view = DictionaryView()
    view.message = await ctx.send(embed=make_embed(0), view=view)

@bot.tree.command(name="dictionary", description="Look up a person, place, or term (Easton's / Smith's Bible Dictionary)")
@app_commands.describe(term="e.g. Aaron, Jericho, Sabbath")
async def dictionary_slash(interaction: discord.Interaction, term: str):
    await interaction.response.defer()
    ctx = await bot.get_context(interaction)
    await cmd_dictionary(ctx, term=term)


# ── !timeline — Ussher's Annals of the World ─────────────────────────────────────

@bot.command(name="timeline", aliases=["chronology"])
async def cmd_timeline(ctx, *, query: str = ""):
    """Chronological placement of a book, person, or event, from James
    Ussher's Annals of the World (1658, public domain).
    Usage: !timeline Abraham
    """
    q = query.strip()
    if not q:
        lo, hi = timeline_year_range()
        await ctx.send(f"Usage: `!timeline <book, person, or event>` — e.g. `!timeline Abraham`. "
                        f"{timeline_entry_count()} dated entries, {lo} to {hi}.")
        return

    window = search_timeline(q)
    if not window:
        await ctx.send(f"No timeline entry mentions **{q}**. Try a Bible book, a name, or an event like `flood` or `exodus`.")
        return

    lines = []
    for e in window:
        text = e["text"]
        if len(text) > 400:
            text = text[:397] + "…"
        marker = "**→ " if e.get("_matched") else ""
        end_marker = " ←**" if e.get("_matched") else ""
        epoch_suffix = f" ({e['epoch']})" if e.get("epoch") and e is window[0] else ""
        lines.append(f"{marker}`{e['year_display']}`{epoch_suffix}{end_marker}\n{text}")

    embed = discord.Embed(
        title=f"🗓️ Timeline — {q}",
        description="\n\n".join(lines),
        color=discord.Color.dark_gold(),
    )
    embed.set_footer(text="James Ussher, Annals of the World (1658, public domain) · dates per Ussher's own chronology")
    record_special_stat(ctx.author.id, "timeline", q)
    await ctx.send(embed=embed)

@bot.tree.command(name="timeline", description="Chronological placement of a book, person, or event (Ussher's Annals of the World)")
@app_commands.describe(query="e.g. Abraham, exodus, flood")
async def timeline_slash(interaction: discord.Interaction, query: str):
    await interaction.response.defer()
    ctx = await bot.get_context(interaction)
    await cmd_timeline(ctx, query=query)
