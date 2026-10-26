"""The illustrated editions' pictures (bot_commands/illustrations.py): each tied to a passage the bot has, and
the 🖌️ button under !verse, !fable, !tale and !shakespeare. The pictures kept here (data/illustrations/<set>/)
aren't in git, so nothing below needs them; the JSON says where each one belongs."""
import re

import pytest


@pytest.fixture(scope="module")
def il(bot_module):
    from bot_commands import illustrations
    return illustrations


SETS = {"la_fontaine": 300, "aesop_rackham": 60, "aesop_crane": 40, "aesop_winter": 80, "grimm_crane": 100,
        "grimm_rackham": 70, "malory_beardsley": 15, "faerie_queene_crane": 9, "shakespeare_boydell": 70}


def test_the_sets(il):
    sets = il.sets()
    assert set(sets) == set(SETS)
    for name, least in SETS.items():
        assert len(sets[name]["pictures"]) >= least, name
    assert len({s["code"] for s in sets.values()}) == len(sets)
    keys = [p["key"] for p in il.pictures()]
    assert len(keys) == len(set(keys))
    assert all(re.fullmatch(r"[a-z]{2}[0-9a-f]{5}", k) for k in keys)


def test_every_picture_belongs_to_a_passage_the_bot_has(il, lookup):
    """Its book and chapter open, and a picture of some lines is at a line that's there."""
    for p in il.pictures():
        ref = f"{p['book']} {p['chapter']}" + (f":{p['start']}" if p.get("start") else "")
        assert lookup.get_verse(ref)["found"], (p["key"], ref)
        assert p.get("file") or re.match(r"https://[a-z.]+\.wikimedia\.org/", p["image"]), p["key"]


def test_a_fable_or_tale_picture_is_titled_as_the_bot_titles_the_fable(il, lookup):
    """The pictures matched by their story are shown under the bot's (Townsend's, Hunt's, Thornbury's) title."""
    for p in il.pictures():
        if p["book"] in ("Aesop's Fables", "Grimm's Household Tales", "Fables of La Fontaine"):
            first = lookup.get_verse(f"{p['book']} {p['chapter']}")["text"]
            assert f"*{p['title']}*" in first, p["key"]


def _here(il, found: list) -> list:
    """Those of some pictures that can be shown here: from Commons, or kept on this machine (the bot's)."""
    return [p for p in found if p.get("image") or il._local_file(p)]


@pytest.mark.parametrize("ref, label, title", [
    ("Aesop's Fables 12", "Pictures", "The Hare and the Tortoise"),          # Rackham, Crane and Winter
    ("Fables of La Fontaine 1", "Doré", "The Grasshopper and the Ant"),
    ("Grimm's Household Tales 69", "Rackham", "Jorinda and Joringel"),
    ("Le Morte d'Arthur 8.24", "Beardsley", "How Sir Tristram Drank of the Love Drink"),
    ("The Faerie Queene 1.1:14", "Crane", "Holiness defeats Error"),
    ("Hamlet 1.4:1", "Boydell", "Hamlet, Horatio, Marcellus and the Ghost"),
    ("King Lear 3.4:115", "Boydell", "“Off, off, you lendings—come, unbutton here”"),
])
def test_the_button_under_verse(il, lookup, ref, label, title):
    found = il.for_result(lookup.get_verse(ref))
    assert any(p["title"] == title for p in found)
    if len(_here(il, found)) < len(found):
        pytest.skip("the pictures kept here aren't built on this machine (scripts/build_illustrations.py)")
    [button] = il.buttons(found)
    assert button.item.label == label and button.item.custom_id.startswith("pics:")
    assert len(button.item.custom_id) <= 100


def test_a_picture_of_some_lines_only_goes_with_them(il, lookup):
    """Lear's "Off, off, you lendings" is at line 115 of 3.4: not with the scene's first passage."""
    assert il.for_result(lookup.get_verse("King Lear 3.4:1")) == []
    assert il.for_result(lookup.get_verse("King Lear 3.4:115"))


def test_boydell_scenes_are_folgers(il):
    """Boydell's Winter's Tale 4.3, the sheep-shearing, is Folger's 4.4."""
    shown = {(p["book"], p["chapter"]) for p in il.pictures() if p["set"] == "shakespeare_boydell"}
    assert ("The Winter's Tale", "4.4") in shown and ("The Winter's Tale", "4.3") not in shown


def test_no_button_without_a_picture(il, lookup):
    assert il.for_result(lookup.get_verse("John 3:16")) == []
    assert il.picture_buttons(lookup.get_verse("John 3:16")) == []
    assert il.picture_buttons({"found": False}) == []


def test_the_embed(il):
    p = next(p for p in il.pictures() if p["set"] == "grimm_rackham" and p.get("caption"))
    e = il.picture_embed(p)
    assert e.title.startswith("🖌️ ") and p["caption"] in e.description
    assert e.fields[0].value == f"`!verse Grimm's Household Tales {p['chapter']}`"
    assert e.footer.text.startswith("Arthur Rackham, The Fairy Tales of the Brothers Grimm (1909)")
    for q in il.pictures():                                     # (Discord: 6,000 characters a message)
        e = il.picture_embed(q)
        assert len(e.title) <= 256 and len(e.description or "") <= 1500


def test_the_button_under_fable_tale_and_shakespeare(il, monkeypatch):
    from bot_commands import fable, oracles, tales

    def labels(view):
        return [getattr(c, "item", c).label for c in view.children]
    assert "Rackham" in labels(tales.message(69)["view"])                     # (Rackham's, from Commons)
    assert "Rackham" not in labels(tales.message(200)["view"])
    if _here(il, il.for_passage("Fables of La Fontaine", "1")):
        assert "Doré" in labels(fable.message(1, code="lf")["view"])
    sent = {}

    class Author:
        id = 1

    class Ctx:
        guild = None
        author = Author()

        async def send(self, **kwargs):
            sent.update(kwargs)
    monkeypatch.setattr(oracles, "shakespeare_lot", lambda rng=None: (32, "Hamlet", "1", "4", "40"))
    import asyncio
    asyncio.run(oracles.cmd_shakespeare.callback(Ctx()))
    assert "Boydell" in labels(sent["view"])
