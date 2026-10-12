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


def test_every_hard_pool_work_exists(quiz, lookup):
    for book, _ in quiz.HARD_POOL:
        assert lookup._resolve_book(book)[1] is not None, book


QUESTION = {"text": "Jesus wept.", "answer": "John", "choices": ["Mark", "John", "Luke", "Acts"], "reference": "John 11:35"}


class Response:
    def __init__(self):
        self.sent = []

    async def send_message(self, text, ephemeral=False):
        self.sent.append((text, ephemeral))


def _click(view, label, user_id, name="tester"):
    button = next(b for b in view.children if b.label == label)
    user = type("U", (), {"id": user_id, "display_name": name})()
    interaction = type("I", (), {"user": user, "response": Response()})()
    asyncio.run(button.callback(interaction))
    return interaction.response.sent


def test_answers_are_private_one_per_person_and_scored(quiz):
    view = quiz.QuizView(QUESTION, hard=False)
    assert [b.label for b in view.children] == QUESTION["choices"]
    assert _click(view, "John", 1, "Ann")[0][0].startswith("✅ Correct!") and _click(view, "Mark", 1)[0][1]
    assert "already answered" in _click(view, "Mark", 1)[0][0]     # one try each
    reply = _click(view, "Luke", 2, "Bob")[0]
    assert reply[0].startswith("❌") and reply[1]                    # ephemeral
    scores = quiz._load_scores()
    assert scores["1"] == {"correct": 1, "answered": 1} and scores["2"] == {"correct": 0, "answered": 1}


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
    quiz.record_answer(5, True)
    quiz.record_answer(6, False)
    asyncio.run(quiz.cmd_quiz.callback(fake_ctx, mode="leaderboard"))
    board = fake_ctx.sent[-1]["embed"].description.splitlines()
    assert board[0] == "1. <@5> — 1 right of 1"
