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
| `!search <text>` | `!find` | Full-text search |
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
| `!oraclesetup` | | (Admins) A daily oracle in a channel: `channel #chan`, `time HH:MM` (UTC), `kind any\|virgil\|…`, `test`, `off` |

Every oracle takes an optional question (`!virgil will I find work?`), shown with the
answer, and every answer has a 🖼️ Card button that renders it as an image.

### Quiz

| Command | Aliases | What it does |
|---|---|---|
| `!quiz [hard \| leaderboard]` | `!guess` | Which book is this verse from? One private guess each, revealed after 60s. Scores per server, weekly and all-time, with streaks |
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
| `!plan` | | Chapter-a-day reading plan |
| `!prefer <translation>` | | Default translation for plain `!verse` |
| `!leaderboard` | `!lb` | Most active bookmarkers |
| `!features` | | (Admins) Opt-in server features |

Plus `!stats`, and owner/admin tools `!guildactivity` and `!scanstats`.

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
```

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
  stats.py, help.py, autodetect.py, slash.py
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

**Runtime state is not in git.** The bot writes per-server and per-user data
to `data/` as it runs — `stats.json`, `guild_activity.json`, `guild_config.json`,
`user_prefs.json`, `bookmarks.json`, `reading_plans.json`, `subscribers.json`,
`votd_mode.json`. These contain Discord user/server IDs and are gitignored; back
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
3. Add a few lookups to `tests/test_lookup.py`.

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
