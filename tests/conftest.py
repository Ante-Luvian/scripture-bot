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
