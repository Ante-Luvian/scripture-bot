"""!pascal / !pensees (the owner, 2026-11-11): one of Pascal's Pensées at random, by number or by its words, with a
🖼️ Card and ◀ ▶ to the thoughts either side."""
import asyncio
import random
import types

import pytest

from conftest import FakeCtx


@pytest.fixture(scope="module")
def oracles(bot_module):
    from bot_commands import oracles
    return oracles


def test_picks(oracles):
    assert oracles._pascal_pick("233") == "233"
    assert "Infinite—nothing" in oracles._pascal_thought("233")[1]
    assert "numbered 1 to 924" in oracles._pascal_pick("925")
    assert "numbered" in oracles._pascal_pick("0")
    n = oracles._pascal_pick("heart reason", rng=random.Random(1))
    text = oracles._pascal_thought(n)[1].lower()
    assert "heart" in text and "reason" in text
    assert "None of Pascal's thoughts" in oracles._pascal_pick("zzzzqq")
    assert oracles._pascal_pick("", rng=random.Random(2)) in oracles._pascal()


def test_message_has_card_and_neighbours(oracles):
    message = oracles._pascal_message("233")
    assert message["embed"].title == "🕯️ Pascal, Pensées 233"
    assert "Section III" in message["embed"].footer.text                 # (the wager's section)
    items = [c.item for c in message["view"].children]
    assert items[0].custom_id == "ocard:pascal:233"
    assert [i.label for i in items[1:]] == ["◀ 232", "234 ▶"]
    first = [c.item.custom_id for c in oracles._pascal_message("1")["view"].children]
    assert not any(cid.endswith(":p") for cid in first)                  # (nothing before the first)
    for n in oracles._pascal():
        assert len(oracles._pascal_message(n)["embed"].description) <= 4096, n


def test_card_content_renders(oracles):
    title, text, source = oracles._oracle_card_content("pascal", "347")
    assert title == "Pascal, Pensées 347" and "thinking reed" in text and source == "trans. W. F. Trotter"
    from bot_commands.card import _render_verse_card
    buf = _render_verse_card(title, text, source, "", "parchment", justify=True)
    assert buf.getbuffer().nbytes > 10000


def test_the_commands(bot_module):
    for name in ("pascal", "pensees", "pensées"):
        assert bot_module.bot.get_command(name).name == "pascal"
    ctx = FakeCtx()
    asyncio.run(bot_module.bot.get_command("pascal").callback(ctx, query="347"))
    assert "Pensées 347" in ctx.sent[-1]["embed"].title


def test_nav_button_edits_to_its_thought(oracles):
    edits = []

    class Response:
        async def edit_message(self, **kw): edits.append(kw)
    nav = oracles.PascalNav("234", "n")
    asyncio.run(nav.callback(types.SimpleNamespace(response=Response())))
    assert edits[-1]["embed"].title.endswith("Pensées 234")
