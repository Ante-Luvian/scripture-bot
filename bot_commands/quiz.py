"""
!quiz: guess which book a verse comes from.
  !quiz              a Bible verse; the other choices are books from the same Testament
  !quiz hard         a passage from one of several traditions (Proverbs? the Quran? the Edda?)
  !quiz leaderboard  this server's top scorers, this week and all time
Everyone gets one answer per question, told privately whether they were
right; after ROUND_SECONDS the answer is revealed in the channel with who
got it. Scores (per server) live in data/quiz_scores.json.
"""
import datetime
import json
import random
import re

import discord
from discord import app_commands

from core import ROOT, _atomic_write_json, bot, log, lookup
from scripture_lookup import BIBLE_NT, BIBLE_OT

QUIZ_SCORES_PATH = ROOT / "data" / "quiz_scores.json"
ROUND_SECONDS = 60
MAX_TEXT = 700

# Hard mode: (book key the lookup knows, name shown as the answer)
HARD_POOL = [
    ("Proverbs", "Proverbs"), ("Psalms", "Psalms"), ("Matthew", "Gospel of Matthew"),
    ("Quran", "Quran"), ("Book of Enoch", "Book of Enoch"), ("Rig Veda", "Rig Veda"),
    ("Gathas", "Zoroastrian Gathas"), ("1 Nephi", "Book of Mormon"), ("Corpus Hermeticum", "Corpus Hermeticum"),
    ("Hovamol", "Poetic Edda"), ("Didache", "Didache"), ("Golden Verses of Pythagoras", "Golden Verses of Pythagoras"),
    ("The Hidden Words (Arabic)", "The Hidden Words (Bahá'í)"), ("Ginza Rba", "Ginza Rba (Mandaean)"),
]


def _clean(text: str) -> str:
    text = re.sub(r"\*\*\[\d+\]\*\*\s*", "", text or "").strip()
    return text if len(text) <= MAX_TEXT else text[:MAX_TEXT - 1] + "…"


def _usable(text: str) -> bool:
    return len(text) >= 25 and "no recoverable text" not in text.lower()


def make_question(hard: bool = False, rng: random.Random = random) -> "dict | None":
    """{"text", "answer", "choices": [4 names, shuffled], "reference"} or None."""
    for _ in range(10):
        if hard:
            book, answer = rng.choice(HARD_POOL)
            result = lookup.random_verse_from_book(book)
            others = [name for _, name in HARD_POOL if name != answer]
        else:
            testament = BIBLE_OT if rng.random() < 0.6 else BIBLE_NT
            result = lookup.random_verse_from_books(testament)
            answer = result.get("book") or ""
            others = [b for b in testament if b != answer]
        text = _clean(result.get("text", "")) if result.get("found") else ""
        if not (answer and _usable(text)):
            continue
        choices = rng.sample(others, 3) + [answer]
        rng.shuffle(choices)
        return {"text": text, "answer": answer, "choices": choices, "reference": result.get("reference", "")}
    return None


# ── scores ──────────────────────────────────────────────────────────────────
# Kept per server, so a leaderboard only ever shows that server's members:
# {"guilds": {guild id (or "dm"): {user id: record}}}. A record holds all-time
# totals, this week's (Monday-to-Sunday UTC; reset on the first answer of a new
# week, the old week left readable for the Monday report until then), and the
# current and best run of right answers in a row.

def _load_scores() -> dict:
    try:
        data = json.loads(QUIZ_SCORES_PATH.read_text(encoding="utf-8")) if QUIZ_SCORES_PATH.exists() else {}
    except Exception:
        data = {}
    data.setdefault("guilds", {})
    return data


def week_key(day: datetime.date) -> str:
    iso = day.isocalendar()
    return f"{iso.year}-W{iso.week:02d}"


def _guild_key(guild_id) -> str:
    return str(guild_id) if guild_id else "dm"


def record_answer(guild_id, user_id: int, correct: bool, today: "datetime.date | None" = None) -> dict:
    today = today or datetime.datetime.now(datetime.timezone.utc).date()
    scores = _load_scores()
    s = scores["guilds"].setdefault(_guild_key(guild_id), {}).setdefault(str(user_id), {})
    for key in ("correct", "answered", "streak", "best_streak", "week_correct", "week_answered"):
        s.setdefault(key, 0)
    if s.get("week") != week_key(today):
        s.update(week=week_key(today), week_correct=0, week_answered=0)
    s["answered"] += 1
    s["week_answered"] += 1
    if correct:
        s["correct"] += 1
        s["week_correct"] += 1
        s["streak"] += 1
        s["best_streak"] = max(s["best_streak"], s["streak"])
    else:
        s["streak"] = 0
    _atomic_write_json(QUIZ_SCORES_PATH, scores)
    return s


def _ranked(records: dict, correct: str, answered: str) -> list:
    return sorted(((uid, s) for uid, s in records.items() if s.get(answered)),
                  key=lambda kv: (-kv[1][correct], kv[1][answered]))


def leaderboard_embed(guild_id, today: "datetime.date | None" = None) -> discord.Embed:
    today = today or datetime.datetime.now(datetime.timezone.utc).date()
    records = _load_scores()["guilds"].get(_guild_key(guild_id), {})
    this_week = {uid: s for uid, s in records.items() if s.get("week") == week_key(today)}
    week_lines = [f"{i}. <@{uid}> — {s['week_correct']} right of {s['week_answered']}"
                  for i, (uid, s) in enumerate(_ranked(this_week, "week_correct", "week_answered")[:10], 1)]
    all_lines = [f"{i}. <@{uid}> — {s['correct']} right of {s['answered']}"
                 + (f" · best run {s['best_streak']} 🔥" if s.get("best_streak", 0) >= 3 else "")
                 for i, (uid, s) in enumerate(_ranked(records, "correct", "answered")[:10], 1)]
    embed = discord.Embed(title="🏆 Quiz leaderboard", color=discord.Color.dark_teal())
    if not all_lines:
        embed.description = "No answers in this server yet — try `!quiz`!"
        return embed
    embed.add_field(name="This week", value="\n".join(week_lines) or "No answers yet this week.", inline=False)
    embed.add_field(name="All time", value="\n".join(all_lines), inline=False)
    embed.set_footer(text="Weekly scores start fresh every Monday (UTC).")
    return embed


def weekly_top(week: str, n: int = 3) -> dict:
    """{guild key: [(user id, right, answered), ...]} for a finished week --
    for the owner's Monday report."""
    out = {}
    for gid, records in _load_scores()["guilds"].items():
        week_records = {uid: s for uid, s in records.items() if s.get("week") == week}
        ranked = _ranked(week_records, "week_correct", "week_answered")[:n]
        if ranked:
            out[gid] = [(uid, s["week_correct"], s["week_answered"]) for uid, s in ranked]
    return out


def score_line(score: dict) -> str:
    streak = f"🔥 {score['streak']} in a row! " if score["streak"] >= 3 else ""
    return f"{streak}(Your score here: {score['correct']} right out of {score['answered']}.)"


# ── the round ───────────────────────────────────────────────────────────────

class QuizView(discord.ui.View):
    """Four answer buttons. One answer per person (told privately); after
    ROUND_SECONDS the answer is revealed. Not a persistent view: a round
    is over long before a restart matters."""

    def __init__(self, question: dict, hard: bool):
        super().__init__(timeout=ROUND_SECONDS)
        self.question, self.hard = question, hard
        self.answers: dict[int, tuple[str, bool]] = {}   # user id -> (name, correct)
        self.message = None
        for choice in question["choices"]:
            button = discord.ui.Button(label=choice[:80], style=discord.ButtonStyle.secondary)
            button.callback = self._make_callback(choice)
            self.add_item(button)

    def _make_callback(self, choice: str):
        async def callback(interaction: discord.Interaction):
            if interaction.user.id in self.answers:
                await interaction.response.send_message("You've already answered this one.", ephemeral=True)
                return
            correct = choice == self.question["answer"]
            self.answers[interaction.user.id] = (str(interaction.user.display_name), correct)
            score = record_answer(getattr(interaction, "guild_id", None), interaction.user.id, correct)
            verdict = "✅ Correct!" if correct else f"❌ Not quite — the answer is revealed in {ROUND_SECONDS}s."
            await interaction.response.send_message(f"{verdict} {score_line(score)}", ephemeral=True)
        return callback

    def reveal_embed(self) -> discord.Embed:
        winners = [name for name, ok in self.answers.values() if ok]
        embed = question_embed(self.question, self.hard)
        embed.add_field(name="Answer", value=f"**{self.question['answer']}** — {self.question['reference']}", inline=False)
        embed.add_field(name="Got it right", value=", ".join(winners) if winners else "Nobody this time!", inline=False)
        embed.set_footer(text=f"{len(self.answers)} answered · !quiz for another · !quiz leaderboard")
        return embed

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True
            if item.label == self.question["answer"][:80]:
                item.style = discord.ButtonStyle.success
        if self.message is not None:
            try:
                await self.message.edit(embed=self.reveal_embed(), view=self)
            except discord.HTTPException as e:
                log.warning(f"Couldn't reveal the quiz answer: {e}")


def question_embed(question: dict, hard: bool) -> discord.Embed:
    embed = discord.Embed(
        title="❓ Which book is this from?" if not hard else "❓ Which tradition's text is this?",
        description=f"*{question['text']}*",
        color=discord.Color.dark_teal(),
    )
    embed.set_footer(text=f"Pick an answer below — one try each. Revealed in {ROUND_SECONDS} seconds.")
    return embed


@bot.command(name="quiz", aliases=["guess"])
async def cmd_quiz(ctx, *, mode: str = ""):
    """Guess which book a verse comes from.
    Usage: !quiz              — a Bible verse
           !quiz hard         — a passage from one of many traditions
           !quiz leaderboard  — top scorers"""
    mode = mode.strip().lower()
    if mode in ("leaderboard", "lb", "scores"):
        guild = getattr(ctx, "guild", None)
        await ctx.send(embed=leaderboard_embed(guild.id if guild else None),
                       allowed_mentions=discord.AllowedMentions.none())
        return
    hard = mode == "hard"
    question = make_question(hard)
    if question is None:
        await ctx.send("⚠️ I couldn't come up with a question just now — try again.")
        return
    view = QuizView(question, hard)
    view.message = await ctx.send(embed=question_embed(question, hard), view=view)


@bot.tree.command(name="quiz", description="Guess which book a verse comes from")
@app_commands.describe(mode="Bible (default), hard (many traditions), or leaderboard")
@app_commands.choices(mode=[app_commands.Choice(name="Bible", value=""),
                            app_commands.Choice(name="Hard: many traditions", value="hard"),
                            app_commands.Choice(name="Leaderboard", value="leaderboard")])
async def quiz_slash(interaction: discord.Interaction, mode: str = ""):
    await interaction.response.defer()
    ctx = await bot.get_context(interaction)
    await cmd_quiz(ctx, mode=mode)
