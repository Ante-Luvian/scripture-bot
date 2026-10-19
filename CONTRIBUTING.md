# Contributing to ScriptureBot

ScriptureBot is a Discord bot: a library of the Bible and the sacred and ancient texts of the
world, with study tools, daily posts and games. README.md describes what it does and how the
code is laid out; CLAUDE.md holds the working rules in full. The essentials:

## Before you change anything
- `python -m pytest` must pass before every commit. It takes about a minute and needs no network.
- Changing a command? Stress-test it: `python -m pytest -m stress -k "<command>"` feeds it
  gibberish, typos, emoji, markup, huge input and books that don't exist, and fails on a crash,
  leaked markup or anything over Discord's limits. Fix what it finds; don't loosen the checks.
- New commands go in the fitting module in `bot_commands/`; a new module must be imported in
  `bot.py`. Adding or removing a command needs the registry snapshot regenerated
  (`python -c "import tests.test_command_registry as t; t.regenerate()"`), a line in
  INTRODUCTION.md (a test checks), and usually one in the `!help` menu (`help.HELP_MENU`).

## Texts and data
- A corpus is `book -> chapter -> verse` JSON in `data/`. After adding or rebuilding one, run
  `python scripts/clean_corpora.py` and then `python -m pytest -m corpus`.
- Build texts with a script in `scripts/` so they can be rebuilt, never by hand-editing data.
- Don't commit media a script can rebuild (rendered audio, crops, scores), or the bot's runtime
  state files in `data/` (`.gitignore` covers both).
- Curated tables are checked against the text the bot actually has before an entry goes in.

## Commits and changes users will see
- A commit message has a summary line, then why the change was made and what was checked.
- A change Discord users will notice gets a CHANGELOG.md entry, written for people who know
  nothing about the code: what changed, why they'd care, and a command to try.

## Licence
By contributing you agree that your contribution is licensed under the GNU General Public License
v3.0, like the rest of the code (LICENSE). The texts in `data/` come from their own sources and
keep their own terms.
