"""INTRODUCTION.md (the welcome posted by !changelogintro) and the command."""
import asyncio
import re

import pytest

from conftest import FakeCtx, ROOT

# Owner/maintenance tools that don't belong in a public introduction
NOT_INTRODUCED = {"guildactivity", "scanstats", "votdmode"}


@pytest.fixture(scope="module")
def cl(bot_module):
    from bot_commands import changelog
    return changelog


@pytest.fixture(scope="module")
def intro_text():
    return (ROOT / "INTRODUCTION.md").read_text(encoding="utf-8")


def test_sections_fit_in_discord(cl, intro_text):
    sections = cl.intro_sections()                 # as posted: without the pack markers
    assert len(sections) >= 8
    for title, body in sections:
        assert title and len(title) <= 256
        assert body and len(body) <= 3800, f"section {title!r} is {len(body)} chars"


def test_every_command_is_introduced(bot_module, intro_text):
    mentioned = set(re.findall(r"!([a-z]+)", intro_text))
    missing = sorted(c.name for c in bot_module.bot.commands
                     if not c.hidden and c.name not in NOT_INTRODUCED and c.name not in mentioned)
    assert not missing, f"commands not explained in INTRODUCTION.md: {missing}"


def test_every_mentioned_command_exists(bot_module, intro_text):
    unknown = sorted({w for w in re.findall(r"`!([a-z]+)", intro_text) if bot_module.bot.get_command(w) is None})
    assert not unknown, f"INTRODUCTION.md mentions commands that don't exist: {unknown}"


# ── posting ─────────────────────────────────────────────────────────────────

class FakeMessage:
    def __init__(self, author_id, channel=None):
        self.author = type("A", (), {"id": author_id})()
        self.deleted = False

    async def delete(self):
        self.deleted = True


class FakeChannel:
    id = 100
    mention = "#updates"

    def __init__(self, history=()):
        self.sent, self._history = [], list(history)

    async def send(self, content=None, **kwargs):
        self.sent.append({"content": content, **kwargs})

    def history(self, limit=100):
        async def gen():
            for m in self._history[:limit]:
                yield m
        return gen()


def test_post_introduction_then_two_latest_updates_oldest_first(cl):
    channel = FakeChannel()
    sections, entries = asyncio.run(cl.post_introduction(channel))
    titles = [m["embed"].title for m in channel.sent]
    assert sections == len(cl.parse_sections((ROOT / "INTRODUCTION.md").read_text(encoding="utf-8")))
    assert titles[0] == "👋 Hello! I'm ScriptureBot"
    latest = cl.load_changelog()[:2]
    assert entries == 2
    assert titles[-2:] == [f"📜 What's new — {latest[1]['title']}", f"📜 What's new — {latest[0]['title']}"]


class FakeBot:
    user = type("U", (), {"id": 999})()

    def __init__(self, channel):
        self.channel = channel

    def get_channel(self, cid):
        return self.channel if cid == self.channel.id else None


def _admin_ctx(in_channel=None):
    ctx = FakeCtx()
    ctx.guild = type("G", (), {"id": 1})()
    ctx.channel = in_channel or type("C", (), {"id": 555})()
    ctx.message = FakeMessage(1)
    return ctx


def test_fresh_deletes_only_my_own_messages(cl, monkeypatch):
    import core
    core._update_guild_config(1, changelog_channel_id=100)
    mine, theirs = FakeMessage(999), FakeMessage(42)
    channel = FakeChannel(history=[mine, theirs])
    monkeypatch.setattr(cl, "bot", FakeBot(channel))
    ctx = _admin_ctx()
    asyncio.run(cl.cmd_changelogintro.callback(ctx, arg="fresh"))
    assert mine.deleted and not theirs.deleted
    assert channel.sent and "after removing 1 of my earlier messages" in ctx.sent[-1]["content"]


def test_run_inside_the_channel_removes_the_command_message(cl, monkeypatch):
    import core
    core._update_guild_config(1, changelog_channel_id=100)
    channel = FakeChannel()
    monkeypatch.setattr(cl, "bot", FakeBot(channel))
    ctx = _admin_ctx(in_channel=channel)
    asyncio.run(cl.cmd_changelogintro.callback(ctx, arg=""))
    assert ctx.message.deleted                       # so the introduction is first
    assert channel.sent[0]["embed"].title == "👋 Hello! I'm ScriptureBot"
    assert ctx.sent == []                            # no extra confirmation in the channel itself


# ── keeping a posted introduction up to date ────────────────────────────────

class EditableChannel:
    """Channel whose sent messages can later be edited/deleted by id."""
    id = 100

    def __init__(self):
        self.messages, self.next_id = {}, 1

    async def send(self, content=None, embed=None, **kw):
        mid = self.next_id
        self.next_id += 1
        self.messages[mid] = embed
        return type("Msg", (), {"id": mid})()

    def get_partial_message(self, mid):
        channel = self

        class Partial:
            async def edit(self, embed=None):
                channel.messages[mid] = embed

            async def delete(self):
                del channel.messages[mid]
        return Partial()


def _intro(*sections):
    return "# note\n\n" + "\n\n".join(f"## {t}\n{b}" for t, b in sections)


@pytest.fixture
def tmp_intro(cl, tmp_path, monkeypatch):
    path = tmp_path / "INTRODUCTION.md"
    monkeypatch.setattr(cl, "INTRO_PATH", path)
    return path


class Client:
    def __init__(self, channel, dms):
        self.channel, self.dms = channel, dms

    def get_channel(self, cid):
        return self.channel if cid == self.channel.id else None

    async def application_info(self):
        dms = self.dms

        class Owner:
            async def send(self, text):
                dms.append(text)
        return type("App", (), {"owner": Owner(), "team": None})()


def _intro_titles(channel, n):
    return [channel.messages[i].title for i in range(1, n + 1) if i in channel.messages]


def test_posted_introduction_is_edited_in_place_when_it_changes(cl, tmp_intro):
    import core
    tmp_intro.write_text(_intro(("Hello", "v1"), ("Library", "v1")), encoding="utf-8")
    channel, dms = EditableChannel(), []
    asyncio.run(cl.post_introduction(channel, guild_id=1))
    record = core._load_guild_config()["1"]["changelog_intro"]
    assert record["message_ids"] == [1, 2] and record["channel_id"] == 100

    assert asyncio.run(cl.refresh_introductions(Client(channel, dms))) == 0     # unchanged: nothing to do

    tmp_intro.write_text(_intro(("Hello", "v2"), ("Library", "v2")), encoding="utf-8")
    assert asyncio.run(cl.refresh_introductions(Client(channel, dms))) == 1
    assert [channel.messages[i].description for i in (1, 2)] == ["v2", "v2"]
    assert channel.next_id == 3 + 2        # no new messages beyond the 2 updates posted after it
    assert asyncio.run(cl.refresh_introductions(Client(channel, dms))) == 0     # and only once
    assert dms == []


def test_shrunk_introduction_deletes_the_extra_message(cl, tmp_intro):
    tmp_intro.write_text(_intro(("A", "1"), ("B", "1"), ("C", "1")), encoding="utf-8")
    channel = EditableChannel()
    asyncio.run(cl.post_introduction(channel, guild_id=1))
    tmp_intro.write_text(_intro(("A", "2"), ("B", "2")), encoding="utf-8")
    asyncio.run(cl.refresh_introductions(Client(channel, [])))
    assert 3 not in channel.messages and _intro_titles(channel, 3) == ["A", "B"]


def test_grown_introduction_updates_what_fits_and_tells_the_owner(cl, tmp_intro):
    tmp_intro.write_text(_intro(("A", "1")), encoding="utf-8")
    channel, dms = EditableChannel(), []
    asyncio.run(cl.post_introduction(channel, guild_id=1))
    tmp_intro.write_text(_intro(("A", "2"), ("B", "new")), encoding="utf-8")
    asyncio.run(cl.refresh_introductions(Client(channel, dms)))
    assert channel.messages[1].description == "2"
    assert dms and "!changelogintro fresh" in dms[0]


def test_needs_an_updates_channel(cl, monkeypatch):
    monkeypatch.setattr(cl, "bot", FakeBot(FakeChannel()))
    ctx = _admin_ctx()
    asyncio.run(cl.cmd_changelogintro.callback(ctx, arg=""))
    assert "!changelogsetup #channel" in ctx.sent[-1]["content"]
