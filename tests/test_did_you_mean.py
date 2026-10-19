"""A book name the bot doesn't know is no longer answered silently with whatever is closest: "Against
Heresies" was Cicero's Against Verres, "Moralia" Xenophon's Memorabilia, "Ecclesiasticus"
Ecclesiastes, "Gospel of John" the Gospel of Thomas, "First Samuel" 2 Samuel. A slip of a letter or
two is still read as the book; anything further asks, with a button for each likely book."""
import asyncio

import pytest


@pytest.mark.parametrize("ref, expect", [
    ("Jhon 3:16", "John 3:16"), ("1 Jhon 1:9", "1 John 1:9"), ("Genisis 1:1", "Genesis 1:1"),
    ("Mathew 5:3", "Matthew 5:3"), ("Phillipians 4:13", "Philippians 4:13"), ("Duteronomy 6:4", "Deuteronomy 6:4"),
    ("Odysey 1:1", "Odyssey 1:1–4"), ("Confesions 1.1:1", "Confessions 1.1:1"),
    # other names, now aliases (the closest-name guess had them wrong)
    ("Ecclesiasticus 1:1", "Sirach 1:1"), ("Song of Songs 2:1", "Song of Solomon 2:1"),
    ("Acts of the Apostles 2:1", "Acts 2:1"), ("Gospel of John 3:16", "John 3:16"),
    ("the Gospel according to St Luke 2:1", "Luke 2:1"), ("First Samuel 3:10", "1 Samuel 3:10"),
    ("2nd Timothy 3:16", "2 Timothy 3:16"), ("Tobias 1:1", "Tobit 1:1"),
])
def test_slips_and_other_names_still_find_the_book(lookup, ref, expect):
    result = lookup.get_verse(ref)
    assert result["found"] and result["reference"] == expect


@pytest.mark.parametrize("ref, first_guess", [
    ("Moralia 1:1", "Memorabilia 1:1"),
    ("Retractions 1:1", "Orations 1:1"),
    ("Corinthians 13:4", None),                    # the first or the second? ask
])
def test_a_guess_too_far_asks(lookup, ref, first_guess):
    result = lookup.get_verse(ref)
    assert not result["found"] and "don't have a book called" in result["error"]
    assert result["did_you_mean"] and all(r.endswith(ref.split(" ", 1)[1].split(" ")[-1]) for r in result["did_you_mean"])
    if first_guess:
        assert result["did_you_mean"][0] == first_guess
    if ref.startswith("Corinthians"):
        assert {"1 Corinthians 13:4", "2 Corinthians 13:4"} <= set(result["did_you_mean"])


def test_a_random_passage_from_an_unknown_book_asks_too(lookup):
    assert lookup.random_verse_from_book("Moralia").get("did_you_mean")
    assert lookup.random_verse_from_book("Provebs")["found"]


def test_the_reply_has_a_button_for_each_guess(bot_module, fake_ctx):
    import core
    result = core.lookup.get_verse("Moralia 1:1")
    asyncio.run(core._send_result(fake_ctx, result))
    sent = fake_ctx.sent[-1]
    labels = [b.label for b in sent["view"].children]
    assert labels == result["did_you_mean"][:3] and "Did you mean?" in str(sent["embed"].fields[0].name)
