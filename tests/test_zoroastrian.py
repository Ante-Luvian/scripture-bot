"""!roz (the Zoroastrian day), its daily post, and the 🔤 Terms button (bot_commands/zoroastrian.py)."""
import asyncio
import datetime

import pytest

D = datetime.date


@pytest.fixture(scope="module")
def z(bot_module):
    from bot_commands import zoroastrian
    return zoroastrian


def test_the_shahenshahi_and_kadmi_new_years(z):
    """Navroz 1395 Y.Z. fell on 15 August 2025 (Shahenshahi); the year has no leap day, so 1396's is 365 days on."""
    assert z.roz_mah(z.day_of_year(D(2025, 8, 15), "shahenshahi"))[2] == "roz Hormazd, mah Fravardin"
    assert z.shahenshahi_year(D(2025, 8, 15)) == 1395 and z.shahenshahi_year(D(2026, 8, 15)) == 1396
    assert z.day_of_year(D(2026, 8, 15), "shahenshahi") == 1                  # (2026 has no 29 February)
    assert z.day_of_year(D(2028, 8, 14), "shahenshahi") == 1                  # (2028 does: a day earlier)
    assert z.day_of_year(D(2025, 8, 14), "shahenshahi") == 365
    assert z.roz_mah(365)[2].startswith("Vahishtoisht (Gatha day 5)")
    assert z.roz_mah(z.day_of_year(D(2025, 8, 15), "kadmi"))[2] == "roz Hormazd, mah Ardibehesht"   # a month ahead


def test_the_fasli_year_and_the_gahambars(z):
    """The Fasli year begins on 21 March; Wikipedia's Gregorian dates for the Gahambars are its days 41, 101..."""
    assert z.day_of_year(D(2026, 3, 21), "fasli") == 1 and z.day_of_year(D(2026, 3, 20), "fasli") == 365
    assert z.day_of_year(D(2028, 3, 20), "fasli") == 366                      # (a leap year's sixth Gatha day)
    for day, name in ((D(2026, 4, 30), "Maidyozarem"), (D(2026, 6, 29), "Maidyoshahem"),
                      (D(2026, 9, 12), "Paitishahem"), (D(2026, 10, 12), "Ayathrem"),
                      (D(2026, 12, 31), "Maidyarem"), (D(2027, 3, 16), "Hamaspathmaedem")):
        assert any(f"{name} Gahambar" in f and "day 1 of 5" in f for f in z.festivals(z.day_of_year(day, "fasli"))), name
    assert not z.festivals(z.day_of_year(D(2026, 4, 29), "fasli"))


def test_festivals(z):
    assert z.festivals(1)[0].startswith("**Navroz**")
    assert any("Khordad Sal" in f for f in z.festivals(6))
    assert any("jashan of Meher" in f for f in z.festivals(6 * 30 + 16))          # Mehergan: Meher roz, Meher mah
    assert any("jashan of Adar" in f for f in z.festivals(8 * 30 + 9))
    assert any("Zarthost no Diso" in f for f in z.festivals(9 * 30 + 11))         # Khorshed roz, Dae mah
    ahead, name = z.next_festival(D(2025, 8, 14))
    assert ahead == 1 and "Navroz" in name


def test_the_embed(z):
    e = z.roz_embed(D(2025, 8, 15))
    assert "**Shahenshahi:** roz Hormazd, mah Fravardin, 1395 Y.Z." in e.description
    being = e.fields[0]
    assert "Hormazd" in being.name and "Ahura Mazda" in being.value and "`!verse Sirozahs 2:1`" in being.value
    assert "Navroz" in e.fields[1].value
    assert "Havan 6–10 a.m." in e.fields[2].value
    assert len(e) <= 6000


def test_parse_day(z):
    today = D(2026, 11, 9)
    assert z.parse_day("", today) == today and z.parse_day("21 March", today) == D(2026, 3, 21)
    assert z.parse_day("march 21", today) == D(2026, 3, 21) and z.parse_day("2025-08-15", today) == D(2025, 8, 15)
    assert z.parse_day("31 February", today) is None and z.parse_day("banana", today) is None
    assert z.parse_day("9999-12-31", today) is None and z.parse_day("0001-01-01", today) is None


def test_the_command(z, fake_ctx):
    asyncio.run(z.cmd_roz.callback(fake_ctx, when="15 August 2025"))
    assert "Give a date like" in fake_ctx.sent[-1]["content"]
    asyncio.run(z.cmd_roz.callback(fake_ctx, when="2025-08-15"))
    assert fake_ctx.sent[-1]["embed"].title == "🔥 The Zoroastrian day — 15 August 2025"


def test_the_daily_post_once_a_day(z):
    sent = []

    class Channel:
        async def send(self, **kwargs):
            sent.append(kwargs)
    assert asyncio.run(z.post_rozday(1, Channel(), D(2026, 11, 9)))
    assert not asyncio.run(z.post_rozday(1, Channel(), D(2026, 11, 9)))       # (a restart doesn't post it twice)
    assert asyncio.run(z.post_rozday(1, Channel(), D(2026, 11, 9), force=True))
    assert len(sent) == 2 and sent[0]["content"] == "🔥 **The Zoroastrian day**"


def test_terms(z, lookup):
    r = lookup.get_verse("Yashts 22:1")
    names = [n for n, _ in z.terms_in(r["text"])]
    assert "Ahura Mazda" in names
    [button] = z.term_buttons(r)
    assert button.item.custom_id == "zterms:Yashts 22:1" and button.item.label == "Terms"
    assert "fravashi" in [n for n, _ in z.terms_in(lookup.get_verse("Yasna 23:1")["text"])]
    assert "Chinvat bridge" in [n for n, _ in z.terms_in(lookup.get_verse("Arda Viraf 5:2")["text"])]
    assert z.term_buttons(lookup.get_verse("John 3:16")) == []                # (only the Zoroastrian texts)
    assert z.term_buttons({"found": False}) == []
