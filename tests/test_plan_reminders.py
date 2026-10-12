"""Reading-plan reminders by DM (!plan remind)."""
import asyncio
import datetime

import discord
import pytest

from conftest import FakeCtx

TODAY = datetime.date(2026, 10, 12)


@pytest.fixture(scope="module")
def personal(bot_module):
    from bot_commands import personal
    return personal


def _plans():
    import core
    return core._load_reading_plans()


def _start_plan(uid="1", book="John", total=21, started=TODAY, **extra):
    import core
    data = core._load_reading_plans()
    data[uid] = {"book": book, "total_chapters": total, "started_at": started.isoformat(), **extra}
    core._save_reading_plans(data)


def _plan_cmd(personal, action, arg=""):
    ctx = FakeCtx()
    ctx.guild = None
    asyncio.run(personal.cmd_plan.callback(ctx, action=action, arg=arg))
    return ctx.sent[-1]["content"]


def test_remind_on_off_and_time(personal):
    _start_plan()
    assert "Daily DM reminders are off" in _plan_cmd(personal, "remind")
    assert "at 07:00 UTC" in _plan_cmd(personal, "remind", "on")
    assert _plans()["1"]["remind_at"] == "07:00"
    assert "at 19:30 UTC" in _plan_cmd(personal, "remind", "on 19:30")
    assert "Use 24-hour UTC time" in _plan_cmd(personal, "remind", "on 25:00")
    assert _plans()["1"]["remind_at"] == "19:30"
    assert _plan_cmd(personal, "remind", "off") == "Reading-plan reminders are off."
    assert "remind_at" not in _plans()["1"]


class FakeUser:
    def __init__(self, closed=False):
        self.sent, self.closed = [], closed

    async def send(self, content=None, **kw):
        if self.closed:
            raise discord.Forbidden(type("R", (), {"status": 403, "reason": "Forbidden"})(), "DMs closed")
        self.sent.append({"content": content, **kw})


class FakeClient:
    def __init__(self, users):
        self.users = users

    def get_user(self, uid):
        return self.users.get(uid)


def test_reminder_dms_todays_chapter_once(personal):
    _start_plan(started=TODAY - datetime.timedelta(days=3), remind_at="07:00")   # day 4
    user = FakeUser()
    client = FakeClient({1: user})
    assert asyncio.run(personal.run_plan_reminders(client, TODAY, "07:00")) == 1
    assert "Day 4 of 21" in user.sent[0]["content"] and "**John**" in user.sent[0]["content"]
    assert user.sent[1]["embed"].title.startswith("John 4")      # the chapter itself
    assert asyncio.run(personal.run_plan_reminders(client, TODAY, "07:00")) == 0   # once a day
    assert asyncio.run(personal.run_plan_reminders(client, TODAY + datetime.timedelta(days=1), "07:00")) == 1


def test_no_reminder_at_other_times_or_without_opting_in(personal):
    _start_plan(remind_at="07:00")
    _start_plan(uid="2")                                   # no reminders
    client = FakeClient({1: FakeUser(), 2: FakeUser()})
    assert asyncio.run(personal.run_plan_reminders(client, TODAY, "07:01")) == 0
    assert asyncio.run(personal.run_plan_reminders(client, TODAY, "07:00")) == 1
    assert client.users[2].sent == []


def test_no_reminder_after_the_last_chapter(personal):
    _start_plan(total=3, started=TODAY - datetime.timedelta(days=3), remind_at="07:00")   # day 4 of 3
    user = FakeUser()
    assert asyncio.run(personal.run_plan_reminders(FakeClient({1: user}), TODAY, "07:00")) == 0
    assert user.sent == []


def test_closed_dms_dont_crash_or_retry_all_day(personal):
    _start_plan(remind_at="07:00")
    user = FakeUser(closed=True)
    assert asyncio.run(personal.run_plan_reminders(FakeClient({1: user}), TODAY, "07:00")) == 0
    assert _plans()["1"]["last_reminded"] == TODAY.isoformat()
