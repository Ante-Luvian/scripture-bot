"""
!daily -- one command for the server's daily posts (2026-11-08). There were ten admin commands,
!votdsetup, !oraclesetup, !quizsetup, !verslesetup, !hymndaysetup, !saintsetup, !astrosetup,
!angelussetup, !troparionsetup and !learningsetup, eight of them never used; !daily lists what
this server posts and when, and "!daily saint channel #saints" hands on to !saintsetup, which
does the work. The old names still work (hidden from !help); /setup has a subcommand for each.
!changelogsetup isn't here: the updates channel isn't a daily post.
"""
import discord
from discord.ext import commands

from core import _load_guild_config, bot

# kind -> (label, the command it hands on to, its settings' prefix in guild_config.json, other names)
KINDS = {
    "votd":      ("📖 Verse of the Day", "votdsetup", "votd", ("verse", "verseoftheday")),
    "oracle":    ("🔮 A daily oracle", "oraclesetup", "oracle", ("oracles",)),
    "quiz":      ("🎲 A quiz question", "quizsetup", "quiz", ()),
    "versle":    ("🟩 The Versle puzzle", "verslesetup", "versle", ()),
    "hymn":      ("🎵 The hymn of the day", "hymndaysetup", "hymnday", ("hymnday",)),
    "saint":     ("😇 The saint of the day", "saintsetup", "saintday", ("saints",)),
    "astro":     ("🪐 The day's sky (!planets, !horoscope)", "astrosetup", "astro", ("planets", "horoscope", "sky")),
    "angelus":   ("🔔 The Angelus", "angelussetup", "angelus", ()),
    "troparion": ("☦️ The troparia of the day", "troparionsetup", "troparion", ("troparia",)),
    "learning":  ("✡️ The day's Jewish learning", "learningsetup", "learning", ("jewish",)),
    "roz":       ("🔥 The Zoroastrian day (!roz)", "rozsetup", "rozday", ("zoroastrian", "parsi")),
    "office":    ("🕯️ An hour of the Divine Office (!office)", "officesetup", "office", ("breviary", "hours")),
}
_BY_NAME = {name: kind for kind, (_, _, _, others) in KINDS.items() for name in (kind, *others)}


def overview(guild_id: int) -> discord.Embed:
    g = _load_guild_config().get(str(guild_id), {})
    lines = []
    for kind, (label, _, key, _others) in KINDS.items():
        channel = g.get(f"{key}_channel_id")
        if not channel:
            lines.append(f"{label} — off · `!daily {kind} channel #channel`")
            continue
        times = g.get(f"{key}_times") or ([g[f"{key}_time"]] if g.get(f"{key}_time") else [])
        when = f"at {', '.join(times)} UTC" if times else "at its usual time"
        lines.append(f"{label} — <#{channel}> {when} · `!daily {kind}`")
    embed = discord.Embed(title="📅 This server's daily posts", description="\n".join(lines),
                          color=discord.Color.dark_gold())
    embed.add_field(name="Change one", value=(
        "`!daily saint channel #saints` — post it in that channel\n"
        "`!daily saint time 07:30` — at that time (24-hour, UTC)\n"
        "`!daily saint test` — post one now · `!daily saint off` — stop it\n"
        "`!daily saint` — its settings (some have more: `!daily votd` its style, `!daily oracle` and "
        "`!daily quiz` their kind)"), inline=False)
    return embed


@bot.command(name="daily")
@commands.guild_only()
@commands.has_permissions(administrator=True)
async def cmd_daily(ctx, kind: str = "", action: str = "", *, arg: str = ""):
    """(Admins) The server's daily posts, in one place.
    Usage: !daily                         — what this server posts each day, and where
           !daily saint channel #saints   — post the saint of the day there
           !daily saint time 07:30        — at that time (UTC); also test, off, and !daily saint alone
    Kinds: votd, oracle, quiz, versle, hymn, saint, astro, angelus, troparion, learning, roz, office."""
    if not kind:
        await ctx.send(embed=overview(ctx.guild.id), allowed_mentions=discord.AllowedMentions.none())
        return
    found = _BY_NAME.get(kind.lower())
    if found is None:
        shown = kind.replace("`", "'")[:40]
        await ctx.send(f"I don't post `{shown}` daily. The daily posts are: "
                       + ", ".join(f"`{k}`" for k in KINDS) + ". `!daily` shows them all.")
        return
    setup = bot.get_command(KINDS[found][1])
    await setup.callback(ctx, action, arg=arg)      # (its own admin check is this one's, above)
