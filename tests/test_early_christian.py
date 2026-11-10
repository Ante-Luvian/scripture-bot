"""The lost gospels in fragments and the early church documents (scripts/build_early_christian.py)."""
import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent

FRAGMENTS = ("Gospel according to the Hebrews", "Gospel of the Nazoreans", "Gospel of the Ebionites",
             "Gospel according to the Egyptians", "Egerton Gospel", "Oxyrhynchus Gospel 840", "Oxyrhynchus Gospel 1224",
             "Fayoum Gospel Fragment", "Preaching of Peter")
CHURCH = ("Muratorian Canon", "Marcionite Prologues", "Anti-Marcionite Prologues", "Inscription of Abercius",
          "Passion of the Scillitan Martyrs")


@pytest.mark.parametrize("ref, words", [
    ("Gospel of the Hebrews 5", "Even now did my mother the Holy Spirit take me by one of mine hairs"),
    ("Gospel of the Hebrews 2", "iii.11.7. For the Ebionites"),          # (a new paragraph at the top of a page)
    ("Gospel of the Hebrews 15", "Jerome.\n*On Ephesians*"),            # (James's heading joins its first passage)
    ("Gospel of the Hebrews 17", "Greek and Latin speech"),             # (the transcription: "arid")
    ("Gospel of the Nazoreans 2", "Behold, the mother of the Lord and his brethren"),
    ("Ebionites 3", "whereof the taste is the *taste* of manna"),
    ("Gospel of the Egyptians 3", "When ye have trampled on the garment of shame"),
    ("Egerton Gospel 2", "Master Jesus, journeying with lepers"),
    ("Oxyrhynchus 840 3", "Woe unto you, ye blind, that see not!"),
    ("Oxyrhynchus 840 3", "have been washed in living waters"),            # (runs over a page)
    ("Oxyrhynchus 1224 4", "For the one who is not against you is for you"),
    ("Fayoum 1", "said: The cock shall twice crow and thou *or* said: Before the cock crow twice to-day"),
    ("Preaching of Peter 4", "worshipping God through Christ in a new way"),
    ("Muratorian Canon 1", "The third book of the Gospel, that according to Luke"),
    ("Marcionite Prologues 1", "*To the Galatians*\nGalatians are Greeks."),
    ("Anti-Marcionite Prologues 1", "who was called Colobodactylus, because"),
    ("Abercius 13", "And set before me food the fish from the spring"),
    ("Scillitan Martyrs 27", "for ever and ever. Amen."),
])
def test_passages(lookup, ref, words):
    result = lookup.get_verse(ref)
    assert result.get("found"), ref
    assert words in result["text"], (ref, result["text"][:300])


def test_jamess_notes_left_out(lookup):
    books = {**lookup._data["nt_apocrypha"], **lookup._data["patristics"]}
    text = "\n".join(t for b in FRAGMENTS + CHURCH for vs in books[b].values() for t in vs.values())
    for note in ("When I published the note", "These Ebionites were vegetarians", "The borrowing from St. Luke",
                 "Epiphanius goes on to say", "There are allusions to the saying", "Shortly after this he cites Paul",
                 "Cyril convinced him", "The writer seems to show gross ignorance", "Jerome is our chief source",
                 "Go to the Chronological List", "Early Christian Writings", "Translation reprinted from",
                 "{{", "}}", "''", "<", ". . .", "Footnotes"):
        assert note not in text, note
    assert not re.search(r"[a-z]\d", text), re.search(r".{30}[a-z]\d.{30}", text)        # (no footnote marks)


def test_sources(lookup):
    assert "James (1924)" in lookup.get_verse("Gospel of the Hebrews 1")["source"]
    assert "Bell and T. C. Skeat" in lookup.get_verse("Egerton Gospel 1")["source"]
    assert "Burkitt" in lookup.get_verse("Marcionite Prologues 1")["source"]
    # the Muratorian Canon is the library's own ANF 5 copy, word for word
    caius = json.loads((ROOT / "data" / "patristics" / "caius.json").read_text(encoding="utf-8"))["books"]["Fragments"]["2"]
    assert lookup._data["patristics"]["Muratorian Canon"]["1"]["2"] == re.sub(r"^\d+\.\s*", "", caius["3"])
