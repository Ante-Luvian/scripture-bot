"""The Catechism (data/catechism.json) and the Code of Canon Law (data/canon.json), as !ccc, !canon and asking the
library read them: clean of what the PDF they came from left. Canon 1247 read "works and aVairs" in an answer
(the ff ligature read as V), and every "§" was "Â§"."""
import json
import re

import pytest

from core import ROOT


def _texts(name):
    def walk(node):
        if isinstance(node, dict):
            for k, v in node.items():
                if k == "text" and isinstance(v, str):
                    yield v
                else:
                    yield from walk(v)
        elif isinstance(node, list):
            for v in node:
                yield from walk(v)
    return list(walk(json.loads((ROOT / "data" / name).read_text(encoding="utf-8"))))


@pytest.mark.parametrize("name", ["canon.json", "catechism.json"])
def test_no_broken_ligatures_or_mojibake(name):
    for text in _texts(name):
        assert not re.search(r"(?<![\w])[a-z]{1,8}[VYW][a-z]{2,}\b", text), text[:120]     # ("aVairs", "ofWce")
        assert "Â" not in text and "â€" not in text, text[:120]                            # ("Â§1")


def test_canon_1247():
    canon = {e["id"]: e for e in json.loads((ROOT / "data" / "canon.json").read_text(encoding="utf-8"))}
    assert "works and affairs which hinder the worship" in canon[1247]["text"]
