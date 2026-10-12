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
  bookmarks, reading_plans, subscribers, votd_mode). `.gitignore` covers them.
- Commit messages: a summary line plus a body explaining *why*, and noting anything
  verified or deliberately left out.

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
