"""The medieval and Catholic Reformation classics (scripts/build_catholic_classics.py, 2026-11-10): Anselm, Francis
and the Little Flowers, Bernard, Bonaventure, Eckhart, Catherine; Trent, Ignatius, Teresa, John of the Cross,
de Sales, Pascal."""
import pytest


@pytest.fixture(scope="module")
def books(bot_module):
    from bot_commands import books
    return books


def text(lookup, ref):
    found = lookup.get_verse(ref)
    assert found.get("found"), (ref, found.get("suggestions"))
    return found["text"]


def test_works_by_their_own_divisions(lookup):
    assert "fool hath said in his heart" in text(lookup, "Proslogium 2:1")
    assert "neither necessity nor impossibility" in text(lookup, "Cur Deus Homo 2.18:1")    # (Deane's 18 (a) and (b))
    assert "spiritual marriage" in text(lookup, "Interior Castle 7.2:1")
    assert "Session VI" in text(lookup, "Council of Trent 6:1")
    assert "Stanzas XX and XXI" in text(lookup, "Spiritual Canticle 20:1")
    assert "Part I" in text(lookup, "Introduction to the Devout Life 1.1:1")
    assert "Infinite—nothing" in text(lookup, "Pensées 233:1")                    # (the wager, by its number)
    assert "Infinite—nothing" in text(lookup, "Pascal 233:1")


def test_francis_in_his_own_words(lookup):
    """Robinson's introductions are left out: each piece starts with Francis's text."""
    assert text(lookup, "Writings of St. Francis 7:1").split("\n")[1].startswith("The Lord gave to me, Brother Francis")
    canticle = text(lookup, "Writings of St. Francis 19:1")
    assert "Most high, omnipotent, good Lord,\nPraise, glory" in canticle      # (its first stanza, line by line)
    for n in range(1, 21):
        assert "Robinson" not in text(lookup, f"Writings of St. Francis {n}")


def test_no_footnote_marks_or_titles_again(lookup):
    data = {**lookup._data["medieval"], **lookup._data["reformation"]}
    for book in ("Writings of St. Francis", "Life of St. Teresa", "Interior Castle", "Spiritual Exercises",
                 "Dark Night of the Soul", "Ascent of Mount Carmel", "In Behalf of the Fool"):
        for ch, verses in data[book].items():
            for v, t in verses.items():
                assert "brothers. 8 Wherefore" not in t and "‑‑" not in t, (book, ch, v)
                assert not t.startswith(("APPENDIX", "ANSELM’S APOLOGETIC")), (book, ch, v)
    first = data["Dark Night of the Soul"]["2.6"]
    assert first["1"].count("Of other kinds of pain") == 1                      # (its title once, not twice)


def test_on_the_shelves(books):
    medieval = dict(dict(books.BOOKS_TREE)["🏰 Medieval Christianity"])
    assert "Cur Deus Homo" in dict(medieval["Theologians"])["Anselm of Canterbury"]
    assert "Little Flowers of St. Francis" in dict(medieval["Franciscans"])["The Little Flowers"]
    assert ("Bernard of Clairvaux", ["On Loving God"]) in medieval["Mystics"]
    catholic = dict(dict(dict(books.BOOKS_TREE)["🕯️ Reformation and After"])["Catholic Writers"])
    assert catholic["John of the Cross"] == ["Ascent of Mount Carmel", "Dark Night of the Soul", "Spiritual Canticle"]
    assert catholic["Blaise Pascal"] == ["Pensées"]
    assert books._author_works_node("teresa of ávila")
