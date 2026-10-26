"""
!gematria, !virgil / !homer / !delphi, !oracle, !sortesbiblicae.
"""
import asyncio
import discord
import random
import re
from scripture_lookup import BIBLE_NT, BIBLE_OT
from bot_commands.card import (
    _render_verse_card,
)
from bot_commands.verse import (
    _study_buttons,
    passage_buttons,
)
from discord.ext import commands, tasks
from core import (
    command_enabled,
    _load_guild_config,
    _update_guild_config,
    bot,
    log,
    lookup,
    record_special_stat,
    tradition_enabled,
)
from core import ROOT

VIRGIL_SOURCE = "trans. John Dryden (1697)"
HOMER_SOURCE = "PMG VII"
DELPHI_SOURCE = "trans. Melissa Gold"
_ORACULAR_BOOKS = {   # !oracle's pool: book -> (source, stats prefix)
    "Delphic Maxims":      (DELPHI_SOURCE, "Delphi 1"),
    "Oracular Statements": ("Oracular Statements from Delphi", "Delphi 2"),
    "Chaldaean Oracles":   ("Chaldaean Oracles — ed. Westcott", "Chaldaean Oracles"),
    "Golden Verses":       ("Golden Verses of Pythagoras", "GVP"),
}


# ── The asker's question ──────────────────────────────────────────────────────
# Oracles take an optional question (`!virgil will I find work?`). It used to
# be ignored; now it heads the answer -- in the embed's author line -- so the
# answer makes sense when shared, and the Card button reads it back from there
# (button IDs are capped at 100 chars, too short to carry it).

_QUESTION_PREFIX = "❓ "


def _record(ctx, kind: str, ref: str) -> None:
    """Usage stats for an oracle draw -- except the scheduled daily oracle,
    which nobody asked for (see _DailyContext)."""
    if not getattr(ctx, "is_daily", False):
        record_special_stat(ctx.author.id, kind, ref)


def _ask(embed: discord.Embed, question: str) -> discord.Embed:
    q = (question or "").strip()
    if q:
        embed.set_author(name=(_QUESTION_PREFIX + q)[:256])
    return embed


def _question_from(message) -> str:
    try:
        name = message.embeds[0].author.name or ""
    except (AttributeError, IndexError):
        return ""
    return name[len(_QUESTION_PREFIX):] if name.startswith(_QUESTION_PREFIX) else ""


# ── 🖼️ Card button under oracle answers ───────────────────────────────────────
# (Oracles are the bot's most used commands, and !card its most used image.)

def _oracle_card_content(kind: str, key: str) -> "tuple[str, str, str] | None":
    """(title, text, source) of an oracle answer, looked up again from the
    data by the key its Card button carries -- or None if it's gone."""
    if kind == "virgil":                       # key "6.851": book.line
        book, _, line = key.partition(".")
        text = ((_load_aeneid() or {}).get(book) or {}).get(line)
        return (f"Sortes Vergilianae — Aeneid {key}", text, VIRGIL_SOURCE) if text else None
    if kind == "homer":                        # key "1-2-3": the dice
        text = (_load_homer() or {}).get(key.replace("-", ""))
        return (f"Homeromanteion — {key}", text, HOMER_SOURCE) if text else None
    if kind == "hafez":                        # key: poem number; the card shows its opening stanza
        stanza = _hafiz_poems().get(key, {}).get("1")
        return (f"Fāl-e Hāfez — Poem {key}", stanza, HAFIZ_SOURCE) if stanza else None
    if kind == "rumi":                         # key "1.5:3": book.story:passage
        parts = _rumi_parts(key)
        return (f"The Masnavi — {parts[0]}", parts[1], RUMI_SOURCE) if parts else None
    if kind == "iching":                       # key "3:15": hexagram, changing lines
        n, _, moving = key.partition(":")
        texts = _iching_texts(n)
        if not texts:
            return None
        parts = [texts["1"].removeprefix("The Judgment: ")] + [texts[str(int(m) + 2)] for m in moving]
        h = _iching_meta()[n]
        return (f"I Ching — {n}. {h['name']} ({h['english']})", "\n\n".join(parts), ICHING_SOURCE)
    if kind == "bard":                         # key "Hamlet|3.1|64": a sonnet whole, a play's first speech
        book, chap, line = (key.split("|") + ["", ""])[:3]
        text = _shakespeare().get(book, {}).get(chap, {}).get(line)
        if not text:
            return None
        if book == SONNETS or chap == "1" and set(_shakespeare()[book]) == {"1"}:
            return (_sonnet_title(book, chap, line), _plain(text), SHAKESPEARE_SOURCE)
        return (f"{book} — {_scene_name(chap)}", _plain(_first_speech(_play_text(book, chap, line))),
                SHAKESPEARE_SOURCE)
    if kind == "delphi":                       # key: maxim number
        book, num = "Delphic Maxims", key
    elif kind == "oracle" and "|" in key:      # key "Chaldaean Oracles|12"
        book, num = key.split("|", 1)
    else:
        return None
    text = (lookup._data.get("classical", {}).get(book, {}).get(num) or {}).get("1")
    if not text:
        return None
    if kind == "delphi":
        return (f"Delphic Maxim {num}", text, DELPHI_SOURCE)
    return (f"{book} — {num}", text, _ORACULAR_BOOKS.get(book, (book,))[0])


class OracleCardButton(discord.ui.DynamicItem[discord.ui.Button],
                       template=r"ocard:(?P<kind>virgil|homer|delphi|oracle|iching|hafez|rumi|bard):(?P<key>.+)"):
    """Renders an oracle answer as a !card-style image. Like the study
    buttons, its custom_id carries what it needs, so it keeps working after a
    restart; only ever sent in timeout=None views (see verse.StudyButton)."""

    def __init__(self, kind: str, key: str, disabled: bool = False):
        super().__init__(discord.ui.Button(label="Card", emoji="🖼️", style=discord.ButtonStyle.secondary,
                                           custom_id=f"ocard:{kind}:{key}", disabled=disabled))
        self.kind, self.key = kind, key

    @classmethod
    async def from_custom_id(cls, interaction, item, match):
        return cls(match["kind"], match["key"])

    async def callback(self, interaction: discord.Interaction):
        # One image per answer; the edit is also the interaction's response
        await interaction.response.edit_message(view=_card_view(self.kind, self.key, disabled=True))
        content = _oracle_card_content(self.kind, self.key)
        if content is None:
            await interaction.followup.send("⚠️ I can't find that answer's text any more.", ephemeral=True)
            return
        question = _question_from(interaction.message)
        style = {"iching": "ink", "hafez": "persian", "rumi": "persian"}.get(self.kind, "classical")
        buf = await asyncio.to_thread(_render_verse_card, *content, question, style)
        await interaction.followup.send(file=discord.File(buf, filename="oracle.png"))


bot.add_dynamic_items(OracleCardButton)


def _card_view(kind: str, key: str, disabled: bool = False) -> discord.ui.View:
    view = discord.ui.View(timeout=None)
    view.add_item(OracleCardButton(kind, key, disabled))
    return view

# ── !gematria — Gematria lookup via gematrix.org ─────────────────────────────

_gematria_cooldowns: dict[int, list] = {}  # user_id → [timestamps]

@bot.command(name="gematria", aliases=["gem", "gematrix"])
async def cmd_gematria(ctx, *, query: str = ""):
    """Look up gematria values. Usage: !gematria love  or  !gematria 666"""
    import urllib.request, urllib.parse
    import html as html_mod

    if not query:
        await ctx.send("Usage: `!gematria <word or phrase or number>`")
        return

    encoded = urllib.parse.quote_plus(query.strip())
    url = f"https://www.gematrix.org/?word={encoded}"

    async with ctx.typing():
        try:
            req = urllib.request.Request(
                url,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                    "Accept": "text/html",
                }
            )
            with (await asyncio.to_thread(urllib.request.urlopen, req, timeout=15)) as r:
                raw = r.read().decode("utf-8")
        except Exception as e:
            await ctx.send(f"⚠️ Could not reach gematrix.org: {e}")
            return

    # ── Parse the results table ───────────────────────────────────────────────
    # Each row: word | jewish | english | simple | searches
    row_re = re.compile(
        r'<tr[^>]*>.*?'
        r'<td[^>]*><a[^>]*>([^<]+)</a></td>'   # word
        r'\s*<td[^>]*><a[^>]*>(\d+)</a></td>'  # jewish
        r'\s*<td[^>]*><a[^>]*>(\d+)</a></td>'  # english
        r'\s*<td[^>]*><a[^>]*>(\d+)</a></td>'  # simple
        r'\s*<td[^>]*>(\d+)</td>',              # searches (ignored)
        re.DOTALL
    )
    rows = row_re.findall(raw)

    # Fallback: find computed values for the phrase itself
    computed = {}
    for cipher in ["Jewish", "English", "Simple"]:
        vm = re.search(rf'in {cipher} Gematria equals (\d+)', raw, re.IGNORECASE)
        if vm:
            computed[cipher.lower()] = vm.group(1)

    if not rows and not computed:
        await ctx.send(f"⚠️ No gematria results found for **{query}**.\nTry: <{url}>")
        return

    # ── Format as compact list ────────────────────────────────────────────────
    label = query.strip()

    def fmt_row(word, jewish, english, simple):
        values = f"{jewish:<8} {english:<8} {simple}"
        if len(word) <= 32:
            return f"{word:<32} {values}"
        else:
            return f"{word}\n{'':32} {values}"

    header  = f"{'Word':<32} {'Jew.':<8} {'Eng.':<8} {'Smp.'}"
    divider = "─" * 56
    lines   = [header, divider]
    lines   = [header, divider]

    top_jewish = top_english = top_simple = None

    for i, (word, jewish, english, simple, _) in enumerate(rows[:10]):
        word = html_mod.unescape(word).strip()
        lines.append(fmt_row(word, jewish, english, simple))
        if i == 0:
            top_jewish, top_english, top_simple = jewish, english, simple

    if not rows and computed:
        lines.append(fmt_row(
            label,
            computed.get('jewish', '?'),
            computed.get('english', '?'),
            computed.get('simple', '?')
        ))
        top_jewish  = computed.get("jewish")
        top_english = computed.get("english")
        top_simple  = computed.get("simple")

    table = "```\n" + "\n".join(lines) + "\n```"
    count = len(rows)

    embed = discord.Embed(
        title=f"🔢 Gematria — {label}",
        description=table,
        color=discord.Color.purple(),
        url=url
    )
    embed.set_footer(text=f"{min(count, 10)} of {count} results — gematrix.org")

    # ── Buttons: click to search by that value ────────────────────────────────
    class GematriaButton(discord.ui.Button):
        def __init__(self, label, value, style):
            super().__init__(label=label, style=style)
            self.value = value

        async def callback(self, interaction: discord.Interaction):
            import time
            now = time.monotonic()
            user_id = interaction.user.id

            # Rate limit: max 3 clicks per 10 seconds per user
            history = _gematria_cooldowns.setdefault(user_id, [])
            # Prune entries older than 10 seconds
            _gematria_cooldowns[user_id] = [t for t in history if now - t < 10]
            if len(_gematria_cooldowns[user_id]) >= 3:
                await interaction.response.send_message(
                    "🛑 Slow down! You can only search 3 times per 10 seconds.",
                    ephemeral=True
                )
                return

            _gematria_cooldowns[user_id].append(now)
            await interaction.response.defer(ephemeral=True)

            encoded = urllib.parse.quote_plus(self.value)
            url = f"https://www.gematrix.org/?word={encoded}"
            try:
                req = urllib.request.Request(
                    url,
                    headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
                )
                with (await asyncio.to_thread(urllib.request.urlopen, req, timeout=15)) as r:
                    raw2 = r.read().decode("utf-8")
            except Exception as e:
                await interaction.followup.send(f"⚠️ Could not reach gematrix.org: {e}", ephemeral=True)
                return

            rows2 = row_re.findall(raw2)
            computed2 = {}
            for cipher in ["Jewish", "English", "Simple"]:
                vm = re.search(rf'in {cipher} Gematria equals (\d+)', raw2, re.IGNORECASE)
                if vm:
                    computed2[cipher.lower()] = vm.group(1)

            if not rows2 and not computed2:
                await interaction.followup.send(f"⚠️ No results for **{self.value}**.", ephemeral=True)
                return

            lines2 = [header, divider]
            for i, (word, jewish, english, simple, _) in enumerate(rows2[:10]):
                word = html_mod.unescape(word).strip()
                lines2.append(fmt_row(word, jewish, english, simple))

            if not rows2 and computed2:
                lines2.append(fmt_row(
                    self.value,
                    computed2.get('jewish', '?'),
                    computed2.get('english', '?'),
                    computed2.get('simple', '?')
                ))

            count2 = len(rows2)
            table2 = "```\n" + "\n".join(lines2) + "\n```"
            embed2 = discord.Embed(
                title=f"🔢 Gematria — {self.value}",
                description=table2,
                color=discord.Color.purple(),
                url=url
            )
            embed2.set_footer(text=f"{min(count2, 10)} of {count2} results — gematrix.org")
            await interaction.followup.send(embed=embed2, ephemeral=True)

    class GematriaView(discord.ui.View):
        def __init__(self):
            super().__init__(timeout=120)
            seen = set()
            styles = [
                discord.ButtonStyle.primary,
                discord.ButtonStyle.secondary,
                discord.ButtonStyle.success,
            ]
            pairs = [
                (f"Jewish {top_jewish}", top_jewish),
                (f"English {top_english}", top_english),
                (f"Simple {top_simple}", top_simple),
            ]
            for (lbl, val), style in zip(pairs, styles):
                if val and val not in seen:
                    self.add_item(GematriaButton(lbl, val, style))
                    seen.add(val)

    await ctx.send(embed=embed, view=GematriaView())


# ── !virgil — Sortes Vergilianae ──────────────────────────────────────────────

_AENEID_DATA = None

def _load_aeneid():
    global _AENEID_DATA
    if _AENEID_DATA is None:
        import json
        path = ROOT / "data" / "classical" / "aeneid.json"
        if path.exists():
            _AENEID_DATA = json.loads(path.read_text(encoding="utf-8"))["books"]["Aeneid"]
    return _AENEID_DATA

@bot.command(name="virgil", aliases=["sortesvir", "aeneid"])
async def cmd_virgil(ctx, *, question: str = ""):
    """Consult the Sortes Vergilianae. Usage: !virgil [optional question]"""
    aeneid = _load_aeneid()
    if aeneid is None:
        await ctx.send("⚠️ Aeneid data not found. Run `build_data.py` step 20.")
        return

    # Pick a random book then a random line within it
    book_num = str(random.randint(1, 12))
    lines = aeneid.get(book_num, {})
    if not lines:
        await ctx.send("⚠️ No lines found for that book.")
        return

    line_num = random.randint(1, len(lines))
    verse_text = lines.get(str(line_num), "")

    # Visual: 📖 {book} 🕯️ {line} 👈
    display = f"📖 {book_num}  🕯️ {line_num}  👈"

    embed = discord.Embed(
        title="Sortes Vergilianae",
        description=f"{display}\n\n*{verse_text}*",
        color=discord.Color.dark_gold()
    )
    embed.set_footer(text=VIRGIL_SOURCE)
    _ask(embed, question)
    _record(ctx, "virgil", f"Aeneid {book_num}.{line_num}")
    await ctx.send(embed=embed, view=_card_view("virgil", f"{book_num}.{line_num}"))


_HOMER_DATA = None

def _load_homer():
    global _HOMER_DATA
    if _HOMER_DATA is None:
        import json
        path = ROOT / "data" / "classical" / "homeromanteion.json"
        if path.exists():
            _HOMER_DATA = json.loads(path.read_text(encoding="utf-8"))["oracle"]
    return _HOMER_DATA

@bot.command(name="homer", aliases=["homeromanteion", "sortes"])
async def cmd_homer(ctx, *, question: str = ""):
    """Roll three dice and receive a Homeric oracle. Usage: !homer"""
    d1, d2, d3 = random.randint(1,6), random.randint(1,6), random.randint(1,6)
    log.info(f"RNG  divination dice        → {d1},{d2},{d3} (user: {ctx.author})")
    roll_str = f"{d1}-{d2}-{d3}"
    key = f"{d1}{d2}{d3}"

    oracle = _load_homer()
    if oracle is None:
        await ctx.send("⚠️ Homeromanteion data not found.")
        return

    text = oracle.get(key)
    dice_display = f"🎲 {d1}  🎲 {d2}  🎲 {d3}"

    if text is None:
        embed = discord.Embed(
            title=f"The Oracle is Silent  ({roll_str})",
            description=f"{dice_display}\n\n*The papyrus is blank for this combination. The gods withhold their answer.*",
            color=discord.Color.dark_gray()
        )
    else:
        embed = discord.Embed(
            title=f"Homeromanteion  ({roll_str})",
            description=f"{dice_display}\n\n*{text}*",
            color=discord.Color.blurple()
        )
    embed.set_footer(text="Sortes Homericae — PMG VII, Oxford Classical Text translations")
    _ask(embed, question)
    _record(ctx, "homer", roll_str)
    if text is None:
        await ctx.send(embed=embed)   # the oracle is silent: nothing to put on a card
    else:
        await ctx.send(embed=embed, view=_card_view("homer", roll_str))


@bot.command(name="delphi")
async def cmd_delphi(ctx, *, question: str = ""):
    """Return a random Delphic maxim. Usage: !delphi [optional question]"""
    maxims = lookup._data.get("classical", {}).get("Delphic Maxims", {})
    if not maxims:
        await ctx.send("Delphic Maxims data not found. Have you run `build_data.py`?")
        return
    num, chap = random.choice(list(maxims.items()))
    log.info(f"RNG  maxims                 → Maxim {num} (user: {ctx.author})")
    text = chap.get("1", "")
    embed = discord.Embed(
        title=f"Delphic Maxim {num}",
        description=text,
        color=discord.Color.gold()
    )
    embed.set_footer(text=DELPHI_SOURCE)
    _ask(embed, question)
    _record(ctx, "delphi", f"Maxim {num}")
    await ctx.send(embed=embed, view=_card_view("delphi", num))


# ── !oracle — random verse from any oracular corpus ───────────────────────────

@bot.command(name="oracle")
async def cmd_oracle(ctx, *, question: str = ""):
    """Return a random verse from any oracular corpus. Usage: !oracle"""
    classical = lookup._data.get("classical", {})
    pool = []
    for book, (source, ref_prefix) in _ORACULAR_BOOKS.items():
        for num, chap in classical.get(book, {}).items():
            text = chap.get("1", "")
            if text:
                pool.append((book, num, text, source, ref_prefix))

    if not pool:
        await ctx.send("No oracular data found. Have you run `build_data.py`?")
        return

    book, num, text, source, ref_prefix = random.choice(pool)
    log.info(f"RNG  sortes                 → {ref_prefix} {num} [{source}] (user: {ctx.author})")

    if len(text) > 1800:
        text = text[:1797] + "…"
    embed = discord.Embed(
        title=f"{book} — {num}",
        description=text,
        color=discord.Color.dark_purple()
    )
    embed.set_footer(text=source)
    _ask(embed, question)
    _record(ctx, "oracle", f"{ref_prefix} {num}")
    await ctx.send(embed=embed, view=_card_view("oracle", f"{book}|{num}"))


# ── !sortesbiblicae — the Bible opened at random ──────────────────────────────

@bot.command(name="sortesbiblicae", aliases=["bibliomancy", "biblicae"])
async def cmd_sortes_biblicae(ctx, *, question: str = ""):
    """Sortes Biblicae: open the Bible at random and read the verse your eye
    falls on -- the old practice of bibliomancy. Usage: !sortesbiblicae [optional question]"""
    result = lookup.random_verse_from_books(BIBLE_OT + BIBLE_NT)
    if not result.get("found"):
        await ctx.send(f"⚠️ {result.get('error', 'Could not open the Bible.')}")
        return
    log.info(f"RNG  sortes biblicae        → {result['reference']} (user: {ctx.author})")

    chapter_verse = f"{result['chapter']}:{result['verse']}"
    embed = discord.Embed(
        title="Sortes Biblicae",
        description=f"📖 {result['book']}  🕯️ {chapter_verse}  👈\n\n*{result['text']}*",
        color=discord.Color.dark_gold(),
    )
    embed.set_footer(text=f"{result['reference']} — {result.get('source', 'King James Version')}")
    _ask(embed, question)
    _record(ctx, "sortesbiblicae", result["reference"])

    # It's a Bible verse, so it gets the same study buttons as !verse (Card
    # included) -- persistent buttons, so the view must never time out
    view = discord.ui.View(timeout=None)
    for b in _study_buttons(result):
        view.add_item(b)
    await ctx.send(embed=embed, view=view)


@bot.tree.command(name="sortesbiblicae", description="Open the Bible at random (Sortes Biblicae)")
async def sortes_biblicae_slash(interaction: discord.Interaction, question: str = ""):
    await interaction.response.defer()
    ctx = await bot.get_context(interaction)
    await cmd_sortes_biblicae(ctx, question=question)


# ── !iching — cast a hexagram ─────────────────────────────────────────────────
# The three-coin method: each line is three coins, heads 3 and tails 2, so
# 6 (old yin), 7 (young yang), 8 (young yin) or 9 (old yang). Old lines are
# "changing": their texts are read, and they flip to give a second hexagram.
# Lines are built from the bottom up. Text: Legge (SBE 16, 1882).

ICHING_SOURCE = "trans. James Legge (1882)"
_ICHING_META = None


def _iching_meta() -> dict:
    """{"1": {"name", "chinese", "english", "lines": [bottom..top, 1 = yang]}, ...}"""
    global _ICHING_META
    if _ICHING_META is None:
        import json
        path = ROOT / "data" / "chinese" / "iching_hexagrams.json"
        _ICHING_META = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    return _ICHING_META


def cast_lines(rng=random) -> list:
    """Six line values (6-9), bottom to top."""
    return [sum(rng.choice((2, 3)) for _ in range(3)) for _ in range(6)]


def _hexagram_for(bits: list) -> str:
    return next(n for n, h in _iching_meta().items() if h["lines"] == bits)


def iching_reading(values: list) -> dict:
    """{"hexagram": "3", "moving": [1, 5], "becomes": "8" or None} for line values."""
    primary = [1 if v in (7, 9) else 0 for v in values]
    moving = [i for i, v in enumerate(values, 1) if v in (6, 9)]
    becomes = [1 - b if i in moving else b for i, b in enumerate(primary, 1)]
    return {"hexagram": _hexagram_for(primary), "moving": moving,
            "becomes": _hexagram_for(becomes) if moving else None}


def _hexagram_figure(values: list) -> str:
    """The hexagram drawn top line first, changing lines marked."""
    rows = []
    for i, v in reversed(list(enumerate(values, 1))):
        bar = "━━━━━━━━━━━" if v in (7, 9) else "━━━━   ━━━━"
        mark = {9: "  ○ changing", 6: "  ✕ changing"}.get(v, "")
        rows.append(bar + mark)
    return "```\n" + "\n".join(rows) + "\n```"


def _hexagram_title(n: str) -> str:
    h = _iching_meta()[n]
    return f"{n}. {h['name']} {h['chinese']} — {h['english']}"


def _iching_texts(n: str) -> dict:
    return lookup._data.get("chinese", {}).get("I Ching", {}).get(n, {})


@bot.command(name="iching", aliases=["yijing", "hexagram"])
async def cmd_iching(ctx, *, question: str = ""):
    """Cast an I Ching hexagram (three-coin method). Usage: !iching [optional question]"""
    if not _iching_meta() or not _iching_texts("1"):
        await ctx.send("⚠️ I Ching data not found.")
        return
    values = cast_lines()
    reading = iching_reading(values)
    n, moving, becomes = reading["hexagram"], reading["moving"], reading["becomes"]
    log.info(f"RNG  i ching                → {values} = {n}{f' -> {becomes}' if becomes else ''} (user: {ctx.author})")
    texts = _iching_texts(n)
    embed = discord.Embed(
        title=f"☯️ {_hexagram_title(n)}",
        description=f"{_hexagram_figure(values)}\n**{texts['1']}**\n\n*{texts['2']}*",
        color=discord.Color.dark_teal(),
    )
    for line in moving:
        embed.add_field(name=f"Changing line {line}", value=texts[str(line + 2)][:1024], inline=False)
    if becomes:
        embed.add_field(name=f"Becoming {_hexagram_title(becomes)}",
                        value=_iching_texts(becomes)["1"][:1024], inline=False)
    else:
        embed.add_field(name="No changing lines", value="The hexagram stands as it is.", inline=False)
    embed.set_footer(text=f"{ICHING_SOURCE} · read the whole hexagram: !verse I Ching {n}")
    _ask(embed, question)
    _record(ctx, "iching", f"Hexagram {n}" + (f" → {becomes}" if becomes else ""))
    await ctx.send(embed=embed, view=_card_view("iching", f"{n}:{''.join(map(str, moving))}"))


# ── !hafez — Fāl-e Hāfez ──────────────────────────────────────────────────────
# A living Persian custom: hold a wish or question in mind, open the Divan of
# Hafiz at random, and read the poem you find as the answer. Bell's 43
# ghazals stand in for the full Divan.

HAFIZ_SOURCE = "trans. Gertrude Bell (1897)"


def _hafiz_poems() -> dict:
    return lookup._data.get("sufi", {}).get("Divan of Hafiz", {})


@bot.command(name="hafez", aliases=["hafiz", "fal"])
async def cmd_hafez(ctx, *, question: str = ""):
    """Fāl-e Hāfez: open the Divan of Hafiz at random. Usage: !hafez [optional question]"""
    poems = _hafiz_poems()
    if not poems:
        await ctx.send("⚠️ The Divan of Hafiz isn't loaded.")
        return
    num = random.choice(list(poems))
    log.info(f"RNG  fal-e hafez            → poem {num} (user: {ctx.author})")
    text = "\n\n".join(poems[num].values())
    embed = discord.Embed(title=f"🌹 Fāl-e Hāfez — Poem {num}", description=f"*{text}*"[:4096],
                          color=discord.Color.dark_red())
    embed.set_footer(text=f"{HAFIZ_SOURCE} · !verse Hafiz {num}")
    _ask(embed, question)
    _record(ctx, "hafez", f"Poem {num}")
    await ctx.send(embed=embed, view=_card_view("hafez", num))


# ── !rumi — the Masnavi opened at random ──────────────────────────────────────
# The same custom as the Fāl-e Hāfez, with Rumi's Masnavi: open it anywhere and
# read what you find. Whinfield's abridgement keeps each story's prose summary
# as its first passage; the oracle reads a run of the couplets themselves.

RUMI_SOURCE = "trans. E. H. Whinfield (1898)"


def _masnavi() -> dict:
    return lookup._data.get("sufi", {}).get("Masnavi", {})


def _story_title(passage: str) -> str:
    m = re.match(r"\*(.+?)\*\n", passage)
    return m.group(1) if m else ""


def rumi_passage(rng=random) -> "tuple[str, str] | None":
    """("book.story:passage", its text): a run of couplets, not a story's prose summary."""
    stories = _masnavi()
    couplets = [(s, v) for s, passages in stories.items() for v, t in passages.items()
                if "\n" in t and not t.startswith("*")]
    if not couplets:
        return None
    story, verse = rng.choice(couplets)
    return f"{story}:{verse}", stories[story][verse]


def _rumi_parts(key: str) -> "tuple[str, str, str] | None":
    """(heading, couplets, story title) for a passage key "1.5:3"."""
    story, _, verse = key.partition(":")
    passages = _masnavi().get(story, {})
    text = passages.get(verse)
    if not text:
        return None
    book, _, num = story.partition(".")
    title = _story_title(passages.get("1", ""))
    if num == "0":
        part = "Prologue"
    elif title.startswith("Epilogue"):
        part = "Epilogue"
    else:
        part = f"Story {num}"
    return f"Book {book}, {part}", text, title


@bot.command(name="rumi", aliases=["masnavi", "mathnawi"])
async def cmd_rumi(ctx, *, question: str = ""):
    """Open Rumi's Masnavi at random. Usage: !rumi [optional question]"""
    pick = rumi_passage()
    if pick is None:
        await ctx.send("⚠️ The Masnavi isn't loaded.")
        return
    key, _ = pick
    where, text, title = _rumi_parts(key)
    log.info(f"RNG  masnavi                → {key} (user: {ctx.author})")
    embed = discord.Embed(title=f"🌹 The Masnavi — {where}", description=f"*{text}*"[:4096],
                          color=discord.Color.dark_red())
    if title and not title.startswith(("Prologue", "Epilogue")):
        embed.add_field(name="From the story", value=title, inline=False)
    embed.set_footer(text=f"{RUMI_SOURCE} · the whole story: !verse Masnavi {key.split(':')[0]}")
    _ask(embed, question)
    _record(ctx, "rumi", f"Masnavi {key}")
    await ctx.send(embed=embed, view=_card_view("rumi", key))


# ── !shakespeare, !sonnet ─────────────────────────────────────────────────────
# Shakespeare opened at random (data/shakespeare): a passage of a play, read as an answer to a question if one
# is asked, as people have opened the Bible or Virgil (there's no old custom of it for Shakespeare: this is the
# bot's own); and a sonnet, or a run of stanzas from his other poems. Both follow the server's Shakespeare
# tradition switch, as !ballad does the ballads'.

SHAKESPEARE_SOURCE = "ed. Barbara Mowat and Paul Werstine (Folger Shakespeare)"
SONNETS = "Shakespeare's Sonnets"
POEMS = {"venus": "Venus and Adonis", "adonis": "Venus and Adonis", "lucrece": "Lucrece",
         "phoenix": "The Phoenix and Turtle", "turtle": "The Phoenix and Turtle"}


def _shakespeare() -> dict:
    return lookup._data.get("shakespeare", {})


def _scene_name(chap: str) -> str:
    """"3.1" -> "Act 3, Scene 1"; "0" the Prologue (or Induction), "2.0" a chorus, "6" the Epilogue."""
    if chap == "0":
        return "Prologue"
    if chap == "6":
        return "Epilogue"
    act, _, scene = chap.partition(".")
    if act == "0":
        return f"Induction, Scene {scene}"
    return f"Act {act}, Chorus" if scene == "0" else f"Act {act}, Scene {scene}"


def shakespeare_passage(rng=random) -> "tuple[str, str, str] | None":
    """(play, scene, first line) of a passage of a play, at random -- one with someone speaking in it."""
    books = _shakespeare()
    picks = [(b, c, v) for b, chs in books.items() if b != SONNETS and not set(chs) <= {"1"}
             for c, vs in chs.items() for v, t in vs.items() if "**" in t]
    return rng.choice(picks) if picks else None


def _play_text(book: str, chap: str, line: str) -> str:
    """A passage without its scene's heading (the embed's title names the scene)."""
    text = _shakespeare().get(book, {}).get(chap, {}).get(line, "")
    return re.sub(r"^\*(?:Act \d+, (?:Scene|Chorus)[^*]*|Prologue|Epilogue|Induction[^*]*)\*\n", "", text)


def _plain(text: str) -> str:
    """For a card (all in italics): a stage direction in square brackets, the rest without markup."""
    text = re.sub(r"(?m)^\*([^*\n]+)\*$", r"[\1]", text)
    return re.sub(r"\*+", "", text)


def _first_speech(text: str) -> str:
    """A passage's opening speeches, enough for a card (four lines or so; a whole passage is too long for one)."""
    taken = []
    for speech in (s for s in text.split("\n\n") if "**" in s):
        if taken and sum(len(s) for s in taken) + len(speech) > 700:
            break
        taken.append(re.sub(r"^\*\*([^*]+)\*\*", r"\1:", speech))
        if sum(s.count("\n") + 1 for s in taken) >= 4 or sum(len(s) for s in taken) > 250:
            break
    return "\n\n".join(taken) or text.split("\n\n")[0]


@bot.command(name="shakespeare", aliases=["bard", "sortesshakespeare"])
async def cmd_shakespeare(ctx, *, question: str = ""):
    """Shakespeare opened at random: a passage of one of his plays. Usage: !shakespeare [optional question]"""
    if not tradition_enabled(ctx.guild.id if ctx.guild else None, "shakespeare"):
        await ctx.send("Shakespeare is turned off on this server.")
        return
    pick = shakespeare_passage()
    if pick is None:
        await ctx.send("⚠️ Shakespeare isn't loaded.")
        return
    book, chap, line = pick
    log.info(f"RNG  shakespeare            → {book} {chap}:{line} (user: {ctx.author})")
    result = lookup.get_verse(f"{book} {chap}:{line}")
    embed = discord.Embed(title=f"🎭 {book} — {_scene_name(chap)}", description=_play_text(book, chap, line)[:4096],
                          color=discord.Color.dark_gold())
    embed.set_footer(text=f"{SHAKESPEARE_SOURCE} · !verse {result.get('reference', f'{book} {chap}:{line}')}")
    _ask(embed, question)
    _record(ctx, "shakespeare", f"{book} {chap}:{line}")
    view = _card_view("bard", f"{book}|{chap}|{line}")
    for button in passage_buttons(result):                     # (◀ Previous · Next ▶ · 📖 the whole scene)
        view.add_item(button)
    await ctx.send(embed=embed, view=view)


def _sonnet_pick(query: str, rng=random) -> "tuple[str, str, str] | str":
    """(book, chapter, first line) for !sonnet's query -- a number, a poem's name, or anything else (a question)
    for one at random from the Sonnets and the poems -- or the reply when there's no such sonnet."""
    books = _shakespeare()
    q = query.strip().lower()
    num = re.fullmatch(r"#?(\d{1,6})", q)
    if num:
        n = num.group(1).lstrip("0") or "0"
        if n not in books.get(SONNETS, {}):
            return "There are 154 sonnets: try a number from 1 to 154."
        return SONNETS, n, "1"
    poem = next((name for word, name in POEMS.items() if word in q.split()), None)
    pool = ([(SONNETS, c, "1") for c in books.get(SONNETS, {})] if not poem else [])
    for name in ([poem] if poem else set(POEMS.values())):
        pool += [(name, "1", v) for v in books.get(name, {}).get("1", {}) if v != "0"]   # (not the dedication)
    return rng.choice(pool)


def _sonnet_title(book: str, chap: str, line: str) -> str:
    if book == SONNETS:
        return f"Sonnet {chap}"
    lines = list(_shakespeare().get(book, {}).get("1", {}))
    later = [int(v) for v in lines if int(v) > int(line)]
    end = f"–{later[0] - 1}" if later else ""
    return f"{book}, lines {line}{end}" if later else f"{book}, from line {line}"


@bot.command(name="sonnet", aliases=["sonnets"])
async def cmd_sonnet(ctx, *, query: str = ""):
    """One of Shakespeare's sonnets, or stanzas of his other poems. Usage: !sonnet · !sonnet 18 · !sonnet venus
    (or lucrece, phoenix) · !sonnet [a question]"""
    if not tradition_enabled(ctx.guild.id if ctx.guild else None, "shakespeare"):
        await ctx.send("Shakespeare is turned off on this server.")
        return
    if not _shakespeare().get(SONNETS):
        await ctx.send("⚠️ Shakespeare isn't loaded.")
        return
    pick = _sonnet_pick(query)
    if isinstance(pick, str):
        await ctx.send(pick)
        return
    book, chap, line = pick
    question = query if not re.fullmatch(r"#?\d+", query.strip()) and not any(
        w in POEMS for w in query.lower().split()) else ""
    log.info(f"RNG  sonnet                 → {book} {chap}:{line} (user: {ctx.author})")
    text = _shakespeare()[book][chap][line]
    ref = f"Sonnets {chap}" if book == SONNETS else f"{book} {line}"
    embed = discord.Embed(title=f"🎭 {_sonnet_title(book, chap, line)}", description=text[:4096],
                          color=discord.Color.dark_gold())
    embed.set_footer(text=f"{SHAKESPEARE_SOURCE} · !verse {ref}")
    _ask(embed, question)
    _record(ctx, "sonnet", ref)
    await ctx.send(embed=embed, view=_card_view("bard", f"{book}|{chap}|{line}"))


# ── Daily oracle (!oraclesetup) ───────────────────────────────────────────────
# Like the daily verse: an oracle posted each day in a channel of the
# server's choosing. Per-guild settings in guild_config.json:
# oracle_channel_id, oracle_time ("HH:MM" UTC), oracle_kind.

DAILY_ORACLE_HEADER = "🔮 **Today's oracle**"
# Sortes Biblicae (bibliomancy) is deliberately not offered as a daily oracle,
# at the owner's request; it remains an ordinary command.
_DAILY_KINDS = {
    "virgil": cmd_virgil,
    "homer": cmd_homer,
    "delphi": cmd_delphi,
    "oracle": cmd_oracle,
    "iching": cmd_iching,
    "hafez": cmd_hafez,
    "rumi": cmd_rumi,
}


class _DailyContext:
    """Runs an oracle command into a channel with no one asking: the first
    message gets the "Today's oracle" header, and no usage stats are recorded."""
    is_daily = True
    author = None

    def __init__(self, channel):
        self.channel = channel
        self._first = True

    async def send(self, content=None, **kwargs):
        if self._first:
            self._first = False
            content = DAILY_ORACLE_HEADER if content is None else f"{DAILY_ORACLE_HEADER}\n{content}"
        return await self.channel.send(content, **kwargs)

    def typing(self):
        return self.channel.typing()


async def post_daily_oracle(channel, kind: str = "any") -> str:
    """Post one oracle to `channel`; "any" picks one of them at random.
    Returns the kind posted."""
    if kind not in _DAILY_KINDS:
        kind = random.choice(list(_DAILY_KINDS))
    await _DAILY_KINDS[kind](_DailyContext(channel))
    return kind


async def run_daily_oracles(client, current_hm: str) -> int:
    """Post to every guild whose daily-oracle time is current_hm ("HH:MM" UTC)."""
    posted = 0
    for guild_id, g in _load_guild_config().items():
        channel_id = g.get("oracle_channel_id")
        if not channel_id or g.get("oracle_time", "12:00") != current_hm:
            continue
        if not command_enabled(int(guild_id), "oracle"):   # the server turned it off
            continue
        channel = client.get_channel(int(channel_id))
        if channel is None:
            continue
        try:
            await post_daily_oracle(channel, g.get("oracle_kind", "any"))
            posted += 1
        except Exception:
            log.exception(f"Failed to post the daily oracle for guild {guild_id}")
    return posted


@tasks.loop(minutes=1)
async def daily_oracle_task():
    import datetime
    now = datetime.datetime.now(datetime.timezone.utc)
    await run_daily_oracles(bot, f"{now.hour:02d}:{now.minute:02d}")


@daily_oracle_task.before_loop
async def _before_daily_oracle():
    await bot.wait_until_ready()


@bot.command(name="oraclesetup", aliases=["oracleconfig"])
@commands.has_permissions(administrator=True)
async def cmd_oraclesetup(ctx, action: str = "", *, arg: str = ""):
    """Configure this server's daily oracle post.
    Usage: !oraclesetup                  — show this server's settings
           !oraclesetup channel #chan    — post the daily oracle there
           !oraclesetup time 12:00       — daily post time (24h UTC)
           !oraclesetup kind any         — any | virgil | homer | delphi | oracle | iching | hafez | rumi
           !oraclesetup test             — post one now, to try it
           !oraclesetup off              — stop the daily oracle"""
    if not ctx.guild:
        await ctx.send("This command only works in a server.")
        return
    g = _load_guild_config().get(str(ctx.guild.id), {})
    channel_id, time_hm, kind = g.get("oracle_channel_id"), g.get("oracle_time", "12:00"), g.get("oracle_kind", "any")
    action = action.strip().lower()

    if not action:
        embed = discord.Embed(title=f"🔮 Daily oracle — {ctx.guild.name}", color=discord.Color.dark_purple())
        embed.add_field(name="Channel", value=f"<#{channel_id}>" if channel_id else "*not set — daily oracle is off*")
        embed.add_field(name="Time (UTC)", value=time_hm)
        embed.add_field(name="Oracle", value=kind)
        embed.set_footer(text="!oraclesetup channel #chan · time HH:MM · kind any|virgil|homer|delphi|oracle|iching|hafez|rumi · test · off")
        await ctx.send(embed=embed)
        return
    if action == "off":
        _update_guild_config(ctx.guild.id, oracle_channel_id=None)
        await ctx.send("The daily oracle is off for this server.")
        return
    if action == "channel":
        channel = ctx.message.channel_mentions[0] if ctx.message.channel_mentions else None
        if channel is None:
            await ctx.send("Mention a channel: `!oraclesetup channel #general`")
            return
        _update_guild_config(ctx.guild.id, oracle_channel_id=channel.id)
        await ctx.send(f"The daily oracle will be posted in {channel.mention} at {time_hm} UTC ({kind}).")
        return
    if action == "time":
        m = re.match(r"^(\d{1,2}):(\d{2})$", arg.strip())
        if not m or not (0 <= int(m.group(1)) <= 23 and 0 <= int(m.group(2)) <= 59):
            await ctx.send("Use 24-hour UTC time: `!oraclesetup time 12:00`")
            return
        hm = f"{int(m.group(1)):02d}:{int(m.group(2)):02d}"
        _update_guild_config(ctx.guild.id, oracle_time=hm)
        await ctx.send(f"Daily oracle time set to **{hm} UTC**.")
        return
    if action == "kind":
        new_kind = arg.strip().lower()
        if new_kind not in ("any", *_DAILY_KINDS):
            await ctx.send("Choose `any`, `virgil`, `homer`, `delphi`, `oracle`, `iching`, `hafez`, or `rumi`.")
            return
        _update_guild_config(ctx.guild.id, oracle_kind=new_kind)
        await ctx.send(f"Daily oracle set to **{new_kind}**.")
        return
    if action == "test":
        channel = bot.get_channel(int(channel_id)) if channel_id else ctx.channel
        await post_daily_oracle(channel, kind)
        return
    await ctx.send("Unknown option. Use `channel`, `time`, `kind`, `test`, or `off` — see `!help oraclesetup`.")
