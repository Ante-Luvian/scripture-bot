"""!physiologus and !reynard: two medieval books of beasts (scripts/build_beasts.py)."""
import asyncio
import re

import pytest


@pytest.fixture(scope="module")
def beasts(lookup):
    from bot_commands import beasts as b
    return b


class Ctx:
    guild = None
    author = "tester"

    def __init__(self):
        self.sent = []

    async def send(self, content=None, **kw):
        self.sent.append((content, kw))


def ask(beasts, key, q):
    ctx = Ctx()
    asyncio.run(beasts.send_beast(ctx, key, q))
    return ctx.sent[-1]


def test_the_physiologus_with_its_christian_readings(beasts):
    assert beasts.numbers("ph") == list(range(1, 34))
    lion = " ".join(beasts.chapters("ph")[str(beasts.find("ph", "lion")[0])].values())
    assert "resemblance to the Holy Trinity" in lion and "(Song 5:2)" in lion          # (its notes, in brackets)
    pelican = " ".join(beasts.chapters("ph")[str(beasts.find("ph", "pelican")[0])].values())
    assert "Jesus Christ" in pelican                                                      # (the moral: not cut)
    snake = list(beasts.chapters("ph")[str(beasts.find("ph", "snake")[0])].values())
    assert "**About the Snake and Her Deeds (Third translation)**" in snake               # (both translations)
    assert not any(re.search(r"<|&#|•", v) for c in beasts.chapters("ph").values() for v in c.values())


def test_reynard_whole(beasts):
    assert beasts.numbers("rf") == list(range(1, 45))
    assert beasts.title("rf", 27) == "How Reynart the Fox came another time to the Court."   # (Morley's 2nd "XXVI")
    four = list(beasts.chapters("rf")["4"].values())
    assert "Grymbart the Dasse the Fox’s" in four[0]                                        # (footnote mark gone)
    assert four[-1].startswith("-# Old words: Dasse, Badger")                               # (Morley's glosses)
    text = " ".join(v for c in beasts.chapters("rf").values() for v in c.values() if not v.startswith("-#"))
    assert not re.search(r"\[\d+\]|[A-Za-z]\d{1,3}\b", text)                                # (no page or note marks)


def test_finding(beasts):
    assert ask(beasts, "ph", "pelican")[1]["embed"].title == "🦁 The Pelican"
    assert ask(beasts, "ph", "99")[0] == "The Physiologus's beasts are numbered 1 to 33."
    assert ask(beasts, "ph", "dragon")[0].startswith("I found no beast")
    _, kw = ask(beasts, "rf", "tybert")
    assert kw["embed"].title.startswith("🦊 10.")
    ids = [c.custom_id for c in kw["view"].children]
    assert len(ids) == len(set(ids)) and "beast:rf:after:11:0" in ids and "beast:rf:prev:9:0" in ids
    assert all(len(p) <= 4096 for k in ("ph", "rf") for n in beasts.numbers(k) for p in beasts.pages(k, n))


def test_the_references(lookup):
    assert lookup.get_verse("Physiologus 24")["text"].startswith("**[1]** *About the Pelican*")
    assert lookup.get_verse("Reynard 27")["found"] and lookup.get_verse("Bestiary 19:1")["found"]


def test_tale_opens_them_too_and_neither_has_a_slash_command(beasts):
    """The owner: own ! commands are fine, but not a slash command each -- /tale reaches them."""
    from bot_commands import tales
    from core import bot
    ctx = Ctx()
    asyncio.run(tales.send_tale(ctx, "reynard tybert"))
    assert ctx.sent[-1][1]["embed"].title.startswith("🦊 10.")
    asyncio.run(tales.send_tale(ctx, "physiologus pelican"))
    assert ctx.sent[-1][1]["embed"].title == "🦁 The Pelican"
    asyncio.run(tales.send_tale(ctx, "bestiary"))
    assert ctx.sent[-1][1]["embed"].title.startswith("🦁 ")
    assert bot.get_command("beast").name == "physiologus" and bot.get_command("fox").name == "reynard"
    slash = {c.name for c in bot.tree.get_commands()}
    assert "tale" in slash and not {"physiologus", "reynard"} & slash