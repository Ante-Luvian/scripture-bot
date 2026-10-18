"""The Pali Canon from SuttaCentral (Sujato's translation)."""
import pytest

import sutta_lookup as sl

MN1 = {"keys_order": ["mn1:0.1", "mn1:0.2", "mn1:1.1", "mn1:1.2", "mn1:2.1", "mn1:3.1", "mn1:3.2"],
       "html_text": {"mn1:0.1": "<header><ul><li>{}</li></ul>", "mn1:0.2": "<h1>{}</h1></header>",
                     "mn1:1.1": "<p>{}", "mn1:1.2": "{}</p>", "mn1:2.1": "<h2>{}</h2>",
                     "mn1:3.1": "<p><span class='verse-line'>{}</span>", "mn1:3.2": "<span class='verse-line'>{}</span></p>"},
       "translation_text": {"mn1:0.1": "Middle Discourses 1 ", "mn1:0.2": "The Root of All Things ",
                            "mn1:1.1": "So I have heard. ", "mn1:1.2": "At one time<j> the Buddha... ",
                            "mn1:2.1": "The Unlearned ", "mn1:3.1": "First line, ", "mn1:3.2": "second line."}}
AN1 = {"keys_order": ["an1.1:0.1", "an1.1:1.1", "an1.5:0.1", "an1.5:1.0", "an1.5:1.1"],
       "html_text": {"an1.1:0.1": "<h1>{}</h1>", "an1.1:1.1": "<p>{}</p>", "an1.5:0.1": "<h3>{}</h3>",
                     "an1.5:1.0": "<h3>{}</h3>", "an1.5:1.1": "<p>{}</p>"},
       "translation_text": {"an1.1:0.1": "Numbered Discourses 1.1–10", "an1.1:1.1": "Sutta one.",
                            "an1.5:0.1": "x", "an1.5:1.0": "5", "an1.5:1.1": "Sutta five."}}


@pytest.fixture
def api(monkeypatch):
    pages = {"bilarasuttas/mn1/sujato?lang=en": MN1, "bilarasuttas/an1.5/sujato?lang=en": {"msg": "Not Found"},
             "suttaplex/an1?language=en": [{"uid": "an1.1-10"}, {"uid": "an1.11-20"}],
             "bilarasuttas/an1.1-10/sujato?lang=en": AN1}
    monkeypatch.setattr(sl, "_get", lambda path: pages[path])


@pytest.mark.parametrize("ref, parsed", [
    ("MN 1", ("mn", "mn1", None, None)), ("sn 56.11:3", ("sn", "sn56.11", 3, 3)), ("AN1.1-10", ("an", "an1.1-10", None, None)),
    ("Majjhima Nikaya 10", ("mn", "mn10", None, None)), ("Dhp 183 sujato", ("dhp", "dhp183", None, None)),
    ("Dhp 1:1", None), ("Snp 1.8", None), ("John 3:16", None), ("Thig 1.1:2-3", ("thig", "thig1.1", 2, 3)),
])
def test_parse(ref, parsed):
    assert sl.parse(ref) == parsed


def test_a_sutta(lookup, api):
    r = lookup.get_verse("MN 1")
    assert r["reference"] == "MN 1 · The Root of All Things" and "Sujato" in r["source"]
    assert r["text"] == "So I have heard. At one time the Buddha...\n\n**The Unlearned**\n\nFirst line,\nsecond line."
    assert lookup.get_verse("MN 1:3")["text"] == "First line,\nsecond line."


def test_a_sutta_kept_in_a_group(lookup, api):
    r = lookup.get_verse("AN 1.5")
    assert r["found"] and r["text"] == "Sutta five." and r["reference"].startswith("AN 1.5")


def test_the_bots_own_dhammapada_stays(lookup):
    assert "Müller" in lookup.get_verse("Dhammapada 1:1")["source"]


def test_pages():
    pages = sl.pack(["a" * 3000, "b. " * 2000, "c"])
    assert all(len(p) <= 3800 for p in pages) and pages[-1].endswith("c")


@pytest.mark.live
def test_suttacentral_live():
    r = sl.get_sutta("SN 56.11")
    assert r["found"] and "middle way" in " ".join(r.get("pages") or [r["text"]])
    assert sl.get_sutta("AN 1.5")["found"]
