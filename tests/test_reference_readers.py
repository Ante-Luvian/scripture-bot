"""How a reference is read: ScriptureLookup's readers, in order (scripture_lookup, "How a reference is
read"). The order matters, so it's pinned here, and each reader is tried on what it's for."""
import pytest


def names(lookup, online=True):
    return [n for n, _, _ in lookup._readers_before_parsing(online)]


def test_the_order(lookup):
    order = names(lookup)
    assert order.index("Plato by Stephanus page") < order.index("the Babylonian Talmud by page")
    assert order[:4] == ["the Quran, from the Quran API", "the Pali Canon, from SuttaCentral",
                         "the Gita's other translations, from the Gita API", "Sikh scripture, from BaniDB"]
    assert order[-1] == "anything Sefaria has that the parser can't read"
    assert names(lookup, online=False) == order[4:]                 # (inside a lookup that's already online)
    unknown = [n for n, _, _ in lookup._readers_for_unknown_books()]
    assert unknown[0] == "the Mishnah" and unknown[-2] == "the hadith" and "Sefaria" in unknown[-1]


@pytest.mark.parametrize("ref, reader, expect", [
    ("Epistle of Jeremiah 1:5", "_read_epistle_of_jeremiah", "Baruch 6:5"),
    ("Delphi 1:5", "_read_delphi", "Delphi 1:5"),
    ("Baal 1:1", "_try_ancient_near_east", "Baal and Yamm 1"),
    ("Republic 514a", "_try_stephanus", "Republic 514a"),
])
def test_each_offline_reader(lookup, ref, reader, expect):
    result = getattr(lookup, reader)(ref)
    assert result and result["found"] and result["reference"] == expect
    assert lookup.get_verse(ref)["reference"] == expect                 # and it's the one that answers


@pytest.mark.parametrize("reader, ref", [
    ("_read_epistle_of_jeremiah", "John 3:16"), ("_read_delphi", "John 3:16"), ("_read_talmud", "John 3:16"),
    ("_read_zohar", "John 3:16"), ("_try_stephanus", "John 3:16"), ("_read_unparseable", "John 3:16"),
])
def test_readers_pass_on_what_isnt_theirs(lookup, reader, ref):
    assert getattr(lookup, reader)(ref) is None


def test_homer_by_book_and_line(lookup):
    assert lookup._homer_lines("Iliad 6.440-465") == "Iliad 6:440-465"
    assert lookup._homer_lines("John 3.16-18") == "John 3.16-18"          # (not a poem cited by line)


def test_the_first_reader_that_answers_wins(lookup, monkeypatch):
    import quran_lookup
    import sutta_lookup
    asked = []
    monkeypatch.setattr(quran_lookup, "get_quran", lambda ref, local: asked.append("quran") or None)
    monkeypatch.setattr(sutta_lookup, "get_sutta", lambda ref: asked.append("sutta") or
                        {"found": True, "reference": "MN 1", "text": "x"})
    result = lookup.get_verse("MN 1")
    assert asked == ["quran", "sutta"] and result["tradition"] == "buddhist"


def test_an_unknown_book_tries_the_online_libraries_in_order(lookup, monkeypatch):
    tried = []
    monkeypatch.setattr(type(lookup), "_try_sefaria", lambda self, *a: tried.append("mishnah") or None)
    monkeypatch.setattr(type(lookup), "_try_yerushalmi", lambda self, *a: tried.append("yerushalmi") or None)
    monkeypatch.setattr(type(lookup), "_try_hadith", lambda self, ref: tried.append("hadith") or
                        {"found": True, "reference": "Sahih al-Bukhari 1", "text": "x"})
    result = lookup.get_verse("Nosuchbookatall 1:1")
    assert tried[:2] == ["mishnah", "yerushalmi"] and tried[-1] == "hadith"
    assert result["tradition"] == "islamic"
