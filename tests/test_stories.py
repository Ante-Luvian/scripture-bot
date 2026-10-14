"""!story: every passage (and every Christian reader of one) resolves, and says what the table says it does."""
import asyncio
import json
import re

import pytest

from core import ROOT

STORIES = json.loads((ROOT / "data" / "stories.json").read_text(encoding="utf-8"))["stories"]


def _flat(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"\*\*\[[\w:.]+\]\*\*|\*\*|──[^─]*──", " ", text)).strip()


def _cases():
    for key, story in STORIES.items():
        for p in story["passages"]:
            yield pytest.param(p["ref"], p["quote"], id=f"{key}:{p['ref']}")
            for r in p.get("read_by", []):
                yield pytest.param(r["ref"], r["quote"], id=f"{key}:{p['ref']}<-{r['who']}")


@pytest.mark.parametrize("ref, quote", list(_cases()))
def test_each_passage_is_there(lookup, ref, quote):
    result = lookup.get_verse(ref)
    assert result.get("found"), (ref, result.get("error"))
    assert _flat(quote) in _flat(result["text"]), (ref, quote, result["text"][:300])


@pytest.fixture(scope="module")
def S(bot_module):
    from bot_commands import stories
    return stories


def test_names_and_aliases(S):
    assert S.find_story("Flood")["title"] == "The Flood"
    assert S.find_story("deluge")["title"] == "The Flood"
    assert S.find_story("tower of babel")["title"] == "The Tower to Heaven"
    assert S.find_story("pagan prophecies")["title"] == "Christ Foretold Among the Pagans"
    assert S.find_story("zzz") is None


def test_the_story_embed(S, fake_ctx):
    asyncio.run(S.send_story(fake_ctx, "flood"))
    sent = fake_ctx.sent[-1]
    embed = sent["embed"]
    assert embed.title == "🌊 The Flood" or "The Flood" in embed.title
    assert any("Genesis 7:17" in f.name for f in embed.fields)
    assert any("Gilgamesh" in f.name and "Six days" in f.value for f in embed.fields)    # the excerpt starts at the quote
    menu = [getattr(i, "item", i) for i in sent["view"].children][-1]
    assert len(menu.options) == len(STORIES["flood"]["passages"])


def test_the_christian_readers_are_shown(S, fake_ctx):
    asyncio.run(S.send_story(fake_ctx, "christ"))
    fields = fake_ctx.sent[-1]["embed"].fields
    eclogue = next(f for f in fields if "Eclogues 4" in f.name)
    assert "Constantine" in eclogue.value and "Augustine" in eclogue.value


def test_the_list(S, fake_ctx):
    asyncio.run(S.send_story(fake_ctx, ""))
    text = fake_ctx.sent[-1]["embed"].description
    assert all(f"`!story {k}`" in text for k in STORIES)
