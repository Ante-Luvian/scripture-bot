"""Checks against the real external services. Excluded from the normal run
(see pytest.ini); run on demand with:  python -m pytest -m live"""
import pytest

import net_notes_lookup as N


@pytest.mark.live
def test_netbible_notes_endpoints_still_work():
    ok, detail = N.health_check()
    assert ok, detail


@pytest.mark.live
def test_catena_bible_api(bot_module):
    from bot_commands import church
    r = church._fetch_catena_sections("John 3:16")
    assert not r.get("error_send"), r.get("error_send")
    names = [name for name, _ in r["sections"]]
    assert len(names) >= 10 and any("Chrysostom" in n for n in names)
    assert all(len(body) > 50 and "<" not in body for _, body in r["sections"])


@pytest.mark.live
def test_netbible_notes_end_to_end():
    r = N.get_net_notes("Psalm 23:1")
    assert r["found"] and r["source"] == "netbible"
    v = r["verses"][0]
    assert v["segments"] and v["notes"] and v["intro"]
