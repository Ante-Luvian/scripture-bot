"""
The Zoroastrian day and the Avesta's words (2026-11-09, the owner's choice from a list).

    !roz            today in the Zoroastrian calendar: the day (roz) and month (mah), each named for a divine
                    being; that being's line of the Sirozah; any festival today and the next; the five gahs
    !roz 21 March   another day's
    !daily roz      the same posted each day (!rozsetup does the work)

And a 🔤 Terms button under !verse for a Zoroastrian passage that uses the words translators leave in
Avestan or Pahlavi (asha, fravashi, the Amesha Spentas...): what each means, briefly.

The calendar. Every month has 30 days, each named for a being (the Sirozah lists them in order), and the year
ends with five Gatha days, named for Zarathustra's five Gathas: 365 days. The Parsis of India keep it without
leap days, so its new year drifts: the Shahenshahi reckoning's fell on 15 August 2025 (year 1395 of Yazdegerd,
"Y.Z."), the Kadmi's a month earlier. The Fasli reckoning (and Iran's) keeps it to the sun, its new year on
21 March. The festivals are on fixed days of the year in each: the six Gahambars (seasonal feasts; Wikipedia's
Gregorian dates for them, April 30 - May 4 and so on, are these days of the Fasli year), the new year,
Zarathustra's birthday (Khordad roz of Farvardin mah) and death day (Khorshed roz of Dae mah), the ten days of
the souls (Muktad) at the year's end, and the jashan of a being on the day its roz and mah coincide.
"""
import datetime
import json
import re

import discord
from discord.ext import commands, tasks

from core import ROOT, _atomic_write_json, _load_guild_config, _update_guild_config, bot, command_enabled, log, lookup

ROZDAY_PATH = ROOT / "data" / "rozday.json"     # {"posted": {guild id: "YYYY-MM-DD"}}
DEFAULT_ROZDAY_TIME = "06:00"
COLOR = discord.Color.from_rgb(200, 90, 20)

SHAHENSHAHI_NAVROZ = datetime.date(2025, 8, 15)   # 1 Farvardin 1395 Y.Z.
SHAHENSHAHI_YEAR = 1395
KADMI_AHEAD = 30                                  # (the Kadmi reckoning is a month ahead)

# the 30 days, as the Parsis name them, with the Sirozah's verse for each (Sirozahs 2:N is day N)
DAYS = ["Hormazd", "Bahman", "Ardibehesht", "Shehrevar", "Spendarmad", "Khordad", "Amardad", "Dae-pa-Adar",
        "Adar", "Avan", "Khorshed", "Mohor", "Tir", "Gosh", "Dae-pa-Meher", "Meher", "Srosh", "Rashne",
        "Fravardin", "Behram", "Ram", "Govad", "Dae-pa-Din", "Din", "Ashishvangh", "Ashtad", "Asman", "Zamyad",
        "Mareshpand", "Aneran"]
# the 12 months, and the day of the month that has the same being (its jashan)
MONTHS = [("Fravardin", (19,)), ("Ardibehesht", (3,)), ("Khordad", (6,)), ("Tir", (13,)), ("Amardad", (7,)),
          ("Shehrevar", (4,)), ("Meher", (16,)), ("Avan", (10,)), ("Adar", (9,)), ("Dae", (1, 8, 15, 23)),
          ("Bahman", (2,)), ("Spendarmad", (5,))]
GATHA_DAYS = ["Ahunavad", "Ushtavad", "Spentomad", "Vohukhshathra", "Vahishtoisht"]

GAHAMBARS = [(41, "Maidyozarem", "mid-spring"), (101, "Maidyoshahem", "midsummer"),
             (176, "Paitishahem", "the bringing in of the harvest"), (206, "Ayathrem", "the bringing home of the herds"),
             (286, "Maidyarem", "midwinter"), (361, "Hamaspathmaedem", "all souls, on the five Gatha days")]
# the five watches of the day, with Mills's hours for them (the Gahs' introduction in SBE 31)
GAHS = [("Havan", "6–10 a.m."), ("Rapithwin", "10 a.m.–3 p.m."), ("Uzirin", "3–6 p.m."),
        ("Aiwisruthrem", "6 p.m.–midnight"), ("Ushahin", "midnight–6 a.m.")]


def day_of_year(day: datetime.date, reckoning: str) -> int:
    """1..365 (366: a Fasli leap year's extra Gatha day) in the Shahenshahi, Kadmi or Fasli year."""
    if reckoning == "fasli":
        start = datetime.date(day.year if day >= datetime.date(day.year, 3, 21) else day.year - 1, 3, 21)
        return (day - start).days + 1
    shift = KADMI_AHEAD if reckoning == "kadmi" else 0
    return ((day - SHAHENSHAHI_NAVROZ).days + shift) % 365 + 1


def shahenshahi_year(day: datetime.date) -> int:
    return SHAHENSHAHI_YEAR + (day - SHAHENSHAHI_NAVROZ).days // 365


def roz_mah(doy: int) -> "tuple[int | None, int | None, str]":
    """(day 1-30, month 1-12, its name) for a day of the year; a Gatha day has no month."""
    if doy > 360:
        return None, None, f"{GATHA_DAYS[min(doy - 361, 4)]} (Gatha day {doy - 360})"
    month, day = (doy - 1) // 30 + 1, (doy - 1) % 30 + 1
    return day, month, f"roz {DAYS[day - 1]}, mah {MONTHS[month - 1][0]}"


def festivals(doy: int) -> list:
    """What's kept on this day of the year."""
    out = []
    if doy == 1:
        out.append("**Navroz**, the New Year")
    if doy == 6:
        out.append("**Khordad Sal**, the birthday of Zarathustra")
    if doy == 281:
        out.append("**Zarthost no Diso**, the anniversary of Zarathustra's death")
    for first, name, meaning in GAHAMBARS:
        if first <= doy <= first + 4 or (name == "Hamaspathmaedem" and doy == 366):
            out.append(f"the **{name} Gahambar** ({meaning}), day {doy - first + 1} of 5")
    if 356 <= doy:
        out.append("**Muktad**, the days of the souls (fravashis) at the year's end")
    day, month, _ = roz_mah(doy)
    if day and day in MONTHS[month - 1][1]:
        out.append(f"the **jashan of {DAYS[day - 1]}**: the day and the month share their being")
    return out


def next_festival(day: datetime.date, reckoning: str = "shahenshahi") -> "tuple[int, str]":
    for ahead in range(1, 370):
        found = festivals(day_of_year(day + datetime.timedelta(days=ahead), reckoning))
        if found:
            return ahead, found[0]
    return 0, ""


def _sirozah(day: "int | None") -> str:
    if not day:
        return ""
    text = lookup._data.get("zoroastrian", {}).get("Sirozahs", {}).get("2", {}).get(str(day), "")
    return re.sub(r"^[^\n]*\n", "", text).strip()          # (without its heading, the day's name)


def roz_embed(day: datetime.date) -> discord.Embed:
    lines = []
    for reckoning, label in (("shahenshahi", "Shahenshahi"), ("kadmi", "Kadmi"), ("fasli", "Fasli")):
        doy = day_of_year(day, reckoning)
        year = f", {shahenshahi_year(day)} Y.Z." if reckoning == "shahenshahi" else ""
        lines.append(f"**{label}:** {roz_mah(doy)[2]}{year}")
    embed = discord.Embed(title=f"🔥 The Zoroastrian day — {day.day} {day.strftime('%B %Y')}",
                          description="\n".join(lines), color=COLOR)
    roz, _, _ = roz_mah(day_of_year(day, "shahenshahi"))
    line = _sirozah(roz)
    if line:
        embed.add_field(name=f"Today's being, in the Sirozah (Shahenshahi roz {DAYS[roz - 1]})",
                        value=f"*{line}*"[:1024] + f"\n`!verse Sirozahs 2:{roz}`", inline=False)
    today = []
    for reckoning, label in (("shahenshahi", "Shahenshahi"), ("kadmi", "Kadmi"), ("fasli", "Fasli")):
        today += [f"{f} ({label})" for f in festivals(day_of_year(day, reckoning))]
    ahead, upcoming = next_festival(day)
    value = "\n".join(today) if today else "No festival today."
    if upcoming:
        value += f"\nNext (Shahenshahi): {upcoming}, in {ahead} day{'s' if ahead != 1 else ''}"
    embed.add_field(name="Festivals", value=value[:1024], inline=False)
    embed.add_field(name="The five watches of the day (gahs), each with its prayer",
                    value=" · ".join(f"{n} {h}" for n, h in GAHS) + "\n`!verse Gahs 1` (Havan) to `!verse Gahs 5`",
                    inline=False)
    embed.set_footer(text="The Parsis of India keep the Shahenshahi or Kadmi reckoning, without leap days; "
                          "the Fasli, like Iran's, begins each year on 21 March.")
    return embed


_MONTH_NAMES = {datetime.date(2000, m, 1).strftime("%B").lower(): m for m in range(1, 13)}


def parse_day(text: str, today: datetime.date) -> "datetime.date | None":
    """'21 March', 'March 21', '2026-03-21'; None if it isn't a date."""
    t = text.strip().lower()
    if not t or t == "today":
        return today
    m = re.fullmatch(r"(\d{4})-(\d{1,2})-(\d{1,2})", t)
    if m:
        y, mo, d = map(int, m.groups())
    else:
        m = re.fullmatch(r"(\d{1,2})\s+([a-z]+)|([a-z]+)\s+(\d{1,2})", t)
        if not m:
            return None
        d, name = (m.group(1), m.group(2)) if m.group(1) else (m.group(4), m.group(3))
        mo = next((n for full, n in _MONTH_NAMES.items() if full.startswith(name[:3]) and len(name) >= 3), None)
        if mo is None:
            return None
        y, d = today.year, int(d)
    try:
        return datetime.date(y, mo, d)
    except ValueError:
        return None


def _today() -> datetime.date:
    return datetime.datetime.now(datetime.timezone.utc).date()


@bot.command(name="roz", aliases=["zoroastrianday", "parsiday", "zday"])
async def cmd_roz(ctx, *, when: str = ""):
    """Today in the Zoroastrian calendar. Usage: !roz  or  !roz 21 March"""
    day = parse_day(when, _today())
    if day is None:
        await ctx.send("Give a date like `!roz 21 March` or `!roz 2026-08-15`, or nothing for today.")
        return
    await ctx.send(embed=roz_embed(day))


# ── the daily post (!rozsetup, through !daily roz) ─────────────────────────────

def _load_state() -> dict:
    try:
        return json.loads(ROZDAY_PATH.read_text(encoding="utf-8")) if ROZDAY_PATH.exists() else {}
    except ValueError:
        return {}


async def post_rozday(guild_id, channel, day: datetime.date, force: bool = False) -> bool:
    state = _load_state()
    if state.get("posted", {}).get(str(guild_id)) == day.isoformat() and not force:
        return False
    await channel.send(content="🔥 **The Zoroastrian day**", embed=roz_embed(day))
    state.setdefault("posted", {})[str(guild_id)] = day.isoformat()
    _atomic_write_json(ROZDAY_PATH, state)
    return True


async def run_daily_roz(client, day: datetime.date, current_hm: str) -> int:
    posted = 0
    for guild_id, g in _load_guild_config().items():
        channel_id = g.get("rozday_channel_id")
        if not channel_id or g.get("rozday_time", DEFAULT_ROZDAY_TIME) != current_hm:
            continue
        if not command_enabled(int(guild_id), "roz"):
            continue
        channel = client.get_channel(int(channel_id))
        if channel is None:
            continue
        try:
            posted += await post_rozday(guild_id, channel, day)
        except Exception:
            log.exception(f"Failed to post the Zoroastrian day for guild {guild_id}")
    return posted


@tasks.loop(minutes=1)
async def daily_roz_task():
    now = datetime.datetime.now(datetime.timezone.utc)
    await run_daily_roz(bot, now.date(), f"{now.hour:02d}:{now.minute:02d}")


@daily_roz_task.before_loop
async def _before_daily_roz():
    await bot.wait_until_ready()


@bot.command(name="rozsetup", aliases=["rozconfig"], hidden=True)       # (!daily roz)
@commands.has_permissions(administrator=True)
async def cmd_rozsetup(ctx, action: str = "", *, arg: str = ""):
    """Post the Zoroastrian day in a channel.
    Usage: !rozsetup                  — show this server's settings
           !rozsetup channel #chan    — post each day's there
           !rozsetup time 06:00       — daily post time (24h UTC)
           !rozsetup test             — post today's now
           !rozsetup off              — stop the daily post"""
    if not ctx.guild:
        await ctx.send("This command only works in a server.")
        return
    g = _load_guild_config().get(str(ctx.guild.id), {})
    channel_id, time_hm = g.get("rozday_channel_id"), g.get("rozday_time", DEFAULT_ROZDAY_TIME)
    action = action.strip().lower()
    if not action:
        embed = discord.Embed(title=f"🔥 The Zoroastrian day — {ctx.guild.name}", color=COLOR)
        embed.add_field(name="Channel", value=f"<#{channel_id}>" if channel_id else "*not set — no daily post*")
        embed.add_field(name="Time (UTC)", value=time_hm)
        embed.set_footer(text="!daily roz channel #chan · time HH:MM · test · off")
        await ctx.send(embed=embed)
    elif action == "off":
        _update_guild_config(ctx.guild.id, rozday_channel_id=None)
        await ctx.send("The daily Zoroastrian day post is off for this server. (`!roz` still works.)")
    elif action == "channel":
        channel = ctx.message.channel_mentions[0] if ctx.message.channel_mentions else None
        if channel is None:
            await ctx.send("Mention a channel: `!daily roz channel #zoroastrian`")
            return
        _update_guild_config(ctx.guild.id, rozday_channel_id=channel.id)
        m = re.search(r"\btime\s+(\d{1,2}):(\d{2})\b", arg)
        if m and 0 <= int(m.group(1)) <= 23 and 0 <= int(m.group(2)) <= 59:
            time_hm = f"{int(m.group(1)):02d}:{m.group(2)}"
            _update_guild_config(ctx.guild.id, rozday_time=time_hm)
        await ctx.send(f"The Zoroastrian day will be posted in {channel.mention} at {time_hm} UTC.")
    elif action == "time":
        m = re.match(r"^(\d{1,2}):(\d{2})$", arg.strip())
        if not m or not (0 <= int(m.group(1)) <= 23 and 0 <= int(m.group(2)) <= 59):
            await ctx.send("Use 24-hour UTC time: `!daily roz time 06:00`")
            return
        hm = f"{int(m.group(1)):02d}:{int(m.group(2)):02d}"
        _update_guild_config(ctx.guild.id, rozday_time=hm)
        await ctx.send(f"Daily Zoroastrian day time set to **{hm} UTC**.")
    elif action == "test":
        channel = bot.get_channel(int(channel_id)) if channel_id else ctx.channel
        await post_rozday(ctx.guild.id, channel, _today(), force=True)
    else:
        await ctx.send("Unknown option. Use `channel`, `time`, `test`, or `off`.")


# ── 🔤 Terms: the Avesta's untranslated words ──────────────────────────────────
# (term, the spellings the translators use, what it means)

TERMS = [
    ("Ahura Mazda", r"ahura[- ]?mazda|mazda ahura|aûharmazd|auharmazd|ohrmazd|ormazd|ormuzd|hormazd",
     "\"the Wise Lord\": God, the creator of all that is good. Ohrmazd (Ormazd, Aûharmazd) is the later form."),
    ("Angra Mainyu", r"angra[- ]mainyu|ahriman|aharman|aharmen",
     "\"the Evil Spirit\", the destroyer, God's adversary; Ahriman (Aharman) is the later form."),
    ("Spenta Mainyu", r"spenta[- ]mainyu|bounteous spirit|holy spirit",
     "\"the Bounteous Spirit\", God's creative spirit, opposed to the Evil Spirit."),
    ("asha", r"\basha\b|\bashem\b|\bartâ|\bard\b|ashavan",
     "truth, righteousness, the right order of the world; its opposite is the druj."),
    ("druj", r"\bdruj\b|\bdrûg|\bdrug\b",
     "\"the Lie\": falsehood and disorder, the opposite of asha; also a demoness of it."),
    ("Amesha Spentas", r"amesha[- ]spentas?|amshaspands?|bountiful immortals?|archangels",
     "\"the Bounteous Immortals\", the six beings who serve Ahura Mazda: Good Mind (Vohu Manah), Best Truth "
     "(Asha Vahishta), Desirable Dominion (Khshathra Vairya), Holy Devotion (Spenta Armaiti), Wholeness "
     "(Haurvatat) and Immortality (Ameretat)."),
    ("Vohu Manah", r"vohu[- ]?man[aôo]h?|vohûman|bahman\b|good mind",
     "\"Good Mind\", the first of the Amesha Spentas; the Parsis' Bahman."),
    ("yazata", r"yazatas?|yazads?|\bizads?\b",
     "\"one worthy of worship\": a divine being, often translated \"angel\"; Mithra, Anahita and Sraosha are yazatas."),
    ("fravashi", r"fravashis?|farvardîn|farohars?|fravahars?",
     "the guardian spirit of a righteous person, existing before birth and after death; honoured at Muktad."),
    ("daeva", r"da[eê]vas?|\bdevs?\b|\bdeevs?\b|\bdîvs?\b",
     "a demon. Once a name for gods, as in India (deva), the Gathas turned it against them."),
    ("Sraosha", r"sraosha|srôsh|srosh|serosch",
     "\"Obedience\", the yazata who hears prayer, guards the world by night and leads souls after death."),
    ("Mithra", r"mithra|mihir|meher\b",
     "the yazata of contracts, truth and light, \"of the wide pastures\"; the Parsis' Meher."),
    ("Anahita", r"an[âa]hita|ardvi[- ]s[ûu]ra|ardvî|\baban\b|\bavan\b",
     "Ardvi Sura Anahita, the yazata of the waters; the Parsis' Avan."),
    ("haoma", r"\bhaomas?\b|\bhôm\b|\bhom\b",
     "a sacred plant and its pressed juice, offered in the Yasna; also a yazata."),
    ("baresman", r"baresman|barsom",
     "a bundle of twigs (now metal rods) the priest holds at worship."),
    ("zaothra", r"zaothras?",
     "the libation, holy water offered at the Yasna."),
    ("Chinvat bridge", r"chinvat|chinwad|kinvat|kinvad|chakât-i-dâîtî|chakat-i-daitik",
     "the bridge every soul crosses after death: wide for the righteous, a blade's edge for the wicked."),
    ("Saoshyant", r"saoshyants?|sôshyans|soshyans|soshyant",
     "\"the one who will bring benefit\": the saviour to come at the end of time, who raises the dead."),
    ("Gathas", r"g[âa]thas?\b",
     "the five hymns of Zarathustra himself, the oldest part of the Avesta (`!verse Gathas 1`)."),
    ("Ahuna Vairya", r"ahuna[- ]vairya|yath[âa] ah[ûu] vairy[ôo]|ahunavar",
     "the holiest prayer, \"Yatha Ahu Vairyo\" (`!prayer ahuna vairya`)."),
    ("Ashem Vohu", r"ashem vohu",
     "the short prayer in praise of asha (`!prayer ashem vohu`)."),
    ("Mazdayasnian", r"mazdayasn[ai]ans?|mazda[- ]worshipp?ers?",
     "a worshipper of Mazda: a Zoroastrian."),
    ("Mathra", r"m[ãa]thras?\b|manthras?",
     "a holy word or formula, whose power is in being spoken rightly."),
    ("ratu", r"\bratus?\b",
     "a spiritual lord or master; also the lord of a time or of a kind of creature."),
    ("khrafstra", r"khrafstras?|khrafstars?",
     "a noxious creature (snakes, insects, vermin), made by the Evil Spirit."),
    ("Airyana Vaejah", r"airyan[ae]m? va[eê]j[ao]h?|aîrân-vêg|airan-vej",
     "\"the Aryan expanse\", the first and best land created, the homeland of the faith."),
    ("Gahambar", r"gahambars?|gahanb[âa]rs?",
     "one of the six seasonal feasts of the year (`!roz` shows when)."),
    ("dakhma", r"dakhmas?",
     "a place where the dead are laid out to the birds, so as not to defile earth or fire; a \"tower of silence\"."),
    ("kusti", r"\bk[ôo]st[îi]\b|\bkusti\b",
     "the sacred cord, tied three times round the waist over the sacred shirt, and retied at prayer."),
    ("dastur, mobad, herbad", r"dast[ûu]rs?|m[ôo]bads?|herbads?",
     "Zoroastrian priests: a dastur is a high priest, a mobad a priest, a herbad a teacher or junior priest."),
]
_TERM_RE = [(name, re.compile(pattern, re.I), meaning) for name, pattern, meaning in TERMS]


def terms_in(text: str) -> list:
    """[(term, meaning)] used in a passage, in the list's order."""
    return [(name, meaning) for name, rx, meaning in _TERM_RE if rx.search(text or "")]


class TermsButton(discord.ui.DynamicItem[discord.ui.Button], template=r"zterms:(?P<ref>.+)"):
    """The meanings of the Avestan words in a passage, looked up again from its reference (so the button
    works after a restart)."""

    def __init__(self, ref: str):
        super().__init__(discord.ui.Button(label="Terms", emoji="🔤", style=discord.ButtonStyle.secondary,
                                           custom_id=f"zterms:{ref}"))
        self.ref = ref

    @classmethod
    async def from_custom_id(cls, interaction, item, match):
        return cls(match["ref"])

    async def callback(self, interaction: discord.Interaction):
        result = lookup.get_verse(self.ref)
        found = terms_in(result.get("text", "")) if result.get("found") else []
        if not found:
            await interaction.response.send_message("I can't find that passage's words any more.", ephemeral=True)
            return
        embed = discord.Embed(title=f"🔤 The words in {self.ref}", color=COLOR,
                              description="\n".join(f"**{name}** — {meaning}" for name, meaning in found)[:4096])
        embed.set_footer(text="Words the translators leave in Avestan or Pahlavi")
        await interaction.response.send_message(embed=embed, ephemeral=True)


bot.add_dynamic_items(TermsButton)


def term_buttons(result: dict) -> list:
    """The 🔤 Terms button for a Zoroastrian passage that uses any of the words; [] for anything else."""
    if not result.get("found") or result.get("tradition") != "zoroastrian":
        return []
    ref = result.get("reference", "")
    if not ref or len(ref) > 90 or not terms_in(result.get("text", "")):
        return []
    return [TermsButton(ref)]
