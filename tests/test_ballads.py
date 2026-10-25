"""!ballad: Child's ballads, their tunes (the Digital Tradition's notation, read as SongWright IV wrote it) and
their recordings."""
import asyncio
import json
import re
import sys

import pytest

from core import ROOT

sys.path.insert(0, str(ROOT / "scripts"))


@pytest.fixture(scope="module")
def ballads(lookup):
    from bot_commands import ballads as b
    return b


class Ctx:
    guild = None
    author = "tester"

    def __init__(self):
        self.sent = []

    async def send(self, content=None, **kw):
        self.sent.append((content, kw))


def ask(ballads, q):
    ctx = Ctx()
    asyncio.run(ballads.send_ballad(ctx, q))
    return ctx.sent[-1]


def test_all_305_are_here_in_their_versions(ballads):
    assert sorted(ballads.by_number()) == list(range(1, 306))
    assert ballads.by_number()[12][:3] == ["12A", "12B", "12C"] and ballads.by_number()[22] == ["22"]
    assert ballads.title(84) == "Bonny Barbara Allen"


def test_the_text_is_the_books(ballads):
    """Lines sacred-texts' copy had lost letters from, mended from the proofread Gutenberg edition and the scans."""
    v = ballads.versions()
    assert v["2A"]["17"].startswith("‘When thou hast gotten thy turns well done")       # (was "en thou hast")
    assert "knyghtës cofer" in v["117A"]["42"] and "bowës bende" in v["116A"]["67"]   # (ë was a space)
    assert v["22"]["6"].startswith("‘Lakit me neyþer mete ne drynk")                     # (þ was "th"/"RR")
    assert "Sᵗ" not in v["145A"]["11"] and "St Georges" in v["145A"]["11"]
    text = json.dumps(v, ensure_ascii=False)
    assert not re.search(r"RR|a\+e|y\+o|-\+-|Sacred Texts", text)


def test_by_number_version_and_name(ballads):
    _, kw = ask(ballads, "12B")
    assert kw["embed"].title == "🎻 12. Lord Rendal" and "Child 12B" in kw["embed"].footer.text
    _, kw = ask(ballads, "matty groves")
    assert kw["embed"].title.startswith("🎻 81.") and "matty groves" in kw["embed"].author.name
    _, kw = ask(ballads, "barbara allen")
    assert kw["embed"].title.startswith("🎻 84.") and not kw["embed"].author.name
    assert ask(ballads, "12Z")[0].startswith("Child 12, *Lord Rendal*, has versions A, B")
    assert ask(ballads, "306")[0] == "Child's ballads are numbered 1 to 305."
    assert ask(ballads, "qqqq")[0].startswith("I couldn't find a ballad called")


def test_long_ballads_turn_pages_and_versions_cycle(ballads):
    _, kw = ask(ballads, "117")
    pages = ballads.pages("117A")
    assert len(pages) > 30 and all(len(p) <= ballads.PAGE + 600 for p in pages)
    ids = [getattr(i, "custom_id", None) for i in kw["view"].children]
    assert "ballad:next:117A:1" in ids and len(set(ids)) == len(ids)
    _, kw = ask(ballads, "12")
    assert any(getattr(i, "custom_id", "") == "ballad:ver:12A:0" for i in kw["view"].children)


def test_a_ballad_without_a_tune_says_so(ballads):
    _, kw = ask(ballads, "117")
    assert "I have no tune for this one" in kw["embed"].footer.text
    assert not any((getattr(i, "custom_id", None) or "").startswith("ballad:play") for i in kw["view"].children)


def test_the_recordings(ballads):
    videos = ballads._extras()["youtube"]
    assert len(videos) >= 290
    assert videos["81"]["title"] == "Matty Groves" and videos["277"]["title"] == "Wee Cooper O' Fife"
    assert videos["254"]["title"].startswith("2415. Sweet William (Child #254)")      # (out of place in the list)
    _, kw = ask(ballads, "84")
    link = [i for i in kw["view"].children if getattr(i, "url", None)]
    assert link and link[0].url == f"https://www.youtube.com/watch?v={videos['84']['id']}"


def test_tunes(ballads):
    listed = ballads._extras()["tunes"]
    assert len(listed) >= 160 and "84" in listed and "117" not in listed
    assert listed["277"][0]["title"]                                    # (the Wether's Skin: Child 277, not 227)
    if not ballads.tunes(84):
        pytest.skip("the tunes haven't been rendered here (python scripts/build_child_tunes.py)")
    kw = ballads.tune_message(84, 0)
    assert kw["content"].startswith("🎵 **") and "Digital Tradition" in kw["content"]
    assert kw["file"].filename.endswith(".ogg") and "view" in kw


def test_the_tune_notation():
    """SongWright IV's notation, as build_child_tunes reads it: Barbara Allan comes out as the familiar air."""
    import build_child_tunes as t
    text = ("N-Test\nK-D\nB-3/4\nS-100\nM-5D-8 S-6 F-8 G-8 a-5 G-8 F-8 E-8 D-5 E-8 F-8 a-8 d-4 d-4 c-8 a-5 R-8\n"
            "M-5b%8_b%8 G-7 G-7 G-7 B-=+>-= c&) c&) c&)\n")
    tune = t.parse(text)
    names = ["C", "C#", "D", "Eb", "E", "F", "F#", "G", "Ab", "A", "Bb", "B"]
    got = [(names[p % 12] + str(p // 12 - 1) if p is not None else "r", d) for p, d in tune["notes"]]
    assert got[:16] == [("D4", .5), ("F#4", .5), ("G4", .5), ("A4", 1.5), ("G4", .5), ("F#4", .5), ("E4", .5),
                        ("D4", 1.5), ("E4", .5), ("F#4", .5), ("A4", .5), ("D5", 1), ("D5", 1), ("C#5", .5),
                        ("A4", 1.5), ("r", .5)]
    assert got[16] == ("B4", 1.0)                                       # (a tie, the natural against the key's B)
    assert got[17:20] == [("G4", 1 / 3)] * 3                           # (quaver triplets)
    assert got[20] == ("B3", .125)                                      # (a chord: its first note, a demisemiquaver)
    assert got[21:] == [("B4", 1 / 6)] * 3                              # (C flat, semiquaver triplets)
    assert tune["pickup"] == .5 and not tune["unknown"]
    assert t.key_signature("Ab") == {"B": -1, "E": -1, "A": -1, "D": -1}
    assert t.key_signature("Em") == {"F": 1} and t.key_signature("Bb") == {"B": -1, "E": -1}


def test_the_reference_reader(lookup):
    r = lookup.get_verse("Child 12A:5")
    assert r["found"] and r["reference"] == "Child 12A:5" and r["tradition"] == "ballads"
    assert lookup.get_verse("Child 2:17")["reference"] == "Child 2A:17"
    assert lookup.get_verse("child ballads 84B")["text"].startswith("**[1]** *Bonny Barbara Allen*")
    assert not lookup.get_verse("Child 400")["found"]


def test_a_server_with_every_tradition_gets_the_ballads(monkeypatch):
    import core
    from scripture_lookup import TRADITIONS
    every_old = [k for k in TRADITIONS if k not in core.ADDED_TRADITIONS]
    monkeypatch.setattr(core, "_load_guild_config", lambda: {"1": {"traditions": every_old},
                                                             "2": {"traditions": ["bible", "christian"]}})
    assert core.tradition_enabled(1, "ballads") and not core.tradition_enabled(2, "ballads")
