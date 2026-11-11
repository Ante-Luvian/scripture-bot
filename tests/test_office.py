"""!office (bot_commands/office.py): an hour of the Roman Breviary, by the Divinum Officium project's own engine (a
git clone in vendor/, run with Perl). The parts that need neither are tested always; the hours, where both are here."""
import asyncio
import datetime

import pytest


@pytest.fixture(scope="module")
def office(bot_module):
    from bot_commands import office
    return office


TODAY = datetime.date(2026, 11, 11)


@pytest.mark.parametrize("args, hour, day", [
    ("", "lauds", TODAY), ("vespers", "vespers", TODAY), ("compline tomorrow", "compline", datetime.date(2026, 11, 12)),
    ("matins 2026-12-25", "matins", datetime.date(2026, 12, 25)), ("25 December", "lauds", datetime.date(2026, 12, 25)),
    ("vespers december 24", "vespers", datetime.date(2026, 12, 24)), ("None yesterday", "none", datetime.date(2026, 11, 10)),
])
def test_parse(office, args, hour, day):
    assert office.parse(args, TODAY) == (hour, day)


@pytest.mark.parametrize("args", ["banana", "lauds 31 February", "!!", "matins 2026-13-40"])
def test_parse_refuses(office, args):
    assert isinstance(office.parse(args, TODAY), str)


def test_titles_in_english(office):
    assert office.english("Dominica VI Post Epiphaniam") == "Sixth Sunday after Epiphany"
    assert office.english("Feria IV") == "Wednesday"


def test_a_section_as_discord_text(office):
    cell = ("<DIV ALIGN='right'><A HREF='#'>Top</A></DIV>"
            "<FONT SIZE='+1' COLOR=\"red\"><B><I>Psalms</I></B></FONT><br/>"
            "<FONT COLOR=\"red\"><I>Ant.</I></FONT> Alleluia.<br/>"
            "<FONT COLOR=\"red\"><I>92:1</I></FONT> The Lord hath reigned, * he is clothed with beauty.<br/>"
            "<FONT COLOR=\"red\"><I>V.</I></FONT> O God, <span style='color:red; font-size:1.25em'>+</span> come<br/>"
            "<FONT SIZE='+2' COLOR=\"red\"><B><I>G</I></B></FONT>lory be to the Father.<br/>")
    text = office.text_of(cell)
    assert text.startswith("**Psalms**") and "Top" not in text
    assert "*92:1* The Lord hath reigned, ∗ he is clothed" in text           # (the mid-verse mark isn't italics)
    assert "V. O God, ✠ come" in text and "Glory be to the Father." in text and "Ant. Alleluia." in text


@pytest.mark.skipif("not __import__('bot_commands.office', fromlist=['x']).available()",
                    reason="needs Perl and vendor/divinum-officium")
def test_the_hours(office):
    """Lauds on Sunday 15 November 2026, by the Divino Afflatu rubrics: the sixth Sunday after Epiphany, resumed in
    November, with St Albert the Great commemorated; Psalm 92 its first psalm; Matins runs to many pages."""
    name, pages = asyncio.run(office.hour_pages("lauds", datetime.date(2026, 11, 15)))
    assert name.startswith("Sixth Sunday after Epiphany") and "St. Albert the Great" in name
    assert "Psalm 92" in pages[0] and "O God, ✠ come to my assistance" in pages[0]
    assert all(len(p) <= 4096 and p.count("*") % 2 == 0 for p in pages)
    _, matins = asyncio.run(office.hour_pages("matins", datetime.date(2026, 11, 15)))
    assert len(matins) > 5
