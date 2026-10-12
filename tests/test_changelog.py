"""Changelog: CHANGELOG.md format, announcing unseen entries per server, and
the !changelog / !changelogsetup commands."""
import asyncio

import discord
import pytest

from conftest import FakeCtx, ROOT


@pytest.fixture(scope="module")
def cl(bot_module):
    from bot_commands import changelog
    return changelog


# ── the real CHANGELOG.md ───────────────────────────────────────────────────

def test_real_changelog_is_well_formed(cl):
    entries = cl.parse_changelog((ROOT / "CHANGELOG.md").read_text(encoding="utf-8"))
    assert entries, "CHANGELOG.md has no '## ' entries"
    ids = [e["id"] for e in entries]
    assert len(ids) == len(set(ids)), "duplicate headings -- the bot uses them to remember what it posted"
    for e in entries:
        assert e["date"], f"entry needs a 'YYYY-MM-DD · Title' heading: {e['id']!r}"
        assert e["items"], f"entry has no '- ' bullets: {e['id']!r}"
        assert len(cl.entry_embed(e).description) <= 4096
    dates = [e["date"] for e in entries]
    assert dates == sorted(dates, reverse=True), "newest entries go first"


# ── parsing and selection ───────────────────────────────────────────────────

SAMPLE = """# Changelog
Intro mentioning `## YYYY-MM-DD · Title` inline is fine.

## 2026-10-12 · Newest
- One
- Two, which wraps
  onto a second line

## 2026-10-11 · Middle
- Three

## 2026-10-10 · Oldest
- Four
"""


def test_parse(cl):
    entries = cl.parse_changelog(SAMPLE)
    assert [e["title"] for e in entries] == ["Newest", "Middle", "Oldest"]
    assert entries[0] == {"id": "2026-10-12 · Newest", "date": "2026-10-12", "title": "Newest",
                          "items": ["One", "Two, which wraps onto a second line"]}


def test_pending_is_oldest_first_and_capped(cl, monkeypatch):
    entries = cl.parse_changelog(SAMPLE)
    assert [e["title"] for e in cl.pending_entries(entries, [])] == ["Oldest", "Middle", "Newest"]
    assert [e["title"] for e in cl.pending_entries(entries, ["2026-10-11 · Middle"])] == ["Oldest", "Newest"]
    monkeypatch.setattr(cl, "MAX_PER_STARTUP", 2)
    assert [e["title"] for e in cl.pending_entries(entries, [])] == ["Middle", "Newest"]


# ── announcing ──────────────────────────────────────────────────────────────

class FakeChannel:
    def __init__(self, fail=False):
        self.sent, self.fail = [], fail
        self.mention = "#updates"

    async def send(self, content=None, **kw):
        if self.fail:
            raise discord.Forbidden(type("R", (), {"status": 403, "reason": "Forbidden"})(), "no access")
        self.sent.append({"content": content, **kw})


class FakeClient:
    def __init__(self, channels):
        self.channels = channels

    def get_channel(self, channel_id):
        return self.channels.get(channel_id)


@pytest.fixture
def sample_changelog(cl, tmp_path, monkeypatch):
    path = tmp_path / "CHANGELOG.md"
    path.write_text(SAMPLE, encoding="utf-8")
    monkeypatch.setattr(cl, "CHANGELOG_PATH", path)


def _guild(gid):
    import core
    return core._load_guild_config().get(str(gid), {})


def test_announce_posts_unseen_then_nothing(cl, sample_changelog):
    import core
    core._update_guild_config(1, changelog_channel_id=100, changelog_seen=["2026-10-10 · Oldest"])
    core._update_guild_config(2, votd_channel_id=200)            # no changelog channel: skipped
    channel = FakeChannel()
    client = FakeClient({100: channel})

    assert asyncio.run(cl.announce_changelog(client)) == 2
    assert [m["embed"].title for m in channel.sent] == ["📜 What's new — Middle", "📜 What's new — Newest"]
    assert set(_guild(1)["changelog_seen"]) == {"2026-10-12 · Newest", "2026-10-11 · Middle", "2026-10-10 · Oldest"}
    assert "changelog_seen" not in _guild(2)

    assert asyncio.run(cl.announce_changelog(client)) == 0      # nothing twice


def test_announce_retries_when_posting_fails(cl, sample_changelog):
    import core
    core._update_guild_config(1, changelog_channel_id=100)
    assert asyncio.run(cl.announce_changelog(FakeClient({100: FakeChannel(fail=True)}))) == 0
    assert not _guild(1).get("changelog_seen")                 # not marked seen: retried next startup


def test_announce_skips_missing_channel(cl, sample_changelog):
    import core
    core._update_guild_config(1, changelog_channel_id=999)
    assert asyncio.run(cl.announce_changelog(FakeClient({}))) == 0


# ── commands ────────────────────────────────────────────────────────────────

def _admin_ctx(mentions=()):
    ctx = FakeCtx()
    ctx.guild = type("G", (), {"id": 1, "name": "Test"})()
    ctx.message = type("M", (), {"channel_mentions": list(mentions)})()
    return ctx


def test_setup_posts_only_the_latest_and_marks_all_seen(cl, sample_changelog):
    channel = FakeChannel()
    channel.id = 100
    ctx = _admin_ctx([channel])
    asyncio.run(cl.cmd_changelogsetup.callback(ctx, arg="#updates"))
    assert _guild(1)["changelog_channel_id"] == 100
    assert len(_guild(1)["changelog_seen"]) == 3
    assert len(channel.sent) == 1 and channel.sent[0]["embed"].title == "📜 What's new — Newest"
    assert "will be posted in #updates" in ctx.sent[-1]["content"]


def test_setup_reports_missing_permissions(cl, sample_changelog):
    channel = FakeChannel(fail=True)
    channel.id = 100
    ctx = _admin_ctx([channel])
    asyncio.run(cl.cmd_changelogsetup.callback(ctx, arg="#updates"))
    assert "can't post in" in ctx.sent[-1]["content"]


def test_setup_off_and_status(cl, sample_changelog):
    import core
    core._update_guild_config(1, changelog_channel_id=100)
    ctx = _admin_ctx()
    asyncio.run(cl.cmd_changelogsetup.callback(ctx, arg=""))
    assert "<#100>" in ctx.sent[-1]["content"]
    asyncio.run(cl.cmd_changelogsetup.callback(ctx, arg="off"))
    assert _guild(1)["changelog_channel_id"] is None


def test_changelog_command(cl, sample_changelog, fake_ctx):
    asyncio.run(cl.cmd_changelog.callback(fake_ctx))
    embed = fake_ctx.sent[0]["embed"]
    assert [f.name for f in embed.fields] == ["Newest (2026-10-12)", "Middle (2026-10-11)", "Oldest (2026-10-10)"]
    assert embed.fields[0].value == "• One\n• Two, which wraps onto a second line"
