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


def test_shakespeare_casts_lots_like_virgil(lookup):
    """!shakespeare: dice for the play (First Folio order), the act, the scene and the line; the line drawn,
    with its speaker, is in the play at that place."""
    import random
    from bot_commands import oracles
    order = oracles._play_lines()["order"]
    assert len(order) == 38 and order[0] == "The Tempest" and order[35] == "Cymbeline"      # (the Folio's 36)
    assert order[36:] == ["Pericles, Prince of Tyre", "The Two Noble Kinsmen"]
    assert oracles._play_lines()["lines"]["Hamlet"]["3.1"]["64"][0][:3] == [
        "HAMLET", "To be or not to be—that is the question:", 0]
    # a line is shown in its whole sentence, the line itself in bold (the owner: a cut line reads badly)
    helen = oracles._lot_text("All's Well That Ends Well", "1.1", "209")
    assert helen.startswith("*So is running away") and "***safety. But the composition" in helen
    assert "a good wing" in helen and helen.endswith("— Helen")
    rng = random.Random(1)
    for _ in range(200):
        n, play, act, scene, line = oracles.shakespeare_lot(rng)
        assert order[n - 1] == play and 1 <= int(act) <= 5
        text = oracles._lot_text(play, f"{act}.{scene}", line)
        assert text.startswith("*") and "—" in text
        found = lookup.get_verse(f"{play} {act}.{scene}.{line}")                    # (📜 In context)
        assert found["found"]
        title, card, _ = oracles._oracle_card_content("bard", f"{play}|{act}.{scene}|{line}")
        assert title == f"{play} {act}.{scene}.{line}" and card and "*" not in card
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
