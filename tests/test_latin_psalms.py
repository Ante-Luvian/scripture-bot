"""!psalm 110 chant: the psalms chanted in Latin to the psalm tones."""
import asyncio
import sys

import pytest

from core import ROOT


@pytest.fixture(scope="module")
def lp(bot_module):
    from bot_commands import latin_psalms
    return latin_psalms


@pytest.fixture(scope="module")
def sp():
    sys.path.insert(0, str(ROOT / "scripts"))
    import sung_psalms
    return sung_psalms


@pytest.mark.parametrize("hebrew, vulgate", [
    (1, [1]), (8, [8]), (9, [9]), (10, [9]), (23, [22]), (51, [50]), (110, [109]), (113, [112]),
    (114, [113]), (115, [113]), (116, [114, 115]), (119, [118]), (146, [145]), (147, [146, 147]), (150, [150]),
])
def test_numbering(lp, hebrew, vulgate):
    assert lp.vulgate(hebrew) == vulgate


def test_the_psalter(lp):
    ps = lp.psalms()
    assert len(ps) == 150
    assert lp.incipit(109) == "Dixit Dóminus Dómino meo"
    assert [p["name"] for p in ps["118"]["parts"]][:3] == ["Aleph", "Beth", "Gimel"] and len(ps["118"]["parts"]) == 22
    assert ps["109"]["english"][0][1].startswith("The Lord said to my Lord")
    assert all(not l.startswith("﻿") for p in ps.values() for l in p["latin"])


def test_parse(lp):
    assert lp.parse("110") == (110, [(109, 0)], False)
    assert lp.parse("23 organ") == (23, [(22, 0)], True)
    assert lp.parse("119 beth") == (119, [(118, 1)], False)
    assert lp.parse("119 22") == (119, [(118, 21)], False)
    assert lp.parse("116") == (116, [(114, 0), (115, 0)], False)
    assert lp.parse("hello") is None and lp.parse("151") is None


def test_pointing_follows_the_liber(sp):
    """Tone 8 as the Liber Usualis sets Psalm 109's first verse."""
    t = sp.TONES["8"]
    sy = sp.syllables("Dixit Dóminus Dómino meo:")
    first = [n[0][0] for n in sp.point(sy, t["mediant"], t["clef"], True)]
    assert first == [55, 57, 60, 60, 60, 60, 60, 60, 62, 60]          # g a, c on the tenor, d on "me", c
    sy = sp.syllables("Sede a dextris meis:")
    second = [n[0][0] for n in sp.point(sy, t["terminations"]["G"], t["clef"], False)]
    assert second == [60, 60, 60, 59, 60, 57, 55]                      # ... b c on "dex-tris", a on "me", g
    assert [s["text"] for s in sp.syllables("Israël")] == ["Is", "ra", "ël"]


def test_the_post(lp):
    msg = lp.chant_message(110, 109)
    assert "Psalm 110 · Vulgate 109 · *Dixit Dóminus Dómino meo*" in msg["content"]
    latin, english = msg["embeds"]
    assert latin.description.startswith("Dixit Dóminus Dómino meo: ✱ Sede a dextris meis:")
    assert english.description.startswith("The Lord said to my Lord")
    if lp.audio_path(109, 0, False) is None:
        pytest.skip("the chanted psalms aren't rendered here (scripts/build_psalm_chant.py)")
    assert msg["file"].filename == "Psalm_110_sung.ogg"
    assert [getattr(i, "item", i).label for i in msg["view"].children][0] == "Organ"
    organ = lp.chant_message(119, 118, 1, organ=True)
    assert organ["file"].filename == "Psalm_119_Beth_organ.ogg" and "2 of 22" in organ["content"]


def test_every_psalm_is_rendered(lp):
    if not lp.AUDIO_DIR.exists():
        pytest.skip("the chanted psalms aren't rendered here (scripts/build_psalm_chant.py)")
    for v, p in lp.psalms().items():
        for i, _ in enumerate(p["parts"]):
            for organ in (False, True):
                path = lp.audio_path(int(v), i, organ)
                assert path is not None, (v, i, organ)
                assert path.stat().st_size < 10_000_000, (v, i, "over Discord's upload limit")


def test_scores(lp):
    if not (lp.AUDIO_DIR / "score").exists():
        pytest.skip("the psalm scores aren't drawn here (scripts/build_psalm_chant.py --scores)")
    for v, p in lp.psalms().items():
        for i, _ in enumerate(p["parts"]):
            assert lp.score_paths(int(v), i), (v, i)
    labels = [getattr(b, "item", b).label for b in lp.chant_message(110, 109)["view"].children]
    assert labels == ["Organ", "Score"]
    msg = lp.score_message(110, 109, 0, 0)
    assert "pointed to the 8th tone, ending G" in msg["content"] and msg["file"].filename == "score_1.png"
    long = max(((int(v), i) for v, p in lp.psalms().items() for i, _ in enumerate(p["parts"])),
               key=lambda vi: len(lp.score_paths(*vi)))
    n = len(lp.score_paths(*long))
    if n > 1:
        for page in range(n):
            ids = [getattr(b, "item", b).custom_id for b in lp.score_message(1, *long, page)["view"].children]
            assert len(set(ids)) == 2


def test_the_commands(lp, fake_ctx):
    from bot_commands import hymns, liturgy
    asyncio.run(liturgy.cmd_psalm.callback(fake_ctx, args="110 chant"))
    assert "Dixit" in fake_ctx.sent[-1]["content"]
    asyncio.run(hymns.send_chant(fake_ctx, "psalm 51"))
    assert "Psalm 51" in fake_ctx.sent[-1]["content"]
    asyncio.run(liturgy.cmd_psalm.callback(fake_ctx, args="chant"))
    assert "Which psalm?" in fake_ctx.sent[-1]["content"]
