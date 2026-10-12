"""The !notes canary: health_check (network stubbed) and the owner DM on failure.
The real network check is in test_live.py (`python -m pytest -m live`)."""
import asyncio

import pytest

import net_notes_lookup as N
from test_net_notes import GENESIS_1_1, NOTES_HTML, _note


# Genesis 1:1-2 has only 5 markers; repeat verse 1 as verses 1-24 so the
# chapter clears health_check's plausibility floor.
CHAPTER = "".join(GENESIS_1_1.replace("_1_1", f"_1_{v}").replace('data-verse="1"', f'data-verse="{v}"')
                  for v in range(1, 25))


def test_health_check_passes_on_consistent_data(monkeypatch):
    monkeypatch.setattr(N, "_fetch_netbible", lambda b, c: (CHAPTER, NOTES_HTML))
    ok, detail = N.health_check()
    assert ok, detail


def test_health_check_fails_when_fetch_fails(monkeypatch):
    monkeypatch.setattr(N, "_fetch_netbible", lambda b, c: None)
    assert N.health_check() == (False, "the request failed or returned something unexpected")


def test_health_check_fails_when_notes_are_missing(monkeypatch):
    only_one_note = _note(1, '<span class="notetype">tn</span>  On beginning.')
    monkeypatch.setattr(N, "_fetch_netbible", lambda b, c: (CHAPTER, only_one_note))
    ok, detail = N.health_check()
    assert not ok and "have no note" in detail


def test_health_check_fails_on_implausibly_little_text(monkeypatch):
    monkeypatch.setattr(N, "_fetch_netbible", lambda b, c: (GENESIS_1_1, NOTES_HTML))
    ok, detail = N.health_check()
    assert not ok and "parsed to only" in detail


# ── the canary task's alert ─────────────────────────────────────────────────

class FakeOwner:
    def __init__(self):
        self.dms = []

    async def send(self, text):
        self.dms.append(text)


class FakeClient:
    def __init__(self, owner):
        self.app = type("App", (), {"owner": owner, "team": None})()

    async def application_info(self):
        return self.app


@pytest.fixture(scope="module")
def health(bot_module):
    from bot_commands import health
    return health


def test_canary_dms_owner_on_failure(health, monkeypatch):
    monkeypatch.setattr(health, "health_check", lambda: (False, "the request failed"))
    owner = FakeOwner()
    assert asyncio.run(health.run_notes_check(FakeClient(owner))) is False
    assert len(owner.dms) == 1 and "the request failed" in owner.dms[0]


def test_canary_quiet_on_success(health, monkeypatch):
    monkeypatch.setattr(health, "health_check", lambda: (True, "John 3: 36 verses, 71 notes"))
    owner = FakeOwner()
    assert asyncio.run(health.run_notes_check(FakeClient(owner))) is True
    assert owner.dms == []
