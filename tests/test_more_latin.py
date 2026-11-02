"""More Latin authors (2026-11-01, scripts/build_latin.py): Seneca's prose and tragedies, Pliny's letters, Petronius,
Ovid's Fasti, Statius, Valerius Flaccus, Hyginus, Fulgentius, Dares and Dictys."""
import pytest


@pytest.fixture(scope="module")
def books(bot_module):
    from bot_commands import books
    return books


def found(lookup, ref):
    res = lookup.get_verse(ref)
    assert res.get("found"), (ref, res.get("error") or res.get("suggestions"))
    return res


def test_poems_and_plays_by_line(lookup):
    """Passages keyed by their first line: a line inside one finds it."""
    assert "founder of the City" in found(lookup, "Fasti 1:30")["text"]                   # (lines 27-44)
    assert "Pelias" in found(lookup, "Argonautica 1:30")["text"]
    assert "Base hope is credulous" in found(lookup, "Thyestes 300")["text"]
    assert "Ghost of Thyestes" in found(lookup, "Agamemnon (Seneca) 1:5")["text"]


def test_moral_letters_by_section(lookup):
    """Gummere's section numbers aren't at every paragraph: section 2 is in the passage from 1."""
    res = found(lookup, "Moral Letters 1:2")
    assert "Moral Letters to Lucilius" in str(res.get("reference"))
    assert "On Saving Time" in res["text"]


def test_seneca_against_the_greek_plays(lookup):
    """Euripides' and Aeschylus's plays keep their titles; Seneca's are named for him where they'd clash."""
    assert "Phoenician" in str(found(lookup, "Phoenissae 1:1").get("reference"))          # (Euripides)
    assert "Oedipus" in found(lookup, "Phoenissae (Seneca) 1:1")["text"]
    assert "Oedipus" in found(lookup, "Seneca Phoenissae 1:1")["text"]
    assert "Medea" in found(lookup, "Medea (Seneca) 1:1")["text"]


def test_latin_titles(lookup):
    assert "Novatus" in found(lookup, "de ira 2.1:1")["text"]
    assert "Nature" in found(lookup, "de brevitate vitae 2:1")["text"]
    assert "Admetus" in found(lookup, "Hyginus 50:1")["text"]
    assert "Laomedon" in found(lookup, "Dares 3:1")["text"]
    assert "*To Catilius Severus*" in found(lookup, "Pliny the Younger 16:1")["text"]


def test_hyginus(lookup):
    assert "*Themisto*\nAthamas" in found(lookup, "Fabulae 1:1")["text"]                       # (not "1 THEMISTO:")
    assert "*Phaethon*" in found(lookup, "Fabulae 152:2")["text"]                         # (Grant's 152A)
    assert "missing" in found(lookup, "Fabulae 207:1")["text"]                           # (lost fables: a note)
    assert "Great Bear" in found(lookup, "Astronomica 2.1:1")["text"]


def test_the_latin_shelves(books):
    latin = dict(dict(books.BOOKS_TREE)["🦅 Latin"])
    assert {"Thebaid", "Achilleid"} <= set(dict(latin["Epic"])["Statius"])
    assert "Fasti" in dict(latin["Epic"])["Ovid"] and "Metamorphoses" in dict(latin["Epic"])["Ovid"]
    assert "Thyestes" in dict(latin["Drama"])["Seneca"] and "Plautus" in dict(latin["Drama"])
    assert "Moral Letters to Lucilius" in dict(latin["Philosophy"])["Seneca"]
    assert "Apocolocyntosis" in dict(latin["Novels & Satire"])["Seneca"]                  # (Perseus's, kept)
    assert "Satyricon" in dict(latin["Novels & Satire"])["Petronius"]
    assert set(dict(latin["Myth & Legend"])) == {"Hyginus", "Fulgentius", "Dares Phrygius", "Dictys Cretensis"}
    assert "Letters of Pliny" in dict(latin["Letters & Essays"])["Pliny the Younger"]
    assert "Natural History" in dict(latin["Science"])["Pliny the Elder"]


def test_natural_history(lookup):
    assert "*Of God*" in found(lookup, "Natural History 2.5")["text"]
    assert "Natural History 7.2" in str(found(lookup, "pliny the elder 7.2").get("reference"))
