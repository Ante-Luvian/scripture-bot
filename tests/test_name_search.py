"""Finding authors and books by name (2026-10-31): "cato" brought up Plato (one letter off), "cato the elder" the
Acts of the Apostles, and "Claudius Ptolemy" nothing. A name's whole words now come before any spelling-alike."""
import pytest


@pytest.fixture(scope="module")
def books(bot_module):
    from bot_commands import books
    return books


def test_cato_is_never_plato(books, lookup):
    for q in ("cato", "Cato"):
        found = books._author_works_node(q)
        assert found and "Plato" not in found[0] and "Euthyphro" not in str(found[1])
    assert "Plato" not in str(lookup.get_verse("Cato 1:1").get("suggestions"))
    assert lookup.get_verse("Cato 1:1")["suggestions"][0] in ("Marcus Cato", "Cato the Younger", "On Agriculture",
                                                              "Distichs of Cato")


def test_a_far_spelling_alike_is_no_match(books):
    assert books._author_works_node("cato the younger stuff") is None or \
        "Acts" not in books._author_works_node("cato the younger stuff")[0]
    found = books._author_works_node("cato the elder")
    assert found is None or "Acts of the Apostles" not in str(found)


def test_ptolemys_names(books, lookup):
    for q in ("ptolemy", "claudius ptolemy", "Claudius Ptolemaeus"):
        assert books._author_works_node(q)[0] == "Ptolemy", q
    assert lookup.get_verse("Claudius Ptolemy 1:1")["found"]                  # (his Tetrabiblos)


def test_whole_word_matches():
    from scripture_lookup import whole_word_matches
    names = ["Plato", "Marcus Cato", "Cato the Younger", "Catoptrics", "Comparison of Aristides and Marcus Cato"]
    assert whole_word_matches("cato", names) == ["Marcus Cato", "Cato the Younger",
                                                  "Comparison of Aristides and Marcus Cato"]
    assert whole_word_matches("marcus cato", names) == ["Marcus Cato", "Comparison of Aristides and Marcus Cato"]


def test_classical_is_greek_and_latin_by_kind(books):
    """No Perseus shelf: its authors filed by language and kind with the rest (the owner, 2026-11-01). Greek and
    Latin are what 🏛️ Classical opens to, not a second Classical inside it."""
    classical = dict(books.ROOT_BOOKS_TREE)["🏛️ Classical"]
    assert [name for name, _ in classical][:2] == ["🏛️ Greek", "🦅 Latin"]
    assert "🏛️ Classical" not in [name for name, _ in classical]
    greek, latin = dict(dict(books.BOOKS_TREE)["🏛️ Greek"]), dict(dict(books.BOOKS_TREE)["🦅 Latin"])
    assert "Thucydides" in dict(greek["Historians"]) and "Sophocles" in dict(greek["Drama"])
    assert "Tacitus" in dict(latin["Historians"]) and "Plautus" in dict(latin["Drama"])
    assert {"Aeneid", "Eclogues", "Georgics"} <= set(dict(latin["Epic"])["Virgil"])   # (beside the Aeneid)
    plutarch = dict(greek["Lives, Essays & Satire"])
    assert "Theseus" in plutarch["Plutarch: Parallel Lives"] and "Of Fate" in plutarch["Plutarch: Moralia"]
    assert len(books._author_works_node("plutarch")[1]) >= 141                  # (all of him, from every shelf)
    assert "More" not in greek and "More" not in latin                          # (every author placed)
