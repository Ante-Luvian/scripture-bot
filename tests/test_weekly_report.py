"""The owner's weekly report."""
import asyncio
import datetime
import json

import pytest

UTC = datetime.timezone.utc
MONDAY_9 = datetime.datetime(2026, 10, 12, 9, 5, tzinfo=UTC)     # 2026-10-12 is a Monday


@pytest.fixture(scope="module")
def report(bot_module):
    from bot_commands import report
    return report


@pytest.fixture(autouse=True)
def offline_notes_check(report, monkeypatch):
    monkeypatch.setattr(report, "health_check", lambda: (True, "John 3: 36 verses, 71 notes"))


STATS_BEFORE = {"total_commands": 100, "unique_users": ["a", "b"],
                "command_counts": {"verse": 50, "virgil": 30}, "verse_counts": {"John 3:16": 5}}
STATS_NOW = {"total_commands": 160, "unique_users": ["a", "b", "c"],
             "command_counts": {"verse": 70, "virgil": 65, "notes": 5}, "verse_counts": {"John 3:16": 9, "Psalms 23:1": 2}}


def _field(embed, name):
    return next(f.value for f in embed.fields if f.name == name)


def test_report_shows_this_weeks_difference(report):
    since = MONDAY_9 - datetime.timedelta(days=7)
    errors = [{"at": (MONDAY_9 - datetime.timedelta(days=1)).isoformat(timespec="seconds"), "where": "!xref", "error": "KeyError"},
              {"at": (MONDAY_9 - datetime.timedelta(days=1)).isoformat(timespec="seconds"), "where": "!xref", "error": "KeyError"},
              {"at": (MONDAY_9 - datetime.timedelta(days=30)).isoformat(timespec="seconds"), "where": "!old", "error": "X"}]
    embed = report.build_report(STATS_NOW, report._snapshot(STATS_BEFORE), errors, since, 9, (True, "fine"))
    assert _field(embed, "Usage") == "**60** commands · **1** new users · 9 servers"
    assert _field(embed, "Top commands") == "1. virgil — 35\n2. verse — 20\n3. notes — 5"
    assert _field(embed, "Top verses") == "1. John 3:16 — 4\n2. Psalms 23:1 — 2"
    assert _field(embed, "Errors") == "**2** — !xref ×2"          # last week's only
    assert _field(embed, "!notes source (netbible.org)") == "✅ fine"


def test_first_report_says_so_and_no_errors_is_celebrated(report):
    embed = report.build_report(STATS_NOW, None, [], MONDAY_9, 1, (False, "request failed"))
    assert "first one" in embed.title
    assert _field(embed, "Errors") == "None 🎉"
    assert _field(embed, "!notes source (netbible.org)") == "⚠️ request failed"


class FakeClient:
    guilds = [1, 2]

    def __init__(self):
        self.dms = []

    async def application_info(self):
        dms = self.dms

        class Owner:
            async def send(self, **kw):
                dms.append(kw["embed"])
        return type("App", (), {"owner": Owner(), "team": None})()


def test_sent_monday_morning_once_then_snapshot_moves(report):
    import core
    core._save_stats(STATS_NOW)
    client = FakeClient()
    assert not asyncio.run(report.send_weekly_report_if_due(client, MONDAY_9.replace(hour=8)))   # too early
    assert not asyncio.run(report.send_weekly_report_if_due(client, MONDAY_9 + datetime.timedelta(days=1)))  # Tuesday
    assert asyncio.run(report.send_weekly_report_if_due(client, MONDAY_9))
    assert not asyncio.run(report.send_weekly_report_if_due(client, MONDAY_9.replace(hour=15)))  # e.g. after a restart
    assert len(client.dms) == 1
    state = json.loads(report.REPORT_STATE_PATH.read_text(encoding="utf-8"))
    assert state["snapshot"]["total_commands"] == 160 and state["sent_at"].startswith("2026-10-12")


def test_errors_are_logged_for_the_report(bot_module, monkeypatch):
    import core
    monkeypatch.setattr(core, "_last_error_dm", {})

    async def no_dm():
        raise RuntimeError("offline")
    monkeypatch.setattr(core.bot, "application_info", no_dm)
    asyncio.run(core.report_error("!xref", KeyError("x")))
    logged = json.loads(core.ERROR_LOG_PATH.read_text(encoding="utf-8"))
    assert logged[-1]["where"] == "!xref" and logged[-1]["error"] == "KeyError"


def test_preview_command_is_owner_only_and_doesnt_reset_the_week(report, bot_module, fake_ctx):
    cmd = bot_module.bot.get_command("weeklyreport")
    assert cmd.hidden and cmd.checks                  # is_owner
    asyncio.run(cmd.callback(fake_ctx))
    assert fake_ctx.sent[0]["embed"].title.startswith("📊 Weekly report")
    assert not report.REPORT_STATE_PATH.exists()
