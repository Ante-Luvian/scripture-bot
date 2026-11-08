"""Every command is counted once, typed or slash (2026-11-08: !stats used to count only the commands
that called record_stat / record_special_stat, and no slash command at all)."""
import asyncio
import types


def _user(uid=5):
    return types.SimpleNamespace(id=uid, __str__=lambda self: "someone")


def test_a_command_with_no_stats_call_of_its_own_is_counted(bot_module):
    import core
    guild = types.SimpleNamespace(id=1, name="Guild")
    core.count_command("hymn", _user(), guild)
    core.count_command("hymn", _user(6), None)          # (in a DM: in !stats, not the per-server log)
    stats = core._load_stats()
    assert stats["command_counts"]["hymn"] == 2 and stats["total_commands"] == 2
    assert set(stats["unique_users"]) == {"5", "6"}
    assert core._load_guild_activity()["1"]["commands"]["hymn"] == 1


def test_record_stat_no_longer_counts_the_command_again(bot_module):
    import core
    core.record_stat(5, "verse", {"found": True, "reference": "John 3:16", "book": "John"})
    core.record_special_stat(5, "ccc", "CCC 1")
    stats = core._load_stats()
    assert stats.get("total_commands", 0) == 0 and not stats.get("command_counts")
    assert stats["verse_counts"]["John 3:16"] == 1 and stats["special_counts"]["ccc"]["CCC 1"] == 1


def test_slash_commands_are_counted_under_their_prefix_name(bot_module):
    import core
    tree = bot_module.bot.tree
    interaction = types.SimpleNamespace(user=_user(), guild=None, channel="#c")
    asyncio.run(core.on_app_command_completion(interaction, tree.get_command("bcp")))
    asyncio.run(core.on_app_command_completion(interaction, tree.get_command("setup").get_command("votd")))
    counts = core._load_stats()["command_counts"]
    assert counts == {"bcp": 1, "votdsetup": 1}
