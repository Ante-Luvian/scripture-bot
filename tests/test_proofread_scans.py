"""Texts that exist only as page scans, OCR'd and proofread against every page image (the owner's go-ahead,
2026-11-11): the Acts of Apollonius (Conybeare, 1894), the Testaments of Isaac and Jacob (Gaselee, 1927) and the
longer Joseph and Asenath (Brooks, 1918)."""
import re

import pytest


@pytest.mark.parametrize("ref, words", [
    ("Acts of Apollonius 1:0", "Christ, Who giveth all things, prepareth a crown of righteousness"),
    ("Acts of Apollonius 1:30", "the source of deathlessness for the soul"),
    ("Acts of Apollonius 1:47", "to Whom be glory for ever. Amen."),
    ("Martyrdom of Apollonius 1:17", "The Egyptians do homage to an onion in their folly."),
    ("Testament of Isaac 1:1", "This is the coming forth from the body of the Patriarch Isaac"),
    ("Testament of Isaac 1:31", "Abtelmoluchos"),
    ("Testament of Jacob 1:1", "This again also is the coming forth from the body of our father the Patriarch Jacob"),
    ("Joseph and Asenath (Longer Text) 1:1", "*Asenath is sought in Marriage by the King’s Son and many others.*\nIn the first year of plenty"),
    ("Longer Asenath 16:1", "Bring me also an honeycomb"),
    ("Joseph and Asenath (Longer Text) 29:1", "*Pharaoh’s Son dies. Pharaoh also dies and Joseph succeeds him.*"),
    ("Testament of Jacob 1:4", "receive the blessing of Isaac thy father and Rebecca thy mother"),
])
def test_passages(lookup, ref, words):
    result = lookup.get_verse(ref)
    assert result.get("found"), ref
    assert words in result["text"], (ref, result["text"][:300])


def test_sections_and_no_scan_debris(lookup):
    apollonius = lookup._data["patristics"]["Acts of Apollonius"]["1"]
    assert list(apollonius) == [str(n) for n in range(0, 48)]                 # (the prologue, then §§ 1-47)
    for book in ("Testament of Isaac", "Testament of Jacob"):
        for v, text in lookup._data["charles"][book]["1"].items():
            assert not re.search(r"\(f\. ?\d|[α-ω]|\b\w*\d\w*\b|[!?][!+*]|\s[,;:.]", text), (book, v, text[:120])
    for v, text in apollonius.items():
        assert not re.search(r"[α-ω]|[¹²³°®*]|‘‘|\s[,;:.]", text), (v, text[:120])


def test_brooks_asenath_is_the_longer_text_beside_cooks(lookup):
    books = lookup._data["charles"]
    longer, shorter = books["Joseph and Asenath (Longer Text)"], books["Joseph and Aseneth"]
    assert list(longer) == [str(n) for n in range(1, 30)]
    assert lookup.get_verse("Joseph and Aseneth 1:1")["reference"].startswith("Joseph and Aseneth 1")   # (Cook's, as before)
    for ch, verses in longer.items():
        for v, text in verses.items():
            assert not re.search(r"[α-ω]|[¹²³°®*†]|‘‘|\s[,;:.]|\b[A-Z]?[a-z]+[!?][a-z]", text.split("\n", 1)[-1]), (ch, v, text[:100])
