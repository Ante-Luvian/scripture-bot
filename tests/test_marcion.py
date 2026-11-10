"""Marcion's Gospel, reconstructed (scripts/build_gnosis.py marcion)."""
import pytest


@pytest.mark.parametrize("ref, words", [
    ("Gospel of Marcion 4:31", "In the fifteenth year of Tiberius Caesar, Pontius Pilate being governor of Judea, "
                               "Jesus descended [out of heaven] into Capernaum"),          # (its opening, "3:1/4:31")
    ("Marcion's Gospel 4:16", "And he came to Nazareth"),
    ("Gospel of Marcion 4:25", "*(Zahn omits — relocated to 17:19)*\n[But I tell you of a truth"),
    ("Gospel of Marcion 17:18", "(4:27) And many lepers were in Israel"),                 # (moved here)
    ("Gospel of Marcion 23:25", "whom they were asking for"),                             # (the page: "sking")
    ("Gospel of Marcion 24:39", "for a spirit hath not flesh and bones"),
])
def test_passages(lookup, ref, words):
    result = lookup.get_verse(ref)
    assert result.get("found"), ref
    assert words in result["text"], (ref, result["text"][:300])


def test_layout(lookup):
    book = lookup._data["gnostic"]["Gospel of Marcion"]
    assert list(book) == [str(c) for c in range(4, 25)]                   # (no Luke 1-3: Marcion began at 4:31)
    assert "1" not in book["4"] and "39" not in book["4"]                  # (4:38-39 unattested)
    text = "\n".join(t for vs in book.values() for t in vs.values())
    for junk in ("Adv.Marc", "Panarion", "unattested", "Dopey", "[-", "Tert", "neccess"):
        assert junk not in text, junk
    assert text.count("*(Zahn omits") > 10
