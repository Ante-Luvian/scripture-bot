import asyncio

import pytest


@pytest.mark.parametrize("topic", ["", "texts", "islamic", "jewish", "buddhist", "gita", "sikh", "parsha", "quran translations"])
def test_help_pages_fit_in_a_message(bot_module, fake_ctx, topic):
    """Discord refuses an embed over 6,000 characters (or a field over 1,024)."""
    asyncio.run(bot_module.bot.get_command("help").callback(fake_ctx, topic=topic))
    for sent in fake_ctx.sent:
        embed = sent.get("embed")
        if embed:
            assert len(embed) <= 6000 and all(len(f.value) <= 1024 for f in embed.fields), (topic, len(embed))
