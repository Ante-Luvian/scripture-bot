"""Texts that exist only as page scans, OCR'd and proofread against every page image (the owner's go-ahead,
2026-11-11): the Acts of Apollonius (Conybeare, 1894) and the Testaments of Isaac and Jacob (Gaselee, 1927)."""
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
