"""
!salah -- the five daily Muslim prayer times for a place, from Aladhan (no key needed),
worked out by the method the local Muslim authorities use (Aladhan picks it by country).

API: https://api.aladhan.com/v1/timingsByAddress?address=...
     -> {"data": {"timings": {"Fajr": "05:38", ...}, "date": {...}, "meta": {"timezone", "method"}}}
"""
import asyncio
import json
import urllib.parse
import urllib.request

import discord

from core import bot

API = "https://api.aladhan.com/v1/timingsByAddress?address="
COLOR = discord.Color.from_rgb(20, 110, 70)
PRAYERS = [("Fajr", "the dawn prayer"), ("Sunrise", "(the end of Fajr's time)"), ("Dhuhr", "the midday prayer"),
           ("Asr", "the afternoon prayer"), ("Maghrib", "the sunset prayer"), ("Isha", "the night prayer")]


def fetch(place: str) -> "dict | None":
    """Aladhan's answer for a place; None if it can't find it (or can't be reached)."""
    try:
        req = urllib.request.Request(API + urllib.parse.quote(place, safe=""), headers={"User-Agent": "ScriptureBot/1.0"})
        with urllib.request.urlopen(req, timeout=45) as r:      # (finding an unfamiliar place can be slow)
            data = json.loads(r.read().decode("utf-8"))
    except Exception:
        return None
    return data.get("data") if data.get("code") == 200 else None


def salah_embed(place: str, data: dict) -> discord.Embed:
    timings, meta, date = data["timings"], data["meta"], data["date"]
    hijri = date.get("hijri") or {}
    embed = discord.Embed(title=f"🕌 Prayer times — {place}", color=COLOR, description=(
        f"**{date.get('readable', '')}** · {hijri.get('day', '')} {(hijri.get('month') or {}).get('en', '')} "
        f"{hijri.get('year', '')} AH"))
    embed.add_field(name="Today", value="\n".join(
        f"**{name}** {timings.get(name, '—')} — {what}" for name, what in PRAYERS), inline=False)
    embed.set_footer(text=f"Local time ({meta.get('timezone', '')}) · {meta.get('method', {}).get('name', '')} "
                          f"method · from Aladhan")
    return embed


async def send_salah(ctx, place: str) -> None:
    place = place.strip()
    if not place:
        await ctx.send("Which place? `!salah London` or `!salah Cairo, Egypt`")
        return
    async with ctx.typing():
        data = await asyncio.to_thread(fetch, place)
    if data is None:
        await ctx.send(f"I couldn't find prayer times for **{discord.utils.escape_markdown(place)}**. "
                       f"Try a city and its country: `!salah Cairo, Egypt`.")
        return
    await ctx.send(embed=salah_embed(place, data))


@bot.command(name="salah", aliases=["salat", "prayertimes", "namaz"])
async def cmd_salah(ctx, *, place: str = ""):
    """Today's five Muslim prayer times for a place.
    Usage: !salah London   ·   !salah Cairo, Egypt"""
    await send_salah(ctx, place)


@bot.tree.command(name="salah", description="Today's five Muslim prayer times for a place")
@discord.app_commands.describe(place="A city, with its country if needed: London · Cairo, Egypt")
async def salah_slash(interaction: discord.Interaction, place: str):
    await interaction.response.defer()
    await send_salah(await bot.get_context(interaction), place)
