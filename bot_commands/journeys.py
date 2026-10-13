"""
!journey: the great journeys of the Bible on a map -- Abraham's, the Exodus,
Paul's three missionary journeys and his voyage to Rome, and more -- each
stop with what happened there and the verse that names it.
  !journey               the list
  !journey paul 2        one journey: a route map and its stops

Every stop's verse names the place in the KJV (tests/test_journeys.py checks
it against the local text), as the curated tables elsewhere are checked.
Places are the !place data (data/people_places/).
"""
import asyncio
import re

import discord
from discord import app_commands

from core import bot, log
from bot_commands import people

COLOR = discord.Color.from_rgb(150, 50, 40)

# key: (title, also called, what it was, [(place slug, verse, the KJV's spelling, what happened)])
JOURNEYS = {
    "abraham": ("Abraham's journey", ["abram"],
                "God calls Abram to leave his country for a land He will show him (Genesis 11–22).", [
        ("ur_1189", "Genesis 11:31", "Ur", "Terah sets out from Ur of the Chaldees with Abram, Sarai and Lot"),
        ("haran_527", "Genesis 11:31", "Haran", "They settle in Haran; Terah dies there"),
        ("shechem_1069", "Genesis 12:6", "Sichem", "Abram reaches the oak of Moreh; God promises the land"),
        ("bethel_202", "Genesis 12:8", "Bethel", "He pitches his tent between Bethel and Hai and builds an altar"),
        ("egypt_362", "Genesis 12:10", "Egypt", "Famine drives him down into Egypt"),
        ("bethel_202", "Genesis 13:3", "Bethel", "Back to the altar at Bethel, where Abram and Lot part"),
        ("hebron_551", "Genesis 13:18", "Hebron", "He settles by the oaks of Mamre at Hebron"),
        ("beersheba_170", "Genesis 21:31", "Beersheba", "A covenant with Abimelech at the well of the oath"),
        ("mount_moriah_848", "Genesis 22:2", "Moriah", "“Take now thy son… into the land of Moriah”"),
    ]),
    "exodus": ("The Exodus", ["moses", "wilderness", "wanderings"],
               "Israel leaves Egypt and travels through the wilderness to the edge of the promised land "
               "(Exodus 12 – Joshua 6). Many of these sites are uncertain.", [
        ("rameses_980", "Exodus 12:37", "Rameses", "Israel sets out from Rameses"),
        ("succoth_1114", "Exodus 12:37", "Succoth", "The first camp"),
        ("etham_417", "Exodus 13:20", "Etham", "In the edge of the wilderness, led by the pillar of cloud and fire"),
        ("pi-hahiroth_948", "Exodus 14:2", "Pihahiroth", "Camped by the sea, where the waters part"),
        ("marah_765", "Exodus 15:23", "Marah", "Bitter water made sweet"),
        ("elim_369", "Exodus 15:27", "Elim", "Twelve wells and seventy palm trees"),
        ("sin_1097", "Exodus 16:1", "Sin", "The wilderness of Sin: manna and quails"),
        ("rephidim_996", "Exodus 17:1", "Rephidim", "Water from the rock; the battle with Amalek"),
        ("mount_sinai_855", "Exodus 19:11", "Sinai", "The Ten Commandments and the Law given at Mount Sinai"),
        ("kadesh-barnea_663", "Deuteronomy 1:19", "Kadeshbarnea", "The spies sent out; forty years' wandering"),
        ("mount_hor_842", "Numbers 20:22", "Hor", "Aaron dies on Mount Hor"),
        ("mount_nebo_849", "Deuteronomy 34:1", "Nebo", "Moses sees the promised land, and dies"),
        ("shittim_1086", "Joshua 3:1", "Shittim", "The last camp before crossing the Jordan"),
        ("jericho_634", "Joshua 6:1", "Jericho", "The walls fall"),
    ]),
    "paul1": ("Paul's first missionary journey", ["paul 1", "paul one", "first journey"],
              "Barnabas and Saul (Paul) are sent out from Antioch to Cyprus and Asia Minor (Acts 13–14).", [
        ("antioch_68", "Acts 13:1", "Antioch", "The church at Antioch sends out Barnabas and Saul"),
        ("seleucia_1045", "Acts 13:4", "Seleucia", "Down to the port"),
        ("salamis_1016", "Acts 13:5", "Salamis", "Preaching in the synagogues of Cyprus"),
        ("paphos_919", "Acts 13:6", "Paphos", "Elymas the sorcerer struck blind; the governor believes"),
        ("perga_936", "Acts 13:13", "Perga", "John Mark leaves them"),
        ("antioch_69", "Acts 13:14", "Antioch", "Paul's sermon in the synagogue at Antioch in Pisidia"),
        ("iconium_590", "Acts 13:51", "Iconium", "Driven out, they shake the dust off their feet"),
        ("lystra_742", "Acts 14:8", "Lystra", "A lame man healed; the crowd calls them gods; Paul stoned"),
        ("derbe_330", "Acts 14:20", "Derbe", "Many disciples made"),
        ("lystra_742", "Acts 14:21", "Lystra", "Back again, strengthening the disciples"),
        ("iconium_590", "Acts 14:21", "Iconium", "…and again"),
        ("antioch_69", "Acts 14:21", "Antioch", "…and again, ordaining elders"),
        ("perga_936", "Acts 14:25", "Perga", "Preaching the word"),
        ("attalia_120", "Acts 14:25", "Attalia", "The port"),
        ("antioch_68", "Acts 14:26", "Antioch", "Home, to tell what God had done"),
    ]),
    "paul2": ("Paul's second missionary journey", ["paul 2", "paul two", "second journey"],
              "Paul and Silas revisit the churches, then cross into Europe (Acts 15:36 – 18:22).", [
        ("antioch_68", "Acts 15:35", "Antioch", "Paul and Silas set out"),
        ("derbe_330", "Acts 16:1", "Derbe", "Visiting the churches again"),
        ("lystra_742", "Acts 16:1", "Lystra", "Timothy joins them"),
        ("troas_1182", "Acts 16:8", "Troas", "The vision of the man of Macedonia: “Come over… and help us”"),
        ("samothrace_1025", "Acts 16:11", "Samothracia", "Sailing for Europe"),
        ("neapolis_880", "Acts 16:11", "Neapolis", "Landing in Macedonia"),
        ("philippi_942", "Acts 16:12", "Philippi", "Lydia baptised; Paul and Silas jailed; the earthquake"),
        ("amphipolis_59", "Acts 17:1", "Amphipolis", "On the road west"),
        ("apollonia_76", "Acts 17:1", "Apollonia", "On the road west"),
        ("thessalonica_1158", "Acts 17:1", "Thessalonica", "Three sabbaths of preaching; a riot"),
        ("berea_177", "Acts 17:10", "Berea", "The Bereans search the scriptures daily"),
        ("athens_118", "Acts 17:15", "Athens", "Paul's sermon on Mars' hill: “the unknown god”"),
        ("corinth_306", "Acts 18:1", "Corinth", "Eighteen months with Aquila and Priscilla"),
        ("cenchreae_281", "Acts 18:18", "Cenchrea", "Paul cuts his hair for a vow"),
        ("ephesus_400", "Acts 18:19", "Ephesus", "A short stay; Aquila and Priscilla remain"),
        ("caesarea_266", "Acts 18:22", "Cesarea", "Landing in Judea"),
        ("antioch_68", "Acts 18:22", "Antioch", "Home"),
    ]),
    "paul3": ("Paul's third missionary journey", ["paul 3", "paul three", "third journey"],
              "Paul's long stay at Ephesus, his last visit to Greece, and the journey to Jerusalem "
              "(Acts 18:23 – 21:17).", [
        ("antioch_68", "Acts 18:22", "Antioch", "Setting out once more"),
        ("galatia_431", "Acts 18:23", "Galatia", "Through Galatia and Phrygia, strengthening the disciples"),
        ("ephesus_400", "Acts 19:1", "Ephesus", "Two years' teaching; the silversmiths' riot"),
        ("macedonia_747", "Acts 20:1", "Macedonia", "Encouraging the churches"),
        ("greece_495", "Acts 20:2", "Greece", "Three months"),
        ("philippi_942", "Acts 20:6", "Philippi", "After the days of unleavened bread"),
        ("troas_1182", "Acts 20:6", "Troas", "Eutychus falls from the window during Paul's long sermon"),
        ("assos_110", "Acts 20:13", "Assos", "Paul walks; the others sail"),
        ("mitylene_808", "Acts 20:14", "Mitylene", "Down the coast"),
        ("samos_1024", "Acts 20:15", "Samos", "Down the coast"),
        ("miletus_801", "Acts 20:15", "Miletus", "Farewell to the elders of Ephesus"),
        ("coos_308", "Acts 21:1", "Coos", "Sailing on"),
        ("rhodes_1000", "Acts 21:1", "Rhodes", "Sailing on"),
        ("patara_924", "Acts 21:1", "Patara", "A ship to Phoenicia"),
        ("tyre_1184", "Acts 21:3", "Tyre", "A week with the disciples"),
        ("ptolemais_959", "Acts 21:7", "Ptolemais", "A day with the brethren"),
        ("caesarea_266", "Acts 21:8", "Cesarea", "At Philip's house; Agabus warns of chains"),
        ("jerusalem_636", "Acts 21:17", "Jerusalem", "Welcomed by the brethren — and soon arrested"),
    ]),
    "rome": ("Paul's voyage to Rome", ["paul rome", "shipwreck", "paul 4", "paul four"],
             "Paul, a prisoner who has appealed to Caesar, sails for Rome and is shipwrecked on the way "
             "(Acts 25 – 28).", [
        ("caesarea_266", "Acts 25:4", "Cesarea", "Paul held prisoner; he appeals to Caesar"),
        ("sidon_1093", "Acts 27:3", "Sidon", "Allowed ashore to see his friends"),
        ("myra_864", "Acts 27:5", "Myra", "Onto a ship of Alexandria bound for Italy"),
        ("cnidus_304", "Acts 27:7", "Cnidus", "Slow going against the wind"),
        ("fair_havens_424", "Acts 27:8", "Fair havens", "Paul warns them not to sail on"),
        ("melita_761", "Acts 28:1", "Melita", "Shipwrecked in the storm; the viper; healings on Malta"),
        ("syracuse_1121", "Acts 28:12", "Syracuse", "Three days"),
        ("rhegium_999", "Acts 28:13", "Rhegium", "Waiting for the south wind"),
        ("puteoli_963", "Acts 28:13", "Puteoli", "Landing in Italy; a week with the brethren"),
        ("appii_forum_427", "Acts 28:15", "Appii forum", "Believers from Rome come out to meet him"),
        ("three_taverns_1159", "Acts 28:15", "taverns", "More come to meet him; Paul takes courage"),
        ("rome_1013", "Acts 28:16", "Rome", "Two years under guard, preaching the kingdom of God"),
    ]),
    "egypt": ("The flight into Egypt", ["holy family", "flight", "nativity", "jesus"],
              "Joseph, Mary and the child Jesus escape Herod and return (Matthew 2).", [
        ("bethlehem_218", "Matthew 2:1", "Bethlehem", "Jesus born; the wise men come"),
        ("egypt_362", "Matthew 2:14", "Egypt", "Warned in a dream, Joseph takes the family into Egypt"),
        ("nazareth_878", "Matthew 2:23", "Nazareth", "After Herod's death, home to Nazareth"),
    ]),
    "jonah": ("Jonah's journey", ["jonas"],
              "Jonah runs from God's call, is swallowed by a great fish, and goes to Nineveh after all "
              "(Jonah 1–3).", [
        ("joppa_652", "Jonah 1:3", "Joppa", "Jonah boards a ship for Tarshish, fleeing from the Lord"),
        ("nineveh_899", "Jonah 3:3", "Nineveh", "After the great fish, he preaches and the city repents"),
    ]),
}


def find_journey(query: str) -> "str | None":
    q = re.sub(r"[^a-z0-9 ]+", " ", re.sub(r"['’]s\b", "", query.lower()))
    q = re.sub(r"\s+", " ", q).strip()
    q = re.sub(r"\b(journey|journeys|missionary|the|of|to)\b", " ", q)
    for word, n in (("first", "1"), ("one", "1"), ("second", "2"), ("two", "2"), ("third", "3"), ("three", "3")):
        q = re.sub(rf"\b{word}\b", n, q)
    q = re.sub(r"\s+", " ", q).strip()
    m = re.fullmatch(r"(?:paul ?)?([123])", q)
    if m:
        return f"paul{m.group(1)}"
    for key, (title, also, _, _) in JOURNEYS.items():
        names = [key, title.lower().replace("'s", ""), *also]
        if q in names or q.replace(" ", "") in [n.replace(" ", "") for n in names]:
            return key
    return next((k for k, (title, also, _, _) in JOURNEYS.items()
                 if q and (q in title.lower() or any(q in a for a in also))), None)


def stops(key: str) -> list:
    places = people.data()["places"]
    return [(places[slug], ref, note) for slug, ref, _, note in JOURNEYS[key][3]]


def journey_embed(key: str) -> discord.Embed:
    title, _, about, _ = JOURNEYS[key]
    lines = [f"**{i}. {p['name'].split(' (')[0]}** — {note} ({ref})"
             for i, (p, ref, note) in enumerate(stops(key), 1)]
    text = about + "\n\n" + "\n".join(lines)
    embed = discord.Embed(title=f"🧭 {title}", description=text[:4000], color=COLOR)
    embed.set_image(url="attachment://journey.png")
    embed.set_footer(text="Read a stop with !verse <reference> · see a place with !place <name> · "
                          "places: OpenBible.info / Theographic")
    return embed


def list_embed() -> discord.Embed:
    lines = [f"**{title}** — `!journey {key}` · {len(route)} stops" for key, (title, _, _, route) in JOURNEYS.items()]
    embed = discord.Embed(title="🧭 Journeys of the Bible", description="\n".join(lines), color=COLOR)
    embed.set_footer(text="Each one is a map of the route with what happened at every stop")
    return embed


async def map_file(key: str) -> "discord.File | None":
    import bible_map
    try:
        buf = await asyncio.to_thread(bible_map.render_route, JOURNEYS[key][0],
                                      [p for p, _, _ in stops(key)], people.located_places())
    except Exception:
        log.exception(f"Couldn't draw the journey {key}")
        return None
    return discord.File(buf, filename="journey.png")


class JourneyMenu(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=600)
        options = [discord.SelectOption(label=title[:100], value=key, description=f"{len(route)} stops")
                   for key, (title, _, _, route) in JOURNEYS.items()]
        select = discord.ui.Select(placeholder="Another journey…", options=options)
        select.callback = self._chosen
        self.add_item(select)
        self.select = select

    async def _chosen(self, interaction: discord.Interaction):
        await interaction.response.defer(thinking=True)
        key = self.select.values[0]
        file = await map_file(key)
        embed = journey_embed(key)
        if file is None:
            embed.set_image(url=None)
        await interaction.followup.send(embed=embed, view=JourneyMenu(), **({"file": file} if file else {}))


async def send_journey(ctx, query: str) -> None:
    query = query.strip()
    if not query:
        await ctx.send(embed=list_embed(), view=JourneyMenu())
        return
    key = find_journey(query)
    if key is None:
        await ctx.send(f"I don't have a journey called **{query}**.", embed=list_embed(), view=JourneyMenu())
        return
    file = await map_file(key)
    embed = journey_embed(key)
    if file is None:
        embed.set_image(url=None)
    await ctx.send(embed=embed, view=JourneyMenu(), **({"file": file} if file else {}))


@bot.command(name="journey", aliases=["journeys", "route"])
async def cmd_journey(ctx, *, query: str = ""):
    """A journey from the Bible on a map, with what happened at each stop.
    Usage: !journey             — the list
           !journey paul 2      — Paul's second missionary journey
           !journey exodus      — also abraham, paul 1, paul 3, rome, egypt, jonah"""
    async with ctx.typing():
        await send_journey(ctx, query)


@bot.tree.command(name="journey", description="A journey from the Bible on a map, with what happened at each stop")
@app_commands.describe(journey="Which journey; empty for the list")
@app_commands.choices(journey=[app_commands.Choice(name=title, value=key)
                               for key, (title, _, _, _) in JOURNEYS.items()])
async def journey_slash(interaction: discord.Interaction, journey: str = ""):
    await interaction.response.defer()
    ctx = await bot.get_context(interaction)
    await send_journey(ctx, journey)
