"""
!angelus -- the Angelus, the short prayer said morning, noon and evening in
memory of the Incarnation, in English and Latin with the Ave Maria sung; in
Eastertide the Regina caeli takes its place, as the Church directs. And
!angelussetup, which posts it in a channel at the hours a server chooses.

The texts are A Manual of Prayers for the Use of the Catholic Laity (1889, the
prayer book of the Third Plenary Council of Baltimore), on Wikisource: the
Angelus from "Morning Prayers", the Hail Mary (written out in full where the
Manual has "Hail, Mary, etc.") from "Christian Faith and Practice", and the
Regina caeli from "Evening Prayers". Its season, "From Holy Saturday till
Trinity Eve", is the Manual's.
"""
import datetime
import json
import re

import discord
from discord.ext import commands, tasks

from core import ROOT, _atomic_write_json, _load_guild_config, _update_guild_config, bot, log
from bot_commands.hymns import hymns, sung_path
from liturgical_calendar import _easter_sunday

ANGELUS_PATH = ROOT / "data" / "angelus.json"      # {"posted": {guild id: "YYYY-MM-DD HH:MM"}}
DEFAULT_TIMES = ["12:00"]
COLOR = discord.Color.from_rgb(70, 110, 170)
SOURCE = "A Manual of Prayers for the Use of the Catholic Laity (Baltimore, 1889)"

HAIL_MARY = ("Hail, Mary, full of grace; the Lord is with thee: blessed art thou among women, and blessed is the "
             "fruit of thy womb, Jesus. Holy Mary, Mother of God, pray for us sinners, now and at the hour of our "
             "death. Amen.")
AVE_MARIA = ("Ave, Maria, gratia plena; Dominus tecum: benedicta tu in mulieribus, et benedictus fructus ventris "
             "tui, Jesus. Sancta Maria, Mater Dei, ora pro nobis peccatoribus, nunc et in hora mortis nostræ. Amen.")

ANGELUS_EN = [
    "℣. The Angel of the Lord declared unto Mary.\n℟. And she conceived by the Holy Ghost.",
    HAIL_MARY,
    "℣. Behold the handmaid of the Lord.\n℟. Be it done unto me according to Thy word.",
    HAIL_MARY,
    "℣. And the Word was made Flesh.\n℟. And dwelt among us.",
    HAIL_MARY,
    "*Let us pray.*\nPour forth, we beseech Thee, O Lord, Thy grace into our hearts; that as we have known the "
    "Incarnation of Christ Thy Son by the message of an Angel, so, by His Passion and Cross, we may be brought to "
    "the glory of His resurrection; through the same Christ our Lord. Amen.",
]
ANGELUS_LA = [
    "℣. Angelus Domini nuntiavit Mariæ.\n℟. Et concepit de Spiritu Sancto.",
    AVE_MARIA,
    "℣. Ecce ancilla Domini.\n℟. Fiat mihi secundum verbum tuum.",
    AVE_MARIA,
    "℣. Et Verbum caro factum est.\n℟. Et habitavit in nobis.",
    AVE_MARIA,
    "*Oremus.*\nGratiam tuam, quæsumus, Domine, mentibus nostris infunde, ut qui, Angelo nuntiante, Christi filii "
    "tui incarnationem cognovimus, per passionem ejus et crucem ad resurrectionis gloriam perducamur; per eumdem "
    "Christum Dominum nostrum. Amen.",
]
REGINA_EN = [
    "O Queen of heaven, rejoice! Alleluia.\nFor He whom thou didst merit to bear, Alleluia,\n"
    "Hath arisen, as He said, Alleluia.\nPray for us to God. Alleluia.",
    "℣. Rejoice and be glad, O Virgin Mary. Alleluia.\n℟. For the Lord hath risen indeed. Alleluia.",
    "*Let us pray.*\nO God, who, through the Resurrection of Thy Son our Lord Jesus Christ, didst vouchsafe to fill "
    "the world with joy; grant, we beseech Thee, that, through His Virgin Mother, Mary, we may lay hold on the joys "
    "of everlasting life. Through the same Christ our Lord.\n℟. Amen.",
]
REGINA_LA = [
    "Regina Cœli, lætare! Alleluia.\nQuia quem meruisti portare, Alleluia,\nResurrexit sicut dixit. Alleluia.\n"
    "Ora pro nobis Deum. Alleluia.",
    "℣. Gaude et lætare, Virgo Maria. Alleluia.\n℟. Quia surrexit Dominus vere. Alleluia.",
    "*Oremus.*\nDeus, qui per resurrectionem Filii tui Domini nostri Jesu Christi mundum lætificare dignatus es; "
    "præsta, quæsumus, ut per ejus Genitricem Virginem Mariam perpetuæ capiamus gaudia vitæ. Per eumdem Christum "
    "Dominum nostrum.\n℟. Amen.",
]
SUNG = {"angelus": "Ave Maria (Antiphona)", "regina": "Regina caeli"}   # the chants sung with each


def eastertide(day: datetime.date) -> bool:
    """The Regina caeli's season: "From Holy Saturday till Trinity Eve" (the Manual)."""
    easter = _easter_sunday(day.year)
    return easter - datetime.timedelta(days=1) <= day <= easter + datetime.timedelta(days=55)


def angelus_message(day: datetime.date) -> dict:
    """send() kwargs: the prayer in English and Latin, and its chant sung."""
    kind = "regina" if eastertide(day) else "angelus"
    if kind == "regina":
        title, en, la = "🔔 Regina Cæli", REGINA_EN, REGINA_LA
        content = "🔔 **Regina Cæli** · in Eastertide it is said in place of the Angelus, standing"
    else:
        title, en, la = "🔔 The Angelus", ANGELUS_EN, ANGELUS_LA
        content = "🔔 **The Angelus** · the prayer of the Incarnation, said morning, noon and evening"
    english = discord.Embed(title=title, description="\n\n".join(en), color=COLOR)
    latin = discord.Embed(title=f"{title}, in Latin", description="\n\n".join(la), color=COLOR)
    latin.set_footer(text=SOURCE)
    message = {"content": content, "embeds": [english, latin]}
    chant = next((h for h in hymns() if h["title"] == SUNG[kind]), None)
    path = sung_path(chant) if chant else None
    if path:
        message["content"] += f"\n🎤 *{chant['title']}*, sung in Latin."
        message["file"] = discord.File(path, filename=f"{'Regina_caeli' if kind == 'regina' else 'Ave_Maria'}_sung.ogg")
    return message


def _now() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


@bot.command(name="angelus", aliases=["reginacaeli", "reginacoeli"])
async def cmd_angelus(ctx):
    """The Angelus (the Regina caeli in Eastertide), in English and Latin, with its chant sung.
    Usage: !angelus"""
    await ctx.send(**angelus_message(_now().date()))


@bot.tree.command(name="angelus", description="The Angelus (Regina caeli in Eastertide), in English and Latin, sung")
async def angelus_slash(interaction: discord.Interaction):
    await interaction.response.defer()
    ctx = await bot.get_context(interaction)
    await ctx.send(**angelus_message(_now().date()))


# ── the daily post (!angelussetup) ──────────────────────────────────────────
# Per-server settings in guild_config.json: angelus_channel_id, angelus_times (["HH:MM"], UTC).

def _load_state() -> dict:
    try:
        return json.loads(ANGELUS_PATH.read_text(encoding="utf-8")) if ANGELUS_PATH.exists() else {}
    except ValueError:
        return {}


async def post_angelus(guild_id, channel, when: str, day: datetime.date, force: bool = False) -> bool:
    """Post once per server per time slot (`when` is "YYYY-MM-DD HH:MM"; a restart doesn't repeat it)."""
    state = _load_state()
    if state.get("posted", {}).get(str(guild_id)) == when and not force:
        return False
    await channel.send(**angelus_message(day))
    state.setdefault("posted", {})[str(guild_id)] = when
    _atomic_write_json(ANGELUS_PATH, state)
    return True


async def run_angelus(client, now: datetime.datetime) -> int:
    hm, posted = f"{now.hour:02d}:{now.minute:02d}", 0
    for guild_id, g in _load_guild_config().items():
        channel_id = g.get("angelus_channel_id")
        if not channel_id or hm not in g.get("angelus_times", DEFAULT_TIMES):
            continue
        channel = client.get_channel(int(channel_id))
        if channel is None:
            continue
        try:
            posted += await post_angelus(guild_id, channel, f"{now.date().isoformat()} {hm}", now.date())
        except Exception:
            log.exception(f"Failed to post the Angelus for guild {guild_id}")
    return posted


@tasks.loop(minutes=1)
async def angelus_task():
    await run_angelus(bot, _now())


@angelus_task.before_loop
async def _before_angelus():
    await bot.wait_until_ready()


def _times(arg: str) -> "list | None":
    found = re.findall(r"\b(\d{1,2}):(\d{2})\b", arg)
    if not found or any(not (0 <= int(h) <= 23 and 0 <= int(m) <= 59) for h, m in found):
        return None
    return sorted({f"{int(h):02d}:{m}" for h, m in found})


@bot.command(name="angelussetup", aliases=["angelusconfig"])
@commands.has_permissions(administrator=True)
async def cmd_angelussetup(ctx, action: str = "", *, arg: str = ""):
    """Post the Angelus in a channel, at one or more times a day.
    Usage: !angelussetup                          — show this server's settings
           !angelussetup channel #chan            — post it there
           !angelussetup time 06:00 12:00 18:00   — when (24h UTC; the traditional three, or just noon)
           !angelussetup test                     — post it now
           !angelussetup off                      — stop posting it"""
    if not ctx.guild:
        await ctx.send("This command only works in a server.")
        return
    g = _load_guild_config().get(str(ctx.guild.id), {})
    channel_id, times = g.get("angelus_channel_id"), g.get("angelus_times", DEFAULT_TIMES)
    action = action.strip().lower()
    if not action:
        embed = discord.Embed(title=f"🔔 The Angelus — {ctx.guild.name}", color=COLOR)
        embed.add_field(name="Channel", value=f"<#{channel_id}>" if channel_id else "*not set — not posted*")
        embed.add_field(name="Times (UTC)", value=", ".join(times))
        embed.set_footer(text="!angelussetup channel #chan · time 06:00 12:00 18:00 · test · off")
        await ctx.send(embed=embed)
    elif action == "off":
        _update_guild_config(ctx.guild.id, angelus_channel_id=None)
        await ctx.send("The Angelus won't be posted here any more. (`!angelus` still works.)")
    elif action == "channel":
        channel = ctx.message.channel_mentions[0] if ctx.message.channel_mentions else None
        if channel is None:
            await ctx.send("Mention a channel: `!angelussetup channel #prayer`")
            return
        _update_guild_config(ctx.guild.id, angelus_channel_id=channel.id)
        new = _times(arg.split("time", 1)[1]) if "time" in arg else None   # ("channel #chan time 12:00" in one go)
        if new:
            times = new
            _update_guild_config(ctx.guild.id, angelus_times=times)
        await ctx.send(f"The Angelus will be posted in {channel.mention} at {', '.join(times)} UTC.")
    elif action in ("time", "times"):
        new = _times(arg)
        if not new:
            await ctx.send("Give 24-hour UTC times: `!angelussetup time 12:00`, or the traditional three, "
                           "`!angelussetup time 06:00 12:00 18:00`.")
            return
        _update_guild_config(ctx.guild.id, angelus_times=new)
        await ctx.send(f"The Angelus will be posted at **{', '.join(new)} UTC**.")
    elif action == "test":
        channel = bot.get_channel(int(channel_id)) if channel_id else ctx.channel
        now = _now()
        await post_angelus(ctx.guild.id, channel, now.isoformat(), now.date(), force=True)
    else:
        await ctx.send("Unknown option. Use `channel`, `time`, `test`, or `off`.")
