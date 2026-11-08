"""`!<command> random` for every command where a random pick makes sense, and a random pick for the lookups that
used to answer only "Usage: ..." when sent with nothing (the owner's rule, 2026-11-02; core.random_input has it).

Each picker makes an argument its command already understands: a name (`!who Ruth`), a number (`!canon 1247`), a
reference (`!xref John 3:16`), a date (`!saint 25 July`). A command whose bare form is already random ("!verse",
"!ballad") gets "" for "random", so its own random path runs."""
import datetime
import random

from core import BIBLE_NT, BIBLE_OT, guild_traditions, lookup, random_input

ALREADY_RANDOM = ""                   # (the command's own bare form is a random one)


def _guild_id(ctx):
    return getattr(getattr(ctx, "guild", None), "id", None)


def bible_reference() -> str:
    return lookup.random_verse_from_books(BIBLE_OT + BIBLE_NT)["reference"]


def day_this_year() -> datetime.date:
    year = datetime.date.today().year
    start = datetime.date(year, 1, 1)
    return start + datetime.timedelta(days=random.randrange((datetime.date(year + 1, 1, 1) - start).days))


def gospel_reference() -> str:
    """A verse of the Gospels: the Fathers' commentary (!catena, !study) covers them fully, much of the Old
    Testament not at all."""
    return lookup.random_verse_from_books(["Matthew", "Mark", "Luke", "John"])["reference"]


def iso_day() -> str:
    return day_this_year().isoformat()


# ── commands whose bare form is already random: "random" runs it ──────────────
for _name in ("verse", "ballad", "blake", "desert", "dore", "physiologus", "reynard", "vov", "card", "midi",
              "metrical", "harmony", "summa", "edda", "odin"):
    random_input(_name, lambda: ALREADY_RANDOM)


# ── the daily ones: bare is today's; "random" a random day this year ─────────
for _name in ("bcp", "mp", "ep", "collect", "hymnday", "troparion", "planets", "parsha", "dafyomi", "learning",
              "today"):
    random_input(_name, iso_day)
random_input("psalm", lambda: day_this_year().strftime("%m-%d"))


def _saint_day() -> str:
    d = day_this_year()
    return f"{d.day} {d.strftime('%B')}"


random_input("saint", _saint_day)


def _horoscope() -> str:
    from bot_commands.planets import SIGNS
    return random.choice(SIGNS)[0].lower()


random_input("horoscope", _horoscope)


# ── the browsing ones: bare is the list; "random" one of what's listed ────────
def _icon() -> str:
    from bot_commands.icons import icons
    return random.choice(sorted(icons()))


def _journey(ctx) -> str:
    from bot_commands.journeys import allowed
    return random.choice(allowed(_guild_id(ctx)))


def _king() -> str:
    from bot_commands.kings import KINGS
    return random.choice(KINGS)[0]


def _measure() -> str:
    from bot_commands.measures import UNITS
    return random.choice(sorted(UNITS))


def _story() -> str:
    from bot_commands.stories import EMOJI
    return random.choice(sorted(EMOJI))


def _prayer() -> str:
    from bot_commands.prayers import PRAYERS
    return random.choice(sorted(PRAYERS))


def _creed() -> str:
    from bot_commands.church import CREEDS
    return random.choice(sorted(CREEDS))


def _mysteries() -> str:
    from bot_commands.rosary import MYSTERIES
    return random.choice(sorted(MYSTERIES))


def _liturgy_part() -> str:
    from bot_commands.divine_liturgy import sections
    return random.choice(sections())[0]


def _hymn_shelf() -> str:
    from bot_commands.hymns import SHELVES
    return random.choice(sorted(SHELVES))


def _quiz(ctx) -> str:
    from bot_commands.quiz import QUIZ_POOLS
    have = set(guild_traditions(_guild_id(ctx)))
    return random.choice(["", "hard"] + [k for k in QUIZ_POOLS if k in have])


def _book(ctx) -> str:
    from bot_commands.books import _hidden_book, _leaves, tree_for
    guild_id = _guild_id(ctx)
    _, sections = tree_for(guild_id)
    return random.choice([b for b in _leaves(sections) if isinstance(b, str) and not _hidden_book(guild_id, b)])


for _name, _picker in (("icon", _icon), ("journey", _journey), ("kings", _king), ("measure", _measure),
                       ("story", _story), ("prayer", _prayer), ("creed", _creed), ("rosary", _mysteries),
                       ("divineliturgy", _liturgy_part), ("hymnlist", _hymn_shelf), ("quiz", _quiz),
                       ("books", _book)):
    random_input(_name, _picker)


# ── the lookups: bare used to be "Usage: ..."; now a random one, with a word on asking for a particular one ──
def _one_of(kind: str, keep=lambda e: True) -> str:
    """A random person or place whose name is theirs alone (not "Kedesh", one of several: that asks which one)."""
    from bot_commands.people import _index, _norm, data
    index = _index(kind)
    return random.choice([e["name"] for e in data()[kind].values()
                          if keep(e) and index.get(_norm(e["name"])) == [e["slug"]]])


def _person() -> str:
    return _one_of("people")


def _person_with_family() -> str:
    return _one_of("people", lambda p: p.get("father") or p.get("mother") or p.get("children"))


def _place() -> str:
    return _one_of("places")


def _dictionary_term() -> str:
    from bible_dictionary_lookup import _load
    return random.choice([e["name"] for e in _load().values()])


def _topic() -> str:
    from topics_lookup import _load
    return random.choice(sorted(_load())).title()


def _timeline() -> str:
    from timeline_lookup import _load
    entry = random.choice(_load())
    return " ".join(entry["text"].split()[:8])             # (enough of its words to find it again)


def _strongs() -> str:
    from strongs_lookup import _load
    return random.choice(sorted(_load()))


def _strongs_in_the_text() -> str:
    """A Strong's number that occurs in the interlinear text (the dictionary has numbers no verse is tagged with)."""
    import interlinear_lookup
    con = interlinear_lookup._connect()
    if con is None:
        return _strongs()
    # (a plain number: the text also tags "H2050B", which the command reads as H2050 and finds nowhere)
    rows = con.execute("SELECT strong FROM words WHERE strong GLOB '[GH][0-9]*' ORDER BY RANDOM() LIMIT 30").fetchall()
    plain = [r[0] for r in rows if r[0][1:].isdigit()]
    return plain[0] if plain else _strongs()


def _ccc() -> str:
    from bot_commands.church import _load_ccc
    return str(random.choice(sorted(_load_ccc())))


def _canon() -> str:
    from bot_commands.church import _load_canon
    return str(random.choice(sorted(_load_canon())))


def _bible_book() -> str:
    return random.choice(BIBLE_OT + BIBLE_NT)


def _quotation() -> str:
    from bot_commands.reference import _OT_NT_QUOTATIONS
    return random.choice(random.choice(_OT_NT_QUOTATIONS))


def _dss_reference() -> str:
    from bot_commands.translations import _DSS_BIBLICAL_BOOKS
    return lookup.random_verse_from_books([random.choice(list(_DSS_BIBLICAL_BOOKS))])["reference"]


# Themes that every tradition speaks of (`!theme` searches the whole library for the word)
THEMES = ["love", "mercy", "forgiveness", "death", "the soul", "wisdom", "prayer", "faith", "hope", "peace",
          "justice", "light", "darkness", "suffering", "joy", "truth", "humility", "pride", "anger", "patience",
          "charity", "the heart", "creation", "the stars", "the sea", "fire", "water", "bread", "the poor", "kings",
          "silence", "dreams", "angels", "the body", "fasting", "sacrifice", "friendship", "gold", "the mountain"]

LOOKUPS = [
    ("who", _person, "`!who Ruth` for someone particular"),
    ("tree", _person_with_family, "`!tree David`, or `!tree Abraham to David` for a line of descent"),
    ("place", _place, "`!place Bethel` for a particular place"),
    ("dictionary", _dictionary_term, "`!dictionary Aaron` for a particular entry"),
    ("topic", _topic, "`!topic love` for a particular subject"),
    ("timeline", _timeline, "`!timeline Abraham` for a particular book, person or event"),
    ("root", _strongs, "`!root H6`, `!root G26` or `!root <word>` for a particular one"),
    ("concordance", _strongs_in_the_text, "`!concordance G26` or `!concordance agape` for a particular word"),
    ("ccc", _ccc, "`!ccc 2558` for a particular paragraph (1–2865)"),
    ("canon", _canon, "`!canon 1247` for a particular canon (1–1751)"),
    ("cloud", _bible_book, "`!cloud Ecclesiastes` for a particular book"),
    ("theme", lambda: random.choice(THEMES), "`!theme forgiveness` for a particular theme"),
    ("xref", bible_reference, "`!xref John 3:16` for a particular verse"),
    ("quoted", _quotation, "`!quoted Isaiah 53:5` for a particular verse"),
    ("memorize", bible_reference, "`!memorize John 3:16` for a particular verse"),
    ("interlinear", bible_reference, "`!interlinear John 3:16` for a particular verse"),
    ("reverseinterlinear", bible_reference, "`!reverseinterlinear John 3:16` for a particular verse"),
    ("notes", bible_reference, "`!notes John 3:16` for a particular verse"),
    ("study", gospel_reference, "`!study John 3:16` for a particular verse"),
    ("compare", bible_reference, "`!compare John 3:16` for a particular verse"),
    ("variants", _dss_reference, "`!variants Isaiah 53:5` for a particular verse"),
    ("strong", _strongs, "`!strong G26` or `!strong John 3:16` for a particular one"),
    ("gematria", _dictionary_term, "`!gematria love` for a particular word"),
]
for _name, _picker, _hint in LOOKUPS:
    random_input(_name, _picker, bare=True, hint=_hint)

# (catena: bare is today's verse; "random" a random one)
random_input("catena", gospel_reference)
