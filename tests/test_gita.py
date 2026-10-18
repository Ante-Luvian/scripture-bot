"""More Gita translations and the commentaries, from the vedicscriptures Gita API."""
import pytest

import gita_lookup as gl

V = {"siva": {"author": "Swami Sivananda", "et": "2.47 Thy right is to work only.", "ec": "2.47 कर्मणि in work"},
     "sankar": {"author": "Sri Shankaracharya", "et": "2.47 Te, your; adhikarah, right.", "sc": "।।2.47।। कर्मण्येव"},
     "prabhu": {"author": "Prabhupada", "et": "You have a right to perform your prescribed duty.", "ec": " There are three considerations."}}


@pytest.fixture
def api(monkeypatch):
    monkeypatch.setattr(gl, "fetch", lambda ch, v: {**V, "siva": {"et": f"{ch}.{v} Verse {v} by Sivananda."}} if v != 47 else V)


@pytest.mark.parametrize("ref, parsed", [
    ("Gita 2:47 sivananda", (2, 47, 47, ["sivananda"])), ("Bhagavad Gita 2:47-48 siva shankara", (2, 47, 48, ["sivananda", "shankara"])),
    ("BG 18:66 purport", (18, 66, 66, ["purport"])), ("Gita 2:47", None), ("Gita 2 sivananda", None), ("John 3:16 shankara", None),
])
def test_parse(ref, parsed):
    assert gl.parse(ref) == parsed


def test_plain_gita_stays_purohit(lookup):
    assert "Purohit" in lookup.get_verse("Gita 2:47")["source"]
    assert not lookup.get_verse("Gita 2:48")["text"].startswith("Revised")


def test_named_translations_and_commentaries(lookup, api):
    r = lookup.get_verse("Gita 2:47 sivananda")
    assert r["text"] == "Thy right is to work only." and r["source"] == "Swami Sivananda"
    assert lookup.get_verse("Gita 2:47 shankara")["text"] == "Te, your; adhikarah, right."
    assert lookup.get_verse("Gita 2:47 purport")["text"] == "There are three considerations."
    both = lookup.get_verse("Gita 2:47-48 purohit sivananda")
    assert "__Shri Purohit Swami (1935)__" in both["text"] and "**[48]** Verse 48 by Sivananda." in both["text"]
    assert "72 verses" in lookup.get_verse("Gita 2:73 sivananda")["error"]


@pytest.mark.live
def test_gita_api_live():
    data = gl.fetch(2, 47)
    for name, (key, field, _) in gl.EDITIONS.items():
        assert name == "purohit" or (data.get(key) or {}).get(field), name
