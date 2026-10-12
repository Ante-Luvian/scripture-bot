"""
Slash-command wrappers for prefix commands defined in other modules.
"""
import discord
import re
from discord import app_commands
from bot_commands.books import (
    list_books,
)
from bot_commands.church import (
    _load_canon,
    _load_ccc,
    cmd_catena,
    cmd_summa,
)
from core import (
    GUILD_FEATURES,
    bot,
    lookup,
)
from bot_commands.oracles import (
    cmd_delphi,
    cmd_gematria,
    cmd_homer,
    cmd_oracle,
)
from bot_commands.personal import (
    cmd_save,
    cmd_saved,
)
from bot_commands.verse import (
    cmd_discover,
    cmd_study,
    verse_prefix,
)
from bot_commands.votd import (
    _send_votd,
    _send_votd_extended,
    _send_votd_full,
    cmd_subscribe,
    cmd_unsubscribe,
)

# ── Slash commands ─────────────────────────────────────────────────────────────

def book_suggestions(current: str, limit: int = 25) -> list[str]:
    """Book names to suggest while typing a /verse reference: Bible books
    first (in Bible order), then everything else alphabetically; names that
    start with what's typed before names that merely contain it; an
    abbreviation ("Jn") suggests its book ("John"). Once a chapter number
    has been typed ("John 3"), just echo the text back."""
    text = current.strip()
    if re.search(r"\s\d", text):
        return [text[:100]]
    q = text.lower()
    from scripture_lookup import ALIASES, BIBLE_NT, BIBLE_OT
    bible = BIBLE_OT + BIBLE_NT
    others = sorted({v[1] for v in lookup._book_index.values()} - set(bible))
    ordered = bible + others
    starts = [b for b in ordered if b.lower().startswith(q)]
    via_alias = [ALIASES[a] for a in sorted(ALIASES) if a.startswith(q) and q and ALIASES[a] in ordered]
    contains = [b for b in ordered if q and q in b.lower()]
    seen, out = set(), []
    for b in starts + via_alias + contains:
        if b not in seen:
            seen.add(b)
            out.append(b[:100])
        if len(out) >= limit:
            break
    return out


async def _verse_autocomplete(interaction: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
    return [app_commands.Choice(name=b, value=b) for b in book_suggestions(current)]


@bot.tree.command(name="verse", description="Look up a scripture verse")
@app_commands.describe(reference="e.g. John 3:16 | John 3:16 ESV | John 3:16 Knox | John 3:16 KJV ESV NASB")
@app_commands.autocomplete(reference=_verse_autocomplete)
async def verse_slash(interaction: discord.Interaction, reference: str):
    await interaction.response.defer()
    ctx = await bot.get_context(interaction)
    await verse_prefix(ctx, reference=reference)

@bot.tree.command(name="ccc", description="Look up a paragraph of the Catechism of the Catholic Church")
@app_commands.describe(number="Paragraph number (1–2865)")
async def ccc_slash(interaction: discord.Interaction, number: int):
    await interaction.response.defer()
    data = _load_ccc()
    if data is None:
        await interaction.followup.send("⚠️ catechism.json not found."); return
    text = data.get(number)
    if text is None:
        await interaction.followup.send(f"⚠️ Paragraph {number} not found."); return
    text = re.sub(r'\*+', '', text)
    if len(text) > 4000: text = text[:3997] + "…"
    embed = discord.Embed(title=f"CCC {number}", description=text, color=discord.Color.gold())
    embed.set_footer(text="Catechism of the Catholic Church")
    await interaction.followup.send(embed=embed)

@bot.tree.command(name="canon", description="Look up a canon of the Code of Canon Law")
@app_commands.describe(number="Canon number (1–1751)")
async def canon_slash(interaction: discord.Interaction, number: int):
    await interaction.response.defer()
    data = _load_canon()
    if data is None:
        await interaction.followup.send("⚠️ canon.json not found."); return
    text = data.get(number)
    if text is None:
        await interaction.followup.send(f"⚠️ Canon {number} not found."); return
    text = re.sub(r'\*+', '', text)
    if len(text) > 4000: text = text[:3997] + "…"
    embed = discord.Embed(title=f"Canon {number}", description=text, color=discord.Color.dark_red())
    embed.set_footer(text="Code of Canon Law (1983)")
    await interaction.followup.send(embed=embed)

@bot.tree.command(name="catena", description="Patristic commentary on a Bible verse from catenabible.com")
@app_commands.describe(reference="e.g. John 3:16 | Romans 8:28 | Matthew 5:3")
async def catena_slash(interaction: discord.Interaction, reference: str):
    await interaction.response.defer()
    ctx = await bot.get_context(interaction)
    await cmd_catena(ctx, reference=reference)

@bot.tree.command(name="gematria", description="Look up gematria values for a word or number")
@app_commands.describe(query="Word, phrase, or number to look up")
async def gematria_slash(interaction: discord.Interaction, query: str):
    await interaction.response.defer()
    ctx = await bot.get_context(interaction)
    await cmd_gematria(ctx, query=query)

@bot.tree.command(name="votd", description="Verse of the Day")
@app_commands.describe(translation='Optional translation (e.g. ESV), "full", or "extended"')
async def votd_slash(interaction: discord.Interaction, translation: str = ""):
    await interaction.response.defer()
    arg = translation.strip()
    if arg.lower() == "full":
        await _send_votd_full(interaction.channel)
    elif arg.lower() == "extended":
        await _send_votd_extended(interaction.channel)
    else:
        await _send_votd(interaction.channel, translation=arg)

@bot.tree.command(name="delphi", description="Random Delphic maxim")
@app_commands.describe(question="Optional question for the oracle")
async def delphi_slash(interaction: discord.Interaction, question: str = ""):
    await interaction.response.defer()
    ctx = await bot.get_context(interaction)
    await cmd_delphi(ctx, question=question)

@bot.tree.command(name="oracle", description="Random verse from an oracular corpus")
@app_commands.describe(question="Optional question for the oracle")
async def oracle_slash(interaction: discord.Interaction, question: str = ""):
    await interaction.response.defer()
    ctx = await bot.get_context(interaction)
    await cmd_oracle(ctx, question=question)

@bot.tree.command(name="homer", description="Roll three dice and receive a Homeric oracle")
@app_commands.describe(question="Optional question for the oracle")
async def homer_slash(interaction: discord.Interaction, question: str = ""):
    await interaction.response.defer()
    ctx = await bot.get_context(interaction)
    await cmd_homer(ctx, question=question)

@bot.tree.command(name="books", description="List available scripture collections")
@app_commands.describe(section="Optional section name to expand")
async def books_slash(interaction: discord.Interaction, section: str = ""):
    await interaction.response.defer()
    ctx = await bot.get_context(interaction)
    await list_books(ctx, section=section)

@bot.tree.command(name="summa", description="Look up an article from the Summa Theologica")
@app_commands.describe(reference="e.g. I.2.3 | I-II.109.1 | II-II.23 | random")
async def summa_slash(interaction: discord.Interaction, reference: str = ""):
    await interaction.response.defer()
    ctx = await bot.get_context(interaction)
    await cmd_summa(ctx, reference=reference.strip())

@bot.tree.command(name="discover", description="Random passage from any loaded tradition (scripture, patristics, classical texts, and more)")
async def discover_slash(interaction: discord.Interaction):
    await interaction.response.defer()
    ctx = await bot.get_context(interaction)
    await cmd_discover(ctx)

@bot.tree.command(name="study", description="Look up a verse and its patristic commentary together")
@app_commands.describe(reference="e.g. John 3:16")
async def study_slash(interaction: discord.Interaction, reference: str):
    await interaction.response.defer()
    ctx = await bot.get_context(interaction)
    await cmd_study(ctx, reference=reference)

@bot.tree.command(name="save", description="Save a verse to your personal bookmark list")
@app_commands.describe(reference="e.g. John 3:16")
async def save_slash(interaction: discord.Interaction, reference: str):
    await interaction.response.defer()
    ctx = await bot.get_context(interaction)
    await cmd_save(ctx, reference=reference)

@bot.tree.command(name="saved", description="List your saved verses")
async def saved_slash(interaction: discord.Interaction):
    await interaction.response.defer()
    ctx = await bot.get_context(interaction)
    await cmd_saved(ctx)

@bot.tree.command(name="subscribe", description="Get the daily Verse of the Day sent to you by DM")
async def subscribe_slash(interaction: discord.Interaction):
    await interaction.response.defer()
    ctx = await bot.get_context(interaction)
    await cmd_subscribe(ctx)

@bot.tree.command(name="unsubscribe", description="Stop the daily DM Verse of the Day")
async def unsubscribe_slash(interaction: discord.Interaction):
    await interaction.response.defer()
    ctx = await bot.get_context(interaction)
    await cmd_unsubscribe(ctx)


# ── Slash versions of the remaining commands ──────────────────────────────────
# Every user-facing prefix command now has a slash version (see
# tests/test_slash_parity.py). They look the prefix command up by name and
# call it directly -- which skips the prefix command's own checks, so the
# admin ones carry Discord-side permissions instead (hidden from non-admins
# by default, enforced, server-only).

def _command(name: str):
    return bot.get_command(name)


async def _slash_ctx(interaction: discord.Interaction):
    await interaction.response.defer()
    return await bot.get_context(interaction)


class _WithChannelMention:
    """The setup commands read their channel from the typed message's
    mentions; a slash command's message has none, so supply the picked one."""

    def __init__(self, message, channel):
        self._message = message
        self.channel_mentions = [channel] if channel is not None else []

    def __getattr__(self, name):
        return getattr(self._message, name)


def _admin_only(func):
    func = app_commands.guild_only()(func)
    func = app_commands.checks.has_permissions(administrator=True)(func)
    return app_commands.default_permissions(administrator=True)(func)


@bot.tree.command(name="virgil", description="Sortes Vergilianae: a random line from Virgil's Aeneid as your oracle")
@app_commands.describe(question="Optional question for the oracle")
async def virgil_slash(interaction: discord.Interaction, question: str = ""):
    await _command("virgil")(await _slash_ctx(interaction), question=question)


@bot.tree.command(name="search", description="Search the Bible for a word or phrase")
@app_commands.describe(query="e.g. shepherd, or shepherd ESV for another translation")
async def search_slash(interaction: discord.Interaction, query: str):
    await _command("search")(await _slash_ctx(interaction), query=query)


@bot.tree.command(name="prayer", description="A random prayer from the 1662 Book of Common Prayer")
async def prayer_slash(interaction: discord.Interaction):
    await _command("prayer")(await _slash_ctx(interaction))


@bot.tree.command(name="collect", description="The Collect (short prayer) of the day")
@app_commands.describe(date="Optional date, YYYY-MM-DD")
async def collect_slash(interaction: discord.Interaction, date: str = ""):
    await _command("collect")(await _slash_ctx(interaction), date_raw=date)


@bot.tree.command(name="mp", description="Today's Morning Prayer readings (Book of Common Prayer)")
@app_commands.describe(date="Optional date, YYYY-MM-DD")
async def mp_slash(interaction: discord.Interaction, date: str = ""):
    await _command("mp")(await _slash_ctx(interaction), date_raw=date)


@bot.tree.command(name="ep", description="Today's Evening Prayer readings (Book of Common Prayer)")
@app_commands.describe(date="Optional date, YYYY-MM-DD")
async def ep_slash(interaction: discord.Interaction, date: str = ""):
    await _command("ep")(await _slash_ctx(interaction), date_raw=date)


@bot.tree.command(name="psalm", description="Today's appointed psalms (Coverdale Psalter)")
@app_commands.describe(period="Morning or evening psalms (default: by time of day)")
@app_commands.choices(period=[app_commands.Choice(name="Morning", value="mp"),
                              app_commands.Choice(name="Evening", value="ep")])
async def psalm_slash(interaction: discord.Interaction, period: str = ""):
    await _command("psalm")(await _slash_ctx(interaction), args=period)


@bot.tree.command(name="stats", description="How the bot has been used: top verses, books and commands")
async def stats_slash(interaction: discord.Interaction):
    await _command("stats")(await _slash_ctx(interaction))


@bot.tree.command(name="export", description="Download a book or chapters as a text file")
@app_commands.describe(reference="e.g. John, or John 1-5, or John 3")
async def export_slash(interaction: discord.Interaction, reference: str):
    await _command("export")(await _slash_ctx(interaction), arg=reference)


@bot.tree.command(name="unsave", description="Remove a saved verse by its number in /saved")
@app_commands.describe(number="The verse's number in your /saved list")
async def unsave_slash(interaction: discord.Interaction, number: int):
    await _command("unsave")(await _slash_ctx(interaction), number)


@bot.tree.command(name="features", description="(Admins) Turn optional server features on or off")
@app_commands.describe(name="Which feature (leave empty to see them all)", state="on or off")
@app_commands.choices(name=[app_commands.Choice(name=k, value=k) for k in GUILD_FEATURES],
                      state=[app_commands.Choice(name="on", value="on"), app_commands.Choice(name="off", value="off")])
@_admin_only
async def features_slash(interaction: discord.Interaction, name: str = "", state: str = ""):
    await _command("features")(await _slash_ctx(interaction), name, state)


@bot.tree.command(name="votdsetup", description="(Admins) Configure the daily Verse of the Day post")
@app_commands.describe(action="What to change", channel="For 'channel'", value="For 'time' (HH:MM, UTC) or 'mode' (basic/full/extended)")
@app_commands.choices(action=[app_commands.Choice(name=a, value=a) for a in ("show", "channel", "time", "mode", "off")])
@_admin_only
async def votdsetup_slash(interaction: discord.Interaction, action: str = "show",
                          channel: discord.TextChannel = None, value: str = ""):
    ctx = await _slash_ctx(interaction)
    ctx.message = _WithChannelMention(ctx.message, channel)
    await _command("votdsetup")(ctx, "" if action == "show" else action, arg=value)


@bot.tree.command(name="oraclesetup", description="(Admins) Configure the daily oracle post")
@app_commands.describe(action="What to change", channel="For 'channel'",
                       value="For 'time' (HH:MM, UTC) or 'kind' (any/virgil/homer/delphi/oracle)")
@app_commands.choices(action=[app_commands.Choice(name=a, value=a) for a in ("show", "channel", "time", "kind", "test", "off")])
@_admin_only
async def oraclesetup_slash(interaction: discord.Interaction, action: str = "show",
                            channel: discord.TextChannel = None, value: str = ""):
    ctx = await _slash_ctx(interaction)
    ctx.message = _WithChannelMention(ctx.message, channel)
    await _command("oraclesetup")(ctx, "" if action == "show" else action, arg=value)


@bot.tree.command(name="changelogsetup", description="(Admins) Choose where the bot announces her updates")
@app_commands.describe(channel="The updates channel (leave empty to see the current one)", off="Stop announcing updates")
@_admin_only
async def changelogsetup_slash(interaction: discord.Interaction, channel: discord.TextChannel = None, off: bool = False):
    ctx = await _slash_ctx(interaction)
    ctx.message = _WithChannelMention(ctx.message, channel)
    await _command("changelogsetup")(ctx, arg="off" if off else (channel.mention if channel else ""))


@bot.tree.command(name="changelogintro", description="(Admins) Post the full introduction + latest updates in the updates channel")
@app_commands.describe(fresh="First delete my own earlier messages there, so the introduction comes first")
@_admin_only
async def changelogintro_slash(interaction: discord.Interaction, fresh: bool = False):
    await _command("changelogintro")(await _slash_ctx(interaction), arg="fresh" if fresh else "")
