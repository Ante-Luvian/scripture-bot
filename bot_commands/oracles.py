"""
!gematria, !virgil / !homer / !delphi, !oracle, !sortesbiblicae.
"""
import asyncio
import discord
import functools
import random
import re
import runes
from scripture_lookup import BIBLE_NT, BIBLE_OT
from bot_commands import illustrations
from bot_commands.card import (
    _render_parallel_card,
    _render_runes_card,
    _render_verse_card,
)
from bot_commands.verse import (
    PassageButton,
    _study_buttons,
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
    if kind == "bard":                         # key "Hamlet|3.1|64": a play's line, a sonnet or poem passage
        book, chap, line = (key.split("|") + ["", ""])[:3]
        if book in _play_lines().get("lines", {}):
            text = _lot_text(book, chap, line, markdown=False)
            return (f"{book} {chap}.{line}", text, SHAKESPEARE_SOURCE) if text else None
        text = _shakespeare().get(book, {}).get(chap, {}).get(line)
        return (_sonnet_title(book, chap, line), _plain(text), SHAKESPEARE_SOURCE) if text else None
    if kind == "edda":                         # key "Hovamol|138": a stanza of the Poetic Edda ("Eiriksmol|6|2": Odin's
        poem, stanza, verse, odin = (key.split("|") + ["", "", ""])[:4]       # speech in a stanza of Hollander's;
        text = _edda_text(poem, stanza, verse)                                #  "|o" on the end: !odin's, unquoted)
        text = _unquoted(text)                    # (no quotation marks on the card: the owner, 2026-11-08)
        # (a half-line to a line, the second halves indented: the owner's choice, 2026-11-08)
        return (_edda_title(poem, stanza), _half_lines(_plain(text), mark=True), _edda_source(poem)) if text else None
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
                       template=r"ocard:(?P<kind>virgil|homer|delphi|oracle|iching|hafez|rumi|bard|edda):(?P<key>.+)"):
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
        view = _view_after(interaction.message, self.custom_id)
        await interaction.response.edit_message(view=view if view.children else
                                                _card_view(self.kind, self.key, disabled=True))
        content = _oracle_card_content(self.kind, self.key)
        if content is None:
            await interaction.followup.send("⚠️ I can't find that answer's text any more.", ephemeral=True)
            return
        question = _question_from(interaction.message)
        style = {"iching": "ink", "hafez": "persian", "rumi": "persian", "edda": "norse",
                 "bard": "parchment"}.get(self.kind, "classical")
        # (a poem's lines kept whole: the Edda's stanzas, the Sonnets and the long poems; not a play's speech)
        shakespeare_poem = self.kind == "bard" and self.key.split("|")[0] not in _play_lines().get("lines", {})
        # (Shakespeare's poems and the Edda set as a printed poem: upright, flush left, lines indented)
        buf = await asyncio.to_thread(_render_verse_card, *content, question, style,
                                      verse=self.kind == "edda", poem=shakespeare_poem or self.kind == "edda")
        await interaction.followup.send(file=discord.File(buf, filename="oracle.png"))


bot.add_dynamic_items(OracleCardButton)


def _card_view(kind: str, key: str, disabled: bool = False) -> discord.ui.View:
    view = discord.ui.View(timeout=None)
    view.add_item(OracleCardButton(kind, key, disabled))
    return view


def _view_after(message, pressed: str) -> discord.ui.View:
    """An oracle answer's buttons once one image button is pressed: rebuilt from the message (so it works after a
    restart), the 🖼️ Card or ᚱ Runes button pressed now (or before) disabled, the rest (◀ ▶, 🖌️, 📜) as they were.
    (Until 2026-11-08 a pressed Card left only itself, and !edda's ◀ ▶ and 🖌️ went.)"""
    view = discord.ui.View(timeout=None)
    for r, row in enumerate(getattr(message, "components", None) or []):
        for c in getattr(row, "children", []):
            cid = getattr(c, "custom_id", None) or ""
            done = bool(getattr(c, "disabled", False)) or cid == pressed
            if m := OracleCardButton.__discord_ui_compiled_template__.fullmatch(cid):
                button = OracleCardButton(m["kind"], m["key"], disabled=done)
            elif m := RunesButton.__discord_ui_compiled_template__.fullmatch(cid):
                button = RunesButton(m["key"], disabled=done)
            elif m := NorseButton.__discord_ui_compiled_template__.fullmatch(cid):
                button = NorseButton(m["key"], disabled=done)
            elif m := NorseCardButton.__discord_ui_compiled_template__.fullmatch(cid):
                button = NorseCardButton(m["key"], disabled=done)
            elif m := PassageButton.__discord_ui_compiled_template__.fullmatch(cid):
                button = PassageButton(m["kind"], m["ref"])
            elif m := illustrations.PictureButton.__discord_ui_compiled_template__.fullmatch(cid):
                button = illustrations.PictureButton(m["keys"].split(","))
            else:
                continue
            button.item.row = min(r, 4)                         # (each on the row it was on)
            view.add_item(button)
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
# Shakespeare by lot, as !virgil draws Virgil (there's no old custom of it for Shakespeare: this is the bot's
# own): four dice, for the play (numbered in the First Folio's order, data/shakespeare/lines.json), the act,
# the scene and the line, and the line drawn is the answer. And a sonnet, or a run of stanzas from his other
# poems. Both follow the server's Shakespeare tradition switch, as !ballad does the ballads'.

SHAKESPEARE_SOURCE = "Folger edition"
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


_SHAKESPEARE_LINES = None


def _play_lines() -> dict:
    """{"order": [the 38 plays, First Folio order], "lines": {play: {scene: {line: [[speaker, text], ...]}}}}"""
    global _SHAKESPEARE_LINES
    if _SHAKESPEARE_LINES is None:
        import json
        path = ROOT / "data" / "shakespeare" / "lines.json"
        _SHAKESPEARE_LINES = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    return _SHAKESPEARE_LINES


def shakespeare_lot(rng=random) -> "tuple[int, str, str, str, str] | None":
    """The four dice: (the play's number, the play, act, scene, line). A die for each, as !virgil rolls one for
    the book and one for the line: an act of the five, a scene of that act's (its Chorus is one), a line of the
    scene's. (The Prologues, Inductions and Epilogues stand outside the acts, so don't come up.)"""
    data = _play_lines()
    if not data.get("order"):
        return None
    n = rng.randint(1, len(data["order"]))
    play = data["order"][n - 1]
    scenes = [s for s in data["lines"][play] if re.fullmatch(r"[1-5]\.\d+", s)]
    act = rng.choice(sorted({s.split(".")[0] for s in scenes}, key=int))
    scene = rng.choice(sorted((s.split(".")[1] for s in scenes if s.split(".")[0] == act), key=int))
    line = rng.choice(sorted(data["lines"][play][f"{act}.{scene}"], key=int))
    return n, play, act, scene, line


_SENTENCE_END = re.compile(r"[.!?][’”'\")\]]*(?=\s|$)")


def _lot_sentence(play: str, chap: str, line: str) -> "tuple[str, list] | None":
    """The line drawn as part of its sentence: (speaker, [(text, is the line drawn, prose)]), from the start of the
    sentence the line begins in to the end of the one it ends in, inside the one speech. A printed line, prose's
    above all, so often stops mid-sentence ("safety. But the composition that your valor and")."""
    scene = _play_lines().get("lines", {}).get(play, {}).get(chap, {})
    parts = scene.get(line)
    if not parts:
        return None
    who, _, _, speech = max(parts, key=lambda p: len(p[1]))        # (a shared line: the longer share)
    rows = sorted((int(n), p[1], p[2]) for n, ps in scene.items() for p in ps if p[3] == speech)
    text, spans = "", []
    for n, t, prose in rows:
        spans.append((n, len(text), len(text) + len(t), prose))
        text += t + "\n"
    _, ds, de, _ = next(s for s in spans if s[0] == int(line))
    ends = [m.end() for m in _SENTENCE_END.finditer(text)]
    start = max((e for e in ends if e <= ds), default=0)
    stop = min((e for e in ends if e >= de - 1), default=len(text))
    pieces = []
    for n, a, b, prose in spans:
        piece = text[max(a, start):min(b, stop)].strip()
        if piece:
            pieces.append((piece, n == int(line), prose))
    return who, pieces


def _lot_text(play: str, chap: str, line: str, markdown: bool = True) -> str:
    """The sentence(s) the line drawn is in, verse a line a line and prose run on, the line drawn in bold, and
    who speaks it."""
    found = _lot_sentence(play, chap, line)
    if not found:
        return ""
    who, pieces = found
    rows = []
    for i, (piece, drawn, prose) in enumerate(pieces):
        shown = (f"***{piece}***" if drawn else f"*{piece}*") if markdown else piece
        if i and prose and pieces[i - 1][2]:
            rows[-1] += " " + shown                                    # (prose: one paragraph)
        else:
            rows.append(shown)
    body = "\n".join(rows)
    if not who:
        return body
    return f"{body}\n— {who.title()}" if markdown else f"{who.title()}: {body}"


def _plain(text: str) -> str:
    return re.sub(r"\*+", "", text)


@bot.command(name="shakespeare", aliases=["bard", "sortesshakespeare"])
async def cmd_shakespeare(ctx, *, question: str = ""):
    """Shakespeare by lot: dice for the play, act, scene and line. Usage: !shakespeare [optional question]"""
    if not tradition_enabled(ctx.guild.id if ctx.guild else None, "shakespeare"):
        await ctx.send("Shakespeare is turned off on this server.")
        return
    lot = shakespeare_lot()
    if lot is None:
        await ctx.send("⚠️ Shakespeare isn't loaded.")
        return
    n, play, act, scene, line = lot
    chap = f"{act}.{scene}"
    log.info(f"RNG  shakespeare            → {n} {play} {chap}.{line} (user: {ctx.author})")
    # Visual, as !virgil's: 🎭 {play} 📜 {act} 🎬 {scene} 🕯️ {line} 👈
    display = f"🎭 {n}  📜 {act}  🎬 {'Chorus' if scene == '0' else scene}  🕯️ {line}  👈"
    embed = discord.Embed(title=f"🎭 {play}, {_scene_name(chap)}",
                          description=f"{display}\n\n{_lot_text(play, chap, line)}", color=discord.Color.dark_gold())
    embed.set_footer(text=f"{play} {chap}.{line} · {SHAKESPEARE_SOURCE}")
    _ask(embed, question)
    _record(ctx, "shakespeare", f"{play} {chap}.{line}")
    view = _card_view("bard", f"{play}|{chap}|{line}")
    ref = f"{play} {chap}:{line}"
    if len(ref) <= 93:                                         # (📜 the passage around the line)
        in_context = PassageButton("x", ref)
        in_context.item.row = 0                                # (beside Card: !verse's go on a row of their own)
        view.add_item(in_context)
    for b in illustrations.buttons(illustrations.for_passage(play, chap, int(line)), row=0):
        view.add_item(b)                                       # (🖌️ Boydell: a picture of the scene, at this line)
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


# ── !edda — a stanza of the Poetic Edda ─────────────────────────────────────
# A stanza at random, from all 35 poems or from one ("!edda havamal"), with 🃏 Card, ◀ ▶ to read on stanza by
# stanza, and 🖌️ Collingwood's and Frølich's pictures of the poem (bot_commands/illustrations.py). The owner's
# request, 2026-11-07. Bellows's spellings ("Hovamol") are the bot's names; the English title goes with them.
EDDA_SOURCE = "The Poetic Edda, trans. Henry Adams Bellows (1923)"
EDDA_ENGLISH = {
    "Voluspo": "The Prophecy of the Seeress", "Hovamol": "The Sayings of the High One",
    "Vafthruthnismol": "The Lay of Vafthruthnir", "Grimnismol": "The Ballad of Grimnir",
    "Skirnismol": "The Ballad of Skirnir", "Harbarthsljoth": "The Poem of Harbarth", "Hymiskvitha": "The Lay of Hymir",
    "Lokasenna": "Loki's Wrangling", "Thrymskvitha": "The Lay of Thrym", "Alvissmol": "The Ballad of Alvis",
    "Baldrs Draumar": "Baldr's Dreams", "Rigsthula": "The Song of Rig", "Hyndluljoth": "The Poem of Hyndla",
    "Svipdagsmol": "The Ballad of Svipdag", "Völundarkvitha": "The Lay of Völund",
    "Helgakvitha Hjorvarthssonar": "The Lay of Helgi the Son of Hjorvarth",
    "Helgakvitha Hundingsbana I": "The First Lay of Helgi Hundingsbane",
    "Helgakvitha Hundingsbana II": "The Second Lay of Helgi Hundingsbane",
    "Fra Dautha Sinfjotla": "Of Sinfjotli's Death", "Gripisspo": "Gripir's Prophecy", "Reginsmol": "The Ballad of Regin",
    "Fafnismol": "The Ballad of Fafnir", "Sigrdrifumol": "The Ballad of the Victory-Bringer",
    "Brot af Sigurtharkvithu": "Fragment of a Sigurth Lay", "Guthrunarkvitha I": "The First Lay of Guthrun",
    "Sigurtharkvitha en Skamma": "The Short Lay of Sigurth", "Helreith Brynhildar": "Brynhild's Hell-Ride",
    "Drap Niflunga": "The Slaying of the Niflungs", "Guthrunarkvitha II": "The Second, or Old, Lay of Guthrun",
    "Guthrunarkvitha III": "The Third Lay of Guthrun", "Oddrunargratr": "Oddrun's Lament",
    "Atlakvitha en Gronlenzka": "The Greenland Lay of Atli", "Atlamol en Gronlenzku": "The Greenland Ballad of Atli",
    "Guthrunarhvot": "Guthrun's Inciting", "Hamthesmol": "The Ballad of Hamther",
    # (and the two poems of Hollander's Old Norse Poems that !odin draws on)
    "Eiriksmol": "The Lay of Eric", "Heithreksgatur": "The Riddles of King Heithrek",
}


def _edda() -> dict:
    """The Poetic Edda's poems: the Norse shelf's books in Bellows's translation (not Hollander's other poems)."""
    return {poem: stanzas for poem, stanzas in lookup._data.get("norse", {}).items()
            if "Bellows" in lookup._book_sources.get(poem, "Bellows")}


def _edda_source(poem: str) -> str:
    source = lookup._book_sources.get(poem, "")
    if "Hollander" in source:
        return "Lee M. Hollander, Old Norse Poems (1936)"
    return EDDA_SOURCE


def _unquoted(text: str) -> str:
    """!odin's text without its quotation marks (the owner, 2026-11-08: "remove quotation marks from anything in
    !odin"): every word in it is his, so the marks only clutter it. Apostrophes ("o’er", "’Tis") stay."""
    text = re.sub(r"[“”\"]", "", text)
    return "\n".join(line.lstrip(" ") for line in text.split("\n"))


def _edda_text(poem: str, stanza: str, verse: str = "") -> str:
    """A stanza's text: Bellows's (verse "1"), or one speech of a Hollander stanza without its "Óthin: " label."""
    verses = lookup._data.get("norse", {}).get(poem, {}).get(stanza, {})
    if verse:
        return re.sub(r"^[^\W\d_][\w ]*: (?=[“(])", "", verses.get(verse, ""))
    return "\n".join(verses[v] for v in sorted(verses, key=int))


def _edda_pick(query: str, rng=random) -> "tuple[str, str] | str":
    """(poem, stanza) for !edda's query: a poem's name ("havamal", "Sayings of the High One") for a stanza of it,
    "havamal 138" for that stanza, anything else (a question) for any stanza of any poem; or the reply when the
    poem or stanza isn't there."""
    poems = _edda()
    q = query.strip()
    m = re.match(r"^(.*?)\s*(\d+)$", q)
    name, number = (m.group(1), m.group(2)) if m and m.group(1) else (q, None)
    poem = lookup._resolve_exact(name)[1] if name else None
    if poem in poems:
        if number:
            return (poem, number) if number in poems[poem] else f"**{poem}** has stanzas 1 to {len(poems[poem])}."
        return poem, rng.choice(list(poems[poem]))
    if poem in lookup._data.get("norse", {}):        # (one of Hollander's poems, not the Edda's)
        return (f"**{poem}** isn't in the Poetic Edda: it's one of the Old Norse poems from the sagas and the "
                f"skalds. `!verse {poem} 1` reads it.")
    if number and not name:
        return "Name a poem with the stanza: `!edda havamal 138`."
    pool = [(p, s) for p, stanzas in poems.items() for s in stanzas]
    return rng.choice(pool)


def _edda_title(poem: str, stanza: str) -> str:
    english = EDDA_ENGLISH.get(poem)
    return f"{poem}{f' ({english})' if english else ''}, stanza {stanza}"


# The Old Norse beside Bellows (the owner, 2026-11-07): Guðni Jónsson's text, matched to Bellows's stanzas by
# scripts/build_edda_norse.py (by content: Bellows numbers and orders some stanzas his own way). A stanza of Bellows's
# with nothing in the Norse to match it (some of his lacunae, a line or two he took from elsewhere) has none.
NORSE_SOURCE = "Old Norse: Guðni Jónsson, Eddukvæði (1949)"
RUNES_NOTE = "Norwegian Viking-Age runes: a modern transcription (the Edda was written down in the Latin alphabet)"


@functools.lru_cache(maxsize=1)
def _edda_norse() -> dict:
    import json
    path = ROOT / "data" / "norse" / "edda_norse.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def _norse_text(poem: str, stanza: str) -> str:
    return _edda_norse().get(poem, {}).get(stanza, "")


class RunesButton(discord.ui.DynamicItem[discord.ui.Button], template=r"runes:(?P<key>.+)"):
    """ᚱ Runes under !edda and !odin: the stanza's Old Norse as a card in Younger Futhark runes. Its custom_id
    carries the "poem|stanza" (so it works after a restart, like the Card button)."""

    def __init__(self, key: str, disabled: bool = False):
        super().__init__(discord.ui.Button(label="ᚱ Runes", style=discord.ButtonStyle.secondary,
                                           custom_id=f"runes:{key}", disabled=disabled, row=1))
        self.key = key

    @classmethod
    async def from_custom_id(cls, interaction, item, match):
        return cls(match["key"])

    async def callback(self, interaction: discord.Interaction):
        poem, _, stanza = self.key.partition("|")
        norse = _norse_text(poem, stanza)
        if not norse:
            await interaction.response.send_message("⚠️ I can't find that stanza's Old Norse any more.",
                                                    ephemeral=True)
            return
        view = _view_after(interaction.message, self.custom_id)       # (one card per answer, as with 🖼️ Card)
        if not view.children:
            view.add_item(RunesButton(self.key, disabled=True))
        await interaction.response.edit_message(view=view)
        # (as on a runestone: one run, filling the card; the owner, 2026-11-08)
        buf = await asyncio.to_thread(_render_runes_card, _edda_title(poem, stanza), runes.carve(norse), RUNES_NOTE,
                                      _question_from(interaction.message), "norse")
        await interaction.followup.send(file=discord.File(buf, filename="runes.png"))


bot.add_dynamic_items(RunesButton)


class NorseCardButton(discord.ui.DynamicItem[discord.ui.Button], template=r"ncard:(?P<key>.+)"):
    """🖼️ Card under the Old Norse view: the English and the Norse side by side as a picture, both a half-line to a
    line, upright, flush left, the second halves indented (the owner, 2026-11-08). Key "poem|stanza", "|o" for
    !odin's (unquoted)."""

    def __init__(self, key: str, disabled: bool = False):
        super().__init__(discord.ui.Button(label="Card", emoji="🖼️", style=discord.ButtonStyle.secondary,
                                           custom_id=f"ncard:{key}", disabled=disabled))
        self.key = key

    @classmethod
    async def from_custom_id(cls, interaction, item, match):
        return cls(match["key"])

    async def callback(self, interaction: discord.Interaction):
        poem, stanza, odin = (self.key.split("|") + [""])[:3]
        norse, english = _norse_text(poem, stanza), _norse_english(poem, stanza)
        if not norse or not english:
            await interaction.response.send_message("⚠️ I can't find that stanza's Old Norse any more.",
                                                    ephemeral=True)
            return
        view = _view_after(interaction.message, self.custom_id)
        if not view.children:
            view.add_item(NorseCardButton(self.key, disabled=True))
        await interaction.response.edit_message(view=view)
        norse, english = _unquoted(norse), _unquoted(english)       # (no quotation marks on the card)
        left = _half_lines(_plain(english), mark=True)
        buf = await asyncio.to_thread(_render_parallel_card, _edda_title(poem, stanza), left,
                                      _norse_marked(norse, left), f"{_edda_source(poem)} · {_norse_source(poem)}")
        await interaction.followup.send(file=discord.File(buf, filename="edda.png"))


bot.add_dynamic_items(NorseCardButton)


_CAESURA = re.compile(r"\s*[·|]\s*| +")          # (Bellows's dot, an old bar; Hollander's em space)


def _half_lines(text: str, mark: bool = False) -> str:
    """The lines cut at the caesura, a half-line to a line, as Guðni prints the Norse: the owner's choice (2026-11-08)
    for the Edda everywhere. Hollander's em-space indents (his whole lines) go. mark: the second half of each line
    starts with a tab, for the cards to indent (a whole line, unsplit, isn't)."""
    out = []
    for line in text.split("\n"):
        halves = [h.strip() for h in _CAESURA.split(line.strip("  ")) if h.strip()]
        out += [("\t" if mark and n else "") + h for n, h in enumerate(halves)]
    return "\n".join(out)


def _norse_marked(norse: str, english_marked: str) -> str:
    """The Norse with its lines marked for indenting: as the English beside it, when the two have as many lines
    (then they are the same half-lines); else every other line."""
    lines, eng = norse.split("\n"), english_marked.split("\n")
    if len(lines) == len(eng):
        return "\n".join(("\t" if e.startswith("\t") else "") + l for l, e in zip(lines, eng))
    return "\n".join(("\t" if n % 2 else "") + l for n, l in enumerate(lines))


def _fit_field(text: str) -> str:
    """A field's value: whole lines up to Discord's 1024 characters."""
    if len(text) <= 1024:
        return text
    return text[:1021].rsplit("\n", 1)[0] + "\n…"


NORSE_SOURCES = {"Eiriksmol": "Old Norse: Finnur Jónsson, Carmina Scaldica (1929)"}   # (else Guðni's Eddukvæði)


def _norse_source(poem: str) -> str:
    return NORSE_SOURCES.get(poem, NORSE_SOURCE)


def _norse_english(poem: str, stanza: str) -> str:
    """The English to set beside the Norse: Bellows's stanza, or in Hollander's poems (only in !odin) Odin's speech
    alone, as the Norse there is his lines alone (scripts/build_edda_norse.py HOLLANDER)."""
    verse = ODIN_HOLLANDER.get(poem, {}).get(stanza, "")
    return _edda_text(poem, stanza, verse)


def _norse_embed(poem: str, stanza: str, odin: bool = False) -> "discord.Embed | None":
    """A stanza's English and Old Norse side by side, a half-line to a line in both (on a phone Discord stacks the
    two columns). None if the stanza has no Norse."""
    norse, english = _norse_text(poem, stanza), _norse_english(poem, stanza)
    if not norse or not english:
        return None
    if odin:
        norse, english = _unquoted(norse), _unquoted(english)
    embed = discord.Embed(title=f"🌲 {_edda_title(poem, stanza)}", color=discord.Color.dark_green())
    embed.add_field(name="English", value=_fit_field(_half_lines(english)), inline=True)
    embed.add_field(name="Old Norse", value=_fit_field(norse), inline=True)
    embed.set_footer(text=f"{_edda_source(poem)} · {_norse_source(poem)}")
    return embed


def _edda_stanza(query: str) -> "tuple[str, str] | None":
    """(poem, stanza) for an Edda reference, as !parallel takes one: "havamal 139", "Hovamol 139", "Hovamol 139:1";
    a poem alone gives one of its stanzas with Norse. None if it isn't a poem of the Edda."""
    m = re.match(r"^(.*?)\s*(\d+)(?::1)?$", query.strip())
    name, number = (m.group(1), m.group(2)) if m and m.group(1) else (query.strip(), None)
    poem = lookup._resolve_exact(name)[1] if name else None
    if poem not in _edda():
        return None
    if number:
        return poem, number
    have = list(_edda_norse().get(poem, {}))
    return (poem, random.choice(have)) if have else (poem, "1")


async def send_norse(ctx, poem: str, stanza: str, odin: bool = False) -> None:
    """The English and Old Norse of a stanza (!parallel, !odin norse), with the ᚱ Runes button."""
    embed = _norse_embed(poem, stanza, odin)
    if embed is None:
        known = poem in _edda() and stanza in _edda()[poem]
        await ctx.send(f"Stanza {stanza} of **{poem}** has no Old Norse here: `!edda {poem} {stanza}` gives the "
                       f"English." if known else f"**{poem}** has stanzas 1 to {len(_edda().get(poem, {}))}.")
        return
    view = discord.ui.View(timeout=None)
    view.add_item(NorseCardButton(f"{poem}|{stanza}{'|o' if odin else ''}"))
    view.add_item(RunesButton(f"{poem}|{stanza}"))
    await ctx.send(embed=embed, view=view)


class NorseButton(discord.ui.DynamicItem[discord.ui.Button], template=r"norse:(?P<key>.+)"):
    """Old Norse under !edda and !odin: the stanza's English and Norse side by side, as a message of its own (the
    owner, 2026-11-08: not in the first message, it made it too big). Key "poem|stanza", "|o" for !odin's."""

    def __init__(self, key: str, disabled: bool = False):
        super().__init__(discord.ui.Button(label="Old Norse", emoji="📜", style=discord.ButtonStyle.secondary,
                                           custom_id=f"norse:{key}", disabled=disabled, row=1))
        self.key = key

    @classmethod
    async def from_custom_id(cls, interaction, item, match):
        return cls(match["key"])

    async def callback(self, interaction: discord.Interaction):
        poem, stanza, odin = (self.key.split("|") + [""])[:3]
        embed = _norse_embed(poem, stanza, odin == "o")
        if embed is None:
            await interaction.response.send_message("⚠️ I can't find that stanza's Old Norse any more.",
                                                    ephemeral=True)
            return
        view = _view_after(interaction.message, self.custom_id)
        if not view.children:
            view.add_item(NorseButton(self.key, disabled=True))
        await interaction.response.edit_message(view=view)
        card = discord.ui.View(timeout=None)
        card.add_item(NorseCardButton(self.key))
        await interaction.followup.send(embed=embed, view=card)


bot.add_dynamic_items(NorseButton)


@bot.command(name="edda", aliases=["eddic"])
async def cmd_edda(ctx, *, query: str = ""):
    """A stanza of the Poetic Edda, the Old Norse poems of the gods and heroes: at random, from one poem, or one
    stanza. Usage: !edda · !edda havamal · !edda havamal 138 · !edda [a question]"""
    await send_edda(ctx, query)


# Odin's own words (the owner, 2026-11-07: "his sayings", and none of the other speakers'): the Hávamál (but for
# five stanzas that are another's words or speak of him: 98 Billing's daughter, 109-110 the frost-giants and "On his
# ring swore Othin", 138 "Now are Hor's words spoken", 144 "Othin for the gods"), Grimnismol whole (his monologue
# as Grimnir), and in the dialogue poems only the stanzas Bellows heads "Othin spake" (or "Harbarth" / "The
# ferryman", Odin disguised): data/norse/edda_speakers.json, from scripts/build_edda_speakers.py.
ODIN_SPEAKERS = {"Othin", "Harbarth", "The ferryman"}
HOVAMOL_NOT_HIS = {"98", "109", "110", "138", "144"}
# And from Hollander's Old Norse Poems (1936; the owner, 2026-11-08: "other sources of Norse poetry that have Odin
# speaking"), stanza -> the verse that is his speech, read by hand: Eiríksmál, where he wakes Valhalla for Eric
# Bloodaxe (1-5 his; in 3 he asks and Bragi answers; in 6 and 7 he answers Sigmund), and the Riddles of King
# Heithrek, every one asked by Odin disguised as Gestumblindi (verse 2 is the king's answer). Hákonarmál has no
# speech of his; the rest of the book, none.
ODIN_HOLLANDER = {
    "Eiriksmol": {"1": "1", "2": "1", "3": "1", "4": "1", "5": "1", "6": "2", "7": "2"},
    "Heithreksgatur": {str(n): "1" for n in range(1, 38)},
}


@functools.lru_cache(maxsize=1)
def _odin_stanzas() -> tuple:
    import json
    path = ROOT / "data" / "norse" / "edda_speakers.json"
    table = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    edda = _edda()
    out = [("Hovamol", s) for s in edda.get("Hovamol", {}) if s not in HOVAMOL_NOT_HIS]
    out += [("Grimnismol", s) for s in edda.get("Grimnismol", {})]
    for poem, speakers in table.items():
        out += [(poem, s) for s, who in speakers.items() if who in ODIN_SPEAKERS and s in edda.get(poem, {})]
    norse = lookup._data.get("norse", {})
    for poem, verses in ODIN_HOLLANDER.items():
        out += [(poem, s) for s, v in verses.items() if v in norse.get(poem, {}).get(s, {})]
    return tuple(out)


def _odin_pick(query: str, rng=random) -> "tuple[str, str, str] | str":
    """(poem, stanza, question) for !odin's query, or the reply when it names a stanza that isn't his."""
    stanzas = _odin_stanzas()
    q = query.strip()
    m = re.match(r"^(.*?)\s*(\d+)$", q)
    name, number = (m.group(1), m.group(2)) if m else (q, None)
    poem = lookup._resolve_exact(name)[1] if name else ("Hovamol" if number else None)
    mine = [s for s in stanzas if s[0] == poem]
    if poem and mine:
        if number:
            if (poem, number) in stanzas:
                return poem, number, ""
            show = "!edda" if poem in _edda() else "!verse"
            return f"Stanza {number} of **{poem}** isn't Odin speaking. `{show} {poem} {number}` shows it."
        return (*rng.choice(mine), "")
    if poem in lookup._data.get("norse", {}):
        if "Hollander" in lookup._book_sources.get(poem, "") or poem in _edda():
            return f"Odin doesn't speak in **{poem}**. `!odin` alone picks from the poems where he does."
        # (the prose: Snorri's Edda, the sagas. !odin keeps to verse, the owner's choice, 2026-11-08)
        return f"`!odin` gives his words in verse; **{poem}** is prose. `!verse {poem} 1` reads it."
    if number and not name:
        return "Name the poem with the stanza: `!odin grimnismal 49`."
    return (*rng.choice(stanzas), q)


@bot.command(name="odin", aliases=["wotan", "woden", "othin", "odinn"])
async def cmd_odin(ctx, *, query: str = ""):
    """Odin's own words: a stanza he speaks in the Poetic Edda (the Hávamál, Grímnismál, and his part in
    Vafþrúðnismál, Hárbarðsljóð, Lokasenna and Baldr's Dreams), Eiríksmál, or one of his riddles as Gestumblindi.
    Usage: !odin · !odin grimnismal · !odin riddles · !odin 138 (the Hávamál's) · !odin [a question]
    (also !wotan, !woden) · !odin norse (· !odin norse grimnismal 49): in Old Norse beside the English"""
    if re.match(r"^(old\s*)?norse\b", query.strip(), re.I):
        await _odin_norse(ctx, re.sub(r"^(old\s*)?norse\b\s*", "", query.strip(), flags=re.I))
        return
    pick = _odin_pick(query)
    if isinstance(pick, str):
        await ctx.send(pick)
        return
    poem, stanza, question = pick
    await send_edda(ctx, "", question=question, chosen=(poem, stanza))


async def _odin_norse(ctx, query: str) -> None:
    """!odin norse: one of Odin's stanzas with its Old Norse beside it (the Edda's, Eiríksmál's, and all but one of
    his riddles). A question after it is ignored, as the Norse view has no place for one."""
    guild = getattr(ctx, "guild", None)
    if not tradition_enabled(guild.id if guild else None, "norse"):
        await ctx.send("The Norse texts are turned off on this server.")
        return
    norse = _edda_norse()
    pool = [(p, s) for p, s in _odin_stanzas() if s in norse.get(p, {})]
    if not pool:
        await ctx.send("⚠️ The Old Norse of the Edda isn't loaded.")
        return
    pick = _odin_pick(query) if query else None
    if isinstance(pick, str):
        await ctx.send(pick.replace("`!odin", "`!odin norse"))
        return
    if pick and not pick[2]:                                 # (a poem or stanza named)
        poem, stanza = pick[:2]
        if stanza not in norse.get(poem, {}):
            mine = [s for s in pool if s[0] == poem]
            if not mine or re.search(r"\d$", query):
                await ctx.send(f"Stanza {stanza} of **{poem}** has no Old Norse here. `!odin {poem} {stanza}` "
                               f"gives the English." if mine else
                               f"**{poem}** has no Old Norse here: `!odin norse` alone picks from the Edda's poems.")
                return
            poem, stanza = random.choice(mine)
    else:
        poem, stanza = random.choice(pool)
    log.info(f"RNG  odin norse             → {poem} {stanza} (user: {ctx.author})")
    _record(ctx, "edda", f"{poem} {stanza}")
    await send_norse(ctx, poem, stanza, odin=True)


async def send_edda(ctx, query: str, question: "str | None" = None, chosen: "tuple | None" = None) -> None:
    """!edda's reply (and !odin's, with the stanza chosen and the question given apart)."""
    guild = getattr(ctx, "guild", None)
    if not tradition_enabled(guild.id if guild else None, "norse"):
        await ctx.send("The Norse texts are turned off on this server.")
        return
    if not _edda():
        await ctx.send("⚠️ The Poetic Edda isn't loaded.")
        return
    pick = chosen or _edda_pick(query)
    if isinstance(pick, str):
        await ctx.send(pick)
        return
    poem, stanza = pick
    if question is None:
        named = lookup._resolve_exact(re.sub(r"\s*\d+$", "", query.strip()))[1] if query.strip() else None
        question = query if named not in _edda() and not re.fullmatch(r"\d+", query.strip()) else ""
    log.info(f"RNG  edda                   → {poem} {stanza} (user: {ctx.author})")
    # (one of Hollander's stanzas: Odin's speech in it alone; a riddle's answer under it, hidden till clicked)
    verse = ODIN_HOLLANDER.get(poem, {}).get(stanza, "") if chosen else ""
    # (Bellows's lines cut at the caesura, a half-line to a line, as in the Old Norse view: the owner, 2026-11-08)
    text = _half_lines(_edda_text(poem, stanza, verse))
    if chosen:
        text = _unquoted(text)
    embed = discord.Embed(title=f"🌲 {_edda_title(poem, stanza)}", description=text[:4096],
                          color=discord.Color.dark_green())
    if poem == "Heithreksgatur" and verse:
        answer = _unquoted(_edda_text(poem, stanza, "2"))
        if answer:
            embed.add_field(name="King Heithrek's answer", value=f"||{answer[:1000]}||", inline=False)
    norse = _norse_text(poem, stanza)            # (not in the message: the owner found it made it too big, 2026-11-08)
    embed.set_footer(text=f"{_edda_source(poem)} · !verse {poem} {stanza}")
    _ask(embed, question)
    _record(ctx, "edda", f"{poem} {stanza}")
    # (two rows: ◀ ▶ 🖌️ on the first; 🖼️ Card, 📜 Old Norse, ᚱ Runes on the second; six won't fit Discord's five)
    view = discord.ui.View(timeout=None)
    card = OracleCardButton("edda", f"{poem}|{stanza}|{verse}|o" if chosen else f"{poem}|{stanza}")
    card.item.row = 1
    view.add_item(card)
    if norse:
        view.add_item(NorseButton(f"{poem}|{stanza}{'|o' if chosen else ''}"))
        view.add_item(RunesButton(f"{poem}|{stanza}"))
    near = lookup.neighbours(f"{poem} {stanza}")
    for kind, side in (("p", "prev"), ("n", "next")):        # (◀ ▶ the stanzas either side, where there's one)
        if near.get(side):
            button = PassageButton(kind, f"{poem} {stanza}")
            button.item.row = 0
            view.add_item(button)
    for b in illustrations.buttons(illustrations.for_passage(poem, stanza), row=0):
        view.add_item(b)                                     # (🖌️ the poem's pictures: Collingwood's, Frølich's)
    await ctx.send(embed=embed, view=view)


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
