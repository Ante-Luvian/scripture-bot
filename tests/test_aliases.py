"""The book-name aliases."""
import ast
import collections
from pathlib import Path


def test_no_alias_points_two_ways():
    """A dict literal silently keeps the last of two equal keys: "pol" once
    meant Polycarp in one place and Aristotle's Politics in another."""
    tree = ast.parse((Path(__file__).parent.parent / "scripture_lookup.py").read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        target = node.target if isinstance(node, ast.AnnAssign) else (node.targets[0] if isinstance(node, ast.Assign) else None)
        if getattr(target, "id", None) == "ALIASES":
            seen = collections.defaultdict(set)
            for k, v in zip(node.value.keys, node.value.values):
                if isinstance(k, ast.Constant):
                    seen[k.value].add(getattr(v, "value", None))
            assert not {k: v for k, v in seen.items() if len(v) > 1}


def test_short_names(lookup):
    assert lookup._resolve_book("Pol")[1] == "Polycarp to the Philippians"
    assert lookup.get_verse("Pol Phil 2:1")["found"]
    assert lookup._resolve_book("1clement")[1] == "1 Clement"
    assert lookup._resolve_book("Politics")[1] == "Politics"
    assert lookup._resolve_book("First Epistle Clement")[1] == "First Epistle"
    from scripture_lookup import ALIASES
    assert ALIASES["odes"] == "Odes"          # the Septuagint book (fetched as a translation), not the Odes of Solomon
    assert lookup._resolve_book("Enchiridion") == ("patristics", "Enchiridion")   # Augustine's
    assert lookup._resolve_book("Epictetus")[1] == "Enchiridion of Epictetus"


# Book names that were already in two collections before this check existed
KNOWN_SHARED = {"Apology", "Divine Names", "Epistle of Barnabas", "Job", "Joshua", "Judith", "Letters",
                "Mystical Theology", "On the Ecclesiastical Hierarchy", "On the Heavenly Hierarchy",
                "On the Mysteries", "On the Soul", "Tobit"}


def test_new_books_do_not_share_a_name(lookup):
    """Two collections with the same book name hide one of them from !verse."""
    where = collections.defaultdict(list)
    for corpus, books in lookup._data.items():
        for book in books:
            where[book].append(corpus)
    assert {b for b, c in where.items() if len(c) > 1} <= KNOWN_SHARED
