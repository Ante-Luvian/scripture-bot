"""
!quiz: guess which book a verse comes from.
  !quiz              a Bible verse; the other choices are books from the same Testament
  !quiz hard         a passage from one of several traditions (Proverbs? the Quran? the Edda?)
  !quiz leaderboard  top scorers
Everyone gets one answer per question, told privately whether they were
right; after ROUND_SECONDS the answer is revealed in the channel with who
got it. Scores live in data/quiz_scores.json.
"""
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

def _load_scores() -> dict:
    try:
        return json.loads(QUIZ_SCORES_PATH.read_text(encoding="utf-8")) if QUIZ_SCORES_PATH.exists() else {}
    except Exception:
        return {}


def record_answer(user_id: int, correct: bool) -> dict:
    scores = _load_scores()
    s = scores.setdefault(str(user_id), {"correct": 0, "answered": 0})
    s["answered"] += 1
    s["correct"] += int(correct)
    _atomic_write_json(QUIZ_SCORES_PATH, scores)
    return s


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
            score = record_answer(interaction.user.id, correct)
            verdict = "✅ Correct!" if correct else f"❌ Not quite — the answer is revealed in {ROUND_SECONDS}s."
            await interaction.response.send_message(
                f"{verdict} (Your score: {score['correct']} right out of {score['answered']}.)", ephemeral=True)
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
        scores = _load_scores()
        top = sorted(scores.items(), key=lambda kv: (-kv[1]["correct"], kv[1]["answered"]))[:10]
        lines = [f"{i}. <@{uid}> — {s['correct']} right of {s['answered']}" for i, (uid, s) in enumerate(top, 1)]
        embed = discord.Embed(title="🏆 Quiz leaderboard", description="\n".join(lines) or "No answers yet — try `!quiz`!",
                              color=discord.Color.dark_teal())
        await ctx.send(embed=embed, allowed_mentions=discord.AllowedMentions.none())
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
