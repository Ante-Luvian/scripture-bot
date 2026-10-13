"""
!measure: Bible weights, measures and money in modern terms.
  !measure                 the list
  !measure cubit           one unit: what it was, its modern size, the verses
  !measure 300 cubits      a conversion ("three hundred cubits" works too)
  !measure Genesis 6:15    every measurement in a verse, converted

Modern values are Easton's Bible Dictionary (1897), quoted in each entry;
relations between units ("the shekel shall be twenty gerahs") are the KJV's
own words. tests/test_measures.py checks every quotation against the local
dictionary and every verse against the local KJV. Money is given in denarii
and days' wages (Matthew 20:2), not in today's currency.
"""
import re
from fractions import Fraction

import discord
from discord import app_commands

from core import bot, lookup
from scripture_lookup import BIBLE_OT

COLOR = discord.Color.from_rgb(140, 110, 60)

INCH, GRAIN, GALLON = 0.0254, 0.06479891, 4.54609      # Easton's figures are English (imperial) units
QUART, PINT, PECK, BUSHEL = GALLON / 4, GALLON / 8, GALLON * 2, GALLON * 8

KINDS = {"length": "📏 Length", "area": "📐 Area", "weight": "⚖️ Weight",
         "dry": "🌾 Dry measure (grain, flour)", "liquid": "🫗 Liquid measure (oil, wine)",
         "money": "🪙 Money"}

# key: name, kind, value (metres, square metres, grams, litres, or denarii), words the KJV
# uses, what it was, Easton's (entry, exact words), (relation, verse, the verse's exact words)
# or None, (example verse, its exact words), note
UNITS = {
    "cubit": dict(
        name="Cubit", kind="length", value=20.24 * INCH, words=["cubit"],
        about="The length of the forearm, from the elbow to the fingertips.",
        easton=("CUBIT", "20.24 inches for the ordinary cubit"),
        relation=None,
        example=("Genesis 6:15", "The length of the ark shall be three hundred cubits"),
        note="Easton's gives 21.888 inches for the longer “sacred” cubit."),
    "handbreadth": dict(
        name="Handbreadth", kind="length", value=4 * INCH, words=["handbreadth", "hand breadth"],
        about="The width of the four fingers.",
        easton=("HANDBREADTH", "A measure of four fingers, equal to about four inches"),
        relation=None,
        example=("1 Kings 7:26", "it was an hand breadth thick")),
    "reed": dict(
        name="Reed", kind="length", value=6 * (20.24 + 4) * INCH, words=["reed"],
        about="Ezekiel's measuring rod: six long cubits, each a cubit and a handbreadth.",
        easton=None,
        relation=("Six cubits, each a cubit and a handbreadth", "Ezekiel 40:5",
                  "a measuring reed of six cubits long by the cubit and an hand breadth"),
        example=("Ezekiel 41:8", "a full reed of six great cubits"),
        note="Worked out from Ezekiel 40:5 with Easton's cubit and handbreadth."),
    "fathom": dict(
        name="Fathom", kind="length", value=72 * INCH, words=["fathom"],
        about="The reach of both arms outstretched; used for the depth of water.",
        easton=("FATHOM", "a span of six feet"),
        relation=None,
        example=("Acts 27:28", "found it twenty fathoms")),
    "furlong": dict(
        name="Furlong (stadion)", kind="length", value=(606 * 12 + 9) * INCH, words=["furlong"],
        about="The Greek stadion, the length of a racecourse. The KJV calls it a furlong, "
              "but it is a little shorter than the English furlong.",
        easton=("FURLONG", "equal to 606 feet and 9 inches"),
        relation=None,
        example=("Luke 24:13", "a village called Emmaus, which was from Jerusalem about threescore furlongs")),
    "mile": dict(
        name="Mile (Roman)", kind="length", value=1618 * 36 * INCH, words=["mile"],
        about="A thousand Roman paces: shorter than the English mile.",
        easton=("MILE", "the Roman mile has 1618 yards"),
        relation=None,
        example=("Matthew 5:41", "whosoever shall compel thee to go a mile, go with him twain")),
    "sabbath": dict(
        name="Sabbath day's journey", kind="length", value=2000 * 20.24 * INCH,
        words=["sabbath day's journey", "sabbath days journey", "sabbath journey"],
        about="How far Jewish tradition allowed someone to walk on the Sabbath.",
        easton=("SABBATH DAY’S JOURNEY", "Supposed to be a distance of 2,000 cubits"),
        relation=None,
        example=("Acts 1:12", "from the mount called Olivet, which is from Jerusalem a sabbath day’s journey")),
    "acre": dict(
        name="Acre", kind="area", value=4046.86, words=["acre"],
        about="As much ground as a yoke of oxen could plough in a day.",
        easton=("ACRE", "It is about an acre of our measure"),
        relation=None,
        example=("Isaiah 5:10", "ten acres of vineyard shall yield one bath")),

    "gerah": dict(
        name="Gerah", kind="weight", value=12 * GRAIN, words=["gerah"],
        about="The smallest weight: a bean or grain.",
        easton=("WEIGHTS", "equal to 12 grains"),
        relation=("A twentieth of a shekel", "Ezekiel 45:12", "the shekel shall be twenty gerahs"),
        example=("Exodus 30:13", "a shekel is twenty gerahs")),
    "bekah": dict(
        name="Bekah", kind="weight", value=120 * GRAIN, words=["bekah"],
        about="Half a shekel: what each Israelite gave for the tabernacle.",
        easton=("WEIGHTS", "equal to 5 pennyweight"),
        relation=("Half a shekel", "Exodus 38:26", "A bekah for every man, that is, half a shekel"),
        example=("Exodus 38:26", "A bekah for every man")),
    "shekel": dict(
        name="Shekel", kind="weight", value=240 * GRAIN, words=["shekel"],
        about="The everyday weight, and so the everyday measure of silver: before coins, "
              "silver was paid by the shekel's weight.",
        easton=("WEIGHTS", "It was equal to 10 pennyweight"),
        relation=("Twenty gerahs", "Ezekiel 45:12", "the shekel shall be twenty gerahs"),
        example=("Genesis 23:15", "the land is worth four hundred shekels of silver"),
        note="Easton's own SHEKEL entry estimates a little less, 220 grains (14.3 g)."),
    "maneh": dict(
        name="Maneh (pound)", kind="weight", value=60 * 240 * GRAIN, words=["maneh", "pound"],
        about="Sixty shekels. The KJV calls it a “pound” in Kings, Ezra and Nehemiah.",
        easton=("WEIGHTS", "equal to 60 shekels, i.e., to 2 lbs. 6 oz"),
        relation=("Sixty shekels (20 + 25 + 15)", "Ezekiel 45:12",
                  "twenty shekels, five and twenty shekels, fifteen shekels, shall be your maneh"),
        example=("1 Kings 10:17", "three pound of gold went to one shield"),
        note="Easton's POUND entry says a hundred shekels instead."),
    "talent": dict(
        name="Talent", kind="weight", value=3000 * 240 * GRAIN, words=["talent"],
        about="The largest weight, three thousand shekels. In the parable of the talents "
              "it is a talent's weight of silver.",
        easton=("WEIGHTS", "Talent of silver (2 Kings 5:22), equal to 3,000 shekels, i.e., 125 lbs"),
        relation=("Three thousand shekels: the silver of 603,550 men at half a shekel each "
                  "came to a hundred talents and 1,775 shekels", "Exodus 38:25",
                  "an hundred talents, and a thousand seven hundred and threescore and fifteen shekels"),
        example=("Matthew 25:15", "unto one he gave five talents"),
        note="Easton's TALENT entry gives less, 94 3/7 lb (42.8 kg); a talent of gold, it says, "
             "weighed double."),
    "litra": dict(
        name="Pound (litra)", kind="weight", value=12 * 28.349523, words=["litra", "pound"],
        about="The Roman pound, in the Gospel of John.",
        easton=("POUND", "Gr. litra, equal to about 12 oz. avoirdupois"),
        relation=None,
        example=("John 12:3", "Then took Mary a pound of ointment of spikenard")),

    "cab": dict(
        name="Cab", kind="dry", value=2 * QUART, words=["cab", "kab"],
        about="A small dry measure, mentioned once: in the famine of the siege of Samaria.",
        easton=("CAB", "the eighteenth part of an ephah, equal to about two English quarts"),
        relation=None,
        example=("2 Kings 6:25", "the fourth part of a cab of dove’s dung for five pieces of silver")),
    "omer": dict(
        name="Omer (tenth deal)", kind="dry", value=GALLON / 2, words=["omer", "tenth deal"],
        about="A day's manna for one person. The KJV's “tenth deal” is the same measure.",
        easton=("OMER", "one-tenth of an ephah=half a gallon dry measure"),
        relation=("A tenth of an ephah", "Exodus 16:36", "an omer is the tenth part of an ephah"),
        example=("Exodus 16:16", "an omer for every man"),
        note="Easton's TENTH DEAL entry says six pints instead."),
    "seah": dict(
        name="Seah (measure)", kind="dry", value=PECK, words=["seah"],
        about="A third of an ephah. The KJV calls it a “measure”.",
        easton=("SEAH", "a seah was a little over one peck"),
        relation=None,
        example=("Genesis 18:6", "three measures of fine meal"),
        note="Easton's MEASURE entry identifies the “measures” of Genesis 18:6 as seahs."),
    "ephah": dict(
        name="Ephah", kind="dry", value=8.75 * GALLON, words=["ephah"],
        about="The usual measure of grain; the same size as the bath.",
        easton=("EPHAH", "equivalent to the bath for liquids"),
        relation=("The same as a bath: a tenth of a homer", "Ezekiel 45:11",
                  "The ephah and the bath shall be of one measure"),
        example=("Ruth 2:17", "it was about an ephah of barley"),
        note="Converted with Easton's figure for the bath (8 gallons 3 quarts)."),
    "homer": dict(
        name="Homer (cor)", kind="dry", value=8 * BUSHEL, words=["homer", "cor", "kor"],
        about="The largest dry measure (the word means “heap”); the cor is the same size.",
        easton=("HOMER", "containing about 8 bushels"),
        relation=("Ten baths, or ten ephahs", "Ezekiel 45:14", "ten baths are an homer"),
        example=("Hosea 3:2", "an homer of barley")),

    "log": dict(
        name="Log", kind="liquid", value=PINT, words=["log"],
        about="The smallest liquid measure: about six eggs' worth.",
        easton=("LOG", "the twelfth part of a him, or nearly a pint"),
        relation=None,
        example=("Leviticus 14:10", "one log of oil")),
    "hin": dict(
        name="Hin", kind="liquid", value=12 * PINT, words=["hin"],
        about="Twelve logs, used for the oil and wine of the offerings.",
        easton=("LOG", "the twelfth part of a him"),
        relation=None,
        example=("Exodus 29:40", "the fourth part of an hin of wine"),
        note="Worked out from Easton's log (nearly a pint, a twelfth of a hin)."),
    "bath": dict(
        name="Bath", kind="liquid", value=8.75 * GALLON, words=["bath"],
        about="The usual liquid measure; the same size as the ephah.",
        easton=("BATH", "It contained 8 gallons 3 quarts of our measure"),
        relation=("A tenth of a homer", "Ezekiel 45:11", "the bath may contain the tenth part of an homer"),
        example=("1 Kings 7:26", "it contained two thousand baths")),
    "firkin": dict(
        name="Firkin", kind="liquid", value=8.875 * GALLON, words=["firkin"],
        about="A Greek jar measure, in the wedding at Cana.",
        easton=("FIRKIN", "containing about 8 7/8 gallons"),
        relation=None,
        example=("John 2:6", "six waterpots of stone")),

    "denarius": dict(
        name="Penny (denarius)", kind="money", value=Fraction(1), words=["penny", "pence", "denarius", "denarii"],
        about="The Roman silver coin, a labourer's pay for a day.",
        easton=("PENNY", "It was the daily pay of a Roman soldier"),
        relation=("A day's wage", "Matthew 20:2", "agreed with the labourers for a penny a day"),
        example=("Matthew 18:28", "which owed him an hundred pence")),
    "drachma": dict(
        name="Piece of silver (drachma)", kind="money", value=Fraction(1),
        words=["drachma", "drachm", "piece of silver"],
        about="The Greek silver coin, worth about a denarius: the lost coin of Luke 15.",
        easton=("FARTHING", "a tenth of a denarius or drachma"),
        relation=None,
        example=("Luke 15:8", "what woman having ten pieces of silver"),
        note="In the Old Testament “pieces of silver” are shekels' weight of silver, not coins."),
    "stater": dict(
        name="Piece of money (stater)", kind="money", value=Fraction(4), words=["stater", "piece of money"],
        about="A silver coin of four drachmas: the temple tax for two people, found in the fish's mouth.",
        easton=("STATER", "or four drachmas"),
        relation=None,
        example=("Matthew 17:27", "thou shalt find a piece of money: that take, and give unto them for me and thee")),
    "mina": dict(
        name="Pound (mina)", kind="money", value=Fraction(100), words=["mina", "pound"],
        about="A hundred drachmas: the sum each servant is given in the parable of the pounds.",
        easton=("POUND", "It was equal to 100 drachmas"),
        relation=None,
        example=("Luke 19:13", "delivered them ten pounds")),
    "assarion": dict(
        name="Farthing (assarion)", kind="money", value=Fraction(1, 10), words=["assarion", "farthing"],
        about="A small copper coin: the price of two sparrows.",
        easton=("FARTHING", "a Roman coin equal to a tenth of a denarius"),
        relation=None,
        example=("Matthew 10:29", "Are not two sparrows sold for a farthing")),
    "quadrans": dict(
        name="Farthing (quadrans)", kind="money", value=Fraction(1, 40), words=["quadrans", "farthing"],
        about="A quarter of an assarion, or two mites.",
        easton=("FARTHING", "the fourth of an as, equal to two lepta"),
        relation=("Two mites", "Mark 12:42", "two mites, which make a farthing"),
        example=("Matthew 5:26", "till thou hast paid the uttermost farthing")),
    "mite": dict(
        name="Mite (lepton)", kind="money", value=Fraction(1, 80), words=["mite", "lepton", "lepta"],
        about="The smallest coin: the widow gave two.",
        easton=("MITE", "the very smallest bronze of copper coin"),
        relation=("Half a farthing", "Mark 12:42", "two mites, which make a farthing"),
        example=("Luke 21:2", "a certain poor widow casting in thither two mites")),
}

# ── numbers, KJV style ────────────────────────────────────────────────────────

ONES = {w: i for i, w in enumerate(
    "zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen "
    "sixteen seventeen eighteen nineteen".split())}
TENS = {w: 10 * i for i, w in enumerate("_ _ twenty thirty forty fifty sixty seventy eighty ninety".split()) if w != "_"}
SCORE = {"score": 20, "twoscore": 40, "threescore": 60, "fourscore": 80}
FRACTIONS = {"half": Fraction(1, 2), "third": Fraction(1, 3), "fourth": Fraction(1, 4),
             "fifth": Fraction(1, 5), "sixth": Fraction(1, 6), "tenth": Fraction(1, 10)}
NUMBER_WORDS = set(ONES) | set(TENS) | set(SCORE) | {"hundred", "thousand"}


def words_to_number(words: list) -> "int | None":
    """'six hundred thousand and three thousand and five hundred and fifty' -> 603550."""
    total = current = 0
    seen = False
    if words and all(w in ("a", "an") for w in words):
        return 1
    for w in words:
        if w in ("and", "a", "an"):
            continue
        if w in ONES:
            current += ONES[w]
        elif w in TENS:
            current += TENS[w]
        elif w in SCORE:
            current = current * 20 if (w == "score" and current) else current + SCORE[w]
        elif w == "hundred":
            current = (current or 1) * 100
        elif w == "thousand":
            total += (current or 1) * 1000
            current = 0
        else:
            return None
        seen = True
    return total + current if seen else None


def read_amount(text: str) -> "Fraction | None":
    """'300', '2.5', '1/2', 'three hundred', 'half a', 'an', 'the fourth part of a' -> a number."""
    t = re.sub(r"[^a-z0-9./ ]+", " ", text.lower()).split()
    if not t:
        return Fraction(1)
    if len(t) == 1 and re.fullmatch(r"\d+(\.\d+)?|\d+/\d+", t[0]):
        return Fraction(t[0])
    while t and t[-1] in ("a", "an", "of", "part", "the"):     # "the fourth part of a" -> "the fourth"
        t.pop()
    while t and t[0] == "the":
        t.pop(0)
    if not t:
        return Fraction(1)
    if t[-1] in FRACTIONS:
        whole = words_to_number(t[:-1]) if t[:-1] else 1
        return None if whole is None else whole * FRACTIONS[t[-1]]
    n = words_to_number(t)
    return None if n is None else Fraction(n)


# ── finding units ─────────────────────────────────────────────────────────────

def _norm(text: str) -> str:
    text = text.lower().replace("’", "'").replace("-", " ")
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9.'/ ]+", " ", text)).strip()


def _singular(word: str) -> str:
    word = word.replace("pieces", "piece").replace("days'", "day's").replace("tenth deals", "tenth deal")
    if word in ("pence", "denarii", "lepta"):
        return word
    for end in ("es", "s"):
        if word.endswith(end) and word[: -len(end)] in ALL_WORDS:
            return word[: -len(end)]
    return word


ALL_WORDS = {w for u in UNITS.values() for w in u["words"]}


def find_units(name: str) -> list:
    """Every unit a name could mean ('pound' is three different things)."""
    n = _singular(_norm(name))
    return [key for key, u in UNITS.items() if n in u["words"] or n == key or n == _norm(u["name"])]


def parse_query(query: str) -> "tuple[Fraction, list] | None":
    """'300 cubits' -> (300, ['cubit']); 'half a shekel' -> (1/2, ['shekel'])."""
    q = _norm(query)
    for size in (3, 2, 1):                       # the longest unit name at the end wins
        words = q.split()
        if len(words) < size:
            continue
        keys = find_units(" ".join(words[-size:]))
        if keys:
            amount = read_amount(" ".join(words[:-size]))
            return (amount, keys) if amount is not None else None
    return None


# ── modern units ──────────────────────────────────────────────────────────────

def _num(x: float) -> str:
    if x >= 100:
        return f"{round(x):,}"
    if x >= 10:
        return f"{x:.1f}".rstrip("0").rstrip(".")
    return f"{x:.2f}".rstrip("0").rstrip(".") if x >= 0.1 else f"{x:.3g}"


def modern(kind: str, amount: float) -> str:
    """A quantity of the base unit for its kind, in metric and US/imperial terms."""
    if kind == "length":
        m = amount
        metric = f"{_num(m * 100)} cm" if m < 1 else f"{_num(m)} m" if m < 1000 else f"{_num(m / 1000)} km"
        ft = m / 0.3048
        other = (f"{_num(ft * 12)} in" if ft < 3 else f"{_num(ft)} ft" if m < 1000
                 else f"{_num(m / 1609.344)} miles")
        return f"{metric} ({other})"
    if kind == "area":
        return f"{_num(amount / 10000)} hectares ({_num(amount / 4046.86)} acres)"
    if kind == "weight":
        g = amount
        metric = f"{_num(g)} g" if g < 1000 else f"{_num(g / 1000)} kg"
        lb = g / 453.59237
        return f"{metric} ({_num(lb * 16)} oz)" if lb < 1 else f"{metric} ({_num(lb)} lb)"
    if kind in ("dry", "liquid"):
        litres = amount
        metric = f"{_num(litres * 1000)} ml" if litres < 0.1 else f"{_num(litres)} litres"
        if kind == "dry":
            other = (f"{_num(litres / 1.1012)} US dry quarts" if litres < 8.8
                     else f"{_num(litres / 35.239)} US bushels")
        else:
            other = f"{_num(litres / 0.473176)} US pints" if litres < 3.785 else f"{_num(litres / 3.785412)} US gallons"
        return f"{metric} ({other})"
    if kind == "money":
        d = Fraction(amount).limit_denominator(1000)
        if d < 1:
            return f"{d.numerator}/{d.denominator} of a denarius (a denarius was a day's wage)"
        if d == 1:
            return "1 denarius: a day's wage for a labourer"
        n = f"{d.numerator:,}" if d.denominator == 1 else _num(float(d))
        return f"{n} denarii: {n} days' wages for a labourer"
    raise ValueError(kind)


def _amount_text(amount: Fraction) -> str:
    if amount.denominator == 1:
        return f"{amount.numerator:,}"
    if amount < 1:
        return f"{amount.numerator}/{amount.denominator}"
    return _num(float(amount))


def _total(amount: Fraction, key: str):
    u = UNITS[key]
    return u["value"] * amount if u["kind"] == "money" else float(amount) * u["value"]


def convert_line(amount: Fraction, key: str) -> str:
    u = UNITS[key]
    return f"**{_amount_text(amount)} × {u['name']}** ≈ {modern(u['kind'], _total(amount, key))}"


# ── measurements in a verse ───────────────────────────────────────────────────

QUADRANS_VERSES = {"Matthew 5:26", "Mark 12:42"}       # Easton's FARTHING: the kodrantes; elsewhere the assarion


def _unit_for(phrase: str, ref: str) -> "str | None":
    """The unit a KJV word means in this verse ('pound' and 'farthing' depend on where)."""
    keys = find_units(phrase)
    book = re.sub(r"\s*\d+:\d+.*$", "", ref)
    old = book in BIBLE_OT
    if phrase.startswith("piece"):
        if "silver" in phrase:
            return "shekel" if old else ("drachma" if book == "Luke" else None)
        return "stater" if book == "Matthew" else None
    if not keys:
        return None
    if "maneh" in keys:
        return "maneh" if old else ("mina" if book == "Luke" else "litra")
    if "assarion" in keys:
        return "quadrans" if ref in QUADRANS_VERSES else "assarion"
    return keys[0]


UNIT_PATTERN = re.compile(
    r"\b(sabbath day's journey|hand ?breadths?|tenth deals?|pieces? of (?:silver|money)|"
    r"cubits?|reeds?|fathoms?|furlongs?|miles?|acres?|gerahs?|bekah|shekels?|talents?|pounds?|"
    r"cabs?|omers?|ephahs?|homers?|logs?|hin|baths|bath|firkins?|pence|penny|farthings?|mites?)\b")
_TOKEN = (r"(?:" + "|".join(sorted(NUMBER_WORDS | {"and", "a", "an", "half"}, key=len, reverse=True))
          + r"|the (?:" + "|".join(FRACTIONS) + r") part of)")
AMOUNT_BEFORE = re.compile(rf"((?:\b{_TOKEN}\b ?)*)$")


OR_BEFORE = re.compile(rf"((?:\b{_TOKEN}\b ?)+)or $")


def measurements_in(text: str, ref: str) -> list:
    """[(the words, amount, unit key, smaller amount or None)] for each measurement in a KJV
    verse; the smaller amount is for "two or three firkins"."""
    plain = _norm(re.sub(r"\*\*\[\d+\]\*\*", " ", text))
    found = []
    for m in UNIT_PATTERN.finditer(plain):
        phrase = m.group(1)
        key = _unit_for(_singular(phrase), ref)
        if key is None:
            continue
        match = AMOUNT_BEFORE.search(plain[: m.start()])
        before = re.sub(r"^(?:and )+", "", match.group(1).strip())
        if not before or (before in ("a", "an") and key == "reed"):
            continue                     # "the shekel of the sanctuary", "a reed shaken with the wind"
        amount = read_amount(before)
        if not amount:
            continue
        low = None
        alt = OR_BEFORE.search(plain[: match.start(1)])
        if alt and (low := read_amount(alt.group(1).strip())):
            before = f"{alt.group(1).strip()} or {before}"
        found.append((f"{before} {phrase}", amount, key, low))
    return found


# ── embeds ────────────────────────────────────────────────────────────────────

def unit_field(key: str) -> "tuple[str, str]":
    u = UNITS[key]
    lines = [u["about"], f"**≈ {modern(u['kind'], u['value'])}**"]
    if u.get("relation"):
        what, ref, words = u["relation"]
        lines.append(f"{what}: “…{words}…” ({ref})")
    ref, words = u["example"]
    lines.append(f"In the Bible: “…{words}…” ({ref})")
    if u.get("easton"):
        entry, words = u["easton"]
        entry = " ".join(w.capitalize() for w in entry.split())
        lines.append(f"*Easton's ({entry}): “{words}”*")
    if u.get("note"):
        lines.append(f"*{u['note']}*")
    return f"{KINDS[u['kind']].split(' ')[0]} {u['name']}", "\n".join(lines)


FOOTER = ("Ancient measures varied by time and place, so these are estimates · modern values: "
          "Easton's Bible Dictionary (1897)")


def unit_embed(keys: list, amount: "Fraction | None" = None) -> discord.Embed:
    if amount is not None and amount != 1:
        description = "\n".join(convert_line(amount, k) for k in keys)
        if len(keys) > 1:
            description = "The KJV uses this word for more than one thing:\n" + description
        embed = discord.Embed(title="📏 Bible measures", description=description, color=COLOR)
    else:
        title = UNITS[keys[0]]["name"] if len(keys) == 1 else "📏 Bible measures"
        embed = discord.Embed(title=f"📏 {title}" if len(keys) == 1 else title, color=COLOR,
                              description=None if len(keys) == 1 else "The KJV uses this word for more than one thing:")
    for key in keys:
        name, value = unit_field(key)
        embed.add_field(name=name, value=value[:1024], inline=False)
    embed.set_footer(text=FOOTER)
    return embed


def verse_embed(ref: str, text: str, found: list) -> discord.Embed:
    plain = re.sub(r"\*\*\[\d+\]\*\*\s*", "", text).strip()
    lines = []
    for words, amount, key, low in found:
        kind = UNITS[key]["kind"]
        size = modern(kind, _total(amount, key))
        if low:
            size = f"{modern(kind, _total(low, key))} to {size}"
        lines.append(f"**{words}** ≈ {size} · {UNITS[key]['name']}")
    embed = discord.Embed(title=f"📏 {ref}", description=f"> {plain[:1500]}\n\n" + "\n".join(lines), color=COLOR)
    embed.set_footer(text=FOOTER)
    return embed


def list_embed() -> discord.Embed:
    embed = discord.Embed(
        title="📏 Bible weights, measures and money",
        description="`!measure cubit` for one, `!measure 300 cubits` to convert, "
                    "`!measure Genesis 6:15` for the measurements in a verse.",
        color=COLOR)
    for kind, label in KINDS.items():
        names = [u["name"] for u in UNITS.values() if u["kind"] == kind]
        if names:
            embed.add_field(name=label, value=", ".join(names), inline=False)
    embed.set_footer(text=FOOTER)
    return embed


async def send_measure(ctx, query: str) -> None:
    query = query.strip()
    if not query:
        await ctx.send(embed=list_embed())
        return
    if re.search(r"\d+\s*:\s*\d+", query):
        result = lookup.get_verse(query)
        if result.get("found"):
            ref = result.get("reference", query)
            found = measurements_in(result["text"], ref)
            if not found:
                await ctx.send(f"I didn't find any weights, measures or money in **{ref}**.")
                return
            await ctx.send(embed=verse_embed(ref, result["text"], found))
            return
    parsed = parse_query(query)
    if parsed is None:
        await ctx.send(f"I don't know a Bible measure called **{query}**.", embed=list_embed())
        return
    amount, keys = parsed
    await ctx.send(embed=unit_embed(keys, amount))


@bot.command(name="measure", aliases=["measures", "weights", "money", "convert"])
async def cmd_measure(ctx, *, query: str = ""):
    """Bible weights, measures and money in modern terms.
    Usage: !measure                — the list
           !measure talent         — one unit
           !measure 300 cubits     — a conversion
           !measure Genesis 6:15   — the measurements in a verse"""
    await send_measure(ctx, query)


async def _unit_names(interaction: discord.Interaction, current: str):
    cur = current.lower()
    names = sorted({u["name"] for u in UNITS.values()})
    return [app_commands.Choice(name=n, value=n) for n in names if cur in n.lower()][:25]


@bot.tree.command(name="measure", description="Bible weights, measures and money in modern terms")
@app_commands.describe(what="A unit (talent), an amount (300 cubits), or a verse (Genesis 6:15); empty for the list")
@app_commands.autocomplete(what=_unit_names)
async def measure_slash(interaction: discord.Interaction, what: str = ""):
    await interaction.response.defer()
    ctx = await bot.get_context(interaction)
    await send_measure(ctx, what)
