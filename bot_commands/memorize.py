"""
!memorize: learn a verse by heart.
  !memorize John 3:16         practice it: words are blanked out, more at each level
  !memorize list              your verses and when each is next due
  !memorize stop John 3:16    stop reviewing one

Practice is a fill-in-the-blanks card: level 1 hides a quarter of the words,
2 half, 3 three quarters, and 4 leaves only each word's first letter (the
"first-letter method"). Which words go is fixed per verse and level, and each
level hides the previous level's words plus more, so the card can be rebuilt
from its button's custom_id alone -- the buttons keep working after restarts.

🔔 Remind me schedules reviews by DM (spaced repetition): after 1, 3, 7, 14
and 30 days, each sent at REVIEW_TIME UTC as a level-4 card. Schedules live
in data/memorize.json: {user id: {reference: {"stage", "due", "added"}}}.
"""
import datetime
import json
import math
import random
import re

import discord
from discord import app_commands
from discord.ext import tasks

from core import ROOT, _atomic_write_json, bot, log, lookup

MEMORIZE_PATH = ROOT / "data" / "memorize.json"
LEVELS = 4
HIDDEN_SHARE = {1: 0.25, 2: 0.5, 3: 0.75}
MAX_TEXT = 900                      # a few verses: more is a chapter, not a memory verse
INTERVALS = [1, 3, 7, 14, 30]       # days until each review
REVIEW_TIME = "08:00"               # UTC

_MARKER = re.compile(r"(\*\*\[\d+\]\*\*)")
_WORD = re.compile(r"[^\W\d_][\w'’\-]*")


def _today() -> datetime.date:
    return datetime.datetime.now(datetime.timezone.utc).date()


def _verse(reference: str) -> "dict | None":
    result = lookup.get_verse(reference)
    if not result.get("found") or not result.get("text"):
        return None
    text = result["text"].strip()
    if len(_MARKER.findall(text)) == 1:          # a single verse: no need for its number
        text = _MARKER.sub("", text).strip()
    return {"reference": result["reference"], "text": text, "source": result.get("source", "")}


def _blank(word: str) -> str:
    return "`" + "_" * min(max(len(word), 2), 10) + "`"


def cloze(text: str, reference: str, level: int) -> str:
    """`text` with words blanked for `level` (0 = none, LEVELS = first letters)."""
    if level <= 0:
        return text
    parts = _MARKER.split(text)
    words = [(i, m) for i, part in enumerate(parts) if not _MARKER.fullmatch(part)
             for m in _WORD.finditer(part)]
    order = list(range(len(words)))
    random.Random(reference).shuffle(order)      # the same order at every level: hidden sets nest
    if level >= LEVELS:
        hidden = set(order)
    else:
        hidden = set(order[:math.ceil(len(words) * HIDDEN_SHARE[level])])
    replacements: dict[int, list] = {}
    for n, (i, m) in enumerate(words):
        if n in hidden:
            new = m.group(0)[0] if level >= LEVELS else _blank(m.group(0))
            replacements.setdefault(i, []).append((m.start(), m.end(), new))
    for i, edits in replacements.items():
        part = parts[i]
        for start, end, new in reversed(edits):
            part = part[:start] + new + part[end:]
        parts[i] = part
    return "".join(parts)


def practice_embed(verse: dict, level: int) -> discord.Embed:
    title = f"🧠 Memorize {verse['reference']}"
    title += " — read it through" if level == 0 else f" — level {level} of {LEVELS}"
    embed = discord.Embed(title=title, description=cloze(verse["text"], verse["reference"], level)[:4096],
                          color=discord.Color.dark_green())
    hint = ("Read it aloud a few times, then press Harder." if level == 0 else
            "Only first letters now — say the whole thing!" if level >= LEVELS else
            "Say it aloud, filling in the blanks, then check with Reveal.")
    embed.set_footer(text=f"{hint} · {verse['source']}" if verse["source"] else hint)
    return embed


class MemorizeButton(discord.ui.DynamicItem[discord.ui.Button],
                     template=r"mem:(?P<action>easier|harder|reveal|remind):(?P<level>\d):(?P<ref>.+)"):
    LOOK = {"easier": ("Easier", "◀"), "harder": ("Harder", "▶"),
            "reveal": ("Reveal", "👁️"), "remind": ("Remind me", "🔔")}

    def __init__(self, action: str, level: int, reference: str, disabled: bool = False):
        label, emoji = self.LOOK[action]
        style = discord.ButtonStyle.primary if action == "harder" else discord.ButtonStyle.secondary
        super().__init__(discord.ui.Button(label=label, emoji=emoji, style=style, disabled=disabled,
                                           custom_id=f"mem:{action}:{level}:{reference}"[:100]))
        self.action, self.level, self.reference = action, level, reference

    @classmethod
    async def from_custom_id(cls, interaction, item, match):
        return cls(match["action"], int(match["level"]), match["ref"])

    async def callback(self, interaction: discord.Interaction):
        verse = _verse(self.reference)
        if verse is None:
            await interaction.response.send_message("⚠️ I can't find that verse any more.", ephemeral=True)
            return
        if self.action in ("easier", "harder"):
            level = max(0, min(LEVELS, self.level + (1 if self.action == "harder" else -1)))
            await interaction.response.edit_message(embed=practice_embed(verse, level),
                                                    view=practice_view(verse["reference"], level))
        elif self.action == "reveal":
            await interaction.response.send_message(f"**{verse['reference']}**\n{verse['text']}"[:2000], ephemeral=True)
        else:
            await interaction.response.send_message(schedule(interaction.user.id, verse["reference"]), ephemeral=True)


bot.add_dynamic_items(MemorizeButton)


def practice_view(reference: str, level: int) -> discord.ui.View:
    view = discord.ui.View(timeout=None)          # persistent buttons: must never time out
    view.add_item(MemorizeButton("easier", level, reference, disabled=level <= 0))
    view.add_item(MemorizeButton("harder", level, reference, disabled=level >= LEVELS))
    view.add_item(MemorizeButton("reveal", level, reference))
    view.add_item(MemorizeButton("remind", level, reference))
    return view


# ── spaced-repetition reviews ───────────────────────────────────────────────

def _load() -> dict:
    try:
        return json.loads(MEMORIZE_PATH.read_text(encoding="utf-8")) if MEMORIZE_PATH.exists() else {}
    except Exception:
        return {}


def schedule(user_id: int, reference: str, today: "datetime.date | None" = None) -> str:
    today = today or _today()
    data = _load()
    mine = data.setdefault(str(user_id), {})
    if reference in mine:
        return f"🔔 **{reference}** is already in your reviews — next one on {mine[reference]['due']}."
    due = today + datetime.timedelta(days=INTERVALS[0])
    mine[reference] = {"stage": 0, "due": due.isoformat(), "added": today.isoformat()}
    _atomic_write_json(MEMORIZE_PATH, data)
    return (f"🔔 I'll send you **{reference}** to practise by private message tomorrow, then after 3, 7, 14 "
            f"and 30 days — spacing reviews out like this is how verses stick. (`!memorize list` shows your "
            f"verses. Your Discord privacy settings need to allow messages from server members.)")


async def run_reviews(client, today: datetime.date, current_hm: str) -> int:
    """DM every review due today (or overdue) at REVIEW_TIME. Returns the number sent."""
    if current_hm != REVIEW_TIME:
        return 0
    data = _load()
    sent, changed = 0, False
    for uid, verses in data.items():
        for reference, entry in list(verses.items()):
            if entry["due"] > today.isoformat():
                continue
            stage = entry["stage"] + 1
            changed = True
            if stage >= len(INTERVALS):
                del verses[reference]          # the last review: learned
            else:
                entry.update(stage=stage, due=(today + datetime.timedelta(days=INTERVALS[stage])).isoformat())
            verse = _verse(reference)          # (scheduled even if the DM fails: no retry spam)
            if verse is None:
                continue
            last = stage >= len(INTERVALS)
            note = ("🎉 Last review — after this you know it!" if last else
                    f"Review {stage} of {len(INTERVALS)} · next in {INTERVALS[stage]} days")
            try:
                user = client.get_user(int(uid)) or await client.fetch_user(int(uid))
                await user.send(f"🧠 Time to practise **{reference}**. {note}  (`!memorize stop {reference}` to stop)",
                                embed=practice_embed(verse, LEVELS), view=practice_view(verse["reference"], LEVELS))
                sent += 1
            except discord.HTTPException as e:
                log.warning(f"Couldn't DM a memory-verse review to {uid}: {e}")
    if changed:
        _atomic_write_json(MEMORIZE_PATH, {uid: v for uid, v in data.items() if v})
    return sent


@tasks.loop(minutes=1)
async def memorize_review_task():
    now = datetime.datetime.now(datetime.timezone.utc)
    await run_reviews(bot, now.date(), f"{now.hour:02d}:{now.minute:02d}")


@memorize_review_task.before_loop
async def _before_reviews():
    await bot.wait_until_ready()


# ── the command ─────────────────────────────────────────────────────────────

@bot.command(name="memorize", aliases=["memorise", "learn"])
async def cmd_memorize(ctx, *, arg: str = ""):
    """Learn a verse by heart.
    Usage: !memorize John 3:16         — practise it, hiding more words each level
           !memorize list              — your verses and when each is next reviewed
           !memorize stop John 3:16    — stop reviewing one"""
    arg = arg.strip()
    words = arg.split(None, 1)
    action = words[0].lower() if words else ""

    if action == "list" and len(words) == 1:
        mine = _load().get(str(ctx.author.id), {})
        if not mine:
            await ctx.send("You have no verses in review yet. Try `!memorize John 3:16`, then press 🔔 **Remind me**.")
            return
        lines = [f"• **{ref}** — review {e['stage'] + 1} of {len(INTERVALS)} on {e['due']}"
                 for ref, e in sorted(mine.items(), key=lambda kv: kv[1]["due"])]
        await ctx.send(embed=discord.Embed(title="🧠 Your memory verses", description="\n".join(lines)[:4096],
                                           color=discord.Color.dark_green()))
        return
    if action == "stop" and len(words) == 2:
        data = _load()
        mine = data.get(str(ctx.author.id), {})
        verse = _verse(words[1])
        key = next((r for r in mine if r.lower() in (words[1].lower(), (verse or {}).get("reference", "").lower())), None)
        if key is None:
            await ctx.send(f"**{words[1]}** isn't in your reviews. `!memorize list` shows them.")
            return
        del mine[key]
        _atomic_write_json(MEMORIZE_PATH, {uid: v for uid, v in data.items() if v})
        await ctx.send(f"Stopped reviewing **{key}**.")
        return
    if not arg:
        await ctx.send("Which verse? For example: `!memorize John 3:16` or `!memorize Psalm 23:1-3`.")
        return
    verse = _verse(arg)
    if verse is None:
        await ctx.send(f"⚠️ I couldn't find **{arg}**. Try something like `!memorize John 3:16`.")
        return
    if len(verse["text"]) > MAX_TEXT:
        await ctx.send(f"That's a long passage to learn in one go ({len(verse['text']):,} characters) — "
                       "try a few verses at a time, like `!memorize Psalm 23:1-3`.")
        return
    await ctx.send(embed=practice_embed(verse, 1), view=practice_view(verse["reference"], 1))


@bot.tree.command(name="memorize", description="Learn a verse by heart, with blanks and spaced reviews by DM")
@app_commands.describe(verse="A verse, e.g. John 3:16 — or 'list' for your verses, 'stop John 3:16' to stop one")
async def memorize_slash(interaction: discord.Interaction, verse: str = ""):
    await interaction.response.defer()
    ctx = await bot.get_context(interaction)
    await cmd_memorize(ctx, arg=verse)
