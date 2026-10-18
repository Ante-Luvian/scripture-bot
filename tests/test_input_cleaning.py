"""What people type is cleaned before any command sees it, and replies are kept within Discord's
limits (core.clean_input, ScriptureTree, fit_for_discord); found by the stress test (stress.py)."""
import asyncio


def test_input_is_cleaned_for_slash_and_typed_commands(bot_module):
    """A backtick or backslash only breaks the reply that quotes it; invisible controls disguise text."""
    import types
    from core import bot, clean_input, fit_for_discord, MAX_INPUT
    assert clean_input("!verse `John\\ 3:16​‮`") == "!verse John 3:16"
    assert len(clean_input("!theme " + "x" * 5000)) <= MAX_INPUT + 40
    data = {"options": [{"name": "query", "value": "`care\\`"}, {"name": "sub", "options": [{"value": "​x"}]}]}
    asyncio.run(bot.tree.interaction_check(types.SimpleNamespace(data=data)))
    assert data["options"][0]["value"] == "care" and data["options"][1]["options"][0]["value"] == "x"
    import discord
    e = discord.Embed(title="t" * 300, description="d" * 5000).add_field(name="f", value="v" * 2000)
    content = fit_for_discord("c" * 3000, {"embed": e})
    assert len(content) == 2000 and len(e.title) == 256 and len(e.description) == 4096 and len(e.fields[0].value) == 1024
    assert bot.allowed_mentions.everyone is False and bot.allowed_mentions.roles is False
