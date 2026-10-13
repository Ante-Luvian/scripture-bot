"""
!quiz: guess which book a verse comes from.
  !quiz              a Bible verse; the other choices are books from the same Testament
  !quiz hard         a passage from one of several traditions (Proverbs? the Quran? the Edda?)
  !quiz leaderboard  this server's top scorers, this week and all time
Everyone gets one answer per question, told privately whether they were
right; after ROUND_SECONDS the answer is revealed in the channel with who
got it. Scores (per server) live in data/quiz_scores.json.
  !quizsetup         (admins) a daily quiz question in a channel; see below
"""
import datetime
import json
import random
import re

import discord
from discord import app_commands
from discord.ext import commands, tasks

from core import ROOT, _atomic_write_json, _load_guild_config, _update_guild_config, bot, log, lookup
from scripture_lookup import BIBLE_NT, BIBLE_OT, TRADITIONS, tradition

QUIZ_SCORES_PATH = ROOT / "data" / "quiz_scores.json"
ROUND_SECONDS = 60
MAX_TEXT = 700

# Hard mode: (book key the lookup knows, name shown as the answer)
HARD_POOL = [
    ("Proverbs", "Proverbs"), ("Psalms", "Psalms"), ("Matthew", "Gospel of Matthew"),
    ("Quran", "Quran"), ("Book of Enoch", "Book of Enoch"), ("Rig Veda", "Rig Veda"),
    ("Gathas", "Zoroastrian Gathas"), ("1 Nephi", "Book of Mormon"), ("Corpus Hermeticum", "Corpus Hermeticum"),
    ("Hovamol", "Poetic Edda"), ("Dhammapada", "Dhammapada (Buddhist)"),
    ("Tao Te Ching", "Tao Te Ching (Taoist)"), ("Analects", "Analects of Confucius"),
    ("Divan of Hafiz", "Hafiz (Sufi poetry)"), ("Bhagavad Gita", "Bhagavad Gita"),
    ("Meditations", "Marcus Aurelius, Meditations"), ("Imitation of Christ", "The Imitation of Christ"), ("Didache", "Didache"), ("Golden Verses of Pythagoras", "Golden Verses of Pythagoras"),
    ("The Hidden Words (Arabic)", "The Hidden Words (Bahá'í)"), ("Ginza Rba", "Ginza Rba (Mandaean)"),
    ("Guru Granth Sahib", "Guru Granth Sahib (Sikh)"), ("Uttaradhyayana Sutra", "Uttaradhyayana Sutra (Jain)"),
    ("Kojiki", "Kojiki (Shinto)"), ("Popol Vuh", "Popol Vuh (Maya)"), ("Kalevala", "Kalevala (Finnish)"),
    ("Masnavi", "Rumi's Masnavi"), ("Zhuangzi", "Zhuangzi (Taoist)"), ("Lotus Sutra", "Lotus Sutra (Buddhist)"),
    ("Cloud of Unknowing", "The Cloud of Unknowing"), ("Yoga Sutras", "Yoga Sutras of Patanjali"),
]


# !quiz <tradition>: which of a tradition's best-known books is this from?
# (The whole of a big tradition -- ~400 Church Fathers' works -- would be a
# lottery, so each has a short list; every book here is checked by a test.)
QUIZ_POOLS = {
    "jewish":    ["Jewish War", "Jewish Antiquities", "On the Creation", "On the Life of Moses I",
                  "Community Rule", "War Scroll", "Hodayot", "Damascus Document"],
    "christian": ["Confessions", "City of God", "1 Clement", "Didache", "Shepherd of Hermas",
                  "Imitation of Christ", "Rule of Benedict", "Inferno", "Ignatius to the Romans"],
    "apocrypha": ["Book of Enoch", "Book of Jubilees", "2 Enoch", "Odes of Solomon", "Wisdom of Solomon",
                  "Sirach", "The Protevangelium of James", "Acts of Paul and Thecla", "Acts of Pilate: First Greek Form"],
    "hindu":     ["Rig Veda", "Atharva Veda", "Bhagavad Gita", "Isa Upanishad", "Katha Upanishad", "Kena Upanishad",
                  "Chandogya Upanishad", "Brihadaranyaka Upanishad", "Laws of Manu", "Yoga Sutras"],
    "buddhist":  ["Dhammapada", "Sutta Nipata", "Diamond Sutra", "Lotus Sutra", "Jataka", "Questions of King Milinda"],
    "chinese":   ["Tao Te Ching", "Analects", "I Ching", "Zhuangzi", "Mencius"],
    "jain":      ["Akaranga Sutra", "Sutrakritanga", "Uttaradhyayana Sutra", "Kalpa Sutra"],
    "zoroastrian": ["Gathas", "Yasna", "Yashts", "Vendidad", "Bundahishn"],
    "classical": ["Iliad", "Odyssey", "Aeneid", "Republic", "Meditations", "Enchiridion of Epictetus",
                  "Works and Days", "Enneads", "Nicomachean Ethics", "Corpus Hermeticum",
                  # from the Perseus library
                  "Antigone", "Oedipus Tyrannus", "Agamemnon", "Medea", "Clouds",
                  "History of the Peloponnesian War", "Anabasis", "Gallic War", "De Rerum Natura",
                  "Metamorphoses", "The Annals", "Description of Greece"],
    "sufi":      ["Divan of Hafiz", "Masnavi", "Rubaiyat"],
    "gnostic":   ["Gospel of Thomas", "Ginza Rba", "The Thunder, Perfect Mind", "The Secret Book of James",
                  "The Tripartite Tractate", "Manichaean Bema Psalms"],
    "norse":     ["Voluspo", "Hovamol", "Lokasenna", "Thrymskvitha", "Grimnismol", "Vafthruthnismol"],
    "neareast":  ["Enuma Elish", "Book of the Dead", "The Instruction of Amenemope", "The Story of Ahikar",
                  "The Great Hymn to the Aten", "Baal and Mot"],
    "lds":       ["1 Nephi", "Mosiah", "Alma", "Ether", "Doctrine and Covenants", "Moses"],
    "bahai":     ["The Hidden Words (Arabic)", "The Hidden Words (Persian)", "Gleanings from the Writings of Baha'u'llah",
                  "Kitab-i-Iqan", "Some Answered Questions", "Prayers and Meditations"],
}


def _clean(text: str) -> str:
    text = re.sub(r"\*\*\[\d+\]\*\*\s*", "", text or "")
    # a chapter title or heading would give the answer away ("*Of the imitation of Christ*", "**Chapter 28**")
    text = re.sub(r"^(?:\*{1,2}[^*\n]+\*{1,2}\s*\n)+", "", text.strip())
    text = re.sub(r"^\(vv\. [\d–]+\) ", "", text).strip()
    return text if len(text) <= MAX_TEXT else text[:MAX_TEXT - 1] + "…"


def _usable(text: str) -> bool:
    return len(text) >= 25 and "no recoverable text" not in text.lower()


def make_question(hard: bool = False, rng: random.Random = random, tradition: str = "") -> "dict | None":
    """{"text", "answer", "choices": [up to 4 names, shuffled], "reference"} or
    None. `tradition`: a QUIZ_POOLS key, for a question within one tradition."""
    for _ in range(10):
        if tradition:
            pool = QUIZ_POOLS[tradition]
            answer = rng.choice(pool)
            result = lookup.random_verse_from_book(answer)
            others = [b for b in pool if b != answer]
            text = _clean(result.get("text", "")) if result.get("found") else ""
            if not _usable(text):
                continue
            choices = rng.sample(others, min(3, len(others))) + [answer]
            rng.shuffle(choices)
            return {"text": text, "answer": answer, "choices": choices, "reference": result.get("reference", ""),
                    "tradition": tradition}
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
        return reveal_embed(question_embed(self.question, self.hard), self.question, list(self.answers.values()))

    async def on_timeout(self):
        _mark_answer(self.children, self.question)
        if self.message is not None:
            try:
                await self.message.edit(embed=self.reveal_embed(), view=self)
            except discord.HTTPException as e:
                log.warning(f"Couldn't reveal the quiz answer: {e}")


def _question_title(question: dict, hard: bool) -> str:
    if question.get("tradition"):
        return f"which book is this from? ({TRADITIONS[question['tradition']][0]})"
    return "which tradition's text is this?" if hard else "which book is this from?"


def question_embed(question: dict, hard: bool) -> discord.Embed:
    title = _question_title(question, hard)
    embed = discord.Embed(
        title=f"❓ {title[0].upper()}{title[1:]}",
        description=f"*{question['text']}*",
        color=discord.Color.dark_teal(),
    )
    embed.set_footer(text=f"Pick an answer below — one try each. Revealed in {ROUND_SECONDS} seconds.")
    return embed


def reveal_embed(embed: discord.Embed, question: dict, answers: list) -> discord.Embed:
    """`embed` (the question) with the answer and who got it; answers: [(name, correct), ...]."""
    winners = [name for name, ok in answers if ok]
    embed.add_field(name="Answer", value=f"**{question['answer']}** — {question['reference']}", inline=False)
    embed.add_field(name="Got it right", value=", ".join(winners)[:1024] if winners else "Nobody this time!", inline=False)
    embed.set_footer(text=f"{len(answers)} answered · !quiz for another · !quiz leaderboard")
    return embed


def _mark_answer(buttons, question: dict) -> None:
    for item in buttons:
        item.disabled = True
        if item.label == question["answer"][:80]:
            item.style = discord.ButtonStyle.success


@bot.command(name="quiz", aliases=["guess"])
async def cmd_quiz(ctx, *, mode: str = ""):
    """Guess which book a verse comes from.
    Usage: !quiz              — a Bible verse
           !quiz hard         — a passage from one of many traditions
           !quiz buddhist     — which of a tradition's books (also chinese, hindu, classical, ...)
           !quiz leaderboard  — top scorers"""
    mode = mode.strip().lower()
    if mode in ("leaderboard", "lb", "scores"):
        guild = getattr(ctx, "guild", None)
        await ctx.send(embed=leaderboard_embed(guild.id if guild else None),
                       allowed_mentions=discord.AllowedMentions.none())
        return
    key = tradition(mode) if mode not in ("", "hard") else None
    if mode and mode != "hard" and key != "bible" and key not in QUIZ_POOLS:
        await ctx.send("Pick a quiz: `!quiz` (the Bible), `!quiz hard` (many traditions), or one tradition: "
                       + ", ".join(f"`!quiz {k}`" for k in QUIZ_POOLS) + ".")
        return
    hard = mode == "hard"
    question = make_question(hard, tradition=key if key in QUIZ_POOLS else "")
    if question is None:
        await ctx.send("⚠️ I couldn't come up with a question just now — try again.")
        return
    view = QuizView(question, hard)
    view.message = await ctx.send(embed=question_embed(question, hard), view=view)


@bot.tree.command(name="quiz", description="Guess which book a verse comes from")
@app_commands.describe(mode="Bible (default), hard (many traditions), one tradition, or leaderboard")
@app_commands.choices(mode=[app_commands.Choice(name="Bible", value=""),
                            app_commands.Choice(name="Hard: many traditions", value="hard"),
                            *[app_commands.Choice(name=TRADITIONS[k][0].split(" ", 1)[1], value=k) for k in QUIZ_POOLS],
                            app_commands.Choice(name="Leaderboard", value="leaderboard")])
async def quiz_slash(interaction: discord.Interaction, mode: str = ""):
    await interaction.response.defer()
    ctx = await bot.get_context(interaction)
    await cmd_quiz(ctx, mode=mode)


# ── Daily quiz (!quizsetup) ─────────────────────────────────────────────────
# One question a day in a channel the admins choose; posting the next one
# first reveals the previous one's answer. Unlike !quiz a round lasts a day,
# across restarts, so the buttons are persistent (DynamicItem, carrying the
# round number) and the round lives in data/daily_quiz.json: {guild id:
# {"round", "date", "question", "hard", "channel_id", "message_id",
# "answers": {user id: [name, correct]}}}.
# Settings in guild_config.json: quiz_channel_id, quiz_time, quiz_kind.

DAILY_QUIZ_PATH = ROOT / "data" / "daily_quiz.json"
DEFAULT_QUIZ_TIME = "18:00"


def _load_daily() -> dict:
    try:
        return json.loads(DAILY_QUIZ_PATH.read_text(encoding="utf-8")) if DAILY_QUIZ_PATH.exists() else {}
    except Exception:
        return {}


class DailyQuizButton(discord.ui.DynamicItem[discord.ui.Button],
                      template=r"dquiz:(?P<guild>\d+):(?P<round>\d+):(?P<idx>\d)"):
    def __init__(self, guild_id, round_no: int, idx: int, label: str):
        super().__init__(discord.ui.Button(label=label[:80], style=discord.ButtonStyle.secondary,
                                           custom_id=f"dquiz:{guild_id}:{round_no}:{idx}"))
        self.guild_id, self.round_no, self.idx = str(guild_id), int(round_no), idx

    @classmethod
    async def from_custom_id(cls, interaction, item, match):
        return cls(match["guild"], int(match["round"]), int(match["idx"]), item.label or "")

    async def callback(self, interaction: discord.Interaction):
        await answer_daily(interaction, self.guild_id, self.round_no, self.idx)


bot.add_dynamic_items(DailyQuizButton)


async def answer_daily(interaction, guild_id: str, round_no: int, idx: int) -> None:
    daily = _load_daily()
    state = daily.get(guild_id)
    if not state or state["round"] != round_no:
        await interaction.response.send_message("This daily quiz is over — try the newest one, "
                                                "or `!quiz` any time!", ephemeral=True)
        return
    uid = str(interaction.user.id)
    if uid in state["answers"]:
        await interaction.response.send_message("You've already answered this one — the answer comes "
                                                "with the next question.", ephemeral=True)
        return
    correct = state["question"]["choices"][idx] == state["question"]["answer"]
    state["answers"][uid] = [str(interaction.user.display_name), correct]
    _atomic_write_json(DAILY_QUIZ_PATH, daily)
    score = record_answer(guild_id, interaction.user.id, correct)
    verdict = "✅ Correct!" if correct else "❌ Not quite — the answer is revealed with the next question."
    await interaction.response.send_message(f"{verdict} {score_line(score)}", ephemeral=True)


def _daily_view(guild_id, round_no: int, question: dict, revealed: bool = False) -> discord.ui.View:
    view = discord.ui.View(timeout=None)          # persistent buttons: must never time out
    for i, choice in enumerate(question["choices"]):
        view.add_item(DailyQuizButton(guild_id, round_no, i, choice))
    if revealed:
        _mark_answer([item.item for item in view.children], question)
    return view


def _daily_embed(question: dict, hard: bool) -> discord.Embed:
    embed = question_embed(question, hard)
    embed.title = "📅 Daily quiz: " + _question_title(question, hard)
    embed.set_footer(text="One guess each · the answer comes with the next question · !quiz leaderboard")
    return embed


async def post_daily_quiz(client, guild_id, channel, today: datetime.date, kind: str = "bible") -> bool:
    """Reveal this server's previous daily quiz, then post a new one in `channel`."""
    gid = str(guild_id)
    previous = _load_daily().get(gid)
    if previous:
        old_channel = client.get_channel(int(previous["channel_id"]))
        if old_channel is not None:
            try:
                embed = reveal_embed(_daily_embed(previous["question"], previous.get("hard", False)),
                                     previous["question"], [tuple(a) for a in previous["answers"].values()])
                await old_channel.get_partial_message(int(previous["message_id"])).edit(
                    embed=embed, view=_daily_view(gid, previous["round"], previous["question"], revealed=True))
            except discord.HTTPException as e:
                log.warning(f"Couldn't reveal the previous daily quiz in guild {gid}: {e}")
    hard = kind == "hard"
    question = make_question(hard, tradition=kind if kind in QUIZ_POOLS else "")
    if question is None:
        return False
    round_no = (previous or {}).get("round", 0) + 1
    message = await channel.send(embed=_daily_embed(question, hard), view=_daily_view(gid, round_no, question))
    daily = _load_daily()
    daily[gid] = {"round": round_no, "date": today.isoformat(), "question": question, "hard": hard,
                  "channel_id": channel.id, "message_id": message.id, "answers": {}}
    _atomic_write_json(DAILY_QUIZ_PATH, daily)
    return True


async def run_daily_quizzes(client, today: datetime.date, current_hm: str) -> int:
    posted = 0
    for guild_id, g in _load_guild_config().items():
        channel_id = g.get("quiz_channel_id")
        if not channel_id or g.get("quiz_time", DEFAULT_QUIZ_TIME) != current_hm:
            continue
        channel = client.get_channel(int(channel_id))
        if channel is None:
            continue
        try:
            posted += await post_daily_quiz(client, guild_id, channel, today, g.get("quiz_kind", "bible"))
        except Exception:
            log.exception(f"Failed to post the daily quiz for guild {guild_id}")
    return posted


@tasks.loop(minutes=1)
async def daily_quiz_task():
    now = datetime.datetime.now(datetime.timezone.utc)
    await run_daily_quizzes(bot, now.date(), f"{now.hour:02d}:{now.minute:02d}")


@daily_quiz_task.before_loop
async def _before_daily_quiz():
    await bot.wait_until_ready()


@bot.command(name="quizsetup", aliases=["quizconfig"])
@commands.has_permissions(administrator=True)
async def cmd_quizsetup(ctx, action: str = "", *, arg: str = ""):
    """Configure this server's daily quiz.
    Usage: !quizsetup                  — show this server's settings
           !quizsetup channel #chan    — post a daily quiz question there
           !quizsetup time 18:00       — daily post time (24h UTC)
           !quizsetup kind bible       — bible | hard (many traditions) | a tradition (buddhist, chinese, ...)
           !quizsetup test             — post one now (reveals the current one)
           !quizsetup off              — stop the daily quiz"""
    if not ctx.guild:
        await ctx.send("This command only works in a server.")
        return
    g = _load_guild_config().get(str(ctx.guild.id), {})
    channel_id = g.get("quiz_channel_id")
    time_hm, kind = g.get("quiz_time", DEFAULT_QUIZ_TIME), g.get("quiz_kind", "bible")
    action = action.strip().lower()

    if not action:
        embed = discord.Embed(title=f"📅 Daily quiz — {ctx.guild.name}", color=discord.Color.dark_teal())
        embed.add_field(name="Channel", value=f"<#{channel_id}>" if channel_id else "*not set — daily quiz is off*")
        embed.add_field(name="Time (UTC)", value=time_hm)
        embed.add_field(name="Kind", value=kind)
        embed.set_footer(text="!quizsetup channel #chan · time HH:MM · kind bible|hard|<tradition> · test · off")
        await ctx.send(embed=embed)
        return
    if action == "off":
        _update_guild_config(ctx.guild.id, quiz_channel_id=None)
        await ctx.send("The daily quiz is off for this server.")
        return
    if action == "channel":
        channel = ctx.message.channel_mentions[0] if ctx.message.channel_mentions else None
        if channel is None:
            await ctx.send("Mention a channel: `!quizsetup channel #general`")
            return
        _update_guild_config(ctx.guild.id, quiz_channel_id=channel.id)
        await ctx.send(f"A daily quiz question will be posted in {channel.mention} at {time_hm} UTC ({kind}).")
        return
    if action == "time":
        m = re.match(r"^(\d{1,2}):(\d{2})$", arg.strip())
        if not m or not (0 <= int(m.group(1)) <= 23 and 0 <= int(m.group(2)) <= 59):
            await ctx.send("Use 24-hour UTC time: `!quizsetup time 18:00`")
            return
        hm = f"{int(m.group(1)):02d}:{int(m.group(2)):02d}"
        _update_guild_config(ctx.guild.id, quiz_time=hm)
        await ctx.send(f"Daily quiz time set to **{hm} UTC**.")
        return
    if action == "kind":
        new_kind = arg.strip().lower()
        new_kind = new_kind if new_kind in ("bible", "hard") else (tradition(new_kind) or new_kind)
        if new_kind not in ("bible", "hard", *QUIZ_POOLS):
            await ctx.send("Choose `bible`, `hard`, or a tradition: " + ", ".join(f"`{k}`" for k in QUIZ_POOLS) + ".")
            return
        _update_guild_config(ctx.guild.id, quiz_kind=new_kind)
        await ctx.send(f"Daily quiz set to **{new_kind}**.")
        return
    if action == "test":
        channel = bot.get_channel(int(channel_id)) if channel_id else ctx.channel
        if not await post_daily_quiz(bot, ctx.guild.id, channel, datetime.datetime.now(datetime.timezone.utc).date(), kind):
            await ctx.send("⚠️ I couldn't come up with a question just now — try again.")
        return
    await ctx.send("Unknown option. Use `channel`, `time`, `kind`, `test`, or `off` — see `!help quizsetup`.")
