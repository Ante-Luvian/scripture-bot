# Session guide: how to work on ScriptureBot

A handoff for a new Claude session, written at the end of a long one (2026-10-25, the Arthurian
legend and the Middle English corpus) and brought up to date on 2026-10-26 (the Middle English work closed;
Shakespeare, `!shakespeare` and `!sonnet` added: see §6). Read it with CLAUDE.md (the rules, loaded automatically) and
README.md (what the bot does, the layout, the data schema). This file is the *how* and the *why*:
what the owner expects, how the library is built, the traps that cost time, and what's unfinished.

---

## 1. The owner, and how to work with them

The owner runs ScriptureBot, a Discord bot with a very large library (scripture, Church Fathers,
classics, world religions, ballads, Arthurian romance, Middle English poetry) and many commands
(`!verse`, `!books`, `!ballad`, `!tale`, `!horoscope`...). They are attentive and exacting, check the
bot's replies themselves, and notice sloppiness. Their standing preferences, most learned the hard way:

**Sources and texts**
- **Search properly before settling.** Several web searches with different wordings, specialist sites
  for the field (bestiary.ca, university projects, the National Library of Scotland), not just
  Gutenberg, Wikisource and the Internet Archive. The owner has been upset more than once at lazy
  source-finding. List what you found when it matters.
- **English only**, no untranslated originals. Exceptions: hymns (Latin, Greek, Syriac lyrics are fine)
  and **Middle English / Scots, which the owner explicitly wants** ("I don't care about middle english
  being hard"). Latin poems inside an English edition are left out (Skelton's, Gower's Latin verses).
- **ȝ þ ð as themselves, never a stand-in**: not a transcriber's "3" for yogh, not a scribe's "y" for
  thorn. Convert stand-ins only where unambiguous (yat/yar/yis/yaim → þat... but ye/yow are "you");
  early-print abbreviations y^e y^t → þe þat. Where an editor normalized to th/gh (Skeat's Chaucer,
  Wright's Piers, Macaulay's Gower), the letters can't be recovered: say so, don't guess.
- **No copyright or licensing research**, ever. Keep the source string, skip provenance.
- **No raw Internet Archive OCR text.** (Archive *scans*, and Wikisource transcriptions made from
  them, are fine.) Any OCR must be **proofread against every page image** before it goes live; never
  quote an accuracy figure you didn't measure against the images.
- **Common texts (prayers, the Rosary): just use a mainstream source** such as Wikipedia.
- **Can't get the real thing? Leave it out.** Never substitute a YouTube or other link.
- sacred-texts.com is the owner's preferred first source but blocks this machine (Cloudflare); its
  mirror archive.sacred-texts.com has worked before.

**Content and size**
- **Never cut content to save size** (audio, stanzas, chapters) without asking. Keep pieces whole.
- Curated scholarly tables (e.g. `!quoted`) are verified against the loaded text; disputed entries
  are left out and noted in the commit message (CLAUDE.md "Content standards").
- **Citation style (owner's decision, 2026-10-25): a book that is all one chapter is cited by verse
  alone.** "Jude 3", "Sir Orfeo 233-260", never "Jude 1:3". "Jude 1:3" is still *read*, never *shown*.
  Books in parts keep part:line ("Troilus 3:1", "Confessio Amantis 5:6435"). See §4.

**Money**
- The owner pays for an Anthropic API key (used by `!horoscope`). **Ask before any paid request**,
  even one test, and say what it costs. Tests and stress runs must never reach it.

**How to talk and report**
- **Don't use the TaskCreate / TaskUpdate task list** — the owner dislikes it sitting under the
  prompt. Ignore the system's reminders about it; give progress in plain messages.
- Report outcomes faithfully: what was done, what was checked, what wasn't, what's left. Say plainly
  when something failed or a check was skipped.
- When unsure what the owner wants on a judgement call (an edition in modernized spelling, a change
  to how citations look), ask with AskUserQuestion and a recommendation; otherwise act.
- **Changelog entries need the owner's OK** before you write them (even though CLAUDE.md says every
  user-visible change gets one): ask "changelog entry?" at the end of a feature. Write them for Discord
  users who know nothing of the code (CLAUDE.md has the style; read the existing entries).
- Don't raise the "Sophia" rebrand idea unless the owner does.

---

## 2. The workflow for every change

CLAUDE.md has the rules; this is the practical sequence with the commands that work on this machine
(Windows, PowerShell 7, Python 3.14 at C:\Python314).

1. **Build / edit.** Corpus builders are in `scripts/` (see §5). Temporary scripts go in the job's
   tmp folder, never in the repo.
2. **Clean:** `python scripts/clean_corpora.py`. Aim for it to change **nothing**: fix the builder so
   the cleaner has nothing to do (`python scripts/inspect_corpus.py cleaner english/x.json` shows what it
   would change). Its rules can mangle text (it turned "most~ Say" into "mostSay").
3. **Tests:** `python -m pytest -q` (~2 min, ~1400 tests, offline). Guard commits on its exit code.
   `tests/test_fable.py::...another_never_repeats...` is flaky (random); it passes on rerun.
4. **Corpus check** on the files you touched: `python -m pytest -q -m corpus -k latin` (tests/test_corpus_files.py,
   a test per data file: web leftovers, stray sigla, clean_corpora has nothing to do, and the citations rule
   from tests/test_citations.py: **source strings ≤ 80 chars, editor and date only, no URLs or site names**; use
   `book_sources` for a file mixing editions). The owner (2026-11-02): don't re-check untouched books; a new
   addition gets its own new tests instead. The whole `-m corpus` only when shared cleaning/building code changed.
5. **Stress (always, unasked):** `python -m pytest -q -m stress -k "verse or books"` for the commands
   touched; the whole `-m stress` (~3–6 min) when core.py or a shared helper changed. Fix what it finds;
   never loosen the checks. New citation forms or inputs go into `stress.SHAPED[command]`.
6. **Registry:** adding/removing a command fails `tests/test_command_registry.py`; regenerate with
   `python -c "import tests.test_command_registry as t; t.regenerate()"`. INTRODUCTION.md must mention
   every command (`tests/test_introduction.py`), and each intro section must fit Discord (≤ 3800 chars).
   The latest CHANGELOG entry must fit in 4000 chars (`tests/test_changelog.py`).
7. **Commit** with `git commit -F <msgfile>` (summary line, a body saying *why* and what was checked
   or left out, and the two trailer lines from the attribution reminder). **Stage files explicitly**,
   never `git add -A`. Never commit runtime state in data/ or rebuildable media (.gitignore covers them).
8. **Push** right after: `git push`. Confirm with `git status -sb` (should read `## main...origin/main`).
9. **Deploy:** `Restart-Service ScriptureBot`, wait ~45 s, then
   `Get-Content C:\ProgramData\nssm\logs\scripturebot.err.log -Tail 8` and look for "Logged in as" and
   "Synced N slash command(s)" (88 after the 2026-11-08 tidy; Discord's ceiling is 100, see §6) (and "Changelog: posted N update message(s)" if you added entries).
10. **Live stress:** `python stress.py verse books` (posts to #bot-testing in the owner's server only).

The service runs as `NT SERVICE\ScriptureBot`: it can write only files directly in `data\`, `backups\`,
`.avatar_hash` and the logs; packages must be in `C:\Python314\Lib\site-packages`. Changing the service
itself needs the owner in an admin PowerShell. If a force-push is ever needed, the permission classifier
blocks it: give the owner `! git push --force origin main` to run.

---

## 3. Environment traps that cost hours

- **PowerShell + inline Python quoting breaks constantly** (`python -c "..."` with quotes, `<`, `'`).
  Write a small script file in the tmp folder and run it instead. Same for `Select-String` patterns
  with special characters.
- **Don't rewrite source files with PowerShell `Get-Content`/`.Replace`/`Set-Content`**: it mangled
  `tests/test_lookup.py` (encoding and line endings: the whole file changed, then a SyntaxError).
  Use the Edit tool; for a block replacement by line number, PowerShell `List[string]` `RemoveRange` /
  `InsertRange` worked, but Edit is safer. `git checkout -- <file>` to recover.
- **The Edit tool fails on invisible characters**: a line containing a non-breaking space didn't
  match. Read the exact lines first, or replace by line number.
- **Console encoding**: PowerShell shows ȝ þ as garbage unless the Python script reopens stdout as UTF-8
  (`sys.stdout = io.open(sys.stdout.fileno(), "w", encoding="utf-8", closefd=False)`), as the
  inspect tool does.
- **Catastrophic regex backtracking**: `(?:...<span>.*?</span>)*` inside a repeated group hung a build
  for minutes. Use `[^<]*` inside tags, not `.*?`. If a build that used to take seconds runs > 2 min,
  it's this; stop it (TaskStop) and fix the pattern.
- **Long commands**: anything over ~2 min should run in the background; you're notified on completion.
  Don't poll with sleeps. `Wait-Process -Id <pid> -Timeout 590` works to block on one.
- **Rate limits / blocks** (don't try to evade any of them):
  - Wikisource API: 429 unless paced and given a User-Agent.
  - Wayback Machine availability API: 429 (it was still refusing at the end of this session).
  - Bibliotheca Augustana (hs-augsburg.de/~harsch): 503 all session.
  - Michigan's Corpus of Middle English (quod.lib.umich.edu/c/cme): Cloudflare challenge, 403.
  - TEAMS (d.lib.rochester.edu/teams) and METS (metseditions.org): 403.
  - sacred-texts.com: Cloudflare.
  - Virginia's e-text center: gone.
- **Gutenberg quirks**: some editions are several HTML files (#30282 Pearl → `poems.html`; #42713
  King Horn → `KingHorn_KH.html`; list `https://www.gutenberg.org/files/N/N-h/`). Some hold a text twice
  (#14568 Gawayne: once with 3 for yogh, once with ȝ). Headings often have `<br>` or an `<a id>` inside,
  so match loosely (`until_heading()` in build_english.py). Old files write `class = "x"` with spaces.
  The full catalogue is at https://www.gutenberg.org/cache/epub/feeds/pg_catalog.csv (21 MB) — searching
  it (by Language "enm", Subjects, editor names like Skeat/Furnivall/Morris) found most of the Middle
  English texts.

---

## 4. How the library works (for adding books)

`scripture_lookup.py` is the heart. Corpus JSON is `{"source": ..., "books": {book: {chapter: {verse:
text}}}}`, string keys (README "Data").

**Registering a new corpus or file:**
- `corpus_dirs` in `ScriptureLookup.__init__`: corpus folder → list of files (a missing file only warns).
- `CORPUS_PRIORITY`: the order books are looked up in.
- `TRADITIONS` ("english": ("📜 Medieval English poetry", ("english",))) and `TRADITION_ALIASES`;
  `CORPUS_TRADITION` follows. A new tradition also needs `bot_commands/packs.py` `TRADITION_CHOICES`
  (the setup menu) and, so servers that chose everything get it, `core.ADDED_TRADITIONS`.
- `ALIASES` (lower-case keys → book name). Check new titles don't collide: an exact title wins, but
  short words ("Proverbs", "Truth", "Patience") can be taken; name such poems inside a collection
  ("Chaucer's Shorter Poems" part 13 is *Truth*).
- `source_map` in `_get_verse` (corpus → fallback credit).
- `bot_commands/books.py` `BOOKS_TREE` (the `!books` shelves) and `_SUPERGROUP_ORDER`.
- INTRODUCTION.md paragraph with a `<!-- texts: corpus -->` marker (shown only to servers with that
  tradition), README "Data" paragraph, and tests (copy tests/test_english.py's shape).

**Line-chunked books** (cited by line, like Homer): passages keyed `"part.firstline"` (`"1.233"`,
`"3.1"`), each `{"1": text}`. Regrouped on load into part → {first line: passage}; `!verse Book 3:240`
finds the passage holding line 240 (`_line_span`). A file says so with `"line_chunked": true` at the top
level and the loader registers its books (no hard-coded list needed; the old `_LINE_CHUNKED` tuple
still covers Homer, Dante, Hesiod...). The Faerie Queene and Canterbury Tales are *not* line-chunked
(book.canto:stanza, tale:paragraph).

**One-chapter books** (owner's rule): `_one_chapter(book)` (the book's only chapter is "1"):
- `_homer_lines` rewrites "Book 233" / "Book 233-260" to "Book 1:233(-260)" before parsing;
- `_get_verse` labels the reply "Book 233–260" (`chap_label = canon_book`), errors say "Book has no…";
- `_cite(book, chap, verse)` builds every *displayed* reference (random, search, card.py's Strong's list);
- **`get_verse(ref, whole=True)`** gets the whole of a one-chapter book: `core.fetch_chapter_result`
  (the `!books` browser) uses it — without it "Wace 1" would show only verse 1.
- Line 0 and backwards ranges ("260-233") are handled in `_line_span`.

---

## 5. Building corpora: the tools

- `scripts/build_arthurian.py` — the Arthurian legend (translations) and, because they were begun
  there, the Faerie Queene and Canterbury Tales (saved to data/english). Helpers: `gutenberg(n)` (cached
  in `scripts/.cache/arthur/`), `clean`, `chapter(title, paras)` (title in italics leads verse 1),
  `title_case`, `roman`; In Parentheses PDFs via PyMuPDF (`inpar`, Mac Roman text, `DROP_CAPS`).
- `scripts/build_english.py` — Middle English and later poetry. `python scripts/build_english.py
  [names...]` builds all or some (`BUILDS` dict: auchinleck, pearl, havelok, horn, sowdone, torrent,
  genesis, wright, troilus, fame, chaucer1, gower, piers, sisam, arthur_me, bruce, wallace, chaucerian,
  ludus, skelton, hawes, scots, lydgate, cocke). Its toolkit:
  - `drop(html, tag, cls)` / `keep(...)` / `keep_each(...)`: nesting-aware remove / extract elements
    (regex alone can't handle nested sidenote spans).
  - `text(html)`: markup → one line; unwraps all tags (in EETS editions *italic marks the editor's
    expansion of an abbreviation*, so it is never shown as italics), strips leftover combining marks.
  - `numbered_poem(body, junk=..., stanza_cls=..., section=...)`: lines from `<p>`s, stanza breaks,
    `<span class="linenum">` numbers (before or inside the line), section headings → italic notes.
    Variants for each edition's markup: `gutenberg_poem` (span.i0 lines), `skeat_poem` (Skeat's Chaucer
    vols II–III), `skeat1_poem` (Skeat vol I and vol VII, Wright's Piers), `verse_divs` (div.verse /
    line / speaker: Macaulay, Jamieson, Dyce, Halliwell), `sisam_verse`, `p_stanzas` (early prints).
  - `number_lines(marks)`: fills the numbers between the edition's marks, so passages are keyed by the
    edition's own lineation (handles long-line numbering, gaps, half-lines). `group_lines(items)` makes
    paragraphs; `line_chunked(title, paras, part, heading)` makes the keys and **prints a warning
    whenever passages merge because numbers went backwards** — that warning always means something to
    fix (a second lineation, an alternative text, a restart), not noise.
  - `passages()` cuts paragraphs over ~40 lines into ~30-line passages at couplets.
  - `printers_marks` / `printers_letters`: early-print abbreviations (y^e þe, w^t with, tilde/macron =
    n/m). `heading_case` (title case keeping Roman numerals). `mostly_latin` (share of common English
    words < 10%). `in_twenties` (long couplet runs → ~20-line verses for non-line-chunked books).
  - `save(name, source, books, out, book_sources, line_chunked=True)`.
- `scripts/inspect_corpus.py` — read-only checks: `stats` (passages, longest, leftover markup, unclosed
  italics), `show`, `heads`, `big`, `cleaner` (what clean_corpora would change), `letters` (ȝ þ ð and
  stand-ins). Use it on every new file before registering it.

**What each edition taught (so the next one goes faster):**
- Editors print **second lineations** (Zupitza's `{1905}` in Guy; Halliwell's `[2531]` in Torrent;
  Macaulay's other-recension `(3550*)` in Gower): drop them or the numbers jump.
- Editors print **parallel texts** (King Horn's three MSS side by side: take one column; the Legend of
  Good Women's Prologue A and B: take B; Gower's *-marked alternative passages: drop the starred ones;
  the Romaunt's French beside the English: first column only; smaller-type borrowed lines: drop).
- **Speaker labels and rubrics** are not numbered lines: make them italic notes (Auchinleck's
  "dominus ait.", Thrush's "Þe Niȝtingale", the Bruce's *-rubrics). But **italic refrains are lines**
  (Chaucer's roundels): headings are recognised by their wording (`SKEAT_HEADING`), not by italics.
- Editors' marks to strip from the text: `*` on emended words (Havelok, Bruce, Lancelot), `†`/`*` on
  lines in one text only (LGW), stanza numbers ("2. To thee clepe I"), `<...>` supplied words (→ `[...]`).
- Old OCR slips: "1" for "l" ("chape1"), "~" for "?" — check suspicious digits and symbols inside words.
- Verify numbering against the edition: for Auchinleck every numbered line was checked to fall in
  the right passage. Do the same for any new line-chunked edition (look up a few marked lines).

---

## 6. State of things (2026-10-25)

**Live:** the Arthurian legend (20 translated works + 5 Middle English poems) and the medieval English
poetry tradition: Chaucer (all the poetry), the Chaucerian pieces, Gower, Piers Plowman and the Crede,
Pearl/Cleanness/Patience, the Auchinleck manuscript (39 + 2 Arthurian), Havelok, King Horn, Sir Orfeo
(Sisam), the Sowdone, Torrent, Genesis and Exodus, the Wright's Chaste Wife, the Bruce, Wallace, Sisam's
lyrics/political poems/York and Towneley plays, the Faerie Queene, and (second batch) the N-Town plays,
Skelton, Hawes, Eyre-Todd's Scots poets, Lydgate's Disguising, Cocke Lorelles Bote. Changelog entries
for the Arthurian books and the first medieval batch were posted 2026-10-25.

**Closed (owner, 2026-10-26): the Middle English corpus is finished.** "We're good for middle english":
don't add more medieval English texts unless the owner asks. The second batch's changelog entry was posted
2026-10-26; Everyman and Rhys's modernized miracle plays were left out by the owner's decision; the Owl and
the Nightingale (the Oxford Text Archive's transcription of Atkins 1922, found on llds.phon.ox.ac.uk) was
left out after a costly proofread against the scans, which the owner did not want (ask before any such
work). The retry found nothing for Ywain or the Alliterative Morte Arthure (Augustana still 503, and its
archived pages never had them; Virginia's text wasn't archived; the OTA's Morte is academic-login only).
The list below is kept as a record only.

**Not done, and why (record only):**
- *Ywain and Gawain*, the Alliterative *Morte Arthure*, *The Owl and the Nightingale*, the Stanzaic
  *Morte Arthur*, Lovelich's *History of the Holy Grail* and *Merlin*, the Prose Merlin: only online at
  sites that were blocked or down (Augustana 503, Wayback 429, CME Cloudflare, TEAMS/METS 403). Retry
  Augustana and the Wayback Machine (copies of Augustana and the old Virginia e-text center); don't evade.
- Paton's 1929 *Sir Lancelot of the Lake* (Vulgate Lancelot), Gottfried's *Tristan* (Weston 1899),
  Thomas's *Tristan* (Loomis 1923): exist as scans only → would need OCR with a full page-by-page proofread.
- Gutenberg candidates not yet built: *Erthe upon Erthe* (#33768, printed from 24 MSS: pick one),
  Hall's *Early Middle English Selections* (#26413, extracts), Wright's *Political Songs* (#61511,
  mixed English/French/Latin: English only), Pollard's *Fifteenth Century Prose and Verse* (#30851),
  Percy's *Reliques* (#45939-41), *The Interlude of Wealth and Health* (#17270), Skeat's *Kingis Quair*
  (not found on Gutenberg; search elsewhere).
- Luminarium has ~40 short Middle English lyrics (luminarium.org/medlit/mltexts.htm) not yet added
  (some duplicate Sisam's: Alysoun, the Maid of the Moor).
- An agent found that the Perseus plays (data/classical/perseus) run speaker names into the text; not
  fixed (a separate task).

**Deliberately left out:** prose (Chaucer's Boece, the Testament of Love, Jack Upland, Mandeville);
Gower's Latin verses and sidenotes; Skelton's Latin poems and the poems only attributed to him; Sisam's
extracts from longer works; two Auchinleck fragments (a list of Norman names; a two-line poem); the
Auchinleck Orfeo (Sisam's is the same text with its lost opening). Lydgate's Disguising has no þ: its
transcriber printed th.

**Shakespeare (added 2026-10-26, live, changelog posted):** `scripts/build_shakespeare.py` → `data/shakespeare/`
(the Folger TEI downloads; the owner chose Folger's modern spelling over the First Folio). A scene is a chapter
(`Hamlet 3.1`; Prologue/Induction `0`, a chorus `2.0`, Epilogue `6`), passages keyed by Folger's line numbers,
line-chunked; `last_lines` in the file lets the lookup reach a scene's last lines. `lines.json` holds every line
(speaker, text, prose flag, speech number) for `!shakespeare` (oracles.py): dice for play (First Folio order, then
Pericles 37, Two Noble Kinsmen 38), act, scene, line, the line shown bold inside its whole sentence (the owner
disliked lines cut mid-sentence), 🖼️ Card and 📜 In context on one row. `!sonnet` gives a sonnet or a stanza run of
the other poems. Credit is just "Folger edition" (the owner found the editors' names excessive). "Julius Caesar" is
Suetonius, so the play is `Shakespeare: Julius Caesar` / `JC`. Not built, by choice: the 1866 game *Shakspeare's
Mental Photographs* (Gutenberg #56851) and a daily line. Adding a tradition is now at Discord's limits: the setup
menu holds exactly 25 (a 26th needs the menu split), and `/search` takes traditions by autocomplete
(`tests/test_slash_limits.py` guards both).

**Illustrations and journeys (added 2026-10-26, live, changelog not yet asked for):** the owner wanted the old
illustrated editions *without a command of their own*: a 🖌️ button under `!verse`, `!fable`, `!tale` and `!shakespeare`
(`bot_commands/illustrations.py`, data from `scripts/build_illustrations.py`, its docstring lists the nine sets). Pictures
from a different translation are tied to the bot's by text overlap *and* title, the doubtful ones read side by side and
settled in `AESOP_SAME` / `GRIMM_SAME`; Boydell's scene numbers are checked against Folger's by required words. Not done:
most of Crane's *Faerie Queene* designs (only in Archive scans: page-image work, ask first), Flaxman's Homer, Doré's
other books, the Ellesmere Chaucer portraits (ideas, not asked for). `!journey` gained `canterbury`, `odyssey`, `aeneid`
(places in `journeys.PLACES`; legendary places where antiquity put them, ringed, the note saying who).

**How the owner wants checks run (2026-10-26):** proportionate. The 12-minute corpus check only when corpus *text*
changed (else compare `books` with HEAD); never OCR or proofread scan images without asking first (token cost).

**Handoff, 2026-11-02 (all committed, pushed, live; nothing uncommitted):**
- *Esoteric shelf* (data/esoteric, tradition "gnostic", never opt-in): Agrippa, Pico, Ficino (an AI translation,
  labelled so; the owner accepted it), the Solomonic books, grimoires, Dee, Lilly/Sepharial, Swedenborg, the
  magical papyri and Mithras Liturgy, 46 alchemy treatises. Builders: build_esoteric/papyri/mithraic/pico/
  alchemy/ficino.py.
- *Classical in !books* is two sections, `🏛️ Greek` and `🦅 Latin`, which the 🏛️ Classical menu opens to directly
  (the owner: no "Classical inside Classical", no Perseus shelf). Perseus authors are filed into them by
  `PERSEUS_PLACES` / `SHELF_ORDER` in books.py; an unplaced one lands on Greek → "More" (a test fails).
- *Latin* (scripts/build_latin.py → data/classical/latin.json; `python scripts/build_latin.py <step>`): Seneca
  (dialogues, On Benefits, Natural Questions, Moral Letters, nine tragedies), Pliny the Younger, Pliny the Elder's
  Natural History (37 books), Petronius, Ovid's Fasti, Statius, Valerius Flaccus, Hyginus (from ToposText: theoi's
  own Fabulae pages are now truncated), Fulgentius, Dares, Dictys, plus the older Cato/Varro/Cicero/Distichs.
  theoi.com pages are cached by scripts/fetch_theoi.py. Poems, plays and the Moral Letters are stored line-chunked:
  the file's `line_chunked` *list* names them (scripture_lookup now accepts a list there as well as `true`).
  Seneca's Medea/Agamemnon/Phoenissae carry "(Seneca)": "Phoenissae" alone resolves to Euripides via the Perseus
  aliases. Tests: tests/test_more_latin.py.
- *Ask the library* (bot_commands/ask.py) runs on claude-sonnet-5-5 with gnostic, esoteric and catholic shelves
  (CCC, canon law, the Summa from data/summa.json, gitignored). **Private:** never in the changelog,
  INTRODUCTION.md or !help.
- *grok reply* (bot_commands/grok.py, an on_message listener): "grok is this true?" → a drawn post from @grok
  (the owner's logo in data/grok/logo.jpg) saying yes/no/maybe/a joke; a cooldown of 5 s a person; each answer
  and skip logged as "GROK". **Secret:** same rule as the ask feature.
- *LacusCurtius Latin (done 2026-11-02):* the Historia Augusta (30 lives, each a book "Historia Augusta: Hadrian"),
  Frontinus's Stratagems and Aqueducts (Bennett; Thayer also has Rodgers's 2003 Aqueducts, not taken), Velleius
  ("Roman History"), Florus (Halm's four-book numbers, as Thayer's marks have them; Forster's two-book chapter titles
  in italics). `lacus()` in build_latin.py handles Thayer's page variants (unnamed or <SPAN>-labelled chapter marks,
  headings at page tops, gaps, • pop-ups); the Latin Historians shelf is time-ordered by `AUTHOR_ORDER` in books.py.
- *The Revelations of Methodius (2026-11-02, the owner's request: Middle English reopened for it):* the Corpus of
  Middle English (quod.lib.umich.edu/c/cme) still blocks scripts with Cloudflare, so the owner opened the page and
  pasted its text into scripts/.cache/cme/Text.txt ("Save page" only saved the challenge page). The paste loses the
  line breaks but keeps the editor's every-fifth-line numbers, so `methodius()` in build_english.py rebuilds the
  lines at the scribe's stops, flags unclear blocks, and METHODIUS_SPLITS settles them by the rimes. The same route
  works for any other CME text the owner wants.
- *Metatron literature (2026-11-07, the owner's request):* Ginzberg's *Legends of the Jews* vols 1-4
  (scripts/build_jewish_legends.py, Gutenberg; a story a chapter, "1.37" Enoch's ascension); *3 Enoch* as Source
  Library's machine translation of Vatican MS Ebr. 228, Odeberg's base manuscript (scripts/build_3enoch.py; the
  owner chose it over OCR-and-proofreading Odeberg's scans: no clean transcription of Odeberg exists online; the
  48 "Rabbi Ishmael said" openings are Odeberg's 48 chapters). Its API: sourcelibrary.org/api/books/<id>/text?content=
  both&format=json (text has zero-width watermark characters: strip them). The Targum lookups were broken (Sefaria
  titles "Targum Jonathan on Genesis", "Aramaic Targum to Psalms"; its Neofiti is 8 verses). Not found in English:
  al-Kindi, al-Masudi, al-Suyuti, al-Buni on Metatron. The same MS 228 has *Hekhalot Rabbati* from scan 142 if wanted.
- *Open:* ~~Juvenal and Martial~~ (done 2026-11-09: Ramsay on Wikisource, Bohn on tertullian.org; build_latin.py
  `juvenal`, `martial`, `persius`; two Persius openings come from the book's Page: transcriptions); Hyginus's Astronomica books
  1, 3, 4 (only Book 2 is transcribed anywhere found); Ptolemy's Almagest (OCR only: the owner said no OCR
  "at the moment"); the PDF guides (scripts/build_guides.py) haven't been rebuilt since these books.
- *Traps met this time:* clean_corpora deletes runs of "* * *" as stray markdown, so a builder must turn an
  editor's lacuna stars into "…" itself. PowerShell eats `"` and `<` inside `python -c`: write a scratch .py. The
  fable test flaked because the 🎲 fallback picked the same fable from another collection (fixed).

**Handoff, 2026-11-08: the Norse shelf (all committed, pushed, live; nothing uncommitted, nothing open):**
- *What's there:* `!edda` (Bellows's Poetic Edda), `!odin` (`!wotan`, `!woden`: Odin's own words, by Bellows's speaker
  headings in data/norse/edda_speakers.json, plus Hollander's Eiríksmál and the 37 riddles of Heiðreksgátur),
  Hollander's *Old Norse Poems*, Snorri's Heimskringla and Prose Edda, the Völsunga saga (data/norse/).
- *The Old Norse:* data/norse/edda_norse.json `{poem: {stanza: text}}`, built by scripts/build_edda_norse.py from
  heimskringla.no (Guðni Jónsson's Eddukvæði, 1949; Eiríksmál from Finnur Jónsson's Carmina Scaldica, 1929). Bellows
  reorders/splits stanzas, so they're matched by content (align()); every pairing out of sequence was read by hand
  and the wrong ones fixed in `OVERRIDES`; Hollander's poems in `HOLLANDER` (the riddles' numbering is shifted by
  one after Hollander's 23, which Guðni hasn't). 1539/1566 Bellows stanzas + all but one riddle have Norse.
  `python scripts/build_edda_norse.py --report` (~20 s) shows every pairing.
- *How it's shown (the owner's choices, settled after several rounds; don't redo without asking):* **not** in the
  `!edda`/`!odin` message (too big). It comes by the 📜 Old Norse button, `!parallel havamal 139`, or `!odin norse`:
  English and Norse as two inline embed fields, a half-line to a line in both. Messages show Bellows's lines split at
  the caesura (`_half_lines` in oracles.py; Hollander's em-space caesura too). Buttons: ◀ ▶ 🖌️ on row 0; 🖼️ Card,
  📜 Old Norse, ᚱ Runes on row 1 (`_view_after` rebuilds them from the message when one is pressed).
- *Cards (bot_commands/card.py):* Edda cards are a printed poem: half-lines, upright, flush left, second halves
  indented (a leading tab marks them), no quotation marks. `_render_parallel_card`: English | Old Norse columns.
  `_render_runes_card`: runestone style, one continuous run filling the card, in **BabelStone Runic Norse**
  (fonts/BabelStoneRunicNorse.ttf: the service can't read fonts installed per-user) with Norway's mixed runes
  (runes.py: short-twig ᛆ ᚿ ᛐ ᚮ, long-branch ᚼ ᛘ ᛒ ᛋ), labelled a modern transcription. Norse cards have a smooth
  plaited band (`_draw_plait`, drawn at 4x).
- *Tried and rejected by the owner:* hand-drawn straight-stroke runes (looked bad; reverted, its changelog post
  deleted). No runic font without curves exists among those found (BabelStone family, Noto, Segoe UI Historic).
- Tests: tests/test_edda_norse.py, test_odin.py, test_edda_command.py, test_card_styles.py.

**Handoff, 2026-11-08 (later): the command tidy (all committed, pushed, live; changelog posted):**
- *Why:* the bot was at **100 slash commands, Discord's ceiling** (`tests/test_slash_parity.py::test_within_discords_slash_limit`
  guards it); one more and the whole sync fails. Now **83**: room again, but spend it carefully. The owner asked for
  redundant commands to go; candidates were picked from `data/guild_activity.json` (every `!` command per server since
  launch; the older `stats.json` counts were partial, see below) plus plain duplication. Don't bring these back.
- *Folded into another command (old name → now):* `!mp` `!ep` `!psalm` `!collect` → `!bcp morning|evening|psalm|collect`
  (`/bcp` has part and period choices; `!bcp mp` now gives the whole office); `!psalm 23 sing` → `!metrical 23`;
  `!psalm 110 chant` → `!chant psalm 110`; `!unsubscribe` → `!subscribe off`; `!study` → the Catena button;
  `!votdmode` → `!votdsetup mode`; `!concordance` → `!strong G26 verses`; `!root` → `!strong G26 root`;
  `!reverseinterlinear` → `!interlinear reverse` and the 🔁 button; `!leaderboard` now shows the quiz's.
- *Retired outright:* bookmarks (`!save`, `!saved`, `!unsave`, the 📌 reaction) and `!features` (nobody had a bookmark;
  the `!plan` streak, its one non-bookmark flag, is always on); `!scanstats`; the legacy VOTD migration and
  `data/votd_mode.json`; `deprecated/` (its scripts are in git at 5e99f69, which the lookup modules' docstrings name).
- *Prefix-only on purpose* (`PREFIX_ONLY` in test_slash_parity, each still reachable by slash): `!delphi` (`/oracle`),
  `!parsha` `!dafyomi` (`/learning`'s choice), `!hymnlist` (`/hymn list`), `!leaderboard` (`/quiz`'s choice).
- *Admin daily posts:* `!daily` (bot_commands/daily.py) lists them all and hands `!daily saint channel #x` on to
  `!saintsetup`; the ten `*setup` commands are `hidden=True` but still work, and `/setup <kind>` is unchanged.
  `!changelogsetup` stays separate (not a daily post).
- *Aliases removed because they misled:* `!aeneid` `!sortes` `!traditions` `!learn` `!mystery` `!st` `!thomas`
  `!classical` `!poem` `!po` `!matins` `!vespers` `!evensong`; `!liturgy` now opens `!divineliturgy`, `!dailyverse` `!votd`.
- *Counting:* `core.count_command` (from `on_command` and the new `on_app_command_completion`) now counts **every**
  command, `!` and `/`, in `stats.json` and `guild_activity.json`. Until 2026-11-08 only the commands that called
  `record_stat` / `record_special_stat` reached `!stats`, and slash commands were counted nowhere; those two now record
  only which verse or reference was shown. Past counts were left as they were (a backfill would make one weekly report
  show the whole backlog as that week's).
- *Buttons that must survive restarts* are DynamicItems in views with `timeout=None`: `StrongMoreButton` (📖 🌳),
  `StrongPageButton` (◀ ▶ through a long entry, rebuilt by `strong_entry_message`), `InterlinearFlipButton` (🔁).
- *The posted introduction:* only edited in place where `guild_config.json` has a `changelog_intro` record (written by
  `!changelogintro`). ℍ𝕐ℙ𝔼ℝℍ𝕀𝕊𝕋𝕆ℝ𝕐's predated the record; the owner ran `!changelogintro fresh` there, so it's tracked
  now. A line naming only `!daily …` and a pack's command needs a `<!-- pack: x -->` marker, or it shows in servers
  with that pack off (test_packs caught the troparion, Angelus, hymn-of-the-day and learning lines).
- *The PDF guides* (scripts/build_guides.py) were one-offs, the owner says: don't offer to rebuild them.
- *Wikimedia pictures are local copies (2026-11-08):* Wikimedia began refusing full-size originals (429), so `!dore`,
  `!blake` and the 🖌️ buttons showed empty embeds. Each Commons entry now has a `"copy"` (a ≤1200 px JPEG in
  data/{dore,blake,illustrations}/copies/, gitignored, ~300 MB) that the bot attaches (`core.local_picture`: own
  `"file"`, then `"copy"`, then the address). Rebuild: README "Pictures". `scripts/wikimedia_copies.py` asks for standard
  thumbnail widths only; its 429s are momentary (5 s back-off, not a minute). The weekly source check counts missing copies.
  New Commons pictures (any new set) must go through it too, or they'll be blank.

**2026-11-09 (all committed, pushed, live):** Perseus plays' speaker names now open their speeches (perseus_tei);
the Ellesmere Chaucer's 23 pilgrims under the Canterbury Tales (🖌️, `chaucer_ellesmere`); Hekhalot Rabbati, Sar Torah
and the Chapter of Rabbi Nehuniah (scripts/build_hekhalot.py, MS Ebr. 228 again); Juvenal, Persius and Martial. Flaxman's
Iliad (34 plates, at the Greek line engraved on each) and Odyssey (20, Réveil's, placed by scene) under !verse (🖌️):
`iliad_flaxman`, `odyssey_flaxman`; the owner approved reading the plates. !homer is the dice oracle (no line refs),
so they're not under it.

**Avesta finished (2026-11-09, live; no changelog entry yet -- ask the owner):** `build_world_texts.py avesta` now also
builds the Visperad, the Khorda Avesta prayers (Nyayeshes, Gahs, Afrinagans, Sirozahs: a "Khorda Avesta" shelf),
Avesta Fragments and Yashts 22-23, and fixed the Yasna's Gatha chapters (they had held Mills's commentary). Changelog
posted (with !gathas, the Gathas oracle: new, said plainly not an old custom).
Then, all live: `build_world_texts.py pahlavi` (Menog-i Khrad, Shikand-gumanik Vizar, Bahman Yasht, Zadspram,
Dinkard 7, Arda Viraf from avesta.org) and `shahnameh` (Zimmern's Epic of Kings); bot_commands/zoroastrian.py:
!roz (Shahenshahi/Kadmi/Fasli day, Sirozah line, festivals, gahs; anchor Navroz 1395 = 2025-08-15), !daily roz, and
the 🔤 Terms button under Zoroastrian !verse; !prayer ashem vohu / ahuna vairya / airyema ishyo; Zoroastrian passages
in six !story stories; 🖌️ `shahnameh_tahmasp` (12 Met folios at Zimmern's paragraphs). Changelog posted.
Then (live, no changelog yet -- ask): !gathas a daily-oracle kind; the rest of West's Pahlavi books (Sad Dar,
Shayast-la-Shayast, Dadistan-i Dinik, Manuskihar's Epistles, Dinkard 5/8/9) and `_split_missing` putting back ~90
verses whose numbers the OCR lost or misread (19 left with no number in the text at all).

**Bahá'í (2026-11-09):** `scripts/build_bahai.py` builds every work of the Báb, Bahá'u'lláh and 'Abdu'l-Bahá in
bahai.org/library (its .xhtml) plus Bahá'í Prayers and the Aqdas's Q&A; the Íqán, Epistle, Gems etc. a chapter a
paragraph as cited (the Íqán's ¶213 checked). Hidden Words and Aqdas kept from before. Shoghi Effendi's 7 books
added at the owner's word (interpretation, but in the Talmud's/Fathers' role); the UHJ's not. The Persian Bayán from
Terry's English of Nicolas's French, citation "unofficial: ...", only the Báb's bold text. The Arabic Bayán exists the
same way (bahai-library.com/bab_bayan_arabic_terry), offered to the owner, not added. Not in English at all: the
Kitáb-i-Badí', most tablets. No changelog yet for any of this -- ask.

---

## 7. Where things are

- Bot entry `bot.py`; shared state and helpers `core.py`; commands in `bot_commands/` (a new module
  must be imported in bot.py); lookups `scripture_lookup.py`; corpus cleaning `corpus_clean.py` +
  `scripts/clean_corpora.py`; stress harness `stress.py`; tests in `tests/` (`conftest.py` redirects
  runtime files to a temp folder — add new runtime paths to `RUNTIME_FILES`).
- Corpus builders: `scripts/build_*.py` (each module docstring says what it builds and from where).
  Download caches: `scripts/.cache/` (not in git).
- Memory (persists between sessions): `C:\Users\chris\.claude\projects\C--Users-chris-OneDrive-Desktop-
  Projects-Scripture\memory\` — MEMORY.md is the index; the files hold the owner's rules summarised in §1.
- The PDF guides the owner sends people: `python scripts/build_guides.py` → `guides/` (not in git).
