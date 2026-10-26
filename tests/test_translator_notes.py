"""Cleanup of 2026-10-26: translators' notes served as the author's text, titles two collections share, and
Julian's misattributed translations. Each was found by a user asking for a verse."""
import re


def _text(lookup, book: str) -> str:
    corpus, name = lookup._resolve_book(book)[0], lookup._resolve_book(book)[1]
    chapters = lookup._data[corpus][name]
    return "\n".join(v for ch in chapters.values() for v in ch.values())


def test_taylors_notes_are_not_the_authors_text(lookup):
    """`!verse iamblichus` gave "On the Mysteries 138:6", Taylor's note on Galen. Taylor's books end with
    the author's last words now."""
    mysteries = _text(lookup, "On the Mysteries")
    assert not re.search(r"\bGale\b|De Ingenio Sanitatis|Roger Bacon", mysteries)
    last = lookup._data["classical"]["On the Mysteries"]
    assert list(last)[-1] == "104" and "immutable guard of true conceptions" in list(last["104"].values())[-1]
    assert "Gaffarel" not in _text(lookup, "Theology of Plato")
    cave = _text(lookup, "On the Cave of the Nymphs")
    assert "This Cronius" not in cave and cave.rstrip().endswith("the present Cave of the Nymphs.")


def test_no_page_numbers_in_porphyry(lookup):
    for book in ("On Abstinence", "On the Cave of the Nymphs", "Letter to Marcella", "Auxiliaries to the Intelligibles"):
        assert not re.search(r"\|\d", _text(lookup, book)), book


def test_a_title_two_collections_share_reaches_both(lookup):
    """Plato's Apology and Rufinus's, Aristotle's On the Soul and Tertullian's: each one opens, each with its
    own credit (Aristotle was credited to Tertullian's translator)."""
    seen = {}
    for corpus, books in lookup._data.items():
        for title, chapters in books.items():
            if title in seen and seen[title][1] != chapters:
                raise AssertionError(f"{title}: in {seen[title][0]} and {corpus}, different texts, one unreachable")
            seen.setdefault(title, (corpus, chapters))
    assert lookup.get_verse("On the Soul 1:1")["source"] == "various translators"                 # Aristotle's
    assert lookup.get_verse("On the Soul (Tertullian) 1:1")["source"].startswith("trans. Holmes")
    assert lookup.get_verse("On the Mysteries 1:1")["source"] == "trans. Thomas Taylor (1821)"
    assert "Ambrose" in lookup.get_verse("On the Mysteries (Ambrose) 1:1")["text"]
    assert lookup.get_verse("Letters (Theodoret) 1:1")["found"]
    assert lookup.get_verse("Epistle of Barnabas 1:1")["source"] == "trans. J. B. Lightfoot"
    assert lookup.get_verse("Epistle of Barnabas (Roberts and Donaldson) 1:1")["text"].count("All hail")


def test_julian(lookup):
    """King's translation (1888), not Taylor's; Wright's Against the Galilaeans; no "Caesars" that was really
    Taylor's hymn to the Sun; the Sun oration's opening restored."""
    assert lookup.get_verse("Hymn to King Helios 1:1")["text"].count("It is my opinion that the present subject")
    assert lookup._book_sources["Hymn to King Helios"] == "trans. C. W. King (1888)"
    assert lookup._book_sources["Against the Galilaeans"] == "trans. Wilmer Cave Wright (1923)"
    assert "The Caesars" not in lookup._data["classical"]
