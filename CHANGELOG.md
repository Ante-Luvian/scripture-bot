# ScriptureBot changelog

What's new, newest first. When the bot starts after an update, she posts any
entries a server hasn't seen yet to that server's changelog channel
(`!changelogsetup #channel`); anyone can read recent ones with `!changelog`.

Format: one `## YYYY-MM-DD · Title` section per notable change (new commands,
new features, fixes users would notice), with `- ` bullets written for users.
Once an entry has been announced, don't change its heading — the heading is
how the bot remembers what it has already posted.

## 2026-10-12 · Changelog announcements
- I can now announce my own updates! Server admins: `!changelogsetup #channel` picks where they're posted.
- `!changelog` shows recent updates any time.

## 2026-10-12 · Sortes Biblicae and oracle cards
- New `!sortesbiblicae` (or `!bibliomancy`): the Bible opened at random, the old practice of bibliomancy — with the same study buttons as `!verse`.
- Every oracle answer (`!virgil`, `!homer`, `!delphi`, `!oracle`) now has a 🖼️ **Card** button that turns it into an image.

## 2026-10-12 · Study buttons under verses
- Bible verses from `!verse` now come with **Notes · Cross-refs · Interlinear · Card** buttons — one click to dig deeper.
- "Mishnah Berakhot 1:1" (the way Mishnah results are labelled) now works as a reference.

## 2026-10-12 · NET Bible notes
- New `!notes John 3:16`: the NET Bible's translator's, study, and text-critical notes for a verse (up to 5 verses), straight from netbible.org.
- Numbered markers in the verse show exactly which word each note is about.

## 2026-10-11 · Fixes
- Ancient Near East texts (Gilgamesh, the Baal Cycle, the Hymn to the Aten, the Mu'allaqat…) work again.
- Side-by-side translations like `!verse John 3:16 kjv web` work again.
- The Shepherd of Hermas takes traditional citations: `Herm Sim 9:1`, `Herm Man 4:1:2`.
- `John 3:16 - 18` (spaces around the dash) and Psalms 151–155 labels fixed.
