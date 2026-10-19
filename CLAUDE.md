# Scripture Discord Bot — notes for Claude

See README.md for what the bot does, the command list, layout, and data schema.

## Workflow (every session)

- Run `python -m pytest` before committing; it takes a few seconds and needs no network.
- **After every commit, `git push`** to origin (private GitHub repo). The owner wants
  GitHub kept current with all changes; don't wait to be asked.
- The live bot is the Windows service `ScriptureBot` (NSSM, runs `python bot.py` in
  this folder). Code changes only go live after `Restart-Service ScriptureBot`; then
  check `C:\ProgramData\nssm\logs\scripturebot.err.log` for "Logged in as" and
  "Synced N slash command(s)". Web/cloud sessions can't reach the service — say so.
- Never commit the runtime state files in `data/` (stats, guild_*, user_prefs,
  bookmarks, reading_plans, subscribers, votd_mode, versle, hymnday, saintday, angelus, troparion, deluge, learning). `.gitignore` covers them.
- Never commit audio or images a script can rebuild (the chant in `data/hymns/audio/sung/` and
  `more/`, the chanted psalms, scores, Doré crops); `.gitignore` covers them. The repo was 1.1 GB,
  mostly re-rendered chant, until the history was rewritten on 2026-10-19 to drop it. Downloaded
  media with no other copy (the Sacred Harp, hymn tunes) stays tracked.
- Commit messages: a summary line plus a body explaining *why*, and noting anything
  verified or deliberately left out.
- **Add a `CHANGELOG.md` entry for every user-visible change worth announcing** (new
  commands, new features, fixes users would notice) as part of the same change. The bot
  posts unseen entries to each server's changelog channel when it next starts, so write
  the bullets for Discord users, newest entry first, heading `## YYYY-MM-DD · Title`.
  Never edit the heading of an entry that's been announced (it's the entry's ID).
  Internal refactors and test-only changes don't get entries.
  **Write entries for Discord users who know nothing about the code or tonight's
  conversation** -- the owner found terse entries ("`Mishnah Berakhot 1:1` and
  `John 3:16 - 18` now work") meaningless. For each bullet: one change only; for a
  feature, what it does and why someone would want it, plus an example command; for
  a fix, what users would have seen go wrong ("said 'Unknown book'") and what
  happens now; explain any unfamiliar term (e.g. what the Mishnah or an
  interlinear is) in a few words. Detailed is fine -- an entry can be ~4,000 chars.
- **`INTRODUCTION.md` explains every user-facing command** to new users (posted by
  `!changelogintro`). When you add, rename or remove a command, update it in the same
  change -- `tests/test_introduction.py` fails if a command is missing from it or it
  mentions one that doesn't exist. Same plain-language style as the changelog.
- Only commit when the full test suite passes (guard the commit on the test exit code).
  `python -m pytest -m live` runs the separate checks against real services (e.g.
  netbible.org for `!notes`); run them when touching that code. The bot also checks
  netbible.org weekly and DMs the owner if it breaks (`bot_commands/health.py`).
- **Stress-test every change to a command, without being asked** (the owner wants it automatic):
  1. `python -m pytest -m stress -k "<commands touched>"` (offline; the whole thing takes ~6
     minutes, run it all when core.py or a shared helper changed). It feeds each command
     `stress.HOSTILE` -- gibberish, typos, books that don't exist, emoji, bare symbols, markdown,
     mentions, absurd numbers, other scripts, huge input -- and fails on a crash, the error
     apology, leaked markup ([[ ]], {{ }}, HTML, entities), unbalanced ** or `, "None"/"nan",
     unfilled {placeholders}, or anything over Discord's limits. Fix what it finds; don't loosen
     the checks to pass.
  2. After deploying: `python stress.py <commands touched>` posts a representative sample
     (`stress.LIVE_SAMPLE`) and the replies to **#bot-testing in the owner's server only**, then
     a summary. This also covers the commands that need the internet (`stress.NETWORK`), which the
     offline run skips. A new command gets inputs shaped for it too (bad page numbers, dates...).
  This grew out of the owner's girlfriend's stress-testing of /theme with bare symbols ($ % * _ ~
  { >), which turned up web debris and broken markup (tests/test_corpus_clean.py).
- The two PDF guides the owner sends people (every feature; every work with a command that opens
  it) come from `python scripts/build_guides.py`, into `guides/` (not in git). It tries every
  command it prints against the bot and stops on one that fails. Rebuild them when the library or
  INTRODUCTION.md changes, if the owner wants fresh copies.
- After adding or rebuilding a corpus, run `python scripts/clean_corpora.py` (strips web
  leftovers, licences, footnotes, Beta Code; see README "Cleaning") and then
  `python -m pytest -m corpus`, the slow check that every corpus file is clean.
- Tests must never touch the live runtime files; `tests/conftest.py` redirects them
  to a temp folder for every test. Keep new runtime-file paths in its `RUNTIME_FILES`.

## Code layout rules

- New commands go in the fitting `bot_commands/` module, using `@bot.command` /
  `@bot.tree.command` with `bot` imported from `core`. A new module must be added to
  the import list in `bot.py`, or its commands won't register.
- Shared helpers and state live in `core.py`. Feature modules may import from `core`
  and from each other, but keep the import graph acyclic.
- Build file paths from `core.ROOT`, not `Path(__file__)` (feature modules live one
  directory below the project root).
- Don't define the same top-level name in two places. bot.py once had two
  `_send_parallel` functions; the second silently replaced the first and broke
  `!verse John 3:16 kjv web`.
- Adding or removing a command fails `tests/test_command_registry.py` by design.
  Regenerate the snapshot: `python -c "import tests.test_command_registry as t; t.regenerate()"`
- Corpus data is `book -> chapter -> verse` JSON with string keys (README "Data").

## Content standards

Curated scholarly tables (e.g. `!quoted` in `bot_commands/reference.py`) are verified
against the locally loaded text before an entry is added. Each entry is labelled with
its evidential status (direct quotation / referenced but not extant / close parallel).
Disputed or unverifiable cases are left out and noted in the commit message instead.
Keep to that standard: don't add entries from memory.
