"""!kings: every reign length and verdict is quoted from the KJV, and checked here against the local text."""
import asyncio

import pytest


@pytest.fixture(scope="module")
def kings(bot_module):
    from bot_commands import kings
    return kings


def _kjv(lookup, ref):
    result = lookup.get_verse(ref)
    assert result.get("found"), ref
    return result["text"]


def test_every_quotation_is_in_its_verse(kings, lookup):
    for name, _, _, _, (ref, words), verdicts, verdict, _ in kings.KINGS:
        assert words in _kjv(lookup, ref), (name, ref, words)
        for vref, vwords in verdicts:
            assert vwords in _kjv(lookup, vref), (name, vref, vwords)
        assert (verdict is None) == (not verdicts), name


def test_verdicts_match_their_words(kings):
    for name, _, _, _, _, verdicts, verdict, _ in kings.KINGS:
        said = " ".join(w for _, w in verdicts).lower()
        if verdict == "right":
            assert "right" in said and "not that which was right" not in said, name
        elif verdict == "evil":
            assert any(w in said for w in ("evil", "sin", "rejected", "not that which was right")), name
        elif verdict == "mixed":
            assert len(verdicts) == 2, name


def test_the_list(kings):
    by = {k: [x[0] for x in kings.KINGS if x[2] == k] for k in kings.KINGDOMS}
    assert by["united"] == ["Saul", "David", "Solomon"]
    assert len(by["israel"]) == 19 and by["israel"][0] == "Jeroboam" and by["israel"][-1] == "Hoshea"
    assert len(by["judah"]) == 20 and by["judah"][0] == "Rehoboam" and by["judah"][-1] == "Zedekiah"
    assert kings.length_text(7 / 365) == "7 days" and kings.length_text(0.25) == "3 months"


def test_finding_kings(kings):
    assert [k[0] for k in kings.find_king("Uzziah")] == ["Azariah"]
    assert [k[0] for k in kings.find_king("Jehoram")] == ["Jehoram of Israel", "Jehoram of Judah"]     # two kings
    assert [k[0] for k in kings.find_king("king hezekiah")] == ["Hezekiah"]
    assert kings.find_king("Nebuchadnezzar") == []


def test_command(kings, fake_ctx):
    asyncio.run(kings.send_kings(fake_ctx))
    sent = fake_ctx.sent[-1]
    assert sent["embed"].title == "👑 The Kings of Israel and Judah" and sent["file"].filename == "kings.png"
    asyncio.run(kings.send_kings(fake_ctx, "Josiah"))
    embed = fake_ctx.sent[-1]["embed"]
    assert embed.title == "👑 Josiah" and "31 years" in embed.description
