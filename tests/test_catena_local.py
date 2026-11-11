"""The Fathers on a verse from the library (scripts/build_catena_index.py, bot_commands/catena_local.py)."""
import pytest


@pytest.fixture(scope="module")
def C(bot_module):
    from bot_commands import catena_local
    return catena_local


def test_a_gospel_verse_has_the_catena_aurea_first(C):
    s = C.sections("John", 3, 16)
    assert s and s[0][0].endswith("(in the Catena Aurea)") and "Aquinas, Catena Aurea on John" in s[0][1]


def test_augustines_psalms_are_renumbered(C):
    """Augustine's Expositions number the Psalms as the Latin Bible does (his 109 is the KJV's 110)."""
    s = C.sections("Psalms", 110, 1)
    assert s[0][0] == "Augustine" and "The Lord said unto my Lord" in s[0][1]
    assert not any("The Lord said unto my Lord" in body and who == "Augustine"
                   for who, body in C.sections("Psalms", 109, 1))


def test_quotations_one_a_work_and_short(C):
    s = C.sections("Isaiah", 53, 5)
    works = [body.rsplit("— *", 1)[1] for _, body in s]
    assert len(works) == len(set(works)) and all(len(body) < 3200 for _, body in s)
