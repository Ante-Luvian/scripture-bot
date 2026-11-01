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


def test_an_answer_is_a_plan_then_one_request_with_the_passages(ask, small_index, monkeypatch):
    sent = []

    def fake(system, messages, max_tokens=2000):
        sent.append((system, messages))
        if system == ask.PLAN:
            return ('{"asking": "what Barnabas teaches of the two ways", "shelves": ["fathers"], '
                    '"references": ["Nowhere 99:99"], "searches": ["way of light"]}')
        return "Barnabas sets out two ways [Epistle of Barnabas 18:1] and a made-up one [Nowhere 1:1]."
    monkeypatch.setattr(ask, "_index", small_index)
    monkeypatch.setattr(ask, "_ask_claude", fake)
    text, cited = asyncio.run(ask.answer("the two ways of light and darkness", None, []))
    assert len(sent) == 2 and "Passages from the library" in sent[1][1][-1]["content"]
    assert "What it asks: what Barnabas teaches of the two ways" in sent[1][1][-1]["content"]   # (the plan's reading)
    assert "Nowhere" not in text and "Nowhere" not in sent[1][1][-1]["content"]   # (a reference the library hasn't)


def test_a_question_about_christs_words_keeps_to_the_bible(ask, small_index):
    """"Does Christ claim to be God?" was answered from Hilary: the search had found no Gospel verse, and the
    Fathers' commentary shouldn't have been opened for what Christ himself said."""
    plan = {"corpora": ask.SHELVES["bible"], "references": ["John 10:30", "John 8:58", "Didache 1:1"],
            "searches": ["I and my Father"]}
    found = ask.gather("does christ claim to be god", None, plan, index=small_index)
    refs = [p["reference"] for p in found]
    assert refs[:2] == ["John 10:30", "John 8:58"] and "Didache 1:1" not in refs     # (not the Fathers' shelf)
    assert "I and my Father are one" in found[0]["text"] and "**[" not in found[0]["text"]


class _Reply:
    def __init__(self, data):
        self.data = data

    def read(self):
        return __import__("json").dumps(self.data).encode()

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def test_the_jewish_shelf_is_searched_on_sefaria(ask, lookup, monkeypatch):
    """Its texts are online, not indexed: Sefaria's search finds them, each read as !verse would show it, once."""
    hits = {"hits": {"hits": [{"_source": {"ref": r}} for r in ("Pirkei Avot 4:1", "Pirkei Avot 4:1", "Nowhere 1:1")]}}
    asked = []
    monkeypatch.setattr(ask.urllib.request, "urlopen", lambda req, timeout=0: asked.append(req) or _Reply(hits))
    monkeypatch.setattr(lookup, "get_verse", lambda ref: {"found": ref != "Nowhere 1:1", "reference": ref,
                                                          "text": "**[1]** Ben Zoma says: Who is wise?",
                                                          "tradition": "jewish"})
    found = ask.sefaria_passages(["who is wise"], None)
    assert [p["reference"] for p in found] == ["Pirkei Avot 4:1"] and found[0]["text"].startswith("(1) Ben Zoma")
    assert b"Talmud/Bavli/" in asked[0].data                                  # (the bot's shelf only)


def test_sefaria_down_means_an_answer_without_it(ask, monkeypatch):
    def down(*a, **k):
        raise OSError("no route")
    monkeypatch.setattr(ask.urllib.request, "urlopen", down)
    assert ask.sefaria_passages(["who is wise"], None) == []


def test_hadith_and_quran_are_in_the_index(ask, lookup):
    index = ask.Index(corpora=("quran", "hadith"))
    if not index.hadith:
        pytest.skip("hadith not downloaded here (python scripts/fetch_hadith.py)")
    found = ask.find_passages("the deeds are judged by intentions", index=index, corpora=("hadith",))
    assert found and found[0]["reference"].split(" ")[-1].isdigit()
    assert lookup.get_verse(found[0]["reference"])["found"]                   # (one !verse opens)
    assert ask.find_passages("Jesus son of Mary", index=index, corpora=("quran",))


def test_a_plan_that_cant_be_had_searches_everywhere(ask, monkeypatch):
    monkeypatch.setattr(ask, "_ask_claude", lambda *a, **k: "not json")
    assert ask._plan("anything", []) == {"corpora": ask.CORPORA, "references": [], "searches": []}


def test_an_answer_that_ran_out_of_room_ends_on_a_whole_sentence(ask):
    cut = ("He is a failed student [Sotah 47a].\n\nThe Jerusalem Talmud also tells of healing in his name. "
           "A grandson of R. Joshua ben Levi")
    assert ask._to_last_sentence(cut).endswith("healing in his name.")
    assert ask._to_last_sentence("One [Sotah 47a].\n\nA grandson of") == "One [Sotah 47a]."


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
