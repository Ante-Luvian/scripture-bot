# Scripture Discord Bot

A Discord bot for looking up, comparing, and studying scripture and related
texts across many traditions: the Bible in dozens of translations (plus the
Septuagint, Vulgate, Peshitta, and Dead Sea Scrolls), the Apocrypha, LDS
scripture, the Apostolic and Church Fathers, Enoch and Jubilees, the Quran and
hadith, the Talmud and other rabbinic literature (via Sefaria), and Gnostic,
Hermetic, Neoplatonic, Classical, Norse, Dharmic, and Ancient Near Eastern texts.
It also has study tools (Strong's, interlinears, cross-references, topical and
dictionary lookups), the Book of Common Prayer daily office, a liturgical
calendar, and a daily Verse of the Day.

---

## Quick start

### 1. Create the Discord application

1. https://discord.com/developers/applications → **New Application**
2. **Bot** tab → **Reset Token** → copy it
3. Under **Privileged Gateway Intents**, enable **Message Content Intent**
4. **OAuth2 → URL Generator**: scopes `bot` + `applications.commands`;
   permissions `Send Messages`, `Embed Links`, `Attach Files`, `Add Reactions`
5. Open the generated URL to invite the bot

### 2. Get the code and data

The text corpus is in this repo under `data/`; six large third-party corpora
(Perseus Greek/Latin, Swete LXX, ETCBC Peshitta/Syriac NT, Tischendorf) are git
submodules, so clone with:

```bash
git clone --recurse-submodules https://github.com/Ante-Luvian/scripture-bot
```

(Already cloned without them? `git submodule update --init`.)

### 3. Install dependencies

```bash
python -m pip install -r requirements.txt        # running the bot
python -m pip install -r requirements-dev.txt    # + pytest, for development
```

### 4. Run

Put the bot token in a `.env` file next to `bot.py` (it's gitignored):

```
DISCORD_TOKEN=your_token_here
```

then:

```bash
python bot.py
```

### Running as a Windows service (NSSM)

In production the bot runs as the Windows service **ScriptureBot** under
[NSSM](https://nssm.cc/), starting `python bot.py` in the project folder.

| Task | Command (PowerShell) |
|---|---|
| Restart after code changes | `Restart-Service ScriptureBot` |
| Status | `Get-Service ScriptureBot` |
| Logs | `C:\ProgramData\nssm\logs\scripturebot.err.log` (the bot logs to stderr) |

The running bot only picks up code changes after a restart.

---

## Commands

Prefix commands use `!`; most also have a `/` slash-command version.
`!help` in Discord shows the full in-bot help.

### Looking up text

| Command | Aliases | What it does |
|---|---|---|
| `!verse <ref>` | `!v`, `!scripture` | Look up a verse, range, or chapter. `!verse` alone = random verse; `!verse Enoch` = random verse from a book. Add a translation (`!verse John 3:16 esv`) or several for a side-by-side (`!verse John 3:16 kjv web`). Bible verses come with Notes · Cross-refs · Interlinear · Card buttons. |
| `!search <text> [in:<tradition>]` | `!find` | Full-text search, optionally in one tradition (`TRADITIONS` in scripture_lookup.py) |
| `!theme <word>` | `!traditions` | One passage on a theme from each tradition, side by side |
| `!books [filter]` | | Browse every collection, book, and chapter |
| `!discover` | | Random passage from any tradition |
| `!compare <ref>` | `!cmp` | One verse across many translations |
| `!parallel <ref>` | `!poem`, `!par`, `!classical` | Bible or classical text in parallel languages |
| `!variants <ref>` | `!dss`, `!scrollcompare` | KJV vs Septuagint vs Dead Sea Scroll witness |
| `!translations` | `!trans`, `!tl` | List available translations |
| `!export <book> [chapters]` | | Download a book or chapter range as a text file |
| `!card <ref>` | `!versecard`, `!quotecard` | Render a verse as a shareable image |

### Study tools

| Command | Aliases | What it does |
|---|---|---|
| `!study <ref>` | | Verse plus patristic commentary |
| `!catena <ref>` | | Patristic commentary (catenabible.com) |
| `!story [name]` | `!stories`, `!myth` | One story across traditions (`stories.py`, curated in `data/stories.json`: a reference and a quotation per passage, both checked against the text by `tests/test_stories.py`); `christ` adds the Church Fathers who read each pagan text as foretelling Christ |
| `!cloud <book>` | `!wordcloud` | A book's most distinctive words as an image (`cloud.py`, the `wordcloud` package): tf-idf against the other books of its corpus, stopwords (KJV's included) removed |
| `!saint [name \| day]` | `!saints`, `!saintoftheday` | The saint of the day, or by name/day (`saints.py`, `data/saints/saints.json` from `build_saints.py`): Butler's 1894 abridged Lives, with a 📖 Golden Legend button; Legend-only saints open to the Legend; several of a name give a picker |
| `!saintsetup` | `!saintconfig` | (Admins) Post the saint of the day in a channel: `channel #chan`, `time HH:MM` (UTC, default 07:00), `test`, `off`; `saintday.json` stops double posts |
| `!xref <ref>` | `!crossref` | Cross-references (Treasury of Scripture Knowledge) |
| `!notes <ref>` | `!netnotes` | The NET Bible's translator's, study, and text-critical notes for a verse (up to 5 verses) |
| `!quoted <ref>` | `!otnt`, `!quotedin` | OT ↔ NT quotations, and NT quotations of / parallels with Enoch and other non-canonical works |
| `!strong <number or ref>` | `!strongs` | Strong's entry, or a verse with Strong's tagging |
| `!root <number or word>` | `!cognates` | A Hebrew/Greek word's root and its direct derivatives |
| `!concordance <number or word>` | `!conc` | Every verse tagged with a Strong's number |
| `!interlinear <ref>` | `!il` | Word-by-word interlinear image |
| `!reverseinterlinear <ref>` | `!ril` | KJV text tagged with Strong's numbers, as an image |
| `!topic <subject>` | `!naves` | Nave's Topical Bible |
| `!dictionary <term>` | `!dict`, `!define` | Easton's / Smith's Bible Dictionary |
| `!timeline <subject>` | `!chronology` | Ussher's *Annals of the World* |
| `!gematria <word or number>` | `!gem` | Gematria values (gematrix.org) |
| `!kings [name]` | `!king`, `!monarchs` | The 42 kings (and Athaliah) from Saul to Zedekiah: reign lengths and verdicts quoted from the KJV with verses (`kings.py`, checked by `test_kings.py`), drawn as a chart (Pillow) or one king at a time |
| `!measure [unit \| amount unit \| verse]` | `!measures`, `!weights`, `!money`, `!convert` | Bible weights, measures and money in modern terms (`measures.py`): 33 units with Easton's figures quoted, KJV relations ("the shekel shall be twenty gerahs"), conversions (`300 cubits`, `half a shekel`), and every measurement in a verse (`Genesis 6:15`). Money in denarii / days' wages and in USD (Easton's 1897 pence × UK inflation × exchange rate, constants in the module); silver shekels/talents also as money. Quotes and verses are checked by `test_measures.py` |
| `!who <name>` | `!person`, `!whois` | A person: description, family (with a menu to walk the tree), tribe, birth/death places, every verse naming them; namesakes offered as a list (Theographic) |
| `!tree <name> [to <name>]` | `!familytree`, `!lineage`, `!genealogy` | A family-tree picture (grandparents to children, paternal line), or a chart of every generation between two people (`family_tree.py`) |
| `!place <name>` | `!where`, `!map` | A place on a drawn map card (nearby places, locator inset, scale; uncertain sites ringed), with its verses |
| `!harmony [words \| verse \| n]` | `!gospels`, `!synoptic` | An event in the life of Christ as each Gospel tells it, side by side (Robertson's Harmony, 185 sections, `data/harmony.json` from `build_harmony.py`); buttons read each account and step through the events |
| `!journey [name]` | `!journeys`, `!route` | A journey on a route map (`bible_map.render_route`) with its stops and verses: Abraham, Exodus, Paul 1–3, Rome, Egypt, Jonah. Every stop's verse is checked against the KJV by a test |
| `!hymn [title \| words \| topic \| passage]` | `!hymns`, `!hymnal` | A public-domain hymn: words, author, tune, Bible passages; ▶️ plays the tune (an organ .ogg) |
| `!midi [title \| words \| topic \| passage]` | `!tune` | Just a hymn's tune, posted straight away without the words |
| `!psalm <n> chant [organ]` | `!chant psalm <n>` | A psalm chanted in Latin to a psalm tone (or on the organ), with the Latin and Douay-Rheims |
| `!troparion [date]` | `!troparia`, `!kontakion` | The day's Orthodox troparia and kontakia with their tones (oca.org, live); `!troparionsetup` posts them daily |
| `!rosary [joyful\|luminous\|sorrowful\|glorious]` | `!rosario` | The Rosary a page at a time: the day's mysteries with their Bible passages, the Ave Maria sung |
| `!prayer [name \| list]` | | A traditional prayer by name (St Michael, Memorare, Anima Christi…), English and Latin, sung where it's a chant; empty for a random BCP prayer |
| `!angelus` | `!reginacaeli` | The Angelus (Regina caeli in Eastertide), English and Latin, its chant sung; `!angelussetup` posts it at chosen hours |
| `!chant [title \| words]` | `!sing`, `!sungchant` | A Latin chant sung with its words, posted straight away; random if empty |
| `!hymnlist [all \| hymns \| chant \| harp \| chant kind \| words]` | `!hymnindex`, `!listhymns` | The hymnal by title: section counts, or a paged list to open from |
| `!metrical [n \| nb \| n:v-v \| words \| tune]` | `!metricalpsalm`, `!singpsalm`, `!psalter1650`; `!psalm 23 sing` | A psalm from the Scottish Metrical Psalter (1650) with its tune to play, a menu of other same-meter tunes, KJV button, second versions, pages |

### Church, liturgy, and the daily office

| Command | Aliases | What it does |
|---|---|---|
| `!today [date]` | `!calendar`, `!liturgy` | Observances across traditions for a date |
| `!bcp` | | BCP daily office: psalms, lessons, collect |
| `!mp` / `!ep` | `!matins` / `!evensong`, `!vespers` | Morning / Evening Prayer lessons |
| `!psalm` | `!psalms` | Today's appointed psalm(s) |
| `!collect` | | Collect of the day |
| `!prayer` | | Random BCP prayer or collect |
| `!creed [name]` | `!creeds` | Apostles', Nicene, or Athanasian Creed (English/Latin/Greek) |
| `!ccc <n>` | | Catechism of the Catholic Church |
| `!canon <n>` | | Code of Canon Law |
| `!summa <ref>` | `!aquinas` | Summa Theologica article |

### Oracles

| Command | Aliases | What it does |
|---|---|---|
| `!oracle` | | Random verse from an oracular corpus |
| `!delphi` | | Random Delphic maxim |
| `!homer` | `!homeromanteion`, `!sortes` | Homeric dice oracle |
| `!virgil [question]` | `!aeneid` | Sortes Vergilianae |
| `!sortesbiblicae` | `!bibliomancy` | Sortes Biblicae: the Bible opened at random (with the study buttons) |
| `!hafez [question]` | `!hafiz`, `!fal` | Fāl-e Hāfez: a random poem from the Divan of Hafiz (Bell's 43 ghazals) |
| `!rumi [question]` | `!masnavi`, `!mathnawi` | A random run of couplets from Rumi's Masnavi (Whinfield), with the story it comes from; also a daily-oracle kind |
| `!iching [question]` | `!yijing`, `!hexagram` | Cast an I Ching hexagram (three coins): Judgment, Image, changing lines, the hexagram it becomes (Legge) |
| `!oraclesetup` | | (Admins) A daily oracle in a channel: `channel #chan`, `time HH:MM` (UTC), `kind any\|virgil\|…`, `test`, `off` |

Every oracle takes an optional question (`!virgil will I find work?`), shown with the
answer, and every answer has a 🖼️ Card button that renders it as an image.

### Quiz

| Command | Aliases | What it does |
|---|---|---|
| `!quiz [hard \| leaderboard]` | `!guess` | Which book is this verse from? One private guess each, revealed after 60s. Scores per server, weekly and all-time, with streaks |
| `!versle [stats]` | `!dailyverse` | Versle: a daily well-known verse (`data/versle_pool.json`, from `build_versle_pool.py`); guess its reference in six tries with private 🟩🟨⬛ book/chapter/verse feedback; shareable grid; streaks in `data/versle.json` |
| `!whoami` | `!mystery`, `!whoisit` | Who Am I? A Bible figure (named in 20+ verses) from clues generated from the !who data, easiest last; guess via a modal, first right answer wins (`games.py`) |
| `!hymnday [YYYY-MM-DD]` | `!hymnoftheday`, `!hotd` | The hymn of the day for the Church year (`hymnday.py`): the feast's hymn on great feasts, a seasonal one in Advent/Christmas/Lent/Passiontide/Easter/Pentecost week, else English hymn, Latin chant and Sacred Harp in turn; the same for everyone on a UTC day |
| `!hymndaysetup` | `!hymndayconfig` | (Admins) Post the hymn of the day in a channel: `channel #chan`, `time HH:MM` (UTC, default 08:00), `test`, `off`; `hymnday.json` stops double posts |
| `!verslesetup` | `!versleconfig` | (Admins) Each day's Versle posted in a channel with yesterday's answer and solve count: `channel #chan`, `time HH:MM` (UTC, default 00:05), `test`, `off`; `versle.json` "posted" stops double posts |
| `!quizsetup` | `!quizconfig` | (Admins) A daily quiz question in a channel, revealed with the next: `channel #chan`, `time HH:MM` (UTC), `kind bible\|hard`, `test`, `off` |

### Verse of the Day

| Command | What it does |
|---|---|
| `!votd [translation \| full \| extended]` | Today's verse |
| `!votdsetup` | (Admins) Configure this server's daily post: channel, time, style |
| `!subscribe` / `!unsubscribe` | Daily verse by DM |

### Personal

| Command | Aliases | What it does |
|---|---|---|
| `!save <ref> [note]` | `!bookmark` | Bookmark a verse |
| `!saved [export]` | `!bookmarks` | List (or export) bookmarks |
| `!unsave <n>` | | Remove a bookmark |
| `!plan` | | Chapter-a-day reading plan, with optional daily DM (`!plan remind on [HH:MM]`) |
| `!memorize <ref>` | `!memorise`, `!learn` | Learn a verse by heart: blanked-out practice card (4 levels) and spaced reviews by DM; `list`, `stop <ref>` |
| `!prefer <translation>` | | Default translation for plain `!verse` |
| `!leaderboard` | `!lb` | Most active bookmarkers |
| `!features` | | (Admins) Opt-in server features |

Plus `!stats`, and owner/admin tools `!guildactivity`, `!scanstats`, `!errors [days]`
(recent errors, grouped) and `!weeklyreport` (preview of the Monday DM report).
Right-clicking a message → Apps → **Look up verses** shows the references in it, privately.

The bot copies its runtime files in `data/` to `backups/YYYY-MM-DD/` once a day,
keeping 14 days (`bot_commands/backup.py`).

### Updates

| Command | What it does |
|---|---|
| `!changelog` | Recent updates (also `!whatsnew`) |
| `!changelogsetup #channel` | (Admins) Where the bot announces new updates; `off` to stop |
| `!changelogintro [fresh]` | (Admins) Post the full introduction ([`INTRODUCTION.md`](INTRODUCTION.md)) and the two latest updates in that channel; `fresh` first deletes the bot's own earlier messages there |

Updates come from [`CHANGELOG.md`](CHANGELOG.md): when the bot starts after an
update, she posts each entry a server hasn't seen yet to its changelog channel.

### Reference formats

```
Genesis 1:1     Gen 1:1     Jn 3:16           ← names, abbreviations, any case
John 3:16-18    John 3:16 – 18                ← verse ranges
John 7:53-8:11  John 3-5                      ← cross-chapter / chapter ranges
Psalm 23                                      ← whole chapter (paginated)
1 Nephi 3:7     1Ne 3:7     D&C 76:22         ← LDS
Wisdom 7:22     Ps Sol 17:1 Psalm 151:1       ← Apocrypha / LXX
Enoch 1:9       Jubilees 3:4
1 Clem 5:1      Ign Eph 7:2  Pol Phil 2:1  Mart Pol 9:1  Barn 4:1  Did 9:1
Herm Sim 9:1    Herm Sim 9:1:3   Herm. Sim. 9.1.3   Hermas 78:3
Quran 1:1       Surah 1:1
Rig Veda 10.121:9
Gilgamesh 1:1   Baal 1:1     Aten 1       Muallaqat 1:1
Delphi 1:1      Kitab-i-Aqdas 1:1
Berakhot 2a     Shabbat 31a                ← Talmud, via Sefaria
Berakhot 1:1    M Berakhot 1:1   Avot 1:1  ← Mishnah, via Sefaria
Guru Granth Sahib 1:1   Japji 1           ← Ang (page):line; Japji by pauri (0 = Mool Mantar)
Akaranga Sutra 1.1.1:3  Mencius 6.1.2:1   Chandogya Upanishad 6.8:7   Masnavi 1.0:1
```

**The Perseus library** (`scripts/build_perseus.py`, from the `canonical-greekLit` and
`canonical-latinLit` submodules): ~600 Greek and Latin works in English, a file per
author in `data/classical/perseus/` (loaded by globbing that folder, with `index.json`
for `!books` and `aliases.json` for catalogue titles like "Germania"). The last
citation level is the verse, the rest the chapter (`History of the Peloponnesian War 2.40:1`);
a work cited by one level is chapter 1 (`Antigone 1:450`); Perseus "card" levels are
dropped. Works already in the library are skipped; a title shared by two authors
keeps the author's name (`Sophocles: Electra`).

**World texts** (built by `scripts/build_world_texts.py`, mostly from the Sacred
Books of the East on archive.sacred-texts.com) keep each tradition's own
divisions: book.lecture.lesson for the Akaranga, book.part.chapter for Mencius
(lost chapters in that copy are gaps, not renumbered), prapathaka.khanda for the
Chandogya, book.story for the Masnavi, Ang:line for the Guru Granth Sahib. Where a
source has no verse numbers (Kojiki, Jataka, Popol Vuh, Mabinogion) a verse is a
paragraph, long ones cut into runs of sentences; long poems without stanzas
(Kalevala, Masnavi) are runs of eight lines.

**Apostolic Fathers** use Lightfoot/Harmer `chapter:sentence-group` numbering.
**Shepherd of Hermas** takes the traditional citation — `Herm Sim 9:1` is
Similitude 9, chapter 1 (Lightfoot's continuous chapter 78); add a third number
for a verse — or Lightfoot's continuous chapters directly (`Hermas 78:3`).

---

## Project layout

```
bot.py                  Entry point: startup (on_ready) and bot.run()
core.py                 Shared state & helpers: the Bot, the ScriptureLookup
                        engine, logging, per-guild/per-user persistence,
                        stats, and the common result/embed senders
bot_commands/           One module per feature area; each registers its
  verse.py              commands on core.bot when imported:
  books.py                !verse/!search/!discover/!study · !books/!export
  translations.py         !compare/!variants/!strong/!parallel
  card.py                 !card/!interlinear/!reverseinterlinear/!concordance
  reference.py            !xref/!quoted/!root/!topic/!dictionary/!timeline
  church.py               !catena/!ccc/!canon/!creed/!summa
  liturgy.py              !today/!bcp/!prayer/!mp/!ep/!psalm/!collect
  oracles.py              !gematria/!virgil/!homer/!delphi/!oracle
  votd.py                 !votd/!votdsetup/!subscribe + the daily task
  personal.py             !save/!plan/!prefer/!leaderboard/!features
  quiz.py                 !quiz/!quizsetup + the daily quiz
  memorize.py             !memorize + its DM reviews
  people.py               !who/!place/!tree (map cards: bible_map.py; trees: family_tree.py)
  hymns.py                !hymn (tunes played by hymn_audio.py)
  hymnday.py              !hymnday, !hymndaysetup (the hymn of the day)
  saints.py               !saint, !saintsetup (Butler's Lives and the Golden Legend)
  cloud.py                !cloud (word clouds)
  stories.py              !story (one story across traditions; data/stories.json)
  psalter.py              !metrical (the Scottish Metrical Psalter)
  games.py                !whoami, !versle
  journeys.py             !journey (route maps: bible_map.py)
  harmony.py              !harmony (data/harmony.json)
  measures.py             !measure (weights, measures, money; Easton's figures)
  kings.py                !kings (the kings of Israel and Judah, chart)
  report.py               the owner's weekly report, !errors
  backup.py               daily backup of data/
  stats.py, help.py, autodetect.py, slash.py, changelog.py, health.py
scripture_lookup.py     Reference parsing and the local-corpus lookup engine
*_lookup.py             Other sources: translations (bolls.life), Sefaria,
                        Strong's, cross-refs, topics, dictionary, timeline,
                        interlinear, hadith, Summa, BCP, poems
liturgical_calendar.py  !today's multi-tradition calendar
data/                   The text corpus (JSON) — see below
fonts/                  Fonts for !card / interlinear images
tests/                  pytest suite
deprecated/             Old one-off build/fix scripts, kept for reference
<six submodules>        Third-party corpora (Perseus, LXX, Peshitta, ...)
```

---

## Data

Every corpus file in `data/` follows one schema:

```json
{
  "source": "Human-readable source name",
  "books": {
    "Book Name": {
      "1": { "1": "Verse text here.", "2": "Next verse." },
      "2": { "...": "..." }
    }
  }
}
```

Chapter and verse keys are **strings**. D&C sections are chapters; Articles of
Faith are chapter `"1"`, verses `"1"`–`"13"`.

**Cleaning.** Texts scraped from the web bring the web with them: site menus and
scripts, licences, translators' footnotes, page markers, back-of-book indexes, Greek
in Beta Code. `corpus_clean.py` holds the rules (general ones, plus fixes by file) and
`scripts/clean_corpora.py` applies them to every file under `data/` (idempotent; needs
`pip install beta-code`). Run it after rebuilding a corpus; `python -m pytest -m corpus`
checks that nothing is left (several minutes, so it's not in the default run).

Three reference datasets have their own shape, each rebuilt by a script in `scripts/`:

- `data/people_places/` (`build_people_places.py`): `people_places.json` holds
  `{"people": {slug: {name, family links, verses, ...}}, "places": {slug: {name,
  lat, lon, approx, verses, ...}}}` from Theographic Bible Metadata, and
  `basemap.json` the Natural Earth coastlines, lakes and rivers for the map cards.
- `data/hymns/` (`build_hymns.py`): `hymns.json` (`{"hymns": [{title, author,
  tune, meter, scripture, stanzas, refrain, midi, ...}]}`), `midi/`, and `audio/`
  (each tune rendered to Ogg Opus by `render_hymn_audio.py`, which needs numpy,
  mido and ffmpeg; the bot itself only sends the file). The
  Open Hymnal's ABC scores are converted to the words and MIDI; a few extra hymns
  (`EXTRA_HYMNS`) take their words from Hymnary.org and tunes from Wikimedia Commons
  or, where none could be fetched, from MIDI files the owner supplied in `scripts/hymn_midi/`.
  `more_hymns.json` and `audio/more/` (`build_chant.py`) add the ancient Latin hymns,
  sequences and antiphons from the GregoBase chant corpus (each gabc score parsed to its
  words and melody, the whole piece synthesised as chant). `sacred_harp.json` and
  `audio/harp/` (`build_sacred_harp.py`) are the Sacred Harp (1991 ed.): words from
  fasola.org, the sung four-part recordings from Sacred Harp Bremen. Entries carry
  their own `audio` path and `audio_kind`. `translations.json` (`build_translations.py`) holds
  published English for the Latin chants, by title: the Book of Common Prayer (1662 texts, from
  Gutenberg #29622) for the Mass Ordinary, Pater noster and canticles, and J. M. Neale's
  *Mediaeval Hymns and Sequences* (Wikisource), matched on the chant's opening words, and
  translations Wikipedia's hymn articles print under a named translator (`WIKIPEDIA` there).
  `audio/sung/` (`build_sung_chant.py`) has every chant *sung* with its Latin words, for
  `!chant` and the 🎤 Sung button, named by GregoBase id like the organ files: MBROLA's
  Italian voice it3 (`scripts/mbrola/`), ecclesiastical Latin turned into Italian phonemes,
  three slightly detuned voices in a synthetic reverb. `scores/` (`build_chant_scores.py`) has each
  chant's score in square notation as PNG pages (`chant-NNNNN-P.png`), for the 🎼 Score button:
  laid out by exsurge under Node (`scripts/score/`, `npm install` there; needs node) from the same
  gabc, cut into pages at the gaps between staves. Sung audio is in git (commit 2d175e9); the
  scores, like the chanted psalms, are rebuilt on the bot's machine instead.
- `data/saints/` (`build_saints.py`): `saints.json` (`{"saints": [{month, day, name,
  life, reflection, source, golden_legend: [book keys], also: [names], ...}]}`). Butler's
  abridged *Lives* (Benziger, 1894) from archive.sacred-texts.com/chr/lots, a saint for
  every day; plus the Golden Legend's saints (the existing medieval corpus), matched to
  Butler's by hand in `GOLDEN_LEGEND`, or dated from the 1913 Catholic Encyclopedia or the
  Legend's own text; those with no checkable day are found by name only.
- `data/psalter/` (`build_psalter.py`): `psalter.json` (`{"psalms": [{number,
  version ("primary"/"alternate"), meter, first_line, stanzas: [{verses, lines}],
  tune}], "tunes": {id: {title, meter, attribution, seconds}}}`), `midi/` and
  `audio/` (one Ogg per tune), all from the Open 1650 project's corpus: the 1650
  Scottish Psalter text, its psalm-to-tune settings, and 27 four-part tunes as
  note events. Needs numpy, mido and ffmpeg, like the hymn audio.
  `latin_psalms.json` (`build_psalm_chant.py`): the 150 psalms in Latin, Vulgate numbering, a
  Breviary verse a line with stresses, `*` and `†` marked, plus the Douay-Rheims and each psalm's
  tone, from jgabc (github.com/bbloomf/jgabc). `chant/sung/` and `chant/organ/` are the psalms
  chanted to those tones (`sung_psalms.py` points the syllables to the Liber Usualis tones),
  sung as the chants are and on the organ; Psalm 118 in its 22 sections. That audio is rebuilt on
  the bot's machine and not kept in git.

**Runtime state is not in git.** The bot writes per-server and per-user data
to `data/` as it runs — `stats.json`, `guild_activity.json`, `guild_config.json`,
`user_prefs.json`, `bookmarks.json`, `reading_plans.json`, `subscribers.json`,
`votd_mode.json`, plus game state (`quiz_scores.json`, `daily_quiz.json`, `memorize.json`,
`versle.json`). These contain Discord user/server IDs and are gitignored; back
them up separately if you move machines.

**Online services.** Some commands fetch from the web, so they need internet
access (local `!verse` lookups don't): bolls.life (translations), netbible.org (`!notes`;
bolls.life as backup), sefaria.org
(rabbinic texts), catenabible.com (`!catena`), newadvent.org (`!summa`),
gematrix.org (`!gematria`), verseoftheday.com (`!votd`), openbible.info (`!xref`),
deadseascrolls.org.il (`!variants`), and hebcal.com / orthocal.info /
universalis.com / api.aladhan.com (`!today`).

### Adding a corpus

1. Add `data/<corpus>/<book>.json` in the schema above.
2. In `scripture_lookup.py`: list the file under its corpus in
   `ScriptureLookup._load_all()`, add the corpus to `CORPUS_PRIORITY` and to
   the `source_map` in `get_verse()`, and add book abbreviations to `ALIASES`.
   A new corpus also needs a `TRADITIONS` entry (for `!theme`/`!search in:`),
   a label in `search_by_corpus`'s `_LABELS`, a group in `BOOKS_TREE` and
   `_SUPERGROUP_ORDER` (`bot_commands/books.py`), and its books in core's
   `_CATEGORY_BOOKS`; optionally a `QUIZ_POOLS` entry and a card style.
3. Add a few lookups to `tests/test_lookup.py` (or `tests/test_world_corpora.py`).

---

## Development

```bash
python -m pytest            # a few seconds, no network needed
```

- **Adding a command:** put it in the fitting `bot_commands/` module (or a new
  one, imported in `bot.py`), decorated with `@bot.command` from `core`.
- **Command registry snapshot:** `tests/test_command_registry.py` fails if any
  command, alias, or slash command appears or disappears. After adding or
  removing one on purpose, regenerate it:
  `python -c "import tests.test_command_registry as t; t.regenerate()"`
- **Deploying:** commit, push, then `Restart-Service ScriptureBot`.
