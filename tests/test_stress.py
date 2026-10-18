"""Every command fed hostile input (stress.py): no crash, no apology, no leaked markup, within
Discord's limits. Slow (a few minutes), so it's its own mark: python -m pytest -m stress"""
import asyncio

import pytest

pytestmark = pytest.mark.stress


@pytest.fixture(scope="module")
def harness(bot_module):
    import stress
    from core import bot
    bot.wait_for = stress._no_answer
    return stress


def _commands():
    import logging
    logging.disable(logging.WARNING)
    import bot  # noqa: F401  (registers the commands)
    import stress
    return [c.name for c in stress.text_commands() if c.name not in stress.NETWORK]


@pytest.mark.parametrize("name", _commands())
def test_command_survives_hostile_input(harness, name):
    from core import bot
    command = bot.all_commands[name]
    failures = []
    for arg in harness.sample(command):
        found = asyncio.run(harness.run(name, arg, harness.Recorder()))
        if found:
            failures.append(f"!{name} {arg[:50]!r}: {found}")
    assert not failures, "\n".join(failures)
