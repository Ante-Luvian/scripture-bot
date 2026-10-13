"""!tree: family tree pictures and lines of descent."""
import asyncio

import pytest
from PIL import Image


@pytest.fixture(scope="module")
def pp(bot_module):
    from bot_commands import people
    return people


def _names(pp, line):
    return [pp.data()["people"][s]["name"] for s in line]


def test_abraham_to_david(pp):
    line = pp.descent(pp.find("people", "Abraham"), pp.find("people", "David"))
    assert [n.split(" (")[0] for n in _names(pp, line)] == [
        "Abraham", "Isaac", "Jacob", "Judah", "Pharez", "Hezron", "Ram", "Amminadab", "Nahshon",
        "Salmon", "Boaz", "Obed", "Jesse", "David"]


def test_lines_run_through_fathers(pp):
    # Terah -> Abraham -> Isaac, not Terah -> Sarah (his daughter, Genesis 20:12) -> Isaac
    line = _names(pp, pp.descent(pp.find("people", "Adam"), pp.find("people", "Jesus")))
    assert line[0] == "Adam" and line[-1] == "Jesus Christ" and "Abraham" in line and "Sarah" not in line


def test_no_line(pp):
    assert pp.descent(pp.find("people", "Ruth"), pp.find("people", "Moses")) is None


def test_family_chart_draws(pp):
    import family_tree
    people = pp.data()["people"]
    [moses] = [s for s in pp.find("people", "Moses")][:1]
    img = Image.open(family_tree.family_chart(moses, people))
    assert img.width > 400 and img.height > 300
    david = pp.find("people", "David")[0]
    assert len(people[david]["children"]) > family_tree.MAX_CHILDREN        # a long list is cut short…
    img = Image.open(family_tree.family_chart(david, people))
    assert img.width < 2000                                                 # …and stays a sensible size
    assert family_tree.short_name({"name": "Judah (patriarch)"}) == "Judah"


def test_lineage_chart_wraps_into_columns(pp):
    import family_tree
    line = pp.descent(pp.find("people", "Adam"), pp.find("people", "Jesus"))
    img = Image.open(family_tree.lineage_chart(line, pp.data()["people"]))
    assert img.width > img.height * 0.6 and img.height < 1200


def test_tree_command(pp, fake_ctx):
    asyncio.run(pp.send_tree(fake_ctx, "Moses"))
    sent = fake_ctx.sent[-1]
    assert sent["embed"].title == "🌳 The family of Moses" and sent["file"].filename == "tree.png"
    asyncio.run(pp.send_tree(fake_ctx, "Abraham to David"))
    assert fake_ctx.sent[-1]["embed"].description.startswith("**14 generations:** Abraham → Isaac")
    asyncio.run(pp.send_tree(fake_ctx, "David to Abraham"))                # either order
    assert fake_ctx.sent[-1]["embed"].title == "🌳 From Abraham to David"
    asyncio.run(pp.send_tree(fake_ctx, "Ruth to Moses"))
    assert "can't find a line" in fake_ctx.sent[-1]["content"]
    asyncio.run(pp.send_tree(fake_ctx, "Zzyzx"))
    assert "don't know anyone" in fake_ctx.sent[-1]["content"]
