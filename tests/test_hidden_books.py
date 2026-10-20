"""Easter eggs (scripture_lookup.HIDDEN_BOOKS: the Sermons of Vivec) open for whoever knows the name,
and never show up when looking: not in !books, a search, a did-you-mean, the /verse autocomplete or a
random draw."""
import random


def test_vivec_opens_by_name(lookup):
    assert lookup.get_verse("Vivec 1:1")["found"]
    assert lookup.get_verse("Lessons of Vivec 1:1")["found"]


def test_vivec_is_never_listed(lookup):
    from bot_commands import books
    from bot_commands.slash import book_suggestions
    from scripture_lookup import ALIASES
    leaves = list(books._leaves(books.BOOKS_TREE))
    assert not any("Vivec" in leaf for leaf in leaves)
    text = lookup._data[lookup._resolve_exact("Vivec")[0]]["Vivec"]["1"]["1"]
    phrase = " ".join(text.split()[:6])
    assert not any(r["book"] == "Vivec" for r in lookup.search(phrase, limit=50)[0])
    assert not any(h.get("book") == "Vivec" for hits in lookup.search_by_corpus(phrase).values() for h in hits)
    assert "Vivec" not in book_suggestions("v", limit=200) + book_suggestions("viv")
    assert "Vivec" not in lookup._suggest_books("Vivek")
    assert ALIASES.get("sermon") != "Vivec"
    rng = random.Random(1)
    assert all(lookup.random_verse(rng)["book"] != "Vivec" for _ in range(3000))


def test_a_shelf_with_books_and_subshelves_shows_both():
    """Mesopotamian holds Enuma Elish and the Gilgamesh sub-shelf; the browser used to draw only the
    sub-shelf, so Enuma Elish couldn't be found in !books."""
    from bot_commands import books
    label, node = books._find_node(books.BOOKS_TREE, "Mesopotamian")
    view = books.BooksView([("Books", books.BOOKS_TREE, "tree"), (label, node, "tree")])
    labels = [getattr(c, "label", "") for c in view.children]
    assert "Enuma Elish" in labels and any("Gilgamesh" in l for l in labels)
