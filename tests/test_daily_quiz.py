"""The daily quiz (!quizsetup): posting, answering across a day, the reveal."""
import asyncio
import datetime

import pytest

from conftest import FakeCtx

TODAY = datetime.date(2026, 10, 12)
QUESTION = {"text": "Jesus wept.", "answer": "John", "choices": ["Mark", "John", "Luke", "Acts"], "reference": "John 11:35"}


@pytest.fixture(scope="module")
def quiz(bot_module):
    from bot_commands import quiz
    return quiz


@pytest.fixture(autouse=True)
def fixed_question(quiz, monkeypatch):
    monkeypatch.setattr(quiz, "make_question", lambda hard=False: dict(QUESTION))


class Channel:
    id = 100
    mention = "#quiz"

    def __init__(self):
        self.sent, self.edits, self.next_id = [], {}, 1

    async def send(self, content=None, **kw):
        self.sent.append(kw)
        self.next_id += 1
        return type("Msg", (), {"id": self.next_id - 1})()

    def get_partial_message(self, mid):
        channel = self

        class Partial:
            async def edit(self, **kw):
                channel.edits[mid] = kw
        return Partial()


class Client:
    def __init__(self, channel):
        self.channel = channel

    def get_channel(self, cid):
        return self.channel if cid == self.channel.id else None


class Response:
    def __init__(self):
        self.sent = []

    async def send_message(self, text, ephemeral=False):
        self.sent.append((text, ephemeral))


def _press(quiz, view, label, user_id, name="tester"):
    """Press a button as Discord would after a restart: rebuilt from its custom_id."""
    item = next(c for c in view.children if c.item.label == label)
    match = quiz.DailyQuizButton.__discord_ui_compiled_template__.fullmatch(item.custom_id)
    button = asyncio.run(quiz.DailyQuizButton.from_custom_id(None, item.item, match))
    user = type("U", (), {"id": user_id, "display_name": name})()
    interaction = type("I", (), {"user": user, "response": Response()})()
    asyncio.run(button.callback(interaction))
    return interaction.response.sent[0]


def test_a_day_of_answers_then_the_reveal(quiz):
    channel = Channel()
    client = Client(channel)
    assert asyncio.run(quiz.post_daily_quiz(client, 5, channel, TODAY))
    first = channel.sent[0]
    assert first["embed"].title == "📅 Daily quiz: which book is this from?"
    view = first["view"]
    assert view.timeout is None and [c.item.label for c in view.children] == QUESTION["choices"]

    text, private = _press(quiz, view, "John", 1, "Ann")
    assert private and text.startswith("✅ Correct!")
    assert "already answered" in _press(quiz, view, "Mark", 1)[0]
    assert _press(quiz, view, "Luke", 2, "Bob")[0].startswith("❌ Not quite")
    assert quiz._load_scores()["guilds"]["5"]["1"]["correct"] == 1        # counts on the server's leaderboard

    # the next day: yesterday's is revealed, then a new one is posted
    asyncio.run(quiz.post_daily_quiz(client, 5, channel, TODAY + datetime.timedelta(days=1)))
    reveal = channel.edits[1]
    fields = {f.name: f.value for f in reveal["embed"].fields}
    assert fields["Answer"] == "**John** — John 11:35" and fields["Got it right"] == "Ann"
    buttons = [c.item for c in reveal["view"].children]
    assert all(b.disabled for b in buttons) and next(b for b in buttons if b.label == "John").style.name == "success"
    assert len(channel.sent) == 2
    assert "over" in _press(quiz, view, "Acts", 3)[0]                      # old buttons no longer count


def test_posted_at_the_chosen_time_only(quiz):
    import core
    channel = Channel()
    core._update_guild_config(5, quiz_channel_id=100, quiz_time="18:00")
    core._update_guild_config(6, quiz_channel_id=None)
    assert asyncio.run(quiz.run_daily_quizzes(Client(channel), TODAY, "17:59")) == 0
    assert asyncio.run(quiz.run_daily_quizzes(Client(channel), TODAY, "18:00")) == 1


def _admin_ctx(channel):
    ctx = FakeCtx()
    ctx.guild = type("G", (), {"id": 5, "name": "Bible Study"})()
    ctx.channel = channel
    ctx.message = type("M", (), {"channel_mentions": [channel]})()
    return ctx


def test_quizsetup(quiz, bot_module, monkeypatch):
    import core
    channel = Channel()
    monkeypatch.setattr(quiz, "bot", Client(channel))
    ctx = _admin_ctx(channel)
    asyncio.run(quiz.cmd_quizsetup.callback(ctx, "channel"))
    asyncio.run(quiz.cmd_quizsetup.callback(ctx, "time", arg="7:05"))
    asyncio.run(quiz.cmd_quizsetup.callback(ctx, "kind", arg="hard"))
    g = core._load_guild_config()["5"]
    assert (g["quiz_channel_id"], g["quiz_time"], g["quiz_kind"]) == (100, "07:05", "hard")
    asyncio.run(quiz.cmd_quizsetup.callback(ctx, "test"))
    assert channel.sent[-1]["embed"].title == "📅 Daily quiz: which tradition's text is this?"
    asyncio.run(quiz.cmd_quizsetup.callback(ctx, "off"))
    assert core._load_guild_config()["5"]["quiz_channel_id"] is None
    assert bot_module.bot.get_command("quizsetup").checks          # admins only
