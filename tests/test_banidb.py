"""Sikh scripture from BaniDB: more Guru Granth Sahib translations, the Dasam Granth, Bhai Gurdas."""
import pytest

import banidb_lookup as bl


def _line(n, ms="", bdb="", ssk=""):
    return {"lineNo": n, "translation": {"en": {"ms": ms, "bdb": bdb, "ssk": ssk}, "pu": {"ss": {"unicode": "ਪੰਜਾਬੀ"}}}}


PAGES = {("G", 1): [_line(1, "There is but one God.", "One Universal Creator God. ~", "One Universal Creator God. ~"),
                    _line(1, "Embrace His meditation.", "Chant And Meditate:", "Chant And Meditate:")],
         ("D", 1): [_line(74212, bdb="The Lord is One."), _line(74213, bdb="Name of the Bani : Japu Sahib")],
         ("B", 1): [_line(1, bdb="Invocation"), _line(1, bdb="I bow before the Guru."), _line(2, bdb="Second pauri.")]}


@pytest.fixture
def api(monkeypatch):
    monkeypatch.setattr(bl, "fetch_page", lambda src, page: PAGES.get((src, page)))


@pytest.mark.parametrize("ref, parsed", [
    ("Guru Granth Sahib 1:1 manmohan", ("G", 1, 1, 1, ["manmohan"])), ("Guru Granth Sahib 1:1", None),
    ("Dasam Granth 1", ("D", 1, None, None, ["banidb"])), ("Bhai Gurdas 1:1-2", ("B", 1, 1, 2, ["banidb"])),
    ("Vaaran 3", ("B", 3, None, None, ["banidb"])), ("SGGS 5:2 khalsa ms", ("G", 5, 2, 2, ["khalsa", "manmohan"])),
    ("John 3:16 manmohan", None),
])
def test_parse(ref, parsed):
    assert bl.parse(ref) == parsed


def test_plain_guru_granth_sahib_stays_ours(lookup):
    assert "Sant Singh Khalsa" in lookup.get_verse("Guru Granth Sahib 1:1")["source"]


def test_translations_side_by_side(lookup, api):
    r = lookup.get_verse("Guru Granth Sahib 1:1-2 khalsa manmohan")
    assert r["text"] == ("__Sant Singh Khalsa__\n**[1]** One Universal Creator God.\n**[2]** Chant And Meditate:\n\n"
                         "__Manmohan Singh__\n**[1]** There is but one God.\n**[2]** Embrace His meditation.")
    assert lookup.get_verse("Guru Granth Sahib 1:1 manmohan")["text"] == "There is but one God."


def test_dasam_granth_and_bhai_gurdas(lookup, api):
    assert lookup.get_verse("Dasam Granth 1:2")["text"] == "Name of the Bani : Japu Sahib"
    r = lookup.get_verse("Bhai Gurdas 1:1")
    assert r["text"] == "**[1]** Invocation\nI bow before the Guru." and "Vaaran of Bhai Gurdas" in r["source"]
    assert "has 2 pauris" in lookup.get_verse("Bhai Gurdas 1:5")["error"]
    assert "40 vaars" in lookup.get_verse("Bhai Gurdas 41")["error"]


@pytest.mark.live
def test_banidb_live():
    for src in "GDB":
        lines = bl.fetch_page(src, 1)
        assert lines and any(bl._english(l, "bdb") for l in lines), src
    assert bl._english(bl.fetch_page("G", 1)[0], "ms")
