"""The NIV: bolls.life now answers every NIV request with a notice from Biblica in place of the verse,
which the bot was posting as scripture. It's withdrawn, and asking for it explains why."""
import asyncio
import io
import json

import pytest

import translation_lookup as tl


@pytest.mark.parametrize("name", ["NIV", "niv84", "NIV2011"])
def test_asking_for_the_niv_explains_it_is_gone(name):
    for result in (tl.get_translation("John 3:16", name), tl.get_parallel("John 3:16", ["KJV", name]),
                   tl.get_random_verse(name), tl.search_translation("love", name)):
        assert not result["found"] and "isn't available any more" in result["error"]
    assert name.lower() in tl.TRANSLATION_SUFFIXES             # still recognised, so the reply explains
    assert name.lower() not in tl.TRANSLATIONS and "NIV" not in tl.list_translations()


def test_a_withheld_notice_is_never_shown_as_a_verse(monkeypatch):
    notice = [{"pk": 1, "verse": 16, "text": "Biblica, Inc. has prohibited me from using the NIV translation; "
                                             "they have chosen financial profit over the free dissemination"}]

    class Response(io.BytesIO):
        def __enter__(self): return self
        def __exit__(self, *exc): return False
    monkeypatch.setattr(tl.urllib.request, "urlopen", lambda req, timeout=None: Response(json.dumps(notice).encode()))
    tl._chapter_cache.clear()
    assert tl._fetch_chapter("ESV", 43, 3) is None              # whatever translation it turns up in


def test_prefer_niv_is_refused(bot_module, fake_ctx):
    import core
    asyncio.run(bot_module.bot.get_command("prefer").callback(fake_ctx, translation="NIV"))
    assert "isn't available any more" in fake_ctx.sent[-1]["content"]
    assert core._get_preferred_translation(fake_ctx.author.id) is None


def test_an_niv_default_goes_back_to_the_kjv(bot_module, fake_ctx):
    import core
    core._save_user_prefs({str(fake_ctx.author.id): {"translation": "niv"}})
    asyncio.run(bot_module.bot.get_command("verse").callback(fake_ctx, reference="John 3:16"))
    assert "isn't available any more" in fake_ctx.sent[0]["content"] and "KJV" in fake_ctx.sent[0]["content"]
    assert core._get_preferred_translation(fake_ctx.author.id) is None
    assert "only begotten" in fake_ctx.sent[-1]["embed"].description    # and the verse, in the KJV
