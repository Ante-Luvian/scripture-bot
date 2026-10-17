"""
!icon -- Orthodox icons (data/icons/, built by scripts/build_icons.py): the icon of the
day's Great Feast on the feast, otherwise one of the famous icons in turn; or any by name.
Each comes with the summary of its Wikipedia article.
"""
import datetime
import functools
import json
import re

import discord

from core import ROOT, bot

ICONS_DIR = ROOT / "data" / "icons"
COLOR = discord.Color.from_rgb(180, 140, 40)


@functools.lru_cache(maxsize=1)
def icons() -> dict:
    path = ICONS_DIR / "icons.json"
    return json.loads(path.read_text(encoding="utf-8"))["icons"] if path.exists() else {}


def orthodox_pascha(year: int) -> datetime.date:
    """Orthodox Easter: the Julian-calendar computus, given as a Gregorian date (1900-2099: +13 days)."""
    a, b, c = year % 4, year % 7, year % 19
    d = (19 * c + 15) % 30
    e = (2 * a + 4 * b - d + 34) % 7
    month, day = divmod(d + e + 114, 31)
    return datetime.date(year, month, day + 1) + datetime.timedelta(days=13)


def feast_icon(day: datetime.date) -> "str | None":
    pascha = orthodox_pascha(day.year)
    for key, icon in icons().items():
        feast = icon["feast"]
        if feast.startswith("pascha"):
            if day == pascha + datetime.timedelta(days=int(feast[6:] or 0)):
                return key
        elif feast and feast == day.strftime("%m-%d"):
            return key
    return None


def icon_for(day: datetime.date) -> "tuple[str, bool]":
    """(key, is it the day's feast)."""
    key = feast_icon(day)
    if key:
        return key, True
    plain = sorted(k for k, v in icons().items() if not v["feast"] or k in SAINTS)
    return plain[day.toordinal() % len(plain)], False


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z ]", " ", s.lower().replace("st.", "st").replace("saint ", "st "))).strip()


def find(query: str) -> "str | None":
    q = _norm(query)
    for key, icon in icons().items():
        if q in [_norm(key), _norm(icon["title"])] + [_norm(n) for n in icon["names"]]:
            return key
    for key, icon in icons().items():
        if q and any(q in _norm(x) for x in [key, icon["title"]] + icon["names"]):
            return key
    return None


def icon_message(key: str, why: str = "") -> dict:
    icon = icons()[key]
    about = icon["about"] if len(icon["about"]) <= 1500 else icon["about"][:1500].rsplit(". ", 1)[0] + "."
    embed = discord.Embed(title=f"☦️ {icon['title']}", description=about, color=COLOR,
                          url=f"https://en.wikipedia.org/wiki/{icon['article'].replace(' ', '_')}")
    embed.set_image(url=f"attachment://{icon['file']}")
    embed.set_footer(text="Image: Wikimedia Commons (public domain) · text: Wikipedia")
    message = {"embed": embed, "file": discord.File(ICONS_DIR / icon["file"], filename=icon["file"])}
    if why:
        message["content"] = why
    return message


SAINTS = ("st george", "st nicholas", "trinity")         # shown on a day, but not one of the Great Feasts' icons


def list_embed() -> discord.Embed:
    great = [k for k, v in icons().items() if v["feast"] and k not in SAINTS]
    feasts = [f"• {icons()[k]['title']} — `!icon {k}`" for k in great]
    others = [f"• {v['title']} — `!icon {k}`" for k, v in icons().items() if k not in great]
    embed = discord.Embed(title="☦️ Icons", color=COLOR)
    embed.add_field(name="Famous icons", value="\n".join(others)[:1024], inline=False)
    embed.add_field(name="The Great Feasts", value="\n".join(feasts)[:1024], inline=False)
    embed.set_footer(text="!icon on its own: the day's feast, or one of the famous icons in turn")
    return embed


def _today() -> datetime.date:
    return datetime.datetime.now(datetime.timezone.utc).date()


async def send_icon(ctx, query: str = "") -> None:
    if not icons():
        await ctx.send("⚠️ The icons aren't available right now.")
        return
    q = query.strip()
    if q.lower() in ("list", "all", "index"):
        await ctx.send(embed=list_embed())
        return
    if not q:
        key, feast = icon_for(_today())
        why = "☦️ **The icon of today's feast**" if feast else "☦️ **Icon of the day**"
        await ctx.send(**icon_message(key, why))
        return
    key = find(q)
    if key is None:
        await ctx.send(f"I don't have an icon called **{discord.utils.escape_markdown(q)}**. `!icon list` shows "
                       f"the ones I have.")
        return
    await ctx.send(**icon_message(key))


@bot.command(name="icon", aliases=["icons", "ikon"])
async def cmd_icon(ctx, *, query: str = ""):
    """An Orthodox icon, with what it shows.
    Usage: !icon             — the day's feast icon, or an icon of the day
           !icon trinity     — an icon by name (`!icon list` for them all)"""
    await send_icon(ctx, query)


@bot.tree.command(name="icon", description="An Orthodox icon: the day's feast, or one by name")
@discord.app_commands.describe(name="An icon's name (trinity, vladimir, nativity…), or 'list'; empty for today's")
async def icon_slash(interaction: discord.Interaction, name: str = ""):
    await interaction.response.defer()
    ctx = await bot.get_context(interaction)
    await send_icon(ctx, name)
