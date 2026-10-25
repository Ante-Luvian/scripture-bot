"""
What a server has: its packs of commands and the traditions whose texts it sees (core.PACKS,
core.guild_packs, core.guild_traditions). When the bot joins a server it asks the admins what
the server is for -- which traditions, which church, whether to include divination -- and
switches off the rest; `!serversetup` (/setup traditions) asks again, and `!packs` switches one
pack or tradition on or off.

A switched-off pack's slash commands also leave that server's / menu. Discord can't hide a
global command in one server, so the pack commands are registered server by server instead
(sync_all, at startup); in DMs only the global ones show, and the rest still work typed.
"""
import discord
from discord import app_commands
from discord.ext import commands

from scripture_lookup import TRADITIONS, tradition
from core import (
    PACK_OF,
    PACKS,
    _load_guild_config,
    _update_guild_config,
    bot,
    command_enabled,
    guild_packs,
    guild_traditions,
    log,
)

# ── The choices ────────────────────────────────────────────────────────────────

# Every tradition but the Bible (which every server has), as the setup menu offers them
TRADITION_CHOICES = {
    "christian": ("Christianity", "⛪", "The Church Fathers, medieval and Reformation writers"),
    "apocrypha": ("Apocrypha", "👼", "Enoch, Jubilees, the Septuagint, the NT apocrypha"),
    "jewish": ("Judaism", "✡️", "Mishnah, Talmud, Midrash, Zohar, Maimonides"),
    "islamic": ("Islam", "☪️", "The Quran and hadith"),
    "sufi": ("Sufi poetry", "🌹", "Rumi, Hafiz, Omar Khayyam"),
    "hindu": ("Hinduism", "🕉️", "The Vedas, the Upanishads, the Gita"),
    "sikh": ("Sikhism", "🪯", "The Guru Granth Sahib"),
    "jain": ("Jainism", "🤚", "The Jain sutras"),
    "buddhist": ("Buddhism", "☸️", "The Pali Canon, the Dhammapada, the Lotus Sutra"),
    "chinese": ("Chinese classics", "☯️", "The Tao Te Ching, Confucius, the I Ching"),
    "shinto": ("Shinto", "⛩️", "The Kojiki and Nihongi"),
    "zoroastrian": ("Zoroastrianism", "🔥", "The Avesta"),
    "classical": ("Greek & Roman", "🏛️", "Homer, Plato, the Stoics and 600 more"),
    "gnostic": ("Gnostic & Hermetic", "🧿", "The Gospel of Thomas, Nag Hammadi, the Hermetica"),
    "norse": ("Norse", "🌲", "The Poetic Edda"),
    "finnish": ("Finnish", "🦢", "The Kalevala"),
    "celtic": ("Celtic", "☘️", "The Mabinogion"),
    "ballads": ("Folk ballads", "🎻", "Child's 305 English and Scottish ballads, with tunes"),
    "neareast": ("Ancient Near East", "🌙", "Gilgamesh, Enuma Elish, the Book of the Dead"),
    "mesoamerican": ("Mesoamerican", "🌽", "The Popol Vuh"),
    "bahai": ("Baháʼí", "🌍", "The writings of Baháʼu'lláh"),
    "lds": ("Latter-day Saint", "📯", "The Book of Mormon and the other LDS scriptures"),
}
CHURCHES = {
    "protestant": ("Protestant / evangelical", {"protestant"}),
    "anglican": ("Anglican", None),                      # asks how high church
    "catholic": ("Catholic", {"saints", "catholic_devotion", "catholic_teaching"}),
    "orthodox": ("Orthodox", {"saints", "orthodox"}),
    "all": ("All of them", {"protestant", "saints", "catholic_devotion", "catholic_teaching", "orthodox"}),
}
ANGLICAN = {
    "low": ("Low church / evangelical", {"protestant"}),
    "broad": ("Broad church", {"protestant", "saints"}),
    "high": ("High church / Anglo-Catholic", {"protestant", "saints", "catholic_devotion"}),
}
# traditions that don't on their own make a server a comparative-religion one
_CHRISTIAN_TEXTS = {"bible", "christian", "apocrypha"}


def packs_for(traditions: set, church_packs: set, divination: bool) -> set:
    """The packs that go with a server's answers."""
    packs = set()
    if "christian" in traditions:
        packs |= {"church"} | church_packs
    if "jewish" in traditions:
        packs.add("jewish_learning")
    if "islamic" in traditions:
        packs.add("islamic_prayer")
    if set(traditions) - _CHRISTIAN_TEXTS:
        packs.add("comparative")
    if divination:
        packs.add("divination")
    return packs


def save_choices(guild_id: int, packs: set, traditions: set) -> None:
    _update_guild_config(guild_id, packs=sorted(packs & set(PACKS)),
                         traditions=sorted((set(traditions) | {"bible"}) & set(TRADITIONS)))


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
    (The packs outgrew one field, and the last step of !serversetup failed with "Must be 1024 or fewer".)"""
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
    packs, traditions = guild_packs(guild_id), guild_traditions(guild_id)
    embed = discord.Embed(title=title, color=discord.Color.dark_gold())
    _fields(embed, "Commands", [f"{'✅' if key in packs else '▫️'} **{label}** (`{key}`) — {description}"
                                for key, (label, description, _) in PACKS.items()], "\n")
    _fields(embed, "Texts in !verse, !search, !theme and !discover",
            ["✅ **Bible** (always)\n" + f"{'✅' if k in traditions else '▫️'} {name} (`{k}`)"
             for k, (name, _, _) in list(TRADITION_CHOICES.items())[:1]]
            + [f"{'✅' if k in traditions else '▫️'} {name} (`{k}`)"
               for k, (name, _, _) in list(TRADITION_CHOICES.items())[1:]], " · ")
    embed.set_footer(text="Admins: !packs <name> on|off switches one · !serversetup (or /setup traditions) "
                          "asks the questions again · the Bible, study tools and games are always here")
    return embed


def configured(guild_id: int) -> bool:
    return "packs" in _load_guild_config().get(str(guild_id), {})


# ── The questions ──────────────────────────────────────────────────────────────

class SetupWizard(discord.ui.View):
    """Which traditions → (if Christianity) which church → (if Anglican) how high → divination?"""

    def __init__(self, guild_id: int, author_id: int = None):
        super().__init__(timeout=900)
        self.guild_id, self.author_id = guild_id, author_id
        self.traditions = set(guild_traditions(guild_id)) - {"bible"} if configured(guild_id) else set()
        self.church_packs: set = set()
        self.message = None
        self.show_traditions()

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        member = interaction.user
        if not getattr(getattr(member, "guild_permissions", None), "administrator", False):
            await interaction.response.send_message("🔒 Only server admins can change this.", ephemeral=True)
            return False
        return True

    # each step replaces the buttons and the question
    def show_traditions(self) -> None:
        self.clear_items()
        menu = discord.ui.Select(placeholder="Pick any number (or none, for just the Bible)",
                                 min_values=0, max_values=len(TRADITION_CHOICES), options=[
            discord.SelectOption(label=name, value=key, emoji=emoji, description=description,
                                 default=key in self.traditions)
            for key, (name, emoji, description) in TRADITION_CHOICES.items()])

        async def picked(interaction: discord.Interaction):
            self.traditions = set(menu.values)
            await interaction.response.defer()
        menu.callback = picked
        self.add_item(menu)
        self._button("Next ▶", discord.ButtonStyle.primary, self.after_traditions)
        self._button("Everything", discord.ButtonStyle.secondary, self.everything)
        self.question = ("**1. Which traditions is this server for?** I'm a library of sacred texts from all over "
                         "the world. Pick the ones you want; the rest stay out of sight. The Bible is always here.\n"
                         "*Everything* keeps the whole library, for comparative religion.")

    def show_church(self) -> None:
        self.clear_items()
        for key, (label, _) in CHURCHES.items():
            self._button(label, discord.ButtonStyle.primary, self._church(key))
        self.question = ("**2. Which church?** This decides the prayers and devotions I offer: the Prayer Book's "
                         "daily office, the Rosary and the Catechism, the Orthodox liturgy and icons, the saints.")

    def show_anglican(self) -> None:
        self.clear_items()
        for key, (label, _) in ANGLICAN.items():
            self._button(label, discord.ButtonStyle.primary, self._anglican(key))
        self.question = ("**How high church?** Everyone gets the Prayer Book's daily office. Broad adds the saint "
                         "of the day; High also adds the Rosary, the Angelus and Latin chant.")

    def show_divination(self) -> None:
        self.clear_items()
        self._button("Yes, include them", discord.ButtonStyle.secondary, self._divination(True))
        self._button("No thanks", discord.ButtonStyle.primary, self._divination(False))
        self.question = ("**Last: divination?** Oracles and fortune-telling from old traditions: the Sortes "
                         "Virgilianae, the I Ching, the tarot, Delphic maxims, opening the Bible at random — "
                         "plus William Blake's visionary books. Some servers enjoy them; some would rather not.")

    def _button(self, label, style, callback) -> None:
        button = discord.ui.Button(label=label, style=style)
        button.callback = callback
        self.add_item(button)

    def embed(self) -> discord.Embed:
        return discord.Embed(title="⚙️ Setting up ScriptureBot", description=self.question,
                             color=discord.Color.dark_gold())

    async def _show(self, interaction: discord.Interaction) -> None:
        await interaction.response.edit_message(embed=self.embed(), view=self)

    # the answers
    async def after_traditions(self, interaction: discord.Interaction) -> None:
        if "christian" in self.traditions:
            self.show_church()
        else:
            self.show_divination()
        await self._show(interaction)

    async def everything(self, interaction: discord.Interaction) -> None:
        await self.finish(interaction, set(PACKS), set(TRADITIONS))

    def _church(self, key):
        async def callback(interaction: discord.Interaction):
            packs = CHURCHES[key][1]
            if packs is None:
                self.show_anglican()
            else:
                self.church_packs = set(packs)
                self.show_divination()
            await self._show(interaction)
        return callback

    def _anglican(self, key):
        async def callback(interaction: discord.Interaction):
            self.church_packs = set(ANGLICAN[key][1])
            self.show_divination()
            await self._show(interaction)
        return callback

    def _divination(self, wanted: bool):
        async def callback(interaction: discord.Interaction):
            await self.finish(interaction, packs_for(self.traditions | {"bible"}, self.church_packs, wanted),
                              self.traditions | {"bible"})
        return callback

    async def finish(self, interaction: discord.Interaction, packs: set, traditions: set) -> None:
        save_choices(self.guild_id, packs, traditions)
        self.stop()
        await interaction.response.edit_message(
            embed=summary_embed(self.guild_id, "✅ All set — here's what this server has"), view=None)
        await apply(interaction.guild)

    async def on_timeout(self):
        if self.message is not None:
            try:
                await self.message.edit(view=None)
            except discord.HTTPException:
                pass


class WelcomeView(discord.ui.View):
    """The button on the bot's welcome message. Persistent, so it still works after a restart."""

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Set me up", emoji="⚙️", style=discord.ButtonStyle.primary,
                       custom_id="scripture:serversetup")
    async def start(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.guild is None:
            return
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("🔒 Only server admins can set me up.", ephemeral=True)
            return
        wizard = SetupWizard(interaction.guild.id, interaction.user.id)
        await interaction.response.send_message(embed=wizard.embed(), view=wizard, ephemeral=True)


def welcome_embed() -> discord.Embed:
    embed = discord.Embed(
        title="📖 Thanks for adding ScriptureBot!",
        description=(
            "I'm a library of sacred and ancient texts: the Bible in dozens of translations with study tools, "
            "and the scriptures and classics of many other traditions. Try `!verse John 3:16`; `!help` lists "
            "everything.\n\n"
            "**First, admins: tell me what this server is for.** Press **Set me up** and answer three quick "
            "questions (which traditions, which church, whether you'd like oracles and divination). I'll put "
            "away the commands you won't use, so your `/` menu stays tidy. Until then, everything is on.\n\n"
            "**Also worth setting up** (with `/setup`):\n"
            "• `/setup changelog` then `/setup intro` — a channel that introduces me to everyone, every command "
            "explained, where I also announce my updates\n"
            "• `/setup votd` — a daily Verse of the Day · `/setup quiz` — a daily quiz question"),
        color=discord.Color.dark_gold())
    embed.set_footer(text="Change your answers any time: /setup traditions, or /setup packs for one at a time")
    return embed


async def welcome(guild: discord.Guild) -> None:
    """On joining a server: its / menu (everything, until it chooses), and the welcome."""
    try:
        await sync_guild(guild)
    except discord.HTTPException as e:
        log.warning(f"Couldn't register the pack commands in new server {guild.id}: {e}")
    channel = guild.system_channel
    if channel is None or not channel.permissions_for(guild.me).send_messages:
        channel = next((c for c in guild.text_channels if c.permissions_for(guild.me).send_messages), None)
    try:
        if channel is not None:
            await channel.send(embed=welcome_embed(), view=WelcomeView())
        elif guild.owner is not None:
            await guild.owner.send(f"Thanks for adding me to **{guild.name}**! I couldn't post there, so: run "
                                   "`/setup traditions` in the server to choose what it's for.")
    except discord.HTTPException:
        pass


# ── The commands ───────────────────────────────────────────────────────────────

async def send_wizard(ctx) -> None:
    wizard = SetupWizard(ctx.guild.id, ctx.author.id)
    wizard.message = await ctx.send(embed=wizard.embed(), view=wizard)


@bot.command(name="serversetup", aliases=["onboard"])
@commands.guild_only()
@commands.has_permissions(administrator=True)
async def cmd_serversetup(ctx):
    """(Admins) Choose what this server is for: its traditions, church and whether to include divination.
    Usage: !serversetup"""
    await send_wizard(ctx)


def resolve(name: str):
    """("pack", key) or ("texts", key) for what an admin typed, or None."""
    name = name.strip().lower().replace(" ", "_")
    if name in PACKS:
        return "pack", name
    if name in ("bible",):
        return None
    key = tradition(name.replace("_", " "))
    return ("texts", key) if key and key != "bible" else None


@bot.command(name="packs", aliases=["pack"])
@commands.guild_only()
@commands.has_permissions(administrator=True)
async def cmd_packs(ctx, name: str = "", state: str = ""):
    """(Admins) Switch one pack of commands, or one tradition's texts, on or off.
    Usage: !packs  |  !packs divination off  |  !packs hindu on"""
    if not name:
        await ctx.send(embed=summary_embed(ctx.guild.id))
        return
    found = resolve(name)
    state = state.lower()
    if found is None or state not in ("on", "off"):
        await ctx.send("Usage: `!packs <name> on` or `!packs <name> off`, where the name is a pack ("
                       + ", ".join(f"`{k}`" for k in PACKS) + ") or a tradition (`hindu`, `buddhist`, `jewish`…). "
                       "`!packs` alone shows them all.")
        return
    kind, key = found
    packs, traditions = set(guild_packs(ctx.guild.id)), set(guild_traditions(ctx.guild.id))
    target = packs if kind == "pack" else traditions
    (target.add if state == "on" else target.discard)(key)
    save_choices(ctx.guild.id, packs, traditions)
    label = PACKS[key][0] if kind == "pack" else TRADITION_CHOICES[key][0]
    await ctx.send(f"{'✅' if state == 'on' else '▫️'} **{label}** is now {state} in this server.")
    await apply(ctx.guild)


async def pack_name_autocomplete(interaction: discord.Interaction, current: str):
    current = current.lower()
    names = [(f"{label} (commands)", key) for key, (label, _, _) in PACKS.items()]
    names += [(f"{name} (texts)", key) for key, (name, _, _) in TRADITION_CHOICES.items()]
    return [app_commands.Choice(name=label[:100], value=key)
            for label, key in names if current in label.lower() or current in key][:25]
