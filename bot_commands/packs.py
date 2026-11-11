"""
What a server has: its packs of commands (core.PACKS, core.guild_packs). Every pack is on until an
admin switches one off with `!packs` (/setup packs). Every server has every text. (The !serversetup
questionnaire -- which traditions, which church, divination? -- was removed at the owner's request,
2026-11-11.)

A switched-off pack's slash commands also leave that server's / menu. Discord can't hide a
global command in one server, so the pack commands are registered server by server instead
(sync_all, at startup); in DMs only the global ones show, and the rest still work typed.
"""
import discord
from discord import app_commands
from discord.ext import commands

from core import (
    PACK_OF,
    PACKS,
    _update_guild_config,
    bot,
    command_enabled,
    guild_packs,
    log,
)

def save_choices(guild_id: int, packs: set) -> None:
    _update_guild_config(guild_id, packs=sorted(packs & set(PACKS)))


# ── Slash commands, server by server ────────────────────────────────────────────

OPTIONAL: dict = {}      # slash commands that belong to a pack, taken out of the global tree


def split_tree(tree) -> None:
    """Take the pack commands out of the global commands (once): they're added per server."""
    if OPTIONAL:
        return
    for command in list(tree.get_commands(type=discord.AppCommandType.chat_input)):
        if command.name in PACK_OF:
            OPTIONAL[command.name] = tree.remove_command(command.name)


async def sync_guild(guild, tree=None) -> int:
    """Register this server's pack commands with Discord; how many it has."""
    tree = tree or bot.tree
    tree.clear_commands(guild=guild)
    for name, command in OPTIONAL.items():
        if command_enabled(guild.id, name):
            tree.add_command(command, guild=guild)
    synced = await tree.sync(guild=guild)
    return len(synced)


async def sync_all() -> int:
    """At startup: the global slash commands, then each server's own. Returns the global count."""
    split_tree(bot.tree)
    synced = await bot.tree.sync()
    for guild in bot.guilds:
        try:
            await sync_guild(guild)
        except discord.HTTPException as e:
            log.warning(f"Couldn't register the pack commands in {guild.name} ({guild.id}): {e}")
    log.info(f"Pack commands registered in {len(bot.guilds)} server(s)")
    return len(synced)


async def apply(guild) -> None:
    """After a server's choices change: its / menu, and its posted introduction."""
    if guild is not None:
        try:
            await sync_guild(guild)
        except discord.HTTPException as e:
            log.warning(f"Couldn't update the pack commands in {guild.id}: {e}")
    from bot_commands.changelog import refresh_introductions
    try:
        await refresh_introductions(bot)
    except Exception as e:
        log.warning(f"Couldn't refresh introductions: {e}")


# ── What a server has ──────────────────────────────────────────────────────────

def _fields(embed: discord.Embed, name: str, items: list, sep: str) -> None:
    """`items` joined by `sep` in as many fields as Discord's 1,024 characters a field need, none split.
    (The packs outgrew one field, and a summary once failed with "Must be 1024 or fewer".)"""
    chunks, cur = [], ""
    for item in items:
        if cur and len(cur) + len(sep) + len(item) > 1024:
            chunks.append(cur)
            cur = item
        else:
            cur = f"{cur}{sep}{item}" if cur else item
    for i, chunk in enumerate(chunks + [cur]):
        embed.add_field(name=name if i == 0 else "​", value=chunk, inline=False)


def summary_embed(guild_id: int, title: str = "⚙️ What this server has") -> discord.Embed:
    packs = guild_packs(guild_id)
    embed = discord.Embed(title=title, color=discord.Color.dark_gold())
    _fields(embed, "Commands", [f"{'✅' if key in packs else '▫️'} **{label}** (`{key}`) — {description}"
                                for key, (label, description, _) in PACKS.items()], "\n")
    embed.add_field(name="Texts", value="The whole library, every tradition's texts, is here on every server.",
                    inline=False)
    embed.set_footer(text="Admins: !packs <name> on|off switches one (or /setup packs) · the Bible, study "
                          "tools and games are always here")
    return embed


class WelcomeView(discord.ui.View):
    """The "Set me up" button on welcome messages posted before 2026-11-11, when the setup questions were removed:
    still answered (persistent), so pressing it doesn't fail."""

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Set me up", emoji="⚙️", style=discord.ButtonStyle.primary,
                       custom_id="scripture:serversetup")
    async def start(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(
            "There's nothing to set up any more: everything is on. Admins can switch a group of commands off with "
            "`!packs` (or `/setup packs`).", ephemeral=True)


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
            "• `/setup votd` — a daily Verse of the Day · `/setup quiz` — a daily quiz question\n"
            "• `!packs` — switch off groups of commands your server won't use (the Rosary, divination...)"),
        color=discord.Color.dark_gold())


async def welcome(guild: discord.Guild) -> None:
    """On joining a server: its / menu, and the welcome."""
    try:
        await sync_guild(guild)
    except discord.HTTPException as e:
        log.warning(f"Couldn't register the pack commands in new server {guild.id}: {e}")
    channel = guild.system_channel
    if channel is None or not channel.permissions_for(guild.me).send_messages:
        channel = next((c for c in guild.text_channels if c.permissions_for(guild.me).send_messages), None)
    try:
        if channel is not None:
            await channel.send(embed=welcome_embed())
    except discord.HTTPException:
        pass


# ── The command ────────────────────────────────────────────────────────────────

def resolve(name: str):
    """The pack an admin typed, or None."""
    name = name.strip().lower().replace(" ", "_")
    return name if name in PACKS else None


@bot.command(name="packs", aliases=["pack"])
@commands.guild_only()
@commands.has_permissions(administrator=True)
async def cmd_packs(ctx, name: str = "", state: str = ""):
    """(Admins) Switch one pack of commands on or off.
    Usage: !packs  |  !packs divination off  |  !packs saints on"""
    if not name:
        await ctx.send(embed=summary_embed(ctx.guild.id))
        return
    found = resolve(name)
    state = state.lower()
    if found is None or state not in ("on", "off"):
        await ctx.send("Usage: `!packs <name> on` or `!packs <name> off`, where the name is a pack of commands ("
                       + ", ".join(f"`{k}`" for k in PACKS) + "). `!packs` alone shows them all. (Every server "
                       "has every tradition's texts; only commands can be switched off.)")
        return
    key = found
    packs = set(guild_packs(ctx.guild.id))
    (packs.add if state == "on" else packs.discard)(key)
    save_choices(ctx.guild.id, packs)
    label = PACKS[key][0]
    await ctx.send(f"{'✅' if state == 'on' else '▫️'} **{label}** is now {state} in this server.")
    await apply(ctx.guild)


async def pack_name_autocomplete(interaction: discord.Interaction, current: str):
    current = current.lower()
    names = [(label, key) for key, (label, _, _) in PACKS.items()]
    return [app_commands.Choice(name=label[:100], value=key)
            for label, key in names if current in label.lower() or current in key][:25]
