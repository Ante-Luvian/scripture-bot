"""Discord refuses the whole slash-command sync if any fixed list of choices has more than 25 entries (adding
the Shakespeare tradition took /search's tradition list to 26 and the bot failed to start)."""
import bot  # noqa: F401  (registers every command)
from core import bot as client


def test_no_slash_command_has_more_than_25_choices():
    for command in client.tree.walk_commands():
        for param in getattr(command, "parameters", []):
            assert len(param.choices) <= 25, f"/{command.qualified_name} {param.name}: {len(param.choices)} choices"
