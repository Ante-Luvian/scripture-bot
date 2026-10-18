"""!vov: the Puritan prayers of The Valley of Vision."""
import asyncio

import pytest


@pytest.fixture(scope="module")
def vov(bot_module):
    from bot_commands import vov
    return vov


def test_the_collection(vov):
    assert len(vov.prayers()) >= 190 and len(vov.sections()) >= 10
    trinity = vov.prayers()[1]
    assert trinity["title"] == "The Trinity" and trinity["lines"][0].startswith("THREE IN ONE")
    for p in vov.prayers():
        assert len(vov.prayer_embed(p).description) <= 4096


def test_credit_is_the_puritans(vov):
    footer = vov.prayer_embed(vov.prayers()[0]).footer.text
    assert footer.startswith("A Puritan prayer") and "Bennett" not in footer


@pytest.mark.parametrize("query, check", [
    ("", lambda s: s["embed"].title.startswith("🙏")),
    ("2", lambda s: s["embed"].title == "🙏 The Trinity"),
    ("topics", lambda s: "Penitence and Deprecation" in s["embed"].description),
    ("topics 4", lambda s: s["embed"].title.endswith("Penitence and Deprecation") and "`" in s["embed"].description),
    ("penitence", lambda s: "Penitence" in s["embed"].footer.text),
    ("999", lambda s: "There are" in s["content"]),
    ("zzqx", lambda s: "couldn't find" in s["content"]),
])
def test_the_command(vov, fake_ctx, query, check):
    asyncio.run(vov.send_vov(fake_ctx, query))
    assert check(fake_ctx.sent[-1])
