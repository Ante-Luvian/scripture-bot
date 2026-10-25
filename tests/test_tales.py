"""!tale: the Grimms' Household Tales (Hunt)."""
import asyncio

import pytest


@pytest.fixture(scope="module")
def tales(lookup):
    from bot_commands import tales as t
    return t


class Ctx:
    guild = None
    author = "tester"

    def __init__(self):
        self.sent = []

    async def send(self, content=None, **kw):
        self.sent.append((content, kw))


def ask(tales, q):
    ctx = Ctx()
    asyncio.run(tales.send_tale(ctx, q))
    return ctx.sent[-1]


def test_all_210(tales):
    assert tales.numbers() == list(range(1, 211))
    assert tales.title(12) == "Rapunzel" and tales.title(201) == "St. Joseph in the Forest"
    assert tales.label(203) == "Children's Legend 3"
    assert tales.paragraphs(12)[2] == "“Rapunzel, Rapunzel,\nLet down thy hair to me.”"   # (a rhyme keeps its lines)
    assert "\n" not in tales.paragraphs(12)[0]                                          # (prose doesn't)


def test_finding_one(tales):
    assert ask(tales, "12")[1]["embed"].title == "🏰 Rapunzel"
    _, kw = ask(tales, "sleeping beauty")
    assert kw["embed"].title == "🏰 Briar-Rose" and "sleeping beauty" in kw["embed"].author.name
    assert ask(tales, "hansel and gretel")[1]["embed"].title == "🏰 Hansel and Grethel"
    assert ask(tales, "red riding hood")[1]["embed"].title == "🏰 Little Red-Cap"
    assert ask(tales, "snow white and rose red")[1]["embed"].title == "🏰 Snow-White and Rose-Red"
    for name, n in tales.NAMES.items():                  # (every name it knows leads to a tale that has it)
        assert str(n) in tales.tales(), name
    assert ask(tales, "211")[0].startswith("The tales are numbered 1 to 200")
    assert ask(tales, "qqqq")[0].startswith("I found no tale")


def test_long_tales_turn_pages(tales):
    _, kw = ask(tales, "60")
    pages = tales.pages(60)
    assert len(pages) > 15 and all(len(p) < 4096 for p in pages)
    ids = [getattr(i, "custom_id", None) for i in kw["view"].children]
    assert "tale:next:60:1:" in ids and len(set(ids)) == len(ids)
    assert "page 1 of" in kw["embed"].footer.text


def test_the_reference(lookup):
    r = lookup.get_verse("Grimm 12:3")
    assert r["found"] and r["text"].startswith("**[3]** “Rapunzel, Rapunzel,") and r["tradition"] == "ballads"
