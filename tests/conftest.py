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
