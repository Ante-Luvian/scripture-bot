"""Shakespeare (scripts/build_shakespeare.py, the Folger text): every play and poem there whole and clean, and
cited by act.scene.line the way everyone quotes him -- "Hamlet 3.1.64" is "To be or not to be"."""
import re

import pytest


@pytest.fixture(scope="module")
def books(lookup):
    return lookup._data["shakespeare"]


def _text(book):
    return "\n".join(v for c in book.values() for v in c.values())


def test_every_work_is_there(books):
    assert len(books) == 42                                                     # (38 plays and 4 poems)
    assert len(books["Hamlet"]) == 20 and "5.2" in books["Hamlet"]
    assert len(books["Shakespeare's Sonnets"]) == 154
    assert {"0", "2.0", "6"} <= set(books["Henry V"])                           # (Prologue, a chorus, Epilogue)
    assert {"0.1", "0.2"} <= set(books["The Taming of the Shrew"])              # (the Induction's two scenes)
    assert max(int(k) for k in books["Lucrece"]["1"]) > 1800                    # (1855 lines)
    assert "Vilia miretur" not in _text(books["Venus and Adonis"])              # (the Latin epigraph: left out)


def test_clean(books):
    text = "\n".join(_text(b) for b in books.values())
    assert not re.search(r"<|&#|&[a-z]+;|�|\[138\]", text)
    assert not re.search(r"[a-z][,.;:][A-Z][a-z]", text)                        # (no lost space at a line break)
    for line in text.split("\n"):
        assert line.count("*") % 2 == 0, line


def test_cited_by_act_scene_line(lookup):
    r = lookup.get_verse("Hamlet 3.1.64")
    assert r["found"] and r["reference"].startswith("Hamlet 3.1:64") and "To be or not to be" in r["text"]
    assert lookup.get_verse("Hamlet 3.1:64")["reference"] == r["reference"]
    assert lookup.get_verse("Hamlet 3.1.56-90")["reference"].startswith("Hamlet 3.1:56")
    assert lookup.get_verse("Hamlet 3.1")["reference"] == "Hamlet 3.1"          # (the whole scene)
    assert "Friends, Romans, countrymen" in lookup.get_verse("JC 3.2.82")["text"]
    assert "Two households" in lookup.get_verse("Romeo and Juliet prologue")["text"]
    assert "Thus far with rough" in lookup.get_verse("Henry V epilogue")["text"]
    assert "Shall I compare thee" in lookup.get_verse("Sonnets 18")["text"]
    assert not lookup.get_verse("Hamlet 3.1.9999")["found"]
    assert lookup.get_verse("Macbeth 5.5.19")["tradition"] == "shakespeare"


def test_shakespeare_draws_a_passage_of_a_play(lookup):
    """!shakespeare: a passage with someone speaking, its scene named, and a card of its opening speeches."""
    import random
    from bot_commands import oracles
    rng = random.Random(1)
    for _ in range(50):
        book, chap, line = oracles.shakespeare_passage(rng)
        assert book not in (oracles.SONNETS, "Venus and Adonis", "Lucrece", "The Phoenix and Turtle")
        assert "**" in oracles._play_text(book, chap, line)
        title, text, _ = oracles._oracle_card_content("bard", f"{book}|{chap}|{line}")
        assert title.startswith(book) and text and "*" not in text and len(text) < 2000   # (a long speech whole)
    assert oracles._scene_name("0") == "Prologue" and oracles._scene_name("6") == "Epilogue"
    assert oracles._scene_name("2.0") == "Act 2, Chorus" and oracles._scene_name("3.1") == "Act 3, Scene 1"


def test_sonnet_picks(lookup):
    import random
    from bot_commands import oracles
    rng = random.Random(1)
    assert oracles._sonnet_pick("18", rng) == (oracles.SONNETS, "18", "1")
    assert isinstance(oracles._sonnet_pick("155", rng), str) and isinstance(oracles._sonnet_pick("0", rng), str)
    assert oracles._sonnet_pick("venus", rng)[0] == "Venus and Adonis"
    assert oracles._sonnet_pick("lucrece", rng)[2] != "0"                       # (not the dedication)
    drawn = {oracles._sonnet_pick("", rng)[0] for _ in range(300)}
    assert oracles.SONNETS in drawn and "Lucrece" in drawn                      # (all his poems in the draw)
    assert oracles._sonnet_title(oracles.SONNETS, "18", "1") == "Sonnet 18"
    assert oracles._sonnet_title("Lucrece", "1", "1").startswith("Lucrece, lines 1–")


def test_shared_titles_keep_their_old_books(lookup):
    """Suetonius's Julius Caesar, Plutarch's Pericles and Chaucer's Troilus are where they were."""
    assert lookup.get_verse("Julius Caesar 1:1")["tradition"] != "shakespeare"
    assert lookup.get_verse("Pericles 1:1")["tradition"] != "shakespeare"
    assert lookup.get_verse("Troilus 3:1")["reference"].startswith("Troilus and Criseyde")
