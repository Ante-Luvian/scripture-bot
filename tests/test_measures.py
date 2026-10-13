"""!measure: every quotation is checked against the local Easton's and KJV."""
import asyncio
import json
import re
from fractions import Fraction

import pytest

from core import ROOT


@pytest.fixture(scope="module")
def measures(bot_module):
    from bot_commands import measures
    return measures


@pytest.fixture(scope="module")
def easton():
    entries = json.loads((ROOT / "data" / "dictionary" / "bible_dictionary.json").read_text(encoding="utf-8"))["entries"]
    return {k: " ".join(d["text"] for d in e["definitions"] if d["source"] == "EAS") for k, e in entries.items()}


def _kjv(ref):
    from core import lookup
    result = lookup.get_verse(ref)
    assert result.get("found"), ref
    return result["text"]


def test_easton_quotations(measures, easton):
    for key, u in measures.UNITS.items():
        if u.get("easton"):
            entry, words = u["easton"]
            assert words in easton.get(entry, ""), (key, entry, words)


def test_verse_quotations(measures):
    for key, u in measures.UNITS.items():
        quotes = [u["example"]] + ([u["relation"][1:]] if u.get("relation") else [])
        for ref, words in quotes:
            assert words in _kjv(ref), (key, ref, words)


def test_talent_is_three_thousand_shekels():
    # Exodus 38:25-26: 603,550 men at half a shekel = 100 talents and 1,775 shekels
    assert "six hundred thousand and three thousand and five hundred and fifty men" in _kjv("Exodus 38:26")
    assert (603550 / 2 - 1775) / 100 == 3000


def test_numbers(measures):
    n = measures.words_to_number
    assert n("six hundred thousand and three thousand and five hundred and fifty".split()) == 603550
    assert n("a thousand seven hundred and threescore and fifteen".split()) == 1775
    assert n("five and twenty".split()) == 25 and n(["fourscore"]) == 80 and n(["an"]) == 1
    r = measures.read_amount
    assert r("300") == 300 and r("2.5") == Fraction(5, 2) and r("half a") == Fraction(1, 2)
    assert r("the fourth part of an") == Fraction(1, 4) and r("an half") == Fraction(1, 2)


def test_queries(measures):
    assert measures.parse_query("300 cubits") == (300, ["cubit"])
    assert measures.parse_query("three hundred cubits") == (300, ["cubit"])
    assert measures.parse_query("half a shekel") == (Fraction(1, 2), ["shekel"])
    assert measures.parse_query("pound") == (1, ["maneh", "litra", "mina"])
    assert measures.parse_query("sabbath day's journey") == (1, ["sabbath"])
    assert measures.parse_query("2 mites") == (2, ["mite"])
    assert measures.parse_query("nonsense") is None


def test_conversions(measures):
    assert measures.convert_line(Fraction(300), "cubit") == "**300 × Cubit** ≈ 154 m (506 ft)"
    assert "1/40 of a denarius" in measures.convert_line(Fraction(2), "mite")
    assert "1,000 days' wages" in measures.convert_line(Fraction(10), "mina")
    assert "about $7.01–$7.48 today" in measures.convert_line(Fraction(1), "denarius")   # 7½d.–8d. in 1897
    assert measures.size_text("day", Fraction(1)) == "25.7 km (16 miles) to 32.2 km (20 miles)"


def test_judas_silver_is_zechariahs(measures):
    assert "thirty pieces of silver" in _kjv("Matthew 27:9") and "thirty pieces of silver" in _kjv("Zechariah 11:12")
    embed = measures.verse_embed("Matthew 26:15", _kjv("Matthew 26:15"),
                                 measures.measurements_in(_kjv("Matthew 26:15"), "Matthew 26:15"))
    assert "Zechariah 11:12–13" in embed.description
    assert "as silver money: 120 denarii" in embed.description
    assert '“shekel” in R.V.' in measures_easton_stater()


def measures_easton_stater():
    entries = json.loads((ROOT / "data" / "dictionary" / "bible_dictionary.json").read_text(encoding="utf-8"))["entries"]
    return entries["STATER"]["definitions"][0]["text"]


def test_parable_talents_are_money(measures):
    embed = measures.verse_embed("Matthew 25:15", _kjv("Matthew 25:15"),
                                 measures.measurements_in(_kjv("Matthew 25:15"), "Matthew 25:15"))
    assert "as silver money: 60,000 denarii" in embed.description


def test_penny_value_is_eastons(easton):
    assert "about 7 1/2d. or 8d. of our present money" in easton["PENNY"]


@pytest.mark.parametrize("ref, expected", [
    ("Genesis 6:15", [("three hundred cubits", 300, "cubit"), ("fifty cubits", 50, "cubit"), ("thirty cubits", 30, "cubit")]),
    ("Exodus 30:13", [("half a shekel", Fraction(1, 2), "shekel"), ("a shekel", 1, "shekel"),
                      ("twenty gerahs", 20, "gerah"), ("an half shekel", Fraction(1, 2), "shekel")]),
    ("Hosea 3:2", [("fifteen pieces of silver", 15, "shekel"), ("an homer", 1, "homer"), ("an half homer", Fraction(1, 2), "homer")]),
    ("Luke 19:13", [("ten pounds", 10, "mina")]),
    ("John 12:3", [("a pound", 1, "litra")]),
    ("Ezra 2:69", [("threescore and one thousand drams", 61000, "dram"), ("five thousand pound", 5000, "maneh")]),
    ("1 Samuel 17:4", [("six cubits", 6, "cubit"), ("a span", 1, "span")]),
    ("Exodus 3:18", [("three days' journey", 3, "day")]),
    ("Acts 19:19", [("fifty thousand pieces of silver", 50000, "drachma")]),
    ("Mark 12:42", [("two mites", 2, "mite"), ("a farthing", 1, "quadrans")]),
    ("Matthew 10:29", [("a farthing", 1, "assarion")]),
    ("Matthew 11:7", []),                            # "a reed shaken with the wind" is not a measurement
    ("Matthew 26:15", [("thirty pieces of silver", 30, "shekel")]),   # Zechariah's shekels (Matthew 27:9)
])
def test_verses(measures, ref, expected):
    found = [(w, a, k) for w, a, k, _ in measures.measurements_in(_kjv(ref), ref)]
    assert found == expected


def test_or_range(measures):
    (words, amount, key, low), = measures.measurements_in(_kjv("John 2:6"), "John 2:6")
    assert (words, amount, key, low) == ("two or three firkins", 3, "firkin", 2)


def test_command(measures, fake_ctx):
    asyncio.run(measures.send_measure(fake_ctx, "Genesis 6:15"))
    embed = fake_ctx.sent[-1]["embed"]
    assert embed.title == "📏 Genesis 6:15" and "**three hundred cubits** ≈ 154 m" in embed.description
    asyncio.run(measures.send_measure(fake_ctx, "talent"))
    assert fake_ctx.sent[-1]["embed"].title == "📏 Talent"
    asyncio.run(measures.send_measure(fake_ctx, ""))
    assert len(fake_ctx.sent[-1]["embed"].fields) == len(measures.KINDS)
    for u in measures.UNITS.values():
        assert re.match(r"^[^\n]+$", u["name"])
