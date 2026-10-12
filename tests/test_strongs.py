"""strongs_lookup -- definitions, root-finding (!root), and word search."""
import pytest

import strongs_lookup as S


def test_dictionary_loaded():
    assert S.entry_count() > 14000


def test_get_definition_is_case_and_space_insensitive():
    entry = S.get_definition(" g26 ")
    assert entry and entry["lexeme"] == "ἀγάπη"


def test_unknown_number():
    assert S.get_definition("G999999") is None


@pytest.mark.parametrize("number, root", [
    ("G26", "G25"),   # agape <- agapao
    ("G25", "G25"),   # regression: must ignore "(or compare G5689)", a nonexistent number
    ("H6",  "H6"),    # "a primitive root" is its own root
])
def test_find_root(number, root):
    assert S.find_root(number) == root


def test_find_root_of_unknown_number_is_itself():
    assert S.find_root("G999999") == "G999999"


def test_root_family_is_direct_derivatives():
    root, family = S.get_root_family("G26")
    assert root == "G25"
    assert "G26" in family
    assert root not in family


@pytest.mark.parametrize("query", ["agape", "agápē", "AGAPE"])
def test_search_accent_and_case_insensitive(query):
    assert S.search_by_word(query)[0] == "G26"


def test_search_testament_filter():
    hebrew = S.search_by_word("love", testament="H")
    assert hebrew and all(n.startswith("H") for n in hebrew)


def test_search_empty_query():
    assert S.search_by_word("   ") == []
