"""!theme (one passage per tradition) and !search ... in:<tradition>."""
import asyncio

import pytest


def test_stems(lookup):
    assert lookup._stem("forgiveness") == "forgiv"
    assert lookup._stem("love") == "lov" and lookup._stem("souls") == "soul"


def test_theme_passages_one_per_tradition(lookup):
    from scripture_lookup import TRADITIONS
    passages = lookup.theme_passages("love")
    labels = [label for label, _ in passages]
    order = [label for label, _ in TRADITIONS.values()]
    assert labels == [l for l in order if l in labels]                  # tradition order, one each
    assert {"📖 Bible", "☸️ Buddhist", "☯️ Chinese", "🕉️ Hindu", "☪️ Islamic"} <= set(labels)
    for _, hit in passages:
        assert "lov" in hit["text"].lower() and 40 <= len(hit["text"]) <= 600
        assert lookup.get_verse(hit["reference"])["found"], hit["reference"]   # every reference can be opened
    bible = dict(passages)["📖 Bible"]
    assert bible["text"].lower().count("lov") >= 2                       # about love, not a passing mention


def test_theme_command(bot_module, fake_ctx, monkeypatch):
    from bot_commands import verse
    monkeypatch.setattr(verse, "_check_search_cooldown", lambda uid: True)
    asyncio.run(verse.cmd_theme.callback(fake_ctx, query="forgiveness"))
    embed = fake_ctx.sent[0]["embed"]
    assert embed.title == "🌐 Forgiveness — across the traditions"
    assert len(embed) <= 6000 and len(embed.fields) >= 8
    assert all("**" in f.value for f in embed.fields)                    # the theme word is highlighted
    asyncio.run(verse.cmd_theme.callback(fake_ctx, query="xyzzyplugh"))
    assert "couldn't find" in fake_ctx.sent[-1]["content"]


@pytest.mark.parametrize("typed, key", [("buddhist", "buddhist"), ("Buddhism", "buddhist"), ("daoist", "chinese"),
                                        ("islam", "islamic"), ("church", "christian"), ("nonsense", None)])
def test_tradition_names(typed, key):
    from scripture_lookup import tradition
    assert tradition(typed) == key


def test_search_in_one_tradition(lookup, bot_module, fake_ctx, monkeypatch):
    from bot_commands import verse
    hits = lookup.search_by_corpus("nirvana", ("buddhist",))
    assert hits and all(label == "☸️ Buddhist" for label in hits)
    monkeypatch.setattr(verse, "_check_search_cooldown", lambda uid: True)
    asyncio.run(verse.search_prefix.callback(fake_ctx, query="nirvana in:buddhist"))
    assert fake_ctx.sent[0]["embed"].description.startswith("☸️ Buddhist")
    asyncio.run(verse.search_prefix.callback(fake_ctx, query="love in:martian"))
    assert "don't know the tradition" in fake_ctx.sent[-1]["content"]
