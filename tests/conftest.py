import logging
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# discord.py warns about optional voice deps on import; not relevant here.
logging.getLogger("discord").setLevel(logging.ERROR)


@pytest.fixture(scope="session")
def bot_module():
    """bot.py, imported once. Importing does not connect to Discord (that only
    happens under __main__), but it does build the full ScriptureLookup."""
    import bot
    return bot


@pytest.fixture(scope="session")
def lookup(bot_module):
    return bot_module.lookup


# Files the running bot writes. Tests that drive real commands must never
# touch the live copies (an earlier version of this suite added a fake user
# and fake John 3:16 lookups to data/stats.json on every run).
RUNTIME_FILES = ["VOTD_MODE_PATH", "STATS_PATH", "GUILD_ACTIVITY_PATH", "GUILD_CONFIG_PATH",
                 "USER_PREFS_PATH", "BOOKMARKS_PATH", "READING_PLANS_PATH", "SUBSCRIBERS_PATH",
                 "ERROR_LOG_PATH", "REPORT_STATE_PATH", "QUIZ_SCORES_PATH", "DAILY_QUIZ_PATH",
                 "MEMORIZE_PATH", "VERSLE_PATH", "HYMNDAY_PATH"]


@pytest.fixture(autouse=True)
def isolate_runtime_files(tmp_path, monkeypatch):
    """Point every runtime-state path, in every module that holds one, at a
    temporary folder for the duration of each test."""
    for name, module in list(sys.modules.items()):
        if not (name in ("core", "bot") or name.startswith("bot_commands.")):
            continue
        for attr in RUNTIME_FILES:
            if hasattr(module, attr):
                monkeypatch.setattr(module, attr, tmp_path / attr.lower().replace("_path", ".json"))
        if hasattr(module, "BACKUP_DIR"):
            monkeypatch.setattr(module, "BACKUP_DIR", tmp_path / "backups")


class FakeCtx:
    """Just enough of commands.Context to drive a prefix command directly:
    records everything sent; typing() is a no-op."""

    def __init__(self):
        self.sent = []
        self.author = type("Author", (), {"id": 1, "__str__": lambda self: "tester"})()

    async def send(self, content=None, **kwargs):
        self.sent.append({"content": content, **kwargs})

    def typing(self):
        class _Typing:
            async def __aenter__(self): return self
            async def __aexit__(self, *exc): return False
        return _Typing()


@pytest.fixture
def fake_ctx():
    return FakeCtx()
