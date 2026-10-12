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
    bot,
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

@bot.tree.command(name="verse", description="Look up a scripture verse")
@app_commands.describe(reference="e.g. John 3:16 | John 3:16 ESV | John 3:16 Knox | John 3:16 KJV ESV NASB")
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
