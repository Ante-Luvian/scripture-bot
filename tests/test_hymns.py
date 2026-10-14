"""!hymn: finding hymns, their words as built from the Open Hymnal's scores, and playing the tunes."""
import asyncio
import importlib.util
import io
import re
import wave
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def hy(bot_module):
    from bot_commands import hymns
    return hymns


@pytest.fixture(scope="module")
def builder():
    spec = importlib.util.spec_from_file_location("build_hymns", ROOT / "scripts" / "build_hymns.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _one(hy, title):
    return next(h for h in hy.hymns() if h["title"] == title)


@pytest.mark.parametrize("query, title", [
    ("amazing grace", "Amazing Grace"),
    ("Amazing grace! How sweet the sound", "Amazing Grace"),            # the first line
    ("silent night", "Silent Night"),
    ("hark the herald", "Hark! The Herald Angels Sing"),
    ("when peace like a river", "It Is Well With My Soul"),            # a line from the words
])
def test_finding_a_hymn(hy, query, title):
    assert hy.find_hymns(query)[0]["title"] == title


def test_by_topic_and_by_passage(hy):
    christmas = [h["title"] for h in hy.find_hymns("christmas")]
    assert "Silent Night" in christmas and len(christmas) > 10
    psalm = hy.hymns_for_passage("Psalm 18:2")
    assert "A Mighty Fortress Is Our God" in [h["title"] for h in psalm]
    assert hy.hymns_for_passage("not a reference at all") is None
    assert "Amazing Grace" in [h["title"] for h in hy.find_hymns("John 9:25")]


def test_words_are_clean_and_set_in_lines(hy):
    for h in hy.hymns():
        assert h["stanzas"], h["title"]
        for text in h["stanzas"] + [h["refrain"]]:
            assert not re.search(r"[~*_\\|%{}<>�]", text), (h["title"], text[:60])
    grace = _one(hy, "Amazing Grace")
    assert grace["stanzas"][0].split("\n") == ["Amazing grace! How sweet the sound", "That saved a wretch like me!",
                                               "I once was lost, but now am found;", "Was blind, but now I see."]


def test_refrains_are_printed_once(hy):
    well = _one(hy, "It Is Well With My Soul")
    assert well["stanzas"][1].endswith("And hath shed His own blood for my soul.")
    assert well["refrain"].startswith("It is well, with my soul,")
    far = _one(hy, "Far, Far Away On Judea's Plains")          # its refrain is printed only under verse 1
    assert far["refrain"].startswith("Glory to God, glory to God,")
    child = _one(hy, "What Child Is This?")                     # a shared last line isn't a refrain
    assert child["stanzas"][0].endswith("The Babe, the Son of Mary.") and not child["refrain"]




def test_every_hymn_has_a_tune(hy):
    for h in hy.hymns():
        if "midi" in h:                                           # (the chant is rendered from its score)
            assert (hy.MIDI_DIR / h["midi"]).exists(), h["title"]
        assert hy.audio_path(h) is not None, h["title"]          # rendered ahead: python scripts/render_hymn_audio.py


def test_the_bot_needs_nothing_to_play_a_tune(hy):
    # the live service runs as SYSTEM without numpy/mido: playing only sends a file
    source = (ROOT / "bot_commands" / "hymns.py").read_text(encoding="utf-8")
    assert "import hymn_audio" not in source and "numpy" not in source
    path = hy.audio_path(_one(hy, "Amazing Grace"))
    assert path.suffix == ".ogg" and path.read_bytes()[:4] == b"OggS" and path.stat().st_size < 1_000_000


def test_the_tune_is_right(hy):
    import hymn_audio
    melody = sorted(n for n in hymn_audio.midi_notes(hy.MIDI_DIR / _one(hy, "Amazing Grace")["midi"]) if n[3] == 0)
    names = "C C# D Eb E F F# G Ab A Bb B".split()
    assert [names[p % 12] for _, _, p, _ in melody[:9]] == ["D", "G", "B", "G", "B", "A", "G", "E", "D"]


def test_playing_makes_a_wav(hy):
    import hymn_audio
    data = hymn_audio.render(hy.MIDI_DIR / _one(hy, "Silent Night")["midi"])
    with wave.open(io.BytesIO(data)) as w:
        assert w.getframerate() == hymn_audio.SAMPLE_RATE and w.getnframes() > hymn_audio.SAMPLE_RATE * 10
    assert len(data) < 9 * 1024 * 1024                          # under Discord's upload limit


def test_abc_reader(builder):
    abc = "L: 1/4\nK: G\n[V: S1V1] [Q:1/4=120] D | G2- G (3ABc | ^F G :| d & B |]\n"
    tempo, voices = builder.abc_music(abc)
    assert tempo == 30                                           # whole notes a minute
    notes = voices["S1V1"]
    # D, G tied over three beats, a triplet, F sharp (F is sharp in G anyway), the repeat, then two notes at once
    pitches = [p for _, _, p in notes]
    assert pitches[:7] == [62, 67, 69, 71, 72, 66, 67]
    assert notes[1][1] == pytest.approx(0.75) and notes[2][1] == pytest.approx(1 / 6)
    assert pitches[7:14] == pitches[:7]                          # played twice
    assert notes[-1][0] == notes[-2][0]                          # "&": d and B together


def test_hymn_command(hy, fake_ctx):
    asyncio.run(hy.send_hymn_search(fake_ctx, "amazing grace"))
    sent = fake_ctx.sent[-1]
    assert sent["embed"].title == "🎵 Amazing Grace"
    assert "John Newton" in sent["embed"].fields[0].value
    labels = [item.item.label for item in sent["view"].children]
    assert labels == ["Play the tune", "Read the passages"]
    asyncio.run(hy.send_hymn_search(fake_ctx, "christmas"))
    assert "Hymns for" in fake_ctx.sent[-1]["embed"].title
    asyncio.run(hy.send_hymn_search(fake_ctx, "zzzqqq"))
    assert "No hymn found" in fake_ctx.sent[-1]["content"]


def test_passages_button(hy):
    embed = hy.passages_embed(_one(hy, "Amazing Grace"))
    assert embed.fields[0].name == "John 9:25" and "I was blind" in embed.fields[0].value


@pytest.mark.parametrize("title, first", [
    ("Once in Royal David's City", "Once in royal David’s city"),
    ("Jerusalem (And Did Those Feet in Ancient Time)", "And did those feet in ancient time"),
    ("I Heard the Voice of Jesus Say", "I heard the voice of Jesus say,"),
    ("A Beautiful Life", "Each day I'll do a golden deed,"),
    ("I Vow to Thee, My Country", "I vow to thee, my country, all earthly things above"),
])
def test_hymns_from_hymnary(hy, title, first):
    h = _one(hy, title)
    assert h["first_line"] == first and h["source"].startswith(("Hymnary.org", "Wikipedia")) and h["scripture"]
    assert (hy.MIDI_DIR / h["midi"]).read_bytes().startswith(b"MThd") and hy.audio_path(h)
    if title == "A Beautiful Life":                              # its refrain, printed once, without "[Refrain]"
        assert h["refrain"].startswith("Life's evening sun is sinking low")
        assert len(h["stanzas"]) == 5 and "Refrain" not in "".join(h["stanzas"])


def test_play_sends_just_the_audio(hy):
    sent = {}

    class Response:
        async def send_message(self, content=None, **kwargs):
            sent.update(kwargs, content=content)

    class Interaction:
        response = Response()

    asyncio.run(hy.play(Interaction(), _one(hy, "I Heard the Voice of Jesus Say")))
    assert "files" not in sent and sent["file"].filename.endswith(".ogg")


def test_the_phos_hilaron(hy):
    found = hy.find_hymns("Phos Hilaron")
    assert found and found[0]["first_line"] == "O gladsome light, O grace"
    assert len(found[0]["stanzas"]) == 3 and hy.audio_path(found[0]) is not None
