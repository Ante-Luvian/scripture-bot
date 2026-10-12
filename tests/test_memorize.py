"""!memorize: the blanked-out practice card, its buttons, and DM reviews."""
import asyncio
import datetime
import re

import pytest

TODAY = datetime.date(2026, 10, 12)


@pytest.fixture(scope="module")
def mem(bot_module):
    from bot_commands import memorize
    return memorize


def _blanks(text):
    return len(re.findall(r"`_+`", text))


def test_each_level_hides_more_and_keeps_the_last_ones_hidden(mem):
    v = mem._verse("John 3:16")
    assert v["text"].startswith("For God so loved")                     # no lone verse number
    levels = [mem.cloze(v["text"], v["reference"], n) for n in range(mem.LEVELS + 1)]
    assert levels[0] == v["text"]
    assert 0 < _blanks(levels[1]) < _blanks(levels[2]) < _blanks(levels[3])
    words = v["text"].split()
    for easier, harder in zip(levels[1:3], levels[2:4]):                  # hidden sets nest
        for a, b in zip(easier.split(), harder.split()):
            assert not ("`_" in a and "`_" not in b)
    assert levels[4].startswith("F G s l t w,") and len(levels[4].split()) == len(words)
    assert mem.cloze(v["text"], v["reference"], 2) == levels[2]           # same card every time


def test_verse_numbers_are_never_blanked(mem):
    v = mem._verse("Psalm 23:1-2")
    card = mem.cloze(v["text"], v["reference"], 4)
    assert card.startswith("**[1]** T L i m s; I s n w.") and "**[2]**" in card


class Response:
    def __init__(self):
        self.edits, self.sent = [], []

    async def edit_message(self, **kw):
        self.edits.append(kw)

    async def send_message(self, text, ephemeral=False):
        self.sent.append((text, ephemeral))


def _press(mem, view, label, user_id=1):
    """Press a button as Discord would after a restart: rebuilt from its custom_id."""
    item = next(c for c in view.children if c.item.label == label)
    match = mem.MemorizeButton.__discord_ui_compiled_template__.fullmatch(item.custom_id)
    button = asyncio.run(mem.MemorizeButton.from_custom_id(None, item.item, match))
    interaction = type("I", (), {"user": type("U", (), {"id": user_id})(), "response": Response()})()
    asyncio.run(button.callback(interaction))
    return interaction.response


def test_command_and_buttons(mem, fake_ctx):
    asyncio.run(mem.cmd_memorize.callback(fake_ctx, arg="John 3:16"))
    msg = fake_ctx.sent[0]
    assert msg["embed"].title == "🧠 Memorize John 3:16 — level 1 of 4" and msg["view"].timeout is None
    harder = _press(mem, msg["view"], "Harder").edits[0]
    assert harder["embed"].title.endswith("level 2 of 4")
    top = _press(mem, harder["view"], "Harder").edits[0]
    top = _press(mem, top["view"], "Harder").edits[0]
    assert top["embed"].title.endswith("level 4 of 4")
    assert next(c.item for c in top["view"].children if c.item.label == "Harder").disabled
    text, private = _press(mem, msg["view"], "Reveal").sent[0]
    assert private and "For God so loved the world" in text
    assert _press(mem, msg["view"], "Easier").edits[0]["embed"].title.endswith("read it through")


def test_long_passages_and_unknown_verses(mem, fake_ctx):
    asyncio.run(mem.cmd_memorize.callback(fake_ctx, arg="Psalm 119"))
    asyncio.run(mem.cmd_memorize.callback(fake_ctx, arg="Hezekiah 3:16"))
    assert "a few verses at a time" in fake_ctx.sent[0]["content"]
    assert "couldn't find" in fake_ctx.sent[1]["content"]


class Client:
    def __init__(self):
        self.dms = []
        outer = self

        class User:
            async def send(self, text, **kw):
                outer.dms.append((text, kw))
        self.user = User()

    def get_user(self, uid):
        return self.user


def test_spaced_reviews_by_dm(mem):
    assert "tomorrow" in mem.schedule(1, "John 3:16", today=TODAY)
    assert "already in your reviews" in mem.schedule(1, "John 3:16", today=TODAY)
    client, day = Client(), TODAY
    assert asyncio.run(mem.run_reviews(client, day, mem.REVIEW_TIME)) == 0        # not due yet
    sent_on = []
    for _ in range(80):
        day += datetime.timedelta(days=1)
        assert asyncio.run(mem.run_reviews(client, day, "07:59")) == 0           # only at REVIEW_TIME
        if asyncio.run(mem.run_reviews(client, day, mem.REVIEW_TIME)):
            sent_on.append((day - TODAY).days)
    assert sent_on == [1, 4, 11, 25, 55]          # after 1, 3, 7, 14, 30 days
    text, kw = client.dms[0]
    assert "Review 1 of 5" in text and kw["embed"].title.endswith("level 4 of 4")
    assert "Last review" in client.dms[-1][0]
    assert mem._load() == {}                      # learned: no longer scheduled


def test_list_and_stop(mem, fake_ctx):
    mem.schedule(1, "John 3:16", today=TODAY)
    asyncio.run(mem.cmd_memorize.callback(fake_ctx, arg="list"))
    assert "**John 3:16** — review 1 of 5 on 2026-10-13" in fake_ctx.sent[0]["embed"].description
    asyncio.run(mem.cmd_memorize.callback(fake_ctx, arg="stop jn 3:16"))
    assert fake_ctx.sent[1]["content"] == "Stopped reviewing **John 3:16**." and mem._load() == {}
