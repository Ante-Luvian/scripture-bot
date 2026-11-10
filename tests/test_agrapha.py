"""The Agrapha (scripts/build_agrapha.py): each saying word for word from the library's own copy of the writer who
quotes it, with that source and the command that opens it -- which must open the very passage."""
import re


def test_each_saying_is_in_its_source(lookup):
    agrapha = lookup._data["nt_apocrypha"]["Agrapha"]
    assert sum(map(len, agrapha.values())) >= 19
    for verses in agrapha.values():
        for text in verses.values():
            sayings = re.findall(r"“(.+?)”", text)
            ref = re.search(r"`!verse (.+?)`", text).group(1)
            source = lookup.get_verse(ref)
            assert source.get("found"), ref
            flat = re.sub(r"\s+", " ", source["text"]).lower()
            for saying in sayings:
                assert saying.lower().rstrip(".") in flat, (ref, saying[:60])


def test_found_by_name(lookup):
    assert lookup._resolve_book("agrapha")[1] == "Agrapha"
    assert "more blessed to give than to receive" in lookup.get_verse("Agrapha 1:1")["text"]
    assert "My mother, the Holy Spirit" in lookup.get_verse("Agrapha 4:2")["text"]
