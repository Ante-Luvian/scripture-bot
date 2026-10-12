"""Every prefix command, alias, and slash command must stay registered.

Safety net for moving commands out of bot.py into cogs: the registry must
be identical before and after. If a command is added/removed on purpose,
regenerate the snapshot:

    python -c "import tests.test_command_registry as t; t.regenerate()"
"""
import json
from pathlib import Path

SNAPSHOT = Path(__file__).parent / "command_registry.json"


def _current(bot_module) -> dict:
    b = bot_module.bot
    return {
        "prefix": {c.name: sorted(c.aliases) for c in sorted(b.commands, key=lambda c: c.name)},
        "slash": sorted(c.name for c in b.tree.get_commands()),
    }


def test_command_registry_unchanged(bot_module):
    expected = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    current = _current(bot_module)
    assert current["prefix"] == expected["prefix"]
    assert current["slash"] == expected["slash"]


def regenerate():
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    import bot
    SNAPSHOT.write_text(json.dumps(_current(bot), indent=1, ensure_ascii=False), encoding="utf-8")
