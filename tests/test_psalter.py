"""!metrical: the Scottish Metrical Psalter (1650), its tunes, and finding a psalm."""
import asyncio
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def ps(bot_module):
    from bot_commands import psalter
    return psalter


def test_the_whole_psalter_is_there(ps):
    numbers = {p["number"] for p in ps.psalter()["psalms"] if p["version"] == "primary"}
    assert numbers == set(range(1, 151))
    for p in ps.psalter()["psalms"]:
        assert p["stanzas"] and all(s["lines"] for s in p["stanzas"]), p["number"]
        assert p["tune"] in ps.tunes(), p["number"]
        assert ps.tunes()[p["tune"]]["meter"] == p["meter"], p["number"]       # the tune fits the words


def test_psalm_23(ps):
    p = ps.get_psalm(23)
    assert p["stanzas"][0]["lines"] == ["The LORD's my shepherd, I'll not want.", "He makes me down to lie",
                                        "In pastures green: he leadeth me", "The quiet waters by."]
    assert p["tune"] == "crimond"
    assert ps.get_psalm(100, second=True)["first_line"].startswith("O all ye lands")
    assert ps.get_psalm(100)["tune"] == "old-hundredth"


def test_every_tune_plays_without_numpy(ps):
    source = (ROOT / "bot_commands" / "psalter.py").read_text(encoding="utf-8")
    assert "hymn_audio" not in source and "numpy" not in source
    for tid in ps.tunes():
        path = ps.audio_path(tid)
        assert path and path.read_bytes()[:4] == b"OggS" and path.stat().st_size < 1_000_000, tid


def test_crimond_is_crimond(ps):
    import hymn_audio
    melody = sorted(n for n in hymn_audio.midi_notes(ROOT / "data" / "psalter" / "midi" / "crimond.mid") if n[3] == 0)
    # "The LORD's my shep-herd": C, A, B flat, G, C, as in the CCEH score
    assert [p for _, _, p, _ in melody[:5]] == [60, 69, 70, 67, 72]
    assert melody[1][1] - melody[1][0] > 1.5 * (melody[0][1] - melody[0][0])    # the long A on "LORD's"


@pytest.mark.parametrize("text, want", [
    ("23", (23, False, None)),
    ("Psalm 100b", (100, True, None)),
    ("100 second", (100, True, None)),
    ("119:105-112", (119, False, (105, 112))),
    ("ps 46:1", (46, False, (1, 1))),
    ("shepherd", None),
])
def test_reading_a_request(ps, text, want):
    assert ps.parse_request(text) == want


def test_search(ps):
    assert ps.search("the lord's my shepherd")[0]["number"] == 23
    assert {p["number"] for p in ps.search("crimond")} >= {23}               # a tune lists its psalms
    assert ps.search("zzzqqq") == []


def test_long_psalms_turn_pages(ps):
    p = ps.get_psalm(119)
    shown = ps.pages(p)
    assert len(shown) > 3 and all(len(page) <= ps.PAGE_CHARS for page in shown)
    assert "".join(shown).count("**") // 2 == len(p["stanzas"])            # nothing lost between pages
    some = ps.pages(p, (105, 112))
    assert len(some) == 1 and some[0].startswith("**105** ")
    labels = [c.item.label for c in ps.psalm_view(p, page=1).children if hasattr(c.item, "label")]
    assert "◀ Earlier verses" in labels and "Later verses ▶" in labels


def test_metrical_command(ps, fake_ctx):
    asyncio.run(ps.send_metrical(fake_ctx, "23"))
    sent = fake_ctx.sent[-1]
    assert sent["embed"].title == "🎶 Psalm 23"
    assert sent["embed"].description.startswith("**1** The LORD's my shepherd")
    assert "CRIMOND" in sent["embed"].fields[0].value
    kinds = [type(c).__name__ for c in sent["view"].children]
    assert kinds.count("PsalterButton") == 2 and "TuneMenu" in kinds
    asyncio.run(ps.send_metrical(fake_ctx, "100"))
    labels = [getattr(c.item, "label", None) for c in fake_ctx.sent[-1]["view"].children]
    assert "Second version" in labels
    asyncio.run(ps.send_metrical(fake_ctx, "23b"))
    assert "only one version" in fake_ctx.sent[-1]["content"]
    asyncio.run(ps.send_metrical(fake_ctx, "151"))
    assert "Psalms 1 to 150" in fake_ctx.sent[-1]["content"]


def test_psalm_sing_routes_here(bot_module, fake_ctx):
    from bot_commands import liturgy
    asyncio.run(liturgy.cmd_psalm.callback(fake_ctx, args="23 sing"))
    assert fake_ctx.sent[-1]["embed"].title == "🎶 Psalm 23"


def test_kjv_button(ps):
    embed = ps.kjv_embed(ps.get_psalm(23))
    assert embed.description.startswith("**1** The Lord is my shepherd")


def test_playing_another_tune(ps):
    sent = {}

    class Response:
        async def send_message(self, content=None, **kwargs):
            sent.update(kwargs, content=content)

    class Interaction:
        response = Response()

    asyncio.run(ps.play(Interaction(), ps.get_psalm(23), "dundee"))
    assert "DUNDEE" in sent["content"] and "another tune" in sent["content"]
    assert sent["file"].filename == "Psalm_23_Dundee.ogg"
