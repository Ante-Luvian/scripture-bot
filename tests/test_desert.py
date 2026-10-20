"""!desert: sayings of the Desert Fathers, at random, by father, by topic, by number, by words."""
import re

import pytest


@pytest.fixture(scope="module")
def desert(bot_module):
    from bot_commands import desert
    return desert


def test_every_saying_is_there(desert):
    s = desert.sayings()
    assert sorted(map(int, s["1"])) == list(range(1, 636))
    assert sorted(map(int, s["2"])) == [n for n in range(1, 707) if n != 133]      # (Budge skips 133)


def test_topics_cover_both_books_without_gaps(desert):
    t = desert.topics()
    assert len(t) == 18
    for book in ("1", "2"):
        mine = [x for x in t if x[0] == book]
        assert mine[0][1] == 1
        assert all(a[2] + 1 == b[1] for a, b in zip(mine, mine[1:]))
    assert desert.topic_of("1", 230) == "Of Patient Endurance"
    assert desert.find_topic("humility") is not None
    assert desert.topics()[desert.find_topic("humility")][3].startswith("Of Humility")
    assert desert.find_topic("topic 6") == 5


def test_fathers(desert):
    f = desert.fathers()
    assert next(iter(f)) == "Poemen"                       # the most sayings
    assert "Abbâ" not in f and "Christ" not in f
    assert desert.find_father("poemen") == "Poemen"
    assert desert.find_father("Abba Arsenius") == "Arsenius"
    assert desert.find_father("Pambo") == "Pambô"          # without the accent
    assert desert.find_father("Panbô") is None or desert.find_father("Panbô") == "Pambô"
    assert desert.find_father("asdfghjkl") is None


def test_a_father_draws_only_his_sayings(desert):
    for book, n in desert.pool("f:Sisoes"):
        assert "Sisoes" in desert.sayings()[book][str(n)]


def test_words(desert):
    found = desert.pool("w:ten lamps of fire")
    assert ("1", 303) in found


def test_message_pages_a_long_saying_without_losing_any(desert):
    longest = max(((b, int(n)) for b, vs in desert.sayings().items() for n in vs),
                  key=lambda k: len(desert.sayings()[k[0]][str(k[1])]))
    text = desert.body(desert.sayings()[longest[0]][str(longest[1])])
    parts = desert.pages(text)
    assert len(parts) > 1 and all(len(p) <= 4096 for p in parts)
    assert re.sub(r"\s+", "", "".join(parts)) == re.sub(r"\s+", "", text)
    m = desert.message(*longest)
    assert m["embed"].description == parts[0]
    assert len(m["view"].children) == 3                    # ◀ ▶ 🎲


def test_heading_is_left_out_of_the_saying(desert):
    m = desert.message("1", 183)
    assert not m["embed"].description.startswith("*")
    assert m["embed"].footer.text == "Patient Endurance · Budge (1907)"
    assert desert.brief(desert.topic_of("1", 1)) == "Flight from Men"
    assert len(desert.SHORT) == len(desert.topics())
    assert desert.find_topic("hospitality") == 8
    assert len(m["embed"].footer.text) < 60


def test_button_ids_fit(desert):
    m = desert.message("2", 256, spec="w:" + "x" * 40)
    assert all(len(b.custom_id) <= 100 for b in m["view"].children)
