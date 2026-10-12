"""The suite must never write the live bot's runtime files."""
import asyncio

from conftest import RUNTIME_FILES, ROOT


def test_runtime_paths_point_outside_the_project(bot_module):
    import core
    for attr in RUNTIME_FILES:
        if hasattr(core, attr):
            assert ROOT not in getattr(core, attr).parents, attr


def test_running_a_command_leaves_live_stats_untouched(bot_module, fake_ctx, monkeypatch):
    live = ROOT / "data" / "stats.json"
    before = live.read_bytes() if live.exists() else None
    from bot_commands import verse
    monkeypatch.setattr(verse, "_get_preferred_translation", lambda user_id: None)
    asyncio.run(verse.verse_prefix.callback(fake_ctx, reference="John 3:16"))
    assert fake_ctx.sent
    assert (live.read_bytes() if live.exists() else None) == before
