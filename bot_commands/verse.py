"""
!verse / !search, plus !discover and !study.
"""
import discord
from scripture_lookup import BIBLE_APOCRYPHA, BIBLE_NT, BIBLE_OT, DRB_SUFFIXES, KNOX_SUFFIXES, get_verse_drb, get_verse_knox
from translation_lookup import TRANSLATION_SUFFIXES, get_parallel, get_random_verse, get_translation, search_translation
from bot_commands.church import (
    cmd_catena,
)
from core import (
    ANE_BOOKS,
    _build_bolls_search_embed,
    _check_search_cooldown,
    _get_preferred_translation,
    _send_result,
    bot,
    log,
    lookup,
)
from bot_commands.translations import (
    _send_parallel,
)

# ── Prefix command  !verse ─────────────────────────────────────────────────────
@bot.command(name="verse", aliases=["v", "scripture"])
async def verse_prefix(ctx, *, reference: str = ""):
    ref = reference.strip()

    # No reference — fully random verse
    if not ref:
        result = lookup.random_verse()
        log.info(f"RNG  random_verse          → {result.get('reference', '?')} (user: {ctx.author})")
        await _send_result(ctx, result)
        return

    # ── Bible shortcuts ───────────────────────────────────────────────────────
    ref_lc = ref.lower()
    if ref_lc.startswith("bible"):
        sub = ref_lc[5:].strip()
        if sub in ("ot", "old testament", "old"):
            result = lookup.random_verse_from_books(BIBLE_OT)
            log.info(f"RNG  random OT             → {result.get('reference', '?')} (user: {ctx.author})")
            await _send_result(ctx, result)
        elif sub in ("nt", "new testament", "new"):
            result = lookup.random_verse_from_books(BIBLE_NT)
            log.info(f"RNG  random NT             → {result.get('reference', '?')} (user: {ctx.author})")
            await _send_result(ctx, result)
        elif sub in ("apocrypha", "apoc", "deuterocanon", "deuterocanonical"):
            result = lookup.random_verse_from_books(BIBLE_APOCRYPHA)
            log.info(f"RNG  random Apocrypha      → {result.get('reference', '?')} (user: {ctx.author})")
            await _send_result(ctx, result)
        elif sub in ("otnt", "ot nt", "nt ot"):
            # Return one from OT and one from NT
            r1 = lookup.random_verse_from_books(BIBLE_OT)
            r2 = lookup.random_verse_from_books(BIBLE_NT)
            await _send_result(ctx, r1)
            await _send_result(ctx, r2)
        else:
            # Just "Bible" — random from OT + NT + Apocrypha
            result = lookup.random_verse_from_books(BIBLE_OT + BIBLE_NT + BIBLE_APOCRYPHA)
            await _send_result(ctx, result)
        return

    # ── Ancient Near East shortcut ────────────────────────────────────────────
    if ref_lc in ("ancient_near_east", "ancient near east", "ane"):
        result = lookup.random_verse_from_books(ANE_BOOKS)
        log.info(f"RNG  random ANE             → {result.get('reference', '?')} (user: {ctx.author})")
        await _send_result(ctx, result)
        return

    # ── Suffix detection ──────────────────────────────────────────────────────
    parts = ref.rsplit(None, 1)
    suffix = parts[1].lower() if len(parts) == 2 else ""

    if suffix in KNOX_SUFFIXES:
        result = get_verse_knox(parts[0].strip())
        await _send_result(ctx, result)
        return

    if suffix in DRB_SUFFIXES:
        result = get_verse_drb(parts[0].strip())
        await _send_result(ctx, result)
        return

    if suffix in TRANSLATION_SUFFIXES:
        # Check for parallel: multiple translation suffixes at end
        tokens = ref.split()
        trans_list = []
        i = len(tokens) - 1
        while i >= 0 and tokens[i].lower() in TRANSLATION_SUFFIXES:
            trans_list.insert(0, tokens[i])
            i -= 1
        if len(trans_list) >= 2:
            base_ref = " ".join(tokens[:i + 1])
            async with ctx.typing():
                result = get_parallel(base_ref, trans_list)
            await _send_parallel(ctx, result)
            return
        # Bare translation slug → random verse in that translation
        if not parts[0].strip():
            async with ctx.typing():
                result = get_random_verse(suffix)
            await _send_result(ctx, result)
            return
        # Single translation lookup
        async with ctx.typing():
            result = get_translation(parts[0].strip(), parts[1])
        await _send_result(ctx, result)
        return

    # ── Normal local lookup ───────────────────────────────────────────────────
    # If the user set a default translation with !prefer and gave no explicit
    # suffix, try that translation first; fall through to local KJV/other-corpus
    # lookup if it doesn't have this reference (e.g. Enoch, Mishnah, Quran --
    # anything outside the Protestant canon bolls.life translations cover).
    preferred = _get_preferred_translation(ctx.author.id)
    if preferred:
        async with ctx.typing():
            pref_result = get_translation(ref, preferred)
        if pref_result.get("found"):
            await _send_result(ctx, pref_result)
            return

    result = lookup.get_verse(ref)
    if result["found"]:
        await _send_result(ctx, result)
        return

    # If it failed to parse (no chapter:verse) try it as a book name for random verse
    if "Could not parse" in result.get("error", ""):
        result = lookup.random_verse_from_book(ref)
        if result.get("found"):
            log.info(f"RNG  random_verse_from_book({ref}) → {result.get('reference', '?')} (user: {ctx.author})")

    await _send_result(ctx, result)


@bot.command(name="search", aliases=["find"])
async def search_prefix(ctx, *, query: str = ""):
    if not query:
        await ctx.send("Usage: `!search <phrase>` or `!search <phrase> ESV` to search a specific translation.")
        return
    if not _check_search_cooldown(ctx.author.id):
        await ctx.send("⏳ Search is rate-limited — please wait a moment.", delete_after=8)
        return

    # Translation suffix → bolls.life search
    tokens = query.split()
    if len(tokens) >= 2 and tokens[-1].lower() in TRANSLATION_SUFFIXES:
        phrase = " ".join(tokens[:-1])
        trans  = tokens[-1]
        async with ctx.typing():
            data = search_translation(phrase, trans, page=1)
        if not data.get("found") or not data.get("results"):
            await ctx.send(f"No results for **{phrase}** in **{trans.upper()}**.")
            return
        embed, view = _build_bolls_search_embed(phrase, trans, data)
        view.message = await ctx.send(embed=embed, view=view)
        return

    # Local corpus search — show overview first
    async with ctx.typing():
        by_corpus = lookup.search_by_corpus(query)

    if not by_corpus:
        await ctx.send(f"No results found for **{query}**.")
        return

    total_hits = sum(len(hits) for hits in by_corpus.values())
    await _send_search_overview(ctx, query, by_corpus, total_hits)


async def _send_search_overview(ctx, query: str, by_corpus: dict, total_hits: int):
    """
    Send the corpus overview embed with a button per corpus.
    Each button shows that corpus's results paginated.
    """
    embed = discord.Embed(
        title=f'🔍 "{query}" — {total_hits:,} result{"s" if total_hits != 1 else ""}',
        color=discord.Color.gold()
    )
    # One line per corpus: emoji label + count
    lines = []
    corpus_order = sorted(by_corpus.items(), key=lambda x: -len(x[1]))
    for label, hits in corpus_order:
        lines.append(f"{label} — **{len(hits):,}**")
    embed.description = "\n".join(lines)
    embed.set_footer(text="Click a corpus button to browse results · !search <phrase> ESV to search a translation")

    class SearchOverviewView(discord.ui.View):
        def __init__(self):
            super().__init__(timeout=120)
            # Add one button per corpus (max 5 rows × 5 buttons = 25, but we cap at 20)
            for i, (label, hits) in enumerate(corpus_order[:20]):
                # Strip emoji prefix for button label, keep short
                short = label.split(" ", 1)[-1][:40]  # drop the emoji
                btn = discord.ui.Button(
                    label=f"{short} ({len(hits)})",
                    style=discord.ButtonStyle.primary,
                    row=i // 4,
                )
                btn.callback = self._make_callback(label, hits)
                self.add_item(btn)

        def _make_callback(self, label: str, hits: list):
            async def callback(interaction: discord.Interaction):
                e, v = _build_corpus_results_embed(query, label, hits, offset=0)
                v.message = await interaction.response.send_message(embed=e, view=v)
            return callback

        async def on_timeout(self):
            try:
                await self.message.edit(view=None)
            except Exception:
                pass

    view = SearchOverviewView()
    view.message = await ctx.send(embed=embed, view=view)


def _build_corpus_results_embed(query: str, corpus_label: str, hits: list,
                                 offset: int = 0, page_size: int = 5):
    """Paginated results embed for a single corpus."""
    PAGE = page_size
    total = len(hits)
    page_num    = offset // PAGE + 1
    total_pages = max(1, (total + PAGE - 1) // PAGE)
    page_hits   = hits[offset:offset + PAGE]

    embed = discord.Embed(
        title=f'🔍 "{query}" in {corpus_label}',
        color=discord.Color.gold()
    )
    embed.set_footer(text=f"Page {page_num}/{total_pages} · {total} result{'s' if total != 1 else ''}")

    q_lower = query.lower()
    for r in page_hits:
        snippet = r["text"]
        idx = snippet.lower().find(q_lower)
        if idx != -1:
            snippet = (snippet[:idx] + "**" + snippet[idx:idx+len(query)]
                       + "**" + snippet[idx+len(query):])
        if len(snippet) > 300:
            start = max(0, idx - 80) if idx != -1 else 0
            snippet = ("…" if start else "") + snippet[start:start+300] + "…"
        embed.add_field(name=r["reference"], value=snippet, inline=False)

    class CorpusResultsView(discord.ui.View):
        def __init__(self):
            super().__init__(timeout=180)
            self._offset = offset
            if page_num > 1:
                b = discord.ui.Button(label="◀ Prev", style=discord.ButtonStyle.secondary)
                async def prev(interaction: discord.Interaction):
                    new_off = max(0, self._offset - PAGE)
                    e, v = _build_corpus_results_embed(query, corpus_label, hits, new_off, PAGE)
                    v.message = self.message
                    await interaction.response.edit_message(embed=e, view=v)
                b.callback = prev
                self.add_item(b)

            self.add_item(discord.ui.Button(
                label=f"{page_num}/{total_pages}",
                style=discord.ButtonStyle.secondary,
                disabled=True
            ))

            if page_num < total_pages:
                b = discord.ui.Button(label="Next ▶", style=discord.ButtonStyle.secondary)
                async def nxt(interaction: discord.Interaction):
                    new_off = self._offset + PAGE
                    e, v = _build_corpus_results_embed(query, corpus_label, hits, new_off, PAGE)
                    v.message = self.message
                    await interaction.response.edit_message(embed=e, view=v)
                b.callback = nxt
                self.add_item(b)

        async def on_timeout(self):
            try:
                await self.message.edit(view=None)
            except Exception:
                pass

    return embed, CorpusResultsView()


# ── !discover — random passage from any loaded tradition ────────────────────────

@bot.command(name="discover")
async def cmd_discover(ctx):
    """Random passage from any loaded tradition — scripture, patristics, classical texts, and more."""
    result = lookup.random_verse()
    log.info(f"RNG  discover               → {result.get('reference', '?')} (user: {ctx.author})")
    await _send_result(ctx, result)


# ── !study — verse lookup + patristic commentary in one command ─────────────────

@bot.command(name="study")
async def cmd_study(ctx, *, reference: str = ""):
    """Look up a verse and its patristic commentary together. Usage: !study John 3:16"""
    ref = reference.strip()
    if not ref:
        await ctx.send("Usage: `!study <reference>` — e.g. `!study John 3:16`")
        return
    await verse_prefix(ctx, reference=ref)
    await cmd_catena(ctx, reference=ref)
