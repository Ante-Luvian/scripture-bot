"""
!journey: great journeys on a map -- Abraham's, the Exodus, Paul's three
missionary journeys and his voyage to Rome, and more from the Bible; and the
Canterbury pilgrims' road, Odysseus's wanderings and Aeneas's voyage -- each
stop with what happened there and the verse or line that names it.
  !journey               the list
  !journey paul 2        one journey: a route map and its stops

Every stop's verse names the place in the bot's own text (the KJV; Skeat's
Chaucer, Murray's Odyssey, Dryden's Aeneid): tests/test_journeys.py checks it,
as the curated tables elsewhere are checked. The Bible's places are the !place
data (data/people_places/); the others are in PLACES below.
"""
import asyncio
import re

import discord
from discord import app_commands

from core import bot, log, lookup, tradition_enabled
from bot_commands import people

COLOR = discord.Color.from_rgb(150, 50, 40)

# The places of the journeys outside the Bible ("@key" in a route), each where the Wikipedia article named says
# (or its Wikidata entry, where the article gives none). The places of legend are where they were put in
# antiquity, as Wikipedia's "Geography of the Odyssey" and "Aeaea" report it, and who put them there is said in
# the stop's note; all are ringed as uncertain. (St Thomas-a-Watering, the pilgrims' first halt, is left out:
# no coordinates, and two miles from the Tabard.)
PLACES = {
    # the road to Canterbury
    "southwark": ("Southwark", 51.4988, -0.0901, False),                    # (the Tabard stood here)
    "deptford": ("Deptford", 51.478, -0.0265, False),
    "greenwich": ("Greenwich", 51.48, 0.0, False),
    "rochester": ("Rochester", 51.375, 0.5, False),
    "sittingbourne": ("Sittingbourne", 51.34, 0.74, False),
    "boughton": ("Boughton under Blean", 51.292, 0.974, False),
    "harbledown": ("Harbledown", 51.283, 1.054, False),
    "canterbury": ("Canterbury", 51.2797, 1.0831, False),                   # (the cathedral)
    # the Odyssey and the Aeneid
    "troy": ("Troy", 39.9575, 26.2389, False),
    "ismarus": ("Ismarus", 40.9, 25.5167, True),                            # (Mount Ismaros, by Maroneia)
    "malea": ("Cape Malea", 36.4381, 23.1986, False),
    "djerba": ("Djerba", 33.8, 10.8833, True),
    "etna": ("Mount Etna", 37.755, 14.995, True),
    "lipari": ("Lipari", 38.4667, 14.95, True),
    "lentini": ("Lentini", 37.2833, 15.0, True),
    "circeo": ("Mount Circeo", 41.2333, 13.05, True),
    "acheron": ("The Acheron", 39.2362, 20.5345, True),                     # (the Necromanteion)
    "sirenuse": ("The Sirenuse", 40.581, 14.433, True),
    "messina": ("Strait of Messina", 38.2458, 15.6325, True),
    "sicily": ("Sicily", 37.5, 14.0, True),
    "gozo": ("Gozo", 36.05, 14.25, True),
    "corfu": ("Corfu", 39.6, 19.87, True),
    "ithaca": ("Ithaca", 38.3667, 20.7167, False),
    "antandros": ("Antandros", 39.5758, 26.7906, False),
    "aenus": ("Aenus", 40.7222, 26.0833, True),
    "delos": ("Delos", 37.3933, 25.2711, False),
    "crete": ("Crete", 35.21, 24.91, False),
    "strophades": ("The Strophades", 37.25, 21.0, False),
    "actium": ("Actium", 38.953, 20.768, False),
    "buthrotum": ("Buthrotum", 39.7456, 20.0206, False),
    "castro": ("Castrum Minervae", 40.007, 18.4257, True),
    "drepanum": ("Drepanum", 38.0175, 12.515, False),
    "carthage": ("Carthage", 36.8526, 10.3235, False),
    "eryx": ("Eryx", 38.0369, 12.5864, False),
    "cumae": ("Cumae", 40.8486, 14.0536, False),
    "caieta": ("Caieta", 41.2167, 13.5667, False),
    "aetna": ("Mount Etna", 37.755, 14.995, False),                         # (Virgil's, not a guess at Homer's)
    "circeii": ("Mount Circeo", 41.2333, 13.05, False),
    "tiber": ("The Tiber's mouth", 41.7558, 12.2917, False),               # (Ostia)
}

# how a journey's map is drawn when it isn't the Bible's: the region in the corner, and where the places are from
MAPS = {
    "canterbury": {"locator": (-7.0, 49.0, 4.0, 56.5), "credit": "places: Wikipedia"},
    "odyssey": {"locator": (-12.0, 25.0, 45.0, 55.0), "credit": "places: Wikipedia, and as placed in antiquity"},
    "aeneid": {"locator": (-12.0, 25.0, 45.0, 55.0), "credit": "places: Wikipedia"},
}

# key: (title, also called, what it was, [(place slug, verse, the text's spelling, what happened)])
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
    "canterbury": ("The road to Canterbury", ["canterbury tales", "chaucer", "pilgrims", "pilgrimage"],
                   "Chaucer's pilgrims ride from the Tabard inn in Southwark to the shrine of St Thomas Becket at "
                   "Canterbury, telling tales on the way. The places are the ones the Tales name as they pass.", [
        ("@southwark", "The Canterbury Tales 1:3", "Southwerk", "The pilgrims gather at the Tabard inn"),
        ("@deptford", "The Canterbury Tales 5:5", "Depeford", "“Lo, Depeford! and it is half-way pryme”: the Host "
         "hurries the Reeve on"),
        ("@greenwich", "The Canterbury Tales 5:5", "Grenewich", "“Lo, Grenewich, ther many a shrewe is inne”"),
        ("@rochester", "The Canterbury Tales 19:3", "Rouchestre", "“Lo! Rouchestre stant heer faste by!”: the Monk's "
         "turn"),
        ("@sittingbourne", "The Canterbury Tales 28:64", "Sidingborne", "The Summoner promises two or three tales of "
         "friars before Sittingbourne"),
        ("@boughton", "The Canterbury Tales 43:2", "Boghton under Blee", "The Canon and his Yeoman ride up to join "
         "them"),
        ("@harbledown", "The Canterbury Tales 45:2", "Bob-up-and-doun", "“Bob-up-and-doun, Under the Blee”: the Cook "
         "is too drunk to tell his tale"),
        ("@canterbury", "The Canterbury Tales 1:2", "Caunterbury", "“The holy blisful martir for to seke”"),
    ]),
    "odyssey": ("The wanderings of Odysseus", ["odysseus", "ulysses", "homer"],
                "Ten years on the way home from Troy to Ithaca (Odyssey 5–13). Where Homer's places were, nobody "
                "knows; the map follows where they were put in antiquity, each ringed, and says by whom.", [
        ("@troy", "Odyssey 9:39", "Ilios", "Odysseus sets sail for home"),
        ("@ismarus", "Odyssey 9:40", "Ismarus", "He sacks the city of the Cicones, who rally and kill many of his men"),
        ("@malea", "Odyssey 9:80", "Malea", "Rounding Malea, the north wind drives him off course past Cythera"),
        ("@djerba", "Odyssey 9:84", "Lotus-eaters", "The Lotus-eaters' food makes men forget their homecoming "
         "(Djerba, said Polybius and Strabo)"),
        ("@etna", "Odyssey 9:106", "Cyclopes", "The Cyclops Polyphemus shuts them in his cave; Odysseus blinds him "
         "(Sicily by Etna, said Euripides, Thucydides and Strabo)"),
        ("@lipari", "Odyssey 10:1", "Aeolian isle", "Aeolus gives him the winds in a bag; his men open it in sight of "
         "home (Lipari, said Strabo)"),
        ("@lentini", "Odyssey 10:81", "Telepylus", "The Laestrygonians destroy every ship but his (Sicily, said "
         "Thucydides; its south-east, said Strabo)"),
        ("@circeo", "Odyssey 10:135", "Aeaea", "Circe turns his men into swine; he stays a year (Mount Circeo, said "
         "the Roman writers)"),
        ("@acheron", "Odyssey 11:14", "Cimmerians", "At the edge of the world he calls up the dead to question "
         "Teiresias (the river Acheron, said Pausanias)"),
        ("@circeo", "Odyssey 12:3", "Aeaean isle", "Back to Circe, who tells him the dangers to come"),
        ("@sirenuse", "Odyssey 12:167", "Sirens", "Bound to the mast, he hears the Sirens' song (the Sirenuse, one of "
         "the three places Strabo said)"),
        ("@messina", "Odyssey 12:235", "Scylla", "Past Charybdis, Scylla snatches six men (the Strait of Messina, said "
         "Polybius and Strabo)"),
        ("@sicily", "Odyssey 12:262", "island of the god", "Thrinacia: his men eat the Sun's cattle; the ship is "
         "wrecked and he alone lives (later taken for Sicily)"),
        ("@gozo", "Odyssey 12:448", "Ogygia", "Years with the nymph Calypso (Gozo, said Callimachus)"),
        ("@corfu", "Odyssey 5:280", "Phaeacians", "Wrecked again, he swims to the Phaeacians' land (Corfu, said "
         "Thucydides)"),
        ("@ithaca", "Odyssey 13:96", "Ithaca", "The Phaeacians set him down on Ithaca, asleep"),
    ]),
    "aeneid": ("The voyage of Aeneas", ["aeneas", "virgil", "vergil"],
               "From fallen Troy to the mouth of the Tiber, where Rome is to be (Aeneid 1–7). Most of Virgil's places "
               "are real; Aeneas tells the voyage to Dido at Carthage.", [
        ("@troy", "Aeneid 3:3", "Troy", "Troy falls to the Greeks"),
        ("@antandros", "Aeneid 3:7", "Antandros", "Under Mount Ida the exiles build their fleet"),
        ("@aenus", "Aeneid 3:72", "Thracia", "In Thrace a bleeding myrtle tells of murdered Polydorus; they flee "
         "(Aenus: Virgil has Aeneas found it)"),
        ("@delos", "Aeneid 3:108", "Delian", "Apollo's oracle bids them seek their ancient mother"),
        ("@crete", "Aeneid 3:181", "Cretan", "They settle in Crete, until a plague drives them on"),
        ("@strophades", "Aeneid 3:274", "Strophades", "The Harpies foul their feast and curse them"),
        ("@actium", "Aeneid 3:363", "Actian", "Trojan games on the shore at Actium"),
        ("@buthrotum", "Aeneid 3:379", "Buthrotus", "Helenus, Priam's son, reigns here with Hector's widow Andromache, "
         "and foretells the way"),
        ("@castro", "Aeneid 3:696", "Minerva's temple", "First sight of Italy: Minerva's temple on the heights "
         "(Castrum Minervae, now Castro)"),
        ("@aetna", "Aeneid 3:727", "Aetna", "Under Etna they take aboard Achaemenides, left behind by Ulysses, and flee "
         "the Cyclopes"),
        ("@drepanum", "Aeneid 3:931", "Drepanum", "Anchises, Aeneas's father, dies"),
        ("@carthage", "Aeneid 1:468", "Carthage", "A storm drives them to Africa: Dido's Carthage (books 1–4)"),
        ("@eryx", "Aeneid 5:991", "Eryx", "Back in Sicily: games for Anchises, and a temple to Venus on Eryx"),
        ("@cumae", "Aeneid 6:2", "Cumaean", "The Sibyl leads him down to the underworld"),
        ("@caieta", "Aeneid 7:3", "Cajeta", "His old nurse Caieta dies and gives the place her name"),
        ("@circeii", "Aeneid 7:12", "Circe", "They sail by night past Circe's shore"),
        ("@tiber", "Aeneid 7:42", "Tiber", "Into the mouth of the Tiber: Latium, the promised land"),
    ]),
}
BIBLE = [k for k in JOURNEYS if k not in MAPS]


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


def place(slug: str) -> dict:
    """A stop's place: the !place record for the Bible's, or one of PLACES ("@troy")."""
    if slug.startswith("@"):
        name, lat, lon, approx = PLACES[slug[1:]]
        return {"name": name, "lat": lat, "lon": lon, "approx": approx}
    return people.data()["places"][slug]


def stops(key: str) -> list:
    return [(place(slug), ref, note) for slug, ref, _, note in JOURNEYS[key][3]]


def tradition_of(key: str) -> "str | None":
    """The tradition of the text a journey is told in (the Bible's, the classics, medieval English poetry)."""
    return lookup.get_verse(JOURNEYS[key][3][0][1]).get("tradition")


def allowed(guild_id) -> list:
    """The journeys whose texts this server has turned on."""
    return [k for k in JOURNEYS if tradition_enabled(guild_id, tradition_of(k))]


def journey_embed(key: str) -> discord.Embed:
    title, _, about, _ = JOURNEYS[key]
    lines = [f"**{i}. {p['name'].split(' (')[0]}** — {note} ({ref})"
             for i, (p, ref, note) in enumerate(stops(key), 1)]
    text = about + "\n\n" + "\n".join(lines)
    embed = discord.Embed(title=f"🧭 {title}", description=text[:4000], color=COLOR)
    embed.set_image(url="attachment://journey.png")
    if key in MAPS:
        embed.set_footer(text=f"Read a stop with !verse <reference> · {MAPS[key]['credit']}")
    else:
        embed.set_footer(text="Read a stop with !verse <reference> · see a place with !place <name> · "
                              "places: OpenBible.info / Theographic")
    return embed


def list_embed(keys: "list | None" = None) -> discord.Embed:
    keys = list(JOURNEYS) if keys is None else keys

    def line(key):
        return f"**{JOURNEYS[key][0]}** — `!journey {key}` · {len(JOURNEYS[key][3])} stops"
    parts = []
    if any(k in BIBLE for k in keys):
        parts.append("\n".join(line(k) for k in keys if k in BIBLE))
    if any(k in MAPS for k in keys):
        parts.append("**From other books**\n" + "\n".join(line(k) for k in keys if k in MAPS))
    embed = discord.Embed(title="🧭 Journeys", description="\n\n".join(parts) or "None on this server.", color=COLOR)
    embed.set_footer(text="Each one is a map of the route with what happened at every stop")
    return embed


async def map_file(key: str) -> "discord.File | None":
    import bible_map
    style = {"locator": MAPS[key]["locator"], "credit": MAPS[key]["credit"]} if key in MAPS else {}
    try:
        buf = await asyncio.to_thread(bible_map.render_route, JOURNEYS[key][0],
                                      [p for p, _, _ in stops(key)], people.located_places(), **style)
    except Exception:
        log.exception(f"Couldn't draw the journey {key}")
        return None
    return discord.File(buf, filename="journey.png")


class JourneyMenu(discord.ui.View):
    def __init__(self, keys: "list | None" = None):
        super().__init__(timeout=600)
        self.keys = list(JOURNEYS) if keys is None else keys
        options = [discord.SelectOption(label=JOURNEYS[key][0][:100], value=key,
                                        description=f"{len(JOURNEYS[key][3])} stops") for key in self.keys]
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
        await interaction.followup.send(embed=embed, view=JourneyMenu(self.keys), **({"file": file} if file else {}))


async def send_journey(ctx, query: str) -> None:
    query = query.strip()
    guild = getattr(ctx, "guild", None)
    keys = allowed(guild.id if guild else None)
    if not query:
        await ctx.send(embed=list_embed(keys), view=JourneyMenu(keys))
        return
    key = find_journey(query)
    if key is None or key not in keys:
        await ctx.send(f"I don't have a journey called **{discord.utils.escape_markdown(query[:100])}**.",
                       embed=list_embed(keys), view=JourneyMenu(keys))
        return
    file = await map_file(key)
    embed = journey_embed(key)
    if file is None:
        embed.set_image(url=None)
    await ctx.send(embed=embed, view=JourneyMenu(keys), **({"file": file} if file else {}))


@bot.command(name="journey", aliases=["journeys", "route"])
async def cmd_journey(ctx, *, query: str = ""):
    """A journey on a map, with what happened at each stop: the Bible's, Chaucer's pilgrims', Odysseus's, Aeneas's.
    Usage: !journey             — the list
           !journey paul 2      — Paul's second missionary journey
           !journey exodus      — also abraham, paul 1, paul 3, rome, egypt, jonah
           !journey canterbury  — also odyssey, aeneid"""
    async with ctx.typing():
        await send_journey(ctx, query)


@bot.tree.command(name="journey", description="A journey on a map (the Bible, Chaucer, the Odyssey, the Aeneid), "
                                               "with what happened at each stop")
@app_commands.describe(journey="Which journey; empty for the list")
@app_commands.choices(journey=[app_commands.Choice(name=title, value=key)
                               for key, (title, _, _, _) in JOURNEYS.items()])
async def journey_slash(interaction: discord.Interaction, journey: str = ""):
    await interaction.response.defer()
    ctx = await bot.get_context(interaction)
    await send_journey(ctx, journey)
