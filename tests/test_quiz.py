"""!quiz: questions, answering, reveal, scores."""
import asyncio
import random

import pytest


@pytest.fixture(scope="module")
def quiz(bot_module):
    from bot_commands import quiz
    return quiz


@pytest.mark.parametrize("seed", range(15))
def test_bible_question_is_well_formed(quiz, seed):
    q = quiz.make_question(hard=False, rng=random.Random(seed))
    assert q and len(q["choices"]) == 4 and len(set(q["choices"])) == 4
    assert q["answer"] in q["choices"]
    testament = quiz.BIBLE_OT if q["answer"] in quiz.BIBLE_OT else quiz.BIBLE_NT
    assert all(c in testament for c in q["choices"])      # distractors from the same Testament
    assert q["reference"].startswith(q["answer"])
    assert 25 <= len(q["text"]) <= quiz.MAX_TEXT and "**[" not in q["text"]


@pytest.mark.parametrize("seed", range(15))
def test_hard_question_mixes_traditions(quiz, seed):
    q = quiz.make_question(hard=True, rng=random.Random(seed))
    names = [name for _, name in quiz.HARD_POOL]
    assert q and q["answer"] in q["choices"] and all(c in names for c in q["choices"])
    assert "no recoverable text" not in q["text"].lower()


@pytest.mark.parametrize("key", ["buddhist", "chinese", "hindu", "classical", "christian", "jewish",
                                 "apocrypha", "gnostic", "norse", "neareast", "lds", "bahai", "jain", "zoroastrian", "sufi"])
def test_tradition_quiz(quiz, lookup, key):
    for book in quiz.QUIZ_POOLS[key]:
        assert lookup._resolve_book(book)[1] == book, book
        assert lookup.random_verse_from_book(book).get("found"), book
    for seed in range(5):
        q = quiz.make_question(rng=random.Random(seed), tradition=key)
        assert q and q["answer"] in q["choices"] and set(q["choices"]) <= set(quiz.QUIZ_POOLS[key])
        assert len(q["choices"]) == min(4, len(quiz.QUIZ_POOLS[key]))
        assert not q["text"].startswith("*") and "(vv." not in q["text"][:6]     # no title giving it away
    assert quiz.question_embed(q, False).title.startswith("❓ Which book is this from? (")


def test_random_passage_skips_empty_chapters(lookup):
    import random as r
    for seed in range(40):                     # the Enneads and Enoch have empty chapters
        r.seed(seed)
        assert lookup.random_verse_from_book("Enneads")["found"]
        assert lookup.random_verse_from_book("Book of Enoch")["found"]


def test_quiz_command_traditions(quiz, fake_ctx):
    asyncio.run(quiz.cmd_quiz.callback(fake_ctx, mode="Buddhism"))
    assert fake_ctx.sent[-1]["embed"].title == "❓ Which book is this from? (☸️ Buddhist)"
    asyncio.run(quiz.cmd_quiz.callback(fake_ctx, mode="islamic"))          # one book only: not a quiz
    assert "Pick a quiz" in fake_ctx.sent[-1]["content"]


def test_every_hard_pool_work_exists(quiz, lookup):
    for book, _ in quiz.HARD_POOL:
        assert lookup._resolve_book(book)[1] is not None, book


QUESTION = {"text": "Jesus wept.", "answer": "John", "choices": ["Mark", "John", "Luke", "Acts"], "reference": "John 11:35"}


class Response:
    def __init__(self):
        self.sent = []

    async def send_message(self, text, ephemeral=False):
        self.sent.append((text, ephemeral))


def _click(view, label, user_id, name="tester", guild_id=10):
    button = next(b for b in view.children if b.label == label)
    user = type("U", (), {"id": user_id, "display_name": name})()
    interaction = type("I", (), {"user": user, "response": Response(), "guild_id": guild_id})()
    asyncio.run(button.callback(interaction))
    return interaction.response.sent


def test_answers_are_private_one_per_person_and_scored(quiz):
    view = quiz.QuizView(QUESTION, hard=False)
    assert [b.label for b in view.children] == QUESTION["choices"]
    assert _click(view, "John", 1, "Ann")[0][0].startswith("✅ Correct!") and _click(view, "Mark", 1)[0][1]
    assert "already answered" in _click(view, "Mark", 1)[0][0]     # one try each
    reply = _click(view, "Luke", 2, "Bob")[0]
    assert reply[0].startswith("❌") and reply[1]                    # ephemeral
    scores = quiz._load_scores()["guilds"]["10"]
    assert (scores["1"]["correct"], scores["1"]["answered"]) == (1, 1)
    assert (scores["2"]["correct"], scores["2"]["answered"]) == (0, 1)


def test_scores_are_kept_per_server(quiz):
    quiz.record_answer(10, 1, True)
    quiz.record_answer(20, 2, True)
    board = quiz.leaderboard_embed(10).fields[1].value
    assert "<@1>" in board and "<@2>" not in board
    assert "No answers in this server" in quiz.leaderboard_embed(30).description
    quiz.record_answer(None, 3, True)              # in DMs
    assert "3" in quiz._load_scores()["guilds"]["dm"]


def test_weekly_scores_restart_on_monday(quiz):
    import datetime
    sunday, monday = datetime.date(2026, 10, 18), datetime.date(2026, 10, 19)
    quiz.record_answer(10, 1, True, today=sunday)
    quiz.record_answer(10, 1, True, today=sunday)
    assert quiz.weekly_top(quiz.week_key(sunday)) == {"10": [("1", 2, 2)]}   # still readable on Monday
    s = quiz.record_answer(10, 1, False, today=monday)
    assert (s["week_correct"], s["week_answered"], s["correct"], s["answered"]) == (0, 1, 2, 3)
    week, all_time = quiz.leaderboard_embed(10, today=monday).fields
    assert week.value == "1. <@1> — 0 right of 1" and all_time.value.startswith("1. <@1> — 2 right of 3")


def test_streaks(quiz):
    for _ in range(3):
        s = quiz.record_answer(10, 1, True)
    assert s["streak"] == 3 and quiz.score_line(s).startswith("🔥 3 in a row!")
    s = quiz.record_answer(10, 1, False)
    assert s["streak"] == 0 and s["best_streak"] == 3 and "🔥" not in quiz.score_line(s)
    assert "best run 3 🔥" in quiz.leaderboard_embed(10).fields[1].value


def test_reveal_after_the_round(quiz):
    view = quiz.QuizView(QUESTION, hard=False)
    _click(view, "John", 1, "Ann")
    _click(view, "Luke", 2, "Bob")
    edits = []

    class Msg:
        async def edit(self, **kw):
            edits.append(kw)
    view.message = Msg()
    asyncio.run(view.on_timeout())
    embed = edits[0]["embed"]
    fields = {f.name: f.value for f in embed.fields}
    assert fields["Answer"] == "**John** — John 11:35" and fields["Got it right"] == "Ann"
    assert all(b.disabled for b in view.children)
    assert next(b for b in view.children if b.label == "John").style.name == "success"


def test_quiz_command_and_leaderboard(quiz, fake_ctx):
    asyncio.run(quiz.cmd_quiz.callback(fake_ctx, mode=""))
    msg = fake_ctx.sent[0]
    assert msg["embed"].title == "❓ Which book is this from?" and len(msg["view"].children) == 4
    fake_ctx.guild = type("G", (), {"id": 10})()
    quiz.record_answer(10, 5, True)
    quiz.record_answer(10, 6, False)
    asyncio.run(quiz.cmd_quiz.callback(fake_ctx, mode="leaderboard"))
    board = fake_ctx.sent[-1]["embed"].fields[1].value.splitlines()
    assert board[0] == "1. <@5> — 1 right of 1"
