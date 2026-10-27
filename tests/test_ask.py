"""Asking the library (bot_commands/ask.py): the search that finds the passages, the check on the answer's
citations, and the day's allowance. No test reaches the paid API: the request is replaced by a fake reply."""
import asyncio

import pytest


@pytest.fixture(scope="module")
def ask(bot_module):
    from bot_commands import ask
    return ask


@pytest.fixture(scope="module")
def small_index(ask):
    return ask.Index(corpora=("apostolic_fathers",))           # (a small shelf: a full build takes ~20s)


def test_it_finds_passages_that_open(ask, small_index, lookup):
    found = ask.find_passages("What does Barnabas say about the two ways, of light and of darkness?",
                              index=small_index)
    assert found and len(found) <= ask.PASSAGES
    for p in found:
        assert lookup.get_verse(p["reference"])["found"], p["reference"]      # (each one !verse can open)
        assert len(p["text"]) <= max(ask.PASSAGE_CHARS) + 2
    books = [p["reference"].rsplit(" ", 1)[0] for p in found]
    assert all(books.count(b) <= ask.PER_BOOK for b in books)               # (not one book's eight verses)


def test_a_book_or_author_named_may_give_more(ask):
    assert ask._named("Enneads", ["Classical", "Platonic", "Plotinus"], "What does Plotinus say evil is?")
    assert ask._named("Epistle of Barnabas", ["Apostolic Fathers"], "what does the epistle of barnabas say")
    assert not ask._named("Enneads", ["Classical", "Platonic", "Plotinus"], "what is evil?")


def test_nothing_to_search_for(ask, small_index):
    assert ask.find_passages("what is the", index=small_index) == []         # (only common words)
    assert ask.find_passages("xyzzyplugh", index=small_index) == []


def test_citations_it_wasnt_given_are_taken_out(ask):
    passages = [{"reference": "Enneads 1.8:3", "text": "..."}, {"reference": "Phaedo 67e:1", "text": "..."}]
    text, cited = ask.checked("Evil is privation [Enneads 1.8:3], as Plato says [Republic 509b:1]; and death "
                              "frees the soul [Phaedo 67e:1] [Enneads 1.8:3].", passages)
    assert "Republic" not in text and "[Enneads 1.8:3]" in text
    assert cited == ["Enneads 1.8:3", "Phaedo 67e:1"]


def test_a_citation_without_brackets_still_counts(ask):
    """The second live answer wrote "In *Enneads* 1.8:1, evil is..." and its sources footer came out empty."""
    passages = [{"reference": "Enneads 1.8:1", "text": "..."}, {"reference": "Enneads 1.8:7", "text": "..."},
                {"reference": "Enneads 1.7:3", "text": "..."}]
    _, cited = ask.checked("In *Enneads* 1.8:7, the Kosmos is a blend. In *Enneads* 1.8:1, evil is absence.",
                           passages)
    assert cited == ["Enneads 1.8:7", "Enneads 1.8:1"]                     # (in the order the answer gives them)


def test_a_named_author_gets_only_their_passages(ask, small_index):
    found = ask.find_passages("What does the Epistle of Barnabas say about the two ways?", index=small_index)
    assert found and all(p["reference"].startswith("Epistle of Barnabas") for p in found)


def test_an_answer_is_one_request_with_the_passages(ask, small_index, monkeypatch):
    sent = []

    def fake(system, messages):
        sent.append(messages)
        return "Barnabas sets out two ways [Epistle of Barnabas 18:1] and a made-up one [Nowhere 1:1]."
    monkeypatch.setattr(ask, "_index", small_index)
    monkeypatch.setattr(ask, "_ask_claude", fake)
    text, cited = asyncio.run(ask.answer("the two ways of light and darkness", None, []))
    assert len(sent) == 1 and "Passages from the library" in sent[0][-1]["content"]
    assert "Nowhere" not in text


def test_without_a_key_it_cannot_reach_the_api(ask):
    with pytest.raises(RuntimeError):
        ask._ask_claude(ask.SYSTEM, [{"role": "user", "content": "hello"}])


def test_the_days_allowance(ask):
    usage = ask._usage()
    assert usage["count"] == 0 and usage["cap"] == ask.ASK_DEFAULT_CAP
    usage.update(count=7, cap=9)
    ask._save_usage(usage)
    assert ask._usage()["count"] == 7
    ask._save_usage({"day": "2000-01-01", "count": 99, "cap": 9})
    assert ask._usage() == {"day": ask.dt.date.today().isoformat(), "count": 0, "cap": 9}   # (a new day; cap kept)


def test_channels_are_off_until_opened(ask):
    assert ask.ask_channels(12345) == set()
