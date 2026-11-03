"""`!<command> random` for every command where it makes sense, and the lookups sent bare give a random one (the
owner's rule, 2026-11-02, from bug-testers: `!verse random` said "Unknown book: random", bare `!concordance` "No
Strong's entry matches ****")."""
import asyncio
import re

import pytest

# what a command says when it didn't understand what it was given
NOT_UNDERSTOOD = re.compile(r"not found|couldn't|could not|don't know|don't have|no \w+ (?:called|matches|found)|"
                            r"Usage:|isn't a|Unknown|Which \w+\?|Give a date|I found no", re.IGNORECASE)


@pytest.fixture(scope="module")
def core(bot_module):
    import core
    return core


def test_every_random_input_is_a_command(core, bot_module):
    for name in core.RANDOM_INPUTS:
        assert bot_module.bot.get_command(name), name


def test_every_picker_picks(core, fake_ctx):
    for name, (picker, bare, hint) in core.RANDOM_INPUTS.items():
        command = core.bot.get_command(name)
        for _ in range(3):
            value, _ = core.randomized(command, "random", fake_ctx)
            assert value is not None, name
        if bare:
            assert hint and core.randomized(command, "", fake_ctx)[1], name      # (bare: random, and says so)
        else:
            assert core.randomized(command, "", fake_ctx)[0] is None, name        # (bare: as before)


def test_a_typed_word_is_left_alone(core):
    who = core.bot.get_command("who")
    assert core.randomized(who, "Ruth")[0] is None and core.randomized(who, "Random")[0] is not None


def test_a_slash_command_typed_random(core, fake_ctx):
    """Slash commands call the command straight (`await cmd_who(ctx, name=...)`), past the hooks: same result."""
    who = core.bot.get_command("who")
    asyncio.run(who(fake_ctx, **{core._text_param(who): "random"}))
    sent = fake_ctx.sent[0]
    assert sent.get("embed") is not None and "random" not in str(sent.get("content") or "").lower()


@pytest.mark.stress
def test_random_is_understood_by_every_command(core, bot_module):
    import stress
    from core import bot
    bot.wait_for = stress._no_answer
    failures = []
    for name in sorted(core.RANDOM_INPUTS):
        if name in stress.NETWORK:
            continue
        for arg in ("random", ""):
            channel = stress.Recorder()
            found = asyncio.run(stress.run(name, arg, channel))
            first = channel.sent[0] if channel.sent else {}
            text = (first.get("content") or "") + " " + (getattr(first.get("embed"), "title", "") or "")
            if found or not channel.sent or (arg == "random" and NOT_UNDERSTOOD.search(text)):
                failures.append(f"!{name} {arg!r}: {found or text[:120]!r}")
    assert not failures, "\n".join(failures)
