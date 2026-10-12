# Scripture Discord Bot

A Discord bot that looks up scripture verses across:
- **King James Bible + Apocrypha** (15 deuterocanonical books)
- **LDS Standard Works** (Book of Mormon, D&C, Pearl of Great Price)
- **Brenton Septuagint** (including Psalms of Solomon, 3 & 4 Maccabees, Odes)
- **R.H. Charles** – Book of Enoch (1917) & Book of Jubilees (1902)

---

## Quick Start

### 1. Create a Discord Bot

1. Go to https://discord.com/developers/applications → **New Application**
2. Go to **Bot** tab → **Reset Token** → copy it
3. Under **Privileged Gateway Intents**, enable **Message Content Intent**
4. Go to **OAuth2 → URL Generator**: scopes = `bot` + `applications.commands`; permissions = `Send Messages`, `Embed Links`
5. Open the generated URL to invite the bot to your server

### 2. Install Python dependencies

```bash
python -m pip install -r requirements.txt
```

### 3. Build the data files

```bash
python build_data.py
```

This downloads public-domain texts and writes structured JSON into `data/`.
Some sources require manual steps (see below).

### 4. Run the bot

```bash
export DISCORD_TOKEN=your_token_here      # Linux/Mac
set DISCORD_TOKEN=your_token_here         # Windows CMD
$env:DISCORD_TOKEN="your_token_here"      # PowerShell

python bot.py
```

---

## Data Acquisition

### KJV + Apocrypha
`build_data.py` fetches the KJV automatically from the public `bcbooks/scriptures-json` repo.

For the **Apocryphal books** (Tobit, Judith, Wisdom, Sirach, Maccabees, etc.) the automated script writes stubs. To get the real text:

Option A – Use the SWORD Project's KJV+Apocrypha module:
1. Install [SWORD utilities](https://crosswire.org/sword/software/swordutils.jsp)
2. Download module `KJV` and `KJVApoc`
3. Export with `mod2osis KJVApoc` and parse the XML into the JSON schema

Option B – Use the [eBible.org eng-kjv+dc download](https://ebible.org/find/show.php?id=engkjvapoc), which is public domain.

### LDS Standard Works
Fetched automatically from `bcbooks/scriptures-json`. ✓

### Brenton Septuagint
The `Logosio/brenton-septuagint` repo (GitHub) may not have a single combined JSON. If the automated fetch fails:

1. Clone https://github.com/Logosio/brenton-septuagint
2. Combine individual book files into `data/brenton/brenton_septuagint.json` with schema:
   ```json
   {
     "source": "Brenton Septuagint (1851)",
     "books": {
       "Psalms of Solomon": { "1": { "1": "Blessed is the man…" } }
     }
   }
   ```

Alternatively, [Unbound Bible](https://unbound.biola.edu/) hosts the LXX in tab-delimited format (free download after registration).

### Apostolic Fathers (J.B. Lightfoot)

Lightfoot's *The Apostolic Fathers* (1889–1890, 5 vols.) is fully public domain. The texts are widely reproduced but rarely in clean verse-addressable JSON. `build_data.py` will attempt a scrollmapper bundle first, then write annotated stubs with source URLs.

**Manual acquisition options:**

| Text | Best free source |
|---|---|
| 1 & 2 Clement | [CCEL – Lightfoot](https://www.ccel.org/ccel/lightfoot/fathers2.html) |
| Ignatius (7 letters) | Same CCEL link; use the **middle recension** (authentic) only |
| Polycarp to Philippians | [earlychristianwritings.com](https://earlychristianwritings.com/polycarp.html) |
| Martyrdom of Polycarp | [earlychristianwritings.com](https://earlychristianwritings.com/martyrdompolycarp.html) |
| Epistle of Barnabas | [earlychristianwritings.com](https://earlychristianwritings.com/barnabas.html) |
| Didache | [earlychristianwritings.com](https://earlychristianwritings.com/didache.html) |
| Shepherd of Hermas | [earlychristianwritings.com](https://earlychristianwritings.com/shepherd.html) |

Once you have the text, structure it into the standard JSON schema. The Shepherd of Hermas is a single file (`shepherd_of_hermas.json`) using Lightfoot's continuous chapter numbering, 1–114.

**A note on verse numbers:** The Apostolic Fathers don't have traditional chapter:verse divisions like the Bible. The convention used here is `chapter:sentence-group`, following the Lightfoot/Harmer paragraph numbering. For example:

- `1 Clement 5:1` → Chapter 5, first sentence-unit
- `Didache 9:1`
- `Herm Sim 9:1` → Hermas, Similitude 9, chapter 1 (the traditional citation; continuous ch. 78)
- `Herm Sim 9:1:3` or `Herm Sim 9.1.3` → …verse 3
- `Hermas 78:3` → the same verse, by continuous chapter


These require manual preparation:

1. Sacred-texts.com hosts plain HTML: 
   - Enoch: https://sacred-texts.com/bib/boe/
   - Jubilees: https://sacred-texts.com/bib/jub/
2. Each chapter is a separate HTML page. Scrape them (respecting their terms) or use a pre-converted source.
3. A community-prepared JSON of 1 Enoch is available at:
   https://github.com/scrollmapper/bible_databases (check the `formats/json/` folder)
4. Place the results in:
   - `data/charles/book_of_enoch.json`
   - `data/charles/book_of_jubilees.json`

---

## JSON Schema

Every data file must follow this schema:

```json
{
  "source": "Human-readable source name",
  "books": {
    "Book Name": {
      "1": {
        "1": "Verse text here.",
        "2": "Next verse."
      },
      "2": { ... }
    }
  }
}
```

- All keys (chapter and verse numbers) must be **strings**.
- D&C sections are treated as "chapters".
- Articles of Faith: chapter `"1"`, verses `"1"`–`"13"`.

---

## Commands

| Command | Example | Description |
|---|---|---|
| `/verse <ref>` | `/verse John 3:16` | Slash command verse lookup |
| `!verse <ref>` | `!verse 2 Nephi 2:25` | Prefix command |
| `!v <ref>` | `!v Enoch 1:9` | Short alias |
| `!scripture <ref>` | `!scripture Wisdom 7:22` | Another alias |
| `!search <text>` | `!search faith hope charity` | Full-text search |
| `!books` | `!books lds` | List books (optional filter) |

### Supported Reference Formats

```
Genesis 1:1
Gen 1:1
Jn 3:16
1 Nephi 3:7
1Ne 3:7
D&C 76:22
Doctrine and Covenants 76:22–24     ← verse range
Wisdom 7:22
Ps Sol 17:1
Enoch 1:9
Jubilees 3:4
1 Clement 5:1
1 Clem 5:1
Ign Eph 7:2                         ← Ignatius to the Ephesians
Ign Rom 4:1
Pol Phil 2:1                        ← Polycarp to the Philippians
Mart Pol 9:1                        ← Martyrdom of Polycarp
Barn 4:1                            ← Epistle of Barnabas
Did 9:1                             ← Didache
Herm Vis 1:1                        ← Shepherd of Hermas, Vision 1, ch. 1
Herm Man 6:1                        ← Shepherd of Hermas, Mandate 6, ch. 1
Herm Sim 9:1:3                      ← Shepherd of Hermas, Similitude 9, ch. 1, v. 3
Hermas 78:3                         ← same verse, Lightfoot continuous chapters
```

---

## File Structure

```
scripture-bot/
├── bot.py                  ← Discord bot (entry point)
├── scripture_lookup.py     ← Verse lookup engine
├── build_data.py           ← Data download/build script
├── requirements.txt
├── README.md
└── data/
    ├── kjv/
    │   └── kjv_with_apocrypha.json
    ├── lds/
    │   ├── book_of_mormon.json
    │   ├── doctrine_and_covenants.json
    │   └── pearl_of_great_price.json
    ├── brenton/
    │   └── brenton_septuagint.json
    ├── charles/
    │   ├── book_of_enoch.json
    │   └── book_of_jubilees.json
    └── apostolic_fathers/
        ├── 1_clement.json
        ├── 2_clement.json
        ├── ignatius_ephesians.json
        ├── ignatius_magnesians.json
        ├── ignatius_trallians.json
        ├── ignatius_romans.json
        ├── ignatius_philadelphians.json
        ├── ignatius_smyrnaeans.json
        ├── ignatius_polycarp.json
        ├── polycarp_philippians.json
        ├── martyrdom_of_polycarp.json
        ├── epistle_of_barnabas.json
        ├── didache.json
        ├── hermas_visions.json
        ├── hermas_mandates.json
        └── hermas_similitudes.json
```

---

## Extending

To add a new corpus (e.g. the Dead Sea Scrolls, Nag Hammadi texts):
1. Add a `data/newcorpus/mybook.json` with the standard schema
2. Add an entry in `build_data.py`'s `corpus_dirs` dict inside `ScriptureLookup._load_all()`
3. Add book aliases to the `ALIASES` dict in `scripture_lookup.py`
4. Add the corpus to `CORPUS_PRIORITY`
