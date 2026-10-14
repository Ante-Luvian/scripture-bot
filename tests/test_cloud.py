"""!cloud: a book's distinctive words as a word cloud."""
import asyncio

import pytest


@pytest.fixture(scope="module")
def C(bot_module):
    from bot_commands import cloud
    return cloud


def test_distinctive_not_merely_common(C, lookup):
    words = list(C.distinctive_words("kjv", "Ecclesiastes"))
    assert {"vanity", "vexation"} <= set(words[:5])
    assert not {"the", "and", "unto", "thee", "lord"} & set(words[:20])     # common to every book


def test_the_picture(C, fake_ctx):
    pytest.importorskip("wordcloud")
    asyncio.run(C.cmd_cloud.callback(fake_ctx, book="Song of Solomon"))
    sent = fake_ctx.sent[-1]
    assert sent["embed"].title == "☁️ Song of Solomon" and "beloved" in sent["embed"].description
    assert sent["file"].filename == "cloud.png" and sent["file"].fp.read(8) == b"\x89PNG\r\n\x1a\n"


def test_unknown_book(C, fake_ctx):
    asyncio.run(C.cmd_cloud.callback(fake_ctx, book="Qwxzvbn"))
    assert "don't know a book" in fake_ctx.sent[-1]["content"]
    asyncio.run(C.cmd_cloud.callback(fake_ctx, book=""))
    assert "Which book?" in fake_ctx.sent[-1]["content"]
