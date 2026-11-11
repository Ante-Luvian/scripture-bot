"""
Joining a server: the welcome message, and the slash commands. Every server has every command and every text.
(The !serversetup questionnaire and the !packs switches that turned groups of commands off server by server were
removed at the owner's request, 2026-11-11.)
"""
import discord

from core import bot, log


async def sync_all() -> int:
    """At startup: the slash commands, all global. Returns how many.

    Until 2026-11-11 the commands of a pack were registered server by server, so a server could drop them; those
    registrations are cleared here, or each server would show those commands twice."""
    synced = await bot.tree.sync()
    for guild in bot.guilds:
        try:
            if await bot.tree.fetch_commands(guild=guild):
                bot.tree.clear_commands(guild=guild)
                await bot.tree.sync(guild=guild)
        except discord.HTTPException as e:
            log.warning(f"Couldn't clear the old server commands in {guild.name} ({guild.id}): {e}")
    return len(synced)


class WelcomeView(discord.ui.View):
    """The "Set me up" button on welcome messages posted before 2026-11-11, when the setup questions were removed:
    still answered (persistent), so pressing it doesn't fail."""

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Set me up", emoji="⚙️", style=discord.ButtonStyle.primary,
                       custom_id="scripture:serversetup")
    async def start(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(
            "There's nothing to set up any more: every command and every text is here. `/setup` has the "
            "optional extras (a changelog channel, a daily verse...).", ephemeral=True)


def welcome_embed() -> discord.Embed:
    return discord.Embed(
        title="📖 Thanks for adding ScriptureBot!",
        description=(
            "I'm a library of sacred and ancient texts: the Bible in dozens of translations with study tools, "
            "and the scriptures and classics of many other traditions. Try `!verse John 3:16`; `!help` lists "
            "everything.\n\n"
            "**Worth setting up** (with `/setup`):\n"
            "• `/setup changelog` then `/setup intro` — a channel that introduces me to everyone, every command "
            "explained, where I also announce my updates\n"
            "• `/setup votd` — a daily Verse of the Day · `/setup quiz` — a daily quiz question"),
        color=discord.Color.dark_gold())


async def welcome(guild: discord.Guild) -> None:
    """On joining a server: the welcome, in its system channel or the first it can post in."""
    channel = guild.system_channel
    if channel is None or not channel.permissions_for(guild.me).send_messages:
        channel = next((c for c in guild.text_channels if c.permissions_for(guild.me).send_messages), None)
    try:
        if channel is not None:
            await channel.send(embed=welcome_embed())
    except discord.HTTPException:
        pass
