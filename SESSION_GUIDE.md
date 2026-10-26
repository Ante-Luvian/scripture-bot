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
4. **Corpus check** after touching any corpus: `python -m pytest -q -m corpus` (~12 min). Includes
   `tests/test_citations.py`: **source strings ≤ 80 chars, editor and date only, no URLs or site names**
   (use `book_sources` for a file mixing editions). Run it in the background (`run_in_background`).
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
   "Synced 51 slash command(s)" (and "Changelog: posted N update message(s)" if you added entries).
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

**How the owner wants checks run (2026-10-26):** proportionate. The 12-minute corpus check only when corpus *text*
changed (else compare `books` with HEAD); never OCR or proofread scan images without asking first (token cost).

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
