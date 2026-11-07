"""Metatron literature (2026-11-07): Ginzberg's Legends of the Jews (scripts/build_jewish_legends.py), and the Targum
lookups (Pseudo-Jonathan names Enoch "Metatron, the Great Scribe" at Genesis 5:24), whose Sefaria titles were
wrong: every Pseudo-Jonathan, most Targum Jonathan and all Neofiti references failed or showed the wrong verses."""
import json

import pytest

from core import ROOT


@pytest.fixture(scope="module")
def legends():
    return json.loads((ROOT / "data" / "jewish" / "legends_of_the_jews.json").read_text(encoding="utf-8"))["books"][
        "Legends of the Jews"]


def found(lookup, ref):
    res = lookup.get_verse(ref)
    assert res.get("found"), (ref, res.get("error"))
    return res


def test_legends_of_the_jews(lookup, legends):
    assert sorted({c.split(".")[0] for c in legends}) == ["1", "2", "3", "4"] and len(legends) > 400
    assert "*The Ascension of Enoch*" in found(lookup, "Legends of the Jews 1.37")["text"]
    assert "Metatron" in "\n".join(legends["1.38"].values())                      # (The Translation of Enoch)
    assert found(lookup, "ginzberg 1.1:1")["text"].count("*I. The Creation of the World*")
    assert legends["3.1"]["1"].startswith("*Moses in the Wilderness*\n*The Long Route*")   # (an unnumbered chapter)


def test_3_enoch(lookup):
    """A machine translation of Vatican MS 228, in Odeberg's 48 chapters (each opens "Rabbi Ishmael said")."""
    book = json.loads((ROOT / "data" / "charles" / "3_enoch.json").read_text(encoding="utf-8"))
    assert "machine translation (AI)" in book["source"]
    chapters = book["books"]["3 Enoch"]
    assert list(chapters) == [str(n) for n in range(1, 49)]
    assert all(c["1"].startswith("Rabbi Ishmael said") for n, c in chapters.items() if n != "1")
    assert "Because I am Enoch, the son of Jared" in found(lookup, "3 Enoch 4")["text"]      # (Odeberg's 4)
    assert "Right Hand" in found(lookup, "metatron 48:1")["text"]
    text = "\n".join(v for c in chapters.values() for v in c.values())
    assert not any(ch in text for ch in "​‌‍﻿그<>")                   # (watermark, a Korean slip)
    assert max(len(v) for c in chapters.values() for v in c.values()) < 2000


def test_the_targum_titles(lookup, monkeypatch):
    """Sefaria's own titles (no network here: the reference each asks Sefaria for)."""
    import scripture_lookup
    asked = []
    monkeypatch.setattr(scripture_lookup, "fetch_sefaria_generic",
                        lambda ref: asked.append(ref) or {"found": True, "text": "x"})
    for ref in ("Targum Pseudo-Jonathan Genesis 5:24", "Targum Jonathan Isaiah 53:5", "Targum Jonathan Psalms 1:1",
                "Targum Onkelos Genesis 1:1", "Targum Neofiti Genesis 1:3"):
        lookup.get_verse(ref)
    assert asked == ["Targum_Jonathan_on_Genesis.5.24", "Targum_Jonathan_on_Isaiah.53.5", "Aramaic_Targum_to_Psalms.1.1",
                     "Onkelos_Genesis.1.1", "Targum_Neofiti.1.3"]
    res = lookup.get_verse("Targum Neofiti Exodus 3:14")                         # (Sefaria's is Genesis 1:1-8)
    assert not res["found"] and "Genesis 1:1-8" in res["error"]
