"""
!vov: Puritan prayers, as collected in The Valley of Vision (data/devotions/valley_of_vision.json,
built by scripts/build_valley_of_vision.py). The prayers are the Puritans' own words, adapted, so
they are credited to them and not to the collection's editor.

    !vov                one at random
    !vov 37             prayer 37
    !vov topics         the book's sections; !vov topics 4 lists a section's prayers
    !vov <topic>        a prayer on that theme (by section or title: "!vov penitence", "!vov trinity")
"""
import functools
import json
import random
import re

import discord

from core import ROOT, bot

DATA_PATH = ROOT / "data" / "devotions" / "valley_of_vision.json"
COLOR = discord.Color.from_rgb(70, 60, 50)
CREDIT = "A Puritan prayer · from the collection The Valley of Vision"


@functools.lru_cache(maxsize=1)
def data() -> dict:
    return json.loads(DATA_PATH.read_text(encoding="utf-8")) if DATA_PATH.exists() else {"sections": [], "prayers": []}


def prayers() -> list:
    return data()["prayers"]


def sections() -> list:
    return data()["sections"]


def _words(s: str) -> set:
    return {w for w in re.findall(r"[a-z]+", s.lower()) if len(w) > 2 and w not in {"and", "the", "for", "with"}}


def find(topic: str) -> list:
    """Prayers on a theme: a section's (by number or name), else those whose title shares a word with it."""
    q = topic.strip().lower()
    for s in sections():
        if q == str(s["n"]) or (_words(q) and _words(q) <= _words(s["title"])):
            return [p for p in prayers() if p["section"] == s["n"]]
    words = _words(q)
    stems = {w[:5] for w in words}
    return [p for p in prayers() if words and any(t[:5] in stems for t in _words(p["title"]))]


def prayer_embed(p: dict) -> discord.Embed:
    section = next((s["title"] for s in sections() if s["n"] == p["section"]), "")
    body = "\n".join(discord.utils.escape_markdown(l) for l in p["lines"])
    embed = discord.Embed(title=f"🙏 {p['title']}", description=body[:4000], color=COLOR)
    embed.set_footer(text=f"{CREDIT} · {section} · prayer {p['n']} of {len(prayers())}")
    return embed


def topics_embed(n: str = "") -> discord.Embed:
    if n:
        s = next((s for s in sections() if str(s["n"]) == n.strip()
                  or _words(n) and _words(n) <= _words(s["title"])), None)
        if s:
            rows = [f"`{p['n']}` {p['title']}" for p in prayers() if p["section"] == s["n"]]
            embed = discord.Embed(title=f"🙏 {s['title']}", color=COLOR, description="\n".join(rows)[:4000])
            embed.set_footer(text="!vov <number> for a prayer · !vov topics for all the sections")
            return embed
    embed = discord.Embed(title="🙏 The Valley of Vision — Puritan prayers", color=COLOR, description=(
        "Prayers of the English Puritans, gathered by theme.\n\n"
        + "\n".join(f"`{s['n']}` **{s['title']}** — {s['count']} prayers" for s in sections())
        + "\n\n`!vov topics 4` lists a section's prayers · `!vov 37` shows one · `!vov penitence` a prayer on a "
          "theme · `!vov` one at random"))
    return embed


async def send_vov(ctx, query: str = "") -> None:
    if not prayers():
        await ctx.send("⚠️ The prayers aren't available right now.")
        return
    q = query.strip()
    if not q:
        await ctx.send(embed=prayer_embed(random.choice(prayers())))
        return
    m = re.fullmatch(r"(?i)(?:topics?|themes?|sections?|list|contents)(?:\s+(.+))?", q)
    if m:
        await ctx.send(embed=topics_embed(m.group(1) or ""))
        return
    if re.fullmatch(r"#?\d+", q):
        n = int(q.lstrip("#"))
        if 1 <= n <= len(prayers()):
            await ctx.send(embed=prayer_embed(prayers()[n - 1]))
        else:
            await ctx.send(f"There are {len(prayers())} prayers: try `!vov 1` to `!vov {len(prayers())}`, "
                           f"or `!vov topics` to browse them.")
        return
    found = find(q)
    if found:
        await ctx.send(embed=prayer_embed(random.choice(found)))
        return
    await ctx.send(f"I couldn't find a prayer about **{discord.utils.escape_markdown(q[:100])}**. "
                   f"`!vov topics` shows the themes; `!vov` gives one at random.")


@bot.command(name="vov", aliases=["valleyofvision", "puritan"])
async def cmd_vov(ctx, *, query: str = ""):
    """Puritan prayers from The Valley of Vision.
    Usage: !vov              — one at random
           !vov 37           — prayer 37
           !vov topics       — the themes (!vov topics 4: that theme's prayers)
           !vov penitence    — a prayer on a theme"""
    await send_vov(ctx, query)

# (no /vov: Discord allows a bot 100 slash commands, and this one has them all)
