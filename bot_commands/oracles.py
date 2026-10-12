"""
!gematria, !virgil / !homer / !delphi, !oracle.
"""
import discord
import random
import re
from core import (
    bot,
    log,
    lookup,
    record_special_stat,
)
from core import ROOT

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
            with urllib.request.urlopen(req, timeout=15) as r:
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
                with urllib.request.urlopen(req, timeout=15) as r:
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
    embed.set_footer(text="The Aeneid — Virgil (trans. John Dryden, 1697)")
    record_special_stat(ctx.author.id, "virgil", f"Aeneid {book_num}.{line_num}")
    await ctx.send(embed=embed)


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
    record_special_stat(ctx.author.id, "homer", roll_str)
    await ctx.send(embed=embed)


@bot.command(name="delphi")
async def cmd_delphi(ctx):
    """Return a random Delphic maxim. Usage: !delphi"""
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
    embed.set_footer(text="Delphic Maxims — trans. Melissa Gold (Hellenion)")
    record_special_stat(ctx.author.id, "delphi", f"Maxim {num}")
    await ctx.send(embed=embed)


# ── !oracle — random verse from any oracular corpus ───────────────────────────

@bot.command(name="oracle")
async def cmd_oracle(ctx, *, question: str = ""):
    """Return a random verse from any oracular corpus. Usage: !oracle"""
    classical = lookup._data.get("classical", {})
    oracular_books = {
        "Delphic Maxims":      ("Delphic Maxims — trans. Melissa Gold (Hellenion)", "Delphi 1"),
        "Oracular Statements": ("Oracular Statements from Delphi", "Delphi 2"),
        "Chaldaean Oracles":   ("Chaldaean Oracles — ed. Westcott", "Chaldaean Oracles"),
        "Golden Verses":       ("Golden Verses of Pythagoras", "GVP"),
    }

    pool = []
    for book, (source, ref_prefix) in oracular_books.items():
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
    record_special_stat(ctx.author.id, "oracle", f"{ref_prefix} {num}")
    await ctx.send(embed=embed)
