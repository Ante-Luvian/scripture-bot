"""Checks against the real external services. Excluded from the normal run
(see pytest.ini); run on demand with:  python -m pytest -m live"""
import pytest

import net_notes_lookup as N


@pytest.mark.live
def test_netbible_notes_endpoints_still_work():
    ok, detail = N.health_check()
    assert ok, detail


@pytest.mark.live
def test_netbible_notes_end_to_end():
    r = N.get_net_notes("Psalm 23:1")
    assert r["found"] and r["source"] == "netbible"
    v = r["verses"][0]
    assert v["segments"] and v["notes"] and v["intro"]
