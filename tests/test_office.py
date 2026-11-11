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


@pytest.mark.parametrize("args, key, rest", [
    ("vespers 1960 tomorrow", "1960", "vespers tomorrow"), ("compline", "da", "compline"),
    ("lauds Monastic", "monastic", "lauds"), ("matins 1570 25 December", "1570", "matins 25 December"),
])
def test_rubrics(office, args, key, rest):
    assert office.rubrics_of(args) == (key, rest)


@pytest.mark.skipif("not __import__('bot_commands.office', fromlist=['x']).available()",
                    reason="needs Perl and vendor/divinum-officium")
def test_each_hour_as_it_comes(office):
    """!daily office: each chosen hour at its traditional time in the server's zone, once (across restarts), as a card
    with 📖 to open it; the day is the server's day."""
    import core
    sent = []

    class Channel:
        async def send(self, **kw):
            sent.append(kw)
    core._update_guild_config(7, office_channel_id=99, office_zone=-5, office_hours=["vespers", "compline"],
                              office_rubrics="1960")
    client = type("C", (), {"get_channel": lambda self, i: Channel() if i == 99 else None})()
    utc = lambda h, m=0: datetime.datetime(2026, 11, 15, h, m)              # (UTC-5: 18:00 there is 23:00 here)
    assert asyncio.run(office.run_office_hours(client, utc(18))) == 0          # (13:00 there: no hour chosen)
    assert asyncio.run(office.run_office_hours(client, utc(23))) == 1          # (18:00 there: Vespers)
    assert asyncio.run(office.run_office_hours(client, utc(23))) == 0          # (already posted)
    card = sent[0]["embed"]
    assert card.title.startswith("🕯️ Vespers · Sunday 15 November") and "1960" in card.footer.text
    assert "Sixth Sunday" in card.description and any(f.name == "Psalms" for f in card.fields)
    button = sent[0]["view"].children[0].item
    assert button.custom_id == "dopen:vespers:20261115:1960" and "Vespers" in button.label
    # Compline at 21:00 there is 02:00 UTC the next day: still Sunday's Compline
    assert asyncio.run(office.run_office_hours(client, datetime.datetime(2026, 11, 16, 2, 0))) == 1
    assert sent[1]["embed"].title.startswith("🕯️ Compline · Sunday 15 November")


@pytest.mark.skipif("not __import__('bot_commands.office', fromlist=['x']).available()",
                    reason="needs Perl and vendor/divinum-officium")
def test_summary_and_no_omitted_sections(office):
    name, pages = asyncio.run(office.hour_pages("matins", datetime.date(2026, 11, 15)))
    summary = office._SUMMARY[("Matins", datetime.date(2026, 11, 15), "da")]
    assert summary["psalms"][:3] == ["1", "2", "3"]
    assert "From the Holy Gospel according to Matthew (Matt 13:31-35)" in summary["lessons"]
    assert any("Augustine" in l for l in summary["lessons"]) and any("Jerome" in l for l in summary["lessons"])
    assert not any("{omit}" in p or "{" in p for p in pages)
