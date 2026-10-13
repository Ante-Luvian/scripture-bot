"""!harmony: Robertson's harmony of the Gospels."""
import asyncio

import pytest


@pytest.fixture(scope="module")
def ha(bot_module):
    from bot_commands import harmony
    return harmony


def test_the_harmony_is_complete(ha):
    s = ha.sections()
    assert len(s) == 185 and s[0]["section"] == "1" and s[-1]["section"] == "184"
    assert all(sec["refs"] for sec in s)


def test_every_passage_is_in_the_kjv(ha):
    from core import lookup
    for sec in ha.sections():
        for r in sec["refs"]:
            for p in ha.pieces(r["ref"]):
                assert lookup.get_verse(p).get("found"), (sec["section"], p)


def test_pieces(ha):
    assert ha.pieces("John 11:55-12:1, 9-11") == ["John 11:55-12:1", "John 12:9-11"]
    assert ha.pieces("Luke 22:14-16, 24-30") == ["Luke 22:14-16", "Luke 22:24-30"]
    assert ha.pieces("Matthew 5-7") == ["Matthew 5-7"]


def test_feeding_the_five_thousand(ha):
    [five] = ha.search("feeding five thousand") or ha.search("five thousand")
    assert ha.told_by(five) == "Told by all four Gospels"
    assert [r["book"] for r in five["refs"]] == ["Mark", "Matthew", "Luke", "John"]
    assert ha.search("5000") == [five]
    assert five in ha.search("John 6:10") and five in ha.search("Mark 6:41")


def test_popular_names(ha):
    from core import lookup
    for name, verse in ha.POPULAR.items():
        assert lookup.get_verse(verse).get("found"), verse
        found = ha.search(name)
        assert 1 <= len(found) <= 2, (name, [s["title"] for s in found])   # a verse may close one event and open the next
    assert "bread and drinking wine" in ha.search("Last Supper")[0]["title"]
    assert "three great parables" in ha.search("prodigal son")[0]["title"].lower() or \
        "Luke 15" in ha.search("prodigal son")[0]["refs"][0]["ref"]


def test_by_number_and_single_gospel(ha):
    [s] = ha.search("1")
    assert s["refs"] == [{"book": "Luke", "ref": "Luke 1:1-4"}] and ha.told_by(s) == "Only in Luke"
    assert ha.search("Romans 8:28") == [] and ha.sections_for("Romans 8:28") is None


def test_harmony_command(ha, fake_ctx):
    asyncio.run(ha.send_harmony(fake_ctx, "Mark 6:41"))
    sent = fake_ctx.sent[-1]
    assert sent["embed"].title.endswith("Feeding of the five thousand")
    assert {f.name.split()[0] for f in sent["embed"].fields} == {"Mark", "Matthew", "Luke", "John"}
    labels = [c.item.label for c in sent["view"].children]
    assert "◀ Event before" in labels and "Event after ▶" in labels and "Read John 6:1-13" in labels
    asyncio.run(ha.send_harmony(fake_ctx, "zzqx"))
    assert "couldn't find" in fake_ctx.sent[-1]["content"]
