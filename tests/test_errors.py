"""Unexpected errors: the user is told, the owner gets a (throttled) DM."""
import asyncio

import discord
import pytest
from discord.ext import commands

from conftest import FakeCtx


@pytest.fixture
def core(bot_module, monkeypatch):
    import core
    monkeypatch.setattr(core, "_last_error_dm", {})
    return core


@pytest.fixture
def owner_dms(core, monkeypatch):
    dms = []

    class Owner:
        async def send(self, text):
            dms.append(text)

    async def application_info():
        return type("App", (), {"owner": Owner(), "team": None})()

    monkeypatch.setattr(core.bot, "application_info", application_info)
    return dms


def _raised(exc):
    """An exception with a real traceback."""
    try:
        raise exc
    except Exception as e:
        return e


# ── report_error ────────────────────────────────────────────────────────────

def test_report_error_dms_owner_once_per_6_hours(core, owner_dms):
    err = _raised(ValueError("boom"))
    asyncio.run(core.report_error("!xref", err))
    asyncio.run(core.report_error("!xref", err))          # same error again: muted
    assert len(owner_dms) == 1
    assert "Error in !xref" in owner_dms[0] and "ValueError: boom" in owner_dms[0]
    assert "test_errors.py:" in owner_dms[0]              # where it happened

    asyncio.run(core.report_error("!notes", err))         # a different place: reported
    assert len(owner_dms) == 2


def test_report_error_survives_failed_dm(core, monkeypatch):
    async def broken():
        raise RuntimeError("no DMs")
    monkeypatch.setattr(core.bot, "application_info", broken)
    asyncio.run(core.report_error("!xref", _raised(ValueError("x"))))   # must not raise


# ── prefix commands ─────────────────────────────────────────────────────────

def _ctx():
    ctx = FakeCtx()
    ctx.command = type("C", (), {"name": "xref", "qualified_name": "xref"})()
    ctx.invoked_with = "xref"
    return ctx


def test_command_bug_tells_user_and_owner(core, owner_dms):
    ctx = _ctx()
    error = commands.CommandInvokeError(_raised(KeyError("chapter")))
    asyncio.run(core.on_command_error(ctx, error))
    assert ctx.sent[-1]["content"] == core.USER_ERROR_MESSAGE
    assert "Error in !xref" in owner_dms[0] and "KeyError" in owner_dms[0]


def test_missing_permissions_explained_not_reported(core, owner_dms):
    ctx = _ctx()
    asyncio.run(core.on_command_error(ctx, commands.MissingPermissions(["administrator"])))
    assert "Only server admins" in ctx.sent[-1]["content"]
    assert owner_dms == []


def test_bad_input_explained_not_reported(core, owner_dms):
    ctx = _ctx()
    asyncio.run(core.on_command_error(ctx, commands.BadArgument("That isn't a number")))
    assert ctx.sent[-1]["content"] == "⚠️ That isn't a number — see `!help xref`."
    assert owner_dms == []


# ── buttons (through discord.py's real error route) and slash commands ─────

class FakeResponse:
    def __init__(self, done=False):
        self.done, self.sent = done, []

    def is_done(self):
        return self.done

    async def send_message(self, text, ephemeral=False):
        self.sent.append((text, ephemeral))

    async def edit_message(self, view=None):
        self.done = True


class FakeFollowup:
    def __init__(self):
        self.sent = []

    async def send(self, text, ephemeral=False):
        self.sent.append((text, ephemeral))


def _interaction(done=False):
    return type("I", (), {"response": FakeResponse(done), "followup": FakeFollowup(), "command": None,
                          "data": {"custom_id": "x", "component_type": 2}})()


def test_every_view_uses_the_reporting_handler(core):
    assert discord.ui.View.on_error is core._view_on_error


def test_failing_button_tells_user_and_owner(core, owner_dms):
    async def broken(interaction):
        raise ZeroDivisionError("oops")

    view = discord.ui.View()
    button = discord.ui.Button(label="Card", custom_id="t")
    button.callback = broken
    view.add_item(button)
    interaction = _interaction()
    asyncio.run(view._scheduled_task(button, interaction))      # how discord.py runs a press
    assert interaction.response.sent == [(core.USER_ERROR_MESSAGE, True)]   # only they see it
    assert "Error in the “Card” button" in owner_dms[0] and "ZeroDivisionError" in owner_dms[0]


def test_failing_persistent_study_button_is_reported(core, owner_dms, monkeypatch):
    from bot_commands import verse

    async def broken_xref(ctx, reference=""):
        raise LookupError("no such verse")

    monkeypatch.setitem(verse._STUDY_ACTIONS, "xref", ("Cross-refs", "🔗", broken_xref))
    item = verse.StudyButton("xref", "John 3:16")
    view = discord.ui.View(timeout=None)
    view.add_item(item)
    interaction = _interaction()
    interaction.message = type("M", (), {"components": [type("R", (), {"children": [item.item]})()]})()
    interaction.channel = None
    interaction.user = interaction.guild = None
    asyncio.run(view._scheduled_task(item, interaction))
    # the button press was answered (edit), so the apology goes as a followup
    assert interaction.followup.sent == [(core.USER_ERROR_MESSAGE, True)]
    assert "Cross-refs" in owner_dms[0] and "LookupError" in owner_dms[0]


def test_failing_slash_command_tells_user_and_owner(core, owner_dms):
    interaction = _interaction(done=True)                       # slash wrappers defer first
    asyncio.run(core.on_app_command_error(interaction, _raised(IndexError("x"))))
    assert interaction.followup.sent == [(core.USER_ERROR_MESSAGE, True)]
    assert "Error in /?" in owner_dms[0]
