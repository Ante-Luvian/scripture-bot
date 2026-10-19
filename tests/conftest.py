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


# Chant audio rendered on the bot's machine and not kept in git (data/hymns/audio/more/ by
# scripts/build_chant.py, sung/ by scripts/build_sung_chant.py): a fresh clone hasn't got it, and
# the tests that need it skip their audio checks there.
def _rendered(folder: str) -> bool:
    path = Path(__file__).resolve().parent.parent / "data" / "hymns" / "audio" / folder
    return path.is_dir() and any(path.glob("*.ogg"))


HAVE_ORGAN_CHANT = _rendered("more")
HAVE_SUNG_CHANT = _rendered("sung")
needs_sung_chant = pytest.mark.skipif(not HAVE_SUNG_CHANT, reason="sung chant not rendered here "
                                                                  "(python scripts/build_sung_chant.py)")
needs_organ_chant = pytest.mark.skipif(not HAVE_ORGAN_CHANT, reason="chant audio not rendered here "
                                                                    "(python scripts/build_chant.py)")


@pytest.fixture(scope="session")
def lookup(bot_module):
    return bot_module.lookup


# Files the running bot writes. Tests that drive real commands must never
# touch the live copies (an earlier version of this suite added a fake user
# and fake John 3:16 lookups to data/stats.json on every run).
RUNTIME_FILES = ["VOTD_MODE_PATH", "STATS_PATH", "GUILD_ACTIVITY_PATH", "GUILD_CONFIG_PATH",
                 "USER_PREFS_PATH", "BOOKMARKS_PATH", "READING_PLANS_PATH", "SUBSCRIBERS_PATH",
                 "ERROR_LOG_PATH", "REPORT_STATE_PATH", "QUIZ_SCORES_PATH", "DAILY_QUIZ_PATH",
                 "MEMORIZE_PATH", "VERSLE_PATH", "HYMNDAY_PATH", "SAINTDAY_PATH", "ANGELUS_PATH", "TROPARION_PATH",
                 "DELUGE_PATH", "LEARNING_PATH"]


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


@pytest.fixture(autouse=True)
def offline_sefaria_names(request, monkeypatch):
    """An unknown book asks Sefaria whether it's in their library, and the Quran comes from
    the Quran API; offline tests get "no" and our own Pickthall."""
    if request.node.get_closest_marker("live") is None:
        import quran_lookup
        import sefaria_lookup
        monkeypatch.setattr(sefaria_lookup, "sefaria_name", lambda query: None)
        monkeypatch.setattr(quran_lookup, "fetch_surah", lambda edition, surah: None)


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
