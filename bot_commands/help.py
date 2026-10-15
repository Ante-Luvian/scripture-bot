"""
!help and !translations.
"""
import discord
from translation_lookup import list_translations
from topics_lookup import topic_count
from bot_commands.books import (
    _PLATO_STEPHANUS_RANGES,
)
from core import (
    bot,
)
from bot_commands.votd import (
    DM_DIGEST_TIME,
)

@bot.command(name="help", aliases=["h", "commands", "?"])
async def cmd_help(ctx, *, topic: str = ""):
    """Show help for ScriptureBot commands."""
    topic = topic.strip().lower()

    # ── Topic-specific help ───────────────────────────────────────────────────
    if topic in ("verse", "v", "scripture"):
        embed = discord.Embed(title="📖 !verse — Look Up Scripture", color=discord.Color.dark_gold())
        embed.add_field(name="Basic lookup", value=(
            "`!verse John 3:16` — KJV by default\n"
            "`!verse John 3:16 ESV` — any translation slug\n"
            "`!verse John 3:16 KJV ESV NASB` — parallel display\n"
            "`!verse John 3-5` — full chapters\n"
            "`!verse John 7:53-8:11` — cross-chapter range"
        ), inline=False)
        embed.add_field(name="Random verses", value=(
            "`!verse` — fully random\n"
            "`!verse John` — random from a book\n"
            "`!verse bible ot` / `!verse bible nt` / `!verse bible apocrypha`"
        ), inline=False)
        embed.add_field(name="Ancient languages", value=(
            "`!verse John 3:16 OE` — Old English (Wessex Gospels)\n"
            "`!verse Psalm 23 WLC` — Hebrew (Westminster Leningrad Codex)\n"
            "`!verse John 3:16 TR` — Greek NT (Textus Receptus)\n"
            "`!verse Genesis 1:1 LXX` — Septuagint (Greek OT)\n"
            "`!verse John 3:16 VULG` / `vulgate` / `latin` — Vulgata\n"
            "`!verse John 3:16 peshitta` / `syriac` — Peshitta\n"
            "`!verse John 3:16 CSL` / `slavonic` — Church Slavonic"
        ), inline=False)
        embed.add_field(name="Special translations", value=(
            "`!verse John 3:16 Knox` — Knox Bible\n"
            "`!verse Tobit 1:1 DRB` — Douay-Rheims\n"
            "`!translations` — full list of available translation slugs"
        ), inline=False)
        await ctx.send(embed=embed)
        return

    if topic in ("strong", "strongs"):
        embed = discord.Embed(title="📚 !strong — Strong's Lexicon & Concordance", color=discord.Color.dark_gold())
        embed.description = (
            "`!strong G3588` — Greek lexicon entry\n"
            "`!strong H7225` — Hebrew lexicon entry\n"
            "`!strong John 3:16` — verse with every word tagged with its Strong's number\n"
            "`!strong G26 in John` — every occurrence of that number within one book (concordance)\n\n"
            "Concordance search is scoped to a single canonical Bible book at a time — "
            "a whole-Bible search would mean hundreds of live lookups per query."
        )
        await ctx.send(embed=embed)
        return

    if topic in ("compare", "ancient", "cmp"):
        embed = discord.Embed(title="🏛️ !compare — Multi-Translation View", color=discord.Color.dark_gold())
        embed.description = (
            "`!compare John 3:16` — verse across all English translations\n"
            "`!compare ancient John 3:16` — verse across ancient language witnesses\n"
            "`!compare strong John 3:16` — KJV + original Greek (NT) or Hebrew (OT), each word tagged with its Strong's number\n\n"
            "Ancient NT: KJV · Textus Receptus (Greek) · Vulgate · Peshitta · Church Slavonic · Old English\n"
            "Ancient OT: KJV · Hebrew (WLC) · LXX (Greek) · Vulgate · Peshitta · Church Slavonic · Old English\n"
            "Apocrypha: KJV · LXX · Vulgate · Peshitta · Church Slavonic"
        )
        await ctx.send(embed=embed)
        return

    if topic in ("parallel", "poem", "classical", "par"):
        embed = discord.Embed(title="📜 !parallel — Classical & Poetic Texts", color=discord.Color.dark_gold())
        embed.add_field(name="Usage", value="`!parallel <work> <book>.<lines>`", inline=False)
        embed.add_field(name="Examples", value=(
            "`!parallel Il. 6.440-465` — Iliad (Pope EN + Greek)\n"
            "`!parallel Aen. 4.1-30` — Aeneid (Dryden EN + Latin)\n"
            "`!parallel Met. 1.1-20` — Metamorphoses (Garth/Dryden + Latin)\n"
            "`!parallel Heliand 1.1-30` — Heliand (Scott EN + Old Saxon)\n"
            "`!parallel Republic 1.1-20` — Plato (Loeb English + Greek)\n"
            "`!parallel` — full list of available works"
        ), inline=False)
        embed.add_field(name="Plato — Stephanus ranges", value="\n".join(
            f"`{name}` — {first}–{last}"
            for name, (first, last) in _PLATO_STEPHANUS_RANGES.items()
        ), inline=False)
        await ctx.send(embed=embed)
        return

    if topic in ("books", "book"):
        embed = discord.Embed(title="📚 !books — Browse Collections", color=discord.Color.dark_gold())
        embed.description = (
            "`!books` — browse all loaded scripture collections\n"
            "`!books Genesis` — show Genesis chapter/verse breakdown\n"
            "`!books Augustine` — list works by an author\n\n"
            "The interactive menu lets you drill down into categories. "
            "Click any book name to see its chapter and verse counts."
        )
        embed.add_field(name="Citation formats by corpus", value=(
            "**Bible** — `!verse John 3:16` · `!verse Genesis 1:1-3`\n"
            "**Apocrypha** — `!verse Sirach 24:1` · `!verse 1 Maccabees 2:1`\n"
            "**Mishnah** — `!verse Berakhot 1:1` *(tractate chapter:mishnah)*\n"
            "**Babylonian Talmud** — `!verse Berakhot 2a:3` *(tractate daf-side:section)*\n"
            "**Jerusalem Talmud** — `!verse Jerusalem Talmud Berakhot 1:1` *(ch:halakhah)*\n"
            "**Tosefta** — `!verse Tosefta Berakhot 1:1` *(chapter:halakhah)*\n"
            "**Targum Onkelos** — `!verse Targum Onkelos Genesis 1:1`\n"
            "**Targum Jonathan** — `!verse Targum Jonathan Isaiah 1:1`\n"
            "**Midrash Rabbah** — `!verse Bereshit Rabbah 1:1` *(section:subsection)*\n"
            "**Zohar** — `!verse Zohar Bereshit 5` *(parasha + segment)*\n"
            "**Sefer Yetzirah** — `!verse Sefer Yetzirah 1:1` · **Tanya** — `!verse Tanya 1:1`\n"
            "**Quran** — `!verse Quran 2:255` · **Hadith** — `!verse Sahih al-Bukhari 1:1`\n"
            "**Homer** — `!verse Iliad 6.440` *(book.line)* · `!verse Odyssey 1` *(a whole book)*\n"
            "**Plato** — `!verse Republic 514a` *(Stephanus)* · ranges: `!verse Republic 361e-362a` · `!help books` for full list"
        ), inline=False)
        await ctx.send(embed=embed)
        return

    if topic in ("votd", "verseoftheday", "dayverse"):
        embed = discord.Embed(title="🌅 !votd — Verse of the Day", color=discord.Color.dark_gold())
        embed.description = (
            "`!votd` — today's verse (from verseoftheday.com, KJV)\n"
            "`!votd ESV` — verse of the day in a specific translation\n"
            "`!votd full` — KJV verse + ancient translations + first patristic commentary\n"
            "`!votd extended` — full VOTD + today's calendar across all five traditions\n\n"
            "A new verse is posted automatically each day in this server's configured channel — "
            "server admins can set that up with `!help votdsetup`."
        )
        await ctx.send(embed=embed)
        return

    if topic in ("features", "feature"):
        embed = discord.Embed(title="⚙️ !features — Optional Server Features", color=discord.Color.dark_gold())
        embed.description = (
            "All off by default. Requires Administrator permission to change.\n\n"
            "`!features` — show current on/off state for this server\n"
            "`!features react_save on` — react 📌 to a verse embed to bookmark it\n"
            "`!features streaks on` — show your `!plan` check-in streak\n"
            "`!features export on` — let `!saved export` send your full bookmark list as a text file"
        )
        await ctx.send(embed=embed)
        return

    if topic in ("votdsetup", "votdconfig"):
        embed = discord.Embed(title="⚙️ !votdsetup — Configure Daily VOTD (Admin)", color=discord.Color.dark_gold())
        embed.description = (
            "Each server picks its own channel, time, and mode for the daily Verse of the Day post.\n\n"
            "`!votdsetup` — show this server's current config\n"
            "`!votdsetup channel #general` — set the announcement channel\n"
            "`!votdsetup time 04:00` — set the post time (24h UTC)\n"
            "`!votdsetup mode full` — `basic` (verse only) · `full` (+ ancients + commentary) · `extended` (+ calendar)\n"
            "`!votdsetup off` — disable daily VOTD for this server\n\n"
            "Requires Administrator permission."
        )
        await ctx.send(embed=embed)
        return

    if topic in ("discover",):
        embed = discord.Embed(title="🔭 !discover — Random Passage, Any Tradition", color=discord.Color.dark_gold())
        embed.description = (
            "`!discover` — a random passage from any loaded tradition: scripture, LDS scripture, "
            "Septuagint, Enoch/Jubilees, Apostolic Fathers, Quran, classical texts, Jewish texts, "
            "Baha'i, Gnostic, Dharmic, Norse, Ancient Near Eastern, patristics, and medieval sources.\n\n"
            "Same underlying picker as bare `!verse` — `!discover` is just the more obvious name for it."
        )
        await ctx.send(embed=embed)
        return

    if topic in ("study",):
        embed = discord.Embed(title="🔎 !study — Verse + Patristic Commentary", color=discord.Color.dark_gold())
        embed.description = (
            "`!study John 3:16` — looks up the verse, then shows patristic commentary on it "
            "(from catenabible.com), in one command instead of two.\n\n"
            "Equivalent to running `!verse` followed by `!catena` on the same reference."
        )
        await ctx.send(embed=embed)
        return

    if topic in ("interlinear", "inter", "il"):
        embed = discord.Embed(title="🔤 !interlinear — Word-by-Word Image", color=discord.Color.dark_gold())
        embed.description = (
            "`!interlinear John 3:16` — Greek NT interlinear\n"
            "`!interlinear Psalm 23:1` — Hebrew OT interlinear\n\n"
            "Renders each word of the original text with its transliteration and short gloss "
            "stacked underneath, as an image — built on the same Strong's tagging as `!strong`. "
            "Hebrew columns read right-to-left, matching a printed Hebrew interlinear.\n\n"
            "Capped at 60 tagged words per verse (image width limit)."
        )
        await ctx.send(embed=embed)
        return

    if topic in ("reverseinterlinear", "rinterlinear", "ril", "kjvinterlinear"):
        embed = discord.Embed(title="🔤 !reverseinterlinear — KJV Reading-Order Interlinear", color=discord.Color.dark_gold())
        embed.description = (
            "`!reverseinterlinear John 3:16`\n\n"
            "Shows the actual KJV verse text in its own natural English word order "
            "(unlike `!interlinear`, which orders by the original Greek/Hebrew) — each "
            "English word or phrase tagged with the Strong's number of the word(s) it "
            "translates. A Hebrew or Greek word often covers more than one English word "
            "(e.g. \"In the beginning\" is a single Hebrew word); the tag covers the "
            "whole phrase in that case.\n\n"
            "Capped at 60 tagged words per verse (image width limit)."
        )
        await ctx.send(embed=embed)
        return

    if topic in ("timeline", "chronology"):
        embed = discord.Embed(title="🗓️ !timeline — Chronological Placement", color=discord.Color.dark_gold())
        embed.description = (
            "`!timeline Abraham` — where a person, book, or event falls in James Ussher's "
            "chronology (Annals of the World, 1658, public domain), with the entries just "
            "before and after for context.\n\n"
            "Dates follow Ussher's own reckoning specifically, not a modern scholarly consensus — "
            "useful alongside `!study` for seeing where things fall relative to each other."
        )
        await ctx.send(embed=embed)
        return

    if topic in ("dictionary", "dict", "define"):
        embed = discord.Embed(title="📔 !dictionary — Bible Dictionary", color=discord.Color.dark_gold())
        embed.description = (
            "`!dictionary Aaron` — look up a person, place, or term\n\n"
            "Combines Easton's Bible Dictionary (1897) and Smith's Bible Dictionary (1863), "
            "both public domain — encyclopedia-style background, distinct from `!topic`'s "
            "thematic scripture outlines and `!strong`'s word-level Greek/Hebrew lexicon."
        )
        await ctx.send(embed=embed)
        return

    if topic in ("save", "saved", "unsave", "bookmark", "bookmarks"):
        embed = discord.Embed(title="📌 Personal Bookmarks", color=discord.Color.dark_gold())
        embed.description = (
            "`!save John 3:16` — save a verse to your personal list\n"
            "`!save John 3:16 | this got me through a hard week` — save with a personal note\n"
            "`!saved` — show your saved verses (with any notes)\n"
            "`!unsave 2` — remove saved verse #2 (number from `!saved`)\n\n"
            "Saving an already-saved verse with a new `| note` updates the note instead of "
            "duplicating the entry.\n\n"
            "Bookmarks are personal — only you can see and manage your own list."
        )
        await ctx.send(embed=embed)
        return

    if topic in ("plan", "readingplan"):
        embed = discord.Embed(title="📅 !plan — Reading Plan", color=discord.Color.dark_gold())
        embed.description = (
            "`!plan start John` — start a chapter-a-day plan through a book\n"
            "`!plan` or `!plan today` — show today's assigned chapter\n"
            "`!plan status` — see your progress\n"
            "`!plan remind on` — get each day's chapter by DM (07:00 UTC, or `!plan remind on 19:30`)\n"
            "`!plan remind off` — stop the reminders\n"
            "`!plan stop` — cancel your plan\n\n"
            "One plan per person. The chapter shown advances automatically by date, "
            "not by how often you check in."
        )
        await ctx.send(embed=embed)
        return

    if topic in ("memorize", "memorise", "learn"):
        embed = discord.Embed(title="🧠 !memorize — Learn a Verse by Heart", color=discord.Color.dark_gold())
        embed.description = (
            "`!memorize John 3:16` — the verse with a quarter of its words blanked out\n"
            "  **Harder** / **Easier** — more or fewer blanks (4 levels; the last leaves first letters only)\n"
            "  **Reveal** — check yourself (only you see it)\n"
            "  **🔔 Remind me** — practise it again by DM after 1, 3, 7, 14 and 30 days (08:00 UTC)\n"
            "`!memorize list` — your verses and when each review is due\n"
            "`!memorize stop John 3:16` — stop reviewing one\n\n"
            "Up to a few verses at a time, e.g. `!memorize Psalm 23:1-3`."
        )
        await ctx.send(embed=embed)
        return

    if topic in ("harmony", "gospels", "synoptic"):
        embed = discord.Embed(title="📖 !harmony — The four Gospels side by side", color=discord.Color.dark_gold())
        embed.description = (
            "`!harmony feeding five thousand` — an event, found by words from it\n"
            "`!harmony Mark 6:41` — the event a verse belongs to\n"
            "`!harmony 72` — an event by its number (1 to 184)\n"
            "`!harmony` — a random event told by more than one Gospel\n\n"
            "Each Gospel's account is shown side by side, with buttons to read any of them in full and to "
            "step to the event before or after. The order of events follows A. T. Robertson's "
            "*A Harmony of the Gospels* (1922)."
        )
        await ctx.send(embed=embed)
        return

    if topic in ("journey", "journeys", "route"):
        embed = discord.Embed(title="🧭 !journey — Journeys on a map", color=discord.Color.dark_gold())
        embed.description = (
            "`!journey` — the list\n"
            "`!journey paul 2` — Paul's second missionary journey (also `paul 1`, `paul 3`)\n"
            "`!journey rome` — Paul's voyage and shipwreck on the way to Rome\n"
            "`!journey exodus` · `!journey abraham` · `!journey egypt` (the flight into Egypt) · `!journey jonah`\n\n"
            "Each is a map with the stops numbered in order and joined by arrows, and a list of what "
            "happened at each stop with the verse that tells it. A dashed ring means nobody is sure "
            "exactly where the place was."
        )
        await ctx.send(embed=embed)
        return

    if topic in ("kings", "king", "monarchs"):
        embed = discord.Embed(title="👑 !kings — The kings of Israel and Judah", color=discord.Color.dark_gold())
        embed.description = (
            "`!kings` — a chart of every king from Saul to Zedekiah: the united kingdom, then Israel and Judah "
            "side by side, each reign a block as long as the Bible says it lasted, coloured by the Bible's "
            "verdict on it (green: “did that which was right”, red: “did evil”, gold: both).\n"
            "`!kings Hezekiah` — one king: how long he reigned and the verdict, quoted, with the verses.\n\n"
            "Reigns overlapped, so the chart stacks them in order rather than on a timeline."
        )
        await ctx.send(embed=embed)
        return

    if topic in ("measure", "measures", "weights", "money", "convert"):
        embed = discord.Embed(title="📏 !measure — Bible weights, measures and money", color=discord.Color.dark_gold())
        embed.description = (
            "`!measure` — the list: cubits, shekels, talents, ephahs, pence and more\n"
            "`!measure talent` — what a unit was, its size today, and verses that use it\n"
            "`!measure 300 cubits` — a conversion (`three hundred cubits` and `half a shekel` work too)\n"
            "`!measure Genesis 6:15` — every measurement in a verse, converted (the size of the ark)\n\n"
            "Sizes today are the estimates of Easton's Bible Dictionary (1897), quoted with each unit; "
            "ancient measures varied, so treat them as rough. Money is given in denarii, a labourer's "
            "pay for a day (Matthew 20:2), and in dollars from Easton's 1897 values adjusted for inflation."
        )
        await ctx.send(embed=embed)
        return

    if topic in ("versle", "dailyverse"):
        embed = discord.Embed(title="📜 !versle — Versle, the daily verse puzzle", color=discord.Color.dark_gold())
        embed.description = (
            "Every day everyone gets the same well-known verse. Where in the Bible is it? Press **✍️ Guess** "
            "and type a verse (`John 3:16`); you have six tries.\n\n"
            "After each guess I tell you, privately, how close you were: 🟩 right, 🟨 within three, "
            "⬛ further off — for the book, then the chapter, then the verse — and which way to go "
            "(\"later in the Bible, by 5 books\").\n\n"
            "When you're done, **📣 Share my result** posts your squares (not the answer) for the channel.\n"
            "`!versle stats` — your record and streak. A new verse at midnight UTC.\n\n"
            "**Admins:** `!verslesetup channel #chan` posts each day's puzzle there, with yesterday's "
            "answer and how many solved it (`time HH:MM` UTC, `test`, `off`)."
        )
        await ctx.send(embed=embed)
        return

    if topic in ("whoami", "mystery", "whoisit"):
        embed = discord.Embed(title="🕵️ !whoami — Who Am I?", color=discord.Color.dark_gold())
        embed.description = (
            "I think of someone from the Bible and give you a clue. **💡 Next clue** gives an easier one — "
            "their family, where they lived and died, what their name means, a verse with their name "
            "hidden, their relatives' names, and last of all the first letter.\n\n"
            "Anyone in the channel can press **✍️ Guess** — one guess per clue each — and the first right "
            "answer wins. Other names count too (`Israel` for Jacob, `Cephas` for Peter). "
            "**🏳️ Give up** shows who it was."
        )
        await ctx.send(embed=embed)
        return

    if topic in ("tree", "familytree", "lineage", "genealogy"):
        embed = discord.Embed(title="🌳 !tree — Family trees", color=discord.Color.dark_gold())
        embed.description = (
            "`!tree David` — a picture of someone's family: grandparents and parents above, brothers and "
            "sisters beside, husband or wives, and children below, with their line of fathers across the top\n"
            "`!tree Abraham to David` — every generation from one person down to another, as a chart "
            "(either order works; try `!tree Adam to Jesus`)\n\n"
            "From the Bible's genealogies and family records (Theographic Bible Metadata). When a name is "
            "shared, I draw the best-known one and list the others — `!who <name>` tells them apart."
        )
        await ctx.send(embed=embed)
        return

    if topic in ("who", "person", "whois"):
        embed = discord.Embed(title="👤 !who — People of the Bible", color=discord.Color.dark_gold())
        embed.description = (
            "`!who Ruth` — who she was, her family and tribe, where she was born and died, "
            "and every verse that names her\n"
            "`!who Mary` — when several people share a name, pick the one you mean from a list\n"
            "`!who John all` — list everyone of that name\n\n"
            "The menu under a card opens a parent, spouse, child or sibling, so you can walk a family "
            "tree (Ruth → Obed → Jesse → David). About 3,000 people, from Theographic Bible Metadata; "
            "descriptions from Easton's Bible Dictionary."
        )
        await ctx.send(embed=embed)
        return

    if topic in ("place", "where", "map"):
        embed = discord.Embed(title="📍 !place — Places of the Bible", color=discord.Color.dark_gold())
        embed.description = (
            "`!place Bethel` — a map card marking it, with nearby places named, what it was, "
            "who was born or died there, and every verse that names it\n"
            "`!place Sea of Galilee` · `!place Rome` · `!place Ur`\n\n"
            "Where a site is uncertain the map says so and rings the likely spot. About 1,250 places; "
            "locations from OpenBible.info, maps drawn from Natural Earth."
        )
        await ctx.send(embed=embed)
        return

    if topic in ("hymn", "hymns", "hymnal", "midi", "tune", "hymnlist", "hymnday", "hymndaysetup", "chant", "sing"):
        embed = discord.Embed(title="🎵 !hymn — Hymns", color=discord.Color.dark_gold())
        embed.description = (
            "`!hymn amazing grace` — by title, first line, or a line from the words\n"
            "`!hymn christmas` — hymns on a topic\n"
            "`!hymn Psalm 23` — hymns drawn from a passage\n"
            "`!hymn` — a random hymn\n"
            "`!midi amazing grace` — just the tune, no words (`!midi` alone: a random one)\n"
            "`!chant Pater noster` — a Latin chant sung, straight away (`!chant` alone: a random one)\n"
            "`!hymnlist` — the whole hymnal by title (`!hymnlist all`, `!hymnlist chant`, `!hymnlist veni`)\n"
            "`!hymnday` — the hymn of the day, chosen for the Church year (`!hymnday 2026-12-25` for another day)\n"
            "**Admins:** `!hymndaysetup channel #chan` posts it every day (`time HH:MM` UTC, `test`, `off`)\n\n"
            "**▶️ Play the tune** posts the hymn tune, once through in four parts on an organ, as audio "
            "you can play in Discord. **📖 Read the passages** shows the Bible verses "
            "the hymn draws on. About 290 public-domain hymns, from the Open Hymnal Project and Hymnary.org.\n\n"
            "**Ancient hymns:** 720 Latin hymns, sequences, antiphons and chants of the Mass in Gregorian chant, with the "
            "chant to play — `!hymn Salve Regina`, `!hymn Te lucis`, `!hymn Dies irae`, `!hymn Ubi caritas`. "
            "**The Sacred Harp:** all 550 songs, sung in four parts — `!hymn Idumea`, `!hymn Babylon is fallen`, "
            "`!hymnlist harp`."
        )
        await ctx.send(embed=embed)
        return

    if topic in ("metrical", "metricalpsalm", "singpsalm", "psalter1650"):
        embed = discord.Embed(title="🎶 !metrical — The Scottish Metrical Psalter", color=discord.Color.dark_gold())
        embed.description = (
            "The Psalms in rhymed, regular verse for a congregation to sing, from the Scottish Psalter "
            "of 1650 — still sung in Scottish churches, and the source of *The Lord's my shepherd, "
            "I'll not want*.\n\n"
            "`!metrical 23` — Psalm 23 in metre, with the tune it's sung to (also `!psalm 23 sing`)\n"
            "`!psalm 110 chant` — a psalm chanted in Latin to a Gregorian psalm tone, with the English (`organ` for the organ)\n"
            "`!metrical 100b` — a psalm's second version, where the Psalter has two\n"
            "`!metrical 119:105-112` — just the stanzas for those verses\n"
            "`!metrical 119 nun` — one of Psalm 119's 22 lettered parts (Aleph, Beth, Gimel…)\n"
            "`!metrical shepherd` — psalms with those words; `!metrical crimond` lists a tune's psalms\n"
            "`!metrical` — a random psalm\n\n"
            "Stanzas are numbered by the Bible verse they start at, as in the old psalm books. "
            "**▶️ Play the tune** posts one verse of the tune in four parts on an organ — every stanza "
            "is sung to it. The menu plays the psalm's other possible tunes (any tune in the same meter "
            "fits the words). **📖 Read in the KJV** shows the same psalm in prose."
        )
        await ctx.send(embed=embed)
        return

    if topic in ("leaderboard", "lb"):
        embed = discord.Embed(title="🏆 !leaderboard — Bookmark Leaderboard", color=discord.Color.dark_gold())
        embed.description = (
            "`!leaderboard` — shows who has saved the most verses with `!save`.\n\n"
            "For overall bot usage (most cited verses/books/commands), see `!stats` instead."
        )
        await ctx.send(embed=embed)
        return

    if topic in ("prefer", "preference", "defaulttranslation"):
        embed = discord.Embed(title="⭐ !prefer — Default Translation", color=discord.Color.dark_gold())
        embed.description = (
            "`!prefer ESV` — set your default translation\n"
            "`!prefer` — show your current default\n"
            "`!prefer off` — clear it (back to local KJV)\n\n"
            "Once set, plain `!verse John 3:16` uses your default automatically. "
            "An explicit suffix (`!verse John 3:16 NASB`) always overrides it for that one lookup.\n\n"
            "Only affects standard Bible books covered by that translation — references like "
            "Enoch, Mishnah, or Quran fall back to their normal local text regardless."
        )
        await ctx.send(embed=embed)
        return

    if topic in ("xref", "xrefs", "crossref", "crossreference"):
        embed = discord.Embed(title="🔗 !xref — Cross-References", color=discord.Color.dark_gold())
        embed.description = (
            "`!xref John 3:16` — up to 15 related verses, most-attested first\n\n"
            "From the Treasury of Scripture Knowledge (public domain, ~340,000 references), "
            "via openbible.info's structured dataset (CC-BY). Covers the 66-book Protestant canon only."
        )
        await ctx.send(embed=embed)
        return

    if topic in ("notes", "netnotes", "netnote"):
        embed = discord.Embed(title="📝 !notes — NET Bible Notes", color=discord.Color.dark_gold())
        embed.description = (
            "`!notes John 3:16` — the NET Bible translators' notes for a verse\n"
            "`!notes Genesis 1:1-3` — several verses at once (up to 5)\n\n"
            "Three kinds of note: **translator's notes** (why a word was rendered as it was, and "
            "the alternatives), **study notes** (background and interpretation), and "
            "**text-critical notes** (where the manuscripts differ).\n\n"
            "Notes © Biblical Studies Press; the title links to the chapter on netbible.org."
        )
        await ctx.send(embed=embed)
        return

    if topic in ("topic", "topics", "naves", "topical"):
        embed = discord.Embed(title="📚 !topic — Nave's Topical Bible", color=discord.Color.dark_gold())
        embed.description = (
            f"`!topic love` — browse scripture organized by subject ({topic_count()} subjects)\n\n"
            "Gives you the full outline for that subject, with embedded scripture citations, exactly "
            "as Nave arranged it — not individual verse links like `!xref`.\n\n"
            "If your exact wording isn't a subject, you'll get a list of similar subject names to try."
        )
        await ctx.send(embed=embed)
        return

    if topic in ("card", "versecard", "quotecard"):
        embed = discord.Embed(title="🖼️ !card — Shareable Verse Image", color=discord.Color.dark_gold())
        embed.description = (
            "`!card John 3:16` — renders the verse as a parchment-style PNG you can share\n"
            "`!card` — random verse, same style\n\n"
            "Same underlying lookup as `!verse`, just rendered as an image instead of an embed."
        )
        await ctx.send(embed=embed)
        return

    if topic in ("subscribe", "unsubscribe", "dm"):
        embed = discord.Embed(title="📬 Daily Verse by DM", color=discord.Color.dark_gold())
        embed.description = (
            f"`!subscribe` — get the daily Verse of the Day sent to your DMs (around {DM_DIGEST_TIME} UTC)\n"
            "`!unsubscribe` — stop it\n\n"
            "Independent of any server's `!votdsetup` channel post — this goes straight to you."
        )
        await ctx.send(embed=embed)
        return

    if topic in ("today", "calendar", "liturgy", "feast", "saint"):
        embed = discord.Embed(title="📅 !today — Liturgical & Religious Calendar", color=discord.Color.dark_gold())
        embed.description = (
            "What's going on today across religious traditions — feast days, "
            "saints, liturgical seasons, Hebrew/Hijri dates and holidays."
        )
        embed.add_field(name="Usage", value=(
            "`!today` — today, all five traditions\n"
            "`!today christian` — Catholic + Anglican + Orthodox in one embed\n"
            "`!today anglican` — Common Worship calendar (Church of England)\n"
            "`!today catholic` — Roman Rite (General Calendar)\n"
            "`!today orthodox` — Eastern Orthodox commemorations + fasting info\n"
            "`!today jewish` — Hebrew date + Jewish observances\n"
            "`!today islam` — Hijri date + Islamic holidays\n"
            "`!today catholic 2026-12-25` — any tradition + a specific date\n"
            "`!today 12-25` — MM-DD with the current year"
        ), inline=False)
        embed.add_field(name="Sources", value=(
            "Catholic — universalis.com · "
            "Anglican — bundled Common Worship calendar + Easter computus · "
            "Orthodox — orthocal.info · "
            "Jewish — hebcal.com · "
            "Islamic — api.aladhan.com"
        ), inline=False)
        await ctx.send(embed=embed)
        return

    if topic in ("bcp", "office", "matins", "evensong", "vespers", "mp", "ep"):
        embed = discord.Embed(title="📖 !bcp — Book of Common Prayer Daily Office",
                              color=discord.Color.dark_blue())
        embed.description = (
            "The Psalms, lessons, and Collect appointed for Morning or Evening Prayer, "
            "from the Canadian 1962 BCP (with 1922 daily-office lectionary) and the "
            "Coverdale Psalter on its 30-day cycle. KJV text for the lessons.\n\n"
            "Pages are paginated with ◀ ▶ buttons. Midnight–noon defaults to Morning Prayer, "
            "noon–midnight to Evening Prayer."
        )
        embed.add_field(name="The full office", value=(
            "`!bcp` — today, time-appropriate\n"
            "`!bcp morning` / `!bcp evening` — full office for that period\n"
            "`!bcp 2026-12-25` — full office for a specific date"
        ), inline=False)
        embed.add_field(name="Individual pieces", value=(
            "`!bcp mp` / `!mp` — both lessons for Morning Prayer\n"
            "`!bcp ep` / `!ep` — both lessons for Evening Prayer\n"
            "`!bcp 1` / `!bcp 2` — first or second lesson, time-appropriate\n"
            "`!bcp psalm` / `!psalm` — psalms for the current period\n"
            "`!psalm mp` / `!psalm ep` — psalms for that specific period\n"
            "`!psalm 110 chant` — a psalm chanted in Latin, with the Douay-Rheims English\n"
            "`!bcp collect` / `!collect` — the Collect of the Day\n"
            "`!bcp prayer` / `!prayer` — a random devotional prayer · `!help prayer`"
        ), inline=False)
        embed.add_field(name="Notes", value=(
            "• The lectionary year (I/II) is computed from the most-recent Advent Sunday.\n"
            "• On a Red-Letter Saint's Day the daily lessons are still used, but the "
            "Saint's collect is shown in place of the seasonal one.\n"
            "• Sources: lectionarycentral.com (lessons), BCP 1662 (psalter & collects)."
        ), inline=False)
        await ctx.send(embed=embed)
        return

    if topic in ("prayer", "collect"):
        embed = discord.Embed(title="📿 !prayer — Prayers",
                              color=discord.Color.dark_purple())
        embed.description = (
            "`!prayer st michael` — a traditional prayer by name, in English and Latin, with its chant sung "
            "where it has one (the Memorare, Anima Christi, Salve Regina, Our Father, Hail Mary…)\n"
            "`!prayer list` — the prayers I have\n"
            "`!prayer` — a random devotional prayer from the Book of Common Prayer 1662"
        )
        embed.add_field(name="Usage", value=(
            "`!prayer` — a random prayer/collect (alias for `!bcp prayer`)\n"
            "`!collect` — the Collect of the Day (alias for `!bcp collect`)\n"
            "`!collect 2026-12-25` — collect for a specific date"
        ), inline=False)
        embed.add_field(name="Sources drawn from", value=(
            "Fixed collects of Morning and Evening Prayer (Collect for Peace, Grace, "
            "Aid against all Perils, Prayer of Saint Chrysostom)\n"
            "Prayers upon Several Occasions and the Thanksgivings\n"
            "The General Confession and Collect for Purity\n"
            "Prayers from the Visitation of the Sick, Burial of the Dead, and "
            "Forms of Prayer at Sea\n"
            "Seasonal Sunday collects (filtered to exclude state and saint's-day collects)"
        ), inline=False)
        await ctx.send(embed=embed)
        return

    if topic in ("strong", "strongs", "concordance"):
        embed = discord.Embed(title="📚 !strong — Strong's Concordance", color=discord.Color.dark_gold())
        embed.description = (
            "Look up a Strong's number for definitions, transliteration, "
            "pronunciation, and gloss — or pass a verse to see each word "
            "tagged with its Strong's number."
        )
        embed.add_field(name="Lexicon lookup", value=(
            "`!strong G3588` — Greek NT (Thayer's Greek Lexicon)\n"
            "`!strong H7225` — Hebrew OT (Brown-Driver-Briggs)"
        ), inline=False)
        embed.add_field(name="Tagged verse (alias for !compare strong)", value=(
            "`!strong John 3:16` — KJV + every Greek word tagged with its Strong's number\n"
            "`!strong Psalm 23:1` — same, for Hebrew OT"
        ), inline=False)
        embed.set_footer(text="Source: bolls.life")
        await ctx.send(embed=embed)
        return

    if topic in ("jewish", "rabbinic", "talmud", "mishnah", "zohar", "kabbalah"):
        embed = discord.Embed(title="✡️ Jewish Texts — Citation Guide", color=discord.Color.dark_gold())
        embed.add_field(name="Mishnah  (chapter:mishnah)", value=(
            "`!verse Berakhot 1:1`\n`!verse Avot 2:1`\n`!verse Pirkei Avot 3:14`"
        ), inline=True)
        embed.add_field(name="Babylonian Talmud  (tractate daf-side[:section])", value=(
            "`!verse Berakhot 2a`  *(whole daf)*\n"
            "`!verse Berakhot 2a:3`  *(section 3)*\n"
            "`!verse Shabbat 31a:1`\n"
            "daf = page + `a` (front) or `b` (back)"
        ), inline=False)
        embed.add_field(name="Jerusalem Talmud  (chapter:halakhah)", value=(
            "`!verse Jerusalem Talmud Berakhot 1:1`\n"
            "`!verse Yerushalmi Shabbat 2:1`\n"
            "39 tractates available via Sefaria (Guggenheimer trans.)"
        ), inline=False)
        embed.add_field(name="Tosefta  (chapter:halakhah)", value=(
            "`!verse Tosefta Berakhot 1:1`\n`!verse Tosefta Shabbat 2:3`"
        ), inline=True)
        embed.add_field(name="Targumim  (chapter:verse)", value=(
            "`!verse Targum Onkelos Genesis 1:1`  *(Torah)*\n"
            "`!verse Targum Jonathan Isaiah 6:1`  *(Prophets)*\n"
            "`!verse Targum Pseudo-Jonathan Genesis 1:1`\n"
            "`!verse Targum Neofiti Genesis 1:1`"
        ), inline=False)
        embed.add_field(name="Midrash  (section:subsection)", value=(
            "`!verse Bereshit Rabbah 1:1`\n"
            "`!verse Shemot Rabbah 1:1`\n"
            "`!verse Mechilta 1:1`  ·  `!verse Sifra 1:1`\n"
            "`!verse Pirkei DeRabbi Eliezer 1:1`"
        ), inline=False)
        embed.add_field(name="Zohar  (parasha + segment)", value=(
            "`!verse Zohar Bereshit 5`\n"
            "`!verse Zohar Introduction 1`\n"
            "`!verse Zohar`  *(random)*\n"
            "54 parashot — use `!books` → Kabbalah → Zohar for full list"
        ), inline=True)
        embed.add_field(name="Other Kabbalah  (chapter:verse)", value=(
            "`!verse Sefer Yetzirah 1:1`\n"
            "`!verse Sefer HaBahir 1:1`\n"
            "`!verse Tikkunei Zohar 1:1`\n"
            "`!verse Tanya 1:1`"
        ), inline=True)
        embed.add_field(name="Maimonides  (section, chapter:halacha)", value=(
            "`!verse Mishneh Torah, Repentance 1:1`\n"
            "`!verse Mishneh Torah, Foundations of the Torah 1:1`\n"
            "`!verse Mishneh Torah, Kings and Wars 1:1`\n"
            "`!verse Guide for the Perplexed 1:1`  *(part:chapter)*\n"
            "84 sections · use `!books` → Maimonides for full list"
        ), inline=False)
        await ctx.send(embed=embed)
        return

    if topic in ("ane", "ancient near east", "ancient_near_east", "mesopotamia", "egypt", "egyptian", "ugaritic", "gilgamesh", "baal"):
        embed = discord.Embed(title="🏺 Ancient Near Eastern Texts — Citation Guide", color=discord.Color.dark_gold())
        embed.add_field(name="Epic of Gilgamesh  (tablet:section)", value=(
            "`!verse Gilgamesh 1:1`  *(Tablet I, section 1)*\n"
            "`!verse Gilgamesh 11`   *(The Flood — whole tablet)*\n"
            "`!parallel Gilgamesh 11.1`  *(English + Akkadian)*\n"
            "12 tablets · cite by tablet number, optionally :section"
        ), inline=False)
        embed.add_field(name="The Baal Cycle  (episode:section)", value=(
            "`!verse Baal 1:1`  *(Baal and Yamm)*\n"
            "`!verse Baal 2:1`  *(The Palace of Baal)*\n"
            "`!verse Baal 3:1`  *(Baal and Mot)*\n"
            "`!parallel Baal 1.5`  *(English + Ugaritic)*\n"
            "3 episodes · cite as Baal <episode>:<section>"
        ), inline=False)
        embed.add_field(name="Egyptian Texts  (section number)", value=(
            "`!verse Aten 1`  *(Great Hymn to the Aten — 13 sections)*\n"
            "`!verse Book of the Dead 1`  *(52 chapters)*\n"
            "`!verse Leiden Hymns 1`  *(22 stanzas)*\n"
            "`!verse Amenemope 1`  *(Instruction of Amenemope — 36 chapters)*\n"
            "`!verse Two Ways 1`  *(Book of Two Ways — 19 spells)*\n"
            "Or omit the number for the full text"
        ), inline=False)
        embed.add_field(name="Aramaic Wisdom", value=(
            "`!verse Ahikar 1`  *(Story of Ahikar — 5 sections)*"
        ), inline=True)
        embed.add_field(name="Random", value=(
            "`!verse ancient_near_east`  *(random from all ANE texts)*"
        ), inline=True)
        await ctx.send(embed=embed)
        return

    if topic in ("islamic", "islam", "quran", "hadith", "muslim"):
        embed = discord.Embed(title="☪️ Islamic Texts — Citation Guide", color=discord.Color.green())
        embed.add_field(name="Quran  (surah:ayah)", value=(
            "`!verse Quran 2:255`  *(Al-Baqara, verse 255 — the Throne Verse)*\n"
            "`!verse Quran 1:1`  *(Al-Faatiha, verse 1)*\n"
            "`!verse Quran 112:1`  *(Al-Ikhlaas)*\n"
            "114 surahs · use `!books` → Quran for full list with names and verse counts"
        ), inline=False)
        embed.add_field(name="The Six Books (Kutub al-Sittah)", value=(
            "`!verse Sahih al-Bukhari 1`  *(1–7,563, 97 books)*\n"
            "`!verse Sahih Muslim 1`  *(1–7,563, 56 books)*\n"
            "`!verse Sunan Abu Dawud 1`  *(1–5,274, 43 books)*\n"
            "`!verse Jami at-Tirmidhi 1`  *(1–3,956, 49 books)*\n"
            "`!verse Sunan an-Nasa'i 1`  *(1–5,761, 51 books)*\n"
            "`!verse Sunan Ibn Majah 1`  *(1–4,341, 37 books)*\n"
            "Cite by sequential hadith number — no chapter needed"
        ), inline=False)
        embed.add_field(name="Other Hadith Collections", value=(
            "`!verse Muwatta Malik 1`  *(1–1,852, 61 books)*\n"
            "`!verse Forty Hadith of Nawawi 1`  *(1–42)*\n"
            "`!verse Forty Hadith of Dehlawi 1`  *(1–40)*\n"
        ), inline=True)
        embed.add_field(name="Aliases", value=(
            "`Bukhari`, `Muslim`, `Abu Dawud`, `Tirmidhi`\n"
            "`Nasai`, `Ibn Majah`, `Muwatta`, `Nawawi`\n"
            "`Dehlawi`, `Shah Waliullah`"
        ), inline=True)
        embed.add_field(name="Sira & Islamic Biography", value=(
            "The Sira (Ibn Ishaq/Ibn Hisham) and Stories of the Prophets (Ibn Kathir) "
            "are not available in a structured API. They exist as PDFs at archive.org. "
            "The Quran and Hadith remain the primary accessible sources."
        ), inline=False)
        await ctx.send(embed=embed)
        return

    if topic in ("search", "find"):
        embed = discord.Embed(title="🔍 !search — Search Scripture", color=discord.Color.dark_gold())
        embed.description = (
            "`!search shepherd` — search KJV for a phrase\n"
            "`!search shepherd ESV` — search a specific translation\n\n"
            "Rate-limited: 3 searches per 30 seconds per user."
        )
        await ctx.send(embed=embed)
        return

    if topic in ("oracle", "delphi", "homer", "virgil", "sortes", "sortesbiblicae", "bibliomancy", "iching", "yijing", "hafez", "hafiz", "rumi", "masnavi"):
        embed = discord.Embed(title="🎲 Divination Commands", color=discord.Color.dark_gold())
        embed.add_field(name="!oracle", value="Random saying from an oracular corpus (Delphic maxims and oracles, "
                                              "Chaldaean Oracles, Golden Verses of Pythagoras)", inline=False)
        embed.add_field(name="!delphi", value="Random Delphic maxim", inline=False)
        embed.add_field(name="!homer", value="Roll three dice → receive a Homeric oracle", inline=False)
        embed.add_field(name="!virgil", value="Sortes Virgilianae — random passage from the Aeneid", inline=False)
        embed.add_field(name="!sortesbiblicae", value="Sortes Biblicae — the Bible opened at random (also `!bibliomancy`)",
                        inline=False)
        embed.add_field(name="!iching", value="Cast an I Ching hexagram with three coins: the Judgment, the Image, "
                                              "any changing lines, and the hexagram it becomes (Legge's translation)",
                        inline=False)
        embed.add_field(name="!hafez", value="Fāl-e Hāfez — the Persian custom of opening the Divan of Hafiz at random "
                                             "and reading the poem as your answer (Gertrude Bell's translation)",
                        inline=False)
        embed.add_field(name="!rumi", value="The same with Rumi's Masnavi: open it anywhere and read a few couplets "
                                            "as your answer, with the story they come from (Whinfield's translation)",
                        inline=False)
        embed.add_field(name="Ask a question", value="Add one after any of these — `!virgil will I find work?` — "
                                                     "and it's shown with the answer and on its card.", inline=False)
        embed.add_field(name="!oraclesetup (admins)", value="A daily oracle in a channel: `!oraclesetup channel #chan`, "
                                                            "then `time 12:00`, `kind any`, `test`, or `off`.", inline=False)
        embed.set_footer(text="Every answer has a 🖼️ Card button to turn it into an image.")
        await ctx.send(embed=embed)
        return

    if topic in ("ccc", "catechism"):
        embed = discord.Embed(title="⛪ !ccc — Catechism of the Catholic Church", color=discord.Color.dark_gold())
        embed.description = (
            "`!ccc 1` — paragraph 1\n"
            "`!ccc 1700-1715` — paragraph range\n"
            "`!ccc random` — random paragraph"
        )
        await ctx.send(embed=embed)
        return

    if topic in ("summa", "st", "aquinas"):
        embed = discord.Embed(title="🏛️ !summa — Summa Theologica", color=discord.Color.dark_gold())
        embed.description = (
            "`!summa I.1.1` — Part I, Question 1, Article 1\n"
            "`!summa II-II.23.1` — Second Part of Part II\n"
            "`!summa random` — random article"
        )
        await ctx.send(embed=embed)
        return

    if topic in ("creed", "creeds"):
        embed = discord.Embed(title="📜 !creed — The Ecumenical Creeds", color=discord.Color.dark_gold())
        embed.description = (
            "`!creed` — list the creeds\n"
            "`!creed apostle` — The Apostles' Creed\n"
            "`!creed nicene` — The Nicene Creed\n"
            "`!creed athanasius` — The Athanasian Creed (Quicunque Vult)\n\n"
            "Add `latin` for the traditional Latin text, `greek` for the Nicene Creed's original "
            "conciliar Greek, or `parallel` for everything available: "
            "`!creed apostle latin` · `!creed nicene greek` · `!creed nicene parallel`\n\n"
            "The Nicene Creed is the only one with a genuine ancient Greek original — the "
            "Athanasian Creed, despite its name, was actually composed in Latin.\n\n"
            "English text is traditional, as in the 1662 Book of Common Prayer."
        )
        await ctx.send(embed=embed)
        return

    if topic in ("rosary", "rosario"):
        embed = discord.Embed(title="📿 !rosary — The Rosary", color=discord.Color.dark_gold())
        embed.description = (
            "`!rosary` — the Rosary with today's mysteries, a page at a time (◀ ▶): the opening prayers, "
            "five decades each with its Bible passage, and the closing prayers, with the *Ave Maria* sung\n"
            "`!rosary joyful` · `luminous` · `sorrowful` · `glorious` — a set by name\n\n"
            "The days: Joyful on Monday and Saturday, Sorrowful on Tuesday and Friday, Glorious on Wednesday "
            "and Sunday, Luminous on Thursday."
        )
        await ctx.send(embed=embed)
        return

    if topic in ("angelus", "angelussetup", "reginacaeli"):
        embed = discord.Embed(title="🔔 !angelus — The Angelus", color=discord.Color.dark_gold())
        embed.description = (
            "`!angelus` — the Angelus in English and Latin, with the *Ave Maria* sung; in Eastertide "
            "(Holy Saturday to the eve of Trinity Sunday) the *Regina Cæli* instead, with its chant\n\n"
            "Words from *A Manual of Prayers for the Use of the Catholic Laity* (1889).\n\n"
            "**Admins:** `!angelussetup channel #chan` posts it every day at noon UTC; "
            "`!angelussetup time 06:00 12:00 18:00` for the traditional three hours (`test`, `off`)"
        )
        await ctx.send(embed=embed)
        return

    if topic in ("saint", "saints", "saintsetup"):
        embed = discord.Embed(title="🕯️ !saint — Saints", color=discord.Color.dark_gold())
        embed.description = (
            "`!saint` — the saint of the day on the traditional calendar\n"
            "`!saint Christopher` — a saint by name (several of one name? pick from a menu)\n"
            "`!saint 25 July` — the saints of a day\n\n"
            "Lives from *Butler's Lives of the Saints* (abridged, 1894), with a **📖 Golden Legend** button "
            "when the medieval *Golden Legend* tells the story too; saints only the Legend has, like "
            "Christopher, open straight to it.\n\n"
            "**Admins:** `!saintsetup channel #chan` posts the saint of the day (`time HH:MM` UTC, `test`, `off`)"
        )
        await ctx.send(embed=embed)
        return

    if topic in ("catena",):
        embed = discord.Embed(title="📿 !catena — Patristic Commentary", color=discord.Color.dark_gold())
        embed.description = (
            "`!catena John 3:16` — patristic commentary on a verse\n"
            "Sourced from catenabible.com"
        )
        await ctx.send(embed=embed)
        return

    # ── Main help menu ────────────────────────────────────────────────────────
    embed = discord.Embed(
        title="📖 ScriptureBot — Help",
        description="Use `!help <command>` for detailed help on any command.",
        color=discord.Color.dark_gold()
    )
    embed.add_field(name="✡️ Jewish Texts", value=(
        "`!help jewish` — Mishnah · Talmud · Jerusalem Talmud · Tosefta · Targum · Midrash · Zohar · Kabbalah"
    ), inline=False)
    embed.add_field(name="☪️ Islamic Texts", value=(
        "`!help islamic` — Quran (114 surahs) · Hadith (9 collections) · citation formats"
    ), inline=False)
    embed.add_field(name="🏺 Ancient Near Eastern Texts", value=(
        "`!help ane` — Gilgamesh · Baal Cycle · Egyptian texts · Ahikar · citation formats"
    ), inline=False)
    embed.add_field(name="📖 Scripture", value=(
        "`!verse` — look up or randomise a verse · `!help verse`\n"
        "`!compare` — multi-translation view · `!help compare`\n"
        "`!search` — search for a phrase (`in:buddhist` for one tradition) · `!help search`\n"
        "`!theme` — one passage on a theme from each tradition, side by side\n"
        "`!cloud Ecclesiastes` — a book's most distinctive words as a word cloud\n"
        "`!story flood` — one story told by many traditions (`creation`, `underworld`, `christ`…)\n"
        "`!votd` — verse of the day · `!help votd`\n"
        "`!today` — liturgical calendar across traditions · `!help today`\n"
        "`!books` — browse collections · `!help books`\n"
        "`!translations` — list translation slugs\n"
        "`!prefer` — set your default translation · `!help prefer`"
    ), inline=False)
    embed.add_field(name="📜 Classical & Poetic", value=(
        "`!parallel` — Homer, Virgil, Ovid, Heliand, Plato + more · `!help parallel`"
    ), inline=False)
    embed.add_field(name="⛪ Catholic", value=(
        "`!ccc` — Catechism · `!help ccc`\n"
        "`!summa` — Summa Theologica · `!help summa`\n"
        "`!canon` — Code of Canon Law\n"
        "`!catena` — Patristic commentary · `!help catena`\n"
        "`!saint` — the saint of the day, or `!saint George`, `!saint 25 July` · `!help saint`"
    ), inline=False)
    embed.add_field(name="📜 Creeds", value=(
        "`!creed apostle` / `nicene` / `athanasius` — traditional English · `!help creed`"
    ), inline=False)
    embed.add_field(name="📖 Anglican Daily Office", value=(
        "`!bcp` — psalms, lessons, and collect for Morning/Evening Prayer · `!help bcp`\n"
        "`!mp` / `!ep` — both lessons for that period\n"
        "`!psalm` / `!psalm mp` / `!psalm ep` — appointed Coverdale psalms\n"
        "`!collect` — the Collect of the Day\n"
        "`!prayer` — random devotional prayer from the BCP · `!help prayer`"
    ), inline=False)
    embed.add_field(name="🎲 Divination", value=(
        "`!oracle` `!delphi` `!homer` `!virgil` `!sortesbiblicae` `!iching` `!hafez` `!rumi` — oracular & sortes · `!help oracle`\n"
        "`!quiz` — guess which book a verse is from (`!quiz hard`, `!quiz buddhist`, `!quiz leaderboard`)\n"
        "`!whoami` — Who Am I? Guess a Bible figure from clues that get easier · `!help whoami`\n"
        "`!versle` — the daily verse puzzle: where in the Bible is it? · `!help versle`"
    ), inline=False)
    embed.add_field(name="🔭 Discovery & Personal", value=(
        "`!discover` — random passage from any loaded tradition · `!help discover`\n"
        "`!study` — verse + patristic commentary together · `!help study`\n"
        "`!xref` — cross-references (Treasury of Scripture Knowledge) · `!help xref`\n"
        "`!harmony feeding five thousand` — the four Gospels side by side · `!help harmony`\n"
        "`!notes` — NET Bible translators' notes on a verse · `!help notes`\n"
        "`!topic` — browse scripture by subject (Nave's Topical Bible) · `!help topic`\n"
        "`!save` / `!saved` / `!unsave` — personal bookmarks · `!help save`\n"
        "`!plan` — chapter-a-day reading plan · `!help plan`\n"
        "`!memorize` — learn a verse by heart, with reviews by DM · `!help memorize`\n"
        "`!leaderboard` — most active bookmarkers · `!help leaderboard`\n"
        "`!subscribe` / `!unsubscribe` — daily verse by DM · `!help subscribe`\n"
        "`!card` — shareable verse image · `!help card`"
    ), inline=False)
    embed.add_field(name="🗺️ People, Places & Hymns", value=(
        "`!who Ruth` — who someone was, their family, every verse naming them · `!help who`\n"
        "`!tree David` / `!tree Abraham to David` — a family tree, or a line of descent, drawn · `!help tree`\n"
        "`!place Bethel` — a place on a map, with its verses · `!help place`\n"
        "`!journey paul 2` — a journey on a map: Paul's, the Exodus, Abraham's… · `!help journey`\n"
        "`!measure 300 cubits` — Bible weights, measures and money in today's terms · `!help measure`\n"
        "`!kings` — every king of Israel and Judah: reigns and the Bible's verdict, as a chart · `!help kings`\n"
        "`!hymn amazing grace` — a hymn's words, its tune to play, the Bible behind it · `!midi <hymn>` just the tune · `!hymnlist` · `!help hymn`\n"
        "`!metrical 23` — a psalm in rhyming verse to sing (Scottish Psalter, 1650), with its tune · "
        "`!help metrical`"
    ), inline=False)
    embed.add_field(name="⚙️ Server Setup (Admin)", value=(
        "`!votdsetup` — configure this server's daily VOTD channel/time/mode · `!help votdsetup`\n"
        "`!features` — turn optional features on/off · `!help features`\n"
        "`!changelogsetup #channel` — where I announce my updates · `!changelog` — recent updates\n"
        "`!changelogintro` — post my full introduction + latest updates there (`fresh` clears my old posts first)\n"
        "`!oraclesetup channel #chan` — a daily oracle post (`time`, `kind`, `test`, `off`)\n"
        "`!quizsetup channel #chan` — a daily quiz question (`time`, `kind bible|hard`, `test`, `off`)\n"
        "`!verslesetup channel #chan` — the day's Versle puzzle (`time`, `test`, `off`)\n"
        "`!hymndaysetup channel #chan` — the hymn of the day (`time`, `test`, `off`)\n"
        "`!saintsetup channel #chan` — the saint of the day (`time`, `test`, `off`)\n"
        "`!angelussetup channel #chan` — the Angelus at noon, or `time 06:00 12:00 18:00` (`test`, `off`)"
    ), inline=False)
    embed.add_field(name="🏛️ Ancient Languages & Strong's", value=(
        "Append to `!verse`: `OE` `WLC` `LXX` `TR` `VULG` `peshitta` `CSL`\n"
        "`!compare ancient <ref>` — all ancient witnesses at once · `!help compare`\n"
        "`!compare strong <ref>` — KJV + original-language Strong's tagging · `!help compare`\n"
        "`!strong G3588` / `!strong H7225` — Strong's lexicon lookup · `!help strong`"
    ), inline=False)
    embed.set_footer(text="!help verse · !help compare · !help votd · !help votdsetup · !help features · !help today · !help bcp · !help prayer · !help strong · !help books · !help parallel · !help oracle · !help discover · !help study · !help xref · !help notes · !help topic · !help save · !help plan · !help leaderboard · !help subscribe · !help card · !help who · !help tree · !help whoami · !help versle · !help place · !help journey · !help measure · !help kings · !help harmony · !help hymn · !help metrical · !help creed · !help ccc · !help summa")
    await ctx.send(embed=embed)


@bot.tree.command(name="help", description="Show ScriptureBot command help")
async def help_slash(interaction: discord.Interaction, topic: str = ""):
    await interaction.response.defer()
    ctx = await bot.get_context(interaction)
    await cmd_help(ctx, topic=topic)


@bot.command(name="translations", aliases=["trans", "tl"])
async def cmd_translations(ctx):
    """List all available Bible translations. Usage: !translations"""
    trans_list = list_translations()
    lines = trans_list.split("\n")

    # Balance the split by character count, not line count -- lines vary
    # enough in length that a line-count split let one column silently grow
    # past Discord's 1024-char embed field limit as translations were added.
    total_chars = sum(len(l) + 1 for l in lines)
    col1_lines, running = [], 0
    for l in lines:
        if col1_lines and running >= total_chars / 2:
            break
        col1_lines.append(l)
        running += len(l) + 1
    col2_lines = lines[len(col1_lines):]
    col1 = "\n".join(col1_lines)
    col2 = "\n".join(col2_lines)
    if len(col1) > 1000:
        col1 = col1[:997] + "…"
    if len(col2) > 1000:
        col2 = col2[:997] + "…"

    embed = discord.Embed(
        title="📖 Available Bible Translations",
        color=discord.Color.dark_gold()
    )
    embed.add_field(name="Via bolls.life (A–M)", value=col1, inline=True)
    embed.add_field(name="Via bolls.life (N–Z)", value=col2, inline=True)
    embed.add_field(
        name="Local translations (offline)",
        value=(
            "**DRB** — Douay-Rheims Bible (Challoner revision)\n"
            "**Knox** — Knox Bible, trans. Ronald Knox (1945–49)\n"
            "**KJV** — King James Version (no suffix needed)"
        ),
        inline=False
    )
    embed.add_field(
        name="Ancient languages (local)",
        value=(
            "**OE** — Old English (Wessex Gospels, ~990 AD) — Gospels only\n"
            "**WLC** / **Hebrew** — Westminster Leningrad Codex (Hebrew OT)\n"
            "**LXX** / **Septuagint** — Greek OT (Swete 1930)\n"
            "**TR** — Textus Receptus (Greek NT, Elzevir 1624)\n"
            "**VULG** / **Vulgate** — Vulgata Clementina (Latin)\n"
            "**Peshitta** / **Syriac** — Peshitta (Aramaic)\n"
            "**CSL** / **Slavonic** — Church Slavonic (Elizabeth Bible, 1757)"
        ),
        inline=False
    )
    embed.set_footer(text=(
        "Usage: !verse John 3:16 ESV  ·  !verse Tobit 1:1 NRSVCE  ·  "
        "!verse John 3:16 KJV ESV NASB (parallel)  ·  !verse John 3:16 Knox"
    ))
    await ctx.send(embed=embed)

@bot.tree.command(name="translations", description="List all available Bible translations")
async def translations_slash(interaction: discord.Interaction):
    await interaction.response.defer()
    ctx = await bot.get_context(interaction)
    await cmd_translations(ctx)
